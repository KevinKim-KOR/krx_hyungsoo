import json
import sys
from pathlib import Path
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
import pandas as pd

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).parent.parent
OUTPUT_PATH = BASE_DIR / "reports" / "tuning" / "gatekeeper_decision_latest.json"
REPORTS_DIR = BASE_DIR / "reports"
OUTPUT_DATE_PATH = REPORTS_DIR / "tuning" / f"gatekeeper_decision_{datetime.now(KST).strftime('%Y%m%d')}.json"

sys.path.append(str(BASE_DIR))

# Schema Constants
SCHEMA_ID = "GATEKEEPER_DECISION_V3"
SCHEMA_VERSION = "3.0.0"

# Contract 2: Decision Order
DECISION_ORDER = ["ERROR", "REJECT", "HOLD", "PROMOTE"]

def normalize_stop_loss(sl_dict):
    """Normalize BP to PCT"""
    val = sl_dict.get("value", 0.0)
    unit = sl_dict.get("unit", "PCT")
    
    if unit == "BP":
        return {"value": val / 100.0, "unit": "PCT"}
    elif unit == "PCT":
        return {"value": val, "unit": "PCT"}
    else:
        return {"value": val, "unit": "UNKNOWN"} # Should trigger integrity error

def run_gatekeeper_v3():
    # 1. LOAD CONFIG (Baseline)
    integrity_ok = True
    missing_keys = []
    
    try:
        from config.production_config import PROD_STRATEGY_CONFIG
        baseline_params = PROD_STRATEGY_CONFIG
    except ImportError:
        baseline_params = {}
        integrity_ok = False
        missing_keys.append("production_config.py")

    # Required Keys Check
    required_keys = ["ma_short_period", "regime_ma_long", "adx_threshold", "stop_loss"]
    for k in required_keys:
        if k not in baseline_params:
            missing_keys.append(k)
            integrity_ok = False

    # 2. MOCK CANDIDATE (For demonstration/validation per contract)
    # In real flow, this would come from an optimization report
    candidate_params = {
        "ma_short_period": 120, # Drifted
        "regime_ma_long": 120,
        "adx_threshold": 17.5,
        "stop_loss": {"value": 1200.0, "unit": "BP"} # Needs norm
    }
    
    # 3. NORMALIZE
    cand_sl_norm = normalize_stop_loss(candidate_params["stop_loss"])
    
    # 4. CHECKS LOGIC
    checks = []
    
    # HC1: Param Drift
    # Mock result: Drift > Limit
    # For demo: ma_short 60 -> 120 (100% change, Limit 25%)
    hc1_passed = False 
    checks.append({
        "check_id": "HC1_PARAM_DRIFT_LIMIT",
        "severity": "HARD",
        "passed": hc1_passed,
        "metrics": {
            "limits": {"ma_short_period_max_change_pct": 0.25},
            "observed": {"ma_short_period_change_pct": 1.0}
        },
        "message_ko": "파라미터 변동폭(100%) 허용 범위(25%) 초과"
    })
    
    # HC2: Similarity
    hc2_passed = False
    sim_score = 0.58
    checks.append({
        "check_id": "HC2_SIMILARITY_MIN",
        "severity": "HARD",
        "passed": hc2_passed,
        "metrics": {"similarity": sim_score, "min_required": 0.7},
        "message_ko": "유사성 부족(과적합 위험)"
    })
    
    # HC3: Risk
    checks.append({
        "check_id": "HC3_RISK_BOUNDS",
        "severity": "HARD",
        "passed": True,
        "metrics": {"mdd_pct": 9.5, "mdd_max": 15.0},
        "message_ko": "리스크 기준 통과"
    })
    
    # HC4: Trade Sanity
    checks.append({
        "check_id": "HC4_TRADE_SANITY",
        "severity": "HARD",
        "passed": False,
        "metrics": {"ratio": 0.0, "min": 0.5, "max": 2.0},
        "message_ko": "거래건수 비정상(0건)"
    })

    # SC1 & SC2 (Soft Checks)
    checks.append({"check_id": "SC1_RETURN_IMPROVEMENT", "severity": "SOFT", "passed": False, "metrics": {}, "message_ko": "수익 개선폭 미달"})
    checks.append({"check_id": "SC2_EXPOSURE_NORMALIZATION", "severity": "SOFT", "passed": False, "metrics": {}, "message_ko": "노출도 정상 범위 이탈"})

    # 5. DECISION LOGIC
    decision = "PROMOTE"
    reason = "All Checks Passed"
    action = "배포 승인"
    
    if not integrity_ok:
        decision = "ERROR"
        reason = "Integrity Check Failed"
        action = "설정 파일 복구 필요"
    else:
        hard_fails = [c for c in checks if c['severity'] == 'HARD' and not c['passed']]
        soft_fails = [c for c in checks if c['severity'] == 'SOFT' and not c['passed']]
        
        if hard_fails:
            decision = "REJECT"
            reason = f"Hard Check Failed ({hard_fails[0]['check_id']})"
            action = "후보 폐기 및 파라미터 재조정"
        elif soft_fails:
            decision = "HOLD"
            reason = "Soft Check Failed"
            action = "수동 검토 필요"

    # 6. CONSTRUCT REPORT (Contract 2 Structure)
    report = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "asof": datetime.now(KST).strftime("%Y-%m-%d"),
            "baseline_config_hash8": "current",
            "candidate_id": "mock_candidate_v3",
            "candidate_source": "internal_mock",
            "policy": {
                "decision_order": DECISION_ORDER
            }
        },
        "baseline": {
            "params": baseline_params
        },
        "candidate": {
            "params": candidate_params,
            "normalized": {
                "stop_loss": cand_sl_norm
            },
            "scorecard": {
                "period": {"from": "2024-01-01", "to": "2024-12-31"},
                "return_pct": 0.0,
                "mdd_pct": 0.0,
                "sharpe": 0.0,
                "trades": 0,
                "exposure": 0.0,
                "baseline_return_pct": 0.0,
                "baseline_trades": 0
            }
        },
        "similarity": {
            "method": "weighted_normalized_distance",
            "weights": {"ma_short": 0.25}, # Simplified for demo
            "normalization": {"ma_short": 200},
            "score_0_1": sim_score,
            "min_required": 0.7,
            "passed": hc2_passed
        },
        "checks": checks,
        "integrity": {
            "ok": integrity_ok,
            "config_missing_keys": missing_keys,
            "notes_ko": "필수키 누락 발생" if not integrity_ok else "정상"
        },
        "decision": {
            "result": decision,
            "reason_ko": reason,
            "recommended_action_ko": action
        },
        "policy_matrix": {
            "if_integrity_fail": "ERROR",
            "if_any_hard_fail": "REJECT",
            "else_if_any_soft_fail": "HOLD",
            "else": "PROMOTE"
        }
    }

    # Save
    OUTPUT_PATH.parent.mkdir(exist_ok=True, parents=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    # Alias to Date
    with open(OUTPUT_DATE_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Success: Generated {OUTPUT_PATH}")

if __name__ == "__main__":
    run_gatekeeper_v3()
