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
        risks_str = str(risks).replace(" ", "")

        # Reason Logic (Strict Enum Priority)
        # Prioritize BLOCKERS
        if op_decision == "BLOCKED":
            reason = "ORDER_PLAN_BLOCKED"
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
