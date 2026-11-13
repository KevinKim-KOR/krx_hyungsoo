"use client";

// 개발·실험용 (diagnostics) — POC3-07 신규, 2026-08-16 범위 축소.
//
// 설계(§5.3): 정상 업무 메뉴와 시각적으로 분리된 마지막 관리 그룹.
//
// 2026-08-16 사용자 직접 지시로 **정상 업무에 쓰는 것들을 빼냈다.** 이 화면은 이제
// 진짜 개발·실험용만 남는다.
//   - DataStatusView         → `data_status`(데이터 상태) 메뉴로 복원.
//       POC3-07 이 "placeholder" 로 보고 흡수했으나, 실제로는 2026-06-08 NAV/Discount
//       Display FIX 로 이미 전체 ETF NAV·괴리율 조회 화면이 된 상태였다(판단 근거가 낡음).
//   - OciStartupStatusDetail → `oci_status`(OCI 운영 상태) 메뉴로 분리. 정상 업무 조회다.
//       (2026-09-27 사용자 직접 지시로 `oci_status` 는 「OCI 운영·적용」(`approval`)에 합쳐졌다.)
//   - ML 카드 3개            → `ml`(ML 실험) 메뉴로 이동.
//
// 남은 것은 미리보기·샘플(PREVIEW/TEST) · 개발 호환 점검 · LEGACY 대시보드뿐이다.
// 이 화면 지시로 OCI job·Telegram·SCP 를 자동 실행하지 않는다(side effect 없는 조회만).
//
// 2026-11-12 POC6-29(설계 §3 Q6 · PLAN 판정 Q6 · Q12): 「요즘 잘 오르는 ETF」에 있던 [신규 ETF 관찰 후보 갱신]을
//   처음엔 이 화면 맨 아래 「미사용 기능」 구역(맨 위 [미사용 기능] 버튼)으로 옮겼다.
//   → 같은 날 보완(보완 PLAN 판정 Q-R5 · RESULT 판정 §4): 사이드바 「진단·상태 › 미사용 기능 › 신규 ETF 관찰 점검」
//   (`unused_universe_watch` · UnusedFeatureView)으로 다시 옮겼다. 이 화면에는 옮긴 곳 한 줄과 이동 버튼만 남는다.
//   그 결과는 계속 아래 미리보기의 [저장된 보유 종목으로 초안 만들기] · PUSH-3 급등락 관찰 신호 초안이 읽는다.

import ManualPreviewSection from "./approval/ManualPreviewSection";
import DevCompatSection from "./approval/DevCompatSection";
import DashboardView from "./DashboardView";
import type { MenuKey } from "./LeftSidebar";
import type { Run } from "@/lib/api";

interface Props {
  run: Run | null;
  setRun: (run: Run | null) => void;
  onNavigate: (key: MenuKey) => void;
}

export default function DiagnosticsView({ run, setRun, onNavigate }: Props) {
  return (
    <section aria-labelledby="diagnostics-h">
      <h1 id="diagnostics-h">개발·실험용</h1>
      <p className="helper" style={{ marginBottom: 16 }}>
        정상 업무 화면이 아닙니다. 미리보기·샘플(PREVIEW/TEST), 개발 호환 점검,
        참고용 이전 화면(LEGACY)을 이곳에서 관리합니다. 데이터 상태·ML 연구는 각각
        별도 메뉴로, OCI 운영 상태는 「OCI 운영·적용」으로 옮겼습니다.
      </p>
      {/* POC6-29 보완(Q-R5): 미사용 기능은 사이드바 폴더로 옮겼다 — 옮긴 곳 한 줄 + 이동 버튼. */}
      <div className="message info" data-testid="diag-unused-moved">
        미사용 기능은 「진단·상태 › 미사용 기능」으로 옮겼습니다.
        <button
          type="button"
          className="wb-btn btn-md ec-inline"
          onClick={() => onNavigate("unused_universe_watch")}
        >
          「신규 ETF 관찰 점검」으로
        </button>
      </div>

      {/* A. 미리보기·샘플 (approval 에서 이동, PREVIEW/TEST 성격) */}
      <div className="diagnostics-preview">
        <h2>미리보기·샘플 (PREVIEW/TEST)</h2>
        <p className="helper" style={{ marginBottom: 12 }}>
          아래는 실제 자동 발송이 아니라 미리보기·샘플용입니다. 결과는 발송된 것이
          아닙니다.
        </p>
        <ManualPreviewSection run={run} setRun={setRun} />
        <DevCompatSection run={run} setRun={setRun} />
      </div>

      {/* B. LEGACY — 기존 대시보드 (참고용) */}
      <details className="card" style={{ marginTop: 24 }}>
        <summary
          style={{ cursor: "pointer", color: "var(--muted)", fontWeight: 600 }}
        >
          기존 대시보드 (LEGACY · 참고용) — 정상 운영 화면 아님
        </summary>
        <div style={{ marginTop: 12 }}>
          <DashboardView onNavigate={onNavigate} />
        </div>
      </details>
    </section>
  );
}
