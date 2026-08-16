// POC3-05 보유 ETF 확인 근거 — 컴포넌트 계약 test.
// - 금지어(위험/고위험/손절/매도/청산/BUY/SELL) 비노출.
// - 급락(falling) 관련 열·빠른보기 없음(이번 Step 제외).
// - 읽기 전용(값 수정·저장 버튼 없음). N+1 없음(2 endpoint 단일 조회).
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";

const fetchEnrichedHoldings = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
const fetchBenchmarkSeries = vi.fn();
const fetchPriceSeries = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
    fetchHoldingsMarketEvidence: (...a: unknown[]) => fetchHoldingsMarketEvidence(...a),
    fetchBenchmarkSeries: (...a: unknown[]) => fetchBenchmarkSeries(...a),
    fetchPriceSeries: (...a: unknown[]) => fetchPriceSeries(...a),
  };
});

import HoldingsRiskEvidenceSection from "./HoldingsRiskEvidenceSection";
import type { HoldingsMarketEvidenceResponse } from "@/lib/api";

function enrichedResult() {
  return {
    items: [
      {
        ticker: "069500", name: "KODEX200", quantity: 10, avg_buy_price: 1000,
        invested_amount: 10000, current_price: 1100, price_asof: "2026-07-24",
        price_source: "naver", eval_amount: 11000, pnl_amount: 1000,
        pnl_rate_pct: 10, buy_weight_pct: 50, market_weight_pct: 50,
        price_missing: false, calc_missing: false,
      },
    ],
  };
}
function evidenceResult(): HoldingsMarketEvidenceResponse {
  return {
    status: "ok", asof: "2026-07-24", holdings_asof: "2026-07-24", market_asof: "2026-07-24",
    market_context: null,
    summary: {
      total_holdings_count: 1, matched_topn_count: 0, not_in_current_topn_count: 1,
      evidence_unavailable_count: 0, constituents_available_count: 1,
      constituents_unavailable_count: 0, nav_discount_unavailable_count: 0,
    },
    holdings: [
      {
        ticker: "069500", name: "KODEX200",
        holding: { quantity: 10, avg_buy_price: 1000, evaluation_amount: 11000, pnl_rate_pct: 10 },
        topn_match: { status: "unavailable", rank: null, basis: null, candidate_name: null },
        returns: { status: "ok", one_month_return_pct: 1, three_month_return_pct: 2 },
        excess_return: { status: "ok", vs_kodex200_1m_pctp: 1, vs_kodex200_3m_pctp: 2 },
        short_term_momentum: {
          status: "ok", return_5d_pct: -1, return_10d_pct: -2, return_20d_pct: -3,
          excess_vs_kodex200_5d_pctp: -0.5, excess_vs_kodex200_10d_pctp: -1, excess_vs_kodex200_20d_pctp: -1.5,
        },
        constituents_overlap: { status: "ok", overlap_with_market_core: [] },
        nav_discount: { status: "ok", source: null, asof: null, nav: null, market_price: null, discount_rate_pct: null, flag: null, message: null },
        evidence_notes: [],
      },
    ],
    warnings: [],
  };
}

async function renderSection() {
  const utils = render(<HoldingsRiskEvidenceSection />);
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
  return utils;
}

describe("보유 ETF 확인 근거 (POC3-05 B)", () => {
  beforeEach(() => {
    __resetQueryCache();
    fetchEnrichedHoldings.mockResolvedValue(enrichedResult());
    fetchHoldingsMarketEvidence.mockResolvedValue(evidenceResult());
    fetchPriceSeries.mockResolvedValue({ availability: "NO_DATA", points: [] });
  });

  it("제목·표·5일/20일/KODEX200 대비 열이 렌더된다", async () => {
    await renderSection();
    expect(screen.getByRole("heading", { name: "보유 ETF 확인 근거" })).toBeTruthy();
    expect(screen.getByText("KODEX200")).toBeTruthy();
    expect(screen.getByText("KODEX200 대비 20일")).toBeTruthy();
  });

  it("금지어(위험/고위험/손절/매도/청산/BUY/SELL)가 없다", async () => {
    const { container } = await renderSection();
    const text = container.textContent ?? "";
    for (const bad of ["위험", "고위험", "손절", "매도", "청산", "BUY", "SELL"]) {
      expect(text).not.toContain(bad);
    }
  });

  it("급락(falling) 신호 열·빠른보기가 없다 (이번 Step 제외)", async () => {
    const { container } = await renderSection();
    const text = container.textContent ?? "";
    expect(text).not.toContain("급락");
    expect(text).not.toContain("주의 신호");
    // 빠른 보기는 전체 / 자료 확인 필요 두 개만.
    expect(screen.getByRole("button", { name: "전체" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /자료 확인 필요/ })).toBeTruthy();
  });

  it("N+1 없음: 조회는 목록 endpoint 2종뿐이고 ticker 인자 호출이 없다", async () => {
    // 보유 종목을 3개로 늘려도 ticker별 호출이 생기지 않는다(목록 1회 조회 계약).
    fetchEnrichedHoldings.mockResolvedValue({
      items: [
        enrichedResult().items[0],
        { ...enrichedResult().items[0], ticker: "233740", name: "B" },
        { ...enrichedResult().items[0], ticker: "305720", name: "C" },
      ],
    });
    await renderSection();
    // 두 목록 조회 함수는 인자 없이(ticker 미전달) 호출된다.
    for (const call of fetchEnrichedHoldings.mock.calls) expect(call).toHaveLength(0);
    for (const call of fetchHoldingsMarketEvidence.mock.calls) expect(call).toHaveLength(0);
    // ticker별 가격 시계열은 선택 전에는 호출되지 않는다(lazy).
    expect(fetchPriceSeries).not.toHaveBeenCalled();
  });

  it("읽기 전용: 값 수정·저장 버튼이 없다", async () => {
    await renderSection();
    expect(screen.queryByRole("button", { name: /저장/ })).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("§6.4: 선택 상세에서 NAV partial 을 정상(ok)과 구분해 표시하고 message 를 노출한다", async () => {
    const ev = evidenceResult();
    ev.holdings[0].nav_discount = {
      status: "partial",
      source: "naver",
      asof: "2026-07-24",
      nav: 1050,
      market_price: 1100,
      discount_rate_pct: null, // 일부 값 결측 = partial
      flag: null,
      message: "괴리율 계산 불가",
    };
    fetchHoldingsMarketEvidence.mockResolvedValue(ev);
    await renderSection();
    // 행 선택 → 선택 상세 렌더. PriceChart lazy 조회 state 업데이트까지 act 로 감싼다.
    await act(async () => {
      fireEvent.click(screen.getByText("KODEX200"));
      await Promise.resolve();
      await Promise.resolve();
    });
    const text = document.body.textContent ?? "";
    // partial 상태가 정상처럼 숨겨지지 않는다.
    expect(text).toContain("부분 자료");
    // message 가 노출된다.
    expect(text).toContain("괴리율 계산 불가");
  });
});

describe("확인 근거 — 카드 전환 (사용자 실화면 직접 지시 2026-08-15)", () => {
  beforeEach(() => {
    __resetQueryCache();
    fetchPriceSeries.mockResolvedValue({ availability: "NO_DATA", points: [] });
  });

  it("자료 확인 필요 행은 배지를 띄우고, 빠른보기 버튼 조회와 충돌하지 않는다", async () => {
    // 시장 evidence 가 없는 보유 → need_check 행이 되어 "자료 확인 필요" 배지가 뜬다.
    fetchEnrichedHoldings.mockResolvedValue(enrichedResult());
    fetchHoldingsMarketEvidence.mockResolvedValue({
      ...evidenceResult(),
      holdings: [],
    });
    await renderSection();
    // 행은 role=button 이지만 접근가능 이름이 종목으로 고정돼 있어,
    // 같은 문구를 쓰는 빠른보기 버튼 조회가 단일 매치로 유지된다.
    expect(
      screen.getByRole("button", { name: /자료 확인 필요/ }),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: /KODEX200 상세 보기/ })).toBeTruthy();
    // 배지 문구 자체는 화면에 존재한다.
    expect(document.querySelector(".wb-hb.warn")?.textContent).toContain(
      "자료 확인 필요",
    );
  });

  it("정상 행에는 '확인됨' 배지를 띄우지 않는다", async () => {
    fetchEnrichedHoldings.mockResolvedValue(enrichedResult());
    fetchHoldingsMarketEvidence.mockResolvedValue(evidenceResult());
    const { container } = await renderSection();
    expect(container.textContent ?? "").not.toContain("확인됨");
  });
});
