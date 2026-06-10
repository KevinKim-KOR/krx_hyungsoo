// POC2 ML Feature Sanity Check (2026-06-08) — GET /ml/feature-sanity/latest read-only.
//
// 저장된 state/ml/ml_feature_sanity_latest.json 만 조회. feature 재계산 X,
// 외부 source 호출 X.

import { request } from "./core";

export type MlSanityStatus = "ok" | "warn" | "error" | string;

export interface MlSanitySampleRow {
  ticker: string;
  name?: string | null;
  asof: string;
  return_5d?: number | null;
  return_10d?: number | null;
  return_20d?: number | null;
  excess_return_5d_vs_kodex200?: number | null;
  excess_return_20d_vs_kodex200?: number | null;
  volatility_20d?: number | null;
  drawdown_20d?: number | null;
  volume_ratio_20d?: number | null;
  nav_discount_rate_pct?: number | null;
  nav_status?: string | null;
}

export interface MlSanitySubChecks {
  status: MlSanityStatus;
  warnings?: string[];
  errors?: string[];
  [key: string]: unknown;
}

export interface MlSanitySnapshot {
  generated_at: string;
  feature_asof_range: {
    start?: string | null;
    end?: string | null;
    trading_days?: number;
  };
  etf_feature_row_count: number;
  market_risk_row_count: number;
  checked_ticker_count: number;
  sampled_tickers: string[];
  sanity_status: MlSanityStatus;
  coverage_checks: MlSanitySubChecks;
  calculation_checks: MlSanitySubChecks;
  nav_join_checks: MlSanitySubChecks;
  risk_proxy_checks: MlSanitySubChecks;
  outlier_checks?: MlSanitySubChecks;
  sample_rows: MlSanitySampleRow[];
  warnings: string[];
  errors: string[];
}

export interface MlFeatureSanityResponse {
  // ok: snapshot 정상 / empty: 미생성 / error: 파일 손상 (fail-loud)
  status: "ok" | "empty" | "error";
  snapshot_path: string;
  snapshot: MlSanitySnapshot | null;
  message?: string | null;
}

export function fetchMlFeatureSanityLatest(): Promise<MlFeatureSanityResponse> {
  return request<MlFeatureSanityResponse>(
    "GET",
    "/ml/feature-sanity/latest",
  );
}
