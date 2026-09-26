"""POC4-03 러너 — 02A 기준 대조 · 선형 재현 게이트 · 자원 상한 · 라이브 경로 · 재개 · compare · summarize.

tmp 프로젝트 루트 · KRX 스키마 고정 DB · 02A 러너로 만든 tmp 기준 폴더만 쓴다(`project_root`·`reference_expect`
주입). 봉인 DB·라이브 경로는 열지 않는다.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import shutil
import socket
import sys
from pathlib import Path

import pytest

from app import research_run_guard as guard
from app import ml_rf_gate_verdict as vd
from app.ml_baseline_snapshot import SnapshotIntegrityError
from app.ml_score_validity_report import canonical_sha256
from tests._krx_fixture import build_sealed_db
from tests.test_poc4_02a_pit_runner import E2_DATES, clean_rows
from tests.test_poc4_02a_pit_runner import runner as runner_02a

ROOT = Path(__file__).resolve().parent.parent


def _load_runner():
    name = "run_poc4_03_rf_kill_gate"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / "run_poc4_03_rf_kill_gate.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


def _make_root(base: Path) -> Path:
    root = base / "root"
    (root / "state" / "market").mkdir(parents=True)
    (root / "state" / "runs").mkdir()
    (root / "logs").mkdir()
    (root / "state" / "market" / "market_data.sqlite").write_bytes(b"live market db")
    (root / "logs" / "oci_market_data_batch.log").write_text("batch\n", "utf-8")
    return root


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    """고정 DB · e2 manifest · 02A 러너로 만든 기준 폴더 (모듈에서 한 번)."""
    base = tmp_path_factory.mktemp("p403run")
    db = base / "krx.sqlite"
    build_sealed_db(db, clean_rows())
    e2 = base / "dataset_manifest.json"
    e2.write_text(json.dumps({"evaluation_calendar": {"e2_dates": E2_DATES}}), "utf-8")
    ref = base / "ref02a"
    argv = [
        "run",
        "--out-dir",
        str(ref),
        "--sealed-db",
        str(db),
        "--e2-manifest",
        str(e2),
    ]
    assert runner_02a.main(argv, project_root=_make_root(base / "r02a")) == 0
    return {"db": db, "e2": e2, "ref": ref}


@pytest.fixture
def env(tmp_path, base):
    db = tmp_path / "krx.sqlite"
    shutil.copyfile(base["db"], db)
    return {
        "root": _make_root(tmp_path),
        "db": db,
        "e2": base["e2"],
        "ref": base["ref"],
        "runs": tmp_path / "runs",
        "expect": runner.reference_digest(base["ref"], base["e2"]),
    }


def run(env, name, *extra, arm="PIT", ref=None, expect=None, limits=None):
    argv = ["run", "--arm", arm, "--out-dir", str(env["runs"] / name)]
    argv += ["--sealed-db", str(env["db"]), "--e2-manifest", str(env["e2"])]
    argv += ["--reference-dir", str(ref or env["ref"]), *extra]
    kw = {"project_root": env["root"], "reference_expect": expect or env["expect"]}
    if limits is not None:
        kw["limits"] = limits
    return runner.main(argv, **kw)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _guard(env, name) -> dict:
    return _json(env["runs"] / name / guard.GUARD_FAILED)


# --- 새 실행 --------------------------------------------------------------------------------


def test_pit_run_writes_result_with_candidate_and_linear_hashes(env):
    assert run(env, "p1") == 0
    out = env["runs"] / "p1"
    progress = sorted(p.name for p in (out / runner.PROGRESS_DIR).iterdir())
    assert progress == [f"PIT_{d}.json" for d in E2_DATES]
    res = _json(out / guard.RESULT)
    assert res["official"] is True and res["arm"] == "PIT"
    assert res["verdict_candidate"]["verdict"] in vd.VERDICTS
    assert res["determinism"]["canonical_sha256"] == canonical_sha256(
        res, exclude=vd.CANONICAL_EXCLUDED
    )
    assert set(res["models"]) == {"LIN", "MOM", "RF_A", "RF_B", "RF_C", "RF_PRIMARY"}
    assert res["recipe"]["rf_config_sha256"] == runner.rfm.FROZEN_CONFIG_SHA256
    assert res["recipe"]["bootstrap"]["iterations"] == 10000
    for day in res["per_date"]:
        ref = _json(env["ref"] / "progress" / f"PIT_{day['signal_date']}.json")
        text = runner.canon(ref["record"])
        assert (
            day["linear_canonical_sha256"] == hashlib.sha256(text.encode()).hexdigest()
        )
    meta = _json(out / guard.RUN_META)
    assert meta["resumed"] is False and meta["progress_computed"] == 2
    manifest = _json(out / guard.RUN_MANIFEST)
    assert manifest["fingerprint"]["rf_config_sha256"] == runner.rfm.config_sha256()
    assert "scikit-learn" in manifest["fingerprint"]["packages"]
    assert "joblib" in manifest["fingerprint"]["packages"]
    assert manifest["fingerprint"]["recipe_sha256"] == vd.FROZEN_RECIPE_SHA256


def test_control_run_writes_no_verdict_candidate(env):
    assert run(env, "c1", arm="CONTROL") == 0
    res = _json(env["runs"] / "c1" / guard.RESULT)
    assert res["arm"] == "CONTROL" and res["verdict_candidate"] is None
    assert "CONTROL 진단" in res["verdict_role"]


def test_existing_folder_and_live_path_are_refused(env):
    assert run(env, "p1") == 0
    with pytest.raises(SnapshotIntegrityError, match="새 폴더"):
        run(env, "p1")
    argv = [
        "run",
        "--arm",
        "PIT",
        "--out-dir",
        str(env["root"] / "state" / "runs" / "x"),
    ]
    with pytest.raises(guard.RunnerError, match="라이브 경로"):
        runner.main(argv, project_root=env["root"], reference_expect=env["expect"])


# --- 시작 전 거부 ----------------------------------------------------------------------------


def test_reference_mismatch_refuses_start(env):
    bad = {**env["expect"], "result_json_sha256": "0" * 64}
    with pytest.raises(guard.RunnerError, match="02A 기준 산출물"):
        run(env, "p1", expect=bad)
    assert not (env["runs"] / "p1").exists()


def test_force_cpu_env_is_refused(env, monkeypatch):
    monkeypatch.setenv(runner.FORCE_CPU_ENV, "true")
    with pytest.raises(guard.RunnerError, match="FORCE_CPU"):
        run(env, "p1")


def test_changed_rf_config_is_refused(env, monkeypatch):
    rf = runner.rfm.RF_CONFIGS["RF_A"]
    monkeypatch.setitem(runner.rfm.RF_CONFIGS, "RF_A", {**rf, "max_depth": 5})
    with pytest.raises(runner.rfm.RfContractError, match="동결값"):
        run(env, "p1")


# --- 실행 중 가드 -----------------------------------------------------------------------------


def test_linear_mismatch_stops_before_models_and_marks_guard(env, tmp_path):
    ref = tmp_path / "ref_tampered"
    shutil.copytree(env["ref"], ref)
    path = ref / "progress" / f"PIT_{E2_DATES[1]}.json"
    unit = _json(path)
    unit["record"]["ic_filter"] += 1e-12
    path.write_text(json.dumps(unit), "utf-8")
    expect = runner.reference_digest(ref, env["e2"])
    with pytest.raises(runner.ReproductionError, match="02A 기준 기록과 다르다"):
        run(env, "p1", ref=ref, expect=expect)
    out = env["runs"] / "p1"
    assert _guard(env, "p1")["guard"] == "LINEAR_REPRODUCTION_FAILED"
    assert sorted(p.name for p in (out / runner.PROGRESS_DIR).iterdir()) == [
        f"PIT_{E2_DATES[0]}.json"
    ]
    assert not (out / guard.RESULT).exists()
    with pytest.raises(guard.RunnerError, match="재개하지 않는다"):
        run(env, "p1", "--resume", ref=ref, expect=expect)


@pytest.mark.parametrize("limits", [(-1, 10 * 10**9), (4 * 3600, 1)])
def test_resource_limit_stops_with_guard(env, limits):
    with pytest.raises(guard.ResourceLimitError):
        run(env, "p1", limits=limits)
    assert _guard(env, "p1")["guard"] == "RESOURCE_LIMIT"
    assert not (env["runs"] / "p1" / guard.RESULT).exists()


def test_live_path_change_blocks_result(env, monkeypatch):
    real = runner.evaluate_point_models

    def touch(*args, **kwargs):
        (env["root"] / "logs" / "three_push_runtime_cron.log").write_text("x", "utf-8")
        return real(*args, **kwargs)

    monkeypatch.setattr(runner, "evaluate_point_models", touch)
    with pytest.raises(guard.RunnerError, match="라이브 경로가 바뀌었다"):
        run(env, "p1")
    assert _guard(env, "p1")["guard"] == "LIVE_PATHS_CHANGED"
    assert not (env["runs"] / "p1" / guard.RESULT).exists()


def test_run_makes_no_network_calls(env, monkeypatch):
    def refuse(*_a, **_k):
        raise AssertionError("외부 네트워크 호출")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    assert run(env, "p1") == 0


def test_logs_do_not_print_model_metrics(env, caplog):
    with caplog.at_level(logging.INFO, logger="poc4_03_rf_kill_gate"):
        assert run(env, "p1") == 0
    lines = [r.getMessage() for r in caplog.records if r.name == "poc4_03_rf_kill_gate"]
    assert lines and not any("ic=" in m or "IC" in m for m in lines)


# --- 재개 · compare · summarize ------------------------------------------------------------


def test_two_fresh_runs_confirm_determinism_and_final_verdict(env):
    assert run(env, "a") == 0 and run(env, "b") == 0
    argv = [
        "compare",
        "--first",
        str(env["runs"] / "a"),
        "--second",
        str(env["runs"] / "b"),
    ]
    assert runner.main(argv) == 0
    cmp_ = _json(env["runs"] / "b" / runner.COMPARE)
    cand = _json(env["runs"] / "a" / guard.RESULT)["verdict_candidate"]
    assert cmp_["determinism_confirmed"] is True and cmp_["final_verdict"] == cand


def test_resume_equals_fresh_but_is_not_determinism_evidence(env, monkeypatch):
    assert run(env, "fresh") == 0
    real, calls = runner.evaluate_point_models, {"n": 0}

    def stop_second(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise KeyboardInterrupt("중단 흉내")
        return real(*args, **kwargs)

    monkeypatch.setattr(runner, "evaluate_point_models", stop_second)
    with pytest.raises(KeyboardInterrupt):
        run(env, "resumed")
    monkeypatch.setattr(runner, "evaluate_point_models", real)
    with pytest.raises(guard.RunnerError, match="입력 지문"):
        run(env, "resumed", "--resume", "--limit-dates", "1")
    assert run(env, "resumed", "--resume") == 0
    a = _json(env["runs"] / "fresh" / guard.RESULT)["determinism"]["canonical_sha256"]
    b = _json(env["runs"] / "resumed" / guard.RESULT)["determinism"]["canonical_sha256"]
    assert a == b
    argv = ["compare", "--first", str(env["runs"] / "fresh"), "--second"]
    assert runner.main([*argv, str(env["runs"] / "resumed")]) == 2
    final = _json(env["runs"] / "resumed" / runner.COMPARE)["final_verdict"]
    assert final["verdict"] == vd.INVALID_STOP and final["failed"] == ["C9"]


def test_compare_refuses_guard_failed_and_mixed_arms(env):
    assert run(env, "p") == 0 and run(env, "c", arm="CONTROL") == 0
    with pytest.raises(guard.RunnerError, match="arm 이 다르다"):
        runner.main(
            [
                "compare",
                "--first",
                str(env["runs"] / "p"),
                "--second",
                str(env["runs"] / "c"),
            ]
        )
    with pytest.raises(guard.ResourceLimitError):
        run(env, "g", limits=(-1, 10 * 10**9))
    with pytest.raises(guard.RunnerError, match="비교하지 않는다"):
        runner.main(
            [
                "compare",
                "--first",
                str(env["runs"] / "p"),
                "--second",
                str(env["runs"] / "g"),
            ]
        )


def _pass(monkeypatch):
    """판정 후보를 PASS 로 고정 — PIT PASS 뒤 CONTROL·summarize 흐름만 본다."""
    monkeypatch.setattr(
        vd, "decide", lambda conds, invalid: vd._verdict(vd.PASS, "테스트", [])
    )


def _compare(env, a, b):
    return runner.main(
        ["compare", "--first", str(env["runs"] / a), "--second", str(env["runs"] / b)]
    )


def test_summarize_after_pit_pass_is_diagnostic_and_does_not_change_pit(
    env, tmp_path, monkeypatch
):
    _pass(monkeypatch)
    assert (
        run(env, "p1") == 0 and run(env, "p2") == 0 and _compare(env, "p1", "p2") == 0
    )
    assert (
        _json(env["runs"] / "p2" / runner.COMPARE)["final_verdict"]["verdict"]
        == vd.PASS
    )
    for name in ("c1", "c2"):
        assert run(env, name, arm="CONTROL") == 0
    assert _compare(env, "c1", "c2") == 0
    before = hashlib.sha256(
        (env["runs"] / "p2" / guard.RESULT).read_bytes()
    ).hexdigest()
    out = tmp_path / "summary.json"
    argv = ["summarize", "--pit", str(env["runs"] / "p2"), "--control"]
    argv += [str(env["runs"] / "c2"), "--out", str(out)]
    assert runner.main(argv, project_root=env["root"]) == 0
    summary = _json(out)
    assert summary["pit_final_verdict"]["verdict"] == vd.PASS
    assert summary["role"].startswith("진단")
    assert set(summary["pit_control_gap"]) == {"ic", "net25"}
    assert set(summary["models"]["RF_PRIMARY"]) == {"PIT", "CONTROL"}
    after = hashlib.sha256((env["runs"] / "p2" / guard.RESULT).read_bytes()).hexdigest()
    assert before == after


def test_summarize_refuses_without_pit_pass_or_compare_or_on_live_path(env, tmp_path):
    assert (
        run(env, "p1") == 0
        and run(env, "p2") == 0
        and _compare(env, "p1", "p2") in (0, 2)
    )
    for name in ("c1", "c2"):
        assert run(env, name, arm="CONTROL") == 0
    _compare(env, "c1", "c2")
    base = [
        "summarize",
        "--pit",
        str(env["runs"] / "p2"),
        "--control",
        str(env["runs"] / "c2"),
    ]
    final = _json(env["runs"] / "p2" / runner.COMPARE)["final_verdict"]["verdict"]
    if final != vd.PASS:
        with pytest.raises(guard.RunnerError, match="PASS 가 아니다"):
            runner.main(
                [*base, "--out", str(tmp_path / "s.json")], project_root=env["root"]
            )
    live = env["root"] / "state" / "runs" / "s.json"
    with pytest.raises(guard.RunnerError, match="라이브 경로"):
        runner.main([*base, "--out", str(live)], project_root=env["root"])
    no_cmp = [
        "summarize",
        "--pit",
        str(env["runs"] / "p1"),
        "--control",
        str(env["runs"] / "c2"),
    ]
    with pytest.raises(guard.RunnerError, match="compare 를 마친"):
        runner.main(
            [*no_cmp, "--out", str(tmp_path / "t.json")], project_root=env["root"]
        )


def test_control_compare_is_invalid_when_control_preflight_blocks(env, monkeypatch):
    real = vd.model_preflight

    def blocked(records):
        out = real(records)
        return {**out, "gate": {**out["gate"], "status": "BLOCKED_LEAKAGE"}}

    monkeypatch.setattr(vd, "model_preflight", blocked)
    for name in ("c1", "c2"):
        assert run(env, name, arm="CONTROL") == 0
    assert _compare(env, "c1", "c2") == 0
    cmp_ = _json(env["runs"] / "c2" / runner.COMPARE)
    assert cmp_["control_diagnostic_valid"] is False and cmp_["control_invalid_reasons"]


def test_compare_same_folder_and_mismatch_are_c9(env):
    assert run(env, "a") == 0 and run(env, "b") == 0
    assert _compare(env, "a", "a") == 2
    final = _json(env["runs"] / "a" / runner.COMPARE)["final_verdict"]
    assert final["failed"] == ["C9"]
    path = env["runs"] / "b" / guard.RESULT
    res = _json(path)
    res["calendar"]["evaluated"] += 1
    res["determinism"]["canonical_sha256"] = None
    res["determinism"]["canonical_sha256"] = canonical_sha256(
        res, exclude=vd.CANONICAL_EXCLUDED
    )
    path.write_text(json.dumps(res), "utf-8")
    assert _compare(env, "a", "b") == 1
    assert _json(env["runs"] / "b" / runner.COMPARE)["final_verdict"]["failed"] == [
        "C9"
    ]


def test_compare_refuses_other_result_schema(env):
    assert run(env, "a") == 0
    argv = ["compare", "--first", str(env["runs"] / "a"), "--second", str(env["ref"])]
    with pytest.raises(guard.RunnerError, match="결과 형식"):
        runner.main(argv)


def test_out_dir_under_reference_is_refused(env):
    argv = ["run", "--arm", "PIT", "--out-dir", str(env["ref"] / "x")]
    argv += ["--reference-dir", str(env["ref"]), "--e2-manifest", str(env["e2"])]
    with pytest.raises(guard.RunnerError, match="기준 산출물 폴더"):
        runner.main(argv, project_root=env["root"], reference_expect=env["expect"])


# --- 추가 가드 경로 ------------------------------------------------------------------------


def test_sealed_change_blocks_result(env, monkeypatch):
    real, calls = runner.verify_sealed_source, {"n": 0}

    def changed(*args, **kwargs):
        calls["n"] += 1
        out = real(*args, **kwargs)
        return {**out, "file_sha256": "0" * 64} if calls["n"] == 2 else out

    monkeypatch.setattr(runner, "verify_sealed_source", changed)
    with pytest.raises(runner.SealedSourceError):
        run(env, "p1")
    assert _guard(env, "p1")["guard"] == "SEALED_SOURCE_CHANGED"
    assert not (env["runs"] / "p1" / guard.RESULT).exists()


def test_reference_change_during_run_blocks_result(env, tmp_path, monkeypatch):
    ref = tmp_path / "ref_copy"
    shutil.copytree(env["ref"], ref)
    expect = runner.reference_digest(ref, env["e2"])
    real = runner.evaluate_point_models

    def touch(*args, **kwargs):
        (ref / "run_manifest_final.json").write_text("{}", "utf-8")
        return real(*args, **kwargs)

    monkeypatch.setattr(runner, "evaluate_point_models", touch)
    with pytest.raises(guard.RunnerError, match="기준 산출물이 바뀌었다"):
        run(env, "p1", ref=ref, expect=expect)
    assert _guard(env, "p1")["guard"] == "REFERENCE_CHANGED"


def test_model_contract_error_marks_guard(env, monkeypatch):
    def broken(*_a, **_k):
        raise runner.rfm.RfContractError("모의 계약 위반")

    monkeypatch.setattr(runner, "evaluate_point_models", broken)
    with pytest.raises(runner.rfm.RfContractError):
        run(env, "p1")
    assert _guard(env, "p1")["guard"] == "MODEL_CONTRACT"


def test_final_resource_check_before_result(env, monkeypatch):
    real, calls = guard.ResourceGuard.check, {"n": 0}

    def third(self):
        calls["n"] += 1
        if calls["n"] == len(E2_DATES) + 1:
            raise guard.ResourceLimitError("모의 초과 — 마지막 검사")
        return real(self)

    monkeypatch.setattr(guard.ResourceGuard, "check", third)
    with pytest.raises(guard.ResourceLimitError):
        run(env, "p1")
    assert _guard(env, "p1")["guard"] == "RESOURCE_LIMIT"
    assert not (env["runs"] / "p1" / guard.RESULT).exists()


def _interrupt_second(monkeypatch):
    real, calls = runner.evaluate_point_models, {"n": 0}

    def stop(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise KeyboardInterrupt("중단 흉내")
        return real(*args, **kwargs)

    monkeypatch.setattr(runner, "evaluate_point_models", stop)
    return real


def test_resume_refuses_live_change_and_bad_progress(env, monkeypatch):
    real = _interrupt_second(monkeypatch)
    with pytest.raises(KeyboardInterrupt):
        run(env, "r1")
    monkeypatch.setattr(runner, "evaluate_point_models", real)
    (env["root"] / "logs" / "oci_market_data_batch.log").write_text("changed", "utf-8")
    with pytest.raises(guard.RunnerError, match="재개 전에 라이브"):
        run(env, "r1", "--resume")
    assert _guard(env, "r1")["guard"] == "LIVE_PATHS_CHANGED"
    (env["root"] / "logs" / "oci_market_data_batch.log").write_text("batch\n", "utf-8")
    _interrupt_second(monkeypatch)
    with pytest.raises(KeyboardInterrupt):
        run(env, "r2")
    monkeypatch.setattr(runner, "evaluate_point_models", real)
    path = env["runs"] / "r2" / runner.PROGRESS_DIR / f"PIT_{E2_DATES[0]}.json"
    unit = _json(path)
    unit["signal_date"] = "2099-01-01"
    path.write_text(json.dumps(unit), "utf-8")
    with pytest.raises(guard.RunnerError, match="progress 기록"):
        run(env, "r2", "--resume")
