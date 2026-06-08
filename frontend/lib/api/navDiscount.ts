// POC2 NAV / Discount Display FIX (2026-06-08) —
// GET /market/nav-discount/latest read-only 호출.
//
// 저장된 etf_nav_daily 만 조회한다. refresh / 외부 호출 0건.

import { request } from "./core";

export type NavDiscountStatus = "ok" | "partial" | "unavailable" | string;

export interface NavDiscountItem {
  ticker: string;
  name: string | null;
  nav: number | null;
  market_price: number | null;
  discount_rate_pct: number | null;
  flag: string | null;
  asof: string;
  source: string;
  status: NavDiscountStatus;
  message: string | null;
}

export interface NavDiscountSummary {
  total_count: number;
  ok_count: number;
  unavailable_count: number;
  failed_count: number;
}

export interface NavDiscountLatestResponse {
  status: "ok" | "empty";
  asof: string | null;
  source: string | null;
  summary: NavDiscountSummary;
  items: NavDiscountItem[];
}

export function fetchNavDiscountLatest(): Promise<NavDiscountLatestResponse> {
  return request<NavDiscountLatestResponse>("GET", "/market/nav-discount/latest");
}
