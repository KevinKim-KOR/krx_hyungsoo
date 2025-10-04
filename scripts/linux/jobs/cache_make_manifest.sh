#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
OUT="data/cache_manifest.sha"
mkdir -p data
echo "[CACHE] make manifest -> $OUT"
# 파일 수 많을 때도 안전하게 0-terminated
find data/cache -type f -print0 | sort -z | xargs -0 sha256sum > "$OUT"
echo "[DONE] entries: $(wc -l < "$OUT")"
