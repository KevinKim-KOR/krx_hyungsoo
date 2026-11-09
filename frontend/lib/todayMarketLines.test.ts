// POC6-27 — 시장 흐름 문장(설계 §3 · PLAN 판정 §2 · §4 · RESULT 판정 §3-1): 종가 ≠ 비교 기준값 · 비교 날짜는 실제 날짜로 ·
// 최근 큰 변화는 저점 문장과 발생일 · 방향 · 비교일 · 기준값이 모두 같은 코스피 범위 사건 1건만 뺀다.
import { describe, it, expect } from "vitest";
import type { FlowEvent } from "@/lib/api/marketFlow";
import { EVENTS_1109, OBS_1106, flowWith } from "./todayMarketTestFixtures";
import { eventSentence, isRealDate, isSameAsLow, josa, kospiObs, lowSentence, md, parseIsoInstant, recentChanges, wonAbs } from "./todayMarketLines";

describe("저점 문장 — 종가와 비교 기준값을 나눈다(판정 §4)", () => {
  it("비교 날짜를 직접 적는다 — 11/9 사례 '11/5의 최근 저점 …'('직전 거래일'로 부르지 않음 · RESULT 판정 §3-1)", () => {
    expect(lowSentence(OBS_1106)).toBe("11/5의 최근 저점 5,383.80을 밑돌았습니다.");
  });
  it("중간 거래일 저장 종가가 비어도 실제 비교 날짜(11/5 없음 → 11/4)", () => {
    const gap = { ...OBS_1106, d1: { from_date: "2026-11-04", diff: -400, pct: -7.3 }, range: { dir: "아래" as const, bound: 5459.69, bound_date: "2026-11-04" } };
    expect(lowSentence(gap)).toBe("11/4의 최근 저점 5,459.69를 밑돌았습니다.");
    expect(lowSentence(gap)).not.toContain("직전");
  });
  it("기준값 날짜가 다르면 그 실제 날짜", () => {
    expect(lowSentence({ ...OBS_1106, range: { dir: "아래", bound: 5469.47, bound_date: "2026-10-26" } })).toBe(
      "10/26의 최근 저점 5,469.47을 밑돌았습니다.",
    );
  });
  it("위로 벗어나면 고점 · 범위 안이면 문장 없음", () => {
    expect(lowSentence({ ...OBS_1106, range: { dir: "위", bound: 6000, bound_date: "2026-10-20" } })).toBe(
      "10/20의 최근 고점 6,000.00을 넘었습니다.",
    );
    expect(lowSentence({ ...OBS_1106, range: null })).toBeNull();
    expect(lowSentence(null)).toBeNull();
  });
});

describe("최근 큰 변화 — 정확히 같은 사건만 뺀다(판정 §2)", () => {
  it("11/9 사례: 7건 − 저점 문장 1건 − 보인 2건 = 외 4건 · 날짜와 변화를 먼저", () => {
    const r = recentChanges(flowWith(), true);
    expect(r.shown).toEqual([
      "11/5 코스피 종가 5,383.80이 10/26 저점 5,469.47을 밑돌았습니다",
      "11/4 WTI가 7.97달러 하락했습니다 · 평소 변화의 3.4배",
    ]);
    expect([r.rest, r.excluded]).toEqual([4, 1]);
  });
  it("저점 문장을 보이지 않았으면 빼지 않는다", () => {
    const r = recentChanges(flowWith(), false);
    expect(r.shown[0]).toBe("11/6 코스피 종가 5,059.69가 11/5 저점 5,383.80을 밑돌았습니다");
    expect([r.rest, r.excluded]).toEqual([5, 0]);
  });
  it.each([
    ["발생일", { date: "2026-11-05" }],
    ["방향", { dir: "위" as const }],
    ["비교일", { bound_date: "2026-11-04" }],
    ["기준값", { bound: 5383.81 }],
    ["종류(같은 날 다른 종류 사건)", { kind: "expansion" }],
    ["자료(같은 날 다른 자료)", { key: "wti" as const }],
  ])("%s가 다르면 같은 사건이 아니다", (_n, over) => {
    expect(isSameAsLow({ ...EVENTS_1109[0], ...over } as FlowEvent, OBS_1106)).toBe(false);
  });
  it("모두 같을 때만 같은 사건", () => {
    expect(isSameAsLow(EVENTS_1109[0], OBS_1106)).toBe(true);
  });
  it("사건이 없으면 서버 '없음' 문장 · 확인 못 한 자료 문장은 그대로", () => {
    const r = recentChanges(flowWith({ events: [], event_check: { checked: [], unchecked: [], unchecked_text: "원/달러 비교 자료 부족", empty_text: "최근 큰 변화 없음" } }), true);
    expect([r.shown, r.empty, r.unchecked]).toEqual([[], "최근 큰 변화 없음", "원/달러 비교 자료 부족"]);
  });
  it("구조 칸이 없는 옛 응답은 서버 원문 줄 + '괄호 안 = 비교 기준값'", () => {
    const legacy = EVENTS_1109.map(({ date, series, kind, text }) => ({ date, series, kind, text }));
    const r = recentChanges(flowWith({ events: legacy }), true);
    expect(r.legacy).toBe(
      "최근 큰 변화: 11/6 코스피 직전 20개 관측 범위 아래(5,383.80 · 11/5 밑) · … 외 5건 (괄호 안 = 비교 기준값)",
    );
    expect(r.shown).toEqual([]);
  });
});

describe("검증자 r1 F2 — 날짜는 달력 날짜로만", () => {
  it("isRealDate · parseIsoInstant · md", () => {
    expect([isRealDate("2026-11-06"), isRealDate("2028-02-29"), isRealDate("2026-13-01"), isRealDate("2026-02-29"), isRealDate("2026-11-31")]).toEqual([
      true, true, false, false, false,
    ]);
    expect(parseIsoInstant("2026-10-23T08:30:02.123456+09:00")?.toISOString()).toBe("2026-10-22T23:30:02.123Z");
    expect(parseIsoInstant("2026-02-30T08:30:02+09:00")).toBeNull();
    expect(parseIsoInstant("2026-11-06T08:30:02+15:00")).toBeNull();
    expect(md("2026-11-05")).toBe("11/5");
    expect(md("2026-13-01")).toBe("2026-13-01"); // '13/1' 처럼 날짜인 척하지 않음
  });
  it("기준값 날짜가 깨졌으면 받은 글자 그대로(날짜인 척하지 않음)", () => {
    const bad = { ...OBS_1106, d1: { ...OBS_1106.d1, from_date: "2026-13-01" }, range: { ...OBS_1106.range, bound_date: "2026-13-01" } };
    expect(lowSentence(bad)).toBe("2026-13-01의 최근 저점 5,383.80을 밑돌았습니다.");
  });
});

describe("사건 문장 · 형식", () => {
  it("범위 위 · 변화 확대 · 수급", () => {
    expect(eventSentence(EVENTS_1109[5])).toBe("11/3 원/달러 1,362.04원이 10/6 고점 1,343.75원을 넘었습니다");
    expect(eventSentence(EVENTS_1109[4])).toBe("11/3 원/달러가 19.29원 상승했습니다 · 평소 변화의 4.6배");
    expect(eventSentence({ date: "2026-11-05", series: "외국인", kind: "flow", text: "…", key: "foreign", value: -3.4e12, unit: "원", ratio: 2.1 })).toBe(
      "11/5 외국인 순매도 3.4조원 · 직전 20거래일 평균 규모의 2.1배",
    );
  });
  it("조사 · 금액 형식", () => {
    expect(josa("5,383.80", "이", "가")).toBe("5,383.80이");
    expect(josa("88.28달러", "을", "를")).toBe("88.28달러를");
    expect(josa("WTI", "이", "가")).toBe("WTI가");
    expect(wonAbs(-164308100000000)).toBe("164.3조원");
    expect(wonAbs(924600000000)).toBe("9,246억원");
  });
  it("코스피 관측값은 구조 칸에서만(문장 파싱 없음)", () => {
    expect(kospiObs(flowWith())?.value).toBe(5059.69);
    expect(kospiObs(flowWith({ short_lines: [{ text: "코스피 11/6 · 직전 대비 -324.11pt", flags: [] }] }))).toBeNull();
  });
});
