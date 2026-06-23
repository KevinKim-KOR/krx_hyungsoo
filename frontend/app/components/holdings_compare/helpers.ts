// POC2 — 보유·후보 비교 v1 CLOSEOUT (2026-06-24) — helper.
//
// HoldingsCompareView.tsx 의 책임 분리 (FIX r1 — B-3 파일 책임 과다 해소).
// 신규 계산 / 신규 API 0건. 순수 변환 + 사용자 친화 상태 문구 상수.

import type {
  EnrichedHolding,
  HoldingsMarketEvidenceItem,
  MarketCandidate,
} from "@/lib/api";

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

// ─── 보유 노출 1 칸 표현 (AC-4) ─────────────────────────────────────

export type ExposureKind =
  | "direct_only"
  | "direct_and_overlap"
  | "overlap_only"
  | "no_overlap"
  | "unchecked"
  | "unavailable";

export interface ExposureSummary {
  kind: ExposureKind;
  directHoldingTicker: string | null;
  directHoldingName: string | null;
  overlapHoldingCount: number;
  topOverlapHoldingName: string | null;
  topOverlapWeightPct: number | null;
}

export function computeExposure(
  candidateTicker: string | null | undefined,
  aggregated: AggregatedHolding[],
  evidenceByTicker: Record<string, HoldingsMarketEvidenceItem>,
  evidenceLoaded: boolean,
  evidenceError: boolean,
): ExposureSummary {
  const direct = candidateTicker
    ? aggregated.find((h) => h.ticker === candidateTicker)
    : undefined;
  const directHoldingTicker = direct?.ticker ?? null;
  const directHoldingName = direct?.name ?? null;

  let overlapHoldingCount = 0;
  let topOverlapHoldingName: string | null = null;
  let topOverlapWeightPct: number | null = null;
  let constituentsAnyUnavail = false;

  if (evidenceLoaded && candidateTicker) {
    for (const h of aggregated) {
      const ev = evidenceByTicker[h.ticker];
      // FIX r1-1 — evidence 미매칭 / co 부재 / status unavail 모두 정상 조회
      // 미완료로 카운트. 지시문 — "중복 없음" 은 모든 보유 ETF 정상 조회 +
      // 일치 0건일 때만.
      if (!ev) {
        constituentsAnyUnavail = true;
        continue;
      }
      const co = ev.constituents_overlap;
      if (!co) {
        constituentsAnyUnavail = true;
        continue;
      }
      if (
        co.status === "constituents_unavailable" ||
        co.status === "market_core_unavailable" ||
        co.status === "unavailable"
      ) {
        constituentsAnyUnavail = true;
        continue;
      }
      const found = (co.overlap_with_market_core ?? []).find(
        (it) => it.ticker === candidateTicker,
      );
      if (found) {
        overlapHoldingCount += 1;
        const w = found.weight_pct ?? 0;
        if (topOverlapWeightPct === null || w > topOverlapWeightPct) {
          topOverlapWeightPct = found.weight_pct ?? null;
          topOverlapHoldingName = h.name;
        }
      }
    }
  }

  if (!evidenceLoaded) {
    if (evidenceError) {
      return {
        kind: "unavailable",
        directHoldingTicker,
        directHoldingName,
        overlapHoldingCount: 0,
        topOverlapHoldingName: null,
        topOverlapWeightPct: null,
      };
    }
    if (direct) {
      return {
        kind: "direct_only",
        directHoldingTicker,
        directHoldingName,
        overlapHoldingCount: 0,
        topOverlapHoldingName: null,
        topOverlapWeightPct: null,
      };
    }
    return {
      kind: "unchecked",
      directHoldingTicker: null,
      directHoldingName: null,
      overlapHoldingCount: 0,
      topOverlapHoldingName: null,
      topOverlapWeightPct: null,
    };
  }

  if (direct && overlapHoldingCount > 0) {
    return {
      kind: "direct_and_overlap",
      directHoldingTicker,
      directHoldingName,
      overlapHoldingCount,
      topOverlapHoldingName,
      topOverlapWeightPct,
    };
  }
  if (direct) {
    return {
      kind: "direct_only",
      directHoldingTicker,
      directHoldingName,
      overlapHoldingCount: 0,
      topOverlapHoldingName: null,
      topOverlapWeightPct: null,
    };
  }
  if (overlapHoldingCount > 0) {
    return {
      kind: "overlap_only",
      directHoldingTicker: null,
      directHoldingName: null,
      overlapHoldingCount,
      topOverlapHoldingName,
      topOverlapWeightPct,
    };
  }
  if (constituentsAnyUnavail) {
    return {
      kind: "unavailable",
      directHoldingTicker: null,
      directHoldingName: null,
      overlapHoldingCount: 0,
      topOverlapHoldingName: null,
      topOverlapWeightPct: null,
    };
  }
  // 모든 보유 ETF overlap 정상 조회 + 일치 0건일 때만 진짜 "중복 없음".
  return {
    kind: "no_overlap",
    directHoldingTicker: null,
    directHoldingName: null,
    overlapHoldingCount: 0,
    topOverlapHoldingName: null,
    topOverlapWeightPct: null,
  };
}

export function exposureLabel(ex: ExposureSummary): string {
  switch (ex.kind) {
    case "direct_only":
      return "직접 보유";
    case "direct_and_overlap":
      return "직접 보유 · 구성종목도 겹침";
    case "overlap_only":
      return `구성종목 겹침 · 보유 ETF ${ex.overlapHoldingCount}개`;
    case "no_overlap":
      return "중복 없음";
    case "unchecked":
      return STATE_UNCHECKED;
    case "unavailable":
      return STATE_UNAVAIL;
  }
}

export function exposureColor(ex: ExposureSummary): string {
  switch (ex.kind) {
    case "direct_only":
    case "direct_and_overlap":
      return "var(--warn)";
    case "overlap_only":
      return "var(--warn)";
    case "no_overlap":
      return "var(--ok)";
    case "unchecked":
    case "unavailable":
    default:
      return "var(--muted)";
  }
}

export function exposureSortRank(kind: ExposureKind): number {
  switch (kind) {
    case "direct_and_overlap":
      return 5;
    case "direct_only":
      return 4;
    case "overlap_only":
      return 3;
    case "no_overlap":
      return 2;
    case "unchecked":
      return 1;
    case "unavailable":
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

export function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function returnColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return "var(--muted)";
  return value >= 0 ? "var(--ok)" : "var(--danger)";
}
