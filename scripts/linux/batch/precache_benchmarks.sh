#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"
export ALLOW_NET_FETCH=1  # 프리캐시는 온라인 시도

bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log precache_bm \
    --guard td \
    -- \
    bash -c '
      set -e
      "$PYTHONBIN" - <<PY
import sys, json, datetime as dt
from pathlib import Path

# 1) 벤치마크 목록 결정
cfg_path = Path("config/data_sources.yaml")
benchmarks = ["KOSPI", "S&P500"]
try:
    import yaml
    if cfg_path.exists():
        y = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        if "benchmarks" in y:
            benchmarks = list(y["benchmarks"].keys()) or benchmarks
except Exception:
    pass

# 2) 기간: 최근 5년
end = dt.date.today().strftime("%Y-%m-%d")
start = (dt.date.today().replace(year=dt.date.today().year - 5)).strftime("%Y-%m-%d")

# 3) 로더 호출 (외부 오류는 상위 run_py_guarded로 처리)
from scripts.bt.data_loader import load_benchmark, ExternalDataUnavailable

ok = []
sk = []
for name in benchmarks:
    try:
        df = load_benchmark(name, start, end)
        ok.append(name)
    except ExternalDataUnavailable:
        sk.append(name)

print(f"[PRECACHE] ok={ok} skip={sk} range={start}~{end}")
PY
    '
