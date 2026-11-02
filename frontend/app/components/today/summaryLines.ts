// POC6-16 — 「오늘의 투자 점검」 맨 위 「지금 확인할 내용」의 줄 · 「지금 할 일」 안내를 만드는 순수 함수
// (설계 V1 · PLAN 판정 2026-11-02 V1.1 §2 · §3 · §3-1 · §5).
//
// - 모든 문장은 이 화면이 이미 받은 응답과 기존 함수에서 만든다(새 점수 · 등급 · 합산 건수 · 재계산 없음).
//   시장 = KOSPI 카드와 같은 `/market/topn/latest` 시장 판정 · `/market/flow-context` 서버 문장 ·
//   보유 = 보유 위험 띠(`riskStateFromQueries`) · 후보 = 같은 목록 응답 · 자료 = 정비 항목(`collectMaintenance`) ·
//   연구 = POC6-15 `forwardConclusion`.
// - 줄마다 자기 응답 상태만 본다(한 줄 실패가 다른 줄을 가리지 않음). 다시 읽기에 실패해 이전 값을 보이면
//   그 값을 받은 시각(공유 캐시 successAt)을 같이 적는다.
// - 「지금 할 일」은 기존 정비 점검이 알린 것만(새 임계값 · 클릭 이력 추정 없음). 해결 동선이 확인된
//   작업(시장 자료 갱신 · 보유 현재가 [업데이트] · 다시 읽기)만 안내하고 나머지는 정비 목록으로 보낸다.

import type { QueryState } from "@/lib/api/queryCache";
import type {
  EnrichedHoldingsResult,
  ForwardComparisonResponse,
  HoldingsMarketEvidenceResponse,
  MarketCandidate,
  MarketTopNResponse,
  NavDiscountLatestResponse,
  PriceSeriesResponse,
} from "@/lib/api";
import type { MarketFlowContext } from "@/lib/api/marketFlow";
import { kospiStatusView } from "@/lib/kospiStatus";
import type { MenuKey } from "../LeftSidebar";
import { kstText } from "../MLCardParts";
import { forwardConclusion } from "../ml_forward/forwardText";
import { PARTIAL_EVAL_TEXT, fmtShare } from "../holdings_risk_evidence/declineSummary";
import { FAILURE_TEXT, PARTIAL_JUDGE_TEXT, riskStateFromQueries } from "../holdings_risk_evidence/riskCombination";
import type { MaintenanceItem } from "./maintenanceQueue";
import { fmtKstDate, fmtPct, regimeLabelKo } from "./todayHelpers";

export const SCROLL_KOSPI = "tc-kospi-area";
export const SCROLL_MAINT = "tc-maint-area";

export type SummaryTone = "ok" | "warn" | "muted" | "bad" | "info";
export type SummaryTarget =
  | { kind: "menu"; key: MenuKey }
  | { kind: "scroll"; id: string }
  | { kind: "reload" };
export type SummaryAction = { label: string; target: SummaryTarget; primary: boolean };
export type SummaryRow = {
  id: "market" | "holdings" | "candidates" | "data" | "research";
  area: string;
  tone: SummaryTone;
  badge: string;
  text: string;
  // 결론 아래 보조 한 줄(서버가 준 둘째 문장 등 · 없으면 null)
  sub?: string | null;
  basis: string | null;
  staleNote: string | null;
  actions: SummaryAction[];
};
export type SummaryTask = {
  id: "market_refresh" | "holdings_price" | "read_failed" | "market_unknown";
  title: string;
  reasons: string[];
  doText: string;
  // 이 화면 버튼으로 해결되지 않는 경우(시장 목록 실패 = 브라우저 새로 고침) 버튼 없음(검토 지적 2)
  action: SummaryAction | null;
};

const menu = (label: string, key: MenuKey, primary: boolean): SummaryAction => ({
  label,
  target: { kind: "menu", key },
  primary,
});
const scroll = (label: string, id: string, primary: boolean): SummaryAction => ({
  label,
  target: { kind: "scroll", id },
  primary,
});

// 성공 시각(ms) → 'YYYY-MM-DD HH:MM:SS'(한국 시각). 없으면 '조회 시각 미확인'(판정 §4).
export function readTimeText(ms: number | undefined): string {
  if (typeof ms !== "number" || !Number.isFinite(ms)) return "조회 시각 미확인";
  return kstText(new Date(ms).toISOString()) ?? "조회 시각 미확인";
}

function staleOf(label: string, q: QueryState<unknown>): string | null {
  if (q.phase !== "success" || !q.stale) return null;
  return `${label}: 다시 읽기 실패 · ${readTimeText(q.successAt)}에 읽은 값을 표시 중`;
}

// 첫 조회부터 실패해 이전 값도 없는 원천(검증자 r1 F1 — 줄 안에서 빠지지 않게).
function failOf(label: string, q: QueryState<unknown>): string | null {
  return q.phase === "error" ? `${label}: 불러오지 못했습니다(이전 값 없음)` : null;
}

// 줄 아래 상태 메모(다시 읽기 실패 · 첫 조회 실패)를 한 줄로.
function joinStale(...notes: (string | null)[]): string | null {
  const xs = notes.filter((x): x is string => !!x);
  return xs.length ? xs.join(" / ") : null;
}

// ── 시장 흐름 ────────────────────────────────────────────────────────────────
export function marketRow(
  market: QueryState<MarketTopNResponse>,
  flow: QueryState<MarketFlowContext>,
  series?: QueryState<PriceSeriesResponse>,
): SummaryRow {
  const actions = [
    menu("시장 흐름 자세히", "market_discovery", true),
    scroll("KOSPI 차트 ↓", SCROLL_KOSPI, false),
  ];
  const flowText =
    flow.phase === "success"
      ? (flow.data.today_lines[0] ?? "수급 · 환율 · 유가 요약 문장이 없습니다")
      : flow.phase === "error"
        ? "수급 · 환율 · 유가 자료를 불러오지 못했습니다"
        : "수급 · 환율 · 유가 불러오는 중";
  // 서버 둘째 문장(최근 큰 변화 또는 확인 못 한 자료 · 판정 §5 — 일부 결측 구분)을 버리지 않는다(검토 지적 7).
  const flowSub = flow.phase === "success" ? (flow.data.today_lines[1] ?? null) : null;
  const stale = joinStale(
    staleOf("수급 · 환율 · 유가", flow),
    series ? staleOf("KOSPI 가격 흐름", series) : null,
    series ? failOf("KOSPI 가격 흐름", series) : null,
  );
  if (market.phase === "loading" || market.phase === "idle") {
    return { id: "market", area: "시장 흐름", tone: "muted", badge: "불러오는 중", text: flowText, sub: flowSub, basis: null, staleNote: stale, actions };
  }
  if (market.phase === "error") {
    return {
      id: "market",
      area: "시장 흐름",
      tone: "bad",
      badge: "불러오지 못함",
      text: `시장 판정 · KOSPI를 불러오지 못했습니다 · ${flowText}`,
      sub: flowSub,
      basis: "시장 판정 · 요즘 잘 오르는 ETF 목록은 [요약 다시 읽기]로 다시 계산하지 않습니다 — 브라우저를 새로 고치면 다시 읽습니다",
      staleNote: stale,
      actions,
    };
  }
  // KOSPI 카드 '기존 시장 판정' 줄과 같은 조건 · 같은 값(시장 배경 응답이 있으면 상태가 partial 이어도 그대로).
  const ctx = market.data.market_context ?? null;
  const usable = !!ctx;
  const regime = ctx ? regimeLabelKo(ctx.regime_code, ctx.regime_label) : null;
  const streak = ctx ? ctx.regime_streak : null;
  // 연속 일수가 없으면 KOSPI 카드처럼 '지속일 자료 없음'(검토 지적 10)
  const badge = !regime
    ? "시장 판정 확인 불가"
    : streak && streak.streak_days != null
      ? `${regime} · ${streak.streak_days}거래일째${streak.at_least ? " 이상" : ""}`
      : `${regime} · 지속일 자료 없음`;
  const kv = kospiStatusView(ctx?.kospi, market.phase);
  const kospiBasis = (!kv.loading ? kv.basisLine : null) ?? "KOSPI 기준일 확인 불가";
  // 시장 판정 날짜 = KOSPI 카드 '기존 시장 판정' 줄과 같은 값(market_context.asof · POC5-11 'KODEX200 기준일').
  const kodexDate = usable && ctx?.asof ? `KODEX200 기준일 ${fmtKstDate(ctx.asof)}` : null;
  return {
    id: "market",
    area: "시장 흐름",
    tone: regime ? "info" : "muted",
    badge,
    text: `KODEX200 기준 시장 판정 · ${flowText}`,
    sub: flowSub,
    basis: [kospiBasis, kodexDate, "시장 판정은 이 화면을 처음 열 때 읽은 값(다시 읽기 제외)"].filter(Boolean).join(" · "),
    staleNote: stale,
    actions,
  };
}

// ── 보유 점검 ────────────────────────────────────────────────────────────────
export function holdingsRow(
  holdings: QueryState<EnrichedHoldingsResult>,
  evidence: QueryState<HoldingsMarketEvidenceResponse>,
): SummaryRow {
  const actions = [
    menu("확인 근거 보기", "holdings_evidence", true),
    menu("보유 현황 보기", "holdings", false),
  ];
  const stale = joinStale(staleOf("보유", holdings), staleOf("보유 근거", evidence));
  const risk = riskStateFromQueries(holdings, evidence);
  if (!risk) {
    return { id: "holdings", area: "보유 점검", tone: "muted", badge: "불러오는 중", text: "보유 · 보유 근거를 불러오는 중입니다", basis: null, staleNote: stale, actions };
  }
  const count =
    holdings.phase === "success" ? new Set(holdings.data.items.map((it) => it.ticker)).size : null;
  const ref = evidence.phase === "success" ? (evidence.data.price_basis?.reference_date ?? null) : null;
  const d0 = risk.summary;
  const basis = [
    count != null ? `보유 ${count}개` : null,
    ref ? `PC 저장 가격 기준일 ${ref}` : null,
    risk.regime ? `시장 국면(보유 근거 기준) ${risk.regime}` : null,
    // 보유 칸 띠의 판정 범위와 같은 문장(검토 지적 6)
    d0 ? `구간 판정 가능 ${d0.judgeable}/${d0.total}종목${risk.combo.partial ? ` · ${PARTIAL_JUDGE_TEXT}` : ""}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  if (risk.combo.holdings === "no_holdings") {
    return { id: "holdings", area: "보유 점검", tone: "muted", badge: risk.combo.text, text: "판정할 보유 종목이 없습니다", basis: basis || null, staleNote: stale, actions };
  }
  if (risk.failed) {
    return { id: "holdings", area: "보유 점검", tone: "bad", badge: "불러오지 못함", text: FAILURE_TEXT[risk.failed], basis: basis || null, staleNote: stale, actions };
  }
  const d = risk.summary;
  const text = d
    ? `PC 최근 20저장일 하락 구간 ${d.inBand}종목 · 보유 평가 비중 ${fmtShare(d.inBandShare)}` +
      (d.evalPartial && d.inBandShare !== null ? `(${PARTIAL_EVAL_TEXT})` : "") +
      " · 먼저 볼 보유는 아래 「보유 · 잘 오르는 ETF 자세히」"
    : "하락 구간 요약을 만들 수 없습니다";
  return { id: "holdings", area: "보유 점검", tone: "info", badge: risk.combo.text, text, basis: basis || null, staleNote: stale, actions };
}

// ── 잘 오르는 ETF(대시보드 고정 조건 목록 · 판정 §5 · 화면 글자에 '후보' 안 씀 = AC-7) ─────────────────────────
const BASIS_WORD: Record<string, string> = {
  daily: "일간 수익률",
  one_month: "1개월 수익률",
  three_month: "3개월 수익률",
};

export function candidateLabel(data: MarketTopNResponse): string {
  const word = BASIS_WORD[data.basis ?? ""] ?? `수익률(기준 ${data.basis ?? "미확인"})`;
  return `${word} 상위 ${data.candidates.length}개`;
}

// 종목별 실제 시작 · 끝일이 모두 같을 때만 하나의 기간(다르면 그 사실 · 판정 §5).
export function candidatePeriod(cands: MarketCandidate[]): string {
  if (cands.length === 0) return "기간 없음";
  const s = cands[0].selected_basis_start_date ?? null;
  const e = cands[0].selected_basis_end_date ?? null;
  const same = cands.every(
    (c) => (c.selected_basis_start_date ?? null) === s && (c.selected_basis_end_date ?? null) === e,
  );
  if (!same) return "종목별 계산 기간 다름(「요즘 잘 오르는 ETF」에서 확인)";
  return s && e ? `${s} ~ ${e}` : "계산 기간 확인 불가";
}

const FILTER_WORDS: [string, string][] = [
  ["exclude_inverse", "인버스"],
  ["exclude_leveraged", "레버리지"],
  ["exclude_synthetic", "합성"],
  ["exclude_futures", "선물"],
];

export function candidateConditions(data: MarketTopNResponse): string {
  const f = (data.filters ?? {}) as Record<string, unknown>;
  const ex = FILTER_WORDS.filter(([k]) => f[k] === true).map(([, w]) => w);
  const cap = typeof data.n === "number" ? `최대 ${data.n}개` : null;
  return [ex.length ? `${ex.join(" · ")} 제외` : "제외 조건 없음", cap].filter(Boolean).join(" · ");
}

export function candidatesRow(market: QueryState<MarketTopNResponse>): SummaryRow {
  const actions = [
    menu("요즘 잘 오르는 ETF", "market_discovery", true),
    menu("ETF 비교하기", "workbench", false),
  ];
  const base = { id: "candidates" as const, area: "잘 오르는 ETF", staleNote: null, actions };
  if (market.phase === "loading" || market.phase === "idle") {
    return { ...base, tone: "muted", badge: "불러오는 중", text: "요즘 잘 오르는 ETF 목록을 불러오는 중입니다", basis: null };
  }
  if (market.phase === "error") {
    return { ...base, tone: "bad", badge: "불러오지 못함", text: "요즘 잘 오르는 ETF 목록을 불러오지 못했습니다", basis: "브라우저를 새로 고치면 다시 읽습니다" };
  }
  const data = market.data;
  if (data.status !== "ok") {
    // 원시 진단(서버 오류 원문)은 요약에 옮기지 않는다 — 아래 구역과 같은 '확인 불가'(검토 지적 8a)
    return { ...base, tone: "muted", badge: "확인 불가", text: "요즘 잘 오르는 ETF 목록을 확인할 수 없습니다", basis: "브라우저를 새로 고치면 다시 읽습니다" };
  }
  const c = data.candidates;
  const basis = `${candidatePeriod(c)} · ${candidateConditions(data)} · 「요즘 잘 오르는 ETF」에서 고른 기간 · 정렬과 다를 수 있음`;
  if (c.length === 0) {
    return { ...base, tone: "muted", badge: candidateLabel(data), text: "조건에 맞는 ETF가 없습니다", basis };
  }
  const top = c[0];
  const ret = top.selected_return_pct;
  return {
    ...base,
    tone: "info",
    badge: candidateLabel(data),
    text:
      `1위 ${top.name ?? top.ticker} ${typeof ret === "number" ? fmtPct(ret) : "수익률 확인 불가"}` +
      (c.length > 1 ? ` 외 ${c.length - 1}개 · 상위 ${Math.min(3, c.length)}개는 아래` : ""),
    basis,
  };
}

// ── 자료 확인(정비 항목 · 투자 위험 표시 아님) ────────────────────────────────
// unknownSources = 정비 점검에 쓰는 원천 중 첫 조회에 실패해 정비 항목에 나타나지 않는 것(보유 · 시장 목록).
//   이것이 있으면 빈 정비 목록을 '갱신 필요 없음'으로 정리하지 않는다(검증자 r1 F1).
export function dataRow(
  items: MaintenanceItem[],
  loading: boolean,
  hasTasks: boolean,
  nav?: QueryState<NavDiscountLatestResponse>,
  evidence?: QueryState<HoldingsMarketEvidenceResponse>,
  unknownSources: string[] = [],
): SummaryRow {
  const actions = [scroll("자료 최신화 목록 ↓", SCROLL_MAINT, false)];
  // 정비 항목을 만든 원천 중 다시 읽기에 실패해 이전 값을 쓰는 것(그 값을 받은 시각 · 검토 지적 3)
  const stale = joinStale(
    nav ? staleOf("ETF 기준가", nav) : null,
    evidence ? staleOf("보유 근거", evidence) : null,
  );
  if (loading) {
    return { id: "data", area: "자료 확인", tone: "muted", badge: "확인 중", text: "자료 상태를 확인하는 중입니다", basis: null, staleNote: stale, actions };
  }
  const tail = hasTasks ? " · 해야 할 작업은 맨 위 「지금 할 일」" : "";
  const notChecked = unknownSources.length ? `${unknownSources.join(" · ")} 자료를 불러오지 못해 확인하지 못했습니다` : null;
  if (items.length === 0 && !notChecked) {
    return { id: "data", area: "자료 확인", tone: "ok", badge: "갱신 필요 없음", text: "기존 자료 점검에서 갱신이 필요한 항목이 없습니다", basis: null, staleNote: stale, actions };
  }
  if (items.length === 0) {
    return {
      id: "data",
      area: "자료 확인",
      tone: "bad",
      badge: "일부 확인 못함",
      text: notChecked!,
      basis: "갱신이 필요한지 알 수 없습니다(오래됐다는 뜻은 아님) · 투자 위험 표시가 아닙니다" + tail,
      staleNote: stale,
      actions,
    };
  }
  const head = items.slice(0, 2).map((it) => it.text);
  // 불러오지 못한 항목은 '오래됨'과 다르다(판정 §3-1 · 검토 지적 5). '함께 있음'은 오래됨 · 없음이 실제로 확인된
  //   항목(stale)이 하나 이상 있을 때만 — 확인 못한 원천(notChecked)은 오래됨의 근거가 아니다(검증자 r2 F3).
  const unknown = items.filter((it) => it.task === "read_failed" || it.task === "market_unknown").length;
  const confirmed = items.length - unknown; // 오래됨 · 없음이 실제로 확인된 항목 수
  const meaning =
    confirmed === 0
      ? "자료를 불러오지 못한 항목입니다(오래됐다는 뜻은 아님) · 투자 위험 표시가 아닙니다"
      : unknown > 0 || notChecked
        ? "오래됐거나 없는 자료와 불러오지 못한 자료가 함께 있습니다 · 투자 위험 표시가 아닙니다"
        : "자료가 오래됐거나 없다는 뜻이며 투자 위험 표시가 아닙니다";
  return {
    id: "data",
    area: "자료 확인",
    tone: "warn",
    badge: `자료 최신화 필요 ${items.length}건`,
    text: head.join(" · ") + (items.length > 2 ? ` 외 ${items.length - 2}건` : "") + (notChecked ? ` · ${notChecked}` : ""),
    basis: meaning + tail,
    staleNote: stale,
    actions,
  };
}

// ── 연구(예측과 결과 비교 · 투자 판단 신호 아님) ─────────────────────────────
// 예측 기준일(= 예측한 날) — 응답의 공개 확인된 기준일 목록 · 비교 보고에 들어간 기준일 범위(다르면 따로 · 검증자 r1 F2).
//   보고 만든 시각과 다르다. 두 범위를 하나로 합치지 않는다.
export function researchDates(d: ForwardComparisonResponse): string | null {
  const ds = (d.dates ?? []).map((x) => x.D).filter((x): x is string => typeof x === "string").sort();
  const parts: string[] = [];
  if (ds.length > 0) {
    parts.push(`예측이 기록된 기준일 ${ds.length}개(${ds[0]}${ds.length > 1 ? ` ~ ${ds[ds.length - 1]}` : ""})`);
  } else if (d.status === "OK" || d.status === "NO_RECORDS") {
    parts.push("예측이 기록된 기준일 없음");
  }
  const p = d.report?.predicted_dates;
  if (p && p.count > 0 && p.first && p.last) {
    const same = ds.length === p.count && ds[0] === p.first && ds[ds.length - 1] === p.last;
    if (!same) parts.push(`비교 보고에 들어간 기준일 ${p.count}개(${p.first} ~ ${p.last})`);
  }
  return parts.length ? parts.join(" · ") : null;
}

export function researchRow(forward: QueryState<ForwardComparisonResponse>): SummaryRow {
  const actions = [menu("예측과 결과 비교", "ml", true)];
  const fixed = "연구용 · 운영에 쓰지 않음 · 기준일 뒤 20거래일 자료가 확보되면 결과를 비교합니다";
  const dates = forward.phase === "success" ? researchDates(forward.data) : null;
  const basis = dates ? `${dates} · ${fixed}` : fixed;
  if (forward.phase === "loading" || forward.phase === "idle") {
    return { id: "research", area: "연구", tone: "muted", badge: "불러오는 중", text: "예측과 결과 비교 기록을 불러오는 중입니다", basis, staleNote: null, actions };
  }
  if (forward.phase === "error") {
    return { id: "research", area: "연구", tone: "bad", badge: "불러오지 못함", text: "예측과 결과 비교 기록을 불러오지 못했습니다", basis, staleNote: null, actions };
  }
  const c = forwardConclusion(forward.data);
  // POC6-15 결론 문장 그대로 — 단 '아래 안내'는 「예측과 결과 비교」 화면에만 있다(검토 지적 9)
  const text = c.text.replace("아래 안내를 먼저 확인해 주세요", "「예측과 결과 비교」에서 안내를 확인해 주세요");
  return {
    id: "research",
    area: "연구",
    tone: c.tone,
    badge: c.label,
    text: `예측과 결과 비교 · ${text}`,
    basis,
    staleNote: staleOf("연구", forward),
    actions,
  };
}

// ── 지금 할 일(판정 §3-1) ────────────────────────────────────────────────────
export function summaryTasks(
  items: MaintenanceItem[],
  loading: boolean,
  market: QueryState<MarketTopNResponse>,
  holdings: QueryState<EnrichedHoldingsResult>,
  flow: QueryState<MarketFlowContext>,
  series?: QueryState<PriceSeriesResponse>,
  forward?: QueryState<ForwardComparisonResponse>,
): SummaryTask[] {
  if (loading) return [];
  const tasks: SummaryTask[] = [];
  const marketItems = items.filter((it) => it.task === "market_refresh");
  if (marketItems.length > 0) {
    const ctx = market.phase === "success" ? market.data.market_context : null;
    const kospiDate = ctx?.kospi?.as_of_date ?? null;
    const etfDate = market.phase === "success" ? (market.data.asof ?? null) : null;
    const dates = [kospiDate ? `KOSPI ${kospiDate}` : null, etfDate ? `ETF 가격 ${etfDate}` : null]
      .filter(Boolean)
      .join(" · ");
    tasks.push({
      id: "market_refresh",
      title: "시장 자료 갱신이 필요합니다.",
      reasons: [dates ? `지금 PC에 저장된 시장 자료: ${dates}` : null, ...marketItems.map((it) => it.text)].filter(
        (x): x is string => !!x,
      ),
      doText: "이동 후 [최신 시장 데이터 갱신]을 눌러 주세요. 갱신해도 다른 자료 항목이 모두 해결되는 것은 아닙니다.",
      action: menu("시장 자료 갱신 화면", "market_discovery", true),
    });
  }
  const priceItems = items.filter((it) => it.task === "holdings_price");
  if (priceItems.length > 0) {
    tasks.push({
      id: "holdings_price",
      title: "보유 종목 현재가를 다시 받아야 합니다.",
      reasons: priceItems.map((it) => it.text),
      doText: "아래 「자료 최신화 필요」의 [업데이트]를 눌러 주세요.",
      action: scroll("업데이트 위치로 ↓", SCROLL_MAINT, true),
    });
  }
  // [요약 다시 읽기]로 다시 읽는 원천의 실패만 '다시 읽어 주세요'(검토 지적 2)
  const unknown = items.filter((it) => it.task === "read_failed").map((it) => it.text);
  if (holdings.phase === "error") unknown.push("보유 자료를 불러오지 못했습니다");
  if (flow.phase === "error") unknown.push("수급 · 환율 · 유가 자료를 불러오지 못했습니다");
  // 다시 읽기 대상의 나머지 첫 조회 실패도 같은 안내(검증자 r1 F1)
  if (series?.phase === "error") unknown.push("KOSPI 가격 흐름 자료를 불러오지 못했습니다");
  if (forward?.phase === "error") unknown.push("예측과 결과 비교 기록을 불러오지 못했습니다");
  if (unknown.length > 0) {
    tasks.push({
      id: "read_failed",
      title: "자료 상태를 확인하지 못했습니다. 다시 읽어 주세요.",
      reasons: unknown,
      doText: "자료가 오래됐다는 뜻은 아닙니다. 다시 읽어도 같으면 서버 상태를 확인해야 합니다.",
      action: { label: "요약 다시 읽기", target: { kind: "reload" }, primary: false },
    });
  }
  // 시장 판정 · 요즘 잘 오르는 ETF 목록은 다시 읽기 대상이 아니다(판정 §2) — 버튼 없이 새로 고침 안내
  const marketUnknown = items.filter((it) => it.task === "market_unknown").map((it) => it.text);
  if (market.phase === "error") marketUnknown.unshift("시장 판정 · 요즘 잘 오르는 ETF 목록을 불러오지 못했습니다");
  if (marketUnknown.length > 0) {
    tasks.push({
      id: "market_unknown",
      title: "시장 판정 · 요즘 잘 오르는 ETF 목록을 확인하지 못했습니다.",
      reasons: marketUnknown,
      doText: "브라우저를 새로 고치면 다시 읽습니다([요약 다시 읽기]는 이 목록을 다시 읽지 않습니다). 오래됐다는 뜻은 아닙니다.",
      action: null,
    });
  }
  return tasks;
}

// 머리말 — 이 화면이 값을 읽은 시각(값마다 다름 · 가장 이른 ~ 가장 늦은 · 상단 하나로 덮지 않음 · 판정 §4).
export function readRangeText(times: (number | undefined)[]): string {
  const xs = times.filter((t): t is number => typeof t === "number" && Number.isFinite(t));
  if (xs.length === 0) return "아직 읽은 값이 없습니다";
  const lo = Math.min(...xs);
  const hi = Math.max(...xs);
  const a = readTimeText(lo);
  const b = readTimeText(hi);
  return a === b ? a : `${a} ~ ${b}`;
}
