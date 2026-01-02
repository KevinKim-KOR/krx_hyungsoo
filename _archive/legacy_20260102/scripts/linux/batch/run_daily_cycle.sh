#!/bin/bash
# run_daily_cycle.sh - NAS 일일 자동화 사이클
# Cron: 0 16 * * 1-5  (월~금 16:00)

set -e

PROJECT_ROOT="/volume2/homes/Hyungsoo/krx/krx_alertor_modular"
cd "$PROJECT_ROOT"

source config/env.nas.sh

LOG_DIR="logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/daily_cycle_$TIMESTAMP.log"

echo "=========================================="
echo "[DAILY CYCLE] 시작: $(date)"
echo "=========================================="

# 1. Git 동기화 (PC에서 전략 변경사항 가져오기)
echo "[1/5] Git 동기화..."
bash scripts/linux/batch/update_from_git.sh >> "$LOG_FILE" 2>&1
if [ $? -eq 0 ]; then
    echo "  ✓ Git Pull 성공"
else
    echo "  ✗ Git Pull 실패"
    exit 1
fi

# 2. EOD 데이터 수집
echo "[2/5] EOD 데이터 수집..."
bash scripts/linux/batch/run_ingest_eod_serial.sh >> "$LOG_FILE" 2>&1
if [ $? -eq 0 ]; then
    echo "  ✓ 데이터 수집 성공"
else
    echo "  ✗ 데이터 수집 실패 (계속 진행)"
fi

# 3. 캐시 → DB 동기화
echo "[3/5] 캐시 동기화..."
bash scripts/linux/batch/run_sync_cache_to_db.sh >> "$LOG_FILE" 2>&1
if [ $? -eq 0 ]; then
    echo "  ✓ 동기화 성공"
else
    echo "  ✗ 동기화 실패 (계속 진행)"
fi

# 4. 스캐너 실행
echo "[4/5] 스캐너 실행..."
bash scripts/linux/batch/run_scanner.sh >> "$LOG_FILE" 2>&1
if [ $? -eq 0 ]; then
    echo "  ✓ 스캐너 성공"
else
    echo "  ✗ 스캐너 실패"
fi

# 5. EOD 리포트 생성 & Telegram 전송
echo "[5/5] EOD 리포트 생성..."
bash scripts/linux/batch/run_report_eod.sh >> "$LOG_FILE" 2>&1
if [ $? -eq 0 ]; then
    echo "  ✓ 리포트 생성 성공"
else
    echo "  ✗ 리포트 생성 실패"
fi

echo "=========================================="
echo "[DAILY CYCLE] 완료: $(date)"
echo "로그: $LOG_FILE"
echo "=========================================="

# 로그 정리 (30일 이상 된 로그 삭제)
find "$LOG_DIR" -name "daily_cycle_*.log" -mtime +30 -delete

exit 0
