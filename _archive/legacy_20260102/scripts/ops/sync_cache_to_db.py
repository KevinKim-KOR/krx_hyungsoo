#!/usr/bin/env python3
"""
Sync parquet cache (data/cache/ohlcv/*.parquet) into a local SQLite DB:
  data/db/prices.sqlite  -> table: price_daily

Schema:
  price_daily(
    symbol TEXT NOT NULL,
    date   TEXT NOT NULL,        -- YYYY-MM-DD
    open   REAL, high REAL, low REAL, close REAL,
    adj_close REAL, volume REAL,
    src    TEXT,                 -- provider tag (unknown if N/A)
    updated_at TEXT,             -- ISO timestamp
    PRIMARY KEY(symbol, date)
  )

Usage:
  python -m scripts.ops.sync_cache_to_db [--only SYMBOL1,SYMBOL2]
"""
from __future__ import annotations
import os, glob, sqlite3, sys
from pathlib import Path
from datetime import datetime
import pandas as pd

DB_PATH = Path("data/db/prices.sqlite")
TABLE   = "price_daily"
CACHE_GLOB = "data/cache/ohlcv/*.parquet"

def _ensure_db(conn: sqlite3.Connection):
    conn.execute(f"""
    CREATE TABLE IF NOT EXISTS {TABLE}(
      symbol TEXT NOT NULL,
      date   TEXT NOT NULL,
      open   REAL, high REAL, low REAL, close REAL,
      adj_close REAL, volume REAL,
      src    TEXT,
      updated_at TEXT,
      PRIMARY KEY(symbol, date)
    );
    """)
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_date ON {TABLE}(date);")
    conn.commit()

def _read_parquet(p: Path) -> pd.DataFrame | None:
    try:
        df = pd.read_parquet(p)
        if df.empty: return None
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        df.index = df.index.tz_localize(None)
        df = df.sort_index()
        # 표준 컬럼 정렬
        rename = {"Adj_Close":"Adj Close","AdjClose":"Adj Close"}
        df = df.rename(columns=rename)
        cols = {c: None for c in ["Open","High","Low","Close","Adj Close","Volume"]}
        for c in list(cols.keys()):
            if c not in df.columns: cols[c] = None
        # 없는 컬럼은 생성
        for c in cols:
            if c not in df.columns:
                df[c] = None
        return df[["Open","High","Low","Close","Adj Close","Volume"]]
    except Exception:
        return None

def _detect_src_from_meta(p: Path) -> str:
    # 간단 태그 추정 (폴더/파일명 정보만 사용)
    # 필요시 providers/ohlcv.py에서 별도 메타파일 생산 가능
    return "cache"

def upsert_symbol(conn: sqlite3.Connection, symbol: str, df: pd.DataFrame, src: str):
    # DataFrame -> records
    now = datetime.utcnow().isoformat(timespec="seconds")
    recs = []
    for dt, row in df.iterrows():
        recs.append((
            symbol,
            dt.strftime("%Y-%m-%d"),
            _f(row.get("Open")), _f(row.get("High")), _f(row.get("Low")), _f(row.get("Close")),
            _f(row.get("Adj Close")), _f(row.get("Volume")),
            src, now
        ))
    sql = f"""
    INSERT INTO {TABLE}(symbol,date,open,high,low,close,adj_close,volume,src,updated_at)
    VALUES(?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(symbol,date) DO UPDATE SET
      open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close,
      adj_close=excluded.adj_close, volume=excluded.volume, src=excluded.src, updated_at=excluded.updated_at;
    """
    conn.executemany(sql, recs)

def _f(x):
    try:
        v = float(x)
        if pd.isna(v): return None
        return v
    except Exception:
        return None

def main(only: list[str] | None = None) -> int:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        _ensure_db(conn)

        files = sorted(glob.glob(CACHE_GLOB))
        if only:
            # filter by symbol list
            keep = set(only)
            files = [p for p in files if Path(p).stem in keep]
        if not files:
            print("[SYNC] no parquet files found")
            return 2

        total_syms = 0
        for p in files:
            sym = Path(p).stem
            df = _read_parquet(Path(p))
            if df is None or df.empty:
                continue
            src = _detect_src_from_meta(Path(p))
            upsert_symbol(conn, sym, df, src)
            total_syms += 1
        conn.commit()

        # 로그/최신일 출력
        cur = conn.execute(f"SELECT MAX(date) FROM {TABLE}")
        mx = cur.fetchone()[0]
        print(f"[SYNC] upserted symbols={total_syms}, latest={mx}")
        return 0 if total_syms > 0 else 2
    finally:
        conn.close()

if __name__ == "__main__":
    only = None
    if len(sys.argv) >= 3 and sys.argv[1] == "--only":
        only = [x.strip() for x in sys.argv[2].split(",") if x.strip()]
    sys.exit(main(only))
