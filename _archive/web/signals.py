# web/signals.py
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from signals.service import (
    compute_daily_signals,
    send_signals_to_telegram,
)
import csv, io

router = APIRouter()
tpl = Jinja2Templates(directory="web/templates")

def _sort_rows(rows, key):
    if key == "score_desc": return sorted(rows, key=lambda x: x["score"], reverse=True)
    if key == "score_asc":  return sorted(rows, key=lambda x: x["score"])
    if key == "r1_desc":    return sorted(rows, key=lambda x: (x.get("r1") or 0), reverse=True)
    if key == "r1_asc":     return sorted(rows, key=lambda x: (x.get("r1") or 0))
    if key == "name_asc":   return sorted(rows, key=lambda x: x["name"])
    if key == "code_asc":   return sorted(rows, key=lambda x: x["code"])
    return rows

def _summary(rows):
    s = {"BUY":0, "SELL":0, "HOLD":0}
    for r in rows: s[r["signal"]] = s.get(r["signal"],0) + 1
    return s

@router.get("/signals", response_class=HTMLResponse)
def signals_page(request: Request,
                 mode: str = Query(None),      # 'score_abs' | 'rank'
                 wl: int = Query(0),           # watchlist 사용 여부
                 sort: str = Query("score_desc")):
    overrides = {}
    if mode in ("score_abs","rank"): overrides["mode"] = mode
    overrides["use_watchlist"] = bool(wl)

    p = compute_daily_signals(overrides=overrides)
    rows = _sort_rows(p.get("signals", []), sort)
    summ = _summary(rows)

    return tpl.TemplateResponse("signals.html", {
        "request": request,
        "date": p.get("date"),
        "signals": rows,
        "mode": p.get("mode"),
        "windows": p.get("windows", []),
        "weights": p.get("weights", []),
        "thr": p.get("score_threshold"),
        "top_k": p.get("top_k"),
        "bottom_k": p.get("bottom_k"),
        "use_watchlist": bool(wl),
        "insufficient": p.get("filtered_counts",{}).get("insufficient_price",0),
        "filters": p.get("filters",{}),
        "filtered_counts": p.get("filtered_counts",{}),
        "sort": sort,
        "summary": summ,
    })

@router.post("/api/signals/recalc")
def signals_recalc(mode: str = Query(None), wl: int = Query(0), sort: str = Query("score_desc")):
    overrides = {}
    if mode in ("score_abs","rank"): overrides["mode"] = mode
    overrides["use_watchlist"] = bool(wl)
    p = compute_daily_signals(overrides=overrides)
    return JSONResponse({"ok": True, "count": len(p.get("signals", [])), "date": p.get("date")})

@router.post("/api/signals/notify")
def signals_notify(mode: str = Query(None), wl: int = Query(0)):
    overrides = {}
    if mode in ("score_abs","rank"): overrides["mode"] = mode
    overrides["use_watchlist"] = bool(wl)
    p = compute_daily_signals(overrides=overrides)
    ok = send_signals_to_telegram(p, top=5)
    return JSONResponse({"ok": ok})