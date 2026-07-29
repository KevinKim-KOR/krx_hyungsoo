// POC3-01 REMEDIATION — 무효화 연결 계약 test (§4.5 · A-1(1)).
// 변경 성공 이벤트가 Dashboard 관련 읽기만 무효화하고, 변경 실패 시 무효화하지
// 않음을 검증한다. HoldingsClient/MarketDiscoveryView 의 성공/실패 분기 로직을
// 재현해 invalidateQueries 호출 여부를 확인한다.
import { describe, it, expect, beforeEach, vi } from "vitest";
import * as cache from "./queryCache";
import {
  DASH_KEY_MARKET,
  DASH_KEY_HOLDINGS,
  DASH_KEY_EVIDENCE,
  DASH_KEY_NAV,
  WB_KEY_CAND,
  WB_KEY_HOLD,
  WB_KEY_EVID,
  HOLDINGS_INVALIDATION_KEYS,
  MARKET_INVALIDATION_KEYS,
} from "./dashboardKeys";

beforeEach(() => {
  cache.__resetQueryCache();
  vi.restoreAllMocks();
});

// HoldingsClient 저장 로직 재현 (성공 시에만 무효화 · 실패 시 catch 로 미호출).
async function simulateHoldingsSave(saveFn: () => Promise<void>) {
  try {
    await saveFn();
    for (const k of HOLDINGS_INVALIDATION_KEYS) cache.invalidateQueries(k);
  } catch {
    // 변경 실패 → 무효화 안 함.
  }
}

// MarketDiscoveryView 갱신 status 처리 재현.
function simulateMarketStatus(status: "completed" | "failed") {
  if (status === "completed") {
    for (const k of MARKET_INVALIDATION_KEYS) cache.invalidateQueries(k);
  }
  // failed 분기는 무효화 안 함.
}

describe("무효화 그룹 정합성", () => {
  it("Holdings 무효화 그룹은 Dashboard·Workbench 의 보유·Evidence 를 포함한다", () => {
    expect(HOLDINGS_INVALIDATION_KEYS).toContain(DASH_KEY_HOLDINGS);
    expect(HOLDINGS_INVALIDATION_KEYS).toContain(DASH_KEY_EVIDENCE);
    // A-1(7): Workbench 키도 무효화 대상.
    expect(HOLDINGS_INVALIDATION_KEYS).toContain(WB_KEY_HOLD);
    expect(HOLDINGS_INVALIDATION_KEYS).toContain(WB_KEY_EVID);
    // 시장·NAV 는 무관.
    expect(HOLDINGS_INVALIDATION_KEYS).not.toContain(DASH_KEY_MARKET);
    expect(HOLDINGS_INVALIDATION_KEYS).not.toContain(DASH_KEY_NAV);
    expect(HOLDINGS_INVALIDATION_KEYS).not.toContain(WB_KEY_CAND);
  });

  it("Market 무효화 그룹은 Dashboard·Workbench 의 시장·Evidence 를 포함한다", () => {
    expect(MARKET_INVALIDATION_KEYS).toContain(DASH_KEY_MARKET);
    expect(MARKET_INVALIDATION_KEYS).toContain(DASH_KEY_EVIDENCE);
    // A-1(7): Workbench 후보·Evidence 도 무효화 대상.
    expect(MARKET_INVALIDATION_KEYS).toContain(WB_KEY_CAND);
    expect(MARKET_INVALIDATION_KEYS).toContain(WB_KEY_EVID);
    // 보유·NAV 는 무관.
    expect(MARKET_INVALIDATION_KEYS).not.toContain(DASH_KEY_HOLDINGS);
    expect(MARKET_INVALIDATION_KEYS).not.toContain(DASH_KEY_NAV);
    expect(MARKET_INVALIDATION_KEYS).not.toContain(WB_KEY_HOLD);
  });
});

describe("변경 성공/실패 무효화 연결", () => {
  it("Holdings 저장 성공 시 보유·Evidence 를 무효화한다", async () => {
    const spy = vi.spyOn(cache, "invalidateQueries");
    await simulateHoldingsSave(async () => {});
    expect(spy).toHaveBeenCalledWith(DASH_KEY_HOLDINGS);
    expect(spy).toHaveBeenCalledWith(DASH_KEY_EVIDENCE);
    // 시장·NAV 는 무효화 대상 아님.
    expect(spy).not.toHaveBeenCalledWith(DASH_KEY_MARKET);
    expect(spy).not.toHaveBeenCalledWith(DASH_KEY_NAV);
  });

  it("Holdings 저장 실패 시 무효화하지 않는다 (§4.5)", async () => {
    const spy = vi.spyOn(cache, "invalidateQueries");
    await simulateHoldingsSave(async () => {
      throw new Error("save failed");
    });
    expect(spy).not.toHaveBeenCalled();
  });

  it("Market 갱신 완료 시 시장 + Evidence 를 무효화한다", () => {
    const spy = vi.spyOn(cache, "invalidateQueries");
    simulateMarketStatus("completed");
    expect(spy).toHaveBeenCalledWith(DASH_KEY_MARKET);
    // Evidence 도 무효화 (시장 후보·국면 의존).
    expect(spy).toHaveBeenCalledWith(DASH_KEY_EVIDENCE);
    // 보유·NAV 는 무효화 대상 아님.
    expect(spy).not.toHaveBeenCalledWith(DASH_KEY_HOLDINGS);
    expect(spy).not.toHaveBeenCalledWith(DASH_KEY_NAV);
  });

  it("Market 갱신 실패 시 무효화하지 않는다 (§4.5)", () => {
    const spy = vi.spyOn(cache, "invalidateQueries");
    simulateMarketStatus("failed");
    expect(spy).not.toHaveBeenCalled();
  });
});

describe("무효화 후 재조회", () => {
  it("무효화된 키는 다음 조회에서 재호출된다", async () => {
    const fetcher = vi.fn(async () => ({ v: 1 }));
    const { renderHook, waitFor } = await import("@testing-library/react");
    const h = renderHook(() => cache.useSharedQuery(DASH_KEY_HOLDINGS, fetcher));
    await waitFor(() => expect(h.result.current.phase).toBe("success"));
    expect(fetcher).toHaveBeenCalledTimes(1);
    // 무효화.
    cache.invalidateQueries(DASH_KEY_HOLDINGS);
    h.unmount();
    // 재마운트 → 재조회.
    const h2 = renderHook(() => cache.useSharedQuery(DASH_KEY_HOLDINGS, fetcher));
    await waitFor(() => expect(h2.result.current.phase).toBe("success"));
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
