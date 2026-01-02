#!/usr/bin/env bash
set -euo pipefail

# 레포 루트로 이동
cd "$(dirname "$0")/../../.."

LOGDATE="$(date +%F)"
echo "=== HEALTHCHECK $(date '+%F %T') ==="

# [1] Git
echo "[1] Git"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
  HEAD="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
  echo "$BRANCH"
  echo "$HEAD"
else
  echo "git repo not found"
fi

# [2] Disk
echo "[2] Disk"
# /volume2 우선, 없으면 현재 파티션
if df -h /volume2 >/dev/null 2>&1; then
  df -h /volume2 | awk 'NR==2 {printf "%-18s %4s %4s %4s %3s %s\n",$1,$2,$3,$4,$5,$6}'
else
  df -h . | awk 'NR==2 {printf "%-18s %4s %4s %4s %3s %s\n",$1,$2,$3,$4,$5,$6}'
fi

# [3] Today logs
echo "[3] Today logs"
LOGDIR="logs"
mkdir -p "$LOGDIR"
SCN="$LOGDIR/scanner_${LOGDATE}.log"
RPT="$LOGDIR/report_${LOGDATE}.log"
if [ -s "$SCN" ]; then echo " - OK: $SCN"; else echo " - MISS: $SCN"; fi
if [ -s "$RPT" ]; then echo " - OK: $RPT"; else echo " - MISS: $RPT"; fi

# [4] Recent errors (48h)
echo "[4] Recent errors"
MARKER=".state/last_deploy"
HAS_ERR=0   # ← set -u 대비 초기화

if [ -f "$MARKER" ]; then
  echo "since $(cat .state/last_deploy.txt 2>/dev/null || echo 'last deploy')"
  mapfile -t ERRFILES < <(find logs -type f -newer "$MARKER" ! -name 'health_*.log' | sort)
else
  # 마커가 없을 땐 최근 로그만 제한적으로 스캔
  mapfile -t ERRFILES < <(find logs -type f -printf '%T@ %p\n' | sort -nr | head -n 20 | cut -d' ' -f2-)
fi

if [ ${#ERRFILES[@]} -eq 0 ]; then
  echo " - none since last deploy"
else
  for f in "${ERRFILES[@]}"; do
    # 필요하면 패턴 조정 가능(예: 외부 요인 소음 더 줄이기)
    HITS=$(grep -nE '(^Traceback|^\[ERROR\]|ERROR:yfinance)' "$f" | tail -n 10 || true)
    if [ -n "$HITS" ]; then
      echo "$f:"
      echo "$HITS"
      HAS_ERR=1
    fi
  done
  # 에러 파일을 순회했는데도 히트가 전혀 없으면 깔끔히 안내
  if [ "$HAS_ERR" -eq 0 ]; then
    echo " - none since last deploy"
  fi
fi



# [5] Locks
echo "[5] Locks"
LOCKDIR=".locks"
mkdir -p "$LOCKDIR"
# 상세 목록 (없으면 총계 0만 출력)
echo "total $(ls -1 "$LOCKDIR" 2>/dev/null | wc -l)"
ls -l "$LOCKDIR" 2>/dev/null || true

echo "=== END ==="

# (선택) 텔레그램 알림: 환경변수 있는 경우에만 전송, 없으면 조용히 스킵
if [ "${HAS_ERR}" -eq 1 ]; then
  if [ -x "scripts/linux/jobs/ping_telegram.sh" ]; then
    if [ -n "${TG_TOKEN:-}" ] && [ -n "${TG_CHAT_ID:-}" ]; then
      echo "[ALERT] send telegram"
      scripts/linux/jobs/ping_telegram.sh \
        "HEALTHCHECK ERRORS" \
        "최근 에러가 감지되었습니다. 로그를 확인하세요." \
        || echo "[ALERT] telegram failed (non-fatal)"
    else
      echo "[ALERT] skip: no TG_TOKEN/TG_CHAT_ID"
    fi
  fi
fi