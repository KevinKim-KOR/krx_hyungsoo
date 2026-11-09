// POC6-27 — [AI용 시장 정보 복사] 글(설계 §6 · 판정 §4): 고정 프롬프트 글자 그대로 + 화면 값 · 빠진 값 '확인 불가' ·
// 늦은 자료는 [자료 상태] · 사건은 전체(화면의 '외 N건'과 달리).
import { describe, it, expect } from "vitest";
import type { MarketTopNResponse } from "@/lib/api";
import type { MarketFlowContext } from "@/lib/api/marketFlow";
import { buildTodayMarketCopyText, TODAY_MARKET_PROMPT } from "./todayMarketCopyText";
import { freshnessRows } from "./todayFreshness";
import { flowWith } from "./todayMarketTestFixtures";

// 설계 §6 고정 프롬프트 원문(docs/ai_design/POC6/POC6_27_TODAY_CHECK_REVISION_DESIGN_V1.md §6).
const DESIGN_PROMPT = [
  "아래 시장 자료를 읽고, 한국 ETF를 검토하기 전에 내가 무엇을 알아야 하는지 쉬운 한국어로 설명해 주세요.",
  "",
  "1. 시장 상태를 한 문장으로 써 주세요. KODEX 200 시장 판정과 코스피 가격 관측의 기준을 각각 밝혀 주세요.",
  "2. 코스피의 최근 가격 움직임과 20거래일·60거래일·6개월 흐름을 줄을 나눠 써 주세요. 주어진 값과 실제 비교 기간을 사용해 주세요.",
  "3. 외국인 누적 순매도와 최근 매도 속도 변화를 구분해 주세요. 가격과 수급이 다른 방향을 보이면 그 차이를 설명해 주세요.",
  "4. 원/달러·WTI나 최근 사건 중 위 내용을 이해하는 데 도움이 되는 관측이 있으면 별도 줄에 추가해 주세요.",
  "5. 마지막에 다음에 확인할 점을 한 줄 써 주세요.",
  "",
  "붙인 자료의 범위에서 관측과 해석을 구분해 주세요. 각 값의 기준일을 사용하고 빠진 값은 확인 불가로 써 주세요. 추세·원인·향후 방향에 대한 해석은 근거와 한계를 밝혀 주세요. 매매 판단에 사용할 수 있는 확인 사항까지 제시해 주세요.",
  "",
  "[아래에 복사한 시장 자료]",
].join("\n");

const MARKET = {
  status: "ok",
  market_context: {
    asof: "2026-11-06",
    regime_label: "하락장",
    regime_code: "bear",
    regime_streak: { regime_code: "bear", streak_days: 21, at_least: false },
    kospi: { status: "ok", display_state: "ok", as_of_date: "2026-11-06", return_20d_pct: -23.64, return_60d_pct: -19.16 },
  },
} as unknown as MarketTopNResponse;

function flow1109(): MarketFlowContext {
  return flowWith({
    D: "2026-11-05",
    periods: {
      "6M": {
        label: "6개월", boundary: "2026-05-05", start: "2026-05-06", end: "2026-11-05", lines: [],
        kospi: { from_date: "2026-05-04", from: 6936.99, to_date: "2026-11-05", to: 5383.8, diff: -1553.19, pct: -22.38997 },
        investors: { foreign: { sum: -164308100000000, days: 124, expected: 124, partial: false } },
      },
    },
    windows: {
      lines: [],
      trend: "직전 20거래일보다 일평균 매도 감소",
      foreign20: {
        recent: { sum: -22.1e12, avg: -1.105e12, from: "2026-10-08", to: "2026-11-05" },
        previous: { sum: -24.0e12, avg: -1.2e12, from: "2026-09-04", to: "2026-10-07" },
      },
      r60: {
        foreign: { sum: -53.1e12, from: "2026-08-10", to: "2026-11-05" },
        individual: { sum: -11.8e12, from: "2026-08-10", to: "2026-11-05" },
        institution: { sum: 9.7e12, from: "2026-08-10", to: "2026-11-05" },
      },
    },
    short_lines: [
      flowWith().short_lines[0],
      { text: "원/달러 …", flags: [], key: "usdkrw", obs: { date: "2026-11-05", value: 1340.07, unit: "원", d1: null, d5: null, range: null } },
      { text: "WTI …", flags: [], key: "wti", obs: { date: "2026-11-06", value: 90.83, unit: "달러", d1: { from_date: "2026-11-05", diff: 0.31, pct: 0.34 }, d5: null, range: null } },
    ],
    end_basis: { D: "2026-11-05", kospi_E: "2026-11-06", flows_E: "2026-11-05", limited_by: "flows", text: "코스피는 11/6, 수급은 11/5까지 있어 기간 비교는 11/5까지입니다" },
    freshness: {
      today_kst: "2026-11-09", expected_kr: "2026-11-06", expected_kr_basis: "calendar",
      items: [
        { key: "flows", label: "외국인 수급", last_date: "2026-11-05", expected: "2026-11-06", basis: "kr_t1", state: "late", behind: 1, reason: "…" },
        { key: "usdkrw", label: "원/달러", last_date: "2026-11-05", expected: "2026-11-06", basis: "kr_t1", state: "late", behind: 1, reason: "…" },
      ],
    },
  });
}

function build(market: MarketTopNResponse | null, flow: MarketFlowContext | null) {
  const fresh = freshnessRows(
    { market, marketPhase: market ? "success" : "error", flow, flowFailed: !flow, holdings: null, holdingsFailed: false, evidence: null, evidenceFailed: false },
    "copy",
  );
  return buildTodayMarketCopyText({ market, flow, fresh });
}

describe("[AI용 시장 정보 복사]", () => {
  it("고정 프롬프트는 설계 §6 글자 그대로 · 맨 앞", () => {
    expect(TODAY_MARKET_PROMPT).toBe(DESIGN_PROMPT);
    expect(build(MARKET, flow1109()).startsWith(`${DESIGN_PROMPT}\n`)).toBe(true);
  });

  it("11/9 사례 근거 줄 — 종가 ≠ 비교 기준값 · 기간 · 수급 · 자료 상태(늦음 · 원인 확인 전)", () => {
    const lines = build(MARKET, flow1109()).slice(DESIGN_PROMPT.length + 1).trim().split("\n");
    expect(lines).toEqual([
      "[시장 판정] KODEX 200 하락장 · 21거래일째 · 2026-11-06",
      "[코스피 최신 종가] 5,059.69 · 2026-11-06 · 2026-11-05 대비 -324.11pt(-6.02%)",
      "[코스피 기간 수익률] 20거래일 -23.64% · 60거래일 -19.16%(둘 다 2026-11-06 기준)",
      "[코스피 6개월] -22.39% · 5/4 6,936.99 → 11/5 5,383.80 · 가격과 수급의 공통 비교 종료일 11/5",
      "[외국인 6개월] 누적 순매도 164.3조원 · 11/5까지 124/124일",
      "[외국인 매도 속도] 직전 20거래일 24.0조원 순매도(일평균 1.2조원) → 최근 20거래일 22.1조원 순매도(일평균 1.1조원) · 11/5까지 · 직전 20거래일보다 일평균 매도 감소",
      "[60거래일 수급] 외국인 -53.1조원 · 개인 -11.8조원 · 기관계 +9.7조원 · 11/5까지",
      "[최근 저점] 2026-11-06 종가 5,059.69 · 11/5의 최근 저점 5,383.80을 밑돌았습니다(직전 20개 저장 종가 기준)",
      "[원/달러] 1,340.07원 · 2026-11-05",
      "[WTI] 90.83달러(+0.34%) · 2026-11-06",
      "[최근 큰 변화 1] 11/6 코스피 종가 5,059.69가 11/5 저점 5,383.80을 밑돌았습니다",
      "[최근 큰 변화 2] 11/5 코스피 종가 5,383.80이 10/26 저점 5,469.47을 밑돌았습니다",
      "[최근 큰 변화 3] 11/4 WTI가 7.97달러 하락했습니다 · 평소 변화의 3.4배",
      "[최근 큰 변화 4] 11/4 WTI 88.21달러가 10/7 저점 88.28달러를 밑돌았습니다",
      "[최근 큰 변화 5] 11/3 원/달러가 19.29원 상승했습니다 · 평소 변화의 4.6배",
      "[최근 큰 변화 6] 11/3 원/달러 1,362.04원이 10/6 고점 1,343.75원을 넘었습니다",
      "[최근 큰 변화 7] 11/2 WTI가 7.66달러 하락했습니다 · 평소 변화의 3.8배",
      "[자료 상태] 2026-11-09 확인 · 외국인 수급 마지막 2026-11-05 · 기대 2026-11-06(국내 직전 거래일) · 1거래일 늦음 / 원/달러 실제 관측일(런던 날짜) 2026-11-05 · 기대 2026-11-06(국내 직전 거래일 대비) · 1거래일 늦음 · 지연 원인 확인 전",
      "[공통 비교 기간] 코스피는 11/6, 수급은 11/5까지 있어 기간 비교는 11/5까지입니다",
    ]);
  });

  it("빠진 값은 '확인 불가'(시장 판정 · 시장 흐름 모두 없음)", () => {
    const text = build(null, null);
    for (const tag of ["[시장 판정]", "[코스피 최신 종가]", "[코스피 기간 수익률]", "[코스피 6개월]", "[외국인 6개월]", "[원/달러]", "[WTI]", "[최근 큰 변화]"]) {
      expect(text).toContain(`${tag} 확인 불가`);
    }
    expect(text).toContain("[자료 상태]");
    expect(text).toContain("기준 확인 필요");
  });

  it("중간 거래일 저장 종가가 비면(11/5 없음) 실제 비교 날짜 11/4 로 적고 '전일'로 부르지 않는다(RESULT 판정 §3-1)", () => {
    const f = flow1109();
    const gap = { ...f.short_lines[0], obs: { ...f.short_lines[0].obs!, d1: { from_date: "2026-11-04", diff: -400, pct: -7.33 }, range: { dir: "아래" as const, bound: 5459.69, bound_date: "2026-11-04" } } };
    const text = build(MARKET, { ...f, short_lines: [gap, ...f.short_lines.slice(1)] } as MarketFlowContext);
    expect(text).toContain("[코스피 최신 종가] 5,059.69 · 2026-11-06 · 2026-11-04 대비 -400.00pt(-7.33%)");
    expect(text).toContain("· 11/4의 최근 저점 5,459.69");
    expect(text).not.toContain("전일");
    expect(text).not.toContain("직전 거래일(");
  });

  it("고점을 넘은 날이면 줄 이름도 '[최근 고점]'(검토 F5)", () => {
    const f = flow1109();
    const up = { ...f.short_lines[0], obs: { ...f.short_lines[0].obs!, range: { dir: "위" as const, bound: 5000, bound_date: "2026-10-20" } } };
    const text = build(MARKET, { ...f, short_lines: [up, ...f.short_lines.slice(1)] } as MarketFlowContext);
    expect(text).toContain("[최근 고점] 2026-11-06 종가 5,059.69");
    expect(text).not.toContain("[최근 저점]");
  });

  it("KOSPI 화면 판정이 지연이면 기간 수익률을 싣지 않는다(화면과 같은 규칙)", () => {
    const stale = { ...MARKET, market_context: { ...MARKET.market_context, kospi: { status: "stale", display_state: "stale", as_of_date: "2026-11-05", trading_day_lag: 1 } } } as unknown as MarketTopNResponse;
    expect(build(stale, flow1109())).toContain("[코스피 기간 수익률] 확인 불가");
  });
});
