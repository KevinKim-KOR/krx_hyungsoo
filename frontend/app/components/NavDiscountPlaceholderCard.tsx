"use client";

// POC2 ETF Exposure Data Unfolding 1차 (2026-06-06) — NAV/괴리율 빈자리 카드.
//
// 책임 (지시문 §5.7 / AC-7):
// - NAV / 괴리율은 source 미연동 상태로 표시. 친구 화면(Holdings Evidence)과
//   동일한 unavailable 노출 정책. 본 STEP에서 source 진단 / 신규 fetcher 추가 X.

export default function NavDiscountPlaceholderCard() {
  return (
    <div className="card">
      <h2>NAV / 괴리율 상태</h2>
      <div className="nav-unavailable-note" style={{ display: "block" }}>
        NAV / 괴리율: <strong>unavailable</strong>
        <br />
        사유: source 미연동
        <br />
        다음 단계에서 source 진단 필요 (본 STEP에서 진단·신규 fetcher 도입 X).
      </div>
    </div>
  );
}
