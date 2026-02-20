"""
Push Preview Generator (C-P.22)
채널별 렌더링 프리뷰 생성 (No Send)

주의:
- External Send = FORBIDDEN
- 반드시 app/utils/push_formatter.py만 사용
- Atomic Write 적용
"""

import json
import uuid
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from pathlib import Path
import sys

# Setup paths
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.utils.push_formatter import render_all_channels

STATE_DIR = BASE_DIR / "state"
OUTBOX_LATEST = BASE_DIR / "reports" / "ops" / "push" / "outbox" / "outbox_latest.json"
PREVIEW_DIR = BASE_DIR / "reports" / "ops" / "push" / "preview"
PREVIEW_LATEST = PREVIEW_DIR / "preview_latest.json"
PREVIEW_SNAPSHOTS_DIR = PREVIEW_DIR / "snapshots"
GATE_FILE = STATE_DIR / "execution_gate.json"


def get_gate_mode() -> str:
    """Gate 모드 조회 (관측용)"""
    if not GATE_FILE.exists():
        return "MOCK_ONLY"
    try:
        data = json.loads(GATE_FILE.read_text(encoding="utf-8"))
        return data.get("mode", "MOCK_ONLY")
    except Exception:
        return "MOCK_ONLY"


def generate_push_preview() -> dict:
    """
    Push 렌더링 프리뷰 생성
    
    입력: outbox_latest.json
    출력: preview_latest.json (Atomic Write)
    """
    preview_id = str(uuid.uuid4())
    asof = datetime.now(KST).isoformat()
    
    # Load Outbox
    if not OUTBOX_LATEST.exists():
        return {
            "result": "SKIPPED",
            "reason": "No outbox_latest.json"
        }
    
    try:
        outbox = json.loads(OUTBOX_LATEST.read_text(encoding="utf-8"))
    except Exception as e:
        return {
            "result": "ERROR",
            "reason": f"Failed to load outbox: {e}"
        }
    
    messages = outbox.get("messages", [])
    observed_gate_mode = get_gate_mode()
    
    # Render all channels for all messages
    all_renders = []
    channels_evaluated = ["CONSOLE", "TELEGRAM", "SLACK", "EMAIL"]
    
    for msg in messages:
        renders = render_all_channels(msg, asof, channels_evaluated)
        all_renders.extend(renders)
    
    # If no messages, render empty preview
    if not messages:
        # Create placeholder render for demonstration
        pass
    
    # Summary
    total_render = len(all_renders)
    blocked_count = sum(1 for r in all_renders if r.get("blocked"))
    
    preview = {
        "schema": "PUSH_RENDER_PREVIEW_V1",
        "preview_id": preview_id,
        "asof": asof,
        "source_outbox_ref": str(OUTBOX_LATEST.relative_to(BASE_DIR)),
        "formatter_ref": "app/utils/push_formatter.py",
        "channels_evaluated": channels_evaluated,
        "observed_gate_mode": observed_gate_mode,
        "rendered": all_renders,
        "summary": {
            "total_render": total_render,
            "pass": total_render - blocked_count,
            "blocked": blocked_count
        }
    }
    
    # Ensure directories
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Atomic Write
    import os
    preview_tmp = PREVIEW_DIR / "preview_latest.json.tmp"
    preview_tmp.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(preview_tmp), str(PREVIEW_LATEST))
    
    # Snapshot
    snapshot_name = f"preview_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}.json"
    snapshot_path = PREVIEW_SNAPSHOTS_DIR / snapshot_name
    snapshot_path.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return {
        "result": "OK",
        "preview_id": preview_id,
        "summary": preview["summary"],
        "preview_latest_path": str(PREVIEW_LATEST.relative_to(BASE_DIR)),
        "snapshot_path": str(snapshot_path.relative_to(BASE_DIR))
    }


if __name__ == "__main__":
    result = generate_push_preview()
    print(json.dumps(result, ensure_ascii=False, indent=2))
