// POC3-02D-OPS-03 확정 계약 9 ⑥ · PLAN STEP 5-5 — KOSPI 를 보여 주는 나머지 자리도 카드와
// **같은 판정 · 같은 문구**를 쓰는지 본다.
//   - 코스피 차트: 부모가 넘긴 topn KOSPI 필드로 같은 판정의 선 색(추가 조회 없음 · KS-1) · 배지 · 기준 줄은 차트 아래에 없음
//     (머리 줄과 겹쳐 뺌 · 형수님 결정 2026-11-14 · POC6-29-1 결과서 §4-1).
//   - AI 복사 텍스트 · AI 세션 스냅샷: 'N/A' 대신 같은 상태 문장.
// 설계자 RESULT STEP 4 (2026-09-30) — 제목에서 'KS11' 제거 · 공식 자료원 한 줄 ·
// 「오늘의 투자 점검」 KOSPI 카드 출처 한 줄(기준일은 머리 줄 · 2026-11-14 '마지막 자료 기준일' 뺌) · 정비 큐 KOSPI 항목.
// 외부 호출 0 — `@/lib/api` 는 대역.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within, waitFor, act } from "@testing-library/react";
import type {
  MarketCandidate,
  MarketContext,
  MarketContextKospi,
  MarketTopNFilters,
  MarketTopNResponse,
} from "@/lib/api";
import { __resetQueryCache, markQueryFailed, type QueryState } from "@/lib/api/queryCache";

const fetchBenchmarkSeries = vi.fn();
vi.mock("@/lib/api", () => ({
  fetchBenchmarkSeries: (...a: unknown[]) => fetchBenchmarkSeries(...a),
}));
// POC6-29 — 목록 넘기기(ListTransfer)가 누를 때 읽는 시장 판정 · 시장 흐름.
const fetchMarketTopnLatest = vi.fn();
const fetchMarketFlowContext = vi.fn();
vi.mock("@/lib/api/market", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchMarketTopnLatest: (...a: unknown[]) => fetchMarketTopnLatest(...a),
}));
vi.mock("@/lib/api/marketFlow", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchMarketFlowContext: (...a: unknown[]) => fetchMarketFlowContext(...a),
}));

import KospiChart, { KOSPI_SERIES_KEY } from "./today/KospiChart";
import { morningOk } from "@/lib/morningTestFixtures";
import KospiHeadline from "./today/KospiHeadline";
import MarketContextCard from "./MarketContextCard";
import ListTransfer from "./workbench/ListTransfer";
import { summaryOk } from "@/lib/etfCompareTestFixtures";
import { collectMaintenance } from "./today/maintenanceQueue";
import { kospiStatusText } from "@/lib/kospiStatus";
import { buildMarketDiscoveryCopyText } from "@/lib/marketDiscoveryCopyText";
import { toMarketContextSnapshot } from "@/lib/etfExposureDraft";
import { loadAISessionsDraft } from "@/lib/aiSessionsDraft";

// 08:10 배치 전 · T-2 만 있는 날(확정 계약 9 — 정상 아님).
const STALE_T2: MarketContextKospi = {
  status: "stale",
  as_of_date: "2026-09-28",
  display_state: "stale",
  trading_day_lag: 1,
  today_is_trading_day: true,
};

const OK: MarketContextKospi = {
  status: "ok",
  return_20d_pct: 1.2,
  return_60d_pct: 3.4,
  return_1m_pct: 1.2,
  return_3m_pct: 3.4,
  as_of_date: "2026-09-29",
  display_state: "ok",
  trading_day_lag: 0,
  today_is_trading_day: true,
};

const STALE_TEXT =
  "기준일 지연 · KOSPI 기준일 2026-09-28 · 1거래일 지연 · KOSPI 원자료가 최근 거래일까지 갱신되지 않았습니다.";

function ctxWith(kospi: MarketContextKospi): MarketContext {
  return {
    status: "partial",
    asof: "2026-09-29",
    primary_benchmark: "KODEX200",
    regime_label: "보합장",
    regime_code: "neutral",
    regime_score: 0,
    regime_reasons: [],
    kodex200: { status: "ok", return_20d_pct: 1, return_60d_pct: 2 },
    kospi,
    warnings: [],
  };
}

const FILTERS: MarketTopNFilters = {
  exclude_inverse: true,
  exclude_leveraged: true,
  exclude_synthetic: true,
  exclude_futures: true,
};
const CANDIDATES = [{ rank: 1, ticker: "069500", name: "KODEX 200" }] as MarketCandidate[];

function seriesOk() {
  return {
    ticker: "KOSPI",
    availability: "AVAILABLE",
    available_from: "2026-09-01",
    available_to: "2026-09-28",
    series: [
      { date: "2026-09-23", price: 6901.55 },
      { date: "2026-09-28", price: 6889.74 },
    ],
  };
}

beforeEach(() => {
  __resetQueryCache();
  fetchBenchmarkSeries.mockReset();
  fetchBenchmarkSeries.mockResolvedValue(seriesOk());
  window.sessionStorage.clear();
});

describe("코스피 차트 — 같은 판정으로 선 색 · 그래프 아래 줄 없음(형수님 결정 2026-11-14)", () => {
  // 그래프 아래 두 줄(기간 · 저장일 수 · 최종값 / 배지 · 기준일 · N거래일 지연)은 코스피 공식 종가 머리 줄과 겹쳐 뺐다.
  const noBottomLines = (c: HTMLElement) => {
    expect(c.querySelector("[data-kospi-chart-state]")).toBeNull();
    expect(c.querySelector(".kospi-badge")).toBeNull();
    expect(c.textContent).not.toMatch(/개 저장일|최종|기준일|거래일 지연/);
  };

  it("기준일 지연: 아래 상태 줄 없이 선은 경고색", async () => {
    const { container } = render(<KospiChart kospi={STALE_T2} phase="success" />);
    await screen.findByTestId("kospi-chart-readout");
    noBottomLines(container);
    expect(container.querySelector("path")?.getAttribute("stroke")).toBe("var(--warn)");
    // 가격 흐름 조회는 차트 자기 것 1회뿐 — 판정은 부모가 넘긴 값(추가 호출 없음).
    expect(fetchBenchmarkSeries).toHaveBeenCalledTimes(1);
  });

  it("정상: 아래 줄 없음 · 선은 기본색", async () => {
    const { container } = render(<KospiChart kospi={OK} phase="success" />);
    await screen.findByTestId("kospi-chart-readout");
    noBottomLines(container);
    expect(container.querySelector("path")?.getAttribute("stroke")).toBe("var(--accent)");
  });

  it("자료원 확인 실패 = 경고색 · 휴장일 = 기본색(둘 다 아래 줄 없음)", async () => {
    const { container, unmount } = render(
      <KospiChart kospi={{ ...STALE_T2, display_state: "source_failed" }} phase="success" />,
    );
    await screen.findByTestId("kospi-chart-readout");
    noBottomLines(container);
    expect(container.querySelector("path")?.getAttribute("stroke")).toBe("var(--warn)");
    unmount();
    __resetQueryCache();
    const holiday = { ...OK, display_state: "holiday" as const, today_is_trading_day: false };
    const r = render(<KospiChart kospi={holiday} phase="success" />);
    await screen.findByTestId("kospi-chart-readout");
    noBottomLines(r.container);
    expect(r.container.querySelector("path")?.getAttribute("stroke")).toBe("var(--accent)");
  });

  it("KOSPI 판정을 불러오는 중이면 선은 기본색 · 아래 줄 없음", async () => {
    const { container } = render(<KospiChart kospi={null} phase="loading" />);
    await screen.findByTestId("kospi-chart-readout");
    noBottomLines(container);
    expect(container.querySelector("path")?.getAttribute("stroke")).toBe("var(--accent)");
  });

  it("가격 흐름 다시 읽기 실패로 이전 값을 그리면 경고 한 줄 · 선은 경고색", async () => {
    const { container } = render(<KospiChart kospi={OK} phase="success" />);
    await screen.findByTestId("kospi-chart-readout");
    expect(screen.queryByTestId("kospi-chart-stale")).toBeNull();
    act(() => markQueryFailed(KOSPI_SERIES_KEY)); // 이전 성공값은 두고 '다시 읽기 실패' 표시(캐시 실패 경로와 같음)
    expect((await screen.findByTestId("kospi-chart-stale")).textContent).toBe("⚠ 이전 조회값 (재조회 실패)");
    expect(container.querySelector("path")?.getAttribute("stroke")).toBe("var(--warn)");
    noBottomLines(container);
  });
});

describe("AI 복사 텍스트 · AI 세션 스냅샷 — 'N/A' 대신 같은 상태 문장", () => {
  it("상태 한 줄 = 배지 · 기준 줄 · 사유(카드와 같은 문구)", () => {
    expect(kospiStatusText(STALE_T2)).toBe(STALE_TEXT);
    expect(kospiStatusText(OK)).toBe("KOSPI 기준일 2026-09-29");
    expect(kospiStatusText({ status: "unavailable", as_of_date: null })).toBe(
      "수집 결과 없음 · 저장된 KOSPI 자료가 없습니다.",
    );
  });

  it("복사 텍스트: 지연이면 같은 문장 · 정상이면 기존 수익률 줄 그대로", () => {
    const stale = buildMarketDiscoveryCopyText({
      asof: "2026-09-29",
      filters: FILTERS,
      candidates: CANDIDATES,
      marketContext: ctxWith(STALE_T2),
    });
    expect(stale).toContain(`- KOSPI 보조 기준: ${STALE_TEXT}`);
    expect(stale).not.toContain("N/A");
    const ok = buildMarketDiscoveryCopyText({
      asof: "2026-09-29",
      filters: FILTERS,
      candidates: CANDIDATES,
      marketContext: ctxWith(OK),
    });
    expect(ok).toContain("- KOSPI 보조 기준: 20거래일 +1.20%, 60거래일 +3.40%");
  });

  it("복사 텍스트: 운영 판정이 ok 여도 화면 판정이 지연이면 수익률을 싣지 않는다", () => {
    const text = buildMarketDiscoveryCopyText({
      asof: "2026-09-29",
      filters: FILTERS,
      candidates: CANDIDATES,
      marketContext: ctxWith({ ...OK, display_state: "stale", as_of_date: "2026-09-28" }),
    });
    expect(text).not.toContain("20거래일 +1.20%");
    expect(text).toContain("- KOSPI 보조 기준: 기준일 지연 · KOSPI 기준일 2026-09-28");
  });

  it("ETF 노출 draft 스냅샷: 판정 · 기준일 · 같은 문장을 남긴다", () => {
    const snap = toMarketContextSnapshot(ctxWith(STALE_T2), CANDIDATES) as {
      kospi: Record<string, unknown>;
    };
    expect(snap.kospi).toEqual({
      status: "stale",
      return_20d_pct: null,
      return_60d_pct: null,
      as_of_date: "2026-09-28",
      display_state: "stale",
      state_text: STALE_TEXT,
    });
  });

  // POC6-29 — 「요즘 잘 오르는 ETF」 넘기기 카드는 보관 · 같은 계약을 「후보리스트」 목록 넘기기(ListTransfer)에서 본다.
  it("AI 투자 세션으로 넘기기(「후보리스트」 목록): 저장 draft 의 스냅샷 · 질문 문구가 같은 문장", async () => {
    fetchMarketTopnLatest.mockResolvedValue({ status: "ok", market_context: ctxWith(STALE_T2) });
    fetchMarketFlowContext.mockRejectedValue(new Error("x"));
    render(<ListTransfer s={summaryOk()} side="top" />);
    fireEvent.click(screen.getByRole("button", { name: "이 목록을 AI 투자 세션으로 넘기기" }));
    await waitFor(() => expect(loadAISessionsDraft()).not.toBeNull());
    const draft = loadAISessionsDraft();
    const snap = draft?.market_context_snapshot as { regime_label: string; kospi: Record<string, unknown>; candidate_excess_returns: unknown[] };
    expect(snap.regime_label).toBe("보합장");
    expect(snap.kospi.state_text).toBe(STALE_TEXT);
    expect(snap.kospi.display_state).toBe("stale");
    expect(snap.candidate_excess_returns).toHaveLength(summaryOk().top.length);
    expect(draft?.question_text).toContain("[시스템 시장 판정]");
    expect(draft?.question_text).toContain(`- KOSPI 보조 기준: ${STALE_TEXT}`);
  });

  it("넘길 때 시장 판정을 못 읽으면 글에 그 사실 · 스냅샷은 비움(다른 값으로 채우지 않음)", async () => {
    fetchMarketTopnLatest.mockRejectedValue(new Error("x"));
    fetchMarketFlowContext.mockRejectedValue(new Error("x"));
    render(<ListTransfer s={summaryOk()} side="top" />);
    fireEvent.click(screen.getByRole("button", { name: "이 목록을 AI 투자 세션으로 넘기기" }));
    await waitFor(() => expect(loadAISessionsDraft()).not.toBeNull());
    const draft = loadAISessionsDraft();
    expect(draft?.market_context_snapshot).toBeNull();
    expect(draft?.question_text).toContain("- 시장 판정을 불러오지 못했습니다(넘길 때 읽기 실패 · 이 글에는 싣지 않음)");
    expect(draft?.question_text).not.toContain("KOSPI 보조 기준");
  });
});

// 설계자 확정 문구(설계자 RESULT STEP 4-2) — 상수가 아니라 원문으로 고정해 본다.
const KRX_SOURCE = "출처: 한국거래소(KRX)";

// KODEX200 기준일(시장 판정 축)을 KOSPI 기준일과 다르게 둔다 — 둘을 헷갈리면 드러난다.
function todayMarket(kospi: MarketContextKospi): QueryState<MarketTopNResponse> {
  return {
    phase: "success",
    stale: false,
    data: { asof: "2026-09-21", market_context: { ...ctxWith(kospi), asof: "2026-09-21" } },
  } as unknown as QueryState<MarketTopNResponse>;
}

describe("설계자 RESULT STEP 4-1 · 4-2 — 시장 배경 카드 제목 · 공식 자료원", () => {
  it.each([
    ["정상", OK],
    ["기준일 지연", STALE_T2],
  ])("%s: 제목 'KOSPI (보조)' · 'KS11' 없음 · KOSPI 칸에 출처 한 줄", (_label, kospi) => {
    render(<MarketContextCard ctx={ctxWith(kospi)} />);
    const h3 = screen.getByRole("heading", { name: /^KOSPI \(보조\)/ });
    expect(document.body.textContent).not.toContain("KS11");
    const src = screen.getAllByText(KRX_SOURCE);
    expect(src).toHaveLength(1);
    // 출처 줄은 KOSPI 칸 안이다(KODEX200 칸이 아님).
    expect(h3.parentElement).toContainElement(src[0]);
    expect(src[0]).toHaveClass("helper");
  });
});

describe("설계자 RESULT STEP 4-2 · 4-3 — 「오늘의 투자 점검」 KOSPI 카드", () => {
  // 2026-11-14(설계자 지시 · POC6-29-1 결과서 §5) — 기준일은 코스피 공식 종가 머리 줄 한 곳이라 이 카드의 '마지막 자료
  // 기준일' 은 뺐다. 출처(KRX 약관 제10조③)는 카드 전체에 한 줄 그대로 · 코스피 수익률 · 위치의 날짜는 KOSPI 저장 종가
  // 끝 행(KODEX200 날짜 아님).
  const MORNING = { phase: "success", data: morningOk(), stale: false } as const;

  it("출처는 카드 전체에 한 줄 · 날짜는 KOSPI 종가 기준일(KODEX200 날짜 아님) · '마지막 자료 기준일' 없음", async () => {
    // POC6-27 — 차트는 「시장 흐름」 안으로 옮겼다(사용자 결정 ①) · 이 부품은 나머지 지표만(차트 없음).
    render(<KospiHeadline market={todayMarket(STALE_T2)} morning={MORNING} />);
    const card = screen.getByLabelText("KOSPI 현재 위치");
    expect(within(card).getByTestId("tc-kospi-source").textContent).toBe(KRX_SOURCE);
    expect(card.textContent).not.toContain("마지막 자료 기준일");
    expect(within(card).getAllByText(new RegExp(KRX_SOURCE.replace(/[()]/g, "\\$&")))).toHaveLength(1);
    // 설계자 RESULT 재판정 V3 D4(2026-11-13) — 펼친 칸의 '기존 시장 판정 참고'(KODEX200 기준일 D)는 뺐다(당일 판정 ·
    // 판정 표와 중복). 이 카드에는 KODEX200 날짜가 없다.
    fireEvent.click(within(card).getByRole("button", { name: "시장 수치와 거래량 펼치기" }));
    expect(card.textContent).not.toContain("KODEX200 기준일");
    expect(card.textContent).not.toContain("2026-09-21");
    expect(within(card).getByTestId("tc-kospi-detail").textContent).toContain("11/11 종가 기준");
    // 펼친 뒤에도 출처 줄은 카드 전체에 한 줄.
    expect(within(card).getAllByText(new RegExp(KRX_SOURCE.replace(/[()]/g, "\\$&")))).toHaveLength(1);
  });

  it("KOSPI 저장 종가가 없으면 날짜를 내지 않는다 — KODEX200 날짜로 대신하지 않음", async () => {
    const none = morningOk({
      kospi_detail: { status: "unavailable", as_of_date: null, r20: null, r60: null, return_1y_pct: null, high_52w_gap_pct: null, reason: "저장된 코스피 공식 종가 없음" },
    });
    render(
      <KospiHeadline
        market={todayMarket({ status: "unavailable", as_of_date: null, display_state: "no_result" })}
        morning={{ phase: "success", data: none, stale: false }}
      />,
    );
    const card = screen.getByLabelText("KOSPI 현재 위치");
    // UI-03 — '없다' 확인은 접힌 칸을 편 뒤에도 본다(판정 §3).
    for (const step of ["접힘", "펼침"]) {
      if (step === "펼침") {
        fireEvent.click(within(card).getByRole("button", { name: "시장 수치와 거래량 펼치기" }));
        expect(within(card).getByTestId("tc-kospi-detail").textContent).toBe("코스피 수익률·위치코스피 수익률 확인 불가 — 저장된 코스피 공식 종가 없음");
      }
      expect(card.textContent).not.toMatch(/마지막 자료 기준일|종가 기준|\d{1,2}\/\d{1,2}/);
      expect(within(card).getByText(KRX_SOURCE)).toHaveClass("tc-muted", "tc-small");
    }
  });
});

describe("설계자 RESULT STEP 4-2 — AI 복사 텍스트 출처", () => {
  function copyText(kospi: MarketContextKospi): string {
    return buildMarketDiscoveryCopyText({
      asof: "2026-09-29",
      filters: FILTERS,
      candidates: CANDIDATES,
      marketContext: ctxWith(kospi),
    });
  }

  it("KOSPI 값을 싣는 줄 끝에만 붙는다 · 값이 없는 상태 줄은 그대로", () => {
    const ok = copyText(OK).split("\n");
    expect(ok).toContain(`- KOSPI 보조 기준: 20거래일 +1.20%, 60거래일 +3.40% · ${KRX_SOURCE}`);
    expect(ok.filter((l) => l.includes(KRX_SOURCE))).toHaveLength(1);
    const stale = copyText(STALE_T2).split("\n");
    expect(stale).toContain(`- KOSPI 보조 기준: ${STALE_TEXT}`);
    expect(stale.join("\n")).not.toContain("한국거래소");
  });
});

describe("설계자 RESULT STEP 4 · PLAN STEP 7-4 — 정비 큐 KOSPI 항목(VIX 지연과 같은 모양)", () => {
  const IDLE = { phase: "idle" } as const;

  function topn(
    ctx: MarketContext | null,
    extra: Record<string, unknown> = {},
  ): QueryState<MarketTopNResponse> {
    return {
      phase: "success",
      stale: false,
      // POC6-16 — 실제 응답처럼 status 를 둔다(정상이 아니면 KOSPI 항목은 '상태 모름'으로 분류).
      data: { status: "ok", asof: "2026-09-29", market_context: ctx, ...extra },
    } as unknown as QueryState<MarketTopNResponse>;
  }

  function items(market: QueryState<MarketTopNResponse>) {
    return collectMaintenance(IDLE, IDLE, IDLE, market);
  }

  it("기준일 지연: 사유 문장 + 기준 줄 · ⓘ 는 카드와 같은 상태 한 줄", () => {
    expect(items(topn(ctxWith(STALE_T2)))).toEqual([
      {
        task: "market_refresh",
        text: "KOSPI 원자료가 최근 거래일까지 갱신되지 않았습니다 (KOSPI 기준일 2026-09-28 · 1거래일 지연)",
        kind: "heavy",
        target: "today_check",
        actionLabel: "최신 자료 갱신",
        source: "kospi",
        reason: STALE_TEXT,
      },
    ]);
  });

  it.each([
    [
      "자료원 확인 실패",
      { ...STALE_T2, display_state: "source_failed" as const },
      "KOSPI 원자료를 불러오지 못했습니다 (KOSPI 기준일 2026-09-28 · 1거래일 지연)",
    ],
    [
      "수집 결과 없음",
      { status: "unavailable" as const, as_of_date: null, display_state: "no_result" as const },
      "저장된 KOSPI 자료가 없습니다",
    ],
    [
      "아직 평가되지 않음",
      { status: "unavailable" as const, as_of_date: null, display_state: "not_evaluated" as const },
      "KOSPI 최신성 판정이 아직 실행되지 않았습니다",
    ],
  ])("%s: 항목 하나", (_label, kospi, text) => {
    const got = items(topn(ctxWith(kospi)));
    expect(got.map((it) => it.text)).toEqual([text]);
    expect(got[0].reason).toBe(kospiStatusText(kospi));
  });

  it("응답에 시장 배경(KOSPI)이 없으면 카드와 같이 '자료원 확인 실패' 항목", () => {
    expect(items(topn(null)).map((it) => it.text)).toEqual(["KOSPI 원자료를 불러오지 못했습니다"]);
  });

  it("정상 · 휴장일 · 시장 응답 전/실패에는 항목이 없다", () => {
    expect(items(topn(ctxWith(OK)))).toEqual([]);
    const holiday = { ...OK, display_state: "holiday" as const, today_is_trading_day: false };
    expect(items(topn(ctxWith(holiday)))).toEqual([]);
    expect(items({ phase: "loading" })).toEqual([]);
    expect(items({ phase: "error" })).toEqual([]);
  });

  it("VIX 지연 항목과 같은 종류 · 이동 화면 · 버튼 문구", () => {
    const got = items(
      topn(ctxWith(STALE_T2), {
        market_risk_reference: {
          kodex200: { availability: "available", as_of_date: "2026-09-29" },
          vix: {
            availability: "available",
            as_of_date: "2026-09-20",
            // POC5-12 — 서버 판정(vix_freshness 실제 계산값)
            freshness: { state: "update_check", compare_date: "2026-09-29", weekdays_behind: 7 },
          },
        },
      }),
    );
    expect(got).toHaveLength(2);
    const [vix, kospi] = got;
    expect(vix.text).toBe("VIX 자료 업데이트 확인 필요(기준일 2026-09-20)");
    expect(kospi.text).toContain("KOSPI");
    expect({ kind: kospi.kind, target: kospi.target, actionLabel: kospi.actionLabel }).toEqual({
      kind: vix.kind,
      target: vix.target,
      actionLabel: vix.actionLabel,
    });
  });
});
