"""
Watchlist Candidate Generator (D-P.63)

PC에서 Backtest 결과(및 Reco)를 기반으로 "감시 후보(Candidates)"를 제안합니다.
- Source 1: reports/backtest/latest/backtest_result.json (Performance Metrics)
- Source 2: reports/live/reco/latest/reco_latest.json (Latest Recommendation)

Output:
- state/watchlist_candidates/latest/watchlist_candidates_latest.json
- SCHEMA: WATCHLIST_CANDIDATES_V1
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import hashlib

BASE_DIR = Path(__file__).parent.parent

# Input Paths
BACKTEST_RESULT_FILE = BASE_DIR / "reports" / "backtest" / "latest" / "backtest_result.json"
RECO_LATEST_FILE = BASE_DIR / "reports" / "live" / "reco" / "latest" / "reco_latest.json"

# Output Paths
CANDIDATES_DIR = BASE_DIR / "state" / "watchlist_candidates"
CANDIDATES_LATEST_FILE = CANDIDATES_DIR / "latest" / "watchlist_candidates_latest.json"
CANDIDATES_SNAPSHOTS_DIR = CANDIDATES_DIR / "snapshots"


def ensure_dirs():
    CANDIDATES_LATEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Optional[Dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except:
        return None


def generate_candidates(confirm: bool = False) -> Dict:
    """후보 생성 실행"""
    
    # 1. Load Sources
    # Fail-Closed Rule: No Backtest = No Candidates
    bt_data = load_json(BACKTEST_RESULT_FILE)
    if not bt_data:
        return {
            "result": "BLOCKED", 
            "reason": "NO_BACKTEST_RESULT",
            "message": "백테스트 결과 파일이 없어 후보를 생성할 수 없습니다."
        }
        
    reco_data = load_json(RECO_LATEST_FILE)
    
    # 2. Process Candidates
    # Logic: Extract all tickers from Backtest result (assuming it contains per-ticker stats)
    # If the backtest result structure is simple (just summary), we might need to rely on Reco or mock for now.
    # Assuming Backtest Result contains "details" or "tickers" list.
    
    # Sample Backtest Result Structure Assumption:
    # { "summary": { ... }, "tickers": { "005930": { "cagr": 0.15, "mdd": -0.1 }, ... } }
    
    candidates = []
    
    # Check if 'tickers' or 'details' exists in bt_data
    # If not, let's look for 'trades' and aggregate, or just use Reco as fallback if BT is summary only.
    # For this phase, let's assume BT data has a 'portfolio_stats' or similar per ticker, OR we use Reco as primary if BT is just aggregate.
    
    # Strategy: Use Reco list as base, then enrich with BT stats if available.
    # If Reco is missing, we can't recommend much unless BT has the full universe list.
    
    source_tickers = set()
    
    # Source A: Reco
    if reco_data and "recommendations" in reco_data:
        for r in reco_data["recommendations"]:
            source_tickers.add(r["ticker"])
            
    # Source B: Backtest structure (Mocking assumption for now if file doesn't exist or has different schema)
    # Let's say if BT has "ranking" or "top_performers"
    if "top_performers" in bt_data:
        for t in bt_data["top_performers"]:
            source_tickers.add(t["ticker"])
            
    # If no tickers found, fallback to mock demo for UI check if confirm=True
    if not source_tickers:
        # If confirm is True, we might want to return empty list instead of mock in prod.
        # But for dev, let's say "No Tickers Found"
        if not confirm:
             return {"result": "BLOCKED", "reason": "NO_TICKERS_FOUND"}
    
    # Build Candidate List
    now = datetime.now()
    idx = 0
    for t in sorted(list(source_tickers)):
        # Enrich with meta (Mock meta here since we don't have master file loaded)
        # In real app, load stock master
        name = "Unknown" 
        # Try to find name in Reco
        if reco_data:
            for r in reco_data.get("recommendations", []):
                if r["ticker"] == t:
                    name = r.get("name", name)
                    break
        
        # Enrich with BT stats
        stats = {}
        if "tickers" in bt_data and t in bt_data["tickers"]:
            stats = bt_data["tickers"][t]
            
        candidates.append({
            "id": f"c_{idx}",
            "ticker": t,
            "name": name,
            "source": "BACKTEST" if "tickers" in bt_data and t in bt_data["tickers"] else "RECO",
            "score": stats.get("score", 0),  # Placeholder
            "metrics": {
                "cagr": stats.get("cagr", 0),
                "mdd": stats.get("mdd", 0),
                "win_rate": stats.get("win_rate", 0)
            },
            "generated_at": now.isoformat()
        })
        idx += 1
        
    # Result Construction
    result_data = {
        "schema": "WATCHLIST_CANDIDATES_V1",
        "generated_at": now.isoformat(),
        "source_backtest": str(BACKTEST_RESULT_FILE.name),
        "source_reco": str(RECO_LATEST_FILE.name) if reco_data else None,
        "count": len(candidates),
        "candidates": candidates
    }
    
    # Save
    ensure_dirs()
    
    # Save Latest
    CANDIDATES_LATEST_FILE.write_text(json.dumps(result_data, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Save Snapshot
    snap_name = f"watchlist_candidates_{now.strftime('%Y%m%d_%H%M%S')}.json"
    snap_path = CANDIDATES_SNAPSHOTS_DIR / snap_name
    shutil.copy2(CANDIDATES_LATEST_FILE, snap_path)
    
    return {
        "result": "OK",
        "count": len(candidates),
        "path": f"state/watchlist_candidates/latest/watchlist_candidates_latest.json"
    }

def get_latest_candidates() -> Optional[Dict]:
    return load_json(CANDIDATES_LATEST_FILE)

if __name__ == "__main__":
    # Test Run
    print(generate_candidates(confirm=True))
