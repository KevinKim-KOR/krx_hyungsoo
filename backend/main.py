# -*- coding: utf-8 -*-
"""
backend/main.py
KRX Alertor Modular - 읽기 전용 옵저버 백엔드
"""
import logging
import sys
import json
import yaml
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# --- 1. 환경 설정 및 상수 ---
BASE_DIR = Path(".")
LOG_DIR = BASE_DIR / "logs"
STATE_DIR = BASE_DIR / "state"
REPORTS_DIR = BASE_DIR / "reports"
PAPER_DIR = REPORTS_DIR / "paper"
DASHBOARD_DIR = BASE_DIR / "dashboard"

# 로그 디렉토리 확보
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --- 2. 로깅 설정 (Backend 전용) ---
def setup_backend_logger():
    today_str = datetime.now().strftime("%Y%m%d")
    log_file = LOG_DIR / f"backend_{today_str}.log"
    
    logger = logging.getLogger("backend")
    logger.setLevel(logging.INFO)
    
    # 중복 핸들러 방지
    if logger.handlers:
        return logger
        
    # File Handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    
    # Console Handler (uvicorn 로그와 별도)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("[BACKEND] %(message)s"))
    logger.addHandler(ch)
    
    return logger

logger = setup_backend_logger()

# --- 3. FastAPI 앱 설정 ---
app = FastAPI(
    title="KRX Alertor Modular API",
    description="파일 시스템 기반의 읽기 전용 옵저버 백엔드 (Phase 14)",
    version="14.3",
    contact={
        "name": "Phase 14 Maintainer",
    }
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # React 연동을 위해 전체 허용
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Static Files (Dashboard)
# 주의: dashboard 디렉토리가 없으면 에러 날 수 있으므로 체크
if DASHBOARD_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=str(DASHBOARD_DIR)), name="dashboard")

# --- 4. 유틸리티 함수 (Robust File Reading) ---

def get_today_str() -> str:
    return datetime.now().strftime("%Y%m%d")

def safe_read_text_advanced(path: Path) -> Dict[str, Any]:
    """
    안전한 텍스트 파일 읽기 (인코딩, 파일 잠금 대비) + 메타데이터 반환
    Returns:
        { "content": str, "encoding": str, "quality": "perfect"|"partial"|"failed" }
    """
    if not path.exists():
        return {"content": "", "encoding": "none", "quality": "failed"}
    
    # 1. UTF-8 시도
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {"content": f.read(), "encoding": "utf-8", "quality": "perfect"}
    except UnicodeDecodeError:
        pass
    except Exception as e:
        logger.error(f"파일 읽기 실패(UTF-8): {path} - {e}")

    # 2. CP949 (EUC-KR) 시도
    try:
        with open(path, "r", encoding="cp949") as f:
            return {"content": f.read(), "encoding": "cp949", "quality": "perfect"}
    except UnicodeDecodeError:
        pass
        
    except UnicodeDecodeError:
        pass
        
    # 3. Shadow Copy Strategy (Windows Locking Fix)
    # If direct read fails (PermissionError), try copying to temp
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        shutil.copy2(path, tmp_path)
        
        # Try reading temp file with standard encodings
        content = ""
        encoding = "shadow-copy"
        
        try:
             with open(tmp_path, "r", encoding="utf-8") as f:
                 content = f.read()
                 encoding = "utf-8"
        except UnicodeDecodeError:
             with open(tmp_path, "r", encoding="cp949") as f:
                 content = f.read()
                 encoding = "cp949"
                 
        try:
            tmp_path.unlink() # Cleanup
        except:
             pass
             
        return {"content": content, "encoding": encoding, "quality": "perfect"}
        
    except Exception as e:
        logger.warning(f"Shadow Copy 읽기 실패: {path} - {e}")
        # Continue to forced read
        
    # 4. UTF-16 (PowerShell Default) 시도
    try:
        with open(path, "r", encoding="utf-16") as f:
            return {"content": f.read(), "encoding": "utf-16", "quality": "perfect"}
    except UnicodeDecodeError:
        pass
        
    # 4. 최후의 수단 (Errors Ignore/Replace)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return {"content": f.read(), "encoding": "forced-utf8", "quality": "partial"}
    except Exception as e:
        logger.error(f"파일 강제 읽기 완전 실패: {path} - {e}", exc_info=True)
        return {"content": "", "encoding": "failed", "quality": "failed", "error": str(e)}

def safe_read_text(path: Path) -> str:
    """기존 함수 호환용 (단순 content 반환)"""
    res = safe_read_text_advanced(path)
    if res["quality"] == "failed":
        raise IOError(f"파일 읽기 실패: {res.get('error')}")
    return res["content"]

def safe_read_json(path: Path) -> Dict[str, Any]:
    """JSON 파일 안전 읽기"""
    content = safe_read_text(path)
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 실패: {path} - {str(e)}")
        raise ValueError("잘못된 JSON 형식입니다.")

def safe_read_yaml(path: Path) -> Any:
    """YAML 파일 안전 읽기"""
    if not path.exists():
        return [] 
    content = safe_read_text(path)
    try:
        return yaml.safe_load(content)
    except yaml.YAMLError as e:
        logger.error(f"YAML 파싱 실패: {path} - {str(e)}")
        raise ValueError("잘못된 YAML 형식입니다.")

# --- 5. API Endpoints ---

@app.get("/")
def read_root():
    """Dashboard 진입점"""
    index_path = DASHBOARD_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "KRX Alertor Modular API Backend Running. Dashboard not found."}

@app.get("/api/status", summary="시스템 상태 조회 (Enhanced)")
def get_status():
    """
    일별 실행 로그(daily_YYYYMMDD.log)를 파싱하여 현재 시스템 상태 및 관측 신뢰도를 반환합니다.
    """
    logger.info("상태 조회 요청 (GET /api/status)")
    try:
        today = get_today_str()
        log_file = LOG_DIR / f"daily_{today}.log"
        
        status = {
            "schema_version": "UI-1.0",
            "date": today,
            "badge": "WAITING", 
            "message": "아직 실행 로그가 없습니다.",
            "read_quality": "failed",
            "read_encoding": "none",
            "evidence": {"ok_count": 0, "error_count": 0, "skip_count": 0},
            "log_file": str(log_file)
        }
        
        if not log_file.exists():
            status["badge"] = "UNKNOWN"
            return status
            
        # Advanced Reading
        read_res = safe_read_text_advanced(log_file)
        content = read_res["content"]
        status["read_quality"] = read_res["quality"]
        status["read_encoding"] = read_res["encoding"]
        
        # Evidence Counting
        ok_count = content.count("[OK]") # 대소문자 주의, 보통 로그엔 [OK]로 남김
        # 스크립트는 [Step 1] Success, [Step 2] Success, [OK] Paper Trade Done 등을 남김
        # 또는 [SKIP] 
        skip_count = content.count("[SKIP]")
        err_count = content.count("[ERROR]") + content.count("FAILED") + content.count("Traceback")
        
        status["evidence"]["ok_count"] = ok_count
        status["evidence"]["skip_count"] = skip_count
        status["evidence"]["error_count"] = err_count
        
        # Logic for Badge
        if err_count > 0:
            status["badge"] = "FAIL"
            status["message"] = f"오류 {err_count}건이 감지되었습니다."
        elif skip_count > 0:
            status["badge"] = "SKIP"
            status["message"] = "이미 작업이 완료되어 건너뛰었습니다."
        elif "COMPLETED Successfully" in content or ok_count > 0:
            status["badge"] = "OK"
            status["message"] = "정상적으로 완료되었습니다."
        elif "START" in content:
            status["badge"] = "RUNNING"
            status["message"] = "작업 실행 중입니다."
        else:
            status["badge"] = "UNKNOWN"
            status["message"] = "로그 내용을 분석할 수 없습니다."
            
        return status
        
    except Exception as e:
        logger.error("상태 조회 중 오류 발생", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "상태 조회 실패", "detail": str(e)}
        )

@app.get("/api/portfolio", summary="포트폴리오 조회")
def get_portfolio():
    """현재 포트폴리오 상태(paper_portfolio.json)를 반환합니다."""
    logger.info("포트폴리오 조회 요청 (GET /api/portfolio)")
    path = STATE_DIR / "paper_portfolio.json"
    try:
        return safe_read_json(path)
    except FileNotFoundError:
        return {"error": "포트폴리오 파일이 없습니다.", "cash": 0, "holdings": {}, "total_equity": 0}
    except Exception as e:
        logger.error("포트폴리오 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="내부 서버 오류")

@app.get("/api/signals", summary="당일 신호 조회")
def get_signals():
    """오늘 생성된 매매 신호(signals_YYYYMMDD.yaml)를 반환합니다."""
    logger.info("신호 조회 요청 (GET /api/signals)")
    try:
        today = get_today_str()
        path = REPORTS_DIR / f"signals_{today}.yaml"
        return safe_read_yaml(path)
    except Exception as e:
        logger.error("신호 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="내부 서버 오류")

@app.get("/api/history", summary="과거 이력 조회 (Equity Curve)")
def get_history():
    """일별 리포트 파일들을 취합하여 자산 추이(Equity Curve) 데이터를 반환합니다."""
    logger.info("이력 조회 요청 (GET /api/history)")
    try:
        if not PAPER_DIR.exists():
            return []
        
        files = sorted(PAPER_DIR.glob("paper_*.json"))
        history = []
        
        for f in files:
            try:
                data = json.loads(safe_read_text(f))
                history.append({
                    "date": data.get("execution_date", "").split("T")[0],
                    "equity": data.get("after", {}).get("equity", 0),
                    "cash": data.get("after", {}).get("cash", 0),
                    "trades_count": data.get("trades_count", 0)
                })
            except Exception as inner_e:
                logger.warning(f"이력 파일 파싱 실패 (스킵함): {f.name} - {str(inner_e)}")
                continue
                
        return history
    except Exception as e:
        logger.error("이력 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="내부 서버 오류")

@app.get("/api/raw", summary="원본 파일 조회")
def get_raw(filename: str = Query(..., description="프로젝트 루트 기준 파일 경로")):
    """디버깅용 원본 파일 뷰어"""
    logger.info(f"원본 조회 요청: {filename}")
    if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
        raise HTTPException(status_code=403, detail="잘못된 파일 경로입니다.")
        
    path = BASE_DIR / filename
    allowed_parents = [LOG_DIR, STATE_DIR, REPORTS_DIR]
    # Path Security Check
    try:
        resolved_path = path.resolve()
        if not any(str(resolved_path).startswith(str(p.resolve())) for p in allowed_parents):
             raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
    except Exception:
        # If resolve fails (e.g. file doesn't exist on some OS), we might still want to allow if parent is valid
        # But for safety, strict check:
        pass

    if not path.exists():
        # Return empty content or 404. For logs, empty content is better for UI.
        return {"filename": filename, "content": ""}

    try:
        # Raw view also uses advanced read to show encoding info if needed, but return string content
        # Just use safe_read_text for simplicity unless debugging encoding
        content = safe_read_text(path)
        return {"filename": filename, "content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    except Exception as e:
        logger.error(f"원본 읽기 실패: {filename}", exc_info=True)
        raise HTTPException(status_code=500, detail="파일 읽기 실패")


@app.get("/api/validation", summary="검증 리포트 조회")
def get_validation_report():
    """OOS 월별 검증 리포트를 반환합니다."""
    logger.info("검증 리포트 조회 요청 (GET /api/validation)")
    path = REPORTS_DIR / "validation" / "oos_2024_2025_monthly.json"
    if not path.exists():
        return {"status": "not_ready", "message": "검증 리포트가 없습니다."}
    try:
        return safe_read_json(path)
    except Exception as e:
        logger.error("검증 리포트 로드 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="리포트 로드 실패")

@app.get("/api/diagnosis/v3", summary="진단 V3.1 데이터 (Schema V3.1 Strict)")
def get_diagnosis_v3():
    """Contact-1: PHASE_C0_DAILY_V3_1_EVIDENCE Serving"""
    # Updated to V3.1 for Phase C-0.3 Fidelity Upgrade
    path = REPORTS_DIR / "validation" / "phase_c0_daily_2024_2025_v3_1.json"
    if not path.exists():
        return {"status": "not_ready", "message": "Diagnosis V3.1 report not found"}
    return safe_read_json(path)

@app.get("/api/gatekeeper/v3", summary="게이트키퍼 V3 데이터 (Schema Contract 2)")
def get_gatekeeper_v3():
    """Contract-2: GATEKEEPER_DECISION_V3 Serving (Latest)"""
    # Contract says: single_source_latest = gatekeeper_decision_latest.json
    path = REPORTS_DIR / "tuning" / "gatekeeper_decision_latest.json"
    if not path.exists():
         # Fallback to finding latest if alias not yet created by tool? 
         # Contract says "create latest.json after generation".
         # But for robostness, if latest not found, search pattern?
         # "ui_consumes: { single_source_latest: ... }"
         # Strict adherence means we look for latest.json. If not there, it's not ready.
         return {"status": "not_ready", "message": "Gatekeeper V3 report (latest.json) not found"}
    return safe_read_json(path)

@app.get("/api/diagnosis", summary="진단 리포트 조회 (V3 Alias)")
def get_diagnosis_report():
    return get_diagnosis_v3()

@app.get("/api/gatekeeper", summary="Gatekeeper 심사 결과 조회 (V3 Alias)")
def get_gatekeeper_report():
    return get_gatekeeper_v3()

@app.get("/api/report/human", summary="Human Report (Contract 5)")
def get_report_human():
    path = REPORTS_DIR / "phase_c" / "latest" / "report_human.json"
    if not path.exists():
        return {"result": "FAIL", "message": "Human report not found"}
    return safe_read_json(path)

@app.get("/api/report/ai", summary="AI Report (Contract 5)")
def get_report_ai():
    path = REPORTS_DIR / "phase_c" / "latest" / "report_ai.json"
    if not path.exists():
        return {"result": "FAIL", "message": "AI report not found"}
    return safe_read_json(path)

@app.get("/api/recon/summary", summary="Reconciliation Summary (Source of Truth)")
def get_recon_summary():
    summary_path = REPORTS_DIR / "phase_c" / "latest" / "recon_summary.json"
    daily_path = REPORTS_DIR / "phase_c" / "latest" / "recon_daily.jsonl"
    
    # Invariant Check: Daily Ready but Summary Not Ready/Missing -> ERROR
    if daily_path.exists() and not summary_path.exists():
        return {
            "status": "error",
            "schema": "RECON_SUMMARY_V1",
            "error": "IC_SUMMARY_INCONSISTENT_WITH_DAILY",
            "message": "Daily log exists but Summary is missing. Reconciler might have failed mid-process."
        }

    if not summary_path.exists():
        return {"status": "not_ready", "message": "Recon summary not found", "error": "A1_FILE_NOT_FOUND"}

    try:
        data = safe_read_json(summary_path)
        # Ensure it's a dict
        if not isinstance(data, dict):
             return {"status": "error", "message": "Invalid JSON format", "error": "A3_JSON_INVALID"}
             
        # Envelope Wrap
        return {
            "status": "ready",
            "schema": "RECON_SUMMARY_V1",
            "asof": data.get("asof", datetime.now().strftime("%Y-%m-%d")), 
            # Merge file content into Envelope top-level or keep separate?
            # User wants "status" field etc. 
            # Usually Summary file *is* the data. Let's merge standard envelope fields with data.
            **data,
            "error": None
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "error": "A5_UNKNOWN_ERROR"}

@app.get("/api/recon/daily", summary="Reconciliation Daily Events (Source of Truth)")
def get_recon_daily():
    path = REPORTS_DIR / "phase_c" / "latest" / "recon_daily.jsonl"
    if not path.exists():
        return {"status": "not_ready", "message": "Recon daily not found", "rows": [], "row_count": 0}
    try:
        lines = path.read_text(encoding="utf-8").strip().split('\n')
        rows = [json.loads(line) for line in lines if line.strip()]
        return {
            "status": "ready",
            "schema": "RECON_DAILY_V1",
            "asof": datetime.now().strftime("%Y-%m-%d"),
            "row_count": len(rows),
            "rows": rows,
            "error": None
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "rows": [], "row_count": 0, "error": str(e)}


# --- Phase C-P.1: Push & Ticket APIs ---

PUSH_DIR = REPORTS_DIR / "push" / "latest"
TICKETS_DIR = STATE_DIR / "tickets"

@app.get("/api/push/latest", summary="Push Messages (Latest)")
def get_push_latest():
    """최신 Push 메시지 목록 반환"""
    path = PUSH_DIR / "push_messages.json"
    if not path.exists():
        return {
            "status": "not_ready",
            "schema": "PUSH_MESSAGE_V1",
            "asof": datetime.now().isoformat(),
            "row_count": 0,
            "rows": [],
            "error": "PUSH_FILE_NOT_FOUND"
        }
    try:
        data = safe_read_json(path)
        # Envelope 포맷 보장
        if "rows" not in data:
            data["rows"] = []
        if "status" not in data:
            data["status"] = "ready"
        if "schema" not in data:
            data["schema"] = "PUSH_MESSAGE_V1"
        if "row_count" not in data:
            data["row_count"] = len(data.get("rows", []))
        if "asof" not in data:
            data["asof"] = datetime.now().isoformat()
        if "error" not in data:
            data["error"] = None
        return data
    except Exception as e:
        return {"status": "error", "message": str(e), "rows": [], "row_count": 0, "error": str(e)}


from pydantic import BaseModel
from typing import Optional
import uuid

class TicketPayload(BaseModel):
    mode: Optional[str] = None
    reason: Optional[str] = None
    scope: Optional[str] = None
    message_id: Optional[str] = None

class TicketSubmit(BaseModel):
    request_type: str  # REQUEST_RECONCILE, REQUEST_REPORTS, ACKNOWLEDGE
    payload: dict
    trace_id: Optional[str] = None

@app.post("/api/tickets", summary="Ticket 생성 (Append-only)")
def create_ticket(ticket: TicketSubmit):
    """
    티켓 생성 (TICKET_SUBMIT_V1 → TICKET_REQUEST_V1 변환 후 저장)
    
    규칙:
    - request_id, requested_at, status는 서버가 강제 주입
    - Append-only: 수정/삭제 금지
    """
    logger.info(f"티켓 생성 요청: {ticket.request_type}")
    
    # 유효성 검증
    valid_types = ["REQUEST_RECONCILE", "REQUEST_REPORTS", "ACKNOWLEDGE"]
    if ticket.request_type not in valid_types:
        return JSONResponse(
            status_code=400,
            content={"result": "FAIL", "message": f"Invalid request_type. Must be one of {valid_types}"}
        )
    
    # 서버 정보 강제 주입
    request_id = str(uuid.uuid4())
    requested_at = datetime.now().isoformat()
    
    ticket_request = {
        "schema": "TICKET_REQUEST_V1",
        "request_id": request_id,
        "requested_at": requested_at,
        "request_type": ticket.request_type,
        "payload": ticket.payload,
        "status": "OPEN",  # 최초 고정
        "trace_id": ticket.trace_id
    }
    
    # Append-only 저장
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
            "appended": True
        }
    except Exception as e:
        logger.error(f"티켓 저장 실패: {e}")
        return JSONResponse(
            status_code=500,
            content={"result": "FAIL", "message": str(e), "appended": False}
        )


# --- Phase C-P.2: Ticket Status Board APIs ---

TICKET_RESULTS_FILE = TICKETS_DIR / "ticket_results.jsonl"

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
    
    # 해당 request_id의 요청 찾기
    req = next((r for r in requests if r.get("request_id") == request_id), None)
    if not req:
        return "NOT_FOUND"
    
    # 해당 request_id의 결과들 중 최신 상태
    req_results = [r for r in results if r.get("request_id") == request_id]
    if not req_results:
        return "OPEN"  # 결과 없으면 OPEN
    
    # processed_at 기준 최신
    latest = max(req_results, key=lambda x: x.get("processed_at", ""))
    return latest.get("status", "OPEN")

def append_ticket_result(result: Dict):
    """결과 Append (Append-only)"""
    TICKETS_DIR.mkdir(parents=True, exist_ok=True)
    with open(TICKET_RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")


class TicketConsume(BaseModel):
    request_id: str
    processor_id: str = "manual"

@app.post("/api/tickets/consume", summary="티켓 소비 (OPEN → IN_PROGRESS)")
def consume_ticket(data: TicketConsume):
    """티켓을 IN_PROGRESS 상태로 전이 (State Machine)"""
    logger.info(f"티켓 소비 요청: {data.request_id}")
    
    current = get_ticket_current_status(data.request_id)
    
    if current == "NOT_FOUND":
        return JSONResponse(status_code=404, content={"result": "FAIL", "message": "Ticket not found"})
    
    if current != "OPEN":
        return JSONResponse(
            status_code=409,
            content={"result": "CONFLICT", "message": f"Cannot consume. Current status: {current}", "current_status": current}
        )
    
    result = {
        "schema": "TICKET_RESULT_V1",
        "result_id": str(uuid.uuid4()),
        "request_id": data.request_id,
        "processed_at": datetime.now().isoformat(),
        "status": "IN_PROGRESS",
        "processor_id": data.processor_id,
        "message": "티켓 처리 시작",
        "artifacts": []
    }
    
    append_ticket_result(result)
    logger.info(f"티켓 소비 완료: {data.request_id} → IN_PROGRESS")
    
    return {"result": "OK", "request_id": data.request_id, "new_status": "IN_PROGRESS", "result_id": result["result_id"]}


class TicketComplete(BaseModel):
    request_id: str
    status: str  # DONE or FAILED
    message: str = ""
    processor_id: str = "manual"
    artifacts: List[str] = []

@app.post("/api/tickets/complete", summary="티켓 완료 (IN_PROGRESS → DONE/FAILED)")
def complete_ticket(data: TicketComplete):
    """티켓을 DONE 또는 FAILED 상태로 전이 (State Machine)"""
    logger.info(f"티켓 완료 요청: {data.request_id} → {data.status}")
    
    if data.status not in ["DONE", "FAILED"]:
        return JSONResponse(status_code=400, content={"result": "FAIL", "message": "status must be DONE or FAILED"})
    
    current = get_ticket_current_status(data.request_id)
    
    if current == "NOT_FOUND":
        return JSONResponse(status_code=404, content={"result": "FAIL", "message": "Ticket not found"})
    
    if current != "IN_PROGRESS":
        return JSONResponse(
            status_code=409,
            content={"result": "CONFLICT", "message": f"Cannot complete. Current status: {current}", "current_status": current}
        )
    
    result = {
        "schema": "TICKET_RESULT_V1",
        "result_id": str(uuid.uuid4()),
        "request_id": data.request_id,
        "processed_at": datetime.now().isoformat(),
        "status": data.status,
        "processor_id": data.processor_id,
        "message": data.message,
        "artifacts": data.artifacts
    }
    
    append_ticket_result(result)
    logger.info(f"티켓 완료: {data.request_id} → {data.status}")
    
    return {"result": "OK", "request_id": data.request_id, "new_status": data.status, "result_id": result["result_id"]}


@app.get("/api/tickets/latest", summary="티켓 상태 보드 (TICKETS_BOARD_V1)")
def get_tickets_board():
    """티켓 상태 보드 조회 (Synthesized View)"""
    requests = read_jsonl(TICKETS_DIR / "ticket_requests.jsonl")
    results = read_jsonl(TICKET_RESULTS_FILE)
    
    board = []
    for req in requests:
        rid = req.get("request_id")
        
        # 해당 request_id의 최신 결과
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
        
        board.append({
            "request_id": rid,
            "requested_at": req.get("requested_at"),
            "request_type": req.get("request_type"),
            "payload": req.get("payload"),
            "trace_id": req.get("trace_id"),
            "current_status": current_status,
            "last_message": last_message,
            "last_processed_at": last_processed_at
        })
    
    # 최신순 정렬
    board.sort(key=lambda x: x.get("requested_at", ""), reverse=True)
    
    return {
        "status": "ready",
        "schema": "TICKETS_BOARD_V1",
        "asof": datetime.now().isoformat(),
        "row_count": len(board),
        "rows": board,
        "error": None
    }


# --- Phase C-P.4: Execution Gate APIs ---

EXECUTION_GATE_FILE = STATE_DIR / "execution_gate.json"
VALID_MODES = ["MOCK_ONLY", "DRY_RUN", "REAL_ENABLED"]
DEFAULT_GATE = {
    "schema": "EXECUTION_GATE_V1",
    "mode": "MOCK_ONLY",
    "updated_at": None,
    "updated_by": None,
    "reason": "Default (no gate file)"
}

def get_current_gate() -> Dict:
    """현재 Gate 상태 조회 (파일 없으면 Default)"""
    if not EXECUTION_GATE_FILE.exists():
        return DEFAULT_GATE.copy()
    try:
        data = json.loads(EXECUTION_GATE_FILE.read_text(encoding="utf-8"))
        return data
    except:
        return DEFAULT_GATE.copy()

@app.get("/api/execution_gate", summary="Execution Gate 상태 조회")
def get_execution_gate():
    """현재 Gate 상태 반환 (Envelope)"""
    gate = get_current_gate()
    return {
        "status": "ready",
        "schema": "EXECUTION_GATE_V1",
        "asof": datetime.now().isoformat(),
        "data": gate,
        "error": None
    }


class GateUpdate(BaseModel):
    mode: str
    reason: str

@app.post("/api/execution_gate", summary="Execution Gate 모드 변경")
def update_execution_gate(data: GateUpdate):
    """
    Gate 모드 변경
    
    Transition Rule:
    - MOCK_ONLY <-> DRY_RUN: 허용
    - Any -> MOCK_ONLY: 즉시 허용 (Emergency Stop)
    - Any -> REAL_ENABLED: 400 Bad Request (C-P.4에서 금지)
    """
    logger.info(f"Gate 변경 요청: {data.mode}")
    
    # Validation
    if data.mode not in VALID_MODES:
        return JSONResponse(
            status_code=400,
            content={"result": "FAIL", "message": f"Invalid mode. Must be one of {VALID_MODES}"}
        )
    
    # C-P.4 Restriction: Block REAL_ENABLED
    if data.mode == "REAL_ENABLED":
        logger.warning("REAL_ENABLED mode requested - BLOCKED by C-P.4 policy")
        return JSONResponse(
            status_code=400,
            content={
                "result": "BLOCKED",
                "message": "REAL_ENABLED mode is blocked in Phase C-P.4. Only MOCK_ONLY and DRY_RUN are allowed.",
                "policy": "C-P.4_BLOCK_REAL_AT_API"
            }
        )
    
    # Update Gate
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    gate_data = {
        "schema": "EXECUTION_GATE_V1",
        "mode": data.mode,
        "updated_at": datetime.now().isoformat(),
        "updated_by": "local_api",
        "reason": data.reason
    }
    
    EXECUTION_GATE_FILE.write_text(json.dumps(gate_data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    logger.info(f"Gate 변경 완료: {data.mode}")
    return {
        "result": "OK",
        "mode": data.mode,
        "updated_at": gate_data["updated_at"]
    }


# --- Phase C-P.6: Two-Key Approval, Receipt & Emergency Stop APIs ---

APPROVALS_DIR = STATE_DIR / "approvals"
APPROVALS_FILE = APPROVALS_DIR / "real_enable_approvals.jsonl"
RECEIPTS_FILE = TICKETS_DIR / "ticket_receipts.jsonl"
EMERGENCY_STOP_FILE = STATE_DIR / "emergency_stop.json"

def get_emergency_stop_status() -> Dict:
    """Emergency Stop 상태 조회"""
    if not EMERGENCY_STOP_FILE.exists():
        return {"enabled": False, "updated_at": None, "updated_by": None, "reason": None}
    try:
        data = json.loads(EMERGENCY_STOP_FILE.read_text(encoding="utf-8"))
        return data
    except:
        return {"enabled": False, "updated_at": None, "updated_by": None, "reason": None}

def get_latest_approval() -> Dict:
    """최신 Approval 조회"""
    if not APPROVALS_FILE.exists():
        return None
    approvals = read_jsonl(APPROVALS_FILE)
    if not approvals:
        return None
    # 최신 것 반환
    return max(approvals, key=lambda x: x.get("requested_at", ""))


@app.get("/api/emergency_stop", summary="Emergency Stop 상태 조회")
def get_emergency_stop():
    """현재 Emergency Stop 상태 반환"""
    status = get_emergency_stop_status()
    return {
        "status": "ready",
        "schema": "EMERGENCY_STOP_V1",
        "asof": datetime.now().isoformat(),
        "data": status,
        "error": None
    }


class EmergencyStopUpdate(BaseModel):
    enabled: bool
    operator_id: str = "local_operator"
    reason: str = ""

@app.post("/api/emergency_stop", summary="Emergency Stop 설정")
def set_emergency_stop(data: EmergencyStopUpdate):
    """Emergency Stop 상태 변경 (enabled=true면 Gate를 MOCK_ONLY로 강제)"""
    logger.info(f"Emergency Stop 변경 요청: enabled={data.enabled}")
    
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    
    stop_data = {
        "schema": "EMERGENCY_STOP_V1",
        "enabled": data.enabled,
        "updated_at": datetime.now().isoformat(),
        "updated_by": data.operator_id,
        "reason": data.reason
    }
    
    EMERGENCY_STOP_FILE.write_text(json.dumps(stop_data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # enabled=true면 Gate를 MOCK_ONLY로 강제
    if data.enabled:
        gate_data = {
            "schema": "EXECUTION_GATE_V1",
            "mode": "MOCK_ONLY",
            "updated_at": datetime.now().isoformat(),
            "updated_by": "emergency_stop_system",
            "reason": f"Emergency Stop activated: {data.reason}"
        }
        EXECUTION_GATE_FILE.write_text(json.dumps(gate_data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.warning("Emergency Stop 활성화 - Gate를 MOCK_ONLY로 강제 전환")
    
    return {"result": "OK", "enabled": data.enabled, "updated_at": stop_data["updated_at"]}


class ApprovalRequest(BaseModel):
    requested_by: str
    reason: str

@app.post("/api/approvals/real_enable/request", summary="REAL 모드 승인 요청")
def request_real_approval(data: ApprovalRequest):
    """REAL_ENABLED 승인 요청 생성 (PENDING 상태, keys=[])"""
    logger.info(f"REAL 승인 요청: by={data.requested_by}")
    
    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
    
    approval = {
        "schema": "REAL_ENABLE_APPROVAL_V1",
        "approval_id": str(uuid.uuid4()),
        "requested_at": datetime.now().isoformat(),
        "requested_by": data.requested_by,
        "mode_target": "REAL_ENABLED",
        "reason": data.reason,
        "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
        "keys_required": 2,
        "keys": [],
        "status": "PENDING"
    }
    
    with open(APPROVALS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(approval, ensure_ascii=False) + "\n")
    
    return {"result": "OK", "approval_id": approval["approval_id"], "status": "PENDING"}


class KeyApproval(BaseModel):
    approval_id: str
    key_id: str
    approver_id: str

@app.post("/api/approvals/real_enable/approve", summary="REAL 모드 Key 제공")
def approve_real_key(data: KeyApproval):
    """승인에 Key 추가 (2개 충족 시 APPROVED)"""
    logger.info(f"Key 제공: approval={data.approval_id}, key={data.key_id}")
    
    if not APPROVALS_FILE.exists():
        return JSONResponse(status_code=404, content={"result": "FAIL", "message": "No approvals found"})
    
    approvals = read_jsonl(APPROVALS_FILE)
    
    # 같은 approval_id의 모든 버전 중 최신 것 찾기 (JSONL은 append-only)
    matching = [a for a in approvals if a.get("approval_id") == data.approval_id]
    if not matching:
        return JSONResponse(status_code=404, content={"result": "FAIL", "message": "Approval not found"})
    
    # 최신 버전 (마지막에 추가된 것)
    target = matching[-1]
    
    # 만료 체크
    if datetime.fromisoformat(target["expires_at"]) < datetime.now():
        return JSONResponse(status_code=409, content={"result": "EXPIRED", "message": "Approval has expired"})
    
    # 이미 승인/취소됨
    if target["status"] in ["APPROVED", "REVOKED"]:
        return JSONResponse(status_code=409, content={"result": "CONFLICT", "message": f"Status is already {target['status']}"})
    
    # 중복 Key 체크
    existing_keys = [k["key_id"] for k in target.get("keys", [])]
    if data.key_id in existing_keys:
        return JSONResponse(status_code=409, content={"result": "DUPLICATE", "message": "Key already provided"})
    
    # 같은 approver가 이미 키 제공했는지 체크
    existing_approvers = [k["provided_by"] for k in target.get("keys", [])]
    if data.approver_id in existing_approvers:
        return JSONResponse(status_code=409, content={"result": "DUPLICATE", "message": "Approver already provided a key"})
    
    # Key 추가
    new_key = {
        "key_id": data.key_id,
        "provided_by": data.approver_id,
        "provided_at": datetime.now().isoformat()
    }
    target["keys"].append(new_key)
    
    # 2개 충족 시 APPROVED
    if len(target["keys"]) >= target["keys_required"]:
        target["status"] = "APPROVED"
        logger.info(f"Approval APPROVED: {data.approval_id}")
    
    # 새 로그 Append (Append-only)
    with open(APPROVALS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(target, ensure_ascii=False) + "\n")
    
    return {"result": "OK", "approval_id": data.approval_id, "status": target["status"], "keys_count": len(target["keys"])}


@app.get("/api/approvals/real_enable/latest", summary="최신 REAL 승인 상태 조회")
def get_latest_real_approval():
    """최신 REAL 승인 상태 반환"""
    approval = get_latest_approval()
    
    if not approval:
        return {"status": "not_ready", "schema": "REAL_ENABLE_APPROVAL_V1", "data": None}
    
    # 만료 체크
    if approval["status"] == "PENDING" and datetime.fromisoformat(approval["expires_at"]) < datetime.now():
        approval["status"] = "EXPIRED"
    
    return {
        "status": "ready",
        "schema": "REAL_ENABLE_APPROVAL_V1",
        "asof": datetime.now().isoformat(),
        "data": approval,
        "error": None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)




