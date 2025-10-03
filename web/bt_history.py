# web/bt_history.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os, json
import pandas as pd
from datetime import timedelta

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

PROC_ROOT = os.path.join("reports", "backtests", "processed")
INDEX_JSON = os.path.join("reports", "backtests", "index.json")

def _load_index():
    if not os.path.exists(INDEX_JSON):
        return {"packages": []}
    with open(INDEX_JSON, "r", encoding="utf-8") as f:
        obj = json.load(f) or {}
    return obj if isinstance(obj, dict) else {"packages": []}

def _last_two_packages():
    idx = _load_index()
    pkgs = idx.get("packages", [])
    # 가장 나중에 append된게 최신
    if len(pkgs) < 2:
        return None, None
    return pkgs[-1], pkgs[-2]

def _load_equity_csv(pkg_entry):
    fdir = pkg_entry["final_dir"]
    fpath = os.path.join(fdir, pkg_entry["manifest"]["entrypoints"]["equity"])
    df = pd.read_csv(fpath, parse_dates=["date"]).set_index("date").sort_index()
    # nav, ret 컬럼 가정 (backtest_cli.py 출력과 동일)
    return df[["nav","ret"]].copy()

def _mdd(nav: pd.Series) -> float:
    roll_max = nav.cummax()
    dd = nav/roll_max - 1.0
    return dd.min() if len(dd) else 0.0

def _last_30d_return(nav: pd.Series) -> float:
    if len(nav) < 2:
        return 0.0
    end = nav.index[-1]
    start = end - timedelta(days=30)
    sub = nav[nav.index >= start]
    if len(sub) < 2:
        return 0.0
    return float(sub.iloc[-1]/sub.iloc[0] - 1.0)

def _align_common(a: pd.DataFrame, b: pd.DataFrame):
    ix = a.index.intersection(b.index)
    a2 = a.loc[ix].copy()
    b2 = b.loc[ix].copy()
    return a2, b2

@router.get("/bt/history", response_class=HTMLResponse)
def bt_history(request: Request):
    cur, prev = _last_two_packages()
    if not cur or not prev:
        return templates.TemplateResponse(
            "bt_history.html",
            {"request": request, "has_data": False, "msg": "비교할 패키지가 2개 이상 필요합니다."}
        )

    df_cur = _load_equity_csv(cur)
    df_prev = _load_equity_csv(prev)
    a, b = _align_common(df_cur, df_prev)

    # 요약지표
    cur_nav_end = float(a["nav"].iloc[-1]) if len(a) else None
    prev_nav_end= float(b["nav"].iloc[-1]) if len(b) else None
    cur_mdd = float(_mdd(a["nav"])) if len(a) else None
    prev_mdd= float(_mdd(b["nav"])) if len(b) else None
    cur_30d = float(_last_30d_return(a["nav"])) if len(a) else None
    prev_30d= float(_last_30d_return(b["nav"])) if len(b) else None

    # 최근 50개만 테이블로(너무 기니)
    a_tail = a.tail(50).reset_index()
    b_tail = b.tail(50).reset_index()

    ctx = {
        "request": request,
        "has_data": True,
        "cur_pkg": cur,
        "prev_pkg": prev,
        "cur_end": cur_nav_end,
        "prev_end": prev_nav_end,
        "cur_mdd": cur_mdd,
        "prev_mdd": prev_mdd,
        "cur_30d": cur_30d,
        "prev_30d": prev_30d,
        "rows": zip(
            a_tail["date"].dt.strftime("%Y-%m-%d"),
            a_tail["nav"].round(4), b_tail["nav"].round(4),
            a_tail["ret"].round(5), b_tail["ret"].round(5),
        )
    }
    return templates.TemplateResponse("bt_history.html", ctx)
