// POC3-08 재작업(검증자 지적 #3) — 부분 평가값을 전체 합계처럼 표시하지 않는다.
//   전부 계산 / 일부만 계산 / 전부 불가 3상태를 실제 컴포넌트 렌더로 고정.
import { describe, it, expect } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
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

// POC6-25 — 값 없음(null · 필드 누락)을 '0원'으로 그리지 않는다(통합설계 V1.1 B-3).
//   행 현재가 = '현재 미확인' · 상세 현재가 = '미확인' · 상세 평가금액 = '평가 불가' · 숫자 0 은 '0원' 유지.
//   실제 EnrichedSection 을 렌더하고 행을 눌러 상세를 편다(호출부 그대로 확인).
function renderOne(row: EnrichedHolding) {
  const { container } = render(<EnrichedSection items={[row]} />);
  const price = container.querySelector(".hld-row-price")?.textContent ?? "";
  fireEvent.click(container.querySelector(".hld-row") as Element);
  const detail = Object.fromEntries(
    Array.from(container.querySelectorAll(".detail-fields li")).map((li) => [
      li.querySelector(".k")?.textContent,
      li.querySelector(".v")?.textContent,
    ])
  );
  return { price, detail };
}

describe("POC6-25 현재가 · 평가금액 값 없음 표시", () => {
  it("시세 없음(null): 행 '현재 미확인' · 상세 '현재가 미확인' · '평가금액 평가 불가' · 매입가 유지", () => {
    const { price, detail } = renderOne(unpricedRow("005930", "삼성전자", "일반"));
    expect(price).toContain("매입 1,000원");
    expect(price).toContain("현재 미확인");
    expect(price).not.toMatch(/현재\s*0원/);
    expect(detail["현재가"]).toBe("미확인");
    expect(detail["평가금액"]).toBe("평가 불가");
    expect(detail["평균 매입단가"]).toBe("1,000원");
  });

  it("필드 누락(응답에 칸 없음)도 null 과 같다", () => {
    const row = unpricedRow("005930", "삼성전자", "일반") as Partial<EnrichedHolding>;
    delete row.current_price;
    delete row.eval_amount;
    const { price, detail } = renderOne(row as EnrichedHolding);
    expect(price).toContain("현재 미확인");
    expect(detail["현재가"]).toBe("미확인");
    expect(detail["평가금액"]).toBe("평가 불가");
  });

  it("정상 숫자: 행 · 상세 현재가와 상세 평가금액은 지금 금액 글 그대로", () => {
    const { price, detail } = renderOne(calcRow("069500", "KODEX 200", "일반", 1000));
    expect(price).toContain("현재 1,100원");
    expect(detail["현재가"]).toBe("1,100원");
    expect(detail["평가금액"]).toBe("11,000원");
  });

  it("명시적 숫자 0 은 값 없음으로 바꾸지 않고 '0원' 유지", () => {
    const row = { ...unpricedRow("005930", "삼성전자", "일반"), current_price: 0, eval_amount: 0 };
    const { price, detail } = renderOne(row);
    expect(price).toContain("현재 0원");
    expect(price).not.toContain("미확인");
    expect(detail["현재가"]).toBe("0원");
    expect(detail["평가금액"]).toBe("0원");
  });
});
