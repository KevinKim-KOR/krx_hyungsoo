"""POC3-02C-OPS-02 — 장중 급등락 본문 (설계자 §6·§7).

```text
[장중 급등락] 10:30

보유종목
• KODEX ○○: 전일 대비 -3.2%
  보유 급락 주의

신규 진입 검토
• 반도체 · KODEX 반도체: +2.1%
  5일 +4.3% · 20일 +8.7%

진입 회피
• 2차전지 · KODEX 2차전지산업: -2.4%
  장중 급락

기준
현재가 2026-09-21 10:30 · 직전 종가 2026-09-18

※ 자동 조건 감지이며 매수·매도 지시가 아닙니다.
```

**후보가 없는 구역은 통째로 생략**하고, 모든 구역이 비면 빈 문자열을 돌려준다
(러너가 미발송 처리).

한 메시지 안 우선순위(§6) — 상한에 걸리면 **아래쪽부터** 잘린다.

```text
1 보유 급락  2 보유 급등  3 진입 회피－급락  4 진입 회피－추격주의  5 진입 검토
```

잘린 신호도 **이력에는 남는다** — 이 모듈은 본문만 만들고, 이력 기록은 호출자가
`SectionPlan.dropped` 로 받아 처리한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.runtime_evidence.holdings_risk import (
    RISK_STATE_SHORT,
    SURGE_STATE_SHORT,
)
from app.runtime_evidence.sector_signal import (
    STATE_AVOID_CHASE,
    STATE_AVOID_DROP,
    STATE_ENTRY_REVIEW,
    STATE_LABEL,
    SectorSignal,
)

HEADER = "[장중 급등락]"
PREVIEW_HEADER = "[장중 급등락 — 형식 미리보기]"
# 설계자 확정 (§15-1 · 2026-09-20).
#
# 최초 §7 지정 문구 `"매수·매도 지시가 아닙니다"` 는 **부정문인데도**
# `FORBIDDEN_PHRASES` 의 `"매도 지시"` 에 부분일치해 러너가 발송을 막았다.
# 가드를 완화하지 않고 **문구를 바꿨다** — `매수`·`매도`·`매매`·`지시` 를 전부
# 피한다.
#
# **신규 통합 메시지에만** 붙는다. 비활성 상태의 기존 `[보유 급락 알림]` 은
# "면책문구·매매지시 문구 없음"(POC3-OPS-02A) 계약을 그대로 유지한다.
DISCLAIMER = "※ 자동 감지 결과이며, 최종 판단은 사용자가 합니다."

SECTION_HELD = "보유종목"
SECTION_ENTRY = "신규 진입 검토"
SECTION_AVOID = "진입 회피"


@dataclass
class SectionPlan:
    """상한 적용 후 실제로 실릴 것과 잘린 것."""

    held_drop: list[Any] = field(default_factory=list)
    held_surge: list[Any] = field(default_factory=list)
    avoid_drop: list[SectorSignal] = field(default_factory=list)
    avoid_chase: list[SectorSignal] = field(default_factory=list)
    entry: list[SectorSignal] = field(default_factory=list)
    dropped: list[dict[str, Any]] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (
            self.held_drop
            or self.held_surge
            or self.avoid_drop
            or self.avoid_chase
            or self.entry
        )

    def total(self) -> int:
        return (
            len(self.held_drop)
            + len(self.held_surge)
            + len(self.avoid_drop)
            + len(self.avoid_chase)
            + len(self.entry)
        )


def _fmt_pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{v:+.1f}%"


def build_section_plan(
    *,
    held_drop: list[Any],
    held_surge: list[Any],
    sector_signals: list[SectorSignal],
    max_items_per_section: int,
) -> SectionPlan:
    """§6 우선순위대로 구역을 채우고 **구역별 상한**을 적용한다.

    상한은 **구역 단위**다 — 하위 유형마다 따로 적용하면 안 된다(검증자 지적).
    「보유종목」에 급락 3 + 급등 3 = 6개가 들어가면 구역 상한이 6이 된 셈이고,
    한 메시지 최대가 9가 아니라 15가 된다.

    ```text
    보유종목    급락 → 급등 순으로 채워 합계 3개
    진입 회피   급락 → 추격주의 순으로 채워 합계 3개
    진입 검토   3개
    → 한 메시지 최대 9종목
    ```

    상한을 넘은 것은 버리지 않고 `dropped` 에 남긴다(설계 §6).
    """
    plan = SectionPlan()
    cap = max(0, int(max_items_per_section))

    def fill(groups: list[tuple[list[Any], list[Any]]], section: str) -> None:
        """한 **구역** 안에서 우선순위대로 채우고 합계 `cap` 에서 자른다."""
        room = cap
        for items, bucket in groups:
            for item in items:
                if room > 0:
                    bucket.append(item)
                    room -= 1
                else:
                    plan.dropped.append(
                        {
                            "section": section,
                            "ticker": getattr(item, "ticker", None),
                            "state": getattr(item, "state", None),
                            "reason": "section_cap",
                        }
                    )

    # 보유종목 — §6 우선순위 1 급락 → 2 급등.
    fill([(held_drop, plan.held_drop), (held_surge, plan.held_surge)], SECTION_HELD)
    # 진입 회피 — §6 우선순위 3 급락 → 4 추격주의.
    fill(
        [
            (
                [s for s in sector_signals if s.state == STATE_AVOID_DROP],
                plan.avoid_drop,
            ),
            (
                [s for s in sector_signals if s.state == STATE_AVOID_CHASE],
                plan.avoid_chase,
            ),
        ],
        SECTION_AVOID,
    )
    # 진입 검토 — §6 우선순위 5.
    fill(
        [([s for s in sector_signals if s.state == STATE_ENTRY_REVIEW], plan.entry)],
        SECTION_ENTRY,
    )
    return plan


def _held_lines(items: list[Any], labels: dict[str, str], kind: str) -> list[str]:
    out: list[str] = []
    for i in items:
        name = getattr(i, "name", None) or getattr(i, "ticker", "")
        pct = getattr(i, "day_drop_pct", None)
        if pct is None:
            pct = getattr(i, "day_return_pct", None)
        out.append(f"• {name}: 전일 대비 {_fmt_pct(pct)}")
        label = labels.get(getattr(i, "state", ""), "")
        out.append(f"  {kind}{(' ' + label) if label else ''}")
    return out


def _sector_lines(items: list[SectorSignal], *, with_window: bool) -> list[str]:
    out: list[str] = []
    for s in items:
        out.append(f"• {s.sector_key} · {s.name}: {_fmt_pct(s.day_return_pct)}")
        if with_window:
            out.append(
                f"  5일 {_fmt_pct(s.return_5d_pct)} · 20일 {_fmt_pct(s.return_20d_pct)}"
            )
        else:
            out.append(f"  {STATE_LABEL.get(s.state, '')}")
    return out


def render_intraday_alert(
    plan: SectionPlan,
    *,
    slot_label: str,
    quote_asof: Optional[str] = None,
    base_close_date: Optional[str] = None,
    header: str = HEADER,
    disclaimer: str = DISCLAIMER,
) -> str:
    """§7 본문. **모든 구역이 비면 빈 문자열**(미발송).

    `disclaimer` 기본값이 빈 문자열인 이유는 위 `DISCLAIMER` 주석 참조 —
    설계 지정 문구가 `FORBIDDEN_PHRASES` 와 충돌한다.
    """
    if plan.is_empty():
        return ""

    lines: list[str] = [f"{header} {slot_label}".strip()]

    # 짧은 라벨을 쓴다 — 줄 앞에 이미 `전일 대비 -5.4%` 가 있어 긴 라벨
    # (`전일 대비 하락 5~7%`)을 붙이면 같은 말이 두 번 나온다.
    held = _held_lines(plan.held_drop, RISK_STATE_SHORT, "보유 급락") + _held_lines(
        plan.held_surge, SURGE_STATE_SHORT, "보유 급등"
    )
    if held:
        lines += ["", SECTION_HELD] + held

    if plan.entry:
        lines += ["", SECTION_ENTRY] + _sector_lines(plan.entry, with_window=True)

    avoid = plan.avoid_drop + plan.avoid_chase
    if avoid:
        lines += ["", SECTION_AVOID] + _sector_lines(avoid, with_window=False)

    lines += [
        "",
        "기준",
        f"현재가 {quote_asof or '—'} · 직전 종가 {base_close_date or '—'}",
    ]
    if disclaimer:
        lines += ["", disclaimer]
    return "\n".join(lines)


def render_checkup_summary(
    *,
    checks: int,
    sent: int,
    suppressed: int,
    no_signal: int,
    failed: int = 0,
    unknown: bool = False,
) -> str:
    """§8 — 15:40 보유 브리핑 끝에 붙는 **한 줄**.

    **별도 메시지를 만들지 않는다.** 집계 불가는 `0` 으로 위장하지 않고
    `확인 불가` 로 적는다.
    """
    if unknown:
        return "장중 점검 확인 불가"
    parts = [
        f"장중 점검 {checks}회",
        f"알림 {sent}건",
        f"중복 억제 {suppressed}건",
        f"신호 없음 {no_signal}건",
    ]
    if failed:
        parts.append(f"조회 실패 {failed}회")
    return " · ".join(parts)


__all__ = [
    "DISCLAIMER",
    "HEADER",
    "PREVIEW_HEADER",
    "SECTION_AVOID",
    "SECTION_ENTRY",
    "SECTION_HELD",
    "SectionPlan",
    "build_section_plan",
    "render_checkup_summary",
    "render_intraday_alert",
]
