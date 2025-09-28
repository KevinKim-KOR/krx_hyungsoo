# signals/service.py
from typing import List, Dict, Optional, Tuple
from utils.config import get_report_cfg_defaults, get_signals_cfg_defaults
from reporting_eod import _load_watchlist
from .queries import recent_trading_dates_kr, load_universe_from_json, load_prices_for_dates, load_names

def _merge_cfg(base: Dict, overrides: Optional[Dict]) -> Dict:
    if not overrides:
        return base
    out = dict(base)
    for k in ("mode","windows","weights","score_threshold","top_k","bottom_k","use_watchlist"):
        if k in overrides and overrides[k] is not None:
            out[k] = overrides[k]
    return out

def compute_daily_signals(codes: Optional[List[str]] = None,
                          overrides: Optional[Dict] = None) -> Dict[str, object]:
    """
    멀티-모멘텀 점수 기반.
    overrides로 mode/rank/threshold/watchlist 등을 일시 변경 가능(웹 UI에서 사용).
    """
    cfg = _merge_cfg(get_signals_cfg_defaults(), overrides)
    top_n, min_abs = get_report_cfg_defaults()

    dates = recent_trading_dates_kr(limit=max(cfg["windows"]) + 60)
    if not dates:
        return {"date": None, "signals": [], "mode": cfg["mode"], "windows": cfg["windows"]}

    d0 = dates[-1]
    need_dates: List[str] = [d0]
    for w in cfg["windows"]:
        idx = len(dates) - 1 - int(w)
        if idx >= 0:
            need_dates.append(dates[idx])
    need_dates = sorted(set(need_dates))

    if codes is None:
        if cfg.get("use_watchlist"):
            try:
                codes = _load_watchlist() or []
            except Exception:
                codes = []
        if not codes:
            codes = load_universe_from_json()

    names = load_names(codes)
    px = load_prices_for_dates(codes, need_dates)

    rows: List[Dict] = []
    insufficient = 0
    for code in codes:
        m = px.get(code, {})
        p0 = m.get(d0)
        if p0 is None:
            insufficient += 1; continue

        rets: List[float] = []
        ok = True
        for w in cfg["windows"]:
            idx = len(dates) - 1 - int(w)
            if idx < 0: ok = False; break
            d_prev = dates[idx]
            p1 = m.get(d_prev)
            if p1 is None or p1 == 0: ok = False; break
            rets.append((p0 - p1) / p1)
        if not ok:
            insufficient += 1; continue

        score = sum(r * float(wt) for r, wt in zip(rets, cfg["weights"]))
        signal = "HOLD"
        if cfg["mode"] == "score_abs":
            thr = float(cfg["score_threshold"])
            if score >= thr: signal = "BUY"
            elif score <= -thr: signal = "SELL"

        rows.append({
            "code": code, "name": names.get(code, code), "date": d0,
            "r1": rets[0] if len(rets)>0 else None,
            "r5": rets[1] if len(rets)>1 else None,
            "r20": rets[2] if len(rets)>2 else None,
            "score": score, "signal": signal
        })

    if cfg["mode"] == "rank":
        rows = sorted(rows, key=lambda x: x["score"], reverse=True)
        for i, row in enumerate(rows):
            if i < int(cfg["top_k"]): row["signal"] = "BUY"
            elif i >= max(0, len(rows)-int(cfg["bottom_k"])): row["signal"] = "SELL"
            else: row["signal"] = "HOLD"
    else:
        rows = sorted(rows, key=lambda x: abs(x["score"]), reverse=True)

    return {
        "date": d0, "signals": rows, "mode": cfg["mode"],
        "windows": cfg["windows"], "weights": cfg["weights"],
        "score_threshold": float(cfg["score_threshold"]),
        "top_k": int(cfg["top_k"]), "bottom_k": int(cfg["bottom_k"]),
        "use_watchlist": bool(cfg["use_watchlist"]),
        "insufficient_count": insufficient, "min_abs": min_abs,
    }
