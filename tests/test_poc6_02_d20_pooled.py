"""POC6-02 — ETF D20 공동 학습 비교(설계 개정 2 §10 · PLAN 판정 2026-10-21).

합성 가격 snapshot · tmp 시장 DB · tmp 보유 파일 · tmp 결과 폴더만 쓴다(라이브 DB · 외부 호출 0).
확인: 06 재사용 · 적격(4종 · 252 · 42) · 경계 · 시간 분리 · 날짜 균형 MAE · 세 조건 경계 · 결정성 ·
snapshot 개인 값 제외 · 결과 폴더 원자 쓰기 · RTX 실행기(GPU_NOT_RUN · 손상) · 취합 대조 · MLP 학습 규칙.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import shutil
import socket
import sqlite3
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from app import holdings as holdings_module
from app import market_data_store
from app.d20_pooled import gpu_runner, mlp
from app.d20_pooled import report as R
from app.d20_pooled import runner
from app.d20_pooled import study as S
from app.d20_pooled.snapshot import (
    SnapshotError,
    build_snapshot,
    digest,
    load_snapshot,
    snapshot_problem,
)
from app.market_benchmark_store import MARKET_BENCHMARK_DAILY_PRICE_DDL
from app.market_briefing import calendar as cal
from app.market_data_store import ETF_DAILY_PRICE_DDL, ETF_MASTER_DDL
from app.reentry_review import model as m06
from app.reentry_review import prices
from app.reentry_review.prices import FDR, NAVER

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "scripts" / "run_d20_pooled_research.py"
N = 560
TICKERS = ("A01", "A02", "A03", "A04")


def _weekdays(start: str, n: int) -> list[str]:
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


DATES = _weekdays("2023-01-02", N)


def _walk(seed: int, n: int = N) -> list[float]:
    rnd, c, out = random.Random(seed), 10000.0, []
    for _ in range(n):
        c *= math.exp(rnd.gauss(0.0002, 0.015))
        out.append(round(c, 2))
    return out


def _rows(
    closes, dates=DATES, source=NAVER, fetched="2026-10-05T00:00:00Z"
) -> list[list]:
    out, prev = [], None
    for d, c in zip(dates, closes):
        out.append([d, c, source, fetched, None if prev is None else c / prev - 1.0])
        prev = c
    return out


def _snap(etfs: dict, dates=DATES) -> dict:
    """06 `research_axis` 와 같은 모양(연도 파일 없음 = KOSPI 보정 · 축 = [첫 저장일, T])."""
    T = dates[-1]
    firsts = [rows[0][0] for rows in etfs.values() if rows and rows[0][0] <= T]
    first = min(firsts) if firsts else T
    years = range(int(first[:4]), int(T[:4]) + 1)
    return {
        "schema": "poc6_02_snapshot_v1",
        "T": T,
        "holdings": {
            "status": "V1",
            "rows": len(etfs),
            "tickers": len(etfs),
            "etf": len(etfs),
            "non_etf": 0,
        },
        "axis": {
            "label": prices.AXIS_LABEL,
            "dates": [d for d in dates if d >= first],
            "modes": {str(y): prices.MODE_KOSPI for y in years},
            "skipped_weekdays": [],
            "kospi_latest": dates[-1],
            "calendar_years": [],
            "problem": None,
        },
        "price_basis_label": prices.PRICE_BASIS_LABEL,
        "etfs": {t: {"name": f"ETF {t}", "rows": rows} for t, rows in etfs.items()},
    }


def _four() -> dict:
    return {t: _rows(_walk(seed)) for seed, t in enumerate(TICKERS, start=3)}


@pytest.fixture(scope="module")
def cpu_four():
    return S.run_cpu(_snap(_four()))


# ── 06 재사용 · 목표 ─────────────────────────────────────────────────────────────


def test_target_known_paths_and_public_median():
    dates = DATES[:100]
    rising = _snap({"A": _rows([100.0 + k for k in range(100)], dates)}, dates)
    assert S.target(S.prepare(rising), "A", 70) == 0.0  # 완전 상승 = 0
    flat = [100.0] * 100
    flat[75] = 90.0
    assert S.target(
        S.prepare(_snap({"A": _rows(flat, dates)}, dates)), "A", 70
    ) == pytest.approx(-0.10)
    assert m06.median is m06._median
    assert m06.median([3.0, 1.0, 2.0, 4.0]) == 2.5


def test_single_etf_reproduces_06_ridge_and_median(monkeypatch):
    """적격 1종이면 ETF 별 MEDIAN · RIDGE 구간 MAE 가 06 evaluate 와 같다(같은 축 · 같은 규칙)."""
    rows = _rows(_walk(7))
    monkeypatch.setattr(S, "MIN_ETFS", 1)
    cpu = S.run_cpu(_snap({"A": rows}))
    ref = m06.evaluate(
        prices.AxisSeries(DATES, [prices.PriceRow(*r) for r in rows]), DATES[-1]
    )
    for b in range(3):
        assert cpu["scores"][S.RIDGE]["blocks"][b] == pytest.approx(
            ref["blocks"][b]["mae_model_pp"], abs=1e-9
        )
        assert cpu["scores"][S.MEDIAN]["blocks"][b] == pytest.approx(
            ref["blocks"][b]["mae_baseline_pp"], abs=1e-9
        )


# ── 적격 · 경계 · 자료 부족 · 확인 필요 ──────────────────────────────────────────


def _fdr_with_break(closes, at: int) -> list[list]:
    rows = _rows(closes, source=FDR)
    rows[at][4] = rows[at][4] + 0.01  # change ≠ 종가 비율 = BASIS_BREAK(06)
    return rows


def test_eligibility_reasons_breaks_and_data_short():
    prep0 = S.prepare(_snap(_four()))
    b2 = prep0["blocks"][1]
    etfs = _four()
    etfs["SHORT"] = _rows(_walk(11)[-300:], DATES[-300:])
    etfs["BRK"] = _fdr_with_break(_walk(12), b2[20])
    prep = S.prepare(_snap(etfs))
    assert prep["eligible"] == list(TICKERS) and prep["status"] is None
    assert any("학습" in r for r in prep["etfs"]["SHORT"]["ineligible_reasons"])
    brk = prep["etfs"]["BRK"]
    assert any("2구간" in r and "시험 날짜" in r for r in brk["ineligible_reasons"])
    assert (
        brk["breaks"][0]["date"] == DATES[b2[20]]
        and brk["breaks"][0]["kind"] == prices.BASIS_BREAK
    )
    assert brk["excluded_by_reason"][prices.BASIS_BREAK] > 0
    three = {t: etfs[t] for t in TICKERS[:3]}
    out = S.run_cpu(_snap(three))
    assert out["status"] == S.DATA_SHORT and "scores" not in out


def test_axis_problem_is_check_required():
    snap = _snap(_four())
    snap["axis"]["kospi_latest"] = DATES[
        -2
    ]  # 파일 없는 해에 KOSPI 최신일 < T = 06 축 문제
    snap["axis"]["problem"] = prices.axis_problem(snap["T"], snap["axis"])
    assert snap["axis"]["problem"] and snapshot_problem(snap) is None
    with pytest.raises(S.StudyError, match="연구 축 확정 불가"):
        S.prepare(snap)
    snap["axis"]["problem"] = None  # 다시 판정한 값과 다른 저장값 = 손상
    with pytest.raises(S.StudyError, match="계약 위반"):
        S.prepare(snap)


def _weekend_between(dates: list[str]) -> tuple[int, str]:
    for k in range(1, len(dates)):
        a, b = date.fromisoformat(dates[k - 1]), date.fromisoformat(dates[k])
        if (b - a).days == 3:
            return k, (a + timedelta(days=1)).isoformat()  # 금 → 토
    raise AssertionError


def _swap(xs: list, k: int) -> None:
    xs[k], xs[k + 1] = xs[k + 1], xs[k]


_CORRUPT = {
    # 연구 축(검증자 r1 재현 3종 포함)
    "axis_invalid_date": lambda s: s["axis"]["dates"].__setitem__(100, "invalid-date"),
    "axis_duplicate": lambda s: s["axis"]["dates"].__setitem__(
        100, s["axis"]["dates"][99]
    ),
    "axis_reversed": lambda s: _swap(s["axis"]["dates"], 100),
    "axis_basic_format": lambda s: s["axis"]["dates"].__setitem__(
        100, s["axis"]["dates"][100].replace("-", "")
    ),
    "axis_weekend": lambda s: s["axis"]["dates"].__setitem__(
        *_weekend_between(s["axis"]["dates"])
    ),
    "axis_after_T": lambda s: s["axis"]["dates"].append("2099-01-02"),
    "axis_modes_missing_year": lambda s: s["axis"]["modes"].pop(DATES[0][:4]),
    "axis_modes_wrong": lambda s: s["axis"]["modes"].__setitem__(
        DATES[0][:4], prices.MODE_FILE
    ),
    "axis_skipped_in_axis": lambda s: s["axis"]["skipped_weekdays"].append(
        s["axis"]["dates"][5]
    ),
    "axis_calendar_years_text": lambda s: s["axis"].__setitem__(
        "calendar_years", ["2024"]
    ),
    "axis_kospi_latest_bad": lambda s: s["axis"].__setitem__("kospi_latest", "어제"),
    "axis_problem_mismatch": lambda s: s["axis"].__setitem__("problem", "x"),
    "axis_label": lambda s: s["axis"].__setitem__("label", "다른 축"),
    "axis_extra_key": lambda s: s["axis"].__setitem__("x", 1),
    # 기준일 · 최상위
    "T_invalid": lambda s: s.__setitem__("T", "2025-02-30"),
    "top_extra_key": lambda s: s.__setitem__("extra", 1),
    "price_label": lambda s: s.__setitem__("price_basis_label", "수정주가"),
    # ETF 저장 행
    "row_invalid_date": lambda s: s["etfs"]["A01"]["rows"][50].__setitem__(
        0, "2023-13-01"
    ),
    "row_duplicate": lambda s: s["etfs"]["A01"]["rows"].__setitem__(
        51, list(s["etfs"]["A01"]["rows"][50])
    ),
    "row_reversed": lambda s: _swap(s["etfs"]["A01"]["rows"], 50),
    "row_close_text": lambda s: s["etfs"]["A01"]["rows"][50].__setitem__(1, "abc"),
    "row_change_text": lambda s: s["etfs"]["A01"]["rows"][50].__setitem__(4, "x"),
    "row_change_nan": lambda s: s["etfs"]["A01"]["rows"][50].__setitem__(
        4, float("nan")
    ),
    "row_source_number": lambda s: s["etfs"]["A01"]["rows"][50].__setitem__(2, 5),
    "row_fetched_bad": lambda s: s["etfs"]["A01"]["rows"][50].__setitem__(3, "어제"),
    "name_number": lambda s: s["etfs"]["A01"].__setitem__("name", 7),
    "ticker_bar": lambda s: s["etfs"].__setitem__("A|9", s["etfs"].pop("A04")),
    # 보유 건수
    "holdings_etf_count": lambda s: s["holdings"].__setitem__("etf", 5),
    "holdings_bool": lambda s: s["holdings"].__setitem__("non_etf", True),
}


@pytest.mark.parametrize("kind", sorted(_CORRUPT))
def test_corrupt_snapshot_is_rejected_at_every_layer(tmp_path, kind):
    good = _snap(_four())
    assert snapshot_problem(good) is None
    bad = json.loads(json.dumps(good))
    _CORRUPT[kind](bad)
    assert snapshot_problem(bad), kind  # 검사 함수
    with pytest.raises(S.StudyError, match="계약 위반"):
        S.prepare(bad)  # 계산 시작 층(어느 경로로 오든)
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(SnapshotError):
        load_snapshot(p)  # 파일 읽기 층


def test_recipe_keeps_original_five_and_change_reason():
    e = S.RECIPE["eligibility"]
    assert (e["min_etfs"], e["min_etfs_original"]) == (4, 5) and "Q1 (b)" in e[
        "min_etfs_change"
    ]
    assert e["min_train_per_block"] == 252 and e["min_test_dates_per_block"] == 42


# ── 시간 분리 · 결정성 ────────────────────────────────────────────────────────


def test_labels_end_before_block_start_and_future_prices_do_not_leak(cpu_four):
    assert all(b["label_before_start"] for b in cpu_four["blocks"])
    prep = cpu_four["prep"]
    s2 = prep["blocks"][1][0]
    anchor = len(DATES) - 1 - S.H
    for cut, blocks in ((s2, [0]), (anchor + 1, [0, 1, 2])):
        mod = {
            t: [
                r if k < cut else [r[0], r[1] * 1.5, *r[2:]] for k, r in enumerate(rows)
            ]
            for t, rows in _four().items()
        }
        other = S.run_cpu(_snap(mod))
        for b in blocks:
            assert [r["preds"] for r in other["rows_by_block"][b]] == [
                r["preds"] for r in cpu_four["rows_by_block"][b]
            ]
    # 정답은 미래 가격으로 바뀐다(예측만 같다)
    assert [r["truth"] for r in other["rows_by_block"][2]] != [
        r["truth"] for r in cpu_four["rows_by_block"][2]
    ]


def test_same_input_is_deterministic(cpu_four):
    again = S.run_cpu(_snap(_four()))
    assert (
        again["rows_by_block"] == cpu_four["rows_by_block"]
        and again["scores"] == cpu_four["scores"]
    )
    assert cpu_four["repro_cpu_identical"] is True
    assert cpu_four["candidates"][S.GPU_MLP]["verdict"] == S.GPU_NOT_RUN


def test_pooled_weights_sum_to_one_per_date(cpu_four):
    bs = S.block_sets(cpu_four["prep"], 0)
    per = {}
    for (_, i), w in zip(bs["pooled"], bs["weights"]):
        per[i] = per.get(i, 0.0) + w
    assert all(abs(v - 1.0) < 1e-12 for v in per.values())


# ── 평가 · 판정 ───────────────────────────────────────────────────────────────


def test_date_balanced_mae_weights_dates_not_rows():
    rows = [
        {"date": "d1", "ticker": "A", "truth": 0.0, "preds": {"M": -0.01}},
        {"date": "d1", "ticker": "B", "truth": 0.0, "preds": {"M": -0.03}},
        {"date": "d2", "ticker": "A", "truth": 0.0, "preds": {"M": -0.06}},
    ]
    r = S.date_balanced_mae(rows, "M")
    assert r["mae_pp"] == pytest.approx(4.0) and (r["dates"], r["rows"]) == (2, 3)


BASE = {
    "overall": 20.0,
    "blocks": [1.0, 1.0, 1.0],
}  # 20 → 19 = 정확히 5%(부동소수 오차 없음)


@pytest.mark.parametrize(
    "overall, blocks, ok, failed",
    [
        (
            1.9,
            [0.9, 0.9, 1.0],
            True,
            None,
        ),  # 정확히 5% 개선 · 2구간 승 · 같은 값은 승 아님
        (19.0001, [0.9, 0.9, 1.0], False, "overall_improve"),
        (19.0, [0.9, 1.0, 1.0], False, "block_wins"),  # 같은 값 = 이긴 구간 아님
        (19.0, [0.9, 0.9, 1.05], True, None),  # 정확히 5% 악화 = 허용
        (19.0, [0.9, 0.9, 1.0500001], False, "no_block_worse_5pct"),
    ],
)
def test_three_condition_boundaries(overall, blocks, ok, failed):
    j = S.judge({"overall": overall, "blocks": blocks}, BASE)
    assert j["pass"] is ok
    if failed:
        assert j["conditions"][failed] is False


def test_base_zero_is_reject_and_both_baselines_required():
    j = S.judge(
        {"overall": 0.0, "blocks": [0.0] * 3}, {"overall": 0.0, "blocks": [0.0] * 3}
    )
    assert j["pass"] is False and j["base_zero"]
    scores = {
        S.MEDIAN: {"overall": 2.0, "blocks": [1.0] * 3},
        S.RIDGE: {"overall": 1.0, "blocks": [0.5] * 3},
        S.HGB: {"overall": 1.5, "blocks": [0.7] * 3},
    }
    assert (
        S.verdict_for(scores, S.HGB)["verdict"] == S.REJECT
    )  # MEDIAN 은 이겼지만 RIDGE 는 못 이김


def test_near_boundary_is_flagged_not_changed():
    j = S.judge({"overall": 19.0, "blocks": [0.9, 0.9, 1.0]}, BASE)
    assert j["relative_improvement"] == 0.05
    assert "전체 개선 5% 경계" in j["near_boundary"] and j["pass"] is True


# ── snapshot(tmp DB · tmp 보유) ────────────────────────────────────────────────


def _market_db(path: Path, *, with_master=True, with_kospi=True) -> None:
    con = sqlite3.connect(path)
    if with_master:
        con.execute(ETF_MASTER_DDL)
    con.execute(ETF_DAILY_PRICE_DDL)
    con.execute(MARKET_BENCHMARK_DAILY_PRICE_DDL)
    for seed, t in enumerate(TICKERS, start=3):
        if with_master:
            con.execute(
                "INSERT INTO etf_master (ticker, name, source, last_seen_at)"
                " VALUES (?, ?, 'FDR', 'x')",
                (t, f"ETF {t}"),
            )
        for d, c, src, f, ch in _rows(_walk(seed)):
            con.execute(
                "INSERT INTO etf_daily_price (ticker, date, close, change, source, fetched_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (t, d, c, ch, src, f),
            )
    if with_kospi:
        con.executemany(
            "INSERT INTO market_benchmark_daily_price"
            " VALUES ('KOSPI', 'KOSPI', ?, ?, 'NAVER_FDR', 'x')",
            [(d, 2500.0 + k) for k, d in enumerate(DATES)],
        )
    con.commit()
    con.close()


def _holdings(qty: int = 10) -> None:
    f = holdings_module.HOLDINGS_FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "ticker": t,
            "quantity": qty,
            "avg_buy_price": 12345,
            "name": t,
            "account_group": "ISA비밀계좌",
        }
        for t in TICKERS
    ]
    rows.append(
        {
            "ticker": TICKERS[0],
            "quantity": 1,
            "avg_buy_price": 1,
            "name": "x",
            "account_group": "연금",
        }
    )
    rows.append(
        {
            "ticker": "005930",
            "quantity": 3,
            "avg_buy_price": 70000,
            "name": "삼성전자",
            "account_group": "일반",
        }
    )
    f.write_text(json.dumps({"holdings": rows}, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def market(tmp_path, monkeypatch):
    db = tmp_path / "market.sqlite"
    _market_db(db)
    caldir = tmp_path / "cal"
    caldir.mkdir()
    monkeypatch.setattr(market_data_store, "DEFAULT_DB_PATH", db)
    monkeypatch.setattr(cal, "CALENDAR_DIR", caldir)
    monkeypatch.setattr(R, "RESEARCH_ROOT", tmp_path / "research" / "poc6_02")
    _holdings()
    return db


def test_snapshot_reads_tickers_only_and_ignores_personal_values(market):
    snap = build_snapshot()
    text = json.dumps(snap, ensure_ascii=False)
    assert snap["holdings"] == {
        "status": "OK",
        "rows": 6,
        "tickers": 5,
        "etf": 4,
        "non_etf": 1,
    }  # V1 보유 문서도 화면 GET /holdings 와 같은 현재 보유로 읽는다
    assert snap["T"] == DATES[-1] and snap["axis"]["problem"] is None
    for secret in (
        "ISA비밀계좌",
        "삼성전자",
        "quantity",
        "avg_buy_price",
        "account_group",
    ):
        assert secret not in text
    assert sorted(snap["etfs"]) == list(TICKERS)  # 개별주 ticker 는 건수만
    before = digest(snap)
    _holdings(qty=999)  # 수량 · 평단이 바뀌어도 입력은 같다
    con = sqlite3.connect(market)
    con.execute(
        "CREATE TABLE market_macro_daily (series_id TEXT, obs_date TEXT, value REAL)"
    )
    con.execute("INSERT INTO market_macro_daily VALUES ('X', '2024-01-02', 1.0)")
    con.commit()
    con.close()
    assert digest(build_snapshot()) == before  # 거시 자료 · 평가와 무관


def test_no_holdings_file_is_check_required_but_no_etf_is_data_short(market):
    holdings_module.HOLDINGS_FILE.unlink()
    with pytest.raises(SnapshotError, match="보유 파일 없음"):
        build_snapshot()  # 경로 문제를 빈 모집단(자료 부족)으로 넘기지 않음
    _holdings()
    doc = json.loads(holdings_module.HOLDINGS_FILE.read_text(encoding="utf-8"))
    doc["holdings"] = [h for h in doc["holdings"] if h["ticker"] == "005930"]
    holdings_module.HOLDINGS_FILE.write_text(json.dumps(doc), encoding="utf-8")
    snap = build_snapshot()  # 보유 파일은 있는데 ETF 가 없음 = 정상 자료 부족
    assert snap["holdings"]["etf"] == 0 and snap["etfs"] == {}
    assert S.run_cpu(snap)["status"] == S.DATA_SHORT


@pytest.mark.parametrize("problem", ["no_db", "no_master", "no_kospi", "no_prices"])
def test_snapshot_input_problems_are_check_required(tmp_path, monkeypatch, problem):
    db = tmp_path / "m.sqlite"
    if problem != "no_db":
        _market_db(
            db, with_master=problem != "no_master", with_kospi=problem != "no_kospi"
        )
    if problem == "no_prices":
        con = sqlite3.connect(db)
        con.execute("DROP TABLE etf_daily_price")
        con.commit()
        con.close()
    monkeypatch.setattr(market_data_store, "DEFAULT_DB_PATH", db)
    _holdings()
    with pytest.raises(SnapshotError):
        build_snapshot()


# ── 결과 폴더 · CLI ──────────────────────────────────────────────────────────


def test_run_writes_folder_bundle_without_truth_and_no_network(market, monkeypatch):
    def _no_net(*a, **k):
        raise AssertionError("외부 연결 시도")

    monkeypatch.setattr(socket.socket, "connect", _no_net)
    folder = runner.run()
    names = sorted(p.name for p in folder.iterdir())
    assert names == [
        "gpu_bundle",
        "gpu_bundle.zip",
        "input_snapshot.json",
        "report.json",
        "report.md",
    ]
    rep = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    assert (
        rep["status"] == S.COMPLETED
        and rep["candidates"][S.GPU_MLP]["verdict"] == S.GPU_NOT_RUN
    )
    assert rep["candidates"][S.HGB]["verdict"] in (S.PROMISING, S.REJECT)
    gin = json.loads(
        (folder / "gpu_bundle" / "gpu_input.json").read_text(encoding="utf-8")
    )
    for blk in gin["blocks"]:  # 시험 정답 칸 없음(칸 목록 그대로)
        assert sorted(blk) == sorted(
            (
                "block",
                "train_X",
                "train_y",
                "train_w",
                "mean",
                "std",
                "test_ids",
                "test_X",
            )
        )
    leaked = "test_y" in json.dumps(gin) or "truth" in json.dumps(gin)
    assert not leaked  # 큰 문자열 비교 설명을 만들지 않게 참/거짓만 확인
    assert (folder / "gpu_bundle" / "mlp.py").read_bytes() == (
        REPO / "app/d20_pooled/mlp.py"
    ).read_bytes()
    assert gin["mlp_spec"] == json.loads(json.dumps(mlp.SPEC))
    assert gin["code_sha256"] == {
        n: hashlib.sha256((REPO / "app/d20_pooled" / n).read_bytes()).hexdigest()
        for n in ("mlp.py", "gpu_runner.py")
    }
    assert rep["completion"] == "CPU_PARTIAL_GPU_PENDING"  # GPU 전에는 부분 완료
    resolved = rep["recipe_resolved"]["hgb_get_params"]
    assert {k: resolved[k] for k in S.HGB_PARAMS} == S.HGB_PARAMS
    assert "validation_fraction" in resolved  # 나머지 기본값도 남김
    assert "보유 ETF 4종" in " ".join(rep["limits"])  # 고정 숫자 아님(이번 snapshot)
    for b, blk in enumerate(rep["blocks"]):
        assert (
            sum(
                int(k) * v
                for k, v in blk["etfs_per_date"]["dates_by_etf_count"].items()
            )
            == blk["test_rows"]
        )
        for t in TICKERS:
            pb = rep["eligibility"]["etfs"][t]["blocks"][b]
            assert (
                pb["train_label_end"] < blk["first_date"]
            )  # ETF × 구간 정답 끝 < 시작
            assert set(pb["train_excluded_by_reason"]) <= {
                S.LOOKBACK_SHORT,
                *prices.REASON_TEXT,
            }
    md = (folder / "report.md").read_text(encoding="utf-8")
    assert "## 판정" in md and "적격 ETF × 구간" in md and "ETF별 MAE" in md
    assert "1구간 학습 · 예측 초" in md
    bat = (folder / "gpu_bundle" / "run_gpu.bat").read_text(encoding="utf-8")
    assert bat.count("gpu_runner.py") == 1  # 인터프리터 하나 · 실행 한 번


def test_output_failure_is_failure_without_partial(tmp_path, monkeypatch, cpu_four):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setattr(R, "RESEARCH_ROOT", blocker / "poc6_02")
    rep = {"study_id": "x", "stage": "CPU"}
    with pytest.raises(R.ArtifactSaveError):
        R.write_run(rep, {}, None)
    assert blocker.is_file() and not list(tmp_path.rglob("*.partial"))


def test_cli_check_required_and_data_short(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "RESEARCH_ROOT", tmp_path / "research")
    bad = _snap(_four())
    bad["axis"]["problem"] = "축 문제"
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    from scripts.run_d20_pooled_research import main

    assert main(["run", "--snapshot", str(p)]) == 2
    assert not (tmp_path / "research").exists()
    short = _snap({t: _rows(_walk(s)) for s, t in enumerate(TICKERS[:3], start=3)})
    p.write_text(json.dumps(short), encoding="utf-8")
    assert main(["run", "--snapshot", str(p)]) == 0
    (folder,) = (tmp_path / "research").iterdir()
    rep = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    assert rep["status"] == S.DATA_SHORT and not (folder / "gpu_bundle").exists()


# ── MLP · RTX 실행기 ─────────────────────────────────────────────────────────


def test_standardize_weighted_population_and_constant_column():
    mean, std = mlp.standardize_params([[1.0, 5.0], [3.0, 5.0]], [1.0, 3.0])
    assert mean == pytest.approx([2.5, 5.0]) and std == pytest.approx(
        [math.sqrt(0.75), 0.0]
    )
    assert mlp.apply_standardize([[3.0, 5.0]], mean, std)[0][1] == 0.0


def _tiny(n=50, seed=1):
    rnd = random.Random(seed)
    X = [[rnd.gauss(0, 1) for _ in range(5)] for _ in range(n)]
    y = [-abs(rnd.gauss(0, 0.05)) for _ in range(n)]
    w = [1.0 / (1 + k % 3) for k in range(n)]
    mean, std = mlp.standardize_params(X, w)
    return X, y, w, mean, std


def test_mlp_accumulation_equals_full_batch_and_seed_repro():
    torch = pytest.importorskip("torch")
    X, y, w, mean, std = _tiny()
    before = torch.are_deterministic_algorithms_enabled()
    full = mlp.train_predict(X, y, w, X[:10], mean, std, epochs=5)
    chunk = mlp.train_predict(X, y, w, X[:10], mean, std, epochs=5, microbatch=7)
    assert max(abs(a - b) for a, b in zip(full, chunk)) <= mlp.REPRO_TOL
    assert mlp.train_predict(X, y, w, X[:10], mean, std, epochs=5) == full
    assert (
        torch.are_deterministic_algorithms_enabled() == before
    )  # 전역 설정을 남기지 않음


def test_mlp_uses_date_balanced_weights():
    pytest.importorskip("torch")
    X, y, w, mean, std = _tiny()
    weighted = mlp.train_predict(X, y, w, X[:10], mean, std, epochs=5)
    uniform = mlp.train_predict(X, y, [1.0] * len(w), X[:10], mean, std, epochs=5)
    assert weighted != uniform


def test_runner_on_cpu_only_torch_is_gpu_not_run(market, tmp_path):
    torch = pytest.importorskip("torch")
    if torch.cuda.is_available():
        pytest.skip("CUDA 장비에서는 실제 GPU 경로")
    _, dst = _bundle_copy(market, tmp_path)
    p = _run_bundle(dst)
    res = json.loads((dst / "gpu_result.json").read_text(encoding="utf-8"))
    assert (
        p.returncode == 0
        and res["status"] == "GPU_NOT_RUN"
        and "CUDA 사용 불가" in res["reason"]
    )
    assert "blocks" not in res  # CPU 로 바꿔 학습하지 않음


def test_merge_clips_and_rejects_bad_predictions():
    rows = [
        [{"id": "A|d1", "ticker": "A", "date": "d1", "truth": -0.1, "preds": {}}]
        for _ in range(1)
    ]
    out = S.merge_gpu(rows, [{"block": 1, "test_ids": ["A|d1"], "pred": [0.3]}])
    assert out[0][0]["preds"][S.GPU_MLP] == 0.0
    assert (
        S.merge_gpu(rows, [{"block": 1, "test_ids": ["A|d1"], "pred": [-1.5]}])[0][0][
            "preds"
        ][S.GPU_MLP]
        == -1.0
    )
    for bad in (
        {"block": 1, "test_ids": ["A|d2"], "pred": [0.0]},
        {"block": 1, "test_ids": ["A|d1", "A|d1"], "pred": [0.0, 0.0]},
        {"block": 1, "test_ids": ["A|d1"], "pred": [float("nan")]},
        {"block": 1, "test_ids": ["A|d1"], "pred": []},
    ):
        with pytest.raises(ValueError):
            S.merge_gpu(rows, [bad])


def _bundle_copy(market, tmp_path) -> tuple[Path, Path]:
    folder = runner.run()
    dst = tmp_path / "pc"
    shutil.copytree(folder / "gpu_bundle", dst)
    return folder, dst


def _run_bundle(dst: Path, prefix: str = "") -> subprocess.CompletedProcess:
    code = prefix + "import runpy; runpy.run_path('gpu_runner.py', run_name='__main__')"
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=dst,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_runner_without_cuda_or_torch_is_gpu_not_run_and_tamper_is_check_required(
    market, tmp_path
):
    folder, dst = _bundle_copy(market, tmp_path)
    p = _run_bundle(dst, "import sys; sys.modules['torch'] = None; ")
    res = json.loads((dst / "gpu_result.json").read_text(encoding="utf-8"))
    assert (
        p.returncode == 0
        and res["status"] == "GPU_NOT_RUN"
        and "torch 없음" in res["reason"]
    )
    assert res["study_id"] == folder.name
    gin = json.loads((dst / "gpu_input.json").read_text(encoding="utf-8"))
    gin["blocks"][0]["train_y"][0] += 0.001
    (dst / "gpu_input.json").write_text(json.dumps(gin), encoding="utf-8")
    p = _run_bundle(dst)
    res = json.loads((dst / "gpu_result.json").read_text(encoding="utf-8"))
    assert (
        p.returncode == 1
        and res["status"] == "CHECK_REQUIRED"
        and "digest" in res["reason"]
    )


def _main_in_process(dst: Path, monkeypatch, torch) -> tuple[int, dict]:
    """실행기 main 전체 경로를 CPU 로(시험 전용 · CUDA 있음으로 두고 장치만 cpu)."""
    monkeypatch.setattr(gpu_runner, "HERE", str(dst))
    monkeypatch.setattr(gpu_runner, "DEVICE", "cpu")
    monkeypatch.setattr(gpu_runner, "environment", lambda torch=None: {"t": 1})
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    monkeypatch.setitem(sys.modules, "mlp", mlp)
    monkeypatch.setattr(mlp, "EPOCHS", 3)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "max_memory_allocated", lambda *a, **k: 0)
    rc = gpu_runner.main()
    return rc, json.loads((dst / "gpu_result.json").read_text(encoding="utf-8"))


def test_pc_runner_main_paths_ok_input_code_nan_oom(market, tmp_path, monkeypatch):
    torch = pytest.importorskip("torch")
    folder = runner.run()

    def fresh(name: str) -> Path:
        dst = tmp_path / name
        shutil.copytree(folder / "gpu_bundle", dst)
        return dst

    rc, res = _main_in_process(fresh("ok"), monkeypatch, torch)
    assert rc == 0 and res["status"] == "OK" and len(res["blocks"]) == 3
    assert (
        res["code_sha256"]
        == json.loads(
            (folder / "gpu_bundle" / "gpu_input.json").read_text(encoding="utf-8")
        )["code_sha256"]
    )

    dst = fresh("no_input")
    (dst / "gpu_input.json").unlink()
    rc, res = _main_in_process(dst, monkeypatch, torch)
    assert (
        rc == 1
        and res["status"] == "CHECK_REQUIRED"
        and "읽을 수 없음" in res["reason"]
    )

    dst = fresh("code")
    with open(dst / "mlp.py", "a", encoding="utf-8") as f:
        f.write("\n# changed\n")
    rc, res = _main_in_process(dst, monkeypatch, torch)
    assert rc == 1 and res["status"] == "CHECK_REQUIRED" and "코드" in res["reason"]

    with monkeypatch.context() as m:
        m.setattr(mlp, "train_predict", lambda *a, **k: [float("nan")] * len(a[3]))
        rc, res = _main_in_process(fresh("nan"), monkeypatch, torch)
    assert (
        rc == 1 and res["status"] == "RUN_FAILED" and "유한하지 않은" in res["reason"]
    )

    def _oom(*a, **k):
        raise torch.cuda.OutOfMemoryError("x")

    with monkeypatch.context() as m:
        m.setattr(gpu_runner, "epoch_seconds", _oom)
        rc, res = _main_in_process(fresh("oom"), monkeypatch, torch)
    assert rc == 1 and res["status"] == "RUN_FAILED" and "메모리 부족" in res["reason"]
    assert "blocks" not in res  # 크기를 몰래 낮춰 학습하지 않음


@pytest.mark.parametrize(
    "kind", ["broken", "schema", "no_axis", "bad_row", "axis_invalid_date"]
)
def test_cli_bad_snapshot_file_is_check_required(tmp_path, monkeypatch, kind):
    monkeypatch.setattr(R, "RESEARCH_ROOT", tmp_path / "research")
    snap = _snap(_four())
    if kind == "schema":
        snap["schema"] = "x"
    elif kind == "no_axis":
        del snap["axis"]
    elif kind == "bad_row":
        snap["etfs"]["A01"]["rows"][3] = [1, 2]
    elif kind == "axis_invalid_date":  # 검증자 r1 재현과 같은 손상
        _CORRUPT[kind](snap)
    p = tmp_path / "snap.json"
    p.write_text("{broken" if kind == "broken" else json.dumps(snap), encoding="utf-8")
    from scripts.run_d20_pooled_research import main

    assert (
        main(["run", "--snapshot", str(p)]) == 2
    )  # 입력 문제 = 확인 필요(계산 오류 아님)
    assert not (tmp_path / "research").exists()


def test_merge_write_failure_leaves_no_folder(market, tmp_path, monkeypatch):
    folder = runner.run()
    p = tmp_path / "gpu_result.json"
    p.write_text(json.dumps(_ok_result(folder, monkeypatch)), encoding="utf-8")

    def _fail(*a, **k):
        raise OSError("disk")

    monkeypatch.setattr(R, "render_md", _fail)
    with pytest.raises(R.ArtifactSaveError):
        runner.merge(folder, p)
    assert not (folder / "gpu_merged").exists()
    assert not list(folder.rglob("*.partial"))


def _ok_result(folder: Path, monkeypatch) -> dict:
    """실행기의 공식 학습 경로를 CPU 로 돌린 결과(시험 전용 · 장치만 다름)."""
    torch = pytest.importorskip("torch")
    gin = json.loads(
        (folder / "gpu_bundle" / "gpu_input.json").read_text(encoding="utf-8")
    )
    monkeypatch.setattr(gpu_runner, "DEVICE", "cpu")
    monkeypatch.setattr(mlp, "EPOCHS", 3)
    blocks = [{**b} for b in gin["blocks"]]
    res = gpu_runner.probe(torch, mlp, blocks[0])
    off = gpu_runner.official(torch, mlp, blocks, res["chosen_microbatch"])
    assert off["repeat_max_abs_diff"] <= mlp.REPRO_TOL
    return {
        "schema": "poc6_02_gpu_result_v1",
        "study_id": gin["study_id"],
        "input_digest": gin["input_digest"],
        "recipe_digest": gin["recipe_digest"],
        "bundle_digest": gin["bundle_digest"],
        "code_sha256": dict(gin["code_sha256"]),
        "status": "OK",
        "reason": None,
        "env": {"device": "test-cpu"},
        "resources": res,
        "blocks": off["blocks"],
        "repeat_max_abs_diff": off["repeat_max_abs_diff"],
    }


def test_merge_accepts_exact_match_and_keeps_cpu_scores(market, tmp_path, monkeypatch):
    folder = runner.run()
    res = _ok_result(folder, monkeypatch)
    p = tmp_path / "gpu_result.json"
    p.write_text(json.dumps(res), encoding="utf-8")
    out = runner.merge(folder, p)
    merged = json.loads(out.read_text(encoding="utf-8"))
    cpu_rep = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    assert merged["stage"] == "MERGED" and set(merged["scores"]) == {
        S.MEDIAN,
        S.RIDGE,
        S.HGB,
        S.GPU_MLP,
    }
    for m in S.CPU_METHODS:
        assert merged["scores"][m] == cpu_rep["scores"][m]
    assert merged["candidates"][S.GPU_MLP]["verdict"] in (S.PROMISING, S.REJECT)
    assert merged["completion"] == "FULL"
    assert out == folder / "gpu_merged" / "report_with_gpu.json"
    assert (folder / "gpu_merged" / "report_with_gpu.md").exists()
    with pytest.raises(R.ArtifactSaveError, match="이미 GPU 취합"):
        runner.merge(folder, p)  # 덮어쓰지 않음(명시 거절)
    assert json.loads((folder / "report.json").read_text(encoding="utf-8")) == cpu_rep


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.update(study_id="other"),
        lambda r: r.update(input_digest="0" * 64),
        lambda r: r.update(bundle_digest="0" * 64),
        lambda r: r["blocks"][0]["test_ids"].pop(),
        lambda r: r["blocks"][1]["test_ids"].__setitem__(
            1, r["blocks"][1]["test_ids"][0]
        ),
        lambda r: r.update(schema="x"),
        lambda r: r.update(status="WEIRD"),
        lambda r: r.update(status=None),
        lambda r: r["code_sha256"].update({"mlp.py": "0" * 64}),
        lambda r: r.update(repeat_max_abs_diff=1e-3),  # OK 인데 재현 실패
        lambda r: r.pop("repeat_max_abs_diff"),
        lambda r: r.update(env=[1]),
        lambda r: r.update(reason=5),
    ],
)
def test_merge_rejects_other_or_damaged_results(market, tmp_path, monkeypatch, mutate):
    folder = runner.run()
    res = _ok_result(folder, monkeypatch)
    mutate(res)
    p = tmp_path / "gpu_result.json"
    p.write_text(json.dumps(res), encoding="utf-8")
    with pytest.raises(runner.MergeError):
        runner.merge(folder, p)
    assert not (folder / "gpu_merged").exists()
    assert not (folder / "gpu_attempts").exists()


def _edit_json(path: Path, fn) -> None:
    body = json.loads(path.read_text(encoding="utf-8"))
    fn(body)
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")


def _nudge(box: dict, key: str) -> None:
    """[-1, 0] 안에서 값을 조금 바꾼다(형식은 맞고 내용만 다름)."""
    v = box[key]
    box[key] = v + 0.001 if v < -0.001 else v - 0.001


_FOLDER_TAMPER = {
    "truth": lambda f: _edit_json(
        f / "report.json", lambda r: _nudge(r["rows_by_block"][0][0], "truth")
    ),
    "cpu_pred": lambda f: _edit_json(
        f / "report.json",
        lambda r: _nudge(r["rows_by_block"][1][3]["preds"], S.HGB),
    ),
    "truth_text": lambda f: _edit_json(
        f / "report.json", lambda r: r["rows_by_block"][0][0].__setitem__("truth", "x")
    ),
    # 검증자 r2 재현 — 행 ID 는 그대로 두고 종목코드 한 칸만 다른 ETF 로
    "ticker": lambda f: _edit_json(
        f / "report.json",
        lambda r: r["rows_by_block"][0][0].__setitem__(
            "ticker",
            (
                TICKERS[1]
                if r["rows_by_block"][0][0]["ticker"] != TICKERS[1]
                else TICKERS[2]
            ),
        ),
    ),
    "date": lambda f: _edit_json(
        f / "report.json",
        lambda r: r["rows_by_block"][0][0].__setitem__(
            "date", r["rows_by_block"][0][-1]["date"]
        ),  # 같은 구간의 다른 날짜(첫 행과 다름)
    ),
    "eligibility": lambda f: _edit_json(
        f / "report.json",
        lambda r: r["eligibility"]["etfs"][TICKERS[0]].__setitem__(
            "valid_n", r["eligibility"]["etfs"][TICKERS[0]]["valid_n"] + 1
        ),
    ),
    "blocks_info": lambda f: _edit_json(
        f / "report.json",
        lambda r: r["blocks"][1].__setitem__(
            "train_rows_pooled", r["blocks"][1]["train_rows_pooled"] + 1
        ),
    ),
    "diagnostics": lambda f: _edit_json(
        f / "report.json",
        lambda r: r["diagnostics"]["per_etf"][TICKERS[0]].__setitem__("rows", 188),
    ),
    "price_breaks": lambda f: _edit_json(
        f / "report.json", lambda r: r["price_breaks"].append({"date": "2024-01-02"})
    ),
    "limits": lambda f: _edit_json(f / "report.json", lambda r: r["limits"].pop()),
    "holdings": lambda f: _edit_json(
        f / "report.json",
        lambda r: r["holdings"].__setitem__("rows", r["holdings"]["rows"] + 1),
    ),
    "row_id": lambda f: _edit_json(
        f / "report.json",
        lambda r: r["rows_by_block"][2][0].__setitem__("id", "A01|2000-01-03"),
    ),
    "scores": lambda f: _edit_json(
        f / "report.json",
        lambda r: r["scores"][S.MEDIAN].__setitem__(
            "overall", r["scores"][S.MEDIAN]["overall"] + 0.1
        ),
    ),
    "verdict": lambda f: _edit_json(
        f / "report.json",
        lambda r: r["candidates"][S.HGB].__setitem__(
            "verdict",
            (
                S.REJECT
                if r["candidates"][S.HGB]["verdict"] == S.PROMISING
                else S.PROMISING
            ),
        ),  # 실제로 뒤집는다
    ),
    "recipe": lambda f: _edit_json(
        f / "report.json", lambda r: r["recipe"].__setitem__("clip", [-2.0, 0.0])
    ),
    "snapshot": lambda f: _edit_json(
        f / "input_snapshot.json",
        lambda s_: s_["etfs"]["A01"]["rows"][9].__setitem__(1, 1.0),
    ),
    "snapshot_corrupt": lambda f: _edit_json(
        f / "input_snapshot.json",
        lambda s_: s_["axis"]["dates"].__setitem__(100, "invalid-date"),
    ),
    "bundle_body": lambda f: _edit_json(
        f / "gpu_bundle" / "gpu_input.json",
        lambda g: g["blocks"][0]["train_y"].__setitem__(
            0, g["blocks"][0]["train_y"][0] + 0.001
        ),
    ),
}


@pytest.mark.parametrize("kind", sorted(_FOLDER_TAMPER))
def test_merge_rejects_damaged_cpu_folder(market, tmp_path, kind):
    """취합은 디스크에서 다시 읽는 CPU 폴더(보고서 · 입력 · 묶음)의 자기 일치를 확인한다."""
    folder = runner.run()
    p = tmp_path / "r.json"
    p.write_text(json.dumps(_not_run_result(folder)), encoding="utf-8")
    _FOLDER_TAMPER[kind](folder)
    with pytest.raises(runner.MergeError):
        runner.merge(folder, p)
    assert not (folder / "gpu_merged").exists()
    assert not (folder / "gpu_attempts").exists()


def _not_run_result(folder: Path) -> dict:
    gin = json.loads(
        (folder / "gpu_bundle" / "gpu_input.json").read_text(encoding="utf-8")
    )
    res = {
        k: gin[k]
        for k in ("study_id", "input_digest", "recipe_digest", "bundle_digest")
    }
    res.update(schema="poc6_02_gpu_result_v1", status="GPU_NOT_RUN", reason="x")
    return res


def test_merge_rejects_regenerated_bundle_with_consistent_digest(market, tmp_path):
    """묶음 표본을 바꾸고 digest 까지 다시 맞춰도 잠긴 입력에서 다시 만든 표본과 달라 거절."""
    folder = runner.run()
    path = folder / "gpu_bundle" / "gpu_input.json"
    gin = json.loads(path.read_text(encoding="utf-8"))
    gin["blocks"][0]["train_y"][0] += 0.001
    body = {k: v for k, v in gin.items() if k != "bundle_digest"}
    gin["bundle_digest"] = prices.canonical_hash(body)
    path.write_text(json.dumps(gin), encoding="utf-8")
    p = tmp_path / "r.json"
    p.write_text(json.dumps(_not_run_result(folder)), encoding="utf-8")
    with pytest.raises(runner.MergeError, match="표본"):
        runner.merge(folder, p)


def test_merge_ignores_only_run_specific_values(market, tmp_path):
    """생성 시각 · 환경 · 자원 · 구간별 시간은 실행마다 다르다 — 그 값만 다르면 취합한다."""
    folder = runner.run()
    p = tmp_path / "r.json"
    p.write_text(json.dumps(_not_run_result(folder)), encoding="utf-8")

    def _volatile(r):
        r["environment"]["platform"] = "다른 기계"
        r["resources"]["wall_seconds"] = 999.0
        for b in r["blocks"]:
            b["seconds"] = {m: 9.9 for m in b["seconds"]}

    _edit_json(folder / "report.json", _volatile)
    merged = json.loads(runner.merge(folder, p).read_text(encoding="utf-8"))
    assert merged["completion"] == "PARTIAL_GPU_NOT_RUN"


@pytest.mark.parametrize("bad", ["date", "close"])
def test_db_values_outside_contract_are_check_required(market, bad):
    con = sqlite3.connect(market)
    if bad == "date":
        con.execute(
            "INSERT INTO etf_daily_price (ticker, date, close, change, source, fetched_at)"
            " VALUES ('A01', '2024-13-01', 1.0, 0.0, 'NAVER_FDR', '2026-10-05T00:00:00Z')"
        )
    else:
        con.execute(
            "UPDATE etf_daily_price SET close = 'abc' WHERE ticker = 'A01' AND date = ?",
            (DATES[50],),
        )
    con.commit()
    con.close()
    with pytest.raises(SnapshotError, match="시세 DB 값"):
        build_snapshot()  # DB 에서 온 값도 같은 계약


def test_merge_rejects_bundle_code_changed_on_mac(market, tmp_path, monkeypatch):
    folder = runner.run()
    res = _ok_result(folder, monkeypatch)
    p = tmp_path / "gpu_result.json"
    p.write_text(json.dumps(res), encoding="utf-8")
    with open(folder / "gpu_bundle" / "mlp.py", "a", encoding="utf-8") as f:
        f.write("\n# changed\n")
    with pytest.raises(runner.MergeError, match="코드"):
        runner.merge(folder, p)


def test_merge_gpu_not_run_is_partial_attempt_and_later_ok_still_merges(
    market, tmp_path, monkeypatch
):
    folder, dst = _bundle_copy(market, tmp_path)
    _run_bundle(dst, "import sys; sys.modules['torch'] = None; ")
    out = runner.merge(folder, dst / "gpu_result.json")
    merged = json.loads(out.read_text(encoding="utf-8"))
    assert merged["candidates"][S.GPU_MLP]["verdict"] == S.GPU_NOT_RUN
    assert merged["completion"] == "PARTIAL_GPU_NOT_RUN"  # 최상위에서 부분 완료가 보임
    assert "PARTIAL_GPU_NOT_RUN" in (out.parent / "report_with_gpu.md").read_text(
        encoding="utf-8"
    )
    assert set(merged["scores"]) == set(S.CPU_METHODS)
    assert out.parent.parent == folder / "gpu_attempts"
    assert not (folder / "gpu_merged").exists()
    p = tmp_path / "ok.json"
    p.write_text(json.dumps(_ok_result(folder, monkeypatch)), encoding="utf-8")
    ok = json.loads(runner.merge(folder, p).read_text(encoding="utf-8"))
    assert ok["completion"] == "FULL"  # 앞 시도 기록이 뒤의 OK 취합을 막지 않음


def test_merge_refuses_smoke_folder(market, tmp_path):
    folder = runner.run(smoke=True)
    gin = json.loads(
        (folder / "gpu_bundle" / "gpu_input.json").read_text(encoding="utf-8")
    )
    res = {
        k: gin[k]
        for k in ("study_id", "input_digest", "recipe_digest", "bundle_digest")
    }
    res.update(schema="poc6_02_gpu_result_v1", status="GPU_NOT_RUN", reason="x")
    p = tmp_path / "r.json"
    p.write_text(
        json.dumps(res), encoding="utf-8"
    )  # 다른 칸은 다 맞아도 smoke 에는 붙이지 않는다
    with pytest.raises(runner.MergeError):
        runner.merge(folder, p)
    rep = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    assert (
        rep["status"] == "SMOKE" and "scores" not in rep and "rows_by_block" not in rep
    )


def test_cli_entry_runs_from_snapshot(tmp_path):
    p = tmp_path / "snap.json"
    p.write_text(json.dumps(_snap(_four())), encoding="utf-8")
    code = (
        "import sys; sys.path.insert(0, %r); from pathlib import Path; "
        "from app.d20_pooled import report as R; R.RESEARCH_ROOT = Path(%r); "
        "from scripts.run_d20_pooled_research import main; "
        "sys.exit(main(['run', '--snapshot', %r]))"
    ) % (str(REPO), str(tmp_path / "out"), str(p))
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert "산출 폴더" in proc.stdout and "POOLED_GPU_MLP: GPU_NOT_RUN" in proc.stdout
    assert (
        "완료 범위: CPU_PARTIAL_GPU_PENDING" in proc.stdout
    )  # GPU 전 부분 완료가 화면에도 보임
