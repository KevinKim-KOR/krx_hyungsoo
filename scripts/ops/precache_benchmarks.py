#!/usr/bin/env python3
import sys, os
from pathlib import Path
from datetime import datetime, timedelta

# repo root on sys.path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.bt.data_loader import load_benchmark  # 프로젝트 내 모듈 사용

def day(n): return (datetime.today() + timedelta(days=n)).strftime("%Y-%m-%d")

def main():
    import argparse, yaml
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=None)
    ap.add_argument("--end",   default=None)
    ap.add_argument("--names", default=None, help="comma list e.g. KOSPI,S&P500")
    args = ap.parse_args()

    start = args.start or day(-5*365)   # 최근 5년 기본
    end   = args.end   or day(0)

    # 이름 소스: CLI > config/data_sources.yaml > 기본값
    names = []
    if args.names:
        names = [s.strip() for s in args.names.split(",") if s.strip()]
    else:
        cfg = ROOT / "config" / "data_sources.yaml"
        if cfg.exists():
            try:
                y = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
                names = y.get("benchmarks", []) or []
            except Exception:
                names = []
    if not names:
        names = ["KOSPI", "S&P500"]

    print(f"[PRECACHE] {names} {start}~{end}")
    failed = []
    for name in names:
        try:
            _ = load_benchmark(name, start, end)
            print(f"[OK] {name}")
        except Exception as e:
            print(f"[WARN] {name} failed: {e}", file=sys.stderr)
            failed.append(name)

    # 일부/전부 실패 시 재시도 유도를 위해 RC=2 반환
    return 0 if not failed else 2

if __name__ == "__main__":
    sys.exit(main())
