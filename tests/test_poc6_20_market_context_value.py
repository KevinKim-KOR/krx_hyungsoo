"""POC6-20 시장 4열(가용 시각 · 창 · 결측 · 시간대) · 판정 · 실행 흐름 · verify 변조 검출 · 실제 LightGBM 격리 확인.

시장 4열은 손으로 만든 작은 사본으로, 실행 흐름은 tmp_path 의 작은 봉인 DB · 가짜 시장 사본 · 가짜 모델(학습 0)로
돈다. 봉인 DB · 라이브 DB · POC6-19 실제 사본은 열지 않는다. 실제 LightGBM 확인은 별도 프로세스의 작은 가짜
자료로만 한다(공식 자료 · 성과 미사용 · 판정 §6).
"""

from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from app.feature_gain import protocol as P8
from app.market_context_value import flow as FW
from app.market_context_value import learner as L
from app.market_context_value import market_inputs as MI
from app.market_context_value import protocol as P20
from app.market_context_value import report as RP
from app.market_context_value import study as ST
from app.market_context_value import verify as VR
from app.ml_evidence import store
from app.weekly_selection import data as D
from app.weekly_selection import features as F
from app.weekly_selection import flow as FL
from app.weekly_selection import model as M
from app.weekly_selection import policy as PO
from app.weekly_selection import protocol as PR
from tests._krx_fixture import build_sealed_db, krx_row, rows_by_date

REPO = Path(__file__).resolve().parents[1]
KST = MI.KST


def _bdays(first: str, last: str, holidays=()) -> list[str]:
    d, end = dt.date.fromisoformat(first), dt.date.fromisoformat(last)
    out = []
    while d <= end:
        if d.weekday() < 5 and d.isoformat() not in holidays:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def _src(axis, net=None, status=None, macro=None) -> MI.Sources:
    status = status or {d: "VALID" for d in axis}
    net = net or {d: {"foreign": 1, "institution": -1} for d in axis}
    macro = macro or {MI.KRW: [], MI.WTI: []}
    return MI.Sources(
        flow_status=status,
        flow_net={d: v for d, v in net.items() if status.get(d) == "VALID"},
        macro=macro,
    )


def _obs(days, tz, vals, flag="OK"):
    return [
        {"obs_date": d, "timezone": tz, "close": v, "flag": flag}
        for d, v in zip(days, vals)
    ]


# ── 시장 4열: 수급 창 · 가용 시각 ────────────────────────────────────────────────


AXIS = _bdays("2021-03-01", "2021-05-31")


def test_flow_window_ends_on_trading_day_before_signal_hand_calc():
    i = AXIS.index("2021-04-30")  # 금요일 신호
    net = {
        d: {"foreign": k + 1, "institution": (-1) ** k * 10} for k, d in enumerate(AXIS)
    }
    v, why, ev = MI._flow(AXIS, i, _src(AXIS, net))
    win = AXIS[i - 20 : i]  # noqa: E203 — D 바로 앞 축 거래일까지 20일
    assert why == [] and (ev["first"], ev["last"]) == (win[0], win[-1]) == (
        win[0],
        "2021-04-29",
    )
    assert (
        ev["last_available_at"] == "2021-04-30T12:00:00+09:00"
    )  # 다음 거래일(=D) 12:00 KST
    f = [net[d]["foreign"] for d in win]
    g = [net[d]["institution"] for d in win]
    assert v["FLOW_FRGN_DIR_20"] == sum(f) / sum(abs(x) for x in f)
    assert v["FLOW_ORGN_DIR_20"] == sum(g) / sum(abs(x) for x in g)


def test_flow_ignores_signal_day_and_later_but_not_window_days():
    i = AXIS.index("2021-04-30")
    net = {d: {"foreign": 5, "institution": 3} for d in AXIS}
    base, _, _ = MI._flow(AXIS, i, _src(AXIS, net))
    for d in (
        "2021-04-30",
        "2021-05-03",
        "2021-05-31",
    ):  # 마감 뒤(D 당일 = D+1 12:00 가용) · 미래
        n2 = {**net, d: {"foreign": -999999, "institution": 999999}}
        assert MI._flow(AXIS, i, _src(AXIS, n2))[0] == base
    n3 = {**net, "2021-04-29": {"foreign": -999999, "institution": 3}}
    assert MI._flow(AXIS, i, _src(AXIS, n3))[0] != base  # 창 안 마지막 날은 반영


def test_failed_day_in_window_makes_signal_undefined_without_shrinking():
    i = AXIS.index("2021-04-30")
    st = {d: "VALID" for d in AXIS}
    st["2021-04-12"] = "FAILED"
    v, why, ev = MI._flow(AXIS, i, _src(AXIS, status=st))
    assert v is None and why == ["FLOW_FAILED 2021-04-12"] and ev["days"] == 20
    later = AXIS.index("2021-05-14")  # 창이 실패일을 지나면 다시 정의
    assert MI._flow(AXIS, later, _src(AXIS, status=st))[0] is not None


def test_all_zero_window_is_zero_and_flagged_but_not_requested_is_none():
    i = AXIS.index("2021-04-30")
    net = {d: {"foreign": 0, "institution": 0} for d in AXIS}
    v, why, ev = MI._flow(AXIS, i, _src(AXIS, net))
    assert v == {"FLOW_FRGN_DIR_20": 0.0, "FLOW_ORGN_DIR_20": 0.0} and why == []
    assert ev["foreign"]["all_zero"] and ev["institution"]["all_zero"]
    st = {d: "VALID" for d in AXIS if d >= "2021-04-20"}  # 요청 전 날짜가 창에 있음
    v2, why2, _ = MI._flow(AXIS, i, _src(AXIS, net, status=st))
    assert v2 is None and why2 == ["FLOW_NOT_REQUESTED"]


def test_flow_axis_short_at_start():
    v, why, _ = MI._flow(AXIS, 10, _src(AXIS))
    assert v is None and why == ["FLOW_AXIS_SHORT"]


# ── 시장 4열: 매크로 가용 시각 · 시간대 · 21개 ───────────────────────────────────


def test_macro_available_converts_source_midnight_plus_two_days_with_dst():
    assert MI.macro_available("2021-01-13", "Europe/London").isoformat() == (
        "2021-01-15T09:00:00+09:00"  # GMT
    )
    assert MI.macro_available("2021-07-14", "Europe/London").isoformat() == (
        "2021-07-16T08:00:00+09:00"  # BST
    )
    assert MI.macro_available("2021-01-13", "America/New_York").isoformat() == (
        "2021-01-15T14:00:00+09:00"  # EST
    )
    assert MI.macro_available("2021-07-14", "America/New_York").isoformat() == (
        "2021-07-16T13:00:00+09:00"  # EDT
    )


def _macro_src(days, krw, wti):
    return _src(
        AXIS,
        macro={
            MI.KRW: _obs(days, "Europe/London", krw),
            MI.WTI: _obs(days, "America/New_York", wti),
        },
    )


def test_macro_uses_latest_available_and_twenty_observations_back():
    days = _bdays("2021-03-01", "2021-05-31")
    krw = [1000.0 + k for k in range(len(days))]
    wti = [10.0 - k for k in range(len(days))]  # 음수로 내려감 — 그대로 차이
    src = _macro_src(days, krw, wti)
    av = {
        s: [MI.macro_available(o["obs_date"], o["timezone"]) for o in src.macro[s]]
        for s in src.macro
    }
    i = AXIS.index("2021-04-30")  # 금요일 → d + 2 ≤ 금 → 수요일(04-28)이 최신
    v, why, ev = MI._macro("USDKRW_CHG_20", i, AXIS, src, av)
    k = days.index("2021-04-28")
    assert (
        why == [] and ev["latest"][0] == "2021-04-28" and ev["base"][0] == days[k - 20]
    )
    assert v == krw[k] / krw[k - 20] - 1.0
    w, _, wev = MI._macro("WTI_DIFF_20", i, AXIS, src, av)
    assert w == wti[k] - wti[k - 20] == -20.0 and wev["calendar_days"] == 28
    assert "2021-04-29" not in json.dumps(
        ev
    )  # 목요일(+2 = 토) · 금요일 관측은 쓰지 않음


def test_macro_needs_twenty_one_observations():
    days = _bdays("2021-04-01", "2021-04-28")  # 20개
    src = _macro_src(days, [1000.0] * len(days), [1.0] * len(days))
    av = {
        s: [MI.macro_available(o["obs_date"], o["timezone"]) for o in src.macro[s]]
        for s in src.macro
    }
    v, why, _ = MI._macro("USDKRW_CHG_20", AXIS.index("2021-04-30"), AXIS, src, av)
    assert len(days) == 20 and v is None and why == [f"MACRO_SHORT {MI.KRW}"]


def test_build_defines_signal_only_when_all_four_columns_exist():
    days = _bdays("2021-01-04", "2021-05-31")
    src = _macro_src(days, [1000.0 + k for k in range(len(days))], [5.0] * len(days))
    st = {d: "VALID" for d in AXIS}
    st["2021-05-03"] = "FAILED"
    src.flow_status = st
    src.flow_net = {
        d: {"foreign": 1, "institution": 2} for d in AXIS if st[d] == "VALID"
    }
    sig = D.weekly_signals(AXIS)
    out = MI.build(AXIS, sig, src)
    for i in sig:
        rec = out[i]
        assert (rec["values"] is None) == bool(rec["reasons"])
        if rec["values"] is not None:
            assert (
                rec["values"][1] == 1.0 and rec["values"][3] == 0.0
            )  # 기관계 만 · WTI 차이 0
    bad = [AXIS[i] for i in sig if out[i]["values"] is None and AXIS[i] > "2021-04-01"]
    assert bad and all(
        "FLOW_FAILED 2021-05-03" in out[AXIS.index(d)]["reasons"] for d in bad
    )


# ── 사본 읽기(해시 · A 표본 · 국가 · 세부 미사용) ────────────────────────────────


FLOW_FIELDS = ["date", "investor", "source_field", "raw_eok", "net_won"]
DATE_FIELDS = ["date", "phase", "status", "reason"]
MACRO_FIELDS = [
    "series_id",
    "symbol",
    "phase",
    "window",
    "obs_date",
    "timezone",
    "raw_timestamp_utc",
    "close",
    "unit",
    "flag",
    "canonical",
    "raw_file",
]


def _write(path: Path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_sources(base: Path, axis, failed=(), macro_days=None, seed=7) -> dict:
    """가짜 POC6-19 사본 · 해시 = SHA 에 넣을 값."""
    rng = np.random.default_rng(seed)
    fl, ds = [], []
    for d in axis:
        st = "FAILED" if d in failed else "VALID"
        ds.append({"date": d, "phase": "B", "status": st, "reason": ""})
        if st == "VALID":
            for inv in ("foreign", "institution", "nation", "inst_pension"):
                v = int(rng.integers(-5000, 5000)) * 100_000_000
                fl.append(
                    {
                        "date": d,
                        "investor": inv,
                        "source_field": inv,
                        "raw_eok": "0",
                        "net_won": str(v),
                    }
                )
    run = base / MI.FLOW_RUN
    _write(run / MI.FLOW_FILE, FLOW_FIELDS, fl)
    _write(run / MI.FLOW_DATES_FILE, DATE_FIELDS, ds)
    mr = []
    for d in macro_days or axis:
        for sid, tz, v in (
            (MI.KRW, "Europe/London", 1100 + rng.normal()),
            (MI.WTI, "America/New_York", rng.normal(50, 10)),
        ):
            row = {k: "" for k in MACRO_FIELDS}
            row.update(
                series_id=sid,
                phase="B",
                window="B_FULL",
                obs_date=d,
                timezone=tz,
                close=repr(float(v)),
                flag="OK",
                canonical="1",
            )
            mr.append(row)
            junk = {
                **row,
                "phase": "A",
                "window": "S1",
                "close": "-1e9",
                "canonical": "0",
            }
            mr.append(junk)  # A 표본(장기와 합치지 않음)
    _write(base / MI.MACRO_RUN / MI.MACRO_FILE, MACRO_FIELDS, mr)
    return {
        rel: store.sha256_file(base / run_id / rel)
        for run_id, rel in (
            (MI.FLOW_RUN, MI.FLOW_FILE),
            (MI.FLOW_RUN, MI.FLOW_DATES_FILE),
            (MI.MACRO_RUN, MI.MACRO_FILE),
        )
    }


def test_load_sources_keeps_two_investors_and_canonical_macro_only(
    tmp_path, monkeypatch
):
    axis = _bdays("2021-03-01", "2021-03-31")
    sha = write_sources(tmp_path, axis, failed=("2021-03-10",))
    monkeypatch.setattr(MI, "SHA", sha)
    src = MI.load_sources(tmp_path)
    assert (
        src.flow_status["2021-03-10"] == "FAILED" and "2021-03-10" not in src.flow_net
    )
    assert all(set(v) == {"foreign", "institution"} for v in src.flow_net.values())
    assert all(o["close"] > 0 for o in src.macro[MI.KRW]) and len(
        src.macro[MI.KRW]
    ) == len(axis)
    assert set(src.files) == {
        f"{MI.FLOW_RUN}/{MI.FLOW_FILE}",
        f"{MI.FLOW_RUN}/{MI.FLOW_DATES_FILE}",
        f"{MI.MACRO_RUN}/{MI.MACRO_FILE}",
    }


def test_load_sources_refuses_changed_copy(tmp_path, monkeypatch):
    axis = _bdays("2021-03-01", "2021-03-31")
    sha = write_sources(tmp_path, axis)
    monkeypatch.setattr(MI, "SHA", {**sha, MI.MACRO_FILE: "0" * 64})
    with pytest.raises(D.CheckRequired, match="해시 다름"):
        MI.load_sources(tmp_path)


# ── 판정(손계산) ──────────────────────────────────────────────────────────────────


def _c(cagr, mdd=-0.1, subs=(0.0, 0.0, 0.0), to=1.0):
    return {
        "status": "OK",
        "total": {"cagr": cagr, "mdd": mdd},
        "subperiods": [{"return": s} for s in subs],
        "turnover": {"annual": to},
    }


def _test(**kw):
    base = {f"{k}_{c}": _c(0.05) for k in "PMBK" for c in ("20", "40")}
    base.update(kw)
    return base


def test_judge_market_gain_needs_two_of_three_subperiods():
    t = _test(M_20=_c(0.2, subs=(0.1, -0.1, -0.1)), M_40=_c(0.06))
    j = RP.judge("OK", t, None)
    assert j["values"]["cagr_gap_M_P"] >= RP.GAP_MIN and j["values"]["sub_wins"] == 1
    assert (
        j["market_gain"] == "MARKET_GAIN_NOT_SHOWN"
        and j["candidate"] == "NOT_CANDIDATE"
    )


def test_judge_candidate_needs_every_axis():
    t = _test(M_20=_c(0.07, subs=(0.1, 0.1, -0.1)), M_40=_c(0.06))
    j = RP.judge("OK", t, {"uncertain": True})
    assert (j["market_gain"], j["candidate"], j["uncertainty"]) == (
        "MARKET_GAIN_OBSERVED",
        "FURTHER_REVIEW_CANDIDATE",
        "UNCERTAIN",
    )
    assert j["values"]["sub_wins"] == 2 and j["values"][
        "cagr_gap_M_P"
    ] == pytest.approx(0.02)
    j2 = RP.judge(
        "OK", _test(M_20=_c(0.0599, subs=(0.1, 0.1, 0.1)), M_40=_c(0.06)), None
    )
    assert (
        j2["market_gain"] == "MARKET_GAIN_NOT_SHOWN"
        and "MARKET_GAIN_NOT_SHOWN" in j2["reasons"]
    )


def test_judge_risk_cost_and_baseline_reasons():
    t = _test(
        M_20=_c(0.07, mdd=-0.2, subs=(0.1, 0.1, 0.1), to=6.5),
        K_20=_c(0.08),
        M_40=_c(0.04),
    )
    j = RP.judge("OK", t, None)
    assert (
        j["candidate"] == "NOT_CANDIDATE" and j["market_gain"] == "MARKET_GAIN_OBSERVED"
    )
    for r in (
        "M_NOT_ABOVE_K",
        "MDD_WORSE_THAN_P",
        "MDD_WORSE_THAN_B",
        "MDD_WORSE_THAN_K",
        "TURNOVER_ABOVE_6",
        "COST_SENSITIVE_40BP_VS_P",
        "COST_SENSITIVE_40BP_VS_B",
    ):
        assert r in j["reasons"]
    assert "M_NOT_ABOVE_B" not in j["reasons"]


@pytest.mark.parametrize("validity", ["CHECK_REQUIRED", "DATA_SHORT", "BUDGET_STOP"])
def test_invalid_runs_are_not_judged_not_failures(validity):
    j = RP.judge(validity, None, None)
    assert (
        j["market_gain"] == j["candidate"] == "NOT_JUDGED"
        and j["OPERATION_ADOPTION"] == "NO"
    )


# ── 실행 흐름(작은 봉인 DB · 가짜 시장 사본 · 가짜 모델) ──────────────────────────


@pytest.fixture(scope="module")
def sealed(tmp_path_factory):
    rng = np.random.default_rng(20261104)
    days = [
        d.replace("-", "")
        for d in _bdays("2015-01-02", "2017-06-30", holidays=("2016-07-01",))
    ]
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
    path = tmp_path_factory.mktemp("poc620") / "krx.sqlite"
    sha = build_sealed_db(path, rows_by_date(*maps))
    return path, sha, store.sha256_file(path)


class _Booster:
    """P = RET_5 · M = RET_5 × WTI 차이의 부호(가짜 · 학습 0).

    시장 열은 그날 모든 ETF 에 같은 값이라 더하기만 하면 날짜 안 순위가 P 와 같다. 부호를 곱해 순위가 달라지게
    해서 M · P 장부가 실제로 갈라지게 한다(bootstrap 방향 변이를 잡기 위해).
    """

    def __init__(self, inp):
        self.inp = inp

    def predict(self, X, num_threads=None):
        out = np.nan_to_num(X[:, F.COLUMNS.index("RET_5")])
        if self.inp == "M":
            out = out * np.where(np.nan_to_num(X[:, -1]) < 0, -1.0, 1.0)
        return out


def _lgb_str(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    return {"regression_l2": "regression"}.get(v, str(v))


def _text(b):
    pr = {**M.params(L.STRUCT), "num_iterations": M.NUM_ROUNDS}
    body = "\n".join(f"[{k}: {_lgb_str(v)}]" for k, v in pr.items())
    names = " ".join(L.COLUMNS[b.inp])
    return (
        f"FAKE {b.inp}\nfeature_names={names}\nparameters:\n{body}\nend of parameters\n"
    )


class _Clock:
    def __init__(self):
        self.t = dt.datetime(2026, 11, 4, tzinfo=dt.timezone.utc)

    def __call__(self):
        self.t += dt.timedelta(seconds=1)
        return self.t


FAILED_DAYS = ("2016-03-09", "2016-09-14")


@pytest.fixture
def study(sealed, monkeypatch, tmp_path):
    path, content, file_sha = sealed
    for k, v in (
        ("FILE_SHA", file_sha),
        ("CONTENT_SHA", content),
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
    ):
        monkeypatch.setattr(PR, k, v)
    monkeypatch.setattr(L, "train", lambda inp, X, y, w: _Booster(inp))
    monkeypatch.setattr(M, "to_text", _text)
    monkeypatch.setattr(M, "restore", lambda text: _Booster(text.split()[1]))
    monkeypatch.setattr(M, "env", lambda: {"lightgbm": M.LGB_VERSION, "fake": True})
    monkeypatch.setattr(
        FL, "runtime_env", lambda: {"lightgbm": M.LGB_VERSION, "fake": True}
    )
    p = D.build_panel(path, PR.VERSION, content)
    base = tmp_path / "poc6_19"
    monkeypatch.setattr(MI, "SHA", write_sources(base, p.axis, failed=FAILED_DAYS))
    fx0, *_ = PR.survey(p)
    monkeypatch.setattr(
        PR, "EXPECTED", {k: fx0[k] for k in ("eligible_rows", "signals")}
    )
    fx, *_ = P20.survey(p, base)
    monkeypatch.setattr(
        P20,
        "EXPECTED",
        {k: fx[k] for k in ("defined_signals", "val", "sub_weeks", "fits")},
    )
    return {
        "root": tmp_path / "poc6_20",
        "db": path,
        "base": base,
        "clock": _Clock(),
        "fx": fx,
        "p": p,
    }


def _run(s):
    FW.prepare(s["root"], s["db"], REPO, s["clock"], market_base=s["base"])
    return FW.run(s["root"], s["db"], REPO, s["clock"], market_base=s["base"])


def _rdir(s, res):
    return next(s["root"].glob(f"*/runs/{res['meta']['run_id']}"))


def _verify(s):
    return VR.verify(s["root"], s["db"], REPO, clock=s["clock"], market_base=s["base"])


def test_study_has_lost_weeks_in_both_phases(study):
    fx = study["fx"]
    assert fx["val"]["lost"] and fx["test"]["lost"]  # 실패일이 걸친 주 = 순위 없음
    assert fx["val"]["weeks"] + len(fx["val"]["lost"]) == fx["val"]["h1_weeks"]
    assert all(
        not set(fx["val"]["lost"]) & set(fx[t]["plan_signals"]) for t in ("val", "test")
    )
    assert fx["fits"] == 2 * len(
        fx["quarter_detail"]["val"] + fx["quarter_detail"]["test"]
    )


def test_end_to_end_ok_and_verify_ok(study):
    res = _run(study)
    assert res["meta"]["status"] == "OK", res["report"].get("stop")
    rdir = _rdir(study, res)
    recs = [PR.load_json(f) for f in PR.model_files(rdir)]
    assert len(recs) == study["fx"]["fits"]
    by_q: dict = {}
    for r in recs:
        by_q.setdefault((r["phase"], r["quarter"]), {})[r["input"]] = r
    for (_ph, q), pair in by_q.items():
        p_, m_ = pair["P"], pair["M"]
        for k in (
            "rows_sha256",
            "label_sha256",
            "weight_sha256",
            "x30_sha256",
            "rows",
            "weeks",
        ):
            assert p_[k] == m_[k], (q, k)  # 같은 행 · 정답 · 가중치 · 30열
        assert (
            p_["x_sha256"] != m_["x_sha256"]
            and p_["columns_sha256"] != m_["columns_sha256"]
        )
        assert (p_["id"], m_["id"]) == (f"{q}_P", f"{q}_M")
    rep = res["report"]
    assert set(rep["validation"]) == {"P_20", "M_20", "B_20", "K_20"}
    assert set(rep["test"]) == {f"{k}_{c}" for k in "PMBK" for c in ("20", "40")}
    assert rep["judgment"]["market_gain"] in (
        "MARKET_GAIN_OBSERVED",
        "MARKET_GAIN_NOT_SHOWN",
    )
    # bootstrap 입력 = 저장 장부의 완결 주 M_20 − P_20(공용 함수와 따로 손계산)
    sig_days = {study["p"].axis[i] for i in D.weekly_signals(study["p"].axis)}

    def weekly(name):
        led = PR.load_json(rdir / "test" / f"{name}.json")["ledger"]
        out, prev = [], PO.START_VALUE
        for r in led:
            if r["date"] in sig_days:
                out.append(r["value"] / prev - 1.0)
                prev = r["value"]
        return out

    diffs = [a - b for a, b in zip(weekly("M_20"), weekly("P_20"))]
    assert set(study["fx"]["test"]["lost"]) <= sig_days
    assert rep["bootstrap"]["weeks"] == len(diffs)
    assert rep["bootstrap"]["mean_diff"] == pytest.approx(
        float(np.mean(diffs)), abs=1e-15
    )
    v = _verify(study)
    assert v["status"] == "OK", v["problems"]


def test_lost_weeks_get_no_plan_but_books_keep_running(study):
    res = _run(study)
    rdir = _rdir(study, res)
    fx = study["fx"]
    for sub, tag in (("validation", "val"), ("test", "test")):
        for name in ("P_20", "M_20", "B_20"):
            bk = PR.load_json(rdir / sub / f"{name}.json")
            planned = {pl["signal"] for pl in bk["plans"]}
            assert not planned & set(fx[tag]["lost"])
            assert planned <= set(fx[tag]["plan_signals"])
            led = {r["date"] for r in bk["ledger"]}
            assert all(
                d in led for d in fx[tag]["lost"]
            )  # 순위 없는 주에도 장부는 매일 이어짐


def test_market_columns_follow_lock_and_hand_check(study):
    res = _run(study)
    rdir = _rdir(study, res)
    saved = json.loads(gzip.decompress((rdir / "market.json.gz").read_bytes()))
    p = study["p"]
    d = study["fx"]["test"]["plan_signals"][3]
    rec = saved["signals"][d]
    i = p.axis.index(d)
    win = p.axis[i - 20 : i]  # noqa: E203
    src = MI.load_sources(study["base"])
    f = [src.flow_net[x]["foreign"] for x in win]
    assert rec["values"][0] == pytest.approx(sum(f) / sum(abs(x) for x in f), abs=0)
    k = rec["evidence"]["USDKRW_CHG_20"]
    assert rec["values"][2] == k["latest"][1] / k["base"][1] - 1.0
    assert k["latest"][2] <= rec["evidence"]["deadline"]


def test_validation_check_required_stops_before_main_evaluation(study, monkeypatch):
    real = PO.simulate_bench
    test_start = study["p"].axis.index(study["fx"]["test"]["start"])

    def flaky(p, j, k, start, end, cost):
        bk = real(p, j, k, start, end, cost)
        if start < test_start:
            bk.status, bk.unresolved = "CHECK_REQUIRED", {
                "items": [],
                "first_unresolved": None,
            }
        return bk

    monkeypatch.setattr(PO, "simulate_bench", flaky)
    res = _run(study)
    assert (
        res["meta"]["status"] == "CHECK_REQUIRED"
        and "주 평가 미실행" in res["report"]["stop"]
    )
    rdir = _rdir(study, res)
    recs = [PR.load_json(f) for f in PR.model_files(rdir)]
    assert recs and all(r["phase"] == "val" for r in recs)
    assert not (rdir / "test").exists()
    assert res["report"]["judgment"]["market_gain"] == "NOT_JUDGED"


def test_verify_detects_tampered_prediction_and_market(study):
    res = _run(study)
    rdir = _rdir(study, res)
    f = next(x for x in PR.model_files(rdir) if x.stem.endswith("_M"))
    rec = PR.load_json(f)
    d = rec["signals"][0]
    code = sorted(rec["predictions"][d])[0]
    rec["predictions"][d][code] += 1.0
    os.chmod(f, 0o644)
    f.write_bytes(P8.dumps(rec))
    g = rdir / "market.json.gz"
    m = json.loads(gzip.decompress(g.read_bytes()))
    first = next(k for k, v in m["signals"].items() if v["values"])
    m["signals"][first]["values"][3] += 0.5
    os.chmod(g, 0o644)
    g.write_bytes(gzip.compress(json.dumps(m).encode()))
    v = _verify(study)
    joined = " | ".join(v["problems"])
    assert v["status"] == "MISMATCH"
    assert (
        "복원 예측 ≠ 저장 예측" in joined
        and "market.json.gz" in joined
        and "파일 해시" in joined
    )


def test_run_once_and_prepare_once(study):
    _run(study)
    with pytest.raises(PR.Refused):
        FW.run(
            study["root"], study["db"], REPO, study["clock"], market_base=study["base"]
        )
    with pytest.raises(PR.Refused):
        FW.prepare(
            study["root"], study["db"], REPO, study["clock"], market_base=study["base"]
        )


def test_run_refuses_changed_market_copy(study, monkeypatch):
    FW.prepare(
        study["root"], study["db"], REPO, study["clock"], market_base=study["base"]
    )
    monkeypatch.setattr(MI, "SHA", {**MI.SHA, MI.FLOW_FILE: "1" * 64})
    with pytest.raises(D.CheckRequired):
        FW.run(
            study["root"], study["db"], REPO, study["clock"], market_base=study["base"]
        )


def test_cli_verify_without_lock_is_check_required(tmp_path, monkeypatch, capsys):
    sys.path.insert(0, str(REPO / "scripts"))
    import run_market_context_value as CLI

    monkeypatch.setattr(P20, "ROOT", tmp_path / "none")
    rc = CLI.main(["verify"])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1].split(" ", 1)[1])
    assert rc == 2 and out["status"] == "CHECK_REQUIRED"


# ── 실제 LightGBM 격리 확인(작은 가짜 자료 · 별도 프로세스 · 판정 §6) ───────────────

_REAL = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
import numpy as np
from app.market_context_value import learner as L
from app.weekly_selection import model as M
rng = np.random.default_rng(1)
X = rng.normal(size=(600, 34)); X[::7, 3] = np.nan
y = (X[:, 0] - 0.5 * X[:, 33] + rng.normal(scale=0.1, size=600)).tolist()
w = [1.0] * 600
out = {"openmp": M.openmp_problem(), "lgb": M.env()["lightgbm"]}
for inp, Xi in (("P", X[:, :30]), ("M", X)):
    b = L.train(inp, L.matrix(Xi.tolist(), len(L.COLUMNS[inp])), y, w)
    text = M.to_text(b)
    back = M.restore(text)
    a, c = M.predict(b, Xi), M.predict(back, Xi)
    rp = M.resolved_params(text)
    out[inp] = {
        "names": L.feature_names(text) == list(L.COLUMNS[inp]),
        "diff": float(np.max(np.abs(a - c))),
        "leaves": rp.get("num_leaves"),
        "depth": rp.get("max_depth"),
    }
try:
    L.matrix(X[:, :30].tolist(), 34)
    out["width_guard"] = False
except ValueError:
    out["width_guard"] = True
print(json.dumps(out))
"""


def test_real_lightgbm_30_and_34_columns_round_trip_on_fake_data():
    r = subprocess.run(
        [sys.executable, "-c", _REAL, str(REPO)],
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["openmp"] is None and out["lgb"] == M.LGB_VERSION and out["width_guard"]
    for inp in ("P", "M"):
        assert out[inp]["names"] and out[inp]["diff"] <= M.RESTORE_TOL
        assert (out[inp]["leaves"], out[inp]["depth"]) == ("15", "4")


def test_input_columns_are_thirty_then_four_market_columns_in_fixed_order():
    assert L.COLUMNS["P"] == tuple(F.COLUMNS) and len(F.COLUMNS) == 30
    assert L.COLUMNS["M"][:30] == tuple(F.COLUMNS)
    assert L.COLUMNS["M"][30:] == (
        "FLOW_FRGN_DIR_20",
        "FLOW_ORGN_DIR_20",
        "USDKRW_CHG_20",
        "WTI_DIFF_20",
    )
    assert MI.FLOW_INVESTOR == {
        "FLOW_FRGN_DIR_20": "foreign",
        "FLOW_ORGN_DIR_20": "institution",
    }


# ── verify 변조 · 정지 주장 · 실패 경로(실행 전 독립 검토 지적 반영) ───────────────────


def _write_json(path: Path, obj) -> None:
    if path.exists():
        os.chmod(path, 0o644)
    path.write_bytes(P8.dumps(obj))


def _refresh_manifest(rdir: Path) -> None:
    meta = PR.load_json(rdir / "run.json")
    meta["files"] = PR.manifest(rdir)
    _write_json(rdir / "run.json", meta)


def _set_status(rdir: Path, status: str) -> None:
    meta = PR.load_json(rdir / "run.json")
    meta["status"] = status
    _write_json(rdir / "run.json", meta)


def _forge_val_stop(rdir: Path) -> None:
    import shutil

    shutil.rmtree(rdir / "test")
    test_ids = [
        f.stem for f in PR.model_files(rdir) if PR.load_json(f)["phase"] == "test"
    ]
    for mid in test_ids:
        for suffix in (".txt", ".json"):
            (rdir / "models" / f"{mid}{suffix}").unlink()
    for n in ("predictions_test.json", "schedule_test.json", "report.md"):
        (rdir / n).unlink()
    rep = PR.load_json(rdir / "report.json")
    for k in (
        "test",
        "test_signal_after_end",
        "bootstrap",
        "bootstrap_tail_excluded",
        "explain",
    ):
        rep.pop(k, None)
    rep["fits"] = [r for r in rep["fits"] if r["phase"] == "val"]
    rep["judgment"] = RP.judge("CHECK_REQUIRED", None, None)
    rep["stop"] = ST.VAL_STOP.format(bad=["K_20"])
    _write_json(rdir / "report.json", rep)
    (rdir / "report.md").write_text(RP.markdown(rep), encoding="utf-8")
    _set_status(rdir, "CHECK_REQUIRED")
    _refresh_manifest(rdir)


def _forge_params(rdir: Path) -> None:
    f = next(x for x in PR.model_files(rdir) if x.stem.endswith("_M"))
    txt = f.with_suffix(".txt")
    text = txt.read_text(encoding="utf-8").replace(
        "[num_leaves: 15]", "[num_leaves: 63]"
    )
    os.chmod(txt, 0o644)
    txt.write_text(text, encoding="utf-8")
    rec = PR.load_json(f)
    rec.update(
        model_sha256=store.sha256_bytes(text.encode()),
        resolved_params=M.resolved_params(text),
    )
    _write_json(f, rec)
    _refresh_manifest(rdir)


def _second_run(rdir: Path) -> None:
    import shutil

    shutil.copytree(rdir, rdir.parent / (rdir.name[:-1] + "z"))


def _forge_stages(rdir: Path) -> None:
    meta = PR.load_json(rdir / "run.json")
    meta["stages"] = list(reversed(meta["stages"]))
    _write_json(rdir / "run.json", meta)


def _drop_market(rdir: Path) -> None:
    (rdir / "market.json.gz").unlink()
    _refresh_manifest(rdir)


def _report_change(fn):
    def apply(rdir: Path) -> None:
        rep = PR.load_json(rdir / "report.json")
        fn(rep)
        _write_json(rdir / "report.json", rep)
        os.chmod(rdir / "report.md", 0o644)
        (rdir / "report.md").write_text(RP.markdown(rep), encoding="utf-8")
        _refresh_manifest(rdir)

    return apply


def _forge_schedule(rdir: Path) -> None:
    s = PR.load_json(rdir / "schedule_test.json")
    s[0]["model"] = "bogus"
    _write_json(rdir / "schedule_test.json", s)
    _refresh_manifest(rdir)


def _forge_model_record(rdir: Path) -> None:
    f = next(x for x in PR.model_files(rdir) if x.stem.endswith("_P"))
    rec = PR.load_json(f)
    rec.update(id="anything", restore_max_abs_diff=0.5)
    _write_json(f, rec)
    _refresh_manifest(rdir)


def _failed_book_tamper(rdir: Path) -> None:
    for n in ("report.json", "report.md"):
        (rdir / n).unlink()
    bk = PR.load_json(rdir / "test" / "M_20.json")
    bk["ledger"][-1]["value"] *= 2
    _write_json(rdir / "test" / "M_20.json", bk)
    _set_status(rdir, "FAILED")
    _refresh_manifest(rdir)


def _broken_features(rdir: Path) -> None:
    f = rdir / "features.json.gz"
    os.chmod(f, 0o644)
    f.write_bytes(b"not gzip")
    _refresh_manifest(rdir)


@pytest.mark.parametrize(
    "tamper, expect",
    [
        (lambda r: _set_status(r, "DATA_SHORT"), "DATA_SHORT"),
        (_forge_val_stop, "선행 재생 정지 문구 ≠"),
        (_forge_params, "고정 ML_B 설정"),
        (_second_run, "실행이 2개"),
        (_forge_stages, "단계"),
        (_drop_market, "필수 근거 없음"),
        (
            _report_change(lambda rep: rep.update(conclusion="M is better")),
            "계약 밖 칸",
        ),
        (
            _report_change(lambda rep: rep["coverage"]["test"].update(lost=[])),
            "coverage",
        ),
        (_forge_schedule, "schedule_test.json ≠"),
        (_forge_model_record, "복원 차이 기록"),
        (_failed_book_tamper, "정책 재적용 ≠ 저장 장부"),
        (lambda r: _set_status(r, "FAILED"), "실패 실행에 보고 파일이 남음"),
        (_broken_features, "검사 중 손상"),
    ],
)
def test_verify_catches_forged_or_broken_records(study, tamper, expect):
    res = _run(study)
    assert res["meta"]["status"] == "OK"
    tamper(_rdir(study, res))
    v = _verify(study)  # 예외 없이 기록을 남긴다
    assert v["status"] == "MISMATCH" and expect in " | ".join(v["problems"]), v[
        "problems"
    ]


def test_report_write_failure_is_failed_and_verify_records_it(study, monkeypatch):
    real = P8.write_once

    def flaky(path, data):
        if Path(path).name == "report.md":
            raise OSError("disk full")
        return real(path, data)

    monkeypatch.setattr(P8, "write_once", flaky)
    FW.prepare(
        study["root"], study["db"], REPO, study["clock"], market_base=study["base"]
    )
    with pytest.raises(OSError):
        FW.run(
            study["root"], study["db"], REPO, study["clock"], market_base=study["base"]
        )
    monkeypatch.setattr(P8, "write_once", real)
    rdir = next(study["root"].glob("*/runs/*"))
    meta = PR.load_json(rdir / "run.json")
    assert meta["status"] == "FAILED" and meta["report_files_left_invalid"] == [
        "report.json"
    ]
    v = _verify(study)
    assert v["status"] == "MISMATCH" and v["run_status"] == "FAILED"
    assert any("실패 실행에 보고 파일이 남음" in x for x in v["problems"])


def test_real_validation_stop_verifies_ok(study, monkeypatch):
    real = PO.simulate_bench
    test_start = study["p"].axis.index(study["fx"]["test"]["start"])

    def flaky(p, j, k, start, end, cost):
        bk = real(p, j, k, start, end, cost)
        if start < test_start:
            bk.status, bk.unresolved = "CHECK_REQUIRED", {
                "items": [],
                "first_unresolved": None,
            }
        return bk

    monkeypatch.setattr(PO, "simulate_bench", flaky)
    res = _run(study)
    assert res["report"]["stop"] == ST.VAL_STOP.format(bad=["K_20"])
    v = _verify(study)
    assert v["status"] == "OK", v["problems"]  # 진짜 정지는 정지 주장 검사를 통과


# ── 마지막 계산 뒤 예산 상한(검증자 r1 F1) ──────────────────────────────────────────


def test_budget_over_after_last_book_check_becomes_budget_stop(study, monkeypatch):
    real = ST.pair_bootstrap

    def slow(p, sig, tbooks):
        out = real(p, sig, tbooks)
        study["clock"].t += dt.timedelta(
            seconds=PR.BUDGET_S + 1
        )  # 마지막 장부 검사 뒤 상한 초과
        return out

    monkeypatch.setattr(ST, "pair_bootstrap", slow)
    res = _run(study)
    rep, meta = res["report"], res["meta"]
    assert meta["status"] == "BUDGET_STOP" and rep["stop"].startswith(
        "BudgetStop: finish:"
    )
    assert (
        rep["judgment"]["market_gain"] == rep["judgment"]["candidate"] == "NOT_JUDGED"
    )
    assert not set(ST.FINAL_KEYS[1:]) & set(rep)  # bootstrap · 설명 칸 없음
    assert (
        meta["stages"][-1]["stage"] == "finish"
        and meta["stages"][-1]["wall_s"] > PR.BUDGET_S
    )
    v = _verify(study)
    assert v["status"] == "OK" and v["run_status"] == "BUDGET_STOP", v["problems"]


def test_ok_run_ends_with_finish_stage_and_verify_requires_it(study):
    res = _run(study)
    meta = res["meta"]
    assert meta["stages"][-1]["stage"] == "finish"
    assert meta["finished_at"] == meta["stages"][-1]["at"] <= meta["written_at"]
    rdir = _rdir(study, res)
    m = PR.load_json(rdir / "run.json")
    m["stages"] = m["stages"][:-1]
    m["finished_at"] = m["stages"][-1]["at"]
    _write_json(rdir / "run.json", m)
    v = _verify(study)
    assert v["status"] == "MISMATCH" and any("finish" in x for x in v["problems"])


@pytest.mark.parametrize("slow", ["markdown", "manifest"])
def test_budget_over_while_building_report_becomes_budget_stop(
    study, monkeypatch, slow
):
    """finish 판정 전에 보고 글 · 해시 목록까지 계산한다(검증자 r2 F2) — 그 사이 초과도 BUDGET_STOP."""
    target = (RP, "markdown") if slow == "markdown" else (PR, "manifest")
    real = getattr(*target)
    state = {"done": False}

    def slow_fn(*a, **k):
        out = real(*a, **k)
        if not state["done"]:  # 첫 호출(정상 완료 보고를 만드는 중)에만 상한을 넘긴다
            state["done"] = True
            study["clock"].t += dt.timedelta(seconds=PR.BUDGET_S + 1)
        return out

    monkeypatch.setattr(*target, slow_fn)
    res = _run(study)
    assert res["meta"]["status"] == "BUDGET_STOP", res["report"].get("stop")
    assert res["report"]["stop"].startswith("BudgetStop: finish:")
    assert res["report"]["judgment"]["market_gain"] == "NOT_JUDGED"
    monkeypatch.setattr(*target, real)
    v = _verify(study)
    assert v["status"] == "OK" and v["run_status"] == "BUDGET_STOP", v["problems"]


def test_verify_flags_ok_run_whose_write_finished_after_limit(study):
    res = _run(study)
    rdir = _rdir(study, res)
    m = PR.load_json(rdir / "run.json")
    st0 = store.parse_iso(m["started_at"])
    m["written_at"] = store.iso(st0 + dt.timedelta(seconds=PR.BUDGET_S + 1))
    _write_json(rdir / "run.json", m)
    v = _verify(study)
    assert v["status"] == "MISMATCH" and any(
        "기록 완료 시각" in x for x in v["problems"]
    )
