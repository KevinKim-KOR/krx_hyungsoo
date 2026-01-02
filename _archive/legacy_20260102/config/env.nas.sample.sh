#!/usr/bin/env bash
# NAS 환경 예시 템플릿 — 실제 운영값에 맞게 복제/수정해서 config/env.nas.sh 로 사용하세요.

# Python interpreter in venv (권장)
PYTHONBIN="${PYTHONBIN:-$HOME/krx/krx_alertor_modular/venv/bin/python}"

# (선택) 웹 인덱스 산출물 루트 강제 — 경로 꼬임 방지
export WEB_REPO_ROOT="${WEB_REPO_ROOT:-$HOME/krx/krx_alertor_modular}"

# (선택) 기타 서비스용 변수들
export TZ="Asia/Seoul"

# PATH 보강(필요시)
# export PATH="$HOME/krx/krx_alertor_modular/venv/bin:$PATH"
