#!/usr/bin/env python3
# scripts/report_eod.py
import sys, argparse

try:
    import reporting_eod as mod
except Exception as e:
    print(f"[ERROR] import reporting_eod failed: {e}", file=sys.stderr)
    sys.exit(1)

def _ns(**kw):
    return argparse.Namespace(**kw)

def main():
    ap = argparse.ArgumentParser(description="EOD report runner adapter")
    ap.add_argument("--date", default="auto", help="YYYY-MM-DD or 'auto'")
    args = ap.parse_args()

    # 1) run(date=...) 우선
    if hasattr(mod, "run"):
        return mod.run(date=args.date)

    # 2) main(...) 다양한 시그니처 방어적으로 시도
    if hasattr(mod, "main"):
        for call in (
            lambda: mod.main(args),
            lambda: mod.main(_ns(date=args.date)),
            lambda: mod.main(),  # 인자 없는 main
        ):
            try:
                return call()
            except TypeError:
                continue
            except Exception as e:
                print(f"[WARN] reporting_eod.main call failed: {e}", file=sys.stderr)
                break

    print("[ERROR] reporting_eod entry not found (expected main(args) or run(date=...))", file=sys.stderr)
    return 1

if __name__ == "__main__":
    sys.exit(main() or 0)
