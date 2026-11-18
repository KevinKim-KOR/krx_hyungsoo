// POC6-32 V2 — ③ 「선택한 후보 검토」(today/WeeklyCandidateReview) 시험 · PLAN §3-1 R1 ~ R5 · §9 I-7 ~ I-11 · I-17.
// 고정 응답 = 서버 조립 출력(lib/weeklyReviewTestFixtures.json · 11/16 공개 시장 자료 · 합성 보유) — 고정 자료에 없는 상태
// (공식 기준정보 없음 · 구성 미수집 · 기간 다름 · 국내시장 대비 못 함 · 잠정 · 보유 없음 · 계산 실패)는 응답을 복사해 칸만 바꾼다.
// [판단 근거 보기]는 진짜 요청 함수를 쓰고 fetch 만 가짜다(보낸 요청 몸통을 그대로 대조).
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { WEEKLY_NONE, WEEKLY_SELECTED } from "@/lib/weeklyReviewTestFixtures";
import type { WeeklyReviewOk, WeeklySelectedReview } from "@/lib/api/weeklyReview";
import { feeText, memberPeriodText, oneMonthText, threeMonthText, weeklyPreviewQuery } from "@/lib/weeklyReview";
import WeeklyCandidateReview from "./WeeklyCandidateReview";

type Pending = { url: string; body: Record<string, unknown> | null; resolve: (b: unknown) => void };
let pending: Pending[] = [];
const fetchMock = vi.fn((url: string, init?: { body?: string }) => {
  return new Promise((resolve) => {
    pending.push({
      url,
      body: init?.body ? JSON.parse(init.body) : null,
      resolve: (b) => resolve({ ok: true, status: 200, text: async () => JSON.stringify(b) }),
    });
  });
});

beforeEach(() => {
  pending = [];
  fetchMock.mockClear();
  vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://api.test");
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

const clone = (r: WeeklyReviewOk) => structuredClone(r) as WeeklyReviewOk;
const rvOf = (r: WeeklyReviewOk) => r.selected_review as WeeklySelectedReview;

function show(r: WeeklyReviewOk, busy = false) {
  const h = { onClear: vi.fn(), onCompare: vi.fn(), onExposure: vi.fn() };
  const view = render(<WeeklyCandidateReview r={r} busy={busy} {...h} />);
  return { ...h, ...view };
}

describe("③ 선택한 후보 검토 — 고르기 전 · 고른 뒤 네 질문", () => {
  it("고르기 전 = 안내만(R1 ~ R5 없음)", () => {
    show(WEEKLY_NONE);
    const box = screen.getByTestId("wr-review");
    expect(box).toHaveTextContent("③ 선택한 후보 검토");
    expect(box).toHaveTextContent("고르기 전");
    expect(box).toHaveTextContent("위 표의 [고르기]로 후보를 고르면 어떤 상품인지 · 실제로 올랐는지 · 내 보유에 무엇이 겹치는지 봅니다.");
    expect(screen.queryByTestId("wr-r1")).toBeNull();
    expect(screen.queryByRole("button", { name: "비교 상세 →" })).toBeNull();
  });

  it("R1 어떤 상품인가 = 공식 기준정보(파일 날짜 · 총보수 0.45%) · 주식 상위 3개 · 상위 3개 합 · 구성 줄(기준일 · 저장 행 · 상태)", () => {
    show(WEEKLY_SELECTED);
    expect(screen.getByTestId("wr-review-head")).toHaveTextContent("KODEX 글로벌비만치료제TOP2 Plus(476070) · 1개월 상위 2위");
    const r1 = screen.getByTestId("wr-r1");
    expect(r1).toHaveTextContent(
      "공식 기초지수 iSelect 글로벌 비만치료제TOP2 Plus 지수(PR) · 지수산출기관 NH투자증권 · 투자 대상 해외 · 주식 · 상품 구조 추적배수 일반 · 실물(패시브) · 총보수 0.45% (KRX 공식 기준정보 2026-09-27 파일)",
    );
    const c = rvOf(WEEKLY_SELECTED).constituents;
    const tops = c.top_stocks.map((s) => `${s.name} ${(s.weight_pct as number).toFixed(2)}%`).join(" · ");
    expect(c.top_stocks).toHaveLength(3);
    expect(r1).toHaveTextContent(`주요 편입(주식) ${tops} → 상위 3개 합 57.27%`);
    expect(r1).toHaveTextContent("구성 기준일 11/13 · 저장 4행(주식 3 · 원화현금 1) · 상위 4행만 확인(그 밖 구성은 미확인)");
  });

  it("R2 실제로 올랐나 = '가격 관측'(판정 아님) · 실제 기간 · 방향 · 국내시장 값과 문구(시작 · 끝 · 가격 상태가 맞을 때)", () => {
    show(WEEKLY_SELECTED);
    const r2 = screen.getByTestId("wr-r2");
    const heads = Array.from(r2.querySelectorAll("th")).map((t) => t.textContent);
    expect(heads).toEqual(["기간", "가격 관측", "실제 기간", "방향", "같은 기간 국내시장(KODEX 200) 대비"]);
    expect(r2).not.toHaveTextContent("판정");
    const row = (p: string) => r2.querySelector(`tr[data-period="${p}"]`) as HTMLElement;
    expect(row("1m")).toHaveTextContent("1개월+11.77%10/19 → 11/16올랐음국내시장 -11.03% · 올랐고 국내시장보다 22.80%p 높음");
    expect(row("3m")).toHaveTextContent("3개월-0.62%8/18 → 11/16내렸음국내시장 -26.29% · 내렸지만 국내시장보다 25.67%p 덜 내림");
    expect(r2).toHaveTextContent("가격 = 11/16 마감 뒤 저장(이 ETF · KODEX 200 같음)");
  });

  it("R2 — 기간 다름 = 값 + '기간 다름' + 실제 기간(공통 기간 함께) · 국내시장 값 없음 · 대비 못 함 = 문구만 · 잠정 문구 그대로", () => {
    const r = clone(WEEKLY_SELECTED);
    const [m1, m3] = rvOf(r).returns;
    Object.assign(m3, {
      value_pct: 4.2,
      start: "2026-08-25",
      status: "period_differs",
      direction: "up",
      market: { value_pct: null, diff_pp: null, comparable: false, provisional: false, reason: "기간 다름" },
      phrase: "올랐음 · 기간 다름 · 국내시장 대비 안 함",
    });
    Object.assign(m1, {
      market: { ...m1.market, provisional: true },
      phrase: "올랐고 국내시장보다 22.80%p 높음 · 잠정 비교",
    });
    show(r);
    const r2 = screen.getByTestId("wr-r2");
    const row3 = r2.querySelector('tr[data-period="3m"]') as HTMLElement;
    expect(row3).toHaveTextContent("3개월+4.20% · 기간 다름8/25 → 11/16 (공통 8/18 → 11/16)올랐음올랐음 · 기간 다름 · 국내시장 대비 안 함");
    expect(row3).not.toHaveTextContent("국내시장 -");
    expect(r2.querySelector('tr[data-period="1m"]')).toHaveTextContent("올랐고 국내시장보다 22.80%p 높음 · 잠정 비교");

    const r3 = clone(WEEKLY_SELECTED);
    Object.assign(rvOf(r3).returns[0], {
      market: { value_pct: null, diff_pp: null, comparable: false, provisional: false, reason: "가격 상태 다름" },
      phrase: "올랐음 · 국내시장 대비 안 함(가격 상태 다름)",
    });
    Object.assign(rvOf(r3).returns[1], {
      value_pct: null,
      status: "missing",
      direction: null,
      start: null,
      end: null,
      market: { value_pct: null, diff_pp: null, comparable: false, provisional: false, reason: "수익률 자료 없음" },
      phrase: "수익률 확인 불가",
    });
    render(<WeeklyCandidateReview r={r3} busy={false} onClear={vi.fn()} onCompare={vi.fn()} onExposure={vi.fn()} />);
    const last = screen.getAllByTestId("wr-r2")[1];
    expect(last.querySelector('tr[data-period="1m"]')).toHaveTextContent("+11.77%10/19 → 11/16올랐음올랐음 · 국내시장 대비 안 함(가격 상태 다름)");
    expect(last.querySelector('tr[data-period="3m"]')).toHaveTextContent("3개월확인 불가확인 불가확인 불가수익률 확인 불가");
  });

  it("R3 더 확인할 것 = 서버 줄 그대로 · 보유 겹침 확인 범위 줄은 경고 색 · 상세 근거 안내", () => {
    show(WEEKLY_SELECTED);
    const r3 = screen.getByTestId("wr-r3");
    for (const l of rvOf(WEEKLY_SELECTED).checks) expect(r3).toHaveTextContent(l);
    const ov = rvOf(WEEKLY_SELECTED).overlap!;
    expect(within(r3).getByText(ov.warn_lines[0])).toHaveClass("wr-warn");
    expect(within(r3).getByText("공식 기준정보 파일 2026-09-27(51일 전 · 그 뒤 바뀐 상품 정보는 확인 불가)")).not.toHaveClass("wr-warn");
  });

  it("R4 내 보유에 무엇이 겹치나 = 주식별 노출 · 분모 · 기준일 · 후보끼리 중복률과 다른 값(확인 범위 줄은 R3 에 한 번)", () => {
    show(WEEKLY_SELECTED);
    const r4 = screen.getByTestId("wr-r4");
    const ov = rvOf(WEEKLY_SELECTED).overlap!;
    for (const l of ov.lines) expect(r4).toHaveTextContent(l);
    expect(r4).toHaveTextContent(ov.date_line as string);
    expect(r4).toHaveTextContent("내 보유 평가액 기준 노출 — 「ETF 구성종목」 목록의 후보끼리 중복률과 다른 값");
    expect(r4).not.toHaveTextContent(ov.warn_lines[0]);
  });

  it("R5 [비교 상세 →] · [구성종목 보기 →] · [고른 후보 지우기] = 부르는 쪽 함수 · 다시 읽는 동안 막힘", () => {
    const h = show(WEEKLY_SELECTED);
    fireEvent.click(screen.getByRole("button", { name: "비교 상세 →" }));
    fireEvent.click(screen.getByRole("button", { name: "구성종목 보기 →" }));
    fireEvent.click(screen.getByRole("button", { name: "고른 후보 지우기" }));
    expect(h.onCompare).toHaveBeenCalledTimes(1);
    expect(h.onExposure).toHaveBeenCalledTimes(1);
    expect(h.onClear).toHaveBeenCalledTimes(1);
    for (const b of ["비교 상세 →", "구성종목 보기 →", "고른 후보 지우기"]) {
      expect(screen.getByRole("button", { name: b }).className).toContain("btn-md");
    }
    h.unmount();
    show(WEEKLY_SELECTED, true);
    for (const b of ["비교 상세 →", "구성종목 보기 →", "고른 후보 지우기"]) expect(screen.getByRole("button", { name: b })).toBeDisabled();
  });
});

describe("③ — 자료가 부족한 후보도 단독 근거로(AC1)", () => {
  it("공식 기준정보 없음 = '… — 확인 불가'(파일 날짜) · 구성 미수집 = 주요 편입 없이 구성 줄(경고) · R2 · R3 는 그대로", () => {
    const r = clone(WEEKLY_SELECTED);
    const rv = rvOf(r);
    rv.product = { ...rv.product, found: false, index_name: null, index_provider: null, market: null, asset: null, multiple: null, replication: null, fee_pct: null, missing_reason: "공식 기준정보에 없음" };
    rv.constituents = {
      ...rv.constituents,
      state: "not_collected",
      state_label: "미수집",
      asof: null,
      stored_rows: 0,
      stock_rows: 0,
      other_rows: [],
      top_n: null,
      top_stocks: [],
      top3_sum_pct: null,
      line: "구성 자료 없음(미수집) — [구성종목 보기]에서 수집",
    };
    show(r);
    const r1 = screen.getByTestId("wr-r1");
    expect(within(r1).getByText(/^공식 기준정보에 없음 — 공식 기초지수 · 투자 대상 · 상품 구조 확인 불가/)).toHaveClass("wr-warn");
    expect(r1).toHaveTextContent("(KRX 공식 기준정보 2026-09-27 파일)");
    expect(r1).not.toHaveTextContent("주요 편입");
    expect(within(r1).getByText("구성 자료 없음(미수집) — [구성종목 보기]에서 수집")).toHaveClass("wr-warn");
    expect(screen.getByTestId("wr-r2")).toHaveTextContent("올랐고 국내시장보다 22.80%p 높음");
    expect(screen.getByTestId("wr-r3")).toBeInTheDocument();
  });

  it("보유 없음 · 계산 실패 = R4 에 그 사유 줄(경고 · 후보끼리 중복률 줄 없음) · R1 ~ R3 는 보임", () => {
    const r = clone(WEEKLY_SELECTED);
    const rv = rvOf(r);
    rv.overlap = { ...rv.overlap!, state: "no_holdings", warn_lines: ["등록 보유 없음 — 내 보유 노출을 계산할 대상이 없습니다"], lines: [], date_line: null, numbers: null };
    show(r);
    const r4 = screen.getByTestId("wr-r4");
    expect(within(r4).getByText("등록 보유 없음 — 내 보유 노출을 계산할 대상이 없습니다")).toHaveClass("wr-warn");
    expect(r4).not.toHaveTextContent("후보끼리 중복률");
    expect(screen.getByTestId("wr-r1")).toHaveTextContent("공식 기초지수");
    expect(screen.getByTestId("wr-r2")).toHaveTextContent("1개월");
  });

  it("고른 후보가 목록에서 사라짐 = 경고 줄 + 고르기 전", () => {
    show({ ...clone(WEEKLY_NONE), selected_missing: true });
    expect(screen.getByTestId("wr-review")).toHaveTextContent("고른 후보가 지금 목록에 없습니다(자료가 바뀜) — 위 표에서 다시 고르세요.");
    expect(screen.getByTestId("wr-review")).toHaveTextContent("고르기 전");
  });
});

describe("③ [판단 근거 보기] — 이 자리에서 펼침 · 자체 넘기기 숨김 · 주간 목록 대조 요청", () => {
  it("펼치면 기존 미리보기 카드 · 생성 요청 = 주간 화면 · 1개월 상위 · 제외 4종 · 순위 · 실제 기간 · 끝일 가격 상태 · 1개월 값 · 6개월 시장 흐름", async () => {
    show(WEEKLY_SELECTED);
    expect(screen.queryByTestId("wr-preview")).toBeNull();
    const toggle = screen.getByRole("button", { name: /판단 근거 보기/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    const box = screen.getByTestId("wr-preview");
    expect(box).toHaveTextContent("대상: KODEX 글로벌비만치료제TOP2 Plus (후보)");
    expect(screen.getByRole("button", { name: /판단 근거 접기/ })).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(within(box).getByRole("button", { name: /판단 근거 미리보기 생성/ }));
    await waitFor(() => expect(pending.length).toBe(1));
    expect(pending[0].url).toContain("/decision-draft/preview");
    expect(pending[0].body).toEqual({
      target_kind: "candidate",
      ticker: "476070",
      list_source: "common_period",
      screen: "today_weekly_review",
      basis: "one_month",
      exclude_inverse: true,
      exclude_leveraged: true,
      exclude_synthetic: true,
      exclude_futures: true,
      side: "top",
      rank: 2,
      start_date: "2026-10-19",
      end_date: "2026-11-16",
      end_price_state: "after_close",
      basis_value: 11.7735,
      flow_period: "6M",
    });
    await act(async () =>
      pending[0].resolve({ status: "ok", target_kind: "candidate", ticker: "476070", preview_text: "[대상]\n- 합성 미리보기", generated_at: "2026-11-17T10:00:00+09:00" }),
    );
    await screen.findByText("- 합성 미리보기");
    // 자체 [AI 세션에서 검토]는 이 화면에서 숨김(넘기기는 주간 버튼 줄 하나)
    expect(within(box).queryByRole("button", { name: "AI 세션에서 검토" })).toBeNull();
    expect(within(box).getByRole("button", { name: "복사" })).toBeInTheDocument();
  });

  it("다시 읽는 동안은 펼친 미리보기를 내리고 단추를 막는다 · 고른 후보가 바뀌면 접힌 채 처음부터", () => {
    const { rerender } = render(<WeeklyCandidateReview r={WEEKLY_SELECTED} busy={false} onClear={vi.fn()} onCompare={vi.fn()} onExposure={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /판단 근거 보기/ }));
    expect(screen.getByTestId("wr-preview")).toBeInTheDocument();
    rerender(<WeeklyCandidateReview r={WEEKLY_SELECTED} busy onClear={vi.fn()} onCompare={vi.fn()} onExposure={vi.fn()} />);
    expect(screen.queryByTestId("wr-preview")).toBeNull();
    expect(screen.getByRole("button", { name: /판단 근거 접기/ })).toBeDisabled();
    const other = clone(WEEKLY_SELECTED);
    Object.assign(rvOf(other), { ticker: "428560", name: "KODEX 미국ETF산업Top10 Indxx", rank: 1 });
    rerender(<WeeklyCandidateReview r={other} busy={false} onClear={vi.fn()} onCompare={vi.fn()} onExposure={vi.fn()} />);
    expect(screen.getByRole("button", { name: /판단 근거 보기/ })).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByTestId("wr-preview")).toBeNull();
  });

  it("요청 대조 칸은 묶음 안 ETF 에서도 그 ETF 값(대표 값이 아님) · 목록에 없으면 null", () => {
    const q = weeklyPreviewQuery(WEEKLY_NONE, "453870");
    expect(q).toMatchObject({ rank: 4, start_date: "2026-10-19", end_date: "2026-11-16", basis_value: 10.7957, screen: "today_weekly_review" });
    expect(weeklyPreviewQuery(WEEKLY_NONE, "999999")).toBeNull();
  });
});

describe("화면 도우미 — 기간 다름 · 총보수", () => {
  it("기간 다름 값은 '확인 불가'가 아니라 값 + 실제 기간 · 묶음 1개월은 기간 다름이 섞이면 범위로 묶지 않음", () => {
    const r = clone(WEEKLY_NONE);
    const g = r.flows[2];
    const [a, b] = g.members;
    b.periods.one_month = { status: "period_differs", start: "2026-10-20", end: "2026-11-16" };
    b.three_month = 1.5;
    b.periods.three_month = { status: "period_differs", start: "2026-08-25", end: "2026-11-16" };
    expect(memberPeriodText(b, "three_month")).toBe("+1.50% · 기간 다름(8/25 → 11/16)");
    expect(memberPeriodText(a, "three_month")).toBe("+0.01%");
    expect(oneMonthText(g)).toBe("+10.80% · +10.80% · 기간 다름(10/20 → 11/16)");
    expect(threeMonthText(g)).toBe("+0.01% · +1.50% · 기간 다름(8/25 → 11/16)");
    a.one_month = null;
    a.periods.one_month = { status: "missing", start: null, end: null };
    expect(memberPeriodText(a, "one_month")).toBe("확인 불가");
  });

  it("총보수 = CSV 글자 '0.450000' → '0.45%' · 숫자가 아니면 그대로 · 비면 확인 불가", () => {
    expect(feeText("0.450000")).toBe("0.45%");
    expect(feeText("0.0099")).toBe("0.0099%");
    expect(feeText("연 0.45")).toBe("연 0.45");
    expect(feeText("")).toBe("확인 불가");
    expect(feeText(null)).toBe("확인 불가");
  });
});
