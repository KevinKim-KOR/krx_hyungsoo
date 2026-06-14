"""POC2 Cleanup — draft_message 의 focus / summary 렌더링 분리 (2026-06-14).

`app/draft_message.py` 의 KS-10 near 해소를 위해 다음 helper 들을 본 모듈로
이관했다. 산식 / 문구 / 데이터 계약 변경 0건. 함수 시그니처와 동작 그대로.

본 모듈은 다음 helper 를 제공한다:

- `compute_summary` — 전체 보유종목 요약 dict.
- `select_focus_items` — 주목 종목 선별 (카테고리, item) 튜플 리스트.
- `_render_summary_lines` — 요약 dict → 사람이 읽는 줄 묶음.
- `_render_focus_item` — 주목 종목 1건 → 줄 묶음.
- `_render_focus_section` — 주목 종목 카테고리별 섹션 묶음.

draft_message.py 가 본 모듈을 import 하여 사용한다.
"""

from __future__ import annotations

from typing import Any

from app.message_helpers import (
    _format_money,
    _format_pct,
    _format_signed_money,
    _format_signed_pct,
    _is_calc_available,
    _is_priced,
    _item_label,
    _to_finite_float,
)

# Top N 정책 상수 (Step 2B) — draft_message 와 동일 값 사용. 본 파일에 직접 정의해
# 두면 draft_message 의 상수 재import 없이도 동작한다.
TOP_N_PRICE_MISSING = 3
TOP_N_BOTTOM_PNL_RATE = 3
TOP_N_TOP_MARKET_WEIGHT = 3
TOP_N_TOP_PNL_RATE = 3


def compute_summary(recs: list[dict[str, Any]]) -> dict[str, Any]:
    """전체 보유종목 요약. 시세 확인/미확인 + 계산 가능 여부를 분리.

    카운트 정의:
    - total_count          : 전체 종목 수
    - priced_count         : 시세 확인 종목 수 (current_price 유효)
    - unpriced_count       : 시세 미확인 종목 수
    - calc_available_count : 평가 계산 가능 종목 수 (current_price + eval_amount + invested_amount 모두 유효 양수)
    - calc_missing_count   : 시세는 있는데 평가 계산 불가능 종목 수 (priced - calc_available)

    집계 정의:
    - total_invested  : 전체 종목 invested_amount 합계 (있는 것만)
    - priced_eval     : 평가 계산 가능 종목 기준 eval_amount 합계
    - priced_pnl      : 같은 종목 기준 손익 합계
    - priced_pnl_rate_pct : 같은 종목 기준 수익률
    """
    total_count = len(recs)
    priced_items = [it for it in recs if isinstance(it, dict) and _is_priced(it)]
    calc_items = [it for it in priced_items if _is_calc_available(it)]
    unpriced_count = total_count - len(priced_items)
    calc_missing_count = len(priced_items) - len(calc_items)

    total_invested = 0.0
    for it in recs:
        if not isinstance(it, dict):
            continue
        n = _to_finite_float(it.get("invested_amount"))
        if n is not None:
            total_invested += n

    calc_invested = 0.0
    calc_eval = 0.0
    for it in calc_items:
        inv = _to_finite_float(it.get("invested_amount"))
        ev = _to_finite_float(it.get("eval_amount"))
        calc_invested += inv  # type: ignore[operator]
        calc_eval += ev  # type: ignore[operator]

    calc_pnl = calc_eval - calc_invested if calc_items else None
    calc_pnl_rate = (
        (calc_pnl / calc_invested * 100.0)
        if calc_items and calc_invested > 0 and calc_pnl is not None
        else None
    )

    return {
        "total_count": total_count,
        "priced_count": len(priced_items),
        "unpriced_count": unpriced_count,
        "calc_available_count": len(calc_items),
        "calc_missing_count": calc_missing_count,
        "total_invested": total_invested,
        "priced_eval": calc_eval if calc_items else None,
        "priced_pnl": calc_pnl,
        "priced_pnl_rate_pct": calc_pnl_rate,
    }


def _render_summary_lines(summary: dict[str, Any]) -> list[str]:
    """요약 dict → 사람이 읽는 줄 묶음.

    평가 라벨은 "시세 확인" 이 아니라 "평가 계산 N개 기준" 으로 표기 — current_price
    는 있지만 eval_amount 가 누락된 종목이 0 원으로 취급되지 않도록 명시 분리.
    """
    lines: list[str] = ["", "전체 요약:"]
    lines.append(f"   - 보유 종목: {summary['total_count']}개")
    lines.append(
        f"   - 시세 확인: {summary['priced_count']}개 / "
        f"미확인: {summary['unpriced_count']}개"
    )
    if summary.get("calc_missing_count", 0) > 0:
        lines.append(
            f"   - 평가 계산 가능: {summary['calc_available_count']}개 / "
            f"계산 정보 부족: {summary['calc_missing_count']}개"
        )

    total_inv = _format_money(summary.get("total_invested"))
    if total_inv is not None:
        lines.append(f"   - 총 매입금액: {total_inv}")

    calc_count = summary.get("calc_available_count", 0)
    if calc_count > 0:
        basis = f"(평가 계산 {calc_count}개 기준)"
        ev = _format_money(summary.get("priced_eval"))
        if ev is not None:
            lines.append(f"   - 평가금액: {ev} {basis}")
        pnl = _format_signed_money(summary.get("priced_pnl"))
        if pnl is not None:
            lines.append(f"   - 평가손익: {pnl} {basis}")
        pnl_rate = _format_signed_pct(summary.get("priced_pnl_rate_pct"))
        if pnl_rate is not None:
            lines.append(f"   - 평가수익률: {pnl_rate} {basis}")

    if summary["unpriced_count"] > 0 or summary.get("calc_missing_count", 0) > 0:
        lines.append(
            "   - ⚠ 일부 종목 시세 미확인 또는 계산 정보 부족 — "
            "평가금액/손익/수익률은 평가 계산 가능 종목 기준입니다."
        )

    return lines


def select_focus_items(
    recs: list[dict[str, Any]],
) -> list[tuple[str, dict[str, Any]]]:
    """주목 종목 선별. (category_label, item) 튜플 리스트 반환.

    우선순위:
      1. price_missing — 가격 미확인 (최대 TOP_N_PRICE_MISSING)
      2. calc_missing  — 시세는 있는데 평가 계산 정보 부족 (최대 TOP_N_PRICE_MISSING)
      3. bottom_pnl_rate — 평가수익률 하위 (최대 TOP_N_BOTTOM_PNL_RATE)
      4. top_market_weight — 시장비중 상위 (최대 TOP_N_TOP_MARKET_WEIGHT)
      5. top_pnl_rate — 평가수익률 상위 (최대 TOP_N_TOP_PNL_RATE)
    """
    valid_items = [it for it in recs if isinstance(it, dict)]
    selected: list[tuple[str, dict[str, Any]]] = []
    seen_tickers: set[str] = set()

    def _add(category: str, item: dict[str, Any]) -> None:
        ticker = item.get("ticker") or _item_label(item)
        if ticker in seen_tickers:
            return
        seen_tickers.add(str(ticker))
        selected.append((category, item))

    # 1. 가격 미확인
    price_missing = [it for it in valid_items if not _is_priced(it)]
    for it in price_missing[:TOP_N_PRICE_MISSING]:
        _add("price_missing", it)

    # 2. 계산 정보 부족
    calc_missing = [
        it for it in valid_items if _is_priced(it) and not _is_calc_available(it)
    ]
    for it in calc_missing[:TOP_N_PRICE_MISSING]:
        _add("calc_missing", it)

    # 3. 평가수익률 하위
    pnl_rate_valid = [
        (it, _to_finite_float(it.get("pnl_rate_pct"))) for it in valid_items
    ]
    pnl_rate_sortable = [(it, n) for it, n in pnl_rate_valid if n is not None]

    bottom_sorted = sorted(pnl_rate_sortable, key=lambda x: x[1])
    for it, _ in bottom_sorted[:TOP_N_BOTTOM_PNL_RATE]:
        _add("bottom_pnl_rate", it)

    # 4. 시장비중 상위
    market_weight_sortable = [
        (it, n)
        for it in valid_items
        for n in [_to_finite_float(it.get("market_weight_pct"))]
        if n is not None
    ]
    top_market_sorted = sorted(market_weight_sortable, key=lambda x: x[1], reverse=True)
    for it, _ in top_market_sorted[:TOP_N_TOP_MARKET_WEIGHT]:
        _add("top_market_weight", it)

    # 5. 평가수익률 상위
    top_pnl_sorted = sorted(pnl_rate_sortable, key=lambda x: x[1], reverse=True)
    for it, _ in top_pnl_sorted[:TOP_N_TOP_PNL_RATE]:
        _add("top_pnl_rate", it)

    return selected


def _render_focus_item(item: dict[str, Any]) -> str:
    """주목 종목 1건 → 사람이 읽는 줄 묶음."""
    label = _item_label(item)
    lines: list[str] = [f"   • {label}"]

    pnl_rate = _format_signed_pct(item.get("pnl_rate_pct"))
    if pnl_rate is not None:
        lines.append(f"     - 평가수익률: {pnl_rate}")

    pnl_amount = _format_signed_money(item.get("pnl_amount"))
    if pnl_amount is not None:
        lines.append(f"     - 평가손익: {pnl_amount}")

    market_weight = _format_pct(item.get("market_weight_pct"))
    if market_weight is not None:
        lines.append(f"     - 시장비중: {market_weight}")

    if not _is_priced(item):
        lines.append("     - [시세 미확인]")
    elif not _is_calc_available(item):
        lines.append("     - [계산 정보 부족]")

    action = item.get("action")
    if isinstance(action, str) and action:
        lines.append(f"     - 판단: {action}")

    reason = item.get("reason")
    if isinstance(reason, str) and reason:
        lines.append(f"     - 사유: {reason}")

    return "\n".join(lines)


_CATEGORY_HEADERS = {
    "price_missing": "🔍 시세 미확인 종목",
    "calc_missing": "⚙ 계산 정보 부족 종목",
    "bottom_pnl_rate": "📉 평가수익률 하위",
    "top_market_weight": "📊 시장비중 상위",
    "top_pnl_rate": "📈 평가수익률 상위",
}


def _render_focus_section(
    focus: list[tuple[str, dict[str, Any]]],
) -> list[str]:
    """주목 종목 섹션. 카테고리별로 묶어 표시. 비어있으면 빈 리스트."""
    if not focus:
        return []

    by_category: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for category, item in focus:
        if category not in by_category:
            by_category[category] = []
            order.append(category)
        by_category[category].append(item)

    lines: list[str] = ["", "주목 종목:"]
    for category in order:
        items = by_category[category]
        if not items:
            continue
        header = _CATEGORY_HEADERS.get(category, category)
        lines.append(f"  {header}")
        for it in items:
            lines.append(_render_focus_item(it))

    return lines
