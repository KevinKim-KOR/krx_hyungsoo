#!/bin/bash
# 로컬 개발 시 VM MongoDB 로 SSH 터널을 연다.
#
# 사용법:
#   scripts/mongo-tunnel.sh          # 포그라운드 실행 (종료는 Ctrl+C)
#   scripts/mongo-tunnel.sh &        # 백그라운드 실행
#
# 선행 조건:
#   - VM 의 MongoDB 컨테이너가 기동 중이어야 합니다.
#   - 로컬 .env 에 MONGO_DB_HOST=localhost:27017 이 설정되어 있어야 합니다.
#
# 주의:
#   - 로컬 27017 포트가 이미 사용 중이면 실패합니다.
#   - 터널을 닫으면 로컬 앱이 DB 에 접근하지 못합니다.

set -euo pipefail

SSH_KEY="${SSH_KEY:-$HOME/DEV/ssh-key-2025-10-09.key}"
SSH_USER="${SSH_USER:-ubuntu}"
SSH_HOST="${SSH_HOST:-134.185.109.82}"
LOCAL_PORT="${LOCAL_PORT:-27017}"
REMOTE_PORT="${REMOTE_PORT:-27017}"

if [[ ! -f "$SSH_KEY" ]]; then
  echo "[mongo-tunnel] SSH 키를 찾을 수 없습니다: $SSH_KEY" >&2
  exit 1
fi

# 이미 로컬 포트가 사용 중인지 확인
if lsof -iTCP:"$LOCAL_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[mongo-tunnel] 로컬 포트 $LOCAL_PORT 이 이미 사용 중입니다. 기존 터널이 있거나 다른 프로세스가 점유 중일 수 있습니다." >&2
  exit 1
fi

echo "[mongo-tunnel] ${SSH_USER}@${SSH_HOST} 로 터널을 엽니다: localhost:${LOCAL_PORT} → VM:${REMOTE_PORT}"
exec ssh \
  -i "$SSH_KEY" \
  -N \
  -L "${LOCAL_PORT}:localhost:${REMOTE_PORT}" \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  "${SSH_USER}@${SSH_HOST}"
