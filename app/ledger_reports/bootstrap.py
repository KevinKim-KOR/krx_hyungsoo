"""POC5-04 — R1 날짜 묶음 moving-block bootstrap(비원형) · 평균의 percentile 95% 구간.

설계 개정 1 §6 · PLAN §1-5.

```text
날짜 축      시작일 ~ 종료일의 운영 거래일 전부(알림 없는 날 = 빈 묶음 · 0 으로 채우지 않음)
묶음        사건 날짜(runtime_date_kst) 마다 그날의 모든 관측(item · ticker)이 함께 움직인다
블록        길이 b = max(5, horizon) · 시작 = [0, N-b] 균등 · 끝과 처음을 잇지 않는다(비원형)
재표본      ceil(N/b) 블록을 이어 N 날짜로 자른다 → 그 날짜 관측을 모두 모은 평균
보류        성숙 관측이 있는 서로 다른 날짜 < 2b → INSUFFICIENT_SAMPLE(구간 NULL)
계산 불가    관측 0 인 재표본이 하나라도 있으면 RESAMPLE_UNDEFINED(구간 NULL · 건수 표시)
분위        ml_score_validity_metrics.percentile((n-1)p 선형 보간) · 난수 random.Random(seed)
```
"""

from __future__ import annotations

import math
import random
from typing import Any, Mapping, Sequence

from app.ml_score_validity_metrics import percentile

ITERATIONS = 1000
SEED = 0
LOW_PCT = 2.5
HIGH_PCT = 97.5


def block_days(horizon: int) -> int:
    return max(5, int(horizon))


def date_block_ci(
    days: Sequence[str],
    obs_by_day: Mapping[str, Sequence[float]],
    *,
    block: int,
    iterations: int = ITERATIONS,
    seed: int = SEED,
) -> dict[str, Any]:
    if int(iterations) < 1:
        # 재표집을 한 번도 하지 않고 OK 를 내지 않는다.
        raise ValueError("iterations 는 1 이상이어야 한다")
    n_days = len(days)
    n_obs_days = sum(1 for d in days if obs_by_day.get(d))
    out: dict[str, Any] = {
        "method": "moving_block_non_circular_date_bundles",
        "statistic": "mean",
        "block_days": block,
        "iterations": iterations,
        "seed": seed,
        "n_days": n_days,
        "n_signal_dates_with_matured": n_obs_days,
        "low": None,
        "high": None,
        "undefined_resamples": 0,
        "status": "OK",
    }
    if n_obs_days < 2 * block or n_days < block:
        out["status"] = "INSUFFICIENT_SAMPLE"
        return out
    rng = random.Random(seed)
    n_blocks = math.ceil(n_days / block)
    means: list[float] = []
    undefined = 0
    for _ in range(iterations):
        total = 0.0
        count = 0
        picked = 0
        for _b in range(n_blocks):
            first = rng.randrange(n_days - block + 1)
            for k in range(block):
                if picked >= n_days:
                    break
                vals = obs_by_day.get(days[first + k], ())
                total += sum(vals)
                count += len(vals)
                picked += 1
        if count == 0:
            undefined += 1
            continue
        means.append(total / count)
    out["undefined_resamples"] = undefined
    if undefined:
        out["status"] = "RESAMPLE_UNDEFINED"  # 정상 구간으로 위장하지 않는다
        return out
    out["low"] = percentile(means, LOW_PCT)
    out["high"] = percentile(means, HIGH_PCT)
    return out
