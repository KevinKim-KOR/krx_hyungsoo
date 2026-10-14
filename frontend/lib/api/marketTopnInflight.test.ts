// POC5-12 — 같은 주소의 시장 TOP N GET 진행 중 공유(설계 §4 · PLAN §3 보완 1 · 판정 §4).
// 진짜 fetchMarketTopnLatest · request 를 쓰고 브라우저 fetch 만 가짜로 바꿔 서버 호출 수를 센다.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fetchMarketTopnLatest, postMarketRefresh } from "./market";

type Pending = { url: string; resolve: (body: unknown) => void; reject: (e: unknown) => void };

let pending: Pending[] = [];
const fetchMock = vi.fn((url: string, init?: { signal?: AbortSignal }) => {
  return new Promise((resolve, reject) => {
    init?.signal?.addEventListener("abort", () => {
      const e = new Error("aborted");
      e.name = "AbortError";
      reject(e);
    });
    pending.push({
      url,
      resolve: (body) =>
        resolve({ ok: true, status: 200, text: async () => JSON.stringify(body) }),
      reject,
    });
  });
});

beforeEach(() => {
  pending = [];
  fetchMock.mockClear();
  vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://api.test");
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const flush = async () => {
  for (let i = 0; i < 5; i++) await Promise.resolve();
};

describe("fetchMarketTopnLatest 진행 중 공유", () => {
  it("같은 입력 두 번 → 서버 호출 1회 · 같은 결과", async () => {
    const a = fetchMarketTopnLatest(10);
    const b = fetchMarketTopnLatest(10);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    pending[0].resolve({ status: "ok", asof: "2026-10-14" });
    expect(await a).toEqual({ status: "ok", asof: "2026-10-14" });
    expect(await b).toBe(await a);
  });

  it("끝나면 지운다 — 다음 호출은 다시 서버로(보관 캐시 없음)", async () => {
    const a = fetchMarketTopnLatest(10);
    pending[0].resolve({ status: "ok" });
    await a;
    const b = fetchMarketTopnLatest(10);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    pending[1].resolve({ status: "ok" });
    await b;
  });

  it("입력이 다르면 따로 부른다", () => {
    fetchMarketTopnLatest(10);
    fetchMarketTopnLatest(10, { basis: "daily" });
    fetchMarketTopnLatest(30);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("실패 뒤 지운다 — 같이 기다리던 쪽도 같은 실패 · 다음 호출은 새로 부름", async () => {
    const a = fetchMarketTopnLatest(10);
    const b = fetchMarketTopnLatest(10);
    pending[0].reject(new TypeError("network down"));
    await expect(a).rejects.toThrow(/네트워크 호출 실패/);
    await expect(b).rejects.toThrow(/네트워크 호출 실패/);
    fetchMarketTopnLatest(10);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("시간 초과 뒤 지운다 — 다음 호출은 새로 부름", async () => {
    vi.useFakeTimers();
    const a = fetchMarketTopnLatest(10);
    const caught = a.catch((e) => e);
    await vi.advanceTimersByTimeAsync(10001);
    expect(String(await caught)).toMatch(/요청 시간 초과/);
    await flush();
    fetchMarketTopnLatest(10);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe("postMarketRefresh scope (POC5-12)", () => {
  it("인자 없으면 원래 경로 · 'vix' 면 scope=vix", async () => {
    const full = postMarketRefresh();
    const vix = postMarketRefresh("vix");
    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual([
      "http://api.test/market/refresh",
      "http://api.test/market/refresh?scope=vix",
    ]);
    pending.forEach((p) => p.resolve({ status: "accepted", message: "", cooldown_remaining_seconds: 0 }));
    await Promise.all([full, vix]);
  });
});
