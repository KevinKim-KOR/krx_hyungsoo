"""POC3-ML-02 — Relative Upside Score Validity Gate · 평가 오케스트레이션.

PLAN V1 (`docs/ai_plan/POC3/POC3-ML-02_..._PLAN_V1.md`) 구현.

3대 전제 (PLAN §0):
  1. E2 는 현재 v0 실행 레시피의 point-in-time 재현이며 신규 학습 정책이 아니다.
  2. 신호 생성일과 진입가격 날짜는 같지 않다.
  3. 생존편향으로 이번 Step 의 최대 최종 판정은 RESEARCH_ONLY 다.

본 모듈은 운영 모듈을 **import 만** 하고 수정하지 않는다 (PLAN §2.3).
feature/모델 산식을 재구현하지 않는다.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import time
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.market_data_store import (
    DEFAULT_DB_PATH,
    fetch_price_history,
    get_etf_name_map,
    list_etf_tickers,
)
from app.market_regime import _label_at
from app.market_topn_helpers import classify_etf_tags
from app.ml_relative_upside_score import SCORE_SNAPSHOT_PATH
from app.ml_relative_upside_features import (
    FUTURE_HORIZON_20D,
    KODEX200_TICKER,
    RETURN_LOOKBACK_20D,
    build_feature_rows_for_ticker,
    build_kodex200_series,
    is_complete_for_inference,
)
from app.ml_relative_upside_model import (
    normalize_to_display_scores,
    predict_raw_scores,
    train_walk_forward,
)
from app.ml_score_validity_metrics import spearman

logger = logging.getLogger(__name__)

# --- 평가 상수 (PLAN §4 / §5) -----------------------------------------------
QUANTILE_BUCKETS = 5
TOP_DECILE_FRACTION = 0.10
# 점수 기준 top-N 바스켓 (설계자 보완 §4). 화면 DEFAULT_N 과 같은 10.
SCORE_TOP_N = 10
COST_BPS_GRID = (0.0, 10.0, 25.0, 50.0)
PRIMARY_COST_BP = 25.0
PRICE_BASIS_LABEL = "price return (분배금 미반영, SOURCE_CLOSE)"
EXCLUDED_TAGS = ("inverse", "leveraged", "synthetic", "futures")

# 최소 lookback — build_feature_rows_for_ticker 가 요구하는 관측치 수.
MIN_OBSERVATIONS = RETURN_LOOKBACK_20D + 1

# 첫 유효종가 이후 경과해야 하는 거래일 수 (상장 PIT — 설계자 보완 §2).
MIN_TRADING_DAYS_SINCE_LISTING = RETURN_LOOKBACK_20D

# --- E2 평가 구간 계약 (설계자 보완 §1 — 2026-08-29) ------------------------
# 아래 두 날짜는 v0 레시피가 아직 모델을 만들 수 없는 구간이라 **애초에 E2 평가
# 대상이 아니다**. 결과를 보고 제거하는 것이 아니라 PLAN 의 E2 시작일을 복원한다.
PRE_EVALUATION_WARMUP_DATES = ("2014-04-30", "2014-05-30")
E2_FIRST_SIGNAL_DATE = "2014-06-30"
E2_EXPECTED_POINT_COUNT = 145

PHASE_WARMUP = "PRE_EVALUATION_WARMUP"
PHASE_EVALUATION = "E2_EVALUATION"

# fail-closed 임계 (설계자 보완 §1 / PLAN §9 S-1 · S-3).
BLOCKING_MIN_COVERAGE = 0.70

# --- E1 재현 게이트 (PLAN §2.2 · 설계자 승인 2026-08-29) ---------------------
E1_SNAPSHOT_ASOF = "2026-08-20"
E1_MAX_SCORE_ABS_ERROR = 1.0
E1_MIN_SPEARMAN = 0.999
E1_TOP_K = 100
E1_MIN_TOP_K_OVERLAP = 0.95


@dataclass
class RebalancePoint:
    """PLAN §2.4 — 판단일 t / 진입일 e(t) / 청산일 e(t')."""

    signal_date: str
    entry_date: str
    next_signal_date: str
    exit_date: str
    signal_index: int
    horizon: str  # "1m" | "3m"


@dataclass
class DateResult:
    """단일 기준일의 평가 결과."""

    signal_date: str
    entry_date: str
    exit_date: str
    regime: Optional[str]
    train_row_count: int
    test_row_count: int
    scored_count: int
    evaluated_count: int
    ic: Optional[float] = None
    quantile_means: dict[int, Optional[float]] = field(default_factory=dict)
    top_decile_mean: Optional[float] = None
    top_decile_median: Optional[float] = None
    top_decile_tickers: list[str] = field(default_factory=list)
    top_decile_values: list[float] = field(default_factory=list)
    coverage_denominator: int = 0
    coverage_numerator: int = 0
    missing_reasons: dict[str, int] = field(default_factory=dict)
    asof_equals_signal_ratio: Optional[float] = None
    scores: dict[str, float] = field(default_factory=dict)
    labels: dict[str, float] = field(default_factory=dict)


# --- 가격 로딩 / 달력 --------------------------------------------------------


def load_prices(db_path: Path = DEFAULT_DB_PATH) -> dict[str, list[tuple[str, float]]]:
    """전체 ticker 의 (date, close) 시계열. 운영 함수 `fetch_price_history` 사용.

    PLAN §3.2 확정사항 1 — 원시 가격 이력은 메모리에 한 번 적재할 수 있다.
    절단은 각 기준일에서 수행한다.
    """
    prices: dict[str, list[tuple[str, float]]] = {}
    for ticker in list_etf_tickers(db_path):
        history = fetch_price_history(ticker, db_path=db_path)
        if history:
            prices[ticker] = history
    return prices


def trading_days(prices: dict[str, list[tuple[str, float]]]) -> list[str]:
    """거래일 축 = KODEX200 유효 종가일 (PLAN §2.3)."""
    series = prices.get(KODEX200_TICKER)
    if not series:
        raise RuntimeError(f"KODEX200({KODEX200_TICKER}) 시계열이 없습니다")
    return [d for d, _ in series]


def month_end_days(days: list[str]) -> list[str]:
    """각 달의 마지막 거래일."""
    by_month: dict[str, str] = {}
    for d in days:
        by_month[d[:7]] = d
    return [by_month[k] for k in sorted(by_month)]


def build_calendar(days: list[str], *, months_ahead: int) -> list[RebalancePoint]:
    """판단일 t → 진입 e(t) → 청산 e(t') 조합 (PLAN §2.4).

    `months_ahead=1` 이면 1M, `3` 이면 3M. 진입일은 t 다음 거래일이다.
    e(t) 또는 e(t') 가 존재하지 않으면 그 기준일은 제외한다.
    """
    index = {d: i for i, d in enumerate(days)}
    ends = month_end_days(days)
    horizon = f"{months_ahead}m"
    points: list[RebalancePoint] = []
    for k in range(len(ends) - months_ahead):
        t = ends[k]
        t2 = ends[k + months_ahead]
        i1 = index[t] + 1
        i2 = index[t2] + 1
        if i1 >= len(days) or i2 >= len(days):
            continue
        points.append(
            RebalancePoint(
                signal_date=t,
                entry_date=days[i1],
                next_signal_date=t2,
                exit_date=days[i2],
                signal_index=index[t],
                horizon=horizon,
            )
        )
    return points


def truncate_history(
    history: list[tuple[str, float]], cut_date: str
) -> list[tuple[str, float]]:
    """`date <= cut_date` 로 절단 (PLAN §3.1 1단계 · 확정사항 1)."""
    dates = [d for d, _ in history]
    return history[: bisect.bisect_right(dates, cut_date)]


def build_close_maps(
    prices: dict[str, list[tuple[str, float]]],
) -> dict[str, dict[str, float]]:
    """ticker → {date: close}. 라벨 계산용 O(1) 조회."""
    return {t: {d: c for d, c in h} for t, h in prices.items()}


# --- 라벨 (PLAN §2.4) --------------------------------------------------------


def forward_excess(
    close_maps: dict[str, dict[str, float]],
    ticker: str,
    entry_date: str,
    exit_date: str,
) -> Optional[float]:
    """진입일 → 청산일 KODEX200 대비 초과수익.

    ETF 와 KODEX200 이 **동일한 진입·청산 날짜**를 쓴다. 두 날짜 중 하나라도
    유효 종가가 없으면 None (보간·이월 금지).
    """
    etf = close_maps.get(ticker)
    kodex = close_maps.get(KODEX200_TICKER)
    if not etf or not kodex:
        return None
    p0, p1 = etf.get(entry_date), etf.get(exit_date)
    k0, k1 = kodex.get(entry_date), kodex.get(exit_date)
    if not p0 or not p1 or not k0 or not k1:
        return None
    if p0 <= 0 or p1 <= 0 or k0 <= 0 or k1 <= 0:
        return None
    return (p1 / p0 - 1.0) - (k1 / k0 - 1.0)


# --- E2: v0 레시피의 PIT 재현 (PLAN §3.1) -----------------------------------


@dataclass
class ScoreRun:
    """단일 기준일의 재현 결과."""

    signal_date: str
    display_scores: dict[str, float]
    raw_scores: dict[str, float]
    inference_asof: dict[str, str]
    simple_signal: dict[str, float]
    train_row_count: int
    test_row_count: int
    coefficients: Optional[list[float]] = None
    bias: Optional[float] = None
    max_input_date: Optional[str] = None
    max_target_end_date: Optional[str] = None
    train_date_range: tuple[str, str] = ("", "")
    model: object = None
    inference_rows: list = field(default_factory=list)


def reproduce_scores_at(
    prices: dict[str, list[tuple[str, float]]],
    signal_date: str,
    *,
    keep_model: bool = False,
    keep_rows: bool = False,
) -> ScoreRun:
    """기준일 `t` 시점에 실제로 생성됐을 점수를 재현한다.

    PLAN §3.1 의 5단계 — 절단 → 기존 함수 무변경 호출 → 현재 80/20 split 그대로
    → 그 시점 점수 재현 → **별도 purge·embargo 규칙 추가 없음**.

    확정사항 1: 전 구간 panel 을 미리 만들어 `asof_date` 로 자르지 않는다.
    반드시 절단된 가격 이력을 feature 함수에 전달한다.

    확정사항 2: 절단만으로 `target_end <= t` 가 성립한다. 근거 —
    `build_feature_rows_for_ticker` 는 `i + 20 < n` 일 때만 target 을 채우므로
    target 이 존재하는 행의 최대 종료 index 는 `n - 1`, 즉 절단된 이력의 마지막
    날짜(<= t)다.
    """
    truncated: dict[str, list[tuple[str, float]]] = {}
    max_input_date = ""
    for ticker, history in prices.items():
        cut = truncate_history(history, signal_date)
        if cut:
            truncated[ticker] = cut
            if cut[-1][0] > max_input_date:
                max_input_date = cut[-1][0]

    kodex_map = build_kodex200_series(truncated)

    training_rows = []
    max_target_end = ""
    for ticker, history in truncated.items():
        if ticker == KODEX200_TICKER:
            continue
        rows = build_feature_rows_for_ticker(
            ticker, history, kodex_map, include_future_target=True
        )
        if rows:
            training_rows.extend(rows)
            # L-3 실증: target 존재 행의 최대 종료일 = 절단 이력의 마지막 날짜.
            if len(history) > MIN_OBSERVATIONS + FUTURE_HORIZON_20D:
                end_date = history[-1][0]
                if end_date > max_target_end:
                    max_target_end = end_date

    model, train_result = train_walk_forward(training_rows)

    inference_rows = []
    for ticker, history in truncated.items():
        if ticker == KODEX200_TICKER:
            continue
        rows = build_feature_rows_for_ticker(
            ticker, history, kodex_map, include_future_target=False
        )
        latest = next((r for r in reversed(rows) if is_complete_for_inference(r)), None)
        if latest is not None:
            inference_rows.append(latest)

    raw_scores = predict_raw_scores(model, inference_rows) if model else {}
    display_scores = normalize_to_display_scores(raw_scores)

    coefficients = None
    bias = None
    if model is not None:
        weights = model.linear.weight.detach().cpu().flatten().tolist()
        coefficients = [float(w) for w in weights]
        bias = float(model.linear.bias.detach().cpu().flatten().tolist()[0])

    return ScoreRun(
        signal_date=signal_date,
        display_scores=display_scores,
        raw_scores=raw_scores,
        inference_asof={r.ticker: r.asof_date for r in inference_rows},
        simple_signal={
            r.ticker: float(r.excess_return_20d)
            for r in inference_rows
            if r.excess_return_20d is not None
        },
        train_row_count=train_result.train_row_count,
        test_row_count=train_result.test_row_count,
        coefficients=coefficients,
        bias=bias,
        max_input_date=max_input_date or None,
        max_target_end_date=max_target_end or None,
        train_date_range=train_result.train_date_range,
        model=model if keep_model else None,
        inference_rows=inference_rows if keep_rows else [],
    )


def evaluate_e1_gates(
    snapshot_scores: dict[str, float],
    reproduced_scores: dict[str, float],
) -> dict:
    """PLAN §2.2 — E1 재현 게이트 G-1 / G-3 / G-4 판정 (순수 함수).

    G-2(계수)는 저장된 참조 계수가 없어 게이트로 쓰지 않는다 — 기록만 한다.

    **하나라도 실패하면 기준을 완화하지 않고 `E1_UNAVAILABLE`** 로 처리한다.
    """
    snap_set, repro_set = set(snapshot_scores), set(reproduced_scores)
    g1 = snap_set == repro_set
    common = sorted(snap_set & repro_set)

    max_err: Optional[float] = None
    rank_corr: Optional[float] = None
    overlap: Optional[float] = None
    if common:
        max_err = max(abs(reproduced_scores[t] - snapshot_scores[t]) for t in common)
        rank_corr = spearman(
            [snapshot_scores[t] for t in common],
            [reproduced_scores[t] for t in common],
        )
        snap_top = {
            t
            for t, _ in sorted(snapshot_scores.items(), key=lambda kv: -kv[1])[
                :E1_TOP_K
            ]
        }
        repro_top = {
            t
            for t, _ in sorted(reproduced_scores.items(), key=lambda kv: -kv[1])[
                :E1_TOP_K
            ]
        }
        denom = min(E1_TOP_K, len(snap_top), len(repro_top)) or 1
        overlap = len(snap_top & repro_top) / denom

    g3 = max_err is not None and max_err <= E1_MAX_SCORE_ABS_ERROR
    g4 = (
        rank_corr is not None
        and rank_corr >= E1_MIN_SPEARMAN
        and overlap is not None
        and overlap >= E1_MIN_TOP_K_OVERLAP
    )
    passed = bool(g1 and g3 and g4)
    return {
        "status": "E1_RECONSTRUCTED" if passed else "E1_UNAVAILABLE",
        "gates": {
            "G1_candidate_set_identical": {
                "passed": g1,
                "snapshot_count": len(snap_set),
                "reproduced_count": len(repro_set),
                "only_in_snapshot": sorted(snap_set - repro_set)[:20],
                "only_in_reproduced": sorted(repro_set - snap_set)[:20],
            },
            "G3_max_abs_score_error": {
                "passed": g3,
                "value": max_err,
                "threshold": E1_MAX_SCORE_ABS_ERROR,
            },
            "G4_rank_agreement": {
                "passed": g4,
                "spearman": rank_corr,
                "spearman_threshold": E1_MIN_SPEARMAN,
                "top_k": E1_TOP_K,
                "top_k_overlap": overlap,
                "top_k_overlap_threshold": E1_MIN_TOP_K_OVERLAP,
            },
        },
    }


def run_e1_gate(prices: dict, *, log: Optional[logging.Logger] = None) -> dict:
    """PLAN §2.2 — 게이트 4종. 하나라도 실패하면 E1_UNAVAILABLE."""
    if not SCORE_SNAPSHOT_PATH.exists():
        return {"status": "E1_UNAVAILABLE", "reason": "운영 snapshot 파일 없음"}
    snapshot = json.loads(SCORE_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    snap_scores = {
        c["ticker"]: c["relative_upside_score"]
        for c in snapshot.get("candidates", [])
        if c.get("relative_upside_score") is not None
    }
    (log or logger).info(
        "E1: snapshot asof=%s candidates=%d",
        snapshot.get("asof_date"),
        len(snap_scores),
    )

    t0 = time.perf_counter()
    run = reproduce_scores_at(prices, E1_SNAPSHOT_ASOF, keep_model=True)
    elapsed = time.perf_counter() - t0
    repro = run.display_scores
    (log or logger).info("E1: 재현 %d건 (%.1fs)", len(repro), elapsed)

    gate = evaluate_e1_gates(snap_scores, repro)
    passed = gate["status"] == "E1_RECONSTRUCTED"
    return {
        "status": gate["status"],
        "snapshot_asof": snapshot.get("asof_date"),
        "snapshot_generated_at": snapshot.get("generated_at"),
        "cutoff_date": E1_SNAPSHOT_ASOF,
        "gates": gate["gates"],
        "G2_coefficients_recorded_only": {
            "note": "저장된 참조 계수가 없어 게이트로 쓰지 않는다 (PLAN §2.2)",
            "coefficients": run.coefficients,
            "bias": run.bias,
        },
        "train_row_count": run.train_row_count,
        "test_row_count": run.test_row_count,
        "train_date_range": list(run.train_date_range),
        "elapsed_seconds": round(elapsed, 2),
        "_model": run.model if passed else None,
        "_scores": repro,
        "_train_end": run.train_date_range[1] if passed else None,
    }


# --- universe / 태그 / 커버리지 ---------------------------------------------


def build_tag_map(db_path: Path = DEFAULT_DB_PATH) -> dict[str, list[str]]:
    """ticker → 상품 태그. 운영 `classify_etf_tags` 사용 (현재 이름 기준 — B-3)."""
    names = get_etf_name_map(db_path=db_path)
    return {t: classify_etf_tags(n) for t, n in names.items()}


def is_filter_universe(tags: list[str]) -> bool:
    """인버스·레버리지·합성·선물 제외 후 남는가 (화면 필터와 동일)."""
    return not any(tag in EXCLUDED_TAGS for tag in tags)


def observations_upto(history: list[tuple[str, float]], signal_date: str) -> int:
    """기준일까지의 유효 종가 개수 (상장 PIT proxy — PLAN §2.6)."""
    dates = [d for d, _ in history]
    return bisect.bisect_right(dates, signal_date)


def is_pit_eligible(
    history: list[tuple[str, float]],
    signal_date: str,
    day_index: dict[str, int],
) -> bool:
    """coverage 분모 편입 조건 (설계자 보완 §2).

    셋을 **모두** 만족해야 한다:
      1. 기준일 이전 유효 종가가 **최소 21개**(`MIN_OBSERVATIONS`) 존재
      2. **첫 유효종가 이후 20거래일** 경과 (KODEX200 거래일 축 기준)
      3. (호출자가) 인버스·레버리지·합성·선물 제외

    종가 한 건만 있는 ticker 는 분모에 들어가지 않는다.
    """
    if observations_upto(history, signal_date) < MIN_OBSERVATIONS:
        return False
    first_date = history[0][0] if history else None
    if first_date is None:
        return False
    t_idx = day_index.get(signal_date)
    first_idx = day_index.get(first_date)
    if t_idx is None:
        return False
    if first_idx is None:
        # 첫 유효종가일이 benchmark 거래일 축에 없으면 그 날짜 이하의 최근
        # 거래일 index 로 근사한다 (축 밖 날짜를 통과시키지 않는다).
        prior = [d for d in day_index if d <= first_date]
        if not prior:
            return False
        first_idx = day_index[max(prior)]
    return (t_idx - first_idx) >= MIN_TRADING_DAYS_SINCE_LISTING


def classify_phase(signal_date: str) -> str:
    """기준일을 warmup / 평가 로 분류 (설계자 보완 §1).

    warmup 집합은 **사전 고정**이다. 실행 결과(`train_rows=0`)를 보고 임의로
    warmup 으로 재분류하지 않는다.
    """
    return (
        PHASE_WARMUP if signal_date in PRE_EVALUATION_WARMUP_DATES else PHASE_EVALUATION
    )


def assert_evaluation_window(evaluation_dates: list[str]) -> None:
    """E2 평가 구간이 계약(2014-06-30 시작 · 145개)과 일치하는지 확인."""
    if not evaluation_dates:
        raise RuntimeError("E2 평가 기준일이 0건이다")
    first = min(evaluation_dates)
    if first != E2_FIRST_SIGNAL_DATE:
        raise RuntimeError(
            f"E2 시작일 계약 위반: 기대 {E2_FIRST_SIGNAL_DATE}, 실제 {first}"
        )
    if len(evaluation_dates) != E2_EXPECTED_POINT_COUNT:
        raise RuntimeError(
            f"E2 평가일 수 계약 위반: 기대 {E2_EXPECTED_POINT_COUNT}, "
            f"실제 {len(evaluation_dates)}"
        )


# --- 시장 상태 (PLAN §4.6) ---------------------------------------------------


def regime_at(kodex_closes: list[float], signal_index: int) -> Optional[str]:
    """운영 `_label_at` 을 그대로 호출. 정의상 `closes[:i+1]` 만 사용한다."""
    return _label_at(kodex_closes, signal_index)


# --- 무결성 해시 (PLAN §2.1) -------------------------------------------------


def price_projection_sha256(
    *, db_path: Path = DEFAULT_DB_PATH, cutoff_date: Optional[str] = None
) -> str:
    """`(ticker,date,close)` 투영의 sha256. `created_at`/`fetched_at` 제외."""
    digest = hashlib.sha256()
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        if cutoff_date:
            cur = con.execute(
                "SELECT ticker,date,close FROM etf_daily_price WHERE date <= ? "
                "ORDER BY ticker,date",
                (cutoff_date,),
            )
        else:
            cur = con.execute(
                "SELECT ticker,date,close FROM etf_daily_price ORDER BY ticker,date"
            )
        for ticker, date_str, close in cur:
            digest.update(f"{ticker}|{date_str}|{close}\n".encode("utf-8"))
    finally:
        con.close()
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
