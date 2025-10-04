import argparse, json
from pathlib import Path
import math

def load_manifest(run_dir: Path) -> dict:
    p = run_dir / "manifest.json"
    if not p.exists():
        raise SystemExit(f"manifest not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))

def rel_diff(a, b):
    if a == b: return 0.0
    if a == 0: return float("inf")
    return abs(a-b)/abs(a)

def main():
    ap = argparse.ArgumentParser(description="compare two runs (A=baseline, B=candidate)")
    ap.add_argument("--a", required=True, help="baseline run_dir")
    ap.add_argument("--b", required=True, help="candidate run_dir")
    ap.add_argument("--tol-return", type=float, default=1e-4)   # 1bp
    ap.add_argument("--tol-cagr",   type=float, default=1e-4)
    ap.add_argument("--tol-mdd",    type=float, default=1e-4)
    ap.add_argument("--report_out", default="")
    args = ap.parse_args()

    A = load_manifest(Path(args.a))
    B = load_manifest(Path(args.b))

    diffs = {}
    fields = [("Final_Return","tol-return"),("CAGR_like","tol-cagr"),("MDD","tol-mdd")]
    ok = True
    for f, tol_name in fields:
        tol = getattr(args, tol_name.replace("-","_"))
        d = rel_diff(A["metrics"][f], B["metrics"][f])
        diffs[f] = d
        if not (math.isfinite(d) and d <= tol):
            ok = False

    same_hash = (A["hashes"]["equity_curve.csv"] == B["hashes"]["equity_curve.csv"])
    # 에퀴티 곡선 해시가 다르면 더 강한 시그널
    if not same_hash:
        ok = False

    lines = [
        f"[COMPARE] A(baseline)={args.a}",
        f"[COMPARE] B(candidate)={args.b}",
        f" - hash_equal: {same_hash}",
        f" - Final_Return rel_diff: {diffs['Final_Return']:.6g} (tol={args.tol_return})",
        f" - CAGR_like   rel_diff: {diffs['CAGR_like']:.6g} (tol={args.tol_cagr})",
        f" - MDD         rel_diff: {diffs['MDD']:.6g} (tol={args.tol_mdd})",
        f"[RESULT] {'OK' if ok else 'DRIFT'}"
    ]
    report = "\n".join(lines)
    if args.report_out:
        Path(args.report_out).write_text(report, encoding="utf-8")
    print(report)
    raise SystemExit(0 if ok else 2)

if __name__ == "__main__":
    main()
