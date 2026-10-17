"use client";
// POC5-19 개정(차트 읽기 · 2026-10-17) — KOSPI · 종목 가격 · 거래량 차트 공통 틀(라이브러리 없이 SVG).
// 가로 = 저장일 순서(달력의 연속 관측 아님) · 날짜 눈금 3~5개 · 세로 = 실제 값과 단위 · 눈금과 같은 옅은 가로선.
// 고르기: 마우스 이동 · 누르기 · 터치 끌기 · 키보드 좌우(Home · End). 선택은 세로 안내선 + 점(선) / 막대 강조.
// 결측(null)은 0 이나 앞 값으로 채우지 않는다 — 선은 그 자리에서 끊고, 막대는 점선 빈칸.
// 선택값 줄은 이 틀 밖(부모)에서 보인다 — 두 차트가 같은 날짜를 함께 가리킬 수 있게.
import type { KeyboardEvent, PointerEvent } from "react";
import {
  dateTickIndices,
  dateTickLabels,
  fmtTick,
  valueAxis,
  type ChartUnit,
} from "@/lib/chartScale";

const VW = 1000; // 가로 좌표(비율 고정 안 함 · 선 굵기는 화면 기준)

export default function SeriesChart({
  dates,
  values,
  kind,
  unit,
  selected,
  onSelect,
  label,
  height = 160,
  warn = false,
  testId,
}: {
  dates: string[];
  values: (number | null)[];
  kind: "line" | "bar";
  unit: ChartUnit;
  selected: number;
  onSelect: (i: number) => void;
  label: string;
  height?: number;
  warn?: boolean;
  testId?: string;
}) {
  const n = dates.length;
  if (n === 0) return null;
  const finite = values.filter((v): v is number => v !== null && Number.isFinite(v));
  const axis = valueAxis(finite, { zeroBase: kind === "bar", integer: unit !== "pt" });
  const y = (v: number) => (1 - (v - axis.lo) / (axis.hi - axis.lo)) * 100;
  const xc = (i: number) => ((i + 0.5) / n) * VW;
  const sel = Math.min(Math.max(selected, 0), n - 1);
  const ticks = dateTickIndices(n, n > 40 ? 5 : 4);
  const tickLabels = dateTickLabels(dates, ticks);

  // 마우스는 올리기만 해도 · 터치는 누르거나 끌면 그 날짜를 고른다(위 선택값 줄이 따라 바뀜).
  const pick = (e: PointerEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    if (r.width <= 0) return;
    const i = Math.floor(((e.clientX - r.left) / r.width) * n);
    if (!Number.isFinite(i)) return;
    onSelect(Math.min(Math.max(i, 0), n - 1));
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const next =
      e.key === "ArrowLeft"
        ? sel - 1
        : e.key === "ArrowRight"
          ? sel + 1
          : e.key === "Home"
            ? 0
            : e.key === "End"
              ? n - 1
              : null;
    if (next === null) return;
    e.preventDefault();
    onSelect(Math.min(Math.max(next, 0), n - 1));
  };

  // 선: null 에서 끊는다. 앞뒤가 비어 혼자 있는 점은 둥근 끝 점으로 보인다.
  const segs: string[] = [];
  let cur = "";
  values.forEach((v, i) => {
    if (v === null || !Number.isFinite(v)) {
      if (cur) segs.push(cur);
      cur = "";
      return;
    }
    const p = `${xc(i).toFixed(2)},${y(v).toFixed(3)}`;
    cur = cur ? `${cur} L${p}` : `M${p} L${p}`;
  });
  if (cur) segs.push(cur);

  const slot = VW / n;
  const bw = Math.max(slot * 0.62, 1);
  const selV = values[sel];

  return (
    <div className="rc" data-testid={testId}>
      <div className="rc-body" style={{ height }}>
        <div className="rc-y" aria-hidden="true">
          {axis.ticks.map((t) => (
            <span key={t} style={{ top: `${y(t)}%` }}>
              {fmtTick(t, unit)}
            </span>
          ))}
        </div>
        <div
          className="rc-plot"
          role="group"
          tabIndex={0}
          aria-label={`${label} · 좌우 화살표로 날짜 고르기`}
          onPointerDown={pick}
          onPointerMove={pick}
          onKeyDown={onKey}
          data-testid={testId ? `${testId}-plot` : undefined}
        >
          <svg viewBox={`0 0 ${VW} 100`} preserveAspectRatio="none" width="100%" height="100%" aria-hidden="true">
            {axis.ticks.map((t) => (
              <line
                key={t}
                x1={0}
                x2={VW}
                y1={y(t)}
                y2={y(t)}
                className={t === 0 && kind === "bar" ? "rc-base" : "rc-grid"}
                vectorEffect="non-scaling-stroke"
              />
            ))}
            {kind === "bar"
              ? values.map((v, i) =>
                  v === null || !Number.isFinite(v) ? (
                    <rect
                      key={dates[i]}
                      x={i * slot + (slot - bw) / 2}
                      y={88}
                      width={bw}
                      height={11}
                      className={i === sel ? "rc-missing rc-missing-sel" : "rc-missing"}
                      vectorEffect="non-scaling-stroke"
                      data-testid={testId ? `${testId}-missing-${i}` : undefined}
                    />
                  ) : (
                    <rect
                      key={dates[i]}
                      x={i * slot + (slot - bw) / 2}
                      y={Math.min(y(v), 99.4)}
                      width={bw}
                      height={Math.max(100 - y(v), 0.6)}
                      className={i === sel ? "rc-bar rc-bar-sel" : "rc-bar"}
                      data-testid={testId ? `${testId}-bar-${i}` : undefined}
                    />
                  ),
                )
              : segs.map((d, k) => (
                  <path
                    key={k}
                    d={d}
                    className="rc-line"
                    stroke={warn ? "var(--warn)" : "var(--accent)"}
                    vectorEffect="non-scaling-stroke"
                  />
                ))}
            <line x1={xc(sel)} x2={xc(sel)} y1={0} y2={100} className="rc-guide" vectorEffect="non-scaling-stroke" />
          </svg>
          {kind === "line" && selV !== null && Number.isFinite(selV) ? (
            <span
              className={warn ? "rc-dot rc-dot-warn" : "rc-dot"}
              style={{ left: `${(xc(sel) / VW) * 100}%`, top: `${y(selV)}%` }}
            />
          ) : null}
        </div>
      </div>
      <div className="rc-x" aria-hidden="true">
        {ticks.map((i, k) => (
          <span
            key={i}
            className={k === 0 ? "rc-x-first" : k === ticks.length - 1 ? "rc-x-last" : undefined}
            style={{ left: `${(xc(i) / VW) * 100}%` }}
          >
            {tickLabels[k]}
          </span>
        ))}
      </div>
    </div>
  );
}
