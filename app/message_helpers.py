"""POC2 Step 5D-2 Final — draft_message.py 의 leaf-level format / 항목 식별 helpers 분리.

분리 목적: draft_message.py KS-10 근접(>=600라인) 해소.
분리 전후 동작 / 출력 / 부호 / 숫자 포매팅 / 시세 확인 판정 / 평가 계산 가능 판정 모두 동일.

본 모듈에는 외부 의존이 없는 leaf utilities 만 둔다:
- 숫자 변환 / 포매팅 (_to_finite_float, _format_*)
- 항목 식별 (_is_priced, _is_calc_available, _is_default_hold, _item_label)
- 정적 사유 상수 (DEFAULT_HOLD_REASON)

draft_message.py 는 본 모듈 심볼을 재공개(re-export) 하여 기존 import 경로
(`from app.draft_message import compute_summary` / `draft_message.DEFAULT_HOLD_REASON`)
가 그대로 유지된다.
"""

from __future__ import annotations

import math
from typing import Any, Optional

# 기본 HOLD reason — 이번 단계 추천 로직 없이 holdings stub 으로 채워지는 정적 사유.
# 이 사유와 정확히 일치하는 항목은 "기본 HOLD" 로 분류해 상세 목록에서 제외한다.
DEFAULT_HOLD_REASON = "보유 종목 현황 (이번 단계는 추천 판단 없이 HOLD 고정)"


def _to_finite_float(value: Any) -> Optional[float]:
    """엄격한 숫자 변환. None/bool/문자열 변환 실패/NaN/Inf 는 None 으로 차단.

    Top N 정렬 안전성: 누락/None/NaN/비숫자 필드를 정렬 대상에서 제외하기 위한 단일 진입점.
    bool 은 isinstance(int, bool) 이슈를 피하려 명시 차단.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(n) or math.isinf(n):
        return None
    return n


def _format_money(value: Any) -> Optional[str]:
    """숫자(또는 숫자 변환 가능 값) → '50,250원'. 변환 불가/NaN 이면 None."""
    n = _to_finite_float(value)
    if n is None:
        return None
    if n == int(n):
        return f"{int(n):,}원"
    return f"{n:,.2f}원"


def _format_pct(value: Any) -> Optional[str]:
    n = _to_finite_float(value)
    if n is None:
        return None
    return f"{n:g}%"


def _format_signed_money(value: Any) -> Optional[str]:
    """평가손익용 부호 포함 포맷. -1000 → '-1,000원', 1000 → '+1,000원'."""
    n = _to_finite_float(value)
    if n is None:
        return None
    sign = "+" if n > 0 else ""  # 0 / 음수는 그대로 (음수는 '-' 자체로 표시됨)
    if n == int(n):
        return f"{sign}{int(n):,}원"
    return f"{sign}{n:,.2f}원"


def _format_signed_pct(value: Any) -> Optional[str]:
    n = _to_finite_float(value)
    if n is None:
        return None
    sign = "+" if n > 0 else ""
    return f"{sign}{n:g}%"


def _is_priced(item: dict[str, Any]) -> bool:
    """current_price 키가 있고 유효 양수일 때만 '시세 확인' 으로 간주.

    주의: 시세 확인 ≠ 평가 계산 가능. 평가 계산 가능 여부는 _is_calc_available
    로 별도 판정 (eval_amount + invested_amount 가 모두 유효 양수여야 함).
    """
    if "current_price" not in item:
        return False
    n = _to_finite_float(item.get("current_price"))
    return n is not None and n > 0


def _is_calc_available(item: dict[str, Any]) -> bool:
    """평가 계산 가능 여부.

    eval_amount 와 invested_amount 가 모두 유효 양수여야 한다.
    current_price 는 있는데 eval_amount 가 누락된 경우 (예: quantity 누락,
    enrichment 단계 직전 끊긴 데이터) 는 "계산 정보 부족" 으로 분류한다.
    """
    if not _is_priced(item):
        return False
    ev = _to_finite_float(item.get("eval_amount"))
    inv = _to_finite_float(item.get("invested_amount"))
    return ev is not None and ev > 0 and inv is not None and inv > 0


def _is_default_hold(item: dict[str, Any]) -> bool:
    """기본 HOLD 종목 식별. action=HOLD + reason 이 정적 stub 일 때만 True."""
    action = item.get("action")
    reason = item.get("reason")
    return action == "HOLD" and reason == DEFAULT_HOLD_REASON


def _item_label(item: dict[str, Any]) -> str:
    """헤더 라벨. '종목명 (종목코드)' 또는 '종목코드' 단독."""
    ticker = item.get("ticker") or ""
    name = item.get("name") or ""
    if name and ticker and name != ticker:
        return f"{name} ({ticker})"
    if ticker:
        return str(ticker)
    if name:
        return str(name)
    return "(종목 미상)"
