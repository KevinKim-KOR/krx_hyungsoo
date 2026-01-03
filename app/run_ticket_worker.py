# -*- coding: utf-8 -*-
"""
app/run_ticket_worker.py
Ticket Worker (Phase C-P.4)

규칙:
- No Execution: 실제 엔진 실행 금지
- Gate Priority: 티켓 처리 전 반드시 Gate 상태 확인
- Idempotency: consume 409 시 SKIP_AND_CONTINUE
"""
import json
import os
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta
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
        
        # 해당 request_id의 결과들
        req_results = [r for r in results if r.get("request_id") == rid]
        
        if req_results:
            # 최신 상태
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
                # Stale lock - Force acquire
                logger.warning(f"Stale lock detected (age: {age_seconds:.0f}s > {STALE_THRESHOLD_SECONDS}s). Force acquiring...")
        except Exception as e:
            logger.warning(f"Invalid lock file, overwriting: {e}")
    
    # Acquire lock
    lock_data = {
        "pid": os.getpid(),
        "acquired_at": datetime.now().isoformat()
    }
    LOCK_FILE.write_text(json.dumps(lock_data, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Lock acquired (PID: {os.getpid()})")
    return True


def release_lock():
    """Lock 해제"""
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()
        logger.info("Lock released")


def get_gate_mode() -> str:
    """Gate 모드 조회 (API 우선, 실패 시 MOCK_ONLY)"""
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


def consume_ticket(request_id: str) -> bool:
    """티켓 소비 (OPEN → IN_PROGRESS) - Idempotency: 409면 SKIP"""
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


def complete_ticket(request_id: str, request_type: str, mode: str) -> bool:
    """티켓 완료 - Gate 모드에 따른 메시지 태그"""
    try:
        if mode == "MOCK_ONLY":
            message = f"SUCCESS [MOCK_ONLY]: Simulated execution for {request_type}"
        elif mode == "DRY_RUN":
            message = f"SUCCESS [DRY_RUN]: Payload validated for {request_type}"
        elif mode == "REAL_ENABLED":
            # C-P.4에서는 도달 불가, 만약 도달 시 BLOCKED 처리
            message = f"FAILED [BLOCKED]: REAL_ENABLED mode is not allowed in C-P.4"
            status = "FAILED"
        else:
            message = f"SUCCESS [UNKNOWN_MODE]: Processed {request_type}"
        
        # REAL_ENABLED인 경우 FAILED 처리
        if mode == "REAL_ENABLED":
            status = "FAILED"
        else:
            status = "DONE"
        
        resp = requests.post(
            f"{API_BASE}/api/tickets/complete",
            json={
                "request_id": request_id,
                "status": status,
                "message": message,
                "processor_id": f"worker_{os.getpid()}"
            }
        )
        
        if resp.status_code == 200:
            logger.info(f"Completed ticket: {request_id} - {message}")
            return True
        elif resp.status_code == 409:
            logger.warning(f"Complete conflict (status mismatch): {request_id}")
            return False
        else:
            logger.error(f"Complete failed ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Complete request failed: {e}")
        return False


def process_ticket(ticket: dict, mode: str) -> bool:
    """단일 티켓 처리 - Gate 모드에 따른 동작"""
    request_id = ticket.get("request_id")
    request_type = ticket.get("request_type", "UNKNOWN")
    payload = ticket.get("payload", {})
    
    logger.info(f"Processing ticket: {request_id} ({request_type}) [Mode: {mode}]")
    
    # Step A: Consume (Idempotency - 409면 SKIP)
    if not consume_ticket(request_id):
        return False  # 409 or error - SKIP_AND_CONTINUE
    
    # Step B: Execute based on Gate Mode
    if mode == "MOCK_ONLY":
        logger.info(f"[MOCK_ONLY] Simulating execution... (sleep 1s)")
        time.sleep(1)
    elif mode == "DRY_RUN":
        logger.info(f"[DRY_RUN] Validating payload...")
        # Payload 검증 (실행 X)
        if request_type == "REQUEST_RECONCILE":
            required = ["mode", "reason"]
        elif request_type == "REQUEST_REPORTS":
            required = ["mode", "scope", "reason"]
        else:
            required = []
        
        missing = [k for k in required if k not in payload]
        if missing:
            logger.warning(f"[DRY_RUN] Missing payload keys: {missing}")
        else:
            logger.info(f"[DRY_RUN] Payload validation PASSED")
        time.sleep(0.5)  # 짧은 대기
    elif mode == "REAL_ENABLED":
        logger.error(f"[BLOCKED] REAL_ENABLED mode is not allowed in C-P.4!")
        # FAILED 상태로 완료 처리
    
    # Step C: Complete with mode-specific tag
    return complete_ticket(request_id, request_type, mode)


def run_worker():
    """워커 메인 실행"""
    logger.info("=" * 50)
    logger.info("Ticket Worker Starting (C-P.4)...")
    
    # 0. Gate Check (매 실행 전 확인)
    mode = get_gate_mode()
    logger.info(f"Execution Gate Mode: {mode}")
    
    # 1. Acquire Lock
    if not acquire_lock():
        logger.error("Failed to acquire lock. Another worker may be running.")
        return False
    
    try:
        # 2. Scan OPEN tickets  
        open_tickets = get_open_tickets()
        logger.info(f"Found {len(open_tickets)} OPEN ticket(s)")
        
        if not open_tickets:
            logger.info("No OPEN tickets to process.")
            return True
        
        # 3. Process one ticket (1회 실행 후 종료 정책)
        ticket = open_tickets[0]
        success = process_ticket(ticket, mode)
        
        if success:
            logger.info("Ticket processed successfully!")
        else:
            logger.warning("Ticket processing failed or skipped.")
        
        return success
        
    finally:
        # 4. Release Lock (finally 보장)
        release_lock()
        logger.info("Worker finished.")
        logger.info("=" * 50)


if __name__ == "__main__":
    run_worker()
