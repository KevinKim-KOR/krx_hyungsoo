// POC6-27 — 자료별 최신성(설계 §2 · PLAN 쟁점 2 · 판정 Q4 · Q5 · §4). 기대일은 서버 값만 쓰고 화면은 비교만.
import { describe, it, expect } from "vitest";
import type { EnrichedHoldingsResult, HoldingsMarketEvidenceResponse, MarketTopNResponse } from "@/lib/api";
import type { FlowFreshItem, MarketFlowContext } from "@/lib/api/marketFlow";
import { freshnessLine, freshnessRows, freshnessSummary, kstDate, needsAttention, type FreshSources } from "./todayFreshness";

const item = (key: string, label: string, last: string | null, state: FlowFreshItem["state"], behind: number | null, reason: string | null = null): FlowFreshItem => ({
  key, label, last_date: last, expected: state === "observed" ? null : "2026-11-06", basis: state === "observed" ? "observed_only" : "kr_t1", state, behind, reason,
});
function flow(items: FlowFreshItem[], basis: "calendar" | "weekday_fallback" = "calendar"): MarketFlowContext {
  return { status: [], freshness: { today_kst: "2026-11-09", expected_kr: "2026-11-06", expected_kr_basis: basis, items } } as unknown as MarketFlowContext;
}
// 11/9 사례: 수급 · 원/달러 11/5(1거래일 늦음) · WTI 11/6(판정 없음)
const FLOW_1109 = flow([
  item("flows", "외국인 수급", "2026-11-05", "late", 1, "국내 직전 거래일 2026-11-06 대비 1거래일 늦음"),
  item("usdkrw", "원/달러", "2026-11-05", "late", 1, "국내 직전 거래일 2026-11-06 대비 1거래일 늦음"),
  item("wti", "WTI", "2026-11-06", "observed", null),
]);
const MARKET = {
  status: "ok",
  market_context: { asof: "2026-11-06", kospi: { status: "ok", display_state: "ok", as_of_date: "2026-11-06" } },
} as unknown as MarketTopNResponse;
const HOLD = (asof: string | null, source = "naver", price: number | null = 10) =>
  ({ items: [{ ticker: "161510", current_price: price, price_source: source, price_asof: asof }] }) as unknown as EnrichedHoldingsResult;
const EVID = { price_basis: { reference_date: "2026-11-06" } } as unknown as HoldingsMarketEvidenceResponse;
const src = (over: Partial<FreshSources> = {}): FreshSources => ({
  market: MARKET, marketPhase: "success", flow: FLOW_1109, flowFailed: false,
  holdings: HOLD("2026-11-06T15:27:20+09:00"), holdingsFailed: false, evidence: EVID, evidenceFailed: false, ...over,
});

describe("검증자 r1 F2 — 달력에 없는 날짜 · 느슨한 시각은 최신이 아니라 '기준 확인 필요'", () => {
  it("kstDate 는 실제 날짜 · 시간대가 붙은 ISO 시각만 읽는다", () => {
    expect(kstDate("2026-11-06")).toBe("2026-11-06");
    expect(kstDate("2028-02-29")).toBe("2028-02-29");
    expect(kstDate("2026-11-06T15:27:20+09:00")).toBe("2026-11-06");
    expect(kstDate("2026-11-06T15:27:20Z")).toBe("2026-11-07");
    for (const bad of ["2026-13-01", "2026-02-29", "2026-02-30T15:27:20+09:00", "2026-11-06T25:00:00+09:00", "2026/11/06", "Nov 6 2026", "2026-11-06T15:27:20"]) {
      expect(kstDate(bad)).toBeNull();
    }
  });
  it.each([
    ["시장 판정 기준일", { market: { ...MARKET, market_context: { ...MARKET.market_context, asof: "2026-13-01" } } as unknown as MarketTopNResponse }, "regime", "날짜 확인 불가"],
    ["보유 근거 가격 기준일", { evidence: { price_basis: { reference_date: "2026-02-30" } } as unknown as HoldingsMarketEvidenceResponse }, "evidence_basis", "날짜 확인 불가"],
    ["보유 현재가 시각(날짜만)", { holdings: HOLD("2026-13-01") }, "holdings_price", "관측 시각 확인 불가 1종목"],
    ["보유 현재가 시각(넘어가는 날짜)", { holdings: HOLD("2026-02-30T15:27:20+09:00") }, "holdings_price", "관측 시각 확인 불가 1종목"],
  ] as const)("%s", (_n, over, key, reason) => {
    const row = freshnessRows(src(over as Partial<FreshSources>), "reload").find((r) => r.key === key);
    expect(row?.state).toBe("check");
    expect(row?.reason).toBe(reason);
  });
  it("서버 기대일이 깨졌으면 비교하는 줄은 '기대 기준일 확인 불가'(최신으로 보지 않음)", () => {
    const broken = { ...FLOW_1109, freshness: { ...FLOW_1109.freshness!, expected_kr: "2026-13-01" } } as MarketFlowContext;
    const rows = freshnessRows(src({ flow: broken }), "reload");
    for (const key of ["regime", "evidence_basis", "holdings_price"]) {
      const r = rows.find((x) => x.key === key);
      expect(r?.state).toBe("check");
      expect(r?.reason).toBe("기대 기준일 확인 불가");
    }
  });
});

describe("불러오는 중은 '자료 없음'이 아니다(검토 F3)", () => {
  it("시장 흐름을 불러오는 중이면 수급 · 원/달러 · 기대일에 기대는 줄(시장 판정 · 보유 · 근거)을 만들지 않는다", () => {
    const rows = freshnessRows(src({ flow: null }), "reload");
    expect(rows.map((r) => r.key)).toEqual(["kospi"]);
    expect(needsAttention(rows)).toEqual([]);
  });
  it("보유 · 근거를 불러오는 중이면 그 줄만 없다 · 실패면 '불러오지 못함'", () => {
    expect(freshnessRows(src({ holdings: null, evidence: null }), "reload").map((r) => r.key)).not.toContain("holdings_price");
    const failed = needsAttention(freshnessRows(src({ holdings: null, holdingsFailed: true, evidence: null, evidenceFailed: true }), "reload"));
    expect(failed.find((r) => r.key === "holdings_price")?.reason).toBe("보유 자료를 불러오지 못함");
    expect(failed.find((r) => r.key === "evidence_basis")?.reason).toBe("보유 근거 자료를 불러오지 못함");
    expect(needsAttention(freshnessRows(src({ flow: null, flowFailed: true }), "reload")).find((r) => r.key === "flows")?.reason).toBe(
      "시장 흐름 자료를 불러오지 못함",
    );
  });
});

describe("11/9 사례 — 수급 · 원/달러만 1거래일 늦음(판정 §4)", () => {
  it("[요약 다시 읽기] 대상: 늦은 것은 수급 · 원/달러 두 줄 · 요약 '2건 · 1거래일 늦음'", () => {
    const bad = needsAttention(freshnessRows(src(), "reload"));
    expect(bad.map((r) => r.key)).toEqual(["flows", "usdkrw"]);
    expect(freshnessSummary(bad)).toBe("2건 · 1거래일 늦음");
    expect(freshnessLine(bad[0])).toBe("마지막 2026-11-05 · 기대 2026-11-06(국내 직전 거래일) · 1거래일 늦음");
    // 원/달러는 '국내 T-1 대비' 기준과 실제 관측일(런던 날짜)을 나눠 적는다(판정 Q4).
    expect(freshnessLine(bad[1])).toBe("실제 관측일(런던 날짜) 2026-11-05 · 기대 2026-11-06(국내 직전 거래일 대비) · 1거래일 늦음");
  });
  it("WTI 는 날짜로 경고 · 확인 창을 만들지 않는다(판정 §4)", () => {
    const all = freshnessRows(src({ flow: flow([item("wti", "WTI", "2026-10-01", "observed", null)]) }), "reload");
    expect(all.find((r) => r.key === "wti")).toBeUndefined();
  });
  it("[AI용 시장 정보 복사] 대상은 시장 자료만(보유 현재가 · 보유 근거 없음)", () => {
    expect(freshnessRows(src(), "copy").map((r) => r.key)).toEqual(["kospi", "regime", "flows", "usdkrw"]);
  });
});

describe("요약 문구 — 지연 정도 · 상태가 섞이면 나눈다(판정 §2)", () => {
  it("'늦음 N건 · 기준 확인 필요 M건'", () => {
    const rows = needsAttention(
      freshnessRows(src({ flow: flow([item("flows", "외국인 수급", "2026-11-04", "late", 2), item("usdkrw", "원/달러", null, "check", null, "자료 없음")]) }), "reload"),
    );
    expect(freshnessSummary(rows)).toBe("늦음 1건 · 기준 확인 필요 1건");
  });
  it("늦은 거래일 수가 다르면 'N건 · K거래일'로 묶지 않는다", () => {
    const rows = needsAttention(
      freshnessRows(src({ flow: flow([item("flows", "외국인 수급", "2026-11-04", "late", 2), item("usdkrw", "원/달러", "2026-11-05", "late", 1)]) }), "reload"),
    );
    expect(freshnessSummary(rows)).toBe("늦음 2건");
  });
  it("평일 대체를 쓴 해는 기준을 함께 밝힌다", () => {
    const rows = needsAttention(freshnessRows(src({ flow: flow([item("flows", "외국인 수급", "2026-11-05", "late", 1)], "weekday_fallback") }), "reload"));
    expect(rows[0].basis).toBe("국내 직전 거래일 · 평일 기준(달력 없음)");
  });
});

describe("기준을 알 수 없으면 '기준 확인 필요'(판정 §4)", () => {
  it("시장 흐름 실패 · 옛 응답(freshness 없음)", () => {
    expect(needsAttention(freshnessRows(src({ flow: null, flowFailed: true }), "copy")).map((r) => [r.key, r.state, r.reason])).toEqual([
      ["regime", "check", "기대 기준일 확인 불가"],
      ["flows", "check", "시장 흐름 자료를 불러오지 못함"],
      ["usdkrw", "check", "시장 흐름 자료를 불러오지 못함"],
    ]);
    const old = { status: [{ key: "flows", label: "투자자별 순매수", E: "2026-11-05" }] } as unknown as MarketFlowContext;
    const rows = needsAttention(freshnessRows(src({ flow: old }), "copy"));
    expect(rows.find((r) => r.key === "flows")).toMatchObject({ state: "check", lastDate: "2026-11-05", reason: "기준일 판정 자료 없음(서버 응답에 없음)" });
  });
  it("깨진 날짜 · 날짜 없음", () => {
    const rows = needsAttention(freshnessRows(src({ evidence: { price_basis: { reference_date: "11/06" } } as unknown as HoldingsMarketEvidenceResponse }), "reload"));
    expect(rows.find((r) => r.key === "evidence_basis")).toMatchObject({ state: "check", reason: "날짜 확인 불가" });
  });
});

describe("보유 현재가(판정 Q5) — 네이버 체결 시각인 행만 날짜 비교", () => {
  it.each([
    ["기대일과 같은 날 체결", HOLD("2026-11-06T15:27:20+09:00"), "fresh"],
    ["오늘 장중 체결(기대일보다 뒤)", HOLD("2026-11-09T10:12:00+09:00"), "fresh"],
    ["기대일 전 체결", HOLD("2026-11-05T15:30:00+09:00"), "late"],
    ["UTC 표기도 KST 날짜로(11/5 23:00Z = 11/6 08:00 KST)", HOLD("2026-11-05T23:00:00Z"), "fresh"],
    ["다른 출처", HOLD("2026-11-06T15:27:20+09:00", "other"), "check"],
    ["시세 없음", HOLD(null, "naver", null), "check"],
    ["시각 깨짐", HOLD("어제"), "check"],
  ] as const)("%s → %s", (_n, h, state) => {
    expect(freshnessRows(src({ holdings: h }), "reload").find((r) => r.key === "holdings_price")?.state).toBe(state);
  });
  it("KST 날짜 변환", () => {
    expect(kstDate("2026-11-05T23:00:00Z")).toBe("2026-11-06");
    expect(kstDate("2026-11-06")).toBe("2026-11-06");
    expect(kstDate("x")).toBeNull();
  });
});

describe("코스피 — 기존 화면 판정 그대로", () => {
  it("지연이면 늦음(거래일 지연 수) · 휴장이면 최신", () => {
    const stale = { ...MARKET, market_context: { asof: "2026-11-06", kospi: { status: "stale", display_state: "stale", as_of_date: "2026-11-05", trading_day_lag: 1 } } } as unknown as MarketTopNResponse;
    expect(freshnessRows(src({ market: stale }), "copy")[0]).toMatchObject({ key: "kospi", state: "late", behind: 1 });
    const holiday = { ...MARKET, market_context: { asof: "2026-11-06", kospi: { status: "ok", display_state: "holiday", as_of_date: "2026-11-06" } } } as unknown as MarketTopNResponse;
    expect(freshnessRows(src({ market: holiday }), "copy")[0]).toMatchObject({ key: "kospi", state: "fresh" });
  });
});
