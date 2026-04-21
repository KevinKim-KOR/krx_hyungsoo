import { NextResponse } from "next/server";

import { loadDashboardData } from "@/lib/dashboard-store";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const dashboard = await loadDashboardData();
    return NextResponse.json(dashboard);
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "대시보드 데이터를 불러오지 못했습니다.",
      },
      { status: 500 },
    );
  }
}
