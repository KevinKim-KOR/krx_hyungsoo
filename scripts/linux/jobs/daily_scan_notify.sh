#!/bin/bash
# scripts/linux/jobs/daily_scan_notify.sh
# 장마감 후 매매 신호 스캔 및 텔레그램 알림
# 실행: 평일 18:00 (장마감 후)

set -e

# 경로 설정
PROJECT_ROOT="/volume2/homes/Hyungsoo/krx/krx_alertor_modular"
cd "$PROJECT_ROOT"

# 환경 변수 로드
if [ -f "config/env.nas.sh" ]; then
    source config/env.nas.sh
fi

# 로그 디렉토리
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# 날짜
TODAY=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/daily_scan_${TIMESTAMP}.log"

# 로그 시작
echo "========================================" | tee -a "$LOG_FILE"
echo "[$(date)] 장마감 신호 스캔 시작" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# RC 초기화
RC=0

# 1. 데이터 업데이트 (선택적)
echo "[$(date)] Step 1: 데이터 업데이트 (스킵)" | tee -a "$LOG_FILE"
# python3.8 pc/cli.py update --date auto 2>&1 | tee -a "$LOG_FILE"

# 2. 매매 신호 스캔 + 텔레그램 알림
echo "[$(date)] Step 2: 매매 신호 스캔 및 알림" | tee -a "$LOG_FILE"
python3.8 pc/cli.py scan \
    --date auto \
    --min-confidence 0.6 \
    --top-n 10 \
    --output "reports/signals_${TODAY}.csv" \
    --notify \
    2>&1 | tee -a "$LOG_FILE"

RC=$?

if [ $RC -eq 0 ]; then
    echo "[$(date)] ✅ 스캔 및 알림 성공 (RC=$RC)" | tee -a "$LOG_FILE"
else
    echo "[$(date)] ❌ 스캔 및 알림 실패 (RC=$RC)" | tee -a "$LOG_FILE"
fi

# 로그 종료
echo "========================================" | tee -a "$LOG_FILE"
echo "[$(date)] 작업 완료 (RC=$RC)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

exit $RC
