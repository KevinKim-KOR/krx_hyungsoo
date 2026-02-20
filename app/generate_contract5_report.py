# -*- coding: utf-8 -*-
"""
app/generate_contract5_report.py
P103: OCI Contract 5 Report Generator V1 (Human + AI, Read-only)

Objective:
- Aggregate Ops Summary, Reco, Order Plan.
- Generate CONTRACT5_REPORT_V1 (JSON) for Dashboard/AI.
- Generate Human Markdown report.
- Fail-Closed: Block if inputs missing or blocked.
"""

import json
import sys
import shutil
import subprocess
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from pathlib import Path
from typing import Dict, Any, List, Optional

# --- Configuration ---
BASE_DIR = Path(__file__).parent.parent
RECO_LATEST_FILE = BASE_DIR / "reports" / "live" / "reco" / "latest" / "reco_latest.json"
ORDER_PLAN_LATEST_FILE = BASE_DIR / "reports" / "live" / "order_plan" / "latest" / "order_plan_latest.json"
# Ops Summary is fetched via API or file? 
# Ops Summary file path is usually not strictly exposed as "latest" file in same way? 
# Ops Summary is generated dynamically or cached. 
# But backend/main.py has /api/ops/summary/latest.
# We can use subprocess to call regenerate_ops_summary logic OR fetch via API.
# But "ops_summary_ref" in contract suggests using API Ref.
# However, to READ the DATA, we need to call the generator or API.
# Since we are inside the system, calling the generator function directly is safer/faster if modular.
# app.generate_ops_summary.regenerate_ops_summary is available.

OUTPUT_DIR_C5 = BASE_DIR / "reports" / "ops" / "contract5" / "latest"
OUTPUT_DIR_C5_SNAP = BASE_DIR / "reports" / "ops" / "contract5" / "snapshots"
OUTPUT_SSOT_HUMAN_JSON = BASE_DIR / "reports" / "phase_c" / "latest" / "report_human.json" # Dashboard SSOT
OUTPUT_AI_JSON = OUTPUT_DIR_C5 / "ai_report_latest.json"
OUTPUT_HUMAN_MD = OUTPUT_DIR_C5 / "human_report_latest.md"

# Ensure directories
OUTPUT_DIR_C5.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR_C5_SNAP.mkdir(parents=True, exist_ok=True)
OUTPUT_SSOT_HUMAN_JSON.parent.mkdir(parents=True, exist_ok=True)

def load_json(path: Path) -> Optional[Dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def get_ops_summary() -> Dict:
    """Fetch Ops Summary data"""
    # Import here to avoid circular dependency if possible, or usually ok.
    # Note: generate_ops_summary.py needs RECO/ORDER_PLAN inputs?
    # Yes, Ops Summary Consumes Reco/Order Plan.
    # But Contract 5 Consumes Ops Summary + Reco + Order Plan.
    # This seems circular if Ops Summary includes Contract 5 status?
    # P102/P101: Ops Summary includes Reco/Order Plan status.
    # P103: Contract 5 Report aggregates everything.
    # And Ops Summary ALSO wants to include Contract 5 status?
    # "OPS_SUMMARY_V1에 contract5 섹션 추가/갱신"
    # Logic flow: 
    # 1. Reco/OrderPlan Generated.
    # 2. Ops Summary Generated (reads Reco/OrderPlan, but NO Contract 5 yet or Stale).
    # 3. Contract 5 Generated (reads Ops Summary).
    # 4. Ops Summary Regenerated (to include Contract 5 status)?
    # Ideally, Ops Summary generation includes Contract 5 status from previous run or current file.
    
    # We will generate Contract 5 based on "Current Ops Summary" (which might not have latest C5).
    # Then updating Ops Summary happens later or via Dashboard calls?
    # We will just fetch the function result.
    
    from app.generate_ops_summary import regenerate_ops_summary
    return regenerate_ops_summary()

def generate_markdown(c5_report: Dict) -> str:
    """Generate Markdown content for Human"""
    decision = c5_report.get("decision", "UNKNOWN")
    reason = c5_report.get("reason", "UNKNOWN")
    inputs = c5_report.get("inputs", {})
    
    lines = []
    lines.append(f"# Daily Operation Report")
    lines.append(f"**Date**: {c5_report['asof']}")
    lines.append(f"**Decision**: {decision}")
    lines.append(f"**Reason**: {reason}")
    lines.append("")
    lines.append("## Inputs Status")
    lines.append(f"- **Ops Summary**: {inputs.get('ops_asof', '?')}")
    lines.append(f"- **Reco**: {inputs.get('reco_decision', 'MISSING')} ({inputs.get('reco_asof', '?')})")
    lines.append(f"- **Order Plan**: {inputs.get('order_plan_decision', 'MISSING')} ({inputs.get('order_plan_asof', '?')})")
    lines.append("")
    
    if decision == "OK":
        lines.append("## Summary")
        lines.append(f"{c5_report.get('reason_detail', 'Operations Normal')}")
        # Add more insights if available
    else:
        lines.append("## Issues")
        lines.append(f"**Block Reason**: {c5_report.get('reason_detail')}")
        
    return "\n".join(lines)

def generate_ai_content(c5_report: Dict) -> Dict:
    """Generate AI structured content"""
    return {
        "summary": c5_report.get("reason_detail"),
        "decision_vector": c5_report.get("decision"),
        "inputs": c5_report.get("inputs")
    }

def generate_contract5_report() -> Dict[str, Any]:
    now = datetime.now(KST)
    asof_str = now.isoformat()
    
    # 1. Gather Inputs
    ops_data = get_ops_summary()
    reco_data = load_json(RECO_LATEST_FILE)
    order_plan_data = load_json(ORDER_PLAN_LATEST_FILE)
    
    # 2. Decide Status
    # Fail-Closed logic
    decision = "OK"
    reason = "SUCCESS"
    reason_detail = "All inputs consolidated"
    
    if not ops_data:
        decision = "BLOCKED"
        reason = "INPUT_MISSING"
        reason_detail = "Ops Summary missing"
    elif not reco_data:
        decision = "BLOCKED"
        reason = "INPUT_MISSING"
        reason_detail = "Reco missing"
    elif not order_plan_data:
        decision = "BLOCKED" # or WARN if Reco was Empty?
        # If Reco was Empty, Order Plan might be missing? No, OrderPlan generator creates EMPTY plan.
        # So inputs must exist.
        reason = "INPUT_MISSING"
        reason_detail = "Order Plan missing"
    else:
        # Check decisions
        ops_dec = ops_data.get("overall_status", "UNKNOWN")
        reco_dec = reco_data.get("decision", "UNKNOWN")
        op_dec = order_plan_data.get("decision", "UNKNOWN")
        
        if ops_dec == "BLOCKED" or ops_dec == "CRITICAL" or ops_dec == "ERROR":
            decision = "BLOCKED"
            reason = "INPUT_BLOCKED"
            reason_detail = f"Ops Summary is {ops_dec}"
        elif reco_dec == "BLOCKED":
            decision = "BLOCKED"
            reason = "INPUT_BLOCKED"
            reason_detail = f"Reco is BLOCKED ({reco_data.get('reason')})"
        elif op_dec == "BLOCKED":
            decision = "BLOCKED"
            reason = "INPUT_BLOCKED"
            reason_detail = f"Order Plan is BLOCKED ({order_plan_data.get('reason')})"
        elif ops_dec == "WARN":
            decision = "WARN"
            reason = "INPUT_WARN"
            reason_detail = "Ops Summary has Warnings"
        elif reco_dec == "EMPTY_RECO":
            decision = "EMPTY"
            reason = "SUCCESS_EMPTY"
            reason_detail = "No Recommendations generated"
        # Order Plan EMPTY is OK (NO_ORDERS)
        
    # 3. Construct Report
    # Note: 'ops_summary_ref' uses generic API URL as per contract
    
    report = {
        "schema": "CONTRACT5_REPORT_V1",
        "asof": asof_str,
        "report_id": f"c5-{now.strftime('%Y%m%d-%H%M%S')}",
        "decision": decision,
        "reason": reason,
        "reason_detail": reason_detail,
        "inputs": {
            "ops_summary_ref": "http://localhost:8000/api/ops/summary/latest",
            "ops_asof": ops_data.get("asof") if ops_data else None,
            "reco_ref": str(RECO_LATEST_FILE.relative_to(BASE_DIR)).replace("\\", "/"),
            "reco_asof": reco_data.get("asof") if reco_data else None,
            "reco_decision": reco_data.get("decision") if reco_data else None,
            "order_plan_ref": str(ORDER_PLAN_LATEST_FILE.relative_to(BASE_DIR)).replace("\\", "/"),
            "order_plan_asof": order_plan_data.get("asof") if order_plan_data else None,
            "order_plan_decision": order_plan_data.get("decision") if order_plan_data else None,
        },
        "evidence_refs": [],
        "content": {},
        "error_summary": None,
        # Shim for Ops Dashboard (backward compatibility)
        "headline": {
            "status_badge": decision
        }
    }
    
    if reco_data: report["evidence_refs"].append(report["inputs"]["reco_ref"])
    if order_plan_data: report["evidence_refs"].append(report["inputs"]["order_plan_ref"])
    
    # 4. Generate Content
    report["content"]["human"] = generate_markdown(report)
    report["content"]["ai"] = generate_ai_content(report)
    
    # 5. Save Artifacts
    try:
        # Atomic Write helper
        def atomic_write(path: Path, content: str):
            tmp = path.with_name(f".tmp_{path.name}")
            tmp.write_text(content, encoding="utf-8")
            shutil.move(tmp, path)

        # 5.1 AI Report (JSON) -> reports/ops/contract5/latest/ai_report_latest.json
        json_content = json.dumps(report, indent=2, ensure_ascii=False)
        atomic_write(OUTPUT_AI_JSON, json_content)
        
        # 5.2 Human Report (JSON wrapper for Dashboard SSOT) -> reports/phase_c/latest/report_human.json
        # Dashboard reads this. It expects 'headline' if old schema, 
        # or 'decision' if new schema (we will update dashboard).
        atomic_write(OUTPUT_SSOT_HUMAN_JSON, json_content)
        
        # 5.3 Human Markdown -> reports/ops/contract5/latest/human_report_latest.md
        atomic_write(OUTPUT_HUMAN_MD, report["content"]["human"])
        
        # 5.4 Snapshots
        snap_ts = now.strftime("%Y%m%d_%H%M%S")
        
        # AI Snapshot
        shutil.copy(OUTPUT_AI_JSON, OUTPUT_DIR_C5_SNAP / f"ai_report_{snap_ts}.json")
        # Human Markdown Snapshot
        shutil.copy(OUTPUT_HUMAN_MD, OUTPUT_DIR_C5_SNAP / f"human_report_{snap_ts}.md")
        
        print(json_content) # Output for API capture
        return report

    except Exception as e:
        err_json = {
            "schema": "CONTRACT5_REPORT_V1",
            "decision": "BLOCKED",
            "reason": "WRITE_ERROR",
            "error_summary": str(e)
        }
        print(json.dumps(err_json))
        return err_json

if __name__ == "__main__":
    generate_contract5_report()
