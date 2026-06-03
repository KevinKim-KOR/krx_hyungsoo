// PC Market Discovery — Evidence 타입 정의.
//
// 본 모듈은 MarketCandidate 1건과 MarketTopNResponse 1건을 둘러싸는
// "근거 (evidence)" 계열 타입만 둔다 — 호출 함수는 두지 않는다.
//
// 추가 이력:
// - Market Regime & Benchmark Context (2026-05-22)
//   · MarketCandidateExcessReturn (vs KODEX200 / vs KOSPI 초과수익률).
//   · MarketContext + MarketRegimeCode + MarketContextStatus + KODEX200/KOSPI 보조.
// - Market Discovery Evidence Closeout 1차 (2026-06-01)
//   · short_term_momentum (5d / 10d / 20d 단기 흐름 + KODEX200 대비 초과).
//   · data_quality (daily_return_check + nav_discount + warnings).
//
// NAV / 괴리율 source 진단은 본 모듈의 책임이 아니다 — NavDiscountPayload 는
// unavailable 인터페이스만 정의하고 source 구현은 별도 STEP 으로 분리한다.

// ─── Short-term momentum (5d / 10d / 20d) ───────────────────────────

export interface ShortTermMomentumStartDates {
  five_d?: string | null;
  ten_d?: string | null;
  twenty_d?: string | null;
}

export interface ShortTermMomentumPayload {
  status: "ok" | "unavailable";
  return_5d_pct?: number | null;
  return_10d_pct?: number | null;
  return_20d_pct?: number | null;
  excess_vs_kodex200_5d_pctp?: number | null;
  excess_vs_kodex200_10d_pctp?: number | null;
  excess_vs_kodex200_20d_pctp?: number | null;
  start_dates?: ShortTermMomentumStartDates | null;
  end_date?: string | null;
  message?: string | null;
}

// ─── Data quality (daily return surge/drop + NAV discount) ──────────

export type DailyReturnFlag =
  | "daily_surge_check_needed"
  | "daily_drop_check_needed";

export interface DailyReturnCheckPayload {
  status: "ok" | "warning" | "unavailable";
  daily_return_pct?: number | null;
  flag?: DailyReturnFlag | null;
  threshold_pct?: number | null;
  message?: string | null;
}

export type DiscountFlag = "discount_check_needed" | "discount_warning";

export interface NavDiscountPayload {
  status: "ok" | "unavailable" | "partial";
  asof?: string | null;
  nav?: number | null;
  market_price?: number | null;
  discount_rate_pct?: number | null;
  flag?: DiscountFlag | null;
  source?: string | null;
  message?: string | null;
}

export interface DataQualityPayload {
  status: "ok" | "warning" | "unavailable";
  daily_return_check: DailyReturnCheckPayload;
  nav_discount: NavDiscountPayload;
  warnings: string[];
}

// ─── Market Regime & Benchmark Context (2026-05-22) ─────────────────

export interface MarketCandidateExcessReturn {
  vs_kodex200_1m_pctp?: number | null;
  vs_kodex200_3m_pctp?: number | null;
  vs_kospi_1m_pctp?: number | null;
  vs_kospi_3m_pctp?: number | null;
}

export type MarketRegimeCode = "bull" | "neutral" | "bear" | "unavailable";
export type MarketContextStatus = "ok" | "partial" | "unavailable";

export interface MarketContextKodex200 {
  status: "ok" | "unavailable";
  return_20d_pct?: number | null;
  return_60d_pct?: number | null;
  return_1m_pct?: number | null;
  return_3m_pct?: number | null;
  close?: number | null;
  ma20?: number | null;
  ma60?: number | null;
  ma20_position?: "above" | "below" | null;
  ma60_position?: "above" | "below" | null;
}

export interface MarketContextKospi {
  status: "ok" | "unavailable";
  return_20d_pct?: number | null;
  return_60d_pct?: number | null;
  return_1m_pct?: number | null;
  return_3m_pct?: number | null;
}

export interface MarketContext {
  status: MarketContextStatus;
  asof?: string | null;
  primary_benchmark: string;
  regime_label: string;
  regime_code: MarketRegimeCode;
  regime_score?: number | null;
  regime_reasons: string[];
  kodex200: MarketContextKodex200;
  kospi: MarketContextKospi;
  warnings: string[];
}
