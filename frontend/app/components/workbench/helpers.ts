// POC3-02 Judgment Workbench — 공통 표시 헬퍼 (§8 데이터 정직성).
// Workbench 에만 적용. 기존 데이터 의미 변경 없음.

import { sameDetail, sameDiffOf, sameShort, sameViewOf } from "@/lib/samePeriodKodex";
import type {
  MarketCandidate,
  EnrichedHolding,
  HoldingsMarketEvidenceItem,
} from "@/lib/api";
import { ddSortValue } from "@/lib/storedDrawdown";

// 기준일 표시: 순수 날짜(YYYY-MM-DD)는 그대로, ISO datetime 은 KST 가독 변환
// (raw ISO 원문 미노출 · A-1(8)). 파싱 불가 시 "확인 불가".
export function fmtAsofKst(s: string | null | undefined): string {
  if (!s) return "—";
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const d = new Date(s);
  if (isNaN(d.getTime())) return "확인 불가";
  const parts = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(d);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")} ${get("hour")}:${get("minute")} KST`;
}

// 방향 있는 수치: 부호 + 방향 기호 (색만으로 방향 표현 안 함 · §7.5).
export function fmtSignedPct(v: number | null | undefined): string {
  if (v == null) return "—";
  const arrow = v > 0 ? "▲" : v < 0 ? "▼" : "―";
  return `${arrow} ${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

export function fmtPlainPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

export function fmtIndex(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toLocaleString("ko-KR", { maximumFractionDigits: 2 });
}

// 금액 요약 (억/만). 상세 정확 금액은 별도.
export function fmtAmountSummary(v: number | null | undefined): string {
  if (v == null) return "—";
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(2)}억`;
  if (abs >= 1e4) return `${sign}${Math.round(abs / 1e4).toLocaleString("ko-KR")}만`;
  return v.toLocaleString("ko-KR");
}

export function directionColor(v: number | null | undefined): string {
  if (v == null) return "var(--muted)";
  // 2026-08-16 국내 관례 — 상승 빨강 / 하락 파랑 (전용 토큰).
  return v > 0 ? "var(--pnl-up)" : v < 0 ? "var(--pnl-down)" : "var(--muted)";
}

// 후보 returns 접근 (없으면 null). c 가 없어도(undefined) 안전.
export function candReturn(
  c: MarketCandidate | undefined,
  key: "one_month" | "three_month" | "daily",
): number | null {
  const r = c?.returns?.[key];
  return r?.return_pct ?? null;
}

// 후보 동일 기간 KODEX200 대비 1M(%p) — 칸 · 사용자 정렬이 같은 값을 쓴다(POC5-22 · 판정 §2).
// 새 객체(`same_period_kodex200`)만 읽는다 — 없거나 계산 불가면 null(기존 excess_return 으로 대신하지 않음).
export function candExcess(c: MarketCandidate | undefined): number | null {
  return sameDiffOf(c?.same_period_kodex200, "1m");
}

// POC5-25 — 후보 '20저장일 종가 고점 대비'(%) — 현재 저장 종가 객체만(옛 drawdown_20d 를 쓰지 않는다 · 100배 없음).
export function candDrawdown(c: MarketCandidate | undefined): number | null {
  return ddSortValue(c);
}

// POC5-25 — 고점 대비 정렬의 값 없음 = 방향과 무관하게 맨 뒤(판정 §3). 둘 다 값이 있으면 null(값으로 비교).
export function drawdownMissingLast(
  a: MarketCandidate | undefined,
  b: MarketCandidate | undefined,
): number | null {
  const na = candDrawdown(a) == null;
  const nb = candDrawdown(b) == null;
  if (!na && !nb) return null;
  return na === nb ? 0 : na ? 1 : -1;
}

// 후보 데이터 상태 (data_quality · optional).
export function candDataState(c: MarketCandidate | undefined): string {
  const dq = c?.data_quality as { status?: string } | null | undefined;
  return dq?.status ?? "—";
}

// 후보/보유 일치: Evidence item 을 ticker 로 찾는다.
export function evidenceByTicker(
  items: HoldingsMarketEvidenceItem[] | undefined,
  ticker: string | null | undefined,
): HoldingsMarketEvidenceItem | undefined {
  if (!ticker || !items) return undefined;
  return items.find((it) => it.ticker === ticker);
}

// 보유 여부: **현재 Holdings 목록**(LIST_DIRECT) 기준. 과거 Evidence 존재 여부가
// 아니라 현재 보유 ticker 집합에 있는지로 판정한다 (요약·표 정합 · A-1). 필터용
// boolean (집합 미로드면 false — 필터는 "확정 보유만" 남기는 용도).
export function isHeld(
  heldTickers: Set<string> | undefined,
  ticker: string | null | undefined,
): boolean {
  return !!(ticker && heldTickers?.has(ticker));
}

// 관계 3-state: 집합이 undefined(현재 목록 조회 실패/미완)면 "확인 불가"(unknown),
// 로드됐으면 포함 여부로 yes/no. 조회 실패를 "미포함(false)" 으로 축약하지 않는다
// (A-1(4): 첫 조회 실패 시 관계를 확인 불가로 표시).
export type RelationState = "yes" | "no" | "unknown";
export function relationState(
  set: Set<string> | undefined,
  ticker: string | null | undefined,
): RelationState {
  if (!set || !ticker) return "unknown";
  return set.has(ticker) ? "yes" : "no";
}

// 현재 Holdings 응답에서 고유 ticker 집합.
export function heldTickerSet(
  items: { ticker: string }[] | undefined,
): Set<string> {
  return new Set((items ?? []).map((h) => h.ticker));
}

// 보유 종목 Evidence 확인 필요 여부 (evidence unavailable notes 등).
export function holdingNeedsAttention(item: HoldingsMarketEvidenceItem): boolean {
  // status 는 "ok" 아니면 각종 unavailable — ok 가 아니면 확인 필요.
  // NAV·구성종목뿐 아니라 returns·excess 상태도 검사한다 (A-1: 1M/3M/KODEX초과가
  // 전부 확인 불가인데 "정상" 으로 표시되던 결함 정정).
  const navBad =
    item.nav_discount?.status != null && item.nav_discount.status !== "ok";
  const conBad =
    item.constituents_overlap?.status != null &&
    item.constituents_overlap.status !== "ok";
  const retBad =
    item.returns?.status != null && item.returns.status !== "ok";
  const exBad =
    item.excess_return?.status != null && item.excess_return.status !== "ok";
  return navBad || conBad || retBad || exBad;
}

export function holdingEval(h: EnrichedHolding): {
  evalAmount: number | null;
  pnlAmount: number | null;
  pnlRate: number | null;
  weight: number | null;
} {
  return {
    evalAmount: h.eval_amount,
    pnlAmount: h.pnl_amount,
    pnlRate: h.pnl_rate_pct,
    weight: h.market_weight_pct,
  };
}

// Evidence item 의 기간 수익률 — 없으면 null.
// 2026-08-16: 6M/12M 추가(보유↔후보 같은 기간 비교). status 판정은 기존대로
//   1m/3m 기준이므로, status=ok 여도 6M/12M 은 null 일 수 있다.
export function evidenceReturn(
  ev: HoldingsMarketEvidenceItem | undefined,
  key: "one_month" | "three_month" | "six_month" | "twelve_month",
): number | null {
  const r = ev?.returns;
  if (!r || r.status !== "ok") return null;
  switch (key) {
    case "one_month":
      return r.one_month_return_pct;
    case "three_month":
      return r.three_month_return_pct;
    case "six_month":
      return r.six_month_return_pct ?? null;
    case "twelve_month":
      return r.twelve_month_return_pct ?? null;
  }
}

// 상세 칸 — 후보에 있으면 후보 객체, 보유만 고르면 보유 근거 객체(같은 helper · 같은 1M · POC5-22 Q2 (a)).
// 보유 근거 객체는 상위 후보와 연결된 보유 종목만 있다 — 없으면 '동일 기간 값 없음'(기존 excess_return ·
// 단기 20구간으로 대신하지 않는다). 보유 탭 칸은 HoldingTable 이 같은 sameViewOf 로 그린다.
export function samePeriodDetail(
  c: MarketCandidate | undefined,
  ev: HoldingsMarketEvidenceItem | undefined,
): string {
  const v = sameViewOf(c ? c.same_period_kodex200 : ev?.same_period_kodex200, "1m");
  const d = sameDetail(v);
  return d ? `${sameShort(v, "동일 기간 값 없음")} — ${d}` : sameShort(v, "동일 기간 값 없음");
}

// 보유 종목 Evidence 상태: 없음/실패는 "정상" 으로 표시하지 않는다 (A-1(5)).
export type HoldingEvidenceState = "ok" | "attention" | "unavailable" | "unknown";

export function holdingEvidenceState(
  ev: HoldingsMarketEvidenceItem | undefined,
  evidencePhase: "success" | "loading" | "error" | "idle",
): HoldingEvidenceState {
  // Evidence 조회 자체가 실패/로딩이면 정상 아님.
  if (evidencePhase === "error") return "unavailable";
  if (evidencePhase !== "success") return "unknown";
  // 조회는 됐으나 이 종목 Evidence 가 없음 → 확인 불가.
  if (!ev) return "unavailable";
  return holdingNeedsAttention(ev) ? "attention" : "ok";
}
