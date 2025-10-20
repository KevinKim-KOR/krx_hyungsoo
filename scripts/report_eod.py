#!/usr/bin/env python3
import sys, importlib, argparse, inspect
from pathlib import Path

# 프로젝트 루트 경로를 sys.path에 추가 (scripts/에서 루트 모듈 import 가능)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def _try_call(mod, names, date):
    for n in names:
        fn = getattr(mod, n, None)
        if callable(fn):
            try:
                return fn(date=date) if "date" in inspect.signature(fn).parameters else fn(date)
            except TypeError:
                try:
                    return fn(date)
                except TypeError:
                    pass
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="auto")
    args = ap.parse_args()

    try:
        mod = importlib.import_module("reporting_eod")
    except Exception as e:
        print(f"[ERROR] import reporting_eod failed: {e}")
        return 1

    # run()/report()/generate_eod_report() 우선 시도
    if _try_call(mod, ("run", "report", "generate_eod_report", "generate_and_send_report_eod"), args.date) is not None:
        return 0

    # main(args) 폴백
    main_fn = getattr(mod, "main", None)
    if callable(main_fn):
        main_fn(args)
        return 0

    print("[ERROR] reporting_eod entry not found (expected run()/report()/generate_eod_report() or main(args))")
    return 1

if __name__ == "__main__":
    sys.exit(main())
