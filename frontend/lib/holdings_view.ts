// POC2 Step 5D-2 Final — RunPanel.tsx + EvidenceDetails.tsx + HoldingsClient.tsx 가
// 공유하는 helpers / types. 본 파일은 순수 함수와 타입만 포함하며 React 컴포넌트는
// 두지 않는다 (.ts 파일 — JSX 미포함).
//
// 분리 목적: KS-10 트리거 해소 + RunPanel ↔ EvidenceDetails 양방향 import 정돈.
// 분리 전후 함수 본문 / 타입 / 동작 / 출력 모두 동일 — 위치만 이동.

export const DEFAULT_GROUP = "일반";

// ─── 숫자 / 포맷 helpers ─────────────────────────────────────────

export function toFiniteNumber(v: unknown): number | null {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

export function fmtMoney(v: unknown): string | null {
  const n = toFiniteNumber(v);
  if (n === null) return null;
  return `${n.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}원`;
}

export function fmtSignedMoney(v: unknown): string | null {
  const n = toFiniteNumber(v);
  if (n === null) return null;
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}원`;
}

export function fmtPct(v: unknown): string | null {
  const n = toFiniteNumber(v);
  if (n === null) return null;
  return `${n.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}%`;
}

export function fmtSignedPct(v: unknown): string | null {
  const n = toFiniteNumber(v);
  if (n === null) return null;
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}%`;
}

export function pnlClass(v: unknown): string {
  const n = toFiniteNumber(v);
  if (n === null) return "";
  if (n > 0) return "pnl-pos";
  if (n < 0) return "pnl-neg";
  return "";
}

// ─── recommendations 정규화 ─────────────────────────────────────

export type NormRec = {
  ticker: string;
  name: string;
  account_group: string;
  source_index: number;
  quantity: number | null;
  avg_buy_price: number | null;
  invested_amount: number | null;
  current_price: number | null;
  eval_amount: number | null;
  pnl_amount: number | null;
  pnl_rate_pct: number | null;
  buy_weight_pct: number | null;
  market_weight_pct: number | null;
  price_asof: string | null;
  price_source: string | null;
  action: string;
  reason: string;
};

export function normalizeRec(
  r: Record<string, unknown>,
  idx: number,
): NormRec {
  const ag =
    typeof r.account_group === "string" && r.account_group.trim()
      ? r.account_group
      : DEFAULT_GROUP;
  const si =
    typeof r.source_index === "number" && Number.isFinite(r.source_index)
      ? r.source_index
      : idx;
  const ticker = typeof r.ticker === "string" ? r.ticker : "";
  const name = typeof r.name === "string" ? r.name : "";
  const action = typeof r.action === "string" ? r.action : "";
  const reason = typeof r.reason === "string" ? r.reason : "";
  return {
    ticker,
    name,
    account_group: ag,
    source_index: si,
    quantity: toFiniteNumber(r.quantity),
    avg_buy_price: toFiniteNumber(r.avg_buy_price),
    invested_amount: toFiniteNumber(r.invested_amount),
    current_price: toFiniteNumber(r.current_price),
    eval_amount: toFiniteNumber(r.eval_amount),
    pnl_amount: toFiniteNumber(r.pnl_amount),
    pnl_rate_pct: toFiniteNumber(r.pnl_rate_pct),
    buy_weight_pct: toFiniteNumber(r.buy_weight_pct),
    market_weight_pct: toFiniteNumber(r.market_weight_pct),
    price_asof: typeof r.price_asof === "string" ? r.price_asof : null,
    price_source: typeof r.price_source === "string" ? r.price_source : null,
    action,
    reason,
  };
}

export function isPriced(rec: NormRec): boolean {
  return rec.current_price !== null && rec.current_price > 0;
}

export function isCalcAvailable(rec: NormRec): boolean {
  return (
    isPriced(rec) &&
    rec.eval_amount !== null &&
    rec.eval_amount > 0 &&
    rec.invested_amount !== null &&
    rec.invested_amount > 0
  );
}

export function rowKey(rec: NormRec): string {
  // source_index + ticker + account_group + avg_buy_price.
  // avg_buy_price 누락 시 "?" 토큰으로 대체 (동일 종목 다중 행 충돌 방지).
  const avg =
    rec.avg_buy_price !== null && rec.avg_buy_price !== undefined
      ? rec.avg_buy_price
      : "?";
  return `${rec.source_index}|${rec.ticker}|${rec.account_group}|${avg}`;
}

// ─── 요약 계산 ────────────────────────────────────────────────

export type Summary = {
  total_count: number;
  priced_count: number;
  unpriced_count: number;
  calc_available_count: number;
  calc_missing_count: number;
  total_invested: number;
  priced_invested: number;
  priced_eval: number | null;
  priced_pnl: number | null;
  priced_pnl_rate_pct: number | null;
};

export type AccountSummary = Summary & { account_group: string };

export function computeSummaryFor(recs: NormRec[]): Summary {
  const total_count = recs.length;
  const priced = recs.filter(isPriced);
  const calc = priced.filter(isCalcAvailable);

  let total_invested = 0;
  for (const r of recs) {
    if (r.invested_amount !== null) total_invested += r.invested_amount;
  }

  let calc_invested = 0;
  let calc_eval = 0;
  for (const r of calc) {
    calc_invested += r.invested_amount as number;
    calc_eval += r.eval_amount as number;
  }

  const priced_pnl = calc.length > 0 ? calc_eval - calc_invested : null;
  const priced_pnl_rate_pct =
    calc.length > 0 && calc_invested > 0 && priced_pnl !== null
      ? (priced_pnl / calc_invested) * 100.0
      : null;

  return {
    total_count,
    priced_count: priced.length,
    unpriced_count: total_count - priced.length,
    calc_available_count: calc.length,
    calc_missing_count: priced.length - calc.length,
    total_invested,
    priced_invested: calc_invested,
    priced_eval: calc.length > 0 ? calc_eval : null,
    priced_pnl,
    priced_pnl_rate_pct,
  };
}
