// POC6-29 보완 R1 · R2 — '지금 시장' 빠른 시세 3칸 · 흐름 문장 · ⓪ 결과 줄(보완 PLAN 판정 '구현에서 확인할 세 가지' 1).
import { describe, it, expect } from "vitest";
import type { MarketRiskVix } from "./api/market";
import type { MarketContext } from "./api/marketEvidence";
import type { FlowEvent, MarketFlowContext } from "./api/marketFlow";
import {
  flowsSentence,
  fxwtiSentence,
  kstMdHm,
  quickResultLine,
  quoteView,
  regimeSentence,
  roAfterNumber,
  vixSentence,
} from "./marketNowText";
import { QUICK_FETCHED, quickItems } from "./quickQuotesTestFixtures";

describe("kstMdHm — 한국 시각 'M/D HH:MM'", () => {
  it.each([
    ["2026-11-12T15:36:00+09:00", "11/12 15:36"],
    ["2026-11-12T06:56:13Z", "11/12 15:56"],
    ["2026-11-11T23:30:00Z", "11/12 08:30"],
    ["2026-02-30T10:00:00+09:00", "2026-02-30T10:00:00+09:00"],
    [null, "확인 불가"],
  ])("%s → %s", (iso, want) => {
    expect(kstMdHm(iso)).toBe(want);
  });
});

describe("quoteView — 빠른 시세 한 칸", () => {
  const [kospi, , kodex] = quickItems();

  it("마감 · 지수 = 소수 둘째 자리 · KODEX 200 = 원 · 등락 부호 · 색 방향 · 원천 시각과 조회 시각을 따로", () => {
    expect(quoteView(kospi)).toMatchObject({
      label: "코스피",
      badge: "마감",
      value: "5,342.73",
      change: "-32.63 (-0.61%)",
      dir: "down",
      time: "시세 시각 11/12 15:36",
      fetched: "조회 11/12 15:36",
      note: null,
      warn: false,
    });
    expect(quoteView(kodex)).toMatchObject({ value: "84,240원", change: "-300원 (-0.35%)" });
  });

  it.each<[string | null, string]>([
    ["OPEN", "장중"],
    ["CLOSE", "마감"],
    ["PREOPEN", "장 상태 확인 필요"],
    [null, "장 상태 확인 필요"],
  ])("장 상태 %s → 배지 %s", (status, badge) => {
    const it0 = { ...kospi, quote: { ...kospi.quote!, market_status: status } };
    expect(quoteView(it0).badge).toBe(badge);
  });

  it("'변동 없음' = 저장 시세 · 시세 시각은 이전 그대로 · 조회 시각은 이번 확인 시각 + '시세 변동 없음'", () => {
    const v = quoteView({ ...kospi, last_attempt: { at: "2026-11-12T15:58:04+09:00", status: "unchanged", reason: null } });
    expect(v.time).toBe("시세 시각 11/12 15:36");
    expect(v.fetched).toBe("조회 11/12 15:58 · 시세 변동 없음");
    expect(v.warn).toBe(false);
  });

  it("오르면 + · up · 변화 0 이면 색 없음", () => {
    expect(quoteView({ ...kospi, quote: { ...kospi.quote!, change: 12.5, change_pct: 0.23 } })).toMatchObject({
      change: "+12.50 (+0.23%)",
      dir: "up",
    });
    expect(quoteView({ ...kospi, quote: { ...kospi.quote!, change: 0, change_pct: 0 } }).dir).toBeNull();
  });

  it("성공 기록 없음 = '시세 미확인'(받는 방법) · 기록 없이 실패 = 실패 사유 · 시각 · 성공 뒤 실패 = 이전 값 + 실패 안내", () => {
    expect(quoteView({ ...kospi, quote: null, last_attempt: null })).toMatchObject({
      value: null,
      note: "시세 미확인 · [최신 자료 갱신]을 누르면 받습니다",
      warn: false,
    });
    expect(
      quoteView({ ...kospi, quote: null, last_attempt: { at: QUICK_FETCHED, status: "failed", reason: "http_error" } }),
    ).toMatchObject({ value: null, note: "시세 미확인 · 받지 못했습니다(연결 실패 · 11/12 15:36)", warn: true });
    const v = quoteView({ ...kospi, last_attempt: { at: "2026-11-12T16:00:00+09:00", status: "failed", reason: "weird" } });
    expect(v.value).toBe("5,342.73");
    expect(v.note).toBe("마지막 조회 실패(원인 미상 · 11/12 16:00) · 위 값은 이전에 받은 시세입니다");
    expect(v.warn).toBe(true);
  });
});

function ctx(over: Partial<MarketContext> = {}): MarketContext {
  return {
    status: "ok",
    asof: "2026-11-12",
    primary_benchmark: "069500",
    regime_label: "하락장",
    regime_code: "bear",
    regime_score: -4,
    regime_reasons: ["KODEX200 20거래일 수익률 -2.14%", "현재가가 20일 이동평균 아래"],
    kodex200: { status: "ok" } as MarketContext["kodex200"],
    kospi: { status: "ok" } as MarketContext["kospi"],
    regime_streak: { streak_days: 25, at_least: false },
    warnings: [],
    ...over,
  };
}

describe("regimeSentence — 국면 · 판정 근거 · 기준", () => {
  it("국면(지속일) · 서버 근거 문장 그대로 · 기준 = KODEX 200 저장 시각(있으면) 아니면 날짜", () => {
    expect(regimeSentence(ctx(), "하락장", "KODEX 200 11/12 가격(15:56 마감 뒤 저장)")).toEqual({
      key: "regime",
      text: "국내 시장은 하락장(25거래일째)입니다. 판정 근거: KODEX200 20거래일 수익률 -2.14% · 현재가가 20일 이동평균 아래.",
      basis: "KODEX 200 11/12 가격(15:56 마감 뒤 저장)",
      stale: null,
    });
    const s = regimeSentence(ctx({ regime_reasons: [], regime_streak: { streak_days: 30, at_least: true } }), "하락장", null)!;
    expect(s.text).toBe("국내 시장은 하락장(30거래일째 이상)입니다.");
    // 저장 시점을 붙일 수 없으면 판정이 쓴 날짜만(저장 시점 확인 필요 · 검증자 F4)
    expect(s.basis).toBe("KODEX 200 11/12 가격 기준(저장 시점 확인 필요)");
    // 판정이 쓴 날짜 = 같은 이력의 끝일(return_end_date)이 asof 보다 우선
    const k = ctx().kodex200;
    expect(regimeSentence(ctx({ kodex200: { ...k, return_end_date: "2026-11-11" } }), "하락장", null)!.basis).toBe(
      "KODEX 200 11/11 가격 기준(저장 시점 확인 필요)",
    );
    expect(regimeSentence(ctx({ regime_streak: null }), "중립", null)!.text).toMatch(/^국내 시장은 중립입니다\./);
    expect(regimeSentence(null, "", null)).toBeNull();
  });
});

// 2026-11-14 운영 화면 'VIX … 18.70로' 정정 — 끝 숫자 소리의 받침(ㄹ 제외)이면 '으로'
describe("roAfterNumber — 숫자 뒤 '(으)로'", () => {
  it.each([
    ["18.70", "으로"], ["17.43", "으로"], ["17.46", "으로"],
    ["17.41", "로"], ["17.42", "로"], ["17.44", "로"], ["17.45", "로"], ["17.47", "로"], ["17.48", "로"], ["17.49", "로"],
  ])("%s → %s", (n, want) => {
    expect(roAfterNumber(n)).toBe(want);
  });
  it("VIX 문장에 그대로 — 18.70으로 · 17.49로", () => {
    const base = { availability: "available", change_1d_pct: 6.92, change_5d_pct: 1, as_of_date: "2026-11-12" } as MarketRiskVix;
    expect(vixSentence({ ...base, close: 18.7 })?.text).toBe("VIX(미국 변동성)는 18.70으로 전일보다 6.92% 높아졌습니다.");
    expect(vixSentence({ ...base, close: 18.7, change_1d_pct: 0 })?.text).toBe("VIX(미국 변동성)는 18.70으로 전일과 같습니다.");
    expect(vixSentence({ ...base, close: 17.49 })?.text).toBe("VIX(미국 변동성)는 17.49로 전일보다 6.92% 높아졌습니다.");
  });
});

describe("vixSentence — 값 · 변화 · 미국 날짜 · 기존 최신성", () => {
  const vix = (over: Partial<MarketRiskVix> = {}): MarketRiskVix =>
    ({ availability: "available", close: 17.49, change_1d_pct: -10.12, change_5d_pct: 5.3, as_of_date: "2026-11-11", ...over }) as MarketRiskVix;
  it.each([
    [-10.12, "VIX(미국 변동성)는 17.49로 전일보다 10.12% 낮아졌습니다."],
    [3.5, "VIX(미국 변동성)는 17.49로 전일보다 3.50% 높아졌습니다."],
    [0, "VIX(미국 변동성)는 17.49로 전일과 같습니다."],
    [null, "VIX(미국 변동성)는 17.49입니다."],
  ])("전일 대비 %s", (c, want) => {
    const s = vixSentence(vix({ change_1d_pct: c as number | null }))!;
    expect(s.text).toBe(want);
    expect(s.basis).toBe("11/11 미국");
  });
  it("자료 없음 · 값 없음 = null(호출자가 '확인되지 않음' 문장)", () => {
    expect(vixSentence(vix({ availability: "unavailable" }))).toBeNull();
    expect(vixSentence(vix({ close: null }))).toBeNull();
    expect(vixSentence(null)).toBeNull();
  });
});

function flow(over: Partial<MarketFlowContext> = {}): MarketFlowContext {
  return {
    has_flows: true,
    periods: {},
    windows: {
      lines: [],
      trend: "직전 20거래일보다 일평균 매도 감소",
      foreign20: {
        recent: { sum: -21.179e12, avg: -1.05895e12, from: "2026-10-13", to: "2026-11-09" },
        previous: { sum: -31.3538e12, avg: -1.56769e12, from: "2026-09-09", to: "2026-10-12" },
      },
      r60: { institution: { sum: 11.0198e12, from: "2026-08-11", to: "2026-11-09" } },
    },
    short_lines: [],
    events: [],
    status: [],
    freshness: {
      today_kst: "2026-11-12",
      expected_kr: "2026-11-11",
      expected_kr_basis: "weekday_fallback",
      items: [{ key: "flows", label: "외국인 수급", last_date: "2026-11-09", expected: "2026-11-11", basis: "", state: "late", behind: 2, reason: null }],
    },
    ...over,
  } as unknown as MarketFlowContext;
}

describe("flowsSentence — 외국인 20거래일 · 기관 60거래일 · 기준일 · 늦음", () => {
  it("서버 창 계산 그대로(하루 평균 · 직전 · 추세 · 기관 합) · 마지막 날짜 · 2거래일 늦음", () => {
    expect(flowsSentence(flow())).toEqual({
      key: "flows",
      text:
        "외국인은 최근 20거래일(10/13 ~ 11/9) 하루 평균 1.1조원 순매도입니다(직전 20거래일 1.6조원 순매도 · 직전 20거래일보다 일평균 매도 감소). " +
        "기관은 최근 60거래일(8/11 ~ 11/9) 11.0조원 순매수입니다.",
      basis: "11/9까지",
      stale: "2거래일 늦음",
    });
  });
  it("수급 자료 없음 · 창 계산 없음 · 응답 없음", () => {
    expect(flowsSentence(flow({ has_flows: false }))!.text).toBe("투자자별 수급 자료가 없습니다.");
    expect(flowsSentence(flow({ windows: { lines: [] } as MarketFlowContext["windows"] }))).toBeNull();
    expect(flowsSentence(null)).toBeNull();
  });
});

describe("fxwtiSentence — 원/달러 · WTI 값 + 자료별 가장 최근 사건(최대 2건 · 아래 목록에서 뺄 것)", () => {
  const obs = (date: string, value: number, diff: number) => ({ date, value, d1: { from_date: "x", diff, pct: 0 }, range: null });
  const ev = (key: FlowEvent["key"], date: string, text: string, extra: Partial<FlowEvent> = {}): FlowEvent => ({
    date,
    series: String(key),
    kind: "expansion",
    text,
    key,
    value: 1,
    unit: key === "usdkrw" ? "원" : "달러",
    delta: -1,
    ratio: 3.2,
    ...extra,
  });
  const base = flow({
    short_lines: [
      { key: "usdkrw", obs: obs("2026-11-11", 1341.91, -1.93) },
      { key: "wti", obs: obs("2026-11-10", 86.04, -0.81) },
    ] as unknown as MarketFlowContext["short_lines"],
  });

  it("사건이 각 자료마다 있으면 날짜가 가장 최근(응답 순서 첫 번째) 1건씩 · 코스피 · 수급 사건은 넣지 않음", () => {
    const evs = [
      ev("kospi", "2026-11-10", "k"),
      ev("usdkrw", "2026-11-10", "u1", { delta: -18.86 }),
      ev("wti", "2026-11-10", "w1", { kind: "range", bound: 86.85, bound_date: "2026-11-09", dir: "아래", value: 86.04 }),
      ev("usdkrw", "2026-11-09", "u2"),
    ];
    const r = fxwtiSentence({ ...base, events: evs } as MarketFlowContext);
    expect(r.merged).toEqual([evs[1], evs[2]]);
    expect(r.sentence!.text).toBe(
      "원/달러는 11/11 1,341.91원(직전 대비 -1.93원), WTI는 11/10 86.04달러(직전 대비 -0.81달러)입니다. " +
        "11/10 원/달러가 18.86원 하락했습니다 · 평소 변화의 3.2배. 11/10 WTI 86.04달러가 11/9 저점 86.85달러를 밑돌았습니다.",
    );
  });

  it("구조 칸 없는 옛 사건 = 합치지 않음 · 값 · 사건 모두 없으면 null", () => {
    const old = fxwtiSentence({ ...base, events: [{ date: "2026-11-10", series: "원/달러", kind: "x", text: "옛 문장" }] } as MarketFlowContext);
    expect(old.merged).toEqual([]);
    expect(old.sentence!.text).toBe("원/달러는 11/11 1,341.91원(직전 대비 -1.93원), WTI는 11/10 86.04달러(직전 대비 -0.81달러)입니다.");
    expect(fxwtiSentence(flow()).sentence).toBeNull();
    expect(fxwtiSentence(null)).toEqual({ sentence: null, merged: [] });
  });
});

describe("quickResultLine — ⓪ 결과(새로 받음 · 변동 없음 · 항목별 실패 · 전체 실패)", () => {
  const items = quickItems();
  it.each([
    [
      "모두 새로 · 같은 장 상태",
      { status: "done", items: { KOSPI: { status: "updated" }, KOSDAQ: { status: "updated" }, "069500": { status: "updated" } } },
      items,
      "⓪ 코스피 · 코스닥 · KODEX 200 새 시세 받음(시세 시각 11/12 15:36 · 마감)",
      false,
    ],
    [
      "마감 뒤 시각만 바뀜 = 변동 없음",
      { status: "done", items: { KOSPI: { status: "unchanged" }, KOSDAQ: { status: "unchanged" }, "069500": { status: "updated" } } },
      items,
      "⓪ KODEX 200 새 시세 받음(시세 시각 11/12 15:35 · 마감) · 코스피 · 코스닥 조회 성공 · 시세 변동 없음",
      false,
    ],
    [
      "일부 실패 = 마지막 시세 시각 · 기록 없으면 시세 미확인",
      { status: "partial", items: { KOSPI: { status: "failed", reason: "timeout" }, KOSDAQ: { status: "failed", reason: "http_error" }, "069500": { status: "unchanged" } } },
      quickItems({ KOSDAQ: { quote: null } }),
      "⓪ KODEX 200 조회 성공 · 시세 변동 없음 · 코스피 받지 못함(응답 시간 초과) — 마지막 시세 11/12 15:36 표시 · 코스닥 받지 못함(연결 실패) — 시세 미확인",
      true,
    ],
  ])("%s", (_t, step, its, text, warn) => {
    expect(quickResultLine(step, its)).toEqual({ text, warn });
  });

  it("항목 결과가 없는 실패(예외 · 저장 실패) = 전체 실패 + 다른 단계는 이어서 · 다시 읽기 실패여도 이름은 코드표로", () => {
    expect(quickResultLine({ status: "failed", items: {}, message: "빠른 시세를 받는 중 오류가 났습니다." }, null)).toEqual({
      text: "⓪ 빠른 시세를 받지 못했습니다(빠른 시세를 받는 중 오류가 났습니다.) · 보유 · 시장 단계는 이어서 진행합니다",
      warn: true,
    });
    expect(quickResultLine({ status: "done", items: { KOSPI: { status: "unchanged" } } }, null).text).toBe(
      "⓪ 코스피 조회 성공 · 시세 변동 없음",
    );
  });
});
