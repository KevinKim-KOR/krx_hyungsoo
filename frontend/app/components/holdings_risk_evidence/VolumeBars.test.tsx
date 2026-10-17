// POC5-19 — 최근 저장일 거래량 막대 · 문구(설계 V1 §2 · §3 · 개정 판정 Q1 · Q2 · 차트 읽기 개정 2026-10-17 §3 · §4).
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { VolumeTrendEvidence } from "@/lib/api";
import { NO_VOLUME_TEXT } from "@/lib/storedVolume";
import VolumeBars from "./VolumeBars";
import {
  TREND_HELP_BASIS,
  TREND_HELP_MISSING,
  TREND_HELP_PRICE_MATCH,
  TREND_HELP_SHORT,
  missingNote,
  trendLimits,
} from "./volumeTrend";

function ev(volumes: (number | null)[]): VolumeTrendEvidence {
  const points = volumes.map((v, i) => ({ date: `2026-10-${String(i + 1).padStart(2, "0")}`, volume: v }));
  return {
    asof_date: points.length ? points[points.length - 1].date : null,
    points,
    missing_count: volumes.filter((v) => v === null).length,
  };
}

describe("거래량 흐름 문구 (POC5-19)", () => {
  it("결측 안내 · 저장된 0 은 결측 아님", () => {
    expect(missingNote(ev([1, null, 3, null]))).toBe(
      "거래량이 비어 있거나 확인이 필요한 날 2개는 빈칸으로 두었습니다(0으로 채우지 않음).",
    );
    expect(missingNote(ev([1, 0]))).toBeNull();
  });

  it("? 의 기간 기준은 '종가가 확인된 저장일'(판정 Q1) · 모든 원본 행이라고 하지 않음 · 날짜로 찾음 · 제한은 해당할 때만", () => {
    expect(TREND_HELP_BASIS).toContain("가격 흐름 · 거래량 칸과 같은, 종가가 확인된 저장일");
    expect(TREND_HELP_BASIS).not.toContain("모든");
    expect(TREND_HELP_BASIS).toContain("차트 위 줄");
    expect(TREND_HELP_PRICE_MATCH).toContain("같은 날짜의 값을 찾아");
    expect(TREND_HELP_PRICE_MATCH).toContain("'종가 자료 없음'");
    expect(TREND_HELP_PRICE_MATCH).toContain("고른 과거 날짜의 평균이 아닙니다");
    expect(trendLimits(ev(Array(20).fill(5)))).toEqual([]);
    expect(trendLimits(ev([1, 2]))).toEqual([TREND_HELP_SHORT]);
    expect(trendLimits(ev([...Array(19).fill(5), null]))).toEqual([TREND_HELP_MISSING]);
    expect(trendLimits(ev([]))).toEqual([]);
    expect(trendLimits(null)).toEqual([]);
    for (const bad of ["매수", "매도", "상승", "안전", "위험"]) {
      expect([TREND_HELP_BASIS, TREND_HELP_PRICE_MATCH, TREND_HELP_SHORT, TREND_HELP_MISSING].join(" ")).not.toContain(bad);
    }
  });
});

describe("거래량 막대 (POC5-19 · 차트 읽기 개정)", () => {
  it("주 눈금 · 0 시작 · 고른 날은 부모가 정함(누르기 · 화살표 → onSelect)", () => {
    const onSelect = vi.fn();
    const { container } = render(
      <VolumeBars ev={ev([12000, 20000, 48851])} selected={2} onSelect={onSelect} label="에이 거래량" />,
    );
    expect(Array.from(container.querySelectorAll(".rc-y > span")).map((e) => e.textContent)).toEqual([
      "0주",
      "2만주",
      "4만주",
      "6만주",
    ]);
    expect(screen.getByTestId("volume-bars-bar-2")).toHaveClass("rc-bar-sel");
    fireEvent.keyDown(screen.getByTestId("volume-bars-plot"), { key: "ArrowLeft" });
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it("값 없는 날은 점선 빈칸 · 날짜 자리 유지 / 저장된 0 은 막대(바닥선) · 색은 중립 클래스", () => {
    const { container } = render(
      <VolumeBars ev={ev([100, null, 0, 300])} selected={1} onSelect={() => {}} label="x" />,
    );
    expect(container.querySelectorAll(".rc-missing")).toHaveLength(1);
    expect(screen.getByTestId("volume-bars-missing-1")).toHaveClass("rc-missing-sel");
    expect(screen.getByTestId("volume-bars-bar-2")).toHaveClass("rc-bar");
    expect(container.querySelectorAll("rect[fill], rect[stroke]")).toHaveLength(0);
    expect(container.querySelector(".up, .down, .warn")).toBeNull();
    // 날짜 자리 4개(첫 눈금은 연도까지).
    expect(Array.from(container.querySelectorAll(".rc-x > span")).map((e) => e.textContent)).toEqual([
      "2026-10-01",
      "10-02",
      "10-03",
      "10-04",
    ]);
  });

  it("자료 0개는 기존 '자료 없음' 문장", () => {
    const { container } = render(<VolumeBars ev={ev([])} selected={0} onSelect={() => {}} label="x" />);
    expect(container.textContent).toBe(NO_VOLUME_TEXT);
  });
});
