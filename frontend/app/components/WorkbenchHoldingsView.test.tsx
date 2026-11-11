// 「ETF 비교하기 › 보유」 화면 계약(POC6-28 · 판정 2026-11-11 §4 · Q6).
// 요약 · 보유 · 보유 근거 · 가격 시계열을 가짜로 바꿔 응답을 통제한다. 실제 네트워크 · 운영 자료 미의존.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import { __resetEtfCompareCondition } from "@/lib/etfCompareCondition";
import { summaryOk } from "@/lib/etfCompareTestFixtures";

const fetchEtfCompareSummary = vi.fn();
const fetchEnrichedHoldings = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
const fetchPriceSeries = vi.fn();

vi.mock("@/lib/api/etfCompare", async (orig) => ({
  ...(await orig<typeof import("@/lib/api/etfCompare")>()),
  fetchEtfCompareSummary: (...a: unknown[]) => fetchEtfCompareSummary(...a),
}));
vi.mock("@/lib/api", () => ({
  fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
  fetchHoldingsMarketEvidence: (...a: unknown[]) => fetchHoldingsMarketEvidence(...a),
  fetchPriceSeries: (...a: unknown[]) => fetchPriceSeries(...a),
}));

import WorkbenchHoldingsView, { declineWeightLine } from "./WorkbenchHoldingsView";
import { flow, link } from "@/lib/etfCompareTestFixtures";
import { evidenceNotice } from "./workbench/holdingParts";
import type { CompareSummaryOk, PriceFlow } from "@/lib/api/etfCompare";

function item(ticker: string, name: string, weight: number | null, pnl: number | null = 1000) {
  return {
    ticker,
    name,
    quantity: 1,
    avg_buy_price: 1,
    invested_amount: 1,
    current_price: 100,
    price_asof: "x",
    price_source: "n",
    eval_amount: 1000,
    pnl_amount: pnl,
    pnl_rate_pct: -12.5,
    buy_weight_pct: null,
    market_weight_pct: weight,
    price_missing: false,
    calc_missing: false,
  };
}

function holdings() {
  return {
    items: [
      item("H00002", "분산 ETF", 30),
      item("H00002", "분산 ETF", null),
      item("B00001", "반도체 전공정", 0.7),
      item("005930", "개별 주식 A", 20),
    ],
  };
}

const D10 = { judgeable: true, state: "D10_PLUS", label: "PC 20저장일 하락 10% 이상", return_20d_pct_1dp: -27.0, unjudged_reason: null };
const NONE = { judgeable: true, state: null, label: null, return_20d_pct_1dp: -2.0, unjudged_reason: null };

// 보유 근거 응답(다른 시점에 읽은 응답 · 요약과 일부러 다른 값). 요약이 있으면 화면은 이 값으로 하락 · 흐름을 말하지 않는다.
function ev(ticker: string, p: { decline?: boolean; comparison?: string; r20?: number; ex20?: number }) {
  return {
    ticker,
    name: ticker,
    holding: {},
    topn_match: { status: "not_in_current_topn" },
    returns: {
      status: "unavailable",
      one_month_return_pct: null as number | null,
      three_month_return_pct: null as number | null,
    },
    excess_return: {},
    short_term_momentum: {
      status: "ok",
      return_5d_pct: -9.99,
      return_10d_pct: null,
      return_20d_pct: p.r20 ?? -20.0,
      excess_vs_kodex200_5d_pctp: null,
      excess_vs_kodex200_10d_pctp: null,
      excess_vs_kodex200_20d_pctp: p.ex20 ?? -5.0,
    },
    constituents_overlap: { status: "ok", overlap_with_market_core: [] },
    nav_discount: { status: "ok" },
    evidence_notes: [],
    price_dates: {
      end_date: "2026-11-10",
      start_date_5d: "2026-11-03",
      start_date_20d: "2026-10-13",
      comparison: p.comparison ?? "ok",
    },
    decline_band: p.decline ? { ...D10, return_20d_pct_1dp: -20.0 } : NONE,
  };
}

// 보유 근거는 요약과 반대로 둔다 — 반도체 전공정 · 개별 주식 A 는 하락 아님, 분산 ETF 는 하락.
function evidence() {
  return {
    status: "ok",
    asof: "2026-11-10",
    holdings: [
      ev("B00001", {}),
      ev("H00002", { decline: true, comparison: "window_mismatch", r20: -12.0 }),
      ev("005930", {}),
    ],
  };
}

// 요약 같은 응답의 가격 흐름 — 반도체 전공정 · 개별 주식 A = 하락 10% 이상 · 분산 ETF = 비교 기간 다름(구간 밖).
const FLOWS: Record<string, PriceFlow> = {
  B00001: flow({
    return_5d_pct: -10.61,
    return_20d_pct: -27.02,
    excess_vs_kodex200_20d_pctp: -12.54,
    kodex200_return_20d_pct: -14.48,
    decline_band: D10,
  }),
  H00002: flow({
    comparison: "window_mismatch",
    return_20d_pct: -2.0,
    excess_vs_kodex200_20d_pctp: null,
    kodex200_return_20d_pct: null,
    decline_band: NONE,
  }),
  "005930": flow({
    return_20d_pct: -17.5,
    excess_vs_kodex200_20d_pctp: -3.02,
    kodex200_return_20d_pct: -14.48,
    decline_band: { ...D10, return_20d_pct_1dp: -17.5 },
  }),
};

function summary(over: Record<string, Partial<PriceFlow> | null> = {}): CompareSummaryOk {
  const s = summaryOk();
  return {
    ...s,
    holdings: {
      ...s.holdings,
      items: s.holdings.items.map((h) => {
        const o = over[h.ticker];
        const f = o === null ? null : { ...FLOWS[h.ticker], ...(o ?? {}) };
        return { ...h, price_flow: f, end_price: f ? f.end_price : null };
      }),
    },
  };
}

const nav = vi.fn();

beforeEach(() => {
  __resetQueryCache();
  __resetEtfCompareCondition();
  for (const f of [fetchEtfCompareSummary, fetchEnrichedHoldings, fetchHoldingsMarketEvidence, fetchPriceSeries, nav]) f.mockReset();
  fetchEtfCompareSummary.mockResolvedValue(summary());
  fetchEnrichedHoldings.mockResolvedValue(holdings());
  fetchHoldingsMarketEvidence.mockResolvedValue(evidence());
  fetchPriceSeries.mockResolvedValue({ ticker: "x", availability: "NO_DATA", series: [] });
});

const rows = () => screen.getAllByTestId("ec-hold-row");
const rowOf = (name: string) => rows().find((r) => r.textContent?.includes(name))!;

describe("「보유」 기본 행 · 배지 · 순서", () => {
  it("같은 ticker 다계좌 = 한 행 · 비중 부분 결측 표기 · 하락장이면 기존 하락 판정 보유 먼저", async () => {
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    await screen.findByTestId("ec-hold-regime");
    expect(rows()).toHaveLength(3);
    // 하락 판정 = 개별 주식 A(비중 20) · 반도체 전공정(0.7) 먼저 → 분산 ETF(30)
    expect(rows().map((r) => r.textContent?.split("비중")[0])).toEqual([
      expect.stringContaining("개별 주식 A"),
      expect.stringContaining("반도체 전공정"),
      expect.stringContaining("분산 ETF"),
    ]);
    expect(rows()[2]).toHaveTextContent("2계좌 합산");
    expect(rows()[2]).toHaveTextContent("(1/2)");
    expect(screen.getByTestId("ec-hold-regime")).toHaveTextContent(
      "최근 하락한 보유부터 보여 줍니다 · 기존 하락 판정 2종목 · 보유 비중 20.70%",
    );
  });

  it("점검 사유는 직접 하위권 + 수익률 음수인 행만 · 하락 · 노출 · 자료 부족 배지는 따로", async () => {
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    const reasons = screen.getAllByTestId("ec-point-reason");
    expect(reasons).toHaveLength(1);
    expect(reasons[0]).toHaveTextContent("점검 사유: 후보 하위 1위 · 1개월 -44.92%(10/12 → 11/9)");
    const [stock, semi, etf] = rows();
    expect(semi).toHaveTextContent("PC 20저장일 하락 10% 이상");
    expect(semi).toHaveTextContent("노출 확인");
    expect(stock).toHaveTextContent("개별 주식");
    expect(stock).not.toHaveTextContent("비교 자료 부족");
    expect(etf).toHaveTextContent("비교 자료 부족");
    expect(etf).not.toHaveTextContent("PC 20저장일 하락");
  });

  it("거르기 — 최근 하락 2 · 약세 묶음 접점 2 · 비교 자료 부족 1(개별 주식 제외)", async () => {
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    fireEvent.click(screen.getByRole("button", { name: "비교 자료 부족 1" }));
    expect(rows()).toHaveLength(1);
    expect(rows()[0]).toHaveTextContent("분산 ETF");
    fireEvent.click(screen.getByRole("button", { name: "약세 묶음 접점 2" }));
    expect(rows().map((r) => r.textContent)).toEqual([
      expect.stringContaining("개별 주식 A"),
      expect.stringContaining("반도체 전공정"),
    ]);
    fireEvent.click(screen.getByRole("button", { name: "최근 하락 2" }));
    expect(rows().map((r) => r.textContent)).toEqual([
      expect.stringContaining("개별 주식 A"),
      expect.stringContaining("반도체 전공정"),
    ]);
  });
});

describe("「보유」 행 상세 — 이름을 나눈 근거(판정 §4)", () => {
  it("최근 가격 변화 · 같은 기간 KODEX 200 · 후보 조회 기간 · 가격 기준일 = 요약 같은 응답", async () => {
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    fireEvent.click(rowOf("반도체 전공정"));
    const d = await screen.findByTestId("ec-hold-detail");
    expect(within(d).getByTestId("ec-hold-recent")).toHaveTextContent(
      "5거래일 11/2 → 11/9 -10.61% · 20거래일 10/13 → 11/9 -27.02%",
    );
    expect(within(d).getByTestId("ec-hold-kodex")).toHaveTextContent(
      "10/13 → 11/9 · 이 종목 -27.02% · KODEX 200 -14.48% · 차이 -12.54%p",
    );
    expect(within(d).getByTestId("ec-hold-candidate")).toHaveTextContent("1개월 -44.92% · 10/12 → 11/9 · 하위 1위");
    expect(within(d).getByTestId("ec-hold-dates")).toHaveTextContent(
      "후보 · 보유 가격 흐름 모두 11/9 가격 = 마감 뒤 저장(11/10 13:18 저장)",
    );
    expect(within(d).getByTestId("ec-hold-exposure")).toHaveTextContent("직접 — 후보 하위 1위 · 노출 확인: 주성엔지니어링(1)");
  });

  it("비교 기간이 다르면 · 기준일이 다르면 KODEX 200 줄은 비교하지 않는다(이유를 나눠 적음)", async () => {
    fetchEtfCompareSummary.mockResolvedValue(
      summary({
        "005930": {
          end_date: "2026-11-10",
          comparison: "date_mismatch",
          excess_vs_kodex200_20d_pctp: null,
          kodex200_return_20d_pct: null,
          decline_band: { ...NONE, judgeable: false, return_20d_pct_1dp: null, unjudged_reason: "date_mismatch" },
          end_price: { date: "2026-11-10", state: "unknown", fetched_at_kst: null },
        },
      }),
    );
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    fireEvent.click(rowOf("분산 ETF"));
    expect(await screen.findByTestId("ec-hold-kodex")).toHaveTextContent("KODEX 200 비교 기간이 달라 비교하지 않음");
    fireEvent.click(rowOf("개별 주식 A"));
    expect(await screen.findByTestId("ec-hold-kodex")).toHaveTextContent("기준일이 PC 비교 기준일과 달라 비교하지 않음");
    expect(screen.getByTestId("ec-hold-recent")).toHaveTextContent(
      "기준일이 PC 비교 기준일과 달라 비교하지 않음(이 종목 끝일 11/10)",
    );
    expect(screen.getByTestId("ec-hold-dates")).toHaveTextContent(
      "후보 근거 11/9 가격 = 마감 뒤 저장 · 보유 가격 흐름 11/10 가격 = PC 저장 가격 · 마감값 확인 필요 — 기준일이 달라 두 근거를 따로 봅니다",
    );
    expect(rowOf("개별 주식 A")).not.toHaveTextContent("PC 20저장일 하락");
  });

  it("개별 주식 = NAV · ETF 구성종목 해당 없음 · 구성 자료 없는 ETF = 기존 「ETF 구성종목」 경로", async () => {
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    fireEvent.click(rowOf("개별 주식 A"));
    expect(await screen.findByTestId("ec-hold-exposure")).toHaveTextContent("개별 주식 — NAV · ETF 구성종목 해당 없음");
    fireEvent.click(rowOf("분산 ETF"));
    const exp = await screen.findByTestId("ec-hold-exposure");
    expect(exp).toHaveTextContent("구성종목 자료 없음 — 노출을 비교할 수 없음");
    fireEvent.click(within(exp).getByRole("button", { name: "ETF 구성종목에서 확인 →" }));
    expect(nav).toHaveBeenCalledWith("etf_exposure");
  });

  it("월간 수익률은 3개월이 없는 부분 응답에서도 확인된 1개월 값을 보인다(보유 근거)", async () => {
    const e = evidence();
    e.holdings[0].returns = { status: "partial", one_month_return_pct: -12.34, three_month_return_pct: null };
    fetchHoldingsMarketEvidence.mockResolvedValue(e);
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    fireEvent.click(rowOf("반도체 전공정"));
    expect(await screen.findByTestId("ec-hold-detail")).toHaveTextContent("월간 수익률(보유 근거)-12.34%");
  });

  it("[검증자 r2 F4] 요약이 있으면 하락 판정 · 순서 · 흐름 숫자는 요약 같은 응답만 — 다른 시점 보유 근거 값과 섞지 않음", async () => {
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    // 보유 근거는 분산 ETF 를 하락(-12%)으로 · 반도체 전공정을 구간 밖(-20%)으로 보지만 화면은 요약 값만 쓴다.
    expect(rowOf("분산 ETF")).not.toHaveTextContent("PC 20저장일 하락");
    expect(rowOf("반도체 전공정")).toHaveTextContent("PC 20저장일 하락 10% 이상");
    expect(rowOf("반도체 전공정")).not.toHaveTextContent("저장 상태 확인 불가");
    fireEvent.click(rowOf("반도체 전공정"));
    const d = await screen.findByTestId("ec-hold-detail");
    expect(d).not.toHaveTextContent("-20.00%");
    expect(d).not.toHaveTextContent("-9.99%");
    expect(d).not.toHaveTextContent("-5.00%p");
  });

  it("[검증자 r2 F4] '장중'은 그 흐름을 계산한 같은 응답 · 같은 끝일 행이 장중일 때만", async () => {
    const intraday = { date: "2026-11-09", state: "intraday" as const, fetched_at_kst: "2026-11-09T13:18:02+09:00" };
    fetchEtfCompareSummary.mockResolvedValue(summary({ B00001: { end_price: intraday } }));
    const { unmount } = render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    expect(within(rowOf("반도체 전공정")).getByText(/PC 20저장일 하락 10% 이상/)).toHaveTextContent(
      "PC 20저장일 하락 10% 이상 · 장중",
    );
    expect(within(rowOf("개별 주식 A")).getByText(/PC 20저장일 하락 10% 이상/)).not.toHaveTextContent("장중");
    fireEvent.click(rowOf("반도체 전공정"));
    expect(await screen.findByTestId("ec-hold-dates")).toHaveTextContent(
      "후보 · 보유 가격 흐름 모두 11/9 가격 = 장중 저장값 · 11/9 13:18 저장",
    );
    unmount();
    __resetQueryCache();
    // 같은 날짜라도 다시 저장된 판(마감 뒤)이면 그 응답의 흐름 · 상태가 함께 바뀐다 — 옛 값에 새 상태를 붙이지 않음.
    fetchEtfCompareSummary.mockResolvedValue(
      summary({
        B00001: {
          return_20d_pct: -25.0,
          decline_band: { ...D10, return_20d_pct_1dp: -25.0 },
          end_price: { date: "2026-11-09", state: "after_close", fetched_at_kst: "2026-11-09T15:40:00+09:00" },
        },
      }),
    );
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    expect(within(rowOf("반도체 전공정")).getByText(/PC 20저장일 하락 10% 이상/)).not.toHaveTextContent("장중");
    fireEvent.click(rowOf("반도체 전공정"));
    expect(await screen.findByTestId("ec-hold-recent")).toHaveTextContent("20거래일 10/13 → 11/9 -25.00%");
    expect(screen.getByTestId("ec-hold-dates")).toHaveTextContent("11/9 가격 = 마감 뒤 저장(11/9 15:40 저장)");
  });

  it("요약에 저장 가격이 없는 보유 = 흐름 없음 · 비교 자료 부족 · 보유 근거 하락으로 채우지 않음", async () => {
    fetchHoldingsMarketEvidence.mockResolvedValue({
      ...evidence(),
      holdings: [ev("B00001", { decline: true }), ev("H00002", {}), ev("005930", {})],
    });
    fetchEtfCompareSummary.mockResolvedValue(summary({ B00001: null }));
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    const semi = rowOf("반도체 전공정");
    expect(semi).not.toHaveTextContent("PC 20저장일 하락");
    expect(semi).toHaveTextContent("비교 자료 부족");
    fireEvent.click(semi);
    expect(await screen.findByTestId("ec-hold-recent")).toHaveTextContent("가격 변화 없음(저장 가격 없음)");
    expect(screen.getByTestId("ec-hold-kodex")).toHaveTextContent("같은 기간 비교 자료 없음(저장 가격 없음)");
    expect(screen.getByTestId("ec-hold-dates")).toHaveTextContent("이 종목 저장 가격 없음");
  });

  it("요약을 못 받으면 보유 근거 값 + '저장 상태 확인 불가' · 날짜 문제는 '비교 자료 부족'", async () => {
    fetchEtfCompareSummary.mockRejectedValue(new Error("down"));
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    await screen.findByText(/비교 자료 조회 실패/);
    const etf = rowOf("분산 ETF");
    expect(etf).toHaveTextContent("비교 자료 부족");
    expect(within(etf).getByText(/PC 20저장일 하락 10% 이상/)).toHaveTextContent(
      "PC 20저장일 하락 10% 이상 · 저장 상태 확인 불가",
    );
    expect(screen.getByRole("button", { name: "최근 하락 1" })).toBeInTheDocument();
    fireEvent.click(etf);
    expect(await screen.findByTestId("ec-hold-recent")).toHaveTextContent(
      "5거래일 11/3 → 11/10 -9.99% · 20거래일 10/13 → 11/10 -12.00%(보유 근거 · 저장 상태 확인 불가)",
    );
    expect(screen.getByTestId("ec-hold-kodex")).toHaveTextContent("비교 요약 없음 — 보이지 않음");
    expect(screen.getByTestId("ec-hold-dates")).toHaveTextContent(
      "보유 근거 11/10 가격 = 저장 상태 확인 불가(비교 요약 없음)",
    );
    // 보유 근거는 읽었으니 안내 줄은 없다(요약 실패는 머리 줄이 따로 알림).
    expect(screen.queryByTestId("ec-ev-notice")).toBeNull();
  });

  it("보유 근거 조회가 실패해도 보유 목록은 남는다", async () => {
    fetchHoldingsMarketEvidence.mockRejectedValue(new Error("down"));
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    expect(await screen.findAllByTestId("ec-hold-row")).toHaveLength(3);
    expect(await screen.findByText(/보유 근거 조회 실패/)).toBeInTheDocument();
  });
});

describe("[검증자 r3 F5] 실패 · 이전 조회값 안내 = 실제로 화면에 쓰인 출처", () => {
  const notice = () => screen.getByTestId("ec-ev-notice");

  it("요약 있음 + 보유 근거 실패 = 월간 수익률만 못 보임 · 가격 변화 · 하락 판정은 요약 값으로 보임", async () => {
    fetchHoldingsMarketEvidence.mockRejectedValue(new Error("down"));
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    await screen.findByTestId("ec-ev-notice");
    expect(notice()).toHaveTextContent(
      "보유 근거 조회 실패 — 월간 수익률(보유 근거)을 보이지 못합니다. 가격 변화 · 하락 판정은 비교 요약 값으로 보입니다.",
    );
    expect(notice()).not.toHaveTextContent("가격 변화 · 하락 판정을 보이지 못합니다");
    // 실제로 요약 값이 보인다(검증자 재현 그대로).
    expect(rowOf("반도체 전공정")).toHaveTextContent("PC 20저장일 하락 10% 이상");
    fireEvent.click(rowOf("반도체 전공정"));
    expect(await screen.findByTestId("ec-hold-recent")).toHaveTextContent("20거래일 10/13 → 11/9 -27.02%");
    expect(screen.getByTestId("ec-hold-month")).toHaveTextContent("확인값 없음(보유 근거 조회 실패)");
  });

  it("요약 없음 + 보유 근거 실패 = 가격 변화 · 하락 판정도 못 보임", async () => {
    fetchHoldingsMarketEvidence.mockRejectedValue(new Error("down"));
    fetchEtfCompareSummary.mockRejectedValue(new Error("down"));
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    expect(await screen.findByTestId("ec-ev-notice")).toHaveTextContent(
      "보유 근거 조회 실패 — 월간 수익률(보유 근거)과 가격 변화 · 하락 판정(비교 요약 없음)을 보이지 못합니다.",
    );
    fireEvent.click(rowOf("반도체 전공정"));
    expect(await screen.findByTestId("ec-hold-recent")).toHaveTextContent(
      "가격 변화 없음(비교 요약 없음 · 보유 근거 조회 실패)",
    );
    expect(screen.getByTestId("ec-hold-dates")).toHaveTextContent(
      "가격 기준일 확인 불가(비교 요약 없음 · 보유 근거 조회 실패)",
    );
  });

  it("요약에 없는 보유 = '비교 요약에 이 종목 없음' · 비교 자료 부족 · 하락 수에서 '아님'으로 세지 않음", async () => {
    const s = summary();
    fetchEtfCompareSummary.mockResolvedValue({
      ...s,
      holdings: { ...s.holdings, items: s.holdings.items.filter((h) => h.ticker !== "B00001") },
    });
    fetchHoldingsMarketEvidence.mockRejectedValue(new Error("down"));
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    expect(await screen.findByTestId("ec-ev-notice")).toHaveTextContent(
      "보유 근거 조회 실패 — 월간 수익률(보유 근거)과 비교 요약에 가격 흐름이 없는 보유 1종목의 가격 변화 · 하락 판정을 보이지 못합니다.",
    );
    expect(screen.getByTestId("ec-hold-regime")).toHaveTextContent(
      "기존 하락 판정 1종목 · 보유 비중 20.00% · 하락 판정을 못 한 보유 1종목은 세지 않음",
    );
    const semi = rowOf("반도체 전공정");
    expect(semi).toHaveTextContent("비교 자료 부족");
    fireEvent.click(semi);
    expect(await screen.findByTestId("ec-hold-kodex")).toHaveTextContent("비교 요약에 이 종목 없음 — 보이지 않음");
    expect(screen.getByTestId("ec-hold-candidate")).toHaveTextContent("후보 비교 자료 없음(비교 요약에 이 종목 없음)");
    expect(screen.getByTestId("ec-hold-exposure")).toHaveTextContent("후보 비교 자료 없음(비교 요약에 이 종목 없음)");
    expect(screen.getByTestId("ec-hold-recent")).toHaveTextContent(
      "가격 변화 없음(비교 요약에 이 종목 없음 · 보유 근거 조회 실패)",
    );
  });

  it("보유 근거 다시 조회 실패(이전 값 남음) = 이전 조회값이라고 적는다 · 요약 값은 그대로", async () => {
    const e = evidence();
    e.holdings[0].returns = { status: "partial", one_month_return_pct: -12.34, three_month_return_pct: null };
    fetchHoldingsMarketEvidence.mockResolvedValue(e);
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    expect(screen.queryByTestId("ec-ev-notice")).toBeNull();
    fetchHoldingsMarketEvidence.mockRejectedValue(new Error("down"));
    fireEvent.click(screen.getByRole("button", { name: "다시 불러오기" }));
    expect(await screen.findByTestId("ec-ev-notice")).toHaveTextContent(
      "보유 근거 다시 조회 실패 — 월간 수익률(보유 근거)은 이전 조회값입니다(최신 아님). 가격 변화 · 하락 판정은 비교 요약 값입니다.",
    );
    fireEvent.click(rowOf("반도체 전공정"));
    expect(await screen.findByTestId("ec-hold-month")).toHaveTextContent("-12.34% · 이전 조회값(다시 조회 실패)");
  });

  it("요약 없음 + 보유 근거 다시 조회 실패 = 가격 변화 · 하락 판정도 이전 조회값", async () => {
    fetchEtfCompareSummary.mockRejectedValue(new Error("down"));
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    await screen.findByText(/비교 자료 조회 실패/);
    fetchHoldingsMarketEvidence.mockRejectedValue(new Error("down"));
    fireEvent.click(screen.getByRole("button", { name: "다시 불러오기" }));
    expect(await screen.findByTestId("ec-ev-notice")).toHaveTextContent(
      "보유 근거 다시 조회 실패 — 월간 수익률(보유 근거)과 가격 변화 · 하락 판정(비교 요약 없음)은 이전 조회값입니다(최신 아님).",
    );
    fireEvent.click(rowOf("분산 ETF"));
    expect(await screen.findByTestId("ec-hold-recent")).toHaveTextContent("(보유 근거 이전 조회값 · 저장 상태 확인 불가)");
    expect(screen.getByTestId("ec-hold-dates")).toHaveTextContent(
      "보유 근거(이전 조회값) 11/10 가격 = 저장 상태 확인 불가(비교 요약 없음)",
    );
  });

  it("보유 다시 조회 실패(이전 값 남음) = 보유 목록이 이전 조회값임을 알림", async () => {
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    expect(screen.queryByTestId("ec-hold-stale")).toBeNull();
    fetchEnrichedHoldings.mockRejectedValue(new Error("down"));
    fireEvent.click(screen.getByRole("button", { name: "다시 불러오기" }));
    expect(await screen.findByTestId("ec-hold-stale")).toHaveTextContent(
      "보유 다시 조회 실패 — 아래 보유 목록 · 비중 · 손익은 이전 조회값입니다(최신 아님).",
    );
    expect(rows()).toHaveLength(3);
  });

  it("보유 근거 안내 문구 조합(확인 중 · 정상은 안내 없음 · 행이 없으면 '보인다'고 말하지 않음)", () => {
    expect(evidenceNotice("ok", "ok", 0, true)).toBeNull();
    expect(evidenceNotice("loading", "none", 0, true)).toBeNull();
    expect(evidenceNotice("error", "ok", 2, true)).toBe(
      "보유 근거 조회 실패 — 월간 수익률(보유 근거)과 비교 요약에 가격 흐름이 없는 보유 2종목의 가격 변화 · 하락 판정을 보이지 못합니다.",
    );
    expect(evidenceNotice("stale", "ok", 1, true)).toBe(
      "보유 근거 다시 조회 실패 — 월간 수익률(보유 근거)과 비교 요약에 가격 흐름이 없는 보유 1종목의 가격 변화 · 하락 판정은 이전 조회값입니다(최신 아님).",
    );
    expect(evidenceNotice("error", "unread", 0, true)).toBe(
      "보유 근거 조회 실패 — 월간 수익률(보유 근거)과 가격 변화 · 하락 판정(비교 요약이 보유를 읽지 못함)을 보이지 못합니다.",
    );
    expect(evidenceNotice("error", "ok", 0, false)).toBe("보유 근거 조회 실패");
    expect(evidenceNotice("stale", "ok", 0, false)).toBeNull();
  });
});

describe("[설계자 RESULT 판정 §3] 요약 응답에 가격 흐름 칸이 없음(백엔드 재시작 전) = 하락 0 · 부족 26 으로 세지 않음", () => {
  // 첨부 화면(최근 하락 0 · 비교 자료 부족 26)의 재현 조건 — 새 화면 코드가 price_flow 칸 없는 옛 응답을 읽음.
  const noFlow = () => {
    const s = summary();
    return {
      ...s,
      holdings: {
        ...s.holdings,
        items: s.holdings.items.map((h) => {
          const { price_flow: _drop, ...rest } = h;
          void _drop;
          return rest;
        }),
      },
    };
  };
  const btn = (name: string) => screen.getByRole("button", { name });

  it("보유 근거가 있으면 그 값 + '저장 상태 확인 불가' · 부족은 구성 자료 · 날짜 근거로만", async () => {
    fetchEtfCompareSummary.mockResolvedValue(noFlow());
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    // 보유 근거: 분산 ETF 만 하락 · 반도체 전공정은 구성 자료 있음 + 날짜 정상 → 부족 아님.
    expect(btn("최근 하락 1")).toBeInTheDocument();
    expect(btn("비교 자료 부족 1")).toBeInTheDocument();
    expect(within(rowOf("분산 ETF")).getByText(/PC 20저장일 하락 10% 이상/)).toHaveTextContent(
      "PC 20저장일 하락 10% 이상 · 저장 상태 확인 불가",
    );
    expect(rowOf("반도체 전공정")).not.toHaveTextContent("비교 자료 부족");
    fireEvent.click(rowOf("반도체 전공정"));
    expect(await screen.findByTestId("ec-hold-kodex")).toHaveTextContent("비교 요약에 가격 흐름 없음 — 보이지 않음");
    expect(screen.getByTestId("ec-hold-recent")).toHaveTextContent("(보유 근거 · 저장 상태 확인 불가)");
    expect(screen.getByTestId("ec-hold-dates")).toHaveTextContent(
      "보유 근거 11/10 가격 = 저장 상태 확인 불가(비교 요약에 가격 흐름 없음)",
    );
  });

  it("보유 근거도 실패하면 하락 숫자 '—' · 부족은 가격 비교 근거 없음으로 · 안내에 종목 수", async () => {
    fetchEtfCompareSummary.mockResolvedValue(noFlow());
    fetchHoldingsMarketEvidence.mockRejectedValue(new Error("down"));
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    await screen.findByTestId("ec-ev-notice");
    expect(btn("최근 하락 —")).toBeInTheDocument();
    expect(btn("비교 자료 부족 2")).toBeInTheDocument();
    expect(screen.getByTestId("ec-hold-regime")).toHaveTextContent("하락 판정 수와 비중을 셀 수 없습니다");
    expect(screen.getByTestId("ec-hold-regime")).not.toHaveTextContent("0종목");
    expect(screen.getByTestId("ec-ev-notice")).toHaveTextContent(
      "보유 근거 조회 실패 — 월간 수익률(보유 근거)과 비교 요약에 가격 흐름이 없는 보유 3종목의 가격 변화 · 하락 판정을 보이지 못합니다.",
    );
  });
});

describe("[검증자 F6] 하락 숫자는 실제로 판정한(judgeable) 보유만 — 판정 못 함은 '0종목'이 아님", () => {
  const btn = (name: string) => screen.getByRole("button", { name });
  const regime = () => screen.getByTestId("ec-hold-regime");
  const UNJ = { judgeable: false, state: null, label: null, return_20d_pct_1dp: null, unjudged_reason: "insufficient_history" };
  const unjudgedEv = (t: string) => ({
    ...ev(t, {}),
    short_term_momentum: {
      status: "unavailable",
      return_5d_pct: null,
      return_10d_pct: null,
      return_20d_pct: null,
      excess_vs_kodex200_5d_pctp: null,
      excess_vs_kodex200_10d_pctp: null,
      excess_vs_kodex200_20d_pctp: null,
    },
    price_dates: { end_date: "2026-11-10", start_date_5d: null, start_date_20d: null, comparison: "unavailable" },
    decline_band: UNJ,
  });
  const summaryWith = (f: (h: CompareSummaryOk["holdings"]["items"][number]) => object) => {
    const s = summary();
    return { ...s, holdings: { ...s.holdings, items: s.holdings.items.map((h) => ({ ...h, ...f(h) })) } };
  };
  const expectUncountable = () => {
    expect(btn("최근 하락 —")).toBeInTheDocument();
    expect(regime()).toHaveTextContent("하락 판정 수와 비중을 셀 수 없습니다");
    expect(regime()).not.toHaveTextContent("0종목");
  };

  it("요약 가격 흐름 칸 없음 + 보유 근거 3종목 모두 판정 못 함(이력 부족) = '—'", async () => {
    fetchEtfCompareSummary.mockResolvedValue(
      summaryWith((h) => {
        const { price_flow: _d, ...rest } = h;
        void _d;
        return { ...rest, price_flow: undefined };
      }),
    );
    fetchHoldingsMarketEvidence.mockResolvedValue({
      ...evidence(),
      holdings: [unjudgedEv("B00001"), unjudgedEv("H00002"), unjudgedEv("005930")],
    });
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    expectUncountable();
  });

  it("요약 가격 흐름 3종목 모두 판정 못 함 + 보유 근거 실패 = '—'", async () => {
    fetchEtfCompareSummary.mockResolvedValue(
      summaryWith((h) => ({
        price_flow: flow({ status: "unavailable", comparison: "unavailable", return_20d_pct: null, decline_band: UNJ }),
        ticker: h.ticker,
      })),
    );
    fetchHoldingsMarketEvidence.mockRejectedValue(new Error("down"));
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    await screen.findByTestId("ec-ev-notice");
    expectUncountable();
  });

  it("요약 price_flow=null(저장 가격 없음) 3종목 + 보유 근거 실패 = '—' · 상세는 저장 가격 없음", async () => {
    fetchEtfCompareSummary.mockResolvedValue(summary({ B00001: null, H00002: null, "005930": null }));
    fetchHoldingsMarketEvidence.mockRejectedValue(new Error("down"));
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    await screen.findByTestId("ec-ev-notice");
    expectUncountable();
    fireEvent.click(rowOf("반도체 전공정"));
    expect(await screen.findByTestId("ec-hold-recent")).toHaveTextContent("가격 변화 없음(저장 가격 없음)");
  });

  it("대조군 — 3종목 모두 판정했고 구간 밖 = '최근 하락 0' · '기존 하락 판정 0종목'(안내 없음)", async () => {
    fetchEtfCompareSummary.mockResolvedValue(
      summaryWith(() => ({ price_flow: flow({ decline_band: NONE }) })),
    );
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    expect(btn("최근 하락 0")).toBeInTheDocument();
    expect(regime()).toHaveTextContent("기존 하락 판정 0종목");
    expect(screen.queryByTestId("ec-hold-unjudged")).toBeNull();
  });

  it("일부만 판정 못 함 = 판정한 범위의 숫자 + 판정 못 한 보유 수를 따로", async () => {
    fetchEtfCompareSummary.mockResolvedValue(
      summary({
        "005930": {
          comparison: "date_mismatch",
          decline_band: { ...UNJ, unjudged_reason: "date_mismatch" },
        },
      }),
    );
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    expect(btn("최근 하락 1")).toBeInTheDocument();
    expect(regime()).toHaveTextContent("기존 하락 판정 1종목 · 보유 비중 0.70% · 하락 판정을 못 한 보유 1종목은 세지 않음");
    expect(screen.getByTestId("ec-hold-unjudged")).toHaveTextContent("하락 판정을 못 한 보유 1종목");
  });
});

describe("[독립 검토 · F5 옆칸] '모름'을 '아님'으로 세지 않음 · 요약이 보유를 못 읽은 경우", () => {
  const btn = (name: string) => screen.getByRole("button", { name });

  it("요약 없음 + 보유 근거에 없는 보유 = 판정 자료 없음 안내 · 비교 자료 부족 · 약세 묶음 접점은 '—'", async () => {
    fetchEtfCompareSummary.mockRejectedValue(new Error("down"));
    fetchHoldingsMarketEvidence.mockResolvedValue({ ...evidence(), holdings: [ev("H00002", { decline: true }), ev("005930", {})] });
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    await screen.findByText(/비교 자료 조회 실패/);
    expect(btn("최근 하락 1")).toBeInTheDocument();
    expect(screen.getByTestId("ec-hold-unjudged")).toHaveTextContent(
      "하락 판정을 못 한 보유 1종목 — 가격 자료 없음 · 이력 부족 · 기준일 다름 등으로 판정하지 않아 최근 하락 숫자에 넣지 않았습니다.",
    );
    expect(btn("비교 자료 부족 —")).toBeInTheDocument();
    expect(btn("약세 묶음 접점 —")).toBeInTheDocument();
    expect(screen.getByTestId("ec-hold-filter-note")).toHaveTextContent(
      "비교 요약 없음 — 약세 묶음 접점 · 비교 자료 부족은 셀 수 없어 '—'(가격 비교 날짜 문제가 확인된 행만 배지)",
    );
  });

  it("보유 조회 실패 + 보유 근거 실패 = 행이 없으니 '요약 값으로 보입니다'라고 하지 않음", async () => {
    fetchEnrichedHoldings.mockRejectedValue(new Error("down"));
    fetchHoldingsMarketEvidence.mockRejectedValue(new Error("down"));
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findByText("보유 확인 실패");
    expect(await screen.findByTestId("ec-ev-notice")).toHaveTextContent(/^보유 근거 조회 실패$/);
    expect(screen.queryAllByTestId("ec-hold-row")).toHaveLength(0);
  });

  it("요약이 보유를 못 읽음(holdings.status error) = 접점 · 부족 '—' · 개별 주식을 부족으로 넣지 않음 · 이유를 그대로", async () => {
    const s = summary();
    fetchEtfCompareSummary.mockResolvedValue({ ...s, holdings: { status: "error", items: [] } });
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    expect(btn("약세 묶음 접점 —")).toBeInTheDocument();
    expect(btn("비교 자료 부족 —")).toBeInTheDocument();
    expect(rowOf("개별 주식 A")).not.toHaveTextContent("비교 자료 부족");
    // 하락 판정은 보유 근거 값 + 저장 상태 확인 불가(요약 연결 없음).
    expect(within(rowOf("분산 ETF")).getByText(/PC 20저장일 하락 10% 이상/)).toHaveTextContent(
      "PC 20저장일 하락 10% 이상 · 저장 상태 확인 불가",
    );
    fireEvent.click(rowOf("개별 주식 A"));
    expect(await screen.findByTestId("ec-hold-candidate")).toHaveTextContent(
      "후보 비교 자료 없음(비교 요약이 보유를 읽지 못함)",
    );
    expect(screen.getByTestId("ec-hold-kodex")).toHaveTextContent("비교 요약이 보유를 읽지 못함 — 보이지 않음");
  });

  it("요약이 보유를 못 읽음 + 보유 근거 실패 = 하락 숫자도 '—'(모두 '아님'으로 세지 않음)", async () => {
    const s = summary();
    fetchEtfCompareSummary.mockResolvedValue({ ...s, holdings: { status: "error", items: [] } });
    fetchHoldingsMarketEvidence.mockRejectedValue(new Error("down"));
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    await screen.findByTestId("ec-ev-notice");
    expect(btn("최근 하락 —")).toBeInTheDocument();
    expect(screen.getByTestId("ec-ev-notice")).toHaveTextContent(
      "보유 근거 조회 실패 — 월간 수익률(보유 근거)과 가격 변화 · 하락 판정(비교 요약이 보유를 읽지 못함)을 보이지 못합니다.",
    );
  });
});

describe("[검증자 r1 F2] 하락 보유 수 · 비중 · 거르기 숫자는 확인한 범위만", () => {
  const regime = () => screen.getByTestId("ec-hold-regime");

  it("하락 보유 비중이 모두 미확인이면 '확인 불가' · 일부만이면 확인 범위를 적는다", async () => {
    const h = holdings();
    h.items = h.items.map((i) => (i.ticker === "B00001" || i.ticker === "005930" ? { ...i, market_weight_pct: null } : i));
    fetchEnrichedHoldings.mockResolvedValue(h);
    const { unmount } = render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    expect(regime()).toHaveTextContent("기존 하락 판정 2종목 · 보유 비중 확인 불가");
    expect(regime()).not.toHaveTextContent("0.00%");
    unmount();
    __resetQueryCache();
    const h2 = holdings();
    h2.items = h2.items.map((i) => (i.ticker === "005930" ? { ...i, market_weight_pct: null } : i));
    fetchEnrichedHoldings.mockResolvedValue(h2);
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    expect(regime()).toHaveTextContent("기존 하락 판정 2종목 · 보유 비중 0.70%(2종목 중 1종목만 확인)");
  });

  it("다계좌 중 일부 계좌 비중만 있으면 그 종목은 미확인으로 센다", () => {
    const row = { ticker: "A", name: "a", evalAmount: 1, evalOk: 1, pnlAmount: 1, pnlOk: 1, pnlRate: null, currentPrice: 1, weight: 30, weightOk: 1, count: 2 };
    expect(declineWeightLine([row])).toBe("기존 하락 판정 1종목 · 보유 비중 확인 불가");
    expect(declineWeightLine([])).toBe("기존 하락 판정 0종목");
    expect(declineWeightLine([], 2)).toBe("기존 하락 판정 0종목 · 하락 판정을 못 한 보유 2종목은 세지 않음");
    expect(declineWeightLine(null)).toBe("보유 · 가격 흐름 자료를 읽지 못해 하락 판정 수와 비중을 셀 수 없습니다");
  });

  it("보유 최초 조회 실패 = 0종목 · 0% 가 아니라 '셀 수 없음'", async () => {
    fetchEnrichedHoldings.mockRejectedValue(new Error("down"));
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findByText("보유 확인 실패");
    expect(regime()).toHaveTextContent("보유 · 가격 흐름 자료를 읽지 못해 하락 판정 수와 비중을 셀 수 없습니다");
    expect(regime()).not.toHaveTextContent("0종목");
  });

  it("보유 근거 최초 조회 실패여도 요약 같은 응답으로 셀 수 있는 숫자(하락 · 접점 · 부족)는 그대로", async () => {
    fetchHoldingsMarketEvidence.mockRejectedValue(new Error("down"));
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    expect(regime()).toHaveTextContent("기존 하락 판정 2종목 · 보유 비중 20.70%");
    expect(screen.getByRole("button", { name: "최근 하락 2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "약세 묶음 접점 2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "비교 자료 부족 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "전체 3" })).toBeInTheDocument();
  });

  it("요약도 보유 근거도 없으면 '최근 하락' · '비교 자료 부족' · '약세 묶음 접점' 모두 '—'", async () => {
    fetchHoldingsMarketEvidence.mockRejectedValue(new Error("down"));
    fetchEtfCompareSummary.mockRejectedValue(new Error("down"));
    render(<WorkbenchHoldingsView onNavigate={nav} />);
    await screen.findAllByTestId("ec-hold-row");
    expect(screen.getByRole("button", { name: "최근 하락 —" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "비교 자료 부족 —" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "약세 묶음 접점 —" })).toBeInTheDocument();
    expect(link({ ticker: "x" }).top_rank).toBeUndefined();
  });
});
