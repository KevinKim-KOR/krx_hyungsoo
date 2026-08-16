#!/usr/bin/env bash
# macOS/Linux 版 stop — 기존 stop.bat 과 동일 목적 (포트 3000 / 8000 정리).
# Windows 는 netstat + taskkill, 여기서는 lsof + kill 로 같은 일을 한다.
#
# 2026-08-16 주인 확인 추가 — 3000(Next/React/Express) 과 8000(FastAPI/Django) 은
# 가장 흔한 개발 포트다. 포트 번호만 보고 죽이면 다른 프로젝트의 서버를 종료시킨다.
# 죽이기 전에 그 프로세스의 작업 디렉터리가 이 프로젝트 밑인지 확인한다.
# 확인이 안 되면(권한 부족 등) 죽이지 않는다 — 남의 것을 죽이는 쪽보다 안전하다.
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================"
echo "POC1 approval loop - stop"
echo "========================================"

found=0
skipped=0
for port in 3000 8000; do
    # -t: PID 만 / -i: 네트워크 / -sTCP:LISTEN: LISTEN 상태만 (연결 중인 클라이언트 제외)
    pids=$(lsof -t -i :"$port" -sTCP:LISTEN 2>/dev/null || true)
    for pid in $pids; do
        # -d cwd -Fn: 작업 디렉터리만 기계 판독 형식으로. 앞의 'n' 을 떼면 경로.
        cwd=$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | grep '^n' | sed 's/^n//' | head -1)
        case "$cwd" in
            "$PROJECT_DIR" | "$PROJECT_DIR"/*)
                echo "   - Port $port PID $pid terminated."
                kill "$pid" 2>/dev/null || true
                found=1
                ;;
            *)
                echo "   - Port $port PID $pid 는 이 프로젝트가 아님 — 건너뜀 (${cwd:-경로 확인 불가})"
                skipped=1
                ;;
        esac
    done
done

if [ "$found" -eq 0 ] && [ "$skipped" -eq 0 ]; then
    echo "   - No matching server running."
elif [ "$found" -eq 0 ]; then
    echo "   - 종료한 프로세스 없음. 위 포트는 다른 프로젝트가 쓰고 있다."
else
    echo "   - Stop complete."
fi

echo
echo "========================================"
echo "POC1 stop done"
echo "========================================"
