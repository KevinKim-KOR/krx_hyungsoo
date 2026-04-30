"""POC2 Step 1 + Step 2C — holdings 단일 SSOT 저장소.

설계자 결정 (Step 1):
- 저장 위치: state/holdings/holdings_latest.json (단일 파일)
- 입력 필드: ticker(필수), quantity(필수), avg_buy_price(필수), name(선택)
- 종목명 미입력 시 ticker 로 표시
- 히스토리/스냅샷 / Naver 자동조회 / 현재가 / 평가손익 등은 BACKLOG
- DB 도입 / in-memory 단독 / frontend localStorage 단독 보관 금지

설계자 결정 (Step 2C):
- account_group(표시/그룹용 라벨) 필드 추가. 계좌번호/세금/증권사 판정값 아님.
- 기본값/정규화 단일 helper 진입점: normalize_account_group()
  · trim
  · 빈 값 → "일반"
  · 30자 초과 → HoldingsValidationError
  · 기본 추천값(일반/ISA/연금/오픈뱅킹/기타) 대소문자 혼용 정규화
  · 사용자 커스텀 라벨은 trim 외에는 의미 변경 금지
- 저장/로드/draft 생성 모든 경로에서 동일 helper 를 거친다 (백엔드가 최종 방어선).
- 기존 holdings_latest.json 항목에 account_group 이 없어도 로드 단계에서
  "일반" 으로 정규화 후 통과 (하위 호환성). 파일 자체 마이그레이션은 다음 저장 시 자연 발생.
- 동일 ticker 중복 차단 정책 완화: (ticker, account_group, avg_buy_price) 삼중조합
  중복만 차단. 같은 종목을 같은 계좌·평단에 두 번 적는 것은 의미 없으나, 같은 종목을
  분할 매수해 평단이 다른 행으로 두는 사용자 흐름은 허용 (Step 2C 지시문).

검증 실패는 ValidationError 로 raise — run 생성 전에 차단되어야 한다
(POC2 Step1 지시문 E항: 입력 검증 실패로 FAILED run 만들지 마라).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

HOLDINGS_DIR = Path("state/holdings")
HOLDINGS_FILE = HOLDINGS_DIR / "holdings_latest.json"

# Step 2C: account_group 정책 상수.
ACCOUNT_GROUP_DEFAULT = "일반"
ACCOUNT_GROUP_MAX_LEN = 30
# 기본 추천값. 대소문자 혼용 / 공백 정규화 대상.
# 한국어 기본값은 사용자 입력 표준 표기.
_DEFAULT_RECOMMENDED_GROUPS: tuple[str, ...] = (
    "일반",
    "ISA",
    "연금",
    "오픈뱅킹",
    "기타",
)
# 비교용 lower 맵: lower(원본) → 표준 표기. 한국어는 lower 영향 없음.
_DEFAULT_RECOMMENDED_LOOKUP: dict[str, str] = {
    g.lower(): g for g in _DEFAULT_RECOMMENDED_GROUPS
}


class HoldingsValidationError(ValueError):
    """holdings 입력 검증 실패. run 생성 전 차단용."""


def normalize_account_group(value: Any) -> str:
    """account_group 단일 정규화 진입점.

    - None / "" / 공백만 → ACCOUNT_GROUP_DEFAULT ("일반")
    - 문자열이 아니면 HoldingsValidationError
    - trim 후 30자 초과면 HoldingsValidationError (조용히 자르지 않는다)
    - 기본 추천값(일반/ISA/연금/오픈뱅킹/기타) 의 대소문자 혼용은 표준 표기로 정규화
    - 그 외 사용자 커스텀 라벨은 trim 만 적용 (예: "Kiwoom-ISA" → "Kiwoom-ISA")
    """
    if value is None:
        return ACCOUNT_GROUP_DEFAULT
    if not isinstance(value, str):
        raise HoldingsValidationError(
            f"account_group 은 문자열이어야 합니다 (received: {type(value).__name__})"
        )
    stripped = value.strip()
    if not stripped:
        return ACCOUNT_GROUP_DEFAULT
    if len(stripped) > ACCOUNT_GROUP_MAX_LEN:
        raise HoldingsValidationError(
            f"account_group 은 {ACCOUNT_GROUP_MAX_LEN}자 이하여야 합니다 "
            f"(입력 길이: {len(stripped)})"
        )
    canonical = _DEFAULT_RECOMMENDED_LOOKUP.get(stripped.lower())
    if canonical is not None:
        return canonical
    return stripped


@dataclass
class Holding:
    ticker: str
    quantity: float
    avg_buy_price: float
    name: Optional[str] = None
    account_group: str = field(default=ACCOUNT_GROUP_DEFAULT)

    def display_name(self) -> str:
        return self.name if self.name else self.ticker

    def invested_amount(self) -> float:
        return float(self.quantity) * float(self.avg_buy_price)


def _coerce_holding(raw: Any, idx: int) -> Holding:
    """단일 holding dict 1건을 Holding 으로 변환 + 검증.

    필수 키 누락 / 빈 문자열 / 숫자 음수 등은 HoldingsValidationError.
    account_group 은 누락/빈 값이면 "일반" 으로 정규화. 30자 초과는 차단.
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

    # Step 2C: account_group 정규화. 누락 키는 None 으로 처리되어 "일반" 으로 귀결.
    try:
        account_group = normalize_account_group(raw.get("account_group"))
    except HoldingsValidationError as e:
        raise HoldingsValidationError(f"holdings[{idx}].account_group: {e}")

    return Holding(
        ticker=ticker,
        quantity=quantity,
        avg_buy_price=avg_buy_price,
        name=name,
        account_group=account_group,
    )


def validate_holdings(raw_list: Any) -> list[Holding]:
    """입력값을 검증하고 Holding 리스트로 변환. 실패 시 HoldingsValidationError.

    Step 2C 중복 정책:
    동일 (ticker, account_group, avg_buy_price) 삼중조합만 중복 차단한다.
    같은 종목을 분할 매수해 평단이 다른 행은 허용. 같은 계좌·같은 평단 중복은 의미 없음.
    """
    if not isinstance(raw_list, list):
        raise HoldingsValidationError("holdings 페이로드는 리스트여야 합니다.")
    if len(raw_list) == 0:
        raise HoldingsValidationError(
            "holdings 가 비어 있습니다. 1개 이상의 보유 종목이 필요합니다."
        )
    seen: set[tuple[str, str, float]] = set()
    holdings: list[Holding] = []
    for idx, raw in enumerate(raw_list):
        h = _coerce_holding(raw, idx)
        key = (h.ticker, h.account_group, float(h.avg_buy_price))
        if key in seen:
            raise HoldingsValidationError(
                f"holdings[{idx}] 중복 — 동일 (ticker, account_group, avg_buy_price): "
                f"{h.ticker!r}/{h.account_group!r}/{h.avg_buy_price}"
            )
        seen.add(key)
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

    Step 2C: 기존 holdings_latest.json 항목에 account_group 이 없을 수 있다.
    누락 항목은 _coerce_holding 단계에서 ACCOUNT_GROUP_DEFAULT 로 정규화된다.
    파일 자체는 다음 save() 시점에 자연 마이그레이션되며, 강제 재작성은 하지 않는다.
    """
    if not HOLDINGS_FILE.exists():
        return []
    data = json.loads(HOLDINGS_FILE.read_text(encoding="utf-8"))
    raw_list = data.get("holdings")
    if raw_list is None:
        raise HoldingsValidationError(
            f"{HOLDINGS_FILE} 의 'holdings' 키가 누락됐습니다."
        )
    return validate_holdings(raw_list)
