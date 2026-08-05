"use client";

// 승인·적용 화면 (기존 approval route key 유지).
//
// 2026-08-05 POC3-07 §5.4·§7·§10.1 역할 축소:
//   이 화면은 "실제 승인 대상 = PARAM·seed 운영 기준의 OCI 적용" 만 다룬다.
//   - 정보 PUSH(Market·Holdings·Spike)는 승인 대상이 아니다 → 카드 만들지 않음.
//   - 식별 계약이 없는 빈 승인 카드를 만들지 않는다(직전 POC3 확정 유지).
//   - 미리보기·샘플·개발 호환 점검·현재 run 표시는 진단·상태(diagnostics)로 이동했다.
//   - PUSH 실행 결과는 기동 시 상태 요약(첫 화면)·진단·상태에서만 확인한다.
//
//   내부 approval route key·MainPanel 분기는 불변. run/setRun 은 더 이상 이 화면에서
//   사용하지 않는다(미리보기가 진단·상태로 이동).

import OciAlertHeader from "./approval/OciAlertHeader";
import ThreePushParamCard from "./ThreePushParamCard";

export default function ApprovalTelegramView() {
  return (
    <section aria-labelledby="approval-h">
      {/* 화면 역할 안내 (OCI 적용 대상 = 운영 기준) */}
      <OciAlertHeader />

      {/* OCI 운영 기준 적용 — 이 화면의 유일한 실제 승인·적용 작업 (계약 불변) */}
      <ThreePushParamCard />
    </section>
  );
}
