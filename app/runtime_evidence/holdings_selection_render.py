"""POC3-OPS-01A — 보유 브리핑 본문 렌더러 (그룹화 · 변화분).

설계자 확정 (PLAN §3):
- **면책·주의 문구를 넣지 않는다.** 다른 면책·운영 설명으로 대체하지도 않는다.
- 고유 ticker 1회만. 다계좌는 종목 1행 + `(N개 계좌)`.
- **개수 상한 없음.** `최대 N개` · 상위 일부 표시 규칙을 두지 않는다.
- 평가금액·현재가·NAV·구성종목 등 선정과 무관한 숫자 제외.
- 헤더의 두 날짜는 다르다 — 분모는 과거 종가일, 분자는 실행 시점 시세.

**두 줄 배치 (사용자 확정 2026-09-06 · C안)**

    ``  종목명 (N개 계좌)``
    ``      매입대비 +12.3% · 20거래일 -6.7% · 고점 대비 -10.5%``

한 줄에 몰면 종목명 길이에 따라 뒤 항목이 밀린다. 게다가 발송이
``parse_mode="HTML"`` 이라 Telegram 이 **비례 글꼴**로 렌더해서 공백으로 맞춘
열이 어차피 정렬되지 않는다. 종목명을 분리하면 그 문제가 사라진다.

**매입가 대비 손익률을 맨 앞에 둔다.** 라벨은 `매입대비` 다 (설계자 확정
2026-09-06 — `매입` 만으로는 매입가인지 손익인지 모호하다). 사용자 요청 —
20일 하락률만으로는
"팔지 홀딩할지" 를 못 정한다(20거래일 -6.7% 인데 매입 +89.2% 인 종목과
20거래일 -6.1% 인데 매입 -3.5% 인 종목이 같이 있다).
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


def _detail_parts(item: SelectedTicker) -> list[str]:
    """둘째 줄 항목들. 순서 = 매입 → 20거래일 → 고점 대비."""
    parts: list[str] = []
    if item.profit_loss_pct is not None:
        parts.append(f"매입대비 {item.profit_loss_pct:+.1f}%")
    parts.append(_value_cell(item))
    dd = item.drawdown_20d_pct
    if dd is not None and dd <= DRAWDOWN_NOTE_MAX_PCT:
        parts.append(f"고점 대비 {dd:+.1f}%")
    return parts


def _item_line(item: SelectedTicker, extra: str = "") -> str:
    """종목 1건 = **두 줄**. `extra` 는 둘째 줄 끝에 덧붙인다(구간 이동 표기)."""
    detail = " · ".join(_detail_parts(item))
    if extra:
        detail = f"{detail}{extra}"
    return f"  {_name_cell(item)}\n      {detail}"


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
            lines.append(_item_line(item, extra=f"   ({label})"))
        lines.append("")

    if changes.moved:
        lines.append(f"■ 구간 이동 ({len(changes.moved)})")
        for item, before in changes.moved:
            before_txt = ", ".join(group_label(r, s) for r, s in sorted(before.items()))
            after_txt = ", ".join(
                group_label(r, v["state"]) for r, v in sorted(item.reasons.items())
            )
            lines.append(_item_line(item))
            lines.append(f"      ({before_txt} → {after_txt})")
        lines.append("")

    if changes.resolved:
        names = resolved_names or {}
        lines.append(f"■ 정상 해소 ({len(changes.resolved)})")
        for ticker in changes.resolved:
            lines.append(f"  {names.get(ticker, ticker)}")
        lines.append("")

    return "\n".join(lines).rstrip()
