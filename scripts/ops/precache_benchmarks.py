#!/usr/bin/env python3
import sys, os, signal, time
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.bt.data_loader import load_benchmark

def day(n): return (datetime.today() + timedelta(days=n)).strftime("%Y-%m-%d")

class Timeout:
    def __init__(self, seconds: int):
        self.seconds = seconds
        self.enabled = hasattr(signal, "SIGALRM")  # Unix only
    def __enter__(self):
        if self.enabled and self.seconds > 0:
            signal.signal(signal.SIGALRM, self._raise)
            signal.alarm(self.seconds)
    def __exit__(self, exc_type, exc, tb):
        if self.enabled:
            signal.alarm(0)
    @staticmethod
    def _raise(*_): raise TimeoutError("operation timed out")

def main():
    import argparse, yaml
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=None)
    ap.add_argument("--end",   default=None)
    ap.add_argument("--names", default=None, help="comma list e.g. KOSPI,S&P500")
    args = ap.parse_args()

    start = args.start or day(-5*365)
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
                pass
    if not names:
        names = ["KOSPI", "S&P500"]

    tmo = int(os.getenv("PRECACHE_TIMEOUT_SEC", "90"))
    print(f"[PRECACHE] {names} {start}~{end} (timeout {tmo}s each)")

    failed = []
    for name in names:
        try:
            with Timeout(tmo):
                _ = load_benchmark(name, start, end)
            print(f"[OK] {name}")
        except Exception as e:
            print(f"[WARN] {name} failed: {e}", file=sys.stderr)
            failed.append(name)

    # 일부/전부 실패 → RC=2 (재시도 유도)
    return 0 if not failed else 2

if __name__ == "__main__":
    sys.exit(main())
