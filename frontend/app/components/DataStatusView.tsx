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
        시장 데이터 / SQLite / refresh 상태가 들어갈 자리입니다.
      </p>

      <div className="card placeholder-card">
        <h2>시장 데이터 상태 화면 예정</h2>
        <p>SQLite / FDR refresh 상태가 이 화면에 연결될 예정입니다.</p>
        <ul className="helper">
          <li>SQLite market_data 상태가 표시될 자리</li>
          <li>market topn artifact 상태가 표시될 자리</li>
          <li>마지막 갱신 시간 표시 예정 영역</li>
          <li>수집 성공 / 실패 수 표시 예정 영역</li>
        </ul>
      </div>

      <div className="card placeholder-card placeholder-detail-area">
        <div className="helper">
          (다음 단계에서 실제 SQLite / refresh log 데이터가 연결될 영역.
          본 단계에서는 신규 API / 직접 조회 / refresh 실행 버튼 모두 추가하지 않습니다.)
        </div>
      </div>
    </section>
  );
}
