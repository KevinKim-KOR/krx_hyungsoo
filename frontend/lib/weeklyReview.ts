// POC6-32 V2 — 「주간 ETF 점검」 화면 도우미(숫자 · 기간 표시 · 판단 근거 미리보기 요청 · AI 세션 초안). 글 자체는 서버가 만든다.
// 넘기기 초안은 화면에 보이는 응답 하나에서만 만든다(판정 §3-1 · 같은 검토 건) — 기존 칸만(판정 Q7 · DB 열 없음).

import type { AISessionsDraft } from "@/lib/aiSessionsDraft";
import type { DecisionDraftListQuery } from "@/lib/api/decisionDraftPreview";
import {
  WEEKLY_REVIEW_SOURCE,
  type WeeklyFlow,
  type WeeklyMarketEvidence,
  type WeeklyMember,
  type WeeklyReturn,
  type WeeklyReviewOk,
} from "@/lib/api/weeklyReview";
import { md as mdOrUnknown, netWord, wonAbs } from "@/lib/todayMarketLines";

export function signedPct(v: number | null | undefined): string {
  // 서버 글(복사 글 · 시장 줄)과 같은 모양 — '+12.55%' · '-0.62%'(「후보리스트」 pct 와 같은 자릿수)
  if (v === null || v === undefined || !Number.isFinite(v)) return "확인 불가";
  const s = v > 0 ? "+" : v < 0 ? "-" : "";
  return `${s}${Math.abs(v).toFixed(2)}%`;
}

export function md(d: string | null | undefined): string {
  if (!d || !/^\d{4}-\d{2}-\d{2}/.test(d)) return d ?? "-";
  return `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}`;
}

type PeriodKey = "one_month" | "three_month";

// ETF 하나의 기간 값 — 기간 다름이면 값 + '기간 다름(실제 시작 → 끝)'(V2 W5 · '확인 불가'로 쓰지 않음) · 값이 없으면 '확인 불가'.
export function memberPeriodText(m: WeeklyMember, key: PeriodKey): string {
  const v = m[key];
  const p = m.periods?.[key];
  if (v !== null && p?.status === "period_differs") return `${signedPct(v)} · 기간 다름(${md(p.start)} → ${md(p.end)})`;
  return signedPct(v);
}

const differs = (m: WeeklyMember, key: PeriodKey) => m.periods?.[key]?.status === "period_differs";

// 묶음의 1개월 — 모두 공통 기간이고 같으면 '각 +10.80%' · 다르면 '최소 ~ 최대'(표시 자릿수 기준) ·
// 값이 없거나 기간 다름인 ETF 가 있으면 ETF 마다 이어 씀(기간이 다른 값을 범위로 묶지 않음).
export function oneMonthText(f: WeeklyFlow): string {
  const ms = f.members;
  if (ms.length === 1) return memberPeriodText(ms[0], "one_month");
  if (ms.some((m) => m.one_month === null || differs(m, "one_month"))) {
    return ms.map((m) => memberPeriodText(m, "one_month")).join(" · ");
  }
  const vs = ms.map((m) => m.one_month as number);
  const shown = Array.from(new Set(vs.map(signedPct)));
  if (shown.length === 1) return `각 ${shown[0]}`;
  return `${signedPct(Math.min(...vs))} ~ ${signedPct(Math.max(...vs))}`;
}

export function threeMonthText(f: WeeklyFlow): string {
  return f.members.map((m) => memberPeriodText(m, "three_month")).join(" · ");
}

export function ranksText(f: WeeklyFlow): string {
  return f.members.map((m) => m.rank).join(" · ");
}

// ② 행 자료 부족 표시 — 서버 사유 그대로 '자료 부족: …'(충분하면 null · 표시 없음).
export function lackText(lack: string[] | undefined): string | null {
  return lack && lack.length ? `자료 부족: ${lack.join(" · ")}` : null;
}

// 목록 안 ETF 하나(묶음 안 ETF 포함 · 없으면 null).
export function memberOf(r: WeeklyReviewOk, ticker: string): WeeklyMember | null {
  for (const f of r.flows) {
    const m = f.members.find((x) => x.ticker === ticker);
    if (m) return m;
  }
  return null;
}

// ③ '실제로 올랐나' 방향(서버 방향 코드 → 쉬운 한국어 · 값이 없으면 '확인 불가').
const DIRECTION: Record<string, string> = { up: "올랐음", down: "내렸음", flat: "변화 없음" };
export function directionText(r: WeeklyReturn): string {
  return r.direction ? DIRECTION[r.direction] : "확인 불가";
}

// 공식 기준정보 총보수(CSV 글자 '0.450000') → '0.45%' · 숫자가 아니면 글자 그대로 · 비면 '확인 불가'.
export function feeText(raw: string | null | undefined): string {
  const s = (raw ?? "").trim();
  if (!s) return "확인 불가";
  const n = Number(s);
  return Number.isFinite(n) ? `${n}%` : s;
}

// ③ 판단 근거 미리보기의 시장 흐름 묶음 기간(「ETF보유 및 후보 선정」 행 상세와 같은 6개월).
export const WEEKLY_FLOW_PERIOD = "6M";

// ── ① 시장 한 줄 — 공통 시장 근거 칸(일일 복사와 같은 칸 · 서버 `app/market_evidence.py`)에서 그린다 ──────────
// 판정 = 당일 판정(일일 복사 대조 기준과 같음) · 당일을 못 읽었으면 아침 판정 · 둘 다 없으면 사유.
// 기간 값은 늘 실제 시작 → 끝을 붙인다(PLAN §1-5 '1개월'의 뜻이 넷). 못 읽은 칸은 '확인 불가'(빈칸 · 0 으로 쓰지 않음).
type Obj = Record<string, unknown>;
const obj = (v: unknown): Obj | null => (v !== null && typeof v === "object" && !Array.isArray(v) ? (v as Obj) : null);
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const text = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v : null);
const POSITION: Record<string, string> = { above: "위", below: "아래" };

function retText(name: string, r: Obj | null): string {
  const v = num(r?.value);
  return v === null ? `${name} 확인 불가` : `${name} ${signedPct(v)}(${mdOrUnknown(text(r?.start))} → ${mdOrUnknown(text(r?.end))})`;
}

function maText(r: Obj): string {
  const p20 = POSITION[text(obj(r.ma20)?.position) ?? ""] ?? null;
  const p60 = POSITION[text(obj(r.ma60)?.position) ?? ""] ?? null;
  if (p20 && p20 === p60) return `20 · 60일선 ${p20}`;
  return `20일선 ${p20 ?? "확인 불가"} · 60일선 ${p60 ?? "확인 불가"}`;
}

function regimeText(fields: Obj): string {
  const rg = obj(fields.regime);
  const today = obj(rg?.today);
  const morning = obj(rg?.morning);
  const r = today?.status === "ok" ? today : morning?.status === "ok" ? morning : null;
  if (!r) return `KODEX 200 시장 판정 확인 불가 — ${text(today?.reason) ?? text(rg?.reason) ?? "근거 확인 불가"}`;
  const n = num(r.streak_days);
  const streak = n !== null ? ` · ${n}거래일째${r.at_least === true ? " 이상" : ""}` : " · 지속일 확인 불가";
  const which = r === today ? "" : " · 당일 판정 확인 불가 — 아침 판정";
  const both = r === today && rg?.same_basis === false && morning?.status === "ok" ? " · 아침 판정은 다른 근거(복사 글에 둘 다)" : "";
  const basis = [retText("20거래일", obj(r.r20)), retText("60거래일", obj(r.r60)), maText(r)].join(" · ");
  return `KODEX 200 ${text(r.label) ?? "확인 불가"}${streak}(판정 가격 ${mdOrUnknown(text(r.price_date))}${which} · ${basis})${both}`;
}

function windowText(w: Obj | null): string | null {
  const v = num(w?.sum);
  if (v === null) return null;
  return `${netWord(v)} ${wonAbs(v)}(${mdOrUnknown(text(w?.from))} ~ ${mdOrUnknown(text(w?.to))})`;
}

function foreignText(fields: Obj): string {
  const fl = obj(fields.flows);
  const w = obj(fl?.w20);
  const recent = w?.status === "ok" ? windowText(obj(w.recent)) : null;
  if (!recent) return `외국인 20거래일 확인 불가 — ${text(w?.reason) ?? text(fl?.reason) ?? "자료 없음"}`;
  const prev = windowText(obj(w?.previous));
  return `외국인 최근 20거래일 ${recent} · 직전 20거래일 ${prev ?? "확인 불가"}`;
}

// '자료 기준일' — 같은 날짜가 이어지면 이름을 묶는다(예: '코스피 · 수급 11/13').
function basisText(fields: Obj, etfEnd: string | null): string {
  const date = (k: string, key = "date") => text(obj(fields[k])?.[key]);
  const items: [string, string][] = [
    ["ETF 시세", mdOrUnknown(etfEnd)],
    ["코스피", mdOrUnknown(date("kospi"))],
    ["수급", mdOrUnknown(date("flows", "latest_date"))],
    ["원/달러", mdOrUnknown(date("usdkrw"))],
    ["WTI", mdOrUnknown(date("wti"))],
    ["VIX 미국", mdOrUnknown(date("vix"))],
  ];
  const groups: { names: string[]; d: string }[] = [];
  for (const [name, d] of items) {
    const last = groups[groups.length - 1];
    if (last && last.d === d) last.names.push(name);
    else groups.push({ names: [name], d });
  }
  return `자료 기준일: ${groups.map((g) => `${g.names.join(" · ")} ${g.d}`).join(" · ")}`;
}

export type WeeklyMarketView = { ok: true; line: string; basis: string } | { ok: false; reason: string };

export function weeklyMarketView(mev: WeeklyMarketEvidence | null | undefined, etfEnd: string | null): WeeklyMarketView {
  const fields = obj(mev?.fields);
  if (!mev || mev.status === "unavailable" || !fields) {
    return { ok: false, reason: `공통 시장 근거 확인 불가 — ${text(mev?.message) ?? "사유 확인 불가"}` };
  }
  return { ok: true, line: `${regimeText(fields)} · ${foreignText(fields)}`, basis: basisText(fields, etfEnd) };
}

// [판단 근거 보기] 요청 — 이 화면의 공통 기간 목록(1개월 상위 · 제외 4종)에서 고른 ETF 를 찾고, 화면이 본 순위 ·
// 1개월 실제 시작 · 끝 · 끝일 가격 상태 · 1개월 값을 서버가 지금 목록과 대조한다(다르면 '목록이 바뀜' 안내).
// 서버(`app/decision_preview_common_period.py`)는 주간 화면 값 'today_weekly_review' 를 받는다(DecisionDraftScreen).
export function weeklyPreviewQuery(r: WeeklyReviewOk, ticker: string): DecisionDraftListQuery | null {
  const m = memberOf(r, ticker);
  if (!m) return null;
  const p = m.periods?.one_month;
  return {
    list_source: "common_period",
    screen: WEEKLY_REVIEW_SOURCE,
    basis: r.condition.basis,
    ...r.condition.filters,
    side: r.condition.side,
    rank: m.rank,
    start_date: p?.start ?? null,
    end_date: p?.end ?? null,
    end_price_state: m.end_price?.state ?? null,
    basis_value: m.one_month,
  };
}

// 넘기기 초안 — 질문 원문 = 복사 글 · 시장 근거 = 응답의 시장 묶음 · 고른 후보의 상품 · 구성 요약 · 보유 겹침 ·
// 검토 조건 · 자료 부족 · 근거 목록(PLAN V2 §4-3 · I-13). 모두 이 응답 하나의 값(다시 계산 없음).
export function weeklyDraft(r: WeeklyReviewOk, now: Date = new Date()): AISessionsDraft {
  return {
    asof: r.end_date,
    filters: { ...r.condition.filters },
    candidate_snapshot: r.candidate_snapshot,
    question_text: r.copy_text,
    linked_market_refresh_id: null,
    draft_created_at: now.toISOString(),
    market_context_snapshot: r.market_context_snapshot,
    constituent_snapshot: r.constituent_snapshot ?? null,
    overlap_snapshot: r.overlap ? { ...r.overlap } : null,
    data_quality_snapshot: r.data_quality_snapshot ? { ...r.data_quality_snapshot } : null,
    source_screen: WEEKLY_REVIEW_SOURCE,
  };
}
