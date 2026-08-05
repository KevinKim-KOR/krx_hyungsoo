// POC3-03 Navigation IA + POC3-07 운영/진단 화면 분리 — 좌측 메뉴 그룹 test.
//
// 2026-08-05 POC3-07 갱신:
// - data_status 흡수 + dashboard(LEGACY) 이동 → "진단·상태"(diagnostics) 그룹.
// - "승인·운영" 라벨 "승인·알림" → "승인·적용"(§5.4·§10.1).
// - MenuKey 11→10 (dashboard·data_status 제거, diagnostics 추가).
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import LeftSidebar, {
  MENU_GROUPS,
  MENU_ITEMS,
  type MenuKey,
} from "./LeftSidebar";

const ALL_KEYS: MenuKey[] = [
  "today_check",
  "workbench",
  "market_discovery",
  "etf_exposure",
  "ai_sessions",
  "holdings",
  "holdings_manage",
  "holdings_evidence",
  "approval",
  "diagnostics",
];

const GROUP_TITLES = [
  "오늘 확인",
  "비교·판단",
  "보유·자료 관리",
  "승인·운영",
  "진단·상태",
];

// AC-8 금지 내부 명칭 (사용자 화면 비노출).
const FORBIDDEN = [
  "Workbench",
  "Market Discovery",
  "Holdings",
  "ETF Exposure",
  "Data Status",
  "Operations Panel",
];

describe("LeftSidebar 그룹 구조 (POC3-03 · POC3-07 · 5그룹)", () => {
  it("AC-1: 그룹 제목이 순서대로 표시된다 (오늘/비교·판단/보유·자료/승인·운영/진단·상태)", () => {
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    const titles = screen
      .getAllByRole("button", { expanded: true })
      .map((b) => b.textContent?.replace(/[▸▾]/g, "").trim());
    for (const t of GROUP_TITLES) {
      expect(screen.getByText(t)).toBeTruthy();
    }
    expect(MENU_GROUPS.map((g) => g.title)).toEqual(GROUP_TITLES);
    expect(titles.length).toBe(GROUP_TITLES.length);
  });

  it("AC-2: 10개 key 가 그룹에 정확히 1회씩 귀속(중복·누락·신규 0)", () => {
    const keys = MENU_GROUPS.flatMap((g) => g.items.map((i) => i.key));
    expect(keys.sort()).toEqual([...ALL_KEYS].sort());
    expect(new Set(keys).size).toBe(10);
    expect(keys.length).toBe(10);
    expect(MENU_ITEMS.map((i) => i.key).sort()).toEqual([...ALL_KEYS].sort());
  });

  it("B-1: 모든 MenuKey 가 정확히 1개 그룹에 귀속된다 (모듈 invariant — 누락 시 로드 throw)", () => {
    for (const key of ALL_KEYS) {
      const owners = MENU_GROUPS.filter((g) => g.items.some((i) => i.key === key));
      expect(owners.length).toBe(1);
    }
    expect(() =>
      render(<LeftSidebar active="today_check" onSelect={() => {}} />)
    ).not.toThrow();
  });

  it("보완1: 최초 진입 시 모든 그룹이 펼쳐진다", () => {
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    const groupTitles = screen.getAllByRole("button", { expanded: true });
    expect(groupTitles.length).toBe(GROUP_TITLES.length);
    for (const item of MENU_ITEMS) {
      expect(screen.getByText(item.label)).toBeTruthy();
    }
  });

  it("AC-4 + 보완2: 선택 메뉴와 그 메뉴가 속한 그룹이 함께 활성 표시된다", () => {
    render(<LeftSidebar active="holdings" onSelect={() => {}} />);
    const activeMenu = screen.getByText("보유 현황").closest("button");
    expect(activeMenu?.getAttribute("aria-current")).toBe("page");
    const groupTitle = screen.getByText("보유·자료 관리").closest(".sidebar-group");
    expect(groupTitle?.className).toContain("active-group");
    const otherGroup = screen.getByText("오늘 확인").closest(".sidebar-group");
    expect(otherGroup?.className).not.toContain("active-group");
  });

  it("AC-6: 그룹 제목 클릭은 접기/펼치기만 하고 onSelect(화면전환) 를 부르지 않는다", () => {
    const onSelect = vi.fn();
    render(<LeftSidebar active="today_check" onSelect={onSelect} />);
    const compareTitle = screen.getByText("비교·판단").closest("button")!;
    expect(compareTitle.getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(compareTitle);
    expect(compareTitle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("ETF 비교하기")).toBeNull();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("메뉴 클릭은 onSelect(key) 를 부른다", () => {
    const onSelect = vi.fn();
    render(<LeftSidebar active="today_check" onSelect={onSelect} />);
    fireEvent.click(screen.getByText("ETF 비교하기"));
    expect(onSelect).toHaveBeenCalledWith("workbench");
  });

  it("AC-5/보완3: 접힌 그룹으로 active 가 바뀌면 그 그룹만 자동 펼치고 다른 접힘은 유지", () => {
    const { rerender } = render(
      <LeftSidebar active="today_check" onSelect={() => {}} />
    );
    fireEvent.click(screen.getByText("보유·자료 관리").closest("button")!);
    fireEvent.click(screen.getByText("비교·판단").closest("button")!);
    expect(screen.queryByText("보유 현황")).toBeNull();
    expect(screen.queryByText("ETF 비교하기")).toBeNull();

    rerender(<LeftSidebar active="holdings" onSelect={() => {}} />);
    expect(screen.getByText("보유 현황")).toBeTruthy();
    expect(screen.queryByText("ETF 비교하기")).toBeNull();
  });

  it("AC-8: 내부 명칭이 사용자 화면에 노출되지 않는다 (label·hint·그룹명·aria)", () => {
    const { container } = render(
      <LeftSidebar active="today_check" onSelect={() => {}} />
    );
    const text = container.textContent ?? "";
    for (const bad of FORBIDDEN) {
      expect(text).not.toContain(bad);
    }
    const withAttrs = container.querySelectorAll("[title],[aria-label]");
    withAttrs.forEach((el) => {
      const t = (el.getAttribute("title") ?? "") + (el.getAttribute("aria-label") ?? "");
      for (const bad of FORBIDDEN) {
        expect(t).not.toContain(bad);
      }
    });
  });

  it("승인·운영 그룹은 승인·적용 메뉴 1개만 (정보 PUSH 카드·자리표시자 없음)", () => {
    const ops = MENU_GROUPS.find((g) => g.title === "승인·운영")!;
    expect(ops.items.map((i) => i.label)).toEqual(["승인·적용"]);
  });

  it("진단·상태 그룹은 diagnostics 1개이며 승인·운영 뒤에 온다 (POC3-07 §5.3)", () => {
    const diag = MENU_GROUPS.find((g) => g.title === "진단·상태")!;
    expect(diag.items.map((i) => i.key)).toEqual(["diagnostics"]);
    const order = MENU_GROUPS.map((g) => g.title);
    expect(order.indexOf("진단·상태")).toBe(order.indexOf("승인·운영") + 1);
    // 제거된 key 는 어디에도 없다.
    const allKeys = MENU_GROUPS.flatMap((g) => g.items.map((i) => i.key));
    expect(allKeys).not.toContain("dashboard" as MenuKey);
    expect(allKeys).not.toContain("data_status" as MenuKey);
  });

  it("보완2: 진단·상태 선택 시 그 그룹이 활성 표시된다", () => {
    render(<LeftSidebar active="diagnostics" onSelect={() => {}} />);
    const grp = screen.getByText("진단·상태").closest(".sidebar-group");
    expect(grp?.className).toContain("active-group");
  });

  it("승인·적용 라벨은 슬래시 표기가 아니다", () => {
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    expect(screen.getByText("승인·적용")).toBeTruthy();
    expect(screen.queryByText("승인 / 적용")).toBeNull();
  });
});
