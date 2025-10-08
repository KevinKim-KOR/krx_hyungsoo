#!/usr/bin/env python3
# scripts/report_eod.py
from __future__ import annotations
import sys, argparse, subprocess, inspect
from pathlib import Path
import importlib

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_FILE = Path(__file__).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _call_entrypoints(mod, date_arg: str):
    """reporting_eod 모듈에서 다양한 엔트리포인트를 시도하고, 성공 시 RC(int)를 반환."""
    candidates = (
        "run", "main", "generate_eod_report", "generate",
        "report_eod", "report", "make_eod_report", "make_report",
    )
    for name in candidates:
        fn = getattr(mod, name, None)
        if not callable(fn):
            continue
        # 어댑터 자기 자신(main 등)을 잘못 잡아오는 경우 스킵
        try:
            src = Path(inspect.getsourcefile(fn) or "")
            if src == ADAPTER_FILE:
                continue
        except Exception:
            pass

        try:
            sig = inspect.signature(fn)
            params = sig.parameters
            if "date" in params:
                rc = fn(date=date_arg)
            elif "asof" in params:
                rc = fn(asof=date_arg)
            elif len(params) == 1:
                rc = fn(argparse.Namespace(date=date_arg))
            else:
                rc = fn()
            return int(rc) if rc is not None else 0
        except SystemExit as e:
            return int(getattr(e, "code", 0) or 0)
        except Exception:
            # 다른 후보 계속 시도
            continue
    return None

def main():
    ap = argparse.ArgumentParser(description="EOD report runner adapter")
    ap.add_argument("--date", default="auto", help="YYYY-MM-DD or 'auto'")
    args = ap.parse_args()
    date_arg = args.date

    # 1) 모듈 임포트 시도
    mod = None
    try:
        mod = importlib.import_module("reporting_eod")
    except Exception:
        mod = None

    # 2) 모듈이 로드되면 엔트리포인트 호출 → 실패 시 파일 자체 실행
    if mod:
        rc = _call_entrypoints(mod, date_arg)
        if rc is not None:
            return rc
        try:
            file_path = Path(mod.__file__)
            return subprocess.call([sys.executable, str(file_path), "--date", date_arg])
        except Exception:
            pass
        print("[ERROR] reporting_eod entry not found (expected main(args) or run(date=...))", file=sys.stderr)
        return 1

    # 3) 마지막 폴백: 루트의 파일 실행
    file_path = ROOT / "reporting_eod.py"
    if file_path.exists():
        return subprocess.call([sys.executable, str(file_path), "--date", date_arg])

    print("[ERROR] import reporting_eod failed and file not found", file=sys.stderr)
    return 1

if __name__ == "__main__":
    sys.exit(main() or 0)
