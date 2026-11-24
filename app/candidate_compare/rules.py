"""두 기준 · 오른 주 — 과거 비교(봉인)와 이번 주 화면(PC 시세 DB)이 같은 함수를 쓴다(PLAN §2-3 '같은 뜻').

```text
오른 주   네 구간마다 끝 ÷ 시작 − 1 > 1e-9 = 오름 · 그 이하(변화 없음 포함) = 오름 아님
          주 마감 값이 하나라도 없거나 0 이하 · 비유한 = None(미확인 · 공통 후보군에서 빠짐)
순서      1개월(반올림 전) 내림차순 · 같으면 종목코드 오름차순(운영 `pc_etf_compare_summary` 와 같음)
대조 A    공통 후보군을 위 순서로 세워 위 3
시험 B    1개월 > 0 인 후보를 (오른 주 내림차순 · 1개월 순서) → 위 3 · 모자라면 남은 공통 후보의 1개월 순서로 채움
선택 변경 종목 집합으로 비교(순서만 바뀐 것은 변경 아님 · 판정 §2)
```
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from app.candidate_compare.protocol import N_INTERVALS, N_PICK, UP_EPS


@dataclass(frozen=True)
class Cand:
    """한 후보. `ret` = 1개월 수익률(단위는 쓰는 쪽 — 부호 · 순서만 본다) · `up` = 오른 주 수(None = 미확인)."""

    code: str
    ret: float
    up: Optional[int]


def _ok(v: Optional[float]) -> bool:
    return v is not None and math.isfinite(v) and v > 0


def interval_changes(closes: Sequence[Optional[float]]) -> list[Optional[float]]:
    """네 구간의 변화율(끝 ÷ 시작 − 1) — 두 값 중 하나라도 없으면 그 구간 None."""
    out: list[Optional[float]] = []
    for a, b in zip(closes, closes[1:]):
        out.append(float(b) / float(a) - 1.0 if _ok(a) and _ok(b) else None)
    return out


def up_weeks(closes: Sequence[Optional[float]]) -> Optional[int]:
    """주 마감 5번 → 오른 주 수(0 ~ 4) · 값이 하나라도 없으면 None."""
    if len(closes) != N_INTERVALS + 1 or not all(_ok(c) for c in closes):
        return None
    return sum(1 for ch in interval_changes(closes) if ch is not None and ch > UP_EPS)


def move_of(change: Optional[float]) -> str:
    """한 구간 표시 — up · down · flat · none(값 없음)."""
    if change is None:
        return "none"
    if change > UP_EPS:
        return "up"
    if change < -UP_EPS:
        return "down"
    return "flat"


def order_key(c: Cand) -> tuple[float, str]:
    return (-c.ret, c.code)


def pick_a(common: Sequence[Cand]) -> list[str]:
    """대조 A — 1개월 순서 위 3."""
    return [c.code for c in sorted(common, key=order_key)[:N_PICK]]


def pick_b(common: Sequence[Cand]) -> list[str]:
    """시험 B — 1개월 > 0 중 오른 주 내림차순 → 1개월 순서 · 모자라면 1개월 순서로 채움."""
    if any(c.up is None for c in common):
        raise ValueError("공통 후보군에 오른 주 미확인 후보가 있음")
    pos = sorted(
        (c for c in common if c.ret > 0), key=lambda c: (-c.up, -c.ret, c.code)
    )
    picks = [c.code for c in pos[:N_PICK]]
    if len(picks) < N_PICK:
        rest = [c.code for c in sorted(common, key=order_key) if c.code not in picks]
        need = N_PICK - len(picks)
        picks += rest[:need]
    return picks


def same_selection(a: Sequence[str], b: Sequence[str]) -> bool:
    """종목 집합이 같으면 같은 선택(순서만 바뀐 것은 변경 아님)."""
    return set(a) == set(b)


def changed_count(now: Sequence[str], prev: Optional[Sequence[str]]) -> Optional[int]:
    """교체 부담 — 지난 신호 주 목록에서 빠진 종목 수(0 ~ 3) · 지난 목록이 없으면 None."""
    if prev is None:
        return None
    return len(set(prev) - set(now))
