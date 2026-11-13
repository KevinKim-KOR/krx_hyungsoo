"use client";
// POC5-22 — 동일 기간 KODEX200 대비 한 칸(「요즘 잘 오르는 ETF」 · 「ETF 비교하기」 공통).
// 값은 기존 상승 · 하락 색. 계산 불가 · 값 없음은 회색 짧은 글(시장 대비 열위 · 위험 표시 아님).
import { sameShort, type SameView } from "@/lib/samePeriodKodex";

export default function SamePeriodValue({
  view,
  colorOf,
  className = "v",
  absentText,
}: {
  view: SameView;
  colorOf: (v: number) => string;
  className?: string;
  absentText?: string;
}) {
  if (view.kind === "ok") {
    return (
      <span className={className} style={{ color: colorOf(view.diff) }}>
        {sameShort(view)}
      </span>
    );
  }
  return <span className={`${className} sp-na`.trim()}>{sameShort(view, absentText)}</span>;
}
