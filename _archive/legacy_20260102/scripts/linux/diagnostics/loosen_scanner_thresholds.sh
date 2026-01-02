#!/usr/bin/env bash
# scripts/linux/diagnostics/loosen_scanner_thresholds.sh
# 목적: config/config.yaml 의 scanner 임계치를 안전하게 완화(추가/재정의)
# - 기존 키가 있으면 유지하되, 하단에 "autopatch" 블록을 추가하여 느슨한 값으로 override
# - YAML 로더가 "마지막 값 우선"일 때만 유효(일반 PyYAML 로더 가정)

set -euo pipefail
cd "$(dirname "$0")/../../.."

CFG="config/config.yaml"
BKP="config/config.yaml.bak.$(date +%F_%H%M%S)"
[ -f "$CFG" ] || { echo "[ERR] $CFG not found"; exit 2; }

cp -a "$CFG" "$BKP"
echo "[BACKUP] -> $BKP"

cat >> "$CFG" <<'EOF'

# --- [autopatch] scanner loosen defaults (diagnostics) ---
scanner:
  # 윈도우 기본
  mfi_window: 14
  rsi_window: 14
  # 절대 느슨한 영역으로 override
  min_rsi: 0
  max_rsi: 100
  min_mfi: 0
  max_mfi: 100
  # 모멘텀/브레이크아웃류도 사실상 해제
  min_momentum_z: -9999
  min_breakout_score: -9999
  # 거래대금/가격 하한 0
  min_avg_turnover: 0
  min_price_krw: 0
EOF

echo "[DONE] appended loose scanner thresholds into $CFG"
