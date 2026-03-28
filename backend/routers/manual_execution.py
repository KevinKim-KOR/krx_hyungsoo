"""manual_execution 라우터 — execution_prep + ticket + record.

중복 라우트 포함: 1차 정의(실동작) + 2차 정의(shadowed) 모두 이동.
삭제 판단은 S5-6에서 수행.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend.utils import (
    KST,
    BASE_DIR,
    REPORTS_DIR,
    OPS_SUMMARY_PATH,
    logger,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
EXECUTION_PREP_LATEST_FILE = (
    BASE_DIR
    / "reports"
    / "live"
    / "execution_prep"
    / "latest"
    / "execution_prep_latest.json"
)
TICKET_LATEST_FILE_ME = (
    BASE_DIR
    / "reports"
    / "live"
    / "manual_execution_ticket"
    / "latest"
    / "manual_execution_ticket_latest.json"
)
RECORD_LATEST_FILE = (
    BASE_DIR
    / "reports"
    / "live"
    / "manual_execution_record"
    / "latest"
    / "manual_execution_record_latest.json"
)
DRAFT_DIR = BASE_DIR / "reports" / "live" / "manual_execution_record" / "draft"
DRAFT_LATEST_FILE = DRAFT_DIR / "latest" / "manual_execution_record_draft_latest.json"
ORDER_PLAN_EXPORT_LATEST_FILE = (
    BASE_DIR
    / "reports"
    / "live"
    / "order_plan_export"
    / "latest"
    / "order_plan_export_latest.json"
)

# Ensure Draft Dir
(DRAFT_DIR / "latest").mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class ExecutionPrepRequest(BaseModel):
    confirm_token: Optional[str] = None


class ManualExecutionItem(BaseModel):
    ticker: str
    side: str
    status: str  # EXECUTED | SKIPPED
    executed_qty: Optional[int] = 0
    note: Optional[str] = ""


class ManualExecutionRecordRequest(BaseModel):
    confirm_token: str
    items: List[ManualExecutionItem]


class RecordSubmitRequest(BaseModel):
    confirm_token: str
    items: List[Dict[str, Any]]
    filled_at: Optional[str] = None
    method: Optional[str] = "UI_MANUAL"
    evidence_note: Optional[str] = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
                f"# Manual Execution Ticket (BLOCKED)",
                f"**Plan ID**: {src.get('plan_id', 'UNKNOWN')}",
                f"**AsOf**: {ticket.get('asof', '')}",
                f"**Status**: ❌ BLOCKED",
                f"**Reason**: {ticket.get('reason', '')}",
            ]
        else:
            lines = [
                f"# Manual Execution Ticket",
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
                "> **Operator Instruction**: Copy input string, paste to HTS. Check each order as executed."
            )

        md_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"P146.8C: Ticket MD regenerated with plan_id={src.get('plan_id')}")
    except Exception as e:
        logger.warning(f"P146.8C: Ticket MD regen failed: {e}")


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


# ===========================================================================
# 1차 정의 (실동작)
# ===========================================================================

# --- Execution Prep (P112) ------------------------------------------------


@router.get("/api/execution_prep/latest", summary="Execution Prep 최신 조회")
def get_execution_prep_latest():
    """Execution Prep Latest (P112)"""
    if not EXECUTION_PREP_LATEST_FILE.exists():
        return {
            "status": "empty",
            "schema": "EXECUTION_PREP_V1",
            "data": None,
            "error": "No execution prep generated yet.",
        }

    try:
        data = json.loads(EXECUTION_PREP_LATEST_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "EXECUTION_PREP_V1",
            "data": data,
            "error": None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/api/execution_prep/prepare", summary="Execution Prep 생성 (Human Gate)")
def prepare_execution(
    request: ExecutionPrepRequest,
    confirm: bool = Query(False),
    force: bool = Query(False),
):
    """Prepare Execution (P112) - Requires Confirm + Token"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail={"result": "BLOCKED", "reason": "CONFIRM_REQUIRED"},
        )

    try:
        from app.generate_execution_prep import generate_prep

        generate_prep(confirm_token=request.confirm_token, force=force)

        if EXECUTION_PREP_LATEST_FILE.exists():
            data = json.loads(EXECUTION_PREP_LATEST_FILE.read_text(encoding="utf-8"))
            return data
        else:
            return {"result": "FAIL", "reason": "Generation failed (No file)"}

    except ImportError as e:
        logger.error(f"Prep import error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"result": "FAILED", "reason": f"Import error: {e}"},
        )
    except Exception as e:
        logger.error(f"Prep error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"result": "FAILED", "reason": str(e)},
        )


# --- Manual Execution Ticket (P113-A) ------------------------------------


@router.get(
    "/api/manual_execution_ticket/latest",
    summary="Manual Execution Ticket 최신 조회",
)
def get_manual_execution_ticket_latest():
    """Manual Execution Ticket Latest (P113-A)"""
    if not TICKET_LATEST_FILE_ME.exists():
        return {
            "status": "empty",
            "schema": "MANUAL_EXECUTION_TICKET_V1",
            "data": None,
            "error": "No ticket generated yet.",
        }
    try:
        data = json.loads(TICKET_LATEST_FILE_ME.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "MANUAL_EXECUTION_TICKET_V1",
            "data": data,
            "error": None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post(
    "/api/manual_execution_ticket/regenerate",
    summary="Manual Execution Ticket 재생성",
)
def regenerate_manual_execution_ticket(confirm: bool = Query(False)):
    """Regenerate Manual Execution Ticket (P113-A / P146.6/8) - Aligns to Export"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail={"result": "BLOCKED", "reason": "CONFIRM_REQUIRED"},
        )

    try:
        from app.generate_manual_execution_ticket import generate_ticket

        generate_ticket()

        if not TICKET_LATEST_FILE_ME.exists():
            return {"result": "FAIL", "reason": "Generation failed (No file)"}

        data = json.loads(TICKET_LATEST_FILE_ME.read_text(encoding="utf-8"))

        # P146.6/8: Patch plan_id & token to match Export (SSOT alignment)
        export_path = (
            REPORTS_DIR
            / "live"
            / "order_plan_export"
            / "latest"
            / "order_plan_export_latest.json"
        )
        if export_path.exists():
            try:
                export_data = json.loads(export_path.read_text(encoding="utf-8"))
                export_plan_id = export_data.get("source", {}).get("plan_id")
                if export_plan_id:
                    old_plan_id = data.get("source", {}).get("plan_id")
                    data["source"]["plan_id"] = export_plan_id
                    data["source"]["_aligned_from"] = "export"
                    data["source"]["_original_prep_plan_id"] = old_plan_id

                    # P146.8C: Copy confirm_token
                    export_token = export_data.get("human_confirm", {}).get(
                        "confirm_token"
                    ) or export_data.get("source", {}).get("confirm_token")
                    if export_token:
                        data["source"]["confirm_token"] = export_token

                    # Save patched ticket back
                    TICKET_LATEST_FILE_ME.write_text(
                        json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )

                    # P146.8C: Regenerate MD
                    _regen_ticket_md(data)

                    logger.info(
                        f"P146.8: Ticket regen patched {old_plan_id} -> {export_plan_id}"
                    )
            except Exception as e:
                logger.warning(f"P146.8: Export read failed, keeping prep plan_id: {e}")

        return data

    except ImportError as e:
        logger.error(f"Ticket import error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"result": "FAILED", "reason": f"Import error: {e}"},
        )
    except Exception as e:
        logger.error(f"Ticket error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"result": "FAILED", "reason": str(e)},
        )


# --- Manual Execution Record (P113-A) ------------------------------------


@router.get(
    "/api/manual_execution_record/latest",
    summary="Manual Execution Record 최신 조회",
)
def get_manual_execution_record_latest():
    """Manual Execution Record Latest (P113-A)"""
    if not RECORD_LATEST_FILE.exists():
        return {
            "status": "empty",
            "schema": "MANUAL_EXECUTION_RECORD_V1",
            "data": None,
            "error": "No record generated yet.",
        }
    try:
        data = json.loads(RECORD_LATEST_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "MANUAL_EXECUTION_RECORD_V1",
            "data": data,
            "error": None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post(
    "/api/manual_execution_record/draft",
    summary="Draft Record 생성 (Server-Side)",
)
def generate_draft_record():
    """Generate Manual Execution Record Draft (Server-Side) - P146.2 / P161"""
    try:
        import hashlib

        # 1. Paths (local to avoid NameError)
        _ticket_path = (
            REPORTS_DIR
            / "live"
            / "manual_execution_ticket"
            / "latest"
            / "manual_execution_ticket_latest.json"
        )
        _export_path = (
            REPORTS_DIR
            / "live"
            / "order_plan_export"
            / "latest"
            / "order_plan_export_latest.json"
        )
        _prep_path = (
            REPORTS_DIR
            / "live"
            / "execution_prep"
            / "latest"
            / "execution_prep_latest.json"
        )
        _summary_path = (
            REPORTS_DIR / "ops" / "summary" / "latest" / "ops_summary_latest.json"
        )
        _draft_path = (
            REPORTS_DIR
            / "live"
            / "manual_execution_record"
            / "draft"
            / "latest"
            / "manual_execution_record_draft_latest.json"
        )
        _draft_path.parent.mkdir(parents=True, exist_ok=True)

        # 2. Load artifacts
        ticket = _load_json(_ticket_path)
        export = _load_json(_export_path)

        if not ticket or not export:
            return {
                "result": "BLOCKED",
                "reason": "Missing Ticket or Order Plan Export. Cannot generate draft.",
            }

        # Optional summary check (non-blocking)
        summary = _load_json(_summary_path)

        # 3. Load Prep (optional for linkage)
        prep = _load_json(_prep_path)
        if not prep:
            prep = {}

        # 4. Validate Linkage — P146.5/P146.6 Fail-Closed (ticket+export gate)
        ticket_plan_id = ticket.get("source", {}).get("plan_id")
        export_plan_id = export.get("source", {}).get("plan_id")

        # Gate: ticket and export must agree. Prep is upstream/informational.
        if ticket_plan_id and export_plan_id and ticket_plan_id != export_plan_id:
            return {
                "result": "BLOCKED",
                "reason": "PLAN_ID_MISMATCH",
                "detail": {"ticket": ticket_plan_id, "export": export_plan_id},
                "guidance": "plan_id가 일치하지 않습니다. TICKET 재생성 버튼을 눌러 Export에 맞춰주세요.",
            }

        # P161: Determine exec_mode
        _exec_mode = "LIVE"
        if OPS_SUMMARY_PATH.exists():
            try:
                _summ = json.loads(OPS_SUMMARY_PATH.read_text(encoding="utf-8"))
                _exec_mode = _summ.get("manual_loop", {}).get("mode", "LIVE")
            except Exception:
                pass
        try:
            from app.utils.portfolio_normalize import load_asof_override

            _override = load_asof_override()
            if _override.get("enabled", False):
                _exec_mode = "DRY_RUN"
            _replay_date = _override.get("asof_kst", "")
        except Exception:
            _replay_date = ""

        # P161: Compute ticket_id (never null)
        _ticket_id = ticket.get("ticket_id") or ticket.get("source", {}).get("plan_id")
        if not _ticket_id:
            _ticket_id = f"ticket-{export_plan_id or 'UNKNOWN'}"

        # P161: Compute idempotency_key (never empty)
        _order_plan_key = export.get("source", {}).get("order_plan_key", "")
        if not _order_plan_key:
            # Fallback: construct from plan_id:decision:payload_sha256
            _op_plan_id = export.get("source", {}).get("plan_id", "")
            _op_decision = export.get("decision", "")
            _op_sha = export.get("integrity", {}).get("payload_sha256", "")
            _order_plan_key = f"{_op_plan_id}:{_op_decision}:{_op_sha}"
        _idemp_raw = (
            f"{export_plan_id or ''}:{_order_plan_key}:{_exec_mode}:{_replay_date}"
        )
        _idempotency_key = hashlib.sha256(_idemp_raw.encode("utf-8")).hexdigest()
        if not _idempotency_key:
            raise ValueError("Failed to compute idempotency_key — cannot be empty")

        # 5. Construct Draft (P161: Always overwrite)
        items = []
        for order in export.get("orders", []):
            items.append(
                {
                    "ticker": order.get("ticker"),
                    "side": order.get("side"),
                    "status": "EXECUTED",
                    "qty_planned": order.get("qty", 0),
                    "executed_qty": order.get("qty", 0),
                    "avg_price": None,
                    "note": "",
                }
            )

        draft = {
            "schema": "MANUAL_EXECUTION_RECORD_DRAFT_V1",
            "asof": datetime.now(KST).isoformat(),
            "source_refs": {"prep_ref": prep.get("source", {}).get("order_plan_ref")},
            "linkage": {
                "prep_plan_id": prep.get("source", {}).get("plan_id"),
                "ticket_plan_id": ticket_plan_id,
                "export_plan_id": export_plan_id,
                "ticket_id": _ticket_id,
            },
            "items": items,
            "dedupe": {"idempotency_key": _idempotency_key},
            "exec_mode": _exec_mode,
        }

        # 6. Sanitize & Save (Always overwrite)
        def recursive_sanitize(obj):
            if isinstance(obj, dict):
                return {k: recursive_sanitize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [recursive_sanitize(v) for v in obj]
            elif isinstance(obj, str):
                return obj.replace("\\", "/")
            else:
                return obj

        sanitized_draft = recursive_sanitize(draft)
        _draft_path.write_text(
            json.dumps(sanitized_draft, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return {
            "result": "OK",
            "path": str(_draft_path),
            "count": len(items),
            "ticket_id": _ticket_id,
            "idempotency_key": _idempotency_key,
        }

    except Exception as e:
        logger.error(f"Draft Gen Error: {e}")
        return {"result": "ERROR", "reason": str(e)}


@router.get("/api/manual_execution_record/draft", summary="Draft Record 다운로드")
def get_draft_record():
    """Get Latest Draft Record JSON"""
    if not DRAFT_LATEST_FILE.exists():
        raise HTTPException(status_code=404, detail="No Draft Found")

    return FileResponse(
        path=DRAFT_LATEST_FILE,
        media_type="application/json",
        filename="manual_execution_record_draft.json",
    )


# --- /api/manual_execution_record/submit (유일한 정의) ---


@router.post("/api/manual_execution_record/submit")
async def submit_execution_record_api(
    payload: Dict[str, Any] = Body(...),
    confirm: bool = Query(False),
):
    """
    P162: Submit Execution Record — Draft-as-SSOT.
    Loads the server-side draft file, copies ticket_id/idempotency_key/items
    directly, and writes the final record. DRY_RUN/REPLAY structurally cannot
    produce TOKEN_MISMATCH. If BLOCKED, returns HTTP 409 (not 200).
    """
    import shutil

    if not confirm:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "result": "BLOCKED",
                "reason": "CONFIRM_REQUIRED",
            },
        )

    # --- 1. Determine exec_mode (SSOT) ---
    _exec_mode = "LIVE"
    if OPS_SUMMARY_PATH.exists():
        try:
            _summ = json.loads(OPS_SUMMARY_PATH.read_text(encoding="utf-8"))
            _exec_mode = _summ.get("manual_loop", {}).get("mode", "LIVE")
        except Exception:
            pass
    try:
        from app.utils.portfolio_normalize import load_asof_override

        override_data = load_asof_override()
        if override_data.get("enabled", False):
            _exec_mode = "DRY_RUN"
    except Exception:
        pass

    # --- 2. Token validation (LIVE only) ---
    token = payload.get("confirm_token", "")

    if _exec_mode in ["DRY_RUN", "REPLAY"]:
        # Structurally bypass: no token comparison ever runs
        token = "DRY_RUN_AUTO"
    else:
        # LIVE: Fail-Closed token validation
        if not token:
            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "result": "BLOCKED",
                    "reason": "TOKEN_MISSING",
                    "message": "LIVE 모드에서는 confirm_token이 필요합니다.",
                },
            )
        try:
            _exp_path = (
                REPORTS_DIR
                / "live"
                / "order_plan_export"
                / "latest"
                / "order_plan_export_latest.json"
            )
            if _exp_path.exists():
                _exp = json.loads(_exp_path.read_text(encoding="utf-8"))
                _expected = _exp.get("human_confirm", {}).get(
                    "confirm_token"
                ) or _exp.get("source", {}).get("confirm_token")
                if _expected and token != _expected:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "ok": False,
                            "result": "BLOCKED",
                            "reason": "TOKEN_MISMATCH",
                            "plan_id": _exp.get("source", {}).get("plan_id"),
                            "message": "토큰이 Export의 confirm_token과 일치하지 않습니다.",
                        },
                    )
        except Exception:
            pass

    # --- 3. Load server-side Draft as SSOT ---
    try:
        _draft_path = (
            REPORTS_DIR
            / "live"
            / "manual_execution_record"
            / "draft"
            / "latest"
            / "manual_execution_record_draft_latest.json"
        )
        if not _draft_path.exists():
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "result": "BLOCKED",
                    "reason": "DRAFT_MISSING",
                    "message": "Draft 파일이 없습니다. 먼저 GENERATE DRAFT를 실행하세요.",
                },
            )

        draft = json.loads(_draft_path.read_text(encoding="utf-8"))

        # Extract from draft (never re-compute)
        draft_ticket_id = draft.get("linkage", {}).get("ticket_id")
        draft_idempotency_key = draft.get("dedupe", {}).get("idempotency_key", "")
        draft_items = draft.get("items", [])
        draft_plan_id = draft.get("linkage", {}).get("export_plan_id") or draft.get(
            "linkage", {}
        ).get("prep_plan_id")

        # Validate: items must not be empty
        if not draft_items:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "result": "BLOCKED",
                    "reason": "DRAFT_INCOMPLETE",
                    "message": "Draft의 items가 비어있습니다.",
                },
            )

        # Validate: idempotency_key must not be empty
        if not draft_idempotency_key:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "result": "BLOCKED",
                    "reason": "DRAFT_INCOMPLETE",
                    "message": "Draft의 idempotency_key가 비어있습니다.",
                },
            )

        # --- 4. Build final Record from draft ---
        record = {
            "schema": "MANUAL_EXECUTION_RECORD_V1",
            "asof": datetime.now(KST).isoformat(),
            "source": {
                "prep_ref": draft.get("source_refs", {}).get("prep_ref"),
                "ticket_ref": "reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.json",
                "confirm_token": token,
                "plan_id": draft_plan_id,
            },
            "ticket_id": draft_ticket_id,
            "idempotency_key": draft_idempotency_key,
            "exec_mode": _exec_mode,
            "decision": "EXECUTED",
            "reason": "SUBMITTED_VIA_DRAFT",
            "reason_detail": f"exec_mode={_exec_mode}, items={len(draft_items)}",
            "summary": {
                "orders_total": len(draft_items),
                "executed_count": sum(
                    1 for i in draft_items if i.get("status") == "EXECUTED"
                ),
                "skipped_count": sum(
                    1 for i in draft_items if i.get("status") == "SKIPPED"
                ),
            },
            "items": draft_items,
            "evidence_refs": [
                "reports/live/execution_prep/latest/execution_prep_latest.json",
                "reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.json",
            ],
        }

        # --- 5. Save Record (atomic write) ---
        _record_dir = REPORTS_DIR / "live" / "manual_execution_record" / "latest"
        _record_dir.mkdir(parents=True, exist_ok=True)
        _record_path = _record_dir / "manual_execution_record_latest.json"

        _temp = _record_path.parent / f".tmp_{_record_path.name}"
        _temp.write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        shutil.move(str(_temp), str(_record_path))

        # Snapshot
        _snap_dir = REPORTS_DIR / "live" / "manual_execution_record" / "snapshots"
        _snap_dir.mkdir(parents=True, exist_ok=True)
        _snap_name = f"record_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}.json"
        shutil.copy(str(_record_path), str(_snap_dir / _snap_name))

        logger.info(
            f"[P162] Record saved: decision={record['decision']}, exec_mode={_exec_mode}, idempotency_key={draft_idempotency_key[:16]}..."
        )

        # --- 6. Return (success = 200, blocked = 409) ---
        if record["decision"] == "BLOCKED":
            return JSONResponse(status_code=409, content=record)

        return {"ok": True, "record_decision": record["decision"], **record}

    except Exception as e:
        logger.error(f"Record Submit failed: {e}")
        import traceback

        traceback.print_exc()
        err_str = str(e)
        if "plan_id" in err_str.lower() or "mismatch" in err_str.lower():
            reason = "PLAN_MISMATCH"
        elif "draft" in err_str.lower() or "incomplete" in err_str.lower():
            reason = "DRAFT_INCOMPLETE"
        else:
            reason = err_str
        return JSONResponse(
            status_code=500,
            content={"ok": False, "result": "FAILED", "reason": reason},
        )
