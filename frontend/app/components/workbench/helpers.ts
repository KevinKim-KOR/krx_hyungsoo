// POC3-02 Judgment Workbench — 공통 표시 헬퍼 (§8 데이터 정직성).
// Workbench 에만 적용. 기존 데이터 의미 변경 없음.

import type {
  MarketCandidate,
  EnrichedHolding,
  HoldingsMarketEvidenceItem,
} from "@/lib/api";

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

export function fmtScore(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toFixed(1);
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
  return v > 0 ? "var(--ok)" : v < 0 ? "var(--danger)" : "var(--muted)";
}

// 후보 returns 접근 (없으면 null). c 가 없어도(undefined) 안전.
export function candReturn(
  c: MarketCandidate | undefined,
  key: "one_month" | "three_month" | "daily",
): number | null {
  const r = c?.returns?.[key];
  return r?.return_pct ?? null;
}

// 후보 초과수익 (excess_return · optional shape 안전 접근).
// 2026-08-13 필드명 정정 — 실제 응답 키는 `vs_kodex200_1m_pctp` 이며
// `excess_return_pct` 는 존재하지 않아 항상 null 이었다(화면 전체 "—").
// 보유 탭의 evidenceExcess 와 같은 1M 기준으로 맞춘다.
export function candExcess(c: MarketCandidate | undefined): number | null {
  const ex = c?.excess_return as
    | { vs_kodex200_1m_pctp?: number | null; excess_return_pct?: number | null }
    | null
    | undefined;
  return ex?.vs_kodex200_1m_pctp ?? ex?.excess_return_pct ?? null;
}

// 후보 고점 대비 (drawdown_20d · 음수 표기 close/peak-1 → %).
export function candDrawdown(c: MarketCandidate | undefined): number | null {
  return c?.drawdown_20d != null ? c.drawdown_20d * 100 : null;
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

// Evidence item 의 기간 수익률 (1M/3M) — 없으면 null.
export function evidenceReturn(
  ev: HoldingsMarketEvidenceItem | undefined,
  key: "one_month" | "three_month",
): number | null {
  const r = ev?.returns;
  if (!r || r.status !== "ok") return null;
  return key === "one_month"
    ? r.one_month_return_pct
    : r.three_month_return_pct;
}

// Evidence item 의 KODEX200 대비 초과수익 (1M pctp) — 없으면 null.
export function evidenceExcess(
  ev: HoldingsMarketEvidenceItem | undefined,
): number | null {
  const ex = ev?.excess_return;
  if (!ex || ex.status !== "ok") return null;
  return ex.vs_kodex200_1m_pctp;
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
