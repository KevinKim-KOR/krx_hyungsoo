#!/bin/bash
# scripts/sync/setup_ssh_key.sh
# NAS에서 Oracle Cloud SSH 키 설정 (ssh-copy-id 없는 경우)

# ============================================================
# 설정
# ============================================================

ORACLE_USER="ubuntu"
ORACLE_HOST="168.107.51.68"
SSH_KEY_PATH="$HOME/.ssh/oracle_cloud_key"
SSH_PUB_KEY_PATH="${SSH_KEY_PATH}.pub"

# ============================================================
# 함수
# ============================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# ============================================================
# 메인 로직
# ============================================================

log "=========================================="
log "Oracle Cloud SSH 키 설정 시작"
log "=========================================="

# 1. SSH 키 생성 (없으면)
if [ ! -f "$SSH_KEY_PATH" ]; then
    log "SSH 키 생성 중..."
    ssh-keygen -t rsa -b 4096 -f "$SSH_KEY_PATH" -N ""
    
    if [ $? -eq 0 ]; then
        log "✅ SSH 키 생성 완료: $SSH_KEY_PATH"
    else
        log "❌ SSH 키 생성 실패"
        exit 1
    fi
else
    log "✅ SSH 키가 이미 존재합니다: $SSH_KEY_PATH"
fi

# 2. 권한 설정
chmod 600 "$SSH_KEY_PATH"
chmod 644 "$SSH_PUB_KEY_PATH"
log "✅ SSH 키 권한 설정 완료"

# 3. 공개 키 내용 확인
log ""
log "=========================================="
log "공개 키 내용:"
log "=========================================="
cat "$SSH_PUB_KEY_PATH"
log "=========================================="
log ""

# 4. Oracle에 공개 키 등록 (한 줄 명령어)
log "Oracle에 공개 키 등록 중..."
log "비밀번호를 입력해주세요."
log ""

cat "$SSH_PUB_KEY_PATH" | ssh "$ORACLE_USER@$ORACLE_HOST" \
    "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"

if [ $? -eq 0 ]; then
    log ""
    log "✅ 공개 키 등록 완료"
else
    log ""
    log "❌ 공개 키 등록 실패"
    log ""
    log "수동으로 등록하려면 다음 단계를 따르세요:"
    log "1. Oracle에 SSH 접속:"
    log "   ssh $ORACLE_USER@$ORACLE_HOST"
    log ""
    log "2. Oracle에서 다음 명령어 실행:"
    log "   mkdir -p ~/.ssh"
    log "   chmod 700 ~/.ssh"
    log "   echo \"$(cat $SSH_PUB_KEY_PATH)\" >> ~/.ssh/authorized_keys"
    log "   chmod 600 ~/.ssh/authorized_keys"
    log "   exit"
    exit 1
fi

# 5. 연결 테스트
log ""
log "=========================================="
log "SSH 연결 테스트 중..."
log "=========================================="

ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no "$ORACLE_USER@$ORACLE_HOST" "echo 'SSH 연결 성공!'"

if [ $? -eq 0 ]; then
    log ""
    log "✅ SSH 키 설정 완료!"
    log ""
    log "이제 다음 명령어로 동기화를 실행할 수 있습니다:"
    log "  bash scripts/sync/sync_to_oracle.sh"
else
    log ""
    log "❌ SSH 연결 실패"
    log "공개 키가 제대로 등록되었는지 확인해주세요."
    exit 1
fi

log "=========================================="
log "설정 완료"
log "=========================================="
