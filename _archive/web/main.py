# web/main.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Tuple, List

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# -----------------------------------------------------------------------------
# 0) FastAPI 앱 생성 (가장 먼저)
# -----------------------------------------------------------------------------
app = FastAPI(title="KRX Alertor Web")
print("[WEB] app started")

# -----------------------------------------------------------------------------
# 1) 경로/템플릿
# -----------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]   # repo root (web/의 부모)
BASE_DIR = Path(__file__).resolve().parent   # .../web
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# -----------------------------------------------------------------------------
# 2) /reports 정적 마운트 (존재할 때만)
# -----------------------------------------------------------------------------
try:
    REPORTS_DIR = (ROOT / "reports").resolve()
    if REPORTS_DIR.exists():
        app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR)), name="reports")
        print(f"[WEB] mount /reports -> {REPORTS_DIR}")
    else:
        print(f"[WEB] skip /reports (not found): {REPORTS_DIR}")
except Exception as e:
    print(f"[WEB] WARN: failed to mount /reports: {e}")

# -----------------------------------------------------------------------------
# 3) 라우터 등록 (각 모듈이 없어도 앱은 뜨게 try/except)
# -----------------------------------------------------------------------------
def _safe_include(path: str, attr: str) -> None:
    try:
        mod = __import__(path, fromlist=[attr])
        router = getattr(mod, attr, None)
        if router is not None:
            app.include_router(router)
            print(f"[WEB] router mounted: {path}.{attr}")
        else:
            print(f"[WEB] WARN: {path}.{attr} not found")
    except Exception as e:
        print(f"[WEB] WARN: fail to include {path}.{attr}: {e}")

_safe_include("web.signals", "router")
_safe_include("web.watchlist", "router")
_safe_include("web.bt_inbox_service", "router")
_safe_include("web.bt_history", "router")

# -----------------------------------------------------------------------------
# 4) 홈(/) — 의존 모듈이 없을 때도 안전하게 동작하도록 가드
# -----------------------------------------------------------------------------
# 기존 로직은 DB/리포트 유틸에 강하게 의존했음.
# import 단계에서 실패하지 않도록, 라우트 내부에서 동적으로 import + 예외 캡처.

def _load_report_cfg_defaults_safe() -> Tuple[int, float]:
    """top_n, min_abs"""
    try:
        from reporting_eod import _load_report_cfg_defaults  # type: ignore
        return _load_report_cfg_defaults()
    except Exception:
        # 합리적 기본값
        return (5, 0.03)

def _latest_two_dates_safe(session) -> Tuple[Optional[str], Optional[str]]:
    try:
        from sqlalchemy import select, func  # type: ignore
        from db import PriceDaily  # type: ignore
        d0 = session.execute(select(func.max(PriceDaily.date))).scalar()
        if not d0:
            return None, None
        d1 = session.execute(select(func.max(PriceDaily.date)).where(PriceDaily.date < d0)).scalar()
        return (str(d0), str(d1) if d1 else None)
    except Exception:
        return (None, None)

def _returns_for_dates_safe(session, d0: str, d1: str) -> List[dict]:
    try:
        from sqlalchemy import select  # type: ignore
        from db import PriceDaily, Security  # type: ignore
        rows0 = session.execute(select(PriceDaily.code, PriceDaily.close).where(PriceDaily.date == d0)).all()
        rows1 = session.execute(select(PriceDaily.code, PriceDaily.close).where(PriceDaily.date == d1)).all()
        px0 = {c: (float(x) if x is not None else None) for c, x in rows0}
        px1 = {c: (float(x) if x is not None else None) for c, x in rows1}
        codes = sorted(set(px0) & set(px1))
        try:
            names = dict(session.execute(select(Security.code, Security.name)).all())
        except Exception:
            names = {}
        data = []
        for code in codes:
            p0, p1 = px0.get(code), px1.get(code)
            if p0 is None or p1 is None or p1 == 0:
                continue
            ret = (p0 - p1) / p1
            data.append({"code": code, "name": names.get(code, code), "ret": ret})
        return data
    except Exception:
        return []

def fmt_pct(x: float) -> str:
    return f"{x*100:+.2f}%"

def arrow(x: float) -> str:
    return "▲" if x > 0 else ("▼" if x < 0 else "→")

def _market_candidate_codes() -> List[str]:
    # utils.datasources.benchmark_candidates 가 있으면 사용
    try:
        from utils.datasources import benchmark_candidates  # type: ignore
        cands = benchmark_candidates()
        # 문자열 리스트 보장
        return [str(c) for c in (cands or [])]
    except Exception:
        # 폴백: TIGER 200 등 대표코드 후보
        return ["069500", "069500.KS"]

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    # DB 세션 확보(없으면 None 처리)
    SessionLocal = None
    try:
        from db import SessionLocal as _SL  # type: ignore
        SessionLocal = _SL
    except Exception:
        pass

    top_n, min_abs = _load_report_cfg_defaults_safe()

    d0 = d1 = None
    data: List[dict] = []
    if SessionLocal:
        try:
            with SessionLocal() as session:  # type: ignore
                d0, d1 = _latest_two_dates_safe(session)
                data = _returns_for_dates_safe(session, d0, d1) if d0 and d1 else []
        except Exception as e:
            print(f"[WEB] WARN: DB access failed: {e}")

    # 마켓 후보
    cands = _market_candidate_codes()
    mkt = next((x for x in (data or []) if str(x.get("code")) in cands), None)

    # 상하위 N
    pos = [x for x in data if x.get("ret", 0) >= min_abs]
    neg = [x for x in data if x.get("ret", 0) <= -min_abs]
    winners = sorted(pos, key=lambda x: x["ret"], reverse=True)[:top_n]
    losers  = sorted(neg, key=lambda x: x["ret"])[:top_n]

    # 템플릿이 없거나 에러시에도 안전하게 HTMLResponse 반환
    try:
        return templates.TemplateResponse(
            "home.html",
            {
                "request": request,
                "d0": d0, "d1": d1, "mkt": mkt,
                "fmt_pct": fmt_pct, "arrow": arrow,
                "winners": winners, "losers": losers,
                "count": len(data), "min_abs": min_abs, "top_n": top_n
            }
        )
    except Exception:
        # 최소 동작 페이지
        html = f"""
        <html><body style="font-family:system-ui">
        <h3>KRX Alertor Web</h3>
        <p>서비스는 기동되었습니다.</p>
        <ul>
          <li><a href="/bt/history">백테스트 비교</a></li>
          <li><a href="/reports/index.html">리포트 인덱스</a></li>
        </ul>
        </body></html>
        """
        return HTMLResponse(html)

# -----------------------------------------------------------------------------
# 5) 보고서 트리거 API (선택적 의존성; 실패해도 앱은 살려 둠)
# -----------------------------------------------------------------------------
@app.post("/api/report/eod")
def api_report_eod():
    try:
        from reporting_eod import generate_and_send_report_eod  # type: ignore
        rc = generate_and_send_report_eod("auto", expect_today=False)
    except Exception as e:
        return JSONResponse({"ok": False, "rc": 1, "message": f"failed: {e}"})
    msg = "sent" if rc == 0 else ("stale" if rc == 2 else "failed")
    return JSONResponse({"ok": rc == 0, "rc": rc, "message": msg})

# -----------------------------------------------------------------------------
# 6) 헬스엔드포인트
# -----------------------------------------------------------------------------
@app.get("/health", response_class=PlainTextResponse)
def health():
    return "ok"
