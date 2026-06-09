"""GET /ml/readiness/latest — read-only ML feature 적재 상태 조회 (2026-06-08).

지시문 §6.6 — ML readiness 화면이 실제 적재된 feature 기준으로 표시하도록 backend
지원. 본 API 는:
- etf_ml_feature_daily / market_risk_feature_daily row 수 / latest asof 만 read.
- 외부 source 호출 X / refresh X / 매수·매도 판단 X.
- 표시 대상 7축의 정적 메타 + DB 상태 결합.

표시 7축 (지시문 §6.6 '포함'):
1. ETF 가격 시계열
2. NAV / 괴리율 feature
3. 거래량 / 유동성 feature
4. 시장지수 feature
5. ETF universe 시장 폭 feature
6. 변동성 feature
7. 조정장 전조 feature

제외 (지시문 §6.6 '제외' — 화면에서 표시하지 않음):
- CNN Fear & Greed / VKOSPI / 외국인·기관 수급 / KOSPI 전체 시장 폭 / 구성종목 가격 시계열.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.market_data_store import DEFAULT_DB_PATH
from app.ml_feature_store import fetch_readiness

router = APIRouter()


class MlReadinessAxis(BaseModel):
    label: str
    status: str  # available / partial / empty
    note: str


class MlReadinessResponse(BaseModel):
    status: str  # ok
    etf_feature_row_count: int
    etf_distinct_asof_count: int
    etf_latest_asof: Optional[str] = None
    market_risk_row_count: int
    market_risk_latest_asof: Optional[str] = None
    axes: list[MlReadinessAxis]


def _build_axes(
    *,
    etf_count: int,
    market_count: int,
) -> list[MlReadinessAxis]:
    """7축 상태 — 실제 row 수 기준.

    개별 컬럼 가용성을 row 단위로 분리 체크하지 않고, store 적재 여부로 일괄 분류.
    "empty" = row 0 / "partial" = row > 0 이지만 universe 일부 / "available" = 양쪽 모두 적재.
    """
    base_status = (
        "available"
        if etf_count > 0 and market_count > 0
        else ("partial" if (etf_count > 0 or market_count > 0) else "empty")
    )
    return [
        MlReadinessAxis(
            label="ETF 가격 시계열",
            status=base_status,
            note=(
                f"etf_ml_feature_daily {etf_count}건 — return 5/10/20d + "
                "close/volume 적재"
                if etf_count > 0
                else "etf_ml_feature_daily 미적재"
            ),
        ),
        MlReadinessAxis(
            label="NAV / 괴리율 feature",
            status=base_status,
            note=(
                "etf_ml_feature_daily.nav / nav_market_price / discount_rate_pct + "
                "nav_status 컬럼 — latest available ≤ asof 정책"
                if etf_count > 0
                else "미적재"
            ),
        ),
        MlReadinessAxis(
            label="거래량 / 유동성 feature",
            status=base_status,
            note=(
                "etf_ml_feature_daily.volume + volume_ratio_20d (20일 평균 대비)"
                if etf_count > 0
                else "미적재"
            ),
        ),
        MlReadinessAxis(
            label="시장지수 feature",
            status="available" if market_count > 0 else "empty",
            note=(
                f"market_risk_feature_daily {market_count}건 — KODEX200 / KOSPI "
                "return 1/5/20d"
                if market_count > 0
                else "market_risk_feature_daily 미적재"
            ),
        ),
        MlReadinessAxis(
            label="ETF universe 시장 폭 feature",
            status="available" if market_count > 0 else "empty",
            note=(
                "etf_universe_up/down/flat_count + ratio + median_return_1d/5d"
                if market_count > 0
                else "미적재"
            ),
        ),
        MlReadinessAxis(
            label="변동성 feature",
            status=base_status,
            note=(
                "etf_ml_feature_daily.volatility_20d (일간 수익률 표준편차) + "
                "market_risk_feature_daily.volatility_20d_market_proxy / "
                "volatility_expansion_20d"
                if etf_count > 0 and market_count > 0
                else "일부만 적재"
            ),
        ),
        MlReadinessAxis(
            label="조정장 전조 feature",
            status="available" if market_count > 0 else "empty",
            note=(
                "distance_from_20d_high + down_day_volume_ratio + "
                "large_negative_day_proxy + short_term_weakness_proxy + "
                "breadth_deterioration_proxy (proxy raw 값. label/threshold 미확정)"
                if market_count > 0
                else "market_risk_feature_daily 미적재"
            ),
        ),
    ]


@router.get("/ml/readiness/latest", response_model=MlReadinessResponse)
def get_ml_readiness_latest() -> MlReadinessResponse:
    """저장된 etf_ml_feature_daily / market_risk_feature_daily 의 row 수 / latest
    asof 를 read-only 로 반환. 외부 source 호출 X / refresh X."""
    r = fetch_readiness(db_path=DEFAULT_DB_PATH)
    axes = _build_axes(
        etf_count=r.etf_row_count,
        market_count=r.market_risk_row_count,
    )
    return MlReadinessResponse(
        status="ok",
        etf_feature_row_count=r.etf_row_count,
        etf_distinct_asof_count=r.etf_distinct_asof_count,
        etf_latest_asof=r.etf_latest_asof,
        market_risk_row_count=r.market_risk_row_count,
        market_risk_latest_asof=r.market_risk_latest_asof,
        axes=axes,
    )
