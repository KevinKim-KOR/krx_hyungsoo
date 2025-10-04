from __future__ import annotations
from pathlib import Path
from datetime import datetime
import os, re, time
import pandas as pd

# ---------- 공용 유틸 ----------
def _bdate_range(start: str, end: str) -> pd.DatetimeIndex:
    return pd.bdate_range(start=pd.to_datetime(start), end=pd.to_datetime(end), freq="B")

def _to_yyyymmdd(s: str) -> str:
    return pd.to_datetime(s).strftime("%Y%m%d")

def _safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s)

def _ensure_dir(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)

# ---------- 야후 파트: 캐시 + 재시도 ----------
def _yf_download_with_cache(ticker: str, start: str, end: str, tries: int = 4, backoff: int = 4) -> pd.DataFrame:
    """yfinance 다운로드를 파일 캐시와 재시도로 안정화."""
    import yfinance as yf

    cache_dir = Path("data/webcache/yf")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{_safe_name(ticker)}_{start}_{end}.csv"

    # 1) 캐시 우선 사용
    if cache_path.exists():
        try:
            df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
            if len(df):
                return df
        except Exception:
            pass  # 캐시가 손상되었으면 새로 받는다

    last_err = None
    for i in range(1, tries + 1):
        try:
            df = yf.download(
                ticker, start=start, end=end,
                progress=False, auto_adjust=False,
                group_by="column", threads=False
            )
            if df is not None and len(df):
                # 캐시 저장
                df.to_csv(cache_path)
                return df
            last_err = ValueError("empty dataframe")
        except Exception as e:
            last_err = e
        # 레이트리밋/네트워크 이슈 → 대기 후 재시도
        time.sleep(backoff * i)

    # 모두 실패
    raise last_err if last_err else RuntimeError("yfinance failed unexpectedly")

def _extract_close(df: pd.DataFrame, ticker_hint: str = "") -> pd.Series:
    """단일/멀티 컬럼 안전하게 'Close' 계열 시리즈를 뽑는다."""
    if not isinstance(df.columns, pd.MultiIndex):
        if "Adj Close" in df.columns:
            s = df["Adj Close"]
        elif "Close" in df.columns:
            s = df["Close"]
        else:
            cand = [c for c in df.columns if "Adj" in c or "Close" in c]
            if not cand:
                raise KeyError(f"Adj/Close not in columns: {df.columns.tolist()}")
            s = df[cand[0]]
        return s.rename("close")

    # MultiIndex → 평탄화
    flat_cols = [" | ".join(map(str, c)) for c in df.columns]
    df_flat = df.copy()
    df_flat.columns = flat_cols

    # 힌트가 있으면 우선
    if ticker_hint:
        cand = [c for c in flat_cols if ("Adj Close" in c or "Close" in c) and ticker_hint in c]
        if cand:
            return df_flat[cand[0]].rename("close")

    cand = [c for c in flat_cols if "Adj Close" in c] or [c for c in flat_cols if "Close" in c]
    if not cand:
        raise KeyError(f"Adj/Close not in MultiIndex columns: {flat_cols}")
    return df_flat[cand[0]].rename("close")

def _load_yf_index_close_ret(ticker: str, start: str, end: str) -> pd.DataFrame:
    """야후에서 인덱스/ETF를 받아 close/ret 생성."""
    df = _yf_download_with_cache(ticker, start, end)
    s = _extract_close(df, ticker_hint=ticker)
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()

    idx = _bdate_range(start, end)
    out = pd.DataFrame({"close": s.reindex(idx).ffill()})
    out["ret"] = out["close"].pct_change().fillna(0.0)
    return out

# ---------- 인덱스 로더 ----------
def load_kospi(start: str, end: str) -> pd.DataFrame:
    """KOSPI: 우선 pykrx → 실패 시 야후(^KS11) → 그래도 실패 시 ETF(069500.KS) 프록시."""
    # 1) pykrx 시도
    try:
        from pykrx import stock
        s, e = _to_yyyymmdd(start), _to_yyyymmdd(end)
        df = stock.get_index_ohlcv_by_date(s, e, "1001")[["종가"]].rename(columns={"종가": "close"})
        df.index = pd.to_datetime(df.index)
        idx = _bdate_range(start, end)
        df = df.reindex(idx).ffill()
        df["ret"] = df["close"].pct_change().fillna(0.0)
        return df
    except Exception:
        pass
    # 2) 야후 지수(^KS11)
    try:
        return _load_yf_index_close_ret("^KS11", start, end)
    except Exception:
        # 3) 최후: KOSPI200 ETF(069500.KS) 프록시
        return _load_yf_index_close_ret("069500.KS", start, end)

def load_kosdaq(start: str, end: str) -> pd.DataFrame:
    """KOSDAQ: pykrx → 야후(^KQ11) → ETF(229200.KS) 프록시."""
    try:
        from pykrx import stock
        s, e = _to_yyyymmdd(start), _to_yyyymmdd(end)
        df = stock.get_index_ohlcv_by_date(s, e, "2001")[["종가"]].rename(columns={"종가": "close"})
        df.index = pd.to_datetime(df.index)
        idx = _bdate_range(start, end)
        df = df.reindex(idx).ffill()
        df["ret"] = df["close"].pct_change().fillna(0.0)
        return df
    except Exception:
        pass
    try:
        return _load_yf_index_close_ret("^KQ11", start, end)
    except Exception:
        return _load_yf_index_close_ret("229200.KS", start, end)


def load_sp500(start: str, end: str) -> pd.DataFrame:
    """S&P500: 야후 ^GSPC → 실패 시 SPY ETF 프록시."""
    try:
        return _load_yf_index_close_ret("^GSPC", start, end)
    except Exception:
        return _load_yf_index_close_ret("SPY", start, end)

def load_benchmark(name: str, start: str, end: str) -> pd.DataFrame:
    name = name.upper()
    if name == "KOSPI":  return load_kospi(start, end)
    if name == "KOSDAQ": return load_kosdaq(start, end)
    if name in {"S&P500", "SP500", "GSPC"}: return load_sp500(start, end)
    raise ValueError(f"Unsupported benchmark: {name}")