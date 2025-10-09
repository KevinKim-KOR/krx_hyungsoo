#!/usr/bin/env python3
from __future__ import annotations
import os, json, time, math
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
CACHE_KR = DATA / "cache" / "kr"
PARQUET = DATA / "parquet"

# ---------- 공통 유틸 ----------
def _bdate_range(start: str, end: str) -> pd.DatetimeIndex:
    idx = pd.bdate_range(start=start, end=end, freq="C", holidays=None)
    return idx

def _coerce_close(df: pd.DataFrame) -> pd.Series:
    """여러 형태의 DataFrame에서 '종가/Close/Adj Close' 추출."""
    if df is None or len(df) == 0:
        raise ValueError("empty dataframe")

    # 단일컬럼이면 그대로
    if df.shape[1] == 1:
        s = pd.to_numeric(df.iloc[:, 0], errors="coerce")
        s.index = pd.to_datetime(df.index)
        return s

    cols = [c for c in df.columns]
    # 한국어 '종가'
    for key in ["종가", "close", "Close", "Adj Close"]:
        if key in df.columns:
            s = pd.to_numeric(df[key], errors="coerce")
            s.index = pd.to_datetime(df.index)
            return s

    # MultiIndex를 평탄화해서 탐색
    if isinstance(df.columns, pd.MultiIndex):
        flat = [" | ".join(map(str, c)) for c in df.columns]
        tmp = df.copy()
        tmp.columns = flat
        for key in ["Adj Close", "Close", "종가"]:
            cands = [c for c in tmp.columns if key in c]
            if cands:
                s = pd.to_numeric(tmp[cands[0]], errors="coerce")
                s.index = pd.to_datetime(tmp.index)
                return s

    # 첫 번째 숫자열
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if num_cols:
        s = pd.to_numeric(df[num_cols[0]], errors="coerce")
        s.index = pd.to_datetime(df.index)
        return s

    raise KeyError(f"cannot find close column from columns={cols}")

def _normalize_close_ret(close: pd.Series, start: str, end: str) -> pd.DataFrame:
    close = close.dropna()
    close = close.sort_index()
    idx = _bdate_range(start, end)
    out = pd.DataFrame({"close": close.reindex(idx).ffill()})
    out["ret"] = out["close"].pct_change().fillna(0.0)
    return out

# ---------- 설정 로더 ----------
def _load_yaml(path: Path) -> Dict[str, Any]:
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

def load_sources_cfg() -> Dict[str, Any]:
    path = Path(os.getenv("DATA_SOURCES_YAML", ROOT / "config" / "data_sources.yaml"))
    if path.exists():
        try: return _load_yaml(path)
        except Exception: pass
    return {"benchmarks": {}, "universe": {}, "probes": ["069500.KS.pkl","069500.pkl"]}

def _resolve_bm_plan(name: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    bms = cfg.get("benchmarks", {})
    if isinstance(bms, dict) and name in bms:
        return bms[name]
    # 합리적 기본값(레거시 하드코딩 제거용 fallback)
    defaults = {
        "KOSPI": {"providers": ["local_cache","parquet","pykrx_index","yf_index","yf_etf"],
                  "symbols": {"pykrx_index":"1001","yf_index":"^KS11","yf_etf":"069500.KS","local_keys":["069500.KS","069500"]}},
        "KOSDAQ":{"providers": ["local_cache","parquet","pykrx_index","yf_index","yf_etf"],
                  "symbols": {"pykrx_index":"2001","yf_index":"^KQ11","yf_etf":"229200.KS","local_keys":["229200.KS","229200"]}},
        "S&P500":{"providers": ["local_cache","parquet","yf_index","yf_etf"],
                  "symbols": {"yf_index":"^GSPC","yf_etf":"SPY","local_keys":["SPY","^GSPC"]}},
    }
    return defaults.get(name, {"providers":["local_cache"], "symbols":{"local_keys":[]}})

# ---------- 각 공급자 로더 ----------
def _load_local_cache(symbols: Dict[str,Any], start: str, end: str) -> Optional[pd.DataFrame]:
    keys: List[str] = symbols.get("local_keys") or []
    for k in keys:
        for cand in [f"{k}.pkl", f"{k}.KS.pkl"]:
            p = CACHE_KR / cand
            if p.exists():
                try:
                    df = pd.read_pickle(p)
                    # index 기반 또는 'date' 컬럼 기반 모두 허용
                    if isinstance(df, pd.DataFrame):
                        if isinstance(df.index, pd.DatetimeIndex):
                            close = _coerce_close(df)
                        else:
                            # date 컬럼 추정
                            dc = next((c for c in df.columns if "date" in str(c).lower()), None)
                            if dc:
                                close = _coerce_close(df.set_index(pd.to_datetime(df[dc])))
                            else:
                                close = _coerce_close(df)
                    else:
                        # Series 등은 직접 처리
                        close = pd.to_numeric(pd.Series(df), errors="coerce")
                        close.index = pd.to_datetime(close.index)
                    return _normalize_close_ret(close, start, end)
                except Exception:
                    continue
    return None

def _load_parquet(name: str, start: str, end: str) -> Optional[pd.DataFrame]:
    p = PARQUET / f"{name}.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
        close = _coerce_close(df)
        return _normalize_close_ret(close, start, end)
    except Exception:
        return None

def _load_pykrx_index(symbols: Dict[str,Any], start: str, end: str) -> Optional[pd.DataFrame]:
    try:
        from pykrx import stock
    except Exception:
        return None
    code = symbols.get("pykrx_index")
    if not code: return None
    try:
        s = start.replace("-","")
        e = end.replace("-","")
        df = stock.get_index_ohlcv_by_date(s, e, code)[["종가"]].rename(columns={"종가":"close"})
        close = df["close"]
        return _normalize_close_ret(close, start, end)
    except Exception:
        # pykrx 내 '지수명' KeyError 등은 무해 실패로 간주
        return None

def _yf_download_once(tkr: str, start: str, end: str):
    import yfinance as yf, pandas as pd
    df = yf.download(
        tkr, start=start, end=end,
        progress=False, auto_adjust=False,
        group_by="column", threads=False
    )
    if df is None or len(df) == 0:
        raise ValueError("yfinance returned empty")
    # 컬럼 강건 처리
    if not isinstance(df.columns, pd.MultiIndex):
        if "Adj Close" in df.columns:
            return pd.to_numeric(df["Adj Close"], errors="coerce")
        if "Close" in df.columns:
            return pd.to_numeric(df["Close"], errors="coerce")
    # MultiIndex → 평탄화 후 'Adj Close' 우선
    flat = [" | ".join(map(str, c)) if isinstance(c, tuple) else str(c) for c in df.columns]
    tmp = df.copy(); tmp.columns = flat
    for key in ["Adj Close","Close"]:
        cands = [c for c in tmp.columns if key in c]
        if cands:
            return pd.to_numeric(tmp[cands[0]], errors="coerce")
    raise KeyError("Close/Adj Close not found")

def _load_yf(symbol: str, start: str, end: str) -> Optional[pd.DataFrame]:
    # 짧은 재시도(외부요인)
    last_err = None
    for i in range(5):
        try:
            s = _yf_download_once(symbol, start, end)
            s.index = pd.to_datetime(s.index)
            return _normalize_close_ret(s, start, end)
        except Exception as e:
            last_err = e
            # 레이트리밋/네트워크 → 짧게 backoff (총수초)
            time.sleep(min(2**i, 5))
    # 실패는 None
    return None

def _load_yf_index(symbols: Dict[str,Any], start: str, end: str) -> Optional[pd.DataFrame]:
    tkr = symbols.get("yf_index")
    return _load_yf(tkr, start, end) if tkr else None

def _load_yf_etf(symbols: Dict[str,Any], start: str, end: str) -> Optional[pd.DataFrame]:
    tkr = symbols.get("yf_etf")
    return _load_yf(tkr, start, end) if tkr else None

# ---------- 퍼사드 ----------
def load_benchmark(name: str, start: str, end: str) -> pd.DataFrame:
    """
    벤치마크 로더(하드코딩 제거):
    - config/data_sources.yaml 의 providers 순서에 따라
      local_cache → parquet → pykrx_index → yf_index → yf_etf …
      순차 시도. 성공 시 즉시 반환.
    - 모두 실패하면 RuntimeError.
    """
    cfg = load_sources_cfg()
    plan = _resolve_bm_plan(name, cfg)
    providers: List[str] = plan.get("providers") or []
    symbols: Dict[str,Any] = plan.get("symbols") or {}

    # 빈/오류 방지
    providers = [p for p in providers if p]

    # 우선순위대로 시도
    for prov in providers:
        try:
            if prov == "local_cache":
                df = _load_local_cache(symbols, start, end)
            elif prov == "parquet":
                df = _load_parquet(name, start, end)
            elif prov == "pykrx_index":
                df = _load_pykrx_index(symbols, start, end)
            elif prov == "yf_index":
                df = _load_yf_index(symbols, start, end)
            elif prov == "yf_etf":
                df = _load_yf_etf(symbols, start, end)
            else:
                df = None
            if df is not None and len(df) > 0:
                return df
        except Exception:
            # 공급자 개별 실패는 조용히 넘어가고 다음 후보 시도
            continue

    raise RuntimeError(f"benchmark '{name}' unavailable by providers={providers}")
