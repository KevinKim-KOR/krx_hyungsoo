"""POC4-02A 러너 — 새 폴더 · 기존 폴더 거부 · 재개 · 지문 · 배타 쓰기 · 라이브 경로 · 봉인 변경 · compare
· manifest 뒷부분(날짜별 분할·canonical hash) · 벤치마크 source · 외부 네트워크 0.

모두 tmp_path 의 KRX 스키마 고정 DB 와 tmp 프로젝트 루트만 쓴다(`project_root` 주입). 봉인 DB·라이브
경로는 열지 않는다.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import socket
import sqlite3
import sys
from pathlib import Path

import pytest

from app import ml_pit_bias_eval as pit_eval
from app.krx_sealed_reader import BENCHMARK_CODE, SealedSourceError
from app.ml_baseline_snapshot import SnapshotGuardError, SnapshotIntegrityError
from app.ml_score_validity_report import canonical_sha256
from tests._krx_fixture import build_sealed_db, rows_by_date
from tests.test_poc4_02a_pit_bias import make_code, reasons_rows

ROOT = Path(__file__).resolve().parent.parent
E2_DATES = ["2014-06-30", "2014-07-31"]


def _load_runner():
    name = "run_poc4_02a_pit_bias"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / "run_poc4_02a_pit_bias.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


def clean_rows(n_codes: int = 40) -> dict:
    maps = [make_code(BENCHMARK_CODE, seed=1, name="KODEX 200")]
    maps += [make_code(f"B{k:05d}", seed=5000 + k) for k in range(n_codes)]
    # D00009 — 2014-07-31 신호일에 청산가 없음 (PIT 전용)
    maps.append(make_code("D00009", 0, 160, seed=4001))
    maps.append(make_code("N00009", 140, seed=4002))  # 06-30 에 CONTROL 미상장
    return rows_by_date(*maps)


@pytest.fixture(scope="module")
def clean_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("krx02a_clean") / "krx.sqlite"
    build_sealed_db(path, clean_rows())
    return path


@pytest.fixture
def env(tmp_path, clean_db):
    """tmp 프로젝트 루트(라이브 5경로 흉내) · e2 manifest · 봉인 DB 사본."""
    root = tmp_path / "root"
    (root / "state" / "market").mkdir(parents=True)
    (root / "state" / "runs").mkdir()
    (root / "logs").mkdir()
    (root / "state" / "market" / "market_data.sqlite").write_bytes(b"live market db")
    (root / "logs" / "oci_market_data_batch.log").write_text(
        "batch\n", encoding="utf-8"
    )
    e2 = tmp_path / "dataset_manifest.json"
    e2.write_text(json.dumps({"evaluation_calendar": {"e2_dates": E2_DATES}}), "utf-8")
    db = tmp_path / "krx.sqlite"
    shutil.copyfile(clean_db, db)
    return {"root": root, "e2": e2, "db": db, "runs": tmp_path / "runs"}


def run(env, name, *extra, db=None, e2=None):
    argv = ["run", "--out-dir", str(env["runs"] / name)]
    argv += ["--sealed-db", str(db or env["db"]), "--e2-manifest", str(e2 or env["e2"])]
    return runner.main([*argv, *extra], project_root=env["root"])


def _result(env, name) -> dict:
    return json.loads((env["runs"] / name / runner.RESULT).read_text(encoding="utf-8"))


def _tree(folder: Path) -> dict:
    return {
        str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def _fail_on_call(monkeypatch, n, action=None):
    """n 번째 evaluate_point 호출에서 멈춘다(또는 action 실행 후 진행)."""
    real, calls = runner.evaluate_point, {"n": 0}

    def wrapped(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == n:
            if action is None:
                raise RuntimeError("중단 흉내")
            action()
        return real(*args, **kwargs)

    monkeypatch.setattr(runner, "evaluate_point", wrapped)
    return real


# --- 새 실행 ---------------------------------------------------------------------------


def test_new_run_writes_result_and_refuses_existing_folder(env):
    assert run(env, "a") == 0
    out = env["runs"] / "a"
    progress = sorted(p.name for p in (out / runner.PROGRESS_DIR).iterdir())
    assert progress == [
        f"{arm}_{d}.json" for arm in ("CONTROL", "PIT") for d in E2_DATES
    ]
    result = _result(env, "a")
    assert result["official"] is True and result["price_basis"] == "KRX_BASEPRICE_CHAIN"
    assert result["official_labels"]["survivorship_status"] == "REDUCED_NOT_ELIMINATED"
    assert result["determinism"]["canonical_sha256"] == canonical_sha256(
        result, exclude=("generated_at",)
    )
    assert result["source"]["before"] == result["source"]["after"]
    for arm in ("PIT", "CONTROL"):
        block = result["arms"][arm]
        assert block["status"] == "MEASURED"
        for sp in (
            block["metrics"]["strategy_performance"],
            block["metrics"]["sensitivity"]["strategy_performance"],
        ):
            assert sp["price_basis"] == "KRX_BASEPRICE_CHAIN"
        assert all("_scores" not in r for r in result["per_date"][arm])
    assert (
        result["arms"]["PIT"]["counts"]["reasons_prefilter"]["NO_FORWARD_EXIT_PRICE"]
        == 1
    )
    assert (
        result["arms"]["CONTROL"]["counts"]["reasons_prefilter"]["NOT_YET_LISTED"] == 1
    )
    effect = result["survivorship_effect"]
    assert effect["status"] == "PRODUCED"
    assert effect["per_date_paired"]["ic_filter"]["n_paired"] == 2
    assert [r["signal_date"] for r in result["cross_coverage"]] == E2_DATES
    manifest = json.loads((out / runner.RUN_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["fingerprint_sha256"] and "code_committed" in manifest["code"]
    assert manifest["external_calls"] == 0
    assert manifest["final_manifest"] == runner.RUN_MANIFEST_FINAL
    _assert_final_manifest(out, manifest, result)
    meta = json.loads((out / runner.RUN_META).read_text(encoding="utf-8"))
    assert meta["progress_computed"] == 4 and meta["resumed"] is False
    before = _tree(out)
    with pytest.raises(SnapshotIntegrityError, match="이미 있다"):
        run(env, "a")
    with pytest.raises(runner.RunnerError, match="이미 끝난"):
        run(env, "a", "--resume")
    assert _tree(out) == before


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_final_manifest(out: Path, manifest: dict, result: dict) -> None:
    """판정 A2 · PLAN §4 — manifest 에 결과 canonical hash · 날짜별 경계 · 실제 학습 행 수 · 마지막 학습일."""
    final = json.loads((out / runner.RUN_MANIFEST_FINAL).read_text(encoding="utf-8"))
    canonical = result["determinism"]["canonical_sha256"]
    assert final["result"]["canonical_sha256"] == canonical
    assert final["result"]["file_sha256"] == _sha(out / runner.RESULT)
    assert final["run_manifest_sha256"] == _sha(out / runner.RUN_MANIFEST)
    assert final["fingerprint_sha256"] == manifest["fingerprint_sha256"]
    assert final["live_paths"]["run_start"] == manifest["live_paths_before"]
    assert final["live_paths"]["after"] == manifest["live_paths_before"]
    assert final["sealed_source_after"] == result["source"]["after"]
    split = final["split_by_date"]
    for arm in ("PIT", "CONTROL"):
        assert [e["signal_date"] for e in split[arm]] == E2_DATES
        for e, rec in zip(split[arm], result["per_date"][arm]):
            assert e["trainer_train_row_count"] == e["train_rows"] > 0
            assert e["train_row_count"] == rec["train_row_count"] == e["train_rows"]
            assert e["last_train_date"] == e["train_last_date"] < e["validation_start"]
            assert e["purged_days"] == 20 and e["device"]
            assert e["split_fingerprint"] == rec["split"]["split_fingerprint"]
            assert e["max_target_end_date"] <= e["signal_date"]
    for p, c in zip(split["PIT"], split["CONTROL"]):  # 두 arm 같은 날짜 경계
        assert p["validation_start"] == c["validation_start"]
        assert p["split_fingerprint"] == c["split_fingerprint"]


def test_limit_dates_marks_not_official(env):
    code = run(env, "smoke", "--limit-dates", "1")
    result = _result(env, "smoke")
    measured = all(
        result["arms"][a]["status"] == "MEASURED" for a in ("PIT", "CONTROL")
    )
    assert code == (0 if measured else 3)  # 신호일 1개면 N-1 통제가 막을 수 있다
    assert result["official"] is False
    assert result["calendar"]["evaluated_count"] == 1
    assert [r["signal_date"] for r in result["per_date"]["PIT"]] == E2_DATES[-1:]


def test_write_new_is_exclusive(tmp_path):
    runner.write_new(tmp_path / "x.json", {"a": 1})
    with pytest.raises(FileExistsError):
        runner.write_new(tmp_path / "x.json", {"a": 2})
    assert json.loads((tmp_path / "x.json").read_text(encoding="utf-8")) == {"a": 1}


# --- 재개 ------------------------------------------------------------------------------


def test_resume_equals_uninterrupted_and_keeps_progress(env, monkeypatch):
    assert run(env, "a") == 0
    real = _fail_on_call(monkeypatch, 3)
    with pytest.raises(RuntimeError, match="중단 흉내"):
        run(env, "b")
    out = env["runs"] / "b"
    assert not (out / runner.RESULT).exists()
    kept = _tree(out / runner.PROGRESS_DIR)
    assert len(kept) == 2
    monkeypatch.setattr(runner, "evaluate_point", real)
    assert run(env, "b", "--resume") == 0
    now = _tree(out / runner.PROGRESS_DIR)
    assert {k: now[k] for k in kept} == kept and len(now) == 4  # 기존 기록 그대로
    meta = json.loads((out / runner.RUN_META).read_text(encoding="utf-8"))
    assert (meta["resumed"], meta["progress_reused"], meta["progress_computed"]) == (
        True,
        2,
        2,
    )
    final = json.loads((out / runner.RUN_MANIFEST_FINAL).read_text(encoding="utf-8"))
    assert final["resumed"] is True
    first, second = str(env["runs"] / "a"), str(out)
    # 재개한 실행과의 비교 — hash 는 같지만 결정성 확인(PLAN §8)에는 쓸 수 없다 → exit 2
    assert runner.main(["compare", "--first", first, "--second", second]) == 2
    cmp_ = json.loads((out / runner.COMPARE).read_text(encoding="utf-8"))
    assert cmp_["identical"] is True
    assert cmp_["first"]["recomputed"] == cmp_["second"]["recomputed"]
    assert (cmp_["first"]["resumed"], cmp_["second"]["resumed"]) == (False, True)
    assert cmp_["determinism_eligible"] is False
    assert cmp_["determinism_confirmed"] is False
    with pytest.raises(FileExistsError):
        runner.main(["compare", "--first", first, "--second", second])
    # 재개 없이 처음부터 두 번 → 결정성 확인
    assert run(env, "c") == 0
    third = str(env["runs"] / "c")
    assert runner.main(["compare", "--first", first, "--second", third]) == 0
    cmp_ = json.loads((env["runs"] / "c" / runner.COMPARE).read_text(encoding="utf-8"))
    assert cmp_["identical"] and cmp_["determinism_eligible"]
    assert cmp_["determinism_confirmed"] and cmp_["both_official"]
    same = env["runs"] / "a_copy"
    shutil.copytree(
        env["runs"] / "a", same
    )  # 같은 폴더끼리 비교는 결정성 확인이 아니다
    assert runner.main(["compare", "--first", str(same), "--second", str(same)]) == 2
    tampered = _result(env, "a")
    tampered["arms"]["PIT"]["counts"]["dates"] = 99
    (env["runs"] / "a" / runner.RESULT).write_text(json.dumps(tampered), "utf-8")
    assert runner.main(["compare", "--first", second, "--second", first]) == 1


def test_resume_stops_on_fingerprint_mismatch(env, monkeypatch):
    real = _fail_on_call(monkeypatch, 2)
    with pytest.raises(RuntimeError):
        run(env, "b")
    monkeypatch.setattr(runner, "evaluate_point", real)
    out = env["runs"] / "b"
    before = _tree(out)
    monkeypatch.setattr(pit_eval, "EPOCHS", pit_eval.EPOCHS - 1)
    with pytest.raises(runner.RunnerError, match="config_sha256"):
        run(env, "b", "--resume")
    monkeypatch.setattr(pit_eval, "EPOCHS", pit_eval.EPOCHS + 1)
    with pytest.raises(runner.RunnerError, match="evaluation_dates_sha256"):
        run(env, "b", "--resume", "--limit-dates", "1")
    assert _tree(out) == before
    unit_path = next((out / runner.PROGRESS_DIR).iterdir())
    unit = json.loads(unit_path.read_text(encoding="utf-8"))
    unit["fingerprint_sha256"] = "0" * 64
    unit_path.write_text(json.dumps(unit), encoding="utf-8")
    with pytest.raises(runner.RunnerError, match="progress 기록"):
        run(env, "b", "--resume")
    assert not (out / runner.RESULT).exists()


def test_resume_requires_manifest(env):
    (env["runs"] / "empty").mkdir(parents=True)
    with pytest.raises(runner.RunnerError, match="run_manifest"):
        run(env, "empty", "--resume")


# --- 실행 규율 -------------------------------------------------------------------------


def test_live_path_change_blocks_result_and_resume(env, monkeypatch):
    log = env["root"] / "logs" / "oci_market_data_batch.log"
    original = log.read_bytes()
    real = _fail_on_call(
        monkeypatch, 1, lambda: log.write_text("changed\n", encoding="utf-8")
    )
    with pytest.raises(runner.RunnerError, match="logs/oci_market_data_batch.log"):
        run(env, "live")
    out = env["runs"] / "live"
    assert not (out / runner.RESULT).exists()
    marker = json.loads((out / runner.GUARD_FAILED).read_text(encoding="utf-8"))
    assert marker["guard"] == "LIVE_PATHS_CHANGED"
    monkeypatch.setattr(runner, "evaluate_point", real)
    log.write_bytes(
        original
    )  # 라이브 파일을 되돌려도 거부된 실행은 재개로 결과를 만들지 않는다
    before = _tree(out)
    with pytest.raises(runner.RunnerError, match="가드가 결과를 거부"):
        run(env, "live", "--resume")
    assert _tree(out) == before and not (out / runner.RESULT).exists()


def test_live_change_before_interruption_blocks_resume(env, monkeypatch):
    """중단된 첫 구간의 라이브 변경 — 재개 세션은 manifest 의 처음 시작 지문과도 비교한다."""
    log = env["root"] / "logs" / "oci_market_data_batch.log"
    real, calls = runner.evaluate_point, {"n": 0}

    def wrapped(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            log.write_text("changed\n", encoding="utf-8")
        if calls["n"] == 2:
            raise RuntimeError("중단 흉내")
        return real(*args, **kwargs)

    monkeypatch.setattr(runner, "evaluate_point", wrapped)
    with pytest.raises(RuntimeError, match="중단 흉내"):
        run(env, "b")
    monkeypatch.setattr(runner, "evaluate_point", real)
    out = env["runs"] / "b"
    with pytest.raises(runner.RunnerError, match="logs/oci_market_data_batch.log"):
        run(env, "b", "--resume")
    assert not (out / runner.RESULT).exists()
    detail = json.loads((out / runner.GUARD_FAILED).read_text(encoding="utf-8"))[
        "detail"
    ]
    assert detail["session_before"] == detail["after"] != detail["run_start"]


@pytest.mark.parametrize(
    "rel", ["state/runs", "state/runs/poc4_02a_x", "logs/three_push_runtime_cron.log"]
)
def test_out_dir_under_live_watch_path_is_refused(env, rel):
    live = runner.live_fingerprint(env["root"])
    for extra in ((), ("--resume",)):
        argv = ["run", "--out-dir", str(env["root"] / rel), *extra]
        argv += ["--sealed-db", str(env["db"]), "--e2-manifest", str(env["e2"])]
        with pytest.raises(runner.RunnerError, match="감시 대상 라이브 경로"):
            runner.main(argv, project_root=env["root"])
    assert runner.live_fingerprint(env["root"]) == live


def test_run_folder_creation_is_inside_live_guard(env, monkeypatch):
    """폴더 거부를 끄더라도 라이브 지문은 실행 폴더를 만들기 전에 잰다 → state/runs 변경을 잡는다."""
    monkeypatch.setattr(runner, "_check_out_dir", lambda out_dir, root: None)
    out = env["root"] / "state" / "runs" / "poc4_02a_x"
    argv = ["run", "--out-dir", str(out), "--sealed-db", str(env["db"])]
    with pytest.raises(runner.RunnerError, match="state/runs"):
        runner.main([*argv, "--e2-manifest", str(env["e2"])], project_root=env["root"])
    assert not (out / runner.RESULT).exists()


def test_live_runs_listing_change_blocks_result(env, monkeypatch):
    runs = env["root"] / "state" / "runs"
    _fail_on_call(monkeypatch, 1, lambda: (runs / "new_run").mkdir())
    with pytest.raises(runner.RunnerError, match="state/runs"):
        run(env, "live2")
    assert not (env["runs"] / "live2" / runner.RESULT).exists()


def test_sealed_source_change_blocks_result_and_resume(env, monkeypatch, clean_db):
    def tamper():
        con = sqlite3.connect(env["db"])
        con.execute("CREATE TABLE tamper (x)")
        con.commit()
        con.close()

    real = _fail_on_call(monkeypatch, 1, tamper)
    with pytest.raises(SealedSourceError, match="file_sha256"):
        run(env, "sealed")
    out = env["runs"] / "sealed"
    assert not (out / runner.RESULT).exists()
    marker = json.loads((out / runner.GUARD_FAILED).read_text(encoding="utf-8"))
    assert marker["guard"] == "SEALED_SOURCE_CHANGED"
    monkeypatch.setattr(runner, "evaluate_point", real)
    shutil.copyfile(
        clean_db, env["db"]
    )  # 봉인 DB 를 되돌려도 거부된 실행은 재개하지 않는다
    with pytest.raises(runner.RunnerError, match="가드가 결과를 거부"):
        run(env, "sealed", "--resume")
    assert not (out / runner.RESULT).exists()


def test_other_database_connection_is_refused(env, monkeypatch):
    other = env["runs"].parent / "other.sqlite"
    _fail_on_call(monkeypatch, 1, lambda: sqlite3.connect(other))
    with pytest.raises(SnapshotGuardError):
        run(env, "guard")
    assert not other.exists()


def test_blocked_arms_exit_3_without_metrics(env, tmp_path):
    db = tmp_path / "reasons.sqlite"
    build_sealed_db(db, reasons_rows())
    e2 = tmp_path / "e2_one.json"
    e2.write_text(
        json.dumps({"evaluation_calendar": {"e2_dates": E2_DATES[:1]}}), "utf-8"
    )
    assert run(env, "blocked", db=db, e2=e2) == 3
    result = _result(env, "blocked")
    for arm in ("PIT", "CONTROL"):
        block = result["arms"][arm]
        assert block["status"] == "BLOCKED_COVERAGE" and block["metrics"] is None
        assert "ic_filter" not in result["per_date"][arm][0]
    assert result["survivorship_effect"]["status"] == "NOT_PRODUCED"
    assert result["cross_coverage"][0]["control_numerator"] == 12


# --- 경계 (PLAN §5) --------------------------------------------------------------------


def test_benchmark_missing_from_sealed_source_fails_without_result(env, tmp_path):
    """069500 은 봉인 version 에서만 — 없으면 다른 source 로 대신하지 않고 멈춘다."""
    rows = {
        d: [r for r in rs if r["ISU_CD"] != BENCHMARK_CODE]
        for d, rs in clean_rows().items()
    }
    db = tmp_path / "no_bench.sqlite"
    build_sealed_db(db, rows)
    live = runner.live_fingerprint(env["root"])
    with pytest.raises(SealedSourceError, match=f"벤치마크 {BENCHMARK_CODE}"):
        run(env, "nobench", db=db)
    assert not (env["runs"] / "nobench" / runner.RESULT).exists()
    assert runner.live_fingerprint(env["root"]) == live


def test_run_makes_no_network_calls(env, monkeypatch):
    attempts: list = []

    def refuse(*args, **kwargs):
        attempts.append(args)
        raise OSError("외부 네트워크 금지 (테스트)")

    for owner, name in (
        (socket.socket, "connect"),
        (socket.socket, "connect_ex"),
        (socket, "create_connection"),
        (socket, "getaddrinfo"),
    ):
        monkeypatch.setattr(owner, name, refuse)
    assert run(env, "net") == 0
    assert attempts == []
