# -*- coding: utf-8 -*-
"""operator 라우터 — /api/operator/sync_cycle."""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.utils import (
    BASE_DIR,
    REPORTS_DIR,
    PREP_LATEST_FILE,
    TICKET_LATEST_FILE,
    ORDER_PLAN_EXPORT_LATEST_FILE,
    OPS_SUMMARY_PATH,
    logger,
)

router = APIRouter()


# --- 모델 ---
class SyncCycleRequest(BaseModel):
    token: Optional[str] = None
    prep_only: Optional[bool] = False


# --- 헬퍼 ---
def _regen_ticket_md(ticket: dict):
    """Regenerate the ticket .md file from patched ticket JSON data."""
    try:
        md_path = (
            REPORTS_DIR
            / "live"
            / "manual_execution_ticket"
            / "latest"
            / "manual_execution_ticket_latest.md"
        )
        src = ticket.get("source", {})
        summ = ticket.get("summary", {})
        gr = ticket.get("guardrails", {})

        if ticket.get("decision") == "BLOCKED":
            lines = [
                "# Manual Execution Ticket (BLOCKED)",
                f"**Plan ID**: {src.get('plan_id', 'UNKNOWN')}",
                f"**AsOf**: {ticket.get('asof', '')}",
                "**Status**: ❌ BLOCKED",
                f"**Reason**: {ticket.get('reason', '')}",
            ]
        else:
            lines = [
                "# Manual Execution Ticket",
                f"**Plan ID**: {src.get('plan_id', 'UNKNOWN')}",
                f"**AsOf**: {ticket.get('asof', '')}",
                f"**Token**: `{src.get('confirm_token', '')}`",
                "",
                "## Summary",
                f"- **Status**: {gr.get('decision', '')} {gr.get('violated', '')}",
                f"- **Orders**: {summ.get('total_orders', 0)} (Notional: {summ.get('total_notional', 0):,.0f} KRW)",
                f"- **Cash**: {summ.get('cash_before', 0):,.0f} -> ~{summ.get('cash_after_est', 0):,.0f} KRW",
                "",
                "## Copy-Paste (HTS/MTS)",
                "```text",
                f"{ticket.get('copy_paste', '')}",
                "```",
                "",
                "## Orders to Execute",
                "| Side | Ticker | Qty | Limit | Check |",
                "|---|---|---|---|---|",
            ]
            for o in ticket.get("orders", []):
                qty = o.get("qty", 0)
                limit = o.get("limit_price", 0)
                lines.append(
                    f"| {o.get('side', '')} | {o.get('ticker', '')} | {qty:,} | {limit:,} | [ ] |"
                )
            lines.append("")
            lines.append(
                "> **Operator Instruction**: Copy input string, paste to HTS. "
                "Check each order as executed."
            )

        md_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"P146.8C: Ticket MD regenerated with plan_id={src.get('plan_id')}")
    except Exception as e:
        logger.warning(f"P146.8C: Ticket MD regen failed: {e}")


# --- 라우트 ---
@router.post("/api/operator/sync_cycle", summary="이번 회차 정리 (Sync Cycle)")
def sync_cycle(req: SyncCycleRequest):
    """P146.7: Align ticket/prep plan_ids to export in one click."""
    try:
        # 1. Determine exec_mode
        exec_mode = "LIVE"
        if OPS_SUMMARY_PATH.exists():
            try:
                summ = json.loads(OPS_SUMMARY_PATH.read_text(encoding="utf-8"))
                ml = summ.get("manual_loop", {})
                exec_mode = ml.get("mode", "LIVE")
            except Exception:
                pass
        # Replay override
        try:
            from app.utils.portfolio_normalize import load_asof_override

            override = load_asof_override()
            if override.get("enabled", False):
                exec_mode = "DRY_RUN"
        except Exception:
            pass

        # 2. Token gate (LIVE requires token)
        if exec_mode == "LIVE":
            if not req.token:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "ok": False,
                        "reason": "TOKEN_MISMATCH",
                        "message": "LIVE 모드에서는 token이 필요합니다.",
                    },
                )

        # 3. Read export plan_id (SSOT 기준)
        if not ORDER_PLAN_EXPORT_LATEST_FILE.exists():
            raise HTTPException(
                status_code=409,
                detail={
                    "ok": False,
                    "reason": "EXPORT_NOT_FOUND",
                    "message": "Export 파일이 없습니다.",
                },
            )
        export_data = json.loads(
            ORDER_PLAN_EXPORT_LATEST_FILE.read_text(encoding="utf-8")
        )
        export_plan_id = export_data.get("source", {}).get("plan_id")
        if not export_plan_id:
            raise HTTPException(
                status_code=409,
                detail={
                    "ok": False,
                    "reason": "EXPORT_NO_PLAN_ID",
                    "message": "Export에 plan_id가 없습니다.",
                },
            )

        actions = {"ticket_regenerated": False, "prep_regenerated": False}
        plan_ids = {"export": export_plan_id}

        # 4. Ticket alignment (skip if prep_only)
        if not req.prep_only:
            ticket_plan_id = None
            if TICKET_LATEST_FILE.exists():
                try:
                    td = json.loads(TICKET_LATEST_FILE.read_text(encoding="utf-8"))
                    ticket_plan_id = td.get("source", {}).get("plan_id")
                except Exception:
                    pass

            if ticket_plan_id != export_plan_id:
                # Regenerate ticket + patch
                from app.generate_manual_execution_ticket import generate_ticket

                generate_ticket()
                if TICKET_LATEST_FILE.exists():
                    td = json.loads(TICKET_LATEST_FILE.read_text(encoding="utf-8"))
                    old_id = td.get("source", {}).get("plan_id")
                    td["source"]["plan_id"] = export_plan_id
                    td["source"]["_aligned_from"] = "export"
                    td["source"]["_original_prep_plan_id"] = old_id
                    # P146.8C: Also align confirm_token from export
                    export_token = export_data.get("human_confirm", {}).get(
                        "confirm_token"
                    ) or export_data.get("source", {}).get("confirm_token")
                    if export_token:
                        td["source"]["confirm_token"] = export_token
                    TICKET_LATEST_FILE.write_text(
                        json.dumps(td, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    # P146.8C: Regenerate MD with patched values
                    _regen_ticket_md(td)
                    actions["ticket_regenerated"] = True
                    logger.info(
                        f"P146.7 Sync: ticket plan_id {old_id} -> {export_plan_id}"
                    )

            plan_ids["ticket"] = (
                export_plan_id if actions["ticket_regenerated"] else ticket_plan_id
            )

        # 5. Prep alignment
        prep_plan_id = None
        if PREP_LATEST_FILE.exists():
            try:
                pd = json.loads(PREP_LATEST_FILE.read_text(encoding="utf-8"))
                prep_plan_id = pd.get("source", {}).get("plan_id")
            except Exception:
                pass

        if prep_plan_id != export_plan_id:
            # Regenerate prep
            token_for_prep = req.token or (
                "SYNC_CYCLE_DRY" if exec_mode == "DRY_RUN" else ""
            )
            from app.generate_execution_prep import generate_prep

            generate_prep(token_for_prep)
            # Patch plan_id to export
            if PREP_LATEST_FILE.exists():
                pd = json.loads(PREP_LATEST_FILE.read_text(encoding="utf-8"))
                old_id = pd.get("source", {}).get("plan_id")
                pd["source"]["plan_id"] = export_plan_id
                pd["source"]["_aligned_from"] = "export"
                pd["source"]["_original_plan_id"] = old_id
                PREP_LATEST_FILE.write_text(
                    json.dumps(pd, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                actions["prep_regenerated"] = True
                logger.info(f"P146.7 Sync: prep plan_id {old_id} -> {export_plan_id}")

        plan_ids["prep"] = (
            export_plan_id if actions["prep_regenerated"] else prep_plan_id
        )

        return {
            "ok": True,
            "exec_mode": exec_mode,
            "plan_ids": plan_ids,
            "actions": actions,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync Cycle Error: {e}")
        raise HTTPException(status_code=500, detail={"ok": False, "reason": str(e)})
