#!/bin/bash
# scripts/automation/cron_wrapper.sh
# Crontab용 래퍼 스크립트 - 환경변수 및 경로 설정

# 프로젝트 경로
PROJECT_DIR="/volume2/homes/Hyungsoo/krx/krx_alertor_modular"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/cron_$(date +%Y%m%d).log"

# 로그 디렉토리 생성
mkdir -p "${LOG_DIR}"

# 로그 시작
echo "=== $(date '+%Y-%m-%d %H:%M:%S') Cron 시작 ===" >> "${LOG_FILE}"

# 환경변수 설정 (NAS Python 경로)
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
export PYTHONPATH="${PROJECT_DIR}"

# Python 경로 확인 (NAS에 맞게 수정 필요)
PYTHON_PATH="/usr/local/bin/python3"

# Python 경로가 없으면 대체 경로 시도
if [ ! -f "${PYTHON_PATH}" ]; then
    PYTHON_PATH=$(which python3 2>/dev/null || which python 2>/dev/null)
fi

echo "Python 경로: ${PYTHON_PATH}" >> "${LOG_FILE}"
echo "작업 디렉토리: ${PROJECT_DIR}" >> "${LOG_FILE}"

# 작업 디렉토리로 이동
cd "${PROJECT_DIR}" || {
    echo "ERROR: 디렉토리 이동 실패" >> "${LOG_FILE}"
    exit 1
}

# 스크립트 실행 (인자로 전달된 명령)
if [ -n "$1" ]; then
    echo "실행 명령: $@" >> "${LOG_FILE}"
    ${PYTHON_PATH} "$@" >> "${LOG_FILE}" 2>&1
    EXIT_CODE=$?
    echo "종료 코드: ${EXIT_CODE}" >> "${LOG_FILE}"
else
    echo "ERROR: 실행할 스크립트가 지정되지 않음" >> "${LOG_FILE}"
    exit 1
fi

echo "=== $(date '+%Y-%m-%d %H:%M:%S') Cron 종료 ===" >> "${LOG_FILE}"
echo "" >> "${LOG_FILE}"

exit ${EXIT_CODE}
