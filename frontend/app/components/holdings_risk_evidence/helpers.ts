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
  // POC5-UI-02 §11 — 선택 상세 '자료 확인 안내' 조립용(이미 받은 응답 · 기존 판정만).
  notes: string[]; // 그 종목 evidence_notes(여러 계좌면 같은 문구 한 번 · 들어온 순서)
  price_missing: boolean; // enriched 계좌 행 중 하나라도 시세 미확인
  calc_missing: boolean; // enriched 계좌 행 중 하나라도 평가 계산값 미확인
  evidence_conflict: boolean; // 같은 종목 계좌 간 단기 흐름 값 · 상태 불일치(기존 판정)
  // 단기 흐름 status = unavailable — 백엔드가 이때만 '단기 흐름은 데이터 부족으로 확인할 수 없습니다.'를
  // evidence_notes 에 붙인다(app/holdings_market_evidence.py :: _build_evidence_notes).
  flow_unavailable: boolean;
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
  notes: string[]; // 계좌 행들의 evidence_notes(같은 문구 한 번)
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
    const notes: string[] = [];
    for (const g of group) {
      for (const n of g.evidence_notes ?? []) {
        if (!notes.includes(n)) notes.push(n);
      }
    }
    out.set(ticker, {
      notes,
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
  // 계좌 행의 시세 · 계산 미확인(종목 통합 결과에는 둘이 합쳐져 있어 따로 모은다).
  const missingByTicker = new Map<string, { price: boolean; calc: boolean }>();
  for (const e of enriched) {
    const m = missingByTicker.get(e.ticker) ?? { price: false, calc: false };
    missingByTicker.set(e.ticker, {
      price: m.price || !!e.price_missing,
      calc: m.calc || !!e.calc_missing,
    });
  }

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
      notes: ev?.notes ?? [],
      price_missing: missingByTicker.get(agg.ticker)?.price ?? false,
      calc_missing: missingByTicker.get(agg.ticker)?.calc ?? false,
      evidence_conflict: ev?.evidence_conflict ?? false,
      flow_unavailable: ev?.status === "unavailable",
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

// POC5-UI-02 — 「확인 근거」 사용자 선택 정렬(POC3-05 설계 V2 229행 '사용자 선택 정렬' · UI-02 §3-1 · 판정 Q1 (a)).
// 화면에 보이는 원래 숫자(반올림 전)로 순서만 바꾼다. 값이 없는(null · 유한수 아님) 행은 맨 뒤 · 같은 값끼리와
// 값 없는 행끼리는 들어온 순서 그대로(안정 정렬) · 행을 빼지 않는다. 위험 순위가 아니다.
export type EvidenceSortKey = "weight" | "pnl_rate" | "ret5" | "ret20";

type SortField = keyof Pick<
  RiskEvidenceRow,
  | "market_weight_pct"
  | "pnl_rate_pct"
  | "return_5d_pct"
  | "return_20d_pct"
>;

// 키 → (행 칸 · 방향). desc = true 면 큰 값부터.
const SORT_SPEC: Record<EvidenceSortKey, { field: SortField; desc: boolean }> = {
  weight: { field: "market_weight_pct", desc: true },
  pnl_rate: { field: "pnl_rate_pct", desc: false },
  ret5: { field: "return_5d_pct", desc: false },
  ret20: { field: "return_20d_pct", desc: false },
};

// 화면 버튼 순서 · 문구.
export const EVIDENCE_SORT_OPTIONS: ReadonlyArray<[EvidenceSortKey, string]> = [
  ["weight", "평가 비중"],
  ["pnl_rate", "손익률"],
  ["ret5", "5일 변화"],
  ["ret20", "20일 변화"],
];
// 'KODEX200 대비 20일'(= 종목 20일 − KODEX200 20일 · 모든 종목에 같은 KODEX200 값)은 20일 변화와
// 순서가 같아 정렬 선택에서 뺐다(설계 §11-2 · 값 표시는 그대로).

export const DEFAULT_EVIDENCE_SORT: EvidenceSortKey = "ret5";

export function sortEvidenceRows(
  rows: RiskEvidenceRow[],
  key: EvidenceSortKey,
): RiskEvidenceRow[] {
  const { field, desc } = SORT_SPEC[key];
  return rows
    .map((row, index) => ({ row, index }))
    .sort((a, b) => {
      const va = a.row[field];
      const vb = b.row[field];
      const ha = va !== null && Number.isFinite(va);
      const hb = vb !== null && Number.isFinite(vb);
      if (!ha && !hb) return a.index - b.index;
      if (!ha) return 1;
      if (!hb) return -1;
      const d = desc ? (vb as number) - (va as number) : (va as number) - (vb as number);
      return d !== 0 ? d : a.index - b.index;
    })
    .map((x) => x.row);
}

// POC5-UI-02 §11-3 — 선택 종목 상세의 '자료 확인 안내'. 이미 받은 응답 · 기존 판정만 쓰고
// 날짜 · 건수 · 원인을 추측해 덧붙이지 않는다. 안내가 하나도 없으면 빈 배열(영역 없음).
// evidence_notes 에는 Market Discovery 후보 여부 · 20거래일 KODEX200 대비 · 구성종목 같은 일반 문구가
// 늘 들어 있어, 자료 확인 필요의 사유가 되는 것은 시세 · 계산 미확인 · 계좌 불일치 · 단기 흐름 unavailable
// 문구뿐이다. 이 넷이 없는데 자료 확인 필요면 사유 미제공 문구를 먼저 보이고 일반 문구는 그대로 둔다.
export const NO_REASON_TEXT = "자료 확인이 필요하지만 상세 사유 정보가 제공되지 않습니다.";

export function evidenceGuidance(row: RiskEvidenceRow): string[] {
  const out: string[] = [];
  const add = (t: string) => {
    if (!out.includes(t)) out.push(t);
  };
  if (row.price_missing) add("보유 시세를 확인할 수 없습니다.");
  if (row.calc_missing) add("보유 평가 계산값을 확인할 수 없습니다.");
  if (row.evidence_conflict) {
    add(
      "같은 종목의 계좌별 단기 흐름 값(상태 · 5일 · 20일 · KODEX200 대비)이 서로 다릅니다.",
    );
  }
  const hasReason =
    row.price_missing || row.calc_missing || row.evidence_conflict || row.flow_unavailable;
  if (row.need_check && !hasReason) add(NO_REASON_TEXT);
  for (const n of row.notes) add(n);
  return out;
}
