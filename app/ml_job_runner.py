"""ML evidence refresh job runner (POC2 UI 안전실행, 2026-06-11).

Data Status 화면의 "ML evidence 갱신" 버튼이 본 runner 를 background 로 시작한다.
3단계 (feature → sanity → baseline) 를 순서대로 수행하고 매 단계마다 동일
snapshot 파일에 기록한다. 단계 실패 시 이후 단계는 skipped, 기존 artifact 는
보존 (마지막 성공 결과는 사용자가 계속 볼 수 있어야 한다 — 지시문 §5.4).

본 모듈의 책임:
- job state snapshot (state/ml/ml_job_status_latest.json) 의 생성 / 갱신.
- threading.Lock 으로 in-process 중복 실행 차단.
- snapshot 안의 PID + last_heartbeat_at 으로 프로세스 재시작 후 stale lock 자동
  해제 (10분 기준).
- 각 단계 실행 — CLI 가 호출하는 동일 함수 (`build_features` /
  `build_sanity_report` / `build_baseline_report`) 를 직접 호출하여 동일 artifact
  를 만든다. CLI 경로는 그대로 살아있다 (AC-9).

본 모듈이 절대 하지 않는 것:
- baseline 산식 변경 / risk threshold 확정 / 매수·매도 판단 / 외부 source 호출.
- 외부 인프라 (Celery / Redis / 신규 DB) 도입.
- 기존 snapshot 삭제 (성공 시에만 덮어쓰기, 실패 시 보존).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# state snapshot path — gitignored 운영 artifact.
JOB_STATUS_PATH = Path("state/ml/ml_job_status_latest.json")

# Stale lock 기준 — 지시문 §5.3 + 사용자 결정 (a) PID + heartbeat 10분.
STALE_HEARTBEAT_SECONDS = 600

# 단계 식별자 (3단계 고정 순서, 지시문 §4).
STEP_FEATURE = "feature_generation"
STEP_SANITY = "sanity_check"
STEP_BASELINE = "baseline_lookback"
STEP_SEQUENCE: tuple[str, ...] = (STEP_FEATURE, STEP_SANITY, STEP_BASELINE)

STEP_ARTIFACT_PATH = {
    STEP_FEATURE: "state/ml/ml_feature_snapshot_latest.json",
    STEP_SANITY: "state/ml/ml_feature_sanity_latest.json",
    STEP_BASELINE: "state/ml/ml_baseline_v0_report_latest.json",
}

# In-process lock — 동일 FastAPI 프로세스 안의 동시 trigger 차단.
_RUN_LOCK = threading.Lock()

_KST = timezone(timedelta(hours=9))


def _now_kst_iso() -> str:
    return datetime.now(_KST).strftime("%Y-%m-%dT%H:%M:%S.%f%z")


def _new_job_id(now: Optional[datetime] = None) -> str:
    """`ml-evidence-refresh-YYYYMMDDHHMMSS-<seq>` 형식 (지시문 §6.1)."""
    base = now or datetime.now(_KST)
    return f"ml-evidence-refresh-{base.strftime('%Y%m%d%H%M%S')}-{os.getpid():05d}"


def _empty_step() -> dict[str, Any]:
    return {
        "status": "queued",
        "started_at": None,
        "finished_at": None,
        "message": "",
        "artifact_path": "",
    }


def _build_initial_state(
    job_id: str,
    requested_by: str,
    started_at: str,
) -> dict[str, Any]:
    steps: dict[str, dict[str, Any]] = {}
    for step in STEP_SEQUENCE:
        s = _empty_step()
        s["artifact_path"] = STEP_ARTIFACT_PATH[step]
        steps[step] = s
    return {
        "job_id": job_id,
        "status": "queued",
        "started_at": started_at,
        "finished_at": None,
        "requested_by": requested_by,
        "pid": os.getpid(),
        "last_heartbeat_at": started_at,
        "steps": steps,
        "last_success_summary": None,
        "message": "",
        "error": None,
    }


def _write_status(state: dict[str, Any]) -> None:
    JOB_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with JOB_STATUS_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, default=str)


class JobStatusCorruptedError(RuntimeError):
    """on-disk job status 파일이 손상되어 의미를 해석할 수 없을 때 (B-1 fail-loud)."""

    def __init__(self, path: Path, cause: Exception):
        super().__init__(f"ml_job_status 파일 손상 ({path}): {cause}")
        self.path = path
        self.cause = cause


def _read_status_raw() -> tuple[Optional[dict[str, Any]], Optional[Exception]]:
    """status 파일 read — (state, error) tuple 로 반환.

    - 파일 없음: (None, None) — 정상 미실행 상태.
    - JSON 손상 / 비-dict: (None, exception) — 손상을 호출자에게 알린다.
    - 정상 dict: (dict, None).

    FIX r2 (B-1): 손상과 미실행을 같은 None 으로 흡수하던 기존 구현 제거.
    """
    if not JOB_STATUS_PATH.exists():
        return None, None
    try:
        with JOB_STATUS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"ml_job_status read 실패: {e}")
        return None, e
    if not isinstance(data, dict):
        return None, ValueError("ml_job_status 파일이 dict 아님")
    return data, None


def _read_status() -> Optional[dict[str, Any]]:
    """기존 호출자용 헬퍼 (loss-tolerant 경로). 손상 시 None.

    UI / API 응답을 위해서는 _read_status_raw 를 사용해 손상 사실을 살려야 한다.
    """
    state, _err = _read_status_raw()
    return state


def get_latest_status() -> tuple[Optional[dict[str, Any]], Optional[Exception]]:
    """저장된 job status 와 read error 를 함께 반환 (read-only).

    FIX r2: 기존은 dict 만 반환했으나, B-1 (손상 상태가 미실행과 구분 안 됨) 해소
    위해 (state, error) tuple 반환. API 가 손상 시 status="error" 응답.
    본 함수는 어떤 job 도 실행하지 않는다 (지시문 §5.6 / AC-7).
    """
    return _read_status_raw()


# Windows 에서 os.kill(pid, 0) 은 PID 0 / 음수에서 비결정적 동작 (자기 자신에게
# CTRL_C_EVENT 와 동등하게 처리될 수 있어 KeyboardInterrupt 유발 가능) 이라 사용
# 하지 않는다. POSIX 만 안전. Windows 에서는 PID 확인을 비활성화하고 heartbeat
# 시각 10분 기준으로만 stale 판정한다 (FIX r2).
_PID_CHECK_SUPPORTED = sys.platform != "win32"


def _pid_alive(pid: Any) -> bool:
    """POSIX 에서만 PID 생존 확인. Windows 에서는 항상 True 반환 (확인 안 함).

    FIX r2 (A-1 / B-6): 기존 `os.kill(pid, 0)` 이 Windows 에서 PID 0 을 alive 로
    반환하고 자기 PID 에 대해 KeyboardInterrupt 유발 가능 — stdlib 만으로 안전한
    Windows PID 확인은 없으므로 Windows 에서는 heartbeat 만으로 stale 판정한다.
    psutil 등 신규 의존성 추가는 §8 정신상 금지.
    """
    if not _PID_CHECK_SUPPORTED:
        return True
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _is_stale_running(state: dict[str, Any]) -> bool:
    """기존 status 가 running 인데 (1) heartbeat 가 오래되었거나 (2) PID 가 죽은
    경우 True. POSIX 는 PID 확인 + heartbeat 둘 다, Windows 는 heartbeat 만.

    지시문 §5.3 + 사용자 결정 (a) — PID + heartbeat 10분. Windows 한정으로
    PID 확인은 비활성화 (FIX r2).
    """
    if state.get("status") != "running":
        return False
    last_hb = state.get("last_heartbeat_at")
    if isinstance(last_hb, str):
        try:
            ts = datetime.fromisoformat(last_hb)
        except ValueError:
            return True
        age = datetime.now(_KST) - ts
        if age.total_seconds() > STALE_HEARTBEAT_SECONDS:
            return True
    elif last_hb is None:
        # heartbeat 가 아예 없으면 안전 측면에서 stale.
        return True
    pid = state.get("pid")
    if _PID_CHECK_SUPPORTED and not _pid_alive(pid):
        return True
    return False


class JobAlreadyRunningError(RuntimeError):
    """이미 실행 중인 job 이 있어 새 job 을 만들 수 없을 때 (지시문 §5.3 / AC-4)."""

    def __init__(self, state: dict[str, Any]):
        super().__init__("ML evidence refresh is already running")
        self.state = state


def _heartbeat(state: dict[str, Any]) -> None:
    state["last_heartbeat_at"] = _now_kst_iso()
    _write_status(state)


def _mark_step(
    state: dict[str, Any],
    step: str,
    *,
    status: str,
    message: str = "",
    started: bool = False,
    finished: bool = False,
) -> None:
    s = state["steps"][step]
    s["status"] = status
    if started and s["started_at"] is None:
        s["started_at"] = _now_kst_iso()
    if finished:
        s["finished_at"] = _now_kst_iso()
    if message:
        s["message"] = message
    _heartbeat(state)


def _run_feature(state: dict[str, Any], db_path: Path) -> dict[str, Any]:
    """generate_ml_features CLI 와 동일한 핵심 함수를 호출 + snapshot 저장.

    CLI 가 호출하는 동일 함수 (`build_features` / `upsert_*` / SNAPSHOT_PATH).
    runner 가 직접 호출하므로 subprocess 0건. snapshot 저장 책임도 본 함수가 진다.
    """
    from dataclasses import asdict as _asdict

    from app.ml_feature_builder import build_features
    from app.ml_feature_store import upsert_etf_features, upsert_market_risk_features
    from scripts.generate_ml_features import (  # noqa: E402  (CLI 와 동일 path 공유)
        DEFAULT_LOOKBACK_DAYS,
        SNAPSHOT_PATH,
    )

    result = build_features(
        db_path=db_path,
        default_lookback_days=DEFAULT_LOOKBACK_DAYS,
    )
    etf_upserted = upsert_etf_features(result.etf_rows, db_path=db_path)
    mkt_upserted = upsert_market_risk_features(result.market_rows, db_path=db_path)
    asofs = result.asofs
    last_asof = asofs[-1] if asofs else None
    now_iso = _now_kst_iso()

    snap = {
        "asof": last_asof,
        "etf_feature_count": etf_upserted,
        "market_risk_feature_count": mkt_upserted,
        "asof_count": len(asofs),
        "etf_universe_count": result.missing_data_summary.get("etf_universe_count"),
        "etf_series_missing": result.missing_data_summary.get("etf_series_missing"),
        "asof_without_kospi": result.missing_data_summary.get("asof_without_kospi"),
        "nav_join_status": (
            "ok"
            if any(r.nav_status == "ok" for r in result.etf_rows)
            else "all_unavailable_or_missing"
        ),
        "market_risk_feature_status": ("ok" if result.market_rows else "empty"),
        "generated_at": now_iso,
        "started_at": state["steps"][STEP_FEATURE]["started_at"],
        "lookback_days_default": DEFAULT_LOOKBACK_DAYS,
        "ticker_filter_used": False,
        "missing_data_summary": result.missing_data_summary,
        "sample_items": [_asdict(r) for r in result.etf_rows[-5:]],
        "requested_by": "ui_job_runner",
    }
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SNAPSHOT_PATH.open("w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2, default=str)

    if etf_upserted <= 0 and mkt_upserted <= 0:
        raise RuntimeError(
            "feature generation upsert 0건 — DB 가 비어있거나 universe coverage 0"
        )
    return {
        "last_asof": last_asof,
        "etf_upserted": etf_upserted,
        "market_upserted": mkt_upserted,
    }


def _run_sanity(state: dict[str, Any], db_path: Path) -> dict[str, Any]:
    """check_ml_feature_sanity CLI 와 동일한 핵심 함수 호출 + snapshot 저장."""
    from app.api_ml_sanity import SANITY_SNAPSHOT_PATH
    from app.ml_feature_sanity import DEFAULT_SAMPLE_TICKER_COUNT, build_sanity_report

    report = build_sanity_report(
        db_path=db_path, sample_count=DEFAULT_SAMPLE_TICKER_COUNT
    )
    SANITY_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SANITY_SNAPSHOT_PATH.open("w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2, default=str)

    if report.sanity_status == "error":
        raise RuntimeError(
            f"sanity_status=error / errors={len(report.errors)} "
            f"warnings={len(report.warnings)}"
        )
    return {
        "sanity_status": report.sanity_status,
        "etf_feature_rows": report.etf_feature_row_count,
        "warnings": len(report.warnings),
        "errors": len(report.errors),
    }


def _run_baseline(state: dict[str, Any], db_path: Path) -> dict[str, Any]:
    """run_ml_baseline_v0 CLI 와 동일한 핵심 함수 호출 + snapshot 저장."""
    from app.api_ml_baseline import BASELINE_REPORT_PATH
    from app.market_regime import KODEX200_TICKER
    from app.ml_baseline_v0 import build_baseline_report

    report = build_baseline_report(db_path=db_path, kodex_ticker=KODEX200_TICKER)
    BASELINE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with BASELINE_REPORT_PATH.open("w", encoding="utf-8") as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2, default=str)

    if report.status == "error":
        raise RuntimeError(
            f"baseline status=error / errors={len(report.errors)} "
            f"warnings={len(report.warnings)}"
        )
    return {
        "feature_asof_end": report.feature_asof_range.get("end"),
        "evaluated_days": report.evaluated_asof_range.get("evaluated_days"),
        "baseline_report_status": report.status,
    }


_STEP_FUNCS: dict[str, Callable[[dict[str, Any], Path], dict[str, Any]]] = {
    STEP_FEATURE: _run_feature,
    STEP_SANITY: _run_sanity,
    STEP_BASELINE: _run_baseline,
}


def _run_job(state: dict[str, Any], db_path: Path) -> None:
    """3단계 순차 실행. 단계 실패 시 이후 단계 skipped + 전체 failed.

    snapshot 저장은 단계별 함수가 책임지며, 본 함수는 job state 갱신과 단계 간
    분기만 담당한다.
    """
    state["status"] = "running"
    _heartbeat(state)

    last_success_summary: Optional[dict[str, Any]] = None
    for step in STEP_SEQUENCE:
        _mark_step(state, step, status="running", started=True)
        try:
            summary = _STEP_FUNCS[step](state, db_path)
        except Exception as e:  # noqa: BLE001 — runner 는 모든 예외를 status 로 흡수.
            logger.exception(f"ml_job_runner 단계 실패 step={step}")
            _mark_step(state, step, status="failed", message=str(e), finished=True)
            # 이후 단계 skipped.
            failed_idx = STEP_SEQUENCE.index(step)
            for later in STEP_SEQUENCE[failed_idx + 1 :]:  # noqa: E203
                _mark_step(state, later, status="skipped", message="이전 단계 실패")
            state["status"] = "failed"
            state["error"] = f"{step}: {e}"
            state["finished_at"] = _now_kst_iso()
            _heartbeat(state)
            return
        _mark_step(
            state,
            step,
            status="success",
            message=json.dumps(summary, ensure_ascii=False, default=str),
            finished=True,
        )
        if step == STEP_BASELINE:
            last_success_summary = summary

    state["status"] = "success"
    state["last_success_summary"] = last_success_summary
    state["finished_at"] = _now_kst_iso()
    state["message"] = "all steps succeeded"
    _heartbeat(state)


def start_evidence_refresh_job(
    *,
    db_path: Optional[Path] = None,
    requested_by: str = "ui",
    schedule: Optional[Callable[[Callable[[], None]], None]] = None,
) -> dict[str, Any]:
    """ML evidence 갱신 job 을 즉시 시작 + 초기 status 반환 (지시문 §5.7 / AC-2).

    schedule 인자가 주어지면 그것을 통해 background 실행을 위임 (FastAPI
    BackgroundTasks 통합 지점). 미지정 시 threading.Thread 로 실행. 양쪽 모두
    이 함수는 즉시 반환한다 — HTTP 응답이 job 완료를 기다리지 않는다.

    이미 실행 중인 job 이 있고 stale 이 아니면 `JobAlreadyRunningError` 를
    raise (지시문 §5.3 — 새 job 생성 금지, 현재 running 상태를 반환).
    """
    from app.market_data_store import DEFAULT_DB_PATH

    effective_db = db_path or DEFAULT_DB_PATH

    # 1) on-disk lock 확인: stale 이면 무시, 아니면 raise.
    #    FIX r2: 손상 시 fail-loud 로 JobStatusCorruptedError raise (B-1).
    existing, read_err = _read_status_raw()
    if read_err is not None:
        raise JobStatusCorruptedError(JOB_STATUS_PATH, read_err)
    if existing is not None and existing.get("status") == "running":
        if _is_stale_running(existing):
            logger.warning(
                "stale running job 감지 (PID=%s heartbeat=%s) — 새 job 으로 덮어씁니다.",
                existing.get("pid"),
                existing.get("last_heartbeat_at"),
            )
        else:
            raise JobAlreadyRunningError(existing)

    # 2) in-process lock 확인: 동일 프로세스 안에서 동시 trigger 차단.
    if not _RUN_LOCK.acquire(blocking=False):
        latest = _read_status() or existing
        if latest:
            raise JobAlreadyRunningError(latest)
        raise JobAlreadyRunningError(
            {
                "status": "running",
                "message": "in-process lock held without snapshot",
            }
        )

    # 3) 초기 state 작성 + 디스크 기록.
    try:
        started_at = _now_kst_iso()
        job_id = _new_job_id()
        state = _build_initial_state(job_id, requested_by, started_at)
        _write_status(state)
    except Exception:
        _RUN_LOCK.release()
        raise

    def _runner() -> None:
        try:
            _run_job(state, effective_db)
        finally:
            _RUN_LOCK.release()

    if schedule is not None:
        # FastAPI BackgroundTasks 등 — 호출자 책임으로 실행 위임.
        schedule(_runner)
    else:
        thread = threading.Thread(
            target=_runner,
            name=f"ml-evidence-refresh-{job_id}",
            daemon=True,
        )
        thread.start()

    return dict(state)


def main() -> int:
    """CLI 진입점 — 사용자가 터미널에서도 동일 runner 를 호출 가능 (CLI 유지)."""
    try:
        state = start_evidence_refresh_job(requested_by="cli")
    except JobAlreadyRunningError as e:
        print(f"[SKIP] {e}: {e.state.get('job_id')}")
        return 0
    print(f"[START] {state['job_id']} (background)")
    # CLI 모드에서는 thread join 으로 종료 대기 (스크립트 종료 시 daemon 죽는 문제 회피).
    for t in threading.enumerate():
        if t.name.startswith("ml-evidence-refresh-"):
            t.join()
    final = _read_status() or {}
    print(f"[END]   status={final.get('status')} error={final.get('error')}")
    return 0 if final.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
