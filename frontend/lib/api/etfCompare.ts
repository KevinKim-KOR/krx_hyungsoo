// POC6-28 — 「ETF 비교하기」 요약 read-only client.
// GET /market/etf-compare/summary — 같은 모집단의 상·하위 최대 30 · 묶음 · 네 기준 · 가격 시점 · 국면 · 보유 연결.
// 응답에 금액 · 계좌가 없다(보유는 ticker 와 연결 사실만).

import { request } from "./core";
import { ETF_COMPARE_KEY_PREFIX } from "./dashboardKeys";

export { ETF_COMPARE_KEY_PREFIX };

export type CompareBasis = "daily" | "one_month" | "three_month";

export interface CompareFilters {
  exclude_inverse: boolean;
  exclude_leveraged: boolean;
  exclude_synthetic: boolean;
  exclude_futures: boolean;
}

export type PriceStateCode = "intraday" | "after_close" | "unknown";

export interface EndPrice {
  date: string | null;
  state: PriceStateCode;
  fetched_at_kst: string | null;
}

// 보유 한 종목의 가격 흐름 · 기존 하락 판정 · 끝일 행 저장 상태 — 같은 응답 · 같은 DB 읽기(검증자 r2 F4).
// 값 · 판정은 보유 근거 PC 사본과 같은 기존 함수(app/pc_price_basis.py)로 만든다.
export interface PriceFlow {
  end_date: string | null;
  start_date_5d: string | null;
  start_date_20d: string | null;
  comparison: "ok" | "date_mismatch" | "window_mismatch" | "unavailable";
  status: string | null;
  return_5d_pct: number | null;
  return_20d_pct: number | null;
  excess_vs_kodex200_20d_pctp: number | null;
  kodex200_return_20d_pct: number | null;
  decline_band: {
    judgeable: boolean;
    state: string | null;
    label: string | null;
    return_20d_pct_1dp: number | null;
    unjudged_reason: string | null;
  };
  end_price: EndPrice;
}

export type CritStatus = "ok" | "period_differs" | "missing";

export interface PeriodCriterion {
  status: CritStatus;
  value: number | null;
  start: string | null;
  end: string | null;
  start_close?: number | null;
  end_close?: number | null;
  reason: string | null;
}

export interface SameCriterion {
  status: CritStatus;
  value: number | null;
  start: string | null;
  end: string | null;
  kodex200_return_pct: number | null;
  etf_return_pct: number | null;
  reason: string | null;
}

export interface DrawdownCriterion {
  status: CritStatus;
  value: number | null;
  reason: string | null;
  start: string | null;
  end: string | null;
  peak_date: string | null;
  peak_close: number | null;
  close: number | null;
}

export interface Classification {
  kind: "sector" | "index" | "unclassified";
  sector: string | null;
  index_name: string | null;
  market: string | null;
  asset: string | null;
  strategy: boolean;
  broad: boolean;
}

export interface ConstituentItem {
  ticker: string | null;
  name: string | null;
  weight_pct: number | null;
  key: string | null;
  match_key: string | null;
}

export interface EtfConstituents {
  asof: string;
  items: ConstituentItem[];
}

export interface CompareRow {
  rank: number;
  ticker: string;
  name: string | null;
  held: boolean;
  tags: string[];
  classification: Classification;
  basis_return: {
    value: number;
    start: string;
    end: string;
    start_close: number;
    end_close: number;
  };
  criteria: {
    one_month: PeriodCriterion;
    three_month: PeriodCriterion;
    same_kodex_1m: SameCriterion;
    drawdown: DrawdownCriterion;
  };
  end_price: EndPrice;
  constituents: EtfConstituents | null;
}

export type CommonStatus = "no_sample" | "single" | "no_overlap" | "ok";

export interface CompareGroup {
  kind: "sector" | "index" | "unclassified";
  name: string | null;
  etf_count: number;
  distinct_index_count: number;
  tickers: string[];
  return_min: number;
  return_max: number;
  markets: Record<string, number>;
  assets: Record<string, number>;
  strategy_count: number;
  held_count: number;
  both_sides: boolean;
  constituents: {
    status: CommonStatus;
    etf_with_data: number;
    etf_total: number;
    asof_min: string | null;
    asof_max: string | null;
    top_n: number;
    common: { key: string; name: string; etf_count: number }[];
  };
}

export interface SideOverview {
  mix: { market: string; asset: string; count: number }[];
  unclassified_count: number;
  sector_etf_count: number;
  total: number;
  repeated_sector_count: number;
  index_group_count: number;
  constituents_etf_count: number;
}

export type ExposureStatus = "ok" | "none" | "no_constituents" | "no_sample";

export interface HoldingLink {
  ticker: string;
  is_stock: boolean;
  in_population: boolean;
  out_reason: "stock" | "filter_excluded" | "no_price" | "period_differs" | null;
  basis_return: { value: number; start: string; end: string } | null;
  side: "top" | "bottom" | null;
  side_rank: number | null;
  // 상위에도 든 경우의 상위 순위(모집단 60 미만 · 상·하위 공통 · 검증자 r1 F3)
  top_rank?: number | null;
  end_price: EndPrice | null;
  price_flow?: PriceFlow | null;
  has_constituents: boolean;
  exposure: {
    status: ExposureStatus;
    compared_etf_count: number;
    compared_asof_min: string | null;
    compared_asof_max: string | null;
    holding_asof: string | null;
    top_n: number;
    overlaps: { key: string; name: string; etfs: string[] }[];
  };
}

export interface PriceStateSummary {
  end_date: string;
  intraday_count: number;
  after_close_count: number;
  unknown_count: number;
  provisional: boolean;
  intraday_fetched_min: string | null;
  intraday_fetched_max: string | null;
  after_close_fetched_min: string | null;
  after_close_fetched_max: string | null;
}

export interface CompareRegime {
  status: string | null;
  code: string | null;
  label: string | null;
  asof: string | null;
  score: number | null;
  reasons: string[];
  streak_days: number | null;
  streak_at_least: boolean | null;
  same_end_date: boolean;
  price: EndPrice;
}

export interface CompareSummaryOk {
  status: "ok";
  message: null;
  basis: CompareBasis;
  end_date: string;
  filters: CompareFilters;
  n: number;
  period: { start: string; end: string };
  criteria_periods: {
    one_month: { start: string; end: string } | null;
    three_month: { start: string; end: string } | null;
    drawdown: { start: string; end: string } | null;
  };
  kodex200: {
    basis_return_pct: number;
    one_month_return_pct: number | null;
    three_month_return_pct: number | null;
  };
  counts: {
    universe: number;
    no_price: number;
    filter_excluded: number;
    no_return: number;
    start_differs: number;
    end_differs: number;
    period_differs: number;
    population: number;
    shown_top: number;
    shown_bottom: number;
  };
  price_state: PriceStateSummary;
  regime: CompareRegime;
  top: CompareRow[];
  bottom: CompareRow[];
  in_both: string[];
  groups: { top: CompareGroup[]; bottom: CompareGroup[] };
  overview: { top: SideOverview; bottom: SideOverview };
  both_side_sectors: string[];
  holdings: { status: "ok" | "none" | "error"; items: HoldingLink[] };
  sources: {
    official_csv: { status: string; name: string | null; csv_asof: string | null };
    dictionary: { status: string; sector_count: number | null };
  };
}

export interface CompareSummaryNotOk {
  status: "missing" | "empty" | "invalid" | "no_common_period";
  message: string | null;
  basis: CompareBasis;
  filters?: CompareFilters;
}

export type CompareSummary = CompareSummaryOk | CompareSummaryNotOk;

export interface CompareCondition {
  basis: CompareBasis;
  filters: CompareFilters;
}

function query(c: CompareCondition): string {
  const p = new URLSearchParams({ basis: c.basis });
  for (const [k, v] of Object.entries(c.filters)) p.set(k, String(v));
  return p.toString();
}

export function etfCompareKey(c: CompareCondition): string {
  return `${ETF_COMPARE_KEY_PREFIX}${query(c)}`;
}

export function fetchEtfCompareSummary(c: CompareCondition): Promise<CompareSummary> {
  return request<CompareSummary>("GET", `/market/etf-compare/summary?${query(c)}`);
}
