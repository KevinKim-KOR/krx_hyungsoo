// 「개발·실험용」 미사용 기능 이동 안내(POC6-29 보완 · 보완 PLAN 판정 2026-11-12 Q-R5 · RESULT 판정 §4).
// [신규 ETF 관찰 후보 갱신]은 처음엔 이 화면 맨 아래 「미사용 기능」 구역(맨 위 [미사용 기능] 버튼)에 두었다가
// 사이드바 「진단·상태 › 미사용 기능 › 신규 ETF 관찰 점검」(`unused_universe_watch`)으로 옮겼다.
// - 이 화면에는 [미사용 기능] 버튼 · 구역 · 갱신 패널이 없다.
// - 옮긴 곳 한 줄 + 이동 버튼(누르면 onNavigate("unused_universe_watch")).
// - 화면을 열기만 해서는 갱신(외부 조회 · 파일 덮어쓰기)을 하지 않는다.
// 미리보기 · 호환 점검 · LEGACY 대시보드는 이 계약과 무관해 가짜로 바꾼다(실제 네트워크 · 운영 자료 미의존).
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";

const refreshUniverseMomentum = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  refreshUniverseMomentum: (...a: unknown[]) => refreshUniverseMomentum(...a),
}));
vi.mock("./approval/ManualPreviewSection", () => ({ default: () => <div>미리보기 자리</div> }));
vi.mock("./approval/DevCompatSection", () => ({ default: () => <div>호환 점검 자리</div> }));
vi.mock("./DashboardView", () => ({ default: () => <div>LEGACY 자리</div> }));

import DiagnosticsView from "./DiagnosticsView";

beforeEach(() => {
  refreshUniverseMomentum.mockReset();
});

const view = (onNavigate = vi.fn()) => {
  render(<DiagnosticsView run={null} setRun={vi.fn()} onNavigate={onNavigate} />);
  return onNavigate;
};

describe("「개발·실험용」 미사용 기능 이동 안내", () => {
  it("[미사용 기능] 버튼 · 구역 · 갱신 패널이 없다", () => {
    view();
    expect(screen.queryByRole("button", { name: "미사용 기능" })).toBeNull();
    expect(screen.queryByTestId("diag-unused")).toBeNull();
    expect(screen.queryByRole("button", { name: /신규 ETF 관찰 후보 갱신/ })).toBeNull();
    expect(document.body.textContent).not.toContain("어떤 기능 수행");
  });

  it("옮긴 곳 한 줄 + 이동 버튼 → onNavigate('unused_universe_watch')", () => {
    const onNavigate = view();
    const line = screen.getByTestId("diag-unused-moved");
    expect(line.textContent).toContain("미사용 기능은 「진단·상태 › 미사용 기능」으로 옮겼습니다");
    const btn = within(line).getByRole("button", { name: "「신규 ETF 관찰 점검」으로" });
    expect(onNavigate).not.toHaveBeenCalled();
    fireEvent.click(btn);
    expect(onNavigate).toHaveBeenCalledTimes(1);
    expect(onNavigate).toHaveBeenCalledWith("unused_universe_watch");
  });

  it("안내 줄은 미리보기 · LEGACY 보다 위 · 화면을 열기만 해서는 갱신 요청 0", () => {
    view();
    const line = screen.getByTestId("diag-unused-moved");
    const preview = screen.getByText("미리보기 자리");
    expect(line.compareDocumentPosition(preview) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(refreshUniverseMomentum).not.toHaveBeenCalled();
  });
});
