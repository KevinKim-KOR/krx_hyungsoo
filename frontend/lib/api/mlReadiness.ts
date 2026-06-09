// POC2 ML 최소 데이터 레인 (2026-06-08) — GET /ml/readiness/latest read-only.
//
// 저장된 etf_ml_feature_daily / market_risk_feature_daily 의 row 수 + latest asof
// 를 조회한다. 외부 source 호출 X.

import { request } from "./core";

export type MlReadinessStatus = "available" | "partial" | "empty" | string;

export interface MlReadinessAxis {
  label: string;
  status: MlReadinessStatus;
  note: string;
}

export interface MlReadinessResponse {
  status: "ok";
  etf_feature_row_count: number;
  etf_distinct_asof_count: number;
  etf_latest_asof: string | null;
  market_risk_row_count: number;
  market_risk_latest_asof: string | null;
  axes: MlReadinessAxis[];
}

export function fetchMlReadinessLatest(): Promise<MlReadinessResponse> {
  return request<MlReadinessResponse>("GET", "/ml/readiness/latest");
}
