"""POC6-11 보고 지표 · 판정 · 실행 흐름(잠금 · 중단 · 순서 · 1회) · verify 변조 검출 — 설계 §8 · §9 · §10 · 판정 §3 · §4.

실행 흐름은 tmp_path 의 작은 봉인 DB 와 가짜 모델(LightGBM 대신 · 학습 0)로 돈다. 봉인 DB · 라이브 DB 는
열지 않는다. 기간 · 해시 · 최소 표본 상수만 이 시험용으로 바꾼다(정책 · 지표 · 판정 기준은 그대로).
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from app.ml_evidence import store
from app.weekly_selection import features as F
from app.weekly_selection import flow as FL
from app.weekly_selection import model as M
from app.weekly_selection import policy as PO
from app.weekly_selection import protocol as PR
from app.weekly_selection import report as R
from app.weekly_selection import verify as VR
from tests._krx_fixture import build_sealed_db, krx_row, rows_by_date

REPO = Path(__file__).resolve().parents[1]


# ── 지표 · 판정(손계산) ──────────────────────────────────────────────────────────


def _led(vals, start="2021-01-04"):
    d0 = dt.date.fromisoformat(start)
    return [
        {
            "date": (d0 + dt.timedelta(days=k)).isoformat(),
            "value": v,
            "cash": v,
            "pos": {},
        }
        for k, v in enumerate(vals)
    ]


def test_period_cagr_mdd_recovery_hand_calc():
    led = _led([100, 110, 99, 105, 111, 90])
    r = R.period(led, "2021-01-04", 100.0)
    assert r["return"] == pytest.approx(-0.10)
    assert r["cagr"] == pytest.approx(0.9 ** (365.25 / 5) - 1)
    assert r["mdd"] == pytest.approx(90 / 111 - 1)
    assert (r["mdd_peak"], r["mdd_trough"], r["not_recovered"]) == (
        "2021-01-08",
        "2021-01-09",
        True,
    )
    r2 = R.period(_led([100, 110, 99, 111]), "2021-01-04", 100.0)
    assert r2["mdd"] == pytest.approx(99 / 110 - 1) and r2["recovered"] == "2021-01-07"


def test_subperiod_base_is_previous_value_no_restart():
    led = _led([100, 120, 90, 108])
    subs = R.subperiods(
        led,
        "2021-01-04",
        100.0,
        (("2021-01-04", "2021-01-05"), ("2021-01-06", "2021-01-07")),
    )
    assert subs[0]["return"] == pytest.approx(0.2) and subs[0]["base_value"] == 100.0
    assert subs[1]["base_date"] == "2021-01-05" and subs[1]["return"] == pytest.approx(
        108 / 120 - 1
    )


def test_turnover_formula():
    led = _led([100.0] * 366)
    bk = {
        "fills": [
            {"side": "BUY", "notional": 300.0, "intent": 1},
            {"side": "SELL", "notional": 300.0},
        ],
        "intents": [{"id": 1, "side": "BUY", "signal": "x"}],
        "plans": [{"signal": "x"}],
    }
    t = R.turnover(bk, led, "2021-01-04")
    years = 365 / 365.25
    assert t["annual"] == pytest.approx(600 / (2 * 100 * years))
    assert t["annual_ex_first_plan"] == pytest.approx(300 / (2 * 100 * years))


def test_bootstrap_deterministic_and_interval():
    d = list(np.linspace(-0.01, 0.02, 60))
    a, b = R.bootstrap(d), R.bootstrap(d)
    assert a == b and a["weeks"] == 60 and a["ci95"][0] < a["mean_diff"] < a["ci95"][1]
    assert R.bootstrap([0.001] * 30)["uncertain"] is False


def test_bootstrap_uses_13_week_circular_blocks():
    d = (
        [1.0] * 13 + [-1.0] * 13
    ) * 4  # 13주 덩어리 자기상관 — 1주 추출이면 구간이 절반 폭
    b = R.bootstrap(d)
    assert 0.6 < b["ci95"][1] - b["ci95"][0] < 1.2
    assert b["ci95"] == pytest.approx(
        [-0.40384615384615385, 0.4230769230769231]
    )  # seed 20261026 고정


def test_weekly_returns_excludes_incomplete_tail():
    led = _led([100, 101, 102, 103, 104])
    w, tail = R.weekly_returns(led, {"2021-01-05", "2021-01-07"}, 100.0)
    assert [x for x, _ in w] == ["2021-01-05", "2021-01-07"] and tail == 1
    assert w[1][1] == pytest.approx(103 / 101 - 1)


def _met(cagr, mdd, subs=(0.0, 0.0, 0.0), to=1.0):
    return {
        "total": {"cagr": cagr, "mdd": mdd},
        "subperiods": [{"return": s} for s in subs],
        "turnover": {"annual": to},
    }


def _test(  # 기본값 = 네 기준의 정확한 경계(부동소수로 정확히 표현되는 값)
    lc=0.01,
    bc=0.0,
    kc=-0.05,
    lm=-0.05,
    bm=0.0,
    km=0.0,
    ls=(0.1, 0.1, -0.1),
    bs=(0, 0, 0),
    to=6.0,
    l4=0.005,
    b4=0.0,
):
    return {
        "L_20": _met(lc, lm, ls, to),
        "B_20": _met(bc, bm, bs),
        "K_20": _met(kc, km),
        "L_40": _met(l4, lm),
        "B_40": _met(b4, bm),
    }


def test_judge_boundaries():
    boot = {"uncertain": True}
    j = R.judge("OK", _test(), boot)  # 1%p 차 · MDD 5%p 차 · 회전율 6 정확히 = 통과
    assert (j["h1"], j["candidate"], j["uncertainty"]) == (
        "PRICE_GAIN_OBSERVED",
        "FURTHER_REVIEW_CANDIDATE",
        "UNCERTAIN",
    )
    assert R.judge("OK", _test(lc=0.00999), boot)["h1"] == "PRICE_GAIN_NOT_SHOWN"
    assert (
        R.judge("OK", _test(ls=(0.1, -0.1, 0.0)), boot)["h1"] == "PRICE_GAIN_NOT_SHOWN"
    )
    j = R.judge("OK", _test(kc=0.02), boot)
    assert j["h1"] == "PRICE_GAIN_OBSERVED" and j["candidate"] == "NOT_CANDIDATE"
    assert j["reasons"] == ["L_NOT_ABOVE_K"]
    r = R.judge("OK", _test(lm=-0.0501), boot)["reasons"]
    assert r == ["MDD_WORSE_THAN_B", "MDD_WORSE_THAN_K"]
    assert R.judge("OK", _test(to=6.0001), boot)["reasons"] == ["TURNOVER_ABOVE_6"]
    assert R.judge("OK", _test(l4=0.0), boot)["reasons"] == ["COST_SENSITIVE_40BP"]
    assert (
        R.judge("OK", _test(), {"uncertain": False})["uncertainty"]
        == "CI_EXCLUDES_ZERO"
    )
    for st in ("CHECK_REQUIRED", "DATA_SHORT", "BUDGET_STOP"):
        j = R.judge(st, None, None)
        assert (j["h1"], j["candidate"], j["OPERATION_ADOPTION"]) == (
            "NOT_JUDGED",
            "NOT_JUDGED",
            "NO",
        )


def test_select_tie_prefers_ml_a_and_mom20():
    v = {
        k: {"total": {"cagr": c}}
        for k, c in (
            ("ML_A", 0.1),
            ("ML_B", 0.1 + 1e-13),
            ("MOM20", 0.2),
            ("MOM120", 0.2 + 2e-12),
        )
    }
    s = R.select(v)
    assert (s["L"], s["B"]) == ("ML_A", "MOM120")


# ── 실행 흐름(작은 봉인 DB · 가짜 모델) ────────────────────────────────────────────


def _bdays(first: str, last: str, holidays=()):
    d, end = dt.date.fromisoformat(first), dt.date.fromisoformat(last)
    out = []
    while d <= end:
        if d.weekday() < 5 and d.isoformat() not in holidays:
            out.append(d.strftime("%Y%m%d"))
        d += dt.timedelta(days=1)
    return out


@pytest.fixture(scope="module")
def sealed(tmp_path_factory):
    rng = np.random.default_rng(20261026)
    days = _bdays("2015-01-02", "2017-06-30", holidays=("2016-07-01",))
    maps = []
    for k in range(26):
        code = "069500" if k == 0 else f"{100000 + k}"
        name = "KODEX 200" if k == 0 else f"TEST ETF {k}"
        c, prev, rows = 10000.0, None, {}
        for d in days:
            o = round(c * (1 + rng.normal(0, 0.003)))
            c = max(1000.0, round(c * (1 + rng.normal(0.0003, 0.015))))
            row = krx_row(
                code, d, c, prev, volume=20000 + int(rng.integers(0, 5000)), name=name
            )
            row.update(
                TDD_OPNPRC=f"{o:g}",
                TDD_HGPRC=f"{max(o, c) + 30:g}",
                TDD_LWPRC=f"{min(o, c) - 30:g}",
            )
            rows[d] = row
            prev = c
        maps.append(rows)
    path = tmp_path_factory.mktemp("poc611") / "krx.sqlite"
    sha = build_sealed_db(path, rows_by_date(*maps))
    return path, sha, store.sha256_file(path)


class _Booster:
    def __init__(self, struct):
        self.struct = struct

    def predict(self, X, num_threads=None):
        k = F.COLUMNS.index("RET_20" if self.struct == "ML_A" else "RET_5")
        return np.nan_to_num(X[:, k]) * (1.0 if self.struct == "ML_A" else -1.0)


def _lgb_str(v):
    """LightGBM 모델 원문의 매개변수 표기 흉내(참거짓 = 1/0 · regression_l2 = regression)."""
    if isinstance(v, bool):
        return "1" if v else "0"
    return {"regression_l2": "regression"}.get(v, str(v))


def _text(b):
    pr = {**M.params(b.struct), "num_iterations": M.NUM_ROUNDS}
    body = "\n".join(f"[{k}: {_lgb_str(v)}]" for k, v in pr.items())
    return f"FAKE {b.struct}\nparameters:\n{body}\nend of parameters\n"


class _Clock:
    def __init__(self):
        self.t = dt.datetime(2026, 10, 26, tzinfo=dt.timezone.utc)

    def __call__(self):
        self.t += dt.timedelta(seconds=1)
        return self.t


@pytest.fixture
def study(sealed, monkeypatch, tmp_path):
    path, content, file_sha = sealed
    monkeypatch.setattr(PR, "FILE_SHA", file_sha)
    monkeypatch.setattr(PR, "CONTENT_SHA", content)
    monkeypatch.setattr(PR, "VAL_RANGE", ("2016-01-01", "2016-06-30"))
    monkeypatch.setattr(PR, "TEST_RANGE", ("2016-07-01", "2017-06-30"))
    monkeypatch.setattr(
        PR,
        "SUB_RANGES",
        (
            ("2016-07-01", "2016-10-31"),
            ("2016-11-01", "2017-02-28"),
            ("2017-03-01", "2017-06-30"),
        ),
    )
    monkeypatch.setattr(PR, "VAL_Q", ((2016, 1), (2016, 2)))
    monkeypatch.setattr(PR, "TEST_Q", ((2016, 3), (2017, 2)))
    monkeypatch.setattr(PR, "MIN_WEEKS", {"val": 1, "test": 1, "sub": 1})
    monkeypatch.setattr(PR, "MIN_TRAIN_WEEKS", 1)
    monkeypatch.setattr(PR, "MIN_TRAIN_ROWS", 1)
    monkeypatch.setattr(M, "train", lambda struct, X, y, w: _Booster(struct))
    monkeypatch.setattr(M, "to_text", _text)
    monkeypatch.setattr(M, "restore", lambda text: _Booster(text.split()[1]))
    monkeypatch.setattr(M, "env", lambda: {"lightgbm": M.LGB_VERSION, "fake": True})
    monkeypatch.setattr(
        FL, "runtime_env", lambda: {"lightgbm": M.LGB_VERSION, "fake": True}
    )
    monkeypatch.setattr(
        M, "openmp_problem", lambda order=None: None
    )  # 가짜 모델 = OpenMP 미사용
    from app.weekly_selection import data as D

    p = D.build_panel(path, PR.VERSION, content)
    fx, *_ = PR.survey(p)
    monkeypatch.setattr(
        PR,
        "EXPECTED",
        {k: fx[k] for k in ("eligible_rows", "fits", "val", "sub_weeks")},
    )
    return {
        "root": tmp_path / "poc6_11",
        "db": path,
        "clock": _Clock(),
        "fx": fx,
        "sha": (content, file_sha),
    }


def _run(s):
    FL.prepare(s["root"], s["db"], REPO, s["clock"])
    return FL.run(s["root"], s["db"], REPO, s["clock"])


def _rdir(s, res):
    return next(s["root"].glob(f"*/runs/{res['meta']['run_id']}"))


def test_study_facts_mirror_the_real_q3_shape(study):
    fx = study["fx"]
    # 검증 마지막 거래일 = 그 주 마지막 거래일 = 시험 첫 계획 신호 = 시험 첫 분기 cutoff(판정 §4)
    assert fx["val"]["end"] == "2016-06-30" == fx["test"]["first_signal"]
    assert fx["quarter_detail"]["test"][0]["cutoff"] == "2016-06-30"
    assert fx["assign"]["2016-06-30"] == "2016Q3"  # cutoff = D 판을 쓴다
    assert (
        "2016-06-30" not in fx["val"]["plan_signals"]
    )  # 검증 곡선에는 실행 밖 신호 없음
    assert fx["fits"] == 2 * 2 + 4


def test_run_ok_order_and_verify(study):
    res = _run(study)
    assert res["meta"]["status"] == "OK", res["report"].get("stop")
    rdir = _rdir(study, res)
    recs = [json.loads(f.read_text()) for f in sorted((rdir / "models").glob("*.json"))]
    sel = json.loads((rdir / "selection.json").read_text())
    val = [r for r in recs if r["phase"] == "val"]
    test = [r for r in recs if r["phase"] == "test"]
    assert (
        len(val) == 4 and len(test) == 4 and {r["struct"] for r in test} == {sel["L"]}
    )  # 추가 fit 0
    when = store.parse_iso(sel["selected_at"])
    assert all(store.parse_iso(r["predicted_at"]) < when for r in val)
    assert all(store.parse_iso(r["train_started_at"]) > when for r in test)
    assert res["report"]["validation_signal_after_end"] == ["2016-06-30"]
    j = res["report"]["judgment"]
    assert j["validity"] == "OK" and j["h1"] in (
        "PRICE_GAIN_OBSERVED",
        "PRICE_GAIN_NOT_SHOWN",
    )
    assert (j["OPERATION_ADOPTION"], j["TOTAL_RETURN_VALIDATED"]) == ("NO", "NO")
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert out["status"] == "OK", out["problems"][:5]
    with pytest.raises(PR.Refused):
        FL.run(study["root"], study["db"], REPO, study["clock"])  # 1회 규칙
    with pytest.raises(PR.Refused):
        FL.prepare(study["root"], study["db"], REPO, study["clock"])


def _break(curve):
    orig = PO.simulate

    def sim(*a, **k):
        bk = orig(*a, **k)
        if bk.curve == curve:
            bk.status = "CHECK_REQUIRED"
            bk.unresolved = {
                "first_unresolved": "2016-01-04",
                "items": [{"cause": "TEST"}],
            }
            bk.end = {"stopped_at": bk.ledger[-1]["date"]}
        return bk

    return sim


def test_validation_check_required_stops_before_selection(study, monkeypatch):
    monkeypatch.setattr(PO, "simulate", _break("ML_B"))
    res = _run(study)
    rdir = _rdir(study, res)
    assert (
        res["meta"]["status"] == "CHECK_REQUIRED"
        and res["report"]["judgment"]["h1"] == "NOT_JUDGED"
    )
    assert not (rdir / "selection.json").exists() and not (rdir / "test").exists()
    assert sorted(f.name for f in (rdir / "validation").iterdir()) == [
        "ML_A.json",
        "ML_B.json",
    ]  # 나머지 미실행
    assert all(
        json.loads(f.read_text())["phase"] == "val"
        for f in (rdir / "models").glob("*.json")
    )
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert out["run_status"] == "CHECK_REQUIRED" and out["status"] == "OK", out[
        "problems"
    ][:5]


def test_test_check_required_is_not_judged_and_skips_40bp(study, monkeypatch):
    monkeypatch.setattr(PO, "simulate", _break("B_20"))
    res = _run(study)
    rdir = _rdir(study, res)
    assert res["meta"]["status"] == "CHECK_REQUIRED"
    assert (
        res["report"]["judgment"]["candidate"] == "NOT_JUDGED"
        and res["report"]["selection"]
    )
    assert sorted(f.name for f in (rdir / "test").iterdir()) == [
        "B_20.json",
        "L_20.json",
    ]


def test_budget_stop_is_recorded(study, monkeypatch):
    monkeypatch.setattr(PR, "BUDGET_S", 3)
    res = _run(study)
    rdir = _rdir(study, res)
    assert (
        res["meta"]["status"] == "BUDGET_STOP" and "BudgetStop" in res["report"]["stop"]
    )
    assert json.loads((rdir / "run.json").read_text())["status"] == "BUDGET_STOP"
    assert res["report"]["judgment"]["h1"] == "NOT_JUDGED"


def test_failure_after_run_id_is_recorded(study, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("시험 실패")

    monkeypatch.setattr(R, "select", boom)
    with pytest.raises(RuntimeError):
        _run(study)
    run = next(study["root"].glob("*/runs/*/run.json"))
    meta = json.loads(run.read_text())
    assert meta["status"] == "FAILED" and "시험 실패" in meta["reason"]
    assert (run.parent / "predictions_validation.json").exists()  # 부분 산출물 보존


def test_lock_mismatch_refuses(study, monkeypatch):
    monkeypatch.setattr(
        PR, "EXPECTED", {"eligible_rows": study["fx"]["eligible_rows"] + 1}
    )
    with pytest.raises(PR.CheckRequired):
        FL.prepare(study["root"], study["db"], REPO, study["clock"])
    monkeypatch.setattr(PR, "EXPECTED", {"eligible_rows": study["fx"]["eligible_rows"]})
    FL.prepare(study["root"], study["db"], REPO, study["clock"])
    monkeypatch.setattr(PR, "code_hashes", lambda repo: {"changed": "x"})
    with pytest.raises(PR.CheckRequired):
        FL.run(study["root"], study["db"], REPO, study["clock"])
    monkeypatch.setattr(M, "env", lambda: {"lightgbm": None})
    with pytest.raises(PR.CheckRequired):  # 환경 확인 전 잠금 금지
        FL.prepare(study["root"] / "other", study["db"], REPO, study["clock"])


def _tamper(path: Path, fn, manifest=True):
    """변조 뒤 run.json 해시 목록도 맞춰 고친다(해시 목록이 아닌 내용 검사로 잡는지 본다)."""
    data = json.loads(path.read_text())
    fn(data)
    path.write_text(json.dumps(data, ensure_ascii=False))
    if manifest and path.name not in ("run.json", "protocol.json"):
        run = next(p for p in path.parents if (p / "run.json").exists()) / "run.json"
        meta = json.loads(run.read_text())
        meta["files"] = PR.manifest(run.parent)
        run.write_text(json.dumps(meta, ensure_ascii=False))


def test_verify_detects_file_change_by_manifest(study):
    res = _run(study)
    rdir = _rdir(study, res)
    _tamper(
        rdir / "schedule_test.json",
        lambda d: d[0].update(trained_at=d[0]["trained_at"]),
        manifest=False,
    )
    (rdir / "models" / "extra.txt").write_text("x")
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert "산출물 해시 ≠ run.json 목록" in out["problems"]


def test_schedule_links_model_cutoff_and_times(study):
    res = _run(study)
    rdir = _rdir(study, res)
    sch = json.loads((rdir / "schedule_test.json").read_text())
    first = sch[0]
    assert (first["signal"], first["exec_date"], first["cutoff"]) == (
        "2016-06-30",
        "2016-07-05",
        "2016-06-30",
    )
    assert first["model"].startswith("2016Q3_") and store.parse_iso(first["trained_at"])
    assert all(x["cutoff"] <= x["signal"] for x in sch)
    _tamper(rdir / "schedule_test.json", lambda d: d[0].update(cutoff="2016-07-01"))
    assert (
        "schedule_test.json ≠ 모델 기록"
        in VR.verify(study["root"], study["db"], repo=REPO)["problems"]
    )


def test_run_refuses_when_recipe_differs_from_lock(study, monkeypatch):
    """잠근 뒤 설정(보유 한도 · 정답 기간 · 학습 반복 · 기간)을 바꾸면 실행 id 를 만들기 전에 거부(검증 r1 F1)."""
    FL.prepare(study["root"], study["db"], REPO, study["clock"])
    for mod, attr, val in (
        (PO, "SLOTS", 4),
        (F, "HORIZON", 59),
        (M, "NUM_ROUNDS", 299),
        (PR, "SUB_RANGES", (("2016-07-01", "2016-11-30"),) + PR.SUB_RANGES[1:]),
    ):
        with monkeypatch.context() as m:
            m.setattr(mod, attr, val)
            with pytest.raises(PR.CheckRequired, match="recipe"):
                FL.run(study["root"], study["db"], REPO, study["clock"])
    assert not list(study["root"].glob("*/runs/*"))


def test_run_stops_when_facts_differ_from_lock(study):
    """잠금 문서의 사실이 다시 센 사실과 다르면 실행 기록을 남기고 CHECK_REQUIRED(학습 0)."""
    doc = FL.prepare(study["root"], study["db"], REPO, study["clock"])
    f = study["root"] / doc["lock_id"] / "protocol.json"
    d = json.loads(f.read_text())
    d["facts"]["eligible_rows"] += 1
    f.write_text(json.dumps(d, ensure_ascii=False))
    res = FL.run(study["root"], study["db"], REPO, study["clock"])
    assert (
        res["meta"]["status"] == "CHECK_REQUIRED"
        and "잠금과 다름" in res["report"]["stop"]
    )
    rdir = _rdir(study, res)
    assert not (rdir / "models").exists() and not (rdir / "features.json.gz").exists()


def _quiet_signal(rdir):
    """편입 · 이탈이 없던 시험 신호 — 점수 배율을 바꿔도 장부가 같은 곳(복원 예측 대조만 잡는다)."""
    bk = json.loads((rdir / "test" / "L_20.json").read_text())
    used = {it["signal"] for it in bk["intents"]}
    return next(
        pl["signal"]
        for pl in bk["plans"]
        if not pl["entries"] and not pl["exits"] and pl["signal"] not in used
    )


@pytest.mark.parametrize(
    "target",
    [
        "fill_price",
        "prediction",
        "prediction_scale",
        "prediction_file_only",
        "intent_model",
        "judgment",
        "selection",
        "selection_consistent",
    ],
)
def test_verify_detects_tampering(study, target):
    res = _run(study)
    rdir = _rdir(study, res)
    if target == "fill_price":
        _tamper(
            rdir / "test" / "L_20.json",
            lambda d: d["fills"][0].update(price=d["fills"][0]["price"] * 1.001),
        )
    elif target == "prediction":

        def bump(d):
            sig = next(iter(next(iter(d.values()))))
            v = next(iter(d.values()))[sig]
            for c in v:
                v[c] = -v[c]

        _tamper(rdir / "predictions_test.json", bump)
    elif target == "prediction_scale":
        sig = _quiet_signal(rdir)

        def scale(d):
            v = next(iter(d.values()))[sig]
            for c in v:
                v[c] = v[c] * 2.0

        _tamper(rdir / "predictions_test.json", scale)
        rec = next(  # 모델별 예측도 같이 고쳐 '모아 쓴 파일 ≠ 모델별' 대조를 피함 → 복원 예측 대조만 남김
            f
            for f in (rdir / "models").glob("*.json")
            if sig in json.loads(f.read_text())["signals"]
        )
        _tamper(
            rec,
            lambda d: d["predictions"].update(
                {sig: {c: v * 2.0 for c, v in d["predictions"][sig].items()}}
            ),
        )
        mid = rec.stem

        def fits(d):  # 보고서의 모델 기록 사본도 같이 → 복원 예측 대조만 남김
            for r in d["fits"]:
                if r["id"] == mid:
                    r["predictions"][sig] = {
                        c: v * 2.0 for c, v in r["predictions"][sig].items()
                    }

        _tamper(rdir / "report.json", fits)
    elif target == "prediction_file_only":
        sig = _quiet_signal(rdir)

        def scale_only(d):
            v = next(iter(d.values()))[sig]
            for c in v:
                v[c] = v[c] * 2.0

        _tamper(
            rdir / "predictions_test.json", scale_only
        )  # 모델별 예측 · 장부는 그대로
    elif target == "intent_model":
        _tamper(
            rdir / "test" / "L_20.json",
            lambda d: d["intents"][0].update(model="2099Q1_ML_A"),
        )
    elif target == "selection_consistent":
        other = {}

        def flip(d):
            other["L"] = "ML_B" if d["L"] == "ML_A" else "ML_A"
            d["L"] = other["L"]

        _tamper(rdir / "selection.json", flip)
        _tamper(rdir / "report.json", lambda d: d["selection"].update(L=other["L"]))
    elif target == "judgment":
        _tamper(
            rdir / "report.json",
            lambda d: d["judgment"].update(h1="PRICE_GAIN_OBSERVED", candidate="X"),
        )
        rep = json.loads(
            (rdir / "report.json").read_text()
        )  # report.md 도 같이 → 판정 재계산만 남김
        (rdir / "report.md").write_text(R.markdown(rep))
        _tamper(rdir / "report.json", lambda d: None)  # 해시 목록 갱신
    else:
        _tamper(
            rdir / "selection.json",
            lambda d: d.update(L="ML_B" if d["L"] == "ML_A" else "ML_A"),
        )
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert out["status"] == "MISMATCH", target


def test_report_markdown_has_price_note_and_statuses(study):
    res = _run(study)
    md = (_rdir(study, res) / "report.md").read_text()
    assert "합성 가격지수의 모의 성과" in md and "OPERATION_ADOPTION = NO" in md
    assert not math.isnan(res["report"]["test"]["L_20"]["total"]["cagr"])


@pytest.mark.parametrize("limit", [4, 9, 14, 19, 24, 30, 37])
def test_stopped_runs_verify_consistently(study, monkeypatch, limit):
    """예산 정지 지점마다 — 이미 계산한 지표 · 선택이 보고에 남고 verify 가 일관(검토 r1)."""
    monkeypatch.setattr(PR, "BUDGET_S", limit)
    res = _run(study)
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert out["status"] == "OK", (
        limit,
        res["meta"]["status"],
        res["report"].get("stop"),
        out["problems"][:4],
    )
    assert out["run_status"] == res["meta"]["status"]


def test_verify_flags_code_changed_after_lock(study, monkeypatch):
    _run(study)
    assert VR.verify(study["root"], study["db"], repo=REPO)["status"] == "OK"
    monkeypatch.setattr(
        PR, "code_hashes", lambda repo: {"app/weekly_selection/policy.py": "x"}
    )
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert any("잠금 코드" in x for x in out["problems"])


# ── 실제 LightGBM(설치 뒤에만 · 가짜 자료) ─────────────────────────────────────────


REAL_LGB = os.environ.get("POC611_REAL_LGB") == "1"
real_only = pytest.mark.skipif(
    not REAL_LGB, reason="실제 LightGBM 시험은 별도 프로세스(아래 실행기)에서만"
)


def test_openmp_problem_detects_torch_first():
    hb, tc = (
        "/opt/homebrew/Cellar/libomp/23.1.4/lib/libomp.dylib",
        "/x/site-packages/torch/lib/libomp.dylib",
    )
    sk = "/x/site-packages/sklearn/.dylibs/libomp.dylib"
    assert M.openmp_problem([hb, sk, tc]) is None
    assert M.openmp_problem([sk, hb]) is None
    assert "먼저" in M.openmp_problem([tc, hb])
    assert "로드되지 않음" in M.openmp_problem([tc, sk])


def test_real_lightgbm_in_clean_process():
    """다른 시험 모듈이 torch 를 먼저 올렸을 수 있으므로(전체 회귀) 실제 학습은 새 프로세스에서."""
    pytest.importorskip("lightgbm")
    if REAL_LGB:
        pytest.skip("이미 실행기 안")
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            __file__,
            "-k",
            "real_lightgbm and not clean_process",
        ],
        cwd=REPO,
        env={**os.environ, "POC611_REAL_LGB": "1", "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert r.returncode == 0 and "2 passed" in r.stdout and "failed" not in r.stdout, (
        r.stdout[-3000:] + r.stderr[-2000:]
    )


@real_only
def test_real_lightgbm_train_save_restore_deterministic():
    assert M.openmp_problem() is None  # 실행기 프로세스 — Homebrew libomp 가 먼저
    rng = np.random.default_rng(1)
    X = rng.normal(size=(1500, len(F.COLUMNS)))
    X[rng.random(X.shape) < 0.05] = np.nan  # 결측 = NaN(0 과 구분)
    y = np.tanh(X[:, 0] - 0.5 * np.nan_to_num(X[:, 3])) * 0.5
    w = np.ones(len(y))
    for struct in ("ML_A", "ML_B"):
        b1, b2 = M.train(struct, X, y, w), M.train(struct, X, y, w)
        t1 = M.to_text(b1)
        p1 = M.predict(b1, X)
        assert np.array_equal(p1, M.predict(b2, X))  # 같은 환경 · 같은 입력 = 같은 예측
        assert np.max(np.abs(p1 - M.predict(M.restore(t1), X))) <= M.RESTORE_TOL
        rp = M.resolved_params(t1)
        want = M.params(struct)
        for k in (
            "num_leaves",
            "max_depth",
            "min_data_in_leaf",
            "max_bin",
            "seed",
            "num_threads",
        ):
            assert str(rp[k]) == str(want[k]), k
        assert rp["objective"] == "regression" and rp["deterministic"] == "1"
    assert M.loaded_libomp()  # 실제로 올라온 libomp 경로


@real_only
def test_real_lightgbm_study_run_and_verify(study, monkeypatch):
    monkeypatch.undo()  # 가짜 모델 해제 — 아래에서 필요한 상수만 다시 바꾼다
    for k, v in (
        ("FILE_SHA", study["sha"][1]),
        ("CONTENT_SHA", study["sha"][0]),
        ("VAL_RANGE", ("2016-01-01", "2016-06-30")),
        ("TEST_RANGE", ("2016-07-01", "2017-06-30")),
        (
            "SUB_RANGES",
            (
                ("2016-07-01", "2016-10-31"),
                ("2016-11-01", "2017-02-28"),
                ("2017-03-01", "2017-06-30"),
            ),
        ),
        ("VAL_Q", ((2016, 1), (2016, 2))),
        ("TEST_Q", ((2016, 3), (2017, 2))),
        ("MIN_WEEKS", {"val": 1, "test": 1, "sub": 1}),
        ("MIN_TRAIN_WEEKS", 1),
        ("MIN_TRAIN_ROWS", 1),
        ("EXPECTED", {"eligible_rows": study["fx"]["eligible_rows"]}),
    ):
        monkeypatch.setattr(PR, k, v)
    res = _run(study)
    assert res["meta"]["status"] in ("OK", "CHECK_REQUIRED"), res["report"].get("stop")
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert out["status"] == "OK", out["problems"][:5]


# ── 검증 r1 F1 · F2 와 같은 층(잠금 · run · 모델 · 보고 기록) — 해시 목록을 맞춘 의미 변조 ─────────


def _set_path(d, path, val):
    for k in path[:-1]:
        d = d[k]
    d[path[-1]] = val


def _future_cutoff(rdir):
    mid = sorted(f.stem for f in (rdir / "models").glob("*.json"))[0]
    _tamper(rdir / "models" / f"{mid}.json", lambda d: d.update(cutoff="2099-01-01"))

    def sch(rows):
        for x in rows:
            if x["model"] == mid:
                x.update(
                    cutoff="2099-01-01",
                    virtual_info_time="2099-01-01 종가 뒤(재생 가정)",
                )

    _tamper(rdir / "schedule_validation.json", sch)


def _over_budget_consistent(d):
    """마지막 단계 시각 · 경과 · 끝 시각을 모두 맞춰 예산(90분)을 넘긴 것처럼 — 예산 검사만 잡게."""
    at = store.parse_iso(d["started_at"]) + dt.timedelta(seconds=6000)
    d["stages"][-1].update(at=store.iso(at), wall_s=6000.0)
    d["finished_at"] = store.iso(at)


def _time_back(d):
    """학습 끝 시각을 시작보다 1초 앞으로 · 소요도 같이 맞춤(순서 검사만 잡게)."""
    ts = store.parse_iso(d["train_started_at"])
    d["trained_at"] = store.iso(ts - dt.timedelta(seconds=1))
    d["seconds"] = -1.0


R1_CASES = {
    "recipe_slots": (
        "lock",
        lambda d: _set_path(d, ["recipe", "policy", "slots"], 1),
        "recipe",
    ),
    "recipe_horizon": (
        "lock",
        lambda d: _set_path(d, ["recipe", "label", "horizon"], 1),
        "recipe",
    ),
    "recipe_rounds": (
        "lock",
        lambda d: _set_path(d, ["recipe", "model", "rounds"], 1),
        "recipe",
    ),
    "lock_inputs": (
        "lock",
        lambda d: _set_path(d, ["inputs", "content_sha256"], "0" * 64),
        "잠금 입력",
    ),
    "model_future_cutoff": ("special", _future_cutoff, "cutoff"),
    "model_rows0": ("model", lambda d: d.update(rows=0), "학습 행"),
    "model_weeks0": ("model", lambda d: d.update(weeks=0), "학습 행"),
    "model_signals": (
        "model",
        lambda d: d.update(signals=d["signals"][1:]),
        "배정 신호",
    ),
    "model_time_order": ("model", _time_back, "시각"),
    "model_restore_diff": (
        "model",
        lambda d: d.update(restore_max_abs_diff=1.0),
        "차이 기록",
    ),
    "run_lock_id": (
        "run",
        lambda d: d.update(lock_id="20990101T000000Z_00000000"),
        "식별자",
    ),
    "run_wall_only": ("run", lambda d: d["stages"][-1].update(wall_s=10**9), "경과"),
    "run_budget": ("run", _over_budget_consistent, "예산"),
    "report_fits": (
        "report",
        lambda d: d["fits"][0].update(cutoff="2099-01-01"),
        "fits",
    ),
    "report_after_end": (
        "report",
        lambda d: d.update(validation_signal_after_end=[]),
        "after_end",
    ),
    "report_rank_ic": (
        "report",
        lambda d: d["explain"]["rank_ic"]["L"].update(mean=0.5),
        "순위 IC",
    ),
    "report_note": ("report", lambda d: d.update(price_note="총수익"), "식별자"),
}


@pytest.mark.parametrize("case", sorted(R1_CASES))
def test_verify_rejects_semantic_tamper_with_fixed_hashes(study, case):
    kind, fn, needle = R1_CASES[case]
    res = _run(study)
    rdir = _rdir(study, res)
    assert VR.verify(study["root"], study["db"], repo=REPO)["status"] == "OK"
    if kind == "lock":
        _tamper(rdir.parents[1] / "protocol.json", fn)
    elif kind == "model":
        _tamper(sorted((rdir / "models").glob("*.json"))[0], fn)
    elif kind == "run":
        _tamper(rdir / "run.json", fn)
    elif kind == "report":
        _tamper(rdir / "report.json", fn)
    else:
        fn(rdir)
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert out["status"] == "MISMATCH" and any(
        needle in x for x in out["problems"]
    ), out["problems"][:6]


def test_verify_rejects_report_md_edit(study):
    res = _run(study)
    md = _rdir(study, res) / "report.md"
    md.write_text(md.read_text().replace("PRICE_GAIN_NOT_SHOWN", "PRICE_GAIN_OBSERVED"))
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert "report.md ≠ report.json 에서 다시 만든 보고" in out["problems"]


def test_correction_lock_keeps_prior_run_and_needs_code_change(study, monkeypatch):
    first = _run(study)
    with pytest.raises(PR.Refused):  # 정정 사유 없이 두 번째 잠금 금지
        FL.prepare(study["root"], study["db"], REPO, study["clock"])
    with pytest.raises(PR.Refused, match="같음"):  # 코드 · 환경이 같으면 정정 불필요
        FL.prepare(
            study["root"], study["db"], REPO, study["clock"], correction_reason="시험"
        )
    real = PR.code_hashes(REPO)
    changed = {**real, "app/weekly_selection/verify.py": "0" * 64}
    monkeypatch.setattr(PR, "code_hashes", lambda repo: changed)
    with monkeypatch.context() as m:  # 설정을 바꾼 정정은 거부(정정 = 코드 결함만)
        m.setattr(PO, "SLOTS", 4)
        with pytest.raises(PR.CheckRequired, match="recipe"):
            FL.prepare(
                study["root"],
                study["db"],
                REPO,
                study["clock"],
                correction_reason="시험",
            )
    doc = FL.prepare(
        study["root"],
        study["db"],
        REPO,
        study["clock"],
        correction_reason="검증 r1 F1 · F2",
    )
    assert doc["corrects"]["lock_id"] == first["meta"]["lock_id"]
    assert doc["corrects"]["changed_code"] == ["app/weekly_selection/verify.py"]
    assert doc["corrects"]["prior_runs"] == [first["meta"]["run_id"]]
    second = FL.run(study["root"], study["db"], REPO, study["clock"])
    assert (
        second["meta"]["lock_id"] == doc["lock_id"] and second["meta"]["status"] == "OK"
    )
    assert (
        study["root"]
        / first["meta"]["lock_id"]
        / "runs"
        / first["meta"]["run_id"]
        / "run.json"
    ).exists()
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert out["status"] == "OK" and out["run_id"] == second["meta"]["run_id"], out[
        "problems"
    ][:4]
    a = json.loads((_rdir(study, first) / "report.json").read_text())
    b = json.loads((_rdir(study, second) / "report.json").read_text())
    assert (a["validation"], a["test"], a["judgment"]) == (
        b["validation"],
        b["test"],
        b["judgment"],
    )


# ── 검증 r2 F3 — 필수 근거 누락(해시 목록 · report.md 를 맞춘 삭제)과 그 옆칸 ─────────────────


def _refresh_manifest(rdir):
    run = rdir / "run.json"
    meta = json.loads(run.read_text())
    meta["files"] = PR.manifest(rdir)
    run.write_text(json.dumps(meta, ensure_ascii=False))


def _drop_files(rdir, *rels):
    for rel in rels:
        (rdir / rel).unlink()
    _refresh_manifest(rdir)


def _drop_report_key(rdir, key):
    rep = json.loads((rdir / "report.json").read_text())
    del rep[key]
    (rdir / "report.json").write_text(json.dumps(rep, ensure_ascii=False))
    (rdir / "report.md").write_text(R.markdown(rep))
    _refresh_manifest(rdir)


def _drop_run_key(rdir, key):
    run = rdir / "run.json"
    meta = json.loads(run.read_text())
    del meta[key]
    run.write_text(json.dumps(meta, ensure_ascii=False))


F3_FILES = [
    ("eligibility.json.gz",),
    ("features.json.gz",),
    ("models/2016Q1_ML_A.json", "models/2016Q1_ML_A.txt"),
    ("predictions_validation.json",),
    ("predictions_test.json",),
    ("schedule_validation.json",),
    ("schedule_test.json",),
    ("validation/ML_B.json",),
    ("validation/K.json",),
    ("test/B_20.json",),
    ("test/K_40.json",),
    ("selection.json",),
    ("report.json",),
    ("report.md",),
]
F3_REPORT_KEYS = [
    "fits",
    "explain",
    "bootstrap",
    "bootstrap_tail_excluded",
    "validation",
    "test",
    "selection",
    "validation_signal_after_end",
    "test_signal_after_end",
]


@pytest.mark.parametrize("rels", F3_FILES, ids=[x[0] for x in F3_FILES])
def test_verify_rejects_missing_evidence_file(study, rels):
    res = _run(study)
    rdir = _rdir(study, res)
    _drop_files(rdir, *rels)
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert out["status"] == "MISMATCH", out["problems"][:5]


@pytest.mark.parametrize("key", F3_REPORT_KEYS)
def test_verify_rejects_missing_report_key(study, key):
    res = _run(study)
    rdir = _rdir(study, res)
    _drop_report_key(rdir, key)
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert out["status"] == "MISMATCH", out["problems"][:5]
    assert any("필수 칸 없음" in x or "필수 근거" in x for x in out["problems"]), out[
        "problems"
    ][:5]


@pytest.mark.parametrize("key", ["stages", "files", "finished_at", "started_at"])
def test_verify_rejects_missing_run_key(study, key):
    res = _run(study)
    rdir = _rdir(study, res)
    _drop_run_key(rdir, key)
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert out["status"] == "MISMATCH" and any(
        key in x or "단계" in x for x in out["problems"]
    ), out["problems"][:5]


def test_verify_rejects_dropped_stage(study):
    res = _run(study)
    rdir = _rdir(study, res)
    _tamper(
        rdir / "run.json",
        lambda d: d.update(
            stages=[x for x in d["stages"] if x["stage"] != "features · labels"]
        ),
    )
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert any("단계 기록 순서 ≠ 계약 순서" in x for x in out["problems"])


def test_failed_run_verifies_consistently_and_keeps_evidence(study, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("시험 실패")

    with monkeypatch.context() as m:
        m.setattr(R, "select", boom)
        with pytest.raises(RuntimeError):
            _run(study)
    run = next(study["root"].glob("*/runs/*/run.json"))
    assert isinstance(
        json.loads(run.read_text())["files"], dict
    )  # 실패 실행도 해시 목록
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert out["run_status"] == "FAILED" and out["status"] == "OK", out["problems"][:5]
    _drop_files(run.parent, "models/2016Q1_ML_B.json", "models/2016Q1_ML_B.txt")
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert out["status"] == "MISMATCH" and any(
        "필수 근거" in x for x in out["problems"]
    ), out["problems"][:5]


def test_corrupt_record_is_mismatch_not_crash(study):
    res = _run(study)
    rdir = _rdir(study, res)
    _tamper(rdir / "test" / "L_20.json", lambda d: d.update(ledger="손상"))
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert out["status"] == "MISMATCH" and any(
        "형식 손상" in x for x in out["problems"]
    ), out["problems"][:5]


def test_verify_rejects_truncated_stages_on_ok_run(study):
    """정상 완료인데 마지막 단계 기록만 빠짐(앞부분 순서는 맞음) — 완료 계약만 잡는 경우."""
    res = _run(study)
    rdir = _rdir(study, res)
    _tamper(rdir / "run.json", lambda d: d.update(stages=d["stages"][:-1]))
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert "정상 완료인데 계약 단계가 다 기록되지 않음" in out["problems"], out[
        "problems"
    ][:5]


# ── 검증 r3 F3 잔여 — 선택 · 시험 근거 동시 누락(필요 범위를 가장 강한 주장이 정함) ──────────────


def _cut_after_validation(rdir, *, report_test=True, status=None, stop=None):
    """선택 · 시험 모델 · 시험 예측/일정 · 시험 장부를 지우고 단계 기록을 validation books 까지로 줄인다."""
    rels = ["selection.json", "predictions_test.json", "schedule_test.json"]
    rels += [str(f.relative_to(rdir)) for f in (rdir / "test").glob("*.json")]
    for f in (rdir / "models").glob("*.json"):
        if json.loads(f.read_text())["phase"] == "test":
            rels += [f"models/{f.name}", f"models/{f.stem}.txt"]
    for rel in rels:
        (rdir / rel).unlink()
    run = rdir / "run.json"
    meta = json.loads(run.read_text())
    k = [x["stage"] for x in meta["stages"]].index("validation books")
    meta["stages"] = meta["stages"][: k + 1]
    if status:
        meta["status"] = status
    rep = json.loads((rdir / "report.json").read_text())
    rep.pop("selection")
    rep["fits"] = [r for r in rep["fits"] if r["phase"] == "val"]
    if not report_test:
        for key in (
            "test",
            "test_signal_after_end",
            "bootstrap",
            "bootstrap_tail_excluded",
            "explain",
        ):
            rep.pop(key)
        rep["judgment"] = R.judge(status or "OK", None, None)
    if stop:
        rep["stop"] = stop
    (rdir / "report.json").write_text(json.dumps(rep, ensure_ascii=False))
    (rdir / "report.md").write_text(R.markdown(rep))
    meta["files"] = PR.manifest(rdir)
    run.write_text(json.dumps(meta, ensure_ascii=False))


@pytest.mark.parametrize(
    "case",
    [
        "ok_keep_test_report",
        "ok_drop_test_report",
        "forged_check_required",
        "forged_data_short",
    ],
)
def test_verify_rejects_selection_and_test_phase_loss(study, case):
    res = _run(study)
    rdir = _rdir(study, res)
    if case == "ok_keep_test_report":  # 검증자 r3 재현 그대로
        _cut_after_validation(rdir)
    elif case == "ok_drop_test_report":
        _cut_after_validation(rdir, report_test=False)
    elif (
        case == "forged_check_required"
    ):  # 미확정 곡선 없이 '검증 장부에서 미확정 정지'로 바꿈
        _cut_after_validation(
            rdir,
            report_test=False,
            status="CHECK_REQUIRED",
            stop="검증 곡선 평가 미확정 []",
        )
    else:  # 자료 부족으로 바꿈(잠금 사실에 부족 기록 없음)
        _cut_after_validation(
            rdir, report_test=False, status="DATA_SHORT", stop="평가 주 부족"
        )
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert out["status"] == "MISMATCH", out["problems"][:6]


def test_verify_rejects_test_structure_disagreement(study):
    res = _run(study)
    rdir = _rdir(study, res)
    other = {}

    def flip(d):
        other["L"] = "ML_B" if d["L"] == "ML_A" else "ML_A"
        d["L"] = other["L"]

    _tamper(rdir / "selection.json", flip)
    _tamper(rdir / "report.json", lambda d: d["selection"].update(L=other["L"]))
    out = VR.verify(study["root"], study["db"], repo=REPO)
    assert any("시험 구조 기록 불일치" in x for x in out["problems"]), out["problems"][
        :6
    ]
