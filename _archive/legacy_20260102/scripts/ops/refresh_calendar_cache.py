#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import date, timedelta
import sys
import pandas as pd

# --- 패키지 경로 보정: repo root를 sys.path에 추가 ---
ROOT = Path(__file__).resolve().parents[2]  # scripts/ops/ -> scripts -> ROOT
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 외부 설정(YAML)에서 우선순위 심볼을 읽어옴
from utils.datasources import calendar_symbol_priority

# 입출력 경로 고정
DATADIR = ROOT / "data" / "cache" / "kr"
DATADIR.mkdir(parents=True, exist_ok=True)
OUTP = DATADIR / "trading_days.pkl"


# ----------------------------
# 로컬 캐시 → 원격 순의 최소 의존 fetch
# ----------------------------
def _read_local(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """
    data/cache/kr/<symbol>.pkl 및 <raw>.pkl(예: 069500.KS -> 069500) 로컬 캐시 우선 시도.
    """
    paths = [DATADIR / f"{symbol}.pkl"]
    raw = symbol.split(".")[0]
    if raw != symbol:
        paths.append(DATADIR / f"{raw}.pkl")

    for p in paths:
        if p.is_file():
            try:
                df = pd.read_pickle(p)
                if df is None or len(df) == 0:
                    continue
                # 인덱스를 날짜로 정규화
                idx = pd.to_datetime(getattr(df, "index", pd.Index([]))).tz_localize(None).normalize()
                # 범위 필터
                mask = (idx >= start) & (idx <= end)
                df = df.loc[mask] if hasattr(df, "loc") else df
                if len(df) > 0:
                    return df
            except Exception:
                pass
    return pd.DataFrame()


def _read_yf(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """
    yfinance 단독 사용(최소 의존). 'Close' 우선, 없으면 'Adj Close'.
    """
    try:
        import yfinance as yf
        df = yf.download(
            symbol,
            start=start.date(),
            end=(end + pd.Timedelta(days=1)).date(),  # end 당일 포함
            progress=False,
            auto_adjust=False,
            group_by="column",
            threads=False,
        )
        if df is None or len(df) == 0:
            return pd.DataFrame()
        if "Close" in df.columns:
            out = df[["Close"]].rename(columns={"Close": "close"})
        elif "Adj Close" in df.columns:
            out = df[["Adj Close"]].rename(columns={"Adj Close": "close"})
        else:
            # 평탄화 후 'Close' 포함 첫 컬럼 사용
            cols = [c for c in map(str, df.columns) if "Close" in c]
            if not cols:
                return pd.DataFrame()
            out = df[cols[0]].to_frame("close")
        out.index = pd.to_datetime(out.index).tz_localize(None).normalize()
        return out
    except Exception:
        return pd.DataFrame()


def _first_available_df(symbols: list[str], start: pd.Timestamp, end: pd.Timestamp) -> tuple[str | None, pd.DataFrame | None]:
    """
    우선순위 심볼 배열에 대해: 로컬 → yfinance 순으로 첫 성공 DF 반환.
    """
    for s in symbols:
        df = _read_local(s, start, end)
        if len(df) > 0:
            return s, df
        df = _read_yf(s, start, end)
        if len(df) > 0:
            return s, df
    return None, None


# ----------------------------
# 공개 함수: trading_days_cached_or_build
# ----------------------------
def build_calendar(start: str, end: str) -> pd.DatetimeIndex:
    """
    calendar_symbol_priority()에 정의된 우선순위 심볼을 사용해
    일봉 인덱스를 가져와 거래일 DatetimeIndex를 생성.
    실패 시 RuntimeError("No objects to concatenate")로 신호.
    """
    start_ts = pd.to_datetime(start).tz_localize(None).normalize()
    end_ts   = pd.to_datetime(end).tz_localize(None).normalize()

    symbols = calendar_symbol_priority()  # 예: ["069500.KS","069500"]
    _, df = _first_available_df(symbols, start_ts, end_ts)
    if df is None or len(df) == 0:
        # 배치 프리체크에서 이 메시지를 그대로 사용하므로 유지
        raise RuntimeError("No objects to concatenate")

    idx = pd.to_datetime(df.index).tz_localize(None).normalize()
    idx = pd.DatetimeIndex(sorted(pd.unique(idx)))
    return idx


def trading_days_cached_or_build(asof: str | None = None) -> pd.DatetimeIndex:
    """
    1) 캐시(trading_days.pkl)가 유효하면 그대로 반환
    2) 없거나 비정상이면 asof 기준 과거 2년~asof로 새로 빌드
    """
    # 캐시 우선
    try:
        idx = pd.read_pickle(OUTP)
        if isinstance(idx, pd.DatetimeIndex) and len(idx) > 0:
            return idx
    except Exception:
        pass

    # 재빌드
    end = pd.to_datetime(asof or pd.Timestamp.today()).tz_localize(None).normalize()
    start = (end - pd.DateOffset(years=2)).normalize()
    idx = build_calendar(start.isoformat(), end.isoformat())

    pd.to_pickle(idx, OUTP)
    print(f"[CAL] wrote {OUTP} (n={len(idx)}, {idx.min().date()}~{idx.max().date()})")
    return idx


# ----------------------------
# CLI 진입점
# ----------------------------
def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Build/refresh KRX trading-days cache")
    ap.add_argument("--start", default=(date.today().replace(month=1, day=1) - timedelta(days=365)).isoformat())
    ap.add_argument("--end",   default=date.today().isoformat())
    args = ap.parse_args()

    try:
        idx = build_calendar(args.start, args.end)
        if len(idx) == 0:
            print("[CAL] no data -> exit 2 (retry)")
            return 2
        pd.to_pickle(idx, OUTP)
        print(f"[CAL] wrote {OUTP} (n={len(idx)}, {idx.min().date()}~{idx.max().date()})")
        return 0
    except RuntimeError as e:
        if "No objects to concatenate" in str(e):
            print("[CAL] source empty -> exit 2 (retry)")
            return 2
        raise


if __name__ == "__main__":
    sys.exit(main())
