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


def regenerate_ops_summary():
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
        "cash_ratio_pct": portfolio.get("cash_ratio_pct", 0) if portfolio else 0
    }
    
    order_plan_summary = {
        "decision": order_plan.get("decision", "UNKNOWN") if order_plan else "UNKNOWN",
        "reason": order_plan.get("reason", "") if order_plan else "",
        "orders_count": len(order_plan.get("orders", [])) if order_plan else 0
    }
    
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
    
    # === Overall Status ===
    if emergency_enabled:
        overall_status = "STOPPED"
    elif health_decision == "FAIL":
        overall_status = "BLOCKED"
    elif not ops_run:
        overall_status = "NO_RUN_HISTORY" # or WARN?
    elif health_decision == "WARN":
        overall_status = "WARN"
    else:
        overall_status = "OK" # Default
        
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

    # 5. Order Plan (D-P.58)
    if order_plan and order_plan.get("decision") == "BLOCKED":
        top_risks.append({
            "code": "ORDER_PLAN_BLOCKED",
            "severity": "WARN",
            "message": f"Order plan blocked: {order_plan.get('reason')}",
            "evidence_refs": ["reports/live/order_plan/latest/order_plan_latest.json"]
        })
        if overall_status == "OK":
            overall_status = "WARN"

    # 6. Strategy Bundle (P78/P79)
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
    result = regenerate_ops_summary()
    print(json.dumps(result, indent=2, ensure_ascii=False))
