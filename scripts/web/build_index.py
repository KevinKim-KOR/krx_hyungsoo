#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
(동일본) See web/build_index.py
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
LINK_BASE = os.environ.get("WEB_BASE_PREFIX", "..")

def _coerce_float(x):
    try:
        if x is None: return None
        if isinstance(x, (int, float)): return float(x)
        s = str(x).replace(",", "")
        return float(s)
    except Exception:
        return None

def _pick_meta(name: str) -> Dict[str, Optional[str]]:
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

def _read_equity_curve_csv(fname: Path):
    try:
        import pandas as pd
        df = pd.read_csv(fname)
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if not num_cols: return None
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
    def k(e): 
        try:
            return datetime.strptime(e["started_at"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime.fromtimestamp(0)
    runs.sort(key=k, reverse=True)
    return runs

def build_html(rows: List[Dict[str, Any]]) -> str:
    # 동일한 HTML (web/build_index.py와 동일)
    from web.build_index import build_html as _bh
    return _bh(rows)

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = gather_runs()
    (OUT_DIR / "index.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "index.html").write_text(build_html(rows), encoding="utf-8")
    print(f"[INDEX] wrote {OUT_DIR/'index.json'} and {OUT_DIR/'index.html'}")

if __name__ == "__main__":
    raise SystemExit(main())
