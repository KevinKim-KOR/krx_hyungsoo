"""POC2 Step 5B — Momentum Engine holdings mode (placeholder 산식).

설계자 결정 (Step 5B 지시문):
- placeholder 산식: score_value = pnl_rate (현재 평가수익률 기준).
- 이 값은 최종 모멘텀 산식이 아니다. 투자 판단 정책이 아니다. BUY/SELL/리밸런싱 금지.
- 외부 API / 신규 의존성 0. holdings_enrich 결과만 사용.
- mode = "holdings" 고정. universe mode 미구현.
- candidates 의 holdings mode row 매핑 필수: source_index + ticker + account_group +
  avg_buy_price (Step 2C / Step 3 정책 동일 — holding_id 신규 도입 금지).
- 계산 불가는 run 실패가 아니라 is_available=false / score_result.is_scored=false +
  exclusion_reason / fallback_text 로 처리.
- rank 는 optional. score_result.is_scored=true + score_value + ranking_basis 가 모두
  있고 비교 가능한 후보가 2개 이상일 때만 부여. Telegram Top N / 매수 우선순위 아님.

이 모듈은 순수 함수 1개 (build_holdings_momentum_result) 만 외부에 노출한다.
EnrichedHolding 리스트와 asof / run_id 를 입력받아 momentum_result dict 를 반환한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.holdings_enrich import EnrichedHolding

ENGINE_ID = "momentum_engine_placeholder_v1"
ENGINE_VERSION = "0.1.0"
MODE_HOLDINGS = "holdings"
RANKING_BASIS_PNL_RATE = "pnl_rate"

# Step 7B (2026-05-12) — 사용자 노출 텍스트에서 "placeholder" 단어 제거.
# 내부 식별자 (engine_id="momentum_engine_placeholder_v1", PLACEHOLDER_SCORE_BASIS_TEXT
# 상수 키, ENGINE_VERSION 등) 는 호환 / 데이터 계약 유지 위해 변경하지 않는다.
# score_basis_text 는 candidate.score_result 필드로 들어가지만 사용자 노출 message_text
# / Telegram 에는 노출되지 않음 (Step5B/Step6 설계). 안전 차원에서 사용자 친화 표현으로 보강.
PLACEHOLDER_SCORE_BASIS_TEXT = "현재 보유 종목 점검 기준 (평가수익률)"
FALLBACK_TEXT = "데이터 부족으로 보유 종목 점검 제외"

CANDIDATE_REASON_AVAILABLE = (
    "현재 평가수익률 기준 보유 종목 점검값이 계산되었습니다. "
    "이 값은 최종 투자 판단 산식이 아닙니다."
)
EXCLUSION_REASON_NO_PNL = "pnl_rate 없음 또는 평가 계산 불가"


def _is_candidate_scorable(item: EnrichedHolding) -> bool:
    """placeholder 산식(pnl_rate) 으로 점수 부여 가능한지.

    pnl_rate 는 holdings_enrich 가 평가 계산 가능 row 에서만 채운다 (Step 2B 정책).
    따라서 pnl_rate 가 None / NaN / 비유효 양수/음수 외 값이면 점수 불가.
    """
    if item.price_missing or item.calc_missing:
        return False
    if item.pnl_rate_pct is None:
        return False
    try:
        v = float(item.pnl_rate_pct)
    except (TypeError, ValueError):
        return False
    if v != v:  # NaN
        return False
    return True


def _label(item: EnrichedHolding) -> str:
    """판단 사유 문장에 쓰일 종목 라벨. 종목명 우선, 없으면 ticker."""
    name = (item.name or "").strip()
    if name and name != item.ticker:
        return name
    return item.ticker


def _candidate_id(item: EnrichedHolding) -> str:
    """row 매핑용 결정론적 id. source_index + ticker + account_group + avg_buy_price.

    holding_id 신규 도입 금지. 동일 ticker 가 여러 account_group / 여러 avg_buy_price
    row 로 존재할 수 있으므로 4 요소를 모두 포함한다.
    """
    return (
        f"{item.source_index}|{item.ticker}"
        f"|{item.account_group}|{item.avg_buy_price}"
    )


def _build_candidate_scored(
    item: EnrichedHolding,
    rank: Optional[int],
) -> dict[str, Any]:
    score_value = round(float(item.pnl_rate_pct), 2)  # type: ignore[arg-type]
    out: dict[str, Any] = {
        "candidate_id": _candidate_id(item),
        "ticker": item.ticker,
        "name": item.name or item.ticker,
        "mode": MODE_HOLDINGS,
        "is_available": True,
        "score_result": {
            "is_scored": True,
            "score_value": score_value,
            "score_unit": "%",
            "score_basis_text": PLACEHOLDER_SCORE_BASIS_TEXT,
            "ranking_basis": RANKING_BASIS_PNL_RATE,
        },
        "reason_text": CANDIDATE_REASON_AVAILABLE,
        "input_basis": {"pnl_rate_pct": score_value},
        "source_index": item.source_index,
        "account_group": item.account_group,
        "avg_buy_price": float(item.avg_buy_price),
    }
    if rank is not None:
        out["rank"] = rank
    return out


def _build_candidate_excluded(item: EnrichedHolding) -> dict[str, Any]:
    return {
        "candidate_id": _candidate_id(item),
        "ticker": item.ticker,
        "name": item.name or item.ticker,
        "mode": MODE_HOLDINGS,
        "is_available": False,
        "score_result": {
            "is_scored": False,
            "score_basis_text": FALLBACK_TEXT,
        },
        "reason_text": FALLBACK_TEXT,
        "input_basis": {},
        "exclusion_reason": EXCLUSION_REASON_NO_PNL,
        "source_index": item.source_index,
        "account_group": item.account_group,
        "avg_buy_price": float(item.avg_buy_price),
    }


def _build_summary(
    total: int,
    scored: list[dict[str, Any]],
    excluded_count: int,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "total_candidates": total,
        "scored_candidates": len(scored),
        "excluded_candidates": excluded_count,
    }
    if not scored:
        summary["summary_reason_text"] = FALLBACK_TEXT
        return summary

    # 현재 보유 종목 점검 기준 상위 후보 1개 — Telegram Top N 정책이 아님 (rank 1위 단건만).
    top = max(scored, key=lambda c: c["score_result"]["score_value"])
    top_label = top["name"] or top["ticker"]
    # Step 7B (2026-05-12): 사용자 노출 message_text 에서 "placeholder" 단어 제거.
    summary["summary_reason_text"] = (
        f"현재 보유 종목 점검 기준으로 평가 가능한 보유 종목 {len(scored)}개를 "
        "점검했습니다. 이 값은 최종 투자 판단 산식이 아닙니다."
    )
    summary["top_candidate"] = {
        "candidate_id": top["candidate_id"],
        "ticker": top["ticker"],
        "name": top["name"],
        "source_index": top["source_index"],
        "account_group": top["account_group"],
        "avg_buy_price": top["avg_buy_price"],
        "score_value": top["score_result"]["score_value"],
        "reason_text": (
            f"현재 보유 종목 점검 기준으로 평가 가능한 보유 종목 중 {top_label}의 "
            "점검값이 가장 높습니다. 이 값은 최종 투자 판단 산식이 아닙니다."
        ),
    }
    return summary


def build_holdings_momentum_result(
    enriched: list[EnrichedHolding],
    asof: Optional[str] = None,
    run_context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """holdings mode momentum_result 빌드.

    반환 규약 (Step5A 계약 + Step5B 한정):
    - engine_id / engine_version / mode / asof / summary / candidates 6 키
    - candidates[] 의 holdings mode 항목은 source_index / ticker / account_group /
      avg_buy_price 4 키를 모두 포함 (row 매핑 깨짐 방지)
    - rank 는 score 가능 후보가 2개 이상일 때만 부여. 1개일 때는 비교 대상이 없으므로 생략.
    - 계산 불가 후보는 is_available=false + score_result.is_scored=false +
      exclusion_reason. run 실패 처리하지 않는다.
    - run_context 는 Step5A 계약상 자리만 있는 metadata. 본 Step 에서는 받기만 하고 결과에
      별도로 직렬화하지 않는다 (asof / engine_id / engine_version 가 그 역할).
    """
    _ = run_context  # 인자 자리는 받되 본 Step 에서는 별도 직렬화 안 함.
    asof_iso = asof or datetime.now(timezone.utc).isoformat()

    scorable = [item for item in enriched if _is_candidate_scorable(item)]
    excluded = [item for item in enriched if not _is_candidate_scorable(item)]

    # rank 부여 정책: 비교 가능한 후보 2개 이상일 때만.
    # 동률 시 source_index 작은 쪽 우선 (Step3 와 동일 결정론적 정렬).
    scored_dicts: list[dict[str, Any]]
    if len(scorable) >= 2:
        ordered = sorted(
            scorable,
            key=lambda x: (-float(x.pnl_rate_pct), x.source_index),  # type: ignore[arg-type]
        )
        scored_dicts = [
            _build_candidate_scored(item, rank=idx + 1)
            for idx, item in enumerate(ordered)
        ]
    elif len(scorable) == 1:
        scored_dicts = [_build_candidate_scored(scorable[0], rank=None)]
    else:
        scored_dicts = []

    # 제외 후보는 holdings 입력 순서 유지.
    excluded_dicts = [_build_candidate_excluded(item) for item in excluded]

    # 최종 candidates 는 입력 holdings 순서를 따라 합치되, scored 결과는 위에서
    # 부여한 rank 정보를 보존해야 하므로 dict 를 source_index 키로 인덱싱 후 재배열.
    by_source_index: dict[int, dict[str, Any]] = {}
    for c in scored_dicts:
        by_source_index[int(c["source_index"])] = c
    for c in excluded_dicts:
        by_source_index[int(c["source_index"])] = c
    candidates_in_order: list[dict[str, Any]] = [
        by_source_index[item.source_index] for item in enriched
    ]

    summary = _build_summary(
        total=len(enriched),
        scored=scored_dicts,
        excluded_count=len(excluded_dicts),
    )

    return {
        "engine_id": ENGINE_ID,
        "engine_version": ENGINE_VERSION,
        "mode": MODE_HOLDINGS,
        "asof": asof_iso,
        "summary": summary,
        "candidates": candidates_in_order,
    }
