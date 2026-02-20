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
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
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
    today_str = datetime.now(KST).strftime("%Y%m%d")
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
    return datetime.now(KST).strftime("%Y%m%d")

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
    path = REPORTS_DIR / "phase_c" / "report_human_v1.json"
    if not path.exists():
        return {"result": "FAIL", "message": "Human report not found"}
    return safe_read_json(path)

@app.get("/api/report/ai", summary="AI Report (Contract 5)")
def get_report_ai():
    path = REPORTS_DIR / "phase_c" / "report_ai_v1.json"
    if not path.exists():
        return {"result": "FAIL", "message": "AI report not found"}
    return safe_read_json(path)

@app.get("/api/recon/summary", summary="Reconciliation Summary (Source of Truth)")
def get_recon_summary():
    summary_path = REPORTS_DIR / "phase_c" / "recon_summary.json"
    daily_path = REPORTS_DIR / "phase_c" / "recon_daily.jsonl"
    
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
            "asof": data.get("asof", datetime.now(KST).strftime("%Y-%m-%d")), 
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
    path = REPORTS_DIR / "phase_c" / "recon_daily.jsonl"
    if not path.exists():
        return {"status": "not_ready", "message": "Recon daily not found", "rows": [], "row_count": 0}
    try:
        lines = path.read_text(encoding="utf-8").strip().split('\n')
        rows = [json.loads(line) for line in lines if line.strip()]
        return {
            "status": "ready",
            "schema": "RECON_DAILY_V1",
            "asof": datetime.now(KST).strftime("%Y-%m-%d"),
            "row_count": len(rows),
            "rows": rows,
            "error": None
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "rows": [], "row_count": 0, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
