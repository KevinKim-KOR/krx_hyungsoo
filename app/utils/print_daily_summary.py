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


        # P99-FIX2: Parsing logic (5-point fix)
        
        # (A) ops: overall_status 우선
        ops = d.get("overall_status") or d.get("ops_status") or "WARN"

        # (B) live: push.last_send_decision 기준
        push = d.get("push") or {}
        live_decision = push.get("last_send_decision") or "COMPLETED"
        live_res = f"OK/{live_decision}"
        
        # (C) bundle + stale: strategy_bundle 우선 + stale_reason 보정
        bundle = d.get("strategy_bundle") or d.get("bundle") or {}
        stale = bundle.get("stale")
        if stale is None:
            stale = bool(bundle.get("stale_reason"))
        bundle_stale = "true" if stale else "false"
        
        # (D) reco: GENERATED → OK 정규화
        reco = d.get("reco") or {}
        reco_decision = reco.get("decision") or "COMPLETED"
        if reco_decision == "GENERATED":
            reco_decision = "OK"
        
        order = d.get("order_plan", {}) or {}
        op_decision = order.get("decision", "MISSING_OP")

        c5 = d.get("contract5", {}) or {}
        c5_decision = c5.get("decision", "MISSING_C5")
        
        # (E) risks: code만 추출 (dict에서 code 필드만)
        top_risks_raw = d.get("top_risks") or []
        risks = [r.get("code") for r in top_risks_raw if isinstance(r, dict) and r.get("code")]
        
        # P81-FIX v2.2: Filter ORDER_PLAN_* risks when order_plan=SKIPPED
        if op_decision == "SKIPPED":
            risks = [r for r in risks if not r.startswith("ORDER_PLAN_")]
        
        # P83-FIX: Strict single risk when bundle_stale (root cause)
        if bundle_stale == "true":
            risks = ["BUNDLE_STALE_WARN"]
            
        risks_str = str(risks).replace(" ", "")

        # Reason Logic (P83: Priority Reordering for Actionable WHY)
        # Priority: GIT_PULL_FAILED > BUNDLE_STALE_WARN > ORDER_PLAN_* > EMPTY_RECO > OK
        reason = "UNMAPPED_CASE"  # Default fallback - never UNKNOWN
        
        # P88-FIX: Single Decision Tree Logic
        # Priority: Bundle Stale > Order Plan Blocked > Reco Empty > Ops Warning > OK
        
        reason = "UNMAPPED_CASE"
        
        # 1. Reason Determination
        if bundle_stale == "true":
            reason = "BUNDLE_STALE_WARN"
        
        elif op_decision == "BLOCKED":
            op_reason = order.get("reason", "")
            if not op_reason:
                reason = "ORDER_PLAN_BLOCKED"
            else:
                op_reason_code = op_reason.split(":")[0].strip()
                # Check for wrapped stale/reco errors in Order Plan
                if op_reason_code in ("RECO_BUNDLE_STALE", "BUNDLE_STALE"):
                    reason = "BUNDLE_STALE_WARN"
                elif op_reason_code.startswith("ORDER_PLAN_"):
                    reason = op_reason_code
                else:
                    reason = f"ORDER_PLAN_{op_reason_code}"

        elif op_decision == "COMPLETED" and order.get("reason", "").startswith("NO_ACTION_"):
            reason = order.get("reason")

        elif reco_decision == "EMPTY_RECO":
            reason = "EMPTY_RECO" # or RECO_EMPTY_RECO depending on ENUM policy. 
            # User accepted "EMPTY_RECO" in previous P87 contexts. Using standard.

        elif ops != "OK" and ops != "WARN":
            reason = f"OPS_{ops}"
            
        else:
            reason = "OK"

        # 2. Detail Extraction (SSOT based on Reason)
        detail_msg = ""
        
        if reason.startswith("ORDER_PLAN_") or reason.startswith("NO_ACTION_"):
            # SSOT: Order Plan cases MUST fetch from API
            try:
                import urllib.request
                # P88: Direct API Fetch with 1s timeout
                with urllib.request.urlopen("http://localhost:8000/api/order_plan/latest", timeout=1) as response:
                    if response.status == 200:
                        op_latest = json.loads(response.read().decode())
                        # Extract detail from rows (CheckResult) or root (Plan)
                        # API usually returns consistent format. "rows" for lists check, but latest plan is single object usually.
                        # However, previous P87 verification used `rows` assumption or root check.
                        # Let's check root `reason_detail` first (saved Plan), then `rows`.
                        detail_msg = op_latest.get("reason_detail", "")
                        if not detail_msg and "rows" in op_latest:
                             detail_msg = op_latest["rows"][0].get("reason_detail", "")
                        
                        if not detail_msg:
                            detail_msg = "MISSING_DETAIL"
                    else:
                        detail_msg = "DETAIL_SOURCE_UNAVAILABLE (HTTP Error)"
            except Exception:
                detail_msg = "DETAIL_SOURCE_UNAVAILABLE"

        elif reason == "BUNDLE_STALE_WARN":
             detail_msg = bundle.get("stale_reason", "") or bundle.get("summary", {}).get("stale_reason", "") or "Strategy bundle is stale"

        elif reason == "EMPTY_RECO" or reason.startswith("RECO_"):
             detail_msg = reco.get("reason_detail", "") or "MISSING_DETAIL"

        elif reason.startswith("OPS_"):
             detail_msg = d.get("ops_summary", {}).get("message", "")
        
        # 3. Sanitize
        # P88: Strict Sanitize (1 line, escape quotes, 240 chars)
        detail_safe = str(detail_msg).replace("\n", " ").replace("\r", "").replace('"', "'").strip()[:240]

        # 4. Output
        summary_line = f"DAILY_SUMMARY ops={ops} live={live_res} bundle_stale={bundle_stale} reco={reco_decision} order_plan={op_decision} c5={c5_decision} Reason={reason} risks={risks_str}"
        print(summary_line)

        # P87-FIX: Write Detail Log to File
        try:
             with open("logs/daily_summary.detail.latest", "w", encoding="utf-8") as f:
                  f.write(f'Reason={reason} detail="{detail_safe}"\n')
        except Exception:
             pass


    except Exception as e:
        print(f"DAILY_SUMMARY Reason=PARSE_ERROR error={str(e)}")

if __name__ == "__main__":
    main()
