// POC6-27 — 「오늘의 투자 점검」 시장 흐름 · AI 복사 · 목록 조건 공유 · 시장 갱신 이어 보기
// (설계 §3 · §4 · §6 · 사용자 결정 ① ③ · PLAN 판정 §2 · Q3 · Q7 · Q9 · §4).
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, cleanup, screen, fireEvent, waitFor, within, act } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import { setMarketCondition, __resetMarketCondition } from "@/lib/marketConditionStore";
import { setStartedRefreshId, getStartedRefreshId } from "@/lib/marketRefreshMemory";
import { OBS_1106, flowWith } from "@/lib/todayMarketTestFixtures";
import { TODAY_MARKET_PROMPT } from "@/lib/todayMarketCopyText";

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
}

const writeText = vi.fn();
beforeEach(() => {
  __resetQueryCache();
  vi.clearAllMocks();
  prime();
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
  it("종가 · 비교 날짜 대비 → 저점 문장(실제 비교 날짜) → 20 · 60 · 6개월 → 차트 → 외국인 수급 → 최근 큰 변화 2건 · 외 4건", async () => {
    await renderView();
    expect(screen.getByTestId("tc-kospi-close").textContent).toBe("11/6 코스피 종가 5,059.69 -324.11pt (-6.02%) 11/5 대비");
    expect(screen.getByTestId("tc-kospi-close").textContent).toContain("-324.11pt (-6.02%) 11/5 대비");
    expect(screen.getByTestId("tc-kospi-low").textContent).toContain("11/5의 최근 저점 5,383.80을 밑돌았습니다.");
    expect(screen.getByTestId("tc-kospi-low").textContent).not.toContain("직전 거래일");
    fireEvent.click(within(flowCard()).getByRole("button", { name: "근거 보기" }));
    expect(screen.getByTestId("tc-kospi-low-why").textContent).toContain(
      "비교 기준: 직전 20개 저장 종가의 최저 5,383.80(2026-11-05) · 그날 종가 5,059.69(2026-11-06)",
    );
    expect(screen.getByTestId("tc-tile-20").textContent).toBe("20거래일-23.64%11/6 기준");
    expect(screen.getByTestId("tc-tile-60").textContent).toBe("60거래일-19.16%11/6 기준");
    expect(screen.getByTestId("tc-tile-6m").textContent).toBe("6개월 하락-22.39%5/4~11/5 · 수급과 같은 기간");
    const foreign = screen.getByTestId("tc-flow-foreign").textContent ?? "";
    expect(foreign).toContain("6개월 누적 164.3조원 순매도 (124/124일)");
    expect(foreign).toContain("하루 평균 순매도액 1.2조원 → 1.1조원 · 직전 20거래일보다 일평균 매도 감소");
    const changes = screen.getByTestId("tc-flow-changes");
    expect(within(changes).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "11/5 코스피 종가 5,383.80이 10/26 저점 5,469.47을 밑돌았습니다",
      "11/4 WTI가 7.97달러 하락했습니다 · 평소 변화의 3.4배",
    ]);
    expect(changes.textContent).toContain("외 4건");
    // 전체 7건 · 뺀 1건은 펼침 안에.
    const all = screen.getByTestId("tc-flow-events-all");
    expect(all.textContent).toContain("최근 큰 변화 전체 7건 · 위 저점 문장과 같은 1건은 요약에서 뺌");
    expect(within(all).getAllByRole("listitem")).toHaveLength(7);
  });

  it("RESULT 판정 §3-1 — 중간 거래일 저장 종가가 비면(11/5 없음) 화면도 실제 비교 날짜 11/4 로 적는다", async () => {
    const f = flow1109();
    const gap = { ...f.short_lines[0], obs: { ...OBS_1106, d1: { from_date: "2026-11-04", diff: -400, pct: -7.33 }, range: { dir: "아래" as const, bound: 5459.69, bound_date: "2026-11-04" } } };
    fetchMarketFlowContext.mockResolvedValue({ ...f, short_lines: [gap, ...f.short_lines.slice(1)] });
    await renderView();
    expect(screen.getByTestId("tc-kospi-close").textContent).toContain("-400.00pt (-7.33%) 11/4 대비");
    expect(screen.getByTestId("tc-kospi-low").textContent).toContain("11/4의 최근 저점 5,459.69를 밑돌았습니다.");
    expect(screen.getByTestId("tc-market-flow").textContent).not.toMatch(/직전 거래일\(|전일/);
  });

  it("판정 Q9 — 차트는 기존 KospiChart 의 최근 최대 120개 저장일(130개 저장 중)", async () => {
    await renderView();
    expect(within(screen.getByTestId("tc-flow-chart")).getByText(/최근 120개 저장일/)).toBeInTheDocument();
  });

  it("시장 흐름 응답 실패면 수치 · 최근 큰 변화 '불러오지 못함' · 시장 판정 배지는 남는다", async () => {
    fetchMarketFlowContext.mockRejectedValue(new Error("x"));
    render(<TodayInvestmentCheckView onNavigate={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId("tc-flow-changes").textContent).toContain("수급 · 환율 · 유가 자료를 불러오지 못했습니다"));
    expect(screen.getByTestId("tc-kospi-close").textContent).toContain("코스피 종가 확인 불가");
    expect(screen.getByTestId("tc-flow-regime").textContent).toBe("하락장 · 21거래일째");
  });
});

describe("[AI용 시장 정보 복사](설계 §6 · 판정 §4)", () => {
  it("모두 최신이면 바로 복사 · 고정 프롬프트 + 근거", async () => {
    await renderView();
    fireEvent.click(within(flowCard()).getByRole("button", { name: "AI용 시장 정보 복사" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    const text = writeText.mock.calls[0][0] as string;
    expect(text.startsWith(TODAY_MARKET_PROMPT)).toBe(true);
    expect(text).toContain("[코스피 최신 종가] 5,059.69 · 2026-11-06");
    expect(await screen.findByTestId("tc-copy-message")).toHaveTextContent("AI용 시장 정보를 복사했습니다");
  });

  it("늦은 핵심 자료가 있으면 먼저 고르기 · 창이 열린 동안 다시 누를 수 없음 · [취소]면 복사 안 함 · [계속]이면 [자료 상태] 줄과 함께 복사", async () => {
    prime("late");
    await renderView();
    const btn = within(flowCard()).getByRole("button", { name: "AI용 시장 정보 복사" });
    fireEvent.click(btn);
    const dlg = await screen.findByTestId("tc-stale-dialog");
    expect(dlg.querySelector('[data-fresh="flows"]')?.textContent).toContain("1거래일 늦음");
    expect(btn).toBeDisabled();
    expect(screen.getByRole("button", { name: "요약 다시 읽기" })).toBeDisabled();
    fireEvent.click(within(dlg).getByRole("button", { name: "취소" }));
    expect(writeText).not.toHaveBeenCalled();
    fireEvent.click(btn);
    fireEvent.click(within(await screen.findByTestId("tc-stale-dialog")).getByRole("button", { name: "이 자료로 계속" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(writeText.mock.calls[0][0]).toContain("외국인 수급 마지막 2026-11-05 · 기대 2026-11-06(국내 직전 거래일) · 1거래일 늦음");
  });

  it("복사가 실패하면 성공처럼 보이지 않고 글 상자를 펼친다", async () => {
    writeText.mockRejectedValue(new Error("denied"));
    await renderView();
    fireEvent.click(within(flowCard()).getByRole("button", { name: "AI용 시장 정보 복사" }));
    expect(await screen.findByTestId("tc-copy-message")).toHaveTextContent("복사하지 못했습니다 — 아래 글을 직접 선택해 복사하세요.");
    const box = screen.getByRole("textbox", { name: "복사할 시장 정보" }) as HTMLTextAreaElement;
    expect(box.value.startsWith(TODAY_MARKET_PROMPT)).toBe(true);
  });
});

describe("목록 조건 공유(설계 §4 · 판정 §4)", () => {
  it("같은 탭에서 고른 조건(3개월 · 낮은 순 · 제외 없음)으로 읽고 · 두 카드가 실제 응답의 방향을 적는다", async () => {
    setMarketCondition({
      basis: "three_month",
      order: "asc",
      filters: { exclude_inverse: false, exclude_leveraged: false, exclude_synthetic: false, exclude_futures: false },
    });
    fetchMarketTopnLatest.mockResolvedValue(market({ basis: "three_month", order: "asc", filters: { exclude_inverse: false, exclude_leveraged: false, exclude_synthetic: false, exclude_futures: false } }));
    await renderView();
    expect(fetchMarketTopnLatest).toHaveBeenCalledWith(10, {
      basis: "three_month",
      order: "asc",
      excludeInverse: false,
      excludeLeveraged: false,
      excludeSynthetic: false,
      excludeFutures: false,
    });
    expect(within(screen.getByLabelText("잘 오르는 ETF")).getByText("3개월 수익률 낮은 순 2개")).toBeInTheDocument();
    expect(screen.getByLabelText("잘 오르는 ETF 자세히").textContent).toContain("수익률 낮은 순(하락 폭이 큰 순)으로 고른 목록");
  });

  it("새로 고침(공유 조건 비움)이면 기본 조건(저장 기본 기간 · 높은 순 · 4종 제외)", async () => {
    setMarketCondition({ basis: "daily", order: "asc", filters: { exclude_inverse: false, exclude_leveraged: false, exclude_synthetic: false, exclude_futures: false } });
    __resetMarketCondition();
    await renderView();
    expect(fetchMarketTopnLatest).toHaveBeenCalledWith(10, {
      basis: "one_month",
      order: "desc",
      excludeInverse: true,
      excludeLeveraged: true,
      excludeSynthetic: true,
      excludeFutures: true,
    });
  });

  it("조건 목록 조회 실패면 '불러오지 못함'과 요청한 조건(다른 조건의 목록으로 대신하지 않음)", async () => {
    fetchMarketTopnLatest.mockRejectedValue(new Error("x"));
    render(<TodayInvestmentCheckView onNavigate={vi.fn()} />);
    await waitFor(() =>
      expect(screen.getByLabelText("잘 오르는 ETF").textContent).toContain(
        "목록을 불러오지 못했습니다 · 요청한 조건 1개월 수익률 높은 순 · 인버스 · 레버리지 · 합성 · 선물 제외",
      ),
    );
  });
});

describe("검토 정정 — 표시 · 경쟁", () => {
  it("검증자 r1 F1 — [이 자료로 계속]으로 반영한 새 값을 늦게 끝난 첫 조회 응답이 덮지 않는다", async () => {
    prime("late");
    let resolveInit!: (v: unknown) => void;
    fetchMarketFlowContext.mockImplementationOnce(() => new Promise((r) => (resolveInit = r)));
    render(<TodayInvestmentCheckView onNavigate={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId("tc-flow-regime").textContent).not.toContain("불러오는 중"));
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
    expect(screen.getByTestId("tc-flow-foreign").textContent).toContain("하루 평균 순매수 2,500억원 → 순매도 1.1조원");
  });

  it("F9 — 위 문장과 같은 사건만 있고 확인 못 한 자료가 있으면 '없음'을 단정하지 않는다", async () => {
    fetchMarketFlowContext.mockResolvedValue({
      ...flow1109(),
      events: [flowWith().events[0]],
      event_check: { checked: [], unchecked: ["원/달러"], unchecked_text: "원/달러는 자료가 부족해 비교하지 못했습니다", empty_text: null },
    });
    await renderView();
    const box = screen.getByTestId("tc-flow-changes");
    expect(box.textContent).toContain("위 문장 외 확인한 자료에서는 최근 큰 변화 없음");
    expect(box.textContent).toContain("원/달러는 자료가 부족해 비교하지 못했습니다");
  });

  it("F3 — 시장 흐름 · 보유를 불러오는 중에는 「자료 최신화 필요」가 없고 복사 버튼은 막힌다", async () => {
    fetchMarketFlowContext.mockImplementation(() => new Promise(() => undefined));
    fetchEnrichedHoldings.mockImplementation(() => new Promise(() => undefined));
    render(<TodayInvestmentCheckView onNavigate={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId("tc-flow-regime").textContent).not.toContain("불러오는 중"));
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
      prime("late");
      await renderView();
      let resolveFlow!: (v: unknown) => void;
      fetchMarketFlowContext.mockImplementationOnce(() => new Promise((r) => (resolveFlow = r)));
      fireEvent.click(screen.getByRole("button", { name: "요약 다시 읽기" }));
      postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "r1", message: "", cooldown_remaining_seconds: 0 });
      fireEvent.click(screen.getAllByRole("button", { name: "최신 시장 데이터 갱신" })[0]);
      await screen.findByRole("button", { name: "시장 데이터 갱신 중..." });
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
    expect(await screen.findByTestId("tc-market-result")).toHaveTextContent("시장 데이터 갱신 중입니다");
    expect(fetchMarketRefreshStatus).toHaveBeenCalledTimes(1);
    expect(postMarketRefresh).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "시장 데이터 갱신 중..." })).toBeDisabled();
  });

  it("그 사이 끝났으면 완료 처리 · 다시 읽은 자료의 기준일 대조(코스피 그대로 · 수급 11/5 → 11/6)", async () => {
    prime("late");
    setStartedRefreshId("r9");
    let resolveStatus!: (v: unknown) => void;
    fetchMarketRefreshStatus.mockImplementation(() => new Promise((r) => (resolveStatus = r)));
    await renderView();
    fetchMarketFlowContext.mockResolvedValue(flow1109("fresh"));
    await act(async () => resolveStatus({ status: "completed", refresh_id: "r9", error_summary: null, cooldown_remaining_seconds: 21600 }));
    await waitFor(() => expect(screen.getByTestId("tc-market-result").textContent).toContain("시장 데이터 갱신 완료 · 코스피 11/6 그대로 · 외국인 수급 11/5 → 11/6"));
    expect(getStartedRefreshId()).toBeNull();
  });

  it("이 탭에서 시작한 갱신이 없어도 들어올 때 상태 1회 — 진행 중이면 같은 작업으로 이어 봄(POST 없음) · 아니면 줄 없음", async () => {
    fetchMarketRefreshStatus.mockResolvedValue({ status: "running", refresh_id: "r11", cooldown_remaining_seconds: 0 });
    await renderView();
    expect(await screen.findByTestId("tc-market-result")).toHaveTextContent("시장 데이터 갱신 중입니다");
    expect(fetchMarketRefreshStatus).toHaveBeenCalledTimes(1);
    expect(postMarketRefresh).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "시장 데이터 갱신 중..." })).toBeDisabled();
  });

  it("지난 갱신이 끝난 상태 · 대기 중이면 들어올 때 아무 줄도 없다(지난 결과로 완료 처리 · 다시 읽기 없음)", async () => {
    fetchMarketRefreshStatus.mockResolvedValue({ status: "completed", refresh_id: "r12", error_summary: null, cooldown_remaining_seconds: 9000 });
    await renderView();
    await waitFor(() => expect(fetchMarketRefreshStatus).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId("tc-market-result")).toBeNull();
    expect(fetchMarketFlowContext).toHaveBeenCalledTimes(1);
    expect(screen.getAllByRole("button", { name: "최신 시장 데이터 갱신" })[0]).not.toBeDisabled();
  });

  it("'VIX 다시 받기'가 도는 중이면 실패가 아니라 진행 중 안내 · 버튼 막힘(들어올 때 상태 · 누른 뒤 거절 둘 다)", async () => {
    fetchMarketRefreshStatus.mockResolvedValue({ status: "completed", refresh_id: "r12", cooldown_remaining_seconds: 9000, vix_retry: { needed: true, status: "running", refresh_id: "v1" } });
    await renderView();
    expect(await screen.findByTestId("tc-market-result")).toHaveTextContent("VIX 다시 받기가 진행 중이라 시장 데이터 갱신을 시작하지 않았습니다");
    expect(screen.getAllByRole("button", { name: "최신 시장 데이터 갱신" })[0]).toBeDisabled();
    cleanup();
    vi.clearAllMocks();
    prime();
    postMarketRefresh.mockResolvedValue({ status: "vix_retry_running", refresh_id: "v1", message: "VIX 다시 받기가 진행 중입니다.", cooldown_remaining_seconds: 9000 });
    await renderView();
    fireEvent.click(screen.getAllByRole("button", { name: "최신 시장 데이터 갱신" })[0]);
    expect(await screen.findByTestId("tc-market-result")).toHaveTextContent("VIX 다시 받기가 진행 중이라");
    expect(screen.getByTestId("tc-market-result").textContent).not.toContain("실패");
    expect(screen.getAllByRole("button", { name: "최신 시장 데이터 갱신" })[0]).toBeDisabled();
  });

  it("다른 갱신이 기록돼 있으면 이 탭 것의 결과는 모른다 — 원래 버튼(줄 없음)", async () => {
    setStartedRefreshId("r9");
    fetchMarketRefreshStatus.mockResolvedValue({ status: "completed", refresh_id: "r10", cooldown_remaining_seconds: 0 });
    await renderView();
    await waitFor(() => expect(getStartedRefreshId()).toBeNull());
    expect(screen.queryByTestId("tc-market-result")).toBeNull();
    expect(screen.getAllByRole("button", { name: "최신 시장 데이터 갱신" })[0]).not.toBeDisabled();
  });
});
