import sys
import json

def main():
    try:
        # Read from stdin
        input_str = sys.stdin.read()
        if not input_str or not input_str.strip():
            print("DAILY_SUMMARY Reason=EMPTY_INPUT")
            return

        try:
            d = json.loads(input_str)
        except json.JSONDecodeError:
            print("DAILY_SUMMARY Reason=INVALID_JSON")
            return
        
        # Check error (detail)
        if "detail" in d:
             msg = str(d.get('detail', 'unknown')).replace(" ", "_")
             print(f"DAILY_SUMMARY Reason=API_ERROR detail={msg}")
             return

        # Unwrap "data" if present (FastAPI common wrapper)
        if "data" in d and isinstance(d["data"], dict):
            d = d["data"]
        
        # Unwrap "rows" if present (Common list response wrapper)
        if "rows" in d and isinstance(d["rows"], list) and len(d["rows"]) > 0:
            d = d["rows"][0]



        # Parsing logic (Robust)
        ops = d.get("ops_status")
        if not ops:
            ops = "MISSING_OPS"
            # Debug: Print keys if ops_status is missing
            # But we must output in DAILY_SUMMARY format for grep to work (partial)
            # We'll rely on the default printing but add debug info if possible
            # Actually, let's just use the defaults but maybe add a debug print to stderr?
            # Script captures stdout. usage: ... | python script.py | sed ...
            print(f"DEBUG: Available keys: {list(d.keys())}", file=sys.stderr)

        live = d.get("live_status", {}) or {}
        live_res = f"{live.get('result','MISSING_RESULT')}/{live.get('decision','MISSING_DECISION')}"
        
        bundle = d.get("bundle", {}) or {}
        bundle_stale = str(bundle.get("stale", "missing_stale")).lower()
        
        reco = d.get("reco", {}) or {}
        reco_decision = reco.get("decision", "MISSING_RECO")
        
        order = d.get("order_plan", {}) or {}
        op_decision = order.get("decision", "MISSING_OP")
        
        risks = d.get("top_risks", []) or []
        
        # P81-FIX v2.2: Filter ORDER_PLAN_* risks when order_plan=SKIPPED
        if op_decision == "SKIPPED":
            risks = [r for r in risks if not r.startswith("ORDER_PLAN_")]
        
        # P83-FIX: Strict single risk when bundle_stale (root cause)
        # When stale, ALL other risks are downstream effects - show only root cause
        if bundle_stale == "true":
            risks = ["BUNDLE_STALE_WARN"]
            
        risks_str = str(risks).replace(" ", "")

        # Reason Logic (P83: Priority Reordering for Actionable WHY)
        # Priority: GIT_PULL_FAILED > BUNDLE_STALE_WARN > ORDER_PLAN_* > EMPTY_RECO > OK
        reason = "UNMAPPED_CASE"  # Default fallback - never UNKNOWN
        
        # P87-FIX: SSOT Logic (Re-verified)
        if op_decision == "BLOCKED":
            op_reason = order.get("reason", "")
            op_reason_code = op_reason.split(":")[0].strip() if op_reason else "UNKNOWN"
            
            # P86: SSOT Logic (Stale check)
            if op_reason_code in ("RECO_BUNDLE_STALE", "BUNDLE_STALE"):
                # Usually caught by bundle_stale==true, but if not..
                pass 
            elif op_reason_code and op_reason_code != "BLOCKED":
                if op_reason_code.startswith("ORDER_PLAN_"):
                    pass # reason already set likely
                else:
                    pass
        
        # P87-FIX2: SSOT Priority & Detail Logic (Strict)
        # Priority: Bundle Stale > Order Plan Blocked > Reco Empty > Ops Warning > OK
        
        reason = "UNMAPPED_CASE"
        detail_msg = ""
        
        # 1. Bundle Stale (Root Cause)
        if bundle_stale == "true":
            reason = "BUNDLE_STALE_WARN"
            # Try to get stale reason if available, else standard msg
            # Check if bundle dict has 'stale_reason' or 'summary.stale_reason'
            # Assuming flat dict or summary dict. Safe get.
            detail_msg = bundle.get("stale_reason", "") or bundle.get("summary", {}).get("stale_reason", "")
            if not detail_msg: detail_msg = "Strategy bundle is stale"
            
        # 2. Order Plan Blocked (if not caused by stale)
        elif op_decision == "BLOCKED":
            op_reason = order.get("reason", "")
            op_reason_code = op_reason.split(":")[0].strip() if op_reason else "UNKNOWN"
            detail_msg = order.get("reason_detail", "")
            
            # Special Handling for stale-induced block (Double check)
            if op_reason_code in ("RECO_BUNDLE_STALE", "BUNDLE_STALE"):
                reason = "BUNDLE_STALE_WARN"
                if not detail_msg: detail_msg = "Blocked due to stale bundle"
            elif op_reason_code and op_reason_code != "BLOCKED":
                 if op_reason_code.startswith("ORDER_PLAN_"):
                     reason = op_reason_code
                 else:
                     reason = f"ORDER_PLAN_{op_reason_code}"
            else:
                 reason = "ORDER_PLAN_BLOCKED"
            
            # P87-FIX2: Fallback for missing detail in blocking case
            if not detail_msg:
                 detail_msg = "MISSING_DETAIL"

        # 3. NO_ACTION Special Case
        elif op_decision == "COMPLETED" and order.get("reason", "").startswith("NO_ACTION_"):
            reason = order.get("reason")
            detail_msg = order.get("reason_detail", "")

        # 4. Reco Empty
        elif reco_decision == "EMPTY_RECO":
            reason = "RECO_EMPTY_RECO" # Enforce ENUM consistency (or just EMPTY_RECO if that's the enum)
            # P87: Use existing ENUM 'EMPTY_RECO' if that is the standard, strictly ENUM-only
            if not reason.startswith("RECO_") and reason != "EMPTY_RECO":
                 reason = "EMPTY_RECO" 
            elif reason == "RECO_EMPTY_RECO":
                 pass # OK
            else:
                 reason = "EMPTY_RECO" # Fallback to standard short enum
            
            detail_msg = reco.get("reason_detail", "")
            if not detail_msg: detail_msg = "MISSING_DETAIL"

        # 5. Ops Warning/Error
        elif ops != "OK" and ops != "WARN":
            reason = f"OPS_{ops}"
            detail_msg = d.get("ops_summary", {}).get("message", "") # fallback

        # 6. OK
        else:
            reason = "OK"
            detail_msg = ""

        # Safe string for log (remove newlines, truncate if too long)
        # P87-FIX2: Strict Sanitize
        detail_safe = str(detail_msg).replace("\n", " ").replace("\r", "").replace('"', "'").strip()[:300]

        # Print Standard Summary to stdout (for daily_summary.latest)
        summary_line = f"DAILY_SUMMARY ops={ops} live={live_res} bundle_stale={bundle_stale} reco={reco_decision} order_plan={op_decision} Reason={reason} risks={risks_str}"
        print(summary_line)

        # P87-FIX: Write Detail Log to File (Side Effect) - Operator Recovery
        try:
             with open("logs/daily_summary.detail.latest", "w", encoding="utf-8") as f:
                  f.write(f'Reason={reason} detail="{detail_safe}"\n')
        except Exception:
             pass # Fail silent on side-effect log gen


    except Exception as e:
        print(f"DAILY_SUMMARY Reason=PARSE_ERROR error={str(e)}")

if __name__ == "__main__":
    main()
