# web/main.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from db import SessionLocal, PriceDaily, Security

app = FastAPI(title="KRX Alertor Web")
templates = Jinja2Templates(directory="web/templates")

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
    with SessionLocal() as session:
        d0, d1 = latest_two_dates(session)
        data = returns_for_dates(session, d0, d1) if d0 and d1 else []
    mkt = next((x for x in data if x["code"] in ("069500", "069500.KS")), None)
    pos = [x for x in data if x["ret"] >= 0.003]
    neg = [x for x in data if x["ret"] <= -0.003]
    winners = sorted(pos, key=lambda x: x["ret"], reverse=True)[:5]
    losers  = sorted(neg, key=lambda x: x["ret"])[:5]
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "d0": d0, "d1": d1, "mkt": mkt,
         "fmt_pct": fmt_pct, "arrow": arrow,
         "winners": winners, "losers": losers, "count": len(data)}
    )
