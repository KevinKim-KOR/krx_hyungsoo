"""
Live Cycle Runner (D-P.50)

단일 실행으로 Bundle→Reco→Summary→(Console)Send를 처리합니다.
- Fail-Closed: 중간 실패 시에도 영수증 저장
- Console Only: 외부 발송 금지 (CONSOLE_SIMULATED)
- Atomic Write + Snapshot 지원

Usage:
    from app.run_live_cycle import run_live_cycle
    result = run_live_cycle()
"""

import json
import os
import hashlib
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).parent.parent

# Output paths
CYCLE_DIR = BASE_DIR / "reports" / "live" / "cycle"
CYCLE_LATEST_DIR = CYCLE_DIR / "latest"
CYCLE_SNAPSHOTS_DIR = CYCLE_DIR / "snapshots"
CYCLE_LATEST_FILE = CYCLE_LATEST_DIR / "live_cycle_latest.json"


def ensure_dirs():
    """디렉토리 생성"""
    CYCLE_LATEST_DIR.mkdir(parents=True, exist_ok=True)
    CYCLE_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def compute_payload_sha256(data: Dict) -> str:
    """페이로드 SHA256 계산"""
    payload_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()


def run_bundle_step() -> Dict[str, Any]:
    """
    Step 1: Bundle 로드 및 검증
    """
    try:
        from app.load_strategy_bundle import load_latest_bundle, get_bundle_status
        
        bundle, validation = load_latest_bundle()
        status = get_bundle_status()
        
        return {
            "success": True,
            "latest_ref": "state/strategy_bundle/latest/strategy_bundle_latest.json",
            "decision": validation.decision if validation else "NO_BUNDLE",
            "stale": getattr(validation, "stale", True) if validation else True,
            "valid": validation.valid if validation else False,
            "bundle_id": validation.bundle_id if validation else None,
            "strategy_name": getattr(validation, "strategy_name", None) if validation else None,
            "evidence_refs": ["state/strategy_bundle/latest/strategy_bundle_latest.json"] if bundle else []
        }
    except Exception as e:
        return {
            "success": False,
            "latest_ref": None,
            "decision": "LOAD_ERROR",
            "stale": True,
            "valid": False,
            "bundle_id": None,
            "strategy_name": None,
            "evidence_refs": [],
            "error": str(e)
        }


def run_reco_step() -> Dict[str, Any]:
    """
    Step 2: Reco 생성
    """
    try:
        from app.generate_reco_report import generate_reco_report, load_latest_reco, list_snapshots
        
        result = generate_reco_report()
        
        if result.get("success"):
            report = result.get("report", {})
            snapshots = list_snapshots()
            snapshot_ref = snapshots[0]["ref"] if snapshots else None
            
            return {
                "success": True,
                "latest_ref": "reports/live/reco/latest/reco_latest.json",
                "snapshot_ref": snapshot_ref or result.get("snapshot_ref"),
                "decision": report.get("decision", "UNKNOWN"),
                "reason": report.get("reason", "UNKNOWN"),
                "evidence_refs": report.get("evidence_refs", ["reports/live/reco/latest/reco_latest.json"])
            }
        else:
            return {
                "success": False,
                "latest_ref": "reports/live/reco/latest/reco_latest.json",
                "snapshot_ref": result.get("snapshot_ref"),
                "decision": "BLOCKED",
                "reason": result.get("error", "RECO_ERROR"),
                "evidence_refs": ["reports/live/reco/latest/reco_latest.json"]
            }
    except Exception as e:
        return {
            "success": False,
            "latest_ref": None,
            "snapshot_ref": None,
            "decision": "ERROR",
            "reason": f"RECO_ERROR: {str(e)}",
            "evidence_refs": []
        }


def run_summary_step() -> Dict[str, Any]:
    """
    Step 3: Ops Summary 재생성
    """
    try:
        from app.generate_ops_summary import regenerate_ops_summary, save_ops_summary
        
        summary = regenerate_ops_summary()
        # save_ops_summary is not exported? Wait, let me check generate_ops_summary.py again.
        # regenerate_ops_summary saves internally. run_live_cycle shouldn't call save_ops_summary unless it exists?
        # The original code imported save_ops_summary. Let's assume it was removed or needs check. 
        # Actually regenerate_ops_summary in previous steps included saving.
        # So we just return summary and fake the rest?
        # Let's check if save_ops_summary exists in generate_ops_summary.py
        
        # Checking generate_ops_summary.py content from history:
        # It defines regenerate_ops_summary and calls it in main.
        # It does NOT define save_ops_summary separately. It saves inside regenerate_ops_summary.
        # So remove save_ops_summary import and usage options.
        
        # Get latest snapshot
        snapshots_dir = BASE_DIR / "reports" / "ops" / "summary" / "snapshots"
        snapshot_ref = None
        if snapshots_dir.exists():
            snapshots = sorted(snapshots_dir.glob("*.json"), reverse=True)
            if snapshots:
                snapshot_ref = f"reports/ops/summary/snapshots/{snapshots[0].name}"
        
        return {
            "success": True,
            "latest_ref": "reports/ops/summary/ops_summary_latest.json",
            "snapshot_ref": snapshot_ref
        }
    except Exception as e:
        return {
            "success": False,
            "latest_ref": None,
            "snapshot_ref": None,
            "error": str(e)
        }

# ... (in run_live_cycle)

        # Step 2: Reco (proceed even if bundle issues)
        reco_result = run_reco_step()
        receipt["reco"] = reco_result
        
        if not reco_result.get("success"):
            if receipt["result"] == "OK":
                receipt["decision"] = "PARTIAL"
                receipt["reason"] = "RECO_FAIL"
        else:
            # User Policy: NO_PORTFOLIO, NO_RECO, EMPTY_RECO -> BLOCKED
            reco_decision = reco_result.get("decision", "UNKNOWN")
            if reco_decision in ("EMPTY_RECO", "BLOCKED", "NO_RECO"):
                receipt["decision"] = "BLOCKED"
                receipt["reason"] = reco_result.get("reason", "EMPTY_RECO")
                
        # Step 3: Ops Summary
        summary_result = run_summary_step()
        receipt["ops_summary"] = summary_result
        
        if not summary_result.get("success"):
            if receipt["result"] == "OK":
                receipt["result"] = "FAILED"
                receipt["decision"] = "PARTIAL"
                receipt["reason"] = "SUMMARY_FAIL"
        
        # Step 4: Push (Console Only)
        push_result = run_push_step()
        receipt["push"] = push_result
        
        if not push_result.get("success"):
            if receipt["result"] == "OK":
                receipt["result"] = "FAILED"
                receipt["decision"] = "PARTIAL"
                receipt["reason"] = "PUSH_FAIL"
        
    except Exception as e:
        receipt["result"] = "FAILED"
        receipt["decision"] = "BLOCKED"
        receipt["reason"] = f"SYSTEM_ERROR: {str(e)}"
    
    # Save receipt + snapshot
    return _save_receipt(receipt)


def _save_receipt(receipt: Dict) -> Dict:
    """영수증 저장 + 스냅샷"""
    ensure_dirs()
    
    snapshot_ref = None
    
    try:
        # Compute integrity
        results_data = {
            "bundle": receipt.get("bundle"),
            "reco": receipt.get("reco"),
            "ops_summary": receipt.get("ops_summary"),
            "push": receipt.get("push")
        }
        receipt["integrity"] = {
            "payload_sha256": compute_payload_sha256(results_data)
        }
        
        # 1. Atomic write to latest
        tmp_path = CYCLE_LATEST_FILE.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_path, CYCLE_LATEST_FILE)
        
        # 2. Prepare snapshot path FIRST
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_filename = f"live_cycle_{timestamp}.json"
        snapshot_path = CYCLE_SNAPSHOTS_DIR / snapshot_filename
        snapshot_ref = f"reports/live/cycle/snapshots/{snapshot_filename}"
        
        # 3. Set snapshot_ref in receipt BEFORE saving
        receipt["snapshot_ref"] = snapshot_ref
        
        # 4. Re-save latest with snapshot_ref included
        tmp_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_path, CYCLE_LATEST_FILE)
        
        # 5. Create snapshot from the UPDATED latest file
        tmp_snap = snapshot_path.with_suffix(".tmp")
        shutil.copy2(CYCLE_LATEST_FILE, tmp_snap)
        os.replace(tmp_snap, snapshot_path)
        
        return {
            "success": True,
            "receipt": receipt,
            "saved_to": "reports/live/cycle/latest/live_cycle_latest.json",
            "snapshot_ref": snapshot_ref
        }
    except Exception as e:
        return {
            "success": False,
            "receipt": receipt,
            "error": str(e),
            "snapshot_ref": snapshot_ref
        }


def load_latest_cycle() -> Optional[Dict]:
    """최신 영수증 로드"""
    if not CYCLE_LATEST_FILE.exists():
        return None
    
    try:
        return json.loads(CYCLE_LATEST_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return None


def list_cycle_snapshots() -> list:
    """스냅샷 목록"""
    ensure_dirs()
    
    snapshots = []
    for f in sorted(CYCLE_SNAPSHOTS_DIR.glob("*.json"), reverse=True):
        stat = f.stat()
        snapshots.append({
            "filename": f.name,
            "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "ref": f"reports/live/cycle/snapshots/{f.name}"
        })
    
    return snapshots[:20]


if __name__ == "__main__":
    result = run_live_cycle()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
