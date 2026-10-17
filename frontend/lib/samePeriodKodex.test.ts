// POC5-22 — 동일 기간 KODEX200 비교 공통 helper(설계 V1 §3 · §5 · PLAN 판정 Q1 · Q2).
// - 값은 새 객체(`same_period_kodex200`)에서만 · 없으면 '값 없음'(기존 excess_return 으로 대신하지 않음).
// - 계산 불가 사유는 짧은 글 · 한계 문장(가격 조정 기준 연속성 미검사)은 공통 상수 하나.
import { describe, it, expect } from "vitest";
import type { MarketCandidate, SamePeriodKodex200, SamePeriodKodex200Item } from "./api";
import {
  SAME_PERIOD_LIMIT,
  reasonText,
  sameCopyText,
  sameDetail,
  sameDiffOf,
  sameGroups,
  sameShort,
  sameSummary,
  sameView,
  sameViewOf,
} from "./samePeriodKodex";

function ok(start: string, end: string, cand: number, kodex: number, diff: number): SamePeriodKodex200Item {
  return {
    status: "ok",
    reason: null,
    start_date: start,
    end_date: end,
    candidate_return_pct: cand,
    kodex200_return_pct: kodex,
    diff_pctp: diff,
  };
}

function na(reason: string, start: string | null = "2026-09-14", end: string | null = "2026-10-14"): SamePeriodKodex200Item {
  return {
    status: "unavailable",
    reason,
    start_date: start,
    end_date: end,
    candidate_return_pct: 20.3,
    kodex200_return_pct: null,
    diff_pctp: null,
  };
}

function cand(ticker: string, sp: SamePeriodKodex200 | null | undefined, legacy = 99.9): MarketCandidate {
  return {
    ticker,
    // 기존 기간 다른 차이 — 새 객체가 없어도 이 값으로 대신하지 않는다.
    excess_return: { vs_kodex200_1m_pctp: legacy, vs_kodex200_3m_pctp: legacy },
    same_period_kodex200: sp,
  } as MarketCandidate;
}

const ONE = ok("2026-09-14", "2026-10-14", 22.2689, -9.8615, 32.1304);
const THREE = ok("2026-07-16", "2026-10-14", 33.7931, -12.6548, 46.4479);

describe("sameViewOf — 새 객체만 읽는다", () => {
  it("값 · 계산 불가 · 값 없음", () => {
    expect(sameViewOf({ one_month: ONE }, "1m")).toEqual({
      kind: "ok",
      diff: 32.1304,
      cand: 22.2689,
      kodex: -9.8615,
      start: "2026-09-14",
      end: "2026-10-14",
    });
    expect(sameViewOf({ one_month: na("kodex200_end_price_missing") }, "1m")).toEqual({
      kind: "unavailable",
      reason: "KODEX200 끝일 가격 없음",
      start: "2026-09-14",
      end: "2026-10-14",
    });
    expect(sameViewOf(null, "1m")).toEqual({ kind: "absent" });
    expect(sameViewOf({ one_month: ONE }, "3m")).toEqual({ kind: "absent" });
  });

  it("status=ok 라도 값 · 날짜가 비면 계산 불가로 본다(0 으로 채우지 않음)", () => {
    expect(sameViewOf({ one_month: { ...ONE, diff_pctp: null } }, "1m").kind).toBe("unavailable");
    expect(sameViewOf({ one_month: { ...ONE, start_date: null } }, "1m").kind).toBe("unavailable");
  });

  it("새 객체가 없으면 기존 excess_return(기간 다른 차이)으로 대신하지 않는다", () => {
    const c = cand("A", undefined, 37.33);
    expect(sameView(c, "1m")).toEqual({ kind: "absent" });
    expect(sameDiffOf(c.same_period_kodex200, "1m")).toBeNull();
    expect(sameShort(sameView(c, "1m"))).toBe("—");
    expect(sameCopyText(sameView(c, "1m"))).toBe("동일 기간 값 없음");
  });

  it("사유 문구", () => {
    expect(reasonText("candidate_period_unknown")).toBe("후보 기간 확인 불가");
    expect(reasonText("kodex200_start_price_missing")).toBe("KODEX200 시작일 가격 없음");
    expect(reasonText("kodex200_end_price_missing")).toBe("KODEX200 끝일 가격 없음");
    expect(reasonText("other")).toBe("계산 불가");
    expect(reasonText(null)).toBe("계산 불가");
  });
});

describe("표시 문구", () => {
  it("칸 · 상세 · 복사문", () => {
    const v = sameViewOf({ one_month: ONE }, "1m");
    expect(sameShort(v)).toBe("+32.13%p");
    expect(sameDetail(v)).toBe("후보 +22.27% · KODEX200 -9.86% · 사용 종가 2026-09-14 → 2026-10-14");
    expect(sameCopyText(v)).toBe(
      "+32.13%p (후보 +22.27% · KODEX200 -9.86% · 사용 종가 2026-09-14 → 2026-10-14)",
    );
    const u = sameViewOf({ one_month: na("kodex200_start_price_missing") }, "1m");
    expect(sameShort(u)).toBe("KODEX200 시작일 가격 없음");
    expect(sameCopyText(u)).toBe("계산 불가 — KODEX200 시작일 가격 없음 (후보 기간 2026-09-14 → 2026-10-14)");
    const u2 = sameViewOf({ one_month: na("candidate_period_unknown", null, null) }, "1m");
    expect(sameCopyText(u2)).toBe("계산 불가 — 후보 기간 확인 불가");
    expect(sameShort({ kind: "absent" }, "동일 기간 값 없음")).toBe("동일 기간 값 없음");
  });

  it("음수 · 0 차이", () => {
    expect(sameShort(sameViewOf({ one_month: ok("a", "b", 1, 2, -1) }, "1m"))).toBe("-1.00%p");
    expect(sameShort(sameViewOf({ one_month: ok("a", "b", 1, 1, 0) }, "1m"))).toBe("0.00%p");
  });

  it("한계 문장(판정 Q1 (a))", () => {
    expect(SAME_PERIOD_LIMIT).toBe("저장 종가로 계산하며 가격 조정 기준의 연속성은 검사하지 않습니다.");
  });
});

describe("목록 위 줄 · ? 묶음", () => {
  it("같은 기간끼리 묶어 KODEX200 수익률 한 번씩 · 계산 불가 · 값 없음 수", () => {
    const cs = [
      cand("A", { one_month: ONE, three_month: THREE }),
      cand("B", { one_month: ONE, three_month: ok("2026-07-28", "2026-10-14", 31.24, -0.49, 31.73) }),
      cand("C", { one_month: na("kodex200_end_price_missing"), three_month: THREE }),
      cand("D", null),
    ];
    expect(sameGroups(cs, "1m")).toEqual([
      "· 1M 2026-09-14 → 2026-10-14 (2개) · KODEX200 -9.86%",
      "· 1M 계산 불가 1개(칸에 사유)",
      "· 1M 동일 기간 값 없음 1개",
    ]);
    expect(sameGroups(cs, "3m")).toEqual([
      "· 3M 2026-07-16 → 2026-10-14 (2개) · KODEX200 -12.65%",
      "· 3M 2026-07-28 → 2026-10-14 (1개) · KODEX200 -0.49%",
      "· 3M 동일 기간 값 없음 1개",
    ]);
    expect(sameSummary(cs)).toBe(
      "후보와 같은 시작 · 끝 날짜의 KODEX200 종가로 뺀 차이 (%p) · 1칸 계산 불가 · 2칸 값 없음",
    );
  });

  it("시작일은 같고 끝일만 다르면(끝이 이른 후보) 다른 기간으로 묶는다", () => {
    const cs = [
      cand("A", { one_month: ONE }),
      cand("B", { one_month: ok("2026-09-14", "2026-10-13", 17.89, -9.64, 27.53) }),
    ];
    expect(sameGroups(cs, "1m")).toEqual([
      "· 1M 2026-09-14 → 2026-10-13 (1개) · KODEX200 -9.64%",
      "· 1M 2026-09-14 → 2026-10-14 (1개) · KODEX200 -9.86%",
    ]);
  });

  it("전부 값 없음(이전 응답) · 정상", () => {
    expect(sameSummary([cand("A", undefined), cand("B", null)])).toBe("응답에 동일 기간 비교가 없습니다");
    expect(sameSummary([cand("A", { one_month: ONE, three_month: THREE })])).toBe(
      "후보와 같은 시작 · 끝 날짜의 KODEX200 종가로 뺀 차이 (%p)",
    );
  });
});
