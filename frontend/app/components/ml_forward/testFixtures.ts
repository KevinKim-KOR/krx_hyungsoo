// POC6-14 — 시험용 가짜 응답(실제 연구 자료 아님 · 앱 코드에서 쓰지 않음).
import type { ForwardComparisonResponse, ForwardRow } from "@/lib/api";

export const ROW: ForwardRow = {
  ticker: "0015K0",
  name: "TIGER 미국소비트렌드액티브",
  primary: true,
  methods: {
    MEDIAN: { status: "OK", pred_pct: -3.06 },
    RIDGE: { status: "OK", pred_pct: -0.0001 },
    HGB: { status: "ENV_MISMATCH", reason: "scikit-learn 1.9.0 → 1.9.1" },
    MLP_CPU: { status: "OK", pred_pct: -2.27, retried_at: "2026-10-30T03:05:00.000000Z" },
  },
  actual: { state: "NOT_EVALUATED" },
  detail: {
    run_id: "20261030T010545Z_632f4d6c",
    visible_by: "2026-10-30T01:05:48.513143Z",
    write_started_at: "2026-10-30T01:05:48.508783Z",
    model_version: "mv_e926e0661c261324",
    input_cutoff: "2026-10-30T01:05:45.098128Z",
    close_cutoff_at: "2026-10-30T06:30:00.000000Z",
    input: { object: "10b74d9067d3abc", observed_at: "2026-10-30T00:40:12Z", available_at: "2026-10-30T00:47:16Z" },
  },
};

export const DATA: ForwardComparisonResponse = {
  status: "OK",
  label: "연구용 · 운영 미채택",
  cohort: { id: "cohort_v1", size: 24 },
  dates: [
    { D: "2026-10-29", primary_rows: 24 },
    { D: "2026-10-27", primary_rows: 24 },
  ],
  selected_D: "2026-10-29",
  basis: {
    visible_by: { min: "2026-10-30T01:05:48.513143Z", max: "2026-10-30T01:05:48.513143Z" },
    input_cutoff: { min: "2026-10-30T01:05:45.098128Z", max: "2026-10-30T01:05:45.098128Z" },
    close_cutoff_at: { min: "2026-10-30T06:30:00.000000Z", max: "2026-10-30T06:30:00.000000Z" },
    record_runs: ["20261030T010545Z_632f4d6c"],
    model_versions: ["mv_e926e0661c261324"],
    maturity: null,
    unreadable_runs: [],
  },
  rows: [ROW, { ticker: "108450", name: "ACE 삼성그룹섹터가중", primary: false, why: "NO_EVIDENCE" }],
  report: {
    state: "OK",
    selected_D: "INCLUDED",
    id: "20261030T010545Z_632f4d6c",
    generated_at: "2026-10-30T01:05:48.515504Z",
    counts: { primary_records: 72, matured: 0, pending_or_missing: 72, predicted_by_method: { MEDIAN: 72 } },
    predicted_dates: { count: 3, first: "2026-10-22", last: "2026-10-29" },
    matured_dates: { count: 0, first: null, last: null },
    comparisons: {
      ALL_FOUR: {
        rows: 0,
        dates: 0,
        tickers: 0,
        excluded_rows: 0,
        mae_pp: { MEDIAN: null },
        deep: { rows: 0, under_estimate_pp: {} },
      },
    },
    newer_unreadable: [],
  },
  other: { unconfirmed_forward_records: 0, diagnostic_entries: 0, supplementary_entries: 0 },
};
