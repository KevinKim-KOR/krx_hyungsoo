#!/bin/bash
# scripts/linux/jobs/stop_loss_check.sh
# 손절 모니터링 (평일 15:30 실행)

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
LOG_FILE="$LOG_DIR/stop_loss_check_${TIMESTAMP}.log"

# 로그 시작
echo "========================================" | tee -a "$LOG_FILE"
echo "[$(date)] 손절 모니터링 시작" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# RC 초기화
RC=0

# 손절 모니터링 실행
echo "[$(date)] 손절 체크 및 알림" | tee -a "$LOG_FILE"
python3.8 scripts/phase4/monitor_stop_loss.py 2>&1 | tee -a "$LOG_FILE"

RC=$?

if [ $RC -eq 0 ]; then
    echo "[$(date)] ✅ 손절 모니터링 성공 (RC=$RC)" | tee -a "$LOG_FILE"
else
    echo "[$(date)] ❌ 손절 모니터링 실패 (RC=$RC)" | tee -a "$LOG_FILE"
fi

# 로그 종료
echo "========================================" | tee -a "$LOG_FILE"
echo "[$(date)] 작업 완료 (RC=$RC)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

exit $RC
