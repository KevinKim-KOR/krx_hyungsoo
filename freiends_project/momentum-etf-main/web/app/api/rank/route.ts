import { NextRequest, NextResponse } from "next/server";

import { loadRankData } from "../../../lib/rank-store";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const tickerType = searchParams.get("ticker_type") ?? undefined;
    const asOfDate = searchParams.get("as_of_date") ?? undefined;
    const maRuleOverrides = Array.from({ length: 2 }, (_, index) => index + 1)
      .map((order) => {
        const maType = searchParams.get(`rule${order}_ma_type`);
        const maMonthsRaw = searchParams.get(`rule${order}_ma_months`);
        if (!maType && !maMonthsRaw) {
          return null;
        }
        return {
          order,
          ma_type: maType ?? "",
          ma_months: maMonthsRaw ? Number(maMonthsRaw) : 0,
          ma_days: 0,
          score_column: `추세${order}`,
        };
      })
      .filter((rule): rule is NonNullable<typeof rule> => rule !== null);
    const data = await loadRankData({
      ticker_type: tickerType,
      ma_rule_overrides: maRuleOverrides,
      as_of_date: asOfDate,
    });
    return NextResponse.json(data);
  } catch (error) {
    let message = error instanceof Error ? error.message : "순위 데이터를 불러오지 못했습니다.";
    if (message.includes("응답하지 않았습니다") || message.includes("fetch failed") || message.includes("timeout")) {
      message = "몽고디비 데이터베이스 응답 지연(타임아웃)으로 인해 순위 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.";
    }
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
