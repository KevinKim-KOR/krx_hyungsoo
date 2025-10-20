#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, argparse, datetime, traceback, inspect, types

def log(msg: str): print(msg, flush=True)

PREFERRED_NAMES = [
    "run_cron","cron","run","main",
    "send_signals","generate_and_send",
    "send_all","send_summary","emit","notify","push"
]

def _is_callable_function(obj):
    """Return True only for plain functions or bound methods (exclude classes/types/typing)."""
    if inspect.isfunction(obj) or inspect.ismethod(obj):
        return True
    return False  # exclude classes, modules, typing aliases, etc.

def _call_fn(fn, mode: str):
    sig = None
    try:
        sig = inspect.signature(fn)
    except (ValueError, TypeError):
        pass
    if sig and "mode" in sig.parameters:
        fn(mode=mode)
    else:
        fn()

def try_call_business(mode: str) -> bool:
    try:
        from signals import service  # noqa
    except Exception:
        return False

    # 1) 우선순위 이름 매핑 (함수/메서드만)
    for name in PREFERRED_NAMES:
        fn = getattr(service, name, None)
        if fn and _is_callable_function(fn):
            log(f"[INFO] using signals.service.{name}()")
            _call_fn(fn, mode)
            return True

    # 2) 자동탐색: service 내 public 함수/메서드만
    cands = []
    for n in dir(service):
        if n.startswith("_"):
            continue
        obj = getattr(service, n)
        if _is_callable_function(obj):
            cands.append((n, obj))

    if cands:
        cands.sort(key=lambda x: x[0])  # 이름순 안정 선택
        name, fn = cands[0]
        log(f"[INFO] using signals.service.{name}() (auto-picked)")
        _call_fn(fn, mode)
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
