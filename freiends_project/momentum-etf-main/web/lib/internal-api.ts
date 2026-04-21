type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

function getFastApiBaseUrl(): string {
  const value = String(process.env.FASTAPI_INTERNAL_URL ?? "").trim();
  if (!value) {
    throw new Error("FASTAPI_INTERNAL_URL 환경변수가 필요합니다.");
  }
  return value.replace(/\/+$/, "");
}

function getFastApiToken(): string {
  const value = String(process.env.FASTAPI_INTERNAL_TOKEN ?? "").trim();
  if (!value) {
    throw new Error("FASTAPI_INTERNAL_TOKEN 환경변수가 필요합니다.");
  }
  return value;
}

const DEFAULT_TIMEOUT_MS = 30_000;

export async function fetchFastApiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  headers.set("X-Internal-Token", getFastApiToken());

  const controller = new AbortController();
  if (init?.signal) {
    init.signal.addEventListener("abort", () => controller.abort(init.signal!.reason));
  }
  const timeoutId = setTimeout(() => controller.abort("timeout"), DEFAULT_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${getFastApiBaseUrl()}${path}`, {
      ...init,
      headers,
      signal: controller.signal,
      cache: "no-store",
    });
  } catch (error) {
    clearTimeout(timeoutId);
    const isAbort =
      (error instanceof DOMException && error.name === "AbortError") ||
      (error instanceof Error && error.name === "AbortError") ||
      (error instanceof Error && error.message.includes("fetch failed") && String((error as any).cause).includes("AbortError"));

    if (isAbort) {
      try {
        await fetch(`${getFastApiBaseUrl()}/internal/health/report_error`, {
          method: "POST",
          headers: { "X-Internal-Token": getFastApiToken() },
        }).catch(() => { });
      } catch (e) { }
      throw new Error(`FastAPI 요청이 ${DEFAULT_TIMEOUT_MS / 1_000}초 내에 응답하지 않았습니다. (${path})`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }

  const payload = (await response.json().catch(() => ({}))) as { detail?: string; error?: string } & JsonValue;
  if (!response.ok) {
    const message =
      (typeof payload === "object" && payload && "detail" in payload && typeof payload.detail === "string"
        ? payload.detail
        : null) ||
      (typeof payload === "object" && payload && "error" in payload && typeof payload.error === "string"
        ? payload.error
        : null) ||
      `FastAPI 요청에 실패했습니다. (${response.status})`;

    if (message.includes("NetworkTimeout") || message.includes("timed out") || message.includes("시간 초과") || message.includes("응답하지 않았습니다")) {
      try {
        await fetch(`${getFastApiBaseUrl()}/internal/health/report_error`, {
          method: "POST",
          headers: { "X-Internal-Token": getFastApiToken() },
        }).catch(() => { });
      } catch (e) { }
    }
    throw new Error(message);
  }

  return payload as T;
}
