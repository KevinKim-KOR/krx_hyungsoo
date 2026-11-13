// POC6-28 — 「ETF 비교하기」 시험용 요약 응답(GET /market/etf-compare/summary 모양 · 실제 값과 무관한 고정 자료).
// POC6-29 — 종목 상세 수치 응답(GET /market/etf-detail)도 같은 고정 자료로.
import type {
  CompareGroup,
  CompareRow,
  CompareSummaryOk,
  HoldingLink,
  PriceFlow,
} from "@/lib/api/etfCompare";
import type { DetailPeriod, EtfDetailItem, EtfDetailResponse } from "@/lib/api/etfDetail";

const START = "2026-10-12";
const END = "2026-11-09";
const AFTER = { date: END, state: "after_close" as const, fetched_at_kst: "2026-11-10T13:18:02+09:00" };

export function row(p: {
  rank: number;
  ticker: string;
  name: string;
  value: number;
  held?: boolean;
  kind?: "sector" | "index" | "unclassified";
  sector?: string | null;
  index?: string | null;
  market?: string;
  asset?: string;
  strategy?: boolean;
  three?: { status: "ok" | "period_differs" | "missing"; value: number | null; start?: string };
  same?: number | null;
  dd?: { status: "ok" | "period_differs" | "missing"; value: number | null; reason?: string | null };
  cons?: boolean;
}): CompareRow {
  const three = p.three ?? { status: "ok" as const, value: p.value / 2 };
  const dd = p.dd ?? { status: "ok" as const, value: -10 };
  return {
    rank: p.rank,
    ticker: p.ticker,
    name: p.name,
    held: !!p.held,
    tags: [],
    classification: {
      kind: p.kind ?? "index",
      sector: p.sector ?? null,
      index_name: p.index === undefined ? `${p.name} 지수` : p.index,
      market: p.market ?? "국내",
      asset: p.asset ?? "주식",
      strategy: !!p.strategy,
      broad: false,
    },
    basis_return: { value: p.value, start: START, end: END, start_close: 10000, end_close: 10000 * (1 + p.value / 100) },
    criteria: {
      one_month: { status: "ok", value: p.value, start: START, end: END, reason: null },
      three_month: {
        status: three.status,
        value: three.value,
        start: three.start ?? (three.status === "missing" ? null : "2026-08-11"),
        end: three.status === "missing" ? null : END,
        reason: three.status === "ok" ? null : three.status === "missing" ? "no_period" : "period_differs",
      },
      same_kodex_1m:
        p.same === null
          ? {
              status: "missing",
              value: null,
              start: START,
              end: END,
              kodex200_return_pct: null,
              etf_return_pct: p.value,
              reason: "kodex200_start_price_missing",
            }
          : {
              status: "ok",
              value: p.same ?? p.value + 22.64,
              start: START,
              end: END,
              kodex200_return_pct: -22.64,
              etf_return_pct: p.value,
              reason: null,
            },
      drawdown: {
        status: dd.status,
        value: dd.value,
        reason: dd.reason ?? null,
        start: "2026-10-13",
        end: END,
        peak_date: "2026-10-13",
        peak_close: 26500,
        close: 14395,
      },
    },
    end_price: AFTER,
    constituents: p.cons
      ? {
          asof: "2026-10-02",
          items: [
            { ticker: "036930", name: "주성엔지니어링", weight_pct: 8.1, key: "036930", match_key: "036930" },
            { ticker: null, name: "마이크론", weight_pct: 6.0, key: "MU.O", match_key: "MU.O" },
          ],
        }
      : null,
  };
}

export function group(rows: CompareRow[], p: Partial<CompareGroup> & Pick<CompareGroup, "kind" | "name">): CompareGroup {
  const vals = rows.map((r) => r.basis_return.value);
  return {
    etf_count: rows.length,
    distinct_index_count: rows.length,
    tickers: rows.map((r) => r.ticker),
    return_min: Math.min(...vals),
    return_max: Math.max(...vals),
    markets: { 국내: rows.length },
    assets: { 주식: rows.length },
    strategy_count: rows.filter((r) => r.classification.strategy).length,
    held_count: rows.filter((r) => r.held).length,
    both_sides: false,
    constituents: {
      status: "no_sample",
      etf_with_data: 0,
      etf_total: rows.length,
      asof_min: null,
      asof_max: null,
      top_n: 10,
      common: [],
    },
    ...p,
  };
}

export const TOP = [
  row({ rank: 1, ticker: "T00001", name: "인도 대표", value: 15.74, market: "해외", index: "Nifty 50 Index" }),
  row({ rank: 2, ticker: "T00002", name: "인도 대표2", value: 14.81, market: "해외", index: "Nifty 50 Index" }),
  row({ rank: 3, ticker: "T00003", name: "헬스케어", value: 12.41, kind: "sector", sector: "바이오" }),
];

export const BOTTOM = [
  row({ rank: 1, ticker: "B00001", name: "반도체 전공정", value: -44.92, kind: "sector", sector: "반도체", held: true, cons: true }),
  row({
    rank: 2,
    ticker: "B00002",
    name: "반도체 커버드콜",
    value: -40.1,
    kind: "sector",
    sector: "반도체",
    strategy: true,
    cons: true,
    dd: { status: "ok", value: 0 },
  }),
  row({
    rank: 3,
    ticker: "B00003",
    name: "늦은 상장",
    value: -36.0,
    three: { status: "period_differs", value: -25.47, start: "2026-09-15" },
    dd: { status: "missing", value: null, reason: "insufficient_history" },
  }),
];

// 보유 가격 흐름(검증자 r2 F4 · 요약 같은 응답) — 기본 = 비교 가능 · 20저장일 -3% · KODEX 200 -12% · 하락 구간 밖.
export function flow(p: Partial<PriceFlow> = {}): PriceFlow {
  return {
    end_date: END,
    start_date_5d: "2026-11-02",
    start_date_20d: "2026-10-13",
    comparison: "ok",
    status: "ok",
    return_5d_pct: -1.5,
    return_20d_pct: -3,
    excess_vs_kodex200_20d_pctp: 9,
    kodex200_return_20d_pct: -12,
    decline_band: { judgeable: true, state: null, label: null, return_20d_pct_1dp: -3, unjudged_reason: null },
    end_price: AFTER,
    ...p,
  };
}

export function link(p: Partial<HoldingLink> & Pick<HoldingLink, "ticker">): HoldingLink {
  return {
    is_stock: false,
    in_population: true,
    out_reason: null,
    basis_return: { value: -5, start: START, end: END },
    side: null,
    side_rank: null,
    end_price: AFTER,
    price_flow: flow(),
    has_constituents: false,
    exposure: {
      status: "no_constituents",
      compared_etf_count: 2,
      compared_asof_min: "2026-10-02",
      compared_asof_max: "2026-10-02",
      holding_asof: null,
      top_n: 10,
      overlaps: [],
    },
    ...p,
  };
}

export function summaryOk(over: Partial<CompareSummaryOk> = {}): CompareSummaryOk {
  const semi = group(BOTTOM.slice(0, 2), {
    kind: "sector",
    name: "반도체",
    distinct_index_count: 2,
    constituents: {
      status: "ok",
      etf_with_data: 2,
      etf_total: 2,
      asof_min: "2026-10-02",
      asof_max: "2026-10-02",
      top_n: 10,
      common: [
        { key: "036930", name: "주성엔지니어링", etf_count: 2 },
        { key: "MU.O", name: "마이크론", etf_count: 2 },
      ],
    },
  });
  return {
    status: "ok",
    message: null,
    basis: "one_month",
    end_date: END,
    filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
    n: 30,
    period: { start: START, end: END },
    criteria_periods: {
      one_month: { start: START, end: END },
      three_month: { start: "2026-08-11", end: END },
      drawdown: { start: "2026-10-13", end: END },
    },
    kodex200: {
      basis_return_pct: -22.64,
      one_month_return_pct: -22.64,
      three_month_return_pct: -20.82,
    },
    counts: {
      universe: 1204,
      no_price: 8,
      filter_excluded: 211,
      no_return: 7,
      start_differs: 16,
      end_differs: 1,
      period_differs: 17,
      population: 961,
      shown_top: 3,
      shown_bottom: 3,
    },
    price_state: {
      end_date: END,
      intraday_count: 0,
      after_close_count: 961,
      unknown_count: 0,
      provisional: false,
      intraday_fetched_min: null,
      intraday_fetched_max: null,
      after_close_fetched_min: "2026-11-10T13:17:11+09:00",
      after_close_fetched_max: "2026-11-10T13:21:00+09:00",
    },
    regime: {
      status: "ok",
      code: "bear",
      label: "하락장",
      asof: END,
      score: -4,
      reasons: [],
      streak_days: 22,
      streak_at_least: false,
      same_end_date: true,
      price: AFTER,
    },
    top: TOP,
    bottom: BOTTOM,
    in_both: [],
    groups: {
      top: [
        group(TOP.slice(0, 2), { kind: "index", name: "Nifty 50 Index", distinct_index_count: 1, markets: { 해외: 2 } }),
        group([TOP[2]], { kind: "sector", name: "바이오" }),
      ],
      bottom: [semi, group([BOTTOM[2]], { kind: "index", name: "늦은 상장 지수" })],
    },
    overview: {
      top: {
        mix: [
          { market: "해외", asset: "주식", count: 2 },
          { market: "국내", asset: "주식", count: 1 },
        ],
        unclassified_count: 0,
        sector_etf_count: 1,
        total: 3,
        repeated_sector_count: 0,
        index_group_count: 1,
        constituents_etf_count: 0,
      },
      bottom: {
        mix: [{ market: "국내", asset: "주식", count: 3 }],
        unclassified_count: 0,
        sector_etf_count: 2,
        total: 3,
        repeated_sector_count: 1,
        index_group_count: 1,
        constituents_etf_count: 2,
      },
    },
    both_side_sectors: [],
    holdings: {
      status: "ok",
      items: [
        link({
          ticker: "B00001",
          side: "bottom",
          side_rank: 1,
          basis_return: { value: -44.92, start: START, end: END },
          has_constituents: true,
          exposure: {
            status: "ok",
            compared_etf_count: 1,
            compared_asof_min: "2026-10-02",
            compared_asof_max: "2026-10-02",
            holding_asof: "2026-10-02",
            top_n: 10,
            overlaps: [{ key: "036930", name: "주성엔지니어링", etfs: ["B00002"] }],
          },
        }),
        link({ ticker: "H00002", basis_return: { value: 3.2, start: START, end: END } }),
        link({
          ticker: "005930",
          is_stock: true,
          in_population: false,
          out_reason: "stock",
          basis_return: null,
          exposure: {
            status: "ok",
            compared_etf_count: 2,
            compared_asof_min: "2026-10-02",
            compared_asof_max: "2026-10-02",
            holding_asof: null,
            top_n: 10,
            overlaps: [{ key: "005930", name: "005930", etfs: ["B00001", "B00002"] }],
          },
        }),
      ],
    },
    sources: {
      official_csv: { status: "ok", name: "krx_etf_basic_20260927.csv", csv_asof: "2026-09-27" },
      dictionary: { status: "ok", sector_count: 28 },
    },
    ...over,
  };
}

// POC6-29 — GET /market/etf-detail 시험 응답(행 상세 · [표] · 「보유와 후보 비교」 공통 · 고정 자료).

export function period(
  value: number | null,
  start: string | null = START,
  end: string | null = END,
  status: DetailPeriod["status"] = "ok",
  reason: string | null = null,
): DetailPeriod {
  return { status, value, start, end, start_close: value == null ? null : 10000, end_close: value == null ? null : 10000, reason };
}

export function detailItem(ticker: string, over: Partial<EtfDetailItem> = {}): EtfDetailItem {
  return {
    ticker,
    name: `ETF ${ticker}`,
    is_etf: true,
    last_date: END,
    end_price: AFTER,
    daily: period(0.5, "2026-11-06", END),
    w5: period(-1.2, "2026-11-02", END),
    w20: period(-8.4, "2026-10-13", END),
    m1: period(-10.25, START, END),
    m3: period(-5.5, "2026-08-11", END),
    m6: period(12.3, "2026-05-12", END),
    m12: period(30.1, "2025-11-10", END),
    excess20: {
      status: "ok",
      value_pctp: 6.1,
      etf_return_pct: -8.4,
      kodex200_return_pct: -14.5,
      start: "2026-10-13",
      end: END,
      reason: null,
    },
    same_kodex: {
      one_month: { status: "ok", value: 12.39, etf_return_pct: -10.25, kodex200_return_pct: -22.64, start: START, end: END, reason: null },
      three_month: { status: "ok", value: 10.2, etf_return_pct: -5.5, kodex200_return_pct: -15.7, start: "2026-08-11", end: END, reason: null },
    },
    drawdown: { status: "ok", value: -3.0, start: "2026-10-13", end: END, peak_date: "2026-10-20", peak_close: 10300, close: 9991, reason: null },
    nav: { status: "ok", nav: 10010, market_price: 10000, discount_rate_pct: -0.1, flag: null, asof: END },
    ...over,
  };
}

export function detailResponse(tickers: string[], over: Partial<EtfDetailResponse> = {}): EtfDetailResponse {
  return {
    status: "ok",
    message: null,
    end_date: END,
    kodex200: { window20: period(-14.5, "2026-10-13", END) },
    items: tickers.map((t) => detailItem(t)),
    ...over,
  };
}
