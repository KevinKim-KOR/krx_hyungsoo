// POC5-13 · POC5-15 — 「오늘의 투자 점검」 보유 현재 상태 · 하락 구간 요약.
// POC6-27(설계 §4 · PLAN 판정 §4) — 자리는 「지금 확인할 내용」의 「보유 점검」 카드(배지 · 결론 · 기준 줄 · [?]).
// POC6-29(설계 §2 · PLAN §3-2 · 판정 Q10) — 판정 출처를 「보유」와 같은 요약 응답(price_flow · 같은 함수 · 종목 단위)으로
//   바꾸고 「보유 자세히」를 합쳤다. 이 파일은 새 카드 계약을 본다:
//   - 같은 종목 여러 계좌 = 한 종목 · 판정 가능 수와 하락 수를 따로 · 판정 못 한 보유는 '하락 아님'으로 세지 않음.
//   - 요약 · 보유 조회 실패는 실패 문장(0종목 위장 없음) · 받는 중이면 판정 문장 없음 · 빈 보유는 대상 없음.
//   - 비중 = 종목 합산 · 일부 계좌만 확인되면 그 범위 · 시장 배지는 시장 판정 응답 값.
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { QueryState } from "@/lib/api/queryCache";
import type { EnrichedHoldingsResult, MarketTopNResponse } from "@/lib/api";
import type { CompareSummary } from "@/lib/api/etfCompare";
import { flow, link, summaryOk } from "@/lib/etfCompareTestFixtures";
import { HoldingsCheckCard, countHoldings } from "./CheckCards";

function marketWith(regime_code: string | null, regime_label: string | null): QueryState<MarketTopNResponse> {
  return {
    phase: "success",
    stale: false,
    successAt: 0,
    reload: () => undefined,
    reloadAsync: async () => null,
    data: (regime_code
      ? { status: "ok", market_context: { regime_code, regime_label } }
      : { status: "ok", market_context: null }) as unknown as MarketTopNResponse,
  } as unknown as QueryState<MarketTopNResponse>;
}

function ok<T>(data: T): QueryState<T> {
  return { phase: "success", stale: false, successAt: 0, data, reload: () => undefined, reloadAsync: async () => data } as unknown as QueryState<T>;
}
const LOADING = { phase: "loading", reload: () => undefined, reloadAsync: async () => null } as unknown as QueryState<never>;
const ERR = { phase: "error", reload: () => undefined, reloadAsync: async () => null } as unknown as QueryState<never>;

const declined = (r20: number) =>
  flow({
    return_20d_pct: r20,
    decline_band: { judgeable: true, state: "drawdown_10", label: "PC 20저장일 하락 10% 이상", return_20d_pct_1dp: r20, unjudged_reason: null },
  });
const notDeclined = flow({ return_20d_pct: 1, decline_band: { judgeable: true, state: null, label: null, return_20d_pct_1dp: 1, unjudged_reason: null } });
const unjudged = flow({
  decline_band: { judgeable: false, state: null, label: null, return_20d_pct_1dp: null, unjudged_reason: "date_mismatch" },
});

function summaryWith(items: ReturnType<typeof link>[]) {
  return summaryOk({ holdings: { status: "ok", items } });
}

function hold(rows: { ticker: string; weight?: number | null }[]): EnrichedHoldingsResult {
  return {
    items: rows.map((r) => ({ ticker: r.ticker, name: r.ticker, market_weight_pct: r.weight ?? null, price_missing: false })),
  } as unknown as EnrichedHoldingsResult;
}

function renderCard(summary: QueryState<CompareSummary>, holdings: QueryState<EnrichedHoldingsResult>, market = marketWith("bear", "하락장")) {
  render(<HoldingsCheckCard market={market} summary={summary} holdings={holdings} onNavigate={() => undefined} />);
  return screen.getByTestId("tc-risk-strip");
}

describe("오늘 — 「보유 점검」 카드(POC6-29 · 「보유」와 같은 판정 · 종목 단위)", () => {
  it("같은 종목 두 계좌 = 한 종목 · '보유 N종목 중 M종목 하락 · 판정 K종목' · 비중 = 하락 종목 합산", () => {
    const s = summaryWith([
      link({ ticker: "A1", price_flow: declined(-12) }),
      link({ ticker: "B1", price_flow: notDeclined }),
    ]);
    const card = renderCard(ok(s), ok(hold([{ ticker: "A1", weight: 10 }, { ticker: "A1", weight: 15 }, { ticker: "B1", weight: 75 }])));
    expect(within(card).getByTestId("tc-hold-count").textContent).toBe("보유 2종목 중 1종목 하락 · 판정 2종목");
    expect(within(card).getByTestId("tc-hold-basis").textContent).toContain("해당 보유 비중 25.00%(현금 제외 · 같은 종목 계좌 합산)");
    expect(card.textContent).toContain("시장 약세");
    expect(card.textContent).toContain("보유 약세");
  });

  it("판정 못 한 보유는 '하락 아님'으로 세지 않는다 — 판정 수를 따로 · '보유 판정 불완전'", () => {
    const s = summaryWith([link({ ticker: "A1", price_flow: notDeclined }), link({ ticker: "B1", price_flow: unjudged })]);
    const card = renderCard(ok(s), ok(hold([{ ticker: "A1", weight: 50 }, { ticker: "B1", weight: 50 }])));
    expect(within(card).getByTestId("tc-hold-count").textContent).toBe("보유 2종목 중 0종목 하락 · 판정 1종목");
    expect(within(card).getByTestId("tc-hold-basis").textContent).toContain("판정 못 한 보유 1종목은 세지 않음");
    expect(card.textContent).toContain("보유 판정 불완전");
    expect(card.textContent).not.toContain("보유 하락 구간 없음");
  });

  it("하나도 판정하지 못했으면 '0종목 하락' · '비중 0%'가 아니라 셀 수 없음(「보유」의 '—'와 같은 뜻)", () => {
    const s = summaryWith([link({ ticker: "A1", price_flow: unjudged }), link({ ticker: "B1", price_flow: null })]);
    const card = renderCard(ok(s), ok(hold([{ ticker: "A1", weight: 40 }, { ticker: "B1", weight: 60 }])));
    expect(within(card).getByTestId("tc-hold-count").textContent).toBe("보유 2종목 · 하락 판정을 하지 못했습니다(판정 0종목)");
    const basis = within(card).getByTestId("tc-hold-basis").textContent ?? "";
    expect(basis).toContain("해당 보유 비중 셀 수 없음");
    expect(basis).not.toContain("0%");
    expect(card.textContent).toContain("보유 판정 불완전");
  });

  it("요약에 없는 보유 · 가격 흐름 없음(null)도 판정 못 함으로", () => {
    const s = summaryWith([link({ ticker: "A1", price_flow: null })]);
    const c = countHoldings(s, hold([{ ticker: "A1" }, { ticker: "Z9" }]).items);
    expect(c?.total).toBe(2);
    expect(c?.judged).toBe(0);
    expect(c?.decline).toHaveLength(0);
  });

  it("모두 판정했고 하락이 없으면 '보유 하락 구간 없음' · 비중 0%", () => {
    const s = summaryWith([link({ ticker: "A1", price_flow: notDeclined })]);
    const card = renderCard(ok(s), ok(hold([{ ticker: "A1", weight: 100 }])), marketWith("neutral", "보합장"));
    expect(within(card).getByTestId("tc-hold-count").textContent).toBe("보유 1종목 중 0종목 하락 · 판정 1종목");
    expect(card.textContent).toContain("보유 하락 구간 없음");
    expect(card.textContent).toContain("해당 보유 비중 0%");
    expect(card.textContent).toContain("시장 보합장");
  });

  it("하락 종목의 비중이 일부 계좌만 확인되면 그 범위를 적는다 · 모두 없으면 '확인 불가'", () => {
    const s = summaryWith([link({ ticker: "A1", price_flow: declined(-12) }), link({ ticker: "B1", price_flow: declined(-11) })]);
    const card = renderCard(ok(s), ok(hold([{ ticker: "A1", weight: 10 }, { ticker: "B1", weight: null }])));
    expect(within(card).getByTestId("tc-hold-basis").textContent).toContain("2종목 중 1종목만 확인");
  });

  it("요약 조회 실패 · 보유 조회 실패는 실패 문장(숫자 없음) · 받는 중이면 판정 문장 없음", () => {
    const a = renderCard(ERR as QueryState<CompareSummary>, ok(hold([{ ticker: "A1" }])));
    expect(within(a).getByTestId("tc-risk-failed").textContent).toBe("보유 하락 판정 자료를 불러오지 못했습니다.");
    expect(within(a).queryByTestId("tc-hold-count")).toBeNull();
  });

  it("보유 조회 실패 = '보유 자료를 불러오지 못했습니다.'", () => {
    const card = renderCard(ok(summaryOk()), ERR as QueryState<EnrichedHoldingsResult>);
    expect(within(card).getByTestId("tc-risk-failed").textContent).toBe("보유 자료를 불러오지 못했습니다.");
  });

  it("받는 중 = 판정 문장 · 보유 배지 없음", () => {
    const card = renderCard(LOADING as QueryState<CompareSummary>, ok(hold([{ ticker: "A1" }])));
    expect(card.textContent).toContain("불러오는 중");
    expect(within(card).queryByTestId("tc-hold-count")).toBeNull();
  });

  it("빈 보유 = 대상 없음 · 시장 판정 응답이 없으면 '시장 판정 확인 불가'", () => {
    const card = renderCard(ok(summaryWith([])), ok(hold([])), marketWith(null, null));
    expect(card.textContent).toContain("판정할 보유 종목이 없습니다");
    expect(card.textContent).toContain("시장 판정 확인 불가");
  });

  it("요약이 보유를 읽지 못했으면(holdings.status ≠ ok) 실패로 · 0종목으로 바꾸지 않는다", () => {
    const card = renderCard(ok(summaryOk({ holdings: { status: "error", items: [] } })), ok(hold([{ ticker: "A1" }])));
    expect(within(card).getByTestId("tc-risk-failed").textContent).toBe("보유 하락 판정 자료가 보유를 읽지 못했습니다.");
  });
});
