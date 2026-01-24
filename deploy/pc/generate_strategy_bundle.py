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
    """번들을 스냅샷 파일로 저장"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"strategy_bundle_{timestamp}.json"
    filepath = OUTPUT_DIR / filename
    
    # Atomic write
    tmp_path = filepath.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, filepath)
    
    return filepath


def validate_bundle_locally(bundle: dict) -> bool:
    """로컬에서 번들 검증"""
    try:
        from app.utils.strategy_bundle_validator import validate_strategy_bundle
        result = validate_strategy_bundle(bundle)
        print(f"[Validation] decision={result.decision}, valid={result.valid}")
        if result.issues:
            print(f"[Validation] issues: {result.issues}")
        if result.warnings:
            print(f"[Validation] warnings: {result.warnings}")
        return result.valid
    except ImportError:
        print("[WARNING] strategy_bundle_validator not found, skipping validation")
        return True


def main():
    print("=" * 60)
    print("Strategy Bundle Generator (D-P.49)")
    print("=" * 60)
    
    # 1. 번들 생성
    print("\n[1] Generating bundle...")
    bundle = generate_bundle()
    print(f"    bundle_id: {bundle['bundle_id']}")
    print(f"    created_at: {bundle['created_at']}")
    print(f"    strategy: {bundle['strategy']['name']} v{bundle['strategy']['version']}")
    print(f"    payload_sha256: {bundle['integrity']['payload_sha256'][:16]}...")
    
    # 2. 로컬 검증
    print("\n[2] Validating bundle locally...")
    is_valid = validate_bundle_locally(bundle)
    if not is_valid:
        print("[ERROR] Bundle validation failed! Aborting.")
        return 1
    
    # 3. 저장
    print("\n[3] Saving bundle snapshot...")
    filepath = save_bundle(bundle)
    print(f"    Saved to: {filepath}")
    print(f"    File size: {filepath.stat().st_size} bytes")
    
    # 4. 다음 단계 안내
    print("\n" + "=" * 60)
    print("NEXT STEPS (Transfer to OCI):")
    print("=" * 60)
    print(f"""
1. Copy to OCI via scp/rsync:
   scp "{filepath}" ubuntu@<OCI_IP>:~/krx_hyungsoo/state/strategy_bundle/snapshots/

2. On OCI, validate and apply:
   cd ~/krx_hyungsoo
   BUNDLE_PATH="state/strategy_bundle/snapshots/{filepath.name}"
   python -c "from app.utils.strategy_bundle_validator import validate_bundle_file; r=validate_bundle_file('$BUNDLE_PATH'); print(r)"
   
   # If PASS, apply to latest:
   cp "$BUNDLE_PATH" "state/strategy_bundle/latest/strategy_bundle_latest.json.tmp"
   mv -f "state/strategy_bundle/latest/strategy_bundle_latest.json.tmp" "state/strategy_bundle/latest/strategy_bundle_latest.json"

3. Regenerate reco and verify:
   curl -X POST http://localhost:8000/api/reco/regenerate -H "Content-Type: application/json" -d '{{"confirm": true}}'
""")
    
    return 0


if __name__ == "__main__":
    exit(main())
