// POC5-21 — 후보 수익률 실제 계산 기간 판정(설계자 PLAN 판정 Q1 · Q3).
// - '모두 같음'은 값이 있는 후보의 날짜가 전부 확인되고 전부 같을 때만.
// - 시작일이 여러 종류면 모든 값에 실제 시작일(다수를 기준 삼지 않음).
// - 끝일은 시장 저장 최신일과 비교(다수가 옛 날짜여도 기준 불변).
// - KODEX200 대비 비교는 POC5-22 동일 기간 값(lib/samePeriodKodex.test.ts)으로 옮겼다.
import { describe, it, expect } from "vitest";
import type { MarketCandidate, MarketPeriodReturn } from "./api";
import {
  UNKNOWN_BADGE,
  allPeriodsUnknown,
  candidateBadges,
  groupLine,
  groupSummary,
  periodGroup,
  valueNote,
  valuePeriod,
} from "./returnPeriod";

const ASOF = "2026-10-14";

function r(pct: number | null, start?: string, end?: string): MarketPeriodReturn {
  return {
    return_pct: pct,
    basis_start_date: start ?? null,
    basis_end_date: ASOF,
    ...(start ? { price_start_date: start } : {}),
    ...(end ? { price_end_date: end } : {}),
  };
}

function cand(
  ticker: string,
  one: MarketPeriodReturn | null,
  three: MarketPeriodReturn | null = r(3, "2026-07-16", ASOF),
): MarketCandidate {
  return {
    ticker,
    returns: { one_month: one, three_month: three },
  } as MarketCandidate;
}

describe("valuePeriod", () => {
  it("값 없음 · 날짜 없음 · 날짜 있음을 나눈다(basis_* 로 채우지 않는다)", () => {
    expect(valuePeriod(null)).toEqual({ kind: "none" });
    expect(valuePeriod(r(null, "2026-09-14", ASOF))).toEqual({ kind: "none" });
    // basis_start_date · basis_end_date 가 있어도 price_* 가 없으면 확인 불가.
    expect(valuePeriod({ return_pct: 1, basis_start_date: "2026-09-14", basis_end_date: ASOF })).toEqual({
      kind: "unknown",
    });
    expect(valuePeriod(r(1, "2026-09-14"))).toEqual({ kind: "unknown" });
    expect(valuePeriod(r(1, "2026-09-14", ASOF))).toEqual({
      kind: "dated",
      start: "2026-09-14",
      end: ASOF,
    });
  });
});

describe("공통 안내 한 줄(groupLine)", () => {
  it("전부 확인 · 전부 같음일 때만 '모두 같음' · 값 없는 후보는 세지 않는다", () => {
    const g = periodGroup(
      [cand("A", r(1, "2026-09-14", ASOF)), cand("B", r(2, "2026-09-14", ASOF)), cand("C", null)],
      "one_month",
    );
    expect(g).toMatchObject({ total: 2, dated: 2, unknown: 0 });
    expect(groupLine(g)).toBe("2026-09-14 → 2026-10-14 종가 · 표시 후보 2개 모두 같음");
  });

  it("일부 미확인은 빼고 '모두 같음'이라 하지 않는다", () => {
    const g = periodGroup([cand("A", r(1, "2026-09-14", ASOF)), cand("B", r(2))], "one_month");
    const line = groupLine(g);
    expect(line).toBe(
      "2026-09-14 → 2026-10-14 종가 · 날짜 확인된 1개 같음 · 1개 계산 기간 확인 불가",
    );
    expect(line).not.toContain("모두 같음");
  });

  it("전부 미확인 · 값 없음", () => {
    expect(groupLine(periodGroup([cand("A", r(1)), cand("B", r(2))], "one_month"))).toBe(
      "확인 불가 — 응답에 사용 종가 날짜가 없습니다",
    );
    expect(groupLine(periodGroup([cand("A", null)], "one_month"))).toBe("표시할 값이 없습니다");
  });

  it("시작일 · 끝일이 여러 종류면 '종목별 계산 기간 다름' + 같은 부분만 공통", () => {
    const starts = periodGroup(
      [cand("A", null, r(1, "2026-07-16", ASOF)), cand("B", null, r(2, "2026-07-28", ASOF))],
      "three_month",
    );
    expect(groupLine(starts)).toBe(
      "종목별 계산 기간 다름 · 시작일은 각 값 아래 · 끝 2026-10-14 공통",
    );
    const ends = periodGroup(
      [
        cand("A", r(1, "2026-09-14", ASOF)),
        cand("B", r(2, "2026-09-14", "2026-10-13")),
        cand("C", r(3)),
      ],
      "one_month",
    );
    expect(groupLine(ends)).toBe(
      "종목별 계산 기간 다름 · 시작 2026-09-14 공통 · 끝일이 시장 저장 최신일과 다른 후보는 이름 옆 · 1개 계산 기간 확인 불가",
    );
  });

  it("? 안 요약 — 같음 · 다름 · 미확인", () => {
    expect(groupSummary(periodGroup([cand("A", r(1, "2026-09-14", ASOF))], "one_month"))).toBe(
      "2026-09-14 → 2026-10-14 (1개 모두)",
    );
    expect(
      groupSummary(
        periodGroup(
          [cand("A", null, r(1, "2026-07-16", ASOF)), cand("B", null, r(2, "2024-02-14", ASOF)), cand("C", null, r(3))],
          "three_month",
        ),
      ),
    ).toBe("종목별 다름 — 시작 2024-02-14 ~ 2026-07-16 · 끝 2026-10-14 · 1개 확인 불가");
  });
});

describe("값 아래 표시(valueNote)", () => {
  it("시작일이 여러 종류면 다수 쪽 값까지 모두 실제 시작일(다수를 기준 삼지 않음)", () => {
    const cs = [
      cand("A", null, r(1, "2026-07-16", ASOF)),
      cand("B", null, r(2, "2026-07-16", ASOF)),
      cand("C", null, r(3, "2026-07-28", ASOF)),
    ];
    const g = periodGroup(cs, "three_month");
    expect(cs.map((c) => valueNote(valuePeriod(c.returns?.three_month), g, false))).toEqual([
      "시작 2026-07-16",
      "시작 2026-07-16",
      "시작 2026-07-28",
    ]);
  });

  it("한 종류면 값 아래 표시 없음 · 미확인은 후보 전체가 미확인이 아니면 '기간 확인 불가'", () => {
    const g = periodGroup([cand("A", r(1, "2026-09-14", ASOF)), cand("B", r(2))], "one_month");
    expect(valueNote({ kind: "dated", start: "2026-09-14", end: ASOF }, g, false)).toBeNull();
    expect(valueNote({ kind: "unknown" }, g, false)).toBe("기간 확인 불가");
    expect(valueNote({ kind: "unknown" }, g, true)).toBeNull();
    expect(valueNote({ kind: "none" }, g, false)).toBeNull();
  });
});

describe("이름 옆 표시(candidateBadges) — 끝일은 시장 저장 최신일과 비교", () => {
  it("끝일이 시장 저장 최신일과 다르면 '수익률 끝일'", () => {
    const cs = [cand("A", r(1, "2026-09-14", ASOF)), cand("B", r(2, "2026-09-14", "2026-10-13"))];
    const g = periodGroup(cs, "one_month");
    expect(candidateBadges(cs[0], "one_month", g, ASOF)).toEqual([]);
    expect(candidateBadges(cs[1], "one_month", g, ASOF)).toEqual(["수익률 끝일 2026-10-13"]);
  });

  it("후보 모두가 같은 옛 끝일이어도 그 날짜를 기준으로 바꾸지 않는다", () => {
    const cs = [
      cand("A", r(1, "2026-09-14", "2026-10-13")),
      cand("B", r(2, "2026-09-14", "2026-10-13")),
      cand("C", r(3, "2026-09-14", "2026-10-13")),
    ];
    const g = periodGroup(cs, "one_month");
    // 개별주만 더 최신(시장 저장 최신일 10-15) · ETF 는 모두 10-14 인 경우와 같은 규칙.
    for (const c of cs) expect(candidateBadges(c, "one_month", g, ASOF)).toEqual(["수익률 끝일 2026-10-13"]);
    expect(candidateBadges(cs[0], "one_month", g, null)).toEqual([]);
  });

  it("날짜가 하나도 없는 후보 — 다른 후보는 날짜가 있으면 이름 옆 · 전부 없으면 위 한 줄만", () => {
    const cs = [cand("A", r(1, "2026-09-14", ASOF)), cand("B", r(2), r(3))];
    expect(allPeriodsUnknown(cs[1])).toBe(true);
    expect(candidateBadges(cs[1], "one_month", periodGroup(cs, "one_month"), ASOF)).toEqual([UNKNOWN_BADGE]);
    const all = [cand("A", r(1), r(2)), cand("B", r(2), r(3))];
    expect(candidateBadges(all[0], "one_month", periodGroup(all, "one_month"), ASOF)).toEqual([]);
  });
});
