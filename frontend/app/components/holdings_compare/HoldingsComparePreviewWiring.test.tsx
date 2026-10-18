// POC5-23 — 「보유와 비교」 → 판단 근거 미리보기 연결(판정 Q1 (a) · §4).
// 화면 목록 응답의 조건(개수 · 기준 · 정렬 · 네 필터)이 후보 미리보기 요청 본문에 그대로 실리고,
// 보유 미리보기 요청에는 실리지 않는다. 보유 조회는 모의 · 미리보기는 진짜 요청 함수 + 가짜 fetch.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { MarketCandidate } from "@/lib/api";
import HoldingsCompareView from "../HoldingsCompareView";

const fetchEnrichedHoldings = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
vi.mock("@/lib/api/holdings", () => ({
  fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
  fetchHoldingsMarketEvidence: (...a: unknown[]) => fetchHoldingsMarketEvidence(...a),
}));

const bodies: unknown[] = [];
const fetchMock = vi.fn(async (_url: string, init?: { body?: string }) => {
  bodies.push(init?.body ? JSON.parse(init.body) : null);
  return { ok: true, status: 200, text: async () => JSON.stringify({ status: "error" }) };
});

const FILTERS = {
  exclude_inverse: true,
  exclude_leveraged: false,
  exclude_synthetic: true,
  exclude_futures: true,
};

function data() {
  return {
    status: "ok",
    asof: "2026-10-14",
    n: 10,
    basis: "three_month",
    order: "desc",
    filters: FILTERS,
    candidates: [
      { rank: 2, ticker: "0223A0", name: "RISE 코스닥커버드콜액티브", tags: [] } as unknown as MarketCandidate,
    ],
    daily_topn: [],
    one_month_topn: [],
    three_month_topn: [],
  } as never;
}

beforeEach(() => {
  bodies.length = 0;
  vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://api.test");
  vi.stubGlobal("fetch", fetchMock);
  fetchEnrichedHoldings.mockReset().mockResolvedValue({
    items: [
      {
        ticker: "111111",
        name: "보유 반도체 ETF",
        quantity: 1,
        avg_buy_price: 100,
        invested_amount: 100,
        current_price: 110,
        price_asof: "2026-10-14",
        price_source: "n",
        eval_amount: 110,
        pnl_amount: 10,
        pnl_rate_pct: 10,
        buy_weight_pct: null,
        market_weight_pct: 100,
        price_missing: false,
        calc_missing: false,
      },
    ],
  });
  fetchHoldingsMarketEvidence.mockReset().mockResolvedValue({
    status: "ok",
    asof: "2026-10-14",
    holdings: [],
    warnings: [],
  });
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("보유와 비교 → 판단 근거 미리보기", () => {
  it("후보 요청 = 화면 목록 조건 그대로 · 보유 요청 = 조건 없음", async () => {
    render(<HoldingsCompareView data={data()} />);
    await waitFor(() => expect(screen.getByText("RISE 코스닥커버드콜액티브")).toBeInTheDocument());
    fireEvent.click(screen.getByText("RISE 코스닥커버드콜액티브"));
    fireEvent.click(await screen.findByRole("button", { name: /판단 근거 미리보기 생성/ }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({
      target_kind: "candidate",
      ticker: "0223A0",
      n: 10,
      basis: "three_month",
      order: "desc",
      ...FILTERS,
    });

    await waitFor(() => expect(screen.getByText("보유 반도체 ETF")).toBeInTheDocument());
    fireEvent.click(screen.getByText("보유 반도체 ETF"));
    fireEvent.click(await screen.findByRole("button", { name: /판단 근거 미리보기 생성/ }));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).toEqual({ target_kind: "holding", ticker: "111111" });
  });
});
