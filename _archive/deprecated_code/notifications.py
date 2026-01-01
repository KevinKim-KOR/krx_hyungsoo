import requests

def send_slack(text, webhook):
    if not webhook:
        return False
    try:
        r = requests.post(webhook, json={"text": text}, timeout=10)
        return r.status_code in (200, 204)
    except Exception:
        return False

def send_telegram(text, token, chat_id):
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

def send_notify(text, cfg):
    ui = (cfg.get("ui") or {})
    ch = (cfg.get("notifications", {}) or {}).get("channel", "").lower()
    if ch == "telegram":
        tg = (cfg.get("notifications", {}) or {}).get("telegram", {}) or {}
        return send_telegram(text, tg.get("bot_token"), tg.get("chat_id"))
    # fallback: Slack
    return send_slack(text, ui.get("slack_webhook", ""))
