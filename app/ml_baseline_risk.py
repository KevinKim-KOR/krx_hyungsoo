"""ML Baseline v0 — Risk (위험 구간) 룩백 baseline (2026-06-11).

지시문 §8 — 시장 risk feature 가 이후 3/5/10d 시장 수익률 / 5/10d drawdown /
5d down_ratio 와 관련이 있었는지 market composite risk score 의 tercile
(사용자 결정 — 상하 1/3) 비교로 룩백 검증.

조정장 label / 위험 threshold 0건. 위험 알림 X.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.ml_baseline_targets import (
    MAX_HORIZON,
    RISK_DOWN_RATIO_HORIZON,
    RISK_DRAWDOWN_HORIZONS,
    RISK_RETURN_HORIZONS,
    RiskTargetRow,
)

# 사용자 결정 — tercile (상하 1/3).
RISK_TERCILE = 1.0 / 3.0

# 7축 risk proxy + 보조 axes (지시문 §8.3) — composite score 입력.
RISK_COMPOSITE_AXES = [
    # 클수록 위험 (DESC rank: 큰 값 = 위험).
    ("volatility_20d_market_proxy", True),
    ("volatility_expansion_20d", True),
    ("down_day_volume_ratio", True),
    ("nav_discount_abs_avg", True),
    # 작을수록 위험 (ASC rank: 작은(-) 값 = 위험).
    ("kodex200_return_5d", False),
    ("kodex200_return_20d", False),
    ("etf_universe_median_return_5d", False),
    ("distance_from_20d_high", False),
    ("drawdown_20d_market_proxy", False),
    # 클수록 위험.
    ("etf_universe_down_ratio", True),
    ("large_negative_day_proxy", True),
    ("short_term_weakness_proxy", True),
    ("breadth_deterioration_proxy", True),
]

SAMPLE_ASOF_LIMIT = 5


@dataclass
class _RiskAsofRow:
    asof: str
    values: dict[str, Optional[float]]
    composite_score: Optional[float] = None


def _load_market_risk_rows(con: sqlite3.Connection) -> list[_RiskAsofRow]:
    cols = [a for a, _ in RISK_COMPOSITE_AXES]
    select = ", ".join(cols)
    cur = con.execute(
        f"SELECT asof, {select} FROM market_risk_feature_daily ORDER BY asof"
    )
    out: list[_RiskAsofRow] = []
    for r in cur.fetchall():
        asof = str(r[0])
        vals: dict[str, Optional[float]] = {}
        for i, col in enumerate(cols, start=1):
            vals[col] = float(r[i]) if r[i] is not None else None
        out.append(_RiskAsofRow(asof=asof, values=vals))
    return out


def _compute_composite_scores(rows: list[_RiskAsofRow]) -> None:
    """asof 별 composite risk score 부여 — axes 별 ASC/DESC rank 평균.

    높을수록 위험. 누락된 axis 는 skip.
    """
    n = len(rows)
    if n == 0:
        return
    # axis 별 rank 사전 산출 (asof 가 universe).
    axis_ranks: dict[str, dict[int, float]] = {}
    for axis, is_higher_risk in RISK_COMPOSITE_AXES:
        pairs = [
            (i, rows[i].values.get(axis))
            for i in range(n)
            if rows[i].values.get(axis) is not None
        ]
        if not pairs:
            continue
        # is_higher_risk=True → DESC sort (큰 값 위쪽 rank=1).
        pairs.sort(key=lambda p: p[1], reverse=is_higher_risk)
        ranks: dict[int, float] = {}
        for r, (i, _) in enumerate(pairs):
            ranks[i] = float(r + 1)
        axis_ranks[axis] = ranks

    for i in range(n):
        present_ranks = [
            ax_ranks[i] for ax_ranks in axis_ranks.values() if i in ax_ranks
        ]
        if len(present_ranks) >= 3:  # 최소 3 axis 이상 rank 있는 경우만.
            # 낮을수록 위험 (rank=1 이 가장 위험) → 부호 반전: score 가 클수록 위험.
            rows[i].composite_score = -(sum(present_ranks) / len(present_ranks))


# ─── public ──────────────────────────────────────────────────────────


@dataclass
class RiskBaselineResult:
    status: str
    evaluated_days: int
    target_horizons: dict[str, list[int]] = field(default_factory=dict)
    high_risk_group_future_return: dict[str, Optional[float]] = field(
        default_factory=dict
    )
    high_risk_group_future_drawdown: dict[str, Optional[float]] = field(
        default_factory=dict
    )
    low_risk_group_future_return: dict[str, Optional[float]] = field(
        default_factory=dict
    )
    low_risk_group_future_drawdown: dict[str, Optional[float]] = field(
        default_factory=dict
    )
    high_minus_low_return: dict[str, Optional[float]] = field(default_factory=dict)
    drawdown_capture_rate: dict[str, Optional[float]] = field(default_factory=dict)
    high_risk_group_future_down_ratio_5d: Optional[float] = None
    low_risk_group_future_down_ratio_5d: Optional[float] = None
    # 지시문 §8.4 — 단순 baseline 비교 (composite v0 와 별도).
    simple_baselines: dict[str, dict[str, Optional[float]]] = field(
        default_factory=dict
    )
    sample_asof_results: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def evaluate_risk_baseline(
    db_path: Path,
    risk_targets: list[RiskTargetRow],
) -> RiskBaselineResult:
    warnings: list[str] = []
    errors: list[str] = []

    target_by_asof = {t.asof: t for t in risk_targets}
    eligible_asofs = sorted(target_by_asof.keys())
    # horizon tail 제거.
    if len(eligible_asofs) > MAX_HORIZON:
        eligible_asofs = eligible_asofs[:-MAX_HORIZON]
    else:
        warnings.append(
            f"risk target 의 asof 수({len(eligible_asofs)})가 "
            f"MAX_HORIZON({MAX_HORIZON}) 이하 — 평가 가능 거래일 0"
        )

    if not eligible_asofs:
        return RiskBaselineResult(
            status="insufficient_history",
            evaluated_days=0,
            target_horizons={
                "return": list(RISK_RETURN_HORIZONS),
                "drawdown": list(RISK_DRAWDOWN_HORIZONS),
                "down_ratio": [RISK_DOWN_RATIO_HORIZON],
            },
            warnings=warnings,
            errors=errors,
        )

    with sqlite3.connect(str(db_path)) as con:
        all_rows = _load_market_risk_rows(con)
    if not all_rows:
        errors.append("market_risk_feature_daily 가 비어있음")
        return RiskBaselineResult(
            status="error",
            evaluated_days=0,
            target_horizons={
                "return": list(RISK_RETURN_HORIZONS),
                "drawdown": list(RISK_DRAWDOWN_HORIZONS),
                "down_ratio": [RISK_DOWN_RATIO_HORIZON],
            },
            warnings=warnings,
            errors=errors,
        )
    _compute_composite_scores(all_rows)

    # eligible 범위 + composite_score 있는 행만.
    eligible_rows = [
        r
        for r in all_rows
        if r.asof in set(eligible_asofs) and r.composite_score is not None
    ]
    if len(eligible_rows) < 6:  # tercile 분할 위한 최소.
        warnings.append(
            f"composite_score 산출 가능 asof 가 {len(eligible_rows)}건 — tercile 분할 어려움"
        )
        return RiskBaselineResult(
            status="insufficient_history",
            evaluated_days=len(eligible_rows),
            target_horizons={
                "return": list(RISK_RETURN_HORIZONS),
                "drawdown": list(RISK_DRAWDOWN_HORIZONS),
                "down_ratio": [RISK_DOWN_RATIO_HORIZON],
            },
            warnings=warnings,
            errors=errors,
        )

    # tercile 분할 (composite_score DESC — 높을수록 위험).
    sorted_rows = sorted(eligible_rows, key=lambda r: r.composite_score, reverse=True)
    n = len(sorted_rows)
    k = max(1, int(n * RISK_TERCILE))
    high_asofs = {r.asof for r in sorted_rows[:k]}
    low_asofs = {r.asof for r in sorted_rows[-k:]}

    def _avg_target(asofs: set[str], field_name: str) -> Optional[float]:
        vals = []
        for a in asofs:
            t = target_by_asof.get(a)
            if t is None:
                continue
            v = getattr(t, field_name)
            if v is not None:
                vals.append(v)
        if not vals:
            return None
        return sum(vals) / len(vals)

    high_ret: dict[str, Optional[float]] = {}
    low_ret: dict[str, Optional[float]] = {}
    high_dd: dict[str, Optional[float]] = {}
    low_dd: dict[str, Optional[float]] = {}
    diff: dict[str, Optional[float]] = {}
    capture: dict[str, Optional[float]] = {}

    for h in RISK_RETURN_HORIZONS:
        k_key = f"{h}d"
        hr = _avg_target(high_asofs, f"future_kodex200_return_{h}d")
        lr = _avg_target(low_asofs, f"future_kodex200_return_{h}d")
        high_ret[k_key] = hr
        low_ret[k_key] = lr
        if hr is not None and lr is not None:
            diff[k_key] = hr - lr

    for h in RISK_DRAWDOWN_HORIZONS:
        k_key = f"{h}d"
        hd = _avg_target(high_asofs, f"future_market_drawdown_{h}d")
        ld = _avg_target(low_asofs, f"future_market_drawdown_{h}d")
        high_dd[k_key] = hd
        low_dd[k_key] = ld
        # drawdown_capture_rate: high group 의 worst drawdown 이 전체 worst 의 몇 % 인지.
        all_dd = _avg_target(set(eligible_asofs), f"future_market_drawdown_{h}d")
        if hd is not None and all_dd is not None and all_dd < 0:
            capture[k_key] = (
                hd / all_dd
            )  # 둘 다 음수 → ratio 양수, >1 = high group 이 더 큰 낙폭.
        else:
            capture[k_key] = None

    high_dr = _avg_target(high_asofs, "future_universe_down_ratio_5d")
    low_dr = _avg_target(low_asofs, "future_universe_down_ratio_5d")

    # ─ 지시문 §8.4 단순 baseline 비교 3종 ─
    # 각 axis 의 top tercile (가장 위험한 1/3) asof 의 future drawdown_10d /
    # future_kodex200_return_5d 평균. composite v0 와 별도로 보고.
    simple_baselines = _compute_simple_risk_baselines(eligible_rows, target_by_asof)

    sample_indices = _pick_sample_indices(len(sorted_rows), SAMPLE_ASOF_LIMIT)
    samples: list[dict[str, Any]] = []
    for idx in sample_indices:
        r = sorted_rows[idx]
        t = target_by_asof.get(r.asof)
        samples.append(
            {
                "asof": r.asof,
                "composite_score": r.composite_score,
                "future_kodex200_return_5d": (
                    t.future_kodex200_return_5d if t else None
                ),
                "future_market_drawdown_10d": (
                    t.future_market_drawdown_10d if t else None
                ),
                "future_universe_down_ratio_5d": (
                    t.future_universe_down_ratio_5d if t else None
                ),
            }
        )

    status = "ok" if not warnings else "warn"
    return RiskBaselineResult(
        status=status,
        evaluated_days=len(eligible_rows),
        target_horizons={
            "return": list(RISK_RETURN_HORIZONS),
            "drawdown": list(RISK_DRAWDOWN_HORIZONS),
            "down_ratio": [RISK_DOWN_RATIO_HORIZON],
        },
        high_risk_group_future_return=high_ret,
        high_risk_group_future_drawdown=high_dd,
        low_risk_group_future_return=low_ret,
        low_risk_group_future_drawdown=low_dd,
        high_minus_low_return=diff,
        drawdown_capture_rate=capture,
        high_risk_group_future_down_ratio_5d=high_dr,
        low_risk_group_future_down_ratio_5d=low_dr,
        simple_baselines=simple_baselines,
        sample_asof_results=samples,
        warnings=warnings,
        errors=errors,
    )


def _pick_sample_indices(n: int, k: int) -> list[int]:
    if n <= k:
        return list(range(n))
    step = (n - 1) / (k - 1)
    return [int(round(i * step)) for i in range(k)]


# 지시문 §8.4 — 단순 baseline 3종 (composite v0 와 별도 보고).
# 각 axis 는 (column_name, is_higher_risk) — composite 와 동일한 방향 약속.
SIMPLE_RISK_BASELINE_AXES = [
    # 단순 5일 시장 수익률 기준 (작을수록 위험).
    ("kodex200_return_5d", False),
    # 단순 20일 drawdown 기준 (작을수록 위험; market proxy 음수일수록 깊은 낙폭).
    ("drawdown_20d_market_proxy", False),
    # 단순 시장폭 악화 기준 (down_ratio 클수록 위험).
    ("etf_universe_down_ratio", True),
]


def _compute_simple_risk_baselines(
    eligible_rows: list[_RiskAsofRow],
    target_by_asof: dict[str, "RiskTargetRow"],
) -> dict[str, dict[str, Optional[float]]]:
    """각 axis 의 top tercile (위험 상위 1/3) asof 의 future target 평균.

    composite v0 와 별도 — 본 baseline 이 단일 단순 기준으로도 high-risk asof
    의 future drawdown 이 더 깊었는지 보여준다.
    """
    out: dict[str, dict[str, Optional[float]]] = {}
    for axis, is_higher_risk in SIMPLE_RISK_BASELINE_AXES:
        pairs = [
            (r.asof, r.values.get(axis))
            for r in eligible_rows
            if r.values.get(axis) is not None
        ]
        if len(pairs) < 6:
            out[axis] = {
                "high_risk_future_market_drawdown_10d": None,
                "high_risk_future_kodex200_return_5d": None,
                "low_risk_future_market_drawdown_10d": None,
                "low_risk_future_kodex200_return_5d": None,
                "evaluated_asof_count": len(pairs),
            }
            continue
        pairs.sort(key=lambda x: x[1], reverse=is_higher_risk)
        k = max(1, int(len(pairs) * RISK_TERCILE))
        high_asofs = {a for a, _ in pairs[:k]}
        low_asofs = {a for a, _ in pairs[-k:]}

        def _avg(asofs: set[str], field_name: str) -> Optional[float]:
            vals = []
            for a in asofs:
                t = target_by_asof.get(a)
                if t is None:
                    continue
                v = getattr(t, field_name)
                if v is not None:
                    vals.append(v)
            return sum(vals) / len(vals) if vals else None

        out[axis] = {
            "high_risk_future_market_drawdown_10d": _avg(
                high_asofs, "future_market_drawdown_10d"
            ),
            "high_risk_future_kodex200_return_5d": _avg(
                high_asofs, "future_kodex200_return_5d"
            ),
            "low_risk_future_market_drawdown_10d": _avg(
                low_asofs, "future_market_drawdown_10d"
            ),
            "low_risk_future_kodex200_return_5d": _avg(
                low_asofs, "future_kodex200_return_5d"
            ),
            "evaluated_asof_count": len(pairs),
        }
    return out
