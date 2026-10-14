// POC5-12 — 「요즘 잘 오르는 ETF」 갱신 버튼의 'VIX 다시 받기'(설계 §3 · PLAN §2 · 판정 Q2 · §3)와
// 시장 GET 응답 처리(설계 §4 · PLAN §3 · 판정 §4): 같은 입력 1회 · 늦은 응답 무시 · 받은 화면 유지.
import { StrictMode } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";

const fetchMarketTopnLatest = vi.fn();
const postMarketRefresh = vi.fn();
const fetchMarketRefreshStatus = vi.fn();
const actualApi = vi.hoisted(() => ({}) as Record<string, unknown>);
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  Object.assign(actualApi, actual);
  return {
    ...actual,
    fetchMarketTopnLatest: (...a: unknown[]) => fetchMarketTopnLatest(...a),
    postMarketRefresh: (...a: unknown[]) => postMarketRefresh(...a),
    fetchMarketRefreshStatus: (...a: unknown[]) => fetchMarketRefreshStatus(...a),
  };
});

import MarketDiscoveryView from "./MarketDiscoveryView";

function topn(asof = "2026-10-12") {
  return {
    status: "ok",
    asof,
    candidates: [],
    daily_topn: [],
    one_month_topn: [],
    three_month_topn: [],
    market_context: null,
  };
}

function status(over: Record<string, unknown> = {}) {
  return { status: "completed", refresh_id: "r1", cooldown_remaining_seconds: 0, ...over };
}

const NEEDED = { needed: true, status: "needed", refresh_id: "r1", error_summary: "시장 불안 지표(VIX)를 갱신하지 못했습니다" };

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

async function flush() {
  await act(async () => {
    for (let i = 0; i < 8; i++) await Promise.resolve();
  });
}

async function tick(ms = 4100) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
  await flush();
}

const text = () => document.body.textContent ?? "";
const refreshButton = (name: string) => screen.getAllByRole("button", { name })[0];

beforeEach(() => {
  __resetQueryCache();
  vi.useFakeTimers();
  fetchMarketTopnLatest.mockReset().mockResolvedValue(topn());
  postMarketRefresh.mockReset();
  fetchMarketRefreshStatus.mockReset().mockResolvedValue(status({ status: "idle" }));
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("'VIX 다시 받기' 버튼 (POC5-12)", () => {
  it("대기 중 · 표식 있음 → 'VIX 다시 받기' · scope=vix · 같은 id 로 끝난 결과 · 시장 다시 읽기", async () => {
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ cooldown_remaining_seconds: 3600, vix_retry: NEEDED }),
    );
    postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "vix_retry_1", message: "", cooldown_remaining_seconds: 3600 });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    expect(screen.queryByRole("button", { name: "최신 시장 데이터 갱신" })).toBeNull();
    fireEvent.click(refreshButton("VIX 다시 받기"));
    await flush();
    expect(postMarketRefresh).toHaveBeenCalledWith("vix");
    expect(text()).toContain("VIX 다시 받는 중…");
    expect(fetchMarketTopnLatest).toHaveBeenCalledTimes(1);
    // 이전 재시도의 완료 결과(다른 id)는 이번 결과로 읽지 않는다.
    fetchMarketRefreshStatus.mockResolvedValue(
      status({
        cooldown_remaining_seconds: 3600,
        vix_retry: { needed: false, status: "completed", refresh_id: "vix_retry_0", vix_as_of_date: "2026-10-09" },
      }),
    );
    await tick();
    expect(text()).toContain("VIX 다시 받는 중…");
    fetchMarketRefreshStatus.mockResolvedValue(
      status({
        cooldown_remaining_seconds: 3600,
        vix_retry: { needed: false, status: "completed", refresh_id: "vix_retry_1", vix_as_of_date: "2026-10-13" },
      }),
    );
    await tick();
    expect(text()).toContain("VIX 다시 받기 완료(기준일 2026-10-13)");
    expect(text()).not.toContain("갱신 완료");
    expect(fetchMarketTopnLatest).toHaveBeenCalledTimes(2);
    // 표식이 풀려 원래 버튼으로 돌아온다.
    expect(refreshButton("최신 시장 데이터 갱신")).toBeTruthy();
  });

  it("첫 상태 조회 전에 이미 끝났어도 결과가 보인다(빠른 완료)", async () => {
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ cooldown_remaining_seconds: 3600, vix_retry: NEEDED }),
    );
    postMarketRefresh.mockImplementation(async () => {
      fetchMarketRefreshStatus.mockResolvedValue(
        status({
          cooldown_remaining_seconds: 3600,
          vix_retry: { needed: false, status: "completed", refresh_id: "vix_retry_2", vix_as_of_date: "2026-10-13" },
        }),
      );
      return { status: "accepted", refresh_id: "vix_retry_2", message: "", cooldown_remaining_seconds: 3600 };
    });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(refreshButton("VIX 다시 받기"));
    await flush();
    await tick();
    expect(text()).toContain("VIX 다시 받기 완료(기준일 2026-10-13)");
  });

  it("다시 받기 실패 → '확인 필요: …' · 버튼은 그대로 'VIX 다시 받기' · 시장 다시 읽기 없음", async () => {
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ cooldown_remaining_seconds: 3600, vix_retry: NEEDED }),
    );
    postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "vix_retry_3", message: "", cooldown_remaining_seconds: 3600 });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(refreshButton("VIX 다시 받기"));
    await flush();
    fetchMarketRefreshStatus.mockResolvedValue(
      status({
        cooldown_remaining_seconds: 3600,
        vix_retry: { ...NEEDED, status: "failed", refresh_id: "vix_retry_3" },
      }),
    );
    await tick();
    expect(text()).toContain("확인 필요: 시장 불안 지표(VIX)를 갱신하지 못했습니다");
    expect(refreshButton("VIX 다시 받기")).not.toBeDisabled();
    expect(fetchMarketTopnLatest).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["대기 끝(0) · 표식 있음", { cooldown_remaining_seconds: 0, vix_retry: NEEDED }],
    ["대기 중 · 표식 없음", { cooldown_remaining_seconds: 3600, vix_retry: null }],
    ["대기 중 · 다시 받기 완료", { cooldown_remaining_seconds: 3600, vix_retry: { needed: false, status: "completed", refresh_id: "x" } }],
    ["대기 중 · 해제(cleared)", { cooldown_remaining_seconds: 3600, vix_retry: { needed: false, status: "cleared", refresh_id: "x" } }],
  ])("%s → 원래 버튼 · 전체 갱신(scope 없음)", async (_label, over) => {
    fetchMarketRefreshStatus.mockResolvedValue(status(over));
    postMarketRefresh.mockResolvedValue({ status: "skipped_cooldown", refresh_id: "r1", message: "", cooldown_remaining_seconds: 3600 });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    expect(screen.queryByRole("button", { name: "VIX 다시 받기" })).toBeNull();
    fireEvent.click(refreshButton("최신 시장 데이터 갱신"));
    await flush();
    expect(postMarketRefresh).toHaveBeenCalledWith();
  });

  it("not_needed 응답은 안내 한 줄 · 표식을 다시 읽어 원래 버튼으로", async () => {
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ cooldown_remaining_seconds: 3600, vix_retry: NEEDED }),
    );
    postMarketRefresh.mockImplementation(async () => {
      fetchMarketRefreshStatus.mockResolvedValue(
        status({ cooldown_remaining_seconds: 3600, vix_retry: { needed: false, status: "cleared" } }),
      );
      return { status: "not_needed", refresh_id: null, message: "다시 받을 VIX 실패 기록이 없습니다.", cooldown_remaining_seconds: 3600 };
    });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(refreshButton("VIX 다시 받기"));
    await flush();
    expect(text()).toContain("다시 받을 VIX 실패 기록이 없습니다.");
    expect(refreshButton("최신 시장 데이터 갱신")).toBeTruthy();
  });

  it("전체 갱신이 VIX 만 실패하고 끝나면 같은 화면에서 바로 'VIX 다시 받기'", async () => {
    postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "r9", message: "", cooldown_remaining_seconds: 0 });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(refreshButton("최신 시장 데이터 갱신"));
    await flush();
    fetchMarketRefreshStatus.mockResolvedValue(
      status({
        refresh_id: "r9",
        error_summary: "시장 불안 지표(VIX)를 갱신하지 못했습니다",
        cooldown_remaining_seconds: 21600,
        vix_retry: { ...NEEDED, refresh_id: "r9" },
      }),
    );
    await tick();
    expect(text()).toContain("갱신 완료. 확인 필요: 시장 불안 지표(VIX)를 갱신하지 못했습니다");
    expect(refreshButton("VIX 다시 받기")).toBeTruthy();
  });

  it("다시 받기 결과 줄은 다음 전체 갱신을 시작하면 비운다", async () => {
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ cooldown_remaining_seconds: 3600, vix_retry: NEEDED }),
    );
    postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "vix_retry_4", message: "", cooldown_remaining_seconds: 3600 });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(refreshButton("VIX 다시 받기"));
    await flush();
    fetchMarketRefreshStatus.mockResolvedValue(
      status({
        cooldown_remaining_seconds: 0,
        vix_retry: { ...NEEDED, status: "failed", refresh_id: "vix_retry_4" },
      }),
    );
    await tick();
    expect(text()).toContain("확인 필요: 시장 불안 지표(VIX)를 갱신하지 못했습니다");
    // 대기가 끝난 뒤(상태 0) 원래 버튼으로 전체 갱신.
    postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "r10", message: "", cooldown_remaining_seconds: 0 });
    fetchMarketRefreshStatus.mockResolvedValue(status({ status: "running", refresh_id: "r10" }));
    fireEvent.click(refreshButton("최신 시장 데이터 갱신"));
    await flush();
    expect(postMarketRefresh).toHaveBeenLastCalledWith();
    expect(text()).not.toContain("확인 필요: 시장 불안 지표(VIX)");
    expect(text()).toContain("갱신 중...");
  });
});

describe("검토 반영 (POC5-12)", () => {
  it("갱신 중 필터를 바꾸면 갱신이 끝난 뒤 다시 읽기도 새 조건이다(옛 조건 자료를 새 결과처럼 보이지 않음)", async () => {
    postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "r20", message: "", cooldown_remaining_seconds: 0 });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    fetchMarketRefreshStatus.mockResolvedValue(status({ status: "running", refresh_id: "r20" }));
    fireEvent.click(refreshButton("최신 시장 데이터 갱신"));
    await flush();
    fireEvent.click(screen.getByLabelText("레버리지 제외")); // 기본 true → false
    await flush();
    const changed = fetchMarketTopnLatest.mock.calls.length;
    expect(fetchMarketTopnLatest.mock.calls[changed - 1][1]).toMatchObject({ excludeLeveraged: false });
    fetchMarketRefreshStatus.mockResolvedValue(status({ refresh_id: "r20" }));
    await tick();
    expect(text()).toContain("갱신 완료.");
    expect(fetchMarketTopnLatest.mock.calls.length).toBe(changed + 1);
    expect(fetchMarketTopnLatest.mock.calls[changed][1]).toMatchObject({ excludeLeveraged: false });
  });

  it("전체 갱신 POST 가 'VIX 다시 받기 실행 중'으로 거절되면 그 진행 · 결과를 보이고 '갱신 완료'로 부르지 않는다", async () => {
    postMarketRefresh.mockResolvedValue({ status: "vix_retry_running", refresh_id: "vix_retry_7", message: "VIX 다시 받기가 진행 중입니다.", cooldown_remaining_seconds: 0 });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(refreshButton("최신 시장 데이터 갱신"));
    await flush();
    expect(postMarketRefresh).toHaveBeenCalledWith();
    expect(text()).toContain("VIX 다시 받는 중…");
    fetchMarketRefreshStatus.mockResolvedValue(
      status({
        refresh_id: "r_old",
        vix_retry: { needed: false, status: "completed", refresh_id: "vix_retry_7", vix_as_of_date: "2026-10-13" },
      }),
    );
    await tick();
    expect(text()).toContain("VIX 다시 받기 완료(기준일 2026-10-13)");
    expect(text()).not.toContain("갱신 완료.");
    expect(text()).not.toContain("갱신 실패");
  });

  it("'VIX 다시 받기'가 이미 도는 중이면(다른 창) 그 id 로 결과까지 본다", async () => {
    fetchMarketRefreshStatus.mockResolvedValue(status({ cooldown_remaining_seconds: 3600, vix_retry: NEEDED }));
    postMarketRefresh.mockResolvedValue({ status: "vix_retry_running", refresh_id: "vix_retry_8", message: "VIX 다시 받기가 진행 중입니다.", cooldown_remaining_seconds: 3600 });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(refreshButton("VIX 다시 받기"));
    await flush();
    expect(text()).toContain("VIX 다시 받는 중…");
    fetchMarketRefreshStatus.mockResolvedValue(
      status({
        cooldown_remaining_seconds: 3600,
        vix_retry: { ...NEEDED, status: "failed", refresh_id: "vix_retry_8" },
      }),
    );
    await tick();
    expect(text()).toContain("확인 필요: 시장 불안 지표(VIX)를 갱신하지 못했습니다");
  });

  it("화면을 연 채 6시간 대기가 끝나면 버튼이 원래 전체 갱신으로 돌아온다", async () => {
    fetchMarketRefreshStatus.mockResolvedValue(status({ cooldown_remaining_seconds: 60, vix_retry: NEEDED }));
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    expect(refreshButton("VIX 다시 받기")).toBeTruthy();
    await tick(59_000);
    expect(refreshButton("VIX 다시 받기")).toBeTruthy();
    await tick(1_100);
    expect(screen.queryByRole("button", { name: "VIX 다시 받기" })).toBeNull();
    postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "r30", message: "", cooldown_remaining_seconds: 0 });
    fireEvent.click(refreshButton("최신 시장 데이터 갱신"));
    await flush();
    expect(postMarketRefresh).toHaveBeenCalledWith();
  });
});

describe("검증자 r1 — 멈춘 뒤 온 이전 상태 응답 (POC5-12)", () => {
  // 검증자 재현 순서: 이전 상태 요청 2개 겹침 → 두 번째 응답으로 실패 → 새 재시도 → 첫 번째의 늦은 응답.
  it.each([false, true])("이전 재시도의 늦은 응답 도착=%s → 새 진행 줄 · 버튼 잠금 · 상태 확인 유지", async (deliverOld) => {
    fetchMarketRefreshStatus.mockResolvedValue(status({ cooldown_remaining_seconds: 3600, vix_retry: NEEDED }));
    postMarketRefresh.mockResolvedValueOnce({ status: "accepted", refresh_id: "vix_old", message: "", cooldown_remaining_seconds: 3600 });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(refreshButton("VIX 다시 받기"));
    await flush();
    const delayedOld = deferred<ReturnType<typeof status>>();
    const oldFailure = status({ cooldown_remaining_seconds: 3600, vix_retry: { ...NEEDED, status: "failed", refresh_id: "vix_old" } });
    fetchMarketRefreshStatus.mockReturnValueOnce(delayedOld.promise).mockResolvedValueOnce(oldFailure);
    await tick(4000);
    await tick(4000);
    expect(text()).toContain("확인 필요: 시장 불안 지표(VIX)를 갱신하지 못했습니다");
    postMarketRefresh.mockResolvedValueOnce({ status: "accepted", refresh_id: "vix_new", message: "", cooldown_remaining_seconds: 3600 });
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ cooldown_remaining_seconds: 3600, vix_retry: { needed: false, status: "running", refresh_id: "vix_new" } }),
    );
    fireEvent.click(refreshButton("VIX 다시 받기"));
    await flush();
    if (deliverOld) delayedOld.resolve(oldFailure);
    await flush();
    expect(text()).toContain("VIX 다시 받는 중…");
    expect(refreshButton("VIX 다시 받기")).toBeDisabled();
    const calls = fetchMarketRefreshStatus.mock.calls.length;
    await tick(4000);
    expect(fetchMarketRefreshStatus.mock.calls.length - calls).toBe(1);
    // 새 재시도의 결과는 그대로 읽힌다.
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ cooldown_remaining_seconds: 3600, vix_retry: { needed: false, status: "completed", refresh_id: "vix_new", vix_as_of_date: "2026-10-13" } }),
    );
    await tick(4000);
    expect(text()).toContain("VIX 다시 받기 완료(기준일 2026-10-13)");
  });

  it("이전 확인이 상한(120회)에 닿은 뒤의 늦은 오류 응답도 새 재시도를 끝내지 않는다", async () => {
    fetchMarketRefreshStatus.mockResolvedValue(status({ cooldown_remaining_seconds: 3600, vix_retry: NEEDED }));
    postMarketRefresh.mockResolvedValueOnce({ status: "accepted", refresh_id: "vix_a", message: "", cooldown_remaining_seconds: 3600 });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(refreshButton("VIX 다시 받기"));
    await flush();
    const firstOld = deferred<ReturnType<typeof status>>();
    // 첫 요청은 오래 걸리고, 나머지는 표식만 남은 상태(이 재시도 id 의 끝 아님)를 준다.
    fetchMarketRefreshStatus.mockReturnValueOnce(firstOld.promise);
    for (let i = 0; i < 120; i++) await tick(4000);
    expect(text()).toContain("확인 필요: 상태 확인 시간이 너무 길어졌습니다");
    postMarketRefresh.mockResolvedValueOnce({ status: "accepted", refresh_id: "vix_b", message: "", cooldown_remaining_seconds: 3600 });
    fireEvent.click(refreshButton("VIX 다시 받기"));
    await flush();
    firstOld.reject(new Error("late network error"));
    await flush();
    expect(text()).toContain("VIX 다시 받는 중…");
    const calls = fetchMarketRefreshStatus.mock.calls.length;
    await tick(4000);
    expect(fetchMarketRefreshStatus.mock.calls.length - calls).toBe(1);
  });

  it("화면을 열 때 읽은 상태가 늦게 와도 더 새 상태(전체 갱신 끝)를 덮지 않는다", async () => {
    const mountStatus = deferred<ReturnType<typeof status>>();
    fetchMarketRefreshStatus.mockReturnValueOnce(mountStatus.promise);
    postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "r40", message: "", cooldown_remaining_seconds: 0 });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(refreshButton("최신 시장 데이터 갱신"));
    await flush();
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ refresh_id: "r40", error_summary: "시장 불안 지표(VIX)를 갱신하지 못했습니다", cooldown_remaining_seconds: 21600, vix_retry: { ...NEEDED, refresh_id: "r40" } }),
    );
    await tick();
    expect(refreshButton("VIX 다시 받기")).toBeTruthy();
    mountStatus.resolve(status({ status: "idle", cooldown_remaining_seconds: 0, vix_retry: null }));
    await flush();
    expect(refreshButton("VIX 다시 받기")).toBeTruthy();
  });

  it("화면을 열 때 읽은 '진행 중' 상태가 늦게 와도, 그 사이 이어받은 다른 재시도를 바꿔 따라가지 않는다", async () => {
    const mountStatus = deferred<ReturnType<typeof status>>();
    fetchMarketRefreshStatus.mockReturnValueOnce(mountStatus.promise);
    postMarketRefresh.mockResolvedValue({ status: "vix_retry_running", refresh_id: "vix_Y", message: "", cooldown_remaining_seconds: 3600 });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(refreshButton("최신 시장 데이터 갱신"));
    await flush();
    expect(text()).toContain("VIX 다시 받는 중…");
    mountStatus.resolve(status({ cooldown_remaining_seconds: 3600, vix_retry: { needed: false, status: "running", refresh_id: "vix_X" } }));
    await flush();
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ cooldown_remaining_seconds: 3600, vix_retry: { needed: false, status: "completed", refresh_id: "vix_Y", vix_as_of_date: "2026-10-13" } }),
    );
    await tick(4000);
    expect(text()).toContain("VIX 다시 받기 완료(기준일 2026-10-13)");
  });

  it.each(["resolve", "reject"] as const)("전체 갱신: 실패 뒤 다시 누른 새 갱신을 이전 상태 요청의 늦은 응답(%s)이 끝내지 않는다", async (late) => {
    postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "rA", message: "", cooldown_remaining_seconds: 0 });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(refreshButton("최신 시장 데이터 갱신"));
    await flush();
    const delayedOld = deferred<ReturnType<typeof status>>();
    const oldFailed = status({ status: "failed", refresh_id: "rA", error_summary: "all_price_fetches_failed" });
    fetchMarketRefreshStatus.mockReturnValueOnce(delayedOld.promise).mockResolvedValueOnce(oldFailed);
    await tick(4000);
    await tick(4000);
    expect(text()).toContain("실패: all_price_fetches_failed");
    postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "rB", message: "", cooldown_remaining_seconds: 0 });
    fetchMarketRefreshStatus.mockResolvedValue(status({ status: "running", refresh_id: "rB" }));
    fireEvent.click(refreshButton("최신 시장 데이터 갱신"));
    await flush();
    if (late === "resolve") delayedOld.resolve(oldFailed);
    else delayedOld.reject(new Error("late network error"));
    await flush();
    expect(text()).toContain("갱신 중...");
    expect(text()).not.toContain("all_price_fetches_failed");
    expect(text()).not.toContain("late network error");
    const calls = fetchMarketRefreshStatus.mock.calls.length;
    await tick(4000);
    expect(fetchMarketRefreshStatus.mock.calls.length - calls).toBe(1);
    expect(text()).toContain("갱신 중...");
  });
});

describe("r1 검토 반영 — 끝난 뒤 다시 읽기 · 화면 떠난 뒤 POST 응답 (POC5-12)", () => {
  // 진짜 fetchMarketTopnLatest(진행 중 공유)를 쓰고 fetch 만 바꾼다. hold 가 켜지면 다음 TOP N GET 을 붙잡는다.
  function realTopnServer() {
    vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://api.test");
    const held: Array<{ resolve: (asof: string) => void }> = [];
    const server = { asof: "2026-10-12", hold: false, topnCalls: 0, held };
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        const ok = (body: unknown) => ({ ok: true, status: 200, text: async () => JSON.stringify(body) });
        if (!String(url).includes("/market/topn/latest")) return Promise.resolve(ok({ items: [] }));
        server.topnCalls += 1;
        if (server.hold) {
          server.hold = false;
          return new Promise((res) => held.push({ resolve: (asof) => res(ok(topn(asof))) }));
        }
        return Promise.resolve(ok(topn(server.asof)));
      }),
    );
    fetchMarketTopnLatest.mockImplementation(actualApi.fetchMarketTopnLatest as (...a: unknown[]) => unknown);
    return server;
  }

  it("전체 갱신이 끝난 뒤 다시 읽기는 갱신 전에 보낸 같은 조건 요청에 붙지 않고 새로 보낸다", async () => {
    const server = realTopnServer();
    postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "r50", message: "", cooldown_remaining_seconds: 0 });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    fetchMarketRefreshStatus.mockResolvedValue(status({ status: "running", refresh_id: "r50" }));
    fireEvent.click(refreshButton("최신 시장 데이터 갱신"));
    await flush();
    server.hold = true; // 갱신 중 필터를 바꿔 보낸 요청이 아직 안 끝남(갱신 전 자료)
    fireEvent.click(screen.getByLabelText("레버리지 제외"));
    await flush();
    const before = server.topnCalls;
    server.asof = "2026-10-14"; // 갱신이 끝난 뒤 서버 자료
    fetchMarketRefreshStatus.mockResolvedValue(status({ refresh_id: "r50" }));
    await tick();
    expect(server.topnCalls - before).toBe(1);
    server.held[0].resolve("2026-10-12"); // 갱신 전 요청이 늦게 끝남 → 무시
    await flush();
    expect(text()).toContain("갱신 완료.");
    expect(text()).toContain("2026-10-14");
    expect(text()).not.toContain("2026-10-12");
  });

  it("'VIX 다시 받기'가 끝난 뒤 다시 읽기도 그 전에 보낸 요청에 붙지 않는다", async () => {
    const server = realTopnServer();
    fetchMarketRefreshStatus.mockResolvedValue(status({ cooldown_remaining_seconds: 3600, vix_retry: NEEDED }));
    postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "vix_retry_60", message: "", cooldown_remaining_seconds: 3600 });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(refreshButton("VIX 다시 받기"));
    await flush();
    server.hold = true;
    fireEvent.click(screen.getByLabelText("레버리지 제외"));
    await flush();
    const before = server.topnCalls;
    server.asof = "2026-10-14";
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ cooldown_remaining_seconds: 3600, vix_retry: { needed: false, status: "completed", refresh_id: "vix_retry_60", vix_as_of_date: "2026-10-13" } }),
    );
    await tick();
    expect(server.topnCalls - before).toBe(1);
    server.held[0].resolve("2026-10-12");
    await flush();
    expect(text()).toContain("VIX 다시 받기 완료(기준일 2026-10-13)");
    expect(text()).toContain("2026-10-14");
  });

  it.each([
    ["accepted", { status: "accepted", refresh_id: "r70", message: "", cooldown_remaining_seconds: 0 }],
    ["vix_retry_running", { status: "vix_retry_running", refresh_id: "vix_retry_70", message: "", cooldown_remaining_seconds: 0 }],
  ])("POST 응답(%s)이 화면을 떠난 뒤 오면 상태 확인을 새로 열지 않는다", async (_label, response) => {
    const post = deferred<Record<string, unknown>>();
    postMarketRefresh.mockReturnValue(post.promise);
    const view = render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(refreshButton("최신 시장 데이터 갱신"));
    await flush();
    view.unmount();
    const calls = fetchMarketRefreshStatus.mock.calls.length;
    post.resolve(response);
    await flush();
    await tick(4100);
    await tick(4100);
    expect(fetchMarketRefreshStatus.mock.calls.length).toBe(calls);
  });
});

describe("시장 GET 응답 처리 (POC5-12)", () => {
  it("개발 모드 이중 실행(StrictMode)에도 같은 입력 서버 GET 은 1회", async () => {
    vi.useRealTimers();
    vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://api.test");
    const fetchStub = vi.fn(async (url: string) => {
      const body = String(url).includes("/market/topn/latest") ? topn() : {};
      return { ok: true, status: 200, text: async () => JSON.stringify(body) };
    });
    vi.stubGlobal("fetch", fetchStub);
    fetchMarketTopnLatest.mockImplementation(
      actualApi.fetchMarketTopnLatest as (...a: unknown[]) => unknown,
    );
    render(
      <StrictMode>
        <MarketDiscoveryView onNavigate={() => undefined} />
      </StrictMode>,
    );
    expect(await screen.findByText("2026-10-12")).toBeTruthy();
    expect(fetchMarketTopnLatest.mock.calls.length).toBeGreaterThanOrEqual(2); // 화면은 두 번 부름
    const topnCalls = fetchStub.mock.calls.filter((c) => String(c[0]).includes("/market/topn/latest"));
    expect(topnCalls).toHaveLength(1); // 서버는 한 번
  });

  it("늦게 온 이전 요청 응답은 무시한다(마지막 요청 결과만)", async () => {
    const first = deferred<ReturnType<typeof topn>>();
    const second = deferred<ReturnType<typeof topn>>();
    fetchMarketTopnLatest.mockReset();
    fetchMarketTopnLatest.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    render(
      <StrictMode>
        <MarketDiscoveryView onNavigate={() => undefined} />
      </StrictMode>,
    );
    await flush();
    second.resolve(topn("2026-10-14"));
    await flush();
    first.resolve(topn("2026-10-01"));
    await flush();
    expect(text()).toContain("2026-10-14");
    expect(text()).not.toContain("2026-10-01");
  });

  it("화면을 떠난 뒤 온 응답은 화면 갱신 없이 버려진다(React 기본 동작 · 오류 없음)", async () => {
    const pending = deferred<ReturnType<typeof topn>>();
    fetchMarketTopnLatest.mockReset().mockReturnValue(pending.promise);
    const errors = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const view = render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    view.unmount();
    pending.resolve(topn("2026-10-14"));
    await flush();
    expect(errors).not.toHaveBeenCalled();
    errors.mockRestore();
  });

  it("같은 입력 재조회가 실패하면 받은 자료와 기준일을 두고 오류 한 줄", async () => {
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ cooldown_remaining_seconds: 3600, vix_retry: NEEDED }),
    );
    postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "vix_retry_5", message: "", cooldown_remaining_seconds: 3600 });
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    expect(text()).toContain("2026-10-12");
    fetchMarketTopnLatest.mockRejectedValueOnce(
      new (actualApi.ApiRequestError as new (m: string, s: number, b: unknown) => Error)(
        "요청 시간 초과: GET /market/topn/latest (10000ms)",
        0,
        null,
      ),
    );
    fireEvent.click(refreshButton("VIX 다시 받기"));
    await flush();
    fetchMarketRefreshStatus.mockResolvedValue(
      status({
        cooldown_remaining_seconds: 3600,
        vix_retry: { needed: false, status: "completed", refresh_id: "vix_retry_5", vix_as_of_date: "2026-10-13" },
      }),
    );
    await tick();
    expect(fetchMarketTopnLatest).toHaveBeenCalledTimes(2);
    expect(text()).toContain(
      "시장 자료를 다시 불러오지 못해 이전에 받은 자료(기준일 2026-10-12)를 표시합니다",
    );
    expect(text()).toContain("요청 시간 초과");
    expect(screen.getByText("카드")).toBeTruthy(); // 결과 영역 그대로
  });

  it("입력을 바꾼 뒤 실패하면 결과 영역을 숨기고 오류 카드(이전 조건 자료를 새 결과처럼 보이지 않음)", async () => {
    render(<MarketDiscoveryView onNavigate={() => undefined} />);
    await flush();
    expect(screen.getByText("카드")).toBeTruthy();
    fetchMarketTopnLatest.mockRejectedValueOnce(new Error("down"));
    fireEvent.click(screen.getByLabelText("인버스 제외"));
    await flush();
    expect(screen.queryByText("카드")).toBeNull();
    expect(text()).toContain("알 수 없는 오류: down");
    expect(text()).not.toContain("이전에 받은 자료");
  });
});
