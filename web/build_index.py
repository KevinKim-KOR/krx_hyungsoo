#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtests Web Index (stdlib only)
- Recent-N, search, sort, export CSV, color dots
- Robust path detection:
  * Repo root auto-discovery
  * Support both layouts:
      A) <repo>/reports/backtests/...
      B) <repo>/backtests/...
- Outputs: <repo>/reports/index.json, <repo>/reports/index.html
"""
from __future__ import annotations

import json, os, csv
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

# ---------- Path discovery ----------
def _is_repo_root(p: Path) -> bool:
    # Heuristics: must have "web" dir and either "scripts" or "config"
    return (p / "web").is_dir() and ((p / "scripts").is_dir() or (p / "config").is_dir())

def _find_repo_root() -> Path:
    here = Path(__file__).resolve().parent  # e.g., .../web
    for up in [here] + list(here.parents):
        if _is_repo_root(up):
            return up
    # Fallback: if this file is under .../web, parent is repo root
    if here.name == "web":
        return here.parent
    return Path.cwd()

ROOT = _find_repo_root()
OUT_DIR = ROOT / "reports"

# Decide backtests directory (supports both layouts)
BT_DIR_A = OUT_DIR / "backtests"      # <repo>/reports/backtests
BT_DIR_B = ROOT / "backtests"         # <repo>/backtests
BT_DIR = BT_DIR_A if BT_DIR_A.exists() else BT_DIR_B

# Decide link base (href from reports/index.html to backtests)
def _decide_link_base() -> str:
    # Allow explicit override first
    env = os.environ.get("WEB_BASE_PREFIX")
    if env:
        return env
    if BT_DIR == BT_DIR_A:
        return "backtests"          # reports/index.html -> reports/backtests
    elif BT_DIR == BT_DIR_B:
        return "../backtests"       # reports/index.html -> ../backtests
    return "."                      # safe fallback

LINK_BASE = _decide_link_base()

# ---------- Helpers ----------
def _coerce_float(x):
    try:
        if x is None: return None
        if isinstance(x, (int, float)): return float(x)
        s = str(x).strip().replace(",", "")
        if s == "": return None
        return float(s)
    except Exception:
        return None

def _pick_meta(name: str) -> Dict[str, Optional[str]]:
    meta = {"strategy": None, "universe": None}
    if "__" in name:
        for p in name.split("__"):
            if p.startswith("strat-"):
                meta["strategy"] = p[6:]
            if p.startswith("uni-"):
                meta["universe"] = p[4:]
    return meta

def _load_metrics_from_json(mfile: Path) -> Dict[str, Any]:
    d = json.loads(mfile.read_text(encoding="utf-8"))
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

def _read_csv_first_numeric_series(fname: Path, max_rows: int = 500) -> Optional[List[float]]:
    try:
        with fname.open("r", encoding="utf-8", newline="") as f:
            rdr = csv.reader(f)
            headers = next(rdr, None)
            if not headers: return None
            cols = [[] for _ in headers]
            rows = 0
            for row in rdr:
                rows += 1
                for i, v in enumerate(row):
                    fv = _coerce_float(v)
                    cols[i].append(fv)
                if rows >= max_rows:
                    break
        num_cols = []
        for i, series in enumerate(cols):
            vals = [v for v in series if isinstance(v, (int, float)) and v is not None]
            if not series: continue
            if len(vals) / max(1, len(series)) >= 0.5:
                if len(vals) >= 2:
                    m = sum(vals) / len(vals)
                    var = sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
                else:
                    var = 0.0
                num_cols.append((i, vals, var))
        if not num_cols:
            return None
        _, vals, _ = max(num_cols, key=lambda t: t[2])
        vals = vals[-60:] if len(vals) > 60 else vals
        if not vals: return None
        mn, mx = min(vals), max(vals)
        if mx == mn: return [0.5] * len(vals)
        return [(v - mn) / (mx - mn) for v in vals]
    except Exception:
        return None

def _gather_loose_csvs(bt_dir: Path) -> List[Dict[str, Any]]:
    out = []
    for csvf in sorted(bt_dir.glob("run_*.csv")):
        meta = _pick_meta(csvf.name)
        mt = datetime.fromtimestamp(csvf.stat().st_mtime)
        out.append({
            "run_id": csvf.stem,
            "started_at": mt.strftime("%Y-%m-%d %H:%M:%S"),
            "path": f"{LINK_BASE}/{csvf.name}",
            "folder": None,
            "strategy": meta.get("strategy"),
            "universe": meta.get("universe"),
            "sharpe": None, "cagr": None, "mdd": None,
            "winrate": None, "trades": None, "pnl": None,
            "spark": _read_csv_first_numeric_series(csvf),
        })
    return out

def _gather_subdirs(bt_dir: Path) -> List[Dict[str, Any]]:
    out = []
    for d in sorted([p for p in bt_dir.iterdir() if p.is_dir()]):
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
            "spark": _read_csv_first_numeric_series(eq) if eq.exists() else None,
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
    def k(e):
        try:
            return datetime.strptime(e["started_at"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime.fromtimestamp(0)
    runs.sort(key=k, reverse=True)
    return runs

def build_html(rows: List[Dict[str, Any]]) -> str:
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Backtests Index</title>
<style>
:root {{ --muted:#f8f8fb; --line:#e5e7eb; --txt:#111827; }}
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
const ROWS = {json.dumps(gather_runs(), ensure_ascii=False)};
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
  let color = "#dc2626";
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
  arr.sort((a,b)=> cmp(a,b,"started_at")).reverse();
  if (N !== "all") {{
    const n = parseInt(N);
    if (!isNaN(n)) arr = arr.slice(0, n);
  }}
  if (q) {{
    arr = arr.filter(r => (r.strategy||"").toLowerCase().includes(q) || (r.universe||"").toLowerCase().includes(q));
  }}
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

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "index.json").write_text(
        json.dumps(gather_runs(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "index.html").write_text(build_html([]), encoding="utf-8")
    print(f"[INDEX] wrote {OUT_DIR/'index.json'} and {OUT_DIR/'index.html'}")

if __name__ == "__main__":
    raise SystemExit(main())
