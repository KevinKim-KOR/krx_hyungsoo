#!/bin/bash
# scripts/linux/setup_cron.sh
# NAS cron 작업 설정 스크립트

PROJECT_ROOT="/volume2/homes/Hyungsoo/krx/krx_alertor_modular"

echo "========================================="
echo "KRX Alertor - Cron 작업 설정"
echo "========================================="
echo ""

# 현재 crontab 백업
echo "1. 현재 crontab 백업..."
crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null || true

# crontab 항목 생성
CRON_FILE="/tmp/krx_alertor_cron.txt"

cat > "$CRON_FILE" << 'EOF'
# KRX Alertor - 자동화 작업
# 프로젝트: /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# 1. 장마감 후 매매 신호 스캔 및 텔레그램 알림
# 평일 18:00 (장마감 후)
0 18 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/linux/jobs/daily_scan_notify.sh

# 2. 주간 백테스트 리포트
# 매주 일요일 09:00
0 9 * * 0 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/linux/jobs/weekly_backtest_report.sh

# 3. 텔레그램 연결 테스트 (선택적)
# 매일 09:00
# 0 9 * * * cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/linux/jobs/ping_telegram.sh

EOF

echo "2. Cron 작업 항목:"
echo "---"
cat "$CRON_FILE"
echo "---"
echo ""

# 사용자 확인
read -p "위 cron 작업을 설치하시겠습니까? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # 기존 crontab에 추가
    (crontab -l 2>/dev/null || true; cat "$CRON_FILE") | crontab -
    
    echo "✅ Cron 작업 설치 완료!"
    echo ""
    echo "현재 crontab:"
    crontab -l
    echo ""
    echo "스크립트 실행 권한 설정..."
    chmod +x "$PROJECT_ROOT/scripts/linux/jobs/"*.sh
    echo "✅ 완료!"
else
    echo "❌ 설치 취소됨"
fi

# 임시 파일 삭제
rm -f "$CRON_FILE"

echo ""
echo "========================================="
echo "설정 완료"
echo "========================================="
echo ""
echo "수동 실행 테스트:"
echo "  bash $PROJECT_ROOT/scripts/linux/jobs/daily_scan_notify.sh"
echo ""
echo "Cron 로그 확인:"
echo "  tail -f $PROJECT_ROOT/logs/daily_scan_*.log"
echo ""
