from __future__ import annotations
import os, re, time
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd

class ExternalDataUnavailable(RuntimeError):
    pass

# --- env policy ---
def _allow_net() -> bool:
    # 기본 온라인 허용; 필요시 config/env.*.sh 에서 ALLOW_NET_FETCH로 제어
    return str(os.environ.get("ALLOW_NET_FETCH", "1")).lower() in ("1", "true", "yes", "y")

# --- defaults (최소 하드코딩) ---
DEFAULT_POLICY = {
    "KOSPI":  {"providers": ["local_cache", "parquet", "pykrx_index", "yf_index", "yf_etf"],
               "symbols":   {"pykrx_index": "1001", "yf_index": "^KS11", "yf_etf": "069500.KS",
                             "local_keys": ["069500.KS", "069500", "KOSPI", "KOSPI_ETF"]}},
    "KOSDAQ": {"providers": ["local_cache", "parquet", "pykrx_index", "yf_index", "yf_etf"],
               "symbols":   {"pykrx_index": "2001", "yf_index": "^KQ11", "yf_etf": "229200.KS",
                             "local_keys": ["229200.KS", "229200", "KOSDAQ", "KOSDAQ_ETF"]}},
    "S&P500": {"providers": ["local_cache", "parquet", "yf_index", "yf_etf"],
               "symbols":   {"yf_index": "^GSPC", "yf_etf": "SPY",
                             "local_keys": ["SPY", "^GSPC"]}},
}

def _load_policy() -> Dict[str, Any]:
    p = Path("config/data_sources.yaml")
    if p.exists():
        try:
            import yaml  # PyYAML
            return yaml.safe_load(p.read_text(encoding="utf-8")).get("benchmarks", DEFAULT_POLICY)
        except Exception:
            pass
    return DEFAULT_POLICY

# --- common helpers ---
def _bdate_range(start: str, end: str) -> pd.DatetimeIndex:
    return pd.bdate_range(start=pd.to_datetime(start), end=pd.to_datetime(end), freq="B")

def _to_yyyymmdd(s: str) -> str:
    return pd.to_datetime(s).strftime("%Y%m%d")

def _safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s)

def _extract_close_from_obj(obj) -> pd.Series:
    """로컬 캐시 포맷 다양성 대응: Series/DataFrame/Dict/중첩 모두에서 'close' 유도."""
    if isinstance(obj, pd.Series):
        s = obj.copy(); s.name = "close"; return s

    if isinstance(obj, pd.DataFrame):
        df = obj.copy()
        # 명시 컬럼
        for c in ["close", "Close", "adj_close", "Adj Close", "Adj_Close", "AdjClose", "종가", "price", "Price"]:
            if c in df.columns:
                return df[c].rename("close")
        # MultiIndex 평탄화
        if isinstance(df.columns, pd.MultiIndex):
            flat_cols = [" | ".join(map(str, c)) for c in df.columns]
            df = df.copy(); df.columns = flat_cols
            cand = [c for c in flat_cols if ("Adj Close" in c or "Close" in c or "종가" in c)]
            if cand:
                return df[cand[0]].rename("close")
        # 숫자 첫 컬럼
        num = df.select_dtypes("number")
        if num.shape[1] > 0:
            return num.iloc[:, 0].rename("close")

    if isinstance(obj, dict):
        # 흔한 키
        for k in ["close", "Close", "Adj Close", "adj_close", "종가", "price", "Price"]:
            if k in obj:
                return _extract_close_from_obj(obj[k])
        # 하위 값 탐색
        for v in obj.values():
            try:
                s = _extract_close_from_obj(v)
                if isinstance(s, pd.Series):
                    return s
            except Exception:
                pass

    try:
        df = pd.DataFrame(obj)
        return _extract_close_from_obj(df)
    except Exception:
        pass

    raise ValueError("could not extract close from local object")

def _frame_from_close_series(s: pd.Series, start: str, end: str) -> pd.DataFrame:
    s.index = pd.to_datetime(s.index); s = s.sort_index()
    idx = _bdate_range(start, end)
    out = pd.DataFrame({"close": s.reindex(idx).ffill()})
    out["ret"] = out["close"].pct_change().fillna(0.0)
    return out

# --- local cache / parquet ---
def _load_local_cache(symbol_candidates: List[str], start: str, end: str) -> pd.DataFrame:
    roots = [Path("data/benchmarks"), Path("data/cache/kr"), Path("data/cache")]
    names = []
    for sym in symbol_candidates:
        names += [f"{sym}.parquet", f"{sym}.pkl", sym]  # parquet 우선
    for root in roots:
        for name in names:
            p = root / name
            if not p.exists():
                continue
            try:
                if p.suffix.lower() in (".parquet", ".pq"):
                    obj = pd.read_parquet(p)
                elif p.suffix.lower() in (".pkl", ".pickle", ""):
                    obj = pd.read_pickle(p)
                else:
                    continue
                s = _extract_close_from_obj(obj)
                return _frame_from_close_series(s, start, end)
            except Exception:
                continue
    raise FileNotFoundError(f"no local cache for {symbol_candidates}")

# --- yfinance with cache+retry ---
def _yf_download_with_cache(ticker: str, start: str, end: str, tries: int = 5, backoff: int = 5) -> pd.DataFrame:
    import yfinance as yf
    cache_dir = Path("data/webcache/yf"); cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{_safe_name(ticker)}_{start}_{end}.csv"

    if cache_path.exists():
        try:
            df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
            if len(df): return df
        except Exception:
            pass

    last_err = None
    for i in range(1, tries + 1):
        try:
            df = yf.download(
                ticker, start=start, end=end,
                progress=False, auto_adjust=False,
                group_by="column", threads=False
            )
            if df is not None and len(df):
                df.to_csv(cache_path)
                return df
            last_err = ValueError("empty dataframe")
        except Exception as e:
            last_err = e
        time.sleep(backoff * i)  # 기하급수 백오프

    raise last_err if last_err else RuntimeError("yfinance failed")

def _extract_close_from_yf(df: pd.DataFrame, ticker_hint: str = "") -> pd.Series:
    if not isinstance(df.columns, pd.MultiIndex):
        if "Adj Close" in df.columns: s = df["Adj Close"]
        elif "Close" in df.columns:   s = df["Close"]
        else:
            cand = [c for c in df.columns if ("Adj" in c or "Close" in c)]
            if not cand: raise KeyError(f"Adj/Close not found: {df.columns.tolist()}")
            s = df[cand[0]]
        return s.rename("close")

    flat_cols = [" | ".join(map(str, c)) for c in df.columns]
    df_flat = df.copy(); df_flat.columns = flat_cols
    if ticker_hint:
        cand = [c for c in flat_cols if (("Adj Close" in c or "Close" in c) and ticker_hint in c)]
        if cand: return df_flat[cand[0]].rename("close")
    cand = [c for c in flat_cols if "Adj Close" in c] or [c for c in flat_cols if "Close" in c]
    if not cand: raise KeyError(f"Adj/Close not in MultiIndex: {flat_cols}")
    return df_flat[cand[0]].rename("close")

def _load_yf_index_close_ret(ticker: str, start: str, end: str) -> pd.DataFrame:
    if not _allow_net():
        raise ExternalDataUnavailable("network disabled by policy")
    df = _yf_download_with_cache(ticker, start, end)
    s  = _extract_close_from_yf(df, ticker_hint=ticker)
    return _frame_from_close_series(s, start, end)

# --- pykrx index ---
def _load_pykrx_index(code: str, start: str, end: str) -> pd.DataFrame:
    if not _allow_net():
        raise ExternalDataUnavailable("network disabled by policy")
    from pykrx import stock
    s, e = _to_yyyymmdd(start), _to_yyyymmdd(end)
    df = stock.get_index_ohlcv_by_date(s, e, code)[["종가"]].rename(columns={"종가": "close"})
    df.index = pd.to_datetime(df.index)
    idx = _bdate_range(start, end)
    df = df.reindex(idx).ffill()
    df["ret"] = df["close"].pct_change().fillna(0.0)
    return df

# --- public API ---
def load_benchmark(name: str, start: str, end: str) -> pd.DataFrame:
    norm = name.upper()
    key = "S&P500" if norm in {"S&P500", "SP500", "GSPC"} else norm
    pol = _load_policy().get(key)
    if not pol:
        raise ValueError(f"Unsupported benchmark: {name}")

    providers: List[str] = pol["providers"]
    sym = pol["symbols"]

    for p in providers:
        try:
            if p == "local_cache":
                return _load_local_cache(sym.get("local_keys", []), start, end)
            if p == "parquet":
                # parquet도 local_cache 경로에서 처리 (우선순위만 다름)
                return _load_local_cache(sym.get("local_keys", []), start, end)
            if p == "pykrx_index":
                return _load_pykrx_index(sym["pykrx_index"], start, end)
            if p == "yf_index":
                return _load_yf_index_close_ret(sym["yf_index"], start, end)
            if p == "yf_etf":
                return _load_yf_index_close_ret(sym["yf_etf"], start, end)
        except ExternalDataUnavailable:
            # 정책상 네트워크 금지 등 → 다음 프로바이더 시도
            continue
        except Exception:
            # 제공처 오류/레이트리밋 → 다음 프로바이더 시도
            continue

    raise ExternalDataUnavailable(f"all providers failed for {name}")
