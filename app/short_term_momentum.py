"""단기 흐름 + 일간 급등/급락 데이터 품질 플래그 (POC2 — 2026-06-01).

Market Discovery Evidence Closeout 1차 — 지시문 §5 / §6 / §10.

책임:
- 후보 ETF 별 최근 5/10/20 거래일 수익률 계산.
- KODEX200 대비 5/10/20 거래일 초과수익 계산.
- 일간 수익률 ±10% 임계 플래그 (data_quality.daily_return_check).

본 모듈은 시장 데이터 read 만 사용 (SQLite 직접 접근 X).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.market_data_store import DEFAULT_DB_PATH, fetch_price_history

KODEX200_TICKER = "069500"

# 일간 급등 / 급락 임계 (지시문 §6).
DAILY_SURGE_THRESHOLD_PCT = 10.0
DAILY_DROP_THRESHOLD_PCT = -10.0


@dataclass(frozen=True)
class ShortTermMomentum:
    """단기 흐름 결과. 가격 이력 부족 시 status='unavailable'."""

    status: str  # ok / unavailable
    return_5d_pct: Optional[float] = None
    return_10d_pct: Optional[float] = None
    return_20d_pct: Optional[float] = None
    excess_vs_kodex200_5d_pctp: Optional[float] = None
    excess_vs_kodex200_10d_pctp: Optional[float] = None
    excess_vs_kodex200_20d_pctp: Optional[float] = None
    start_date_5d: Optional[str] = None
    start_date_10d: Optional[str] = None
    start_date_20d: Optional[str] = None
    end_date: Optional[str] = None
    message: Optional[str] = None


@dataclass(frozen=True)
class DailyReturnCheck:
    """일간 수익률 데이터 품질 체크."""

    status: str  # ok / warning / unavailable
    daily_return_pct: Optional[float] = None
    flag: Optional[str] = None  # daily_surge_check_needed / daily_drop_check_needed
    threshold_pct: Optional[float] = None
    message: Optional[str] = None


def _window_return_pct(series: list[tuple[str, float]], window: int) -> Optional[float]:
    """series 의 마지막 window+1 거래일 사이 수익률 (%). 부족 시 None."""
    if len(series) < window + 1:
        return None
    start_close = series[-(window + 1)][1]
    end_close = series[-1][1]
    if start_close <= 0:
        return None
    return (end_close - start_close) / start_close * 100.0


def _window_start_date(series: list[tuple[str, float]], window: int) -> Optional[str]:
    if len(series) < window + 1:
        return None
    return series[-(window + 1)][0]


MIN_TRADING_DAYS_FOR_OK = 21  # 20거래일 수익률 산출에 필요한 close 개수.


def compute_short_term_momentum(
    ticker: str,
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> ShortTermMomentum:
    """후보 ETF 의 단기 흐름 + KODEX200 대비 초과수익 계산 (지시문 §5).

    데이터 부족 시 status='unavailable' + 부족 메시지. 0 임의 대체 없음.

    2026-06-03 FIX (검증자 A-1 NOTE) — 응답 계약 정합. status='ok' 는 5/10/20
    거래일 수익률 + KODEX200 대비 초과수익이 모두 산출 가능한 경우로 한정.
    가장 긴 윈도우 (20거래일 = 21개 close) 가 부족하거나 KODEX200 시계열이
    같은 길이를 채우지 못하면 status='unavailable'. 부분 ok + null 필드 금지.
    """
    series = fetch_price_history(ticker, db_path=db_path)
    if len(series) < MIN_TRADING_DAYS_FOR_OK:
        return ShortTermMomentum(
            status="unavailable",
            message=(
                "insufficient price history "
                f"(need >={MIN_TRADING_DAYS_FOR_OK} trading days)"
            ),
        )

    bench = fetch_price_history(KODEX200_TICKER, db_path=db_path)
    if len(bench) < MIN_TRADING_DAYS_FOR_OK:
        return ShortTermMomentum(
            status="unavailable",
            message=(
                "insufficient KODEX200 benchmark history "
                f"(need >={MIN_TRADING_DAYS_FOR_OK} trading days)"
            ),
        )

    r5 = _window_return_pct(series, 5)
    r10 = _window_return_pct(series, 10)
    r20 = _window_return_pct(series, 20)
    b5 = _window_return_pct(bench, 5)
    b10 = _window_return_pct(bench, 10)
    b20 = _window_return_pct(bench, 20)

    return ShortTermMomentum(
        status="ok",
        return_5d_pct=r5,
        return_10d_pct=r10,
        return_20d_pct=r20,
        excess_vs_kodex200_5d_pctp=(
            (r5 - b5) if (r5 is not None and b5 is not None) else None
        ),
        excess_vs_kodex200_10d_pctp=(
            (r10 - b10) if (r10 is not None and b10 is not None) else None
        ),
        excess_vs_kodex200_20d_pctp=(
            (r20 - b20) if (r20 is not None and b20 is not None) else None
        ),
        start_date_5d=_window_start_date(series, 5),
        start_date_10d=_window_start_date(series, 10),
        start_date_20d=_window_start_date(series, 20),
        end_date=series[-1][0],
    )


def compute_short_term_momentum_batch(
    tickers: list[str],
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, ShortTermMomentum]:
    """여러 ticker 의 단기 흐름 계산 — KODEX200 시계열은 1회만 fetch (효율).

    응답 빌더 (GET /market/topn/latest) 가 사용. ticker 마다 외부 fetch 없음.

    2026-06-03 FIX (검증자 A-1 NOTE) — 단일 호출과 동일한 status 판정 규칙.
    20거래일 이력 또는 KODEX200 benchmark 이력 부족 시 status='unavailable'.
    """
    bench = fetch_price_history(KODEX200_TICKER, db_path=db_path)
    bench_ok = len(bench) >= MIN_TRADING_DAYS_FOR_OK
    b5 = _window_return_pct(bench, 5) if bench_ok else None
    b10 = _window_return_pct(bench, 10) if bench_ok else None
    b20 = _window_return_pct(bench, 20) if bench_ok else None

    out: dict[str, ShortTermMomentum] = {}
    for ticker in tickers:
        series = fetch_price_history(ticker, db_path=db_path)
        if len(series) < MIN_TRADING_DAYS_FOR_OK:
            out[ticker] = ShortTermMomentum(
                status="unavailable",
                message=(
                    "insufficient price history "
                    f"(need >={MIN_TRADING_DAYS_FOR_OK} trading days)"
                ),
            )
            continue
        if not bench_ok:
            out[ticker] = ShortTermMomentum(
                status="unavailable",
                message=(
                    "insufficient KODEX200 benchmark history "
                    f"(need >={MIN_TRADING_DAYS_FOR_OK} trading days)"
                ),
            )
            continue
        r5 = _window_return_pct(series, 5)
        r10 = _window_return_pct(series, 10)
        r20 = _window_return_pct(series, 20)
        out[ticker] = ShortTermMomentum(
            status="ok",
            return_5d_pct=r5,
            return_10d_pct=r10,
            return_20d_pct=r20,
            excess_vs_kodex200_5d_pctp=(
                (r5 - b5) if (r5 is not None and b5 is not None) else None
            ),
            excess_vs_kodex200_10d_pctp=(
                (r10 - b10) if (r10 is not None and b10 is not None) else None
            ),
            excess_vs_kodex200_20d_pctp=(
                (r20 - b20) if (r20 is not None and b20 is not None) else None
            ),
            start_date_5d=_window_start_date(series, 5),
            start_date_10d=_window_start_date(series, 10),
            start_date_20d=_window_start_date(series, 20),
            end_date=series[-1][0],
        )
    return out


def compute_daily_return_check(
    ticker: str,
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> DailyReturnCheck:
    """일간 수익률 ±10% 임계 플래그 (지시문 §6).

    데이터 품질 확인용. 매수/매도 판단 아님.
    """
    series = fetch_price_history(ticker, db_path=db_path)
    if len(series) < 2:
        return DailyReturnCheck(
            status="unavailable",
            message="insufficient price history (need >=2 trading days)",
        )
    prev_close = series[-2][1]
    last_close = series[-1][1]
    if prev_close <= 0:
        return DailyReturnCheck(status="unavailable", message="invalid prev close")
    daily_pct = (last_close - prev_close) / prev_close * 100.0

    if daily_pct >= DAILY_SURGE_THRESHOLD_PCT:
        return DailyReturnCheck(
            status="warning",
            daily_return_pct=daily_pct,
            flag="daily_surge_check_needed",
            threshold_pct=DAILY_SURGE_THRESHOLD_PCT,
            message="일간 수익률 +10% 이상. 가격 데이터 또는 괴리율 확인 필요.",
        )
    if daily_pct <= DAILY_DROP_THRESHOLD_PCT:
        return DailyReturnCheck(
            status="warning",
            daily_return_pct=daily_pct,
            flag="daily_drop_check_needed",
            threshold_pct=DAILY_DROP_THRESHOLD_PCT,
            message="일간 수익률 -10% 이하. 가격 데이터 또는 분배금/권리락 확인 필요.",
        )
    return DailyReturnCheck(
        status="ok",
        daily_return_pct=daily_pct,
        flag=None,
    )
