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
        
        # P83: Check bundle stale FIRST (root cause for downstream blocks)
        if bundle_stale == "true":
            reason = "BUNDLE_STALE_WARN"
            
        # Then check order_plan blockers (only if not stale-caused)
        elif op_decision == "BLOCKED":
            op_reason = order.get("reason", "")
            op_reason_code = op_reason.split(":")[0].strip() if op_reason else ""
            
            # P86: SSOT Logic
            # If blocked due to RECO_BUNDLE_STALE, surface as BUNDLE_STALE_WARN (handled by bundle_stale check above usually, but safe-guard)
            if op_reason_code in ("RECO_BUNDLE_STALE", "BUNDLE_STALE"):
                reason = "BUNDLE_STALE_WARN"
            elif op_reason_code and op_reason_code != "BLOCKED":
                # P86: Specific Reason Code (e.g. ORDER_PLAN_PORTFOLIO_CALC_ERROR)
                if op_reason_code.startswith("ORDER_PLAN_"):
                    reason = op_reason_code
                else:
                    reason = f"ORDER_PLAN_{op_reason_code}"
                
                # P86: Stack specific risk if not in top_risks (consistency check)
                # Note: risks list comes from ops_summary basically, but if we are parsing daily_summary 
                # (which is just a log line generator), we might need to be careful not to mutate raw input risks too much 
                # unless we are essentially re-deriving.
                # Here we just set the 'Reason' field of daily_summary log line.
            else:
                reason = "ORDER_PLAN_BLOCKED"
                
        # P81: NO_ACTION flow (decision=COMPLETED but special reason)
        elif op_decision == "COMPLETED" and order.get("reason", "").startswith("NO_ACTION_"):
            reason = order.get("reason")
            
        elif reco_decision == "EMPTY_RECO":
            reason = "EMPTY_RECO"
        if ops != "OK" and ops != "WARN":
            reason = f"OPS_{ops}"
        else:
            reason = "OK"

        # P87: Detail Logic (Operator Recovery)
        # Extract meaningful detail for the reason
        detail_msg = ""
        if "ORDER_PLAN" in reason:
            # Check Order Plan detail
             detail_msg = order.get("reason_detail", "")
        elif "BUNDLE_STALE" in reason:
             # Check Bundle Validation data
             pass # Already clear from reason usually, but can look at bundle status? 
             # Actually daily_ops.sh already prints age.
             pass
        
        # Fallback to generic detail or empty
        if not detail_msg:
             detail_msg = d.get("reco", {}).get("reason_detail", "") or d.get("detail", "")

        # Safe string for log
        detail_safe = str(detail_msg).replace("\n", " ")

        # Print Standard Summary to stdout (for daily_summary.latest)
        summary_line = f"DAILY_SUMMARY ops={ops} live={live_res} bundle_stale={bundle_stale} reco={reco_decision} order_plan={op_decision} Reason={reason} risks={risks_str}"
        print(summary_line)

        # P87: Write Detail Log to File (Side Effect)
        # Reason=<ENUM> detail="<msg>"
        try:
             with open("logs/daily_summary.detail.latest", "w", encoding="utf-8") as f:
                  f.write(f'Reason={reason} detail="{detail_safe}"\n')
        except Exception:
             pass # Fail silent on side-effect log gen


    except Exception as e:
        print(f"DAILY_SUMMARY Reason=PARSE_ERROR error={str(e)}")

if __name__ == "__main__":
    main()
