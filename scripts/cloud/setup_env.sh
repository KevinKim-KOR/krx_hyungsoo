#!/bin/bash
# scripts/cloud/setup_env.sh
# Oracle Cloud 환경 변수 설정

# 프로젝트 루트
PROJECT_ROOT="/home/ubuntu/krx_hyungsoo"
cd "$PROJECT_ROOT"

# 환경 변수 파일 생성
ENV_FILE="$PROJECT_ROOT/.env"

echo "================================================================================"
echo "Oracle Cloud 환경 변수 설정"
echo "================================================================================"
echo ""

# 기존 파일 백업
if [ -f "$ENV_FILE" ]; then
    echo "기존 .env 파일 백업..."
    cp "$ENV_FILE" "$ENV_FILE.backup.$(date +%Y%m%d_%H%M%S)"
fi

# 환경 변수 작성
cat > "$ENV_FILE" << 'EOF'
# Oracle Cloud 환경 변수
# 생성 시간: $(date '+%Y-%m-%d %H:%M:%S')

# 텔레그램 설정
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=8216278192:AAFLuiVI8hrWr86uV2zs9gMLrTcZdO9tGyk
TELEGRAM_CHAT_ID=7457035904

# 별칭 (호환성)
TG_TOKEN=8216278192:AAFLuiVI8hrWr86uV2zs9gMLrTcZdO9tGyk
TG_CHAT_ID=7457035904

# 환경
ENV=cloud
PYTHONPATH=/home/ubuntu/krx_hyungsoo

# 타임존
TZ=Asia/Seoul
EOF

echo "✅ .env 파일 생성 완료: $ENV_FILE"
echo ""

# 권한 설정 (보안)
chmod 600 "$ENV_FILE"
echo "✅ 파일 권한 설정: 600 (소유자만 읽기/쓰기)"
echo ""

# 내용 확인 (민감 정보 마스킹)
echo "생성된 환경 변수:"
echo "--------------------------------------------------------------------------------"
cat "$ENV_FILE" | grep -v "^#" | grep -v "^$" | sed 's/\(TOKEN=\).*/\1***MASKED***/' | sed 's/\(CHAT_ID=\).*/\1***MASKED***/'
echo "--------------------------------------------------------------------------------"
echo ""

echo "================================================================================"
echo "설정 완료!"
echo "================================================================================"
echo ""
echo "다음 단계:"
echo "1. crontab에 환경 변수 로드 추가:"
echo "   0 9 * * * cd /home/ubuntu/krx_hyungsoo && source .env && /usr/bin/python3 scripts/nas/daily_regime_check.py"
echo ""
echo "2. 또는 Python 스크립트에서 자동 로드:"
echo "   from dotenv import load_dotenv"
echo "   load_dotenv()"
echo ""
echo "3. 테스트:"
echo "   source .env && python3 scripts/nas/daily_regime_check.py"
echo ""
