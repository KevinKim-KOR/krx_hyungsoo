// POC6-29 보완(RESULT 판정 §1 · §2 · 보완 PLAN 판정 Q-R1 · Q-R2 · Q-R3 · Q-R6 · '구현에서 확인할 세 가지' 1 · 2) —
// 「오늘의 투자 점검」 '지금 시장'(빠른 시세 3칸 · 흐름 문장)과 [최신 자료 갱신] ⓪ 빠른 시세 · 대기 · 같은 거래일 다시 받음.
// 실제 화면 조합(TodayInvestmentCheckView · useTodayRefresh)을 가짜 응답으로 본다. 네트워크 · 실제 자료 없음.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, fireEvent, within } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import { detailItem, detailResponse, summaryOk } from "@/lib/etfCompareTestFixtures";
import { QUICK_FETCHED, quickEmpty, quickOk } from "@/lib/quickQuotesTestFixtures";
import { morningMissing, morningOk, shortOk } from "@/lib/morningTestFixtures";
import { setStartedRefreshId } from "@/lib/marketRefreshMemory";
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


// 시장 판정 근거 · VIX 값이 있는 응답(흐름 문장 확인용 · 값 = 2026-11-12 격리 작업본 저장값과 같은 모양)
function marketWithReasons() {
  const m = market();
  return {
    ...m,
    market_context: {
      ...m.market_context,
      // 판정이 쓴 KODEX 200 끝일 · 종가 = 아래 상세 끝일 행(11/12 · 84,240) — 같은 저장값일 때만 저장 시점이 붙는다(검증자 F4 · F7)
      asof: "2026-11-12",
      kodex200: { status: "ok", close: 84240 },
      regime_reasons: ["KODEX200 20거래일 수익률 -2.14%", "현재가가 20일 이동평균 아래"],
      regime_streak: { streak_days: 25, at_least: false },
    },
    market_risk_reference: {
      ...m.market_risk_reference,
      vix: { ...m.market_risk_reference.vix, close: 17.49, change_1d_pct: -10.12, change_5d_pct: 5.3, as_of_date: "2026-11-11" },
    },
  };
}

// KODEX 200 상세 — 재현 사례(09:53 장중 85,045원 → 15:56 마감 뒤 저장 84,240원 · 같은 거래일 11/12).
function kodexAt(state: "intraday" | "after_close", fetched: string, close: number) {
  return detailResponse([], {
    end_date: "2026-11-12",
    items: [
      detailItem("069500", {
        end_price: { date: "2026-11-12", state, fetched_at_kst: fetched },
        daily: { status: "ok", value: 0.6, start: "2026-11-11", end: "2026-11-12", start_close: 84540, end_close: close, reason: null },
      }),
    ],
  });
}
const KODEX_0953 = kodexAt("intraday", "2026-11-12T09:53:21+09:00", 85045);
const KODEX_1556 = kodexAt("after_close", "2026-11-12T15:56:59+09:00", 84240);

const tiles = () => screen.getAllByTestId("tc-now-quote").map((t) => t.textContent ?? "");
const allButton = () => screen.getAllByRole("button", { name: /자료 갱신/ })[0];
const ALL_RUNNING = {
  state: "running",
  job_id: "job1",
  started_at: "2026-11-12T06:56:13Z",
  finished_at: null,
  steps: { quick: { status: "running" }, holdings: { status: "pending" }, market: { status: "pending" } },
};
function allAfterQuick(quick: Record<string, unknown>, rest: Record<string, unknown> = {}) {
  return {
    ...ALL_RUNNING,
    steps: { quick, holdings: { status: "running" }, market: { status: "pending" } },
    ...rest,
  };
}
const QUICK_DONE = {
  status: "done",
  fetched_at: QUICK_FETCHED,
  items: { KOSPI: { status: "updated" }, KOSDAQ: { status: "updated" }, "069500": { status: "updated" } },
};

beforeEach(() => {
  __resetQueryCache();
  prime();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("보완 R1 — 「시장 흐름」 맨 위 '지금 시장'(빠른 시세 3칸 · 흐름 문장)", () => {
  it("화면을 열면 빠른 시세 저장값만 읽는다(외부 조회 · 묶음 작업 없음) · 3칸 = 값 · 등락 · 시세 시각 · 조회 시각 · 장 상태", async () => {
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    expect(fetchQuickQuotes).toHaveBeenCalledTimes(1);
    expect(postRefreshAll).not.toHaveBeenCalled();
    // 보완 2차(§10-2) — 세 칸의 거래일 · 장 상태 · 조회가 같으면 공통 시점은 머리에 한 번 · 칸에는 시각 줄 없음
    expect(screen.getByTestId("tc-now-head").textContent).toBe("11/12 마감 · 네이버 시세 · 마지막 조회 11/12 15:36");
    const [kospi, kosdaq, kodex] = tiles();
    expect(kospi).toContain("코스피");
    expect(kospi).toContain("5,342.73");
    expect(kospi).toContain("-32.63 (-0.61%)");
    expect(kospi).not.toContain("시세 시각");
    expect(kosdaq).toContain("696.53");
    expect(kodex).toContain("84,240원");
    expect(kodex).toContain("-300원 (-0.35%)");
    expect(screen.queryAllByTestId("tc-now-own-time")).toHaveLength(0);
  });

  it("다른 칸만 그 칸에 시각 · 장 상태(공통 시점은 나머지 두 칸 기준)", async () => {
    fetchQuickQuotes.mockResolvedValue(
      quickOk({
        "069500": {
          quote: {
            value: 84500,
            change: -40,
            change_pct: -0.05,
            source_time: "2026-11-12T15:20:00+09:00",
            trade_date: "2026-11-12",
            market_status: "OPEN",
            fetched_at: "2026-11-12T15:20:05+09:00",
          },
          last_attempt: { at: "2026-11-12T15:20:05+09:00", status: "updated", reason: null },
        },
      }),
    );
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    expect(screen.getByTestId("tc-now-head").textContent).toBe("11/12 마감 · 네이버 시세 · 마지막 조회 11/12 15:36");
    const own = screen.getAllByTestId("tc-now-own-time");
    expect(own).toHaveLength(1);
    expect(own[0].textContent).toBe("시세 시각 11/12 15:20 · 조회 11/12 15:20");
    expect(tiles()[2]).toContain("장중");
  });

  // 형수님 결정(2026-11-13 · 검증자 F4 · F7 · F8 · F9) — 당일 판정 값 · 저장 시점은 아침 기준 응답의 today_regime(서버의 같은
  // 한 번 읽기)에서만. 따로 받은 KODEX 200 상세는 어떤 경우에도 판정에 저장 시점을 붙이지 않는다(가격 상세를 일부러 다르게 넣음).
  const ROW_1556 = { date: "2026-11-12", close: 84240, state: "after_close" as const, fetched_at_kst: "2026-11-12T15:56:59+09:00" };
  const ROW_0953 = { date: "2026-11-12", close: 85045, state: "intraday" as const, fetched_at_kst: "2026-11-12T09:53:21+09:00" };
  // F8 재현용 — 같은 날 · 같은 종가 85,045 를 15:56 에 다시 저장(과거 가격만 바뀐 새 저장본)한 가격 상세
  const KODEX_1556_SAME_CLOSE = kodexAt("after_close", "2026-11-12T15:56:59+09:00", 85045);
  // 같은 읽기 응답의 판정(26거래일째)을 시장 판정 응답(25거래일째)과 일부러 다르게 — 어느 출처를 썼는지 화면에서 가려낸다.
  const VERDICT = (days: number) =>
    `당일 판정 — 국내 시장은 하락장(${days}거래일째)입니다. 판정 근거: KODEX200 20거래일 수익률 -2.14% · 현재가가 20일 이동평균 아래.`;
  it.each<[string, "ok" | "unconfirmed" | "absent" | "fail", typeof ROW_1556 | typeof ROW_0953 | null, ReturnType<typeof kodexAt>, string, string, string | null]>([
    ["같은 읽기 · 마감 뒤(상세는 장중이어도 무시)", "ok", ROW_1556, KODEX_0953, `${VERDICT(26)} KODEX 200 11/12 가격(15:56 마감 뒤 저장)`, "11/12 마감 뒤 저장", "FDR 일별 가격 · 11/12 15:56 저장"],
    ["같은 읽기 · 장중(상세는 마감 뒤여도 무시 · F7)", "ok", ROW_0953, KODEX_1556, `${VERDICT(26)} KODEX 200 11/12 가격(09:53 장중 저장)`, "11/12 장중 저장", "FDR 일별 가격 · 11/12 09:53 저장"],
    ["F8 — 상세가 같은 날 · 같은 종가의 다른 저장본(15:56)", "ok", ROW_0953, KODEX_1556_SAME_CLOSE, `${VERDICT(26)} KODEX 200 11/12 가격(09:53 장중 저장)`, "11/12 장중 저장", "FDR 일별 가격 · 11/12 09:53 저장"],
    ["아침 기준 응답에 칸 없음(옛 서버) = 시장 판정 응답 · 날짜만", "absent", null, KODEX_1556, `${VERDICT(25)} KODEX 200 11/12 가격 기준(저장 시점 확인 필요)`, "11/12 저장 시점 확인 필요", null],
    ["아침 기준 읽기 실패 = 시장 판정 응답 · 날짜만", "fail", null, KODEX_1556, `${VERDICT(25)} KODEX 200 11/12 가격 기준(저장 시점 확인 필요)`, "11/12 저장 시점 확인 필요", null],
    ["당일 판정 미확인(이력 부족)", "unconfirmed", ROW_1556, KODEX_1556, "당일 판정 미확인 — KODEX 200 판정 근거 부족(저장 이력)", "11/12 마감 뒤 저장", "FDR 일별 가격 · 11/12 15:56 저장"],
  ])("당일 판정 출처 — %s", async (_t, kind, row, detail, box, cell, src) => {
    const m = marketWithReasons();
    fetchMarketTopnLatest.mockResolvedValue(m);
    fetchEtfDetail.mockResolvedValue(detail);
    const ok = morningOk();
    if (kind === "fail") fetchMorningBasis.mockRejectedValue(new Error("x"));
    else if (kind === "absent") fetchMorningBasis.mockResolvedValue(ok);
    else
      fetchMorningBasis.mockResolvedValue({
        ...ok,
        today_regime:
          kind === "ok"
            ? {
                status: "ok",
                basis_date: row!.date,
                reason: null,
                context: { ...m.market_context, regime_streak: { streak_days: 26, at_least: false }, kodex200: { ...m.market_context.kodex200, close: row!.close } },
                basis_row: row,
              }
            : { status: "unconfirmed", basis_date: row!.date, reason: "KODEX 200 판정 근거 부족(저장 이력)", context: null, basis_row: row },
      });
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    expect(screen.getByTestId("tc-now-regime").textContent).toBe(box);
    const row0 = screen.getByTestId("tc-regime-today");
    const cells = row0.querySelectorAll("td");
    expect(cells[cells.length - 1].textContent).toContain(cell);
    // 표 '당일' 줄의 판정 값도 같은 출처(같은 읽기 = 26거래일째 · 칸 없음 · 실패 = 시장 판정 응답 25거래일째)
    if (kind === "ok") expect(row0.textContent).toContain("하락장 · 26거래일째");
    if (kind === "absent" || kind === "fail") expect(row0.textContent).toContain("하락장 · 25거래일째");
    const pop = within(row0).queryByTestId("tc-src-regime-today")?.querySelector(".tc-src-pop")?.textContent ?? null;
    expect(pop).toBe(src);
  });

  it("검증자 F10 — [요약 다시 읽기]에서 아침 기준만 실패하면 남은 이전 응답의 당일 판정 · 저장 시점을 쓰지 않는다(시장 판정 · 날짜만 + 카드 아래 안내)", async () => {
    const m = marketWithReasons();
    fetchMarketTopnLatest.mockResolvedValue(m);
    fetchMorningBasis.mockResolvedValue({
      ...morningOk(),
      today_regime: {
        status: "ok",
        basis_date: "2026-11-12",
        reason: null,
        context: { ...m.market_context, regime_streak: { streak_days: 26, at_least: false } },
        basis_row: ROW_0953,
      },
    });
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    expect(screen.getByTestId("tc-now-regime").textContent).toContain("하락장(26거래일째)");
    expect(screen.getByTestId("tc-now-regime").textContent).toContain("09:53 장중 저장");
    // [요약 다시 읽기]는 시장 판정(시장 목록)을 다시 읽지 않는다 — 아침 기준만 실패(이전 성공 응답이 캐시에 남음)
    fetchMorningBasis.mockRejectedValue(new Error("x"));
    fireEvent.click(screen.getByRole("button", { name: "요약 다시 읽기" }));
    await flush();
    const cont = screen.queryByRole("button", { name: "이 자료로 계속" });
    if (cont) {
      fireEvent.click(cont);
      await flush();
    }
    expect(fetchMorningBasis).toHaveBeenCalledTimes(2);
    const box = screen.getByTestId("tc-now-regime").textContent ?? "";
    expect(box).toBe(`${VERDICT(25)} KODEX 200 11/12 가격 기준(저장 시점 확인 필요)`);
    expect(box).not.toMatch(/26거래일째|09:53|장중 저장/);
    const row = screen.getByTestId("tc-regime-today");
    expect(row.textContent).toContain("하락장 · 25거래일째");
    expect(row.textContent).not.toMatch(/26거래일째|장중 저장/);
    expect(screen.getByTestId("tc-market-flow").querySelector(".tc-sum-stale")?.textContent).toContain("아침 요약 기준: 다시 읽기 실패");
  });

  it("검증자 F10 — 갱신(③ 전일 자료 보충) 뒤 시장 판정은 새 값 · 아침 기준만 다시 읽기 실패 → 새 시장 판정 · 날짜만(이전 당일 판정 · 09:53 저장 안 남음)", async () => {
    vi.useFakeTimers();
    const m = marketWithReasons();
    fetchMarketTopnLatest.mockResolvedValue(m);
    fetchMorningBasis.mockResolvedValue({
      ...morningOk(),
      today_regime: {
        status: "ok",
        basis_date: "2026-11-12",
        reason: null,
        context: { ...m.market_context, regime_streak: { streak_days: 26, at_least: false } },
        basis_row: ROW_0953,
      },
    });
    postRefreshAll.mockResolvedValue(ALL_RUNNING);
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    expect(screen.getByTestId("tc-now-regime").textContent).toContain("09:53 장중 저장");
    fireEvent.click(allButton());
    await flush();
    const base = {
      ...ALL_RUNNING,
      steps: {
        quick: QUICK_DONE,
        holdings: { status: "done", ok_count: 1, fail_count: 0 },
        market: { status: "skipped_cooldown", cooldown_remaining_seconds: 1380, next_available_at: "2026-11-12T12:59:47Z", message: "" },
      },
    };
    // ③ 이 끝나면 시장 판정 · 아침 기준을 다시 읽는다 — 시장 판정 = 상승장(3거래일째) · 아침 기준 = 실패
    fetchMarketTopnLatest.mockResolvedValue({
      ...m,
      market_context: { ...m.market_context, regime_label: "상승장", regime_code: "bull", regime_streak: { streak_days: 3, at_least: false } },
    });
    fetchMorningBasis.mockRejectedValue(new Error("x"));
    const marketCalls = fetchMarketTopnLatest.mock.calls.length;
    const morningCalls = fetchMorningBasis.mock.calls.length;
    fetchRefreshAllStatus.mockResolvedValue({
      ...base,
      state: "done",
      finished_at: "2026-11-12T08:51:30Z",
      steps: { ...base.steps, prevday: { status: "done", id: "prevday_x", expected_date: "2026-11-11", reason: null, items: {} } },
    });
    await act(async () => {
      vi.advanceTimersByTime(1600);
    });
    await flush();
    expect(fetchMarketTopnLatest.mock.calls.length).toBe(marketCalls + 1);
    expect(fetchMorningBasis.mock.calls.length).toBe(morningCalls + 1);
    const box = screen.getByTestId("tc-now-regime").textContent ?? "";
    expect(box).toContain("상승장(3거래일째)");
    expect(box).toContain("KODEX 200 11/12 가격 기준(저장 시점 확인 필요)");
    expect(box).not.toMatch(/하락장|09:53|장중 저장/);
    const row = screen.getByTestId("tc-regime-today");
    expect(row.textContent).toContain("상승장 · 3거래일째");
    expect(row.textContent).not.toMatch(/하락장|장중 저장/);
    expect(screen.getByTestId("tc-market-flow").querySelector(".tc-sum-stale")?.textContent).toContain("아침 요약 기준: 다시 읽기 실패");
    expect(screen.getByTestId("tc-basis-result").textContent).toBe("아침 요약 기준을 다시 읽지 못했습니다(표시 중인 값은 이전 기준)");
    vi.useRealTimers();
  });

  it.each<[string, { date?: string; close?: number }]>([
    ["F4 기준일과 다른 날의 행", { date: "2026-11-10" }],
    ["F7 같은 날 · 판정 종가와 다른 저장값", { close: 85045 }],
  ])("아침 줄도 저장 상태 · 출처는 아침 판정이 쓴 행(날짜 · 종가)과 같은 저장값일 때만 — %s", async (_t, over) => {
    const ok = morningOk();
    fetchMorningBasis.mockResolvedValue({
      ...ok,
      items: ok.items.map((i) => (i.key === "kodex200" && i.basis_row ? { ...i, basis_row: { ...i.basis_row, ...over } } : i)),
    });
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    const row = screen.getByTestId("tc-regime-morning");
    expect(row.textContent).not.toContain("마감 뒤 저장");
    expect(within(row).queryByTestId("tc-src-regime-morning")?.textContent ?? "").not.toContain("저장");
  });

  it("흐름 문장 = 국면 · 판정 근거 · KODEX 200 저장 기준 · VIX 값과 변화 · 미국 날짜(새 계산 없음)", async () => {
    const m = marketWithReasons();
    fetchMarketTopnLatest.mockResolvedValue(m);
    fetchEtfDetail.mockResolvedValue(KODEX_1556);
    // 당일 판정 = 아침 기준 응답의 today_regime(같은 한 번 읽기의 판정 + 끝 행 저장 시점 · 형수님 결정 2026-11-13)
    fetchMorningBasis.mockResolvedValue({
      ...morningOk(),
      today_regime: {
        status: "ok",
        basis_date: "2026-11-12",
        reason: null,
        context: m.market_context,
        basis_row: { date: "2026-11-12", close: 84240, state: "after_close", fetched_at_kst: "2026-11-12T15:56:59+09:00" },
      },
    });
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    // 보완 2차(S 판정 §3) — 당일 판정은 「오늘 시장 변화」에 날짜 · 저장 시점을 붙여서
    expect(screen.getByTestId("tc-now-regime").textContent).toBe(
      "당일 판정 — 국내 시장은 하락장(25거래일째)입니다. 판정 근거: KODEX200 20거래일 수익률 -2.14% · 현재가가 20일 이동평균 아래. KODEX 200 11/12 가격(15:56 마감 뒤 저장)",
    );
    expect(screen.getByTestId("tc-morning-vix").textContent).toBe("VIX(미국 변동성)는 17.49로 전일보다 10.12% 낮아졌습니다. 11/11 미국");
    // 시장 판정 줄 · VIX 줄은 흐름 문장에 합쳐 카드에서 빠졌다(보완 PLAN 판정 Q-R6 · 상세는 당일 판정 아래 판정 표 · 접기 ①)
    expect(screen.queryByTestId("tc-flow-kodex")).toBeNull();
    expect(screen.queryByTestId("tc-flow-vix")).toBeNull();
  });

  it("기록 없음 = 세 칸 '시세 미확인' + 받는 방법 · 한 칸만 실패 = 그 칸은 마지막 성공 값 + 실패 안내", async () => {
    fetchQuickQuotes.mockResolvedValue(quickEmpty());
    const { unmount } = render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    for (const t of tiles()) expect(t).toContain("시세 미확인 · [최신 자료 갱신]을 누르면 받습니다");
    unmount();
    __resetQueryCache();
    fetchQuickQuotes.mockResolvedValue(
      quickOk({ "069500": { last_attempt: { at: "2026-11-12T16:10:00+09:00", status: "failed", reason: "timeout" } } }),
    );
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    const kodex = tiles()[2];
    expect(kodex).toContain("84,240원");
    expect(kodex).toContain("마지막 조회 실패(응답 시간 초과 · 11/12 16:10) · 위 값은 이전에 받은 시세입니다");
  });

  it("[요약 다시 읽기] = 빠른 시세 · KODEX 200 기준 가격도 저장값만 한 번씩 다시 읽는다(묶음 작업 · 외부 조회 없음)", async () => {
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(screen.getByRole("button", { name: "요약 다시 읽기" }));
    await flush();
    expect(fetchQuickQuotes).toHaveBeenCalledTimes(2);
    expect(fetchEtfDetail).toHaveBeenCalledTimes(2);
    expect(postRefreshAll).not.toHaveBeenCalled();
  });
});

describe("보완 R2 — [최신 자료 갱신] ⓪ 빠른 시세 · 시장 대기 · 같은 거래일 다시 받음", () => {
  it("⓪ 이 끝나는 대로 저장값을 다시 읽어 3칸에 먼저 반영 · 시장 단계가 대기여도 · 대기 줄 = 다음 가능 시각 + 지금 표시 기준", async () => {
    vi.useFakeTimers();
    postRefreshAll.mockResolvedValue(ALL_RUNNING);
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(allButton());
    await flush();
    expect(screen.getByTestId("tc-all-result").textContent).toContain("⓪ 빠른 시세(코스피 · 코스닥 · KODEX 200) 받는 중...");
    fetchQuickQuotes.mockResolvedValue(
      quickOk({ KOSPI: { quote: { value: 5350.12, change: -25.24, change_pct: -0.47, source_time: "2026-11-12T15:20:00+09:00", trade_date: "2026-11-12", market_status: "OPEN", fetched_at: "2026-11-12T15:20:03+09:00" } } }),
    );
    fetchRefreshAllStatus.mockResolvedValue(allAfterQuick(QUICK_DONE));
    await act(async () => {
      vi.advanceTimersByTime(1600);
    });
    await flush();
    expect(fetchQuickQuotes).toHaveBeenCalledTimes(2);
    expect(tiles()[0]).toContain("5,350.12");
    expect(tiles()[0]).toContain("장중");
    expect(screen.getByTestId("tc-quick-result").textContent).toBe(
      "⓪ 코스피 · 코스닥 · KODEX 200 새 시세 받음(시세 시각 11/12 15:36)",
    );
    // 시장 단계 = 대기(6시간) — 빠른 시세 · 보유는 이미 받았다.
    fetchRefreshAllStatus.mockResolvedValue({
      ...ALL_RUNNING,
      state: "done",
      finished_at: "2026-11-12T06:56:14Z",
      steps: {
        quick: QUICK_DONE,
        holdings: { status: "done", ok_count: 1, fail_count: 0 },
        market: { status: "skipped_cooldown", cooldown_remaining_seconds: 1380, next_available_at: "2026-11-12T06:56:07Z", message: "" },
      },
    });
    await act(async () => {
      vi.advanceTimersByTime(1600);
    });
    await flush();
    const line = screen.getByTestId("tc-market-result").textContent ?? "";
    expect(line).toContain("② 시장 자료는 대기 중입니다(6시간 간격) — 다음 갱신 가능 11/12 15:56(약 23분 뒤)");
    expect(line).toContain("지금 표시 = ETF 가격 11/9(11/10 13:18 마감 뒤 저장) · 코스피 공식 종가 11/6");
    expect(tiles()[0]).toContain("5,350.12");
  });

  it("⓪ 결과 = 조회 성공 · 시세 변동 없음 / 한 항목 실패는 그 항목의 마지막 시세 시각 또는 '시세 미확인'", async () => {
    vi.useFakeTimers();
    postRefreshAll.mockResolvedValue(ALL_RUNNING);
    fetchQuickQuotes.mockResolvedValue(
      quickOk({ KOSDAQ: { quote: null, last_attempt: { at: QUICK_FETCHED, status: "failed", reason: "http_error" } } }),
    );
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(allButton());
    await flush();
    fetchRefreshAllStatus.mockResolvedValue(
      allAfterQuick({
        status: "partial",
        items: { KOSPI: { status: "unchanged" }, KOSDAQ: { status: "failed", reason: "http_error" }, "069500": { status: "failed", reason: "timeout" } },
      }),
    );
    await act(async () => {
      vi.advanceTimersByTime(1600);
    });
    await flush();
    const q = screen.getByTestId("tc-quick-result");
    expect(q.textContent).toBe(
      "⓪ 코스피 조회 성공 · 시세 변동 없음 · 코스닥 받지 못함(연결 실패) — 시세 미확인 · KODEX 200 받지 못함(응답 시간 초과) — 마지막 시세 11/12 15:35 표시",
    );
    expect(q.className).toContain("tc-warn");
  });

  it("같은 거래일에 다시 받은 시장 자료 = 날짜 + 저장 시각 + 값(KODEX 200 09:53 장중 85,045원 → 15:56 마감 뒤 84,240원)", async () => {
    fetchEtfDetail.mockResolvedValue(KODEX_0953);
    setStartedRefreshId("r9");
    const waiters: ((v: unknown) => void)[] = [];
    fetchMarketRefreshStatus.mockImplementation(() => new Promise((r) => waiters.push(r)));
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    fetchEtfDetail.mockResolvedValue(KODEX_1556);
    await act(async () => waiters.splice(0).forEach((w) => w({ status: "completed", refresh_id: "r9", error_summary: null, cooldown_remaining_seconds: 21600 })));
    await flush();
    expect(screen.getByTestId("tc-market-result").textContent).toContain(
      "② 시장 자료 갱신 완료 · ETF 가격 11/12 같은 거래일에 다시 받음(09:53 장중 → 15:56 마감 뒤 저장 · KODEX 200 85,045원 → 84,240원)",
    );
  });

  it("다시 읽기 실패 = 실패한 자료 + 지금 표시 중인 값의 기준(날짜 · 저장 시각)을 함께 적는다", async () => {
    fetchEtfDetail.mockResolvedValue(KODEX_0953);
    setStartedRefreshId("r9");
    const waiters: ((v: unknown) => void)[] = [];
    fetchMarketRefreshStatus.mockImplementation(() => new Promise((r) => waiters.push(r)));
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    fetchEtfDetail.mockRejectedValue(new Error("x"));
    await act(async () => waiters.splice(0).forEach((w) => w({ status: "completed", refresh_id: "r9", error_summary: null, cooldown_remaining_seconds: 21600 })));
    await flush();
    const line = screen.getByTestId("tc-market-result").textContent ?? "";
    expect(line).toContain("ETF 가격 확인 불가");
    expect(line).toContain("다시 읽기 실패: KODEX 200 기준 가격(표시 중인 값 기준: ETF 가격 11/12(09:53 장중 저장) · 코스피 공식 종가 11/6");
  });
});

// POC6-29 보완 2차(판정서 V2 · S 판정 · PLAN §10) — 아침 요약 · 당일 판정 · 근거 표 · ③ 전일 자료 보충.
describe("보완 2차 — 아침 요약 · 오늘 시장 변화 · 근거 표 · ③", () => {
  it("준비됨 = '필수 자료 준비됨' · 아침 판정(기준일 마감) · 외국인 5거래일 문장 · 당일 판정은 오늘 시장 변화에 따로", async () => {
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    const m = screen.getByTestId("tc-morning");
    expect(m.textContent).toContain("아침 요약 · 11/11 마감 기준");
    // 설계자 정리(2026-11-13 · 마감 뒤) — 시장 판단 먼저 · 준비 상태는 끝 짧은 한 줄(형수님 선택)
    expect(screen.getByTestId("tc-morning-ready").textContent).toBe("필수 자료 준비됨(코스피 공식 종가 · KODEX 200 · 수급)");
    expect(screen.getByTestId("tc-morning-regime").textContent).toBe(
      "국내 시장은 하락장 24거래일째입니다. KODEX 200은 최근 20거래일간 10.70% 하락했고, 20일선과 60일선 아래에 있습니다.",
    );
    // 순서 = 제목 → 판단 → 자료 문장 → 끝 줄
    const order = ["tc-morning-regime", "tc-morning-text", "tc-morning-ready"].map((id) => within(m).getByTestId(id));
    for (let i = 1; i < order.length; i++) expect(order[i - 1].compareDocumentPosition(order[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(m.textContent).not.toContain("직전 국내 거래일 · 그날까지 저장된 자료");
    expect(screen.getByTestId("tc-morning-flows").textContent).toBe(
      "외국인은 최근 5거래일(11/5 ~ 11/11) 1.1조원 순매도입니다(순매수 → 순매도 전환). 11/11까지",
    );
    // 당일 판정(시장 판정 응답 · 오늘 저장값)은 아침 요약 안에 없다(S 판정 §3).
    expect(m.textContent).not.toContain("당일 판정");
    expect(screen.getByTestId("tc-now-regime").textContent).toContain("당일 판정 — 국내 시장은 하락장");
  });

  it("11/12 사례 — '전일 자료 미완료 · 코스피 공식 종가 · 수급은 11/9까지' 한 줄 + 확인된 사유 · 11/9 문장은 위에 없고 접기 ③ 으로", async () => {
    fetchMorningBasis.mockResolvedValue(morningMissing());
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    // 빠진 자료는 끝 한 줄 · 원인 · 확인 시각은 [자료 상태 보기](처음엔 닫힘 · 설계자 정리 2026-11-13)
    const ready = screen.getByTestId("tc-morning-ready");
    expect(ready.firstChild?.textContent).toBe("코스피 공식 종가 · 수급은 11/9까지 있습니다.");
    const why = ready.querySelector("details") as HTMLDetailsElement;
    expect(why.open).toBe(false);
    expect(why.querySelector("summary")?.textContent).toBe("자료 상태 보기");
    expect(screen.getAllByTestId("tc-morning-reason").map((e) => e.textContent)).toEqual([
      "코스피 공식 종가: 설정 확인 필요(KRX 키 없음) · 15:59 확인",
      "수급: 가져오기 실패(가져오기 실행 실패) · 15:59 확인",
    ]);
    expect(screen.queryByTestId("tc-morning-kospi")).toBeNull();
    expect(screen.queryByTestId("tc-morning-flows")).toBeNull();
    // 미완료 계열(코스피 · 수급)의 사건은 위로 올리지 않는다
    const changes = screen.queryByTestId("tc-morning-changes")?.textContent ?? "";
    expect(changes).not.toMatch(/코스피|외국인|기관/);
    const five = screen.getByTestId("tc-ev-incomplete");
    expect(five.textContent).toContain("③ 전일 자료 미완료");
    expect(five.textContent).toContain("기준일 전 자료");
  });

  it("아침 판정 미확인(기준일 근거 없음)이면 미확인으로 · 당일 판정은 그대로", async () => {
    const ok = morningOk();
    fetchMorningBasis.mockResolvedValue({
      ...ok,
      ready: false,
      missing: ["kodex200"],
      items: ok.items.map((i) =>
        i.key === "kodex200"
          ? { ...i, met: false, state: "late", basis_row: { date: "2026-11-11", close: 84540, state: "intraday" as const }, reason: "KODEX 200 근거 미확인 · 11/11 장중 저장값만 있음 · ETF 전체 갱신 다음 21:59" }
          : i,
      ),
      morning_regime: { status: "unconfirmed", basis_date: "2026-11-11", reason: "KODEX 200 11/11 마감 가격 미확인", context: null },
    });
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    expect(screen.getByTestId("tc-morning-ready").firstChild?.textContent).toBe("KODEX 200 판정 근거는 확인되지 않았습니다.");
    expect(screen.getByTestId("tc-morning-reason").textContent).toBe("KODEX 200 근거 미확인 · 11/11 장중 저장값만 있음 · ETF 전체 갱신 다음 21:59");
    expect(screen.getByTestId("tc-morning-regime").textContent).toBe("아침 판정 미확인 — KODEX 200 11/11 마감 가격 미확인");
    expect(screen.getByTestId("tc-now-regime").textContent).toContain("당일 판정 — 국내 시장은 하락장");
    // 시장 판정 근거 표(당일 판정 바로 아래 · 형수님 결정 2026-11-13) — 아침 줄은 미확인 · 당일 줄은 수치
    expect(screen.getByTestId("tc-regime-morning").textContent).toContain("아침 판정 미확인 — KODEX 200 11/11 마감 가격 미확인");
    expect(screen.getByTestId("tc-regime-today").textContent).toContain("하락장");
  });

  it("근거 표 — 주체마다 5거래일 합 · 하루 빠지면 '5거래일 자료 부족' · 기준일 · 상태 · [?] 안에만 출처 · 받은 시각 · 기간", async () => {
    fetchMorningBasis.mockResolvedValue(morningMissing());
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    expect(screen.getByTestId("tc-ev-short-foreign").textContent).toBe("최근 5거래일 1.1조원 순매도 · 순매수 → 순매도 전환");
    expect(screen.getByTestId("tc-ev-short-institution").textContent).toBe("최근 5거래일 4,001억원 순매수");
    expect(screen.getByTestId("tc-ev-short-individual").textContent).toBe("5거래일 자료 부족");
    const f = screen.getByTestId("tc-ev-foreign");
    expect(f.textContent).toContain("11/11 하루 5,250억원 순매도");
    expect(f.textContent).toContain("2거래일 늦음");
    // 표 칸에는 출처 · 받은 시각이 없고 [?] 안에만
    const cells = Array.from(f.querySelectorAll("td")).map((td) => td.firstChild?.textContent ?? "");
    expect(cells.join(" ")).not.toContain("OCI 수집");
    const hint = screen.getByTestId("tc-src-foreign");
    expect(hint.tagName).toBe("DETAILS");
    expect(hint.textContent).toContain("OCI 수집 → PC 반영 11/12 15:59 · 5거래일 11/5 ~ 11/11 · 직전 10/29 ~ 11/4");
    expect(within(screen.getByLabelText("VIX")).getAllByText(/./).length).toBeGreaterThan(0);
  });

  it("③ 전일 자료 보충 — ② 대기면 같은 작업에서 · 끝나면 아침 기준 · 시장 자료를 다시 읽고 ③ 줄 · 끝 줄(같은 판단)", async () => {
    vi.useFakeTimers();
    postRefreshAll.mockResolvedValue(ALL_RUNNING);
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(allButton());
    await flush();
    const base = {
      ...ALL_RUNNING,
      steps: {
        quick: QUICK_DONE,
        holdings: { status: "done", ok_count: 1, fail_count: 0 },
        market: { status: "skipped_cooldown", cooldown_remaining_seconds: 1380, next_available_at: "2026-11-12T12:59:47Z", message: "" },
      },
    };
    fetchRefreshAllStatus.mockResolvedValue({ ...base, steps: { ...base.steps, prevday: { status: "running" } } });
    await act(async () => {
      vi.advanceTimersByTime(1600);
    });
    await flush();
    expect(screen.getByTestId("tc-prevday-result").textContent).toContain("③ 전일 자료 보충 중...");
    const morningCalls = fetchMorningBasis.mock.calls.length;
    const flowCalls = fetchMarketFlowContext.mock.calls.length;
    fetchRefreshAllStatus.mockResolvedValue({
      ...base,
      state: "done",
      finished_at: "2026-11-12T08:51:30Z",
      steps: {
        ...base.steps,
        prevday: {
          status: "done",
          id: "prevday_x",
          expected_date: "2026-11-11",
          reason: null,
          items: {
            kospi: { label: "코스피 공식 종가", status: "fetched", before: "2026-11-09", after: "2026-11-11", reason: null },
            flows: { label: "투자자 수급", status: "applied", before: "2026-11-09", after: "2026-11-11", reason: null, via: "local" },
            vix: { label: "VIX", status: "already", before: "2026-11-11", after: "2026-11-11", reason: null },
            usdkrw: { label: "원/달러", status: "already", before: "2026-11-11", after: "2026-11-11", reason: null },
            wti: { label: "WTI", status: "skipped", before: "2026-11-11", after: "2026-11-11", reason: "원/달러가 최신이라 함께 받지 않음" },
          },
        },
      },
    });
    await act(async () => {
      vi.advanceTimersByTime(1600);
    });
    await flush();
    expect(screen.getByTestId("tc-prevday-result").textContent).toBe(
      "③ 전일 자료(11/11 기준) — 코스피 공식 종가 11/9 → 11/11 받음 · 수급 11/9 → 11/11 반영(PC 보관본) · VIX 11/11 이미 있음 · 원/달러 11/11 이미 있음",
    );
    expect(fetchMorningBasis.mock.calls.length).toBe(morningCalls + 1);
    expect(fetchMarketFlowContext.mock.calls.length).toBe(flowCalls + 1);
    expect(screen.getByTestId("tc-basis-result").textContent).toBe("아침 요약 기준 11/11 · 필수 자료 모두 준비됨");
    vi.useRealTimers();
  });

  it("③ 건너뜀(② 가 시작 · 진행 중) = 사유 줄만 · 다시 읽기 없음 · ② 거절(③ 진행 중)은 실패가 아닌 안내", async () => {
    vi.useFakeTimers();
    postRefreshAll.mockResolvedValue(ALL_RUNNING);
    render(<TodayInvestmentCheckView onNavigate={() => undefined} />);
    await flush();
    fireEvent.click(allButton());
    await flush();
    const morningCalls = fetchMorningBasis.mock.calls.length;
    fetchRefreshAllStatus.mockResolvedValue({
      ...ALL_RUNNING,
      state: "done",
      steps: {
        quick: QUICK_DONE,
        holdings: { status: "done", ok_count: 1, fail_count: 0 },
        market: { status: "prevday_running", refresh_id: null, message: "전일 자료 보충이 진행 중입니다.", cooldown_remaining_seconds: 0 },
        prevday: { status: "skipped", reason: "전일 자료 보충이 이미 진행 중입니다", id: null, items: {} },
      },
    });
    await act(async () => {
      vi.advanceTimersByTime(1600);
    });
    await flush();
    expect(screen.getByTestId("tc-prevday-result").textContent).toBe("③ 전일 자료 보충 안 함 — 전일 자료 보충이 이미 진행 중입니다");
    expect(fetchMorningBasis.mock.calls.length).toBe(morningCalls);
    const line = screen.getByTestId("tc-market-result");
    expect(line.textContent).toBe("② 전일 자료 보충이 진행 중입니다. 끝난 뒤 다시 누르세요");
    expect(line.querySelector(".tc-warn")).toBeNull();
    vi.useRealTimers();
  });
});
