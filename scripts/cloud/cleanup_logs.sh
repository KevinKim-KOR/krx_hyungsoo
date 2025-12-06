#!/bin/bash
# scripts/cloud/cleanup_logs.sh
# Oracle Cloud용: 오래된 로그 파일 정리

# Oracle Cloud 경로 설정
PROJECT_ROOT="/home/ubuntu/krx_hyungsoo"
DAYS=30

cd "$PROJECT_ROOT"

echo "=========================================="
echo "[$(date)] [Cloud] 로그 정리 시작"
echo "=========================================="

# 로그 디렉토리 확인
if [ ! -d "logs" ]; then
    echo "⚠️ logs 디렉토리 없음"
    exit 0
fi

# 정리 전 통계
TOTAL_LOGS=$(find logs -name "*.log" | wc -l)
TOTAL_SIZE=$(du -sh logs | cut -f1)

echo "정리 전:"
echo "  - 로그 파일 수: $TOTAL_LOGS"
echo "  - 총 크기: $TOTAL_SIZE"

# 30일 이상 된 로그 삭제
echo ""
echo "${DAYS}일 이상 된 로그 삭제 중..."
DELETED=$(find logs -name "*.log" -mtime +$DAYS -delete -print | wc -l)

# 정리 후 통계
REMAINING_LOGS=$(find logs -name "*.log" | wc -l)
REMAINING_SIZE=$(du -sh logs | cut -f1)

echo ""
echo "정리 후:"
echo "  - 삭제된 파일: $DELETED개"
echo "  - 남은 파일: $REMAINING_LOGS개"
echo "  - 남은 크기: $REMAINING_SIZE"

echo ""
echo "=========================================="
echo "[$(date)] 로그 정리 완료"
echo "=========================================="
