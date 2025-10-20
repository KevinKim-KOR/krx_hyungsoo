#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run KRX scanner directly (bypass app.py subcommand) with robust config adapters.

- Reads config from config/config.yaml (or ./config.yaml) as SPoT link.
- Patches scanner.load_cfg and scanner.get_effective_cfg at module namespace.
- Builds an effective cfg that provides root-level keys expected by scanner.py
  (e.g., cfg["regime"]) with safe defaults if missing.
- Calls scanner.recommend_buy_sell(asof=today, cfg=effective_cfg).
- Writes CSV to data/output/scanner_latest.csv.
- Optionally sends Telegram if config says so.

Standard log tokens: [RUN]/[INFO]/[DONE]/[EXIT]
"""
import os, sys, datetime, traceback

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
    import scanner, pandas as pd

    def load_cfg_compat(*args, **kwargs):
        # Accept (asof,cfg) | (cfg) | ()
        if "cfg" in kwargs and kwargs["cfg"] is not None:
            return _ensure_dict(kwargs["cfg"])
        if len(args) >= 2 and args[1] is not None:
            return _ensure_dict(args[1])
        if len(args) >= 1 and isinstance(args[0], dict):
            return _ensure_dict(args[0])
        return {}

    def get_effective_cfg_compat(asof=None, cfg=None):
        # Ignore asof for config materialization; return dict cfg
        try:
            import pandas as pd  # noqa
            if asof is not None:
                pd.to_datetime(asof)
        except Exception:
            pass
        return load_cfg_compat(cfg)

    # Install into module globals (overwrite)
    scanner.load_cfg = load_cfg_compat
    scanner.get_effective_cfg = get_effective_cfg_compat

def _build_effective_cfg(raw_cfg):
    """
    scanner.py가 기대하는 루트 키들을 보장:
      - regime: { sma_days: int }  (없으면 기본값 주입)
    또한 config가 scanner: {...} 아래에 있을 때 루트로 승격.
    """
    cfg = _ensure_dict(raw_cfg).copy()

    # 1) scanner: 섹션 내 하위 키들을 루트로 승격(없으면 무시)
    scn = _ensure_dict(cfg.get("scanner"))
    for k in ("regime", "threshold", "universe", "output", "runtime"):
        if k not in cfg and k in scn:
            cfg[k] = _ensure_dict(scn[k])

    # 2) regime 기본값 보강 (루트 기준)
    regime = _ensure_dict(cfg.get("regime"))
    if "sma_days" not in regime:
        regime["sma_days"] = 20  # 안전 기본값
    if "spx_ticker" not in regime:
        regime["spx_ticker"] = "^GSPC"   # ← 이 줄 추가
    cfg["regime"] = regime

    return cfg

def _send_telegram(text: str):
    import os, requests
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

    # Load config once (SPoT: config/config.yaml symlink)
    raw_cfg = _read_yaml_default()
    # Patch scanner namespace to neutralize signature mismatch
    _patch_scanner_namespace()
    # Build effective cfg (root-level keys guaranteed)
    eff_cfg = _build_effective_cfg(raw_cfg)

    # 파생 설정: 출력/푸시 옵션은 scanner: 섹션/루트 둘 다 지원
    scn = _ensure_dict(raw_cfg.get("scanner"))
    out_csv = (scn.get("output", {}) if "output" in scn else raw_cfg.get("output", {})).get("csv", "data/output/scanner_latest.csv")
    send_tg = bool((scn.get("output", {}) if "output" in scn else raw_cfg.get("output", {})).get("send_telegram", True))

    # asof: 오늘(로컬)
    asof = pd.Timestamp.today().normalize()

    try:
        buy_df, sell_df, meta = scanner.recommend_buy_sell(asof=asof, cfg=eff_cfg)
    except Exception as e:
        log(f"[EXIT 2] recommend_buy_sell_error: {e}\n{traceback.format_exc()}")
        sys.exit(2)

    # Save output
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    try:
        import pandas as pd
        frames = []
        if buy_df is not None and not buy_df.empty:
            t = buy_df.copy(); t["__side__"]="BUY"; frames.append(t)
        if sell_df is not None and not sell_df.empty:
            t = sell_df.copy(); t["__side__"]="SELL"; frames.append(t)
        out = pd.concat(frames, sort=False) if frames else pd.DataFrame()
        out.to_csv(out_csv, index=False)
        log(f"[INFO] wrote {out_csv} rows={len(out)}")
    except Exception as e:
        log(f"[WARN] save_csv_failed: {e}")

    # Telegram (optional & quiet)
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
