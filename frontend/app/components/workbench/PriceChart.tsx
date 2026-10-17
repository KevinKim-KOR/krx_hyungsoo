"use client";

// POC3-02 — 선택 종목 가격 시계열 차트 (§5.8·§6·§8·§10).
// 기존 SQLite 저장 가격만 SVG 선으로. NO_DATA/UNAVAILABLE 은 빈 정상 차트로
// 그리지 않고 사유 표시. BUY/SELL 마커·예측선·목표가 없음.
// POC5-19 개정(차트 읽기 · 2026-10-17): 날짜 · 원 눈금 · 가로선 · 고른 날의 종가 줄(공통 틀 · 「확인 근거」 ·
// 「ETF 비교하기」 같은 차트). 종목을 바꾸면 고른 날은 그 종목의 최근 저장일로 다시 시작(key).
// POC5-UI-04: 기간 선택(3개월 기본 · 6개월 · 1년 · 전체). 받은 시계열은 그대로 두고 그릴 배열만 자른다
// (공유 조회 결과 · 세부 흐름 창의 날짜 대응 자료 보존 · 기간 버튼은 조회하지 않음). 종목을 바꾸면 3개월로 다시 시작.

import { useMemo, useState } from "react";
import { useSharedQuery } from "@/lib/api/queryCache";
import { fetchPriceSeries, type PricePoint, type PriceSeriesResponse } from "@/lib/api";
import {
  DEFAULT_PRICE_PERIOD,
  PRICE_PERIODS,
  periodWindow,
  type PricePeriod,
} from "@/lib/pricePeriod";
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

  return <PeriodPriceChart key={ticker} series={data.series} stale={q.stale} />;
}

function PeriodPriceChart({ series, stale }: { series: PricePoint[]; stale: boolean }) {
  const [period, setPeriod] = useState<PricePeriod>(DEFAULT_PRICE_PERIOD);
  const shown = useMemo(() => periodWindow(series, period), [series, period]);
  const first = shown[0];
  const last = shown[shown.length - 1];
  return (
    <div>
      <div className="holdings-sortbar price-period-bar">
        <span className="holdings-sortbar-label">기간</span>
        <div className="holdings-sort-seg" role="group" aria-label="가격 차트 기간">
          {PRICE_PERIODS.map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={period === key ? "on" : ""}
              aria-pressed={period === key}
              onClick={() => setPeriod(key)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {/* 기간을 바꾸면 고른 날은 그 창의 가장 최근 저장일로(key). */}
      <ReadableLineChart
        key={period}
        points={shown}
        unit="원"
        valueLabel="종가"
        label="선택 종목 일별 가격 시계열"
        warn={stale}
        testId="price-chart"
      />
      <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }} data-testid="price-chart-period">
        표시 기간 {first.date} ~ {last.date} · {shown.length}개 저장일
        {period === "ALL"
          ? ""
          : shown.length < series.length
            ? ` · 전체 저장 ${series[0].date} ~ ${series[series.length - 1].date} · ${series.length}개`
            : " · 저장된 자료 전체(선택한 기간보다 짧음)"}
        {stale && <span style={{ color: "var(--warn)" }}> · ⚠ 이전 조회값 (재조회 실패)</span>}
      </div>
    </div>
  );
}
