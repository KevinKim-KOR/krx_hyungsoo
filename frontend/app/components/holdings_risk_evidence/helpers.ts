// POC3-05 보유 ETF 확인 근거 — 순수 변환 헬퍼.
//
// 신규 계산/신규 API 0건. 기존 evidence(읽기 전용) 를 ticker 별로 조립만 한다.
//  - enriched (GET /holdings/enriched): 평가액·평가 비중·손익률 — aggregateHoldingsByTicker 재사용.
//  - market-evidence (GET /holdings/market-evidence/latest): 5일·20일·KODEX200 대비 20일 + status.
// 설계 정정: 급락(falling) 신호는 자동 조회 GET 계약 부재로 이번 Step 제외(PLAN §1.3·§6).
// 위험 점수/등급/저장 rank/signal 을 만들지 않는다. "최근 5일 낮은 순" 은 표시 정렬일 뿐이다.
// POC6-33(PLAN §3 · 판정 §3 · §4) — 선택 상세 글(방향 줄 · 주간 순위 줄 · 필요한 자료 안내 거르기 · 날짜 역할 ·
// 주요 편입 · 순자산가치(NAV) 묶음)을 만드는 순수 함수. 받은 응답 값만 쓰고 새 계산 · 조회는 없다.

import type {
  ConstituentsSummaryResponse,
  EnrichedHolding,
  HoldingsMarketEvidenceItem,
  HoldingsMarketEvidenceNavDiscount,
  HoldingsMarketEvidencePriceDates,
  HoldingsDeclineBand,
  PriceBasis,
} from "@/lib/api";
import type { CompareCondition, CompareSummary, HoldingLink } from "@/lib/api/etfCompare";
import type { QueryState } from "@/lib/api/queryCache";
import { BASIS_LABEL, filtersText, md } from "@/lib/etfCompare";
import {
  discountFlagClass,
  discountFlagLabel,
  discountPctText,
  discountRateColor,
  isKnownDiscountFlag,
  isKnownNavSource,
  isKnownNavStatus,
  navDateCell,
  navSourceLabel,
  navStatusLabel,
} from "@/lib/navLabels";
import {
  WINDOW_MISMATCH_OTHER_TEXT,
  dateMismatchText,
  windowMismatchText,
} from "@/lib/priceBasis";
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
  // 단기 흐름 status = unavailable — builder 는 이때 '단기 흐름은 데이터 부족으로 확인할 수 없습니다.'를
  // evidence_notes 에 붙인다(app/holdings_market_evidence.py :: _build_evidence_notes). POC5-09 의
  // 기준일 불일치 정정(app/pc_price_basis.py)도 unavailable 로 두며, 그 사유는 price_dates 로 보인다.
  flow_unavailable: boolean;
  // POC5-09 — 가격 흐름의 실제 계산 기준일 · 비교 기간 · 현재 비교 가능성(첫 계좌 항목 · 종목 단위 값).
  price_dates: HoldingsMarketEvidencePriceDates | null;
  // POC5-13 — PC 20저장일 하락 구간(첫 계좌 항목 · 계좌 간 흐름 값이 다르면 null = 판정하지 않음).
  decline_band: HoldingsDeclineBand | null;
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
  price_dates: HoldingsMarketEvidencePriceDates | null;
  decline_band: HoldingsDeclineBand | null;
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
      price_dates: group[0].price_dates ?? null,
      decline_band: group[0].decline_band ?? null,
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
      price_dates: ev?.price_dates ?? null,
      decline_band: ev && !ev.evidence_conflict ? ev.decline_band : null,
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

// 화면 버튼 순서 · 문구(POC6-33 판정 Q47 — 5 · 20 은 '저장일').
export const EVIDENCE_SORT_OPTIONS: ReadonlyArray<[EvidenceSortKey, string]> = [
  ["weight", "평가 비중"],
  ["pnl_rate", "손익률"],
  ["ret5", "5저장일 변화"],
  ["ret20", "20저장일 변화"],
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
// POC5-09 — 가격 흐름 기준일 · 비교 기간 불일치(실제 날짜)를 맨 위 사유로 보인다(판정 §9-4-2).
export const NO_REASON_TEXT = "자료 확인이 필요하지만 상세 사유 정보가 제공되지 않습니다.";

export function evidenceGuidance(
  row: RiskEvidenceRow,
  basis: PriceBasis | null = null,
): string[] {
  const out: string[] = [];
  const add = (t: string) => {
    if (!out.includes(t)) out.push(t);
  };
  const pd = row.price_dates;
  const ref = basis?.reference_date ?? null;
  if (pd?.comparison === "date_mismatch") add(dateMismatchText(pd.end_date, ref));
  if (pd?.comparison === "window_mismatch") {
    const b20 = basis?.kodex200_start_date_20d ?? null;
    const b5 = basis?.kodex200_start_date_5d ?? null;
    if (pd.start_date_20d !== b20) {
      add(windowMismatchText(20, pd.start_date_20d, pd.end_date, b20, ref));
    }
    if (pd.start_date_5d !== b5) {
      add(windowMismatchText(5, pd.start_date_5d, pd.end_date, b5, ref));
    }
    if (pd.start_date_20d === b20 && pd.start_date_5d === b5) add(WINDOW_MISMATCH_OTHER_TEXT);
  }
  const priceReason =
    pd?.comparison === "date_mismatch" || pd?.comparison === "window_mismatch";
  if (row.price_missing) add("보유 시세를 확인할 수 없습니다.");
  if (row.calc_missing) add("보유 평가 계산값을 확인할 수 없습니다.");
  if (row.evidence_conflict) {
    add(
      "같은 종목의 계좌별 단기 흐름 값(상태 · 5저장일 · 20저장일 · KODEX 200 대비)이 서로 다릅니다.",
    );
  }
  const hasReason =
    priceReason ||
    row.price_missing ||
    row.calc_missing ||
    row.evidence_conflict ||
    row.flow_unavailable;
  if (row.need_check && !hasReason) add(NO_REASON_TEXT);
  for (const n of row.notes) if (!isFilteredNote(n)) add(n);
  return out;
}

// POC6-33(판정 Q23 · PLAN E6 · I-3) — 공유 builder 안내(app/holdings_market_evidence.py _build_evidence_notes ·
// PC 사본 app/pc_price_basis.py)에서 이 화면이 거르는 문장. builder · PUSH · 초안 문장은 그대로 둔다.
// - 옛 'Market Discovery' 후보 네 문장 · 20거래일 KODEX200 대비 차이(방향 줄 · 세 묶음과 같은 값)는 앞부분으로 거른다.
// - 'NAV / 괴리율 확인이 필요합니다.'(NAV 묶음의 괴리 표시와 같은 사실) · 범위 없는 구성 중복 두 문장 · 기술 낱말
//   ('캐시' · 'source')이 든 자료 부족 세 문장(같은 상세의 구성 줄 · NAV 묶음이 쉬운 한국어로 보임)은 통째로 거른다.
// - 자료 부족 안내 '단기 흐름은 데이터 부족으로 확인할 수 없습니다.'와 그 밖의 문장은 거르지 않는다.
export const FILTERED_NOTE_PREFIXES: readonly string[] = [
  "현재 Market Discovery ",
  "20거래일 KODEX200 대비 단기 흐름 차이 ",
];
export const FILTERED_NOTES: readonly string[] = [
  "NAV / 괴리율 확인이 필요합니다.",
  "구성종목 기준 현재 후보군의 반복 핵심 종목과 일부 겹칩니다.",
  "구성종목 기준 현재 후보군의 반복 핵심 종목과 겹치는 항목이 없습니다.",
  "구성종목 데이터가 캐시에 없어 비교할 수 없습니다.",
  "현재 후보군의 구성종목 데이터를 확인할 수 없습니다.",
  "NAV / 괴리율은 source 미연동으로 확인할 수 없습니다.",
];

export function isFilteredNote(note: string): boolean {
  return FILTERED_NOTES.includes(note) || FILTERED_NOTE_PREFIXES.some((p) => note.startsWith(p));
}

// ── POC6-33 선택 상세 ① 방향 줄(판정 Q34 · Q37 · Q50 · PLAN E4 · I-14) ─────────────────────────────
// 보이는 값(소수 둘째 자리)이 0.00 이면 '변화 없음'(부호 없음 · −0.004 도 같음). 값 없음 = 기존 '자료 확인 필요'.
// KODEX 200 대비 값은 근거 응답 값(row.excess_vs_kodex200_20d_pctp)만 쓴다(주간 요약 응답 값은 쓰지 않음 · Q50).
export function shownValue(v: number | null): number | null {
  if (v === null || !Number.isFinite(v)) return null;
  return Number(v.toFixed(2)) || 0;
}

export function directionText(v: number | null): string {
  const r = shownValue(v);
  if (r === null) return "자료 확인 필요";
  if (r === 0) return "0.00%(변화 없음)";
  return r > 0 ? `+${r.toFixed(2)}%(올랐음)` : `${r.toFixed(2)}%(내렸음)`;
}

export function diffText(v: number | null): string {
  const r = shownValue(v);
  if (r === null) return "자료 확인 필요";
  if (r === 0) return "0.00%p";
  return `${r > 0 ? "+" : ""}${r.toFixed(2)}%p`;
}

// ── POC6-33 선택 상세 ② 주간 순위 줄(판정 Q22 · Q24 · Q33 · Q49 · Q52 · PLAN E5 · I-7 · I-8 · I-12) ─────
// 「주간 ETF 점검」 목록과 같은 인자(app/weekly_review.py BASIS · FILTERS = 1개월 · 인버스 · 레버리지 · 합성 · 선물 제외)로
// GET /market/etf-compare/summary 를 한 번 읽는다(상위 30 = 서버 LIST_N). 화면 글의 조건 · 기간은 응답 값을 쓴다.
export const WEEKLY_CHECK_CONDITION: CompareCondition = {
  basis: "one_month",
  filters: {
    exclude_inverse: true,
    exclude_leveraged: true,
    exclude_synthetic: true,
    exclude_futures: true,
  },
};

export const WEEKLY_RANK_LOADING = "주간 순위 불러오는 중...";
export const WEEKLY_RANK_FAILED = "자료 확인 불가 — 주간 순위 조회 실패";
export const STOCK_RANK_TEXT = "ETF 순위 대상 아님(개별 주식)";
export const STOCK_NA_TEXT = "NAV·ETF 구성종목 해당 없음(개별 주식)";

// 요약이 목록을 만들지 못한 이유(응답 status · 「ETF 비교하기」 SummaryStatus 와 같은 갈래).
const SUMMARY_NOT_OK_TEXT: Record<string, string> = {
  missing: "시장 자료 파일 없음",
  empty: "저장 가격 없음",
  invalid: "시장 자료를 읽지 못함",
  no_common_period: "KODEX 200 저장 가격으로 같은 기간을 정하지 못함",
};

export interface WeeklyRankView {
  main: string;
  // 그 조회의 조건 · 실제 기간(요약을 받았을 때만 · 개별 주식은 없음).
  basis: string | null;
  // 개별 주식이 요약 응답으로 확인됨(is_stock · out_reason 'stock') — 구성 · NAV 대신 '해당 없음' 한 줄.
  stock: boolean;
}

// 순위 · 순위권 밖 줄에만 끝 가격 상태를 붙인다(I-7 · 마감 뒤 저장 · 값 없음은 붙이지 않음 · 기존 낱말).
export function endStateSuffix(link: HoldingLink): string {
  const st = link.end_price?.state;
  if (st === "intraday") return " · 장중 저장값 기준";
  if (st === "unknown") return " · 마감값 확인 필요";
  return "";
}

export function weeklyRankView(q: QueryState<CompareSummary>, ticker: string): WeeklyRankView {
  if (q.phase === "idle" || q.phase === "loading") {
    return { main: WEEKLY_RANK_LOADING, basis: null, stock: false };
  }
  if (q.phase === "error") return { main: WEEKLY_RANK_FAILED, basis: null, stock: false };
  // 다시 읽기 실패로 이전 성공값만 남은 상태(stale) — 이전 순위를 지금 순위로 보이지 않는다(검증자 r1 F1).
  if (q.stale) return { main: WEEKLY_RANK_FAILED, basis: null, stock: false };
  const s = q.data;
  if (s.status !== "ok") {
    const why = SUMMARY_NOT_OK_TEXT[s.status] ?? "주간 순위 목록을 만들지 못함";
    return { main: `자료 확인 불가 — ${why}`, basis: null, stock: false };
  }
  // POC6-33 RESULT 판정 §1 — 순위 = 고른 기간의 가격 수익률 하나('1개월 수익률 상위 30'). 기간 이름은 응답 basis 값.
  // 목록 정렬(5저장일 변화 등) · 구성종목 중복의 후보 목록(상위 10개)과 이름으로 구별한다.
  const listName = `${BASIS_LABEL[s.basis]} 수익률 상위 ${s.n}`;
  const filters = filtersText(s.filters);
  const basis =
    `「주간 ETF 점검」과 같은 조회 · ${listName} · ` +
    `${md(s.period.start)} → ${md(s.period.end)} · ${filters}`;
  const link = s.holdings.items.find((h) => h.ticker === ticker) ?? null;
  if (!link) {
    const why =
      s.holdings.status === "error" ? "주간 순위의 보유 목록을 읽지 못함" : "주간 순위 자료에 이 종목 없음";
    return { main: `자료 확인 불가 — ${why}`, basis, stock: false };
  }
  if (link.is_stock || link.out_reason === "stock") {
    return { main: STOCK_RANK_TEXT, basis: null, stock: true };
  }
  if (link.in_population) {
    const start = link.basis_return?.start ?? s.period.start;
    const end = link.basis_return?.end ?? s.period.end;
    const period = `${md(start)} → ${md(end)}`;
    const suffix = endStateSuffix(link);
    if (link.top_rank != null) {
      return {
        main: `${listName} 중 ${link.top_rank}위 · ${period} · ${filters}${suffix}`,
        basis,
        stock: false,
      };
    }
    // 모집단 안 · 상위 밖(하위 30 포함 · Q24).
    return { main: `순위권 밖 · ${listName} 밖 · ${period}${suffix}`, basis, stock: false };
  }
  if (link.out_reason === "filter_excluded") {
    return { main: `규칙상 제외 — ${filters} 조건 · 가격 · 손익 근거는 아래 그대로`, basis, stock: false };
  }
  if (link.out_reason === "no_price") {
    return { main: "자료 확인 불가 — 저장 가격 없음", basis, stock: false };
  }
  if (link.out_reason === "period_differs") {
    return { main: "자료 확인 불가 — 같은 기간 수익률을 구하지 못함", basis, stock: false };
  }
  return { main: "자료 확인 불가 — 주간 순위 자료에 이 종목 없음", basis, stock: false };
}

// ── POC6-33 선택 상세 ④ 아래 날짜 역할(판정 Q35 · PLAN E9) — 날짜는 응답 값만(코드에 두지 않음) ─────────
export function dateRoleLines(
  row: RiskEvidenceRow,
  item: HoldingsMarketEvidenceItem | null,
): string[] {
  const out: string[] = [];
  const pd = row.price_dates;
  if (pd && pd.comparison !== "date_mismatch" && pd.start_date_20d && pd.end_date) {
    out.push(
      `20저장일 수익률 = 시작 종가 ${md(pd.start_date_20d)} → 끝 종가 ${md(pd.end_date)}(종가 21개 · 변화 20구간)`,
    );
  }
  const pts = item?.volume_trend?.points ?? [];
  if (pts.length > 0) {
    out.push(
      `[세부 흐름 보기] 차트 = 표시 기간 ${md(pts[0].date)} ~ ${md(pts[pts.length - 1].date)} · 최근 ${pts.length}개 저장일`,
    );
  }
  const sv = item?.stored_volume;
  if (sv && sv.status !== "no_price_data" && sv.window_date_count > 0 && sv.window_start_date && sv.window_end_date) {
    out.push(`거래량 평균 = 비교 구간 ${md(sv.window_start_date)} ~ ${md(sv.window_end_date)}`);
  }
  return out;
}

// ── POC6-33 선택 상세 ⑥ 주요 편입(판정 Q27 · PLAN E8) — GET /market/constituents/summary 한 ETF 응답 ─────────
// 상태 글은 서버 state_label 그대로(미수집 · 원천 기준일 미확인 · 상위 N행만 확인 · 전체 확인 · 구성 자료를 읽지 못함).
// 기준일 = 이 응답의 구성 기준일(겹침 비교의 구성 기준일과 다를 수 있어 따로 붙인다).
export function mainHoldingsText(r: ConstituentsSummaryResponse): { head: string; stocks: string | null } {
  if (r.status === "missing") return { head: "구성 자료 확인 불가 — 시장 자료 파일 없음", stocks: null };
  if (r.status === "error" || r.state === "error") return { head: "구성 자료를 읽지 못함", stocks: null };
  if (r.state === "not_collected") return { head: "미수집 — 저장된 구성 자료 없음", stocks: null };
  const head = `구성 기준일 ${md(r.asof ?? null)} · ${r.state_label ?? "상태 확인 필요"} · 저장 ${r.stored_rows ?? 0}행`;
  const top = r.top_stocks ?? [];
  const stocks = top.length
    ? top
        .map((t) => `${t.name ?? "이름 확인 불가"} ${t.weight_pct != null ? `${t.weight_pct.toFixed(1)}%` : "비중 확인 불가"}`)
        .join(" · ")
    : null;
  return { head, stocks };
}

// ── POC6-33 선택 상세 ⑥ 구성종목 중복(판정 Q25 · Q26 · Q51 · PLAN E7 · I-4) ─────────────────────────────
// 근거 응답에는 실제 비교에 쓴 구성 기준일 · 행 수가 없다(반환 = status + 겹침 목록) → '비교 범위 확인 불가'를 머리로 두고
// '중복 없음' · 겹침 건수 · 비율은 보이지 않는다. 찾은 겹침 종목은 그 자체로 확인된 사실이라 이름 · 이 ETF 편입 비중만 보인다.
// 실제 비교 규칙(builder): 보유 ETF 최신 구성 상위 10행 ↔ 후보 가운데 2곳 이상의 구성 상위 10행에 함께 나온 종목(반복 핵심 종목)
// (app/holdings_market_evidence.py _build_constituents_overlap · _build_market_core_lookup → app/etf_constituents_analysis.py
// compute_repeated_core_holdings min_appears=2 · DEFAULT_TOP_K_FOR_OVERLAP=10). 후보 한 곳에만 있는 종목은 비교 대상이 아니다.
export const OVERLAP_SCOPE_UNKNOWN = "비교 범위 확인 불가";
export const OVERLAP_CAP_TEXT =
  "보유 ETF 구성 상위 10행을, 후보 가운데 2곳 이상의 구성 상위 10행에 함께 나온 종목(반복 핵심 종목)과 비교 · 상위 10행 = 비교 상한 · 실제 비교에 쓴 구성 기준일 · 행 수는 이 응답에 없음";
export const OVERLAP_STATUS_TEXT: Record<string, string> = {
  constituents_unavailable: "구성종목 확인 불가 — 이 ETF 의 저장 구성 자료 없음",
  market_core_unavailable: "구성종목 확인 불가 — 비교 후보의 구성 자료 없음",
};
export const OVERLAP_UNAVAILABLE_TEXT = "구성종목 확인 불가";
// RESULT 판정 §2-1(E7 · I-4) — 비교에 쓴 후보 목록은 주간 순위(수익률 상위 30)와 다른 별도 목록이다. 목록의 기간 ·
// 제외 조건은 그 목록의 기준(topn_basis · topnBasisText)을 붙인다.
export const OVERLAP_LIST_PREFIX = "비교 후보 목록(주간 순위 목록과 별도): ";

// 찾은 겹침 한 종목 — 비중은 보유 ETF 자신의 구성 행 비중(builder _build_constituents_overlap 의 r.weight_pct)이라
// '이 ETF 편입 비중'으로 뜻을 붙인다. 비중이 없으면 이름만.
export function overlapFoundText(x: {
  ticker: string | null;
  name: string | null;
  weight_pct: number | null;
}): string {
  const label = x.name ?? x.ticker ?? "-";
  return x.weight_pct != null ? `${label} · 이 ETF 편입 비중 ${x.weight_pct.toFixed(2)}%` : label;
}

// ── POC6-33 선택 상세 ⑦ 순자산가치(NAV) · 괴리율 묶음(판정 Q3 · Q36 · Q38 ~ Q40 · Q53 · Q54 · PLAN E10 · I-9 · I-11) ──
// 시장가 · NAV · 괴리율(부호) · 기준일 · 출처 · 수집 상태를 늘 보인다(값 없음 '-'). 사용자용 글자는 lib/navLabels(「데이터 상태」와
// 같은 사전). NAV 저장 행이 없는 ETF 의 builder 표지 source 'not_integrated' 는 출처가 아니라 '행 없음'이라 '-'(I-11 ④).
// 받은 안내 원문(message) · 사전 밖 원문은 [자세히] 안에만.
export const NAV_NO_ROW_SOURCE = "not_integrated";

export interface NavCell {
  label: string;
  value: string;
  color?: string;
  flag?: string | null;
  flagClass?: string;
}

function fmtWon(v: number | null): string {
  return v != null && Number.isFinite(v) ? Math.round(v).toLocaleString("ko-KR") : "-";
}

export function navCells(nav: HoldingsMarketEvidenceNavDiscount): NavCell[] {
  const source = nav.source === NAV_NO_ROW_SOURCE ? null : nav.source;
  return [
    { label: "시장가", value: fmtWon(nav.market_price) },
    { label: "NAV", value: fmtWon(nav.nav) },
    {
      label: "괴리율",
      value: discountPctText(nav.discount_rate_pct),
      color: discountRateColor(nav.discount_rate_pct),
      flag: discountFlagLabel(nav.flag),
      flagClass: discountFlagClass(nav.flag),
    },
    { label: "기준일", value: navDateCell(nav.status, nav.asof) },
    { label: "출처", value: navSourceLabel(source) },
    { label: "수집 상태", value: navStatusLabel(nav.status) },
  ];
}

export function navRawLines(nav: HoldingsMarketEvidenceNavDiscount): string[] {
  const out: string[] = [];
  if (nav.message) out.push(`받은 안내 원문: ${nav.message}`);
  if (!isKnownNavStatus(nav.status)) out.push(`수집 상태 원문: ${String(nav.status)}`);
  if (nav.source && nav.source !== NAV_NO_ROW_SOURCE && !isKnownNavSource(nav.source)) {
    out.push(`출처 원문: ${nav.source}`);
  }
  if (nav.flag && !isKnownDiscountFlag(nav.flag)) out.push(`괴리율 표시 원문: ${nav.flag}`);
  return out;
}

export const NAV_HELP: readonly string[] = [
  "NAV 는 순자산가치(ETF 가 담은 자산의 1주당 가치)입니다. 괴리율은 (시장가 − NAV) ÷ NAV × 100 이며, 양수는 그 기준 시점의 시장가가 NAV 보다 높았다는 뜻입니다.",
  "괴리율 절대값이 3% 이상이면 ‘괴리 확인 필요(3% 이상)’, 5% 이상이면 ‘괴리 주의(5% 이상)’를 붙입니다. 자료 확인용 표시이며 사고팔기 판단이 아닙니다.",
  "수집 상태: ‘수집됨’ = 그 기준일에 NAV · 시장가 · 괴리율을 받음 · ‘이전 목록 재사용’ = 그날 조회에 실패해 이전에 받은 목록을 다시 저장함(날짜 = 재저장일) · ‘확인 불가’ = 받지 못함.",
];
