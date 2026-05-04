"""POC2 Step 3 — 첫 factor: portfolio_concentration_v1.

내부 식별자: ``portfolio_concentration_v1``
사용자 표시명: ``보유 비중 영향``

설계자 결정 (Step 3 지시문 §4·§5·§6):
- 외부 API / 신규 의존성 없음. holdings_enrich.enrich_holdings 결과만 사용.
- "평가 계산 가능" row 만 분모/분자에 사용 (Step 2B 의 _is_calc_available 정책 재사용).
- factor_signals 생성 범위: portfolio scope 1개 + max_weight_row 의 holding_row scope 0~1개.
  · 모든 row 에 대해 factor_signal 을 만들지 않는다 (Telegram 요약형 정책 + 기본 노출
    영역 단순성 보장).
- threshold / 위험 등급 / WATCH·REVIEW·BUY·SELL 라벨 일체 도입 금지.
- row 매핑은 (source_index, ticker, account_group, avg_buy_price) 4 요소를 그대로 보존.
  holding_id 신규 도입 금지.
- 계산 불가는 run 실패가 아니다. is_available=False + fallback_text 로 처리.

이 모듈은 순수 함수 1개(build_factor_signals)만 외부에 노출한다. 외부 호출자는
EnrichedHolding 리스트를 그대로 넘기고, 결과 dict 리스트를 받아 draft_payload 에
실으면 된다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.holdings_enrich import EnrichedHolding

FACTOR_ID = "portfolio_concentration_v1"
FACTOR_DISPLAY_NAME = "보유 비중 영향"
UNIT_PCT = "%"

FALLBACK_TEXT = "데이터 부족으로 factor 판단 제외"


def _is_calc_available(item: EnrichedHolding) -> bool:
    """Step 2B 정책 재사용 — 시세 확인 + 평가금액·매입금액 모두 유효 양수일 때만.

    holdings_enrich 가 채워둔 calc_missing/price_missing flag 를 그대로 활용한다.
    """
    if item.price_missing or item.calc_missing:
        return False
    if item.eval_amount is None or item.eval_amount <= 0:
        return False
    if item.invested_amount is None or item.invested_amount <= 0:
        return False
    return True


def _label(item: EnrichedHolding) -> str:
    """판단 사유 문장에 쓰일 종목 라벨. 종목명 우선, 없으면 ticker."""
    name = (item.name or "").strip()
    if name and name != item.ticker:
        return name
    return item.ticker


def _portfolio_signal_unavailable(computed_at: str, reason: str) -> dict[str, Any]:
    """계산 불가 시 portfolio scope signal."""
    return {
        "factor_id": FACTOR_ID,
        "factor_name": FACTOR_DISPLAY_NAME,
        "scope": "portfolio",
        "is_available": False,
        "value": None,
        "unit": UNIT_PCT,
        "reason_text": None,
        "fallback_text": FALLBACK_TEXT,
        "input_basis": {"reason": reason},
        "computed_at": computed_at,
    }


def build_factor_signals(
    enriched: list[EnrichedHolding],
) -> list[dict[str, Any]]:
    """portfolio_concentration_v1 factor_signals 빌드.

    반환 규약:
    - 항상 portfolio scope signal 1개를 첫 항목으로 포함한다.
    - 평가 계산 가능 row 가 1+ 일 때 그중 비중이 가장 큰 row 1개에 대해서만
      holding_row scope signal 을 추가한다. 그 외 row 에 대한 signal 은 생성하지 않는다.
    - 모든 dict 는 이번 단계 contract 인 (factor_id / factor_name / scope /
      is_available / value / unit / reason_text / fallback_text / input_basis /
      computed_at) 키를 가진다. holding_row scope 는 추가로 source_index, ticker,
      account_group, avg_buy_price 4 키를 포함한다.
    - 계산 불가 시에도 portfolio signal 1개는 항상 반환한다 (fallback_text 포함).
    - undefined / null / NaN / 0 대체값을 노출하지 않는다 (계산 불가 = is_available
      False + fallback_text + value=None).
    """
    computed_at = datetime.now(timezone.utc).isoformat()

    if not enriched:
        return [_portfolio_signal_unavailable(computed_at, "no_holdings")]

    calc_rows = [item for item in enriched if _is_calc_available(item)]
    if not calc_rows:
        return [_portfolio_signal_unavailable(computed_at, "no_calc_available_rows")]

    total_market_value = sum(
        float(item.eval_amount) for item in calc_rows  # type: ignore[arg-type]
    )
    if total_market_value <= 0:
        return [
            _portfolio_signal_unavailable(
                computed_at, "portfolio_total_market_value_not_positive"
            )
        ]

    # max_weight_row 1개 선택. 동률 시 holdings 입력 순서(즉 source_index 작은 쪽) 를
    # 우선한다 — 정렬 안정성.
    weighted: list[tuple[EnrichedHolding, float]] = []
    for item in calc_rows:
        ev = float(item.eval_amount)  # type: ignore[arg-type]
        weight_pct = ev / total_market_value * 100.0
        weighted.append((item, weight_pct))
    weighted.sort(key=lambda x: (-x[1], x[0].source_index))
    max_item, max_weight = weighted[0]

    excluded_count = len(enriched) - len(calc_rows)
    label = _label(max_item)

    portfolio_reason = (
        f"평가 계산 가능 보유분 중 {label}의 비중이 가장 큽니다. "
        "현재 초안은 이 종목의 가격 변동 영향을 상대적으로 크게 받습니다."
    )

    portfolio_signal: dict[str, Any] = {
        "factor_id": FACTOR_ID,
        "factor_name": FACTOR_DISPLAY_NAME,
        "scope": "portfolio",
        "is_available": True,
        "value": round(max_weight, 2),
        "unit": UNIT_PCT,
        "reason_text": portfolio_reason,
        "fallback_text": None,
        "input_basis": {
            "calc_available_count": len(calc_rows),
            "excluded_count": excluded_count,
            "portfolio_total_market_value": round(total_market_value, 2),
            "max_weight_source_index": max_item.source_index,
            "max_weight_ticker": max_item.ticker,
            "max_weight_account_group": max_item.account_group,
            "max_weight_avg_buy_price": float(max_item.avg_buy_price),
        },
        "computed_at": computed_at,
    }

    holding_row_reason = "이 종목은 평가 계산 가능 보유분 중 비중이 가장 큰 항목입니다."
    holding_row_signal: dict[str, Any] = {
        "factor_id": FACTOR_ID,
        "factor_name": FACTOR_DISPLAY_NAME,
        "scope": "holding_row",
        "source_index": max_item.source_index,
        "ticker": max_item.ticker,
        "account_group": max_item.account_group,
        "avg_buy_price": float(max_item.avg_buy_price),
        "is_available": True,
        "value": round(max_weight, 2),
        "unit": UNIT_PCT,
        "reason_text": holding_row_reason,
        "fallback_text": None,
        "input_basis": {
            "row_market_value": round(float(max_item.eval_amount), 2),  # type: ignore[arg-type]
            "portfolio_total_market_value": round(total_market_value, 2),
        },
        "computed_at": computed_at,
    }

    return [portfolio_signal, holding_row_signal]


def find_portfolio_signal(
    factor_signals: Optional[list[dict[str, Any]]],
) -> Optional[dict[str, Any]]:
    """factor_signals 에서 portfolio scope signal 1개를 찾는다 (없으면 None).

    Step3 정책상 항상 1개이지만, 과거 run 호환성을 위해 None 도 허용.
    """
    if not factor_signals:
        return None
    for sig in factor_signals:
        if isinstance(sig, dict) and sig.get("scope") == "portfolio":
            return sig
    return None
