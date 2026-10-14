// POC5-12 — VIX 최신성 안내 문구(설계 §2 · PLAN §1 · 판정 Q1). 서버 판정만 읽고 추측하지 않는다.
import { describe, it, expect } from "vitest";
import { vixFreshnessNotice } from "./vixFreshness";
import type { MarketRiskVix } from "./api/market";

function vix(over: Partial<MarketRiskVix> = {}): MarketRiskVix {
  return {
    availability: "available",
    as_of_date: "2026-10-09",
    close: 20,
    recent_20d_series: [],
    ...over,
  };
}

describe("vixFreshnessNotice", () => {
  it.each(["fresh", "one_weekday_behind"] as const)("%s 는 안내 없음", (state) => {
    expect(
      vixFreshnessNotice(vix({ freshness: { state, compare_date: "2026-10-13", weekdays_behind: 1 } })),
    ).toBeNull();
  });

  it("update_check: 'VIX 자료 업데이트 확인 필요(기준일 D)' · 국내 날짜 비교 설명 없음", () => {
    const got = vixFreshnessNotice(
      vix({ freshness: { state: "update_check", compare_date: "2026-10-13", weekdays_behind: 2 } }),
    );
    expect(got?.state).toBe("update_check");
    expect(got?.text).toBe("VIX 자료 업데이트 확인 필요(기준일 2026-10-09)");
    expect(got?.reason).toContain("2026-10-13");
    expect(got?.reason).toContain("평일 2일");
    expect(got?.reason).not.toMatch(/시장 기준일|KODEX|보다 이전/);
  });

  it("date_check: 'VIX 기준일 확인 필요(기준일 D)'", () => {
    const got = vixFreshnessNotice(
      vix({
        as_of_date: "2026-10-14",
        freshness: { state: "date_check", compare_date: "2026-10-13", weekdays_behind: null },
      }),
    );
    expect(got?.text).toBe("VIX 기준일 확인 필요(기준일 2026-10-14)");
    expect(got?.reason).not.toMatch(/시장 기준일|KODEX|보다 이전/);
  });

  it("판정 필드 없음: 옛 'VIX < 시장 날짜' 규칙으로 추측하지 않고 기준일 확인 필요", () => {
    // 옛 규칙이면 경고가 없었을(VIX 날짜가 더 늦음) 경우도, 있었을 경우도 같은 문구.
    expect(vixFreshnessNotice(vix({ as_of_date: "2026-10-09" }))?.text).toBe(
      "VIX 기준일 확인 필요(기준일 2026-10-09)",
    );
    expect(vixFreshnessNotice(vix({ as_of_date: "2026-10-20", freshness: null }))?.state).toBe(
      "date_check",
    );
  });

  it("날짜가 없으면 '(기준일 확인 불가)'", () => {
    expect(
      vixFreshnessNotice(
        vix({ as_of_date: null, freshness: { state: "date_check", compare_date: "2026-10-13" } }),
      )?.text,
    ).toBe("VIX 기준일 확인 필요(기준일 확인 불가)");
  });

  it("VIX 자료 없음(unavailable) · 응답 없음은 이 안내를 만들지 않는다(기존 항목 몫)", () => {
    expect(vixFreshnessNotice(vix({ availability: "unavailable", as_of_date: null }))).toBeNull();
    expect(vixFreshnessNotice(null)).toBeNull();
    expect(vixFreshnessNotice(undefined)).toBeNull();
  });
});
