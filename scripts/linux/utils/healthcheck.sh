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
ERRS="$( (find logs -type f -mtime -2 -name "*.log" -print0 2>/dev/null || true) \
  | xargs -0 -I{} sh -c 'grep -HnE "ERROR|Traceback|Exception" "{}" || true' \
  | tail -n 20 || true)"
if [ -n "${ERRS}" ]; then
  echo "${ERRS}"
  HAS_ERR=1
else
  echo " - none"
  HAS_ERR=0
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