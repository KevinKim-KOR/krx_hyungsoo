#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hybrid yfinance ingest runner
- bulk download first, then per-ticker retries for failed ones
- writes safe artifact to data/tmp/ingest_last.parquet (does not alter existing caches/DB)
- controlled by config/data_sources.yaml (yf.*)
"""
import os, sys, time, random, json, traceback
from datetime import datetime, date
from typing import List, Tuple

LOGFMT_TS = "%Y-%m-%d %H:%M:%S"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root/ingest/..
os.chdir(ROOT)

def log(msg: str):
    print(msg, flush=True)

def read_yaml(path: str):
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def read_universe_from_files(key: str) -> List[str]:
    # 1) data/universe/<key>.txt
    p_txt = os.path.join("data", "universe", f"{key}.txt")
    if os.path.isfile(p_txt):
        with open(p_txt, "r", encoding="utf-8") as f:
            arr = [x.strip() for x in f if x.strip()]
        if arr: return arr

    # 2) config/data_sources.yaml -> universe.tickers
    cfg = read_yaml(os.path.join("config", "data_sources.yaml"))
    u = (cfg.get("universe") or {}).get("tickers")
    if isinstance(u, list) and u:
        return [str(x).strip() for x in u if str(x).strip()]

    # 3) config/data_sources.yaml -> yf.tickers
    yft = (cfg.get("yf") or {}).get("tickers")
    if isinstance(yft, list) and yft:
        return [str(x).strip() for x in yft if str(x).strip()]

    return []

def get_yf_cfg():
    cfg = read_yaml(os.path.join("config", "data_sources.yaml"))
    yfc = cfg.get("yf") or {}
    # defaults
    mode = str(yfc.get("mode", "bulk")).lower()
    universe_key = yfc.get("universe_key", "yf_universe")
    pt = yfc.get("per_ticker") or {}
    net = yfc.get("net") or {}
    return {
        "mode": mode,
        "universe_key": universe_key,
        "pt": {
            "delay": float(pt.get("delay_sec", 1.2)),
            "jitter": float(pt.get("jitter_sec", 0.6)),
            "retry": int(pt.get("retry", 3)),
            "backoff_base": int(pt.get("backoff_base_sec", 2)),
            "timeout": int(pt.get("timeout_sec", 25)),
            "max_fail_ratio": float(pt.get("max_fail_ratio", 0.2)),
        },
        "net": {
            "session_reuse": bool(net.get("session_reuse", True))
        }
    }

def save_artifact(df):
    os.makedirs("data/tmp", exist_ok=True)
    outp = os.path.join("data", "tmp", "ingest_last.parquet")
    try:
        df.to_parquet(outp, index=True)
        log(f"[DONE] artifact written: {outp} rows={len(df)}")
    except Exception as e:
        log(f"[WARN] failed to write parquet: {e}. try csv fallback.")
        outc = os.path.join("data", "tmp", "ingest_last.csv")
        df.to_csv(outc, index=True)
        log(f"[DONE] artifact written: {outc} rows={len(df)}")

def bulk_download(tickers: List[str]):
    import pandas as pd
    import yfinance as yf
    # 1일분만 최신 종가 확보 목적
    df = yf.download(
        tickers=tickers, period="5d", interval="1d", group_by="ticker",
        auto_adjust=False, progress=False, threads=True
    )
    # 정규화: 멀티인덱스/다중컬럼 상황 대비
    # 결과를 (ticker, date, ...) 단일 테이블로 펴기
    if isinstance(df.columns, pd.MultiIndex):
        parts = []
        for t in tickers:
            if t in df.columns.levels[0]:
                sub = df[t].copy()
                sub["ticker"] = t
                parts.append(sub)
        if parts:
            df2 = pd.concat(parts)
        else:
            df2 = pd.DataFrame()
    else:
        # 단일컬럼 구조일 가능성 (단일 티커)
        df2 = df.copy()
        df2["ticker"] = tickers[0] if tickers else ""
    # 최신일의 결측/비어있음 탐지
    return df2

def per_ticker_fetch(tickers: List[str], pt_cfg) -> Tuple["pd.DataFrame", List[str]]:
    import pandas as pd, yfinance as yf, requests
    session = requests.Session() if pt_cfg["retry"] > 0 else None
    got = []
    failed = []
    for i, t in enumerate(tickers):
        success = False
        for attempt in range(1, pt_cfg["retry"] + 1):
            try:
                if session:
                    tk = yf.Ticker(t, session=session)
                else:
                    tk = yf.Ticker(t)
                df = tk.history(period="5d", auto_adjust=False, timeout=pt_cfg["timeout"])
                if not df.empty and not df.iloc[-1].isnull().any():
                    df = df.copy()
                    df["ticker"] = t
                    got.append(df)
                    success = True
                    break
            except Exception as e:
                # 분류: 레이트리밋/네트워크만 재시도, 기타는 즉시 실패
                msg = str(e)
                transient = any(s in msg for s in [
                    "429", "rate", "temporarily", "timed out", "Read timed out",
                    "Name or service not known", "Temporary failure in name resolution",
                    "Connection reset by peer"
                ])
                if not transient:
                    break
            # backoff
            sleep_s = pt_cfg["backoff_base"] * (2 ** (attempt - 1))
            log(f"[TRY] {t} attempt={attempt} backoff={sleep_s}s")
            time.sleep(sleep_s)
        if not success:
            failed.append(t)
        # inter-request delay + jitter
        delay = pt_cfg["delay"] + random.uniform(0, pt_cfg["jitter"])
        time.sleep(delay)
    if got:
        return pd.concat(got), failed
    else:
        return pd.DataFrame(), failed

def run():
    import pandas as pd
    log(f"[RUN] ingest {datetime.now().strftime(LOGFMT_TS)}")

    yf_cfg = get_yf_cfg()
    mode = yf_cfg["mode"]
    uni_key = yf_cfg["universe_key"]
    tickers = read_universe_from_files(uni_key)

    if not tickers:
        log("[SKIP] no_tickers_found (data/universe/*.txt or config/* list)")
        sys.exit(0)

    log(f"[INFO] mode={mode} universe={len(tickers)} tickers")

    if mode == "bulk":
        try:
            df = bulk_download(tickers)
            save_artifact(df)
            log(f"[DONE] ingest {datetime.now().strftime(LOGFMT_TS)}")
            sys.exit(0)
        except Exception as e:
            log(f"[EXIT 2] bulk_error: {e}")
            sys.exit(2)

    elif mode == "per_ticker":
        df, failed = per_ticker_fetch(tickers, yf_cfg["pt"])
        fail_ratio = (len(failed) / max(1, len(tickers)))
        if df.empty and fail_ratio > 0:
            log(f"[SKIP] per_ticker_failed fail_ratio={fail_ratio:.2f}")
            sys.exit(0)
        save_artifact(df)
        log(f"[INFO] per_ticker_failed={len(failed)} ratio={fail_ratio:.2f}")
        if fail_ratio > yf_cfg["pt"]["max_fail_ratio"]:
            log("[SKIP] external_issue_after_retries")
            sys.exit(0)
        log(f"[DONE] ingest {datetime.now().strftime(LOGFMT_TS)}")
        sys.exit(0)

    else:  # hybrid (default)
        # 1) bulk 시도
        df_bulk = None
        try:
            df_bulk = bulk_download(tickers)
        except Exception as e:
            log(f"[WARN] bulk_failed: {e}")

        # 2) 누락/결측 티커만 per_ticker
        need = set()
        if df_bulk is None:
            need = set(tickers)
        else:
            # 최신일 기준으로 빈/결측 티커 선별
            try:
                last_day = df_bulk.index.get_level_values(0).max() if isinstance(df_bulk.index, pd.MultiIndex) else df_bulk.index.max()
            except Exception:
                last_day = None
            present = set(str(x) for x in getattr(df_bulk, "ticker", pd.Series([], dtype=str)).astype(str).unique())
            need = set(tickers) - present

        if need:
            log(f"[INFO] per_ticker_recover count={len(need)}")
            df_pt, failed = per_ticker_fetch(sorted(list(need)), yf_cfg["pt"])
        else:
            df_pt, failed = None, []

        # 3) 병합 후 산출
        import pandas as pd
        dfs = []
        if df_bulk is not None and not df_bulk.empty: dfs.append(df_bulk)
        if df_pt is not None and not df_pt.empty: dfs.append(df_pt)
        if dfs:
            df_all = pd.concat(dfs, sort=False)
            save_artifact(df_all)
        else:
            log("[SKIP] no_data_after_hybrid")
            sys.exit(0)

        fail_ratio = (len(failed) / max(1, len(tickers))) if failed is not None else 0.0
        log(f"[INFO] hybrid_failed={len(failed)} ratio={fail_ratio:.2f}")
        if fail_ratio > yf_cfg["pt"]["max_fail_ratio"]:
            log("[SKIP] external_issue_after_retries")
            sys.exit(0)

        log(f"[DONE] ingest {datetime.now().strftime(LOGFMT_TS)}")
        sys.exit(0)

if __name__ == "__main__":
    try:
        run()
    except SystemExit as se:
        raise
    except Exception as e:
        log(f"[EXIT 2] unhandled_error: {e}\n{traceback.format_exc()}")
        sys.exit(2)
