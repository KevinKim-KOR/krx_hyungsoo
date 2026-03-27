"""
Ops Summary Generator (C-P.35 + D-P.58 + D-P.59)

Single Pane of Glass: 분산된 최신 산출물을 통합 요약
- 읽기/요약만 허용, 비즈니스 로직 실행 금지
- Atomic Write 필수
- D-P.58: Portfolio, Order Plan status & risk included
- D-P.59: Portfolio Stale Risk (7 days inactive)
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# 파일 직접 실행 지원 (python app/generate_ops_summary.py)
_BASE_DIR = Path(__file__).resolve().parent.parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

from app.ops_summary.paths import (
    KST,
    BASE_DIR,
    HEALTH_LATEST,
    SEND_LATEST,
    OUTBOX_LATEST,
    EMERGENCY_STOP_FILE,
    GATE_FILE,
    PORTFOLIO_LATEST,
    ORDER_PLAN_LATEST,
    CONTRACT5_LATEST,
    RECO_LATEST,
    SUMMARY_DIR,
    SUMMARY_LATEST,
    SUMMARY_SNAPSHOTS_DIR,
)
from app.ops_summary.helpers import (
    safe_load_json,
    sanitize_evidence_ref,
    get_latest_ops_run,
    get_tickets_summary,
    get_tickets_recent,
)
from app.ops_summary.risk_aggregator import compute_all_risks
from app.load_strategy_bundle import load_latest_bundle


def generate_ops_summary():
    """Ops Summary 생성"""
    now = datetime.now(KST)

    # === Health ===
    health = safe_load_json(HEALTH_LATEST) or {}
    health_decision = health.get("decision", "UNKNOWN")
    health_snapshot_ref = health.get("snapshot_ref")

    if health_snapshot_ref:
        health_snapshot_ref = sanitize_evidence_ref(health_snapshot_ref)

    if not health_snapshot_ref:
        base_snap_dir = (
            BASE_DIR / "reports" / "ops" / "evidence" / "health" / "snapshots"
        )
        if base_snap_dir.exists():
            snaps = sorted(base_snap_dir.glob("*.json"), reverse=True)
            if snaps:
                health_snapshot_ref = (
                    f"reports/ops/evidence/health/snapshots/{snaps[0].name}"
                )

    # === Gate & Emergency ===
    emergency = safe_load_json(EMERGENCY_STOP_FILE) or {"enabled": False}
    emergency_enabled = emergency.get("enabled", False)
    gate = safe_load_json(GATE_FILE) or {"mode": "DRY_RUN"}

    # === Last Run ===
    ops_run = get_latest_ops_run()
    last_run_triplet = {
        "last_done": None,
        "last_failed": None,
        "last_blocked": None,
    }
    if ops_run:
        status = ops_run.get("overall_status", "")
        run_time = ops_run.get("asof")
        if status in ("DONE", "WARN", "OK"):
            last_run_triplet["last_done"] = run_time
        elif status == "FAILED":
            last_run_triplet["last_failed"] = run_time
        elif status in ("BLOCKED", "STOPPED"):
            last_run_triplet["last_blocked"] = run_time

    # === Tickets ===
    tickets_summary = get_tickets_summary()
    tickets_recent = get_tickets_recent()

    # === Push ===
    outbox = safe_load_json(OUTBOX_LATEST) or {}
    outbox_count = len(outbox.get("messages", []))
    send = safe_load_json(SEND_LATEST) or {}
    send_decision = send.get("decision", "N/A")

    # === Portfolio ===
    portfolio = safe_load_json(PORTFOLIO_LATEST)
    portfolio_summary = {
        "present": bool(portfolio),
        "updated_at": portfolio.get("updated_at") if portfolio else None,
        "total_value": portfolio.get("total_value", 0) if portfolio else 0,
        "cash_ratio_pct": (portfolio.get("cash_ratio_pct", 0) if portfolio else 0),
        "source": (portfolio.get("source", "LOCAL_STATE") if portfolio else "MISSING"),
        "bundle_id": portfolio.get("bundle_id") if portfolio else None,
        "integrity_prefix": (
            portfolio.get("integrity", {}).get("payload_sha256", "")[:8]
            if portfolio and portfolio.get("integrity")
            else None
        ),
    }

    # === Order Plan ===
    order_plan = safe_load_json(ORDER_PLAN_LATEST)

    op_snapshot_ref = None
    op_snap_dir = BASE_DIR / "reports" / "live" / "order_plan" / "snapshots"
    if op_snap_dir.exists():
        snaps = sorted(op_snap_dir.glob("order_plan_*.json"), reverse=True)
        if snaps:
            op_snapshot_ref = f"reports/live/order_plan/snapshots/{snaps[0].name}"

    order_plan_summary = {
        "decision": (
            order_plan.get("decision", "UNKNOWN") if order_plan else "UNKNOWN"
        ),
        "reason": order_plan.get("reason", "") if order_plan else "",
        "reason_detail": (order_plan.get("reason_detail", "") if order_plan else ""),
        "orders_count": (len(order_plan.get("orders", [])) if order_plan else 0),
        "latest_ref": "reports/live/order_plan/latest/order_plan_latest.json",
        "snapshot_ref": op_snapshot_ref,
    }

    # === Contract 5 ===
    c5_report = safe_load_json(CONTRACT5_LATEST)
    c5_snapshot_ref = None
    c5_snap_dir = BASE_DIR / "reports" / "ops" / "contract5" / "snapshots"
    if c5_snap_dir.exists():
        snaps = sorted(c5_snap_dir.glob("ai_report_*.json"), reverse=True)
        if snaps:
            c5_snapshot_ref = f"reports/ops/contract5/snapshots/{snaps[0].name}"
    c5_decision = c5_report.get("decision", "MISSING") if c5_report else "MISSING"

    # === Strategy Bundle ===
    bundle, validation = load_latest_bundle()
    bundle_summary = {
        "present": bundle is not None,
        "created_at": validation.created_at,
        "strategy_name": validation.strategy_name or "Unknown",
        "stale": validation.stale,
        "stale_reason": validation.stale_reason,
    }

    # === Reco ===
    reco = safe_load_json(RECO_LATEST)
    reco_decision = reco.get("decision", "MISSING_RECO") if reco else "MISSING_RECO"
    reco_reason = reco.get("reason", "") if reco else ""

    source_bundle_id = None
    if reco and reco.get("source_bundle"):
        source_bundle_id = reco["source_bundle"].get("bundle_id")

    reco_snapshot_ref = None
    reco_snap_dir = BASE_DIR / "reports" / "live" / "reco" / "snapshots"
    if reco_snap_dir.exists():
        snaps = sorted(reco_snap_dir.glob("reco_*.json"), reverse=True)
        if snaps:
            reco_snapshot_ref = f"reports/live/reco/snapshots/{snaps[0].name}"

    reco_summary = {
        "decision": reco_decision,
        "reason": reco_reason,
        "latest_ref": "reports/live/reco/latest/reco_latest.json",
        "snapshot_ref": reco_snapshot_ref,
        "source_bundle_id": source_bundle_id,
    }

    # === Risk Computation ===
    risk_result = compute_all_risks(
        health_decision=health_decision,
        health_snapshot_ref=health_snapshot_ref,
        emergency_enabled=emergency_enabled,
        ops_run=ops_run,
        tickets_recent=tickets_recent,
        portfolio=portfolio,
        order_plan=order_plan,
        c5_report=c5_report,
        c5_decision=c5_decision,
        validation=validation,
        reco=reco,
        now=now,
    )

    # === Contract 5 Summary ===
    ds_decision = "PENDING"
    ds_sentiment = "NEUTRAL"
    ds_summary = "Pending calculation"

    contract5_summary = {
        "human_report": {
            "decision": c5_decision,
            "latest_ref": "reports/phase_c/latest/report_human.json",
            "snapshot_ref": (
                c5_snapshot_ref.replace("ai_report", "human_report").replace(
                    ".json", ".md"
                )
                if c5_snapshot_ref
                else None
            ),
        },
        "daily_summary": {
            "decision": ds_decision,
            "sentiment": ds_sentiment,
            "summary_text": ds_summary,
        },
        "ai_report": {
            "decision": c5_decision,
            "latest_ref": ("reports/ops/contract5/latest/ai_report_latest.json"),
            "snapshot_ref": c5_snapshot_ref,
        },
    }

    # === Construct Summary ===
    summary = {
        "schema": "OPS_SUMMARY_V1",
        "asof": now.isoformat(),
        "overall_status": risk_result["overall_status"],
        "guard": {
            "evidence_health": {
                "decision": health_decision,
                "snapshot_ref": health_snapshot_ref,
            },
            "emergency_stop": emergency,
            "execution_gate": gate,
        },
        "last_run_triplet": last_run_triplet,
        "tickets": tickets_summary,
        "tickets_recent": tickets_recent,
        "push": {
            "outbox_row_count": outbox_count,
            "last_send_decision": send_decision,
        },
        "portfolio": portfolio_summary,
        "order_plan": order_plan_summary,
        "manual_loop": risk_result["manual_loop"],
        "contract5": contract5_summary,
        "reco": reco_summary,
        "strategy_bundle": bundle_summary,
        "top_risks": risk_result["top_risks"],
        "evidence_refs": [
            "reports/ops/daily/snapshots",
            "state/tickets/ticket_results.jsonl",
            "reports/ops/evidence/health/health_latest.json",
        ],
    }

    # === Save ===
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_LATEST.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_LATEST.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    SUMMARY_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    snap_name = f"ops_summary_{now.strftime('%Y%m%d_%H%M%S')}.json"
    shutil.copy(SUMMARY_LATEST, SUMMARY_SNAPSHOTS_DIR / snap_name)

    return summary


# ── 호환 alias (활성 소비자 계약 유지) ──


def regenerate_ops_summary():
    """generate_ops_summary 호환 alias.

    소비자: run_ops_drill.py, run_live_cycle.py
    """
    return generate_ops_summary()


def generate_and_save_from_receipt(receipt):
    """receipt 기반 ops summary 생성 호환 alias.

    소비자: run_ops_cycle.py
    receipt 인자는 현재 사용하지 않으나 시그니처를 유지한다.
    """
    summary = generate_ops_summary()
    return {
        "snapshot_path": str(SUMMARY_SNAPSHOTS_DIR),
        "summary_latest_path": str(SUMMARY_LATEST),
        "overall_status": summary.get("overall_status", "N/A"),
    }


if __name__ == "__main__":
    result = generate_ops_summary()
    print(json.dumps(result, indent=2, ensure_ascii=False))
