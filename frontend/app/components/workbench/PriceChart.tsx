"use client";

// POC3-02 — 선택 종목 가격 시계열 차트 (§5.8·§6·§8·§10).
// 기존 SQLite 저장 가격만 SVG 선으로. NO_DATA/UNAVAILABLE 은 빈 정상 차트로
// 그리지 않고 사유 표시. BUY/SELL 마커·예측선·목표가 없음.
// POC5-19 개정(차트 읽기 · 2026-10-17): 날짜 · 원 눈금 · 가로선 · 고른 날의 종가 줄(공통 틀 · 「확인 근거」 ·
// 「ETF 비교하기」 같은 차트). 종목을 바꾸면 고른 날은 그 종목의 최근 저장일로 다시 시작(key).

import { useSharedQuery } from "@/lib/api/queryCache";
import { fetchPriceSeries, type PriceSeriesResponse } from "@/lib/api";
import ReadableLineChart from "../charts/ReadableLineChart";

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
      <ReadableLineChart
        key={ticker}
        points={data.series}
        unit="원"
        valueLabel="종가"
        label="선택 종목 일별 가격 시계열"
        warn={q.stale}
        testId="price-chart"
      />
      <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
        제공 기간 {data.available_from} ~ {data.available_to} · {data.series.length}개 저장일
        {q.stale && (
          <span style={{ color: "var(--warn)" }}> · ⚠ 이전 조회값 (재조회 실패)</span>
        )}
      </div>
    </div>
  );
}
