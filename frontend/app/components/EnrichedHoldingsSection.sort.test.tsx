// POC3-08 보유 현황 정렬 로직 테스트.
// 정렬은 표시 순서만 바꾼다(평가·계산 무변경). 기본·최우선 = 계좌순.
import { describe, it, expect } from "vitest";
import { sortHoldings } from "./EnrichedHoldingsSection";
import type { EnrichedHolding } from "@/lib/api";

// 최소 EnrichedHolding 픽스처 — 정렬에 쓰이는 필드만 의미 있음.
function h(
  ticker: string,
  name: string | null,
  account_group: string
): EnrichedHolding {
  return {
    ticker,
    name,
    quantity: 1,
    avg_buy_price: 100,
    invested_amount: 100,
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

const tickersOf = (arr: EnrichedHolding[]) => arr.map((x) => x.ticker);
const accountsOf = (arr: EnrichedHolding[]) =>
  arr.map((x) => x.account_group);

describe("sortHoldings — 계좌순(기본·최우선)", () => {
  it("계좌 그룹을 증권사 순서(일반·ISA·연금·오픈뱅킹·기타)로 묶는다", () => {
    const items = [
      h("A", "가", "연금"),
      h("B", "나", "일반"),
      h("C", "다", "오픈뱅킹"),
      h("D", "라", "ISA"),
      h("E", "마", "기타"),
    ];
    const out = sortHoldings(items, "account");
    expect(accountsOf(out)).toEqual([
      "일반",
      "ISA",
      "연금",
      "오픈뱅킹",
      "기타",
    ]);
  });

  it("같은 계좌 안에서는 종목명 가나다순", () => {
    const items = [
      h("T1", "다종목", "일반"),
      h("T2", "가종목", "일반"),
      h("T3", "나종목", "일반"),
    ];
    const out = sortHoldings(items, "account");
    expect(out.map((x) => x.name)).toEqual(["가종목", "나종목", "다종목"]);
  });

  it("추천 목록에 없는 커스텀 계좌는 뒤로", () => {
    const items = [
      h("A", "가", "내커스텀계좌"),
      h("B", "나", "일반"),
    ];
    const out = sortHoldings(items, "account");
    expect(accountsOf(out)).toEqual(["일반", "내커스텀계좌"]);
  });

  it("account_group 누락은 '일반' 취급", () => {
    const noAg = h("X", "엑스", "");
    // account_group 을 빈 값으로 — 코드상 (ag ?? '일반') 후 trim 되어 '일반' 우선순위.
    const items = [h("A", "가", "ISA"), noAg];
    const out = sortHoldings(items, "account");
    // '일반' 취급이므로 ISA 보다 앞.
    expect(out[0].ticker).toBe("X");
  });
});

describe("sortHoldings — 종목명순 / 종목코드순", () => {
  it("종목명순은 계좌 무시 전체 가나다", () => {
    const items = [
      h("T1", "다", "일반"),
      h("T2", "가", "연금"),
      h("T3", "나", "ISA"),
    ];
    const out = sortHoldings(items, "name");
    expect(out.map((x) => x.name)).toEqual(["가", "나", "다"]);
  });

  it("종목명 없으면 ticker 로 대체해 정렬", () => {
    const items = [h("ZZZ", null, "일반"), h("AAA", null, "일반")];
    const out = sortHoldings(items, "name");
    expect(tickersOf(out)).toEqual(["AAA", "ZZZ"]);
  });

  it("종목코드순은 ticker 오름차순", () => {
    const items = [
      h("069500", "케이", "일반"),
      h("000660", "에스", "ISA"),
      h("005930", "삼", "연금"),
    ];
    const out = sortHoldings(items, "ticker");
    expect(tickersOf(out)).toEqual(["000660", "005930", "069500"]);
  });
});

describe("sortHoldings — 원본 불변(표시용 새 배열)", () => {
  it("입력 배열을 변형하지 않는다", () => {
    const items = [h("B", "나", "일반"), h("A", "가", "일반")];
    const before = tickersOf(items);
    sortHoldings(items, "name");
    expect(tickersOf(items)).toEqual(before); // 원본 순서 유지
  });
});
