// POC5-19 — 근거 묶음의 짧은 표시(받은 근거 응답 · 기존 문구만 · 새 계산 없음).
// POC6-33(판정 Q34 · PLAN E4) — 세부 흐름 창 첫 줄(세 근거 기준일 + 핵심 값)은 펼친 상세의 세 묶음과 같은 내용이라
// 창에서 뺐다(창 = 차트 · 고른 날 수치 · 날짜 범위). 그 줄을 만들던 함수도 함께 뺐다.
import type { PriceBasis } from "@/lib/api";
import { declineDetailText } from "./declineSummary";
import type { RiskEvidenceRow } from "./helpers";

export function pct(v: number | null): string {
  return v === null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}
export function pctp(v: number | null): string {
  return v === null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%p`;
}

// 하락 구간 짧은 값: 구간 이름 / '해당 없음' / 판정하지 않는 사유(기존 문장).
export function bandShortText(row: RiskEvidenceRow, basis: PriceBasis | null): string {
  const band = row.decline_band;
  if (!band?.judgeable) return declineDetailText(row, basis);
  return band.state ? (band.label ?? "") : "해당 없음";
}
