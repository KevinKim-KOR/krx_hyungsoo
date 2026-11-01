"use client";

// POC2 PC UI Shell — 좌측 메뉴 컴포넌트.
//
// 2026-05-21 갱신: AI Sessions 메뉴 추가 (Market Discovery 와 분리, 지시문 §3).
// 2026-07-29 POC3-01: 새 기본 진입 화면 "오늘의 투자 점검" 추가.
// 2026-08-01 POC3-03 Navigation Information Architecture v1:
//   평면 메뉴를 사용자 과업 순서의 그룹으로 재편.
//   그룹 순서: 오늘 확인 → 비교·판단 → 보유·자료 관리 → 승인·운영 (설계서 §3.1).
//   + 사용자 실화면 지시(2026-08-01): "기존 대시보드" 를 별도 "점검대상" 그룹으로
//     분리 → 총 5개 그룹 (§3.2 를 사용자 지시로 재편, 결과서 §4).
//   - 화면 전환 key(MenuKey) 와 개수(9개) 는 불변 — 그룹은 표현 계층에만 존재.
//   - 첫 진입 기본값(today_check) 은 MainPanel 책임 (LeftSidebar 는 active 를 받기만 함).
//   - 그룹 접힘 상태는 이 컴포넌트의 세션 UI 상태(useState)로만 관리 — DB/파일/URL/
//     localStorage/sessionStorage 저장 안 함 (§4.2·AC-9, 접힘 영구저장은 B-057 보류 유지).
//   - active 가 접힌 그룹에 속하면 그 그룹을 자동으로 펼쳐 선택 메뉴가 항상 보이게 함
//     (§4.3·AC-5). 다른 그룹의 사용자 접힘 상태는 유지.
// AC-7 사용자 언어: 그룹명·메뉴명 모두 내부 명칭(Workbench/Market Discovery/Holdings/
//   ETF Exposure/Data Status/Operations Panel) 비노출. hint 도 동일.
// 2026-11-01 POC6-15: 그룹 안에 폴더 하나를 둘 수 있다(한 단계만 · 범용 트리 아님).
//   폴더 = 펼침·접힘만(화면 전환 없음 · key 없음). 접힘 상태는 그룹과 같이 useState 만.
//   active 가 폴더 안이면 그 폴더를 자동으로 펴고, 접어 두면 폴더 줄에 현재 위치를 보인다.

import { useEffect, useState } from "react";

export type MenuKey =
  | "today_check"
  | "workbench"
  | "market_discovery"
  | "etf_exposure"
  | "ai_sessions"
  | "holdings"
  | "holdings_manage"
  | "holdings_evidence"
  | "approval"
  | "diagnostics"
  | "ml"
  | "ml_legacy"
  | "alert_records"
  | "data_status";

export interface MenuItem {
  key: MenuKey;
  label: string;
  hint?: string;
}

// 그룹 안 폴더(POC6-15 · 한 단계만). 폴더 자체는 화면이 아니라 key 가 없다.
export interface MenuFolder {
  id: string;
  title: string;
  items: MenuItem[];
}

export type MenuEntry = MenuItem | MenuFolder;

export interface MenuGroup {
  id: string;
  title: string;
  items: MenuEntry[];
}

export function isMenuFolder(entry: MenuEntry): entry is MenuFolder {
  return "items" in entry;
}

// 그룹 안의 화면 메뉴(폴더 하위 포함)를 순서대로 편다.
export function groupMenuItems(group: MenuGroup): MenuItem[] {
  return group.items.flatMap((e) => (isMenuFolder(e) ? e.items : [e]));
}

// 5개 과업 그룹 (설계서 §3.1·§3.2·Q2·Q3 + 사용자 "점검대상" 분리 지시).
// 각 화면 전환 key 는 정확히 한 그룹에만 1회 귀속 (중복·고아 0 · AC-2).
export const MENU_GROUPS: MenuGroup[] = [
  {
    id: "today",
    title: "오늘 확인",
    items: [
      { key: "today_check", label: "오늘의 투자 점검", hint: "코스피 위치 · 오늘 확인할 것 · 자료 상태" },
    ],
  },
  {
    id: "compare",
    title: "비교·판단",
    items: [
      { key: "workbench", label: "ETF 비교하기", hint: "관심·보유 ETF 한 화면 비교" },
      { key: "market_discovery", label: "요즘 잘 오르는 ETF", hint: "강한 흐름 ETF 찾기" },
      { key: "etf_exposure", label: "ETF 구성종목", hint: "담고 있는 종목 / 중복" },
      { key: "ai_sessions", label: "AI 투자 세션", hint: "AI 질문/답변 기록" },
    ],
  },
  // 2026-08-02 POC3-05 DESIGN_V2: "보유·자료 관리" 아래 하위 메뉴 분리(설계서 §4.1).
  //   2026-08-05 POC3-07: "데이터 상태"(data_status)는 진단·상태 그룹으로 흡수(§5.4).
  //   순서: 보유 현황 → 종목 관리 → 확인 근거.
  {
    id: "manage",
    title: "보유·자료 관리",
    items: [
      { key: "holdings", label: "보유 현황", hint: "평가 현황 / 시세 갱신" },
      { key: "holdings_manage", label: "종목 관리", hint: "입력 / 수정 / 저장 / OCI 적용" },
      { key: "holdings_evidence", label: "확인 근거", hint: "보유 ETF의 수치와 확인 근거" },
    ],
  },
  // 2026-08-05 POC3-07 §5.4·§10.1: "승인·알림" → "승인·적용" 역할 축소
  //   (실제 승인 대상 = PARAM·seed OCI 적용). 정보 PUSH 카드·빈 승인 카드 없음.
  // 2026-09-27 사용자 직접 지시: 「승인·적용」과 「OCI 운영 상태」(`oci_status`)를
  //   한 화면 「OCI 운영·적용」으로 합쳤다. route key 는 `approval` 그대로이고
  //   `oci_status` 는 없앴다(① 지금 OCI 상태 → ② OCI 에 적용).
  {
    id: "ops",
    title: "승인·운영",
    items: [
      { key: "approval", label: "OCI 운영·적용", hint: "OCI 상태 · 운영 기준 적용" },
    ],
  },
  // 2026-08-05 POC3-07 §5.3: 정상 업무와 시각적으로 분리된 마지막 관리 그룹.
  //   data_status 흡수 + 기존 dashboard(LEGACY) + 미리보기·샘플·미연결 격리.
  {
    id: "diagnostics",
    title: "진단·상태",
    // 2026-08-16 사용자 직접 지시 — 진단 서랍에 정상 업무가 섞여 있어 분리했다.
    //   순서: 정상 업무(데이터 상태) → ML 실험 → 개발·실험용.
    // 2026-11-01 POC6-15(설계자 PLAN 판정 Q2): 「ML 실험」 → 「ML 연구」 폴더 · 두 화면.
    //   예측과 결과 비교 = 기존 `ml` key(06 전향 비교 · 카드 1) · 이전 자료·실험 = `ml_legacy`(카드 5).
    //   data_status 는 POC3-07 이 "placeholder" 로 보고 흡수했으나, 실제로는
    //   2026-06-08 부터 전체 ETF NAV·괴리율 조회 화면이었다(판단 근거가 낡음) → 복원.
    //   (「OCI 운영 상태」는 2026-09-27 에 승인·운영 그룹 「OCI 운영·적용」으로 합쳤다.)
    items: [
      { key: "data_status", label: "데이터 상태", hint: "전체 ETF NAV · 괴리율 · 수집 상태" },
      {
        id: "ml_research",
        title: "ML 연구",
        items: [
          { key: "ml", label: "예측과 결과 비교", hint: "미리 기록한 예측 · 이후 실제 결과" },
          { key: "ml_legacy", label: "이전 자료·실험", hint: "예측 비교와 별개인 이전 자료 · 실험" },
        ],
      },
      // 2026-10-07 POC5-03 설계 개정 2(사용자 결정): 받은 알림 · 당시 근거 · 이후 결과 기록.
      //   매일 보는 「오늘 확인」이 아니라 사후 ML 검토용이라 ML 실험 바로 아래에 둔다(지금 = ML 연구 폴더 아래).
      { key: "alert_records", label: "받은 알림 기록", hint: "받은 알림 · 당시 근거 · 이후 결과" },
      { key: "diagnostics", label: "개발·실험용", hint: "미리보기 · 샘플 · 개발 호환 · LEGACY" },
    ],
  },
];

// 하위 호환: 기존에 평면 목록을 참조하던 코드/테스트를 위해 유지(그룹 · 폴더 평탄화).
export const MENU_ITEMS: MenuItem[] = MENU_GROUPS.flatMap(groupMenuItems);

// 모듈 로드 시 메뉴 귀속 무결성 검증 (계약: 모든 MenuKey 가 정확히 1개 그룹에 귀속).
// 누락·중복이면 첫 그룹 위장(fallback)으로 숨기지 않고 즉시 throw — dev/운영 모두 동일하게
// 명확한 오류로 종료한다. 화면 빌드·렌더 이전에 터지므로 "활성 그룹 없는 상태로 조용히 진행"
// 하는 경로 자체가 존재하지 않는다.
const ALL_MENU_KEYS: MenuKey[] = [
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
  "ml",
  "ml_legacy",
  "alert_records",
  "data_status",
];

function assertMenuGroupsCover(): void {
  const allItems = MENU_ITEMS;
  // 각 MenuKey 가 그룹 전체에서 "정확히 1번" 나타나는지 item 단위로 센다.
  // (그룹 단위 filter 로 세면 같은 그룹 안 동일 key 중복을 놓친다.)
  for (const key of ALL_MENU_KEYS) {
    const count = allItems.filter((it) => it.key === key).length;
    if (count !== 1) {
      throw new Error(
        `LeftSidebar 메뉴 귀속 계약 위반: MenuKey "${key}" 는 정확히 1번 나타나야 하나 ${count}번. (누락=0 / 중복>1, 같은 그룹 내 중복 포함)`
      );
    }
  }
  // 정의된 항목 수 = 알려진 key 수. 목록에 없는 신규 key 유입도 차단.
  if (allItems.length !== ALL_MENU_KEYS.length) {
    throw new Error(
      `LeftSidebar 메뉴 항목 수(${allItems.length})가 알려진 MenuKey 수(${ALL_MENU_KEYS.length})와 다름 — 미등록 key 유입.`
    );
  }
}
assertMenuGroupsCover();

// active key 가 속한 그룹 id 를 찾는다. 위 invariant 로 항상 정확히 1개 그룹이 존재하므로
// fallback 없이 그 id 를 반환한다(누락 시엔 위에서 이미 throw 됨).
function groupIdOf(key: MenuKey): string {
  const g = MENU_GROUPS.find((grp) => groupMenuItems(grp).some((it) => it.key === key));
  if (!g) {
    // invariant 상 도달 불가. 방어적으로 명확히 종료(위장 금지).
    throw new Error(`LeftSidebar: MenuKey "${key}" 가 어느 그룹에도 귀속되지 않음`);
  }
  return g.id;
}

// active key 가 속한 폴더 id(폴더 밖이면 null).
function folderIdOf(key: MenuKey): string | null {
  for (const g of MENU_GROUPS) {
    for (const e of g.items) {
      if (isMenuFolder(e) && e.items.some((it) => it.key === key)) return e.id;
    }
  }
  return null;
}

interface Props {
  active: MenuKey;
  onSelect: (key: MenuKey) => void;
}

export default function LeftSidebar({ active, onSelect }: Props) {
  // 최초 진입: 모든 그룹 펼침 (§4.1·보완1). collapsed = 접힌 그룹 id 집합.
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  // 자동 펼침(§4.3·AC-5·보완3): active 가 접힌 그룹에 속하면 그 그룹만 펼친다.
  // 다른 그룹의 사용자 접힘 상태는 그대로 유지.
  const activeGroupId = groupIdOf(active);
  useEffect(() => {
    setCollapsed((prev) => {
      if (!prev.has(activeGroupId)) return prev;
      const next = new Set(prev);
      next.delete(activeGroupId);
      return next;
    });
  }, [activeGroupId]);

  // 폴더 접힘(POC6-15) — 처음엔 모두 펼침. active 가 폴더 안으로 바뀌면 그 폴더를 편다.
  const [collapsedFolders, setCollapsedFolders] = useState<Set<string>>(new Set());
  const activeFolderId = folderIdOf(active);
  useEffect(() => {
    if (activeFolderId === null) return;
    setCollapsedFolders((prev) => {
      if (!prev.has(activeFolderId)) return prev;
      const next = new Set(prev);
      next.delete(activeFolderId);
      return next;
    });
  }, [activeFolderId]);

  const toggleFolder = (id: string) => {
    setCollapsedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const renderItem = (item: MenuItem) => {
    const isActive = item.key === active;
    return (
      <li key={item.key} className={isActive ? "active" : ""}>
        <button
          type="button"
          className="sidebar-menu-btn"
          onClick={() => onSelect(item.key)}
          aria-current={isActive ? "page" : undefined}
        >
          <span className="sidebar-menu-label">{item.label}</span>
          {item.hint ? (
            <span className="sidebar-menu-hint">{item.hint}</span>
          ) : null}
        </button>
      </li>
    );
  };

  const renderFolder = (folder: MenuFolder) => {
    const isOpen = !collapsedFolders.has(folder.id);
    const activeChild = folder.items.find((it) => it.key === active);
    const listId = `sidebar-folder-${folder.id}`;
    return (
      <li key={folder.id} className={"sidebar-folder" + (activeChild ? " active-folder" : "")}>
        <button
          type="button"
          className="sidebar-folder-btn"
          aria-expanded={isOpen}
          aria-controls={listId}
          onClick={() => toggleFolder(folder.id)}
        >
          <span className="sidebar-group-caret" aria-hidden="true">
            {isOpen ? "▾" : "▸"}
          </span>
          <span className="sidebar-folder-name">{folder.title}</span>
          {!isOpen && activeChild ? (
            <span className="sidebar-folder-current">· {activeChild.label}</span>
          ) : null}
        </button>
        {isOpen ? (
          <ul id={listId} className="sidebar-menu sidebar-submenu">
            {folder.items.map(renderItem)}
          </ul>
        ) : null}
      </li>
    );
  };

  const toggleGroup = (id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <aside className="app-sidebar" aria-label="좌측 메뉴">
      <div className="sidebar-brand">krx_alertor</div>
      <nav>
        {MENU_GROUPS.map((group) => {
          const isCollapsed = collapsed.has(group.id);
          const isActiveGroup = group.id === activeGroupId;
          return (
            <div
              key={group.id}
              className={
                "sidebar-group" + (isActiveGroup ? " active-group" : "")
              }
            >
              <button
                type="button"
                className="sidebar-group-title"
                aria-expanded={!isCollapsed}
                onClick={() => toggleGroup(group.id)}
              >
                <span className="sidebar-group-caret" aria-hidden="true">
                  {isCollapsed ? "▸" : "▾"}
                </span>
                <span className="sidebar-group-name">{group.title}</span>
              </button>
              {!isCollapsed ? (
                <ul className="sidebar-menu">
                  {group.items.map((entry) =>
                    isMenuFolder(entry) ? renderFolder(entry) : renderItem(entry)
                  )}
                </ul>
              ) : null}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
