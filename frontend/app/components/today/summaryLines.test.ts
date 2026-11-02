// POC6-16 — 「지금 확인할 내용」 줄 · 「지금 할 일」 순수 함수 시험(PLAN 판정 V1.1 §2 · §3-1 · §4 · §5).
// 줄 문장은 기존 응답 · 함수 값 그대로 · 자기 응답 상태만 · 할 일은 기존 정비 점검이 알린 것만.
import { describe, it, expect } from "vitest";
import type { QueryState } from "@/lib/api/queryCache";
import type {
  EnrichedHoldingsResult,
  ForwardComparisonResponse,
  MarketTopNResponse,
} from "@/lib/api";
import type { MarketFlowContext } from "@/lib/api/marketFlow";
import { DATA as FWD } from "../ml_forward/testFixtures";
import { forwardConclusion } from "../ml_forward/forwardText";
import type { MaintenanceItem } from "./maintenanceQueue";
import {
  candidatePeriod,
  candidatesRow,
  dataRow,
  marketRow,
  readRangeText,
  readTimeText,
  researchDates,
  researchRow,
  summaryTasks,
} from "./summaryLines";

const cand = (ticker: string, ret: number | null, s = "2026-09-23", e = "2026-10-23") => ({
  ticker,
  name: `ETF ${ticker}`,
  selected_return_pct: ret,
  selected_basis_start_date: s,
  selected_basis_end_date: e,
});
function market(over: Record<string, unknown> = {}, ctx: Record<string, unknown> = {}): QueryState<MarketTopNResponse> {
  return {
    phase: "success",
    stale: false,
    successAt: 1,
    data: {
      status: "ok",
      asof: "2026-10-23",
      basis: "one_month",
      n: 10,
      filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
      candidates: [cand("A", 11.4873), cand("B", 9.702), cand("C", 8.7055), cand("D", 1)],
      market_context: {
        status: "ok",
        asof: "2026-10-23",
        regime_label: "하락장",
        regime_code: "bear",
        regime_streak: { regime_code: "bear", streak_days: 11, at_least: false },
        kospi: { status: "stale", display_state: "stale", as_of_date: "2026-10-22", trading_day_lag: 6 },
        kodex200: { status: "ok" },
        ...ctx,
      },
      ...over,
    } as unknown as MarketTopNResponse,
  };
}
const FLOW_OK: QueryState<MarketFlowContext> = {
  phase: "success",
  stale: false,
  data: { today_lines: ["시장 흐름 6개월(10/22까지): 코스피 -13.78%", "최근 큰 변화: …"] } as unknown as MarketFlowContext,
};
const ERR = { phase: "error" } as const;
const LOADING = { phase: "loading" } as const;

describe("시장 흐름 줄", () => {
  it("KOSPI 카드와 같은 시장 판정 · 연속 일수 · 서버 문장 · KOSPI · KODEX200 기준일을 따로", () => {
    const r = marketRow(market(), FLOW_OK);
    expect(r.badge).toBe("하락장 · 11거래일째");
    expect(r.text).toBe("KODEX200 기준 시장 판정 · 시장 흐름 6개월(10/22까지): 코스피 -13.78%");
    expect(r.basis).toBe(
      "KOSPI 기준일 2026-10-22 · 6거래일 지연 · KODEX200 기준일 2026-10-23 · 시장 판정은 이 화면을 처음 열 때 읽은 값(다시 읽기 제외)",
    );
    expect(r.sub).toBe("최근 큰 변화: …");
    expect(r.actions.map((a) => [a.label, a.primary])).toEqual([
      ["시장 흐름 자세히", true],
      ["KOSPI 차트 ↓", false],
    ]);
  });
  it("시장 배경 상태가 partial 이어도 KOSPI 카드처럼 시장 판정을 보인다(실제 자료 2026-11-02 · 카드와 같은 조건)", () => {
    const r = marketRow(market({}, { status: "partial" }), FLOW_OK);
    expect(r.badge).toBe("하락장 · 11거래일째");
    expect(r.basis).toContain("KODEX200 기준일 2026-10-23");
    const none = marketRow(market({ market_context: null }), FLOW_OK);
    expect(none.badge).toBe("시장 판정 확인 불가");
  });
  it("수급 · 환율 · 유가만 실패하면 시장 판정은 남기고 실패를 구분", () => {
    const r = marketRow(market(), ERR);
    expect(r.badge).toBe("하락장 · 11거래일째");
    expect(r.text).toContain("수급 · 환율 · 유가 자료를 불러오지 못했습니다");
  });
  it("시장 목록 조회 실패 — 다시 읽기로 다시 계산하지 않는다는 안내", () => {
    const r = marketRow(ERR, FLOW_OK);
    expect([r.tone, r.badge]).toEqual(["bad", "불러오지 못함"]);
    expect(r.basis).toContain("브라우저를 새로 고치면 다시 읽습니다");
  });
  it("수급 등 다시 읽기 실패 — 이전 값 · 그 값을 받은 시각", () => {
    const stale: QueryState<MarketFlowContext> = { ...FLOW_OK, stale: true, successAt: Date.UTC(2026, 10, 1, 17, 25, 0) } as QueryState<MarketFlowContext>;
    expect(marketRow(market(), stale).staleNote).toBe(
      "수급 · 환율 · 유가: 다시 읽기 실패 · 2026-11-02 02:25:00에 읽은 값을 표시 중",
    );
  });
});

describe("잘 오르는 ETF 줄(판정 §5)", () => {
  it("요청 상한이 아니라 실제 길이 N · 기준 · 1위 · 기간 · 제외 조건", () => {
    const r = candidatesRow(market());
    expect(r.badge).toBe("1개월 수익률 상위 4개");
    expect(r.text).toBe("1위 ETF A +11.49% 외 3개 · 상위 3개는 아래");
    expect(r.basis).toBe(
      "2026-09-23 ~ 2026-10-23 · 인버스 · 레버리지 · 합성 · 선물 제외 · 최대 10개 · 「요즘 잘 오르는 ETF」에서 고른 기간 · 정렬과 다를 수 있음",
    );
  });
  it.each([
    [[], "1개월 수익률 상위 0개", "조건에 맞는 ETF가 없습니다"],
    [[cand("A", 2)], "1개월 수익률 상위 1개", "1위 ETF A +2.00%"],
    [[cand("A", null), cand("B", 1)], "1개월 수익률 상위 2개", "1위 ETF A 수익률 확인 불가 외 1개 · 상위 2개는 아래"],
  ])("목록 길이 그대로 — %#", (cs, badge, text) => {
    const r = candidatesRow(market({ candidates: cs }));
    expect([r.badge, r.text]).toEqual([badge, text]);
  });
  it("종목별 계산 기간이 다르면 선두 종목 날짜로 덮지 않는다", () => {
    expect(candidatePeriod([cand("A", 1), cand("B", 1, "2026-09-22")] as never)).toBe(
      "종목별 계산 기간 다름(「요즘 잘 오르는 ETF」에서 확인)",
    );
  });
  it("화면 글자에 '후보' 낱말을 쓰지 않는다(AC-7)", () => {
    for (const q of [market(), ERR, LOADING, market({ candidates: [] })] as QueryState<MarketTopNResponse>[]) {
      const r = candidatesRow(q);
      expect(`${r.area} ${r.badge} ${r.text} ${r.basis ?? ""}`).not.toContain("후보");
    }
  });
});

const item = (task: MaintenanceItem["task"], text: string): MaintenanceItem => ({
  task,
  text,
  kind: task === "holdings_price" ? "light" : "heavy",
  target: "market_discovery",
  actionLabel: "x",
});

describe("지금 할 일(판정 §3-1)", () => {
  const H_OK: QueryState<EnrichedHoldingsResult> = { phase: "success", stale: false, data: { items: [] } as unknown as EnrichedHoldingsResult };
  it("시장 자료 지연 — 실제 자료일 · 사유 · 갱신 화면 이동(명령 아님) · 이동 후 누를 버튼 이름", () => {
    const t = summaryTasks([item("market_refresh", "KOSPI 원자료가 … 6거래일 지연"), item("other", "구성종목 없음")], false, market(), H_OK, FLOW_OK);
    expect(t.map((x) => x.id)).toEqual(["market_refresh"]);
    expect(t[0].title).toBe("시장 자료 갱신이 필요합니다.");
    expect(t[0].reasons).toEqual(["지금 PC에 저장된 시장 자료: KOSPI 2026-10-22 · ETF 가격 2026-10-23", "KOSPI 원자료가 … 6거래일 지연"]);
    expect(t[0].doText).toContain("[최신 시장 데이터 갱신]");
    expect(t[0].action).toEqual({ label: "시장 자료 갱신 화면", target: { kind: "menu", key: "market_discovery" }, primary: true });
  });
  it("보유 현재가 결측 — 이 화면 [업데이트] 위치로(새 명령 버튼 없음)", () => {
    const t = summaryTasks([item("holdings_price", "보유 종목 현재가를 불러오지 못했습니다 (1건)")], false, market(), H_OK, FLOW_OK);
    expect(t.map((x) => [x.id, x.action?.target.kind])).toEqual([["holdings_price", "scroll"]]);
  });
  it("첫 조회 실패 · 응답 손상 = 상태 모름(미갱신으로 단정 안 함) · 다시 읽는 원천만 [요약 다시 읽기]", () => {
    const t = summaryTasks([item("read_failed", "보유 ETF 비교 자료를 불러오지 못했습니다")], false, ERR, ERR, ERR);
    expect(t.map((x) => x.id)).toEqual(["read_failed", "market_unknown"]);
    expect(t[0].title).toBe("자료 상태를 확인하지 못했습니다. 다시 읽어 주세요.");
    expect(t[0].reasons).toHaveLength(3);
    expect(t[0].action?.target).toEqual({ kind: "reload" });
    // 시장 목록은 다시 읽기 대상이 아니다 — 버튼 없이 새로 고침 안내(검토 지적 2)
    expect(t[1].action).toBeNull();
    expect(t[1].doText).toContain("브라우저를 새로 고치면 다시 읽습니다");
    expect(t.find((x) => x.id === "market_refresh")).toBeUndefined();
  });
  it("시장 목록만 실패 — '다시 읽어 주세요' · 다시 읽기 버튼 없음", () => {
    const H: QueryState<EnrichedHoldingsResult> = { phase: "success", stale: false, data: { items: [] } as unknown as EnrichedHoldingsResult };
    const t = summaryTasks([], false, ERR, H, FLOW_OK);
    expect(t.map((x) => [x.id, x.action])).toEqual([["market_unknown", null]]);
  });
  it("시장 목록 응답이 정상이 아님 · 시장 배경 없음 → KOSPI 항목은 '상태 모름'(갱신 필요로 단정 안 함 · 검토 지적 8b)", () => {
    const H: QueryState<EnrichedHoldingsResult> = { phase: "success", stale: false, data: { items: [] } as unknown as EnrichedHoldingsResult };
    const t = summaryTasks([item("market_unknown", "KOSPI 원자료를 불러오지 못했습니다")], false, market({ status: "invalid", market_context: null }), H, FLOW_OK);
    expect(t.map((x) => x.id)).toEqual(["market_unknown"]);
  });
  it("해소되면 없음 · 확인 중에는 만들지 않음 · 해결 동선 미확인 항목만 있으면 없음", () => {
    expect(summaryTasks([], false, market(), H_OK, FLOW_OK)).toEqual([]);
    expect(summaryTasks([item("market_refresh", "x")], true, market(), H_OK, FLOW_OK)).toEqual([]);
    expect(summaryTasks([item("other", "구성종목 없음")], false, market(), H_OK, FLOW_OK)).toEqual([]);
  });
});

describe("자료 확인 · 연구 줄", () => {
  it("자료 확인 — 기존 건수 · 앞 두 항목 · 투자 위험 표시 아님 · 목록 이동은 보조", () => {
    const r = dataRow([item("market_refresh", "가"), item("other", "나"), item("other", "다")], false, true);
    expect([r.badge, r.text]).toEqual(["자료 최신화 필요 3건", "가 · 나 외 1건"]);
    expect(r.basis).toContain("투자 위험 표시가 아닙니다");
    expect(r.actions.every((a) => !a.primary)).toBe(true);
    expect(dataRow([], false, false).badge).toBe("갱신 필요 없음");
    expect(dataRow([], true, false).badge).toBe("확인 중");
  });
  it("연구 — POC6-15 결론 함수 그대로 · 대기는 할 일이 아님 · 20거래일 문구(판정 §5)", () => {
    const q: QueryState<ForwardComparisonResponse> = { phase: "success", stale: false, data: FWD };
    const r = researchRow(q);
    const c = forwardConclusion(FWD);
    expect([r.tone, r.badge, r.text]).toEqual([c.tone, c.label, `예측과 결과 비교 · ${c.text}`]);
    expect(r.badge).toBe("아직 비교할 결과가 없습니다");
    expect(r.basis).toContain("기준일 뒤 20거래일 자료가 확보되면 결과를 비교합니다");
    expect(r.basis).not.toContain("지나야");
    expect(researchRow(ERR).badge).toBe("불러오지 못함");
  });
});

describe("읽은 시각", () => {
  it("한국 시각 · 없으면 '조회 시각 미확인' · 범위는 가장 이른 ~ 가장 늦은", () => {
    const a = Date.UTC(2026, 10, 1, 17, 25, 0);
    const b = Date.UTC(2026, 10, 1, 17, 31, 5);
    expect(readTimeText(undefined)).toBe("조회 시각 미확인");
    expect(readRangeText([b, undefined, a])).toBe("2026-11-02 02:25:00 ~ 2026-11-02 02:31:05");
    expect(readRangeText([a, a])).toBe("2026-11-02 02:25:00");
    expect(readRangeText([])).toBe("아직 읽은 값이 없습니다");
  });
});

// 검토 지적 3 · 5 · 6 · 8a · 9 · 10 — 이전 값 시각 원천 · 상태 모름 문구 · 원문 미노출 · 연구 안내 · 지속일 없음.
describe("검토 정정", () => {
  const staleAt = Date.UTC(2026, 10, 1, 17, 25, 0);
  const staleQ = <T,>(data: T) => ({ phase: "success", stale: true, successAt: staleAt, data }) as QueryState<T>;
  it("자료 확인 줄 — NAV · 보유 근거 다시 읽기 실패면 그 값을 받은 시각", () => {
    const r = dataRow([item("other", "가")], false, false, staleQ({}) as never, staleQ({}) as never);
    expect(r.staleNote).toBe(
      "ETF 기준가: 다시 읽기 실패 · 2026-11-02 02:25:00에 읽은 값을 표시 중 / 보유 근거: 다시 읽기 실패 · 2026-11-02 02:25:00에 읽은 값을 표시 중",
    );
  });
  it("시장 흐름 줄 — KOSPI 시계열 다시 읽기 실패도 시각", () => {
    expect(marketRow(market(), FLOW_OK, staleQ({}) as never).staleNote).toBe(
      "KOSPI 가격 흐름: 다시 읽기 실패 · 2026-11-02 02:25:00에 읽은 값을 표시 중",
    );
  });
  it("자료 확인 줄 — 불러오지 못한 항목만이면 '오래됨'이라고 쓰지 않음", () => {
    expect(dataRow([item("read_failed", "가")], false, true).basis).toContain("오래됐다는 뜻은 아님");
    expect(dataRow([item("read_failed", "가"), item("other", "나")], false, false).basis).toContain("함께 있습니다");
  });
  it("목록 응답이 정상이 아니면 서버 원문을 옮기지 않는다", () => {
    const r = candidatesRow(market({ status: "invalid", error: "SQLite 조회 실패: OperationalError" }));
    expect(`${r.text} ${r.basis}`).not.toContain("SQLite");
    expect(r.badge).toBe("확인 불가");
  });
  it("연구 — 대시보드에 없는 '아래 안내' 대신 화면 이름", () => {
    const bad = { phase: "success", stale: false, data: { ...FWD, basis: { ...FWD.basis!, unreadable_runs: ["r1"] } } } as QueryState<ForwardComparisonResponse>;
    const r = researchRow(bad);
    expect(r.text).toContain("「예측과 결과 비교」에서 안내를 확인해 주세요");
    expect(r.text).not.toContain("아래 안내");
  });
  it("연속 일수 없음 — KOSPI 카드처럼 '지속일 자료 없음'", () => {
    expect(marketRow(market({}, { regime_streak: null }), FLOW_OK).badge).toBe("하락장 · 지속일 자료 없음");
  });
});

// 검증자 r1 F1 — 첫 조회 실패(이전 값 없음)도 줄 · 할 일에 남는다 · F2 — 연구 줄에 실제 예측 기준일.
describe("검증자 r1 정정", () => {
  const H_OK: QueryState<EnrichedHoldingsResult> = { phase: "success", stale: false, data: { items: [] } as unknown as EnrichedHoldingsResult };
  it("KOSPI 가격 흐름 첫 조회 실패 — 시장 흐름 줄 메모 · 다시 읽기 할 일", () => {
    expect(marketRow(market(), FLOW_OK, ERR as never).staleNote).toBe("KOSPI 가격 흐름: 불러오지 못했습니다(이전 값 없음)");
    const t = summaryTasks([], false, market(), H_OK, FLOW_OK, ERR as never, undefined);
    expect(t.map((x) => x.id)).toEqual(["read_failed"]);
    expect(t[0].reasons).toEqual(["KOSPI 가격 흐름 자료를 불러오지 못했습니다"]);
  });
  it("연구 기록 첫 조회 실패 — 다시 읽기 할 일", () => {
    const t = summaryTasks([], false, market(), H_OK, FLOW_OK, undefined, ERR as never);
    expect(t[0].reasons).toEqual(["예측과 결과 비교 기록을 불러오지 못했습니다"]);
  });
  it("정비 점검 원천(보유 · 시장 목록)이 첫 조회 실패면 빈 정비 목록을 '갱신 필요 없음'으로 정리하지 않음", () => {
    const r = dataRow([], false, true, undefined, undefined, ["보유"]);
    expect([r.tone, r.badge, r.text]).toEqual(["bad", "일부 확인 못함", "보유 자료를 불러오지 못해 확인하지 못했습니다"]);
    expect(r.basis).toContain("갱신이 필요한지 알 수 없습니다");
    const mixed = dataRow([item("other", "가")], false, false, undefined, undefined, ["시장 판정 · 요즘 잘 오르는 ETF 목록"]);
    expect(mixed.text).toBe("가 · 시장 판정 · 요즘 잘 오르는 ETF 목록 자료를 불러오지 못해 확인하지 못했습니다");
    expect(mixed.basis).toContain("함께 있습니다");
    expect(dataRow([], false, false, undefined, undefined, []).badge).toBe("갱신 필요 없음");
  });
  it.each([
    ["기록 목록과 보고 범위가 다름 — 따로", FWD, "예측이 기록된 기준일 2개(2026-10-27 ~ 2026-10-29) · 비교 보고에 들어간 기준일 3개(2026-10-22 ~ 2026-10-29)"],
    ["보고 없음 — 기록 목록만", { ...FWD, report: { state: "NONE", selected_D: "RUN_REPORT_MISSING" } }, "예측이 기록된 기준일 2개(2026-10-27 ~ 2026-10-29)"],
    ["같은 범위 — 한 번만", { ...FWD, dates: [{ D: "2026-10-22", primary_rows: 24 }, { D: "2026-10-27", primary_rows: 24 }, { D: "2026-10-29", primary_rows: 24 }] }, "예측이 기록된 기준일 3개(2026-10-22 ~ 2026-10-29)"],
    ["예측 기록 없음", { ...FWD, status: "NO_RECORDS", dates: [], report: null }, "예측이 기록된 기준일 없음"],
  ])("연구 예측 기준일 — %s", (_n, d, want) => {
    expect(researchDates(d as ForwardComparisonResponse)).toBe(want);
    const r = researchRow({ phase: "success", stale: false, data: d as ForwardComparisonResponse });
    expect(r.basis?.startsWith(want)).toBe(true);
    expect(r.basis).toContain("기준일 뒤 20거래일 자료가 확보되면 결과를 비교합니다");
  });
});

// 검증자 r2 F3 — 자료 확인 줄의 뜻 = 정비 항목 구성(없음 · 불러오지 못함만 · 오래됨/없음만 · 섞임) × 확인 못한 원천(없음 · 있음) 8조합.
//   '함께 있습니다'는 오래됨/없음이 실제로 확인된 항목이 있을 때만(확인 못한 원천은 오래됨의 근거가 아님).
describe("자료 확인 줄 뜻 — 8조합", () => {
  const U = item("read_failed", "ETF 기준가 자료를 불러오지 못했습니다");
  const S = item("other", "ETF가 담고 있는 종목 자료가 없습니다 (25건)");
  const MEAN = {
    ok: null,
    unknownOnlyNoItems: "갱신이 필요한지 알 수 없습니다(오래됐다는 뜻은 아님)",
    unknown: "자료를 불러오지 못한 항목입니다(오래됐다는 뜻은 아님)",
    stale: "자료가 오래됐거나 없다는 뜻이며",
    mixed: "오래됐거나 없는 자료와 불러오지 못한 자료가 함께 있습니다",
  };
  it.each([
    ["항목 없음 · 확인 못한 원천 없음", [], [], "갱신 필요 없음", MEAN.ok],
    ["항목 없음 · 확인 못한 원천 있음", [], ["보유"], "일부 확인 못함", MEAN.unknownOnlyNoItems],
    ["불러오지 못함만 · 원천 없음", [U], [], "자료 최신화 필요 1건", MEAN.unknown],
    ["불러오지 못함만 · 원천 있음(보유 + NAV 실패)", [U], ["보유"], "자료 최신화 필요 1건", MEAN.unknown],
    ["불러오지 못함만 · 원천 있음(시장 목록 + NAV 실패)", [U], ["시장 판정 · 요즘 잘 오르는 ETF 목록"], "자료 최신화 필요 1건", MEAN.unknown],
    ["오래됨/없음만 · 원천 없음", [S], [], "자료 최신화 필요 1건", MEAN.stale],
    ["오래됨/없음만 · 원천 있음", [S], ["보유"], "자료 최신화 필요 1건", MEAN.mixed],
    ["섞임 · 원천 없음", [S, U], [], "자료 최신화 필요 2건", MEAN.mixed],
    ["섞임 · 원천 있음", [S, U], ["보유"], "자료 최신화 필요 2건", MEAN.mixed],
  ] as [string, MaintenanceItem[], string[], string, string | null][])("%s", (_n, items, unknownSources, badge, meaning) => {
    const r = dataRow(items, false, false, undefined, undefined, unknownSources);
    expect(r.badge).toBe(badge);
    if (meaning === null) expect(r.basis).toBeNull();
    else expect(r.basis).toContain(meaning);
    // 오래됨/없음 항목이 없으면 '오래됐거나 없는 자료'라고 말하지 않는다
    if (!items.some((it) => it.task === "other")) expect(r.basis ?? "").not.toContain("오래됐거나 없는");
    // 확인 못한 원천은 줄 본문에 남는다
    for (const u of unknownSources) expect(r.text).toContain(u);
  });
});
