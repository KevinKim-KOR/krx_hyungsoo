#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate lightweight web index for backtests with:
- Export CSV of the current view
- Recent N filter
- Simple color dots based on Sharpe/MDD
Outputs: reports/index.json, reports/index.html
Env:
  WEB_BASE_PREFIX: base prefix for links from reports to backtests (default: "..")
"""
from __future__ import annotations

import json, os, re
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BT_DIR = ROOT / "backtests"
OUT_DIR = ROOT / "reports"
LINK_BASE = os.environ.get("WEB_BASE_PREFIX", "..")  # reports 기준 ../backtests

def _coerce_float(x):
    try:
        if x is None: return None
        if isinstance(x, (int, float)): return float(x)
        s = str(x).replace(",", "")
        return float(s)
    except Exception:
        return None

def _pick_meta(name: str) -> Dict[str, Optional[str]]:
    """
    Try to extract strategy/universe from filename or folder name.
    e.g., run_2025...__strat-xxx__uni-kr_all.csv
    """
    meta = {"strategy": None, "universe": None}
    if "__" in name:
        parts = name.split("__")
        for p in parts:
            if p.startswith("strat-"):
                meta["strategy"] = p[6:]
            if p.startswith("uni-"):
                meta["universe"] = p[4:]
    return meta

def _load_metrics_from_json(mfile: Path) -> Dict[str, Any]:
    d = json.loads(mfile.read_text(encoding="utf-8"))
    # Normalize keys
    def g(*keys, default=None):
        for k in keys:
            if k in d: return d[k]
        return default
    return {
        "strategy": g("strategy", "name"),
        "universe": g("universe", "univ"),
        "sharpe": _coerce_float(g("sharpe", "sharpe_ratio")),
        "cagr": _coerce_float(g("cagr", "annual_return", "ann_return")),
        "mdd": _coerce_float(g("mdd", "max_drawdown")),
        "winrate": _coerce_float(g("winrate", "win_rate")),
        "trades": int(g("trades", "num_trades", "n_trades", default=0) or 0),
        "pnl": _coerce_float(g("pnl", "final_pnl", "net_profit")),
    }

def _read_equity_curve_csv(fname: Path) -> Optional[List[float]]:
    try:
        df = pd.read_csv(fname)
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if not num_cols: return None
        # choose most variant numeric col for sparkline
        col = max(num_cols, key=lambda c: df[c].var())
        s = pd.to_numeric(df[col], errors="coerce").dropna().tail(60)
        if s.empty: return None
        mn, mx = float(s.min()), float(s.max())
        if mx == mn: return [0.5]*len(s)
        return [ (float(v)-mn)/(mx-mn) for v in s.tolist() ]
    except Exception:
        return None

def _gather_loose_csvs(bt_dir: Path) -> List[Dict[str, Any]]:
    out = []
    for csvf in sorted(bt_dir.glob("run_*.csv")):
        meta = _pick_meta(csvf.name)
        mt = datetime.fromtimestamp(csvf.stat().st_mtime)
        entry = {
            "run_id": csvf.stem,
            "started_at": mt.strftime("%Y-%m-%d %H:%M:%S"),
            "path": f"{LINK_BASE}/{csvf.name}",
            "folder": None,
            "strategy": meta.get("strategy"),
            "universe": meta.get("universe"),
            "sharpe": None, "cagr": None, "mdd": None,
            "winrate": None, "trades": None, "pnl": None,
            "spark": _read_equity_curve_csv(csvf),
        }
        out.append(entry)
    return out

def _gather_subdirs(bt_dir: Path) -> List[Dict[str, Any]]:
    out = []
    for d in sorted([p for p in bt_dir.iterdir() if p.is_dir()]):
        # look for metrics.json & equity_curve.csv
        mfile = d / "metrics.json"
        eq = d / "equity_curve.csv"
        meta = _pick_meta(d.name)
        mt = datetime.fromtimestamp(d.stat().st_mtime)
        base_link = f"{LINK_BASE}/{d.name}"
        entry = {
            "run_id": d.name,
            "started_at": mt.strftime("%Y-%m-%d %H:%M:%S"),
            "path": base_link + ("/metrics.json" if mfile.exists() else ""),
            "folder": f"{LINK_BASE}/{d.name}/",
            "strategy": meta.get("strategy"),
            "universe": meta.get("universe"),
            "sharpe": None, "cagr": None, "mdd": None,
            "winrate": None, "trades": None, "pnl": None,
            "spark": _read_equity_curve_csv(eq) if eq.exists() else None,
        }
        if mfile.exists():
            try:
                entry.update(_load_metrics_from_json(mfile))
            except Exception:
                pass
        out.append(entry)
    return out

def gather_runs() -> List[Dict[str, Any]]:
    BT_DIR.mkdir(exist_ok=True, parents=True)
    runs = []
    runs.extend(_gather_subdirs(BT_DIR))
    runs.extend(_gather_loose_csvs(BT_DIR))
    # sort desc by started_at
    def k(e): 
        try:
            return datetime.strptime(e["started_at"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime.fromtimestamp(0)
    runs.sort(key=k, reverse=True)
    return runs

def build_html(rows: List[Dict[str, Any]]) -> str:
    # minimal CSS/JS; client-side sort/filter/export
    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Backtests Index</title>
<style>
:root {{
  --muted:#f8f8fb; --line:#e5e7eb; --txt:#111827;
}}
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:20px;color:var(--txt)}}
h2{{margin:0 0 12px 0}}
.toolbar{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0 16px 0}}
select,input,button{{padding:6px 8px}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid var(--line);padding:8px;font-size:14px}}
th{{background:var(--muted);text-align:left;cursor:pointer;user-select:none}}
td.num{{text-align:right}}
.badge{{background:#eef;border:1px solid #ccd;border-radius:6px;padding:2px 6px;font-size:12px}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:5px;margin-right:6px;vertical-align:middle;border:1px solid #0001}}
td.spark svg{{display:block}}
caption{{text-align:left;margin:0 0 6px 0;font-weight:600}}
</style>
</head>
<body>
<h2>Backtests Index <span class="badge">{len(rows)} runs</span></h2>

<div class="toolbar">
  <label>최근
    <select id="recentN">
      <option value="all">전체</option>
      <option>10</option>
      <option selected>30</option>
      <option>50</option>
      <option>100</option>
    </select> 개</label>
  <label>전략
    <input id="q" type="search" placeholder="strategy/universe 검색">
  </label>
  <button id="export">Export CSV</button>
</div>

<table id="tbl">
  <caption>runs</caption>
  <thead>
    <tr>
      <th data-k="started_at">Date</th>
      <th data-k="run_id">Run</th>
      <th data-k="strategy">Strategy</th>
      <th data-k="universe">Universe</th>
      <th data-k="sharpe" class="num">Sharpe</th>
      <th data-k="cagr" class="num">CAGR</th>
      <th data-k="mdd" class="num">MDD</th>
      <th data-k="winrate" class="num">Win%</th>
      <th data-k="trades" class="num">Trades</th>
      <th data-k="pnl" class="num">PnL</th>
      <th>Spark</th>
    </tr>
  </thead>
  <tbody></tbody>
</table>

<script>
const ROWS = {json.dumps(rows, ensure_ascii=False)};
let sortKey = "started_at";
let sortAsc = false;

function formatNum(v, pct=false) {{
  if (v === null || v === undefined || isNaN(v)) return "";
  const n = Number(v);
  return pct ? (n*100).toFixed(2) + "%" : n.toFixed(3);
}}

function sparkSVG(vals) {{
  if (!vals || vals.length < 2) return "";
  const w = 80, h = 28;
  const pts = vals.map((v,i)=>[i*(w/(vals.length-1)), (1-v)*h]);
  const d = "M"+pts.map(p=>p[0].toFixed(1)+","+p[1].toFixed(1)).join(" L");
  return `<svg width="${{w}}" height="${{h}}" viewBox="0 0 ${{w}} ${{h}}"><path d="${{d}}" fill="none" stroke="currentColor" stroke-width="1"/></svg>`;
}}

function colorDot(sharpe, mdd) {{
  let color = "#dc2626"; // red
  if (sharpe !== null && sharpe !== undefined) {{
    if (sharpe >= 1.0 && (mdd === null || mdd >= -0.2)) color = "#16a34a";
    else if (sharpe >= 0.5) color = "#ca8a04";
  }}
  return `<span class="dot" style="background:${{color}}"></span>`;
}}

function cmp(a,b,k) {{
  const va = a[k], vb = b[k];
  if (va === vb) return 0;
  if (va === null || va === undefined) return 1;
  if (vb === null || vb === undefined) return -1;
  if (k === "started_at") return (new Date(va) - new Date(vb));
  if (typeof va === "number" && typeof vb === "number") return va - vb;
  return (""+va).localeCompare(""+vb);
}}

function currentView() {{
  const N = document.querySelector("#recentN").value;
  const q = document.querySelector("#q").value.toLowerCase();
  let arr = Array.from(ROWS);
  // filter by recent N (already sorted desc by date)
  arr.sort((a,b)=> cmp(a,b,"started_at")).reverse();
  if (N !== "all") {{
    const n = parseInt(N);
    if (!isNaN(n)) arr = arr.slice(0, n);
  }}
  // search on strategy/universe
  if (q) {{
    arr = arr.filter(r => (r.strategy||"").toLowerCase().includes(q) || (r.universe||"").toLowerCase().includes(q));
  }}
  // sort
  arr.sort((a,b)=> sortAsc ? cmp(a,b,sortKey) : cmp(b,a,sortKey));
  return arr;
}}

function render() {{
  const tbody = document.querySelector("#tbl tbody");
  tbody.innerHTML = "";
  for (const r of currentView()) {{
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${{r.started_at}}</td>
      <td><a href="${{r.folder || r.path}}" target="_blank">${{colorDot(r.sharpe, r.mdd)}}${{r.run_id}}</a></td>
      <td>${{r.strategy||""}}</td>
      <td>${{r.universe||""}}</td>
      <td class="num">${{formatNum(r.sharpe)}}</td>
      <td class="num">${{formatNum(r.cagr, true)}}</td>
      <td class="num">${{formatNum(r.mdd, true)}}</td>
      <td class="num">${{formatNum(r.winrate, true)}}</td>
      <td class="num">${{r.trades||""}}</td>
      <td class="num">${{formatNum(r.pnl)}}</td>
      <td class="spark">${{sparkSVG(r.spark)}}</td>
    `;
    tbody.appendChild(tr);
  }}
}}

function exportCSV() {{
  const rows = currentView();
  const headers = ["started_at","run_id","strategy","universe","sharpe","cagr","mdd","winrate","trades","pnl"];
  const lines = [headers.join(",")];
  for (const r of rows) {{
    const vals = headers.map(h => r[h]===null||r[h]===undefined?"":r[h]);
    lines.push(vals.join(","));
  }}
  const blob = new Blob([lines.join("\\n")], {{type:"text/csv;charset=utf-8;"}});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "index_view.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}}

document.querySelector("#export").addEventListener("click", exportCSV);
document.querySelector("#recentN").addEventListener("change", render);
document.querySelector("#q").addEventListener("input", render);
document.querySelectorAll("th[data-k]").forEach(th => {{
  th.addEventListener("click", () => {{
    const k = th.getAttribute("data-k");
    if (sortKey === k) sortAsc = !sortAsc; else {{ sortKey = k; sortAsc = (k==="run_id"||k==="strategy"||k==="universe"); }}
    render();
  }});
}});

render();
</script>
</body></html>
"""
    return html

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = gather_runs()
    # dump json
    (OUT_DIR / "index.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    # html
    (OUT_DIR / "index.html").write_text(build_html(rows), encoding="utf-8")
    print(f"[INDEX] wrote {OUT_DIR/'index.json'} and {OUT_DIR/'index.html'}")

if __name__ == "__main__":
    raise SystemExit(main())
