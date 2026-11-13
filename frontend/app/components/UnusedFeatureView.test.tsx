// POC6-29 보완 — 「진단·상태 › 미사용 기능 › 신규 ETF 관찰 점검」(보완 PLAN 판정 2026-11-12 Q-R5 · RESULT 판정 §4 ·
// PLAN §9-4 · 목업 R4).
//
// - 펼치지 않고 읽는다: 제목 · 「미사용 기능」 배지 · 세 줄(어떤 기능이었는지 · 왜 빠졌는지 · 지금 어디서) · 실행 버튼 ·
//   [「개발·실험용」으로].
// - 화면을 열기만 해서는 갱신(외부 조회 · 파일 덮어쓰기) 요청 0 · 버튼을 누를 때만 1회(기존 패널 그대로).
// - 「자세히」는 처음엔 접힘 · 없앤 「요즘 잘 오르는 ETF」의 기능별 옮긴 곳 · 옮긴 메뉴로 가는 버튼 · 보관 경로는 이 안에만.
// - 관통(실제 MainPanel · 사이드바): 메뉴 → 페이지 → 「개발·실험용」 → 안내 줄 버튼 → 다시 페이지.
//
// @/lib/api 는 부분 mock — 갱신 요청(refreshUniverseMomentum)만 바꿔 호출 수를 센다.
// 첫 화면(「오늘의 투자 점검」)과 「개발·실험용」의 미리보기 · 호환 점검 · LEGACY 대시보드는 이 계약(메뉴 → 화면 연결)과
// 무관해 가짜로 바꾼다(실제 네트워크 · 운영 자료 미의존 · 그 화면들의 조회 · 변경과 무관하게 이동만 본다).
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, within, act } from "@testing-library/react";

const refreshUniverseMomentum = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    refreshUniverseMomentum: (...a: unknown[]) => refreshUniverseMomentum(...a),
  };
});
vi.mock("./TodayInvestmentCheckView", () => ({
  default: () => <h1>오늘의 투자 점검</h1>,
}));
vi.mock("./approval/ManualPreviewSection", () => ({ default: () => <div>미리보기 자리</div> }));
vi.mock("./approval/DevCompatSection", () => ({ default: () => <div>호환 점검 자리</div> }));
vi.mock("./DashboardView", () => ({ default: () => <div>LEGACY 자리</div> }));

import MainPanel from "./MainPanel";
import UnusedFeatureView from "./UnusedFeatureView";

beforeEach(() => {
  vi.clearAllMocks();
  refreshUniverseMomentum.mockImplementation(() => Promise.reject(new Error("test: 갱신 실패")));
});

const page = (onNavigate = vi.fn()) => {
  render(<UnusedFeatureView feature="universe_watch" onNavigate={onNavigate} />);
  return onNavigate;
};
const details = () => screen.getByTestId("unused-details") as HTMLDetailsElement;

// 접힌 「자세히」 밖(펼치지 않고 보이는 곳)의 글자.
function textOutsideDetails(): string {
  const root = screen.getByRole("heading", { level: 1 }).closest("section")!.cloneNode(true) as HTMLElement;
  root.querySelectorAll("details").forEach((d) => d.remove());
  return root.textContent ?? "";
}

describe("「신규 ETF 관찰 점검」 페이지", () => {
  it("펼치지 않고 제목 · 배지 · 세 줄 · 실행 버튼 · 이동 버튼이 보인다", () => {
    page();
    expect(screen.getByRole("heading", { level: 1, name: "신규 ETF 관찰 점검" })).toBeInTheDocument();
    expect(screen.getByText("미사용 기능")).toHaveClass("tc-badge");
    const lines = screen.getByTestId("unused-lines");
    expect(lines.closest("details")).toBeNull();
    expect(Array.from(lines.querySelectorAll("dt")).map((d) => d.textContent)).toEqual([
      "어떤 기능이었는지",
      "왜 빠졌는지",
      "지금 어디서",
    ]);
    const dd = Array.from(lines.querySelectorAll("dd")).map((d) => d.textContent);
    expect(dd[0]).toBe(
      "기존 후보군에서 pykrx 1개월 수익률이 가장 높은 ETF 한 종목을 수동으로 찾습니다. 두 실험용 초안이 그 결과를 읽습니다.",
    );
    expect(dd[1]).toBe(
      "일상 ETF 탐색을 「후보리스트」로 통합했습니다. 이 기능은 실험용 수동 초안에서 쓰기 때문에 별도 메뉴로 옮겼습니다.",
    );
    expect(dd[2]).toContain("이 페이지에서 실행합니다.");
    expect(dd[2]).toContain("「개발·실험용」 › 미리보기 · 수동 전달 점검의 'PUSH-2 보유 관찰 브리핑 초안' · 'PUSH-3 급등락 관찰 신호 초안'");
    const run = screen.getByRole("button", { name: "신규 ETF 관찰 후보 갱신" });
    const back = screen.getByRole("button", { name: "「개발·실험용」으로" });
    expect(run.closest("details")).toBeNull();
    expect(back.closest("details")).toBeNull();
    // 순서 = 세 줄 → 실행 → 이동 → 자세히(기능마다 같은 틀).
    expect(lines.compareDocumentPosition(run) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(run.compareDocumentPosition(back) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(back.compareDocumentPosition(details()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("화면을 열기만 해서는 갱신 요청 0 · 실행 버튼을 누를 때만 1회", async () => {
    page();
    expect(refreshUniverseMomentum).not.toHaveBeenCalled();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "신규 ETF 관찰 후보 갱신" }));
    });
    expect(refreshUniverseMomentum).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/test: 갱신 실패/)).toBeInTheDocument();
  });

  it("[「개발·실험용」으로] → onNavigate('diagnostics')", () => {
    const onNavigate = page();
    fireEvent.click(screen.getByRole("button", { name: "「개발·실험용」으로" }));
    expect(onNavigate).toHaveBeenCalledTimes(1);
    expect(onNavigate).toHaveBeenCalledWith("diagnostics");
  });

  it("「자세히」 처음엔 접힘 · 기능별 옮긴 곳 · 보관 경로는 이 안에만", () => {
    page();
    const d = details();
    expect(d.open).toBe(false);
    expect(d.querySelector("summary")?.textContent).toBe("자세히 · 없앤 「요즘 잘 오르는 ETF」의 기능별 옮긴 곳");
    const t = d.textContent ?? "";
    for (const s of [
      "「후보리스트」 [목록 | 표]",
      "「보유와 후보 비교」",
      "「오늘의 투자 점검」 시장 흐름 · [시장 근거와 다른 변화 보기]",
      "「오늘의 투자 점검」 [최신 자료 갱신]",
      "「후보리스트」 「이 목록으로 할 일」",
      "화면마다 [이 기준을 기본으로]",
      "「오늘의 투자 점검」 「보유 점검」 · 「잘 오르는 ETF」 카드",
      "archive/poc6_29_market_discovery/README.md",
    ]) {
      expect(t).toContain(s);
    }
    const outside = textOutsideDetails();
    expect(outside).not.toContain("archive/");
    expect(outside).not.toContain("README");
    expect(outside).not.toContain("요즘 잘 오르는 ETF");
  });

  it("「자세히」의 이동 버튼 = 옮긴 메뉴(후보리스트 · 보유와 후보 비교 · 오늘의 투자 점검)", () => {
    const onNavigate = page();
    fireEvent.click(details().querySelector("summary")!);
    const buttons = within(details()).getAllByRole("button");
    const pairs: [string, string][] = [];
    for (const b of buttons) {
      onNavigate.mockClear();
      fireEvent.click(b);
      expect(onNavigate).toHaveBeenCalledTimes(1);
      pairs.push([b.textContent ?? "", onNavigate.mock.calls[0][0] as string]);
    }
    expect(new Set(pairs.map(([label, key]) => `${label}=${key}`))).toEqual(
      new Set([
        "「후보리스트」로=workbench",
        "「보유와 후보 비교」로=holding_candidate_compare",
        "「오늘의 투자 점검」으로=today_check",
      ]),
    );
    expect(refreshUniverseMomentum).not.toHaveBeenCalled();
  });
});

// --- 관통(실제 MainPanel · 사이드바) -------------------------------------------------------------

const sidebar = () => screen.getByRole("complementary", { name: "좌측 메뉴" });
const menu = (label: string) => within(sidebar()).getByText(label).closest("button")!;

async function renderPanel() {
  const r = render(<MainPanel />);
  await act(async () => {
    await new Promise((res) => setTimeout(res, 0));
  });
  return r;
}

describe("MainPanel 「미사용 기능 › 신규 ETF 관찰 점검」 관통", () => {
  it("메뉴 → 페이지(요청 0) · 사이드바 현재 위치 = 그 메뉴 하나 · 폴더 펼침", async () => {
    await renderPanel();
    fireEvent.click(menu("신규 ETF 관찰 점검"));
    expect(await screen.findByRole("heading", { level: 1, name: "신규 ETF 관찰 점검" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1, name: "오늘의 투자 점검" })).toBeNull();
    expect(screen.getByRole("button", { name: "신규 ETF 관찰 후보 갱신" })).toBeInTheDocument();
    expect(refreshUniverseMomentum).not.toHaveBeenCalled();
    const current = within(sidebar())
      .getAllByRole("button")
      .filter((b) => b.getAttribute("aria-current") === "page");
    expect(current).toHaveLength(1);
    expect(current[0].textContent).toContain("신규 ETF 관찰 점검");
    const folder = within(sidebar()).getByText("미사용 기능").closest("button")!;
    expect(folder).toHaveAttribute("aria-expanded", "true");
    expect(folder.closest("li")?.className).toContain("active-folder");
  });

  it("페이지 → 「개발·실험용」 → 안내 줄 버튼 → 다시 페이지 · 갱신 요청 0", async () => {
    await renderPanel();
    fireEvent.click(menu("신규 ETF 관찰 점검"));
    await screen.findByRole("heading", { level: 1, name: "신규 ETF 관찰 점검" });
    fireEvent.click(screen.getByRole("button", { name: "「개발·실험용」으로" }));
    expect(await screen.findByRole("heading", { level: 1, name: "개발·실험용" })).toBeInTheDocument();
    expect(screen.getByText("미리보기 자리")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "신규 ETF 관찰 후보 갱신" })).toBeNull();
    const line = screen.getByTestId("diag-unused-moved");
    fireEvent.click(within(line).getByRole("button", { name: "「신규 ETF 관찰 점검」으로" }));
    expect(await screen.findByRole("heading", { level: 1, name: "신규 ETF 관찰 점검" })).toBeInTheDocument();
    expect(refreshUniverseMomentum).not.toHaveBeenCalled();
  });
});
