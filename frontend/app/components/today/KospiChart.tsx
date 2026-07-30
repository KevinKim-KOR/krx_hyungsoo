"use client";

// POC3-01 오늘의 투자 점검 — 코스피 가격 흐름 차트 (설계서 §4.1).
//
// 저장된 KOSPI close 시계열(market_benchmark_daily_price)만 SVG 선으로 그린다.
// - NO_DATA/UNAVAILABLE 은 빈 정상 차트로 위장하지 않고 사유 표시.
// - BUY/SELL 마커·예측선·목표가 없음. 거래량은 미저장이라 이 차트에 없음(§4.1 Q5).
// - 최상단 대표 정보 — 장식 배경이 아니라 흐름을 읽을 수 있는 크기(§4.1 차트 구성).

import { useSharedQuery } from "@/lib/api/queryCache";
import { fetchBenchmarkSeries, type PriceSeriesResponse } from "@/lib/api";

export const KOSPI_SERIES_KEY = "today:price-series?benchmark=KOSPI";

// 최근 N 거래일만 표시 (전체 12년 시계열은 대표 차트에서 흐름 판독을 흐린다).
const RECENT_DAYS = 120;

export default function KospiChart() {
  const q = useSharedQuery<PriceSeriesResponse>(KOSPI_SERIES_KEY, () =>
    fetchBenchmarkSeries("KOSPI"),
  );

  if (q.phase === "loading") {
    return <p className="tc-muted tc-small">코스피 가격 흐름 불러오는 중...</p>;
  }
  if (q.phase === "error") {
    return <p className="tc-danger tc-small">코스피 가격 흐름 확인 불가 (조회 실패)</p>;
  }
  if (q.phase === "idle") {
    return null;
  }

  const data = q.data;
  if (data.availability !== "AVAILABLE" || data.series.length === 0) {
    const label =
      data.availability === "NO_DATA"
        ? "저장된 코스피 가격 자료 없음"
        : "코스피 가격 확인 불가";
    return (
      <div className="tc-small">
        <span className="tc-warn" style={{ fontWeight: 600 }}>
          {label}
        </span>
      </div>
    );
  }

  const recent = data.series.slice(-RECENT_DAYS);
  const first = recent[0];
  const last = recent[recent.length - 1];

  return (
    <div>
      <SvgLine points={recent} stale={q.stale} />
      <div className="tc-small tc-muted" style={{ marginTop: 6 }}>
        코스피 {first.date} ~ {last.date} · 최근 {recent.length}거래일 · 최종{" "}
        {last.price.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}
        {q.stale && <span className="tc-warn"> · ⚠ 이전 조회값 (재조회 실패)</span>}
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
  const W = 900;
  const H = 220;
  const pad = 10;
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
      aria-label="코스피 일별 가격 흐름"
      style={{ overflow: "visible" }}
    >
      <path
        d={d}
        fill="none"
        stroke={stale ? "var(--warn)" : "var(--accent)"}
        strokeWidth={1.75}
      />
    </svg>
  );
}
