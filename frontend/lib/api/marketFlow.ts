// POC6-01 — GET /market/flow-context(시장 흐름 · 수급 · 환율 · 유가 · 읽기 전용).
// 문장 줄 · AI 전달문은 서버가 만들고 화면 · 복사문 · 미리보기가 그대로 쓴다(세 경로 같은 숫자 · 기간).
// 기간 4종이 한 번에 오므로 기간을 바꿔도 다시 조회하지 않는다.
import { request } from "./core";

export type FlowPeriodCode = "1M" | "3M" | "6M" | "YTD";
export const FLOW_PERIODS: [FlowPeriodCode, string][] = [
  ["1M", "1개월"],
  ["3M", "3개월"],
  ["6M", "6개월"],
  ["YTD", "연초 이후"],
];
export const DEFAULT_FLOW_PERIOD: FlowPeriodCode = "6M";

export type FlowPoint = [string, number];
export type FlowInvestor = "foreign" | "individual" | "institution" | "other_corp";

export interface FlowPriceSeries {
  label: string;
  unit: string;
  E: string | null;
  points: FlowPoint[];
  collected_at: string | null;
}

export interface FlowPeriod {
  label: string;
  boundary: string;
  start: string | null;
  end: string;
  lines: string[];
  // POC6-27 — 이미 응답에 있던 구조값(화면 숫자 칸 · 복사문이 씀 · 없으면 '확인 불가')
  covered?: boolean;
  kospi?: FlowChange | null;
  investors?: Partial<Record<FlowInvestor, FlowPeriodSum>>;
}

export interface FlowChange {
  from_date: string;
  from: number;
  to_date: string;
  to: number;
  diff: number;
  pct: number | null;
}

export interface FlowPeriodSum {
  sum: number;
  days: number;
  expected: number;
  partial: boolean;
}

// POC6-27 — 서버가 계산에 쓴 값을 문장과 따로 내보낸 구조 칸(추가 칸 · 옛 응답에는 없음 · 문장은 그대로).
export interface FlowStep {
  from_date: string;
  diff: number;
  pct: number | null;
}

export interface FlowRange {
  dir: "위" | "아래";
  bound: number; // 비교 기준값(직전 20개 관측의 최고 · 최저) — 그날 종가가 아니다
  bound_date: string;
}

export interface FlowPriceObs {
  date: string;
  value: number; // 그날 관측값(종가)
  unit: string;
  d1: FlowStep | null;
  d5: FlowStep | null;
  range: FlowRange | null;
}

export interface FlowNetObs {
  date: string;
  value: number;
  unit: string;
  ratio: number | null;
  base_from: string | null;
  base_to: string | null;
  note: string | null;
}

export type FlowSeriesKey = "kospi" | "usdkrw" | "wti" | "foreign" | "institution";

export interface FlowShortLine {
  text: string;
  flags: string[];
  key?: FlowSeriesKey;
  obs?: FlowPriceObs | FlowNetObs | null;
}

export interface FlowEvent {
  date: string;
  series: string;
  kind: string;
  text: string;
  key?: FlowSeriesKey;
  value?: number;
  unit?: string;
  dir?: "위" | "아래";
  bound?: number;
  bound_date?: string;
  delta?: number;
  ratio?: number | null;
  base_from?: string | null;
  base_to?: string | null;
  zero_base?: boolean;
}

export interface FlowWindowSum {
  sum: number;
  avg?: number;
  from: string;
  to: string;
}

export interface FlowWindows {
  lines: string[];
  trend?: string | null;
  trend_short?: string | null;
  foreign20?: { recent: FlowWindowSum; previous: FlowWindowSum } | null;
  r60?: Partial<Record<"foreign" | "individual" | "institution", FlowWindowSum | null>> | null;
}

export type FlowFreshState = "fresh" | "late" | "check" | "observed";

export interface FlowFreshItem {
  key: string;
  label: string;
  last_date: string | null;
  expected: string | null;
  basis: string;
  state: FlowFreshState;
  behind: number | null;
  reason: string | null;
}

export interface FlowFreshness {
  today_kst: string;
  expected_kr: string | null;
  expected_kr_basis: "calendar" | "weekday_fallback" | null;
  items: FlowFreshItem[];
}

export interface MarketFlowContext {
  generated_at: string;
  D: string | null;
  has_flows: boolean;
  series: {
    kospi?: FlowPriceSeries;
    usdkrw?: FlowPriceSeries;
    wti?: FlowPriceSeries;
    flows?: {
      label: string;
      unit: string;
      E: string | null;
      investors: Record<FlowInvestor, FlowPoint[]>;
      collected_at: string | null;
    };
  };
  periods: Partial<Record<FlowPeriodCode, FlowPeriod>>;
  windows: FlowWindows;
  short_lines: FlowShortLine[];
  events: FlowEvent[];
  // 최근 5개 관측 사건을 모든 자료에서 비교했는지(검증자 r1 F2). 사건이 없을 때 보일 문장(empty_text) ·
  // 확인 못 한 자료 문장(unchecked_text)은 서버가 만든다 — '큰 변화 없음'은 모두 비교했을 때만.
  event_check: {
    checked: string[];
    unchecked: { label: string; reason: string }[];
    unchecked_text: string | null;
    empty_text: string | null;
  };
  // 기간마다 그 기간 변화로 만든 해석 줄 [관측, 가능성, 다른 설명 · 한계] · 확인 못 한 조합 · 해당 없음 문장.
  interpretation: Partial<Record<FlowPeriodCode, { rows: string[][]; notes: string[] }>>;
  limits: string[];
  status: { key: string; label: string; E: string | null; collected_at: string | null }[];
  today_lines: string[];
  ai_text: Partial<Record<FlowPeriodCode, string>>;
  // POC6-17 — 기간 비교 기준일 이유 · 수급 연결 상태(서버 한 곳에서 만든 문장 · 네 출력 공통)
  end_basis?: FlowEndBasis;
  flow_link?: FlowLink;
  // POC6-27 — 자료별 최신성(서버가 기대 기준일을 정하고 화면은 비교만 · 옛 응답에는 없음)
  freshness?: FlowFreshness;
}

export interface FlowEndBasis {
  D: string | null;
  kospi_E: string | null;
  flows_E: string | null;
  // 공통 끝일 D 를 실제로 막은 자료(수급 · 코스피 · 중간 결측 · 공통 날짜 없음) · null = 제한 없음
  limited_by: "flows" | "kospi" | "gap" | "unknown" | null;
  text: string;
}

export type FlowLinkState =
  | "applied"
  | "applied_local"
  | "kept_local"
  | "apply_failed"
  | "oci_collect_failed"
  | "no_record"
  | "legacy_direct_failed"
  | "unknown";

export interface FlowLink {
  state: FlowLinkState;
  at: string | null;
  text: string;
  // [최신 시장 데이터 갱신]을 다시 눌러 나아질 수 있는가(서버 판단 · 할 일 근거)
  retry_helps: boolean;
  oci_flow_status: string | null;
}

const isArr = (v: unknown): v is unknown[] => Array.isArray(v);
const isObj = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

// 화면이 쓰는 칸의 모양만 확인한다(어긋나면 조회 실패로 — 카드 하나 때문에 화면 전체가 깨지지 않게).
export function isMarketFlowContext(v: unknown): v is MarketFlowContext {
  return (
    isObj(v) &&
    (v.D === null || typeof v.D === "string") &&
    typeof v.has_flows === "boolean" &&
    isObj(v.series) &&
    isObj(v.periods) &&
    isObj(v.windows) &&
    isArr(v.windows.lines) &&
    isArr(v.short_lines) &&
    isArr(v.events) &&
    isObj(v.event_check) &&
    isArr(v.event_check.unchecked) &&
    isObj(v.interpretation) &&
    Object.values(v.interpretation).every((x) => isObj(x) && isArr(x.rows) && isArr(x.notes)) &&
    isArr(v.limits) &&
    isArr(v.status) &&
    isArr(v.today_lines) &&
    v.today_lines.every((l) => typeof l === "string") &&
    isObj(v.ai_text) &&
    (v.end_basis === undefined || (isObj(v.end_basis) && typeof v.end_basis.text === "string")) &&
    (v.flow_link === undefined ||
      (isObj(v.flow_link) && typeof v.flow_link.text === "string" && typeof v.flow_link.retry_helps === "boolean"))
  );
}

// 「시장 흐름 자세히」 · 대시보드가 경고색으로 보일 수급 연결 상태(정상 반영 · 새 자료 없음은 제외)
export const FLOW_LINK_WARN: FlowLinkState[] = [
  "applied_local",
  "kept_local",
  "apply_failed",
  "oci_collect_failed",
  "no_record",
  "legacy_direct_failed",
  "unknown",
];

// 다시 눌러 나아질 수 있는가 — 서버 retry_helps 와 함께, 확인된 OCI 최근 수집 실패면 언제나 아님(판정 §4-4 ·
// 검증자 r1 F1 · 서버 판단을 화면 두 곳(「지금 할 일」 · 버튼 위치 안내)에서도 같은 규칙으로 막는다)
export function flowRetryHelps(l: FlowLink | undefined): boolean {
  if (!l || !l.retry_helps || l.state === "oci_collect_failed") return false;
  return l.oci_flow_status == null || l.oci_flow_status === "OK" || l.oci_flow_status === "PARTIAL";
}

// 화면에 따로 알릴 만한 기준일 · 연결 문장(제한 있음 또는 경고 상태일 때만 · 정상이면 null)
export function flowBasisNote(d: MarketFlowContext): string | null {
  const parts: string[] = [];
  if (d.end_basis && d.end_basis.limited_by) parts.push(d.end_basis.text);
  if (d.flow_link && FLOW_LINK_WARN.includes(d.flow_link.state)) parts.push(`수급 연결: ${d.flow_link.text}`);
  return parts.length ? parts.join(" · ") : null;
}

export async function fetchMarketFlowContext(): Promise<MarketFlowContext> {
  const body = await request<unknown>("GET", "/market/flow-context");
  if (!isMarketFlowContext(body)) {
    throw new Error("market flow-context: 응답 형식이 다름");
  }
  return body;
}
