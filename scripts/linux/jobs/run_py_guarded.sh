#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

LOGDIR="logs"; mkdir -p "$LOGDIR"
TMP_OUT="$(mktemp)"

set +e
# 전달받은 커맨드를 그대로 실행 (예: "$PYTHONBIN" scripts/scanner.py --today)
"$@" >"$TMP_OUT" 2>&1
RC=$?
set -e

OUT="$(cat "$TMP_OUT")"
rm -f "$TMP_OUT"
echo "$OUT"

if [ $RC -ne 0 ]; then
  # 외부요인 패턴(레이트리밋/네트워크/서버 오류 등) → 스킵으로 변환
  if echo "$OUT" | grep -qiE \
    'Too Many Requests|Rate limited|timed out|ReadTimeout|Connection reset|Temporary failure|Name or service not known|Max retries exceeded|502 Bad Gateway|503 Service Unavailable|JSONDecodeError|Remote end closed connection'; then
    echo "[SKIP] external-data-unavailable (guarded)"
    exit 0
  fi
  exit $RC
fi
exit 0
