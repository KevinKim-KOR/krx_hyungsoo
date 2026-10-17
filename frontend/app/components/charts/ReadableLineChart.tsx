"use client";
// POC5-19 개정(차트 읽기 · 2026-10-17) — 한 줄 가격 차트(KOSPI · 종목 가격) = 선택값 줄 + 공통 틀.
// 선택값 줄은 차트 바로 위 고정 자리(툴팁에 기대지 않음). 처음엔 가장 최근 저장일.
import { useState } from "react";
import { fmtValue, type ChartUnit } from "@/lib/chartScale";
import SeriesChart from "./SeriesChart";

export default function ReadableLineChart({
  points,
  unit,
  valueLabel,
  label,
  height,
  warn,
  testId,
}: {
  points: { date: string; price: number }[];
  unit: ChartUnit;
  valueLabel: string;
  label: string;
  height?: number;
  warn?: boolean;
  testId?: string;
}) {
  const n = points.length;
  const [sel, setSel] = useState<number | null>(null);
  const cur = Math.min(Math.max(sel ?? n - 1, 0), n - 1);
  const p = points[cur];
  return (
    <div>
      <div className="rc-readout" aria-live="polite" data-testid={testId ? `${testId}-readout` : undefined}>
        <span className="rc-readout-date">{p.date}</span> · {valueLabel}{" "}
        <b>{fmtValue(p.price, unit)}</b>
      </div>
      <SeriesChart
        dates={points.map((q) => q.date)}
        values={points.map((q) => q.price)}
        kind="line"
        unit={unit}
        selected={cur}
        onSelect={setSel}
        label={label}
        height={height}
        warn={warn}
        testId={testId}
      />
    </div>
  );
}
