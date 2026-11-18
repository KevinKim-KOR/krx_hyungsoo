// POC6-32 V2(PLAN 판정 V2 Q1 (a) · PLAN §2 S4 · §9 I-1 ~ I-5) — 상세 화면 이동 관통(실제 MainPanel · 사이드바).
//
// - 화면 안에서 상세(「보유와 후보 비교」 · 「ETF 구성종목」)를 열면 보낸 화면을 내리지 않고 숨겨 둔다 →
//   [← 보낸 화면으로]로 돌아가면 보낸 화면의 상태가 그대로(다시 그리지 않음) · 상세 → 상세는 한 단계씩.
// - 좌측 메뉴를 누르면 기록을 버리고 처음부터 · 화면 안에서 상세가 아닌 화면으로 가도 버림.
// - 상세가 열린 동안 메뉴 강조 = 처음 보낸 화면의 메뉴 · 화면이 바뀌면 맨 위(돌아갈 때도).
//
// 화면들은 상태(누른 수) · 그려진 횟수를 세는 가짜 화면으로 바꾼다 — 이 시험은 이동 장치만 본다(조회 · 자료 무관 ·
// 실제 네트워크 · 운영 자료 미의존). 실제 화면의 상태 복원은 UnusedFeatureView.test.tsx 관통 시험이 함께 본다.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";

const h = vi.hoisted(() => {
  const mounts: Record<string, number> = {};
  type R = typeof import("react");
  // 제목(h1) · 누른 수 버튼(화면 안 상태) · 이동 버튼들
  function make(react: R, title: string, links: [string, string][]) {
    return function FakeScreen({ onNavigate }: { onNavigate?: (key: string) => void }) {
      const [n, setN] = react.useState(0);
      react.useEffect(() => {
        mounts[title] = (mounts[title] ?? 0) + 1;
      }, []);
      return react.createElement(
        "section",
        null,
        react.createElement("h1", null, title),
        react.createElement("button", { type: "button", onClick: () => setN((x) => x + 1) }, `${title} 누른 수 ${n}`),
        ...links.map(([label, key]) =>
          react.createElement("button", { key: label, type: "button", onClick: () => onNavigate?.(key) }, label),
        ),
      );
    };
  }
  return { mounts, make };
});

vi.mock("./TodayInvestmentCheckView", async () => ({
  default: h.make(await import("react"), "오늘의 투자 점검", [
    ["주간 ETF 점검 열기 →", "weekly_etf_check"],
    // 화면 안 버튼으로 상세(「ETF 구성종목」)를 연다 — 실제 버튼 이름과 무관한 시험용 이름(실제 NAV 버튼은 「데이터 상태」로 감)
    ["시험용 상세 열기 →", "etf_exposure"],
  ]),
}));
vi.mock("./WeeklyEtfCheckView", async () => ({
  default: h.make(await import("react"), "주간 ETF 점검", [
    ["비교 상세", "holding_candidate_compare"],
    ["구성종목 보기", "etf_exposure"],
    ["후보리스트 보기 →", "workbench"],
  ]),
}));
vi.mock("./JudgmentWorkbenchView", async () => ({
  default: h.make(await import("react"), "후보리스트", [["비교 상세", "holding_candidate_compare"]]),
}));
vi.mock("./WorkbenchHoldingsView", async () => ({
  default: h.make(await import("react"), "보유", [["보유와 후보 비교에서 보기 →", "holding_candidate_compare"]]),
}));
vi.mock("./ETFExposureView", async () => ({
  default: h.make(await import("react"), "ETF 구성종목", [
    ["보유와 후보 비교에서 보기 →", "holding_candidate_compare"],
    ["AI 투자 세션으로 넘기기", "ai_sessions"],
  ]),
}));
vi.mock("./HoldingCandidateCompareView", async () => ({
  default: h.make(await import("react"), "보유와 후보 비교", [["AI 세션에서 검토", "ai_sessions"]]),
}));
vi.mock("./AISessionsView", async () => ({ default: h.make(await import("react"), "AI 투자 세션", []) }));

import MainPanel from "./MainPanel";

beforeEach(() => {
  for (const k of Object.keys(h.mounts)) delete h.mounts[k];
});

const sidebar = () => screen.getByRole("complementary", { name: "좌측 메뉴" });
const menu = (label: string) => {
  const btn = within(sidebar())
    .getAllByRole("button")
    .find((b) => b.querySelector(".sidebar-menu-label")?.textContent === label);
  if (!btn) throw new Error(`좌측 메뉴에 「${label}」 없음`);
  return btn;
};
const current = () =>
  within(sidebar())
    .getAllByRole("button")
    .filter((b) => b.getAttribute("aria-current") === "page")
    .map((b) => b.querySelector(".sidebar-menu-label")?.textContent);
// 보이는 화면 제목(숨겨 둔 화면은 빠짐)
const shown = () => screen.getAllByRole("heading", { level: 1 }).map((x) => x.textContent);
const click = (name: string) => fireEvent.click(screen.getByRole("button", { name }));
const backBar = () => screen.queryByTestId("dn-back");

describe("POC6-32 V2 상세 화면 이동 · 보낸 화면 복원", () => {
  it("주간 → [비교 상세] → 상세 위 [← 보낸 화면으로] · 강조 = 주간 ETF 점검 · 돌아오면 보낸 화면 상태 그대로(다시 그리지 않음)", () => {
    render(<MainPanel />);
    fireEvent.click(menu("주간 ETF 점검"));
    click("주간 ETF 점검 누른 수 0");
    click("주간 ETF 점검 누른 수 1");
    expect(backBar()).toBeNull();

    click("비교 상세");
    expect(shown()).toEqual(["보유와 후보 비교"]);
    const bar = backBar()!;
    expect(bar.textContent).toContain("보낸 화면 「주간 ETF 점검」");
    const back = within(bar).getByRole("button", { name: "← 보낸 화면으로" });
    expect(back.className).toContain("btn-md"); // 중간 버튼 40px
    expect(current()).toEqual(["주간 ETF 점검"]);
    // 보낸 화면은 내리지 않고 숨겨 둠(누른 수 2 그대로 · 화면에는 안 보임)
    const hiddenSender = screen.getByText("주간 ETF 점검 누른 수 2");
    expect(hiddenSender.closest("[hidden]")).not.toBeNull();
    expect(screen.queryByRole("button", { name: "주간 ETF 점검 누른 수 2" })).toBeNull();

    fireEvent.click(back);
    expect(shown()).toEqual(["주간 ETF 점검"]);
    expect(screen.getByRole("button", { name: "주간 ETF 점검 누른 수 2" })).toBeInTheDocument();
    expect(h.mounts["주간 ETF 점검"]).toBe(1);
    expect(backBar()).toBeNull();
    expect(screen.queryByText(/보유와 후보 비교 누른 수/)).toBeNull(); // 상세는 내림
    expect(current()).toEqual(["주간 ETF 점검"]);
  });

  it("상세 → 상세는 한 단계씩: 주간 → 구성종목 → 보유와 후보 비교 → ← 구성종목(상태 그대로) → ← 주간", () => {
    render(<MainPanel />);
    fireEvent.click(menu("주간 ETF 점검"));
    click("주간 ETF 점검 누른 수 0");
    click("구성종목 보기");
    click("ETF 구성종목 누른 수 0");
    expect(backBar()!.textContent).toContain("보낸 화면 「주간 ETF 점검」");

    click("보유와 후보 비교에서 보기 →");
    expect(shown()).toEqual(["보유와 후보 비교"]);
    expect(backBar()!.textContent).toContain("보낸 화면 「ETF 구성종목」");
    expect(current()).toEqual(["주간 ETF 점검"]); // 처음 보낸 화면

    click("← 보낸 화면으로");
    expect(shown()).toEqual(["ETF 구성종목"]);
    expect(screen.getByRole("button", { name: "ETF 구성종목 누른 수 1" })).toBeInTheDocument();
    expect(backBar()!.textContent).toContain("보낸 화면 「주간 ETF 점검」");

    click("← 보낸 화면으로");
    expect(shown()).toEqual(["주간 ETF 점검"]);
    expect(screen.getByRole("button", { name: "주간 ETF 점검 누른 수 1" })).toBeInTheDocument();
    expect(backBar()).toBeNull();
    expect(h.mounts).toEqual({ "오늘의 투자 점검": 1, "주간 ETF 점검": 1, "ETF 구성종목": 1, "보유와 후보 비교": 1 });
  });

  it("강조 = 처음 보낸 화면의 메뉴: 「후보리스트」 · 「보유」 · 「오늘의 투자 점검」에서 연 상세", () => {
    render(<MainPanel />);
    click("시험용 상세 열기 →");
    expect(shown()).toEqual(["ETF 구성종목"]);
    expect(current()).toEqual(["오늘의 투자 점검"]);
    expect(backBar()!.textContent).toContain("보낸 화면 「오늘의 투자 점검」");

    fireEvent.click(menu("후보리스트"));
    click("비교 상세");
    expect(current()).toEqual(["후보리스트"]);
    expect(backBar()!.textContent).toContain("보낸 화면 「후보리스트」");

    fireEvent.click(menu("보유"));
    click("보유와 후보 비교에서 보기 →");
    expect(current()).toEqual(["보유"]);
    expect(backBar()!.textContent).toContain("보낸 화면 「보유」");
  });

  it("상세가 열린 동안 메뉴를 누르면 기록을 버리고 처음부터(강조 중인 「주간 ETF 점검」을 눌러도 새로 그림)", () => {
    render(<MainPanel />);
    fireEvent.click(menu("주간 ETF 점검"));
    click("주간 ETF 점검 누른 수 0");
    click("비교 상세");
    fireEvent.click(menu("주간 ETF 점검"));
    expect(shown()).toEqual(["주간 ETF 점검"]);
    expect(screen.getByRole("button", { name: "주간 ETF 점검 누른 수 0" })).toBeInTheDocument();
    expect(screen.queryByText("주간 ETF 점검 누른 수 1")).toBeNull(); // 숨겨 둔 화면도 내림
    expect(screen.queryByText(/보유와 후보 비교 누른 수/)).toBeNull();
    expect(h.mounts["주간 ETF 점검"]).toBe(2);
    expect(backBar()).toBeNull();

    // 다른 메뉴도 같다
    click("구성종목 보기");
    fireEvent.click(menu("보유"));
    expect(shown()).toEqual(["보유"]);
    expect(screen.queryByText(/주간 ETF 점검 누른 수/)).toBeNull();
    expect(screen.queryByText(/ETF 구성종목 누른 수/)).toBeNull();
    expect(backBar()).toBeNull();
    expect(current()).toEqual(["보유"]);
  });

  it("화면 안에서 상세가 아닌 화면으로 가면 기록을 버림(상세 → AI 투자 세션 · 주간 → 후보리스트) · 같은 메뉴 다시 누름(기록 없음)은 그대로", () => {
    render(<MainPanel />);
    fireEvent.click(menu("주간 ETF 점검"));
    click("주간 ETF 점검 누른 수 0");
    fireEvent.click(menu("주간 ETF 점검")); // 같은 메뉴 다시 누름 = 변화 없음
    expect(screen.getByRole("button", { name: "주간 ETF 점검 누른 수 1" })).toBeInTheDocument();
    expect(h.mounts["주간 ETF 점검"]).toBe(1);

    click("비교 상세");
    click("AI 세션에서 검토");
    expect(shown()).toEqual(["AI 투자 세션"]);
    expect(backBar()).toBeNull();
    expect(current()).toEqual(["AI 투자 세션"]);
    expect(screen.queryByText(/주간 ETF 점검 누른 수/)).toBeNull();

    fireEvent.click(menu("주간 ETF 점검"));
    click("후보리스트 보기 →");
    expect(shown()).toEqual(["후보리스트"]);
    expect(backBar()).toBeNull();
    expect(current()).toEqual(["후보리스트"]);
  });

  it("오늘 화면의 [주간 ETF 점검 열기 →] = 메뉴 화면 이동(상세 아님 · 기록 없음 · 강조 = 주간 ETF 점검)", () => {
    render(<MainPanel />);
    click("주간 ETF 점검 열기 →");
    expect(shown()).toEqual(["주간 ETF 점검"]);
    expect(backBar()).toBeNull();
    expect(current()).toEqual(["주간 ETF 점검"]);
    expect(screen.queryByText(/오늘의 투자 점검 누른 수/)).toBeNull();
  });

  it("화면이 바뀌면 맨 위에서 시작 — 상세 열기 · [← 보낸 화면으로] · 메뉴 모두(새 화면이 그려진 뒤)", () => {
    const at: string[] = [];
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => {
      at.push(shown().join("|"));
    });
    try {
      render(<MainPanel />);
      expect(scrollTo).not.toHaveBeenCalled();
      fireEvent.click(menu("주간 ETF 점검"));
      click("비교 상세");
      click("← 보낸 화면으로");
      fireEvent.click(menu("주간 ETF 점검")); // 기록 없음 · 같은 메뉴 = 그대로
      expect(at).toEqual(["주간 ETF 점검", "보유와 후보 비교", "주간 ETF 점검"]);
      expect(scrollTo).toHaveBeenLastCalledWith(0, 0);
    } finally {
      scrollTo.mockRestore();
    }
  });
});
