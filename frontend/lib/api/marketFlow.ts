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
  windows: { lines: string[] };
  short_lines: { text: string; flags: string[] }[];
  events: { date: string; series: string; kind: string; text: string }[];
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
    isObj(v.ai_text)
  );
}

export async function fetchMarketFlowContext(): Promise<MarketFlowContext> {
  const body = await request<unknown>("GET", "/market/flow-context");
  if (!isMarketFlowContext(body)) {
    throw new Error("market flow-context: 응답 형식이 다름");
  }
  return body;
}
