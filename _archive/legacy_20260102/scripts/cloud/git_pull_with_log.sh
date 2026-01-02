#!/bin/bash
# scripts/cloud/git_pull_with_log.sh
# Oracle Cloud에서 실행되는 Git Pull 스크립트 (날짜/시간 기록)

set -e

# 프로젝트 루트
PROJECT_ROOT="/home/ubuntu/krx_hyungsoo"
cd "$PROJECT_ROOT"

# 로그 디렉토리
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# 로그 파일
LOG_FILE="$LOG_DIR/git_pull.log"

# 시작 시간
START_TIME=$(date '+%Y-%m-%d %H:%M:%S')

echo "================================================================================" | tee -a "$LOG_FILE"
echo "Git Pull 시작 - $START_TIME" | tee -a "$LOG_FILE"
echo "================================================================================" | tee -a "$LOG_FILE"

# 현재 브랜치 및 커밋 확인
echo "" | tee -a "$LOG_FILE"
echo "[이전 상태]" | tee -a "$LOG_FILE"
echo "브랜치: $(git rev-parse --abbrev-ref HEAD)" | tee -a "$LOG_FILE"
echo "커밋: $(git rev-parse --short HEAD) - $(git log -1 --pretty=%B | head -1)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Git Pull 실행
echo "[Git Pull 실행]" | tee -a "$LOG_FILE"
if git pull --ff-only 2>&1 | tee -a "$LOG_FILE"; then
    PULL_STATUS="✅ 성공"
    EXIT_CODE=0
else
    PULL_STATUS="❌ 실패"
    EXIT_CODE=1
fi

# 업데이트 후 상태
echo "" | tee -a "$LOG_FILE"
echo "[업데이트 후 상태]" | tee -a "$LOG_FILE"
echo "브랜치: $(git rev-parse --abbrev-ref HEAD)" | tee -a "$LOG_FILE"
echo "커밋: $(git rev-parse --short HEAD) - $(git log -1 --pretty=%B | head -1)" | tee -a "$LOG_FILE"

# 종료 시간
END_TIME=$(date '+%Y-%m-%d %H:%M:%S')

echo "" | tee -a "$LOG_FILE"
echo "================================================================================" | tee -a "$LOG_FILE"
echo "Git Pull 완료 - $END_TIME" | tee -a "$LOG_FILE"
echo "결과: $PULL_STATUS" | tee -a "$LOG_FILE"
echo "================================================================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

exit $EXIT_CODE
