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
//   - ML 카드 3개            → `ml`(ML 실험) 메뉴로 이동.
//
// 남은 것은 미리보기·샘플(PREVIEW/TEST) · 개발 호환 점검 · LEGACY 대시보드뿐이다.
// 이 화면 지시로 OCI job·Telegram·SCP 를 자동 실행하지 않는다(side effect 없는 조회만).

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
        참고용 이전 화면(LEGACY)을 이곳에서 관리합니다. 데이터 상태·OCI 운영 상태·ML
        실험은 각각 별도 메뉴로 분리됐습니다.
      </p>

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
