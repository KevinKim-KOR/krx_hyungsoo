// POC5-22 Q3 (a) — 「보유와 비교」 카드의 KODEX200 칸 = 기존 단기 20구간 값(정렬 · 보유 카드와 같은 지표).
// 후보 카드가 1개월 excess_return 을 '20일'이라는 이름으로 보이던 연결을 바로잡았다. 1/3개월 동일 기간 값은 넣지 않는다.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import type { MarketCandidate } from "@/lib/api";
import { CandidateCompareCards } from "./CompareCards";

function cand(over: Partial<MarketCandidate> = {}): MarketCandidate {
  return {
    rank: 1,
    ticker: "0005D0",
    name: "SOL 전고체배터리&실리콘음극재",
    returns: { one_month: { return_pct: 22.27 } },
    excess_return: { vs_kodex200_1m_pctp: 37.33, vs_kodex200_3m_pctp: 47.02 },
    same_period_kodex200: {
      one_month: {
        status: "ok",
        start_date: "2026-09-14",
        end_date: "2026-10-14",
        candidate_return_pct: 22.2689,
        kodex200_return_pct: -9.8615,
        diff_pctp: 32.1304,
      },
    },
    short_term_momentum: { status: "ok", excess_vs_kodex200_20d_pctp: 28.04 },
    ...over,
  } as MarketCandidate;
}

function exCell(): HTMLElement {
  return screen.getByText("20구간 KODEX200 차이").parentElement!;
}

describe("보유와 비교 — 후보 카드 20구간 KODEX200 차이", () => {
  it("단기 20구간 값 · %p · 1개월 값(기간 다름 · 동일 기간)은 넣지 않는다", () => {
    render(
      <CandidateCompareCards rows={[cand()]} basis="one_month" exposureByTicker={{}} selectedTicker={null} onSelect={() => undefined} />,
    );
    expect(exCell().textContent).toBe("20구간 KODEX200 차이+28.04%p");
    expect(screen.queryByText("20일 KODEX 초과")).toBeNull();
    const all = document.body.textContent ?? "";
    expect(all).not.toContain("37.33");
    expect(all).not.toContain("32.13");
  });

  it("단기 값이 없으면 결측 표기(1개월 값으로 채우지 않음)", () => {
    render(
      <CandidateCompareCards
        rows={[cand({ short_term_momentum: { status: "unavailable" } })]}
        basis="one_month"
        exposureByTicker={{}}
        selectedTicker={null}
        onSelect={() => undefined}
      />,
    );
    expect(exCell().textContent).toBe("20구간 KODEX200 차이-");
  });
});
