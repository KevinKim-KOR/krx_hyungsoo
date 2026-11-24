"""POC7-03 두 기준 · 자리 판정 · 평가 · 판정 · 잠금 → 실행 → 독립 재계산 — tmp 가짜 자료만(라이브 · 봉인 DB 안 엶)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from app.candidate_compare import flow as FW
from app.candidate_compare import population as PO
from app.candidate_compare import recompute_weeks as RW
from app.candidate_compare import rules as RU
from app.candidate_compare import study as ST
from app.candidate_compare import verify as VF
from app.candidate_compare.protocol import COST, CheckRequired, Config
from app.entry_timing import data as DA
from tests import _krx_fixture as KF

NOW = datetime(2026, 11, 24, 3, 0, tzinfo=timezone.utc)


# ── 두 기준 · 오른 주(연구와 이번 주 화면이 같은 함수) ─────────────────────────────


@pytest.mark.parametrize(
    "closes, want",
    [
        ([1, 2, 3, 4, 5], 4),
        ([5, 4, 3, 2, 1], 0),
        ([1, 1, 1, 1, 1], 0),  # 변화 없음 = 오름 아님
        ([1, 1 + 1e-12, 2, 2, 3], 2),  # 1e-9 이하 차이 = 변화 없음
        ([1, None, 2, 3, 4], None),  # 값 없음 = 미확인
        ([1, 0, 2, 3, 4], None),  # 0 이하 = 미확인
        ([1, 2, 3, 4], None),  # 다섯 번이 아님
    ],
)
def test_up_weeks(closes, want) -> None:
    assert RU.up_weeks(closes) == want


def test_pick_a_orders_by_return_then_code() -> None:
    c = [
        RU.Cand("B", 0.1, 1),
        RU.Cand("A", 0.1, 0),
        RU.Cand("C", 0.3, 2),
        RU.Cand("D", -0.1, 4),
    ]
    assert RU.pick_a(c) == ["C", "A", "B"]


def test_pick_b_up_weeks_then_return_rank_then_fill() -> None:
    c = [
        RU.Cand("A", 0.11, 1),  # 1개월 1위 · 오른 주 1
        RU.Cand("B", 0.07, 4),  # 37위 같은 자리 · 4주
        RU.Cand("C", 0.09, 4),
        RU.Cand("D", 0.08, 3),
        RU.Cand("E", -0.05, 4),  # 음수는 시험 기준 앞자리에 못 듦
    ]
    assert RU.pick_b(c) == ["C", "B", "D"]
    # 양수가 둘뿐 → 남는 자리는 1개월 순서로 채움
    few = [
        RU.Cand("A", 0.02, 0),
        RU.Cand("B", 0.01, 1),
        RU.Cand("C", -0.01, 4),
        RU.Cand("D", -0.02, 4),
    ]
    assert RU.pick_b(few) == ["B", "A", "C"]
    with pytest.raises(ValueError):
        RU.pick_b([RU.Cand("A", 0.1, None)])


def test_same_selection_is_set_based_and_turnover() -> None:
    assert RU.same_selection(["A", "B", "C"], ["C", "A", "B"])
    assert not RU.same_selection(["A", "B", "C"], ["A", "B", "D"])
    assert RU.changed_count(["A", "B", "C"], ["C", "B", "A"]) == 0
    assert RU.changed_count(["A", "B", "D"], ["A", "X", "Y"]) == 2
    assert RU.changed_count(["A"], None) is None


# ── 자리 판정 · 비용 · 낙폭(손으로 만든 행렬) ────────────────────────────────────


def _data(
    n_days: int = 30, codes=("069500", "AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG")
) -> PO.Data:
    axis = [
        f"2021-01-{d:02d}" if d <= 31 else f"2021-02-{d - 31:02d}"
        for d in range(1, n_days + 1)
    ]
    shape = (len(codes), n_days)
    one = np.ones(shape)
    panel = DA.Panel(
        axis=axis,
        codes=list(codes),
        I=one * 100.0,
        O=one * 100.0,
        C=one * 100.0,
        seg=np.zeros(shape, dtype=np.int32),
        has_row=np.ones(shape, dtype=bool),
        exec_ok=np.ones(shape, dtype=bool),
        name=np.full(shape, "TEST", dtype=object),
        index_name=np.full(shape, "", dtype=object),
    )
    return PO.Data(panel=panel, vol=np.full(shape, 1000.0))


def test_slot_states() -> None:
    d = _data()
    p, ci = d.panel, d.panel.ci
    e1, e2 = 2, 22
    p.exec_ok[ci["BBB"], e1] = False
    d.vol[ci["BBB"], e1] = 0.0  # 행 있음 · 거래량 0 → 현금
    p.has_row[ci["CCC"], e1] = False  # 행 없음 → 미확인(폐지로 확정하지 않음)
    p.exec_ok[ci["DDD"], e1] = False  # 행 있고 거래량 있으나 체결 판정 실패 → 미확인
    p.has_row[ci["EEE"], e2] = False
    p.seg[ci["FFF"], e2] = 1
    p.exec_ok[ci["GGG"], e2] = False
    got = {
        c: ST.slot(d, c, e1, e2)
        for c in ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG")
    }
    assert (got["AAA"]["entry"], got["AAA"]["exit"]) == ("OK", "OK")
    assert got["BBB"]["entry"] == "CASH" and got["BBB"]["why"] == "NO_TRADE_E1"
    assert got["CCC"]["entry"] == "UNKNOWN" and got["CCC"]["why"] == "NO_ROW_E1"
    assert got["DDD"]["entry"] == "UNKNOWN" and got["DDD"]["why"] == "NOT_EXEC_E1"
    assert [got[c]["why"] for c in ("EEE", "FFF", "GGG")] == [
        "NO_ROW_E2",
        "SEG_BREAK",
        "NOT_EXEC_E2",
    ]
    assert [ST.unknown(got[c]) for c in ("AAA", "BBB", "CCC", "EEE")] == [
        False,
        False,
        True,
        True,
    ]


def test_basket_cost_cash_and_mdd() -> None:
    d = _data()
    p, ci = d.panel, d.panel.ci
    e1, e2 = 2, 22
    p.O[ci["AAA"], e2] = 110.0  # +10% 가격 → 비용 후 110·0.998/(100·1.002) − 1
    p.I[ci["AAA"], 5] = 90.0  # 보유 중 −10% 종가 → 낙폭
    p.exec_ok[ci["BBB"], e1] = False
    d.vol[ci["BBB"], e1] = 0.0  # 현금 0%
    bk = ST.basket(d, ["AAA", "BBB", "CCC"], e1, e2, COST, alt=False)
    a = 110 * 0.998 / (100 * 1.002) - 1
    assert bk["ret"] == pytest.approx(
        (a + 0.0 + (100 * 0.998 / (100 * 1.002) - 1)) / 3, abs=1e-15
    )
    # 묶음 경로: 세 자리 평균 · AAA 가 90 일 때 (0.9 + 1 + 1)/3 = 0.9667 → 낙폭 1 − 0.9667
    assert bk["mdd"] == pytest.approx(1 - (0.9 + 1 + 1) / 3, abs=1e-12)


def test_basket_unknown_base_vs_alternative() -> None:
    d = _data()
    p, ci = d.panel, d.panel.ci
    e1, e2 = 2, 22
    p.has_row[ci["AAA"], e1] = False  # 편입 미확인
    p.has_row[ci["BBB"], e2] = False  # 청산 미확인 · 같은 구간 마지막 종가 = e2 − 1
    p.I[ci["BBB"], e2 - 1] = 105.0
    base = ST.basket(d, ["AAA", "BBB", "CCC"], e1, e2, COST, alt=False)
    assert base["ret"] is None
    alt = ST.basket(d, ["AAA", "BBB", "CCC"], e1, e2, COST, alt=True)
    s = {x["code"]: x for x in alt["slots"]}
    assert s["AAA"]["value"] == "CASH"
    assert s["BBB"]["exit"] == "REFERENCE" and s["BBB"]["ref_date"] == p.axis[e2 - 1]
    want = (
        0.0 + (105 * 0.998 / (100 * 1.002) - 1) + (100 * 0.998 / (100 * 1.002) - 1)
    ) / 3
    assert alt["ret"] == pytest.approx(want, abs=1e-15)
    # 같은 구간 유효 종가(편입일 포함)가 하나도 없으면 대안도 평가 불가
    lo, hi = e1 + 1, e2 + 1
    p.seg[ci["BBB"], lo:hi] = 2  # 편입 다음 날부터 다른 구간
    p.I[ci["BBB"], e1] = np.nan  # 편입일 종가도 없음
    assert ST.basket(d, ["BBB"], e1, e2, COST, alt=True)["ret"] is None


def _week(a, b, same=None) -> dict:
    return {
        "signal": "2021-01-01",
        "span": "main",
        "sub": 0,
        "status": "OK",
        "entry": "2021-01-03",
        "exit": "2021-01-23",
        "a": a,
        "b": b,
        "same": RU.same_selection(a, b) if same is None else same,
    }


def test_evaluate_week_pairs_invalid_and_same_selection_zero() -> None:
    d = _data()
    p, ci = d.panel, d.panel.ci
    p.O[ci["DDD"], 22] = 120.0
    r = ST.evaluate_week(
        d, _week(["AAA", "BBB", "CCC"], ["CCC", "AAA", "BBB"]), COST, alt=False
    )
    assert r["status"] == "OK" and r["d"] == 0.0  # 순서만 다름 = 같은 선택
    p.has_row[ci["EEE"], 22] = False  # B 쪽 청산 미확인 → 두 묶음 함께 평가 불가
    r = ST.evaluate_week(
        d, _week(["AAA", "BBB", "CCC"], ["DDD", "EEE", "AAA"]), COST, alt=False
    )
    assert r["status"] == "INVALID" and r["ret_a"] is None and r["ret_b"] is None
    assert ["B", "EEE", "NO_ROW_E2"] in r["reasons"]
    bad, total = ST.unconfirmed_slots([r], alt=False)
    assert (bad, total) == (1, 6)
    # KODEX 200 값이 빠져도 주 평가는 그대로(그 열만 미확인)
    p.has_row[ci["EEE"], 22] = True
    p.exec_ok[ci["069500"], 2] = False
    r = ST.evaluate_week(
        d, _week(["AAA", "BBB", "CCC"], ["DDD", "EEE", "AAA"]), COST, alt=False
    )
    assert r["status"] == "OK" and r["kodex"] is None and r["d"] > 0


# ── 판정 순서(PLAN §4 · 판정 Q5) ─────────────────────────────────────────────


def _summary(**kw) -> dict:
    s = {
        "valid_weeks": 290,
        "unconfirmed_share": 0.002,
        "delta": 0.003,
        "bootstrap": {"lo": 0.001, "hi": 0.005},
        "sub_wins": 3,
        "mdd": {"weeks": 290, "b_minus_a": 0.005},
        "turnover": {"b_minus_a": 0.2},
        "diff_weeks": 200,
    }
    s.update(kw)
    return s


CFG = Config(root=Path("/nonexistent"), expected=None)


@pytest.mark.parametrize(
    "base, alt, code",
    [
        (_summary(valid_weeks=235), _summary(), "UNDECIDABLE"),  # 236 미만
        (_summary(unconfirmed_share=0.051), _summary(), "UNDECIDABLE"),  # 5% 초과
        (_summary(delta=0.0), _summary(), "SHORT"),
        (
            _summary(delta=-0.01, valid_weeks=10),
            _summary(),
            "UNDECIDABLE",
        ),  # 순서: 자료 먼저
        (_summary(), _summary(), "CANDIDATE"),
        (_summary(bootstrap={"lo": -0.0001}), _summary(), "UNCONFIRMED"),
        (_summary(delta=0.0019), _summary(), "UNCONFIRMED"),
        (_summary(sub_wins=1), _summary(), "UNCONFIRMED"),
        (_summary(mdd={"weeks": 290, "b_minus_a": 0.0101}), _summary(), "UNCONFIRMED"),
        (
            _summary(mdd={"weeks": 0, "b_minus_a": None}),
            _summary(),
            "UNCONFIRMED",
        ),  # 낙폭 확인 불가
        (_summary(turnover={"b_minus_a": 0.51}), _summary(), "UNCONFIRMED"),
        (_summary(diff_weeks=25), _summary(), "UNCONFIRMED"),
        (_summary(), _summary(valid_weeks=200), "UNCONFIRMED"),  # 대안 자료 기준 미충족
        (_summary(), _summary(delta=0.001), "UNCONFIRMED"),  # 대안 조건 미충족
    ],
)
def test_judge_order(base, alt, code) -> None:
    assert ST.judge(base, alt, CFG)["code"] == code


# ── 가짜 봉인 DB: 주 기록 · 잠금 → 실행 1회 → 독립 재계산 ─────────────────────────

DATES = KF.trading_dates(120, start=20210104)


def _sealed(tmp_path: Path, patch=None) -> tuple[Path, str]:
    rng = np.random.default_rng(7)
    maps = []
    specs = {"069500": ("KODEX 200", 0.0005)}
    for k in range(12):
        specs[f"T{k:05d}"] = (f"TEST {k}", 0.0)
    specs["T09999"] = ("TEST 인버스", 0.004)
    for code, (name, drift) in specs.items():
        r = drift + rng.normal(0, 0.01, len(DATES))
        closes = list(np.round(10000 * np.cumprod(1 + r), 0))
        rows = KF.series_rows(code, DATES, closes, name=name)
        maps.append(rows)
    by_date = KF.rows_by_date(*maps)
    if patch:
        patch(by_date)
    db = tmp_path / "sealed.sqlite"
    return db, KF.build_sealed_db(db, by_date)


def _cfg(tmp_path: Path, db: Path, content: str, **kw) -> Config:
    base = dict(
        db=db,
        file_sha=None,
        content_sha=content,
        root=tmp_path / "out",
        spans={
            "main": ("2021-02-15", "2021-05-20"),
            "aux": ("2014-01-01", "2020-12-31"),
        },
        subs=(
            ("2021-02-15", "2021-03-15"),
            ("2021-03-16", "2021-04-15"),
            ("2021-04-16", "2021-05-20"),
        ),
        expected=None,
        valid_weeks_min=1,
    )
    base.update(kw)
    return Config(**base)


def _iso(d: str) -> str:
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


GAP = next(d for d in DATES[60:] if datetime.strptime(d, "%Y%m%d").weekday() == 4)


def test_weeks_population_name_filter_and_common_set(tmp_path: Path) -> None:
    def patch(
        by,
    ):  # T00003 은 한 금요일(주 마감) 행이 없음 → 그 날을 주 마감으로 쓰는 주의 공통 후보군에서 빠짐
        by[GAP] = [r for r in by[GAP] if r["ISU_CD"] != "T00003"]

    db, content = _sealed(tmp_path, patch)
    cfg = _cfg(tmp_path, db, content)
    data = PO.load(cfg)
    weeks = PO.build_weeks(data, cfg)
    assert weeks and all(w["span"] == "main" and w["status"] == "OK" for w in weeks)
    for w in weeks:
        # 인버스(하루 +0.4% 추세)는 이름으로 빠져 어느 순서에도 없다
        assert "T09999" not in w["a_order"] + w["b_order"] + list(w["picks"])
        assert len(w["a"]) == 3 and len(w["b"]) == 3 and w["n_pop"] <= 13
    gap = _iso(GAP)
    hit = [w for w in weeks if gap in w["weekly_dates"][:-1] and w["window"][0] != gap]
    assert hit
    for w in hit:
        assert "T00003" in [c for c, _ in w["dropped"]]
        assert w["n_common"] == w["n_pop"] - 1
    cnt = PO.counts(weeks, cfg.spans)
    assert cnt["main"]["weeks"] == len(weeks)
    assert cnt["main"]["common_missing"] == sum(len(w["dropped"]) for w in weeks)
    with pytest.raises(CheckRequired):
        PO.check_expected(cnt, {"main": {"weeks": len(weeks) + 1}})


def test_prepare_run_verify_once(tmp_path: Path) -> None:
    db, content = _sealed(tmp_path)
    cfg = _cfg(tmp_path, db, content)
    lock = FW.prepare(cfg, NOW)
    assert lock["counts"]["main"]["weeks"] > 0
    with pytest.raises(CheckRequired):
        FW.prepare(cfg, NOW)  # 잠금이 이미 있음
    res = FW.run(cfg, NOW)
    assert res["verdict"]["code"] in (
        "UNDECIDABLE",
        "SHORT",
        "CANDIDATE",
        "UNCONFIRMED",
    )
    with pytest.raises(CheckRequired):
        FW.run(cfg, NOW)  # 공식 실행은 한 번
    v = VF.verify(cfg, NOW)
    assert v["status"] == "VERIFIED_OK", v["checks"]
    run_dir = Path(res["dir"])
    rep = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert rep["main"]["assigned_slots"] == 6 * rep["main"]["ok_weeks"]
    md = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "판정:" in md and "비용 후 가격 모의 결과" in md


def test_verify_catches_changed_record(tmp_path: Path) -> None:
    db, content = _sealed(tmp_path)
    cfg = _cfg(tmp_path, db, content)
    FW.prepare(cfg, NOW)
    res = FW.run(cfg, NOW)
    f = Path(res["dir"]) / "weeks.json"
    f.chmod(0o644)
    body = json.loads(f.read_text(encoding="utf-8"))
    body["rows"][0]["base"]["d"] = 0.5
    f.write_text(json.dumps(body), encoding="utf-8")
    v = VF.verify(cfg, NOW)
    assert v["status"] == "MISMATCH" and any("해시" in c for c in v["checks"])


def test_run_refuses_changed_settings(tmp_path: Path) -> None:
    db, content = _sealed(tmp_path)
    cfg = _cfg(tmp_path, db, content)
    FW.prepare(cfg, NOW)
    other = _cfg(tmp_path, db, content, subs=(("2021-02-15", "2021-03-31"),) * 3)
    with pytest.raises(CheckRequired):
        FW.run(other, NOW)
    assert FW.runs(FW.real_root(cfg.root), FW.locks(FW.real_root(cfg.root))[0][0]) == []


def test_refusal_before_results_leaves_no_run(tmp_path: Path, monkeypatch) -> None:
    db, content = _sealed(tmp_path)
    cfg = _cfg(tmp_path, db, content)
    FW.prepare(cfg, NOW)
    real = PO.build_weeks

    def shifted(data, c):
        w = real(data, c)
        w[0] = {**w[0], "b": list(reversed(w[0]["b"]))}
        return w

    monkeypatch.setattr(PO, "build_weeks", shifted)
    with pytest.raises(CheckRequired):
        FW.run(cfg, NOW)  # 주 기록이 잠금과 다름 — 결과 계산 전 거부
    root = FW.real_root(cfg.root)
    assert FW.runs(root, FW.locks(root)[0][0]) == []  # 기록 없음 · 잠금 그대로
    monkeypatch.setattr(PO, "build_weeks", real)
    assert FW.run(cfg, NOW)["run_id"]


def test_failure_during_evaluation_consumes_lock_and_allows_correction(
    tmp_path: Path, monkeypatch
) -> None:
    db, content = _sealed(tmp_path)
    cfg = _cfg(tmp_path, db, content)
    FW.prepare(cfg, NOW)

    def boom(*a, **k):
        raise RuntimeError("계산 중 중단 흉내")

    monkeypatch.setattr(ST, "evaluate", boom)
    with pytest.raises(RuntimeError):
        FW.run(cfg, NOW)
    root = FW.real_root(cfg.root)
    rd = FW.runs(root, FW.locks(root)[0][0])
    assert len(rd) == 1 and (rd[0] / "started.json").exists()
    assert FW.run_status(root, rd[0]) == "FAILED"
    with pytest.raises(CheckRequired):
        FW.run(cfg, NOW)  # 같은 잠금으로 다시 실행 거부
    with pytest.raises(CheckRequired):
        FW.prepare(cfg, NOW)  # 사유 없는 정정 거부
    later = datetime(2026, 11, 24, 4, 0, tzinfo=timezone.utc)
    lock2 = FW.prepare(cfg, later, "계산 중 중단(코드 변경 없음 · 실패 실행)")
    assert lock2["previous_lock"] is not None
    monkeypatch.undo()
    assert FW.run(cfg, later)["lock_id"] == lock2["lock_id"]


def test_correction_lock_before_run_needs_code_change(
    tmp_path: Path, monkeypatch
) -> None:
    db, content = _sealed(tmp_path)
    cfg = _cfg(tmp_path, db, content)
    FW.prepare(cfg, NOW)
    with pytest.raises(CheckRequired):
        FW.prepare(cfg, NOW, "사유만 있고 코드 그대로")
    real = FW.code_hashes
    monkeypatch.setattr(FW, "code_hashes", lambda repo: {**real(repo), "x": "changed"})
    later = datetime(2026, 11, 24, 4, 0, tzinfo=timezone.utc)
    assert FW.prepare(cfg, later, "실행 전 코드 결함 정정")["lock_id"]


@pytest.mark.parametrize(
    "base, code",
    [
        (_summary(valid_weeks=236), "CANDIDATE"),  # 정확히 236 = 통과
        (_summary(unconfirmed_share=0.05), "CANDIDATE"),  # 정확히 5% = 통과
        (_summary(delta=0.002), "CANDIDATE"),  # 정확히 0.20%p = 충족
        (_summary(sub_wins=2), "CANDIDATE"),
        (_summary(mdd={"weeks": 290, "b_minus_a": 0.01}), "CANDIDATE"),  # 정확히 1.0%p
        (_summary(turnover={"b_minus_a": 0.5}), "CANDIDATE"),
        (_summary(diff_weeks=26), "CANDIDATE"),
    ],
)
def test_judge_boundaries(base, code) -> None:
    assert ST.judge(base, base, CFG)["code"] == code


def test_alternative_unconfirmed_counts_only_missing_exit() -> None:
    row = {
        "status": "OK",
        "slots_a": [
            {"entry": "UNKNOWN", "exit": None},
            {"entry": "OK", "exit": "REFERENCE"},
        ],
        "slots_b": [{"entry": "OK", "exit": "UNKNOWN"}],
    }
    assert ST.unconfirmed_slots([row], alt=True) == (
        1,
        3,
    )  # 현금 가정 · 참고 평가액은 빠진 자리 아님
    assert ST.unconfirmed_slots([row], alt=False) == (2, 3)


def test_reference_close_may_be_evaluation_or_entry_day() -> None:
    d = _data()
    p, ci = d.panel, d.panel.ci
    e1, e2 = 2, 22
    p.exec_ok[ci["AAA"], e2] = (
        False  # 평가일 시가 체결 불가 · 그날 종가는 있음 → 참고 평가액 = 평가일 종가
    )
    p.I[ci["AAA"], e2] = 104.0
    s = {x["code"]: x for x in ST.basket(d, ["AAA"], e1, e2, COST, alt=True)["slots"]}
    assert s["AAA"]["ref_date"] == p.axis[e2] and s["AAA"]["exit_px"] == 104.0
    lo, hi = e1 + 1, e2 + 1
    p.seg[ci["BBB"], lo:hi] = 3
    p.has_row[ci["BBB"], e2] = True
    p.exec_ok[ci["BBB"], e2] = False
    s = {x["code"]: x for x in ST.basket(d, ["BBB"], e1, e2, COST, alt=True)["slots"]}
    assert s["BBB"]["ref_date"] == p.axis[e1]  # 같은 구간은 편입일 종가뿐


def test_kodex_column_needs_same_segment() -> None:
    d = _data()
    p, ci = d.panel, d.panel.ci
    assert ST.kodex(d, 2, 22, COST) is not None
    p.seg[ci["069500"], 22] = 5
    assert ST.kodex(d, 2, 22, COST) is None


def _axis_panel(codes: dict) -> PO.Data:
    """실제 평일 축(주 신호가 나오는) · 종목별 (이름, 일 수익률, 다른 구간으로 둘 위치 목록)."""
    start = datetime(2021, 1, 4)
    axis = [
        (start + timedelta(days=k)).date().isoformat()
        for k in range(90)
        if (start + timedelta(days=k)).weekday() < 5
    ]
    shape = (len(codes), len(axis))
    chain = np.zeros(shape)
    seg = np.zeros(shape, dtype=np.int32)
    names = np.full(shape, "", dtype=object)
    for j, (code, (name, r, odd)) in enumerate(codes.items()):
        chain[j] = 100.0 * (1 + r) ** np.arange(len(axis))
        names[j] = name
        for pos in odd or ():
            seg[j, pos] = 7
    panel = DA.Panel(
        axis=axis,
        codes=list(codes),
        I=chain,
        O=chain.copy(),
        C=chain.copy(),
        seg=seg,
        has_row=np.ones(shape, dtype=bool),
        exec_ok=np.ones(shape, dtype=bool),
        name=names,
        index_name=np.full(shape, "", dtype=object),
    )
    return PO.Data(panel=panel, vol=np.ones(shape))


def test_week_close_in_other_segment_is_missing_and_few_candidates() -> None:
    data = _axis_panel(
        {"069500": ("KODEX 200", 0.001, None), "AAA": ("가", 0.002, None)}
    )
    panel = data.panel
    sig = DA.weekly_signals(panel.axis)
    cfg = Config(
        root=Path("/nonexistent"),
        expected=None,
        spans={"main": ("2021-01-01", "2021-12-31")},
    )
    k = 6
    w = PO.week_record(panel, k, sig, cfg)
    assert w["status"] == "FEW" and w["n_common"] == 2  # 공통 후보 2개 < 3
    i = sig[k]
    s = DA.window_start(panel.axis, i, 30)
    wk = [sig[k - 4 + m] for m in range(5)]
    assert s < wk[0]
    data2 = _axis_panel(
        {"069500": ("KODEX 200", 0.001, None), "BBB": ("나", 0.002, [wk[0]])}
    )
    pop = {p["code"]: p for p in PO.population(data2.panel, i, s, wk)}
    # D · 1개월 시작은 같은 구간이라 전체 후보에는 있지만, W-4 값만 다른 구간 → 오른 주 미확인
    assert "BBB" in pop and pop["BBB"]["up"] is None and pop["BBB"]["closes"][0] is None


class _Src:
    """verify 바구니용 가짜 원천 — 행은 있으나 체결 판정 실패(거래량 있음)."""

    def open_star(self, code, d):
        return None if (code == "X" and d == "E1") else 100.0

    def has(self, code, d):
        return True

    def no_trade(self, code, d):
        return False

    def seg(self, code, d):
        return 0

    def chain(self, code, d):
        return (100.0, 0)


def test_population_needs_same_segment_at_signal_and_window_start() -> None:
    probe = _axis_panel({"069500": ("KODEX 200", 0.001, None)})
    sig = DA.weekly_signals(probe.panel.axis)
    k = 6
    i = sig[k]
    s = DA.window_start(probe.panel.axis, i, 30)
    wk = [sig[k - 4 + m] for m in range(5)]
    data = _axis_panel(
        {"069500": ("KODEX 200", 0.001, None), "CCC": ("다", 0.002, [s])}
    )
    pop = {p["code"] for p in PO.population(data.panel, i, s, wk)}
    assert (
        "069500" in pop and "CCC" not in pop
    )  # 1개월 시작일이 다른 구간 → 1개월 수익률을 잇지 않음


def test_verify_basket_unknown_entry_is_not_cash() -> None:
    bk = RW._basket(_Src(), ["X", "Y", "Z"], "E1", "E2", ["D1"], COST, False)
    assert bk["ret"] is None and bk["slots"][0]["entry"] == "UNKNOWN"
    assert bk["slots"][0]["why"] == "NOT_EXEC_E1" and "value" not in bk["slots"][0]
    bk = RW._basket(_Src(), ["X", "Y", "Z"], "E1", "E2", ["D1"], COST, True)
    assert bk["ret"] is not None and bk["slots"][0]["value"] == "CASH"
