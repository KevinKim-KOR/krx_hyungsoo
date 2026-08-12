#!/usr/bin/env bash
# macOS/Linux 版 start — 기존 start.bat 과 동일 목적 (백엔드 8000 + 프론트 3000).
# Windows 는 새 cmd 창을 띄우지만, 여기서는 백그라운드 실행 + 로그 파일로 대체한다.
# 로그: /tmp/krx_backend.log · /tmp/krx_frontend.log
set -uo pipefail

cd "$(dirname "$0")"

BACKEND_LOG=/tmp/krx_backend.log
FRONTEND_LOG=/tmp/krx_frontend.log

echo "========================================"
echo "POC1 approval loop - start (macOS)"
echo "========================================"
echo

# 0. 기존 프로세스 정리
echo "[0/3] Cleaning up existing processes..."
./stop.sh >/dev/null 2>&1
sleep 1

# 1. FastAPI backend (port 8000)
#    .venv 는 uv 로 만든 Python 3.12 환경. 없으면 여기서 멈춘다.
if [ ! -x ".venv/bin/python" ]; then
    echo "ERROR: .venv/bin/python 이 없습니다. 먼저 venv 를 만드세요." >&2
    exit 1
fi
echo "[1/3] Starting FastAPI backend on port 8000..."
nohup .venv/bin/python -m uvicorn app.api:app \
    --host 127.0.0.1 --port 8000 --reload > "$BACKEND_LOG" 2>&1 &

# 2. Next.js frontend (port 3000)
#    NEXT_PUBLIC_API_BASE 는 frontend/.env.local 이 단일 소스.
#    최초 1회: cp frontend/.env.local.example frontend/.env.local
#    node 는 nvm 설치본이라 비대화형 셸에서는 PATH 에 없다 → 명시적으로 로드한다.
echo "[2/3] Starting Next.js frontend on port 3000..."
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
# shellcheck source=/dev/null
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" >/dev/null
if ! command -v node >/dev/null 2>&1; then
    echo "ERROR: node 를 찾을 수 없습니다 (nvm 설치 확인)." >&2
    exit 1
fi
( cd frontend && nohup npm run dev > "$FRONTEND_LOG" 2>&1 & )

# 3. 부팅 대기 후 브라우저 열기
echo "[3/3] Waiting 5 seconds for servers to boot..."
sleep 5
open "http://localhost:3000"

echo
echo "========================================"
echo "Start complete"
echo "- Frontend : http://localhost:3000   (log: $FRONTEND_LOG)"
echo "- Backend  : http://127.0.0.1:8000/docs (log: $BACKEND_LOG)"
echo "Run ./stop.sh to shut down."
echo "========================================"
