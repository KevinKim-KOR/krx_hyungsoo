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
}

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
}

export interface MarketTopNRequestOptions extends MarketTopNFilterOptions {
  basis?: MarketBasis;
  order?: MarketOrder;
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
  return request<MarketTopNResponse>(
    "GET",
    `/market/topn/latest?${params.toString()}`,
  );
}

export type MarketRefreshStartStatus =
  | "accepted"
  | "running"
  | "skipped_cooldown"
  | "failed_to_start";

export interface MarketRefreshStartResponse {
  status: MarketRefreshStartStatus;
  refresh_id?: string | null;
  message: string;
  cooldown_remaining_seconds: number;
}

export function postMarketRefresh(): Promise<MarketRefreshStartResponse> {
  // FDR 수집은 background — POST 자체는 즉시 응답이라 짧은 timeout.
  return request<MarketRefreshStartResponse>(
    "POST",
    "/market/refresh",
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
}

export function fetchMarketRefreshStatus(): Promise<MarketRefreshStatusResponse> {
  return request<MarketRefreshStatusResponse>("GET", "/market/refresh/status");
}
