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
// - 2026-11-17 POC6-32 V2(PLAN §2 S4 · §9 I-1 ~ I-5) — 보낸 화면 기록(lib/detailNav):
//   - 화면 안에서 상세(「보유와 후보 비교」 · 「ETF 구성종목」 · 메뉴에 없음)를 열면 보낸 화면을 내리지 않고 숨겨 둔다.
//     상세 위에 [← 보낸 화면으로] 줄을 이 컨테이너가 그린다(상세 화면은 고치지 않아도 됨) · 한 단계씩 돌아간다.
//   - 좌측 메뉴를 누르면 기록을 버리고 처음부터 그린다(숨겨 둔 화면도 내림). 화면 안에서 상세가 아닌 화면으로 가도 버린다.
//   - 상세가 열린 동안 좌측 메뉴 강조 = 처음 보낸 화면의 메뉴.
//   - 숨겨 둔 화면이 부르는 이동은 무시한다(보이는 화면만 이동을 부름).

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import AISessionsView from "./AISessionsView";
import AlertRecordsView from "./AlertRecordsView";
import ApprovalTelegramView from "./ApprovalTelegramView";
import DiagnosticsView from "./DiagnosticsView";
import MLView from "./MLView";
import DataStatusView from "./DataStatusView";
import TodayInvestmentCheckView from "./TodayInvestmentCheckView";
import WeeklyEtfCheckView from "./WeeklyEtfCheckView";
import JudgmentWorkbenchView from "./JudgmentWorkbenchView";
import WorkbenchHoldingsView from "./WorkbenchHoldingsView";
import ETFExposureView from "./ETFExposureView";
import HoldingsView from "./HoldingsView";
import HoldingsManageView from "./HoldingsManageView";
import HoldingsEvidenceView from "./HoldingsEvidenceView";
import LeftSidebar, { isDetailKey, screenLabelOf, type MenuKey } from "./LeftSidebar";
import SectorSummaryView from "./SectorSummaryView";
import HoldingCandidateCompareView from "./HoldingCandidateCompareView";
import UnusedFeatureView from "./UnusedFeatureView";
import type { Run } from "@/lib/api";
import {
  navBack,
  navGo,
  navHighlight,
  navSelect,
  navSender,
  navStack,
  navStart,
  type NavState,
} from "@/lib/detailNav";

type Navigate = (key: MenuKey) => void;

function renderView(
  key: MenuKey,
  onNavigate: Navigate,
  run: Run | null,
  setRun: (r: Run | null) => void,
): React.ReactNode {
  switch (key) {
    case "today_check":
      return <TodayInvestmentCheckView onNavigate={onNavigate} />;
    case "weekly_etf_check":
      // 2026-11-17 POC6-32 V2 — 「오늘 확인 › 주간 ETF 점검」(메뉴로 열 때마다 새로 그려 주간 자료를 새로 읽음).
      return <WeeklyEtfCheckView onNavigate={onNavigate} />;
    case "workbench":
      return <JudgmentWorkbenchView onNavigate={onNavigate} />;
    case "workbench_holdings":
      return <WorkbenchHoldingsView onNavigate={onNavigate} />;
    case "etf_sector":
      // 2026-11-12 POC6-29 — 「섹터요약」(POC6-28 「후보」 [섹터 요약] 탭을 독립 메뉴로 · 자기 조건).
      return <SectorSummaryView onNavigate={onNavigate} />;
    case "holding_candidate_compare":
      // 2026-11-12 POC6-29 — 「보유와 후보 비교」(C 「요즘 잘 오르는 ETF › 보유와 비교」를 옮김).
      // 2026-11-17 POC6-32 V2 — 상세 화면(메뉴에 없음 · 화면 안에서만 엶).
      return <HoldingCandidateCompareView onNavigate={onNavigate} />;
    case "etf_exposure":
      // 2026-05-27 — ETF Constituents & Overlap 1차. "AI Sessions 로 넘기기"
      // 도 onNavigate 로 분기. 2026-11-17 POC6-32 V2 — 상세 화면(메뉴에 없음 · 화면 안에서만 엶).
      return <ETFExposureView onNavigate={onNavigate} />;
    case "ai_sessions":
      return <AISessionsView />;
    case "holdings":
      // POC3-05 DESIGN_V2: "보유 현황" — 평가 현황·시세 갱신 (읽기 중심, 입력폼 없음).
      return <HoldingsView onNavigate={onNavigate} />;
    case "holdings_manage":
      // "종목 관리" — 입력·수정·삭제·저장 (초안 생성 없음, §4.6).
      return <HoldingsManageView onNavigate={onNavigate} />;
    case "holdings_evidence":
      // "확인 근거" — 보유 ETF의 수치와 확인 근거 (읽기 전용 · 사용자 선택 정렬 · POC5-UI-02).
      //   POC6-33(PLAN E11) — 상세의 화면 이동 버튼을 빼서 onNavigate 를 넘기지 않는다.
      return <HoldingsEvidenceView />;
    case "approval":
      // 「OCI 운영·적용」 — ① 지금 OCI 상태(읽기만) · ② OCI 에 적용.
      //   2026-09-27 사용자 직접 지시로 「OCI 운영 상태」(`oci_status`)를 여기로 합쳤다.
      return <ApprovalTelegramView />;
    case "diagnostics":
      // 「개발·실험용」 — 미리보기/샘플(PREVIEW/TEST) · LEGACY 대시보드. run state 공유.
      //   (POC3-07 때 흡수했던 기동 시 OCI 상태 · 데이터 상태는 2026-08-16 에
      //   따로 나갔다. OCI 상태는 2026-09-27 부터 「OCI 운영·적용」(`approval`) 안에 있다.)
      return <DiagnosticsView run={run} setRun={setRun} onNavigate={onNavigate} />;
    case "ml":
      // 2026-08-16 사용자 지시 — 흩어져 있던 ML 카드 5개를 한 메뉴로 모음.
      // 2026-11-01 POC6-15 — 「ML 연구 › 예측과 결과 비교」(06 전향 비교 카드 1개 · key 그대로).
      return <MLView key="ml-forward" page="forward" />;
    case "ml_legacy":
      // 2026-11-01 POC6-15 — 「ML 연구 › 이전 자료·실험」(현재 예측 비교와 별개인 카드 5개).
      return <MLView key="ml-legacy" page="legacy" />;
    case "alert_records":
      // 2026-10-07 POC5-03 설계 개정 2 — 받은 알림 · 당시 근거 · 이후 결과(사후 ML 검토용).
      return <AlertRecordsView />;
    case "data_status":
      // 2026-08-16 — POC3-07 이 diagnostics 로 흡수했던 것을 정상 업무 조회로 복원.
      return <DataStatusView />;
    case "unused_universe_watch":
      // 2026-11-12 POC6-29 보완(Q-R5) — 「미사용 기능 › 신규 ETF 관찰 점검」(기능마다 같은 틀 · 열 때 요청 0 ·
      //   2026-11-19 형수님 직접 지시로 「진단·상태」 안 폴더 → 그룹).
      return <UnusedFeatureView key="unused-universe-watch" feature="universe_watch" onNavigate={onNavigate} />;
  }
}

// 상세 위 한 줄 — [← 보낸 화면으로](중간 버튼 40px) · 돌아갈 화면 이름.
function BackBar({ label, onBack }: { label: string; onBack: () => void }) {
  return (
    <nav className="dn-back" aria-label="보낸 화면으로 돌아가기" data-testid="dn-back">
      <button type="button" className="wb-btn btn-md" onClick={onBack}>
        ← 보낸 화면으로
      </button>
      <span className="dn-back-from">
        보낸 화면 「{label}」 · 돌아가면 고른 것 · 조건이 그대로입니다
      </span>
    </nav>
  );
}

export default function MainPanel() {
  // 2026-07-29 POC3-01 — 첫 진입 기본 화면을 "오늘의 투자 점검" 으로 전환.
  // 2026-08-05 POC3-07 — 기존 Dashboard 는 진단·상태(diagnostics) 안 LEGACY 로 흡수.
  // 2026-11-17 POC6-32 V2 — 지금 화면 + 숨겨 둔 보낸 화면 기록(lib/detailNav · 이 탭 메모리만).
  const [nav, setNav] = useState<NavState<MenuKey>>(() => navStart<MenuKey>("today_check"));
  const active = nav.active;
  // run state 는 「개발·실험용」(DiagnosticsView · 2026-11-19 부터 「미사용 기능」 그룹)의 미리보기·샘플 영역이 controlled 로 공유.
  //   2026-08-05 POC3-07: 미리보기·샘플이 승인·적용에서 진단·상태로 이동하며 run 공유
  //   대상도 DiagnosticsView 로 옮겨졌다. 자동 발송 아님(PREVIEW/TEST).
  const [run, setRun] = useState<Run | null>(null);

  // 2026-11-14 형수님 결정 — 화면이 바뀌면(좌측 메뉴 · 화면 안 이동 버튼 · [← 보낸 화면으로] 모두 여기 한 곳) 맨 위에서 시작한다.
  //   메뉴는 새 페이지가 아니라 같은 창의 내용만 바꾸므로, 그대로 두면 앞 화면에서 내려가 있던 창 스크롤이 남아
  //   더 짧은 화면은 맨 아래가 보였다(「오늘의 투자 점검」을 내린 뒤 「보유」 → 맨 아래 · 실화면 재현).
  //   그리기 전(layout effect)에 올려 새 화면이 아래에 잠깐 보이지 않게 한다. 첫 진입 · 같은 메뉴 다시 누름은 그대로.
  const shownId = useRef(active.id);
  useLayoutEffect(() => {
    if (shownId.current === active.id) return;
    shownId.current = active.id;
    window.scrollTo(0, 0);
  }, [active.id]);

  // 화면마다 자기 번호로 묶은 이동 함수(같은 화면에는 늘 같은 함수 · 예전 setActive 처럼 바뀌지 않음).
  const navFns = useRef(new Map<number, Navigate>());
  const stack = navStack(nav);
  const navFor = (id: number): Navigate => {
    let f = navFns.current.get(id);
    if (!f) {
      f = (key: MenuKey) => setNav((s) => navGo(s, id, key, isDetailKey(key)));
      navFns.current.set(id, f);
    }
    return f;
  };
  // 내린 화면의 이동 함수는 버린다(그린 뒤).
  useEffect(() => {
    const live = new Set(navStack(nav).map((e) => e.id));
    for (const id of Array.from(navFns.current.keys())) {
      if (!live.has(id)) navFns.current.delete(id);
    }
  }, [nav]);
  const sender = navSender(nav);

  // 2026-06-03 — 모든 메뉴를 Market Discovery 와 동일한 폭으로 통일 (사용자 요청).
  // globals.css 의 .app-content max-width 가 본 정책을 반영한다.

  return (
    <div className="app-shell">
      <LeftSidebar active={navHighlight(nav)} onSelect={(key) => setNav((s) => navSelect(s, key))} />
      <main className="app-content">
        {sender ? <BackBar label={screenLabelOf(sender.key)} onBack={() => setNav((s) => navBack(s))} /> : null}
        {stack.map((e) => (
          <div key={e.id} hidden={e.id !== active.id} data-screen={e.key}>
            {renderView(e.key, navFor(e.id), run, setRun)}
          </div>
        ))}
      </main>
    </div>
  );
}
