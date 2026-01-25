"""
Strategy Bundle Generator (D-P.49)

PC에서 백테스트/튜닝 결과를 STRATEGY_BUNDLE_V1 스냅샷으로 생성합니다.
- PC에서만 실행 (OCI 아님)
- integrity.payload_sha256 자동 계산
- 출력: state/strategy_bundle/snapshots/strategy_bundle_YYYYMMDD_HHMMSS.json

Usage:
    python deploy/pc/generate_strategy_bundle.py
"""

import json
import hashlib
import uuid
import os
import socket
import subprocess
from datetime import datetime
from pathlib import Path

# 프로젝트 루트
BASE_DIR = Path(__file__).parent.parent.parent

# 출력 경로
OUTPUT_DIR = BASE_DIR / "state" / "strategy_bundle" / "snapshots"


def get_git_info():
    """Git 정보 조회"""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=BASE_DIR
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=BASE_DIR
        ).stdout.strip()
        return commit or "unknown", branch or "unknown"
    except Exception:
        return "unknown", "unknown"


def get_active_surface_sha256():
    """active_surface.json의 SHA256 계산"""
    path = BASE_DIR / "docs" / "ops" / "active_surface.json"
    if path.exists():
        content = path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    return "unknown"


def compute_payload_sha256(strategy: dict) -> str:
    """strategy 섹션의 SHA256 계산"""
    strategy_json = json.dumps(strategy, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(strategy_json.encode("utf-8")).hexdigest()


def generate_bundle() -> dict:
    """
    STRATEGY_BUNDLE_V1 생성
    
    NOTE: 실제 환경에서는 백테스트/튜닝 결과에서 파라미터를 가져와야 합니다.
    현재는 기본 전략 파라미터를 사용합니다.
    """
    now = datetime.now()
    bundle_id = str(uuid.uuid4())
    created_at = now.isoformat()
    
    # Git 정보
    git_commit, git_branch = get_git_info()
    
    # 전략 파라미터 (실제 환경에서는 백테스트 결과에서 로드)
    strategy = {
        "name": "KRX_MOMENTUM_V1",
        "version": "1.0.0",
        "universe": ["069500", "229200", "114800", "122630"],
        "lookbacks": {
            "momentum_period": 20,
            "volatility_period": 14
        },
        "rebalance_rule": {
            "frequency": "DAILY",
            "time_kst": "09:05"
        },
        "risk_limits": {
            "max_position_pct": 0.25,
            "max_drawdown_pct": 0.15
        },
        "position_limits": {
            "max_positions": 4,
            "min_cash_pct": 0.10
        },
        "decision_params": {
            "entry_threshold": 0.02,
            "exit_threshold": -0.03,
            "adx_filter_min": 20
        }
    }
    
    # payload SHA256 계산
    payload_sha256 = compute_payload_sha256(strategy)
    
    bundle = {
        "schema": "STRATEGY_BUNDLE_V1",
        "bundle_id": bundle_id,
        "created_at": created_at,
        "source": {
            "pc_host": socket.gethostname(),
            "git_commit": git_commit,
            "git_branch": git_branch,
            "active_surface_sha256": get_active_surface_sha256()
        },
        "strategy": strategy,
        "compat": {
            "min_oci_version": "1.49",
            "expected_python": "3.10+"
        },
        "evidence_refs": [
            "reports/backtest/latest/backtest_result.json"
        ],
        "integrity": {
            "payload_sha256": payload_sha256,
            "signed_by": "PC_LOCAL",
            "signature": f"auto-{payload_sha256[:16]}",
            "algorithm": "HMAC-SHA256"
        }
    }
    
    return bundle


def save_bundle(bundle: dict) -> Path:
    """번들을 스냅샷 및 최신 파일로 저장"""
    # 1. Snapshot
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"strategy_bundle_{timestamp}.json"
    snapshot_path = OUTPUT_DIR / filename
    
    tmp_snap = snapshot_path.with_suffix(".tmp")
    tmp_snap.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_snap, snapshot_path)
    
    # 2. Latest
    LATEST_DIR = BASE_DIR / "state" / "strategy_bundle" / "latest"
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    latest_path = LATEST_DIR / "strategy_bundle_latest.json"
    
    tmp_latest = latest_path.with_suffix(".tmp")
    tmp_latest.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_latest, latest_path)
    
    return snapshot_path


def main():
    print("=" * 60)
    print("Strategy Bundle Generator (D-P.49) - PC Mode")
    print("=" * 60)
    
    # 1. 번들 생성
    print("\n[1] Generating bundle...")
    bundle = generate_bundle()
    print(f"    bundle_id: {bundle['bundle_id']}")
    print(f"    created_at: {bundle['created_at']}")
    print(f"    strategy: {bundle['strategy']['name']} v{bundle['strategy']['version']}")
    
    # 2. 로컬 검증
    print("\n[2] Validating bundle locally...")
    is_valid = validate_bundle_locally(bundle)
    if not is_valid:
        print("[ERROR] Bundle validation failed! Aborting.")
        return 1
    
    # 3. 저장
    print("\n[3] Saving bundle...")
    snapshot_path = save_bundle(bundle)
    print(f"    Snapshot: {snapshot_path.name}")
    print(f"    Latest:   state/strategy_bundle/latest/strategy_bundle_latest.json")
    
    # 4. Git Push 안내
    print("\n" + "=" * 60)
    print("NEXT STEPS (Git Workflow):")
    print("=" * 60)
    print("""
1. Commit and Push to OCI:
   git add state/strategy_bundle/
   git commit -m "Update strategy bundle"
   git push origin archive-rebuild

2. OCI will pull and run daily ops automatically (cron).
""")
    
    return 0


if __name__ == "__main__":
    exit(main())
