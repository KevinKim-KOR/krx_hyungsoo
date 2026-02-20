"""
Watchlist Manager (D-P.61)

PC UI에서 "감시 대상 종목"을 관리합니다.
- WATCHLIST_V1 스키마
- state/watchlist/latest/watchlist_latest.json 저장
"""

import json
import os
import shutil
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from pathlib import Path
from typing import Dict, Any, List, Optional
import hashlib

BASE_DIR = Path(__file__).parent.parent

# Output paths
WATCHLIST_DIR = BASE_DIR / "state" / "watchlist"
WATCHLIST_LATEST_FILE = WATCHLIST_DIR / "latest" / "watchlist_latest.json"
WATCHLIST_SNAPSHOTS_DIR = WATCHLIST_DIR / "snapshots"


def ensure_dirs():
    WATCHLIST_LATEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def load_watchlist() -> Optional[Dict]:
    """Watchlist 로드"""
    if not WATCHLIST_LATEST_FILE.exists():
        return None
    try:
        return json.loads(WATCHLIST_LATEST_FILE.read_text(encoding="utf-8"))
    except:
        return None


def upsert_watchlist(items: List[Dict], updated_by: str = "pc_ui") -> Dict:
    """Watchlist 저장 (Upsert)"""
    ensure_dirs()
    
    now = datetime.now(KST)
    updated_at = now.isoformat()
    
    # 1. Build Watchlist
    watchlist = {
        "schema": "WATCHLIST_V1",
        "updated_at": updated_at,
        "updated_by": updated_by,
        "items": items,
        "item_count": len(items)
    }
    
    # Update hash
    payload_str = json.dumps(items, sort_keys=True)
    watchlist["integrity"] = {
         "payload_sha256": hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    }
    
    # 2. Save Latest (Atomic)
    tmp_path = WATCHLIST_LATEST_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(watchlist, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, WATCHLIST_LATEST_FILE)
    
    # 3. Save Snapshot
    snapshot_filename = f"watchlist_{now.strftime('%Y%m%d_%H%M%S')}.json"
    snapshot_path = WATCHLIST_SNAPSHOTS_DIR / snapshot_filename
    shutil.copy2(WATCHLIST_LATEST_FILE, snapshot_path)
    
    return {
        "result": "OK",
        "updated_at": updated_at,
        "item_count": len(items),
        "snapshot_ref": f"state/watchlist/snapshots/{snapshot_filename}"
    }


if __name__ == "__main__":
    # Test
    test_items = [
        {"ticker": "069500", "name": "KODEX 200", "enabled": True},
        {"ticker": "229200", "name": "KODEX 코스닥150", "enabled": True}
    ]
    print(json.dumps(upsert_watchlist(test_items), indent=2, ensure_ascii=False))
