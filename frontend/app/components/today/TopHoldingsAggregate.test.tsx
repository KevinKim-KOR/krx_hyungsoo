// POC5-09 설계 §10-2-2 — 「오늘의 투자 점검」 최대 3개의 비중 · 손익 = 「확인 근거」와 같은 종목 합산.
// 한 종목에 이익 계좌와 손실 계좌가 함께 있을 때 두 화면 값이 같고, backend 요약의 비중 · 손익(이 시험에서는
// 일부러 다른 값)은 쓰지 않는다. 선정 · 순서 · 5일 · 20일 · KODEX200 대비는 backend 요약 그대로.
// (POC5-14 전 backend 요약 값은 마지막 줄 값이 복사된 첫 줄 값이었고, 지금은 backend 도 종목 합산이다.)
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { __resetQueryCache, type QueryState } from "@/lib/api/queryCache";
import type {
  EnrichedHoldingsResult,
  HoldingsMarketEvidenceResponse,
  MarketTopNResponse,
} from "@/lib/api";

const fetchEnrichedHoldings = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
    fetchHoldingsMarketEvidence: (...a: unknown[]) => fetchHoldingsMarketEvidence(...a),
  };
});

import JudgmentQueueSection from "./JudgmentQueueSection";
import HoldingsRiskEvidenceSection from "../HoldingsRiskEvidenceSection";

function row(ticker: string, name: string, invested: number, evalAmt: number) {
  return {
    ticker, name, quantity: 1, avg_buy_price: invested, invested_amount: invested,
    current_price: evalAmt, price_asof: "2026-10-12", price_source: "naver",
    eval_amount: evalAmt, pnl_amount: evalAmt - invested,
    pnl_rate_pct: ((evalAmt - invested) / invested) * 100,
    buy_weight_pct: null, market_weight_pct: null, price_missing: false, calc_missing: false,
  };
}
// KODEX 200 = 손실 계좌(먼저) + 이익 계좌. 합산 평가 2,234,000 · 매입 2,030,000.
const ENRICHED = {
  items: [
    row("069500", "KODEX 200", 230000, 223400),
    row("069500", "KODEX 200", 1800000, 2010600),
    row("0193T0", "KODEX SK하이닉스단일종목레버리지", 276000, 107595),
    row("0181B0", "HANARO 미국AI메모리반도체TOP4+", 152000, 150300),
  ],
} as unknown as EnrichedHoldingsResult;
// 기대 = 전체 평가 합 2,491,895 기준.
const KODEX_WEIGHT = ((223400 + 2010600) / 2491895) * 100; // 89.65…
const KODEX_PNL = ((2234000 - 2030000) / 2030000) * 100; // +10.05…

function evidence(): HoldingsMarketEvidenceResponse {
  return {
    status: "ok",
    asof: "2026-10-13",
    holdings_asof: null,
    market_asof: "2026-10-08",
    market_context: null,
    summary: {
      total_holdings_count: 4, matched_topn_count: 0, not_in_current_topn_count: 4,
      evidence_unavailable_count: 0, constituents_available_count: 0,
      constituents_unavailable_count: 4, nav_discount_unavailable_count: 0,
    },
    holdings: [],
    judgment_summary: {
      market_position: { available: true },
      holdings: {
        available: true,
        // backend 요약의 비중 · 손익 — 일부러 화면 합산과 다른 값(손실 계좌 값) · 화면에 나오면 안 된다.
        top_holdings: [
          {
            ticker: "069500", name: "KODEX 200", eval_amount: 223400,
            market_weight_pct: 9.0, pnl_rate_pct: -2.87,
            return_5d_pct: -3.56, return_20d_pct: -4.67, excess_vs_kodex200_20d_pctp: 0,
          },
        ],
        coverage: { total: 3, need_check: 0, ok: 3 },
      },
      data_status: {},
    },
    warnings: [],
  };
}
const MARKET = { phase: "loading" } as QueryState<MarketTopNResponse>;

describe("최대 3개 비중 · 손익 = 종목 합산 (POC5-09 설계 §10-2-2)", () => {
  beforeEach(() => {
    __resetQueryCache();
    fetchEnrichedHoldings.mockResolvedValue(ENRICHED);
    fetchHoldingsMarketEvidence.mockResolvedValue(evidence());
  });

  it("이익 · 손실 계좌가 섞인 종목 — 「오늘의 투자 점검」과 「확인 근거」의 비중 · 손익이 같다", async () => {
    render(
      <JudgmentQueueSection
        market={MARKET}
        holdings={{ phase: "success", stale: false, data: ENRICHED }}
        evidence={{ phase: "success", stale: false, data: evidence() }}
        onNavigate={() => undefined}
      />,
    );
    // POC5-UI-03 — 20일 · KODEX200 대비 · 손익은 종목별 '수치 더보기'(기본 접힘). 펼친 뒤 확인한다.
    screen.getAllByRole("button", { name: /수치 더보기$/ }).forEach((b) => fireEvent.click(b));
    const weight = `비중 ${KODEX_WEIGHT.toFixed(1)}%`;
    const pnl = `손익 +${KODEX_PNL.toFixed(2)}%`;
    const today = screen.getByLabelText("오늘 내가 확인할 것").textContent ?? "";
    expect(weight).toBe("비중 89.7%");
    expect(pnl).toBe("손익 +10.05%");
    expect(today).toContain(weight);
    expect(today).toContain(pnl);
    // backend 요약의 비중 · 손익은 쓰지 않는다 · 5일 · 20일 · KODEX200 대비는 그대로.
    expect(today).not.toContain("비중 9.0%");
    expect(today).not.toContain("-2.87%");
    expect(today).toContain("5일 -3.56%");
    expect(today).toContain("20일 -4.67% · KODEX200 대비 +0.00%");
    // 0 은 값이다 — 'KODEX200 대비 자료 없음' 안내를 내지 않는다.
    expect(today).not.toContain("자료 없음");

    render(<HoldingsRiskEvidenceSection />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    const card = screen.getByRole("button", { name: "KODEX 200 상세 보기" });
    expect(card.textContent).toContain(`${KODEX_WEIGHT.toFixed(1)}%`);
    expect(card.textContent).toContain(`+${KODEX_PNL.toFixed(2)}%`);
  });

  it("보유 조회 전 · 실패면 비중 · 손익을 보이지 않는다(backend 요약 값으로 대신하지 않음)", () => {
    render(
      <JudgmentQueueSection
        market={MARKET}
        holdings={{ phase: "error" }}
        evidence={{ phase: "success", stale: false, data: evidence() }}
        onNavigate={() => undefined}
      />,
    );
    // 값이 '없다'를 보는 시험은 펼친 상태에서 본다(UI-03 판정 §3).
    screen.getAllByRole("button", { name: /수치 더보기$/ }).forEach((b) => fireEvent.click(b));
    const today = screen.getByLabelText("오늘 내가 확인할 것").textContent ?? "";
    expect(today).toContain("KODEX 200");
    expect(today).not.toMatch(/비중|손익 /);
  });
});
