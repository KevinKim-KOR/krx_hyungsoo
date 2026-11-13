// POC5-12 'VIX 다시 받기' 흐름 — POC6-29 에서 「요즘 잘 오르는 ETF」 갱신 버튼 옆에서 「오늘의 투자 점검」
// [시장 근거와 다른 변화 보기](지금 번호 ①)로 옮겼다. 같은 hook(`useMarketVixRetry`)을 A 의 실제 조합(`useTodayRefresh`)으로 본다
// (보관된 `MarketDiscoveryVixRetry.test.tsx` 의 버튼 흐름 + POC6-29 독립 검토 지적).
// - 대기 중 · 표식 → [VIX 다시 받기] · scope=vix · 같은 id 의 끝난 결과만 · 빠른 완료 · 실패 · 해당 없음.
// - 성공 뒤 이 화면이 읽은 시장 자료(시장 판정 · 시장 흐름 · 보유 근거 · 잘 오르는 ETF · 보유 하락 판정)를 다시 읽는다.
// - 다시 받기가 도는 동안만 [최신 자료 갱신]이 막히고 끝나면 풀린다(들어올 때 이미 도는 경우 포함).
// - 화면을 떠난 뒤 도착한 묶음 작업 응답은 시장 상태 확인을 새로 시작하지 않는다.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, fireEvent, within } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import { detailResponse, summaryOk } from "@/lib/etfCompareTestFixtures";
import { quickOk } from "@/lib/quickQuotesTestFixtures";
import { morningOk, shortOk } from "@/lib/morningTestFixtures";
import { flowWith } from "@/lib/todayMarketTestFixtures";

const fetchMarketTopnLatest = vi.fn();
const fetchEnrichedHoldings = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
const fetchNavDiscountLatest = vi.fn();
const fetchBenchmarkSeries = vi.fn();
const fetchOciStartupStatus = vi.fn();
const postMarketRefresh = vi.fn();
const fetchMarketRefreshStatus = vi.fn();
const fetchMarketFlowContext = vi.fn();
const fetchForwardComparison = vi.fn();
const fetchLedgerLatestByKind = vi.fn();
const fetchEtfCompareSummary = vi.fn();
const postRefreshAll = vi.fn();
const fetchRefreshAllStatus = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchMarketTopnLatest: (...a: unknown[]) => fetchMarketTopnLatest(...a),
  fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
  fetchHoldingsMarketEvidence: (...a: unknown[]) => fetchHoldingsMarketEvidence(...a),
  fetchNavDiscountLatest: (...a: unknown[]) => fetchNavDiscountLatest(...a),
  fetchBenchmarkSeries: (...a: unknown[]) => fetchBenchmarkSeries(...a),
  fetchOciStartupStatus: (...a: unknown[]) => fetchOciStartupStatus(...a),
  postMarketRefresh: (...a: unknown[]) => postMarketRefresh(...a),
  fetchMarketRefreshStatus: (...a: unknown[]) => fetchMarketRefreshStatus(...a),
}));
vi.mock("@/lib/api/marketFlow", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchMarketFlowContext: (...a: unknown[]) => fetchMarketFlowContext(...a),
}));
vi.mock("@/lib/api/mlForwardComparison", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchForwardComparison: (...a: unknown[]) => fetchForwardComparison(...a),
}));
vi.mock("@/lib/api/decisionLedger", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchLedgerLatestByKind: (...a: unknown[]) => fetchLedgerLatestByKind(...a),
}));
vi.mock("@/lib/api/etfCompare", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchEtfCompareSummary: (...a: unknown[]) => fetchEtfCompareSummary(...a),
}));
vi.mock("@/lib/api/refreshAll", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  postRefreshAll: (...a: unknown[]) => postRefreshAll(...a),
  fetchRefreshAllStatus: (...a: unknown[]) => fetchRefreshAllStatus(...a),
}));

// POC6-29 보완 — 빠른 시세 저장값 · KODEX 200 상세(시장 판정 문장 기준 · 갱신 전후 대조)도 가짜로 둔다.
const fetchQuickQuotes = vi.fn();
const fetchEtfDetail = vi.fn();
vi.mock("@/lib/api/quickQuotes", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchQuickQuotes: (...a: unknown[]) => fetchQuickQuotes(...a),
}));
const fetchMorningBasis = vi.fn();
const fetchShortFlows = vi.fn();
vi.mock("@/lib/api/morningBasis", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/morningBasis")>()),
  fetchMorningBasis: (...a: unknown[]) => fetchMorningBasis(...a),
}));
vi.mock("@/lib/api/shortFlows", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/shortFlows")>()),
  fetchShortFlows: (...a: unknown[]) => fetchShortFlows(...a),
}));
vi.mock("@/lib/api/etfDetail", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchEtfDetail: (...a: unknown[]) => fetchEtfDetail(...a),
}));

import TodayInvestmentCheckView from "../TodayInvestmentCheckView";

function market() {
  return {
    status: "ok",
    asof: "2026-11-06",
    basis: "one_month",
    order: "desc",
    n: 10,
    filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
    candidates: [],
    market_context: {
      status: "ok",
      asof: "2026-11-06",
      regime_label: "하락장",
      regime_code: "bear",
      regime_reasons: [],
      kodex200: { status: "ok" },
      kospi: { status: "ok", display_state: "ok", as_of_date: "2026-11-06", return_20d_pct: -2, return_60d_pct: -3 },
      warnings: [],
    },
    market_risk_reference: {
      kodex200: { availability: "available", as_of_date: "2026-11-06", recent_20d_series: [] },
      vix: { availability: "available", as_of_date: "2026-11-05", recent_20d_series: [], freshness: { state: "fresh" } },
    },
  };
}

function status(over: Record<string, unknown> = {}) {
  return { status: "completed", refresh_id: "r1", cooldown_remaining_seconds: 0, ...over };
}
const NEEDED = { needed: true, status: "needed", refresh_id: "r1", error_summary: "시장 불안 지표(VIX)를 갱신하지 못했습니다" };
const IDLE_ALL = { state: "idle", job_id: null, started_at: null, finished_at: null, steps: { holdings: null, market: null } };

function prime() {
  fetchQuickQuotes.mockReset().mockResolvedValue(quickOk());
  fetchMorningBasis.mockReset().mockResolvedValue(morningOk());
  fetchShortFlows.mockReset().mockResolvedValue(shortOk());
  fetchEtfDetail.mockReset().mockImplementation((ts: string[]) => Promise.resolve(detailResponse(ts)));
  fetchMarketTopnLatest.mockReset().mockResolvedValue(market());
  fetchEnrichedHoldings.mockReset().mockResolvedValue({ items: [{ ticker: "B00001", name: "보유", market_weight_pct: 10, price_missing: false }] });
  fetchHoldingsMarketEvidence.mockReset().mockResolvedValue({ status: "ok", summary: { constituents_unavailable_count: 0, evidence_unavailable_count: 0, nav_discount_unavailable_count: 0 }, holdings: [], price_basis: { reference_date: "2026-11-06", date_mismatch: [] }, warnings: [] });
  fetchNavDiscountLatest.mockReset().mockResolvedValue({ status: "ok", summary: { unavailable_count: 0, failed_count: 0 } });
  fetchBenchmarkSeries.mockReset().mockResolvedValue({ ticker: "KOSPI", availability: "AVAILABLE", series: [{ date: "2026-11-06", price: 5000 }] });
  fetchOciStartupStatus.mockReset().mockResolvedValue({ reachable: true, overall: "OPERATING", summary_line: "OCI", jobs: [], note: "" });
  fetchMarketFlowContext.mockReset().mockResolvedValue(flowWith());
  fetchForwardComparison.mockReset().mockResolvedValue({ status: "NO_RECORDS", label: "연구용" });
  fetchLedgerLatestByKind.mockReset().mockRejectedValue(new Error("x"));
  fetchEtfCompareSummary.mockReset().mockResolvedValue(summaryOk());
  postMarketRefresh.mockReset();
  fetchMarketRefreshStatus.mockReset().mockResolvedValue(status({ status: "idle" }));
  postRefreshAll.mockReset().mockResolvedValue(IDLE_ALL);
  fetchRefreshAllStatus.mockReset().mockResolvedValue(IDLE_ALL);
}

async function flush() {
  await act(async () => {
    for (let i = 0; i < 12; i++) await Promise.resolve();
  });
}
async function tick(ms = 4100) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
  await flush();
}

const vixSection = () => screen.getByLabelText("VIX");
const vixButton = () => within(vixSection()).queryByRole("button", { name: "VIX 다시 받기" });
const vixLine = () => screen.queryByTestId("tc-vix-retry-line")?.textContent ?? null;
const allButton = () => screen.getAllByRole("button", { name: /자료 갱신/ })[0];
const holdCard = () => screen.getByLabelText("보유 점검").textContent ?? "";

beforeEach(() => {
  __resetQueryCache();
  vi.useFakeTimers();
  prime();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("'VIX 다시 받기'(오늘 점검 ②)", () => {
  it("대기 중 · 표식 → [VIX 다시 받기] · scope=vix · 다른 id 결과는 무시 · 같은 id 완료 → 이 화면 시장 자료를 다시 읽고 카드는 멈추지 않음", async () => {
    fetchMarketRefreshStatus.mockResolvedValue(status({ cooldown_remaining_seconds: 3600, vix_retry: NEEDED }));
    postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "vix_retry_1", message: "", cooldown_remaining_seconds: 3600 });
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    expect(holdCard()).toContain("보유 1종목");
    const before = {
      market: fetchMarketTopnLatest.mock.calls.length,
      summary: fetchEtfCompareSummary.mock.calls.length,
      flow: fetchMarketFlowContext.mock.calls.length,
      evidence: fetchHoldingsMarketEvidence.mock.calls.length,
    };
    fireEvent.click(vixButton() as HTMLElement);
    await flush();
    expect(postMarketRefresh).toHaveBeenCalledWith("vix");
    expect(vixLine()).toBe("VIX 다시 받는 중…");
    // 다시 받는 동안 [최신 자료 갱신]은 막힌다 · 머리 줄은 진행 중 안내(거절이라고 하지 않음).
    expect(allButton()).toBeDisabled();
    expect(screen.getByTestId("tc-market-result").textContent).toContain("VIX 다시 받기가 진행 중입니다");
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ cooldown_remaining_seconds: 3600, vix_retry: { needed: false, status: "completed", refresh_id: "vix_retry_0", vix_as_of_date: "2026-10-09" } }),
    );
    await tick();
    expect(vixLine()).toBe("VIX 다시 받는 중…");
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ cooldown_remaining_seconds: 3600, vix_retry: { needed: false, status: "completed", refresh_id: "vix_retry_1", vix_as_of_date: "2026-11-06" } }),
    );
    await tick();
    expect(vixLine()).toBe("VIX 다시 받기 완료(기준일 2026-11-06)");
    expect(fetchMarketTopnLatest.mock.calls.length).toBe(before.market + 1);
    expect(fetchEtfCompareSummary.mock.calls.length).toBe(before.summary + 1);
    expect(fetchMarketFlowContext.mock.calls.length).toBeGreaterThan(before.flow);
    expect(fetchHoldingsMarketEvidence.mock.calls.length).toBe(before.evidence + 1);
    await flush();
    // 검토 지적 — 지운 자료를 다시 읽어 '불러오는 중'에 멈추지 않는다 · 버튼이 풀린다.
    expect(holdCard()).toContain("보유 1종목");
    expect(holdCard()).not.toContain("불러오는 중");
    expect(screen.getByTestId("tc-cand-top")).toBeTruthy();
    expect(allButton()).not.toBeDisabled();
    expect(screen.queryByTestId("tc-market-result")).toBeNull();
  });

  it("첫 상태 확인 전에 이미 끝났어도 결과가 보인다(빠른 완료)", async () => {
    fetchMarketRefreshStatus.mockResolvedValue(status({ cooldown_remaining_seconds: 3600, vix_retry: NEEDED }));
    postMarketRefresh.mockImplementation(async () => {
      fetchMarketRefreshStatus.mockResolvedValue(
        status({ cooldown_remaining_seconds: 3600, vix_retry: { needed: false, status: "completed", refresh_id: "vix_retry_2", vix_as_of_date: "2026-11-06" } }),
      );
      return { status: "accepted", refresh_id: "vix_retry_2", message: "", cooldown_remaining_seconds: 3600 };
    });
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(vixButton() as HTMLElement);
    await flush();
    await tick();
    expect(vixLine()).toBe("VIX 다시 받기 완료(기준일 2026-11-06)");
  });

  it("다시 받기 실패 → '확인 필요: …' · 버튼은 그대로 · 시장 자료 다시 읽기 없음 · [최신 자료 갱신] 풀림", async () => {
    fetchMarketRefreshStatus.mockResolvedValue(status({ cooldown_remaining_seconds: 3600, vix_retry: NEEDED }));
    postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "vix_retry_3", message: "", cooldown_remaining_seconds: 3600 });
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    const markets = fetchMarketTopnLatest.mock.calls.length;
    fireEvent.click(vixButton() as HTMLElement);
    await flush();
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ cooldown_remaining_seconds: 3600, vix_retry: { ...NEEDED, status: "failed", refresh_id: "vix_retry_3" } }),
    );
    await tick();
    expect(vixLine()).toBe("확인 필요: 시장 불안 지표(VIX)를 갱신하지 못했습니다");
    expect(vixButton()).not.toBeDisabled();
    expect(fetchMarketTopnLatest.mock.calls.length).toBe(markets);
    expect(allButton()).not.toBeDisabled();
  });

  it.each([
    ["대기 끝(0) · 표식 있음", { cooldown_remaining_seconds: 0, vix_retry: NEEDED }],
    ["대기 중 · 표식 없음", { cooldown_remaining_seconds: 3600, vix_retry: null }],
    ["대기 중 · 해제(cleared)", { cooldown_remaining_seconds: 3600, vix_retry: { needed: false, status: "cleared", refresh_id: "x" } }],
  ])("%s → [VIX 다시 받기] 없음", async (_label, over) => {
    fetchMarketRefreshStatus.mockResolvedValue(status(over));
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    expect(vixButton()).toBeNull();
  });

  it("해당 없음(not_needed) 응답은 안내 한 줄 · 표식을 다시 읽어 버튼을 거둔다", async () => {
    fetchMarketRefreshStatus.mockResolvedValue(status({ cooldown_remaining_seconds: 3600, vix_retry: NEEDED }));
    postMarketRefresh.mockImplementation(async () => {
      fetchMarketRefreshStatus.mockResolvedValue(status({ cooldown_remaining_seconds: 3600, vix_retry: { needed: false, status: "cleared" } }));
      return { status: "not_needed", refresh_id: null, message: "다시 받을 VIX 실패 기록이 없습니다.", cooldown_remaining_seconds: 3600 };
    });
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(vixButton() as HTMLElement);
    await flush();
    expect(vixLine()).toBe("다시 받을 VIX 실패 기록이 없습니다.");
    expect(vixButton()).toBeNull();
  });

  it("들어올 때 이미 다시 받기가 도는 중이면 그 id 로 따라가고, 끝나면 [최신 자료 갱신]이 풀린다(검토 지적)", async () => {
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ cooldown_remaining_seconds: 3600, vix_retry: { needed: true, status: "running", refresh_id: "v7" } }),
    );
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    expect(vixLine()).toBe("VIX 다시 받는 중…");
    expect(allButton()).toBeDisabled();
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ cooldown_remaining_seconds: 3600, vix_retry: { needed: false, status: "completed", refresh_id: "v7", vix_as_of_date: "2026-11-06" } }),
    );
    await tick();
    expect(vixLine()).toBe("VIX 다시 받기 완료(기준일 2026-11-06)");
    expect(allButton()).not.toBeDisabled();
  });

  it("[최신 자료 갱신]의 시장 단계가 '다시 받기 진행 중'으로 거절되면 그 다시 받기를 따라가고 끝나면 풀린다", async () => {
    postRefreshAll.mockResolvedValue({
      state: "done",
      job_id: "j1",
      started_at: "2026-11-09T00:00:00Z",
      finished_at: "2026-11-09T00:00:05Z",
      steps: {
        holdings: { status: "done", ok_count: 1, fail_count: 0 },
        market: { status: "vix_retry_running", refresh_id: "v8", message: "VIX 다시 받기가 진행 중입니다.", cooldown_remaining_seconds: 3600 },
      },
    });
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(allButton());
    await flush();
    expect(vixLine()).toBe("VIX 다시 받는 중…");
    expect(screen.getByTestId("tc-market-result").textContent).toContain("VIX 다시 받기가 진행 중입니다");
    expect(screen.getByTestId("tc-market-result").textContent).not.toContain("실패");
    expect(allButton()).toBeDisabled();
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ cooldown_remaining_seconds: 3600, vix_retry: { needed: false, status: "completed", refresh_id: "v8", vix_as_of_date: "2026-11-06" } }),
    );
    await tick();
    expect(vixLine()).toBe("VIX 다시 받기 완료(기준일 2026-11-06)");
    expect(allButton()).not.toBeDisabled();
  });

  it("전체 갱신이 VIX 만 실패하고 끝나면 같은 화면에서 바로 [VIX 다시 받기]", async () => {
    postRefreshAll.mockResolvedValue({
      state: "done",
      job_id: "j2",
      started_at: "2026-11-09T00:00:00Z",
      finished_at: "2026-11-09T00:00:05Z",
      steps: { holdings: { status: "done", ok_count: 1, fail_count: 0 }, market: { status: "accepted", refresh_id: "r9", message: "", cooldown_remaining_seconds: 0 } },
    });
    fetchMarketRefreshStatus.mockResolvedValue(status({ status: "running", refresh_id: "r9" }));
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    fetchMarketRefreshStatus.mockResolvedValue(status({ status: "idle" }));
    fireEvent.click(allButton());
    await flush();
    fetchMarketRefreshStatus.mockResolvedValue(
      status({ refresh_id: "r9", error_summary: "시장 불안 지표(VIX)를 갱신하지 못했습니다", cooldown_remaining_seconds: 21600, vix_retry: { ...NEEDED, refresh_id: "r9" } }),
    );
    await tick();
    await flush();
    expect(vixButton()).toBeTruthy();
  });
});

describe("화면을 떠난 뒤 도착한 응답(검토 지적)", () => {
  it("묶음 작업 시작 응답이 화면을 떠난 뒤 오면 시장 상태 확인을 새로 시작하지 않는다", async () => {
    let resolve!: (v: unknown) => void;
    postRefreshAll.mockImplementation(() => new Promise((r) => (resolve = r)));
    const { unmount } = render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(allButton());
    await flush();
    unmount();
    const polls = fetchMarketRefreshStatus.mock.calls.length;
    await act(async () =>
      resolve({
        state: "done",
        job_id: "j3",
        started_at: "2026-11-09T00:00:00Z",
        finished_at: "2026-11-09T00:00:05Z",
        steps: { holdings: { status: "done", ok_count: 1, fail_count: 0 }, market: { status: "accepted", refresh_id: "r3", message: "", cooldown_remaining_seconds: 0 } },
      }),
    );
    await flush();
    await tick(20000);
    expect(fetchMarketRefreshStatus.mock.calls.length).toBe(polls);
  });
});
