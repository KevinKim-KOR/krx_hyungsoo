// POC6-16 — 「오늘의 투자 점검」 맨 위 「지금 확인할 내용」 관통 시험(실제 화면 · 가짜 응답 · PLAN 판정 V1.1 §2 · §3 · §3-1 · §4 · §6).
//
// - 첫 진입 = 기존 7개 + 연구 1개 · 왕복 = 캐시 재사용 · [요약 다시 읽기] = 저장 자료 6개만(후보 목록 · OCI · 명령 0).
// - 다시 읽기 중복 클릭 막음 · 다 끝난 뒤 완료 / 일부 실패 · 실패 줄은 이전 값 + 그 값을 받은 시각.
// - 「지금 할 일」 = 기존 정비 점검이 알린 것만 · 갱신 화면 이동(명령 아님) · 해소되면 사라짐 · 연구 대기는 할 일 아님.
// - 줄마다 주요 이동 하나 · 같은 화면 이동은 목적 카드로 스크롤 + 포커스.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within, act } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import { DATA as FWD } from "../ml_forward/testFixtures";

const fetchMarketTopnLatest = vi.fn();
const fetchEnrichedHoldings = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
const fetchNavDiscountLatest = vi.fn();
const fetchBenchmarkSeries = vi.fn();
const refreshMarket = vi.fn();
const fetchOciStartupStatus = vi.fn();
const fetchMarketFlowContext = vi.fn();
const fetchForwardComparison = vi.fn();

vi.mock("@/lib/api", () => ({
  fetchMarketTopnLatest: (...a: unknown[]) => fetchMarketTopnLatest(...a),
  fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
  fetchHoldingsMarketEvidence: (...a: unknown[]) => fetchHoldingsMarketEvidence(...a),
  fetchNavDiscountLatest: (...a: unknown[]) => fetchNavDiscountLatest(...a),
  fetchBenchmarkSeries: (...a: unknown[]) => fetchBenchmarkSeries(...a),
  refreshMarket: (...a: unknown[]) => refreshMarket(...a),
  fetchOciStartupStatus: (...a: unknown[]) => fetchOciStartupStatus(...a),
}));
vi.mock("@/lib/api/marketFlow", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return { ...actual, fetchMarketFlowContext: (...a: unknown[]) => fetchMarketFlowContext(...a) };
});
vi.mock("@/lib/api/mlForwardComparison", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return { ...actual, fetchForwardComparison: (...a: unknown[]) => fetchForwardComparison(...a) };
});

import TodayInvestmentCheckView from "../TodayInvestmentCheckView";

function marketOk(kospiState: "ok" | "stale" = "stale") {
  return {
    status: "ok",
    asof: "2026-10-23",
    basis: "one_month",
    n: 10,
    filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
    candidates: [
      { ticker: "A1", name: "가", selected_return_pct: 11.4873, selected_basis_start_date: "2026-09-23", selected_basis_end_date: "2026-10-23" },
      { ticker: "B2", name: "나", selected_return_pct: 9.702, selected_basis_start_date: "2026-09-23", selected_basis_end_date: "2026-10-23" },
    ],
    daily_topn: [],
    one_month_topn: [],
    three_month_topn: [],
    market_context: {
      status: "ok",
      asof: "2026-10-23",
      regime_label: "하락장",
      regime_code: "bear",
      warnings: [],
      kodex200: { status: "ok", ma20_distance_pct: -1, ma60_distance_pct: -2, ma20_position: "below", ma60_position: "below" },
      kospi:
        kospiState === "ok"
          ? { status: "ok", display_state: "ok", as_of_date: "2026-10-23", daily_return_pct: -1 }
          : { status: "stale", display_state: "stale", as_of_date: "2026-10-22", trading_day_lag: 6 },
      regime_streak: { regime_code: "bear", streak_days: 11, at_least: false },
      primary_benchmark: "KODEX200",
      regime_reasons: [],
    },
    market_risk_reference: {
      kodex200: { availability: "available", as_of_date: "2026-10-23", recent_20d_series: [] },
      vix:
        kospiState === "ok"
          ? { availability: "available", as_of_date: "2026-10-22", recent_20d_series: [], freshness: { state: "fresh" } }
          : { availability: "available", as_of_date: "2026-10-22", recent_20d_series: [] },
    },
  };
}
const EVIDENCE = {
  status: "ok",
  asof: "2026-10-23",
  summary: {
    total_holdings_count: 1,
    evidence_unavailable_count: 0,
    constituents_unavailable_count: 0,
    nav_discount_unavailable_count: 0,
  },
  holdings: [],
  warnings: [],
};
const HOLDINGS = { items: [{ ticker: "069500", name: "KODEX200", price_missing: false, eval_amount: 1000, invested_amount: 900 }] };
const NAV = { status: "ok", asof: "2026-10-23", summary: { unavailable_count: 0, failed_count: 0 } };
const SERIES = {
  ticker: "KOSPI",
  availability: "AVAILABLE",
  available_from: "2026-10-01",
  available_to: "2026-10-22",
  series: [
    { date: "2026-10-21", price: 5550 },
    { date: "2026-10-22", price: 5533 },
  ],
};
const FLOW = { today_lines: ["시장 흐름 6개월(10/22까지): 코스피 -13.78%"] };

const READ_FNS = [
  fetchBenchmarkSeries,
  fetchMarketFlowContext,
  fetchEnrichedHoldings,
  fetchHoldingsMarketEvidence,
  fetchNavDiscountLatest,
  fetchForwardComparison,
];

function prime(kospiState: "ok" | "stale" = "stale") {
  fetchMarketTopnLatest.mockResolvedValue(marketOk(kospiState));
  fetchEnrichedHoldings.mockResolvedValue(HOLDINGS);
  fetchHoldingsMarketEvidence.mockResolvedValue(EVIDENCE);
  fetchNavDiscountLatest.mockResolvedValue(NAV);
  fetchBenchmarkSeries.mockResolvedValue(SERIES);
  fetchOciStartupStatus.mockResolvedValue({ reachable: true, overall: "OPERATING", summary_line: "OCI 정상", jobs: [], note: "" });
  fetchMarketFlowContext.mockResolvedValue(FLOW);
  fetchForwardComparison.mockResolvedValue(FWD);
  refreshMarket.mockResolvedValue({});
}

beforeEach(() => {
  __resetQueryCache();
  vi.clearAllMocks();
  prime();
});

const summary = () => screen.getByLabelText("지금 확인할 내용");
const row = (id: string) => summary().querySelector(`[data-row="${id}"]`) as HTMLElement;

async function renderView(onNavigate = vi.fn()) {
  const r = render(<TodayInvestmentCheckView onNavigate={onNavigate} />);
  await waitFor(() => expect(within(row("research")).queryByText("불러오는 중")).toBeNull());
  await waitFor(() => expect(within(row("market")).queryByText("불러오는 중")).toBeNull());
  await waitFor(() => expect(within(row("holdings")).queryByText("불러오는 중")).toBeNull());
  return { ...r, onNavigate };
}

describe("POC6-16 지금 확인할 내용", () => {
  it("첫 진입 = 기존 7개 + 연구 1개 · 명령 0 · 왕복 = 캐시 재사용(새 호출 0)", async () => {
    const { unmount } = await renderView();
    expect(fetchMarketTopnLatest).toHaveBeenCalledTimes(1);
    expect(fetchOciStartupStatus).toHaveBeenCalledTimes(1);
    for (const f of READ_FNS) expect(f).toHaveBeenCalledTimes(1);
    expect(fetchForwardComparison).toHaveBeenCalledWith();
    expect(refreshMarket).not.toHaveBeenCalled();
    unmount();
    vi.clearAllMocks();
    prime();
    render(<TodayInvestmentCheckView onNavigate={vi.fn()} />);
    await screen.findByText("코스피 가격 흐름");
    expect(fetchMarketTopnLatest).not.toHaveBeenCalled();
    for (const f of READ_FNS) expect(f).not.toHaveBeenCalled();
  });

  it("배치: 머리말 → 지금 확인할 내용(할 일 → 판단 → 자료 · 연구) → KOSPI 카드 → 아래 두 카드", async () => {
    await renderView();
    const before = (a: Element, b: Element) =>
      expect(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const tasks = screen.getByRole("region", { name: "지금 할 일" });
    const judge = screen.getByRole("group", { name: "투자 판단에 볼 것" });
    const data = screen.getByRole("group", { name: "자료 · 연구 상태" });
    before(tasks, judge);
    before(judge, data);
    before(summary(), screen.getByLabelText("KOSPI 현재 위치"));
    before(screen.getByLabelText("KOSPI 현재 위치"), screen.getByLabelText("보유 · 잘 오르는 ETF 자세히"));
    expect(Array.from(judge.querySelectorAll("[data-row]")).map((e) => e.getAttribute("data-row"))).toEqual([
      "market",
      "holdings",
      "candidates",
    ]);
    expect(Array.from(data.querySelectorAll("[data-row]")).map((e) => e.getAttribute("data-row"))).toEqual(["data", "research"]);
  });

  it("요약 = 원래 구역 값(시장 판정 · KOSPI 기준일 · 잘 오르는 ETF 수 · 연구 결론)", async () => {
    await renderView();
    const card = screen.getByLabelText("KOSPI 현재 위치");
    expect(within(row("market")).getByText("하락장 · 11거래일째")).toBeInTheDocument();
    expect(row("market").textContent).toContain("KOSPI 기준일 2026-10-22 · 6거래일 지연");
    expect(card.textContent).toContain("KOSPI 기준일 2026-10-22 · 6거래일 지연");
    const detail = screen.getByLabelText("보유 · 잘 오르는 ETF 자세히");
    expect(within(row("candidates")).getByText("1개월 수익률 상위 2개")).toBeInTheDocument();
    expect(within(detail).getByText("1개월 수익률 상위 2개")).toBeInTheDocument();
    expect(within(row("research")).getByText("아직 비교할 결과가 없습니다")).toBeInTheDocument();
  });

  it("[요약 다시 읽기] = 저장 자료 6개만 원천별 1번 · 후보 목록 · OCI · 명령 0 · 중복 클릭 막음 · 완료 표시", async () => {
    await renderView();
    vi.clearAllMocks();
    prime();
    let release!: () => void;
    fetchHoldingsMarketEvidence.mockImplementation(
      () => new Promise((r) => (release = () => r(EVIDENCE))),
    );
    const btn = screen.getByRole("button", { name: "요약 다시 읽기" });
    fireEvent.click(btn);
    const running = await screen.findByRole("button", { name: "다시 읽는 중..." });
    expect(running).toBeDisabled();
    fireEvent.click(running);
    // 다 끝나기 전에는 완료를 보이지 않는다 · 도는 동안 [업데이트](POST 뒤 다시 읽기)도 막힌다(검토 지적 4 · 11)
    expect(screen.queryByTestId("tc-reload-state")).toBeNull();
    expect(within(screen.getByLabelText("자료 최신화 필요")).queryAllByRole("button", { name: "업데이트" }).every((b) => (b as HTMLButtonElement).disabled)).toBe(true);
    await act(async () => release());
    await screen.findByText(/^다시 읽기 완료 · /);
    // 안내 문장은 다시 읽기 뒤에도 그대로(검토 지적 1)
    expect(screen.getByTestId("tc-reload-note").textContent).toContain("시장 판정 · 요즘 잘 오르는 ETF 목록은 다시 계산하지 않습니다");
    for (const f of READ_FNS) expect(f).toHaveBeenCalledTimes(1);
    expect(fetchMarketTopnLatest).not.toHaveBeenCalled();
    expect(fetchOciStartupStatus).not.toHaveBeenCalled();
    expect(refreshMarket).not.toHaveBeenCalled();
  });

  it("다시 읽기 일부 실패 — 실패 원천만 이전 값 + 그 시각 · 다른 줄은 새 값 · 완료로 위장 안 함", async () => {
    await renderView();
    fetchHoldingsMarketEvidence.mockRejectedValueOnce(new Error("x"));
    fetchForwardComparison.mockResolvedValueOnce({ ...FWD, status: "NO_RECORDS" });
    fireEvent.click(screen.getByRole("button", { name: "요약 다시 읽기" }));
    expect(await screen.findByText(/^다시 읽기 일부 실패\(보유 근거\)/)).toBeInTheDocument();
    expect(row("holdings").textContent).toMatch(/보유 근거: 다시 읽기 실패 · \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}에 읽은 값을 표시 중/);
    expect(within(row("research")).getByText("예측 기록 없음")).toBeInTheDocument();
    expect(row("research").textContent).not.toContain("다시 읽기 실패");
    // 보유 근거로 만든 정비 항목을 보이는 자료 확인 줄에도 그 값의 시각(검토 지적 3)
    expect(row("data").textContent).toMatch(/보유 근거: 다시 읽기 실패 · \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}에 읽은 값을 표시 중/);
  });

  it("[업데이트](POST 뒤 다시 읽기)가 도는 동안 [요약 다시 읽기]는 막힘 — 같은 조회가 겹쳐 POST 전 값으로 완료되지 않게(검토 지적 4)", async () => {
    // 보유 현재가 결측 1건 → [업데이트] 버튼이 생긴다.
    fetchEnrichedHoldings.mockResolvedValue({ items: [{ ...HOLDINGS.items[0], price_missing: true }] });
    await renderView();
    let done!: () => void;
    refreshMarket.mockImplementation(() => new Promise((r) => (done = () => r({}))));
    fireEvent.click(within(screen.getByLabelText("자료 최신화 필요")).getByRole("button", { name: "업데이트" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "요약 다시 읽기" })).toBeDisabled());
    await act(async () => done());
    await waitFor(() => expect(screen.getByRole("button", { name: "요약 다시 읽기" })).not.toBeDisabled());
  });

  it("지금 할 일 — 시장 자료 지연이면 기본 노출 · 갱신 화면 이동(명령 0) · 지연 없으면 없음", async () => {
    const { onNavigate } = await renderView();
    const tasks = screen.getByRole("region", { name: "지금 할 일" });
    expect(tasks.textContent).toContain("시장 자료 갱신이 필요합니다.");
    expect(tasks.textContent).toContain("지금 PC에 저장된 시장 자료: KOSPI 2026-10-22 · ETF 가격 2026-10-23");
    expect(tasks.textContent).toContain("이동 후 [최신 시장 데이터 갱신]을 눌러 주세요.");
    fireEvent.click(within(tasks).getByRole("button", { name: "시장 자료 갱신 화면" }));
    expect(onNavigate).toHaveBeenCalledWith("market_discovery");
    expect(refreshMarket).not.toHaveBeenCalled();
    // 같은 작업의 강조 버튼은 한 곳(요약 자료 확인 줄은 목록 이동만 · 보조)
    expect(screen.getAllByRole("button", { name: "시장 자료 갱신 화면" })).toHaveLength(1);
  });

  it("지연이 없고 정비 항목도 없으면 할 일 없음 · 연구 대기는 할 일이 아님", async () => {
    prime("ok");
    await renderView();
    expect(screen.queryByRole("region", { name: "지금 할 일" })).toBeNull();
    expect(within(row("data")).getByText("갱신 필요 없음")).toBeInTheDocument();
    expect(within(row("research")).getByText("아직 비교할 결과가 없습니다")).toBeInTheDocument();
  });

  it("첫 조회 실패(보유) — 상태 모름 안내 + 다시 읽기 · 미갱신으로 단정 안 함 · 다른 줄은 정상", async () => {
    prime("ok");
    fetchEnrichedHoldings.mockRejectedValue(new Error("x"));
    await renderView();
    const tasks = screen.getByRole("region", { name: "지금 할 일" });
    expect(tasks.textContent).toContain("자료 상태를 확인하지 못했습니다. 다시 읽어 주세요.");
    expect(tasks.textContent).not.toContain("시장 자료 갱신이 필요합니다");
    expect(within(row("holdings")).getByText("불러오지 못함")).toBeInTheDocument();
    expect(within(row("market")).getByText("하락장 · 11거래일째")).toBeInTheDocument();
  });

  it("버튼 — 줄마다 주요 이동은 하나(자료 확인 줄은 보조만) · 이동 목적지", async () => {
    const { onNavigate } = await renderView();
    const primaries = (id: string) =>
      Array.from(row(id).querySelectorAll(".tc-sum-go button")).filter((b) => !b.classList.contains("tc-fold-btn"));
    expect(primaries("market").map((b) => b.textContent)).toEqual(["시장 흐름 자세히"]);
    expect(primaries("holdings").map((b) => b.textContent)).toEqual(["확인 근거 보기"]);
    expect(primaries("candidates").map((b) => b.textContent)).toEqual(["요즘 잘 오르는 ETF"]);
    expect(primaries("research").map((b) => b.textContent)).toEqual(["예측과 결과 비교"]);
    expect(primaries("data")).toHaveLength(0);
    for (const [id, name, key] of [
      ["market", "시장 흐름 자세히", "market_discovery"],
      ["holdings", "확인 근거 보기", "holdings_evidence"],
      ["holdings", "보유 현황 보기", "holdings"],
      ["candidates", "ETF 비교하기", "workbench"],
      ["research", "예측과 결과 비교", "ml"],
    ] as const) {
      fireEvent.click(within(row(id)).getByRole("button", { name }));
      expect(onNavigate).toHaveBeenLastCalledWith(key);
    }
  });

  it("같은 화면 이동 — 목적 카드로 스크롤하고 포커스(키보드) · 화면 전환 없음", async () => {
    const spy = vi.fn();
    Element.prototype.scrollIntoView = spy;
    const { onNavigate } = await renderView();
    fireEvent.click(within(row("market")).getByRole("button", { name: "KOSPI 차트 ↓" }));
    expect(document.activeElement).toBe(screen.getByLabelText("KOSPI 현재 위치"));
    fireEvent.click(within(row("data")).getByRole("button", { name: "자료 최신화 목록 ↓" }));
    expect(document.activeElement).toBe(screen.getByLabelText("자료 최신화 필요"));
    expect(spy).toHaveBeenCalledTimes(2);
    expect(onNavigate).not.toHaveBeenCalled();
  });

  // 검증자 r1 F1 — 원천 7개 × 첫 조회 실패(이전 값 없음): 요약 안에서 빠지지 않고 · 정비 점검 원천이면 '갱신 필요 없음'이 아니다.
  it.each([
    ["시장 목록", fetchMarketTopnLatest, true, "market_unknown"],
    ["KOSPI 가격 흐름", fetchBenchmarkSeries, false, "read_failed"],
    ["수급 · 환율 · 유가", fetchMarketFlowContext, false, "read_failed"],
    ["보유", fetchEnrichedHoldings, true, "read_failed"],
    ["보유 근거", fetchHoldingsMarketEvidence, true, "read_failed"],
    ["ETF 기준가", fetchNavDiscountLatest, true, "read_failed"],
    ["연구", fetchForwardComparison, false, "read_failed"],
  ] as const)("첫 조회 실패 — %s", async (_name, fn, checksData, taskId) => {
    prime("ok");
    fn.mockRejectedValue(new Error("x"));
    render(<TodayInvestmentCheckView onNavigate={vi.fn()} />);
    await waitFor(() => expect(summary().textContent).toMatch(/불러오지 못/));
    await waitFor(() => expect(within(row("data")).queryByText("확인 중")).toBeNull());
    const tasks = screen.getByRole("region", { name: "지금 할 일" });
    expect(tasks.querySelector(`[data-task="${taskId}"]`)).not.toBeNull();
    expect(tasks.textContent).not.toContain("시장 자료 갱신이 필요합니다");
    if (checksData) expect(within(row("data")).queryByText("갱신 필요 없음")).toBeNull();
  });

  it("연구 줄 — 실제 예측 기준일 범위(보고 만든 시각과 따로)", async () => {
    await renderView();
    expect(row("research").textContent).toContain(
      "예측이 기록된 기준일 2개(2026-10-27 ~ 2026-10-29) · 비교 보고에 들어간 기준일 3개(2026-10-22 ~ 2026-10-29)",
    );
  });

  // 검증자 r2 F3 재현 조합 — 두 원천이 함께 첫 조회 실패해도 '오래됐거나 없는 자료와 함께'라고 하지 않는다 · 실제 결측과 섞일 때만 '함께'.
  it.each([
    ["보유 + NAV", [fetchEnrichedHoldings, fetchNavDiscountLatest], false],
    ["보유 + 보유 근거", [fetchEnrichedHoldings, fetchHoldingsMarketEvidence], false],
    ["시장 목록 + NAV", [fetchMarketTopnLatest, fetchNavDiscountLatest], false],
    ["보유 실패 + 실제 구성종목 결측(대조)", [fetchEnrichedHoldings], true],
  ] as const)("조회 실패 조합 — %s", async (_n, fns, realMissing) => {
    prime("ok");
    if (realMissing) {
      fetchHoldingsMarketEvidence.mockResolvedValue({ ...EVIDENCE, summary: { ...EVIDENCE.summary, constituents_unavailable_count: 25 } });
    }
    for (const f of fns) f.mockRejectedValue(new Error("x"));
    render(<TodayInvestmentCheckView onNavigate={vi.fn()} />);
    await waitFor(() => expect(within(row("data")).queryByText("확인 중")).toBeNull());
    await waitFor(() => expect(row("data").textContent).toMatch(/불러오지 못/));
    const basis = row("data").querySelector(".tc-sum-basis")?.textContent ?? "";
    if (realMissing) expect(basis).toContain("오래됐거나 없는 자료와 불러오지 못한 자료가 함께 있습니다");
    else {
      expect(basis).not.toContain("오래됐거나 없는");
      expect(basis).toMatch(/오래됐다는 뜻은 아님/);
    }
  });
});
