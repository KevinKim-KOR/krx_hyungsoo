"""
Ops Cycle Runner V2 (C-P.16)
운영 관측 루프 1회 + 티켓 0~1건 처리

주의: 
- 티켓 처리는 최대 1건 (Bounded Processing)
- 모든 안전장치 우회 금지
"""

import json
import uuid
import logging
from datetime import datetime
from pathlib import Path

import requests

# Setup
BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
TICKETS_DIR = STATE_DIR / "tickets"
OPS_DIR = BASE_DIR / "reports" / "ops" / "daily"
SNAPSHOTS_DIR = OPS_DIR / "snapshots"
LOCK_FILE = STATE_DIR / "ops_runner.lock"
EMERGENCY_STOP_FILE = STATE_DIR / "emergency_stop.json"
GATE_FILE = STATE_DIR / "execution_gate.json"
WINDOWS_FILE = STATE_DIR / "real_enable_windows" / "real_enable_windows.jsonl"
ALLOWLIST_FILE = BASE_DIR / "docs" / "contracts" / "execution_allowlist_v1.json"

API_BASE = "http://127.0.0.1:8000"
LOCK_TIMEOUT_SECONDS = 60

logging.basicConfig(level=logging.INFO, format="[OPS_RUNNER_V2] %(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    return [json.loads(line) for line in lines if line.strip()]


def check_emergency_stop() -> bool:
    """비상 정지 상태 확인"""
    if not EMERGENCY_STOP_FILE.exists():
        return False
    try:
        data = json.loads(EMERGENCY_STOP_FILE.read_text(encoding="utf-8"))
        return data.get("enabled", data.get("active", False))
    except Exception:
        return False


def get_execution_gate_mode() -> str:
    """실행 게이트 모드 조회"""
    if not GATE_FILE.exists():
        return "MOCK_ONLY"
    try:
        data = json.loads(GATE_FILE.read_text(encoding="utf-8"))
        return data.get("mode", "MOCK_ONLY")
    except Exception:
        return "MOCK_ONLY"


def check_window_active() -> bool:
    """REAL Window 활성 여부"""
    windows = read_jsonl(WINDOWS_FILE)
    for w in windows:
        if w.get("status") == "ACTIVE":
            return True
    return False


def get_allowlist_version() -> str:
    """Allowlist 버전"""
    if not ALLOWLIST_FILE.exists():
        return "N/A"
    try:
        data = json.loads(ALLOWLIST_FILE.read_text(encoding="utf-8"))
        return data.get("version", "v1")
    except Exception:
        return "N/A"


def get_tickets_counters() -> dict:
    """티켓 카운터 계산"""
    requests_file = TICKETS_DIR / "ticket_requests.jsonl"
    results_file = TICKETS_DIR / "ticket_results.jsonl"
    receipts_file = TICKETS_DIR / "ticket_receipts.jsonl"
    
    reqs = read_jsonl(requests_file)
    results = read_jsonl(results_file)
    receipts = read_jsonl(receipts_file)
    
    counters = {
        "tickets_open": 0,
        "tickets_in_progress": 0,
        "tickets_done": 0,
        "tickets_failed": 0,
        "tickets_blocked": 0
    }
    
    for req in reqs:
        rid = req.get("request_id")
        req_results = [r for r in results if r.get("request_id") == rid]
        if req_results:
            latest = max(req_results, key=lambda x: x.get("processed_at", ""))
            status = latest.get("status", "OPEN")
        else:
            status = "OPEN"
        
        if status == "OPEN":
            counters["tickets_open"] += 1
        elif status == "IN_PROGRESS":
            counters["tickets_in_progress"] += 1
        elif status == "DONE":
            counters["tickets_done"] += 1
        elif status == "FAILED":
            counters["tickets_failed"] += 1
    
    # Count blocked from receipts
    for r in receipts:
        if r.get("decision") == "BLOCKED":
            counters["tickets_blocked"] += 1
    
    return counters


def acquire_lock() -> tuple:
    """Lock 확보"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    
    if LOCK_FILE.exists():
        try:
            lock_data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            lock_time = datetime.fromisoformat(lock_data.get("locked_at", ""))
            elapsed = (datetime.now() - lock_time).total_seconds()
            
            if elapsed < LOCK_TIMEOUT_SECONDS:
                return False, f"Locked by {lock_data.get('run_id')} ({elapsed:.0f}s ago)"
        except Exception:
            pass
    
    run_id = str(uuid.uuid4())
    lock_data = {
        "run_id": run_id,
        "locked_at": datetime.now().isoformat()
    }
    LOCK_FILE.write_text(json.dumps(lock_data, ensure_ascii=False), encoding="utf-8")
    return True, run_id


def release_lock():
    """Lock 해제"""
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()


def save_v2_snapshot(run_id: str, overall_status: str, ops_report_ref: str, 
                     ticket_step: dict, safety_snapshot: dict, counters: dict,
                     started_at: str, evidence_health: dict = None) -> str:
    """OPS_CYCLE_RUN_V2 스냅샷 저장 (C-P.34: evidence_health 포함)"""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = SNAPSHOTS_DIR / f"ops_run_{timestamp}.json"
    
    snapshot = {
        "schema": "OPS_CYCLE_RUN_V2",
        "run_id": run_id,
        "asof": datetime.now().isoformat(),
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(),
        "overall_status": overall_status,
        "ops_report_ref": ops_report_ref,
        "evidence_health": evidence_health or {"decision": "N/A"},
        "ticket_step": ticket_step,
        "safety_snapshot": safety_snapshot,
        "counters": {**counters, "skips_this_run": 1 if ticket_step.get("decision") == "SKIPPED" else 0}
    }
    
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"V2 Snapshot saved: {snapshot_path}")
    return str(snapshot_path.relative_to(BASE_DIR))


def run_ops_cycle_v2() -> dict:
    """운영 루프 1회 + 티켓 0~1건 처리 (C-P.16)"""
    started_at = datetime.now().isoformat()
    run_id = None
    
    # Safety snapshot 준비
    safety_snapshot = {
        "emergency_stop_enabled": check_emergency_stop(),
        "execution_gate_mode": get_execution_gate_mode(),
        "window_active": check_window_active(),
        "allowlist_version": get_allowlist_version()
    }
    
    # Default ticket_step
    ticket_step = {
        "attempted": False,
        "selected_request_id": None,
        "selected_request_type": None,
        "decision": "NONE",
        "reason": "NO_OPEN_TICKETS",
        "receipt_ref": None
    }
    
    # Step 1: Emergency Stop 확인
    if safety_snapshot["emergency_stop_enabled"]:
        logger.warning("Emergency Stop is ACTIVE. Aborting.")
        ticket_step["decision"] = "SKIPPED"
        ticket_step["reason"] = "EMERGENCY_STOP_ACTIVE"
        
        snapshot_path = save_v2_snapshot(
            run_id="N/A",
            overall_status="STOPPED",
            ops_report_ref="",
            ticket_step=ticket_step,
            safety_snapshot=safety_snapshot,
            counters=get_tickets_counters(),
            started_at=started_at,
            evidence_health={"decision": "N/A", "fail_closed_triggered": False, "reason": "EMERGENCY_STOP"}
        )
        return {
            "result": "STOPPED",
            "overall_status": "STOPPED",
            "reason": "EMERGENCY_STOP_ACTIVE",
            "snapshot_path": snapshot_path,
            "ticket_step": ticket_step
        }
    
    # Step 1.5 (C-P.34): Evidence Health Gate - Fail-Closed
    evidence_health = {
        "decision": "UNKNOWN",
        "generated_at": None,
        "latest_ref": "reports/ops/evidence/health/health_latest.json",
        "snapshot_ref": None,
        "top_fail_reasons": [],
        "fail_closed_triggered": False,
        "error_summary": None
    }
    
    try:
        from app.run_evidence_health_check import regenerate_health_report
        health_result = regenerate_health_report()
        evidence_health["decision"] = health_result.get("decision", "UNKNOWN")
        evidence_health["generated_at"] = datetime.now().isoformat()
        evidence_health["snapshot_ref"] = health_result.get("snapshot_path")
        
        # Load health_latest for top_fail_reasons
        health_latest_path = BASE_DIR / "reports" / "ops" / "evidence" / "health" / "health_latest.json"
        if health_latest_path.exists():
            health_data = json.loads(health_latest_path.read_text(encoding="utf-8"))
            evidence_health["top_fail_reasons"] = [r["reason"] for r in health_data.get("top_fail_reasons", [])[:3]]
        
        logger.info(f"Evidence Health decision: {evidence_health['decision']}")
    except Exception as e:
        # Fail-Closed: 예외 발생 시 무조건 FAIL
        logger.error(f"Evidence Health FAIL-CLOSED: {e}")
        evidence_health["decision"] = "FAIL"
        evidence_health["fail_closed_triggered"] = True
        evidence_health["error_summary"] = str(e)[:100]  # 짧은 요약만
    
    # Guard 판정: FAIL이면 downstream SKIP
    if evidence_health["decision"] == "FAIL":
        logger.warning("Evidence Health FAIL. Blocking downstream.")
        ticket_step["decision"] = "SKIPPED"
        ticket_step["reason"] = "EVIDENCE_HEALTH_FAIL"
        
        snapshot_path = save_v2_snapshot(
            run_id="N/A",
            overall_status="BLOCKED",
            ops_report_ref="",
            ticket_step=ticket_step,
            safety_snapshot=safety_snapshot,
            counters=get_tickets_counters(),
            started_at=started_at,
            evidence_health=evidence_health
        )
        return {
            "result": "BLOCKED",
            "overall_status": "BLOCKED",
            "reason": "EVIDENCE_HEALTH_FAIL",
            "snapshot_path": snapshot_path,
            "ticket_step": ticket_step,
            "evidence_health": evidence_health
        }
    
    # Step 2: Lock 확보
    locked, lock_result = acquire_lock()
    if not locked:
        logger.warning(f"Lock failed: {lock_result}")
        ticket_step["decision"] = "SKIPPED"
        ticket_step["reason"] = "LOCK_CONFLICT_409"
        
        snapshot_path = save_v2_snapshot(
            run_id="N/A",
            overall_status="DONE_WITH_SKIPS",
            ops_report_ref="",
            ticket_step=ticket_step,
            safety_snapshot=safety_snapshot,
            counters=get_tickets_counters(),
            started_at=started_at,
            evidence_health=evidence_health
        )
        return {
            "result": "SKIPPED",
            "overall_status": "DONE_WITH_SKIPS",
            "reason": lock_result,
            "snapshot_path": snapshot_path,
            "ticket_step": ticket_step
        }
    
    run_id = lock_result
    logger.info(f"Lock acquired. run_id={run_id}")
    
    try:
        # Step 3: Ops Report regenerate
        ops_report_ref = "reports/ops/daily/ops_report_latest.json"
        try:
            resp = requests.post(f"{API_BASE}/api/ops/daily/regenerate", timeout=30)
            if resp.status_code == 200:
                logger.info("Ops report regenerated")
            else:
                logger.error(f"Ops regenerate failed: {resp.status_code}")
        except Exception as e:
            logger.error(f"Ops regenerate error: {e}")
        
        # Step 4: Ticket 1건 처리 (Worker import)
        try:
            from app.run_ticket_worker import process_one_ticket
            ticket_step = process_one_ticket(skip_lock=True)  # Lock은 이미 확보됨
            logger.info(f"Ticket step result: {ticket_step}")
        except ImportError as e:
            logger.error(f"Worker import error: {e}")
            ticket_step["decision"] = "SKIPPED"
            ticket_step["reason"] = f"WORKER_IMPORT_ERROR: {e}"
        except Exception as e:
            logger.error(f"Ticket processing error: {e}")
            ticket_step["decision"] = "SKIPPED"
            ticket_step["reason"] = f"TICKET_PROCESS_ERROR: {e}"
        
        # Step 5: 최종 상태 결정
        if ticket_step.get("decision") == "PROCESSED":
            overall_status = "DONE"
        elif ticket_step.get("decision") == "SKIPPED":
            overall_status = "DONE_WITH_SKIPS"
        else:  # NONE
            overall_status = "DONE"
        
        # Step 6: V2 Snapshot 저장
        counters = get_tickets_counters()
        snapshot_path = save_v2_snapshot(
            run_id=run_id,
            overall_status=overall_status,
            ops_report_ref=ops_report_ref,
            ticket_step=ticket_step,
            safety_snapshot=safety_snapshot,
            counters=counters,
            started_at=started_at,
            evidence_health=evidence_health
        )
        
        return {
            "result": "OK",
            "overall_status": overall_status,
            "reason": ticket_step.get("reason", "CYCLE_COMPLETE"),
            "run_id": run_id,
            "snapshot_path": snapshot_path,
            "ticket_step": ticket_step,
            "counters": counters,
            "evidence_health": evidence_health
        }
        
    except Exception as e:
        logger.error(f"Cycle failed: {e}")
        ticket_step["decision"] = "SKIPPED"
        ticket_step["reason"] = str(e)
        
        snapshot_path = save_v2_snapshot(
            run_id=run_id or "N/A",
            overall_status="FAILED",
            ops_report_ref="",
            ticket_step=ticket_step,
            safety_snapshot=safety_snapshot,
            counters=get_tickets_counters(),
            started_at=started_at,
            evidence_health=evidence_health
        )
        return {
            "result": "FAILED",
            "overall_status": "FAILED",
            "reason": str(e),
            "snapshot_path": snapshot_path,
            "ticket_step": ticket_step,
            "evidence_health": evidence_health
        }
    
    finally:
        release_lock()
        logger.info("Lock released.")


# Legacy alias for backward compatibility
run_ops_cycle = run_ops_cycle_v2


if __name__ == "__main__":
    result = run_ops_cycle_v2()
    print(json.dumps(result, ensure_ascii=False, indent=2))
