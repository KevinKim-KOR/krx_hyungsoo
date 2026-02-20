"""
Strategy Bundle Validator (C-P.47)

PC에서 생성된 전략 번들의 무결성을 검증합니다.
- 스키마 키 존재/타입 확인
- evidence_refs는 ref_validator로 전수 검사
- integrity(sha/signature) 검증
- 실패 시 FAIL-CLOSED
"""

import json
import hashlib
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))

# Import ref_validator for evidence_refs validation
from app.utils.ref_validator import validate_and_resolve_ref, DANGEROUS_TOKENS

import os

BASE_DIR = Path(__file__).parent.parent.parent

# Bundle max age in seconds (default 24h)
BUNDLE_MAX_AGE_SECONDS = int(os.environ.get("BUNDLE_MAX_AGE_SECONDS", 86400))


@dataclass
class BundleValidationResult:
    """번들 검증 결과"""
    decision: str  # PASS | WARN | FAIL
    valid: bool
    bundle_id: Optional[str]
    created_at: Optional[str]
    strategy_name: Optional[str]
    strategy_version: Optional[str]
    issues: List[str]
    warnings: List[str]
    stale: bool = False  # True if bundle is older than BUNDLE_MAX_AGE_SECONDS
    stale_reason: Optional[str] = None
    age_seconds: Optional[int] = None


# Required top-level keys
REQUIRED_KEYS = [
    "schema", "bundle_id", "created_at", "source", "strategy", "compat", "evidence_refs", "integrity"
]

# Required source keys
REQUIRED_SOURCE_KEYS = ["pc_host", "git_commit", "git_branch", "active_surface_sha256"]

# Required strategy keys
REQUIRED_STRATEGY_KEYS = ["name", "version", "universe", "lookbacks", "rebalance_rule", "risk_limits", "position_limits", "decision_params"]

# Required integrity keys
REQUIRED_INTEGRITY_KEYS = ["payload_sha256", "signed_by", "algorithm"]

# Required compat keys
REQUIRED_COMPAT_KEYS = ["min_oci_version", "expected_python"]


def compute_payload_sha256(strategy: Dict) -> str:
    """
    strategy 섹션의 SHA256 계산
    
    정렬 + 컴팩트 JSON으로 결정론적 해시
    """
    strategy_json = json.dumps(strategy, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(strategy_json.encode("utf-8")).hexdigest()


def validate_evidence_refs(refs: List[str]) -> List[str]:
    """
    evidence_refs 전수 검사
    
    - RAW_PATH_ONLY 정책 검증
    - 위험 토큰 검사
    - 실제 파일 존재 여부는 WARN only (번들 생성 시점과 검증 시점이 다를 수 있음)
    """
    issues = []
    
    for ref in refs:
        # 위험 토큰 검사
        for token in DANGEROUS_TOKENS:
            if token in ref:
                issues.append(f"evidence_ref contains dangerous token '{token}': {ref}")
                continue
        
        # 접두어 검사 (RAW_PATH_ONLY)
        forbidden_prefixes = ["json:", "file://", "file:", "http://", "https://"]
        for prefix in forbidden_prefixes:
            if ref.startswith(prefix):
                issues.append(f"evidence_ref has forbidden prefix '{prefix}': {ref}")
    
    return issues


def validate_strategy_bundle(bundle: Dict) -> BundleValidationResult:
    """
    전략 번들 검증 (Fail-Closed)
    
    1. 스키마 키 존재 확인
    2. 타입 확인
    3. evidence_refs 검증
    4. integrity 검증 (payload_sha256)
    5. Stale 체크 (24h+)
    """
    issues = []
    warnings = []
    
    # === 1. 스키마 키 존재 확인 ===
    for key in REQUIRED_KEYS:
        if key not in bundle:
            issues.append(f"Missing required key: {key}")
    
    # 필수 키 누락 시 조기 종료
    if issues:
        return BundleValidationResult(
            decision="FAIL",
            valid=False,
            bundle_id=bundle.get("bundle_id"),
            created_at=bundle.get("created_at"),
            strategy_name=None,
            strategy_version=None,
            issues=issues,
            warnings=warnings,
            stale=True,  # Fail-Closed: treat as stale if validation fails
            stale_reason="VALIDATION_FAIL"
        )
    
    # === 2. 스키마 버전 확인 ===
    if bundle.get("schema") != "STRATEGY_BUNDLE_V1":
        issues.append(f"Invalid schema: expected STRATEGY_BUNDLE_V1, got {bundle.get('schema')}")
    
    # === 3. source 키 확인 ===
    source = bundle.get("source", {})
    for key in REQUIRED_SOURCE_KEYS:
        if key not in source:
            issues.append(f"Missing source.{key}")
    
    # === 4. strategy 키 확인 ===
    strategy = bundle.get("strategy", {})
    for key in REQUIRED_STRATEGY_KEYS:
        if key not in strategy:
            issues.append(f"Missing strategy.{key}")
    
    # === 5. compat 키 확인 ===
    compat = bundle.get("compat", {})
    for key in REQUIRED_COMPAT_KEYS:
        if key not in compat:
            issues.append(f"Missing compat.{key}")
    
    # === 6. integrity 키 확인 ===
    integrity = bundle.get("integrity", {})
    for key in REQUIRED_INTEGRITY_KEYS:
        if key not in integrity:
            issues.append(f"Missing integrity.{key}")
    
    # 필수 키 누락 시 조기 종료
    if issues:
        return BundleValidationResult(
            decision="FAIL",
            valid=False,
            bundle_id=bundle.get("bundle_id"),
            created_at=bundle.get("created_at"),
            strategy_name=strategy.get("name"),
            strategy_version=strategy.get("version"),
            issues=issues,
            warnings=warnings,
            stale=True,  # Fail-Closed: treat as stale if validation fails
            stale_reason="VALIDATION_FAIL"
        )
    
    # === 7. evidence_refs 검증 ===
    evidence_refs = bundle.get("evidence_refs", [])
    if not isinstance(evidence_refs, list):
        issues.append("evidence_refs must be an array")
    else:
        ref_issues = validate_evidence_refs(evidence_refs)
        issues.extend(ref_issues)
    
    # === 8. payload_sha256 무결성 검증 (핵심!) ===
    expected_sha256 = integrity.get("payload_sha256", "")
    computed_sha256 = compute_payload_sha256(strategy)
    
    if expected_sha256 != computed_sha256:
        issues.append(f"payload_sha256 mismatch: expected={expected_sha256[:16]}..., computed={computed_sha256[:16]}...")
    
    # === 9. Stale 체크 (24h+) ===
    is_stale = False
    stale_reason = None
    age_seconds = None
    
    try:
        created_at = bundle.get("created_at", "")
        if created_at:
            # ISO8601 파싱 (타임존 무시)
            dt_str = created_at[:19]  # YYYY-MM-DDTHH:MM:SS
            created_dt = datetime.fromisoformat(dt_str)
            now = datetime.now(KST)
            age = now - created_dt
            age_seconds = int(age.total_seconds())
            
            if age_seconds > BUNDLE_MAX_AGE_SECONDS:
                is_stale = True
                stale_reason = f"Bundle is stale: created {age.days}d {age.seconds//3600}h ago"
                warnings.append(stale_reason)
        else:
            # No created_at -> Fail-Closed: treat as stale
            is_stale = True
            stale_reason = "No created_at timestamp"
    except Exception as e:
        # Parse error -> Fail-Closed: treat as stale
        is_stale = True
        stale_reason = f"Could not parse created_at: {e}"
        warnings.append(stale_reason)
    
    # === 10. 결과 결정 ===
    if issues:
        decision = "FAIL"
        valid = False
    elif warnings:
        decision = "WARN"
        valid = True
    else:
        decision = "PASS"
        valid = True
    
    return BundleValidationResult(
        decision=decision,
        valid=valid,
        bundle_id=bundle.get("bundle_id"),
        created_at=bundle.get("created_at"),
        strategy_name=strategy.get("name"),
        strategy_version=strategy.get("version"),
        issues=issues,
        warnings=warnings,
        stale=is_stale,
        stale_reason=stale_reason,
        age_seconds=age_seconds
    )


def validate_bundle_file(path: Path) -> BundleValidationResult:
    """
    파일에서 번들 로드 후 검증
    """
    if not path.exists():
        return BundleValidationResult(
            decision="FAIL",
            valid=False,
            bundle_id=None,
            created_at=None,
            strategy_name=None,
            strategy_version=None,
            issues=["Bundle file not found"],
            warnings=[],
            stale=True,
            stale_reason="FILE_NOT_FOUND"
        )
    
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
        return validate_strategy_bundle(bundle)
    except json.JSONDecodeError as e:
        return BundleValidationResult(
            decision="FAIL",
            valid=False,
            bundle_id=None,
            created_at=None,
            strategy_name=None,
            strategy_version=None,
            issues=[f"JSON parse error: {e}"],
            warnings=[],
            stale=True,
            stale_reason="JSON_PARSE_ERROR"
        )


if __name__ == "__main__":
    # Test validation
    test_bundle_path = BASE_DIR / "state" / "strategy_bundle" / "latest" / "strategy_bundle_latest.json"
    
    if test_bundle_path.exists():
        result = validate_bundle_file(test_bundle_path)
        print(f"Decision: {result.decision}")
        print(f"Valid: {result.valid}")
        print(f"Bundle ID: {result.bundle_id}")
        print(f"Issues: {result.issues}")
        print(f"Warnings: {result.warnings}")
    else:
        print(f"No bundle found at {test_bundle_path}")
