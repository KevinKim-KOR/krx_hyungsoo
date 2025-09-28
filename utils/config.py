# utils/config.py
# -*- coding: utf-8 -*-
from typing import Tuple, Dict, List
try:
    import yaml
except Exception:
    yaml = None

def load_cfg(path: str = "config.yaml") -> Dict:
    if yaml is None:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def get_report_cfg_defaults() -> Tuple[int, float]:
    cfg = load_cfg(); r = cfg.get("report") or {}
    top_n  = int(r.get("top_n", 5)) if str(r.get("top_n","")).isdigit() else 5
    try:   min_abs = float(r.get("min_abs_ret", 0.003))
    except: min_abs = 0.003
    return top_n, min_abs

def get_signals_cfg_defaults() -> Dict:
    cfg = load_cfg(); s = cfg.get("signals") or {}
    mode     = s.get("mode", "score_abs")
    windows  = [int(x) for x in (s.get("windows",[1,5,20]) or [1,5,20])]
    weights  = s.get("weights",[0.2,0.3,0.5])
    if not isinstance(weights, list) or len(weights)!=len(windows):
        weights = [1.0/len(windows)]*len(windows)
    try:   thr = float(s.get("score_threshold", 0.005))
    except: thr = 0.005
    top_k   = int(s.get("top_k",3))
    bottom_k= int(s.get("bottom_k",3))
    use_wl  = bool(s.get("use_watchlist", False))
    # --- 전략 필터 기본값 ---
    f = s.get("filters", {}) or {}
    filt = {
        "turnover_window": int(f.get("turnover_window", 20)),
        "min_turnover_krw": float(f.get("min_turnover_krw", 0.0)),  # 0이면 비활성
        "vol_window": int(f.get("vol_window", 20)),
        "max_vol_std": float(f.get("max_vol_std", 1.0)),            # 100% (= 사실상 비활성)
        "sma_short": int(f.get("sma_short", 5)),
        "sma_long":  int(f.get("sma_long", 20)),
        "sma_require": f.get("sma_require", "none"),                # 'none' | 'up' | 'down'
    }
    return {
        "mode": mode, "windows": windows, "weights": weights,
        "score_threshold": thr, "top_k": top_k, "bottom_k": bottom_k,
        "use_watchlist": use_wl, "filters": filt,
    }

def load_watchlist(path: str = "watchlist.yaml") -> List[str]:
    if yaml is None: return []
    try:
        with open(path,"r",encoding="utf-8") as f:
            y = yaml.safe_load(f) or []
        out = []
        if isinstance(y, dict): y = y.get("codes") or y.get("tickers") or []
        for it in y:
            if isinstance(it, str): out.append(it.strip())
            elif isinstance(it, dict):
                c = str(it.get("code") or it.get("ticker") or "").strip()
                if c: out.append(c)
        return sorted(set(out))
    except Exception:
        return []
