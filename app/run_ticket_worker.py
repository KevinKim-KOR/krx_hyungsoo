# -*- coding: utf-8 -*-
"""
app/run_ticket_worker.py
Ticket Worker (Phase C-P.8)

규칙:
- No Execution: 실제 엔진 실행 금지
- Allowlist Enforcement: 허용목록 exact match 검증
- Shadow Run: REAL_ENABLED면 Shadow로 강제 처리
"""
import json
import os
import time
import requests
import shutil
import uuid
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

API_BASE = "http://127.0.0.1:8000"
STALE_THRESHOLD_SECONDS = 600


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
                logger.warning(f"Lock already held (age: {age_seconds:.0f}s)")
                return False
            else:
                logger.warning(f"Stale lock. Force acquiring...")
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


def check_emergency_stop() -> dict:
    try:
        resp = requests.get(f"{API_BASE}/api/emergency_stop", timeout=5)
        if resp.status_code == 200:
            return resp.json().get("data", {})
    except:
        pass
    return {"enabled": False}


def get_gate_mode() -> str:
    try:
        resp = requests.get(f"{API_BASE}/api/execution_gate", timeout=5)
        if resp.status_code == 200:
            mode = resp.json().get("data", {}).get("mode", "MOCK_ONLY")
            logger.info(f"Gate mode: {mode}")
            return mode
    except:
        pass
    return "MOCK_ONLY"


def load_execution_plan() -> dict:
    if not EXECUTION_PLAN_FILE.exists():
        return {}
    try:
        data = json.loads(EXECUTION_PLAN_FILE.read_text(encoding="utf-8"))
        return data.get("plans", {})
    except:
        return {}


def load_allowlist() -> dict:
    """Load immutable allowlist from docs/contracts/"""
    if not ALLOWLIST_FILE.exists():
        logger.error(f"Allowlist not found: {ALLOWLIST_FILE}")
        return {}
    try:
        data = json.loads(ALLOWLIST_FILE.read_text(encoding="utf-8"))
        logger.info(f"Allowlist loaded: v{data.get('version')}")
        return data
    except Exception as e:
        logger.error(f"Failed to load allowlist: {e}")
        return {}


def write_receipt(request_id: str, mode: str, result: str, message: str, artifacts: list = None) -> str:
    TICKETS_DIR.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema": "EXECUTION_RECEIPT_V1",
        "receipt_id": str(uuid.uuid4()),
        "request_id": request_id,
        "issued_at": datetime.now().isoformat(),
        "mode": mode,
        "result": result,
        "message": message,
        "artifacts": artifacts or []
    }
    with open(RECEIPTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    logger.info(f"Receipt written: {result}")
    return receipt["receipt_id"]


def consume_ticket(request_id: str) -> bool:
    try:
        resp = requests.post(
            f"{API_BASE}/api/tickets/consume",
            json={"request_id": request_id, "processor_id": f"worker_{os.getpid()}"}
        )
        if resp.status_code == 200:
            logger.info(f"Consumed ticket: {request_id}")
            return True
        elif resp.status_code == 409:
            logger.info(f"Already consumed (409)")
            return False
        else:
            logger.error(f"Consume failed ({resp.status_code})")
            return False
    except Exception as e:
        logger.error(f"Consume failed: {e}")
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


def deep_validate(request_id: str, request_type: str, plans: dict) -> dict:
    """Deep Validation - checks module existence"""
    checks = {}
    errors = []
    
    plan = plans.get(request_type)
    checks["plan_exists"] = plan is not None
    if not plan:
        errors.append(f"No plan for: {request_type}")
    
    cmd = plan.get("cmd", []) if plan else []
    module_path = plan.get("module", "") if plan else ""
    
    checks["python_available"] = shutil.which("python") is not None
    
    if module_path:
        full_path = BASE_DIR / module_path
        checks["module_exists"] = full_path.exists()
        if not full_path.exists():
            errors.append(f"Module not found: {module_path}")
    else:
        checks["module_exists"] = False
    
    return {
        "valid": all(checks.values()) and len(errors) == 0,
        "cmd": cmd,
        "checks": checks,
        "errors": errors
    }


def validate_against_allowlist(request_type: str, cmd: list, expected_outputs: list) -> dict:
    """Validate against immutable allowlist (exact match only)"""
    allowlist = load_allowlist()
    violations = []
    
    if not allowlist:
        return {"allowed": False, "violations": ["Allowlist not available"], "version": None}
    
    version = allowlist.get("version", "unknown")
    allowed_types = allowlist.get("allowed_request_types", [])
    rules = allowlist.get("rules", {})
    
    # Check 1: request_type in allowed_request_types
    if request_type not in allowed_types:
        violations.append(f"request_type '{request_type}' not in allowed_request_types")
    
    # Get rule for this request_type
    rule = rules.get(request_type, {})
    
    # Check 2: command exact match
    cmd_allowlist = rule.get("real_command_allowlist", [])
    if cmd not in cmd_allowlist:
        violations.append(f"command {cmd} not in real_command_allowlist (exact match required)")
    
    # Check 3: expected outputs exact match
    output_allowlist = rule.get("expected_outputs_allowlist", [])
    for output in expected_outputs:
        if output not in output_allowlist:
            violations.append(f"output '{output}' not in expected_outputs_allowlist")
    
    return {
        "allowed": len(violations) == 0,
        "violations": violations,
        "version": version
    }


# Expected outputs mapping
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


def save_dryrun_artifact(request_id: str, request_type: str, validation: dict, allowlist_result: dict) -> str:
    DRYRUN_DIR.mkdir(parents=True, exist_ok=True)
    
    decision = "SHADOW_OK" if (validation["valid"] and allowlist_result["allowed"]) else "SHADOW_BLOCKED"
    
    artifact = {
        "schema": "DRYRUN_ARTIFACT_V1",
        "asof": datetime.now().isoformat(),
        "request_id": request_id,
        "request_type": request_type,
        "valid": validation["valid"] and allowlist_result["allowed"],
        "plan_ref": validation["cmd"],
        "checks": validation["checks"],
        "errors": validation["errors"],
        "allowlist_version": allowlist_result.get("version"),
        "allowlist_violations": allowlist_result.get("violations", []),
        "decision": decision
    }
    filepath = DRYRUN_DIR / f"{request_id}.json"
    filepath.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(filepath.relative_to(BASE_DIR))


def save_shadow_artifact(request_id: str, request_type: str, validation: dict, allowlist_result: dict) -> str:
    """Save Shadow Run artifact with allowlist enforcement"""
    SHADOW_DIR.mkdir(parents=True, exist_ok=True)
    
    filepath = SHADOW_DIR / f"{request_id}.json"
    if filepath.exists():
        logger.warning(f"Shadow artifact already exists")
        return str(filepath.relative_to(BASE_DIR))
    
    expected = EXPECTED_OUTPUTS.get(request_type, [])
    
    # Decision based on both validation AND allowlist
    if validation["valid"] and allowlist_result["allowed"]:
        decision = "SHADOW_OK"
        reason = "All checks passed and allowlist validated. Ready for real execution."
    else:
        decision = "SHADOW_BLOCKED"
        all_issues = validation["errors"] + allowlist_result.get("violations", [])
        reason = f"Blocked by: {all_issues}"
    
    artifact = {
        "schema": "SHADOW_RUN_V1",
        "request_id": request_id,
        "shadowed_at": datetime.now().isoformat(),
        "request_type": request_type,
        "would_run_command": validation["cmd"],
        "inputs_checked": validation["checks"],
        "expected_outputs": expected,
        "allowlist_version": allowlist_result.get("version"),
        "allowlist_violations": allowlist_result.get("violations", []),
        "decision": decision,
        "reason": reason
    }
    
    filepath.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Shadow artifact saved: {decision}")
    return str(filepath.relative_to(BASE_DIR))


def process_ticket(ticket: dict, mode: str) -> bool:
    request_id = ticket.get("request_id")
    request_type = ticket.get("request_type", "UNKNOWN")
    
    logger.info(f"Processing: {request_id} ({request_type}) [Mode: {mode}]")
    
    if not consume_ticket(request_id):
        return False
    
    plans = load_execution_plan()
    validation = deep_validate(request_id, request_type, plans)
    expected_outputs = EXPECTED_OUTPUTS.get(request_type, [])
    allowlist_result = validate_against_allowlist(request_type, validation["cmd"], expected_outputs)
    
    if mode == "MOCK_ONLY":
        logger.info(f"[MOCK_ONLY] Simulating...")
        time.sleep(1)
        message = f"SUCCESS [MOCK_ONLY]: Simulated for {request_type}"
        write_receipt(request_id, mode, "DONE", message)
        return complete_ticket(request_id, "DONE", message)
    
    elif mode == "DRY_RUN":
        logger.info(f"[DRY_RUN] Validating with allowlist...")
        artifact_path = save_dryrun_artifact(request_id, request_type, validation, allowlist_result)
        
        if validation["valid"] and allowlist_result["allowed"]:
            message = f"SUCCESS [DRY_RUN]: Validation passed. Decision: SHADOW_OK"
            write_receipt(request_id, mode, "DONE", message, [artifact_path])
            return complete_ticket(request_id, "DONE", message, [artifact_path])
        else:
            blocked_by = "EXECUTION_ALLOWLIST_V1" if not allowlist_result["allowed"] else "VALIDATION"
            message = f"FAILED [DRY_RUN]: Decision: SHADOW_BLOCKED. BlockedBy: {blocked_by}"
            write_receipt(request_id, mode, "FAILED", message, [artifact_path])
            return complete_ticket(request_id, "FAILED", message, [artifact_path])
    
    elif mode == "REAL_ENABLED":
        logger.info(f"[SHADOW] Real execution simulated with allowlist check...")
        shadow_path = save_shadow_artifact(request_id, request_type, validation, allowlist_result)
        
        if validation["valid"] and allowlist_result["allowed"]:
            message = f"SUCCESS [SHADOW]: Decision: SHADOW_OK. Allowlist v{allowlist_result['version']}"
            write_receipt(request_id, "REAL_ENABLED", "DONE", message, [shadow_path])
            return complete_ticket(request_id, "DONE", message, [shadow_path])
        else:
            blocked_by = "EXECUTION_ALLOWLIST_V1" if not allowlist_result["allowed"] else "VALIDATION"
            message = f"FAILED [SHADOW]: Decision: SHADOW_BLOCKED. BlockedBy: {blocked_by}"
            write_receipt(request_id, "REAL_ENABLED", "FAILED", message, [shadow_path])
            return complete_ticket(request_id, "FAILED", message, [shadow_path])
    
    else:
        message = f"SUCCESS [UNKNOWN]: Processed"
        write_receipt(request_id, mode, "DONE", message)
        return complete_ticket(request_id, "DONE", message)


def run_worker():
    logger.info("=" * 50)
    logger.info("Ticket Worker Starting (C-P.8)...")
    
    stop_status = check_emergency_stop()
    if stop_status.get("enabled"):
        logger.warning(f"Emergency Stop ACTIVE")
        logger.info("=" * 50)
        return True
    
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
