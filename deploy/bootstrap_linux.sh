#!/bin/bash
# =============================================================================
# KRX Alertor Modular - Bootstrap Script (Linux/NAS)
# Phase C-P.39: Deployment Profile Lock
# =============================================================================
# 용도: venv 생성, 의존성 설치, 헬스체크, DRY_RUN ops 1회 실행
# 실패 시 exit code != 0
# =============================================================================

set -e

echo "========================================"
echo " KRX Alertor Modular - Bootstrap"
echo " v1.0-golden"
echo "========================================"

# 1. Working directory 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"
echo "[1/5] Project root: $PROJECT_ROOT"

# 2. Python 버전 확인
echo "[2/5] Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "  Python: $PYTHON_VERSION"
else
    echo "  ERROR: Python 3 not found. Install Python 3.10+"
    exit 1
fi

# 3. venv 생성/활성화
echo "[3/5] Setting up virtual environment..."
if [ ! -d ".venv" ]; then
    echo "  Creating .venv..."
    python3 -m venv .venv
fi
echo "  Activating .venv..."
source .venv/bin/activate

# 4. 의존성 설치
echo "[4/5] Installing dependencies..."
pip install -r requirements.txt --quiet
echo "  Dependencies installed."

# 5. Backend 시작 (백그라운드) + Health Check
echo "[5/5] Starting backend for health check..."
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
sleep 5

# Health Check
if curl -s http://127.0.0.1:8000/api/ops/health > /dev/null 2>&1; then
    echo "  Health Check: OK"
else
    echo "  Health Check: FAILED (backend may not be running)"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

# 6. DRY_RUN Ops Cycle
echo "[Bonus] Running DRY_RUN Ops Cycle..."
OPS_RESULT=$(curl -s -X POST http://127.0.0.1:8000/api/ops/cycle/run 2>/dev/null || echo '{"overall_status":"FAILED"}')
OPS_STATUS=$(echo "$OPS_RESULT" | grep -o '"overall_status":"[^"]*"' | cut -d'"' -f4)
echo "  Ops Cycle: ${OPS_STATUS:-UNKNOWN}"

# Cleanup
kill $BACKEND_PID 2>/dev/null || true

echo ""
echo "========================================"
echo " Bootstrap Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Start backend: uvicorn backend.main:app --host 0.0.0.0 --port 8000"
echo "  2. Open dashboard: http://localhost:8000/dashboard/"
echo "  3. Register scheduler: See docs/ops/runbook_deploy_v1.md"
echo ""

exit 0
