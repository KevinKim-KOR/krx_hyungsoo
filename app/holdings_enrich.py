"""POC2 Step 2 — holdings × market_cache 결합 + 평가/손익/비중 계산.

설계자 결정:
- 시장데이터 fetch 는 절대 트리거하지 않는다. (호출자가 market_cache.get_all 등으로
  미리 dict 를 만들어 넘긴다.) 이 모듈은 순수 결합/계산 책임만.
- eval_amount / pnl_amount / pnl_rate_pct 계산은 quantity + avg_buy_price +
  current_price 가 모두 숫자(>0) 일 때만 수행한다.
- invested_amount / buy_weight_pct 는 시세 없어도 계산 가능 (POC2 Step 1 호환).
- market_weight_pct 는 해당 종목의 eval_amount 존재 + 전체 합계 > 0 일 때만.
- 계산 불가 항목은 None 으로 두고 price_missing / calc_missing flag 로 명시.
- undefined / NaN 은 절대 만들지 않는다 (UI/Telegram 표시 계층이 None 만 보면 됨).
- holdings 의 name 이 비어있으면 market_quote.name 으로 폴백 (사용자 입력 우선).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.holdings import Holding
from app.market_cache import MarketQuote


@dataclass
class EnrichedHolding:
    """holdings + 시세 결합 결과 단건.

    None 은 "값이 없음" 을 의미한다 (UI/메시지 렌더러가 줄 자체를 생략).
    NaN / 음수 / 0 은 만들지 않는다.
    """

    ticker: str
    name: Optional[str]
    quantity: float
    avg_buy_price: float
    invested_amount: float

    current_price: Optional[float]
    price_asof: Optional[str]
    price_source: Optional[str]

    eval_amount: Optional[float]
    pnl_amount: Optional[float]
    pnl_rate_pct: Optional[float]

    buy_weight_pct: Optional[float]
    market_weight_pct: Optional[float]

    price_missing: bool
    calc_missing: bool


def _is_valid_price(value: object) -> bool:
    """시세 값으로 사용 가능한 양수 숫자인지."""
    if not isinstance(value, (int, float)):
        return False
    if isinstance(value, bool):
        # bool 은 isinstance(int) True 라 별도 차단.
        return False
    return value > 0


def _resolve_name(holding: Holding, quote: Optional[MarketQuote]) -> Optional[str]:
    """name 우선순위: 사용자 입력 > 시세 응답 > None."""
    if holding.name and holding.name.strip():
        return holding.name.strip()
    if quote is not None and isinstance(quote.name, str) and quote.name.strip():
        return quote.name.strip()
    return None


def enrich_holdings(
    holdings: list[Holding],
    market_quotes: dict[str, MarketQuote],
) -> list[EnrichedHolding]:
    """holdings 와 시세 dict 를 결합한 EnrichedHolding 리스트 반환.

    - market_quotes 키는 ticker (str). 누락된 종목은 시세 없이 처리 (price_missing=True).
    - 호출자는 market_cache.get_all() 결과 또는 그 부분집합을 그대로 넘기면 된다.
    - 이 함수는 외부 호출/네트워크/디스크 I/O 를 일으키지 않는다.
    """
    # 1차: 단건 결합 + 단건 계산 (eval_amount 까지)
    eval_amounts: list[Optional[float]] = []
    invested_total = 0.0

    rows: list[dict[str, object]] = []
    for h in holdings:
        invested = float(h.quantity) * float(h.avg_buy_price)
        invested_total += invested

        quote = market_quotes.get(h.ticker)
        current_price: Optional[float] = None
        price_asof: Optional[str] = None
        price_source: Optional[str] = None
        if quote is not None and _is_valid_price(quote.current_price):
            current_price = float(quote.current_price)  # type: ignore[arg-type]
            price_asof = quote.price_asof
            price_source = quote.price_source

        if current_price is not None:
            eval_amount: Optional[float] = float(h.quantity) * current_price
            pnl_amount: Optional[float] = eval_amount - invested
            pnl_rate_pct: Optional[float] = (
                (pnl_amount / invested * 100.0) if invested > 0 else None
            )
            calc_missing = False
        else:
            eval_amount = None
            pnl_amount = None
            pnl_rate_pct = None
            calc_missing = True

        eval_amounts.append(eval_amount)
        rows.append(
            {
                "holding": h,
                "quote": quote,
                "invested": invested,
                "current_price": current_price,
                "price_asof": price_asof,
                "price_source": price_source,
                "eval_amount": eval_amount,
                "pnl_amount": pnl_amount,
                "pnl_rate_pct": pnl_rate_pct,
                "calc_missing": calc_missing,
            }
        )

    # 2차: 비중 계산 (전체 합계 필요)
    eval_total = sum(v for v in eval_amounts if v is not None)

    enriched: list[EnrichedHolding] = []
    for row in rows:
        h: Holding = row["holding"]  # type: ignore[assignment]
        quote: Optional[MarketQuote] = row["quote"]  # type: ignore[assignment]
        invested: float = row["invested"]  # type: ignore[assignment]

        buy_weight_pct: Optional[float] = (
            round(invested / invested_total * 100.0, 2) if invested_total > 0 else None
        )

        eval_amount = row["eval_amount"]  # type: ignore[assignment]
        market_weight_pct: Optional[float] = None
        if eval_amount is not None and eval_total > 0:
            market_weight_pct = round(eval_amount / eval_total * 100.0, 2)

        # 반올림 정책: 금액 2자리, 비율 2자리. (UI/메시지에서 _format_money 가 추가 처리)
        eval_rounded: Optional[float] = (
            round(eval_amount, 2) if eval_amount is not None else None
        )
        pnl_rounded: Optional[float] = (
            round(row["pnl_amount"], 2) if row["pnl_amount"] is not None else None
        )
        pnl_rate_rounded: Optional[float] = (
            round(row["pnl_rate_pct"], 2) if row["pnl_rate_pct"] is not None else None
        )

        enriched.append(
            EnrichedHolding(
                ticker=h.ticker,
                name=_resolve_name(h, quote),
                quantity=float(h.quantity),
                avg_buy_price=float(h.avg_buy_price),
                invested_amount=round(invested, 2),
                current_price=row["current_price"],  # type: ignore[arg-type]
                price_asof=row["price_asof"],  # type: ignore[arg-type]
                price_source=row["price_source"],  # type: ignore[arg-type]
                eval_amount=eval_rounded,
                pnl_amount=pnl_rounded,
                pnl_rate_pct=pnl_rate_rounded,
                buy_weight_pct=buy_weight_pct,
                market_weight_pct=market_weight_pct,
                price_missing=(row["current_price"] is None),
                calc_missing=bool(row["calc_missing"]),
            )
        )

    return enriched


def to_recommendation_dict(item: EnrichedHolding) -> dict[str, object]:
    """EnrichedHolding → draft_payload.recommendations 항목용 dict.

    POC2 Step 1 의 8필드(ticker/name/quantity/avg_buy_price/invested_amount/
    buy_weight_pct/action/reason) 호환을 유지하면서 시세/평가 필드만 추가한다.

    - action 은 항상 'HOLD' (이번 단계 추천 로직 확장 금지 — 설계자 결정 유지).
    - None 인 필드는 키 자체를 생략 (raw JSON 노출 시에도 undefined 없음).
    - draft_payload 는 지시문 허용 필드(시세/평가/시장비중) 만 포함한다.
      누락 사유는 별도 flag 로 기록하지 않는다 — 표시 계층은 키 존재 여부로 판단.
      (price_missing/calc_missing 같은 메타 flag 는 enrichment API 응답 전용)
    """
    base: dict[str, object] = {
        "ticker": item.ticker,
        "name": item.name if item.name else item.ticker,
        "quantity": item.quantity,
        "avg_buy_price": item.avg_buy_price,
        "invested_amount": item.invested_amount,
        "action": "HOLD",
        "reason": "보유 종목 현황 (이번 단계는 추천 판단 없이 HOLD 고정)",
    }
    if item.buy_weight_pct is not None:
        base["buy_weight_pct"] = item.buy_weight_pct
    if item.current_price is not None:
        base["current_price"] = item.current_price
    if item.price_asof is not None:
        base["price_asof"] = item.price_asof
    if item.price_source is not None:
        base["price_source"] = item.price_source
    if item.eval_amount is not None:
        base["eval_amount"] = item.eval_amount
    if item.pnl_amount is not None:
        base["pnl_amount"] = item.pnl_amount
    if item.pnl_rate_pct is not None:
        base["pnl_rate_pct"] = item.pnl_rate_pct
    if item.market_weight_pct is not None:
        base["market_weight_pct"] = item.market_weight_pct
    return base
