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
// 2026-11-12 POC6-29(설계 §3 · PLAN 판정 Q3 · Q17): 「비교·판단」 → 「ETF보유 및 후보 선정」 · 「ETF 비교하기」 폴더를 없애고
//   보유 · 섹터요약 · 후보리스트 · 보유와 후보 비교를 바로 둔다(+ ETF 구성종목 · AI 투자 세션). 「요즘 잘 오르는 ETF」
//   (`market_discovery`)는 기능을 「오늘의 투자 점검」 · 이 그룹으로 옮기고 메뉴에서 뺐다. 메뉴의 '후보'는 이 그룹 이름 ·
//   「후보리스트」 · 「보유와 후보 비교」 세 곳뿐이다(힌트에는 쓰지 않음 · POC6-32 V2 부터 두 곳 · 아래).
// 2026-11-12 POC6-29 보완(보완 PLAN 판정 Q-R5 · RESULT 판정 §4 · 목업 R4): 「진단·상태」 끝(「개발·실험용」 다음)에 폴더
//   「미사용 기능」(「ML 연구」와 같은 폴더)을 두고 기능마다 하위 메뉴 하나를 둔다. 첫 하위 메뉴 = 「신규 ETF 관찰 점검」
//   (`unused_universe_watch` · 메뉴 key 16 → 17).
// 2026-11-17 POC6-32 V2(PLAN 판정 V2 Q1 (a) · PLAN §2 S1 · S4 · §9 I-4):
//   - 「오늘 확인」에 「오늘의 투자 점검」 바로 아래 형제 메뉴 「주간 ETF 점검」(`weekly_etf_check`)을 둔다.
//   - 「보유와 후보 비교」(`holding_candidate_compare`) · 「ETF 구성종목」(`etf_exposure`)은 메뉴에서 뺀 상세 화면이다
//     (key 는 그대로 · 화면 안에서만 엶). 계약 = 메뉴 key 는 메뉴에 정확히 1번 · 상세 key 는 0번.
//   - 메뉴의 '후보'는 그룹 이름 「ETF보유 및 후보 선정」 · 「후보리스트」 두 곳뿐이다(힌트에는 쓰지 않음).
//   - 상세가 열린 동안의 강조는 MainPanel 이 넘긴 '처음 보낸 화면'의 메뉴다. 상세 key 가 그대로 오면 「주간 ETF 점검」.
// 2026-11-19 형수님 직접 지시(메뉴 순서 · 단계 · 메뉴 key · 이름 · 힌트는 그대로):
//   - 그룹 5개 → 7개: 오늘 확인 → ETF보유 및 후보 선정 → 보유·자료 관리 → 진단·상태 → 승인·운영 → ML 연구 → 미사용 기능.
//   - 「받은 알림 기록」은 「승인·운영」의 「OCI 운영·적용」 다음으로 옮겼다.
//   - 「ML 연구」 · 「미사용 기능」은 「진단·상태」 안 폴더였다 → 한 단계 올려 그룹으로 둔다(id 그대로).
//   - 「개발·실험용」(`diagnostics`)은 「미사용 기능」의 「신규 ETF 관찰 점검」 다음으로 옮겼다. 형수님 판정 = 지금 쓰지 않는 화면
//     (PC 실행 기록 = 2026-08-12 ~ 09-22 시험 실패 기록 156건뿐 · 실제 수동 초안 · 발송 없음 · 정상 화면에서 이 화면으로 가는 길 없음).
//   - 「진단·상태」에는 「ETF NAV·괴리율 조회」 하나만 남는다.
//   - 폴더 틀(MenuFolder · renderFolder · 폴더 자동 펼침)은 그대로 둔다. 지금 MENU_GROUPS 에는 폴더가 없다.

import { useEffect, useState } from "react";

export type MenuKey =
  | "today_check"
  | "weekly_etf_check"
  | "workbench"
  | "workbench_holdings"
  | "etf_sector"
  | "holding_candidate_compare"
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
  | "data_status"
  | "unused_universe_watch";

export interface MenuItem {
  key: MenuKey;
  label: string;
  hint?: string;
}

// 그룹 안 폴더(POC6-15 · 한 단계만). 폴더 자체는 화면이 아니라 key 가 없다.
// (2026-11-19 부터 MENU_GROUPS 에 폴더 없음 · 틀은 그대로 둔다.)
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

// 7개 그룹 (설계서 §3.1·§3.2·Q2·Q3 + 사용자 "점검대상" 분리 지시 · 2026-11-19 형수님 직접 지시로 5 → 7 · 맨 위 주석).
// 각 화면 전환 key 는 정확히 한 그룹에만 1회 귀속 (중복·고아 0 · AC-2 · 상세 key 는 메뉴에 없음 · POC6-32 V2).
export const MENU_GROUPS: MenuGroup[] = [
  {
    id: "today",
    title: "오늘 확인",
    items: [
      { key: "today_check", label: "오늘의 투자 점검", hint: "코스피 위치 · 오늘 확인할 것 · 자료 상태" },
      // 2026-11-17 POC6-32 V2 — 형제 메뉴(힌트에 '후보'를 쓰지 않음).
      { key: "weekly_etf_check", label: "주간 ETF 점검", hint: "1개월 상위 ETF 흐름 · 고른 ETF 근거 · 보유 겹침 · 검토 기록" },
    ],
  },
  {
    id: "compare",
    title: "ETF보유 및 후보 선정",
    items: [
      // 2026-11-12 POC6-29: 「후보리스트」는 기존 `workbench` key 를 그대로 쓴다(다른 화면의 이동이 모두 이 key).
      { key: "workbench_holdings", label: "보유", hint: "내 보유의 비중 · 하락 · 약세 묶음 접점 · 판단 근거" },
      { key: "etf_sector", label: "섹터요약", hint: "같은 기간 상·하위 ETF의 업종 · 테마" },
      { key: "workbench", label: "후보리스트", hint: "같은 기간 상·하위 ETF 순위 · 표 · 목록 넘기기" },
      // 2026-11-17 POC6-32 V2 — 「보유와 후보 비교」 · 「ETF 구성종목」은 상세 화면(DETAIL_KEYS · 메뉴에 없음).
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
  // 2026-08-05 POC3-07 §5.3: 정상 업무와 시각적으로 분리된 관리 그룹(그때는 마지막 그룹).
  //   data_status 흡수 + 기존 dashboard(LEGACY) + 미리보기·샘플·미연결 격리.
  // 2026-08-16 사용자 직접 지시 — 진단 서랍에 정상 업무가 섞여 있어 분리했다.
  //   data_status 는 POC3-07 이 "placeholder" 로 보고 흡수했으나, 실제로는
  //   2026-06-08 부터 전체 ETF NAV·괴리율 조회 화면이었다(판단 근거가 낡음) → 복원.
  //   (「OCI 운영 상태」는 2026-09-27 에 승인·운영 그룹 「OCI 운영·적용」으로 합쳤다.)
  // 2026-11-19 형수님 직접 지시: 「보유·자료 관리」 바로 다음 · 「ETF NAV·괴리율 조회」 하나만 남는다
  //   (ML 연구 · 미사용 기능 = 그룹으로 올림 · 받은 알림 기록 = 「승인·운영」 · 개발·실험용 = 「미사용 기능」).
  {
    id: "diagnostics",
    title: "진단·상태",
    items: [
      // 2026-11-19 POC6-34(PLAN 판정 Q7 · PLAN N1 · N2 · I-27): 이름만 「데이터 상태」 → 「ETF NAV·괴리율 조회」(key 그대로).
      { key: "data_status", label: "ETF NAV·괴리율 조회", hint: "전체 ETF · 수집 상태 · 큰 괴리 찾기" },
    ],
  },
  // 2026-08-05 POC3-07 §5.4·§10.1: "승인·알림" → "승인·적용" 역할 축소
  //   (실제 승인 대상 = PARAM·seed OCI 적용). 정보 PUSH 카드·빈 승인 카드 없음.
  // 2026-09-27 사용자 직접 지시: 「승인·적용」과 「OCI 운영 상태」(`oci_status`)를
  //   한 화면 「OCI 운영·적용」으로 합쳤다. route key 는 `approval` 그대로이고
  //   `oci_status` 는 없앴다(① 지금 OCI 상태 → ② OCI 에 적용).
  // 2026-11-19 형수님 직접 지시: 「진단·상태」 다음 · 「받은 알림 기록」을 「OCI 운영·적용」 다음에 둔다.
  {
    id: "ops",
    title: "승인·운영",
    items: [
      { key: "approval", label: "OCI 운영·적용", hint: "OCI 상태 · 운영 기준 적용" },
      // 2026-10-07 POC5-03 설계 개정 2(사용자 결정): 받은 알림 · 당시 근거 · 이후 결과 기록.
      //   처음엔 「진단·상태」의 ML 실험 바로 아래 · 2026-11-19 형수님 직접 지시로 이 그룹으로 옮겼다.
      { key: "alert_records", label: "받은 알림 기록", hint: "받은 알림 · 당시 근거 · 이후 결과" },
    ],
  },
  // 2026-11-01 POC6-15(설계자 PLAN 판정 Q2): 「ML 실험」 → 「ML 연구」 두 화면.
  //   예측과 결과 비교 = 기존 `ml` key(06 전향 비교 · 카드 1) · 이전 자료·실험 = `ml_legacy`(카드 5).
  // 2026-11-19 형수님 직접 지시: 「진단·상태」 안 폴더 → 한 단계 올려 그룹(id `ml_research` 그대로 · 「승인·운영」 다음).
  {
    id: "ml_research",
    title: "ML 연구",
    items: [
      { key: "ml", label: "예측과 결과 비교", hint: "미리 기록한 예측 · 이후 실제 결과" },
      { key: "ml_legacy", label: "이전 자료·실험", hint: "예측 비교와 별개인 이전 자료 · 실험" },
    ],
  },
  // 2026-11-12 POC6-29 보완(Q-R5 · RESULT 판정 §4): 일상 메뉴에서 뺀 기능을 기능마다 하위 메뉴 하나로 둔다.
  //   힌트에 '후보'를 쓰지 않는다(판정 Q17 · POC6-32 V2 — 메뉴의 '후보'는 그룹 이름 · 「후보리스트」에만).
  // 2026-11-19 형수님 직접 지시: 「진단·상태」 안 폴더 → 한 단계 올려 그룹(id `unused_features` 그대로 · 「ML 연구」 다음 ·
  //   마지막 그룹). 「개발·실험용」을 「신규 ETF 관찰 점검」 다음에 둔다(형수님 판정 = 지금 쓰지 않는 화면 · 맨 위 주석).
  {
    id: "unused_features",
    title: "미사용 기능",
    items: [
      {
        key: "unused_universe_watch",
        label: "신규 ETF 관찰 점검",
        hint: "1개월 수익률 1위 ETF 수동 확인 · 실험용 초안",
      },
      { key: "diagnostics", label: "개발·실험용", hint: "미리보기 · 샘플 · 개발 호환 · LEGACY" },
    ],
  },
];

// 하위 호환: 기존에 평면 목록을 참조하던 코드/테스트를 위해 유지(그룹 · 폴더 평탄화).
export const MENU_ITEMS: MenuItem[] = MENU_GROUPS.flatMap(groupMenuItems);

// 2026-11-17 POC6-32 V2(PLAN §2 S4) — 메뉴에 없는 상세 화면 key(화면 안에서만 엶 · 보낸 화면 기록에 쌓임).
export const DETAIL_KEYS: readonly MenuKey[] = ["etf_exposure", "holding_candidate_compare"];
// 상세 화면 이름(메뉴 라벨이 없으므로 따로 둔다 · [← 보낸 화면으로] 안내에 씀).
const DETAIL_LABELS: Partial<Record<MenuKey, string>> = {
  etf_exposure: "ETF 구성종목",
  holding_candidate_compare: "보유와 후보 비교",
};

export function isDetailKey(key: MenuKey): boolean {
  return DETAIL_KEYS.includes(key);
}

// 강조할 메뉴 key — 상세 key 가 오면 「주간 ETF 점검」(기본값 · MainPanel 은 처음 보낸 화면의 key 를 넘김).
export function menuKeyOf(key: MenuKey): MenuKey {
  return isDetailKey(key) ? "weekly_etf_check" : key;
}

// 화면 이름 — 메뉴 라벨 또는 상세 화면 이름.
export function screenLabelOf(key: MenuKey): string {
  return DETAIL_LABELS[key] ?? MENU_ITEMS.find((it) => it.key === key)?.label ?? key;
}

// 모듈 로드 시 메뉴 귀속 무결성 검증 (계약: 상세가 아닌 MenuKey 는 정확히 1개 그룹에 1번 · 상세 key 는 0번).
// 누락·중복이면 첫 그룹 위장(fallback)으로 숨기지 않고 즉시 throw — dev/운영 모두 동일하게
// 명확한 오류로 종료한다. 화면 빌드·렌더 이전에 터지므로 "활성 그룹 없는 상태로 조용히 진행"
// 하는 경로 자체가 존재하지 않는다.
const ALL_MENU_KEYS: MenuKey[] = [
  "today_check",
  "weekly_etf_check",
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

function assertMenuGroupsCover(): void {
  const allItems = MENU_ITEMS;
  // 각 MenuKey 가 그룹 전체에서 몇 번 나타나는지 item 단위로 센다(메뉴 key = 정확히 1번 · 상세 key = 0번).
  // (그룹 단위 filter 로 세면 같은 그룹 안 동일 key 중복을 놓친다.)
  for (const key of ALL_MENU_KEYS) {
    const count = allItems.filter((it) => it.key === key).length;
    const want = isDetailKey(key) ? 0 : 1;
    if (count !== want) {
      throw new Error(
        `LeftSidebar 메뉴 귀속 계약 위반: MenuKey "${key}" 는 ${want}번 나타나야 하나 ${count}번. (메뉴 key = 정확히 1번 · 상세 key = 0번, 같은 그룹 내 중복 포함)`
      );
    }
  }
  // 상세 key 는 알려진 key 여야 한다.
  for (const key of DETAIL_KEYS) {
    if (!ALL_MENU_KEYS.includes(key)) {
      throw new Error(`LeftSidebar: 상세 key "${key}" 가 알려진 MenuKey 목록에 없음.`);
    }
  }
  // 정의된 항목 수 = 알려진 key 수 − 상세 key 수. 목록에 없는 신규 key 유입도 차단.
  const menuKeyCount = ALL_MENU_KEYS.length - DETAIL_KEYS.length;
  if (allItems.length !== menuKeyCount) {
    throw new Error(
      `LeftSidebar 메뉴 항목 수(${allItems.length})가 메뉴 key 수(${menuKeyCount})와 다름 — 미등록 key 유입.`
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
  // 강조할 화면 key(MainPanel = 처음 보낸 화면 · 상세 key 면 「주간 ETF 점검」으로 바꿔 강조)
  active: MenuKey;
  onSelect: (key: MenuKey) => void;
}

export default function LeftSidebar({ active: activeKey, onSelect }: Props) {
  // POC6-32 V2 — 상세 key 는 메뉴에 없으므로 강조할 메뉴 key 로 바꿔 쓴다(그룹 · 폴더 · 현재 위치 표시 모두).
  const active = menuKeyOf(activeKey);
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
