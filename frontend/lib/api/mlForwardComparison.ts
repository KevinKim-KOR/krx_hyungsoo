// POC6-14 — GET /ml/forward-comparison(06 전향 ML 비교 기록 · PC 읽기 전용).
//
// 연구용 · 운영 미채택(추천 · 매매 아님). 서버는 06 기록을 읽기만 한다(실행 · 학습 · 보고 생성 0).
// 단위: 예측 · 실제 = `*_pct`(서버가 비율 ×100 한 번) · MAE · 작게 추정한 정도 = `*_pp`(보고 값 그대로 · 다시 곱하지 않음).
// 숫자가 허용 범위를 어기면 서버가 숫자 대신 status/state = CHECK_REQUIRED 로 준다.

import { request } from "./core";

export type ForwardViewStatus = "OK" | "NO_RECORDS" | "CHECK_REQUIRED" | "READ_FAILED";
export type ForwardMethodKey = "MEDIAN" | "RIDGE" | "HGB" | "MLP_CPU";

export interface ForwardMethodCell {
  status: string; // OK | FAILED | ENV_MISMATCH | NOT_RUN_ENV | DATA_SHORT | CHECK_REQUIRED | MISSING
  pred_pct?: number | null;
  reason?: string | null;
  retried_at?: string | null;
}

export type ForwardActualState =
  | "MATURED"
  | "PENDING_NOT_DUE"
  | "PENDING_CALENDAR"
  | "DUE_DATA_MISSING"
  | "DATA_CHECK_REQUIRED"
  | "NOT_EVALUATED"
  | "CHECK_REQUIRED";

export interface ForwardActual {
  state: ForwardActualState;
  actual_pct?: number | null;
  target_end?: string | null;
  basis_run?: string | null;
  basis_at?: string | null;
  reason?: string | null;
}

export interface ForwardRowDetail {
  run_id: string;
  visible_by: string;
  write_started_at: string;
  model_version: string;
  input_cutoff?: string | null;
  close_cutoff_at?: string | null;
  input: { object?: string | null; observed_at?: string | null; available_at?: string | null };
}

export interface ForwardRow {
  ticker: string;
  name?: string | null;
  primary: boolean;
  why?: string | null;
  methods?: Record<ForwardMethodKey, ForwardMethodCell>;
  actual?: ForwardActual;
  detail?: ForwardRowDetail;
}

export interface TimeSpan {
  min: string;
  max: string;
}

export interface ForwardBasis {
  visible_by: TimeSpan | null;
  input_cutoff: TimeSpan | null;
  close_cutoff_at: TimeSpan | null;
  record_runs: string[];
  model_versions: string[];
  maturity: { runs: string[]; at: TimeSpan | null } | null;
  unreadable_runs: string[];
}

export interface ForwardComparisonEntry {
  rows: number | null;
  dates: number | null;
  tickers: number | null;
  excluded_rows: number | null;
  mae_pp: Partial<Record<ForwardMethodKey, number | null>>;
  deep: { rows: number | null; under_estimate_pp: Partial<Record<ForwardMethodKey, number | null>> };
}

export interface ForwardDateSpan {
  count: number;
  first: string | null;
  last: string | null;
}

export interface ForwardReport {
  state: "OK" | "NONE" | "CHECK_REQUIRED";
  selected_D: "INCLUDED" | "RUN_REPORT_MISSING" | "RUN_REPORT_UNREADABLE";
  id?: string | null;
  generated_at?: string;
  counts?: Record<string, unknown>;
  predicted_dates?: ForwardDateSpan;
  matured_dates?: ForwardDateSpan;
  comparisons?: Record<string, ForwardComparisonEntry>;
  newer_unreadable?: string[];
  unreadable?: string[];
}

export interface ForwardOtherCounts {
  unconfirmed_forward_records: number;
  diagnostic_entries: number;
  supplementary_entries: number;
}

export interface ForwardComparisonResponse {
  status: ForwardViewStatus;
  label: string;
  message?: string | null;
  cohort?: { id: string; size: number; selected_at?: string | null } | null;
  dates?: { D: string; primary_rows: number }[] | null;
  selected_D?: string | null;
  basis?: ForwardBasis | null;
  rows?: ForwardRow[] | null;
  report?: ForwardReport | null;
  other?: ForwardOtherCounts | null;
}

export function fetchForwardComparison(d?: string): Promise<ForwardComparisonResponse> {
  const q = d ? `?d=${encodeURIComponent(d)}` : "";
  return request<ForwardComparisonResponse>("GET", `/ml/forward-comparison${q}`);
}
