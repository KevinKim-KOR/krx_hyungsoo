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

    # POC2 Step 1A 책임 분리:
    # - 사람이 읽는 메시지 본문(message_text)는 로컬 백엔드(FastAPI) 가 만든다.
    # - OCI bash 는 message_text 를 그대로 사용해 발송만 담당한다.
    # - holdings 기반 run 에서 message_text 가 누락되면 FAILED 로 처리한다
    #   (raw JSON 으로 대체 발송 금지).
    # - 비-holdings(샘플) run 등 message_text 가 없는 경우는 호환을 위해
    #   기존 형식의 raw recommendations 메시지를 fallback 으로 사용한다.
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

# Step 1A: holdings 식별 (recommendations 첫 항목에 quantity/avg_buy_price 가 있으면 holdings).
recs = payload["recommendations"]
is_holdings = (
    isinstance(recs, list)
    and len(recs) > 0
    and isinstance(recs[0], dict)
    and ("quantity" in recs[0] or "avg_buy_price" in recs[0])
)

message_text = data.get("message_text")
if is_holdings:
    # holdings run 은 message_text 가 반드시 존재해야 한다.
    if not isinstance(message_text, str) or not message_text.strip():
        print("CONTRACT_ERROR")
        print("holdings_run_missing_message_text")
        sys.exit(2)
    print("OK_MSG")
    print(message_text)
else:
    # 비-holdings(샘플 등). message_text 있으면 그대로, 없으면 raw fallback.
    if isinstance(message_text, str) and message_text.strip():
        print("OK_MSG")
        print(message_text)
    else:
        title = str(payload["title"])
        note = str(payload["note"])
        try:
            recs_str = json.dumps(recs, ensure_ascii=False)
        except Exception:
            recs_str = str(recs)
        fallback = (
            "✅ POC1 승인 처리\n"
            f"run_id: {data.get('run_id', '')}\n"
            f"title: {title}\n"
            f"note: {note}\n"
            f"recommendations: {recs_str}"
        )
        print("OK_MSG")
        print(fallback)
PY
)
    parse_status=$(echo "$parsed" | head -n 1)
    if [ "$parse_status" != "OK_MSG" ]; then
        # PARSE_ERROR / CONTRACT_ERROR — Telegram 발송 시도 없이 FAILED.
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

    # parsed 의 첫 줄(OK_MSG) 제외, 나머지 전체가 message_text.
    msg=$(echo "$parsed" | tail -n +2)

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
