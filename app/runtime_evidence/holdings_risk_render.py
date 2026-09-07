"""POC3-OPS-02A — 위험 알림 본문 렌더러.

설계자 확정 (PLAN V1.2 §4.2) — **동시 발생을 억제하지 않고 한 메시지로 묶는다.**
여러 보유종목의 동시 하락은 오히려 중요한 포트폴리오 위험이다.

- 구간별 그룹 · 해당 종목 **전부** 표시 · 임의 Top N 제한 **없음**
- 헤더에 `보유 N종목 중 M종목 동시 하락` (1종목이면 `동시` 없이 `1종목 하락`)

**이름은 `[보유 급락 알림]` 이다** (사용자 지시 2026-09-07). 09:15 `[보유 종목
관찰 브리핑]` 과 이름이 비슷해 혼동이 생겼다. 둘은 역할이 다르다 — 관찰 브리핑은
하루 기준으로 20거래일 하락·매입/고점 대비를 정리하고, 급락 알림은 장중 7회
확인해 **전일 대비 새로 하락하거나 악화될 때만** 보낸다.
- **국가·섹터 원인 해석 금지** — '미국 익스포저 하락' 같은 문구는 입증되지 않았다
- **면책문구·매매지시 문구 없음**

배치는 OPS-01A 와 같은 **두 줄**이다. 발송이 `parse_mode="HTML"` 이라 Telegram 이
비례 글꼴로 렌더해 공백 정렬이 성립하지 않으므로, 종목명을 분리한다.

    ``  종목명 (N개 계좌)``
    ``      전일 대비 -6.2% · 고점 대비 -11.4% · 매입대비 +12.1%``

**시가 대비는 표시하지 않는다** (PLAN V1.3 §4.2-b — 원본 응답에 시가 없음).
"""

from __future__ import annotations

from typing import Optional

from app.runtime_evidence.holdings_risk import (
    GROUP_ORDER,
    RiskTicker,
    group_label,
    short_label,
)
from app.runtime_evidence.holdings_risk_state import RiskChangeSet

HEADER = "[보유 급락 알림]"
PREVIEW_HEADER = "[보유 급락 알림 — 형식 미리보기]"

UNAVAILABLE_GROUP = "데이터 확인 필요"
UNAVAILABLE_NOTE = "직전 거래일 종가 또는 오늘 시세를 확인할 수 없음"


def _name_cell(item: RiskTicker) -> str:
    """다계좌는 ticker 기준으로 합쳐 **한 번만**. (PLAN §4.6)"""
    if item.account_count > 1:
        return f"{item.name} ({item.account_count}개 계좌)"
    return item.name


def _detail_parts(item: RiskTicker) -> list[str]:
    """둘째 줄. 순서 = 전일 대비(trigger) → 고점 대비 → 매입대비."""
    parts: list[str] = []
    if item.day_drop_pct is not None:
        parts.append(f"전일 대비 {item.day_drop_pct:+.1f}%")
    if item.drawdown_pct is not None:
        parts.append(f"고점 대비 {item.drawdown_pct:+.1f}%")
    if item.profit_loss_pct is not None:
        parts.append(f"매입대비 {item.profit_loss_pct:+.1f}%")
    return parts


def _item_line(item: RiskTicker, extra: str = "") -> str:
    detail = " · ".join(_detail_parts(item))
    if extra:
        detail = f"{detail}{extra}"
    return f"  {_name_cell(item)}\n      {detail}"


def render_risk_groups(
    items: list[RiskTicker], *, worsened_from: Optional[dict[str, str]] = None
) -> list[str]:
    """구간별 그룹. 빈 그룹은 만들지 않는다.

    `worsened_from` 이 있으면 그 종목 줄 끝에 `(이전 구간 → 현재 구간)` 을 붙인다.
    """
    came_from = worsened_from or {}
    lines: list[str] = []
    for state in GROUP_ORDER:
        members = [i for i in items if i.state == state]
        if not members:
            continue
        lines.append(f"■ {group_label(state)} ({len(members)})")
        for i in members:
            prev = came_from.get(i.ticker)
            extra = f"   ({short_label(prev)} → {short_label(i.state)})" if prev else ""
            lines.append(_item_line(i, extra=extra))
        lines.append("")
    return lines


def render_unavailable_group(unavailable: list[tuple[str, str]]) -> list[str]:
    """`데이터 확인 필요` 그룹 (PLAN §4.6 부분 실패 · §4.7 결손 처리).

    시세 조회에 실패했거나 **직전 거래일 종가가 정확히 없는** 종목이다. 하락률을
    계산할 수 없으므로 구간을 붙이지 않는다. 진단 필드에만 남기면 "그 종목은
    괜찮다" 로 읽혀 **데이터를 못 봤다는 사실이 숨는다**.
    """
    if not unavailable:
        return []
    lines = [f"■ {UNAVAILABLE_GROUP} ({len(unavailable)})"]
    for _ticker, name in unavailable:
        lines.append(f"  {name}\n      {UNAVAILABLE_NOTE}")
    lines.append("")
    return lines


def render_risk_alert(
    changes: RiskChangeSet,
    *,
    slot_label: str,
    held_ticker_count: int,
    quote_asof: Optional[str] = None,
    base_close_date: Optional[str] = None,
    header: str = HEADER,
    unavailable: Optional[list[tuple[str, str]]] = None,
) -> str:
    """신규·악화를 **한 건으로 묶어** 렌더.

    `held_ticker_count` 는 보유 **고유 ticker 수**다(다계좌 합친 뒤).

    `unavailable` 은 `(ticker, 종목명)` 목록이다. 발송이 성립할 때 **본문 말미에
    함께 싣는다**. 결손만으로 발송을 촉발하지는 않는다 — §4.3 발송 표에 그 항목이
    없고, 촉발시키면 억제 계약이 없어 매 틱 알림이 나간다.
    """
    items = list(changes.new) + [i for i, _ in changes.worsened]
    if not items:
        return ""
    came_from = {i.ticker: prev for i, prev in changes.worsened}
    unavail = list(unavailable or [])

    head = f"{header} {slot_label}" if slot_label else header
    # 1종목일 때 "1종목 동시 하락" 은 어색하다 (사용자 지시 2026-09-07).
    kind = "하락" if len(items) == 1 else "동시 하락"
    lines = [f"{head} — 보유 {held_ticker_count}종목 중 {len(items)}종목 {kind}"]
    if base_close_date or quote_asof:
        lines.append(
            f"기준: 직전 거래일 종가 {base_close_date or '—'} · 시세 {quote_asof or '—'}"
        )
    lines.append("")
    lines.extend(render_risk_groups(items, worsened_from=came_from))
    lines.extend(render_unavailable_group(unavail))
    return "\n".join(lines).rstrip()
