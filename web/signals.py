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
    payload = compute_daily_signals()
    return tpl.TemplateResponse("signals.html", {
        "request": request,
        "date": payload.get("date"),
        "signals": payload.get("signals", []),
        "min_abs": payload.get("min_abs", 0.003)
    })

@router.post("/api/signals/recalc")
def signals_recalc():
    payload = compute_daily_signals()
    return JSONResponse({"ok": True, "count": len(payload.get("signals", [])), "date": payload.get("date")})
