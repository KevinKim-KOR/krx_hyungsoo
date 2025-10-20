#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

CFG="config/config.yaml"
BKP="config/config.yaml.bak.$(date +%F_%H%M%S)"

if [ ! -f "$CFG" ]; then
  echo "[ERR] $CFG not found" >&2
  exit 2
fi

# 이미 키가 있으면 변경하지 않음
if grep -qE '^[[:space:]]*mfi_window:' "$CFG"; then
  echo "[OK] scanner.mfi_window already present. no change."
  exit 0
fi

cp -a "$CFG" "$BKP"
echo "[BACKUP] -> $BKP"

# YAML 최하단에 안전 기본값 블록 추가
cat >> "$CFG" <<'EOF'

# --- [autopatch] scanner defaults (safe-fallback) ---
scanner:
  mfi_window: 14
EOF

echo "[DONE] appended scanner.mfi_window: 14 into $CFG"
