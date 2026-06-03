// POC2 — AI 투자세션 기록 / Decision Evidence 1차.
//
// state/decision/decision_evidence.sqlite (시장 데이터 SQLite 와 분리).
// 본 그룹은 매매 자동화 / Telegram / OCI PUSH / AI API 호출과 무관 — 사용자가
// 외부 AI 채널 (GPT / Gemini / Claude) 에서 받은 텍스트를 저장·조회만 한다.
//
// 자동 AI 토론 / 투자 판단 자동화는 본 모듈의 책임이 아니다.

import { request } from "./core";
import type { MarketCandidate } from "./market";

export type DecisionUserVerdict =
  | "useful"
  | "needs_constituents"
  | "needs_market_compare"
  | "hold";

export const DECISION_VERDICT_LABEL: Record<DecisionUserVerdict, string> = {
  useful: "쓸 만함",
  needs_constituents: "구성 종목 필요",
  needs_market_compare: "시장 비교 필요",
  hold: "보류",
};

export const DEFAULT_DECISION_VERDICT: DecisionUserVerdict = "hold";

export interface DecisionFilters {
  exclude_inverse: boolean;
  exclude_leveraged: boolean;
  exclude_synthetic: boolean;
  exclude_futures: boolean;
}

export interface DecisionCandidateSnapshot {
  rank?: number | null;
  ticker?: string | null;
  name?: string | null;
  daily_return_pct?: number | null;
  one_month_return_pct?: number | null;
  three_month_return_pct?: number | null;
  tags: string[];
}

export interface CreateDecisionSessionRequest {
  asof: string;
  source_screen: string;
  filters: DecisionFilters;
  candidate_snapshot: DecisionCandidateSnapshot[];
  question_text: string;
  // 2026-05-21 — 단일 answer_text → 3 채널 분리 (GPT / Gemini / Claude).
  // 백엔드는 3개 중 **최소 1개 이상** 비어있지 않아야 함을 422 로 검증한다.
  gpt_answer_text: string;
  gemini_answer_text: string;
  claude_answer_text: string;
  user_memo: string;
  user_verdict: DecisionUserVerdict;
  next_checks: string[];
  linked_market_refresh_id?: string | null;
  // 2026-05-22 — 저장 시점 시장 문맥 (free schema dict). null/빈 dict 모두 허용.
  market_context_snapshot?: Record<string, unknown> | null;
  // 2026-05-27 — 저장 시점 구성종목 / 중복률 스냅샷.
  constituent_snapshot?: Record<string, unknown> | null;
  overlap_snapshot?: Record<string, unknown> | null;
  // 2026-06-01 — Market Discovery Evidence Closeout 1차.
  short_term_momentum_snapshot?: Record<string, unknown> | null;
  data_quality_snapshot?: Record<string, unknown> | null;
}

export interface CreateDecisionSessionResponse {
  status: "ok";
  id: string;
  created_at: string;
}

export interface DecisionSessionSummary {
  id: string;
  created_at: string;
  asof: string;
  source_screen: string;
  user_verdict: DecisionUserVerdict;
  summary: string;
  candidate_count: number;
  // 2026-05-21 — 목록에서 채널별 답변 입력 여부 표시 (지시문 §10.2).
  has_gpt_answer: boolean;
  has_gemini_answer: boolean;
  has_claude_answer: boolean;
}

export interface ListDecisionSessionsResponse {
  status: "ok";
  records: DecisionSessionSummary[];
}

export interface DecisionSessionDetail {
  id: string;
  created_at: string;
  updated_at: string;
  asof: string;
  source_screen: string;
  filters: DecisionFilters;
  candidate_snapshot: DecisionCandidateSnapshot[];
  question_text: string;
  gpt_answer_text: string;
  gemini_answer_text: string;
  claude_answer_text: string;
  user_memo: string;
  user_verdict: DecisionUserVerdict;
  next_checks: string[];
  linked_market_refresh_id?: string | null;
  // 2026-05-22 — 저장 시점 시장 문맥 (free schema dict). 백엔드가 항상 dict (없으면 {}) 로 반환.
  market_context_snapshot: Record<string, unknown>;
  // 2026-05-27 — 저장 시점 구성종목 / 중복률 (free schema dict, 없으면 {}).
  constituent_snapshot: Record<string, unknown>;
  overlap_snapshot: Record<string, unknown>;
  // 2026-06-01 — Market Discovery Evidence Closeout 1차.
  short_term_momentum_snapshot: Record<string, unknown>;
  data_quality_snapshot: Record<string, unknown>;
}

export interface GetDecisionSessionResponse {
  status: "ok" | "not_found";
  record?: DecisionSessionDetail | null;
  message?: string | null;
}

export function createDecisionSession(
  req: CreateDecisionSessionRequest,
): Promise<CreateDecisionSessionResponse> {
  return request<CreateDecisionSessionResponse>(
    "POST",
    "/decision/sessions",
    req,
  );
}

export function fetchDecisionSessions(
  limit: number = 10,
): Promise<ListDecisionSessionsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  return request<ListDecisionSessionsResponse>(
    "GET",
    `/decision/sessions?${params.toString()}`,
  );
}

export function fetchDecisionSession(
  id: string,
): Promise<GetDecisionSessionResponse> {
  return request<GetDecisionSessionResponse>(
    "GET",
    `/decision/sessions/${encodeURIComponent(id)}`,
  );
}

// MarketCandidate (응답 형태) → DecisionCandidateSnapshot (저장 형태) 변환.
// 저장 시점 후보를 그대로 보존 — Market Discovery 응답 구조가 바뀌어도 과거
// 기록은 불변이어야 한다 (지시문 §4 / §7.1).
export function toDecisionCandidateSnapshot(
  c: MarketCandidate,
): DecisionCandidateSnapshot {
  return {
    rank: c.rank ?? null,
    ticker: c.ticker ?? null,
    name: c.name ?? null,
    daily_return_pct: c.returns?.daily?.return_pct ?? null,
    one_month_return_pct: c.returns?.one_month?.return_pct ?? null,
    three_month_return_pct: c.returns?.three_month?.return_pct ?? null,
    tags: (c.tags ?? []) as string[],
  };
}
