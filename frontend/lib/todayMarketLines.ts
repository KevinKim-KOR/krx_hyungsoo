// POC6-27 — 「오늘의 투자 점검」 시장 흐름 문장(설계 §3 · PLAN 쟁점 1 · 판정 §2 · §4).
//
// 숫자는 모두 서버가 계산한 구조 칸에서 읽는다(문장 파싱 없음 · 새 계산 없음 — 형식만).
// - 실제 종가(obs.value · 그날)와 비교 기준값(range.bound · 직전 20개 관측의 최고 · 최저 · bound_date)을 나눠 쓴다.
// - 비교 날짜는 실제 날짜로 적는다('11/5의 최근 저점 …' · RESULT 판정 §3-1). d1.from_date 는 직전 '저장' 종가일이라
//   중간 거래일 종가가 비면 실제 직전 거래일과 다를 수 있어 '직전 거래일' · '전일'로 부르지 않는다(달력 조회 없음).
// - 최근 큰 변화: 서버 줄과 같은 고르기(최신순 2건 · '외 N건') · 위 저점 문장과 발생일 · 방향 · 비교일 ·
//   기준값이 모두 같은 코스피 범위 사건 1건만 뺀다(같은 날 다른 종류 사건은 그대로).
// - 구조 칸이 없는 옛 응답이면 서버 원문 줄에 '괄호 안 = 비교 기준값'을 붙여 보인다.
import type {
  FlowEvent,
  FlowNetObs,
  FlowPriceObs,
  FlowSeriesKey,
  FlowWindowSum,
  MarketFlowContext,
} from "@/lib/api/marketFlow";

const WON_PER_EOK = 100_000_000;

// 날짜 칸은 실제 달력 날짜로 읽힐 때만 날짜로 쓴다(검증자 r1 F2 — 모양만 맞는 2026-13-01 · 2026-02-30 은 날짜가 아님).
export function isRealDate(s: string | null | undefined): s is string {
  if (typeof s !== "string") return false;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return false;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const t = new Date(Date.UTC(y, mo - 1, d));
  return t.getUTCFullYear() === y && t.getUTCMonth() === mo - 1 && t.getUTCDate() === d;
}

// ISO 시각(날짜 · 시 · 분 · 선택 초 · 시간대 필수)만 읽는다 — 아니면 null.
// JS 기본 해석은 느슨하다(2026-02-30 을 3/2 로 넘기고 '2026/11/06' · 'Nov 6 2026' 도 받음 · F2).
const ISO_INSTANT = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d{1,9})?)?(?:Z|[+-](\d{2}):(\d{2}))$/;
export function parseIsoInstant(s: string | null | undefined): Date | null {
  if (typeof s !== "string") return null;
  const m = ISO_INSTANT.exec(s);
  if (!m || !isRealDate(m[1])) return null;
  if (Number(m[2]) > 23 || Number(m[3]) > 59 || (m[4] !== undefined && Number(m[4]) > 59)) return null;
  if (m[5] !== undefined && (Number(m[5]) > 14 || Number(m[6]) > 59)) return null;
  const t = new Date(s);
  return isNaN(t.getTime()) ? null : t;
}

// 'M/D' — 실제 날짜가 아니면 받은 글자 그대로(13/1 처럼 날짜인 척하지 않음).
export function md(d: string | null | undefined): string {
  if (!d) return "확인 불가";
  return isRealDate(d) ? `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}` : d;
}

export function num2(v: number): string {
  return v.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function withUnit(v: number, unit: string | undefined): string {
  if (!unit || unit === "pt") return num2(v);
  return `${num2(v)}${unit}`;
}

// 기존 화면 fmtPct 와 같은 부호 표기(+ · -).
export function signedPct(p: number | null | undefined): string {
  if (p == null || !Number.isFinite(p)) return "확인 불가";
  return `${p >= 0 ? "+" : "-"}${Math.abs(p).toFixed(2)}%`;
}

// 서버 won() 과 같은 형식(정수 원 → 억원 · 조원 · 부호 없이 크기만 · 방향은 문장에서).
export function wonAbs(v: number): string {
  const a = Math.abs(v) / WON_PER_EOK;
  if (a >= 10000) {
    return `${(a / 10000).toLocaleString("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}조원`;
  }
  return `${Math.round(a).toLocaleString("ko-KR")}억원`;
}

// 받침 유무로 조사 고르기(숫자는 읽는 소리 · 영문 끝 글자는 받침 없음으로).
const DIGIT_HAS_FINAL: Record<string, boolean> = {
  "0": true, // 영
  "1": true, // 일
  "2": false, // 이
  "3": true, // 삼
  "4": false, // 사
  "5": false, // 오
  "6": true, // 육
  "7": true, // 칠
  "8": true, // 팔
  "9": false, // 구
};

function hasFinal(word: string): boolean {
  const ch = word.trim().slice(-1);
  if (ch in DIGIT_HAS_FINAL) return DIGIT_HAS_FINAL[ch];
  const code = ch.charCodeAt(0);
  if (code >= 0xac00 && code <= 0xd7a3) return (code - 0xac00) % 28 !== 0;
  return false;
}

export function josa(word: string, withFinal: string, withoutFinal: string): string {
  return `${word}${hasFinal(word) ? withFinal : withoutFinal}`;
}

const LABEL: Record<FlowSeriesKey, string> = {
  kospi: "코스피",
  usdkrw: "원/달러",
  wti: "WTI",
  foreign: "외국인",
  institution: "기관계",
};

function isPriceObs(o: unknown): o is FlowPriceObs {
  return typeof o === "object" && o !== null && "range" in o && "d1" in o;
}

export function kospiObs(flow: MarketFlowContext | null): FlowPriceObs | null {
  const row = flow?.short_lines?.find((r) => r.key === "kospi");
  return row && isPriceObs(row.obs) ? row.obs : null;
}

export function priceObs(flow: MarketFlowContext | null, key: "usdkrw" | "wti"): FlowPriceObs | null {
  const row = flow?.short_lines?.find((r) => r.key === key);
  return row && isPriceObs(row.obs) ? row.obs : null;
}

export function foreignObs(flow: MarketFlowContext | null): FlowNetObs | null {
  const row = flow?.short_lines?.find((r) => r.key === "foreign");
  const o = row?.obs;
  return o && !isPriceObs(o) ? (o as FlowNetObs) : null;
}

// 상단 저점 문장 — 그날 종가가 직전 20개 관측 범위를 벗어났을 때만.
export function lowSentence(obs: FlowPriceObs | null): string | null {
  const r = obs?.range;
  if (!obs || !r) return null;
  const when = md(r.bound_date);
  return r.dir === "아래"
    ? `${when}의 최근 저점 ${josa(num2(r.bound), "을", "를")} 밑돌았습니다.`
    : `${when}의 최근 고점 ${josa(num2(r.bound), "을", "를")} 넘었습니다.`;
}

export function isSameAsLow(e: FlowEvent, obs: FlowPriceObs | null): boolean {
  const r = obs?.range;
  return (
    !!obs &&
    !!r &&
    e.key === "kospi" &&
    e.kind === "range" &&
    e.date === obs.date &&
    e.dir === r.dir &&
    e.bound_date === r.bound_date &&
    e.bound === r.bound
  );
}

export function hasStructuredEvents(flow: MarketFlowContext): boolean {
  return (flow.events ?? []).every((e) => e.key !== undefined && e.value !== undefined);
}

// 사건 한 줄 — 날짜와 변화를 먼저(판정 §2 예: '11/5 코스피 종가 5,383.80이 10/26 저점 5,469.47을 밑돌았습니다').
export function eventSentence(e: FlowEvent): string {
  if (e.key === undefined || e.value === undefined) return `${e.text} (괄호 안 = 비교 기준값)`;
  const label = LABEL[e.key];
  const when = md(e.date);
  if (e.key === "foreign" || e.key === "institution") {
    const way = e.value < 0 ? "순매도" : "순매수";
    return e.ratio != null
      ? `${when} ${label} ${way} ${wonAbs(e.value)} · 직전 20거래일 평균 규모의 ${e.ratio.toFixed(1)}배`
      : `${when} ${label} 직전 20거래일 순매수 0, 이번 ${way} ${wonAbs(e.value)}`;
  }
  if (e.kind === "range" && e.bound !== undefined && e.bound_date) {
    const subject = e.key === "kospi" ? `코스피 종가 ${num2(e.value)}` : `${label} ${withUnit(e.value, e.unit)}`;
    const mark = e.dir === "아래" ? "저점" : "고점";
    const verb = e.dir === "아래" ? "밑돌았습니다" : "넘었습니다";
    return `${when} ${josa(subject, "이", "가")} ${md(e.bound_date)} ${mark} ${josa(withUnit(e.bound, e.unit), "을", "를")} ${verb}`;
  }
  if (e.kind === "expansion" && e.delta !== undefined) {
    const move = `${withUnit(Math.abs(e.delta), e.unit)} ${e.delta < 0 ? "하락" : "상승"}했습니다`;
    if (e.zero_base) return `${when} ${josa(label, "이", "가")} 직전 20회 변화가 없다가 ${move}`;
    return `${when} ${josa(label, "이", "가")} ${move}${e.ratio != null ? ` · 평소 변화의 ${e.ratio.toFixed(1)}배` : ""}`;
  }
  return `${e.text} (괄호 안 = 비교 기준값)`;
}

export interface RecentChanges {
  // 구조 칸이 있는 응답: 보일 문장 2건 · 나머지 수 · 빼낸 건수 · 확인 못 한 자료 문장 · 사건 없음 문장.
  shown: string[];
  rest: number;
  excluded: number;
  unchecked: string | null;
  empty: string | null;
  // 구조 칸이 없는 옛 응답: 서버 원문 줄(괄호 안 = 비교 기준값 안내 붙임).
  legacy: string | null;
}

export function recentChanges(flow: MarketFlowContext, lowShown: boolean): RecentChanges {
  const chk = flow.event_check ?? { unchecked_text: null, empty_text: null };
  const events = flow.events ?? [];
  if (events.length > 0 && !hasStructuredEvents(flow)) {
    const line = flow.today_lines?.[1] ?? null;
    return {
      shown: [],
      rest: 0,
      excluded: 0,
      unchecked: null,
      empty: null,
      legacy: line ? `${line} (괄호 안 = 비교 기준값)` : null,
    };
  }
  const obs = lowShown ? kospiObs(flow) : null;
  const kept = obs ? events.filter((e) => !isSameAsLow(e, obs)) : events;
  const shown = kept.slice(0, 2).map(eventSentence);
  return {
    shown,
    rest: kept.length - shown.length,
    excluded: events.length - kept.length,
    unchecked: chk.unchecked_text,
    empty: events.length === 0 ? chk.empty_text : null,
    legacy: null,
  };
}

// 외국인 수급 — 6개월 합(기간 표 · 수급과 같은 공통 기간) · 최근 · 직전 20거래일(서버 창 계산 그대로).
export interface ForeignView {
  six: { sum: number; days: number; expected: number; partial: boolean; end: string } | null;
  recent: FlowWindowSum | null;
  previous: FlowWindowSum | null;
  trend: string | null;
}

export function foreignView(flow: MarketFlowContext | null): ForeignView {
  const p = flow?.periods?.["6M"];
  const f = p?.investors?.foreign;
  const w = flow?.windows?.foreign20 ?? null;
  return {
    six: p && f ? { ...f, end: p.end } : null,
    recent: w?.recent ?? null,
    previous: w?.previous ?? null,
    trend: flow?.windows?.trend ?? null,
  };
}

export function netWord(v: number): string {
  return v < 0 ? "순매도" : "순매수";
}
