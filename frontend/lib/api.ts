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
  scope: "portfolio" | "holding_row";
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
export function refreshMarket(): Promise<MarketRefreshResult> {
  // Naver 시세 조회는 종목당 최대 5초 + 직렬 호출이라 기본 timeout 보다 여유 필요.
  return request<MarketRefreshResult>("POST", "/market/refresh", undefined, 60000);
}

export function fetchEnrichedHoldings(): Promise<EnrichedHoldingsResult> {
  return request<EnrichedHoldingsResult>("GET", "/holdings/enriched");
}
