// POC6-14 — 「전향 ML 비교 · 연구」 표시 함수(PLAN 판정 Q2 · Q3) 시험.
import { describe, it, expect } from "vitest";
import { fmtPct, fmtPctp } from "../holdings_compare/helpers";
import {
  D20_MEANING,
  NOT_EVAL_LONG,
  actualLong,
  actualShort,
  copyText,
  fmtD20,
  fmtSizePp,
  kstTime,
  reportLine,
  runTime,
} from "./forwardText";
import { DATA, ROW } from "./testFixtures";

describe("fmtD20 — 0 근처는 부호 없이", () => {
  it.each([
    [0, "0.00%"],
    [-0.004, "0.00%"],
    [-0, "0.00%"],
    [-3.06, "-3.06%"],
    [-12.49, "-12.49%"],
  ])("%s → %s", (v, want) => expect(fmtD20(v)).toBe(want));
  it("null · 비유한 값은 숫자로 살리지 않음", () => {
    expect(fmtD20(null)).toBe("-");
    expect(fmtD20(undefined)).toBe("-");
    expect(fmtD20(Number.NaN)).toBe("확인 필요");
  });
  it("기존 fmtPct · fmtPctp 전역 동작은 그대로", () => {
    expect(fmtPct(0)).toBe("+0.00%");
    expect(fmtPctp(3.41)).toBe("+3.41%p");
  });
});

describe("fmtSizePp — MAE · 작게 추정한 정도", () => {
  it("부호 없는 %p · 음수 · 비유한은 확인 필요(abs 로 살리지 않음)", () => {
    expect(fmtSizePp(3.41)).toBe("3.41%p");
    expect(fmtSizePp(0)).toBe("0.00%p");
    expect(fmtSizePp(null)).toBe("-");
    expect(fmtSizePp(-1)).toBe("확인 필요");
    expect(fmtSizePp(Number.POSITIVE_INFINITY)).toBe("확인 필요");
  });
});

describe("시각", () => {
  it("KST 초까지 · 회차 id 접두", () => {
    expect(kstTime("2026-10-30T01:05:48.513143Z")).toBe("2026-10-30 10:05:48");
    expect(kstTime(null)).toBe("미확인");
    expect(kstTime("x")).toBe("미확인");
    expect(runTime("20261030T010545Z_632f4d6c")).toBe("2026-10-30 10:05");
  });
});

describe("성숙 상태 문구(Q3)", () => {
  it("NOT_EVALUATED = 성숙 확인 전 · 결과 대기와 구분", () => {
    expect(actualShort({ state: "NOT_EVALUATED" })).toBe("성숙 확인 전");
    expect(actualLong({ state: "NOT_EVALUATED" })).toBe(NOT_EVAL_LONG);
    expect(actualShort({ state: "PENDING_NOT_DUE" })).toBe("결과 대기");
    expect(actualShort({ state: "MATURED", actual_pct: -7.12 })).toBe("-7.12%");
  });
});

describe("복사문 = 응답에서만", () => {
  it("연구용 · 표본 · D · 공개 확인 · 판 · 네 방법 · 실제 · 보고 범위 · D20 뜻 한 번", () => {
    const t = copyText(DATA, ROW);
    expect(t.split("\n")[0]).toBe("[전향 ML 비교 · 연구 — 연구용 · 운영 미채택]");
    expect(t).toContain("고정 연구 표본(24종 · 보유 · 추천 목록과 무관) 중 0015K0 TIGER 미국소비트렌드액티브");
    expect(t).toContain("기준일 D 2026-10-29 · 공개 확인 2026-10-30 10:05:48 KST · 모델 판 mv_e926e0661c261324");
    expect(t).toContain(
      "중앙값 기준선 -3.06% · Ridge 0.00% · HGB 환경 불일치(scikit-learn 1.9.0 → 1.9.1) · MLP(CPU) -2.27%",
    );
    expect(t).toContain(`실제 D20: ${NOT_EVAL_LONG}`);
    expect(t).toContain("예측 포함 기준일 3개(2026-10-22 ~ 2026-10-29) · 성숙 비교 기준일 0개 · 네 방법 공통 비교 행 0 — 아직 비교할 결과 없음");
    expect(t.split(D20_MEANING).length - 1).toBe(1);
    expect(t).not.toContain("+0.00%");
  });
  it("보고 상태가 다르면 그 사실을 붙인다(정상 보고 없음을 '보고 없음'으로 바꾸지 않음)", () => {
    expect(reportLine({ ...DATA, report: { ...DATA.report!, selected_D: "RUN_REPORT_MISSING" } })).toContain(
      "보고 상태: 보고서 확인 대기 — 이 기준일을 기록한 회차(20261030T010545Z_632f4d6c)의 보고가 아직 없습니다",
    );
    expect(reportLine({ ...DATA, report: { state: "NONE", selected_D: "RUN_REPORT_MISSING" } })).toContain(
      "보고 상태: 보고 없음 — 06 실행이 아직 비교 보고를 남기지 않았습니다",
    );
    const allBad = reportLine({
      ...DATA,
      report: { state: "CHECK_REQUIRED", selected_D: "RUN_REPORT_UNREADABLE", unreadable: ["a", "b"] },
    });
    expect(allBad).toContain("최신 보고 확인 필요 — 보고 파일 2개를 모두 읽지 못했습니다");
    expect(allBad).not.toContain("보고 없음 —");
  });
});
