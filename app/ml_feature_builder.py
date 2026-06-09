"""ML 최소 데이터 레인 — feature 계산 builder (POC2 2026-06-08 / FIX r2).

지시문 §5 / §6 — 기존 가격 / NAV / market_benchmark 데이터로 ETF별 + 시장 위험 +
조정장 전조 feature 를 계산. 외부 source 호출 0건. ML 학습 X.

본 모듈은 orchestrator 책임만 — 시계열 primitives 와 NAV join 은 별도 모듈로 분리
(KS-10 near 진입 회피 FIX r2):
- 시계열 primitives → `app/ml_feature_primitives.py`
- NAV join → `app/ml_feature_nav_lookup.py`

입력:
- etf_daily_price (date, close, volume) — fetch_price_volume_history
- market_benchmark_daily_price (KOSPI) — fetch_benchmark_history
- KODEX200 은 ETF 이므로 etf_daily_price 에서 ticker=069500 로 조회
- etf_nav_daily (asof, source, nav, market_price, discount_rate_pct, status)

출력 (저장은 호출자):
- list[EtfMlFeatureRow]
- list[MarketRiskFeatureRow]

다음은 안 한다 (지시문 §6.3):
- 조정장 label / regime 확정 / 알림 — feature 만 저장.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.market_benchmark_store import fetch_benchmark_history
from app.market_data_store import (
    DEFAULT_DB_PATH,
    fetch_price_volume_history,
    get_etf_name_map,
    list_etf_tickers,
)
from app.market_regime import KODEX200_TICKER, KOSPI_ID
from app.ml_feature_nav_lookup import NavLookup
from app.ml_feature_primitives import (
    WINDOW_5,
    WINDOW_10,
    WINDOW_20,
    PriceSeries,
    build_series,
    daily_returns,
    distance_from_20d_high,
    drawdown_20d,
    excess_vs_kodex200,
    return_pct,
    volatility_20d,
    volume_ratio_20d,
)
from app.ml_feature_store import EtfMlFeatureRow, MarketRiskFeatureRow

SHORT_WEAKNESS_WINDOW = 3
NAV_DISCOUNT_EXTREME_THRESHOLD_PCT = 3.0


def _build_etf_feature(
    series: PriceSeries,
    idx: int,
    name: Optional[str],
    kodex_returns_by_date: dict[str, dict[str, Optional[float]]],
    nav_lookup: NavLookup,
) -> EtfMlFeatureRow:
    asof = series.dates[idx]
    r5 = return_pct(series, idx, WINDOW_5)
    r10 = return_pct(series, idx, WINDOW_10)
    r20 = return_pct(series, idx, WINDOW_20)
    kodex = kodex_returns_by_date.get(asof) or {}
    excess5 = excess_vs_kodex200(r5, kodex.get("r5"))
    excess10 = excess_vs_kodex200(r10, kodex.get("r10"))
    excess20 = excess_vs_kodex200(r20, kodex.get("r20"))
    vol = volatility_20d(series, idx)
    dd = drawdown_20d(series, idx)
    vr = volume_ratio_20d(series, idx)
    nav_row = nav_lookup.lookup(series.ticker, asof)
    flags: list[str] = []
    if nav_row is None:
        nav_status = "unavailable"
    else:
        nav_status = nav_row.status
        if nav_row.asof != asof:
            flags.append(f"nav_asof={nav_row.asof}")
    if vol is None:
        flags.append("vol_short")
    if dd is None:
        flags.append("dd_short")
    return EtfMlFeatureRow(
        asof=asof,
        ticker=series.ticker,
        name=name,
        close_price=series.closes[idx],
        volume=series.volumes[idx],
        return_5d=r5,
        return_10d=r10,
        return_20d=r20,
        excess_return_5d_vs_kodex200=excess5,
        excess_return_10d_vs_kodex200=excess10,
        excess_return_20d_vs_kodex200=excess20,
        volatility_20d=vol,
        drawdown_20d=dd,
        volume_ratio_20d=vr,
        nav=(nav_row.nav if nav_row else None),
        nav_market_price=(nav_row.market_price if nav_row else None),
        nav_discount_rate_pct=(nav_row.discount_rate_pct if nav_row else None),
        nav_status=nav_status,
        source_flags=";".join(flags) if flags else None,
    )


# ─── 공개 API: build_features ────────────────────────────────────────


@dataclass
class FeatureBuildResult:
    etf_rows: list[EtfMlFeatureRow]
    market_rows: list[MarketRiskFeatureRow]
    asofs: list[str]
    missing_data_summary: dict[str, int]


def _resolve_asof_window(
    kodex_dates: list[str],
    start_date: Optional[str],
    end_date: Optional[str],
    default_lookback: int,
) -> list[str]:
    """KODEX200 의 거래일 시퀀스 안에서 [start, end] 구간 추출.

    end_date 기본값 = 마지막 거래일. start_date 기본값 = end_date 기준 lookback
    거래일 전.
    """
    if not kodex_dates:
        return []
    end = end_date or kodex_dates[-1]
    end_idx = next(
        (i for i in range(len(kodex_dates) - 1, -1, -1) if kodex_dates[i] <= end),
        -1,
    )
    if end_idx < 0:
        return []
    if start_date:
        start_idx = next((i for i, d in enumerate(kodex_dates) if d >= start_date), -1)
        if start_idx < 0 or start_idx > end_idx:
            return []
    else:
        start_idx = max(0, end_idx - default_lookback + 1)
    return kodex_dates[start_idx : end_idx + 1]  # noqa: E203


def _kodex_returns_map(
    kodex_series: PriceSeries,
) -> dict[str, dict[str, Optional[float]]]:
    out: dict[str, dict[str, Optional[float]]] = {}
    for idx, d in enumerate(kodex_series.dates):
        out[d] = {
            "r1": return_pct(kodex_series, idx, 1),
            "r5": return_pct(kodex_series, idx, WINDOW_5),
            "r10": return_pct(kodex_series, idx, WINDOW_10),
            "r20": return_pct(kodex_series, idx, WINDOW_20),
        }
    return out


def _build_kospi_series_for_returns(
    db_path: Path,
) -> dict[str, dict[str, Optional[float]]]:
    rows = fetch_benchmark_history(benchmark_id=KOSPI_ID, db_path=db_path)
    if not rows:
        return {}
    triples: list[tuple[str, float, Optional[int]]] = [
        (d, float(c), None) for d, c in rows if c is not None and c > 0
    ]
    series = build_series(KOSPI_ID, triples)
    out: dict[str, dict[str, Optional[float]]] = {}
    for idx, d in enumerate(series.dates):
        out[d] = {
            "r1": return_pct(series, idx, 1),
            "r5": return_pct(series, idx, WINDOW_5),
            "r20": return_pct(series, idx, WINDOW_20),
        }
    return out


def _build_market_risk_row_kodex_only(
    asof: str,
    kodex_series: PriceSeries,
    kodex_idx: int,
    kospi_returns: dict[str, Optional[float]],
) -> MarketRiskFeatureRow:
    """KODEX200 기반 시장 수익률 + KODEX 자체 시장 proxy (변동성 / drawdown)만 채운다.

    universe breadth / NAV 분포 / 조정장 전조 proxy 는 caller (build_features) 가
    universe 전체 ETF 시계열을 보고 채운다 — 본 함수는 KODEX-only fast path.
    """
    k1 = return_pct(kodex_series, kodex_idx, 1)
    k5 = return_pct(kodex_series, kodex_idx, WINDOW_5)
    k20 = return_pct(kodex_series, kodex_idx, WINDOW_20)
    k_returns_for_proxy = daily_returns(kodex_series, kodex_idx, WINDOW_20)
    return MarketRiskFeatureRow(
        asof=asof,
        kodex200_return_1d=k1,
        kodex200_return_5d=k5,
        kodex200_return_20d=k20,
        kospi_return_1d=kospi_returns.get("r1"),
        kospi_return_5d=kospi_returns.get("r5"),
        kospi_return_20d=kospi_returns.get("r20"),
        etf_universe_up_count=None,
        etf_universe_down_count=None,
        etf_universe_flat_count=None,
        etf_universe_up_ratio=None,
        etf_universe_down_ratio=None,
        etf_universe_median_return_1d=None,
        etf_universe_median_return_5d=None,
        nav_discount_avg=None,
        nav_discount_abs_avg=None,
        nav_discount_extreme_count=None,
        volatility_20d_market_proxy=(
            statistics.stdev(k_returns_for_proxy)
            if len(k_returns_for_proxy) >= 2
            else None
        ),
        drawdown_20d_market_proxy=drawdown_20d(kodex_series, kodex_idx),
        distance_from_20d_high=distance_from_20d_high(kodex_series, kodex_idx),
        volatility_expansion_20d=None,
        down_day_volume_ratio=None,
        large_negative_day_proxy=None,
        short_term_weakness_proxy=None,
        breadth_deterioration_proxy=None,
    )


def build_features(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    default_lookback_days: int = 60,
    universe_filter: Optional[list[str]] = None,
) -> FeatureBuildResult:
    """asof 구간에 대해 모든 ETF feature + 시장 risk feature 생성.

    start_date / end_date 미지정 시 기본 60거래일.
    universe_filter 지정 시 해당 ticker 만 대상 (디버그 / 테스트 용도).
    """
    # 1) KODEX200 시계열 = "거래일 sequence" 의 정답.
    kodex_rows = fetch_price_volume_history(KODEX200_TICKER, db_path=db_path)
    if not kodex_rows:
        return FeatureBuildResult(
            etf_rows=[],
            market_rows=[],
            asofs=[],
            missing_data_summary={"kodex200_missing": 1},
        )
    kodex_series = build_series(KODEX200_TICKER, kodex_rows)
    kodex_returns_by_date = _kodex_returns_map(kodex_series)
    kospi_returns_by_date = _build_kospi_series_for_returns(db_path)

    # 2) 처리 대상 asof 추출.
    asofs = _resolve_asof_window(
        kodex_series.dates, start_date, end_date, default_lookback_days
    )
    if not asofs:
        return FeatureBuildResult(
            etf_rows=[], market_rows=[], asofs=[], missing_data_summary={}
        )

    # 3) NAV lookup 1회 (전체 ticker × asof).
    nav_lookup = NavLookup(db_path=db_path)

    # 4) universe 시계열 prefetch.
    if universe_filter is not None:
        tickers = list(universe_filter)
    else:
        tickers = list_etf_tickers(db_path=db_path)
    name_map = get_etf_name_map(db_path=db_path)
    series_map: dict[str, PriceSeries] = {}
    missing_series_count = 0
    for tk in tickers:
        if tk == KODEX200_TICKER:
            series_map[tk] = kodex_series
            continue
        rows = fetch_price_volume_history(tk, db_path=db_path)
        if not rows:
            missing_series_count += 1
            continue
        series_map[tk] = build_series(tk, rows)

    # 5) asof 별로 ETF feature + market risk feature 생성.
    etf_rows_all: list[EtfMlFeatureRow] = []
    market_rows: list[MarketRiskFeatureRow] = []
    missing_kospi = 0
    for asof in asofs:
        kodex_idx = kodex_series.date_index.get(asof)
        if kodex_idx is None:
            continue
        etf_rows_today: list[EtfMlFeatureRow] = []
        # universe daily / 5d returns 산출 (breadth / median 계산용).
        # 변수명 충돌 회피 — primitives.daily_returns 와 같은 이름이라 ufx.
        universe_daily_returns: list[float] = []
        five_returns: list[float] = []
        # down day volume aggregation
        kodex_today_change = (
            (kodex_series.closes[kodex_idx] / kodex_series.closes[kodex_idx - 1] - 1.0)
            * 100.0
            if kodex_idx >= 1 and kodex_series.closes[kodex_idx - 1] > 0
            else None
        )
        for tk, series in series_map.items():
            idx = series.date_index.get(asof)
            if idx is None or idx < 1:
                continue
            row = _build_etf_feature(
                series=series,
                idx=idx,
                name=name_map.get(tk),
                kodex_returns_by_date=kodex_returns_by_date,
                nav_lookup=nav_lookup,
            )
            etf_rows_today.append(row)
            # daily return for breadth
            prev_close = series.closes[idx - 1]
            cur_close = series.closes[idx]
            if prev_close > 0:
                universe_daily_returns.append((cur_close / prev_close - 1.0) * 100.0)
            if row.return_5d is not None:
                five_returns.append(row.return_5d)

        etf_rows_all.extend(etf_rows_today)
        # 시장 risk row.
        kospi_returns = kospi_returns_by_date.get(asof) or {}
        if not kospi_returns:
            missing_kospi += 1
        market_row = _build_market_risk_row_kodex_only(
            asof=asof,
            kodex_series=kodex_series,
            kodex_idx=kodex_idx,
            kospi_returns=kospi_returns,
        )
        # breadth + nav 분포 채우기.
        up = sum(1 for d in universe_daily_returns if d > 0.0)
        down = sum(1 for d in universe_daily_returns if d < 0.0)
        flat = sum(1 for d in universe_daily_returns if d == 0.0)
        total = up + down + flat
        up_ratio = (up / total) if total > 0 else None
        down_ratio = (down / total) if total > 0 else None
        median_1d = (
            statistics.median(universe_daily_returns)
            if universe_daily_returns
            else None
        )
        median_5d = statistics.median(five_returns) if five_returns else None
        nav_discounts = [
            row.nav_discount_rate_pct
            for row in etf_rows_today
            if row.nav_discount_rate_pct is not None and row.nav_status == "ok"
        ]
        nav_avg = statistics.fmean(nav_discounts) if nav_discounts else None
        nav_abs_avg = (
            statistics.fmean([abs(x) for x in nav_discounts]) if nav_discounts else None
        )
        nav_extreme = sum(
            1 for x in nav_discounts if abs(x) >= NAV_DISCOUNT_EXTREME_THRESHOLD_PCT
        )

        # 조정장 전조 proxy.
        # volatility_expansion: 단기(5일) 변동성 / 20일 변동성.
        vol20 = volatility_20d(kodex_series, kodex_idx)
        kodex_5_returns = daily_returns(kodex_series, kodex_idx, WINDOW_5)
        vol5 = statistics.stdev(kodex_5_returns) if len(kodex_5_returns) >= 2 else None
        vol_expansion = (
            (vol5 / vol20)
            if (vol5 is not None and vol20 is not None and vol20 > 0)
            else None
        )
        # down_day_volume_ratio: 오늘 KODEX200 일간 수익률 < 0 이면 KODEX200 volume_ratio_20d
        # 반환, 아니면 None.
        down_day_vol_ratio: Optional[float] = None
        kvr = volume_ratio_20d(kodex_series, kodex_idx)
        if kodex_today_change is not None and kodex_today_change < 0:
            down_day_vol_ratio = kvr
        # large_negative_day_proxy: 오늘 수익률(음수) × volume_ratio (음수 + 거래량 확대일수록 큰 값).
        large_neg = None
        if (
            kodex_today_change is not None
            and kodex_today_change < 0
            and kvr is not None
        ):
            large_neg = abs(kodex_today_change) * kvr
        # short_term_weakness_proxy: 최근 3일 모두 음수면 그 합, 아니면 0/ None.
        recent_3 = daily_returns(kodex_series, kodex_idx, SHORT_WEAKNESS_WINDOW)
        if len(recent_3) == SHORT_WEAKNESS_WINDOW and all(r < 0 for r in recent_3):
            short_weak = sum(recent_3)
        else:
            short_weak = 0.0 if recent_3 else None
        # breadth_deterioration_proxy: down_ratio - up_ratio.
        breadth_det = (
            (down_ratio - up_ratio)
            if (down_ratio is not None and up_ratio is not None)
            else None
        )

        market_rows.append(
            MarketRiskFeatureRow(
                asof=market_row.asof,
                kodex200_return_1d=market_row.kodex200_return_1d,
                kodex200_return_5d=market_row.kodex200_return_5d,
                kodex200_return_20d=market_row.kodex200_return_20d,
                kospi_return_1d=market_row.kospi_return_1d,
                kospi_return_5d=market_row.kospi_return_5d,
                kospi_return_20d=market_row.kospi_return_20d,
                etf_universe_up_count=up,
                etf_universe_down_count=down,
                etf_universe_flat_count=flat,
                etf_universe_up_ratio=up_ratio,
                etf_universe_down_ratio=down_ratio,
                etf_universe_median_return_1d=median_1d,
                etf_universe_median_return_5d=median_5d,
                nav_discount_avg=nav_avg,
                nav_discount_abs_avg=nav_abs_avg,
                nav_discount_extreme_count=nav_extreme,
                volatility_20d_market_proxy=market_row.volatility_20d_market_proxy,
                drawdown_20d_market_proxy=market_row.drawdown_20d_market_proxy,
                distance_from_20d_high=market_row.distance_from_20d_high,
                volatility_expansion_20d=vol_expansion,
                down_day_volume_ratio=down_day_vol_ratio,
                large_negative_day_proxy=large_neg,
                short_term_weakness_proxy=short_weak,
                breadth_deterioration_proxy=breadth_det,
            )
        )

    summary = {
        "asof_count": len(asofs),
        "etf_universe_count": len(tickers),
        "etf_series_missing": missing_series_count,
        "etf_feature_row_count": len(etf_rows_all),
        "market_risk_row_count": len(market_rows),
        "asof_without_kospi": missing_kospi,
    }
    return FeatureBuildResult(
        etf_rows=etf_rows_all,
        market_rows=market_rows,
        asofs=asofs,
        missing_data_summary=summary,
    )


__all__ = [
    "FeatureBuildResult",
    "build_features",
]
