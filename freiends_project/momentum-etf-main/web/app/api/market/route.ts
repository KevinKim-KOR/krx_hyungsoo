import { NextResponse } from "next/server";

import { loadEtfMarketTable } from "@/lib/market-store";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const market = await loadEtfMarketTable();
    return NextResponse.json(market);
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "ETF 마켓 데이터를 불러오지 못했습니다.",
      },
      { status: 500 },
    );
  }
}
