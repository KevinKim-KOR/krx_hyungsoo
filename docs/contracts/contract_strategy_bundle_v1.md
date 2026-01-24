# Contract: Strategy Bundle V1

**Version**: 1.0
**Date**: 2026-01-24
**Status**: LOCKED

---

## 1. 개요

PC(고성능)에서 백테스트/튜닝으로 확정된 전략 파라미터를 OCI(운영)가 안전하게 수용하기 위한 번들 스키마를 정의합니다.

> 🔒 **PC = Generate + Sign**: PC에서만 생성/서명
> 
> 🔒 **OCI = Validate + Load**: OCI는 검증 후 읽기 전용 수용
> 
> 🔒 **Fail-Closed**: 무결성 불일치 시 적용 금지 + BLOCKED

---

## 2. Schema: STRATEGY_BUNDLE_V1

```json
{
  "schema": "STRATEGY_BUNDLE_V1",
  "bundle_id": "uuid-v4",
  "created_at": "2026-01-24T10:00:00+09:00",
  "source": {
    "pc_host": "KEVIN-PC",
    "git_commit": "abc1234",
    "git_branch": "main",
    "active_surface_sha256": "sha256-of-active_surface.json"
  },
  "strategy": {
    "name": "KRX_MOMENTUM_V1",
    "version": "1.0.0",
    "universe": ["069500", "229200", "114800"],
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
  },
  "compat": {
    "min_oci_version": "1.45",
    "expected_python": "3.10+"
  },
  "evidence_refs": [
    "reports/backtest/latest/backtest_result.json",
    "reports/validation/latest/oos_validation.json"
  ],
  "integrity": {
    "payload_sha256": "sha256-of-strategy-section",
    "signed_by": "PC_LOCAL",
    "signature": "hmac-sha256-signature",
    "algorithm": "HMAC-SHA256"
  }
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `schema` | string | ✓ | "STRATEGY_BUNDLE_V1" |
| `bundle_id` | UUID | ✓ | 고유 식별자 |
| `created_at` | ISO8601 | ✓ | 생성 시각 (KST) |
| `source` | object | ✓ | 출처 정보 |
| `source.pc_host` | string | ✓ | PC 호스트명 |
| `source.git_commit` | string | ✓ | Git 커밋 해시 (short) |
| `source.git_branch` | string | ✓ | Git 브랜치명 |
| `source.active_surface_sha256` | string | ✓ | active_surface.json의 SHA256 |
| `strategy` | object | ✓ | 전략 파라미터 묶음 |
| `strategy.name` | string | ✓ | 전략 이름 |
| `strategy.version` | string | ✓ | 전략 버전 |
| `strategy.universe` | array | ✓ | 거래 대상 (코드 또는 규칙 참조) |
| `strategy.lookbacks` | object | ✓ | Lookback 기간 설정 |
| `strategy.rebalance_rule` | object | ✓ | 리밸런싱 규칙 |
| `strategy.risk_limits` | object | ✓ | 리스크 제한 |
| `strategy.position_limits` | object | ✓ | 포지션 제한 |
| `strategy.decision_params` | object | ✓ | 의사결정 파라미터 |
| `compat` | object | ✓ | 호환성 정보 |
| `compat.min_oci_version` | string | ✓ | 최소 OCI active_surface 버전 |
| `compat.expected_python` | string | ✓ | 예상 Python 버전 |
| `evidence_refs` | array | ✓ | 증거 참조 경로 (RAW_PATH_ONLY) |
| `integrity` | object | ✓ | 무결성 정보 |
| `integrity.payload_sha256` | string | ✓ | strategy 섹션의 SHA256 |
| `integrity.signed_by` | string | ✓ | 서명 주체 (PC_LOCAL) |
| `integrity.signature` | string | ✓ | HMAC 서명 |
| `integrity.algorithm` | string | ✓ | 서명 알고리즘 |

---

## 4. 무결성 검증 규칙

### 4-A. payload_sha256 계산

```python
import json
import hashlib

strategy_json = json.dumps(bundle["strategy"], sort_keys=True, separators=(',', ':'))
payload_sha256 = hashlib.sha256(strategy_json.encode("utf-8")).hexdigest()
```

### 4-B. 검증 실패 시 (Fail-Closed)

| 조건 | 결과 |
|------|------|
| `payload_sha256` 불일치 | decision=FAIL, BLOCKED |
| `signature` 검증 실패 | decision=FAIL, BLOCKED |
| 필수 키 누락 | decision=FAIL, BLOCKED |
| `evidence_refs` 경로 위반 | decision=WARN |

---

## 5. 저장소 경로

| 경로 | 용도 | 방식 |
|------|------|------|
| `state/strategy_bundle/latest/strategy_bundle_latest.json` | 최신 번들 | Atomic Write |
| `state/strategy_bundle/snapshots/*.json` | 스냅샷 | Append-only |

---

## 6. 금지사항

> ⚠️ **번들에 절대 포함 금지**

- API 토큰/키
- 계정 ID/비밀번호
- .env 값
- 개인정보

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-24 | 초기 버전 (Phase C-P.47) |
