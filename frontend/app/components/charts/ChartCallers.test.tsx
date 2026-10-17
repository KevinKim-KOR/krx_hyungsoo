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

// 끝 날짜에서 거꾸로 저장일 n개(주말 건너뜀) — 날짜 오름차순.
function seriesEnding(n: number, end: string, base: number) {
  const out: { date: string; price: number }[] = [];
  const d = new Date(`${end}T00:00:00Z`);
  while (out.length < n) {
    const wd = d.getUTCDay();
    if (wd !== 0 && wd !== 6) out.unshift({ date: d.toISOString().slice(0, 10), price: 0 });
    d.setUTCDate(d.getUTCDate() - 1);
  }
  return out.map((p, i) => ({ ...p, price: base + i * 1.25 }));
}

// POC5-UI-04 — 기간 선택(기본 3개월 · 6개월 · 1년 · 전체 · 기준 = 그 종목의 마지막 저장일 · 경계 포함).
describe("종목 가격 차트(확인 근거 · ETF 비교하기) — 기간 선택 · 원 · 종목별 고른 날", () => {
  it("처음 3개월 · 기간을 바꾸면 그 창의 최근 저장일 · 실제 기간 · N개 · 전체 복구 · 새 GET 없음 · 종목을 바꾸면 3개월", async () => {
    const a = seriesEnding(300, "2026-10-14", 10000);
    const b = seriesEnding(40, "2026-10-14", 20000);
    fetchPriceSeries.mockImplementation((t: string) => Promise.resolve(resp(t, t === "AAAAAA" ? a : b)));
    const { container, rerender } = render(<PriceChart ticker="AAAAAA" />);
    await screen.findByText(/표시 기간/);
    const btn = (name: string) => screen.getByRole("button", { name });
    const cap = () => screen.getByTestId("price-chart-period").textContent;
    const ro = () => screen.getByTestId("price-chart-readout").textContent;
    const plot = () => container.querySelector(".rc-plot") as HTMLElement;
    const win = (start: string) => a.filter((p) => p.date >= start);
    const won = (p: { price: number }) => `${p.price.toLocaleString("ko-KR", { maximumFractionDigits: 6 })}원`;

    // 처음 = 3개월(2026-07-14 ~ 2026-10-14 · 경계 포함).
    expect(btn("3개월")).toHaveAttribute("aria-pressed", "true");
    const w3 = win("2026-07-14");
    expect(w3[0].date).toBe("2026-07-14");
    expect(cap()).toBe(`표시 기간 2026-07-14 ~ 2026-10-14 · ${w3.length}개 저장일 · 전체 저장 ${a[0].date} ~ 2026-10-14 · 300개`);
    expect(xLabels(container)[0]).toBe("2026-07-14");
    expect(yLabels(container).every((t) => t.endsWith("원"))).toBe(true);
    expect(ro()).toBe(`2026-10-14 · 종가 ${won(a[299])}`);
    fireEvent.keyDown(plot(), { key: "Home" });
    expect(ro()).toBe(`2026-07-14 · 종가 ${won(w3[0])}`);

    // 1년 → 고른 날은 그 창의 가장 최근 저장일 · 해 바뀜 연도 눈금.
    fireEvent.click(btn("1년"));
    expect(btn("1년")).toHaveAttribute("aria-pressed", "true");
    expect(ro()).toBe(`2026-10-14 · 종가 ${won(a[299])}`);
    const w12 = win("2025-10-14");
    expect(cap()).toBe(`표시 기간 ${w12[0].date} ~ 2026-10-14 · ${w12.length}개 저장일 · 전체 저장 ${a[0].date} ~ 2026-10-14 · 300개`);
    expect(xLabels(container).filter((t) => /^\d{4}-/.test(t ?? "")).length).toBeGreaterThanOrEqual(2);

    // 6개월 · 전체 복구.
    fireEvent.click(btn("6개월"));
    expect(xLabels(container)[0]).toBe(win("2026-04-14")[0].date);
    fireEvent.click(btn("전체"));
    expect(cap()).toBe(`표시 기간 ${a[0].date} ~ 2026-10-14 · 300개 저장일`);
    expect(xLabels(container)[0]).toBe(a[0].date);
    expect(fetchPriceSeries).toHaveBeenCalledTimes(1); // 기간 버튼은 조회하지 않음

    // 다른 종목 → 3개월로 다시 시작 · 저장 기간이 짧으면 있는 만큼.
    rerender(<PriceChart ticker="BBBBBB" />);
    await act(async () => {
      await Promise.resolve();
    });
    await screen.findByText(/40개 저장일/);
    expect(btn("3개월")).toHaveAttribute("aria-pressed", "true");
    expect(cap()).toBe(`표시 기간 ${b[0].date} ~ 2026-10-14 · 40개 저장일 · 저장된 자료 전체(선택한 기간보다 짧음)`);
    expect(ro()).toBe(`2026-10-14 · 종가 ${won(b[39])}`);

    // 이미 받은 종목으로 돌아가도(불러오는 중 없이 바로 그림) 기간은 3개월로 다시 시작.
    fireEvent.click(btn("전체"));
    rerender(<PriceChart ticker="AAAAAA" />);
    expect(btn("3개월")).toHaveAttribute("aria-pressed", "true");
    expect(cap()).toContain("표시 기간 2026-07-14 ~ 2026-10-14");
    expect(fetchPriceSeries).toHaveBeenCalledTimes(2); // 종목별 한 번(돌아올 때 다시 조회하지 않음)
  });
});
