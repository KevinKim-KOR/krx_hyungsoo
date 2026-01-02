#!/bin/bash
# scripts/cloud/daily_scan_notify.sh
# Oracle Cloud용: 장마감 후 일일 리포트 및 텔레그램 알림
# 실행: 평일 16:00 (장마감 후)

set -e

# Oracle Cloud 경로 설정
PROJECT_ROOT="/home/ubuntu/krx_hyungsoo"
cd "$PROJECT_ROOT"

# 환경 변수 로드 (있다면)
if [ -f "config/env.cloud.sh" ]; then
    source config/env.cloud.sh
fi

# 로그 디렉토리
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# 날짜
TODAY=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/daily_report_${TIMESTAMP}.log"

# 로그 시작
echo "========================================" | tee -a "$LOG_FILE"
echo "[$(date)] [Cloud] 장마감 일일 리포트 시작" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# RC 초기화
RC=0

# 일일 리포트 생성 및 텔레그램 알림
# Cloud 환경에서는 python3 (Ubuntu 기본) 사용
echo "[$(date)] 일일 리포트 생성 및 알림" | tee -a "$LOG_FILE"
/usr/bin/python3 scripts/nas/daily_report_alert.py 2>&1 | tee -a "$LOG_FILE"

RC=$?

if [ $RC -eq 0 ]; then
    echo "[$(date)] ✅ 일일 리포트 전송 성공 (RC=$RC)" | tee -a "$LOG_FILE"
else
    echo "[$(date)] ❌ 일일 리포트 전송 실패 (RC=$RC)" | tee -a "$LOG_FILE"
fi

# 로그 종료
echo "========================================" | tee -a "$LOG_FILE"
echo "[$(date)] 작업 완료 (RC=$RC)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

exit $RC
