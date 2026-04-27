"""POC2 Step 1A — holdings 기반 draft_payload → 사람이 읽는 message_text.

설계자 결정 (Step 1A):
- handoff artifact 에 top-level `message_text` 키 추가
- 메시지 문자열 생성 책임은 로컬 백엔드(여기). OCI bash 는 JSON 파싱하지 않음
- raw JSON 노출 금지. 존재하는 필드만 줄 단위로 표시
- 데이터 새로 만들지 않음 (현재가/평가손익/score 추가 금지)
- 없는 필드는 생략. undefined/null 노출 금지

대상은 holdings 기반 draft 만 명확히 식별한다 (recommendations 항목에
quantity/avg_buy_price 등 holdings 필드가 들어있는 형태). 식별 불가 / 누락 시는
None 을 반환하여 호출자가 적절히 처리하게 한다.
"""

from __future__ import annotations

from typing import Any, Optional


def _format_money(value: Any) -> Optional[str]:
    """숫자(또는 숫자 변환 가능 값) → '50,250원'. 변환 불가면 None."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    # 정수 경계는 정수처럼, 소수는 두 자리까지.
    if n == int(n):
        return f"{int(n):,}원"
    return f"{n:,.2f}원"


def _format_pct(value: Any) -> Optional[str]:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return f"{n:g}%"


def _format_qty(value: Any) -> Optional[str]:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n == int(n):
        return f"{int(n):,}"
    return f"{n:,.4f}".rstrip("0").rstrip(".")


def is_holdings_draft(payload: Any) -> bool:
    """draft_payload 가 holdings 기반 형태인지 식별.

    기준: recommendations 가 list 이고 첫 항목에 quantity 또는 avg_buy_price 가 있으면
    holdings 기반으로 본다 (POC2 Step 1 운영 흐름).
    """
    if not isinstance(payload, dict):
        return False
    recs = payload.get("recommendations")
    if not isinstance(recs, list) or len(recs) == 0:
        return False
    head = recs[0]
    if not isinstance(head, dict):
        return False
    return ("quantity" in head) or ("avg_buy_price" in head)


def _render_item(idx: int, item: dict[str, Any]) -> str:
    """단일 holdings 항목 → 사람이 읽는 줄 묶음.

    표시 우선순위:
      헤더(종목명/종목코드)
      수량 / 평균 매입단가 / 매입금액 / 매입비중 (Step 1 필드)
      현재가 / 평가금액 / 평가손익 / 평가수익률 / 시장비중 (Step 2 필드, 있을 때만)
      [시세 미확인] / [평가 정보 부족] (Step 2 누락 표시)
      판단 / 사유

    payload 에 없는 값은 줄 자체를 생략. None / undefined / NaN 노출 금지.
    "실시간" 표현은 사용하지 않는다 (지시문 금지어).
    """
    ticker = item.get("ticker") or ""
    name = item.get("name") or ticker or "(종목 미상)"

    # 헤더: "1. RISE 미국은행TOP10 (0013P0)" 또는 "1. 0013P0" (name 없을 때)
    if name and ticker and name != ticker:
        header = f"{idx}. {name} ({ticker})"
    elif ticker:
        header = f"{idx}. {ticker}"
    else:
        header = f"{idx}. {name}"

    lines: list[str] = [header]

    qty = _format_qty(item.get("quantity"))
    if qty is not None:
        lines.append(f"   - 수량: {qty}")

    avg_price = _format_money(item.get("avg_buy_price"))
    if avg_price is not None:
        lines.append(f"   - 평균 매입단가: {avg_price}")

    invested = _format_money(item.get("invested_amount"))
    if invested is not None:
        lines.append(f"   - 매입금액: {invested}")

    weight = _format_pct(item.get("buy_weight_pct"))
    if weight is not None:
        lines.append(f"   - 매입비중: {weight}")

    # POC2 Step 2 — 시세/평가/손익/시장비중 (모두 옵셔널, 있으면 줄 추가)
    current_price = _format_money(item.get("current_price"))
    if current_price is not None:
        lines.append(f"   - 현재가: {current_price}")

    eval_amount = _format_money(item.get("eval_amount"))
    if eval_amount is not None:
        lines.append(f"   - 평가금액: {eval_amount}")

    pnl_amount = _format_money(item.get("pnl_amount"))
    if pnl_amount is not None:
        lines.append(f"   - 평가손익: {pnl_amount}")

    pnl_rate = _format_pct(item.get("pnl_rate_pct"))
    if pnl_rate is not None:
        lines.append(f"   - 평가수익률: {pnl_rate}")

    market_weight = _format_pct(item.get("market_weight_pct"))
    if market_weight is not None:
        lines.append(f"   - 시장비중: {market_weight}")

    # 누락 사유 명시 — 사용자가 "왜 비었는지" 알 수 있게.
    # holdings 항목인데 current_price 자체가 키로 없으면 "시세 미확인" 으로 간주
    # (Step 2 to_recommendation_dict 가 None 시세 키를 생략하므로 키 존재 여부로 판단).
    if item.get("current_price") is None and (
        "quantity" in item or "avg_buy_price" in item
    ):
        lines.append("   - [시세 미확인]")

    action = item.get("action")
    if isinstance(action, str) and action:
        lines.append(f"   - 판단: {action}")

    reason = item.get("reason")
    if isinstance(reason, str) and reason:
        lines.append(f"   - 사유: {reason}")

    return "\n".join(lines)


def build_message_text(run_id: str, payload: dict[str, Any]) -> str:
    """holdings draft_payload → Telegram 본문.

    호출자는 is_holdings_draft 로 사전 검증해야 한다. 그렇지 않으면 빈 문자열 반환.
    """
    if not is_holdings_draft(payload):
        return ""

    title = payload.get("title") or "보유 종목 기반 초안"
    note = payload.get("note") or ""
    recs = payload.get("recommendations") or []

    header_lines = [
        "✅ POC2 holdings 승인 처리",
        f"run_id: {run_id}",
        f"title: {title}",
    ]
    if note:
        header_lines.append("")
        header_lines.append(note)

    body_lines: list[str] = ["", "보유 종목:"]
    for i, item in enumerate(recs, start=1):
        if not isinstance(item, dict):
            continue
        body_lines.append(_render_item(i, item))

    return "\n".join(header_lines + body_lines)
