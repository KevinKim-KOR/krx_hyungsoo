// POC6-14 — 「전향 ML 비교 · 연구」 표시 함수(PLAN 판정 Q2 · Q3) 시험.
// 2026-11-01 POC6-15 — 쉬운 한국어 문구로 기대값을 맞추고(뜻 · 숫자 그대로) 맨 위 결론 한 줄(forwardConclusion) 구분을 더함.
import { describe, it, expect } from "vitest";
import type { ForwardComparisonResponse } from "@/lib/api";
import { fmtPct, fmtPctp } from "../holdings_compare/helpers";
import {
  D20_MEANING,
  NOT_EVAL_LONG,
  actualLong,
  actualShort,
  copyText,
  fmtD20,
  forwardConclusion,
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

describe("결과 상태 문구(Q3 · POC6-15 쉬운 말)", () => {
  it("NOT_EVALUATED = 결과 확인 전 · 결과 대기와 구분", () => {
    expect(actualShort({ state: "NOT_EVALUATED" })).toBe("결과 확인 전");
    expect(actualLong({ state: "NOT_EVALUATED" })).toBe(NOT_EVAL_LONG);
    expect(actualShort({ state: "PENDING_NOT_DUE" })).toBe("결과 대기");
    expect(actualShort({ state: "MATURED", actual_pct: -7.12 })).toBe("-7.12%");
  });
});

describe("복사문 = 응답에서만", () => {
  it("연구용 · 표본 · D · 공개 확인 · 판 · 네 방법 · 실제 · 보고 범위 · D20 뜻 한 번", () => {
    const t = copyText(DATA, ROW);
    expect(t.split("\n")[0]).toBe("[예측과 결과 비교(연구 이름: 전향 ML 비교) — 연구용 · 운영에 쓰지 않음]");
    expect(t.split("\n")[1]).toMatch(/^현재 결론: 아직 비교할 결과가 없습니다 · 비교 보고 \d{4}-\d{2}-\d{2} \d{2}:\d{2} 만듦/);
    expect(t).toContain("고정 연구 대상(24종 · 보유 · 추천 목록과 무관) 중 0015K0 TIGER 미국소비트렌드액티브");
    expect(t).toContain(
      "기준일 2026-10-29 · 예측 공개 확인 2026-10-30 10:05:48 KST · 모델 버전 mv_e926e0661c261324 · 기록 실행 20261030T010545Z_632f4d6c",
    );
    expect(t).toContain(
      "중앙값 기준선 -3.06% · Ridge 0.00% · HGB 환경 불일치(원인 확인 필요 · 원문: scikit-learn 1.9.0 → 1.9.1) · MLP(CPU) -2.27%",
    );
    expect(t).toContain(`실제: ${NOT_EVAL_LONG}`);
    expect(t).toContain(
      "예측이 들어간 기준일 3개(2026-10-22 ~ 2026-10-29) · 결과가 나온 기준일 0개 · 같은 종목 · 같은 날 비교: " +
        "HGB · 중앙값 기준선 · Ridge 함께 0건 · MLP(CPU) · 중앙값 기준선 · Ridge 함께 0건 · 네 방법 함께 0건 — 아직 비교할 결과가 없습니다",
    );
    expect(t.split(D20_MEANING).length - 1).toBe(1);
    expect(t).not.toContain("+0.00%");
  });
  it("보고 상태가 다르면 그 사실을 붙인다(정상 보고 없음을 '보고 없음'으로 바꾸지 않음)", () => {
    expect(reportLine({ ...DATA, report: { ...DATA.report!, selected_D: "RUN_REPORT_MISSING" } })).toContain(
      "보고 상태: 이 기준일 보고 대기 — 이 기준일을 기록한 실행(2026-10-30 10:05)의 보고가 아직 없습니다",
    );
    expect(reportLine({ ...DATA, report: { state: "NONE", selected_D: "RUN_REPORT_MISSING" } })).toContain(
      "보고 상태: 비교 보고가 아직 없습니다 — 정기 실행이 아직 비교 보고를 남기지 않았습니다",
    );
    const allBad = reportLine({
      ...DATA,
      report: { state: "CHECK_REQUIRED", selected_D: "RUN_REPORT_UNREADABLE", unreadable: ["a", "b"] },
    });
    expect(allBad).toContain("최신 보고를 확인해야 합니다 — 보고 파일 2개를 모두 읽지 못했습니다");
    expect(allBad).not.toContain("비교 보고가 아직 없습니다");
  });
});

// POC6-15 판정 §3 — 맨 위 결론 한 줄은 보고 없음 · 손상 · 정상 비교 0 · 비교 있음 · 실행 기록 손상을 합치지 않는다.
describe("현재 결론 한 줄(forwardConclusion)", () => {
  const rep = DATA.report!;
  const withRows = (n: number) => ({
    ...DATA,
    report: {
      ...rep,
      matured_dates: { count: 2, first: "2026-09-01", last: "2026-09-02" },
      comparisons: { ...rep.comparisons, ALL_FOUR: { ...rep.comparisons!.ALL_FOUR, rows: n } },
    },
  });
  it.each<[string, ForwardComparisonResponse, string, string]>([
    ["정상 보고 · 비교 0", DATA, "muted", "아직 비교할 결과가 없습니다"],
    ["보고 없음", { ...DATA, report: { state: "NONE", selected_D: "RUN_REPORT_MISSING" } }, "muted", "비교 보고가 아직 없습니다"],
    [
      "보고 모두 읽지 못함",
      { ...DATA, report: { state: "CHECK_REQUIRED", selected_D: "RUN_REPORT_UNREADABLE", unreadable: ["a"] } },
      "bad",
      "최신 보고를 확인해야 합니다",
    ],
    ["이 기준일 보고 손상", { ...DATA, report: { ...rep, selected_D: "RUN_REPORT_UNREADABLE" as const } }, "bad", "최신 보고를 확인해야 합니다"],
    ["더 늦은 보고 손상", { ...DATA, report: { ...rep, newer_unreadable: ["z"] } }, "bad", "최신 보고를 확인해야 합니다"],
    ["보고 값 범위 밖", { ...DATA, report: { ...rep, state: "CHECK_REQUIRED" as const } }, "bad", "최신 보고를 확인해야 합니다"],
    ["실행 기록 손상", { ...DATA, basis: { ...DATA.basis!, unreadable_runs: ["r1"] } }, "bad", "실행 기록을 확인해야 합니다"],
    ["비교 있음", withRows(48), "ok", "비교 결과 있음"],
    ["예측 기록 없음", { ...DATA, status: "NO_RECORDS" as const }, "muted", "예측 기록 없음"],
    ["읽기 실패", { ...DATA, status: "READ_FAILED" as const }, "bad", "확인 필요"],
  ])("%s", (_name, data, tone, label) => {
    const c = forwardConclusion(data);
    expect([c.tone, c.label]).toEqual([tone, label]);
  });
  it("이 기준일 보고 대기는 그 전 보고 기준임을 덧붙이고 숫자는 받은 값 그대로", () => {
    const c = forwardConclusion({ ...DATA, report: { ...rep, selected_D: "RUN_REPORT_MISSING" } });
    expect(c.label).toBe("아직 비교할 결과가 없습니다");
    expect(c.text).toContain("이 기준일 보고는 대기 중(그 전 보고 기준)");
    expect(c.text).toContain(`지금까지 예측 ${rep.counts!.primary_records}건 · 결과가 나온 예측 ${rep.counts!.matured}건`);
    expect(forwardConclusion(withRows(1234)).text).toContain("네 방법 함께 1,234건");
  });

  // 검증자 r1 F1 — 비교는 세 가지이고 공통 줄이 따로다. 하나라도 줄이 있으면 '결과 있음'(네 방법 공통 0 이어도),
  //   셋 다 0 일 때만 '아직 없음', 항목이 빠지면 확인 필요. 결론 · 복사문(보고 줄)이 같은 판단.
  const cmp = (hgb: number | null, mlp: number | null, all4: number | null) => {
    const base = rep.comparisons!;
    const set = (k: string, n: number | null) =>
      n === null ? {} : { [k]: { ...base[k], rows: n, mae_pp: n > 0 ? { MEDIAN: 7, RIDGE: 7, HGB: 7, MLP_CPU: 7 } : base[k].mae_pp } };
    return {
      ...DATA,
      report: {
        ...rep,
        matured_dates: { count: 1, first: "2026-09-01", last: "2026-09-01" },
        comparisons: {
          ...set("HGB_vs_MEDIAN_RIDGE", hgb),
          ...set("MLP_CPU_vs_MEDIAN_RIDGE", mlp),
          ...set("ALL_FOUR", all4),
        },
      },
    } as ForwardComparisonResponse;
  };
  it.each<[string, ForwardComparisonResponse, string, string, string]>([
    ["MLP 실패 · HGB 비교만", cmp(1, 0, 0), "ok", "비교 결과 있음", "HGB · 중앙값 기준선 · Ridge 함께 1건"],
    ["HGB 실패 · MLP 비교만", cmp(0, 1, 0), "ok", "비교 결과 있음", "MLP(CPU) · 중앙값 기준선 · Ridge 함께 1건"],
    ["HGB · MLP 가 서로 다른 줄", cmp(1, 1, 0), "ok", "비교 결과 있음", "네 방법 함께 0건"],
    ["네 방법 모두", cmp(1, 1, 1), "ok", "비교 결과 있음", "네 방법 함께 1건"],
    ["셋 다 0", cmp(0, 0, 0), "muted", "아직 비교할 결과가 없습니다", "아직 비교할 결과가 없습니다"],
    ["HGB 비교 항목 빠짐(다른 비교는 있음)", cmp(null, 3, 3), "bad", "최신 보고를 확인해야 합니다", "비교 항목 확인 필요"],
    ["MLP 비교 줄 수 음수", cmp(2, -1, 0), "bad", "최신 보고를 확인해야 합니다", "비교 항목 확인 필요"],
  ])("세 비교 — %s", (_n, data, tone, label, inLine) => {
    const c = forwardConclusion(data);
    expect([c.tone, c.label]).toEqual([tone, label]);
    const line = reportLine(data);
    expect(line).toContain(inLine);
    if (tone !== "muted") expect(line).not.toContain("아직 비교할 결과가 없습니다");
    expect(copyText(data, ROW).split("\n")[1]).toBe(`현재 결론: ${c.label} · ${c.text}`);
  });
});
