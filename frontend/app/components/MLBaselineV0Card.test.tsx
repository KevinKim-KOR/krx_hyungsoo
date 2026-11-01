// POC6-15 — 「Baseline 실험(v0)」 카드 시험(가짜 응답 · 서버 없음).
//
// - 순서: 결론 한 줄 → 설명 → 표 → 접힌 개발 정보(버튼 없음).
// - 상태마다 다른 쉬운 결론(불러오는 중 · 불러오기 실패 종류 · 손상 · 보고 없음 · 보고 내용 없음 ·
//   보고 있음 · 주의 · 과거 자료 부족 · 계산 오류 · 처음 보는 상태 값).
// - 숫자 · 날짜 · 단위는 바꾸기 전과 같음(건수에 쉼표만). 옮긴 개발 식별자는 개발 정보 안에만.
// 픽스처 값 = 2026-11-01 실서버 GET /ml/baseline-v0/latest 응답(sample_asof_results 만 비움).
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import type { MlBaselineV0Report, MlBaselineV0Response } from "@/lib/api";

const fetchMlBaselineV0Latest = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchMlBaselineV0Latest: (...a: unknown[]) => fetchMlBaselineV0Latest(...a),
  };
});

import MLBaselineV0Card from "./MLBaselineV0Card";
import { ApiConfigError, ApiRequestError } from "@/lib/api";

const REPORT: MlBaselineV0Report = {
  status: "ok",
  generated_at: "2026-08-30T14:38:54Z",
  feature_asof_range: { start: "2014-05-12", end: "2026-08-27", trading_days: 3018 },
  evaluated_asof_range: { start: "2014-05-12", end: "2026-07-29", evaluated_days: 2998 },
  coverage_checks: {
    etf_feature_row_count: 1382327,
    market_risk_row_count: 3018,
    trading_days: 3018,
    max_horizon_tail_excluded: 20,
  },
  candidate_baseline: {
    status: "ok",
    evaluated_days: 2998,
    evaluated_ticker_count: 1163,
    target_horizons: [5, 10, 20],
    top_group_quantile: 0.2,
    top_group_avg_future_return: {
      "5d": 0.00315764353585842,
      "10d": 0.005949310734004886,
      "20d": 0.010435815624608043,
    },
    top_group_avg_future_excess_return: {
      "5d": 6.403073221814976e-5,
      "10d": -0.00023436151574926983,
      "20d": -0.0024711617801681874,
    },
    universe_median_future_return: {
      "5d": 0.0007210933886312017,
      "10d": 0.001739376695428089,
      "20d": 0.0037839388340644743,
    },
    hit_rate: { "5d": 0.4852852796462661, "10d": 0.486999568720875, "20d": 0.4772701828840251 },
    rank_correlation: {
      "5d": 0.018575071271503756,
      "10d": 0.029505111588277632,
      "20d": 0.033143418460961624,
    },
    simple_baselines: {
      simple_return_20d_top_quintile_avg_future_return: {
        "5d": 0.003321743619986337,
        "10d": 0.006070771638024268,
        "20d": 0.010471481016567356,
      },
      simple_excess_20d_vs_kodex200_top_quintile_avg_future_return: {
        "5d": 0.003321743619986337,
        "10d": 0.006070771638024268,
        "20d": 0.010471481016567356,
      },
      universe_median_future_return: {
        "5d": 0.0007210933886312017,
        "10d": 0.001739376695428089,
        "20d": 0.0037839388340644743,
      },
    },
    sample_asof_results: [],
    warnings: [],
    errors: [],
  },
  risk_baseline: {
    status: "ok",
    evaluated_days: 2998,
    target_horizons: { return: [3, 5, 10], drawdown: [5, 10], down_ratio: [5] },
    high_risk_group_future_return: {
      "3d": 0.000936007824943626,
      "5d": 0.002359706020668223,
      "10d": 0.004442984099707898,
    },
    high_risk_group_future_drawdown: { "5d": -0.022368284731570286, "10d": -0.0355975564802924 },
    low_risk_group_future_return: {
      "3d": 0.0034740241235944585,
      "5d": 0.005727685452565199,
      "10d": 0.00996181286636904,
    },
    low_risk_group_future_drawdown: { "5d": -0.0153722178933094, "10d": -0.02716587594247846 },
    high_minus_low_return: {
      "3d": -0.0025380162986508325,
      "5d": -0.0033679794318969758,
      "10d": -0.005518828766661142,
    },
    drawdown_capture_rate: { "5d": 1.2300109763248803, "10d": 1.1864725367797915 },
    high_risk_group_future_down_ratio_5d: 0.4532303875314131,
    low_risk_group_future_down_ratio_5d: 0.44269587336279875,
    simple_baselines: {
      kodex200_return_5d: {
        high_risk_future_market_drawdown_10d: -0.034510621108121364,
        high_risk_future_kodex200_return_5d: 0.0024572353607296466,
        low_risk_future_market_drawdown_10d: -0.030986568363322427,
        low_risk_future_kodex200_return_5d: 0.0061382514925364074,
        evaluated_asof_count: 2998,
      },
      drawdown_20d_market_proxy: {
        high_risk_future_market_drawdown_10d: -0.03722206537571507,
        high_risk_future_kodex200_return_5d: 0.002860619151701196,
        low_risk_future_market_drawdown_10d: -0.025718831066984273,
        low_risk_future_kodex200_return_5d: 0.005719633401455483,
        evaluated_asof_count: 2998,
      },
      etf_universe_down_ratio: {
        high_risk_future_market_drawdown_10d: -0.03228557250310544,
        high_risk_future_kodex200_return_5d: 0.0038208634784963964,
        low_risk_future_market_drawdown_10d: -0.029248903550794694,
        low_risk_future_kodex200_return_5d: 0.003980404773735284,
        evaluated_asof_count: 2998,
      },
    },
    sample_asof_results: [],
    warnings: [],
    errors: [],
  },
  leakage_checks: {
    feature_future_data_leakage_detected: false,
    target_horizon_short_tail_excluded: true,
    time_order_preserved: true,
    candidate_tail_asof_count: 62,
    risk_tail_asof_count: 20,
    details: [],
  },
  warnings: [],
  errors: [],
};

const REPORT_PATH = "state/ml/ml_baseline_v0_report_latest.json";

function okResponse(over: Partial<MlBaselineV0Report> = {}): MlBaselineV0Response {
  return { status: "ok", report_path: REPORT_PATH, report: { ...REPORT, ...over }, message: null };
}

const EMPTY_MSG =
  "ML baseline v0 룩백 report 미생성. CLI 'python scripts/run_ml_baseline_v0.py' 를 1회 실행하면 본 화면에 검증 결과가 표시됩니다.";
const CORRUPT_MSG =
  "baseline report 파일이 손상되어 읽을 수 없습니다 (json_decode_failed): Expecting value: line 1 column 1 (char 0)";

function conclusion(container: HTMLElement): HTMLElement {
  const el = container.querySelector<HTMLElement>('[data-role="conclusion"]');
  if (!el) throw new Error("결론 줄 없음");
  return el;
}

function devDetails(container: HTMLElement): HTMLElement {
  const el = container.querySelector<HTMLElement>("details.ml-dev-details");
  if (!el) throw new Error("개발 정보 없음");
  return el;
}

// 개발 정보 칸을 뺀 카드 글자(기본 화면에 보이는 쪽).
function textOutsideDev(container: HTMLElement): string {
  const clone = container.cloneNode(true) as HTMLElement;
  clone.querySelector("details.ml-dev-details")?.remove();
  return clone.textContent ?? "";
}

function rowCells(table: HTMLElement, label: string): string[] {
  const row = within(table)
    .getAllByRole("row")
    .find((r) => r.querySelector("td")?.textContent === label);
  if (!row) throw new Error(`행 없음: ${label}`);
  return Array.from(row.querySelectorAll("td"))
    .slice(1)
    .map((td) => td.textContent ?? "");
}

function isBefore(a: Element, b: Element): boolean {
  return Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
}

beforeEach(() => {
  fetchMlBaselineV0Latest.mockReset();
});

describe("MLBaselineV0Card", () => {
  it("순서 — 결론 한 줄이 설명 · 표 · 개발 정보보다 앞 · 버튼 없음 · 조회는 마운트 때 1회", async () => {
    fetchMlBaselineV0Latest.mockResolvedValue(okResponse());
    const { container } = render(<MLBaselineV0Card />);
    await screen.findByText("보고 있음");
    expect(fetchMlBaselineV0Latest).toHaveBeenCalledTimes(1);
    expect(container.querySelector("h2")?.textContent).toBe("Baseline 실험(v0) — 과거 자료로 되돌아본 검증");
    const concl = conclusion(container);
    const desc = screen.getByText(/추천에 쓸 수 있다는 뜻은 아닙니다/);
    const cand = container.querySelector('[data-role="candidate-table"]')!;
    const risk = container.querySelector('[data-role="risk-table"]')!;
    const simple = container.querySelector('[data-role="simple-compare"]')!;
    const dev = devDetails(container);
    expect(isBefore(container.querySelector("h2")!, concl)).toBe(true);
    expect(isBefore(concl, desc)).toBe(true);
    expect(isBefore(desc, cand)).toBe(true);
    expect(isBefore(cand, risk)).toBe(true);
    expect(isBefore(risk, simple)).toBe(true);
    expect(isBefore(simple, dev)).toBe(true);
    expect(container.querySelectorAll("button")).toHaveLength(0);
    // 설명 = '보고 있음' ≠ 추천 가능 · 다시 계산 위치(CLI 로만 문구 정정)
    expect(desc.textContent).toContain("「이전 자료와 실험 다시 만들기」");
    expect(textOutsideDev(container)).not.toContain("CLI");
    // 단순 기준 비교는 사용자용 접힘(개발 정보와 다른 칸)
    expect(simple.querySelector("summary")?.textContent).toBe("단순 기준과 비교 보기");
    expect(simple.hasAttribute("open")).toBe(false);
    expect(dev.contains(simple)).toBe(false);
  });

  type Case = {
    name: string;
    setup: () => void;
    label: string;
    text?: RegExp;
    tone: string;
  };
  const CASES: Case[] = [
    {
      name: "불러오기 실패 — 설정 오류",
      setup: () => fetchMlBaselineV0Latest.mockRejectedValue(new ApiConfigError("NEXT_PUBLIC_API_BASE 없음")),
      label: "불러오지 못함",
      text: /화면 설정 오류 — 서버 주소 설정이 없습니다$/,
      tone: "ml-readiness-bad",
    },
    {
      name: "불러오기 실패 — 서버 오류 응답",
      setup: () =>
        fetchMlBaselineV0Latest.mockRejectedValue(
          new ApiRequestError("요청 실패: GET /ml/baseline-v0/latest (HTTP 500)", 500, null),
        ),
      label: "불러오지 못함",
      text: /서버가 오류로 응답했습니다\(HTTP 500\)$/,
      tone: "ml-readiness-bad",
    },
    {
      name: "불러오기 실패 — 시간 초과",
      setup: () =>
        fetchMlBaselineV0Latest.mockRejectedValue(
          new ApiRequestError("요청 시간 초과: GET /ml/baseline-v0/latest (10000ms)", 0, null),
        ),
      label: "불러오지 못함",
      text: /서버 응답 시간이 지났습니다$/,
      tone: "ml-readiness-bad",
    },
    {
      name: "불러오기 실패 — 연결 안 됨",
      setup: () =>
        fetchMlBaselineV0Latest.mockRejectedValue(
          new ApiRequestError("네트워크 호출 실패: GET /ml/baseline-v0/latest — Failed to fetch", 0, null),
        ),
      label: "불러오지 못함",
      text: /서버에 연결하지 못했습니다$/,
      tone: "ml-readiness-bad",
    },
    {
      name: "불러오기 실패 — 모르는 요청 실패(원문 보임)",
      setup: () => fetchMlBaselineV0Latest.mockRejectedValue(new ApiRequestError("weird thing", 0, null)),
      label: "불러오지 못함",
      text: /요청 실패 — 원인 확인 필요 · 원문: 요청 실패\(HTTP 0\): weird thing/,
      tone: "ml-readiness-bad",
    },
    {
      name: "불러오기 실패 — 알 수 없는 오류(원문 보임)",
      setup: () => fetchMlBaselineV0Latest.mockRejectedValue(new Error("boom")),
      label: "불러오지 못함",
      text: /알 수 없는 오류 — 원인 확인 필요 · 원문: 알 수 없는 오류: boom/,
      tone: "ml-readiness-bad",
    },
    {
      name: "응답 error — 보고 파일 손상(고정 문장 → 요약)",
      setup: () =>
        fetchMlBaselineV0Latest.mockResolvedValue({
          status: "error",
          report_path: REPORT_PATH,
          report: null,
          message: CORRUPT_MSG,
        }),
      label: "보고 파일 손상",
      text: /^저장된 Baseline 실험 보고 파일이 손상되어 읽을 수 없습니다$/,
      tone: "ml-readiness-bad",
    },
    {
      name: "응답 error — 모르는 메시지(원문 + 원인 확인 필요)",
      setup: () =>
        fetchMlBaselineV0Latest.mockResolvedValue({
          status: "error",
          report_path: REPORT_PATH,
          report: null,
          message: "disk gone",
        }),
      label: "보고 파일 손상",
      text: /원문: disk gone · 원인 확인 필요$/,
      tone: "ml-readiness-bad",
    },
    {
      name: "응답 empty — 보고 없음",
      setup: () =>
        fetchMlBaselineV0Latest.mockResolvedValue({
          status: "empty",
          report_path: REPORT_PATH,
          report: null,
          message: EMPTY_MSG,
        }),
      label: "보고 없음",
      text: /^Baseline 실험 보고가 아직 만들어지지 않았습니다 · 위 「이전 자료와 실험 다시 만들기」에서 만들 수 있습니다$/,
      tone: "ml-readiness-missing",
    },
    {
      name: "응답 ok · 보고 null — 보고 내용 없음",
      setup: () =>
        fetchMlBaselineV0Latest.mockResolvedValue({ status: "ok", report_path: REPORT_PATH, report: null }),
      label: "보고 내용 없음",
      text: /응답 상태 값 ‘ok’인데 보고 내용이 비어 있습니다 · 원인 확인 필요/,
      tone: "ml-readiness-partial",
    },
    {
      name: "모르는 응답 상태 · 보고 null — 원래 값 보임",
      setup: () =>
        fetchMlBaselineV0Latest.mockResolvedValue({
          status: "stale" as MlBaselineV0Response["status"],
          report_path: REPORT_PATH,
          report: null,
        }),
      label: "보고 내용 없음",
      text: /응답 상태 값 ‘stale’인데 보고 내용이 비어 있습니다 · 원인 확인 필요/,
      tone: "ml-readiness-partial",
    },
    {
      name: "보고 ok — 보고 있음",
      setup: () => fetchMlBaselineV0Latest.mockResolvedValue(okResponse()),
      label: "보고 있음",
      text: /^자료 기간 2014-05-12 ~ 2026-08-27\(3,018거래일\) · 평가 2,998거래일 · 1,163종목$/,
      tone: "ml-readiness-available",
    },
    {
      name: "보고 warn — 주의(경고 건수)",
      setup: () =>
        fetchMlBaselineV0Latest.mockResolvedValue(
          okResponse({ status: "warn", warnings: ["rank correlation 산출 불가 (target join 부족)"] }),
        ),
      label: "주의",
      text: /1,163종목 · 경고 1건$/,
      tone: "ml-readiness-partial",
    },
    {
      name: "보고 insufficient_history — 과거 자료 부족",
      setup: () => fetchMlBaselineV0Latest.mockResolvedValue(okResponse({ status: "insufficient_history" })),
      label: "과거 자료 부족",
      text: /^자료 기간 2014-05-12 ~ 2026-08-27/,
      tone: "ml-readiness-partial",
    },
    {
      name: "보고 error — 계산 오류(오류 건수)",
      setup: () =>
        fetchMlBaselineV0Latest.mockResolvedValue(
          okResponse({ status: "error", errors: ["market_risk_feature_daily 가 비어있음"] }),
        ),
      label: "계산 오류",
      text: /1,163종목 · 오류 1건$/,
      tone: "ml-readiness-bad",
    },
    {
      name: "모르는 보고 상태 — 원래 값 그대로",
      setup: () => fetchMlBaselineV0Latest.mockResolvedValue(okResponse({ status: "weird_status" })),
      label: "weird_status",
      text: /처음 보는 상태 값 — 확인 필요$/,
      tone: "ml-readiness-missing",
    },
  ];

  it.each(CASES)("상태별 결론 — $name", async ({ setup, label, text, tone }) => {
    setup();
    const { container } = render(<MLBaselineV0Card />);
    await waitFor(() => expect(conclusion(container).textContent).not.toContain("불러오는 중"));
    const concl = conclusion(container);
    const badge = concl.querySelector(".ml-readiness-badge")!;
    expect(badge.textContent).toBe(label);
    expect(badge.className).toContain(tone);
    if (text) expect(concl.querySelector(".ml-conclusion-text")?.textContent ?? "").toMatch(text);
    // 결론이 '실패'로 뭉개지지 않음 — warn · 부족 · 없음은 '실패' 글자를 쓰지 않는다
    if (["주의", "과거 자료 부족", "보고 없음", "보고 있음"].includes(label)) {
      expect(concl.textContent).not.toContain("실패");
    }
  });

  it("상태별 결론 — 서로 다른 상태는 서로 다른 결론(배지 + 문장)", async () => {
    const seen = new Map<string, string>();
    for (const c of CASES) {
      fetchMlBaselineV0Latest.mockReset();
      c.setup();
      const { container, unmount } = render(<MLBaselineV0Card />);
      await waitFor(() => expect(conclusion(container).textContent).not.toContain("불러오는 중"));
      const key = conclusion(container).textContent ?? "";
      expect(seen.has(key), `${c.name} = ${seen.get(key)}`).toBe(false);
      seen.set(key, c.name);
      unmount();
    }
  });

  it("불러오는 중 — 응답 전 결론", async () => {
    fetchMlBaselineV0Latest.mockReturnValue(new Promise(() => {}));
    const { container } = render(<MLBaselineV0Card />);
    expect(conclusion(container).textContent).toBe("불러오는 중");
    expect(container.querySelector('[data-role="candidate-table"]')).toBeNull();
  });

  it("숫자 · 날짜 · 단위 그대로 — 두 표 · 단순 기준 비교 · 설명 줄", async () => {
    fetchMlBaselineV0Latest.mockResolvedValue(okResponse());
    const { container } = render(<MLBaselineV0Card />);
    await screen.findByText("보고 있음");
    const cand = container.querySelector<HTMLElement>('[data-role="candidate-table"]')!;
    expect(rowCells(cand, "종합 점수 상위 20% — 이후 평균 수익률")).toEqual(["+0.32%", "+0.59%", "+1.04%"]);
    expect(rowCells(cand, "종합 점수 상위 20% — KODEX 200 대비 평균 초과 수익")).toEqual([
      "+0.01%",
      "-0.02%",
      "-0.25%",
    ]);
    expect(rowCells(cand, "전체 ETF — 이후 수익률 중앙값")).toEqual(["+0.07%", "+0.17%", "+0.38%"]);
    expect(rowCells(cand, "종합 점수 상위 20% 중 KODEX 200보다 나은 비율")).toEqual(["0.485", "0.487", "0.477"]);
    expect(rowCells(cand, "점수 순위와 이후 수익률의 순위 상관")).toEqual(["0.019", "0.030", "0.033"]);
    expect(rowCells(cand, "단순 기준: 지난 20일 수익률 상위 20% — 이후 평균 수익률")).toEqual([
      "+0.33%",
      "+0.61%",
      "+1.05%",
    ]);
    expect(rowCells(cand, "단순 기준: 지난 20일 KODEX 200 대비 초과 수익 상위 20% — 이후 평균 수익률")).toEqual([
      "+0.33%",
      "+0.61%",
      "+1.05%",
    ]);

    const risk = container.querySelector<HTMLElement>('[data-role="risk-table"]')!;
    const heads = Array.from(risk.querySelectorAll("th")).map((th) => th.textContent);
    expect(heads).toEqual([
      "구간",
      "이후 KODEX 200 수익률 3일",
      "5일",
      "10일",
      "이후 KODEX 200 고점 대비 최대 하락폭 5일",
      "10일",
    ]);
    expect(rowCells(risk, "위험 점수 상위 1/3")).toEqual(["+0.09%", "+0.24%", "+0.44%", "-2.24%", "-3.56%"]);
    expect(rowCells(risk, "위험 점수 하위 1/3")).toEqual(["+0.35%", "+0.57%", "+1.00%", "-1.54%", "-2.72%"]);
    expect(textOutsideDev(container)).not.toContain("D20");

    const simple = container.querySelector<HTMLElement>('[data-role="simple-compare"]')!;
    expect(rowCells(simple, "지난 5일 KODEX 200 수익률(작을수록 위험)")).toEqual([
      "-3.45%",
      "-3.10%",
      "+0.25%",
      "+0.61%",
    ]);
    expect(rowCells(simple, "지난 20일 고점 대비 KODEX 200 하락폭(작을수록 위험)")).toEqual([
      "-3.72%",
      "-2.57%",
      "+0.29%",
      "+0.57%",
    ]);
    expect(rowCells(simple, "시장 폭 악화(그날 내린 ETF 비율이 클수록 위험)")).toEqual([
      "-3.23%",
      "-2.92%",
      "+0.38%",
      "+0.40%",
    ]);

    const body = textOutsideDev(container);
    expect(body).toContain("평가 2,998거래일 · 1,163종목.");
    expect(body).toContain("이후 5일 동안 내린 ETF 비율(하루 평균): 상위 0.453 · 하위 0.443.");
    // 보고 만든 시각(실행일)은 개발 정보에만 숨기지 않음 — 본문 아래 · 개발 정보 앞
    const gen = container.querySelector<HTMLElement>('[data-role="generated-at"]')!;
    expect(gen.textContent).toBe("보고 만든 시각 2026-08-30 23:38:54(한국 시각)");
    expect(devDetails(container).contains(gen)).toBe(false);
    expect(isBefore(gen, devDetails(container))).toBe(true);
    // 개발 정보 — 범위 검사 건수는 쉼표만(줄이지 않음)
    expect(devDetails(container).textContent).toContain("etf_feature_row_count=1,382,327");
    expect(devDetails(container).textContent).toContain("candidate tail asof count=62");
    expect(devDetails(container).textContent).toContain("2026-08-30T14:38:54Z (한국 시각 2026-08-30 23:38:54)");
  });

  it("옮긴 개발 식별자는 개발 정보 안에만 — 명령 · 파일 경로 · 원래 지표 이름 · 누수 검사 이름", async () => {
    fetchMlBaselineV0Latest.mockResolvedValue(okResponse());
    const { container } = render(<MLBaselineV0Card />);
    await screen.findByText("보고 있음");
    const dev = devDetails(container).textContent ?? "";
    const body = textOutsideDev(container);
    for (const id of [
      "scripts/run_ml_baseline_v0.py",
      REPORT_PATH,
      "composite rank v0",
      "hit rate (excess > 0)",
      "rank correlation",
      "future market drawdown",
      "drawdown_20d_market_proxy",
      "future data leakage detected=false",
      "horizon tail excluded=true",
    ]) {
      expect(dev, id).toContain(id);
      expect(body, id).not.toContain(id);
    }
  });

  it("경고 · 오류 · 누수 이상은 본문에도 — 고정 문장은 쉬운 말 · 모르는 문장은 원문 + 확인 필요", async () => {
    fetchMlBaselineV0Latest.mockResolvedValue(
      okResponse({
        status: "error",
        warnings: ["rank correlation 산출 불가 (target join 부족)", "new warning text"],
        errors: ["kodex200(069500) close 시계열이 etf_ml_feature_daily 에 없음", "mystery failure"],
        leakage_checks: { ...REPORT.leakage_checks, feature_future_data_leakage_detected: true },
      }),
    );
    const { container } = render(<MLBaselineV0Card />);
    await screen.findByText("계산 오류");
    expect(conclusion(container).textContent).toContain("경고 2건 · 오류 2건");
    const errBox = container.querySelector<HTMLElement>('[data-role="report-errors"]')!;
    const warnBox = container.querySelector<HTMLElement>('[data-role="report-warnings"]')!;
    expect(isBefore(conclusion(container), errBox)).toBe(true);
    expect(isBefore(warnBox, screen.getByText(/추천에 쓸 수 있다는 뜻은 아닙니다/))).toBe(true);
    expect(errBox.textContent).toContain("오류 2건");
    expect(errBox.textContent).toContain("KODEX 200(069500) 종가 자료가 ETF 학습용 값에 없습니다");
    expect(errBox.textContent).toContain("mystery failure — 처음 보는 문장 · 원인 확인 필요");
    expect(errBox.textContent).toContain("미래 자료 섞임 의심");
    expect(warnBox.textContent).toContain("경고 2건");
    expect(warnBox.textContent).toContain("점수 순위와 이후 수익률의 순위 상관을 계산하지 못했습니다");
    expect(warnBox.textContent).toContain("new warning text — 처음 보는 문장 · 확인 필요");
    // 고정 문장 원문은 개발 정보에만
    const dev = devDetails(container).textContent ?? "";
    expect(dev).toContain("rank correlation 산출 불가 (target join 부족)");
    expect(dev).toContain("kodex200(069500) close 시계열이 etf_ml_feature_daily 에 없음");
    expect(textOutsideDev(container)).not.toContain("etf_ml_feature_daily");
  });

  it("누수 검사 — 마지막 구간 · 날짜 순서 이상과 참 · 거짓이 아닌 값은 본문 오류 칸에 각각 보임", async () => {
    fetchMlBaselineV0Latest.mockResolvedValue(
      okResponse({
        leakage_checks: {
          ...REPORT.leakage_checks,
          target_horizon_short_tail_excluded: false,
          time_order_preserved: false,
        },
      }),
    );
    const a = render(<MLBaselineV0Card />);
    await screen.findByText("보고 있음");
    const box = a.container.querySelector<HTMLElement>('[data-role="report-errors"]')!;
    expect(box.textContent).toContain("결과 기간이 모자란 마지막 거래일에 이후 결과 값이 들어 있습니다");
    expect(box.textContent).toContain("날짜 순서가 어긋난 자료가 있습니다 · 원인 확인 필요");
    expect(box.textContent).not.toContain("미래 자료 섞임 의심");
    a.unmount();

    const odd = { ...REPORT.leakage_checks } as Record<string, unknown>;
    delete odd.time_order_preserved;
    odd.feature_future_data_leakage_detected = "maybe";
    fetchMlBaselineV0Latest.mockResolvedValue(
      okResponse({ leakage_checks: odd as unknown as MlBaselineV0Report["leakage_checks"] }),
    );
    const b = render(<MLBaselineV0Card />);
    await screen.findByText("보고 있음");
    const box2 = b.container.querySelector<HTMLElement>('[data-role="report-errors"]')!;
    expect(box2.textContent).toContain("미래 자료 섞임 검사 값 ‘maybe’ — 처음 보는 값입니다 · 원인 확인 필요");
    expect(box2.textContent).toContain("날짜 순서 검사 값 ‘undefined’ — 처음 보는 값입니다 · 원인 확인 필요");
    expect(box2.textContent).not.toContain("마지막 구간 제외 검사");
  });

  it("정상 보고(경고 0 · 오류 0 · 누수 이상 없음)엔 경고 칸 없음 · 모르는 응답 상태는 원래 값 보임", async () => {
    fetchMlBaselineV0Latest.mockResolvedValue(okResponse());
    const first = render(<MLBaselineV0Card />);
    await screen.findByText("보고 있음");
    expect(first.container.querySelector('[data-role="report-errors"]')).toBeNull();
    expect(first.container.querySelector('[data-role="report-warnings"]')).toBeNull();
    expect(first.container.querySelectorAll(".message")).toHaveLength(0);
    first.unmount();

    fetchMlBaselineV0Latest.mockResolvedValue({ ...okResponse(), status: "partial" as MlBaselineV0Response["status"] });
    const second = render(<MLBaselineV0Card />);
    await screen.findByText("보고 있음");
    expect(textOutsideDev(second.container)).toContain("응답 상태 값 ‘partial’ — 처음 보는 값입니다 · 확인 필요");
  });

  it("응답 메시지 원문 · 오류 원문은 개발 정보에 남음(고정 문장은 본문에서 요약만)", async () => {
    fetchMlBaselineV0Latest.mockResolvedValue({
      status: "empty",
      report_path: REPORT_PATH,
      report: null,
      message: EMPTY_MSG,
    });
    const a = render(<MLBaselineV0Card />);
    await screen.findByText("보고 없음");
    expect(devDetails(a.container).textContent).toContain(EMPTY_MSG);
    expect(textOutsideDev(a.container)).not.toContain("run_ml_baseline_v0");
    a.unmount();

    fetchMlBaselineV0Latest.mockRejectedValue(
      new ApiRequestError("요청 실패: GET /ml/baseline-v0/latest (HTTP 503)", 503, null),
    );
    const b = render(<MLBaselineV0Card />);
    await screen.findByText("불러오지 못함");
    expect(devDetails(b.container).textContent).toContain(
      "오류 원문: 요청 실패(HTTP 503): 요청 실패: GET /ml/baseline-v0/latest (HTTP 503)",
    );
  });
});
