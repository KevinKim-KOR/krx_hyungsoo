#!/usr/bin/env python3
import json, os, re
from pathlib import Path
from datetime import datetime, date
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BT_DIR = ROOT / "backtests"
OUT_DIR = ROOT / "reports"
LINK_BASE = os.environ.get("WEB_BASE_PREFIX", "..")  # reports 기준 ../backtests

def _load_metrics(run_dir: Path):
    m = run_dir / "metrics.json"
    if not m.exists(): return None
    try:
        d = json.loads(m.read_text(encoding="utf-8"))
        d["_mtime"] = run_dir.stat().st_mtime
        d["_name"]  = run_dir.name
        return d
    except Exception:
        return None

def _spark_values(run_dir: Path, N=60):
    f = run_dir / "equity_curve.csv"
    if not f.exists(): return None
    try:
        df = pd.read_csv(f)
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if not num_cols: return None
        col = max(num_cols, key=lambda c: df[c].var())
        s = pd.to_numeric(df[col], errors="coerce").dropna().tail(N)
        if s.empty: return None
        mn, mx = float(s.min()), float(s.max())
        if mx == mn: return [0.5]*len(s)
        return [ (v-mn)/(mx-mn) for v in s.tolist() ]
    except Exception:
        return None

def _svg_spark(values, w=100, h=24, pad=2):
    if not values: return ""
    xs = []
    n = len(values)
    for i, v in enumerate(values):
        x = pad + (w-2*pad) * (i/(n-1 if n>1 else 1))
        y = pad + (h-2*pad) * (1.0 - v)
        xs.append(f"{x:.1f},{y:.1f}")
    return f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}'><polyline fill='none' stroke='currentColor' stroke-width='1.5' points='{' '.join(xs)}'/></svg>"

def gather_runs():
    runs = []
    if BT_DIR.exists():
        for p in sorted(BT_DIR.glob("*_*"), key=lambda x: x.stat().st_mtime, reverse=True):
            mt = _load_metrics(p)
            if mt:
                mt["_spark"] = _svg_spark(_spark_values(p))
                runs.append(mt)
    return runs

# ---- Status badges ----
def _to_series(obj) -> pd.Series:
    if isinstance(obj, pd.DatetimeIndex): return pd.Series(obj)
    if isinstance(obj, pd.Series): return pd.to_datetime(obj, errors="coerce")
    if isinstance(obj, pd.Index):  return pd.to_datetime(pd.Series(obj), errors="coerce")
    return pd.to_datetime(pd.Series(obj), errors="coerce")

def latest_trading_day_from_cache() -> date:
    p = ROOT / "data" / "cache" / "kr" / "trading_days.pkl"
    obj = pd.read_pickle(p)
    parts = []
    idx = getattr(obj, "index", None)
    if isinstance(idx, pd.DatetimeIndex) and len(idx): parts.append(_to_series(idx))
    for c in getattr(obj, "columns", []):
        if "date" in str(c).lower(): parts.append(_to_series(obj[c]))
    if not parts:
        try: parts.append(pd.to_datetime(obj.stack(dropna=False), errors="coerce"))
        except Exception: pass
    cat = pd.concat(parts, axis=0).dropna()
    today = pd.Timestamp.today().normalize()
    cat = cat[cat <= today]
    return cat.max().date()

def probe_latest() -> date:
    """config/data_sources.yaml 의 probes/postcheck_probes 사용."""
    import pandas as pd
    base = ROOT / "data" / "cache" / "kr"
    probes = ["069500.KS.pkl","069500.pkl"]
    cfg = ROOT / "config" / "data_sources.yaml"
    if cfg.exists():
        try:
            import yaml
            y = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
            probes = y.get("probes") or y.get("postcheck_probes") or probes
        except Exception:
            pass

    dates = []
    for name in probes:
        p = base / name
        if not p.exists():
            continue
        df = pd.read_pickle(p)
        idx = getattr(df, "index", None)
        if isinstance(idx, pd.DatetimeIndex) and len(idx):
            dates.append(pd.to_datetime(idx).max().date()); continue
        # date 컬럼 탐색
        hit = False
        for col in getattr(df,"columns",[]):
            if "date" in str(col).lower():
                s = pd.to_datetime(df[col], errors="coerce")
                if s.notna().any():
                    dates.append(s.max().date()); hit=True; break
        if hit: continue
        # 마지막 수단: stack
        try:
            s = pd.to_datetime(df.stack(dropna=False), errors="coerce")
            if s.notna().any(): dates.append(s.max().date())
        except Exception:
            pass
    return max(dates) if dates else None


def drift_today():
    today = datetime.today().strftime("%Y-%m-%d")
    logs = sorted((ROOT / "logs").glob(f"compare_*_{today}.log"))
    out = []
    for p in logs:
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if "[RESULT] DRIFT" in txt:
            m = re.search(r"compare_(.+?)_"+re.escape(today), p.name)
            strat = m.group(1) if m else "unknown"
            out.append({"strategy": strat, "path": f"../logs/{p.name}"})
    return out

def row_html(r):
    ts = datetime.fromtimestamp(r["_mtime"]).strftime("%Y-%m-%d %H:%M")
    period = r.get("period", {})
    period_str = f"{period.get('start','')}~{period.get('end','')}"
    folder = r.get("_name","")
    href = f"{LINK_BASE}/backtests/{folder}"
    final = r.get("Final_Return","")
    cagr  = r.get("CAGR_like","")
    mdd   = r.get("MDD","")
    tag   = r.get("strategy","")
    spark = r.get("_spark","") or ""
    return (
        f"<tr data-strategy='{tag}' data-mtime='{int(r['_mtime'])}'>"
        f"<td class='str'><span class='dot' data-tag='{tag}'></span>{tag}</td>"
        f"<td>{period_str}</td>"
        f"<td class='num'>{final}</td>"
        f"<td class='num'>{cagr}</td>"
        f"<td class='num'>{mdd}</td>"
        f"<td>{ts}</td>"
        f"<td><a href='{href}' target='_blank'>{folder}</a></td>"
        f"<td class='spark'>{spark}</td>"
        "</tr>"
    )

def build_html(entries):
    rows = "\n".join(row_html(r) for r in entries) or "<tr><td colspan=8>No runs</td></tr>"

    # status
    drift = drift_today()
    drift_badge = f"<span class='badge badge-red'>DRIFT {len(drift)}</span>" if drift else "<span class='badge badge-green'>DRIFT 0</span>"
    # data freshness
    data_badge = "<span class='badge'>Data n/a</span>"
    try:
        cal = latest_trading_day_from_cache()
        prb = probe_latest()
        if prb and cal:
            ok = (prb == cal) or (prb >= cal)
            cls = "badge-green" if ok else "badge-red"
            data_badge = f"<span class='badge {cls}'>Data { 'OK' if ok else 'STALE' } — calendar {cal}, probes {prb}</span>"
        elif prb:
            data_badge = f"<span class='badge badge-amber'>Data probes {prb}</span>"
        elif cal:
            data_badge = f"<span class='badge badge-amber'>Calendar {cal}</span>"
    except Exception:
        pass

    tpl = """<!doctype html>
<html><head><meta charset="utf-8"><title>Backtests Index</title>
<style>
body{font-family:system-ui,Arial,sans-serif;margin:24px}
.toolbar{display:flex;gap:12px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
select,input,button{padding:6px 8px}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #ddd;padding:8px;font-size:14px}
th{background:#f8f8f8;text-align:left;cursor:pointer;user-select:none}
td.num{text-align:right}
.badge{background:#eef;border:1px solid #ccd;border-radius:6px;padding:2px 6px;font-size:12px}
.badge-green{background:#e6f7ec;border-color:#b9e0c5}
.badge-red{background:#fde8e8;border-color:#f5b5b5}
.badge-amber{background:#fff7e6;border-color:#f4dbb5}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:middle;border:1px solid #0001}
td.spark svg{display:block}
ul{margin:8px 0 0 18px}
</style></head>
<body>
<h2>Backtests Index <span class="badge">%%COUNT%% runs</span> %%DRIFT%% %%DATA%%</h2>

<div class="toolbar">
  <label>Strategy
    <input id="q" type="text" placeholder="filter by strategy…">
  </label>
  <label>최근 N건
    <select id="limit">
      <option>10</option><option selected>20</option><option>50</option><option>100</option><option>All</option>
    </select>
  </label>
  <button id="btnCsv">CSV export</button>
</div>

%%DRIFT_LIST%%

<table id="tbl">
  <thead>
    <tr>
      <th data-key="strategy">Strategy</th>
      <th data-key="period">Period</th>
      <th data-key="Final">Final</th>
      <th data-key="CAGR">CAGR</th>
      <th data-key="MDD">MDD</th>
      <th data-key="_mtime">mtime</th>
      <th data-key="_name">folder</th>
      <th data-key="spark">spark</th>
    </tr>
  </thead>
  <tbody>
%%ROWS%%
  </tbody>
</table>

<script>
(function(){
  const tbl = document.getElementById('tbl');
  const q   = document.getElementById('q');
  const lim = document.getElementById('limit');
  const btn = document.getElementById('btnCsv');

  let sortKey = '_mtime';
  let asc = false;

  function getRows(){ return Array.from(tbl.tBodies[0].rows); }

  function cmp(a,b,k){
    const ia = a.cells, ib = b.cells;
    let va, vb;
    switch(k){
      case 'strategy': va = ia[0].textContent.trim(); vb = ib[0].textContent.trim(); break;
      case 'period':   va = ia[1].textContent; vb = ib[1].textContent; break;
      case 'Final':    va = parseFloat(ia[2].textContent)||-1e99; vb = parseFloat(ib[2].textContent)||-1e99; break;
      case 'CAGR':     va = parseFloat(ia[3].textContent)||-1e99; vb = parseFloat(ib[3].textContent)||-1e99; break;
      case 'MDD':      va = parseFloat(ia[4].textContent)|| 1e99; vb = parseFloat(ib[4].textContent)|| 1e99; break;
      case '_mtime':   va = parseInt(a.dataset.mtime||'0'); vb = parseInt(b.dataset.mtime||'0'); break;
      default:         va = a.textContent; vb = b.textContent;
    }
    if(va<vb) return asc?-1:1;
    if(va>vb) return asc?1:-1;
    return 0;
  }

  function render(){
    let rows = getRows();

    rows.forEach(r=>{
      const tag = r.cells[0].textContent.trim();
      const dot = r.querySelector('.dot');
      const h = Math.abs([...tag].reduce((a,c)=>a*33 + c.charCodeAt(0), 7)) % 360;
      dot.style.background = `hsl(${h} 70% 85%)`;
      dot.style.borderColor = `hsl(${h} 60% 40% / 0.3)`;
    });

    const needle = (q.value||'').trim().toLowerCase();
    if(needle){
      rows = rows.filter(r => r.cells[0].textContent.toLowerCase().includes(needle));
    }

    rows.sort((a,b)=>cmp(a,b,sortKey));

    const sel = lim.value;
    let n = rows.length;
    if(sel!=='All'){ n = Math.min(parseInt(sel||'20'), rows.length); }
    getRows().forEach(r => r.style.display = 'none');
    rows.forEach((r,i)=>{ r.style.display = (i<n)?'':'none'; });
  }

  Array.from(tbl.tHead.rows[0].cells).forEach((th, idx)=>{
    th.addEventListener('click', ()=>{
      const map = ['strategy','period','Final','CAGR','MDD','_mtime','_name','spark'];
      const key = map[idx]||'_mtime';
      if(sortKey===key) asc=!asc; else { sortKey=key; asc=false; }
      render();
    });
  });

  btn.addEventListener('click', ()=>{
    const rows = getRows().filter(r => r.style.display !== 'none');
    const header = ['Strategy','Period','Final','CAGR','MDD','mtime','folder'];
    const lines = [header.join(',')];
    rows.forEach(r=>{
      const tds = r.cells;
      const rec = [tds[0].textContent.trim(), tds[1].textContent, tds[2].textContent,
                   tds[3].textContent, tds[4].textContent, tds[5].textContent, tds[6].textContent];
      lines.push(rec.map(v => `"${v.replaceAll('"','""')}"`).join(','));
    });
    const blob = new Blob([lines.join('\\n')], {type:'text/csv;charset=utf-8;'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'backtests_index.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  });

  const tblEl = document.getElementById('tbl');
  window.addEventListener('load', render);
  document.getElementById('q').addEventListener('input', render);
  document.getElementById('limit').addEventListener('change', render);
})();
</script>

</body></html>"""
    drift_list = ""
    d = drift_today()
    if d:
        drift_list = "<div><b>Recent DRIFT:</b><ul>" + "".join(
            f"<li>{x['strategy']} — <a href='{x['path']}' target='_blank'>{x['path'].split('/')[-1]}</a></li>" for x in d
        ) + "</ul></div>"

    return (tpl
            .replace("%%ROWS%%", rows)
            .replace("%%COUNT%%", str(len(entries)))
            .replace("%%DRIFT%%", drift_badge)
            .replace("%%DATA%%", data_badge)
            .replace("%%DRIFT_LIST%%", drift_list))

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = gather_runs()
    (OUT_DIR / "index.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "index.html").write_text(build_html(entries), encoding="utf-8")
    print(f"[INDEX] wrote {OUT_DIR/'index.json'} and {OUT_DIR/'index.html'}")

if __name__ == "__main__":
    raise SystemExit(main())
