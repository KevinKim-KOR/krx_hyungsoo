export TZ=Asia/Seoul
# venv의 python을 사용하면 각 잡에서 별도 활성화 없이 패키지 사용 가능
export ENV=nas
export PYTHONBIN="/volume2/homes/Hyungsoo/krx/krx_alertor_modular/venv/bin/python"
export ALLOW_NET_FETCH=1   # 운영시간엔 온라인 허용
export TG_TOKEN="8216278192:AAFLuiVI8hrWr86uV2zs9gMLrTcZdO9tGyk"
export TG_CHAT_ID=7457035904

# --- Telegram env aliases (for compatibility) ---
export TELEGRAM_TOKEN="${TELEGRAM_TOKEN:-$TG_TOKEN}"
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-$TG_TOKEN}"
export TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-$TG_CHAT_ID}"