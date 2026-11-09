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
import { flowRetryHelps, type MarketFlowContext } from "@/lib/api/marketFlow";
import type { MenuKey } from "../LeftSidebar";
import { kstText } from "../MLCardParts";
import { forwardConclusion } from "../ml_forward/forwardText";
import type { MaintenanceItem } from "./maintenanceQueue";


export type SummaryTone = "ok" | "warn" | "muted" | "bad" | "info";
export type SummaryTarget =
  | { kind: "menu"; key: MenuKey }
  | { kind: "scroll"; id: string }
  | { kind: "reload" }
  // POC6-27 — 상단 두 최신화 버튼과 같은 작업(「자료 최신화 필요」 카드 안 할 일 버튼 · 판정 Q2 경로 보존)
  | { kind: "market_refresh" }
  | { kind: "holdings_refresh" };
export type SummaryAction = { label: string; target: SummaryTarget; primary: boolean };
export type SummaryRow = {
  id: "market" | "holdings" | "candidates" | "data" | "research";
  area: string;
  tone: SummaryTone;
  badge: string;
  text: string;
  // 결론 아래 보조 한 줄(서버가 준 둘째 문장 등 · 없으면 null)
  sub?: string | null;
  // POC6-17 — 알릴 설명(기간 비교 기준일 제한 · 수급 연결 문제 · 서버 문장 · 없으면 null)
  note?: string | null;
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

// 성공 시각(ms) → 'YYYY-MM-DD HH:MM:SS'(한국 시각). 없으면 '조회 시각 미확인'(판정 §4).
export function readTimeText(ms: number | undefined): string {
  if (typeof ms !== "number" || !Number.isFinite(ms)) return "조회 시각 미확인";
  return kstText(new Date(ms).toISOString()) ?? "조회 시각 미확인";
}

export function staleOf(label: string, q: QueryState<unknown>): string | null {
  if (q.phase !== "success" || !q.stale) return null;
  return `${label}: 다시 읽기 실패 · ${readTimeText(q.successAt)}에 읽은 값을 표시 중`;
}

// 첫 조회부터 실패해 이전 값도 없는 원천(검증자 r1 F1 — 줄 안에서 빠지지 않게).
export function failOf(label: string, q: QueryState<unknown>): string | null {
  return q.phase === "error" ? `${label}: 불러오지 못했습니다(이전 값 없음)` : null;
}

// 줄 아래 상태 메모(다시 읽기 실패 · 첫 조회 실패)를 한 줄로.
export function joinStale(...notes: (string | null)[]): string | null {
  const xs = notes.filter((x): x is string => !!x);
  return xs.length ? xs.join(" / ") : null;
}

// POC6-27 — 예전 '시장 흐름' 요약 줄(marketRow)은 「시장 흐름」 구역(MarketFlowBlock)이 대신한다.

// POC6-27 — 예전 '보유 점검' 요약 줄(holdingsRow)은 「보유 점검」 카드(today/CheckCards)가 대신한다.

// ── 잘 오르는 ETF(대시보드 고정 조건 목록 · 판정 §5 · 화면 글자에 '후보' 안 씀 = AC-7) ─────────────────────────
const BASIS_WORD: Record<string, string> = {
  daily: "일간 수익률",
  one_month: "1개월 수익률",
  three_month: "3개월 수익률",
};

// POC6-27 판정 §4 — 응답의 실제 방향으로 적는다(오름차순 = '수익률 낮은 순' · 예전 '상위'는 방향을 보지 않았음).
export function candidateLabel(data: MarketTopNResponse): string {
  const word = BASIS_WORD[data.basis ?? ""] ?? `수익률(기준 ${data.basis ?? "미확인"})`;
  const dir = data.order === "asc" ? "낮은 순" : data.order === "desc" ? "높은 순" : "방향 확인 불가";
  return `${word} ${dir} ${data.candidates.length}개`;
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

// POC6-27 — 예전 '잘 오르는 ETF' 요약 줄(candidatesRow)은 「잘 오르는 ETF」 카드가 대신한다.

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
  // POC6-27 — 정비 목록은 이 줄 바로 아래 펼침(「자료 업데이트 목록」)이라 스크롤 버튼이 없다.
  const actions: SummaryAction[] = [];
  // 정비 항목을 만든 원천 중 다시 읽기에 실패해 이전 값을 쓰는 것(그 값을 받은 시각 · 검토 지적 3)
  const stale = joinStale(
    nav ? staleOf("ETF 기준가", nav) : null,
    evidence ? staleOf("보유 근거", evidence) : null,
  );
  if (loading) {
    return { id: "data", area: "자료 확인", tone: "muted", badge: "확인 중", text: "자료 상태를 확인하는 중입니다", basis: null, staleNote: stale, actions };
  }
  const tail = hasTasks ? " · 해야 할 작업은 맨 위 「자료 최신화 필요」" : "";
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
    badge: `확인할 자료 ${items.length}건`,
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
  // POC6-17 — 수급이 기간 비교를 막았거나 수급 반영 · 직접 조회 실패가 확인됐고, 다시 눌러 나아질 수 있을 때만(서버 retry_helps · PLAN §4).
  // 확인된 OCI 수집 실패 · 정상 가져오기 뒤 새 자료 없음 · 조회 실패는 할 일을 만들지 않는다(판정 §4-4). 같은 버튼 하나.
  const fd = flow.phase === "success" ? flow.data : null;
  const flowLimited = fd?.end_basis?.limited_by === "flows";
  const flowFailed = fd?.flow_link?.state === "apply_failed" || fd?.flow_link?.state === "legacy_direct_failed";
  const flowReason =
    fd && flowRetryHelps(fd.flow_link) && fd.flow_link && (flowLimited || flowFailed)
      ? flowLimited && fd.end_basis
        ? fd.end_basis.text
        : `수급 연결: ${fd.flow_link.text}`
      : null;
  if (marketItems.length > 0 || flowReason) {
    const ctx = market.phase === "success" ? market.data.market_context : null;
    const kospiDate = ctx?.kospi?.as_of_date ?? null;
    const etfDate = market.phase === "success" ? (market.data.asof ?? null) : null;
    const dates = [kospiDate ? `KOSPI ${kospiDate}` : null, etfDate ? `ETF 가격 ${etfDate}` : null]
      .filter(Boolean)
      .join(" · ");
    tasks.push({
      id: "market_refresh",
      title: "시장 자료 갱신이 필요합니다.",
      reasons: [
        dates ? `지금 PC에 저장된 시장 자료: ${dates}` : null,
        ...marketItems.map((it) => it.text),
        flowReason,
      ].filter((x): x is string => !!x),
      doText:
        "[최신 시장 데이터 갱신]을 눌러 주세요(맨 위 버튼과 같은 작업). 갱신해도 다른 자료 항목이 모두 해결되는 것은 아닙니다." +
        (flowReason ? " 수급은 OCI가 모은 자료를 이 버튼으로 PC에 반영합니다(자동 실행은 보관본만 받습니다)." : ""),
      action: { label: "최신 시장 데이터 갱신", target: { kind: "market_refresh" }, primary: true },
    });
  }
  const priceItems = items.filter((it) => it.task === "holdings_price");
  if (priceItems.length > 0) {
    tasks.push({
      id: "holdings_price",
      title: "보유 종목 현재가를 다시 받아야 합니다.",
      reasons: priceItems.map((it) => it.text),
      doText: "[보유 현재가 업데이트]를 눌러 주세요(맨 위 버튼과 같은 작업).",
      action: { label: "보유 현재가 업데이트", target: { kind: "holdings_refresh" }, primary: true },
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
