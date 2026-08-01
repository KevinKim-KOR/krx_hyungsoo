// POC3-03 Navigation Information Architecture v1 — 좌측 메뉴 그룹 재편 test.
// (설계서 4그룹 + 사용자 실화면 지시로 "점검대상" 분리 → 총 5그룹.)
//
// 검증 대상 (설계서 §3·§4·§6 + AC + 보완사항):
// - AC-1: 좌측 메뉴가 오늘 확인 / 비교·판단 / 보유·자료 관리 / 승인·운영 / 점검대상 그룹으로 표시.
// - AC-2: 9개 화면 전환 key 가 정확히 한 그룹에 1회 귀속(중복·누락·신규 0).
// - AC-4: 선택 화면과 좌측 메뉴 활성 표시 일치.
// - AC-5/보완3: 접힌 그룹으로 내부 이동 시 그 그룹 자동 펼침, 다른 그룹 접힘 유지.
// - AC-6: 그룹 접기·펼치기는 화면 전환(onSelect) 을 발생시키지 않는다.
// - AC-8: 내부 명칭(Workbench/Market Discovery/Holdings/ETF Exposure/Data Status/
//   Operations Panel) 이 사용자 문구로 노출되지 않는다.
// - 보완1: 최초 진입 시 모든 그룹 펼쳐진 상태.
// - 보완2: 현재 메뉴가 속한 그룹도 활성 식별.
// - AC-11: 메뉴명이 한 글자씩 세로 줄바꿈되지 않는다(구조 — nowrap 클래스).
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import LeftSidebar, {
  MENU_GROUPS,
  MENU_ITEMS,
  type MenuKey,
} from "./LeftSidebar";

const ALL_KEYS: MenuKey[] = [
  "today_check",
  "dashboard",
  "workbench",
  "market_discovery",
  "etf_exposure",
  "ai_sessions",
  "holdings",
  "approval",
  "data_status",
];

// 2026-08-01 사용자 요청 — "기존 대시보드" 를 "점검대상" 그룹으로 분리(§3.2·Q2 재편).
const GROUP_TITLES = [
  "오늘 확인",
  "비교·판단",
  "보유·자료 관리",
  "승인·운영",
  "점검대상",
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

describe("LeftSidebar 그룹 구조 (POC3-03 · 5그룹)", () => {
  it("AC-1: 그룹 제목이 순서대로 표시된다 (오늘/비교·판단/보유·자료/승인·운영/점검대상)", () => {
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    const titles = screen
      .getAllByRole("button", { expanded: true })
      .map((b) => b.textContent?.replace(/[▸▾]/g, "").trim());
    for (const t of GROUP_TITLES) {
      expect(screen.getByText(t)).toBeTruthy();
    }
    // MENU_GROUPS 순서 = 확정 순서.
    expect(MENU_GROUPS.map((g) => g.title)).toEqual(GROUP_TITLES);
    expect(titles.length).toBe(GROUP_TITLES.length);
  });

  it("AC-2: 9개 key 가 그룹에 정확히 1회씩 귀속(중복·누락·신규 0)", () => {
    const keys = MENU_GROUPS.flatMap((g) => g.items.map((i) => i.key));
    expect(keys.sort()).toEqual([...ALL_KEYS].sort());
    expect(new Set(keys).size).toBe(9);
    expect(keys.length).toBe(9);
    // 평탄화 export 도 동일.
    expect(MENU_ITEMS.map((i) => i.key).sort()).toEqual([...ALL_KEYS].sort());
  });

  it("B-1: 모든 MenuKey 가 정확히 1개 그룹에 귀속된다 (모듈 invariant — 누락 시 로드 throw)", () => {
    // LeftSidebar 모듈은 로드 시 assertMenuGroupsCover() 로 귀속 무결성을 검증하고,
    // 누락·중복이면 즉시 throw 한다(fallback 위장 없음). 이 테스트가 실행된다는 것 자체가
    // import 시 throw 되지 않았다는 뜻 = invariant 통과. 아래는 그 계약을 명시적으로 재확인.
    for (const key of ALL_KEYS) {
      const owners = MENU_GROUPS.filter((g) => g.items.some((i) => i.key === key));
      expect(owners.length).toBe(1); // 0개(누락)도 2개(중복)도 아님
    }
    // 렌더도 오류 없이 된다(활성 그룹 판정이 항상 유효 = 조용한 표시오류 경로 없음).
    expect(() =>
      render(<LeftSidebar active="today_check" onSelect={() => {}} />)
    ).not.toThrow();
  });

  it("보완1: 최초 진입 시 모든 그룹이 펼쳐진다", () => {
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    const groupTitles = screen.getAllByRole("button", { expanded: true });
    // 접힘 토글(aria-expanded) 를 가진 그룹 제목이 전부 expanded=true.
    expect(groupTitles.length).toBe(GROUP_TITLES.length);
    // 각 그룹의 메뉴가 실제로 보인다(9개 메뉴 버튼 노출).
    for (const item of MENU_ITEMS) {
      expect(screen.getByText(item.label)).toBeTruthy();
    }
  });

  it("AC-4 + 보완2: 선택 메뉴와 그 메뉴가 속한 그룹이 함께 활성 표시된다", () => {
    render(<LeftSidebar active="holdings" onSelect={() => {}} />);
    // 선택 메뉴: aria-current=page
    const activeMenu = screen.getByText("내가 가진 ETF").closest("button");
    expect(activeMenu?.getAttribute("aria-current")).toBe("page");
    // 그 메뉴가 속한 그룹(보유·자료 관리) 이 active-group 클래스.
    const groupTitle = screen.getByText("보유·자료 관리").closest(".sidebar-group");
    expect(groupTitle?.className).toContain("active-group");
    // 다른 그룹은 active-group 아님.
    const otherGroup = screen.getByText("오늘 확인").closest(".sidebar-group");
    expect(otherGroup?.className).not.toContain("active-group");
  });

  it("AC-6: 그룹 제목 클릭은 접기/펼치기만 하고 onSelect(화면전환) 를 부르지 않는다", () => {
    const onSelect = vi.fn();
    render(<LeftSidebar active="today_check" onSelect={onSelect} />);
    const compareTitle = screen.getByText("비교·판단").closest("button")!;
    // 처음 펼침 → 클릭 → 접힘.
    expect(compareTitle.getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(compareTitle);
    expect(compareTitle.getAttribute("aria-expanded")).toBe("false");
    // 접히면 그 그룹 메뉴가 사라진다.
    expect(screen.queryByText("ETF 비교하기")).toBeNull();
    // onSelect 는 한 번도 안 불렸다.
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
    // 보유·자료 관리, 비교·판단 두 그룹을 사용자가 접는다.
    fireEvent.click(screen.getByText("보유·자료 관리").closest("button")!);
    fireEvent.click(screen.getByText("비교·판단").closest("button")!);
    expect(screen.queryByText("내가 가진 ETF")).toBeNull();
    expect(screen.queryByText("ETF 비교하기")).toBeNull();

    // 내부 이동으로 active 가 holdings(접힌 보유·자료 관리 그룹) 로 바뀐다.
    rerender(<LeftSidebar active="holdings" onSelect={() => {}} />);
    // 보유·자료 관리 그룹이 자동으로 펼쳐진다.
    expect(screen.getByText("내가 가진 ETF")).toBeTruthy();
    // 사용자가 접은 다른 그룹(비교·판단) 은 그대로 접힘 유지.
    expect(screen.queryByText("ETF 비교하기")).toBeNull();
  });

  it("AC-8: 내부 명칭이 사용자 화면에 노출되지 않는다 (label·hint·그룹명·aria)", () => {
    const { container } = render(
      <LeftSidebar active="today_check" onSelect={() => {}} />
    );
    // 보이는 텍스트 + 모든 title/aria-label 스캔.
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

  it("승인·운영 그룹은 승인·알림 메뉴 1개만 (Operations Panel·자리표시자 없음)", () => {
    const ops = MENU_GROUPS.find((g) => g.title === "승인·운영")!;
    expect(ops.items.map((i) => i.label)).toEqual(["승인·알림"]);
  });

  it("점검대상 그룹은 기존 대시보드 1개이며 승인·운영 뒤에 온다 (사용자 §3.2 재편)", () => {
    const inspect = MENU_GROUPS.find((g) => g.title === "점검대상")!;
    expect(inspect.items.map((i) => i.key)).toEqual(["dashboard"]);
    // 그룹 순서: 승인·운영 → 점검대상.
    const order = MENU_GROUPS.map((g) => g.title);
    expect(order.indexOf("점검대상")).toBe(order.indexOf("승인·운영") + 1);
    // 보유·자료 관리에는 더 이상 dashboard 가 없다.
    const manage = MENU_GROUPS.find((g) => g.title === "보유·자료 관리")!;
    expect(manage.items.some((i) => i.key === "dashboard")).toBe(false);
  });

  it("보완2: 기존 대시보드 선택 시 점검대상 그룹이 활성 표시된다", () => {
    render(<LeftSidebar active="dashboard" onSelect={() => {}} />);
    const grp = screen.getByText("점검대상").closest(".sidebar-group");
    expect(grp?.className).toContain("active-group");
    const activeMenu = screen.getByText("기존 대시보드").closest("button");
    expect(activeMenu?.getAttribute("aria-current")).toBe("page");
  });

  it("승인·알림 라벨은 슬래시 표기가 아니다 (Q1 통일)", () => {
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    expect(screen.getByText("승인·알림")).toBeTruthy();
    expect(screen.queryByText("승인 / 알림")).toBeNull();
  });
});
