#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtests Web Index (stdlib only; YAML optional)
- Recent-N, search, sort, export CSV, color dots
- Settings externalized to config/web_index.yaml (fallback safe)
- Robust path discovery & link base auto
- NEW: Allow explicit repo root override via WEB_REPO_ROOT env var
Outputs: <repo>/reports/index.json, <repo>/reports/index.html
"""
from __future__ import annotations

import json, os, csv
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

# ---------- Path discovery ----------
def _is_repo_root(p: Path) -> bool:
    # Heuristic: must have "web" dir and either "scripts" or "config"
    return (p / "web").is_dir() and ((p / "scripts").is_dir() or (p / "config").is_dir())

def _find_repo_root() -> Path:
    # 0) explicit override
    override = os.environ.get("WEB_REPO_ROOT")
    if override:
        return Path(override).resolve()
    # 1) walk up from this file
    here = Path(__file__).resolve().parent  # .../web
    for up in [here] + list(here.parents):
        if _is_repo_root(up):
            return up
    # 2) fallback: cwd if it looks like repo
    cwd = Path.cwd()
    if _is_repo_root(cwd):
        return cwd
    # 3) last resort: parent of this file
    return here.parent

ROOT = _find_repo_root()
OUT_DIR = ROOT / "reports"
CFG_FILE_YAML = ROOT / "config" / "web_index.yaml"
CFG_FILE_JSON = ROOT / "config" / "web_index.json"

# Decide backtests directory (supports both layouts)
BT_DIR_A = OUT_DIR / "backtests"      # <repo>/reports/backtests
BT_DIR_B = ROOT / "backtests"         # <repo>/backtests
BT_DIR = BT_DIR_A if BT_DIR_A.exists() else BT_DIR_B

def _decide_link_base() -> str:
    env = os.environ.get("WEB_BASE_PREFIX")
    if env:
        return env
    if BT_DIR == BT_DIR_A:
        return "backtests"
    elif BT_DIR == BT_DIR_B:
        return "../backtests"
    return "."

LINK_BASE = _decide_link_base()

# ---------- Config (YAML optional; fallback defaults) ----------
DEFAULT_SETTINGS: Dict[str, Any] = {
    "defaults": {"recentN": 30, "sort_key": "started_at", "sort_asc": False},
    "colors": {"sharpe": {"green": 1.0, "amber": 0.5}, "mdd": {"green_min": -0.2}},
    "columns": [
        {"key": "started_at", "label": "Date", "fmt": "none"},
        {"key": "run_id", "label": "Run", "fmt": "none"},
        {"key": "strategy", "label": "Strategy", "fmt": "none"},
        {"key": "universe", "label": "Universe", "fmt": "none"},
        {"key": "sharpe", "label": "Sharpe", "fmt": "num"},
        {"key": "cagr", "label": "CAGR", "fmt": "pct"},
        {"key": "mdd", "label": "MDD", "fmt": "pct"},
        {"key": "winrate", "label": "Win%", "fmt": "pct"},
        {"key": "trades", "label": "Trades", "fmt": "int"},
        {"key": "pnl", "label": "PnL", "fmt": "num"},
        {"key": "spark", "label": "Spark", "fmt": "none"},
    ],
}

def _load_settings() -> Dict[str, Any]:
    # YAML 우선, 실패 시 JSON, 둘 다 없으면 fallback
    if CFG_FILE_YAML.exists():
        try:
            import yaml  # type: ignore
            with CFG_FILE_YAML.open("r", encoding="utf-8") as f:
                s = yaml.safe_load(f) or {}
            print(f"[PRECHECK] OK: config={CFG_FILE_YAML} (used)")
            return _merge_settings(DEFAULT_SETTINGS, s)
        except Exception as e:
            print(f"[PRECHECK] WARN: YAML read failed ({CFG_FILE_YAML}): {e}")
    if CFG_FILE_JSON.exists():
        try:
            s = json.loads(CFG_FILE_JSON.read_text(encoding="utf-8"))
            print(f"[PRECHECK] OK: config={CFG_FILE_JSON} (used)")
            return _merge_settings(DEFAULT_SETTINGS, s)
        except Exception as e:
            print(f"[PRECHECK] WARN: JSON read failed ({CFG_FILE_JSON}): {e}")
    print(f"[PRECHECK] OK: config=fallback(defaults)")
    return DEFAULT_SETTINGS

def _merge_settings(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    out = json.loads(json.dumps(base))
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_settings(out[k], v)  # type: ignore
        else:
            out[k] = v
    return out

# ---------- Data helpers ----------
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

# ---------- HTML ----------
def build_html(rows: List[Dict[str, Any]], settings: Dict[str, Any]) -> str:
    cols = settings["columns"]
    recentN_default = settings["defaults"]["recentN"]
    sort_key_default = settings["defaults"]["sort_key"]
    sort_asc_default = bool(settings["defaults"]["sort_asc"])
    thresholds = settings["colors"]

    ths = []
    for c in cols:
        k = c["key"]; lbl = c.get("label", k)
        cls = " class=\"num\"" if c.get("fmt") in ("num","pct","int") else ""
        ths.append(f'<th data-k="{k}"{cls}>{lbl}</th>')
    thead_html = "<tr>" + "".join(ths) + "</tr>"

    opt_list = ["all", "10", "30", "50", "100"]
    opt_html = []
    for o in opt_list:
        sel = " selected" if (str(o).isdigit() and int(o) == int(recentN_default)) else ""
        opt_html.append(f'<option value="{o}"{sel}>{o if o!="all" else "전체"}</option>')
    opts = "\n      ".join(opt_html)

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
      {opts}
    </select> 개</label>
  <label>전략
    <input id="q" type="search" placeholder="strategy/universe 검색">
  </label>
  <button id="export">Export CSV</button>
</div>

<table id="tbl">
  <caption>runs</caption>
  <thead>{thead_html}</thead>
  <tbody></tbody>
</table>

<script>
const ROWS = {json.dumps(gather_runs(), ensure_ascii=False)};
const SETTINGS = {json.dumps(DEFAULT_SETTINGS, ensure_ascii=False)}; // HTML에는 실사용 설정을 안 노출해도 OK
let sortKey = "{DEFAULT_SETTINGS['defaults']['sort_key']}";
let sortAsc = {str(bool(DEFAULT_SETTINGS['defaults']['sort_asc'])).lower()};

function formatVal(key, v) {{
  const fmtDef = {json.dumps({c['key']: c.get('fmt','none') for c in DEFAULT_SETTINGS['columns']}, ensure_ascii=False)};
  const fmt = fmtDef[key] || "none";
  if (v===null || v===undefined || v==="") return "";
  const n = Number(v);
  if (fmt==="pct")   return isNaN(n) ? "" : (n*100).toFixed(2) + "%";
  if (fmt==="num")   return isNaN(n) ? "" : n.toFixed(3);
  if (fmt==="int")   return isNaN(n) ? "" : Math.round(n).toString();
  return v;
}}

function sparkSVG(vals) {{
  if (!vals || vals.length < 2) return "";
  const w = 80, h = 28;
  const pts = vals.map((v,i)=>[i*(w/(vals.length-1)), (1-v)*h]);
  const d = "M"+pts.map(p=>p[0].toFixed(1)+","+p[1].toFixed(1)).join(" L");
  return `<svg width="${{w}}" height="${{h}}" viewBox="0 0 ${{w}} ${{h}}"><path d="${{d}}" fill="none" stroke="currentColor" stroke-width="1"/></svg>`;
}}

function colorDot(sharpe, mdd) {{
  const thr = {json.dumps(DEFAULT_SETTINGS['colors'], ensure_ascii=False)};
  let color = "#dc2626";
  if (sharpe!==null && sharpe!==undefined) {{
    if (sharpe >= (thr.sharpe.green ?? 1.0) && (mdd===null || mdd >= (thr.mdd.green_min ?? -0.2))) color = "#16a34a";
    else if (sharpe >= (thr.sharpe.amber ?? 0.5)) color = "#ca8a04";
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
  const sel = document.querySelector("#recentN");
  const N = sel ? sel.value : "all";
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
  arr.sort((a,b)=> sortAsc ? cmp(a,b,"{DEFAULT_SETTINGS['defaults']['sort_key']}") : cmp(b,a,"{DEFAULT_SETTINGS['defaults']['sort_key']}"));
  return arr;
}}

function render() {{
  const tbody = document.querySelector("#tbl tbody");
  tbody.innerHTML = "";
  for (const r of currentView()) {{
    const tr = document.createElement("tr");
    let tds = [];
    const cols = {json.dumps([c['key'] for c in DEFAULT_SETTINGS['columns']], ensure_ascii=False)};
    for (const k of cols) {{
      if (k === "spark") {{
        tds.push(`<td class="spark">${{sparkSVG(r.spark)}}</td>`);
      }} else if (k === "run_id") {{
        const dot = colorDot(r.sharpe, r.mdd);
        const href = r.folder || r.path;
        tds.push(`<td><a href="${{href}}" target="_blank">${{dot}}${{r.run_id}}</a></td>`);
      }} else {{
        const clsMap = {json.dumps({c['key']: (c.get('fmt') in ('num','pct','int')) for c in DEFAULT_SETTINGS['columns']})};
        const cls = clsMap[k] ? " class='num'" : "";
        tds.push(`<td${{cls}}>${{formatVal(k, r[k])}}</td>`);
      }}
    }}
    tr.innerHTML = tds.join("");
    tbody.appendChild(tr);
  }}
}}

function exportCSV() {{
  const rows = currentView();
  const headers = {json.dumps([c['key'] for c in DEFAULT_SETTINGS['columns'] if c['key']!='spark'])};
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
  th.addEventListener("click", render);
}});
</script>
</body></html>
"""

# ---------- Main ----------
def main():
    # print where we think repo root is
    print(f"[PRECHECK] WEB_REPO_ROOT={os.environ.get('WEB_REPO_ROOT', '(auto)')} -> ROOT={ROOT}")
    settings = _load_settings()
    rows = gather_runs()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "index.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "index.html").write_text(build_html(rows, settings), encoding="utf-8")
    print(f"[INDEX] wrote {OUT_DIR/'index.json'} and {OUT_DIR/'index.html'}")

if __name__ == "__main__":
    raise SystemExit(main())
