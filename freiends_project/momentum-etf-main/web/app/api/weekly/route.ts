import { NextRequest, NextResponse } from "next/server";

import { aggregateActiveWeekData, loadWeeklyTableData, updateWeeklyRow } from "../../../lib/weekly-store";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await loadWeeklyTableData();
    return NextResponse.json(data);
  } catch (error) {
    const message = error instanceof Error ? error.message : "주별 데이터를 불러오지 못했습니다.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function POST() {
  try {
    const result = await aggregateActiveWeekData();
    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "이번주 데이터 집계에 실패했습니다.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const payload = (await request.json()) as { week_date?: string } & Record<string, unknown>;
    const result = await updateWeeklyRow(payload.week_date ?? "", payload);
    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "주별 데이터 저장에 실패했습니다.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
