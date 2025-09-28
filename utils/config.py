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
    cfg = load_cfg()
    r = cfg.get("report") or {}
    try:
        top_n = int(r.get("top_n", 5))
    except Exception:
        top_n = 5
    try:
        min_abs = float(r.get("min_abs_ret", 0.003))
    except Exception:
        min_abs = 0.003
    return top_n, min_abs

def get_signals_cfg_defaults() -> Dict:
    cfg = load_cfg()
    s = cfg.get("signals") or {}
    mode = s.get("mode", "score_abs")  # "score_abs" | "rank"
    windows = s.get("windows", [1, 5, 20])
    try:
        windows = [int(x) for x in windows]
    except Exception:
        windows = [1, 5, 20]
    weights = s.get("weights", [0.2, 0.3, 0.5])
    if not isinstance(weights, list) or len(weights) != len(windows):
        weights = [1.0 / len(windows)] * len(windows)
    try:
        thr = float(s.get("score_threshold", 0.005))  # 0.5%
    except Exception:
        thr = 0.005
    try:
        top_k = int(s.get("top_k", 3))
    except Exception:
        top_k = 3
    try:
        bottom_k = int(s.get("bottom_k", 3))
    except Exception:
        bottom_k = 3
    use_watchlist = bool(s.get("use_watchlist", False))
    return {
        "mode": mode,
        "windows": windows,
        "weights": weights,
        "score_threshold": thr,
        "top_k": top_k,
        "bottom_k": bottom_k,
        "use_watchlist": use_watchlist,
    }
