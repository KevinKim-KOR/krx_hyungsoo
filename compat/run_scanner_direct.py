#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run KRX scanner directly (bypass app.py subcommand) with robust adapters.

- Reads config from config/config.yaml (or ./config.yaml).
- Patches:
    * scanner.load_cfg / scanner.get_effective_cfg (cfg 시그니처 불일치 해소)
    * krx_helpers.get_ohlcv_safe (비재귀, 재시도/백오프)
    * scanner.get_universe_codes (DB우회: SPoT/file 기반)
- Builds effective cfg with root-level keys (regime.sma_days, regime.spx_ticker).
- Calls scanner.recommend_buy_sell(asof=today, cfg=effective_cfg).
- Writes CSV to data/output/scanner_latest.csv.
- Optionally sends Telegram.

Tokens: [RUN]/[TRY]/[INFO]/[SKIP]/[DONE]/[EXIT]
"""
import os, sys, time, random, datetime, traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ROOT)  # repo root
os.chdir(ROOT)

def log(msg: str):
    print(msg, flush=True)

def _ensure_dict(x):
    try:
        import collections
        if isinstance(x, dict):
            return x
        if isinstance(x, collections.abc.Mapping):
            return dict(x)
    except Exception:
        pass
    return {} if x is None else (x if isinstance(x, dict) else {})

def _read_yaml_default():
    import yaml
    for p in ("config/config.yaml","config.yaml"):
        if os.path.isfile(p):
            with open(p,"r",encoding="utf-8") as f:
                return _ensure_dict(yaml.safe_load(f) or {})
    return {}

def _read_data_sources():
    import yaml
    p = "config/data_sources.yaml"
    if os.path.isfile(p):
        with open(p,"r",encoding="utf-8") as f:
            return _ensure_dict(yaml.safe_load(f) or {})
    return {}

def _patch_scanner_namespace():
    import scanner

    def load_cfg_compat(*args, **kwargs):
        if "cfg" in kwargs and kwargs["cfg"] is not None:
            return _ensure_dict(kwargs["cfg"])
        if len(args) >= 2 and args[1] is not None:
            return _ensure_dict(args[1])
        if len(args) >= 1 and isinstance(args[0], dict):
            return _ensure_dict(args[0])
        return {}

    def get_effective_cfg_compat(asof=None, cfg=None):
        return load_cfg_compat(cfg)

    scanner.load_cfg = load_cfg_compat
    scanner.get_effective_cfg = get_effective_cfg_compat

def _patch_helpers_namespace():
    import pandas as pd, requests, yfinance as yf
    import krx_helpers as KH

    def _is_transient(msg: str) -> bool:
        msg = (msg or "").lower()
        keys = ["429", "rate", "temporar", "timeout", "timed out",
                "name or service not known", "temporary failure",
                "connection reset", "network is unreachable"]
        return any(k in msg for k in keys)

    def get_ohlcv_safe_nonrec(ticker: str, start, end, retry=3, base_backoff=2, delay=0.6, jitter=0.6, timeout=20):
        try:
            if isinstance(start, (pd.Timestamp, )):
                start = start.date()
            if isinstance(end, (pd.Timestamp, )):
                end = end.date()
            session = requests.Session()
            t = yf.Ticker(ticker, session=session)
            last_err = None
            for attempt in range(1, retry + 1):
                try:
                    df = t.history(start=start, end=end, auto_adjust=False, timeout=timeout)
                    if df is None or df.empty:
                        raise RuntimeError("empty")
                    # Normalize columns
                    cols = {c.lower(): c for c in df.columns}
                    need = ["open","high","low","close","volume"]
                    if not all(k in cols for k in need):
                        df = df.rename(columns={v: v.title() for v in df.columns})
                    return df
                except Exception as e:
                    last_err = e
                    if attempt < retry and _is_transient(str(e)):
                        sleep_s = base_backoff * (2 ** (attempt - 1))
                        log(f"[TRY] get_ohlcv {ticker} attempt={attempt} backoff={sleep_s}s")
                        time.sleep(sleep_s)
                        continue
                    break
            log(f"[SKIP] ohlcv_fetch_failed ticker={ticker} err={last_err}")
            return pd.DataFrame()
        finally:
            time.sleep(delay + random.uniform(0, jitter))

    KH.get_ohlcv_safe = get_ohlcv_safe_nonrec

def _load_universe_from_file(path):
    tickers = []
    try:
        with open(path,"r",encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith("#"):
                    tickers.append(s)
    except Exception as e:
        log(f"[WARN] universe_file_read_failed: {e}")
    return tickers

def _get_universe_codes_safe(cfg):
    """
    DB 대신 SPoT/file에서 유니버스 로드:
      1) config/data_sources.yaml 의 yf.universe_key 를 찾아 data/universe/<key>.txt
      2) config/scanner.yaml 의 universe.file_fallback
      3) config/scanner.yaml 의 universe.inline 리스트
    """
    cfg = _ensure_dict(cfg)
    ds = _read_data_sources()

    # 1) SPoT: data_sources.yaml → yf.universe_key
    yf_src = _ensure_dict(ds.get("yf"))
    key = yf_src.get("universe_key") or "yf_universe"
    path1 = os.path.join("data","universe", f"{key}.txt")
    if os.path.isfile(path1):
        codes = _load_universe_from_file(path1)
        if codes:
            log(f"[INFO] universe_spot key={key} size={len(codes)}")
            return codes

    # 2) scanner.yaml file_fallback
    scn = _ensure_dict(cfg.get("scanner"))
    uni = _ensure_dict(scn.get("universe") or cfg.get("universe"))
    file_fb = uni.get("file_fallback") or os.path.join("data","universe","yf_universe.txt")
    if os.path.isfile(file_fb):
        codes = _load_universe_from_file(file_fb)
        if codes:
            log(f"[INFO] universe_file_fallback path={file_fb} size={len(codes)}")
            return codes

    # 3) inline
    inline = uni.get("inline") or []
    if inline:
        log(f"[INFO] universe_inline size={len(inline)}")
        return list(inline)

    log("[SKIP] universe_missing (no SPoT/file/inline)")
    return []

def _patch_universe_namespace():
    """scanner.get_universe_codes 를 파일/SPoT 기반 안전구현으로 치환"""
    import scanner
    def get_universe_codes_safe(session_unused, cfg):
        return _get_universe_codes_safe(cfg)
    scanner.get_universe_codes = get_universe_codes_safe

def _build_effective_cfg(raw_cfg):
    cfg = _ensure_dict(raw_cfg).copy()
    scn = _ensure_dict(cfg.get("scanner"))
    for k in ("regime", "threshold", "universe", "output", "runtime"):
        if k not in cfg and k in scn:
            cfg[k] = _ensure_dict(scn[k])

    regime = _ensure_dict(cfg.get("regime"))
    if "sma_days" not in regime:
        regime["sma_days"] = 20
    if "spx_ticker" not in regime:
        regime["spx_ticker"] = "^GSPC"
    cfg["regime"] = regime
    return cfg

def _send_telegram(text: str):
    import requests
    tok = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        log("[INFO] telegram_env_missing → skip push")
        return False
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    r = requests.post(url, data={"chat_id": chat, "text": text, "disable_notification": True}, timeout=10)
    ok = r.ok and r.json().get("ok")
    log("[INFO] telegram_sent" if ok else f"[WARN] telegram_failed status={r.status_code} body={r.text}")
    return ok

def main():
    import pandas as pd, scanner
    log(f"[RUN] scanner {datetime.datetime.now():%F %T}")

    raw_cfg = _read_yaml_default()
    _patch_scanner_namespace()   # cfg 시그니처 호환
    _patch_helpers_namespace()   # OHLCV 안전 패치
    _patch_universe_namespace()  # 유니버스: DB우회 → SPoT/파일/인라인

    eff_cfg = _build_effective_cfg(raw_cfg)

    # 출력/푸시 옵션 (scanner: 섹션 우선)
    scn = _ensure_dict(raw_cfg.get("scanner"))
    out_csv = (scn.get("output", {}) if "output" in scn else raw_cfg.get("output", {})).get("csv", "data/output/scanner_latest.csv")
    send_tg = bool((scn.get("output", {}) if "output" in scn else raw_cfg.get("output", {})).get("send_telegram", True))

    asof = pd.Timestamp.today().normalize()

    try:
        buy_df, sell_df, meta = scanner.recommend_buy_sell(asof=asof, cfg=eff_cfg)
    except Exception as e:
        log(f"[EXIT 2] recommend_buy_sell_error: {e}\n{traceback.format_exc()}")
        sys.exit(2)

    # 저장
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    try:
        frames = []
        if buy_df is not None and not buy_df.empty:
            t = buy_df.copy(); t["__side__"]="BUY"; frames.append(t)
        if sell_df is not None and not sell_df.empty:
            t = sell_df.copy(); t["__side__"]="SELL"; frames.append(t)
        import pandas as pd
        out = pd.concat(frames, sort=False) if frames else pd.DataFrame()
        out.to_csv(out_csv, index=False)
        log(f"[INFO] wrote {out_csv} rows={len(out)}")
    except Exception as e:
        log(f"[WARN] save_csv_failed: {e}")

    # 텔레그램(옵션)
    if send_tg:
        try:
            n_buy = 0 if buy_df is None else len(buy_df)
            n_sell = 0 if sell_df is None else len(sell_df)
            msg = f"[scanner] {asof.date()} buy={n_buy} sell={n_sell}"
            _send_telegram(msg)
        except Exception as e:
            log(f"[WARN] telegram_error: {e}")

    log(f"[DONE] scanner {datetime.datetime.now():%F %T}")
    sys.exit(0)

if __name__ == "__main__":
    main()
