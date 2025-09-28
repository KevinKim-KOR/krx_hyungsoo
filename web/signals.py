# web/signals.py
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from signals.service import compute_daily_signals

router = APIRouter()
tpl = Jinja2Templates(directory="web/templates")

@router.get("/signals", response_class=HTMLResponse)
def signals_page(request: Request):
    p = compute_daily_signals()
    return tpl.TemplateResponse("signals.html", {
        "request": request,
        "date": p.get("date"),
        "signals": p.get("signals", []),
        "mode": p.get("mode"),
        "windows": p.get("windows", []),
        "weights": p.get("weights", []),
        "thr": p.get("score_threshold"),
        "top_k": p.get("top_k"),
        "bottom_k": p.get("bottom_k"),
        "use_watchlist": p.get("use_watchlist"),
        "insufficient": p.get("insufficient_count", 0),
    })

@router.post("/api/signals/recalc")
def signals_recalc():
    p = compute_daily_signals()
    return JSONResponse({"ok": True, "count": len(p.get("signals", [])), "date": p.get("date")})
