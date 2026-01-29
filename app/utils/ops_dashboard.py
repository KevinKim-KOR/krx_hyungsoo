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
        return False

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

    # If we got this far, the Backend is ONLINE.
    print(f"  {Colors.GREEN}● ONLINE{Colors.RESET} (OpsStatus: {ops_status}, Msg: asof={ops_asof})")
    return True

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

def check_bundle_api(name):
    # SPoT: Check /api/strategy_bundle/latest
    url = f"{API_BASE}/api/strategy_bundle/latest"
    data = get_json(url)
    
    status_icon = f"{Colors.GRAY}?{Colors.RESET}"
    status_text = "UNKNOWN"
    details = ""
    
    if "error" in data and data["error"]:
        status_icon = f"{Colors.RED}X{Colors.RESET}"
        status_text = "API FAIL"
        details = str(data["error"])
    else:
        # API returns wrapped response with 'summary' key
        if "summary" in data:
            data = data["summary"]

        # Expected: present, decision, created_at, stale, stale_reason
        present = data.get("present", False)
        decision = data.get("decision", "UNKNOWN")

        created_at = data.get("created_at", "?")
        stale = data.get("stale", False)
        stale_reason = data.get("stale_reason", "")
        
        # SPoT Priority: FAIL > NO_BUNDLE > WARN > STALE > FRESH
        if decision == "NO_BUNDLE":
             status_icon = f"{Colors.RED}X{Colors.RESET}"
             status_text = "MISSING"
             details = "No bundle present"
        elif decision == "FAIL":
             status_icon = f"{Colors.RED}●{Colors.RESET}"
             status_text = "FAIL"
             issues = data.get("issues", [])
             details = str(issues[0]) if issues else "Validation Failed"
        elif not present:
             # Fallback if present is False but decision isn't NO_BUNDLE or FAIL (unlikely)
             status_icon = f"{Colors.RED}X{Colors.RESET}"
             status_text = f"MISSING ({decision})"
             details = "Bundle present=False"
        else:
             # Bundle is present
             if stale:
                status_icon = f"{Colors.YELLOW}●{Colors.RESET}"
                status_text = "STALE"
                details = stale_reason or "Bundle is stale"
             elif decision == "WARN":
                status_icon = f"{Colors.YELLOW}●{Colors.RESET}"
                status_text = "WARN"
                warnings = data.get("warnings", [])
                details = str(warnings[0]) if warnings else "Warnings present"
             else:
                status_icon = f"{Colors.GREEN}●{Colors.RESET}"
                status_text = "FRESH"
                
                # Calculate age just for display
                age_str = ""
                try:
                    dt_str = created_at.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(dt_str)
                    if dt.tzinfo:
                         from datetime import timezone
                         now = datetime.now(timezone.utc)
                    else:
                         now = datetime.now()
                    diff = now - dt
                    hours = diff.total_seconds() / 3600
                    days = diff.days
                    age_str = f"{int(hours)}h" if days < 1 else f"{days}d"
                except:
                    pass
                details = f"age={age_str}"


    print(f"  {status_icon} {name:<15} | {status_text:<16} | {details}")


def main():
    print_header()
    
    if not check_backend():
        print(f"\n{Colors.RED}CRITICAL: Backend is unreachable. Check 'sudo systemctl status krx-backend'.{Colors.RESET}")
        return

    print(f"\n{Colors.BOLD}[Strategy Bundle]{Colors.RESET}")
    # SPoT: Use API status directly
    check_bundle_api("Strategy Bundle")

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
