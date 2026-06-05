"use client";

// POC2 PC UI Shell 1차 — Data Status view (placeholder).
//
// 본 단계 정책 (지시문 §3.6):
// - 화면 자리만 마련.
// - SQLite 직접 조회 / 신규 API / refresh 실행 버튼 / 데이터 수집 실행 모두 금지.
// - 다음 단계에서 SQLite + market refresh 상태가 연결될 영역.

export default function DataStatusView() {
  return (
    <section aria-labelledby="data-status-h">
      <h1 id="data-status-h">Data Status</h1>
      <p className="subtitle">
        시장 데이터 / SQLite / refresh 상태 모니터링 화면 (준비 중).
      </p>
      <div className="role-banner">
        <strong>[보조 화면 — 준비 중]</strong> 시장 데이터 수집 상태, SQLite 최종 갱신 시간,
        수집 성공/실패 수 등이 이 화면에 표시될 예정입니다. 현재는 Market Discovery 화면의
        &lsquo;최신 시장 데이터 갱신&rsquo; 버튼과 요약 정보에서 상태를 확인할 수 있습니다.
      </div>

      <div className="card placeholder-card">
        <h2>시장 데이터 수집 상태 (예정)</h2>
        <ul className="helper">
          <li>SQLite market_data 기준일 / 수집 성공·실패 수</li>
          <li>market refresh log 마지막 갱신 시간</li>
          <li>ETF Master 수록 종목 수 / 가격 시계열 기간</li>
        </ul>
        <p style={{ marginTop: 8 }}>
          현재 시장 데이터 상태는{" "}
          <strong>Market Discovery 화면</strong>의 요약 및 갱신 섹션에서 확인할 수 있습니다.
        </p>
      </div>

      <div className="card placeholder-card placeholder-detail-area">
        <div className="helper">
          다음 단계에서 실제 SQLite / refresh log 데이터가 연결됩니다.
          현재는 신규 API / 직접 조회 / refresh 실행 버튼이 없습니다.
        </div>
      </div>
    </section>
  );
}
