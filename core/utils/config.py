# utils/config.py
# -*- coding: utf-8 -*-
from typing import Tuple, Dict, List
import os, time, shutil

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

def load_watchlist(path: str = None) -> List[str]:
    """
    watchlist.yaml을 읽어 코드 목록을 반환.
    우선 reporting_eod._load_watchlist()가 있으면 재사용하고,
    없으면 KRX_WATCHLIST > 인자 path > 기본 경로에서 YAML을 읽습니다.
    허용 포맷:
      - ["069500","005930", ...]
      - {"codes":[...]} / {"tickers":[...]} / {"watchlist":[...]}
      - [{"code":"069500","is_active":true}, ...]  (is_active=false 제외)
    """
    # 0) reporting_eod에 로더가 이미 있으면 우선 사용
    try:
        from reporting_eod import _load_watchlist as _wl
        wl = _wl()
        if wl:
            return sorted({str(x).strip() for x in wl if str(x).strip()})
    except Exception:
        pass

    # 1) 경로 후보
    cand = []
    envp = os.environ.get("KRX_WATCHLIST")
    for p in (path, envp, "watchlist.yaml", "conf/watchlist.yaml",
              os.path.expanduser("~/.config/krx_alertor_modular/watchlist.yaml")):
        if p:
            cand.append(p)

    try:
        import yaml
    except Exception:
        return []

    for p in cand:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    y = yaml.safe_load(f) or []
                if isinstance(y, dict):
                    lst = y.get("codes") or y.get("tickers") or y.get("watchlist") or []
                else:
                    lst = y
                out: List[str] = []
                for it in lst:
                    if isinstance(it, str):
                        c = it.strip()
                        if c: out.append(c)
                    elif isinstance(it, dict):
                        if it.get("is_active") is False: 
                            continue
                        c = str(it.get("code") or it.get("ticker") or "").strip()
                        if c: out.append(c)
                return sorted(set(out))
        except Exception:
            continue
    return []

def get_watchlist_path() -> str:
    p = os.environ.get("KRX_WATCHLIST")
    if p: return p
    # 선호 순서: secret > repo root > conf > 홈
    for c in (
        "secret/watchlist.yaml",
        "watchlist.yaml",
        "conf/watchlist.yaml",
        os.path.expanduser("~/.config/krx_alertor_modular/watchlist.yaml"),
    ):
        if os.path.exists(c):
            return c
    # 기본 경로
    return "secret/watchlist.yaml"

def _parse_watchlist_yaml(y) -> List[str]:
    # 다양한 포맷을 codes 리스트로 통일
    if isinstance(y, dict):
        lst = y.get("codes") or y.get("tickers") or y.get("watchlist") or []
    else:
        lst = y or []
    out: List[str] = []
    for it in lst:
        if isinstance(it, str):
            c = it.strip()
            if c: out.append(c)
        elif isinstance(it, dict):
            if it.get("is_active") is False:  # 규칙: is_active=false 제외
                continue
            c = str(it.get("code") or it.get("ticker") or "").strip()
            if c: out.append(c)
    return sorted(set(out))

def read_watchlist_codes() -> List[str]:
    try:
        import yaml
    except Exception:
        return []
    p = get_watchlist_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            y = yaml.safe_load(f) or []
        return _parse_watchlist_yaml(y)
    except Exception:
        return []

def write_watchlist_codes(codes: List[str]) -> bool:
    """한 줄당 1코드 형식으로 저장(단순 리스트). 저장 전 자동 백업."""
    try:
        import yaml
    except Exception:
        return False
    codes = [str(c).strip() for c in codes if str(c).strip()]
    p = get_watchlist_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    # 백업
    if os.path.exists(p):
        bdir = os.path.join(os.path.dirname(p), "backup")
        os.makedirs(bdir, exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(p, os.path.join(bdir, f"watchlist-{ts}.yaml"))
    # 저장(단순 리스트로)
    try:
        with open(p, "w", encoding="utf-8") as f:
            yaml.safe_dump(sorted(set(codes)), f, allow_unicode=True, sort_keys=False)
        return True
    except Exception:
        return False