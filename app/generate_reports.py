# -*- coding: utf-8 -*-
"""
app/generate_reports.py
Contract 5 Reports Generator (C-P.9.1)

규칙:
- pandas 없이 동작
- recon_summary.json 없어도 기본 리포트 생성
- asof 필드 갱신으로 변경 증거 확보
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))

# Paths
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "reports" / "phase_c" / "latest"
SUMMARY_PATH = OUTPUT_DIR / "recon_summary.json"
DAILY_PATH = OUTPUT_DIR / "recon_daily.jsonl"
HUMAN_REPORT_PATH = OUTPUT_DIR / "report_human.json"
AI_REPORT_PATH = OUTPUT_DIR / "report_ai.json"


def get_default_summary() -> dict:
    """Get default summary when recon_summary.json is missing"""
    return {
        "schema": "RECON_SUMMARY_V1",
        "asof": datetime.now(KST).isoformat(),
        "status": "bootstrap",
        "period": {"from": "2024-01-01", "to": "2025-12-31"},
        "counts": {"L1_actions": 0, "L2_trades": 0, "L1_L2_delta": 0},
        "integrity": {"critical_days": 0, "warning_days": 0, "info_days": 0, "top_codes": []},
        "kpis": {"gate_open": 0, "executed": 0, "chop_block": 0, "bear_block": 0, "no_data": 0},
        "provenance": {"sources": []},
        "notes": "Bootstrap default - no recon data available"
    }


def main():
    print(">>> Generating Contract 5 Reports (Human/AI)...")
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load or create default summary
    if SUMMARY_PATH.exists():
        print(f"Loading recon_summary.json...")
        with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
            summary = json.load(f)
    else:
        print("Warning: recon_summary.json not found. Using default values.")
        summary = get_default_summary()
    
    # Current timestamp for asof (ensures file change evidence)
    current_asof = datetime.now(KST).isoformat()
    
    # Extract data with defaults
    provenance = summary.get("provenance", {})
    integrity = summary.get("integrity", {"critical_days": 0, "warning_days": 0, "info_days": 0, "top_codes": []})
    kpis = summary.get("kpis", {"gate_open": 0, "executed": 0, "chop_block": 0, "bear_block": 0, "no_data": 0})
    counts = summary.get("counts", {"L1_actions": 0, "L2_trades": 0, "L1_L2_delta": 0})
    period = summary.get("period", {"from": "2024-01-01", "to": "2025-12-31"})
    
    # Status logic
    status_badge = "GREEN"
    if summary.get("status") == "error":
        status_badge = "ERROR"
    elif summary.get("status") == "bootstrap":
        status_badge = "BOOTSTRAP"
    elif integrity.get("critical_days", 0) > 0:
        status_badge = "CRITICAL"
    elif integrity.get("warning_days", 0) > 0:
        status_badge = "AMBER"
    
    # --- Human Report ---
    human_report = {
        "contract_id": "CONTRACT_5",
        "schema_version": "REPORT_HUMAN_V1",
        "generated_at": current_asof,
        "asof": current_asof,
        "headline": {
            "period": f"{period['from']}~{period['to']}",
            "status_badge": status_badge,
            "trade_count": {
                "L1_actions": counts.get("L1_actions", 0),
                "L2_trades": counts.get("L2_trades", 0),
                "delta": counts.get("L1_L2_delta", 0)
            }
        },
        "integrity_summary": {
            "critical_total": integrity.get("critical_days", 0),
            "warning_total": integrity.get("warning_days", 0),
            "info_total": integrity.get("info_days", 0),
            "top_codes": [{"code": x.get("code", "UNKNOWN"), "count": x.get("days", 0)} 
                          for x in integrity.get("top_codes", [])[:5]]
        },
        "kpis": [
            {"key": "gate_open_days", "label_ko": "시장 개장", "value": kpis.get("gate_open", 0), "unit": "days"},
            {"key": "executed_days", "label_ko": "체결 발생", "value": kpis.get("executed", 0), "unit": "days"},
            {"key": "chop_blocked_days", "label_ko": "횡보장 방어", "value": kpis.get("chop_block", 0), "unit": "days"},
            {"key": "bear_blocked_days", "label_ko": "하락장 방어", "value": kpis.get("bear_block", 0), "unit": "days"},
            {"key": "no_data_days", "label_ko": "데이터 누락", "value": kpis.get("no_data", 0), "unit": "days"}
        ],
        "pointers": {
            "recon_summary_path": str(SUMMARY_PATH.relative_to(BASE_DIR)),
            "source": "generate_reports.py"
        }
    }
    
    # --- AI Report ---
    ai_report = {
        "contract_id": "CONTRACT_5",
        "schema_version": "REPORT_AI_V1",
        "generated_at": current_asof,
        "asof": current_asof,
        "kpi_vector": {
            "gate_open_days": kpis.get("gate_open", 0),
            "executed_days": kpis.get("executed", 0),
            "L2_trades": counts.get("L2_trades", 0),
            "no_data_days": kpis.get("no_data", 0)
        },
        "integrity_flags": {
            "critical_total": integrity.get("critical_days", 0),
            "critical_codes": [i.get("code", "UNKNOWN") for i in integrity.get("top_codes", [])[:5]]
        },
        "status": status_badge
    }
    
    # Save Human Report
    print(f"Writing Human Report -> {HUMAN_REPORT_PATH}")
    with open(HUMAN_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(human_report, f, indent=2, ensure_ascii=False)
    
    # Save AI Report
    print(f"Writing AI Report -> {AI_REPORT_PATH}")
    with open(AI_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(ai_report, f, indent=2, ensure_ascii=False)
    
    print(">>> Contract 5 Reports Generated Successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
