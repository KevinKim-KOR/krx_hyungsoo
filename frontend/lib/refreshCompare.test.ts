// POC6-29 보완 R2 — 시장 갱신 전후 대조(날짜 + 저장 시각 + 값 · 보완 PLAN 판정 '구현에서 확인할 세 가지' 2).
import { describe, it, expect } from "vitest";
import { detailItem, detailResponse } from "./etfCompareTestFixtures";
import { compareSource, kodexSnap, snapshotText, storedRowText, type SourceSnap, type Snapshot } from "./refreshCompare";

const snap = (date: string | null, saved: string | null = null, value: number | null = null, state: string | null = null): SourceSnap => ({
  date,
  saved,
  state,
  value,
});

function kodex(state: "intraday" | "after_close" | "unknown", date: string, fetched: string, close: number) {
  return detailResponse([], {
    items: [
      detailItem("069500", {
        end_price: { date, state, fetched_at_kst: fetched },
        daily: { status: "ok", value: 0.6, start: "2026-11-11", end: date, start_close: 84540, end_close: close, reason: null },
      }),
    ],
  });
}

describe("kodexSnap — KODEX 200 상세의 끝일 가격 · 저장 시각 · 가격 시점(대체값 없음)", () => {
  it("상세 그대로 · 상세 없음 · 실패 · 069500 없음 = 모두 비움(다른 응답 날짜로 채우지 않음)", () => {
    expect(kodexSnap(kodex("intraday", "2026-11-12", "2026-11-12T09:53:21+09:00", 85045))).toEqual(
      snap("2026-11-12", "2026-11-12T09:53:21+09:00", 85045, "intraday"),
    );
    const empty = snap(null);
    expect(kodexSnap(null)).toEqual(empty);
    expect(kodexSnap(detailResponse([], { status: "invalid", items: [] }))).toEqual(empty);
    expect(kodexSnap(detailResponse(["000001"]))).toEqual(empty);
  });

  // 당일 판정 문장의 기준 — 판정이 쓴 끝 행(아침 기준 응답 today_regime.basis_row · 같은 한 번 읽기)의 저장 시점만.
  it.each<[string, { date: string; state: string | null; fetched_at_kst: string | null }, string]>([
    ["같은 날 마감 뒤", { date: "2026-11-12", state: "after_close", fetched_at_kst: "2026-11-12T15:56:59+09:00" }, "KODEX 200 11/12 가격(15:56 마감 뒤 저장)"],
    ["같은 날 장중", { date: "2026-11-12", state: "intraday", fetched_at_kst: "2026-11-12T09:53:21+09:00" }, "KODEX 200 11/12 가격(09:53 장중 저장)"],
    ["다음 날 저장 = 날짜까지", { date: "2026-11-09", state: "after_close", fetched_at_kst: "2026-11-10T13:18:02+09:00" }, "KODEX 200 11/9 가격(11/10 13:18 마감 뒤 저장)"],
    ["저장 시각 모름", { date: "2026-11-12", state: "unknown", fetched_at_kst: null }, "KODEX 200 11/12 가격(저장 시점 확인 필요)"],
    ["시각은 있으나 장중 · 마감 뒤 판단 불가(가격 날짜보다 앞선 시각)", { date: "2026-11-12", state: "unknown", fetched_at_kst: "2026-11-11T16:00:00+09:00" }, "KODEX 200 11/12 가격(11/11 16:00 저장 · 장중인지 마감 뒤인지 확인 필요)"],
  ])("storedRowText — %s", (_t, row, want) => {
    expect(storedRowText(row)).toBe(want);
  });
});

describe("snapshotText — 지금 표시 중인 값의 기준(대기 · 다시 읽기 실패 줄)", () => {
  it("ETF 가격만 저장 시각 · 가격 시점까지 · 없으면 확인 불가", () => {
    const s: Snapshot = {
      etf: snap("2026-11-12", "2026-11-12T09:53:21+09:00", 85045, "intraday"),
      kospi: snap("2026-11-09", "2026-11-10T13:21:00+09:00", 5018.85),
      flows: snap(null),
      usdkrw: snap("2026-11-11"),
      wti: snap("2026-11-10"),
      vix: snap("2026-11-11", null, 17.49),
    };
    expect(snapshotText(s)).toBe(
      "ETF 가격 11/12(09:53 장중 저장) · 코스피 공식 종가 11/9 · 외국인 수급 확인 불가 · 원/달러 11/11 · WTI 11/10 · VIX 11/11",
    );
  });
});

describe("compareSource — 자료 한 칸의 전후 대조(조합)", () => {
  it.each<[string, Parameters<typeof compareSource>[0], SourceSnap, SourceSnap, string]>([
    ["다시 읽은 뒤 없음", "kospi", snap("2026-11-09"), snap(null), "라벨 확인 불가"],
    ["처음 생김", "kospi", snap(null), snap("2026-11-11"), "라벨 없음 → 11/11"],
    ["날짜 바뀜", "flows", snap("2026-11-09", "a"), snap("2026-11-11", "b"), "라벨 11/9 → 11/11"],
    [
      "같은 거래일 다시 받음(재현 사례 · 값 · 가격 시점)",
      "etf",
      snap("2026-11-12", "2026-11-12T09:53:21+09:00", 85045, "intraday"),
      snap("2026-11-12", "2026-11-12T15:56:59+09:00", 84240, "after_close"),
      "라벨 11/12 같은 거래일에 다시 받음(09:53 장중 → 15:56 마감 뒤 저장 · KODEX 200 85,045원 → 84,240원)",
    ],
    [
      "같은 거래일 다시 받음 · 값 같음 · 저장일이 자료일과 다르면 저장 날짜까지(11/11 자료를 11/12 에 두 번 저장)",
      "usdkrw",
      snap("2026-11-11", "2026-11-12T09:56:08+09:00", 1341.91),
      snap("2026-11-11", "2026-11-12T15:59:47+09:00", 1341.91),
      "라벨 11/11 같은 거래일에 다시 받음(11/12 09:56 → 11/12 15:59 저장)",
    ],
    [
      "같은 거래일 다시 받음 · 같은 날 저장 = 시각만",
      "wti",
      snap("2026-11-12", "2026-11-12T09:56:08+09:00", 86.04),
      snap("2026-11-12", "2026-11-12T15:59:47+09:00", 86.04),
      "라벨 11/12 같은 거래일에 다시 받음(09:56 → 15:59 저장)",
    ],
    [
      "다음 날 저장 → 저장 날짜까지",
      "etf",
      snap("2026-11-09", "2026-11-10T13:18:02+09:00", 10000, "after_close"),
      snap("2026-11-09", "2026-11-11T09:30:00+09:00", 10100, "after_close"),
      "라벨 11/9 같은 거래일에 다시 받음(11/10 13:18 마감 뒤 → 11/11 09:30 마감 뒤 저장 · KODEX 200 10,000원 → 10,100원)",
    ],
    ["저장 시각 같음 = 그대로", "wti", snap("2026-11-11", "x", 86.04), snap("2026-11-11", "x", 86.04), "라벨 11/11 그대로"],
    ["저장 시각 없음 · 값 바뀜", "vix", snap("2026-11-11", null, 17.49), snap("2026-11-11", null, 18.2), "라벨 11/11 값 바뀜(17.49 → 18.20)"],
    ["저장 시각 없음 · 값 같음", "vix", snap("2026-11-11", null, 17.49), snap("2026-11-11", null, 17.49), "라벨 11/11 그대로"],
    ["저장 시각 한쪽만", "kospi", snap("2026-11-09", null, 5018.85), snap("2026-11-09", "b", 5018.85), "라벨 11/9 그대로"],
  ])("%s", (_t, key, a, b, want) => {
    expect(compareSource(key, "라벨", a, b)).toBe(want);
  });
});
