# -*- coding: utf-8 -*-
"""
app/run_ticket_worker.py
Ticket Worker (Phase C-P.9)

규칙:
- REAL 실행은 REQUEST_REPORTS 1회만 허용
- Preflight 4개 체크 필수
- EXECUTION_RECEIPT_V2 작성
"""
import json
import os
import time
import requests
import shutil
import uuid
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[WORKER] %(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
STATE_DIR = BASE_DIR / "state"
TICKETS_DIR = STATE_DIR / "tickets"
LOCK_FILE = STATE_DIR / "worker.lock"
DRYRUN_DIR = BASE_DIR / "reports" / "tickets" / "dryrun"
SHADOW_DIR = BASE_DIR / "reports" / "tickets" / "shadow"
RECEIPTS_FILE = TICKETS_DIR / "ticket_receipts.jsonl"
EXECUTION_PLAN_FILE = BASE_DIR / "docs" / "contracts" / "execution_plan_v1.json"
ALLOWLIST_FILE = BASE_DIR / "docs" / "contracts" / "execution_allowlist_v1.json"
WINDOWS_FILE = STATE_DIR / "real_enable_windows" / "real_enable_windows.jsonl"

API_BASE = "http://127.0.0.1:8000"
STALE_THRESHOLD_SECONDS = 600

EXPECTED_OUTPUTS = {
    "REQUEST_RECONCILE": [
        "reports/phase_c/latest/recon_summary.json",
        "reports/phase_c/latest/recon_daily.jsonl"
    ],
    "REQUEST_REPORTS": [
        "reports/phase_c/latest/report_human.json",
        "reports/phase_c/latest/report_ai.json"
    ]
}


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    return [json.loads(line) for line in lines if line.strip()]


def get_open_tickets() -> list:
    requests_file = TICKETS_DIR / "ticket_requests.jsonl"
    results_file = TICKETS_DIR / "ticket_results.jsonl"
    reqs = read_jsonl(requests_file)
    results = read_jsonl(results_file)
    open_tickets = []
    for req in reqs:
        rid = req.get("request_id")
        req_results = [r for r in results if r.get("request_id") == rid]
        if req_results:
            latest = max(req_results, key=lambda x: x.get("processed_at", ""))
            current_status = latest.get("status", "OPEN")
        else:
            current_status = "OPEN"
        if current_status == "OPEN":
            open_tickets.append(req)
    return open_tickets


def acquire_lock() -> bool:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            lock_data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            acquired_at = datetime.fromisoformat(lock_data.get("acquired_at", ""))
            age_seconds = (datetime.now() - acquired_at).total_seconds()
            if age_seconds < STALE_THRESHOLD_SECONDS:
                return False
        except:
            pass
    lock_data = {"pid": os.getpid(), "acquired_at": datetime.now().isoformat()}
    LOCK_FILE.write_text(json.dumps(lock_data, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Lock acquired (PID: {os.getpid()})")
    return True


def release_lock():
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()
        logger.info("Lock released")


# === Preflight Checks ===

def check_emergency_stop() -> dict:
    try:
        resp = requests.get(f"{API_BASE}/api/emergency_stop", timeout=5)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            return {"passed": not data.get("enabled", False), "enabled": data.get("enabled", False)}
    except:
        pass
    return {"passed": True, "enabled": False}


def check_approval() -> dict:
    try:
        resp = requests.get(f"{API_BASE}/api/approvals/real_enable/latest", timeout=5)
        if resp.status_code == 200:
            data = resp.json().get("data")
            if data:
                status = data.get("status", "PENDING")
                return {"passed": status == "APPROVED", "status": status}
    except:
        pass
    return {"passed": False, "status": "NONE"}


def check_window(request_type: str) -> dict:
    try:
        resp = requests.get(f"{API_BASE}/api/real_enable_window/latest", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            rows = data.get("rows", [])
            if rows:
                window = rows[0]
                allowed_types = window.get("allowed_request_types", [])
                used = window.get("real_executions_used", 0)
                max_exec = window.get("max_real_executions", 1)
                type_ok = request_type in allowed_types
                not_consumed = used < max_exec
                return {
                    "passed": type_ok and not_consumed,
                    "window_id": window.get("window_id"),
                    "status": window.get("status"),
                    "type_allowed": type_ok,
                    "not_consumed": not_consumed
                }
    except:
        pass
    return {"passed": False, "window_id": None, "status": "NONE"}


def get_gate_mode() -> str:
    try:
        resp = requests.get(f"{API_BASE}/api/execution_gate", timeout=5)
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("mode", "MOCK_ONLY")
    except:
        pass
    return "MOCK_ONLY"


def load_execution_plan() -> dict:
    if not EXECUTION_PLAN_FILE.exists():
        return {}
    try:
        return json.loads(EXECUTION_PLAN_FILE.read_text(encoding="utf-8")).get("plans", {})
    except:
        return {}


def load_allowlist() -> dict:
    if not ALLOWLIST_FILE.exists():
        return {}
    try:
        return json.loads(ALLOWLIST_FILE.read_text(encoding="utf-8"))
    except:
        return {}


def validate_allowlist(request_type: str, cmd: list) -> dict:
    allowlist = load_allowlist()
    violations = []
    if not allowlist:
        return {"passed": False, "violations": ["Allowlist not available"]}
    
    allowed_types = allowlist.get("allowed_request_types", [])
    if request_type not in allowed_types:
        violations.append(f"request_type '{request_type}' not allowed")
    
    rules = allowlist.get("rules", {}).get(request_type, {})
    cmd_allowlist = rules.get("real_command_allowlist", [])
    if cmd not in cmd_allowlist:
        violations.append(f"command {cmd} not in allowlist")
    
    return {"passed": len(violations) == 0, "violations": violations}


def get_file_info(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    stat = path.stat()
    return {
        "exists": True,
        "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "size": stat.st_size
    }


def consume_ticket(request_id: str) -> bool:
    try:
        resp = requests.post(
            f"{API_BASE}/api/tickets/consume",
            json={"request_id": request_id, "processor_id": f"worker_{os.getpid()}"}
        )
        return resp.status_code == 200
    except:
        return False


def complete_ticket(request_id: str, status: str, message: str, artifacts: list = None) -> bool:
    try:
        resp = requests.post(
            f"{API_BASE}/api/tickets/complete",
            json={
                "request_id": request_id,
                "status": status,
                "message": message,
                "processor_id": f"worker_{os.getpid()}",
                "artifacts": artifacts or []
            }
        )
        return resp.status_code == 200
    except:
        return False


def consume_window(window_id: str):
    """Mark window as consumed (Append CONSUME event)"""
    WINDOWS_DIR = STATE_DIR / "real_enable_windows"
    WINDOWS_DIR.mkdir(parents=True, exist_ok=True)
    
    consume_event = {
        "schema": "REAL_ENABLE_WINDOW_V1",
        "event": "CONSUME",
        "window_id": window_id,
        "consumed_at": datetime.now().isoformat()
    }
    with open(WINDOWS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(consume_event, ensure_ascii=False) + "\n")
    logger.info(f"Window consumed: {window_id}")


def write_receipt_v2(
    request_id: str, mode: str, decision: str, 
    block_reasons: list, started_at: str, finished_at: str,
    command: list, exit_code: int, artifacts: list,
    latest_files_changed: dict, safety_checks: dict
):
    """Write EXECUTION_RECEIPT_V2"""
    TICKETS_DIR.mkdir(parents=True, exist_ok=True)
    
    receipt = {
        "schema": "EXECUTION_RECEIPT_V2",
        "receipt_id": str(uuid.uuid4()),
        "request_id": request_id,
        "mode": mode,
        "decision": decision,
        "block_reasons": block_reasons,
        "started_at": started_at,
        "finished_at": finished_at,
        "command": command,
        "exit_code": exit_code,
        "artifacts_written": artifacts,
        "latest_files_changed": latest_files_changed,
        "safety_checks": safety_checks
    }
    
    with open(RECEIPTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    
    logger.info(f"Receipt V2 written: {decision}")
    return receipt


def process_ticket_real(ticket: dict, plans: dict, window_info: dict, safety_checks: dict) -> bool:
    """Process ticket with REAL execution (REQUEST_REPORTS only)"""
    request_id = ticket.get("request_id")
    request_type = ticket.get("request_type")
    
    plan = plans.get(request_type, {})
    cmd = plan.get("cmd", [])
    
    started_at = datetime.now().isoformat()
    
    # Get before state of files
    outputs = EXPECTED_OUTPUTS.get(request_type, [])
    files_before = {}
    for output in outputs:
        path = BASE_DIR / output
        files_before[output] = get_file_info(path)
    
    # Execute!
    logger.info(f"[REAL] Executing: {cmd}")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=120
        )
        exit_code = result.returncode
        logger.info(f"[REAL] Exit code: {exit_code}")
        if result.stdout:
            logger.info(f"[REAL] stdout: {result.stdout[:500]}")
        if result.stderr:
            logger.warning(f"[REAL] stderr: {result.stderr[:500]}")
    except subprocess.TimeoutExpired:
        exit_code = -1
        logger.error("[REAL] Execution timed out")
    except Exception as e:
        exit_code = -1
        logger.error(f"[REAL] Execution failed: {e}")
    
    finished_at = datetime.now().isoformat()
    
    # Get after state of files
    files_after = {}
    latest_files_changed = {}
    artifacts_written = []
    
    for output in outputs:
        path = BASE_DIR / output
        files_after[output] = get_file_info(path)
        
        if files_after[output]["exists"]:
            artifacts_written.append(output)
            if files_before[output]["exists"]:
                if files_before[output]["mtime"] != files_after[output]["mtime"]:
                    latest_files_changed[output] = {
                        "mtime_before": files_before[output]["mtime"],
                        "mtime_after": files_after[output]["mtime"]
                    }
            else:
                latest_files_changed[output] = {
                    "mtime_before": None,
                    "mtime_after": files_after[output]["mtime"]
                }
    
    # Consume window immediately
    if window_info.get("window_id"):
        consume_window(window_info["window_id"])
    
    # Write receipt
    decision = "EXECUTED" if exit_code == 0 else "FAILED"
    write_receipt_v2(
        request_id=request_id,
        mode="REAL",
        decision=decision,
        block_reasons=[],
        started_at=started_at,
        finished_at=finished_at,
        command=cmd,
        exit_code=exit_code,
        artifacts=artifacts_written,
        latest_files_changed=latest_files_changed,
        safety_checks=safety_checks
    )
    
    # Complete ticket
    status = "DONE" if exit_code == 0 else "FAILED"
    message = f"[REAL] {decision}: exit_code={exit_code}, files_changed={len(latest_files_changed)}"
    return complete_ticket(request_id, status, message, artifacts_written)


def process_ticket(ticket: dict, mode: str) -> bool:
    """Process ticket with preflight checks"""
    request_id = ticket.get("request_id")
    request_type = ticket.get("request_type", "UNKNOWN")
    
    logger.info(f"Processing: {request_id} ({request_type}) [Mode: {mode}]")
    
    if not consume_ticket(request_id):
        return False
    
    plans = load_execution_plan()
    plan = plans.get(request_type, {})
    cmd = plan.get("cmd", [])
    
    # === PREFLIGHT CHECKS ===
    started_at = datetime.now().isoformat()
    block_reasons = []
    
    # (A) Emergency Stop
    estop = check_emergency_stop()
    if not estop["passed"]:
        block_reasons.append("Emergency Stop is ON")
    
    # (B) Two-Key Approval
    approval = check_approval()
    if not approval["passed"]:
        block_reasons.append(f"Approval not APPROVED (status: {approval['status']})")
    
    # (C) Allowlist
    allowlist_check = validate_allowlist(request_type, cmd)
    if not allowlist_check["passed"]:
        block_reasons.extend(allowlist_check["violations"])
    
    # (D) Window
    window_info = check_window(request_type)
    if not window_info["passed"]:
        block_reasons.append(f"Window not ACTIVE or type not allowed (status: {window_info['status']})")
    
    safety_checks = {
        "emergency_stop": estop["enabled"],
        "approval_status": approval["status"],
        "allowlist_pass": allowlist_check["passed"],
        "window_active": window_info["passed"],
        "window_id": window_info.get("window_id")
    }
    
    # === MODE ROUTING ===
    if mode == "MOCK_ONLY":
        time.sleep(1)
        write_receipt_v2(request_id, "MOCK_ONLY", "EXECUTED", [], started_at, datetime.now().isoformat(), [], None, [], {}, safety_checks)
        return complete_ticket(request_id, "DONE", f"[MOCK_ONLY] Simulated {request_type}")
    
    elif mode == "DRY_RUN":
        write_receipt_v2(request_id, "DRY_RUN", "EXECUTED", [], started_at, datetime.now().isoformat(), cmd, None, [], {}, safety_checks)
        return complete_ticket(request_id, "DONE", f"[DRY_RUN] Validated {request_type}")
    
    elif mode == "REAL_ENABLED":
        # REAL mode requires all checks pass
        if block_reasons:
            logger.warning(f"[BLOCKED] {block_reasons}")
            write_receipt_v2(request_id, "REAL", "BLOCKED", block_reasons, started_at, datetime.now().isoformat(), cmd, None, [], {}, safety_checks)
            return complete_ticket(request_id, "FAILED", f"[BLOCKED] {block_reasons}")
        
        # C-P.9: Only REQUEST_REPORTS allowed
        if request_type != "REQUEST_REPORTS":
            block_reasons.append(f"C-P.9: Only REQUEST_REPORTS allowed, got {request_type}")
            write_receipt_v2(request_id, "REAL", "BLOCKED", block_reasons, started_at, datetime.now().isoformat(), cmd, None, [], {}, safety_checks)
            return complete_ticket(request_id, "FAILED", f"[BLOCKED] {block_reasons}")
        
        # All checks passed - REAL EXECUTE
        return process_ticket_real(ticket, plans, window_info, safety_checks)
    
    else:
        return complete_ticket(request_id, "DONE", f"[UNKNOWN] Processed")


def run_worker():
    logger.info("=" * 50)
    logger.info("Ticket Worker Starting (C-P.9)...")
    
    mode = get_gate_mode()
    logger.info(f"Execution Gate Mode: {mode}")
    
    if not acquire_lock():
        logger.error("Failed to acquire lock.")
        return False
    
    try:
        open_tickets = get_open_tickets()
        logger.info(f"Found {len(open_tickets)} OPEN ticket(s)")
        
        if not open_tickets:
            logger.info("No OPEN tickets.")
            return True
        
        ticket = open_tickets[0]
        success = process_ticket(ticket, mode)
        
        if success:
            logger.info("Ticket processed successfully!")
        else:
            logger.warning("Ticket processing failed.")
        
        return success
        
    finally:
        release_lock()
        logger.info("Worker finished.")
        logger.info("=" * 50)


if __name__ == "__main__":
    run_worker()
