"""ML Baseline v0 — Candidate (상승 후보) 룩백 baseline (2026-06-11).

지시문 §7 — 현재 feature 가 이후 5/10/20d 수익률 / 초과수익과 관련이 있었는지
top quintile (사용자 결정 — Top 20%) 기반으로 룩백 검증.

본 모듈은 단순 rank baseline + composite rank v0 만 사용한다.
ML 모델 학습 / 라벨 / 매수·매도 판단 / 위험 threshold 0건.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.ml_baseline_targets import (
    CANDIDATE_HORIZONS,
    MAX_HORIZON,
    CandidateTargetRow,
)

# 사용자 결정 — top quintile (상위 20%).
TOP_GROUP_QUANTILE = 0.20
# composite rank v0 에 포함할 feature (지시문 §7.3).
COMPOSITE_FEATURES = [
    "return_20d",
    "excess_return_20d_vs_kodex200",
    "return_10d",
    "volume_ratio_20d",
]
SAMPLE_ASOF_LIMIT = 5  # snapshot 비대화 방지.


# ─── helpers ─────────────────────────────────────────────────────────


@dataclass
class _AsofFeatureRow:
    ticker: str
    return_5d: Optional[float]
    return_10d: Optional[float]
    return_20d: Optional[float]
    excess_return_20d_vs_kodex200: Optional[float]
    volume_ratio_20d: Optional[float]


def _load_features_by_asof(con: sqlite3.Connection, asof: str) -> list[_AsofFeatureRow]:
    cur = con.execute(
        "SELECT ticker, return_5d, return_10d, return_20d, "
        "excess_return_20d_vs_kodex200, volume_ratio_20d "
        "FROM etf_ml_feature_daily WHERE asof = ?",
        (asof,),
    )
    out: list[_AsofFeatureRow] = []
    for r in cur.fetchall():
        out.append(
            _AsofFeatureRow(
                ticker=str(r[0]),
                return_5d=r[1],
                return_10d=r[2],
                return_20d=r[3],
                excess_return_20d_vs_kodex200=r[4],
                volume_ratio_20d=r[5],
            )
        )
    return out


def _rank_desc(values: dict[str, Optional[float]]) -> dict[str, int]:
    """value DESC 정렬 후 1-based rank. None 은 rank 부여 X (return X)."""
    items = [(tk, v) for tk, v in values.items() if v is not None]
    items.sort(key=lambda x: x[1], reverse=True)
    return {tk: i + 1 for i, (tk, _) in enumerate(items)}


def _composite_rank(rows: list[_AsofFeatureRow]) -> dict[str, float]:
    """COMPOSITE_FEATURES 각각 DESC rank 평균 (낮을수록 강함)."""
    rank_sums: dict[str, list[int]] = {}
    for f in COMPOSITE_FEATURES:
        values = {r.ticker: getattr(r, f) for r in rows}
        ranks = _rank_desc(values)
        for tk, rk in ranks.items():
            rank_sums.setdefault(tk, []).append(rk)
    out: dict[str, float] = {}
    for tk, lst in rank_sums.items():
        if len(lst) >= 2:  # 2 feature 이상 rank 가 있는 경우만.
            out[tk] = sum(lst) / len(lst)
    return out


def _spearman_like(x: list[float], y: list[float]) -> Optional[float]:
    """rank correlation — Pearson on ranks. n<3 이면 None."""
    if len(x) != len(y) or len(x) < 3:
        return None
    rx = _value_to_rank(x)
    ry = _value_to_rank(y)
    n = len(rx)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    dy = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def _value_to_rank(vals: list[float]) -> list[float]:
    indexed = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    for r, idx in enumerate(indexed):
        ranks[idx] = float(r + 1)
    return ranks


def _median(values: list[float]) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def _mean(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _top_tickers_by_feature(
    rows: list[_AsofFeatureRow], feature_name: str, quantile: float
) -> set[str]:
    """단순 baseline — 단일 feature DESC 정렬의 top quantile ticker set."""
    pairs = [
        (r.ticker, getattr(r, feature_name))
        for r in rows
        if getattr(r, feature_name) is not None
    ]
    if not pairs:
        return set()
    pairs.sort(key=lambda x: x[1], reverse=True)
    top_n = max(1, int(len(pairs) * quantile))
    return {tk for tk, _ in pairs[:top_n]}


# ─── per-asof evaluation ─────────────────────────────────────────────


@dataclass
class _AsofEvalResult:
    asof: str
    universe_count: int
    top_count: int
    top_avg_future_return: dict[str, Optional[float]] = field(default_factory=dict)
    top_avg_future_excess: dict[str, Optional[float]] = field(default_factory=dict)
    universe_median_future_return: dict[str, Optional[float]] = field(
        default_factory=dict
    )
    hit_rate: dict[str, Optional[float]] = field(default_factory=dict)
    rank_correlation: dict[str, Optional[float]] = field(default_factory=dict)
    # 지시문 §7.4 — 단순 baseline 비교 기준 2종 (composite v0 외 별도).
    simple_return20d_top_avg_future_return: dict[str, Optional[float]] = field(
        default_factory=dict
    )
    simple_excess20d_top_avg_future_return: dict[str, Optional[float]] = field(
        default_factory=dict
    )


def _evaluate_one_asof(
    feature_rows: list[_AsofFeatureRow],
    target_by_ticker: dict[str, CandidateTargetRow],
    composite_scores: dict[str, float],
) -> _AsofEvalResult:
    asof = next(
        (t.asof for t in target_by_ticker.values()),
        feature_rows[0].ticker if feature_rows else "",
    )
    # composite_scores 가 낮을수록 강함 → top quantile = scores 의 하위 20%.
    ranked = sorted(composite_scores.items(), key=lambda x: x[1])
    n = len(ranked)
    top_n = max(1, int(n * TOP_GROUP_QUANTILE))
    top_tickers = {tk for tk, _ in ranked[:top_n]}

    res = _AsofEvalResult(asof=asof, universe_count=n, top_count=top_n)

    # 단순 baseline 2종 (지시문 §7.4) — composite v0 와 별도로 top quintile 추출.
    simple_ret20_top = _top_tickers_by_feature(
        feature_rows, "return_20d", TOP_GROUP_QUANTILE
    )
    simple_ex20_top = _top_tickers_by_feature(
        feature_rows, "excess_return_20d_vs_kodex200", TOP_GROUP_QUANTILE
    )

    for h in CANDIDATE_HORIZONS:
        ret_field = f"future_return_{h}d"
        ex_field = f"future_excess_return_{h}d_vs_kodex200"

        top_returns: list[float] = []
        top_excess: list[float] = []
        all_returns: list[float] = []
        score_pairs_x: list[float] = []
        score_pairs_y: list[float] = []

        for tk, score in composite_scores.items():
            tgt = target_by_ticker.get(tk)
            if tgt is None:
                continue
            ret = getattr(tgt, ret_field)
            ex = getattr(tgt, ex_field)
            if ret is not None:
                all_returns.append(ret)
                score_pairs_x.append(score)
                score_pairs_y.append(ret)
                if tk in top_tickers:
                    top_returns.append(ret)
            if ex is not None and tk in top_tickers:
                top_excess.append(ex)

        res.top_avg_future_return[f"{h}d"] = _mean(top_returns)
        res.top_avg_future_excess[f"{h}d"] = _mean(top_excess)
        res.universe_median_future_return[f"{h}d"] = _median(all_returns)
        # hit rate: top group 중 future_excess > 0 비율.
        if top_excess:
            wins = sum(1 for v in top_excess if v > 0)
            res.hit_rate[f"{h}d"] = wins / len(top_excess)
        else:
            res.hit_rate[f"{h}d"] = None
        # rank correlation: score (낮을수록 강함) → return (높을수록 좋음) 의
        # correlation 은 음수가 정상. 부호 반전 (score→-score) 후 계산.
        rc = _spearman_like([-s for s in score_pairs_x], score_pairs_y)
        res.rank_correlation[f"{h}d"] = rc

        # 단순 baseline (return_20d / excess_20d) 의 top group future_return 평균.
        res.simple_return20d_top_avg_future_return[f"{h}d"] = _mean(
            [
                getattr(target_by_ticker[tk], ret_field)
                for tk in simple_ret20_top
                if tk in target_by_ticker
                and getattr(target_by_ticker[tk], ret_field) is not None
            ]
        )
        res.simple_excess20d_top_avg_future_return[f"{h}d"] = _mean(
            [
                getattr(target_by_ticker[tk], ret_field)
                for tk in simple_ex20_top
                if tk in target_by_ticker
                and getattr(target_by_ticker[tk], ret_field) is not None
            ]
        )

    return res


# ─── public ──────────────────────────────────────────────────────────


@dataclass
class CandidateBaselineResult:
    status: str  # ok / warn / insufficient_history / error
    evaluated_days: int
    evaluated_ticker_count: int
    target_horizons: list[int]
    top_group_quantile: float
    top_group_avg_future_return: dict[str, Optional[float]] = field(
        default_factory=dict
    )
    top_group_avg_future_excess_return: dict[str, Optional[float]] = field(
        default_factory=dict
    )
    universe_median_future_return: dict[str, Optional[float]] = field(
        default_factory=dict
    )
    hit_rate: dict[str, Optional[float]] = field(default_factory=dict)
    rank_correlation: dict[str, Optional[float]] = field(default_factory=dict)
    # 지시문 §7.4 단순 baseline 비교 — composite v0 와 별도 보고.
    simple_baselines: dict[str, dict[str, Optional[float]]] = field(
        default_factory=dict
    )
    sample_asof_results: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def evaluate_candidate_baseline(
    db_path: Path,
    candidate_targets: list[CandidateTargetRow],
) -> CandidateBaselineResult:
    warnings: list[str] = []
    errors: list[str] = []

    # asof 별 target row index.
    by_asof_ticker: dict[str, dict[str, CandidateTargetRow]] = {}
    for r in candidate_targets:
        by_asof_ticker.setdefault(r.asof, {})[r.ticker] = r
    eligible_asofs = sorted(by_asof_ticker.keys())
    # horizon tail 제거: 마지막 MAX_HORIZON 거래일은 평가에서 제외.
    if len(eligible_asofs) > MAX_HORIZON:
        eligible_asofs = eligible_asofs[:-MAX_HORIZON]
    else:
        warnings.append(
            f"candidate target 의 asof 수({len(eligible_asofs)})가 "
            f"MAX_HORIZON({MAX_HORIZON}) 이하 — 평가 가능 거래일 0"
        )

    if not eligible_asofs:
        return CandidateBaselineResult(
            status="insufficient_history",
            evaluated_days=0,
            evaluated_ticker_count=0,
            target_horizons=list(CANDIDATE_HORIZONS),
            top_group_quantile=TOP_GROUP_QUANTILE,
            warnings=warnings,
            errors=errors,
        )

    per_asof: list[_AsofEvalResult] = []
    universe_tickers: set[str] = set()

    with sqlite3.connect(str(db_path)) as con:
        for asof in eligible_asofs:
            feat_rows = _load_features_by_asof(con, asof)
            if not feat_rows:
                continue
            composite = _composite_rank(feat_rows)
            if not composite:
                continue
            tgt = by_asof_ticker.get(asof, {})
            res = _evaluate_one_asof(feat_rows, tgt, composite)
            res.asof = asof
            per_asof.append(res)
            universe_tickers.update(r.ticker for r in feat_rows)

    if not per_asof:
        errors.append("평가 가능한 asof 0건 — feature 분포 / target join 확인 필요")
        return CandidateBaselineResult(
            status="error",
            evaluated_days=0,
            evaluated_ticker_count=0,
            target_horizons=list(CANDIDATE_HORIZONS),
            top_group_quantile=TOP_GROUP_QUANTILE,
            warnings=warnings,
            errors=errors,
        )

    # 전체 평균 (asof 평균의 평균 — equal weight).
    def _avg_over_asof(field_name: str, horizon_key: str) -> Optional[float]:
        vals = [
            getattr(r, field_name).get(horizon_key)
            for r in per_asof
            if getattr(r, field_name).get(horizon_key) is not None
        ]
        return _mean(vals)

    top_ret: dict[str, Optional[float]] = {}
    top_ex: dict[str, Optional[float]] = {}
    uni_med: dict[str, Optional[float]] = {}
    hit: dict[str, Optional[float]] = {}
    rc: dict[str, Optional[float]] = {}
    simple_ret20: dict[str, Optional[float]] = {}
    simple_ex20: dict[str, Optional[float]] = {}
    for h in CANDIDATE_HORIZONS:
        k = f"{h}d"
        top_ret[k] = _avg_over_asof("top_avg_future_return", k)
        top_ex[k] = _avg_over_asof("top_avg_future_excess", k)
        uni_med[k] = _avg_over_asof("universe_median_future_return", k)
        hit[k] = _avg_over_asof("hit_rate", k)
        rc[k] = _avg_over_asof("rank_correlation", k)
        simple_ret20[k] = _avg_over_asof("simple_return20d_top_avg_future_return", k)
        simple_ex20[k] = _avg_over_asof("simple_excess20d_top_avg_future_return", k)

    # sample asof — 시작 / 중간 / 끝 등 균등 추출.
    sample_indices = _pick_sample_indices(len(per_asof), SAMPLE_ASOF_LIMIT)
    samples: list[dict[str, Any]] = []
    for idx in sample_indices:
        r = per_asof[idx]
        samples.append(
            {
                "asof": r.asof,
                "universe_count": r.universe_count,
                "top_count": r.top_count,
                "top_avg_future_return": r.top_avg_future_return,
                "top_avg_future_excess": r.top_avg_future_excess,
                "universe_median_future_return": r.universe_median_future_return,
                "hit_rate": r.hit_rate,
                "rank_correlation": r.rank_correlation,
            }
        )

    status = "ok" if not warnings else "warn"
    if rc.get("20d") is None and rc.get("10d") is None:
        warnings.append("rank correlation 산출 불가 (target join 부족)")
        status = "warn"
    return CandidateBaselineResult(
        status=status,
        evaluated_days=len(per_asof),
        evaluated_ticker_count=len(universe_tickers),
        target_horizons=list(CANDIDATE_HORIZONS),
        top_group_quantile=TOP_GROUP_QUANTILE,
        top_group_avg_future_return=top_ret,
        top_group_avg_future_excess_return=top_ex,
        universe_median_future_return=uni_med,
        hit_rate=hit,
        rank_correlation=rc,
        simple_baselines={
            "simple_return_20d_top_quintile_avg_future_return": simple_ret20,
            "simple_excess_20d_vs_kodex200_top_quintile_avg_future_return": (
                simple_ex20
            ),
            "universe_median_future_return": uni_med,
        },
        sample_asof_results=samples,
        warnings=warnings,
        errors=errors,
    )


def _pick_sample_indices(n: int, k: int) -> list[int]:
    if n <= k:
        return list(range(n))
    step = (n - 1) / (k - 1)
    return [int(round(i * step)) for i in range(k)]
