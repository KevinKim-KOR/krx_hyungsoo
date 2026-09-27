"use client";

// 「OCI 운영·적용」 — 화면 상단 역할 안내.
//
// 2026-08-05 POC3-07 §5.4·§7·§10.1 역할 축소:
//   이 화면의 실제 작업은 "PC 에서 확정한 운영 기준(PARAM·seed)의 OCI 적용" 하나다.
//   정보 PUSH(시장·보유·급등락)는 승인 대상이 아니고 OCI 가 자동 발송한다 — 여기서
//   카드로 다루지 않는다.
//   투자 판단 초안 영역·승인 대기 표현·빈 자리표시자는 만들지 않는다(식별 필드 없음).
//
// 2026-09-27 사용자 직접 지시: 「OCI 운영 상태」를 이 화면에 합쳐 제목을
//   「OCI 운영·적용」으로 바꿨다(① 지금 OCI 상태 → ② OCI 에 적용). 예전 안내
//   "발송 결과는 진단·상태에서 확인" 은 사실이 아니어서 뺐다 — PUSH 발송 여부는
//   이 앱이 아니라 Telegram 에서 확인한다(① 표의 「PUSH 발송 결과」 행과 같은 말).

export default function OciAlertHeader() {
  return (
    <header className="oci-alert-header">
      <h1 id="approval-h">OCI 운영·적용</h1>
      <p className="subtitle">
        ① 에서 지금 OCI 상태를 확인하고, ② 에서 PC 에서 확정한 운영 기준(PARAM ·
        장중 급등락 설정)을 사용자가 <strong>[적용]</strong> 버튼으로 OCI 에
        반영합니다. 적용 상태·마지막 적용 시각은 ② 의 적용 카드에서 확인합니다.
      </p>
      <p className="subtitle" style={{ marginTop: 4 }}>
        정보 PUSH(시장 흐름·보유 종목·급등락)는 OCI 가 자동 발송하며 승인 대상이
        아닙니다. PUSH 발송 여부는 <strong>Telegram</strong> 에서 확인합니다.
      </p>
    </header>
  );
}
