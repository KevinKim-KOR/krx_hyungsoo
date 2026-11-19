// 「개발·실험용」 미사용 기능 이동 안내(POC6-29 보완 · 보완 PLAN 판정 2026-11-12 Q-R5 · RESULT 판정 §4).
// [신규 ETF 관찰 후보 갱신]은 처음엔 이 화면 맨 아래 「미사용 기능」 구역(맨 위 [미사용 기능] 버튼)에 두었다가
// 사이드바 「진단·상태 › 미사용 기능 › 신규 ETF 관찰 점검」(`unused_universe_watch`)으로 옮겼다.
// 2026-11-19 형수님 직접 지시: 「미사용 기능」 = 그룹(폴더 아님) · 이 화면(「개발·실험용」)도 그 그룹 →
//   안내 줄 = '「신규 ETF 관찰 점검」은 같은 「미사용 기능」 메뉴에 있습니다.'(버튼 그대로 · '진단·상태' 없음).
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
    expect(line.textContent).toContain("「신규 ETF 관찰 점검」은 같은 「미사용 기능」 메뉴에 있습니다.");
    expect(line.textContent).not.toContain("진단·상태");
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

// POC6-34(PLAN N6 · I-34) — 설명 문단의 메뉴 이름 = 「ETF NAV·괴리율 조회」(옛 이름 「데이터 상태」 없음).
describe("「개발·실험용」 설명 문단의 메뉴 이름", () => {
  it("'ETF NAV·괴리율 조회와 ML 연구는 각각 별도 메뉴로, …' · 옛 이름 없음", () => {
    view();
    const para = screen.getByText(/정상 업무 화면이 아닙니다\./);
    expect(para.textContent?.replace(/\s+/g, " ").trim()).toBe(
      "정상 업무 화면이 아닙니다. 미리보기·샘플(PREVIEW/TEST), 개발 호환 점검, 참고용 이전 화면(LEGACY)을 이곳에서 관리합니다. " +
        "ETF NAV·괴리율 조회와 ML 연구는 각각 별도 메뉴로, OCI 운영 상태는 「OCI 운영·적용」으로 옮겼습니다.",
    );
    expect(document.body.textContent).not.toContain("데이터 상태");
  });
});
