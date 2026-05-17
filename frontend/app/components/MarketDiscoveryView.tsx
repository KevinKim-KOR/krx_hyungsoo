"use client";

// POC2 PC UI Shell 1차 — Market Discovery view (placeholder).
//
// 본 단계 정책 (지시문 §3.3):
// - 화면 자리만 마련.
// - TOP N 상세표 / artifact 직접 파싱 / SQLite 조회 API / 필터·정렬·차트 모두 금지.
// - 다음 단계에서 FDR + SQLite 기반 ETF universe / 일간 / 1개월 / 3개월 TOP N 이 연결될 영역.

export default function MarketDiscoveryView() {
  return (
    <section aria-labelledby="market-discovery-h">
      <h1 id="market-discovery-h">Market Discovery</h1>
      <p className="subtitle">
        FDR + SQLite 기반 ETF universe / 일간 / 1개월 / 3개월 TOP N 화면이
        들어갈 자리입니다.
      </p>

      <div className="card placeholder-card">
        <h2>시장 ETF TOP N 화면 예정</h2>
        <p>
          SQLite 기반 ETF universe / 일간 / 1개월 / 3개월 TOP N 이 이 화면에
          연결될 예정입니다.
        </p>
        <p className="helper">
          본 단계에서는 화면 자리만 마련합니다. TOP N 상세표 / 필터 / 정렬 /
          차트는 다음 단계에서 구현 예정.
        </p>
      </div>

      <div className="card placeholder-card placeholder-detail-area">
        <div className="helper">
          (다음 단계에서 TOP N 상세표가 들어갈 영역)
        </div>
      </div>
    </section>
  );
}
