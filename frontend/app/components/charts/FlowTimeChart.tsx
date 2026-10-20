"use client";
// POC6-01 — 날짜(달력) 가로축 차트. 자료마다 거래일 달력이 달라(한국 · 런던 · 뉴욕) 저장일 순서가 아니라
// 실제 날짜 위치에 그린다(보간 · 날짜 이동 없음). 여러 선 + 범례 · 0 기준선(누적 수급) · 큰 변화 표시 점.
// 고른 날(selected)은 부모가 정한다 — 네 차트가 같은 날을 함께 가리킨다. 마우스 · 터치는 위치 → 날짜를
// 부모에게 넘기고(부모가 실제 있는 날로 맞춤), 키보드 좌우는 부모의 onStep 으로.
import type { KeyboardEvent, PointerEvent } from "react";

import { valueAxis } from "@/lib/chartScale";
import type { FlowPoint } from "@/lib/api/marketFlow";

const VW = 1000;
const DAY = 86_400_000;

export interface FlowLine {
  key: string;
  label: string;
  color: string;
  points: FlowPoint[];
}

const t = (d: string) => Date.parse(`${d}T00:00:00Z`);
const md = (d: string) => `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}`;

export function valueAt(points: FlowPoint[], date: string): FlowPoint | null {
  let hit: FlowPoint | null = null;
  for (const p of points) {
    if (p[0] > date) break;
    hit = p;
  }
  return hit;
}

export default function FlowTimeChart({
  title,
  domain,
  lines,
  fmt,
  zeroLine = false,
  marks = [],
  selected,
  onPick,
  onStep,
  height = 120,
  testId,
}: {
  title: string;
  domain: [string, string];
  lines: FlowLine[];
  fmt: (v: number) => string;
  zeroLine?: boolean;
  marks?: { date: string; key: string }[];
  selected: string;
  onPick?: (isoDate: string) => void;
  onStep?: (delta: -1 | 1) => void;
  height?: number;
  testId?: string;
}) {
  const t0 = t(domain[0]);
  const t1 = Math.max(t(domain[1]), t0 + DAY);
  const x = (d: string) => ((t(d) - t0) / (t1 - t0)) * VW;
  const vals = lines.flatMap((l) => l.points.map((p) => p[1]));
  if (vals.length === 0) {
    return (
      <div className="mf-chart" data-testid={testId}>
        <div className="mf-chart-head">
          <span className="mf-chart-title">{title}</span>
        </div>
        <p className="tc-muted tc-small">이 기간에 저장된 값이 없습니다.</p>
      </div>
    );
  }
  const axis = valueAxis(zeroLine ? [...vals, 0] : vals, { target: 3 });
  const y = (v: number) => (1 - (v - axis.lo) / (axis.hi - axis.lo)) * 100;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => new Date(t0 + f * (t1 - t0)).toISOString().slice(0, 10));
  const pick = (e: PointerEvent<HTMLDivElement>) => {
    if (!onPick) return;
    const r = e.currentTarget.getBoundingClientRect();
    if (r.width <= 0) return;
    const f = Math.min(Math.max((e.clientX - r.left) / r.width, 0), 1);
    onPick(new Date(t0 + f * (t1 - t0)).toISOString().slice(0, 10));
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!onStep) return;
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      onStep(e.key === "ArrowLeft" ? -1 : 1);
    }
  };
  return (
    <div className="mf-chart" data-testid={testId}>
      <div className="mf-chart-head">
        <span className="mf-chart-title">{title}</span>
        {lines.length > 1 ? (
          <span className="mf-legend">
            {lines.map((l) => (
              <span key={l.key}>
                <i style={{ background: l.color }} />
                {l.label}
              </span>
            ))}
          </span>
        ) : null}
      </div>
      <div className="rc">
        <div className="rc-body" style={{ height }}>
          <div className="rc-y" aria-hidden="true">
            {axis.ticks.map((v) => (
              <span key={v} style={{ top: `${y(v)}%` }}>
                {fmt(v)}
              </span>
            ))}
          </div>
          <div
            className="rc-plot"
            role="group"
            tabIndex={0}
            aria-label={`${title} · ${domain[0]} ~ ${domain[1]} · 좌우 화살표로 날짜 고르기`}
            onPointerDown={pick}
            onPointerMove={pick}
            onKeyDown={onKey}
          >
            <svg viewBox={`0 0 ${VW} 100`} preserveAspectRatio="none" width="100%" height="100%" aria-hidden="true">
              {axis.ticks.map((v) => (
                <line
                  key={v}
                  x1={0}
                  x2={VW}
                  y1={y(v)}
                  y2={y(v)}
                  className={zeroLine && v === 0 ? "mf-zero" : "rc-grid"}
                  vectorEffect="non-scaling-stroke"
                />
              ))}
              {lines.map((l) => (
                <path
                  key={l.key}
                  d={l.points.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(2)},${y(p[1]).toFixed(3)}`).join(" ")}
                  className="rc-line"
                  stroke={l.color}
                  vectorEffect="non-scaling-stroke"
                  data-testid={testId ? `${testId}-line-${l.key}` : undefined}
                />
              ))}
              <line x1={x(selected)} x2={x(selected)} y1={0} y2={100} className="rc-guide" vectorEffect="non-scaling-stroke" />
            </svg>
            {marks.map((m) => {
              const line = lines.find((l) => l.key === m.key);
              const p = line?.points.find((q) => q[0] === m.date);
              if (!line || !p) return null;
              return (
                <span
                  key={`${m.key}-${m.date}`}
                  className="mf-mark"
                  title={`${md(p[0])} ${line.label} ${fmt(p[1])}`}
                  data-testid={testId ? `${testId}-mark-${m.key}-${m.date}` : undefined}
                  style={{ left: `${(x(p[0]) / VW) * 100}%`, top: `${y(p[1])}%`, borderColor: line.color }}
                />
              );
            })}
            {lines.map((l) => {
              const p = valueAt(l.points, selected);
              return p ? (
                <span key={l.key} className="rc-dot" style={{ left: `${(x(p[0]) / VW) * 100}%`, top: `${y(p[1])}%`, background: l.color }} />
              ) : null;
            })}
          </div>
        </div>
        <div className="rc-x" aria-hidden="true">
          {ticks.map((d, k) => (
            <span
              key={`${d}-${k}`}
              className={k === 0 ? "rc-x-first" : k === ticks.length - 1 ? "rc-x-last" : k % 2 ? "mf-x-odd" : undefined}
              style={{ left: `${k * 25}%` }}
            >
              {k === 0 ? d : md(d)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
