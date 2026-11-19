// POC3-03 Navigation IA + POC3-07 운영/진단 화면 분리 — 좌측 메뉴 그룹 test.
//
// 2026-08-05 POC3-07 갱신:
// - data_status 흡수 + dashboard(LEGACY) 이동 → "진단·상태"(diagnostics) 그룹.
// - "승인·운영" 라벨 "승인·알림" → "승인·적용"(§5.4·§10.1).
// - MenuKey 11→10 (dashboard·data_status 제거, diagnostics 추가).
// - 2026-08-16: ml 추가로 10→11. 흩어져 있던 ML 카드 5개를 한 메뉴로 모음(사용자 지시).
// - 2026-08-16: data_status·oci_status 분리로 11→13. 진단 서랍에 섞여 있던 정상 업무를
//   독립 메뉴로 복원하고, 남은 diagnostics 라벨을 '개발·실험용' 으로 변경(사용자 지시).
// - 2026-09-27: 「승인·적용」+「OCI 운영 상태」를 한 화면 「OCI 운영·적용」(approval)으로
//   합쳐 oci_status 제거 → 13→12 (사용자 직접 지시).
// - 2026-10-07 POC5-03 설계 개정 2: 진단·상태에 「받은 알림 기록」(alert_records) 추가 → 12→13
//   (사용자 목업 결정 · ML 실험 바로 아래).
// - 2026-11-01 POC6-15: 「ML 실험」 → 「ML 연구」 폴더(한 단계 · key 없음) · 예측과 결과 비교(`ml`)
//   · 이전 자료·실험(`ml_legacy`) → 13→14. 폴더 버튼도 aria-expanded 를 가져 그룹 제목 수 셈에서 뺀다.
// - 2026-11-12 POC6-29(설계 §3 · PLAN 판정 Q3 · Q17): 「비교·판단」 → 「ETF보유 및 후보 선정」 · 「ETF 비교하기」 폴더 없앰 ·
//   보유 · 섹터요약(etf_sector) · 후보리스트(workbench) · 보유와 후보 비교(holding_candidate_compare) · ETF 구성종목 ·
//   AI 투자 세션을 바로 둔다. 「요즘 잘 오르는 ETF」(market_discovery) 없앰 → 15→16.
// - 2026-11-12 POC6-29 보완(보완 PLAN 판정 Q-R5 · RESULT 판정 §4): 「진단·상태」 끝(「개발·실험용」 다음)에 폴더
//   「미사용 기능」 › 「신규 ETF 관찰 점검」(unused_universe_watch) → 16→17.
// - 2026-11-17 POC6-32 V2(PLAN 판정 V2 Q1 (a) · PLAN §2 S1 · S4 · §9 I-4): 「오늘 확인」에 「주간 ETF 점검」(weekly_etf_check) 추가 ·
//   「보유와 후보 비교」(holding_candidate_compare) · 「ETF 구성종목」(etf_exposure)은 메뉴에서 뺀 상세 화면(key 는 그대로) →
//   메뉴 key 16개(정확히 1번) · 상세 key 2개(0번). 상세가 열린 동안 강조 = 넘겨받은 화면의 메뉴(상세 key 그대로면 「주간 ETF 점검」).
// - 2026-11-19 POC6-34(PLAN 판정 Q7 · PLAN N1 · N2 · I-27): `data_status` 이름 「데이터 상태」 → 「ETF NAV·괴리율 조회」 ·
//   힌트 '전체 ETF · 수집 상태 · 큰 괴리 찾기'(key · 자리 그대로).
// - 2026-11-19 형수님 직접 지시(메뉴 순서 · 단계 · key · 이름 · 힌트 그대로): 그룹 5 → 7 = 오늘 확인 → ETF보유 및 후보 선정 →
//   보유·자료 관리 → 진단·상태(ETF NAV·괴리율 조회만) → 승인·운영(OCI 운영·적용 · 받은 알림 기록) → ML 연구(폴더 → 그룹) →
//   미사용 기능(폴더 → 그룹 · 신규 ETF 관찰 점검 · 개발·실험용). MENU_GROUPS 에 폴더가 없어 폴더 전용 동작(접힌 폴더 줄의
//   현재 위치 표시 · 폴더 자동 펼침)은 실제 메뉴로 시험할 수 없다 — 그 단언은 뺐다(폴더 틀 코드는 LeftSidebar.tsx 에 그대로).
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import LeftSidebar, {
  DETAIL_KEYS,
  MENU_GROUPS,
  MENU_ITEMS,
  groupMenuItems,
  isDetailKey,
  isMenuFolder,
  menuKeyOf,
  screenLabelOf,
  type MenuKey,
} from "./LeftSidebar";

// 메뉴에 정확히 1번 나오는 key(16개).
const ALL_KEYS: MenuKey[] = [
  "today_check",
  "weekly_etf_check",
  "workbench",
  "workbench_holdings",
  "etf_sector",
  "ai_sessions",
  "holdings",
  "holdings_manage",
  "holdings_evidence",
  "approval",
  "diagnostics",
  "ml",
  "ml_legacy",
  "alert_records",
  "data_status",
  "unused_universe_watch",
];
// 메뉴에 없는 상세 key(화면 안에서만 엶 · 메뉴에 0번).
const DETAIL: MenuKey[] = ["etf_exposure", "holding_candidate_compare"];

// 2026-11-19 형수님 직접 지시 — 7개 그룹 순서.
const GROUP_TITLES = [
  "오늘 확인",
  "ETF보유 및 후보 선정",
  "보유·자료 관리",
  "진단·상태",
  "승인·운영",
  "ML 연구",
  "미사용 기능",
];
const GROUP_IDS = ["today", "compare", "manage", "diagnostics", "ops", "ml_research", "unused_features"];

// AC-8 금지 내부 명칭 (사용자 화면 비노출).
const FORBIDDEN = [
  "Workbench",
  "Market Discovery",
  "Holdings",
  "ETF Exposure",
  "Data Status",
  "Operations Panel",
];

describe("LeftSidebar 그룹 구조 (POC3-03 · POC3-07 · 2026-11-19 7그룹)", () => {
  it("AC-1: 그룹 제목이 순서대로 표시된다 (오늘/ETF보유 및 후보 선정/보유·자료/진단·상태/승인·운영/ML 연구/미사용 기능)", () => {
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    const titles = screen
      .getAllByRole("button", { expanded: true })
      .filter((b) => b.classList.contains("sidebar-group-title"))
      .map((b) => b.textContent?.replace(/[▸▾]/g, "").trim());
    for (const t of GROUP_TITLES) {
      expect(screen.getByText(t)).toBeTruthy();
    }
    expect(MENU_GROUPS.map((g) => g.title)).toEqual(GROUP_TITLES);
    expect(MENU_GROUPS.map((g) => g.id)).toEqual(GROUP_IDS);
    // 화면에 그려진 그룹 제목도 같은 순서.
    expect(titles).toEqual(GROUP_TITLES);
  });

  it("2026-11-19: MENU_GROUPS 에 폴더가 남아 있지 않다(ML 연구 · 미사용 기능 = 그룹) · 화면에도 폴더 줄 없음", () => {
    for (const g of MENU_GROUPS) {
      for (const e of g.items) expect(isMenuFolder(e)).toBe(false);
    }
    const { container } = render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    expect(container.querySelector(".sidebar-folder")).toBeNull();
    expect(container.querySelector(".sidebar-folder-btn")).toBeNull();
    expect(container.querySelector(".sidebar-submenu")).toBeNull();
  });

  it("AC-2: 메뉴 key 16개가 그룹에 정확히 1회씩 귀속(폴더 하위 포함 · 중복·누락·신규 0) · 상세 key 2개는 메뉴에 0번(POC6-32 V2)", () => {
    const keys = MENU_GROUPS.flatMap((g) => groupMenuItems(g).map((i) => i.key));
    expect(keys.sort()).toEqual([...ALL_KEYS].sort());
    expect(new Set(keys).size).toBe(16);
    expect(keys.length).toBe(16);
    expect(MENU_ITEMS.map((i) => i.key).sort()).toEqual([...ALL_KEYS].sort());
    expect([...DETAIL_KEYS].sort()).toEqual([...DETAIL].sort());
    for (const key of DETAIL) expect(keys).not.toContain(key);
  });

  it("B-1: 메뉴 key 는 정확히 1개 그룹 · 상세 key 는 0개 그룹에 귀속된다 (모듈 invariant — 어기면 로드 throw)", () => {
    for (const key of ALL_KEYS) {
      const owners = MENU_GROUPS.filter((g) => groupMenuItems(g).some((i) => i.key === key));
      expect(owners.length).toBe(1);
      expect(isDetailKey(key)).toBe(false);
    }
    for (const key of DETAIL) {
      const owners = MENU_GROUPS.filter((g) => groupMenuItems(g).some((i) => i.key === key));
      expect(owners.length).toBe(0);
      expect(isDetailKey(key)).toBe(true);
    }
    expect(() =>
      render(<LeftSidebar active="today_check" onSelect={() => {}} />)
    ).not.toThrow();
  });

  it("보완1: 최초 진입 시 모든 그룹이 펼쳐진다", () => {
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    const groupTitles = screen
      .getAllByRole("button", { expanded: true })
      .filter((b) => b.classList.contains("sidebar-group-title"));
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
    const compareTitle = screen.getByText("ETF보유 및 후보 선정").closest("button")!;
    expect(compareTitle.getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(compareTitle);
    expect(compareTitle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("후보리스트")).toBeNull();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("메뉴 클릭은 onSelect(key) 를 부른다", () => {
    const onSelect = vi.fn();
    render(<LeftSidebar active="today_check" onSelect={onSelect} />);
    // 2026-11-12 POC6-29: 기존 workbench key = 「후보리스트」(폴더 없음).
    fireEvent.click(screen.getByText("후보리스트"));
    expect(onSelect).toHaveBeenCalledWith("workbench");
    fireEvent.click(screen.getByText("섹터요약"));
    expect(onSelect).toHaveBeenCalledWith("etf_sector");
    // 2026-11-17 POC6-32 V2 — 「보유와 후보 비교」는 메뉴에 없다(상세) · 「주간 ETF 점검」 = weekly_etf_check.
    expect(screen.queryByText("보유와 후보 비교")).toBeNull();
    fireEvent.click(screen.getByText("주간 ETF 점검"));
    expect(onSelect).toHaveBeenCalledWith("weekly_etf_check");
    expect(onSelect).toHaveBeenCalledTimes(3);
  });

  it("AC-5/보완3: 접힌 그룹으로 active 가 바뀌면 그 그룹만 자동 펼치고 다른 접힘은 유지", () => {
    const { rerender } = render(
      <LeftSidebar active="today_check" onSelect={() => {}} />
    );
    fireEvent.click(screen.getByText("보유·자료 관리").closest("button")!);
    fireEvent.click(screen.getByText("ETF보유 및 후보 선정").closest("button")!);
    expect(screen.queryByText("보유 현황")).toBeNull();
    expect(screen.queryByText("후보리스트")).toBeNull();

    rerender(<LeftSidebar active="holdings" onSelect={() => {}} />);
    expect(screen.getByText("보유 현황")).toBeTruthy();
    expect(screen.queryByText("후보리스트")).toBeNull();
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

  it("승인·운영 그룹 = OCI 운영·적용 → 받은 알림 기록 (2026-11-19 형수님 직접 지시 · 정보 PUSH 카드·자리표시자 없음)", () => {
    const ops = MENU_GROUPS.find((g) => g.title === "승인·운영")!;
    const opsItems = groupMenuItems(ops);
    expect(ops.id).toBe("ops");
    expect(ops.items.length).toBe(2);
    expect(opsItems.map((i) => i.label)).toEqual(["OCI 운영·적용", "받은 알림 기록"]);
    // route key 는 approval 그대로 (2026-09-27 합침 — key 변경 없음) · alert_records 도 key 그대로.
    expect(opsItems.map((i) => i.key)).toEqual(["approval", "alert_records"]);
    expect(opsItems[0].hint).toBe("OCI 상태 · 운영 기준 적용");
    expect(opsItems[1].hint).toBe("받은 알림 · 당시 근거 · 이후 결과");
  });

  it("2026-11-19: 받은 알림 기록 · 개발·실험용 · ML 연구 두 화면 · 신규 ETF 관찰 점검은 「진단·상태」에 없다", () => {
    const owner = (key: MenuKey) => MENU_GROUPS.find((g) => groupMenuItems(g).some((i) => i.key === key))!.title;
    expect(owner("alert_records")).toBe("승인·운영");
    expect(owner("ml")).toBe("ML 연구");
    expect(owner("ml_legacy")).toBe("ML 연구");
    expect(owner("unused_universe_watch")).toBe("미사용 기능");
    expect(owner("diagnostics")).toBe("미사용 기능");
    expect(owner("data_status")).toBe("진단·상태");
  });

  it("2026-09-27 합침: oci_status 메뉴는 어디에도 없다 · 「OCI 운영 상태」 라벨도 없다", () => {
    const allKeys = MENU_ITEMS.map((i) => i.key) as string[];
    expect(allKeys).not.toContain("oci_status");
    expect(MENU_ITEMS.map((i) => i.label)).not.toContain("OCI 운영 상태");
  });

  it("진단·상태 그룹 = ETF NAV·괴리율 조회 하나 · 보유·자료 관리 다음 · 승인·운영 → ML 연구 → 미사용 기능 순서 (2026-11-19 형수님 직접 지시)", () => {
    const diag = MENU_GROUPS.find((g) => g.title === "진단·상태")!;
    // 형수님 지시 순서(2026-11-19): 보유·자료 관리 → 진단·상태 → 승인·운영 → ML 연구 → 미사용 기능(마지막).
    //   (그 전: 진단·상태 = 데이터 상태 → ML 연구 폴더 → 받은 알림 기록 → 개발·실험용 → 미사용 기능 폴더.)
    expect(diag.id).toBe("diagnostics");
    expect(diag.items.length).toBe(1);
    expect(groupMenuItems(diag).map((i) => i.key)).toEqual(["data_status"]);
    const order = MENU_GROUPS.map((g) => g.title);
    expect(order.indexOf("진단·상태")).toBe(order.indexOf("보유·자료 관리") + 1);
    expect(order.indexOf("승인·운영")).toBe(order.indexOf("진단·상태") + 1);
    expect(order.indexOf("ML 연구")).toBe(order.indexOf("승인·운영") + 1);
    expect(order.indexOf("미사용 기능")).toBe(order.indexOf("ML 연구") + 1);
    expect(order[order.length - 1]).toBe("미사용 기능");
    // 제거된 key 는 어디에도 없다.
    const allKeys = MENU_ITEMS.map((i) => i.key);
    expect(allKeys).not.toContain("dashboard" as MenuKey);
    // data_status 는 2026-08-16 사용자 지시로 복원됨 (POC3-07 흡수 근거가 낡았던 건).
    expect(allKeys).toContain("data_status" as MenuKey);
  });

  it("보완2: 진단·상태 선택(ETF NAV·괴리율 조회) 시 그 그룹이 활성 표시된다 · 개발·실험용 선택이면 미사용 기능 그룹(2026-11-19)", () => {
    const { rerender } = render(<LeftSidebar active="data_status" onSelect={() => {}} />);
    const grp = () => screen.getByText("진단·상태").closest(".sidebar-group");
    expect(grp()?.className).toContain("active-group");
    rerender(<LeftSidebar active="diagnostics" onSelect={() => {}} />);
    expect(grp()?.className).not.toContain("active-group");
    expect(screen.getByText("미사용 기능").closest(".sidebar-group")?.className).toContain("active-group");
  });

  it("OCI 운영·적용 라벨은 슬래시 표기가 아니다", () => {
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    expect(screen.getByText("OCI 운영·적용")).toBeTruthy();
    expect(screen.queryByText("OCI 운영 / 적용")).toBeNull();
    expect(screen.queryByText("승인·적용")).toBeNull();
  });
});

// --- POC6-15 「ML 연구」 — 2026-11-19 형수님 직접 지시로 「진단·상태」 안 폴더 → 그룹(「승인·운영」 다음) ------------------

describe("「ML 연구」 그룹(POC6-15 · 2026-11-19 폴더 → 그룹)", () => {
  const groupBtn = () => screen.getByText("ML 연구").closest("button")!;
  const groupBox = () => groupBtn().closest(".sidebar-group")!;

  it("그룹 아래 두 화면 · 라벨 · 힌트 · 기존 ml key = 예측과 결과 비교 · 폴더 없음", () => {
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    const g = MENU_GROUPS.find((x) => x.title === "ML 연구")!;
    expect(g.id).toBe("ml_research");
    expect(g.items.some(isMenuFolder)).toBe(false);
    expect(groupMenuItems(g).map((i) => [i.key, i.label, i.hint])).toEqual([
      ["ml", "예측과 결과 비교", "미리 기록한 예측 · 이후 실제 결과"],
      ["ml_legacy", "이전 자료·실험", "예측 비교와 별개인 이전 자료 · 실험"],
    ]);
    expect(screen.queryByText("ML 실험")).toBeNull();
    expect(groupBtn()).toHaveClass("sidebar-group-title");
    const labels = Array.from(groupBox().querySelectorAll(".sidebar-menu-label")).map((e) => e.textContent);
    expect(labels).toEqual(["예측과 결과 비교", "이전 자료·실험"]);
  });

  it("그룹 제목 버튼은 펼침·접힘만 — onSelect 0 · aria-expanded 바뀜", () => {
    const onSelect = vi.fn();
    render(<LeftSidebar active="today_check" onSelect={onSelect} />);
    expect(groupBtn().getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(groupBtn());
    expect(groupBtn().getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("예측과 결과 비교")).toBeNull();
    expect(screen.queryByText("이전 자료·실험")).toBeNull();
    fireEvent.click(groupBtn());
    expect(groupBtn().getAttribute("aria-expanded")).toBe("true");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("하위 메뉴 클릭 = onSelect(key) · 선택된 메뉴 aria-current · 「ML 연구」 그룹만 활성 표시", () => {
    const onSelect = vi.fn();
    const { rerender } = render(<LeftSidebar active="today_check" onSelect={onSelect} />);
    fireEvent.click(screen.getByText("이전 자료·실험"));
    expect(onSelect).toHaveBeenCalledWith("ml_legacy");
    fireEvent.click(screen.getByText("예측과 결과 비교"));
    expect(onSelect).toHaveBeenCalledWith("ml");
    rerender(<LeftSidebar active="ml_legacy" onSelect={onSelect} />);
    expect(screen.getByText("이전 자료·실험").closest("button")?.getAttribute("aria-current")).toBe("page");
    expect(screen.getByText("예측과 결과 비교").closest("button")?.getAttribute("aria-current")).toBeNull();
    expect(groupBox().className).toContain("active-group");
    expect(screen.getByText("진단·상태").closest(".sidebar-group")?.className).not.toContain("active-group");
    expect(document.querySelectorAll(".sidebar-group.active-group")).toHaveLength(1);
  });

  it("접힌 「ML 연구」 그룹 안으로 active 가 바뀌면 그 그룹만 자동으로 편다 · 다른 접힘은 유지", () => {
    const { rerender } = render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    fireEvent.click(groupBtn());
    fireEvent.click(screen.getByText("ETF보유 및 후보 선정").closest("button")!);
    expect(screen.queryByText("이전 자료·실험")).toBeNull();
    rerender(<LeftSidebar active="ml_legacy" onSelect={() => {}} />);
    expect(groupBtn().getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("이전 자료·실험")).toBeTruthy();
    expect(screen.queryByText("후보리스트")).toBeNull();
  });
});

// --- POC6-29 「ETF보유 및 후보 선정」(폴더 없이 여섯 메뉴 · 설계 §3 · 판정 Q3 · Q17) ------------------

describe("POC6-29 「ETF보유 및 후보 선정」", () => {
  it("그룹 메뉴 순서 = 보유 · 섹터요약 · 후보리스트 · AI 투자 세션 · 폴더 없음(POC6-32 V2 — 보유와 후보 비교 · ETF 구성종목은 상세)", () => {
    const g = MENU_GROUPS.find((x) => x.title === "ETF보유 및 후보 선정")!;
    expect(g.items.some(isMenuFolder)).toBe(false);
    expect(groupMenuItems(g).map((i) => [i.key, i.label])).toEqual([
      ["workbench_holdings", "보유"],
      ["etf_sector", "섹터요약"],
      ["workbench", "후보리스트"],
      ["ai_sessions", "AI 투자 세션"],
    ]);
  });

  it("「요즘 잘 오르는 ETF」 · 「ETF 비교하기」 폴더는 어디에도 없다", () => {
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    expect(screen.queryByText("요즘 잘 오르는 ETF")).toBeNull();
    expect(screen.queryByText("ETF 비교하기")).toBeNull();
    expect(MENU_ITEMS.some((i) => (i.key as string) === "market_discovery")).toBe(false);
  });

  it("「보유」를 누르면 onSelect('workbench_holdings') · 선택된 메뉴는 aria-current", () => {
    const onSelect = vi.fn();
    const { rerender } = render(<LeftSidebar active="today_check" onSelect={onSelect} />);
    fireEvent.click(screen.getByText("보유"));
    expect(onSelect).toHaveBeenCalledWith("workbench_holdings");
    rerender(<LeftSidebar active="workbench_holdings" onSelect={onSelect} />);
    expect(screen.getByText("보유").closest("button")).toHaveAttribute("aria-current", "page");
  });
});

// --- POC6-29 보완 「미사용 기능」 — 2026-11-19 형수님 직접 지시로 폴더 → 그룹(마지막) · 「개발·실험용」 추가 ------------------

describe("「미사용 기능」 그룹(POC6-29 보완 · 2026-11-19 폴더 → 그룹)", () => {
  const groupBtn = () => screen.getByText("미사용 기능").closest("button")!;
  const groupBox = () => groupBtn().closest(".sidebar-group")!;

  it("마지막 그룹 · 순서 = 신규 ETF 관찰 점검 → 개발·실험용 · 폴더 없음 · 힌트에 '후보' 없음", () => {
    const g = MENU_GROUPS[MENU_GROUPS.length - 1];
    expect([g.id, g.title]).toEqual(["unused_features", "미사용 기능"]);
    expect(g.items.some(isMenuFolder)).toBe(false);
    expect(groupMenuItems(g).map((i) => [i.key, i.label])).toEqual([
      ["unused_universe_watch", "신규 ETF 관찰 점검"],
      ["diagnostics", "개발·실험용"],
    ]);
    const item = MENU_ITEMS.find((i) => i.key === "unused_universe_watch")!;
    expect(item.hint).toBe("1개월 수익률 1위 ETF 수동 확인 · 실험용 초안");
    expect(item.hint).not.toContain("후보");
    const dev = MENU_ITEMS.find((i) => i.key === "diagnostics")!;
    expect(dev.hint).toBe("미리보기 · 샘플 · 개발 호환 · LEGACY");
  });

  it("「개발·실험용」은 더 이상 「진단·상태」에 없다", () => {
    const diag = MENU_GROUPS.find((g) => g.title === "진단·상태")!;
    expect(groupMenuItems(diag).map((i) => i.key)).not.toContain("diagnostics");
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    const diagBox = screen.getByText("진단·상태").closest(".sidebar-group")!;
    expect(diagBox.textContent).not.toContain("개발·실험용");
    expect(groupBox().textContent).toContain("개발·실험용");
  });

  it("실제 화면: 그룹 제목 아래 신규 ETF 관찰 점검 → 개발·실험용 · 누르면 onSelect · 그룹 제목은 펼침·접힘만", () => {
    const onSelect = vi.fn();
    render(<LeftSidebar active="today_check" onSelect={onSelect} />);
    const groups = document.querySelectorAll(".sidebar-group");
    expect(groups[groups.length - 1]).toBe(groupBox());
    const watch = screen.getByText("신규 ETF 관찰 점검").closest("li")!;
    const dev = screen.getByText("개발·실험용").closest("li")!;
    expect(groupBox().contains(watch)).toBe(true);
    expect(watch.nextElementSibling).toBe(dev);
    expect(dev.nextElementSibling).toBeNull();
    fireEvent.click(screen.getByText("신규 ETF 관찰 점검"));
    expect(onSelect).toHaveBeenCalledWith("unused_universe_watch");
    fireEvent.click(screen.getByText("개발·실험용"));
    expect(onSelect).toHaveBeenCalledWith("diagnostics");
    // 그룹 제목은 펼침 · 접힘만.
    onSelect.mockClear();
    fireEvent.click(groupBtn());
    expect(groupBtn().getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("신규 ETF 관찰 점검")).toBeNull();
    expect(screen.queryByText("개발·실험용")).toBeNull();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("접힌 그룹 안으로 active 가 바뀌면 그룹을 자동으로 편다 · aria-current · 「미사용 기능」 그룹 활성", () => {
    const { rerender } = render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    fireEvent.click(groupBtn());
    expect(screen.queryByText("신규 ETF 관찰 점검")).toBeNull();
    rerender(<LeftSidebar active="unused_universe_watch" onSelect={() => {}} />);
    expect(groupBtn().getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("신규 ETF 관찰 점검").closest("button")).toHaveAttribute("aria-current", "page");
    expect(groupBox().className).toContain("active-group");
    expect(screen.getByText("진단·상태").closest(".sidebar-group")?.className).not.toContain("active-group");

    // 「개발·실험용」으로 와도 같은 그룹이 펴진다.
    rerender(<LeftSidebar active="today_check" onSelect={() => {}} />);
    fireEvent.click(groupBtn());
    expect(screen.queryByText("개발·실험용")).toBeNull();
    rerender(<LeftSidebar active="diagnostics" onSelect={() => {}} />);
    expect(groupBtn().getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("개발·실험용").closest("button")).toHaveAttribute("aria-current", "page");
    expect(groupBox().className).toContain("active-group");
  });
});

// --- POC6-32 V2 「주간 ETF 점검」 메뉴 · 상세 화면 강조(PLAN 판정 V2 Q1 (a) · PLAN §2 S1 · S4 · §9 I-4) ----------------

describe("POC6-32 V2 「주간 ETF 점검」 · 상세 화면", () => {
  it("「오늘 확인」 = 오늘의 투자 점검 → 주간 ETF 점검(바로 아래 형제) · 힌트에 '후보' 없음", () => {
    const today = MENU_GROUPS.find((g) => g.title === "오늘 확인")!;
    expect(today.items.some(isMenuFolder)).toBe(false);
    expect(groupMenuItems(today).map((i) => [i.key, i.label])).toEqual([
      ["today_check", "오늘의 투자 점검"],
      ["weekly_etf_check", "주간 ETF 점검"],
    ]);
    const weekly = MENU_ITEMS.find((i) => i.key === "weekly_etf_check")!;
    expect(weekly.hint).toBeTruthy();
    expect(weekly.hint).not.toContain("후보");
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    const first = screen.getByText("오늘의 투자 점검").closest("li")!;
    expect(first.nextElementSibling).toBe(screen.getByText("주간 ETF 점검").closest("li"));
  });

  it("메뉴에 「보유와 후보 비교」 · 「ETF 구성종목」이 없다 · 메뉴의 '후보' = 그룹 이름 · 「후보리스트」 두 곳", () => {
    const { container } = render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    const text = container.textContent ?? "";
    expect(text).not.toContain("보유와 후보 비교");
    expect(text).not.toContain("ETF 구성종목");
    expect(text.split("후보").length - 1).toBe(2);
    expect(MENU_ITEMS.map((i) => i.label)).not.toContain("보유와 후보 비교");
    expect(MENU_ITEMS.map((i) => i.label)).not.toContain("ETF 구성종목");
  });

  it("상세 key 가 그대로 오면 「주간 ETF 점검」 하나만 강조 · 「오늘 확인」 그룹 활성 · 접혀 있으면 편다(throw 없음)", () => {
    for (const key of DETAIL) {
      const { unmount } = render(<LeftSidebar active={key} onSelect={() => {}} />);
      const current = screen.getAllByRole("button").filter((b) => b.getAttribute("aria-current") === "page");
      expect(current).toHaveLength(1);
      expect(current[0].textContent).toContain("주간 ETF 점검");
      expect(screen.getByText("오늘 확인").closest(".sidebar-group")?.className).toContain("active-group");
      unmount();
    }
    const { rerender } = render(<LeftSidebar active="workbench" onSelect={() => {}} />);
    fireEvent.click(screen.getByText("오늘 확인").closest("button")!);
    expect(screen.queryByText("주간 ETF 점검")).toBeNull();
    rerender(<LeftSidebar active="holding_candidate_compare" onSelect={() => {}} />);
    expect(screen.getByText("주간 ETF 점검").closest("button")).toHaveAttribute("aria-current", "page");
  });

  it("처음 보낸 화면의 key 가 오면 그 메뉴를 강조(MainPanel 이 넘김 · 예: 「후보리스트」)", () => {
    render(<LeftSidebar active="workbench" onSelect={() => {}} />);
    const current = screen.getAllByRole("button").filter((b) => b.getAttribute("aria-current") === "page");
    expect(current.map((b) => b.querySelector(".sidebar-menu-label")?.textContent)).toEqual(["후보리스트"]);
  });

  it("menuKeyOf · screenLabelOf — 상세 key 는 강조 = 주간 ETF 점검 · 이름 = 상세 화면 이름 · 메뉴 key 는 그대로", () => {
    expect(menuKeyOf("etf_exposure")).toBe("weekly_etf_check");
    expect(menuKeyOf("holding_candidate_compare")).toBe("weekly_etf_check");
    expect(menuKeyOf("workbench")).toBe("workbench");
    expect(screenLabelOf("etf_exposure")).toBe("ETF 구성종목");
    expect(screenLabelOf("holding_candidate_compare")).toBe("보유와 후보 비교");
    expect(screenLabelOf("weekly_etf_check")).toBe("주간 ETF 점검");
    expect(screenLabelOf("workbench_holdings")).toBe("보유");
  });

  it("POC6-34 Q7 — data_status 이름 「ETF NAV·괴리율 조회」 · 힌트 · 화면에 한 번 · 옛 이름 없음 · key · 자리 그대로", () => {
    const diag = MENU_GROUPS.find((g) => g.title === "진단·상태")!;
    const first = groupMenuItems(diag)[0];
    expect([first.key, first.label, first.hint]).toEqual([
      "data_status",
      "ETF NAV·괴리율 조회",
      "전체 ETF · 수집 상태 · 큰 괴리 찾기",
    ]);
    expect(screenLabelOf("data_status")).toBe("ETF NAV·괴리율 조회");
    const { container } = render(<LeftSidebar active="data_status" onSelect={() => {}} />);
    const labels = Array.from(container.querySelectorAll(".sidebar-menu-label")).map((e) => e.textContent);
    expect(labels.filter((t) => t === "ETF NAV·괴리율 조회")).toHaveLength(1);
    const hints = Array.from(container.querySelectorAll(".sidebar-menu-hint")).map((e) => e.textContent);
    expect(hints.filter((t) => t === "전체 ETF · 수집 상태 · 큰 괴리 찾기")).toHaveLength(1);
    expect(container.textContent).not.toContain("데이터 상태");
    expect(container.textContent).not.toContain("전체 ETF NAV · 괴리율 · 수집 상태");
    // 강조 = 그 메뉴(이름만 바뀜).
    const current = screen.getAllByRole("button").filter((b) => b.getAttribute("aria-current") === "page");
    expect(current.map((b) => b.querySelector(".sidebar-menu-label")?.textContent)).toEqual(["ETF NAV·괴리율 조회"]);
  });
});
