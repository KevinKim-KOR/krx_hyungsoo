# -*- coding: utf-8 -*-
"""
app/run_ticket_worker.py
Ticket Worker (Phase C-P.6)

규칙:
- No Execution: 실제 엔진 실행 금지
- Receipt Logging: 모든 실행 시도를 영수증으로 기록
- Emergency Stop: 정지 상태면 SKIP
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

# 로깅 설정
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
RECEIPTS_FILE = TICKETS_DIR / "ticket_receipts.jsonl"
EXECUTION_PLAN_FILE = BASE_DIR / "docs" / "contracts" / "execution_plan_v1.json"

API_BASE = "http://127.0.0.1:8000"
STALE_THRESHOLD_SECONDS = 600  # 10분


def read_jsonl(path: Path) -> list:
    """JSONL 파일 읽기"""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    return [json.loads(line) for line in lines if line.strip()]


def get_open_tickets() -> list:
    """OPEN 상태인 티켓 목록 조회"""
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
    """Lock 획득 (Stale Lock Recovery 포함)"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    
    if LOCK_FILE.exists():
        try:
            lock_data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            acquired_at = datetime.fromisoformat(lock_data.get("acquired_at", ""))
            age_seconds = (datetime.now() - acquired_at).total_seconds()
            
            if age_seconds < STALE_THRESHOLD_SECONDS:
                logger.warning(f"Lock already held by PID {lock_data.get('pid')} (age: {age_seconds:.0f}s)")
                return False
            else:
                logger.warning(f"Stale lock detected (age: {age_seconds:.0f}s). Force acquiring...")
        except Exception as e:
            logger.warning(f"Invalid lock file, overwriting: {e}")
    
    lock_data = {"pid": os.getpid(), "acquired_at": datetime.now().isoformat()}
    LOCK_FILE.write_text(json.dumps(lock_data, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Lock acquired (PID: {os.getpid()})")
    return True


def release_lock():
    """Lock 해제"""
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()
        logger.info("Lock released")


def check_emergency_stop() -> dict:
    """Emergency Stop 상태 확인"""
    try:
        resp = requests.get(f"{API_BASE}/api/emergency_stop", timeout=5)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            return data
    except Exception as e:
        logger.warning(f"Emergency Stop API failed: {e}")
    return {"enabled": False}


def get_gate_mode() -> str:
    """Gate 모드 조회"""
    try:
        resp = requests.get(f"{API_BASE}/api/execution_gate", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            mode = data.get("data", {}).get("mode", "MOCK_ONLY")
            logger.info(f"Gate mode: {mode}")
            return mode
    except Exception as e:
        logger.warning(f"Gate API failed, using default: {e}")
    return "MOCK_ONLY"


def load_execution_plan() -> dict:
    """실행 계획 로드"""
    if not EXECUTION_PLAN_FILE.exists():
        logger.error(f"Execution plan not found: {EXECUTION_PLAN_FILE}")
        return {}
    try:
        data = json.loads(EXECUTION_PLAN_FILE.read_text(encoding="utf-8"))
        return data.get("plans", {})
    except Exception as e:
        logger.error(f"Failed to load execution plan: {e}")
        return {}


def write_receipt(request_id: str, mode: str, result: str, message: str, artifacts: list = None) -> str:
    """실행 영수증 기록 (Append-only)"""
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
    
    logger.info(f"Receipt written: {receipt['receipt_id']} ({result})")
    return receipt["receipt_id"]


def consume_ticket(request_id: str) -> bool:
    """티켓 소비 (OPEN → IN_PROGRESS)"""
    try:
        resp = requests.post(
            f"{API_BASE}/api/tickets/consume",
            json={"request_id": request_id, "processor_id": f"worker_{os.getpid()}"}
        )
        if resp.status_code == 200:
            logger.info(f"Consumed ticket: {request_id}")
            return True
        elif resp.status_code == 409:
            logger.info(f"Idempotency: Ticket already consumed (409): {request_id}")
            return False
        else:
            logger.error(f"Consume failed ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Consume request failed: {e}")
        return False


def complete_ticket(request_id: str, status: str, message: str, artifacts: list = None) -> bool:
    """티켓 완료"""
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
        if resp.status_code == 200:
            logger.info(f"Completed ticket: {request_id} - {message}")
            return True
        elif resp.status_code == 409:
            logger.warning(f"Complete conflict: {request_id}")
            return False
        else:
            logger.error(f"Complete failed ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Complete request failed: {e}")
        return False


def deep_validate_dryrun(request_id: str, request_type: str, plans: dict) -> dict:
    """Deep Validation for DRY_RUN mode"""
    checks = {}
    errors = []
    
    plan = plans.get(request_type)
    checks["plan_exists"] = plan is not None
    if not plan:
        errors.append(f"No execution plan for request_type: {request_type}")
    
    cmd = plan.get("cmd", []) if plan else []
    module_path = plan.get("module", "") if plan else ""
    
    python_path = shutil.which("python")
    checks["python_available"] = python_path is not None
    if not python_path:
        errors.append("Python interpreter not found in PATH")
    
    if module_path:
        full_module_path = BASE_DIR / module_path
        checks["module_exists"] = full_module_path.exists()
        if not full_module_path.exists():
            errors.append(f"Module not found: {module_path}")
    else:
        checks["module_exists"] = False
        if plan:
            errors.append("Module path not specified in plan")
    
    valid = all(checks.values()) and len(errors) == 0
    
    return {
        "schema": "DRYRUN_ARTIFACT_V1",
        "asof": datetime.now().isoformat(),
        "request_id": request_id,
        "request_type": request_type,
        "valid": valid,
        "plan_ref": cmd,
        "checks": checks,
        "errors": errors
    }


def save_dryrun_artifact(artifact: dict) -> str:
    """Dry-Run Artifact 저장"""
    DRYRUN_DIR.mkdir(parents=True, exist_ok=True)
    request_id = artifact.get("request_id")
    filepath = DRYRUN_DIR / f"{request_id}.json"
    filepath.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Artifact saved: {filepath}")
    return str(filepath.relative_to(BASE_DIR))


def process_ticket(ticket: dict, mode: str) -> bool:
    """단일 티켓 처리"""
    request_id = ticket.get("request_id")
    request_type = ticket.get("request_type", "UNKNOWN")
    
    logger.info(f"Processing ticket: {request_id} ({request_type}) [Mode: {mode}]")
    
    # Consume (Idempotency)
    if not consume_ticket(request_id):
        return False
    
    # Mode-based processing
    if mode == "MOCK_ONLY":
        logger.info(f"[MOCK_ONLY] Simulating execution... (sleep 1s)")
        time.sleep(1)
        message = f"SUCCESS [MOCK_ONLY]: Simulated execution for {request_type}"
        write_receipt(request_id, mode, "DONE", message)
        return complete_ticket(request_id, "DONE", message)
    
    elif mode == "DRY_RUN":
        logger.info(f"[DRY_RUN] Deep validation with execution plan...")
        plans = load_execution_plan()
        if not plans:
            message = f"FAILED [DRY_RUN]: Execution plan not available"
            write_receipt(request_id, mode, "FAILED", message)
            return complete_ticket(request_id, "FAILED", message)
        
        artifact = deep_validate_dryrun(request_id, request_type, plans)
        artifact_path = save_dryrun_artifact(artifact)
        
        if artifact["valid"]:
            logger.info(f"[DRY_RUN] Validation PASSED: {artifact['checks']}")
            message = f"SUCCESS [DRY_RUN]: Artifact saved. Plan: {artifact['plan_ref']}"
            write_receipt(request_id, mode, "DONE", message, [artifact_path])
            return complete_ticket(request_id, "DONE", message, [artifact_path])
        else:
            logger.warning(f"[DRY_RUN] Validation FAILED: {artifact['errors']}")
            message = f"FAILED [DRY_RUN]: Validation errors: {artifact['errors']}"
            write_receipt(request_id, mode, "FAILED", message, [artifact_path])
            return complete_ticket(request_id, "FAILED", message, [artifact_path])
    
    elif mode == "REAL_ENABLED":
        # BLOCKED - Real execution not allowed in C-P.6
        logger.error(f"[BLOCKED] REAL_ENABLED mode is not allowed in C-P.6!")
        message = f"FAILED [BLOCKED]: Real execution blocked in C-P.6"
        write_receipt(request_id, mode, "BLOCKED", message)
        return complete_ticket(request_id, "FAILED", message)
    
    else:
        message = f"SUCCESS [UNKNOWN_MODE]: Processed {request_type}"
        write_receipt(request_id, mode, "DONE", message)
        return complete_ticket(request_id, "DONE", message)


def run_worker():
    """워커 메인 실행"""
    logger.info("=" * 50)
    logger.info("Ticket Worker Starting (C-P.6)...")
    
    # 0. Emergency Stop Check
    stop_status = check_emergency_stop()
    if stop_status.get("enabled"):
        logger.warning(f"Emergency Stop is ACTIVE: {stop_status.get('reason')}")
        logger.info("Worker skipping all processing due to Emergency Stop.")
        logger.info("=" * 50)
        return True  # 정상 종료 (Skip)
    
    # 1. Gate Check
    mode = get_gate_mode()
    logger.info(f"Execution Gate Mode: {mode}")
    
    # 2. Acquire Lock
    if not acquire_lock():
        logger.error("Failed to acquire lock. Another worker may be running.")
        return False
    
    try:
        # 3. Scan OPEN tickets
        open_tickets = get_open_tickets()
        logger.info(f"Found {len(open_tickets)} OPEN ticket(s)")
        
        if not open_tickets:
            logger.info("No OPEN tickets to process.")
            return True
        
        # 4. Process one ticket
        ticket = open_tickets[0]
        success = process_ticket(ticket, mode)
        
        if success:
            logger.info("Ticket processed successfully!")
        else:
            logger.warning("Ticket processing failed or skipped.")
        
        return success
        
    finally:
        release_lock()
        logger.info("Worker finished.")
        logger.info("=" * 50)


if __name__ == "__main__":
    run_worker()
