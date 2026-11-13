// POC5-UI-03 — 「오늘의 투자 점검」 정보 배치: 기본 접힘 · 펼침 · 접힌 채 보이는 경고 · 날짜 출처 ·
// 최대 3개 종목별 펼침 · 뺀 보유 긴 목록(설계 V1 §2~§4 · 판정 2026-10-14 Q1~Q4).
// 부모가 받은 응답만 표시한다(추가 조회 없음). 화면 안 상태만 쓴다.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within, act, fireEvent } from "@testing-library/react";
import { __resetQueryCache, type QueryState } from "@/lib/api/queryCache";
import type {
  MarketContext,
  MarketContextKospi,
  MarketTopNResponse,
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
  it("기본 = 일간 변화만(기준선 대비 위치는 판정 표 · 설계자 V3 D3), 나머지는 접힘 · 펼치면 같은 응답 값 · 다시 접힘", async () => {
    await renderHeadline(market());
    const c = card();
    const btn = marketToggle();
    expect(btn).toHaveAttribute("aria-expanded", "false");
    expect(btn).toHaveClass("btn-md", "tc-fold-btn");
    expect(within(c).getByTestId("tc-kospi-daily").textContent).toContain("-3.65%");
    expect(c.textContent).not.toContain("KODEX200 MA20 대비");
    expect(c.textContent).not.toContain("기준선 대비 위치");
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
    // 설계자 V3 D4 — '기존 시장 판정 참고'(국면 · 지속일 · KODEX200 기준일)는 뺐다(당일 판정 · 판정 표와 중복)
    expect(d.textContent).not.toContain("하락장");
    expect(d.textContent).not.toContain("기존 시장 판정 참고");
    expect(d.textContent).not.toContain("KODEX200 기준일");
    expect(within(d).getByTestId("stored-volume").textContent).toContain("40,337,658주");

    fireEvent.click(marketToggle());
    expect(within(c).queryByTestId("tc-market-detail")).toBeNull();
  });

  // 설계자 RESULT 재판정 V3 D3 · D4(2026-11-13) — 기준선 옆 날짜(market_risk_reference) · 판정 줄 날짜(market_context.asof)를
  // 보이던 두 칸이 빠져, 이 카드의 날짜는 KOSPI 기준일 하나만(KODEX200 날짜로 대신하지 않음 · 판정 날짜는 판정 표).
  it("날짜 = 'KOSPI 기준일'만 · KODEX200 기준선 · 판정 날짜는 이 카드에 없다(펼친 뒤에도 · 거래량은 자기 기준일)", async () => {
    await renderHeadline(market());
    const c = card();
    expect(c.textContent).toContain("마지막 자료 기준일 2026-10-12");
    expect(within(c).queryByTestId("tc-kodex200-date")).toBeNull();
    for (const d of ["2026-10-13", "2026-10-14"]) expect(c.textContent).not.toContain(d);
    expect(c.textContent).not.toContain("기준선 자료 확인 불가");
    fireEvent.click(marketToggle());
    expect(within(c).queryByTestId("tc-regime-date")).toBeNull();
    expect(c.textContent).not.toContain("KODEX200 기준일");
    expect(c.textContent).not.toContain("2026-10-14"); // 판정 날짜(market_context.asof)
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
      // 설계자 V3 D4 — '기존 시장 판정 지속일 자료 없음'은 그 칸을 빼며 함께 뺐다(지속일은 판정 표 · 당일 판정 상자)
      "확인 필요: 코스피 1년 자료 없음 · 코스피 최근 1년 고점 대비 자료 없음",
    );
  });

  // 설계자 V3 D4 — 접힌 칸에 시장 판정이 없으므로 '시장 판정 확인 불가'를 이 칸의 안내로 내지 않는다(판정 확인 불가는 판정 표
  // '당일' 줄 · 당일 판정 상자가 알림). 시장 조회 실패면 코스피 칸이 자기 상태 사유를 보인다(기존).
  it("시장 조회 실패 · 시장 판정 없음 → 접힌 칸 안내에 '시장 판정' 없음(그 칸이 빠짐)", async () => {
    const { unmount } = await renderHeadline({ phase: "error", error: new Error("x") } as QueryState<MarketTopNResponse>);
    expect(notes()).not.toContain("시장 판정");
    unmount();
    await renderHeadline(market({}, null));
    expect(notes()).not.toContain("시장 판정");
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

// POC6-29 — 「보유 자세히」(최대 3개 · 종목별 수치 더보기 · 가격 기준일이 달라 뺀 보유)는 카드 합침으로 없앴다(설계 §2 ·
// 종목별 수치는 「보유」). 그 구역만 보던 두 묶음 시험은 지웠다.
