// POC2 ML Baseline v0 룩백 검증 (2026-06-11) — GET /ml/baseline-v0/latest.
//
// 저장된 state/ml/ml_baseline_v0_report_latest.json 만 조회. baseline 재계산 X,
// feature 생성 X, 외부 source 호출 X, ML 학습 X, 매수/매도 판단 X.

import { request } from "./core";

export type MlBaselineStatus =
  | "ok"
  | "warn"
  | "insufficient_history"
  | "error"
  | string;

export interface MlBaselineFeatureRange {
  start?: string | null;
  end?: string | null;
  trading_days?: number;
}

export interface MlBaselineEvaluatedRange {
  start?: string | null;
  end?: string | null;
  evaluated_days?: number;
}

export interface MlCandidateBaseline {
  status: MlBaselineStatus;
  evaluated_days: number;
  evaluated_ticker_count: number;
  target_horizons: number[];
  top_group_quantile: number;
  top_group_avg_future_return: Record<string, number | null>;
  top_group_avg_future_excess_return: Record<string, number | null>;
  universe_median_future_return: Record<string, number | null>;
  hit_rate: Record<string, number | null>;
  rank_correlation: Record<string, number | null>;
  // 지시문 §7.4 — 단순 baseline 비교 (composite 와 별도).
  simple_baselines?: Record<string, Record<string, number | null>>;
  sample_asof_results: Array<Record<string, unknown>>;
  warnings: string[];
  errors: string[];
}

export interface MlRiskBaseline {
  status: MlBaselineStatus;
  evaluated_days: number;
  target_horizons: Record<string, number[]>;
  high_risk_group_future_return: Record<string, number | null>;
  high_risk_group_future_drawdown: Record<string, number | null>;
  low_risk_group_future_return: Record<string, number | null>;
  low_risk_group_future_drawdown: Record<string, number | null>;
  high_minus_low_return: Record<string, number | null>;
  drawdown_capture_rate: Record<string, number | null>;
  high_risk_group_future_down_ratio_5d: number | null;
  low_risk_group_future_down_ratio_5d: number | null;
  // 지시문 §8.4 — 단순 baseline 비교 3종 (composite tercile 과 별도).
  simple_baselines?: Record<string, Record<string, number | null>>;
  sample_asof_results: Array<Record<string, unknown>>;
  warnings: string[];
  errors: string[];
}

export interface MlLeakageChecks {
  feature_future_data_leakage_detected: boolean;
  target_horizon_short_tail_excluded: boolean;
  time_order_preserved: boolean;
  candidate_tail_asof_count: number;
  risk_tail_asof_count: number;
  details: string[];
}

export interface MlBaselineV0Report {
  status: MlBaselineStatus;
  generated_at: string;
  feature_asof_range: MlBaselineFeatureRange;
  evaluated_asof_range: MlBaselineEvaluatedRange;
  coverage_checks: Record<string, unknown>;
  candidate_baseline: MlCandidateBaseline;
  risk_baseline: MlRiskBaseline;
  leakage_checks: MlLeakageChecks;
  warnings: string[];
  errors: string[];
}

export interface MlBaselineV0Response {
  status: "ok" | "empty" | "error";
  report_path: string;
  report: MlBaselineV0Report | null;
  message?: string | null;
}

export function fetchMlBaselineV0Latest(): Promise<MlBaselineV0Response> {
  return request<MlBaselineV0Response>("GET", "/ml/baseline-v0/latest");
}
