"""
Ops Run Dashboard (P76)

Aggregates system status from local API:
1. Backend Health
2. Key Evidence Aliases (Spike, Holding, Contract 5, Daily Status)

Usage:
    python3 -m app.utils.ops_dashboard
"""

import sys
import json
import urllib.request
import urllib.error
from datetime import datetime

# Configuration
API_BASE = "http://localhost:8000"
TIMEOUT_SEC = 2

# ANSI Colors
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"

def get_json(url):
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SEC) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    return {"error": "Unknown Code"}

def print_header():
    print(f"\n{Colors.BOLD}=== KRX ALERTOR OPS DASHBOARD ==={Colors.RESET}")
    print(f"{Colors.GRAY}Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.RESET}\n")

def check_backend():
    # 1. Connectivity Check
    status_url = f"{API_BASE}/api/status"
    status_data = get_json(status_url)
    
    print(f"{Colors.BOLD}[Backend System]{Colors.RESET}")
    
    # Check for connection error
    if "error" in status_data and status_data["error"]:
        print(f"  {Colors.RED}● DOWN{Colors.RESET} ({status_data['error']})")
        return False, {}

    # 2. Source of Truth: Ops Summary
    # The user wants to rely on ops_summary/latest for the status text
    summary_url = f"{API_BASE}/api/ops/summary/latest"
    summary_data = get_json(summary_url)
    
    ops_status = "UNKNOWN"
    ops_asof = "?"
    
    # Check if summary fetch was successful (it might fail if file doesn't exist, but backend is up)
    if "error" not in summary_data or not summary_data["error"]:
        # Handle Envelope (rows) vs Flat
        # Logic: row=(d.get("rows") or [d])[0]
        rows = summary_data.get("rows")
        if not rows:
            # Fallback for flat structure or empty rows
            rows = [summary_data]
            
        if rows:
            first_row = rows[0]
            # Verify it's a dict before accessing
            if isinstance(first_row, dict):
                ops_status = first_row.get("overall_status", "UNKNOWN")
                ops_asof = first_row.get("asof", "?")
                # Return this row as the SSOT summary
                summary_data = first_row

    # If we got this far, the Backend is ONLINE.
    print(f"  {Colors.GREEN}● ONLINE{Colors.RESET} (OpsStatus: {ops_status}, Msg: asof={ops_asof})")
    
    # If summary_data is still the raw response with error, return empty dict for safety
    if "error" in summary_data and summary_data["error"]:
        return True, {}
        
    return True, summary_data

def check_evidence(name, alias):
    url = f"{API_BASE}/api/evidence/resolve?ref={alias}"
    data = get_json(url)
    
    # Status Logic
    status_icon = f"{Colors.GRAY}?{Colors.RESET}"
    status_text = "UNKNOWN"
    details = ""
    
    # Check for actual error (transport or API error)
    if "error" in data and data["error"]:
        status_icon = f"{Colors.RED}X{Colors.RESET}"
        status_text = f"API FAIL ({data['error']})"
    else:
        # API returns Envelope (EVIDENCE_VIEW_V1)
        # Structure: { "status": "ready", "rows": [ { "data": { ... } } ] }
        api_status = data.get("status", "UNKNOWN")
        
        if api_status == "ready":
            rows = data.get("rows", [])
            if not rows:
                status_icon = f"{Colors.GRAY}?{Colors.RESET}"
                status_text = "EMPTY"
                details = "No rows returned"
            else:
                # Success path
                content = rows[0].get("data", {})
                
                # --- Specific Checks per Type ---
                
                # 1. Spike / Holding (Watchers)
                if "spike" in alias or "holding" in alias:
                    exec_res = content.get("execution_result", "UNKNOWN")
                    exec_reason = content.get("execution_reason", "")
                    
                    if exec_res == "SUCCESS":
                        status_icon = f"{Colors.GREEN}●{Colors.RESET}"
                        status_text = "Active"
                    else:
                        status_icon = f"{Colors.RED}●{Colors.RESET}"
                        status_text = exec_res
                    
                    details = f"Reason={exec_reason}"
                    if "spike" in alias:
                        # Safety: alerts_count might be missing or None
                        details += f", Alerts={content.get('alerts_count', 0)}"
                    if "holding" in alias:
                        details += f", Alerts={content.get('alerts_generated', 0)}"
                    
                    # Delivery check
                    delivery = content.get("delivery_actual", "NONE")
                    if delivery != "NONE":
                         details += f", Sent={delivery}"

                # 2. Daily Status
                elif "daily_status" in alias:
                    status_icon = f"{Colors.GREEN}●{Colors.RESET}"
                    status_text = "Generated"
                    delivery = content.get("delivery_actual", "NONE")
                    details = f"Delivery={delivery}"
                    if delivery == "TELEGRAM":
                        details = f"{Colors.CYAN}{details}{Colors.RESET}"

                # 3. Contract 5 (Human/AI)
                elif "report" in alias:
                    # Parse status and asof
                    c5_status = "UNKNOWN"
                    c5_asof = "?"
                    
                    if "human" in alias:
                        # Human Schema: headline.status_badge
                        c5_status = content.get("headline", {}).get("status_badge", "MISSING_BADGE")
                        c5_asof = content.get("asof", content.get("generated_at", "?"))
                    elif "ai" in alias:
                        # AI Schema: status
                        c5_status = content.get("status", "MISSING_STATUS")
                        c5_asof = content.get("asof", content.get("generated_at", "?"))

                    # Stale Check (7 days)
                    is_stale = False
                    try:
                        if c5_asof and c5_asof != "?" and len(c5_asof) > 10:
                            # Handle Z for standard isoformat
                            dt_str = c5_asof.replace("Z", "+00:00")
                            dt = datetime.fromisoformat(dt_str)
                            
                            # Compare with aware now if dt is aware
                            if dt.tzinfo:
                                from datetime import timezone
                                now = datetime.now(timezone.utc)
                            else:
                                now = datetime.now()
                            
                            delta = now - dt
                            if delta.days >= 7:
                                is_stale = True
                    except Exception:
                        pass # Ignore date parse errors

                    # Display Logic
                    status_icon = f"{Colors.GREEN}●{Colors.RESET}"
                    status_text = c5_status
                    
                    if is_stale:
                        status_text += "(STALE)"
                        status_icon = f"{Colors.YELLOW}●{Colors.RESET}"
                    
                    details = f"asof={c5_asof}"
        
    # Print Row
    # Format: [Icon] Name  | Status | Details
    print(f"  {status_icon} {name:<15} | {status_text:<16} | {details}")

def sanitize_detail(text):
    """P89: Strict Sanitization for Dashboard (1 line, escape quotes, 120 chars)"""
    if not text:
        return ""
    # Remove newlines/CR, escape quotes
    safe = str(text).replace("\n", " ").replace("\r", "").replace('"', "'").strip()
    # Truncate
    if len(safe) > 120:
        safe = safe[:117] + "..."
    return safe

def check_bundle_ssot(name, summary_data):
    # P80 SSOT: Use Ops Summary's strategy_bundle section
    bundle_data = summary_data.get("strategy_bundle", {})
    
    status_icon = f"{Colors.GRAY}?{Colors.RESET}"
    status_text = "UNKNOWN"
    details = ""
    
    if not bundle_data:
        status_icon = f"{Colors.RED}X{Colors.RESET}"
        status_text = "MISSING"
        details = "Ops Summary missing bundle info"
    else:
        present = bundle_data.get("present", False)
        stale = bundle_data.get("stale", False)
        stale_reason = bundle_data.get("stale_reason", "")
        created_at = bundle_data.get("created_at", "?")
        
        if not present:
             status_icon = f"{Colors.RED}X{Colors.RESET}"
             status_text = "MISSING"
             details = "No bundle present"
        elif stale:
             status_icon = f"{Colors.YELLOW}●{Colors.RESET}"
             status_text = "STALE"
             details = stale_reason or "Bundle is stale"
        else:
             status_icon = f"{Colors.GREEN}●{Colors.RESET}"
             status_text = "FRESH"
             details = f"created={created_at}"

    print(f"  {status_icon} {name:<15} | {status_text:<16} | {details}")


def fetch_order_plan_data():
    """P89: Fetch Order Plan SSOT"""
    url = f"{API_BASE}/api/order_plan/latest"
    # P89: Short timeout for dashboard responsiveness
    try:
        with urllib.request.urlopen(url, timeout=1.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                # Unwrap rows if present
                if "rows" in data:
                    return data["rows"][0] if data["rows"] else {}
                return data
    except Exception:
        return None
    return None

def print_order_plan_line(op_data):
    """P89: Strict Format Order Plan Line"""
    # Format: ● Order Plan | <STATUS> | Reason=<ENUM> | detail="<...>"
    
    status_icon = f"{Colors.RED}X{Colors.RESET}"
    status_text = "ERROR"
    reason_enum = "DETAIL_SOURCE_UNAVAILABLE"
    detail_raw = "API unreachable"
    
    if op_data is not None:
        if not op_data:
            # Empty dict means file likely empty or parsing fail but no exception match
            status_text = "ERROR"
            reason_enum = "EMPTY_DATA"
            detail_raw = "Empty response"
        else:
            decision = op_data.get("decision", "")
            raw_reason = op_data.get("reason", "")
            # P81: Extract ENUM
            reason_enum = raw_reason.split(":")[0].strip() if raw_reason else ""
            detail_raw = op_data.get("reason_detail", "")
            
            if not decision:
                status_text = "ERROR"
                reason_enum = "MISSING_DECISION"
                detail_raw = "Missing decision field"
            elif decision == "BLOCKED":
                status_icon = f"{Colors.RED}●{Colors.RESET}"
                status_text = "BLOCKED"
                if not detail_raw: detail_raw = "MISSING_DETAIL"
            elif decision == "COMPLETED":
                if reason_enum.startswith("NO_ACTION_"):
                    status_icon = f"{Colors.GREEN}●{Colors.RESET}"
                    status_text = "NO_ACTION"
                else:
                    status_icon = f"{Colors.GREEN}●{Colors.RESET}"
                    status_text = "OK"
            elif decision in ("GENERATED", "OK"):
                status_icon = f"{Colors.GREEN}●{Colors.RESET}"
                status_text = "OK"
            else:
                status_icon = f"{Colors.YELLOW}●{Colors.RESET}"
                status_text = decision
    
    # Sanitize Detail
    detail_safe = sanitize_detail(detail_raw)
    
    # Construct Line
    line = f"  {status_icon} {'Order Plan':<15} | {status_text:<16} | Reason={reason_enum} detail=\"{detail_safe}\""
    print(line)
    
    return status_text, reason_enum, detail_safe # Return for Root Cause if needed (though Root Cause calculated separately usually)

def print_root_cause(summary_data, op_data):
    """P89: Root Cause Display (Single Decision Tree)"""
    # Priority: Bundle Stale > Order Plan BLOCKED > Ops != OK > OK
    
    rc_enum = "UNMAPPED_CASE"
    rc_detail = ""
    is_failure = False
    
    # 1. Bundle Stale
    bundle = summary_data.get("strategy_bundle", {})
    if bundle.get("stale") is True:
        rc_enum = "BUNDLE_STALE_WARN"
        rc_detail = bundle.get("stale_reason", "") or "Strategy bundle is stale"
        is_failure = True
        
    # 2. Order Plan BLOCKED (if not stale)
    elif not is_failure and op_data:
        decision = op_data.get("decision", "")
        if decision == "BLOCKED":
            raw_reason = op_data.get("reason", "")
            reason_code = raw_reason.split(":")[0].strip() if raw_reason else "UNKNOWN"
            
            # Check for stale wrapper
            if reason_code in ("RECO_BUNDLE_STALE", "BUNDLE_STALE"):
                rc_enum = "BUNDLE_STALE_WARN"
                rc_detail = "Blocked due to stale bundle"
            elif reason_code.startswith("ORDER_PLAN_"):
                rc_enum = reason_code
                rc_detail = op_data.get("reason_detail", "") or "MISSING_DETAIL"
            else:
                rc_enum = f"ORDER_PLAN_{reason_code}"
                rc_detail = op_data.get("reason_detail", "") or "MISSING_DETAIL"
            is_failure = True
            
    # 3. Reco / Cycle (Usually covered by Order Plan, but check Ops Summary Reco)
    # Check "reco" block in summary
    if not is_failure:
        reco = summary_data.get("reco", {})
        reco_dec = reco.get("decision", "")
        if reco_dec == "EMPTY_RECO":
             rc_enum = "EMPTY_RECO"
             rc_detail = reco.get("reason_detail", "") or "MISSING_DETAIL"
             is_failure = True

    # 4. Ops Status
    if not is_failure:
        # Check overall status
        ops_status = summary_data.get("overall_status", "UNKNOWN") # or ops?
        # check_backend prints ops_status from first_row["overall_status"]
        if ops_status not in ("OK", "WARN"): # WARN is usually acceptable or handled elsewhere? P89 says Ops != OK
             # Wait, WARN might be Stale Bundle. If handled above, fine.
             # If explicit error:
             rc_enum = f"OPS_{ops_status}"
             rc_detail = summary_data.get("ops_summary", {}).get("message", "")
             is_failure = ops_status != "OK"

    # 5. OK
    if not is_failure:
        rc_enum = "OK"
        rc_detail = ""

    # Print
    detail_str = f' detail="{sanitize_detail(rc_detail)}"' if rc_detail else ""
    color = Colors.RED if is_failure and rc_enum != "OK" else Colors.GREEN
    print(f"{Colors.BOLD}Root Cause: {color}{rc_enum}{Colors.RESET}{detail_str}\n")


def main():
    print_header()
    
    # 1. Fetch Data
    success, summary_data = check_backend()
    if not success:
        print(f"\n{Colors.RED}CRITICAL: Backend is unreachable.{Colors.RESET}")
        return

    op_data = fetch_order_plan_data()

    # 2. Print Root Cause (P89 High Visibility)
    print_root_cause(summary_data, op_data)

    # 3. Print Sections
    print(f"{Colors.BOLD}[Strategy Bundle]{Colors.RESET}")
    check_bundle_ssot("Strategy Bundle", summary_data)
    
    # Order Plan Line (Always)
    print_order_plan_line(op_data)

    print(f"\n{Colors.BOLD}[Watcher Status]{Colors.RESET}")
    check_evidence("Spike Watch", "guard_spike_latest")
    check_evidence("Holding Watch", "guard_holding_latest")

    print(f"\n{Colors.BOLD}[Contract 5 Status]{Colors.RESET}")
    check_evidence("Human Report", "guard_report_human_latest")
    check_evidence("AI Report",    "guard_report_ai_latest")

    print(f"\n{Colors.BOLD}[Daily Operations]{Colors.RESET}")
    check_evidence("Daily Status", "guard_daily_status_latest")
    
    print("")

if __name__ == "__main__":
    main()
