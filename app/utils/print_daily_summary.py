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
            
        risks_str = str(risks).replace(" ", "")

        # Reason Logic (Strict Enum Priority + P81 Namespace Rule)
        reason = "UNMAPPED_CASE"  # Default fallback - never UNKNOWN
        
        # Prioritize BLOCKERS
        if op_decision == "BLOCKED":
            op_reason = order.get("reason", "")
            if op_reason and op_reason != "BLOCKED":
                if op_reason.startswith("ORDER_PLAN_"):
                    reason = op_reason
                else:
                    reason = f"ORDER_PLAN_{op_reason}"
            else:
                reason = "ORDER_PLAN_BLOCKED"
                
        # P81: NO_ACTION flow (decision=COMPLETED but special reason)
        elif op_decision == "COMPLETED" and order.get("reason", "").startswith("NO_ACTION_"):
            reason = order.get("reason")
            
        elif reco_decision == "EMPTY_RECO":
            reason = "EMPTY_RECO"
        elif bundle_stale == "true":
            reason = "BUNDLE_STALE"
        elif ops != "OK" and ops != "WARN":
            # If ops is MISSING, reason becomes OPS_MISSING_OPS_STATUS
            reason = f"OPS_{ops}"
        else:
            reason = "OK"

        print(f"DAILY_SUMMARY ops={ops} live={live_res} bundle_stale={bundle_stale} reco={reco_decision} order_plan={op_decision} Reason={reason} risks={risks_str}")

    except Exception as e:
        print(f"DAILY_SUMMARY Reason=PARSE_ERROR error={str(e)}")

if __name__ == "__main__":
    main()
