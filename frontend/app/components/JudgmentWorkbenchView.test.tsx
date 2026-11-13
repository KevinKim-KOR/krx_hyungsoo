// 「ETF보유 및 후보 선정 › 후보리스트」 화면 계약(POC3-02 Workbench → POC6-28 「후보」 → POC6-29 · PLAN 판정 2026-11-12).
// 요약 API · 상세 수치 API · 가격 시계열 · 시장 흐름을 가짜로 바꿔 응답을 통제한다. 실제 네트워크 · 운영 자료 미의존.
// POC6-28 [ETF 순위] 시험(같은 목록 안 표시 순서 · 0.00% 와 값 없음 구분 · 상·하위 공통 · 결측 정직성)을 옮겼고,
// POC6-29 의 이 화면 조건 · [목록 | 표] · 행 상세 수치 · 판단 근거 요청 · 목록 넘기기를 더했다.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import { __resetEtfCompareCondition, getScreenCondition } from "@/lib/etfCompareCondition";
import { detailItem, detailResponse, group, link, period, row, summaryOk } from "@/lib/etfCompareTestFixtures";
import { loadAISessionsDraft } from "@/lib/aiSessionsDraft";
import { render as renderEl } from "@testing-library/react";
import { loadETFExposureDraft } from "@/lib/etfExposureDraft";
import { buildMarketDiscoveryCopyText } from "@/lib/marketDiscoveryCopyText";
import NavDiscountPlaceholderCard from "./NavDiscountPlaceholderCard";

const fetchEtfCompareSummary = vi.fn();
const fetchPriceSeries = vi.fn();
const fetchEtfDetail = vi.fn();
const postDecisionDraftPreview = vi.fn();
const fetchMarketFlowContext = vi.fn();

vi.mock("@/lib/api/etfCompare", async (orig) => ({
  ...(await orig<typeof import("@/lib/api/etfCompare")>()),
  fetchEtfCompareSummary: (...a: unknown[]) => fetchEtfCompareSummary(...a),
}));
vi.mock("@/lib/api/etfDetail", async (orig) => ({
  ...(await orig<typeof import("@/lib/api/etfDetail")>()),
  fetchEtfDetail: (...a: unknown[]) => fetchEtfDetail(...a),
}));
vi.mock("@/lib/api/marketFlow", async (orig) => ({
  ...(await orig<typeof import("@/lib/api/marketFlow")>()),
  fetchMarketFlowContext: (...a: unknown[]) => fetchMarketFlowContext(...a),
}));
vi.mock("@/lib/api", () => ({
  fetchPriceSeries: (...a: unknown[]) => fetchPriceSeries(...a),
  postDecisionDraftPreview: (...a: unknown[]) => postDecisionDraftPreview(...a),
}));

import JudgmentWorkbenchView from "./JudgmentWorkbenchView";
import { priceSeriesKey } from "./workbench/PriceChart";
import { ETF_DETAIL_KEY_PREFIX, PRICE_SERIES_KEY_PREFIX } from "@/lib/api/dashboardKeys";
import { etfDetailKey } from "@/lib/api/etfDetail";

const nav = vi.fn();
function renderView() {
  return render(<JudgmentWorkbenchView onNavigate={nav} />);
}

beforeEach(() => {
  __resetQueryCache();
  __resetEtfCompareCondition();
  window.sessionStorage.clear();
  fetchEtfCompareSummary.mockReset();
  fetchPriceSeries.mockReset();
  fetchEtfDetail.mockReset();
  postDecisionDraftPreview.mockReset();
  fetchMarketFlowContext.mockReset();
  nav.mockReset();
  fetchEtfCompareSummary.mockResolvedValue(summaryOk());
  fetchPriceSeries.mockImplementation((t: string) =>
    Promise.resolve({ ticker: t, availability: "AVAILABLE", series: [{ date: "2026-11-09", price: 100 }] }),
  );
  fetchEtfDetail.mockImplementation((ts: string[]) => Promise.resolve(detailResponse(ts)));
  fetchMarketFlowContext.mockRejectedValue(new Error("flow down"));
});

const vals = () => screen.getAllByTestId("ec-rank-val").map((e) => e.textContent);
const names = () => screen.getAllByTestId("ec-rank-row").map((e) => e.textContent ?? "");
const openRow = (i: number) =>
  fireEvent.click(screen.getAllByTestId("ec-rank-row")[i].querySelector("[role='button']") as HTMLElement);

describe("「후보리스트」 첫 화면", () => {
  it("이 화면 조건으로 1회 조회 · 기준 줄 · 가격 · 상세는 조회하지 않는다 · 옛 탭 없음", async () => {
    renderView();
    expect(await screen.findByTestId("ec-ranking")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "후보리스트" })).toBeInTheDocument();
    expect(screen.getByTestId("ec-basis")).toHaveTextContent(
      "1개월 · 10/12 → 11/9 · 인버스 · 레버리지 · 합성 · 선물 제외 · 비교한 ETF 961개 · 기간이 달라 뺀 17개",
    );
    expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(1);
    expect(fetchEtfCompareSummary.mock.calls[0][0]).toEqual(getScreenCondition("candidates"));
    expect(fetchPriceSeries).not.toHaveBeenCalled();
    expect(fetchEtfDetail).not.toHaveBeenCalled();
    expect(fetchMarketFlowContext).not.toHaveBeenCalled();
    expect(screen.queryByRole("tab", { name: "섹터 요약" })).toBeNull();
    expect(screen.queryByText(/참고점수/)).toBeNull();
  });

  it("처음은 선정 순서 · 하위 3 · 3개월 낮은 순 · 높은 순 모두 기간 다름은 뒤 · '1개월 선정 · 3개월 표시 순서'", async () => {
    renderView();
    await screen.findByTestId("ec-ranking");
    expect(screen.getByTestId("ec-sort-line")).toHaveTextContent("1개월 상위 3 · 정렬 선정 순서(1개월 높은 순)");
    fireEvent.click(screen.getByRole("button", { name: "하위 3" }));
    fireEvent.click(screen.getByRole("button", { name: "3개월 수익률" }));
    expect(screen.getByTestId("ec-sort-line")).toHaveTextContent(
      "1개월 하위 3 · 정렬 1개월 선정 · 3개월 수익률 표시 순서(낮은 순) · 8/11 → 11/9 · 비교 가능 2 · 기간 다름 · 값 없음 1(뒤)",
    );
    expect(vals()).toEqual(["-22.46%", "-20.05%", "기간 다름 · 9/15 → 11/9"]);
    fireEvent.click(screen.getByRole("button", { name: /3개월 수익률/ }));
    expect(vals()).toEqual(["-20.05%", "-22.46%", "기간 다름 · 9/15 → 11/9"]);
    expect(names()[0]).toContain("하위 2위");
  });

  it("고점 대비 0.00% 는 값으로 보이고 값 없음은 사유 · KODEX 대비는 같은 순서 안내", async () => {
    renderView();
    await screen.findByTestId("ec-ranking");
    fireEvent.click(screen.getByRole("button", { name: "하위 3" }));
    fireEvent.click(screen.getByRole("button", { name: "최근 고점 대비(20저장일)" }));
    expect(vals()).toEqual(["-10.00%", "0.00%", "값 없음 · 20저장일 부족"]);
    fireEvent.click(screen.getByRole("button", { name: "1개월 KODEX 200 대비" }));
    expect(screen.getByTestId("ec-kodex-note")).toHaveTextContent("같은 1개월 구간(10/12 → 11/9) KODEX 200 -22.64%");
    expect(vals()[0]).toBe("-22.28%p");
  });
});

describe("행 상세 — 상세 수치 · 판단 근거(판정 Q4-1 · Q4-2)", () => {
  it("행을 누르면 그 종목 하나만 상세 수치를 읽는다 · 계산된 0 · 값 없음 · 자료 없음을 구분한다", async () => {
    fetchEtfDetail.mockImplementation((ts: string[]) =>
      Promise.resolve(
        detailResponse(ts, {
          items: ts.map((t) =>
            detailItem(t, {
              m6: period(null, null, null, "missing", "insufficient_history"),
              m12: period(0, "2025-11-10", "2026-11-09"),
              nav: { status: "missing", nav: null, market_price: null, discount_rate_pct: null, flag: null, asof: null },
            }),
          ),
        }),
      ),
    );
    renderView();
    await screen.findByTestId("ec-ranking");
    fireEvent.click(screen.getByRole("button", { name: "하위 3" }));
    const first = screen.getAllByTestId("ec-rank-row")[0];
    expect(first).toHaveTextContent("보유");
    openRow(0);
    const detail = await within(first).findByTestId("ec-etf-detail");
    await waitFor(() => expect(fetchEtfDetail).toHaveBeenCalledTimes(1));
    expect(fetchEtfDetail.mock.calls[0][0]).toHaveLength(1);
    const months = await within(detail).findByTestId("dn-months");
    expect(months).toHaveTextContent("6개월 값 없음 · 저장 이력 부족");
    expect(months).toHaveTextContent("12개월 0.00% (2025-11-10 → 11/9)");
    expect(within(detail).getByTestId("dn-nav")).toHaveTextContent("저장된 자료 없음");
  });

  it("[판단 근거 미리보기 생성] = 이 화면의 공통 기간 목록 · 본 쪽 · 순위 · 날짜 · 가격 시점을 보낸다 · 시장 흐름 6개월 · 어긋나면 서버 안내", async () => {
    postDecisionDraftPreview.mockResolvedValue({ status: "error", message: "목록이 바뀌었습니다 — 목록을 다시 읽고 다시 고르세요." });
    renderView();
    await screen.findByTestId("ec-ranking");
    fireEvent.click(screen.getByRole("button", { name: "하위 3" }));
    const first = screen.getAllByTestId("ec-rank-row")[0];
    openRow(0);
    const detail = await within(first).findByTestId("ec-etf-detail");
    fireEvent.click(within(detail).getByRole("button", { name: "판단 근거 미리보기 생성" }));
    await waitFor(() => expect(postDecisionDraftPreview).toHaveBeenCalledTimes(1));
    const [kind, ticker, q, flowPeriod] = postDecisionDraftPreview.mock.calls[0];
    const r = summaryOk().bottom[0];
    expect(kind).toBe("candidate");
    expect(ticker).toBe(r.ticker);
    expect(q).toMatchObject({
      list_source: "common_period",
      screen: "candidate_list",
      basis: "one_month",
      exclude_inverse: true,
      side: "bottom",
      rank: r.rank,
      start_date: r.basis_return.start,
      end_date: r.basis_return.end,
      end_price_state: r.end_price.state,
      basis_value: r.basis_return.value, // 같은 날 가격만 바뀐 경우도 서버가 대조(검토 지적)
    });
    expect(flowPeriod).toBe("6M");
    expect(await within(detail).findByText("목록이 바뀌었습니다 — 목록을 다시 읽고 다시 고르세요.")).toBeInTheDocument();
  });

  it("[다시 불러오기] = 열린 행을 닫고 요약을 다시 읽는다 · 차트 · 상세 키는 시장 갱신 무효화 앞부분", async () => {
    expect(priceSeriesKey("069500").startsWith(PRICE_SERIES_KEY_PREFIX)).toBe(true);
    expect(etfDetailKey(["069500"]).startsWith(ETF_DETAIL_KEY_PREFIX)).toBe(true);
    renderView();
    await screen.findByTestId("ec-ranking");
    openRow(0);
    await waitFor(() => expect(fetchEtfDetail).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button", { name: "다시 불러오기" }));
    await waitFor(() => expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(2));
    expect(screen.queryByTestId("ec-etf-detail")).toBeNull();
    await screen.findAllByTestId("ec-rank-row");
    openRow(0);
    await waitFor(() => expect(fetchEtfDetail).toHaveBeenCalledTimes(2));
  });
});

describe("[목록 | 표](판정 Q9 · Q4-1)", () => {
  it("[표] = 지금 보는 쪽 전체의 상세를 한 번에 읽는다(선정 순서) · 정렬을 바꿔도 다시 읽지 않는다", async () => {
    renderView();
    await screen.findByTestId("ec-ranking");
    fireEvent.click(screen.getByRole("button", { name: "표" }));
    const table = await screen.findByTestId("ec-rank-table");
    await waitFor(() => expect(fetchEtfDetail).toHaveBeenCalledTimes(1));
    expect(fetchEtfDetail.mock.calls[0][0]).toEqual(summaryOk().top.map((r) => r.ticker));
    await waitFor(() => expect(within(table).getAllByTestId("ec-table-row")[0]).toHaveTextContent("+12.30%"));
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "순위",
      "ETF",
      "선정(1개월)",
      "1개월",
      "3개월",
      "6개월",
      "12개월",
      "20구간 KODEX 200 차이",
      "시장가",
      "기준가(NAV)",
      "괴리율",
      "최근 고점 대비",
    ]);
    fireEvent.click(screen.getByRole("button", { name: "3개월 수익률" }));
    expect(fetchEtfDetail).toHaveBeenCalledTimes(1);
  });
});

describe("「이 목록으로 할 일」(판정 Q5)", () => {
  it("범위 = 고른 쪽 · 선정 순서 · 기간 · 실제 날짜 · 제외 · 건수 · AI 세션 초안에 같은 머리 · 시장 흐름 못 읽음을 적는다", async () => {
    renderView();
    await screen.findByTestId("ec-ranking");
    fireEvent.click(screen.getByRole("button", { name: "하위 3" }));
    const box = screen.getByTestId("ec-transfer");
    expect(within(box).getByTestId("ec-transfer-scope")).toHaveTextContent(
      "넘기는 범위: 1개월 하위 3개(선정 순서) · 10/12 → 11/9 · 인버스 · 레버리지 · 합성 · 선물 제외",
    );
    fireEvent.click(within(box).getByRole("button", { name: "이 목록을 AI 투자 세션으로 넘기기" }));
    await waitFor(() => expect(nav).toHaveBeenCalledWith("ai_sessions"));
    const draft = loadAISessionsDraft();
    expect(draft?.candidate_snapshot.map((c) => c.rank)).toEqual([1, 2, 3]);
    expect(draft?.question_text).toContain("[「후보리스트」 목록 · 1개월 하위 3개(선정 순서) · 10/12 → 11/9");
    expect(draft?.question_text).toContain("넘기는 건수 3개");
    expect(draft?.question_text).toContain("시장 흐름 자료를 불러오지 못해");
  });

  it("「ETF 구성종목」으로 넘기기 = 범위 · 같은 기간 KODEX 200 1 · 3개월(종목 상세) · 질문 글 머리 · NAV 카드 안내(검토 지적)", async () => {
    renderView();
    await screen.findByTestId("ec-ranking");
    fireEvent.click(screen.getByRole("button", { name: "하위 3" }));
    const box = screen.getByTestId("ec-transfer");
    fireEvent.click(within(box).getByRole("button", { name: "이 목록을 ETF 구성종목에서 보기" }));
    await waitFor(() => expect(nav).toHaveBeenCalledWith("etf_exposure"));
    const rows = summaryOk().bottom;
    expect(fetchEtfDetail).toHaveBeenLastCalledWith(rows.map((r) => r.ticker));
    const draft = loadETFExposureDraft();
    expect(draft?.list_scope?.startsWith("「후보리스트」 1개월 하위 3개(선정 순서) · 10/12 → 11/9 · 인버스 · 레버리지 · 합성 · 선물 제외")).toBe(true);
    const c0 = draft?.market_candidates[0];
    expect(c0?.same_period_kodex200?.one_month?.status).toBe("ok");
    expect(c0?.same_period_kodex200?.three_month?.status).toBe("ok");
    expect(c0?.same_period_kodex200?.three_month?.diff_pctp).toBe(10.2);
    const q = buildMarketDiscoveryCopyText({
      asof: draft!.asof,
      filters: draft!.filters,
      candidates: draft!.market_candidates,
      marketContext: null,
      listScope: draft!.list_scope,
    });
    expect(q.split("\n")[0]).toBe(`아래는 한국 상장 ETF 목록입니다 — ${draft!.list_scope}.`);
    expect(q).toContain("[목록 ETF — 선정 순서]");
    expect(q).not.toContain("Market Discovery");
    expect(q).not.toContain("시장 전체 상승에 따라간");
    expect(q).toContain("동일 기간 KODEX200 대비 3개월: +10.20%p");
    // NAV 칸은 넘기지 않는다 — '갱신하면 재수집'이 아니라 볼 곳을 알린다.
    renderEl(<NavDiscountPlaceholderCard candidates={draft!.market_candidates} />);
    expect(screen.getByTestId("nav-not-carried")).toHaveTextContent("「후보리스트」 [표] 또는 행 상세");
    expect(screen.getByTestId("nav-not-carried")).not.toHaveTextContent("최신 자료 갱신");
  });

  it("저장하지 않은 AI 세션 초안이 있으면 바꾸기 전에 묻는다", async () => {
    renderView();
    await screen.findByTestId("ec-ranking");
    const box = screen.getByTestId("ec-transfer");
    fireEvent.click(within(box).getByRole("button", { name: "이 목록을 AI 투자 세션으로 넘기기" }));
    await waitFor(() => expect(nav).toHaveBeenCalledTimes(1));
    fireEvent.click(within(box).getByRole("button", { name: "이 목록을 AI 투자 세션으로 넘기기" }));
    expect(await within(box).findByRole("alert")).toHaveTextContent("저장하지 않은 AI 세션 초안이 있습니다");
    expect(nav).toHaveBeenCalledTimes(1);
  });
});

describe("이 화면의 조회 기준 · 상태", () => {
  it("[조회 기준]에서 3개월 적용 = 이 화면만 다시 조회 · 섹터요약 · 오늘 점검 조건은 그대로", async () => {
    renderView();
    await screen.findByTestId("ec-ranking");
    fireEvent.click(screen.getByRole("button", { name: "조회 기준" }));
    const panel = screen.getByTestId("ec-condition-panel");
    fireEvent.click(within(panel).getByRole("button", { name: "3개월" }));
    fireEvent.click(within(panel).getByRole("button", { name: "적용" }));
    await waitFor(() => expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(2));
    expect(fetchEtfCompareSummary.mock.calls[1][0].basis).toBe("three_month");
    expect(getScreenCondition("candidates").basis).toBe("three_month");
    expect(getScreenCondition("sector").basis).toBe("one_month");
    expect(getScreenCondition("today").basis).toBe("one_month");
  });

  it("장중 저장값이면 가격 줄에 잠정을 밝힌다", async () => {
    const s = summaryOk();
    fetchEtfCompareSummary.mockResolvedValue({
      ...s,
      price_state: {
        ...s.price_state,
        end_date: "2026-11-10",
        intraday_count: 961,
        after_close_count: 0,
        provisional: true,
        intraday_fetched_min: "2026-11-10T13:17:11+09:00",
        intraday_fetched_max: "2026-11-10T13:21:00+09:00",
      },
    });
    renderView();
    expect(await screen.findByTestId("ec-price-state")).toHaveTextContent(
      "장중 저장값 포함 · 잠정(장중 961개 · 11/10 13:17 ~ 13:21 저장)",
    );
  });

  it("공통 기간을 정하지 못하면 사유 · 목록을 만들지 않는다 · 조회 실패는 실패로", async () => {
    fetchEtfCompareSummary.mockResolvedValueOnce({ status: "no_common_period", message: "x", basis: "one_month" });
    const { unmount } = renderView();
    expect(await screen.findByTestId("ec-not-ok")).toHaveTextContent("공통 기간을 정하지 못해");
    expect(screen.queryByTestId("ec-ranking")).toBeNull();
    unmount();
    __resetQueryCache();
    fetchEtfCompareSummary.mockRejectedValueOnce(new Error("down"));
    renderView();
    expect(await screen.findByText(/비교 자료 조회 실패/)).toBeInTheDocument();
  });
});

describe("[검증자 r1 F3] 상·하위에 함께 든 같은 ETF 를 공통으로 구분한다", () => {
  it("상위 · 하위 목록 모두 '상·하위 공통' · 상세 = 상위 1위 · 하위 1위", async () => {
    const x = row({ rank: 1, ticker: "X00001", name: "단일 ETF", value: -3 });
    const g = group([x], { kind: "index", name: "단일 지수" });
    const s = summaryOk();
    fetchEtfCompareSummary.mockResolvedValue({
      ...s,
      top: [x],
      bottom: [x],
      in_both: ["X00001"],
      groups: { top: [g], bottom: [g] },
      counts: { ...s.counts, population: 1, shown_top: 1, shown_bottom: 1 },
      holdings: { status: "ok" as const, items: [link({ ticker: "X00001", side: "bottom", side_rank: 1, top_rank: 1 })] },
    });
    renderView();
    await screen.findByTestId("ec-ranking");
    expect(screen.getAllByTestId("ec-rank-row")[0]).toHaveTextContent("상·하위 공통");
    fireEvent.click(screen.getByRole("button", { name: "하위 1" }));
    const r = screen.getAllByTestId("ec-rank-row")[0];
    expect(r).toHaveTextContent("상·하위 공통");
    openRow(0);
    expect(await within(r).findByTestId("ec-etf-detail")).toHaveTextContent("상위 1위 · 하위 1위(상·하위 공통)");
  });
});
