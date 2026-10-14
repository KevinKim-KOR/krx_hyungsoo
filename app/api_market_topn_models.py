"""Market Discovery API — Pydantic response/request 모델."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from app.stored_volume_evidence import StoredVolumeEvidence


class MarketTopNEntry(BaseModel):
    # 결측은 None 통과, 강제 변환 / 0·"" / 0.0 fallback 절대 금지 — Frontend 가 "-" 표시.
    rank: Optional[int] = None
    ticker: Optional[str] = None
    name: Optional[str] = None
    return_pct: Optional[float] = None
    basis_start_date: Optional[str] = None
    basis_end_date: Optional[str] = None
    # 2026-05-18 후보 정제 1차 — ETF 이름 기반 상품 태그 (inverse / leveraged / synthetic / futures).
    tags: list[str] = []


class MarketTopNFilters(BaseModel):
    exclude_inverse: bool = True
    exclude_leveraged: bool = True
    exclude_synthetic: bool = True
    exclude_futures: bool = True


class MarketLatestRefresh(BaseModel):
    refresh_id: Optional[str] = None
    source: Optional[str] = None
    asof: Optional[str] = None
    attempted_count: Optional[int] = None
    success_count: Optional[int] = None
    fail_count: Optional[int] = None
    runtime_seconds: Optional[float] = None
    error_summary: Optional[str] = None
    created_at: Optional[str] = None


class MarketPeriodReturn(BaseModel):
    return_pct: Optional[float] = None
    basis_start_date: Optional[str] = None
    basis_end_date: Optional[str] = None


class MarketReturns(BaseModel):
    daily: Optional[MarketPeriodReturn] = None
    one_month: Optional[MarketPeriodReturn] = None
    three_month: Optional[MarketPeriodReturn] = None
    # 2026-06-08 — 표시 전용 신규 기간 (UI 요청). 정렬 X.
    six_month: Optional[MarketPeriodReturn] = None
    twelve_month: Optional[MarketPeriodReturn] = None
    three_year: Optional[MarketPeriodReturn] = None


class ShortTermMomentumStartDates(BaseModel):
    five_d: Optional[str] = None
    ten_d: Optional[str] = None
    twenty_d: Optional[str] = None


class ShortTermMomentumPayload(BaseModel):
    status: str  # ok / unavailable
    return_5d_pct: Optional[float] = None
    return_10d_pct: Optional[float] = None
    return_20d_pct: Optional[float] = None
    excess_vs_kodex200_5d_pctp: Optional[float] = None
    excess_vs_kodex200_10d_pctp: Optional[float] = None
    excess_vs_kodex200_20d_pctp: Optional[float] = None
    start_dates: Optional[ShortTermMomentumStartDates] = None
    end_date: Optional[str] = None
    message: Optional[str] = None


class DailyReturnCheckPayload(BaseModel):
    status: str  # ok / warning / unavailable
    daily_return_pct: Optional[float] = None
    flag: Optional[str] = None
    threshold_pct: Optional[float] = None
    message: Optional[str] = None


class NavDiscountPayload(BaseModel):
    status: str  # ok / unavailable / partial
    asof: Optional[str] = None
    nav: Optional[float] = None
    market_price: Optional[float] = None
    discount_rate_pct: Optional[float] = None
    flag: Optional[str] = None
    source: Optional[str] = None
    message: Optional[str] = None


class DataQualityPayload(BaseModel):
    status: str  # ok / warning / unavailable
    daily_return_check: DailyReturnCheckPayload
    nav_discount: NavDiscountPayload
    warnings: list[str] = []


class MarketCandidateExcessReturn(BaseModel):
    vs_kodex200_1m_pctp: Optional[float] = None
    vs_kodex200_3m_pctp: Optional[float] = None
    vs_kospi_1m_pctp: Optional[float] = None
    vs_kospi_3m_pctp: Optional[float] = None


class MarketCandidate(BaseModel):
    """통합 후보 테이블 entry — 3 기간 수익률 + 선택된 basis 의 요약 필드."""

    rank: Optional[int] = None
    ticker: Optional[str] = None
    name: Optional[str] = None
    tags: list[str] = []
    selected_return_pct: Optional[float] = None
    selected_basis_start_date: Optional[str] = None
    selected_basis_end_date: Optional[str] = None
    returns: MarketReturns = MarketReturns()
    # 2026-05-22 Market Regime & Benchmark Context 1차 — KODEX200/KOSPI 대비
    # 1m/3m 초과수익 (percentage point). KOSPI 데이터 없으면 vs_kospi_* 는 null.
    excess_return: Optional["MarketCandidateExcessReturn"] = None
    # 2026-06-01 Market Discovery Evidence Closeout 1차 — 단기 흐름 + 데이터 품질.
    short_term_momentum: Optional[ShortTermMomentumPayload] = None
    data_quality: Optional[DataQualityPayload] = None
    # 2026-06-20 ML 축1 — 상대상승 참고점수 v0 (지시문 §10).
    # snapshot 부재 / 점수 미생성 시 null. UI 가 점수 정렬 + "고점 대비" 컬럼 +
    # 점수 근거 표시에 사용. 매매 판단 아님 — UI 측 USER_NOTICE 동행 필수.
    relative_upside_score: Optional[float] = None
    drawdown_20d: Optional[float] = None
    relative_upside_reasons: list[str] = []


MarketCandidate.model_rebuild()


# ─── Market Regime & Benchmark Context (지시문 §9.1) ──────────────────


class MarketContextKodex200(BaseModel):
    status: str  # ok / unavailable
    return_20d_pct: Optional[float] = None
    return_60d_pct: Optional[float] = None
    return_1m_pct: Optional[float] = None
    return_3m_pct: Optional[float] = None
    close: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    ma20_position: Optional[str] = None  # above / below
    ma60_position: Optional[str] = None
    # 2026-07-29 POC3-01 — 기준선 대비 거리(%). (close-ma)/ma*100 저장값 단순 산술.
    ma20_distance_pct: Optional[float] = None
    ma60_distance_pct: Optional[float] = None


class MarketContextKospi(BaseModel):
    status: str  # ok / stale / unavailable
    return_20d_pct: Optional[float] = None
    return_60d_pct: Optional[float] = None
    return_1m_pct: Optional[float] = None
    return_3m_pct: Optional[float] = None
    # 2026-08-03 POC3-06 §6.2 — KOSPI 관찰값 additive 확장. 값은 공통 composer 에서
    # 1회 계산(설계자 Q1). daily/1y 는 수익률, high_52w_gap_pct 는 "고점 대비 음수%"
    # (고점이면 0). 비율(%) 표기 아님. 계산 불가 시 None(자료 없음).
    daily_return_pct: Optional[float] = None
    return_1y_pct: Optional[float] = None
    high_52w_gap_pct: Optional[float] = None
    as_of_date: Optional[str] = None
    # POC3-02D-OPS-02 3-4 (설계자 Q4~Q6 · 2026-09-28) — 화면 상태 **선택** 필드. 기존 필드
    # 의미 불변. `trading_day_lag` 는 C7 공용 거래일 계산(캘린더 축)이다 — KODEX200
    # 적재일 축으로 잰 운영 판정 lag 와 다른 값이다.
    display_state: Optional[str] = None
    trading_day_lag: Optional[int] = None
    today_is_trading_day: Optional[bool] = None


class MarketContextRegimeStreak(BaseModel):
    # 2026-08-03 POC3-06 §6.2 — 현재 국면 라벨이 이어진 거래일 수(설계자 Q4).
    # 기존 국면 규칙을 과거 KODEX200 시계열에 재적용해 역산. 계산 불가 시 None.
    # at_least=True 면 저장 이력 시작점까지 같은 라벨(= N거래일 이상).
    regime_code: Optional[str] = None
    streak_days: Optional[int] = None
    at_least: bool = False


class MarketContextResponse(BaseModel):
    status: str  # ok / partial / unavailable
    asof: Optional[str] = None
    primary_benchmark: str = "KODEX200"
    regime_label: str  # 상승장 / 보합장 / 하락장 / 판정불가
    regime_code: str  # bull / neutral / bear / unavailable
    regime_score: Optional[int] = None
    regime_reasons: list[str] = []
    kodex200: MarketContextKodex200
    kospi: MarketContextKospi
    # 2026-08-03 POC3-06 — 국면 지속 거래일 수 (additive, 기존 필드 불변).
    regime_streak: Optional[MarketContextRegimeStreak] = None
    warnings: list[str] = []


# 2026-07-03 Market Risk Reference v1 — KODEX200 + VIX 일별 맥락 (지시문 §7).
# 기존 필드 삭제·이름 변경 없음. 최상위에 market_risk_reference 하나만 추가.


class MarketRiskRecentPoint(BaseModel):
    date: str
    close: float


class MarketRiskKodex200(BaseModel):
    availability: str  # available / unavailable
    as_of_date: Optional[str] = None
    close: Optional[float] = None
    change_1d_pct: Optional[float] = None
    recent_20d_series: list[MarketRiskRecentPoint] = []
    # 지시문 §8.2 — 상세 노출용 각 시계열 최초·최종 관측일 (전체 저장 범위).
    series_first_date: Optional[str] = None
    series_last_date: Optional[str] = None


class MarketRiskVixFreshness(BaseModel):
    """POC5-12 — PC 화면 응답만 · 미국 동부 마감 기준 VIX 최신성(app/pc_vix_refresh.vix_freshness)."""

    state: str  # fresh / one_weekday_behind / update_check / date_check
    compare_date: Optional[str] = (
        None  # 비교일 E(미국 마감 기준 · 주말이면 직전 금요일)
    )
    weekdays_behind: Optional[int] = None  # D 다음 날 ~ E 평일 수 · date_check 면 None


class MarketRiskVix(BaseModel):
    availability: str
    as_of_date: Optional[str] = None
    close: Optional[float] = None
    change_1d_pct: Optional[float] = None
    change_5d_pct: Optional[float] = None
    recent_20d_series: list[MarketRiskRecentPoint] = []
    series_first_date: Optional[str] = None
    series_last_date: Optional[str] = None
    freshness: Optional[MarketRiskVixFreshness] = None  # POC5-12 선택 필드


class MarketRiskReference(BaseModel):
    kodex200: MarketRiskKodex200
    vix: MarketRiskVix


class MarketTopNResponse(BaseModel):
    status: str  # ok / missing / empty / invalid
    error: Optional[str] = None
    asof: Optional[str] = None
    source: Optional[str] = None
    n: Optional[int] = None
    # 2026-05-18 통합 후보 테이블 1차 — basis: daily / one_month / three_month.
    basis: Optional[str] = None
    # 2026-05-19 Grid 사용성 FIX — 정렬 방향: desc / asc.
    order: Optional[str] = None
    universe_count: Optional[int] = None
    price_success_count: Optional[int] = None
    price_fail_count: Optional[int] = None
    latest_refresh: Optional[MarketLatestRefresh] = None
    runtime_seconds: Optional[float] = None
    # 통합 후보 테이블 (frontend 기본 렌더 소스).
    candidates: list[MarketCandidate] = []
    # 호환용 — 기존 분리 테이블도 유지 (frontend 사용 안 함).
    daily_topn: list[MarketTopNEntry] = []
    one_month_topn: list[MarketTopNEntry] = []
    three_month_topn: list[MarketTopNEntry] = []
    period_exclusions: dict[str, dict[str, int]] = {}
    # 2026-05-18 후보 정제 1차 — 활성 필터 / 기간별 필터 제외 집계.
    filters: MarketTopNFilters = MarketTopNFilters()
    filter_exclusions: dict[str, dict[str, int]] = {}
    candidate_filter_exclusions: dict[str, int] = {}
    topn_caveat: Optional[str] = None
    # 2026-05-22 — Market Regime & Benchmark Context (지시문 §9.1).
    # ok/partial/unavailable + KODEX200 (필수) + KOSPI (보조). status=missing/
    # empty/invalid 인 경우 null 로 노출.
    market_context: Optional[MarketContextResponse] = None
    # 2026-06-20 ML 축1 — 상대상승 참고점수 v0 top-level 상태 (지시문 §10).
    # ok = 후보 중 일부 또는 전부에 점수 부여됨.
    # unavailable = snapshot 부재 또는 모든 후보 점수 null (학습 데이터 부족 등).
    # failed = snapshot 손상 또는 로드 실패. 어느 경우든 후보 응답 자체는 유지.
    relative_upside_score_status: Optional[str] = None
    relative_upside_score_asof_date: Optional[str] = None
    relative_upside_score_generated_at: Optional[str] = None
    relative_upside_score_user_notice: Optional[str] = None
    # 2026-07-03 Market Risk Reference v1 — 최상위 신규 필드 (지시문 §7).
    # 항상 존재하며, 데이터 부재 시 availability="unavailable" 로 응답.
    market_risk_reference: Optional[MarketRiskReference] = None
    # POC5-09 — KODEX200 한 종목의 저장 거래량 관찰값(PC 「오늘의 투자 점검」 · 선택 필드).
    # KOSPI 지수 거래량이 아니다.
    kodex200_stored_volume: Optional[StoredVolumeEvidence] = None


class MarketRefreshResponse(BaseModel):
    # accepted / running / skipped_cooldown / failed_to_start / not_needed(POC5-12 scope=vix 대상 없음)
    # / vix_retry_running(POC5-12 'VIX 다시 받기' 실행 중이라 거절 · refresh_id = 그 재시도 id)
    status: str
    refresh_id: Optional[str] = None
    message: str
    cooldown_remaining_seconds: int = 0


class MarketRefreshVixRetry(BaseModel):
    """POC5-12 — 'VIX 다시 받기' 표식 · 결과(market_refresh_state 의 vix_retry 행)."""

    needed: bool
    status: Optional[str] = None  # needed / running / completed / failed / cleared
    refresh_id: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error_summary: Optional[str] = None
    vix_as_of_date: Optional[str] = None  # 다시 받기 뒤 VIX 저장 기준일


class MarketRefreshStatusResponse(BaseModel):
    status: str  # idle / running / completed / failed / skipped_cooldown
    refresh_id: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    asof: Optional[str] = None
    universe_count: Optional[int] = None
    price_attempted_count: Optional[int] = None
    price_success_count: Optional[int] = None
    price_fail_count: Optional[int] = None
    runtime_seconds: Optional[float] = None
    error_summary: Optional[str] = None
    cooldown_remaining_seconds: int = 0
    vix_retry: Optional[MarketRefreshVixRetry] = None  # POC5-12 선택 필드
