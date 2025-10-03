# web/bt_history.py
from fastapi import APIRouter, Request, Response, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os, json, io
import pandas as pd
from datetime import timedelta

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

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

def _get_pkg_by_key(pkgs, key: str):
    """
    key 예시:
      - 'last' (가장 최신)
      - 'prev' (두 번째)
      - 'idx:N' (0-based index, 음수 허용: -1 최신)
      - 'ts:20251003_235301' (manifest.package_ts)
      - 'dir:/abs/or/final/dir' (final_dir)
    """
    if not pkgs:
        return None
    if key in (None, "", "last"):
        return pkgs[-1]
    if key == "prev":
        return pkgs[-2] if len(pkgs) >= 2 else None
    if key.startswith("idx:"):
        try:
            i = int(key.split(":", 1)[1])
            return pkgs[i]
        except Exception:
            return None
    if key.startswith("ts:"):
        ts = key.split(":", 1)[1]
        for p in pkgs:
            if p.get("manifest", {}).get("package_ts") == ts:
                return p
        return None
    if key.startswith("dir:"):
        d = key.split(":", 1)[1]
        for p in pkgs:
            if p.get("final_dir") == d:
                return p
        return None
    # fallback
    return pkgs[-1]

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
    if nav.empty: return 0.0
    peak = nav.cummax()
    dd = nav / peak - 1.0
    return float(dd.min())

def _last_30d_return(nav: pd.Series) -> float:
    if len(nav) < 2: return 0.0
    end = nav.index[-1]
    start = end - timedelta(days=30)
    sub = nav[nav.index >= start]
    if len(sub) < 2: return 0.0
    return float(sub.iloc[-1] / sub.iloc[0] - 1.0)

def _align_common(a: pd.DataFrame, b: pd.DataFrame):
    ix = a.index.intersection(b.index)
    return a.loc[ix].copy(), b.loc[ix].copy()

def _extract_info(summary: dict, df: pd.DataFrame) -> dict:
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
def bt_history(
    request: Request,
    # 선택: 비교할 두 패키지 키
    pkg_a: str = Query("last"),
    pkg_b: str = Query("prev"),
    # 선택: 최근 N 거래일 차트/표시 범위
    ndays: int = Query(360, ge=30, le=2000),
):
    idx = _load_index()
    pkgs = idx.get("packages", [])
    if len(pkgs) < 2:
        return templates.TemplateResponse(
            "bt_history.html",
            {"request": request, "has_data": False, "msg": "비교할 패키지가 2개 이상 필요합니다."}
        )

    a_pkg = _get_pkg_by_key(pkgs, pkg_a)
    b_pkg = _get_pkg_by_key(pkgs, pkg_b)
    if not a_pkg or not b_pkg:
        return templates.TemplateResponse(
            "bt_history.html",
            {"request": request, "has_data": False, "msg": "선택한 패키지를 찾지 못했습니다."}
        )

    df_a = _load_equity_csv(a_pkg)
    df_b = _load_equity_csv(b_pkg)
    a, b = _align_common(df_a, df_b)

    # 요약/설정
    a_sum = _load_summary(a_pkg)
    b_sum = _load_summary(b_pkg)
    a_info = _extract_info(a_sum, a)
    b_info = _extract_info(b_sum, b)

    # 종합지표
    a_end = float(a["nav"].iloc[-1]) if len(a) else None
    b_end = float(b["nav"].iloc[-1]) if len(b) else None
    a_mdd = _mdd(a["nav"]) if len(a) else None
    b_mdd = _mdd(b["nav"]) if len(b) else None
    a_30d = _last_30d_return(a["nav"]) if len(a) else None
    b_30d = _last_30d_return(b["nav"]) if len(b) else None

    # 최근 ndays 거래일
    a_nd = a.tail(ndays)
    b_nd = b.tail(ndays)

    # 테이블 50행
    a_tail = a_nd.tail(50).reset_index()
    b_tail = b_nd.tail(50).reset_index()

    # 차트
    labels = [d.strftime("%Y-%m-%d") for d in a_nd.index]
    series_a = [round(float(x), 4) for x in a_nd["nav"].tolist()]
    series_b = [round(float(x), 4) for x in b_nd["nav"].tolist()]

    # 드롭다운용 패키지 목록(최근 30개까지만)
    options = [
        {
            "key": f"ts:{p.get('manifest',{}).get('package_ts','')}",
            "label": f"{p.get('manifest',{}).get('package_ts','')}"
                     f" | {p.get('manifest',{}).get('commit','')[:10]}",
        }
        for p in pkgs[-30:]
    ]

    ctx = {
        "request": request,
        "has_data": True,
        "pkg_a": a_pkg, "pkg_b": b_pkg,
        "a_info": a_info, "b_info": b_info,
        "a_end": a_end, "b_end": b_end,
        "a_mdd": a_mdd, "b_mdd": b_mdd,
        "a_30d": a_30d, "b_30d": b_30d,
        "rows": zip(
            a_tail["date"].dt.strftime("%Y-%m-%d"),
            a_tail["nav"].round(4), b_tail["nav"].round(4),
            a_tail["ret"].round(5), b_tail["ret"].round(5),
        ),
        "labels": labels, "series_a": series_a, "series_b": series_b,
        "options": options, "ndays": ndays,
        "sel_a": f"ts:{a_pkg.get('manifest',{}).get('package_ts','')}",
        "sel_b": f"ts:{b_pkg.get('manifest',{}).get('package_ts','')}",
    }
    return templates.TemplateResponse("bt_history.html", ctx)

@router.head("/bt/history")
def bt_history_head():
    return Response(status_code=200)

@router.get("/bt/history.csv")
def bt_history_csv(
    pkg_a: str = Query("last"),
    pkg_b: str = Query("prev"),
    ndays: int = Query(360, ge=30, le=2000),
):
    idx = _load_index()
    pkgs = idx.get("packages", [])
    if len(pkgs) < 2:
        return Response("no data", status_code=404, media_type="text/plain; charset=utf-8")
    a_pkg = _get_pkg_by_key(pkgs, pkg_a)
    b_pkg = _get_pkg_by_key(pkgs, pkg_b)
    if not a_pkg or not b_pkg:
        return Response("not found", status_code=404, media_type="text/plain; charset=utf-8")

    a = _load_equity_csv(a_pkg)
    b = _load_equity_csv(b_pkg)
    a, b = _align_common(a, b)
    a = a.tail(ndays); b = b.tail(ndays)

    out = pd.DataFrame({
        "date": a.index.strftime("%Y-%m-%d"),
        "nav_a": a["nav"].values,
        "nav_b": b["nav"].values,
        "ret_a": a["ret"].values,
        "ret_b": b["ret"].values,
    })
    buf = io.StringIO(); out.to_csv(buf, index=False)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="bt_history.csv"'},
    )
