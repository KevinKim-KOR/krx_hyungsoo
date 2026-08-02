// POC3-01 REMEDIATION — DashboardView 핵심 UI 계약 test (§5).
// @/lib/api 를 mock 해 응답을 통제한다. 실제 네트워크·운영 데이터 미의존.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";

// ── @/lib/api mock ─────────────────────────────────────────────────────────
const fetchMarketTopnLatest = vi.fn();
const fetchEnrichedHoldings = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
const fetchNavDiscountLatest = vi.fn();

vi.mock("@/lib/api", () => ({
  fetchMarketTopnLatest: (...a: unknown[]) => fetchMarketTopnLatest(...a),
  fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
  fetchHoldingsMarketEvidence: (...a: unknown[]) => fetchHoldingsMarketEvidence(...a),
  fetchNavDiscountLatest: (...a: unknown[]) => fetchNavDiscountLatest(...a),
}));

import DashboardView from "./DashboardView";

// ── fixture ────────────────────────────────────────────────────────────────
function marketOk(overrides: Record<string, unknown> = {}) {
  return {
    status: "ok",
    asof: "2026-07-24",
    universe_count: 100,
    candidates: [{ ticker: "069500" }, { ticker: "139260" }],
    daily_topn: [],
    one_month_topn: [],
    three_month_topn: [],
    market_context: {
      status: "ok",
      asof: "2026-07-24",
      regime_label: "보합장",
      regime_code: "neutral",
      warnings: [],
      kodex200: {},
      kospi: {},
      primary_benchmark: "KODEX200",
      regime_reasons: [],
    },
    market_risk_reference: {
      kodex200: {
        availability: "available",
        as_of_date: "2026-07-24",
        close: 34000,
        change_1d_pct: 0.5,
        recent_20d_series: [],
      },
      vix: {
        availability: "available",
        as_of_date: "2026-07-03", // 시장보다 이전 → stale
        close: 17.25,
        recent_20d_series: [],
      },
    },
    ...overrides,
  };
}
function holdingsOk() {
  return {
    items: [
      { ticker: "A", name: "A", quantity: 10, avg_buy_price: 1000, invested_amount: 10000, current_price: 1500, price_asof: "x", price_source: "n", eval_amount: 15000, pnl_amount: 5000, pnl_rate_pct: 50, buy_weight_pct: null, market_weight_pct: null, price_missing: false, calc_missing: false },
      { ticker: "B", name: "B", quantity: 5, avg_buy_price: 2000, invested_amount: 10000, current_price: null, price_asof: null, price_source: null, eval_amount: null, pnl_amount: null, pnl_rate_pct: null, buy_weight_pct: null, market_weight_pct: null, price_missing: true, calc_missing: true },
    ],
  };
}
function evidenceOk(overrides: Record<string, number> = {}) {
  return {
    status: "ok",
    asof: "2026-07-24",
    holdings_asof: "2026-07-24",
    market_asof: "2026-07-24",
    market_context: null,
    summary: {
      total_holdings_count: 2,
      matched_topn_count: 1,
      not_in_current_topn_count: 1,
      evidence_unavailable_count: 0,
      constituents_available_count: 2,
      constituents_unavailable_count: 0,
      nav_discount_unavailable_count: 0,
      ...overrides,
    },
    holdings: [],
    warnings: [],
  };
}
function navOk(overrides: Record<string, number> = {}) {
  return {
    status: "ok",
    asof: "2026-07-24",
    source: "naver",
    summary: { total_count: 2, ok_count: 2, unavailable_count: 0, failed_count: 0, ...overrides },
    items: [],
  };
}

beforeEach(() => {
  __resetQueryCache();
  fetchMarketTopnLatest.mockReset();
  fetchEnrichedHoldings.mockReset();
  fetchHoldingsMarketEvidence.mockReset();
  fetchNavDiscountLatest.mockReset();
  fetchMarketTopnLatest.mockResolvedValue(marketOk());
  fetchEnrichedHoldings.mockResolvedValue(holdingsOk());
  fetchHoldingsMarketEvidence.mockResolvedValue(evidenceOk());
  fetchNavDiscountLatest.mockResolvedValue(navOk());
});

describe("DashboardView — 시장 lazy 조회", () => {
  it("최초 진입에서 /market/topn/latest 를 호출하지 않는다 (AC-8)", async () => {
    render(<DashboardView onNavigate={vi.fn()} />);
    // holdings/evidence/nav 는 로드되지만 market 은 미호출.
    await waitFor(() => expect(fetchEnrichedHoldings).toHaveBeenCalled());
    expect(fetchMarketTopnLatest).not.toHaveBeenCalled();
    expect(screen.getByText(/시장 상태를 불러오면/)).toBeInTheDocument();
    expect(screen.getByText(/기준일: 미조회/)).toBeInTheDocument();
  });

  it("버튼 클릭 시 topn 을 1회 호출한다", async () => {
    render(<DashboardView onNavigate={vi.fn()} />);
    fireEvent.click(screen.getByText("시장 상태 불러오기"));
    await waitFor(() => expect(fetchMarketTopnLatest).toHaveBeenCalledTimes(1));
    // 시장 국면 표시 (버튼 라벨 변경으로 로드 완료 확인).
    await waitFor(() =>
      expect(screen.getByText("시장 상태 다시 불러오기")).toBeInTheDocument(),
    );
  });

  it("재진입 시 조회된 시장 결과를 재호출하지 않는다", async () => {
    const { unmount } = render(<DashboardView onNavigate={vi.fn()} />);
    fireEvent.click(screen.getByText("시장 상태 불러오기"));
    await waitFor(() => expect(fetchMarketTopnLatest).toHaveBeenCalledTimes(1));
    unmount();
    // 재마운트 (화면 왕복). 캐시 재사용 → topn 재호출 없음.
    render(<DashboardView onNavigate={vi.fn()} />);
    await waitFor(() =>
      expect(screen.getByText("시장 상태 다시 불러오기")).toBeInTheDocument(),
    );
    expect(fetchMarketTopnLatest).toHaveBeenCalledTimes(1);
  });
});

describe("DashboardView — 결측 정직성", () => {
  it("평가액 부분 결측은 N/M건 기준으로 표시하고 0으로 위장하지 않는다", async () => {
    render(<DashboardView onNavigate={vi.fn()} />);
    const holdingsCard = (await screen.findByText("보유 현황")).closest(".card")!;
    // B 는 eval_amount null → "1/2건 기준 · 불가 1건 제외" (분할 렌더 대응 textContent).
    await waitFor(() =>
      expect((holdingsCard as HTMLElement).textContent).toMatch(/1\/2건 기준/),
    );
  });

  it("평가액 전부 결측이면 '확인 불가' (0 아님)", async () => {
    fetchEnrichedHoldings.mockResolvedValue({
      items: [
        { ticker: "A", name: "A", quantity: 1, avg_buy_price: 1, invested_amount: 1, current_price: null, price_asof: null, price_source: null, eval_amount: null, pnl_amount: null, pnl_rate_pct: null, buy_weight_pct: null, market_weight_pct: null, price_missing: true, calc_missing: true },
      ],
    });
    render(<DashboardView onNavigate={vi.fn()} />);
    const holdingsCard = (await screen.findByText("보유 현황")).closest(".card")!;
    expect(within(holdingsCard as HTMLElement).getAllByText("확인 불가").length).toBeGreaterThan(0);
  });
});

describe("DashboardView — VIX stale · 예외 · 일부 실패", () => {
  it("VIX 는 소수점 둘째 자리로 표시하고 stale 을 분리 표시한다", async () => {
    render(<DashboardView onNavigate={vi.fn()} />);
    fireEvent.click(screen.getByText("시장 상태 불러오기"));
    const marketCard = (await screen.findByText("시장 상태")).closest(".card")!;
    await waitFor(() => {
      const txt = (marketCard as HTMLElement).textContent ?? "";
      // VIX close 17.25 (둘째 자리) + stale 표시가 시장 카드 안에.
      expect(txt).toMatch(/17\.25/);
      expect(txt).toMatch(/stale/);
    });
  });

  it("예외 버튼이 확정된 탭으로 이동한다", async () => {
    const onNavigate = vi.fn();
    fetchHoldingsMarketEvidence.mockResolvedValue(
      evidenceOk({ evidence_unavailable_count: 3 }),
    );
    render(<DashboardView onNavigate={onNavigate} />);
    const btn = await screen.findByText("해당 근거 확인 →");
    fireEvent.click(btn);
    // POC3-05 DESIGN_V2 §7·AC-13: 근거 확인 연결은 "확인 근거"(holdings_evidence) 로.
    expect(onNavigate).toHaveBeenCalledWith("holdings_evidence");
  });

  it("일부 영역(NAV) 실패해도 정상 영역(보유)은 유지된다", async () => {
    fetchNavDiscountLatest.mockRejectedValue(new Error("nav down"));
    render(<DashboardView onNavigate={vi.fn()} />);
    // 보유는 정상 렌더.
    expect(await screen.findByText("보유 종목 수:")).toBeInTheDocument();
    // 서로 다른 기준일 합치지 않음 안내 유지.
    expect(screen.getByText(/서로 다른 기준일은 합치지 않습니다/)).toBeInTheDocument();
  });

  it("unavailable 을 '예외 없음' 으로 표현하지 않는다", async () => {
    fetchNavDiscountLatest.mockResolvedValue(navOk({ unavailable_count: 2 }));
    render(<DashboardView onNavigate={vi.fn()} />);
    expect(await screen.findByText(/NAV 미연동\/실패 2건/)).toBeInTheDocument();
    expect(screen.queryByText("확인된 예외 없음")).not.toBeInTheDocument();
  });

  it("조회 실패는 예외 목록에 나오고 '확인된 예외 없음' 과 공존하지 않는다 (A-1(4))", async () => {
    fetchNavDiscountLatest.mockRejectedValue(new Error("nav down"));
    render(<DashboardView onNavigate={vi.fn()} />);
    // NAV 실패가 예외로 노출.
    expect(await screen.findByText(/NAV 조회 실패/)).toBeInTheDocument();
    // "확인된 예외 없음" 은 동시에 뜨지 않음.
    expect(screen.queryByText("확인된 예외 없음")).not.toBeInTheDocument();
  });

  it("ISO datetime 기준일을 KST 가독 형식으로 표시한다 (A-1(3))", async () => {
    // evidence.holdings_asof 를 ISO datetime 으로.
    fetchHoldingsMarketEvidence.mockResolvedValue({
      ...evidenceOk(),
      holdings_asof: "2026-06-17T14:35:07.892806+00:00",
    });
    render(<DashboardView onNavigate={vi.fn()} />);
    // raw ISO 원문이 그대로 노출되지 않는다.
    await waitFor(() =>
      expect(screen.queryByText(/2026-06-17T14:35:07/)).not.toBeInTheDocument(),
    );
    // KST 변환(+9h → 23:35) · "KST" 표기.
    expect(screen.getByText(/2026-06-17 23:35 KST/)).toBeInTheDocument();
  });

  it("파싱 불가 날짜는 raw 문자열이 아니라 '확인 불가' 로 표시한다 (B-1)", async () => {
    fetchNavDiscountLatest.mockResolvedValue({ ...navOk(), asof: "not-a-date" });
    render(<DashboardView onNavigate={vi.fn()} />);
    const asofCard = (await screen.findByText("항목별 기준일")).closest(".card")!;
    await waitFor(() => {
      const txt = (asofCard as HTMLElement).textContent ?? "";
      expect(txt).not.toMatch(/not-a-date/);
      expect(txt).toMatch(/확인 불가/);
    });
  });

  it("market status=invalid 는 예외로 잡히고 '예외 없음' 과 공존하지 않는다 (A-1(2))", async () => {
    fetchMarketTopnLatest.mockResolvedValue(
      marketOk({ status: "invalid", market_context: null, market_risk_reference: null }),
    );
    render(<DashboardView onNavigate={vi.fn()} />);
    fireEvent.click(screen.getByText("시장 상태 불러오기"));
    expect(await screen.findByText(/시장 데이터 확인 불가 \(invalid\)/)).toBeInTheDocument();
    expect(screen.queryByText("확인된 예외 없음")).not.toBeInTheDocument();
  });
});
