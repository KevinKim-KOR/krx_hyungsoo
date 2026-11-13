// POC5-09 — 「오늘의 투자 점검」: KODEX200 거래량 칸 · 최대 3개 기준일 · 기준일이 달라 뺀 보유 ·
// 두 안내 카드의 거래량 문구(판정 §9-3 · §9-4-3). 부모가 받은 응답만 표시한다(추가 조회 없음).
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within, act, fireEvent } from "@testing-library/react";
import { __resetQueryCache, type QueryState } from "@/lib/api/queryCache";
import type { MarketTopNResponse } from "@/lib/api";

const fetchBenchmarkSeries = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchBenchmarkSeries: (...a: unknown[]) => fetchBenchmarkSeries(...a),
  };
});

import KospiHeadline from "./KospiHeadline";
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

async function renderHeadline(m: QueryState<MarketTopNResponse>) {
  render(<KospiHeadline market={m} />);
  await act(async () => {
    await Promise.resolve();
  });
  // POC5-UI-03 — KODEX200 거래량은 '시장 수치와 거래량'(기본 접힘) 안에 있다.
  fireEvent.click(screen.getByRole("button", { name: "시장 수치와 거래량 펼치기" }));
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

  it("거래량 필드가 없으면 '거래량 자료 없음' · 기준선 칸은 판정 표로 옮겨 이 카드에 없음(설계자 V3 D3)", async () => {
    await renderHeadline(market({ kodex200_stored_volume: null }));
    expect(screen.getByTestId("stored-volume").textContent).toContain("거래량 자료 없음");
    expect(screen.queryByText("KODEX200 기준선 대비 위치")).toBeNull();
  });

  // POC6-29 — 「보유 자세히」(최대 3개 · 기준일이 달라 뺀 보유)는 카드 합침으로 없앴다(설계 §2) — 그 두 시험은 지웠다.
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
