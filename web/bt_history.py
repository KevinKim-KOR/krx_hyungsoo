# web/bt_history.py
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os, json, io
import pandas as pd
from datetime import timedelta

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

PROC_ROOT = os.path.join("reports", "backtests", "processed")
INDEX_JSON = os.path.join("reports", "backtests", "index.json")

# ---------------- utils ----------------

def _load_json_tolerant(path: str):
    """Allow UTF-8 and UTF-8 with BOM (utf-8-sig)."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

def _pick(d: dict, keys: list, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return default

# -------------- loaders ---------------

def _load_index():
    if not os.path.exists(INDEX_JSON):
        return {"packages": []}
    obj = _load_json_tolerant(INDEX_JSON) or {}
    return obj if isinstance(obj, dict) else {"packages": []}

def _last_two_packages():
    idx = _load_index()
    pkgs = idx.get("packages", [])
    if len(pkgs) < 2:
        return None, None
    return pkgs[-1], pkgs[-2]

def _equity_path(pkg_entry) -> str:
    fdir = pkg_entry["final_dir"]
    eqname = pkg_entry["manifest"]["entrypoints"]["equity"]
    return os.path.join(fdir, eqname)

def _summary_path(pkg_entry) -> str:
    fdir = pkg_entry["final_dir"]
    return os.path.join(fdir, "summary.json")

def _load_equity_csv(pkg_entry):
    fpath = _equity_path(pkg_entry)
    df = pd.read_csv(fpath, parse_dates=["date"]).set_index("date").sort_index()
    return df[["nav","ret"]].copy()

def _load_summary(pkg_entry) -> dict:
    return _load_json_tolerant(_summary_path(pkg_entry)) or {}

# ------------- metrics ----------------

def _mdd(nav: pd.Series) -> float:
    if nav.empty:
        return 0.0
    peak = nav.cummax()
    dd = nav / peak - 1.0
    return float(dd.min())

def _last_30d_return(nav: pd.Series) -> float:
    if len(nav) < 2:
        return 0.0
    end = nav.index[-1]
    start = end - timedelta(days=30)
    sub = nav[nav.index >= start]
    if len(sub) < 2:
        return 0.0
    return float(sub.iloc[-1] / sub.iloc[0] - 1.0)

def _align_common(a: pd.DataFrame, b: pd.DataFrame):
    ix = a.index.intersection(b.index)
    return a.loc[ix].copy(), b.loc[ix].copy()

def _extract_info(summary: dict, df: pd.DataFrame) -> dict:
    """요약 표시에 사용할 공통 키 정리 (없으면 안전한 기본값)."""
    params = summary.get("params") or summary.get("args") or summary.get("config") or {}
    info = {
        "mode": _pick(params, ["mode", "strategy_mode"], "-"),
        "wl": _pick(params, ["wl", "use_watchlist"], "-"),
        "top": _pick(params, ["top", "top_n"], "-"),
        "rows": int(_pick(summary, ["rows", "n_rows"], len(df))),
        "start": df.index.min().strftime("%Y-%m-%d") if len(df) else "-",
        "end":   df.index.max().strftime("%Y-%m-%d") if len(df) else "-",
        "notes": _pick(summary, ["notes", "note", "desc"], ""),
    }
    return info

# --------------- routes ---------------

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

    # 요약/설정(요약 json + 데이터로 보강)
    cur_sum = _load_summary(cur)
    prev_sum = _load_summary(prev)
    cur_info = _extract_info(cur_sum, a)
    prev_info = _extract_info(prev_sum, b)

    # 종합지표
    cur_nav_end = float(a["nav"].iloc[-1]) if len(a) else None
    prev_nav_end= float(b["nav"].iloc[-1]) if len(b) else None
    cur_mdd = _mdd(a["nav"]) if len(a) else None
    prev_mdd= _mdd(b["nav"]) if len(b) else None
    cur_30d = _last_30d_return(a["nav"]) if len(a) else None
    prev_30d= _last_30d_return(b["nav"]) if len(b) else None

    # 최근 50개 표
    a_tail = a.tail(50).reset_index()
    b_tail = b.tail(50).reset_index()

    # 차트 데이터(최근 360개 거래일)
    a_chart = a.tail(360)
    b_chart = b.tail(360)
    labels = [d.strftime("%Y-%m-%d") for d in a_chart.index]
    chart_cur = [round(float(x), 4) for x in a_chart["nav"].tolist()]
    chart_prev= [round(float(x), 4) for x in b_chart["nav"].tolist()]

    ctx = {
        "request": request,
        "has_data": True,
        "cur_pkg": cur, "prev_pkg": prev,
        "cur_info": cur_info, "prev_info": prev_info,
        "cur_end": cur_nav_end, "prev_end": prev_nav_end,
        "cur_mdd": cur_mdd, "prev_mdd": prev_mdd,
        "cur_30d": cur_30d, "prev_30d": prev_30d,
        "rows": zip(
            a_tail["date"].dt.strftime("%Y-%m-%d"),
            a_tail["nav"].round(4), b_tail["nav"].round(4),
            a_tail["ret"].round(5), b_tail["ret"].round(5),
        ),
        "labels": labels,
        "series_cur": chart_cur,
        "series_prev": chart_prev,
    }
    return templates.TemplateResponse("bt_history.html", ctx)

# HEAD 헬스체크
@router.head("/bt/history")
def bt_history_head():
    return Response(status_code=200)

# CSV 내보내기(공통 구간 비교)
@router.get("/bt/history.csv")
def bt_history_csv():
    cur, prev = _last_two_packages()
    if not cur or not prev:
        return Response("no data", status_code=404, media_type="text/plain; charset=utf-8")
    a = _load_equity_csv(cur)
    b = _load_equity_csv(prev)
    a, b = _align_common(a, b)
    out = (
        pd.DataFrame({
            "date": a.index.strftime("%Y-%m-%d"),
            "nav_cur": a["nav"].values,
            "nav_prev": b["nav"].values,
            "ret_cur": a["ret"].values,
            "ret_prev": b["ret"].values,
        })
    )
    buf = io.StringIO()
    out.to_csv(buf, index=False)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="bt_history.csv"'},
    )
