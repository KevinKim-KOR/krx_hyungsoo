"""core 라우터 — /, /api/status, /api/signals, /api/history, /api/raw, /api/validation."""

import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse

from backend.utils import (
    KST,
    BASE_DIR,
    LOG_DIR,
    STATE_DIR,
    REPORTS_DIR,
    PAPER_DIR,
    logger,
    get_today_str,
    safe_read_text,
    safe_read_text_advanced,
    safe_read_json,
    safe_read_yaml,
)

router = APIRouter()


@router.get("/")
def read_root():
    """Root Redirect to Operator Dashboard (P146)"""
    return RedirectResponse(url="/operator", status_code=307)


@router.get("/api/status", summary="시스템 상태 조회 (Enhanced)")
def get_status():
    """일별 실행 로그를 파싱하여 현재 시스템 상태 및 관측 신뢰도를 반환합니다."""
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
            "log_file": str(log_file),
        }

        if not log_file.exists():
            status["badge"] = "UNKNOWN"
            return status

        read_res = safe_read_text_advanced(log_file)
        content = read_res["content"]
        status["read_quality"] = read_res["quality"]
        status["read_encoding"] = read_res["encoding"]

        ok_count = content.count("[OK]")
        skip_count = content.count("[SKIP]")
        err_count = (
            content.count("[ERROR]")
            + content.count("FAILED")
            + content.count("Traceback")
        )

        status["evidence"]["ok_count"] = ok_count
        status["evidence"]["skip_count"] = skip_count
        status["evidence"]["error_count"] = err_count

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
            content={"error": "상태 조회 실패", "detail": str(e)},
        )


@router.get("/api/signals", summary="당일 신호 조회")
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


@router.get("/api/history", summary="과거 이력 조회 (Equity Curve)")
def get_history():
    """일별 리포트 파일들을 취합하여 자산 추이 데이터를 반환합니다."""
    logger.info("이력 조회 요청 (GET /api/history)")
    try:
        if not PAPER_DIR.exists():
            return []

        files = sorted(PAPER_DIR.glob("paper_*.json"))
        history = []

        for f in files:
            try:
                data = json.loads(safe_read_text(f))
                history.append(
                    {
                        "date": data.get("execution_date", "").split("T")[0],
                        "equity": data.get("after", {}).get("equity", 0),
                        "cash": data.get("after", {}).get("cash", 0),
                        "trades_count": data.get("trades_count", 0),
                    }
                )
            except Exception as inner_e:
                logger.warning(
                    f"이력 파일 파싱 실패 (스킵함): {f.name} - {str(inner_e)}"
                )
                continue

        return history
    except Exception as e:
        logger.error("이력 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="내부 서버 오류")


@router.get("/api/raw", summary="원본 파일 조회")
def get_raw(
    filename: str = Query(..., description="프로젝트 루트 기준 파일 경로"),
):
    """디버깅용 원본 파일 뷰어"""
    logger.info(f"원본 조회 요청: {filename}")
    if ".." in filename or filename.startswith(("/", "\\")):
        raise HTTPException(status_code=403, detail="잘못된 파일 경로입니다.")

    path = BASE_DIR / filename
    allowed_parents = [LOG_DIR, STATE_DIR, REPORTS_DIR]
    try:
        resolved_path = path.resolve()
        if not any(
            str(resolved_path).startswith(str(p.resolve())) for p in allowed_parents
        ):
            raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
    except Exception:
        pass

    if not path.exists():
        return {"filename": filename, "content": ""}

    try:
        content = safe_read_text(path)
        return {"filename": filename, "content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    except Exception as e:
        logger.error(f"원본 읽기 실패: {filename}", exc_info=True)
        raise HTTPException(status_code=500, detail="파일 읽기 실패")


@router.get("/api/validation", summary="검증 리포트 조회")
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
