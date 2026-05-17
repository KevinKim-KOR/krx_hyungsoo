"use client";

// POC2 PC UI Shell 1차 — Dashboard view (첫 화면).
//
// 표시 정책 (지시문 §3.2):
// - 최소 상태 요약 + 바로가기 중심.
// - TOP N 상세표 / 차트 / AI 투자세션 / 시장 국면 / 매수·매도 판단은 모두 금지.
// - API 없으면 실제 수치 억지로 붙이지 않음 — 정적 안내 문구로만 표시.

import type { MenuKey } from "./LeftSidebar";

interface Props {
  onNavigate: (key: MenuKey) => void;
}

export default function DashboardView({ onNavigate }: Props) {
  return (
    <section aria-labelledby="dashboard-h">
      <h1 id="dashboard-h">Dashboard</h1>
      <p className="subtitle">
        krx_alertor 운영 상태 요약과 메뉴 바로가기. 상세 화면은 좌측 메뉴에서 선택.
      </p>

      <div className="card">
        <h2>시스템 상태</h2>
        <ul className="dashboard-status-list">
          <li>
            <strong>시장 데이터 기반 구축 완료</strong> — FinanceDataReader +
            SQLite (etf_master / etf_daily_price / market_refresh_log).
          </li>
          <li>
            <strong>운영 의사결정 입력</strong> — 사용자 PC 작업 (주 2회 예상).
            메인 메뉴는 좌측에서.
          </li>
          <li>
            <strong>보조 알림 배관</strong> — Telegram 3-PUSH (보유 종목 상태 /
            신규 ETF 관찰 후보 / 급락 ETF 주의). 자동 매매 없음, 인간 최종 승인 게이트 유지.
          </li>
        </ul>
        <div className="helper" style={{ marginTop: 8 }}>
          마지막 market artifact / refresh 시각은 Data Status 화면에서 연결될 예정.
        </div>
      </div>

      <div className="card">
        <h2>다음 단계 (예정)</h2>
        <p className="helper">
          Market Discovery 화면에 FDR + SQLite 기반 ETF universe / 일간 / 1개월 /
          3개월 TOP N 상세표가 연결될 예정. 본 단계에서는 화면 자리만 마련.
        </p>
      </div>

      <div className="card">
        <h2>바로가기</h2>
        <div className="btn-row dashboard-shortcut-row">
          <button
            type="button"
            onClick={() => onNavigate("market_discovery")}
          >
            Market Discovery →
          </button>
          <button
            type="button"
            onClick={() => onNavigate("holdings")}
          >
            Holdings →
          </button>
          <button
            type="button"
            onClick={() => onNavigate("approval")}
          >
            Approval / Telegram →
          </button>
          <button
            type="button"
            onClick={() => onNavigate("data_status")}
          >
            Data Status →
          </button>
        </div>
      </div>
    </section>
  );
}
