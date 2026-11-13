// POC5-23 판정 §3 — 「보유와 비교」 후보 칸 · 상세 최소 정정.
// 보유 노출 = 직접 보유만 확정(후보 ETF 티커 ↔ 주식 종목 티커 비교 판정 폐기) · '고점 대비'(폐기된 점수
// 스냅샷 값 · 종목별 날짜 없음) 미표시 · [세부 근거 펼치기] 글자색.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import type { MarketCandidate } from "@/lib/api";
import SelectedDetail from "./SelectedDetail";
import SelectedHoldingDetail from "./SelectedHoldingDetail";
import {
  type AggregatedHolding,
  computeExposure,
  exposureLabel,
  exposureSortRank,
} from "./helpers";

const HELD: AggregatedHolding[] = [
  {
    ticker: "111111",
    name: "보유 반도체 ETF",
    invested_amount: 100,
    eval_amount: 120,
    eval_partial_unavail: false,
    pnl_rate_pct: 20,
    market_weight_pct: 100,
    data_missing: false,
  } as AggregatedHolding,
];

describe("보유 노출 판정 — 직접 보유만", () => {
  it("같은 종목 코드면 직접 보유 · 아니면 구성종목 중복 미확인 · 보유 목록 상태는 따로", () => {
    expect(computeExposure("111111", HELD, true, false)).toEqual({
      kind: "direct",
      directHoldingTicker: "111111",
      directHoldingName: "보유 반도체 ETF",
    });
    const other = computeExposure("333333", HELD, true, false);
    expect(other.kind).toBe("overlap_unchecked");
    expect(exposureLabel(other)).toBe("구성종목 중복 미확인");
    expect(exposureLabel(computeExposure("333333", HELD, false, false))).toBe("보유 확인 전");
    expect(exposureLabel(computeExposure("111111", HELD, true, true))).toBe("보유 확인 불가");
    // '중복 없음' · '보유 ETF n개' 같은 확정 표현은 어떤 경우에도 나오지 않는다.
    const labels = [
      computeExposure("111111", HELD, true, false),
      other,
      computeExposure(null, [], true, false),
    ].map(exposureLabel);
    expect(labels.join(" ")).not.toMatch(/중복 없음|보유 ETF \d+개/);
    expect(exposureSortRank("direct")).toBeGreaterThan(exposureSortRank("overlap_unchecked"));
  });
});

describe("선택 후보 상세", () => {
  const cand = {
    rank: 1,
    ticker: "333333",
    name: "후보 장비 ETF",
    tags: [],
    drawdown_20d: -0.042,
    short_term_momentum: {
      status: "ok",
      return_5d_pct: 1,
      excess_vs_kodex200_5d_pctp: 2.5,
      excess_vs_kodex200_20d_pctp: -1.25,
    },
    data_quality: { status: "ok" },
  } as unknown as MarketCandidate;

  it("고점 대비를 보이지 않고 중복은 미확인 · 세부 근거 버튼 글자가 보인다", () => {
    render(
      <SelectedDetail
        candidate={cand}
        exposure={computeExposure("333333", HELD, true, false)}
        expanded={false}
        onToggleExpanded={() => {}}
        directHoldingEvidence={undefined}
      />,
    );
    expect(screen.queryByText(/고점 대비/)).not.toBeInTheDocument();
    expect(screen.queryByText(/-4\.20%/)).not.toBeInTheDocument();
    expect(screen.getByText(/구성종목 중복 미확인 — 아래 \[판단 근거 미리보기\]/)).toBeInTheDocument();
    expect(screen.getByText("없음")).toBeInTheDocument();
    // KODEX200 대비 차이 = %p(미리보기 · 카드와 같은 단위 · 검토 r1).
    expect(screen.getByText("5d: +2.50%p")).toBeInTheDocument();
    expect(screen.getByText("20d: -1.25%p")).toBeInTheDocument();
    const btn = screen.getByRole("button", { name: /세부 근거 펼치기/ });
    expect(btn.style.color).toBe("var(--fg)");
    expect(btn.style.backgroundColor).toBe("transparent");
  });

  it("직접 보유 후보는 그 이름을 보인다", () => {
    render(
      <SelectedDetail
        candidate={{ ...cand, ticker: "111111" } as MarketCandidate}
        exposure={computeExposure("111111", HELD, true, false)}
        expanded={false}
        onToggleExpanded={() => {}}
        directHoldingEvidence={undefined}
      />,
    );
    expect(screen.getByText("보유 반도체 ETF")).toBeInTheDocument();
  });
});

describe("선택 보유 상세", () => {
  it("KODEX 대비 5 · 10 · 20일 차이는 %p · 단기 흐름 변화율은 %", () => {
    render(
      <SelectedHoldingDetail
        holding={HELD[0]}
        rows={[]}
        evidence={
          {
            ticker: "111111",
            short_term_momentum: {
              status: "ok",
              return_5d_pct: -3,
              return_10d_pct: 1,
              return_20d_pct: 2,
              excess_vs_kodex200_5d_pctp: 0.5,
              excess_vs_kodex200_10d_pctp: -0.25,
              excess_vs_kodex200_20d_pctp: 1.2,
            },
          } as never
        }
        evidenceLoaded
      />,
    );
    expect(screen.getByText("+0.50%p")).toBeInTheDocument();
    expect(screen.getByText("-0.25%p")).toBeInTheDocument();
    expect(screen.getByText("+1.20%p")).toBeInTheDocument();
    expect(screen.getByText("-3.00%")).toBeInTheDocument();
  });
});
