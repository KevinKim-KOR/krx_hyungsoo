#!/usr/bin/env bash
# scripts/linux/diagnostics/disable_regime_guard.sh
# 목적: scanner의 레짐 소프트게이트/벤치마크 의존 해제 (벤치마크 레이트리밋 우회)

set -euo pipefail
cd "$(dirname "$0")/../../.."

CFG="config/config.yaml"
BKP="config/config.yaml.bak.$(date +%F_%H%M%S)"
[ -f "$CFG" ] || { echo "[ERR] $CFG not found"; exit 2; }

cp -a "$CFG" "$BKP"
echo "[BACKUP] -> $BKP"

cat >> "$CFG" <<'EOF'

# --- [autopatch] scanner regime disable (diagnostics) ---
scanner:
  regime_softgate: false
  require_benchmark: false
  regime_provider: none
EOF

echo "[DONE] disabled regime gate and benchmark requirement in $CFG"
