"""POC7-01 즉시 참여 · 한 주 보류 비교 — 가짜 봉인 DB(tmp) 시험. 라이브 DB · 봉인 DB 를 열지 않는다."""

from __future__ import annotations

import contextlib
import copy
import csv
import json
import math
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from app.entry_timing import classify as CL
from app.entry_timing import data as DA
from app.entry_timing import flow as FW
from app.entry_timing import protocol as P
from app.entry_timing import study as ST
from app.entry_timing import verify as VR
from app.entry_timing import verify_calc as VC
from app.entry_timing import weekly as WK
from app.entry_timing.protocol import BASE_COST, CheckRequired, Config, dumps
from tests import _krx_fixture as KF

NOW = datetime(2026, 11, 22, 3, 0, tzinfo=timezone.utc)

# --- 파일 열기 · 폴더 목록 읽기 감시(검증자 r6 F13 · Python 감사 훅) -----------------------
_WATCH: list = []
_SEEN: list = []


def _audit(event, args):
    if not _WATCH or event not in ("open", "os.listdir", "os.scandir") or not args:
        return
    a = args[0]
    if not isinstance(a, (str, bytes, os.PathLike)):
        return
    q = os.fsdecode(a)
    if any(q == w or q.startswith(w + os.sep) for w in _WATCH):
        _SEEN.append((event, q))


sys.addaudithook(_audit)


@contextlib.contextmanager
def _no_touch(*paths):
    """이 경로들(밖 위치 · 밖을 가리키는 링크 이름) 아래를 열거나 목록을 읽으면 기록한다."""
    _SEEN.clear()
    _WATCH[:] = [os.fspath(x) for x in paths]
    try:
        yield _SEEN
    finally:
        _WATCH.clear()


CSV_ROWS = [
    ("코스피 200", "국내", "주식"),
    ("S&P 500", "해외", "주식"),
    ("KIS 국고채 3년", "국내", "채권"),
    ("FnGuide 미국 테크", "해외", "주식"),
]
DATES = KF.trading_dates(60, start=20210104)  # 2021-01-04 월 ~ 12 주
SPEC = {
    # code: (이름, 지수명, 하루 수익률)
    "069500": ("KODEX 200", "코스피 200", 0.001),
    "A00001": ("TEST A", "코스피 200", 0.003),
    "B00001": ("TEST B", "S&P 500", 0.004),
    "C00001": ("TEST C", "KRX300 헬스케어", 0.002),
    "D00001": ("TEST D", "FnGuide 화학 지수", 0.005),
    "E00001": ("TEST 인버스", "코스피 200", 0.006),
    "G00001": ("TEST G", "코스피 고정", 0.0),
    "H00001": ("TEST H", "코스피 하락 A", -0.004),
    "I00001": ("TEST I", "코스피 하락 B", -0.003),
}


def _write_csv(path: Path) -> Path:
    with open(path, "w", encoding="cp949", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["기초지수명", "기초시장분류", "기초자산분류"])
        w.writerows(CSV_ROWS)
    return path


def _make_db(tmp_path: Path, *, end_d: int = 40, patch=None) -> tuple[Path, str]:
    maps = []
    for code, (name, idx, r) in SPEC.items():
        n = end_d if code == "D00001" else len(DATES)
        closes = [round(10000 * (1 + r) ** k, 4) for k in range(n)]
        rows = KF.series_rows(code, DATES[:n], closes, name=name)
        for row in rows.values():
            row["IDX_IND_NM"] = idx
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
        csv_path=_write_csv(tmp_path / "basic.csv"),
        csv_sha=None,
        root=tmp_path / "out",
        spans={
            "main": ("2021-01-01", "2021-12-31"),
            "aux": ("2014-01-01", "2020-12-31"),
        },
        subs=(
            ("2021-01-01", "2021-02-15"),
            ("2021-02-16", "2021-03-01"),
            ("2021-03-02", "2021-12-31"),
        ),
        expected=None,
        cross_check_poc6=False,
    )
    base.update(kw)
    return Config(**base)


def _row(by_date, code, d):
    return next(r for r in by_date[d] if r["ISU_CD"] == code)


def _failed(rec):
    return sorted(c["name"] for c in rec["checks"] if not c["ok"])


@pytest.fixture
def world(tmp_path):
    db, content = _make_db(tmp_path)
    return tmp_path, db, content


# --- 분류 ---------------------------------------------------------------------


def test_classify_three_labels_and_dictionary_precedence(tmp_path):
    dic = CL.load_dictionary(_write_csv(tmp_path / "b.csv"))
    assert CL.label("코스피 200", dic)[0] == CL.OFF_DE
    assert CL.label("FnGuide 미국 테크", dic)[0] == CL.OFF_NOT  # 사전이 낱말보다 먼저
    assert CL.label("KRX300 헬스케어", dic)[0] == CL.EST_DE
    assert CL.label("KAP 단기채권 지수(총수익)", dic)[0] == CL.EST_NOT
    assert CL.label("MSCI China NTR Index", dic)[0] == CL.EST_NOT
    assert CL.label("FnGuide 화학 지수", dic) == (CL.UNKNOWN, CL.REASON["provider"])
    conflict = CL.label("Dow Jones Internet Korea Tilted Index(PR)", dic)
    assert conflict == (CL.UNKNOWN, CL.REASON["conflict"])
    assert CL.label("FnKorea 50 지수", dic)[0] == CL.UNKNOWN  # 제공사 이름 안의 Korea
    assert CL.label("STOXX USA ETF Industry Index (KRW)", dic)[0] == CL.UNKNOWN  # 'US '
    assert CL.label("코스피 200 선물지수", dic)[0] == CL.EST_NOT
    assert CL.label("", dic)[0] == CL.UNKNOWN
    assert CL.is_domestic_equity(CL.EST_DE, "MAIN")
    assert not CL.is_domestic_equity(CL.EST_DE, "OFFICIAL")
    bad = tmp_path / "bad.csv"
    with open(bad, "w", encoding="cp949", newline="") as fh:
        csv.writer(fh).writerows(
            [
                ["기초지수명", "기초시장분류", "기초자산분류"],
                ["X", "국내", "주식"],
                ["X", "해외", "주식"],
            ]
        )
    with pytest.raises(CheckRequired):
        CL.load_dictionary(bad)


# --- 주 기록 ------------------------------------------------------------------


def test_week_reconstruction_follows_operating_rule(world):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content)
    panel = DA.load(cfg)
    dic = CL.load_dictionary(cfg.csv_path)
    weeks = WK.build(panel, dic, cfg)
    first = weeks[0]
    assert first["D"] == "2021-02-05"  # D − 30일이 축 처음 이후인 첫 금요일
    assert first["start"] == "2021-01-06"  # 2021-02-05 − 30일 이후 첫 축 날짜
    assert (first["e1"], first["e2"], first["gap_days"]) == (
        "2021-02-08",
        "2021-02-15",
        5,
    )
    codes = [x[1] for x in first["top"]]
    assert "E00001" not in codes  # 이름 '인버스' 제외
    assert codes == ["D00001", "B00001", "A00001", "C00001", "069500"] + [
        "G00001",
        "I00001",
        "H00001",
    ]
    cand = first["variants"]["MAIN"]["candidates"]
    assert [c[1] for c in cand] == codes[2:]  # 국내 주식형만
    assert [c[0] for c in cand] == [3, 4, 5, 6, 7, 8]  # 원래 순위 유지
    assert [c[1] for c in first["variants"]["OFFICIAL"]["candidates"]] == [
        "A00001",
        "069500",
    ]
    assert first["unknown_top"] == [[1, "D00001", True]]  # 나중에 사라진 상품
    assert first["denominator"] == {
        "official": 1,
        "estimated": 4,
        "unknown": 1,
        "unknown_reasons": {CL.REASON["provider"]: 1},
    }
    assert first["next_top"] == codes  # D' 의 상위 30
    assert first["variants"]["MAIN"]["abstain"]  # 지수 < 30 → 규칙 없음 → 즉시
    assert first["variants"]["MAIN"]["decision"] == WK.IMMEDIATE
    assert weeks[-1]["D"] == "2021-03-12"  # D'+1 이 축 안에 있는 주만
    table = WK.classification_table(panel, dic)
    assert sorted(table) == [
        "FnGuide 화학 지수",
        "KRX300 헬스케어",
        "코스피 고정",
        "코스피 하락 A",
        "코스피 하락 B",
    ]
    assert WK.table_counts(table)["UNKNOWN"] == 1
    cnt = WK.counts(panel, weeks, cfg.spans)["main"]
    assert cnt["MAIN"]["next_week_dropout_pairs"] == 0
    assert cnt["MAIN"]["excluded"]["BENCH_NOT_EXEC"] == 0
    assert cnt["preopen_unavailable_weeks"] == 0


def _pop(rets_by_index):
    out = []
    for k, (idx, rets) in enumerate(rets_by_index.items()):
        for m, r in enumerate(rets):
            out.append((-r, f"{k:03d}{m}", k, idx, CL.OFF_DE, r, CL.REASON["official"]))
    return out


def test_breadth_votes_threshold_and_futures_excluded():
    downs = {f"코스피 테스트 {k}": [-0.01] for k in range(16)}
    ups = {f"코스피 테스트 {k}": [0.01] for k in range(16, 31)}
    v = WK._votes(_pop({**downs, **ups}), "MAIN")
    assert (v["votes"], v["up"], v["decision"]) == (31, 15, WK.HOLD)  # 15/31 < 0.5
    ups[f"코스피 테스트 {31}"] = [0.01]
    v = WK._votes(_pop({**downs, **ups}), "MAIN")
    assert (v["votes"], v["up"], v["decision"]) == (32, 16, WK.IMMEDIATE)  # 0.5 → 즉시
    mixed = {
        **downs,
        **ups,
        "코스피 200 선물지수": [0.5],
        "같은 지수": [-0.02, 0.01, 0.03],
    }
    v = WK._votes(_pop(mixed), "MAIN")
    assert (
        v["votes"] == 33 and v["up"] == 17
    )  # 선물 빠짐 · 같은 지수 = 한 표(중앙 0.01)
    few = WK._votes(_pop(dict(list(downs.items())[:10])), "MAIN")
    assert few["abstain"] and few["decision"] == WK.IMMEDIATE


def test_pair_reasons_and_shift(tmp_path):
    def patch(by_date):
        _row(by_date, "A00001", "20210208")["ACC_TRDVOL"] = "0"  # D+1 체결 불가
        _row(by_date, "C00001", "20210215")[
            "ACC_TRDVOL"
        ] = "0"  # D'+1 불가 → 다음 날 가능
        _row(by_date, "B00001", "20210210")[
            "FLUC_RT"
        ] = "9.99"  # 기준가 관계 깨짐 → 새 구간

    db, content = _make_db(tmp_path, patch=patch)
    panel = DA.load(_cfg(tmp_path, db, content))
    ci, pos = panel.ci, {d: i for i, d in enumerate(panel.axis)}
    e1, e2 = pos["2021-02-08"], pos["2021-02-15"]
    assert WK.pair(panel, ci["A00001"], e1, e2) == ("NOT_EXEC_E1", None)
    assert WK.pair(panel, ci["C00001"], e1, e2)[0] == "NOT_EXEC_E2"
    assert WK.pair(panel, ci["B00001"], e1, e2)[0] == "SEG_BREAK"
    d1, d2 = pos["2021-02-26"], pos["2021-03-05"]
    assert WK.pair(panel, ci["D00001"], d1, d2)[0] == "NO_ROW_E2"
    e, r = WK.shifted_pair(panel, ci["C00001"], e1, e2)
    assert panel.axis[e] == "2021-02-16"
    assert math.isclose(r, (1.002) ** 6, rel_tol=1e-6)  # 가짜 종가 넷째 자리 반올림
    st, r = WK.pair(panel, ci["069500"], e1, e2)
    assert st == "OK" and math.isclose(r, 1.001**5, rel_tol=1e-6)


# --- 경로 · 지표 · 판정 ----------------------------------------------------------


def test_week_values_and_flat_price_is_not_avoided_loss(world):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content)
    panel = DA.load(cfg)
    weeks = WK.build(panel, CL.load_dictionary(cfg.csv_path), cfg)
    w = copy.deepcopy(weeks[0])
    w["variants"]["MAIN"]["decision"] = WK.HOLD
    w["variants"]["MAIN"]["candidates"] = [[6, "G00001", CL.EST_DE]]  # 가격 그대로
    row = ST.week_rows(panel, [w], "MAIN", BASE_COST)[0]
    assert row["status"] == "OK"
    assert math.isclose(row["imm"], 1 / 1.002 - 1, rel_tol=1e-12)
    assert row["d_rule"] == 0.0  # 보류 − 즉시 = 0 → '피한 손실' 아님
    split = ST._split([row])
    assert (split["avoided"]["weeks"], split["zero"]["weeks"]) == (0, 1)
    w2 = copy.deepcopy(weeks[0])
    w2["variants"]["MAIN"]["decision"] = WK.HOLD
    w2["variants"]["MAIN"]["candidates"] = [[3, "A00001", CL.OFF_DE]]
    r2 = ST.week_rows(panel, [w2], "MAIN", BASE_COST)[0]
    imm = r2["pairs"][0][2] / 1.002 - 1
    assert math.isclose(r2["d_rule"], (1 / 1.002 - 1) - imm, rel_tol=1e-12)
    assert r2["g_rule"] == 1.0 and r2["d_rule"] < 0  # 오르는 후보를 기다림 = 놓친 상승
    assert ST._split([r2])["missed"]["weeks"] == 1


def test_bootstrap_keeps_calendar_slots():
    slots = [None if k % 4 == 1 else ((k * 37) % 11 - 5) / 1000 for k in range(30)]
    a = ST.bootstrap(slots)
    good = [x for x in slots if x is not None]
    assert a["n_slots"] == 30 and a["n_valid"] == 22
    assert math.isclose(a["mean"], sum(good) / len(good), rel_tol=1e-12)
    rng = np.random.default_rng(ST.SEED)
    starts = rng.integers(0, 30, size=(ST.DRAWS, 3))
    means = []
    for row in starts:
        picked = [slots[(b + t) % 30] for b in row for t in range(ST.BLOCK_WEEKS)][:30]
        ok = [x for x in picked if x is not None]
        means.append(sum(ok) / len(ok))
    lo, hi = np.percentile(means, [2.5, 97.5])
    assert math.isclose(a["lo"], lo, rel_tol=1e-12)
    assert math.isclose(a["hi"], hi, rel_tol=1e-12)
    assert VC.bootstrap(slots, ST.METHOD) == pytest.approx(a)
    dense = ST.bootstrap(good)
    assert (dense["lo"], dense["hi"]) != (a["lo"], a["hi"])  # 빈 자리를 지우면 달라진다


def test_mdd_gross_path():
    assert ST.mdd([1.0] * 5) == 0.0
    assert math.isclose(ST.mdd([1.1, 0.9, 0.9, 1.2]), 0.81 - 1, rel_tol=1e-12)


def _summary(**kw):
    s = {
        "counts": {
            "evaluable_weeks": 100,
            "cand_weeks": 100,
            "pairs": 500,
            "pairs_ok": 500,
            "hold_weeks": 30,
        },
        "delta": {"mean": 0.001, "lo": 0.0001},
        "rule_minus_hold": {"mean": 0.001, "lo": 0.0001},
        "hold_week_gain": 0.003,
        "sub_wins": 2,
        "downturn": {"delta": 0.0},
        "mdd": {"rule": -0.1, "immediate": -0.2},
    }
    s.update(kw)
    return s


GOOD7 = {"main": 0.001, "official": 0.0005}
_C = _summary()["counts"]
CASES = [
    ("A", _summary(), GOOD7, []),
    ("D", _summary(counts={**_C, "evaluable_weeks": 79}), GOOD7, None),
    ("D", _summary(counts={**_C, "pairs_ok": 399}), GOOD7, None),
    ("C", _summary(delta={"mean": 0.0, "lo": -1}), GOOD7, None),
    ("C", _summary(mdd={"rule": -0.3, "immediate": -0.2}), GOOD7, None),
    (
        "B",
        _summary(rule_minus_hold={"mean": 0.001, "lo": -0.0001}),
        GOOD7,
        ["3_rule_beats_always_hold"],
    ),
    ("B", _summary(), {"main": 0.001, "official": -0.0001}, ["7_official_same_sign"]),
    (
        "A",
        _summary(),
        {"main": -0.001, "official": -0.0005},
        [],
    ),  # 같은 부호(PLAN 문구)
    ("B", _summary(counts={**_C, "hold_weeks": 25}), GOOD7, ["6_hold_weeks"]),
    ("B", _summary(downturn={"delta": None}), GOOD7, ["5_downturn_ge_0"]),
    ("B", _summary(hold_week_gain=0.0019), GOOD7, ["2_hold_week_gain"]),
    ("B", _summary(sub_wins=1), GOOD7, ["4_sub_wins"]),
    ("B", _summary(delta={"mean": 0.001, "lo": 0.0}), GOOD7, ["1_ci_lower_gt_0"]),
]


@pytest.mark.parametrize("status,s,c7,failed", CASES)
def test_judge_order_and_conditions_match_verify(status, s, c7, failed):
    got = ST.judge(s, c7)
    assert got["status"] == status
    if failed is not None:
        assert got.get("failed", []) == failed
    assert got == VC.judge(s, c7)  # 검산의 따로 쓴 판정과 같다


def test_judge_note_whenever_criterion_3_fails():
    s = _summary(
        rule_minus_hold={"mean": 0.001, "lo": -0.0001},
        counts={**_C, "hold_weeks": 1},
    )
    assert ST.judge(s, GOOD7)["note"]


def test_dumps_rejects_nan_and_expected_exact_passes():
    with pytest.raises(CheckRequired):
        dumps({"x": float("nan")})
    FW.check_expected({"main": {"weeks": 3}}, {"main": {"weeks": 3}})
    with pytest.raises(CheckRequired):
        FW.check_expected({"main": {"weeks": 3}}, {"main": {"weeks": 4}})


# --- 잠금 · 공식 실행 · 검산 ----------------------------------------------------


def _out(cfg, lock_id, run_id):
    return Path(cfg.root) / lock_id / "runs" / run_id


def _fix_manifest(out, name, data):
    """변조자가 해시 목록 · 완료 기록 해시까지 맞춘 경우(재계산 대조만으로 잡혀야 함)."""
    (out / name).write_bytes(data)
    run_json = json.loads((out / "run.json").read_text(encoding="utf-8"))
    run_json["manifest"][name] = VR.store.sha256_bytes(data)
    _rewrite_run_json(out, run_json)


def _rewrite_run_json(out, run_json):
    raw = dumps(run_json)
    (out / "run.json").write_bytes(raw)
    done = json.loads((out / "completed.json").read_text(encoding="utf-8"))
    done["run_json_sha256"] = VR.store.sha256_bytes(raw)
    (out / "completed.json").write_bytes(dumps(done))


def test_prepare_run_verify_once_and_tamper_detected(world):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content, cross_check_poc6=True)
    lock = FW.prepare(cfg, NOW)
    with pytest.raises(CheckRequired):
        FW.prepare(cfg, NOW)  # 잠금은 하나(정정은 사유 필요)
    run = FW.run(cfg, NOW)
    assert run["status"] == "OK" and run["lock_id"] == lock["lock_id"]
    with pytest.raises(CheckRequired):
        FW.run(cfg, NOW)  # 공식 실행 1회
    out = _out(cfg, lock["lock_id"], run["run_id"])
    rep = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert rep["result"]["judgment"]["status"] == "C"  # 지수 < 30 → 늘 즉시 → Δ = 0
    rec = json.loads((out / "weeks.json").read_text(encoding="utf-8"))
    assert (
        rec[0]["availability"] == "공개 일정상 D+1 08:00 · 과거 실제 수신 시각 미확인"
    )
    proto = json.loads((Path(cfg.root) / lock["lock_id"] / "protocol.json").read_text())
    assert proto["classification"]["FnGuide 화학 지수"][0] == CL.UNKNOWN
    v = VR.verify(cfg, NOW)
    assert v["status"] == "VERIFIED_OK", _failed(v)
    assert any(c["name"] == "poc6_build_panel_cells" and c["ok"] for c in v["checks"])
    # 주 기록을 바꾸고 해시 목록까지 맞춰도 독립 재계산이 잡는다
    rec[0]["variants"]["MAIN"]["result_20bp"]["imm"] += 1e-6
    _fix_manifest(out, "weeks.json", dumps(rec))
    plain = _cfg(tmp_path, db, content)
    assert _failed(VR.verify(plain, NOW)) == ["weeks_recomputed"]
    # 판정을 바꾸고 해시 목록을 맞춰도 잡는다(결과 · 판정 · 글)
    rep["result"]["judgment"]["status"] = "A"
    _fix_manifest(out, "report.json", dumps(rep))
    assert _failed(VR.verify(plain, NOW)) == [
        "judgment",
        "report_json_recomputed",
        "weeks_recomputed",
    ]


def test_hold_path_end_to_end_verified(world, monkeypatch):
    tmp_path, db, content = world
    monkeypatch.setattr(P, "MIN_VOTES", 1)
    monkeypatch.setattr(WK, "MIN_VOTES", 1)
    cfg = _cfg(tmp_path, db, content)
    FW.prepare(cfg, NOW)
    run = FW.run(cfg, NOW)
    lock_dir, _ = FW.active_lock(Path(cfg.root))
    rep = json.loads((lock_dir / "runs" / run["run_id"] / "report.json").read_text())
    s = rep["result"]["primary"]
    assert s["counts"]["hold_weeks"] == 6  # MAIN: 지수 5 중 오른 지수 2 → 보류
    assert s["delta"]["mean"] > 0 and s["mdd"]["rule"] == 0.0
    assert rep["result"]["official_compare"]["decisions_differ"] == 6  # 공식만: 즉시
    j = rep["result"]["judgment"]
    assert j["status"] == "B" and "7_official_same_sign" in j["failed"] and j["note"]
    assert rep["result"]["worked_case"]["decision"] == "HOLD"
    v = VR.verify(cfg, NOW)
    assert v["status"] == "VERIFIED_OK", _failed(v)


def test_verify_catches_shifted_fill_dates(world, monkeypatch):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content)
    real = WK.build

    def late(panel, dictionary, c):  # 매수일을 D+2 로 잘못 잡은 구현
        weeks = real(panel, dictionary, c)
        for w in weeks:
            w["e1_pos"] += 1
            w["e1"] = panel.axis[w["e1_pos"]]
        return weeks

    monkeypatch.setattr(WK, "build", late)
    FW.prepare(cfg, NOW)
    FW.run(cfg, NOW)
    monkeypatch.setattr(WK, "build", real)
    rec = VR.verify(cfg, NOW)
    assert rec["status"] == "MISMATCH"
    assert "weeks_recomputed" in _failed(rec)
    assert "report_json_recomputed" in _failed(rec)
    assert "lock_weeks_sha" in _failed(rec)


def test_lock_chain_order_correction_and_preflight(world, monkeypatch):
    tmp_path, db, content = world
    ids = iter(["20261122T030000Z_ffffffff", "20261122T030000Z_00000000"])
    monkeypatch.setattr(FW, "new_id", lambda now: next(ids))
    cfg = _cfg(tmp_path, db, content)
    with pytest.raises(CheckRequired, match="첫 잠금"):
        FW.prepare(cfg, NOW, correction_reason="없음")
    first = FW.prepare(cfg, NOW)
    other = _cfg(tmp_path, db, content, subs=(("2021-01-01", "2021-12-31"),) * 3)
    with pytest.raises(CheckRequired, match="recipe"):
        FW.run(other, NOW)  # 실행 전 거부 — 기록 없음 · 실행 기회 남음
    assert not (Path(cfg.root) / first["lock_id"] / "runs").exists()
    real_hashes = FW.code_hashes
    monkeypatch.setattr(FW, "code_hashes", lambda repo: {"x": "y"})
    with pytest.raises(CheckRequired, match="코드 해시"):
        FW.run(cfg, NOW)
    monkeypatch.setattr(FW, "code_hashes", real_hashes)
    with pytest.raises(CheckRequired, match="실행이 있을 때만"):
        FW.prepare(cfg, NOW, correction_reason="결함")
    monkeypatch.setattr(FW, "new_id", lambda now: "20261122T030000Z_11111111")
    FW.run(cfg, NOW)
    monkeypatch.setattr(FW, "new_id", lambda now: "20261122T030000Z_00000000")
    with pytest.raises(CheckRequired, match="코드 · 환경이 앞 잠금과 같다"):
        FW.prepare(cfg, NOW, correction_reason="결함")
    changed = {**real_hashes(cfg.repo), "app/entry_timing/study.py": "0" * 64}
    monkeypatch.setattr(FW, "code_hashes", lambda repo: changed)
    fix = FW.prepare(cfg, NOW, correction_reason="결함")
    assert fix["corrects"]["changed_code"] == ["app/entry_timing/study.py"]
    assert fix["corrects"]["prior_runs"] == ["20261122T030000Z_11111111"]
    order = [p["lock_id"] for _, p in FW.locks(Path(cfg.root))]
    assert order == [first["lock_id"], fix["lock_id"]]  # 이름 순서와 반대여도 사슬 순서
    assert FW.active_lock(Path(cfg.root))[1]["lock_id"] == fix["lock_id"]


def test_lock_folder_and_fork_rejected(world):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content)
    lock = FW.prepare(cfg, NOW)
    root = Path(cfg.root)
    src = root / lock["lock_id"] / "protocol.json"
    (root / "copy").mkdir()
    (root / "copy" / "protocol.json").write_bytes(src.read_bytes())
    with pytest.raises(CheckRequired, match="폴더 이름"):
        FW.locks(root)
    (root / "copy" / "protocol.json").unlink()
    (root / "copy").rmdir()
    (root / lock["lock_id"]).rename(root / "renamed")  # 중복 없이 이름만 다름
    with pytest.raises(CheckRequired, match="폴더 이름"):
        FW.locks(root)
    (root / "renamed").rename(root / lock["lock_id"])
    proto = json.loads(src.read_text())
    for k in ("A", "B"):  # 같은 잠금을 둘이 정정
        lid = f"20261122T030000Z_aaaaaaa{k}"
        (root / lid).mkdir()
        fork = {**proto, "lock_id": lid, "corrects": {"lock_id": lock["lock_id"]}}
        (root / lid / "protocol.json").write_bytes(dumps(fork))
    with pytest.raises(CheckRequired, match="사슬"):
        FW.locks(root)
    (root / "20261122T030000Z_aaaaaaaB" / "protocol.json").write_text("{broken")
    with pytest.raises(CheckRequired, match="읽을 수 없음"):
        FW.locks(root)


def test_budget_write_failure_and_interrupt_leave_failed_record(world, monkeypatch):
    tmp_path, db, content = world
    tight = _cfg(tmp_path, db, content, root=tmp_path / "t", budget_s=0.0)
    lock = FW.prepare(tight, NOW)
    with pytest.raises(CheckRequired, match="시간 예산"):
        FW.run(tight, NOW)
    runs = list((Path(tight.root) / lock["lock_id"] / "runs").iterdir())
    names = sorted(p.name for p in runs[0].iterdir())
    assert names == [
        "report.json",
        "report.md",
        "run.json",
        "weeks.json",
    ]  # 결과 파일 뒤 판정
    assert json.loads((runs[0] / "run.json").read_text())["status"] == "FAILED"
    with pytest.raises(CheckRequired, match="FAILED"):
        VR.verify(tight, NOW)  # run.json 이 FAILED 면 결과 파일이 있어도 성립하지 않음
    with pytest.raises(CheckRequired):
        FW.run(tight, NOW)  # 실패도 1회
    cfg = _cfg(tmp_path, db, content, root=tmp_path / "w")
    lock = FW.prepare(cfg, NOW)
    real = FW.write_once

    def boom(root, path, data):
        if Path(path).name == "report.json":
            raise OSError("disk")
        return real(root, path, data)

    monkeypatch.setattr(FW, "write_once", boom)
    with pytest.raises(OSError):
        FW.run(cfg, NOW)
    run_json = next((Path(cfg.root) / lock["lock_id"] / "runs").glob("*/run.json"))
    assert json.loads(run_json.read_text())["status"] == "FAILED"
    monkeypatch.setattr(FW, "write_once", real)
    ki = _cfg(tmp_path, db, content, root=tmp_path / "k")
    lock = FW.prepare(ki, NOW)

    def stop(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(ST, "evaluate", stop)
    with pytest.raises(KeyboardInterrupt):
        FW.run(ki, NOW)
    run_json = next((Path(ki.root) / lock["lock_id"] / "runs").glob("*/run.json"))
    assert json.loads(run_json.read_text())["status"] == "FAILED"
    with pytest.raises(CheckRequired):
        FW.run(ki, NOW)  # 중단 뒤에도 같은 잠금으로 다시 실행하지 않음


def test_prepare_blocks_on_expected_mismatch(world):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content, expected={"main": {"weeks": 999}})
    with pytest.raises(CheckRequired, match="PLAN §1-4"):
        FW.prepare(cfg, NOW)
    assert not list(Path(cfg.root).glob("*/protocol.json"))


# --- 검증자 r1 F1 ~ F4 재현(합성 봉인 DB · 정상 실행 뒤 기록을 바꿈) ---------------------------


def _ok_run(tmp_path, db, content, name):
    cfg = _cfg(tmp_path, db, content, root=tmp_path / name)
    lock = FW.prepare(cfg, NOW)
    run = FW.run(cfg, NOW)
    return (
        cfg,
        Path(cfg.root) / lock["lock_id"],
        _out(cfg, lock["lock_id"], run["run_id"]),
    )


def test_f1_run_record_manifest_and_judgment_tied(world):
    tmp_path, db, content = world
    cfg, _lock_dir, out = _ok_run(tmp_path, db, content, "f1a")
    run_json = json.loads((out / "run.json").read_text(encoding="utf-8"))
    run_json["manifest"] = {}
    run_json["judgment"] = "A"
    _rewrite_run_json(out, run_json)
    failed = _failed(VR.verify(cfg, NOW))
    assert "run_manifest_complete" in failed and "judgment" in failed


def test_f1_report_json_whole_and_markdown_from_recomputed(world):
    tmp_path, db, content = world
    cfg, _lock_dir, out = _ok_run(tmp_path, db, content, "f1b")
    rep = json.loads((out / "report.json").read_text(encoding="utf-8"))
    rep["states"]["adoption"] = "채택"
    rep["counts"]["main"]["pairs_official"] += 100
    rep["lock_id"] = "20990101T000000Z_deadbeef"
    _fix_manifest(out, "report.json", dumps(rep))
    _fix_manifest(out, "report.md", VR.RP.markdown(rep).encode("utf-8"))
    failed = _failed(VR.verify(cfg, NOW))
    assert "report_json_recomputed" in failed and "report_md_rendered" in failed


def test_f1_lock_recipe_counts_and_hash_recomputed(world):
    tmp_path, db, content = world
    cfg, lock_dir, _out_dir = _ok_run(tmp_path, db, content, "f1c")
    proto = json.loads((lock_dir / "protocol.json").read_text(encoding="utf-8"))
    proto["recipe"]["breadth"]["threshold"] = 0.7
    proto["counts"]["main"]["pairs_official"] += 100
    proto["inputs"]["weeks_sha256"] = "0" * 64
    (lock_dir / "protocol.json").write_bytes(dumps(proto))
    failed = _failed(VR.verify(cfg, NOW))
    assert {"lock_recipe", "lock_counts", "lock_weeks_sha"} <= set(failed)


def test_f2_weekly_records_carry_denominator(world, monkeypatch):
    tmp_path, db, content = world
    cfg, _lock_dir, out = _ok_run(tmp_path, db, content, "f2a")
    rec = json.loads((out / "weeks.json").read_text(encoding="utf-8"))
    assert all(
        set(r["denominator"]) == {"official", "estimated", "unknown", "unknown_reasons"}
        for r in rec
    )
    real = VR.RP.week_records

    def drop(weeks, rows):
        out_ = real(weeks, rows)
        for r in out_:
            r.pop("denominator")
        return out_

    monkeypatch.setattr(VR.RP, "week_records", drop)
    cfg2 = _cfg(tmp_path, db, content, root=tmp_path / "f2b")
    FW.prepare(cfg2, NOW)
    FW.run(cfg2, NOW)
    # 기록 함수가 빠뜨린 채로 검산해도 잡는다(검산은 따로 만든 기록 생성기를 쓴다)
    assert "weeks_recomputed" in _failed(VR.verify(cfg2, NOW))


class _Clock:
    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        return self.t


@pytest.mark.parametrize("where", ["run_summary", "report_md"])
def test_f3_budget_covers_final_writes_and_summary(world, monkeypatch, where):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content, root=tmp_path / f"f3{where}", budget_s=1.0)
    lock = FW.prepare(cfg, NOW)
    clock = _Clock()
    monkeypatch.setattr(FW, "time", types.SimpleNamespace(monotonic=clock.monotonic))
    real_dumps, real_write = FW.dumps, FW.write_once

    def slow_dumps(obj):
        if (
            where == "run_summary"
            and isinstance(obj, dict)
            and obj.get("status") == "OK"
        ):
            clock.t += 2.0
        return real_dumps(obj)

    def slow_write(root, path, data):
        if where == "report_md" and Path(path).name == "report.md":
            clock.t += 2.0
        return real_write(root, path, data)

    monkeypatch.setattr(FW, "dumps", slow_dumps)
    monkeypatch.setattr(FW, "write_once", slow_write)
    with pytest.raises(CheckRequired, match="시간 예산"):
        FW.run(cfg, NOW)
    run_json = next((Path(cfg.root) / lock["lock_id"] / "runs").glob("*/run.json"))
    assert json.loads(run_json.read_text())["status"] == "FAILED"
    with pytest.raises(CheckRequired, match="FAILED"):
        VR.verify(cfg, NOW)


def test_f4_interrupt_while_writing_run_json_leaves_failed(world, monkeypatch):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content, root=tmp_path / "f4")
    lock = FW.prepare(cfg, NOW)
    real_put = P._put

    def cut(fh, data):
        if ".run.json." in fh.name and b'"status": "OK"' in data:
            fh.write(data[:17])
            raise KeyboardInterrupt
        real_put(fh, data)

    monkeypatch.setattr(P, "_put", cut)
    with pytest.raises(KeyboardInterrupt):
        FW.run(cfg, NOW)
    run_dir = next((Path(cfg.root) / lock["lock_id"] / "runs").iterdir())
    assert json.loads((run_dir / "run.json").read_text())["status"] == "FAILED"
    assert not [p.name for p in run_dir.iterdir() if p.name.endswith(".tmp")]
    with pytest.raises(FileExistsError):
        P.write_once(cfg.root, run_dir / "run.json", b"x")  # 한 번만


# --- 검증자 r2 F5 · F6 재현 ----------------------------------------------------------------


def test_f5_budget_covers_final_run_json_write(world, monkeypatch):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content, root=tmp_path / "f5a", budget_s=1.0)
    lock = FW.prepare(cfg, NOW)
    clock = _Clock()
    monkeypatch.setattr(FW, "time", types.SimpleNamespace(monotonic=clock.monotonic))
    real_put = P._put

    def slow(fh, data):
        if ".run.json." in fh.name and b'"status": "OK"' in data:
            clock.t += 2.0  # 마지막 성공 기록의 임시 파일 쓰기가 상한을 넘김
        real_put(fh, data)

    monkeypatch.setattr(P, "_put", slow)
    with pytest.raises(CheckRequired, match="시간 예산"):
        FW.run(cfg, NOW)
    run_dir = next((Path(cfg.root) / lock["lock_id"] / "runs").iterdir())
    assert json.loads((run_dir / "run.json").read_text())["status"] == "FAILED"
    assert not [p.name for p in run_dir.iterdir() if p.name.endswith(".tmp")]
    with pytest.raises(CheckRequired, match="FAILED"):
        VR.verify(cfg, NOW)


@pytest.mark.parametrize("bad", [-1, False, "0", float("inf")])
def test_f5_elapsed_must_be_real_nonnegative_number(world, bad):
    tmp_path, db, content = world
    cfg, _lock_dir, out = _ok_run(tmp_path, db, content, f"f5b{bad!r}"[:12])
    run_json = json.loads((out / "run.json").read_text(encoding="utf-8"))
    run_json["elapsed_s"] = bad
    text = json.dumps(run_json, ensure_ascii=False, sort_keys=True, indent=1)
    (out / "run.json").write_text(text + "\n", encoding="utf-8")  # inf 는 dumps 가 거부
    assert "elapsed_within_budget" in _failed(VR.verify(cfg, NOW))


def test_f6_two_runs_in_one_lock_rejected(world):
    tmp_path, db, content = world
    cfg, lock_dir, out = _ok_run(tmp_path, db, content, "f6")
    twin = lock_dir / "runs" / "20990101T000000Z_00000001"
    twin.mkdir()
    rep = json.loads((out / "report.json").read_text(encoding="utf-8"))
    rep["run_id"] = twin.name
    data = {
        "weeks.json": (out / "weeks.json").read_bytes(),
        "report.json": dumps(rep),
        "report.md": VR.RP.markdown(rep).encode("utf-8"),
    }
    for k, v in data.items():
        (twin / k).write_bytes(v)
    run_json = json.loads((out / "run.json").read_text(encoding="utf-8"))
    run_json["run_id"] = twin.name
    run_json["manifest"] = {k: VR.store.sha256_bytes(v) for k, v in data.items()}
    raw = dumps(run_json)
    (twin / "run.json").write_bytes(raw)
    done = json.loads((out / "completed.json").read_text(encoding="utf-8"))
    done.update(run_id=twin.name, run_json_sha256=VR.store.sha256_bytes(raw))
    (twin / "completed.json").write_bytes(dumps(done))
    assert _failed(VR.verify(cfg, NOW)) == ["single_run_in_lock"]  # 기본 = 마지막 실행
    first = VR.verify(cfg, NOW, run_id=out.name)
    assert _failed(first) == ["single_run_in_lock"]


# --- 검증자 r3 F7 ~ F9 재현 ----------------------------------------------------------------


def test_f7_budget_counts_until_run_json_is_named(world, monkeypatch):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content, root=tmp_path / "f7", budget_s=1.0)
    lock = FW.prepare(cfg, NOW)
    clock = _Clock()
    monkeypatch.setattr(FW, "time", types.SimpleNamespace(monotonic=clock.monotonic))
    real_link = P._link

    def slow_link(src, dst):
        if Path(dst).name == "run.json":
            clock.t += 2.0  # 이름 붙이기가 끝나기 전에 상한을 넘김
        real_link(src, dst)

    monkeypatch.setattr(P, "_link", slow_link)
    with pytest.raises(CheckRequired, match="완료"):
        FW.run(cfg, NOW)
    run_dir = next((Path(cfg.root) / lock["lock_id"] / "runs").iterdir())
    names = sorted(p.name for p in run_dir.iterdir() if not p.name.startswith("."))
    assert "budget_exceeded.json" in names and "completed.json" not in names
    failed = _failed(VR.verify(cfg, NOW))
    assert "run_completed" in failed and "run_dir_files" in failed
    with pytest.raises(CheckRequired):
        FW.run(cfg, NOW)  # 다시 실행하지 않음


def test_f8_cleanup_failure_after_link_keeps_result_consistent(world, monkeypatch):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content, root=tmp_path / "f8a")
    FW.prepare(cfg, NOW)
    real_unlink = P._unlink
    state = {"n": 0}

    def flaky(path):
        if ".run.json." in Path(path).name and state["n"] == 0:
            state["n"] += 1
            raise OSError("busy")
        real_unlink(path)

    monkeypatch.setattr(P, "_unlink", flaky)
    run = FW.run(cfg, NOW)  # 정리 실패가 결과를 바꾸지 않는다
    assert run["status"] == "OK" and state["n"] == 1
    lock_dir, _ = FW.active_lock(Path(cfg.root))
    assert (lock_dir / "runs" / run["run_id"] / "completed.json").is_file()
    assert (
        VR.verify(cfg, NOW)["status"] == "VERIFIED_OK"
    )  # 남은 숨김 임시 파일은 쓰이지 않음


def test_f8_cleanup_failure_after_budget_still_records_failed(world, monkeypatch):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content, root=tmp_path / "f8b", budget_s=1.0)
    lock = FW.prepare(cfg, NOW)
    clock = _Clock()
    monkeypatch.setattr(FW, "time", types.SimpleNamespace(monotonic=clock.monotonic))
    real_put, real_unlink = P._put, P._unlink

    def slow(fh, data):
        if ".run.json." in fh.name and b'"status": "OK"' in data:
            clock.t += 2.0
        real_put(fh, data)

    def fail_unlink(path):
        if ".run.json." in Path(path).name:
            raise OSError("busy")
        real_unlink(path)

    monkeypatch.setattr(P, "_put", slow)
    monkeypatch.setattr(P, "_unlink", fail_unlink)
    with pytest.raises(CheckRequired, match="시간 예산"):  # 원래 오류가 가려지지 않음
        FW.run(cfg, NOW)
    run_dir = next((Path(cfg.root) / lock["lock_id"] / "runs").iterdir())
    assert json.loads((run_dir / "run.json").read_text())["status"] == "FAILED"


def test_f9_explicit_run_must_be_direct_child_of_active_lock(world):
    tmp_path, db, content = world
    cfg, lock_dir, out = _ok_run(tmp_path, db, content, "f9")
    nested = out / "sub"
    nested.mkdir()
    for name in (
        "weeks.json",
        "report.json",
        "report.md",
        "run.json",
        "completed.json",
    ):
        (nested / name).write_bytes((out / name).read_bytes())
    with pytest.raises(CheckRequired, match="바로 아래"):
        VR.verify(cfg, NOW, run_id=f"{out.name}/sub")
    with pytest.raises(CheckRequired, match="바로 아래"):
        VR.verify(cfg, NOW, run_id="..")
    assert "run_dir_files" in _failed(VR.verify(cfg, NOW))  # 실행 폴더 안 하위 폴더


def test_f7_completed_record_fields_checked(world):
    tmp_path, db, content = world
    cfg, _lock_dir, out = _ok_run(tmp_path, db, content, "f7c")
    good = (out / "completed.json").read_bytes()
    done = json.loads(good)
    done["done_elapsed_s"] = 99999.0  # 완료 경과가 예산(3,600초)을 넘음
    (out / "completed.json").write_bytes(dumps(done))
    assert _failed(VR.verify(cfg, NOW)) == ["run_completed"]
    (out / "completed.json").write_bytes(good)
    (out / "run.json").write_bytes(
        (out / "run.json").read_bytes() + b" "
    )  # 완료 뒤 run.json 변경
    assert "run_completed" in _failed(VR.verify(cfg, NOW))


# --- 검증자 r4 F10 · F11 재현 --------------------------------------------------------------


def test_f10_completion_measured_at_link_not_after_cleanup(world, monkeypatch):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content, root=tmp_path / "f10", budget_s=1.0)
    FW.prepare(cfg, NOW)
    clock = _Clock()
    monkeypatch.setattr(FW, "time", types.SimpleNamespace(monotonic=clock.monotonic))
    real_link, real_unlink = P._link, P._unlink

    def link(src, dst):
        real_link(src, dst)
        if Path(dst).name == "run.json":
            clock.t = 0.75  # 이름이 예산 안(0.75초)에 붙음

    def unlink(path):
        if ".run.json." in Path(path).name and clock.t == 0.75:
            clock.t += 0.5  # 임시 이름 정리만 늦어짐
        real_unlink(path)

    monkeypatch.setattr(P, "_link", link)
    monkeypatch.setattr(P, "_unlink", unlink)
    run = FW.run(cfg, NOW)
    lock_dir, _ = FW.active_lock(Path(cfg.root))
    done = json.loads(
        (lock_dir / "runs" / run["run_id"] / "completed.json").read_text()
    )
    assert done["done_elapsed_s"] == 0.75  # 링크 직후 · 정리 전
    assert VR.verify(cfg, NOW)["status"] == "VERIFIED_OK"


def test_f11_run_behind_symlink_outside_lock_rejected(world):
    tmp_path, db, content = world
    cfg, lock_dir, out = _ok_run(tmp_path, db, content, "f11a")
    away = tmp_path / "elsewhere" / out.name
    away.parent.mkdir()
    out.rename(away)
    out.symlink_to(
        away, target_is_directory=True
    )  # 같은 이름의 링크 · 실제 실행은 잠금 밖
    failed = _failed(VR.verify(cfg, NOW))
    assert "paths_real" in failed and "single_run_in_lock" in failed
    failed_id = _failed(VR.verify(cfg, NOW, run_id=out.name))
    assert "paths_real" in failed_id


def test_f11_unknown_hidden_file_rejected_but_program_tmp_allowed(world):
    tmp_path, db, content = world
    cfg, _lock_dir, out = _ok_run(tmp_path, db, content, "f11b")
    (out / f".run.json.{'a' * 32}.tmp").write_bytes(
        b"left"
    )  # 정리 실패로 남을 수 있는 이름
    assert VR.verify(cfg, NOW)["status"] == "VERIFIED_OK"
    (out / ".note.json").write_bytes(b"{}")
    assert _failed(VR.verify(cfg, NOW)) == ["run_dir_files"]


def test_f11_symlinked_file_in_run_dir_rejected(world):
    tmp_path, db, content = world
    cfg, _lock_dir, out = _ok_run(tmp_path, db, content, "f11c")
    copy_ = tmp_path / "report_copy.md"
    copy_.write_bytes((out / "report.md").read_bytes())
    (out / "report.md").unlink()
    (out / "report.md").symlink_to(
        copy_
    )  # 바이트는 같지만 실행 폴더의 보통 파일이 아님
    with _no_touch(copy_, out / "report.md") as seen:
        rec = VR.verify(cfg, NOW)
    assert _failed(rec) == [
        "report_md_rendered",
        "run_dir_files",
        "run_manifest_complete",
    ]  # 읽지 않아 해시 · 대조도 불일치
    assert seen == []
