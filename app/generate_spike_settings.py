"""
Spike Settings Manager (D-P.62)

PC UI에서 "Spike 감시 설정"을 관리합니다.
- SPIKE_SETTINGS_V1 스키마
- state/spike_settings/latest/spike_settings_latest.json 저장
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import hashlib

BASE_DIR = Path(__file__).parent.parent

# Output paths
SETTINGS_DIR = BASE_DIR / "state" / "spike_settings"
SETTINGS_LATEST_FILE = SETTINGS_DIR / "latest" / "spike_settings_latest.json"
SETTINGS_SNAPSHOTS_DIR = SETTINGS_DIR / "snapshots"


def ensure_dirs():
    SETTINGS_LATEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def load_spike_settings() -> Dict:
    """Settings 로드 (없으면 기본값 반환하지 않고 None 반환 -> Fail Closed)"""
    if not SETTINGS_LATEST_FILE.exists():
        # Default fallback for initial setup? 
        # Requirement says: "settings 없으면 Fail-Closed = BLOCKED"
        # But for UI display, we might want defaults. But here we return None to let caller decide.
        return None
    try:
        return json.loads(SETTINGS_LATEST_FILE.read_text(encoding="utf-8"))
    except:
        return None


def upsert_spike_settings(params: Dict, updated_by: str = "pc_ui") -> Dict:
    """Settings 저장 (Upsert)"""
    ensure_dirs()
    
    now = datetime.now()
    updated_at = now.isoformat()
    
    # Defaults
    settings = {
        "schema": "SPIKE_SETTINGS_V1",
        "updated_at": updated_at,
        "updated_by": updated_by,
        "enabled": params.get("enabled", False),
        "threshold_pct": float(params.get("threshold_pct", 3.0)),
        "cooldown_minutes": int(params.get("cooldown_minutes", 15)),
        "session_kst": {
            "start": params.get("session_start", "09:10"),
            "end": params.get("session_end", "15:20"),
            "days": params.get("session_days", [0, 1, 2, 3, 4]) # Mon=0, Fri=4
        },
        "market_data": {
            "provider": params.get("provider", "naver"),  # naver or mock
            "fallback": params.get("fallback", True)
        },
        "display": {
            "include_value_volume": params.get("include_value_volume", True),
            "include_deviation": params.get("include_deviation", True),
            "include_portfolio_context": params.get("include_portfolio_context", True)
        },
        "options": {
            "include_premium_fields": params.get("include_premium_fields", False)
        }
    }
    
    # Update hash
    payload_str = json.dumps(settings, sort_keys=True)
    settings["integrity"] = {
         "payload_sha256": hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    }
    
    # 2. Save Latest (Atomic)
    tmp_path = SETTINGS_LATEST_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, SETTINGS_LATEST_FILE)
    
    # 3. Save Snapshot
    snapshot_filename = f"spike_settings_{now.strftime('%Y%m%d_%H%M%S')}.json"
    snapshot_path = SETTINGS_SNAPSHOTS_DIR / snapshot_filename
    shutil.copy2(SETTINGS_LATEST_FILE, snapshot_path)
    
    return {
        "result": "OK",
        "updated_at": updated_at,
        "settings": settings,
        "snapshot_ref": f"state/spike_settings/snapshots/{snapshot_filename}"
    }


if __name__ == "__main__":
    # Test
    test_params = {
        "enabled": True,
        "threshold_pct": 3.5,
        "cooldown_minutes": 20,
        "session_start": "09:00",
        "session_end": "15:30"
    }
    print(json.dumps(upsert_spike_settings(test_params), indent=2, ensure_ascii=False))
