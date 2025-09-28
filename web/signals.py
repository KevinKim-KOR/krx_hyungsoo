# web/signals.py
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from signals.service import compute_daily_signals
import csv, io

router = APIRouter()
tpl = Jinja2Templates(directory="web/templates")

def _sort_rows(rows, key):
    if key == "score_desc": return sorted(rows, key=lambda x: x["score"], reverse=True)
    if key == "score_asc":  return sorted(rows, key=lambda x: x["score"])
    if key == "r1_desc":    return sorted(rows, key=lambda x: (x.get("r1") or 0), reverse=True)
    if key == "r1_asc":     return sorted(rows, key=lambda x: (x.get("r1") or 0))
    if key == "code_asc":   return sorted(rows, key=lambda x: x["code"])
    if key == "name_asc":   return sorted(rows, key=lambda x: x["name"])
    return rows

def _summary(rows):
    s = {"BUY":0,"SELL":0,"HOLD":0}
    for r in rows: s[r["signal"]] = s.get(r["signal"],0)+1
    return s

@router.get("/signals", response_class=HTMLResponse)
def signals_page(request: Request,
                 mode: str = Query(None),      # 'score_abs' | 'rank'
                 wl: int = Query(0),           # 1이면 watchlist 사용
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
        "top_k": p.get("top_k"), "bottom_k": p.get("bottom_k"),
        "use_watchlist": bool(wl),
        "insufficient": p.get("insufficient_count", 0),
        "sort": sort, "summary": summ,
    })

@router.post("/api/signals/recalc")
def signals_recalc(mode: str = Query(None), wl: int = Query(0)):
    overrides = {}
    if mode in ("score_abs","rank"): overrides["mode"] = mode
    overrides["use_watchlist"] = bool(wl)
    p = compute_daily_signals(overrides=overrides)
    return JSONResponse({"ok": True, "count": len(p.get("signals", [])), "date": p.get("date")})

@router.get("/api/signals.csv")
def signals_csv(mode: str = Query(None), wl: int = Query(0), sort: str = Query("score_desc")):
    overrides = {}
    if mode in ("score_abs","rank"): overrides["mode"] = mode
    overrides["use_watchlist"] = bool(wl)
    p = compute_daily_signals(overrides=overrides)
    rows = _sort_rows(p.get("signals", []), sort)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date","code","name","r1","r5","r20","score","signal"])
    for r in rows:
        w.writerow([p.get("date"), r["code"], r["name"], r.get("r1"), r.get("r5"), r.get("r20"), r["score"], r["signal"]])
    data = buf.getvalue().encode("utf-8-sig")
    headers = {"Content-Disposition": 'attachment; filename="signals.csv"'}
    return Response(content=data, media_type="text/csv; charset=utf-8", headers=headers)
