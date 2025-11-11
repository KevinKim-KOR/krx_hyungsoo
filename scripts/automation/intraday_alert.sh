#!/bin/bash
# intraday_alert.sh
# 장중 급등/급락 알림 스크립트 (NAS용)

# 프로젝트 경로
PROJECT_DIR="/volume2/homes/Hyungsoo/krx/krx_alertor_modular"
cd $PROJECT_DIR

# 환경 변수 로드
if [ -f .env ]; then
    source .env
fi

# Python 경로
PYTHON="/usr/bin/python3"

# 로그 디렉토리
LOG_DIR="$PROJECT_DIR/logs/automation"
mkdir -p $LOG_DIR

# 로그 파일
LOG_FILE="$LOG_DIR/intraday_alert_$(date +%Y%m%d).log"

# 장중 알림 실행 (보유 종목 우선)
echo "=== 장중 알림 시작: $(date) ===" >> $LOG_FILE
$PYTHON $PROJECT_DIR/scripts/nas/intraday_alert.py >> $LOG_FILE 2>&1
EXIT_CODE=$?
echo "=== 장중 알림 완료: $(date), Exit Code: $EXIT_CODE ===" >> $LOG_FILE

exit $EXIT_CODE
