#!/bin/bash
# 미국 지표 비활성화 스크립트
# DS220J 환경에서 즉시 사용 가능하도록 설정

CONFIG_FILE="config/us_market_indicators.yaml"

echo "========================================="
echo "미국 지표 비활성화 중..."
echo "========================================="

# 백업 생성
cp "$CONFIG_FILE" "$CONFIG_FILE.backup"
echo "✅ 백업 생성: $CONFIG_FILE.backup"

# enabled: true → enabled: false
sed -i 's/enabled: true/enabled: false/g' "$CONFIG_FILE"

echo "✅ 미국 지표 비활성화 완료"
echo ""
echo "변경 내용:"
grep "enabled:" "$CONFIG_FILE" | head -5

echo ""
echo "========================================="
echo "테스트 실행:"
echo "python3 scripts/nas/daily_regime_check.py"
echo "========================================="
