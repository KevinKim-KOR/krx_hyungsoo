// POC3-05 보유 ETF 확인 근거 — 컴포넌트 계약 test.
// - 금지어(위험/고위험/손절/매도/청산/BUY/SELL) 비노출.
// - 급락(falling) 관련 열·빠른보기 없음(이번 Step 제외).
// - 읽기 전용(값 수정·저장 버튼 없음). N+1 없음(목록 조회 3종 · 종목 인자 조회는 상세를 열 때만).
// POC6-33 — 주간 순위 요약(GET /market/etf-compare/summary) · 한 ETF 구성 요약(GET /market/constituents/summary)도
// mock 한다(실제 요청이 나가지 않게). 고정 자료의 종목 이름 · 코드는 합성값.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, fireEvent, within } from "@testing-library/react";
import { __resetQueryCache, markQueryFailed } from "@/lib/api/queryCache";

const fetchEnrichedHoldings = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
const fetchBenchmarkSeries = vi.fn();
const fetchPriceSeries = vi.fn();
const fetchConstituentsSummary = vi.fn();
const fetchEtfCompareSummary = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
    fetchHoldingsMarketEvidence: (...a: unknown[]) => fetchHoldingsMarketEvidence(...a),
    fetchBenchmarkSeries: (...a: unknown[]) => fetchBenchmarkSeries(...a),
    fetchPriceSeries: (...a: unknown[]) => fetchPriceSeries(...a),
    fetchConstituentsSummary: (...a: unknown[]) => fetchConstituentsSummary(...a),
  };
});
vi.mock("@/lib/api/etfCompare", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return { ...actual, fetchEtfCompareSummary: (...a: unknown[]) => fetchEtfCompareSummary(...a) };
});

import HoldingsRiskEvidenceSection from "./HoldingsRiskEvidenceSection";
import type { ConstituentsSummaryResponse, HoldingsMarketEvidenceResponse } from "@/lib/api";
import { flow, link, summaryOk } from "@/lib/etfCompareTestFixtures";
import { WEEKLY_CHECK_CONDITION } from "./holdings_risk_evidence/helpers";
import { etfCompareKey } from "@/lib/api/etfCompare";

function consSummary(ticker: string, over: Partial<ConstituentsSummaryResponse> = {}): ConstituentsSummaryResponse {
  return {
    status: "ok", message: null, ticker, name: null, state: "full", state_label: "전체 확인",
    asof: "2026-10-07", stored_rows: 12,
    top_stocks: [
      { name: "구성 1", weight_pct: 9.87 },
      { name: "구성 2", weight_pct: 5 },
    ],
    ...over,
  };
}

// 모든 describe 앞 — 주간 순위 · 구성 요약 기본 응답(보유 연결 없음 · 구성 전체 확인).
beforeEach(() => {
  fetchEtfCompareSummary.mockReset();
  fetchConstituentsSummary.mockReset();
  fetchEtfCompareSummary.mockResolvedValue(summaryOk({ holdings: { status: "ok", items: [] } }));
  fetchConstituentsSummary.mockImplementation((t: string) => Promise.resolve(consSummary(t)));
});

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

  it("제목·표·최근 5 · 20저장일/같은 기간 KODEX 200 대비 열이 렌더된다(POC6-33 E2 단위)", async () => {
    await renderSection();
    expect(screen.getByRole("heading", { name: "보유 ETF 확인 근거" })).toBeTruthy();
    expect(screen.getByText("KODEX200")).toBeTruthy();
    expect(screen.getByText("최근 5저장일")).toBeTruthy();
    expect(screen.getByText("20저장일")).toBeTruthy();
    expect(screen.getByText("같은 기간 KODEX 200 대비(%p)")).toBeTruthy();
    expect(screen.getByText("손익률(계좌 합산)")).toBeTruthy();
    expect(screen.getByText("평가 비중(계좌 합산)")).toBeTruthy();
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
    // 빠른 보기는 전체 / 하락 구간 / 자료 확인 필요 세 개(POC5-13 '하락 구간' 추가 · 급락 보기 없음).
    expect(screen.getByRole("button", { name: "전체" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /하락 구간/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /자료 확인 필요/ })).toBeTruthy();
    expect(document.querySelectorAll(".hre-quickview button")).toHaveLength(3);
  });

  it("N+1 없음: 조회는 목록 endpoint 3종(보유 · 근거 · 주간 순위 요약)뿐이고 ticker 인자 호출이 없다", async () => {
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
    // POC6-33 E5 — 주간 순위 요약은 화면 진입 때 한 번 · 「주간 ETF 점검」과 같은 인자(1개월 · 제외 4종).
    expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(1);
    expect(fetchEtfCompareSummary).toHaveBeenCalledWith(WEEKLY_CHECK_CONDITION);
    expect(WEEKLY_CHECK_CONDITION).toEqual({
      basis: "one_month",
      filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
    });
    // ticker별 가격 시계열 · 구성 요약은 선택 전에는 호출되지 않는다(lazy).
    expect(fetchPriceSeries).not.toHaveBeenCalled();
    expect(fetchConstituentsSummary).not.toHaveBeenCalled();
  });

  it("읽기 전용: 값 수정·저장 버튼이 없다", async () => {
    await renderSection();
    // POC6-33 — 정렬 버튼 '5저장일 변화' · '20저장일 변화'의 '저장일'(단위)은 저장 버튼이 아니다.
    expect(screen.queryByRole("button", { name: /저장(?!일)/ })).toBeNull();
    expect(screen.getAllByRole("button", { name: /저장일 변화$/ })).toHaveLength(2);
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("§6.4 · POC6-33 E10: NAV 이전 목록 재사용을 정상과 구분 · 재저장일 · 사전 밖 출처 · 받은 안내 원문은 [자세히] 안에만", async () => {
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
    // partial 상태가 정상처럼 숨겨지지 않는다(수집 상태 '이전 목록 재사용' · 날짜 = 재저장일).
    const nav = screen.getByTestId("hre-nav");
    const cells = Object.fromEntries(
      Array.from(nav.querySelectorAll(".hre-nav-cell")).map((c) => [
        c.getAttribute("data-nav-label"),
        c.querySelector(".v")?.textContent,
      ]),
    );
    expect(cells).toEqual({
      시장가: "1,100", NAV: "1,050", 괴리율: "-", 기준일: "재저장일 2026-07-24", 출처: "기타 출처", "수집 상태": "이전 목록 재사용",
    });
    // message 는 [자세히] 안에만(사전 밖 출처 원문도 같이).
    const raw = within(nav).getByTestId("hre-nav-raw");
    expect(raw.tagName).toBe("DETAILS");
    expect(raw.textContent).toContain("받은 안내 원문: 괴리율 계산 불가");
    expect(raw.textContent).toContain("출처 원문: naver");
    expect(screen.getByText(/괴리율 계산 불가/).closest("details")).toBe(raw);
    expect(document.body.textContent ?? "").not.toContain("부분 자료");
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

// ── POC5-UI-02 — 사용자 선택 정렬(네 가지 · 설계 §11) · 자료 확인 안내 · 전체 ETF NAV 이동 ──
// 종목 3개: A(평가 5000 · 투자 4000 → 손익률 +25% · 비중 50%) · B(2000 · 2500 → -20% · 20%) ·
// C(3000 · 3000 → 0% · 30% · 5일 · 20일 값 없음 = 자료 확인 필요). 응답 순서 = A, B, C.
type EnrichedRowOver = { price_missing?: boolean; calc_missing?: boolean };
function enrichedRow(
  ticker: string,
  name: string,
  evalAmt: number,
  invested: number,
  over: EnrichedRowOver = {},
) {
  return {
    ticker, name, quantity: 1, avg_buy_price: invested, invested_amount: invested,
    current_price: evalAmt, price_asof: "2026-10-08", price_source: "naver",
    eval_amount: evalAmt, pnl_amount: evalAmt - invested,
    pnl_rate_pct: ((evalAmt - invested) / invested) * 100, buy_weight_pct: null,
    market_weight_pct: null, price_missing: false, calc_missing: false,
    ...over,
  };
}
function enrichedThree() {
  return {
    items: [
      enrichedRow("A1", "에이", 5000, 4000),
      enrichedRow("B1", "비", 2000, 2500),
      enrichedRow("C1", "씨", 3000, 3000),
    ],
  };
}
function evItemOf(
  ticker: string,
  name: string,
  r5: number | null,
  r20: number | null,
  ex: number | null,
  notes: string[] = [],
) {
  const base = evidenceResult();
  return {
    ...base.holdings[0],
    ticker,
    name,
    short_term_momentum: {
      ...base.holdings[0].short_term_momentum,
      status: (r5 === null ? "partial" : "ok") as "partial" | "ok",
      return_5d_pct: r5,
      return_20d_pct: r20,
      excess_vs_kodex200_20d_pctp: ex,
    },
    evidence_notes: notes,
  };
}
function evidenceThree(
  items = [
    evItemOf("A1", "에이", -1, -3, -1.5),
    evItemOf("B1", "비", -3, -1, -0.5),
    evItemOf("C1", "씨", null, null, -2),
  ],
): HoldingsMarketEvidenceResponse {
  return { ...evidenceResult(), holdings: items };
}
function rowOrder(): string[] {
  const list = screen.getByTestId("hre-evidence-list");
  return Array.from(list.querySelectorAll('[role="button"]')).map(
    (el) => (el.getAttribute("aria-label") ?? "").replace(" 상세 보기", ""),
  );
}
function guidanceItems(): string[] {
  const box = screen.queryByTestId("hre-guidance");
  if (!box) return [];
  return Array.from(box.querySelectorAll(".hre-guidance-item")).map((el) => el.textContent ?? "");
}
async function renderAndSelect(name: string) {
  render(<HoldingsRiskEvidenceSection />);
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: `${name} 상세 보기` }));
    await Promise.resolve();
  });
}
const NO_REASON = "자료 확인이 필요하지만 상세 사유 정보가 제공되지 않습니다.";

describe("확인 근거 — 사용자 선택 정렬 · 자료 확인 안내 · 전체 ETF NAV 이동 (POC5-UI-02)", () => {
  beforeEach(() => {
    __resetQueryCache();
    fetchEnrichedHoldings.mockReset();
    fetchHoldingsMarketEvidence.mockReset();
    fetchEnrichedHoldings.mockResolvedValue(enrichedThree());
    fetchHoldingsMarketEvidence.mockResolvedValue(evidenceThree());
    fetchPriceSeries.mockResolvedValue({ availability: "NO_DATA", points: [] });
  });

  it("네 정렬 · 기본 5저장일 변화 · 값 없는 행은 맨 뒤 · KODEX 200 대비 값은 계속 보인다 · 다시 조회하지 않는다", async () => {
    await renderSection();
    const group = screen.getByRole("group", { name: "확인 근거 정렬 기준" });
    const labels = Array.from(group.querySelectorAll("button")).map((b) => b.textContent);
    expect(labels).toEqual(["평가 비중", "손익률", "5저장일 변화", "20저장일 변화"]);
    expect(screen.queryByRole("button", { name: "KODEX200 대비" })).toBeNull();
    expect(screen.getByRole("button", { name: "5저장일 변화" }).getAttribute("aria-pressed")).toBe("true");
    // POC6-33 E2 — 저장일 변화 정렬일 때만 '이 목록 정렬 = 저장일 변화 기준' 힌트.
    expect(document.querySelector(".holdings-sortbar-hint")?.textContent).toBe(
      "작은 값부터 · 값이 없는 종목은 맨 뒤 · 이 목록 정렬 = 저장일 변화 기준(「주간 ETF 점검」 순위와 다름)",
    );
    expect(rowOrder()).toEqual(["비", "에이", "씨"]); // 5일 -3 · -1 · 없음

    const cases: Array<[string, string[]]> = [
      ["평가 비중", ["에이", "씨", "비"]], // 50 · 30 · 20 (큰 값부터)
      ["손익률", ["비", "씨", "에이"]], // -20 · 0 · +25
      ["20저장일 변화", ["에이", "비", "씨"]], // -3 · -1 · 없음
      ["5저장일 변화", ["비", "에이", "씨"]],
    ];
    for (const [label, order] of cases) {
      fireEvent.click(screen.getByRole("button", { name: label }));
      expect(screen.getByRole("button", { name: label }).getAttribute("aria-pressed")).toBe("true");
      expect(rowOrder()).toEqual(order);
    }
    // 상대 성과 값 표시는 유지 — 행마다 '같은 기간 KODEX 200 대비(%p)' 칸과 그 값.
    const list = screen.getByTestId("hre-evidence-list");
    expect(screen.getAllByText("같은 기간 KODEX 200 대비(%p)").length).toBeGreaterThanOrEqual(3);
    for (const v of ["-1.50%p", "-0.50%p", "-2.00%p"]) {
      expect(list.textContent ?? "").toContain(v);
    }
    expect(fetchEnrichedHoldings).toHaveBeenCalledTimes(1);
    expect(fetchHoldingsMarketEvidence).toHaveBeenCalledTimes(1);
    // 방향 안내 — 평가 비중만 큰 값부터.
    fireEvent.click(screen.getByRole("button", { name: "평가 비중" }));
    expect(document.querySelector(".holdings-sortbar-hint")?.textContent).toBe(
      "큰 값부터 · 값이 없는 종목은 맨 뒤",
    );
    fireEvent.click(screen.getByRole("button", { name: "손익률" }));
    expect(document.querySelector(".holdings-sortbar-hint")?.textContent).toBe(
      "작은 값부터 · 값이 없는 종목은 맨 뒤",
    );
    // 정렬 이름에 위험 · 순위 표현이 없다.
    expect(group.textContent ?? "").not.toMatch(/위험|순위/);
  });

  it("빠른 보기 '자료 확인 필요'와 함께 동작한다(행을 빼지 않고 걸러진 행만 정렬)", async () => {
    await renderSection();
    fireEvent.click(screen.getByRole("button", { name: /자료 확인 필요 \(1\)/ }));
    expect(rowOrder()).toEqual(["씨"]);
    fireEvent.click(screen.getByRole("button", { name: "평가 비중" }));
    expect(rowOrder()).toEqual(["씨"]);
    fireEvent.click(screen.getByRole("button", { name: "전체" }));
    expect(rowOrder()).toEqual(["에이", "씨", "비"]);
  });

  it("선택 종목의 evidence_notes 를 그 종목 상세에만 보인다(다른 종목 사유 섞임 없음 · 옛 후보 문구는 거름)", async () => {
    fetchHoldingsMarketEvidence.mockResolvedValue(
      evidenceThree([
        evItemOf("A1", "에이", -1, -3, -1.5, ["에이 사유 문구"]),
        evItemOf("B1", "비", -3, -1, -0.5, ["비 사유 문구"]),
        evItemOf("C1", "씨", null, null, -2, ["현재 Market Discovery 후보에 포함되어 있지 않습니다."]),
      ]),
    );
    await renderAndSelect("에이");
    expect(guidanceItems()).toEqual(["에이 사유 문구"]);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "씨 상세 보기" }));
      await Promise.resolve();
    });
    // 씨 = 자료 확인 필요(5 · 20저장일 없음)인데 옛 후보 문구뿐 → 그 문구는 거르고(POC6-33 E6) 사유 미제공 문구만.
    expect(guidanceItems()).toEqual([NO_REASON]);
    expect(document.body.textContent ?? "").not.toContain("Market Discovery");
    expect(screen.getByTestId("hre-guidance").textContent ?? "").not.toContain("에이 사유 문구");
    expect(screen.getByTestId("hre-guidance").textContent ?? "").not.toContain("비 사유 문구");
  });

  it("시세 · 계산 미확인을 그 종목 상세에 보인다", async () => {
    fetchEnrichedHoldings.mockResolvedValue({
      items: [
        enrichedRow("A1", "에이", 5000, 4000, { price_missing: true }),
        enrichedRow("B1", "비", 2000, 2500, { calc_missing: true }),
        enrichedRow("C1", "씨", 3000, 3000),
      ],
    });
    await renderAndSelect("에이");
    expect(guidanceItems()).toEqual(["보유 시세를 확인할 수 없습니다."]);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "비 상세 보기" }));
      await Promise.resolve();
    });
    expect(guidanceItems()).toEqual(["보유 평가 계산값을 확인할 수 없습니다."]);
  });

  it("같은 종목의 계좌별 흐름 값이 다르면 그 사유를 보인다(같은 메모는 한 번)", async () => {
    fetchEnrichedHoldings.mockResolvedValue({
      items: [
        enrichedRow("A1", "에이", 2500, 2000),
        enrichedRow("A1", "에이", 2500, 2000),
        enrichedRow("B1", "비", 2000, 2500),
      ],
    });
    fetchHoldingsMarketEvidence.mockResolvedValue(
      evidenceThree([
        evItemOf("A1", "에이", -1, -3, -1.5, ["공통 메모"]),
        evItemOf("A1", "에이", -2, -3, -1.5, ["공통 메모"]),
        evItemOf("B1", "비", -3, -1, -0.5),
      ]),
    );
    await renderAndSelect("에이");
    expect(guidanceItems()).toEqual([
      "같은 종목의 계좌별 단기 흐름 값(상태 · 5저장일 · 20저장일 · KODEX 200 대비)이 서로 다릅니다.",
      "공통 메모",
    ]);
  });

  it("자료 확인 필요인데 사유가 없으면 '상세 사유 정보가 제공되지 않습니다' · 정상 종목은 안내 칸이 없다", async () => {
    await renderAndSelect("씨"); // 5 · 20저장일 없음 · evidence_notes 없음
    expect(guidanceItems()).toEqual([NO_REASON]);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "에이 상세 보기" }));
      await Promise.resolve();
    });
    expect(screen.queryByTestId("hre-guidance")).toBeNull();
  });

  it("시장 근거 항목이 없는 종목도 사유 미제공 문구로 안내한다", async () => {
    fetchHoldingsMarketEvidence.mockResolvedValue(
      evidenceThree([evItemOf("A1", "에이", -1, -3, -1.5), evItemOf("B1", "비", -3, -1, -0.5)]),
    );
    await renderAndSelect("씨");
    expect(guidanceItems()).toEqual([NO_REASON]);
  });

  it("정렬을 바꿔도 선택한 종목 상세와 자료 확인 안내는 유지된다 · 다시 조회하지 않는다", async () => {
    await renderAndSelect("씨");
    // POC6-33 E3 — 상세 제목 = 이름 · 코드.
    expect(screen.getByRole("heading", { name: "씨 · C1" })).toBeTruthy();
    expect(guidanceItems()).toEqual([NO_REASON]);
    for (const label of ["평가 비중", "손익률", "20저장일 변화", "5저장일 변화"]) {
      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: label }));
        await Promise.resolve();
      });
      expect(screen.getByRole("heading", { name: "씨 · C1" })).toBeTruthy();
      expect(guidanceItems()).toEqual([NO_REASON]);
    }
    expect(fetchEnrichedHoldings).toHaveBeenCalledTimes(1);
    expect(fetchHoldingsMarketEvidence).toHaveBeenCalledTimes(1);
  });

  it("판정 Q54 — 상세에 [전체 ETF NAV·괴리율 보기] 이동 버튼이 없다(전체 표 = 「데이터 상태」) · NAV 묶음은 있다", async () => {
    await renderAndSelect("에이");
    expect(screen.getByTestId("hre-nav")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /전체 ETF NAV/ })).toBeNull();
    expect(document.body.textContent ?? "").not.toContain("전체 ETF NAV·괴리율 보기");
    expect(screen.queryByText(/원인 확인/)).toBeNull();
    expect(fetchEnrichedHoldings).toHaveBeenCalledTimes(1);
    expect(fetchHoldingsMarketEvidence).toHaveBeenCalledTimes(1);
  });
});

// ── POC5-09 — 가격 흐름 기준일 · 저장 거래량 (판정 §9-4 · 설계 §3 · §5) ─────────────
const REF = "2026-10-08";
function volumeOf(ticker: string, asof: string, volume: number, avg: number) {
  return {
    ticker,
    status: "ok" as const,
    asof_date: asof,
    source: "FinanceDataReader",
    volume,
    window_size: 20,
    window_start_date: "2026-09-07",
    window_end_date: "2026-10-07",
    window_date_count: 20,
    valid_count: 20,
    avg_prev20: avg,
    avg_status: "ok" as const,
    ratio: volume / avg,
    ratio_status: "ok" as const,
  };
}
function datesOf(end: string, comparison: "ok" | "date_mismatch") {
  return comparison === "ok"
    ? { end_date: end, start_date_5d: "2026-09-30", start_date_20d: "2026-09-07", comparison }
    : { end_date: end, start_date_5d: "2026-08-05", start_date_20d: "2026-07-14", comparison };
}
function evidenceWithBasis(): HoldingsMarketEvidenceResponse {
  const a = evItemOf("A1", "에이", -1, -3, -1.5, ["에이 메모"]);
  const b = evItemOf("B1", "비", -3, -1, -0.5);
  // C1 = 기준일이 달라 backend 응답 사본이 값을 비운 종목(status unavailable).
  const c = evItemOf("C1", "씨", null, null, null, ["씨 메모"]);
  c.short_term_momentum = { ...c.short_term_momentum, status: "unavailable" as "partial" };
  return {
    ...evidenceThree([
      { ...a, price_dates: datesOf(REF, "ok"), stored_volume: volumeOf("A1", REF, 1500000, 1000000) },
      { ...b, price_dates: datesOf(REF, "ok") },
      {
        ...c,
        price_dates: datesOf("2026-08-12", "date_mismatch"),
        stored_volume: volumeOf("C1", "2026-08-12", 4204301, 6174143.2),
      },
    ]),
    price_basis: {
      reference_date: REF,
      reference_ticker: "069500",
      kodex200_start_date_5d: "2026-09-30",
      kodex200_start_date_20d: "2026-09-07",
      date_mismatch: [{ ticker: "C1", name: "씨", end_date: "2026-08-12" }],
    },
  };
}
function rowEl(name: string): HTMLElement {
  return screen.getByRole("button", { name: `${name} 상세 보기` });
}

describe("확인 근거 — 가격 흐름 기준일 · 저장 거래량 (POC5-09)", () => {
  beforeEach(() => {
    __resetQueryCache();
    fetchEnrichedHoldings.mockReset();
    fetchHoldingsMarketEvidence.mockReset();
    fetchEnrichedHoldings.mockResolvedValue(enrichedThree());
    fetchHoldingsMarketEvidence.mockResolvedValue(evidenceWithBasis());
    fetchPriceSeries.mockResolvedValue({ availability: "NO_DATA", points: [] });
  });

  it("목록 위 기준 줄 · 기준일이 다른 행은 세 칸 '—' + 자료 확인 필요 · 정렬 맨 뒤", async () => {
    await renderSection();
    expect(screen.getByTestId("hre-price-basis").textContent).toBe(
      "가격 흐름(최근 5 · 20저장일 · KODEX 200 대비) 기준 · KODEX 200 20저장일 비교 기간 2026-09-07 ~ 2026-10-08. 마지막 저장일이 가격 기준일과 다른 1종목은 현재 비교에서 뺐습니다: 씨(마지막 저장일 2026-08-12).",
    );
    const c = rowEl("씨");
    expect(Array.from(c.querySelectorAll(".wb-hmetrics .v")).map((e) => e.textContent)).toEqual([
      "—",
      "—",
      "—",
    ]);
    expect(within(c).getByText("자료 확인 필요")).toBeTruthy();
    // 정상 행은 원래 값 그대로.
    expect(rowEl("에이").textContent).toContain("-1.00%");
    expect(rowOrder()).toEqual(["비", "에이", "씨"]);
    fireEvent.click(screen.getByRole("button", { name: "20저장일 변화" }));
    expect(rowOrder()).toEqual(["에이", "비", "씨"]);
  });

  // POC5-19 — 값 · 문구는 그대로이고 위치만 바뀌었다: 거래량 값은 기본 '거래량' 묶음, 가격 흐름 기준 · 출처 줄은
  // 상세 제목 줄 [세부 흐름 보기] 창 아래쪽(차트 읽기 개정 2026-10-17 §2).
  const openFlows = () => fireEvent.click(screen.getByRole("button", { name: "세부 흐름 보기" }));
  const volValues = () =>
    Array.from(screen.getByTestId("evg-volume").querySelectorAll(".evg-grid .v")).map((e) => e.textContent);

  it("기준일이 다른 종목 상세: 실제 날짜 사유 · 가격 흐름 기준 · 과거 저장 거래량 · NAV 유지", async () => {
    await renderAndSelect("씨");
    expect(guidanceItems()).toEqual([
      "이 종목 마지막 저장일: 2026-08-12 / 가격 기준일: 2026-10-08 — 두 날짜가 달라 현재 비교에 사용하지 않습니다.",
      "씨 메모",
    ]);
    const price = screen.getByTestId("evg-price");
    expect(price.textContent).toContain("판정하지 않음");
    expect(price.querySelector(".evg-grid")).toBeNull(); // 기준일이 다르면 값 대신 사유
    expect(price.querySelector(".evg-foot")?.textContent).toBe("마지막 저장일 2026-08-12 · PC 저장 종가");
    const vol = screen.getByTestId("evg-volume");
    expect(vol.textContent).toContain("과거 저장 자료 · 가격 기준일은 2026-10-08");
    expect(vol.textContent).not.toContain("PC 비교 기준일");
    // POC6-33 E4 — 거래량 묶음 첫 칸 = 평균 대비.
    expect(volValues()).toEqual(["0.68배", "4,204,301주", "6,174,143.20주"]);
    expect(vol.querySelector(".evg-foot")?.textContent).toBe("마지막 저장일 2026-08-12");
    openFlows();
    expect(screen.getByTestId("detail-flows-body").textContent).toContain(
      "마지막 저장일 2026-08-12 · 5저장일 2026-08-05 ~ 2026-08-12 · 20저장일 2026-07-14 ~ 2026-08-12",
    );
    // POC6-33 E4 — 창 첫 줄(세 근거 기준일 + 값)은 뺐다 · '과거 저장 자료' 안내는 펼친 상세의 거래량 묶음에 남음(위).
    expect(screen.queryByTestId("detail-flows-strip")).toBeNull();
    expect(screen.getByText("순자산가치(NAV) · 괴리율")).toBeTruthy();
  });

  it("정상 종목 상세: 날짜 사유 없음 · 거래량 값 · 과거 표시 없음 · 세부에 기준 줄 · 출처 줄", async () => {
    await renderAndSelect("에이");
    expect(guidanceItems()).toEqual(["에이 메모"]);
    expect(volValues()).toEqual(["1.50배", "1,500,000주", "1,000,000.00주"]);
    expect(screen.getByTestId("evg-volume").textContent).not.toContain("과거 저장 자료");
    expect(screen.getByTestId("evg-volume").querySelector(".evg-foot")?.textContent).toBe(
      "마지막 저장일 2026-10-08",
    );
    expect(screen.queryByTestId("detail-flows-body")).toBeNull(); // 세부 흐름 창은 누를 때만
    openFlows();
    const body = screen.getByTestId("detail-flows-body");
    expect(body.textContent).toContain(
      "마지막 저장일 2026-10-08 · 5저장일 2026-09-30 ~ 2026-10-08 · 20저장일 2026-09-07 ~ 2026-10-08",
    );
    // RESULT 판정 §2-4(EV-3) — 아래 거래량 줄 = 비교 구간 · 유효 자료 수만 · 제공처 원문은 창 도움말(아래 Decline 시험).
    expect(screen.getByTestId("detail-flows-volume-window").textContent).toBe(
      "거래량 · 비교 구간 2026-09-07 ~ 2026-10-07 · 유효 20/20",
    );
    expect(body.textContent).not.toContain("FinanceDataReader");
    expect(body.textContent).not.toContain("출처");
    expect(screen.queryByTestId("detail-flows-strip")).toBeNull(); // 창 첫 줄 없음(POC6-33 E4)
  });

  it("거래량 필드가 없으면 '거래량 자료 없음'만 · 차트 · NAV 는 그대로 · 세부를 펼쳐도 다시 조회하지 않는다", async () => {
    await renderAndSelect("비");
    expect(screen.getByTestId("evg-volume").textContent).toContain("거래량 자료 없음");
    expect(screen.getByText("순자산가치(NAV) · 괴리율")).toBeTruthy();
    expect(fetchPriceSeries).toHaveBeenCalled();
    const priceCalls = fetchPriceSeries.mock.calls.length;
    openFlows();
    expect(fetchPriceSeries.mock.calls.length).toBe(priceCalls);
    expect(fetchEnrichedHoldings).toHaveBeenCalledTimes(1);
    expect(fetchHoldingsMarketEvidence).toHaveBeenCalledTimes(1);
  });
});

// ── POC6-33 — 누른 행 바로 아래 상세 · 상세 순서 · 주간 순위 · 구성 · NAV · 개별 주식 · 요약 (PLAN §3 · 판정 §3 · §4) ──
// 고정 자료 = 위 evidenceWithBasis(합성 종목 에이 · 비 · 씨 · 기본 정렬 5저장일 변화 = 비 · 에이 · 씨).
const ALL_EXCLUDED = { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true };
// RESULT 판정 §1 — 순위 이름 = '1개월 수익률 상위 30'(조건 줄도 같은 이름).
const WEEKLY_BASIS = "「주간 ETF 점검」과 같은 조회 · 1개월 수익률 상위 30 · 10/12 → 11/9 · 인버스 · 레버리지 · 합성 · 선물 제외";

describe("확인 근거 — 상세 배치 · 순서 · 주간 순위 · 구성 · NAV (POC6-33)", () => {
  beforeEach(() => {
    __resetQueryCache();
    fetchEnrichedHoldings.mockReset();
    fetchHoldingsMarketEvidence.mockReset();
    fetchEnrichedHoldings.mockResolvedValue(enrichedThree());
    fetchHoldingsMarketEvidence.mockResolvedValue(evidenceWithBasis());
    fetchPriceSeries.mockResolvedValue({ availability: "NO_DATA", points: [] });
  });
  const click = async (name: string) => {
    await act(async () => {
      fireEvent.click(rowEl(name));
      await Promise.resolve();
      await Promise.resolve();
    });
  };
  const rankLine = (): [string | undefined, string | null] => {
    const v = screen.getByTestId("hre-weekly-rank").querySelector(".v");
    return [v?.querySelector("strong")?.textContent, v?.querySelector(".hre-detail-sub")?.textContent ?? null];
  };
  const navCellsOf = () =>
    Object.fromEntries(
      Array.from(screen.getByTestId("hre-nav").querySelectorAll(".hre-nav-cell")).map((c) => [
        c.getAttribute("data-nav-label"),
        c.querySelector(".v")?.textContent,
      ]),
    );

  it("E3 · 판정 Q30 — 상세는 누른 행 바로 아래 · 같은 행 다시 누르면 닫힘 · 다른 행이면 위 상세는 닫히고 하나만 · 빠른 보기로 숨으면 상세도 숨음", async () => {
    await renderSection();
    expect(screen.queryByTestId("hre-detail")).toBeNull();
    expect(document.body.textContent ?? "").not.toContain("표에서 ETF 를 선택하면");
    await click("에이");
    expect(rowEl("에이").nextElementSibling).toBe(screen.getByTestId("hre-detail"));
    expect(rowEl("에이").getAttribute("aria-expanded")).toBe("true");
    expect(rowEl("비").getAttribute("aria-expanded")).toBe("false");
    await click("에이");
    expect(screen.queryByTestId("hre-detail")).toBeNull();
    expect(rowEl("에이").getAttribute("aria-expanded")).toBe("false");
    await click("비");
    await click("씨");
    expect(screen.getAllByTestId("hre-detail")).toHaveLength(1);
    expect(rowEl("씨").nextElementSibling).toBe(screen.getByTestId("hre-detail"));
    expect(rowEl("비").nextElementSibling).toBeNull();
    await act(async () => {
      fireEvent.keyDown(rowEl("씨"), { key: "Enter" });
      await Promise.resolve();
    });
    expect(screen.queryByTestId("hre-detail")).toBeNull();
    // 빠른 보기로 선택 행이 숨으면 상세도 숨고, 다시 보이면 선택 그대로.
    await click("에이");
    fireEvent.click(screen.getByRole("button", { name: /^자료 확인 필요 \(/ }));
    expect(screen.queryByTestId("hre-detail")).toBeNull();
    // 다시 보이는 상세의 '주요 편입' 조회 응답까지 act 안에서 받는다(act 경고 없이 · 그 줄의 결과까지 확인).
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "전체" }));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(rowEl("에이").nextElementSibling).toBe(screen.getByTestId("hre-detail"));
    expect(screen.getByTestId("hre-main-holdings").textContent).not.toContain("불러오는 중");
  });

  it("E3 · 판정 Q30 — 위 행 상세가 닫혀 아래 행이 밀려도 누른 행의 화면 위치를 지킨다(누르기 전 · 그린 뒤 차이만큼 스크롤)", async () => {
    await renderSection();
    // jsdom 은 배치를 계산하지 않아 행 위치를 직접 준다(행 묶음 data-row-ticker 의 위 · 누르기 전 → 그린 뒤 순서).
    const tops: Record<string, number[]> = {};
    const rect = vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      const q = tops[this.dataset.rowTicker ?? ""];
      const top = q && q.length ? (q.shift() as number) : 0;
      return { top, bottom: top, left: 0, right: 0, width: 0, height: 0, x: 0, y: top, toJSON: () => ({}) } as DOMRect;
    });
    const scrollBy = vi.fn();
    const orig = window.scrollBy;
    window.scrollBy = scrollBy as unknown as typeof window.scrollBy;
    try {
      tops.B1 = [120, 120];
      await click("비"); // 맨 위 행 — 위치 그대로 · 스크롤 없음
      expect(scrollBy).not.toHaveBeenCalled();
      tops.A1 = [640, 360]; // 비 상세(280px)가 닫혀 에이가 위로 밀림
      await click("에이");
      expect(scrollBy).toHaveBeenCalledTimes(1);
      expect(scrollBy).toHaveBeenCalledWith(0, -280);
      expect(rowEl("에이").nextElementSibling).toBe(screen.getByTestId("hre-detail"));
      tops.A1 = [360, 360];
      await click("에이"); // 같은 행 닫기 — 누른 행은 그대로
      expect(scrollBy).toHaveBeenCalledTimes(1);
    } finally {
      rect.mockRestore();
      window.scrollBy = orig;
    }
  });

  it("판정 Q1 — 상세 순서 = 방향 → 순위 → 필요한 자료 안내 → 세 묶음 → 날짜 역할 → 차트 → 주요 편입 → 구성종목 중복 → NAV", async () => {
    await renderSection();
    await click("에이");
    const kids = Array.from(screen.getByTestId("hre-detail").children).map((c) =>
      c.classList.contains("hre-detail-head")
        ? "head"
        : (c.getAttribute("data-testid") ?? ((c.textContent ?? "").includes("저장된 가격 데이터 없음") ? "chart" : "?")),
    );
    expect(kids).toEqual([
      "head",
      "hre-direction",
      "hre-weekly-rank",
      "hre-guidance",
      "evidence-groups",
      "hre-date-roles",
      "chart",
      "hre-main-holdings",
      "hre-overlap",
      "hre-nav",
    ]);
    expect(screen.getByTestId("hre-guidance").querySelector(".k")?.textContent).toBe("필요한 자료 안내");
    // E9 — 날짜 역할(응답 날짜만).
    expect(Array.from(screen.getByTestId("hre-date-roles").children).map((e) => e.textContent)).toEqual([
      "20저장일 수익률 = 시작 종가 9/7 → 끝 종가 10/8(종가 21개 · 변화 20구간)",
      "거래량 평균 = 비교 구간 9/7 ~ 10/7",
    ]);
  });

  it("판정 Q34 · Q37 · Q50 — 방향 줄 = 최근 20저장일 값 + 방향 낱말 · KODEX 200 대비는 근거 응답 값(주간 요약 값 아님)", async () => {
    // 주간 요약 응답의 가격 흐름 값은 일부러 다르게 — 화면이 그 값을 쓰면 시험이 깨진다.
    fetchEtfCompareSummary.mockResolvedValue(
      summaryOk({
        holdings: {
          status: "ok",
          items: [link({ ticker: "A1", price_flow: flow({ return_20d_pct: 77, excess_vs_kodex200_20d_pctp: 77 }) })],
        },
      }),
    );
    await renderSection();
    await click("에이");
    expect(screen.getByTestId("hre-direction").textContent).toBe(
      "최근 20저장일 -3.00%(내렸음) · 같은 기간 KODEX 200 대비 -1.50%p",
    );
    await click("씨"); // 기준일이 다른 종목 — 값을 비운 사본 → 기존 '자료 확인 필요'
    expect(screen.getByTestId("hre-direction").textContent).toBe(
      "최근 20저장일 자료 확인 필요 · 같은 기간 KODEX 200 대비 자료 확인 필요",
    );
  });

  it("판정 Q22 · Q24 · Q49 — 주간 순위 줄: 상위 30 안 n위 + 장중 · 순위권 밖(하위 30) · 규칙상 제외 · 그 조회의 조건 · 기간 · 요청 한 번", async () => {
    fetchEtfCompareSummary.mockResolvedValue(
      summaryOk({
        holdings: {
          status: "ok",
          items: [
            link({
              ticker: "A1",
              top_rank: 3,
              side: "top",
              side_rank: 3,
              end_price: { date: "2026-11-09", state: "intraday", fetched_at_kst: "2026-11-09T10:00:00+09:00" },
            }),
            link({ ticker: "B1", side: "bottom", side_rank: 1, top_rank: null }),
            link({ ticker: "C1", in_population: false, out_reason: "filter_excluded", basis_return: null }),
          ],
        },
      }),
    );
    await renderSection();
    await click("에이");
    expect(screen.getByTestId("hre-weekly-rank").querySelector(".k")?.textContent).toBe("주간 후보 여부 · 순위");
    expect(rankLine()).toEqual([
      "1개월 수익률 상위 30 중 3위 · 10/12 → 11/9 · 인버스 · 레버리지 · 합성 · 선물 제외 · 장중 저장값 기준",
      WEEKLY_BASIS,
    ]);
    await click("비");
    expect(rankLine()).toEqual(["순위권 밖 · 1개월 수익률 상위 30 밖 · 10/12 → 11/9", WEEKLY_BASIS]);
    await click("씨");
    expect(rankLine()).toEqual([
      "규칙상 제외 — 인버스 · 레버리지 · 합성 · 선물 제외 조건 · 가격 · 손익 근거는 아래 그대로",
      WEEKLY_BASIS,
    ]);
    expect(screen.getByTestId("evidence-groups")).toBeTruthy();
    expect(screen.getByTestId("hre-nav")).toBeTruthy();
    expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(1);
  });

  // ── 검증자 r1 F1 — 화면 진입마다 같은 키로 한 번 새로 읽기 · 이번 진입 조회 전 · 실패 · stale 에 이전 순위를 보이지 않음 ──
  const rankSummary = (rank: number) =>
    summaryOk({ holdings: { status: "ok", items: [link({ ticker: "A1", top_rank: rank, side: "top", side_rank: rank })] } });
  const enterAndOpen = async () => {
    const view = await renderSection();
    await click("에이");
    return view;
  };

  it("판정 Q22 · E5(검증자 r1 F1) — 다시 들어오면 공유 캐시에 이전 성공값이 있어도 새로 읽어 새 순위를 보인다 · 진입마다 요청 한 번", async () => {
    fetchEtfCompareSummary.mockResolvedValue(rankSummary(3));
    const first = await enterAndOpen();
    expect(rankLine()[0]).toMatch(/^1개월 수익률 상위 30 중 3위 · /);
    await click("비");
    await click("에이"); // 같은 진입 안에서 상세를 다시 열어도 다시 읽지 않음
    expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(1);
    first.unmount(); // 캐시는 그대로 두고(같은 세션) 서버의 다음 응답만 25위
    fetchEtfCompareSummary.mockResolvedValue(rankSummary(25));
    await enterAndOpen();
    expect(rankLine()[0]).toMatch(/^1개월 수익률 상위 30 중 25위 · /);
    expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(2);
    expect(fetchEtfCompareSummary).toHaveBeenLastCalledWith(WEEKLY_CHECK_CONDITION);
  });

  it("검증자 r1 F1 — 다시 들어온 뒤 이번 조회가 끝나기 전에는 이전 순위 대신 '불러오는 중'", async () => {
    fetchEtfCompareSummary.mockResolvedValue(rankSummary(3));
    const first = await enterAndOpen();
    first.unmount();
    let resolve: (v: unknown) => void = () => {};
    fetchEtfCompareSummary.mockImplementation(() => new Promise((r) => (resolve = r)));
    await enterAndOpen();
    expect(rankLine()).toEqual(["주간 순위 불러오는 중...", null]);
    await act(async () => {
      resolve(rankSummary(25));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(rankLine()[0]).toMatch(/^1개월 수익률 상위 30 중 25위 · /);
  });

  it("검증자 r1 F1 — 다시 들어온 뒤 이번 조회가 실패하면 이전 순위 대신 '조회 실패' · 그 종목 가격 근거는 그대로", async () => {
    fetchEtfCompareSummary.mockResolvedValue(rankSummary(3));
    const first = await enterAndOpen();
    first.unmount();
    fetchEtfCompareSummary.mockRejectedValue(new Error("summary down"));
    await enterAndOpen();
    expect(rankLine()).toEqual(["자료 확인 불가 — 주간 순위 조회 실패", null]);
    expect(document.body.textContent ?? "").not.toMatch(/3위/);
    expect(screen.getByTestId("evidence-groups")).toBeTruthy();
    expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(2);
  });

  it("검증자 r1 F1 — 보는 중에 같은 키의 다시 읽기가 다른 화면에서 실패하면(stale) 이전 순위 대신 '조회 실패'", async () => {
    fetchEtfCompareSummary.mockResolvedValue(rankSummary(3));
    await enterAndOpen();
    expect(rankLine()[0]).toMatch(/ 중 3위 · /);
    await act(async () => {
      markQueryFailed(etfCompareKey(WEEKLY_CHECK_CONDITION));
      await Promise.resolve();
    });
    expect(rankLine()).toEqual(["자료 확인 불가 — 주간 순위 조회 실패", null]);
  });

  it("판정 Q52 — 주간 순위 조회 중 · 실패여도 목록 · 요약 · 그 종목의 가격 · 거래량 · 구성 · NAV 근거는 그대로 읽힌다", async () => {
    let fail: (e: Error) => void = () => {};
    fetchEtfCompareSummary.mockImplementation(() => new Promise((_, rej) => (fail = rej)));
    await renderSection();
    expect(screen.queryByText("불러오는 중...")).toBeNull();
    expect(rowOrder()).toEqual(["비", "에이", "씨"]);
    await click("에이");
    expect(rankLine()).toEqual(["주간 순위 불러오는 중...", null]);
    await act(async () => {
      fail(new Error("summary down"));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(rankLine()).toEqual(["자료 확인 불가 — 주간 순위 조회 실패", null]);
    expect(screen.queryByTestId("hre-risk-state-failed")).toBeNull();
    expect(screen.getByTestId("hre-risk-summary")).toBeTruthy();
    for (const id of ["hre-direction", "evidence-groups", "hre-main-holdings", "hre-overlap", "hre-nav"]) {
      expect(screen.getByTestId(id)).toBeTruthy();
    }
    expect(screen.queryByTestId("hre-stock-na")).toBeNull();
  });

  it("판정 Q33 · E12 — 개별 주식이 확인되면 'ETF 순위 대상 아님' · 구성 · NAV 대신 한 줄 · 영어 안내 · 상태 원문 없음 · 구성 요약을 읽지 않음", async () => {
    const ev = evidenceWithBasis();
    ev.holdings[1] = {
      ...ev.holdings[1],
      constituents_overlap: { status: "constituents_unavailable", overlap_with_market_core: [] },
      nav_discount: {
        status: "unavailable", source: "not_integrated", asof: null, nav: null, market_price: null,
        discount_rate_pct: null, flag: null, message: "NAV / discount source not integrated",
      },
      evidence_notes: [
        "현재 Market Discovery TOP 10 후보에 포함되어 있지 않습니다.",
        "구성종목 데이터가 캐시에 없어 비교할 수 없습니다.",
        "NAV / 괴리율은 source 미연동으로 확인할 수 없습니다.",
      ],
    };
    fetchHoldingsMarketEvidence.mockResolvedValue(ev);
    fetchEtfCompareSummary.mockResolvedValue(
      summaryOk({
        holdings: {
          status: "ok",
          items: [link({ ticker: "B1", is_stock: true, in_population: false, out_reason: "stock", basis_return: null })],
        },
      }),
    );
    await renderSection();
    await click("비");
    expect(rankLine()).toEqual(["ETF 순위 대상 아님(개별 주식)", null]);
    expect(screen.getByTestId("hre-stock-na").querySelector(".v")?.textContent).toBe(
      "NAV·ETF 구성종목 해당 없음(개별 주식)",
    );
    for (const id of ["hre-nav", "hre-overlap", "hre-main-holdings", "hre-guidance"]) {
      expect(screen.queryByTestId(id)).toBeNull();
    }
    const text = screen.getByTestId("hre-detail").textContent ?? "";
    for (const bad of ["not integrated", "constituents_unavailable", "캐시", "source", "Market Discovery"]) {
      expect(text).not.toContain(bad);
    }
    expect(fetchConstituentsSummary).not.toHaveBeenCalled();
  });

  it("I-12 · I-11 ④ — 주간 요약이 실패하면 개별 주식으로 보지 않고 근거 응답대로(확인 불가 · 출처 '-' · 영어 안내는 [자세히] 안에만)", async () => {
    const ev = evidenceWithBasis();
    ev.holdings[1] = {
      ...ev.holdings[1],
      constituents_overlap: { status: "constituents_unavailable", overlap_with_market_core: [] },
      nav_discount: {
        status: "unavailable", source: "not_integrated", asof: null, nav: null, market_price: null,
        discount_rate_pct: null, flag: null, message: "NAV / discount source not integrated",
      },
    };
    fetchHoldingsMarketEvidence.mockResolvedValue(ev);
    fetchEtfCompareSummary.mockRejectedValue(new Error("summary down"));
    await renderSection();
    await click("비");
    expect(rankLine()).toEqual(["자료 확인 불가 — 주간 순위 조회 실패", null]);
    expect(screen.queryByTestId("hre-stock-na")).toBeNull();
    expect(navCellsOf()).toEqual({
      시장가: "-", NAV: "-", 괴리율: "-", 기준일: "-", 출처: "-", "수집 상태": "확인 불가",
    });
    expect(screen.getByText(/not integrated/).closest("details")).toBe(screen.getByTestId("hre-nav-raw"));
    expect(screen.getByTestId("hre-overlap").querySelector(".v")?.textContent).toBe(
      "구성종목 확인 불가 — 이 ETF 의 저장 구성 자료 없음",
    );
  });

  it("판정 Q25 · Q26 · Q51 — 구성종목 중복 = '비교 범위 확인 불가' · 비교 목록 범위 · 비교 상한 · '중복 없음' · 건수 없음 · 찾은 겹침은 이름 · 비중", async () => {
    const ev = evidenceWithBasis();
    ev.topn_basis = {
      basis: "one_month", n: 10, count: 10, filters: ALL_EXCLUDED,
      start_min: "2026-09-08", start_max: "2026-09-08", end: "2026-10-08",
    };
    ev.holdings[1] = {
      ...ev.holdings[1],
      constituents_overlap: {
        status: "ok",
        overlap_with_market_core: [
          { ticker: "X9", name: "구성 9", weight_pct: 1.234, market_core_count: 3 },
          { ticker: "X8", name: "구성 8", weight_pct: null, market_core_count: 2 },
        ],
      },
    };
    ev.holdings[2] = {
      ...ev.holdings[2],
      constituents_overlap: { status: "market_core_unavailable", overlap_with_market_core: [] },
    };
    fetchHoldingsMarketEvidence.mockResolvedValue(ev);
    await renderSection();
    await click("에이");
    const o = () => screen.getByTestId("hre-overlap");
    expect(o().querySelector(".v strong")?.textContent).toBe("비교 범위 확인 불가");
    // RESULT 판정 §2-1 — '비교 범위 확인 불가'가 맨 앞 · 다음 줄 = 주간 순위와 별도인 후보 목록 + 그 목록의 기간 · 제외 조건.
    expect(o().querySelector(".v")?.firstElementChild?.textContent).toBe("비교 범위 확인 불가");
    expect(screen.getByTestId("hre-overlap-list-basis").textContent).toBe(
      "비교 후보 목록(주간 순위 목록과 별도): 1개월 상위 10개 기준 · 시작 9/8 → 끝 10/8 · 인버스 · 레버리지 · 합성 · 선물 제외",
    );
    // 실제 비교 대상 = 후보 2곳 이상의 상위 10행에 함께 나온 종목(builder min_appears=2) · 후보 한 곳에만 있는 종목은 대상 아님.
    expect(o().textContent).toContain(
      "보유 ETF 구성 상위 10행을, 후보 가운데 2곳 이상의 구성 상위 10행에 함께 나온 종목(반복 핵심 종목)과 비교 · 상위 10행 = 비교 상한",
    );
    expect(o().textContent).not.toMatch(/중복 없음|겹치는 항목이 없|겹침 \d|\d건/);
    expect(screen.queryByTestId("hre-overlap-found")).toBeNull();
    await click("비");
    expect(o().querySelector(".v strong")?.textContent).toBe("비교 범위 확인 불가");
    // 비중 = 보유 ETF 자신의 구성 행 비중 → '이 ETF 편입 비중' · 비중 없는 종목은 이름만 · 건수 · 비율 · '중복 없음' 없음.
    expect(
      Array.from(screen.getByTestId("hre-overlap-found").querySelectorAll("li")).map((li) => li.textContent),
    ).toEqual(["구성 9 · 이 ETF 편입 비중 1.23%", "구성 8"]);
    expect(o().textContent).not.toMatch(/중복 없음|겹치는 항목이 없|겹침 \d|\d건|\d개 겹침|비율/);
    await click("씨");
    expect(o().querySelector(".v")?.textContent).toBe("구성종목 확인 불가 — 비교 후보의 구성 자료 없음");
    expect(o().textContent).not.toContain("market_core_unavailable");
  });

  it("판정 Q27 · E8 — 상세를 열 때 그 ETF 구성 요약 한 번 · 구성 기준일 · 기존 상태 글 · 저장 행 · 주요 편입 / 미수집 / 조회 실패", async () => {
    fetchConstituentsSummary.mockImplementation((t: string) =>
      t === "A1"
        ? Promise.resolve(consSummary(t))
        : t === "B1"
          ? Promise.resolve(consSummary(t, { state: "not_collected", state_label: "미수집", asof: null, stored_rows: 0, top_stocks: [] }))
          : Promise.reject(new Error("constituents down")),
    );
    await renderSection();
    expect(fetchConstituentsSummary).not.toHaveBeenCalled();
    await click("에이");
    expect(fetchConstituentsSummary).toHaveBeenCalledTimes(1);
    expect(fetchConstituentsSummary).toHaveBeenCalledWith("A1");
    const m = () => screen.getByTestId("hre-main-holdings");
    expect(m().querySelector(".k")?.textContent).toBe("주요 편입");
    expect(m().querySelector(".v")?.firstChild?.textContent).toBe("구성 기준일 10/7 · 전체 확인 · 저장 12행");
    expect(m().querySelector(".hre-detail-sub")?.textContent).toBe("구성 1 9.9% · 구성 2 5.0%");
    await click("비");
    expect(m().querySelector(".v")?.textContent).toBe("미수집 — 저장된 구성 자료 없음");
    await click("씨");
    expect(m().querySelector(".v")?.textContent).toBe("구성 자료를 읽지 못함 — 조회 실패");
    expect(fetchConstituentsSummary).toHaveBeenCalledTimes(3);
  });

  it("판정 Q38 · Q53 · Q54 — NAV 묶음 여섯 칸 · 괴리 표시(3% 이상) · 숫자 색 · ? 도움말 = 괴리율 뜻 · 3% · 5% 기준", async () => {
    const ev = evidenceWithBasis();
    ev.holdings[0] = {
      ...ev.holdings[0],
      nav_discount: {
        status: "ok", source: "naver_etf_item_list", asof: "2026-10-08", nav: 1000, market_price: 1031,
        discount_rate_pct: 3.1, flag: "discount_check_needed", message: null,
      },
    };
    fetchHoldingsMarketEvidence.mockResolvedValue(ev);
    await renderSection();
    await click("에이");
    expect(navCellsOf()).toEqual({
      시장가: "1,031", NAV: "1,000", 괴리율: "+3.10%", 기준일: "2026-10-08", 출처: "네이버", "수집 상태": "수집됨",
    });
    const rate = screen.getByTestId("hre-nav").querySelector('[data-nav-label="괴리율"]') as HTMLElement;
    expect(rate.querySelector(".nav-flag")?.textContent).toBe("괴리 확인 필요(3% 이상)");
    expect((rate.querySelector(".v") as HTMLElement).style.color).toBe("var(--warn)");
    expect(screen.queryByTestId("hre-nav-raw")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "순자산가치(NAV) · 괴리율 도움말" }));
    const help = screen.getByRole("dialog", { name: "순자산가치(NAV) · 괴리율 도움말" }).textContent ?? "";
    expect(help).toContain("양수는 그 기준 시점의 시장가가 NAV 보다 높았다는 뜻");
    expect(help).toContain("‘괴리 확인 필요(3% 이상)’");
    expect(help).toContain("‘괴리 주의(5% 이상)’");
  });

  it("판정 Q23 · E6 — 필요한 자료 안내는 옛 후보 · 반복 수치 · 범위 없는 겹침 문구를 거르고 자료 부족 안내는 남긴다", async () => {
    const ev = evidenceWithBasis();
    ev.holdings[0] = {
      ...ev.holdings[0],
      evidence_notes: [
        "현재 Market Discovery TOP 10 후보에 포함되어 있지 않습니다.",
        "20거래일 KODEX200 대비 단기 흐름 차이 -1.50%p.",
        "단기 흐름은 데이터 부족으로 확인할 수 없습니다.",
        "구성종목 기준 현재 후보군의 반복 핵심 종목과 겹치는 항목이 없습니다.",
        "NAV / 괴리율 확인이 필요합니다.",
      ],
    };
    fetchHoldingsMarketEvidence.mockResolvedValue(ev);
    await renderSection();
    await click("에이");
    expect(guidanceItems()).toEqual(["단기 흐름은 데이터 부족으로 확인할 수 없습니다."]);
    const text = screen.getByTestId("hre-detail").textContent ?? "";
    for (const bad of ["Market Discovery", "겹치는 항목이 없", "20거래일", "NAV / 괴리율 확인"]) {
      expect(text).not.toContain(bad);
    }
  });

  it("판정 Q31 · Q32 · E1 · RESULT 판정 §2-6 — 가격 기준일은 요약 한 칸에만 · 보유 저장 시각 = 분 단위 한국 시각 · 기존 후보 목록 기준일은 다를 때만 + ? 뜻", async () => {
    const ev = evidenceWithBasis();
    ev.holdings_asof = "2026-11-06T05:07:09.123456+00:00";
    ev.market_asof = "2026-10-08";
    fetchHoldingsMarketEvidence.mockResolvedValue(ev);
    const first = await renderSection();
    const aux = () =>
      Array.from(screen.getByTestId("hre-risk-scope").querySelectorAll("span")).map((n) => n.textContent ?? "");
    const headHelp = () => {
      fireEvent.click(screen.getByRole("button", { name: "현재 보유 점검 상태 도움말" }));
      const paras = Array.from(
        screen.getByRole("dialog", { name: "현재 보유 점검 상태 도움말" }).querySelectorAll(".help-pop-p"),
      ).map((x) => x.textContent ?? "");
      fireEvent.keyDown(document, { key: "Escape" });
      return paras;
    };
    expect(screen.getByTestId("hre-risk-date").textContent).toBe("2026-10-08");
    expect(screen.getByTestId("hre-risk-need").textContent).toBe("1종목");
    expect(aux()[0]).toBe("보유 저장 시각 2026-11-06 14:07 KST");
    expect(aux().some((t) => t.startsWith("기존 후보 목록 기준일") || t.startsWith("시장 기준일"))).toBe(false);
    expect(headHelp().some((t) => t.startsWith("기존 후보 목록 기준일"))).toBe(false); // 보일 때만 뜻을 더함
    expect(aux()).toContain("계산 가능 2/3종목");
    expect(document.body.textContent ?? "").not.toMatch(/PC 저장 가격 기준일|PC 가격 흐름 기준일|PC 비교 기준일|보유 기준일|시장 기준일/);
    first.unmount();
    __resetQueryCache();
    fetchHoldingsMarketEvidence.mockResolvedValue({ ...ev, market_asof: "2026-10-07" });
    await renderSection();
    expect(aux()).toContain("기존 후보 목록 기준일 2026-10-07");
    expect(aux().some((t) => t.startsWith("시장 기준일"))).toBe(false);
    // 같은 요약의 '가격 기준일' 칸 · 상세 주간 순위의 기간과 다른 날짜라는 뜻을 기존 ? 도움말 마지막 문단으로.
    const help = headHelp();
    expect(help[help.length - 1]).toBe(
      "기존 후보 목록 기준일은 종목 상세 ‘구성종목 중복’이 비교에 쓰는 기존 후보 목록의 날짜입니다. 종목 가격 흐름 · 하락 구간의 ‘가격 기준일’, 종목 상세 주간 순위(「주간 ETF 점검」과 같은 수익률 순위)의 기간과 따로 정해지며, 가격 기준일과 같은 날이면 적지 않습니다.",
    );
  });
});
