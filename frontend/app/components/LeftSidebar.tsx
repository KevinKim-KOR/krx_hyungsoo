"use client";

// POC2 PC UI Shell — 좌측 메뉴 컴포넌트.
//
// 2026-05-21 갱신: AI Sessions 메뉴 추가 (Market Discovery 와 분리, 지시문 §3).
// 메뉴 순서: Dashboard / Market Discovery / AI Sessions / Holdings /
// Approval & Telegram / Data Status.

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

// 2026-07-29 POC3-01 — 새 기본 진입 화면 "오늘의 투자 점검" 추가.
// 기존 Dashboard 는 삭제하지 않고 "기존 대시보드" 로 라벨만 바꿔 보존 (§6.2·§10·AC-10).
// AC-7 사용자 언어: 좌측 메뉴 라벨도 설계서 §7 매핑을 적용 (내부 용어 비노출).
//   Market Discovery→요즘 잘 오르는 ETF · Workbench→ETF 비교하기 ·
//   Holdings→내가 가진 ETF · ETF Exposure→ETF 구성종목 · Approval/Data Status→한국어.
// key(라우팅 식별자) 는 바꾸지 않는다 — 표시 라벨만 사용자 언어로.
// hint 도 화면에 노출되므로 label 과 동일하게 금지 용어(후보/Evidence/Workbench/
// Unavailable/Pending 등)를 쓰지 않는다 (AC-7 즉시 FAIL 조건).
export const MENU_ITEMS: MenuItem[] = [
  { key: "today_check", label: "오늘의 투자 점검", hint: "코스피 위치 · 오늘 확인할 것 · 자료 상태" },
  { key: "dashboard", label: "기존 대시보드", hint: "이전 상태 화면 (참고용)" },
  { key: "workbench", label: "ETF 비교하기", hint: "관심·보유 ETF 한 화면 비교" },
  { key: "market_discovery", label: "요즘 잘 오르는 ETF", hint: "강한 흐름 ETF 찾기" },
  { key: "etf_exposure", label: "ETF 구성종목", hint: "담고 있는 종목 / 중복" },
  { key: "ai_sessions", label: "AI 투자 세션", hint: "AI 질문/답변 기록" },
  { key: "holdings", label: "내가 가진 ETF", hint: "보유 현황 / 평가" },
  { key: "approval", label: "승인 / 알림", hint: "승인 대기 / 발송 결과" },
  { key: "data_status", label: "데이터 상태", hint: "시장 데이터 상태 (예정)" },
];

interface Props {
  active: MenuKey;
  onSelect: (key: MenuKey) => void;
}

export default function LeftSidebar({ active, onSelect }: Props) {
  return (
    <aside className="app-sidebar" aria-label="좌측 메뉴">
      <div className="sidebar-brand">krx_alertor</div>
      <nav>
        <ul className="sidebar-menu">
          {MENU_ITEMS.map((item) => {
            const isActive = item.key === active;
            return (
              <li
                key={item.key}
                className={isActive ? "active" : ""}
              >
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
      </nav>
    </aside>
  );
}
