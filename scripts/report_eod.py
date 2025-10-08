#!/usr/bin/env python3
import sys, importlib, argparse, inspect

def _import_module(name):
    return importlib.import_module(name)

def _call_if_exists(mod, func_name, date):
    fn = getattr(mod, func_name, None)
    if callable(fn):
        # run(date) or report(date) or generate_eod_report(date)
        try:
            return fn(date=date) if "date" in inspect.signature(fn).parameters else fn(date)
        except TypeError:
            # 혹시 시그니처가 다르면 그냥 단일 인자로도 시도
            return fn(date)
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="auto")
    args = ap.parse_args()

    try:
        mod = _import_module("reporting_eod")
    except Exception as e:
        print(f"[ERROR] import reporting_eod failed: {e}", file=sys.stderr)
        sys.exit(1)

    # 우선순위대로 시도
    for name in ("run", "report", "generate_eod_report"):
        out = _call_if_exists(mod, name, args.date)
        if out is not None:
            return 0

    # 마지막으로 main(args) 시도
    main_fn = getattr(mod, "main", None)
    if callable(main_fn):
        main_fn(args)
        return 0

    print("[ERROR] reporting_eod entry not found (expected run()/report()/generate_eod_report() or main(args))", file=sys.stderr)
    return 1

if __name__ == "__main__":
    sys.exit(main())
