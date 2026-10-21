"""POC6-04 — D20 확장 표본 재현 검증(격리 시험 · tmp 만 · 외부 호출 0 · 라이브 DB 0).

합성 세계: 공식 snapshot 7종(공식 적격 4 · 가격 경계로 빠지는 월 분배 이름 2 · 상장 짧은 1) →
A = POC6-02 실행기로 만든 실제 CPU 보고서 · 사본 = POC6-03 저장 함수(4종은 400번째 날 전 가격 기준이 다름) ·
KRX 대조 보고서 = 최소 JSON. 실제 B · C 학습은 POC6-02 `run_cpu` 그대로.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from app.d20_expand import checks as K
from app.d20_expand import inputs as IN
from app.d20_expand import runner as RU
from app.d20_pooled import report as R02R
from app.d20_pooled import runner as R02
from app.d20_pooled import study as S
from app.d20_pooled.snapshot import digest
from app.price_basis_check import fetch as F03
from app.reentry_review import prices
from app.reentry_review.prices import FDR, NAVER

N = 560
FOUR = ["367760", "381170", "395160", "442580"]
MONTHLY = ["161510", "441800"]
SHORT = "0193T0"


def _weekdays(start: str, n: int) -> list[str]:
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


DATES = _weekdays("2023-01-02", N)
T = DATES[-1]


def _walk(seed: int, n: int = N) -> list[float]:
    rnd, c, out = random.Random(seed), 10000.0, []
    for _ in range(n):
        c *= math.exp(rnd.gauss(0.0002, 0.015))
        out.append(round(c, 2))
    return out


def _rows(closes, dates=DATES, source=NAVER, fetched="2026-10-05T00:00:00Z"):
    out, prev = [], None
    for d, c in zip(dates, closes):
        out.append([d, c, source, fetched, None if prev is None else c / prev - 1.0])
        prev = c
    return out


def _break_rows(closes):
    """FDR 행 · 370번째 날 change 가 종가 비율과 다름(BASIS_BREAK) → 공식에서는 시험 날짜 부족."""
    rows = _rows(closes, source=FDR)
    rows[370][4] = rows[370][4] + 0.01
    return rows


def _snap(etfs: dict, dates=None) -> dict:
    dates = dates or DATES
    t_day = dates[-1]
    firsts = [r[0][0] for r in etfs.values() if r]
    first = min(firsts)
    years = range(int(first[:4]), int(t_day[:4]) + 1)
    return {
        "schema": "poc6_02_snapshot_v1",
        "T": t_day,
        "holdings": {
            "status": "OK",
            "rows": len(etfs) + 1,
            "tickers": len(etfs) + 1,
            "etf": len(etfs),
            "non_etf": 1,
        },
        "axis": {
            "label": prices.AXIS_LABEL,
            "dates": [d for d in dates if d >= first],
            "modes": {str(y): prices.MODE_KOSPI for y in years},
            "skipped_weekdays": [],
            "kospi_latest": t_day,
            "calendar_years": [],
            "problem": None,
        },
        "price_basis_label": prices.PRICE_BASIS_LABEL,
        "etfs": {t: {"name": f"ETF {t}", "rows": r} for t, r in etfs.items()},
    }


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _copy_closes(t: str, live: dict) -> list[list]:
    """사본 종가 — 4종은 400번째 날 전이 0.5% 낮은 기준(정답 · feature 가 A 와 달라짐) · 나머지는 경계 없는 종가."""
    rows = live[t]
    out = []
    for k, r in enumerate(rows):
        c = r[1] * (0.995 if t in FOUR and DATES.index(r[0]) < 400 else 1.0)
        out.append([r[0], c])
    return out


def _df(pairs):
    idx = pd.to_datetime([p[0] for p in pairs])
    close = pd.Series([p[1] for p in pairs], index=idx, dtype=float)
    return pd.DataFrame({"Close": close, "Change": close.pct_change()})


def build_world(
    tmp: Path,
    monkeypatch,
    *,
    drop_date_for=None,
    drop_date=None,
    c_etfs=6,
    monthly=None,
) -> dict:
    live = {t: _rows(_walk(s)) for s, t in enumerate(FOUR, start=3)}
    for s, t in enumerate(MONTHLY, start=11):
        live[t] = _break_rows(_walk(s))
    live[SHORT] = _rows(_walk(21, 200), DATES[-200:])
    official = _snap(live)
    snap_path = tmp / "official" / "input_snapshot.json"
    snap_path.parent.mkdir(parents=True)
    snap_path.write_text(json.dumps(official), encoding="utf-8")
    monkeypatch.setattr(R02R, "RESEARCH_ROOT", tmp / "poc6_02")
    a_folder = R02.run(snapshot_path=snap_path)
    # 사본(POC6-03 저장 함수 · 가짜 조회기)
    monkeypatch.setattr(F03, "RESEARCH_ROOT", tmp / "poc6_03")

    def fake(t, start, end):
        pairs = [
            p
            for p in _copy_closes(t, live)
            if start.isoformat() <= p[0] <= end.isoformat()
        ]
        if t == drop_date_for:
            pairs = [p for p in pairs if p[0] != (drop_date or DATES[420])]
        return _df(pairs)

    batch = F03.fetch_batch(official, fetcher=fake)
    copy_dir = F03.write_copy(official, snap_path, batch)
    basis = {
        "per_ticker": {
            t: {
                "krx": {
                    "match": 90,
                    "mismatch": 10 if t in MONTHLY else 2,
                    "not_comparable": {"KRX_OUT_OF_RANGE": 16},
                    "a_over_c": {
                        "first": {"date": DATES[0]},
                        "last": {"date": DATES[540]},
                    },
                }
            }
            for t in live
        }
    }
    basis_path = tmp / "basis" / "report.json"
    basis_path.parent.mkdir(parents=True)
    basis_path.write_text(json.dumps(basis), encoding="utf-8")
    md = basis_path.parent / "report.md"
    md.write_text("# 대조\n", encoding="utf-8")
    files = {
        "official_snapshot": snap_path,
        "a_report": a_folder / "report.json",
        "copy_fetch": copy_dir / "fetch.json",
        "copy_db": copy_dir / "copy.sqlite",
        "basis_report": basis_path,
        "basis_report_md": md,
    }
    manifest = {
        "files": {k: {"path": str(p), "sha256": _sha(p)} for k, p in files.items()},
        "expect": {"b_etfs": 4, "c_etfs": c_etfs, "dates_per_block": 63},
        "monthly": list(monthly or MONTHLY),
        "krx_end": DATES[
            543
        ],  # 3구간 목표 창 끝 > 이 날인 16일을 보조 (b) 에서 뺌(실제와 같은 47 / 16)
    }
    monkeypatch.setattr(RU, "RESEARCH_ROOT", tmp / "poc6_04")
    return {
        "manifest": manifest,
        "files": files,
        "a_folder": a_folder,
        "official": official,
    }


@pytest.fixture
def counted(monkeypatch):
    class Calls(list):
        fits: list

    calls = Calls()
    real = S.run_cpu

    def wrapped(snap, **k):
        calls.append(sorted(snap["etfs"]))
        return real(snap, **k)

    fits = []
    real_fit = S.fit_hgb

    def fit(*a, **k):
        fits.append(1)
        return real_fit(*a, **k)

    monkeypatch.setattr(S, "run_cpu", wrapped)
    monkeypatch.setattr(S, "fit_hgb", fit)
    calls.fits = fits
    return calls


def test_end_to_end_comparability_tables_and_no_retraining(
    tmp_path, monkeypatch, counted
):
    w = build_world(tmp_path, monkeypatch)
    counted.clear()  # A 를 만들 때의 학습은 세지 않음
    counted.fits.clear()
    a_sha = _sha(w["files"]["a_report"])
    p2_before = sorted(
        p.relative_to(tmp_path) for p in (tmp_path / "poc6_02").rglob("*")
    )
    folder, rep = RU.run(w["manifest"], tmp_path)
    assert rep["status"] == RU.COMPLETED, rep.get("problems") or rep.get("reason")
    assert (
        len(counted) == 2
    )  # B · C 한 번씩(재현 확인 두 번 학습은 run_cpu 안) · 보조 분석 재학습 0
    assert (
        len(counted.fits) == 12
    )  # B · C × 3구간 × (공식 + 재현 확인) — 보조 · 표에서 HGB 다시 학습 0
    assert rep["four"] == FOUR and len(rep["c_etfs"]) == 6
    assert rep["environment"]["libraries"]["scikit-learn"]
    assert set(MONTHLY) <= set(rep["c_etfs"]) and SHORT not in rep["c_etfs"]
    # 대조군 · 공통 평가
    assert rep["control"]["ok"] and rep["control"]["over_tolerance_rows"] == 0
    assert all(v <= K.CONTROL_TOL for v in rep["control"]["max_abs_diff"].values())
    c4 = rep["common4"]
    assert c4["B"][S.HGB]["rows"] == c4["C_on_4"][S.HGB]["rows"] == 756
    assert c4["B"][S.HGB]["dates"] == c4["C_on_4"][S.HGB]["dates"] == 189
    for m in (S.MEDIAN, S.RIDGE):  # ETF 별 학습 → B 와 C 의 4종 점수 같음
        assert c4["B"][m] == c4["C_on_4"][m]
    td = c4["truth_diff_A_vs_B"]
    assert td["rows"] == 756 and td["over_0_001"] > 0 and td["max_abs"] > 0
    # C 12(여기 6)종 · 판정 이름
    assert rep["c12"]["verdict"]["label"] in (K.LABEL_MET, K.LABEL_NOT_MET)
    assert rep["c12"]["rows_dates"][0]["rows"] == 63 * 6
    # 보조 (a) 평가만 거름 · (b) 목표 창 끝 기준
    assert rep["aux_a"]["scores"][S.HGB]["rows"] == 3 * 63 * 4
    rd = rep["aux_b"]["rows_dates"]
    assert (rd["B"]["rows"], rd["B"]["dates"], rd["removed_B"]) == (188, 47, 64)
    assert (rd["C"]["rows"], rd["removed_C"]) == (47 * 6, 16 * 6)
    ab = rep["aux_b"]
    assert ab["C_on_4"][S.HGB]["rows"] == 188  # 공통 4종 같은 행(판정 §4)
    for m in (S.MEDIAN, S.RIDGE):
        assert ab["C_on_4"][m] == ab["B"][m]
    assert set(rep["directions"]) == {
        "main_overall",
        "main_block3",
        "aux_a_overall",
        "aux_b_block3",
    }
    dirs = rep["directions"]  # 보고서 값으로 다시 계산 — 비교 상대가 맞게 연결됐는지
    assert dirs["main_overall"] == K.direction(rep["c12"]["scores"])
    assert dirs["main_block3"] == K.direction(rep["c12"]["scores"], block=2)
    assert dirs["aux_a_overall"] == K.direction(rep["aux_a"]["scores"])
    assert dirs["aux_b_block3"] == K.direction(ab["C"])
    want = int(dirs["aux_a_overall"] != dirs["main_overall"]) + int(
        dirs["aux_b_block3"] != dirs["main_block3"]
    )
    assert len(rep["direction_notes"]) == want
    # 입력 고정 · A 고정 사본 · 새 snapshot digest · GPU 묶음 · POC6-02 폴더 불변
    names = sorted(p.name for p in folder.iterdir())
    assert names == [
        "a_report_frozen.json",
        "b_snapshot.json",
        "c_snapshot.json",
        "manifest.json",
        "report.json",
        "report.md",
    ]
    assert _sha(folder / "a_report_frozen.json") == a_sha
    man = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert all(len(v["sha256"]) == 64 for v in man["inputs"].values())
    assert rep["snapshots"]["B"]["digest"] != digest(w["official"])
    assert rep["snapshots"]["C"]["digest"] != rep["snapshots"]["B"]["digest"]
    assert (
        sorted(p.relative_to(tmp_path) for p in (tmp_path / "poc6_02").rglob("*"))
        == p2_before
    )
    md = (folder / "report.md").read_text(encoding="utf-8")
    assert (
        "탐색적" in md
        and "목표 창이 KRX 대조 범위 안인 행" in md
        and "MAE 를 빼지 않는다" in md
    )


def test_hash_mismatch_or_other_inputs_are_check_required(
    tmp_path, monkeypatch, counted
):
    w = build_world(tmp_path, monkeypatch)
    counted.clear()
    m = json.loads(json.dumps(w["manifest"]))
    m["files"]["copy_db"]["sha256"] = "0" * 64
    with pytest.raises(IN.InputError, match="sha256"):
        RU.run(m, tmp_path)
    monkeypatch.setattr(R02, "recipe_digest", lambda: "x")
    with pytest.raises(IN.InputError, match="recipe"):
        RU.run(w["manifest"], tmp_path)
    assert counted == [] and not (tmp_path / "poc6_04").exists()


def test_row_structure_mismatch_stops_before_training(tmp_path, monkeypatch, counted):
    w = build_world(tmp_path, monkeypatch, drop_date_for=FOUR[1])
    counted.clear()
    folder, rep = RU.run(w["manifest"], tmp_path)
    assert rep["status"] == RU.CHECK_REQUIRED and counted == []
    assert any(
        p.startswith("B ") for p in rep["problems"]
    )  # 행 수 · 적격에서 먼저 멈춤
    assert "c12" not in rep and (folder / "report.md").exists()


def test_compare_structure_catches_same_count_different_rows():
    base = {
        "blocks": [("d1", "d9")],
        "etfs": {
            "X": [
                {"train": ["a", "b"], "test": [("t1", "e1", "s1"), ("t2", "e2", "s2")]}
            ]
        },
    }
    moved = json.loads(json.dumps(base))
    moved["etfs"]["X"][0]["test"][1] = ["t3", "e3", "s3"]  # 행 수 같고 날짜만 다름
    base_t = json.loads(json.dumps(base))
    assert K.compare_structure(base_t, base_t, ["X"], "A 대 B") == []
    probs = K.compare_structure(base_t, moved, ["X"], "A 대 B")
    assert probs and probs[0].startswith("A 대 B")
    win = json.loads(json.dumps(base))
    win["etfs"]["X"][0]["test"][0] = ["t1", "e9", "s1"]  # 목표 창 끝만 다름
    assert K.compare_structure(base_t, win, ["X"], "A 대 B")
    tr = json.loads(json.dumps(base))
    tr["etfs"]["X"][0]["train"] = ["a"]
    assert any("학습" in x for x in K.compare_structure(base_t, tr, ["X"], "B 대 C"))


def test_c_count_other_than_expected_stops(tmp_path, monkeypatch, counted):
    w = build_world(tmp_path, monkeypatch, c_etfs=12)
    counted.clear()
    _, rep = RU.run(w["manifest"], tmp_path)
    assert rep["status"] == RU.CHECK_REQUIRED and counted == []
    assert any("C 적격" in p for p in rep["problems"])


@pytest.mark.parametrize("method", [S.MEDIAN, S.RIDGE])
def test_control_over_tolerance_is_check_required(tmp_path, monkeypatch, method):
    w = build_world(tmp_path, monkeypatch)
    real = S.run_cpu
    seen = []

    def nudged(snap, **k):
        out = real(snap, **k)
        seen.append(1)
        if len(seen) == 2:  # C 만 · 공통 4종 MEDIAN 을 1e-9 흔듦
            for blk in out["rows_by_block"]:
                for r in blk:
                    if r["ticker"] == FOUR[0]:
                        r["preds"][method] += 1e-9
        return out

    monkeypatch.setattr(S, "run_cpu", nudged)
    _, rep = RU.run(w["manifest"], tmp_path)
    assert rep["status"] == RU.CHECK_REQUIRED and "대조군" in rep["reason"]
    assert rep["control"]["over_tolerance_rows"] > 0 and "c12" not in rep


def test_compare_values_catches_feature_or_truth_difference():
    rows = {t: _rows(_walk(s)) for s, t in enumerate(FOUR, start=3)}
    prep_b = S.prepare(_snap(rows))
    assert K.compare_values(prep_b, S.prepare(_snap(rows)), FOUR) == []
    moved = json.loads(json.dumps(rows))
    moved[FOUR[2]][300][1] *= 1.01  # 학습 구간 한 날 종가만 다름(행 구조는 같음)
    probs = K.compare_values(prep_b, S.prepare(_snap(moved)), FOUR)
    assert probs and all(FOUR[2] in x and "feature · 정답 다름" in x for x in probs)


def test_check_shapes_catches_same_count_train_or_value_difference():
    """700일(학습 행 여유) — 학습 구간 하루가 빠져도 적격 · 행 수는 그대로이고 학습 날짜만 달라진다."""
    d7 = _weekdays("2022-06-01", 700)
    n7 = len(d7)

    def rows(seed, source=NAVER):
        return _rows(_walk(seed, n7), d7, source=source)

    def brk(seed):
        r = _rows(_walk(seed, n7), d7, source=FDR)
        r[n7 - 190][4] += 0.01  # 1구간 시험 창을 막는 경계
        return r

    def snap(e):
        return _snap(e, d7)

    four = {t: rows(s) for s, t in enumerate(FOUR, start=3)}
    mon_break = {t: brk(s) for s, t in enumerate(MONTHLY, start=11)}
    mon_clean = {t: rows(s, FDR) for s, t in enumerate(MONTHLY, start=11)}
    prep_a = S.prepare(snap({**four, **mon_break}))
    expect = {"b_etfs": 4, "c_etfs": 6, "dates_per_block": 63}
    inp = {"four": FOUR}
    ok_b = S.prepare(snap(four))
    ok_c = S.prepare(snap({**four, **mon_clean}))
    assert prep_a["eligible"] == FOUR
    assert RU._check_shapes(prep_a, ok_b, ok_c, inp, expect) == []
    # 학습 구간 한 날 종가 없음 → 적격 · 시험 행 수는 같고 학습 행 날짜만 다름(A 대 B)
    gap = json.loads(json.dumps(four))
    gap[FOUR[0]][100][1] = None
    probs = RU._check_shapes(
        prep_a,
        S.prepare(snap(gap)),
        S.prepare(snap({**gap, **mon_clean})),
        inp,
        expect,
    )
    assert any(x.startswith("A 대 B") and "학습" in x for x in probs)
    # C 의 공통 종목 값만 다름(구조 같음) → B 대 C feature · 정답
    moved = json.loads(json.dumps(four))
    moved[FOUR[1]][300][1] *= 1.01
    probs = RU._check_shapes(
        prep_a, ok_b, S.prepare(snap({**moved, **mon_clean})), inp, expect
    )
    assert probs and all(x.startswith("B 대 C") for x in probs)


def test_verdict_labels_and_base_zero():
    def sc(h, m, r, hb=(1, 1, 1), mb=(2, 2, 2), rb=(2, 2, 2)):
        return {
            S.HGB: {"overall": h, "blocks": list(hb)},
            S.MEDIAN: {"overall": m, "blocks": list(mb)},
            S.RIDGE: {"overall": r, "blocks": list(rb)},
        }

    assert K.verdict(sc(1.0, 2.0, 2.0))["label"] == K.LABEL_MET
    assert K.verdict(sc(1.99, 2.0, 2.0))["label"] == K.LABEL_NOT_MET
    zero = K.verdict(sc(1.0, 0.0, 2.0, mb=(0, 0, 0)))
    assert zero["label"] == K.LABEL_NOT_MET and zero["reasons"]
    assert (
        K.direction(sc(1.0, 2.0, 2.0)) is True
        and K.direction(sc(3.0, 2.0, 2.0)) is False
    )


def test_window_end_is_last_day_of_full_window_and_truth_diff_units():
    prep = {"dates": DATES[:30]}
    ends = K.window_end(prep)
    assert ends[DATES[0]] == DATES[20] and ends[DATES[9]] == DATES[29]
    assert DATES[10] not in ends  # 뒤로 20거래일이 없는 날은 목표 창 없음
    ra = [[{"id": "a", "truth": -0.05}, {"id": "b", "truth": -0.010}]]
    rb = [[{"id": "a", "truth": -0.0495}, {"id": "b", "truth": -0.012}]]
    td = K.truth_diff(ra, rb)
    assert td["over_0_001"] == 1 and td["max_abs"] == pytest.approx(0.002)
    assert td["unit"].startswith("수익률")


def test_krx_rate_is_mismatch_over_compared_pairs():
    basis = {
        "per_ticker": {
            "X": {
                "krx": {
                    "match": 30,
                    "mismatch": 10,
                    "not_comparable": {"A": 5, "B": 1},
                    "a_over_c": {"first": {"date": "d0"}, "last": {"date": "d1"}},
                }
            }
        }
    }
    k = K.krx_rates(basis, ["X"])["X"]
    assert k["mismatch_rate"] == pytest.approx(0.25) and k["not_comparable"] == 6
    assert (k["observed_from"], k["observed_to"]) == ("d0", "d1")


def test_output_failure_leaves_no_partial(tmp_path, monkeypatch):
    w = build_world(tmp_path, monkeypatch)
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setattr(RU, "RESEARCH_ROOT", blocker / "poc6_04")
    with pytest.raises(RU.SaveError):
        RU.run(w["manifest"], tmp_path)
    monkeypatch.setattr(RU, "RESEARCH_ROOT", tmp_path / "late")
    monkeypatch.setattr(
        RU.os, "rename", lambda a, b: (_ for _ in ()).throw(OSError("x"))
    )
    with pytest.raises(RU.SaveError):
        RU.run(w["manifest"], tmp_path)
    assert not list((tmp_path / "late").iterdir())


def test_copy_from_other_snapshot_is_check_required(tmp_path, monkeypatch):
    w = build_world(tmp_path, monkeypatch)
    db = w["files"]["copy_db"]
    con = sqlite3.connect(db)
    con.execute("UPDATE meta SET value = '\"other\"' WHERE key = 'snapshot_digest'")
    con.commit()
    con.close()
    m = json.loads(json.dumps(w["manifest"]))
    m["files"]["copy_db"]["sha256"] = _sha(db)
    with pytest.raises(IN.InputError, match="digest"):
        RU.run(m, tmp_path)


def test_cli_run_uses_manifest(tmp_path, monkeypatch):
    from scripts.run_d20_expanded_check import main

    w = build_world(tmp_path, monkeypatch)
    monkeypatch.setattr(IN, "MANIFEST", w["manifest"])
    monkeypatch.setattr(IN, "PROJECT_ROOT", tmp_path)
    assert main(["run"]) == 0
    bad = json.loads(json.dumps(w["manifest"]))
    bad["files"]["a_report"]["sha256"] = "1" * 64
    monkeypatch.setattr(IN, "MANIFEST", bad)
    assert main(["run"]) == 2


def test_frozen_a_copy_hash_mismatch_fails_without_partial(tmp_path, monkeypatch):
    w = build_world(tmp_path, monkeypatch)

    real = IN.sha256_file

    def lying(path):
        return "0" * 64 if Path(path).name == "a_report_frozen.json" else real(path)

    monkeypatch.setattr(
        IN, "sha256_file", lying
    )  # 저장한 고정 사본의 해시가 다르게 보이면
    with pytest.raises(RU.SaveError, match="고정 사본"):
        RU.run(w["manifest"], tmp_path)
    assert not list((tmp_path / "poc6_04").glob("*"))


def test_one_test_date_missing_but_eligible_stops_on_row_count(
    tmp_path, monkeypatch, counted
):
    """T 의 종가 하나만 없음 → 그 종목 3구간 마지막 시험 날짜 하나만 빠짐(적격 유지) → 행 수에서 멈춤."""
    w = build_world(tmp_path, monkeypatch, drop_date_for=FOUR[1], drop_date=T)
    counted.clear()
    _, rep = RU.run(w["manifest"], tmp_path)
    assert rep["status"] == RU.CHECK_REQUIRED and counted == []
    assert "B 3구간 시험 행 251 ≠ 252" in rep["problems"]
    assert not any("적격" in x for x in rep["problems"])


def test_structure_detects_window_end_and_feature_start_on_real_axis():
    """실제 축으로 — 그 칸 하나만 다르게(시험 · 학습 날짜는 같게) 만들어 각각 잡히는지."""
    rows = {t: _rows(_walk(s)) for s, t in enumerate(FOUR, start=3)}
    prep = S.prepare(_snap(rows))
    i_start = prep["blocks"][0][0] - S.LB  # 1구간 첫 시험 행의 feature 창 시작

    def variant(change_at=None):
        out = {**prep, "dates": list(prep["dates"]), "etfs": {}}
        # i_start 를 학습 표본에서 빼 '창 시작'으로만 쓰이게
        for t, e in prep["etfs"].items():
            out["etfs"][t] = {**e, "_valid": [i for i in e["_valid"] if i != i_start]}
        if change_at is not None:
            out["dates"][change_at] += "X"
        return out

    base = K.structure(variant(), FOUR)
    last = len(prep["dates"]) - 1  # T = 마지막 시험 행의 목표 창 끝으로만 쓰임
    for k in (last, i_start):
        probs = K.compare_structure(base, K.structure(variant(k), FOUR), FOUR, "A 대 B")
        assert probs and all("시험 행 · 목표 창 · feature 창" in x for x in probs), k


def test_compare_values_truth_only_change():
    rows = {t: _rows(_walk(s)) for s, t in enumerate(FOUR, start=3)}
    moved = json.loads(json.dumps(rows))
    # T 종가를 절반으로 = 마지막 시험 행의 정답(20일 최저)에만 쓰임(feature 무관)
    moved[FOUR[3]][-1][1] *= 0.5
    probs = K.compare_values(S.prepare(_snap(rows)), S.prepare(_snap(moved)), FOUR)
    assert probs and all(FOUR[3] in x for x in probs)


def _rewrite_a(w, fn):
    path = w["files"]["a_report"]
    body = json.loads(path.read_text(encoding="utf-8"))
    fn(body)
    path.write_text(json.dumps(body), encoding="utf-8")
    m = json.loads(json.dumps(w["manifest"]))
    m["files"]["a_report"]["sha256"] = _sha(path)
    return m


def test_a_row_ids_differ_is_check_required(tmp_path, monkeypatch):
    w = build_world(tmp_path, monkeypatch)

    def swap(b):
        blk = b["rows_by_block"][0]
        blk[0], blk[1] = blk[1], blk[0]

    _, rep = RU.run(_rewrite_a(w, swap), tmp_path)
    assert rep["status"] == RU.CHECK_REQUIRED
    assert "A 대 B 시험 행 ID 다름" in rep["problems"]


def test_a_not_cpu_stage_or_other_environment_is_check_required(tmp_path, monkeypatch):
    w = build_world(tmp_path, monkeypatch)
    m = _rewrite_a(w, lambda b: b.update(stage="MERGED"))
    with pytest.raises(IN.InputError, match="CPU 결과"):
        RU.run(m, tmp_path)
    m = _rewrite_a(w, lambda b: b.update(stage="CPU"))

    def other_env():
        return {"python": "3.0.0", "libraries": {"scikit-learn": "0.1"}}

    monkeypatch.setattr(IN.env, "environment", other_env)
    with pytest.raises(IN.InputError, match="계산 환경"):
        RU.run(m, tmp_path)


def test_prepare_error_is_check_required_and_monthly_must_be_in_c(
    tmp_path, monkeypatch
):
    w = build_world(tmp_path, monkeypatch, monthly=[MONTHLY[0], SHORT])
    _, rep = RU.run(w["manifest"], tmp_path)
    assert rep["status"] == RU.CHECK_REQUIRED
    assert any("월 분배" in x and SHORT in x for x in rep["problems"])

    def boom(snap):
        raise S.StudyError("손상")

    monkeypatch.setattr(S, "prepare", boom)
    with pytest.raises(IN.InputError, match="snapshot 준비"):
        RU.run(w["manifest"], tmp_path)


def test_any_save_exception_leaves_no_partial(tmp_path, monkeypatch):
    w = build_world(tmp_path, monkeypatch)
    from app.d20_expand import render

    def broken(r):
        raise KeyError("x")

    monkeypatch.setattr(render, "render_md", broken)
    with pytest.raises(KeyError):
        RU.run(w["manifest"], tmp_path)
    assert not [p for p in (tmp_path / "poc6_04").iterdir()]


def test_direction_overall_and_block():
    sc = {
        S.HGB: {"overall": 1.0, "blocks": [1.0, 1.0, 3.0]},
        S.MEDIAN: {"overall": 2.0, "blocks": [2.0, 2.0, 2.0]},
        S.RIDGE: {"overall": 2.0, "blocks": [2.0, 2.0, 2.0]},
    }
    assert K.direction(sc) is True and K.direction(sc, block=2) is False


def test_direction_inputs_are_wired_to_the_right_tables(tmp_path, monkeypatch):
    """방향 함수가 어느 표(행 수)와 구간으로 불렸는지 — 보조 (b) 는 거른 3구간 값이어야 한다."""
    w = build_world(tmp_path, monkeypatch)
    monkeypatch.setattr(
        K, "direction", lambda sc, block=None: f"{block}:{sc[S.HGB]['rows']}"
    )
    _, rep = RU.run(w["manifest"], tmp_path)
    assert rep["directions"] == {
        "main_overall": f"None:{3 * 63 * 6}",
        "main_block3": f"2:{3 * 63 * 6}",
        "aux_a_overall": f"None:{3 * 63 * 4}",
        "aux_b_block3": f"None:{47 * 6}",
    }
