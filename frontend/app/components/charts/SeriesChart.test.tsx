// POC5-19 개정(차트 읽기 · 2026-10-17 §3) — 공통 차트 틀: 눈금 · 단위 · 가로선 · 고르기 · 결측 · 0 · 선택값 줄.
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SeriesChart from "./SeriesChart";
import ReadableLineChart from "./ReadableLineChart";

const D5 = ["2026-10-08", "2026-10-09", "2026-10-10", "2026-10-13", "2026-10-14"];

function plotOf(container: HTMLElement): HTMLElement {
  return container.querySelector(".rc-plot") as HTMLElement;
}

describe("공통 차트 틀 (차트 읽기 개정 §3)", () => {
  it("세로 = 값 눈금과 단위 · 같은 높이 가로선 / 가로 = 날짜 눈금(첫 눈금은 연도까지)", () => {
    const { container } = render(
      <SeriesChart
        dates={D5}
        values={[48000, 49500, 51000, 50200, 48995]}
        kind="line"
        unit="원"
        selected={4}
        onSelect={() => {}}
        label="x"
      />,
    );
    const yl = Array.from(container.querySelectorAll(".rc-y > span")).map((e) => e.textContent);
    expect(yl).toEqual(["48,000원", "49,000원", "50,000원", "51,000원"]);
    expect(container.querySelectorAll(".rc-grid")).toHaveLength(yl.length);
    const xl = Array.from(container.querySelectorAll(".rc-x > span")).map((e) => e.textContent);
    expect(xl).toEqual(["2026-10-08", "10-09", "10-13", "10-14"]);
    // 고른 날: 세로 안내선 + 점.
    expect(container.querySelector(".rc-guide")).not.toBeNull();
    expect(container.querySelector(".rc-dot")).not.toBeNull();
  });

  it("선은 결측에서 끊는다(앞 값 · 0 으로 잇지 않음) · 혼자 남은 점도 보인다", () => {
    const { container, rerender } = render(
      <SeriesChart dates={D5} values={[1, 2, null, 4, 5]} kind="line" unit="원" selected={2} onSelect={() => {}} label="x" />,
    );
    expect(container.querySelectorAll("path.rc-line")).toHaveLength(2);
    expect(container.querySelector(".rc-dot")).toBeNull(); // 고른 날 값이 없으면 점 없음
    rerender(
      <SeriesChart dates={D5} values={[1, null, 3, null, 5]} kind="line" unit="원" selected={4} onSelect={() => {}} label="x" />,
    );
    expect(container.querySelectorAll("path.rc-line")).toHaveLength(3);
  });

  it("막대: 0 에서 시작 · 값 없는 날 점선 빈칸 · 저장된 0 은 바닥선 · 고른 막대 강조", () => {
    const { container } = render(
      <SeriesChart
        dates={D5}
        values={[12000, null, 0, 48851, 12864]}
        kind="bar"
        unit="주"
        selected={1}
        onSelect={() => {}}
        label="x"
        testId="vb"
      />,
    );
    const yl = Array.from(container.querySelectorAll(".rc-y > span")).map((e) => e.textContent);
    expect(yl[0]).toBe("0주");
    expect(yl).toEqual(["0주", "2만주", "4만주", "6만주"]);
    expect(container.querySelector(".rc-base")).not.toBeNull(); // 0 기준선
    expect(screen.getByTestId("vb-missing-1")).toHaveClass("rc-missing-sel");
    expect(screen.queryByTestId("vb-bar-1")).toBeNull();
    expect(Number(screen.getByTestId("vb-bar-2").getAttribute("height"))).toBeGreaterThan(0);
    expect(container.querySelectorAll(".rc-bar-sel")).toHaveLength(0);
  });

  it("막대는 값이 모두 커도 0 에서 시작(선은 값 범위에 맞춤)", () => {
    const vals = [40000, 41000, 42000, 41500, 40500];
    const bar = render(
      <SeriesChart dates={D5} values={vals} kind="bar" unit="주" selected={0} onSelect={() => {}} label="x" testId="vb" />,
    );
    const yb = Array.from(bar.container.querySelectorAll(".rc-y > span")).map((e) => e.textContent);
    expect(yb[0]).toBe("0주");
    // 40,000주 막대는 높이의 절반을 넘는다(0 기준).
    expect(Number(screen.getByTestId("vb-bar-0").getAttribute("height"))).toBeGreaterThan(50);
    bar.unmount();
    const line = render(
      <SeriesChart dates={D5} values={vals} kind="line" unit="원" selected={0} onSelect={() => {}} label="x" />,
    );
    const yl = Array.from(line.container.querySelectorAll(".rc-y > span")).map((e) => e.textContent);
    expect(yl).toEqual(["40,000원", "41,000원", "42,000원"]);
  });

  // 터치도 같은 포인터 이벤트 처리를 쓴다(누르기 · 끌기). jsdom 은 터치 좌표를 만들 수 없어 마우스 좌표로 본다.
  it("고르기: 좌우 · Home · End(끝에서 멈춤) · 포인터(마우스) 위치 · 좌표 없는 이벤트 무시", () => {
    const onSelect = vi.fn();
    const { container } = render(
      <SeriesChart dates={D5} values={[1, 2, 3, 4, 5]} kind="line" unit="pt" selected={0} onSelect={onSelect} label="x" />,
    );
    const plot = plotOf(container);
    expect(plot).toHaveAttribute("tabindex", "0");
    fireEvent.keyDown(plot, { key: "ArrowLeft" });
    fireEvent.keyDown(plot, { key: "ArrowRight" });
    fireEvent.keyDown(plot, { key: "End" });
    fireEvent.keyDown(plot, { key: "Home" });
    expect(onSelect.mock.calls.map((c) => c[0])).toEqual([0, 1, 4, 0]);
    plot.getBoundingClientRect = () => ({ left: 100, width: 500, top: 0, height: 100, right: 600, bottom: 100, x: 100, y: 0, toJSON: () => ({}) });
    onSelect.mockClear();
    // jsdom 의 PointerEvent 에는 좌표가 없어 같은 이름의 마우스 이벤트로 보낸다.
    const ptr = (type: string, clientX: number) =>
      fireEvent(plot, new MouseEvent(type, { bubbles: true, clientX }));
    ptr("pointermove", 100 + 500 * 0.7);
    ptr("pointerdown", 99);
    ptr("pointerdown", 700);
    fireEvent.pointerMove(plot); // 좌표 없는 이벤트는 무시
    expect(onSelect.mock.calls.map((c) => c[0])).toEqual([3, 0, 4]);
  });

  it("일정한 값 · 전부 0 · 한 개도 좌표가 깨지지 않는다 · 자료 0개는 그리지 않음", () => {
    for (const values of [[5, 5, 5, 5, 5], [0, 0, 0, 0, 0]]) {
      const { container, unmount } = render(
        <SeriesChart dates={D5} values={values} kind={values[0] ? "line" : "bar"} unit="주" selected={4} onSelect={() => {}} label="x" />,
      );
      expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
      unmount();
    }
    const one = render(
      <SeriesChart dates={["2026-10-14"]} values={[100]} kind="line" unit="원" selected={0} onSelect={() => {}} label="x" />,
    );
    expect(one.container.innerHTML).not.toMatch(/NaN|Infinity/);
    expect(Array.from(one.container.querySelectorAll(".rc-x > span")).map((e) => e.textContent)).toEqual(["2026-10-14"]);
    const empty = render(
      <SeriesChart dates={[]} values={[]} kind="line" unit="원" selected={0} onSelect={() => {}} label="x" />,
    );
    expect(empty.container.innerHTML).toBe("");
  });
});

describe("한 줄 가격 차트 — 차트 위 고정 줄 (차트 읽기 개정 §3)", () => {
  const pts = D5.map((date, i) => ({ date, price: 6900 + i * 10.5 }));
  it("처음엔 가장 최근 저장일 · 고르면 그 날짜 · 정확한 값과 단위 · 경고 색", () => {
    const { container } = render(
      <ReadableLineChart points={pts} unit="pt" valueLabel="코스피" label="x" testId="k" warn />,
    );
    const ro = () => screen.getByTestId("k-readout").textContent;
    expect(ro()).toBe("2026-10-14 · 코스피 6,942.00pt");
    fireEvent.keyDown(plotOf(container), { key: "ArrowLeft" });
    expect(ro()).toBe("2026-10-13 · 코스피 6,931.50pt");
    expect(container.querySelector("path")?.getAttribute("stroke")).toBe("var(--warn)");
  });
});
