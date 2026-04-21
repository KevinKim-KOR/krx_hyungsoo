import { NextRequest, NextResponse } from "next/server";

import { loadSystemData, triggerSystemAction } from "../../../lib/system-store";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await loadSystemData();
    return NextResponse.json(data);
  } catch (error) {
    const message = error instanceof Error ? error.message : "시스템정보 데이터를 불러오지 못했습니다.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const payload = (await request.json()) as { action?: string };
    const allowed = new Set([
      "cache_refresh",
      "market_hours_analysis",
      "metadata_updater",
      "asset_summary",
    ] as const);
    const actionStr = String(payload.action || "").trim();
    if (!actionStr || !allowed.has(actionStr as never)) {
      return NextResponse.json({ error: "유효하지 않은 action 입니다." }, { status: 400 });
    }

    const message = await triggerSystemAction(
      actionStr as "cache_refresh" | "market_hours_analysis" | "metadata_updater" | "asset_summary",
    );
    return NextResponse.json({ message });
  } catch (error) {
    const message = error instanceof Error ? error.message : "시스템 작업 실행에 실패했습니다.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
