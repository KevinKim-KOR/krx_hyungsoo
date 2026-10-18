// POC2 — 보유·후보 비교 v1 CLOSEOUT (2026-06-24) — helper.
//
// HoldingsCompareView.tsx 의 책임 분리 (FIX r1 — B-3 파일 책임 과다 해소).
// 신규 계산 / 신규 API 0건. 순수 변환 + 사용자 친화 상태 문구 상수.

import type { EnrichedHolding, MarketCandidate } from "@/lib/api";

// ─── 사용자 친화 상태 문구 (지시문 §6 — raw 상태값 미노출) ──────────

export const STATE_NORMAL = "정상";
export const STATE_PARTIAL_UNAVAIL = "일부 확인 불가";
export const STATE_UNCHECKED = "중복 확인 전";
export const STATE_UNAVAIL = "중복 확인 불가";
export const STATE_NO_DATA = "데이터 없음";
export const STATE_NEED_CHECK = "확인 필요";

// ─── 티커별 통합 보유 (AC-1) ────────────────────────────────────────

export interface AggregatedHolding {
  ticker: string;
  name: string | null;
  invested_amount: number;
  eval_amount: number | null;
  eval_partial_unavail: boolean;
  pnl_rate_pct: number | null;
  market_weight_pct: number | null;
  data_missing: boolean;
}

export function aggregateHoldingsByTicker(
  rows: EnrichedHolding[],
): AggregatedHolding[] {
  if (rows.length === 0) return [];

  const totalEval = rows.reduce((acc, r) => acc + (r.eval_amount ?? 0), 0);

  const byTicker = new Map<string, EnrichedHolding[]>();
  for (const r of rows) {
    const arr = byTicker.get(r.ticker) ?? [];
    arr.push(r);
    byTicker.set(r.ticker, arr);
  }

  const result: AggregatedHolding[] = [];
  for (const [ticker, group] of byTicker) {
    const invested = group.reduce((acc, r) => acc + r.invested_amount, 0);
    let evalSum: number | null = 0;
    let evalPartial = false;
    let dataMissing = false;
    for (const r of group) {
      if (r.price_missing || r.calc_missing) dataMissing = true;
      if (r.eval_amount === null) {
        evalPartial = true;
      } else if (evalSum !== null) {
        evalSum += r.eval_amount;
      }
    }
    if (evalPartial) evalSum = null;

    const pnlRate =
      evalSum !== null && invested > 0
        ? ((evalSum - invested) / invested) * 100
        : null;
    const marketWeight =
      evalSum !== null && totalEval > 0 ? (evalSum / totalEval) * 100 : null;

    result.push({
      ticker,
      name: group[0].name ?? null,
      invested_amount: invested,
      eval_amount: evalSum,
      eval_partial_unavail: evalPartial,
      pnl_rate_pct: pnlRate,
      market_weight_pct: marketWeight,
      data_missing: dataMissing,
    });
  }
  return result;
}

// ─── 보유 노출 1 칸 표현 (AC-4 · POC5-23 정정) ──────────────────────────
//
// POC5-23 판정 §3 — 이전 판정은 후보 **ETF 티커**를 보유 ETF 겹침 항목(시장 반복 핵심 **주식 종목** 티커)과
// 비교해 구조상 거의 늘 '보유 ETF 0개' · '중복 없음'이 됐다. 그 비교는 쓰지 않는다. 이 칸은 직접 보유 여부만
// 확정해 보이고, 후보 ↔ 보유 ETF 구성종목 중복은 [판단 근거 미리보기]가 저장 구성종목으로 비교한다(자동 조회 없음).

export const STATE_OVERLAP_UNCHECKED = "구성종목 중복 미확인";

export type ExposureKind =
  | "direct"
  | "overlap_unchecked"
  | "holdings_loading"
  | "holdings_unavailable";

export interface ExposureSummary {
  kind: ExposureKind;
  directHoldingTicker: string | null;
  directHoldingName: string | null;
}

export function computeExposure(
  candidateTicker: string | null | undefined,
  aggregated: AggregatedHolding[],
  holdingsLoaded: boolean,
  holdingsError: boolean,
): ExposureSummary {
  if (holdingsError) {
    return { kind: "holdings_unavailable", directHoldingTicker: null, directHoldingName: null };
  }
  if (!holdingsLoaded) {
    return { kind: "holdings_loading", directHoldingTicker: null, directHoldingName: null };
  }
  const direct = candidateTicker
    ? aggregated.find((h) => h.ticker === candidateTicker)
    : undefined;
  if (direct) {
    return {
      kind: "direct",
      directHoldingTicker: direct.ticker,
      directHoldingName: direct.name ?? null,
    };
  }
  return { kind: "overlap_unchecked", directHoldingTicker: null, directHoldingName: null };
}

export function exposureLabel(ex: ExposureSummary): string {
  switch (ex.kind) {
    case "direct":
      return "직접 보유";
    case "overlap_unchecked":
      return STATE_OVERLAP_UNCHECKED;
    case "holdings_loading":
      return "보유 확인 전";
    case "holdings_unavailable":
      return "보유 확인 불가";
  }
}

export function exposureColor(ex: ExposureSummary): string {
  return ex.kind === "direct" ? "var(--warn)" : "var(--muted)";
}

export function exposureSortRank(kind: ExposureKind): number {
  switch (kind) {
    case "direct":
      return 2;
    case "overlap_unchecked":
      return 1;
    case "holdings_loading":
    case "holdings_unavailable":
    default:
      return 0;
  }
}

// ─── 상태 라벨 helper ────────────────────────────────────────────────

export function candidateDataState(c: MarketCandidate): string {
  const sm = c.short_term_momentum;
  const dq = c.data_quality;
  const smOk = sm?.status === "ok";
  const dqOk = dq?.status === "ok";
  if (smOk && dqOk) return STATE_NORMAL;
  if (smOk || dqOk) return STATE_PARTIAL_UNAVAIL;
  return STATE_NEED_CHECK;
}

export function holdingStateLabel(h: AggregatedHolding): string {
  if (h.eval_partial_unavail || h.data_missing) return STATE_PARTIAL_UNAVAIL;
  if (h.eval_amount === null) return STATE_NO_DATA;
  return STATE_NORMAL;
}

export function exposureColorByState(state: string): string {
  if (state === STATE_NORMAL) return "var(--ok)";
  if (state === STATE_UNAVAIL) return "var(--danger)";
  if (state === STATE_UNCHECKED) return "var(--muted)";
  return "var(--muted)";
}

// ─── 포맷팅 helper ──────────────────────────────────────────────────

export const DASH = "-";

// POC5-23 — KODEX200 대비 같은 차이 값은 %p(미리보기 · 카드와 같은 단위 · 설계 §6-1).
export function fmtPctp(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%p`;
}

export function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function returnColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return "var(--muted)";
  // 2026-08-16 국내 관례 — 상승 빨강 / 하락 파랑 (전용 토큰).
  return value >= 0 ? "var(--pnl-up)" : "var(--pnl-down)";
}
