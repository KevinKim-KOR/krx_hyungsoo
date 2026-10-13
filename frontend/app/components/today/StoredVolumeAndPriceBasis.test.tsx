// POC5-09 — 「오늘의 투자 점검」: KODEX200 거래량 칸 · 최대 3개 기준일 · 기준일이 달라 뺀 보유 ·
// 두 안내 카드의 거래량 문구(판정 §9-3 · §9-4-3). 부모가 받은 응답만 표시한다(추가 조회 없음).
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within, act } from "@testing-library/react";
import { __resetQueryCache, type QueryState } from "@/lib/api/queryCache";
import type {
  EnrichedHoldingsResult,
  HoldingsMarketEvidenceResponse,
  MarketTopNResponse,
} from "@/lib/api";

const fetchBenchmarkSeries = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchBenchmarkSeries: (...a: unknown[]) => fetchBenchmarkSeries(...a),
  };
});

import KospiHeadline from "./KospiHeadline";
import JudgmentQueueSection from "./JudgmentQueueSection";
import InDevelopmentSection from "./InDevelopmentSection";
import KospiDetailSection from "./KospiDetailSection";

const KODEX_VOLUME = {
  ticker: "069500",
  status: "ok" as const,
  asof_date: "2026-10-08",
  source: "FinanceDataReader",
  volume: 23162524,
  window_size: 20,
  window_start_date: "2026-09-07",
  window_end_date: "2026-10-07",
  window_date_count: 20,
  valid_count: 20,
  avg_prev20: 23710207.85,
  avg_status: "ok" as const,
  ratio: 0.9769009258179067,
  ratio_status: "ok" as const,
};

function market(over: Partial<MarketTopNResponse> = {}): QueryState<MarketTopNResponse> {
  return {
    phase: "success",
    stale: false,
    data: {
      status: "ok",
      candidates: [],
      daily_topn: [],
      one_month_topn: [],
      three_month_topn: [],
      market_context: null,
      kodex200_stored_volume: KODEX_VOLUME,
      ...over,
    } as MarketTopNResponse,
  };
}

function evidence(over: Partial<HoldingsMarketEvidenceResponse> = {}): QueryState<HoldingsMarketEvidenceResponse> {
  return {
    phase: "success",
    stale: false,
    data: {
      status: "ok",
      asof: "2026-10-13",
      holdings_asof: null,
      market_asof: "2026-10-08",
      market_context: null,
      summary: {
        total_holdings_count: 4, matched_topn_count: 0, not_in_current_topn_count: 4,
        evidence_unavailable_count: 1, constituents_available_count: 0,
        constituents_unavailable_count: 4, nav_discount_unavailable_count: 0,
      },
      holdings: [],
      judgment_summary: {
        market_position: { available: true },
        holdings: {
          available: true,
          top_holdings: [
            {
              ticker: "0193T0", name: "KODEX SK하이닉스단일종목레버리지",
              eval_amount: 107595, market_weight_pct: 0.7, pnl_rate_pct: -61.04,
              return_5d_pct: -10.5, return_20d_pct: -11.76, excess_vs_kodex200_20d_pctp: -7.1,
            },
          ],
          coverage: { total: 4, need_check: 3, ok: 1 },
        },
        data_status: {},
      },
      price_basis: {
        reference_date: "2026-10-08",
        reference_ticker: "069500",
        kodex200_start_date_5d: "2026-09-30",
        kodex200_start_date_20d: "2026-09-07",
        date_mismatch: [
          { ticker: "005930", name: "삼성전자", end_date: "2026-08-12" },
          { ticker: "000660", name: "SK하이닉스", end_date: "2026-08-12" },
          { ticker: "006400", name: "삼성SDI", end_date: "2026-08-12" },
        ],
      },
      warnings: [],
      ...over,
    },
  };
}

const holdings: QueryState<EnrichedHoldingsResult> = {
  phase: "success",
  stale: false,
  data: { items: [] } as unknown as EnrichedHoldingsResult,
};

async function renderHeadline(m: QueryState<MarketTopNResponse>) {
  render(<KospiHeadline market={m} />);
  await act(async () => {
    await Promise.resolve();
  });
}

describe("「오늘의 투자 점검」 저장 거래량 · 가격 기준일 (POC5-09)", () => {
  beforeEach(() => {
    __resetQueryCache();
    fetchBenchmarkSeries.mockResolvedValue({ ticker: "KOSPI", availability: "NO_DATA", series: [] });
  });

  it("KOSPI 카드에 'KODEX200 거래량' 2 × 2 칸 · 자기 기준일 · KOSPI 전체 거래량으로 부르지 않음", async () => {
    await renderHeadline(market());
    const card = screen.getByLabelText("KOSPI 현재 위치");
    const vol = within(card).getByTestId("stored-volume");
    expect(vol.querySelector(".tc-label")?.textContent).toContain("KODEX200 거래량");
    expect(vol.querySelector(".wb-detail-grid")?.className).toBe("wb-detail-grid svb-2");
    expect(Array.from(vol.querySelectorAll(".svb-v")).map((e) => e.textContent)).toEqual([
      "2026-10-08",
      "23,162,524주",
      "23,710,207.85주",
      "0.98배",
    ]);
    expect(vol.textContent).not.toContain("과거 저장 자료");
    const help = within(vol).getByRole("note");
    expect(help.getAttribute("title")).toContain("코스피 시장 전체 거래량이 아닙니다");
    expect(card.textContent ?? "").not.toMatch(/KOSPI 거래량|코스피 거래량/);
  });

  it("거래량 필드가 없으면 '거래량 자료 없음' · 기존 기준선 칸은 그대로", async () => {
    await renderHeadline(market({ kodex200_stored_volume: null }));
    expect(screen.getByTestId("stored-volume").textContent).toContain("거래량 자료 없음");
    expect(screen.getByText("KODEX200 기준선 대비 위치")).toBeTruthy();
  });

  it("최대 3개 설명에 PC 저장 가격 기준일 · 기준일이 달라 뺀 보유는 자료 확인 사유로", () => {
    render(
      <JudgmentQueueSection
        market={market()}
        holdings={holdings}
        evidence={evidence()}
        onNavigate={() => undefined}
      />,
    );
    expect(
      screen.getByText("최근 5거래일 변화가 낮은 보유 ETF부터 최대 3개 · PC 저장 가격 기준일 2026-10-08"),
    ).toBeTruthy();
    expect(screen.getByTestId("tc-price-mismatch").textContent).toBe(
      "가격 기준일이 달라 이 비교에서 뺀 보유: 삼성전자 · SK하이닉스 · 삼성SDI(저장 가격 기준일 2026-08-12) — 자료 확인 필요",
    );
    const text = screen.getByLabelText("오늘 내가 확인할 것").textContent ?? "";
    expect(text).not.toMatch(/정상|안전|위험 경보/);
  });

  it("뺀 보유가 없으면 그 줄이 없다 · price_basis 가 없으면 설명은 예전 그대로", () => {
    const { unmount } = render(
      <JudgmentQueueSection
        market={market()}
        holdings={holdings}
        evidence={evidence({
          price_basis: {
            reference_date: "2026-10-08",
            reference_ticker: "069500",
            kodex200_start_date_5d: null,
            kodex200_start_date_20d: null,
            date_mismatch: [],
          },
        })}
        onNavigate={() => undefined}
      />,
    );
    expect(screen.queryByTestId("tc-price-mismatch")).toBeNull();
    unmount();
    render(
      <JudgmentQueueSection
        market={market()}
        holdings={holdings}
        evidence={evidence({ price_basis: null })}
        onNavigate={() => undefined}
      />,
    );
    expect(screen.getByText("최근 5거래일 변화가 낮은 보유 ETF부터 최대 3개")).toBeTruthy();
    expect(screen.queryByTestId("tc-price-mismatch")).toBeNull();
  });

  it("두 안내 카드의 거래량 항목 — 판정 §9-3 문구 · 배지", () => {
    render(<InDevelopmentSection />);
    const board = screen.getByLabelText("개발 중인 판단 기능");
    const item = within(board).getByText("저장 거래량 확인 근거").closest("li") as HTMLElement;
    const badge = within(item).getByText("일부 제공");
    expect(badge.className).toBe("tc-badge tc-badge-dev");
    expect(item.textContent).toContain(
      "저장 거래량과 직전 20개 저장일 평균 대비를 제공합니다. 종목 상세와 KODEX200 영역에서 확인합니다. 종합 위험 분류에는 아직 반영하지 않습니다.",
    );
    expect(within(board).queryByText(/거래량 자료 미저장/)).toBeNull();
    // 다른 미도입 항목 · 배지 양식은 그대로.
    expect(within(board).getAllByText("이번 단계 미도입")[0].className).toBe(
      "tc-badge tc-badge-off",
    );

    render(<KospiDetailSection market={market()} />);
    const detail = screen.getByLabelText("코스피 상세 (개발 중)");
    expect(within(detail).getByText("KOSPI 지수 거래량")).toBeTruthy();
    expect(within(detail).getByText("미제공").className).toBe("tc-badge tc-badge-off");
  });
});
