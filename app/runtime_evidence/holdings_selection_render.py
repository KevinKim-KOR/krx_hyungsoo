"""POC3-OPS-01A — 보유 브리핑 본문 렌더러 (그룹화 · 변화분).

설계자 확정 (PLAN §3):
- **면책·주의 문구를 넣지 않는다.** 다른 면책·운영 설명으로 대체하지도 않는다.
- 고유 ticker 1회만. 다계좌는 종목 1행 + `(N개 계좌)`.
- **개수 상한 없음.** `최대 N개` · 상위 일부 표시 규칙을 두지 않는다.
- 평가금액·현재가·NAV·구성종목 등 선정과 무관한 숫자 제외.
- 보조 `RECENT_LOW_OR_DRAWDOWN` 은 행 끝 `[고점 대비 x%]` 로만.
- 헤더의 두 날짜는 다르다 — 분모는 과거 종가일, 분자는 실행 시점 시세.
"""

from __future__ import annotations

from typing import Optional

from app.runtime_evidence.holdings_selection import (
    DRAWDOWN_NOTE_MAX_PCT,
    GROUP_ORDER,
    REASON_DATA_UNAVAILABLE,
    SelectedTicker,
    group_label,
)
from app.runtime_evidence.holdings_selection_state import ChangeSet

HEADER = "[보유 종목 관찰 브리핑]"
PREVIEW_HEADER = "[보유 종목 관찰 브리핑 — 형식 미리보기]"


def _name_cell(item: SelectedTicker) -> str:
    if item.account_count > 1:
        return f"{item.name} ({item.account_count}개 계좌)"
    return item.name


def _value_cell(item: SelectedTicker) -> str:
    if item.primary_reason == REASON_DATA_UNAVAILABLE:
        return "현재가 조회 실패"
    value = item.reasons[item.primary_reason].get("value")
    return "20거래일 —" if value is None else f"20거래일 {value:+.1f}%"


def _drawdown_note(item: SelectedTicker) -> str:
    dd = item.drawdown_20d_pct
    if dd is None or dd > DRAWDOWN_NOTE_MAX_PCT:
        return ""
    return f"   [고점 대비 {dd:+.1f}%]"


def _item_line(item: SelectedTicker) -> str:
    return f"  {_name_cell(item)}  {_value_cell(item)}{_drawdown_note(item)}"


def render_groups(selected: list[SelectedTicker]) -> list[str]:
    """그룹 표시 순서대로 묶는다. 빈 그룹은 만들지 않는다."""
    lines: list[str] = []
    for reason, state in GROUP_ORDER:
        members = [
            i
            for i in selected
            if i.primary_reason == reason and i.primary_state == state
        ]
        if not members:
            continue
        lines.append(f"■ {group_label(reason, state)} ({len(members)})")
        lines.extend(_item_line(i) for i in members)
        lines.append("")
    return lines


def render_full(
    selected: list[SelectedTicker],
    *,
    slot_label: str,
    base_close_date: Optional[str],
    quote_asof: Optional[str],
) -> str:
    """OPEN(또는 fallback) 전체 현재 상태."""
    head = f"{HEADER} {slot_label}" if slot_label else HEADER
    lines = [head]
    if base_close_date or quote_asof:
        lines.append(
            f"기준: 20거래일 전 종가 {base_close_date or '—'} · 시세 {quote_asof or '—'}"
        )
    lines.append("")
    lines.extend(render_groups(selected))
    return "\n".join(lines).rstrip()


def render_changes(
    changes: ChangeSet,
    *,
    slot_label: str,
    resolved_names: Optional[dict[str, str]] = None,
) -> str:
    """MIDDAY·CLOSE 변화분."""
    total = len(changes.new) + len(changes.moved) + len(changes.resolved)
    lines = [f"{HEADER} {slot_label} — 변화 {total}건", ""]

    if changes.new:
        lines.append(f"■ 새로 선정 ({len(changes.new)})")
        for item in changes.new:
            label = group_label(item.primary_reason, item.primary_state)
            lines.append(f"{_item_line(item)}   ({label})")
        lines.append("")

    if changes.moved:
        lines.append(f"■ 구간 이동 ({len(changes.moved)})")
        for item, before in changes.moved:
            before_txt = ", ".join(group_label(r, s) for r, s in sorted(before.items()))
            after_txt = ", ".join(
                group_label(r, v["state"]) for r, v in sorted(item.reasons.items())
            )
            lines.append(f"{_item_line(item)}")
            lines.append(f"      ({before_txt} → {after_txt})")
        lines.append("")

    if changes.resolved:
        names = resolved_names or {}
        lines.append(f"■ 정상 해소 ({len(changes.resolved)})")
        for ticker in changes.resolved:
            lines.append(f"  {names.get(ticker, ticker)}")
        lines.append("")

    return "\n".join(lines).rstrip()
