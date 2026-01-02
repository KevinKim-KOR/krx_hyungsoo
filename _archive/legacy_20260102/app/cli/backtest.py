import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

# Minimal inbox processor to align with NEW docs.
# Reads *.json requests from --inbox and dispatches to pc/app_pc.py backtest.

def _dispatch_backtest(req: Dict[str, Any]) -> int:
    # Expect keys like: start, end, strategy, universe, output_dir, etc.
    # We delegate to pc/app_pc.py backtest with supported arguments.
    import runpy
    import shlex

    argv = ["pc/app_pc.py", "backtest"]
    if "start" in req: argv += ["--start", str(req["start"])]
    if "end" in req: argv += ["--end", str(req["end"])]
    # Strategy/universe mapping is repository-specific; pass-through as labels
    if "strategy" in req: argv += ["--label", str(req["strategy"])]
    if "universe" in req: argv += ["--universe", str(req["universe"])]

    sys.argv = argv
    try:
        runpy.run_path("pc/app_pc.py", run_name="__main__")
        return 0
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 1


def run(argv=None):
    parser = argparse.ArgumentParser(prog="app.cli.backtest", description="Backtest inbox runner (adapter)")
    parser.add_argument("run", nargs="?")  # allow `run` subcommand like docs
    parser.add_argument("--inbox", default="reports/pending")
    parser.add_argument("--out", default="reports/done")
    args = parser.parse_args(argv)

    inbox = Path(args.inbox)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if not inbox.exists():
        print(f"[WARN] inbox not found: {inbox}")
        return 0

    for p in sorted(inbox.glob("*.json")):
        try:
            req = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[ERROR] invalid request {p.name}: {e}")
            p.rename(out / f"{p.stem}.error.json")
            continue
        rc = _dispatch_backtest(req)
        target = out / f"{p.stem}.rc{rc}.json"
        p.rename(target)
        print(f"[INFO] processed {p.name} -> {target.name} (rc={rc})")
    return 0

if __name__ == "__main__":
    sys.exit(run())
