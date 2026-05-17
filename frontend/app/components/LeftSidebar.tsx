"use client";

// POC2 PC UI Shell 1차 — 좌측 메뉴 컴포넌트.
//
// 5개 메뉴 고정 (지시문 §3.1):
// Dashboard / Market Discovery / Holdings / Approval & Telegram / Data Status

export type MenuKey =
  | "dashboard"
  | "market_discovery"
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
  { key: "market_discovery", label: "Market Discovery", hint: "ETF TOP N (예정)" },
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
