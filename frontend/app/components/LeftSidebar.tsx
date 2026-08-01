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

import { useEffect, useState } from "react";

export type MenuKey =
  | "today_check"
  | "dashboard"
  | "workbench"
  | "market_discovery"
  | "etf_exposure"
  | "ai_sessions"
  | "holdings"
  | "approval"
  | "data_status";

export interface MenuItem {
  key: MenuKey;
  label: string;
  hint?: string;
}

export interface MenuGroup {
  id: string;
  title: string;
  items: MenuItem[];
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
  {
    id: "manage",
    title: "보유·자료 관리",
    items: [
      { key: "holdings", label: "내가 가진 ETF", hint: "보유 현황 / 평가" },
      { key: "data_status", label: "데이터 상태", hint: "시장 데이터 상태 (예정)" },
    ],
  },
  {
    id: "ops",
    title: "승인·운영",
    items: [
      { key: "approval", label: "승인·알림", hint: "승인 대기 / 발송 결과" },
    ],
  },
  // 2026-08-01 사용자 요청 — "기존 대시보드" 를 보유·자료 관리에서 분리해
  // 승인·운영 아래 별도 "점검대상" 그룹으로 이동. UI 최종 판단은 사용자.
  // (설계서 §3.2·Q2 의 "보유·자료 관리 마지막" 귀속을 사용자 지시로 재편.)
  {
    id: "inspect",
    title: "점검대상",
    items: [
      { key: "dashboard", label: "기존 대시보드", hint: "이전 상태 화면 (참고용)" },
    ],
  },
];

// 하위 호환: 기존에 평면 목록을 참조하던 코드/테스트를 위해 유지(그룹 평탄화).
export const MENU_ITEMS: MenuItem[] = MENU_GROUPS.flatMap((g) => g.items);

// 모듈 로드 시 메뉴 귀속 무결성 검증 (계약: 모든 MenuKey 가 정확히 1개 그룹에 귀속).
// 누락·중복이면 첫 그룹 위장(fallback)으로 숨기지 않고 즉시 throw — dev/운영 모두 동일하게
// 명확한 오류로 종료한다. 화면 빌드·렌더 이전에 터지므로 "활성 그룹 없는 상태로 조용히 진행"
// 하는 경로 자체가 존재하지 않는다.
const ALL_MENU_KEYS: MenuKey[] = [
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

function assertMenuGroupsCover(): void {
  const allItems = MENU_GROUPS.flatMap((g) => g.items);
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
  const g = MENU_GROUPS.find((grp) => grp.items.some((it) => it.key === key));
  if (!g) {
    // invariant 상 도달 불가. 방어적으로 명확히 종료(위장 금지).
    throw new Error(`LeftSidebar: MenuKey "${key}" 가 어느 그룹에도 귀속되지 않음`);
  }
  return g.id;
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
                  {group.items.map((item) => {
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
                  })}
                </ul>
              ) : null}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
