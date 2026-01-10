# -*- coding: utf-8 -*-
"""
app/run_ticket_worker.py
Ticket Worker (Phase C-P.10.1)

규칙:
- Receipt V3: sha256 기반 verified 완료 판정
- 스냅샷 순서: before(직전) → REAL → after(직후)
"""
import json
import os
import time
import requests
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
RECEIPTS_FILE = TICKETS_DIR / "ticket_receipts.jsonl"
EXECUTION_PLAN_FILE = BASE_DIR / "docs" / "contracts" / "execution_plan_v1.json"
ALLOWLIST_FILE = BASE_DIR / "docs" / "contracts" / "execution_allowlist_v1.json"
WINDOWS_FILE = STATE_DIR / "real_enable_windows" / "real_enable_windows.jsonl"
PREFLIGHT_DIR = BASE_DIR / "reports" / "tickets" / "preflight"

API_BASE = "http://127.0.0.1:8000"
STALE_THRESHOLD_SECONDS = 600

# Receipt V3: 고정된 4개 타겟 (순서 고정)
PROOF_TARGETS = [
    "reports/phase_c/latest/recon_summary.json",
    "reports/phase_c/latest/recon_daily.jsonl",
    "reports/phase_c/latest/report_human.json",
    "reports/phase_c/latest/report_ai.json"
]

# Ops Report (C-P.13)
OPS_REPORT_DIR = BASE_DIR / "reports" / "ops" / "daily"
OPS_REPORT_LATEST = OPS_REPORT_DIR / "ops_report_latest.json"
OPS_SNAPSHOTS_DIR = OPS_REPORT_DIR / "snapshots"


def update_ops_report():
    """Update daily ops report after ticket processing"""
    try:
        resp = requests.post(f"{API_BASE}/api/ops/daily/regenerate", timeout=10)
        if resp.status_code == 200:
            logger.info("[OPS] Daily ops report updated")
        else:
            logger.warning(f"[OPS] Failed to update ops report: {resp.status_code}")
    except Exception as e:
        logger.error(f"[OPS] Error updating ops report: {e}")


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


# === Snapshot Function (Receipt V3) ===

def snapshot_file(path: Path) -> dict:
    """파일 스냅샷: sha256 + size_bytes + mtime_iso"""
    if not path.exists():
        return {"exists": False, "mtime_iso": None, "size_bytes": None, "sha256": None}
    
    try:
        stat = path.stat()
        mtime_iso = datetime.fromtimestamp(stat.st_mtime).isoformat()
        size_bytes = stat.st_size
        
        # SHA256 계산 (스트리밍)
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        
        return {
            "exists": True,
            "mtime_iso": mtime_iso,
            "size_bytes": size_bytes,
            "sha256": sha256_hash.hexdigest()
        }
    except Exception as e:
        logger.error(f"Snapshot error for {path}: {e}")
        return {"exists": False, "mtime_iso": None, "size_bytes": None, "sha256": None}


def compute_target_proof(path: str, before: dict, after: dict) -> dict:
    """단일 타겟의 changed/verified 계산"""
    # changed: 3종 세트 중 하나라도 다르면 true
    changed = (
        before.get("mtime_iso") != after.get("mtime_iso") or
        before.get("size_bytes") != after.get("size_bytes") or
        before.get("sha256") != after.get("sha256")
    )
    
    # verified 계산 (Contract 규칙)
    if not after.get("exists") or after.get("sha256") is None:
        verified = False
    elif changed:
        verified = True  # 실행으로 산출물 갱신이 증명됨
    else:
        # changed == false: 동일 해시로 재검증
        verified = (before.get("sha256") == after.get("sha256") and before.get("sha256") is not None)
    
    return {
        "path": path,
        "before": before,
        "after": after,
        "changed": changed,
        "verified": verified
    }


def compute_acceptance(exit_code: int, targets: list) -> dict:
    """acceptance 계산"""
    all_verified = all(t.get("verified", False) for t in targets)
    any_changed = any(t.get("changed", False) for t in targets)
    
    if exit_code != 0:
        return {"pass": False, "reason": "FAILED_EXIT_CODE"}
    
    if not all_verified:
        return {"pass": False, "reason": "MISSING_OUTPUTS"}
    
    if any_changed:
        return {"pass": True, "reason": "CHANGED_VERIFIED"}
    else:
        return {"pass": True, "reason": "UNCHANGED_BUT_HASH_MATCH_VERIFIED"}


# === Safety Checks ===

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


def run_preflight(request_id: str, request_type: str) -> dict:
    try:
        resp = requests.post(
            f"{API_BASE}/api/deps/reconcile/check",
            json={"request_id": request_id, "request_type": request_type, "payload": {}},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"Preflight API failed: {e}")
    return {"result": "FAIL", "decision": "PREFLIGHT_FAIL", "artifact_path": None}


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


def write_receipt_v3(
    request_id: str, request_type: str, mode: str, decision: str,
    exit_code: int, outputs_proof: dict, acceptance: dict,
    safety_checks: dict, preflight_artifact_path: str = None
):
    """Write EXECUTION_RECEIPT_V3"""
    TICKETS_DIR.mkdir(parents=True, exist_ok=True)
    
    # C-P.32.1: Evidence refs
    try:
        from app.utils.evidence_refs import build_execution_receipt_refs
        evidence_refs = build_execution_receipt_refs()
    except Exception:
        evidence_refs = []
    
    receipt = {
        "schema": "EXECUTION_RECEIPT_V3",
        "asof": datetime.now().isoformat(),
        "receipt_id": str(uuid.uuid4()),
        "request_id": request_id,
        "request_type": request_type,
        "mode": mode,
        "decision": decision,
        "exit_code": exit_code,
        "outputs_proof": outputs_proof,
        "acceptance": acceptance,
        "safety_checks": safety_checks,
        "preflight_artifact_path": preflight_artifact_path,
        "evidence_refs": evidence_refs
    }
    
    with open(RECEIPTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    
    logger.info(f"Receipt V3 written: {decision}, acceptance.pass={acceptance.get('pass')}")
    return receipt


def process_ticket_real(ticket: dict, plans: dict, window_info: dict, safety_checks: dict, preflight_path: str) -> bool:
    """Process ticket with REAL execution (Receipt V3)"""
    request_id = ticket.get("request_id")
    request_type = ticket.get("request_type")
    
    plan = plans.get(request_type, {})
    cmd = plan.get("cmd", [])
    
    # === STEP 1: BEFORE 스냅샷 (REAL 직전) ===
    logger.info("[V3] Taking BEFORE snapshots...")
    before_snapshots = {}
    for target in PROOF_TARGETS:
        path = BASE_DIR / target
        before_snapshots[target] = snapshot_file(path)
    
    # === STEP 2: REAL 실행 ===
    logger.info(f"[REAL] Executing: {cmd}")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=300
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
    
    # === STEP 3: AFTER 스냅샷 (REAL 직후) ===
    logger.info("[V3] Taking AFTER snapshots...")
    after_snapshots = {}
    for target in PROOF_TARGETS:
        path = BASE_DIR / target
        after_snapshots[target] = snapshot_file(path)
    
    # === STEP 4: changed/verified/acceptance 계산 ===
    targets = []
    for target in PROOF_TARGETS:
        proof = compute_target_proof(target, before_snapshots[target], after_snapshots[target])
        targets.append(proof)
    
    outputs_proof = {
        "latest_dir": "reports/phase_c/latest/",
        "targets": targets
    }
    
    acceptance = compute_acceptance(exit_code, targets)
    
    # Consume window immediately
    if window_info.get("window_id"):
        consume_window(window_info["window_id"])
    
    # Decision
    decision = "EXECUTED" if exit_code == 0 else "FAILED"
    
    # Write Receipt V3
    write_receipt_v3(
        request_id=request_id,
        request_type=request_type,
        mode="REAL",
        decision=decision,
        exit_code=exit_code,
        outputs_proof=outputs_proof,
        acceptance=acceptance,
        safety_checks=safety_checks,
        preflight_artifact_path=preflight_path
    )
    
    status = "DONE" if acceptance.get("pass") else "FAILED"
    message = f"[REAL] {decision}: exit_code={exit_code}, acceptance.pass={acceptance.get('pass')}"
    artifacts = [t["path"] for t in targets if t["after"]["exists"]]
    return complete_ticket(request_id, status, message, artifacts)


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
    
    block_reasons = []
    preflight_path = None
    
    # === PREFLIGHT CHECKS ===
    estop = check_emergency_stop()
    if not estop["passed"]:
        block_reasons.append("Emergency Stop is ON")
    
    approval = check_approval()
    if not approval["passed"]:
        block_reasons.append(f"Approval not APPROVED (status: {approval['status']})")
    
    allowlist_check = validate_allowlist(request_type, cmd)
    if not allowlist_check["passed"]:
        block_reasons.extend(allowlist_check["violations"])
    
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
        outputs_proof = {"latest_dir": "reports/phase_c/latest/", "targets": []}
        acceptance = {"pass": True, "reason": "MOCK_MODE"}
        write_receipt_v3(request_id, request_type, "MOCK_ONLY", "EXECUTED", 0, outputs_proof, acceptance, safety_checks)
        return complete_ticket(request_id, "DONE", f"[MOCK_ONLY] Simulated {request_type}")
    
    elif mode == "DRY_RUN":
        outputs_proof = {"latest_dir": "reports/phase_c/latest/", "targets": []}
        acceptance = {"pass": True, "reason": "DRY_RUN_MODE"}
        write_receipt_v3(request_id, request_type, "DRY_RUN", "EXECUTED", 0, outputs_proof, acceptance, safety_checks)
        return complete_ticket(request_id, "DONE", f"[DRY_RUN] Validated {request_type}")
    
    elif mode == "REAL_ENABLED":
        # Safety checks first
        if block_reasons:
            logger.warning(f"[BLOCKED] {block_reasons}")
            outputs_proof = {"latest_dir": "reports/phase_c/latest/", "targets": []}
            acceptance = {"pass": False, "reason": "BLOCKED_BY_SAFETY_CHECK"}
            write_receipt_v3(request_id, request_type, "REAL", "BLOCKED", None, outputs_proof, acceptance, safety_checks)
            return complete_ticket(request_id, "FAILED", f"[BLOCKED] {block_reasons}")
        
        # Deep Preflight for RECONCILE and REPORTS (C-P.12)
        if request_type in ["REQUEST_RECONCILE", "REQUEST_REPORTS"]:
            preflight_result = run_preflight(request_id, request_type)
            preflight_path = preflight_result.get("artifact_path")
            
            if preflight_result.get("decision") != "PREFLIGHT_PASS":
                block_reasons.append(f"Preflight failed: {preflight_result.get('decision')}")
                outputs_proof = {"latest_dir": "reports/phase_c/latest/", "targets": []}
                acceptance = {"pass": False, "reason": "PREFLIGHT_FAIL"}
                write_receipt_v3(request_id, request_type, "REAL", "BLOCKED", None, outputs_proof, acceptance, safety_checks, preflight_path)
                return complete_ticket(request_id, "FAILED", f"[PREFLIGHT_FAIL] {block_reasons}")
        
        # All checks passed - REAL EXECUTE with V3 proof
        return process_ticket_real(ticket, plans, window_info, safety_checks, preflight_path)
    
    else:
        return complete_ticket(request_id, "DONE", f"[UNKNOWN] Processed")


def process_one_ticket(skip_lock: bool = False) -> dict:
    """
    Process exactly ONE open ticket (C-P.16)
    
    Returns:
        dict with keys:
        - attempted: bool (티켓 처리 시도 여부)
        - selected_request_id: str or None
        - selected_request_type: str or None
        - decision: str (PROCESSED, SKIPPED, NONE)
        - reason: str
        - receipt_ref: str or None (e.g., "state/tickets/ticket_receipts.jsonl:lineN")
    """
    result = {
        "attempted": False,
        "selected_request_id": None,
        "selected_request_type": None,
        "decision": "NONE",
        "reason": "NO_OPEN_TICKETS",
        "receipt_ref": None
    }
    
    # Get gate mode
    mode = get_gate_mode()
    
    # Acquire lock (optional)
    if not skip_lock:
        if not acquire_lock():
            result["decision"] = "SKIPPED"
            result["reason"] = "LOCK_CONFLICT_409"
            return result
    
    try:
        # Get open tickets
        open_tickets = get_open_tickets()
        
        if not open_tickets:
            result["decision"] = "NONE"
            result["reason"] = "NO_OPEN_TICKETS"
            return result
        
        # Select one ticket (oldest)
        ticket = open_tickets[0]
        result["attempted"] = True
        result["selected_request_id"] = ticket.get("request_id")
        result["selected_request_type"] = ticket.get("request_type")
        
        # Count receipts before processing
        receipts_before = len(read_jsonl(RECEIPTS_FILE))
        
        # Process the ticket
        success = process_ticket(ticket, mode)
        
        # Count receipts after processing
        receipts_after = len(read_jsonl(RECEIPTS_FILE))
        
        if success:
            result["decision"] = "PROCESSED"
            result["reason"] = "TICKET_PROCESSED_OK"
            if receipts_after > receipts_before:
                result["receipt_ref"] = f"state/tickets/ticket_receipts.jsonl:line{receipts_after}"
        else:
            result["decision"] = "SKIPPED"
            result["reason"] = "TICKET_PROCESS_FAILED"
        
        return result
        
    finally:
        if not skip_lock:
            release_lock()


def run_worker():
    logger.info("=" * 50)
    logger.info("Ticket Worker Starting (C-P.10.1 - Receipt V3)...")
    
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
        
        # Update ops report after processing (C-P.13)
        update_ops_report()
        
        return success
        
    finally:
        release_lock()
        logger.info("Worker finished.")
        logger.info("=" * 50)


if __name__ == "__main__":
    run_worker()

