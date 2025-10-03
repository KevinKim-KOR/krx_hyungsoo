# web/main.py
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func

# 불필요하면 주석/삭제 가능
# from db import SessionLocal, PriceDaily, Security
# from reporting_eod import generate_and_send_report_eod, _load_report_cfg_defaults

from web.signals import router as signals_router
from web.watchlist import router as watchlist_router
from web.bt_inbox_service import router as bt_inbox_router

# --- app/템플릿 생성이 먼저 ---
app = FastAPI(title="KRX Alertor Web")

# 루트 기준 고정이면 "web/templates"로 둬도 됨
# templates = Jinja2Templates(directory="web/templates")
# 경로 안전하게 가려면:
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# --- 라우터 등록은 app 생성 이후 ---
app.include_router(signals_router)
app.include_router(watchlist_router)
app.include_router(bt_inbox_router)
# wire bt inbox router (route order fixed)

def latest_two_dates(session):
    d0 = session.execute(select(func.max(PriceDaily.date))).scalar()
    if not d0:
        return None, None
    d1 = session.execute(select(func.max(PriceDaily.date)).where(PriceDaily.date < d0)).scalar()
    return (str(d0), str(d1) if d1 else None)

def returns_for_dates(session, d0, d1):
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

def fmt_pct(x): return f"{x*100:+.2f}%"
def arrow(x): return "▲" if x > 0 else ("▼" if x < 0 else "→")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    top_n, min_abs = _load_report_cfg_defaults()  # 보고서 설정 재사용
    with SessionLocal() as session:
        d0, d1 = latest_two_dates(session)
        data = returns_for_dates(session, d0, d1) if d0 and d1 else []
    mkt = next((x for x in data if x["code"] in ("069500", "069500.KS")), None)
    pos = [x for x in data if x["ret"] >=  min_abs]
    neg = [x for x in data if x["ret"] <= -min_abs]
    winners = sorted(pos, key=lambda x: x["ret"], reverse=True)[:top_n]
    losers  = sorted(neg, key=lambda x: x["ret"])[:top_n]
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

@app.post("/api/report/eod")
def api_report_eod():
    rc = generate_and_send_report_eod("auto", expect_today=False)
    msg = "sent" if rc == 0 else ("stale" if rc == 2 else "failed")
    return JSONResponse({"ok": rc == 0, "rc": rc, "message": msg})