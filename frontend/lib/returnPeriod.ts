// POC5-21 — 후보 수익률의 실제 계산 기간(사용한 시작 · 끝 종가의 저장 날짜).
//
// 날짜는 응답의 price_start_date / price_end_date(그 종목 행에서 백엔드가 고른 날짜)만 쓴다.
// basis_end_date(시장 저장 최신일)나 화면 기준일로 대신 채우지 않는다 — 없으면 '확인 불가'.
// 공통 안내는 값이 있는 표시 후보의 날짜가 모두 확인되고 모두 같을 때만 '모두 같음'(설계자 판정 Q3).
// 끝일 표시는 시장 저장 최신일과 비교한다(다수가 쓰는 날짜를 기준으로 삼지 않는다).
import type { MarketCandidate, MarketContextKodex200, MarketPeriodReturn } from "./api";

export type PeriodKey =
  | "daily"
  | "one_month"
  | "three_month"
  | "six_month"
  | "twelve_month"
  | "three_year";

export const PERIOD_KEYS: PeriodKey[] = [
  "daily",
  "one_month",
  "three_month",
  "six_month",
  "twelve_month",
  "three_year",
];

export const PERIOD_LABEL: Record<PeriodKey, string> = {
  daily: "일간",
  one_month: "1개월",
  three_month: "3개월",
  six_month: "6개월",
  twelve_month: "12개월",
  three_year: "3년",
};

export type ValuePeriod =
  | { kind: "none" } // 수익률 없음 — 기존 '-' 표시 그대로
  | { kind: "unknown" } // 수익률은 있으나 사용 종가 날짜가 응답에 없음
  | { kind: "dated"; start: string; end: string };

export function valuePeriod(r: MarketPeriodReturn | null | undefined): ValuePeriod {
  if (r?.return_pct === null || r?.return_pct === undefined) return { kind: "none" };
  const s = r.price_start_date;
  const e = r.price_end_date;
  if (!s || !e) return { kind: "unknown" };
  return { kind: "dated", start: s, end: e };
}

export interface PeriodGroup {
  total: number; // 수익률이 있는 표시 후보 수(날짜 확인 불가 포함)
  dated: number;
  unknown: number;
  starts: string[]; // 서로 다른 시작일(오름차순)
  ends: string[]; // 서로 다른 끝일(오름차순)
}

export function periodGroup(candidates: MarketCandidate[], key: PeriodKey): PeriodGroup {
  const starts = new Set<string>();
  const ends = new Set<string>();
  let total = 0;
  let unknown = 0;
  for (const c of candidates) {
    const vp = valuePeriod(c.returns?.[key]);
    if (vp.kind === "none") continue;
    total += 1;
    if (vp.kind === "unknown") {
      unknown += 1;
      continue;
    }
    starts.add(vp.start);
    ends.add(vp.end);
  }
  return {
    total,
    dated: total - unknown,
    unknown,
    starts: [...starts].sort(),
    ends: [...ends].sort(),
  };
}

export function fmtRange(start: string, end: string): string {
  return `${start} → ${end}`;
}

// 후보 목록 위 한 줄(선택 기간).
export function groupLine(g: PeriodGroup): string {
  if (g.total === 0) return "표시할 값이 없습니다";
  if (g.unknown === g.total) return "확인 불가 — 응답에 사용 종가 날짜가 없습니다";
  if (g.starts.length === 1 && g.ends.length === 1) {
    const range = `${fmtRange(g.starts[0], g.ends[0])} 종가`;
    return g.unknown === 0
      ? `${range} · 표시 후보 ${g.total}개 모두 같음`
      : `${range} · 날짜 확인된 ${g.dated}개 같음 · ${g.unknown}개 계산 기간 확인 불가`;
  }
  const parts = ["종목별 계산 기간 다름"];
  parts.push(g.starts.length === 1 ? `시작 ${g.starts[0]} 공통` : "시작일은 각 값 아래");
  parts.push(
    g.ends.length === 1 ? `끝 ${g.ends[0]} 공통` : "끝일이 시장 저장 최신일과 다른 후보는 이름 옆",
  );
  if (g.unknown > 0) parts.push(`${g.unknown}개 계산 기간 확인 불가`);
  return parts.join(" · ");
}

// ? 안의 기간별 한 줄.
export function groupSummary(g: PeriodGroup): string {
  if (g.total === 0) return "값 없음";
  if (g.unknown === g.total) return "확인 불가";
  const tail = g.unknown > 0 ? ` · ${g.unknown}개 확인 불가` : "";
  if (g.starts.length === 1 && g.ends.length === 1) {
    const n = g.unknown > 0 ? `날짜 확인된 ${g.dated}개` : `${g.total}개 모두`;
    return `${fmtRange(g.starts[0], g.ends[0])} (${n}${tail})`;
  }
  const span = (xs: string[]) => (xs.length === 1 ? xs[0] : `${xs[0]} ~ ${xs[xs.length - 1]}`);
  return `종목별 다름 — 시작 ${span(g.starts)} · 끝 ${span(g.ends)}${tail}`;
}

export function allPeriodsUnknown(c: MarketCandidate): boolean {
  const vps = PERIOD_KEYS.map((k) => valuePeriod(c.returns?.[k])).filter((v) => v.kind !== "none");
  return vps.length > 0 && vps.every((v) => v.kind === "unknown");
}

// 값 아래 짧은 표시 — 시작일이 여러 종류인 기간은 모든 값에 실제 시작일(기준 삼는 다수 없음).
export function valueNote(vp: ValuePeriod, g: PeriodGroup, candidateAllUnknown: boolean): string | null {
  if (vp.kind === "none") return null;
  if (vp.kind === "unknown") return candidateAllUnknown ? null : "기간 확인 불가";
  return g.starts.length > 1 ? `시작 ${vp.start}` : null;
}

export const UNKNOWN_BADGE = "계산 기간 확인 불가";

// 이름 옆 표시 — 날짜가 하나도 없으면 '확인 불가'(선택 기간 전부 확인 불가면 위 한 줄이 말한다),
// 끝일이 시장 저장 최신일과 다르면 '수익률 끝일'.
export function candidateBadges(
  c: MarketCandidate,
  selected: PeriodKey,
  selectedGroup: PeriodGroup,
  marketAsof: string | null | undefined,
): string[] {
  if (allPeriodsUnknown(c)) {
    return selectedGroup.unknown === selectedGroup.total ? [] : [UNKNOWN_BADGE];
  }
  const sel = valuePeriod(c.returns?.[selected]);
  const any =
    sel.kind === "dated"
      ? sel
      : PERIOD_KEYS.map((k) => valuePeriod(c.returns?.[k])).find((v) => v.kind === "dated");
  if (!any || any.kind !== "dated" || !marketAsof) return [];
  return any.end !== marketAsof ? [`수익률 끝일 ${any.end}`] : [];
}

// ── KODEX200 대비 수익률 차이(후보 수익률 − KODEX200 수익률 · %p) ─────────────
export type CmpKey = "1m" | "3m";
export type CmpState = "none" | "unknown" | "same" | "diff";

const CMP_PERIOD: Record<CmpKey, PeriodKey> = { "1m": "one_month", "3m": "three_month" };

export function kodexRange(
  k: MarketContextKodex200 | null | undefined,
  key: CmpKey,
): { start: string; end: string } | null {
  if (!k || k.status !== "ok") return null;
  const start = key === "1m" ? k.return_1m_start_date : k.return_3m_start_date;
  const end = k.return_end_date;
  return start && end ? { start, end } : null;
}

export function cmpState(
  c: MarketCandidate,
  key: CmpKey,
  kodex: MarketContextKodex200 | null | undefined,
): CmpState {
  const v = key === "1m" ? c.excess_return?.vs_kodex200_1m_pctp : c.excess_return?.vs_kodex200_3m_pctp;
  if (v === null || v === undefined) return "none";
  const cand = valuePeriod(c.returns?.[CMP_PERIOD[key]]);
  const kd = kodexRange(kodex, key);
  if (cand.kind !== "dated" || !kd) return "unknown";
  return cand.start === kd.start && cand.end === kd.end ? "same" : "diff";
}

export interface CmpGroup {
  total: number;
  same: number;
  diff: number;
  unknown: number;
}

export function cmpGroup(
  candidates: MarketCandidate[],
  key: CmpKey,
  kodex: MarketContextKodex200 | null | undefined,
): CmpGroup {
  const g = { total: 0, same: 0, diff: 0, unknown: 0 };
  for (const c of candidates) {
    const s = cmpState(c, key, kodex);
    if (s === "none") continue;
    g.total += 1;
    g[s] += 1;
  }
  return g;
}

export function cmpLabel(g: CmpGroup): string {
  if (g.total === 0) return "값 없음";
  if (g.same + g.diff === 0) return "기간 확인 불가";
  let label: string;
  if (g.same === 0) label = "기간 다른 수익률 차이";
  else if (g.diff === 0) label = "같은 기간 수익률 차이";
  else label = "후보별로 다름 — 값 아래 표시";
  return g.unknown > 0 ? `${label} · ${g.unknown}개 기간 확인 불가` : label;
}

export function cmpNote(s: CmpState, g: CmpGroup): string | null {
  if (s === "none") return null;
  if (s === "unknown") return g.same + g.diff === 0 ? null : "기간 확인 불가";
  if (g.same > 0 && g.diff > 0) return s === "diff" ? "기간 다름" : "같은 기간";
  return null;
}
