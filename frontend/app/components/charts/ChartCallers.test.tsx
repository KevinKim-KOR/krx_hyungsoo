// POC5-19 개정(차트 읽기 · 2026-10-17 §3 · §5-4) — 공통 틀을 쓰는 기존 호출자: 기존 기간 · 기준 보존 · 단위 · 고른 날 줄.
//   - 코스피(「오늘의 투자 점검」): 최근 120개 저장값 · pt.
//   - 종목 가격(「확인 근거」 · 「ETF 비교하기」 같은 PriceChart): 받은 전체 저장 기간 · 원 · 종목을 바꾸면 그 종목의 최근 저장일.
// 외부 호출 0 — `@/lib/api` 는 대역.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";

const fetchBenchmarkSeries = vi.fn();
const fetchPriceSeries = vi.fn();
vi.mock("@/lib/api", () => ({
  fetchBenchmarkSeries: (...a: unknown[]) => fetchBenchmarkSeries(...a),
  fetchPriceSeries: (...a: unknown[]) => fetchPriceSeries(...a),
}));

import KospiChart from "../today/KospiChart";
import PriceChart from "../workbench/PriceChart";

// 저장일 n개(주말 건너뜀 · 해를 넘김 가능) — 날짜 오름차순.
function series(n: number, start: string, base: number) {
  const out: { date: string; price: number }[] = [];
  const d = new Date(`${start}T00:00:00Z`);
  while (out.length < n) {
    const wd = d.getUTCDay();
    if (wd !== 0 && wd !== 6) out.push({ date: d.toISOString().slice(0, 10), price: base + out.length * 1.25 });
    d.setUTCDate(d.getUTCDate() + 1);
  }
  return out;
}
const resp = (ticker: string, s: { date: string; price: number }[]) => ({
  ticker,
  availability: "AVAILABLE",
  available_from: s[0].date,
  available_to: s[s.length - 1].date,
  series: s,
});
const xLabels = (c: HTMLElement) => Array.from(c.querySelectorAll(".rc-x > span")).map((e) => e.textContent);
const yLabels = (c: HTMLElement) => Array.from(c.querySelectorAll(".rc-y > span")).map((e) => e.textContent ?? "");

beforeEach(() => {
  __resetQueryCache();
  fetchBenchmarkSeries.mockReset();
  fetchPriceSeries.mockReset();
});

describe("코스피 차트 — 기존 최근 120개 · pt 눈금 · 고른 날 줄", () => {
  it("120개 창 그대로(첫 날짜 눈금 = 끝에서 120번째) · 처음엔 가장 최근 저장일 · pt", async () => {
    const s = series(150, "2026-03-02", 6000);
    fetchBenchmarkSeries.mockResolvedValue(resp("KOSPI", s));
    const { container } = render(<KospiChart />);
    await screen.findByText(/최근 120개 저장일/);
    const recent = s.slice(-120);
    expect(xLabels(container)[0]).toBe(recent[0].date);
    expect(xLabels(container)).toHaveLength(5);
    // 아래 줄 = 저장일 개수(연속 거래일로 설명하지 않음) · 최종 값에 단위.
    expect(screen.getByText(`코스피 ${recent[0].date} ~ ${recent[119].date} · 최근 120개 저장일 · 최종 6,186.25pt`, { exact: false })).toBeTruthy();
    expect(screen.getByTestId("kospi-chart-readout").textContent).toBe(`${recent[119].date} · 코스피 6,186.25pt`);
    expect(yLabels(container).every((t) => t.endsWith("pt"))).toBe(true);
    fireEvent.keyDown(container.querySelector(".rc-plot") as HTMLElement, { key: "Home" });
    expect(screen.getByTestId("kospi-chart-readout").textContent).toBe(`${recent[0].date} · 코스피 6,037.50pt`);
    expect(fetchBenchmarkSeries).toHaveBeenCalledTimes(1);
  });
});

describe("종목 가격 차트(확인 근거 · ETF 비교하기) — 받은 전체 기간 · 원 · 종목별 고른 날", () => {
  it("전체 저장 기간 · 해를 넘기면 연도 눈금 · 원 단위 · 'N개 저장일' · 종목을 바꾸면 그 종목의 최근 저장일", async () => {
    const a = series(300, "2025-06-02", 10000);
    const b = series(40, "2026-08-03", 20000);
    fetchPriceSeries.mockImplementation((t: string) => Promise.resolve(resp(t, t === "AAAAAA" ? a : b)));
    const { container, rerender } = render(<PriceChart ticker="AAAAAA" />);
    await screen.findByText(/300개 저장일/);
    expect(screen.getByText(`제공 기간 ${a[0].date} ~ ${a[299].date} · 300개 저장일`)).toBeTruthy();
    const xl = xLabels(container);
    expect(xl[0]).toBe(a[0].date);
    expect(xl.filter((t) => /^\d{4}-/.test(t ?? "")).length).toBeGreaterThanOrEqual(2); // 2025 → 2026
    expect(yLabels(container).every((t) => t.endsWith("원"))).toBe(true);
    const ro = () => screen.getByTestId("price-chart-readout").textContent;
    expect(ro()).toBe(`${a[299].date} · 종가 10,373.75원`);
    fireEvent.keyDown(container.querySelector(".rc-plot") as HTMLElement, { key: "Home" });
    expect(ro()).toBe(`${a[0].date} · 종가 10,000원`);
    rerender(<PriceChart ticker="BBBBBB" />);
    await act(async () => {
      await Promise.resolve();
    });
    await screen.findByText(/40개 저장일/);
    expect(ro()).toBe(`${b[39].date} · 종가 20,048.75원`);
  });
});
