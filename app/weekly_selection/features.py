"""POC6-11 입력 30열 · 정답(60거래일 상대성과 순위) · 학습 표본 · 분기 모델 배정.

설계 §3 · §4 · PLAN §6(판정 §4 · §5).

```text
입력   w = 5 · 20 · 60 · 120 마다 RET · MA_GAP · RETURN_STD · CLOSE_PEAK_GAP ·
       VOLUME_RATIO · VOLUME_CV(24열) + 봉 6열(O*/I_prev−1 · I/O*−1 · (H*−L*)/I_prev ·
       (I−L*)/(H*−L*) · (H*−max(O*,I))/I_prev · (min(O*,I)−L*)/I_prev)
       결측 = 값 없음(None) + 사유(DIV0 · NO_TRADE) · 0 · 중앙값으로 채우지 않음
정답   e = t+2 · q = e+59 · z = log(I_q/O*_e) − log(I^b_q/O*^b_e) · 같은 날 정답 가능 집합의 평균 순위 →
       y = (순위−1)/(N−1) − 0.5 · 결측 · 연결 실패 · 진입 시가 0 = 정답 없음
학습   날짜 사용 = 정답 가능 ≥ 20 · 자격의 95% 이상 · 분기 cutoff 에서 5달력년 · q ≤ cutoff − 5시장거래일
       가중치 w = 전체 행 / (날짜 수 × 그날 행 수) · 모델 배정 = cutoff ≤ 신호일 D 인 가장 최근 판
```
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from app.weekly_selection.data import BENCH, MIN_ELIGIBLE, CheckRequired, Panel

WINDOWS = (5, 20, 60, 120)
BLOCK = ("RET", "MA_GAP", "RETURN_STD", "CLOSE_PEAK_GAP", "VOLUME_RATIO", "VOLUME_CV")
CANDLES = (
    "OPEN_GAP",
    "CLOSE_OPEN",
    "RANGE",
    "CLOSE_POS",
    "UPPER_SHADOW",
    "LOWER_SHADOW",
)
COLUMNS = tuple(f"{b}_{w}" for w in WINDOWS for b in BLOCK) + CANDLES
EXEC_LAG = 2
HORIZON = 60
USABLE_MIN, USABLE_SHARE = 20, 0.95
TRAIN_YEARS = 5
MATURE_GAP = 5


def _div(a: float, b: float) -> Optional[float]:
    if b == 0 or not math.isfinite(b):
        return None
    v = a / b
    return v if math.isfinite(v) else None


def feature_row(
    p: Panel, j: int, i: int
) -> tuple[list[Optional[float]], dict[str, str]]:
    """종목 j · 신호 i 의 30열. 자격(연속 126행)이 창을 보장한다고 가정하지 않고 값마다 다시 확인한다."""
    I, V = p.I[j], p.V[j]  # noqa: E741
    vals: list[Optional[float]] = []
    why: dict[str, str] = {}
    it = I[i]
    for w in WINDOWS:
        win = I[i - w + 1 : i + 1]  # noqa: E203
        back = I[i - w]
        prev = I[i - w : i + 1]  # noqa: E203
        if not (
            np.isfinite(win).all()
            and np.isfinite(back)
            and back > 0
            and (win > 0).all()
        ):
            raise CheckRequired(f"{p.codes[j]} {p.axis[i]} 종가 창 손상(w={w})")
        rets = prev[1:] / prev[:-1] - 1.0
        vwin = V[i - w + 1 : i + 1]  # noqa: E203
        vback = V[i - w : i]  # noqa: E203
        if not (np.isfinite(vwin).all() and np.isfinite(vback).all()):
            raise CheckRequired(f"{p.codes[j]} {p.axis[i]} 거래량 창 손상(w={w})")
        row = [
            it / back - 1.0,
            it / win.mean() - 1.0,
            float(np.std(rets)),
            it / win.max() - 1.0,
            _div(V[i], vback.mean()),
            _div(float(np.std(vwin)), vwin.mean()),
        ]
        for name, v in zip(BLOCK, row):
            if v is None:
                why[f"{name}_{w}"] = "DIV0"
        vals.extend(row)
    prev_close = I[i - 1]
    ro, rh, rl, rc = p.raw_open[j, i], p.raw_high[j, i], p.raw_low[j, i], p.C[j, i]
    if V[i] == 0 and ro == 0:
        for name in CANDLES:
            why[name] = "NO_TRADE"
        vals.extend([None] * len(CANDLES))
    else:
        # 관계 검사 · 같은 날 비율은 원시 O/H/L/C 로(합성 = 원시 × 같은 날 배율 f = I/C 라 순서 · 비율이 같고,
        # 합성값끼리 비교하면 종가 = 저가 · 고가인 날 1ulp 오차로 정상 행을 손상으로 잘못 본다 · 검토 r1)
        if not (
            np.isfinite([ro, rh, rl, rc, p.O[j, i]]).all()
            and ro > 0
            and rl > 0
            and rc > 0
            and rh >= max(ro, rc)
            and rl <= min(ro, rc)
        ):
            raise CheckRequired(f"{p.codes[j]} {p.axis[i]} 거래일 원시 고저 관계 손상")
        f = it / rc
        candle = [
            p.O[j, i] / prev_close - 1.0,  # O*/I_prev − 1
            rc / ro - 1.0,  # I/O* − 1
            (rh - rl) * f / prev_close,  # (H*−L*)/I_prev
            _div(rc - rl, rh - rl),  # (I−L*)/(H*−L*)
            (rh - max(ro, rc)) * f / prev_close,  # (H*−max(O*,I))/I_prev
            (min(ro, rc) - rl) * f / prev_close,  # (min(O*,I)−L*)/I_prev
        ]
        for name, v in zip(CANDLES, candle):
            if v is None:
                why[name] = "DIV0"
        vals.extend(candle)
    return [None if v is None else float(v) for v in vals], why


def label_ok(p: Panel, j: int, i: int, b: int) -> bool:
    """정답 가용성만(값은 보지 않음) — e · q 행 · 연결값 · 같은 구간 · e 원시 시가 > 0 · 거래량 > 0 · 069500 도."""
    e, q = i + EXEC_LAG, i + EXEC_LAG + HORIZON - 1
    if q >= len(p.axis):
        return False
    for k in (j, b):
        if not (
            p.has_row[k, e]
            and p.has_row[k, q]
            and np.isfinite(p.I[k, q])
            and p.I[k, q] > 0
        ):
            return False
        if p.seg[k, e] != p.seg[k, q] or not (
            p.raw_open[k, e] > 0
            and p.V[k, e] > 0
            and np.isfinite(p.O[k, e])
            and p.O[k, e] > 0
        ):
            return False
    return True


def label_z(p: Panel, j: int, i: int, b: int) -> Optional[float]:
    """z = log(I_q/O*_e) − log(I^b_q/O*^b_e). 정답 불가면 None(0 · 이월로 채우지 않음)."""
    if not label_ok(p, j, i, b):
        return None
    e, q = i + EXEC_LAG, i + EXEC_LAG + HORIZON - 1
    return math.log(p.I[j, q] / p.O[j, e]) - math.log(p.I[b, q] / p.O[b, e])


def availability(
    p: Panel, members: dict[int, list[int]]
) -> tuple[dict[int, int], dict[int, bool]]:
    """잠금용 — 신호별 정답 가능 수 · 학습 사용 가능(정답 크기 · 특징 값은 계산하지 않음)."""
    b = p.ci[BENCH]
    count, usable = {}, {}
    for i in sorted(members):
        js = members[i]
        n = sum(1 for j in js if label_ok(p, j, i, b))
        count[i] = n
        usable[i] = (
            len(js) >= MIN_ELIGIBLE and n >= USABLE_MIN and n >= USABLE_SHARE * len(js)
        )
    return count, usable


def quarter_rows(
    axis: list[str],
    members: dict[int, list[int]],
    count: dict[int, int],
    usable: dict[int, bool],
    cutoff_idx: int,
) -> list[int]:
    """잠금용 분기 학습 신호 위치(training_rows 와 같은 창 · 성숙 · 사용 조건 · 행 수 = 정답 가능 수 합)."""
    cut = dt.date.fromisoformat(axis[cutoff_idx])
    lo = cut.replace(year=cut.year - TRAIN_YEARS).isoformat()
    return [
        i
        for i in sorted(members)
        if lo < axis[i] <= axis[cutoff_idx]
        and i + EXEC_LAG + HORIZON - 1 <= cutoff_idx - MATURE_GAP
        and usable.get(i)
        and count.get(i, 0) > 0
    ]


def rank_y(z: dict[int, float]) -> dict[int, float]:
    """오름차순 평균 동점 순위 → y = (순위−1)/(N−1) − 0.5(N ≥ 2)."""
    items = sorted(z.items(), key=lambda kv: kv[1])
    n = len(items)
    out: dict[int, float] = {}
    k = 0
    while k < n:
        m = k
        while m + 1 < n and items[m + 1][1] == items[k][1]:
            m += 1
        avg = (k + m) / 2 + 1
        for t in range(k, m + 1):
            out[items[t][0]] = (avg - 1) / (n - 1) - 0.5 if n > 1 else 0.0
        k = m + 1
    return out


@dataclass
class Table:
    """자격 행 표(신호일 오름차순 · 종목 코드 오름차순)."""

    sig: list[int]
    rows: list[tuple[int, int]]  # (신호 위치, 종목 위치)
    X: list[list[Optional[float]]]
    missing: list[dict[str, str]]
    z: list[Optional[float]]
    y: list[Optional[float]]
    usable: dict[int, bool]
    label_count: dict[int, int]


def build_table(p: Panel, members: dict[int, list[int]]) -> Table:
    b = p.ci[BENCH]
    sig = sorted(members)
    rows, X, miss, zs, ys = [], [], [], [], []
    usable: dict[int, bool] = {}
    label_count: dict[int, int] = {}
    for i in sig:
        js = sorted(members[i], key=lambda j: p.codes[j])
        zd = {j: z for j in js if (z := label_z(p, j, i, b)) is not None}
        yd = rank_y(zd)
        label_count[i] = len(zd)
        usable[i] = (
            len(js) >= MIN_ELIGIBLE
            and len(zd) >= USABLE_MIN
            and len(zd) >= USABLE_SHARE * len(js)
        )
        for j in js:
            v, why = feature_row(p, j, i)
            rows.append((i, j))
            X.append(v)
            miss.append(why)
            zs.append(zd.get(j))
            ys.append(yd.get(j))
    return Table(
        sig=sig,
        rows=rows,
        X=X,
        missing=miss,
        z=zs,
        y=ys,
        usable=usable,
        label_count=label_count,
    )


def quarter_cutoffs(
    axis: list[str], first: tuple[int, int], last: tuple[int, int]
) -> list[dict]:
    """분기마다 cutoff = 분기 시작 전 마지막 시장 거래일."""
    out = []
    y, q = first
    while (y, q) <= last:
        start = dt.date(y, 3 * (q - 1) + 1, 1).isoformat()
        ci = max(i for i, d in enumerate(axis) if d < start)
        out.append({"id": f"{y}Q{q}", "cutoff": axis[ci], "cutoff_idx": ci})
        q += 1
        if q == 5:
            y, q = y + 1, 1
    return out


def training_rows(t: Table, axis: list[str], cutoff_idx: int) -> list[int]:
    """cutoff 에서 5달력년 안 · q ≤ cutoff − 5시장거래일 · 사용 가능 날짜 · 정답 있는 행의 표 위치."""
    cut = dt.date.fromisoformat(axis[cutoff_idx])
    lo = cut.replace(year=cut.year - TRAIN_YEARS).isoformat()
    out = []
    for r, (i, _j) in enumerate(t.rows):
        if not (lo < axis[i] <= axis[cutoff_idx]):
            continue
        if i + EXEC_LAG + HORIZON - 1 > cutoff_idx - MATURE_GAP or not t.usable.get(i):
            continue
        if t.y[r] is not None:
            out.append(r)
    return out


def weights(t: Table, rows: list[int]) -> list[float]:
    """w = 전체 학습 행 / (학습 날짜 수 × 그날 학습 행 수) — 날짜 합이 같고 평균 1."""
    per: dict[int, int] = {}
    for r in rows:
        per[t.rows[r][0]] = per.get(t.rows[r][0], 0) + 1
    n, d = len(rows), len(per)
    return [n / (d * per[t.rows[r][0]]) for r in rows]


def model_for(signal_idx: int, cutoffs: list[dict]) -> Optional[dict]:
    """cutoff ≤ 신호일인 가장 최근 판(판정 §4). 없으면 None."""
    ok = [c for c in cutoffs if c["cutoff_idx"] <= signal_idx]
    return ok[-1] if ok else None
