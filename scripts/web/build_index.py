#!/usr/bin/env python3
import json, os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
BT_DIR = ROOT / "backtests"
OUT_DIR = ROOT / "reports"

# 링크 베이스 (reports/index.html → ../backtests/.. 가 기본)
LINK_BASE = os.environ.get("WEB_BASE_PREFIX", "..")  # 필요 시 환경변수로 조정

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

def build_html(entries):
    # 테이블 본문
    def row(r):
        ts = datetime.fromtimestamp(r["_mtime"]).strftime("%Y-%m-%d %H:%M")
        period = r.get("period", {})
        period_str = f"{period.get('start','')}~{period.get('end','')}"
        folder = r.get("_name","")
        href = f"{LINK_BASE}/backtests/{folder}"
        # 값 포맷
        final = r.get("Final_Return","")
        cagr = r.get("CAGR_like","")
        mdd  = r.get("MDD","")
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

    rows = "\n".join(row(r) for r in entries) or "<tr><td colspan=7>No runs</td></tr>"

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Backtests Index</title>
<style>
body{{font-family:system-ui,Arial,sans-serif;margin:24px}}
.toolbar{{display:flex;gap:12px;align-items:center;margin-bottom:12px}}
select,input{{padding:6px 8px}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ddd;padding:8px;font-size:14px}}
th{{background:#f8f8f8;text-align:left;cursor:pointer;user-select:none}}
td.num{{text-align:right}}
.badge{{background:#eef;border:1px solid #ccd;border-radius:6px;padding:2px 6px;font-size:12px}}
</style></head>
<body>
<h2>Backtests Index <span class="badge">{len(entries)} runs</span></h2>

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
      <th data-key="Final_Return">Final</th>
      <th data-key="CAGR_like">CAGR</th>
      <th data-key="MDD">MDD</th>
      <th data-key="_mtime">mtime</th>
      <th data-key="_name">folder</th>
    </tr>
  </thead>
  <tbody>
{rows}
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
    // numeric columns
    const numCols = ['Final','CAGR','MDD','_mtime','Final_Return','CAGR_like','MDD'];
    const ia = a.cells;
    const ib = b.cells;
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

    // Filter by strategy
    const needle = (q.value||'').trim().toLowerCase();
    if(needle){
      rows = rows.filter(r => r.cells[0].textContent.toLowerCase().includes(needle));
    }

    // Sort
    rows.sort((a,b)=>cmp(a,b,sortKey));

    // Limit
    const sel = lim.value;
    let n = rows.length;
    if(sel!=='All'){ n = Math.min(parseInt(sel||'20'), rows.length); }
    rows.forEach((r,i)=>{ r.style.display = (i<n)?'':'none'; });
  }

  // header sort
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

  // initial
  render();
})();
</script>

</body></html>"""

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = gather()
    # JSON (그대로 유지)
    (OUT_DIR / "index.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # HTML (고도화)
    (OUT_DIR / "index.html").write_text(build_html(entries), encoding="utf-8")
    print(f"[INDEX] wrote {OUT_DIR/'index.json'} and {OUT_DIR/'index.html'}")

if __name__ == "__main__":
    raise SystemExit(main())
