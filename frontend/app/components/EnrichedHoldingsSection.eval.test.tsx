// POC3-08 재작업(검증자 지적 #3) — 부분 평가값을 전체 합계처럼 표시하지 않는다.
//   전부 계산 / 일부만 계산 / 전부 불가 3상태를 실제 컴포넌트 렌더로 고정.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import EnrichedSection from "./EnrichedHoldingsSection";
import type { EnrichedHolding } from "@/lib/api";

// 계산 가능(priced+eval) 종목.
function calcRow(
  ticker: string,
  name: string,
  account_group: string,
  pnl: number
): EnrichedHolding {
  return {
    ticker,
    name,
    quantity: 10,
    avg_buy_price: 1000,
    invested_amount: 10000,
    current_price: 1000 + pnl / 10,
    price_asof: "2026-08-11",
    price_source: "naver",
    eval_amount: 10000 + pnl,
    pnl_amount: pnl,
    pnl_rate_pct: (pnl / 10000) * 100,
    buy_weight_pct: 50,
    market_weight_pct: 50,
    price_missing: false,
    calc_missing: false,
    account_group,
  };
}

// 시세 미확인(계산 불가) 종목.
function unpricedRow(
  ticker: string,
  name: string,
  account_group: string
): EnrichedHolding {
  return {
    ticker,
    name,
    quantity: 10,
    avg_buy_price: 1000,
    invested_amount: 10000,
    current_price: null,
    price_asof: null,
    price_source: null,
    eval_amount: null,
    pnl_amount: null,
    pnl_rate_pct: null,
    buy_weight_pct: null,
    market_weight_pct: null,
    price_missing: true,
    calc_missing: true,
    account_group,
  };
}

describe("#3 평가값 3상태 — 전부/일부/전부불가", () => {
  it("전부 계산 가능: 부분 경고 없음 · N/M 이 전체와 같음", () => {
    render(
      <EnrichedSection
        items={[
          calcRow("069500", "KODEX 200", "일반", 1000),
          calcRow("139260", "TIGER 200 IT", "일반", -500),
        ]}
      />
    );
    // 평가 계산 2/2.
    expect(screen.getByText("2/2개")).toBeInTheDocument();
    // 부분 합계 경고 문구 없음.
    expect(screen.queryByText(/부분 합계/)).not.toBeInTheDocument();
  });

  it("일부만 계산: 전체·계좌 값에 N/M 기준 명시 + 부분 합계 경고", () => {
    render(
      <EnrichedSection
        items={[
          calcRow("069500", "KODEX 200", "일반", 1000), // 계산 가능
          unpricedRow("005930", "삼성전자", "일반"), // 시세 미확인
        ]}
      />
    );
    // 평가 계산 1/2.
    expect(screen.getByText("1/2개")).toBeInTheDocument();
    // 부분 합계임을 전체 배너에 명시.
    expect(screen.getByText(/부분 합계/)).toBeInTheDocument();
    // N/M 기준 표기 — 배너·계좌 소계 양쪽에 나타난다(부분임을 여러 곳에서 명시).
    expect(screen.getAllByText(/1\/2종목 기준/).length).toBeGreaterThanOrEqual(1);
  });

  it("전부 불가: 평가금액·손익 '계산 불가' · 갱신 유도 경고", () => {
    render(
      <EnrichedSection
        items={[
          unpricedRow("005930", "삼성전자", "일반"),
          unpricedRow("000660", "SK하이닉스", "ISA"),
        ]}
      />
    );
    expect(screen.getByText("0/2개")).toBeInTheDocument();
    // 총 평가금액·평가손익 모두 계산 불가.
    expect(screen.getAllByText("계산 불가").length).toBeGreaterThanOrEqual(1);
    // 시세 확인된 종목이 없다는 경고.
    expect(
      screen.getByText(/시세 확인된 종목이 없어/)
    ).toBeInTheDocument();
  });
});
