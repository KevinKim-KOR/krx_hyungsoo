// PC Market Discovery — SQLite 직접 계산 + refresh background job.
// 2026-05-18 변경: 시장 데이터 SSOT = SQLite. JSON artifact 폐기.
// GET  /market/topn/latest    — SQLite 에서 직접 TOP N 계산 (read-only).
// POST /market/refresh        — FDR 수집을 background job 으로 트리거 (ETF universe + 가격).
// GET  /market/refresh/status — 현재/마지막 refresh 상태.
// (holdings naver 시세 갱신은 별도 endpoint `POST /holdings/market/refresh` —
//  holdings.ts 의 refreshMarket 참조.)
//
// MarketCandidate 1건이 들고 다니는 evidence 계열 (excess_return, short_term_momentum,
// data_quality) + 상위 응답 market_context 는 marketEvidence.ts 에서 import 한다.

import { request } from "./core";
import type {
  DataQualityPayload,
  MarketCandidateExcessReturn,
  MarketContext,
  ShortTermMomentumPayload,
} from "./marketEvidence";

export type MarketTopNStatus = "ok" | "missing" | "empty" | "invalid";

// 결측 필드는 백엔드가 그대로 null 로 통과시킨다 (지시문 §6 "0% 보정 금지").
// frontend 도 모든 필드를 nullable 로 받아 "-" 표시한다.
//
// 2026-05-18 후보 정제 1차 — tags: ETF 이름 기반 상품 태그 배열.
// 가능 값: "inverse" | "leveraged" | "synthetic" | "futures"
// 일반 후보는 빈 배열.
export type MarketProductTag = "inverse" | "leveraged" | "synthetic" | "futures";

// 2026-05-18 통합 후보 테이블 1차 — 조회 기준 basis.
// 2026-05-19 Grid 사용성 FIX — 이전 표현 (일간 급등 / 1개월 모멘텀 / 3개월 추세) 라벨 상수
// MARKET_BASIS_LABEL 제거. 컬럼 라벨은 MARKET_BASIS_COLUMN_LABEL 만 사용 (검증자 B-6 NOTE 반영).
export type MarketBasis = "daily" | "one_month" | "three_month";

export const DEFAULT_MARKET_BASIS: MarketBasis = "one_month";

// 2026-05-19 Grid 사용성 FIX — 정렬 방향.
export type MarketOrder = "desc" | "asc";
export const DEFAULT_MARKET_ORDER: MarketOrder = "desc";

// 컬럼 헤더 라벨 (Grid 사용성 FIX § 4.2 — 통일된 표현).
export const MARKET_BASIS_COLUMN_LABEL: Record<MarketBasis, string> = {
  daily: "일간 수익률",
  one_month: "1개월 수익률",
  three_month: "3개월 수익률",
};

export interface MarketPeriodReturn {
  return_pct?: number | null;
  basis_start_date?: string | null;
  basis_end_date?: string | null;
}

export interface MarketReturns {
  daily?: MarketPeriodReturn | null;
  one_month?: MarketPeriodReturn | null;
  three_month?: MarketPeriodReturn | null;
  // 2026-06-08 — 표시 전용 신규 기간 (UI 요청). basis 정렬은 daily / 1m / 3m 만.
  six_month?: MarketPeriodReturn | null;
  twelve_month?: MarketPeriodReturn | null;
  three_year?: MarketPeriodReturn | null;
}

export interface MarketCandidate {
  rank?: number | null;
  ticker?: string | null;
  name?: string | null;
  tags?: MarketProductTag[];
  selected_return_pct?: number | null;
  selected_basis_start_date?: string | null;
  selected_basis_end_date?: string | null;
  returns?: MarketReturns;
  // 2026-05-22 — Market Regime & Benchmark Context 1차.
  excess_return?: MarketCandidateExcessReturn | null;
  // 2026-06-01 — Market Discovery Evidence Closeout 1차.
  short_term_momentum?: ShortTermMomentumPayload | null;
  data_quality?: DataQualityPayload | null;
  // 2026-06-20 ML 축1 — 상대상승 참고점수 v0.
  // score 는 0~100 (상대 비교용). drawdown 은 음수 표기 (close/peak-1).
  // reasons 는 사람 언어 짧은 요약 최대 3개. 점수 미생성 시 null/빈배열.
  relative_upside_score?: number | null;
  drawdown_20d?: number | null;
  relative_upside_reasons?: string[];
}

// 2026-06-20 ML 축1 — 응답 top-level 의 상대상승 참고점수 상태.
export type RelativeUpsideScoreStatus = "ok" | "unavailable" | "failed";

export interface MarketTopNEntry {
  rank?: number | null;
  ticker?: string | null;
  name?: string | null;
  return_pct?: number | null;
  basis_start_date?: string | null;
  basis_end_date?: string | null;
  tags?: MarketProductTag[];
}

export interface MarketTopNFilters {
  exclude_inverse: boolean;
  exclude_leveraged: boolean;
  exclude_synthetic: boolean;
  exclude_futures: boolean;
}

export interface MarketTopNFilterOptions {
  excludeInverse?: boolean;
  excludeLeveraged?: boolean;
  excludeSynthetic?: boolean;
  excludeFutures?: boolean;
}

export const DEFAULT_MARKET_TOPN_FILTERS: MarketTopNFilters = {
  exclude_inverse: true,
  exclude_leveraged: true,
  exclude_synthetic: true,
  exclude_futures: true,
};

export interface MarketLatestRefresh {
  refresh_id?: string | null;
  source?: string | null;
  asof?: string | null;
  attempted_count?: number | null;
  success_count?: number | null;
  fail_count?: number | null;
  runtime_seconds?: number | null;
  error_summary?: string | null;
  created_at?: string | null;
}

export interface MarketTopNResponse {
  status: MarketTopNStatus;
  error?: string | null;
  asof?: string | null;
  source?: string | null;
  n?: number | null;
  // 2026-05-18 통합 후보 테이블 1차 — 현재 조회 기준.
  basis?: MarketBasis | null;
  // 2026-05-19 Grid 사용성 FIX — 현재 정렬 방향.
  order?: MarketOrder | null;
  universe_count?: number | null;
  price_success_count?: number | null;
  price_fail_count?: number | null;
  latest_refresh?: MarketLatestRefresh | null;
  runtime_seconds?: number | null;
  // 통합 후보 테이블 (frontend 기본 렌더 소스).
  candidates: MarketCandidate[];
  // 호환용 — 기존 분리 테이블도 응답에 유지 (frontend 사용 안 함).
  daily_topn: MarketTopNEntry[];
  one_month_topn: MarketTopNEntry[];
  three_month_topn: MarketTopNEntry[];
  period_exclusions?: Record<string, Record<string, number>>;
  filters?: MarketTopNFilters;
  filter_exclusions?: Record<string, Record<string, number>>;
  candidate_filter_exclusions?: Record<string, number>;
  topn_caveat?: string | null;
  // 2026-05-22 — Market Regime & Benchmark Context. status=missing/empty/invalid
  // 에서는 null.
  market_context?: MarketContext | null;
  // 2026-06-20 ML 축1 — 상대상승 참고점수 v0 top-level 상태.
  relative_upside_score_status?: RelativeUpsideScoreStatus | null;
  relative_upside_score_asof_date?: string | null;
  relative_upside_score_generated_at?: string | null;
  relative_upside_score_user_notice?: string | null;
  // 2026-07-03 Market Risk Reference v1 — KODEX200 + VIX 일별 맥락.
  market_risk_reference?: MarketRiskReference | null;
  // POC5-09 — KODEX200 한 종목의 저장 거래량 관찰값(KOSPI 지수 거래량 아님).
  kodex200_stored_volume?: StoredVolumeEvidence | null;
}

// POC5-09 — 저장 거래량 확인 근거(backend app/stored_volume_evidence.py · 두 응답 공용).
// 거래량 단위 = 주. 평균 = 기준일을 뺀 바로 앞 20개 저장일이 모두 유효할 때만.
export interface StoredVolumeEvidence {
  ticker: string;
  status: "ok" | "no_price_data";
  asof_date: string | null;
  source: string | null;
  volume: number | null;
  window_size: number;
  window_start_date: string | null;
  window_end_date: string | null;
  window_date_count: number;
  valid_count: number;
  avg_prev20: number | null;
  avg_status: "ok" | "insufficient";
  ratio: number | null;
  ratio_status: "ok" | "volume_missing" | "avg_insufficient" | "avg_zero";
}

export interface MarketRiskRecentPoint {
  date: string;
  close: number;
}

export interface MarketRiskKodex200 {
  availability: "available" | "unavailable";
  as_of_date?: string | null;
  close?: number | null;
  change_1d_pct?: number | null;
  recent_20d_series: MarketRiskRecentPoint[];
  series_first_date?: string | null;
  series_last_date?: string | null;
}

// POC5-12 — VIX 최신성 판정(PC 서버 · 미국 장 마감 기준 · 조회 시각). 화면은 미국 마감 ·
// 서머타임을 다시 계산하지 않고 이 값만 읽는다. 필드가 없으면 추측하지 않는다(기준일 확인 필요).
export type VixFreshnessState =
  | "fresh"
  | "one_weekday_behind"
  | "update_check"
  | "date_check";

export interface MarketRiskVixFreshness {
  state: VixFreshnessState;
  compare_date?: string | null; // E — 미국 장 마감 기준 비교일(토 · 일은 직전 금요일)
  weekdays_behind?: number | null; // L — D 다음 날부터 E 까지의 평일 수
}

export interface MarketRiskVix {
  availability: "available" | "unavailable";
  as_of_date?: string | null;
  close?: number | null;
  change_1d_pct?: number | null;
  change_5d_pct?: number | null;
  recent_20d_series: MarketRiskRecentPoint[];
  series_first_date?: string | null;
  series_last_date?: string | null;
  freshness?: MarketRiskVixFreshness | null; // POC5-12 선택 필드
}

export interface MarketRiskReference {
  kodex200: MarketRiskKodex200;
  vix: MarketRiskVix;
}

export interface MarketTopNRequestOptions extends MarketTopNFilterOptions {
  basis?: MarketBasis;
  order?: MarketOrder;
}

// POC5-12 — 같은 주소의 시장 TOP N GET 은 끝날 때까지 같은 요청을 공유한다(개발 모드 이중
// 실행 · 두 화면이 겹쳐 열릴 때 서버 계산 1회). 성공 · 실패 · 시간 초과 뒤 바로 지운다(보관
// 캐시 · 자동 재조회 없음).
const inflightTopn = new Map<string, Promise<MarketTopNResponse>>();

// 갱신 · 'VIX 다시 받기'가 끝난 뒤 다시 읽기는 그 전에 보낸 요청에 붙지 않고 새로 보낸다
// (갱신 전에 보낸 요청의 결과를 '다시 읽은 결과'로 보이지 않게 · 이미 기다리는 쪽은 자기 요청 그대로).
export function forgetMarketTopnInflight(): void {
  inflightTopn.clear();
}

// 테스트용: 진행 중 공유 초기화(vitest.setup 에서 매 테스트 전에 부른다).
export function __resetMarketTopnInflight(): void {
  inflightTopn.clear();
}

export function fetchMarketTopnLatest(
  n: number = 10,
  options: MarketTopNRequestOptions = {},
): Promise<MarketTopNResponse> {
  const params = new URLSearchParams({ n: String(n) });
  params.set("basis", options.basis ?? DEFAULT_MARKET_BASIS);
  params.set("order", options.order ?? DEFAULT_MARKET_ORDER);
  params.set(
    "exclude_inverse",
    String(options.excludeInverse ?? DEFAULT_MARKET_TOPN_FILTERS.exclude_inverse),
  );
  params.set(
    "exclude_leveraged",
    String(options.excludeLeveraged ?? DEFAULT_MARKET_TOPN_FILTERS.exclude_leveraged),
  );
  params.set(
    "exclude_synthetic",
    String(options.excludeSynthetic ?? DEFAULT_MARKET_TOPN_FILTERS.exclude_synthetic),
  );
  params.set(
    "exclude_futures",
    String(options.excludeFutures ?? DEFAULT_MARKET_TOPN_FILTERS.exclude_futures),
  );
  const path = `/market/topn/latest?${params.toString()}`;
  const existing = inflightTopn.get(path);
  if (existing) return existing;
  const shared: Promise<MarketTopNResponse> = request<MarketTopNResponse>(
    "GET",
    path,
  ).finally(() => {
    if (inflightTopn.get(path) === shared) inflightTopn.delete(path);
  });
  inflightTopn.set(path, shared);
  return shared;
}

export type MarketRefreshStartStatus =
  | "accepted"
  | "running"
  | "skipped_cooldown"
  | "failed_to_start"
  | "not_needed" // POC5-12 scope=vix — 다시 받을 VIX 실패 기록 없음(실행 0)
  | "vix_retry_running"; // POC5-12 — 'VIX 다시 받기'가 도는 중이라 거절(refresh_id = 그 재시도 id)

export interface MarketRefreshStartResponse {
  status: MarketRefreshStartStatus;
  refresh_id?: string | null;
  message: string;
  cooldown_remaining_seconds: number;
}

// POC5-12 — scope "vix": 전체 갱신에서 VIX 만 실패했을 때 VIX 단계만 다시 받는다(같은 경로).
export type MarketRefreshScope = "vix";

export function postMarketRefresh(
  scope?: MarketRefreshScope,
): Promise<MarketRefreshStartResponse> {
  // FDR 수집은 background — POST 자체는 즉시 응답이라 짧은 timeout.
  return request<MarketRefreshStartResponse>(
    "POST",
    scope ? `/market/refresh?scope=${scope}` : "/market/refresh",
    undefined,
    15000,
  );
}

export type MarketRefreshStatus =
  | "idle"
  | "running"
  | "completed"
  | "failed"
  | "skipped_cooldown";

export interface MarketRefreshStatusResponse {
  status: MarketRefreshStatus;
  refresh_id?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  asof?: string | null;
  universe_count?: number | null;
  price_attempted_count?: number | null;
  price_success_count?: number | null;
  price_fail_count?: number | null;
  runtime_seconds?: number | null;
  error_summary?: string | null;
  cooldown_remaining_seconds: number;
  vix_retry?: MarketRefreshVixRetry | null; // POC5-12 선택 필드
}

// POC5-12 — 'VIX 다시 받기' 표식 · 결과(전체 갱신 상태와 섞지 않는 별도 행).
export interface MarketRefreshVixRetry {
  needed: boolean;
  status?: "needed" | "running" | "completed" | "failed" | "cleared" | null;
  refresh_id?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  error_summary?: string | null;
  vix_as_of_date?: string | null;
}

export function fetchMarketRefreshStatus(): Promise<MarketRefreshStatusResponse> {
  return request<MarketRefreshStatusResponse>("GET", "/market/refresh/status");
}
