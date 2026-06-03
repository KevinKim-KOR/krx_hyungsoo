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
