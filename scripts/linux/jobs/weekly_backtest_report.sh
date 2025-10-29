#!/bin/bash
# scripts/linux/jobs/weekly_backtest_report.sh
# 주간 백테스트 리포트 생성 및 텔레그램 알림
# 실행: 매주 일요일 09:00

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
WEEK_AGO=$(date -d '7 days ago' +%Y-%m-%d)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/weekly_backtest_${TIMESTAMP}.log"

# 로그 시작
echo "========================================" | tee -a "$LOG_FILE"
echo "[$(date)] 주간 백테스트 시작" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# RC 초기화
RC=0

# 백테스트 실행
echo "[$(date)] 백테스트 실행: $WEEK_AGO ~ $TODAY" | tee -a "$LOG_FILE"
python3.8 pc/cli.py backtest \
    --start "$WEEK_AGO" \
    --end "$TODAY" \
    --capital 10000000 \
    --max-positions 10 \
    --rebalance weekly \
    --output "reports/backtest_weekly_${TODAY}" \
    2>&1 | tee -a "$LOG_FILE"

RC=$?

# 결과 확인 및 텔레그램 알림
if [ $RC -eq 0 ]; then
    echo "[$(date)] ✅ 백테스트 성공 (RC=$RC)" | tee -a "$LOG_FILE"
    
    # 리포트 파일 확인
    SUMMARY_FILE="reports/backtest_weekly_${TODAY}/summary.txt"
    
    if [ -f "$SUMMARY_FILE" ]; then
        # 텔레그램 알림 (Python 스크립트 사용)
        python3.8 -c "
from infra.notify.telegram import send_to_telegram
import sys

try:
    with open('$SUMMARY_FILE', 'r', encoding='utf-8') as f:
        summary = f.read()
    
    message = '*[주간 백테스트 리포트]*\n\n'
    message += f'기간: $WEEK_AGO ~ $TODAY\n\n'
    message += '```\n' + summary[:1000] + '\n```'
    
    send_to_telegram(message)
    print('텔레그램 알림 전송 완료')
except Exception as e:
    print(f'텔레그램 알림 실패: {e}', file=sys.stderr)
" 2>&1 | tee -a "$LOG_FILE"
    fi
else
    echo "[$(date)] ❌ 백테스트 실패 (RC=$RC)" | tee -a "$LOG_FILE"
fi

# 로그 종료
echo "========================================" | tee -a "$LOG_FILE"
echo "[$(date)] 작업 완료 (RC=$RC)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

exit $RC
