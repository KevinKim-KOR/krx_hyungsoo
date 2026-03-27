"""Ops Summary 리스크 계산 및 수동 루프 스테이지 결정."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.ops_summary.paths import (
    BASE_DIR,
    KST,
    OPS_RISK_WINDOW_DAYS,
    PORTFOLIO_STALE_DAYS,
    SEVERITY_MAP,
)
from app.ops_summary.helpers import safe_load_json, sanitize_evidence_ref
from app.utils.portfolio_normalize import load_asof_override, is_holiday_today


def _compute_initial_status(
    emergency_enabled: bool,
    health_decision: str,
    ops_run: Optional[Dict],
) -> str:
    if emergency_enabled:
        return "STOPPED"
    elif health_decision == "FAIL":
        return "BLOCKED"
    elif not ops_run:
        return "NO_RUN_HISTORY"
    elif health_decision == "WARN":
        return "WARN"
    return "OK"


def _collect_health_risks(
    health_decision: str,
    health_snapshot_ref: Optional[str],
    emergency_enabled: bool,
    top_risks: List[Dict],
) -> None:
    if emergency_enabled:
        top_risks.append(
            {
                "code": "EMERGENCY_STOP",
                "severity": "CRITICAL",
                "message": "Emergency stop is active",
                "evidence_refs": ["state/emergency_stop.json"],
            }
        )

    health_evidence = ["reports/ops/evidence/health/health_latest.json"]
    if health_snapshot_ref:
        health_evidence.append(health_snapshot_ref)

    if health_decision == "FAIL":
        top_risks.append(
            {
                "code": "EVIDENCE_HEALTH_FAIL",
                "severity": "CRITICAL",
                "message": "Evidence health check failed",
                "evidence_refs": health_evidence,
            }
        )
    elif health_decision == "WARN":
        top_risks.append(
            {
                "code": "EVIDENCE_HEALTH_WARN",
                "severity": "WARN",
                "message": "Evidence health check has warnings",
                "evidence_refs": health_evidence,
            }
        )


def _collect_ticket_risks(
    tickets_recent: Dict[str, Any],
    top_risks: List[Dict],
) -> None:
    if tickets_recent["failed"] > 0:
        top_risks.append(
            {
                "code": "TICKETS_FAILED",
                "severity": "WARN",
                "message": (
                    f"{tickets_recent['failed']} tickets failed "
                    f"in last {OPS_RISK_WINDOW_DAYS} days"
                ),
                "evidence_refs": tickets_recent["failed_line_refs"],
            }
        )


def _collect_portfolio_risks(
    portfolio: Optional[Dict],
    now: datetime,
    overall_status: str,
    top_risks: List[Dict],
) -> str:
    if not portfolio:
        top_risks.append(
            {
                "code": "NO_PORTFOLIO",
                "severity": "WARN",
                "message": "Portfolio data missing",
                "evidence_refs": [],
            }
        )
        if overall_status == "OK":
            overall_status = "WARN"
    else:
        updated_at_str = portfolio.get("updated_at", "")
        if updated_at_str:
            try:
                updated_dt = datetime.fromisoformat(
                    updated_at_str.replace("Z", "+00:00")
                )
                if updated_dt.tzinfo is None:
                    updated_dt = updated_dt.replace(tzinfo=now.tzinfo)

                days_diff = (now - updated_dt).days
                if days_diff >= PORTFOLIO_STALE_DAYS:
                    top_risks.append(
                        {
                            "code": "PORTFOLIO_STALE_WARN",
                            "severity": "WARN",
                            "message": (
                                f"Portfolio not updated for {days_diff} days "
                                f"(Limit: {PORTFOLIO_STALE_DAYS})"
                            ),
                            "evidence_refs": [
                                "state/portfolio/latest/portfolio_latest.json"
                            ],
                        }
                    )
            except Exception:
                pass
    return overall_status


def _collect_order_plan_risks(
    order_plan: Optional[Dict],
    bundle_is_stale: bool,
    overall_status: str,
    top_risks: List[Dict],
) -> str:
    op_decision = order_plan.get("decision", "UNKNOWN") if order_plan else "UNKNOWN"
    op_reason = order_plan.get("reason", "") if order_plan else ""

    if op_decision == "BLOCKED" and not bundle_is_stale:
        if op_reason == "NO_RECO":
            top_risks.append(
                {
                    "code": "ORDER_PLAN_NO_RECO",
                    "severity": "WARN",
                    "message": "Order Plan blocked: Reco missing",
                    "evidence_refs": [],
                }
            )
            if overall_status == "OK":
                overall_status = "WARN"

        elif op_reason == "PORTFOLIO_INCONSISTENT":
            top_risks.append(
                {
                    "code": "PORTFOLIO_INCONSISTENT",
                    "severity": "CRITICAL",
                    "message": (
                        f"Portfolio Inconsistent: "
                        f"{order_plan.get('reason_detail', '')}"
                    ),
                    "evidence_refs": ["state/portfolio/latest/portfolio_latest.json"],
                }
            )
            overall_status = "BLOCKED"

        else:
            reason_code = op_reason.split(":")[0].strip()
            detail_txt = order_plan.get("reason_detail", "")
            msg = f"Order plan blocked: {reason_code}"
            if detail_txt:
                msg += f" ({detail_txt})"

            top_risks.append(
                {
                    "code": "ORDER_PLAN_BLOCKED",
                    "severity": "WARN",
                    "message": msg,
                    "evidence_refs": [
                        "reports/live/order_plan/latest/order_plan_latest.json"
                    ],
                }
            )
            if overall_status == "OK":
                overall_status = "WARN"

    # Export missing check
    if op_decision in ("GENERATED", "EMPTY"):
        export_path = (
            BASE_DIR
            / "reports"
            / "live"
            / "order_plan_export"
            / "latest"
            / "order_plan_export_latest.json"
        )

        has_export = False
        if export_path.exists():
            try:
                export_data = json.loads(export_path.read_text(encoding="utf-8"))
                export_plan_id = export_data.get("source", {}).get("plan_id")
                plan_id = order_plan.get("plan_id") if order_plan else None
                if export_plan_id == plan_id:
                    has_export = True
            except Exception:
                pass

        if not has_export:
            top_risks.append(
                {
                    "code": "MISSING_EXPORT",
                    "severity": "WARN",
                    "message": ("Order Plan generated but Export (Human Gate) missing"),
                    "evidence_refs": [],
                }
            )
            if overall_status == "OK":
                overall_status = "WARN"

    return overall_status


def _compute_manual_loop(
    order_plan: Optional[Dict],
    overall_status: str,
    top_risks: List[Dict],
) -> Dict[str, Any]:
    """수동 루프 스테이지 결정."""
    export_path = (
        BASE_DIR
        / "reports"
        / "live"
        / "order_plan_export"
        / "latest"
        / "order_plan_export_latest.json"
    )
    prep_path = (
        BASE_DIR
        / "reports"
        / "live"
        / "execution_prep"
        / "latest"
        / "execution_prep_latest.json"
    )
    ticket_path = (
        BASE_DIR
        / "reports"
        / "live"
        / "manual_execution_ticket"
        / "latest"
        / "manual_execution_ticket_latest.json"
    )
    record_path = (
        BASE_DIR
        / "reports"
        / "live"
        / "manual_execution_record"
        / "latest"
        / "manual_execution_record_latest.json"
    )

    export_data = safe_load_json(export_path) if export_path.exists() else None
    prep_data = safe_load_json(prep_path) if prep_path.exists() else None
    ticket_data = safe_load_json(ticket_path) if ticket_path.exists() else None
    record_data = safe_load_json(record_path) if record_path.exists() else None

    manual_stage = "UNKNOWN"

    op_dec = order_plan.get("decision", "UNKNOWN") if order_plan else "UNKNOWN"
    exp_dec = export_data.get("decision", "UNKNOWN") if export_data else "UNKNOWN"

    # P143: Holiday / Replay Logic
    override_cfg = load_asof_override()
    is_holiday_mode = False
    simulate_trade = override_cfg.get("simulate_trade_day", False)
    if override_cfg.get("enabled"):
        if is_holiday_today(
            override_cfg.get("asof_kst"), simulate_trade_day=simulate_trade
        ):
            is_holiday_mode = True

    if is_holiday_mode:
        manual_stage = "NO_ACTION_TODAY"
    elif op_dec == "EMPTY" or exp_dec == "EMPTY":
        manual_stage = "NO_ACTION_TODAY"
    elif not export_data or exp_dec == "BLOCKED":
        manual_stage = "BLOCKED"
    else:
        if not prep_data or prep_data.get("decision") != "READY":
            manual_stage = "NEED_HUMAN_CONFIRM"
        else:
            if not ticket_data or ticket_data.get("decision") != "GENERATED":
                manual_stage = "PREP_READY"
            else:
                manual_stage = "AWAITING_HUMAN_EXECUTION"

                if record_data and record_data.get("decision") in [
                    "EXECUTED",
                    "PARTIAL",
                    "SKIPPED",
                ]:
                    exec_res = record_data.get("execution_result", "EXECUTED")
                    if exec_res == "PARTIAL":
                        manual_stage = "DONE_TODAY_PARTIAL"
                    elif exec_res == "NOT_EXECUTED":
                        manual_stage = "AWAITING_RETRY_EXECUTION"
                    else:
                        manual_stage = "DONE_TODAY"
                        pass
                elif ticket_data and ticket_data.get("decision") == "GENERATED":
                    manual_stage = "AWAITING_RECORD_SUBMIT"

                    dry_run_path = (
                        BASE_DIR
                        / "reports"
                        / "live"
                        / "dry_run_record"
                        / "latest"
                        / "dry_run_record_latest.json"
                    )
                    if dry_run_path.exists():
                        try:
                            dry_run_data = json.loads(
                                dry_run_path.read_text(encoding="utf-8")
                            )
                            dr_ticket_id = dry_run_data.get("linkage", {}).get(
                                "ticket_id"
                            )
                            current_ticket_id = ticket_data.get("id")
                            if dr_ticket_id == current_ticket_id:
                                manual_stage = "DONE_TODAY"
                        except Exception:
                            pass

    # Next Action Logic (P115)
    next_action = "NONE"
    if manual_stage == "NO_ACTION_TODAY":
        if is_holiday_mode:
            next_action = "REPLAY / HOLIDAY CHECK ONLY (No Trade)"
        else:
            next_action = "NONE (Empty Plan)"
    elif manual_stage == "NEED_HUMAN_CONFIRM":
        next_action = "bash deploy/oci/manual_loop_prepare.sh"
    elif manual_stage == "AWAITING_HUMAN_EXECUTION":
        next_action = (
            "EXECUTE TRADES -> "
            "bash deploy/oci/manual_loop_submit_record.sh <record_file>"
        )
    elif manual_stage == "AWAITING_RECORD_SUBMIT":
        rec_dec = record_data.get("decision", "UNKNOWN") if record_data else "UNKNOWN"
        if rec_dec == "BLOCKED":
            reason = record_data.get("reason", "UNKNOWN")
            if reason == "DUPLICATE_SUBMIT_BLOCKED":
                top_risks.append(
                    {
                        "code": "DUPLICATE_RECORD_BLOCKED",
                        "severity": "WARN",
                        "message": "Duplicate record submission attempted.",
                        "evidence_refs": [
                            "reports/live/manual_execution_record/"
                            "latest/manual_execution_record_latest.json"
                        ],
                    }
                )
            elif reason == "LINKAGE_MISMATCH":
                top_risks.append(
                    {
                        "code": "RECORD_LINKAGE_MISMATCH",
                        "severity": "BLOCK",
                        "message": (
                            f"Record Linkage ID Mismatch: "
                            f"{record_data.get('reason_detail')}"
                        ),
                        "evidence_refs": [
                            "reports/live/manual_execution_record/"
                            "latest/manual_execution_record_latest.json"
                        ],
                    }
                )
                overall_status = "BLOCKED"

        next_action = "bash deploy/oci/manual_loop_submit_record.sh <record_file>"
    elif manual_stage == "DONE_TODAY":
        next_action = "NONE (Done)"
    elif manual_stage == "DONE_TODAY_PARTIAL":
        next_action = "REVIEW PARTIALS / RE-SUBMIT (Optional)"
    elif manual_stage == "AWAITING_RETRY_EXECUTION":
        next_action = (
            "RETRY EXECUTION -> " "bash deploy/oci/manual_loop_submit_record.sh"
        )

    # Execution mode
    mode = "LIVE"
    if override_cfg.get("enabled") and override_cfg.get("mode") == "REPLAY":
        mode = "DRY_RUN"
    else:
        try:
            if manual_stage in ["DONE_TODAY", "DONE_TODAY_PARTIAL"]:
                dry_run_path = (
                    BASE_DIR
                    / "reports"
                    / "live"
                    / "dry_run_record"
                    / "latest"
                    / "dry_run_record_latest.json"
                )
                if dry_run_path.exists():
                    dr_data = json.loads(dry_run_path.read_text(encoding="utf-8"))
                    if ticket_data and dr_data.get("linkage", {}).get(
                        "ticket_id"
                    ) == ticket_data.get("id"):
                        mode = "DRY_RUN"
        except Exception:
            pass

    # P191: CHAIN_MISMATCH
    has_chain_mismatch = False
    for doc, name, path in [
        (
            export_data,
            "Export",
            "reports/live/order_plan_export/" "latest/order_plan_export_latest.json",
        ),
        (
            prep_data,
            "Prep",
            "reports/live/execution_prep/" "latest/execution_prep_latest.json",
        ),
        (
            ticket_data,
            "Ticket",
            "reports/live/manual_execution_ticket/"
            "latest/manual_execution_ticket_latest.json",
        ),
    ]:
        if (
            doc
            and doc.get("decision") == "BLOCKED"
            and doc.get("reason") == "CHAIN_MISMATCH"
        ):
            top_risks.append(
                {
                    "code": "CHAIN_MISMATCH",
                    "severity": "CRITICAL",
                    "message": (
                        f"{name} Chain Mismatch: " f"{doc.get('reason_detail', '')}"
                    ),
                    "evidence_refs": [path],
                }
            )
            overall_status = "BLOCKED"
            has_chain_mismatch = True

    if has_chain_mismatch:
        manual_stage = "BLOCKED"

    # Stage-based risks
    if manual_stage == "NEED_HUMAN_CONFIRM":
        top_risks.append(
            {
                "code": "NEED_HUMAN_CONFIRM",
                "severity": "WARN",
                "message": ("Order Plan Export Ready. " "Human Confirmation Required."),
                "evidence_refs": [
                    "reports/live/order_plan_export/"
                    "latest/order_plan_export_latest.json"
                ],
            }
        )
        if overall_status == "OK":
            overall_status = "WARN"

    elif manual_stage == "PREP_READY":
        prep_dec = prep_data.get("decision", "UNKNOWN") if prep_data else "UNKNOWN"
        if prep_dec == "BLOCKED":
            top_risks.append(
                {
                    "code": "EXECUTION_GUARDRAILS_BLOCKED",
                    "severity": "BLOCK",
                    "message": (
                        f"Execution Prep BLOCKED: " f"{prep_data.get('reason_detail')}"
                    ),
                    "evidence_refs": [
                        "reports/live/execution_prep/"
                        "latest/execution_prep_latest.json"
                    ],
                }
            )
            overall_status = "BLOCKED"
        elif prep_dec == "WARN":
            top_risks.append(
                {
                    "code": "EXECUTION_GUARDRAILS_WARN",
                    "severity": "WARN",
                    "message": (
                        f"Execution Prep WARNING: " f"{prep_data.get('reason_detail')}"
                    ),
                    "evidence_refs": [
                        "reports/live/execution_prep/"
                        "latest/execution_prep_latest.json"
                    ],
                }
            )
            if overall_status == "OK":
                overall_status = "WARN"

    elif manual_stage == "AWAITING_RECORD_SUBMIT":
        top_risks.append(
            {
                "code": "MANUAL_RECORD_MISSING",
                "severity": "INFO",
                "message": ("Execution Ticket Generated. Waiting for Record."),
                "evidence_refs": [
                    "reports/live/manual_execution_ticket/"
                    "latest/manual_execution_ticket_latest.json"
                ],
            }
        )

    return {
        "manual_stage": manual_stage,
        "mode": mode,
        "next_action": next_action,
        "overall_status": overall_status,
        "export_data": export_data,
        "prep_data": prep_data,
        "ticket_data": ticket_data,
        "record_data": record_data,
    }


def _collect_contract5_risks(
    c5_report: Optional[Dict],
    c5_decision: str,
    overall_status: str,
    top_risks: List[Dict],
) -> str:
    if c5_decision == "BLOCKED":
        top_risks.append(
            {
                "code": "CONTRACT5_REPORT_BLOCKED",
                "severity": "WARN",
                "message": (
                    f"Daily Report Blocked: "
                    f"{c5_report.get('reason_detail', '') if c5_report else 'Missing'}"
                ),
                "evidence_refs": ["reports/ops/contract5/latest/ai_report_latest.json"],
            }
        )
        if overall_status == "OK":
            overall_status = "WARN"
    elif c5_decision == "EMPTY":
        top_risks.append(
            {
                "code": "CONTRACT5_REPORT_EMPTY",
                "severity": "INFO",
                "message": "Daily Report Empty",
                "evidence_refs": ["reports/ops/contract5/latest/ai_report_latest.json"],
            }
        )
    return overall_status


def _collect_bundle_risks(
    validation: Any,
    overall_status: str,
    top_risks: List[Dict],
) -> str:
    if validation.decision == "NO_BUNDLE":
        top_risks.append(
            {
                "code": "NO_BUNDLE",
                "severity": "WARN",
                "message": "Strategy Bundle missing",
                "evidence_refs": [],
            }
        )
        if overall_status == "OK":
            overall_status = "WARN"
    else:
        if validation.stale:
            top_risks.append(
                {
                    "code": "BUNDLE_STALE_WARN",
                    "severity": "WARN",
                    "message": (f"Strategy Bundle Stale: {validation.stale_reason}"),
                    "evidence_refs": [
                        "state/strategy_bundle/" "latest/strategy_bundle_latest.json"
                    ],
                }
            )
            if overall_status == "OK":
                overall_status = "WARN"
    return overall_status


def _collect_reco_risks(
    reco: Optional[Dict],
    overall_status: str,
    top_risks: List[Dict],
) -> str:
    reco_decision = reco.get("decision", "MISSING_RECO") if reco else "MISSING_RECO"
    reco_reason = reco.get("reason", "") if reco else ""

    if reco_decision == "MISSING_RECO":
        top_risks.append(
            {
                "code": "NO_RECO_YET",
                "severity": "WARN",
                "message": "Reco report missing",
                "evidence_refs": [],
            }
        )
        if overall_status == "OK":
            overall_status = "WARN"
    elif reco_decision == "EMPTY_RECO":
        top_risks.append(
            {
                "code": "RECO_EMPTY",
                "severity": "WARN",
                "message": f"Reco Empty: {reco_reason}",
                "evidence_refs": ["reports/live/reco/latest/reco_latest.json"],
            }
        )
        if overall_status == "OK":
            overall_status = "WARN"
    elif reco_decision == "BLOCKED":
        if "BUNDLE" in reco_reason:
            top_risks.append(
                {
                    "code": "STALE_BUNDLE_BLOCKS_RECO",
                    "severity": "WARN",
                    "message": f"Reco blocked by bundle: {reco_reason}",
                    "evidence_refs": ["reports/live/reco/latest/reco_latest.json"],
                }
            )
            if overall_status == "OK":
                overall_status = "WARN"
    return overall_status


def finalize_risks(
    top_risks: List[Dict],
    overall_status: str,
    emergency_enabled: bool,
) -> str:
    """리스크 정렬 및 최종 overall_status 결정."""

    def risk_sort_key(r):
        return SEVERITY_MAP.get(r.get("severity", "INFO"), 2)

    top_risks.sort(key=risk_sort_key)

    if top_risks:
        top_sev_str = top_risks[0].get("severity", "INFO")
        if top_sev_str in ("CRITICAL", "BLOCKED"):
            overall_status = "BLOCKED"
        elif top_sev_str == "WARN":
            if overall_status != "BLOCKED":
                overall_status = "WARN"
    else:
        if overall_status not in ("OK", "NO_RUN_HISTORY"):
            top_risks.append(
                {
                    "code": f"OPS_{overall_status}",
                    "severity": ("WARN" if overall_status == "WARN" else "BLOCKED"),
                    "message": (
                        f"Operational status is {overall_status} "
                        f"but no specific risk identified."
                    ),
                    "evidence_refs": [],
                }
            )

    if emergency_enabled:
        overall_status = "STOPPED"

    return overall_status


def compute_all_risks(
    *,
    health_decision: str,
    health_snapshot_ref: Optional[str],
    emergency_enabled: bool,
    ops_run: Optional[Dict],
    tickets_recent: Dict[str, Any],
    portfolio: Optional[Dict],
    order_plan: Optional[Dict],
    c5_report: Optional[Dict],
    c5_decision: str,
    validation: Any,
    reco: Optional[Dict],
    now: datetime,
) -> Dict[str, Any]:
    """모든 리스크를 수집하고 최종 상태를 반환한다."""
    top_risks: List[Dict] = []
    overall_status = _compute_initial_status(
        emergency_enabled, health_decision, ops_run
    )

    _collect_health_risks(
        health_decision, health_snapshot_ref, emergency_enabled, top_risks
    )
    _collect_ticket_risks(tickets_recent, top_risks)
    overall_status = _collect_portfolio_risks(portfolio, now, overall_status, top_risks)

    bundle_is_stale = validation.stale if validation else False
    overall_status = _collect_order_plan_risks(
        order_plan, bundle_is_stale, overall_status, top_risks
    )

    manual_result = _compute_manual_loop(order_plan, overall_status, top_risks)
    overall_status = manual_result["overall_status"]

    overall_status = _collect_contract5_risks(
        c5_report, c5_decision, overall_status, top_risks
    )
    overall_status = _collect_bundle_risks(validation, overall_status, top_risks)
    overall_status = _collect_reco_risks(reco, overall_status, top_risks)

    overall_status = finalize_risks(top_risks, overall_status, emergency_enabled)

    return {
        "top_risks": top_risks,
        "overall_status": overall_status,
        "manual_loop": {
            "stage": manual_result["manual_stage"],
            "mode": manual_result["mode"],
            "next_action": manual_result["next_action"],
            "export": manual_result["export_data"],
            "prep": manual_result["prep_data"],
            "ticket": manual_result["ticket_data"],
            "record": manual_result["record_data"],
        },
    }
