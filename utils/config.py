# utils/config.py
# -*- coding: utf-8 -*-
from typing import Tuple, Dict, List
try:
    import yaml  # noqa
except Exception:
    yaml = None

# 1) reporting_eod의 표준 로더가 있으면 그대로 래핑
try:
    from reporting_eod import _load_cfg as _load_cfg_env  # 표준 로더
except Exception:
    _load_cfg_env = None

def load_cfg(path: str = None) -> Dict:
    """
    단일 진입점: 보고서/웹/시그널 모두 이 함수를 통해 설정을 읽습니다.
    - 우선 reporting_eod._load_cfg 사용(환경변수 KRX_CONFIG 포함)
    - 없으면 비워진 dict 반환
    """
    if _load_cfg_env is not None:
        try:
            return _load_cfg_env(path) or {}
        except Exception:
            return {}
    # 안전한 폴백 (PyYAML 없거나 경로 이슈 시 빈 dict)
    return {}

def get_report_cfg_defaults() -> Tuple[int, float]:
    cfg = load_cfg()
    r = cfg.get("report") or {}
    try:   top_n = int(r.get("top_n", 5))
    except: top_n = 5
    try:   min_abs = float(r.get("min_abs_ret", 0.003))
    except: min_abs = 0.003
    return top_n, min_abs

def get_signals_cfg_defaults() -> Dict:
    cfg = load_cfg()
    s = cfg.get("signals") or {}
    mode     = s.get("mode", "score_abs")
    windows  = [int(x) for x in (s.get("windows",[1,5,20]) or [1,5,20])]
    weights  = s.get("weights",[0.2,0.3,0.5])
    if not isinstance(weights, list) or len(weights)!=len(windows):
        weights = [1.0/len(windows)]*len(windows)
    try: thr = float(s.get("score_threshold", 0.005))
    except: thr = 0.005
    top_k   = int(s.get("top_k",3))
    bottom_k= int(s.get("bottom_k",3))
    use_wl  = bool(s.get("use_watchlist", False))

    f = s.get("filters", {}) or {}
    filt = {
        "turnover_window": int(f.get("turnover_window", 20)),
        "min_turnover_krw": float(f.get("min_turnover_krw", 0.0)),
        "vol_window": int(f.get("vol_window", 20)),
        "max_vol_std": float(f.get("max_vol_std", 1.0)),
        "sma_short": int(f.get("sma_short", 5)),
        "sma_long":  int(f.get("sma_long", 20)),
        "sma_require": f.get("sma_require", "none"),
    }
    return {
        "mode": mode, "windows": windows, "weights": weights,
        "score_threshold": thr, "top_k": top_k, "bottom_k": bottom_k,
        "use_watchlist": use_wl, "filters": filt,
    }
