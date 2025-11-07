#!/bin/bash
# scripts/nas/debug_scheduler.sh
# NAS 스케줄러 디버깅 스크립트

set -e

echo "=========================================="
echo "NAS 스케줄러 디버깅 시작"
echo "=========================================="
echo ""

# 프로젝트 루트
PROJECT_ROOT="/volume2/homes/Hyungsoo/krx/krx_alertor_modular"
cd "$PROJECT_ROOT" || exit 1

# 디버그 로그 파일
DEBUG_LOG="$PROJECT_ROOT/logs/debug_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$PROJECT_ROOT/logs"

# 로그 함수
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$DEBUG_LOG"
}

log "=========================================="
log "1. 시스템 정보"
log "=========================================="

log "현재 시간: $(date)"
log "사용자: $(whoami)"
log "작업 디렉토리: $(pwd)"
log "호스트명: $(hostname)"

log ""
log "=========================================="
log "2. Python 환경"
log "=========================================="

# Python 경로 찾기
PYTHON=""
for py_path in "/usr/local/bin/python3.8" "/usr/bin/python3.8" "python3.8"; do
    if command -v "$py_path" &> /dev/null; then
        PYTHON="$py_path"
        log "Python 발견: $PYTHON"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    log "❌ Python 3.8을 찾을 수 없습니다!"
    exit 1
fi

log "Python 버전: $($PYTHON --version)"
log "Python 경로: $(which $PYTHON)"

log ""
log "=========================================="
log "3. 환경 변수"
log "=========================================="

log "PATH: $PATH"
log "PYTHONPATH: ${PYTHONPATH:-'(미설정)'}"
log "HOME: $HOME"
log "USER: $USER"

log ""
log "=========================================="
log "4. 프로젝트 파일 확인"
log "=========================================="

# 주요 파일 확인
files=(
    "scripts/nas/market_open_alert.py"
    "scripts/nas/rising_etf_alert.py"
    "scripts/nas/regime_change_alert.py"
    "scripts/nas/daily_realtime_signals.sh"
    "secret/config.yaml"
    "extensions/notification/telegram_sender.py"
)

for file in "${files[@]}"; do
    if [ -f "$PROJECT_ROOT/$file" ]; then
        log "✅ $file ($(stat -c%s "$PROJECT_ROOT/$file") bytes)"
    else
        log "❌ $file (없음)"
    fi
done

log ""
log "=========================================="
log "5. 디렉토리 권한"
log "=========================================="

log "프로젝트 루트: $(ls -ld "$PROJECT_ROOT")"
log "logs 디렉토리: $(ls -ld "$PROJECT_ROOT/logs" 2>/dev/null || echo '없음')"
log "data 디렉토리: $(ls -ld "$PROJECT_ROOT/data" 2>/dev/null || echo '없음')"

log ""
log "=========================================="
log "6. 텔레그램 설정 확인"
log "=========================================="

if [ -f "$PROJECT_ROOT/secret/config.yaml" ]; then
    log "✅ secret/config.yaml 존재"
    
    # Bot Token 확인 (민감 정보는 마스킹)
    if grep -q "bot_token" "$PROJECT_ROOT/secret/config.yaml"; then
        log "✅ bot_token 설정됨"
    else
        log "❌ bot_token 없음"
    fi
    
    # Chat ID 확인
    if grep -q "chat_id" "$PROJECT_ROOT/secret/config.yaml"; then
        log "✅ chat_id 설정됨"
    else
        log "❌ chat_id 없음"
    fi
else
    log "❌ secret/config.yaml 없음"
fi

log ""
log "=========================================="
log "7. DB 파일 확인"
log "=========================================="

db_files=(
    "data/monitoring/signals.db"
    "data/monitoring/performance.db"
)

for db_file in "${db_files[@]}"; do
    if [ -f "$PROJECT_ROOT/$db_file" ]; then
        size=$(stat -c%s "$PROJECT_ROOT/$db_file")
        log "✅ $db_file ($size bytes)"
    else
        log "⚠️ $db_file (없음)"
    fi
done

log ""
log "=========================================="
log "8. 로그 파일 확인"
log "=========================================="

if [ -d "$PROJECT_ROOT/logs" ]; then
    log_count=$(ls -1 "$PROJECT_ROOT/logs"/*.log 2>/dev/null | wc -l)
    log "로그 파일 수: $log_count"
    
    if [ "$log_count" -gt 0 ]; then
        log "최근 로그 파일:"
        ls -lt "$PROJECT_ROOT/logs"/*.log 2>/dev/null | head -5 | while read line; do
            log "  $line"
        done
    fi
else
    log "⚠️ logs 디렉토리 없음"
fi

log ""
log "=========================================="
log "9. 네트워크 연결 테스트"
log "=========================================="

# 텔레그램 API 연결 테스트
if command -v curl &> /dev/null; then
    log "텔레그램 API 연결 테스트..."
    if curl -s --max-time 5 https://api.telegram.org > /dev/null; then
        log "✅ 텔레그램 API 연결 성공"
    else
        log "❌ 텔레그램 API 연결 실패"
    fi
else
    log "⚠️ curl 명령어 없음"
fi

log ""
log "=========================================="
log "10. 스크립트 수동 실행 테스트"
log "=========================================="

# PYTHONPATH 설정
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# 장 시작 알림 테스트
log "장 시작 알림 테스트..."
if $PYTHON "$PROJECT_ROOT/scripts/nas/market_open_alert.py" >> "$DEBUG_LOG" 2>&1; then
    log "✅ 장 시작 알림 실행 성공"
else
    log "❌ 장 시작 알림 실행 실패 (exit code: $?)"
fi

log ""

# 텔레그램 전송 테스트
log "텔레그램 전송 테스트..."
$PYTHON << EOF >> "$DEBUG_LOG" 2>&1
import sys
sys.path.insert(0, '$PROJECT_ROOT')

try:
    from extensions.notification.telegram_sender import TelegramSender
    sender = TelegramSender()
    result = sender.send_custom("🧪 디버그 테스트 메시지 - $(date)", parse_mode='Markdown')
    print(f"전송 결과: {result}")
    if result:
        print("✅ 텔레그램 전송 성공")
    else:
        print("❌ 텔레그램 전송 실패")
except Exception as e:
    print(f"❌ 에러 발생: {e}")
    import traceback
    traceback.print_exc()
EOF

log ""
log "=========================================="
log "디버깅 완료"
log "=========================================="
log ""
log "디버그 로그 저장: $DEBUG_LOG"
log ""
log "다음 단계:"
log "1. 위 로그를 확인하여 문제 파악"
log "2. ❌ 표시된 항목 수정"
log "3. 텔레그램 메시지 수신 확인"
log ""

echo ""
echo "=========================================="
echo "디버그 로그 위치: $DEBUG_LOG"
echo "=========================================="
echo ""
echo "로그 확인 방법:"
echo "  cat $DEBUG_LOG"
echo ""
