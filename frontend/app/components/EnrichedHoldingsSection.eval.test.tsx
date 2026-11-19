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
    const { container } = render(
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
    // POC6-33 H6 — 배너의 N/M 은 계좌별 보유 행 수라 '행' · 계좌 소계는 그대로(PLAN H6).
    const hero = container.querySelector(".hld-hero")?.textContent ?? "";
    expect(hero).toContain("· 1/2행 기준");
    expect(hero).toContain("1행은 시세 미확인·계산 정보 부족");
    expect(hero).toContain("1/2행만의 부분 합계");
    expect(hero).not.toContain("종목 기준");
    expect(hero).not.toContain("종목만의");
    expect(container.querySelector(".hld-acct-sub")?.textContent).toContain("1/2종목 기준");
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
//   행 현재가 = '현재 미확인' · 상세 평가금액 = '평가 불가' · 숫자 0 은 '0원' 유지.
//   상세 현재가 줄은 POC6-33(2026-11-19 형수님 결정)에서 뺐다 — 현재가는 요약 행에서만 읽는다.
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
  it("시세 없음(null): 행 '현재 미확인' · 상세 '평가금액 평가 불가' · 상세에 현재가 줄 없음 · 매입가 유지", () => {
    const { price, detail } = renderOne(unpricedRow("005930", "삼성전자", "일반"));
    expect(price).toContain("매입 1,000원");
    expect(price).toContain("현재 미확인");
    expect(price).not.toMatch(/현재\s*0원/);
    expect(detail["현재가"]).toBeUndefined();
    expect(detail["평가금액"]).toBe("평가 불가");
    // POC6-33 H1 — 수량 · 평균 매입단가는 요약 행에만(상세에서 뺌 · 위 '매입 1,000원' 그대로).
    expect(detail["평균 매입단가"]).toBeUndefined();
    expect(detail["수량"]).toBeUndefined();
  });

  it("필드 누락(응답에 칸 없음)도 null 과 같다", () => {
    const row = unpricedRow("005930", "삼성전자", "일반") as Partial<EnrichedHolding>;
    delete row.current_price;
    delete row.eval_amount;
    const { price, detail } = renderOne(row as EnrichedHolding);
    expect(price).toContain("현재 미확인");
    expect(detail["현재가"]).toBeUndefined();
    expect(detail["평가금액"]).toBe("평가 불가");
  });

  it("정상 숫자: 행 현재가와 상세 평가금액은 지금 금액 글 그대로(상세 현재가 줄 없음)", () => {
    const { price, detail } = renderOne(calcRow("069500", "KODEX 200", "일반", 1000));
    expect(price).toContain("현재 1,100원");
    expect(detail["현재가"]).toBeUndefined();
    expect(detail["평가금액"]).toBe("11,000원");
  });

  it("명시적 숫자 0 은 값 없음으로 바꾸지 않고 '0원' 유지", () => {
    const row = { ...unpricedRow("005930", "삼성전자", "일반"), current_price: 0, eval_amount: 0 };
    const { price, detail } = renderOne(row);
    expect(price).toContain("현재 0원");
    expect(price).not.toContain("미확인");
    expect(detail["현재가"]).toBeUndefined();
    expect(detail["평가금액"]).toBe("0원");
  });
});

// POC6-33 — 「보유 현황」 상세 · 비중 이름 · 시각 · 출처 · 종목 수와 보유 행 수(PLAN H1 ~ H4 · H6 · H9).
//   가상 보유(보유 A · TEST01 · 가상 숫자)만 쓴다.
function synth(over: Partial<EnrichedHolding> = {}): EnrichedHolding {
  return {
    ticker: "TEST01",
    name: "보유 A",
    quantity: 3,
    avg_buy_price: 2000,
    invested_amount: 6000,
    current_price: 2500,
    price_asof: "2026-11-18T15:54:12+09:00",
    price_source: "naver",
    eval_amount: 7500,
    pnl_amount: 1500,
    pnl_rate_pct: 25,
    buy_weight_pct: 40,
    market_weight_pct: 45.5,
    price_missing: false,
    calc_missing: false,
    account_group: "일반",
    source_index: 0,
    ...over,
  };
}

function detailKeys(row: EnrichedHolding): string[] {
  const { container } = render(<EnrichedSection items={[row]} />);
  fireEvent.click(container.querySelector(".hld-row") as Element);
  return Array.from(container.querySelectorAll(".detail-fields li .k")).map((k) => k.textContent ?? "");
}

describe("POC6-33 「보유 현황」 펼친 상세 · 표기", () => {
  it("상세 순서 = 매입금액 → 평가금액 → 매입 기준 비중 → 가격 기준시각 · 현재가 · 수량 · 평균 매입단가 없음(요약 행에 있음)", () => {
    expect(detailKeys(synth())).toEqual(["매입금액", "평가금액", "매입 기준 비중", "가격 기준시각"]);
  });

  it("가격 기준시각 · 출처 줄만 두 칸 폭(wide2 · 목업 H4)", () => {
    const { container } = render(<EnrichedSection items={[synth()]} />);
    fireEvent.click(container.querySelector(".hld-row") as Element);
    const wide = Array.from(container.querySelectorAll(".detail-fields li.wide2 .k")).map((k) => k.textContent);
    expect(wide).toEqual(["가격 기준시각"]);
  });

  it("시세 없음이어도 평가금액 · 매입 기준 비중 항목은 숨기지 않음(시각 · 출처 없으면 그 줄만 없음)", () => {
    const row = synth({
      current_price: null,
      eval_amount: null,
      pnl_amount: null,
      pnl_rate_pct: null,
      buy_weight_pct: null,
      market_weight_pct: null,
      price_asof: null,
      price_source: null,
      price_missing: true,
      calc_missing: true,
    });
    expect(detailKeys(row)).toEqual(["매입금액", "평가금액", "매입 기준 비중"]);
  });

  it.each([
    ["값 없음(null)", null, "비중 계산 불가"],
    ["칸 누락", undefined, "비중 계산 불가"],
    ["숫자", 40, "40%"],
    ["숫자 0", 0, "0%"],
  ])("매입 기준 비중 %s → '%s'", (_l, bw, want) => {
    const row = synth({ buy_weight_pct: bw as number | null });
    if (bw === undefined) delete (row as Partial<EnrichedHolding>).buy_weight_pct;
    const { detail } = renderOne(row);
    expect(detail["매입 기준 비중"]).toBe(want);
    expect(detail["매입비중"]).toBeUndefined();
  });

  it.each([
    ["한국 시각 ISO", "2026-11-18T15:54:12+09:00", "naver", "2026-11-18 15:54:12 KST · 네이버"],
    ["UTC → 한국 시각", "2026-11-18T06:54:12Z", "naver", "2026-11-18 15:54:12 KST · 네이버"],
    ["자정 넘김(00시)", "2026-11-18T15:00:05Z", "naver", "2026-11-19 00:00:05 KST · 네이버"],
    ["초 없는 ISO", "2026-11-18T15:54+09:00", "naver", "2026-11-18 15:54:00 KST · 네이버"],
    ["날짜만", "2026-08-11", "naver", "2026-08-11 · 네이버"],
    ["시간대 없는 시각", "2026-11-18 15:54:12", "naver", "확인 불가 · 네이버"],
    ["없는 날짜", "2026-02-30", "naver", "확인 불가 · 네이버"],
    ["사전 밖 출처", "2026-11-18T15:54:12+09:00", "TEST", "2026-11-18 15:54:12 KST · 기타 출처"],
    ["객체 기본 이름도 사전 밖", "2026-11-18T15:54:12+09:00", "constructor", "2026-11-18 15:54:12 KST · 기타 출처"],
    ["출처 없음", "2026-11-18T15:54:12+09:00", null, "2026-11-18 15:54:12 KST"],
    ["시각 없음", null, "naver", "확인 불가 · 네이버"],
    ["둘 다 없음", null, null, undefined],
  ])("가격 기준시각 · 출처 한 줄 — %s", (_l, asof, src, want) => {
    const { detail } = renderOne(synth({ price_asof: asof, price_source: src }));
    expect(detail["가격 기준시각"]).toBe(want);
    expect(detail["데이터 출처"]).toBeUndefined();
  });

  it("행 비중 이름 = '보유 내 비중(평가 기준)' · 상세 '매입 기준 비중'", () => {
    const { container } = render(<EnrichedSection items={[synth()]} />);
    expect(container.querySelector(".hld-row-facts")?.textContent).toContain("보유 내 비중(평가 기준) 45.5%");
  });

  it("배너 = 서로 다른 종목 수와 계좌별 보유 행 수를 따로(같은 종목이 두 계좌에 있음)", () => {
    const { container } = render(
      <EnrichedSection
        items={[
          synth(),
          synth({ account_group: "ISA", source_index: 1 }),
          synth({ ticker: "TEST02", name: "보유 B", source_index: 2 }),
        ]}
      />
    );
    expect(container.querySelector(".hld-hero")?.textContent).toContain("보유 종목종목 2개 · 보유 행 3개");
    expect(screen.getByText("3/3개")).toBeInTheDocument(); // 평가 계산(행 기준 · 그대로)
  });

  it("목록 위 안내 = '저장된 네이버 시세' · 시세가 하나도 없으면 '아직 저장된 시세가 없습니다'", () => {
    const { container, unmount } = render(<EnrichedSection items={[synth()]} />);
    expect(container.textContent).toContain("저장된 네이버 시세 기준 평가. 갱신은 위의 [시세 갱신] 버튼.");
    expect(container.textContent).not.toMatch(/Naver|캐시/);
    unmount();
    const r2 = render(
      <EnrichedSection items={[synth({ current_price: null, eval_amount: null, price_missing: true, calc_missing: true })]} />
    );
    expect(r2.container.textContent).toContain("아직 저장된 시세가 없습니다. [시세 갱신] 버튼으로 1회 조회하세요.");
    expect(r2.container.textContent).not.toMatch(/Naver|캐시/);
  });
});
