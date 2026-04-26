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
