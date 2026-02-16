# -*- coding: utf-8 -*-
"""
backend/main.py
KRX Alertor Modular - 읽기 전용 옵저버 백엔드
"""
import logging
import sys
import subprocess
import json
import yaml
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union

from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# --- .env 로딩 (시작 시 1회, override=False: SYSTEM_ENV > DOTENV) ---
try:
    from dotenv import load_dotenv
    import os
    # Try multiple paths to find .env
    _possible_paths = [
        Path(__file__).resolve().parent.parent / ".env",  # backend/../.env
        Path.cwd() / ".env",  # Current working directory
        Path(".env"),  # Relative
    ]
    for _env_file in _possible_paths:
        if _env_file.exists():
            load_dotenv(_env_file, override=False)
            break
except ImportError:
    pass  # python-dotenv 미설치 시 ENV_ONLY로 동작

# --- 1. 환경 설정 및 상수 ---
BASE_DIR = Path(".")
LOG_DIR = BASE_DIR / "logs"
STATE_DIR = BASE_DIR / "state"
REPORTS_DIR = BASE_DIR / "reports"
PAPER_DIR = REPORTS_DIR / "paper"
DASHBOARD_DIR = BASE_DIR / "dashboard"

# P146.3: Draft Generation Constants
PREP_LATEST_FILE = REPORTS_DIR / "live" / "execution_prep" / "latest" / "execution_prep_latest.json"
TICKET_LATEST_FILE = REPORTS_DIR / "live" / "manual_execution_ticket" / "latest" / "manual_execution_ticket_latest.json"
ORDER_PLAN_EXPORT_LATEST_FILE = REPORTS_DIR / "live" / "order_plan_export" / "latest" / "order_plan_export_latest.json"
OPS_SUMMARY_PATH = REPORTS_DIR / "ops" / "summary" / "latest" / "ops_summary_latest.json"
DRAFT_LATEST_FILE = REPORTS_DIR / "live" / "manual_execution_record" / "draft" / "latest" / "manual_execution_record_draft_latest.json"

# Ensure dirs exist
DRAFT_LATEST_FILE.parent.mkdir(parents=True, exist_ok=True)

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
from backend import operator_dashboard

app = FastAPI(
    title="KRX Alertor Modular Backend",
    description="Read-only Observer Backend + Operator Dashboard",
    version="1.0.0"
)

# CORS (P99)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
# Include Routers
app.include_router(operator_dashboard.router)

from backend import dry_run
app.include_router(dry_run.router)

# P146: SSOT & Sync Routers
from app.routers import ssot
app.include_router(ssot.router)

# Import sync router only if dependencies (requests) are available or try/except
try:
    from app.routers import sync
    app.include_router(sync.router)
except ImportError:
    pass # Requests might not be installed on strict server env, but needed for PC


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
        logger.error(f"YAML 파싱 실패: {path} - {str(e)}")
        raise ValueError("잘못된 YAML 형식입니다.")

def _load_json(path: Path) -> Optional[Dict]:
    """Helper for Draft Generation (Hotfix 172)"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

# --- 5. API Endpoints ---

from fastapi.responses import RedirectResponse

@app.get("/")
def read_root():
    """Root Redirect to Operator Dashboard (P146)"""
    return RedirectResponse(url="/operator", status_code=307)

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
    """현재 포트폴리오 상태 반환 (Try portfolio_latest.json first, then paper_portfolio.json)"""
    logger.info("포트폴리오 조회 요청 (GET /api/portfolio)")
    
    # Priority 1: D-P.58 Standard
    path_latest = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"
    if path_latest.exists():
        return safe_read_json(path_latest)
        
    # Priority 2: Legacy
    path_legacy = STATE_DIR / "paper_portfolio.json"
    if path_legacy.exists():
        return safe_read_json(path_legacy)
        
    return {"error": "포트폴리오 파일이 없습니다.", "cash": 0, "holdings": {}, "total_equity": 0}

@app.post("/api/portfolio/upsert")
async def upsert_portfolio_api(confirm: bool = Query(False), payload: Dict = Body(...)):
    """포트폴리오 저장 (D-P.58)"""
    if not confirm:
        return JSONResponse(status_code=400, content={"result": "BLOCKED", "message": "Confirm required"})
        
    try:
        # Save to Standard Location
        path_latest = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"
        path_latest.parent.mkdir(parents=True, exist_ok=True)
        
        # Add timestamp
        if "updated_at" not in payload:
            payload["updated_at"] = datetime.now().isoformat()
            
        with open(path_latest, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, indent=2, ensure_ascii=False))
            
        logger.info(f"포트폴리오 저장 완료: {path_latest}")
        return {"result": "OK", "path": str(path_latest), "data": payload}
        
    except Exception as e:
        logger.error(f"포트폴리오 저장 실패: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"result": "FAILED", "reason": str(e)})

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

@app.get("/api/reco/latest", summary="최신 추천 리포트 조회 (P101)")
def get_reco_latest():
    """
    최신 Reco Report V1을 반환합니다.
    파일이 없으면 decision=NO_RECO_YET을 포함한 Graceful Response를 반환합니다.
    """
    path = REPORTS_DIR / "live" / "reco" / "latest" / "reco_latest.json"
    if not path.exists():
        return {
            "schema": "RECO_REPORT_V1",
            "decision": "NO_RECO_YET",
            "reason": "FILE_NOT_FOUND",
            "message": "아직 추천 리포트가 생성되지 않았습니다.",
            "created_at": None,
            "source_bundle": None
        }
    return safe_read_json(path)

@app.post("/api/reco/regenerate", summary="추천 리포트 재생성 (P101)")
def regenerate_reco(confirm: bool = Query(False)):
    """
    app/generate_reco_report.py를 실행하여 리포트를 재생성합니다.
    - confirm=true 필수
    - Fail-Closed 원칙에 따라 스크립트 실행 결과를 반환
    """
    if not confirm:
        return JSONResponse(
            status_code=400, 
            content={"result": "BLOCKED", "reason": "CONFIRM_REQUIRED", "message": "confirm=true parameter is required"}
        )
    
    try:
        logger.info("Reco Report 재생성 요청 (subprocess)")
        # Run generator script relative to BASE_DIR using -m to support imports
        cmd = [sys.executable, "-m", "app.generate_reco_report"]
        
        # Capture output
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE_DIR)
        
        if result.returncode != 0:
            logger.error(f"Reco Generation Failed (Exit {result.returncode}): {result.stderr}")
            return JSONResponse(
                status_code=500, 
                content={
                    "result": "FAIL", 
                    "error": result.stderr, 
                    "stdout": result.stdout,
                    "exit_code": result.returncode
                }
            )
            
        # Parse script output (Expected JSON)
        try:
             output_json = json.loads(result.stdout)
             logger.info("Reco Report 재생성 성공")
             return output_json
        except json.JSONDecodeError:
             logger.warning("Reco script stdout is not valid JSON")
             return {
                 "result": "OK", 
                 "message": "Script executed but output check failed", 
                 "stdout": result.stdout
             }
             
    except Exception as e:
        logger.error(f"Reco Regeneration Error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"result": "ERROR", "message": str(e)})

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


@app.get("/api/order_plan/latest", summary="최신 주문안 조회 (P102)")
def get_order_plan_latest():
    """
    최신 Order Plan V1 (Intent-Only) 반환
    없을 경우 graceful response
    """
    path = REPORTS_DIR / "live" / "order_plan" / "latest" / "order_plan_latest.json"
    if not path.exists():
        return {
            "schema": "ORDER_PLAN_V1",
            "decision": "BLOCKED",
            "reason": "FILE_NOT_FOUND",
            "message": "아직 주문안이 생성되지 않았습니다."
        }
    return safe_read_json(path)

@app.post("/api/order_plan/regenerate", summary="주문안 재생성 (P102)")
def regenerate_order_plan(confirm: bool = Query(False)):
    """
    app/generate_order_plan.py 실행
    - Fail-Closed: Reco/Portfolio 문제 시 BLOCKED 반환
    """
    if not confirm:
        return JSONResponse(status_code=400, content={"result": "BLOCKED", "reason": "CONFIRM_REQUIRED"})
        
    try:
        logger.info("Order Plan 재생성 요청")
        cmd = [sys.executable, "-m", "app.generate_order_plan"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE_DIR)
        
        if result.returncode != 0:
            logger.error(f"Order Plan Gen Failed: {result.stderr}")
            return JSONResponse(status_code=500, content={
                "result": "FAIL", 
                "error": result.stderr,
                "stdout": result.stdout
            })
            
        try:
            return json.loads(result.stdout)
        except:
             return {"result": "OK", "message": "Parsed error", "stdout": result.stdout}
             
    except Exception as e:
        logger.error(f"Order Plan API Error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"result": "ERROR", "message": str(e)})


@app.get("/api/contract5/latest", summary="최신 Daily Report 조회 (P103)")
def get_contract5_latest():
    """
    최신 Contract 5 Report (AI JSON) 반환
    """
    path = REPORTS_DIR / "ops" / "contract5" / "latest" / "ai_report_latest.json"
    if not path.exists():
        return {
            "schema": "CONTRACT5_REPORT_V1",
            "decision": "BLOCKED",
            "reason": "FILE_NOT_FOUND"
        }
    return safe_read_json(path)


@app.post("/api/contract5/regenerate", summary="Daily Report 재생성 (P103)")
def regenerate_contract5(confirm: bool = Query(False)):
    """
    app/generate_contract5_report.py 실행 (Ops/Reco/OrderPlan 취합)
    """
    if not confirm:
        return JSONResponse(status_code=400, content={"result": "BLOCKED", "reason": "CONFIRM_REQUIRED"})
        
    try:
        logger.info("Contract 5 Report 재생성 요청")
        cmd = [sys.executable, "-m", "app.generate_contract5_report"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE_DIR)
        
        if result.returncode != 0:
            logger.error(f"Contract 5 Gen Failed: {result.stderr}")
            return JSONResponse(status_code=500, content={
                "result": "FAIL", 
                "error": result.stderr,
                "stdout": result.stdout
            })
            
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
             return {"result": "OK", "message": "Parsed error", "stdout": result.stdout}
             
    except Exception as e:
        logger.error(f"Contract 5 API Error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"result": "ERROR", "message": str(e)})


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
    
    # C-P.7: REAL_ENABLED 허용 (Worker에서 Shadow로 강제 처리됨)
    if data.mode == "REAL_ENABLED":
        logger.warning("REAL_ENABLED mode requested - Allowed for SHADOW mode (C-P.7)")
        # Note: Worker will force SHADOW processing, no real subprocess execution
    
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
    """최신 Approval 조회 (Append-only에서 상태 합성)"""
    if not APPROVALS_FILE.exists():
        return None
    
    approvals = read_jsonl(APPROVALS_FILE)
    if not approvals:
        return None
    
    # approval_id별로 이벤트 병합 (append-only 로그이므로 최신 우선)
    merged = {}
    for event in approvals:
        aid = event.get("approval_id")
        if not aid:
            continue
        
        if aid not in merged:
            merged[aid] = event.copy()
        else:
            # 같은 approval_id의 새 이벤트: keys, status 업데이트
            if "keys" in event:
                merged[aid]["keys"] = event["keys"]
            if "status" in event:
                merged[aid]["status"] = event["status"]
    
    if not merged:
        return None
    
    # 정렬: APPROVED 우선, 그 다음 requested_at 최신
    sorted_approvals = sorted(
        merged.values(),
        key=lambda x: (
            x.get("status") == "APPROVED",  # APPROVED가 True(1)로 뒤에 정렬
            x.get("requested_at", "")
        ),
        reverse=True
    )
    
    return sorted_approvals[0] if sorted_approvals else None


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


# --- Phase C-P.8: Execution Allowlist API ---

ALLOWLIST_FILE = BASE_DIR / "docs" / "contracts" / "execution_allowlist_v1.json"

@app.get("/api/execution_allowlist", summary="Execution Allowlist 조회 (Read-Only)")
def get_execution_allowlist():
    """불변 Allowlist 반환 (docs/contracts/ 경로에서 읽기 전용)"""
    if not ALLOWLIST_FILE.exists():
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": "Allowlist not found"}
        )
    
    try:
        data = json.loads(ALLOWLIST_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": data.get("schema", "REAL_EXECUTION_ALLOWLIST_V1"),
            "asof": datetime.now().isoformat(),
            "data": data,
            "immutable_path": "docs/contracts/execution_allowlist_v1.json",
            "error": None
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


# --- Phase C-P.9: Real Enable Window APIs ---

WINDOWS_DIR = STATE_DIR / "real_enable_windows"
WINDOWS_FILE = WINDOWS_DIR / "real_enable_windows.jsonl"


def get_active_window() -> Dict:
    """현재 ACTIVE 상태인 Window 조회 (Synthesized)"""
    if not WINDOWS_FILE.exists():
        return None
    
    events = read_jsonl(WINDOWS_FILE)
    if not events:
        return None
    
    # window_id별로 최신 상태 계산
    windows = {}
    for event in events:
        wid = event.get("window_id")
        if wid not in windows:
            windows[wid] = event.copy()
        else:
            # 이벤트 타입에 따라 상태 업데이트
            if event.get("event") == "REVOKE":
                windows[wid]["status"] = "REVOKED"
            elif event.get("event") == "CONSUME":
                windows[wid]["real_executions_used"] = windows[wid].get("real_executions_used", 0) + 1
    
    # ACTIVE window 찾기 (최신 우선)
    now = datetime.now()
    active_windows = []
    
    for wid, window in windows.items():
        # 만료 체크
        expires_at = datetime.fromisoformat(window.get("expires_at", "2000-01-01"))
        if expires_at < now:
            window["status"] = "EXPIRED"
        
        # 소진 체크
        used = window.get("real_executions_used", 0)
        max_exec = window.get("max_real_executions", 1)
        if used >= max_exec and window.get("status") not in ["REVOKED", "EXPIRED"]:
            window["status"] = "CONSUMED"
        
        if window.get("status") == "ACTIVE":
            active_windows.append(window)
    
    if not active_windows:
        return None
    
    # 최신 생성된 ACTIVE window 반환
    return max(active_windows, key=lambda w: w.get("created_at", ""))


class WindowRequest(BaseModel):
    reason: str
    ttl_seconds: int = 600


@app.post("/api/real_enable_window/request", summary="REAL Enable Window 생성")
def create_real_window(data: WindowRequest):
    """REAL 실행 창 생성 (C-P.9: REQUEST_REPORTS만, 1회만)"""
    logger.info(f"Window 요청: reason={data.reason}, ttl={data.ttl_seconds}")
    
    WINDOWS_DIR.mkdir(parents=True, exist_ok=True)
    
    now = datetime.now()
    window = {
        "schema": "REAL_ENABLE_WINDOW_V1",
        "event": "CREATE",
        "window_id": str(uuid.uuid4()),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=data.ttl_seconds)).isoformat(),
        "created_by": "api",
        "reason": data.reason,
        "allowed_request_types": ["REQUEST_RECONCILE", "REQUEST_REPORTS"],  # C-P.12
        "max_real_executions": 1,  # C-P.9 고정
        "real_executions_used": 0,
        "status": "ACTIVE"
    }
    
    with open(WINDOWS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(window, ensure_ascii=False) + "\n")
    
    logger.info(f"Window 생성: {window['window_id']}")
    return {
        "result": "OK",
        "schema": "REAL_ENABLE_WINDOW_V1",
        "data": window
    }


@app.get("/api/real_enable_window/latest", summary="현재 REAL Enable Window 조회")
def get_real_window_latest():
    """현재 ACTIVE Window 반환 (없으면 빈 rows)"""
    window = get_active_window()
    
    return {
        "status": "ready",
        "schema": "REAL_ENABLE_WINDOW_V1",
        "asof": datetime.now().isoformat(),
        "row_count": 1 if window else 0,
        "rows": [window] if window else [],
        "error": None
    }


class WindowRevoke(BaseModel):
    window_id: str
    reason: str = ""


@app.post("/api/real_enable_window/revoke", summary="REAL Enable Window 폐기")
def revoke_real_window(data: WindowRevoke):
    """Window 즉시 폐기"""
    logger.info(f"Window 폐기: {data.window_id}")
    
    if not WINDOWS_FILE.exists():
        return JSONResponse(status_code=404, content={"result": "FAIL", "message": "No windows"})
    
    revoke_event = {
        "schema": "REAL_ENABLE_WINDOW_V1",
        "event": "REVOKE",
        "window_id": data.window_id,
        "revoked_at": datetime.now().isoformat(),
        "revoked_by": "api",
        "reason": data.reason
    }
    
    with open(WINDOWS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(revoke_event, ensure_ascii=False) + "\n")
    
    return {"result": "OK", "window_id": data.window_id, "status": "REVOKED"}


# --- Phase C-P.10: Reconcile Deps & Preflight APIs ---

PREFLIGHT_DIR = BASE_DIR / "reports" / "tickets" / "preflight"


def check_reconcile_deps() -> dict:
    """Check reconcile dependencies"""
    import sys
    result = {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "python_ok": sys.version_info >= (3, 10),
        "pandas_installed": False,
        "pyarrow_installed": False,
        "required_missing": []
    }
    
    try:
        import pandas
        result["pandas_installed"] = True
        result["pandas_version"] = pandas.__version__
    except ImportError:
        result["required_missing"].append("pandas")
    
    try:
        import pyarrow
        result["pyarrow_installed"] = True
        result["pyarrow_version"] = pyarrow.__version__
    except ImportError:
        result["required_missing"].append("pyarrow")
    
    result["all_deps_ok"] = len(result["required_missing"]) == 0 and result["python_ok"]
    return result


@app.get("/api/deps/reconcile", summary="Reconcile 의존성 상태 조회")
def get_reconcile_deps():
    """현재 reconcile REAL 실행 가능 여부 확인"""
    deps = check_reconcile_deps()
    return {
        "status": "ready" if deps["all_deps_ok"] else "missing_deps",
        "schema": "RECONCILE_DEPENDENCY_V2",
        "asof": datetime.now().isoformat(),
        "row_count": 1,
        "rows": [deps],
        "error": None if deps["all_deps_ok"] else f"Missing: {deps['required_missing']}"
    }


DEPS_SNAPSHOT_DIR = BASE_DIR / "state" / "deps"
DEPS_SNAPSHOT_FILE = DEPS_SNAPSHOT_DIR / "installed_deps_snapshot.json"


@app.post("/api/deps/snapshot", summary="의존성 스냅샷 저장")
def save_deps_snapshot():
    """설치된 의존성을 스냅샷으로 저장"""
    DEPS_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    
    deps = check_reconcile_deps()
    
    snapshot = {
        "schema": "DEPS_SNAPSHOT_V1",
        "asof": datetime.now().isoformat(),
        "python_version": deps.get("python_version"),
        "packages": {
            "pandas": deps.get("pandas_version"),
            "pyarrow": deps.get("pyarrow_version")
        },
        "source": "importlib metadata",
        "all_deps_ok": deps.get("all_deps_ok")
    }
    
    DEPS_SNAPSHOT_FILE.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Deps snapshot saved: {DEPS_SNAPSHOT_FILE}")
    
    return {
        "result": "OK",
        "path": str(DEPS_SNAPSHOT_FILE.relative_to(BASE_DIR)),
        "snapshot": snapshot
    }


@app.get("/api/deps/snapshot", summary="의존성 스냅샷 조회")
def get_deps_snapshot():
    """저장된 의존성 스냅샷 조회"""
    if not DEPS_SNAPSHOT_FILE.exists():
        return {"status": "not_found", "error": "Snapshot not found"}
    
    snapshot = json.loads(DEPS_SNAPSHOT_FILE.read_text(encoding="utf-8"))
    return {"status": "ready", "snapshot": snapshot}


class PreflightRequest(BaseModel):
    request_id: str
    request_type: str
    payload: dict = {}


@app.post("/api/deps/reconcile/check", summary="Reconcile Deep Preflight 수행")
def run_reconcile_preflight(data: PreflightRequest):
    """Deep Preflight 체크 수행 및 Artifact 저장"""
    logger.info(f"Preflight 체크: {data.request_id} ({data.request_type})")
    
    PREFLIGHT_DIR.mkdir(parents=True, exist_ok=True)
    
    checks = {}
    fail_reasons = []
    
    # 1. Import Check
    deps = check_reconcile_deps()
    if deps["all_deps_ok"]:
        checks["import_check"] = {"status": "PASS", "detail": f"pandas={deps.get('pandas_version')}, pyarrow={deps.get('pyarrow_version')}"}
    else:
        checks["import_check"] = {"status": "FAIL", "detail": f"Missing: {deps['required_missing']}"}
        fail_reasons.append(f"import_check: {deps['required_missing']}")
    
    # 2. Input Ready Check (minimal - check if config exists)
    config_path = BASE_DIR / "config" / "production_config_v2.py"
    if config_path.exists():
        checks["input_ready_check"] = {"status": "PASS", "detail": "config exists"}
    else:
        checks["input_ready_check"] = {"status": "FAIL", "detail": "config not found"}
        fail_reasons.append("input_ready_check: config not found")
    
    # 3. Output Writable Check
    output_dir = BASE_DIR / "reports" / "phase_c" / "latest"
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        test_file = output_dir / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
        checks["output_writable_check"] = {"status": "PASS", "detail": str(output_dir)}
    except Exception as e:
        checks["output_writable_check"] = {"status": "FAIL", "detail": str(e)}
        fail_reasons.append(f"output_writable_check: {e}")
    
    # 4. Allowlist Check
    allowlist_file = BASE_DIR / "docs" / "contracts" / "execution_allowlist_v1.json"
    if allowlist_file.exists():
        allowlist = json.loads(allowlist_file.read_text(encoding="utf-8"))
        if data.request_type in allowlist.get("allowed_request_types", []):
            checks["allowlist_check"] = {"status": "PASS", "detail": f"{data.request_type} allowed"}
        else:
            checks["allowlist_check"] = {"status": "FAIL", "detail": f"{data.request_type} not in allowlist"}
            fail_reasons.append(f"allowlist_check: {data.request_type} not allowed")
    else:
        checks["allowlist_check"] = {"status": "FAIL", "detail": "allowlist not found"}
        fail_reasons.append("allowlist_check: file not found")
    
    # 5. Gate Check
    gate_ok = False
    try:
        gate_data = json.loads(EXECUTION_GATE_FILE.read_text(encoding="utf-8")) if EXECUTION_GATE_FILE.exists() else {}
        estop_data = json.loads(EMERGENCY_STOP_FILE.read_text(encoding="utf-8")) if EMERGENCY_STOP_FILE.exists() else {}
        window = get_active_window()
        
        gate_mode = gate_data.get("mode", "MOCK_ONLY")
        estop_enabled = estop_data.get("enabled", False)
        window_active = window is not None and data.request_type in window.get("allowed_request_types", [])
        
        if gate_mode == "REAL_ENABLED" and not estop_enabled and window_active:
            checks["gate_check"] = {"status": "PASS", "detail": f"gate={gate_mode}, estop=OFF, window=ACTIVE"}
            gate_ok = True
        else:
            checks["gate_check"] = {"status": "FAIL", "detail": f"gate={gate_mode}, estop={estop_enabled}, window={window_active}"}
            fail_reasons.append(f"gate_check: conditions not met")
    except Exception as e:
        checks["gate_check"] = {"status": "FAIL", "detail": str(e)}
        fail_reasons.append(f"gate_check: {e}")
    
    # Decision
    all_pass = all(c["status"] == "PASS" for c in checks.values())
    decision = "PREFLIGHT_PASS" if all_pass else "PREFLIGHT_FAIL"
    
    # Save Artifact
    artifact = {
        "schema": "RECONCILE_PREFLIGHT_V1",
        "asof": datetime.now().isoformat(),
        "request_id": data.request_id,
        "request_type": data.request_type,
        "checks": checks,
        "effective_plan": ["python", "-m", "app.reconcile"],
        "decision": decision,
        "fail_reasons": fail_reasons
    }
    
    artifact_path = PREFLIGHT_DIR / f"{data.request_id}.json"
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    
    logger.info(f"Preflight 결과: {decision}")
    return {
        "result": "OK",
        "request_id": data.request_id,
        "decision": decision,
        "artifact_path": str(artifact_path.relative_to(BASE_DIR))
    }


# === Daily Ops Report API (C-P.13) ===

OPS_REPORT_DIR = BASE_DIR / "reports" / "ops" / "daily"
OPS_REPORT_LATEST = OPS_REPORT_DIR / "ops_report_latest.json"
OPS_SNAPSHOTS_DIR = OPS_REPORT_DIR / "snapshots"


def generate_daily_ops_report() -> dict:
    """Generate daily ops report from ticket data"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Read ticket data
    requests_file = BASE_DIR / "state" / "tickets" / "ticket_requests.jsonl"
    results_file = BASE_DIR / "state" / "tickets" / "ticket_results.jsonl"
    receipts_file = BASE_DIR / "state" / "tickets" / "ticket_receipts.jsonl"
    
    requests = read_jsonl(requests_file) if requests_file.exists() else []
    results = read_jsonl(results_file) if results_file.exists() else []
    receipts = read_jsonl(receipts_file) if receipts_file.exists() else []
    
    # Filter today's data
    today_results = [r for r in results if r.get("processed_at", "").startswith(today)]
    today_receipts = [r for r in receipts if r.get("asof", r.get("issued_at", "")).startswith(today)]
    
    # Calculate summary
    done = len([r for r in today_results if r.get("status") == "DONE"])
    failed = len([r for r in today_results if r.get("status") == "FAILED"])
    blocked_receipts = [r for r in today_receipts if r.get("decision") == "BLOCKED"]
    
    # Aggregate blocked reasons
    blocked_reasons = {}
    for r in blocked_receipts:
        reasons = r.get("block_reasons", [])
        if not reasons:
            reason = r.get("acceptance", {}).get("reason", "UNKNOWN")
            reasons = [reason]
        for reason in reasons:
            # Truncate long reason
            short_reason = reason[:50] if len(reason) > 50 else reason
            blocked_reasons[short_reason] = blocked_reasons.get(short_reason, 0) + 1
    
    blocked_reasons_top = sorted(
        [{"reason": k, "count": v} for k, v in blocked_reasons.items()],
        key=lambda x: x["count"],
        reverse=True
    )[:3]
    
    # Find last REAL execution
    real_receipts = [r for r in today_receipts if r.get("mode") == "REAL" and r.get("decision") == "EXECUTED"]
    last_real = None
    if real_receipts:
        last = real_receipts[-1]
        last_real = {
            "request_id": last.get("request_id"),
            "request_type": last.get("request_type"),
            "exit_code": last.get("exit_code"),
            "acceptance_pass": last.get("acceptance", {}).get("pass", False)
        }
    
    # Artifacts written today
    artifacts_written = []
    for r in real_receipts:
        artifacts = r.get("outputs_proof", {}).get("targets", [])
        for t in artifacts:
            if t.get("changed") and t.get("path") not in artifacts_written:
                artifacts_written.append(t.get("path"))
    
    report = {
        "schema": "DAILY_OPS_REPORT_V1",
        "asof": datetime.now().isoformat(),
        "period": today,
        "summary": {
            "tickets_total": len(today_results),
            "done": done,
            "failed": failed,
            "blocked": len(blocked_receipts)
        },
        "blocked_reasons_top": blocked_reasons_top,
        "last_real_execution": last_real,
        "artifacts_written": artifacts_written,
        # C-P.14: Extended fields
        "last_done": None,
        "last_failed": None,
        "last_blocked": None,
        "safety_counters": {
            "window_consumed_count": 0,
            "emergency_stop_hits": 0,
            "allowlist_violation_hits": 0,
            "preflight_fail_hits": 0
        }
    }
    
    # C-P.14: Calculate last_done/failed/blocked
    done_receipts = [r for r in today_receipts if r.get("decision") == "EXECUTED"]
    failed_receipts = [r for r in today_receipts if r.get("decision") == "FAILED"]
    
    if done_receipts:
        last = done_receipts[-1]
        report["last_done"] = {
            "request_id": last.get("request_id"),
            "request_type": last.get("request_type"),
            "at": last.get("asof", last.get("issued_at"))
        }
    
    if failed_receipts:
        last = failed_receipts[-1]
        report["last_failed"] = {
            "request_id": last.get("request_id"),
            "request_type": last.get("request_type"),
            "reason": last.get("acceptance", {}).get("reason", "UNKNOWN"),
            "at": last.get("asof", last.get("issued_at"))
        }
    
    if blocked_receipts:
        last = blocked_receipts[-1]
        reasons = last.get("block_reasons", [])
        reason = reasons[0] if reasons else last.get("acceptance", {}).get("reason", "UNKNOWN")
        report["last_blocked"] = {
            "request_id": last.get("request_id"),
            "request_type": last.get("request_type"),
            "reason": reason[:50] if len(reason) > 50 else reason,
            "at": last.get("asof", last.get("issued_at"))
        }
    
    # C-P.14: Calculate safety_counters from blocked reasons
    for r in blocked_receipts:
        reasons = r.get("block_reasons", [])
        reason_str = " ".join(reasons).lower() if reasons else r.get("acceptance", {}).get("reason", "").lower()
        
        if "window" in reason_str and ("consumed" in reason_str or "inactive" in reason_str or "active" in reason_str):
            report["safety_counters"]["window_consumed_count"] += 1
        if "emergency" in reason_str:
            report["safety_counters"]["emergency_stop_hits"] += 1
        if "allowlist" in reason_str:
            report["safety_counters"]["allowlist_violation_hits"] += 1
        if "preflight" in reason_str:
            report["safety_counters"]["preflight_fail_hits"] += 1
    
    return report


def save_daily_ops_report(report: dict, skip_if_snapshot_exists: bool = False) -> dict:
    """Save daily ops report to files (C-P.14: idempotent snapshot)"""
    OPS_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OPS_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save latest (always overwrite)
    OPS_REPORT_LATEST.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # Save snapshot (C-P.14: idempotent - skip if exists)
    today = datetime.now().strftime("%Y%m%d")
    snapshot_path = OPS_SNAPSHOTS_DIR / f"ops_report_{today}.json"
    
    snapshot_skipped = False
    if snapshot_path.exists() and skip_if_snapshot_exists:
        logger.info(f"Snapshot already exists, skipped: {snapshot_path}")
        snapshot_skipped = True
    else:
        snapshot_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    
    logger.info(f"Ops report saved: {OPS_REPORT_LATEST}")
    return {"snapshot_skipped": snapshot_skipped, "snapshot_path": str(snapshot_path)}


@app.get("/api/ops/daily", summary="일일 운영 리포트 조회")
def get_daily_ops_report():
    """Daily Ops Report API (C-P.13)"""
    if not OPS_REPORT_LATEST.exists():
        # Generate if not exists
        report = generate_daily_ops_report()
        save_daily_ops_report(report)
    else:
        report = json.loads(OPS_REPORT_LATEST.read_text(encoding="utf-8"))
    
    return {
        "status": "ready",
        "schema": "DAILY_OPS_REPORT_V1",
        "asof": report.get("asof"),
        "row_count": 1,
        "rows": [report],
        "error": None
    }


@app.post("/api/ops/daily/regenerate", summary="일일 운영 리포트 재생성")
def regenerate_daily_ops_report():
    """Regenerate daily ops report (C-P.14: idempotent snapshot)"""
    report = generate_daily_ops_report()
    save_result = save_daily_ops_report(report, skip_if_snapshot_exists=True)
    return {
        "result": "OK",
        "report": report,
        "snapshot_skipped": save_result.get("snapshot_skipped", False)
    }


# === Ops Runner API (C-P.15) ===

OPS_RUNNER_LOCK_FILE = STATE_DIR / "ops_runner.lock"
OPS_SNAPSHOTS_DIR = OPS_REPORT_DIR / "snapshots"
LOCK_TIMEOUT_SECONDS = 60


def check_emergency_stop_status() -> bool:
    """비상 정지 상태 확인"""
    stop_file = STATE_DIR / "emergency_stop.json"
    if not stop_file.exists():
        return False
    try:
        data = json.loads(stop_file.read_text(encoding="utf-8"))
        # Note: emergency_stop.json uses 'enabled' key (C-P.15 bugfix)
        return data.get("enabled", data.get("active", False))
    except Exception:
        return False


def acquire_ops_lock() -> tuple:
    """Lock 확보 (중복 실행 방지)"""
    if OPS_RUNNER_LOCK_FILE.exists():
        try:
            lock_data = json.loads(OPS_RUNNER_LOCK_FILE.read_text(encoding="utf-8"))
            lock_time = datetime.fromisoformat(lock_data.get("locked_at", ""))
            elapsed = (datetime.now() - lock_time).total_seconds()
            
            if elapsed < LOCK_TIMEOUT_SECONDS:
                return False, f"Locked by {lock_data.get('run_id')} ({elapsed:.0f}s ago)"
        except Exception:
            pass
    
    run_id = str(uuid.uuid4())
    lock_data = {
        "run_id": run_id,
        "locked_at": datetime.now().isoformat()
    }
    OPS_RUNNER_LOCK_FILE.write_text(json.dumps(lock_data, ensure_ascii=False), encoding="utf-8")
    return True, run_id


def release_ops_lock():
    """Lock 해제"""
    if OPS_RUNNER_LOCK_FILE.exists():
        OPS_RUNNER_LOCK_FILE.unlink()


def save_ops_run_snapshot(run_id: str, status: str, reason: str, ops_summary: dict, tickets_summary: dict, push_summary: dict, started_at: str) -> str:
    """스냅샷 저장"""
    OPS_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = OPS_SNAPSHOTS_DIR / f"ops_run_{timestamp}.json"
    
    snapshot = {
        "schema": "OPS_RUN_SNAPSHOT_V1",
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(),
        "status": status,
        "reason": reason,
        "ops_summary": ops_summary,
        "tickets_summary": tickets_summary,
        "push_summary": push_summary
    }
    
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Ops run snapshot saved: {snapshot_path}")
    return str(snapshot_path.relative_to(BASE_DIR))


@app.post("/api/ops/cycle/run", summary="운영 관측 루프 1회 실행 (V2)")
def run_ops_cycle_api():
    """Ops Cycle Runner API V2 (C-P.16) - 티켓 0~1건 처리 포함"""
    try:
        from app.run_ops_cycle import run_ops_cycle_v2
        result = run_ops_cycle_v2()
        
        if result.get("overall_status") == "STOPPED":
            return result
        elif result.get("result") == "SKIPPED":
            raise HTTPException(status_code=409, detail=result)
        elif result.get("result") == "FAILED":
            raise HTTPException(status_code=500, detail=result)
        
        return {
            "status": "ready",
            "schema": "OPS_CYCLE_RUN_V2",
            "asof": result.get("snapshot_path", ""),
            "row_count": 1,
            "data": result,
            "error": None
        }
    except HTTPException:
        raise
    except ImportError as e:
        logger.error(f"Import error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": f"Import error: {e}"})
    except Exception as e:
        logger.error(f"Ops cycle V2 error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})


@app.get("/api/ops/health", summary="운영 상태 헬스체크")
def get_ops_health():
    """Ops Health Check API (C-P.17)"""
    try:
        # Emergency Stop
        emergency_stop = {"enabled": False, "reason": None}
        stop_file = STATE_DIR / "emergency_stop.json"
        if stop_file.exists():
            data = json.loads(stop_file.read_text(encoding="utf-8"))
            emergency_stop = {
                "enabled": data.get("enabled", False),
                "reason": data.get("reason")
            }
        
        # Execution Gate
        gate_mode = "MOCK_ONLY"
        gate_file = STATE_DIR / "execution_gate.json"
        if gate_file.exists():
            data = json.loads(gate_file.read_text(encoding="utf-8"))
            gate_mode = data.get("mode", "MOCK_ONLY")
        
        # Window Active
        window_active = False
        windows_file = STATE_DIR / "real_enable_windows" / "real_enable_windows.jsonl"
        if windows_file.exists():
            windows = read_jsonl(windows_file)
            window_active = any(w.get("status") == "ACTIVE" for w in windows)
        
        # Allowlist
        allowlist_version = "N/A"
        allowlist_file = BASE_DIR / "docs" / "contracts" / "execution_allowlist_v1.json"
        if allowlist_file.exists():
            data = json.loads(allowlist_file.read_text(encoding="utf-8"))
            allowlist_version = data.get("version", "v1")
        
        # Last Ops Report
        ops_report = None
        ops_file = BASE_DIR / "reports" / "ops" / "daily" / "ops_report_latest.json"
        if ops_file.exists():
            data = json.loads(ops_file.read_text(encoding="utf-8"))
            ops_report = {
                "asof": data.get("asof"),
                "summary": data.get("summary"),
                "last_done": data.get("last_done"),
                "last_failed": data.get("last_failed"),
                "last_blocked": data.get("last_blocked")
            }
        
        # Overall health
        health = "OK"
        if emergency_stop.get("enabled"):
            health = "STOPPED"
        elif gate_mode == "REAL_ENABLED" and not window_active:
            health = "WARNING"
        
        return {
            "status": "ready",
            "schema": "OPS_HEALTH_V1",
            "asof": datetime.now().isoformat(),
            "health": health,
            "data": {
                "emergency_stop": emergency_stop,
                "execution_gate_mode": gate_mode,
                "window_active": window_active,
                "allowlist_version": allowlist_version,
                "last_ops_report": ops_report
            },
            "error": None
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "error",
            "health": "ERROR",
            "error": str(e)
        }


# === Push Delivery API (C-P.18) ===

PUSH_DELIVERY_LATEST = BASE_DIR / "reports" / "ops" / "push" / "push_delivery_latest.json"


@app.get("/api/push/delivery/latest", summary="푸시 발송 결정 최신 조회")
def get_push_delivery_latest():
    """Push Delivery Latest Receipt (C-P.18)"""
    if not PUSH_DELIVERY_LATEST.exists():
        return {
            "status": "empty",
            "schema": "PUSH_DELIVERY_RECEIPT_V1",
            "data": None,
            "error": "No delivery receipt yet"
        }
    
    try:
        data = json.loads(PUSH_DELIVERY_LATEST.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "PUSH_DELIVERY_RECEIPT_V1",
            "asof": data.get("asof"),
            "data": data,
            "error": None
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/push/delivery/run", summary="푸시 발송 결정 사이클 실행")
def run_push_delivery_cycle_api():
    """Push Delivery Cycle Runner API (C-P.18)"""
    try:
        from app.run_push_delivery_cycle import run_push_delivery_cycle
        result = run_push_delivery_cycle()
        return {
            "status": "ready",
            "schema": "PUSH_DELIVERY_RECEIPT_V1",
            "data": result,
            "error": None
        }
    except ImportError as e:
        logger.error(f"Import error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": f"Import error: {e}"})
    except Exception as e:
        logger.error(f"Push delivery error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})


# === Secrets Status API (C-P.19) ===

# Required secrets from PUSH_CHANNELS_V1 contract
REQUIRED_SECRETS = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "SLACK_WEBHOOK_URL",
    "SMTP_HOST",
    "SMTP_USER",
    "SMTP_PASS",
    "EMAIL_TO"
]


@app.get("/api/secrets/status", summary="시크릿 존재 여부 조회")
def get_secrets_status():
    """Secrets Status API (C-P.19) - 값 노출 금지, present 여부만"""
    import os
    
    # Optional: try to load .env if python-dotenv is available
    try:
        from dotenv import load_dotenv
        env_file = BASE_DIR / ".env"
        if env_file.exists():
            load_dotenv(env_file)
    except ImportError:
        pass  # python-dotenv not installed, use system env only
    
    secrets_map = {}
    for secret_name in REQUIRED_SECRETS:
        # Only check presence, NEVER log or return values
        secrets_map[secret_name] = {"present": bool(os.environ.get(secret_name))}
    
    return {
        "status": "ready",
        "schema": "SECRETS_STATUS_V1",
        "asof": datetime.now().isoformat(),
        "row_count": len(REQUIRED_SECRETS),
        "rows": [{
            "provider": "ENV_ONLY",
            "secrets": secrets_map
        }],
        "error": None
    }


# === Secrets Self-Test API (C-P.20) ===

SELF_TEST_LATEST = BASE_DIR / "reports" / "ops" / "secrets" / "self_test_latest.json"
SELF_TEST_SNAPSHOTS_DIR = BASE_DIR / "reports" / "ops" / "secrets" / "snapshots"

# Channel requirements from PUSH_CHANNELS_V1
CHANNEL_REQUIREMENTS = {
    "TELEGRAM": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
    "SLACK": ["SLACK_WEBHOOK_URL"],
    "EMAIL": ["SMTP_HOST", "SMTP_USER", "SMTP_PASS", "EMAIL_TO"]
}


def run_secrets_self_test() -> dict:
    """시크릿 Self-Test 실행"""
    import os
    
    # Optional: try to load .env
    provider = "ENV_ONLY"
    try:
        from dotenv import load_dotenv
        env_file = BASE_DIR / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            provider = "DOTENV_OPTIONAL"
    except ImportError:
        pass
    
    # Check all secrets
    all_secrets = set()
    for secrets in CHANNEL_REQUIREMENTS.values():
        all_secrets.update(secrets)
    
    secrets_status = {}
    for secret_name in all_secrets:
        secrets_status[secret_name] = bool(os.environ.get(secret_name))
    
    # Evaluate by channel
    missing_required_by_channel = {}
    ready_channels = []
    
    for channel, required in CHANNEL_REQUIREMENTS.items():
        missing = [s for s in required if not secrets_status.get(s, False)]
        missing_required_by_channel[channel] = missing
        if not missing:
            ready_channels.append(channel)
    
    # Decision (Fail Closed)
    if ready_channels:
        decision = "SELF_TEST_PASS"
        ready_count = len(ready_channels)
        reason = f"{ready_channels[0]} channel ready ({len(CHANNEL_REQUIREMENTS[ready_channels[0]])} secrets present)"
    else:
        decision = "SELF_TEST_FAIL"
        reason = "No external channel ready"
    
    present_count = sum(1 for v in secrets_status.values() if v)
    
    result = {
        "schema": "SECRETS_SELF_TEST_V1",
        "asof": datetime.now().isoformat(),
        "provider": provider,
        "secrets_checked_count": len(all_secrets),
        "present_count": present_count,
        "missing_required_by_channel": missing_required_by_channel,
        "decision": decision,
        "reason": reason
    }
    
    return result


@app.get("/api/secrets/self_test", summary="시크릿 Self-Test 결과 조회")
def get_secrets_self_test():
    """Secrets Self-Test Latest (C-P.20)"""
    if not SELF_TEST_LATEST.exists():
        return {
            "status": "empty",
            "schema": "SECRETS_SELF_TEST_V1",
            "row_count": 0,
            "rows": [],
            "error": "No self-test result yet. Run POST /api/secrets/self_test/run"
        }
    
    try:
        data = json.loads(SELF_TEST_LATEST.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "SECRETS_SELF_TEST_V1",
            "asof": data.get("asof"),
            "row_count": 1,
            "rows": [data],
            "error": None
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/secrets/self_test/run", summary="시크릿 Self-Test 실행")
def run_secrets_self_test_api():
    """Secrets Self-Test Run (C-P.20) - No external network calls"""
    try:
        result = run_secrets_self_test()
        
        # Save latest
        SELF_TEST_LATEST.parent.mkdir(parents=True, exist_ok=True)
        SELF_TEST_LATEST.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        
        # Save snapshot
        SELF_TEST_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        snapshot_name = f"self_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        snapshot_path = SELF_TEST_SNAPSHOTS_DIR / snapshot_name
        snapshot_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        
        logger.info(f"Self-test complete: {result['decision']}")
        
        return {
            "result": "OK",
            "decision": result["decision"],
            "reason": result["reason"],
            "snapshot_path": str(snapshot_path.relative_to(BASE_DIR))
        }
    except Exception as e:
        logger.error(f"Self-test error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})


# === Push Preview API (C-P.22) ===

PREVIEW_LATEST = BASE_DIR / "reports" / "ops" / "push" / "preview" / "preview_latest.json"


@app.get("/api/push/preview/latest", summary="푸시 렌더 프리뷰 최신 조회")
def get_push_preview_latest():
    """Push Render Preview Latest (C-P.22)"""
    if not PREVIEW_LATEST.exists():
        return {
            "status": "empty",
            "schema": "PUSH_RENDER_PREVIEW_V1",
            "row_count": 0,
            "rows": [],
            "error": "No preview generated yet. Generate via push delivery cycle."
        }
    
    try:
        data = json.loads(PREVIEW_LATEST.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "PUSH_RENDER_PREVIEW_V1",
            "asof": data.get("asof"),
            "row_count": len(data.get("rendered", [])),
            "rows": data.get("rendered", []),
            "data": data,
            "error": None
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# === Real Sender Enable API (C-P.23) ===

SENDER_ENABLE_FILE = STATE_DIR / "real_sender_enable.json"


@app.get("/api/real_sender_enable", summary="Real Sender 활성화 상태 조회")
def get_real_sender_enable():
    """Real Sender Enable Status (C-P.23)"""
    if not SENDER_ENABLE_FILE.exists():
        return {
            "status": "ready",
            "schema": "REAL_SENDER_ENABLE_V1",
            "data": {
                "enabled": False,
                "channel": "TELEGRAM_ONLY",
                "updated_at": None,
                "updated_by": None,
                "reason": "Not configured"
            },
            "error": None
        }
    
    try:
        data = json.loads(SENDER_ENABLE_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "REAL_SENDER_ENABLE_V1",
            "data": data,
            "error": None
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


class SenderEnableRequest(BaseModel):
    enabled: bool
    reason: Optional[str] = None


@app.post("/api/real_sender_enable", summary="Real Sender 활성화/비활성화")
def set_real_sender_enable(request: SenderEnableRequest):
    """Real Sender Enable/Disable (C-P.23)"""
    # Enable requires reason
    if request.enabled and not request.reason:
        raise HTTPException(status_code=400, detail={"error": "reason is required when enabling"})
    
    data = {
        "schema": "REAL_SENDER_ENABLE_V1",
        "enabled": request.enabled,
        "channel": "TELEGRAM_ONLY",
        "updated_at": datetime.now().isoformat(),
        "updated_by": "api",
        "reason": request.reason or "Disabled"
    }
    
    SENDER_ENABLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SENDER_ENABLE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    logger.info(f"Real sender {'enabled' if request.enabled else 'disabled'}: {request.reason}")
    
    return {
        "result": "OK",
        "enabled": request.enabled,
        "channel": "TELEGRAM_ONLY"
    }


# === Push Send API (C-P.23) ===

SEND_LATEST_FILE = BASE_DIR / "reports" / "ops" / "push" / "send" / "send_latest.json"


@app.get("/api/push/send/latest", summary="최신 발송 결과 조회")
def get_push_send_latest():
    """Push Send Latest (C-P.23)"""
    if not SEND_LATEST_FILE.exists():
        return {
            "status": "empty",
            "schema": "PUSH_SEND_RECEIPT_V1",
            "data": None,
            "error": "No send receipt yet"
        }
    
    try:
        data = json.loads(SEND_LATEST_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "PUSH_SEND_RECEIPT_V1",
            "data": data,
            "error": None
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/push/send/run", summary="푸시 발송 실행 (One-Shot)")
def run_push_send():
    """Push Send Run (C-P.23) - One-Shot Telegram Only"""
    try:
        from app.run_push_send_cycle import run_push_send_cycle
        result = run_push_send_cycle()
        logger.info(f"Push send: {result.get('decision')} - {result.get('message')}")
        return result
    except ImportError as e:
        logger.error(f"Push send import error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": f"Import error: {e}"})
    except Exception as e:
        logger.error(f"Push send error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})


# === Push Postmortem API (C-P.25) ===

POSTMORTEM_LATEST = BASE_DIR / "reports" / "ops" / "push" / "postmortem" / "postmortem_latest.json"


@app.get("/api/ops/push/postmortem/latest", summary="Postmortem 최신 조회")
def get_postmortem_latest():
    """Live Fire Postmortem Latest (C-P.25)"""
    if not POSTMORTEM_LATEST.exists():
        return {
            "status": "empty",
            "schema": "LIVE_FIRE_POSTMORTEM_V1",
            "data": None,
            "error": "No postmortem generated yet. Use regenerate endpoint."
        }
    
    try:
        data = json.loads(POSTMORTEM_LATEST.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "LIVE_FIRE_POSTMORTEM_V1",
            "data": data,
            "error": None
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/ops/push/postmortem/regenerate", summary="Postmortem 재생성")
def regenerate_postmortem():
    """Regenerate Live Fire Postmortem (C-P.25)"""
    try:
        from app.generate_live_fire_postmortem import generate_postmortem
        result = generate_postmortem()
        logger.info(f"Postmortem regenerated: {result.get('overall_safety_status')}")
        return result
    except ImportError as e:
        logger.error(f"Postmortem import error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": f"Import error: {e}"})
    except Exception as e:
        logger.error(f"Postmortem error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})


# === Live Fire Ops API (C-P.26) ===

LIVE_FIRE_LATEST = BASE_DIR / "reports" / "ops" / "push" / "live_fire" / "live_fire_latest.json"


@app.get("/api/ops/push/live_fire/latest", summary="Live Fire Ops 최신 조회")
def get_live_fire_latest():
    """Live Fire Ops Receipt Latest (C-P.26)"""
    if not LIVE_FIRE_LATEST.exists():
        return {
            "status": "empty",
            "schema": "LIVE_FIRE_OPS_RECEIPT_V1",
            "data": None,
            "error": "No live fire ops run yet."
        }
    
    try:
        data = json.loads(LIVE_FIRE_LATEST.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "LIVE_FIRE_OPS_RECEIPT_V1",
            "data": data,
            "error": None
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/ops/push/live_fire/run", summary="Live Fire Ops 실행")
def run_live_fire_ops_api():
    """Run Live Fire Ops Cycle (C-P.26)"""
    try:
        from app.run_live_fire_ops import run_live_fire_ops
        result = run_live_fire_ops()
        logger.info(f"Live Fire Ops: attempted={result.get('attempted')}, blocked={result.get('blocked_reason')}")
        return result
    except ImportError as e:
        logger.error(f"Live Fire Ops import error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": f"Import error: {e}"})
    except Exception as e:
        logger.error(f"Live Fire Ops error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})


# === Ops Scheduler API (C-P.28) ===

SCHEDULER_LATEST_DIR = BASE_DIR / "reports" / "ops" / "scheduler" / "latest"
SCHEDULER_SNAPSHOTS_DIR = BASE_DIR / "reports" / "ops" / "scheduler" / "snapshots"
OPS_RUN_LATEST = SCHEDULER_LATEST_DIR / "ops_run_latest.json"


@app.get("/api/ops/scheduler/latest", summary="Ops Run Receipt 최신 조회")
def get_scheduler_latest():
    """Ops Run Receipt Latest (C-P.28) - Graceful Empty State"""
    from datetime import datetime
    
    if not OPS_RUN_LATEST.exists():
        return {
            "status": "not_ready",
            "schema": "OPS_RUN_RECEIPT_V1",
            "asof": datetime.now().isoformat(),
            "row_count": 0,
            "rows": [],
            "error": {
                "code": "NO_RUN_HISTORY",
                "message": "No run history yet."
            }
        }
    
    try:
        data = json.loads(OPS_RUN_LATEST.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "OPS_RUN_RECEIPT_V1",
            "asof": data.get("asof"),
            "row_count": 1,
            "rows": [data],
            "error": None
        }
    except Exception as e:
        return {
            "status": "error",
            "schema": "OPS_RUN_RECEIPT_V1",
            "asof": datetime.now().isoformat(),
            "row_count": 0,
            "rows": [],
            "error": {
                "code": "READ_ERROR",
                "message": str(e)
            }
        }


@app.get("/api/ops/scheduler/snapshots", summary="Ops Run Snapshots 목록")
def get_scheduler_snapshots():
    """Ops Scheduler Snapshots List (C-P.28) - No Path Traversal"""
    from datetime import datetime
    import os
    
    # 하드코딩된 경로만 사용 (Path Traversal 방지)
    snapshots_dir = SCHEDULER_SNAPSHOTS_DIR
    
    if not snapshots_dir.exists():
        return {
            "status": "ready",
            "schema": "OPS_SCHEDULER_SNAPSHOTS_V1",
            "asof": datetime.now().isoformat(),
            "directory": str(snapshots_dir.relative_to(BASE_DIR)),
            "row_count": 0,
            "rows": [],
            "error": None
        }
    
    try:
        files = []
        for f in sorted(snapshots_dir.iterdir(), reverse=True)[:20]:  # 최신 20개만
            if f.is_file() and f.suffix == ".json":
                stat = f.stat()
                files.append({
                    "filename": f.name,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size_bytes": stat.st_size
                })
        
        return {
            "status": "ready",
            "schema": "OPS_SCHEDULER_SNAPSHOTS_V1",
            "asof": datetime.now().isoformat(),
            "directory": str(snapshots_dir.relative_to(BASE_DIR)),
            "row_count": len(files),
            "rows": files,
            "error": None
        }
    except Exception as e:
        return {
            "status": "error",
            "schema": "OPS_SCHEDULER_SNAPSHOTS_V1",
            "asof": datetime.now().isoformat(),
            "directory": str(snapshots_dir.relative_to(BASE_DIR)),
            "row_count": 0,
            "rows": [],
            "error": {
                "code": "READ_ERROR",
                "message": str(e)
            }
        }


@app.get("/api/ops/scheduler/snapshots/{snapshot_id}", summary="스냅샷 단건 조회")
def get_scheduler_snapshot_by_id(snapshot_id: str):
    """Ops Scheduler Snapshot Single View (C-P.29) - Path Traversal Prevention"""
    from datetime import datetime
    import re
    
    # Path Traversal 방지: 화이트리스트 정규식 검증
    pattern = r'^[a-zA-Z0-9_\-\.]+\.json$'
    if not re.match(pattern, snapshot_id):
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "schema": "OPS_SNAPSHOT_VIEWER_V1",
                "error": {
                    "code": "INVALID_ID",
                    "message": f"Invalid snapshot_id format: {snapshot_id}"
                }
            }
        )
    
    # 추가 검증: 경로 구분자 포함 여부
    if '/' in snapshot_id or '\\' in snapshot_id or '..' in snapshot_id:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "schema": "OPS_SNAPSHOT_VIEWER_V1",
                "error": {
                    "code": "INVALID_ID",
                    "message": "Path traversal detected"
                }
            }
        )
    
    # 하드코딩된 디렉토리에서만 조회
    snapshot_path = SCHEDULER_SNAPSHOTS_DIR / snapshot_id
    
    if not snapshot_path.exists():
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "schema": "OPS_SNAPSHOT_VIEWER_V1",
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Snapshot not found: {snapshot_id}"
                }
            }
        )
    
    try:
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": data.get("schema", "OPS_RUN_RECEIPT_V1"),
            "snapshot_id": snapshot_id,
            "data": data
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "schema": "OPS_SNAPSHOT_VIEWER_V1",
                "error": {
                    "code": "READ_ERROR",
                    "message": str(e)
                }
            }
        )



# === Order Plan Export API (P111) ===

EXPORT_LATEST_FILE = BASE_DIR / "reports" / "live" / "order_plan_export" / "latest" / "order_plan_export_latest.json"

@app.get("/api/order_plan_export/latest", summary="Order Plan Export 최신 조회")
def get_order_plan_export_latest():
    """Order Plan Export Latest (P111)"""
    if not EXPORT_LATEST_FILE.exists():
        return {
            "status": "empty",
            "schema": "ORDER_PLAN_EXPORT_V1",
            "data": None,
            "error": "No export generated yet."
        }
    
    try:
        data = json.loads(EXPORT_LATEST_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "ORDER_PLAN_EXPORT_V1",
            "data": data,
            "error": None
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/order_plan_export/regenerate", summary="Order Plan Export 재생성")
def regenerate_order_plan_export(confirm: bool = Query(False)):
    """Regenerate Order Plan Export (P111) - Requires Confirm"""
    if not confirm:
        raise HTTPException(status_code=400, detail={"result": "BLOCKED", "reason": "CONFIRM_REQUIRED"})
        
    try:
        from app.generate_order_plan_export import generate_export
        generate_export()
        
        if EXPORT_LATEST_FILE.exists():
            data = json.loads(EXPORT_LATEST_FILE.read_text(encoding="utf-8"))
            return data
        else:
            return {"result": "FAIL", "reason": "Generation failed (No file)"}
            
    except ImportError as e:
        logger.error(f"Export import error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": f"Import error: {e}"})
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})


# === Execution Prep API (P112) ===

EXECUTION_PREP_LATEST_FILE = BASE_DIR / "reports" / "live" / "execution_prep" / "latest" / "execution_prep_latest.json"

@app.get("/api/execution_prep/latest", summary="Execution Prep 최신 조회")
def get_execution_prep_latest():
    """Execution Prep Latest (P112)"""
    if not EXECUTION_PREP_LATEST_FILE.exists():
        return {
            "status": "empty",
            "schema": "EXECUTION_PREP_V1",
            "data": None,
            "error": "No execution prep generated yet."
        }
    
    try:
        data = json.loads(EXECUTION_PREP_LATEST_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "EXECUTION_PREP_V1",
            "data": data,
            "error": None
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

class ExecutionPrepRequest(BaseModel):
    confirm_token: str

@app.post("/api/execution_prep/prepare", summary="Execution Prep 생성 (Human Gate)")
def prepare_execution(request: ExecutionPrepRequest, confirm: bool = Query(False)):
    """Prepare Execution (P112) - Requires Confirm + Token"""
    if not confirm:
        raise HTTPException(status_code=400, detail={"result": "BLOCKED", "reason": "CONFIRM_REQUIRED"})
        
    if not request.confirm_token:
         raise HTTPException(status_code=400, detail={"result": "BLOCKED", "reason": "TOKEN_REQUIRED"})

    try:
        from app.generate_execution_prep import generate_prep
        generate_prep(request.confirm_token)
        
        if EXECUTION_PREP_LATEST_FILE.exists():
            data = json.loads(EXECUTION_PREP_LATEST_FILE.read_text(encoding="utf-8"))
            return data
        else:
            return {"result": "FAIL", "reason": "Generation failed (No file)"}
            
    except ImportError as e:
        logger.error(f"Prep import error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": f"Import error: {e}"})
    except Exception as e:
        logger.error(f"Prep error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})


# === Manual Execution API (P113-A) ===

TICKET_LATEST_FILE = BASE_DIR / "reports" / "live" / "manual_execution_ticket" / "latest" / "manual_execution_ticket_latest.json"
RECORD_LATEST_FILE = BASE_DIR / "reports" / "live" / "manual_execution_record" / "latest" / "manual_execution_record_latest.json"

# Ticket
@app.get("/api/manual_execution_ticket/latest", summary="Manual Execution Ticket 최신 조회")
def get_manual_execution_ticket_latest():
    """Manual Execution Ticket Latest (P113-A)"""
    if not TICKET_LATEST_FILE.exists():
        return {
            "status": "empty",
            "schema": "MANUAL_EXECUTION_TICKET_V1",
            "data": None,
            "error": "No ticket generated yet."
        }
    try:
        data = json.loads(TICKET_LATEST_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "MANUAL_EXECUTION_TICKET_V1",
            "data": data,
            "error": None
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/manual_execution_ticket/regenerate", summary="Manual Execution Ticket 재생성")
def regenerate_manual_execution_ticket(confirm: bool = Query(False)):
    """Regenerate Manual Execution Ticket (P113-A / P146.6) - Aligns to Export plan_id"""
    if not confirm:
        raise HTTPException(status_code=400, detail={"result": "BLOCKED", "reason": "CONFIRM_REQUIRED"})
        
    try:
        from app.generate_manual_execution_ticket import generate_ticket
        generate_ticket()
        
        if not TICKET_LATEST_FILE.exists():
            return {"result": "FAIL", "reason": "Generation failed (No file)"}
        
        data = json.loads(TICKET_LATEST_FILE.read_text(encoding="utf-8"))
        
        # P146.6: Patch plan_id to match Export (SSOT alignment)
        export_path = REPORTS_DIR / "live" / "order_plan_export" / "latest" / "order_plan_export_latest.json"
        if export_path.exists():
            try:
                export_data = json.loads(export_path.read_text(encoding="utf-8"))
                export_plan_id = export_data.get("source", {}).get("plan_id")
                if export_plan_id:
                    old_plan_id = data.get("source", {}).get("plan_id")
                    data["source"]["plan_id"] = export_plan_id
                    data["source"]["_aligned_from"] = "export"
                    data["source"]["_original_prep_plan_id"] = old_plan_id
                    # Save patched ticket back
                    TICKET_LATEST_FILE.write_text(
                        json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8"
                    )
                    logger.info(f"P146.6: Ticket plan_id patched {old_plan_id} -> {export_plan_id}")
            except Exception as e:
                logger.warning(f"P146.6: Export read failed, keeping prep plan_id: {e}")
        
        return data
            
    except ImportError as e:
        logger.error(f"Ticket import error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": f"Import error: {e}"})
    except Exception as e:
        logger.error(f"Ticket error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})

# Record
@app.get("/api/manual_execution_record/latest", summary="Manual Execution Record 최신 조회")
def get_manual_execution_record_latest():
    """Manual Execution Record Latest (P113-A)"""
    if not RECORD_LATEST_FILE.exists():
        return {
            "status": "empty",
            "schema": "MANUAL_EXECUTION_RECORD_V1",
            "data": None,
            "error": "No record generated yet."
        }
    try:
        data = json.loads(RECORD_LATEST_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "MANUAL_EXECUTION_RECORD_V1",
            "data": data,
            "error": None
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

class ManualExecutionItem(BaseModel):
    ticker: str
    side: str
    status: str # EXECUTED | SKIPPED
    executed_qty: Optional[int] = 0
    note: Optional[str] = ""

class ManualExecutionRecordRequest(BaseModel):
    confirm_token: str
    items: List[ManualExecutionItem]


# Draft Record (P146.2)
DRAFT_DIR = BASE_DIR / "reports" / "live" / "manual_execution_record" / "draft"
DRAFT_LATEST_FILE = DRAFT_DIR / "latest" / "manual_execution_record_draft_latest.json"
ORDER_PLAN_EXPORT_LATEST_FILE = BASE_DIR / "reports" / "live" / "order_plan_export" / "latest" / "order_plan_export_latest.json"

# Ensure Draft Dir
(DRAFT_DIR / "latest").mkdir(parents=True, exist_ok=True)

def _load_json(path: Path) -> dict:
    if path.exists():
        try:
           return json.loads(path.read_text(encoding="utf-8"))
        except:
           return None
    return None

@app.post("/api/manual_execution_record/draft", summary="Draft Record 생성 (Server-Side)")
def generate_draft_record():
    """Generate Manual Execution Record Draft (Server-Side) - P146.2"""
    try:
        # 1. Paths (local to avoid NameError)
        _ticket_path = REPORTS_DIR / "live" / "manual_execution_ticket" / "latest" / "manual_execution_ticket_latest.json"
        _export_path = REPORTS_DIR / "live" / "order_plan_export" / "latest" / "order_plan_export_latest.json"
        _prep_path = REPORTS_DIR / "live" / "execution_prep" / "latest" / "execution_prep_latest.json"
        _summary_path = REPORTS_DIR / "ops" / "summary" / "latest" / "ops_summary_latest.json"
        _draft_path = REPORTS_DIR / "live" / "manual_execution_record" / "draft" / "latest" / "manual_execution_record_draft_latest.json"
        _draft_path.parent.mkdir(parents=True, exist_ok=True)

        # 2. Load artifacts
        ticket = _load_json(_ticket_path)
        export = _load_json(_export_path)

        if not ticket or not export:
            return {"result": "BLOCKED", "reason": "Missing Ticket or Order Plan Export. Cannot generate draft."}

        # Optional summary check (non-blocking)
        summary = _load_json(_summary_path)

        # 3. Load Prep (optional for linkage)
        prep = _load_json(_prep_path)
        if not prep:
            prep = {}

        # 4. Validate Linkage — P146.5 Fail-Closed
        prep_plan_id = prep.get("source", {}).get("plan_id")
        ticket_plan_id = ticket.get("source", {}).get("plan_id")
        export_plan_id = export.get("source", {}).get("plan_id")

        present_ids = {k: v for k, v in {
            "prep": prep_plan_id, "ticket": ticket_plan_id, "export": export_plan_id
        }.items() if v is not None}
        unique_ids = set(present_ids.values())
        
        if len(unique_ids) > 1:
            return {
                "result": "BLOCKED",
                "reason": "PLAN_ID_MISMATCH",
                "detail": present_ids,
                "guidance": "plan_id가 일치하지 않습니다. PC에서 Auto Ops를 재실행하여 한 회전으로 맞춰주세요."
            }

        # 5. Construct Draft
        items = []
        for order in export.get("orders", []):
            items.append({
                "ticker": order.get("ticker"),
                "side": order.get("side"),
                "status": "EXECUTED",
                "qty_planned": order.get("qty", 0),
                "executed_qty": order.get("qty", 0),
                "avg_price": None,
                "note": ""
            })

        draft = {
            "schema": "MANUAL_EXECUTION_RECORD_DRAFT_V1",
            "asof": datetime.now().isoformat(),
            "source_refs": {
                "prep_ref": prep.get("source", {}).get("order_plan_ref")
            },
            "linkage": {
                "prep_plan_id": prep_plan_id,
                "ticket_plan_id": ticket_plan_id,
                "export_plan_id": export_plan_id,
                "ticket_id": ticket.get("ticket_id")
            },
            "items": items,
            "dedupe": {
                "idempotency_key": ""
            }
        }

        # 6. Sanitize & Save
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
        _draft_path.write_text(json.dumps(sanitized_draft, indent=2, ensure_ascii=False), encoding="utf-8")

        return {"result": "OK", "path": str(_draft_path), "count": len(items)}

    except Exception as e:
        logger.error(f"Draft Gen Error: {e}")
        return {"result": "ERROR", "reason": str(e)}

@app.get("/api/manual_execution_record/draft", summary="Draft Record 다운로드")
def get_draft_record():
    """Get Latest Draft Record JSON"""
    if not DRAFT_LATEST_FILE.exists():
        raise HTTPException(status_code=404, detail="No Draft Found")
        
    return FileResponse(path=DRAFT_LATEST_FILE, media_type='application/json', filename="manual_execution_record_draft.json")


def submit_manual_execution_record(request: ManualExecutionRecordRequest, confirm: bool = Query(False)):
    """Submit Manual Execution Record (P113-A) - Requires Confirm + Token"""
    if not confirm:
        raise HTTPException(status_code=400, detail={"result": "BLOCKED", "reason": "CONFIRM_REQUIRED"})
    
    if not request.confirm_token:
         raise HTTPException(status_code=400, detail={"result": "BLOCKED", "reason": "TOKEN_REQUIRED"})

    try:
        from app.generate_manual_execution_record import generate_record
        # Pass full items_data dict as expected by generate_record
        generate_record(request.confirm_token, request.dict())
        
        if RECORD_LATEST_FILE.exists():
            data = json.loads(RECORD_LATEST_FILE.read_text(encoding="utf-8"))
            return data
        else:
            return {"result": "FAIL", "reason": "Generation failed (No file)"}
    except ImportError as e:
        logger.error(f"Record import error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": f"Import error: {e}"})
    except Exception as e:
        logger.error(f"Record error: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})
# === Evidence Ref Resolver API (C-P.30) ===


# 허용된 JSONL 파일 (정확히 2개만)
ALLOWED_JSONL_FILES = {
    "state/tickets/ticket_receipts.jsonl",
    "state/push/send_receipts.jsonl"
}

# 허용된 JSON 디렉토리 패턴
ALLOWED_JSON_PATTERNS = [
    r"^reports/ops/scheduler/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    r"^reports/ops/push/postmortem/postmortem_latest\.json$",
    r"^reports/ops/secrets/self_test_latest\.json$",
    r"^reports/ops/push/outbox/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    r"^reports/ops/push/outbox/outbox_latest\.json$",
    r"^reports/ops/push/live_fire/live_fire_latest\.json$",
    r"^reports/ops/push/live_fire/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    r"^reports/ops/daily/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    # C-P.32.1: evidence_refs 호환
    r"^reports/ops/evidence/index/evidence_index_latest\.json$",
    r"^reports/ops/evidence/index/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    r"^reports/ops/push/send/send_latest\.json$",
    r"^reports/ops/push/send/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    r"^reports/ops/push/preview/preview_latest\.json$",
    r"^reports/phase_c/latest/recon_summary\.json$",
    r"^reports/phase_c/latest/report_human\.json$"
]

# JSONL 패턴
JSONL_REF_PATTERN = r"^(state/tickets/ticket_receipts\.jsonl|state/push/send_receipts\.jsonl):line(\d+)$"


@app.get("/api/evidence/resolve", summary="Evidence Ref Resolver")
def resolve_evidence_ref(ref: str):
    """Evidence Ref Resolver (C-P.30/33) - Uses shared ref_validator"""
    from datetime import datetime
    from app.utils.ref_validator import validate_and_resolve_ref
    
    asof = datetime.now().isoformat()
    
    # 공용 Validator 호출 (C-P.33 단일화)
    result = validate_and_resolve_ref(ref)
    
    # HTTP 상태 코드로 변환
    if result.http_status_equivalent == 400:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "schema": "EVIDENCE_VIEW_V1",
                "asof": asof,
                "error": {
                    "code": result.decision,
                    "message": result.reason
                }
            }
        )
    
    if result.http_status_equivalent == 404:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "schema": "EVIDENCE_VIEW_V1",
                "asof": asof,
                "error": {
                    "code": result.decision,
                    "message": result.reason
                }
            }
        )
    
    # 200 OK
    if result.decision == "PARSE_ERROR":
        return {
            "status": "error",
            "schema": "EVIDENCE_VIEW_V1",
            "asof": asof,
            "row_count": 0,
            "rows": [],
            "error": {
                "code": "PARSE_ERROR",
                "message": result.reason
            },
            "raw_preview": result.raw_content,
            "guidance": "이 파일은 유효한 JSON이 아닙니다. Draft라면 Draft Manager에서 재생성해주세요."
        }
    
    return {
        "status": "ready",
        "schema": "EVIDENCE_VIEW_V1",
        "asof": asof,
        "row_count": 1,
        "rows": [{
            "ref": ref,
            "data": result.data,
            "source": {
                "kind": result.source_kind,
                "path": result.resolved_path,
                "line": result.source_line
            }
        }],
        "error": None
    }


# === Evidence Index API (C-P.31) ===

EVIDENCE_INDEX_DIR = BASE_DIR / "reports" / "ops" / "evidence" / "index"
EVIDENCE_INDEX_LATEST = EVIDENCE_INDEX_DIR / "evidence_index_latest.json"


@app.get("/api/evidence/index/latest", summary="Evidence Index 최신 조회")
def get_evidence_index_latest():
    """Evidence Index Latest (C-P.31) - Graceful Empty State"""
    from datetime import datetime
    
    if not EVIDENCE_INDEX_LATEST.exists():
        return {
            "status": "ready",
            "schema": "EVIDENCE_INDEX_V1",
            "asof": None,
            "row_count": 0,
            "rows": [],
            "error": {
                "code": "NO_INDEX_YET",
                "message": "Evidence index not generated yet."
            }
        }
    
    try:
        data = json.loads(EVIDENCE_INDEX_LATEST.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "EVIDENCE_INDEX_V1",
            "asof": data.get("asof"),
            "row_count": data.get("row_count", 0),
            "rows": data.get("rows", []),
            "error": None
        }
    except Exception as e:
        return {
            "status": "error",
            "schema": "EVIDENCE_INDEX_V1",
            "asof": datetime.now().isoformat(),
            "row_count": 0,
            "rows": [],
            "error": {
                "code": "READ_ERROR",
                "message": str(e)
            }
        }


@app.post("/api/evidence/index/regenerate", summary="Evidence Index 재생성")
def regenerate_evidence_index():
    """Evidence Index Regenerate (C-P.31) - No path input"""
    try:
        from app.generate_evidence_index import regenerate_index
        result = regenerate_index()
        return result
    except ImportError as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": f"Import error: {e}"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": str(e)
        })


# === Evidence Health API (C-P.33) ===

HEALTH_DIR = BASE_DIR / "reports" / "ops" / "evidence" / "health"
HEALTH_LATEST_FILE = HEALTH_DIR / "health_latest.json"


@app.get("/api/evidence/health/latest", summary="Evidence Health 최신 조회")
def get_evidence_health_latest():
    """Evidence Health Latest (C-P.33) - Graceful Empty State"""
    from datetime import datetime
    
    if not HEALTH_LATEST_FILE.exists():
        return {
            "status": "ready",
            "schema": "EVIDENCE_HEALTH_REPORT_V1",
            "asof": None,
            "summary": {
                "total": 0,
                "pass": 0,
                "warn": 0,
                "fail": 0,
                "decision": "UNKNOWN"
            },
            "checks": [],
            "top_fail_reasons": [],
            "error": {
                "code": "NO_REPORT_YET",
                "message": "Health report not generated yet."
            }
        }
    
    try:
        data = json.loads(HEALTH_LATEST_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            **data,
            "error": None
        }
    except Exception as e:
        return {
            "status": "error",
            "schema": "EVIDENCE_HEALTH_REPORT_V1",
            "asof": datetime.now().isoformat(),
            "summary": {"total": 0, "pass": 0, "warn": 0, "fail": 0, "decision": "UNKNOWN"},
            "checks": [],
            "top_fail_reasons": [],
            "error": {
                "code": "READ_ERROR",
                "message": str(e)
            }
        }


@app.post("/api/evidence/health/regenerate", summary="Evidence Health 재생성")
def regenerate_evidence_health():
    """Evidence Health Regenerate (C-P.33) - No subprocess"""
    try:
        from app.run_evidence_health_check import regenerate_health_report
        result = regenerate_health_report()
        return result
    except ImportError as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": f"Import error: {e}"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": str(e)
        })



# === Ops Summary API (C-P.35) ===

SUMMARY_DIR = BASE_DIR / "reports" / "ops" / "summary"
SUMMARY_LATEST_FILE = SUMMARY_DIR / "ops_summary_latest.json"


@app.get("/api/ops/summary/latest", summary="Ops Summary 최신 조회")
def get_ops_summary_latest():
    """Ops Summary Latest (C-P.35) - Single Pane of Glass"""
    from datetime import datetime
    
    if not SUMMARY_LATEST_FILE.exists():
        return {
            "status": "ready",
            "schema": "OPS_SUMMARY_V1",
            "asof": None,
            "row_count": 1,
            "rows": [{
                "overall_status": "NO_RUN_HISTORY",
                "guard": None,
                "last_run_triplet": None,
                "tickets": None,
                "push": None,
                "evidence": None,
                "top_risks": []
            }],
            "error": {
                "code": "NO_SUMMARY_YET",
                "message": "Ops summary not generated yet."
            }
        }
    
    try:
        data = json.loads(SUMMARY_LATEST_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "OPS_SUMMARY_V1",
            "asof": data.get("asof"),
            "row_count": 1,
            "rows": [data],
            "error": None
        }
    except Exception as e:
        return {
            "status": "error",
            "schema": "OPS_SUMMARY_V1",
            "asof": datetime.now().isoformat(),
            "row_count": 0,
            "rows": [],
            "error": {
                "code": "READ_ERROR",
                "message": str(e)
            }
        }


@app.post("/api/ops/summary/regenerate", summary="Ops Summary 재생성")
def regenerate_ops_summary_endpoint():
    """Ops Summary Regenerate (C-P.35) - No subprocess"""
    try:
        from app.generate_ops_summary import generate_ops_summary
        result = generate_ops_summary()
        return result
    except ImportError as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": f"Import error: {e}"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": str(e)
        })


# === Ops Drill API (C-P.37) ===

DRILL_LATEST_FILE = BASE_DIR / "reports" / "ops" / "drill" / "latest" / "drill_latest.json"


@app.get("/api/ops/drill/latest", summary="Ops Drill 최신 조회")
def get_ops_drill_latest():
    """Ops Drill Latest (C-P.37) - Golden Build Proof"""
    from datetime import datetime
    
    if not DRILL_LATEST_FILE.exists():
        return {
            "status": "not_ready",
            "schema": "OPS_DRILL_REPORT_V1",
            "asof": None,
            "row": None,
            "error": {
                "code": "NO_DRILL_YET",
                "message": "Drill report not generated yet."
            }
        }
    
    try:
        data = json.loads(DRILL_LATEST_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "OPS_DRILL_REPORT_V1",
            "asof": data.get("asof"),
            "row": data,
            "error": None
        }
    except Exception as e:
        return {
            "status": "error",
            "schema": "OPS_DRILL_REPORT_V1",
            "asof": datetime.now().isoformat(),
            "row": None,
            "error": {
                "code": "READ_ERROR",
                "message": str(e)
            }
        }


@app.post("/api/ops/drill/run", summary="Ops Drill 실행")
def run_ops_drill_api():
    """Ops Drill Run (C-P.37) - End-to-End Pipeline Test"""
    try:
        from app.run_ops_drill import run_ops_drill
        result = run_ops_drill()
        return result
    except ImportError as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": f"Import error: {e}"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": str(e)
        })


# === Ticket Reaper API (C-P.43) ===

REAPER_LATEST_FILE = BASE_DIR / "reports" / "ops" / "tickets" / "reaper" / "latest" / "reaper_latest.json"


@app.get("/api/tickets/reaper/latest", summary="Ticket Reaper 최신 조회")
def get_ticket_reaper_latest():
    """Ticket Reaper Latest (C-P.43) - Stale IN_PROGRESS Cleanup Report"""
    if not REAPER_LATEST_FILE.exists():
        return {
            "schema": "TICKET_REAPER_REPORT_V1",
            "asof": datetime.now().isoformat(),
            "decision": "NONE",
            "message": "No reaper report yet"
        }
    
    try:
        data = json.loads(REAPER_LATEST_FILE.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        return {
            "schema": "TICKET_REAPER_REPORT_V1",
            "asof": datetime.now().isoformat(),
            "decision": "ERROR",
            "error": str(e)
        }


class ReaperRunRequest(BaseModel):
    threshold_seconds: int = 86400
    max_clean: int = 50


@app.post("/api/tickets/reaper/run", summary="Ticket Reaper 실행")
def run_ticket_reaper_api(data: ReaperRunRequest = ReaperRunRequest()):
    """Ticket Reaper Run (C-P.43) - Clean Stale IN_PROGRESS Tickets"""
    try:
        from app.run_ticket_reaper import run_ticket_reaper
        result = run_ticket_reaper(
            threshold_seconds=data.threshold_seconds,
            max_clean=data.max_clean
        )
        return result
    except ImportError as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": f"Import error: {e}"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": str(e)
        })


# === Strategy Bundle API (C-P.47) ===

@app.get("/api/strategy_bundle/latest", summary="Strategy Bundle 최신 조회")
def get_strategy_bundle_latest():
    """
    Strategy Bundle Latest (C-P.47)
    
    PC에서 생성된 전략 번들 조회 + 검증 결과 반환
    Fail-Closed: 검증 실패 시 번들 미반환
    """
    try:
        from app.load_strategy_bundle import load_latest_bundle, get_bundle_status, list_snapshots
        
        bundle, validation = load_latest_bundle()
        status = get_bundle_status()
        snapshots = list_snapshots()
        
        return {
            "schema": "STRATEGY_BUNDLE_V1",
            "asof": datetime.now().isoformat(),
            "status": "ready" if bundle else "not_ready",
            "bundle": bundle,  # None if validation failed (Fail-Closed)
            "validation": {
                "decision": validation.decision,
                "valid": validation.valid,
                "bundle_id": validation.bundle_id,
                "created_at": validation.created_at,
                "strategy_name": validation.strategy_name,
                "strategy_version": validation.strategy_version,
                "issues": validation.issues,
                "warnings": validation.warnings
            },
            "summary": status,
            "snapshots": snapshots[:5],  # 최근 5개
            "error": None if bundle else {"code": validation.decision, "message": "; ".join(validation.issues)}
        }
    except ImportError as e:
        return {
            "schema": "STRATEGY_BUNDLE_V1",
            "asof": datetime.now().isoformat(),
            "status": "error",
            "bundle": None,
            "validation": None,
            "error": {"code": "IMPORT_ERROR", "message": str(e)}
        }
    except Exception as e:
        return {
            "schema": "STRATEGY_BUNDLE_V1",
            "asof": datetime.now().isoformat(),
            "status": "error",
            "bundle": None,
            "validation": None,
            "error": {"code": "UNKNOWN_ERROR", "message": str(e)}
        }


class StrategyBundleSnapshotRequest(BaseModel):
    confirm: bool = False


@app.post("/api/strategy_bundle/regenerate_snapshot", summary="Strategy Bundle Snapshot 생성")
def regenerate_strategy_bundle_snapshot(data: StrategyBundleSnapshotRequest):
    """
    Strategy Bundle Snapshot 생성 (C-P.47)
    
    latest를 snapshot으로 복제 (고정 경로만, 입력 경로 금지)
    Confirm Guard: confirm=true 필수
    """
    # Confirm Guard
    if not data.confirm:
        return JSONResponse(
            status_code=400,
            content={
                "result": "BLOCKED",
                "message": "Confirm guard: set confirm=true to proceed",
                "snapshot_ref": None
            }
        )
    
    try:
        from app.load_strategy_bundle import regenerate_snapshot
        
        result = regenerate_snapshot()
        
        if result["success"]:
            logger.info(f"Strategy bundle snapshot created: {result['snapshot_ref']}")
            return {
                "result": "OK",
                "snapshot_ref": result["snapshot_ref"],
                "bundle_id": result.get("bundle_id"),
                "created_at": result.get("created_at")
            }
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "result": "FAILED",
                    "message": result.get("error", "Unknown error"),
                    "snapshot_ref": None
                }
            )
    except ImportError as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": f"Import error: {e}"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": str(e)
        })


# === Reco API (D-P.48) ===

@app.get("/api/reco/latest", summary="추천 리포트 최신 조회")
def get_reco_latest():
    """
    Reco Report Latest (D-P.48)
    
    추천 리포트 조회 + 상태 반환
    Graceful: 리포트 없으면 NO_RECO_YET
    """
    try:
        from app.generate_reco_report import load_latest_reco, get_reco_status, list_snapshots
        
        report = load_latest_reco()
        status = get_reco_status()
        snapshots = list_snapshots()
        
        return {
            "schema": "RECO_REPORT_V1",
            "asof": datetime.now().isoformat(),
            "status": "ready" if report else "no_reco_yet",
            "report": report,
            "summary": status,
            "snapshots": snapshots[:5],
            "error": None if report else {"code": "NO_RECO_YET", "message": "No recommendation report found"}
        }
    except ImportError as e:
        return {
            "schema": "RECO_REPORT_V1",
            "asof": datetime.now().isoformat(),
            "status": "error",
            "report": None,
            "error": {"code": "IMPORT_ERROR", "message": str(e)}
        }
    except Exception as e:
        return {
            "schema": "RECO_REPORT_V1",
            "asof": datetime.now().isoformat(),
            "status": "error",
            "report": None,
            "error": {"code": "UNKNOWN_ERROR", "message": str(e)}
        }


class RecoRegenerateRequest(BaseModel):
    confirm: bool = False


@app.post("/api/reco/regenerate", summary="추천 리포트 재생성")
def regenerate_reco(data: Optional[RecoRegenerateRequest] = None):
    """
    Reco Report Regenerate (D-P.48)
    
    전략 번들 기반으로 추천 리포트 재생성
    Confirm Guard: confirm=true 필수
    Fail-Closed: 번들 무결성 실패 시 BLOCKED
    """
    # Confirm Guard
    if not data or not data.confirm:
        return JSONResponse(
            status_code=400,
            content={
                "result": "BLOCKED",
                "message": "Confirm guard: set confirm=true to proceed",
                "report_id": None
            }
        )
    
    try:
        from app.generate_reco_report import generate_reco_report
        
        result = generate_reco_report()
        
        if result["success"]:
            report = result["report"]
            logger.info(f"Reco report generated: {report.get('report_id')} decision={report.get('decision')}")
            return {
                "result": "OK",
                "report_id": report.get("report_id"),
                "decision": report.get("decision"),
                "reason": report.get("reason"),
                "saved_to": result.get("saved_to"),
                "summary": report.get("summary")
            }
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "result": "FAILED",
                    "message": result.get("error", "Unknown error"),
                    "report_id": None
                }
            )
    except ImportError as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": f"Import error: {e}"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": str(e)
        })


# === Live Cycle API (D-P.50) ===

@app.get("/api/live/cycle/latest", summary="Live Cycle 최신 영수증 조회")
def get_live_cycle_latest():
    """
    Live Cycle Latest (D-P.50)
    
    최신 Live Cycle 영수증 조회
    Graceful: 영수증 없으면 NO_CYCLE_YET
    """
    try:
        from app.run_live_cycle import load_latest_cycle, list_cycle_snapshots
        
        receipt = load_latest_cycle()
        snapshots = list_cycle_snapshots()
        
        if receipt:
            return {
                "schema": "LIVE_CYCLE_RECEIPT_V1",
                "asof": datetime.now().isoformat(),
                "status": "ready",
                "row_count": 1,
                "rows": [receipt],
                "snapshots": snapshots[:10],
                "error": None
            }
        else:
            return {
                "schema": "LIVE_CYCLE_RECEIPT_V1",
                "asof": datetime.now().isoformat(),
                "status": "no_cycle_yet",
                "row_count": 0,
                "rows": [],
                "snapshots": snapshots[:10],
                "error": {"code": "NO_CYCLE_YET", "message": "No live cycle receipt found"}
            }
    except ImportError as e:
        return {
            "schema": "LIVE_CYCLE_RECEIPT_V1",
            "asof": datetime.now().isoformat(),
            "status": "error",
            "row_count": 0,
            "rows": [],
            "error": {"code": "IMPORT_ERROR", "message": str(e)}
        }
    except Exception as e:
        return {
            "schema": "LIVE_CYCLE_RECEIPT_V1",
            "asof": datetime.now().isoformat(),
            "status": "error",
            "row_count": 0,
            "rows": [],
            "error": {"code": "UNKNOWN_ERROR", "message": str(e)}
        }


@app.post("/api/live/cycle/run", summary="Live Cycle 실행")
def run_live_cycle_api(confirm: bool = False):
    """
    Live Cycle Run (D-P.50)
    
    Bundle→Reco→Summary→(Console)Send 단일 실행
    Confirm Guard: confirm=true 필수
    Fail-Closed: 실패해도 영수증 저장
    """
    # Confirm Guard
    if not confirm:
        return JSONResponse(
            status_code=400,
            content={
                "result": "BLOCKED",
                "message": "Confirm guard: set confirm=true to proceed",
                "cycle_id": None
            }
        )
    
    try:
        from app.run_live_cycle import run_live_cycle
        
        result = run_live_cycle()
        
        if result.get("success"):
            receipt = result.get("receipt", {})
            logger.info(f"Live cycle completed: {receipt.get('cycle_id')} result={receipt.get('result')}")
            return {
                "result": receipt.get("result", "OK"),
                "cycle_id": receipt.get("cycle_id"),
                "decision": receipt.get("decision"),
                "reason": receipt.get("reason"),
                "saved_to": result.get("saved_to"),
                "snapshot_ref": result.get("snapshot_ref"),
                "delivery_actual": receipt.get("push", {}).get("delivery_actual", "CONSOLE_SIMULATED")
            }
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "result": "FAILED",
                    "message": result.get("error", "Unknown error"),
                    "cycle_id": None
                }
            )
    except ImportError as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": f"Import error: {e}"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": str(e)
        })


# ============================================================================
# Daily Status Push API (D-P.55 + D-P.56)
# ============================================================================

@app.post("/api/push/daily_status/send")
async def push_daily_status_send(
    confirm: bool = Query(False),
    mode: str = Query("normal", description="normal=1일1회, test=idempotency우회")
):
    """
    Daily Status Push - 오늘 운영 상태 1줄 요약 발송
    Confirm Guard: confirm=true 필수
    Idempotency: mode=normal이면 1일 1회, mode=test면 우회
    """
    # Confirm Guard
    if not confirm:
        return JSONResponse(
            status_code=400,
            content={
                "result": "BLOCKED",
                "message": "Confirm guard: set confirm=true to proceed"
            }
        )
    
    # Validate mode
    if mode not in ("normal", "test"):
        return JSONResponse(
            status_code=400,
            content={
                "result": "BLOCKED",
                "message": f"Invalid mode: {mode}. Use 'normal' or 'test'"
            }
        )
    
    try:
        from app.generate_daily_status_push import generate_daily_status_push
        
        result = generate_daily_status_push(mode=mode)
        
        logger.info(f"Daily status push: {result.get('idempotency_key')} mode={mode} skipped={result.get('skipped')} delivery={result.get('delivery_actual')}")
        
        return result
        
    except Exception as e:
        logger.error(f"Daily status push failed: {e}")
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": str(e)
        })


@app.get("/api/push/daily_status/latest")
async def get_daily_status_latest():
    """Daily Status Push 최신 조회"""
    from pathlib import Path
    import json
    
    latest_path = Path("reports/ops/push/daily_status/latest/daily_status_latest.json")
    
    if not latest_path.exists():
        return {
            "result": "NOT_FOUND",
            "rows": [],
            "row_count": 0
        }
    
    try:
        data = json.loads(latest_path.read_text(encoding="utf-8"))
        return {
            "result": "OK",
            "rows": [data],
            "row_count": 1
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": str(e)
        })


# ============================================================================
# Incident Push API (D-P.57)
# ============================================================================

@app.post("/api/push/incident/send")
async def push_incident_send(
    confirm: bool = Query(False),
    mode: str = Query("normal", description="normal=하루1회, test=우회"),
    kind: str = Query(..., description="BACKEND_DOWN, OPS_BLOCKED, OPS_FAILED, LIVE_BLOCKED, LIVE_FAILED, PUSH_FAILED"),
    step: str = Query("Unknown"),
    reason: str = Query("Unknown")
):
    """
    Incident Push - 장애/차단 즉시 알림
    Confirm Guard: confirm=true 필수
    Idempotency: incident_<KIND>_YYYYMMDD (동일 타입 하루 1회)
    """
    if not confirm:
        return JSONResponse(
            status_code=400,
            content={
                "result": "BLOCKED",
                "message": "Confirm guard: set confirm=true to proceed"
            }
        )
    
    if mode not in ("normal", "test"):
        return JSONResponse(
            status_code=400,
            content={
                "result": "BLOCKED",
                "message": f"Invalid mode: {mode}"
            }
        )
    
    try:
        from app.generate_incident_push import generate_incident_push
        
        result = generate_incident_push(
            kind=kind,
            step=step,
            reason=reason,
            mode=mode
        )
        
        logger.info(f"Incident push: {kind} mode={mode} skipped={result.get('skipped')} delivery={result.get('delivery_actual')}")
        
        return result
        
    except Exception as e:
        logger.error(f"Incident push failed: {e}")
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": str(e)
        })


@app.get("/api/push/incident/latest")
async def get_incident_latest():
    """Incident Push 최신 조회"""
    from pathlib import Path
    import json
    
    latest_path = Path("reports/ops/push/incident/latest/incident_latest.json")
    
    if not latest_path.exists():
        return {
            "result": "NOT_FOUND",
            "rows": [],
            "row_count": 0
        }
    
    try:
        data = json.loads(latest_path.read_text(encoding="utf-8"))
        return {
            "result": "OK",
            "rows": [data],
            "row_count": 1
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": str(e)
        })



# ============================================================================
# Portfolio & Order Plan API (D-P.58)
# ============================================================================

class PortfolioHolding(BaseModel):
    ticker: str
    name: str = ""
    quantity: float
    avg_price: float = 0
    current_price: Optional[float] = None

class PortfolioUpsertRequest(BaseModel):
    cash: float
    holdings: List[PortfolioHolding]

@app.post("/api/portfolio/upsert")
async def upsert_portfolio_api(
    payload: PortfolioUpsertRequest,
    confirm: bool = Query(False)
):
    """
    Portfolio Upsert - 포트폴리오 저장
    Confirm Guard: confirm=true 필수
    """
    if not confirm:
        return JSONResponse(
            status_code=400,
            content={
                "result": "BLOCKED",
                "message": "Confirm guard: set confirm=true to proceed"
            }
        )
    
    try:
        from app.generate_portfolio_snapshot import upsert_portfolio
        
        # Convert Pydantic models to dicts
        holdings_dicts = [h.dict() for h in payload.holdings]
        
        result = upsert_portfolio(
            cash=payload.cash,
            holdings=holdings_dicts,
            updated_by="ui"
        )
        
        logger.info(f"Portfolio upsert: {result.get('portfolio_id')} items={result.get('holdings_count')}")
        return result
        
    except Exception as e:
        logger.error(f"Portfolio upsert failed: {e}")
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": str(e)
        })

@app.get("/api/portfolio/latest")
async def get_portfolio_latest_api():
    """Portfolio 최신 조회"""
    from app.generate_portfolio_snapshot import get_portfolio_latest
    
    data = get_portfolio_latest()
    if not data:
         return {
            "result": "NOT_FOUND",
            "rows": [],
            "row_count": 0
        }
    
    return {
        "result": "OK",
        "rows": [data],
        "row_count": 1
    }

@app.post("/api/order_plan/regenerate")
async def regenerate_order_plan_api(confirm: bool = Query(False)):
    """
    Order Plan Regenerate - 주문안 재생성
    Confirm Guard: confirm=true 필수
    """
    if not confirm:
        return JSONResponse(
            status_code=400,
            content={
                "result": "BLOCKED",
                "message": "Confirm guard: set confirm=true to proceed"
            }
        )
        
    try:
        from app.generate_order_plan import generate_order_plan
        
        result = generate_order_plan()
        
        logger.info(f"Order plan regenerate: decision={result.get('decision')} plan_id={result.get('plan_id')}")
        return result
        
    except Exception as e:
        logger.error(f"Order plan regenerate failed: {e}")
        raise HTTPException(status_code=500, detail={
            "result": "FAILED",
            "reason": str(e)
        })

@app.get("/api/order_plan/latest")
async def get_order_plan_latest_api():
    """Order Plan 최신 조회"""
    from app.generate_order_plan import get_order_plan_latest
    
    data = get_order_plan_latest()
    if not data:
         return {
            "result": "NOT_FOUND",
            "rows": [],
            "row_count": 0
        }
    
    return {
        "result": "OK",
        "rows": [data],
        "row_count": 1
    }

# ============================================================================
# Watchlist API (D-P.61)
# ============================================================================

class WatchlistItem(BaseModel):
    ticker: str
    name: str = ""
    enabled: bool = True

class WatchlistUpsertRequest(BaseModel):
    items: List[WatchlistItem]

@app.post("/api/watchlist/upsert")
async def upsert_watchlist_api(
    payload: WatchlistUpsertRequest,
    confirm: bool = Query(False)
):
    """Watchlist 저장 (PC UI)"""
    if not confirm:
        return JSONResponse(status_code=400, content={"result": "BLOCKED", "message": "Confirm required"})
        
    try:
        from app.generate_watchlist import upsert_watchlist
        items_dicts = [i.dict() for i in payload.items]
        return upsert_watchlist(items_dicts)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})

@app.get("/api/watchlist/latest")
async def get_watchlist_latest_api():
    """Watchlist 최신 조회"""
    from app.generate_watchlist import load_watchlist
    data = load_watchlist()
    if not data:
        return {"result": "NOT_FOUND"}
    return {"result": "OK", "data": data}


# ============================================================================
# Spike Push API (D-P.61)
# ============================================================================

@app.post("/api/push/spike/run")
async def run_spike_push_api(confirm: bool = Query(False)):
    """Spike Push 실행 (OCI Cron)"""
    if not confirm:
        return JSONResponse(status_code=400, content={"result": "BLOCKED", "message": "Confirm required"})
        
    try:
        from app.run_spike_push import run_spike_push
        return run_spike_push()
    except Exception as e:
        logger.error(f"Spike run failed: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})

@app.get("/api/push/spike/latest")
async def get_spike_latest_api():
    """Spike Push 최신 조회"""
    from pathlib import Path
    import json
    path = Path("reports/ops/push/spike_watch/latest/spike_watch_latest.json")
    if not path.exists():
        return {"result": "NOT_FOUND"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"result": "ERROR", "reason": str(e)}



# ============================================================================
# Holding Watch API (D-P.66)
# ============================================================================

@app.post("/api/push/holding/run")
async def run_holding_watch_api(confirm: bool = Query(False)):
    """Holding Watch 실행 (OCI Cron / Monitor)"""
    if not confirm:
        return JSONResponse(status_code=400, content={"result": "BLOCKED", "message": "Confirm required"})
        
    try:
        from app.run_holding_watch import run_holding_watch
        return run_holding_watch()
    except Exception as e:
        logger.error(f"Holding run failed: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})

@app.get("/api/push/holding/latest")
async def get_holding_latest_api():
    """Holding Watch 최신 조회"""
    from pathlib import Path
    import json
    path = Path("reports/ops/push/holding_watch/latest/holding_watch_latest.json")
    if not path.exists():
        return {"result": "NOT_FOUND"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"result": "ERROR", "reason": str(e)}


# ============================================================================
# Unified Settings API (D-P.66)
# ============================================================================

@app.get("/api/settings", summary="통합 설정 조회")
def get_unified_settings():
    """통합 설정(Spike + Holding) 최신 상태 반환"""
    from app.generate_settings import load_settings
    data = load_settings()
    return {"result": "OK", "data": data}

@app.post("/api/settings/upsert", summary="통합 설정 저장")
async def upsert_unified_settings(confirm: bool = Query(False), payload: dict = Body(...)):
    """
    통합 설정 저장 (Spike/Holding 섹션 병합)
    """
    if not confirm:
        return JSONResponse(status_code=400, content={"result": "BLOCKED", "message": "Confirm required"})

    from app.generate_settings import upsert_settings
    res = upsert_settings(payload, confirm=confirm)
    if res.get("result") != "OK":
        return JSONResponse(status_code=500, content=res)
    return res


# ============================================================================
# Spike Settings API (D-P.62)
# ============================================================================

@app.post("/api/spike_settings/upsert")
async def upsert_spike_settings_api(
    payload: dict,
    confirm: bool = Query(False)
):
    """Spike 감시 설정 저장"""
    if not confirm:
        return JSONResponse(status_code=400, content={"result": "BLOCKED", "message": "Confirm required"})
        
    try:
        from app.generate_spike_settings import upsert_spike_settings
        return upsert_spike_settings(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})

@app.get("/api/spike_settings/latest")
async def get_spike_settings_latest_api():
    """Spike 감시 설정 조회"""
    from app.generate_spike_settings import load_spike_settings
    data = load_spike_settings()
    if not data:
        return {"result": "NOT_FOUND"}
    return {"result": "OK", "data": data}


# ============================================================================
# Watchlist Candidates API (D-P.63)
# ============================================================================

@app.post("/api/watchlist_candidates/regenerate")
async def regenerate_candidates_api(confirm: bool = Query(False)):
    """후보 리스트 생성 (Backtest/Reco 기반)"""
    if not confirm:
        return JSONResponse(status_code=400, content={"result": "BLOCKED", "message": "Confirm required"})
        
    try:
        from app.generate_watchlist_candidates import generate_candidates
        return generate_candidates(confirm=True)
    except Exception as e:
        return JSONResponse(status_code=500, content={"result": "FAILED", "reason": str(e)})

@app.get("/api/watchlist_candidates/latest")
async def get_candidates_latest_api():
    """후보 리스트 조회"""
    from app.generate_watchlist_candidates import get_latest_candidates
    data = get_latest_candidates()
    if not data:
        return {"result": "NOT_FOUND"}
    return {"result": "OK", "data": data}


# ============================================================================
# Git Transport API (D-P.6X)
# ============================================================================

@app.post("/api/transport/sync", summary="State 파일 OCI 동기화")
async def sync_state_to_remote_api(confirm: bool = Query(True)):
    """
    Git Transport: State 파일만 Commit & Push
    - Code 변경이 있으면 BLOCKED
    """
    try:
        from app.run_git_transport import sync_state_to_remote
        return sync_state_to_remote(confirm=confirm)
    except Exception as e:
         return JSONResponse(status_code=500, content={"result": "FAILED", "reason": str(e)})



# ============================================================================
# Manual Execution API (P144: UI-First Daily Ops)
# ============================================================================

class ExecutionPrepRequest(BaseModel):
    confirm_token: str

@app.post("/api/execution_prep/prepare")
async def prepare_execution_api(
    payload: ExecutionPrepRequest,
    confirm: bool = Query(False)
):
    """
    Execution Prep - 실행 준비 (Human Token)
    Confirm Guard: confirm=true 필수
    """
    if not confirm:
        return JSONResponse(status_code=400, content={"result": "BLOCKED", "message": "Confirm required"})
        
    try:
        from app.generate_execution_prep import generate_prep
        generate_prep(payload.confirm_token)
        
        # Read result to return
        from app.generate_execution_prep import PREP_LATEST
        if PREP_LATEST.exists():
             return json.loads(PREP_LATEST.read_text(encoding="utf-8"))
        return {"result": "OK", "message": "Prep generated (file checks recommended)"}
        
    except Exception as e:
        logger.error(f"Execution Prep failed: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})


class RecordSubmitRequest(BaseModel):
    confirm_token: str
    items: List[Dict[str, Any]]
    filled_at: Optional[str] = None
    method: Optional[str] = "UI_MANUAL"
    evidence_note: Optional[str] = ""

@app.post("/api/manual_execution_record/submit")
async def submit_execution_record_api(
    payload: Dict[str, Any] = Body(...),
    confirm: bool = Query(False)
):
    """
    Submit Execution Record - 실행 기록 제출 (Human Token)
    Accepts arbitrary dict to support flexible schema, but requires confirm_token.
    """
    if not confirm:
        return JSONResponse(status_code=400, content={"result": "BLOCKED", "message": "Confirm required"})
        
    token = payload.get("confirm_token")
    if not token:
        return JSONResponse(status_code=400, content={"result": "BLOCKED", "message": "confirm_token is missing in payload"})

    if not token:
        return JSONResponse(status_code=400, content={"result": "BLOCKED", "message": "confirm_token is missing in payload"})

    try:
        from app.generate_manual_execution_record import generate_record
        print(f"DEBUG: Submitting Record Payload Keys: {list(payload.keys())}")
        if "items" in payload:
             print(f"DEBUG: Items Type: {type(payload['items'])}")
             if isinstance(payload['items'], list) and len(payload['items']) > 0:
                 print(f"DEBUG: First Item Type: {type(payload['items'][0])}")
        
        generate_record(token, payload)
        
        # Read result
        from app.generate_manual_execution_record import RECORD_LATEST
        if RECORD_LATEST.exists():
             return json.loads(RECORD_LATEST.read_text(encoding="utf-8"))
        return {"result": "OK", "message": "Record submitted"}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"DEBUG: EXCEPTION IN BACKEND: {e}")
        logger.error(f"Record Submit failed: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})


@app.post("/api/manual_execution_ticket/regenerate")
async def regenerate_execution_ticket_api(confirm: bool = Query(False)):
    """
    Regenerate Manual Execution Ticket
    """
    if not confirm:
        return JSONResponse(status_code=400, content={"result": "BLOCKED", "message": "Confirm required"})

    try:
        from app.generate_manual_execution_ticket import generate_ticket
        generate_ticket()
        
        # Read result
        path = BASE_DIR / "reports" / "live" / "manual_execution_ticket" / "latest" / "manual_execution_ticket_latest.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"result": "OK", "message": "Ticket generated"}
        
    except ImportError:
         # Fallback if function not importable (maybe run as script)
         cmd = [sys.executable, "-m", "app.generate_manual_execution_ticket"]
         res = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE_DIR)
         if res.returncode != 0:
             return {"result": "FAIL", "error": res.stderr}
         return {"result": "OK", "stdout": res.stdout}
         
    except Exception as e:
        logger.error(f"Ticket Gen failed: {e}")
        raise HTTPException(status_code=500, detail={"result": "FAILED", "reason": str(e)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)









