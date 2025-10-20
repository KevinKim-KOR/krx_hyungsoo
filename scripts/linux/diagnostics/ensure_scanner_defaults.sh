#!/usr/bin/env bash
# scripts/linux/diagnostics/ensure_universe_defaults.sh
set -euo pipefail
cd "$(dirname "$0")/../../.."

CFG="config/config.yaml"
BKP="config/config.yaml.bak.$(date +%F_%H%M%S)"
UF="data/universe/yf_universe.txt"

[ -f "$CFG" ] || { echo "[ERR] $CFG not found"; exit 2; }

append_universe_block() {
  cp -a "$CFG" "$BKP"
  echo "[BACKUP] -> $BKP"
  cat >> "$CFG" <<'EOF'

# --- [autopatch] universe defaults (safe-fallback) ---
universe:
  source: file
  path: data/universe/yf_universe.txt
  # 아래 필터는 현재 비활성으로 0. UI/튜닝 단계에서 조정.
  min_avg_turnover: 0
  min_price_krw: 0
  allow_indices: true
EOF
  echo "[DONE] appended universe block into $CFG"
}

# 1) universe 블록 없으면 추가
if ! grep -qE '^[[:space:]]*universe:' "$CFG"; then
  append_universe_block
else
  echo "[OK] universe block already present. no change."
fi

# 2) 유니버스 파일 보정(없거나 0줄이면 시드 주입)
mkdir -p "$(dirname "$UF")"
lines=0
[ -f "$UF" ] && lines=$(wc -l < "$UF" || echo 0)
if [ "$lines" -eq 0 ]; then
  cat > "$UF" <<'EOF'
SPY
QQQ
SOXX
VOO
VTI
SCHD
TLT
^KS11
EOF
  echo "[WRITE] seeded $UF (8)"
else
  echo "[OK] $UF already has $lines lines"
fi

