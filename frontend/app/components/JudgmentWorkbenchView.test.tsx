// POC3-02 Judgment Workbench 핵심 UI 계약 test (§13).
// @/lib/api mock 으로 응답 통제. 실제 네트워크·운영 데이터 미의존.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";

const fetchMarketTopnLatest = vi.fn();
const fetchEnrichedHoldings = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
const fetchNavDiscountLatest = vi.fn();
const fetchPriceSeries = vi.fn();

vi.mock("@/lib/api", () => ({
  fetchMarketTopnLatest: (...a: unknown[]) => fetchMarketTopnLatest(...a),
  fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
  fetchHoldingsMarketEvidence: (...a: unknown[]) => fetchHoldingsMarketEvidence(...a),
  fetchNavDiscountLatest: (...a: unknown[]) => fetchNavDiscountLatest(...a),
  fetchPriceSeries: (...a: unknown[]) => fetchPriceSeries(...a),
}));

import JudgmentWorkbenchView from "./JudgmentWorkbenchView";

function candOk() {
  return {
    status: "ok",
    asof: "2026-07-24",
    candidates: [
      {
        rank: 1,
        ticker: "069500",
        name: "KODEX 200",
        returns: {
          one_month: { return_pct: 5.0 },
          three_month: { return_pct: 12.0 },
        },
        excess_return: { excess_return_pct: 1.5 },
        relative_upside_score: 72.3,
        drawdown_20d: -0.08,
        data_quality: { status: "ok" },
      },
      {
        rank: 2,
        ticker: "139260",
        name: "TIGER 반도체",
        returns: { one_month: { return_pct: -2.0 }, three_month: { return_pct: 3.0 } },
        excess_return: null,
        relative_upside_score: null,
        drawdown_20d: null,
        data_quality: { status: "partial" },
      },
    ],
    daily_topn: [],
    one_month_topn: [],
    three_month_topn: [],
    market_context: { status: "ok", asof: "2026-07-24", regime_label: "보합장", warnings: [] },
    market_risk_reference: {
      kodex200: { availability: "available", as_of_date: "2026-07-24", close: 34000 },
      vix: { availability: "available", as_of_date: "2026-07-03", close: 17.25 },
    },
  };
}
function holdOk() {
  return {
    items: [
      { ticker: "069500", name: "KODEX 200", quantity: 10, avg_buy_price: 30000, invested_amount: 300000, current_price: 34000, price_asof: "x", price_source: "n", eval_amount: 340000, pnl_amount: 40000, pnl_rate_pct: 13.3, buy_weight_pct: null, market_weight_pct: 60, price_missing: false, calc_missing: false },
    ],
  };
}
function evidOk() {
  return {
    status: "ok",
    asof: "2026-07-24",
    holdings_asof: "2026-07-24",
    market_asof: "2026-07-24",
    market_context: null,
    summary: {
      total_holdings_count: 1,
      matched_topn_count: 1,
      not_in_current_topn_count: 0,
      evidence_unavailable_count: 0,
      constituents_available_count: 1,
      constituents_unavailable_count: 2,
      nav_discount_unavailable_count: 0,
    },
    holdings: [
      {
        ticker: "069500",
        name: "KODEX 200",
        holding: {},
        topn_match: { status: "matched_topn_candidate", rank: 1, basis: "1m", candidate_name: "KODEX 200" },
        returns: {},
        excess_return: {},
        short_term_momentum: {},
        constituents_overlap: { status: "ok", overlap_with_market_core: [] },
        nav_discount: { status: "ok", source: "n", asof: "x", nav: 1, market_price: 1, discount_rate_pct: 0.1, flag: null, message: null },
        evidence_notes: [],
      },
    ],
    warnings: [],
  };
}
function navOk() {
  return {
    status: "ok",
    asof: "2026-07-24",
    source: "naver",
    summary: { total_count: 1, ok_count: 1, unavailable_count: 0, failed_count: 0 },
    items: [],
  };
}
function priceOk() {
  return {
    ticker: "069500",
    availability: "AVAILABLE",
    available_from: "2026-07-01",
    available_to: "2026-07-24",
    series: [
      { date: "2026-07-01", price: 33000 },
      { date: "2026-07-24", price: 34000 },
    ],
  };
}

beforeEach(() => {
  __resetQueryCache();
  fetchMarketTopnLatest.mockReset().mockResolvedValue(candOk());
  fetchEnrichedHoldings.mockReset().mockResolvedValue(holdOk());
  fetchHoldingsMarketEvidence.mockReset().mockResolvedValue(evidOk());
  fetchNavDiscountLatest.mockReset().mockResolvedValue(navOk());
  fetchPriceSeries.mockReset().mockResolvedValue(priceOk());
});

describe("Workbench — 표·요약·탭", () => {
  it("후보 표가 종목당 한 행으로 방향 수치(부호/기호)와 함께 표시된다", async () => {
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    expect(await screen.findByText("KODEX 200")).toBeInTheDocument();
    // 1M +5.00% 에 방향 기호(▲).
    expect(screen.getByText(/▲ \+5\.00%/)).toBeInTheDocument();
    // 하락 종목은 ▼.
    expect(screen.getByText(/▼ -2\.00%/)).toBeInTheDocument();
  });

  it("최초 진입에서 가격 시계열을 조회하지 않는다 (N+1 방지 · AC-14/15)", async () => {
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await waitFor(() => expect(fetchMarketTopnLatest).toHaveBeenCalled());
    // 목록만 조회, 종목별 price-series 호출 없음.
    expect(fetchPriceSeries).not.toHaveBeenCalled();
  });

  it("탭 전환 시 이미 성공한 조회를 반복하지 않는다 (AC-16)", async () => {
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    fireEvent.click(screen.getByRole("tab", { name: "보유" }));
    fireEvent.click(screen.getByRole("tab", { name: "후보" }));
    // 후보/보유는 각 1회만.
    expect(fetchMarketTopnLatest).toHaveBeenCalledTimes(1);
    expect(fetchEnrichedHoldings).toHaveBeenCalledTimes(1);
  });
});

describe("Workbench — 선택 상세 + 차트", () => {
  it("종목 선택 시에만 가격 시계열을 조회하고 차트를 펼친다 (AC-8/14)", async () => {
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    const row = await screen.findByText("KODEX 200");
    expect(fetchPriceSeries).not.toHaveBeenCalled();
    fireEvent.click(row);
    // 선택 후에만 조회.
    await waitFor(() => expect(fetchPriceSeries).toHaveBeenCalledWith("069500"));
    // 제공 기간 표시.
    expect(await screen.findByText(/2026-07-01 ~ 2026-07-24/)).toBeInTheDocument();
  });

  it("가격 NO_DATA 는 빈 정상 차트가 아니라 사유를 표시한다 (AC-13)", async () => {
    fetchPriceSeries.mockResolvedValue({
      ticker: "139260",
      availability: "NO_DATA",
      reason: "no_stored_data",
      series: [],
    });
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    fireEvent.click(await screen.findByText("TIGER 반도체"));
    expect(await screen.findByText(/저장된 가격 데이터 없음/)).toBeInTheDocument();
  });
});

describe("Workbench — 확인 필요 / 결측 정직성 / 실패 격리", () => {
  it("확인 필요 탭에 unavailable 건수가 사유·이동과 함께 나온다", async () => {
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    fireEvent.click(screen.getByRole("tab", { name: "확인 필요" }));
    // constituents_unavailable_count=2.
    expect(await screen.findByText(/구성종목 비교 불가 2건/)).toBeInTheDocument();
  });

  it("예외 버튼이 확정된 탭으로 이동한다", async () => {
    const onNavigate = vi.fn();
    render(<JudgmentWorkbenchView onNavigate={onNavigate} />);
    await screen.findByText("KODEX 200");
    fireEvent.click(screen.getByRole("tab", { name: "확인 필요" }));
    fireEvent.click(await screen.findByText("구성종목 확인 →"));
    expect(onNavigate).toHaveBeenCalledWith("etf_exposure");
  });

  it("일부 영역(NAV) 실패해도 후보 표는 유지된다 (AC-19)", async () => {
    fetchNavDiscountLatest.mockRejectedValue(new Error("nav down"));
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    // 후보 정상 렌더.
    expect(await screen.findByText("KODEX 200")).toBeInTheDocument();
  });

  it("후보 status != ok 는 '확인 불가' 로 표시하고 0으로 위장하지 않는다", async () => {
    fetchMarketTopnLatest.mockResolvedValue({ ...candOk(), status: "invalid", candidates: [] });
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    expect(await screen.findByText(/후보 데이터 확인 불가 \(invalid\)/)).toBeInTheDocument();
  });
});

describe("Workbench — 정렬·필터", () => {
  it("정렬 클릭이 표 순서를 바꾸되 원본 데이터를 변경하지 않는다", async () => {
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    // 2026-08-12 카드 전환: 열 헤더 클릭 → 정렬 바 버튼 클릭. 동작은 동일.
    // 카드 안에도 "1M" 지표 라벨이 있으므로 정렬 바 안에서만 찾는다.
    const sortbar = document.querySelector(".holdings-sortbar") as HTMLElement;
    fireEvent.click(within(sortbar).getByText(/^1M/));
    const list = screen.getByTestId("wb-candidate-list");
    const firstDataRow = within(list).getAllByRole("button")[0];
    expect(within(firstDataRow).getByText("TIGER 반도체")).toBeInTheDocument();
  });

  it("보유 중 필터가 보유 종목만 남긴다", async () => {
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    fireEvent.click(screen.getByText("보유 중"));
    // 069500 은 보유, 139260 은 미보유 → 139260 사라짐.
    expect(screen.queryByText("TIGER 반도체")).not.toBeInTheDocument();
    expect(screen.getByText("KODEX 200")).toBeInTheDocument();
  });
});

describe("Workbench — REJECTED 정정 (보유 표 의미·중복·검색·Evidence·KST)", () => {
  it("같은 ticker 다계좌를 한 행으로 집계한다 (A-1(4))", async () => {
    fetchEnrichedHoldings.mockResolvedValue({
      items: [
        { ticker: "069500", name: "KODEX 200", quantity: 10, avg_buy_price: 30000, invested_amount: 300000, current_price: 34000, price_asof: "x", price_source: "n", eval_amount: 340000, pnl_amount: 40000, pnl_rate_pct: 13.3, buy_weight_pct: null, market_weight_pct: 30, price_missing: false, calc_missing: false, account_group: "연금" },
        { ticker: "069500", name: "KODEX 200", quantity: 5, avg_buy_price: 31000, invested_amount: 155000, current_price: 34000, price_asof: "x", price_source: "n", eval_amount: 170000, pnl_amount: 15000, pnl_rate_pct: 9.7, buy_weight_pct: null, market_weight_pct: 20, price_missing: false, calc_missing: false, account_group: "일반" },
      ],
    });
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    fireEvent.click(screen.getByRole("tab", { name: "보유" }));
    const list = await screen.findByTestId("wb-holding-list");
    // 069500 은 한 행만 (2계좌 합산 표기).
    const codeCells = within(list).getAllByText("069500");
    expect(codeCells.length).toBe(1);
    expect(within(list).getByText(/2계좌 합산/)).toBeInTheDocument();
  });

  it("보유 행에 1M·3M·KODEX초과 지표가 있고 '일간=평가수익률' 오류가 없다 (A-1(2)(3))", async () => {
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    fireEvent.click(screen.getByRole("tab", { name: "보유" }));
    const list = await screen.findByTestId("wb-holding-list");
    // 2026-08-12 카드 전환: 열 헤더 → 지표 라벨. 검사 항목은 동일.
    const labels = within(list)
      .getAllByText(/^(일간|1M|3M|KODEX초과)$/)
      .map((el) => el.textContent);
    expect(labels).toContain("1M");
    expect(labels).toContain("3M");
    expect(labels).toContain("KODEX초과");
    // §7.6 명시 항목 "일간" 은 자리를 두되 값은 미제공(—).
    expect(labels).toContain("일간");
    const dayCell = within(list).getAllByText("일간")[0].parentElement!;
    expect(dayCell.textContent).toMatch(/일간—/);
  });

  it("Evidence 없는 보유 종목은 '정상'이 아니라 '확인 불가' 로 표시한다 (A-1(5))", async () => {
    fetchEnrichedHoldings.mockResolvedValue({
      items: [
        { ticker: "305720", name: "KODEX 2차전지", quantity: 1, avg_buy_price: 10000, invested_amount: 10000, current_price: 11000, price_asof: "x", price_source: "n", eval_amount: 11000, pnl_amount: 1000, pnl_rate_pct: 10, buy_weight_pct: null, market_weight_pct: 100, price_missing: false, calc_missing: false },
      ],
    });
    // Evidence 응답에는 305720 이 없음.
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    fireEvent.click(screen.getByRole("tab", { name: "보유" }));
    const list = await screen.findByTestId("wb-holding-list");
    // NAV·구성종목 상태 배지가 분리 → 둘 다 "확인 불가". "정상" 은 없음.
    expect(within(list).getAllByText(/확인 불가/).length).toBeGreaterThan(0);
    expect(within(list).queryByText(/정상/)).not.toBeInTheDocument();
  });

  it("검색 입력으로 ticker/ETF명 필터링한다 (A-1(1))", async () => {
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    const search = screen.getByLabelText("종목 검색");
    fireEvent.change(search, { target: { value: "반도체" } });
    expect(screen.queryByText("KODEX 200")).not.toBeInTheDocument();
    expect(screen.getByText("TIGER 반도체")).toBeInTheDocument();
  });
});

describe("Workbench — REJECTED r2 정정 (요약·교집합·현재가·attention·stale)", () => {
  it("요약 보유 종목 수는 계좌별 원본 행이 아니라 고유 ticker 수다 (A-1)", async () => {
    fetchEnrichedHoldings.mockResolvedValue({
      items: [
        { ticker: "069500", name: "KODEX 200", quantity: 10, avg_buy_price: 1, invested_amount: 1, current_price: 1, price_asof: "x", price_source: "n", eval_amount: 1, pnl_amount: 1, pnl_rate_pct: 1, buy_weight_pct: null, market_weight_pct: 30, price_missing: false, calc_missing: false, account_group: "A" },
        { ticker: "069500", name: "KODEX 200", quantity: 5, avg_buy_price: 1, invested_amount: 1, current_price: 1, price_asof: "x", price_source: "n", eval_amount: 1, pnl_amount: 1, pnl_rate_pct: 1, buy_weight_pct: null, market_weight_pct: 20, price_missing: false, calc_missing: false, account_group: "B" },
      ],
    });
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    // 요약 "보유 1" (2행이지만 고유 ticker 1).
    const summary = document.querySelector(".wb-summary-row")!;
    expect(summary.textContent).toMatch(/보유\s*1/);
  });

  it("'후보에 포함된 보유'는 현재 후보∩현재 보유 교집합이다 (A-1)", async () => {
    // 후보에 069500 있고 보유에도 069500 있음 → 교집합 1.
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    const summary = document.querySelector(".wb-summary-row")!;
    expect(summary.textContent).toMatch(/후보에 포함된 보유\s*1/);
  });

  it("보유 행에 현재가가 있고 NAV·구성종목 상태가 분리된다 (§7.6·A-1)", async () => {
    // 2026-08-16: 정상 상태는 배지를 띄우지 않는다(후보 탭과 동일 규칙). 따라서
    //   "분리 표시" 는 한쪽만 이상일 때 그 쪽만 뜨는 것으로 검사한다 — 정상 배지
    //   존재 검사보다 분리 계약을 더 정확히 확인한다.
    fetchHoldingsMarketEvidence.mockResolvedValue({
      ...evidOk(),
      holdings: [
        {
          ...evidOk().holdings[0],
          nav_discount: { ...evidOk().holdings[0].nav_discount, status: "ok" },
          constituents_overlap: { status: "unavailable", overlap_with_market_core: [] },
        },
      ],
    });
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    fireEvent.click(screen.getByRole("tab", { name: "보유" }));
    const list = await screen.findByTestId("wb-holding-list");
    // 현재가는 행 하단 우측.
    expect(within(list).getAllByText(/현재/).length).toBeGreaterThan(0);
    // 구성종목만 이상 → 구성종목 배지만 뜨고 NAV 배지는 뜨지 않는다.
    expect(within(list).getByText(/구성종목/)).toBeInTheDocument();
    expect(within(list).queryByText(/^NAV/)).not.toBeInTheDocument();
  });

  it("returns 상태가 unavailable 인 보유 종목은 확인 필요로 분류된다 (A-1)", async () => {
    fetchEnrichedHoldings.mockResolvedValue({
      items: [
        { ticker: "099999", name: "테스트ETF", quantity: 1, avg_buy_price: 1, invested_amount: 1, current_price: 1, price_asof: "x", price_source: "n", eval_amount: 1, pnl_amount: 1, pnl_rate_pct: 1, buy_weight_pct: null, market_weight_pct: 100, price_missing: false, calc_missing: false },
      ],
    });
    fetchHoldingsMarketEvidence.mockResolvedValue({
      ...evidOk(),
      holdings: [
        {
          ticker: "099999", name: "테스트ETF", holding: { pnl_rate_pct: 1 },
          topn_match: { status: "not_in_current_topn", rank: null, basis: null, candidate_name: null },
          returns: { status: "unavailable", one_month_return_pct: null, three_month_return_pct: null },
          excess_return: { status: "unavailable", vs_kodex200_1m_pctp: null, vs_kodex200_3m_pctp: null },
          short_term_momentum: {},
          constituents_overlap: { status: "ok", overlap_with_market_core: [] },
          nav_discount: { status: "ok", source: "n", asof: "x", nav: 1, market_price: 1, discount_rate_pct: 0, flag: null, message: null },
          evidence_notes: [],
        },
      ],
    });
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    fireEvent.click(screen.getByRole("tab", { name: "보유" }));
    // "확인 필요" 는 탭·필터 둘 다 존재 → 필터 버튼(.wb-filter)만 클릭.
    const attnFilter = document
      .querySelector(".wb-filters")!
      .querySelectorAll("button");
    fireEvent.click(
      Array.from(attnFilter).find((b) => b.textContent === "확인 필요")!,
    );
    // returns unavailable → 확인 필요 필터에 남는다.
    const list = await screen.findByTestId("wb-holding-list");
    expect(within(list).getAllByText("테스트ETF").length).toBeGreaterThan(0);
  });
});

describe("가격 API 캐시 키 공유", () => {
  it("Workbench Holdings/Evidence/NAV 키는 Dashboard 와 동일하다 (§9)", async () => {
    const {
      DASH_KEY_HOLDINGS, DASH_KEY_EVIDENCE, DASH_KEY_NAV,
      WB_KEY_HOLD, WB_KEY_EVID, WB_KEY_NAV, WB_KEY_CAND, DASH_KEY_MARKET,
    } = await import("@/lib/api/dashboardKeys");
    expect(WB_KEY_HOLD).toBe(DASH_KEY_HOLDINGS);
    expect(WB_KEY_EVID).toBe(DASH_KEY_EVIDENCE);
    expect(WB_KEY_NAV).toBe(DASH_KEY_NAV);
    // Market topn 만 조건(n)이 달라 분리.
    expect(WB_KEY_CAND).not.toBe(DASH_KEY_MARKET);
  });
});

describe("Workbench — REJECTED r3 정정 (현재 교집합·Evidence 상태·weight 결측)", () => {
  it("후보 표 보유여부는 현재 Holdings 목록 기준이다 (Evidence 아님)", async () => {
    // Evidence 는 069500 만 있지만 현재 보유는 139260 (후보 2번).
    fetchEnrichedHoldings.mockResolvedValue({
      items: [
        { ticker: "139260", name: "TIGER 반도체", quantity: 1, avg_buy_price: 1, invested_amount: 1, current_price: 1, price_asof: "x", price_source: "n", eval_amount: 1, pnl_amount: 1, pnl_rate_pct: 1, buy_weight_pct: null, market_weight_pct: 100, price_missing: false, calc_missing: false },
      ],
    });
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    const list = await screen.findByTestId("wb-candidate-list");
    // 2026-08-12 카드 전환: "◆ 보유" 셀 → "보유" 배지. 3-state 구분은 동일.
    const rows = within(list).getAllByRole("button");
    const tigerRow = rows.find((r) => r.textContent?.includes("139260"))!;
    expect(within(tigerRow).getByText("보유")).toBeInTheDocument();
    // 069500 은 현재 보유 아님 → "미보유" 이며 보유 배지는 없다.
    const kodexRow = rows.find((r) => r.textContent?.includes("069500"))!;
    expect(within(kodexRow).getByText("미보유")).toBeInTheDocument();
    expect(within(kodexRow).queryByText("보유")).not.toBeInTheDocument();
  });

  it("보유 표 후보포함은 현재 후보 목록 교집합이며 요약과 정합한다", async () => {
    // 069500 은 후보에도 있고 보유에도 있음 → 후보포함 ◆.
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    const summary = document.querySelector(".wb-summary-row")!;
    expect(summary.textContent).toMatch(/후보에 포함된 보유\s*1/);
    fireEvent.click(screen.getByRole("tab", { name: "보유" }));
    const list = await screen.findByTestId("wb-holding-list");
    const row = within(list)
      .getAllByRole("button")
      .find((r) => r.textContent?.includes("069500"));
    // 2026-08-12 카드 전환: "◆ 후보" 셀 → "후보 포함" 배지. 3-state 구분은 동일.
    expect(row?.textContent).toMatch(/후보 포함/);
  });

  it("Evidence 정상이면 배지를 띄우지 않고, 확인 불가일 때만 띄운다 (2026-08-16)", async () => {
    // 정상 케이스 — 근거 배지 없음.
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    fireEvent.click(screen.getByRole("tab", { name: "보유" }));
    const list = await screen.findByTestId("wb-holding-list");
    expect(within(list).queryByText(/^근거 /)).not.toBeInTheDocument();
  });

  it("Evidence 가 없는 보유 종목은 근거 확인 불가 배지를 띄운다", async () => {
    fetchHoldingsMarketEvidence.mockResolvedValue({ ...evidOk(), holdings: [] });
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    fireEvent.click(screen.getByRole("tab", { name: "보유" }));
    const list = await screen.findByTestId("wb-holding-list");
    expect(within(list).getByText(/근거 확인 불가/)).toBeInTheDocument();
  });

  it("비중 부분 결측이면 유효 건수를 표기한다 (B-1)", async () => {
    fetchEnrichedHoldings.mockResolvedValue({
      items: [
        { ticker: "069500", name: "KODEX 200", quantity: 1, avg_buy_price: 1, invested_amount: 1, current_price: 1, price_asof: "x", price_source: "n", eval_amount: 1, pnl_amount: 1, pnl_rate_pct: 1, buy_weight_pct: null, market_weight_pct: 30, price_missing: false, calc_missing: false, account_group: "A" },
        { ticker: "069500", name: "KODEX 200", quantity: 1, avg_buy_price: 1, invested_amount: 1, current_price: 1, price_asof: "x", price_source: "n", eval_amount: 1, pnl_amount: 1, pnl_rate_pct: 1, buy_weight_pct: null, market_weight_pct: null, price_missing: false, calc_missing: false, account_group: "B" },
      ],
    });
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    fireEvent.click(screen.getByRole("tab", { name: "보유" }));
    const list = await screen.findByTestId("wb-holding-list");
    // 2계좌 중 1계좌만 비중 유효 → (1/2) 표기.
    expect(within(list).getByText(/\(1\/2\)/)).toBeInTheDocument();
  });
});

describe("Workbench — 탭 전환 시 선택 상세 해제 (사용자 지적 2026-08-13)", () => {
  it("탭을 바꾸면 선택이 풀려 이전 탭에서 고른 종목 상세가 남지 않는다", async () => {
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    // 후보 탭에서 한 종목 선택 → 선택 상세가 열린다.
    const list = await screen.findByTestId("wb-candidate-list");
    const row = within(list)
      .getAllByRole("button")
      .find((r) => r.textContent?.includes("069500"))!;
    fireEvent.click(row);
    expect(document.querySelector(".wb-detail")).not.toBeNull();
    // 보유 탭으로 이동 → 선택 해제되어 상세가 닫힌다.
    fireEvent.click(screen.getByRole("tab", { name: "보유" }));
    expect(document.querySelector(".wb-detail")).toBeNull();
  });
});
