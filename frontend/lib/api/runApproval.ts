// Run 생성 / 승인 / 거절 / 조회 + draft_payload 내부 sub-type 정의.
// Telegram 발송 결과 자체는 별도 응답 타입을 갖지 않고 Run.status 흐름으로 표현된다
// (DELIVERING / FAILED / COMPLETED).

import { request } from "./core";

export type RunStatus =
  | "PENDING_APPROVAL"
  | "REJECTED"
  | "DELIVERING"
  | "FAILED"
  | "COMPLETED";

export const TERMINAL_STATES: ReadonlyArray<RunStatus> = [
  "REJECTED",
  "FAILED",
  "COMPLETED",
];

// POC2 3-PUSH Message Contract (2026-06-12, FIX r2) — 하루 3종 PUSH 메시지 구분.
// "holdings_briefing" = 기존 /runs/generate-from-holdings (재정의).
// "market_briefing" = PUSH-1, 기존 /runs/generate + input_data.push_kind 분기.
// "spike_or_falling_alert" = PUSH-3, 기존 /runs/generate + input_data.push_kind 분기.
// 별도 PUSH endpoint 신설 0건 (§3 / §11 준수). 과거 run 은 null/undefined 가능.
export type PushKind =
  | "holdings_briefing"
  | "market_briefing"
  | "spike_or_falling_alert";

export interface Run {
  run_id: string;
  asof: string;
  status: RunStatus;
  draft_payload: Record<string, unknown> | null;
  // POC2 Step 2D: 백엔드가 generate 시점에 빌드한 전송 메시지 원본.
  // 프론트엔드는 opaque string 으로 받아 그대로 렌더링한다 (조립/파싱 금지).
  // 과거 run 또는 비-holdings 초안에는 null/undefined.
  message_text?: string | null;
  // POC2 3-PUSH Message Contract (2026-06-11).
  push_kind?: PushKind | null;
}

export function generateDraft(input_data: Record<string, unknown>): Promise<Run> {
  return request<Run>("POST", "/runs/generate", { input_data });
}

export function approveRun(run_id: string): Promise<Run> {
  return request<Run>("POST", `/runs/${encodeURIComponent(run_id)}/approve`);
}

export function rejectRun(run_id: string): Promise<Run> {
  return request<Run>("POST", `/runs/${encodeURIComponent(run_id)}/reject`);
}

export function fetchRun(run_id: string): Promise<Run> {
  return request<Run>("GET", `/runs/${encodeURIComponent(run_id)}`);
}

export function isTerminal(status: RunStatus): boolean {
  return TERMINAL_STATES.includes(status);
}

// POC2 3-PUSH Message Contract (2026-06-12, FIX r2 — 설계자 수용):
// 별도 PUSH endpoint 신설 금지선 준수. PUSH-1 / PUSH-3 은 기존 /runs/generate
// 의 input_data.push_kind 분기로 통합. PUSH-2 (holdings_briefing) 는
// holdings.ts 의 generateDraftFromHoldings 가 담당 (별도 holdings 데이터 의존).
//
// 본 함수들은 backend 가 message_text 까지 미리 빌드한 Run 을 반환한다.
// frontend 는 message_text 를 opaque 로 받아 그대로 표시 (조립 금지 — AC-2).
export function generateMarketBriefingDraft(): Promise<Run> {
  return request<Run>("POST", "/runs/generate", {
    input_data: { push_kind: "market_briefing" },
  });
}

export function generateSpikeAlertDraft(): Promise<Run> {
  return request<Run>("POST", "/runs/generate", {
    input_data: { push_kind: "spike_or_falling_alert" },
  });
}

// ─── POC2 Step 5B: momentum result (holdings mode) ──────────────────
//
// draft_payload.momentum_result 6번째 키. Step5B 한정 명시 승인.
// 과거 run 에는 누락될 수 있으므로 모든 접근에서 옵션 처리한다.
//
// placeholder 산식(pnl_rate) 결과 — 최종 투자 판단 산식이 아니다.
// 프론트엔드는 momentum_result 를 새로 조립/계산하지 않는다 — 백엔드가 만든 dict 를
// 그대로 표시만 한다. 전체 후보 순위는 메시지/기본 화면에 나열하지 않으며, 승인 초안
// 기본 영역에는 summary 의 1줄만 표시한다.
export interface MomentumScoreResult {
  is_scored: boolean;
  score_value?: number | null;
  score_unit?: string | null;
  score_basis_text?: string | null;
  ranking_basis?: string | null;
}

export interface MomentumCandidate {
  candidate_id: string;
  ticker: string;
  name: string;
  mode: "holdings" | "universe";
  is_available: boolean;
  score_result: MomentumScoreResult;
  reason_text: string | null;
  input_basis?: Record<string, unknown>;
  rank?: number;
  exclusion_reason?: string;
  source_index?: number;
  account_group?: string;
  avg_buy_price?: number;
}

export interface MomentumTopCandidate {
  candidate_id: string;
  ticker: string;
  name: string;
  source_index?: number;
  account_group?: string;
  avg_buy_price?: number;
  score_value: number;
  reason_text: string;
}

export interface MomentumSummary {
  total_candidates: number;
  scored_candidates: number;
  excluded_candidates: number;
  summary_reason_text: string;
  top_candidate?: MomentumTopCandidate;
}

export interface MomentumResult {
  engine_id: string;
  engine_version: string;
  mode: "holdings" | "universe";
  asof: string;
  summary: MomentumSummary;
  candidates: MomentumCandidate[];
}

// ─── POC2 Step 3: factor signals ─────────────────────────────────────
//
// draft_payload.factor_signals 5번째 키. Step3 한정 명시 승인.
// 과거 run 에는 누락될 수 있으므로 모든 접근에서 옵션 처리한다.
//
// 프론트엔드는 factor_signals 를 새로 조립/계산하지 않는다 — 백엔드가 만든 dict 를
// 그대로 표시만 한다. 종목별 signal 은 메시지에 나열하지 않으며, 승인 초안 기본
// 영역에는 portfolio scope reason_text(또는 fallback_text) 1줄만 표시한다.
export interface FactorSignal {
  factor_id: string;
  factor_name: string;
  // POC2 Step 6 Fix 라운드: scope="universe" 추가 — universe momentum 결과를 기존
  // factor_signals 안의 signal 1건으로 표현 (draft_payload 키 신설 0건).
  // POC2 Step 7C: scope="universe_falling" 추가 — 급락 ETF 주의 신호 (PUSH 3) 도
  // 동일 패턴으로 factor_signals 안의 signal 1건으로 표현.
  scope: "portfolio" | "holding_row" | "universe" | "universe_falling";
  is_available: boolean;
  value: number | null;
  unit: string;
  reason_text: string | null;
  fallback_text: string | null;
  input_basis?: Record<string, unknown>;
  computed_at?: string;
  // holding_row scope 전용 필드
  source_index?: number;
  ticker?: string;
  account_group?: string;
  avg_buy_price?: number;
}
