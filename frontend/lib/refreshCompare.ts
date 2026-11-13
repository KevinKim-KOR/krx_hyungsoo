// POC6-29 보완 R2(RESULT 판정 §2-2 · 보완 PLAN 판정 '구현에서 확인할 세 가지' 2) — 시장 갱신 전후 대조.
// 날짜만 보면 같은 거래일에 다시 받은 값(예: KODEX 200 09:53 장중 85,045원 → 15:56 마감 뒤 저장 84,240원)이
// '그대로'로 보인다. 자료별 날짜 + 저장 시각(+ 확인되는 값)을 함께 대조한다. 대기 · 다시 읽기 실패 때는 지금 표시 중인
// 값의 기준(날짜 · 저장 시각)을 그대로 적는다.
import type { MarketTopNResponse } from "./api";
import type { EtfDetailResponse } from "./api/etfDetail";
import type { MarketFlowContext } from "./api/marketFlow";
import { kstMdHm } from "./marketNowText";
import { kstDate } from "./todayFreshness";
import { kospiObs, md, num2, priceObs, withUnit } from "./todayMarketLines";

export type SourceKey = "etf" | "kospi" | "flows" | "usdkrw" | "wti" | "vix";

export interface SourceSnap {
  date: string | null;
  // 저장 · 수집 시각(없으면 null — 날짜 · 값만 대조)
  saved: string | null;
  // 가격 시점(ETF 가격만 · intraday · after_close · unknown)
  state: string | null;
  value: number | null;
}

export type Snapshot = Record<SourceKey, SourceSnap>;

const LABELS: [SourceKey, string][] = [
  ["etf", "ETF 가격"],
  ["kospi", "코스피 공식 종가"],
  ["flows", "외국인 수급"],
  ["usdkrw", "원/달러"],
  ["wti", "WTI"],
  ["vix", "VIX"],
];

const STATE_WORD: Record<string, string> = { intraday: "장중", after_close: "마감 뒤", unknown: "시점 확인 필요" };

const EMPTY: SourceSnap = { date: null, saved: null, state: null, value: null };

// KODEX 200(069500) 상세의 끝일 가격 · 가격 시점 — 시장 판정의 기준 가격이자 ETF 가격 저장의 대표값.
// 상세를 읽지 못하면 '확인 불가'(다른 응답의 날짜로 채우지 않음 — 출처가 섞이면 없는 변화가 보인다).
export function kodexSnap(detail: EtfDetailResponse | null): SourceSnap {
  const it = detail?.status === "ok" ? (detail.items.find((x) => x.ticker === "069500") ?? null) : null;
  const ep = it?.end_price ?? null;
  if (!it || !ep) return EMPTY;
  const end = [it.daily, it.w5, it.w20, it.m1].find((p) => p && p.end === ep.date && p.end_close != null);
  return { date: ep.date, saved: ep.fetched_at_kst ?? null, state: ep.state ?? null, value: end?.end_close ?? null };
}

// 당일 판정 문장의 기준 — 판정이 쓴 끝 행(아침 기준 응답 today_regime.basis_row · 판정과 같은 한 번 읽기)의 날짜 · 저장 시점.
// 'KODEX 200 11/12 가격(15:56 마감 뒤 저장)' · 다른 날 저장이면 날짜까지 · 저장 시각을 모르면 '저장 시점 확인 필요'.
export function storedRowText(row: { date: string; state: string | null; fetched_at_kst: string | null }): string {
  const head = `KODEX 200 ${md(row.date)} 가격`;
  if (!row.fetched_at_kst) return `${head}(저장 시점 확인 필요)`;
  const when = kstDate(row.fetched_at_kst) === row.date ? hm(row.fetched_at_kst) : kstMdHm(row.fetched_at_kst);
  if (row.state === "intraday" || row.state === "after_close") return `${head}(${when} ${STATE_WORD[row.state]} 저장)`;
  return `${head}(${when} 저장 · 장중인지 마감 뒤인지 확인 필요)`;
}

export function snapshotOf(
  m: MarketTopNResponse | null,
  f: MarketFlowContext | null,
  kodex: EtfDetailResponse | null,
): Snapshot {
  const st = (k: string) => f?.status?.find((s) => s.key === k) ?? null;
  const ko = kospiObs(f);
  const kDate = m?.market_context?.kospi?.as_of_date ?? st("kospi")?.E ?? null;
  const priced = (key: "usdkrw" | "wti"): SourceSnap => {
    const s = st(key);
    const o = priceObs(f, key);
    return { date: s?.E ?? null, saved: s?.collected_at ?? null, state: null, value: o && o.date === s?.E ? o.value : null };
  };
  const vix = m?.market_risk_reference?.vix ?? null;
  return {
    etf: kodexSnap(kodex),
    kospi: { date: kDate, saved: st("kospi")?.collected_at ?? null, state: null, value: ko && ko.date === kDate ? ko.value : null },
    flows: { date: st("flows")?.E ?? null, saved: st("flows")?.collected_at ?? null, state: null, value: null },
    usdkrw: priced("usdkrw"),
    wti: priced("wti"),
    vix: { date: vix?.as_of_date ?? null, saved: null, state: null, value: vix?.close ?? null },
  };
}

function hm(iso: string): string {
  // 'M/D HH:MM' 에서 시각만(같은 날 대조 줄 · 날짜는 앞에 이미 있음)
  const t = kstMdHm(iso);
  const i = t.lastIndexOf(" ");
  return i >= 0 ? t.slice(i + 1) : t;
}

function valueText(k: SourceKey, v: number): string {
  if (k === "etf") return `${Math.round(v).toLocaleString("ko-KR")}원`;
  if (k === "usdkrw") return withUnit(v, "원");
  if (k === "wti") return withUnit(v, "달러");
  return num2(v);
}

// 저장 시각 — 가격일과 같은 날이면 시각만, 다른 날(예: 11/9 가격을 11/10 13:18 저장)이면 날짜까지.
function savedWord(s: SourceSnap): string {
  const st = s.state ? STATE_WORD[s.state] : null;
  if (!s.saved) return st ?? "";
  const when = kstDate(s.saved) === s.date ? hm(s.saved) : kstMdHm(s.saved);
  return `${when}${st ? ` ${st}` : ""}`;
}

// 지금 표시 중인 값의 기준 — 대기 · 다시 읽기 실패 줄(ETF 가격은 저장 시각 · 가격 시점까지).
export function snapshotText(s: Snapshot): string {
  return LABELS.map(([k, label]) => {
    const x = s[k];
    if (!x.date) return `${label} 확인 불가`;
    if (k === "etf" && x.saved) return `${label} ${md(x.date)}(${savedWord(x)} 저장)`;
    return `${label} ${md(x.date)}`;
  }).join(" · ");
}

export function compareSource(k: SourceKey, label: string, a: SourceSnap, b: SourceSnap): string {
  if (!b.date) return `${label} 확인 불가`;
  if (!a.date) return `${label} 없음 → ${md(b.date)}`;
  if (a.date !== b.date) return `${label} ${md(a.date)} → ${md(b.date)}`;
  const vals =
    a.value != null && b.value != null && a.value !== b.value
      ? `${k === "etf" ? "KODEX 200 " : ""}${valueText(k, a.value)} → ${valueText(k, b.value)}`
      : null;
  if (a.saved && b.saved && a.saved !== b.saved) {
    const when = `${savedWord(a)} → ${savedWord(b)} 저장`;
    return `${label} ${md(b.date)} 같은 거래일에 다시 받음(${when}${vals ? ` · ${vals}` : ""})`;
  }
  if (vals) return `${label} ${md(b.date)} 값 바뀜(${vals})`;
  return `${label} ${md(b.date)} 그대로`;
}

export function compareSnapshots(before: Snapshot, after: Snapshot): string {
  return LABELS.map(([k, label]) => compareSource(k, label, before[k], after[k])).join(" · ");
}
