import { NextResponse } from "next/server";

import { fetchFastApiJson } from "../../../lib/internal-api";

export const dynamic = "force-dynamic";

type TickerItem = {
  ticker: string;
  name: string;
  ticker_type: string;
  country_code: string;
};

export async function GET() {
  try {
    const data = await fetchFastApiJson<TickerItem[]>("/internal/ticker-detail/tickers");
    return NextResponse.json(data);
  } catch (error) {
    const message = error instanceof Error ? error.message : "종목 목록을 불러오지 못했습니다.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
