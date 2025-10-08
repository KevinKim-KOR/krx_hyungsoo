#!/usr/bin/env python3
# scripts/report_eod.py
from __future__ import annotations
import sys, argparse, inspect
from pathlib import Path

# 1) 프로젝트 루트를 import 경로에 추가 (서브폴더 실행 보완)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 2) 대상 모듈 후보들: reporting_eod(권장) → report_eod(대안)
MOD_NAMES = ("reporting_eod", "report_eod")

def _import_module():
    last_err = None
    for name in MOD_NAMES:
        try:
            return __import__(name)
        except Exception as e:
            last_err = e
    print(f"[ERROR] import reporting_eod failed: {last_err}", file=sys.stderr)
    sys.exit(1)

def _ns(**kw):
    return argparse.Namespace(**kw)

def _try_call(fn, date_arg: str):
    """
    다양한 시그니처(run(date=...), main(args), main(), report(date), generate_eod_report(date) 등)를
    안전하게 시도하고, 성공시 반환값을 정수 RC로 변환해서 돌려줌.
    """
    try:
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())

        # date 인자를 직접 받는 케이스 우선
        if any(p.name in ("date", "asof") for p in params):
            rc = fn(date=date_arg) if "date" in {p.name for p in params} else fn(asof=date_arg)
        # argparse-style main(args)
        elif len(params) == 1 and params[0].annotation in (inspect._empty, argparse.Namespace):
            rc = fn(_ns(date=date_arg))
        # 인자 없이 동작
        elif len(params) == 0:
            rc = fn()
        # 기타: 그냥 한 번 date만 넣어본다(예외 무시)
        else:
            rc = fn(date_arg)
    except TypeError:
        return None
    except SystemExit as e:  # argparse 내부에서 sys.exit 사용 시
        return int(getattr(e, "code", 0) or 0)
    except Exception as e:
        print(f"[WARN] call failed: {fn.__name__}: {e}", file=sys.stderr)
        return None

    # 반환값이 None이면 0으로 간주
    try:
        return int(rc) if rc is not None else 0
    except Exception:
        return 0

def main():
    ap = argparse.ArgumentParser(description="EOD report runner adapter")
    ap.add_argument("--date", default="auto", help="YYYY-MM-DD or 'auto'")
    args = ap.parse_args()
    date_arg = args.date

    mod = _import_module()

    # 3) 시도할 엔트리포인트 후보들(우선순위)
    candidates = [
        "run",
        "main",
        "generate_eod_report",
        "generate",
        "report_eod",
        "report",
        "make_eod_report",
        "make_report",
    ]

    for name in candidates:
        fn = getattr(mod, name, None)
        if callable(fn):
            rc = _try_call(fn, date_arg)
            if rc is not None:
                return rc

    print("[ERROR] reporting_eod entry not found (expected main(args) or run(date=...))", file=sys.stderr)
    return 1

if __name__ == "__main__":
    sys.exit(main() or 0)
