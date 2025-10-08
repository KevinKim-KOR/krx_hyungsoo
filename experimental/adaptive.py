# adaptive.py  (Py3.8 호환)
import copy
import pandas as pd
from krx_helpers import get_ohlcv_safe
from utils.datasources import regime_ticker

def _sma(s, n): return s.rolling(n).mean()

def detect_market_state(asof, cfg):
    """bull / neutral / bear 중 하나를 리턴"""
    ad = (cfg.get("adaptive") or {})
    #src   = ad.get("regime_source") or (cfg.get("regime", {}) or {}).get("spx_ticker", "069500.KS")
    src   = ad.get("regime_source") or (cfg.get("regime", {}) or {}).get("spx_ticker", regime_ticker())
    lb    = int(ad.get("regime_lookback_days", 200))

    start = (pd.to_datetime(asof) - pd.Timedelta(days=lb*3)).date()
    df = get_ohlcv_safe(src, start, pd.to_datetime(asof).date())
    if df is None or df.empty:
        return "neutral"

    hi, lo, cl = df["High"].dropna(), df["Low"].dropna(), df["Close"].dropna()
    if len(cl) < 60:
        return "neutral"

    sma50  = _sma(cl, 50)
    sma200 = _sma(cl, 200)
    slope50 = (sma50 - sma50.shift(5)).iloc[-1] if len(sma50) >= 55 else 0.0

    # 기본 판정
    state = "neutral"
    if len(sma200) >= 200:
        if cl.iloc[-1] > sma200.iloc[-1] and slope50 > 0:
            state = "bull"
        elif cl.iloc[-1] < sma200.iloc[-1] and slope50 < 0:
            state = "bear"

    # 변동성 과열 시 bull→neutral 강등 (옵션)
    vol_th = ad.get("vol_downgrade_atr_pct")
    if vol_th is not None:
        tr = (hi - lo).abs()
        atr = tr.rolling(14).mean()
        if len(atr) >= 14 and state == "bull":
            atr_pct = float(atr.iloc[-1] / cl.iloc[-1])
            if atr_pct >= float(vol_th):
                state = "neutral"
    return state

def _deep_update(base: dict, over: dict):
    for k,v in (over or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
    return base

def get_effective_cfg(asof, cfg):
    """adaptive.enabled이면, 상태별 프로필을 cfg에 덮어써서 반환"""
    ad = cfg.get("adaptive") or {}
    if not ad.get("enabled"): 
        return cfg
    state = detect_market_state(asof, cfg)
    eff = copy.deepcopy(cfg)
    prof = (ad.get("profiles") or {}).get(state)
    if prof:
        _deep_update(eff, prof)
    eff.setdefault("meta", {})["adaptive_state"] = state
    return eff
