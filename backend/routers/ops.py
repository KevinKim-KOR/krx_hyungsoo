"""ops 라우터 — daily report, health, scheduler, summary, drill, postmortem, live_fire, cycle."""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.utils import (
    KST,
    BASE_DIR,
    STATE_DIR,
    REPORTS_DIR,
    logger,
)

router = APIRouter()

# --- Path Constants ---

OPS_REPORT_DIR = BASE_DIR / "reports" / "ops" / "daily"
OPS_REPORT_LATEST = OPS_REPORT_DIR / "ops_report_latest.json"
OPS_SNAPSHOTS_DIR = OPS_REPORT_DIR / "snapshots"
OPS_RUNNER_LOCK_FILE = STATE_DIR / "ops_runner.lock"
LOCK_TIMEOUT_SECONDS = 60

SCHEDULER_LATEST_DIR = BASE_DIR / "reports" / "ops" / "scheduler" / "latest"
SCHEDULER_SNAPSHOTS_DIR = BASE_DIR / "reports" / "ops" / "scheduler" / "snapshots"
OPS_RUN_LATEST = SCHEDULER_LATEST_DIR / "ops_run_latest.json"

SUMMARY_DIR = BASE_DIR / "reports" / "ops" / "summary"
SUMMARY_LATEST_FILE = SUMMARY_DIR / "ops_summary_latest.json"

DRILL_LATEST_FILE = (
    BASE_DIR / "reports" / "ops" / "drill" / "latest" / "drill_latest.json"
)

POSTMORTEM_LATEST = (
    BASE_DIR / "reports" / "ops" / "push" / "postmortem" / "postmortem_latest.json"
)

LIVE_FIRE_LATEST = (
    BASE_DIR / "reports" / "ops" / "push" / "live_fire" / "live_fire_latest.json"
)


# --- Helpers ---


def read_jsonl(path: Path) -> List[Dict]:
    """JSONL 파일 읽기"""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    return [json.loads(line) for line in lines if line.strip()]


def check_emergency_stop_status() -> bool:
    """비상 정지 상태 확인"""
    stop_file = STATE_DIR / "emergency_stop.json"
    if not stop_file.exists():
        return False
    try:
        data = json.loads(stop_file.read_text(encoding="utf-8"))
        return data.get("enabled", data.get("active", False))
    except Exception:
        return False


def generate_daily_ops_report() -> dict:
    """Generate daily ops report from ticket data"""
    today = datetime.now(KST).strftime("%Y-%m-%d")

    requests_file = BASE_DIR / "state" / "tickets" / "ticket_requests.jsonl"
    results_file = BASE_DIR / "state" / "tickets" / "ticket_results.jsonl"
    receipts_file = BASE_DIR / "state" / "tickets" / "ticket_receipts.jsonl"

    requests = read_jsonl(requests_file) if requests_file.exists() else []
    results = read_jsonl(results_file) if results_file.exists() else []
    receipts = read_jsonl(receipts_file) if receipts_file.exists() else []

    today_results = [r for r in results if r.get("processed_at", "").startswith(today)]
    today_receipts = [
        r for r in receipts if r.get("asof", r.get("issued_at", "")).startswith(today)
    ]

    done = len([r for r in today_results if r.get("status") == "DONE"])
    failed = len([r for r in today_results if r.get("status") == "FAILED"])
    blocked_receipts = [r for r in today_receipts if r.get("decision") == "BLOCKED"]

    blocked_reasons = {}
    for r in blocked_receipts:
        reasons = r.get("block_reasons", [])
        if not reasons:
            reason = r.get("acceptance", {}).get("reason", "UNKNOWN")
            reasons = [reason]
        for reason in reasons:
            short_reason = reason[:50] if len(reason) > 50 else reason
            blocked_reasons[short_reason] = blocked_reasons.get(short_reason, 0) + 1

    blocked_reasons_top = sorted(
        [{"reason": k, "count": v} for k, v in blocked_reasons.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:3]

    real_receipts = [
        r
        for r in today_receipts
        if r.get("mode") == "REAL" and r.get("decision") == "EXECUTED"
    ]
    last_real = None
    if real_receipts:
        last = real_receipts[-1]
        last_real = {
            "request_id": last.get("request_id"),
            "request_type": last.get("request_type"),
            "exit_code": last.get("exit_code"),
            "acceptance_pass": last.get("acceptance", {}).get("pass", False),
        }

    artifacts_written = []
    for r in real_receipts:
        artifacts = r.get("outputs_proof", {}).get("targets", [])
        for t in artifacts:
            if t.get("changed") and t.get("path") not in artifacts_written:
                artifacts_written.append(t.get("path"))

    report = {
        "schema": "DAILY_OPS_REPORT_V1",
        "asof": datetime.now(KST).isoformat(),
        "period": today,
        "summary": {
            "tickets_total": len(today_results),
            "done": done,
            "failed": failed,
            "blocked": len(blocked_receipts),
        },
        "blocked_reasons_top": blocked_reasons_top,
        "last_real_execution": last_real,
        "artifacts_written": artifacts_written,
        "last_done": None,
        "last_failed": None,
        "last_blocked": None,
        "safety_counters": {
            "window_consumed_count": 0,
            "emergency_stop_hits": 0,
            "allowlist_violation_hits": 0,
            "preflight_fail_hits": 0,
        },
    }

    done_receipts = [r for r in today_receipts if r.get("decision") == "EXECUTED"]
    failed_receipts = [r for r in today_receipts if r.get("decision") == "FAILED"]

    if done_receipts:
        last = done_receipts[-1]
        report["last_done"] = {
            "request_id": last.get("request_id"),
            "request_type": last.get("request_type"),
            "at": last.get("asof", last.get("issued_at")),
        }

    if failed_receipts:
        last = failed_receipts[-1]
        report["last_failed"] = {
            "request_id": last.get("request_id"),
            "request_type": last.get("request_type"),
            "reason": last.get("acceptance", {}).get("reason", "UNKNOWN"),
            "at": last.get("asof", last.get("issued_at")),
        }

    if blocked_receipts:
        last = blocked_receipts[-1]
        reasons = last.get("block_reasons", [])
        reason = (
            reasons[0]
            if reasons
            else last.get("acceptance", {}).get("reason", "UNKNOWN")
        )
        report["last_blocked"] = {
            "request_id": last.get("request_id"),
            "request_type": last.get("request_type"),
            "reason": reason[:50] if len(reason) > 50 else reason,
            "at": last.get("asof", last.get("issued_at")),
        }

    for r in blocked_receipts:
        reasons = r.get("block_reasons", [])
        reason_str = (
            " ".join(reasons).lower()
            if reasons
            else r.get("acceptance", {}).get("reason", "").lower()
        )

        if "window" in reason_str and (
            "consumed" in reason_str
            or "inactive" in reason_str
            or "active" in reason_str
        ):
            report["safety_counters"]["window_consumed_count"] += 1
        if "emergency" in reason_str:
            report["safety_counters"]["emergency_stop_hits"] += 1
        if "allowlist" in reason_str:
            report["safety_counters"]["allowlist_violation_hits"] += 1
        if "preflight" in reason_str:
            report["safety_counters"]["preflight_fail_hits"] += 1

    return report


def save_daily_ops_report(report: dict, skip_if_snapshot_exists: bool = False) -> dict:
    """Save daily ops report to files"""
    OPS_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OPS_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    OPS_REPORT_LATEST.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    today = datetime.now(KST).strftime("%Y%m%d")
    snapshot_path = OPS_SNAPSHOTS_DIR / f"ops_report_{today}.json"

    snapshot_skipped = False
    if snapshot_path.exists() and skip_if_snapshot_exists:
        logger.info(f"Snapshot already exists, skipped: {snapshot_path}")
        snapshot_skipped = True
    else:
        snapshot_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    logger.info(f"Ops report saved: {OPS_REPORT_LATEST}")
    return {
        "snapshot_skipped": snapshot_skipped,
        "snapshot_path": str(snapshot_path),
    }


# ══════════════════════════════════════════════
# READ-ONLY ROUTES
# ══════════════════════════════════════════════


@router.get("/api/ops/daily", summary="일일 운영 리포트 조회")
def get_daily_ops_report_api():
    """Daily Ops Report API (C-P.13)"""
    if not OPS_REPORT_LATEST.exists():
        report = generate_daily_ops_report()
        save_daily_ops_report(report)
    else:
        report = json.loads(OPS_REPORT_LATEST.read_text(encoding="utf-8"))

    return {
        "status": "ready",
        "schema": "DAILY_OPS_REPORT_V1",
        "asof": report.get("asof"),
        "row_count": 1,
        "rows": [report],
        "error": None,
    }


@router.get("/api/ops/health", summary="운영 상태 헬스체크")
def get_ops_health():
    """Ops Health Check API (C-P.17)"""
    try:
        emergency_stop = {"enabled": False, "reason": None}
        stop_file = STATE_DIR / "emergency_stop.json"
        if stop_file.exists():
            data = json.loads(stop_file.read_text(encoding="utf-8"))
            emergency_stop = {
                "enabled": data.get("enabled", False),
                "reason": data.get("reason"),
            }

        gate_mode = "MOCK_ONLY"
        gate_file = STATE_DIR / "execution_gate.json"
        if gate_file.exists():
            data = json.loads(gate_file.read_text(encoding="utf-8"))
            gate_mode = data.get("mode", "MOCK_ONLY")

        window_active = False
        windows_file = STATE_DIR / "real_enable_windows" / "real_enable_windows.jsonl"
        if windows_file.exists():
            windows = read_jsonl(windows_file)
            window_active = any(w.get("status") == "ACTIVE" for w in windows)

        allowlist_version = "N/A"
        allowlist_file = BASE_DIR / "docs" / "contracts" / "execution_allowlist_v1.json"
        if allowlist_file.exists():
            data = json.loads(allowlist_file.read_text(encoding="utf-8"))
            allowlist_version = data.get("version", "v1")

        ops_report = None
        ops_file = BASE_DIR / "reports" / "ops" / "daily" / "ops_report_latest.json"
        if ops_file.exists():
            data = json.loads(ops_file.read_text(encoding="utf-8"))
            ops_report = {
                "asof": data.get("asof"),
                "summary": data.get("summary"),
                "last_done": data.get("last_done"),
                "last_failed": data.get("last_failed"),
                "last_blocked": data.get("last_blocked"),
            }

        health = "OK"
        if emergency_stop.get("enabled"):
            health = "STOPPED"
        elif gate_mode == "REAL_ENABLED" and not window_active:
            health = "WARNING"

        return {
            "status": "ready",
            "schema": "OPS_HEALTH_V1",
            "asof": datetime.now(KST).isoformat(),
            "health": health,
            "data": {
                "emergency_stop": emergency_stop,
                "execution_gate_mode": gate_mode,
                "window_active": window_active,
                "allowlist_version": allowlist_version,
                "last_ops_report": ops_report,
            },
            "error": None,
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {"status": "error", "health": "ERROR", "error": str(e)}


@router.get("/api/ops/scheduler/latest", summary="Ops Run Receipt 최신 조회")
def get_scheduler_latest():
    """Ops Run Receipt Latest (C-P.28)"""
    if not OPS_RUN_LATEST.exists():
        return {
            "status": "not_ready",
            "schema": "OPS_RUN_RECEIPT_V1",
            "asof": datetime.now(KST).isoformat(),
            "row_count": 0,
            "rows": [],
            "error": {
                "code": "NO_RUN_HISTORY",
                "message": "No run history yet.",
            },
        }

    try:
        data = json.loads(OPS_RUN_LATEST.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "OPS_RUN_RECEIPT_V1",
            "asof": data.get("asof"),
            "row_count": 1,
            "rows": [data],
            "error": None,
        }
    except Exception as e:
        return {
            "status": "error",
            "schema": "OPS_RUN_RECEIPT_V1",
            "asof": datetime.now(KST).isoformat(),
            "row_count": 0,
            "rows": [],
            "error": {"code": "READ_ERROR", "message": str(e)},
        }


@router.get("/api/ops/scheduler/snapshots", summary="Ops Run Snapshots 목록")
def get_scheduler_snapshots():
    """Ops Scheduler Snapshots List (C-P.28)"""
    snapshots_dir = SCHEDULER_SNAPSHOTS_DIR

    if not snapshots_dir.exists():
        return {
            "status": "ready",
            "schema": "OPS_SCHEDULER_SNAPSHOTS_V1",
            "asof": datetime.now(KST).isoformat(),
            "directory": str(snapshots_dir.relative_to(BASE_DIR)),
            "row_count": 0,
            "rows": [],
            "error": None,
        }

    try:
        files = []
        for f in sorted(snapshots_dir.iterdir(), reverse=True)[:20]:
            if f.is_file() and f.suffix == ".json":
                stat = f.stat()
                files.append(
                    {
                        "filename": f.name,
                        "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "size_bytes": stat.st_size,
                    }
                )

        return {
            "status": "ready",
            "schema": "OPS_SCHEDULER_SNAPSHOTS_V1",
            "asof": datetime.now(KST).isoformat(),
            "directory": str(snapshots_dir.relative_to(BASE_DIR)),
            "row_count": len(files),
            "rows": files,
            "error": None,
        }
    except Exception as e:
        return {
            "status": "error",
            "schema": "OPS_SCHEDULER_SNAPSHOTS_V1",
            "asof": datetime.now(KST).isoformat(),
            "directory": str(snapshots_dir.relative_to(BASE_DIR)),
            "row_count": 0,
            "rows": [],
            "error": {"code": "READ_ERROR", "message": str(e)},
        }


@router.get(
    "/api/ops/scheduler/snapshots/{snapshot_id}",
    summary="스냅샷 단건 조회",
)
def get_scheduler_snapshot_by_id(snapshot_id: str):
    """Ops Scheduler Snapshot Single View (C-P.29)"""
    pattern = r"^[a-zA-Z0-9_\-\.]+\.json$"
    if not re.match(pattern, snapshot_id):
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "schema": "OPS_SNAPSHOT_VIEWER_V1",
                "error": {
                    "code": "INVALID_ID",
                    "message": (f"Invalid snapshot_id format: {snapshot_id}"),
                },
            },
        )

    if "/" in snapshot_id or "\\" in snapshot_id or ".." in snapshot_id:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "schema": "OPS_SNAPSHOT_VIEWER_V1",
                "error": {
                    "code": "INVALID_ID",
                    "message": "Path traversal detected",
                },
            },
        )

    snapshot_path = SCHEDULER_SNAPSHOTS_DIR / snapshot_id

    if not snapshot_path.exists():
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "schema": "OPS_SNAPSHOT_VIEWER_V1",
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Snapshot not found: {snapshot_id}",
                },
            },
        )

    try:
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": data.get("schema", "OPS_RUN_RECEIPT_V1"),
            "snapshot_id": snapshot_id,
            "data": data,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "schema": "OPS_SNAPSHOT_VIEWER_V1",
                "error": {
                    "code": "READ_ERROR",
                    "message": str(e),
                },
            },
        )


@router.get("/api/ops/summary/latest", summary="Ops Summary 최신 조회")
def get_ops_summary_latest():
    """Ops Summary Latest (C-P.35)"""
    if not SUMMARY_LATEST_FILE.exists():
        return {
            "status": "ready",
            "schema": "OPS_SUMMARY_V1",
            "asof": None,
            "row_count": 1,
            "rows": [
                {
                    "overall_status": "NO_RUN_HISTORY",
                    "guard": None,
                    "last_run_triplet": None,
                    "tickets": None,
                    "push": None,
                    "evidence": None,
                    "top_risks": [],
                }
            ],
            "error": {
                "code": "NO_SUMMARY_YET",
                "message": "Ops summary not generated yet.",
            },
        }

    try:
        data = json.loads(SUMMARY_LATEST_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "OPS_SUMMARY_V1",
            "asof": data.get("asof"),
            "row_count": 1,
            "rows": [data],
            "error": None,
        }
    except Exception as e:
        return {
            "status": "error",
            "schema": "OPS_SUMMARY_V1",
            "asof": datetime.now(KST).isoformat(),
            "row_count": 0,
            "rows": [],
            "error": {"code": "READ_ERROR", "message": str(e)},
        }


@router.get("/api/ops/drill/latest", summary="Ops Drill 최신 조회")
def get_ops_drill_latest():
    """Ops Drill Latest (C-P.37)"""
    if not DRILL_LATEST_FILE.exists():
        return {
            "status": "not_ready",
            "schema": "OPS_DRILL_REPORT_V1",
            "asof": None,
            "row": None,
            "error": {
                "code": "NO_DRILL_YET",
                "message": "Drill report not generated yet.",
            },
        }

    try:
        data = json.loads(DRILL_LATEST_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "OPS_DRILL_REPORT_V1",
            "asof": data.get("asof"),
            "row": data,
            "error": None,
        }
    except Exception as e:
        return {
            "status": "error",
            "schema": "OPS_DRILL_REPORT_V1",
            "asof": datetime.now(KST).isoformat(),
            "row": None,
            "error": {"code": "READ_ERROR", "message": str(e)},
        }


@router.get(
    "/api/ops/push/postmortem/latest",
    summary="Postmortem 최신 조회",
)
def get_postmortem_latest():
    """Live Fire Postmortem Latest (C-P.25)"""
    if not POSTMORTEM_LATEST.exists():
        return {
            "status": "empty",
            "schema": "LIVE_FIRE_POSTMORTEM_V1",
            "data": None,
            "error": ("No postmortem generated yet. " "Use regenerate endpoint."),
        }

    try:
        data = json.loads(POSTMORTEM_LATEST.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "LIVE_FIRE_POSTMORTEM_V1",
            "data": data,
            "error": None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get(
    "/api/ops/push/live_fire/latest",
    summary="Live Fire Ops 최신 조회",
)
def get_live_fire_latest():
    """Live Fire Ops Receipt Latest (C-P.26)"""
    if not LIVE_FIRE_LATEST.exists():
        return {
            "status": "empty",
            "schema": "LIVE_FIRE_OPS_RECEIPT_V1",
            "data": None,
            "error": "No live fire ops run yet.",
        }

    try:
        data = json.loads(LIVE_FIRE_LATEST.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "LIVE_FIRE_OPS_RECEIPT_V1",
            "data": data,
            "error": None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ══════════════════════════════════════════════
# MUTATING ROUTES
# ══════════════════════════════════════════════


@router.post(
    "/api/ops/daily/regenerate",
    summary="일일 운영 리포트 재생성",
)
def regenerate_daily_ops_report_api():
    """Regenerate daily ops report (C-P.14)"""
    report = generate_daily_ops_report()
    save_result = save_daily_ops_report(report, skip_if_snapshot_exists=True)
    return {
        "result": "OK",
        "report": report,
        "snapshot_skipped": save_result.get("snapshot_skipped", False),
    }


@router.post(
    "/api/ops/cycle/run",
    summary="운영 관측 루프 1회 실행 (V2)",
)
def run_ops_cycle_api():
    """Ops Cycle Runner API V2 (C-P.16)"""
    try:
        from app.run_ops_cycle import run_ops_cycle_v2

        result = run_ops_cycle_v2()

        if result.get("overall_status") == "STOPPED":
            return result
        elif result.get("result") == "SKIPPED":
            raise HTTPException(status_code=409, detail=result)
        elif result.get("result") == "FAILED":
            raise HTTPException(status_code=500, detail=result)

        return {
            "status": "ready",
            "schema": "OPS_CYCLE_RUN_V2",
            "asof": result.get("snapshot_path", ""),
            "row_count": 1,
            "data": result,
            "error": None,
        }
    except HTTPException:
        raise
    except ImportError as e:
        logger.error(f"Import error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "result": "FAILED",
                "reason": f"Import error: {e}",
            },
        )
    except Exception as e:
        logger.error(f"Ops cycle V2 error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"result": "FAILED", "reason": str(e)},
        )


@router.post("/api/ops/summary/regenerate", summary="Ops Summary 재생성")
def regenerate_ops_summary_endpoint():
    """Ops Summary Regenerate (C-P.35)"""
    try:
        from app.generate_ops_summary import generate_ops_summary

        result = generate_ops_summary()
        return result
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "result": "FAILED",
                "reason": f"Import error: {e}",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"result": "FAILED", "reason": str(e)},
        )


@router.post("/api/ops/drill/run", summary="Ops Drill 실행")
def run_ops_drill_api():
    """Ops Drill Run (C-P.37)"""
    try:
        from app.run_ops_drill import run_ops_drill

        result = run_ops_drill()
        return result
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "result": "FAILED",
                "reason": f"Import error: {e}",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"result": "FAILED", "reason": str(e)},
        )


@router.post(
    "/api/ops/push/postmortem/regenerate",
    summary="Postmortem 재생성",
)
def regenerate_postmortem():
    """Regenerate Live Fire Postmortem (C-P.25)"""
    try:
        from app.generate_live_fire_postmortem import (
            generate_postmortem,
        )

        result = generate_postmortem()
        logger.info(
            f"Postmortem regenerated: " f"{result.get('overall_safety_status')}"
        )
        return result
    except ImportError as e:
        logger.error(f"Postmortem import error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "result": "FAILED",
                "reason": f"Import error: {e}",
            },
        )
    except Exception as e:
        logger.error(f"Postmortem error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"result": "FAILED", "reason": str(e)},
        )


@router.post("/api/ops/push/live_fire/run", summary="Live Fire Ops 실행")
def run_live_fire_ops_api():
    """Run Live Fire Ops Cycle (C-P.26)"""
    try:
        from app.run_live_fire_ops import run_live_fire_ops

        result = run_live_fire_ops()
        logger.info(
            f"Live Fire Ops: attempted={result.get('attempted')}, "
            f"blocked={result.get('blocked_reason')}"
        )
        return result
    except ImportError as e:
        logger.error(f"Live Fire Ops import error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "result": "FAILED",
                "reason": f"Import error: {e}",
            },
        )
    except Exception as e:
        logger.error(f"Live Fire Ops error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"result": "FAILED", "reason": str(e)},
        )
