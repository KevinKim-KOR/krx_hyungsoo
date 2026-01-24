"""
Reco Report Generator (D-P.48)

STRATEGY_BUNDLE_V1을 기반으로 추천 리포트를 생성합니다.
- Fail-Closed: 번들 무결성 실패 시 EMPTY_RECO 생성
- Read-Only: 실제 주문 연동 금지
- Atomic Write 지원
"""

import json
import os
import hashlib
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any

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


def compute_payload_sha256(recommendations: list) -> str:
    """추천 목록의 SHA256 해시 계산"""
    payload_str = json.dumps(recommendations, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()


def generate_empty_reco(reason: str, source_bundle: Optional[Dict] = None) -> Dict:
    """
    EMPTY_RECO 리포트 생성
    
    - 번들 없음, STALE, 또는 시스템 오류 시 사용
    """
    report_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    recommendations = []
    
    return {
        "schema": "RECO_REPORT_V1",
        "report_id": report_id,
        "created_at": now,
        "source_bundle": source_bundle,
        "decision": "EMPTY_RECO",
        "reason": reason,
        "recommendations": recommendations,
        "summary": {
            "total_positions": 0,
            "buy_count": 0,
            "sell_count": 0,
            "hold_count": 0,
            "cash_pct": 1.0
        },
        "constraints_applied": None,
        "evidence_refs": [],
        "integrity": {
            "payload_sha256": compute_payload_sha256(recommendations)
        }
    }


def generate_blocked_reco(reason: str, source_bundle: Optional[Dict] = None) -> Dict:
    """
    BLOCKED 리포트 생성 (Fail-Closed)
    
    - 번들 무결성 실패 시 사용
    """
    report_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    recommendations = []
    
    return {
        "schema": "RECO_REPORT_V1",
        "report_id": report_id,
        "created_at": now,
        "source_bundle": source_bundle,
        "decision": "BLOCKED",
        "reason": reason,
        "recommendations": recommendations,
        "summary": {
            "total_positions": 0,
            "buy_count": 0,
            "sell_count": 0,
            "hold_count": 0,
            "cash_pct": 1.0
        },
        "constraints_applied": None,
        "evidence_refs": [],
        "integrity": {
            "payload_sha256": compute_payload_sha256(recommendations)
        }
    }


def generate_recommendations_from_bundle(bundle: Dict) -> list:
    """
    번들 전략 파라미터를 기반으로 추천 생성
    
    NOTE: 실제 구현에서는 시장 데이터와 전략 로직을 사용해야 합니다.
    현재는 전략 파라미터 기반 Placeholder 추천을 생성합니다.
    """
    strategy = bundle.get("strategy", {})
    universe = strategy.get("universe", [])
    decision_params = strategy.get("decision_params", {})
    
    recommendations = []
    
    # Placeholder: 유니버스 종목에 대한 기본 추천 생성
    ticker_names = {
        "069500": "KODEX 200",
        "229200": "KODEX 코스닥150",
        "114800": "KODEX 인버스",
        "122630": "KODEX 레버리지",
        "252670": "KODEX 200선물인버스2X"
    }
    
    for i, ticker in enumerate(universe[:4]):  # max 4 positions
        # Placeholder logic: 간단한 순환 패턴
        actions = ["BUY", "HOLD", "SELL"]
        action = actions[i % 3] if i < 3 else "HOLD"
        
        if action != "HOLD":
            entry_threshold = decision_params.get("entry_threshold", 0.02)
            recommendations.append({
                "ticker": ticker,
                "name": ticker_names.get(ticker, f"ETF {ticker}"),
                "action": action,
                "weight_pct": 0.25,
                "signal_score": entry_threshold + 0.01 if action == "BUY" else -(entry_threshold + 0.01),
                "rationale": f"전략 파라미터 기반 추천 ({strategy.get('name', 'N/A')})"
            })
    
    return recommendations


def generate_reco_report() -> Dict:
    """
    추천 리포트 생성 (메인 함수)
    
    1. 번들 로드 및 검증
    2. 검증 결과에 따라 GENERATED/EMPTY_RECO/BLOCKED 결정
    3. 추천 생성 (GENERATED인 경우)
    4. Atomic Write로 저장
    
    Returns:
        생성된 리포트 또는 에러 정보
    """
    ensure_dirs()
    
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
    
    # Case 3: 번들 STALE (24h+)
    if validation.stale:
        source_bundle = {
            "bundle_id": validation.bundle_id,
            "strategy_name": validation.strategy_name,
            "strategy_version": validation.strategy_version,
            "bundle_decision": "WARN"
        }
        report = generate_empty_reco("BUNDLE_STALE", source_bundle)
        return _save_and_return(report)
    
    # Case 4: 번들 PASS/WARN - 추천 생성
    try:
        source_bundle = {
            "bundle_id": validation.bundle_id,
            "strategy_name": validation.strategy_name,
            "strategy_version": validation.strategy_version,
            "bundle_decision": validation.decision
        }
        
        recommendations = generate_recommendations_from_bundle(bundle)
        
        # Summary 계산
        buy_count = sum(1 for r in recommendations if r["action"] == "BUY")
        sell_count = sum(1 for r in recommendations if r["action"] == "SELL")
        hold_count = sum(1 for r in recommendations if r["action"] == "HOLD")
        total_weight = sum(r["weight_pct"] for r in recommendations)
        
        strategy = bundle.get("strategy", {})
        position_limits = strategy.get("position_limits", {})
        risk_limits = strategy.get("risk_limits", {})
        
        report_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        report = {
            "schema": "RECO_REPORT_V1",
            "report_id": report_id,
            "created_at": now,
            "source_bundle": source_bundle,
            "decision": "GENERATED",
            "reason": "SUCCESS",
            "recommendations": recommendations,
            "summary": {
                "total_positions": len(recommendations),
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
                "payload_sha256": compute_payload_sha256(recommendations)
            }
        }
        
        return _save_and_return(report)
        
    except Exception as e:
        source_bundle = {
            "bundle_id": validation.bundle_id,
            "strategy_name": validation.strategy_name,
            "strategy_version": validation.strategy_version,
            "bundle_decision": validation.decision
        }
        report = generate_blocked_reco(f"SYSTEM_ERROR: {str(e)}", source_bundle)
        return _save_and_return(report)


def _save_and_return(report: Dict) -> Dict:
    """Atomic Write로 리포트 저장"""
    ensure_dirs()
    
    try:
        # Atomic write
        tmp_path = RECO_LATEST_FILE.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_path, RECO_LATEST_FILE)
        
        return {
            "success": True,
            "report": report,
            "saved_to": "reports/live/reco/latest/reco_latest.json"
        }
    except Exception as e:
        return {
            "success": False,
            "report": report,
            "error": str(e)
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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
