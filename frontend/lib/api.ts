// FastAPI(8000) 직접 호출 유틸.
// Next.js Route Handlers / rewrites 를 거치지 않는다 (설계 결정).
// NEXT_PUBLIC_API_BASE 누락 시 fail-loud. 암묵 fallback 금지 (DEV_RULES).

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

export interface Run {
  run_id: string;
  asof: string;
  status: RunStatus;
  draft_payload: Record<string, unknown> | null;
  // POC2 Step 2D: 백엔드가 generate 시점에 빌드한 전송 메시지 원본.
  // 프론트엔드는 opaque string 으로 받아 그대로 렌더링한다 (조립/파싱 금지).
  // 과거 run 또는 비-holdings 초안에는 null/undefined.
  message_text?: string | null;
}

export class ApiConfigError extends Error {}
export class ApiRequestError extends Error {
  readonly httpStatus: number;
  readonly body: unknown;
  constructor(message: string, httpStatus: number, body: unknown) {
    super(message);
    this.httpStatus = httpStatus;
    this.body = body;
  }
}

function apiBase(): string {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  if (!base) {
    throw new ApiConfigError(
      "NEXT_PUBLIC_API_BASE 가 설정되어 있지 않습니다. " +
        "frontend/.env.local 에 예: NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000"
    );
  }
  return base.replace(/\/$/, "");
}

const DEFAULT_TIMEOUT_MS = 10000;

async function request<T>(
  method: "GET" | "POST" | "PUT",
  path: string,
  body?: unknown,
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<T> {
  const url = `${apiBase()}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
      signal: controller.signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") {
      throw new ApiRequestError(
        `요청 시간 초과: ${method} ${path} (${timeoutMs}ms)`,
        0,
        null
      );
    }
    throw new ApiRequestError(
      `네트워크 호출 실패: ${method} ${path} — ${(e as Error).message}`,
      0,
      null
    );
  } finally {
    clearTimeout(timer);
  }
  let parsed: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }
  if (!response.ok) {
    throw new ApiRequestError(
      `요청 실패: ${method} ${path} (HTTP ${response.status})`,
      response.status,
      parsed
    );
  }
  return parsed as T;
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

// ─── POC2 Step 1: holdings ───────────────────────────────────────────

export interface HoldingItem {
  ticker: string;
  quantity: number;
  avg_buy_price: number;
  name?: string | null;
  // POC2 Step 2C: 표시/그룹용 라벨. 빈 값/누락은 백엔드에서 "일반" 으로 정규화.
  account_group?: string | null;
}

export interface HoldingsPayload {
  holdings: HoldingItem[];
}

export function fetchHoldings(): Promise<HoldingsPayload> {
  return request<HoldingsPayload>("GET", "/holdings");
}

export function saveHoldings(payload: HoldingsPayload): Promise<HoldingsPayload> {
  return request<HoldingsPayload>("PUT", "/holdings", payload);
}

export function generateDraftFromHoldings(): Promise<Run> {
  return request<Run>("POST", "/runs/generate-from-holdings");
}

// ─── POC2 Step 2: market data ────────────────────────────────────────

export interface MarketQuoteItem {
  ticker: string;
  name: string | null;
  current_price: number | null;
  price_asof: string | null;
  price_source: string | null;
}

export interface MarketRefreshResult {
  ok_count: number;
  fail_count: number;
  items: MarketQuoteItem[];
  failures: Array<{ ticker: string; reason: string }>;
}

export interface EnrichedHolding {
  ticker: string;
  name: string | null;
  quantity: number;
  avg_buy_price: number;
  invested_amount: number;
  current_price: number | null;
  price_asof: string | null;
  price_source: string | null;
  eval_amount: number | null;
  pnl_amount: number | null;
  pnl_rate_pct: number | null;
  buy_weight_pct: number | null;
  market_weight_pct: number | null;
  price_missing: boolean;
  calc_missing: boolean;
  // POC2 Step 2C: 표시/그룹용 라벨 + UI key 안정성을 위한 행 위치.
  account_group?: string;
  source_index?: number;
}

export interface EnrichedHoldingsResult {
  items: EnrichedHolding[];
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

// 명시적 사용자 액션에서만 호출 (page load / polling / 새로고침에서 호출 금지).
// holdings 시세 갱신 — 2026-05-18 namespace 정정 후 `/holdings/market/refresh`.
// 기존 `/market/refresh` 는 ETF universe 전체 갱신용 (postMarketRefresh) 으로 이동.
export function refreshMarket(): Promise<MarketRefreshResult> {
  // Naver 시세 조회는 종목당 최대 5초 + 직렬 호출이라 기본 timeout 보다 여유 필요.
  return request<MarketRefreshResult>(
    "POST",
    "/holdings/market/refresh",
    undefined,
    60000,
  );
}

export function fetchEnrichedHoldings(): Promise<EnrichedHoldingsResult> {
  return request<EnrichedHoldingsResult>("GET", "/holdings/enriched");
}

// ─── POC2 Step 6 + Fix 라운드: universe momentum refresh ───────────────
//
// 정책 (Fix 라운드 2026-05-11): 신규 endpoint 추가 금지 — GET /universe/momentum/latest
// 미도입. UI 의 마지막 갱신 표시는 POST refresh 응답을 frontend state 로 보관해서 처리
// (페이지 reload 시 안내 문구로 비워짐). POST 응답에 top_candidate / summary_reason_text
// 가 함께 포함되어 status panel 을 그릴 수 있다.

export interface UniversePriceHistoryBasis {
  base_date: string;
  base_close: number;
  latest_date: string;
  latest_close: number;
}

export interface UniverseTopCandidate {
  candidate_id?: string;
  ticker: string;
  name: string;
  rank?: number;
  score_result?: {
    is_scored: boolean;
    score_value?: number;
    score_unit?: string;
    score_basis_text?: string;
    ranking_basis?: string;
    exclusion_reason?: string;
  };
  reason_text?: string;
  price_history_basis?: UniversePriceHistoryBasis;
}

export interface UniverseRefreshSummary {
  total_candidates: number;
  scored_candidates: number;
  excluded_candidates: number;
  source_freshness: string;
  refresh_status: "ok" | "partial" | "failed";
  // Step6 Fix: UI 가 GET /latest 없이 POST 응답만으로 status panel 을 그리도록 확장.
  summary_reason_text?: string | null;
  top_candidate?: UniverseTopCandidate | null;
  // Step7A: seed source — "starter_seed" 면 UI 가 "기본 후보군 사용" 안내 표시.
  source?: string | null;
  // Step7C: 급락 ETF 주의 신호 (PUSH 3) — universe_mode 가 계산한 결과.
  // falling_candidate 가 null 이면 신호 없음.
  falling_candidate?: UniverseTopCandidate | null;
  falling_threshold_pct?: number | null;
}

export interface UniverseRefreshResponse {
  status: "ok" | "partial" | "failed";
  artifact_path: string;
  momentum_result: {
    mode: string;
    asof: string;
    summary: UniverseRefreshSummary;
  };
}

// 명시적 사용자 액션에서만 호출 — Telegram / Approve / GenerateDraft 자동 발동 금지.
export function refreshUniverseMomentum(): Promise<UniverseRefreshResponse> {
  // pykrx ticker 별 0.5s delay × 최대 20개 + 30s budget — 60s timeout 으로 여유.
  return request<UniverseRefreshResponse>(
    "POST",
    "/universe/momentum/refresh",
    undefined,
    60000,
  );
}

// ─── PC Market Discovery — SQLite 직접 계산 + refresh background job ─
// 2026-05-18 변경: 시장 데이터 SSOT = SQLite. JSON artifact 폐기.
// GET  /market/topn/latest    — SQLite 에서 직접 TOP N 계산 (read-only).
// POST /market/refresh        — FDR 수집을 background job 으로 트리거 (ETF universe + 가격).
// GET  /market/refresh/status — 현재/마지막 refresh 상태.
// (holdings naver 시세 갱신은 별도 endpoint `POST /holdings/market/refresh`.)

export type MarketTopNStatus = "ok" | "missing" | "empty" | "invalid";

// 결측 필드는 백엔드가 그대로 null 로 통과시킨다 (지시문 §6 "0% 보정 금지").
// frontend 도 모든 필드를 nullable 로 받아 "-" 표시한다.
//
// 2026-05-18 후보 정제 1차 — tags: ETF 이름 기반 상품 태그 배열.
// 가능 값: "inverse" | "leveraged" | "synthetic" | "futures"
// 일반 후보는 빈 배열.
export type MarketProductTag = "inverse" | "leveraged" | "synthetic" | "futures";

// 2026-05-18 통합 후보 테이블 1차 — 조회 기준 basis.
// 2026-05-19 Grid 사용성 FIX — 이전 표현 (일간 급등 / 1개월 모멘텀 / 3개월 추세) 라벨 상수
// MARKET_BASIS_LABEL 제거. 컬럼 라벨은 MARKET_BASIS_COLUMN_LABEL 만 사용 (검증자 B-6 NOTE 반영).
export type MarketBasis = "daily" | "one_month" | "three_month";

export const DEFAULT_MARKET_BASIS: MarketBasis = "one_month";

// 2026-05-19 Grid 사용성 FIX — 정렬 방향.
export type MarketOrder = "desc" | "asc";
export const DEFAULT_MARKET_ORDER: MarketOrder = "desc";

// 컬럼 헤더 라벨 (Grid 사용성 FIX § 4.2 — 통일된 표현).
export const MARKET_BASIS_COLUMN_LABEL: Record<MarketBasis, string> = {
  daily: "일간 수익률",
  one_month: "1개월 수익률",
  three_month: "3개월 수익률",
};

export interface MarketPeriodReturn {
  return_pct?: number | null;
  basis_start_date?: string | null;
  basis_end_date?: string | null;
}

export interface MarketReturns {
  daily?: MarketPeriodReturn | null;
  one_month?: MarketPeriodReturn | null;
  three_month?: MarketPeriodReturn | null;
}

export interface MarketCandidateExcessReturn {
  vs_kodex200_1m_pctp?: number | null;
  vs_kodex200_3m_pctp?: number | null;
  vs_kospi_1m_pctp?: number | null;
  vs_kospi_3m_pctp?: number | null;
}

export interface MarketCandidate {
  rank?: number | null;
  ticker?: string | null;
  name?: string | null;
  tags?: MarketProductTag[];
  selected_return_pct?: number | null;
  selected_basis_start_date?: string | null;
  selected_basis_end_date?: string | null;
  returns?: MarketReturns;
  // 2026-05-22 — Market Regime & Benchmark Context 1차.
  excess_return?: MarketCandidateExcessReturn | null;
}

// ─── Market Regime & Benchmark Context (2026-05-22) ─────────────────

export type MarketRegimeCode = "bull" | "neutral" | "bear" | "unavailable";
export type MarketContextStatus = "ok" | "partial" | "unavailable";

export interface MarketContextKodex200 {
  status: "ok" | "unavailable";
  return_20d_pct?: number | null;
  return_60d_pct?: number | null;
  return_1m_pct?: number | null;
  return_3m_pct?: number | null;
  close?: number | null;
  ma20?: number | null;
  ma60?: number | null;
  ma20_position?: "above" | "below" | null;
  ma60_position?: "above" | "below" | null;
}

export interface MarketContextKospi {
  status: "ok" | "unavailable";
  return_20d_pct?: number | null;
  return_60d_pct?: number | null;
  return_1m_pct?: number | null;
  return_3m_pct?: number | null;
}

export interface MarketContext {
  status: MarketContextStatus;
  asof?: string | null;
  primary_benchmark: string;
  regime_label: string;
  regime_code: MarketRegimeCode;
  regime_score?: number | null;
  regime_reasons: string[];
  kodex200: MarketContextKodex200;
  kospi: MarketContextKospi;
  warnings: string[];
}

export interface MarketTopNEntry {
  rank?: number | null;
  ticker?: string | null;
  name?: string | null;
  return_pct?: number | null;
  basis_start_date?: string | null;
  basis_end_date?: string | null;
  tags?: MarketProductTag[];
}

export interface MarketTopNFilters {
  exclude_inverse: boolean;
  exclude_leveraged: boolean;
  exclude_synthetic: boolean;
  exclude_futures: boolean;
}

export interface MarketTopNFilterOptions {
  excludeInverse?: boolean;
  excludeLeveraged?: boolean;
  excludeSynthetic?: boolean;
  excludeFutures?: boolean;
}

export const DEFAULT_MARKET_TOPN_FILTERS: MarketTopNFilters = {
  exclude_inverse: true,
  exclude_leveraged: true,
  exclude_synthetic: true,
  exclude_futures: true,
};

export interface MarketLatestRefresh {
  refresh_id?: string | null;
  source?: string | null;
  asof?: string | null;
  attempted_count?: number | null;
  success_count?: number | null;
  fail_count?: number | null;
  runtime_seconds?: number | null;
  error_summary?: string | null;
  created_at?: string | null;
}

export interface MarketTopNResponse {
  status: MarketTopNStatus;
  error?: string | null;
  asof?: string | null;
  source?: string | null;
  n?: number | null;
  // 2026-05-18 통합 후보 테이블 1차 — 현재 조회 기준.
  basis?: MarketBasis | null;
  // 2026-05-19 Grid 사용성 FIX — 현재 정렬 방향.
  order?: MarketOrder | null;
  universe_count?: number | null;
  price_success_count?: number | null;
  price_fail_count?: number | null;
  latest_refresh?: MarketLatestRefresh | null;
  runtime_seconds?: number | null;
  // 통합 후보 테이블 (frontend 기본 렌더 소스).
  candidates: MarketCandidate[];
  // 호환용 — 기존 분리 테이블도 응답에 유지 (frontend 사용 안 함).
  daily_topn: MarketTopNEntry[];
  one_month_topn: MarketTopNEntry[];
  three_month_topn: MarketTopNEntry[];
  period_exclusions?: Record<string, Record<string, number>>;
  filters?: MarketTopNFilters;
  filter_exclusions?: Record<string, Record<string, number>>;
  candidate_filter_exclusions?: Record<string, number>;
  topn_caveat?: string | null;
  // 2026-05-22 — Market Regime & Benchmark Context. status=missing/empty/invalid
  // 에서는 null.
  market_context?: MarketContext | null;
}

export interface MarketTopNRequestOptions extends MarketTopNFilterOptions {
  basis?: MarketBasis;
  order?: MarketOrder;
}

export function fetchMarketTopnLatest(
  n: number = 10,
  options: MarketTopNRequestOptions = {},
): Promise<MarketTopNResponse> {
  const params = new URLSearchParams({ n: String(n) });
  params.set("basis", options.basis ?? DEFAULT_MARKET_BASIS);
  params.set("order", options.order ?? DEFAULT_MARKET_ORDER);
  params.set(
    "exclude_inverse",
    String(options.excludeInverse ?? DEFAULT_MARKET_TOPN_FILTERS.exclude_inverse),
  );
  params.set(
    "exclude_leveraged",
    String(options.excludeLeveraged ?? DEFAULT_MARKET_TOPN_FILTERS.exclude_leveraged),
  );
  params.set(
    "exclude_synthetic",
    String(options.excludeSynthetic ?? DEFAULT_MARKET_TOPN_FILTERS.exclude_synthetic),
  );
  params.set(
    "exclude_futures",
    String(options.excludeFutures ?? DEFAULT_MARKET_TOPN_FILTERS.exclude_futures),
  );
  return request<MarketTopNResponse>(
    "GET",
    `/market/topn/latest?${params.toString()}`,
  );
}

export type MarketRefreshStartStatus =
  | "accepted"
  | "running"
  | "skipped_cooldown"
  | "failed_to_start";

export interface MarketRefreshStartResponse {
  status: MarketRefreshStartStatus;
  refresh_id?: string | null;
  message: string;
  cooldown_remaining_seconds: number;
}

export function postMarketRefresh(): Promise<MarketRefreshStartResponse> {
  // FDR 수집은 background — POST 자체는 즉시 응답이라 짧은 timeout.
  return request<MarketRefreshStartResponse>(
    "POST",
    "/market/refresh",
    undefined,
    15000,
  );
}

export type MarketRefreshStatus =
  | "idle"
  | "running"
  | "completed"
  | "failed"
  | "skipped_cooldown";

export interface MarketRefreshStatusResponse {
  status: MarketRefreshStatus;
  refresh_id?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  asof?: string | null;
  universe_count?: number | null;
  price_attempted_count?: number | null;
  price_success_count?: number | null;
  price_fail_count?: number | null;
  runtime_seconds?: number | null;
  error_summary?: string | null;
  cooldown_remaining_seconds: number;
}

export function fetchMarketRefreshStatus(): Promise<MarketRefreshStatusResponse> {
  return request<MarketRefreshStatusResponse>("GET", "/market/refresh/status");
}

// ─── POC2 — AI 투자세션 기록 / Decision Evidence 1차 ─────────────
// state/decision/decision_evidence.sqlite (시장 데이터 SQLite 와 분리).
// 본 그룹은 매매 자동화 / Telegram / OCI PUSH / AI API 호출과 무관 — 사용자가
// 외부 AI 채널 (GPT / Gemini / Claude) 에서 받은 텍스트를 저장·조회만 한다.

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

// ─── POC2 ETF Constituents & Overlap 1차 (2026-05-27) ──────────────
// state/market/market_data.sqlite 의 etf_constituents / refresh_log 테이블 +
// pykrx PDF fetcher (실패 시 unavailable). K6 방어 — 1회 최대 10개 ticker.

export interface RefreshConstituentsRequest {
  asof: string;
  tickers: string[];
  top_k?: number;
  force?: boolean;
}

export interface RefreshConstituentsItem {
  ticker: string;
  status: "ok" | "unavailable" | "skipped_timeout";
  source?: string | null;
  constituent_count: number;
  from_cache: boolean;
  message?: string | null;
}

export interface RefreshConstituentsResponse {
  status: "ok" | "partial" | "rejected";
  reason?: string | null;
  message?: string | null;
  asof?: string | null;
  requested_count: number;
  success_count: number;
  fail_count: number;
  cached_count: number;
  fetched_count: number;
  skipped_count: number;
  source?: string | null;
  items: RefreshConstituentsItem[];
}

export function refreshConstituents(
  req: RefreshConstituentsRequest,
): Promise<RefreshConstituentsResponse> {
  // pykrx 호출은 분당 가량이 걸릴 수 있어 timeout 여유.
  return request<RefreshConstituentsResponse>(
    "POST",
    "/market/constituents/refresh",
    req,
    60000,
  );
}

export interface TopHolding {
  rank: number;
  ticker?: string | null;
  name?: string | null;
  weight_pct?: number | null;
}

export interface Concentration {
  top1_weight_pct?: number | null;
  top3_weight_pct?: number | null;
  top5_weight_pct?: number | null;
  top10_weight_pct?: number | null;
}

export interface ConstituentItem {
  etf_ticker: string;
  etf_name?: string | null;
  status: "ok" | "unavailable";
  source?: string | null;
  asof: string;
  top_holdings: TopHolding[];
  concentration: Concentration;
}

export interface OverlapCommonHolding {
  ticker?: string | null;
  name?: string | null;
  left_weight_pct?: number | null;
  right_weight_pct?: number | null;
}

export interface OverlapPair {
  left_ticker: string;
  right_ticker: string;
  common_count_top10: number;
  weighted_overlap_pct?: number | null;
  common_holdings: OverlapCommonHolding[];
}

export interface RepeatedCoreItem {
  etf_ticker: string;
  weight_pct?: number | null;
}

export interface RepeatedCoreHolding {
  ticker?: string | null;
  name?: string | null;
  appears_in_etf_count: number;
  items: RepeatedCoreItem[];
}

export interface ConstituentsAnalysisResponse {
  status: "ok";
  asof: string;
  top_k: number;
  coverage: {
    requested_count: number;
    available_count: number;
    unavailable_count: number;
  };
  constituents: ConstituentItem[];
  overlap_matrix: OverlapPair[];
  repeated_core_holdings: RepeatedCoreHolding[];
}

export function fetchConstituentsAnalysis(
  tickers: string[],
  asof: string,
  top_k: number = 10,
): Promise<ConstituentsAnalysisResponse> {
  const params = new URLSearchParams({
    tickers: tickers.join(","),
    asof,
    top_k: String(top_k),
  });
  return request<ConstituentsAnalysisResponse>(
    "GET",
    `/market/constituents/analysis?${params.toString()}`,
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
