#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
signals entrypoint
- tries to call existing business logic in signals.service if available
- if not found, can send a heartbeat when --force is given (for wiring test)
- emits standard log tokens: [RUN]/[SKIP]/[DONE]/[EXIT]
"""
import os, sys, argparse, datetime, traceback

def log(msg: str):
    print(msg, flush=True)

def try_call_business(mode: str) -> bool:
    """
    Try to call user's business functions in signals.service.
    Returns True if something was actually invoked, False if nothing matched.
    """
    try:
        from signals import service  # type: ignore
    except Exception:
        return False

    # candidate callables by convention
    candidates = [
        ("run_cron", {"mode": mode}),
        ("cron", {"mode": mode}),
        ("run", {"mode": mode}),
        ("main", {"mode": mode}),
        ("send_signals", {"mode": mode}),
        ("generate_and_send", {"mode": mode}),
    ]
    for name, kwargs in candidates:
        fn = getattr(service, name, None)
        if callable(fn):
            log(f"[INFO] using signals.service.{name}()")
            fn(**kwargs) if kwargs else fn()
            return True
    return False

def send_heartbeat() -> None:
    import requests
    tok = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        log("[SKIP] heartbeat_missing_env")
        return
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    text = f"[heartbeat] {os.uname().nodename} {datetime.datetime.now():%F %T}"
    r = requests.post(url, data={
        "chat_id": chat,
        "text": text,
        "disable_notification": True
    }, timeout=10)
    if r.ok and r.json().get("ok"):
        log("[INFO] heartbeat_sent")
    else:
        log(f"[WARN] heartbeat_failed status={r.status_code} body={r.text}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="cron")
    ap.add_argument("--force", action="store_true", help="send heartbeat if no business logic found")
    args = ap.parse_args()

    log(f"[RUN] signals {datetime.datetime.now():%F %T} mode={args.mode}")

    try:
        # 1) 사용자 로직 시도
        if try_call_business(args.mode):
            log("[DONE] signals")
            sys.exit(0)

        # 2) 엔트리 미구현: 강제(옵션)일 때만 하트비트 전송
        if args.force:
            send_heartbeat()
            log("[DONE] signals (force-heartbeat)")
            sys.exit(0)
        else:
            log("[SKIP] no_business_logic_found (use --force for heartbeat)")
            sys.exit(0)

    except SystemExit:
        raise
    except Exception as e:
        log(f"[EXIT 2] signals_error: {e}\n{traceback.format_exc()}")
        sys.exit(2)

if __name__ == "__main__":
    main()
