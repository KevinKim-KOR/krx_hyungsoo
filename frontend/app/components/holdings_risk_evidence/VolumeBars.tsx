"use client";
// POC5-19 — 최근 저장일 거래량 막대(공통 차트 틀 · 0 에서 시작 · 주 눈금 · 옅은 가로선 · 중립 회색).
// 고른 날짜는 부모(세부 흐름 창)가 가격 선과 함께 정한다(개정 2026-10-17 §4).
// 값 없는 날은 점선 빈칸(0 으로 채우지 않음) · 저장된 0 은 바닥선 · 자료 0개는 기존 '거래량 자료 없음'.
import type { VolumeTrendEvidence } from "@/lib/api";
import { NO_VOLUME_TEXT } from "@/lib/storedVolume";
import SeriesChart from "../charts/SeriesChart";

export default function VolumeBars({
  ev,
  selected,
  onSelect,
  label,
  height = 120,
}: {
  ev: VolumeTrendEvidence;
  selected: number;
  onSelect: (i: number) => void;
  label: string;
  height?: number;
}) {
  if (ev.points.length === 0) return <p className="helper">{NO_VOLUME_TEXT}</p>;
  return (
    <SeriesChart
      dates={ev.points.map((p) => p.date)}
      values={ev.points.map((p) => p.volume)}
      kind="bar"
      unit="주"
      selected={selected}
      onSelect={onSelect}
      label={label}
      height={height}
      testId="volume-bars"
    />
  );
}
