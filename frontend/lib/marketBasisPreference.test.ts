// POC5-26 — 「요즘 잘 오르는 ETF」 기본 조회 기준 저장 helper(설계 §3 · PLAN §2 · §3 · 판정 §2 · §3).
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  MARKET_BASIS_PREF_KEY,
  readMarketBasisPref,
  writeMarketBasisPref,
} from "./marketBasisPreference";

const KEY_LITERAL = "krx.marketDiscovery.defaultBasis.v1"; // 문서(PLAN §2 · PROGRAM_TRUTH)에 적은 키 그대로
const realGetItem = Storage.prototype.getItem;
const realSetItem = Storage.prototype.setItem;

// localStorage 만 막는다(sessionStorage 는 그대로).
function failLocal(method: "getItem" | "setItem") {
  const real = method === "getItem" ? realGetItem : realSetItem;
  return vi.spyOn(Storage.prototype, method).mockImplementation(function (
    this: Storage,
    ...args: unknown[]
  ) {
    if (this === window.localStorage) throw new DOMException("blocked", "SecurityError");
    return (real as (...a: unknown[]) => unknown).apply(this, args);
  } as never);
}

// 읽기가 저장소에 쓰는지 본다(설정 · 지우기 둘 다 · 실제 동작은 그대로).
function watchWrites() {
  const set = vi.spyOn(Storage.prototype, "setItem");
  const remove = vi.spyOn(Storage.prototype, "removeItem");
  const clear = vi.spyOn(Storage.prototype, "clear");
  return () => set.mock.calls.length + remove.mock.calls.length + clear.mock.calls.length;
}

beforeEach(() => {
  window.localStorage.clear();
});
afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("저장 키 (POC5-26)", () => {
  it("키는 문서에 적은 값 그대로(바뀌면 저장된 기본이 모두 사라짐)", () => {
    expect(MARKET_BASIS_PREF_KEY).toBe(KEY_LITERAL);
    window.localStorage.setItem(KEY_LITERAL, "three_month");
    expect(readMarketBasisPref()).toEqual({ basis: "three_month", status: "saved" });
    expect(writeMarketBasisPref("daily")).toBe(true);
    expect(window.localStorage.getItem(KEY_LITERAL)).toBe("daily");
  });
});

describe("읽기 (POC5-26)", () => {
  it("저장값 없음 → 1개월 · none · 읽으면서 아무것도 쓰지 않음", () => {
    const writes = watchWrites();
    expect(readMarketBasisPref()).toEqual({ basis: "one_month", status: "none" });
    expect(writes()).toBe(0);
    expect(window.localStorage.getItem(MARKET_BASIS_PREF_KEY)).toBeNull();
  });

  it.each(["daily", "one_month", "three_month"] as const)("허용 값 %s → 그대로 · saved", (v) => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, v);
    const writes = watchWrites();
    expect(readMarketBasisPref()).toEqual({ basis: v, status: "saved" });
    expect(writes()).toBe(0);
  });

  it.each(["weekly", "", "THREE_MONTH", " three_month", '"three_month"', "1개월", "six_month"])(
    "허용 밖 값 %j → 1개월 · invalid · 저장값을 고치거나 지우지 않음",
    (v) => {
      window.localStorage.setItem(MARKET_BASIS_PREF_KEY, v);
      const writes = watchWrites();
      expect(readMarketBasisPref()).toEqual({ basis: "one_month", status: "invalid" });
      expect(writes()).toBe(0);
      expect(window.localStorage.getItem(MARKET_BASIS_PREF_KEY)).toBe(v);
    },
  );

  it("다른 키의 값은 읽지 않는다(전용 키 하나)", () => {
    window.localStorage.setItem("basis", "three_month");
    window.localStorage.setItem(`${MARKET_BASIS_PREF_KEY}.old`, "three_month");
    expect(readMarketBasisPref()).toEqual({ basis: "one_month", status: "none" });
  });

  it("getItem 예외 → 1개월 · read_failed · 저장값은 그대로", () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    const spy = failLocal("getItem");
    const writes = watchWrites();
    expect(readMarketBasisPref()).toEqual({ basis: "one_month", status: "read_failed" });
    expect(writes()).toBe(0);
    spy.mockRestore();
    expect(window.localStorage.getItem(MARKET_BASIS_PREF_KEY)).toBe("three_month");
  });

  it("localStorage 접근 자체가 막힘(SecurityError) → 1개월 · read_failed", () => {
    vi.spyOn(window, "localStorage", "get").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    expect(readMarketBasisPref()).toEqual({ basis: "one_month", status: "read_failed" });
  });
});

describe("쓰기 (POC5-26)", () => {
  it.each(["daily", "one_month", "three_month"] as const)("%s 저장 → true · 그 값 그대로", (v) => {
    expect(writeMarketBasisPref(v)).toBe(true);
    expect(window.localStorage.getItem(MARKET_BASIS_PREF_KEY)).toBe(v);
    expect(readMarketBasisPref()).toEqual({ basis: v, status: "saved" });
  });

  it("허용 밖 값이 있던 자리도 명시 저장으로만 바뀐다", () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "weekly");
    expect(writeMarketBasisPref("daily")).toBe(true);
    expect(window.localStorage.getItem(MARKET_BASIS_PREF_KEY)).toBe("daily");
  });

  it("setItem 예외(저장소 막힘 · 용량) → false · 이전 값 그대로", () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    failLocal("setItem");
    expect(writeMarketBasisPref("one_month")).toBe(false);
    expect(realGetItem.call(window.localStorage, MARKET_BASIS_PREF_KEY)).toBe("three_month");
  });

  it("setItem 은 됐지만 다시 읽은 값이 다른 값이면 false(저장 확인 실패)", () => {
    window.localStorage.setItem(MARKET_BASIS_PREF_KEY, "three_month");
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => undefined);
    expect(writeMarketBasisPref("one_month")).toBe(false);
    expect(realGetItem.call(window.localStorage, MARKET_BASIS_PREF_KEY)).toBe("three_month");
  });

  it("setItem 은 됐지만 다시 읽은 값이 없으면 false", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => undefined);
    expect(writeMarketBasisPref("one_month")).toBe(false);
  });

  it("다시 읽기 예외 → false", () => {
    failLocal("getItem");
    expect(writeMarketBasisPref("one_month")).toBe(false);
  });

  it("localStorage 접근 자체가 막힘 → false", () => {
    vi.spyOn(window, "localStorage", "get").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    expect(writeMarketBasisPref("one_month")).toBe(false);
  });
});
