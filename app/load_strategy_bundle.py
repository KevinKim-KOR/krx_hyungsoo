"""
Strategy Bundle Loader (C-P.47)

PC에서 생성된 전략 번들을 로드하고 관리합니다.
- latest/snapshot 경로 고정
- 파일 없으면 NO_BUNDLE_YET로 Graceful
- Atomic Write 지원
"""

import json
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from typing import Dict, Optional, Tuple, Any

from app.utils.strategy_bundle_validator import (
    validate_strategy_bundle,
    validate_bundle_file,
    BundleValidationResult
)

BASE_DIR = Path(__file__).parent.parent

# Fixed paths
BUNDLE_DIR = BASE_DIR / "state" / "strategy_bundle"
BUNDLE_LATEST_DIR = BUNDLE_DIR / "latest"
BUNDLE_SNAPSHOTS_DIR = BUNDLE_DIR / "snapshots"
BUNDLE_LATEST_FILE = BUNDLE_LATEST_DIR / "strategy_bundle_latest.json"


def ensure_dirs():
    """디렉토리 생성"""
    BUNDLE_LATEST_DIR.mkdir(parents=True, exist_ok=True)
    BUNDLE_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def load_latest_bundle() -> Tuple[Optional[Dict], BundleValidationResult]:
    """
    최신 번들 로드 + 검증
    
    Returns:
        (bundle_data, validation_result)
        - bundle_data: 번들 JSON 또는 None
        - validation_result: 검증 결과
    """
    if not BUNDLE_LATEST_FILE.exists():
        return None, BundleValidationResult(
            decision="NO_BUNDLE",
            valid=False,
            bundle_id=None,
            created_at=None,
            strategy_name=None,
            strategy_version=None,
            issues=["NO_BUNDLE_YET"],
            warnings=[]
        )
    
    try:
        bundle = json.loads(BUNDLE_LATEST_FILE.read_text(encoding="utf-8"))
        validation = validate_strategy_bundle(bundle)
        
        # Fail-Closed: 검증 실패 시 번들 반환하지 않음
        if not validation.valid:
            return None, validation
        
        return bundle, validation
    except json.JSONDecodeError as e:
        return None, BundleValidationResult(
            decision="FAIL",
            valid=False,
            bundle_id=None,
            created_at=None,
            strategy_name=None,
            strategy_version=None,
            issues=[f"JSON parse error: {e}"],
            warnings=[]
        )


def get_bundle_status() -> Dict[str, Any]:
    """
    번들 상태 조회 (API 응답용)
    
    Returns:
        - present: 번들 존재 여부
        - decision: PASS/WARN/FAIL/NO_BUNDLE
        - latest_ref: 최신 번들 경로
        - bundle_id, created_at, strategy_name, strategy_version
        - issues, warnings
    """
    bundle, validation = load_latest_bundle()
    
    latest_ref = "state/strategy_bundle/latest/strategy_bundle_latest.json" if BUNDLE_LATEST_FILE.exists() else None
    
    return {
        "present": bundle is not None,
        "decision": validation.decision,
        "latest_ref": latest_ref,
        "bundle_id": validation.bundle_id,
        "created_at": validation.created_at,
        "strategy_name": validation.strategy_name,
        "strategy_version": validation.strategy_version,
        "issues": validation.issues,
        "warnings": validation.warnings,
        "stale": validation.stale,
        "stale_reason": validation.stale_reason
    }


def list_snapshots() -> list:
    """
    스냅샷 목록 조회
    
    Returns:
        [{"filename": "...", "mtime": "...", "ref": "..."}]
    """
    ensure_dirs()
    
    snapshots = []
    for f in sorted(BUNDLE_SNAPSHOTS_DIR.glob("*.json"), reverse=True):
        stat = f.stat()
        snapshots.append({
            "filename": f.name,
            "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "ref": f"state/strategy_bundle/snapshots/{f.name}"
        })
    
    return snapshots[:20]  # 최근 20개만


def regenerate_snapshot() -> Dict[str, Any]:
    """
    latest를 snapshot으로 복제
    
    - 경로 입력 금지 (고정 경로만)
    - Atomic copy
    
    Returns:
        {"success": bool, "snapshot_ref": "...", "error": "..."}
    """
    ensure_dirs()
    
    if not BUNDLE_LATEST_FILE.exists():
        return {
            "success": False,
            "snapshot_ref": None,
            "error": "NO_BUNDLE_YET: latest bundle does not exist"
        }
    
    # Validate first
    bundle, validation = load_latest_bundle()
    if not validation.valid:
        return {
            "success": False,
            "snapshot_ref": None,
            "error": f"Bundle validation failed: {validation.issues}"
        }
    
    # Generate snapshot filename
    timestamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    snapshot_filename = f"strategy_bundle_{timestamp}.json"
    snapshot_path = BUNDLE_SNAPSHOTS_DIR / snapshot_filename
    
    # Atomic copy
    try:
        tmp_path = snapshot_path.with_suffix(".tmp")
        shutil.copy2(BUNDLE_LATEST_FILE, tmp_path)
        os.replace(tmp_path, snapshot_path)
        
        return {
            "success": True,
            "snapshot_ref": f"state/strategy_bundle/snapshots/{snapshot_filename}",
            "bundle_id": validation.bundle_id,
            "created_at": validation.created_at
        }
    except Exception as e:
        return {
            "success": False,
            "snapshot_ref": None,
            "error": str(e)
        }


if __name__ == "__main__":
    status = get_bundle_status()
    print(json.dumps(status, indent=2, default=str))
