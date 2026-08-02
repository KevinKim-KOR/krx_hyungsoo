"use client";

// OCI 적용·알림 화면 (기존 approval route key 유지).
//
// 2026-08-01 승인·알림 역할 분리 및 재배치.
//   설계 정정(Q1-c): push_kind 3종은 모두 정보 PUSH. 현재 계약에 "투자 판단 초안"
//   식별 필드가 없으므로 판단 초안 영역·승인 대기 표현·빈 자리표시자를 만들지 않는다.
//   화면 명칭 = "OCI 적용·알림". 내부 approval route key·MainPanel 분기·draft→approval
//   자동 이동 경로는 불변.
//
//   구조:
//     A구간 — 운영 기능 역할 정리
//       1) OciAlertHeader        : 화면 역할 안내 (OCI 적용 / 정보 PUSH 구분)
//       2) ThreePushParamCard    : OCI 운영 기준 적용 (주 작업 · 계약 불변)
//       3) InfoPushGuideCards    : 정보 PUSH 운영 기준 안내 (승인 run 미포함)
//     B구간 — 수동 점검과 현재 run 정리
//       4) ManualPreviewSection  : 미리보기·수동 전달 점검 (ThreePushDraftCard + 현재 run
//                                  중 신뢰 가능한 push_kind 만). 자동 PUSH 와 구분.
//       (dev) DevCompatSection   : 개발·호환 점검 (샘플 + push_kind=null run). 기본 접힘.
//     C구간(예정) — UniverseRefreshPanel 을 "요즘 잘 오르는 ETF" 로 이동, 전체 정리.

import UniverseRefreshPanel from "./UniverseRefreshPanel";
import OciAlertHeader from "./approval/OciAlertHeader";
import InfoPushGuideCards from "./approval/InfoPushGuideCards";
import ManualPreviewSection from "./approval/ManualPreviewSection";
import DevCompatSection from "./approval/DevCompatSection";
import ThreePushParamCard from "./ThreePushParamCard";
import type { Run } from "@/lib/api";

// RunPanel 은 ManualPreviewSection / DevCompatSection 내부에서 사용된다(여기서 직접 참조 없음).

interface Props {
  run: Run | null;
  setRun: (run: Run | null) => void;
}

export default function ApprovalTelegramView({ run, setRun }: Props) {
  return (
    <section aria-labelledby="approval-h">
      {/* A구간 1) 화면 역할 안내 */}
      <OciAlertHeader />

      {/* A구간 2) OCI 운영 기준 적용 — 주 작업 (계약 불변) */}
      <ThreePushParamCard />

      {/* A구간 3) 정보 PUSH 운영 기준 — 안내만 (승인 run 미포함) */}
      <InfoPushGuideCards />

      {/* B구간 4) 미리보기·수동 전달 점검 (자동 PUSH 와 구분) */}
      <ManualPreviewSection run={run} setRun={setRun} />

      {/* C구간에서 "요즘 잘 오르는 ETF" 로 이동 예정 — 기능 누락 방지 임시 유지 */}
      <div className="pending-reorg-note card">
        아래 <strong>신규 ETF 관찰 후보</strong> 갱신은 다음 단계(C)에서{" "}
        <strong>요즘 잘 오르는 ETF</strong> 화면으로 이동합니다.
      </div>
      <UniverseRefreshPanel />

      {/* 개발·호환 점검 — 기본 접힘 (샘플 + push_kind=null run) */}
      <DevCompatSection run={run} setRun={setRun} />
    </section>
  );
}
