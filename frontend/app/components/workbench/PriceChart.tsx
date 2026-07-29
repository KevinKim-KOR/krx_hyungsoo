"use client";

// POC3-02 — 선택 종목 가격 시계열 차트 (§5.8·§6·§8·§10).
// 기존 SQLite 저장 가격만 SVG 선으로. NO_DATA/UNAVAILABLE 은 빈 정상 차트로
// 그리지 않고 사유 표시. BUY/SELL 마커·예측선·목표가 없음.

import { useSharedQuery } from "@/lib/api/queryCache";
import { fetchPriceSeries, type PriceSeriesResponse } from "@/lib/api";

// 선택 ticker 별 캐시 키 (동일 ticker 재선택·화면 왕복 시 재사용 · §9).
export function priceSeriesKey(ticker: string): string {
  return `workbench:price-series?ticker=${ticker}`;
}

export default function PriceChart({ ticker }: { ticker: string }) {
  const q = useSharedQuery<PriceSeriesResponse>(priceSeriesKey(ticker), () =>
    fetchPriceSeries(ticker),
  );

  if (q.phase === "loading") {
    return <p style={{ color: "var(--muted)", fontSize: 13 }}>가격 시계열 불러오는 중...</p>;
  }
  if (q.phase === "error") {
    return (
      <p style={{ color: "var(--danger)", fontSize: 13 }}>
        가격 시계열 확인 불가 (조회 실패)
      </p>
    );
  }
  if (q.phase === "idle") {
    return null;
  }

  const data = q.data;
  // NO_DATA / UNAVAILABLE 은 빈 정상 차트 아님 — 사유 표시 (§8·§10).
  if (data.availability !== "AVAILABLE" || data.series.length === 0) {
    const label =
      data.availability === "NO_DATA"
        ? "저장된 가격 데이터 없음"
        : "가격 확인 불가";
    return (
      <div style={{ fontSize: 13 }}>
        <span style={{ color: "var(--warn)", fontWeight: 600 }}>{label}</span>
        {data.reason && (
          <span style={{ color: "var(--muted)" }}> ({data.reason})</span>
        )}
      </div>
    );
  }

  return (
    <div>
      <SvgLine points={data.series} stale={q.stale} />
      <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
        제공 기간 {data.available_from} ~ {data.available_to} · {data.series.length}일
        {q.stale && (
          <span style={{ color: "var(--warn)" }}> · ⚠ 이전 조회값 (재조회 실패)</span>
        )}
      </div>
    </div>
  );
}

function SvgLine({
  points,
  stale,
}: {
  points: { date: string; price: number }[];
  stale: boolean;
}) {
  const W = 640;
  const H = 160;
  const pad = 8;
  const prices = points.map((p) => p.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = max - min || 1;
  const n = points.length;
  const x = (i: number) => pad + (i / Math.max(n - 1, 1)) * (W - 2 * pad);
  const y = (v: number) => H - pad - ((v - min) / span) * (H - 2 * pad);
  const d = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.price).toFixed(1)}`)
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      height={H}
      role="img"
      aria-label="선택 종목 일별 가격 시계열"
      style={{ overflow: "visible" }}
    >
      <path
        d={d}
        fill="none"
        stroke={stale ? "var(--warn)" : "var(--accent)"}
        strokeWidth={1.5}
      />
    </svg>
  );
}
