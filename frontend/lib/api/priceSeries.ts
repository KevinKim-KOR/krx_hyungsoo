// POC3-02 REMEDIATION-1 — 선택 ETF 가격 시계열 read-only client.
// GET /market/price-series?ticker= — 저장된 etf_daily_price 를 그대로 반환.
// 사용자가 표에서 종목 선택 시에만 lazy 조회 (frontend). 신규 산식·source 없음.

import { request } from "./core";

export interface PricePoint {
  date: string;
  price: number;
}

export type PriceSeriesAvailability = "AVAILABLE" | "NO_DATA" | "UNAVAILABLE";

export interface PriceSeriesResponse {
  ticker: string;
  availability: PriceSeriesAvailability;
  reason?: string | null;
  available_from?: string | null;
  available_to?: string | null;
  series: PricePoint[];
}

export function fetchPriceSeries(ticker: string): Promise<PriceSeriesResponse> {
  const params = new URLSearchParams({ ticker });
  return request<PriceSeriesResponse>(
    "GET",
    `/market/price-series?${params.toString()}`,
  );
}

// POC3-01 오늘의 투자 점검 — 시장지수 benchmark 시계열 (코스피 대표 차트).
// 같은 엔드포인트 확장 (?benchmark=KOSPI). 저장값 read-only, 신규 산식 없음.
export function fetchBenchmarkSeries(
  benchmark: string,
): Promise<PriceSeriesResponse> {
  const params = new URLSearchParams({ benchmark });
  return request<PriceSeriesResponse>(
    "GET",
    `/market/price-series?${params.toString()}`,
  );
}
