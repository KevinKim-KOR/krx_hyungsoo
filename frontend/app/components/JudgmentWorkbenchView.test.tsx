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
        stored_drawdown_20: {
          status: "ok",
          value_pct: -8.0,
          start_date: "2026-06-26",
          end_date: "2026-07-24",
          peak_close: 37000,
          peak_date: "2026-07-10",
          close: 34040,
          rows: 20,
        },
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

  it("보유 행에 1M·3M·동일기간 KODEX 1M 지표가 있고 '일간=평가수익률' 오류가 없다 (A-1(2)(3))", async () => {
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    fireEvent.click(screen.getByRole("tab", { name: "보유" }));
    const list = await screen.findByTestId("wb-holding-list");
    // 2026-08-12 카드 전환: 열 헤더 → 지표 라벨. 검사 항목은 동일.
    const labels = within(list)
      .getAllByText(/^(일간|1M|3M|동일기간 KODEX 1M)$/)
      .map((el) => el.textContent);
    expect(labels).toContain("1M");
    expect(labels).toContain("3M");
    expect(labels).toContain("동일기간 KODEX 1M");
    // POC5-22 Q2 (a) — 보유 근거에 동일 기간 객체가 없으면 '동일 기간 값 없음'(기존 차이로 채우지 않음).
    const exCell = within(list).getAllByText("동일기간 KODEX 1M")[0].parentElement!;
    expect(exCell.textContent).toContain("동일 기간 값 없음");
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

// --- 2026-08-29 POC3-ML-02 REJECT Closeout 계약 -----------------------------
// 픽스처(candOk)에 `relative_upside_score: 72.3` 이 들어 있다. 값이 와도 화면에
// 나오지 않고 순서에도 개입하지 않는 것을 고정한다.
describe("REJECT Closeout — 참고점수 비활성", () => {
  it("C-1 점수·사유·참고점수 라벨이 화면에 없다", async () => {
    const { container } = render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText("KODEX 200")).toBeInTheDocument();
    });
    const text = container.textContent ?? "";
    expect(text).not.toContain("72.3");
    expect(text).not.toContain("참고점수");
  });

  it("C-2 정렬 선택지에 `참고점수` 가 없다 / C-7 나머지 5개는 남는다", async () => {
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText("KODEX 200")).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("button", { name: /참고점수/ }),
    ).not.toBeInTheDocument();
    for (const label of ["순위", "1M", "3M", "동일기간 KODEX 1M", "20저장일 종가 고점 대비"]) {
      expect(
        screen.getByRole("button", { name: new RegExp(`^${label}`) }),
      ).toBeInTheDocument();
    }
  });

  // --- C-3 / C-4 : 원본 · 점수 역순 · 점수 전부 null 세 변형 ---------------
  //
  // 정렬 실동작(C-7)까지 한 픽스처로 보려고 3종목을 쓴다. 각 정렬 키가
  // **서로 다른 순서**를 만들도록 값을 설계했다 (useSort 첫 클릭은 asc).
  //   rank        asc → A B C
  //   one_month   asc → B C A   (A=3 · B=1 · C=2)
  //   three_month asc → C A B   (A=2 · B=3 · C=1)
  //   excess      asc → A C B   (A=1 · B=3 · C=2 · 동일 기간 1M 값 — 기존 excess_return 은 반대 순서 함정)
  //   drawdown    asc → B A C   (POC5-25 현재 저장 종가 % · A=-2 · B=-3 · C=-1 · 옛 drawdown_20d 는 반대 순서 함정)
  function sortTrio(scores: (number | null)[] = [10, 20, 30]) {
    const mk = (
      ticker: string,
      name: string,
      rank: number,
      one: number,
      three: number,
      excess: number,
      dd: number,
      score: number | null,
    ) => ({
      rank,
      ticker,
      name,
      returns: {
        one_month: { return_pct: one },
        three_month: { return_pct: three },
      },
      // POC5-22 — 정렬 · 칸은 동일 기간 값만. 기존 기간 다른 차이는 반대 순서라 섞이면 순서가 틀린다.
      excess_return: { vs_kodex200_1m_pctp: -excess },
      same_period_kodex200: {
        one_month: {
          status: "ok",
          start_date: "2026-09-14",
          end_date: "2026-10-14",
          candidate_return_pct: one,
          kodex200_return_pct: one - excess,
          diff_pctp: excess,
        },
      },
      relative_upside_score: score,
      drawdown_20d: -dd / 100,
      stored_drawdown_20: { status: "ok", value_pct: dd, start_date: "2026-09-16", end_date: "2026-10-14", rows: 20 },
      data_quality: { status: "ok" },
    });
    return {
      ...candOk(),
      candidates: [
        mk("AAA111", "가나다 ETF", 1, 3, 2, 1, -2, scores[0]),
        mk("BBB222", "라마바 ETF", 2, 1, 3, 3, -3, scores[1]),
        mk("CCC333", "사아자 ETF", 3, 2, 1, 2, -1, scores[2]),
      ],
    };
  }

  const TRIO = ["AAA111", "BBB222", "CCC333"];

  function orderIn(container: HTMLElement, tickers: string[]): string[] {
    const text = container.textContent ?? "";
    return tickers
      .map((t) => ({ t, at: text.indexOf(t) }))
      .filter((x) => x.at >= 0)
      .sort((a, b) => a.at - b.at)
      .map((x) => x.t);
  }

  async function renderTrio(scores?: (number | null)[]) {
    fetchMarketTopnLatest.mockReset().mockResolvedValue(sortTrio(scores));
    const utils = render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText("가나다 ETF")).toBeInTheDocument();
    });
    return utils;
  }

  it("C-3 / C-4 원본·점수 역순·점수 전부 null 세 변형의 순서가 모두 같고 API 순서다", async () => {
    const variants: (number | null)[][] = [
      [10, 20, 30], // (a) 원본
      [30, 20, 10], // (b) 점수 역순
      [null, null, null], // (c) 점수 제거
    ];
    const results: string[][] = [];
    for (const scores of variants) {
      const { container, unmount } = await renderTrio(scores);
      results.push(orderIn(container, TRIO));
      unmount();
      __resetQueryCache();
    }
    expect(results[0]).toEqual(TRIO); // C-4 — API 순서 그대로
    expect(results[1]).toEqual(results[0]); // C-3
    expect(results[2]).toEqual(results[0]); // C-3
  });

  it("C-7 정상 정렬 5종이 **실제로 순서를 바꾼다**", async () => {
    const { container } = await renderTrio();
    const order = () => orderIn(container, TRIO);
    const click = (label: string) =>
      fireEvent.click(
        screen.getByRole("button", { name: new RegExp(`^${label}`) }),
      );

    expect(order()).toEqual(TRIO); // 기본 = rank asc

    click("1M");
    expect(order()).toEqual(["BBB222", "CCC333", "AAA111"]);

    click("3M");
    expect(order()).toEqual(["CCC333", "AAA111", "BBB222"]);

    click("동일기간 KODEX 1M");
    expect(order()).toEqual(["AAA111", "CCC333", "BBB222"]);
    // 정렬 값 = 칸에 보이는 값(판정 §2) — 보이는 순서도 +1 · +2 · +3.
    const shown = Array.from(container.querySelectorAll(".wb-hm-cell .v"))
      .map((el) => el.textContent ?? "")
      .filter((t) => t.endsWith("%p"));
    expect(shown).toEqual(["+1.00%p", "+2.00%p", "+3.00%p"]);

    click("20저장일 종가 고점 대비");
    expect(order()).toEqual(["BBB222", "AAA111", "CCC333"]);

    click("순위");
    expect(order()).toEqual(TRIO);

    // 같은 키 재클릭 → desc 전환.
    click("순위");
    expect(order()).toEqual([...TRIO].reverse());
  });
});

// POC5-12 — VIX 최신성은 서버 판정(vix.freshness)만 읽는다(판정 Q1 · 세 화면 같은 판정).
describe("Workbench — VIX 최신성 (POC5-12)", () => {
  async function openAttention() {
    await screen.findByText("KODEX 200");
    fireEvent.click(screen.getByRole("tab", { name: /확인 필요/ }));
  }

  function withVix(vix: Record<string, unknown>) {
    const c = candOk();
    return {
      ...c,
      market_risk_reference: {
        ...c.market_risk_reference,
        vix: { ...c.market_risk_reference.vix, ...vix },
      },
    };
  }

  it("update_check 문구 · 옛 '(시장 …보다 이전)' 없음", async () => {
    fetchMarketTopnLatest.mockResolvedValue(
      withVix({ freshness: { state: "update_check", compare_date: "2026-07-24", weekdays_behind: 15 } }),
    );
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await openAttention();
    expect(
      await screen.findByText("VIX 자료 업데이트 확인 필요(기준일 2026-07-03)"),
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/VIX stale|보다 이전/);
  });

  it("fresh 는 VIX 항목 없음(KODEX200 날짜가 더 늦어도)", async () => {
    fetchMarketTopnLatest.mockResolvedValue(
      withVix({ freshness: { state: "fresh", compare_date: "2026-07-03", weekdays_behind: 0 } }),
    );
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await openAttention();
    await screen.findByText(/구성종목 비교 불가/); // 다른 확인 항목은 보인다
    expect(document.body.textContent).not.toMatch(/VIX 자료 업데이트|VIX 기준일 확인|VIX stale/);
  });

  it("판정 필드 없음 → 'VIX 기준일 확인 필요'(추측 안 함)", async () => {
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await openAttention();
    expect(
      await screen.findByText("VIX 기준일 확인 필요(기준일 2026-07-03)"),
    ).toBeInTheDocument();
  });
});

// POC5-22 — 「ETF 비교하기」 동일 기간 KODEX200 대비 1M(후보 탭 · 보유 탭 · 상세 · 판정 Q2 (a)).
describe("Workbench — 동일 기간 KODEX200 대비 (POC5-22)", () => {
  const SP = (cand: number, kodex: number) => ({
    one_month: {
      status: "ok",
      start_date: "2026-06-24",
      end_date: "2026-07-24",
      candidate_return_pct: cand,
      kodex200_return_pct: kodex,
      diff_pctp: cand - kodex,
    },
  });

  function withSame() {
    const c = candOk();
    const list = c.candidates as unknown as Record<string, unknown>[];
    list[0].same_period_kodex200 = SP(5, -3);
    list[1].same_period_kodex200 = {
      one_month: { status: "unavailable", reason: "kodex200_end_price_missing", start_date: "2026-06-24", end_date: "2026-07-24" },
    };
    return c;
  }

  it("후보 칸 = 동일 기간 값 · 계산 불가는 회색 사유 · 기존 excess_return 은 쓰지 않는다", async () => {
    fetchMarketTopnLatest.mockReset().mockResolvedValue(withSame());
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    const list = await screen.findByTestId("wb-candidate-list");
    expect(within(list).getByText("+8.00%p")).toBeInTheDocument();
    const na = within(list).getByText("KODEX200 끝일 가격 없음");
    expect(na).toHaveClass("sp-na");
    expect(list.textContent).not.toContain("1.50"); // 기존 excess_return_pct 1.5
  });

  it("상세 칸 — 후보면 후보 객체(양쪽 수익률 · 사용 종가 날짜)", async () => {
    fetchMarketTopnLatest.mockReset().mockResolvedValue(withSame());
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    const list = await screen.findByTestId("wb-candidate-list");
    fireEvent.click(within(list).getByText("KODEX 200").closest("[role=button]")!);
    const cell = (await screen.findByText("동일 기간 KODEX200 대비 1M")).parentElement!;
    expect(cell.textContent).toContain("+8.00%p — 후보 +5.00% · KODEX200 -3.00% · 사용 종가 2026-06-24 → 2026-07-24");
  });

  it("보유 탭 — 보유 근거 사본의 동일 기간 객체를 같은 helper 로(없으면 '동일 기간 값 없음')", async () => {
    const ev = evidOk();
    (ev.holdings[0] as Record<string, unknown>).same_period_kodex200 = SP(5, -3);
    fetchHoldingsMarketEvidence.mockReset().mockResolvedValue(ev);
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    fireEvent.click(screen.getByRole("tab", { name: "보유" }));
    const list = await screen.findByTestId("wb-holding-list");
    const cell = within(list).getAllByText("동일기간 KODEX 1M")[0].parentElement!;
    expect(cell.textContent).toContain("+8.00%p");
  });

  it("상세 칸 — 후보 목록에 없는 보유만 고르면 보유 근거 객체 · 없으면 '동일 기간 값 없음'", async () => {
    const hold = holdOk();
    hold.items.push({ ...hold.items[0], ticker: "360750", name: "TIGER 미국S&P500" });
    hold.items.push({ ...hold.items[0], ticker: "133690", name: "TIGER 미국나스닥100" });
    const ev = evidOk();
    ev.holdings.push({ ...ev.holdings[0], ticker: "360750", name: "TIGER 미국S&P500" });
    ev.holdings.push({ ...ev.holdings[0], ticker: "133690", name: "TIGER 미국나스닥100" });
    (ev.holdings[2] as Record<string, unknown>).same_period_kodex200 = SP(4, 1);
    fetchEnrichedHoldings.mockReset().mockResolvedValue(hold);
    fetchHoldingsMarketEvidence.mockReset().mockResolvedValue(ev);
    render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("KODEX 200");
    fireEvent.click(screen.getByRole("tab", { name: "보유" }));
    const list = await screen.findByTestId("wb-holding-list");
    // 보유 근거 객체가 있는 보유 — 그 객체(양쪽 수익률 · 사용 종가 날짜).
    fireEvent.click(within(list).getByText("TIGER 미국나스닥100").closest("[role=button]")!);
    const cell = (await screen.findByText("동일 기간 KODEX200 대비 1M")).parentElement!;
    expect(cell.textContent).toContain("+3.00%p — 후보 +4.00% · KODEX200 +1.00% · 사용 종가 2026-06-24 → 2026-07-24");
    // 보유 근거 객체가 없는 보유 — '동일 기간 값 없음'(기존 excess_return 으로 채우지 않음).
    fireEvent.click(within(list).getByText("TIGER 미국S&P500").closest("[role=button]")!);
    const cell2 = (await screen.findByText("동일 기간 KODEX200 대비 1M")).parentElement!;
    expect(cell2.textContent).toContain("동일 기간 값 없음");
  });
});

// POC5-25 — '20저장일 종가 고점 대비'(현재 저장 종가 객체만 · 옛 drawdown_20d 는 반대 순서 함정).
describe("Workbench — 20저장일 종가 고점 대비 (POC5-25)", () => {
  const LABEL = "20저장일 종가 고점 대비";
  function dd(value: number | null, reason?: string) {
    return value == null
      ? { status: "unavailable", reason: reason ?? "insufficient_history", rows: 18 }
      : {
          status: "ok",
          value_pct: value,
          start_date: "2026-09-16",
          end_date: "2026-10-14",
          peak_close: 28550,
          peak_date: "2026-10-06",
          close: 24600,
          rows: 20,
        };
  }
  function five() {
    const mk = (tk: string, name: string, rank: number, v: number | null, old: number) => ({
      rank,
      ticker: tk,
      name,
      returns: { one_month: { return_pct: 1 }, three_month: { return_pct: 1 } },
      drawdown_20d: old,
      stored_drawdown_20: dd(v, v == null && rank === 4 ? "basis_unconfirmed" : undefined),
      data_quality: { status: "ok" },
    });
    return {
      ...candOk(),
      candidates: [
        mk("AAA111", "가 ETF", 1, -2, -0.9),
        mk("BBB222", "나 ETF", 2, null, -0.01), // 값 없음(옛 값은 있음)
        mk("CCC333", "다 ETF", 3, -2, -0.5), // A 와 동률 — 기존(API) 순서 유지
        mk("DDD444", "라 ETF", 4, null, -0.2), // 값 없음(가격 기준 확인 필요)
        mk("EEE555", "마 ETF", 5, -5, 0),
      ],
    };
  }
  const ALL = ["AAA111", "BBB222", "CCC333", "DDD444", "EEE555"];
  function order(container: HTMLElement): string[] {
    const t = container.textContent ?? "";
    return ALL.map((x) => ({ x, at: t.indexOf(x) }))
      .filter((o) => o.at >= 0)
      .sort((a, b) => a.at - b.at)
      .map((o) => o.x);
  }
  async function renderFive() {
    fetchMarketTopnLatest.mockReset().mockResolvedValue(five());
    const utils = render(<JudgmentWorkbenchView onNavigate={vi.fn()} />);
    await screen.findByText("가 ETF");
    return utils;
  }
  const click = (label: string) =>
    fireEvent.click(screen.getByRole("button", { name: new RegExp(`^${label}`) }));

  it("오름(값 작은 순) · 내림 모두 값 없음은 맨 뒤 · 동률은 API 순서", async () => {
    const { container } = await renderFive();
    click(LABEL); // 첫 클릭 = 오름
    expect(order(container)).toEqual(["EEE555", "AAA111", "CCC333", "BBB222", "DDD444"]);
    click(LABEL); // 다시 = 내림
    expect(order(container)).toEqual(["AAA111", "CCC333", "EEE555", "BBB222", "DDD444"]);
  });

  it("카드 줄 = 새 값 또는 사유 · 옛 값은 보이지 않는다 · 0% 아님 중립", async () => {
    const { container } = await renderFive();
    const text = container.textContent ?? "";
    expect(text).toContain("저장 종가 20개 미만");
    expect(text).toContain("가격 기준 확인 필요");
    expect(text).not.toContain("-90.00%"); // 옛 drawdown_20d −0.9 × 100
    const none = Array.from(container.querySelectorAll(".wb-hm-ex .v.wb-dd-none")).map(
      (e) => e.textContent,
    );
    expect(none).toEqual(["저장 종가 20개 미만", "가격 기준 확인 필요"]);
  });

  it("상세 칸 = 값 · 기간 · 고점(날짜 · 종가)", async () => {
    await renderFive();
    const list = screen.getByTestId("wb-candidate-list");
    fireEvent.click(within(list).getByText("가 ETF").closest("[role=button]")!);
    const cell = (await screen.findAllByText(LABEL)).map((e) => e.parentElement!)
      .find((p) => p.className.includes("wb-detail-cell"))!;
    expect(cell.textContent).toBe(`${LABEL}-2.00% (2026-09-16 ~ 2026-10-14 · 고점 2026-10-06 28,550)`);
  });
});
