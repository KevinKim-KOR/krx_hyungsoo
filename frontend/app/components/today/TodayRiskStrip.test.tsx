// POC5-13 · POC5-15 — 「오늘의 투자 점검」 보유 현재 상태 · 하락 구간 요약.
// POC6-27(설계 §4 · PLAN 판정 §4) — 자리는 「지금 확인할 내용」의 「보유 점검」 카드(배지 · 결론 · 기준 줄 · [?]).
//   시장 배지 = §3 과 같은 KODEX 200 판정값(하락장 → '시장 약세') · 보유 배지 = 기존 보유 하락 구간 판정.
//   상태 문장 · 시장 국면 일수 · 구간 판정 가능 건수처럼 검산하는 내용은 [?] 안. 판정은 「확인 근거」와 같은
//   공통 함수(riskStateFromQueries) 그대로 · 실패면 실제 실패 사유 한 문장 · 빈 보유면 대상 없음.
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { QueryState } from "@/lib/api/queryCache";
import type {
  EnrichedHoldingsResult,
  HoldingsDeclineBand,
  HoldingsMarketEvidenceItem,
  HoldingsMarketEvidenceResponse,
  MarketTopNResponse,
} from "@/lib/api";
import JudgmentQueueSection from "./JudgmentQueueSection";
import { HoldingsCheckCard } from "./CheckCards";
import { fmtShare } from "../holdings_risk_evidence/declineSummary";
import {
  HELP_BAND_BASIS,
  HELP_PARTIAL_EVAL,
  HELP_PARTIAL_JUDGE,
  HELP_SHARE_UNAVAILABLE,
  riskStateFromQueries,
} from "../holdings_risk_evidence/riskCombination";

function marketWith(regime_code: string | null, regime_label: string | null): QueryState<MarketTopNResponse> {
  return {
    phase: "success",
    stale: false,
    data: {
      status: "ok",
      market_context: regime_code ? { status: "ok", asof: "2026-10-14", regime_code, regime_label } : null,
    } as unknown as MarketTopNResponse,
  };
}
const MARKET_BEAR = marketWith("bear", "하락장");

function holdingsOf(rows: [string, string, number | null][], stale = false): QueryState<EnrichedHoldingsResult> {
  return {
    phase: "success",
    stale,
    data: {
      items: rows.map(([ticker, name, ev]) => ({
        ticker, name, eval_amount: ev, invested_amount: 1000, price_missing: ev === null, calc_missing: ev === null,
      })),
    } as unknown as EnrichedHoldingsResult,
  };
}
// 가 두 계좌(3000 + 1000) · 나 2000 · 다 3000 · 라 1000 → 가 40% · 나 20% · 다 30% · 라 10%.
const HOLDINGS = holdingsOf([
  ["A1", "가", 3000], ["A1", "가", 1000], ["B2", "나", 2000], ["C3", "다", 3000], ["D4", "라", 1000],
]);

const band = (state: HoldingsDeclineBand["state"], reason: HoldingsDeclineBand["unjudged_reason"] = null) =>
  ({ judgeable: reason === null, state, label: state ? `PC ${state}` : null, return_20d_pct_1dp: null, unjudged_reason: reason }) as HoldingsDeclineBand;
function item(ticker: string, decline: HoldingsDeclineBand): HoldingsMarketEvidenceItem {
  return {
    ticker,
    holding: { evaluation_amount: 555_555 }, // 근거 응답 평가금액 — 쓰지 않음
    short_term_momentum: { status: "ok", return_5d_pct: -1, return_20d_pct: -3, excess_vs_kodex200_20d_pctp: 0 },
    evidence_notes: [],
    decline_band: decline,
  } as unknown as HoldingsMarketEvidenceItem;
}
const top = (ticker: string, name: string, r5: number) => ({
  ticker, name, eval_amount: 0, market_weight_pct: 1, pnl_rate_pct: 1,
  return_5d_pct: r5, return_20d_pct: -1, excess_vs_kodex200_20d_pctp: 0,
});
const BEAR = { available: true, regime_code: "bear", regime_label: "하락장", regime_streak_days: 4, regime_streak_at_least: false };
function evidenceOf(
  items: HoldingsMarketEvidenceItem[],
  mp: Record<string, unknown> = BEAR,
  stale = false,
): QueryState<HoldingsMarketEvidenceResponse> {
  return {
    phase: "success",
    stale,
    data: {
      status: "ok",
      asof: "2026-10-14",
      summary: { total_holdings_count: 5 },
      holdings: items,
      judgment_summary: {
        market_position: mp,
        holdings: {
          available: true,
          top_holdings: [top("C3", "다", -3), top("A1", "가", -2), top("B2", "나", -1)],
          coverage: { total: 4, need_check: 1, ok: 3 },
        },
        data_status: {},
      },
      price_basis: {
        reference_date: "2026-10-14", reference_ticker: "069500",
        kodex200_start_date_5d: "2026-10-07", kodex200_start_date_20d: "2026-09-15", date_mismatch: [],
      },
      warnings: [],
    } as unknown as HoldingsMarketEvidenceResponse,
  };
}
// 가 10% 이상 · 나 5~8% · 다 구간 밖 · 라 판정 안 함(기준일 다름) → 하락 있음 2종목 · 판정 가능 3/4.
const ITEMS = [
  item("A1", band("D10_PLUS")), item("A1", band("D10_PLUS")), item("B2", band("D5_8")),
  item("C3", band(null)), item("D4", band(null, "date_mismatch")),
];
const ALL_JUDGED = [
  item("A1", band("D10_PLUS")), item("A1", band("D10_PLUS")), item("B2", band("D5_8")),
  item("C3", band(null)), item("D4", band(null)),
];
const NONE = ALL_JUDGED.map((it) => ({ ...it, decline_band: band(null) }));
const ERR = { phase: "error" } as const;

function renderCard(
  h: QueryState<EnrichedHoldingsResult> = HOLDINGS,
  ev: QueryState<HoldingsMarketEvidenceResponse> = evidenceOf(ALL_JUDGED),
  market: QueryState<MarketTopNResponse> = MARKET_BEAR,
) {
  return render(
    <HoldingsCheckCard market={market} holdings={h} evidence={ev} onNavigate={() => undefined} onDetail={() => undefined} />,
  );
}
const card = () => screen.getByTestId("tc-risk-strip");
const badges = () => Array.from(card().querySelectorAll(".tc-check-badges .tc-sum-badge")).map((b) => b.textContent);
const main = () => card().querySelector(".tc-check-main")?.textContent ?? "";
const openHelp = () => {
  fireEvent.click(screen.getByRole("button", { name: "현재 상태 도움말" }));
  return screen.getByRole("dialog", { name: "현재 상태 도움말" }).textContent ?? "";
};

describe("오늘 — 「보유 점검」 카드 (POC5-15 판정 그대로 · POC6-27 배치)", () => {
  it("배지(시장 · 보유) → 'N종목 중 M종목 하락 구간' → 기준 · 해당 비중(현금 제외)", () => {
    renderCard();
    expect(badges()).toEqual(["시장 약세", "보유 약세"]);
    expect(main()).toBe("4종목 중 2종목 하락 구간");
    expect(card().textContent).toContain(
      "최근 20일 저장 종가 기준(약 5% 이상 하락) · 해당 보유 비중 60.0%(현금 제외 · 같은 종목 계좌 합산)",
    );
    expect(card().textContent).not.toMatch(/위험|하락 신호|경보|555/);
  });

  it("「확인 근거」와 같은 공통 판정 함수 · 같은 수 · 상태 문장은 [?] 안", () => {
    renderCard(HOLDINGS, evidenceOf(ITEMS));
    const v = riskStateFromQueries(HOLDINGS, evidenceOf(ITEMS))!;
    expect(main()).toBe(`${v.summary!.total}종목 중 ${v.summary!.inBand}종목 하락 구간`);
    expect(card().textContent).toContain(`해당 보유 비중 ${fmtShare(v.summary!.inBandShare)}`);
    const help = openHelp();
    expect(help).toContain(`지금 상태: ${v.combo.text}`);
    expect(help).toContain("시장 국면(보유 근거 기준 · [요약 다시 읽기] 때 다시 계산): 하락장 · 4거래일째");
    expect(help).toContain("구간 판정 가능 3/4종목 · 일부 종목 판정 불가");
  });

  it("일부 종목 판정 불가는 기본 화면에 보이고 · ? 안에 그 제한 문단이 있다", () => {
    renderCard(HOLDINGS, evidenceOf(ITEMS));
    expect(card().textContent).toContain("일부 종목 판정 불가");
    const help = openHelp();
    expect(help).toContain(HELP_PARTIAL_JUDGE);
    expect(help).toContain(HELP_BAND_BASIS);
    expect(help).not.toContain(HELP_PARTIAL_EVAL);
  });

  it("일부 평가 미확인은 비중 뒤에 기본 화면으로 · ? 안에 평가 부족 문단", () => {
    renderCard(
      holdingsOf([["A1", "가", 3000], ["A1", "가", 1000], ["B2", "나", null], ["C3", "다", 3000], ["D4", "라", 1000]]),
      evidenceOf(ALL_JUDGED),
    );
    expect(card().textContent).toContain("해당 보유 비중 50.0%(현금 제외 · 같은 종목 계좌 합산) · 확인된 평가금액 기준 · 일부 평가 자료 미확인");
    expect(openHelp()).toContain(HELP_PARTIAL_EVAL);
  });

  it("평가금액이 모두 없으면 비중 '확인 불가' · ? 는 '비중 확인 불가'를 말하고 '계산했다'고 하지 않는다", () => {
    renderCard(holdingsOf([["A1", "가", null], ["B2", "나", null], ["C3", "다", null], ["D4", "라", null]]), evidenceOf(ALL_JUDGED));
    expect(badges()).toEqual(["시장 약세", "보유 약세"]);
    expect(card().textContent).toContain("해당 보유 비중 확인 불가");
    const help = openHelp();
    expect(help).toContain(HELP_SHARE_UNAVAILABLE);
    expect(help).not.toContain(HELP_PARTIAL_EVAL);
  });

  it("시장 배지는 §3 의 KODEX 200 판정값(보합장 · 판정 없음) · 하락 없음 = '보유 하락 구간 없음'('하락 신호' 금지)", () => {
    renderCard(HOLDINGS, evidenceOf(NONE, { ...BEAR, regime_code: "neutral", regime_label: "보합장", regime_streak_days: 3 }), marketWith("neutral", "보합장"));
    expect(badges()).toEqual(["시장 보합장", "보유 하락 구간 없음"]);
    expect(main()).toBe("4종목 중 0종목 하락 구간");
    expect(card().textContent).not.toMatch(/위험|하락 신호|경보|안전|정상/);
  });

  it("시장 판정 응답이 없으면 '시장 판정 확인 불가'(다른 응답 값으로 대신하지 않음)", () => {
    renderCard(HOLDINGS, evidenceOf(ALL_JUDGED), ERR as QueryState<MarketTopNResponse>);
    expect(badges()[0]).toBe("시장 판정 확인 불가");
  });

  it.each([
    ["근거 실패", HOLDINGS, ERR, "확인 근거를 불러오지 못했습니다."],
    ["보유 실패(시장 하락)", ERR, evidenceOf(ALL_JUDGED), "보유 자료를 불러오지 못했습니다."],
    ["둘 다 실패", ERR, ERR, "보유 자료와 확인 근거를 불러오지 못했습니다."],
  ] as const)("판정 Q1 — %s: 실제 실패 사유 한 문장만(없는 수치 자리 없음)", (_, h, e, reason) => {
    renderCard(h as QueryState<EnrichedHoldingsResult>, e as QueryState<HoldingsMarketEvidenceResponse>);
    expect(screen.getByTestId("tc-risk-failed").textContent).toBe(reason);
    expect(card().textContent).not.toMatch(/\d+종목 중|0\/0/);
  });

  it("정상 응답의 빈 보유는 근거가 실패해도 대상 없음만", () => {
    renderCard(holdingsOf([]), ERR as QueryState<HoldingsMarketEvidenceResponse>);
    expect(badges()[1]).toBe("보유 없음");
    expect(main()).toBe("판정할 보유 종목이 없습니다");
    expect(screen.queryByTestId("tc-risk-failed")).toBeNull();
    expect(riskStateFromQueries(holdingsOf([]), evidenceOf([]))!.combo.text).toBe("보유 판정 대상 없음");
  });

  it("받는 중이면 판정 문장 · 배지가 없다(불러오는 중 안내만)", () => {
    const { unmount } = renderCard({ phase: "loading" }, evidenceOf(ALL_JUDGED));
    expect(card().textContent).toContain("불러오는 중");
    expect(badges()).toHaveLength(1); // 시장 배지만
    expect(card().querySelector(".tc-check-main")).toBeNull();
    unmount();
    renderCard(HOLDINGS, { phase: "loading" });
    expect(card().querySelector(".tc-check-main")).toBeNull();
  });

  it("다시 읽기 실패(stale)여도 받은 자료로 그대로 분류 · 그 사실과 시각을 적는다", () => {
    renderCard(
      holdingsOf([["A1", "가", 3000], ["A1", "가", 1000], ["B2", "나", 2000], ["C3", "다", 3000], ["D4", "라", 1000]], true),
      evidenceOf(ALL_JUDGED, BEAR, true),
    );
    expect(badges()).toEqual(["시장 약세", "보유 약세"]);
    expect(screen.queryByTestId("tc-risk-failed")).toBeNull();
    expect(card().textContent).toContain("보유: 다시 읽기 실패");
  });

  it("? 를 열고 닫아도 카드 그대로 · 아래 「보유 자세히」 최대 3개는 같은 응답 순서", () => {
    renderCard();
    const help = openHelp();
    expect(help).toContain("시장 국면이 각 종목 하락의 원인이라는 뜻은 아닙니다");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    render(<JudgmentQueueSection market={ERR as QueryState<MarketTopNResponse>} holdings={HOLDINGS} evidence={evidenceOf(ALL_JUDGED)} onNavigate={() => undefined} />);
    const names = screen.getAllByTestId("tc-top-row").map((r) => r.textContent ?? "");
    expect(names).toHaveLength(3);
    expect(names[0]).toContain("다");
    expect(names[1]).toContain("가");
    expect(names[2]).toContain("나");
  });
});
