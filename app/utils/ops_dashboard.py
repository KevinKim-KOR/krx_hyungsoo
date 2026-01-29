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
    # Use existing endpoint from main.py
    url = f"{API_BASE}/api/status"
    data = get_json(url)
    
    print(f"{Colors.BOLD}[Backend System]{Colors.RESET}")
    
    # Check for connection error (dictionary with "error" key from get_json exception handler)
    if "error" in data and data["error"]:
        print(f"  {Colors.RED}● DOWN{Colors.RESET} ({data['error']})")
        return False
    
    # Parse /api/status response
    # Schema: badge, message, date, version(maybe missing)
    badge = data.get("badge", "UNKNOWN")
    message = data.get("message", "")
    date = data.get("date", "?")
    
    # If we got this far, the Backend is ONLINE (HTTP 200).
    # The 'badge' just reflects the Daily Ops status.
    print(f"  {Colors.GREEN}● ONLINE{Colors.RESET} (OpsStatus: {badge}, Msg: {message})")
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
                    # Basic existence check
                    status_icon = f"{Colors.GREEN}●{Colors.RESET}"
                    status_text = "Ready"
                    # Try to get some meta checks if possible
                    if "human" in alias:
                        author = content.get("author", "Unknown")
                        details = f"Author={author}"
                    if "ai" in alias:
                        model = content.get("model", "Unknown")
                        details = f"Model={model}"
        
        else:
            status_icon = f"{Colors.RED}X{Colors.RESET}"
            status_text = f"{api_status}"
            if isinstance(data.get('error'), dict):
                details = data['error'].get('message', '')
            else:
                details = str(data.get('error', ''))

    # Print Row
    # Format: [Icon] Name  | Status | Details
    print(f"  {status_icon} {name:<15} | {status_text:<10} | {details}")

def main():
    print_header()
    
    if not check_backend():
        print(f"\n{Colors.RED}CRITICAL: Backend is unreachable. Check 'sudo systemctl status krx-backend'.{Colors.RESET}")
        return

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
