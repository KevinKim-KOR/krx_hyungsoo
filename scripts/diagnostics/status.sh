#!/bin/bash
# scripts/nas/status.sh
# 실시간 신호 시스템 상태 확인

PROJECT_ROOT="/volume2/homes/Hyungsoo/krx/krx_alertor_modular"
cd "$PROJECT_ROOT"

echo "=========================================="
echo "실시간 신호 시스템 상태"
echo "=========================================="

# 1. 최근 실행 로그
echo -e "\n📋 최근 실행:"
if [ -d "logs" ]; then
    LATEST_LOG=$(ls -t logs/realtime_signals_*.log 2>/dev/null | head -1)
    if [ -n "$LATEST_LOG" ]; then
        echo "  파일: $LATEST_LOG"
        echo "  시간: $(stat -c %y "$LATEST_LOG" 2>/dev/null || stat -f "%Sm" "$LATEST_LOG")"
        echo "  크기: $(du -h "$LATEST_LOG" | cut -f1)"
        
        # 마지막 실행 결과
        if grep -q "✅" "$LATEST_LOG"; then
            echo "  상태: ✅ 성공"
        elif grep -q "❌" "$LATEST_LOG"; then
            echo "  상태: ❌ 실패"
        else
            echo "  상태: ⏳ 진행 중"
        fi
    else
        echo "  ⚠️ 로그 파일 없음"
    fi
else
    echo "  ⚠️ logs 디렉토리 없음"
fi

# 2. DB 상태
echo -e "\n💾 DB 상태:"
if [ -d "data/monitoring" ]; then
    for db in data/monitoring/*.db; do
        if [ -f "$db" ]; then
            echo "  - $(basename $db): $(du -h "$db" | cut -f1)"
        fi
    done
else
    echo "  ⚠️ DB 디렉토리 없음"
fi

# 3. 캐시 상태
echo -e "\n📦 캐시 상태:"
if [ -d "data/cache" ]; then
    CACHE_COUNT=$(ls data/cache/*.parquet 2>/dev/null | wc -l)
    CACHE_SIZE=$(du -sh data/cache 2>/dev/null | cut -f1)
    echo "  - 파일 수: $CACHE_COUNT"
    echo "  - 총 크기: $CACHE_SIZE"
else
    echo "  ⚠️ 캐시 디렉토리 없음"
fi

# 4. 최근 신호 통계
echo -e "\n📊 최근 신호 (최근 7일):"
python3.8 << 'EOF'
import sys
sys.path.insert(0, '/volume2/homes/Hyungsoo/krx/krx_alertor_modular')

try:
    from extensions.monitoring import SignalTracker
    tracker = SignalTracker()
    stats = tracker.get_signal_stats(days=7)
    print(f"  - 총 신호: {stats['total_signals']}개")
    print(f"  - 매수: {stats['buy_count']}개")
    print(f"  - 매도: {stats['sell_count']}개")
    print(f"  - 평균 신뢰도: {stats['avg_confidence']:.2f}")
except Exception as e:
    print(f"  ⚠️ 통계 조회 실패: {e}")
EOF

# 5. Cron 상태
echo -e "\n⏰ Cron 상태:"
CRON_COUNT=$(crontab -l 2>/dev/null | grep -c "daily_realtime_signals")
if [ $CRON_COUNT -gt 0 ]; then
    echo "  ✅ Cron 등록됨 ($CRON_COUNT개)"
    crontab -l | grep "daily_realtime_signals"
else
    echo "  ⚠️ Cron 미등록"
fi

# 6. 디스크 사용량
echo -e "\n💿 디스크 사용량:"
echo "  프로젝트: $(du -sh . | cut -f1)"

echo ""
echo "=========================================="
echo "상태 확인 완료"
echo "=========================================="
