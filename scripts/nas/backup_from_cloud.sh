#!/bin/bash
# scripts/nas/backup_from_cloud.sh
# NAS에서 실행: Oracle Cloud의 데이터를 NAS로 백업 (rsync)
# 실행 주기: 매일 새벽 (Cloud 작업 완료 후)

# 설정 (사용자 환경에 맞게 수정 필요)
# config/env.nas.sh 파일이 있으면 로드하여 설정 덮어쓰기
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
CONFIG_FILE="$PROJECT_ROOT/config/env.nas.sh"

if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

CLOUD_USER="${CLOUD_USER:-ubuntu}"
CLOUD_IP="${CLOUD_IP:-YOUR.ORACLE.CLOUD.IP}"  # config/env.nas.sh에 CLOUD_IP 설정 필요
CLOUD_KEY="${CLOUD_KEY:-/volume2/homes/Hyungsoo/.ssh/oracle_key}" # SSH 키 경로

# IP 설정 확인
if [ "$CLOUD_IP" = "YOUR.ORACLE.CLOUD.IP" ]; then
    echo "❌ 오류: CLOUD_IP가 설정되지 않았습니다."
    echo "👉 config/env.nas.sh 파일을 생성하고 아래 내용을 추가하세요:"
    echo "export CLOUD_IP=\"오라클_클라우드_IP\""
    exit 1
fi

REMOTE_DIR="/home/ubuntu/krx_hyungsoo/data/"
LOCAL_DIR="/volume2/homes/Hyungsoo/krx/krx_alertor_modular/data/"

# 로그 설정
LOG_FILE="/volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs/backup_from_cloud.log"

echo "[$(date)] 백업 시작: Cloud($CLOUD_IP) -> NAS" | tee -a "$LOG_FILE"

# rsync 실행 (아카이브 모드, 압축, 상세 출력, 삭제된 파일 반영)
# --delete: Cloud에 없는 파일은 NAS에서도 삭제 (동기화)
rsync -avz --delete -e "ssh -i $CLOUD_KEY" \
    "${CLOUD_USER}@${CLOUD_IP}:${REMOTE_DIR}" \
    "$LOCAL_DIR" \
    >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "[$(date)] ✅ 백업 성공" | tee -a "$LOG_FILE"
else
    echo "[$(date)] ❌ 백업 실패" | tee -a "$LOG_FILE"
fi
