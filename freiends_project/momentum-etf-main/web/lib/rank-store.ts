import { fetchFastApiJson } from "./internal-api";

type RankTickerType = {
  ticker_type: string;
  order: number;
  name: string;
  icon: string;
  country_code: string;
};

type RankMaRule = {
  order: number;
  ma_type: string;
  ma_months: number;
  ma_days: number;
  score_column: string;
};

type RankRow = {
  [key: string]: string | number | null;
  순번: string;
  순위: number | null;
  이전순위: number | null;
  버킷: string;
  bucket: number;
  티커: string;
  종목명: string;
  상장일: string;
  점수: number | null;
  현재가: number | null;
  "괴리율": number | null;
  "일간(%)": number | null;
  "1주(%)": number | null;
  "2주(%)": number | null;
  "3주(%)": number | null;
  "4주(%)": number | null;
  "1달(%)": number | null;
  "2달(%)": number | null;
  "3달(%)": number | null;
  "4달(%)": number | null;
  "5달(%)": number | null;
  "6달(%)": number | null;
  "7달(%)": number | null;
  "8달(%)": number | null;
  "9달(%)": number | null;
  "10달(%)": number | null;
  "11달(%)": number | null;
  "12달(%)": number | null;
  고점: number | null;
  RSI: number | null;
};

type RankData = {
  ticker_types: RankTickerType[];
  ticker_type: string;
  ma_rules: RankMaRule[];
  ma_type_options: string[];
  ma_months_max: number;
  as_of_date: string | null;
  monthly_return_labels: string[];
  rows: RankRow[];
  cache_blocked: boolean;
  latest_trading_day: string | null;
  cache_updated_at: string | null;
  ranking_computed_at: string | null;
  realtime_fetched_at: string | null;
  previous_trading_day: string | null;
  missing_tickers: string[];
  missing_ticker_labels: string[];
  stale_tickers: string[];
};

export async function loadRankData(params?: {
  ticker_type?: string;
  ma_rule_overrides?: RankMaRule[];
  as_of_date?: string;
}): Promise<RankData> {
  const search = new URLSearchParams();
  if (params?.ticker_type) {
    search.set("ticker_type", params.ticker_type);
  }
  if (params?.as_of_date) {
    search.set("as_of_date", params.as_of_date);
  }
  for (const rule of params?.ma_rule_overrides ?? []) {
    search.set(`rule${rule.order}_ma_type`, rule.ma_type);
    search.set(`rule${rule.order}_ma_months`, String(rule.ma_months));
  }

  const query = search.size > 0 ? `?${search.toString()}` : "";
  return fetchFastApiJson<RankData>(`/internal/rank${query}`);
}

export type { RankTickerType, RankMaRule, RankData, RankRow };
