"use client";

// 승인·적용 — 화면 상단 역할 안내.
//
// 2026-08-05 POC3-07 §5.4·§7·§10.1 역할 축소:
//   이 화면의 실제 작업은 "PC 에서 확정한 운영 기준(PARAM·seed)의 OCI 적용" 하나다.
//   정보 PUSH(시장·보유·급등락)는 승인 대상이 아니고 OCI 가 자동 발송한다 — 여기서
//   카드로 다루지 않으며, 실행 결과는 진단·상태(및 첫 화면 요약)에서 확인한다.
//   투자 판단 초안 영역·승인 대기 표현·빈 자리표시자는 만들지 않는다(식별 필드 없음).

export default function OciAlertHeader() {
  return (
    <header className="oci-alert-header">
      <h1 id="approval-h">승인·적용</h1>
      <p className="subtitle">
        PC 에서 확정한 운영 기준(PARAM)을 사용자가 <strong>[적용]</strong> 버튼으로
        OCI 에 반영합니다. 적용 상태·마지막 적용 시각은 아래 적용 카드에서
        확인합니다.
      </p>
      <p className="subtitle" style={{ marginTop: 4 }}>
        정보 PUSH(시장 흐름·보유 종목·급등락)는 OCI 가 자동 발송하며 승인 대상이
        아닙니다. 발송 결과는 <strong>진단·상태</strong>에서 확인합니다.
      </p>
    </header>
  );
}
