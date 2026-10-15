// POC5-15 — '?' 도움말(PLAN 판정 §5): 클릭으로 여닫고 · Escape · 바깥 클릭으로 닫히며 · 마우스를 올리기만
// 해서는 열리지 않는다. 받은 문장만 보인다.
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import HelpPopover from "./HelpPopover";

function setup() {
  render(
    <div>
      <HelpPopover label="현재 상태" paragraphs={["첫째 문단", "둘째 문단"]} />
      <p>바깥</p>
    </div>,
  );
  return screen.getByRole("button", { name: "현재 상태 도움말" });
}

describe("HelpPopover (POC5-15)", () => {
  it("처음엔 닫혀 있고 클릭하면 열리고 다시 누르면 닫힌다", () => {
    const btn = setup();
    expect(btn).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-expanded", "true");
    const dlg = screen.getByRole("dialog", { name: "현재 상태 도움말" });
    expect(dlg.textContent).toBe("첫째 문단둘째 문단");
    fireEvent.click(btn);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("Escape 로 닫히고 버튼으로 초점이 돌아간다", () => {
    const btn = setup();
    fireEvent.click(btn);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(btn);
  });

  it("바깥을 누르면 닫히고 · 창 안을 누르면 열린 채", () => {
    const btn = setup();
    fireEvent.click(btn);
    fireEvent.mouseDown(screen.getByRole("dialog"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByText("바깥"));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("마우스를 올리기만 해서는 열리지 않는다", () => {
    const btn = setup();
    fireEvent.mouseEnter(btn);
    fireEvent.mouseOver(btn);
    fireEvent.focus(btn);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("키보드: 버튼이라 Enter · Space 로 연다(클릭 이벤트)", () => {
    const btn = setup();
    expect(btn.tagName).toBe("BUTTON");
    expect(btn).toHaveAttribute("type", "button");
  });

  it("Tab 으로 초점이 창 밖 다른 요소로 가면 닫힌다(다음 버튼을 가리지 않게) · 창 안 글자 클릭은 열린 채", () => {
    render(
      <div>
        <HelpPopover label="현재 상태" paragraphs={["첫째 문단"]} />
        <button type="button">다음 버튼</button>
      </div>,
    );
    const btn = screen.getByRole("button", { name: "현재 상태 도움말" });
    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-controls", screen.getByRole("dialog").id);
    fireEvent.blur(btn, { relatedTarget: null }); // 창 안 글자 누름 — 옮겨 간 초점 없음
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.blur(btn, { relatedTarget: screen.getByRole("button", { name: "다음 버튼" }) });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(btn).toHaveAttribute("aria-expanded", "false");
  });
});

// ── 위치: 보이는 폭(clientWidth · 스크롤바 제외) 안으로 옮김 · 창 크기 바뀌면 다시 잼 ──
describe("HelpPopover 위치 (POC5-15)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    Object.defineProperty(document.documentElement, "clientWidth", { value: 0, configurable: true });
  });
  function mockPanelRect(left: number, width = 380) {
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
      const el = this as HTMLElement;
      if (el.classList?.contains("help-pop-panel")) {
        const m = /translateX\((-?\d+(?:\.\d+)?)px\)/.exec(el.style.transform || "");
        const t = m ? Number(m[1]) : 0;
        return { left: left + t, right: left + width + t, top: 0, bottom: 100, width, height: 100, x: left + t, y: 0, toJSON() {} } as DOMRect;
      }
      return { left: 0, right: 0, top: 0, bottom: 0, width: 0, height: 0, x: 0, y: 0, toJSON() {} } as DOMRect;
    });
  }
  const panel = () => screen.getByRole("dialog") as HTMLElement;

  it("오른쪽이 보이는 폭(스크롤바 제외)을 넘으면 왼쪽으로 옮긴다", () => {
    Object.defineProperty(document.documentElement, "clientWidth", { value: 983, configurable: true });
    mockPanelRect(700); // 오른쪽 1080
    const btn = setup();
    fireEvent.click(btn);
    expect(panel().style.transform).toBe("translateX(-105px)"); // 983 − 8 − 1080
  });

  it("창 크기가 바뀌면 원래 자리에서 다시 잰다", () => {
    Object.defineProperty(document.documentElement, "clientWidth", { value: 983, configurable: true });
    mockPanelRect(700);
    fireEvent.click(setup());
    Object.defineProperty(document.documentElement, "clientWidth", { value: 900, configurable: true });
    act(() => {
      window.dispatchEvent(new Event("resize"));
    });
    expect(panel().style.transform).toBe("translateX(-188px)"); // 900 − 8 − 1080
    Object.defineProperty(document.documentElement, "clientWidth", { value: 1400, configurable: true });
    act(() => {
      window.dispatchEvent(new Event("resize"));
    });
    expect(panel().style.transform).toBe(""); // 넉넉하면 제자리
  });

  it("왼쪽이 화면 밖이면 오른쪽으로 옮긴다", () => {
    Object.defineProperty(document.documentElement, "clientWidth", { value: 375, configurable: true });
    mockPanelRect(2, 300);
    fireEvent.click(setup());
    expect(panel().style.transform).toBe("translateX(6px)");
  });
});
