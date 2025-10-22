export TZ=Asia/Seoul

# venv 활성화 (자동)
PROJECT_ROOT="/volume2/homes/Hyungsoo/krx/krx_alertor_modular"
if [ -f "$PROJECT_ROOT/venv/bin/activate" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# 환경 설정
export ENV=nas
export PYTHONBIN="$PROJECT_ROOT/venv/bin/python"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
export ALLOW_NET_FETCH=1   # 운영시간엔 온라인 허용
export TG_TOKEN="8216278192:AAFLuiVI8hrWr86uV2zs9gMLrTcZdO9tGyk"
export TG_CHAT_ID=7457035904

# --- Telegram env aliases (for compatibility) ---
export TELEGRAM_TOKEN="${TELEGRAM_TOKEN:-$TG_TOKEN}"
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-$TG_TOKEN}"
export TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-$TG_CHAT_ID}"