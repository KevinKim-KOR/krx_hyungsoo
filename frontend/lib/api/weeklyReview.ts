// POC6-32 V2 — 「주간 ETF 점검」(`GET /weekly/etf-check` · 읽기 전용 · 외부 호출 0).
// 한 응답 = 한 검토 건(판정 §3-1): 화면 · [AI용 주간 검토 복사] · [AI 투자 세션으로 넘기기]가 이 응답 하나를 같이 쓴다.
// 글(흐름 설명 · 고른 후보 검토 줄 · 겹침 줄 · 복사 글 · 대조 결과)은 서버가 만든다(`app/weekly_review*.py` ·
// `app/weekly_candidate_review.py`) — 화면은 그대로 보인다. ① 시장 한 줄은 응답의 공통 시장 근거 칸(`market_evidence` ·
// 일일 복사와 같은 칸)을 화면이 그린다(`lib/weeklyReview.ts` weeklyMarketView · PLAN V2 S3 · 목업 ①).
// 기록 하나의 AI 답 해석 = `GET /weekly/etf-check/records/{id}/review`(「AI 투자 세션」 '당시 검토' · AC3 · 저장 원문만).

import { request } from "./core";
import type { DecisionCandidateSnapshot, DecisionFilters, DecisionUserVerdict } from "./decisionSessions";
import type { MarketCommonEvidence } from "./marketCommonEvidence";

export const WEEKLY_REVIEW_KEY_PREFIX = "today:weekly-review?";
// AI 세션 기록의 출처 값(글자 칸 · 표 변경 없음 · 판정 Q7 · Q8)
export const WEEKLY_REVIEW_SOURCE = "today_weekly_review";

// 기간 상태 — ok = 공통 기간 · period_differs = 시작일이 공통 기간과 다름(값은 남김 · V2 W5) · missing = 값 없음.
export type WeeklyPeriodStatus = "ok" | "period_differs" | "missing";

export interface WeeklyPeriod {
  status: WeeklyPeriodStatus;
  start: string | null;
  end: string | null;
}

export interface WeeklyMember {
  rank: number;
  ticker: string;
  name: string;
  held: boolean;
  index_name: string | null;
  // 값 = 공통 기간(ok) 또는 기간 다름(period_differs)일 때 · 값 없음만 null
  one_month: number | null;
  three_month: number | null;
  periods: { one_month: WeeklyPeriod; three_month: WeeklyPeriod };
  // 끝일 가격 저장 상태(장중 · 마감 뒤 · 모름)
  end_price: { date: string | null; state: "intraday" | "after_close" | "unknown" };
  // 자료 부족 사유(가격 · 상품 · 충분하면 빈 목록 · 서버 한국어 글)
  lack: string[];
}

export interface WeeklyFlow {
  key: string;
  kind: "single" | "group";
  title: string;
  index_name: string | null;
  members: WeeklyMember[];
  rep: string;
  rep_rank: number;
  note: string;
  // 묶음만 — 구성원의 공식 기초지수명이 서로 다름(계열 사전으로 묶임 · 화면 · 복사 글이 상품마다 공식 지수명을 보임 · I-29)
  index_names_differ?: boolean;
  // 구성원 사유를 겹치지 않게 모음
  lack: string[];
}

// 공통 시장 근거(서버 `weekly_review.common_snapshot` — `GET /market/evidence` 와 같은 칸 · 일일 글 제외).
// 못 읽었으면 status = 'unavailable' · message(사유)만 온다.
export type WeeklyMarketEvidence = Pick<MarketCommonEvidence, "status" | "message"> &
  Partial<Omit<MarketCommonEvidence, "status" | "message" | "daily_text">>;

export interface WeeklyOverlap {
  ticker: string;
  name: string;
  rank: number;
  state: string | null;
  warn_lines: string[];
  lines: string[];
  date_line: string | null;
  numbers: { min: string | null; max: string | null; stocks: number; no_value: number; full_confirmed: string } | null;
}

// ── ③ 「선택한 후보 검토」(`selected_review` · 고른 후보가 목록에 있을 때만) ─────────────────────
export interface WeeklyProduct {
  ticker: string;
  found: boolean;
  kind: "etf" | "stock" | "unknown";
  name: string | null;
  // 공식 기준정보 CSV 글자 그대로(예: 총보수 '0.450000')
  index_name: string | null;
  index_provider: string | null;
  market: string | null;
  asset: string | null;
  multiple: string | null;
  replication: string | null;
  fee_pct: string | null;
  tax: string | null;
  listed: string | null;
  // 찾았으면 null · 아니면 '공식 기준정보에 없음' 등 서버 한국어 사유
  missing_reason: string | null;
  csv: { name: string | null; asof: string | null; ok: boolean; error: string | null };
}

export interface WeeklyConstituents {
  state: "not_collected" | "source_unconfirmed" | "top_rows" | "full" | "error";
  state_label: string;
  asof: string | null;
  stored_rows: number;
  stocks_known: boolean;
  stock_rows: number | null;
  other_rows: { label: string; count: number }[];
  top_n: number | null;
  // 주식 상위(최대 3개) · 합 = 소수 둘째 자리(비중을 못 읽은 행이 있으면 null)
  top_stocks: { name: string | null; weight_pct: number | null }[];
  top3_sum_pct: number | null;
  line: string;
}

export interface WeeklyReturn {
  period: "1m" | "3m";
  label: string;
  value_pct: number | null;
  start: string | null;
  end: string | null;
  status: WeeklyPeriodStatus;
  direction: "up" | "down" | "flat" | null;
  common: { start: string | null; end: string | null } | null;
  // 같은 기간 국내시장(KODEX 200) 대비 — 비교할 수 있을 때만 값(comparable) · 둘 다 장중이면 잠정(provisional)
  market: { value_pct: number | null; diff_pp: number | null; comparable: boolean; provisional: boolean; reason: string | null };
  phrase: string;
}

export interface WeeklySelectedReview {
  ticker: string;
  name: string;
  rank: number;
  side: "top";
  product: WeeklyProduct;
  constituents: WeeklyConstituents;
  returns: WeeklyReturn[];
  price_note: string;
  checks: string[];
  overlap: WeeklyOverlap | null;
  overlap_note: string;
}

// ── ④ AI 의견 요약(마지막 기록의 답 해석 · 서버 규칙) ─────────────────────────────────────────
export type WeeklyAi = "gpt" | "gemini" | "claude";
export type WeeklyLatestState = "같음" | "새 값 있음" | "확인 불가" | "형식 없음";

export interface WeeklyLatest {
  state: WeeklyLatestState;
  raw: string | null;
  reason: string | null;
}

// AI 가 적은 확인 항목 한 줄(원문 + 이름 붙은 칸 · 확인 시각이 비면 checked_at = null · checked_at_text = '확인 시각 미기재')
export interface WeeklyCheckedItem {
  line: string;
  item: string;
  value: string | null;
  basis_date: string | null;
  source: string | null;
  checked_at: string | null;
  changes: string | null;
  checked_at_text: string;
}

export type WeeklyAnswerView = { status: "no_answer" } | { status: "ok"; latest: WeeklyLatest; items: WeeklyCheckedItem[] };

export interface WeeklyCell {
  status: "ok" | "needs_check" | "no_answer";
  reason?: string;
  state?: string;
  cited?: number[];
  why?: string | null;
  next_check?: string | null;
}

export interface WeeklyCompareRow {
  ticker: string;
  name: string | null;
  cells: Record<WeeklyAi, WeeklyCell>;
  ok_count: number;
  state_same: boolean | null;
  cited_same: boolean | null;
  // 확인된 답이 2개 이상일 때만 — 모두 같은 번호 · 답마다 다른 번호
  cited_common?: number[] | null;
  cited_only?: Partial<Record<WeeklyAi, number[]>> | null;
  state_text: string;
  cited_text: string | null;
}

export interface WeeklyCompareResult {
  status: "ok" | "no_format";
  message: string | null;
  rows: WeeklyCompareRow[];
  answers?: Record<WeeklyAi, WeeklyAnswerView>;
  answer_count?: number;
  // 'AI 답 없음' | '한 의견' | 'AI 답 n개'
  opinion_text?: string;
  // 예: 'GPT 같음 · Claude 새 값 있음' · 답이 없으면 null
  latest_text?: string | null;
}

export interface WeeklyLastRecord {
  status: "none" | "ok" | "error";
  message: string | null;
  id?: string;
  saved_at?: string;
  asof?: string;
  verdict?: DecisionUserVerdict;
  memo?: string | null;
  next_checks?: string[];
  candidate_count?: number;
  // 저장한 고른 후보(ok = 코드 · 이름 · none = 고르지 않고 넘김 · unknown = 그 칸이 없는 기록 · 검토 F4 · 목업 ⑤)
  selected?: { status: "ok"; ticker: string; name: string | null } | { status: "none" } | { status: "unknown" };
  // 빈 답을 뺀 AI 답 수
  answer_count?: number;
  compare?: WeeklyCompareResult;
}

// 넘기기 · 저장 묶음(기존 자유 칸 · 표 변경 없음 · PLAN V2 §4-3 · §9 I-13)
export interface WeeklyDataQuality {
  condition: Record<string, unknown>;
  // returns = ③ R2 결과 그대로(국내시장 대비 · 잠정 · 사유 · 문구 · '당시 검토'가 같은 대비를 보임 · I-32)
  selected: {
    ticker: string;
    name: string;
    rank: number;
    side: "top";
    returns?: Omit<WeeklyReturn, "label" | "common">[];
  } | null;
  common_periods: {
    one_month: { start: string | null; end: string | null } | null;
    three_month: { start: string | null; end: string | null } | null;
  };
  period_differs_values: unknown[];
  lack: { ticker: string; rank: number; lack: string[] }[];
  // 30행(티커별) · KODEX 200 끝 가격 날짜 · 상태(I-32 — '당시 검토'가 저장된 상태로 I-8 적용)
  price_states?: {
    rows: Record<string, { date: string | null; state: string }>;
    kodex200: { date: string | null; state: string };
  };
  evidence_list: WeeklyEvidence[];
}

export interface WeeklyEvidence {
  no: number;
  group: "market" | "list" | "flow" | "rest" | "selected" | "overlap";
  key?: string;
  text: string;
  tickers: string[];
}

export interface WeeklyReviewOk {
  status: "ok";
  message: null;
  source_screen: string;
  generated_at: string;
  condition: { basis: "one_month"; side: "top"; n: number; filters: DecisionFilters; start: string; end: string; line: string };
  end_date: string;
  flows: WeeklyFlow[];
  first_rows: number;
  selected: { ticker: string; name: string; rank: number } | null;
  selected_missing: boolean;
  selected_review: WeeklySelectedReview | null;
  overlap: WeeklyOverlap | null;
  evidence: WeeklyEvidence[];
  answer_targets: { ticker: string; evidence: number[] }[];
  copy_text: string;
  // 공통 시장 근거(일일 복사와 같은 칸 · 일일 글 제외) — 화면 ① · 복사 글의 시장 [근거 n] · 저장 시장 칸이 같은 칸
  market_evidence: WeeklyMarketEvidence;
  candidate_snapshot: DecisionCandidateSnapshot[];
  market_context_snapshot: Record<string, unknown>;
  data_quality_snapshot: WeeklyDataQuality;
  // 고른 후보의 상품 · 구성 요약(고른 후보가 없으면 빈 객체)
  constituent_snapshot: Record<string, unknown>;
  last_record: WeeklyLastRecord;
}

export interface WeeklyReviewNotOk {
  status: "missing" | "empty" | "invalid" | "no_common_period";
  message: string;
  source_screen: string;
  generated_at: string;
  last_record: WeeklyLastRecord;
}

export type WeeklyReviewResponse = WeeklyReviewOk | WeeklyReviewNotOk;

export function weeklyReviewKey(selected: string | null): string {
  return WEEKLY_REVIEW_KEY_PREFIX + (selected ? `selected=${encodeURIComponent(selected)}` : "");
}

export function fetchWeeklyReview(selected: string | null): Promise<WeeklyReviewResponse> {
  const qs = selected ? `?selected=${encodeURIComponent(selected)}` : "";
  return request<WeeklyReviewResponse>("GET", `/weekly/etf-check${qs}`);
}

// 저장한 주간 기록 하나의 AI 답 해석(④ · ⑤ 최근 검토 기록과 같은 모양 · 저장 원문을 지금 해석기로 나눔 · PLAN I-14).
// 없거나 주간 기록이 아니면 404(서버 한국어 detail) · 읽기 실패는 503.
export function fetchWeeklyRecordReview(id: string): Promise<WeeklyLastRecord> {
  return request<WeeklyLastRecord>("GET", `/weekly/etf-check/records/${encodeURIComponent(id)}/review`);
}
