"""POC6-21 실행 흐름 · verify 변조 검출 · 예산 경계 · 실제 LightGBM 격리 확인.

실행 흐름은 tmp_path 의 작은 봉인 DB · 가짜 POC6-19 사본 · 가짜 모델(학습 0)로 돈다. 봉인 DB · 라이브 DB ·
POC6-19 실제 사본은 열지 않는다. 실제 LightGBM 확인은 별도 프로세스의 작은 가짜 자료로만 한다(공식 자료 ·
성과 미사용 · 판정 §5).
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from app.feature_gain import protocol as P8
from app.market_context_value import learner as L
from app.market_context_value import market_inputs as MI
from app.market_context_value import study as S20
from app.ml_evidence import store
from app.trend_switch import flow as FW
from app.trend_switch import labels as LB
from app.trend_switch import protocol as P21
from app.trend_switch import report as RP
from app.trend_switch import study as ST
from app.trend_switch import verify as VR
from app.weekly_selection import data as D
from app.weekly_selection import features as F
from app.weekly_selection import flow as FL
from app.weekly_selection import model as M
from app.weekly_selection import policy as PO
from app.weekly_selection import protocol as PR
from tests._krx_fixture import build_sealed_db, krx_row, rows_by_date
from tests.test_poc6_20_market_context_value import _bdays, write_sources

REPO = Path(__file__).resolve().parents[1]
FAILED_DAYS = ("2016-03-09", "2016-09-14")


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
    path = tmp_path_factory.mktemp("poc621") / "krx.sqlite"
    sha = build_sealed_db(path, rows_by_date(*maps))
    return path, sha, store.sha256_file(path)


class _Booster:
    """M = RET_5 × WTI 차이의 부호(가짜 · 학습 0) — 절대 문턱 ±h 를 자주 넘도록 수익률 크기 그대로."""

    def predict(self, X, num_threads=None):
        out = np.nan_to_num(X[:, F.COLUMNS.index("RET_5")])
        return out * np.where(np.nan_to_num(X[:, -1]) < 0, -1.0, 1.0)


def _lgb_str(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    return {"regression_l2": "regression"}.get(v, str(v))


def _text(_b):
    pr = {**M.params(L.STRUCT), "num_iterations": M.NUM_ROUNDS}
    body = "\n".join(f"[{k}: {_lgb_str(v)}]" for k, v in pr.items())
    names = " ".join(L.COLUMNS["M"])
    return f"FAKE M\nfeature_names={names}\nparameters:\n{body}\nend of parameters\n"


class _Clock:
    def __init__(self):
        self.t = dt.datetime(2026, 11, 4, tzinfo=dt.timezone.utc)

    def __call__(self):
        self.t += dt.timedelta(seconds=1)
        return self.t


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
    trained = []
    monkeypatch.setattr(
        L,
        "train",
        lambda inp, X, y, w: trained.append((inp, len(y), list(y))) or _Booster(),
    )
    monkeypatch.setattr(M, "to_text", _text)
    monkeypatch.setattr(M, "restore", lambda text: _Booster())
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
    fx, *_ = P21.survey(p, base)
    monkeypatch.setattr(
        P21,
        "EXPECTED",
        {k: fx[k] for k in ("populations", "labels", "val", "sub_weeks", "fits")},
    )
    return {
        "root": tmp_path / "poc6_21",
        "db": path,
        "base": base,
        "clock": _Clock(),
        "fx": fx,
        "p": p,
        "trained": trained,
    }


def _run(s):
    FW.prepare(s["root"], s["db"], REPO, s["clock"], market_base=s["base"])
    return FW.run(s["root"], s["db"], REPO, s["clock"], market_base=s["base"])


def _rdir(s, res):
    return next(s["root"].glob(f"*/runs/{res['meta']['run_id']}"))


def _verify(s):
    return VR.verify(s["root"], s["db"], REPO, clock=s["clock"], market_base=s["base"])


# ── 분모 · 정상 흐름 ────────────────────────────────────────────────────────────


def test_survey_populations_partition_and_one_fit_per_quarter(study):
    fx = study["fx"]
    po, lb = fx["populations"], fx["labels"]
    assert po["signals_20_defined"] + len(po["undefined_20"]) == po["signals_20"]
    assert po["signals_20_defined"] + po["defined_lt20"] == po["defined"]
    for key, total in (
        ("s20", po["signals_20"]),
        ("s20_defined", po["signals_20_defined"]),
    ):
        x = lb[key]
        assert x["usable"] + len(x["unusable_matured"]) + x["immature"] == total
    assert (
        lb["s20"]["rows"] >= lb["rows_h1_s20"]
    )  # ETF 자체 판정은 H1 판정보다 줄지 않음
    assert lb["s20"]["rows"] >= lb["s20_defined"]["rows"]
    assert po["undefined_20"]  # 실패일이 걸친 주 = 공통 조건 밖
    q = fx["quarter_detail"]["val"] + fx["quarter_detail"]["test"]
    assert fx["fits"] == fx["quarters"] == len(q)


def test_end_to_end_ok_and_verify_ok(study):
    res = _run(study)
    assert res["meta"]["status"] == "OK", res["report"].get("stop")
    rdir = _rdir(study, res)
    recs = [PR.load_json(f) for f in PR.model_files(rdir)]
    assert len(recs) == study["fx"]["fits"] and all(
        r["id"].endswith("_M") for r in recs
    )
    assert all(r["input"] == "M" for r in recs)
    assert {inp for inp, _n, _y in study["trained"]} == {"M"}
    rep = res["report"]
    assert set(rep["validation"]) == {f"{k}_20" for k in RP.NAMES}
    assert set(rep["test"]) == {f"{k}_{c}" for k in RP.NAMES for c in ("20", "40")}
    # 같은 후보 순서 · 같은 계획 주 · M0 · M1 은 같은 모델 예측
    bk = {
        n: PR.load_json(rdir / "test" / f"{n}.json")
        for n in ("R0_20", "R1_20", "M0_20", "M1_20")
    }
    sig = {n: [pl["signal"] for pl in b["plans"]] for n, b in bk.items()}
    assert len({tuple(v) for v in sig.values()}) == 1
    first = {n: (b["plans"][0]["cands"], b["plans"][0]["model"]) for n, b in bk.items()}
    assert first["R0_20"][0] == first["M1_20"][0] and first["M0_20"] == first["M1_20"]
    tt = rep["test_trades"]
    assert {"underwater", "cash", "costs_total", "holding", "underwater_sub"} <= set(
        tt["K_20"]
    )
    assert all(len(tt[k]["underwater_sub"]) == 3 and "cash" in tt[k] for k in tt)
    assert tt["K_20"]["holding"]["entry"] == study["fx"]["test"]["k_exec"]
    opps = RP.opportunities(rep["test_trades"])
    assert (
        opps["M1_20"] > 0 and opps["R1_20"] > 0 and opps["M0_20"] == opps["R0_20"] == 0
    )
    assert rep["judgment"]["strengthen_gain"] != "NOT_JUDGED"
    # bootstrap 입력 = 저장 장부의 완결 주 M1_20 − R1_20(공용 함수와 따로 손계산)
    sig_days = {study["p"].axis[i] for i in D.weekly_signals(study["p"].axis)}

    def weekly(name):
        led = PR.load_json(rdir / "test" / f"{name}.json")["ledger"]
        out, prev = [], PO.START_VALUE
        for r in led:
            if r["date"] in sig_days:
                out.append(r["value"] / prev - 1.0)
                prev = r["value"]
        return out

    diffs = [a - b for a, b in zip(weekly("M1_20"), weekly("R1_20"))]
    assert rep["bootstrap"]["weeks"] == len(diffs)
    assert rep["bootstrap"]["mean_diff"] == pytest.approx(
        float(np.mean(diffs)), abs=1e-15
    )
    v = _verify(study)
    assert v["status"] == "OK", v["problems"]


def test_training_label_is_absolute_price_change_not_rank(study):
    res = _run(study)
    rdir = _rdir(study, res)
    p = study["p"]
    feat = json.loads(gzip.decompress((rdir / "features.json.gz").read_bytes()))
    r = next(k for k, y in enumerate(feat["y_abs"]) if y is not None)
    d, code = feat["rows"][r]
    i, j = p.axis.index(d), p.ci[code]
    assert (
        feat["y_abs"][r]
        == math.log(p.I[j, i + 61] / p.O[j, i + 2])
        == LB.label(p, j, i)
    )
    _fx, el, *_r, mkt = P21.survey(p, study["base"])
    t = ST.abs_table(p, el)
    q0 = study["fx"]["quarter_detail"]["val"][0]
    defined = {i for i in el.sig if mkt[i]["values"] is not None}
    rows = S20.train_rows(t, p, q0, defined)
    assert study["trained"][0][2] == [
        t.y[r] for r in rows
    ]  # 첫 fit 정답 = 절대 정답 행 그대로
    h1 = F.build_table(p, {i: el.members[i] for i in t.sig})
    assert [t.y[r] for r in rows] != [h1.y[r] for r in rows]  # H1 순위 정답이 아님
    rec = PR.load_json(next(iter(PR.model_files(rdir))))
    q = next(
        x
        for tag in ("val", "test")
        for x in study["fx"]["quarter_detail"][tag]
        if x["id"] == rec["quarter"]
    )
    assert (rec["weeks"], rec["rows"]) == (
        q["weeks"],
        q["rows"],
    )  # 잠금 분기 = 최종 교집합


def test_no_plan_weeks_keep_books_running(study):
    res = _run(study)
    rdir = _rdir(study, res)
    fx = study["fx"]
    for sub, tag in (("validation", "val"), ("test", "test")):
        for name in ("R1_20", "M1_20"):
            bk = PR.load_json(rdir / sub / f"{name}.json")
            planned = {pl["signal"] for pl in bk["plans"]}
            assert not planned & set(fx[tag]["lost"])
            assert planned <= set(fx[tag]["plan_signals"])
            led = {r["date"] for r in bk["ledger"]}
            assert all(d in led for d in fx[tag]["lost"])


def _flaky_bench(study, monkeypatch):
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


def test_validation_stop_skips_main_evaluation_and_verifies(study, monkeypatch):
    _flaky_bench(study, monkeypatch)
    res = _run(study)
    assert res["meta"]["status"] == "CHECK_REQUIRED"
    assert res["report"]["stop"] == ST.VAL_STOP.format(bad=["K_20"])
    rdir = _rdir(study, res)
    assert all(PR.load_json(f)["phase"] == "val" for f in PR.model_files(rdir))
    assert not (rdir / "test").exists()
    assert res["report"]["judgment"]["candidate"] == "NOT_JUDGED"
    v = _verify(study)
    assert v["status"] == "OK", v["problems"]


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


def test_prepare_refuses_when_denominator_differs_from_plan(study, monkeypatch):
    exp = json.loads(json.dumps(P21.EXPECTED))
    exp["populations"]["signals_20_defined"] += 1
    monkeypatch.setattr(P21, "EXPECTED", exp)
    with pytest.raises(D.CheckRequired, match="PLAN 표와 다름"):
        FW.prepare(
            study["root"], study["db"], REPO, study["clock"], market_base=study["base"]
        )
    assert not study["root"].exists() or not P8.locks(study["root"])


def test_cli_verify_without_lock_is_check_required(tmp_path, monkeypatch, capsys):
    sys.path.insert(0, str(REPO / "scripts"))
    import run_trend_switch as CLI

    monkeypatch.setattr(P21, "ROOT", tmp_path / "none")
    rc = CLI.main(["verify"])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1].split(" ", 1)[1])
    assert rc == 2 and out["status"] == "CHECK_REQUIRED"


# ── verify 변조 · 정지 주장 · 실패 경로 ───────────────────────────────────────────


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


def _forge_prediction(rdir: Path) -> None:
    f = PR.model_files(rdir)[-1]
    rec = PR.load_json(f)
    d = rec["signals"][0]
    code = sorted(rec["predictions"][d])[0]
    rec["predictions"][d][code] += 1.0
    _write_json(f, rec)
    _refresh_manifest(rdir)


def _forge_review(rdir: Path) -> None:
    f = rdir / "test" / "M1_20.json"
    bk = PR.load_json(f)
    rv = next(r for pl in bk["plans"] for r in pl["entry_reviews"] if r["strengthened"])
    rv["strengthened"] = False
    _write_json(f, bk)
    _refresh_manifest(rdir)


def _forge_params(rdir: Path) -> None:
    f = PR.model_files(rdir)[0]
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


def _failed_book_tamper(rdir: Path) -> None:
    for n in ("report.json", "report.md"):
        (rdir / n).unlink()
    bk = PR.load_json(rdir / "test" / "M1_20.json")
    bk["ledger"][-1]["value"] *= 2
    _write_json(rdir / "test" / "M1_20.json", bk)
    _set_status(rdir, "FAILED")
    _refresh_manifest(rdir)


def _foreign_model(rdir: Path) -> None:
    src = PR.model_files(rdir)[0]
    shutil.copy(src.with_suffix(".txt"), rdir / "models" / (src.stem[:-1] + "P.txt"))
    _refresh_manifest(rdir)


def _relabel_stop_without_report(rdir: Path) -> None:
    for n in ("report.json", "report.md"):
        (rdir / n).unlink()
    _set_status(rdir, "CHECK_REQUIRED")
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
        (_forge_prediction, "복원 예측 ≠ 저장 예측"),
        (_forge_review, "검토 기록"),
        (_forge_params, "고정 ML_B 설정"),
        (_second_run, "실행이 2개"),
        (_forge_stages, "단계"),
        (_drop_market, "필수 근거 없음"),
        (
            _report_change(lambda rep: rep.update(conclusion="M1 is better")),
            "계약 밖 칸",
        ),
        (
            _report_change(
                lambda rep: rep["test_trades"]["M1_20"].update(costs_total=0.0)
            ),
            "거래 분석",
        ),
        (
            _report_change(
                lambda rep: rep["judgment"].update(candidate="FURTHER_REVIEW_CANDIDATE")
            ),
            "판정",
        ),
        (_failed_book_tamper, "정책 재적용 ≠ 저장 장부"),
        (lambda r: _set_status(r, "FAILED"), "실패 실행에 보고 파일이 남음"),
        (_foreign_model, "계약 밖 파일"),
        (_relabel_stop_without_report, "보고 파일 없음"),
        (_report_change(lambda rep: rep.pop("coverage")), "필수 칸 없음"),
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


# ── 모든 계산 뒤 예산 상한(POC6-20 검증자 r1 F1 · r2 F2 교훈) ────────────────────────


@pytest.mark.parametrize("slow", ["bootstrap", "markdown", "manifest"])
def test_budget_over_after_last_computation_becomes_budget_stop(
    study, monkeypatch, slow
):
    target = {
        "bootstrap": (ST, "pair_bootstrap"),
        "markdown": (RP, "markdown"),
        "manifest": (PR, "manifest"),
    }[slow]
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
    rep, meta = res["report"], res["meta"]
    assert meta["status"] == "BUDGET_STOP", rep.get("stop")
    assert rep["stop"].startswith("BudgetStop: finish:")
    assert rep["judgment"]["candidate"] == rep["judgment"]["ml_gain"] == "NOT_JUDGED"
    assert not {"bootstrap", "bootstrap_tail_excluded"} & set(rep)
    monkeypatch.setattr(*target, real)
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


# ── 실제 LightGBM 격리 확인(작은 가짜 자료 · 별도 프로세스) ──────────────────────────

_REAL = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
import numpy as np
import app.trend_switch  # noqa: F401 — 같은 OpenMP 로드 순서
from app.market_context_value import learner as L
from app.weekly_selection import model as M
rng = np.random.default_rng(1)
X = rng.normal(size=(600, 34)); X[::7, 3] = np.nan
y = (0.05 * X[:, 0] - 0.02 * X[:, 33] + rng.normal(scale=0.01, size=600)).tolist()  # 로그 변화 크기
b = L.train("M", L.matrix(X.tolist(), 34), y, [1.0] * 600)
text = M.to_text(b)
back = M.restore(text)
a, c = M.predict(b, X), M.predict(back, X)
print(json.dumps({
    "openmp": M.openmp_problem(), "lgb": M.env()["lightgbm"],
    "names": L.feature_names(text) == list(L.COLUMNS["M"]),
    "params": L.param_problems(text), "diff": float(np.max(np.abs(a - c))),
    "spread": float(np.std(a)), "corr": float(np.corrcoef(a, y)[0, 1]),
}))
"""


def test_real_lightgbm_34_columns_absolute_target_round_trip_on_fake_data():
    r = subprocess.run(
        [sys.executable, "-c", _REAL, str(REPO)],
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["openmp"] is None and out["lgb"] == M.LGB_VERSION and out["names"]
    assert out["params"] == [] and out["diff"] <= M.RESTORE_TOL
    assert (
        out["spread"] > 0 and out["corr"] > 0.5
    )  # 절대 크기 목표를 실제로 학습(순위 · 중심화 없음)


def test_verify_audit_catches_policy_bug_that_reapply_repeats(study, monkeypatch):
    """정책 재적용은 같은 코드라 같은 오류를 되풀이한다 — 독립 감사만 잡는다(판정 §5)."""
    from app.trend_switch import policy as TP

    monkeypatch.setattr(
        TP,
        "threshold",
        lambda s, gap: (TP.H, gap is not None and 0 <= gap <= 10, False),
    )
    res = _run(study)
    assert res["meta"]["status"] == "OK"
    v = _verify(study)
    joined = " | ".join(v["problems"])
    assert (
        v["status"] == "MISMATCH"
        and "검토 기록" in joined
        and "정책 재적용" not in joined
    )
