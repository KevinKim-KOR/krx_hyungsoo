"""POC6-23 실행 흐름 · verify 변조 검출 · 정지 경로 · 예산 경계 — tmp 봉인 DB · 가짜 POC6-19 사본만.

봉인 DB · 라이브 DB · POC6-19 실제 사본은 열지 않는다. 학습은 실제 SciPy HiGHS(threads=1)로 작은 가짜 자료만 푼다.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from app.decision_learning import flow as FW
from app.decision_learning import labels as LB
from app.decision_learning import learn as LN
from app.decision_learning import protocol as P23
from app.decision_learning import report as RP
from app.decision_learning import verify as VR
from app.feature_gain import protocol as P8
from app.market_context_value import market_inputs as MI
from app.ml_evidence import store
from app.weekly_selection import data as D
from app.weekly_selection import policy as PO
from app.weekly_selection import protocol as PR
from tests.test_poc6_20_market_context_value import write_sources
from tests.test_poc6_21_flow import FAILED_DAYS, _Clock, sealed  # noqa: F401

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def study(sealed, monkeypatch, tmp_path):  # noqa: F811
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
    ):
        monkeypatch.setattr(PR, k, v)
    env = {**P23.runtime_env(), "threads_env": dict.fromkeys(P23.THREAD_ENV, "1")}
    monkeypatch.setattr(P23, "runtime_env", lambda: dict(env))
    monkeypatch.setattr(P23, "MIN_DATES", 3)
    p = D.build_panel(path, PR.VERSION, content)
    base = tmp_path / "poc6_19"
    monkeypatch.setattr(MI, "SHA", write_sources(base, p.axis, failed=FAILED_DAYS))
    fx0, *_ = PR.survey(p)
    monkeypatch.setattr(
        PR, "EXPECTED", {k: fx0[k] for k in ("eligible_rows", "signals")}
    )
    fx, *_ = P23.survey(p, base)
    exp = {
        k: fx[k] for k in ("axis", "quarters", "train_upper", "last_train", "label_end")
    }
    exp["common"] = {k: fx["common"][k] for k in ("count", "first", "last")}
    for tag in ("val", "test"):
        exp[tag] = {
            k: fx[tag][k] for k in ("weeks", "start", "end", "k_exec", "last_signal")
        }
    exp["sub_weeks"] = fx["sub_weeks"]
    monkeypatch.setattr(P23, "EXPECTED", exp)
    return {
        "root": tmp_path / "poc6_23",
        "db": path,
        "base": base,
        "clock": _Clock(),
        "fx": fx,
        "p": p,
    }


def _prepare(s):
    return FW.prepare(s["root"], s["db"], REPO, s["clock"], market_base=s["base"])


def _run(s):
    _prepare(s)
    return FW.run(s["root"], s["db"], REPO, s["clock"], market_base=s["base"])


def _rdir(s, res):
    return next(s["root"].glob(f"*/runs/{res['meta']['run_id']}"))


def _verify(s):
    return VR.verify(s["root"], s["db"], REPO, clock=s["clock"], market_base=s["base"])


# ── 분모 · 정상 흐름 ────────────────────────────────────────────────────────────


def test_survey_windows_and_plan_table(study):
    fx = study["fx"]
    assert fx["quarters"] == 6 and fx["fits"] == 12 and not fx["data_short"]
    assert fx["common"]["first"] and fx["label_end"]
    assert all(q["upper"] >= 3 for q in fx["quarter_detail"])
    assert P23.compare(fx) == []
    p = study["p"]
    pos = {d: k for k, d in enumerate(p.axis)}
    for q in fx["quarter_detail"]:
        assert pos[q["last"]] + LB.T_LAG <= pos[q["cutoff"]] - P23.MATURE
        assert q["first"] >= q["lo"]


def test_end_to_end_ok_and_verify_ok(study):
    res = _run(study)
    meta, rep = res["meta"], res["report"]
    assert meta["status"] == "OK", rep.get("stop")
    rdir = _rdir(study, res)
    names = {str(f.relative_to(rdir)) for f in rdir.rglob("*") if f.is_file()}
    assert VR.FIXED | {"run.json"} <= names
    assert {f"models/{q['id']}.json" for q in study["fx"]["quarter_detail"]} <= names
    assert {
        n for n in names if n.startswith(("validation/", "test/"))
    } == VR._book_files()
    ref = rep["reference"]
    assert ref["status"] == "OK" and ref["same_as_poc6_21"] is True
    assert ref["start"] == study["fx"]["common"]["first"]
    assert len(rep["learning"]) == 6 and all(r["valid"] >= 3 for r in rep["learning"])
    for r in rep["learning"]:
        assert r["P"]["status"] == r["S"]["status"] == 0
        assert r["P"]["abs_diff"] <= LN.TOL and r["S"]["abs_diff"] <= LN.TOL
    j = rep["judgment"]
    assert j["validity"] == "OK" and j["OPERATION_ADOPTION"] == "NO"
    assert j["candidate"] in ("FURTHER_REVIEW_CANDIDATE", "NOT_CANDIDATE")
    for name in ("P_20", "S_20"):
        bk = PR.load_json(rdir / "test" / f"{name}.json")
        assert bk["plans"][0]["first"] is True and all(
            "chosen" in pl for pl in bk["plans"][1:]
        )
    for r in rep[
        "learning"
    ]:  # flow 의 유효 D 선택 = protocol 의 창 상한(정답 제외만큼 빠짐)
        assert r["valid"] + sum(r["excluded"].values()) == r["upper"]
    _fx, el, _mkt, _common = P23.survey(study["p"], study["base"])
    ends = {study["p"].axis[i] for i in el.sig}
    led = PR.load_json(rdir / "test" / "S_20.json")["ledger"]
    assert rep["bootstrap"]["weeks"] == sum(1 for r in led if r["date"] in ends)
    labels = json.loads(gzip.decompress((rdir / "labels.json.gz").read_bytes()))
    assert all(r["g"] is None or r["g"][0] == 0.0 for r in labels.values())
    v = _verify(study)
    assert v["status"] == "OK", v["problems"]


def test_models_share_statistics_and_forty_bp_uses_same_beta(study):
    res = _run(study)
    rdir = _rdir(study, res)
    doc = PR.load_json(
        rdir / "models" / f"{study['fx']['quarter_detail'][-1]['id']}.json"
    )
    assert len(doc["P"]["beta"]) == len(doc["S"]["beta"]) == 70
    assert doc["s_g"] >= LN.SG_MIN and len(doc["mu"]) == 34
    b20 = PR.load_json(rdir / "test" / "S_20.json")
    b40 = PR.load_json(rdir / "test" / "S_40.json")
    assert {pl["model"] for pl in b20["plans"][1:]} == {
        pl["model"] for pl in b40["plans"][1:]
    }
    assert b40["cost"] == PR.ALT_COST


# ── 정지 경로 ───────────────────────────────────────────────────────────────────


def test_all_dates_excluded_is_insufficient_data(study, monkeypatch):
    real = LB.label

    def none(p, pl, snap, payload, i, cost):
        rec = real(p, pl, snap, payload, i, cost)
        rec.update(excluded="BRANCH_UNRESOLVED", g=None)
        rec.pop("nav_t", None)
        return rec

    monkeypatch.setattr(LB, "label", none)
    res = _run(study)
    assert res["meta"]["status"] == "INSUFFICIENT_DATA"
    assert res["report"]["stop"].startswith(FW.SHORT_STOP.split("{")[0])
    v = _verify(study)
    assert v["status"] == "OK", v["problems"]


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
    assert res["report"]["stop"] == FW.VAL_STOP.format(bad=["K_20"])
    rdir = _rdir(study, res)
    assert not (rdir / "test").exists()
    assert res["report"]["judgment"]["candidate"] == "NOT_JUDGED"
    v = _verify(study)
    assert v["status"] == "OK", v["problems"]


def test_numeric_condition_failure_keeps_model_and_stops(study, monkeypatch):
    monkeypatch.setattr(
        LN, "TOL", -1.0
    )  # 어떤 해도 통과 못 하는 허용오차 = 수치 실패 장면
    res = _run(study)
    first = study["fx"]["quarter_detail"][0]["id"]
    assert res["meta"]["status"] == "CHECK_REQUIRED"
    assert res["report"]["stop"].startswith(f"CheckRequired: {first} 수치 조건: ")
    rdir = _rdir(study, res)
    assert [f.name for f in (rdir / "models").glob("*.json")] == [f"{first}.json"]
    assert not (rdir / "validation").exists()
    v = _verify(study)
    assert v["status"] == "OK", v["problems"]


def test_run_once_and_prepare_once(study):
    _run(study)
    with pytest.raises(PR.Refused):
        FW.run(
            study["root"], study["db"], REPO, study["clock"], market_base=study["base"]
        )
    with pytest.raises(PR.Refused):
        _prepare(study)


def test_prepare_refuses_when_plan_table_differs(study, monkeypatch):
    exp = json.loads(json.dumps(P23.EXPECTED))
    exp["train_upper"][next(iter(exp["train_upper"]))] += 1
    monkeypatch.setattr(P23, "EXPECTED", exp)
    with pytest.raises(D.CheckRequired, match="PLAN 표와 다름"):
        _prepare(study)
    assert not study["root"].exists() or not P8.locks(study["root"])


@pytest.mark.parametrize(
    "change",
    [{"scipy": "1.17.0"}, {"highs": None}, {"threads_env": {"OMP_NUM_THREADS": "8"}}],
)
def test_prepare_refuses_other_environment(study, monkeypatch, change):
    env = {**P23.runtime_env(), **change}
    monkeypatch.setattr(P23, "runtime_env", lambda: env)
    with pytest.raises(D.CheckRequired, match="환경 확인 전"):
        _prepare(study)


def test_run_refuses_when_environment_changed_after_lock(study, monkeypatch):
    _prepare(study)
    env = {**P23.runtime_env(), "numpy": "2.4.5"}
    monkeypatch.setattr(P23, "runtime_env", lambda: env)
    with pytest.raises(D.CheckRequired, match="환경"):
        FW.run(
            study["root"], study["db"], REPO, study["clock"], market_base=study["base"]
        )


def test_cli_verify_without_lock_is_check_required(tmp_path, monkeypatch, capsys):
    sys.path.insert(0, str(REPO / "scripts"))
    import run_decision_learning as CLI

    monkeypatch.setattr(CLI, "REPO", tmp_path)
    rc = CLI.main(["verify"])
    out = capsys.readouterr().out.strip().splitlines()[-1]
    assert rc == 2 and out.startswith("RESULT ") and '"CHECK_REQUIRED"' in out
    for k in P23.THREAD_ENV:
        assert os.environ[k] == "1"


# ── verify 변조 검출 ────────────────────────────────────────────────────────────


def _write_json(path: Path, obj) -> None:
    if path.exists():
        os.chmod(path, 0o644)
    path.write_bytes(P8.dumps(obj))


def _write_gz(path: Path, obj) -> None:
    os.chmod(path, 0o644)
    path.write_bytes(gzip.compress(P8.dumps(obj, compact=True), mtime=0))


def _refresh_manifest(rdir: Path) -> None:
    meta = PR.load_json(rdir / "run.json")
    meta["files"] = PR.manifest(rdir)
    _write_json(rdir / "run.json", meta)


def _forge_beta(rdir: Path) -> None:
    f = sorted((rdir / "models").glob("*.json"))[-1]
    doc = PR.load_json(f)
    doc["S"]["beta"][0] += 0.01
    _write_json(f, doc)
    _refresh_manifest(rdir)


def _forge_solution(rdir: Path) -> None:
    f = sorted((rdir / "models").glob("*.json"))[0]
    doc = PR.load_json(f)
    doc["P"]["x"][-1] += 0.5
    _write_json(f, doc)
    _refresh_manifest(rdir)


def _forge_stats(rdir: Path) -> None:
    f = sorted((rdir / "models").glob("*.json"))[0]
    doc = PR.load_json(f)
    doc["mu"][0] += 1.0
    _write_json(f, doc)
    _refresh_manifest(rdir)


def _forge_label(rdir: Path) -> None:
    f = rdir / "labels.json.gz"
    doc = json.loads(gzip.decompress(f.read_bytes()))
    d = next(d for d, r in doc.items() if r["g"] is not None and len(r["g"]) > 1)
    doc[d]["g"][1] += 0.001
    _write_gz(f, doc)
    _refresh_manifest(rdir)


def _forge_reference(rdir: Path) -> None:
    f = rdir / "reference.json"
    bk = PR.load_json(f)
    bk["ledger"][-1]["value"] *= 1.01
    _write_json(f, bk)
    _refresh_manifest(rdir)


def _forge_choice(rdir: Path) -> None:
    f = rdir / "test" / "S_20.json"
    bk = PR.load_json(f)
    pl = next(pl for pl in bk["plans"][1:] if len(pl["actions"]) > 1)
    pl["actions"][0][1] += 1.0
    _write_json(f, bk)
    _refresh_manifest(rdir)


def _second_run(rdir: Path) -> None:
    shutil.copytree(rdir, rdir.parent / (rdir.name[:-1] + "z"))


def _forge_stages(rdir: Path) -> None:
    meta = PR.load_json(rdir / "run.json")
    meta["stages"] = list(reversed(meta["stages"]))
    _write_json(rdir / "run.json", meta)


def _extra_file(rdir: Path) -> None:
    (rdir / "models" / "notes.json").write_text("{}", encoding="utf-8")
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


def _judgment(rep):
    rep["judgment"]["candidate"] = (
        "NOT_CANDIDATE"
        if rep["judgment"]["candidate"] == "FURTHER_REVIEW_CANDIDATE"
        else "FURTHER_REVIEW_CANDIDATE"
    )


def _learning(rep):
    rep["learning"][0]["valid"] += 1


@pytest.mark.parametrize(
    "tamper,expect",
    [
        (_forge_beta, "정책 재적용"),
        (_forge_solution, "저장 해로 다시 잰 값"),
        (_forge_stats, "표준화"),
        (_forge_label, "labels.json.gz"),
        (_forge_reference, "reference.json"),
        (_forge_choice, "행동 점수"),
        (_second_run, "실행이 2개"),
        (_forge_stages, "단계"),
        (_extra_file, "계약 밖 파일"),
        (_report_change(_judgment), "판정"),
        (_report_change(_learning), "learning"),
    ],
)
def test_verify_catches_forged_or_broken_records(study, tamper, expect):
    res = _run(study)
    assert res["meta"]["status"] == "OK"
    tamper(_rdir(study, res))
    v = _verify(study)
    assert v["status"] == "MISMATCH" and expect in " | ".join(v["problems"]), v[
        "problems"
    ]


# ── 모든 계산 뒤 예산 상한(F1/F2) ───────────────────────────────────────────────


@pytest.mark.parametrize("slow", ["bootstrap", "markdown", "manifest"])
def test_budget_over_after_last_computation_becomes_budget_stop(
    study, monkeypatch, slow
):
    target = {
        "bootstrap": (FW, "pair_bootstrap"),
        "markdown": (RP, "markdown"),
        "manifest": (PR, "manifest"),
    }[slow]
    real = getattr(*target)
    state = {"done": False}

    def slow_fn(*a, **k):
        out = real(*a, **k)
        if not state["done"]:
            state["done"] = True
            study["clock"].t += dt.timedelta(seconds=PR.BUDGET_S + 1)
        return out

    monkeypatch.setattr(*target, slow_fn)
    res = _run(study)
    rep, meta = res["report"], res["meta"]
    assert meta["status"] == "BUDGET_STOP", rep.get("stop")
    assert rep["stop"].startswith("BudgetStop: finish:")
    assert rep["judgment"]["candidate"] == "NOT_JUDGED"
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


# ── 실행 전 독립 검토 지적 보강(정지 경로 · 시간순 · CLI) ─────────────────────────


def test_budget_stop_inside_fit_keeps_learning_row_and_verifies(study, monkeypatch):
    real = LN.fit
    calls = {"n": 0}

    def slow(pb, kind):
        rec = real(pb, kind)
        calls["n"] += 1
        if calls["n"] == 4:  # 둘째 분기 S 를 푼 직후 상한을 넘긴다
            study["clock"].t += dt.timedelta(seconds=PR.BUDGET_S + 1)
        return rec

    monkeypatch.setattr(LN, "fit", slow)
    res = _run(study)
    q2 = study["fx"]["quarter_detail"][1]["id"]
    assert res["meta"]["status"] == "BUDGET_STOP"
    assert res["report"]["stop"].startswith(f"BudgetStop: fit {q2}:")
    row = res["report"]["learning"][1]
    assert row["id"] == q2 and row["P"]["status"] == row["S"]["status"] == 0
    v = _verify(study)
    assert v["status"] == "OK", v["problems"]


def test_check_required_inside_a_book_keeps_written_book_metrics(study, monkeypatch):
    from app.decision_learning import policy as PL

    real = PL.check_bounds

    def flaky(p, st, i):
        if st.bk.curve == "S_20" and st.first_plan_done:
            raise D.CheckRequired("가짜 슬롯 위반")
        return real(p, st, i)

    monkeypatch.setattr(PL, "check_bounds", flaky)
    res = _run(study)
    rep = res["report"]
    assert res["meta"]["status"] == "CHECK_REQUIRED"
    assert rep["stop"] == "CheckRequired: 가짜 슬롯 위반"
    rdir = _rdir(study, res)
    assert [f.name for f in (rdir / "validation").glob("*.json")] == ["P_20.json"]
    assert set(rep["validation"]) == {"P_20"} and set(rep["validation_trades"]) == {
        "P_20"
    }
    v = _verify(study)  # 같은 변이 아래 다시 돌려 같은 정지가 재현됨
    assert v["status"] == "OK", v["problems"]


def test_solver_failure_without_solution_is_a_numeric_stop_and_verifies(
    study, monkeypatch
):
    real = LN.solve
    calls = {"n": 0}

    class _Res:
        status, message, nit, x, fun = 4, "HiGHS Status 0: Not Set", 0, None, None

    def broken(c, A_ub, b_ub):
        calls["n"] += 1
        return (_Res(), 1) if calls["n"] == 2 else real(c, A_ub, b_ub)

    monkeypatch.setattr(LN, "solve", broken)
    res = _run(study)
    q1 = study["fx"]["quarter_detail"][0]["id"]
    assert res["meta"]["status"] == "CHECK_REQUIRED"
    assert res["report"]["stop"].startswith(
        f"CheckRequired: {q1} 수치 조건: S solver 비정상 종료"
    )
    v = _verify(study)
    assert v["status"] == "OK", v["problems"]


def test_verify_rejects_ok_run_relabelled_as_generic_check_required(study):
    res = _run(study)
    rdir = _rdir(study, res)
    meta = PR.load_json(rdir / "run.json")
    meta["status"] = "CHECK_REQUIRED"
    _write_json(rdir / "run.json", meta)
    rep = PR.load_json(rdir / "report.json")
    for k in ("bootstrap", "bootstrap_tail_excluded"):
        rep.pop(k)
    rep["judgment"] = RP.judge("CHECK_REQUIRED", None, None, None)
    rep["stop"] = "CheckRequired: 가짜 정지"
    _write_json(rdir / "report.json", rep)
    os.chmod(rdir / "report.md", 0o644)
    (rdir / "report.md").write_text(RP.markdown(rep), encoding="utf-8")
    _refresh_manifest(rdir)
    v = _verify(study)
    assert v["status"] == "MISMATCH" and any(
        "재현하지 못함" in x for x in v["problems"]
    )


def test_training_windows_by_hand_and_no_future_label_in_assigned_model(study):
    """창 경계를 코드 상수가 아닌 손 숫자(21 · 20 · 5년)로 다시 세고, 배정 모형의 정답 끝이 쓰는 신호보다 앞인지."""
    p, fx = study["p"], study["fx"]
    _fx, _el, _mkt, common = P23.survey(p, study["base"])
    pos = {d: k for k, d in enumerate(p.axis)}
    for q in fx["quarter_detail"]:
        y, n = int(q["id"][:4]), int(q["id"][-1])
        start = dt.date(y, 3 * (n - 1) + 1, 1)
        lo = dt.date(y - 5, start.month, 1).isoformat()
        cut = max(i for i, d in enumerate(p.axis) if d < start.isoformat())
        ds = [i for i in common if p.axis[i] >= lo and i + 21 <= cut - 20]
        assert (q["lo"], q["cutoff"], q["upper"]) == (lo, p.axis[cut], len(ds))
        assert (q["first"], q["last"]) == (p.axis[ds[0]], p.axis[ds[-1]])
        later = [i for i in common if i > ds[-1]]
        assert not later or later[0] + 21 > cut - 20  # 바로 다음 공통 신호는 성숙 안 됨
    by_id = {q["id"]: q for q in fx["quarter_detail"]}
    for d, qid in fx["assign"].items():
        assert pos[by_id[qid]["last"]] + 21 <= pos[d] - 20


def test_min_dates_boundary_exact_passes_one_more_stops(study, monkeypatch, tmp_path):
    res = _run(study)
    m = min(r["valid"] for r in res["report"]["learning"])
    for k, want_ok in ((m, True), (m + 1, False)):
        monkeypatch.setattr(P23, "MIN_DATES", k)
        s2 = {**study, "root": tmp_path / f"min_{k}"}
        got = _run(s2)["meta"]["status"]
        assert (got == "OK") is want_ok, (k, got)
        if not want_ok:
            assert got in ("INSUFFICIENT_DATA", "DATA_SHORT")


def test_cli_sets_thread_env_before_any_numeric_import():
    src = (
        (REPO / "scripts" / "run_decision_learning.py")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    env_line = next(k for k, s in enumerate(src) if s.startswith("for _k in ("))
    first_import = next(
        k
        for k, s in enumerate(src)
        if s.startswith(("import numpy", "import scipy", "from app", "import app"))
    )
    assert env_line < first_import
