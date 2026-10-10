// POC5-06 — 수동 재진입 검토 · ML 근거(PC 로컬 API · 설계 개정 2).
//   GET  /holdings/trade-history/reentry-review     검토 창(내 거래 · 저장된 근거) — 학습 · 외부 조회 · 쓰기 0
//   POST /holdings/trade-history/reentry-review/ml  선택 ETF 하나의 D20 연구 1회 → PC 연구 산출물
// 연구 추정이며 매수/매도 지시가 아니다. 오류 detail 은 문자열(404 = 보유가 바뀜 · 500 = 파일 · 시세 DB ·
// 산출물 저장 실패).

import { request } from "./core";
import type { MarketFlowResponse, PositionHistory } from "./holdingsHistory";

export type ReentryStatus =
  | "OK"
  | "DATA_SHORT"
  | "PRICE_BASIS_UNCONFIRMED"
  | "NOT_ETF"
  | "NO_PRICE"
  | "AXIS_UNCERTAIN"
  | "READ_FAILED"
  | "NO_COPY";

export type ReentryFeatureName = "chg5" | "chg20" | "chg60" | "vol20" | "from_high60";

export interface ReentryAxisView {
  label: string;
  limit_note: string;
  rule: string;
  modes: Record<string, string>;
  skipped_weekday_count: number;
  kospi_latest: string | null;
  length: number;
  first: string | null;
  last: string | null;
}

export interface ReentryPriceState {
  status: ReentryStatus;
  reason: string | null;
  t?: string;
  latest_close?: number | null;
  latest_source?: string | null;
  expected_completed_date?: string | null;
  stale?: boolean;
  stale_note?: string | null;
  price_basis_label?: string;
  partial_check_note?: string;
  axis?: ReentryAxisView;
  features?: Record<ReentryFeatureName, number> | null;
}

export interface LedgerOutcomeView {
  series_id: string;
  horizon: number;
  status: string;
  eval_date: string | null;
  return_raw: number | null;
  max_up_raw: number | null;
  max_down_raw: number | null;
  price_basis: string | null;
  computed_at: string | null;
}

export interface LedgerFeedbackView {
  scope: "EVENT";
  scope_text: string;
  count: number;
  latest: {
    feedback_seq: number;
    helpfulness: string;
    action: string | null;
    memo: string | null;
    feedback_at: string;
  } | null;
}

export type LedgerLinkKind = "SUBJECT" | "SECTOR_REPRESENTATIVE" | "INDEX_GROUP_MEMBER";

export interface LedgerEvidenceItem {
  link_kind: LedgerLinkKind;
  link_text: string;
  event_id: string;
  item_seq: number;
  push_kind: string;
  runtime_kst: string | null;
  runtime_date_kst: string | null;
  subject_kind: string;
  subject_id: string;
  state: string | null;
  state_label: string | null;
  disposition: string;
  delivery_status: string | null;
  view: "DELIVERED" | "PARTIAL" | "NOT_DELIVERED" | "OBSERVED";
  view_text: string;
  exposure: string;
  cohort: string | null;
  off_schedule: number;
  contract_version: string | null;
  outcome_target: boolean;
  outcomes: LedgerOutcomeView[];
  pending_horizons: number[];
  feedback: LedgerFeedbackView;
}

export interface LedgerEvidence {
  ticker: string;
  status: ReentryStatus;
  status_text: string | null;
  synced_at: string | null;
  items: LedgerEvidenceItem[];
  counts: Record<string, Record<string, number>>;
  problems?: string[]; // 사본 손상 사유(READ_FAILED · 04 판정과 같은 규칙)
}

export interface ReentryReviewResponse {
  schema: string;
  read_only: boolean;
  selection: {
    position_id: string;
    cycle_id: string;
    ticker: string;
    name: string | null;
    account_group: string;
  };
  read_basis: {
    holdings_status: string;
    revision: number;
    doc_sha256: string;
    ledger_synced_at: string | null;
    price_latest: string | null;
  };
  my_trades: {
    position: PositionHistory;
    selected_cycle_id: string;
    previous_cycle_ids: string[];
    summary: {
      status: "OPEN" | "CLOSED";
      opened_by: string;
      closed_by: string | null;
      purchase_date_unknown: boolean;
      closed_by_adjustment: boolean;
      last_actual_sell_date: string | null;
      has_adjustment: boolean;
    };
    notes: string[];
  };
  stored_evidence: {
    market_flow: MarketFlowResponse;
    price_state: ReentryPriceState;
    ledger: LedgerEvidence;
  };
  ml: { available: boolean; target_name: string; note: string };
  navigation: { menu: string; label: string; note: string }[];
  notes: string[];
}

export interface ReentryBlock {
  block: number;
  first_date: string;
  last_date: string;
  axis_dates: number;
  train_n: number;
  valid_n: number;
  excluded_n: number;
  status: ReentryStatus;
  train_last_eval_end?: string;
  baseline_median_pct?: number;
  mae_model_pp?: number;
  mae_baseline_pp?: number;
}

export interface ReentryMlResult {
  status: ReentryStatus;
  reason: string | null;
  t?: string;
  features_at_t?: Record<ReentryFeatureName, number> | null;
  samples?: { valid_n: number; excluded_by_reason: Record<string, number> };
  blocks?: ReentryBlock[];
  overall?: {
    n: number;
    mae_model_pp: number;
    mae_baseline_pp: number;
    verdict: "IMPROVED" | "NO_DIFFERENCE" | "WORSE";
    verdict_text: string;
  };
  final?: {
    train_n: number;
    train_first: string;
    train_last: string;
    estimate_pct: number;
    baseline_median_pct: number;
  };
}

export interface ReentryMlResponse {
  schema: string;
  status: ReentryStatus;
  status_text: string;
  reason: string | null;
  ticker: string;
  target_name: string;
  t: string | null;
  expected_completed_date: string | null;
  stale: boolean;
  stale_note: string | null;
  result: ReentryMlResult;
  axis: ReentryAxisView | null;
  price_basis_label: string;
  partial_check_note: string;
  canonical_sha256: string;
  read_basis: ReentryReviewResponse["read_basis"];
  libraries: Record<string, string | null>;
  notes: string[];
  runtime_seconds: number;
  artifact: { folder: string; files: string };
}

const BASE = "/holdings/trade-history/reentry-review";
const ML_TIMEOUT_MS = 60000; // 첫 실행은 학습 라이브러리를 불러온다

export async function fetchReentryReview(
  positionId: string,
  cycleId: string,
): Promise<ReentryReviewResponse> {
  const q = new URLSearchParams({ position_id: positionId, cycle_id: cycleId }).toString();
  return request<ReentryReviewResponse>("GET", `${BASE}?${q}`);
}

export async function runReentryMl(
  positionId: string,
  cycleId: string,
): Promise<ReentryMlResponse> {
  return request<ReentryMlResponse>(
    "POST",
    `${BASE}/ml`,
    { position_id: positionId, cycle_id: cycleId },
    ML_TIMEOUT_MS,
  );
}
