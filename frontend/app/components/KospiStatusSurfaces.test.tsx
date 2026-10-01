// POC3-02D-OPS-03 확정 계약 9 ⑥ · PLAN STEP 5-5 — KOSPI 를 보여 주는 나머지 자리도 카드와
// **같은 판정 · 같은 문구**를 쓰는지 본다.
//   - 코스피 차트: 부모가 넘긴 topn KOSPI 필드로 같은 배지 · 기준 줄(추가 조회 없음 · KS-1).
//   - AI 복사 텍스트 · AI 세션 스냅샷: 'N/A' 대신 같은 상태 문장.
// 설계자 RESULT STEP 4 (2026-09-30) — 제목에서 'KS11' 제거 · 공식 자료원 한 줄 ·
// 「오늘의 투자 점검」 KOSPI 카드 '마지막 자료 기준일' = KOSPI 기준일 · 정비 큐 KOSPI 항목.
// 외부 호출 0 — `@/lib/api` 는 대역.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import type {
  MarketCandidate,
  MarketContext,
  MarketContextKospi,
  MarketTopNFilters,
  MarketTopNResponse,
} from "@/lib/api";
import { __resetQueryCache, type QueryState } from "@/lib/api/queryCache";

const fetchBenchmarkSeries = vi.fn();
vi.mock("@/lib/api", () => ({
  fetchBenchmarkSeries: (...a: unknown[]) => fetchBenchmarkSeries(...a),
}));

import KospiChart from "./today/KospiChart";
import KospiHeadline from "./today/KospiHeadline";
import MarketContextCard from "./MarketContextCard";
import TransferToAISessionsCard from "./TransferToAISessionsCard";
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

describe("코스피 차트 — 카드와 같은 배지 · 기준 줄", () => {
  it("기준일 지연: 같은 배지 · 같은 기준 줄 · 선은 경고색", async () => {
    const { container } = render(<KospiChart kospi={STALE_T2} phase="success" />);
    await screen.findByText(/최근 2거래일/);
    const box = container.querySelector("[data-kospi-chart-state]");
    expect(box?.getAttribute("data-kospi-chart-state")).toBe("stale");
    expect(screen.getByText("기준일 지연")).toHaveClass("kospi-badge", "warn");
    expect(box?.textContent).toContain("KOSPI 기준일 2026-09-28 · 1거래일 지연");
    expect(container.querySelector("path")?.getAttribute("stroke")).toBe("var(--warn)");
    // 가격 흐름 조회는 차트 자기 것 1회뿐 — 판정은 부모가 넘긴 값(추가 호출 없음).
    expect(fetchBenchmarkSeries).toHaveBeenCalledTimes(1);
  });

  it("정상: 배지 · 상태 줄 없음 · 선은 기본색", async () => {
    const { container } = render(<KospiChart kospi={OK} phase="success" />);
    await screen.findByText(/최근 2거래일/);
    expect(container.querySelector("[data-kospi-chart-state]")).toBeNull();
    expect(container.querySelector(".kospi-badge")).toBeNull();
    expect(container.querySelector("path")?.getAttribute("stroke")).toBe("var(--accent)");
  });

  it("자료원 확인 실패 · 휴장일도 같은 생성기 문구", async () => {
    const { unmount } = render(
      <KospiChart kospi={{ ...STALE_T2, display_state: "source_failed" }} phase="success" />,
    );
    await screen.findByText(/최근 2거래일/);
    expect(screen.getByText("자료원 확인 실패")).toHaveClass("kospi-badge", "warn");
    unmount();
    __resetQueryCache();
    const holiday = { ...OK, display_state: "holiday" as const, today_is_trading_day: false };
    const r = render(<KospiChart kospi={holiday} phase="success" />);
    await screen.findByText(/최근 2거래일/);
    expect(screen.getByText("휴장일")).toHaveClass("kospi-badge", "neutral");
    expect(r.container.querySelector("path")?.getAttribute("stroke")).toBe("var(--accent)");
  });

  it("KOSPI 판정을 불러오는 중이면 배지를 달지 않는다", async () => {
    const { container } = render(<KospiChart kospi={null} phase="loading" />);
    await screen.findByText(/최근 2거래일/);
    expect(container.querySelector("[data-kospi-chart-state]")).toBeNull();
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

  it("AI Sessions 로 넘기기: 저장 draft 의 스냅샷 · 질문 문구가 같은 문장", () => {
    render(
      <TransferToAISessionsCard
        asof="2026-09-29"
        filters={FILTERS}
        candidates={CANDIDATES}
        linkedMarketRefreshId={null}
        marketContext={ctxWith(STALE_T2)}
      />,
    );
    fireEvent.click(screen.getByText("AI Sessions로 넘기기"));
    const draft = loadAISessionsDraft();
    const kospi = (draft?.market_context_snapshot as { kospi: Record<string, unknown> }).kospi;
    expect(kospi.state_text).toBe(STALE_TEXT);
    expect(kospi.display_state).toBe("stale");
    expect(draft?.question_text).toContain(`- KOSPI 보조 기준: ${STALE_TEXT}`);
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
  it("마지막 자료 기준일 = KOSPI 기준일(KODEX200 날짜 아님) · 출처는 카드 전체에 한 줄", async () => {
    render(<KospiHeadline market={todayMarket(STALE_T2)} />);
    // 차트까지 그려진 뒤(차트에는 출처 줄을 따로 달지 않는다).
    await screen.findByText(/최근 2거래일/);
    const card = screen.getByLabelText("KOSPI 현재 위치");
    const foot = within(card).getByText(/마지막 자료 기준일/);
    expect(foot.textContent).toBe(`마지막 자료 기준일 2026-09-28 · ${KRX_SOURCE}`);
    expect(card.textContent).not.toContain("마지막 자료 기준일 2026-09-21");
    expect(within(card).getAllByText(new RegExp(KRX_SOURCE.replace(/[()]/g, "\\$&")))).toHaveLength(1);
    // KODEX200 기준일은 기존 시장 판정 줄에만 그대로 남는다.
    expect(within(card).getByText(/· 기준일 2026-09-21/)).toBeInTheDocument();
  });

  it("KOSPI 기준일이 없으면 날짜를 내지 않는다 — KODEX200 날짜로 대신하지 않음", async () => {
    render(
      <KospiHeadline
        market={todayMarket({ status: "unavailable", as_of_date: null, display_state: "no_result" })}
      />,
    );
    await screen.findByText(/최근 2거래일/);
    const card = screen.getByLabelText("KOSPI 현재 위치");
    expect(card.textContent).not.toContain("마지막 자료 기준일");
    expect(within(card).getByText(KRX_SOURCE)).toHaveClass("tc-muted", "tc-small");
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
      data: { asof: "2026-09-29", market_context: ctx, ...extra },
    } as unknown as QueryState<MarketTopNResponse>;
  }

  function items(market: QueryState<MarketTopNResponse>) {
    return collectMaintenance(IDLE, IDLE, IDLE, market);
  }

  it("기준일 지연: 사유 문장 + 기준 줄 · ⓘ 는 카드와 같은 상태 한 줄", () => {
    expect(items(topn(ctxWith(STALE_T2)))).toEqual([
      {
        text: "KOSPI 원자료가 최근 거래일까지 갱신되지 않았습니다 (KOSPI 기준일 2026-09-28 · 1거래일 지연)",
        kind: "heavy",
        target: "market_discovery",
        actionLabel: "시장 자료 업데이트로",
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
          vix: { availability: "available", as_of_date: "2026-09-20" },
        },
      }),
    );
    expect(got).toHaveLength(2);
    const [vix, kospi] = got;
    expect(vix.text).toContain("시장 불안 지표가 오래되었습니다");
    expect(kospi.text).toContain("KOSPI");
    expect({ kind: kospi.kind, target: kospi.target, actionLabel: kospi.actionLabel }).toEqual({
      kind: vix.kind,
      target: vix.target,
      actionLabel: vix.actionLabel,
    });
  });
});
