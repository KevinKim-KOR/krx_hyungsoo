"""POC3-ML-02 — Relative Upside Score Validity Gate · 통계 지표 산식.

본 모듈은 순수 통계 함수만 담는다. DB·파일·모델에 접근하지 않는다.
평가 오케스트레이션은 `app/ml_score_validity_eval.py` 에 있다.

PLAN V1 대응:
- §4.1  Spearman rank IC
- §4.2  분위 스프레드
- §4.4  승률
- §4.8  turnover
- §4.9  거래비용 (월별 실측 turnover 에 적용)
- §4.10 bootstrap 계약 [확정 2026-08-29 · 확정사항 3]
        circular moving-block bootstrap · block 6개월 · 2,000회 · seed 42 ·
        percentile 2.5% / 97.5%
- §4.10 Newey-West (3M 중첩본 전용)

신규 의존성 금지 (PLAN §6) — scipy / statsmodels 를 쓰지 않고 표준 라이브러리로
직접 구현한다.
"""

from __future__ import annotations

import math
import random
from typing import Optional, Sequence

# --- bootstrap 계약 (PLAN §4.10 · 확정사항 3) --------------------------------
BOOTSTRAP_BLOCK_MONTHS = 6
BOOTSTRAP_ITERATIONS = 2000
BOOTSTRAP_SEED = 42
BOOTSTRAP_CI_LOW_PCT = 2.5
BOOTSTRAP_CI_HIGH_PCT = 97.5

# 월 단위 시계열이므로 block 길이 6개월 = 관측치 6개.
BOOTSTRAP_BLOCK_LEN = BOOTSTRAP_BLOCK_MONTHS

# --- N-1 negative control 계약 (PLAN §3.3 · 확정사항 4) ----------------------
SHUFFLE_SEED_START = 0
SHUFFLE_SEED_END = 99  # 포함 — 총 100회
SHUFFLE_MEAN_ABS_MAX = 0.01


def mean(values: Sequence[float]) -> Optional[float]:
    """산술 평균. 빈 시퀀스면 None."""
    if not values:
        return None
    return sum(values) / len(values)


def median(values: Sequence[float]) -> Optional[float]:
    """중앙값. 빈 시퀀스면 None."""
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return float(ordered[mid])
    return (float(ordered[mid - 1]) + float(ordered[mid])) / 2.0


def stdev(values: Sequence[float]) -> Optional[float]:
    """표본 표준편차 (n-1). 관측치 2개 미만이면 None."""
    n = len(values)
    if n < 2:
        return None
    m = sum(values) / n
    var = sum((v - m) ** 2 for v in values) / (n - 1)
    return math.sqrt(var)


def percentile(values: Sequence[float], pct: float) -> Optional[float]:
    """선형보간 percentile (numpy 기본 방식과 동일). 빈 시퀀스면 None."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * (pct / 100.0)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(ordered[int(pos)])
    frac = pos - lo
    return float(ordered[lo]) * (1.0 - frac) + float(ordered[hi]) * frac


def _midranks(values: Sequence[float]) -> list[float]:
    """동점은 평균 순위 (midrank). 1-based."""
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """Spearman 순위상관. 동점은 midrank.

    관측치 2개 미만이거나 한쪽이 상수면 None (상관 정의 불가).
    """
    if len(xs) != len(ys):
        raise ValueError("xs / ys 길이가 다릅니다")
    n = len(xs)
    if n < 2:
        return None
    rx = _midranks(xs)
    ry = _midranks(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0.0 or dy == 0.0:
        return None
    return num / (dx * dy)


def t_stat(values: Sequence[float]) -> Optional[float]:
    """mean / (sd / sqrt(n)). PLAN §5 — **참고 수치**이며 판정 기준이 아니다."""
    n = len(values)
    if n < 2:
        return None
    sd = stdev(values)
    m = mean(values)
    if sd is None or m is None or sd == 0.0:
        return None
    return m / (sd / math.sqrt(n))


def circular_block_bootstrap_ci(
    series: Sequence[float],
    *,
    block_len: int = BOOTSTRAP_BLOCK_LEN,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = BOOTSTRAP_SEED,
    low_pct: float = BOOTSTRAP_CI_LOW_PCT,
    high_pct: float = BOOTSTRAP_CI_HIGH_PCT,
) -> Optional[tuple[float, float]]:
    """circular moving-block bootstrap 으로 **평균**의 CI 를 구한다.

    PLAN §4.10 확정 계약: circular moving-block · block 6개월 · 2,000회 ·
    seed 42 · percentile 2.5% / 97.5%.

    circular = 블록 시작점이 끝을 넘으면 앞으로 되감는다 (끝쪽 관측치가 덜
    뽑히는 편향 제거).

    관측치가 2개 미만이면 None.
    """
    n = len(series)
    if n < 2:
        return None
    b = max(1, min(int(block_len), n))
    n_blocks = math.ceil(n / b)
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(iterations):
        total = 0.0
        count = 0
        for _blk in range(n_blocks):
            start = rng.randrange(n)
            for k in range(b):
                if count >= n:
                    break
                total += series[(start + k) % n]
                count += 1
            if count >= n:
                break
        means.append(total / count)
    lo = percentile(means, low_pct)
    hi = percentile(means, high_pct)
    if lo is None or hi is None:
        return None
    return (lo, hi)


def newey_west_t(series: Sequence[float], *, lag: int) -> Optional[float]:
    """평균 = 0 귀무가설의 Newey-West 보정 t. 3M **중첩** 표본 전용.

    Bartlett kernel. 분산이 0 이하로 나오면 None (보정 불가).
    """
    n = len(series)
    if n < 2:
        return None
    m = sum(series) / n
    dev = [v - m for v in series]
    gamma0 = sum(d * d for d in dev) / n
    var = gamma0
    for k in range(1, min(lag, n - 1) + 1):
        gk = sum(dev[i] * dev[i - k] for i in range(k, n)) / n
        var += 2.0 * (1.0 - k / (lag + 1.0)) * gk
    if var <= 0.0:
        return None
    se = math.sqrt(var / n)
    if se == 0.0:
        return None
    return m / se


def quantile_bucket(rank_index: int, count: int, buckets: int) -> int:
    """오름차순 rank_index (0-based) 를 0..buckets-1 분위로. 0 = 최하위."""
    if count <= 0:
        raise ValueError("count 는 1 이상이어야 합니다")
    if buckets <= 0:
        raise ValueError("buckets 는 1 이상이어야 합니다")
    b = int(rank_index * buckets / count)
    return min(b, buckets - 1)


def replaced_fraction(prev: Sequence[str], cur: Sequence[str]) -> Optional[float]:
    """월간 교체 비율 = |cur \\ prev| / |cur|.

    PLAN §4.8. 직전 바스켓이 없으면(첫 달) None — 비용 계산에서 제외한다.

    주의: "포트폴리오 중 새로 사들인 비중" 이다. 대칭차집합을 쓰면 매도·매수를
    한 번씩 이미 센 값이 되어 §4.9 의 `× 2` 와 이중계상된다.
    """
    if not cur:
        return None
    if prev is None:
        return None
    prev_set = set(prev)
    return len([c for c in cur if c not in prev_set]) / len(cur)


def cost_drag(replaced: Optional[float], one_way_bp: float) -> float:
    """월별 비용 = 그 달 실측 교체비율 x 편도비용 x 2 (매도 + 매수).

    PLAN §4.9 — **평균 turnover 가 아니라 월별 실측값**에 적용한다.
    반환 단위는 수익률과 같은 소수 (25bp = 0.0025).
    """
    if replaced is None:
        return 0.0
    return replaced * (one_way_bp / 10000.0) * 2.0


def win_rate(values: Sequence[float]) -> Optional[float]:
    """> 0 인 비율. 빈 시퀀스면 None."""
    if not values:
        return None
    return len([v for v in values if v > 0]) / len(values)


def shuffle_control_verdict(
    permutation_means: Sequence[float],
) -> dict:
    """N-1 negative control 판정 (PLAN §3.3 · 확정사항 4).

    통과 기준:
      - 100개 평균 IC 의 전체 평균 절대값 < 0.01
      - 100개 값의 2.5% ~ 97.5% 구간에 0 포함

    불충족 시 **누수로 단정하지 않고** `metric 구현 이상 의심` 으로 보고한다.
    """
    m = mean(permutation_means)
    lo = percentile(permutation_means, BOOTSTRAP_CI_LOW_PCT)
    hi = percentile(permutation_means, BOOTSTRAP_CI_HIGH_PCT)
    mean_ok = m is not None and abs(m) < SHUFFLE_MEAN_ABS_MAX
    zero_ok = lo is not None and hi is not None and lo <= 0.0 <= hi
    passed = bool(mean_ok and zero_ok)
    return {
        "permutation_count": len(permutation_means),
        "mean_of_means": m,
        "pct_2_5": lo,
        "pct_97_5": hi,
        "mean_abs_below_threshold": mean_ok,
        "interval_contains_zero": zero_ok,
        "passed": passed,
        "verdict": "ok" if passed else "metric 구현 이상 의심",
    }


# --- 분위 / 상위군 / negative control (PLAN §4.2 · §3.3) ---------------------


def quantile_means(
    scored: list[tuple[str, float, float]], buckets: int = 5
) -> dict[int, Optional[float]]:
    """(ticker, score, label) 을 점수 오름차순 분위로 나눠 분위별 평균 label."""
    if not scored:
        return {}
    ordered = sorted(scored, key=lambda x: x[1])
    groups: dict[int, list[float]] = {b: [] for b in range(buckets)}
    n = len(ordered)
    for i, (_ticker, _score, label) in enumerate(ordered):
        groups[quantile_bucket(i, n, buckets)].append(label)
    return {b: (sum(v) / len(v) if v else None) for b, v in groups.items()}


def top_fraction(
    scored: list[tuple[str, float, float]], fraction: float
) -> list[tuple[str, float, float]]:
    """점수 상위 `fraction` 비율. 최소 1건."""
    if not scored:
        return []
    ordered = sorted(scored, key=lambda x: x[1], reverse=True)
    k = max(1, int(round(len(ordered) * fraction)))
    return ordered[:k]


def shuffle_permutation_means(
    per_date: list[tuple[list[float], list[float]]],
    *,
    seed_start: int,
    seed_end: int,
) -> list[float]:
    """라벨을 기준일 안에서 치환한 뒤 permutation 별 평균 IC 를 만든다.

    `per_date` 는 (scores, labels) 쌍의 리스트. 각 seed 마다 모든 기준일의 라벨을
    셔플하고 IC 를 구해 평균낸다. 총 `seed_end - seed_start + 1` 개 값 반환.
    """
    out: list[float] = []
    for seed in range(seed_start, seed_end + 1):
        rng = random.Random(seed)
        ics: list[float] = []
        for scores, labels in per_date:
            shuffled = list(labels)
            rng.shuffle(shuffled)
            value = spearman(scores, shuffled)
            if value is not None:
                ics.append(value)
        if ics:
            out.append(sum(ics) / len(ics))
    return out
