#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, argparse, datetime, traceback, inspect

def log(msg: str): print(msg, flush=True)

PREFERRED_NAMES = [
    "run_cron","cron","run","main",
    "send_signals","generate_and_send",
    "send_all","send_summary","emit","notify","push"
]

def _is_plain_callable(obj):
    # 함수/메서드만 허용(클래스/타입/모듈 제외)
    return inspect.isfunction(obj) or inspect.ismethod(obj)

def _is_compatible(fn):
    """
    선택 기준:
    - mode 외에 추가 '필수(positional, default 없음)' 인자가 없어야 함
    - *args 또는 **kwargs 있으면 허용
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    has_varargs = any(p.kind == p.VAR_POSITIONAL for p in sig.parameters.values())
    has_varkw  = any(p.kind == p.VAR_KEYWORD   for p in sig.parameters.values())
    if has_varargs or has_varkw:
        return True
    for name, p in sig.parameters.items():
        if name == "mode":
            continue
        # 위치/키워드 인자이면서 기본값 없음 => 필수 인자 → 불가
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) and p.default is inspect._empty:
            return False
    return True

def _call_fn(fn, mode: str):
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        fn(); return
    if "mode" in sig.parameters:
        fn(mode=mode)
    else:
        fn()

def try_call_business(mode: str) -> bool:
    try:
        from signals import service  # 사용자 비즈니스 모듈
    except Exception:
        return False

    # 1) 이름 우선순위에서 호환 가능한 함수 선택
    for name in PREFERRED_NAMES:
        fn = getattr(service, name, None)
        if fn and _is_plain_callable(fn) and _is_compatible(fn):
            log(f"[INFO] using signals.service.{name}()")
            _call_fn(fn, mode)
            return True

    # 2) 자동 탐색: public 함수 중 호환 가능한 것만
    candidates = []
    for n in dir(service):
        if n.startswith("_"):  # private 제외
            continue
        obj = getattr(service, n)
        if _is_plain_callable(obj) and _is_compatible(obj):
            candidates.append((n, obj))
    if candidates:
        candidates.sort(key=lambda x: x[0])  # 이름순 안정성
        name, fn = candidates[0]
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
        log("[SKIP] no_business_logic_found (use --force or add compatible entry in signals/service.py)")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        log(f"[EXIT 2] signals_error: {e}\n{traceback.format_exc()}"); sys.exit(2)

if __name__ == "__main__":
    main()
