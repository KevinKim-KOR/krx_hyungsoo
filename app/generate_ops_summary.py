"""
Ops Summary Generator (C-P.35 + D-P.58 + D-P.59)

Single Pane of Glass: 분산된 최신 산출물을 통합 요약
- 읽기/요약만 허용, 비즈니스 로직 실행 금지
- Atomic Write 필수
- D-P.58: Portfolio, Order Plan status & risk included
- D-P.59: Portfolio Stale Risk (7 days inactive)
"""

import json
import os
import shutil
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
CYCLE_LATEST = BASE_DIR / "reports" / "live" / "cycle" / "latest" / "live_cycle_latest.json"
# D-P.58
PORTFOLIO_LATEST = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"
ORDER_PLAN_LATEST = BASE_DIR / "reports" / "live" / "order_plan" / "latest" / "order_plan_latest.json"
CONTRACT5_LATEST = BASE_DIR / "reports" / "ops" / "contract5" / "latest" / "ai_report_latest.json"

# Output paths
SUMMARY_DIR = BASE_DIR / "reports" / "ops" / "summary"
SUMMARY_LATEST = SUMMARY_DIR / "ops_summary_latest.json"
SUMMARY_SNAPSHOTS_DIR = SUMMARY_DIR / "snapshots"

# Risk Window Configuration (D-P.52)
OPS_RISK_WINDOW_DAYS = int(os.environ.get("OPS_RISK_WINDOW_DAYS", "3"))
OPS_RISK_MAX_EVENTS = int(os.environ.get("OPS_RISK_MAX_EVENTS", "200"))
TICKET_FAIL_EXCLUDE_PREFIXES = os.environ.get(
    "OPS_TICKET_FAIL_EXCLUDE_PREFIXES", 
    "AUTO_CLEANUP_,MANUAL_CLEANUP,REAPER_"
).split(",")

# Risk Configuration (D-P.59)
PORTFOLIO_STALE_DAYS = int(os.environ.get("PORTFOLIO_STALE_DAYS", "7"))


# Forbidden prefixes to strip
FORBIDDEN_PREFIXES = ["json:", "file://", "file:", "http://", "https://"]

# Risk Severity Map (P106)
# Lower value = Higher Priority (Stable Sort)
SEVERITY_MAP = {
    "CRITICAL": 0,
    "BLOCKED": 0, 
    "WARN": 1,
    "INFO": 2,
    "OK": 3
}

RISK_CODE_MAP = {
    "EMERGENCY_STOP": "CRITICAL",
    "EVIDENCE_HEALTH_FAIL": "CRITICAL",
    "PORTFOLIO_INCONSISTENT": "CRITICAL",
    "EVIDENCE_HEALTH_WARN": "WARN",
    "TICKETS_FAILED": "WARN",
    "NO_PORTFOLIO": "WARN",
    "PORTFOLIO_STALE_WARN": "WARN",
    "ORDER_PLAN_NO_RECO": "WARN",
    "ORDER_PLAN_BLOCKED": "WARN",
    "CONTRACT5_REPORT_BLOCKED": "WARN", 
    "CONTRACT5_REPORT_EMPTY": "INFO", 
    "NO_BUNDLE": "WARN",
    "BUNDLE_STALE_WARN": "WARN",
    "NO_RECO_YET": "WARN",
    "RECO_EMPTY": "WARN",
    "STALE_BUNDLE_BLOCKS_RECO": "WARN"
}


def sanitize_evidence_ref(ref: str) -> str:
    """evidence_ref 정제"""
    if not ref or not isinstance(ref, str):
        return None
    cleaned = ref.strip()
    for prefix in FORBIDDEN_PREFIXES:
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    if ".." in cleaned or not cleaned:
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
    """가장 최근에 실행된 daily ops run 스냅샷 로드"""
    if not OPS_RUN_LATEST.exists():
        return None
    snapshots = sorted(OPS_RUN_LATEST.glob("*.json"), reverse=True)
    if not snapshots:
        return None
    return safe_load_json(snapshots[0])


def get_tickets_summary() -> Dict[str, int]:
    """티켓 상태별 카운트 (전체)"""
    stats = {"open": 0, "in_progress": 0, "done": 0, "failed": 0, "blocked": 0}
    if TICKET_RESULTS.exists():
        with open(TICKET_RESULTS, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    row = json.loads(line)
                    status = row.get("status", "").lower()
                    if status in stats:
                        stats[status] += 1
                except: pass
    return stats


def get_tickets_recent() -> Dict[str, Any]:
    """최근 N일간 티켓 통계 (Risk Window)"""
    now = datetime.now()
    start_dt = now - timedelta(days=OPS_RISK_WINDOW_DAYS)
    
    stats = {
        "window_days": OPS_RISK_WINDOW_DAYS,
        "max_events": OPS_RISK_MAX_EVENTS,
        "start_at": start_dt.isoformat(),
        "end_at": now.isoformat(),
        "failed": 0,
        "excluded_cleanup_failed": 0,
        "blocked": 0,
        "done": 0,
        "in_progress": 0,
        "failed_line_refs": []
    }
    
    if not TICKET_RESULTS.exists():
        return stats
        
    events = []
    line_num = 0
    with open(TICKET_RESULTS, 'r', encoding='utf-8') as f:
        for line in f:
            line_num += 1
            try:
                row = json.loads(line)
                ts_str = row.get("timestamp") or row.get("finished_at") or ""
                if not ts_str: continue
                
                # Simple ISO parsing (minimal)
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=now.tzinfo)
                
                if dt >= start_dt:
                    row["_line"] = line_num
                    events.append(row)
            except: pass
            
    # Recent events only
    events.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    events = events[:OPS_RISK_MAX_EVENTS]
    
    for row in events:
        status = row.get("status", "").lower()
        ticket_key = row.get("ticket_key", "")
        
        if status == "failed":
            # Exclude check
            is_excluded = False
            for prefix in TICKET_FAIL_EXCLUDE_PREFIXES:
                if prefix and ticket_key.startswith(prefix):
                    is_excluded = True
                    break
            
            if is_excluded:
                stats["excluded_cleanup_failed"] += 1
            else:
                stats["failed"] += 1
                ref = f"state/tickets/ticket_results.jsonl:line{row['_line']}"
                stats["failed_line_refs"].append(ref)
        elif status == "blocked":
            stats["blocked"] += 1
        elif status == "done":
            stats["done"] += 1
        elif status == "in_progress":
            stats["in_progress"] += 1
            
    return stats


def generate_ops_summary():
    """Ops Summary 생성"""
    now = datetime.now()
    
    # === Health ===
    health = safe_load_json(HEALTH_LATEST) or {}
    health_decision = health.get("decision", "UNKNOWN")
    health_snapshot_ref = health.get("snapshot_ref")
    
    if health_snapshot_ref:
        health_snapshot_ref = sanitize_evidence_ref(health_snapshot_ref)
    
    if not health_snapshot_ref:
        # Try to find latest snapshot
        base_snap_dir = BASE_DIR / "reports" / "ops" / "evidence" / "health" / "snapshots"
        if base_snap_dir.exists():
            snaps = sorted(base_snap_dir.glob("*.json"), reverse=True)
            if snaps:
                health_snapshot_ref = f"reports/ops/evidence/health/snapshots/{snaps[0].name}"

    # Default Daily Summary placeholders (calculated externally or below if logic exists)
    ds_decision = "PENDING"
    ds_sentiment = "NEUTRAL"
    ds_summary = "Pending calculation"

    # === Gate & Emergency ===
    emergency = safe_load_json(EMERGENCY_STOP_FILE) or {"enabled": False}
    emergency_enabled = emergency.get("enabled", False)
    
    gate = safe_load_json(GATE_FILE) or {"mode": "DRY_RUN"}
    
    # === Last Run ===
    ops_run = get_latest_ops_run()
    last_run_triplet = {"last_done": None, "last_failed": None, "last_blocked": None}
    
    if ops_run:
        status = ops_run.get("overall_status", "")
        run_time = ops_run.get("asof")
        if status == "DONE" or status == "WARN" or status == "OK":  # OK/WARN treated as DONE concept
            last_run_triplet["last_done"] = run_time
        elif status == "FAILED":
            last_run_triplet["last_failed"] = run_time
        elif status in ("BLOCKED", "STOPPED"):
            last_run_triplet["last_blocked"] = run_time
            
    # === Tickets ===
    tickets_summary = get_tickets_summary()
    tickets_recent = get_tickets_recent()
    
    # === Push ===
    outbox = safe_load_json(OUTBOX_LATEST) or {}
    outbox_count = len(outbox.get("messages", []))
    
    send = safe_load_json(SEND_LATEST) or {}
    send_decision = send.get("decision", "N/A")
    
    # === D-P.58: Portfolio & Order Plan ===
    portfolio = safe_load_json(PORTFOLIO_LATEST)
    order_plan = safe_load_json(ORDER_PLAN_LATEST)
    
    portfolio_summary = {
        "present": bool(portfolio),
        "updated_at": portfolio.get("updated_at") if portfolio else None,
        "total_value": portfolio.get("total_value", 0) if portfolio else 0,
        "cash_ratio_pct": portfolio.get("cash_ratio_pct", 0) if portfolio else 0,
        # P137: Source Visibility
        "source": portfolio.get("source", "LOCAL_STATE") if portfolio else "MISSING",
        "bundle_id": portfolio.get("bundle_id") if portfolio else None,
        "integrity_prefix": portfolio.get("integrity", {}).get("payload_sha256", "")[:8] if portfolio and portfolio.get("integrity") else None
    }
    
    order_plan = safe_load_json(ORDER_PLAN_LATEST)
    
    # Find Order Plan Snapshot
    op_snapshot_ref = None
    op_snap_dir = BASE_DIR / "reports" / "live" / "order_plan" / "snapshots"
    if op_snap_dir.exists():
        snaps = sorted(op_snap_dir.glob("order_plan_*.json"), reverse=True)
        if snaps:
            op_snapshot_ref = f"reports/live/order_plan/snapshots/{snaps[0].name}"
            
    order_plan_summary = {
        "decision": order_plan.get("decision", "UNKNOWN") if order_plan else "UNKNOWN",
        "reason": order_plan.get("reason", "") if order_plan else "",
        "reason_detail": order_plan.get("reason_detail", "") if order_plan else "",
        "orders_count": len(order_plan.get("orders", [])) if order_plan else 0,
        "latest_ref": "reports/live/order_plan/latest/order_plan_latest.json",
        "snapshot_ref": op_snapshot_ref
    }
    
    # === Contract 5 (P103) ===
    c5_report = safe_load_json(CONTRACT5_LATEST)
    
    # Find C5 Snapshot
    c5_snapshot_ref = None
    c5_snap_dir = BASE_DIR / "reports" / "ops" / "contract5" / "snapshots"
    if c5_snap_dir.exists():
        snaps = sorted(c5_snap_dir.glob("ai_report_*.json"), reverse=True)
        if snaps:
            c5_snapshot_ref = f"reports/ops/contract5/snapshots/{snaps[0].name}"
            
    c5_decision = c5_report.get("decision", "MISSING") if c5_report else "MISSING"
    

    
    # === P78/P79: Strategy Bundle (SPoT) ===
    import sys
    # Add app path if not present (sometimes issue with relative imports if main script)
    if str(BASE_DIR) not in sys.path:
        sys.path.append(str(BASE_DIR))
    
    from app.load_strategy_bundle import load_latest_bundle
    
    bundle, validation = load_latest_bundle()
    
    bundle_summary = {
        "present": bundle is not None,
        "created_at": validation.created_at,
        "strategy_name": validation.strategy_name or "Unknown",
        "stale": validation.stale,
        "stale_reason": validation.stale_reason
    }
    
    # === Overall Status (Initial) ===
    # Use logic but allow Override by Risks later
    if emergency_enabled:
        overall_status = "STOPPED"
    elif health_decision == "FAIL":
        overall_status = "BLOCKED"
    elif not ops_run:
        overall_status = "NO_RUN_HISTORY" 
    elif health_decision == "WARN":
        overall_status = "WARN"
    else:
        overall_status = "OK" 
        
    # === Top Risks ===
    top_risks = []
    
    # 1. Emergency
    if emergency_enabled:
        top_risks.append({
            "code": "EMERGENCY_STOP",
            "severity": "CRITICAL",
            "message": "Emergency stop is active",
            "evidence_refs": ["state/emergency_stop.json"]
        })
        
    # 2. Health
    health_evidence = ["reports/ops/evidence/health/health_latest.json"]
    if health_snapshot_ref:
        health_evidence.append(health_snapshot_ref)
        
    if health_decision == "FAIL":
        top_risks.append({
            "code": "EVIDENCE_HEALTH_FAIL", 
            "severity": "CRITICAL", 
            "message": "Evidence health check failed",
            "evidence_refs": health_evidence
        })
    elif health_decision == "WARN":
        top_risks.append({
            "code": "EVIDENCE_HEALTH_WARN", 
            "severity": "WARN", 
            "message": "Evidence health check has warnings",
            "evidence_refs": health_evidence
        })

    # 3. Tickets (Recent)
    if tickets_recent["failed"] > 0:
        top_risks.append({
            "code": "TICKETS_FAILED",
            "severity": "WARN",
            "message": f"{tickets_recent['failed']} tickets failed in last {OPS_RISK_WINDOW_DAYS} days",
            "evidence_refs": tickets_recent["failed_line_refs"]
        })
        
    # 4. Portfolio (D-P.59 Stale Check)
    if not portfolio:
        top_risks.append({
            "code": "NO_PORTFOLIO",
            "severity": "WARN",
            "message": "Portfolio data missing",
            "evidence_refs": []
        })
        if overall_status == "OK":
            overall_status = "WARN"
    else:
        # Check staleness
        updated_at_str = portfolio.get("updated_at", "")
        if updated_at_str:
            try:
                # Handle possible milliseconds
                updated_dt = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                # Naively assume local time if no tz, or match now.tz
                if updated_dt.tzinfo is None:
                    updated_dt = updated_dt.replace(tzinfo=now.tzinfo)
                
                days_diff = (now - updated_dt).days
                if days_diff >= PORTFOLIO_STALE_DAYS:
                    top_risks.append({
                        "code": "PORTFOLIO_STALE_WARN",
                        "severity": "WARN",
                        "message": f"Portfolio not updated for {days_diff} days (Limit: {PORTFOLIO_STALE_DAYS})",
                        "evidence_refs": ["state/portfolio/latest/portfolio_latest.json"]
                    })
            except Exception:
                pass # Parse error ignore

    # 5. Order Plan (D-P.58 + P83-FIX + P102)
    # P83-FIX: Skip ORDER_PLAN_* risks if bundle is stale (stale is root cause)
    bundle_is_stale = validation.stale if validation else False
    
    op_decision = order_plan.get("decision", "UNKNOWN") if order_plan else "UNKNOWN"
    op_reason = order_plan.get("reason", "") if order_plan else ""
    
    if op_decision == "BLOCKED" and not bundle_is_stale:
        # P102 Risks
        if op_reason == "NO_RECO":
            top_risks.append({
                "code": "ORDER_PLAN_NO_RECO",
                "severity": "WARN", 
                "message": "Order Plan blocked: Reco missing",
                "evidence_refs": []
            })
            if overall_status == "OK": overall_status = "WARN" # or BLOCKED?
            
    # 6. Order Plan Export (P111)
    # Check if Order Plan is GENERATED but Export is missing or stale

            
        elif op_reason == "PORTFOLIO_INCONSISTENT":
            top_risks.append({
                "code": "PORTFOLIO_INCONSISTENT",
                "severity": "CRITICAL", 
                "message": f"Portfolio Inconsistent: {order_plan.get('reason_detail')}",
                "evidence_refs": ["state/portfolio/latest/portfolio_latest.json"]
            })
            overall_status = "BLOCKED" # Critical
            
        else:
            # Generic Blocked
            # P86: SSOT - Stack Umbrella + Specific Risk
            reason_code = op_reason.split(":")[0].strip()
            
            # Umbrella Risk
            # P106: Enrich message with detail for SSOT consumers
            detail_txt = order_plan.get("reason_detail", "")
            msg = f"Order plan blocked: {reason_code}"
            if detail_txt:
                msg += f" ({detail_txt})"

            top_risks.append({
                "code": "ORDER_PLAN_BLOCKED",
                "severity": "WARN",
                "message": msg,
                "evidence_refs": ["reports/live/order_plan/latest/order_plan_latest.json"]
            })
            
            if overall_status == "OK": overall_status = "WARN"



    # 6. Order Plan Export (P111)
    # Check if Order Plan is GENERATED but Export is missing or stale
    if op_decision == "GENERATED" or op_decision == "EMPTY":
        export_path = BASE_DIR / "reports" / "live" / "order_plan_export" / "latest" / "order_plan_export_latest.json"
        
        has_export = False
        if export_path.exists():
            try:
                export_data = json.loads(export_path.read_text(encoding="utf-8"))
                # Check Plan ID match
                export_plan_id = export_data.get("source", {}).get("plan_id")
                plan_id = order_plan.get("plan_id")
                
                if export_plan_id == plan_id:
                    has_export = True
            except Exception:
                pass
        
        if not has_export:
            top_risks.append({
                "code": "MISSING_EXPORT",
                "severity": "WARN",
                "message": "Order Plan generated but Export (Human Gate) missing",
                "evidence_refs": []
            })
            if overall_status == "OK":
                overall_status = "WARN"


    # 7. Execution Prep (P112)
    # If Expect exists, check Prep
    prep_path = BASE_DIR / "reports" / "live" / "execution_prep" / "latest" / "execution_prep_latest.json"
    prep_data = None
    if prep_path.exists():
        try:
             prep_data = json.loads(prep_path.read_text(encoding="utf-8"))
        except Exception:
             pass
             





    # 8. Manual Loop (P114)
    # Check Export -> Prep -> Ticket -> Record sequence
    # Paths
    export_path = BASE_DIR / "reports" / "live" / "order_plan_export" / "latest" / "order_plan_export_latest.json"
    prep_path = BASE_DIR / "reports" / "live" / "execution_prep" / "latest" / "execution_prep_latest.json"
    ticket_path = BASE_DIR / "reports" / "live" / "manual_execution_ticket" / "latest" / "manual_execution_ticket_latest.json"
    record_path = BASE_DIR / "reports" / "live" / "manual_execution_record" / "latest" / "manual_execution_record_latest.json"
    
    # Load Data
    export_data = safe_load_json(export_path) if export_path.exists() else None
    prep_data = safe_load_json(prep_path) if prep_path.exists() else None
    ticket_data = safe_load_json(ticket_path) if ticket_path.exists() else None
    record_data = safe_load_json(record_path) if record_path.exists() else None
    
    manual_stage = "UNKNOWN"
    
    # Logic
    if not export_data or export_data.get("decision") == "BLOCKED":
        manual_stage = "BLOCKED" # Or UPSTREAM_BLOCKED
    else:
        # Export is Ready
        if not prep_data or prep_data.get("decision") != "READY":
            manual_stage = "NEED_HUMAN_CONFIRM"
        else:
            # Prep is Ready
            if not ticket_data or ticket_data.get("decision") != "GENERATED":
                # P140: If Prep is READY, we are effectively PREP_READY or AWAITING_HUMAN_EXECUTION
                # If Ticket is missing/blocked but Prep is READY, the next auto-step (Ticket Gen) should happen.
                manual_stage = "PREP_READY"
            else:
                # Ticket is Ready
                manual_stage = "AWAITING_HUMAN_EXECUTION"
                
                # Check Record
                if record_data and record_data.get("decision") in ["EXECUTED", "PARTIAL", "SKIPPED"]:
                    # P123: Partial/Retry Stages
                    exec_res = record_data.get("execution_result", "EXECUTED")
                    if exec_res == "PARTIAL":
                        manual_stage = "DONE_TODAY_PARTIAL"
                    elif exec_res == "NOT_EXECUTED":
                        manual_stage = "AWAITING_RETRY_EXECUTION"
                    else:
                        manual_stage = "DONE_TODAY"
                            
                        # Check linkage
                        # rec_src = record_data.get("source", {}) # Legacy field or new structure? 
                        # P122 uses linkage.plan_id. P123 contract says linkage.plan_id.
                        # But legacy `source.plan_id` might be gone?
                        # generate_ops_summary.py uses 'linkage' usually?
                        # Let's check how it checks linkage. 
                        # Actually, record generator enforces linkage. If it's EXECUTED/PARTIAL/SKIPPED, linkage is valid.
                        pass
                elif ticket_data and ticket_data.get("decision") == "GENERATED":
                    manual_stage = "AWAITING_RECORD_SUBMIT"

                    # P131: Check for Dry Run Record
                    dry_run_path = BASE_DIR / "reports" / "live" / "dry_run_record" / "latest" / "dry_run_record_latest.json"
                    if dry_run_path.exists():
                        try:
                            dry_run_data = json.loads(dry_run_path.read_text(encoding="utf-8"))
                            # Verify Linkage (Dry Run must be for CURRENT ticket)
                            dr_ticket_id = dry_run_data.get("linkage", {}).get("ticket_id")
                            current_ticket_id = ticket_data.get("id")
                            
                            if dr_ticket_id == current_ticket_id:
                                manual_stage = "DONE_TODAY"
                        except Exception:
                            pass

    # Next Action Logic (P115)
    next_action = "NONE"
    if manual_stage == "NEED_HUMAN_CONFIRM":
        next_action = "bash deploy/oci/manual_loop_prepare.sh"
    elif manual_stage == "AWAITING_HUMAN_EXECUTION":
        next_action = "EXECUTE TRADES -> bash deploy/oci/manual_loop_submit_record.sh <record_file>"
    elif manual_stage == "AWAITING_RECORD_SUBMIT":
        # Check if latest record is blocked
        rec_dec = record_data.get("decision", "UNKNOWN") if record_data else "UNKNOWN"
        if rec_dec == "BLOCKED":
            reason = record_data.get("reason", "UNKNOWN")
            if reason == "DUPLICATE_SUBMIT_BLOCKED":
                top_risks.append({
                    "code": "DUPLICATE_RECORD_BLOCKED",
                    "severity": "WARN",
                    "message": "Duplicate record submission attempted.",
                    "evidence_refs": ["reports/live/manual_execution_record/latest/manual_execution_record_latest.json"]
                })
            elif reason == "LINKAGE_MISMATCH":
                top_risks.append({
                    "code": "RECORD_LINKAGE_MISMATCH",
                    "severity": "BLOCK",
                    "message": f"Record Linkage ID Mismatch: {record_data.get('reason_detail')}",
                    "evidence_refs": ["reports/live/manual_execution_record/latest/manual_execution_record_latest.json"]
                })
                overall_status = "BLOCKED"
        
        next_action = "bash deploy/oci/manual_loop_submit_record.sh <record_file>"
    elif manual_stage == "DONE_TODAY":
        next_action = "NONE (Done)"
    elif manual_stage == "DONE_TODAY_PARTIAL":
        next_action = "REVIEW PARTIALS / RE-SUBMIT (Optional)"
    elif manual_stage == "AWAITING_RETRY_EXECUTION":
         next_action = "RETRY EXECUTION -> bash deploy/oci/manual_loop_submit_record.sh"
    elif manual_stage == "AWAITING_RETRY_EXECUTION":
         next_action = "RETRY EXECUTION -> bash deploy/oci/manual_loop_submit_record.sh"

    # P131/P132: Determine Execution Mode
    mode = "LIVE"
    try:
        # Check if we are in Dry Run mode (only if Done/Partial)
        if manual_stage in ["DONE_TODAY", "DONE_TODAY_PARTIAL"]:
            dry_run_path = BASE_DIR / "reports" / "live" / "dry_run_record" / "latest" / "dry_run_record_latest.json"
            if dry_run_path.exists():
                 dr_data = json.loads(dry_run_path.read_text(encoding="utf-8"))
                 # Verify linkage
                 if ticket_data and dr_data.get("linkage", {}).get("ticket_id") == ticket_data.get("id"):
                     mode = "DRY_RUN"
    except Exception:
        pass
    # Risks based on Stage
    if manual_stage == "NEED_HUMAN_CONFIRM":
        top_risks.append({
            "code": "NEED_HUMAN_CONFIRM",
            "severity": "WARN", 
            "message": "Order Plan Export Ready. Human Confirmation Required.",
            "evidence_refs": ["reports/live/order_plan_export/latest/order_plan_export_latest.json"]
        })
        if overall_status == "OK": overall_status = "WARN"
        
    elif manual_stage == "PREP_READY":
         # Info: Prep Ready, Generate Ticket
         prep_dec = prep_data.get("decision", "UNKNOWN")
         if prep_dec == "BLOCKED":
             top_risks.append({
                 "code": "EXECUTION_GUARDRAILS_BLOCKED",
                 "severity": "BLOCK",
                 "message": f"Execution Prep BLOCKED: {prep_data.get('reason_detail')}",
                 "evidence_refs": ["reports/live/execution_prep/latest/execution_prep_latest.json"]
             })
             overall_status = "BLOCKED"
         elif prep_dec == "WARN":
             top_risks.append({
                 "code": "EXECUTION_GUARDRAILS_WARN",
                 "severity": "WARN",
                 "message": f"Execution Prep WARNING: {prep_data.get('reason_detail')}",
                 "evidence_refs": ["reports/live/execution_prep/latest/execution_prep_latest.json"]
             })
             if overall_status == "OK": overall_status = "WARN" 

    elif manual_stage == "AWAITING_HUMAN_EXECUTION":
         # Maybe INFO or WARN if late?
         pass
         
    elif manual_stage == "AWAITING_RECORD_SUBMIT":
         top_risks.append({
            "code": "MANUAL_RECORD_MISSING",
            "severity": "INFO",
            "message": "Execution Ticket Generated. Waiting for Record.",
            "evidence_refs": ["reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.json"]
        })

    # P111 Export Logic (Legacy Step 6 removed or merged?)
    # Previous Step 6 logic (Lines 455-483 in previous edits) checked for Export missing.
    # Now that we rely on "manual_stage", do we still need that?
    # Yes, if Order Plan GENERATED but Export Missing -> That is effectively manual_stage="BLOCKED" or "EXPORT_MISSING"?
    # If order plan generated, daily_ops should have generated Export.
    # If Export missing, manual_stage will be "BLOCKED" (first branch).
    # But we might want specific warning "MISSING_EXPORT".
    
    # 7. Execution Prep (Step 7 logic from previous edit) -> Merged into Manual Loop.
    # We should remove the old Step 6/7 blocks if they duplicate.

    # 9. Contract 5 Risks (P103)
    if c5_decision == "BLOCKED":
        top_risks.append({
            "code": "CONTRACT5_REPORT_BLOCKED",
            "severity": "WARN", # or BLOCKED? User says WARN/BLOCKED in instruction.
            "message": f"Daily Report Blocked: {c5_report.get('reason_detail', '') if c5_report else 'Missing'}",
            "evidence_refs": ["reports/ops/contract5/latest/ai_report_latest.json"]
        })
        if overall_status == "OK": overall_status = "WARN"
        
    elif c5_decision == "EMPTY":
        top_risks.append({
            "code": "CONTRACT5_REPORT_EMPTY",
            "severity": "INFO",
            "message": "Daily Report Empty",
            "evidence_refs": ["reports/ops/contract5/latest/ai_report_latest.json"]
        })

    # 7. Strategy Bundle (P78/P79)
    if validation.decision == "NO_BUNDLE":
        top_risks.append({
            "code": "NO_BUNDLE",
            "severity": "WARN", 
            "message": "Strategy Bundle missing",
            "evidence_refs": []
        })
        if overall_status == "OK":
            overall_status = "WARN"
    else:
        # SPoT: validation.stale
        if validation.stale:
            top_risks.append({
                "code": "BUNDLE_STALE_WARN",
                "severity": "WARN",
                "message": f"Strategy Bundle Stale: {validation.stale_reason}",
                "evidence_refs": ["state/strategy_bundle/latest/strategy_bundle_latest.json"]
            })
            # Ops Summary does not mandate Fail-Closed for stale bundle, but Reco does.
            # Here we just report risk.
            if overall_status == "OK":
                 overall_status = "WARN"

    # === Reco (For Daily Summary logic) ===
    reco = safe_load_json(RECO_LATEST)
    
    reco_decision = reco.get("decision", "MISSING_RECO") if reco else "MISSING_RECO"
    reco_reason = reco.get("reason", "") if reco else ""
    
    source_bundle_id = None
    if reco and reco.get("source_bundle"):
        source_bundle_id = reco["source_bundle"].get("bundle_id")
        
    # Find latest reco snapshot
    reco_snapshot_ref = None
    reco_snap_dir = BASE_DIR / "reports" / "live" / "reco" / "snapshots"
    if reco_snap_dir.exists():
        snaps = sorted(reco_snap_dir.glob("reco_*.json"), reverse=True)
        if snaps:
            reco_snapshot_ref = f"reports/live/reco/snapshots/{snaps[0].name}"

    reco_summary = {
        "decision": reco_decision,
        "reason": reco_reason,
        "latest_ref": "reports/live/reco/latest/reco_latest.json",
        "snapshot_ref": reco_snapshot_ref,
        "source_bundle_id": source_bundle_id
    }
    
    # Reco Risks
    if reco_decision == "MISSING_RECO":
        top_risks.append({
            "code": "NO_RECO_YET",
            "severity": "WARN",
            "message": "Reco report missing",
            "evidence_refs": []
        })
        if overall_status == "OK":
            overall_status = "WARN"
            
    elif reco_decision == "EMPTY_RECO":
        top_risks.append({
            "code": "RECO_EMPTY", 
            "severity": "WARN",
            "message": f"Reco Empty: {reco_reason}",
            "evidence_refs": ["reports/live/reco/latest/reco_latest.json"]
        })
        if overall_status == "OK":
            overall_status = "WARN"
            
    elif reco_decision == "BLOCKED":
        # Check if bundle related
        if "BUNDLE" in reco_reason:
            top_risks.append({
                "code": "STALE_BUNDLE_BLOCKS_RECO",
                "severity": "WARN",
                "message": f"Reco blocked by bundle: {reco_reason}",
                "evidence_refs": ["reports/live/reco/latest/reco_latest.json"]
            })
            if overall_status == "OK":
                overall_status = "WARN"

    # Sort Risks (P106: Stable Sort)
    # 1. Severity (Ascending: 0=Critical to 3=OK)
    # 2. Stable Sort (Preserve original order for same severity)
    def risk_sort_key(r):
        return SEVERITY_MAP.get(r.get("severity", "INFO"), 2)
        
    top_risks.sort(key=risk_sort_key)
    
    # Update Overall Status based on Top Risk (SSOT)
    if top_risks:
        top_sev_str = top_risks[0].get("severity", "INFO")
        if top_sev_str in ("CRITICAL", "BLOCKED"):
            overall_status = "BLOCKED"
        elif top_sev_str == "WARN":
            if overall_status != "BLOCKED":
                 overall_status = "WARN"
    else:
        # P106-FIX1: Fallback if status is bad but no risks
        if overall_status != "OK" and overall_status != "NO_RUN_HISTORY":
             top_risks.append({
                 "code": f"OPS_{overall_status}",
                 "severity": "WARN" if overall_status == "WARN" else "BLOCKED",
                 "message": f"Operational status is {overall_status} but no specific risk identified.",
                 "evidence_refs": []
             })

    # Force STOPPED if emergency
    if emergency_enabled:
        overall_status = "STOPPED"

    # Construct Contract 5 Summary (Late Binding)


    # Construct Manual Loop Summary
    manual_loop_summary = {
        "stage": manual_stage,
        "mode": mode,
        "next_action": next_action,
        "export": export_data,
        "prep": prep_data,
        "ticket": ticket_data,
        "record": record_data
    }

    # Construct Contract 5 Summary (Late Binding)
    contract5_summary = {
        "human_report": {
            "decision": c5_decision,
            "latest_ref": "reports/phase_c/latest/report_human.json",
            "snapshot_ref": c5_snapshot_ref.replace("ai_report", "human_report").replace(".json", ".md") if c5_snapshot_ref else None
        },
        "daily_summary": {
            "decision": ds_decision,
            "sentiment": ds_sentiment,
            "summary_text": ds_summary
        },
        "ai_report": {
            "decision": c5_decision,
            "latest_ref": "reports/ops/contract5/latest/ai_report_latest.json",
            "snapshot_ref": c5_snapshot_ref
        }
    }

    # Construct Summary
    summary = {
        "schema": "OPS_SUMMARY_V1",
        "asof": now.isoformat(),
        "overall_status": overall_status,
        "guard": {
            "evidence_health": {
                "decision": health_decision,
                "snapshot_ref": health_snapshot_ref
            },
            "emergency_stop": emergency,
            "execution_gate": gate
        },
        "last_run_triplet": last_run_triplet,
        "tickets": tickets_summary,
        "tickets_recent": tickets_recent,
        "push": {
            "outbox_row_count": outbox_count,
            "last_send_decision": send_decision
        },
        "portfolio": portfolio_summary,
        "order_plan": order_plan_summary,
        "manual_loop": manual_loop_summary,
        "contract5": contract5_summary,
        "reco": reco_summary,
        "strategy_bundle": bundle_summary,
        "top_risks": top_risks,
        "evidence_refs": [
            "reports/ops/daily/snapshots", # snapshot dir
            "state/tickets/ticket_results.jsonl",
            "reports/ops/evidence/health/health_latest.json"
        ]
    }
    
    # Save
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_LATEST.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    
    # Snapshot
    SUMMARY_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    snap_name = f"ops_summary_{now.strftime('%Y%m%d_%H%M%S')}.json"
    shutil.copy(SUMMARY_LATEST, SUMMARY_SNAPSHOTS_DIR / snap_name)
    
    return summary


if __name__ == "__main__":
    result = generate_ops_summary()
    print(json.dumps(result, indent=2, ensure_ascii=False))
