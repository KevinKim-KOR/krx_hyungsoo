"""Spike freshness guard (OCI Operational Market Data Refresh v1 · C 확정).

Spike runner 는 외부 거래일 조회를 다시 하지 않는다. freshness 는 07:20 일일 갱신
배치가 한 번 확정·저장하고, Spike 는 그 결과만 검증한다.

Spike 실행 조건 (모두 충족):
1. 당일 데이터 갱신 배치 status = success (write_batch_state 결과)
2. artifact.summary.evidence_as_of == 배치 결과 price_data_as_of
3. artifact_generated_at 이 현재 36시간 이내
4. 현재일 - price_data_as_of <= 7 달력일 (장기 stale 최종 안전 상한)
5. 공용 validate_artifact 통과 (Published 계약)

하나라도 실패 → ok=False → Runner failed · Telegram 미발송 · registry 미기록.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SpikeFreshnessResult:
    ok: bool
    reason: str = ""
    price_data_as_of: Optional[str] = None
    artifact_generated_at: Optional[str] = None


def check_spike_freshness(
    artifact: Any,
    *,
    runtime_date_kst: str,
) -> SpikeFreshnessResult:
    """Spike artifact 의 Published 계약 + freshness 를 검증 (C 확정 계약).

    외부 거래일 조회 없음. 당일 배치 상태(read_batch_state) + artifact 일치 +
    36h + 7달력일 상한만으로 판정.
    """
    from app.universe_bootstrap.artifact_validator import validate_artifact
    from app.three_push_runtime.market_data_batch import (
        evaluate_freshness,
        read_batch_state,
    )

    # (5) Published 계약.
    valid, reason, _meta = validate_artifact(artifact)
    if not valid:
        return SpikeFreshnessResult(ok=False, reason=f"artifact_invalid:{reason}")

    summary = artifact.get("summary") if isinstance(artifact, dict) else {}
    summary = summary or {}
    artifact_price_as_of = summary.get("evidence_as_of")
    artifact_generated_at = summary.get("artifact_generated_at")

    # (1) 당일 배치 성공.
    state = read_batch_state()
    if state is None:
        return SpikeFreshnessResult(ok=False, reason="batch_state_missing")
    if state.get("status") != "success":
        return SpikeFreshnessResult(
            ok=False,
            reason=f"batch_not_success:{state.get('status')}",
        )
    if state.get("refresh_date_kst") != runtime_date_kst:
        # 당일 배치가 아니면 stale (전일 배치 결과로 Spike 발송 금지).
        return SpikeFreshnessResult(
            ok=False,
            reason=(
                "batch_not_today:"
                f"{state.get('refresh_date_kst')}!={runtime_date_kst}"
            ),
        )

    # (2) artifact.price_data_as_of == 배치 결과 price_data_as_of.
    batch_price_as_of = state.get("price_data_as_of")
    if artifact_price_as_of != batch_price_as_of:
        return SpikeFreshnessResult(
            ok=False,
            reason=(
                "price_as_of_mismatch:"
                f"artifact={artifact_price_as_of}!=batch={batch_price_as_of}"
            ),
            price_data_as_of=artifact_price_as_of,
            artifact_generated_at=artifact_generated_at,
        )

    # (3)(4) 36h + 7달력일.
    verdict = evaluate_freshness(
        price_data_as_of=artifact_price_as_of,
        artifact_generated_at=artifact_generated_at,
        current_date=runtime_date_kst,
    )
    return SpikeFreshnessResult(
        ok=verdict.ok,
        reason=verdict.reason,
        price_data_as_of=verdict.price_data_as_of,
        artifact_generated_at=verdict.artifact_generated_at,
    )
