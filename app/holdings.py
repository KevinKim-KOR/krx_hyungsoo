"""POC2 Step 1 — holdings 단일 SSOT 저장소.

설계자 결정:
- 저장 위치: state/holdings/holdings_latest.json (단일 파일)
- 이번 단계 입력 필드: ticker(필수), quantity(필수), avg_buy_price(필수), name(선택)
- 종목명 미입력 시 ticker 로 표시
- 히스토리/스냅샷 / Naver 자동조회 / 현재가 / 평가손익 등은 BACKLOG
- DB 도입 / in-memory 단독 / frontend localStorage 단독 보관 금지

검증 실패는 ValidationError 로 raise — run 생성 전에 차단되어야 한다
(POC2 Step1 지시문 E항: 입력 검증 실패로 FAILED run 만들지 마라).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

HOLDINGS_DIR = Path("state/holdings")
HOLDINGS_FILE = HOLDINGS_DIR / "holdings_latest.json"


class HoldingsValidationError(ValueError):
    """holdings 입력 검증 실패. run 생성 전 차단용."""


@dataclass
class Holding:
    ticker: str
    quantity: float
    avg_buy_price: float
    name: Optional[str] = None

    def display_name(self) -> str:
        return self.name if self.name else self.ticker

    def invested_amount(self) -> float:
        return float(self.quantity) * float(self.avg_buy_price)


def _coerce_holding(raw: Any, idx: int) -> Holding:
    """단일 holding dict 1건을 Holding 으로 변환 + 검증.

    필수 키 누락 / 빈 문자열 / 숫자 음수 등은 HoldingsValidationError.
    """
    if not isinstance(raw, dict):
        raise HoldingsValidationError(
            f"holdings[{idx}] 는 객체여야 합니다 (received: {type(raw).__name__})"
        )

    ticker = raw.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        raise HoldingsValidationError(
            f"holdings[{idx}].ticker 가 비어있거나 문자열이 아닙니다."
        )
    ticker = ticker.strip()

    if "quantity" not in raw:
        raise HoldingsValidationError(f"holdings[{idx}].quantity 가 누락됐습니다.")
    if "avg_buy_price" not in raw:
        raise HoldingsValidationError(f"holdings[{idx}].avg_buy_price 가 누락됐습니다.")

    try:
        quantity = float(raw["quantity"])
    except (TypeError, ValueError):
        raise HoldingsValidationError(
            f"holdings[{idx}].quantity 가 숫자가 아닙니다 (received: {raw['quantity']!r})"
        )
    if quantity <= 0:
        raise HoldingsValidationError(
            f"holdings[{idx}].quantity 는 0 보다 커야 합니다 (received: {quantity})"
        )

    try:
        avg_buy_price = float(raw["avg_buy_price"])
    except (TypeError, ValueError):
        raise HoldingsValidationError(
            f"holdings[{idx}].avg_buy_price 가 숫자가 아닙니다 "
            f"(received: {raw['avg_buy_price']!r})"
        )
    if avg_buy_price <= 0:
        raise HoldingsValidationError(
            f"holdings[{idx}].avg_buy_price 는 0 보다 커야 합니다 (received: {avg_buy_price})"
        )

    name_raw = raw.get("name")
    name: Optional[str] = None
    if name_raw is not None:
        if not isinstance(name_raw, str):
            raise HoldingsValidationError(
                f"holdings[{idx}].name 은 문자열이거나 생략되어야 합니다."
            )
        stripped = name_raw.strip()
        name = stripped if stripped else None

    return Holding(
        ticker=ticker,
        quantity=quantity,
        avg_buy_price=avg_buy_price,
        name=name,
    )


def validate_holdings(raw_list: Any) -> list[Holding]:
    """입력값을 검증하고 Holding 리스트로 변환. 실패 시 HoldingsValidationError."""
    if not isinstance(raw_list, list):
        raise HoldingsValidationError("holdings 페이로드는 리스트여야 합니다.")
    if len(raw_list) == 0:
        raise HoldingsValidationError(
            "holdings 가 비어 있습니다. 1개 이상의 보유 종목이 필요합니다."
        )
    # ticker 중복은 동일 종목 분할 입력 의도일 수도 있으나, 이번 단계 단순성 위해 차단.
    seen: set[str] = set()
    holdings: list[Holding] = []
    for idx, raw in enumerate(raw_list):
        h = _coerce_holding(raw, idx)
        if h.ticker in seen:
            raise HoldingsValidationError(
                f"holdings[{idx}].ticker={h.ticker!r} 가 중복되었습니다."
            )
        seen.add(h.ticker)
        holdings.append(h)
    return holdings


def save(holdings: list[Holding]) -> None:
    """검증된 holdings 를 단일 SSOT 파일로 저장."""
    HOLDINGS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"holdings": [asdict(h) for h in holdings]}
    HOLDINGS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load() -> list[Holding]:
    """저장된 holdings 조회. 파일 없으면 빈 리스트.

    저장된 파일이 손상된 경우(JSON 파싱 실패 등) 도 빈 리스트로 처리하지
    않고 즉시 raise — 사용자가 인지하고 복구하도록 한다.
    """
    if not HOLDINGS_FILE.exists():
        return []
    data = json.loads(HOLDINGS_FILE.read_text(encoding="utf-8"))
    raw_list = data.get("holdings")
    if raw_list is None:
        raise HoldingsValidationError(
            f"{HOLDINGS_FILE} 의 'holdings' 키가 누락됐습니다."
        )
    # 저장된 데이터도 동일 검증 통과해야 한다 (계약 일관성).
    return validate_holdings(raw_list)
