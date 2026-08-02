"use client";

// POC2 PC UI Shell 1차 — 좌측 메뉴 기반 화면 컨테이너.
//
// 정책 (지시문):
// - 라우팅은 App Router 디렉토리 분기 대신 본 컴포넌트의 클라이언트 상태로 처리
//   ("메뉴 폴더 구조는 만들지 않음" — 지시문 §3.1).
// - 첫 진입 시 "오늘의 투자 점검"(today_check).
// - run state 는 본 컨테이너가 controlled 로 보유. ApprovalTelegramView 가 공유.
// - 2026-08-02 POC3-05 DESIGN_V2: "보유·자료 관리" 를 보유 현황(holdings)·종목 관리
//   (holdings_manage)·확인 근거(holdings_evidence)·데이터 상태(data_status) 로 분리.
//   초안 생성 버튼이 Holdings 계열에서 제거되어 draft→approval 자동 전환은 없다(§4.6).

import { useState } from "react";
import AISessionsView from "./AISessionsView";
import ApprovalTelegramView from "./ApprovalTelegramView";
import DashboardView from "./DashboardView";
import TodayInvestmentCheckView from "./TodayInvestmentCheckView";
import JudgmentWorkbenchView from "./JudgmentWorkbenchView";
import DataStatusView from "./DataStatusView";
import ETFExposureView from "./ETFExposureView";
import HoldingsView from "./HoldingsView";
import HoldingsManageView from "./HoldingsManageView";
import HoldingsEvidenceView from "./HoldingsEvidenceView";
import LeftSidebar, { type MenuKey } from "./LeftSidebar";
import MarketDiscoveryView from "./MarketDiscoveryView";
import type { Run } from "@/lib/api";

export default function MainPanel() {
  // 2026-07-29 POC3-01 — 첫 진입 기본 화면을 "오늘의 투자 점검" 으로 전환.
  // 기존 Dashboard 는 "기존 대시보드" 메뉴로 보존 (§6·§10·AC-10).
  const [active, setActive] = useState<MenuKey>("today_check");
  // run state 는 ApprovalTelegramView(OCI 적용·알림)가 controlled 로 공유.
  // 2026-08-02 POC3-05 DESIGN_V2 §4.6: 초안 생성 버튼이 Holdings 계열에서 제거되어
  //   draft→approval 자동 전환(구 handleDraftCreated)은 B구간에서 사용되지 않는다.
  //   초안 생성은 C구간에서 OCI 적용·알림의 수동 점검 영역으로 이동한다.
  const [run, setRun] = useState<Run | null>(null);

  let view: React.ReactNode;
  switch (active) {
    case "today_check":
      view = <TodayInvestmentCheckView onNavigate={setActive} />;
      break;
    case "dashboard":
      view = <DashboardView onNavigate={setActive} />;
      break;
    case "workbench":
      view = <JudgmentWorkbenchView onNavigate={setActive} />;
      break;
    case "market_discovery":
      // 2026-05-21 — "AI Sessions로 넘기기" 클릭 시 ai_sessions 화면 전환.
      view = <MarketDiscoveryView onNavigate={setActive} />;
      break;
    case "etf_exposure":
      // 2026-05-27 — ETF Constituents & Overlap 1차. "AI Sessions 로 넘기기"
      // 도 onNavigate 로 분기.
      view = <ETFExposureView onNavigate={setActive} />;
      break;
    case "ai_sessions":
      view = <AISessionsView />;
      break;
    case "holdings":
      // POC3-05 DESIGN_V2: "보유 현황" — 평가 현황·시세 갱신 (읽기 중심, 입력폼 없음).
      view = <HoldingsView onNavigate={setActive} />;
      break;
    case "holdings_manage":
      // "종목 관리" — 입력·수정·삭제·저장 (초안 생성 없음, §4.6).
      view = <HoldingsManageView onNavigate={setActive} />;
      break;
    case "holdings_evidence":
      // "확인 근거" — 오늘 먼저 볼 ETF와 수치 근거 (읽기 전용).
      view = <HoldingsEvidenceView onNavigate={setActive} />;
      break;
    case "approval":
      view = <ApprovalTelegramView run={run} setRun={setRun} />;
      break;
    case "data_status":
      view = <DataStatusView />;
      break;
  }

  // 2026-06-03 — 모든 메뉴를 Market Discovery 와 동일한 폭으로 통일 (사용자 요청).
  // globals.css 의 .app-content max-width 가 본 정책을 반영한다.

  return (
    <div className="app-shell">
      <LeftSidebar active={active} onSelect={setActive} />
      <main className="app-content">{view}</main>
    </div>
  );
}
