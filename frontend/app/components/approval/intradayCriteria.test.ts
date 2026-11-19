// POC6-34 L3 — 판정 기준 표 문장(순수 함수) 시험.
//
// 지금 값(PC 기록 활성 버전 · 사업군 27개)으로 만든 문장이 PLAN V1 §2-3 문안과 글자까지 같은지,
// 그리고 문장이 **같은 응답의 값**으로 만들어지는지(값 · 사업군 수 · 경계 · 값 없음)를 본다.
// 값은 모두 합성 고정값이다(보유 종목 · 금액 없음).
//
// 보유 급등 · 급락 두 행은 검증자 r1 R1-F1 정정으로 PLAN §2-3 문안과 다르다 — 실행 코드가 읽지 않는
// 설정값 대신 프로그램 고정 경계로 문장을 만든다. 고정 경계는 서버 시험(tests/test_holdings_risk_alert.py)과
// 같은 공용 고정 자료(저장소 tests/fixtures/poc6_34_holdings_bands.json)로 대조한다(저장소 파일만 읽음).
// 표 위 한 줄(C5) · 회차당 최대 값이 없을 때의 각주(C9) · 조회 성공률 '무엇을 보는지'는 설계자 RESULT 판정
// (2026-11-19) 문안이다.

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  buildCriteria,
  criteriaFootnote,
  criteriaTitle,
  CRITERIA_INTRO,
  HOLDING_DROP_UPPER_BOUNDS,
  HOLDING_SURGE_LOWER_BOUNDS,
  minCoverageCount,
  OTHER_GROUP_TITLE,
  policyValueText,
  rankCut,
  UNKNOWN,
  type CriteriaRow,
  type PolicyValue,
} from "./intradayCriteria";

// 설계 고정값(`CONFIRMED_POLICY`)과 같은 12개 — 응답 순서(REQUIRED_POLICY_KEYS) 그대로.
const CURRENT: PolicyValue[] = [
  { key: "surge_threshold_pct", value: 5.0 },
  { key: "drop_threshold_pct", value: -5.0 },
  { key: "cooldown_minutes", value: 120 },
  { key: "dedup_window_minutes", value: 120 },
  { key: "max_sends_per_run", value: 1 },
  { key: "max_sends_per_day", value: 4 },
  { key: "sector_entry_min_pct", value: 1.5 },
  { key: "sector_chase_pct", value: 4.0 },
  { key: "sector_avoid_drop_pct", value: -1.5 },
  { key: "sector_rank_top_pct", value: 20.0 },
  { key: "max_items_per_section", value: 3 },
  { key: "sector_min_coverage_pct", value: 80.0 },
];

function withValues(patch: Record<string, unknown>): PolicyValue[] {
  return CURRENT.map((p) => (p.key in patch ? { key: p.key, value: patch[p.key] } : p));
}

function rowsOf(values: PolicyValue[], n: number): Record<string, CriteriaRow> {
  const out: Record<string, CriteriaRow> = {};
  for (const g of buildCriteria(values, n)) for (const r of g.rows) out[r.key] = r;
  return out;
}

// 보유 급등 · 급락 '이 값의 뜻'(R1-F1) — 저장된 설정값과 상관없이 프로그램 고정 경계로 만든 문장.
const SURGE_FIXED =
  "실행 코드는 이 설정값을 읽지 않고, 프로그램에 고정된 +5% 이상(+5 ~ +7% · +7 ~ +10% · +10% 이상)으로 판정합니다. 오늘 +5.2%인 보유 종목은 급등 후보가 됩니다(정확히 +5.0% 포함 · +4.9% 해당 없음).";
const DROP_FIXED =
  "실행 코드는 이 설정값을 읽지 않고, 프로그램에 고정된 -5% 이하(-5 ~ -7% · -7 ~ -10% · -10% 이하)로 판정합니다. 오늘 -5.2%인 보유 종목은 급락 후보가 됩니다(정확히 -5.0% 포함 · -4.9% 해당 없음).";

// PLAN V1 §2-3 표의 '설정값 · 무엇을 보는지 · 이 값의 뜻' 글자 그대로(보유 급등 · 급락 '이 값의 뜻'만 R1-F1 문장).
const PLAN_2_3: [string, string, string, string, string][] = [
  [
    "surge_threshold_pct",
    "보유 급등 기준",
    "5%",
    "보유 종목의 오늘 등락률을 봅니다. 직전 거래일 종가 대비 값을 소수 첫째 자리로 반올림해서 씁니다.",
    SURGE_FIXED,
  ],
  [
    "drop_threshold_pct",
    "보유 급락 기준",
    "-5%",
    "보유 종목의 오늘 등락률을 봅니다. 직전 거래일 종가 대비 값을 소수 첫째 자리로 반올림해서 씁니다.",
    DROP_FIXED,
  ],
  [
    "sector_entry_min_pct",
    "진입 검토 하한",
    "1.5%",
    "사업군 대표 ETF의 오늘 등락률을 소수 첫째 자리로 반올림해서 봅니다. 대표를 못 읽은 사업군은 대체 ETF가 있으면 그 값을 씁니다.",
    "오늘 +1.6%인 대표 ETF는 하한을 충족합니다(정확히 +1.5%부터 +4% 미만까지). 「신규 진입 검토」로 알리려면 상승 순위 상위 20% 안에 들고, 직전 거래일 종가 기준 5일 · 20일 수익률이 모두 0보다 커야 합니다. 보유 중인 종목은 빠집니다.",
  ],
  [
    "sector_chase_pct",
    "추격 주의 기준",
    "4%",
    "사업군 대표 ETF의 오늘 등락률(소수 첫째 자리 반올림)이 크게 오른 경우를 가립니다.",
    "오늘 +4.2%(정확히 +4.0% 포함)인 대표 ETF는 순위와 상관없이 「진입 회피」 구역의 '단기 급등 · 추격 주의' 후보가 됩니다. 이렇게 오른 종목은 신규 진입 검토로는 알리지 않습니다. 보유 중인 종목은 빠집니다.",
  ],
  [
    "sector_avoid_drop_pct",
    "진입 회피 기준",
    "-1.5%",
    "사업군 대표 ETF의 오늘 등락률(소수 첫째 자리 반올림)이 크게 내린 경우를 가립니다.",
    "오늘 -1.6%(정확히 -1.5% 포함)인 대표 ETF가 하락 순위 하위 20% 안에 들면 「진입 회피」 구역의 '장중 급락' 후보가 됩니다. -1.6%라도 하위 20% 밖이면 알리지 않습니다. 보유 중인 종목은 빠집니다.",
  ],
  [
    "sector_rank_top_pct",
    "순위 조건",
    "20%",
    "오늘 등락률을 읽은 사업군 대표 ETF(대표를 못 읽으면 대체 ETF)를 등락률로 줄 세운 순위를 봅니다. 많이 오른 쪽 위 20%는 신규 진입 검토에, 많이 내린 쪽 아래 20%는 장중 급락 회피에 씁니다.",
    "27개 사업군이 모두 읽히면 27×20%=5.4에서 소수점을 버려 오른 쪽 5개, 내린 쪽 5개가 순위 조건을 충족합니다. 22개만 읽히면 4개씩입니다. 21개 이하로 읽히면 조회 성공률 80%에 못 미쳐 순위를 매기지 않습니다.",
  ],
  [
    "cooldown_minutes",
    "재발송 대기",
    "120분",
    "알린 종목이 조건 밖으로 벗어났다가 같은 상태로 다시 잡혔을 때, 다시 알리려면 마지막 알림부터 지나야 하는 시간입니다. 사업군 대표 ETF 신호와 보유 급등에 종목별로 적용합니다.",
    "마지막으로 알린 회차 시작 시각부터 120분(2시간) 이상 지난 회차에서 같은 상태로 다시 잡혀야 다시 보냅니다. 120분 안에 다시 잡혀 그대로 이어지거나, 같은 상태가 끊기지 않고 이어지면 시간이 지나도 다시 보내지 않습니다. 상태가 바뀌면 기다리지 않고 보냅니다. 보유 급락은 이 대기 대신 같은 날 더 나쁜 구간으로 내려갈 때만 다시 알립니다.",
  ],
  [
    "max_sends_per_day",
    "하루 최대",
    "4건",
    "같은 날(한국 시각) 장중 급등락 알림 메시지를 끝까지 보낸 횟수를 셉니다. 종목 수가 아니라 메시지 수이며, 정해진 시각에 나가는 정기 알림은 세지 않습니다.",
    "그날 장중 급등락 알림을 4건 보내면 남은 장중 점검 회차에는 보유 급락을 포함해 아무것도 보내지 않고, 다음 날 다시 0부터 셉니다. 점검 회차 하나에서는 최대 1건만 보냅니다.",
  ],
  [
    "max_items_per_section",
    "구역별 최대",
    "3건",
    "알림 메시지 한 건의 구역(보유종목 · 신규 진입 검토 · 진입 회피)마다 싣는 종목 수의 상한입니다.",
    "한 구역에 조건을 충족한 종목이 5개여도 이번 메시지에는 3개만 실리고, 한 메시지에는 최대 9종목이 실립니다. 실리지 못한 2개는 보낸 것으로 기록하지 않습니다. 보유 급락, 아직 알린 적 없는 신호, 마지막 알림과 상태가 다른 신호는 다음 회차에 다시 후보가 됩니다.",
  ],
  [
    "sector_min_coverage_pct",
    "최소 조회 성공률",
    "80%",
    // 설계자 RESULT 판정(2026-11-19) — '활성 설정의' → '이 표에 표시한 설정의'(나머지 그대로).
    "이 표에 표시한 설정의 사업군 가운데 오늘 시세(등락률)를 읽은 사업군의 비율을 봅니다. 대표 ETF 대신 대체 ETF로 읽은 경우도 성공으로 셉니다.",
    "27개 사업군 중 22개 이상(81.5%)을 읽으면 사업군 판정을 하고, 21개(77.8%) 이하이면 그 회차의 「신규 진입 검토」와 「진입 회피」 구역을 모두 뺍니다. 보유 종목 급등락 알림은 그대로 판정합니다.",
  ],
];

const PLAN_FOOTNOTE =
  "중복 억제 창은 재발송 대기와 같은 값만 저장되는 다른 이름이라 따로 동작하지 않고, 회차당 최대 1건은 한 점검 회차가 알림 메시지를 하나만 만드는 구조에서 나온 고정값입니다. 위 등락률 기준은 알림 후보를 고르는 조건이며, 실제 발송에는 보유 종목 제외 · 조회 성공률 · 재발송 대기 · 구역별 최대 · 하루 최대가 함께 적용됩니다(보유 급락은 같은 날 더 나쁜 구간으로 내려갈 때만 다시 알림).";

// 설계자 RESULT 판정 C9(2026-11-19 · 형수님 결정 U3) — 회차당 최대 값이 없으면(활성 · 후보 모두) 중복 억제 창
// 설명은 한 문장으로 끊고, 회차당 최대는 따로 '확인할 수 없습니다'라고 쓴다. 뒤 문장은 그대로다.
const RESULT_C9_MISSING_FOOTNOTE =
  "중복 억제 창은 재발송 대기와 같은 값만 저장되는 다른 이름이라 따로 동작하지 않습니다. 회차당 최대 건수는 이 설정에서 확인할 수 없습니다. 위 등락률 기준은 알림 후보를 고르는 조건이며, 실제 발송에는 보유 종목 제외 · 조회 성공률 · 재발송 대기 · 구역별 최대 · 하루 최대가 함께 적용됩니다(보유 급락은 같은 날 더 나쁜 구간으로 내려갈 때만 다시 알림).";

// 설계자 RESULT 판정 C5(2026-11-19) — 판정 문장 두 개 그대로 + PC 의 대표 ETF 선정 · 버전 단위 승인 문장(같은 자리).
const RESULT_C5_INTRO =
  "사업군 판정과 발송 조건은 설정 버전에서 확인합니다. 보유 급등·급락 판정에는 프로그램의 고정 경계를 적용합니다. PC 가 계산하는 것은 사업군 · 대표 ETF 목록(시가총액 순)입니다. 여기서 하나씩 고치지 않고 버전 전체를 승인합니다.";

describe("판정 기준 표 — 지금 값(27개 사업군)이면 PLAN §2-3 문안과 같다", () => {
  it.each(PLAN_2_3)("%s", (key, label, value, what, meaning) => {
    const row = rowsOf(CURRENT, 27)[key];
    expect(row).toEqual({ key, label, value, what, meaning });
  });

  it("세 묶음 · 순서 · 이름은 판정서 §2 표 순서다 · 파생 키 2개는 행이 아니다", () => {
    const groups = buildCriteria(CURRENT, 27);
    expect(groups.map((g) => g.title)).toEqual([
      "보유 종목 급등락",
      "사업군 대표 ETF 검토",
      "발송 한도와 자료 조건",
    ]);
    expect(groups.map((g) => g.rows.map((r) => r.label))).toEqual([
      ["보유 급등 기준", "보유 급락 기준"],
      ["진입 검토 하한", "추격 주의 기준", "진입 회피 기준", "순위 조건"],
      ["재발송 대기", "하루 최대", "구역별 최대", "최소 조회 성공률"],
    ]);
    const labels = groups.flatMap((g) => g.rows.map((r) => r.label));
    expect(labels).not.toContain("중복 억제 창");
    expect(labels).not.toContain("회차당 최대");
  });

  it("각주 · 제목 · 한 줄 설명 문안", () => {
    expect(criteriaFootnote(CURRENT)).toBe(PLAN_FOOTNOTE);
    expect(criteriaTitle(false)).toBe("PC에 기록된 적용 기준");
    expect(criteriaTitle(true)).toBe("승인 시 적용될 기준");
    expect(CRITERIA_INTRO).toBe(RESULT_C5_INTRO);
  });
});

describe("순위 개수 · 최소 성공 수(백엔드 식 · I-21)", () => {
  it.each([
    [27, 20, 5],
    [22, 20, 4],
    [13, 20, 2], // 2.6 — 반올림이면 3 이 된다(버림)
    [3, 20, 1], // 0.6 — 버리면 0 이지만 최소 1개
    [0, 20, 0],
    [10, 0, 1],
  ])("rankCut(%i, %i) = %i", (n, pct, want) => {
    expect(rankCut(n, pct)).toBe(want);
  });

  it.each([
    [27, 80, 22],
    [10, 80, 8], // 정확히 80.0% 는 통과
    [10, 81, 9],
    [27, 100, 27],
    [5, 0, 1], // 성공 0개는 늘 미달
  ])("minCoverageCount(%i, %i) = %i", (n, pct, want) => {
    expect(minCoverageCount(n, pct)).toBe(want);
  });

  it("사업군 0 · 기준 100 초과 · 정수 아님 → 없음(null)", () => {
    expect(minCoverageCount(0, 80)).toBeNull();
    expect(minCoverageCount(27, 101)).toBeNull();
    expect(minCoverageCount(2.5, 80)).toBeNull();
  });
});

describe("순위 조건 · 최소 조회 성공률 문장 모양", () => {
  const rank = (patch: Record<string, unknown>, n: number) =>
    rowsOf(withValues(patch), n).sector_rank_top_pct.meaning;
  const cover = (patch: Record<string, unknown>, n: number) =>
    rowsOf(withValues(patch), n).sector_min_coverage_pct.meaning;

  it("판정서 예 — 10개 · 80% 면 8개부터 통과 · 7개(70.0%)는 미달", () => {
    expect(cover({}, 10)).toBe(
      "10개 사업군 중 8개 이상(80.0%)을 읽으면 사업군 판정을 하고, 7개(70.0%) 이하이면 그 회차의 「신규 진입 검토」와 「진입 회피」 구역을 모두 뺍니다. 보유 종목 급등락 알림은 그대로 판정합니다.",
    );
    expect(rank({}, 10)).toBe(
      "10개 사업군이 모두 읽히면 10×20%=2에서 소수점을 버려 오른 쪽 2개, 내린 쪽 2개가 순위 조건을 충족합니다. 8개만 읽히면 1개씩입니다. 7개 이하로 읽히면 조회 성공률 80%에 못 미쳐 순위를 매기지 않습니다.",
    );
  });

  it("버림이 반올림과 다른 값(13개 · 2.6) — 2개 · 11개만 읽혀도 같은 수", () => {
    expect(rank({}, 13)).toBe(
      "13개 사업군이 모두 읽히면 13×20%=2.6에서 소수점을 버려 오른 쪽 2개, 내린 쪽 2개가 순위 조건을 충족합니다. 11개만 읽혀도 같은 수입니다. 10개 이하로 읽히면 조회 성공률 80%에 못 미쳐 순위를 매기지 않습니다.",
    );
  });

  it("k = n(모두 읽혀야)", () => {
    expect(rank({ sector_min_coverage_pct: 100 }, 27)).toBe(
      "27개 사업군이 모두 읽혀야 순위를 매기며, 27×20%=5.4에서 소수점을 버려 오른 쪽 5개, 내린 쪽 5개가 순위 조건을 충족합니다. 26개 이하로 읽히면 조회 성공률 100%에 못 미쳐 순위를 매기지 않습니다.",
    );
    expect(cover({ sector_min_coverage_pct: 100 }, 27)).toBe(
      "27개 사업군이 모두 읽혀야 사업군 판정을 하고, 26개(96.3%) 이하이면 그 회차의 「신규 진입 검토」와 「진입 회피」 구역을 모두 뺍니다. 보유 종목 급등락 알림은 그대로 판정합니다.",
    );
  });

  it("최소 1개를 남기는 경우 · 성공 1개부터 통과(하나도 못 읽으면 미달)", () => {
    expect(rank({ sector_min_coverage_pct: 0 }, 3)).toBe(
      "3개 사업군이 모두 읽히면 3×20%=0.6에서 소수점을 버리면 0개지만 최소 1개를 남겨 오른 쪽 1개, 내린 쪽 1개가 순위 조건을 충족합니다. 1개만 읽혀도 같은 수입니다. 하나도 읽히지 않으면 순위를 매기지 않습니다.",
    );
    expect(cover({ sector_min_coverage_pct: 0 }, 3)).toBe(
      "3개 사업군 중 1개 이상(33.3%)을 읽으면 사업군 판정을 하고, 하나도 읽지 못하면 그 회차의 「신규 진입 검토」와 「진입 회피」 구역을 모두 뺍니다. 보유 종목 급등락 알림은 그대로 판정합니다.",
    );
  });

  it("사업군 수가 0 이하이면 두 칸이 '확인 불가' · 다른 칸은 그대로", () => {
    for (const n of [0, -1]) {
      const rows = rowsOf(CURRENT, n);
      expect(rows.sector_rank_top_pct.meaning).toBe(UNKNOWN);
      expect(rows.sector_min_coverage_pct.meaning).toBe(UNKNOWN);
      expect(rows.sector_rank_top_pct.value).toBe("20%");
      expect(rows.surge_threshold_pct.meaning).toContain("+5.2%");
    }
  });
});

describe("값 · 예시 규칙(I-19 · I-20)", () => {
  it("설정값이 없거나 숫자가 아니면 '확인 불가'(0 이나 '없음' 으로 메우지 않음)", () => {
    for (const bad of [null, undefined, "5", Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(policyValueText("surge_threshold_pct", bad)).toBe("확인 불가");
    }
    expect(policyValueText("cooldown_minutes", 90)).toBe("90분");
    expect(policyValueText("max_sends_per_day", 4)).toBe("4건");
    expect(policyValueText("sector_avoid_drop_pct", -1.5)).toBe("-1.5%");
  });

  it("문장에 필요한 값이 하나라도 없으면 그 칸만 '확인 불가'", () => {
    const rows = rowsOf(
      withValues({ sector_chase_pct: null, max_sends_per_run: null, sector_min_coverage_pct: null }),
      27,
    );
    expect(rows.sector_chase_pct.value).toBe(UNKNOWN);
    expect(rows.sector_chase_pct.meaning).toBe(UNKNOWN);
    expect(rows.sector_entry_min_pct.value).toBe("1.5%");
    expect(rows.sector_entry_min_pct.meaning).toBe(UNKNOWN); // 추격 주의가 함께 쓰임
    expect(rows.max_sends_per_day.value).toBe("4건");
    expect(rows.max_sends_per_day.meaning).toBe(UNKNOWN); // 회차당 최대가 함께 쓰임
    expect(rows.sector_rank_top_pct.meaning).toBe(UNKNOWN); // 최소 조회 성공률이 함께 쓰임
    expect(rows.sector_min_coverage_pct.meaning).toBe(UNKNOWN);
    // 다른 칸은 그대로다.
    expect(rows.sector_avoid_drop_pct.meaning).toContain("-1.6%");
    expect(rows.cooldown_minutes.meaning).toContain("120분(2시간)");

    const noRank = rowsOf(withValues({ sector_rank_top_pct: undefined }), 27);
    expect(noRank.sector_rank_top_pct.what).toBe(UNKNOWN); // '위 20%' 를 쓸 수 없다
    expect(noRank.sector_avoid_drop_pct.meaning).toBe(UNKNOWN);
  });

  it("응답에 키가 아예 없어도 10행은 그린다(값은 전부 '확인 불가' · 보유 급등 · 급락 뜻은 고정 경계)", () => {
    const groups = buildCriteria([], 0);
    const rows = groups.flatMap((g) => g.rows);
    expect(rows).toHaveLength(10);
    expect(rows.every((r) => r.value === UNKNOWN)).toBe(true);
    const holding = new Set(["surge_threshold_pct", "drop_threshold_pct"]);
    expect(rows.filter((r) => !holding.has(r.key)).every((r) => r.meaning === UNKNOWN)).toBe(true);
    expect(rows.filter((r) => holding.has(r.key)).map((r) => r.meaning)).toEqual([
      SURGE_FIXED,
      DROP_FIXED,
    ]);
    expect(criteriaFootnote([])).toBe(RESULT_C9_MISSING_FOOTNOTE);
  });

  it("예시 · 경계는 같은 응답의 값에서 나온다(다른 값)", () => {
    const rows = rowsOf(
      withValues({
        sector_entry_min_pct: 2,
        sector_chase_pct: 5.5,
        sector_avoid_drop_pct: -2,
        sector_rank_top_pct: 25,
        cooldown_minutes: 90,
        max_items_per_section: 4,
        max_sends_per_day: 6,
      }),
      20,
    );
    expect(rows.sector_entry_min_pct.meaning).toContain(
      "오늘 +2.1%인 대표 ETF는 하한을 충족합니다(정확히 +2.0%부터 +5.5% 미만까지). 「신규 진입 검토」로 알리려면 상승 순위 상위 25% 안에 들고,",
    );
    expect(rows.sector_chase_pct.meaning).toContain("오늘 +5.7%(정확히 +5.5% 포함)인");
    expect(rows.sector_avoid_drop_pct.meaning).toContain(
      "오늘 -2.1%(정확히 -2.0% 포함)인 대표 ETF가 하락 순위 하위 25% 안에 들면",
    );
    expect(rows.sector_avoid_drop_pct.meaning).toContain("-2.1%라도 하위 25% 밖이면");
    expect(rows.cooldown_minutes.meaning).toContain("시각부터 90분(1시간 30분) 이상");
    expect(rows.cooldown_minutes.meaning).toContain("90분 안에 다시 잡혀");
    expect(rows.max_items_per_section.meaning).toContain(
      "종목이 6개여도 이번 메시지에는 4개만 실리고, 한 메시지에는 최대 12종목이 실립니다.",
    );
    expect(rows.max_sends_per_day.meaning).toContain("알림을 6건 보내면");
    expect(rows.sector_rank_top_pct.meaning).toBe(
      "20개 사업군이 모두 읽히면 20×25%=5에서 소수점을 버려 오른 쪽 5개, 내린 쪽 5개가 순위 조건을 충족합니다. 16개만 읽히면 4개씩입니다. 15개 이하로 읽히면 조회 성공률 80%에 못 미쳐 순위를 매기지 않습니다.",
    );
  });

  it("재발송 대기 — 60 미만이면 괄호 없음 · 60 의 배수면 시간만", () => {
    expect(rowsOf(withValues({ cooldown_minutes: 45 }), 27).cooldown_minutes.meaning).toContain(
      "시각부터 45분 이상 지난",
    );
    expect(rowsOf(withValues({ cooldown_minutes: 180 }), 27).cooldown_minutes.meaning).toContain(
      "시각부터 180분(3시간) 이상 지난",
    );
  });

  it("진입 검토 예시가 추격 주의 이상이면 예시 절을 빼고 범위 문장만", () => {
    const meaning = rowsOf(withValues({ sector_entry_min_pct: 3.9 }), 27).sector_entry_min_pct
      .meaning;
    expect(meaning).toBe(
      "오늘 등락률이 정확히 +3.9%부터 +4% 미만까지인 대표 ETF는 하한을 충족합니다. 「신규 진입 검토」로 알리려면 상승 순위 상위 20% 안에 들고, 직전 거래일 종가 기준 5일 · 20일 수익률이 모두 0보다 커야 합니다. 보유 중인 종목은 빠집니다.",
    );
    // 바로 아래 값은 예시가 남는다.
    expect(
      rowsOf(withValues({ sector_entry_min_pct: 3.8 }), 27).sector_entry_min_pct.meaning,
    ).toContain("오늘 +3.9%인 대표 ETF는 하한을 충족합니다(정확히 +3.8%부터 +4% 미만까지).");
  });

  it("경계는 소수 첫째 자리 — 0.1 단위가 아닌 값 · 부동소수 오차(백엔드 비교와 같음)", () => {
    // 보유 급등은 설정값을 쓰지 않는다(R1-F1) — 5.05 를 저장해도 경계는 고정 +5%(정확히 +5.0% 포함).
    expect(rowsOf(withValues({ surge_threshold_pct: 5.05 }), 27).surge_threshold_pct.meaning).toBe(
      `${SURGE_FIXED} 이 설정값(+5.05%)은 실제 판정 경계(+5%)와 다릅니다 — 판정에는 +5%가 쓰입니다.`,
    );
    // 0.1 + 0.2 = 0.30000000000000004 — 백엔드 `0.3 >= 0.30000000000000004` 는 거짓이라 0.4 부터다.
    const noisy = 0.1 + 0.2;
    expect(rowsOf(withValues({ sector_chase_pct: noisy }), 27).sector_chase_pct.meaning).toContain(
      "오늘 +0.6%(정확히 +0.4% 포함)인",
    );
    // 반대 방향도 같다 — `-0.3 <= -0.30000000000000004` 는 거짓이라 -0.4 부터다.
    expect(rowsOf(withValues({ sector_avoid_drop_pct: -noisy }), 27).sector_avoid_drop_pct.meaning).toContain(
      "오늘 -0.5%(정확히 -0.4% 포함)인",
    );
    // 오차 없는 값은 그대로다.
    expect(rowsOf(withValues({ sector_chase_pct: 0.3 }), 27).sector_chase_pct.meaning).toContain(
      "오늘 +0.5%(정확히 +0.3% 포함)인",
    );
  });
});

describe("그 밖의 기준(I-18) · 각주 값(I-23)", () => {
  it("모르는 키는 세 묶음 뒤 '그 밖의 기준' · 문장은 '확인 불가'", () => {
    const groups = buildCriteria([...CURRENT, { key: "new_rule_pct", value: 7 }], 27);
    expect(groups.map((g) => g.title)).toEqual([
      "보유 종목 급등락",
      "사업군 대표 ETF 검토",
      "발송 한도와 자료 조건",
      OTHER_GROUP_TITLE,
    ]);
    expect(groups[3].rows).toEqual([
      { key: "new_rule_pct", label: "new_rule_pct", value: "7건", what: UNKNOWN, meaning: UNKNOWN },
    ]);
    // 모르는 키가 없으면 넷째 묶음이 없다.
    expect(buildCriteria(CURRENT, 27)).toHaveLength(3);
  });

  it("각주의 회차당 최대는 응답 값 · 없으면 회차당 최대를 따로 '확인할 수 없습니다'(C9)", () => {
    expect(criteriaFootnote(withValues({ max_sends_per_run: 2 }))).toBe(
      PLAN_FOOTNOTE.replace("회차당 최대 1건은", "회차당 최대 2건은"),
    );
    expect(criteriaFootnote(withValues({ max_sends_per_run: null }))).toBe(
      RESULT_C9_MISSING_FOOTNOTE,
    );
  });
});

// ── 설계자 RESULT 판정(2026-11-19) — C5 표 위 한 줄 · C9 각주 · 조회 성공률 대상 문구 ─────────────
describe("설계자 RESULT 판정 표시 보완(C5 · C9 · 조회 성공률)", () => {
  it("C5 표 위 한 줄 — 판정 문장 두 개가 맨 앞 · PC 대표 ETF 선정 · 버전 단위 승인 문장이 같은 자리에 이어짐", () => {
    expect(CRITERIA_INTRO).toBe(RESULT_C5_INTRO);
    expect(
      CRITERIA_INTRO.startsWith(
        "사업군 판정과 발송 조건은 설정 버전에서 확인합니다. 보유 급등·급락 판정에는 프로그램의 고정 경계를 적용합니다.",
      ),
    ).toBe(true);
    expect(CRITERIA_INTRO).toContain("PC 가 계산하는 것은 사업군 · 대표 ETF 목록(시가총액 순)입니다.");
    expect(CRITERIA_INTRO).toContain("여기서 하나씩 고치지 않고 버전 전체를 승인합니다.");
    expect(CRITERIA_INTRO).not.toContain("판정 기준은 설정 버전에 담긴 고정값입니다.");
  });

  // 활성 · 후보 어느 쪽이든 표에 보이는 값 목록에서 회차당 최대를 읽지 못한 모양 — 칸 없음 · null · 문자열 · NaN.
  it.each([
    ["키 없음(빈 목록)", [] as PolicyValue[]],
    ["키 없음(다른 값은 있음)", CURRENT.filter((p) => p.key !== "max_sends_per_run")],
    ["null", withValues({ max_sends_per_run: null })],
    ["undefined", withValues({ max_sends_per_run: undefined })],
    ['문자열 "1"', withValues({ max_sends_per_run: "1" })],
    ["NaN", withValues({ max_sends_per_run: Number.NaN })],
  ])("C9 회차당 최대가 %s → 문장 분리 각주(글자 그대로) · '확인 불가는' 없음", (_name, values) => {
    const note = criteriaFootnote(values);
    expect(note).toBe(RESULT_C9_MISSING_FOOTNOTE);
    expect(note).not.toContain("확인 불가는");
    expect(note).not.toContain(UNKNOWN);
    // 중복 억제 창 문장은 빠지지 않고 따로 한 문장이다.
    expect(note.startsWith("중복 억제 창은 재발송 대기와 같은 값만 저장되는 다른 이름이라 따로 동작하지 않습니다. ")).toBe(
      true,
    );
  });

  it.each([1, 2, 3])("C9 회차당 최대가 확인되면(%i) 각주는 기존 문장 그대로", (run) => {
    const note = criteriaFootnote(withValues({ max_sends_per_run: run }));
    expect(note).toBe(PLAN_FOOTNOTE.replace("회차당 최대 1건은", `회차당 최대 ${run}건은`));
    expect(note).not.toContain("확인할 수 없습니다");
  });

  it("조회 성공률 '무엇을 보는지' = '이 표에 표시한 설정의 사업군 가운데 …'(값 · 사업군 수와 무관 · 값 없음도 같음)", () => {
    const want =
      "이 표에 표시한 설정의 사업군 가운데 오늘 시세(등락률)를 읽은 사업군의 비율을 봅니다. 대표 ETF 대신 대체 ETF로 읽은 경우도 성공으로 셉니다.";
    for (const [values, n] of [
      [CURRENT, 27],
      [withValues({ sector_min_coverage_pct: 90 }), 20],
      [withValues({ sector_min_coverage_pct: null }), 27],
      [[], 0],
    ] as [PolicyValue[], number][]) {
      const what = rowsOf(values, n).sector_min_coverage_pct.what;
      expect(what).toBe(want);
      expect(what).not.toContain("활성 설정의");
    }
  });
});

// ── 검증자 r1 R1-F1 — 보유 급등 · 급락은 저장된 설정값이 아니라 프로그램 고정 경계 ───────────
// approval → components → app → frontend → 저장소 루트(helpers.test 와 같은 방식 · new URL(…, import.meta.url) 형태를 쓰지 않음)
const REPO_ROOT = path.dirname(
  path.dirname(path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))),
);
const BANDS_FIXTURE = JSON.parse(
  readFileSync(path.join(REPO_ROOT, "tests", "fixtures", "poc6_34_holdings_bands.json"), "utf8"),
) as { surge_lower_bounds_pct: number[]; drop_upper_bounds_pct: number[] };

describe("보유 급등 · 급락 — 프로그램 고정 경계(R1-F1 · 서버와 같은 공용 고정 자료)", () => {
  const holding = (patch: Record<string, unknown>) => {
    const rows = rowsOf(withValues(patch), 27);
    return { surge: rows.surge_threshold_pct, drop: rows.drop_threshold_pct };
  };

  it("화면 고정 경계 = 서버 시험과 같은 공용 고정 자료", () => {
    expect(BANDS_FIXTURE.surge_lower_bounds_pct.length).toBeGreaterThan(0);
    expect(BANDS_FIXTURE.drop_upper_bounds_pct.length).toBeGreaterThan(0);
    expect([...HOLDING_SURGE_LOWER_BOUNDS]).toEqual(BANDS_FIXTURE.surge_lower_bounds_pct);
    expect([...HOLDING_DROP_UPPER_BOUNDS]).toEqual(BANDS_FIXTURE.drop_upper_bounds_pct);
  });

  it("경계 · 예시 · 구간 문장은 고정 자료 값에서 나온다(정확히 경계 포함 · 0.1 안쪽 해당 없음)", () => {
    const [up, up2, up3] = BANDS_FIXTURE.surge_lower_bounds_pct;
    const [dn, dn2, dn3] = BANDS_FIXTURE.drop_upper_bounds_pct;
    const { surge, drop } = holding({});
    expect(surge.meaning).toContain(
      `고정된 +${up}% 이상(+${up} ~ +${up2}% · +${up2} ~ +${up3}% · +${up3}% 이상)으로 판정합니다.`,
    );
    expect(surge.meaning).toContain(
      `오늘 +${(up + 0.2).toFixed(1)}%인 보유 종목은 급등 후보가 됩니다(정확히 +${up.toFixed(1)}% 포함 · +${(up - 0.1).toFixed(1)}% 해당 없음).`,
    );
    expect(drop.meaning).toContain(
      `고정된 ${dn}% 이하(${dn} ~ ${dn2}% · ${dn2} ~ ${dn3}% · ${dn3}% 이하)로 판정합니다.`,
    );
    expect(drop.meaning).toContain(
      `오늘 ${(dn - 0.2).toFixed(1)}%인 보유 종목은 급락 후보가 됩니다(정확히 ${dn.toFixed(1)}% 포함 · ${(dn + 0.1).toFixed(1)}% 해당 없음).`,
    );
  });

  it("저장값 ±5%(고정 경계와 같음) — 설정값 칸은 그대로 · 뜻은 고정 경계 문장만(다르다는 문장 없음)", () => {
    const { surge, drop } = holding({ surge_threshold_pct: 5.0, drop_threshold_pct: -5.0 });
    expect([surge.value, surge.meaning]).toEqual(["5%", SURGE_FIXED]);
    expect([drop.value, drop.meaning]).toEqual(["-5%", DROP_FIXED]);
  });

  it("저장값 ±3%(검증자 재현) — 판정 경계는 ±5% 그대로 · 설정값이 경계와 다르다고 밝힌다", () => {
    const { surge, drop } = holding({ surge_threshold_pct: 3, drop_threshold_pct: -3 });
    expect(surge.value).toBe("3%");
    expect(surge.meaning).toBe(
      `${SURGE_FIXED} 이 설정값(+3%)은 실제 판정 경계(+5%)와 다릅니다 — 판정에는 +5%가 쓰입니다.`,
    );
    expect(drop.value).toBe("-3%");
    expect(drop.meaning).toBe(
      `${DROP_FIXED} 이 설정값(-3%)은 실제 판정 경계(-5%)와 다릅니다 — 판정에는 -5%가 쓰입니다.`,
    );
    // 설정값으로 만든 예시 · 경계(검증자가 본 틀린 문장)가 남지 않는다.
    for (const bad of ["+3.2%", "+3.0%", "+2.9%", "+3%로 고정"]) expect(surge.meaning).not.toContain(bad);
    for (const bad of ["-3.2%", "-3.0%", "-2.9%", "-3%로 고정"]) expect(drop.meaning).not.toContain(bad);
  });

  it("설정값이 없으면 설정값 칸만 '확인 불가' · 뜻은 고정 경계(비교 문장 없음)", () => {
    for (const bad of [null, undefined, "5", Number.NaN]) {
      const { surge, drop } = holding({ surge_threshold_pct: bad, drop_threshold_pct: bad });
      expect([surge.value, surge.meaning]).toEqual([UNKNOWN, SURGE_FIXED]);
      expect([drop.value, drop.meaning]).toEqual([UNKNOWN, DROP_FIXED]);
    }
  });

  it("저장값이 무엇이든 앞 문장(고정 경계)은 같고 다른 값일 때만 한 문장이 붙는다", () => {
    for (const v of [0, 3, 4.9, 5.1, 7, 10, 100]) {
      const { surge } = holding({ surge_threshold_pct: v });
      expect(surge.meaning.startsWith(SURGE_FIXED)).toBe(true);
      expect(surge.meaning.slice(SURGE_FIXED.length)).toBe(
        ` 이 설정값(${v > 0 ? "+" : ""}${v}%)은 실제 판정 경계(+5%)와 다릅니다 — 판정에는 +5%가 쓰입니다.`,
      );
    }
    for (const v of [0, -3, -4.9, -5.1, -7, -10, -100]) {
      const { drop } = holding({ drop_threshold_pct: v });
      expect(drop.meaning.startsWith(DROP_FIXED)).toBe(true);
      expect(drop.meaning.slice(DROP_FIXED.length)).toBe(
        ` 이 설정값(${v}%)은 실제 판정 경계(-5%)와 다릅니다 — 판정에는 -5%가 쓰입니다.`,
      );
    }
  });
});
