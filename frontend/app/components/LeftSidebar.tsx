"use client";

// POC2 PC UI Shell — 좌측 메뉴 컴포넌트.
//
// 2026-05-21 갱신: AI Sessions 메뉴 추가 (Market Discovery 와 분리, 지시문 §3).
// 메뉴 순서: Dashboard / Market Discovery / AI Sessions / Holdings /
// Approval & Telegram / Data Status.

export type MenuKey =
  | "dashboard"
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

export const MENU_ITEMS: MenuItem[] = [
  { key: "dashboard", label: "Dashboard", hint: "시스템 상태 + 바로가기" },
  { key: "market_discovery", label: "Market Discovery", hint: "ETF 후보 발굴" },
  { key: "etf_exposure", label: "ETF Exposure", hint: "구성종목 / 중복률" },
  { key: "ai_sessions", label: "AI Sessions", hint: "AI 질문/답변 기록" },
  { key: "holdings", label: "Holdings", hint: "보유 현황 / 평가" },
  { key: "approval", label: "Approval / Telegram", hint: "승인 대기 / 발송 결과" },
  { key: "data_status", label: "Data Status", hint: "시장 데이터 상태 (예정)" },
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
