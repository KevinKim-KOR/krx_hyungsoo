// POC5-08 — 「받은 알림 기록」 사후평가 화면 test(설계 §8 · 사용자 확인 목업 2026-10-11).
//
// - 진입 · 상세 열기 = 최신 결과 GET 만(실행 0) · [사후평가 실행] 을 눌렀을 때만 POST 1회 → 다시 GET.
// - 요약: 기준 날짜 4개 · 건수 · 가격 결과 표 · ML 과거 검증(자료 부족 / 비교) · 구간 표 · 입력 변경 안내.
// - 실행이 산출물을 못 만들면(사본 없음 · 확인 필요 · 실패) 그 문구 — 성공처럼 보이지 않는다.
// - 상세: 항목 · 계열마다 한 줄(알림 전체 점수 없음) · 내 평가와 따로 · 평가 없는 알림도 같은 표.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import type {
  LedgerAlertCard,
  LedgerAlertDetail,
  RetroItem,
  RetroResult,
  RetroSlot,
} from "@/lib/api";

const fetchLedgerAlerts = vi.fn();
const fetchLedgerAlertDetail = vi.fn();
const syncDecisionLedger = vi.fn();
const fetchRetrospectiveLatest = vi.fn();
const runRetrospective = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchLedgerAlerts: (...a: unknown[]) => fetchLedgerAlerts(...a),
    fetchLedgerAlertDetail: (...a: unknown[]) => fetchLedgerAlertDetail(...a),
    syncDecisionLedger: (...a: unknown[]) => syncDecisionLedger(...a),
    fetchRetrospectiveLatest: (...a: unknown[]) => fetchRetrospectiveLatest(...a),
    runRetrospective: (...a: unknown[]) => runRetrospective(...a),
  };
});

import AlertRecordsView from "../AlertRecordsView";
import { ApiRequestError } from "@/lib/api";
import { buildRetroRows, priceCell } from "./RetroItemRows";

const CARD: LedgerAlertCard = {
  event_id: "E1",
  push_kind: "holdings_risk_alert",
  time_kst: "09:30",
  schedule_expected: "09:30",
  off_schedule: false,
  delivery_status: "sent",
  key_items: [{ subject_kind: "sector", subject_id: "SEMI", name: "반도체" }],
  latest_feedback: null,
  feedback_count: 0,
};

const DETAIL: LedgerAlertDetail = {
  event_id: "E1",
  push_kind: "holdings_risk_alert",
  time_kst: "09:30",
  runtime_date_kst: "2026-12-01",
  schedule_expected: "09:30",
  off_schedule: false,
  outcome_event_target: true,
  delivery_status: "sent",
  body_text: "본문",
  body_withheld: false,
  body_partial_delivery: false,
  items: [
    {
      item_seq: 1,
      subject_kind: "sector",
      subject_id: "SEMI",
      name: "반도체 사업군",
      held: null,
      state: "AVOID_DROP",
      prev_state: null,
      state_label: null,
      prev_state_label: null,
      disposition: "sent",
      event_type: null,
      t0_price: 100,
      t0_price_asof: "x",
      evaluable: true,
      outcome_target: true,
    },
    {
      item_seq: 2,
      subject_kind: "ticker",
      subject_id: "005930",
      name: "삼성전자",
      held: 1,
      state: null,
      prev_state: null,
      state_label: null,
      prev_state_label: null,
      disposition: "not_selected",
      event_type: null,
      t0_price: 70000,
      t0_price_asof: "x",
      evaluable: true,
      outcome_target: true,
    },
  ],
  feedback: [],
  outcomes: [
    {
      item_seq: 1,
      series_id: "krx_etf:091160",
      series_name: "KODEX 반도체",
      horizon: 1,
      status: "MATURED",
      t0_price: 100,
      t0_price_asof: "x",
      eval_date: "2026-12-01",
      eval_price: 100.85,
      return_raw: 0.0085,
      max_up_raw: null,
      max_down_raw: null,
      path_points: 1,
    },
  ],
};

function slot(over: Partial<RetroSlot>): RetroSlot {
  return {
    series_id: null,
    horizon: 1,
    status: "PENDING_NOT_DUE",
    status_text: "미도래",
    eval_date: null,
    expected_eval_date: null,
    t0_price: null,
    t0_price_asof: null,
    eval_price: null,
    return_raw: null,
    max_up_raw: null,
    max_down_raw: null,
    path_points: null,
    partial_path: false,
    price_basis: null,
    computed_at: null,
    sign: null,
    sign_text: null,
    ml: null,
    ...over,
  };
}

const ITEMS: RetroItem[] = [
  {
    event_id: "E1",
    item_seq: 1,
    signal_date: "2026-12-01",
    push_kind: "holdings_risk_alert",
    subject_kind: "sector",
    subject_id: "SEMI",
    disposition: "sent",
    delivered: true,
    partial: false,
    slots: [
      slot({
        series_id: "krx_etf:091160",
        horizon: 1,
        status: "MATURED",
        status_text: "성숙",
        eval_date: "2026-12-01",
        t0_price: 100,
        eval_price: 100.85,
        return_raw: 0.0085,
        max_up_raw: 0.009,
        max_down_raw: -0.002,
        path_points: 1,
        price_basis: "KRX_ETF_UNADJUSTED",
        computed_at: "2026-12-01T23:10:00+00:00",
      }),
      slot({
        series_id: "krx_etf:091160",
        horizon: 5,
        status: "MATURED",
        status_text: "성숙",
        eval_date: "2026-12-07",
        t0_price: 100,
        eval_price: 97,
        return_raw: -0.03,
        max_up_raw: 0.005,
        max_down_raw: -0.034,
        path_points: 5,
        price_basis: "KRX_ETF_UNADJUSTED",
        computed_at: "2026-12-07T23:10:00+00:00",
        sign: "DOWN",
        sign_text: "기준가격 대비 +5 종가 하락",
        ml: {
          status: "ESTIMATED",
          reason: null,
          reason_text: null,
          block: 3,
          actual_pct: -3,
          estimate_pct: -1,
          baseline_pct: -0.5,
          abs_error_pp: 2,
          baseline_abs_error_pp: 2.5,
        },
      }),
      slot({ horizon: 20, expected_eval_date: "2026-12-29" }),
    ],
  },
  {
    event_id: "E1",
    item_seq: 2,
    signal_date: "2026-12-01",
    push_kind: "holdings_risk_alert",
    subject_kind: "ticker",
    subject_id: "005930",
    disposition: "not_selected",
    delivered: false,
    partial: false,
    slots: [
      slot({ horizon: 1, status: "PENDING_DUE", status_text: "도래 후 미기록" }),
      slot({
        horizon: 5,
        expected_eval_date: "2026-12-07",
        ml: { status: "NONE", reason: "NOT_MATURED", reason_text: "+5 미성숙", block: null },
      }),
      slot({ horizon: 20, expected_eval_date: "2026-12-29" }),
    ],
  },
];

function result(over: Partial<RetroResult> = {}): RetroResult {
  return {
    schema: "alert_retro.v1",
    status: "OK",
    status_text: "사후평가 완료",
    end_date: "2026-10-08",
    run_id: "20261011T220330000000_abcdef12",
    created_at: "2026-10-11T22:03:31+09:00",
    snapshot_acquired_at: "2026-10-11T22:03:30+09:00",
    price_asof_date: "2026-10-08",
    copy_sync: { last_success_at: "2026-10-08T10:15:49+09:00", last_failure_at: null },
    summary: {
      denominators: { events: 3, items: 88, price_observations: 93, price_slots: 279, signal_dates: 1, series_recorded: 0 },
      status_by_horizon: {
        "1": { PENDING_DUE: 93 },
        "5": { PENDING_NOT_DUE: 90, PRICE_MISSING: 2, T0_MISSING: 1 },
        "20": { PENDING_NOT_DUE: 93 },
      },
      delivery: { dispositions: {}, delivered_items: 10, partial_items: 0, exposure: {} },
    },
    ml: {
      status: "DATA_SHORT",
      reason: "세 구간이 모두 유효하지 않음 — 구간별 진단만",
      blocks: [1, 2, 3].map((i) => ({
        index: i,
        days: [],
        start: `2026-09-0${i}`,
        end: `2026-09-1${i}`,
        test_rows: 0,
        test_dates: 0,
        test_groups: {},
        status: "DATA_SHORT" as const,
        reason: "시험 행 없음",
      })),
      overall: null,
      eligible_rows: 0,
      not_eligible: { NOT_MATURED: 85, OUT_OF_SCOPE: 8 },
    },
    feedback_summary: { events_with_feedback: 1, events_without_feedback: 2 },
    input_changed: false,
    input_check: "입력 변경 없음",
    ...over,
  };
}

const NO_RESULT: RetroResult = {
  schema: "alert_retro.v1",
  status: "NO_RESULT",
  status_text: "아직 사후평가 결과가 없습니다",
  end_date: null,
};

beforeEach(() => {
  for (const f of [fetchLedgerAlerts, fetchLedgerAlertDetail, syncDecisionLedger, fetchRetrospectiveLatest, runRetrospective]) {
    f.mockReset();
  }
  fetchLedgerAlerts.mockResolvedValue({
    date: "2026-12-01",
    kind: "all",
    sync: { has_copy: true, last_success_at: "2026-12-02T08:20:00+09:00", last_failure_at: null, last_failure_kind: null },
    alerts: [CARD],
  });
  fetchLedgerAlertDetail.mockResolvedValue(DETAIL);
  fetchRetrospectiveLatest.mockImplementation((eventId?: string) =>
    Promise.resolve(
      eventId ? result({ event: { event_id: eventId, items: ITEMS, feedback: null } }) : result()
    )
  );
});

describe("POC5-08 사후평가 — 요약 카드", () => {
  it("진입은 최신 결과 GET 만 — 실행(POST) 0 · 결과가 없으면 안내", async () => {
    fetchRetrospectiveLatest.mockResolvedValue(NO_RESULT);
    render(<AlertRecordsView />);
    expect(await screen.findByText(/아직 사후평가 결과가 없습니다/)).toBeTruthy();
    expect(fetchRetrospectiveLatest).toHaveBeenCalledWith();
    expect(runRetrospective).not.toHaveBeenCalled();
  });

  it("기준 날짜 4개 · 건수 · 가격 결과 · ML 자료 부족 · 구간 표 · 입력 변경 없음", async () => {
    render(<AlertRecordsView />);
    const card = await screen.findByTestId("retro-summary");
    await waitFor(() => expect(within(card).getByText("가격 관측 기준일")).toBeTruthy());
    expect(within(card).getAllByText("2026-10-08").length).toBe(2); // 종료일 · 가격 관측 기준일
    expect(within(card).getAllByText("10-11 22:03").length).toBe(2); // 사본 읽은 시각 · 생성 시각
    expect(within(card).getByText("생성 시각")).toBeTruthy();
    expect(within(card).getByText("10-08 10:15")).toBeTruthy(); // 사본 동기화
    expect(within(card).getByText("입력 변경 없음")).toBeTruthy();
    expect(within(card).queryByText(/입력이 변경됨/)).toBeNull();
    const counts = screen.getByTestId("retro-counts").textContent ?? "";
    expect(counts).toMatch(/알림 3 · 항목 88 · 가격 관측 93 · 신호일 1일/);
    expect(counts).toMatch(/전달된 항목 10 · 평가 있는 알림 1 \/ 없음 2/);
    expect(counts).not.toMatch(/일부 전달/);
    expect(screen.queryByTestId("retro-excluded")).toBeNull(); // 뺀 항목이 없으면 줄 없음
    const plus5 = within(card).getByText("+5 거래일").closest("tr") as HTMLElement;
    expect(Array.from(plus5.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "+5 거래일",
      "0",
      "90",
      "0",
      "3",
    ]);
    expect(plus5.querySelectorAll("td")[4].getAttribute("title")).toBe(
      "기준 가격 없음 1 · 가격 자료 없음 2"
    );
    expect(screen.getByTestId("retro-ml").textContent).toBe(
      "ML 과거 검증(+5): 자료 부족 — 세 구간이 모두 유효하지 않음 — 구간별 진단만 · 대상 0행(+5 미성숙 85 · 이번 ML 범위 밖 8)"
    );
    expect(within(card).getAllByText("자료 부족 · 시험 행 없음").length).toBe(3);
    expect(within(card).getByText(/세 구간 전체 비교는/)).toBeTruthy();
    expect(within(card).queryByText(/12-09/)).toBeNull(); // 고정 날짜를 화면에 박지 않는다
  });

  it("세 구간 비교가 되면 판정 문구 · 구간 MAE · 입력이 바뀌었으면 재실행 필요", async () => {
    const valid = (i: number, m: number, b: number) => ({
      index: i,
      days: [],
      start: "2026-11-12",
      end: "2026-11-18",
      test_rows: 425,
      test_dates: 5,
      test_groups: {},
      status: "VALID" as const,
      reason: null,
      train_dates: 15 + 5 * i,
      model_mae_pp: m,
      baseline_mae_pp: b,
    });
    fetchRetrospectiveLatest.mockResolvedValue(
      result({
        input_changed: true,
        input_check: "입력이 변경됨 · 재실행 필요",
        ml: {
          status: "COMPARED",
          reason: null,
          blocks: [valid(1, 2.31, 2.58), valid(2, 2.52, 2.49), valid(3, 2.37, 2.76)],
          overall: {
            test_dates: 15,
            model_mae_pp: 2.4,
            baseline_mae_pp: 2.61,
            difference_pp: -0.21,
            verdict: "IMPROVED",
            verdict_text: "개선",
          },
          eligible_rows: 3000,
          not_eligible: {},
        },
      })
    );
    render(<AlertRecordsView />);
    expect(await screen.findByText(/입력이 변경됨 · 재실행 필요 — 이 결과를 만든 뒤/)).toBeTruthy();
    expect(screen.getByTestId("retro-ml").textContent).toBe(
      "ML 과거 검증(+5): 개선 — 전체 모델 MAE 2.40%p · 단순 기준 2.61%p (차이 -0.21%p · 날짜 균형 · 15 시험일)"
    );
    expect(screen.getByText("2.31%p")).toBeTruthy();
    expect(screen.getAllByText("유효").length).toBe(3);
    expect(screen.queryByText("입력 변경 없음")).toBeNull();
    expect(screen.queryByText(/세 구간 전체 비교는/)).toBeNull();
  });
});

describe("POC5-08 사후평가 — 뺀 항목 · 입력 확인 불가", () => {
  it("대상에서 뺀 항목의 사유 · 건수 줄 · 입력 변경을 확인할 수 없으면 경고 줄", async () => {
    fetchRetrospectiveLatest.mockResolvedValue(
      result({
        exclusions: { after_end: 2, cohort_not_primary_live: 1, off_schedule: 3 },
        input_changed: null,
        input_check: "사본 확인 필요 — 입력 변경을 확인할 수 없습니다",
      })
    );
    render(<AlertRecordsView />);
    expect((await screen.findByTestId("retro-excluded")).textContent).toBe(
      "대상에서 뺀 항목 신호 기간 끝 뒤 2 · 운영 표본 아님(LEGACY 등) 1 · 예정 외 실행 3"
    );
    expect(
      screen.getByText("사본 확인 필요 — 입력 변경을 확인할 수 없습니다 — 아래는 기존 결과입니다.")
    ).toBeTruthy();
    expect(screen.queryByText("입력 변경 없음")).toBeNull();
  });
});

describe("POC5-08 사후평가 — [사후평가 실행]", () => {
  it("누를 때만 POST 1회 · 실행 중 버튼 잠금 · 끝나면 최신 결과를 다시 읽는다", async () => {
    let finish: (r: RetroResult) => void = () => {};
    runRetrospective.mockReturnValue(new Promise<RetroResult>((r) => (finish = r)));
    render(<AlertRecordsView />);
    await screen.findByTestId("retro-ml");
    const before = fetchRetrospectiveLatest.mock.calls.filter((c) => c.length === 0).length;
    fireEvent.click(screen.getByRole("button", { name: "사후평가 실행" }));
    const busy = await screen.findByRole("button", { name: "사후평가 중..." });
    expect((busy as HTMLButtonElement).disabled).toBe(true);
    finish(result());
    await screen.findByRole("button", { name: "사후평가 실행" });
    expect(runRetrospective).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(fetchRetrospectiveLatest.mock.calls.filter((c) => c.length === 0).length).toBe(
        before + 1
      )
    );
    expect(syncDecisionLedger).not.toHaveBeenCalled(); // 원장 새로고침과 따로
    expect(screen.queryByText(/사후평가 실행 —/)).toBeNull();
  });

  it.each([
    [
      { ...NO_RESULT, status: "NO_COPY" as const, status_text: "PC 원장 사본이 없습니다 — 먼저 [원장 새로고침]" },
      "사후평가 실행 — PC 원장 사본이 없습니다 — 먼저 [원장 새로고침]",
    ],
    [
      {
        ...NO_RESULT,
        status: "CHECK_REQUIRED" as const,
        status_text: "원장 사본 확인 필요 — 산출물을 만들지 않았습니다",
        problems: ["중복 키: 같은 가격 결과 키가 2행 이상 1건"],
      },
      "사후평가 실행 — 원장 사본 확인 필요 — 산출물을 만들지 않았습니다 — 중복 키: 같은 가격 결과 키가 2행 이상 1건",
    ],
  ])("산출물을 못 만든 실행은 그 상태 문구(성공처럼 보이지 않음)", async (res, text) => {
    runRetrospective.mockResolvedValue(res);
    render(<AlertRecordsView />);
    await screen.findByTestId("retro-ml");
    fireEvent.click(screen.getByRole("button", { name: "사후평가 실행" }));
    expect(await screen.findByText(text)).toBeTruthy();
  });

  it("저장 실패(500)는 실패 문구 · 기존 결과는 그대로", async () => {
    runRetrospective.mockRejectedValue(
      new ApiRequestError("요청 실패", 500, {
        detail: "연구 산출물 저장 실패: OSError — 결과를 보이지 않습니다.",
      })
    );
    render(<AlertRecordsView />);
    await screen.findByTestId("retro-ml");
    fireEvent.click(screen.getByRole("button", { name: "사후평가 실행" }));
    expect(
      await screen.findByText(
        "사후평가 실행 — 실패 — 연구 산출물 저장 실패: OSError — 결과를 보이지 않습니다."
      )
    ).toBeTruthy();
    expect(screen.getByTestId("retro-ml")).toBeTruthy();
  });
});

describe("POC5-08 사후평가 — 알림 상세", () => {
  it("항목 · 계열마다 한 줄 · +5 실제 / 과거 검증 추정 / 단순 기준 / 절대오차 / 사유 · 내 평가와 따로", async () => {
    render(<AlertRecordsView />);
    fireEvent.click(await screen.findByRole("button", { name: "자세히 보기" }));
    expect(await screen.findByText("사후평가 — 가격 결과 · 과거 검증(+5)")).toBeTruthy();
    await waitFor(() => expect(fetchRetrospectiveLatest).toHaveBeenCalledWith("E1"));
    await screen.findAllByText("반도체 사업군 · KODEX 반도체");
    const row9 = (name: string) =>
      screen
        .getAllByText(name, { selector: "td" })
        .map((td) => td.closest("tr") as HTMLElement)
        .find((tr) => tr.querySelectorAll("td").length === 9) as HTMLElement;
    const semi = row9("반도체 사업군 · KODEX 반도체");
    expect(Array.from(semi.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "반도체 사업군 · KODEX 반도체",
      "+0.85%",
      "기준가격 대비 +5 종가 하락",
      "미도래 (12-29)",
      "-3.00%",
      "-1.00%",
      "-0.50%",
      "2.00%p",
      "—",
    ]);
    // 「당시 판단 근거」 표에도 같은 이름이 있다 — 사후평가 표(9칸) 줄을 고른다.
    const sam = row9("삼성전자");
    expect(Array.from(sam.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "삼성전자",
      "도래 후 미기록",
      "미도래 (12-07)",
      "미도래 (12-29)",
      "—",
      "—",
      "—",
      "—",
      "+5 미성숙",
    ]);
    expect(screen.queryByText(/알림 전체 점수|종합 점수/)).toBeNull();
    expect(screen.getByText("내 평가 (선택)")).toBeTruthy(); // 평가 없는 알림도 같은 표
    expect(runRetrospective).not.toHaveBeenCalled(); // 상세 열기 = GET 만
    // 가격 결과 세부 — 기록된 결과 행만(미기록 슬롯 없음) · 계산 시각은 KST
    const facts = screen.getByText("가격 결과 세부").closest("details") as HTMLElement;
    const lines = Array.from(facts.querySelectorAll("tbody tr")).map((tr) =>
      Array.from(tr.querySelectorAll("td")).map((td) => td.textContent)
    );
    expect(lines).toEqual([
      ["반도체 사업군 · KODEX 반도체", "+1", "성숙", "2026-12-01", "100", "100.85", "+0.85%", "+0.90%", "-0.20%", "1", "KRX_ETF_UNADJUSTED", "12-02 08:10"],
      ["반도체 사업군 · KODEX 반도체", "+5", "성숙", "2026-12-07", "100", "97", "-3.00%", "+0.50%", "-3.40%", "5", "KRX_ETF_UNADJUSTED", "12-08 08:10"],
    ]);
  });

  it("최신 결과에 이 알림이 없으면 안내 · 입력이 바뀌었으면 기존 결과라고 표시", async () => {
    fetchRetrospectiveLatest.mockImplementation((eventId?: string) =>
      Promise.resolve(
        eventId
          ? result({ input_changed: true, event: { event_id: eventId, items: [], feedback: null } })
          : result()
      )
    );
    render(<AlertRecordsView />);
    fireEvent.click(await screen.findByRole("button", { name: "자세히 보기" }));
    expect(
      await screen.findByText("이 알림은 최근 사후평가(신호 기간 끝 2026-10-08) 대상에 없습니다")
    ).toBeTruthy();
    expect(screen.getByText("입력이 변경됨 · 재실행 필요 — 아래는 기존 결과입니다")).toBeTruthy();
  });
});

describe("POC5-08 사후평가 — 표기 도우미", () => {
  it("계열 결과가 없는 기초지수 그룹은 계열 수만큼 줄 · 결과가 일부만 있으면 남은 칸은 미기록 계열", () => {
    const pend = (h: number) => slot({ horizon: h, ml: h === 5 ? { status: "NONE", reason: "OUT_OF_SCOPE", reason_text: "이번 ML 범위 밖", block: null } : null });
    const group: RetroItem = {
      ...ITEMS[1],
      item_seq: 7,
      subject_kind: "index_group",
      subject_id: "KODEX|반도체",
      slots: [pend(1), pend(1), pend(5), pend(5), pend(20), pend(20)],
    };
    expect(buildRetroRows([group], [], []).map((r) => r.label)).toEqual([
      "KODEX|반도체 · 계열 1",
      "KODEX|반도체 · 계열 2",
    ]);
    const half: RetroItem = {
      ...group,
      slots: [slot({ series_id: "krx_etf:1", horizon: 1, status: "MATURED", return_raw: 0.01 }), pend(1), pend(5), pend(5), pend(20), pend(20)],
    };
    const rows = buildRetroRows([half], [], [{ ...DETAIL.outcomes[0], series_id: "krx_etf:1", series_name: "ETF 하나" }]);
    expect(rows.map((r) => r.label)).toEqual(["KODEX|반도체 · ETF 하나", "KODEX|반도체 · 결과 미기록 계열"]);
    expect(rows.every((r) => r.cells.every((c) => c !== null))).toBe(true);
  });

  it("가격 칸 문구 — 결측은 0% 로 바꾸지 않고 · 일부 경로 표시 · 미도래는 예정 평가일", () => {
    expect(priceCell(slot({ status: "PRICE_MISSING", status_text: "가격 자료 없음", partial_path: true }))).toBe(
      "가격 자료 없음 · 일부 종가 경로"
    );
    expect(priceCell(slot({ status: "MATURED", horizon: 20, return_raw: -0.0123 }))).toBe("-1.23%");
    expect(priceCell(slot({ expected_eval_date: null }))).toBe("미도래");
    expect(priceCell(null)).toBe("—");
  });
});
