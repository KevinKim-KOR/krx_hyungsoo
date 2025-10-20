#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, argparse, datetime, traceback, inspect

def log(msg: str): print(msg, flush=True)

PREFERRED_NAMES = [
    "run_cron","cron","run","main",
    "send_signals","generate_and_send",
    "send_all","send_summary","emit","notify","push"
]

def try_call_business(mode: str) -> bool:
    try:
        from signals import service  # noqa
    except Exception:
        return False

    # 1) 우선순위 이름 매핑
    for name in PREFERRED_NAMES:
        fn = getattr(service, name, None)
        if callable(fn):
            log(f"[INFO] using signals.service.{name}()")
            try:
                fn(mode=mode) if "mode" in inspect.signature(fn).parameters else fn()
            except TypeError:
                fn()  # 인자 불일치시 무인자 호출
            return True

    # 2) 마지막 수단: service 모듈 내 public callable 자동탐색
    cands = [(n, getattr(service, n)) for n in dir(service)
             if not n.startswith("_") and callable(getattr(service, n))]
    if cands:
        name, fn = sorted(cands)[0]
        log(f"[INFO] using signals.service.{name}() (auto-picked)")
        try:
            fn(mode=mode) if "mode" in inspect.signature(fn).parameters else fn()
        except TypeError:
            fn()
        return True

    return False

def send_heartbeat():
    import requests
    tok = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        log("[SKIP] heartbeat_missing_env"); return
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    text = f"[heartbeat] {os.uname().nodename} {datetime.datetime.now():%F %T}"
    r = requests.post(url, data={"chat_id": chat, "text": text, "disable_notification": True}, timeout=10)
    if r.ok and r.json().get("ok"): log("[INFO] heartbeat_sent")
    else: log(f"[WARN] heartbeat_failed status={r.status_code} body={r.text}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="cron")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    log(f"[RUN] signals {datetime.datetime.now():%F %T} mode={args.mode}")
    try:
        if try_call_business(args.mode):
            log("[DONE] signals"); sys.exit(0)
        if args.force:
            send_heartbeat(); log("[DONE] signals (force-heartbeat)"); sys.exit(0)
        log("[SKIP] no_business_logic_found (use --force or add entry in signals/service.py)")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        log(f"[EXIT 2] signals_error: {e}\n{traceback.format_exc()}"); sys.exit(2)

if __name__ == "__main__":
    main()
