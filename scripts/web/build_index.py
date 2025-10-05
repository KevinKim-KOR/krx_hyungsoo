#!/usr/bin/env python3
import json, sys, os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
BT_DIR = ROOT / "backtests"
OUT_DIR = ROOT / "reports"

def load_metrics(run_dir: Path):
    m = run_dir / "metrics.json"
    if not m.exists():
        return None
    try:
        d = json.loads(m.read_text(encoding="utf-8"))
        d["_mtime"] = run_dir.stat().st_mtime
        d["_name"] = run_dir.name
        return d
    except Exception:
        return None

def gather(limit_per_strategy=20):
    runs = []
    if not BT_DIR.exists():
        return runs
    for p in sorted(BT_DIR.glob("*_*"), key=lambda x: x.stat().st_mtime, reverse=True):
        mt = load_metrics(p)
        if mt:
            runs.append(mt)
    # 전략별 상한
    by_strat = {}
    out = []
    for r in runs:
        s = r.get("strategy", "unknown")
        if by_strat.get(s, 0) < limit_per_strategy:
            out.append(r)
            by_strat[s] = by_strat.get(s, 0) + 1
    return out

def build_html(entries):
    rows = []
    for r in entries:
        ts = datetime.fromtimestamp(r["_mtime"]).strftime("%Y-%m-%d %H:%M")
        rows.append(
            f"<tr><td>{r.get('strategy','')}</td>"
            f"<td>{r.get('period',{}).get('start','')}~{r.get('period',{}).get('end','')}</td>"
            f"<td>{r.get('Final_Return','')}</td>"
            f"<td>{r.get('CAGR_like','')}</td>"
            f"<td>{r.get('MDD','')}</td>"
            f"<td>{ts}</td>"
            f"<td>{r.get('_name','')}</td></tr>"
        )
    table = "\n".join(rows) or "<tr><td colspan=7>No runs</td></tr>"
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Backtests Index</title>
<style>
body{{font-family:system-ui,Arial,sans-serif;margin:24px}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ddd;padding:8px;font-size:14px}}
th{{background:#f8f8f8;text-align:left}}
</style></head>
<body>
<h2>Backtests Index</h2>
<table>
<thead><tr><th>Strategy</th><th>Period</th><th>Final</th><th>CAGR</th><th>MDD</th><th>mtime</th><th>folder</th></tr></thead>
<tbody>
{table}
</tbody></table>
</body></html>"""

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = gather()
    # JSON
    (OUT_DIR / "index.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    # HTML
    (OUT_DIR / "index.html").write_text(build_html(entries), encoding="utf-8")
    print(f"[INDEX] wrote {OUT_DIR/'index.json'} and {OUT_DIR/'index.html'}")

if __name__ == "__main__":
    sys.exit(main())
