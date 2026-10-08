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
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

HOLDINGS_DIR = Path("state/holdings")
HOLDINGS_FILE = HOLDINGS_DIR / "holdings_latest.json"

# POC3-08 (A): 종목코드 형식 검증. 국내 종목코드는 영숫자 6자(대문자).
#   예: "069500"(ETF), "0005G0"(영숫자 ETF), "005930"(개별주).
#   "111"·"dasdasd" 같은 오타/쓰레기 값은 이 형식 게이트에서 차단한다.
#   ETF 실존 여부(etf_master 존재)는 여기서 막지 않는다 — 개별주는 etf_master 에
#   없으므로 실존 게이트로 막으면 정상 개별주까지 차단됨(프론트에서 경고만).
TICKER_PATTERN = re.compile(r"^[0-9A-Z]{6}$")

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


def _coerce_holding(raw: Any, idx: int, *, strict_ticker: bool = False) -> Holding:
    """단일 holding dict 1건을 Holding 으로 변환 + 검증.

    필수 키 누락 / 빈 문자열 / 숫자 음수 등은 HoldingsValidationError.
    account_group 은 누락/빈 값이면 "일반" 으로 정규화. 30자 초과는 차단.

    strict_ticker (POC3-08 A): True 이면 ticker 가 영숫자 6자(TICKER_PATTERN)여야
      한다. 신규 저장(PUT /holdings) 경로에서만 True — "111"·"dasdasd" 같은 오타를
      저장 시점에 차단. 기본 False 는 기존 로드 경로 하위호환(이미 저장된 비정형
      값이 있어도 읽기는 막지 않음).
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

    if strict_ticker and not TICKER_PATTERN.match(ticker):
        raise HoldingsValidationError(
            f"holdings[{idx}].ticker 형식 오류 — 종목코드는 영숫자 6자리여야 합니다 "
            f"(received: {ticker!r})"
        )

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
    if not math.isfinite(quantity) or quantity <= 0:  # POC5-05: NaN · Infinity 거절
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
    if (
        not math.isfinite(avg_buy_price) or avg_buy_price <= 0
    ):  # POC5-05: NaN · Infinity 거절
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


def validate_holdings(
    raw_list: Any,
    *,
    strict_ticker: bool = False,
    allow_empty: bool = False,
    unique_triple: bool = True,
) -> list[Holding]:
    """입력값을 검증하고 Holding 리스트로 변환. 실패 시 HoldingsValidationError.

    Step 2C 중복 정책:
    동일 (ticker, account_group, avg_buy_price) 삼중조합만 중복 차단한다.
    같은 종목을 분할 매수해 평단이 다른 행은 허용. 같은 계좌·같은 평단 중복은 의미 없음.

    strict_ticker (POC3-08 A): 저장 경로에서만 True — ticker 형식(영숫자 6자) 강제.
    기본 False 는 기존 로드/재사용 경로 하위호환.

    POC5-05: allow_empty=True 는 '정상 빈 보유'(전량매도)를 허용한다 — 로더 · 적용
    payload 경로용. 입력 검증 기본값(빈 목록 거절)은 그대로다. unique_triple=False 는
    줄 ID 로 계산한 보유(평단이 우연히 같아진 두 줄)를 로더가 거절하지 않게 한다.
    """
    if not isinstance(raw_list, list):
        raise HoldingsValidationError("holdings 페이로드는 리스트여야 합니다.")
    if len(raw_list) == 0 and not allow_empty:
        raise HoldingsValidationError(
            "holdings 가 비어 있습니다. 1개 이상의 보유 종목이 필요합니다."
        )
    seen: set[tuple[str, str, float]] = set()
    holdings: list[Holding] = []
    for idx, raw in enumerate(raw_list):
        h = _coerce_holding(raw, idx, strict_ticker=strict_ticker)
        key = (h.ticker, h.account_group, float(h.avg_buy_price))
        if unique_triple and key in seen:
            raise HoldingsValidationError(
                f"holdings[{idx}] 중복 — 동일 (ticker, account_group, avg_buy_price): "
                f"{h.ticker!r}/{h.account_group!r}/{h.avg_buy_price}"
            )
        seen.add(key)
        holdings.append(h)
    return holdings


def serialize_payload(holdings: list[Holding]) -> bytes:
    """기존 형태 {"holdings": [허용 5필드]} 의 고정 직렬화(POC5-05 OCI 적용 payload).

    Holding 의 필드가 곧 허용 목록(ticker · quantity · avg_buy_price · name ·
    account_group)이라 개인 이력 · 줄 ID 가 들어갈 자리가 없다.
    """
    payload = {"holdings": [asdict(h) for h in holdings]}
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


_PLAIN_ROW_KEYS = frozenset(
    ("ticker", "quantity", "avg_buy_price", "name", "account_group")
)


def is_history_document(data: Any) -> bool:
    """POC5-05: 기존 형식(최상위 = holdings 하나 · 행 = 허용 5필드 이하)이 아니면 True.

    표지 키(schema_version · personal_trade_history)만 보지 않는다 — 키를 지운 이력 문서가
    기존 형식으로 통과해 판정을 건너뛰지 않게, 기존 형식이 아닌 dict 는 모두 이력 문서로 보고
    전체 판정(_check_history_consistency)을 거치게 한다. OCI payload 는 늘 기존 형식이다.
    """
    if not isinstance(data, dict):
        return False
    if set(data) != {"holdings"}:
        return True
    rows = data.get("holdings")
    return isinstance(rows, list) and any(
        isinstance(r, dict) and set(r) - _PLAIN_ROW_KEYS for r in rows
    )


_DOC_ROW_KEYS = (
    "ticker",
    "quantity",
    "avg_buy_price",
    "name",
    "account_group",
    "position_id",
    "cycle_id",
)


def _check_history_consistency(data: dict[str, Any]) -> None:
    """이력 문서의 holdings 가 이력(정본)으로 다시 계산한 현재 보유와 같은지(POC5-05).

    다르면 손상이다 — 이력에 잔량이 남았는데 holdings 만 빈 배열인 문서를 '정상 빈 보유'
    로 받아 OCI 보유를 비우지 않게 한다. 이력 자체를 계산할 수 없어도 손상이다.
    """
    from app import holdings_book  # 순수 계산 모듈(이력 문서일 때만 · 순환 import 없음)

    hist = data.get("personal_trade_history")
    if (
        data.get("schema_version") != 2
        or isinstance(data.get("revision"), bool)
        or not isinstance(data.get("revision"), int)
        or not isinstance(hist, dict)
        or not isinstance(hist.get("positions"), list)
        or not isinstance(hist.get("records"), list)
    ):
        raise HoldingsValidationError("보유 · 이력 문서 형식이 올바르지 않습니다.")
    records = hist["records"]
    if any(isinstance(r, dict) and "virtual" in r for r in records):
        raise HoldingsValidationError("저장된 기록에 임시 표시가 남아 있습니다(손상).")
    if any(
        not isinstance(r, dict) or set(r) - set(_DOC_ROW_KEYS) for r in data["holdings"]
    ):
        raise HoldingsValidationError("보유 목록 형식이 올바르지 않습니다(손상).")
    try:
        derived = holdings_book.compute(data)["holdings"]
    except Exception as e:  # noqa: BLE001 — 계산 불가(기록 손상 · 충돌) = 문서 손상
        raise HoldingsValidationError(f"매매 이력을 계산할 수 없습니다: {e}") from e

    def row(r: Any) -> tuple:
        if not isinstance(r, dict):
            return ("<not-a-row>",)
        out = []
        for k in _DOC_ROW_KEYS:
            v = r.get(k)
            if k in ("quantity", "avg_buy_price") and isinstance(v, (int, float)):
                v = float(v)
            out.append(v)
        return tuple(out)

    stored = data["holdings"]
    if not isinstance(stored, list) or [row(r) for r in stored] != [
        row(r) for r in derived
    ]:
        raise HoldingsValidationError(
            "보유 목록이 매매 이력과 맞지 않습니다(손상 · 빈 보유로 처리하지 않음)."
        )


def holdings_from_document(data: Any) -> list[Holding]:
    """보유 문서(JSON 객체) → 현재 보유(허용 5필드). 손상 · 이력 불일치는 예외.

    load() · PC OCI 적용 payload · 저장 경계가 같은 판정을 쓴다(POC5-05 · 한 곳).
    정상 빈 보유(전량매도)는 []. 이력 문서의 holdings 는 줄 ID 로 계산한 결과라 평단이
    우연히 같아진 두 줄을 삼중조합 중복으로 거절하지 않는다.
    """
    if not isinstance(data, dict):
        raise HoldingsValidationError("보유 파일의 최상위가 객체가 아닙니다.")
    raw_list = data.get("holdings")
    if raw_list is None:
        raise HoldingsValidationError("보유 파일의 'holdings' 키가 누락됐습니다.")
    if not isinstance(raw_list, list):
        raise HoldingsValidationError("보유 파일의 'holdings' 가 목록이 아닙니다.")
    history = is_history_document(data)
    if history:
        _check_history_consistency(data)
    return validate_holdings(raw_list, allow_empty=True, unique_triple=not history)


def save(holdings: list[Holding]) -> None:
    """검증된 holdings 를 기존 형태로 저장(구판 writer · 앱 경로는 holdings_store).

    POC5-05: 현재 파일이 이력 포함 문서면 저장하지 않는다 — 이 함수는 이력 · 줄 ID 를
    버리므로, 그 문서는 저장 경계(holdings_store)로만 바꾼다.
    """
    if HOLDINGS_FILE.exists():
        try:
            current = json.loads(HOLDINGS_FILE.read_text(encoding="utf-8"))
        except ValueError as e:
            # 손상 파일도 덮어쓰지 않는다(이력 문서였는지 알 수 없음 · 빈 보유로 바꾸지 않음).
            raise HoldingsValidationError(
                f"{HOLDINGS_FILE} 를 읽을 수 없어 덮어쓰지 않습니다."
            ) from e
        if is_history_document(current):
            raise HoldingsValidationError(
                "매매 이력이 든 보유 파일은 이 함수로 덮어쓰지 않습니다(종목 관리 화면 사용)."
            )
    HOLDINGS_DIR.mkdir(parents=True, exist_ok=True)
    HOLDINGS_FILE.write_bytes(serialize_payload(holdings))


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
    # POC5-05: 정상 빈 보유(전량매도)는 [] — 파일 없음과의 구분은 호출자가
    # HOLDINGS_FILE.exists() 로 한다. 이력 문서는 holdings 가 이력과 맞아야 한다.
    return holdings_from_document(data)
