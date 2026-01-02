#!/bin/bash
# scripts/nas/backup_db.sh
# DB 백업 스크립트

PROJECT_ROOT="/volume2/homes/Hyungsoo/krx/krx_alertor_modular"
BACKUP_DIR="/volume2/homes/Hyungsoo/krx/backups"
DATE=$(date +%Y%m%d)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

cd "$PROJECT_ROOT"

echo "=========================================="
echo "[$(date)] DB 백업 시작"
echo "=========================================="

# 백업 디렉토리 생성
mkdir -p "$BACKUP_DIR"

# DB 파일 백업
if [ -f "data/monitoring/signals.db" ]; then
    cp data/monitoring/signals.db "$BACKUP_DIR/signals_$DATE.db"
    echo "✅ signals.db 백업 완료"
else
    echo "⚠️ signals.db 파일 없음"
fi

if [ -f "data/monitoring/performance.db" ]; then
    cp data/monitoring/performance.db "$BACKUP_DIR/performance_$DATE.db"
    echo "✅ performance.db 백업 완료"
else
    echo "⚠️ performance.db 파일 없음"
fi

# 백업 파일 압축 (선택)
# tar -czf "$BACKUP_DIR/backup_$TIMESTAMP.tar.gz" -C "$BACKUP_DIR" signals_$DATE.db performance_$DATE.db

# 30일 이상 된 백업 삭제
DELETED=$(find "$BACKUP_DIR" -name "*.db" -mtime +30 -delete -print | wc -l)
if [ $DELETED -gt 0 ]; then
    echo "🗑️ 오래된 백업 삭제: $DELETED개"
fi

# 백업 현황
echo ""
echo "백업 현황:"
ls -lh "$BACKUP_DIR"/*.db 2>/dev/null | tail -5

echo ""
echo "=========================================="
echo "[$(date)] DB 백업 완료"
echo "=========================================="
