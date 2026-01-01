import json
import sys
from pathlib import Path
from datetime import datetime

# --- CONFIGURATION (Contract C-R) ---
BASE_DIR = Path(__file__).parent.parent
REPORTS_DIR = BASE_DIR / "reports" / "phase_c"

# Inputs (Truth)
RECON_DAILY_PATH = REPORTS_DIR / "recon_daily.jsonl"
RECON_SUMMARY_PATH = REPORTS_DIR / "recon_summary.json"

# Outputs (Reports)
REPORT_HUMAN_PATH = REPORTS_DIR / "report_human_v1.json"
REPORT_AI_PATH = REPORTS_DIR / "report_ai_v1.json"

# Reason Mapping (Code -> Korean)
REASON_MAP = {
    "CHOP_BLOCK": "횡보장(Neutral)으로 판단되어 진입 제한되었습니다.",
    "BEAR_BLOCK": "하락장(Bear) 역배열이므로 진입이 금지됩니다.",
    "DATA_MISSING": "데이터가 부족하여 판단할 수 없습니다.",
    "NO_DATA": "데이터가 없습니다.",
    "NONE": "정상",
    "EXECUTED_SOT_OVERRIDE": "실제 체결(Leger)이 확인되어 로직을 Override하고 통과시켰습니다."
}

def load_recon_data():
    if not RECON_SUMMARY_PATH.exists() or not RECON_DAILY_PATH.exists():
        print("CRITICAL: Recon artifacts not found. Run 'tools/reconcile_phase_c.py' first.")
        sys.exit(1)
        
    with open(RECON_SUMMARY_PATH, "r", encoding="utf-8") as f:
        summary = json.load(f)
        
    daily_list = []
    with open(RECON_DAILY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                daily_list.append(json.loads(line))
                
    return summary, daily_list

def generate_human_report(summary, daily_list):
    """
    Generate UI-optimized report.
    Adheres to PHASE_C_REPORT_HUMAN_V1 schema.
    """
    # KPI Transformation
    # Recon has 'kpi_stats' { gate_open, chop_block ... }
    # Human report expects 'target_kpi' block? 
    # Let's match the UI expectation: headline.kpis_5
    
    kpis = summary.get("kpis", {})
    counts = summary.get("counts", {})
    
    # Alerts Transformation
    # Recon Integrity -> Human Alerts
    alerts = []
    
    # 1. Critical/Warning Days
    integrity = summary.get("integrity", {})
    for item in integrity.get("top_codes", []):
         code = item["code"]
         days = item["days"]
         severity = "CRITICAL" if "CRITICAL" in code or "MISSING" in code else "WARNING"
         
         msg = f"{days}일간 {code} 발생."
         if code == "IC_DATA_MISSING_WITH_EXECUTION":
             msg = "데이터(증거)가 없는 날짜에 체결이 발생했습니다. (Ledger Only)"
             
         alerts.append({
             "severity": severity,
             "code": code,
             "message_ko": msg,
             "details": {"days": days}
         })
         
    # 2. L1/L2 Delta (Always Info)
    delta = counts.get("L1_L2_delta", 0)
    if delta != 0:
        alerts.append({
            "severity": "INFO",
            "code": "TC_L1_L2_DELTA",
            "message_ko": "L1/L2 정의 차이로 인한 Delta는 정상입니다.",
            "details": {"delta": delta}
        })

    report = {
        "schema": "PHASE_C_REPORT_HUMAN_V1",
        "version": "1.1.0",
        "generated_at": datetime.now().isoformat() + "Z",
        "headline": {
            "kpis_5": {
                "gate_open_days": kpis.get("gate_open", 0),
                "chop_block_days": kpis.get("chop_block", 0),
                "bear_block_days": kpis.get("bear_block", 0),
                "executed_days": kpis.get("executed", 0),
                "no_data_days": kpis.get("no_data", 0)
            },
            "trade_count": {
                "policy_id": summary.get("trade_count_policy_id", "UNKNOWN"),
                "L1_actions_total": counts.get("L1_actions", 0),
                "L2_trades_total": counts.get("L2_trades", 0),
                "delta": delta
            }
        },
        "alerts": alerts,
        "refs": {
            "source": "RECON_PHASE_C"
        }
    }
    
    with open(REPORT_HUMAN_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Generated Human Report: {REPORT_HUMAN_PATH}")

def generate_ai_report(summary, daily_list):
    """
    Generate AI-optimized report.
    Adheres to PHASE_C_REPORT_AI_V1 schema.
    Focus on Feature Vectors and Logic Explanations.
    """
    vectors = []
    
    for row in daily_list:
        if row["evidence"]["status"] != "OK":
            continue
            
        vectors.append({
            "date": row["trade_date"],
            "features": [
                row["evidence"]["adx"],
                row["evidence"]["ma_short"],
                row["evidence"]["ma_long"]
            ],
            "label": {
                "regime": row["evidence"]["regime"],
                "gate": row["precheck"]["gate_decision"],
                "executed": int(row["execution"]["executed"])
            },
            "reason_ko": REASON_MAP.get(row["precheck"]["reason"], row["precheck"]["reason"])
        })
        
    report = {
        "schema": "PHASE_C_REPORT_AI_V1",
        "version": "1.0.0",
        "generated_at": datetime.now().isoformat() + "Z",
        "summary": summary,
        "dataset": {
            "count": len(vectors),
            "samples": vectors
        }
    }
    
    with open(REPORT_AI_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Generated AI Report: {REPORT_AI_PATH}")

def main():
    print(">>> Diagnosis Tool (Consumer) Starting...")
    summary, daily = load_recon_data()
    
    generate_human_report(summary, daily)
    generate_ai_report(summary, daily)
    
    print(">>> Diagnosis Reports Generated Successfully.")

if __name__ == "__main__":
    main()
