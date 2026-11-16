// POC6-31 STEP 4 — 구성종목 비교 표시 글(서버 미리보기 줄과 같은 반올림 · 낱말).
import { describe, expect, it } from "vitest";
import {
  addDecimals,
  constituentDatesText,
  formulaText,
  heldText,
  pairCellText,
  pairText,
  pct2,
  rangeText,
  round2,
  scopeLines,
  wtext,
} from "./pairExposureText";
import { pairOk } from "./pairExposureTestFixtures";

describe("구성종목 비교 표시 글", () => {
  it.each([
    ["1.845", "1.85"], // 이진 소수 반올림 오차 없이 셋째 자리 5 → 올림(서버 ROUND_HALF_UP)
    ["1.8449", "1.84"],
    ["0.005", "0.01"],
    ["0.0049", "0.00"],
    ["0", "0.00"],
    ["22.85712", "22.86"],
    ["99.995", "100.00"],
    ["7", "7.00"],
  ])("round2(%s) = %s", (a, b) => {
    expect(round2(a)).toBe(b);
  });

  it("pct2 · wtext — 값 없음은 0 으로 채우지 않음 · 원천 비중은 반올림 없이 둘째 자리까지 0 채움", () => {
    expect(pct2(null)).toBe("확인 불가");
    // 표시 반올림도 글 셈(Number().toFixed 는 1.845 → 1.84 · 서버 미리보기 줄과 달라짐)
    expect(pct2("1.845")).toBe("1.85%");
    expect(pct2("22.855")).toBe("22.86%");
    expect(wtext("3.1")).toBe("3.10%");
    expect(wtext("3.125")).toBe("3.125%");
    expect(wtext("20")).toBe("20.00%");
    expect(wtext(null)).toBe("확인 불가");
  });

  it("addDecimals — 넷째 자리 글끼리 정확히 더함", () => {
    expect(addDecimals(["42.8571", "14.2857", "14.2857", "28.5714"])).toBe("99.9999");
    expect(addDecimals(["0.1", "0.2"])).toBe("0.3");
    expect(addDecimals(["0", "0"])).toBe("0");
  });

  it("짝 칸 — 0(확인)과 저장 범위에서 미확인을 구분", () => {
    expect(pairText({ state: "zero" })).toBe("0(확인)");
    expect(pairText({ state: "out_of_range", stored_rows: 30, stored_sum: "97.4" })).toBe(
      "저장 범위에서 미확인(30행 · 저장 행 합 97.40%)",
    );
    expect(pairText({ state: "self" })).toBe("이 주식 자체");
    expect(pairText({ state: "not_applicable" })).toBe("해당 없음(개별 주식)");
    expect(pairText({ state: "unconfirmed", asof: "2026-06-22" })).toBe("원천 기준일 미확인(2026-06-22 보존 자료)");
    expect(pairText({ state: "no_data" })).toBe("구성 자료 없음");
  });

  it("확인 범위 — 들어감 · 빠짐(사유별) · 합", () => {
    const p = pairOk({ candidate: "C", holding: "H" });
    const sc = scopeLines(p);
    expect(sc?.included).toBe("계산에 들어감: 보유 ETF 1개 = 평가액의 85.00% · 직접 보유 0개 = 0.00%");
    expect(sc?.missing).toBe("빠짐 15.00%: 구성 자료 없음 1개 15.00%");
    // 식의 더하는 값 = 계산에 쓴 자릿수 그대로(따로 반올림하지 않아 보이는 식이 맞음 · 검토 지적 frontend#1)
    expect(sc?.sum).toContain("85% + 0% + 15% = 100%");
    const odd = pairOk({ candidate: "C", holding: "H" });
    odd.scope = {
      ...odd.scope!,
      included: { count: 1, weight: "62.3456" },
      direct: { count: 1, weight: "10.1256" },
      no_data: { count: 1, weight: "27.5288" },
    };
    expect(scopeLines(odd)?.sum).toContain("62.3456% + 10.1256% + 27.5288% = 100%");
  });

  it("계산 입력 — 계산에 쓴 자릿수 그대로 · 합계 뒤 한 번 반올림", () => {
    const s = pairOk({ candidate: "C", holding: "H" }).stocks[0];
    expect(formulaText(s)).toBe(
      "일라이 릴리 = 고른 보유 평가 비중 85% × 편입 3.12% (2.652%) + 직접 보유 0% = 2.652% → 합계에서 반올림 2.65%",
    );
  });

  it("역할별 기준일 — 세 칸이 모두 없으면(예전 기록) 줄 없음", () => {
    expect(constituentDatesText(null)).toBeNull();
    expect(
      constituentDatesText({ candidate_constituents_asof: null, holding_constituents_asof: null, exposure_asof: null }),
    ).toBeNull();
    expect(constituentDatesText({})).toBeNull();
    expect(
      constituentDatesText({ candidate_constituents_asof: "2026-11-13", holding_constituents_asof: null, exposure_asof: "2026-11-12" }),
    ).toBe("구성: 후보 2026-11-13 · 고른 보유 - · 노출 합계 2026-11-12");
  });

  it("보유 중 후보 — 합계 반영 여부 사유를 쓰임별로(서버 글과 같음)", () => {
    const base = pairOk({ candidate: "C", holding: "H" });
    const held = (use: string, w: string | null, asof = "2026-11-10") =>
      heldText({ ...base, candidate: { ...base.candidate, held: true, held_use: use, held_weight: w, asof } });
    expect(held("sum", "1")).toBe("후보를 이미 보유 중(평가 비중 1.00%) — 그 구성도 노출 합계에 들어 있음");
    expect(held("other_date", "1")).toBe(
      "후보를 이미 보유 중(평가 비중 1.00%) — 후보 구성일 2026-11-10이 노출 합계일과 달라 합계 밖(다른 구성일 참고)",
    );
    expect(held("no_weight", null)).toBe("후보를 이미 보유 중 — 시세 미확인이라 분모 밖 — 합계에 넣지 않음");
    expect(heldText(base)).toBe("후보를 지금 보유하지 않음");
  });

  it("노출을 못 낸 주식 · 확인한 구성이 없는 주식은 0 이 아니라 확인 불가(검증자 STEP 4~5 r1 F10)", () => {
    const base = pairOk({ candidate: "C", holding: "005930" });
    expect(formulaText({ ...base.stocks[0], exposure: null })).toBe("일라이 릴리 = 내 보유 전체 비중 확인 불가(계산하지 않음)");
    const none = { ...base.stocks[0].exposure!, terms: [], raw: null, value: null };
    expect(formulaText({ ...base.stocks[0], exposure: none })).toBe("일라이 릴리 = 확인한 구성 없음 → 내 보유 전체 확인 불가");
  });

  it("고른 보유 구성일이 후보와 다르면 고른 보유 칸에 참고 표시 · 비중을 못 읽은 편입은 확인 불가(r1 F12 · F10)", () => {
    const base = pairOk({ candidate: "C", holding: "H" });
    const diff = { ...base, pair_dates_differ: true };
    expect(pairCellText(diff, { state: "found", weight: "2.1" })).toBe("2.10%(구성일 다름 · 참고)");
    expect(pairCellText(diff, { state: "zero" })).toBe("0(확인)(구성일 다름 · 참고)");
    expect(pairCellText(diff, { state: "self" })).toBe("이 주식 자체");
    expect(pairCellText(base, { state: "found", weight: "2.1" })).toBe("2.10%");
    expect(pairCellText(base, { state: "weight_unknown" })).toBe("편입 · 비중 확인 불가");
  });

  it("시세 미확인 분모 밖 · 저장 행 범위 요약(검토 contract#5)", () => {
    const base = pairOk({ candidate: "C", holding: "H" });
    const p = {
      ...base,
      basis: { ...base.basis!, partial: true },
      dates: { ...base.dates, candidate: "2026-11-10" },
      scope: {
        ...base.scope!,
        no_weight: { count: 2 },
        ranges: { depth: 1, legacy: 1, unverified: 1, full: 2, full_min: 11, full_max: 25 },
      },
    };
    // 기준일 줄(부분 평가액 · 구성일 다름)은 서버 글(`date_line`) — 서버 시험 `test_date_line_*`
    expect(scopeLines(p)?.missing).toContain("시세 미확인 2종목은 분모 밖(부분 평가액 기준)");
    expect(rangeText(p)).toBe(
      "합산 보유 ETF별 저장 행: 30행(요청 깊이 전부 · 그 밖은 미확인) 1개 · 예전 10행 1개 · " +
        "원천 전체 확인 기록 없음(그 밖은 미확인) 1개 · 11 ~ 25행(원천 전체) 2개",
    );
  });
});
