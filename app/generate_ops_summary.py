"""
Ops Summary Generator (C-P.35)

Single Pane of Glass: 분산된 최신 산출물을 통합 요약
- 읽기/요약만 허용, 비즈니스 로직 실행 금지
- Atomic Write 필수
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).parent.parent

# Input paths
OPS_RUN_LATEST = BASE_DIR / "reports" / "ops" / "daily" / "snapshots"
HEALTH_LATEST = BASE_DIR / "reports" / "ops" / "evidence" / "health" / "health_latest.json"
EVIDENCE_INDEX_LATEST = BASE_DIR / "reports" / "ops" / "evidence" / "index" / "evidence_index_latest.json"
SEND_LATEST = BASE_DIR / "reports" / "ops" / "push" / "send" / "send_latest.json"
OUTBOX_LATEST = BASE_DIR / "reports" / "ops" / "push" / "outbox" / "outbox_latest.json"
EMERGENCY_STOP_FILE = BASE_DIR / "state" / "emergency_stop.json"
GATE_FILE = BASE_DIR / "state" / "execution_gate.json"
SENDER_ENABLE_FILE = BASE_DIR / "state" / "real_sender_enable.json"
TICKET_REQUESTS = BASE_DIR / "state" / "tickets" / "ticket_requests.jsonl"
TICKET_RESULTS = BASE_DIR / "state" / "tickets" / "ticket_results.jsonl"

# Output paths
SUMMARY_DIR = BASE_DIR / "reports" / "ops" / "summary"
SUMMARY_LATEST = SUMMARY_DIR / "ops_summary_latest.json"
SUMMARY_SNAPSHOTS_DIR = SUMMARY_DIR / "snapshots"

# Forbidden prefixes to strip
FORBIDDEN_PREFIXES = ["json:", "file://", "file:", "http://", "https://"]


def sanitize_evidence_ref(ref: str) -> str:
    """
    evidence_ref 정제 (C-P.35.1)
    - 접두어 제거
    - path traversal (..) 거부
    - RAW_PATH_ONLY 보장
    """
    if not ref or not isinstance(ref, str):
        return None
    
    cleaned = ref.strip()
    
    # 접두어 제거
    for prefix in FORBIDDEN_PREFIXES:
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    
    # Path traversal 거부
    if ".." in cleaned:
        return None
    
    # 빈 문자열 거부
    if not cleaned:
        return None
    
    return cleaned


def safe_load_json(path: Path) -> Optional[Dict]:
    """JSON 파일 안전 로드"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def count_jsonl_lines(path: Path) -> int:
    """JSONL 라인 수"""
    if not path.exists():
        return 0
    try:
        count = 0
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    count += 1
        return count
    except Exception:
        return 0


def get_latest_ops_run() -> Optional[Dict]:
    """최신 ops_run 스냅샷 로드"""
    if not OPS_RUN_LATEST.exists():
        return None
    try:
        snapshots = sorted(OPS_RUN_LATEST.glob("ops_run_*.json"))
        if not snapshots:
            return None
        return safe_load_json(snapshots[-1])
    except Exception:
        return None


def get_tickets_summary() -> Dict:
    """티켓 요약 계산"""
    summary = {"open": 0, "in_progress": 0, "done": 0, "failed": 0, "blocked": 0}
    
    requests = []
    if TICKET_REQUESTS.exists():
        try:
            with open(TICKET_REQUESTS, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        requests.append(json.loads(line))
        except Exception:
            pass
    
    results = []
    if TICKET_RESULTS.exists():
        try:
            with open(TICKET_RESULTS, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        results.append(json.loads(line))
        except Exception:
            pass
    
    for req in requests:
        rid = req.get("request_id")
        req_results = [r for r in results if r.get("request_id") == rid]
        if req_results:
            latest = max(req_results, key=lambda x: x.get("processed_at", ""))
            status = latest.get("status", "OPEN")
        else:
            status = "OPEN"
        
        if status == "OPEN":
            summary["open"] += 1
        elif status == "IN_PROGRESS":
            summary["in_progress"] += 1
        elif status == "DONE":
            summary["done"] += 1
        elif status == "FAILED":
            summary["failed"] += 1
        elif status == "BLOCKED":
            summary["blocked"] += 1
    
    return summary


def generate_ops_summary() -> Dict[str, Any]:
    """Ops Summary 생성"""
    now = datetime.now()
    asof = now.isoformat()
    
    # === Guard ===
    emergency_stop = safe_load_json(EMERGENCY_STOP_FILE) or {}
    emergency_enabled = emergency_stop.get("enabled", emergency_stop.get("active", False))
    
    gate = safe_load_json(GATE_FILE) or {}
    gate_mode = gate.get("mode", "MOCK_ONLY")
    
    health = safe_load_json(HEALTH_LATEST) or {}
    health_summary = health.get("summary", {})
    health_decision = health_summary.get("decision", "UNKNOWN")
    
    # === Last Run Triplet ===
    ops_run = get_latest_ops_run()
    last_run_triplet = {"last_done": None, "last_failed": None, "last_blocked": None}
    
    if ops_run:
        status = ops_run.get("overall_status", "")
        run_time = ops_run.get("asof")
        if status == "DONE":
            last_run_triplet["last_done"] = run_time
        elif status == "FAILED":
            last_run_triplet["last_failed"] = run_time
        elif status in ("BLOCKED", "STOPPED"):
            last_run_triplet["last_blocked"] = run_time
    
    # === Tickets ===
    tickets = get_tickets_summary()
    
    # === Push ===
    outbox = safe_load_json(OUTBOX_LATEST) or {}
    outbox_rows = outbox.get("messages", [])
    outbox_row_count = len(outbox_rows) if isinstance(outbox_rows, list) else 0
    
    send = safe_load_json(SEND_LATEST) or {}
    last_send_decision = send.get("decision", "N/A")
    
    sender = safe_load_json(SENDER_ENABLE_FILE) or {}
    sender_enabled = sender.get("enabled", False)
    
    # === Evidence ===
    evidence_index = safe_load_json(EVIDENCE_INDEX_LATEST) or {}
    evidence_entries = evidence_index.get("entries", [])
    index_row_count = len(evidence_entries) if isinstance(evidence_entries, list) else 0
    
    # === Overall Status ===
    if emergency_enabled:
        overall_status = "STOPPED"
    elif health_decision == "FAIL":
        overall_status = "BLOCKED"
    elif health_decision == "WARN":
        overall_status = "WARN"
    elif ops_run is None:
        overall_status = "NO_RUN_HISTORY"
    else:
        overall_status = "OK"
    
    # === Top Risks ===
    top_risks = []
    
    if emergency_enabled:
        top_risks.append({
            "code": "EMERGENCY_STOP",
            "severity": "CRITICAL",
            "message": "Emergency stop is active",
            "evidence_refs": ["state/emergency_stop.json"]
        })
    
    if health_decision == "FAIL":
        top_risks.append({
            "code": "EVIDENCE_HEALTH_FAIL",
            "severity": "CRITICAL",
            "message": "Evidence health check failed",
            "evidence_refs": ["reports/ops/evidence/health/health_latest.json"]
        })
    elif health_decision == "WARN":
        top_risks.append({
            "code": "EVIDENCE_HEALTH_WARN",
            "severity": "WARN",
            "message": "Evidence health check has warnings",
            "evidence_refs": ["reports/ops/evidence/health/health_latest.json"]
        })
    
    if tickets["failed"] > 0:
        top_risks.append({
            "code": "TICKETS_FAILED",
            "severity": "WARN",
            "message": f"{tickets['failed']} ticket(s) failed",
            "evidence_refs": ["state/tickets/ticket_results.jsonl"]
        })
    
    if tickets["blocked"] > 0:
        top_risks.append({
            "code": "TICKETS_BLOCKED",
            "severity": "WARN",
            "message": f"{tickets['blocked']} ticket(s) blocked",
            "evidence_refs": ["state/tickets/ticket_receipts.jsonl"]
        })
    
    # === Build Summary ===
    summary = {
        "schema": "OPS_SUMMARY_V1",
        "asof": asof,
        "overall_status": overall_status,
        "guard": {
            "evidence_health": {
                "decision": health_decision,
                "fail_closed_triggered": health.get("fail_closed_triggered", False),
                "snapshot_ref": None
            },
            "emergency_stop": {"enabled": emergency_enabled},
            "execution_gate": {"mode": gate_mode}
        },
        "last_run_triplet": last_run_triplet,
        "tickets": tickets,
        "push": {
            "outbox_row_count": outbox_row_count,
            "last_send_decision": last_send_decision,
            "sender_enabled": sender_enabled
        },
        "evidence": {
            "index_row_count": index_row_count,
            "health_decision": health_decision
        },
        "top_risks": top_risks[:5]
    }
    
    return summary


def generate_ops_summary_from_receipt(run_receipt: Dict) -> Dict:
    """
    Ops Summary 생성 (In-Memory Pattern, C-P.36)
    
    순환 의존성 제거: run_receipt를 직접 받아서 Summary 생성
    저장된 ops_run_latest.json을 읽지 않음
    """
    now = datetime.now()
    asof = now.isoformat()
    
    # === Guard (from receipt) ===
    evidence_health = run_receipt.get("evidence_health", {})
    safety_snapshot = run_receipt.get("safety_snapshot", {})
    
    emergency_enabled = safety_snapshot.get("emergency_stop_enabled", False)
    gate_mode = safety_snapshot.get("execution_gate_mode", "MOCK_ONLY")
    health_decision = evidence_health.get("decision", "UNKNOWN")
    
    # === Last Run Triplet (from current run) ===
    overall = run_receipt.get("overall_status", "UNKNOWN")
    run_time = run_receipt.get("asof", asof)
    last_run_triplet = {"last_done": None, "last_failed": None, "last_blocked": None}
    
    if overall == "DONE":
        last_run_triplet["last_done"] = run_time
    elif overall == "FAILED":
        last_run_triplet["last_failed"] = run_time
    elif overall in ("BLOCKED", "STOPPED"):
        last_run_triplet["last_blocked"] = run_time
    
    # === Tickets (from receipt counters) ===
    counters = run_receipt.get("counters", {})
    tickets = {
        "open": counters.get("tickets_open", 0),
        "in_progress": counters.get("tickets_in_progress", 0),
        "done": counters.get("tickets_done", 0),
        "failed": counters.get("tickets_failed", 0),
        "blocked": counters.get("tickets_blocked", 0)
    }
    
    # === Push (from files, as they're not in receipt) ===
    outbox = safe_load_json(OUTBOX_LATEST) or {}
    outbox_rows = outbox.get("messages", [])
    outbox_row_count = len(outbox_rows) if isinstance(outbox_rows, list) else 0
    
    send = safe_load_json(SEND_LATEST) or {}
    last_send_decision = send.get("decision", "N/A")
    
    sender = safe_load_json(SENDER_ENABLE_FILE) or {}
    sender_enabled = sender.get("enabled", False)
    
    # === Evidence ===
    evidence_index = safe_load_json(EVIDENCE_INDEX_LATEST) or {}
    evidence_entries = evidence_index.get("entries", [])
    index_row_count = len(evidence_entries) if isinstance(evidence_entries, list) else 0
    
    # === Overall Status ===
    if emergency_enabled:
        summary_overall_status = "STOPPED"
    elif health_decision == "FAIL":
        summary_overall_status = "BLOCKED"
    elif health_decision == "WARN":
        summary_overall_status = "WARN"
    elif overall == "NO_RUN_HISTORY":
        summary_overall_status = "NO_RUN_HISTORY"
    else:
        summary_overall_status = "OK"
    
    # === Top Risks ===
    top_risks = []
    
    if emergency_enabled:
        top_risks.append({
            "code": "EMERGENCY_STOP",
            "severity": "CRITICAL",
            "message": "Emergency stop is active",
            "evidence_refs": ["state/emergency_stop.json"]
        })
    
    if health_decision == "FAIL":
        top_risks.append({
            "code": "EVIDENCE_HEALTH_FAIL",
            "severity": "CRITICAL",
            "message": "Evidence health check failed",
            "evidence_refs": ["reports/ops/evidence/health/health_latest.json"]
        })
    elif health_decision == "WARN":
        top_risks.append({
            "code": "EVIDENCE_HEALTH_WARN",
            "severity": "WARN",
            "message": "Evidence health check has warnings",
            "evidence_refs": ["reports/ops/evidence/health/health_latest.json"]
        })
    
    if tickets["failed"] > 0:
        top_risks.append({
            "code": "TICKETS_FAILED",
            "severity": "WARN",
            "message": f"{tickets['failed']} ticket(s) failed",
            "evidence_refs": ["state/tickets/ticket_results.jsonl"]
        })
    
    # === Build Summary ===
    summary = {
        "schema": "OPS_SUMMARY_V1",
        "asof": asof,
        "overall_status": summary_overall_status,
        "guard": {
            "evidence_health": {
                "decision": health_decision,
                "fail_closed_triggered": evidence_health.get("fail_closed_triggered", False),
                "snapshot_ref": evidence_health.get("snapshot_ref")
            },
            "emergency_stop": {"enabled": emergency_enabled},
            "execution_gate": {"mode": gate_mode}
        },
        "last_run_triplet": last_run_triplet,
        "tickets": tickets,
        "push": {
            "outbox_row_count": outbox_row_count,
            "last_send_decision": last_send_decision,
            "sender_enabled": sender_enabled
        },
        "evidence": {
            "index_row_count": index_row_count,
            "health_decision": health_decision
        },
        "top_risks": top_risks[:5],
        "source_run_id": run_receipt.get("run_id")
    }
    
    return summary


def save_ops_summary(summary: Dict) -> Dict:
    """Ops Summary 저장 (Atomic Write)"""
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Atomic write latest
    tmp_file = SUMMARY_LATEST.with_suffix('.json.tmp')
    tmp_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(str(tmp_file), str(SUMMARY_LATEST))
    
    # Snapshot (atomic write)
    now = datetime.now()
    snapshot_name = f"ops_summary_{now.strftime('%Y%m%d_%H%M%S')}.json"
    snapshot_path = SUMMARY_SNAPSHOTS_DIR / snapshot_name
    tmp_snapshot = snapshot_path.with_suffix('.json.tmp')
    tmp_snapshot.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(str(tmp_snapshot), str(snapshot_path))
    
    return {
        "result": "OK",
        "overall_status": summary["overall_status"],
        "summary_latest_path": str(SUMMARY_LATEST.relative_to(BASE_DIR)),
        "snapshot_path": str(snapshot_path.relative_to(BASE_DIR))
    }


def generate_and_save_from_receipt(run_receipt: Dict) -> Dict:
    """
    In-Memory Generate → One-Shot Save (C-P.36)
    
    Returns paths for wiring into receipt
    """
    summary = generate_ops_summary_from_receipt(run_receipt)
    return save_ops_summary(summary)


def regenerate_ops_summary() -> Dict:
    """Ops Summary 재생성 (standalone)"""
    summary = generate_ops_summary()
    return save_ops_summary(summary)


if __name__ == "__main__":
    result = regenerate_ops_summary()
    print(json.dumps(result, indent=2))

