#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../.."

echo "[RUN] verify_signal_env $(date '+%F %T')"

# 1) 필수 파일/권한
WRAPPER="scripts/linux/batch/run_signal_wrapper.sh"
TARGET="scripts/linux/batch/run_signals.sh"
ENVSH="config/env.nas.sh"
LOGDIR="logs"
TODAY_LOG="logs/signals_$(date +%F).log"

fail() { echo "[EXIT] $1"; exit 2; }
skip() { echo "[SKIP] $1"; exit 0; }

[ -f "$WRAPPER" ] || fail "missing $WRAPPER"
[ -x "$WRAPPER" ] || fail "no exec perm on $WRAPPER (chmod +x 필요)"
[ -f "$TARGET" ]  || fail "missing $TARGET"
[ -d "$LOGDIR" ]  || fail "missing $LOGDIR directory"

# 2) 래퍼 내용에 env 로드 구문 포함 여부
if ! grep -q 'config/env.nas.sh' "$WRAPPER"; then
  fail "wrapper does not source config/env.nas.sh"
fi

# 3) 환경 로드
if [ -f "$ENVSH" ]; then
  # shellcheck disable=SC1090
  source "$ENVSH"
else
  fail "missing $ENVSH"
fi

# 4) 필수 ENV 확인 (마스킹)
mask() { # 마지막 4자리만 노출
  local s="${1:-}"; local n=${#s}
  if [ $n -le 4 ]; then echo "****"; else printf "%s%s" "$(printf '%*s' $((n-4)) | tr ' ' '*')" "${s: -4}"; fi
}
TEL_TOKEN="${TELEGRAM_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"
TEL_CHAT="${TELEGRAM_CHAT_ID:-}"
SLACK_URL="${SLACK_WEBHOOK_URL:-${SLACK_WEBHOOK:-}}"

[ -n "${PYTHONBIN:-}" ] || fail "PYTHONBIN not set (env.nas.sh 확인)"
echo "[INFO] PYTHONBIN: $PYTHONBIN"
command -v "$PYTHONBIN" >/dev/null 2>&1 || fail "PYTHONBIN not found in PATH"

[ -n "$TEL_TOKEN" ] || echo "[WARN] TELEGRAM_TOKEN empty"
[ -n "$TEL_CHAT" ]  || echo "[WARN] TELEGRAM_CHAT_ID empty"
echo "[INFO] TELEGRAM_TOKEN: $(mask "$TEL_TOKEN")"
echo "[INFO] TELEGRAM_CHAT_ID: $(mask "$TEL_CHAT")"

# 5) 툴 가용성
command -v curl >/dev/null 2>&1 || echo "[WARN] curl not found (텔레그램 전송 실패 가능)"

# 6) 네트워크 간이 점검 (DNS/443 핸드쉐이크 여부)
HOST="api.telegram.org"
if getent hosts "$HOST" >/dev/null 2>&1; then
  echo "[INFO] DNS ok for $HOST"
else
  echo "[WARN] DNS resolve failed for $HOST"
fi

# 7) 로그 경로 확인
touch "$TODAY_LOG" || fail "cannot write $TODAY_LOG"
echo "[INFO] log path ok: $TODAY_LOG"

echo "[DONE] verify_signal_env"
exit 0
