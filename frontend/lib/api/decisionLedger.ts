// POC5-03 — 받은 알림 기록(PC 원장 사본 조회 · 원장 새로고침 · 피드백).
//
// 조회 · 피드백은 PC 사본만 쓴다(SSH 0). 원장 새로고침만 OCI 읽기 전용 export 를
// 1회 실행한다 — 사용자가 버튼을 눌렀을 때만 부른다(화면 진입 · 타이머에서 부르지 않음).
// 평가(피드백)는 선택이다 — 가격 결과는 평가 여부와 무관하게 조회된다(설계 개정 2).

import { request } from "./core";

export type LedgerKind = "all" | "market" | "holdings" | "intraday";
export type Helpfulness = "HELPFUL" | "NEUTRAL" | "UNHELPFUL_CONFUSING";
export type FeedbackAction =
  | "WATCH_ONLY"
  | "BUY_OR_ADD"
  | "SELL_OR_REDUCE"
  | "OTHER";

export interface LedgerSyncStatus {
  has_copy: boolean;
  last_success_at: string | null;
  last_failure_at: string | null;
  last_failure_kind: string | null;
}

export interface LedgerKeyItem {
  subject_kind: string;
  subject_id: string;
  name: string | null;
}

export interface LedgerFeedback {
  feedback_seq: number;
  helpfulness: Helpfulness;
  action: FeedbackAction | null;
  memo: string | null;
  feedback_at: string;
}

export interface LedgerAlertCard {
  event_id: string;
  push_kind: string;
  time_kst: string | null;
  schedule_expected: string | null;
  off_schedule: boolean;
  delivery_status: "sent" | "partial";
  key_items: LedgerKeyItem[];
  latest_feedback: LedgerFeedback | null;
  feedback_count: number;
}

export interface LedgerAlertList {
  date: string;
  kind: LedgerKind;
  sync: LedgerSyncStatus;
  alerts: LedgerAlertCard[];
}

export interface LedgerItem {
  item_seq: number;
  subject_kind: string;
  subject_id: string;
  name: string | null;
  held: number | null;
  state: string | null;
  prev_state: string | null;
  // 알림 본문이 쓰는 기존 상태 라벨(없으면 코드 그대로).
  state_label: string | null;
  prev_state_label: string | null;
  disposition: string;
  event_type: string | null;
  t0_price: number | null;
  t0_price_asof: string | null;
  evaluable: boolean;
  outcome_target: boolean;
}

export interface LedgerOutcomeRow {
  item_seq: number;
  series_id: string;
  series_name: string;
  horizon: number;
  status: string;
  t0_price: number | null;
  t0_price_asof: string | null;
  eval_date: string | null;
  eval_price: number | null;
  return_raw: number | null;
  max_up_raw: number | null;
  max_down_raw: number | null;
  path_points: number | null;
}

export interface LedgerAlertDetail {
  event_id: string;
  push_kind: string;
  time_kst: string | null;
  runtime_date_kst: string | null;
  schedule_expected: string | null;
  off_schedule: boolean;
  outcome_event_target: boolean;
  delivery_status: string | null;
  body_text: string | null;
  body_withheld: boolean;
  // partial = body_text 는 분할 전 전체 생성 본문 — '일부만 전달됨' 으로 표기해야 한다.
  body_partial_delivery: boolean;
  items: LedgerItem[];
  feedback: LedgerFeedback[];
  outcomes: LedgerOutcomeRow[];
}

export interface LedgerSyncResult {
  ok: boolean;
  failure_kind: string | null;
  attempted_at: string;
  counts: Record<
    string,
    { inserted: number; updated: number; unchanged: number }
  > | null; // price_outcome 반영 수는 싣지 않는다(설계 개정 2 §3 수용)
}

export interface LedgerFeedbackInput {
  helpfulness: Helpfulness;
  action?: FeedbackAction | null;
  memo?: string | null;
}

// SSH 1회(백엔드 60초) 를 포함하므로 기본 timeout(10s) 보다 길게 허용.
const SYNC_TIMEOUT_MS = 90_000;

// date 를 주지 않으면 백엔드가 사본의 가장 최근 알림 날짜를 고른다(응답 date 로 돌려줌).
export async function fetchLedgerAlerts(
  date: string | null,
  kind: LedgerKind
): Promise<LedgerAlertList> {
  const q = new URLSearchParams(date ? { date, kind } : { kind });
  return request<LedgerAlertList>("GET", `/decision-ledger/alerts?${q}`);
}

export async function fetchLedgerAlertDetail(
  eventId: string
): Promise<LedgerAlertDetail> {
  return request<LedgerAlertDetail>(
    "GET",
    `/decision-ledger/alerts/${encodeURIComponent(eventId)}`
  );
}

export async function syncDecisionLedger(): Promise<LedgerSyncResult> {
  return request<LedgerSyncResult>(
    "POST",
    "/decision-ledger/sync",
    {},
    SYNC_TIMEOUT_MS
  );
}

export async function postLedgerFeedback(
  eventId: string,
  input: LedgerFeedbackInput
): Promise<LedgerFeedback & { event_id: string }> {
  return request<LedgerFeedback & { event_id: string }>(
    "POST",
    `/decision-ledger/alerts/${encodeURIComponent(eventId)}/feedback`,
    input
  );
}

// ── POC5-08 알림의 ML 사후평가 ───────────────────────────────────────────────
// [사후평가 실행] 을 눌렀을 때만 POST(PC 사본 읽기 → 연구 산출물). 화면 진입 · 상세 열기는
// 완성된 최신 산출물 GET 만(학습 · SSH · 쓰기 0). 평가(피드백)는 표본 · 라벨 · 입력에 쓰지 않는다.

export type RetroStatus =
  | "OK"
  | "NO_COPY"
  | "CHECK_REQUIRED"
  | "NO_RESULT"
  | "ARTIFACT_UNREADABLE";

export interface RetroBlock {
  index: number;
  days: string[];
  start: string;
  end: string;
  test_rows: number;
  test_dates: number;
  test_groups: Record<string, number>;
  status: "VALID" | "DATA_SHORT";
  reason: string | null;
  test_start?: string;
  train_rows?: number;
  train_dates?: number;
  train_excluded_by_time?: number;
  baseline_pct?: number;
  model_mae_pp?: number;
  baseline_mae_pp?: number;
  unseen_categories?: Record<string, number>;
}

export interface RetroOverall {
  test_dates: number;
  model_mae_pp: number;
  baseline_mae_pp: number;
  difference_pp: number;
  verdict: "IMPROVED" | "NO_DIFFERENCE" | "WORSE";
  verdict_text: string;
}

export interface RetroMl {
  status: "COMPARED" | "DATA_SHORT";
  reason: string | null;
  blocks: RetroBlock[];
  overall: RetroOverall | null;
  eligible_rows: number;
  not_eligible: Record<string, number>;
}

export interface RetroCounts {
  denominators: {
    events: number;
    items: number;
    price_observations: number;
    price_slots: number;
    signal_dates: number;
    series_recorded: number; // 결과 행이 기록된 실제 가격 계열 수
  };
  status_by_horizon: Record<string, Record<string, number>>;
  delivery: {
    dispositions: Record<string, number>;
    delivered_items: number;
    partial_items: number;
    exposure: Record<string, number>;
  };
}

export interface RetroSlotMl {
  status: "ESTIMATED" | "NONE"; // NONE = 값 없음 + 사유(reason)
  reason: string | null;
  reason_text: string | null;
  block: number | null;
  actual_pct?: number;
  estimate_pct?: number;
  baseline_pct?: number;
  abs_error_pp?: number;
  baseline_abs_error_pp?: number;
}

export interface RetroSlot {
  series_id: string | null;
  horizon: number;
  status: string;
  status_text: string;
  eval_date: string | null;
  expected_eval_date: string | null;
  t0_price: number | null;
  t0_price_asof: string | null;
  eval_price: number | null;
  return_raw: number | null;
  max_up_raw: number | null;
  max_down_raw: number | null;
  path_points: number | null;
  partial_path: boolean;
  price_basis: string | null;
  computed_at: string | null;
  sign: "UP" | "DOWN" | "FLAT" | null;
  sign_text: string | null;
  ml: RetroSlotMl | null; // +5 칸에만
}

export interface RetroItem {
  event_id: string;
  item_seq: number;
  signal_date: string;
  push_kind: string;
  subject_kind: string;
  subject_id: string;
  disposition: string;
  delivered: boolean;
  partial: boolean;
  slots: RetroSlot[];
}

export interface RetroResult {
  schema: string;
  status: RetroStatus;
  status_text: string;
  end_date: string | null;
  run_id?: string;
  created_at?: string;
  snapshot_acquired_at?: string;
  price_asof_date?: string;
  copy_sync?: { last_success_at: string | null; last_failure_at: string | null };
  summary?: RetroCounts;
  exclusions?: Record<string, number>;
  ml?: RetroMl;
  feedback_summary?: { events_with_feedback: number; events_without_feedback: number };
  problems?: string[];
  // GET latest 만 — 지금 사본이 그 보고의 입력과 같은지(null = 확인 불가).
  input_changed?: boolean | null;
  input_check?: string;
  event?: {
    event_id: string;
    items: RetroItem[];
    feedback: { feedback_seq: number; helpfulness: string; feedback_at: string } | null;
  };
}

const RETRO = "/decision-ledger/retrospective-evaluation";
const RETRO_RUN_TIMEOUT_MS = 120_000; // 첫 실행은 학습 라이브러리를 불러온다 · 사본 전체 1회
const RETRO_READ_TIMEOUT_MS = 30_000; // 입력 변경 확인에 사본을 한 번 읽는다

export async function runRetrospective(): Promise<RetroResult> {
  return request<RetroResult>("POST", RETRO, {}, RETRO_RUN_TIMEOUT_MS);
}

export async function fetchRetrospectiveLatest(
  eventId?: string
): Promise<RetroResult> {
  const q = eventId ? `?${new URLSearchParams({ event_id: eventId })}` : "";
  return request<RetroResult>("GET", `${RETRO}/latest${q}`, undefined, RETRO_READ_TIMEOUT_MS);
}
