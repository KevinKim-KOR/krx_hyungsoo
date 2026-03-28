"""tickets 라우터 — 티켓 CRUD + 상태 보드 + reaper."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.utils import (
    KST,
    BASE_DIR,
    STATE_DIR,
    logger,
)

router = APIRouter()

TICKETS_DIR = STATE_DIR / "tickets"
TICKET_RESULTS_FILE = TICKETS_DIR / "ticket_results.jsonl"
REAPER_LATEST_FILE = (
    BASE_DIR
    / "reports"
    / "ops"
    / "tickets"
    / "reaper"
    / "latest"
    / "reaper_latest.json"
)


# --- Helpers ---


def read_jsonl(path: Path) -> List[Dict]:
    """JSONL 파일 읽기"""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    return [json.loads(line) for line in lines if line.strip()]


def get_ticket_current_status(request_id: str) -> str:
    """티켓의 현재 상태 조회 (State Machine)"""
    requests = read_jsonl(TICKETS_DIR / "ticket_requests.jsonl")
    results = read_jsonl(TICKET_RESULTS_FILE)

    req = next((r for r in requests if r.get("request_id") == request_id), None)
    if not req:
        return "NOT_FOUND"

    req_results = [r for r in results if r.get("request_id") == request_id]
    if not req_results:
        return "OPEN"

    latest = max(req_results, key=lambda x: x.get("processed_at", ""))
    return latest.get("status", "OPEN")


def append_ticket_result(result: Dict):
    """결과 Append (Append-only)"""
    TICKETS_DIR.mkdir(parents=True, exist_ok=True)
    with open(TICKET_RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")


# --- Models ---


class TicketSubmit(BaseModel):
    request_type: str
    payload: dict
    trace_id: Optional[str] = None


class TicketConsume(BaseModel):
    request_id: str
    processor_id: str = "manual"


class TicketComplete(BaseModel):
    request_id: str
    status: str
    message: str = ""
    processor_id: str = "manual"
    artifacts: List[str] = []


class ReaperRunRequest(BaseModel):
    threshold_seconds: int = 86400
    max_clean: int = 50


# --- Routes ---


@router.post("/api/tickets", summary="Ticket 생성 (Append-only)")
def create_ticket(ticket: TicketSubmit):
    """티켓 생성 (TICKET_SUBMIT_V1 → TICKET_REQUEST_V1 변환 후 저장)"""
    logger.info(f"티켓 생성 요청: {ticket.request_type}")

    valid_types = ["REQUEST_RECONCILE", "REQUEST_REPORTS", "ACKNOWLEDGE"]
    if ticket.request_type not in valid_types:
        return JSONResponse(
            status_code=400,
            content={
                "result": "FAIL",
                "message": (f"Invalid request_type. Must be one of {valid_types}"),
            },
        )

    request_id = str(uuid.uuid4())
    requested_at = datetime.now(KST).isoformat()

    ticket_request = {
        "schema": "TICKET_REQUEST_V1",
        "request_id": request_id,
        "requested_at": requested_at,
        "request_type": ticket.request_type,
        "payload": ticket.payload,
        "status": "OPEN",
        "trace_id": ticket.trace_id,
    }

    TICKETS_DIR.mkdir(parents=True, exist_ok=True)
    tickets_file = TICKETS_DIR / "ticket_requests.jsonl"

    try:
        with open(tickets_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(ticket_request, ensure_ascii=False) + "\n")

        logger.info(f"티켓 저장 완료: {request_id}")
        return {
            "result": "OK",
            "request_id": request_id,
            "requested_at": requested_at,
            "status": "OPEN",
            "appended": True,
        }
    except Exception as e:
        logger.error(f"티켓 저장 실패: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "result": "FAIL",
                "message": str(e),
                "appended": False,
            },
        )


@router.post("/api/tickets/consume", summary="티켓 소비 (OPEN → IN_PROGRESS)")
def consume_ticket(data: TicketConsume):
    """티켓을 IN_PROGRESS 상태로 전이"""
    logger.info(f"티켓 소비 요청: {data.request_id}")

    current = get_ticket_current_status(data.request_id)

    if current == "NOT_FOUND":
        return JSONResponse(
            status_code=404,
            content={"result": "FAIL", "message": "Ticket not found"},
        )

    if current != "OPEN":
        return JSONResponse(
            status_code=409,
            content={
                "result": "CONFLICT",
                "message": (f"Cannot consume. Current status: {current}"),
                "current_status": current,
            },
        )

    result = {
        "schema": "TICKET_RESULT_V1",
        "result_id": str(uuid.uuid4()),
        "request_id": data.request_id,
        "processed_at": datetime.now(KST).isoformat(),
        "status": "IN_PROGRESS",
        "processor_id": data.processor_id,
        "message": "티켓 처리 시작",
        "artifacts": [],
    }

    append_ticket_result(result)
    logger.info(f"티켓 소비 완료: {data.request_id} → IN_PROGRESS")

    return {
        "result": "OK",
        "request_id": data.request_id,
        "new_status": "IN_PROGRESS",
        "result_id": result["result_id"],
    }


@router.post(
    "/api/tickets/complete",
    summary="티켓 완료 (IN_PROGRESS → DONE/FAILED)",
)
def complete_ticket(data: TicketComplete):
    """티켓을 DONE 또는 FAILED 상태로 전이"""
    logger.info(f"티켓 완료 요청: {data.request_id} → {data.status}")

    if data.status not in ["DONE", "FAILED"]:
        return JSONResponse(
            status_code=400,
            content={
                "result": "FAIL",
                "message": "status must be DONE or FAILED",
            },
        )

    current = get_ticket_current_status(data.request_id)

    if current == "NOT_FOUND":
        return JSONResponse(
            status_code=404,
            content={"result": "FAIL", "message": "Ticket not found"},
        )

    if current != "IN_PROGRESS":
        return JSONResponse(
            status_code=409,
            content={
                "result": "CONFLICT",
                "message": (f"Cannot complete. Current status: {current}"),
                "current_status": current,
            },
        )

    result = {
        "schema": "TICKET_RESULT_V1",
        "result_id": str(uuid.uuid4()),
        "request_id": data.request_id,
        "processed_at": datetime.now(KST).isoformat(),
        "status": data.status,
        "processor_id": data.processor_id,
        "message": data.message,
        "artifacts": data.artifacts,
    }

    append_ticket_result(result)
    logger.info(f"티켓 완료: {data.request_id} → {data.status}")

    return {
        "result": "OK",
        "request_id": data.request_id,
        "new_status": data.status,
        "result_id": result["result_id"],
    }


@router.get("/api/tickets/latest", summary="티켓 상태 보드 (TICKETS_BOARD_V1)")
def get_tickets_board():
    """티켓 상태 보드 조회 (Synthesized View)"""
    requests = read_jsonl(TICKETS_DIR / "ticket_requests.jsonl")
    results = read_jsonl(TICKET_RESULTS_FILE)

    board = []
    for req in requests:
        rid = req.get("request_id")

        req_results = [r for r in results if r.get("request_id") == rid]
        if req_results:
            latest = max(req_results, key=lambda x: x.get("processed_at", ""))
            current_status = latest.get("status", "OPEN")
            last_message = latest.get("message", "")
            last_processed_at = latest.get("processed_at", "")
        else:
            current_status = "OPEN"
            last_message = ""
            last_processed_at = None

        board.append(
            {
                "request_id": rid,
                "requested_at": req.get("requested_at"),
                "request_type": req.get("request_type"),
                "payload": req.get("payload"),
                "trace_id": req.get("trace_id"),
                "current_status": current_status,
                "last_message": last_message,
                "last_processed_at": last_processed_at,
            }
        )

    board.sort(key=lambda x: x.get("requested_at", ""), reverse=True)

    return {
        "status": "ready",
        "schema": "TICKETS_BOARD_V1",
        "asof": datetime.now(KST).isoformat(),
        "row_count": len(board),
        "rows": board,
        "error": None,
    }


# --- Reaper ---


@router.get("/api/tickets/reaper/latest", summary="Ticket Reaper 최신 조회")
def get_ticket_reaper_latest():
    """Ticket Reaper Latest (C-P.43)"""
    if not REAPER_LATEST_FILE.exists():
        return {
            "schema": "TICKET_REAPER_REPORT_V1",
            "asof": datetime.now(KST).isoformat(),
            "decision": "NONE",
            "message": "No reaper report yet",
        }

    try:
        data = json.loads(REAPER_LATEST_FILE.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        return {
            "schema": "TICKET_REAPER_REPORT_V1",
            "asof": datetime.now(KST).isoformat(),
            "decision": "ERROR",
            "error": str(e),
        }


@router.post("/api/tickets/reaper/run", summary="Ticket Reaper 실행")
def run_ticket_reaper_api(
    data: ReaperRunRequest = ReaperRunRequest(),
):
    """Ticket Reaper Run (C-P.43)"""
    try:
        from app.run_ticket_reaper import run_ticket_reaper

        result = run_ticket_reaper(
            threshold_seconds=data.threshold_seconds,
            max_clean=data.max_clean,
        )
        return result
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "result": "FAILED",
                "reason": f"Import error: {e}",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"result": "FAILED", "reason": str(e)},
        )
