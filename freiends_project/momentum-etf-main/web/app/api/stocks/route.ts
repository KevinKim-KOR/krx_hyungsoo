import { NextRequest, NextResponse } from "next/server";

import { addStockCandidate, deleteStock, loadStocksTable, updateStockBucket, validateStockCandidate } from "@/lib/stocks-store";

export async function GET(request: NextRequest) {
  try {
    const tickerType = request.nextUrl.searchParams.get("ticker_type") ?? undefined;
    const payload = await loadStocksTable(tickerType);
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "종목 관리 데이터를 불러오지 못했습니다." },
      { status: 400 },
    );
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const payload = (await request.json()) as {
      ticker_type?: string;
      ticker?: string;
      bucket_id?: number;
    };

    await updateStockBucket(
      String(payload.ticker_type ?? ""),
      String(payload.ticker ?? ""),
      Number(payload.bucket_id ?? 0),
    );
    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "버킷 변경에 실패했습니다." },
      { status: 400 },
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const payload = (await request.json()) as
      | {
          ticker_type?: string;
          ticker?: string;
          action?: "validate";
        }
      | {
          ticker_type?: string;
          ticker?: string;
          bucket_id?: number;
          action?: "create";
        };

    if (payload.action === "validate") {
      const result = await validateStockCandidate(String(payload.ticker_type ?? ""), String(payload.ticker ?? ""));
      return NextResponse.json(result);
    }

    const result = await addStockCandidate(
      String(payload.ticker_type ?? ""),
      String(payload.ticker ?? ""),
      Number("bucket_id" in payload ? payload.bucket_id ?? 0 : 0),
    );
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "종목 추가 처리에 실패했습니다." },
      { status: 400 },
    );
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const payload = (await request.json()) as {
      ticker_type?: string;
      ticker?: string;
    };

    await deleteStock(String(payload.ticker_type ?? ""), String(payload.ticker ?? ""));
    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "종목 삭제에 실패했습니다." },
      { status: 400 },
    );
  }
}
