// POC3-05 보유 ETF 확인 근거 — 순수 변환 헬퍼.
//
// 신규 계산/신규 API 0건. 기존 evidence(읽기 전용) 를 ticker 별로 조립만 한다.
//  - enriched (GET /holdings/enriched): 평가액·평가 비중·손익률 — aggregateHoldingsByTicker 재사용.
//  - market-evidence (GET /holdings/market-evidence/latest): 5일·20일·KODEX200 대비 20일 + status.
// 설계 정정: 급락(falling) 신호는 자동 조회 GET 계약 부재로 이번 Step 제외(PLAN §1.3·§6).
// 위험 점수/등급/저장 rank/signal 을 만들지 않는다. "최근 5일 낮은 순" 은 표시 정렬일 뿐이다.

import type {
  EnrichedHolding,
  HoldingsMarketEvidenceItem,
} from "@/lib/api";
import {
  aggregateHoldingsByTicker,
  type AggregatedHolding,
} from "../holdings_compare/helpers";

// ticker 한 줄에 표시할 확인 근거 (읽기 전용).
export interface RiskEvidenceRow {
  ticker: string;
  name: string | null;
  // enriched (aggregateHoldingsByTicker)
  eval_amount: number | null;
  market_weight_pct: number | null;
  pnl_rate_pct: number | null;
  // market-evidence short_term_momentum (ticker 통합)
  return_5d_pct: number | null;
  return_20d_pct: number | null;
  excess_vs_kodex200_20d_pctp: number | null;
  // 데이터 상태 (Q4)
  need_check: boolean; // 자료 확인 필요
  // 정렬 유효성: status ok & 5일 값 not null 일 때만 5일 정렬·최대 3건 대상.
  five_d_sortable: boolean;
}

// evidence 를 ticker 별로 통합한다. 같은 ticker 가 여러 행(계좌)일 때 흐름 값이 서로 다르면
// 임의 선택하지 않고 "자료 확인 필요"(evidence_conflict=true) 로 표시한다(Q7).
interface EvidenceByTicker {
  status: string; // short_term_momentum.status (ok/partial/unavailable)
  return_5d_pct: number | null;
  return_20d_pct: number | null;
  excess_vs_kodex200_20d_pctp: number | null;
  evidence_conflict: boolean;
  present: boolean; // 이 ticker 의 evidence item 이 존재하는가
}

function numsEqual(a: number | null, b: number | null): boolean {
  if (a === null && b === null) return true;
  if (a === null || b === null) return false;
  return a === b;
}

function aggregateEvidenceByTicker(
  items: HoldingsMarketEvidenceItem[],
): Map<string, EvidenceByTicker> {
  const byTicker = new Map<string, HoldingsMarketEvidenceItem[]>();
  for (const it of items) {
    const arr = byTicker.get(it.ticker) ?? [];
    arr.push(it);
    byTicker.set(it.ticker, arr);
  }

  const out = new Map<string, EvidenceByTicker>();
  for (const [ticker, group] of byTicker) {
    const first = group[0].short_term_momentum;
    let conflict = false;
    // 같은 ticker 의 여러 계좌 행이 서로 다른 흐름 값/상태면 conflict.
    for (const g of group) {
      const s = g.short_term_momentum;
      if (
        s.status !== first.status ||
        !numsEqual(s.return_5d_pct, first.return_5d_pct) ||
        !numsEqual(s.return_20d_pct, first.return_20d_pct) ||
        !numsEqual(
          s.excess_vs_kodex200_20d_pctp,
          first.excess_vs_kodex200_20d_pctp,
        )
      ) {
        conflict = true;
        break;
      }
    }
    out.set(ticker, {
      status: first.status,
      return_5d_pct: first.return_5d_pct,
      return_20d_pct: first.return_20d_pct,
      excess_vs_kodex200_20d_pctp: first.excess_vs_kodex200_20d_pctp,
      evidence_conflict: conflict,
      present: true,
    });
  }
  return out;
}

// Q4 자료 확인 필요 판정 — 핵심 표시값만 (NAV·구성종목·topn 제외).
function computeNeedCheck(
  agg: AggregatedHolding,
  ev: EvidenceByTicker | undefined,
): boolean {
  // enriched 쪽 결측 (aggregateHoldingsByTicker 가 계좌 결측을 data_missing 으로 집계).
  if (agg.data_missing) return true;
  if (agg.eval_amount === null || agg.eval_partial_unavail) return true;
  if (agg.market_weight_pct === null) return true;
  if (agg.pnl_rate_pct === null) return true;
  // evidence 쪽 — not_loaded/미존재
  if (!ev || !ev.present) return true;
  if (ev.evidence_conflict) return true;
  if (ev.status === "partial" || ev.status === "unavailable") return true;
  // 세 흐름 값 중 하나라도 null → 확인 필요
  if (
    ev.return_5d_pct === null ||
    ev.return_20d_pct === null ||
    ev.excess_vs_kodex200_20d_pctp === null
  ) {
    return true;
  }
  return false;
}

export interface RiskEvidenceCoverage {
  total: number; // 보유 ticker 수
  ok: number; // 자료 확인 필요 아닌 수
  need_check: number; // 자료 확인 필요 수
}

export interface RiskEvidenceResult {
  rows: RiskEvidenceRow[];
  coverage: RiskEvidenceCoverage;
}

export function buildRiskEvidenceRows(
  enriched: EnrichedHolding[],
  evidenceItems: HoldingsMarketEvidenceItem[],
): RiskEvidenceResult {
  const aggs = aggregateHoldingsByTicker(enriched);
  const evByTicker = aggregateEvidenceByTicker(evidenceItems);

  const rows: RiskEvidenceRow[] = aggs.map((agg) => {
    const ev = evByTicker.get(agg.ticker);
    const need = computeNeedCheck(agg, ev);
    // partial 이어도 존재하는 수치는 그대로 보여준다(값은 표시, 상태는 need_check).
    const r5 = ev?.return_5d_pct ?? null;
    const evSortable =
      !!ev && ev.present && ev.status === "ok" && !ev.evidence_conflict && r5 !== null;
    return {
      ticker: agg.ticker,
      name: agg.name,
      eval_amount: agg.eval_amount,
      market_weight_pct: agg.market_weight_pct,
      pnl_rate_pct: agg.pnl_rate_pct,
      return_5d_pct: r5,
      return_20d_pct: ev?.return_20d_pct ?? null,
      excess_vs_kodex200_20d_pctp: ev?.excess_vs_kodex200_20d_pctp ?? null,
      need_check: need,
      five_d_sortable: evSortable,
    };
  });

  const need_check = rows.filter((r) => r.need_check).length;
  return {
    rows,
    coverage: { total: rows.length, ok: rows.length - need_check, need_check },
  };
}

// Q5: 최근 5일 낮은 순 최대 N — status ok & 5일 값 유효한 ticker만 오름차순,
// 동률은 ticker 오름차순. (중복 ticker 는 이미 통합됨.)
export function lowestFiveDayRows(
  rows: RiskEvidenceRow[],
  limit: number,
): RiskEvidenceRow[] {
  return rows
    .filter((r) => r.five_d_sortable && r.return_5d_pct !== null)
    .sort((a, b) => {
      const d = (a.return_5d_pct as number) - (b.return_5d_pct as number);
      if (d !== 0) return d;
      return a.ticker < b.ticker ? -1 : a.ticker > b.ticker ? 1 : 0;
    })
    .slice(0, limit);
}
