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
import KospiCloseBlock from "./KospiCloseBlock";
import type { MarketFlowContext } from "@/lib/api/marketFlow";
import type { KospiDetail } from "@/lib/api/morningBasis";
import { morningOk } from "@/lib/morningTestFixtures";

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
  return_20d_pct: -8.2, // 서버는 1m = 20거래일 · 3m = 60거래일(같은 계산)
  return_60d_pct: -14.6,
  return_1y_pct: 76.82,
  high_52w_gap_pct: -29.96,
} as MarketContextKospi;

// 2026-11-14(POC6-29-1 결과서 §5) — 코스피 수익률 · 위치는 아침 기준 응답의 저장값 상세(KOSPI 판정 상태와 무관)
const KD: KospiDetail = {
  status: "ok",
  as_of_date: "2026-10-12",
  r20: { start_date: "2026-09-12", end_date: "2026-10-12", pct: -8.2 },
  r60: { start_date: "2026-07-16", end_date: "2026-10-12", pct: -14.6 },
  return_1y_pct: 76.82,
  high_52w_gap_pct: -29.96,
  reason: null,
};

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

async function renderHeadline(m: QueryState<MarketTopNResponse>, kd: KospiDetail | null = KD) {
  const r = render(
    <KospiHeadline market={m} morning={{ phase: "success", data: morningOk({ kospi_detail: kd }), stale: false }} />,
  );
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
  it("기본 = 일간 변화 칸 없음(머리 줄 · 형수님 결정 2026-11-14) · 기준선 대비 위치는 판정 표(설계자 V3 D3), 나머지는 접힘 · 펼치면 같은 응답 값 · 다시 접힘", async () => {
    await renderHeadline(market());
    const c = card();
    const btn = marketToggle();
    expect(btn).toHaveAttribute("aria-expanded", "false");
    expect(btn).toHaveClass("btn-md", "tc-fold-btn");
    expect(within(c).queryByTestId("tc-kospi-daily")).toBeNull();
    expect(c.textContent).not.toContain("코스피 일간 변화");
    expect(c.textContent).not.toContain("KODEX200 MA20 대비");
    expect(c.textContent).not.toContain("기준선 대비 위치");
    // 접힌 칸은 그리지 않는다.
    expect(within(c).queryByTestId("tc-market-detail")).toBeNull();
    expect(c.textContent).not.toContain("1개월");
    expect(c.textContent).not.toContain("20거래일");
    expect(c.textContent).not.toContain("하락장");
    expect(within(c).queryByTestId("stored-volume")).toBeNull();
    // 정상이면 '확인 필요' 없음.
    expect(within(c).queryByTestId("tc-market-fold-notes")).toBeNull();

    fireEvent.click(btn);
    expect(marketToggle()).toHaveAttribute("aria-expanded", "true");
    const d = within(c).getByTestId("tc-market-detail");
    // 형수님 결정(2026-11-14) — 이름을 실제 계산대로 20 · 60거래일(위 1 · 3개월 칸 = 달력 기간과 겹치지 않게)
    // 2026-11-14 — 실제 계산 시작일(끝 = 제목의 종가 기준일)
    expect(within(d).getByText(/코스피 수익률·위치/).textContent).toBe("코스피 수익률·위치 · 10/12 종가 기준");
    for (const t of ["20거래일 -8.20% (9/12부터)", "60거래일 -14.60% (7/16부터)", "1년 +76.82%", "최근 1년 고점 대비 -29.96%"]) {
      expect(d.textContent).toContain(t);
    }
    expect(d.textContent).not.toMatch(/1개월|3개월/);
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
  it("날짜 = KOSPI 종가 기준일만(펼친 칸 제목) · '마지막 자료 기준일' 줄 없음(머리 줄 한 곳 · 2026-11-14) · KODEX200 기준선 · 판정 날짜는 이 카드에 없다", async () => {
    await renderHeadline(market());
    const c = card();
    expect(c.textContent).not.toContain("마지막 자료 기준일");
    expect(within(c).queryByTestId("tc-kodex200-date")).toBeNull();
    for (const d of ["2026-10-13", "2026-10-14"]) expect(c.textContent).not.toContain(d);
    expect(c.textContent).not.toContain("기준선 자료 확인 불가");
    fireEvent.click(marketToggle());
    expect(within(c).queryByTestId("tc-regime-date")).toBeNull();
    expect(c.textContent).not.toContain("KODEX200 기준일");
    expect(c.textContent).not.toContain("2026-10-14"); // 판정 날짜(market_context.asof)
    expect(c.textContent).not.toMatch(/10\/13|10\/14/);
    expect(within(c).getByTestId("tc-kospi-detail").textContent).toContain("10/12 종가 기준");
  });

  // 형수님 결정(2026-11-14 · POC6-29-1 결과서 §4-2) — 일간 변화는 코스피 공식 종가 머리 줄(시장 흐름 응답 obs.d1 · 비교 날짜)이
  // 보인다. 이 카드의 '코스피 일간 변화' 칸은 어떤 판정에서도 그리지 않는다(지연일 때 같은 값을 사유 문장으로 막던 칸).
  it.each([
    ["정상", { ...KOSPI_OK }],
    ["지연", { ...KOSPI_OK, status: "stale", display_state: "stale", trading_day_lag: 1 }],
    ["휴장일", { ...KOSPI_OK, display_state: "holiday", today_is_trading_day: false }],
    ["운영 ok · 화면 지연", { ...KOSPI_OK, display_state: "stale", trading_day_lag: 1 }],
  ])("일간 변화 칸 없음 — %s", async (_t, k) => {
    await renderHeadline(market({}, ctx({}, k as MarketContextKospi)));
    expect(within(card()).queryByTestId("tc-kospi-daily")).toBeNull();
    expect(card().textContent).not.toContain("코스피 일간 변화");
    expect(card().textContent).not.toContain("-3.65%");
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

  it("코스피 1년 · 고점 대비 자료 없음 · 60거래일 자료 부족 · 지속일 자료 없음", async () => {
    await renderHeadline(
      market({}, ctx({ regime_streak: null } as Partial<MarketContext>)),
      { ...KD, r60: null, return_1y_pct: null, high_52w_gap_pct: null },
    );
    expect(notes()).toBe(
      // 설계자 V3 D4 — '기존 시장 판정 지속일 자료 없음'은 그 칸을 빼며 함께 뺐다(지속일은 판정 표 · 당일 판정 상자)
      "확인 필요: 코스피 60거래일 자료 부족 · 코스피 1년 자료 없음 · 코스피 최근 1년 고점 대비 자료 없음",
    );
    fireEvent.click(marketToggle());
    expect(within(card()).getByTestId("tc-kospi-detail").textContent).toContain("60거래일 자료 부족");
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

  // 설계자 지시(2026-11-14) — 주말 · 장 시작 전(KOSPI 기준일 ≠ 기대 직전 거래일 · 시장 판정 응답은 값 없음)에도 저장값이
  // 있으면 상세를 읽는다. 상세가 계산되지 않으면(저장 종가 없음 등) 빈 칸을 세지 않는다(칸 자리에 사유).
  it.each([
    ["주말(휴장일 · 지연)", { ...KOSPI_OK, status: "stale", display_state: "stale", trading_day_lag: 1, today_is_trading_day: false }],
    ["장 시작 전(평일 · 지연)", { ...KOSPI_OK, status: "stale", display_state: "stale", trading_day_lag: 1, today_is_trading_day: true }],
  ])("%s — 시장 판정 응답에 값이 없어도 저장값 상세가 보인다 · 위험 문구 없음", async (_t, k) => {
    const stale = { ...k, return_20d_pct: null, return_60d_pct: null, return_1y_pct: null, high_52w_gap_pct: null } as MarketContextKospi;
    await renderHeadline(market({}, ctx({}, stale)));
    expect(notes()).toBe("");
    fireEvent.click(marketToggle());
    const d = within(card()).getByTestId("tc-kospi-detail");
    expect(d.textContent).toContain("20거래일 -8.20% (9/12부터)");
    expect(d.textContent).toContain("1년 +76.82%");
    expect(d.textContent).not.toMatch(/확인 불가|원자료가 최근 거래일까지/);
    expect(card().textContent).not.toMatch(/위험|하락 신호|경보/);
  });

  it("그날 KODEX 200 저장 가격이 없으면 20 · 60거래일 '계산 불가' + 쉬운 말 사유 · 1년 · 고점 대비는 값(독립 검토 2026-11-14)", async () => {
    const reason = "10/12 KODEX 200 저장 가격이 없어 20 · 60거래일은 계산하지 못했습니다";
    await renderHeadline(market(), { ...KD, r20: null, r60: null, reason });
    expect(notes()).toBe("확인 필요: 코스피 20거래일 계산 불가 · 코스피 60거래일 계산 불가");
    fireEvent.click(marketToggle());
    const d = within(card()).getByTestId("tc-kospi-detail");
    expect(d.textContent).toContain("20거래일 계산 불가");
    expect(d.textContent).toContain("60거래일 계산 불가");
    expect(d.textContent).toContain("1년 +76.82%");
    expect(within(d).getByTestId("tc-kospi-detail-reason").textContent).toBe(reason);
    expect(d.textContent).not.toMatch(/축|axis/);
  });

  it("상세를 계산하지 못하면 빈 칸을 세지 않고 칸 자리에 사유 · 아침 기준 읽기 실패 · 옛 서버(칸 없음)", async () => {
    const r = await renderHeadline(market(), { ...KD, status: "unavailable", r20: null, r60: null, return_1y_pct: null, high_52w_gap_pct: null, reason: "코스피 기준일이 KODEX 200 거래일 축에 없음" });
    expect(notes()).toBe("");
    fireEvent.click(marketToggle());
    expect(within(card()).getByTestId("tc-kospi-detail").textContent).toBe("코스피 수익률·위치코스피 수익률 확인 불가 — 코스피 기준일이 KODEX 200 거래일 축에 없음");
    r.unmount();
    render(<KospiHeadline market={market()} morning={{ phase: "error" }} startOpen />);
    expect(within(card()).getByTestId("tc-kospi-detail").textContent).toContain("코스피 수익률을 불러오지 못했습니다");
    expect(notes()).toBe("");
  });
});

// POC6-29 — 「보유 자세히」(최대 3개 · 종목별 수치 더보기 · 가격 기준일이 달라 뺀 보유)는 카드 합침으로 없앴다(설계 §2 ·
// 종목별 수치는 「보유」). 그 구역만 보던 두 묶음 시험은 지웠다.

// 독립 검토(2026-11-14) — 코스피 1 · 3 · 6개월 칸은 시장 흐름을 불러오는 중 · 불러오지 못함 · 그 기간 없음을 나눈다
// ('자료 없음'으로 뭉뚱그리지 않음).
describe("코스피 1 · 3 · 6개월 칸 — 값이 없을 때의 문구", () => {
  const MORNING = { phase: "success", data: morningOk(), stale: false } as const;
  const tiles = () => ["tc-tile-1m", "tc-tile-3m", "tc-tile-6m"].map((id) => screen.getByTestId(id).textContent ?? "");
  it.each([
    ["불러오는 중", { phase: "loading" }, "확인 중불러오는 중"],
    ["불러오지 못함", { phase: "error" }, "확인 불가시장 흐름을 불러오지 못했습니다"],
    ["응답에 그 기간 없음", { phase: "success", data: { periods: {}, short_lines: [] }, stale: false }, "확인 불가자료 없음"],
  ])("%s", async (_t, flow, tail) => {
    render(
      <KospiCloseBlock
        market={market()}
        flow={flow as QueryState<MarketFlowContext>}
        morning={MORNING}
      />,
    );
    await act(async () => {
      await Promise.resolve();
    });
    const [m1, m3, m6] = tiles();
    expect(m1).toBe(`코스피 1개월${tail}`);
    expect(m3).toBe(`코스피 3개월${tail}`);
    expect(m6).toBe(`코스피 6개월${tail}`);
  });
});
