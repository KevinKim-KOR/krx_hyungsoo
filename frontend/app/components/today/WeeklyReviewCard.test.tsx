// POC6-32 V2 — 「주간 ETF 점검」 화면 본문(today/WeeklyReviewCard) 시험.
// 고정 응답 = 서버 조립 함수 출력 그대로(11/16 공개 시장 자료 · 합성 공통 시장 근거 · 합성 보유 · 합성 AI 답 ·
// lib/weeklyReviewTestFixtures.json). 기간 다름 · 자료 부족 · 한 의견 등 고정 자료에 없는 경우는 응답을 복사해 칸만 바꾼다.
// PLAN V2: ① ② ③ ④ ⑤ 차례 · ② 첫 3행 · 묶음 안 ETF 마다 [고르기](W7) · 고른 표시 40px(W9) · 기간 다름 값(W5) ·
// 자료 부족 알약(I-11) · ③ 고르면 그 응답으로 검토 · [비교 상세] · [구성종목 보기] 넘김 · 복사 · 넘기기 = 같은 응답 ·
// ④ 최신 확인 · 확인 항목(확인 시각 미기재) · 이유 · 다음 확인 · 대조 · ⑤ 최근 검토 기록 · ① 시장 한 줄 = 공통 시장 근거 칸.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import { describeDraftOrigin, loadAISessionsDraft, saveAISessionsDraft, clearAISessionsDraft, verdictText } from "@/lib/aiSessionsDraft";
import { WEEKLY_NONE, WEEKLY_SAVED, WEEKLY_SELECTED } from "@/lib/weeklyReviewTestFixtures";
import type { WeeklyReviewOk, WeeklyReviewResponse } from "@/lib/api/weeklyReview";
import { oneMonthText, weeklyDraft, weeklyMarketView } from "@/lib/weeklyReview";
import { takeOneTimeCondition } from "@/lib/etfCompareCondition";
import { takeExposureSingle, takeOpenRecord } from "@/lib/detailNav";
import { takePresetCandidate } from "../workbench/compareSelection";

const fetchWeeklyReview = vi.fn();
vi.mock("@/lib/api/weeklyReview", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchWeeklyReview: (...a: unknown[]) => fetchWeeklyReview(...a),
}));

import WeeklyReviewCard from "./WeeklyReviewCard";

const writeText = vi.fn();

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

async function renderCard(resp: (sel: string | null) => WeeklyReviewResponse = (s) => (s ? WEEKLY_SELECTED : WEEKLY_NONE), gen = 0) {
  fetchWeeklyReview.mockImplementation(async (sel: string | null) => resp(sel));
  const onNavigate = vi.fn();
  const view = render(<WeeklyReviewCard onNavigate={onNavigate} gen={gen} />);
  await screen.findByTestId("wr-flows");
  return { onNavigate, ...view };
}

const PICKED = "KODEX 글로벌비만치료제TOP2 Plus(476070) · 1개월 상위 2위";
const picked = () => waitFor(() => expect(screen.getByTestId("wr-review-head")).toHaveTextContent(PICKED));
// 첫 화면 표의 흐름 줄(단독 행 · 묶음 행 — 묶음 안 ETF 줄은 data-member)
const firstRows = () =>
  Array.from(screen.getByTestId("wr-flows").querySelectorAll(":scope > .wr-table-wrap tbody tr[data-flow]")) as HTMLElement[];
const pickBtn = (row: HTMLElement) => within(row).getByRole("button", { name: /고르기/ });
const pickSecond = async () => {
  fireEvent.click(pickBtn(firstRows()[1]));
  await picked();
};
const clone = (r: WeeklyReviewOk) => structuredClone(r) as WeeklyReviewOk;

beforeEach(() => {
  __resetQueryCache();
  vi.clearAllMocks();
  window.sessionStorage.clear();
  takePresetCandidate();
  takeExposureSingle();
  takeOpenRecord();
  writeText.mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
});

describe("주간 ETF 점검 — 머리 · ① 시장 · ② ETF 흐름", () => {
  it("조건 줄(3개월 공통 기간 포함) · 안쪽 제목 없음 · ① → ② → ③ → ④ → ⑤ 차례", async () => {
    await renderCard();
    expect(fetchWeeklyReview).toHaveBeenCalledWith(null);
    expect(screen.getByTestId("wr-cond")).toHaveTextContent(
      "「후보리스트」 기본 조건과 같은 1개월 상위 30개(선정 순서) · 10/19 → 11/16 · 인버스 · 레버리지 · 합성 · 선물 제외 · 11/16 가격 = 마감 뒤 저장 · 3개월 공통 기간 8/18 → 11/16 · 다른 화면 설정과 따로",
    );
    // 화면 제목은 「주간 ETF 점검」 화면 h1 하나 — 본문에 예전 제목 'ETF 주간 검토'가 없다
    expect(screen.queryByText("ETF 주간 검토")).toBeNull();
    expect(screen.queryByRole("heading")).toBeNull();
    const ids = ["wr-market", "wr-flows", "wr-review", "wr-ai", "wr-last"];
    const order = Array.from(screen.getByTestId("wr-card").querySelectorAll("[data-testid]"))
      .map((e) => e.getAttribute("data-testid"))
      .filter((t): t is string => !!t && ids.includes(t));
    expect(order).toEqual(ids);
    expect(screen.getByTestId("wr-market").textContent).toMatch(/^① 시장 한 줄/);
    expect(screen.getByTestId("wr-flows").textContent).toMatch(/^② ETF 흐름/);
    expect(screen.getByTestId("wr-review").textContent).toMatch(/^③ 선택한 후보 검토/);
    expect(screen.getByTestId("wr-ai").textContent).toMatch(/^④ AI 의견 요약/);
    expect(screen.getByTestId("wr-last").textContent).toMatch(/^⑤ 최근 검토 기록/);
  });

  it("첫 3행(1위 단독 · 2위 단독 · 3 · 4위 Nifty 50 Index 묶음 + 묶음 안 ETF 줄 2개) · 나머지는 펼침 안", async () => {
    await renderCard();
    const rows = firstRows();
    expect(rows.map((r) => r.getAttribute("data-flow"))).toEqual(["428560", "476070", "453810"]);
    expect(rows[0]).toHaveTextContent("KODEX 미국ETF산업Top10 Indxx428560 · 단독1+12.55%+9.86%");
    expect(rows[2]).toHaveTextContent("Nifty 50 Index2개 상품 · 아래 줄에서 하나를 고름3 · 4각 +10.80%+0.01% · -0.64%같은 공식 기초지수를 따르는 2개 상품");
    // 묶음 줄 자체에는 [고르기]가 없고 아래 줄의 ETF 마다 있다(W7)
    expect(within(rows[2]).queryByRole("button")).toBeNull();
    const mem = Array.from(screen.getByTestId("wr-flows").querySelectorAll(":scope > .wr-table-wrap tbody tr[data-member]")) as HTMLElement[];
    expect(mem.map((r) => r.getAttribute("data-member"))).toEqual(["453810", "453870"]);
    expect(mem[0]).toHaveTextContent("KODEX 인도Nifty50 4538103+10.80%+0.01%고르기");
    expect(mem[1]).toHaveTextContent("TIGER 인도니프티50 4538704+10.80%-0.64%고르기");
    const rest = screen.getByText(/^나머지 흐름 펼치기/);
    expect(rest).toHaveTextContent(`나머지 흐름 펼치기 · ${WEEKLY_NONE.flows.length - 3}행 · 5위부터 원래 순위`);
    const details = rest.closest("details") as HTMLElement;
    const restRows = Array.from(details.querySelectorAll("tbody tr[data-flow]")).map((r) => r.getAttribute("data-flow"));
    expect(restRows.slice(0, 2)).toEqual(["476310", "476690"]);
    // 낡은 안내(메뉴에서 빠진 「ETF 구성종목」으로 보냄)가 없다
    expect(screen.getByTestId("wr-flows")).not.toHaveTextContent("「ETF 구성종목」에서 봅니다");
    // 이름이 모두 같은 묶음(Nifty 50)은 상품마다 지수명을 붙이지 않는다
    expect(mem.every((r) => !r.querySelector('[data-testid="wk-mem-index"]'))).toBe(true);
  });

  it("검토 BE-5(PLAN I-6 · I-29) — 묶음 = 같은 기초지수 계열 · 공식 지수명이 다른 상품이 섞이면 그렇다고 쓰고 줄마다 공식 기초지수", async () => {
    await renderCard();
    const flows = screen.getByTestId("wr-flows");
    expect(flows).toHaveTextContent("같은 기초지수 계열(공식 기초지수명이 같거나 계열 사전으로 확인된 것)만 한 묶음");
    expect(flows).not.toHaveTextContent("같은 기초지수만 한 묶음");
    const dj = WEEKLY_NONE.flows.find((f) => f.rep === "483290")!;
    expect(dj.index_names_differ).toBe(true);
    const grp = flows.querySelector('tr[data-flow="483290"]') as HTMLElement;
    expect(grp).toHaveTextContent("같은 지수 계열 · 공식 기초지수명이 다른 상품 포함(지수명 4개) · 4개 상품");
    expect(grp).not.toHaveTextContent("같은 공식 기초지수");
    for (const m of dj.members) {
      const row = flows.querySelector(`tr[data-member="${m.ticker}"]`) as HTMLElement;
      expect(within(row).getByTestId("wk-mem-index")).toHaveTextContent(`공식 기초지수 ${m.index_name}`);
    }
    expect(new Set(dj.members.map((m) => m.index_name)).size).toBe(4);
  });

  it("① 시장 한 줄 = 공통 시장 근거 칸(일일 복사 · 복사 글 시장 [근거 n] 과 같은 값) · 실제 시작 → 끝 · 자료 기준일", async () => {
    await renderCard();
    const mk = screen.getByTestId("wr-market");
    expect(mk).toHaveTextContent("① 시장 한 줄 (일일 복사와 같은 공통 시장 근거)");
    const line =
      "KODEX 200 하락장 · 27거래일째(판정 가격 11/16 · 20거래일 -11.03%(10/19 → 11/16) · 60거래일 -26.29%(8/18 → 11/16) · 20 · 60일선 아래) · " +
      "외국인 최근 20거래일 순매도 6,060억원(10/19 ~ 11/13) · 직전 20거래일 순매도 6,059억원(9/21 ~ 10/16)";
    expect(mk).toHaveTextContent(line);
    expect(mk).toHaveTextContent("자료 기준일: ETF 시세 11/16 · 코스피 · 수급 11/13 · 원/달러 · WTI · VIX 미국 11/16");
    // 같은 응답의 복사 글 시장 근거 줄과 같은 값(같은 칸에서 나옴)
    const copy = WEEKLY_NONE.copy_text;
    for (const v of ["KODEX 200 하락장 · 27거래일째", "20거래일 -11.03%(10/19 → 11/16)", "60거래일 -26.29%(8/18 → 11/16)", "10/19 ~ 11/13 순매도 6,060억원", "9/21 ~ 10/16 순매도 6,059억원"]) {
      expect(copy).toContain(v);
    }
    // V1 목록 요약 판정 줄 · 영어 코드 없음
    expect(mk).not.toHaveTextContent("기존 시장 판정");
    for (const code of ["bear", "below", "after_close", "unavailable", "null"]) expect(mk.textContent).not.toContain(code);
  });

  it("① 공통 시장 근거를 못 읽으면 '공통 시장 근거 확인 불가 — 사유' · 칸 하나만 못 읽으면 그 칸만 사유(다른 칸 그대로)", async () => {
    const na = clone(WEEKLY_NONE);
    na.market_evidence = { status: "unavailable", message: "공통 시장 근거를 읽지 못함" };
    const { unmount } = await renderCard(() => na);
    expect(screen.getByTestId("wr-market")).toHaveTextContent("공통 시장 근거 확인 불가 — 공통 시장 근거를 읽지 못함");
    expect(screen.getByTestId("wr-market")).not.toHaveTextContent("자료 기준일");
    unmount();
    __resetQueryCache();
    const part = clone(WEEKLY_NONE);
    const f = structuredClone(part.market_evidence.fields) as Record<string, Record<string, unknown>>;
    f.regime = { ...f.regime, same_basis: false, today: { status: "unavailable", reason: "당일 판정 칸 없음" } };
    f.flows = { ...f.flows, w20: { status: "unavailable", reason: "20거래일 창의 수급이 온전하지 않음" } };
    f.kospi = { ...f.kospi, date: null };
    part.market_evidence = { ...part.market_evidence, status: "partial", fields: f };
    await renderCard(() => part);
    const mk = screen.getByTestId("wr-market");
    expect(mk).toHaveTextContent("KODEX 200 하락장 · 27거래일째(판정 가격 11/16 · 당일 판정 확인 불가 — 아침 판정 · 20거래일 -11.03%");
    expect(mk).toHaveTextContent("외국인 20거래일 확인 불가 — 20거래일 창의 수급이 온전하지 않음");
    expect(mk).toHaveTextContent("자료 기준일: ETF 시세 11/16 · 코스피 확인 불가 · 수급 11/13");
  });

  it("① 서식 — 이동평균 위치가 다르면 따로 · 지속일 '이상' · 아침과 당일이 다른 근거 · 직전 창 없음 · 판정 없음", () => {
    const base = WEEKLY_NONE.market_evidence;
    const f = structuredClone(base.fields) as Record<string, Record<string, unknown>>;
    const today = f.regime.today as Record<string, unknown>;
    f.regime = {
      ...f.regime,
      same_basis: false,
      today: { ...today, at_least: true, ma20: { ...(today.ma20 as object), position: "above" }, r60: { value: null } },
    };
    const w20 = f.flows.w20 as Record<string, unknown>;
    f.flows = { ...f.flows, w20: { ...w20, previous: null } };
    const v = weeklyMarketView({ ...base, fields: f }, null);
    if (!v.ok) throw new Error(v.reason);
    expect(v.line).toContain("KODEX 200 하락장 · 27거래일째 이상(판정 가격 11/16 · 20거래일 -11.03%(10/19 → 11/16) · 60거래일 확인 불가 · 20일선 위 · 60일선 아래) · 아침 판정은 다른 근거(복사 글에 둘 다)");
    expect(v.line).toContain("외국인 최근 20거래일 순매도 6,060억원(10/19 ~ 11/13) · 직전 20거래일 확인 불가");
    expect(v.basis).toMatch(/^자료 기준일: ETF 시세 확인 불가 · /);
    f.regime = { status: "unavailable", reason: "아침 요약 기준을 읽지 못했습니다", today: null, morning: null };
    const none = weeklyMarketView({ ...base, fields: f }, "2026-11-16");
    expect(none.ok && none.line).toMatch(/^KODEX 200 시장 판정 확인 불가 — 아침 요약 기준을 읽지 못했습니다 · /);
    expect(weeklyMarketView(undefined, "2026-11-16")).toEqual({ ok: false, reason: "공통 시장 근거 확인 불가 — 사유 확인 불가" });
  });

  it("묶음 1개월 — 같으면 '각' · 다르면 최소 ~ 최대", () => {
    const g = WEEKLY_NONE.flows.find((f) => f.rep === "483290");
    expect(g && oneMonthText(g)).toBe("+5.57% ~ +5.75%");
  });

  it("W5 · I-11 — 3개월 기간 다름 = 값 + '기간 다름(실제 기간)' · 자료 부족 알약은 그 줄 아래(충분한 줄은 없음)", async () => {
    const r = clone(WEEKLY_NONE);
    const m0 = r.flows[0].members[0];
    m0.three_month = 4.2;
    m0.periods.three_month = { status: "period_differs", start: "2026-08-25", end: "2026-11-16" };
    m0.lack = ["3개월 기간 다름"];
    r.flows[0].lack = ["3개월 기간 다름"];
    const g = r.flows[2];
    g.members[1].lack = ["공식 기준정보 없음"];
    g.lack = ["공식 기준정보 없음"];
    await renderCard(() => r);
    const rows = firstRows();
    expect(rows[0]).toHaveTextContent("+4.20% · 기간 다름(8/25 → 11/16)");
    expect(rows[0]).not.toHaveTextContent("확인 불가");
    expect(within(rows[0]).getByText("자료 부족: 3개월 기간 다름")).toHaveClass("wk-lack");
    expect(rows[1].querySelector(".wk-lack")).toBeNull();
    // 묶음은 묶음 줄이 아니라 그 ETF 줄 아래
    expect(rows[2].querySelector(".wk-lack")).toBeNull();
    const mem = screen.getByTestId("wr-flows").querySelector('tr[data-member="453870"]') as HTMLElement;
    expect(within(mem).getByText("자료 부족: 공식 기준정보 없음")).toBeInTheDocument();
  });
});

describe("주간 ETF 점검 — [고르기] · 고른 표시 · ③ 선택한 후보 검토", () => {
  it("[고르기] → 그 ETF 로 다시 읽음 · 읽는 동안 복사 · 넘기기 · 고르기 막음 · 끝나면 ③ 검토 · 고른 표시(40px 칸 · 행 표시)", async () => {
    const d = deferred<WeeklyReviewResponse>();
    fetchWeeklyReview.mockImplementation((sel: string | null) => (sel ? d.promise : Promise.resolve(WEEKLY_NONE)));
    render(<WeeklyReviewCard onNavigate={vi.fn()} gen={0} />);
    await screen.findByTestId("wr-flows");
    expect(screen.getByTestId("wr-review")).toHaveTextContent("고르기 전");
    fireEvent.click(pickBtn(firstRows()[1]));
    expect(fetchWeeklyReview).toHaveBeenLastCalledWith("476070");
    expect(screen.getByRole("button", { name: "AI용 주간 검토 복사" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "AI 투자 세션으로 넘기기" })).toBeDisabled();
    expect(pickBtn(firstRows()[0])).toBeDisabled();
    expect(screen.getByText(/다시 읽는 중/)).toBeInTheDocument();
    await act(async () => d.resolve(WEEKLY_SELECTED));
    await picked();
    const row = firstRows()[1];
    expect(row).toHaveClass("wr-picked");
    expect(row).toHaveClass("wk-picked-row");
    const mark = within(row).getByText("✓ 고른 후보");
    expect(mark).toHaveClass("wk-picked-mark");
    expect(within(row).queryByRole("button", { name: /고르기/ })).toBeNull();
    // 다른 줄은 [고르기](중간 버튼 40px)
    expect(pickBtn(firstRows()[0]).className).toContain("btn-md");
    expect(screen.getByRole("button", { name: "AI용 주간 검토 복사" })).not.toBeDisabled();
    // 보유 한 종목을 고르는 칸 · 기본 짝 글자가 없다
    expect(screen.getByTestId("wr-review")).not.toHaveTextContent("보유 한 종목");
    expect(screen.getByTestId("wr-review")).not.toHaveTextContent("비중 1위");
  });

  it("W7 — 묶음 안 둘째 ETF(대표 아님)도 고를 수 있다 · 고른 표시는 그 ETF 줄", async () => {
    const r = clone(WEEKLY_SELECTED);
    r.selected = { ticker: "453870", name: "TIGER 인도니프티50", rank: 4 };
    await renderCard((s) => (s ? r : WEEKLY_NONE));
    const mem = () => screen.getByTestId("wr-flows").querySelector('tr[data-member="453870"]') as HTMLElement;
    fireEvent.click(within(mem()).getByRole("button", { name: "TIGER 인도니프티50 고르기" }));
    expect(fetchWeeklyReview).toHaveBeenLastCalledWith("453870");
    await waitFor(() => expect(within(mem()).getByText("✓ 고른 후보")).toBeInTheDocument());
    expect(mem()).toHaveClass("wk-picked-row");
    expect(firstRows()[2]).not.toHaveClass("wr-picked");
  });

  it("③ = 응답의 고른 후보 검토(어떤 상품인가 · 실제로 올랐나 · 더 확인할 것 · 내 보유 겹침) · 확인 범위 줄이 숫자 줄보다 먼저", async () => {
    await renderCard();
    await pickSecond();
    expect(screen.getByTestId("wr-r1")).toHaveTextContent("공식 기초지수 iSelect 글로벌 비만치료제TOP2 Plus 지수(PR)");
    expect(screen.getByTestId("wr-r2")).toHaveTextContent("올랐고 국내시장보다 22.80%p 높음");
    const lines = Array.from(screen.getByTestId("wr-review").querySelectorAll("div")).map((e) => e.textContent ?? "");
    const iRange = lines.findIndex((t) => t.startsWith("보유 평가액의 52.00%(보유 ETF 2개)에 해당하는 ETF 는 저장된 상위 행 밖 구성이 미확인"));
    const iNum = lines.findIndex((t) => t.startsWith("확보된 행으로 계산한 주요 주식별 보유 노출 범위 0.00% ~ 7.03%"));
    expect(iRange).toBeGreaterThanOrEqual(0);
    expect(iNum).toBeGreaterThan(iRange);
  });

  it("[비교 상세 →] = 「보유와 후보 비교」 후보 칸에 고른 후보 한쪽만 · 이 화면 조건 · 기간은 이번 이동에만", async () => {
    const { onNavigate } = await renderCard();
    await pickSecond();
    fireEvent.click(screen.getByRole("button", { name: "비교 상세 →" }));
    expect(onNavigate).toHaveBeenCalledWith("holding_candidate_compare");
    expect(takePresetCandidate()).toEqual({
      ticker: "476070",
      name: "KODEX 글로벌비만치료제TOP2 Plus",
      side: "top",
      condition: { basis: "one_month", filters: WEEKLY_SELECTED.condition.filters },
      start: "2026-10-19",
      end: "2026-11-16",
      origin: "「주간 ETF 점검」",
    });
    expect(takeOneTimeCondition("compare")?.cond).toEqual({ basis: "one_month", filters: WEEKLY_SELECTED.condition.filters });
    expect(takeExposureSingle()).toBeNull();
  });

  it("[구성종목 보기 →] = 「ETF 구성종목」 이 ETF 하나(보낸 화면 · 목록 조건) · 목록 초안은 건드리지 않음", async () => {
    const { onNavigate } = await renderCard();
    await pickSecond();
    fireEvent.click(screen.getByRole("button", { name: "구성종목 보기 →" }));
    expect(onNavigate).toHaveBeenCalledWith("etf_exposure");
    expect(takeExposureSingle()).toEqual({
      ticker: "476070",
      name: "KODEX 글로벌비만치료제TOP2 Plus",
      from: "「주간 ETF 점검」",
      condition: { basis: "one_month", side: "top", start: "2026-10-19", end: "2026-11-16", filters: WEEKLY_SELECTED.condition.filters },
    });
    expect(takePresetCandidate()).toBeNull();
    expect(window.sessionStorage.length).toBe(0);
  });

  it("다시 읽는 동안 [비교 상세] · [구성종목 보기] · [판단 근거 보기]도 막힘(앞 응답으로 넘기지 않음)", async () => {
    const d = deferred<WeeklyReviewResponse>();
    const { rerender } = await renderCard();
    await pickSecond();
    fetchWeeklyReview.mockImplementation(() => d.promise);
    rerender(<WeeklyReviewCard onNavigate={vi.fn()} gen={1} />);
    await waitFor(() => expect(screen.getByRole("button", { name: "비교 상세 →" })).toBeDisabled());
    expect(screen.getByRole("button", { name: "구성종목 보기 →" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /판단 근거 보기/ })).toBeDisabled();
    await act(async () => d.resolve(WEEKLY_SELECTED));
    await waitFor(() => expect(screen.getByRole("button", { name: "비교 상세 →" })).not.toBeDisabled());
  });

  it("[고른 후보 지우기] → 고르기 전 · [후보리스트 보기 →] 는 같은 조건 · 보낸 화면 「주간 ETF 점검」", async () => {
    const { onNavigate } = await renderCard();
    await pickSecond();
    fireEvent.click(screen.getByRole("button", { name: "고른 후보 지우기" }));
    await waitFor(() => expect(screen.getByTestId("wr-review")).toHaveTextContent("고르기 전"));
    fireEvent.click(screen.getByRole("button", { name: "후보리스트 보기 →" }));
    expect(onNavigate).toHaveBeenCalledWith("workbench");
    const once = takeOneTimeCondition("candidates");
    expect(once?.cond).toEqual({ basis: "one_month", filters: WEEKLY_NONE.condition.filters });
    expect(once?.origin).toBe("「주간 ETF 점검」");
  });

  it("고른 후보가 새 목록에 없으면 알리고 다른 후보로 바꾸지 않음", async () => {
    await renderCard((s) => (s ? { ...WEEKLY_NONE, selected_missing: true } : WEEKLY_NONE));
    fireEvent.click(pickBtn(firstRows()[1]));
    expect(await screen.findByText(/고른 후보가 지금 목록에 없습니다/)).toBeInTheDocument();
    expect(screen.getByTestId("wr-review")).toHaveTextContent("고르기 전");
  });
});

describe("주간 ETF 점검 — 복사 · 넘기기 = 같은 응답(같은 검토 건)", () => {
  it("[AI용 주간 검토 복사] = 응답의 글 그대로 · 막히면 글을 보여 줌", async () => {
    await renderCard();
    await pickSecond();
    fireEvent.click(screen.getByRole("button", { name: "AI용 주간 검토 복사" }));
    expect(writeText).toHaveBeenCalledWith(WEEKLY_SELECTED.copy_text);
    expect(
      await screen.findByText(
        `주간 검토 글을 복사했습니다 — 근거 ${WEEKLY_SELECTED.evidence.length}개 · 답 받을 ETF 3개(지금 보이는 목록 · 기간 · 고른 후보 그대로).`,
      ),
    ).toBeInTheDocument();
    writeText.mockRejectedValueOnce(new Error("blocked"));
    fireEvent.click(screen.getByRole("button", { name: "AI용 주간 검토 복사" }));
    const ta = (await screen.findByLabelText("복사할 주간 검토 글")) as HTMLTextAreaElement;
    expect(ta.value).toBe(WEEKLY_SELECTED.copy_text);
  });

  it("[AI 투자 세션으로 넘기기] = 응답 하나로 만든 초안(질문 = 복사 글 · 고른 후보 상품 · 구성 · 겹침 · 검토 조건 · 근거 목록 · 출처 값)", async () => {
    const { onNavigate } = await renderCard();
    await pickSecond();
    fireEvent.click(screen.getByRole("button", { name: "AI 투자 세션으로 넘기기" }));
    expect(onNavigate).toHaveBeenCalledWith("ai_sessions");
    const d = loadAISessionsDraft();
    expect(d?.source_screen).toBe("today_weekly_review");
    expect(d?.asof).toBe("2026-11-16");
    expect(d?.question_text).toBe(WEEKLY_SELECTED.copy_text);
    expect(d?.candidate_snapshot).toEqual(WEEKLY_SELECTED.candidate_snapshot);
    expect(d?.filters).toEqual(WEEKLY_SELECTED.condition.filters);
    expect(d?.market_context_snapshot).toEqual(WEEKLY_SELECTED.market_context_snapshot);
    expect(d?.constituent_snapshot).toEqual(WEEKLY_SELECTED.constituent_snapshot);
    expect(d?.overlap_snapshot).toEqual(WEEKLY_SELECTED.overlap);
    expect(d?.data_quality_snapshot).toEqual(WEEKLY_SELECTED.data_quality_snapshot);
    expect(WEEKLY_SELECTED.data_quality_snapshot.evidence_list.length).toBe(WEEKLY_SELECTED.evidence.length);
    expect(describeDraftOrigin(d!)).toMatch(/^「주간 ETF 점검」 · 목록 30개 · /);
  });

  it("이미 넘긴 초안이 있으면 확인 줄 → [바꾸고 이동] · [그대로 두기]", async () => {
    const old = weeklyDraft(WEEKLY_NONE);
    delete old.constituent_snapshot;
    delete old.overlap_snapshot;
    saveAISessionsDraft({ ...old, source_screen: undefined, draft_created_at: "2026-11-17T00:14:00+09:00" });
    const { onNavigate } = await renderCard();
    fireEvent.click(screen.getByRole("button", { name: "AI 투자 세션으로 넘기기" }));
    expect(screen.getByTestId("wr-pending")).toHaveTextContent("이미 넘긴 초안이 있습니다(「후보리스트」 · 목록 30개 · 2026-11-17 00:14)");
    expect(onNavigate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "그대로 두기" }));
    expect(loadAISessionsDraft()?.source_screen).toBeUndefined();
    fireEvent.click(screen.getByRole("button", { name: "AI 투자 세션으로 넘기기" }));
    fireEvent.click(screen.getByRole("button", { name: "바꾸고 이동" }));
    expect(loadAISessionsDraft()?.source_screen).toBe("today_weekly_review");
    expect(onNavigate).toHaveBeenCalledWith("ai_sessions");
    clearAISessionsDraft();
  });
});

describe("주간 ETF 점검 — ④ AI 의견 요약 · ⑤ 최근 검토 기록", () => {
  it("첫 사용 = '이 화면에서 저장한 기록 없음'(④ · ⑤ 모두)", async () => {
    await renderCard();
    expect(screen.getByTestId("wr-ai")).toHaveTextContent("이 화면에서 저장한 기록 없음");
    expect(screen.getByTestId("wr-last")).toHaveTextContent("이 화면에서 저장한 기록 없음");
  });

  it("최신 확인(AI 마다) · AI 가 적은 확인 항목 줄 · 확인 시각이 비면 '확인 시각 미기재'(저장 시각과 따로)", async () => {
    await renderCard(() => WEEKLY_SAVED);
    const lt = screen.getByTestId("wr-ai-latest");
    expect(lt).toHaveTextContent("최신 확인: GPT 같음 · Gemini 확인 불가 · Claude 새 값 있음 · AI 답 3개");
    expect(within(lt).getByText("새 값 있음")).toHaveClass("wr-pill-wait");
    const items = screen.getAllByTestId("wr-ai-item");
    expect(items).toHaveLength(1);
    expect(items[0]).toHaveTextContent(
      "Claude — 항목 코스피 종가 · 값 5,190.00 · 기준일 2026-11-16 · 출처 https://data.krx.co.kr · 확인 시각 확인 시각 미기재 · 달라지는 해석 코스피 방향",
    );
    expect(within(items[0]).getByText("확인 시각 미기재")).toHaveClass("wr-pill-wait");
    expect(lt).toHaveTextContent("확인 시각 = AI 가 답에 적은 시각(기록 저장 시각과 따로)");
  });

  it("대조 — 같은 상태 · 같은 번호 / 같은 상태 · 같은 번호와 다른 번호 / 한 의견 · 요약 확인 필요 · 칸 = 상태 · 근거 · 이유 · 다음 확인", async () => {
    await renderCard(() => WEEKLY_SAVED);
    const tbl = screen.getByTestId("wr-ai");
    const row = (t: string) => tbl.querySelector(`tr[data-ticker="${t}"]`) as HTMLElement;
    expect(row("428560")).toHaveTextContent("상태 같음(근거 확인)인용 근거 번호 일치");
    expect(row("476070")).toHaveTextContent("추가 확인 · 근거 27, 33이유: 상위 행 밖 보유 구성 미확인 · 다음 확인: 보유 ETF 구성 더 받기");
    expect(row("476070")).toHaveTextContent("추가 확인 · 근거 2, 27이유: 3개월 흐름 약함 · 다음 확인: 3개월 KODEX 대비 확인");
    expect(row("476070")).toHaveTextContent("상태 같음(추가 확인)같은 번호 27 · 다른 번호 GPT 33 / Gemini 33, 34 / Claude 2");
    expect(row("453810")).toHaveTextContent("자료 부족 · 근거 28이유: 인도 수급 자료 없음");
    expect(row("453810")).toHaveTextContent("요약 확인 필요상태를 셋 중 하나로 읽을 수 없음");
    expect(row("453810")).toHaveTextContent("요약 확인 필요이 ETF 칸이 없음");
    expect(row("453810")).toHaveTextContent("한 의견");
    expect(tbl).toHaveTextContent("AI 의견이며 결정이 아닙니다");
    expect(tbl).not.toHaveTextContent("확인할 점:");
  });

  it("답이 하나인 기록(한 AI 답으로도 저장) = 그 AI 열만 · 최신 확인도 그 AI 만", async () => {
    const r = clone(WEEKLY_SAVED);
    const cmp = r.last_record.compare!;
    cmp.answers!.gemini = { status: "no_answer" };
    cmp.answers!.claude = { status: "no_answer" };
    cmp.opinion_text = "한 의견";
    for (const row of cmp.rows) {
      row.cells.gemini = { status: "no_answer" };
      row.cells.claude = { status: "no_answer" };
    }
    await renderCard(() => r);
    const ths = Array.from(screen.getByTestId("wr-ai").querySelectorAll("th")).map((t) => t.textContent);
    expect(ths).toEqual(["ETF", "GPT", "대조"]);
    expect(screen.getByTestId("wr-ai-latest")).toHaveTextContent("최신 확인: GPT 같음 · 한 의견");
    expect(screen.queryAllByTestId("wr-ai-item")).toHaveLength(0);
  });

  it("답 칸이 빈 AI 의 대조 칸 = '답 없음'(요약 확인 필요와 다름)", async () => {
    const r = clone(WEEKLY_SAVED);
    r.last_record.compare!.rows[0].cells.claude = { status: "no_answer" };
    await renderCard(() => r);
    const row = screen.getByTestId("wr-ai").querySelector('tr[data-ticker="428560"]') as HTMLElement;
    expect(row).toHaveTextContent("답 없음");
    expect(row).not.toHaveTextContent("요약 확인 필요");
  });

  it("최신 확인 '형식 없음' = 사유와 함께 · 질문 형식을 못 읽으면(no_format) 대조 표 대신 안내 · 답마다 최신 확인은 그대로", async () => {
    const r = clone(WEEKLY_SAVED);
    const cmp = r.last_record.compare!;
    const g = cmp.answers!.gpt;
    if (g.status === "ok") g.latest = { state: "형식 없음", raw: null, reason: "최신 확인 줄 없음" };
    cmp.status = "no_format";
    cmp.message = "질문 원문에서 근거 번호 · 대상 ETF 를 찾지 못했습니다 — 요약 확인 필요(원문은 「AI 투자 세션」)";
    cmp.rows = [];
    await renderCard(() => r);
    const ai = screen.getByTestId("wr-ai");
    expect(ai).toHaveTextContent("GPT 형식 없음(최신 확인 줄 없음)");
    expect(ai).toHaveTextContent("질문 원문에서 근거 번호 · 대상 ETF 를 찾지 못했습니다");
    expect(ai.querySelector("table")).toBeNull();
  });

  it("⑤ 저장 시각 · 원자료 기준일 따로 · 판단 · 빈 이유 · 다음 확인 = 미기록 · [기록 열기]는 그 기록 id 를 넘김", async () => {
    const { onNavigate } = await renderCard(() => WEEKLY_SAVED);
    const last = screen.getByTestId("wr-last");
    // 목업 ⑤(검토 F4) — 고른 후보(저장한 코드 · 이름) · AI 답 수까지 한 줄
    expect(screen.getByTestId("wr-last-line")).toHaveTextContent(
      `저장 2026-11-17 21:05 · 원자료 기준일 11/16 · 고른 후보 476070 KODEX 글로벌비만치료제TOP2 Plus · 사용자 판단 ${verdictText("today_weekly_review", "hold")} · AI 답 3개`,
    );
    expect(last).toHaveTextContent("이 화면에서 넘겨 저장한 기록 중 가장 최근 1건");
    expect(last).not.toHaveTextContent("이 한 장");
    expect(last).toHaveTextContent("이유(메모) 미기록");
    expect(last).toHaveTextContent("다음 확인 미기록");
    fireEvent.click(within(last).getByRole("button", { name: /기록 열기/ }));
    expect(onNavigate).toHaveBeenCalledWith("ai_sessions");
    expect(takeOpenRecord()).toBe(WEEKLY_SAVED.last_record.id);
  });

  it("기록 읽기 실패는 '없음'이 아니라 '읽지 못함'(④ · ⑤)", async () => {
    await renderCard(() => ({ ...WEEKLY_NONE, last_record: { status: "error", message: "기록을 읽지 못했습니다 — 「AI 투자 세션」에서 확인" } }));
    expect(screen.getByTestId("wr-ai")).toHaveTextContent("기록을 읽지 못했습니다");
    expect(screen.getByTestId("wr-last")).toHaveTextContent("기록을 읽지 못했습니다");
    expect(screen.getByTestId("wr-last")).not.toHaveTextContent("저장한 기록 없음");
  });
});

describe("주간 ETF 점검 — 상태 · 다시 읽기", () => {
  it("목록을 만들 수 없음 · 불러오기 실패(화면 머리 [다시 읽기]로 안내)", async () => {
    fetchWeeklyReview.mockResolvedValue({ status: "no_common_period", message: "공통 기간 없음", source_screen: "today_weekly_review", generated_at: "x", last_record: { status: "none", message: "" } });
    render(<WeeklyReviewCard onNavigate={vi.fn()} gen={0} />);
    expect(await screen.findByTestId("wr-notok")).toHaveTextContent("공통 기간 없음");
    __resetQueryCache();
    fetchWeeklyReview.mockRejectedValue(new Error("down"));
    render(<WeeklyReviewCard onNavigate={vi.fn()} gen={0} />);
    expect(await screen.findByText("목록을 불러오지 못했습니다 · [다시 읽기]로 다시 시도하세요")).toBeInTheDocument();
    expect(screen.queryByText(/요약 다시 읽기/)).toBeNull();
  });

  it("다시 읽기 차례(gen)가 오르면 지금 고른 후보 그대로 다시 읽는다", async () => {
    const { rerender } = await renderCard();
    await pickSecond();
    const n = fetchWeeklyReview.mock.calls.length;
    rerender(<WeeklyReviewCard onNavigate={vi.fn()} gen={1} />);
    await waitFor(() => expect(fetchWeeklyReview.mock.calls.length).toBe(n + 1));
    expect(fetchWeeklyReview).toHaveBeenLastCalledWith("476070");
  });
});

describe("주간 ETF 점검 — 독립 검토 정정(2026-11-17 · V1 계약 유지)", () => {
  it("F1 — 다시 읽기 차례 뒤 전에 고른 후보를 다시 고르면 새로 읽는다(받아 둔 옛 응답 · 저장 전 ⑤를 보이지 않음)", async () => {
    let saved = false;
    const { rerender } = await renderCard((s) => (s ? (saved ? WEEKLY_SAVED : WEEKLY_SELECTED) : WEEKLY_NONE));
    await pickSecond();
    expect(screen.getByTestId("wr-last")).toHaveTextContent("이 화면에서 저장한 기록 없음");
    fireEvent.click(screen.getByRole("button", { name: "고른 후보 지우기" }));
    await waitFor(() => expect(screen.getByTestId("wr-review")).toHaveTextContent("고르기 전"));
    saved = true; // 그 사이 기록 저장(다른 화면)
    rerender(<WeeklyReviewCard onNavigate={vi.fn()} gen={1} />);
    await waitFor(() => expect(fetchWeeklyReview).toHaveBeenLastCalledWith(null));
    const n = fetchWeeklyReview.mock.calls.length;
    await waitFor(() => expect(pickBtn(firstRows()[1])).not.toBeDisabled());
    fireEvent.click(pickBtn(firstRows()[1]));
    await waitFor(() => expect(fetchWeeklyReview.mock.calls.length).toBe(n + 1));
    expect(fetchWeeklyReview).toHaveBeenLastCalledWith("476070");
    await waitFor(() => expect(screen.getByTestId("wr-last")).toHaveTextContent(verdictText("today_weekly_review", "hold")));
  });

  it("F1 — 화면에 다시 들어오면 받아 둔 응답을 쓰지 않고 새로 읽는다", async () => {
    const first = await renderCard();
    const n = fetchWeeklyReview.mock.calls.length;
    first.unmount();
    render(<WeeklyReviewCard onNavigate={vi.fn()} gen={0} />);
    await screen.findByTestId("wr-flows");
    expect(fetchWeeklyReview.mock.calls.length).toBe(n + 1);
  });

  it("F2 · F8 — 다시 읽기 차례가 오르면 읽는 동안 복사 · 넘기기 · 고르기를 막고 새 조회를 보낸다", async () => {
    const { rerender } = await renderCard();
    const d = deferred<WeeklyReviewResponse>();
    fetchWeeklyReview.mockImplementation(() => d.promise);
    const n = fetchWeeklyReview.mock.calls.length;
    rerender(<WeeklyReviewCard onNavigate={vi.fn()} gen={1} />);
    await waitFor(() => expect(fetchWeeklyReview.mock.calls.length).toBe(n + 1));
    expect(screen.getByRole("button", { name: "AI용 주간 검토 복사" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "AI 투자 세션으로 넘기기" })).toBeDisabled();
    expect(pickBtn(firstRows()[0])).toBeDisabled();
    expect(screen.getByText(/다시 읽는 중/)).toBeInTheDocument();
    // 읽는 중에 차례가 또 오르면 진행 중 조회에 합치지 않고 새로 보낸다
    rerender(<WeeklyReviewCard onNavigate={vi.fn()} gen={2} />);
    await waitFor(() => expect(fetchWeeklyReview.mock.calls.length).toBe(n + 2));
    await act(async () => d.resolve(WEEKLY_NONE));
    await waitFor(() => expect(screen.getByRole("button", { name: "AI용 주간 검토 복사" })).not.toBeDisabled());
  });

  it("F3 — 복사한 뒤 응답이 바뀌면 안내를 바꾸고, 넘길 때 확인한다(복사한 글 ≠ 넘길 질문 원문)", async () => {
    let n = 0;
    const { rerender } = await renderCard(() => ({ ...WEEKLY_NONE, copy_text: `${WEEKLY_NONE.copy_text}\n#${n}` }));
    fireEvent.click(screen.getByRole("button", { name: "AI용 주간 검토 복사" }));
    await screen.findByText(/주간 검토 글을 복사했습니다/);
    n = 1;
    rerender(<WeeklyReviewCard onNavigate={vi.fn()} gen={1} />);
    expect(await screen.findByText(/복사한 뒤 화면 자료가 바뀌었습니다/)).toBeInTheDocument();
    expect(screen.queryByText(/주간 검토 글을 복사했습니다/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "AI 투자 세션으로 넘기기" }));
    expect(screen.getByTestId("wr-pending")).toHaveTextContent("복사한 뒤 자료를 다시 읽어 지금 화면 글이 복사한 글과 다릅니다");
    expect(loadAISessionsDraft()).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "지금 화면 글로 넘기기" }));
    expect(loadAISessionsDraft()?.question_text).toBe(`${WEEKLY_NONE.copy_text}\n#1`);
  });
});
