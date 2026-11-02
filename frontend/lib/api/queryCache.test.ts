// POC3-01 REMEDIATION — queryCache 계약 test (§5).
// 화면 재진입 시 성공 요청 재호출 안 함 · 동일 진행 중 요청 dedup ·
// 무효화 후 재조회 · endpoint/조건 다르면 키 분리.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import {
  useSharedQuery,
  invalidateQueries,
  __resetQueryCache,
} from "./queryCache";

beforeEach(() => {
  __resetQueryCache();
});

describe("useSharedQuery 캐시 공유", () => {
  it("재진입 시 성공한 요청을 재호출하지 않는다", async () => {
    const fetcher = vi.fn(async () => ({ v: 1 }));
    // 1차 마운트 → 1회 호출.
    const first = renderHook(() =>
      useSharedQuery("k1", fetcher),
    );
    await waitFor(() => expect(first.result.current.phase).toBe("success"));
    expect(fetcher).toHaveBeenCalledTimes(1);
    first.unmount();

    // 재마운트(화면 재진입) → 캐시 재사용, 재호출 없음.
    const second = renderHook(() =>
      useSharedQuery("k1", fetcher),
    );
    // 즉시 success (캐시).
    expect(second.result.current.phase).toBe("success");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("동일 진행 중 요청을 중복 실행하지 않는다", async () => {
    let resolve!: (v: unknown) => void;
    const fetcher = vi.fn(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    );
    // 두 컴포넌트가 동일 키를 동시에 요청.
    const a = renderHook(() => useSharedQuery("k2", fetcher));
    const b = renderHook(() => useSharedQuery("k2", fetcher));
    // 진행 중 요청은 1개만.
    expect(fetcher).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolve({ v: 2 });
    });
    await waitFor(() => expect(a.result.current.phase).toBe("success"));
    expect(b.result.current.phase).toBe("success");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("다른 endpoint/조건은 다른 키로 분리한다", async () => {
    const f1 = vi.fn(async () => ({ v: "a" }));
    const f2 = vi.fn(async () => ({ v: "b" }));
    const a = renderHook(() => useSharedQuery("kA", f1));
    const b = renderHook(() => useSharedQuery("kB", f2));
    await waitFor(() => expect(a.result.current.phase).toBe("success"));
    await waitFor(() => expect(b.result.current.phase).toBe("success"));
    expect(f1).toHaveBeenCalledTimes(1);
    expect(f2).toHaveBeenCalledTimes(1);
  });

  it("무효화 후에는 재조회한다 (변경 성공 이벤트)", async () => {
    const fetcher = vi.fn(async () => ({ v: Math.random() }));
    const h = renderHook(() => useSharedQuery("k3", fetcher));
    await waitFor(() => expect(h.result.current.phase).toBe("success"));
    expect(fetcher).toHaveBeenCalledTimes(1);

    // 변경 성공 → 관련 읽기 무효화.
    act(() => invalidateQueries("k3"));

    // 재마운트 시 재조회.
    h.unmount();
    const h2 = renderHook(() => useSharedQuery("k3", fetcher));
    await waitFor(() => expect(h2.result.current.phase).toBe("success"));
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("lazy 는 마운트 시 조회하지 않고 reload 로만 조회한다", async () => {
    const fetcher = vi.fn(async () => ({ v: 1 }));
    const h = renderHook(() => useSharedQuery("k4", fetcher, { lazy: true }));
    // 최초 idle · 미호출.
    expect(h.result.current.phase).toBe("idle");
    expect(fetcher).toHaveBeenCalledTimes(0);
    // 명시 reload → 1회 호출.
    act(() => h.result.current.reload());
    await waitFor(() => expect(h.result.current.phase).toBe("success"));
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("재조회 실패 시 이전 성공값을 stale 로 유지한다 (§4.4)", async () => {
    let call = 0;
    const fetcher = vi.fn(async () => {
      call += 1;
      if (call === 1) return { v: "ok" };
      throw new Error("network");
    });
    const h = renderHook(() => useSharedQuery("k5", fetcher));
    await waitFor(() => expect(h.result.current.phase).toBe("success"));
    // 재조회 실패.
    await act(async () => {
      h.result.current.reload();
    });
    await waitFor(() => {
      const s = h.result.current;
      expect(s.phase).toBe("success");
      if (s.phase === "success") expect(s.stale).toBe(true);
    });
  });

  it("재조회 실패 후 화면 재진입해도 stale 이 유지된다 (A-1(2))", async () => {
    let call = 0;
    const fetcher = vi.fn(async () => {
      call += 1;
      if (call === 1) return { v: "ok" };
      throw new Error("network");
    });
    const h = renderHook(() => useSharedQuery("k6", fetcher));
    await waitFor(() => expect(h.result.current.phase).toBe("success"));
    await act(async () => {
      h.result.current.reload();
    });
    await waitFor(() => {
      const s = h.result.current;
      if (s.phase === "success") expect(s.stale).toBe(true);
    });
    // 화면 나갔다 재진입 (언마운트 → 재마운트).
    h.unmount();
    const h2 = renderHook(() => useSharedQuery("k6", fetcher));
    // 캐시 엔트리에 refetchFailed 가 저장돼 재진입해도 stale 유지.
    const s2 = h2.result.current;
    expect(s2.phase).toBe("success");
    if (s2.phase === "success") expect(s2.stale).toBe(true);
  });

  it("재조회 성공 시 stale 이 해제된다", async () => {
    let call = 0;
    const fetcher = vi.fn(async () => {
      call += 1;
      if (call === 2) throw new Error("network");
      return { v: call };
    });
    const h = renderHook(() => useSharedQuery("k7", fetcher));
    await waitFor(() => expect(h.result.current.phase).toBe("success"));
    // 2차 실패 → stale.
    await act(async () => {
      h.result.current.reload();
    });
    await waitFor(() => {
      const s = h.result.current;
      if (s.phase === "success") expect(s.stale).toBe(true);
    });
    // 3차 성공 → stale 해제.
    await act(async () => {
      h.result.current.reload();
    });
    await waitFor(() => {
      const s = h.result.current;
      expect(s.phase).toBe("success");
      if (s.phase === "success") expect(s.stale).toBe(false);
    });
  });
});

// POC6-16 판정 §4 — 성공한 값과 그 값을 받은 시각을 같이 둔다. 실패 · 캐시 재사용 · 다시 그리기에는 시각을 바꾸지 않는다.
describe("성공 시각(successAt)", () => {
  it("성공 때 기록 · 재마운트(캐시 재사용) 때 그대로 · 다시 읽기 성공 때 새 시각", async () => {
    const now = vi.spyOn(Date, "now").mockReturnValue(1_000);
    const fetcher = vi.fn(async () => ({ v: 1 }));
    const a = renderHook(() => useSharedQuery("t1", fetcher));
    await waitFor(() => expect(a.result.current.phase).toBe("success"));
    expect(a.result.current.phase === "success" && a.result.current.successAt).toBe(1_000);
    a.unmount();
    now.mockReturnValue(5_000);
    const b = renderHook(() => useSharedQuery("t1", fetcher));
    expect(b.result.current.phase === "success" && b.result.current.successAt).toBe(1_000);
    expect(fetcher).toHaveBeenCalledTimes(1);
    await act(async () => {
      await b.result.current.reloadAsync();
    });
    expect(b.result.current.phase === "success" && b.result.current.successAt).toBe(5_000);
    now.mockRestore();
  });

  it("다시 읽기 실패 — 이전 값 · 이전 시각 그대로 · stale 표시(현재 시각으로 바꾸지 않음)", async () => {
    const now = vi.spyOn(Date, "now").mockReturnValue(2_000);
    let fail = false;
    const fetcher = vi.fn(async () => {
      if (fail) throw new Error("x");
      return { v: 7 };
    });
    const h = renderHook(() => useSharedQuery("t2", fetcher));
    await waitFor(() => expect(h.result.current.phase).toBe("success"));
    fail = true;
    now.mockReturnValue(9_000);
    await act(async () => {
      await h.result.current.reloadAsync().catch(() => undefined);
    });
    const st = h.result.current;
    expect(st.phase).toBe("success");
    if (st.phase === "success") {
      expect(st.stale).toBe(true);
      expect(st.successAt).toBe(2_000);
      expect(st.data).toEqual({ v: 7 });
    }
    now.mockRestore();
  });

  it("첫 조회 실패 — error · 성공 시각 없음", async () => {
    const fetcher = vi.fn(async () => {
      throw new Error("x");
    });
    const h = renderHook(() => useSharedQuery("t3", fetcher));
    await waitFor(() => expect(h.result.current.phase).toBe("error"));
    expect("successAt" in h.result.current).toBe(false);
  });
});
