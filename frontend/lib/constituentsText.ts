// POC6-31 — 구성종목 화면 공용 문장(「오늘의 투자 점검」 보유 구성종목 줄 · 「ETF 구성종목」 수집 결과 · 중복률 쌍 범위 ·
// 여러 지수 계열 판정 · AI 복사 글). 화면마다 같은 말을 쓰도록 한 곳에 둔다.
import type { OverlapPair } from "@/lib/api/etfExposure";
import {
  UPDATE_FAILED_RESULTS,
  type ConstituentCounts,
  type ConstituentItem,
  type CrossFamilyStatus,
} from "@/lib/api/constituentsStatus";
import { md } from "@/lib/etfCompare";

const FAIL_LABEL: Record<string, string> = {
  failed: "받기 실패",
  timeout: "시간 초과로 조회 안 함",
  locked: "저장 잠김",
  no_source_date: "원천 기준일 미확인",
};

export interface CountsOpts {
  subject?: string; // 기본 '보유 ETF'
  calls?: number | null; // 작업 결과일 때 실제 호출 수
  shared?: number | null; // 다른 작업과 함께 받은 수(실제 호출에는 없음)
  // 저장 자료로 만든 상태(작업 결과 아님) — '새로 받음'은 생기지 않으므로 빼고 '목표일 이상 구성'으로 센다.
  statusMode?: boolean;
}

export function countsText(counts: ConstituentCounts | null | undefined, total: number, opts: CountsOpts = {}): string {
  const c = counts ?? {};
  const n = (k: keyof ConstituentCounts) => c[k] ?? 0;
  const failParts = UPDATE_FAILED_RESULTS.filter((k) => n(k) > 0).map((k) => `${FAIL_LABEL[k]} ${n(k)}`);
  const failed = UPDATE_FAILED_RESULTS.reduce((acc, k) => acc + n(k), 0);
  const parts = [`${opts.subject ?? "보유 ETF"} ${total}개`];
  if (opts.statusMode) {
    parts.push(`목표일 이상 구성 ${n("existing")}`);
  } else {
    parts.push(`기존 자료 ${n("existing")}`, `새로 받음 ${n("fetched")}`);
  }
  if (n("target_wait") > 0) parts.push(`목표일 자료 대기 ${n("target_wait")}`);
  if (failed > 0) parts.push(`갱신 실패 ${failed}(${failParts.join(" · ")})`);
  if (n("not_checked") > 0) parts.push(`아직 확인 안 함 ${n("not_checked")}`);
  if (!opts.statusMode && (opts.shared ?? 0) > 0) parts.push(`다른 작업과 함께 받음 ${opts.shared}`);
  if (!opts.statusMode && typeof opts.calls === "number") parts.push(`실제 호출 ${opts.calls}회`);
  return parts.join(" · ");
}

// 저장소 잠김으로 끝내 못 쓴 확인 기록(서버를 다시 켜면 그 ETF는 '아직 확인 안 함'으로 보임) — 0 이면 null.
export function unloggedText(n: number | null | undefined): string | null {
  return n && n > 0
    ? `확인 기록 ${n}줄을 저장하지 못했습니다(저장소 잠김) — 서버를 다시 켜면 그 ETF는 '아직 확인 안 함'으로 보입니다`
    : null;
}

// 수집 목표일 규칙(판정 §1 첫째 · §4 M1)
export const TARGET_RULE_TEXT = "목표일 = 거래일 15:30 이후면 그날, 그 전이나 휴장일이면 직전 거래일";

export function itemReason(it: ConstituentItem): string {
  return it.shared ? `${it.reason} · 다른 작업과 함께 받음` : it.reason;
}

export function shownDate(it: ConstituentItem): string | null {
  return it.source_asof ?? it.kept_asof ?? null;
}

export function dateMixText(items: ConstituentItem[]): string {
  const counts = new Map<string, number>();
  for (const it of items) {
    const d = shownDate(it) ?? "없음";
    counts.set(d, (counts.get(d) ?? 0) + 1);
  }
  const keys = [...counts.keys()].sort((a, b) => (a === "없음" ? 1 : b === "없음" ? -1 : b.localeCompare(a)));
  return keys.map((k) => `${k === "없음" ? "없음" : md(k)} ${counts.get(k)}개`).join(" · ");
}

// ── 중복률 쌍 범위(판정 Q7 · §4 M2 · §1 셋째) ──
export type PairScopeKind = "same_date" | "unconfirmed" | "different_date" | "no_data";

// 서버가 정한 범위. 칸 없는 예전 서버 응답은 한 날짜로 읽은 것이라 같은 구성일로 본다(same_date=false 만 다른 날짜).
export function pairScopeOf(p: Pick<OverlapPair, "pair_scope" | "same_date">): PairScopeKind {
  if (p.pair_scope) return p.pair_scope;
  return p.same_date === false ? "different_date" : "same_date";
}

export function splitPairs<T extends Pick<OverlapPair, "pair_scope" | "same_date">>(
  pairs: T[],
): Record<PairScopeKind, T[]> {
  const out: Record<PairScopeKind, T[]> = { same_date: [], unconfirmed: [], different_date: [], no_data: [] };
  for (const p of pairs) out[pairScopeOf(p)].push(p);
  return out;
}

// 참고로 뺀 쌍 문장 — '구성일 다름 a · 원천 기준일 미확인 b · 한쪽 구성 자료 없음 c'(0 은 뺌)
export function pairRestText(s: Record<PairScopeKind, unknown[]>): string {
  return [
    s.different_date.length ? `구성일 다름 ${s.different_date.length}` : null,
    s.unconfirmed.length ? `원천 기준일 미확인 ${s.unconfirmed.length}` : null,
    s.no_data.length ? `한쪽 구성 자료 없음 ${s.no_data.length}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

export function pairDateText(p: Pick<OverlapPair, "pair_scope" | "same_date" | "left_asof" | "right_asof">): string {
  const k = pairScopeOf(p);
  if (k === "no_data") return "한쪽 구성 자료 없음";
  const dates = p.left_asof && p.right_asof ? `${md(p.left_asof)} ↔ ${md(p.right_asof)}` : null;
  if (k === "unconfirmed") return `원천 기준일 미확인${dates ? ` · ${dates}` : ""}`;
  if (k === "different_date") return `구성일 다름${dates ? ` · ${dates}` : ""}`;
  return dates ? `${md(p.left_asof)} 같은 구성일` : "같은 구성일";
}

// ── 여러 지수 계열이 함께 담은 주식 판정 문장(화면 · 복사 글 공용) ──
export function crossFamilyVerdict(g: { status: CrossFamilyStatus; stockCount: number; evidenceCount: number }): string {
  if (g.status === "no_data") return "비교 못 함 — 원천 구성일이 확인된 구성 자료가 없습니다([구성종목 수집]으로 받습니다)";
  if (g.status === "not_comparable") return "비교 못 함 — 같은 날짜에 주식 행이 있는 계열이 2개 미만입니다";
  if (g.stockCount === 0) return "0종목 — 비교는 성립했고 서로 다른 계열 2개 이상이 함께 담은 주식이 없습니다";
  return `서로 다른 계열 2개 이상이 함께 담은 주식 ${g.stockCount}종목 · 편입 근거 ${g.evidenceCount}건`;
}
