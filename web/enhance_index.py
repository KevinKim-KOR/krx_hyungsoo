#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhance generated reports/index.html:
- Inject toolbar (Recent N filter + Export CSV)
- Add client-side row coloring for +/- values
- No dependency on pandas; in-place post-process

Safe: If markers not found, it appends at end of <body>.
"""

from __future__ import annotations
import re
from pathlib import Path
import sys
import json

ROOT = Path(__file__).resolve().parents[1]
REPORTS_HTML = ROOT / "reports" / "index.html"
REPORTS_JSON = ROOT / "reports" / "index.json"
CFG = ROOT / "config" / "web_index.yaml"

# defaults (can be overridden by config keys if you already wrote them later)
RECENT_OPTIONS = [20, 50, 100, 200, "All"]
RECENT_DEFAULT = 50

# try to load default recentN from config/web_index.yaml (optional)
try:
    import yaml  # type: ignore
    if CFG.exists():
        cfg = yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}
        ui = (cfg.get("ui") or {})
        RECENT_DEFAULT = int(ui.get("recentN_default", RECENT_DEFAULT))
        rec_opts = ui.get("recentN_options")
        if isinstance(rec_opts, list) and rec_opts:
            # sanitize (int or "All")
            RECENT_OPTIONS = []
            for v in rec_opts:
                if (isinstance(v, int) and v > 0) or (isinstance(v, str) and v.lower() == "all"):
                    RECENT_OPTIONS.append(v if isinstance(v, int) else "All")
except Exception:
    pass

if not REPORTS_HTML.exists():
    print(f"[ENHANCE] skip (no html): {REPORTS_HTML}")
    sys.exit(0)

# read html
html = REPORTS_HTML.read_text(encoding="utf-8", errors="ignore")

# 1) inject toolbar (Recent N + CSV)
toolbar_html = f"""
<!-- injected by enhance_index.py -->
<style>
  .idx-toolbar{{font-family:system-ui, -apple-system, Segoe UI, Roboto, sans-serif;display:flex;gap:.75rem;align-items:center;margin:8px 0 12px}}
  .idx-toolbar label{{font-size:.9rem;opacity:.8}}
  .idx-toolbar select, .idx-toolbar button{{padding:.3rem .5rem;border:1px solid #ccc;border-radius:6px;background:#fff;cursor:pointer}}
  .idx-muted{{opacity:.6;font-size:.85rem}}
  /* simple coloring */
  table#idxTable td.pos{{color:#0a7f28; font-weight:600}}
  table#idxTable td.neg{{color:#c2371c; font-weight:600}}
</style>
<div class="idx-toolbar" id="idxToolbar">
  <label for="recentN">Recent N</label>
  <select id="recentN">{''.join([f'<option value="{o}">{o}</option>' for o in RECENT_OPTIONS])}</select>
  <button id="btnCsv" type="button">Export CSV</button>
  <span class="idx-muted">* 색상: + (초록) / − (빨강)</span>
</div>
<script>
(function(){
  // helpers
  function parsePercentOrSign(txt){
    if(!txt) return 0;
    const s = txt.trim();
    if(s.startsWith('+')) return 1;
    if(s.startsWith('-')) return -1;
    const m = s.match(/(-?\\d+(?:\\.\\d+)?)\\s*%/);
    if(m){
      const v = parseFloat(m[1]);
      if(v>0) return 1; if(v<0) return -1;
    }
    return 0;
  }
  function ensureTableId(){
    let tbl = document.querySelector('table#idxTable');
    if(!tbl){
      // fallback: first table
      tbl = document.querySelector('table');
      if(tbl) tbl.setAttribute('id','idxTable');
    }
    return document.getElementById('idxTable');
  }
  function colorize(tbl){
    if(!tbl) return;
    const rows = Array.from(tbl.querySelectorAll('tbody tr'));
    rows.forEach(tr=>{
      Array.from(tr.children).forEach(td=>{
        const s = parsePercentOrSign(td.textContent || '');
        td.classList.remove('pos','neg');
        if(s>0) td.classList.add('pos');
        else if(s<0) td.classList.add('neg');
      });
    });
  }
  function filterRecent(tbl, n){
    if(!tbl) return;
    const tbody = tbl.tBodies[0] || tbl.createTBody();
    const rows = Array.from(tbody.rows);
    rows.forEach((tr,idx)=>{
      tr.style.display = (n==='All' ? '' : (idx < n ? '' : 'none'));
    });
  }
  function exportCSV(tbl){
    if(!tbl) return;
    const rows = [];
    const pushRow = (tr)=>rows.push(Array.from(tr.children).map(td=> {
      let v = (td.innerText||'').replaceAll('\\n',' ').trim();
      v = v.replaceAll('"','""');
      if(v.search(/[",\\n]/)>=0) v = '"'+v+'"';
      return v;
    }).join(','));
    // header
    const thead = tbl.tHead;
    if(thead && thead.rows.length) pushRow(thead.rows[0]);
    // body (only visible rows)
    const visible = Array.from(tbl.tBodies[0]?.rows || []).filter(tr=>tr.style.display!=='none');
    visible.forEach(pushRow);
    const csv = rows.join('\\n');
    const blob = new Blob([csv], {type:'text/csv;charset=utf-8;'});
    const a = document.createElement('a');
    const ts = new Date().toISOString().slice(0,19).replace(/[-:T]/g,'');
    a.href = URL.createObjectURL(blob);
    a.download = 'index_view_'+ts+'.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  const tbl = ensureTableId();
  colorize(tbl);

  const sel = document.getElementById('recentN');
  const defN = {RECENT_DEFAULT!r};
  if(sel){
    if([...sel.options].some(o=>o.value == String(defN))) sel.value = String(defN);
    sel.addEventListener('change', ()=> filterRecent(tbl, sel.value==='All' ? 'All' : parseInt(sel.value)));
    // apply default
    filterRecent(tbl, sel.value==='All' ? 'All' : parseInt(sel.value));
  }
  const btn = document.getElementById('btnCsv');
  if(btn){ btn.addEventListener('click', ()=> exportCSV(tbl)); }
})();
</script>
"""

# insert toolbar before first <table>, else at end of <body>
if re.search(r"<table", html, flags=re.IGNORECASE|re.DOTALL):
    html = re.sub(r"(?i)(<table[^>]*>)", toolbar_html + r"\1", html, count=1)
elif re.search(r"</body>", html, flags=re.IGNORECASE):
    html = re.sub(r"(?i)</body>", toolbar_html + r"</body>", html, count=1)
else:
    html += toolbar_html

REPORTS_HTML.write_text(html, encoding="utf-8")
print(f"[ENHANCE] updated {REPORTS_HTML}")
