"use client";

// POC2 PC UI Shell 1차 — 좌측 메뉴 기반 화면 컨테이너.
//
// 정책 (지시문):
// - 라우팅은 App Router 디렉토리 분기 대신 본 컴포넌트의 클라이언트 상태로 처리
//   ("메뉴 폴더 구조는 만들지 않음" — 지시문 §3.1).
// - 첫 진입 시 Dashboard.
// - 5개 메뉴: Dashboard / Market Discovery / Holdings / Approval & Telegram / Data Status.
// - run state 는 본 컨테이너가 controlled 로 보유. HoldingsView / ApprovalTelegramView
//   가 동일 run state 를 공유.
// - HoldingsClient 가 draft 를 생성하면 자동으로 Approval / Telegram 메뉴로 이동
//   (기존 단일 페이지에서 즉시 noticed 되던 운영 동작 보존 — AC-11).

import { useCallback, useState } from "react";
import AISessionsView from "./AISessionsView";
import ApprovalTelegramView from "./ApprovalTelegramView";
import DashboardView from "./DashboardView";
import DataStatusView from "./DataStatusView";
import ETFExposureView from "./ETFExposureView";
import HoldingsView from "./HoldingsView";
import LeftSidebar, { type MenuKey } from "./LeftSidebar";
import MarketDiscoveryView from "./MarketDiscoveryView";
import type { Run } from "@/lib/api";

export default function MainPanel() {
  const [active, setActive] = useState<MenuKey>("dashboard");
  const [run, setRun] = useState<Run | null>(null);

  const handleDraftCreated = useCallback(
    (next: Run | null) => {
      setRun(next);
      if (next !== null) {
        // draft 가 생성되면 사용자가 결과를 즉시 확인할 수 있도록 Approval 화면으로 전환.
        setActive("approval");
      }
    },
    []
  );

  let view: React.ReactNode;
  switch (active) {
    case "dashboard":
      view = <DashboardView onNavigate={setActive} />;
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
      view = <HoldingsView onDraftCreated={handleDraftCreated} />;
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
