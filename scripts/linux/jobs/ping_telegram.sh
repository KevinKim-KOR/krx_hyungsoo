#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

TITLE="${1:-HEALTHCHECK}"
BODY="${2:-"(no message)"}"

if [ -z "${TG_TOKEN:-}" ] || [ -z "${TG_CHAT_ID:-}" ]; then
  echo "[ALERT] skip: TG_TOKEN/TG_CHAT_ID not set"
  exit 0
fi

API="https://api.telegram.org/bot${TG_TOKEN}/sendMessage"
TEXT="${TITLE}"$'\n'"${BODY}"

# jq 없이 안전하게 전송
curl -sS -X POST "$API" \
  --data-urlencode "chat_id=${TG_CHAT_ID}" \
  --data-urlencode "text=${TEXT}" \
  --data-urlencode "disable_web_page_preview=true" \
  --data-urlencode "parse_mode=HTML" \
  >/dev/null || echo "[ALERT] telegram send failed (non-fatal)"
