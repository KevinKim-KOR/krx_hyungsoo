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
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import LeftSidebar, {
  MENU_GROUPS,
  MENU_ITEMS,
  groupMenuItems,
  isMenuFolder,
  type MenuKey,
} from "./LeftSidebar";

const ALL_KEYS: MenuKey[] = [
  "today_check",
  "workbench",
  "workbench_holdings",
  "etf_sector",
  "holding_candidate_compare",
  "etf_exposure",
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

const GROUP_TITLES = [
  "오늘 확인",
  "ETF보유 및 후보 선정",
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
  it("AC-1: 그룹 제목이 순서대로 표시된다 (오늘/ETF보유 및 후보 선정/보유·자료/승인·운영/진단·상태)", () => {
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    const titles = screen
      .getAllByRole("button", { expanded: true })
      .filter((b) => b.classList.contains("sidebar-group-title"))
      .map((b) => b.textContent?.replace(/[▸▾]/g, "").trim());
    for (const t of GROUP_TITLES) {
      expect(screen.getByText(t)).toBeTruthy();
    }
    expect(MENU_GROUPS.map((g) => g.title)).toEqual(GROUP_TITLES);
    expect(titles.length).toBe(GROUP_TITLES.length);
  });

  it("AC-2: 17개 key 가 그룹에 정확히 1회씩 귀속(폴더 하위 포함 · 중복·누락·신규 0 · POC6-29 섹터요약 · 보유와 후보 비교 추가 · 요즘 잘 오르는 ETF 없앰 · 보완 신규 ETF 관찰 점검 추가)", () => {
    const keys = MENU_GROUPS.flatMap((g) => groupMenuItems(g).map((i) => i.key));
    expect(keys.sort()).toEqual([...ALL_KEYS].sort());
    expect(new Set(keys).size).toBe(17);
    expect(keys.length).toBe(17);
    expect(MENU_ITEMS.map((i) => i.key).sort()).toEqual([...ALL_KEYS].sort());
  });

  it("B-1: 모든 MenuKey 가 정확히 1개 그룹에 귀속된다 (모듈 invariant — 누락 시 로드 throw)", () => {
    for (const key of ALL_KEYS) {
      const owners = MENU_GROUPS.filter((g) => groupMenuItems(g).some((i) => i.key === key));
      expect(owners.length).toBe(1);
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
    fireEvent.click(screen.getByText("보유와 후보 비교"));
    expect(onSelect).toHaveBeenCalledWith("holding_candidate_compare");
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

  it("승인·운영 그룹은 OCI 운영·적용 메뉴 1개만 (정보 PUSH 카드·자리표시자 없음)", () => {
    const ops = MENU_GROUPS.find((g) => g.title === "승인·운영")!;
    const opsItems = groupMenuItems(ops);
    expect(ops.items.length).toBe(1);
    expect(opsItems.map((i) => i.label)).toEqual(["OCI 운영·적용"]);
    // route key 는 approval 그대로 (2026-09-27 합침 — key 변경 없음).
    expect(opsItems.map((i) => i.key)).toEqual(["approval"]);
    expect(opsItems[0].hint).toBe("OCI 상태 · 운영 기준 적용");
  });

  it("2026-09-27 합침: oci_status 메뉴는 어디에도 없다 · 「OCI 운영 상태」 라벨도 없다", () => {
    const allKeys = MENU_ITEMS.map((i) => i.key) as string[];
    expect(allKeys).not.toContain("oci_status");
    expect(MENU_ITEMS.map((i) => i.label)).not.toContain("OCI 운영 상태");
  });

  it("진단·상태 그룹은 정상 업무→ML→개발용→미사용 기능 순서이며 승인·운영 뒤에 온다 (POC3-07 §5.3 · 2026-08-16 재편)", () => {
    const diag = MENU_GROUPS.find((g) => g.title === "진단·상태")!;
    // 사용자 지시 순서: 데이터 상태 → ML 연구 폴더(2026-11-01 · 예측과 결과 비교 → 이전 자료·실험)
    //   → 받은 알림 기록(2026-10-07) → 개발·실험용 → 미사용 기능 폴더(2026-11-12 POC6-29 보완 · 신규 ETF 관찰 점검).
    //   (OCI 운영 상태는 2026-09-27 승인·운영 그룹 「OCI 운영·적용」으로 합쳐졌다.)
    expect(groupMenuItems(diag).map((i) => i.key)).toEqual([
      "data_status",
      "ml",
      "ml_legacy",
      "alert_records",
      "diagnostics",
      "unused_universe_watch",
    ]);
    const folder = diag.items[1];
    expect(isMenuFolder(folder) && folder.title).toBe("ML 연구");
    const alerts = groupMenuItems(diag).find((i) => i.key === "alert_records")!;
    expect(alerts.label).toBe("받은 알림 기록");
    expect(alerts.hint).toBe("받은 알림 · 당시 근거 · 이후 결과");
    const order = MENU_GROUPS.map((g) => g.title);
    expect(order.indexOf("진단·상태")).toBe(order.indexOf("승인·운영") + 1);
    // 제거된 key 는 어디에도 없다.
    const allKeys = MENU_ITEMS.map((i) => i.key);
    expect(allKeys).not.toContain("dashboard" as MenuKey);
    // data_status 는 2026-08-16 사용자 지시로 복원됨 (POC3-07 흡수 근거가 낡았던 건).
    expect(allKeys).toContain("data_status" as MenuKey);
  });

  it("보완2: 진단·상태 선택 시 그 그룹이 활성 표시된다", () => {
    render(<LeftSidebar active="diagnostics" onSelect={() => {}} />);
    const grp = screen.getByText("진단·상태").closest(".sidebar-group");
    expect(grp?.className).toContain("active-group");
  });

  it("OCI 운영·적용 라벨은 슬래시 표기가 아니다", () => {
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    expect(screen.getByText("OCI 운영·적용")).toBeTruthy();
    expect(screen.queryByText("OCI 운영 / 적용")).toBeNull();
    expect(screen.queryByText("승인·적용")).toBeNull();
  });
});

// --- POC6-15 「ML 연구」 폴더(한 단계) ------------------------------------------

describe("POC6-15 「ML 연구」 폴더", () => {
  const folderBtn = () => screen.getByText("ML 연구").closest("button")!;

  it("폴더 아래 두 화면 · 라벨 · 힌트 · 기존 ml key = 예측과 결과 비교", () => {
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    const ml = MENU_ITEMS.find((i) => i.key === "ml")!;
    const legacy = MENU_ITEMS.find((i) => i.key === "ml_legacy")!;
    expect([ml.label, ml.hint]).toEqual(["예측과 결과 비교", "미리 기록한 예측 · 이후 실제 결과"]);
    expect([legacy.label, legacy.hint]).toEqual([
      "이전 자료·실험",
      "예측 비교와 별개인 이전 자료 · 실험",
    ]);
    expect(screen.queryByText("ML 실험")).toBeNull();
    const sub = document.getElementById(folderBtn().getAttribute("aria-controls")!)!;
    expect(sub.textContent).toContain("예측과 결과 비교");
    expect(sub.textContent).toContain("이전 자료·실험");
  });

  it("폴더 버튼은 펼침·접힘만 — onSelect 0 · aria-expanded 바뀜", () => {
    const onSelect = vi.fn();
    render(<LeftSidebar active="today_check" onSelect={onSelect} />);
    expect(folderBtn().getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(folderBtn());
    expect(folderBtn().getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("예측과 결과 비교")).toBeNull();
    fireEvent.click(folderBtn());
    expect(folderBtn().getAttribute("aria-expanded")).toBe("true");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("하위 메뉴 클릭 = onSelect(key) · 선택된 하위 메뉴 aria-current · 폴더 · 그룹 활성 표시", () => {
    const onSelect = vi.fn();
    const { rerender } = render(<LeftSidebar active="today_check" onSelect={onSelect} />);
    fireEvent.click(screen.getByText("이전 자료·실험"));
    expect(onSelect).toHaveBeenCalledWith("ml_legacy");
    fireEvent.click(screen.getByText("예측과 결과 비교"));
    expect(onSelect).toHaveBeenCalledWith("ml");
    rerender(<LeftSidebar active="ml_legacy" onSelect={onSelect} />);
    expect(screen.getByText("이전 자료·실험").closest("button")?.getAttribute("aria-current")).toBe("page");
    expect(screen.getByText("예측과 결과 비교").closest("button")?.getAttribute("aria-current")).toBeNull();
    expect(folderBtn().closest("li")?.className).toContain("active-folder");
    expect(screen.getByText("진단·상태").closest(".sidebar-group")?.className).toContain("active-group");
  });

  it("접힌 폴더 줄에 현재 위치 표시 · 폴더 밖 화면이면 표시 없음", () => {
    const { rerender } = render(<LeftSidebar active="ml" onSelect={() => {}} />);
    fireEvent.click(folderBtn());
    expect(folderBtn().textContent).toContain("· 예측과 결과 비교");
    rerender(<LeftSidebar active="data_status" onSelect={() => {}} />);
    expect(folderBtn().getAttribute("aria-expanded")).toBe("false");
    expect(folderBtn().textContent).not.toContain("·");
  });

  it("접힌 폴더 안으로 active 가 바뀌면 그 폴더만 자동으로 편다 · 접힌 그룹도 편다", () => {
    const { rerender } = render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    fireEvent.click(folderBtn());
    fireEvent.click(screen.getByText("ETF보유 및 후보 선정").closest("button")!);
    expect(screen.queryByText("이전 자료·실험")).toBeNull();
    rerender(<LeftSidebar active="ml_legacy" onSelect={() => {}} />);
    expect(folderBtn().getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("이전 자료·실험")).toBeTruthy();
    expect(screen.queryByText("후보리스트")).toBeNull();

    // 다른 그룹에서 접힌 「진단·상태」의 폴더 안으로 오면 그룹과 폴더가 같이 펴진다.
    rerender(<LeftSidebar active="today_check" onSelect={() => {}} />);
    fireEvent.click(screen.getByText("진단·상태").closest("button")!);
    expect(screen.queryByText("ML 연구")).toBeNull();
    rerender(<LeftSidebar active="ml" onSelect={() => {}} />);
    expect(screen.getByText("예측과 결과 비교")).toBeTruthy();
  });
});

// --- POC6-29 「ETF보유 및 후보 선정」(폴더 없이 여섯 메뉴 · 설계 §3 · 판정 Q3 · Q17) ------------------

describe("POC6-29 「ETF보유 및 후보 선정」", () => {
  it("그룹 메뉴 순서 = 보유 · 섹터요약 · 후보리스트 · 보유와 후보 비교 · ETF 구성종목 · AI 투자 세션 · 폴더 없음", () => {
    const g = MENU_GROUPS.find((x) => x.title === "ETF보유 및 후보 선정")!;
    expect(g.items.some(isMenuFolder)).toBe(false);
    expect(groupMenuItems(g).map((i) => [i.key, i.label])).toEqual([
      ["workbench_holdings", "보유"],
      ["etf_sector", "섹터요약"],
      ["workbench", "후보리스트"],
      ["holding_candidate_compare", "보유와 후보 비교"],
      ["etf_exposure", "ETF 구성종목"],
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

// --- POC6-29 보완 「미사용 기능」 폴더(보완 PLAN 판정 Q-R5 · RESULT 판정 §4 · 목업 R4) ------------------

describe("POC6-29 보완 「미사용 기능」 폴더", () => {
  const folderBtn = () => screen.getByText("미사용 기능").closest("button")!;

  it("「진단·상태」 맨 끝(「개발·실험용」 다음) 폴더 · 하위 메뉴 1개 = 「신규 ETF 관찰 점검」 · 힌트에 '후보' 없음", () => {
    const diag = MENU_GROUPS.find((g) => g.title === "진단·상태")!;
    const last = diag.items[diag.items.length - 1];
    const prev = diag.items[diag.items.length - 2];
    expect(isMenuFolder(last) && last.title).toBe("미사용 기능");
    expect(isMenuFolder(last) && last.id).toBe("unused_features");
    expect(!isMenuFolder(prev) && prev.key).toBe("diagnostics");
    expect(isMenuFolder(last) && last.items.map((i) => [i.key, i.label])).toEqual([
      ["unused_universe_watch", "신규 ETF 관찰 점검"],
    ]);
    const item = MENU_ITEMS.find((i) => i.key === "unused_universe_watch")!;
    expect(item.hint).toBe("1개월 수익률 1위 ETF 수동 확인 · 실험용 초안");
    expect(item.hint).not.toContain("후보");
  });

  it("실제 화면에서도 「개발·실험용」 다음 · 폴더 아래 「신규 ETF 관찰 점검」 · 누르면 onSelect", () => {
    const onSelect = vi.fn();
    render(<LeftSidebar active="today_check" onSelect={onSelect} />);
    const dev = screen.getByText("개발·실험용").closest("li")!;
    const folderLi = folderBtn().closest("li")!;
    expect(dev.compareDocumentPosition(folderLi) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(dev.nextElementSibling).toBe(folderLi);
    expect(folderLi.nextElementSibling).toBeNull();
    const sub = document.getElementById(folderBtn().getAttribute("aria-controls")!)!;
    expect(sub.textContent).toContain("신규 ETF 관찰 점검");
    fireEvent.click(screen.getByText("신규 ETF 관찰 점검"));
    expect(onSelect).toHaveBeenCalledWith("unused_universe_watch");
    // 폴더 버튼은 펼침 · 접힘만.
    onSelect.mockClear();
    fireEvent.click(folderBtn());
    expect(folderBtn().getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("신규 ETF 관찰 점검")).toBeNull();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("접힌 폴더 안으로 active 가 바뀌면 폴더를 자동으로 편다 · 접힌 「진단·상태」 그룹도 편다", () => {
    const { rerender } = render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    fireEvent.click(folderBtn());
    expect(screen.queryByText("신규 ETF 관찰 점검")).toBeNull();
    rerender(<LeftSidebar active="unused_universe_watch" onSelect={() => {}} />);
    expect(folderBtn().getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("신규 ETF 관찰 점검").closest("button")).toHaveAttribute("aria-current", "page");
    expect(folderBtn().closest("li")?.className).toContain("active-folder");
    expect(screen.getByText("진단·상태").closest(".sidebar-group")?.className).toContain("active-group");

    rerender(<LeftSidebar active="today_check" onSelect={() => {}} />);
    fireEvent.click(folderBtn());
    fireEvent.click(screen.getByText("진단·상태").closest("button")!);
    expect(screen.queryByText("미사용 기능")).toBeNull();
    rerender(<LeftSidebar active="unused_universe_watch" onSelect={() => {}} />);
    expect(folderBtn().getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("신규 ETF 관찰 점검")).toBeTruthy();
  });

  it("접힌 폴더 줄에 현재 위치 표시", () => {
    render(<LeftSidebar active="unused_universe_watch" onSelect={() => {}} />);
    fireEvent.click(folderBtn());
    expect(folderBtn().textContent).toContain("· 신규 ETF 관찰 점검");
  });
});
