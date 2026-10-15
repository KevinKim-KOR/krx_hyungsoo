// POC3-05 보유 ETF 확인 근거 — 컴포넌트 계약 test.
// - 금지어(위험/고위험/손절/매도/청산/BUY/SELL) 비노출.
// - 급락(falling) 관련 열·빠른보기 없음(이번 Step 제외).
// - 읽기 전용(값 수정·저장 버튼 없음). N+1 없음(2 endpoint 단일 조회).
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, fireEvent, within } from "@testing-library/react";
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
import type { MenuKey } from "./LeftSidebar";

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
    // 빠른 보기는 전체 / 하락 구간 / 자료 확인 필요 세 개(POC5-13 '하락 구간' 추가 · 급락 보기 없음).
    expect(screen.getByRole("button", { name: "전체" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /하락 구간/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /자료 확인 필요/ })).toBeTruthy();
    expect(document.querySelectorAll(".hre-quickview button")).toHaveLength(3);
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
async function renderAndSelect(name: string, onNavigate?: (key: MenuKey) => void) {
  render(<HoldingsRiskEvidenceSection onNavigate={onNavigate} />);
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

  it("네 정렬 · 기본 5일 변화 · 값 없는 행은 맨 뒤 · KODEX200 대비 값은 계속 보인다 · 다시 조회하지 않는다", async () => {
    await renderSection();
    const group = screen.getByRole("group", { name: "확인 근거 정렬 기준" });
    const labels = Array.from(group.querySelectorAll("button")).map((b) => b.textContent);
    expect(labels).toEqual(["평가 비중", "손익률", "5일 변화", "20일 변화"]);
    expect(screen.queryByRole("button", { name: "KODEX200 대비" })).toBeNull();
    expect(screen.getByRole("button", { name: "5일 변화" }).getAttribute("aria-pressed")).toBe("true");
    expect(rowOrder()).toEqual(["비", "에이", "씨"]); // 5일 -3 · -1 · 없음

    const cases: Array<[string, string[]]> = [
      ["평가 비중", ["에이", "씨", "비"]], // 50 · 30 · 20 (큰 값부터)
      ["손익률", ["비", "씨", "에이"]], // -20 · 0 · +25
      ["20일 변화", ["에이", "비", "씨"]], // -3 · -1 · 없음
      ["5일 변화", ["비", "에이", "씨"]],
    ];
    for (const [label, order] of cases) {
      fireEvent.click(screen.getByRole("button", { name: label }));
      expect(screen.getByRole("button", { name: label }).getAttribute("aria-pressed")).toBe("true");
      expect(rowOrder()).toEqual(order);
    }
    // 상대 성과 값 표시는 유지 — 행마다 'KODEX200 대비 20일' 칸과 그 값.
    const list = screen.getByTestId("hre-evidence-list");
    expect(screen.getAllByText("KODEX200 대비 20일").length).toBeGreaterThanOrEqual(3);
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

  it("선택 종목의 evidence_notes 를 그 종목 상세에만 보인다(다른 종목 사유 섞임 없음)", async () => {
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
    // 씨 = 자료 확인 필요(5일 · 20일 없음)인데 일반 문구뿐 → 사유 미제공 문구를 먼저.
    expect(guidanceItems()).toEqual([
      NO_REASON,
      "현재 Market Discovery 후보에 포함되어 있지 않습니다.",
    ]);
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
      "같은 종목의 계좌별 단기 흐름 값(상태 · 5일 · 20일 · KODEX200 대비)이 서로 다릅니다.",
      "공통 메모",
    ]);
  });

  it("자료 확인 필요인데 사유가 없으면 '상세 사유 정보가 제공되지 않습니다' · 정상 종목은 안내 칸이 없다", async () => {
    await renderAndSelect("씨"); // 5일 · 20일 없음 · evidence_notes 없음
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
    expect(screen.getByRole("heading", { name: "C1 상세" })).toBeTruthy();
    expect(guidanceItems()).toEqual([NO_REASON]);
    for (const label of ["평가 비중", "손익률", "20일 변화", "5일 변화"]) {
      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: label }));
        await Promise.resolve();
      });
      expect(screen.getByRole("heading", { name: "C1 상세" })).toBeTruthy();
      expect(guidanceItems()).toEqual([NO_REASON]);
    }
    expect(fetchEnrichedHoldings).toHaveBeenCalledTimes(1);
    expect(fetchHoldingsMarketEvidence).toHaveBeenCalledTimes(1);
  });

  it("'전체 ETF NAV·괴리율 보기 →'는 「데이터 상태」로 이동하고 다시 조회하지 않는다", async () => {
    const onNavigate = vi.fn();
    await renderAndSelect("에이", onNavigate);
    fireEvent.click(screen.getByRole("button", { name: "전체 ETF NAV·괴리율 보기 →" }));
    expect(onNavigate).toHaveBeenCalledTimes(1);
    expect(onNavigate).toHaveBeenCalledWith("data_status");
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
      "가격 흐름(5일 · 20일 · KODEX200 대비) 기준: PC 저장 가격 기준일 2026-10-08 · KODEX200 20일 비교 기간 2026-09-07 ~ 2026-10-08. 기준일이 다른 1종목은 현재 비교에서 뺐습니다: 씨(저장 가격 기준일 2026-08-12).",
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
    fireEvent.click(screen.getByRole("button", { name: "20일 변화" }));
    expect(rowOrder()).toEqual(["에이", "비", "씨"]);
  });

  it("기준일이 다른 종목 상세: 실제 날짜 사유 · 가격 흐름 기준 · 과거 저장 거래량 · NAV 유지", async () => {
    await renderAndSelect("씨");
    expect(guidanceItems()).toEqual([
      "저장 가격 기준일: 2026-08-12 / PC 비교 기준일: 2026-10-08 — 기준일이 달라 현재 비교에 사용하지 않습니다.",
      "씨 메모",
    ]);
    expect(screen.getByTestId("hre-price-flow").textContent).toBe(
      "가격 흐름 기준기준일 2026-08-12 · 5일 2026-08-05 ~ 2026-08-12 · 20일 2026-07-14 ~ 2026-08-12",
    );
    const vol = screen.getByTestId("stored-volume");
    expect(vol.textContent).toContain("씨 거래량");
    expect(vol.textContent).toContain("과거 저장 자료 · PC 비교 기준일은 2026-10-08");
    expect(Array.from(vol.querySelectorAll(".svb-v")).map((e) => e.textContent)).toEqual([
      "2026-08-12",
      "4,204,301주",
      "6,174,143.20주",
      "0.68배",
    ]);
    expect(screen.getByText("NAV · 괴리율")).toBeTruthy();
  });

  it("정상 종목 상세: 날짜 사유 없음 · 거래량 4칸 · 과거 표시 없음 · 출처 줄", async () => {
    await renderAndSelect("에이");
    expect(guidanceItems()).toEqual(["에이 메모"]);
    expect(screen.getByTestId("hre-price-flow").textContent).toContain(
      "기준일 2026-10-08 · 5일 2026-09-30 ~ 2026-10-08 · 20일 2026-09-07 ~ 2026-10-08",
    );
    const vol = screen.getByTestId("stored-volume");
    expect(Array.from(vol.querySelectorAll(".svb-v")).map((e) => e.textContent)).toEqual([
      "2026-10-08",
      "1,500,000주",
      "1,000,000.00주",
      "1.50배",
    ]);
    expect(vol.textContent).not.toContain("과거 저장 자료");
    expect(vol.querySelector(".svb-src")?.textContent).toBe(
      "출처 FinanceDataReader · 비교 구간 2026-09-07 ~ 2026-10-07 · 유효 20/20",
    );
    expect(vol.querySelector(".wb-detail-grid")?.className).toBe("wb-detail-grid");
  });

  it("거래량 필드가 없으면 '거래량 자료 없음'만 · 차트 · NAV 는 그대로 · 다시 조회하지 않는다", async () => {
    await renderAndSelect("비");
    expect(screen.getByTestId("stored-volume").textContent).toContain("거래량 자료 없음");
    expect(screen.getByText("NAV · 괴리율")).toBeTruthy();
    expect(fetchPriceSeries).toHaveBeenCalled();
    expect(fetchEnrichedHoldings).toHaveBeenCalledTimes(1);
    expect(fetchHoldingsMarketEvidence).toHaveBeenCalledTimes(1);
  });
});
