#!/bin/bash
# poc1_consume_inbox.sh - POC1 Step 3 inbox consumer.
#
# 호출 주체: deploy/oci/daily_ops.sh 의 한 step 또는 사용자가 1회 수동 실행.
# 새로운 cron/scheduler 를 만들지 않는다 (설계자 결정).
#
# 동작:
#   1) state/poc1_inbox/*.json 스캔
#   2) 각 artifact:
#      - draft_payload 에서 title/note/recommendations 를 읽음
#      - Telegram sendMessage 발송
#      - 결과를 state/poc1_outbox/{run_id}.json 에 기록
#        ({status: COMPLETED|FAILED, processed_at, telegram_message_id?})
#      - inbox 파일은 state/poc1_processed/{run_id}.json 으로 이동
#
# Telegram 토큰: $REPO_DIR/state/secrets/telegram.env (daily_ops.sh 와 동일 규약)
# 실패 처리: artifact 단위로 격리. 한 건 실패가 전체를 중단시키지 않는다.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
INBOX_DIR="$REPO_DIR/state/poc1_inbox"
OUTBOX_DIR="$REPO_DIR/state/poc1_outbox"
PROCESSED_DIR="$REPO_DIR/state/poc1_processed"
SECRETS_FILE="$REPO_DIR/state/secrets/telegram.env"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

mkdir -p "$INBOX_DIR" "$OUTBOX_DIR" "$PROCESSED_DIR"

cd "$REPO_DIR"

if [ -f "$SECRETS_FILE" ]; then
    # shellcheck disable=SC1090
    source "$SECRETS_FILE"
fi

# 환경변수가 .env 등에서 export 됐을 수도 있음 (둘 다 허용)
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

processed_count=0
failed_count=0

shopt -s nullglob
for artifact in "$INBOX_DIR"/*.json; do
    base="$(basename "$artifact")"
    run_id="${base%.json}"

    echo "$LOG_PREFIX [poc1] processing run_id=$run_id"

    # JSON 파싱 (python3) — title/note/recommendations 추출
    parsed=$(python3 - "$artifact" <<'PY'
import json, sys
path = sys.argv[1]
try:
    data = json.load(open(path, "r", encoding="utf-8"))
except Exception as e:
    print("PARSE_ERROR")
    print(str(e))
    sys.exit(1)
payload = data.get("draft_payload")
# 암묵 fallback 금지 (DEV_RULES). 필수 키 누락 = 즉시 실패.
if not isinstance(payload, dict):
    print("CONTRACT_ERROR")
    print("draft_payload_missing_or_not_dict")
    sys.exit(2)
missing = [k for k in ("title", "note", "recommendations") if k not in payload]
if missing:
    print("CONTRACT_ERROR")
    print("missing_keys=" + ",".join(missing))
    sys.exit(2)
title = str(payload["title"])
note = str(payload["note"])
recs = payload["recommendations"]
try:
    recs_str = json.dumps(recs, ensure_ascii=False)
except Exception:
    recs_str = str(recs)
print("OK")
print(title)
print(note)
print(recs_str)
PY
)
    parse_status=$(echo "$parsed" | head -n 1)
    if [ "$parse_status" != "OK" ]; then
        # PARSE_ERROR (JSON 자체 깨짐) 또는 CONTRACT_ERROR (필수 키 누락)
        # 어느 쪽이든 Telegram 발송 시도하지 않고 즉시 FAILED 로 종결.
        reason_detail=$(echo "$parsed" | sed -n '2p')
        echo "$LOG_PREFIX [poc1] artifact 검증 실패 run_id=$run_id status=$parse_status detail=$reason_detail"
        cat > "$OUTBOX_DIR/$run_id.json" <<EOF
{
  "run_id": "$run_id",
  "status": "FAILED",
  "processed_at": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "reason": "${parse_status}: ${reason_detail}"
}
EOF
        mv -f "$artifact" "$PROCESSED_DIR/$base"
        failed_count=$((failed_count + 1))
        continue
    fi

    title=$(echo "$parsed" | sed -n '2p')
    note=$(echo "$parsed" | sed -n '3p')
    recs_str=$(echo "$parsed" | sed -n '4p')

    # Telegram 메시지 작성
    msg=$(printf "✅ POC1 승인 처리\nrun_id: %s\ntitle: %s\nnote: %s\nrecommendations: %s" \
        "$run_id" "$title" "$note" "$recs_str")

    tg_message_id=""
    delivery_status="FAILED"
    delivery_reason=""

    if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
        delivery_reason="telegram_secrets_missing"
        echo "$LOG_PREFIX [poc1] Telegram 시크릿 누락 — FAILED 처리"
    else
        # Telegram sendMessage 호출
        # --connect-timeout / --max-time 으로 무응답 시 무한 대기 차단.
        tg_resp=$(curl -s \
            --connect-timeout 5 \
            --max-time 10 \
            -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
            --data-urlencode "text=${msg}" 2>/dev/null || echo "")
        if echo "$tg_resp" | grep -q '"ok":true'; then
            tg_message_id=$(echo "$tg_resp" | python3 -c \
                'import sys,json; d=json.load(sys.stdin); print(d.get("result",{}).get("message_id",""))' \
                2>/dev/null || echo "")
            delivery_status="COMPLETED"
        else
            delivery_reason="telegram_api_error"
            echo "$LOG_PREFIX [poc1] Telegram 전송 실패 resp=$tg_resp"
        fi
    fi

    # outbox 작성
    if [ "$delivery_status" = "COMPLETED" ]; then
        cat > "$OUTBOX_DIR/$run_id.json" <<EOF
{
  "run_id": "$run_id",
  "status": "COMPLETED",
  "processed_at": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "telegram_message_id": "$tg_message_id"
}
EOF
        processed_count=$((processed_count + 1))
    else
        cat > "$OUTBOX_DIR/$run_id.json" <<EOF
{
  "run_id": "$run_id",
  "status": "FAILED",
  "processed_at": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "reason": "$delivery_reason"
}
EOF
        failed_count=$((failed_count + 1))
    fi

    mv -f "$artifact" "$PROCESSED_DIR/$base"
    echo "$LOG_PREFIX [poc1] run_id=$run_id → $delivery_status"
done

echo "$LOG_PREFIX [poc1] consume done: completed=$processed_count failed=$failed_count"
exit 0
