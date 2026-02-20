"""
Reco Report Generator (D-P.48)

STRATEGY_BUNDLE_V1을 기반으로 추천 리포트를 생성합니다.
- Fail-Closed: 번들 무결성 실패 시 EMPTY_RECO 생성
- Read-Only: 실제 주문 연동 금지
- Atomic Write 지원
- P101: OCI Reco Generator V1 (Bundle-driven, Read-only)
"""

import json
import os
import hashlib
import uuid
from pathlib import Path
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from typing import Dict, Optional, Any, Tuple, List

from app.load_strategy_bundle import load_latest_bundle, get_bundle_status

BASE_DIR = Path(__file__).parent.parent

# Fixed paths
RECO_DIR = BASE_DIR / "reports" / "live" / "reco"
RECO_LATEST_DIR = RECO_DIR / "latest"
RECO_SNAPSHOTS_DIR = RECO_DIR / "snapshots"
RECO_LATEST_FILE = RECO_LATEST_DIR / "reco_latest.json"


def ensure_dirs():
    """디렉토리 생성"""
    RECO_LATEST_DIR.mkdir(parents=True, exist_ok=True)
    RECO_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def compute_payload_sha256(top_picks: list, holding_actions: list) -> str:
    """
    P101: top_picks + holding_actions의 SHA256 해시 계산
    """
    payload = {
        "top_picks": top_picks,
        "holding_actions": holding_actions
    }
    payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def generate_empty_reco(reason: str, source_bundle: Optional[Dict] = None, reason_detail: str = "") -> Dict:
    """
    EMPTY_RECO 리포트 생성 (P82: reason은 ENUM-only)
    
    - 번들 없음, STALE, 또는 시스템 오류 시 사용
    """
    report_id = str(uuid.uuid4())
    now = datetime.now(KST).isoformat()
    
    top_picks = []
    holding_actions = []
    
    return {
        "schema": "RECO_REPORT_V1",
        "report_id": report_id,
        "created_at": now,
        "source_bundle": source_bundle,
        "decision": "EMPTY_RECO",
        "reason": reason,
        "reason_detail": reason_detail,
        "top_picks": top_picks,
        "holding_actions": holding_actions,
        "summary": {
            "total_positions": 0,
            "buy_count": 0,
            "sell_count": 0,
            "hold_count": 0,
            "cash_pct": 1.0
        },
        "constraints_applied": None,
        "evidence_refs": ["reports/live/reco/latest/reco_latest.json"],
        "integrity": {
            "payload_sha256": compute_payload_sha256(top_picks, holding_actions)
        }
    }


def generate_blocked_reco(reason: str, source_bundle: Optional[Dict] = None, reason_detail: str = "") -> Dict:
    """
    BLOCKED 리포트 생성 (P82: reason은 ENUM-only)
    
    - 번들 무결성 실패 시 사용
    """
    report_id = str(uuid.uuid4())
    now = datetime.now(KST).isoformat()
    
    top_picks = []
    holding_actions = []
    
    return {
        "schema": "RECO_REPORT_V1",
        "report_id": report_id,
        "created_at": now,
        "source_bundle": source_bundle,
        "decision": "BLOCKED",
        "reason": reason,
        "reason_detail": reason_detail,
        "top_picks": top_picks,
        "holding_actions": holding_actions,
        "summary": {
            "total_positions": 0,
            "buy_count": 0,
            "sell_count": 0,
            "hold_count": 0,
            "cash_pct": 1.0
        },
        "constraints_applied": None,
        "evidence_refs": ["reports/live/reco/latest/reco_latest.json"],
        "integrity": {
            "payload_sha256": compute_payload_sha256(top_picks, holding_actions)
        }
    }


def extract_signals_from_bundle(bundle: Dict) -> Tuple[List, List]:
    """
    P101: 번들에서 top_picks와 holding_actions 추출 (Pass-through)
    
    Returns:
        Tuple[top_picks, holding_actions]
    """
    # 1. Top Picks (Scorer)
    # Check strict location: strategy.scorer (P100 standard)
    strategy = bundle.get("strategy", {})
    scorer = strategy.get("scorer", {})
    
    # Fallback to root if not found (Backward compat)
    if not scorer:
        scorer = bundle.get("scorer", {})
        
    top_picks = scorer.get("top_picks", [])
    
    # 2. Holding Actions
    # Check strict location: strategy.holding_action
    holding_action_section = strategy.get("holding_action", {})
    
    # Fallback
    if not holding_action_section:
        holding_action_section = bundle.get("holding_action", {})
        
    holding_actions = holding_action_section.get("items", [])
    
    return top_picks, holding_actions


def generate_reco_report() -> Dict:
    """
    추천 리포트 생성 (메인 함수)
    
    1. 번들 로드 및 검증
    2. 검증 결과에 따라 GENERATED/EMPTY_RECO/BLOCKED 결정
    3. 추천 생성 (GENERATED인 경우)
    4. Atomic Write + Snapshot 저장
    
    Fail-Closed: 모든 예외 상황에서 리포트 저장 + BLOCKED 응답
    
    Returns:
        생성된 리포트 또는 에러 정보
    """
    ensure_dirs()
    
    try:
        # 1. 번들 로드 및 검증
        bundle, validation = load_latest_bundle()
        
        # 2. 결정 로직
        # Case 1: 번들 없음
        if validation.decision == "NO_BUNDLE":
            report = generate_empty_reco("NO_BUNDLE")
            return _save_and_return(report)
        
        # Case 2: 번들 검증 실패 (Fail-Closed)
        if not validation.valid:
            source_bundle = {
                "bundle_id": validation.bundle_id,
                "strategy_name": validation.strategy_name,
                "strategy_version": validation.strategy_version,
                "bundle_decision": validation.decision
            }
            report = generate_blocked_reco("BUNDLE_FAIL", source_bundle)
            return _save_and_return(report)
        
        # Case 3: 번들 STALE (24h+) - getattr for safety (Fail-Closed default)
        is_stale = getattr(validation, "stale", True)  # Default to True if field missing
        if is_stale:
            source_bundle = {
                "bundle_id": validation.bundle_id,
                "strategy_name": validation.strategy_name,
                "strategy_version": validation.strategy_version,
                "bundle_decision": "WARN"
            }
            stale_reason = getattr(validation, "stale_reason", "STALE_CHECK_FAILED")
            # P82: ENUM-only reason + detail separated
            report = generate_empty_reco("BUNDLE_STALE", source_bundle, reason_detail=stale_reason)
            return _save_and_return(report)
        
        # Case 4: 번들 PASS/WARN - 추천 생성
        # P101: Source Bundle 확장
        integrity_section = bundle.get("integrity", {})
        source_bundle = {
            "bundle_id": validation.bundle_id,
            "strategy_name": validation.strategy_name,
            "strategy_version": validation.strategy_version,
            "latest_ref": "state/strategy_bundle/latest/strategy_bundle_latest.json",
            "created_at": validation.created_at,
            "bundle_decision": validation.decision,
            "integrity": {
                "payload_sha256": integrity_section.get("payload_sha256", "")
            }
        }
        
        # P101: Extract signals directly from bundle
        top_picks, holding_actions = extract_signals_from_bundle(bundle)
        
        # Summary 계산 (Holding Actions 기반)
        buy_count = sum(1 for r in holding_actions if r.get("action") == "BUY")
        sell_count = sum(1 for r in holding_actions if r.get("action") == "SELL")
        hold_count = sum(1 for r in holding_actions if r.get("action") == "HOLD") or \
                     sum(1 for r in holding_actions if r.get("action") == "KEEP") # Handle KEEP/HOLD alias
        
        # Cash calc (Holding Actions don't have weight yet, assuming derived from Order Plan later)
        # For Reco V1, cash_pct is placeholder or derived if weights exist
        # P101 doesn't specify weight calculation in Reco, so default to 1.0 or 0.0?
        # Using 1.0 as safe default if no weights
        total_weight = sum(r.get("weight_pct", 0) for r in holding_actions)
        
        strategy = bundle.get("strategy", {})
        position_limits = strategy.get("position_limits", {})
        risk_limits = strategy.get("risk_limits", {})
        
        report_id = str(uuid.uuid4())
        now = datetime.now(KST).isoformat()
        
        # Decision Logic
        if not top_picks and not holding_actions:
            decision = "EMPTY_RECO" # Or WARN per P101
            reason = "NO_SIGNAL"
        else:
            decision = "GENERATED"
            reason = "SUCCESS"
        
        report = {
            "schema": "RECO_REPORT_V1",
            "report_id": report_id,
            "created_at": now,
            "source_bundle": source_bundle,
            "decision": decision,
            "reason": reason,
            "top_picks": top_picks,
            "holding_actions": holding_actions,
            "summary": {
                "total_positions": len(holding_actions), # Using holding actions count or top picks? Usually holdings.
                "buy_count": buy_count,
                "sell_count": sell_count,
                "hold_count": hold_count,
                "cash_pct": round(max(0, 1.0 - total_weight), 4)
            },
            "constraints_applied": {
                "max_position_pct": risk_limits.get("max_position_pct", 0.25),
                "max_positions": position_limits.get("max_positions", 4),
                "min_cash_pct": position_limits.get("min_cash_pct", 0.10)
            },
            "evidence_refs": [
                "state/strategy_bundle/latest/strategy_bundle_latest.json",
                "reports/live/reco/latest/reco_latest.json"
            ],
            "integrity": {
                "payload_sha256": compute_payload_sha256(top_picks, holding_actions)
            }
        }
        
        return _save_and_return(report)
        
    except Exception as e:
        # Fail-Closed: 모든 예외에서 BLOCKED 리포트 저장
        try:
            source_bundle = {
                "bundle_id": getattr(validation, "bundle_id", None) if 'validation' in dir() else None,
                "strategy_name": getattr(validation, "strategy_name", None) if 'validation' in dir() else None,
                "strategy_version": getattr(validation, "strategy_version", None) if 'validation' in dir() else None,
                "bundle_decision": getattr(validation, "decision", "UNKNOWN") if 'validation' in dir() else "UNKNOWN"
            }
        except:
            source_bundle = None
        
        report = generate_blocked_reco(f"SYSTEM_ERROR: {str(e)}", source_bundle)
        return _save_and_return(report)


def _save_and_return(report: Dict) -> Dict:
    """Atomic Write로 리포트 저장 + 스냅샷 생성"""
    import shutil
    ensure_dirs()
    
    snapshot_ref = None
    
    try:
        # 1. Atomic write to latest
        tmp_path = RECO_LATEST_FILE.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_path, RECO_LATEST_FILE)
        
        # 2. Always create snapshot on regenerate
        timestamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
        snapshot_filename = f"reco_{timestamp}.json"
        snapshot_path = RECO_SNAPSHOTS_DIR / snapshot_filename
        
        tmp_snap = snapshot_path.with_suffix(".tmp")
        shutil.copy2(RECO_LATEST_FILE, tmp_snap)
        os.replace(tmp_snap, snapshot_path)
        snapshot_ref = f"reports/live/reco/snapshots/{snapshot_filename}"
        
        return {
            "success": True,
            "report": report,
            "saved_to": "reports/live/reco/latest/reco_latest.json",
            "snapshot_ref": snapshot_ref
        }
    except Exception as e:
        return {
            "success": False,
            "report": report,
            "error": str(e),
            "snapshot_ref": snapshot_ref
        }


def load_latest_reco() -> Optional[Dict]:
    """최신 추천 리포트 로드"""
    if not RECO_LATEST_FILE.exists():
        return None
    
    try:
        return json.loads(RECO_LATEST_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return None


def get_reco_status() -> Dict[str, Any]:
    """
    추천 리포트 상태 조회 (API 응답용)
    """
    report = load_latest_reco()
    
    if report is None:
        return {
            "present": False,
            "decision": "NO_RECO_YET",
            "latest_ref": None,
            "report_id": None,
            "created_at": None,
            "source_bundle": None,
            "summary": None
        }
    
    return {
        "present": True,
        "decision": report.get("decision", "UNKNOWN"),
        "reason": report.get("reason"),
        "latest_ref": "reports/live/reco/latest/reco_latest.json",
        "report_id": report.get("report_id"),
        "created_at": report.get("created_at"),
        "source_bundle": report.get("source_bundle"),
        "summary": report.get("summary")
    }


def list_snapshots() -> list:
    """스냅샷 목록 조회"""
    ensure_dirs()
    
    snapshots = []
    for f in sorted(RECO_SNAPSHOTS_DIR.glob("*.json"), reverse=True):
        stat = f.stat()
        snapshots.append({
            "filename": f.name,
            "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "ref": f"reports/live/reco/snapshots/{f.name}"
        })
    
    return snapshots[:20]


def regenerate_snapshot() -> Dict[str, Any]:
    """
    latest를 snapshot으로 복제
    
    - Atomic copy
    """
    ensure_dirs()
    
    if not RECO_LATEST_FILE.exists():
        return {
            "success": False,
            "snapshot_ref": None,
            "error": "NO_RECO_YET: latest reco does not exist"
        }
    
    report = load_latest_reco()
    if report is None:
        return {
            "success": False,
            "snapshot_ref": None,
            "error": "Failed to load latest reco"
        }
    
    # Generate snapshot filename
    timestamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    snapshot_filename = f"reco_{timestamp}.json"
    snapshot_path = RECO_SNAPSHOTS_DIR / snapshot_filename
    
    # Atomic copy
    try:
        import shutil
        tmp_path = snapshot_path.with_suffix(".tmp")
        shutil.copy2(RECO_LATEST_FILE, tmp_path)
        os.replace(tmp_path, snapshot_path)
        
        return {
            "success": True,
            "snapshot_ref": f"reports/live/reco/snapshots/{snapshot_filename}",
            "report_id": report.get("report_id"),
            "created_at": report.get("created_at")
        }
    except Exception as e:
        return {
            "success": False,
            "snapshot_ref": None,
            "error": str(e)
        }


if __name__ == "__main__":
    result = generate_reco_report()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
