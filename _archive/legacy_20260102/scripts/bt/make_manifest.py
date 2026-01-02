import argparse, json, hashlib, os
from pathlib import Path
from datetime import datetime

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_dir", required=True, help="backtests/<ts>_<strategy> 디렉토리")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    metrics_p = run_dir / "metrics.json"
    equity_p  = run_dir / "equity_curve.csv"

    if not metrics_p.exists() or not equity_p.exists():
        raise SystemExit(f"missing outputs in {run_dir}")

    metrics = json.loads(metrics_p.read_text(encoding="utf-8"))
    manifest = {
        "run_dir": str(run_dir),
        "strategy": metrics.get("strategy"),
        "period": metrics.get("period"),
        "hashes": {
            "metrics.json": sha256_file(metrics_p),
            "equity_curve.csv": sha256_file(equity_p),
        },
        "metrics": {
            "Final_Return": metrics["Final_Return"],
            "CAGR_like": metrics["CAGR_like"],
            "MDD": metrics["MDD"],
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("[MANIFEST] saved:", run_dir / "manifest.json")

if __name__ == "__main__":
    main()
