// POC6-32 V2(판정 §3 · Q9 (a) 보완 · PLAN S6 · §9 I-9 · I-10 · I-22) — 「ETF 구성종목」 한 ETF 모드 · 목록 모드 머리 ·
// 설명 띠 · 보유 겹침 카드의 비교 기준(서버 상위 목록 · 실제 기간) · 상태 글자 한국어.
//
// 조회는 모두 가짜(vi.fn) — 운영 자료 · 네트워크를 쓰지 않는다. 이름은 가상 이름.
import { StrictMode } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

const fetchConstituentsAnalysis = vi.fn();
const fetchConstituentsSummary = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<Record<string, unknown>>()),
  fetchConstituentsAnalysis: (...a: unknown[]) => fetchConstituentsAnalysis(...a),
  fetchConstituentsSummary: (...a: unknown[]) => fetchConstituentsSummary(...a),
  fetchHoldingsMarketEvidence: (...a: unknown[]) => fetchHoldingsMarketEvidence(...a),
}));
const fetchConstituentsCrossFamily = vi.fn();
const fetchConstituentsCollectStatus = vi.fn();
const postConstituentsCollect = vi.fn();
vi.mock("@/lib/api/constituentsStatus", async (orig) => ({
  ...(await orig<Record<string, unknown>>()),
  fetchConstituentsCrossFamily: (...a: unknown[]) => fetchConstituentsCrossFamily(...a),
  fetchConstituentsCollectStatus: (...a: unknown[]) => fetchConstituentsCollectStatus(...a),
  postConstituentsCollect: (...a: unknown[]) => postConstituentsCollect(...a),
}));

import ETFExposureView, { listHeadText, presetConditionText } from "./ETFExposureView";
import HoldingsOverlapBridgeCard, { BRIDGE_STATE_TEXT, topnBasisText, type BridgeState } from "./HoldingsOverlapBridgeCard";
import { presetExposureSingle, takeExposureSingle } from "@/lib/detailNav";
import { loadETFExposureDraft, saveETFExposureDraft, type ETFExposureDraft } from "@/lib/etfExposureDraft";
import type { HoldingsMarketEvidenceResponse, HoldingsTopnBasis } from "@/lib/api";

const LINE_FULL = "구성 기준일 11/16 · 저장 3행(주식 2 · 원화현금 1) · 전체 확인(원천 항목 3개를 모두 받음)";

function summary(p: Record<string, unknown> = {}) {
  return {
    status: "ok",
    message: null,
    ticker: "T00001",
    name: "가상 비만치료 ETF",
    state: "full",
    state_label: "전체 확인",
    asof: "2026-11-16",
    stored_rows: 3,
    stocks_known: true,
    stock_rows: 2,
    other_rows: [{ label: "원화현금", count: 1 }],
    top_n: 3,
    top_stocks: [
      { name: "가상 제약 A", weight_pct: 30.07 },
      { name: "가상 제약 B", weight_pct: 20.9 },
    ],
    top3_sum_pct: 50.97,
    rows: [
      { rank: 1, name: "가상 제약 A", weight_pct: 30.07, is_stock: true, kind_label: "해외 주식" },
      { rank: 2, name: "가상 제약 B", weight_pct: 20.9, is_stock: true, kind_label: "해외 주식" },
      { rank: 3, name: "원화현금", weight_pct: 0.15, is_stock: false, kind_label: "원화현금" },
    ],
    concentration: { top1_weight_pct: 30.07, top3_weight_pct: 51.12, top5_weight_pct: 51.12, top10_weight_pct: 51.12 },
    line: LINE_FULL,
    ...p,
  };
}

const NOT_COLLECTED = summary({
  state: "not_collected",
  state_label: "미수집",
  asof: null,
  stored_rows: 0,
  stock_rows: 0,
  other_rows: [],
  top_n: null,
  top_stocks: [],
  top3_sum_pct: null,
  rows: [],
  concentration: { top1_weight_pct: null, top3_weight_pct: null, top5_weight_pct: null, top10_weight_pct: null },
  line: "구성 자료 없음(미수집) — [구성종목 보기]에서 수집",
});

function listDraft(p: Partial<ETFExposureDraft> = {}): ETFExposureDraft {
  return {
    asof: "2026-11-13",
    filters: {} as never,
    candidate_snapshot: [{ ticker: "T00009", name: "가상 목록 ETF", one_month_return_pct: 3.1, tags: [] } as never],
    market_candidates: [],
    draft_created_at: "2026-11-16T00:00:00Z",
    list_scope: "「후보리스트」 1개월 상위 1개(선정 순서) · 10/14 → 11/13 · 인버스 · 레버리지 · 합성 · 선물 제외",
    list_condition: {
      basis: "one_month",
      side: "top",
      start: "2026-10-14",
      end: "2026-11-13",
      filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
    },
    ...p,
  };
}

const sendOne = (p: Record<string, unknown> = {}) =>
  presetExposureSingle({ ticker: "T00001", name: "가상 비만치료 ETF", from: "「주간 ETF 점검」", ...p });

beforeEach(() => {
  window.sessionStorage.clear();
  takeExposureSingle(); // 앞 시험이 남긴 한 번 넘김 비움
  for (const f of [
    fetchConstituentsAnalysis,
    fetchConstituentsSummary,
    fetchHoldingsMarketEvidence,
    fetchConstituentsCrossFamily,
    fetchConstituentsCollectStatus,
    postConstituentsCollect,
  ])
    f.mockReset();
  fetchConstituentsSummary.mockResolvedValue(summary());
  fetchConstituentsCollectStatus.mockResolvedValue({ state: "idle", job_id: null, items: [] });
  fetchConstituentsAnalysis.mockResolvedValue({
    status: "ok",
    asof: "2026-11-13",
    top_k: 30,
    overlap_top_k: 10,
    coverage: { requested_count: 1, available_count: 0, unavailable_count: 1 },
    constituents: [],
    overlap_matrix: [],
    repeated_core_holdings: [],
  });
  fetchConstituentsCrossFamily.mockResolvedValue({ status: "no_data", scope: null, stocks: [], reference: [] });
});

describe("한 ETF 모드(PLAN S6) — [구성종목 보기]로 넘긴 ETF 하나", () => {
  it("넘긴 ETF 하나만 저장 자료로 읽음 · 열 때 수집 없음 · 목록 초안은 읽지도 바꾸지도 않음 · 목록 화면 부품 없음", async () => {
    saveETFExposureDraft(listDraft());
    const before = JSON.stringify(loadETFExposureDraft());
    sendOne();
    const { container } = render(<ETFExposureView onNavigate={vi.fn()} />);
    await screen.findByTestId("single-line");
    expect(fetchConstituentsSummary).toHaveBeenCalledTimes(1);
    expect(fetchConstituentsSummary).toHaveBeenCalledWith("T00001");
    expect(fetchConstituentsAnalysis).not.toHaveBeenCalled();
    expect(fetchConstituentsCrossFamily).not.toHaveBeenCalled();
    // 수집 상태는 그 ETF 하나로 읽기만(열 때 수집 시작 없음)
    await waitFor(() => expect(fetchConstituentsCollectStatus).toHaveBeenCalledWith(["T00001"]));
    expect(postConstituentsCollect).not.toHaveBeenCalled();
    expect(JSON.stringify(loadETFExposureDraft())).toBe(before);
    expect(takeExposureSingle()).toBeNull(); // 한 번 꺼내면 비움

    expect(screen.getByTestId("exposure-single-head").textContent).toBe(
      "「주간 ETF 점검」에서 고른 ETF 하나를 보여 줍니다 · 저장 자료를 먼저 읽고 수집은 [구성종목 수집]을 누를 때만(이 ETF 하나)",
    );
    const head = container.querySelector(".ec-head") as HTMLElement;
    expect(within(head).getAllByRole("button").map((b) => b.textContent)).toEqual(["구성종목 수집"]);
    expect(within(head).getByRole("button", { name: "구성종목 수집" }).className).toBe("wb-btn btn-md");
    // 목록 탭 · 보유 겹침 카드 · AI 넘기기 · NAV 카드 · 고른 후보 줄 없음
    expect(container.querySelector(".decision-tab-row")).toBeNull();
    expect(screen.queryByTestId("exposure-bridge-load")).toBeNull();
    expect(screen.queryByTestId("exposure-to-ai")).toBeNull();
    expect(screen.queryByTestId("exposure-picked")).toBeNull();
    expect(screen.queryByText("NAV / 괴리율 상태")).toBeNull();
    expect(screen.queryByRole("button", { name: "후보로 고르기" })).toBeNull();

    // 구성 표 · 구성 기준일 · 저장 행 수 · 상태 · 기존 집중(Top 1 · 3 · 5 · 10 · 주식 아닌 행 포함 · I-10)
    expect(screen.getByTestId("single-head").textContent).toContain("가상 비만치료 ETF");
    expect(screen.getByTestId("single-state").textContent).toBe("전체 확인");
    expect(screen.getByTestId("single-line").textContent).toBe(LINE_FULL);
    expect(screen.getByTestId("single-conc").textContent).toBe(
      "집중(저장 행 비중 상위 합 · 현금 등 주식 아닌 행 포함): Top 1 30.07% · Top 3 51.12% · Top 5 51.12% · Top 10 51.12%",
    );
    const trs = within(screen.getByTestId("single-table")).getAllByRole("row").slice(1);
    expect(trs.map((r) => Array.from(r.querySelectorAll("td")).map((td) => td.textContent))).toEqual([
      ["1", "가상 제약 A", "해외 주식", "30.07%"],
      ["2", "가상 제약 B", "해외 주식", "20.90%"],
      ["3", "원화현금", "원화현금", "0.15%"],
    ]);
    // 설명 띠 = 한 ETF 보기(낡은 문구 없음)
    const role = screen.getByTestId("exposure-role").textContent ?? "";
    expect(role).toContain("한 ETF 보기");
    expect(role).not.toMatch(/ML|위험 감지|STEP/);
    // 제목 → 수집 상태 · 설명 → 설명 띠 → 구성 카드
    const before2 = (a: Element, b: Element) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
    expect(
      before2(head, screen.getByTestId("exposure-top")) &&
        before2(screen.getByTestId("exposure-top"), screen.getByTestId("exposure-role")) &&
        before2(screen.getByTestId("exposure-role"), screen.getByTestId("single-card")),
    ).toBe(true);
  });

  it.each([
    ["원천 기준일 미확인", summary({ state: "source_unconfirmed", state_label: "원천 기준일 미확인" }), "원천 기준일 미확인"],
    ["상위 N행만 확인", summary({ state: "top_rows", state_label: "상위 30행만 확인" }), "상위 30행만 확인"],
    ["전체 확인", summary(), "전체 확인"],
  ])("상태 %s — 배지 = 서버 상태 이름 · 구성 표를 보인다", async (_n, resp, label) => {
    fetchConstituentsSummary.mockResolvedValue(resp);
    sendOne();
    render(<ETFExposureView onNavigate={vi.fn()} />);
    expect((await screen.findByTestId("single-state")).textContent).toBe(label);
    expect(screen.getByTestId("single-table")).toBeTruthy();
    expect(screen.queryByTestId("single-read-error")).toBeNull();
  });

  it("미수집 — 배지 '미수집' · 표 없음 · 이 ETF 하나만 [구성종목 수집]으로 받는다는 안내", async () => {
    fetchConstituentsSummary.mockResolvedValue(NOT_COLLECTED);
    sendOne();
    render(<ETFExposureView onNavigate={vi.fn()} />);
    expect((await screen.findByTestId("single-state")).textContent).toBe("미수집");
    expect(screen.getByTestId("single-line").textContent).toBe(
      "저장된 구성 자료가 없습니다(미수집) — 위 [구성종목 수집]을 누르면 이 ETF 하나만 받습니다(화면을 열 때는 받지 않음).",
    );
    expect(screen.queryByTestId("single-table")).toBeNull();
  });

  it.each([
    ["서버 읽기 실패(error)", () => fetchConstituentsSummary.mockResolvedValue(summary({ status: "error", state: "error", state_label: "구성 자료를 읽지 못함", rows: [], message: "구성 자료를 읽지 못함 — …" })), "구성 자료를 읽지 못했습니다(구성이 없다는 뜻이 아님) — 화면을 다시 열면 다시 읽습니다."],
    ["시장 자료 파일 없음(missing)", () => fetchConstituentsSummary.mockResolvedValue({ status: "missing", message: "x", ticker: "T00001", name: null }), "시장 자료 파일이 없어 구성 자료를 읽지 못했습니다(구성이 없다는 뜻이 아님)."],
    ["요청 실패", () => fetchConstituentsSummary.mockRejectedValue(new Error("요청 실패(HTTP 500)")), "구성 자료를 읽지 못했습니다(구성이 없다는 뜻이 아님) — 요청 실패(HTTP 500)"],
  ])("%s — '미수집'으로 바꾸지 않고 '읽지 못함'으로 알린다", async (_n, prime, text) => {
    prime();
    sendOne();
    render(<ETFExposureView onNavigate={vi.fn()} />);
    expect((await screen.findByTestId("single-read-error")).textContent).toBe(text);
    expect(screen.queryByTestId("single-state")).toBeNull();
    expect(screen.getByTestId("single-card").textContent).not.toContain("미수집");
  });

  it("[구성종목 수집] = 그 ETF 하나만 서버 작업 · 끝나면 그 ETF 구성을 다시 읽음 · 상태 문장은 'ETF 1개'", async () => {
    fetchConstituentsSummary.mockResolvedValueOnce(NOT_COLLECTED).mockResolvedValue(summary());
    const job = { job_id: "j", kind: "candidates", tickers: ["T00001"], target_date: "2026-11-16", total: 1, items: [] };
    postConstituentsCollect.mockResolvedValue({ ...job, state: "running", done: 0 });
    fetchConstituentsCollectStatus
      .mockResolvedValueOnce({ state: "idle", job_id: null, items: [] }) // 화면 열 때
      .mockResolvedValue({ ...job, state: "done", done: 1, counts: { existing: 0, fetched: 1 }, calls: 1 });
    sendOne();
    render(<ETFExposureView onNavigate={vi.fn()} />);
    expect((await screen.findByTestId("single-state")).textContent).toBe("미수집");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "구성종목 수집" }));
    });
    expect(postConstituentsCollect).toHaveBeenCalledWith(["T00001"]);
    await waitFor(() => expect(fetchConstituentsSummary).toHaveBeenCalledTimes(2), { timeout: 4000 });
    await waitFor(() => expect(screen.getByTestId("single-state").textContent).toBe("전체 확인"));
    expect(screen.getByTestId("cst-collect-line").textContent).toBe(
      "수집 끝 — 목표일 11/16 · ETF 1개 · 기존 자료 0 · 새로 받음 1 · 실제 호출 1회",
    );
    expect(fetchConstituentsAnalysis).not.toHaveBeenCalled();
  });

  it("다른 목록 수집이 도는 중이면 'ETF' 기준 안내 · 버튼 막힘", async () => {
    fetchConstituentsCollectStatus.mockResolvedValue({
      state: "idle",
      job_id: null,
      stored: true,
      target_date: "2026-11-16",
      total: 1,
      needs_check: 1,
      counts: { not_checked: 1 },
      items: [],
      other_job: { total: 30, done: 4, started_at: "t" },
    });
    sendOne();
    render(<ETFExposureView onNavigate={vi.fn()} />);
    expect((await screen.findByTestId("cst-other-list")).textContent).toBe(
      "다른 목록(30개)을 받는 중(4개 끝) — 끝난 뒤 이 ETF의 [구성종목 수집]을 누르세요",
    );
    expect((screen.getByRole("button", { name: "구성종목 수집" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByTestId("cst-collect-line").textContent).toContain("ETF 1개");
  });

  it("Strict Mode(초기값 두 번 호출)에서도 한 ETF 모드 · 보낸 화면의 목록 조건을 머리에 적는다", async () => {
    sendOne({
      from: "후보리스트",
      condition: {
        basis: "one_month",
        side: "top",
        start: "2026-10-19",
        end: "2026-11-16",
        filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
      },
    });
    render(
      <StrictMode>
        <ETFExposureView onNavigate={vi.fn()} />
      </StrictMode>,
    );
    expect(await screen.findByTestId("exposure-single")).toBeTruthy();
    await waitFor(() => expect(fetchConstituentsSummary).toHaveBeenCalledWith("T00001"));
    expect(screen.getByTestId("exposure-single-head").textContent).toContain("「후보리스트」에서 고른 ETF 하나를 보여 줍니다");
    expect(screen.getByTestId("exposure-single-cond").textContent).toBe(
      "보낸 화면의 목록: 1개월 상위 · 10/19 → 11/16 · 인버스 · 레버리지 · 합성 · 선물 제외 · 아래 구성 기준일은 그 기간과 따로 저장된 구성의 날짜입니다",
    );
    expect(fetchConstituentsAnalysis).not.toHaveBeenCalled();
  });

  it("한 번 넘김 — 다음에 다시 그리면(넘김 없음) 목록 모드(초안)로 연다", async () => {
    saveETFExposureDraft(listDraft());
    sendOne();
    const first = render(<ETFExposureView onNavigate={vi.fn()} />);
    await screen.findByTestId("single-line");
    first.unmount();
    render(<ETFExposureView onNavigate={vi.fn()} />);
    await waitFor(() => expect(fetchConstituentsAnalysis).toHaveBeenCalledWith(["T00009"], null, 30));
    expect(screen.queryByTestId("exposure-single")).toBeNull();
    expect(screen.getByTestId("exposure-list-head")).toBeTruthy();
  });

  it("presetConditionText — 모양이 다르면 쓰지 않음(지어 내지 않음)", () => {
    expect(presetConditionText(null)).toBeNull();
    expect(presetConditionText("x")).toBeNull();
    expect(presetConditionText({ basis: "weird" })).toBeNull();
    expect(presetConditionText({ basis: "three_month" })).toBe("3개월");
  });
});

describe("목록 모드 머리 · 설명 띠(PLAN S6 — 넘겨받은 목록 · 낡은 문구 고침)", () => {
  it("넘겨받은 목록(조건 · 기간 · 개수)과 이 화면이 보이는 것 · 'ML / 위험 감지' · 'STEP 2' 없음", async () => {
    saveETFExposureDraft(listDraft());
    render(<ETFExposureView onNavigate={vi.fn()} />);
    await waitFor(() => expect(fetchConstituentsAnalysis).toHaveBeenCalled());
    expect(screen.getByTestId("exposure-list-head").textContent).toBe(
      "넘겨받은 목록: 「후보리스트」 1개월 상위 1개(선정 순서) · 10/14 → 11/13 · 인버스 · 레버리지 · 합성 · 선물 제외 · 대상 1개 · 아래 = 그 ETF 들의 저장 구성(ETF 마다 구성일)과 후보끼리 중복률",
    );
    const role = screen.getByTestId("exposure-role").textContent ?? "";
    expect(role).toContain("목록 보기");
    expect(role).not.toMatch(/ML|위험 감지|STEP|먼저 실행/);
    expect(fetchConstituentsSummary).not.toHaveBeenCalled();
  });

  it("예전 초안 — 범위 글이 없으면 조건 칸으로 · 조건도 없으면 개수와 기준일", () => {
    expect(listHeadText(listDraft({ list_scope: undefined }))).toBe(
      "넘겨받은 목록: 1개월 상위 · 10/14 → 11/13 · 인버스 · 레버리지 · 합성 · 선물 제외 · 대상 1개 · 아래 = 그 ETF 들의 저장 구성(ETF 마다 구성일)과 후보끼리 중복률",
    );
    expect(listHeadText(listDraft({ list_scope: undefined, list_condition: undefined }))).toBe(
      "넘겨받은 후보 1개 · 목록 기준일 11/13 · 대상 1개 · 아래 = 그 ETF 들의 저장 구성(ETF 마다 구성일)과 후보끼리 중복률",
    );
  });

  it("넘겨받은 목록도 한 ETF 도 없으면 두 길을 안내(낡은 '먼저 실행' 문구 없음)", async () => {
    render(<ETFExposureView onNavigate={vi.fn()} />);
    const msg = await screen.findByText(/넘겨받은 목록이 없습니다/);
    expect(msg.textContent).toBe(
      "넘겨받은 목록이 없습니다. 목록은 「후보리스트」 [이 목록을 ETF 구성종목에서 보기]로 넘기고, ETF 하나는 「주간 ETF 점검」 ③ 또는 「후보리스트」 · 「섹터요약」 행 상세의 [구성종목 보기]로 엽니다.",
    );
    expect(fetchConstituentsAnalysis).not.toHaveBeenCalled();
    expect(fetchConstituentsSummary).not.toHaveBeenCalled();
  });
});

describe("보유 겹침 카드(판정 Q9 · §9 I-22) — 서버 상위 목록 기준 · 실제 기간 · 상태 글자 한국어", () => {
  const basis = (p: Partial<HoldingsTopnBasis> = {}): HoldingsTopnBasis => ({
    basis: "one_month",
    n: 10,
    count: 10,
    filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
    start_min: "2026-10-16",
    start_max: "2026-10-17",
    end: "2026-11-16",
    ...p,
  });
  const ev = (tb: HoldingsTopnBasis | null | undefined) =>
    ({
      status: "ok",
      asof: "2026-11-16",
      holdings_asof: null,
      market_asof: "2026-11-16",
      market_context: null,
      summary: { total_holdings_count: 1, matched_topn_count: 0, constituents_available_count: 1, nav_discount_unavailable_count: 0 },
      holdings: [
        {
          ticker: "H00001",
          name: "가상 보유 ETF",
          account_group: null,
          constituents_overlap: { status: "ok", overlap_with_market_core: [] },
        },
      ],
      warnings: [],
      ...(tb === undefined ? {} : { topn_basis: tb }),
    }) as unknown as HoldingsMarketEvidenceResponse;

  it("비교 기준 = '1개월 상위 10개 기준 · 시작 최소~최대 → 끝' · 행 배지는 넘겨받은 목록 기준이라고 밝힘", () => {
    render(
      <HoldingsOverlapBridgeCard state="ok" data={ev(basis())} errorMessage={null} candidateTickers={["H00001"]} repeatedCoreTickers={[]} onLoad={vi.fn()} />,
    );
    expect(screen.getByTestId("bridge-basis").textContent).toBe(
      "비교 기준: 1개월 상위 10개 기준 · 시작 10/16~10/17 → 끝 11/16 · 인버스 · 레버리지 · 합성 · 선물 제외 · 행의 '넘겨받은 목록에 있음/없음' · '반복 핵심 종목'은 넘겨받은 목록 기준",
    );
    expect(screen.getByText("넘겨받은 목록에 있음")).toBeTruthy();
    expect(screen.getByTestId("bridge-state").textContent).toBe("읽음");
    expect(document.body.textContent).not.toContain("이 목록 ETF");
    expect(document.body.textContent).toContain("상위 목록에 든 보유");
  });

  it.each([
    [basis({ start_max: "2026-10-16" }), "1개월 상위 10개 기준 · 시작 10/16 → 끝 11/16 · 인버스 · 레버리지 · 합성 · 선물 제외"],
    [basis({ count: 8 }), "1개월 상위 10개 기준(실제 8개) · 시작 10/16~10/17 → 끝 11/16 · 인버스 · 레버리지 · 합성 · 선물 제외"],
    [basis({ start_min: null, start_max: null, count: 0, filters: null }), "1개월 상위 10개 기준(실제 0개) · 실제 기간 확인 불가"],
    [null, "비교 기준 · 기간을 응답에서 읽지 못함"],
    [undefined, "비교 기준 · 기간을 응답에서 읽지 못함"],
  ])("기준 문장 %# — 같은 시작 · 실제 개수 · 날짜 없음 · 칸 없음(예전 서버)", (tb, text) => {
    expect(topnBasisText(tb)).toBe(text);
  });

  it.each(["ok", "unavailable", "loading", "not_loaded"] as BridgeState[])("상태 '%s' 는 한국어 글자로만 보인다", (st) => {
    render(
      <HoldingsOverlapBridgeCard state={st} data={st === "ok" ? ev(basis()) : null} errorMessage={null} candidateTickers={[]} repeatedCoreTickers={[]} onLoad={vi.fn()} />,
    );
    const badge = screen.getByTestId("bridge-state");
    expect(badge.textContent).toBe(BRIDGE_STATE_TEXT[st]);
    expect(badge.textContent).not.toMatch(/[A-Za-z_]/);
  });

  it("목록 모드에서 [보유 ETF 겹침 불러오기] → 카드에 비교 기준 줄", async () => {
    saveETFExposureDraft(listDraft());
    fetchHoldingsMarketEvidence.mockResolvedValue(ev(basis()));
    render(<ETFExposureView onNavigate={vi.fn()} />);
    fireEvent.click(screen.getByTestId("exposure-bridge-load"));
    expect((await screen.findByTestId("bridge-basis")).textContent).toContain("1개월 상위 10개 기준 · 시작 10/16~10/17 → 끝 11/16");
    expect(fetchHoldingsMarketEvidence).toHaveBeenCalledTimes(1);
  });
});
