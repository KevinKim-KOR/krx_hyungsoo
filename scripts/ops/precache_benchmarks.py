#!/usr/bin/env python3
import sys, os
from pathlib import Path
from datetime import datetime, timedelta
from multiprocessing import Process, Queue

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def day(n): return (datetime.today() + timedelta(days=n)).strftime("%Y-%m-%d")

def _worker(q: Queue, name: str, start: str, end: str):
    """별도 프로세스에서 벤치마크 로드 실행."""
    try:
        from scripts.bt.data_loader import load_benchmark
        _ = load_benchmark(name, start, end)
        q.put(("ok", None))
    except Exception as e:
        q.put(("err", str(e)))

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
                b = y.get("benchmarks", [])
                if isinstance(b, dict):
                    names = list(b.keys())
                elif isinstance(b, list):
                    names = b
                else:
                    names = []
            except Exception:
                pass
    if not names:
        names = ["KOSPI", "S&P500"]

    tmo = int(os.getenv("PRECACHE_TIMEOUT_SEC", "90"))
    print(f"[PRECACHE] {names} {start}~{end} (timeout {tmo}s each)", flush=True)

    failed = []
    for name in names:
        q = Queue()
        p = Process(target=_worker, args=(q, name, start, end))
        p.start()
        p.join(timeout=tmo)

        if p.is_alive():
            # 타임아웃 → 강제 종료
            try:
                p.terminate()
            finally:
                p.join(3)
            print(f"[WARN] {name} timeout after {tmo}s", flush=True)
            failed.append(name)
            continue

        try:
            status, msg = q.get_nowait()
        except Exception:
            status, msg = ("err", "no result from worker")

        if status == "ok":
            print(f"[OK] {name}", flush=True)
        else:
            print(f"[WARN] {name} failed: {msg}", file=sys.stderr, flush=True)
            failed.append(name)

    # 일부/전부 실패 → RC=2 (재시도 유도)
    return 0 if not failed else 2

if __name__ == "__main__":
    sys.exit(main())
