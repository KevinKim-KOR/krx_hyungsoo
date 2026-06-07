"use client";

// POC2 ETF Exposure Data Unfolding 1차 (2026-06-06) — ML 시계열 준비 상태 카드.
//
// 책임 (지시문 §5.8 / AC-8):
// - ML 학습 / 위험 감지에 필요한 시계열 데이터 축 9개의 현재 준비 상태 표시.
// - 실제 학습 / threshold / factor / label 확정 X. "준비 상태"만.
// - 상태 5종: available / partial / not_collected / not_integrated / not_calculated.
// - 보수적으로 표기. 확신 없으면 not_integrated / not_collected.
//
// 본 카드는 외부 fetch 없음. 정적 상태 표 (현재 시점 시스템 인지 기준).

type ReadinessStatus =
  | "available"
  | "partial"
  | "not_collected"
  | "not_integrated"
  | "not_calculated";

interface ReadinessAxis {
  label: string;
  status: ReadinessStatus;
  note: string;
}

const AXES: ReadinessAxis[] = [
  {
    label: "ETF 가격 시계열",
    status: "available",
    note: "SQLite etf_daily_price 에 가격 시계열 저장",
  },
  {
    label: "ETF 구성종목 snapshot 시계열",
    status: "partial",
    note: "etf_constituents_snapshot 캐시 — 시점 누적 부족",
  },
  {
    label: "구성종목 가격 시계열",
    status: "not_integrated",
    note: "구성종목별 가격 source 미연동",
  },
  {
    label: "NAV / 괴리율 시계열",
    status: "partial",
    note: "Naver ETF universe 단면 스냅샷은 etf_nav_daily 에 적재(2026-06-08). 시계열 누적은 미적용",
  },
  {
    label: "거래량 / 유동성 시계열",
    status: "partial",
    note: "거래량은 etf_daily_price 에 일부 보유 — 유동성 지표 미계산",
  },
  {
    label: "시장지수 시계열",
    status: "partial",
    note: "KODEX200 / KOSPI 기준 시계열 일부 — 추가 벤치 마크 미연동",
  },
  {
    label: "시장 폭 지표",
    status: "not_collected",
    note: "advance/decline 등 시장 폭 지표 미적재",
  },
  {
    label: "외국인 / 기관 수급",
    status: "not_collected",
    note: "수급 데이터 source 미연동 / 미적재",
  },
  {
    label: "변동성 지표",
    status: "not_calculated",
    note: "원천 가격 시계열은 있으나 변동성 지표(IV/RV/MDD 등) 계산 로직 없음",
  },
];

const STATUS_LABEL: Record<ReadinessStatus, string> = {
  available: "available",
  partial: "partial",
  not_collected: "not_collected",
  not_integrated: "not_integrated",
  not_calculated: "not_calculated",
};

const STATUS_CLASS: Record<ReadinessStatus, string> = {
  available: "ml-readiness-badge ml-readiness-available",
  partial: "ml-readiness-badge ml-readiness-partial",
  not_collected: "ml-readiness-badge ml-readiness-missing",
  not_integrated: "ml-readiness-badge ml-readiness-missing",
  not_calculated: "ml-readiness-badge ml-readiness-missing",
};

export default function MLTimeseriesReadinessCard() {
  return (
    <div className="card">
      <h2>ML / 위험 감지 시계열 준비 상태</h2>
      <p className="helper" style={{ marginBottom: 8 }}>
        본 STEP에서 ML / 위험 감지 모델은 만들지 않습니다. 학습에 필요한 시계열
        데이터의 현재 시스템 준비 상태만 보수적으로 표시합니다. 위험 감지는
        &lsquo;하락 예측&rsquo;이 아니라 &lsquo;위험 구간 분류&rsquo;로 정의합니다 (factor /
        threshold / label 미확정).
      </p>
      <table className="market-topn-table">
        <thead>
          <tr>
            <th>시계열 축</th>
            <th style={{ width: 140 }}>상태</th>
            <th>사유 / 현재 source</th>
          </tr>
        </thead>
        <tbody>
          {AXES.map((axis) => (
            <tr key={axis.label}>
              <td>{axis.label}</td>
              <td>
                <span className={STATUS_CLASS[axis.status]}>
                  {STATUS_LABEL[axis.status]}
                </span>
              </td>
              <td style={{ color: "var(--muted)" }}>{axis.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p
        className="helper"
        style={{ marginTop: 8, fontSize: "0.78rem" }}
      >
        상태 의미 — available: 시계열로 사용 가능 / partial: 일부 기간·종목만 /
        not_collected: 미적재 / not_integrated: source 미연동 / not_calculated:
        원천은 있으나 지표 계산 로직 없음.
      </p>
    </div>
  );
}
