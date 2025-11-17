#!/bin/bash
# scripts/sync/sync_to_oracle.sh
# NAS에서 Oracle Cloud로 데이터 동기화

# ============================================================
# 설정
# ============================================================

# 경로 설정
PROJECT_DIR="/volume2/homes/Hyungsoo/krx/krx_alertor_modular"
NAS_SYNC_DIR="$PROJECT_DIR/data/sync"
LOG_DIR="$PROJECT_DIR/logs/sync"

# Oracle Cloud 설정
ORACLE_USER="ubuntu"
ORACLE_HOST="168.107.51.68"
ORACLE_SYNC_DIR="~/krx_hyungsoo/data/sync"
SSH_KEY="$HOME/.ssh/oracle_cloud_key"

# 로그 파일
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/sync_$(date +%Y%m%d).log"

# ============================================================
# 함수
# ============================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_prerequisites() {
    log "📋 사전 조건 확인 중..."
    
    # SSH 키 확인
    if [ ! -f "$SSH_KEY" ]; then
        log "❌ SSH 키를 찾을 수 없습니다: $SSH_KEY"
        return 1
    fi
    
    # 동기화 디렉토리 확인
    if [ ! -d "$NAS_SYNC_DIR" ]; then
        log "❌ 동기화 디렉토리를 찾을 수 없습니다: $NAS_SYNC_DIR"
        return 1
    fi
    
    # 파일 개수 확인
    file_count=$(ls -1 "$NAS_SYNC_DIR"/*.json 2>/dev/null | wc -l)
    if [ "$file_count" -eq 0 ]; then
        log "⚠️ 동기화할 JSON 파일이 없습니다"
        return 1
    fi
    
    log "✅ 사전 조건 확인 완료 (파일: ${file_count}개)"
    return 0
}

sync_files() {
    log "🚀 동기화 시작..."
    
    # rsync 실행
    rsync -avz --progress \
        -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
        "$NAS_SYNC_DIR/" \
        "$ORACLE_USER@$ORACLE_HOST:$ORACLE_SYNC_DIR/" \
        >> "$LOG_FILE" 2>&1
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        log "✅ 동기화 성공"
        return 0
    else
        log "❌ 동기화 실패 (Exit Code: $exit_code)"
        return $exit_code
    fi
}

send_telegram_notification() {
    local status=$1
    local message=$2
    
    # 텔레그램 설정 로드
    if [ -f "$PROJECT_DIR/.env" ]; then
        source "$PROJECT_DIR/.env"
    fi
    
    # 텔레그램 봇 토큰과 채팅 ID 확인
    if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
        log "⚠️ 텔레그램 설정이 없습니다 (알림 스킵)"
        return 0
    fi
    
    # 메시지 전송
    local emoji
    if [ "$status" = "success" ]; then
        emoji="✅"
    else
        emoji="❌"
    fi
    
    local full_message="${emoji} **Oracle 동기화**\n\n${message}\n\n시간: $(date '+%Y-%m-%d %H:%M:%S')"
    
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=${full_message}" \
        -d "parse_mode=Markdown" \
        >> "$LOG_FILE" 2>&1
    
    if [ $? -eq 0 ]; then
        log "📱 텔레그램 알림 전송 완료"
    else
        log "⚠️ 텔레그램 알림 전송 실패"
    fi
}

# ============================================================
# 메인 로직
# ============================================================

main() {
    log "=========================================="
    log "Oracle Cloud 동기화 시작"
    log "=========================================="
    
    # 1. 사전 조건 확인
    if ! check_prerequisites; then
        log "❌ 사전 조건 확인 실패"
        send_telegram_notification "error" "사전 조건 확인 실패"
        return 1
    fi
    
    # 2. 동기화 실행
    if ! sync_files; then
        log "❌ 동기화 실패"
        send_telegram_notification "error" "동기화 실패"
        return 1
    fi
    
    # 3. 성공 알림
    file_count=$(ls -1 "$NAS_SYNC_DIR"/*.json 2>/dev/null | wc -l)
    send_telegram_notification "success" "동기화 완료 (${file_count}개 파일)"
    
    log "=========================================="
    log "✨ Oracle Cloud 동기화 완료"
    log "=========================================="
    
    return 0
}

# 스크립트 실행
main
exit $?
