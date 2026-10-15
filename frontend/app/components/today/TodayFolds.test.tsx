// POC5-UI-03 — 「오늘의 투자 점검」 정보 배치: 기본 접힘 · 펼침 · 접힌 채 보이는 경고 · 날짜 출처 ·
// 최대 3개 종목별 펼침 · 뺀 보유 긴 목록(설계 V1 §2~§4 · 판정 2026-10-14 Q1~Q4).
// 부모가 받은 응답만 표시한다(추가 조회 없음). 화면 안 상태만 쓴다.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within, act, fireEvent } from "@testing-library/react";
import { __resetQueryCache, type QueryState } from "@/lib/api/queryCache";
import type {
  EnrichedHoldingsResult,
  HoldingsMarketEvidenceItem,
  HoldingsMarketEvidenceResponse,
  MarketContext,
  MarketContextKospi,
  MarketTopNResponse,
  PriceBasisMismatch,
  StoredVolumeEvidence,
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

// ── fixture ──────────────────────────────────────────────────────────────────
const KOSPI_OK: MarketContextKospi = {
  status: "ok",
  as_of_date: "2026-10-12",
  display_state: "ok",
  trading_day_lag: 0,
  today_is_trading_day: true,
  daily_return_pct: -3.65,
  return_1m_pct: -8.2,
  return_3m_pct: -14.6,
  return_1y_pct: 76.82,
  high_52w_gap_pct: -29.96,
} as MarketContextKospi;

const VOL_OK: StoredVolumeEvidence = {
  ticker: "069500",
  status: "ok",
  asof_date: "2026-10-13",
  source: "FinanceDataReader",
  volume: 40337658,
  window_size: 20,
  window_start_date: "2026-09-09",
  window_end_date: "2026-10-12",
  window_date_count: 20,
  valid_count: 20,
  avg_prev20: 24033649.15,
  avg_status: "ok",
  ratio: 1.68,
  ratio_status: "ok",
} as StoredVolumeEvidence;

// 세 날짜를 일부러 다르게 둔다: KOSPI 10-12 · 판정 줄(market_context.asof) 10-14 ·
// KODEX200 유효 가격 최신 행(market_risk_reference.kodex200.as_of_date) 10-13.
function ctx(over: Partial<MarketContext> = {}, kospi: MarketContextKospi = KOSPI_OK): MarketContext {
  return {
    status: "ok",
    asof: "2026-10-14",
    regime_label: "하락장",
    regime_code: "bear",
    warnings: [],
    kodex200: {
      status: "ok",
      close: 95250,
      ma20: 108206,
      ma60: 106209.12,
      ma20_position: "below",
      ma60_position: "below",
      ma20_distance_pct: -11.97,
      ma60_distance_pct: -10.32,
    },
    kospi,
    regime_streak: { regime_code: "bear", streak_days: 3, at_least: false },
    primary_benchmark: "KODEX200",
    regime_reasons: [],
    ...over,
  } as MarketContext;
}

function market(
  over: Partial<MarketTopNResponse> = {},
  c: MarketContext | null = ctx(),
): QueryState<MarketTopNResponse> {
  return {
    phase: "success",
    stale: false,
    data: {
      status: "ok",
      candidates: [],
      daily_topn: [],
      one_month_topn: [],
      three_month_topn: [],
      market_context: c,
      kodex200_stored_volume: VOL_OK,
      market_risk_reference: {
        kodex200: { availability: "available", as_of_date: "2026-10-13", recent_20d_series: [] },
        vix: { availability: "available", as_of_date: "2026-09-11", recent_20d_series: [] },
      },
      ...over,
    } as MarketTopNResponse,
  };
}

async function renderHeadline(m: QueryState<MarketTopNResponse>) {
  const r = render(<KospiHeadline market={m} />);
  await act(async () => {
    await Promise.resolve();
  });
  return r;
}

function card() {
  return screen.getByLabelText("KOSPI 현재 위치");
}
function marketToggle() {
  return within(card()).getByRole("button", { name: /^시장 수치와 거래량 (펼치기|접기)$/ });
}

beforeEach(() => {
  __resetQueryCache();
  fetchBenchmarkSeries.mockReset();
  fetchBenchmarkSeries.mockResolvedValue({ ticker: "KOSPI", availability: "NO_DATA", series: [] });
});

// ── KOSPI 카드 ───────────────────────────────────────────────────────────────
describe("KOSPI 카드 — 기본 화면 · 시장 수치와 거래량 펼치기 (설계 §2)", () => {
  it("기본 = 일간 변화 · MA20 · MA60 만, 나머지는 접힘 · 펼치면 같은 응답 값 · 다시 접힘", async () => {
    await renderHeadline(market());
    const c = card();
    const btn = marketToggle();
    expect(btn).toHaveAttribute("aria-expanded", "false");
    expect(btn).toHaveClass("btn-md", "tc-fold-btn");
    expect(within(c).getByTestId("tc-kospi-daily").textContent).toContain("-3.65%");
    expect(c.textContent).toContain("KODEX200 MA20 대비 -11.97%");
    expect(c.textContent).toContain("KODEX200 MA60 대비 -10.32%");
    // 접힌 칸은 그리지 않는다.
    expect(within(c).queryByTestId("tc-market-detail")).toBeNull();
    expect(c.textContent).not.toContain("1개월");
    expect(c.textContent).not.toContain("하락장");
    expect(within(c).queryByTestId("stored-volume")).toBeNull();
    // 정상이면 '확인 필요' 없음.
    expect(within(c).queryByTestId("tc-market-fold-notes")).toBeNull();

    fireEvent.click(btn);
    expect(marketToggle()).toHaveAttribute("aria-expanded", "true");
    const d = within(c).getByTestId("tc-market-detail");
    for (const t of ["1개월 -8.20%", "3개월 -14.60%", "1년 +76.82%", "최근 1년 고점 대비 -29.96%"]) {
      expect(d.textContent).toContain(t);
    }
    expect(d.textContent).toContain("하락장");
    expect(d.textContent).toContain("3거래일째");
    expect(within(d).getByTestId("stored-volume").textContent).toContain("40,337,658주");

    fireEvent.click(marketToggle());
    expect(within(c).queryByTestId("tc-market-detail")).toBeNull();
  });

  it("세 날짜가 다르면 각자 실제 필드 — 기준선 옆 · 판정 줄 · KOSPI 기준일 (UI-03 · POC5-11 판정 Q1)", async () => {
    await renderHeadline(market());
    const c = card();
    expect(within(c).getByTestId("tc-kodex200-date").textContent).toBe(" · 기준일 2026-10-13");
    expect(c.textContent).toContain("마지막 자료 기준일 2026-10-12");
    expect(c.textContent).not.toContain("2026-10-14");
    fireEvent.click(marketToggle());
    // 판정 줄 = market_context.asof 그대로(POC5-11 부터 PC 화면 API 가 KODEX200 이력 끝 날짜로 준다).
    expect(within(c).getByTestId("tc-regime-date").textContent).toBe(" · KODEX200 기준일 2026-10-14");
    expect(c.textContent).not.toContain("저장 가격 최신일");
    // 기준선 옆 날짜는 그대로 market_risk_reference(10-13) — 판정 줄 값으로 바꾸지 않는다.
    expect(within(c).getByTestId("tc-kodex200-date").textContent).toBe(" · 기준일 2026-10-13");
  });

  it("KODEX200 날짜가 없으면 '기준일 확인 불가' — 판정 줄 날짜 · KOSPI 날짜로 대신하지 않음", async () => {
    for (const ref of [
      undefined,
      {
        kodex200: { availability: "unavailable" as const, as_of_date: null, recent_20d_series: [] },
        vix: { availability: "available" as const, as_of_date: "2026-09-11", recent_20d_series: [] },
      },
    ]) {
      const { unmount } = await renderHeadline(market({ market_risk_reference: ref }));
      const date = within(card()).getByTestId("tc-kodex200-date");
      expect(date.textContent).toBe(" · 기준일 확인 불가");
      expect(date.textContent).not.toMatch(/\d{4}-\d{2}-\d{2}/);
      expect(card().textContent).not.toContain("2026-10-14");
      unmount();
    }
  });

  it("기준선 값이 0 이면 값 있음 — 날짜를 붙인다 · 기준선 값이 없으면 날짜를 붙이지 않는다", async () => {
    const zero = ctx({
      kodex200: {
        status: "ok", close: 1, ma20: 1, ma60: 1, ma20_position: "above", ma60_position: "above",
        ma20_distance_pct: 0, ma60_distance_pct: null,
      },
    } as Partial<MarketContext>);
    const { unmount } = await renderHeadline(market({}, zero));
    expect(within(card()).getByTestId("tc-kodex200-date").textContent).toBe(" · 기준일 2026-10-13");
    unmount();
    const none = ctx({ kodex200: { status: "unavailable" } } as Partial<MarketContext>);
    await renderHeadline(market({}, none));
    expect(within(card()).queryByTestId("tc-kodex200-date")).toBeNull();
    expect(card().textContent).toContain("기준선 자료 확인 불가");
  });

  it("일간 칸은 화면 판정 기준 — 지연이면 사유 문장 · 휴장이면 값 · 운영 ok 라도 화면 지연이면 사유", async () => {
    const stale = { ...KOSPI_OK, status: "stale", display_state: "stale", trading_day_lag: 1 } as MarketContextKospi;
    let r = await renderHeadline(market({}, ctx({}, stale)));
    let daily = within(card()).getByTestId("tc-kospi-daily");
    expect(daily.textContent).toContain("KOSPI 원자료가 최근 거래일까지 갱신되지 않았습니다.");
    expect(daily.textContent).not.toContain("%");
    r.unmount();

    const holiday = { ...KOSPI_OK, display_state: "holiday", today_is_trading_day: false } as MarketContextKospi;
    r = await renderHeadline(market({}, ctx({}, holiday)));
    expect(within(card()).getByTestId("tc-kospi-daily").textContent).toContain("-3.65%");
    r.unmount();

    const okButScreenStale = { ...KOSPI_OK, display_state: "stale", trading_day_lag: 1 } as MarketContextKospi;
    await renderHeadline(market({}, ctx({}, okButScreenStale)));
    daily = within(card()).getByTestId("tc-kospi-daily");
    expect(daily.textContent).not.toContain("-3.65%");
    expect(daily.textContent).toContain("KOSPI 원자료가 최근 거래일까지 갱신되지 않았습니다.");
  });
});

describe("접힌 시장 칸의 자료 문제는 펼치기 전후 모두 보인다 (설계 §3 · 판정 Q3)", () => {
  function notes() {
    return within(card()).queryByTestId("tc-market-fold-notes")?.textContent ?? "";
  }

  it("거래량 평균 자료 부족 · 기준일 거래량 없음은 서로 다른 사유로 따로", async () => {
    const vol = {
      ...VOL_OK, volume: null, avg_prev20: null, avg_status: "insufficient",
      valid_count: 12, ratio: null, ratio_status: "volume_missing",
    } as unknown as StoredVolumeEvidence;
    await renderHeadline(market({ kodex200_stored_volume: vol }));
    const before = notes();
    expect(before).toContain("확인 필요:");
    expect(before).toContain("KODEX200 거래량 자료 없음");
    expect(before).not.toContain("거래량 거래량");
    expect(before).toContain("KODEX200 거래량 직전 20개 저장일 평균 자료 부족 (12/20)");
    // 평균 대비는 앞 칸 사유에서 나온 값이라 따로 세지 않는다.
    expect(before).not.toContain("평균 대비");
    fireEvent.click(marketToggle());
    expect(notes()).toBe(before);
  });

  it("거래량 자료 전체 없음 = 'KODEX200 거래량 자료 없음'(거래량 두 번 아님) · 평균 0 = 계산 불가", async () => {
    const { unmount } = await renderHeadline(market({ kodex200_stored_volume: null }));
    expect(notes()).toContain("KODEX200 거래량 자료 없음");
    expect(notes()).not.toContain("거래량 거래량");
    unmount();
    const zero = { ...VOL_OK, avg_prev20: 0, ratio: null, ratio_status: "avg_zero" } as StoredVolumeEvidence;
    await renderHeadline(market({ kodex200_stored_volume: zero }));
    expect(notes()).toBe("확인 필요: KODEX200 거래량 평균 대비 계산 불가");
  });

  it("코스피 1년 · 고점 대비 자료 없음 · 지속일 자료 없음", async () => {
    const k = { ...KOSPI_OK, return_1y_pct: null, high_52w_gap_pct: null } as MarketContextKospi;
    await renderHeadline(market({}, ctx({ regime_streak: null } as Partial<MarketContext>, k)));
    expect(notes()).toBe(
      "확인 필요: 코스피 1년 자료 없음 · 코스피 최근 1년 고점 대비 자료 없음 · 기존 시장 판정 지속일 자료 없음",
    );
  });

  it("시장 조회 실패 · 시장 판정 없음 → '시장 판정 확인 불가'", async () => {
    const { unmount } = await renderHeadline({ phase: "error", error: new Error("x") } as QueryState<MarketTopNResponse>);
    expect(notes()).toBe("확인 필요: 시장 판정 확인 불가");
    unmount();
    await renderHeadline(market({}, null));
    expect(notes()).toContain("시장 판정 확인 불가");
  });

  it("KOSPI 가 지연이면 수익률 칸 빈 값은 세지 않는다(사유가 이미 보임) · 위험 문구를 만들지 않는다", async () => {
    const stale = {
      ...KOSPI_OK, status: "stale", display_state: "stale", trading_day_lag: 1,
      return_1y_pct: null, high_52w_gap_pct: null,
    } as MarketContextKospi;
    await renderHeadline(market({}, ctx({}, stale)));
    expect(notes()).toBe("");
    expect(card().textContent).not.toMatch(/위험|하락 신호|경보/);
  });
});

// ── 오늘 내가 확인할 것 ──────────────────────────────────────────────────────
const holdings: QueryState<EnrichedHoldingsResult> = {
  phase: "success",
  stale: false,
  data: {
    items: [
      { ticker: "A1", name: "가", eval_amount: 600, invested_amount: 500 },
      { ticker: "B2", name: "나", eval_amount: 300, invested_amount: 400 },
      // 매입 금액 0 → 손익률 미산출(비중은 있음).
      { ticker: "C3", name: "다", eval_amount: 100, invested_amount: 0 },
    ],
  } as unknown as EnrichedHoldingsResult,
};

function topRow(ticker: string, name: string, r5: number, r20: number | null, ex: number | null) {
  return {
    ticker, name, eval_amount: 0, market_weight_pct: 1, pnl_rate_pct: 1,
    return_5d_pct: r5, return_20d_pct: r20, excess_vs_kodex200_20d_pctp: ex,
  };
}

function item(ticker: string, comparison: string): HoldingsMarketEvidenceItem {
  return {
    ticker,
    price_dates: { end_date: "2026-10-13", start_date_5d: "2026-10-01", start_date_20d: "2026-09-12", comparison },
    // POC5-13 — 보유 칸 요약이 종목 항목을 「확인 근거」와 같은 함수로 묶는다(API 필수 필드).
    short_term_momentum: { status: "ok", return_5d_pct: null, return_20d_pct: null, excess_vs_kodex200_20d_pctp: null },
  } as unknown as HoldingsMarketEvidenceItem;
}

function evidence(
  top: ReturnType<typeof topRow>[],
  mismatch: PriceBasisMismatch[] = [],
  items: HoldingsMarketEvidenceItem[] = [],
): QueryState<HoldingsMarketEvidenceResponse> {
  return {
    phase: "success",
    stale: false,
    data: {
      status: "ok",
      asof: "2026-10-14",
      summary: {
        total_holdings_count: 3, matched_topn_count: 0, not_in_current_topn_count: 3,
        evidence_unavailable_count: 0, constituents_available_count: 0,
        constituents_unavailable_count: 0, nav_discount_unavailable_count: 0,
      },
      holdings: items,
      judgment_summary: {
        market_position: { available: true },
        holdings: { available: true, top_holdings: top, coverage: { total: 3, need_check: 0, ok: 3 } },
        data_status: {},
      },
      price_basis: {
        reference_date: "2026-10-13",
        reference_ticker: "069500",
        kodex200_start_date_5d: "2026-10-06",
        kodex200_start_date_20d: "2026-09-15",
        date_mismatch: mismatch,
      },
      warnings: [],
    } as unknown as HoldingsMarketEvidenceResponse,
  };
}

function renderQueue(ev: QueryState<HoldingsMarketEvidenceResponse>, h = holdings) {
  return render(
    <JudgmentQueueSection market={market()} holdings={h} evidence={ev} onNavigate={() => undefined} />,
  );
}

describe("최대 3개 — 이름 · 5일 · 비중 + 종목별 '수치 더보기' (설계 §2 · 판정 Q3)", () => {
  it("기본은 5일 · 비중만 · 종목마다 따로 펼친다 · 값은 그대로", () => {
    renderQueue(evidence([topRow("A1", "가", -3, -5, 1.5), topRow("B2", "나", -2, -4, -0.5)]));
    const rows = screen.getAllByTestId("tc-top-row");
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain("5일 -3.00%");
    expect(rows[0].textContent).toContain("비중 60.0%");
    expect(rows[0].textContent).not.toContain("20일");
    expect(rows[0].textContent).not.toContain("손익");
    const b0 = within(rows[0]).getByRole("button", { name: "가 수치 더보기" });
    expect(b0).toHaveAttribute("aria-expanded", "false");
    expect(b0).toHaveClass("btn-md", "tc-fold-btn");
    fireEvent.click(b0);
    expect(rows[0].textContent).toContain("20일 -5.00% · KODEX200 대비 +1.50% · 손익 +20.00%");
    // 다른 종목은 그대로 접힘.
    expect(rows[1].textContent).not.toContain("20일");
    expect(within(rows[1]).getByRole("button", { name: "나 수치 더보기" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    fireEvent.click(within(rows[0]).getByRole("button", { name: "가 접기" }));
    expect(rows[0].textContent).not.toContain("20일");
  });

  it("접힌 값이 비면 펼치기 전후 모두 '확인 필요' — 비교 기간 불일치는 기존 날짜 사유 문구 재사용", () => {
    renderQueue(
      evidence(
        [topRow("A1", "가", -3, -5, null), topRow("B2", "나", -2, null, null), topRow("C3", "다", -1, -2, 0)],
        [],
        [item("A1", "window_mismatch"), item("B2", "ok")],
      ),
    );
    const rows = screen.getAllByTestId("tc-top-row");
    const a = rows[0].textContent ?? "";
    expect(a).toContain(
      "확인 필요: KODEX200 대비 20일: 종목 비교 기간 2026-09-12 ~ 2026-10-13 / KODEX200 비교 기간 2026-09-15 ~ 2026-10-13 — 기간이 달라 비교값을 비워 두었습니다.",
    );
    expect(rows[1].textContent).toContain("확인 필요: 20일 자료 없음 · KODEX200 대비 자료 없음");
    // C3: KODEX200 대비 0 은 값 · 매입 금액 0 이라 손익 미산출.
    expect(rows[2].textContent).toContain("확인 필요: 손익 자료 없음");
    expect(rows[2].textContent).not.toContain("KODEX200 대비 자료 없음");
    fireEvent.click(within(rows[0]).getByRole("button", { name: "가 수치 더보기" }));
    expect(rows[0].textContent).toContain("확인 필요: KODEX200 대비 20일: 종목 비교 기간");
    expect(rows[0].textContent).toContain("KODEX200 대비 -");
    expect(screen.getByLabelText("오늘 내가 확인할 것").textContent).not.toMatch(/위험|하락 신호|경보/);
  });
});

describe("가격 기준일이 달라 뺀 보유 — 3종목까지 그대로 · 4종목 이상 요약 + 모두 보기 (판정 Q4)", () => {
  const m = (ticker: string, name: string, d: string): PriceBasisMismatch => ({ ticker, name, end_date: d });

  it("3종목(같은 종목 여러 계좌 포함)은 기존 한 줄", () => {
    renderQueue(
      evidence([], [m("1", "가", "2026-08-12"), m("2", "나", "2026-08-12"), m("2", "나", "2026-08-12"), m("3", "다", "2026-09-01")]),
    );
    expect(screen.getByTestId("tc-price-mismatch").textContent).toBe(
      "가격 기준일이 달라 이 비교에서 뺀 보유: 가 · 나(저장 가격 기준일 2026-08-12) · 다(저장 가격 기준일 2026-09-01) — 자료 확인 필요",
    );
    expect(screen.queryByRole("button", { name: "모두 보기" })).toBeNull();
  });

  it("4종목 이상은 이유 · 전체 종목 수 · 기준일별 종목 수를 늘 보이고 이름만 펼친다", () => {
    renderQueue(
      evidence(
        [],
        [
          m("1", "가", "2026-08-12"), m("2", "나", "2026-08-12"), m("3", "다", "2026-08-12"),
          m("4", "라", "2026-09-01"), m("4", "라", "2026-09-01"), m("5", "마", "2026-09-01"),
        ],
      ),
    );
    const line = screen.getByTestId("tc-price-mismatch");
    expect(line.textContent).toContain(
      "가격 기준일이 달라 이 비교에서 뺀 보유 5종목(저장 가격 기준일 2026-08-12 3종목 · 2026-09-01 2종목) — 자료 확인 필요",
    );
    expect(line.textContent).not.toContain("가 · 나");
    const btn = within(line).getByRole("button", { name: "모두 보기" });
    expect(btn).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(btn);
    expect(line.textContent).toContain(
      "가 · 나 · 다(저장 가격 기준일 2026-08-12) · 라 · 마(저장 가격 기준일 2026-09-01)",
    );
    expect(line.textContent).toContain("5종목(저장 가격 기준일 2026-08-12 3종목 · 2026-09-01 2종목)");
    fireEvent.click(within(line).getByRole("button", { name: "접기" }));
    expect(line.textContent).not.toContain("가 · 나");
  });
});
