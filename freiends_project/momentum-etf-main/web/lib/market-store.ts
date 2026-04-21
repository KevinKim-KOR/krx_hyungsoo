import { fetchFastApiJson } from "./internal-api";

type MarketRowItem = {
  ticker: string;
  name: string;
  listed_at: string;
  daily_change_pct: number | null;
  current_price: number | null;
  nav: number | null;
  deviation: number | null;
  return_3m_pct: number | null;
  prev_volume: number;
  market_cap: number;
};

type MarketTableData = {
  updated_at: string | null;
  rows: MarketRowItem[];
};

export async function loadEtfMarketTable(): Promise<MarketTableData> {
  return fetchFastApiJson<MarketTableData>("/internal/market");
}

export type { MarketRowItem, MarketTableData };
