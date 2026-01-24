"""
Ops Summary Generator (C-P.35)

Single Pane of Glass: 분산된 최신 산출물을 통합 요약
- 읽기/요약만 허용, 비즈니스 로직 실행 금지
- Atomic Write 필수
"""

import json
import os
from datetime import datetime, timedelta
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
STRATEGY_BUNDLE_LATEST = BASE_DIR / "state" / "strategy_bundle" / "latest" / "strategy_bundle_latest.json"
RECO_LATEST = BASE_DIR / "reports" / "live" / "reco" / "latest" / "reco_latest.json"

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


def find_latest_status_line_refs() -> Dict[str, str]:
    """
    최근 FAILED/BLOCKED 티켓의 라인 번호 찾기 (C-P.44)
    Returns: {"failed_line_ref": "...:lineN", "blocked_line_ref": "...:lineN"}
    """
    refs = {"failed_line_ref": None, "blocked_line_ref": None}
    
    # TICKET_RESULTS에서 최근 FAILED 찾기
    if TICKET_RESULTS.exists():
        try:
            latest_failed_line = None
            latest_failed_time = ""
            with open(TICKET_RESULTS, 'r', encoding='utf-8') as f:
                for line_no, line in enumerate(f, start=1):
                    if line.strip():
                        data = json.loads(line)
                        if data.get("status") == "FAILED":
                            processed_at = data.get("processed_at", "")
                            if processed_at > latest_failed_time:
                                latest_failed_time = processed_at
                                latest_failed_line = line_no
            if latest_failed_line:
                refs["failed_line_ref"] = f"state/tickets/ticket_results.jsonl:line{latest_failed_line}"
        except Exception:
            pass
    
    # TICKET_RECEIPTS에서 최근 BLOCKED 찾기
    receipts_file = BASE_DIR / "state" / "tickets" / "ticket_receipts.jsonl"
    if receipts_file.exists():
        try:
            latest_blocked_line = None
            latest_blocked_time = ""
            with open(receipts_file, 'r', encoding='utf-8') as f:
                for line_no, line in enumerate(f, start=1):
                    if line.strip():
                        data = json.loads(line)
                        if data.get("decision") == "BLOCKED":
                            processed_at = data.get("processed_at", "")
                            if processed_at > latest_blocked_time:
                                latest_blocked_time = processed_at
                                latest_blocked_line = line_no
            if latest_blocked_line:
                refs["blocked_line_ref"] = f"state/tickets/ticket_receipts.jsonl:line{latest_blocked_line}"
        except Exception:
            pass
    
    return refs


def get_strategy_bundle_status() -> Dict[str, Any]:
    """
    Strategy Bundle 상태 조회 (C-P.47)
    
    Returns:
        - present: 번들 존재 여부
        - decision: PASS/WARN/FAIL/NO_BUNDLE
        - bundle_id, created_at, strategy_name, strategy_version
        - stale: 24h 이상 경과 여부
    """
    if not STRATEGY_BUNDLE_LATEST.exists():
        return {
            "present": False,
            "decision": "NO_BUNDLE",
            "latest_ref": None,
            "bundle_id": None,
            "created_at": None,
            "strategy_name": None,
            "strategy_version": None,
            "stale": False,
            "issues": ["NO_BUNDLE_YET"]
        }
    
    try:
        bundle = json.loads(STRATEGY_BUNDLE_LATEST.read_text(encoding="utf-8"))
        
        # Basic validation
        issues = []
        strategy = bundle.get("strategy", {})
        integrity = bundle.get("integrity", {})
        
        # Check required fields
        if bundle.get("schema") != "STRATEGY_BUNDLE_V1":
            issues.append("Invalid schema")
        
        # Check integrity (simplified - full validation in validator module)
        if not integrity.get("payload_sha256"):
            issues.append("Missing payload_sha256")
        
        # Check stale (24h+)
        stale = False
        created_at = bundle.get("created_at", "")
        if created_at:
            try:
                dt_str = created_at[:19]
                created_dt = datetime.fromisoformat(dt_str)
                age = datetime.now() - created_dt
                stale = age > timedelta(hours=24)
            except Exception:
                pass
        
        # Determine decision
        if issues:
            decision = "FAIL"
        elif stale:
            decision = "WARN"
        else:
            decision = "PASS"
        
        return {
            "present": True,
            "decision": decision,
            "latest_ref": "state/strategy_bundle/latest/strategy_bundle_latest.json",
            "bundle_id": bundle.get("bundle_id"),
            "created_at": created_at,
            "strategy_name": strategy.get("name"),
            "strategy_version": strategy.get("version"),
            "stale": stale,
            "issues": issues
        }
    except Exception as e:
        return {
            "present": True,
            "decision": "FAIL",
            "latest_ref": "state/strategy_bundle/latest/strategy_bundle_latest.json",
            "bundle_id": None,
            "created_at": None,
            "strategy_name": None,
            "strategy_version": None,
            "stale": False,
            "issues": [str(e)]
        }


def get_reco_status() -> Dict[str, Any]:
    """
    Reco Report 상태 조회 (D-P.48)
    
    Returns:
        - present: 리포트 존재 여부
        - decision: GENERATED/EMPTY_RECO/BLOCKED/NO_RECO_YET
        - reason, report_id, created_at, summary
        - snapshot_ref: 최신 스냅샷 경로
        - evidence_refs: 증거 참조 경로 목록
    """
    RECO_SNAPSHOTS_DIR = BASE_DIR / "reports" / "live" / "reco" / "snapshots"
    
    # Get latest snapshot
    def get_latest_snapshot_ref():
        try:
            if RECO_SNAPSHOTS_DIR.exists():
                snapshots = sorted(RECO_SNAPSHOTS_DIR.glob("*.json"), reverse=True)
                if snapshots:
                    return f"reports/live/reco/snapshots/{snapshots[0].name}"
        except:
            pass
        return None
    
    if not RECO_LATEST.exists():
        return {
            "present": False,
            "decision": "NO_RECO_YET",
            "reason": "NO_RECO_YET",
            "latest_ref": None,
            "snapshot_ref": None,
            "report_id": None,
            "created_at": None,
            "source_bundle": None,
            "summary": None,
            "evidence_refs": []
        }
    
    try:
        reco = safe_load_json(RECO_LATEST)
        if not reco:
            return {
                "present": False,
                "decision": "NO_RECO_YET",
                "reason": "PARSE_ERROR",
                "latest_ref": "reports/live/reco/latest/reco_latest.json",
                "snapshot_ref": get_latest_snapshot_ref(),
                "report_id": None,
                "created_at": None,
                "source_bundle": None,
                "summary": None,
                "evidence_refs": ["reports/live/reco/latest/reco_latest.json"]
            }
        
        return {
            "present": True,
            "decision": reco.get("decision", "UNKNOWN"),
            "reason": reco.get("reason"),
            "latest_ref": "reports/live/reco/latest/reco_latest.json",
            "snapshot_ref": get_latest_snapshot_ref(),
            "report_id": reco.get("report_id"),
            "created_at": reco.get("created_at"),
            "source_bundle": reco.get("source_bundle"),
            "summary": reco.get("summary"),
            "evidence_refs": reco.get("evidence_refs", ["reports/live/reco/latest/reco_latest.json"])
        }
    except Exception as e:
        return {
            "present": True,
            "decision": "UNKNOWN",
            "reason": f"ERROR: {str(e)}",
            "latest_ref": "reports/live/reco/latest/reco_latest.json",
            "snapshot_ref": get_latest_snapshot_ref(),
            "report_id": None,
            "created_at": None,
            "source_bundle": None,
            "summary": None,
            "evidence_refs": ["reports/live/reco/latest/reco_latest.json"]
        }


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
    
    # Get line-level refs for ticket risks (C-P.44)
    line_refs = find_latest_status_line_refs()
    
    if tickets["failed"] > 0:
        failed_ref = line_refs.get("failed_line_ref") or "state/tickets/ticket_results.jsonl"
        top_risks.append({
            "code": "TICKETS_FAILED",
            "severity": "WARN",
            "message": f"{tickets['failed']} ticket(s) failed",
            "evidence_refs": [failed_ref]
        })
    
    if tickets["blocked"] > 0:
        blocked_ref = line_refs.get("blocked_line_ref") or "state/tickets/ticket_receipts.jsonl"
        top_risks.append({
            "code": "TICKETS_BLOCKED",
            "severity": "WARN",
            "message": f"{tickets['blocked']} ticket(s) blocked",
            "evidence_refs": [blocked_ref]
        })
    
    # === Strategy Bundle Risks (C-P.47) ===
    bundle_status = get_strategy_bundle_status()
    
    if not bundle_status["present"]:
        top_risks.append({
            "code": "NO_STRATEGY_BUNDLE",
            "severity": "WARN",
            "message": "No strategy bundle found",
            "evidence_refs": []
        })
    elif bundle_status["decision"] == "FAIL":
        top_risks.append({
            "code": "BUNDLE_INTEGRITY_FAIL",
            "severity": "CRITICAL",
            "message": f"Strategy bundle integrity failed: {'; '.join(bundle_status.get('issues', []))}",
            "evidence_refs": [bundle_status.get("latest_ref") or "state/strategy_bundle/latest/strategy_bundle_latest.json"]
        })
    elif bundle_status.get("stale"):
        top_risks.append({
            "code": "BUNDLE_STALE",
            "severity": "WARN",
            "message": f"Strategy bundle is stale (created: {bundle_status.get('created_at', 'unknown')})",
            "evidence_refs": [bundle_status.get("latest_ref") or "state/strategy_bundle/latest/strategy_bundle_latest.json"]
        })
    
    # === Reco Status (D-P.48) ===
    reco_status = get_reco_status()
    
    if not reco_status["present"]:
        top_risks.append({
            "code": "NO_RECO_YET",
            "severity": "INFO",
            "message": "No recommendation report generated yet",
            "evidence_refs": []
        })
    elif reco_status["decision"] == "BLOCKED":
        top_risks.append({
            "code": "RECO_BLOCKED",
            "severity": "CRITICAL",
            "message": f"Recommendation generation blocked: {reco_status.get('reason', 'unknown')}",
            "evidence_refs": [reco_status.get("latest_ref") or "reports/live/reco/latest/reco_latest.json"]
        })
    elif reco_status["decision"] == "EMPTY_RECO":
        reason = reco_status.get('reason', 'unknown')
        if reason == "NO_BUNDLE":
            msg = "Empty reco: NO_BUNDLE (PC→OCI bundle handoff required)"
        elif reason == "BUNDLE_STALE":
            msg = "Empty reco: BUNDLE_STALE (bundle >24h old, regenerate on PC)"
        else:
            msg = f"Empty reco due to: {reason}"
        top_risks.append({
            "code": "EMPTY_RECO",
            "severity": "WARN",
            "message": msg,
            "evidence_refs": reco_status.get("evidence_refs", [reco_status.get("latest_ref") or "reports/live/reco/latest/reco_latest.json"])
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
        "strategy_bundle": bundle_status,
        "reco": reco_status,
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

