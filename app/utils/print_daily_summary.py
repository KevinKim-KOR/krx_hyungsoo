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
        
        # P106: SSOT Reason Logic (Use top_risks[0] as Root Cause)
        # Priority is already handled by generate_ops_summary.py stable sort
        if risks:
            reason = risks[0]
        else:
            reason = "OK"

        # P83-FIX: Strict single risk when bundle_stale (but P106 handles this via sort)
        # P106: If Bundle Stale is top risk, it will be Reason.
        # But we might want to ensure 'risks' list in output is consistent?
        # generate_ops_summary.py already handles sorting.
        # We just use it.
        
        risks_str = str(risks).replace(" ", "")

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

        elif reason.startswith("OPS_"):
             detail_msg = d.get("ops_summary", {}).get("message", "")

        else:
             # P106: All other cases (Bundle, Order, Reco) use the message logic already in generate_ops_summary
             # We can try to extract from top_risks if available.
             if risks and top_risks_raw:
                  # top_risks_raw is a list of dicts. We find the one matching 'reason' code.
                  # Since risks[0] is reason, top_risks_raw[0] should be it (sorted).
                  # Let's verify code matches first.
                  first_risk_dict = top_risks_raw[0]
                  if first_risk_dict.get("code") == reason:
                       detail_msg = first_risk_dict.get("message", "")
                  else:
                       # Fallback: find it
                       for r in top_risks_raw:
                            if r.get("code") == reason:
                                 detail_msg = r.get("message", "")
                                 break
        
        if not detail_msg:
             detail_msg = "Detail not available"
        
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

        # P115: Manual Loop Stage & Next Action
        manual_loop = d.get("manual_loop", {})
        ml_stage = manual_loop.get("stage", "UNKNOWN")
        ml_action = manual_loop.get("next_action", "NONE")
        
        print(f"MANUAL_LOOP Stage={ml_stage} Next={ml_action}")


    except Exception as e:
        print(f"DAILY_SUMMARY Reason=PARSE_ERROR error={str(e)}")

if __name__ == "__main__":
    main()
