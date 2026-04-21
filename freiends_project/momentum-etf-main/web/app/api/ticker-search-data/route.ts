import { NextResponse } from "next/server";

import { fetchFastApiJson } from "../../../lib/internal-api";

export const dynamic = "force-dynamic";

type TickerSearchItem = {
  ticker: string;
  name: string;
  ticker_type: string;
  country_code: string;
  current_price: number | null;
  change_pct: number | null;
};

type TickerSearchPayload = {
  tickers: TickerSearchItem[];
  top_movers_by_type: Array<{
    ticker_type: string;
    label: string;
    items: TickerSearchItem[];
  }>;
};

export async function GET() {
  try {
    const data = await fetchFastApiJson<TickerSearchPayload>("/internal/ticker-detail/search-data");
    return NextResponse.json(data);
  } catch (error) {
    const message = error instanceof Error ? error.message : "전역 검색 데이터를 불러오지 못했습니다.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
