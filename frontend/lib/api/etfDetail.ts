// POC6-29(PLAN §2-7 · §3-3 · 판정 Q4-1) — GET /market/etf-detail?tickers= — 종목 상세 수치(읽기 전용).
// 행을 펼치면 그 종목, [표]를 열면 지금 보는 범위, 「보유와 후보 비교」는 고른 두 종목을 한 번에 읽는다.
// 표 · 행 상세 · 비교가 같은 응답 모양 · 같은 값 · 같은 날짜를 쓴다(공통 끝일 = ETF 목록 저장 최신일).

import { request } from "./core";
import { ETF_DETAIL_KEY_PREFIX } from "./dashboardKeys";
import type { EndPrice } from "./etfCompare";

export type DetailStatus = "ok" | "period_differs" | "missing";

export interface DetailPeriod {
  status: DetailStatus;
  value: number | null;
  start: string | null;
  end: string | null;
  start_close: number | null;
  end_close: number | null;
  reason: string | null;
}

export interface DetailExcess {
  status: DetailStatus;
  value_pctp: number | null;
  etf_return_pct: number | null;
  kodex200_return_pct: number | null;
  start: string | null;
  end: string | null;
  // 서버가 함께 주는 KODEX 200 창의 실제 시작 · 끝일(양쪽 날짜가 같을 때만 차이를 계산).
  kodex200_start?: string | null;
  kodex200_end?: string | null;
  reason: string | null;
}

export interface DetailSameKodex {
  status: DetailStatus;
  value: number | null;
  etf_return_pct: number | null;
  kodex200_return_pct: number | null;
  start: string | null;
  end: string | null;
  reason: string | null;
}

export interface DetailDrawdown {
  status: DetailStatus;
  value: number | null;
  start: string | null;
  end: string | null;
  peak_date: string | null;
  peak_close: number | null;
  close: number | null;
  reason: string | null;
}

export interface DetailNav {
  status: "ok" | "missing" | "not_applicable";
  nav: number | null;
  market_price: number | null;
  discount_rate_pct: number | null;
  flag: "discount_check_needed" | "discount_warning" | null;
  asof: string | null;
  row_status?: string | null;
  message?: string | null;
}

export interface EtfDetailItem {
  ticker: string;
  name: string | null;
  is_etf: boolean;
  last_date: string | null;
  end_price: EndPrice | null;
  daily: DetailPeriod;
  w5: DetailPeriod;
  w20: DetailPeriod;
  m1: DetailPeriod;
  m3: DetailPeriod;
  m6: DetailPeriod;
  m12: DetailPeriod;
  excess20: DetailExcess;
  same_kodex: { one_month: DetailSameKodex; three_month: DetailSameKodex };
  drawdown: DetailDrawdown;
  nav: DetailNav;
}

export interface EtfDetailResponse {
  status: "ok" | "missing" | "empty" | "invalid";
  message: string | null;
  end_date: string | null;
  kodex200: { window20: DetailPeriod | null };
  items: EtfDetailItem[];
}

export const ETF_DETAIL_MAX = 30;

function uniq(tickers: readonly string[]): string[] {
  return [...new Set(tickers.filter((t) => !!t))].slice(0, ETF_DETAIL_MAX);
}

export function etfDetailKey(tickers: readonly string[]): string {
  return `${ETF_DETAIL_KEY_PREFIX}tickers=${uniq(tickers).join(",")}`;
}

export function fetchEtfDetail(tickers: readonly string[]): Promise<EtfDetailResponse> {
  const params = new URLSearchParams({ tickers: uniq(tickers).join(",") });
  return request<EtfDetailResponse>("GET", `/market/etf-detail?${params.toString()}`);
}
