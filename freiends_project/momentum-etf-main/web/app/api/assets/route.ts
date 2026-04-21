import { NextResponse } from "next/server";

import { fetchFastApiJson } from "@/lib/internal-api";

type HoldingsRow = {
  account_name: string;
  currency: string;
  bucket: string;
  bucket_id: number;
  ticker: string;
  name: string;
  quantity: number;
  average_buy_price: string;
  current_price: string;
  pnl_krw: number;
  return_pct: number;
  buy_amount_krw: number;
  valuation_krw: number;
  target_ratio?: number | null;
  target_quantity?: number | null;
  target_amount?: number | null;
};

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const account = searchParams.get("account");

  try {
    const search = account ? `?account=${encodeURIComponent(account)}` : "";
    const payload = await fetchFastApiJson<{
      accounts?: any[];
      account_id?: string;
      rows: HoldingsRow[];
    }>(`/internal/holdings${search}`);
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "보유 종목을 불러오지 못했습니다." },
      { status: 400 },
    );
  }
}

export async function DELETE(request: Request) {
  const { searchParams } = new URL(request.url);
  const account = searchParams.get("account") ?? "";
  const ticker = searchParams.get("ticker") ?? "";

  try {
    const payload = await fetchFastApiJson<{ deleted?: string; error?: string }>(
      `/internal/holdings?account=${encodeURIComponent(account)}&ticker=${encodeURIComponent(ticker)}`,
      { method: "DELETE" },
    );
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "종목 삭제에 실패했습니다." },
      { status: 400 },
    );
  }
}

export async function PUT(request: Request) {
  try {
    const body = await request.json();
    const payload = await fetchFastApiJson<{ message?: string; error?: string }>(
      "/internal/cash",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ accounts: [body] }),
      },
    );
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "자산 정보 저장에 실패했습니다." },
      { status: 400 },
    );
  }
}

export async function PATCH(request: Request) {
  try {
    const body = await request.json();
    const endpoint = body.action === "reorder" ? "/internal/holdings/order" : "/internal/holdings";
    const payload = await fetchFastApiJson<{ updated?: string; reordered?: number; error?: string }>(
      endpoint,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "종목 수정에 실패했습니다." },
      { status: 400 },
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const action = body.action ?? "create";

    if (action === "validate") {
      const payload = await fetchFastApiJson<{ ticker?: string; name?: string; bucket_id?: number; error?: string }>(
        "/internal/holdings/validate",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            account_id: body.account_id,
            ticker: body.ticker,
          }),
        },
      );
      return NextResponse.json(payload);
    }

    const payload = await fetchFastApiJson<{ added?: string; error?: string }>(
      "/internal/holdings",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          account_id: body.account_id,
          ticker: body.ticker,
          quantity: body.quantity,
          average_buy_price: body.average_buy_price,
          target_ratio: body.target_ratio,
          memo: body.memo,
        }),
      },
    );
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "요청 처리 중 오류가 발생했습니다." },
      { status: 400 },
    );
  }
}

export const dynamic = "force-dynamic";
