#!/usr/bin/env python3
import json, os
from pathlib import Path
from datetime import datetime
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
    """equity_curve.csv에서 마지막 N포인트를 0..1로 정규화한 리스트(없으면 None)."""
    f = run_dir / "equity_curve.csv"
    if not f.exists(): return None
    try:
        df = pd.read_csv(f)
        # 숫자열 하나 골라 사용(variance 최대)
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if not num_cols: return None
        col = max(num_cols, key=lambda c: df[c].var())
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty: return None
        s = s.tail(N)
        mn, mx = float(s.min()), float(s.max())
        if mx == mn: return [0.5]*len(s)
        return [ (v-mn)/(mx-mn) for v in s.tolist() ]
    except Exception:
        return None

def _svg_spark(values, w=100, h=24, pad=2):
    if not values:  # 안전망
        return ""
    xs = []
    n = len(values)
    for i, v in enumerate(values):
        x = pad + (w-2*pad) * (i/(n-1 if n>1 else 1))
        y = pad + (h-2*pad) * (1.0 - v)
        xs.append(f"{x:.1f},{y:.1f}")
    path = " ".join(xs)
    return f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}'><polyline fill='none' stroke='currentColor' stroke-width='1.5' points='{path}'/></svg>"

def gather():
    runs = []
    if BT_DIR.exists():
        for p in sorted(BT_DIR.glob("*_*"), key=lambda x: x.stat().st_mtime, reverse=True):
            mt = _load_metrics(p)
            if mt:
                mt["_spark"] = _svg_spark(_spark_values(p))
                runs.append(mt)
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
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:middle;border:1px solid #0001}
td.spark svg{display:block}
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
  <button id="btnCsv">CSV export</button>
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

    // 색상 태깅 (전략명 → HSL)
    rows.forEach(r=>{
      const tag = r.cells[0].textContent.trim();
      const dot = r.querySelector('.dot');
      const h = Math.abs([...tag].reduce((a,c)=>a*33 + c.charCodeAt(0), 7)) % 360;
      dot.style.background = `hsl(${h} 70% 85%)`;
      dot.style.borderColor = `hsl(${h} 60% 40% / 0.3)`;
    });

    // 필터
    const needle = (q.value||'').trim().toLowerCase();
    if(needle){
      rows = rows.filter(r => r.cells[0].textContent.toLowerCase().includes(needle));
    }

    // 정렬
    rows.sort((a,b)=>cmp(a,b,sortKey));

    // 제한
    const sel = lim.value;
    let n = rows.length;
    if(sel!=='All'){ n = Math.min(parseInt(sel||'20'), rows.length); }
    getRows().forEach(r => r.style.display = 'none');
    rows.forEach((r,i)=>{ r.style.display = (i<n)?'':'none'; });
  }

  // 헤더 정렬
  Array.from(tbl.tHead.rows[0].cells).forEach((th, idx)=>{
    th.addEventListener('click', ()=>{
      const map = ['strategy','period','Final','CAGR','MDD','_mtime','_name','spark'];
      const key = map[idx]||'_mtime';
      if(sortKey===key) asc=!asc; else { sortKey=key; asc=false; }
      render();
    });
  });

  // CSV export (현재 표시된 행만)
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
