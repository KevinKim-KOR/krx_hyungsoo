# web/watchlist.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from utils.config import read_watchlist_codes, write_watchlist_codes, get_watchlist_path

router = APIRouter()
tpl = Jinja2Templates(directory="web/templates")

@router.get("/watchlist", response_class=HTMLResponse)
def page_watchlist(request: Request):
    codes = read_watchlist_codes()
    text = "\n".join(codes)
    return tpl.TemplateResponse("watchlist.html", {
        "request": request,
        "path": get_watchlist_path(),
        "count": len(codes),
        "text": text,
    })

@router.post("/api/watchlist/save")
def api_watchlist_save(text: str = Form(...)):
    # 한 줄당 1코드
    codes = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    ok = write_watchlist_codes(codes)
    return JSONResponse({"ok": ok, "count": len(codes)})
