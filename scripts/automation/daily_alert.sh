#!/bin/bash
# daily_alert.sh
# 일일 리포트 실행 스크립트 (NAS용)

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
LOG_FILE="$LOG_DIR/daily_alert_$(date +%Y%m%d).log"

# 일일 리포트 실행
echo "=== 일일 리포트 시작: $(date) ===" >> $LOG_FILE
$PYTHON $PROJECT_DIR/scripts/automation/run_daily_report.py >> $LOG_FILE 2>&1
EXIT_CODE=$?
echo "=== 일일 리포트 완료: $(date), Exit Code: $EXIT_CODE ===" >> $LOG_FILE

exit $EXIT_CODE
