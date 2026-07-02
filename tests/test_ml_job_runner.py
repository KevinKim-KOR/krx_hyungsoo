"""POC2 UI 안전실행 — ml_job_runner + /ml/jobs/* API 테스트 (2026-06-11).

지시문 §10 AC-2 / AC-3 / AC-4 / AC-6 / AC-7 / AC-8 검증.

본 테스트는:
- 실제 SQLite / build_features / build_baseline_report 를 호출하지 않는다 —
  step 함수를 monkeypatch 해서 runner 의 흐름과 상태 전이만 검증.
- AC-6 검증을 위해 실제 디스크에 가짜 기존 snapshot 을 두고, 실패 시 보존 여부
  를 확인.
- AC-2 / AC-8 검증을 위해 step 함수가 sleep 으로 의도적으로 늦은 경우 HTTP 응답
  이 즉시 반환되는지 측정.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import ml_job_runner
from app.api import app


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path: Path, monkeypatch):
    """모든 테스트에서 state/ml/ 경로를 tmp 로 격리.

    runner 모듈의 JOB_STATUS_PATH + 각 step 의 snapshot 경로를 tmp 로 재지정.
    in-process lock 도 초기화 (테스트 간 상태 누수 방지).
    """
    job_path = tmp_path / "ml_job_status_latest.json"
    feat_path = tmp_path / "ml_feature_snapshot_latest.json"
    sanity_path = tmp_path / "ml_feature_sanity_latest.json"
    baseline_path = tmp_path / "ml_baseline_v0_report_latest.json"

    monkeypatch.setattr(ml_job_runner, "JOB_STATUS_PATH", job_path, raising=False)

    # api_ml_jobs 모듈도 같은 경로를 표시하도록 패치 (응답 메시지의 path 일관성).
    from app import api_ml_jobs

    monkeypatch.setattr(api_ml_jobs, "JOB_STATUS_PATH", job_path, raising=False)

    # 2026-06-30 Closeout — 시계열 최신화 게이트가 도입되어 기본은 error 반환.
    # 본 파일의 기존 테스트는 게이트 자체와 무관하므로 fixture 에서 bypass.
    # (게이트 자체 검증은 tests/test_api_ml_jobs_timeseries_gate.py 참조.)
    monkeypatch.setattr(
        api_ml_jobs,
        "_timeseries_ready_for_ml",
        lambda: (True, ""),
        raising=False,
    )

    # _run_feature / _run_sanity / _run_baseline 내부의 snapshot path 도 격리.
    import scripts.generate_ml_features as gmf
    from app import api_ml_baseline, api_ml_sanity

    monkeypatch.setattr(gmf, "SNAPSHOT_PATH", feat_path, raising=False)
    monkeypatch.setattr(
        api_ml_sanity, "SANITY_SNAPSHOT_PATH", sanity_path, raising=False
    )
    monkeypatch.setattr(
        api_ml_baseline, "BASELINE_REPORT_PATH", baseline_path, raising=False
    )

    # in-process lock 강제 해제 — 이전 테스트의 누수 방지.
    if ml_job_runner._RUN_LOCK.locked():
        try:
            ml_job_runner._RUN_LOCK.release()
        except RuntimeError:
            pass

    yield {
        "job_path": job_path,
        "feat_path": feat_path,
        "sanity_path": sanity_path,
        "baseline_path": baseline_path,
    }

    if ml_job_runner._RUN_LOCK.locked():
        try:
            ml_job_runner._RUN_LOCK.release()
        except RuntimeError:
            pass


def _stub_all_steps_success(monkeypatch):
    """3단계 모두 즉시 success — 단계 순서 / 최종 상태 검증용."""
    calls: list[str] = []

    def _feat(state, db_path):
        calls.append("feature")
        return {"last_asof": "2026-06-08", "etf_upserted": 100, "market_upserted": 60}

    def _sanity(state, db_path):
        calls.append("sanity")
        return {
            "sanity_status": "ok",
            "etf_feature_rows": 100,
            "warnings": 0,
            "errors": 0,
        }

    def _baseline(state, db_path):
        calls.append("baseline")
        return {
            "feature_asof_end": "2026-06-08",
            "evaluated_days": 40,
            "baseline_report_status": "ok",
        }

    monkeypatch.setitem(ml_job_runner._STEP_FUNCS, ml_job_runner.STEP_FEATURE, _feat)
    monkeypatch.setitem(ml_job_runner._STEP_FUNCS, ml_job_runner.STEP_SANITY, _sanity)
    monkeypatch.setitem(
        ml_job_runner._STEP_FUNCS, ml_job_runner.STEP_BASELINE, _baseline
    )
    return calls


def _wait_for_job_status(
    path: Path,
    *,
    target: tuple[str, ...] = ("success", "failed"),
    timeout: float = 5.0,
) -> dict:
    """폴링으로 job state 가 target 상태에 도달할 때까지 대기 + 반환."""
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        if path.exists():
            try:
                last = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                last = {}
            if last.get("status") in target:
                return last
        time.sleep(0.05)
    return last


# ─── AC-3 단계 순서 + 정상 흐름 ────────────────────────────────────


def test_runner_executes_steps_in_required_sequence(_isolate_state, monkeypatch):
    """AC-3 — feature → sanity → baseline 순서 보장."""
    calls = _stub_all_steps_success(monkeypatch)
    initial = ml_job_runner.start_evidence_refresh_job(requested_by="test")
    assert initial["status"] in ("queued", "running")
    final = _wait_for_job_status(_isolate_state["job_path"])
    assert final["status"] == "success"
    assert calls == ["feature", "sanity", "baseline"]
    for step in (
        ml_job_runner.STEP_FEATURE,
        ml_job_runner.STEP_SANITY,
        ml_job_runner.STEP_BASELINE,
    ):
        assert final["steps"][step]["status"] == "success"
    assert final["last_success_summary"]["baseline_report_status"] == "ok"


# ─── AC-3 단계 실패 격리 ───────────────────────────────────────────


def test_runner_skips_later_steps_when_feature_fails(_isolate_state, monkeypatch):
    """AC-3 / AC-5 — feature 실패 시 sanity / baseline 은 skipped."""

    def _feat(state, db_path):
        raise RuntimeError("feature 단계 의도적 실패")

    monkeypatch.setitem(ml_job_runner._STEP_FUNCS, ml_job_runner.STEP_FEATURE, _feat)

    ml_job_runner.start_evidence_refresh_job(requested_by="test")
    final = _wait_for_job_status(_isolate_state["job_path"])
    assert final["status"] == "failed"
    assert final["steps"][ml_job_runner.STEP_FEATURE]["status"] == "failed"
    assert final["steps"][ml_job_runner.STEP_SANITY]["status"] == "skipped"
    assert final["steps"][ml_job_runner.STEP_BASELINE]["status"] == "skipped"
    assert "feature_generation" in (final.get("error") or "")


def test_runner_skips_baseline_when_sanity_fails(_isolate_state, monkeypatch):
    """AC-3 — sanity 실패 시 baseline 만 skipped."""
    _stub_all_steps_success(monkeypatch)

    def _sanity(state, db_path):
        raise RuntimeError("sanity 단계 의도적 실패")

    monkeypatch.setitem(ml_job_runner._STEP_FUNCS, ml_job_runner.STEP_SANITY, _sanity)

    ml_job_runner.start_evidence_refresh_job(requested_by="test")
    final = _wait_for_job_status(_isolate_state["job_path"])
    assert final["status"] == "failed"
    assert final["steps"][ml_job_runner.STEP_FEATURE]["status"] == "success"
    assert final["steps"][ml_job_runner.STEP_SANITY]["status"] == "failed"
    assert final["steps"][ml_job_runner.STEP_BASELINE]["status"] == "skipped"


# ─── AC-6 실패 시 기존 snapshot 보존 ───────────────────────────────


def test_failure_does_not_delete_existing_snapshots(_isolate_state, monkeypatch):
    """AC-6 — runner 가 어떤 경우에도 기존 snapshot 파일을 삭제하지 않는다."""
    # 기존 snapshot 3종을 미리 디스크에 둔다.
    existing = {"marker": "previous_success"}
    for key in ("feat_path", "sanity_path", "baseline_path"):
        path = _isolate_state[key]
        path.write_text(json.dumps(existing), encoding="utf-8")

    def _feat(state, db_path):
        raise RuntimeError("feature 단계 실패로 snapshot 갱신 안 됨")

    monkeypatch.setitem(ml_job_runner._STEP_FUNCS, ml_job_runner.STEP_FEATURE, _feat)

    ml_job_runner.start_evidence_refresh_job(requested_by="test")
    final = _wait_for_job_status(_isolate_state["job_path"])
    assert final["status"] == "failed"

    # 기존 snapshot 3개 모두 그대로 유지되어야 한다 (지시문 §5.4).
    for key in ("feat_path", "sanity_path", "baseline_path"):
        path = _isolate_state[key]
        assert path.exists(), f"{key} 가 사라짐 — AC-6 위반"
        assert json.loads(path.read_text(encoding="utf-8")) == existing


# ─── AC-4 중복 실행 방지 ───────────────────────────────────────────


def test_duplicate_start_returns_already_running(_isolate_state, monkeypatch):
    """AC-4 — running 중에 두 번째 start 요청은 새 job 을 만들지 않고 raise."""
    barrier = threading.Event()

    def _feat(state, db_path):
        # 첫 번째 job 이 feature 단계에서 멈춰서 'running' 상태 유지.
        barrier.wait(timeout=3.0)
        return {"last_asof": "2026-06-08", "etf_upserted": 1, "market_upserted": 1}

    _stub_all_steps_success(monkeypatch)
    monkeypatch.setitem(ml_job_runner._STEP_FUNCS, ml_job_runner.STEP_FEATURE, _feat)

    first = ml_job_runner.start_evidence_refresh_job(requested_by="test")
    assert first["job_id"]

    # 첫 job 이 running 상태가 되기를 기다림. get_latest_status 는 FIX r2 이후
    # (state, error) tuple 반환.
    deadline = time.time() + 2.0
    while time.time() < deadline:
        snap, _err = ml_job_runner.get_latest_status()
        if snap is not None and snap.get("status") == "running":
            break
        time.sleep(0.02)

    with pytest.raises(ml_job_runner.JobAlreadyRunningError) as ei:
        ml_job_runner.start_evidence_refresh_job(requested_by="test")
    # 중복 요청은 기존 job state 를 그대로 expose.
    assert ei.value.state.get("job_id") == first["job_id"]

    # 정리: 첫 job 의 barrier 해제 후 종료 대기.
    barrier.set()
    _wait_for_job_status(_isolate_state["job_path"])


# ─── AC-2 / AC-8 HTTP 즉시 반환 ────────────────────────────────────


def test_http_post_returns_immediately(_isolate_state, monkeypatch):
    """AC-2 / AC-8 — POST 요청은 job 완료를 기다리지 않는다.

    feature 단계가 1초 sleep 해도 HTTP 응답은 그 안에 돌아와야 한다.
    TestClient 의 BackgroundTasks 는 응답 송신 후 동기 실행하므로, 본 테스트는
    runner 내부에서 threading.Thread 가 도는 schedule=None 경로를 강제한다.
    """
    started = threading.Event()
    finished = threading.Event()

    def _feat(state, db_path):
        started.set()
        time.sleep(1.0)
        finished.set()
        return {"last_asof": "2026-06-08", "etf_upserted": 1, "market_upserted": 1}

    _stub_all_steps_success(monkeypatch)
    monkeypatch.setitem(ml_job_runner._STEP_FUNCS, ml_job_runner.STEP_FEATURE, _feat)

    t0 = time.perf_counter()
    state = ml_job_runner.start_evidence_refresh_job(requested_by="test")
    elapsed = time.perf_counter() - t0
    # 즉시 반환 — 100ms 이내 (대형 마진 유지).
    assert elapsed < 0.5, f"start_evidence_refresh_job 가 {elapsed:.2f}s 만에 반환"
    assert state["status"] in ("queued", "running")
    # background 가 실제로 시작했는지 확인.
    assert started.wait(timeout=1.0), "background runner 가 시작되지 않음"
    # 최종 완료 대기 (cleanup).
    assert finished.wait(timeout=3.0)
    _wait_for_job_status(_isolate_state["job_path"])


# ─── AC-7 status API 는 job 을 실행하지 않는다 ───────────────────


def test_get_latest_does_not_start_job(_isolate_state, monkeypatch):
    """AC-7 — GET /ml/jobs/latest 가 어떤 step 함수도 호출하지 않는다."""

    def _boom(state, db_path):
        raise AssertionError("GET /ml/jobs/latest 가 step 함수를 호출했습니다")

    for step in ml_job_runner.STEP_SEQUENCE:
        monkeypatch.setitem(ml_job_runner._STEP_FUNCS, step, _boom)

    client = TestClient(app)
    resp = client.get("/ml/jobs/latest")
    assert resp.status_code == 200
    body = resp.json()
    # state 가 비어 있으면 status=empty, 있으면 status=ok — 둘 다 실행은 0건.
    assert body["status"] in ("ok", "empty")


def test_post_evidence_refresh_returns_accepted(_isolate_state, monkeypatch):
    """POST /ml/jobs/evidence-refresh 가 accepted 응답 + job 시작."""
    _stub_all_steps_success(monkeypatch)
    client = TestClient(app)
    resp = client.post("/ml/jobs/evidence-refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["job"]["status"] in ("queued", "running", "success")
    # TestClient 가 BackgroundTasks 를 동기 실행하므로 응답 받은 시점에는 이미 완료될 수 있음 — final 만 확인.
    final = _wait_for_job_status(_isolate_state["job_path"])
    assert final["status"] == "success"


def test_post_evidence_refresh_duplicate_returns_already_running(
    _isolate_state, monkeypatch
):
    """POST 중복 호출 시 already_running 반환 (AC-4)."""
    # 첫 호출은 in-process lock 만 잡고 release 안 함 — disk 상태 running 으로 박아둠.
    job_path = _isolate_state["job_path"]
    job_path.parent.mkdir(parents=True, exist_ok=True)
    import os as _os

    job_path.write_text(
        json.dumps(
            {
                "job_id": "ml-evidence-refresh-fake",
                "status": "running",
                "pid": _os.getpid(),
                "last_heartbeat_at": ml_job_runner._now_kst_iso(),
                "steps": {},
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(app)
    resp = client.post("/ml/jobs/evidence-refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "already_running"
    assert body["job"]["job_id"] == "ml-evidence-refresh-fake"


# ─── stale lock 자동 해제 ─────────────────────────────────────────


def test_stale_running_lock_is_recovered(_isolate_state, monkeypatch):
    """사용자 결정 — heartbeat 가 STALE_HEARTBEAT_SECONDS 초과면 stale 로 보고
    새 job 을 시작할 수 있다.
    """
    from datetime import datetime, timedelta

    job_path = _isolate_state["job_path"]
    job_path.parent.mkdir(parents=True, exist_ok=True)
    # 11분 전 heartbeat + 죽은 PID (sentinel: 1 은 init 이지만 kill(1, 0) 은 권한
    # 거부로 OSError → _pid_alive False).
    stale_hb = (datetime.now(ml_job_runner._KST) - timedelta(seconds=11 * 60)).strftime(
        "%Y-%m-%dT%H:%M:%S.%f%z"
    )
    job_path.write_text(
        json.dumps(
            {
                "job_id": "ml-evidence-refresh-stale",
                "status": "running",
                "pid": 999999,  # 존재하지 않을 PID
                "last_heartbeat_at": stale_hb,
                "steps": {},
            }
        ),
        encoding="utf-8",
    )

    _stub_all_steps_success(monkeypatch)
    state = ml_job_runner.start_evidence_refresh_job(requested_by="test")
    # 새 job 이 시작되어야 한다 — stale 자동 해제.
    assert state["job_id"] != "ml-evidence-refresh-stale"
    _wait_for_job_status(_isolate_state["job_path"])


# ─── FIX r2 — Windows PID 확인 비활성화 (A-1 / B-6) ──────────────


def test_pid_check_disabled_on_windows(monkeypatch):
    """Windows 에서 _pid_alive 가 os.kill 을 호출하지 않고 True 반환.

    `os.kill(pid, 0)` 은 Windows 에서 PID 0 / 자기 PID 에 대해 비결정적 동작
    (KeyboardInterrupt 유발 가능) — stdlib 만으로 안전한 PID 확인은 없으므로
    Windows 에서는 heartbeat 시각만으로 stale 판정한다 (FIX r2).
    """
    monkeypatch.setattr(ml_job_runner, "_PID_CHECK_SUPPORTED", False, raising=False)

    def _boom(*args, **kwargs):
        raise AssertionError("Windows 분기에서 os.kill 이 호출됨")

    monkeypatch.setattr(ml_job_runner.os, "kill", _boom, raising=False)
    # 어떤 PID 값이든 True 반환 (확인 skip).
    assert ml_job_runner._pid_alive(999999) is True
    assert ml_job_runner._pid_alive(0) is True
    assert ml_job_runner._pid_alive(None) is True


def test_stale_running_uses_heartbeat_only_on_windows(_isolate_state, monkeypatch):
    """Windows 에서 heartbeat fresh 면 PID 무관하게 running 으로 인정.

    PID 가 죽은 값 (999999) 이라도 heartbeat 가 fresh 면 새 job 시작 거부 —
    Windows 에서는 PID 확인을 안 하므로 의도된 동작 (heartbeat 신뢰).
    """
    monkeypatch.setattr(ml_job_runner, "_PID_CHECK_SUPPORTED", False, raising=False)
    job_path = _isolate_state["job_path"]
    job_path.parent.mkdir(parents=True, exist_ok=True)
    fresh_hb = ml_job_runner._now_kst_iso()
    job_path.write_text(
        json.dumps(
            {
                "job_id": "ml-evidence-refresh-fresh-hb",
                "status": "running",
                "pid": 999999,  # 죽은 PID 지만 Windows 에선 확인 안 함.
                "last_heartbeat_at": fresh_hb,
                "steps": {},
            }
        ),
        encoding="utf-8",
    )
    _stub_all_steps_success(monkeypatch)
    with pytest.raises(ml_job_runner.JobAlreadyRunningError):
        ml_job_runner.start_evidence_refresh_job(requested_by="test")


def test_stale_recovered_on_windows_by_heartbeat_timeout(_isolate_state, monkeypatch):
    """Windows 에서 heartbeat 가 10분 초과면 새 job 허용 (PID 확인 없이도)."""
    from datetime import datetime, timedelta

    monkeypatch.setattr(ml_job_runner, "_PID_CHECK_SUPPORTED", False, raising=False)
    job_path = _isolate_state["job_path"]
    job_path.parent.mkdir(parents=True, exist_ok=True)
    stale_hb = (datetime.now(ml_job_runner._KST) - timedelta(seconds=11 * 60)).strftime(
        "%Y-%m-%dT%H:%M:%S.%f%z"
    )
    # PID 는 살아있는 자기 자신 — 그래도 heartbeat stale 이면 새 job 허용.
    job_path.write_text(
        json.dumps(
            {
                "job_id": "ml-evidence-refresh-stale-windows",
                "status": "running",
                "pid": __import__("os").getpid(),
                "last_heartbeat_at": stale_hb,
                "steps": {},
            }
        ),
        encoding="utf-8",
    )
    _stub_all_steps_success(monkeypatch)
    state = ml_job_runner.start_evidence_refresh_job(requested_by="test")
    assert state["job_id"] != "ml-evidence-refresh-stale-windows"
    _wait_for_job_status(_isolate_state["job_path"])


# ─── FIX r2 — 손상 케이스 fail-loud (B-1) ────────────────────────


def test_get_latest_returns_error_when_status_file_corrupted(_isolate_state):
    """GET /ml/jobs/latest 가 손상 파일에 대해 status='error' 응답 (B-1)."""
    job_path = _isolate_state["job_path"]
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text("{not valid json", encoding="utf-8")

    client = TestClient(app)
    resp = client.get("/ml/jobs/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert body["job"] is None
    assert "손상" in (body.get("message") or "")


def test_post_evidence_refresh_returns_error_when_status_file_corrupted(
    _isolate_state,
):
    """POST 시점에 손상이 발견되면 새 job 자동 생성하지 않고 status='error' (B-1).

    '손상을 자동으로 덮어쓰면' 사용자가 진단할 기회를 놓침 — fail-loud 정책.
    """
    job_path = _isolate_state["job_path"]
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text("{still broken", encoding="utf-8")

    client = TestClient(app)
    resp = client.post("/ml/jobs/evidence-refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert body["job"] is None


def test_get_latest_returns_state_error_tuple_directly(_isolate_state):
    """ml_job_runner.get_latest_status() 자체가 (None, exception) 반환 (B-1)."""
    job_path = _isolate_state["job_path"]
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text("not json at all {", encoding="utf-8")

    state, err = ml_job_runner.get_latest_status()
    assert state is None
    assert err is not None
