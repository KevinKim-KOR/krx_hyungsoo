import { NextRequest, NextResponse } from "next/server";

import {
  hardDeleteStocks,
  loadDeletedStocksTable,
  restoreDeletedStocks,
} from "@/lib/deleted-stocks-store";

export async function GET(request: NextRequest) {
  try {
    const tickerType = request.nextUrl.searchParams.get("ticker_type") ?? undefined;
    const payload = await loadDeletedStocksTable(tickerType);
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "삭제된 종목 데이터를 불러오지 못했습니다." },
      { status: 400 },
    );
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const payload = (await request.json()) as {
      ticker_type?: string;
      tickers?: string[];
    };

    const restoredCount = await restoreDeletedStocks(
      String(payload.ticker_type ?? ""),
      Array.isArray(payload.tickers) ? payload.tickers : [],
    );
    return NextResponse.json({ ok: true, restored_count: restoredCount });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "종목 복구에 실패했습니다." },
      { status: 400 },
    );
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const payload = (await request.json()) as {
      ticker_type?: string;
      tickers?: string[];
    };

    const deletedCount = await hardDeleteStocks(
      String(payload.ticker_type ?? ""),
      Array.isArray(payload.tickers) ? payload.tickers : [],
    );
    return NextResponse.json({ ok: true, deleted_count: deletedCount });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "종목 완전 삭제에 실패했습니다." },
      { status: 400 },
    );
  }
}
