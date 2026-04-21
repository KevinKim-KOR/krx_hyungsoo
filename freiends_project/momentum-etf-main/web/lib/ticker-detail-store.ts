import { fetchFastApiJson } from "./internal-api";

export type TickerDetailRow = {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  change_pct: number | null;
};

export type TickerHoldingRow = {
  ticker: string;
  name: string;
  contracts: number | null;
  amount: number | null;
  raw_code?: string | null;
  raw_name?: string | null;
  reuters_code?: string | null;
  yahoo_symbol?: string | null;
  current_price?: number | null;
  previous_close?: number | null;
  change_pct?: number | null;
  price_currency?: string | null;
  weight: number | null;
};

export type TickerDetailData = {
  ticker: string;
  rows: TickerDetailRow[];
  holdings: TickerHoldingRow[];
  holdings_as_of_date?: string | null;
  holdings_price_as_of_date?: string | null;
  holdings_error?: string | null;
  error?: string;
};

type TickerMetaItem = {
  ticker: string;
  name: string;
  ticker_type: string;
  country_code: string;
};

async function resolveTickerMeta(ticker: string): Promise<TickerMetaItem> {
  const items = await fetchFastApiJson<TickerMetaItem[]>("/internal/ticker-detail/tickers");
  const matches = items.filter((item) => item.ticker.toLowerCase() === ticker.toLowerCase());
  if (matches.length === 0) {
    throw new Error(`${ticker} 티커를 찾지 못했습니다.`);
  }
  if (matches.length > 1) {
    throw new Error(`동일한 티커 ${ticker}가 여러 종목풀에 등록되어 있습니다.`);
  }
  return matches[0];
}

export async function loadTickerDetailData(params: {
  ticker: string;
  ticker_type?: string;
  country_code?: string;
}): Promise<TickerDetailData> {
  const resolvedMeta = params.ticker_type ? null : await resolveTickerMeta(params.ticker);

  const search = new URLSearchParams();
  search.set("ticker", params.ticker);
  search.set("ticker_type", params.ticker_type ?? resolvedMeta!.ticker_type);

  const countryCode = params.country_code ?? resolvedMeta?.country_code;
  if (countryCode) {
    search.set("country_code", countryCode);
  }
  return fetchFastApiJson<TickerDetailData>(`/internal/ticker-detail?${search.toString()}`);
}
