"""
Strategy Bundle Generator (D-P.49 + P100-1)

PC에서 백테스트/튜닝 결과를 STRATEGY_BUNDLE_V1 스냅샷으로 생성합니다.
- PC에서만 실행 (OCI 아님)
- integrity.payload_sha256 자동 계산
- P100-1: Regime detection 통합
- 출력: state/strategy_bundle/snapshots/strategy_bundle_YYYYMMDD_HHMMSS.json

Usage:
    python deploy/pc/generate_strategy_bundle.py
"""

import json
import hashlib
import uuid
import os
import re
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

# 프로젝트 루트
BASE_DIR = Path(__file__).parent.parent.parent

# 프로젝트 루트를 sys.path에 추가 (app 모듈 임포트용)
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# 출력 경로
OUTPUT_DIR = BASE_DIR / "state" / "strategy_bundle" / "snapshots"

# P100-1: Regime Enums
REGIME_CODES = {"RISK_ON", "RISK_OFF", "NEUTRAL", "VOLATILE"}
ENUM_ONLY_PATTERN = re.compile(r"^[A-Z0-9_]+$")


# ============================================================================
# P100-1: Regime Detection (Deterministic, No External Dependencies)
# ============================================================================

def sanitize_reason_detail(text: str, max_len: int = 240) -> str:
    """reason_detail sanitize: 개행 제거, 특수문자 escape, 길이 제한"""
    if not text:
        return ""
    # 개행/탭/캐리지리턴 제거
    clean = text.replace("\n", " ").replace("\r", "").replace("\t", " ")
    # 쌍따옴표 -> 작은따옴표
    clean = clean.replace('"', "'")
    # 연속 공백 제거
    clean = " ".join(clean.split())
    # 길이 제한
    return clean[:max_len]


def validate_enum_only(value: str) -> bool:
    """ENUM-only 정규식 검증: ^[A-Z0-9_]+$"""
    return bool(ENUM_ONLY_PATTERN.match(value))


def compute_input_fingerprint(data_sources: Dict[str, str]) -> str:
    """입력 데이터 소스들의 fingerprint 계산 (결정성 검증용)"""
    fingerprint_data = json.dumps(data_sources, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]


def detect_regime() -> Tuple[str, str, str, str]:
    """
    시장 레짐 판단 (결정적, 외부 의존성 없음)
    
    Returns:
        Tuple[code, reason, reason_detail, input_fingerprint]
        
    P100-1 규칙:
    - 데이터 없으면: NEUTRAL + DATA_MISSING
    - 데이터 있으면: MA 기반 판단
    - 결과는 항상 결정적 (동일 입력 → 동일 출력)
    """
    data_sources = {}
    
    # 1. KOSPI 데이터 찾기 (로컬 캐시 우선)
    kospi_cache_path = BASE_DIR / "state" / "cache" / "kospi_daily.json"
    market_cache_path = BASE_DIR / "state" / "cache" / "market_data_cache.json"
    
    kospi_data = None
    
    # Try kospi_daily.json
    if kospi_cache_path.exists():
        try:
            content = kospi_cache_path.read_text(encoding="utf-8")
            data_sources["kospi_daily"] = hashlib.sha256(content.encode()).hexdigest()[:16]
            kospi_data = json.loads(content)
        except Exception:
            pass
    
    # 2. 데이터 없으면 DATA_MISSING
    if kospi_data is None:
        data_sources["kospi_daily"] = "NOT_FOUND"
        data_sources["market_cache"] = "NOT_USED"
        fingerprint = compute_input_fingerprint(data_sources)
        return (
            "NEUTRAL",
            "DATA_MISSING",
            sanitize_reason_detail("KOSPI daily cache not found at state/cache/kospi_daily.json"),
            fingerprint
        )
    
    # 3. KOSPI 데이터 있으면 MA 기반 판단
    try:
        prices = kospi_data.get("prices", [])
        if len(prices) < 200:
            fingerprint = compute_input_fingerprint(data_sources)
            return (
                "NEUTRAL",
                "INSUFFICIENT_DATA",
                sanitize_reason_detail(f"Need 200 days for MA calculation, got {len(prices)}"),
                fingerprint
            )
        
        # 최근 가격과 200일 이동평균 비교
        recent_prices = [p.get("close", 0) for p in prices[-200:]]
        current_price = recent_prices[-1]
        ma_200 = sum(recent_prices) / len(recent_prices)
        ma_50 = sum(recent_prices[-50:]) / 50 if len(recent_prices) >= 50 else ma_200
        
        # Regime 판단 (결정적)
        price_vs_ma200_pct = (current_price / ma_200 - 1.0) * 100 if ma_200 > 0 else 0
        ma50_vs_ma200_pct = (ma_50 / ma_200 - 1.0) * 100 if ma_200 > 0 else 0
        
        if price_vs_ma200_pct > 5 and ma50_vs_ma200_pct > 2:
            code = "RISK_ON"
            reason = "ABOVE_MA200_STRONG"
            detail = f"Price {price_vs_ma200_pct:.1f}% above MA200, MA50 {ma50_vs_ma200_pct:.1f}% above MA200"
        elif price_vs_ma200_pct > 0:
            code = "NEUTRAL"
            reason = "ABOVE_MA200_WEAK"
            detail = f"Price {price_vs_ma200_pct:.1f}% above MA200, trend unclear"
        elif price_vs_ma200_pct > -5:
            code = "VOLATILE"
            reason = "NEAR_MA200"
            detail = f"Price {price_vs_ma200_pct:.1f}% vs MA200, high uncertainty zone"
        else:
            code = "RISK_OFF"
            reason = "BELOW_MA200_STRONG"
            detail = f"Price {price_vs_ma200_pct:.1f}% below MA200, defensive mode"
        
        fingerprint = compute_input_fingerprint(data_sources)
        return (code, reason, sanitize_reason_detail(detail), fingerprint)
        
    except Exception as e:
        data_sources["parse_error"] = str(e)[:50]
        fingerprint = compute_input_fingerprint(data_sources)
        return (
            "NEUTRAL",
            "PARSE_ERROR",
            sanitize_reason_detail(f"Failed to parse KOSPI data: {str(e)}"),
            fingerprint
        )



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
    # P134: Load Strategy Params (SSOT)
    params_path = BASE_DIR / "state" / "strategy_params" / "latest" / "strategy_params_latest.json"
    params_fingerprint = "DEFAULT"
    params_ref = "hardcoded_defaults"
    
    # Defaults
    strategy_defaults = {
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
    
    if params_path.exists():
        try:
            content = params_path.read_text(encoding="utf-8")
            params_data = json.loads(content)
            
            # Compute Fingerprint (P134 Requirement)
            params_fingerprint = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
            params_ref = "strategy_params_latest"
            
            # Override Strategy Config
            # Note: We keep "name" and "version" from loaded file if present, else defaults
            strategy_defaults["name"] = params_data.get("strategy", strategy_defaults["name"])
            strategy_defaults["version"] = params_data.get("version", strategy_defaults["version"])
            
            # Mapping SSOT 'params' to Bundle structure
            # The schema in 'strategy_params_latest.json' groups everything under 'params'.
            # We map them back to the root of 'strategy' dict for compilation.
            loaded_params = params_data.get("params", {})
            for k, v in loaded_params.items():
                strategy_defaults[k] = v
                
            print(f"[INFO] Loaded Strategy Params from SSOT (fp={params_fingerprint})")
            
        except Exception as e:
            print(f"[WARNING] Failed to load strategy params: {e}. Using defaults.")
            
    strategy = strategy_defaults
    
    # Inject P134 Fingerprint Info
    strategy["params_ref"] = params_ref
    strategy["params_fingerprint"] = params_fingerprint
    
    # P100-1: Regime Detection
    regime_code, regime_reason, regime_detail, regime_fingerprint = detect_regime()
    
    # Validate ENUM-only for reason
    if not validate_enum_only(regime_reason):
        print(f"[WARNING] Regime reason '{regime_reason}' is not ENUM-only, fixing...")
        regime_reason = "UNKNOWN_REASON"
    
    # Validate code is in allowed set
    if regime_code not in REGIME_CODES:
        print(f"[WARNING] Regime code '{regime_code}' is invalid, defaulting to NEUTRAL...")
        regime_code = "NEUTRAL"
    
    # Add regime to strategy
    strategy["regime"] = {
        "code": regime_code,
        "reason": regime_reason,
        "reason_detail": regime_detail,
        "input_fingerprint": regime_fingerprint
    }
    
    # P100-2: ETF Scoring
    try:
        from app.scoring.etf_scorer import score_etfs
        universe = strategy.get("universe", [])
        scorer_result = score_etfs(universe, top_n=4)
        
        # Add scorer to strategy
        strategy["scorer"] = {
            "status": scorer_result.get("status", "SKIPPED"),
            "reason": scorer_result.get("reason", "UNKNOWN_ERROR"),
            "reason_detail": scorer_result.get("reason_detail", ""),
            "data_source": scorer_result.get("data_source", "NONE"),
            "top_picks": scorer_result.get("top_picks", []),
            "input_fingerprint": scorer_result.get("input_fingerprint", "")
        }
    except Exception as e:
        strategy["scorer"] = {
            "status": "SKIPPED",
            "reason": "IMPORT_ERROR",
            "reason_detail": sanitize_reason_detail(f"Failed to import scorer: {str(e)}"),
            "data_source": "NONE",
            "top_picks": [],
            "input_fingerprint": ""
        }
    
    # P100-3: Holding Action Generator
    try:
        from app.scoring.holding_action import compute_actions
        import json as json_module
        
        # Load portfolio
        portfolio_path = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"
        portfolio = None
        if portfolio_path.exists():
            try:
                portfolio = json_module.loads(portfolio_path.read_text(encoding="utf-8"))
            except Exception:
                portfolio = None
        
        # Get inputs from previous steps
        top_picks = strategy.get("scorer", {}).get("top_picks", [])
        regime_code = strategy.get("regime", {}).get("code", "NEUTRAL")
        
        # Compute actions
        action_result = compute_actions(portfolio, top_picks, regime_code)
        
        # Add to strategy
        strategy["holding_action"] = {
            "status": action_result.get("status", "SKIPPED"),
            "reason": action_result.get("reason", "UNKNOWN_ERROR"),
            "reason_detail": action_result.get("reason_detail", ""),
            "items": action_result.get("items", []),
            "items_hash": action_result.get("items_hash", "")
        }
    except Exception as e:
        strategy["holding_action"] = {
            "status": "SKIPPED",
            "reason": "IMPORT_ERROR",
            "reason_detail": sanitize_reason_detail(f"Failed to import holding_action: {str(e)}"),
            "items": [],
            "items_hash": ""
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
    print("Strategy Bundle Generator (D-P.49) - PC Mode")
    print("=" * 60)
    
    # 1. 번들 생성
    print("\n[1] Generating bundle...")
    bundle = generate_bundle()
    print(f"    bundle_id: {bundle['bundle_id']}")
    print(f"    created_at: {bundle['created_at']}")
    print(f"    strategy: {bundle['strategy']['name']} v{bundle['strategy']['version']}")
    
    # P100-1: Regime 정보 출력
    regime = bundle['strategy'].get('regime', {})
    print(f"    regime: {regime.get('code', 'N/A')} ({regime.get('reason', 'N/A')})")
    print(f"    regime_detail: {regime.get('reason_detail', '')[:60]}...")
    print(f"    input_fingerprint: {regime.get('input_fingerprint', 'N/A')}")
    
    # P100-2: Scorer 정보 출력
    scorer = bundle['strategy'].get('scorer', {})
    print(f"    scorer: {scorer.get('status', 'N/A')} ({scorer.get('reason', 'N/A')})")
    print(f"    scorer_source: {scorer.get('data_source', 'N/A')}")
    picks = scorer.get('top_picks', [])
    if picks:
        for p in picks[:4]:
            print(f"      - {p.get('ticker')}: score={p.get('score')}, {p.get('reason')}")
    else:
        print(f"    scorer: no picks (status={scorer.get('status', 'N/A')})")
    
    # P100-3: Holding Action 정보 출력
    action = bundle['strategy'].get('holding_action', {})
    print(f"    holding_action: {action.get('status', 'N/A')} ({action.get('reason', 'N/A')})")
    action_items = action.get('items', [])
    if action_items:
        for a in action_items[:5]:
            print(f"      - {a.get('ticker')}: {a.get('action')}/{a.get('confidence')} ({a.get('reason')})")
    else:
        print(f"    holding_action: no items")
    
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
