"use client";

// 「OCI 운영·적용」 화면 (기존 approval route key 유지).
//
// 2026-08-05 POC3-07 §5.4·§7·§10.1 역할 축소:
//   이 화면은 "실제 승인 대상 = PARAM·seed 운영 기준의 OCI 적용" 만 다룬다.
//   - 정보 PUSH(Market·Holdings·Spike)는 승인 대상이 아니다 → 카드 만들지 않음.
//   - 식별 계약이 없는 빈 승인 카드를 만들지 않는다(직전 POC3 확정 유지).
//   - 미리보기·샘플·개발 호환 점검·현재 run 표시는 진단·상태(diagnostics)로 이동했다.
//
// 2026-09-16 POC3-02C-OPS-01 (설계자 배치 판단 (a)): 장중 급등락 설정 카드를
//   ThreePushParamCard 아래에 추가했다. 위 2026-08-05 의 "정보 PUSH 는 승인
//   대상이 아니다" 는 그대로다 — 새 카드는 **정보 PUSH 가 아니라 운영 기준
//   (사업군·대표 ETF·판정 정책) 의 승인·OCI 적용**이라 이 화면 역할과 같다.
//
// 2026-09-27 사용자 직접 지시: 「승인·적용」과 「OCI 운영 상태」(`oci_status`)를
//   한 화면 「OCI 운영·적용」으로 합쳤다. 위에서 아래로:
//     ① 지금 OCI 상태 (읽기만) — OciStatusPanel(기동 시 1회 읽은 요약 + 표)
//     ② OCI 에 적용 (버튼으로 반영) — ThreePushParamCard → IntradayConfigCard
//   읽기(①)와 쓰기(②)를 섹션 제목으로 갈라 둔다. 각 카드의 동작·계약은 그대로다.
//
//   내부 approval route key·MainPanel 분기는 불변. run/setRun 은 더 이상 이 화면에서
//   사용하지 않는다(미리보기가 진단·상태로 이동).

import { useCallback, useState } from "react";

import OciAlertHeader from "./approval/OciAlertHeader";
import OciStatusPanel from "./OciStatusView";
import ThreePushParamCard from "./ThreePushParamCard";
import IntradayConfigCard from "./IntradayConfigCard";

export default function ApprovalTelegramView() {
  // POC3-02D-OPS-04 항목 6 — ② 운영 기준 전달이 끝나면 ① 을 다시 읽어 '운영 기준 활성'
  // 행이 바로 바뀌게 한다(OCI 는 다시 읽지 않는다).
  const [ociReload, setOciReload] = useState(0);
  const onDelivered = useCallback(() => setOciReload((k) => k + 1), []);
  return (
    <section aria-labelledby="approval-h">
      {/* 화면 역할 안내 (① 읽기 · ② OCI 적용) */}
      <OciAlertHeader />

      {/* ① 읽기만 — PC 백엔드 기동 시 1회 읽은 OCI 상태. 버튼 없음. */}
      <section className="ops-section" aria-labelledby="ops-now-h">
        <h2 id="ops-now-h" className="ops-section-h">
          ① 지금 OCI 상태 (읽기만)
        </h2>
        <OciStatusPanel reloadKey={ociReload} />
      </section>

      {/* ② 버튼으로 반영 — 운영 기준 → 장중 급등락 설정 순서(설계자 배치 판단 (a)).
          위 PARAM 이 전체 PUSH 운영 기준이고, 아래는 그 아래의 장중 전용 설정이다. */}
      <section className="ops-section" aria-labelledby="ops-apply-h">
        <h2 id="ops-apply-h" className="ops-section-h">
          ② OCI 에 적용 (버튼으로 반영)
        </h2>
        <ThreePushParamCard onDelivered={onDelivered} />
        <IntradayConfigCard />
      </section>
    </section>
  );
}
