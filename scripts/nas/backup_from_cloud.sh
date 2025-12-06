#!/bin/bash
# scripts/nas/backup_from_cloud.sh
# NAS에서 실행: Oracle Cloud의 데이터를 NAS로 백업 (rsync)
# 실행 주기: 매일 새벽 (Cloud 작업 완료 후)

# 설정 (사용자 환경에 맞게 수정 필요)
CLOUD_USER="ubuntu"
CLOUD_IP="YOUR.ORACLE.CLOUD.IP"  # Oracle Cloud 공인 IP 입력
CLOUD_KEY="/volume2/homes/Hyungsoo/.ssh/oracle_key" # SSH 키 경로
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
