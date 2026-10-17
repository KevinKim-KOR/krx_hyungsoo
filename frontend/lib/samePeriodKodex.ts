// POC5-22 — 후보와 KODEX200 의 동일 기간 수익률 비교(「요즘 잘 오르는 ETF」 · 「ETF 비교하기」 · 복사문 · AI 자료 공통).
//
// 값은 응답의 `same_period_kodex200`(백엔드가 후보의 실제 시작 · 끝 날짜의 KODEX200 종가로 계산)만 쓴다.
// 필드가 없으면 '값 없음' — 기존 `excess_return`(기간 다른 차이) · 단기 20구간 값으로 대신하지 않는다.
// status=ok 는 필요한 날짜 · 유효 가격으로 산술 비교가 됐다는 뜻이다(가격 기준 연결 확인 아님 · 판정 Q1).
import type { MarketCandidate, SamePeriodKodex200 } from "./api";

export type SameKey = "1m" | "3m";

export type SameView =
  | { kind: "ok"; diff: number; cand: number; kodex: number; start: string; end: string }
  | { kind: "unavailable"; reason: string; start: string | null; end: string | null }
  | { kind: "absent" }; // 응답에 동일 기간 객체가 없음(이전 응답 · 상위 후보 밖 보유 종목)

// 도움말 · 복사문 공통 설명에 한 번 적는 한계(설계자 PLAN 판정 Q1 (a)).
export const SAME_PERIOD_LIMIT = "저장 종가로 계산하며 가격 조정 기준의 연속성은 검사하지 않습니다.";

const REASON_TEXT: Record<string, string> = {
  candidate_period_unknown: "후보 기간 확인 불가",
  kodex200_start_price_missing: "KODEX200 시작일 가격 없음",
  kodex200_end_price_missing: "KODEX200 끝일 가격 없음",
};

export function reasonText(reason: string | null | undefined): string {
  return (reason && REASON_TEXT[reason]) || "계산 불가";
}

// 후보 · 보유 근거 어느 쪽 객체든 같은 판정.
export function sameViewOf(sp: SamePeriodKodex200 | null | undefined, key: SameKey): SameView {
  if (!sp) return { kind: "absent" };
  const it = key === "1m" ? sp.one_month : sp.three_month;
  if (!it) return { kind: "absent" };
  if (
    it.status === "ok" &&
    it.diff_pctp != null &&
    it.candidate_return_pct != null &&
    it.kodex200_return_pct != null &&
    it.start_date &&
    it.end_date
  ) {
    return {
      kind: "ok",
      diff: it.diff_pctp,
      cand: it.candidate_return_pct,
      kodex: it.kodex200_return_pct,
      start: it.start_date,
      end: it.end_date,
    };
  }
  return {
    kind: "unavailable",
    reason: reasonText(it.reason),
    start: it.start_date ?? null,
    end: it.end_date ?? null,
  };
}

export function sameView(c: MarketCandidate | null | undefined, key: SameKey): SameView {
  return sameViewOf(c?.same_period_kodex200, key);
}

// 정렬 · 색에 쓰는 숫자(계산 불가 · 값 없음 = null).
export function sameDiffOf(sp: SamePeriodKodex200 | null | undefined, key: SameKey): number | null {
  const v = sameViewOf(sp, key);
  return v.kind === "ok" ? v.diff : null;
}

export function fmtSigned(v: number, unit: "%" | "%p"): string {
  return `${v > 0 ? "+" : ""}${v.toFixed(2)}${unit}`;
}

// 칸에 보일 짧은 글. 값 없음은 화면이 정한다(응답 전체에 없으면 위 줄이 한 번 알리고 칸은 '—').
export function sameShort(v: SameView, absentText = "—"): string {
  if (v.kind === "ok") return fmtSigned(v.diff, "%p");
  if (v.kind === "unavailable") return v.reason;
  return absentText;
}

// 양쪽 수익률 · 실제 기간 한 줄(상세 칸 · 복사문).
export function sameDetail(v: SameView): string {
  if (v.kind === "ok") {
    return `후보 ${fmtSigned(v.cand, "%")} · KODEX200 ${fmtSigned(v.kodex, "%")} · 사용 종가 ${v.start} → ${v.end}`;
  }
  if (v.kind === "unavailable") {
    return v.start && v.end ? `후보 기간 ${v.start} → ${v.end}` : "";
  }
  return "";
}

// 복사문 한 줄의 값 부분.
export function sameCopyText(v: SameView): string {
  if (v.kind === "ok") return `${sameShort(v)} (${sameDetail(v)})`;
  if (v.kind === "unavailable") {
    const d = sameDetail(v);
    return `계산 불가 — ${v.reason}${d ? ` (${d})` : ""}`;
  }
  return "동일 기간 값 없음";
}

// ? 안 — 같은 기간(시작 · 끝)끼리 묶어 KODEX200 수익률을 한 번씩.
export function sameGroups(candidates: MarketCandidate[], key: SameKey): string[] {
  const groups = new Map<string, { start: string; end: string; kodex: number; n: number }>();
  let unavailable = 0;
  let absent = 0;
  for (const c of candidates) {
    const v = sameView(c, key);
    if (v.kind === "ok") {
      const k = `${v.start}|${v.end}`;
      const g = groups.get(k) ?? { start: v.start, end: v.end, kodex: v.kodex, n: 0 };
      g.n += 1;
      groups.set(k, g);
    } else if (v.kind === "unavailable") unavailable += 1;
    else absent += 1;
  }
  const label = key === "1m" ? "1M" : "3M";
  const out = [...groups.values()]
    .sort((a, b) => b.n - a.n || a.start.localeCompare(b.start) || a.end.localeCompare(b.end))
    .map((g) => `· ${label} ${g.start} → ${g.end} (${g.n}개) · KODEX200 ${fmtSigned(g.kodex, "%")}`);
  if (unavailable) out.push(`· ${label} 계산 불가 ${unavailable}개(칸에 사유)`);
  if (absent) out.push(`· ${label} 동일 기간 값 없음 ${absent}개`);
  return out;
}

// 후보 목록 위 줄의 내용.
export function sameSummary(candidates: MarketCandidate[]): string {
  let unavailable = 0;
  let absent = 0;
  for (const c of candidates)
    for (const k of ["1m", "3m"] as SameKey[]) {
      const v = sameView(c, k);
      if (v.kind === "unavailable") unavailable += 1;
      if (v.kind === "absent") absent += 1;
    }
  if (candidates.length > 0 && absent === candidates.length * 2) {
    return "응답에 동일 기간 비교가 없습니다";
  }
  const parts = ["후보와 같은 시작 · 끝 날짜의 KODEX200 종가로 뺀 차이 (%p)"];
  if (unavailable) parts.push(`${unavailable}칸 계산 불가`);
  if (absent) parts.push(`${absent}칸 값 없음`);
  return parts.join(" · ");
}
