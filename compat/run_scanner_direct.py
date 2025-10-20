#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run KRX scanner directly (bypass app.py subcommand) with robust adapters.

- Reads config from config/config.yaml (or ./config.yaml).
- Patches scanner.load_cfg / scanner.get_effective_cfg (cfg 시그니처 불일치 해소).
- Patches krx_helpers.get_ohlcv_safe to a non-recursive, rate-limit-friendly fetcher.
- Builds an effective cfg that guarantees root-level keys (e.g., cfg['regime']).
- Calls scanner.recommend_buy_sell(asof=today, cfg=effective_cfg).
- Writes CSV to data/output/scanner_latest.csv.
- Optionally sends Telegram if config says so.

Standard log tokens: [RUN]/[TRY]/[INFO]/[SKIP]/[DONE]/[EXIT]
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
        # asof는 무시하고 cfg만 실체화
        return load_cfg_compat(cfg)

    scanner.load_cfg = load_cfg_compat
    scanner.get_effective_cfg = get_effective_cfg_compat

def _patch_helpers_namespace():
    """
    krx_helpers.get_ohlcv_safe 를 비재귀 안전 구현으로 교체.
    - yfinance 단건 history() 사용
    - 재시도 + 지수백오프 + 지연(jitter)
    - 실패 시 빈 DataFrame 반환 (외부요인 SKIP)
    """
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
            import datetime as dt
            # 날짜 정규화
            if isinstance(start, (pd.Timestamp, )):
                start = start.date()
            if isinstance(end, (pd.Timestamp, )):
                end = end.date()
            # 세션 재사용
            session = requests.Session()
            t = yf.Ticker(ticker, session=session)

            last_err = None
            for attempt in range(1, retry + 1):
                try:
                    df = t.history(start=start, end=end, auto_adjust=False, timeout=timeout)
                    # 기대 형식 보정
                    if df is None or df.empty:
                        raise RuntimeError("empty")
                    # 컬럼 표준화(Open, High, Low, Close, Volume 보장)
                    cols = {c.lower(): c for c in df.columns}
                    need = ["open","high","low","close","volume"]
                    if not all(k in cols for k in need):
                        # yfinance는 대소문자 섞임 방지
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
            # 모두 실패
            log(f"[SKIP] ohlcv_fetch_failed ticker={ticker} err={last_err}")
            return pd.DataFrame()
        finally:
            # inter-request delay + jitter
            time.sleep(delay + random.uniform(0, jitter))

    # 모듈 전역에 주입(재귀 방지)
    KH.get_ohlcv_safe = get_ohlcv_safe_nonrec

def _build_effective_cfg(raw_cfg):
    """
    scanner.py가 기대하는 루트 키 보장:
      cfg['regime']['sma_days'], cfg['regime']['spx_ticker']
    scanner: 섹션에만 있으면 루트로 승격
    """
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
    _patch_helpers_namespace()   # OHLCV 안전 패치(비재귀)

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
