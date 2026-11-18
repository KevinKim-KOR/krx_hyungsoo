// POC6-32 V2(PLAN §4-4 · AC3) — 주간 기록 상세 '당시 검토' = 저장한 값만(시장 자료 다시 계산 · 지금 자료 조회 없음).
// 저장 칸 모양은 서버 조립(app/weekly_candidate_review.data_quality_snapshot · constituent_snapshot ·
// app/weekly_review.candidate_snapshot · overlap_of)과 같게 만든 가상 기록이다(이름 가상 · 금액 없음).
// 요청은 기록 하나의 AI 답 해석(`GET /weekly/etf-check/records/{id}/review`) 하나뿐 — 응답은 서버 해석기 출력 그대로인
// 화면 고정 자료(lib/weeklyReviewTestFixtures.json saved.last_record · 합성 답 3개)를 쓴다(진짜 request · 가짜 fetch).
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import WeeklyReviewSnapshot from "./WeeklyReviewSnapshot";
import { WEEKLY_REVIEW_SOURCE, type WeeklyLastRecord } from "@/lib/api/weeklyReview";
import type { DecisionSessionDetail } from "@/lib/api/decisionSessions";
import { WEEKLY_SAVED } from "@/lib/weeklyReviewTestFixtures";

const FILTERS = { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true };

function same(
  status: "ok" | "unavailable",
  start: string,
  end: string,
  etf: number | null,
  kodex: number | null,
  diff: number | null,
  reason: string | null = null,
) {
  return {
    status,
    reason,
    start_date: start,
    end_date: end,
    candidate_return_pct: etf,
    kodex200_return_pct: kodex,
    diff_pctp: diff,
  };
}

function record(over: Partial<DecisionSessionDetail> = {}): DecisionSessionDetail {
  return {
    id: "decision_w",
    created_at: "2026-11-17T21:05:00.000000+0900",
    updated_at: "2026-11-17T21:05:00.000000+0900",
    asof: "2026-11-16",
    source_screen: WEEKLY_REVIEW_SOURCE,
    filters: FILTERS,
    candidate_snapshot: [
      {
        rank: 1,
        ticker: "900001",
        name: "가상 ETF 하나",
        daily_return_pct: null,
        one_month_return_pct: 12.5,
        three_month_return_pct: 3.1,
        tags: [],
        same_period_kodex200: {
          one_month: same("ok", "2026-10-19", "2026-11-16", 12.5, -11.0265, 23.5265),
          three_month: same("ok", "2026-08-18", "2026-11-16", 3.1, -26.2888, 29.3888),
        },
      },
      {
        rank: 2,
        ticker: "900002",
        name: "가상 ETF 둘",
        daily_return_pct: null,
        one_month_return_pct: 11.7735,
        three_month_return_pct: null, // 기간 다름 — 값은 데이터 품질 칸에
        tags: [],
        same_period_kodex200: {
          one_month: same("ok", "2026-10-19", "2026-11-16", 11.7735, -11.0265, 22.8),
          three_month: same("unavailable", "2026-08-25", "2026-11-16", null, null, null, "candidate_period_unknown"),
        },
      },
      {
        rank: 3,
        ticker: "900003",
        name: "가상 ETF 셋",
        daily_return_pct: null,
        one_month_return_pct: 9.4,
        three_month_return_pct: null,
        tags: [],
        same_period_kodex200: {
          one_month: same("unavailable", "2026-10-19", "2026-11-16", 9.4, null, null, "kodex200_end_price_missing"),
          three_month: same("unavailable", "2026-08-18", "2026-11-16", null, null, null, "candidate_period_unknown"),
        },
      },
    ],
    question_text: "질문 원문",
    gpt_answer_text: "최신 확인: 같음\n[ETF 900002]\n상태: 추가 확인",
    gemini_answer_text: "",
    claude_answer_text: "최신 확인: 새 값 있음\n- 항목: 코스피 종가 · 확인 시각:",
    user_memo: "",
    user_verdict: "unrecorded",
    next_checks: [],
    linked_market_refresh_id: null,
    market_context_snapshot: { source: WEEKLY_REVIEW_SOURCE },
    constituent_snapshot: {
      selected: { ticker: "900002", name: "가상 ETF 둘", rank: 2, side: "top" },
      product: {
        ticker: "900002",
        found: true,
        kind: "etf",
        name: "가상 ETF 둘",
        index_name: "가상 지수(PR)",
        index_provider: "가상 산출기관",
        market: "해외",
        asset: "주식",
        multiple: "일반",
        replication: "실물(패시브)",
        fee_pct: "0.450000",
        tax: "배당소득세(보유기간과세)",
        listed: "2024/02/14",
        missing_reason: null,
        csv: { name: "krx_etf_basic_20260927.csv", asof: "2026-09-27", ok: true, error: null },
      },
      constituents: {
        state: "top_rows",
        state_label: "상위 4행만 확인",
        asof: "2026-11-13",
        stored_rows: 4,
        stocks_known: true,
        stock_rows: 3,
        other_rows: [{ label: "원화현금", count: 1 }],
        top_n: 4,
        top_stocks: [
          { name: "가상 종목 갑", weight_pct: 29.98 },
          { name: "가상 종목 을", weight_pct: 20.92 },
          { name: "가상 종목 병", weight_pct: 6.37 },
        ],
        top3_sum_pct: 57.27,
        line: "구성 기준일 11/13 · 저장 4행(주식 3 · 원화현금 1) · 상위 4행만 확인(그 밖 구성은 미확인)",
      },
    },
    overlap_snapshot: {
      ticker: "900002",
      name: "가상 ETF 둘",
      rank: 2,
      state: "ok",
      warn_lines: ["보유 평가액의 52.00%(보유 ETF 2개)에 해당하는 ETF 는 저장된 상위 행 밖 구성이 미확인 — '겹침 없음'이 아닙니다"],
      lines: ["확보된 행으로 계산한 주요 주식별 보유 노출 범위 0.00% ~ 7.03%(주식 3개)"],
      date_line: "기준일: 고른 ETF 구성 11/13 · 노출 합계 11/13 · 보유 평가 11/13(부분 평가액) · 금액 없음",
      numbers: null,
    },
    short_term_momentum_snapshot: {},
    data_quality_snapshot: {
      condition: {
        basis: "one_month",
        side: "top",
        n: 3,
        filters: FILTERS,
        start: "2026-10-19",
        end: "2026-11-16",
        line: "1개월 상위 3개(선정 순서) · 10/19 → 11/16 · 인버스 · 레버리지 · 합성 · 선물 제외 · 11/16 가격 = 마감 뒤 저장",
      },
      selected: { ticker: "900002", name: "가상 ETF 둘", rank: 2, side: "top" },
      common_periods: {
        one_month: { start: "2026-10-19", end: "2026-11-16" },
        three_month: { start: "2026-08-18", end: "2026-11-16" },
      },
      period_differs_values: [
        { ticker: "900002", rank: 2, period: "3m", value_pct: 4.2, start: "2026-08-25", end: "2026-11-16" },
      ],
      lack: [
        { ticker: "900002", rank: 2, lack: ["3개월 기간 다름"] },
        { ticker: "900003", rank: 3, lack: ["3개월 수익률 없음"] },
      ],
      evidence_list: [
        { no: 1, group: "market", text: "시장 판정 하락 추세(가상)", tickers: [] },
        { no: 2, group: "etf", text: "가상 ETF 둘 1개월 +11.77%", tickers: ["900002"] },
      ],
    },
    ml_baseline_evidence_snapshot: {},
    ...over,
  };
}

const PARSED: WeeklyLastRecord = WEEKLY_SAVED.last_record;
let reply: { status: number; body: unknown } | "network" = { status: 200, body: PARSED };
// 경로별로 응답을 붙잡아 두기(늦게 온 앞 기록 응답 시험)
let hold: Record<string, (() => void)[]> = {};
const fetchSpy = vi.fn(async (url: string) => {
  const path = url.replace("http://api.test", "");
  const now = reply; // 요청한 때의 응답(붙잡아 둔 응답은 늦게 와도 그때 응답)
  if (hold[path]) await new Promise<void>((r) => hold[path].push(r));
  if (now === "network") throw new TypeError("Failed to fetch");
  const { status, body } = now;
  return { ok: status === 200, status, text: async () => JSON.stringify(body) };
});
beforeEach(() => {
  fetchSpy.mockClear();
  reply = { status: 200, body: PARSED };
  hold = {};
  vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://api.test");
  vi.stubGlobal("fetch", fetchSpy);
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
const REVIEW_PATH = "/weekly/etf-check/records/decision_w/review";
const calledPaths = () => fetchSpy.mock.calls.map((c) => String(c[0]).replace("http://api.test", ""));

describe("'당시 검토' — 저장 값만", () => {
  it("머리 = 저장 시각 · 원자료 기준일(따로) · 고른 후보 · 사용자 판단 · AI 답 수 · 조건 · 공통 기간", () => {
    render(<WeeklyReviewSnapshot detail={record()} />);
    expect(screen.getByTestId("wrs-head")).toHaveTextContent(
      "저장 2026-11-17 21:05 · 원자료 기준일 2026-11-16 · 고른 후보 가상 ETF 둘(900002) · 사용자 판단 미기록 · AI 답 2개",
    );
    expect(screen.getByTestId("wrs-cond")).toHaveTextContent(
      "1개월 상위 3개(선정 순서) · 10/19 → 11/16 · 인버스 · 레버리지 · 합성 · 선물 제외 · 11/16 가격 = 마감 뒤 저장",
    );
    expect(screen.getByTestId("wrs-cond")).toHaveTextContent("공통 기간 1개월 10/19 → 11/16 · 3개월 8/18 → 11/16");
    // 요청 = 기록 하나의 AI 답 해석 하나(시장 · 목록 · 노출 조회 없음)
    expect(calledPaths()).toEqual([REVIEW_PATH]);
  });

  it("후보 표 — 1 · 3개월 · 같은 기간 KODEX 200 실제 기간 · 기간 다름(값 + 실제 기간 · 대비 안 함) · 자료 부족 · 고른 후보", () => {
    render(<WeeklyReviewSnapshot detail={record()} />);
    const box = screen.getByTestId("wrs-candidates") as HTMLDetailsElement;
    expect(box.open).toBe(true);
    const row = (t: string) => box.querySelector(`tr[data-ticker="${t}"]`) as HTMLElement;
    const cells = (t: string) => Array.from(row(t).querySelectorAll("td")).map((td) => td.textContent);
    expect(cells("900001")).toEqual([
      "1",
      "가상 ETF 하나 900001",
      "+12.50%10/19 → 11/16",
      "-11.03% · 차 +23.53%p",
      "+3.10%8/18 → 11/16",
      "-26.29% · 차 +29.39%p",
    ]);
    expect(cells("900002")).toEqual([
      "2",
      "가상 ETF 둘 900002✓ 고른 후보자료 부족: 3개월 기간 다름",
      "+11.77%10/19 → 11/16",
      "-11.03% · 차 +22.80%p",
      "+4.20%8/25 → 11/16 · 기간 다름(공통 8/18 → 11/16)",
      "기간 다름 · 국내시장 대비 안 함",
    ]);
    expect(row("900002").className).toContain("wrs-picked");
    expect(cells("900003")).toEqual([
      "3",
      "가상 ETF 셋 900003자료 부족: 3개월 수익률 없음",
      "+9.40%10/19 → 11/16",
      "KODEX 200 끝 가격 없음",
      "확인 불가8/18 → 11/16",
      "값 없음",
    ]);
    expect(row("900001").className).not.toContain("wrs-picked");
  });

  it("고른 후보 — 공식 기준정보(파일 날짜) · 구성 요약 · 1 · 3개월(기간 다름은 대비 안 함)", () => {
    render(<WeeklyReviewSnapshot detail={record()} />);
    const s = screen.getByTestId("wrs-selected");
    expect(s).toHaveTextContent("가상 ETF 둘(900002) · 1개월 상위 2위");
    expect(s).toHaveTextContent(
      "공식 기초지수 가상 지수(PR) · 지수산출기관 가상 산출기관 · 투자 대상 해외 · 주식",
    );
    expect(s).toHaveTextContent("상품 구조 일반 · 실물(패시브) · 총보수 0.45% (KRX 공식 기준정보 2026-09-27 파일)");
    expect(s).toHaveTextContent(
      "주요 편입(주식) 가상 종목 갑 29.98% · 가상 종목 을 20.92% · 가상 종목 병 6.37% → 상위 3개 합 57.27%",
    );
    expect(s).toHaveTextContent("구성 기준일 11/13 · 저장 4행(주식 3 · 원화현금 1) · 상위 4행만 확인(그 밖 구성은 미확인)");
    expect(s).toHaveTextContent("1개월 +11.77%(10/19 → 11/16) · 같은 기간 국내시장(KODEX 200) -11.03% · 차 +22.80%p");
    expect(s).toHaveTextContent(
      "3개월 +4.20%(8/25 → 11/16 · 기간 다름) · 같은 기간 국내시장(KODEX 200) 기간 다름 · 국내시장 대비 안 함",
    );
  });

  it("겹침 · 확인 범위 · 인용 근거(저장한 근거 목록) · AI 별 원문(접힘) · 사용자 판단", () => {
    render(<WeeklyReviewSnapshot detail={record()} />);
    const ov = screen.getByTestId("wrs-overlap");
    expect(ov).toHaveTextContent("저장된 상위 행 밖 구성이 미확인 — '겹침 없음'이 아닙니다");
    expect(ov).toHaveTextContent("확보된 행으로 계산한 주요 주식별 보유 노출 범위 0.00% ~ 7.03%(주식 3개)");
    expect(ov).toHaveTextContent("기준일: 고른 ETF 구성 11/13 · 노출 합계 11/13");
    expect(ov).toHaveTextContent("후보끼리 중복률과 다른 값");
    const ev = screen.getByTestId("wrs-evidence");
    expect(ev).toHaveTextContent("[근거 1] 시장 판정 하락 추세(가상)");
    expect(ev).toHaveTextContent("[근거 2] 가상 ETF 둘 1개월 +11.77%");
    const ai = screen.getByTestId("wrs-ai");
    const folds = Array.from(ai.querySelectorAll("details.wrs-fold")) as HTMLDetailsElement[];
    expect(folds.map((d) => d.getAttribute("data-ai"))).toEqual(["GPT", "Claude"]);
    expect(folds.every((d) => !d.open)).toBe(true);
    expect(within(folds[0]).getByText("GPT 답 원문")).toBeTruthy();
    expect(folds[0].querySelector("pre")!.textContent).toBe(record().gpt_answer_text);
    expect(folds[1].querySelector("pre")!.textContent).toBe(record().claude_answer_text);
    expect(ai).toHaveTextContent("답 없음: Gemini");
    expect(ai).toHaveTextContent("AI 가 답에 적은 확인 시각 · 출처는 위 저장 시각과 다른 값");
    const v = screen.getByTestId("wrs-verdict");
    expect(v).toHaveTextContent("미기록");
    expect(v).toHaveTextContent("메모 비어 있음");
    expect(v).toHaveTextContent("다음 확인 비어 있음");
  });

  it("직접 고른 보류 · 메모 · 다음 확인 · 답 하나 = '한 의견'", () => {
    render(
      <WeeklyReviewSnapshot
        detail={record({ user_verdict: "hold", user_memo: "다음 주 다시", next_checks: ["구성 더 받기", "3개월 대비"], claude_answer_text: "" })}
      />,
    );
    expect(screen.getByTestId("wrs-head")).toHaveTextContent("사용자 판단 보류(직접 고름) · AI 답 1개(한 의견)");
    const v = screen.getByTestId("wrs-verdict");
    expect(v).toHaveTextContent("보류(직접 고름)");
    expect(v).toHaveTextContent("메모 다음 주 다시");
    expect(v).toHaveTextContent("다음 확인 구성 더 받기 · 3개월 대비");
  });

  it("기간 다름 기록이 있으면 저장 비교 칸이 ok 여도 국내시장 대비를 쓰지 않는다(칸끼리 어긋난 기록)", () => {
    const base = record();
    const dq = {
      ...base.data_quality_snapshot,
      period_differs_values: [
        { ticker: "900001", rank: 1, period: "1m", value_pct: 12.5, start: "2026-10-21", end: "2026-11-16" },
      ],
    };
    render(<WeeklyReviewSnapshot detail={record({ data_quality_snapshot: dq })} />);
    const row = screen.getByTestId("wrs-candidates").querySelector('tr[data-ticker="900001"]') as HTMLElement;
    const cells = Array.from(row.querySelectorAll("td")).map((td) => td.textContent);
    expect(cells[2]).toBe("+12.50%10/21 → 11/16 · 기간 다름(공통 10/19 → 11/16)");
    expect(cells[3]).toBe("기간 다름 · 국내시장 대비 안 함");
  });

  it("영어 코드 · 식별자가 화면 글자에 없다", () => {
    const { container } = render(<WeeklyReviewSnapshot detail={record()} />);
    const t = container.textContent ?? "";
    for (const code of [
      "candidate_period_unknown",
      "kodex200_end_price_missing",
      "today_weekly_review",
      "unrecorded",
      "top_rows",
      "period_differs",
      "null",
      "undefined",
    ]) {
      expect(t).not.toContain(code);
    }
  });
});

// 검토 F2 · F5 · PLAN I-8 · I-32 — 같은 기간 국내시장(KODEX 200) 대비는 화면 ③ 과 같은 규칙: 고른 후보 = 저장한 R2 결과
// 그대로 · 30행 = 저장 비교 칸 + 저장한 끝 가격(날짜 · 상태)로 I-8 · 그 칸이 없는 기록 = '가격 상태 대조 기록 없음'.
const RETURNS = [
  {
    period: "1m",
    value_pct: 11.7735,
    start: "2026-10-19",
    end: "2026-11-16",
    status: "ok",
    direction: "up",
    phrase: "올랐고 국내시장보다 22.80%p 높음 · 잠정 비교",
    market: { value_pct: -11.0265, diff_pp: 22.8, comparable: true, provisional: true, reason: null },
  },
  {
    period: "3m",
    value_pct: 4.2,
    start: "2026-08-25",
    end: "2026-11-16",
    status: "period_differs",
    direction: "up",
    phrase: "올랐음 · 기간 다름 · 국내시장 대비 안 함",
    market: { value_pct: null, diff_pp: null, comparable: false, provisional: false, reason: "기간 다름" },
  },
];

function withStates(rows: Record<string, string>, kodex: { date: string; state: string }, returns: unknown[] = RETURNS) {
  const dq = record().data_quality_snapshot as Record<string, unknown>;
  const price = (st: string) => ({ date: "2026-11-16", state: st });
  return record({
    data_quality_snapshot: {
      ...dq,
      selected: { ...(dq.selected as Record<string, unknown>), returns },
      price_states: { rows: Object.fromEntries(Object.entries(rows).map(([t, st]) => [t, price(st)])), kodex200: kodex },
    },
  });
}
const kodexCells = (t: string) => {
  const row = screen.getByTestId("wrs-candidates").querySelector(`tr[data-ticker="${t}"]`) as HTMLElement;
  const td = Array.from(row.querySelectorAll("td")).map((x) => x.textContent);
  return [td[3], td[5]];
};

describe("'당시 검토' — 국내시장 대비 = 저장한 가격 상태로 I-8 · 고른 후보 = 저장 R2(검토 F2 · F5 · PLAN I-32)", () => {
  it("둘 다 장중 = 잠정 · 상태 다름 · 모름 = 대비 안 함 · 저장 비교가 원래 없으면 그 사유 · 고른 후보 = 저장 R2 문구 그대로", () => {
    const intra = { date: "2026-11-16", state: "intraday" };
    render(<WeeklyReviewSnapshot detail={withStates({ "900001": "after_close", "900002": "intraday", "900003": "unknown" }, intra)} />);
    expect(kodexCells("900001")).toEqual(["대비 안 함(가격 상태 다름/모름)", "대비 안 함(가격 상태 다름/모름)"]);
    expect(kodexCells("900002")).toEqual(["-11.03% · 차 +22.80%p · 잠정", "기간 다름 · 국내시장 대비 안 함"]);
    expect(kodexCells("900003")).toEqual(["KODEX 200 끝 가격 없음", "값 없음"]);
    expect(screen.getByTestId("wrs").textContent).not.toContain("가격 상태 대조 기록 없음");
    const lines = screen.getAllByTestId("wrs-selected-return").map((x) => x.textContent);
    expect(lines).toEqual([
      "1개월 +11.77%(10/19 → 11/16) · 같은 기간 국내시장(KODEX 200) -11.03% · 올랐고 국내시장보다 22.80%p 높음 · 잠정 비교",
      "3개월 +4.20%(8/25 → 11/16 · 기간 다름) · 같은 기간 국내시장(KODEX 200) 올랐음 · 기간 다름 · 국내시장 대비 안 함",
    ]);
  });

  it.each<[string, Record<string, string>, { date: string; state: string }, [string, string]]>([
    ["둘 다 마감 뒤 = 대비(잠정 아님)", { "900001": "after_close" }, { date: "2026-11-16", state: "after_close" }, ["-11.03% · 차 +23.53%p", "-26.29% · 차 +29.39%p"]],
    ["KODEX 200 상태 모름", { "900001": "after_close" }, { date: "2026-11-16", state: "unknown" }, ["대비 안 함(가격 상태 다름/모름)", "대비 안 함(가격 상태 다름/모름)"]],
    ["끝일이 기간 끝과 다름", { "900001": "after_close" }, { date: "2026-11-13", state: "after_close" }, ["대비 안 함(가격 상태 다름/모름)", "대비 안 함(가격 상태 다름/모름)"]],
    ["그 행의 가격 상태 기록 없음", {}, { date: "2026-11-16", state: "after_close" }, ["대비 안 함(가격 상태 다름/모름)", "대비 안 함(가격 상태 다름/모름)"]],
  ])("30행 I-8 — %s", (_t, rows, kodex, want) => {
    render(<WeeklyReviewSnapshot detail={withStates(rows, kodex)} />);
    expect(kodexCells("900001")).toEqual(want);
  });

  it("저장 R2 가 국내시장 대비를 안 했으면 그 사유 문구 그대로(값을 만들지 않음)", () => {
    const why = "올랐음 · 국내시장 대비 안 함(가격 상태 다름(이 ETF 마감 뒤 저장 · KODEX 200 장중 저장값 · 잠정))";
    const one = { ...RETURNS[0], phrase: why, market: { ...RETURNS[0].market, comparable: false, provisional: false, reason: "가격 상태 다름" } };
    render(<WeeklyReviewSnapshot detail={withStates({}, { date: "2026-11-16", state: "intraday" }, [one])} />);
    expect(screen.getAllByTestId("wrs-selected-return").map((x) => x.textContent)).toEqual([
      `1개월 +11.77%(10/19 → 11/16) · 같은 기간 국내시장(KODEX 200) ${why}`,
    ]);
  });

  it("가격 상태 · R2 를 저장하지 않은 기록 = KODEX 200 칸 머리 · 고른 후보 줄에 '가격 상태 대조 기록 없음'(지금 값으로 채우지 않음)", () => {
    render(<WeeklyReviewSnapshot detail={record()} />);
    const heads = Array.from(screen.getByTestId("wrs-candidates").querySelectorAll("th")).map((x) => x.textContent);
    expect(heads.filter((h) => h === "같은 기간 KODEX 200가격 상태 대조 기록 없음")).toHaveLength(2);
    expect(screen.queryAllByTestId("wrs-selected-return")).toHaveLength(0);
    const sel = screen.getByTestId("wrs-selected").textContent ?? "";
    expect(sel).toContain("1개월 +11.77%(10/19 → 11/16) · 같은 기간 국내시장(KODEX 200) -11.03% · 차 +22.80%p · 가격 상태 대조 기록 없음");
    expect(sel).toContain("3개월 +4.20%(8/25 → 11/16 · 기간 다름) · 같은 기간 국내시장(KODEX 200) 기간 다름 · 국내시장 대비 안 함 · 가격 상태 대조 기록 없음");
  });
});

describe("'당시 검토' — AI 추가 확인을 칸으로 복원(AC3 · 저장 원문을 나눈 결과 · PLAN I-14)", () => {
  it("AI 별 최신 확인 · 확인 항목 줄(확인 시각 미기재) · 후보마다 상태 · 인용 근거 · 이유 · 다음 확인 · AI 끼리 대조 · 원문은 접힘", async () => {
    render(<WeeklyReviewSnapshot detail={record()} />);
    const ai = screen.getByTestId("wrs-ai");
    expect(screen.getByTestId("wrs-ai-note")).toHaveTextContent(
      "저장한 질문 · 답 원문을 다시 읽어 나눈 결과입니다(시장 자료 다시 계산 없음 · 해석 규칙이 바뀌면 나눈 모양도 바뀔 수 있음 · 원문은 아래 접힌 칸)",
    );
    const latest = await within(ai).findByTestId("wr-ai-latest");
    expect(latest).toHaveTextContent("최신 확인: GPT 같음 · Gemini 확인 불가 · Claude 새 값 있음 · AI 답 3개");
    const items = within(ai).getAllByTestId("wr-ai-item");
    expect(items[0]).toHaveTextContent("Claude — 항목 코스피 종가 · 값 5,190.00 · 기준일 2026-11-16 · 출처 https://data.krx.co.kr · 확인 시각 확인 시각 미기재");
    const row = (t: string) => ai.querySelector(`tr[data-ticker="${t}"]`) as HTMLElement;
    expect(row("476070")).toHaveTextContent("추가 확인 · 근거 27, 33이유: 상위 행 밖 보유 구성 미확인 · 다음 확인: 보유 ETF 구성 더 받기");
    expect(row("476070")).toHaveTextContent("상태 같음(추가 확인)같은 번호 27 · 다른 번호 GPT 33 / Gemini 33, 34 / Claude 2");
    expect(row("453810")).toHaveTextContent("한 의견");
    // 원문은 나눈 결과 아래 접힌 칸 그대로
    const folds = Array.from(ai.querySelectorAll("details.wrs-fold")) as HTMLDetailsElement[];
    expect(folds.map((d) => d.getAttribute("data-ai"))).toEqual(["GPT", "Claude"]);
    expect(folds.every((d) => !d.open)).toBe(true);
    expect(latest.compareDocumentPosition(folds[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(calledPaths()).toEqual([REVIEW_PATH]);
  });

  it("질문 형식을 못 읽으면 대조 표 대신 서버 안내 · 답마다 최신 확인은 그대로", async () => {
    const cmp = structuredClone(PARSED.compare!);
    cmp.status = "no_format";
    cmp.message = "질문 원문에서 근거 번호 · 대상 ETF 를 찾지 못했습니다 — 요약 확인 필요(원문은 「AI 투자 세션」)";
    cmp.rows = [];
    reply = { status: 200, body: { ...PARSED, compare: cmp } };
    render(<WeeklyReviewSnapshot detail={record()} />);
    const parsed = screen.getByTestId("wrs-ai-parsed");
    await waitFor(() => expect(parsed).toHaveTextContent("질문 원문에서 근거 번호 · 대상 ETF 를 찾지 못했습니다"));
    expect(parsed).toHaveTextContent("최신 확인: GPT 같음");
    expect(parsed.querySelector("table")).toBeNull();
  });

  it.each([
    [{ status: 404, body: { detail: "「주간 ETF 점검」에서 저장한 기록이 아닙니다." } }, "「주간 ETF 점검」에서 저장한 기록이 아닙니다."],
    [{ status: 503, body: { detail: "기록을 읽지 못했습니다 — 잠시 뒤 다시 열어 주세요." } }, "기록을 읽지 못했습니다 — 잠시 뒤 다시 열어 주세요."],
    [{ status: 500, body: "Internal Server Error" }, "서버에 연결하지 못했습니다"],
    ["network" as const, "서버에 연결하지 못했습니다"],
  ])("못 읽으면 쉬운 한국어 사유 · 원문은 그대로(%#)", async (r, why) => {
    reply = r;
    render(<WeeklyReviewSnapshot detail={record()} />);
    const parsed = screen.getByTestId("wrs-ai-parsed");
    await waitFor(() => expect(parsed).toHaveTextContent(`저장한 답을 나누어 읽지 못했습니다 — ${why} · 아래 원문 참고`));
    for (const code of ["HTTP", "GET", "/weekly", "Failed to fetch", "Internal Server Error"]) expect(parsed.textContent).not.toContain(code);
    expect(screen.getByTestId("wrs-ai").querySelectorAll("details.wrs-fold")).toHaveLength(2);
  });

  it("읽는 중 표시 · 다른 기록으로 바뀌면 늦게 온 앞 기록 응답은 버린다", async () => {
    hold[REVIEW_PATH] = [];
    const { rerender } = render(<WeeklyReviewSnapshot detail={record()} />);
    expect(screen.getByTestId("wrs-ai-parsed")).toHaveTextContent("저장한 답을 나누어 읽는 중입니다");
    const other = { ...PARSED, compare: { ...PARSED.compare!, opinion_text: "다른 기록" } };
    reply = { status: 200, body: other };
    rerender(<WeeklyReviewSnapshot detail={record({ id: "decision_v" })} />);
    await waitFor(() => expect(screen.getByTestId("wr-ai-latest")).toHaveTextContent("다른 기록"));
    for (const release of hold[REVIEW_PATH]) release(); // 앞 기록 응답(AI 답 3개)이 늦게 도착
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.getByTestId("wr-ai-latest")).toHaveTextContent("다른 기록");
    expect(screen.getByTestId("wr-ai-latest")).not.toHaveTextContent("AI 답 3개");
    expect(calledPaths()).toEqual([REVIEW_PATH, "/weekly/etf-check/records/decision_v/review"]);
  });
});

describe("'당시 검토' — 칸이 없거나 모양이 다르면 그 칸만 '당시 기록에 없음'(지금 값으로 채우지 않음)", () => {
  it("저장 칸이 빈 기록(조건 · 고른 후보 · 겹침 · 근거 목록 없음)", () => {
    render(
      <WeeklyReviewSnapshot
        detail={record({ data_quality_snapshot: {}, constituent_snapshot: {}, overlap_snapshot: {}, gpt_answer_text: "", claude_answer_text: "", gemini_answer_text: "g" })}
      />,
    );
    expect(screen.getByTestId("wrs-head")).toHaveTextContent("고른 후보 없음 · 사용자 판단 미기록 · AI 답 1개(한 의견)");
    expect(screen.getByTestId("wrs-cond")).toHaveTextContent("당시 기록에 없음 — 아래 질문 원문 첫 줄 참고");
    expect(screen.getByTestId("wrs-selected")).toHaveTextContent("고른 후보 없음(목록만 넘긴 기록)");
    expect(screen.getByTestId("wrs-overlap")).toHaveTextContent("당시 기록에 없음(겹침을 저장하지 않은 기록)");
    expect(screen.getByTestId("wrs-evidence")).toHaveTextContent("당시 기록에 없음 — 아래 질문 원문 참고");
    // 기간 다름 칸이 없으면 3개월 값 없음 행은 '값 없음' · 기간 다름으로 꾸미지 않음
    const row2 = screen.getByTestId("wrs-candidates").querySelector('tr[data-ticker="900002"]') as HTMLElement;
    expect(row2.textContent).not.toContain("기간 다름");
    expect(row2.textContent).toContain("값 없음");
  });

  it("빈 근거 목록 · 공식 기준정보 없음 · 개별 주식 · 구성 칸 없음", () => {
    const base = record();
    const dq = { ...base.data_quality_snapshot, evidence_list: [] };
    const missing = {
      ...base.constituent_snapshot,
      product: { ticker: "900002", found: false, kind: "unknown", missing_reason: "공식 기준정보에 없음", csv: { asof: "2026-09-27" } },
      constituents: undefined,
    };
    const { unmount } = render(<WeeklyReviewSnapshot detail={record({ data_quality_snapshot: dq, constituent_snapshot: missing })} />);
    expect(screen.getByTestId("wrs-evidence")).toHaveTextContent("저장한 근거 목록이 비어 있음 — 아래 질문 원문 참고");
    expect(screen.getByTestId("wrs-selected")).toHaveTextContent(
      "공식 기준정보에 없음 — 확인 불가 (KRX 공식 기준정보 2026-09-27 파일)",
    );
    expect(screen.getByTestId("wrs-selected")).toHaveTextContent("구성 요약 — 당시 기록에 없음");
    unmount();
    const stock = {
      ...base.constituent_snapshot,
      product: { ticker: "900002", found: false, kind: "stock", missing_reason: "개별 주식 · 기초지수 해당 없음", csv: {} },
    };
    render(<WeeklyReviewSnapshot detail={record({ constituent_snapshot: stock })} />);
    expect(screen.getByTestId("wrs-selected")).toHaveTextContent("개별 주식 · 기초지수 해당 없음");
    expect(screen.getByTestId("wrs-selected")).not.toHaveTextContent("해당 없음 — 확인 불가");
  });
});
