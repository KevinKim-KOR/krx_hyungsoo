// FastAPI(8000) 직접 호출 공통 인프라.
// Next.js Route Handlers / rewrites 를 거치지 않는다 (설계 결정).
// NEXT_PUBLIC_API_BASE 누락 시 fail-loud. 암묵 fallback 금지 (DEV_RULES).

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

export async function request<T>(
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
