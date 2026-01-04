"""
Ops Cycle Runner (C-P.15)
운영 관측 루프 1회 실행

주의: 티켓 워커를 자동 실행하지 않음 (운영 관측만)
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
OPS_DIR = BASE_DIR / "reports" / "ops" / "daily"
SNAPSHOTS_DIR = OPS_DIR / "snapshots"
LOCK_FILE = STATE_DIR / "ops_runner.lock"
EMERGENCY_STOP_FILE = STATE_DIR / "emergency_stop.json"

API_BASE = "http://127.0.0.1:8000"
LOCK_TIMEOUT_SECONDS = 60  # 중복 실행 방지 시간

logging.basicConfig(level=logging.INFO, format="[OPS_RUNNER] %(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def check_emergency_stop() -> bool:
    """비상 정지 상태 확인"""
    if not EMERGENCY_STOP_FILE.exists():
        return False
    try:
        data = json.loads(EMERGENCY_STOP_FILE.read_text(encoding="utf-8"))
        return data.get("active", False)
    except Exception:
        return False


def acquire_lock() -> tuple[bool, str]:
    """Lock 확보 (중복 실행 방지)"""
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


def save_snapshot(run_id: str, status: str, reason: str, ops_summary: dict, tickets_summary: dict, push_summary: dict, started_at: str) -> str:
    """스냅샷 저장"""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = SNAPSHOTS_DIR / f"ops_run_{timestamp}.json"
    
    snapshot = {
        "schema": "OPS_RUN_SNAPSHOT_V1",
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(),
        "status": status,
        "reason": reason,
        "ops_summary": ops_summary,
        "tickets_summary": tickets_summary,
        "push_summary": push_summary
    }
    
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Snapshot saved: {snapshot_path}")
    return str(snapshot_path.relative_to(BASE_DIR))


def run_ops_cycle() -> dict:
    """운영 관측 루프 1회 실행"""
    started_at = datetime.now().isoformat()
    run_id = None
    
    # Step 1: Emergency Stop 확인
    if check_emergency_stop():
        logger.warning("Emergency Stop is ACTIVE. Aborting.")
        snapshot_path = save_snapshot(
            run_id="N/A",
            status="STOPPED",
            reason="EMERGENCY_STOP_ACTIVE",
            ops_summary={},
            tickets_summary={},
            push_summary={},
            started_at=started_at
        )
        return {
            "result": "STOPPED",
            "status": "STOPPED",
            "reason": "EMERGENCY_STOP_ACTIVE",
            "snapshot_path": snapshot_path
        }
    
    # Step 2: Lock 확보
    locked, lock_result = acquire_lock()
    if not locked:
        logger.warning(f"Lock failed: {lock_result}")
        snapshot_path = save_snapshot(
            run_id="N/A",
            status="SKIPPED",
            reason=f"LOCK_FAILED: {lock_result}",
            ops_summary={},
            tickets_summary={},
            push_summary={},
            started_at=started_at
        )
        return {
            "result": "SKIPPED",
            "status": "SKIPPED",
            "reason": lock_result,
            "snapshot_path": snapshot_path
        }
    
    run_id = lock_result
    logger.info(f"Lock acquired. run_id={run_id}")
    
    try:
        # Step 3: Ops Report regenerate
        ops_summary = {}
        try:
            resp = requests.post(f"{API_BASE}/api/ops/daily/regenerate", timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                report = data.get("report", {})
                ops_summary = report.get("summary", {})
                logger.info(f"Ops report regenerated: {ops_summary}")
            else:
                logger.error(f"Ops regenerate failed: {resp.status_code}")
        except Exception as e:
            logger.error(f"Ops regenerate error: {e}")
        
        # Step 4: Tickets 최신 상태 조회
        tickets_summary = {"total": 0, "open": 0, "done": 0}
        try:
            resp = requests.get(f"{API_BASE}/api/tickets/latest", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                rows = data.get("rows", [])
                tickets_summary["total"] = len(rows)
                tickets_summary["open"] = len([r for r in rows if r.get("current_status") == "OPEN"])
                tickets_summary["done"] = len([r for r in rows if r.get("current_status") == "DONE"])
                logger.info(f"Tickets summary: {tickets_summary}")
        except Exception as e:
            logger.error(f"Tickets fetch error: {e}")
        
        # Step 5: Push 최신 조회
        push_summary = {"last_push_at": None, "count": 0}
        try:
            resp = requests.get(f"{API_BASE}/api/push/latest", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                rows = data.get("rows", [])
                push_summary["count"] = len(rows)
                if rows:
                    push_summary["last_push_at"] = rows[-1].get("generated_at")
                logger.info(f"Push summary: {push_summary}")
        except Exception as e:
            logger.error(f"Push fetch error: {e}")
        
        # Step 6: Snapshot 기록
        snapshot_path = save_snapshot(
            run_id=run_id,
            status="DONE",
            reason="CYCLE_COMPLETE",
            ops_summary=ops_summary,
            tickets_summary=tickets_summary,
            push_summary=push_summary,
            started_at=started_at
        )
        
        return {
            "result": "OK",
            "status": "DONE",
            "reason": "CYCLE_COMPLETE",
            "run_id": run_id,
            "snapshot_path": snapshot_path,
            "ops_summary": ops_summary,
            "tickets_summary": tickets_summary,
            "push_summary": push_summary
        }
        
    except Exception as e:
        logger.error(f"Cycle failed: {e}")
        snapshot_path = save_snapshot(
            run_id=run_id or "N/A",
            status="FAILED",
            reason=str(e),
            ops_summary={},
            tickets_summary={},
            push_summary={},
            started_at=started_at
        )
        return {
            "result": "FAILED",
            "status": "FAILED",
            "reason": str(e),
            "snapshot_path": snapshot_path
        }
    
    finally:
        release_lock()
        logger.info("Lock released.")


if __name__ == "__main__":
    result = run_ops_cycle()
    print(json.dumps(result, ensure_ascii=False, indent=2))
