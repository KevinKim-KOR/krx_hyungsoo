// 「ETF 비교하기 › 후보」 화면 계약(POC3-02 Workbench → POC6-28 개편 · 판정 2026-11-11).
// 요약 API(@/lib/api/etfCompare) · 가격 시계열(@/lib/api) 를 가짜로 바꿔 응답을 통제한다. 실제 네트워크 · 운영 자료 미의존.
// 옛 화면의 탭 · 요약 칸 · 확인 필요 · 후보 카드 목록 시험은 없앤 기능이라 빼고, 개념이 남는 계약(최초 진입에 가격 조회 없음 ·
// 고른 종목만 차트 · 0.00% 와 값 없음 구분 · 참고점수 없음 · 결측 정직성)은 새 구조로 옮겼다.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import { __resetEtfCompareCondition, getEtfCompareCondition } from "@/lib/etfCompareCondition";
import { group, link, row, summaryOk } from "@/lib/etfCompareTestFixtures";

const fetchEtfCompareSummary = vi.fn();
const fetchPriceSeries = vi.fn();

vi.mock("@/lib/api/etfCompare", async (orig) => ({
  ...(await orig<typeof import("@/lib/api/etfCompare")>()),
  fetchEtfCompareSummary: (...a: unknown[]) => fetchEtfCompareSummary(...a),
}));
vi.mock("@/lib/api", () => ({
  fetchPriceSeries: (...a: unknown[]) => fetchPriceSeries(...a),
}));

import JudgmentWorkbenchView from "./JudgmentWorkbenchView";
import { priceSeriesKey } from "./workbench/PriceChart";
import { PRICE_SERIES_KEY_PREFIX } from "@/lib/api/dashboardKeys";

function priceOk(ticker: string) {
  return {
    ticker,
    availability: "AVAILABLE",
    series: [
      { date: "2026-10-12", price: 26135 },
      { date: "2026-11-09", price: 14395 },
    ],
  };
}

const nav = vi.fn();
function renderView() {
  return render(<JudgmentWorkbenchView onNavigate={nav} />);
}

beforeEach(() => {
  __resetQueryCache();
  __resetEtfCompareCondition();
  fetchEtfCompareSummary.mockReset();
  fetchPriceSeries.mockReset();
  nav.mockReset();
  fetchEtfCompareSummary.mockResolvedValue(summaryOk());
  fetchPriceSeries.mockImplementation((t: string) => Promise.resolve(priceOk(t)));
});

describe("「후보」 첫 화면 = [섹터 요약]", () => {
  it("기준 줄 · 가격 시점 줄 · 시장 판정 줄 · 기본 조건으로 1회 조회 · 가격 시계열은 조회하지 않는다", async () => {
    renderView();
    expect(await screen.findByTestId("ec-sector-summary")).toBeInTheDocument();
    expect(screen.getByTestId("ec-basis")).toHaveTextContent(
      "1개월 · 10/12 → 11/9 · 인버스 · 레버리지 · 합성 · 선물 제외 · 비교한 ETF 961개 · 기간이 달라 뺀 17개",
    );
    expect(screen.getByTestId("ec-price-state")).toHaveTextContent("11/9 가격 = 마감 뒤 저장(11/10 13:17 ~ 13:21 저장)");
    expect(screen.getByTestId("ec-regime")).toHaveTextContent("시장 판정(국내시장 · KODEX 200 · 11/9): 하락장 · 22거래일째");
    expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(1);
    expect(fetchEtfCompareSummary.mock.calls[0][0]).toEqual(getEtfCompareCondition());
    expect(getEtfCompareCondition().basis).toBe("one_month");
    expect(fetchPriceSeries).not.toHaveBeenCalled();
  });

  it("옛 「확인 필요」 탭 · 요약 칸 · 참고점수는 없다", async () => {
    renderView();
    await screen.findByTestId("ec-sector-summary");
    expect(screen.queryByRole("tab", { name: "확인 필요" })).toBeNull();
    expect(screen.queryByText(/후보에 포함된 보유/)).toBeNull();
    expect(screen.queryByText(/참고점수/)).toBeNull();
  });

  it("하락장 = 보유 겹침 → 하위 → 상위 카드 순서", async () => {
    renderView();
    const box = await screen.findByTestId("ec-sector-summary");
    expect(box.getAttribute("data-order")).toBe("holdings,bottom,top");
    const ids = Array.from(box.querySelectorAll("[data-testid^='ec-card-']")).map((e) => e.getAttribute("data-testid"));
    expect(ids).toEqual(["ec-card-holdings", "ec-card-bottom", "ec-card-top"]);
  });

  it("상위권 = 공식 구성 먼저 · '사업군 분류 1/3 · 공통 업종 확인 어려움'", async () => {
    renderView();
    await screen.findByTestId("ec-sector-summary");
    expect(screen.getByTestId("ec-mix-top")).toHaveTextContent("공식 분류: 해외 주식 2 · 국내 주식 1");
    expect(screen.getByTestId("ec-sector-line-top")).toHaveTextContent("사업군 분류 1/3 · 공통 업종 확인 어려움");
  });

  it("하위권 = 반복된 업종 먼저(펼쳐진 반도체) · 공통 구성종목과 확인 범위 · 기초지수별 묶음은 접힘", async () => {
    renderView();
    const card = await screen.findByTestId("ec-card-bottom");
    const semi = within(card).getAllByTestId("ec-group")[0];
    expect(semi).toHaveTextContent("반도체");
    expect(semi).toHaveTextContent("서로 다른 지수 2종");
    expect(semi).toHaveTextContent("공통 구성종목 주성엔지니어링 2 · 마이크론 2");
    expect(semi).toHaveTextContent("구성 자료 있는 ETF 2/2 · 각 비중 상위 10종목 · 구성 기준일 10/2");
    const toggle = within(card).getByRole("button", { name: /기초지수별 묶음 1개 · 미분류 0개/ });
    expect(within(card).getAllByTestId("ec-group")).toHaveLength(1);
    fireEvent.click(toggle);
    expect(within(card).getAllByTestId("ec-group")).toHaveLength(2);
  });

  it("ETF 를 누르면 그 행 아래 상세 — 기존 차트(저장 건수 줄 없음) · KODEX 200 대비 한 줄 · 고점 · 3개월", async () => {
    renderView();
    const card = await screen.findByTestId("ec-card-bottom");
    fireEvent.click(within(card).getByRole("button", { name: /반도체 전공정/ }));
    const detail = await within(card).findByTestId("ec-etf-detail");
    await waitFor(() => expect(fetchPriceSeries).toHaveBeenCalledWith("B00001"));
    expect(within(detail).getByTestId("ec-detail-same")).toHaveTextContent(
      "10/12 → 11/9 · 이 ETF -44.92% · KODEX 200 -22.64% · 차이 -22.28%p",
    );
    expect(within(detail).getByTestId("ec-detail-drawdown")).toHaveTextContent("20저장일 10/13 ~ 11/9 · 고점 10/13 26,500원");
    expect(await within(detail).findByTestId("price-chart-period")).not.toHaveTextContent("개 저장일");
    expect(detail).toHaveTextContent("보유 중");
  });

  it("목록 전체 AI 복사 — 클립보드에만 쓴다", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    Object.assign(navigator, { clipboard: { writeText } });
    renderView();
    const copy = await screen.findByTestId("ec-copy-bottom");
    fireEvent.click(within(copy).getByRole("button", { name: "이 목록 전체를 AI 질문용으로 복사" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(String((writeText.mock.calls[0] as unknown[])[0])).toContain("[ETF 비교하기 · 1개월 하위 3개 · 10/12 → 11/9]");
    expect(await within(copy).findByRole("status")).toHaveTextContent("목록 전체를 AI 질문용으로 복사했습니다.");
  });
});

describe("[다시 불러오기] — 차트도 새 저장 가격으로(독립 검토 MEDIUM)", () => {
  it("차트 키는 시장 갱신 무효화 앞부분으로 시작한다", () => {
    expect(priceSeriesKey("069500").startsWith(PRICE_SERIES_KEY_PREFIX)).toBe(true);
  });

  it("열린 행을 닫고 요약을 다시 읽는다 · 같은 행을 다시 열면 가격을 새로 조회한다", async () => {
    renderView();
    const card = await screen.findByTestId("ec-card-bottom");
    fireEvent.click(within(card).getByRole("button", { name: /반도체 전공정/ }));
    await waitFor(() => expect(fetchPriceSeries).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button", { name: "다시 불러오기" }));
    await waitFor(() => expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(2));
    expect(screen.queryByTestId("ec-etf-detail")).toBeNull();
    const card2 = await screen.findByTestId("ec-card-bottom");
    fireEvent.click(within(card2).getByRole("button", { name: /반도체 전공정/ }));
    await waitFor(() => expect(fetchPriceSeries).toHaveBeenCalledTimes(2));
  });
});

describe("[ETF 순위] — 같은 목록 안 표시 순서(판정 Q9 · Q10 · §5)", () => {
  const vals = () => screen.getAllByTestId("ec-rank-val").map((e) => e.textContent);
  const names = () => screen.getAllByTestId("ec-rank-row").map((e) => e.textContent ?? "");

  it("처음은 선정 순서 · 하위 30 · 3개월 낮은 순 · 높은 순 모두 기간 다름은 뒤", async () => {
    renderView();
    await screen.findByTestId("ec-sector-summary");
    fireEvent.click(screen.getByRole("tab", { name: "ETF 순위" }));
    expect(screen.getByTestId("ec-sort-line")).toHaveTextContent("1개월 상위 3 · 정렬 선정 순서(1개월 높은 순)");
    fireEvent.click(screen.getByRole("button", { name: "하위 3" }));
    fireEvent.click(screen.getByRole("button", { name: "3개월 수익률" }));
    expect(screen.getByTestId("ec-sort-line")).toHaveTextContent(
      "1개월 하위 3 · 정렬 3개월 수익률 낮은 순 · 8/11 → 11/9 · 비교 가능 2 · 기간 다름 · 값 없음 1(뒤)",
    );
    expect(vals()).toEqual(["-22.46%", "-20.05%", "기간 다름 · 9/15 → 11/9"]);
    fireEvent.click(screen.getByRole("button", { name: /3개월 수익률/ }));
    expect(vals()).toEqual(["-20.05%", "-22.46%", "기간 다름 · 9/15 → 11/9"]);
    expect(names()[0]).toContain("하위 2위"); // 선정 순위와 표시 순서를 나눠 적는다
  });

  it("고점 대비 0.00% 는 값으로 보이고 값 없음은 사유 · KODEX 대비는 같은 순서 안내", async () => {
    renderView();
    await screen.findByTestId("ec-sector-summary");
    fireEvent.click(screen.getByRole("tab", { name: "ETF 순위" }));
    fireEvent.click(screen.getByRole("button", { name: "하위 3" }));
    fireEvent.click(screen.getByRole("button", { name: "최근 고점 대비(20저장일)" }));
    expect(vals()).toEqual(["-10.00%", "0.00%", "값 없음 · 20저장일 부족"]);
    fireEvent.click(screen.getByRole("button", { name: "1개월 KODEX 200 대비" }));
    expect(screen.getByTestId("ec-kodex-note")).toHaveTextContent(
      "같은 1개월 구간(10/12 → 11/9) KODEX 200 -22.64% · 비교 가능한 행에서는 1개월과 순서가 같습니다",
    );
    expect(vals()[0]).toBe("-22.28%p");
  });

  it("보유 종목에는 '보유' 표시 · 행을 누르면 그 행 아래 상세", async () => {
    renderView();
    await screen.findByTestId("ec-sector-summary");
    fireEvent.click(screen.getByRole("tab", { name: "ETF 순위" }));
    fireEvent.click(screen.getByRole("button", { name: "하위 3" }));
    const first = screen.getAllByTestId("ec-rank-row")[0];
    expect(first).toHaveTextContent("보유");
    fireEvent.click(within(first).getByRole("button"));
    expect(await within(first).findByTestId("ec-etf-detail")).toBeInTheDocument();
  });
});

describe("조회 기준 · 상태", () => {
  it("[조회 기준]에서 3개월을 적용하면 같은 조건으로 다시 조회한다(「보유」와 공유)", async () => {
    renderView();
    await screen.findByTestId("ec-sector-summary");
    fireEvent.click(screen.getByRole("button", { name: "조회 기준" }));
    const panel = screen.getByTestId("ec-condition-panel");
    fireEvent.click(within(panel).getByRole("button", { name: "3개월" }));
    fireEvent.click(within(panel).getByRole("button", { name: "적용" }));
    await waitFor(() => expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(2));
    expect(fetchEtfCompareSummary.mock.calls[1][0].basis).toBe("three_month");
    expect(getEtfCompareCondition().basis).toBe("three_month");
  });

  it("장중 저장값이면 가격 줄 · 시장 판정에 잠정을 밝힌다", async () => {
    const s = summaryOk();
    const intraday = { date: "2026-11-10", state: "intraday" as const, fetched_at_kst: "2026-11-10T13:18:02+09:00" };
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
      regime: { ...s.regime, price: intraday },
    });
    renderView();
    expect(await screen.findByTestId("ec-price-state")).toHaveTextContent("장중 저장값 포함 · 잠정(장중 961개 · 11/10 13:17 ~ 13:21 저장)");
    expect(screen.getByTestId("ec-regime")).toHaveTextContent("(잠정 · 장중 저장값 기준)");
  });

  it("공통 기간을 정하지 못하면 사유 · 목록을 만들지 않는다 · 조회 실패는 실패로", async () => {
    fetchEtfCompareSummary.mockResolvedValueOnce({ status: "no_common_period", message: "x", basis: "one_month" });
    const { unmount } = renderView();
    expect(await screen.findByTestId("ec-not-ok")).toHaveTextContent("공통 기간을 정하지 못해");
    expect(screen.queryByTestId("ec-sector-summary")).toBeNull();
    unmount();
    __resetQueryCache();
    fetchEtfCompareSummary.mockRejectedValueOnce(new Error("down"));
    renderView();
    expect(await screen.findByText(/비교 자료 조회 실패/)).toBeInTheDocument();
  });
});

describe("[검증자 r1 F3] 상·하위에 함께 든 같은 ETF 를 공통으로 구분한다", () => {
  function bothSummary() {
    const x = row({ rank: 1, ticker: "X00001", name: "단일 ETF", value: -3 });
    const g = group([x], { kind: "index", name: "단일 지수" });
    const s = summaryOk();
    return {
      ...s,
      top: [x],
      bottom: [x],
      in_both: ["X00001"],
      groups: { top: [g], bottom: [g] },
      counts: { ...s.counts, population: 1, shown_top: 1, shown_bottom: 1 },
      holdings: {
        status: "ok" as const,
        items: [link({ ticker: "X00001", side: "bottom", side_rank: 1, top_rank: 1 })],
      },
    };
  }

  it("[ETF 순위] 상위 · 하위 목록 모두 '상·하위 공통'", async () => {
    fetchEtfCompareSummary.mockResolvedValue(bothSummary());
    renderView();
    await screen.findByTestId("ec-sector-summary");
    fireEvent.click(screen.getByRole("tab", { name: "ETF 순위" }));
    expect(screen.getAllByTestId("ec-rank-row")[0]).toHaveTextContent("상·하위 공통");
    fireEvent.click(screen.getByRole("button", { name: "하위 1" }));
    const r = screen.getAllByTestId("ec-rank-row")[0];
    expect(r).toHaveTextContent("상·하위 공통");
    fireEvent.click(within(r).getByRole("button"));
    expect(await within(r).findByTestId("ec-etf-detail")).toHaveTextContent("상위 1위 · 하위 1위(상·하위 공통)");
  });

  it("[섹터 요약] ETF 줄 · 내 보유와 겹친 항목에도 공통 표시", async () => {
    fetchEtfCompareSummary.mockResolvedValue(bothSummary());
    renderView();
    const hold = await screen.findByTestId("ec-card-holdings");
    expect(hold).toHaveTextContent("하위 1위 · 상위 1위(상·하위 공통)");
    const card = screen.getByTestId("ec-card-bottom");
    fireEvent.click(within(card).getByRole("button", { name: /기초지수별 묶음 1개/ }));
    const grp = within(card).getAllByTestId("ec-group")[0];
    fireEvent.click(grp.querySelector("summary")!);
    expect(within(card).getByRole("button", { name: /단일 ETF/ })).toHaveTextContent("상·하위 공통");
  });
});
