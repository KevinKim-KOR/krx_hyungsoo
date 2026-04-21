import { NextRequest, NextResponse } from "next/server";

import { refreshSingleStock } from "@/lib/stocks-store";

export async function POST(request: NextRequest) {
  try {
    const payload = (await request.json()) as {
      ticker_type?: string;
      ticker?: string;
    };

    const result = await refreshSingleStock(String(payload.ticker_type ?? ""), String(payload.ticker ?? ""));
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "종목 새로고침에 실패했습니다." },
      { status: 400 },
    );
  }
}
