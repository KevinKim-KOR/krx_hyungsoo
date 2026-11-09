// POC6-27 — 목록 조건 탭 공유(설계 §4 · 판정 §4) · 조건 키 · 무효화 · '받아 두고 반영' 캐시 함수.
import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import {
  __resetMarketCondition,
  getMarketCondition,
  setMarketCondition,
  todayMarketKey,
  useMarketCondition,
} from "./marketConditionStore";
import { DASH_KEY_MARKET, MARKET_INVALIDATION_KEYS } from "./api/dashboardKeys";
import { __resetQueryCache, commitQuery, invalidateQueries, markQueryFailed, useSharedQuery } from "./api/queryCache";

const PREF = "krx.marketDiscovery.defaultBasis.v1";
const ALL = { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true };

beforeEach(() => {
  window.localStorage.clear();
  __resetQueryCache();
});

describe("탭 공유 목록 조건", () => {
  it("처음 = 저장 기본 기간 · 높은 순 · 4종 제외 · 기본 조건의 키는 기존 대시보드 키와 같다", () => {
    expect(getMarketCondition()).toEqual({ basis: "one_month", order: "desc", filters: ALL });
    expect(todayMarketKey(getMarketCondition())).toBe(DASH_KEY_MARKET);
    __resetMarketCondition();
    window.localStorage.setItem(PREF, "three_month");
    expect(getMarketCondition().basis).toBe("three_month");
    __resetMarketCondition();
    window.localStorage.setItem(PREF, "엉뚱한 값");
    expect(getMarketCondition().basis).toBe("one_month");
  });

  it("바꾸면 구독 화면에 알림 · 같은 조건이면 알리지 않음 · 새로 고침(비움)이면 기본으로", () => {
    const { result } = renderHook(() => useMarketCondition());
    act(() => setMarketCondition({ basis: "daily", order: "asc", filters: { ...ALL, exclude_futures: false } }));
    expect(result.current).toEqual({ basis: "daily", order: "asc", filters: { ...ALL, exclude_futures: false } });
    const before = result.current;
    act(() => setMarketCondition({ basis: "daily", order: "asc", filters: { ...ALL, exclude_futures: false } }));
    expect(result.current).toBe(before);
    __resetMarketCondition();
    expect(getMarketCondition()).toEqual({ basis: "one_month", order: "desc", filters: ALL });
  });

  it("조건마다 키가 다르고 · 시장 갱신 무효화 목록의 앞부분이 조건 키를 모두 지운다", async () => {
    const k = todayMarketKey({ basis: "three_month", order: "asc", filters: { ...ALL, exclude_inverse: false } });
    expect(k).not.toBe(DASH_KEY_MARKET);
    commitQuery(k, { a: 1 });
    commitQuery(DASH_KEY_MARKET, { a: 2 });
    const { result } = renderHook(() => useSharedQuery<{ a: number }>(k, async () => ({ a: 3 })));
    expect(result.current.phase).toBe("success");
    for (const key of MARKET_INVALIDATION_KEYS) invalidateQueries(key);
    await waitFor(() => expect(result.current.phase).not.toBe("success"));
  });
});

describe("받아 두고 반영(판정 Q3) — commitQuery · markQueryFailed", () => {
  it("반영하면 새 값 · 새 성공 시각 · 다시 읽기 실패 표시 해제", () => {
    const { result } = renderHook(() => useSharedQuery<number>("k", async () => 1));
    act(() => commitQuery("k", 5));
    expect(result.current).toMatchObject({ phase: "success", data: 5, stale: false });
    expect(typeof (result.current as { successAt?: number }).successAt).toBe("number");
  });

  it("반영 시각 = 실제로 받은 시각(창을 오래 열어 둬도 고른 시각으로 밀리지 않음 · 검토 F6)", () => {
    const { result } = renderHook(() => useSharedQuery<number>("k4", async () => 1));
    act(() => commitQuery("k4", 9, 1_700_000_000_000));
    expect((result.current as { successAt?: number }).successAt).toBe(1_700_000_000_000);
  });

  it("검증자 r1 F1 — 반영 뒤 늦게 끝난 그 전 조회는 덮지 않는다(늦은 성공 · 늦은 실패 둘 다)", async () => {
    let okOld!: (v: number) => void;
    const a = renderHook(() => useSharedQuery<number>("k5", () => new Promise<number>((r) => (okOld = r))));
    expect(a.result.current.phase).toBe("loading");
    act(() => commitQuery("k5", 20, 1_700_000_000_000));
    await act(async () => okOld(10));
    expect(a.result.current).toMatchObject({ phase: "success", data: 20, stale: false, successAt: 1_700_000_000_000 });

    let failOld!: (e: Error) => void;
    const b = renderHook(() => useSharedQuery<number>("k6", () => new Promise<number>((_r, j) => (failOld = j))));
    act(() => commitQuery("k6", 20));
    await act(async () => failOld(new Error("늦은 실패")));
    expect(b.result.current).toMatchObject({ phase: "success", data: 20, stale: false });
  });

  it("검증자 r1 F1 — 같은 키의 새 조회가 시작된 뒤 끝난 그 전 조회는 덮지 않는다(무효화 → 다시 읽기)", async () => {
    const pending: ((v: number) => void)[] = [];
    const { result } = renderHook(() => useSharedQuery<number>("k7", () => new Promise<number>((r) => pending.push(r))));
    act(() => invalidateQueries("k7"));
    let second!: Promise<number>;
    act(() => {
      second = result.current.reloadAsync();
    });
    expect(pending).toHaveLength(2);
    await act(async () => {
      pending[1](2);
      await second;
    });
    await act(async () => pending[0](1));
    expect(result.current).toMatchObject({ phase: "success", data: 2 });
  });

  it("무효화로 칸만 비고 새 조회가 없으면 그 전 조회 응답이 들어온다(불러오는 중에 묶이지 않음 · 기존 동작)", async () => {
    let ok!: (v: number) => void;
    const { result } = renderHook(() => useSharedQuery<number>("k8", () => new Promise<number>((r) => (ok = r))));
    act(() => invalidateQueries("k8"));
    await act(async () => ok(3));
    expect(result.current).toMatchObject({ phase: "success", data: 3 });
  });

  it("다시 읽기 실패 표시(지금은 오류)는 진행 중 조회의 순번을 끊지 않는다 — 그 조회가 나중에 성공하면 그 값", async () => {
    let ok!: (v: number) => void;
    const { result } = renderHook(() => useSharedQuery<number>("k9", () => new Promise<number>((r) => (ok = r))));
    act(() => markQueryFailed("k9"));
    expect(result.current.phase).toBe("error");
    await act(async () => ok(4));
    expect(result.current).toMatchObject({ phase: "success", data: 4, stale: false });
  });

  it("실패 표시는 이전 값 · 그 시각을 남긴다 · 이전 값이 없으면 오류", async () => {
    const { result } = renderHook(() => useSharedQuery<number>("k2", async () => 7));
    await waitFor(() => expect(result.current.phase).toBe("success"));
    const at = (result.current as { successAt?: number }).successAt;
    act(() => markQueryFailed("k2"));
    expect(result.current).toMatchObject({ phase: "success", data: 7, stale: true, successAt: at });
    const none = renderHook(() => useSharedQuery<number>("k3", () => new Promise<number>(() => undefined)));
    act(() => markQueryFailed("k3"));
    expect(none.result.current.phase).toBe("error");
  });
});
