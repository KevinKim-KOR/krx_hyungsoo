#!/usr/bin/env python3
import os, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def load_secret():
    import yaml

    def _read_yaml(p):
        try:
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    y = {}
    # 우선순위: env > secret/notify.yaml > secret/config.yaml
    notify = ROOT / "secret" / "notify.yaml"
    config = ROOT / "secret" / "config.yaml"
    if notify.exists():
        y.update(_read_yaml(notify))
    if config.exists():
        # config.yaml 안쪽에도 telegram/slack 섹션이 있을 수 있음 → 덮어쓰기 X, 빈 곳만 채움
        y2 = _read_yaml(config)
        # 평면 키 또는 섹션 키 모두 허용
        for key in ("telegram", "slack"):
            y.setdefault(key, {})
            if key in y2 and isinstance(y2[key], dict):
                for k, v in y2[key].items():
                    y[key].setdefault(k, v)
        # 평면 키도 병합
        for k in ("telegram_bot_token", "telegram_chat_id", "slack_webhook_url"):
            if k in y2 and k not in y:
                y[k] = y2[k]

    # env 최우선
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or (y.get("telegram", {}) or {}).get("bot_token") or y.get("telegram_bot_token")
    chat_id   = os.getenv("TELEGRAM_CHAT_ID")  or (y.get("telegram", {}) or {}).get("chat_id")
    slack_wh  = os.getenv("SLACK_WEBHOOK_URL") or (y.get("slack", {}) or {}).get("webhook_url") or y.get("slack_webhook_url")

    return {
        "telegram_bot_token": bot_token,
        "telegram_chat_id":  chat_id,
        "slack_webhook":     slack_wh,
    }


def send_slack(webhook, text):
    import requests
    try:
        r = requests.post(webhook, json={"text": text}, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[NOTIFY] slack failed: {e}", file=sys.stderr)
        return False

def send_telegram(token, chat_id, text):
    import requests
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[NOTIFY] telegram failed: {e}", file=sys.stderr)
        return False

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="")
    ap.add_argument("--message", required=True)
    ap.add_argument("--channel", default="auto", choices=["auto","slack","telegram"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_secret()
    text = (args.title + "\n" if args.title else "") + args.message

    if args.dry_run:
        print(text)
        return 0

    sent = False
    # channel 우선순위
    chans = []
    if args.channel == "auto":
        # slack 우선 → 없으면 telegram
        if cfg.get("slack_webhook"): chans.append("slack")
        if cfg.get("telegram_bot_token") and cfg.get("telegram_chat_id"): chans.append("telegram")
    else:
        chans.append(args.channel)

    for ch in chans:
        if ch == "slack" and cfg.get("slack_webhook"):
            sent = send_slack(cfg["slack_webhook"], text) or sent
        elif ch == "telegram" and cfg.get("telegram_bot_token") and cfg.get("telegram_chat_id"):
            sent = send_telegram(cfg["telegram_bot_token"], cfg["telegram_chat_id"], text) or sent

    if not sent:
        print("[NOTIFY] skipped (no channel configured)", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
