// POC6-27 — 시장 흐름 시험 자료(11/9 확인 사례 · 저장 종가 · 서버 사건 7건 순서 그대로 · 시험 전용).
import type { FlowEvent, MarketFlowContext } from "@/lib/api/marketFlow";

export const OBS_1106 = {
  date: "2026-11-06",
  value: 5059.69,
  unit: "pt",
  d1: { from_date: "2026-11-05", diff: -324.11, pct: -6.0201 },
  d5: { from_date: "2026-10-30", diff: -671.05, pct: -11.71 },
  range: { dir: "아래" as const, bound: 5383.8, bound_date: "2026-11-05" },
};
export const EVENTS_1109: FlowEvent[] = [
  { date: "2026-11-06", series: "코스피", kind: "range", text: "11/6 코스피 직전 20개 관측 범위 아래(5,383.80 · 11/5 밑)", key: "kospi", value: 5059.69, unit: "pt", dir: "아래", bound: 5383.8, bound_date: "2026-11-05" },
  { date: "2026-11-05", series: "코스피", kind: "range", text: "11/5 코스피 직전 20개 관측 범위 아래(5,469.47 · 10/26 밑)", key: "kospi", value: 5383.8, unit: "pt", dir: "아래", bound: 5469.47, bound_date: "2026-10-26" },
  { date: "2026-11-04", series: "WTI", kind: "expansion", text: "11/4 WTI 변화 확대(-7.97달러 · 이전 20회 평균 변화의 3.4배)", key: "wti", value: 88.21, unit: "달러", delta: -7.97, ratio: 3.4, base_from: "2026-10-06", base_to: "2026-11-03", zero_base: false },
  { date: "2026-11-04", series: "WTI", kind: "range", text: "11/4 WTI 직전 20개 관측 범위 아래(88.28달러 · 10/7 밑)", key: "wti", value: 88.21, unit: "달러", dir: "아래", bound: 88.28, bound_date: "2026-10-07" },
  { date: "2026-11-03", series: "원/달러", kind: "expansion", text: "11/3 원/달러 변화 확대(+19.29원 · 이전 20회 평균 변화의 4.6배)", key: "usdkrw", value: 1362.04, unit: "원", delta: 19.29, ratio: 4.6, base_from: "2026-10-03", base_to: "2026-11-02", zero_base: false },
  { date: "2026-11-03", series: "원/달러", kind: "range", text: "11/3 원/달러 직전 20개 관측 범위 위(1,343.75원 · 10/6 넘음)", key: "usdkrw", value: 1362.04, unit: "원", dir: "위", bound: 1343.75, bound_date: "2026-10-06" },
  { date: "2026-11-02", series: "WTI", kind: "expansion", text: "11/2 WTI 변화 확대(-7.66달러 · 이전 20회 평균 변화의 3.8배)", key: "wti", value: 96.18, unit: "달러", delta: -7.66, ratio: 3.8, base_from: "2026-10-03", base_to: "2026-10-30", zero_base: false },
];

export function flowWith(over: Partial<MarketFlowContext> = {}): MarketFlowContext {
  return {
    generated_at: "2026-11-09T09:00:00+09:00",
    D: "2026-11-05",
    has_flows: true,
    series: {},
    periods: {},
    windows: { lines: [] },
    short_lines: [{ text: "코스피 11/6 · …", flags: [], key: "kospi", obs: OBS_1106 }],
    events: EVENTS_1109,
    event_check: { checked: [], unchecked: [], unchecked_text: null, empty_text: "최근 큰 변화 없음" },
    interpretation: {},
    limits: [],
    status: [],
    today_lines: ["시장 흐름 6개월(11/5까지): …", "최근 큰 변화: 11/6 코스피 직전 20개 관측 범위 아래(5,383.80 · 11/5 밑) · … 외 5건"],
    ai_text: {},
    ...over,
  } as MarketFlowContext;
}

