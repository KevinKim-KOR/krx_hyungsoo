import { NextRequest, NextResponse } from "next/server";

import {
  deleteBacktestConfig,
  listBacktestConfigs,
  loadBacktestConfig,
  runBacktest,
  saveBacktestConfig,
  validateBacktestTicker,
} from "@/lib/backtest-store";

export async function GET(request: NextRequest) {
  try {
    const configId = request.nextUrl.searchParams.get("config_id");
    if (configId) {
      const payload = await loadBacktestConfig(configId);
      return NextResponse.json(payload);
    }
    const payload = await listBacktestConfigs();
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "백테스트 설정을 불러오지 못했습니다." },
      { status: 400 },
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const payload = (await request.json()) as {
      action?: "validate" | "save" | "delete" | "run";
      ticker?: string;
      config_id?: string;
      name?: string;
      period_months?: number;
      slippage_pct?: number;
      country_code?: string;
      rebalance_freq?: string;
      benchmark?: {
        ticker?: string;
        name?: string;
        listing_date?: string;
      };
      groups?: Array<{
        group_id?: string;
        name?: string;
        weight?: number;
        tickers?: Array<{
          ticker?: string;
          name?: string;
          listing_date?: string;
        }>;
      }>;
    };

    const countryCode = String(payload.country_code ?? "kor");

    if (payload.action === "validate") {
      const result = await validateBacktestTicker(String(payload.ticker ?? ""), countryCode);
      return NextResponse.json(result);
    }

    if (payload.action === "delete") {
      const result = await deleteBacktestConfig(String(payload.config_id ?? ""));
      return NextResponse.json(result);
    }

    const normalizedGroups = Array.isArray(payload.groups)
      ? payload.groups.map((group) => ({
          group_id: group.group_id,
          name: String(group.name ?? ""),
          weight: Number(group.weight ?? 0),
          tickers: Array.isArray(group.tickers)
            ? group.tickers.map((ticker) => ({
                ticker: String(ticker.ticker ?? ""),
                name: String(ticker.name ?? ""),
                listing_date: String(ticker.listing_date ?? ""),
              }))
            : [],
        }))
      : [];
    const normalizedBenchmark = payload.benchmark
      ? {
          ticker: String(payload.benchmark.ticker ?? ""),
          name: String(payload.benchmark.name ?? ""),
          listing_date: String(payload.benchmark.listing_date ?? ""),
        }
      : null;

    if (payload.action === "run") {
      const result = await runBacktest(
        Number(payload.period_months ?? 0),
        Number(payload.slippage_pct ?? 0.5),
        normalizedBenchmark,
        normalizedGroups,
        countryCode,
        String(payload.rebalance_freq ?? "monthly"),
      );
      return NextResponse.json(result);
    }

    const result = await saveBacktestConfig(
      String(payload.name ?? ""),
      Number(payload.period_months ?? 0),
      Number(payload.slippage_pct ?? 0.5),
      normalizedBenchmark,
      normalizedGroups,
      String(payload.rebalance_freq ?? "monthly"),
    );
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "백테스트 저장 처리에 실패했습니다." },
      { status: 400 },
    );
  }
}
