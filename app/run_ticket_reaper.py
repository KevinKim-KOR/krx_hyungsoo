"""
Ticket Reaper (C-P.43)

Stale IN_PROGRESS 티켓 자동 정리
- 임계치(기본 24시간) 초과한 IN_PROGRESS 티켓을 FAILED로 종료
- Ops Cycle Step 0.25로 연동
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

BASE_DIR = Path(__file__).parent.parent
TICKETS_DIR = BASE_DIR / "state" / "tickets"
TICKET_REQUESTS_FILE = TICKETS_DIR / "ticket_requests.jsonl"
TICKET_RESULTS_FILE = TICKETS_DIR / "ticket_results.jsonl"

REAPER_DIR = BASE_DIR / "reports" / "ops" / "tickets" / "reaper"
REAPER_LATEST_DIR = REAPER_DIR / "latest"
REAPER_SNAPSHOTS_DIR = REAPER_DIR / "snapshots"
REAPER_LATEST = REAPER_LATEST_DIR / "reaper_latest.json"

DEFAULT_THRESHOLD_SECONDS = 86400  # 24시간
DEFAULT_MAX_CLEAN = 50


def read_jsonl(path: Path) -> List[Dict]:
    """JSONL 파일 읽기"""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    return [json.loads(line) for line in lines if line.strip()]


def get_ticket_board() -> Dict[str, Dict]:
    """
    모든 티켓의 현재 상태 계산 (State Machine)
    Returns: {request_id: {request_type, current_status, last_processed_at, ...}}
    """
    requests = read_jsonl(TICKET_REQUESTS_FILE)
    results = read_jsonl(TICKET_RESULTS_FILE)
    
    board = {}
    for req in requests:
        request_id = req.get("request_id")
        if not request_id:
            continue
        
        # 해당 티켓의 결과들 수집
        req_results = [r for r in results if r.get("request_id") == request_id]
        
        if not req_results:
            status = "OPEN"
            last_processed_at = req.get("requested_at")
        else:
            # 최신 결과
            latest = max(req_results, key=lambda x: x.get("processed_at", ""))
            status = latest.get("status", "OPEN")
            last_processed_at = latest.get("processed_at")
        
        board[request_id] = {
            "request_id": request_id,
            "request_type": req.get("request_type", "UNKNOWN"),
            "current_status": status,
            "last_processed_at": last_processed_at,
            "requested_at": req.get("requested_at")
        }
    
    return board


def find_stale_in_progress(threshold_seconds: int = DEFAULT_THRESHOLD_SECONDS) -> List[Dict]:
    """
    Stale IN_PROGRESS 티켓 찾기
    """
    board = get_ticket_board()
    now = datetime.now()
    threshold = timedelta(seconds=threshold_seconds)
    
    stale = []
    for request_id, ticket in board.items():
        if ticket["current_status"] != "IN_PROGRESS":
            continue
        
        last_processed = ticket.get("last_processed_at")
        if not last_processed:
            continue
        
        try:
            # ISO datetime 파싱
            if "T" in last_processed:
                dt = datetime.fromisoformat(last_processed.replace("Z", "+00:00"))
                # timezone 제거 (naive 비교)
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)
            else:
                dt = datetime.strptime(last_processed, "%Y-%m-%d %H:%M:%S")
            
            age = now - dt
            if age > threshold:
                stale.append({
                    **ticket,
                    "age_seconds": int(age.total_seconds())
                })
        except Exception:
            continue
    
    return stale


def append_ticket_result(result: Dict):
    """결과 Append (Append-only)"""
    TICKETS_DIR.mkdir(parents=True, exist_ok=True)
    with open(TICKET_RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")


def clean_stale_tickets(
    threshold_seconds: int = DEFAULT_THRESHOLD_SECONDS,
    max_clean: int = DEFAULT_MAX_CLEAN
) -> Dict[str, Any]:
    """
    Stale IN_PROGRESS 티켓 정리
    """
    asof = datetime.now().isoformat()
    stale = find_stale_in_progress(threshold_seconds)
    
    cleaned_items = []
    for i, ticket in enumerate(stale[:max_clean]):
        request_id = ticket["request_id"]
        
        # FAILED 상태로 전이
        result = {
            "request_id": request_id,
            "processor_id": "TICKET_REAPER",
            "status": "FAILED",
            "processed_at": asof,
            "message": f"AUTO_CLEANUP_STALE_IN_PROGRESS: exceeded {threshold_seconds}s threshold (age: {ticket.get('age_seconds', 0)}s)"
        }
        append_ticket_result(result)
        
        cleaned_items.append({
            "request_id": request_id,
            "request_type": ticket.get("request_type", "UNKNOWN"),
            "last_processed_at": ticket.get("last_processed_at"),
            "reason": "AUTO_CLEANUP_STALE_IN_PROGRESS"
        })
    
    decision = "CLEANED" if cleaned_items else "NONE"
    
    return {
        "schema": "TICKET_REAPER_REPORT_V1",
        "asof": asof,
        "decision": decision,
        "threshold_seconds": threshold_seconds,
        "stale_count": len(stale),
        "cleaned_count": len(cleaned_items),
        "cleaned_items": cleaned_items
    }


def run_ticket_reaper(
    threshold_seconds: int = DEFAULT_THRESHOLD_SECONDS,
    max_clean: int = DEFAULT_MAX_CLEAN
) -> Dict[str, Any]:
    """
    Ticket Reaper 실행 및 리포트 저장
    """
    report = clean_stale_tickets(threshold_seconds, max_clean)
    
    # 디렉토리 생성
    REAPER_LATEST_DIR.mkdir(parents=True, exist_ok=True)
    REAPER_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 스냅샷 경로
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = REAPER_SNAPSHOTS_DIR / f"reaper_{timestamp}.json"
    
    # evidence_refs 추가
    report["evidence_refs"] = [
        str(snapshot_path.relative_to(BASE_DIR)).replace("\\", "/")
    ]
    
    # Atomic write - snapshot
    tmp_snapshot = snapshot_path.with_suffix(".json.tmp")
    tmp_snapshot.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(str(tmp_snapshot), str(snapshot_path))
    
    # Atomic write - latest
    tmp_latest = REAPER_LATEST.with_suffix(".json.tmp")
    tmp_latest.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(str(tmp_latest), str(REAPER_LATEST))
    
    return {
        "result": "OK",
        "decision": report["decision"],
        "cleaned_count": report["cleaned_count"],
        "stale_count": report["stale_count"],
        "latest_path": str(REAPER_LATEST.relative_to(BASE_DIR)).replace("\\", "/"),
        "snapshot_path": str(snapshot_path.relative_to(BASE_DIR)).replace("\\", "/")
    }


if __name__ == "__main__":
    result = run_ticket_reaper()
    print(json.dumps(result, indent=2, ensure_ascii=False))
