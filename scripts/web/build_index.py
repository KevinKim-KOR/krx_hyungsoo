#!/usr/bin/env python3
import json, os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
BT_DIR = ROOT / "backtests"
OUT_DIR = ROOT / "reports"
LINK_BASE = os.environ.get("WEB_BASE_PREFIX", "..")  # 보고서 기준 ../backtests

def load_metrics(run_dir: Path):
    m = run_dir / "metrics.json"
    if not m.exists():
        return None
    try:
        d = json.loads(m.read_text(encoding="utf-8"))
        d["_mtime"] = run_dir.stat().st_mtime
        d["_name"]  = run_dir.name
        return d
    except Exception:
        return None

def gather():
    runs = []
    if BT_DIR.exists():
        for p in sorted(BT_DIR.glob("*_*"), key=lambda x: x.stat().st_mtime, reverse=True):
            mt = load_metrics(p)
            if mt: runs.append(mt)
    return runs

def row_html(r):
    ts = datetime.fromtimestamp(r["_mtime"]).strftime("%Y-%m-%d %H:%M")
    period = r.get("period", {})
    period_str = f"{period.get('start','')}~{period.get('end','')}"
    folder = r.get("_name","")
    href = f"{LINK_BASE}/backtests/{folder}"
    final = r.get("Final_Return","")
    cagr  = r.get("CAGR_like","")
    mdd   = r.get("MDD","")
    return (
        f"<tr data-strategy='{r.get('strategy','')}' data-mtime='{int(r['_mtime'])}'>"
        f"<td class='str'>{r.get('strategy','')}</td>"
        f"<td>{period_str}</td>"
        f"<td class='num'>{final}</td>"
        f"<td class='num'>{cagr}</td>"
        f"<td class='num'>{mdd}</td>"
        f"<td>{ts}</td>"
        f"<td><a href='{href}' target='_blank'>{folder}</a></td>"
        "</tr>"
    )

def build_html(entries):
    rows = "\n".join(row_html(r) for r in entries) or "<tr><td colspan=7>No runs</td></tr>"
    tpl = """<!doctype html>
<html><head><meta charset="utf-8"><title>Backtests Index</title>
<style>
body{font-family:system-ui,Arial,sans-serif;margin:24px}
.toolbar{display:flex;gap:12px;align-items:center;margin-bottom:12px}
select,input{padding:6px 8px}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #ddd;padding:8px;font-size:14px}
th{background:#f8f8f8;text-align:left;cursor:pointer;user-select:none}
td.num{text-align:right}
.badge{background:#eef;border:1px solid #ccd;border-radius:6px;padding:2px 6px;font-size:12px}
</style></head>
<body>
<h2>Backtests Index <span class="badge">%%COUNT%% runs</span></h2>

<div class="toolbar">
  <label>Strategy
    <input id="q" type="text" placeholder="filter by strategy…">
  </label>
  <label>최근 N건
    <select id="limit">
      <option>10</option><option selected>20</option><option>50</option><option>100</option><option>All</option>
    </select>
  </label>
</div>

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

  let sortKey = '_mtime';
  let asc = false;

  function getRows(){ return Array.from(tbl.tBodies[0].rows); }

  function cmp(a,b,k){
    const ia = a.cells, ib = b.cells;
    let va, vb;
    switch(k){
      case 'strategy': va = ia[0].textContent; vb = ib[0].textContent; break;
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

    const needle = (q.value||'').trim().toLowerCase();
    if(needle){
      rows = rows.filter(r => r.cells[0].textContent.toLowerCase().includes(needle));
    }

    rows.sort((a,b)=>cmp(a,b,sortKey));

    const sel = lim.value;
    let n = rows.length;
    if(sel!=='All'){ n = Math.min(parseInt(sel||'20'), rows.length); }
    rows.forEach((r,i)=>{ r.style.display = (i<n)?'':'none'; });
  }

  Array.from(tbl.tHead.rows[0].cells).forEach((th, idx)=>{
    th.addEventListener('click', ()=>{
      const map = ['strategy','period','Final','CAGR','MDD','_mtime','_name'];
      const key = map[idx]||'_mtime';
      if(sortKey===key) asc=!asc; else { sortKey=key; asc=false; }
      render();
    });
  });

  q.addEventListener('input', render);
  lim.addEventListener('change', render);
  render();
})();
</script>

</body></html>"""
    return tpl.replace("%%ROWS%%", rows).replace("%%COUNT%%", str(len(entries)))

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = gather()
    (OUT_DIR / "index.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "index.html").write_text(build_html(entries), encoding="utf-8")
    print(f"[INDEX] wrote {OUT_DIR/'index.json'} and {OUT_DIR/'index.html'}")

if __name__ == "__main__":
    raise SystemExit(main())
