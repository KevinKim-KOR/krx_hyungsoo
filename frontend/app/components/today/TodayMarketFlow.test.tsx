// POC6-27 — 「오늘의 투자 점검」 시장 흐름 · AI 복사 · 목록 조건 공유 · 시장 갱신 이어 보기
// (설계 §3 · §4 · §6 · 사용자 결정 ① ③ · PLAN 판정 §2 · Q3 · Q7 · Q9 · §4).
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, cleanup, screen, fireEvent, waitFor, within, act } from "@testing-library/react";
import { __resetQueryCache, commitQuery } from "@/lib/api/queryCache";
import { setStartedRefreshId, getStartedRefreshId } from "@/lib/marketRefreshMemory";
import { OBS_1106, flowWith } from "@/lib/todayMarketTestFixtures";
import {
  basisDiffs,
  copyCheck,
  COPY_BASIS_DIFFERS,
  COPY_CANCELLED,
  COPY_DONE,
  COPY_FAILED,
  COPY_READ_FAILED,
  COPY_READING,
  CopySkipped,
  MARKET_COMMON_EVIDENCE_KEY,
  type MarketCommonBasis,
  type MarketCommonEvidence,
} from "@/lib/api/marketCommonEvidence";
import { detailResponse, summaryOk } from "@/lib/etfCompareTestFixtures";
import { quickOk } from "@/lib/quickQuotesTestFixtures";
import type { MorningBasisResponse } from "@/lib/api/morningBasis";
import { MORNING_CTX, morningOk, shortOk } from "@/lib/morningTestFixtures";

const fetchMarketTopnLatest = vi.fn();
const fetchEnrichedHoldings = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
const fetchNavDiscountLatest = vi.fn();
const fetchBenchmarkSeries = vi.fn();
const refreshMarket = vi.fn();
const fetchOciStartupStatus = vi.fn();
const postMarketRefresh = vi.fn();
const fetchMarketRefreshStatus = vi.fn();
const fetchMarketFlowContext = vi.fn();
const fetchForwardComparison = vi.fn();
const fetchLedgerLatestByKind = vi.fn();
const fetchEtfCompareSummary = vi.fn();
const postRefreshAll = vi.fn();
const fetchRefreshAllStatus = vi.fn();

// POC6-31 — 보유 ETF 구성 상태(저장 자료만). 기본 = 다시 확인할 보유 ETF 없음.
const fetchHoldingsConstituentsStatus = vi.fn();
vi.mock("@/lib/api/constituentsStatus", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchHoldingsConstituentsStatus: (...a: unknown[]) => fetchHoldingsConstituentsStatus(...a),
}));
const consStatus = (needs = 0) => ({
  status: "ok",
  reason: null,
  target_date: "2026-11-13",
  running: false,
  total: 2 + needs,
  needs_check: needs,
  counts: { existing: 2, not_checked: needs },
  items: Array.from({ length: needs }, (_, i) => ({
    ticker: `E${i}`,
    name: `보유 ETF ${i}`,
    result: "not_checked",
    label: "아직 확인 안 함",
    reason: "구성 자료 없음 — [최신 자료 갱신]에서 받습니다",
    source_asof: null,
    kept_asof: null,
    kept_confirmed: false,
    needs_check: true,
  })),
});

vi.mock("@/lib/api", () => ({
  fetchMarketTopnLatest: (...a: unknown[]) => fetchMarketTopnLatest(...a),
  fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
  fetchHoldingsMarketEvidence: (...a: unknown[]) => fetchHoldingsMarketEvidence(...a),
  fetchNavDiscountLatest: (...a: unknown[]) => fetchNavDiscountLatest(...a),
  fetchBenchmarkSeries: (...a: unknown[]) => fetchBenchmarkSeries(...a),
  refreshMarket: (...a: unknown[]) => refreshMarket(...a),
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
// POC6-32 — ETF 주간 검토(「잘 오르는 ETF」 자리) 고정 응답(서버 조립 출력 · 11/16 공개 시장 자료)
vi.mock("@/lib/api/weeklyReview", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  const fx = await import("@/lib/weeklyReviewTestFixtures");
  return { ...actual, fetchWeeklyReview: vi.fn(async (sel: string | null) => fx.weeklyFor(sel)) };
});
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
// POC6-32 V2(PLAN §4-1) — 공통 시장 근거(GET /market/evidence) · [AI용 시장 정보 복사]를 누를 때만 읽는다.
const fetchMarketCommonEvidence = vi.fn();
vi.mock("@/lib/api/marketCommonEvidence", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/marketCommonEvidence")>()),
  fetchMarketCommonEvidence: (...a: unknown[]) => fetchMarketCommonEvidence(...a),
}));
// 서버 글(합성) — 화면은 이 글을 한 글자도 바꾸지 않고 복사한다.
const DAILY = "답변 전에 판단에 사용하는 항목의 최신 공개 자료를 확인해 주세요. …(합성 서버 글)\n\n[시장 판정] KODEX 200 하락장 · 합성";
// 기본 기준 = 기본 화면(시장 판정 응답의 하락장 · 11/6 · 코스피 11/6 · 수급 시계열 없음)과 같음.
function commonEv(basis: Partial<MarketCommonBasis> = {}, over: Partial<MarketCommonEvidence> = {}): MarketCommonEvidence {
  return {
    status: "ok",
    message: null,
    generated_at: "2026-11-09T09:00:00+09:00",
    review_date: "2026-11-09",
    basis: {
      regime_label: "하락장",
      regime_price_date: "2026-11-06",
      regime_price_state: "after_close",
      kospi_date: "2026-11-06",
      flow_date: null,
      common_end_date: "2026-11-05",
      ...basis,
    },
    fields: {},
    daily_text: DAILY,
    evidence_items: [],
    data_status: [],
    ...over,
  };
}

import TodayInvestmentCheckView from "../TodayInvestmentCheckView";

function market(over: Record<string, unknown> = {}) {
  return {
    status: "ok",
    asof: "2026-11-06",
    basis: "one_month",
    order: "desc",
    n: 10,
    filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
    candidates: [
      { ticker: "428560", name: "KODEX 미국ETF산업Top10 Indxx", selected_return_pct: 17.02, selected_basis_start_date: "2026-10-07", selected_basis_end_date: "2026-11-06" },
      { ticker: "451530", name: "TIGER 국고채30년스트립액티브", selected_return_pct: 16.23, selected_basis_start_date: "2026-10-07", selected_basis_end_date: "2026-11-06" },
    ],
    market_context: {
      status: "ok",
      asof: "2026-11-06",
      regime_label: "하락장",
      regime_code: "bear",
      regime_streak: { regime_code: "bear", streak_days: 21, at_least: false },
      kodex200: { status: "ok", ma20_distance_pct: -12.08, ma60_distance_pct: -22.33, ma20_position: "below", ma60_position: "below" },
      kospi: { status: "ok", display_state: "ok", as_of_date: "2026-11-06", daily_return_pct: -6.02, return_20d_pct: -23.64, return_60d_pct: -19.16 },
      warnings: [],
    },
    market_risk_reference: {
      kodex200: { availability: "available", as_of_date: "2026-11-06", recent_20d_series: [] },
      vix: { availability: "available", as_of_date: "2026-11-06", recent_20d_series: [], freshness: { state: "fresh" } },
    },
    ...over,
  };
}
const FRESH = (state: "fresh" | "late") => ({
  today_kst: "2026-11-09",
  expected_kr: "2026-11-06",
  expected_kr_basis: "calendar",
  items: [
    { key: "flows", label: "외국인 수급", last_date: state === "late" ? "2026-11-05" : "2026-11-06", expected: "2026-11-06", basis: "kr_t1", state, behind: state === "late" ? 1 : 0, reason: null },
    { key: "usdkrw", label: "원/달러", last_date: "2026-11-06", expected: "2026-11-06", basis: "kr_t1", state: "fresh", behind: 0, reason: null },
    { key: "wti", label: "WTI", last_date: "2026-11-06", expected: null, basis: "observed_only", state: "observed", behind: null, reason: null },
  ],
});
function flow1109(state: "fresh" | "late" = "fresh") {
  return {
    ...flowWith(),
    status: [
      { key: "kospi", label: "코스피", E: "2026-11-06", collected_at: null },
      { key: "flows", label: "투자자별 순매수", E: state === "late" ? "2026-11-05" : "2026-11-06", collected_at: null },
    ],
    periods: {
      "1M": { label: "1개월", boundary: "2026-10-04", start: "2026-10-05", end: "2026-11-05", lines: [], kospi: { from_date: "2026-10-02", from: 6400, to_date: "2026-11-05", to: 5383.8, diff: -1016.2, pct: -15.878125 } },
      "3M": { label: "3개월", boundary: "2026-08-04", start: "2026-08-05", end: "2026-11-05", lines: [], kospi: { from_date: "2026-08-04", from: 6700, to_date: "2026-11-05", to: 5383.8, diff: -1316.2, pct: -19.644776 } },
      "6M": {
        label: "6개월", boundary: "2026-05-05", start: "2026-05-06", end: "2026-11-05", lines: [],
        kospi: { from_date: "2026-05-04", from: 6936.99, to_date: "2026-11-05", to: 5383.8, diff: -1553.19, pct: -22.38997 },
        investors: { foreign: { sum: -164308100000000, days: 124, expected: 124, partial: false } },
      },
    },
    windows: {
      lines: [],
      trend: "직전 20거래일보다 일평균 매도 감소",
      foreign20: {
        recent: { sum: -22.1e12, avg: -1.105e12, from: "2026-10-08", to: "2026-11-05" },
        previous: { sum: -24.0e12, avg: -1.2e12, from: "2026-09-04", to: "2026-10-07" },
      },
      r60: null,
    },
    freshness: FRESH(state),
  };
}
function series(n: number) {
  const pts = Array.from({ length: n }, (_, i) => ({
    date: new Date(Date.UTC(2026, 0, 1) + i * 86400000).toISOString().slice(0, 10),
    price: 5000 + i,
  }));
  return { ticker: "KOSPI", availability: "AVAILABLE", available_from: pts[0].date, available_to: pts[n - 1].date, series: pts };
}

function prime(flowState: "fresh" | "late" = "fresh") {
  fetchMarketCommonEvidence.mockReset().mockResolvedValue(commonEv());
  fetchQuickQuotes.mockReset().mockResolvedValue(quickOk());
  fetchMorningBasis.mockReset().mockResolvedValue(morningOk());
  fetchShortFlows.mockReset().mockResolvedValue(shortOk());
  fetchEtfDetail.mockReset().mockImplementation((ts: string[]) => Promise.resolve(detailResponse(ts)));
  fetchMarketTopnLatest.mockResolvedValue(market());
  fetchEnrichedHoldings.mockResolvedValue({ items: [{ ticker: "161510", name: "보유", current_price: 10, price_source: "naver", price_asof: "2026-11-06T15:27:20+09:00", eval_amount: 10, invested_amount: 9 }] });
  fetchHoldingsMarketEvidence.mockResolvedValue({ status: "ok", summary: { constituents_unavailable_count: 0, evidence_unavailable_count: 0, nav_discount_unavailable_count: 0 }, holdings: [], price_basis: { reference_date: "2026-11-06", date_mismatch: [] }, warnings: [] });
  fetchNavDiscountLatest.mockResolvedValue({ status: "ok", summary: { unavailable_count: 0, failed_count: 0 } });
  fetchBenchmarkSeries.mockResolvedValue(series(130));
  fetchOciStartupStatus.mockResolvedValue({ reachable: true, overall: "OPERATING", summary_line: "OCI", jobs: [], note: "" });
  fetchMarketFlowContext.mockResolvedValue(flow1109(flowState));
  fetchForwardComparison.mockResolvedValue({ status: "NO_RECORDS", label: "연구용 · 운영 미채택" });
  fetchLedgerLatestByKind.mockRejectedValue(new Error("x"));
  refreshMarket.mockResolvedValue({ ok_count: 1, fail_count: 0, items: [], failures: [] });
  fetchMarketRefreshStatus.mockResolvedValue({ status: "idle", refresh_id: null, cooldown_remaining_seconds: 0 });
  fetchEtfCompareSummary.mockResolvedValue(summaryOk());
  fetchRefreshAllStatus.mockResolvedValue(REFRESH_IDLE);
  postRefreshAll.mockResolvedValue(REFRESH_IDLE);
}

const REFRESH_IDLE = { state: "idle", job_id: null, started_at: null, finished_at: null, steps: { holdings: null, market: null } };
// [최신 자료 갱신] 묶음 작업(가짜) — 보유 현재가 끝 · 시장 단계 = 기존 시장 갱신 시작 결과.
const allDone = (market: Record<string, unknown>) => ({
  state: "done",
  job_id: "j1",
  started_at: "2026-11-09T00:00:00Z",
  finished_at: "2026-11-09T00:00:05Z",
  steps: { holdings: { status: "done", ok_count: 1, fail_count: 0 }, market },
});
// 들어올 때 시장 갱신 hook · VIX 다시 받기 hook 이 상태를 각 1회 읽는다 — 둘 다 같은 응답으로 풀어 준다.
function holdStatus() {
  const waiters: ((v: unknown) => void)[] = [];
  fetchMarketRefreshStatus.mockImplementation(() => new Promise((r) => waiters.push(r)));
  return (v: unknown) => waiters.splice(0).forEach((w) => w(v));
}

const writeText = vi.fn();
beforeEach(() => {
  __resetQueryCache();
  vi.clearAllMocks();
  prime();
  fetchHoldingsConstituentsStatus.mockResolvedValue(consStatus());
  writeText.mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
});

async function renderView() {
  const onNavigate = vi.fn();
  render(<TodayInvestmentCheckView onNavigate={onNavigate} />);
  await waitFor(() => expect(screen.getByTestId("tc-kospi-close").textContent).toContain("5,059.69"));
  return { onNavigate };
}
const flowCard = () => screen.getByLabelText("시장 흐름");

describe("시장 흐름 — 11/9 사례(설계 §3 · 판정 §2 · §4)", () => {
  it("코스피 공식 종가 덩어리 — 종가 · 비교 날짜 대비 → 저점 문장(실제 비교 날짜 · 비교 기준) → 20 · 60 · 6개월 → 차트(숫자 바로 아래) · 접기 ① 외국인 두 구간 · 아침 요약 최근 변화", async () => {
    await renderView();
    // 형수님 결정(2026-11-13) — 공식 종가 · 차트는 당일 판정 아래 한 덩어리 · 수급은 근거 접기 안 · 비교 날짜는 직접(RESULT 판정 §3-1)
    const close = screen.getByTestId("tc-kospi-close");
    expect(close.textContent).toContain("코스피 공식 종가(KRX)5,059.69 -324.11pt (-6.02%) 11/5 대비");
    expect(close.textContent).toContain("· 기준일 11/6");
    const low = screen.getByTestId("tc-kospi-low").textContent ?? "";
    expect(low).toContain("11/5의 최근 저점 5,383.80을 밑돌았습니다.");
    expect(low).toContain("(비교 기준: 직전 20개 저장 종가의 최저 5,383.80 · 11/5)");
    expect(low).not.toContain("직전 거래일");
    // 형수님 결정(2026-11-14) — 20 · 60거래일 칸(시장 판정 응답) 대신 같은 시장 흐름 응답의 1 · 3개월(시작 ~ 끝 날짜)
    expect(screen.getByTestId("tc-tile-1m").textContent).toBe("코스피 1개월-15.88%10/2~11/5");
    expect(screen.getByTestId("tc-tile-3m").textContent).toBe("코스피 3개월-19.64%8/4~11/5");
    expect(screen.queryByTestId("tc-tile-20")).toBeNull();
    expect(screen.queryByTestId("tc-tile-60")).toBeNull();
    expect(screen.getByTestId("tc-tile-6m").textContent).toBe("코스피 6개월-22.39%5/4~11/5 · 수급과 같은 기간");
    // 사용자 결정 ① 의 '숫자 바로 아래' — 종가 → 저점 → 칸 → 차트 순서(같은 구역 안)
    const seq = ["tc-kospi-low", "tc-tile-1m", "tc-flow-chart"].map((id) => screen.getByTestId(id));
    for (let k = 1; k < seq.length; k++) {
      expect(seq[k - 1].compareDocumentPosition(seq[k]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(close.contains(seq[k])).toBe(true);
    }
    const foreign = screen.getByTestId("tc-ev-foreign").textContent ?? "";
    expect(foreign).toContain("일평균 순매도 1.2조원 → 1.1조원");
    expect(foreign).toContain("직전 20거래일보다 일평균 매도 감소");
    // 설계자 정리(2026-11-13 · 마감 뒤) — 원/달러 · WTI 의 과거 사건(11/4 WTI · 평소의 3.4배)은 요약 문장에 넣지 않는다(값만 ·
    // 이 자료는 값이 없어 문장 없음) · 최근 변화 줄은 그대로(형수님 선택 · 가장 최근 사건 2건 = 코스피 저점)
    expect(screen.queryByTestId("tc-morning-fxwti")?.textContent ?? "").not.toContain("11/4 WTI가");
    expect(screen.getByTestId("tc-morning-changes").textContent).toContain("11/6 코스피 종가 5,059.69가 11/5 저점 5,383.80을 밑돌았습니다");
    expect(screen.getByTestId("tc-morning-changes").textContent).toContain("전체 7건은 아래 [시장 근거와 다른 변화 보기] ②에서");
    const detail = within(screen.getByTestId("tc-evidence-fold")).getByLabelText("시장 흐름 상세");
    expect(detail.querySelectorAll(".mf-event:not(.tc-warn)").length).toBe(7);
  });

  it("RESULT 판정 §3-1 — 중간 거래일 저장 종가가 비면(11/5 없음) 화면도 실제 비교 날짜 11/4 로 적는다", async () => {
    const f = flow1109();
    const gap = { ...f.short_lines[0], obs: { ...OBS_1106, d1: { from_date: "2026-11-04", diff: -400, pct: -7.33 }, range: { dir: "아래" as const, bound: 5459.69, bound_date: "2026-11-04" } } };
    fetchMarketFlowContext.mockResolvedValue({ ...f, short_lines: [gap, ...f.short_lines.slice(1)] });
    await renderView();
    expect(screen.getByTestId("tc-kospi-close").textContent).toContain("-400.00pt (-7.33%) 11/4 대비");
    expect(screen.getByTestId("tc-kospi-low").textContent).toContain("11/4의 최근 저점 5,459.69를 밑돌았습니다.");
    expect(screen.getByTestId("tc-kospi-close").textContent).not.toMatch(/직전 거래일\(|전일/);
  });

  it("판정 Q9 — 차트는 기존 KospiChart 의 최근 최대 120개 저장일(130개 저장 중) · 그래프 아래 줄 없음", async () => {
    await renderView();
    const chart = screen.getByTestId("tc-flow-chart");
    await within(chart).findByTestId("kospi-chart-readout");
    const pts = series(130).series.slice(-120);
    const x = Array.from(chart.querySelectorAll(".rc-x > span")).map((e) => e.textContent);
    expect(x[0]).toBe(pts[0].date); // 130개 중 끝에서 120번째부터
    expect(x[x.length - 1]).toBe(pts[119].date.slice(5)); // 같은 해 끝 눈금은 '월-일'
    expect(within(chart).getByTestId("kospi-chart-readout").textContent).toBe(`${pts[119].date} · 코스피 5,129.00pt`);
    // 형수님 결정(2026-11-14) — 그래프 아래 두 줄(기간 · 저장일 수 · 최종값 / 배지 · 기준일)은 머리 줄과 겹쳐 뺐다.
    expect(chart.textContent).not.toMatch(/개 저장일|최종|기준일/);
    expect(chart.querySelector(".kospi-badge")).toBeNull();
  });

  it("시장 흐름 응답 실패면 수치 '확인 불가' · 최근 변화 없음 · 실패 안내 · 당일 판정은 남는다", async () => {
    fetchMarketFlowContext.mockRejectedValue(new Error("x"));
    render(<TodayInvestmentCheckView onNavigate={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId("tc-market-flow").querySelector(".tc-sum-stale")?.textContent).toContain("수급 · 환율 · 유가"));
    expect(screen.getByTestId("tc-kospi-close").textContent).toContain("코스피 공식 종가(KRX)확인 불가");
    expect(screen.queryByTestId("tc-morning-changes")).toBeNull();
    expect(screen.getByTestId("tc-now-regime").textContent).toContain("하락장(21거래일째)");
  });
});

const copyBtn = () => within(flowCard()).getByRole("button", { name: "AI용 시장 정보 복사" });
const copyMsg = () => screen.getByTestId("tc-copy-message").textContent;

// POC6-32 V2(PLAN §4-1 · §9 I-23) — 누를 때 공통 시장 근거를 새로 읽어 서버 글 그대로 · 기준이 화면과 다르거나 못 읽으면 복사 안 함.
describe("[AI용 시장 정보 복사](설계 §6 · 판정 §4 · POC6-32 V2 PLAN §4-1)", () => {
  it("모두 최신이면 바로 복사 · 들어올 때는 읽지 않고 누를 때마다 새로 읽어 서버 글을 그대로", async () => {
    await renderView();
    expect(fetchMarketCommonEvidence).not.toHaveBeenCalled();
    fireEvent.click(copyBtn());
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(writeText.mock.calls[0][0]).toBe(DAILY);
    expect(fetchMarketCommonEvidence).toHaveBeenCalledTimes(1);
    expect(await screen.findByTestId("tc-copy-message")).toHaveTextContent("AI용 시장 정보를 복사했습니다");
    // 두 번째 누름 = 앞 응답을 다시 쓰지 않고 새로 읽음(그 사이 서버 글이 바뀌면 새 글)
    fetchMarketCommonEvidence.mockResolvedValue(commonEv({}, { daily_text: `${DAILY} · 두 번째` }));
    fireEvent.click(copyBtn());
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(2));
    expect(fetchMarketCommonEvidence).toHaveBeenCalledTimes(2);
    expect(writeText.mock.calls[1][0]).toBe(`${DAILY} · 두 번째`);
  });

  it("늦은 핵심 자료가 있으면 먼저 고르기 · 창이 열린 동안 다시 누를 수 없음 · [취소]면 복사 안 함 · [계속]이면 서버 글 그대로", async () => {
    prime("late");
    await renderView();
    const btn = copyBtn();
    fireEvent.click(btn);
    const dlg = await screen.findByTestId("tc-stale-dialog");
    expect(dlg.querySelector('[data-fresh="flows"]')?.textContent).toContain("1거래일 늦음");
    expect(btn).toBeDisabled();
    expect(screen.getByRole("button", { name: "요약 다시 읽기" })).toBeDisabled();
    // 검토 F3 — 창이 열리면 '읽는 중' 안내를 내리고 · [취소]면 복사하지 않았다는 안내(클립보드 그대로)
    expect(screen.queryByTestId("tc-copy-message")).toBeNull();
    fireEvent.click(within(dlg).getByRole("button", { name: "취소" }));
    expect(writeText).not.toHaveBeenCalled();
    expect(copyMsg()).toBe(COPY_CANCELLED);
    fireEvent.click(btn);
    fireEvent.click(within(await screen.findByTestId("tc-stale-dialog")).getByRole("button", { name: "이 자료로 계속" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(writeText.mock.calls[0][0]).toBe(DAILY);
    expect(fetchMarketCommonEvidence).toHaveBeenCalledTimes(2); // 누를 때마다 새로 읽음
  });

  it("복사가 실패하면 성공처럼 보이지 않고 글 상자(서버 글)를 펼친다", async () => {
    writeText.mockRejectedValue(new Error("denied"));
    await renderView();
    fireEvent.click(copyBtn());
    expect(await screen.findByTestId("tc-copy-message")).toHaveTextContent("복사하지 못했습니다 — 아래 글을 직접 선택해 복사하세요.");
    const box = screen.getByRole("textbox", { name: "복사할 시장 정보" }) as HTMLTextAreaElement;
    expect(box.value).toBe(DAILY);
  });

  it.each<[string, () => void, string]>([
    ["요청 실패", () => fetchMarketCommonEvidence.mockRejectedValue(new Error("x")), COPY_READ_FAILED],
    [
      "서버가 글을 만들지 못함(unavailable)",
      () => fetchMarketCommonEvidence.mockResolvedValue(commonEv({}, { status: "unavailable", daily_text: null, message: "시장 판정 · 코스피 · 수급 자료를 모두 읽지 못해 시장 근거를 만들지 않았습니다" })),
      "복사할 시장 근거를 만들지 못해 복사하지 않았습니다 — 시장 판정 · 코스피 · 수급 자료를 모두 읽지 못해 시장 근거를 만들지 않았습니다",
    ],
  ])("I-23 — 공통 근거를 못 읽으면(%s) 복사하지 않고 알린다 · 대신할 글 · 글 상자 없음", async (_t, arrange, message) => {
    arrange();
    await renderView();
    fireEvent.click(copyBtn());
    await waitFor(() => expect(copyMsg()).toBe(message));
    expect(writeText).not.toHaveBeenCalled();
    expect(screen.queryByRole("textbox", { name: "복사할 시장 정보" })).toBeNull();
    expect(screen.queryByTestId("tc-stale-dialog")).toBeNull();
    expect(copyBtn()).not.toBeDisabled(); // 다시 누를 수 있음
  });

  it("I-23 — 앞서 읽은 공통 근거가 있어도 이번 읽기가 실패하면 복사하지 않는다(이전 응답으로 대신하지 않음)", async () => {
    await renderView();
    fireEvent.click(copyBtn());
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    fetchMarketCommonEvidence.mockRejectedValue(new Error("x"));
    fireEvent.click(copyBtn());
    await waitFor(() => expect(copyMsg()).toBe(COPY_READ_FAILED));
    expect(writeText).toHaveBeenCalledTimes(1);
  });

  it("읽는 동안 시장 갱신이 끝나면(다시 읽은 자료가 아직 화면에 오지 않아도) 읽은 글을 복사하지 않는다", async () => {
    setStartedRefreshId("r9");
    const resolveStatus = holdStatus();
    await renderView();
    let resolveEv!: (v: unknown) => void;
    fetchMarketCommonEvidence.mockImplementationOnce(() => new Promise((r) => (resolveEv = r)));
    // 갱신 뒤 다시 읽기는 끝나지 않게 둔다 — 새 값이 오기 전에도 멈추는지 본다(지운 키 = 불러오는 중 → 보호가 멈춤 ·
    // 그 그림 전에 글이 도착하면 갱신 완료 표시로 멈춤 · 어느 쪽이 먼저든 복사는 없음)
    const never = () => new Promise(() => undefined);
    for (const f of [fetchMarketTopnLatest, fetchMarketFlowContext, fetchMorningBasis, fetchShortFlows, fetchEtfDetail, fetchBenchmarkSeries])
      f.mockImplementation(never);
    fireEvent.click(copyBtn());
    await act(async () => resolveStatus({ status: "completed", refresh_id: "r9", error_summary: null, cooldown_remaining_seconds: 21600 }));
    await act(async () => resolveEv(commonEv()));
    await waitFor(() => expect(copyMsg()).toMatch(/^(복사에 쓰는 시장 자료가 바뀌어|시장 자료를 새로 읽어) 복사를 멈췄습니다 — 다시 눌러 주세요\.$/));
    expect(writeText).not.toHaveBeenCalled();
    expect(screen.queryByTestId("tc-stale-dialog")).toBeNull();
  });

  it.each<[string, Partial<MarketCommonBasis>, string]>([
    ["코스피 기준일", { kospi_date: "2026-11-09" }, "코스피 기준일"],
    ["수급 기준일", { flow_date: "2026-11-06" }, "수급 기준일"],
    ["시장 판정 이름", { regime_label: "보합장" }, "시장 판정"],
    ["시장 판정 가격 기준일 · 코스피 기준일", { regime_price_date: "2026-11-09", kospi_date: "2026-11-09" }, "시장 판정 가격 기준일 · 코스피 기준일"],
  ])("응답 기준이 화면과 다르면(%s) 복사하지 않고 [요약 다시 읽기] 안내", async (_t, basis, items) => {
    fetchMarketCommonEvidence.mockResolvedValue(commonEv(basis));
    await renderView();
    fireEvent.click(copyBtn());
    await waitFor(() => expect(copyMsg()).toBe(`${COPY_BASIS_DIFFERS}(다른 항목: ${items})`));
    expect(copyMsg()?.startsWith("화면과 복사 근거가 다릅니다 — [요약 다시 읽기] 뒤 다시 누르세요")).toBe(true);
    expect(writeText).not.toHaveBeenCalled();
    expect(screen.queryByTestId("tc-stale-dialog")).toBeNull();
  });

  it("화면 수급 기준일 = 시장 흐름 응답의 수급 시계열 끝(E) — 같으면 복사 · 다르면 안 함", async () => {
    const flows = { label: "투자자별 순매수", unit: "원", E: "2026-11-06", investors: {}, collected_at: null };
    fetchMarketFlowContext.mockResolvedValue({ ...flow1109(), series: { flows } });
    fetchMarketCommonEvidence.mockResolvedValue(commonEv({ flow_date: "2026-11-06" }));
    await renderView();
    fireEvent.click(copyBtn());
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    fetchMarketCommonEvidence.mockResolvedValue(commonEv({ flow_date: "2026-11-05" }));
    fireEvent.click(copyBtn());
    await waitFor(() => expect(copyMsg()).toBe(`${COPY_BASIS_DIFFERS}(다른 항목: 수급 기준일)`));
    expect(writeText).toHaveBeenCalledTimes(1);
  });

  it("읽는 동안 복사 · [요약 다시 읽기] 버튼이 막히고 · 그 사이 화면 판정이 바뀌면(아침 기준 도착) 읽은 글을 복사하지 않는다", async () => {
    let resolveMorning!: (v: unknown) => void;
    fetchMorningBasis.mockReset().mockImplementation(() => new Promise((r) => (resolveMorning = r)));
    let resolveEv!: (v: unknown) => void;
    fetchMarketCommonEvidence.mockImplementationOnce(() => new Promise((r) => (resolveEv = r)));
    await renderView();
    fireEvent.click(copyBtn());
    expect(copyMsg()).toBe(COPY_READING);
    expect(copyBtn()).toBeDisabled();
    expect(screen.getByRole("button", { name: "요약 다시 읽기" })).toBeDisabled();
    const up = { ...MORNING_CTX, regime_label: "상승장", regime_code: "bull" } as typeof MORNING_CTX;
    const row = { date: "2026-11-12", close: 84240, state: "after_close" as const, fetched_at_kst: "2026-11-12T15:56:59+09:00" };
    await act(async () => resolveMorning({ ...morningOk(), today_regime: { status: "ok", basis_date: row.date, reason: null, context: up, basis_row: row } }));
    await waitFor(() => expect(copyMsg()).toBe("복사에 쓰는 시장 자료가 바뀌어 복사를 멈췄습니다 — 다시 눌러 주세요."));
    await act(async () => resolveEv(commonEv())); // 누를 때 화면(하락장 11/6)과 같은 기준의 글이 늦게 도착
    expect(writeText).not.toHaveBeenCalled();
    expect(screen.queryByTestId("tc-stale-dialog")).toBeNull();
    expect(copyMsg()).toBe("복사에 쓰는 시장 자료가 바뀌어 복사를 멈췄습니다 — 다시 눌러 주세요.");
    expect(copyBtn()).not.toBeDisabled();
  });

  it("확인 창이 열린 동안 받아 둔 공통 근거 응답이 바뀌면(같은 키를 다시 읽음) 복사하지 않고 창을 닫는다", async () => {
    prime("late");
    await renderView();
    fireEvent.click(copyBtn());
    expect(await screen.findByRole("button", { name: "이 자료로 계속" })).toBeInTheDocument();
    await act(async () => commitQuery(MARKET_COMMON_EVIDENCE_KEY, commonEv({}, { daily_text: "다른 글" })));
    expect(screen.queryByTestId("tc-stale-dialog")).toBeNull();
    expect(copyMsg()).toBe("복사에 쓰는 시장 자료가 바뀌어 복사를 멈췄습니다 — 다시 눌러 주세요.");
    expect(writeText).not.toHaveBeenCalled();
  });

  it("대조 규칙(순수 함수) — 판정 가격 상태는 화면이 보일 때만 · 없는 값끼리 같음 · 빈 글 · 기준 칸 없는 응답", () => {
    const screenB = { regimeLabel: "하락장", regimePriceDate: "2026-11-06", kospiDate: "2026-11-06", flowDate: null };
    const srv = commonEv().basis;
    expect(basisDiffs({ ...srv, regime_price_state: "intraday" }, screenB)).toEqual([]);
    expect(basisDiffs({ ...srv, regime_price_state: "intraday" }, { ...screenB, regimePriceState: "after_close" })).toEqual([
      "시장 판정 가격 상태(장중 · 마감 뒤)",
    ]);
    expect(basisDiffs({ ...srv, regime_label: null }, { ...screenB, regimeLabel: null })).toEqual([]);
    expect(basisDiffs({}, { regimeLabel: null, regimePriceDate: null, kospiDate: null, flowDate: null })).toEqual([]);
    expect(copyCheck(commonEv(), screenB)).toEqual({ ok: true, text: DAILY });
    expect(copyCheck(commonEv({}, { status: "partial" }), screenB)).toEqual({ ok: true, text: DAILY });
    expect(copyCheck(commonEv({}, { daily_text: "" }), screenB)).toEqual({ ok: false, message: "복사할 시장 근거를 만들지 못해 복사하지 않았습니다 — 사유 확인 불가" });
    expect(copyCheck({ ...commonEv(), basis: undefined } as unknown as MarketCommonEvidence, screenB)).toEqual({ ok: false, message: COPY_READ_FAILED });
    expect(copyCheck(null, screenB)).toEqual({ ok: false, message: COPY_READ_FAILED });
  });
});

// 검토 F1(PLAN I-30) — 클립보드 쓰기는 누른 순간에 시작한다: 글이 나중에 채워지는 클립보드 항목(ClipboardItem)을 누른
// 처리 안에서 넘기고, 새로 읽고 대조한 뒤 그 글로 채운다. 확인 창이 필요하거나 막히면 그 항목을 거절(클립보드 그대로 ·
// '복사하지 못했습니다'를 띄우지 않음). ClipboardItem · clipboard.write 가 없으면 예전처럼 읽은 뒤 writeText.
class FakeItem {
  constructor(readonly items: Record<string, Promise<Blob>>) {}
}
const write = vi.fn(async (items: FakeItem[]) => {
  await items[0].items["text/plain"]; // 브라우저처럼 항목 글을 기다림(거절이면 쓰기도 거절)
});
const readBlob = (b: Blob) =>
  new Promise<string>((res) => {
    const fr = new FileReader();
    fr.onload = () => res(String(fr.result));
    fr.readAsText(b);
  });
const lastItem = () => (write.mock.calls[write.mock.calls.length - 1][0] as FakeItem[])[0].items["text/plain"];

describe("검토 F1 · F3 — 누른 순간 클립보드 쓰기(ClipboardItem) · 확인 창 안내", () => {
  beforeEach(() => {
    write.mockClear();
    vi.stubGlobal("ClipboardItem", FakeItem);
    Object.defineProperty(navigator, "clipboard", { value: { writeText, write }, configurable: true });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("모두 최신 — 누른 처리 안에서(읽기 전) 쓰기를 시작 · 읽은 뒤 항목 글 = 서버 글 그대로 · writeText 안 씀", async () => {
    await renderView();
    let resolveEv!: (v: unknown) => void;
    fetchMarketCommonEvidence.mockImplementationOnce(() => new Promise((r) => (resolveEv = r)));
    fireEvent.click(copyBtn());
    expect(write).toHaveBeenCalledTimes(1); // 응답이 오기 전 = 누른 동작 안
    expect(copyMsg()).toBe(COPY_READING);
    await act(async () => resolveEv(commonEv()));
    expect(await readBlob(await lastItem())).toBe(DAILY);
    await waitFor(() => expect(copyMsg()).toBe(COPY_DONE));
    expect(writeText).not.toHaveBeenCalled();
  });

  it("확인 창이 필요하면 항목 거절(확인 창 사유 · 실패 안내 없음) · [취소] 안내 · [이 자료로 계속] = 그 누름 안에서 writeText", async () => {
    prime("late");
    await renderView();
    fireEvent.click(copyBtn());
    expect(write).toHaveBeenCalledTimes(1);
    const dlg = await screen.findByTestId("tc-stale-dialog");
    await expect(lastItem()).rejects.toEqual(new CopySkipped("dialog"));
    await act(async () => undefined);
    expect(screen.queryByTestId("tc-copy-message")).toBeNull(); // 읽는 중 안내 내림 · 실패 안내 없음
    fireEvent.click(within(dlg).getByRole("button", { name: "취소" }));
    expect(copyMsg()).toBe(COPY_CANCELLED);
    expect(writeText).not.toHaveBeenCalled();
    fireEvent.click(copyBtn());
    fireEvent.click(within(await screen.findByTestId("tc-stale-dialog")).getByRole("button", { name: "이 자료로 계속" }));
    expect(writeText).toHaveBeenCalledTimes(1); // [이 자료로 계속] 누름 처리 안
    expect(writeText.mock.calls[0][0]).toBe(DAILY);
    await waitFor(() => expect(copyMsg()).toBe(COPY_DONE));
  });

  it("막힘(기준 다름) = 항목 거절(막힘 사유) · 기준 다름 안내 그대로(실패 안내로 덮지 않음)", async () => {
    fetchMarketCommonEvidence.mockResolvedValue(commonEv({ kospi_date: "2026-11-09" }));
    await renderView();
    fireEvent.click(copyBtn());
    expect(write).toHaveBeenCalledTimes(1);
    await expect(lastItem()).rejects.toEqual(new CopySkipped("blocked"));
    await act(async () => undefined);
    expect(copyMsg()).toBe(`${COPY_BASIS_DIFFERS}(다른 항목: 코스피 기준일)`);
    expect(writeText).not.toHaveBeenCalled();
    expect(screen.queryByRole("textbox", { name: "복사할 시장 정보" })).toBeNull();
  });

  it("브라우저가 쓰기를 거절하면 성공처럼 보이지 않고 글 상자(서버 글)", async () => {
    write.mockImplementationOnce(async (items: FakeItem[]) => {
      await items[0].items["text/plain"];
      throw new Error("denied");
    });
    await renderView();
    fireEvent.click(copyBtn());
    await waitFor(() => expect(copyMsg()).toBe(COPY_FAILED));
    expect((screen.getByRole("textbox", { name: "복사할 시장 정보" }) as HTMLTextAreaElement).value).toBe(DAILY);
  });

  it.each<[string, () => void]>([
    ["ClipboardItem 없음", () => vi.unstubAllGlobals()],
    [
      "약속 값 항목을 못 만듦",
      () =>
        vi.stubGlobal(
          "ClipboardItem",
          class {
            constructor() {
              throw new TypeError("no promise");
            }
          },
        ),
    ],
  ])("%s — 예전처럼 읽은 뒤 writeText(서버 글 그대로)", async (_t, arrange) => {
    arrange();
    await renderView();
    fireEvent.click(copyBtn());
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(writeText.mock.calls[0][0]).toBe(DAILY);
    expect(write).not.toHaveBeenCalled();
    await waitFor(() => expect(copyMsg()).toBe(COPY_DONE));
  });
});

// POC6-29 — 「오늘의 투자 점검」 목록과 「요즘 잘 오르는 ETF」의 조건 공유는 없앴다(C 메뉴 정리 · 판정 Q1 · Q2 — A 는
//   자체 기간 · 공통 기간 목록). 그 공유만 보던 세 시험은 지웠다(A 카드 시험은 TodayInvestmentCheckView.test).

describe("검토 정정 — 표시 · 경쟁", () => {
  it("검증자 r1 F1 — [이 자료로 계속]으로 반영한 새 값을 늦게 끝난 첫 조회 응답이 덮지 않는다", async () => {
    prime("late");
    let resolveInit!: (v: unknown) => void;
    fetchMarketFlowContext.mockImplementationOnce(() => new Promise((r) => (resolveInit = r)));
    render(<TodayInvestmentCheckView onNavigate={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId("tc-now-regime")).toBeTruthy());
    const newer = { ...flow1109("late"), short_lines: [{ ...flowWith().short_lines[0], obs: { ...OBS_1106, value: 5100 } }] };
    fetchMarketFlowContext.mockResolvedValueOnce(newer);
    fireEvent.click(screen.getByRole("button", { name: "요약 다시 읽기" }));
    fireEvent.click(await screen.findByRole("button", { name: "이 자료로 계속" }));
    await waitFor(() => expect(screen.getByTestId("tc-kospi-close").textContent).toContain("5,100.00"));
    await act(async () => resolveInit(flow1109("late"))); // 첫 조회(5,059.69)가 이제야 끝남
    expect(screen.getByTestId("tc-kospi-close").textContent).toContain("5,100.00");
    expect(screen.getByTestId("tc-kospi-close").textContent).not.toContain("5,059.69");
  });

  it("F2 — 두 구간 방향이 다르면 일평균을 구간마다 방향과 함께(순매수 → 순매도)", async () => {
    fetchMarketFlowContext.mockResolvedValue({
      ...flow1109(),
      windows: {
        lines: [],
        trend: "순매수 → 순매도 전환",
        foreign20: {
          recent: { sum: -22e12, avg: -1.1e12, from: "2026-10-08", to: "2026-11-05" },
          previous: { sum: 5e12, avg: 0.25e12, from: "2026-09-07", to: "2026-10-07" },
        },
      },
    });
    await renderView();
    // 보완 2차 — 근거 표 ③ 외국인 줄(두 구간 기간을 함께)
    expect(screen.getByTestId("tc-ev-foreign").textContent).toContain("일평균 순매수 2,500억원 → 순매도 1.1조원");
  });

  it("F9 — 위 문장과 같은 사건만 있고 확인 못 한 자료가 있으면 '없음'을 단정하지 않는다", async () => {
    fetchMarketFlowContext.mockResolvedValue({
      ...flow1109(),
      events: [flowWith().events[0]],
      event_check: { checked: [], unchecked: ["원/달러"], unchecked_text: "원/달러는 자료가 부족해 비교하지 못했습니다", empty_text: null },
    });
    await renderView();
    // 보완 2차 — 저점 문장은 코스피 공식 종가 덩어리(당일 판정 아래 · 형수님 결정 2026-11-13)에 있으므로 그 사건은 아침 요약 최근 변화에 올라온다 · '없음' 단정은 어디에도 없고
    // 확인 못 한 자료 안내는 근거 접기 ②(기존 시장 흐름 카드)에 그대로.
    expect(screen.getByTestId("tc-morning-changes").textContent).toContain("전체 1건은 아래 [시장 근거와 다른 변화 보기] ②에서");
    expect(screen.getByTestId("tc-market-flow").textContent).not.toContain("최근 큰 변화 없음");
    expect(screen.getByTestId("market-flow-events-unchecked").textContent).toContain("원/달러는 자료가 부족해 비교하지 못했습니다");
  });

  it("F3 — 시장 흐름 · 보유를 불러오는 중에는 「자료 최신화 필요」가 없고 복사 버튼은 막힌다", async () => {
    fetchMarketFlowContext.mockImplementation(() => new Promise(() => undefined));
    fetchEnrichedHoldings.mockImplementation(() => new Promise(() => undefined));
    render(<TodayInvestmentCheckView onNavigate={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId("tc-now-regime")).toBeTruthy());
    expect(screen.queryByLabelText("자료 최신화 필요")).toBeNull();
    expect(screen.getByRole("button", { name: "AI용 시장 정보 복사" })).toBeDisabled();
  });

  it("F4 — [요약 다시 읽기]가 도는 동안 복사 버튼이 막혀 다시 읽기 결과가 복사 창을 가로채지 않는다", async () => {
    await renderView();
    let resolveFlow!: (v: unknown) => void;
    fetchMarketFlowContext.mockImplementationOnce(() => new Promise((r) => (resolveFlow = r)));
    fireEvent.click(screen.getByRole("button", { name: "요약 다시 읽기" }));
    expect(screen.getByRole("button", { name: "AI용 시장 정보 복사" })).toBeDisabled();
    await act(async () => resolveFlow(flow1109()));
    await waitFor(() => expect(screen.getByRole("button", { name: "AI용 시장 정보 복사" })).not.toBeDisabled());
  });

  it(
    "F1 — 다시 읽기 확인 창이 열린 동안 시장 갱신이 끝나면 창을 닫고 받아 둔 옛 결과로 새 값을 덮지 않는다",
    async () => {
      // POC6-29 — [최신 자료 갱신]은 다시 읽는 동안 막힌다. 남은 경로 = 들어올 때 읽은 상태가 늦게 '다른 곳에서 도는 갱신'으로
      //   돌아온 경우(다시 읽기를 이미 눌렀음) — 그 갱신이 창이 열린 동안 끝나도 옛 결과로 덮지 않는다.
      prime("late");
      const resolveProbe = holdStatus();
      await renderView();
      let resolveFlow!: (v: unknown) => void;
      fetchMarketFlowContext.mockImplementationOnce(() => new Promise((r) => (resolveFlow = r)));
      fireEvent.click(screen.getByRole("button", { name: "요약 다시 읽기" }));
      await act(async () => resolveProbe({ status: "running", refresh_id: "r1", cooldown_remaining_seconds: 0 }));
      fetchMarketRefreshStatus.mockResolvedValue({ status: "running", refresh_id: "r1", cooldown_remaining_seconds: 0 });
      await screen.findByRole("button", { name: "자료 갱신 중..." });
      expect(postRefreshAll).not.toHaveBeenCalled();
      await act(async () => resolveFlow(flow1109("late")));
      expect(await screen.findByTestId("tc-stale-dialog")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "요약 다시 읽기" })).toBeDisabled(); // 갱신 중 · 창이 열린 동안 다시 읽기 막힘
      // 다음 상태 확인(4초)에 갱신 완료 — 갱신 뒤 다시 읽는 시장 흐름은 새 값(수급 11/6)
      fetchMarketRefreshStatus.mockResolvedValue({ status: "completed", refresh_id: "r1", error_summary: null, cooldown_remaining_seconds: 21600 });
      fetchMarketFlowContext.mockResolvedValue(flow1109("fresh"));
      await waitFor(() => expect(screen.queryByTestId("tc-stale-dialog")).toBeNull(), { timeout: 7000 });
      expect(screen.getByTestId("tc-reload-state").textContent).toContain("앞서 받아 둔 다시 읽기 결과는 반영하지 않았습니다");
      await waitFor(() => expect(screen.getByTestId("tc-market-result").textContent).toContain("외국인 수급 11/5 → 11/6"));
      expect(screen.queryByLabelText("자료 최신화 필요")).toBeNull(); // 새 값 그대로(옛 11/5 로 되돌아가지 않음)
    },
    15000,
  );
});

describe("판정 Q7 — 다른 화면에서 시작한 시장 갱신을 이어 본다(새로 시작하지 않음)", () => {
  it("진행 중이면 상태를 읽어 '갱신 중' · 버튼 막힘 · POST 없음", async () => {
    setStartedRefreshId("r9");
    fetchMarketRefreshStatus.mockResolvedValue({ status: "running", refresh_id: "r9", cooldown_remaining_seconds: 0 });
    await renderView();
    expect(await screen.findByTestId("tc-market-result")).toHaveTextContent("② 시장 자료 갱신 중입니다");
    expect(fetchMarketRefreshStatus).toHaveBeenCalledTimes(2); // 시장 갱신 · VIX 다시 받기 hook 각 1회(읽기만)
    expect(postMarketRefresh).not.toHaveBeenCalled();
    expect(postRefreshAll).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "자료 갱신 중..." })).toBeDisabled();
  });

  it("그 사이 끝났으면 완료 처리 · 다시 읽은 자료의 기준일 대조(코스피 그대로 · 수급 11/5 → 11/6)", async () => {
    prime("late");
    setStartedRefreshId("r9");
    const resolveStatus = holdStatus();
    await renderView();
    fetchMarketFlowContext.mockResolvedValue(flow1109("fresh"));
    await act(async () => resolveStatus({ status: "completed", refresh_id: "r9", error_summary: null, cooldown_remaining_seconds: 21600 }));
    // 보완 — 날짜 + 저장 시각 + 값 대조(ETF 가격 = KODEX 200 끝일 가격 · 같은 저장이면 '그대로')
    await waitFor(() =>
      expect(screen.getByTestId("tc-market-result").textContent).toContain(
        "② 시장 자료 갱신 완료 · ETF 가격 11/9 그대로 · 코스피 공식 종가 11/6 그대로 · 외국인 수급 11/5 → 11/6",
      ),
    );
    expect(getStartedRefreshId()).toBeNull();
    // 설계자 2026-11-10 — 기대일로 갱신되면 이전 기준일 안내 · 실패 줄이 없다.
    expect(screen.queryByTestId("tc-market-behind")).toBeNull();
    expect(screen.queryByTestId("tc-market-fail")).toBeNull();
    expect(screen.queryByTestId("tc-market-other")).toBeNull();
  });

  it("설계자 2026-11-10 — 갱신 뒤에도 저장일이 그대로면 기준일 안내와 ETF 실패 건수 · 그 밖의 확인 필요를 줄을 나눠 보인다", async () => {
    prime("late");
    setStartedRefreshId("r9");
    const resolveStatus = holdStatus();
    await renderView();
    fetchMarketFlowContext.mockResolvedValue(flow1109("late")); // 다시 읽어도 수급 11/5 그대로
    await act(async () =>
      resolveStatus({
        status: "completed",
        refresh_id: "r9",
        price_fail_count: 7,
        error_summary: "price_partial_failure: fail=7 · 시장 불안 지표(VIX)를 갱신하지 못했습니다",
        cooldown_remaining_seconds: 21600,
      }),
    );
    expect(await screen.findByTestId("tc-market-behind")).toHaveTextContent("갱신 후에도 외국인 수급은 11/5 기준입니다. 화면 기대일은 11/6입니다.");
    expect(screen.getByTestId("tc-market-fail")).toHaveTextContent("ETF 가격 7건은 이번에 갱신하지 못했습니다.");
    expect(screen.getByTestId("tc-market-other")).toHaveTextContent("그 밖의 확인 필요: 시장 불안 지표(VIX)를 갱신하지 못했습니다");
    expect(screen.getByTestId("tc-market-result").textContent).toContain(
      "② 시장 자료 갱신 완료 · ETF 가격 11/9 그대로 · 코스피 공식 종가 11/6 그대로 · 외국인 수급 11/5 그대로",
    );
    expect(screen.getByTestId("tc-market-result").textContent).not.toContain("price_partial_failure");
  });

  it("이 탭에서 시작한 갱신이 없어도 들어올 때 상태 읽기(hook 마다 1회) — 진행 중이면 같은 작업으로 이어 봄(POST 없음) · 아니면 줄 없음", async () => {
    fetchMarketRefreshStatus.mockResolvedValue({ status: "running", refresh_id: "r11", cooldown_remaining_seconds: 0 });
    await renderView();
    expect(await screen.findByTestId("tc-market-result")).toHaveTextContent("② 시장 자료 갱신 중입니다");
    expect(fetchMarketRefreshStatus).toHaveBeenCalledTimes(2);
    expect(postMarketRefresh).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "자료 갱신 중..." })).toBeDisabled();
  });

  it("지난 갱신이 끝난 상태 · 대기 중이면 들어올 때 아무 줄도 없다(지난 결과로 완료 처리 · 다시 읽기 없음)", async () => {
    fetchMarketRefreshStatus.mockResolvedValue({ status: "completed", refresh_id: "r12", error_summary: null, cooldown_remaining_seconds: 9000 });
    await renderView();
    await waitFor(() => expect(fetchMarketRefreshStatus).toHaveBeenCalledTimes(2));
    expect(screen.queryByTestId("tc-market-result")).toBeNull();
    expect(fetchMarketFlowContext).toHaveBeenCalledTimes(1);
    expect(screen.getAllByRole("button", { name: "최신 자료 갱신" })[0]).not.toBeDisabled();
  });

  it("'VIX 다시 받기'가 도는 중이면 실패가 아니라 진행 중 안내 · 버튼 막힘(들어올 때 상태 · 누른 뒤 거절 둘 다)", async () => {
    fetchMarketRefreshStatus.mockResolvedValue({ status: "completed", refresh_id: "r12", cooldown_remaining_seconds: 9000, vix_retry: { needed: true, status: "running", refresh_id: "v1" } });
    await renderView();
    expect(await screen.findByTestId("tc-market-result")).toHaveTextContent("VIX 다시 받기가 진행 중입니다(시장 자료 갱신은 끝난 뒤 시작할 수 있습니다)");
    // VIX 는 근거 접기 ①(수급 · VIX · 원/달러 · WTI) — 안내의 번호가 접기 제목과 같아야 한다(형수님 결정 2026-11-13 배치).
    expect(screen.getByTestId("tc-market-result")).toHaveTextContent("결과는 아래 [시장 근거와 다른 변화 보기] ①에서 볼 수 있습니다");
    expect(within(screen.getByTestId("tc-evidence-fold")).getByRole("heading", { name: "① 수급 · VIX · 원/달러 · WTI" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "자료 갱신 중..." })[0]).toBeDisabled();
    cleanup();
    vi.clearAllMocks();
    prime();
    // 묶음 작업의 시장 단계가 기존 시작 함수의 거절(vix_retry_running)을 그대로 돌려준다.
    postRefreshAll.mockResolvedValue(
      allDone({ status: "vix_retry_running", refresh_id: "v1", message: "VIX 다시 받기가 진행 중입니다.", cooldown_remaining_seconds: 9000 }),
    );
    await renderView();
    fireEvent.click(screen.getAllByRole("button", { name: "최신 자료 갱신" })[0]);
    expect(await screen.findByTestId("tc-market-result")).toHaveTextContent("VIX 다시 받기가 진행 중입니다");
    expect(screen.getByTestId("tc-market-result").textContent).not.toContain("실패");
    expect(screen.getAllByRole("button", { name: "자료 갱신 중..." })[0]).toBeDisabled();
  });

  it("다른 갱신이 기록돼 있으면 이 탭 것의 결과는 모른다 — 원래 버튼(줄 없음)", async () => {
    setStartedRefreshId("r9");
    fetchMarketRefreshStatus.mockResolvedValue({ status: "completed", refresh_id: "r10", cooldown_remaining_seconds: 0 });
    await renderView();
    await waitFor(() => expect(getStartedRefreshId()).toBeNull());
    expect(screen.queryByTestId("tc-market-result")).toBeNull();
    expect(screen.getAllByRole("button", { name: "최신 자료 갱신" })[0]).not.toBeDisabled();
  });
});

// 설계자 RESULT 재판정 V3(2026-11-13) — D1 점수 열 · [?] 산식 / D2 같은 마감 자료 한 행 · 상자는 기준만 / §3 복사 = 화면 판정.
describe("설계자 V3 마감 보완 — 점수 · 공통 행 · 복사", () => {
  // 아침 판정과 같은 11/11 마감 뒤 저장 행으로 계산한 당일 판정(같은 응답 · 같은 한 번 읽기)
  const SAME = { date: "2026-11-11", close: 84540, state: "after_close" as const, fetched_at_kst: "2026-11-11T16:00:00+09:00" };
  const withToday = (tr: NonNullable<MorningBasisResponse["today_regime"]>, over: Partial<MorningBasisResponse> = {}) => ({
    ...morningOk(),
    today_regime: tr,
    ...over,
  });
  const ok = (row: typeof SAME | { date: string; close: number; state: "intraday" | "after_close"; fetched_at_kst: string }, ctx = MORNING_CTX) => ({
    status: "ok" as const,
    basis_date: row.date,
    reason: null,
    context: ctx,
    basis_row: row,
  });
  const rowsOf = () => ["common", "morning", "today"].filter((k) => screen.queryByTestId(`tc-regime-${k}`));

  it("D2 — 같은 유효 응답의 같은 마감 뒤 저장 행이면 '아침·당일 공통' 한 행 · 상자는 기준만 · D1 점수 · 복사도 같은 판정", async () => {
    fetchMorningBasis.mockResolvedValue(withToday(ok(SAME)));
    await renderView();
    await waitFor(() => expect(screen.getByTestId("tc-regime-common")).toBeTruthy());
    expect(rowsOf()).toEqual(["common"]);
    const row = screen.getByTestId("tc-regime-common");
    expect(row.textContent).toContain("아침·당일 공통(11/11 마감)");
    expect(within(row).getByTestId("tc-regime-score").textContent).toBe("-4점");
    expect(row.textContent).toContain("11/11 마감 뒤 저장");
    const box = screen.getByTestId("tc-now-regime").textContent ?? "";
    expect(box).toBe("당일 판정 — 아침과 같은 11/11 마감 뒤 저장값 기준 하락장(24거래일째) · 판정 근거는 위 아침 요약 · 아래 표");
    expect(box).not.toContain("판정 근거:");
    // POC6-32 V2 — 복사 대조 = 같은 선택 결과(당일 판정 11/11 마감 뒤 · 시장 판정 응답 11/6 이 아님) · 같으면 서버 글 그대로
    fetchMarketCommonEvidence.mockResolvedValue(commonEv({ regime_price_date: "2026-11-11", regime_price_state: "after_close" }));
    fireEvent.click(copyBtn());
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(writeText.mock.calls[0][0]).toBe(DAILY);
    // 화면이 판정 가격 행(마감 뒤)을 보이면 그 상태도 대조 — 응답이 장중 저장이면 복사하지 않는다
    fetchMarketCommonEvidence.mockResolvedValue(commonEv({ regime_price_date: "2026-11-11", regime_price_state: "intraday" }));
    fireEvent.click(copyBtn());
    await waitFor(() => expect(copyMsg()).toBe(`${COPY_BASIS_DIFFERS}(다른 항목: 시장 판정 가격 상태(장중 · 마감 뒤))`));
    expect(writeText).toHaveBeenCalledTimes(1);
  });

  it.each<[string, () => MorningBasisResponse]>([
    ["새 당일 자료(당일 판정 11/12)", () => withToday(ok({ date: "2026-11-12", close: 84240, state: "after_close", fetched_at_kst: "2026-11-12T15:56:59+09:00" }, { ...MORNING_CTX, regime_score: -2 } as typeof MORNING_CTX))],
    ["같은 날이지만 당일 행이 장중 저장", () => withToday(ok({ ...SAME, state: "intraday", fetched_at_kst: "2026-11-11T10:00:00+09:00" }))],
    ["아침 판정 미확인", () => withToday(ok(SAME), { morning_regime: { status: "unconfirmed", basis_date: "2026-11-11", reason: "KODEX 200 11/11 마감 가격 미확인", context: null } })],
    [
      "기준일 행 종가가 다름(같은 행인지 확인 불가)",
      () => {
        const m = withToday(ok(SAME));
        return { ...m, items: m.items.map((i) => (i.key === "kodex200" ? { ...i, basis_row: { date: "2026-11-11", close: 85000, state: "after_close" as const } } : i)) };
      },
    ],
    ["당일 판정 칸 없음(옛 서버)", () => morningOk()],
  ])("D2 — %s → 아침 · 당일 두 행(각각의 기준 · 상태)", async (_t, mb) => {
    fetchMorningBasis.mockResolvedValue(mb());
    await renderView();
    await waitFor(() => expect(screen.getByTestId("tc-regime-today")).toBeTruthy());
    expect(rowsOf()).toEqual(["morning", "today"]);
    expect(screen.getByTestId("tc-now-regime").textContent).toMatch(/^당일 판정 — 국내 시장은/);
  });

  it("D1 — 행마다 그 행 판정의 점수 · 확인 못 한 행은 '확인 불가' · [?] = 서버가 준 경계값으로 만든 산식 + 이동평균 한계", async () => {
    fetchMorningBasis.mockResolvedValue(
      withToday(ok({ date: "2026-11-12", close: 84240, state: "after_close", fetched_at_kst: "2026-11-12T15:56:59+09:00" }, { ...MORNING_CTX, regime_score: 2 } as typeof MORNING_CTX), {
        morning_regime: { status: "unconfirmed", basis_date: "2026-11-11", reason: "KODEX 200 11/11 마감 가격 미확인", context: null },
      }),
    );
    await renderView();
    await waitFor(() => expect(within(screen.getByTestId("tc-regime-today")).getByTestId("tc-regime-score").textContent).toBe("+2점"));
    expect(within(screen.getByTestId("tc-regime-morning")).getByTestId("tc-regime-score").textContent).toBe("확인 불가");
    const rule = screen.getByTestId("tc-score-rule").querySelector(".tc-src-pop")?.textContent ?? "";
    expect(rule).toContain("20거래일 수익률 +2% 이상 +1 · -2% 이하 -1 · 그 사이 0");
    expect(rule).toContain("60거래일 수익률 +5% 이상 +1 · -5% 이하 -1 · 그 사이 0");
    expect(rule).toContain("현재가가 20일 이동평균 위 +1 · 같거나 아래 -1");
    expect(rule).toContain("+2점 이상 상승장 · -2점 이하 하락장 · 그 사이 보합장");
    expect(rule).toContain("미래의 추세 전환을 예측하는 값은 아닙니다");
  });

  // 독립 검토 지적(2026-11-13) — 실패 사유 한 곳 · 아침 줄 '불러오는 중' 고착 · 복사 안 두 날짜
  it("두 응답 모두 못 쓰면 상자 · 표 '당일' 줄이 같은 사유 · 아침 줄도 실패를 알림 · 복사는 서버 판정이 있으면 '근거 다름'으로 멈춤", async () => {
    fetchMarketTopnLatest.mockRejectedValue(new Error("x"));
    fetchMorningBasis.mockRejectedValue(new Error("x"));
    await renderView();
    await waitFor(() => expect(screen.getByTestId("tc-now-regime").textContent).toBe("당일 판정을 불러오지 못했습니다"));
    expect(screen.getByTestId("tc-regime-today").textContent).toContain("당일 판정을 불러오지 못했습니다");
    expect(screen.getByTestId("tc-regime-morning").textContent).toContain("아침 요약 기준을 불러오지 못했습니다");
    expect(screen.getByTestId("tc-score-rule").querySelector(".tc-src-pop")?.textContent).toContain("점수 산식을 불러오지 못했습니다");
    // POC6-32 V2 — 화면엔 판정이 없는데 서버 글에는 있음 → 복사하지 않음(화면 사유로 서버 글을 고치지 않음)
    fireEvent.click(copyBtn());
    await waitFor(() => expect(copyMsg()).toBe(`${COPY_BASIS_DIFFERS}(다른 항목: 시장 판정 · 시장 판정 가격 기준일)`));
    expect(writeText).not.toHaveBeenCalled();
    // 서버도 판정을 확인하지 못했으면(같은 '없음') 기준이 같다 — 확인 창 뒤 서버 글 그대로(판정 '확인 불가'는 서버 글이 적음)
    fetchMarketCommonEvidence.mockResolvedValue(commonEv({ regime_label: null, regime_price_date: null, regime_price_state: null }));
    fireEvent.click(copyBtn());
    fireEvent.click(await screen.findByRole("button", { name: "이 자료로 계속" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(writeText.mock.calls[0][0]).toBe(DAILY);
  });

  it("시장 판정 응답만 실패하고 아침 기준의 당일 판정이 있으면 그 판정(이름 · 가격일 · 상태)으로 대조 · 같으면 서버 글 그대로", async () => {
    fetchMarketTopnLatest.mockRejectedValue(new Error("x"));
    fetchMorningBasis.mockResolvedValue(withToday(ok({ date: "2026-11-06", close: 84240, state: "after_close", fetched_at_kst: "2026-11-06T15:56:59+09:00" })));
    await renderView();
    await waitFor(() => expect(screen.getByTestId("tc-now-regime").textContent).toContain("KODEX 200 11/6 가격(15:56 마감 뒤 저장)"));
    fireEvent.click(copyBtn());
    // 시장 판정 응답 실패 = 코스피 행 확인 필요 → 확인 창(그 사이 대조는 이미 통과 · '근거 다름' 안내 없음)
    const dlg = await screen.findByTestId("tc-stale-dialog");
    expect(screen.queryByTestId("tc-copy-message")).toBeNull(); // 검토 F3 — 창이 열리면 '읽는 중' 안내를 내림
    fireEvent.click(within(dlg).getByRole("button", { name: "이 자료로 계속" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(writeText.mock.calls[0][0]).toBe(DAILY);
  });

  it("검증자 F11 — 복사 확인 창이 열린 동안 화면 판정이 바뀌면(아침 기준 도착) 받아 둔 글을 복사하지 않고 창을 닫는다 · 다시 누르면 새 판정", async () => {
    prime("late"); // 외국인 수급이 늦어 복사 전에 확인 창이 열린다
    let resolveMorning!: (v: unknown) => void;
    fetchMorningBasis.mockReset().mockImplementation(() => new Promise((r) => (resolveMorning = r)));
    await renderView();
    await waitFor(() => expect(screen.getByTestId("tc-now-regime").textContent).toContain("하락장(21거래일째)"));
    fireEvent.click(copyBtn());
    expect(await screen.findByRole("button", { name: "이 자료로 계속" })).toBeInTheDocument();
    // 창이 열린 사이 아침 기준 도착 — 같은 읽기의 당일 판정(상승장 1거래일째 · 11/12 15:56 마감 뒤)
    const up = { ...MORNING_CTX, regime_label: "상승장", regime_code: "bull", regime_score: 2, regime_streak: { regime_code: "bull", streak_days: 1, at_least: false } } as typeof MORNING_CTX;
    const row = { date: "2026-11-12", close: 84240, state: "after_close" as const, fetched_at_kst: "2026-11-12T15:56:59+09:00" };
    await act(async () => resolveMorning(withToday(ok(row, up))));
    await waitFor(() => expect(screen.getByTestId("tc-now-regime").textContent).toContain("상승장(1거래일째)"));
    // 받아 둔(이전 판정) 글은 복사하지 않는다 — 창이 닫히고 다시 누르라는 안내
    expect(screen.queryByRole("button", { name: "이 자료로 계속" })).toBeNull();
    expect(screen.getByTestId("tc-copy-message").textContent).toBe("복사에 쓰는 시장 자료가 바뀌어 복사를 멈췄습니다 — 다시 눌러 주세요.");
    expect(writeText).not.toHaveBeenCalled();
    // 다시 누르면 새로 읽은 공통 근거가 지금 화면 판정(상승장 · 11/12 마감 뒤)과 대조된다 — 같으면 그 글 그대로
    fetchMarketCommonEvidence.mockResolvedValue(
      commonEv({ regime_label: "상승장", regime_price_date: "2026-11-12", regime_price_state: "after_close" }, { daily_text: "상승장 글(합성)" }),
    );
    fireEvent.click(copyBtn());
    fireEvent.click(await screen.findByRole("button", { name: "이 자료로 계속" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(writeText.mock.calls[0][0]).toBe("상승장 글(합성)");
  });

  // 설계자 정리(2026-11-13 · 마감 뒤) — 아침 요약의 원/달러 · WTI 는 원/달러가 기준일을 채웠을 때만 값 문장(과거 사건 없음)
  it.each<[string, boolean]>([
    ["원/달러가 기준일 충족 → 값 문장", true],
    ["원/달러가 늦음 → 문장 없음(근거 표에서)", false],
  ])("아침 요약 원/달러 · WTI — %s", async (_t, met) => {
    const f = flow1109();
    fetchMarketFlowContext.mockResolvedValue({
      ...f,
      short_lines: [...f.short_lines, { text: "원/달러 11/6 · …", flags: [], key: "usdkrw", obs: { ...OBS_1106, date: "2026-11-06", value: 1341.91, d1: { from_date: "2026-11-05", diff: -1.93, pct: -0.14 }, d5: null, range: null } }],
    });
    const mb = morningOk();
    fetchMorningBasis.mockResolvedValue({ ...mb, items: mb.items.map((i) => (i.key === "usdkrw" ? { ...i, met, state: met ? "fresh" : "late" } : i)) });
    await renderView();
    await waitFor(() => expect(screen.getByTestId("tc-morning-ready")).toBeTruthy());
    const fx = screen.queryByTestId("tc-morning-fxwti");
    if (met) {
      expect(fx?.textContent).toContain("원/달러는 11/6 1,341.91원(직전 대비 -1.93원)입니다.");
      expect(fx?.textContent).not.toMatch(/평소 변화의|저점|고점/);
    } else expect(fx).toBeNull();
  });

  it("D3 — 판정 표 이동평균 = 가격 + 현재가와의 거리(그 행 판정의 같은 응답 값)", async () => {
    const ctx = { ...MORNING_CTX, kodex200: { ...(MORNING_CTX.kodex200 as object), ma20: 87415, ma20_distance_pct: -3.63, ma60: 100419, ma60_distance_pct: -16.11 } } as typeof MORNING_CTX;
    fetchMorningBasis.mockResolvedValue(withToday(ok(SAME, ctx), { morning_regime: { status: "ok", basis_date: "2026-11-11", reason: null, context: ctx } }));
    await renderView();
    await waitFor(() => expect(screen.getByTestId("tc-regime-common")).toBeTruthy());
    const t = screen.getByTestId("tc-regime-common").textContent ?? "";
    expect(t).toContain("84,540원 · 20일선 87,415원 · 3.63% 아래 · 60일선 100,419원 · 16.11% 아래");
  });
});
