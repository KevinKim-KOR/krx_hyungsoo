// POC2 — Holdings 입력 / 조회 / 시세 enrichment + 보유 종목 시세 refresh.
// 본 모듈의 refreshMarket 은 보유 종목 한정 Naver 시세 갱신
// (`POST /holdings/market/refresh`). ETF universe 전체 가격 refresh 는
// market.ts 의 postMarketRefresh (`POST /market/refresh`) 를 사용한다.

import { request } from "./core";
import type { Run } from "./runApproval";

// ─── POC2 Step 1: holdings ───────────────────────────────────────────

export interface HoldingItem {
  ticker: string;
  quantity: number;
  avg_buy_price: number;
  name?: string | null;
  // POC2 Step 2C: 표시/그룹용 라벨. 빈 값/누락은 백엔드에서 "일반" 으로 정규화.
  account_group?: string | null;
}

export interface HoldingsPayload {
  holdings: HoldingItem[];
}

export function fetchHoldings(): Promise<HoldingsPayload> {
  return request<HoldingsPayload>("GET", "/holdings");
}

export function saveHoldings(payload: HoldingsPayload): Promise<HoldingsPayload> {
  return request<HoldingsPayload>("PUT", "/holdings", payload);
}

export function generateDraftFromHoldings(): Promise<Run> {
  return request<Run>("POST", "/runs/generate-from-holdings");
}

// ─── POC2 Step 2: holdings 시세 enrichment ────────────────────────────

export interface MarketQuoteItem {
  ticker: string;
  name: string | null;
  current_price: number | null;
  price_asof: string | null;
  price_source: string | null;
}

export interface MarketRefreshResult {
  ok_count: number;
  fail_count: number;
  items: MarketQuoteItem[];
  failures: Array<{ ticker: string; reason: string }>;
}

export interface EnrichedHolding {
  ticker: string;
  name: string | null;
  quantity: number;
  avg_buy_price: number;
  invested_amount: number;
  current_price: number | null;
  price_asof: string | null;
  price_source: string | null;
  eval_amount: number | null;
  pnl_amount: number | null;
  pnl_rate_pct: number | null;
  buy_weight_pct: number | null;
  market_weight_pct: number | null;
  price_missing: boolean;
  calc_missing: boolean;
  // POC2 Step 2C: 표시/그룹용 라벨 + UI key 안정성을 위한 행 위치.
  account_group?: string;
  source_index?: number;
}

export interface EnrichedHoldingsResult {
  items: EnrichedHolding[];
}

// 명시적 사용자 액션에서만 호출 (page load / polling / 새로고침에서 호출 금지).
// holdings 시세 갱신 — 2026-05-18 namespace 정정 후 `/holdings/market/refresh`.
// 기존 `/market/refresh` 는 ETF universe 전체 갱신용 (postMarketRefresh) 으로 이동.
export function refreshMarket(): Promise<MarketRefreshResult> {
  // Naver 시세 조회는 종목당 최대 5초 + 직렬 호출이라 기본 timeout 보다 여유 필요.
  return request<MarketRefreshResult>(
    "POST",
    "/holdings/market/refresh",
    undefined,
    60000,
  );
}

export function fetchEnrichedHoldings(): Promise<EnrichedHoldingsResult> {
  return request<EnrichedHoldingsResult>("GET", "/holdings/enriched");
}

// ─── POC2 Holdings × Market Discovery Evidence 1차 (2026-06-03) ──────
// GET /holdings/market-evidence/latest — read-only. 외부 fetch 트리거 X.
// 매수/매도/교체 판단 X. 보유 ETF 가 현재 Market Discovery 후보 / 시장 국면 /
// 단기 흐름 / 구성종목 중복 / NAV 상태와 어떻게 연결되는지의 raw evidence.
// GenerateDraft 흐름과 같은 backend evidence builder 를 재사용 — snapshot 형태로
// draft_payload.holdings_market_evidence_snapshot 에도 저장된다.

export type HoldingsMarketEvidenceTopnMatchStatus =
  | "matched_topn_candidate"
  | "not_in_current_topn"
  | "unavailable";

export type HoldingsMarketEvidenceReturnsStatus = "ok" | "unavailable" | "partial";

export type HoldingsMarketEvidenceConstituentsStatus =
  | "ok"
  | "constituents_unavailable"
  | "market_core_unavailable"
  | "unavailable";

export type HoldingsMarketEvidenceNavStatus =
  | "ok"
  | "warning"
  | "partial"
  | "unavailable";

export interface HoldingsMarketEvidenceTopnMatch {
  status: HoldingsMarketEvidenceTopnMatchStatus;
  rank: number | null;
  basis: string | null;
  candidate_name: string | null;
}

export interface HoldingsMarketEvidenceReturns {
  status: HoldingsMarketEvidenceReturnsStatus;
  one_month_return_pct: number | null;
  three_month_return_pct: number | null;
}

export interface HoldingsMarketEvidenceExcess {
  status: HoldingsMarketEvidenceReturnsStatus;
  vs_kodex200_1m_pctp: number | null;
  vs_kodex200_3m_pctp: number | null;
}

export interface HoldingsMarketEvidenceShortTermMomentum {
  status: HoldingsMarketEvidenceReturnsStatus;
  return_5d_pct: number | null;
  return_10d_pct: number | null;
  return_20d_pct: number | null;
  excess_vs_kodex200_5d_pctp: number | null;
  excess_vs_kodex200_10d_pctp: number | null;
  excess_vs_kodex200_20d_pctp: number | null;
}

export interface HoldingsMarketEvidenceOverlapItem {
  ticker: string | null;
  name: string | null;
  weight_pct: number | null;
  market_core_count: number | null;
}

export interface HoldingsMarketEvidenceConstituentsOverlap {
  status: HoldingsMarketEvidenceConstituentsStatus;
  overlap_with_market_core: HoldingsMarketEvidenceOverlapItem[];
}

export interface HoldingsMarketEvidenceNavDiscount {
  status: HoldingsMarketEvidenceNavStatus;
  source: string | null;
  asof: string | null;
  nav: number | null;
  market_price: number | null;
  discount_rate_pct: number | null;
  flag: string | null;
  message: string | null;
}

export interface HoldingsMarketEvidenceHoldingSnapshot {
  quantity: number;
  avg_buy_price: number;
  evaluation_amount: number | null;
  pnl_rate_pct: number | null;
}

export interface HoldingsMarketEvidenceItem {
  ticker: string;
  name: string;
  account_group?: string;
  holding: HoldingsMarketEvidenceHoldingSnapshot;
  topn_match: HoldingsMarketEvidenceTopnMatch;
  returns: HoldingsMarketEvidenceReturns;
  excess_return: HoldingsMarketEvidenceExcess;
  short_term_momentum: HoldingsMarketEvidenceShortTermMomentum;
  constituents_overlap: HoldingsMarketEvidenceConstituentsOverlap;
  nav_discount: HoldingsMarketEvidenceNavDiscount;
  evidence_notes: string[];
}

export interface HoldingsMarketEvidenceSummary {
  total_holdings_count: number;
  matched_topn_count: number;
  not_in_current_topn_count: number;
  evidence_unavailable_count: number;
  constituents_available_count: number;
  constituents_unavailable_count: number;
  nav_discount_unavailable_count: number;
}

export interface HoldingsMarketEvidenceMarketContext {
  status: string;
  asof: string | null;
  regime_label: string;
  regime_code: string;
}

export interface HoldingsMarketEvidenceResponse {
  status: "ok";
  asof: string;
  holdings_asof: string | null;
  market_asof: string | null;
  market_context: HoldingsMarketEvidenceMarketContext | null;
  summary: HoldingsMarketEvidenceSummary;
  holdings: HoldingsMarketEvidenceItem[];
  warnings: string[];
}

export function fetchHoldingsMarketEvidence(): Promise<HoldingsMarketEvidenceResponse> {
  return request<HoldingsMarketEvidenceResponse>(
    "GET",
    "/holdings/market-evidence/latest",
  );
}
