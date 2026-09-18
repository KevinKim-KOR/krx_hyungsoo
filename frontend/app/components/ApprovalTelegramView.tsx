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
// 2026-09-16 POC3-02C-OPS-01 (설계자 배치 판단 (a)): 장중 급등락 설정 카드를
//   ThreePushParamCard 아래에 추가했다. 위 2026-08-05 의 "정보 PUSH 는 승인
//   대상이 아니다" 는 그대로다 — 새 카드는 **정보 PUSH 가 아니라 운영 기준
//   (사업군·대표 ETF·판정 정책) 의 승인·OCI 적용**이라 이 화면 역할과 같다.
//   신규 메뉴·라우트를 만들지 않는다.
//
//   내부 approval route key·MainPanel 분기는 불변. run/setRun 은 더 이상 이 화면에서
//   사용하지 않는다(미리보기가 진단·상태로 이동).

import OciAlertHeader from "./approval/OciAlertHeader";
import ThreePushParamCard from "./ThreePushParamCard";
import IntradayConfigCard from "./IntradayConfigCard";

export default function ApprovalTelegramView() {
  return (
    <section aria-labelledby="approval-h">
      {/* 화면 역할 안내 (OCI 적용 대상 = 운영 기준) */}
      <OciAlertHeader />

      {/* OCI 운영 기준 적용 — 기존 계약 불변 */}
      <ThreePushParamCard />

      {/* POC3-02C-OPS-01 (2026-09-16) — 장중 급등락 설정.
          위 PARAM 이 전체 PUSH 운영 기준이고, 이것은 그 아래의 장중 전용
          설정이라 순서를 이렇게 둔다(설계자 배치 판단 (a)).
          신규 메뉴·라우트를 만들지 않고 이 화면에만 붙인다. */}
      <IntradayConfigCard />
    </section>
  );
}
