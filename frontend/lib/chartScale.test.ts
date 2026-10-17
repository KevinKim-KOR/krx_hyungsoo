// POC5-19 개정(차트 읽기 · 2026-10-17 §3) — 공통 눈금 계산 · 값 표시.
import { describe, it, expect } from "vitest";
import { dateTickIndices, dateTickLabels, fmtExact, fmtTick, fmtValue, valueAxis } from "./chartScale";

describe("값 눈금 (차트 읽기 개정 §3)", () => {
  it("실제 값 범위를 덮는 보기 좋은 눈금 3~5개 · 최솟값 · 최댓값이 범위 안", () => {
    const a = valueAxis([9123, 12345, 10500], { integer: true });
    expect(a.ticks).toEqual([8000, 10000, 12000, 14000]);
    expect(a.lo).toBeLessThanOrEqual(9123);
    expect(a.hi).toBeGreaterThanOrEqual(12345);
    const k = valueAxis([5600.5, 9100.25]);
    expect(k.ticks).toEqual([4000, 6000, 8000, 10000]);
    for (const v of [[1, 2, 3], [48995, 53600], [0.5, 0.75], [1e6, 3.2e6]]) {
      const t = valueAxis(v).ticks;
      expect(t.length).toBeGreaterThanOrEqual(3);
      expect(t.length).toBeLessThanOrEqual(5);
      expect(t[0]).toBeLessThanOrEqual(Math.min(...v));
      expect(t[t.length - 1]).toBeGreaterThanOrEqual(Math.max(...v));
    }
  });

  it("거래량은 0 에서 시작 · 전부 0 · 일정한 값 · 자료 없음에도 범위가 0 이 아니다", () => {
    expect(valueAxis([12864, 48851], { zeroBase: true, integer: true }).ticks).toEqual([0, 20000, 40000, 60000]);
    const zero = valueAxis([0, 0, 0], { zeroBase: true, integer: true });
    expect(zero.ticks).toEqual([0, 1]);
    expect(zero.hi).toBeGreaterThan(zero.lo);
    const flat = valueAxis([10000, 10000], { integer: true });
    expect(flat.hi).toBeGreaterThan(flat.lo);
    expect(flat.ticks[0]).toBeLessThan(10000);
    expect(flat.ticks[flat.ticks.length - 1]).toBeGreaterThan(10000);
    const none = valueAxis([]);
    expect(none.hi).toBeGreaterThan(none.lo);
    for (const a of [zero, flat, none]) for (const t of a.ticks) expect(Number.isFinite(t)).toBe(true);
    // 원 · 주는 1보다 잘게 나누지 않는다.
    expect(valueAxis([10000, 10001], { integer: true }).ticks.every(Number.isInteger)).toBe(true);
  });
});

describe("날짜 눈금 (차트 읽기 개정 §3)", () => {
  const days = (n: number, start = "2026-01-01") =>
    Array.from({ length: n }, (_, i) => {
      const d = new Date(`${start}T00:00:00Z`);
      d.setUTCDate(d.getUTCDate() + i * 2);
      return d.toISOString().slice(0, 10);
    });

  it("양끝 + 중간 · 개수 · 겹침 없음", () => {
    expect(dateTickIndices(20, 4)).toEqual([0, 6, 13, 19]);
    expect(dateTickIndices(419, 5)).toEqual([0, 105, 209, 314, 418]);
    expect(dateTickIndices(3, 4)).toEqual([0, 1, 2]);
    expect(dateTickIndices(1, 5)).toEqual([0]);
    expect(dateTickIndices(0, 5)).toEqual([]);
  });

  it("첫 눈금과 해가 바뀌는 눈금은 연도까지 · 나머지는 월-일", () => {
    const d = ["2025-01-21", "2025-07-01", "2025-12-02", "2026-05-11", "2026-10-14"];
    expect(dateTickLabels(d, [0, 1, 2, 3, 4])).toEqual([
      "2025-01-21",
      "07-01",
      "12-02",
      "2026-05-11",
      "10-14",
    ]);
    const same = days(20, "2026-09-01");
    expect(dateTickLabels(same, [0, 19])).toEqual(["2026-09-01", "10-09"]);
  });
});

describe("값 표시 — 눈금은 짧게 · 고른 값은 정밀하게 · 단위는 늘 (차트 읽기 개정 §3)", () => {
  it("눈금", () => {
    expect(fmtTick(40000, "주")).toBe("4만주");
    expect(fmtTick(25000, "주")).toBe("2.5만주");
    expect(fmtTick(200000000, "주")).toBe("2억주");
    expect(fmtTick(500, "주")).toBe("500주");
    expect(fmtTick(0, "주")).toBe("0주");
    expect(fmtTick(50000, "원")).toBe("50,000원");
    expect(fmtTick(6000, "pt")).toBe("6,000pt");
  });
  it("고른 값", () => {
    expect(fmtValue(12864, "주")).toBe("12,864주");
    expect(fmtValue(48995, "원")).toBe("48,995원");
    expect(fmtValue(6977.94, "pt")).toBe("6,977.94pt");
    expect(fmtValue(6000, "pt")).toBe("6,000.00pt");
  });

  // POC5-19 검증 r1(P2) — 저장된 값을 반올림 · 정수화하지 않는다. 0 이 아닌 값이 '0'으로 보이지 않는다.
  it("고른 값은 저장된 값 그대로 — 소수 · 아주 작은 값 · 0 구분", () => {
    expect(fmtValue(0.4, "주")).toBe("0.4주");
    expect(fmtValue(0, "주")).toBe("0주");
    expect(fmtValue(0.0004, "주")).toBe("0.0004주");
    expect(fmtValue(1234.5, "주")).toBe("1,234.5주");
    expect(fmtValue(0.004, "원")).toBe("0.004원");
    expect(fmtValue(10373.75, "원")).toBe("10,373.75원");
    expect(fmtValue(6977.945, "pt")).toBe("6,977.945pt");
    expect(fmtExact(0.123456789)).toBe("0.123457");
    expect(fmtExact(-0.5)).toBe("-0.5");
    for (const v of [0.4, 0.0004, 1e-7, 0.004, 2.5e-9]) {
      for (const u of ["주", "원", "pt"] as const) expect(fmtValue(v, u)).not.toMatch(/^0(\.0+)?(주|원|pt)$/);
    }
  });
});
