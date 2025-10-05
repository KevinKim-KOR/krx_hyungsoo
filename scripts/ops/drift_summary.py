#!/usr/bin/env python3
import re, json, sys
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parents[2]

def _read_metrics(run_dir: Path):
    m = run_dir / "metrics.json"
    if not m.exists():
        return None
    try:
        d = json.loads(m.read_text(encoding="utf-8"))
        return {
            "Final_Return": d.get("Final_Return"),
            "CAGR_like": d.get("CAGR_like"),
            "MDD": d.get("MDD"),
            "period": d.get("period", {}),
            "strategy": d.get("strategy", ""),
        }
    except Exception:
        return None

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--date", default=str(date.today()))
    args = ap.parse_args()

    log = ROOT / "logs" / f"compare_{args.strategy}_{args.date}.log"
    if not log.exists():
        print(f"[NO-DRIFT] compare log not found: {log}")
        return 0

    txt = log.read_text(encoding="utf-8", errors="ignore")
    if "[RESULT] DRIFT" not in txt:
        print(f"[NO-DRIFT] no drift in {log.name}")
        return 0

    # 마지막 블록에서 A/B 폴더 추출
    lines = [l for l in txt.splitlines() if "A(baseline)=" in l or "B(candidate)=" in l]
    if not lines:
        print("[DRIFT] (no details)")
        return 0
    a_line = [l for l in lines if "A(baseline)=" in l][-1]
    b_line = [l for l in lines if "B(candidate)=" in l][-1]
    A = Path(re.search(r"A\(baseline\)=(\S+)", a_line).group(1))
    B = Path(re.search(r"B\(candidate\)=(\S+)", b_line).group(1))

    a = _read_metrics(ROOT / A)
    b = _read_metrics(ROOT / B)

    # 요약 메시지
    msg = []
    msg.append(f"[DRIFT] {args.strategy} @ {args.date}")
    msg.append(f"A: {A.name}")
    if a:
        msg.append(f"   Final={a['Final_Return']:.4f}, CAGR={a['CAGR_like']:.4f}, MDD={a['MDD']:.4f}")
    msg.append(f"B: {B.name}")
    if b:
        msg.append(f"   Final={b['Final_Return']:.4f}, CAGR={b['CAGR_like']:.4f}, MDD={b['MDD']:.4f}")
    msg.append(f"paths:\n - {A}\n - {B}")
    print("\n".join(msg))
    return 0

if __name__ == "__main__":
    sys.exit(main())
