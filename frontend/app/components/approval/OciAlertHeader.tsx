"use client";

// OCI 적용·알림 — 화면 상단 역할 안내 (A구간).
//
// 설계 정정: 이 화면의 두 역할을 먼저 구분해 보여준다.
//  1) OCI 운영 기준 적용 — 사용자가 [적용] 버튼으로 실행 (아래 OCI 적용 카드).
//  2) 정보 PUSH — OCI 가 자동 발송, 메시지별 승인 없음 (아래 정보 PUSH 운영 기준).
// 투자 판단 초안 영역·승인 대기 표현은 만들지 않는다(현재 계약에 식별 필드 없음, Q1-c).
// 실측 상태(정상/운영 중/최근 성공)는 여기서 표시하지 않는다 — OCI 적용 상태는 아래
// OCI 적용 카드가 실제 조회값으로 표시한다(Q4).

export default function OciAlertHeader() {
  return (
    <header className="oci-alert-header">
      <h1 id="approval-h">OCI 적용·알림</h1>
      <p className="subtitle">
        PC 에서 확정한 운영 기준을 OCI 에 적용하고, 자동 정보 알림의 운영
        방식을 역할별로 확인합니다. 정보 PUSH 는 메시지마다 승인하지 않습니다.
      </p>
      <div className="oci-role-summary">
        <div className="oci-role-item">
          <div className="oci-role-label">OCI 운영 기준 적용</div>
          <div className="oci-role-desc">
            PC 에서 확정한 운영 PARAM 을 사용자가 <strong>[적용]</strong> 버튼으로
            OCI 에 반영합니다. 적용 상태·마지막 적용 시각은 아래 OCI 적용 카드에서
            확인합니다.
          </div>
        </div>
        <div className="oci-role-item">
          <div className="oci-role-label">정보 PUSH</div>
          <div className="oci-role-desc">
            시장 흐름·보유 종목·급등락 알림을 OCI 가{" "}
            <strong>자동 발송</strong>합니다. 메시지별 승인이 없으며, 아래는
            실행 상태가 아니라 운영 기준 안내입니다.
          </div>
        </div>
      </div>
    </header>
  );
}
