"""POC6-21 절대 정답 · 날짜 사용 규칙 — 판정 §A-2(Q1 ~ Q3) · 통합 설계 §4.

```text
정답   e = t+2 · q = e+59 · y = log(I_q/O*_e) — ETF 자체 자료에서 직접(K 차감 · 단면 순위 · 중심화 없음)
가용   H1 label_ok 에서 069500 의존만 뺀다: ETF 의 e · q 행 · 연결값 > 0 · 같은 연결 구간 · e 원시 시가 · 거래량 > 0
       · O*_e 유한 > 0 · q 가 축 밖이면 없음(결측을 건너뛴 60행으로 평가일을 앞당기지 않음)
날짜   자격 20종 이상 · 그 자격 중 유효 정답 20개 이상 · 유효 정답/자격 95% 이상(H1 상수 그대로)
표     H1 build_table 의 행 · 30열 · 결측 사유를 그대로 두고 정답 · 사용 가능 · 정답 수만 절대 정답으로 바꾼다
```
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from app.weekly_selection import features as F
from app.weekly_selection.data import MIN_ELIGIBLE, Panel


def label_ok(p: Panel, j: int, i: int) -> bool:
    """가용성만(값은 보지 않음) — ETF 자체 행만 본다(069500 미래 행 요구 없음 · 판정 Q2 (b))."""
    e, q = i + F.EXEC_LAG, i + F.EXEC_LAG + F.HORIZON - 1
    if q >= len(p.axis):
        return False
    if not (p.has_row[j, e] and p.has_row[j, q] and np.isfinite(p.I[j, q])):
        return False
    return bool(
        p.I[j, q] > 0
        and p.seg[j, e] == p.seg[j, q]
        and p.raw_open[j, e] > 0
        and p.V[j, e] > 0
        and np.isfinite(p.O[j, e])
        and p.O[j, e] > 0
    )


def label(p: Panel, j: int, i: int) -> Optional[float]:
    """y = log(I_q/O*_e). 정답 불가면 None(0 · 이월로 채우지 않음)."""
    if not label_ok(p, j, i):
        return None
    e, q = i + F.EXEC_LAG, i + F.EXEC_LAG + F.HORIZON - 1
    return math.log(p.I[j, q] / p.O[j, e])


def _usable(eligible: int, n: int) -> bool:
    return (
        eligible >= MIN_ELIGIBLE
        and n >= F.USABLE_MIN
        and n >= F.USABLE_SHARE * eligible
    )


def availability(
    p: Panel, members: dict[int, list[int]]
) -> tuple[dict[int, int], dict[int, bool]]:
    """잠금용 — 신호별 절대 정답 가능 수 · 학습 사용 가능(정답 크기 · 특징 값은 계산하지 않음)."""
    count, usable = {}, {}
    for i in sorted(members):
        js = members[i]
        n = sum(1 for j in js if label_ok(p, j, i))
        count[i], usable[i] = n, _usable(len(js), n)
    return count, usable


def table(p: Panel, t: F.Table) -> F.Table:
    """H1 표(행 · 30열 · 결측)에 절대 정답을 얹은 새 표 — z = y = 절대 정답(H1 순위 정답에서 복원하지 않음)."""
    ys: list[Optional[float]] = []
    count: dict[int, int] = {}
    members: dict[int, int] = {}
    for i, j in t.rows:
        y = label(p, j, i)
        ys.append(y)
        members[i] = members.get(i, 0) + 1
        count[i] = count.get(i, 0) + (y is not None)
    usable = {i: _usable(members.get(i, 0), count.get(i, 0)) for i in t.sig}
    return F.Table(
        sig=t.sig,
        rows=t.rows,
        X=t.X,
        missing=t.missing,
        z=ys,
        y=ys,
        usable=usable,
        label_count={i: count.get(i, 0) for i in t.sig},
    )
