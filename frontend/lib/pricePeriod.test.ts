// POC5-UI-04 — 종목 가격 차트 기간(설계 docs/ai_design/POC5/POC5-19_RESULT_DECISION_AND_PRICE_CHART_PERIOD_DESIGN_2026-10-17.md §3).
import { describe, it, expect } from "vitest";
import { DEFAULT_PRICE_PERIOD, PRICE_PERIODS, minusMonths, periodStart, periodWindow } from "./pricePeriod";

describe("달력 개월 빼기 — 월말은 그 달 말일 · 시각대 변환 없음", () => {
  it("보통 날 · 해 넘김", () => {
    expect(minusMonths("2026-10-14", 3)).toBe("2026-07-14");
    expect(minusMonths("2026-10-14", 6)).toBe("2026-04-14");
    expect(minusMonths("2026-10-14", 12)).toBe("2025-10-14");
    expect(minusMonths("2026-01-15", 3)).toBe("2025-10-15");
    expect(minusMonths("2026-03-01", 12)).toBe("2025-03-01");
  });
  it("그 달에 같은 날이 없으면 말일(윤년 포함)", () => {
    expect(minusMonths("2026-05-31", 3)).toBe("2026-02-28");
    expect(minusMonths("2024-05-31", 3)).toBe("2024-02-29");
    expect(minusMonths("2024-02-29", 12)).toBe("2023-02-28");
    expect(minusMonths("2026-12-31", 6)).toBe("2026-06-30");
    expect(minusMonths("2026-03-31", 1)).toBe("2026-02-28");
  });
  it("기간 이름 · 기본 3개월 · 전체는 시작 없음", () => {
    expect(PRICE_PERIODS.map(([, l]) => l)).toEqual(["3개월", "6개월", "1년", "전체"]);
    expect(DEFAULT_PRICE_PERIOD).toBe("3M");
    expect(periodStart("2026-10-14", "3M")).toBe("2026-07-14");
    expect(periodStart("2026-10-14", "1Y")).toBe("2025-10-14");
    expect(periodStart("2026-10-14", "ALL")).toBeNull();
  });
});

describe("기간 창 — 기준 D = 마지막 저장일 · 경계 포함 · 원본 보존", () => {
  const S = [
    { date: "2025-10-13", price: 1 },
    { date: "2025-10-14", price: 2 },
    { date: "2026-04-13", price: 3 },
    { date: "2026-04-14", price: 4 },
    { date: "2026-07-13", price: 5 },
    { date: "2026-07-14", price: 6 },
    { date: "2026-10-14", price: 7 },
  ];
  it("시작 경계 날짜 포함 · 하루 전은 빠짐", () => {
    expect(periodWindow(S, "3M").map((x) => x.date)).toEqual(["2026-07-14", "2026-10-14"]);
    expect(periodWindow(S, "6M").map((x) => x.date)).toEqual([
      "2026-04-14", "2026-07-13", "2026-07-14", "2026-10-14",
    ]);
    expect(periodWindow(S, "1Y")[0].date).toBe("2025-10-14");
  });
  it("전체 = 받은 전체 · 원본 배열은 바꾸지 않음(새 배열)", () => {
    const before = S.map((x) => x.date);
    const all = periodWindow(S, "ALL");
    expect(all).toEqual(S);
    expect(all).not.toBe(S);
    periodWindow(S, "3M");
    expect(S.map((x) => x.date)).toEqual(before);
  });
  it("저장 기간이 짧으면 있는 만큼만 · 빈 시계열 · 한 개", () => {
    const short = [
      { date: "2026-09-01", price: 1 },
      { date: "2026-10-14", price: 2 },
    ];
    expect(periodWindow(short, "1Y")).toEqual(short);
    expect(periodWindow([], "3M")).toEqual([]);
    expect(periodWindow([{ date: "2026-10-14", price: 9 }], "6M")).toHaveLength(1);
  });
  it("기준은 그 시계열의 마지막 저장일(오늘이 아님)", () => {
    const old = [
      { date: "2024-01-02", price: 1 },
      { date: "2024-03-15", price: 2 },
      { date: "2024-04-15", price: 3 },
    ];
    expect(periodWindow(old, "3M").map((x) => x.date)).toEqual(["2024-03-15", "2024-04-15"]);
  });
});
