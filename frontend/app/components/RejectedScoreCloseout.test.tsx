// POC3-ML-02 REJECT Closeout — 계약 test (2026-08-29 신규).
//
// `relative_upside_v0` 은 유효성 검증에서 REJECT 판정을 받았다. 이 파일은
// **REJECT 된 점수가 판단 화면에 되살아나지 않는다** 는 하나의 책임만 고정한다.
//
// 설계자 확정 검증 계약 (PLAN V1.1 §5):
//   C-1 후보표·워크벤치·카드·보유와비교·선택상세에 점수·사유 미표시
//   C-2 `참고점수` 정렬 선택지 부재
//   C-3 점수를 바꾸거나 지워도 **기본 순서** 불변
//   C-4 기본 상태 순서 = API 후보 순서
//   C-5 ML 연구 화면은 유지 + REJECT·연구용 표기 + 후보 화면 이동 링크 부재
//   C-7 정상 정렬(1M·3M·KODEX초과·고점대비·보유노출)은 그대로 동작
//   C-8 카드 큰 숫자 자리 = 1개월 수익률 (결측은 0 아닌 DASH)
//
// C-6(API·운영 무변경)은 백엔드 회귀 + `git diff` 기계 검사로 확인한다 —
// 프론트 test 의 범위가 아니다.
//
// 픽스처에는 **점수를 일부러 넣는다.** 값이 들어와도 화면에 안 나오는 것을
// 증명해야 하기 때문이다.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import type { MarketCandidate } from "@/lib/api";

import CandidateTable from "./CandidateTable";
import CandidateCards from "./CandidateCards";
import HoldingsCompareView from "./HoldingsCompareView";
import SelectedDetail from "./holdings_compare/SelectedDetail";
import RelativeUpsideRunCard from "./RelativeUpsideRunCard";
import MLView from "./MLView";

vi.mock("@/lib/api/mlRelativeUpside", () => ({
  runRelativeUpsideScore: vi.fn(),
}));

// `ML 실험` 의 다른 카드 4개는 마운트 시 각자 조회한다. 본 파일의 관심사가
// 아니고, 그대로 두면 단언 뒤에 상태가 갱신돼 act(...) 경고가 난다.
// `RelativeUpsideRunCard` 는 mount fetch 가 없으므로 **실물 그대로** 쓴다.
vi.mock("./MLEvidenceRefreshCard", () => ({ default: () => null }));
vi.mock("./MLTimeseriesReadinessCard", () => ({ default: () => null }));
vi.mock("./MLFeatureSanityCard", () => ({ default: () => null }));
vi.mock("./MLBaselineV0Card", () => ({ default: () => null }));

// `보유와 비교` 는 마운트 시 보유/근거를 자동 조회한다. 그대로 두면 단언 시점과
// 상태 갱신 시점이 어긋나 act(...) 경고가 난다. 결정적으로 통제한다.
const fetchEnrichedHoldings = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
vi.mock("@/lib/api/holdings", () => ({
  fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
  fetchHoldingsMarketEvidence: (...a: unknown[]) =>
    fetchHoldingsMarketEvidence(...a),
}));

const SCORE_TEXTS = ["72.3", "88.8", "11.1"];
const REASON_TEXTS = ["1M 상위", "거래대금 충분"];

function cand(over: Partial<MarketCandidate> = {}): MarketCandidate {
  return {
    rank: 1,
    ticker: "069500",
    name: "KODEX 200",
    returns: {
      daily: { return_pct: 0.5 },
      one_month: { return_pct: 6.01 },
      three_month: { return_pct: -13.8 },
      six_month: { return_pct: 4.1 },
      twelve_month: { return_pct: 11.2 },
      three_year: { return_pct: 38.4 },
    },
    excess_return: { vs_kodex200_1m_pctp: 11.9, vs_kodex200_3m_pctp: -2.3 },
    relative_upside_score: 72.3,
    relative_upside_reasons: REASON_TEXTS,
    drawdown_20d: -0.042,
    short_term_momentum: { excess_vs_kodex200_20d_pctp: 1.1 },
    data_quality: { status: "ok" },
    ...over,
  } as MarketCandidate;
}

/** 순서 검증용 3종목. 점수는 순서와 **반대** 로 매긴다. */
function trio(): MarketCandidate[] {
  return [
    cand({ rank: 1, ticker: "AAA", name: "가나다 ETF", relative_upside_score: 11.1 }),
    cand({ rank: 2, ticker: "BBB", name: "라마바 ETF", relative_upside_score: 88.8 }),
    cand({ rank: 3, ticker: "CCC", name: "사아자 ETF", relative_upside_score: 72.3 }),
  ];
}

function reversedScores(list: MarketCandidate[]): MarketCandidate[] {
  const scores = list.map((c) => c.relative_upside_score);
  return list.map((c, i) => ({
    ...c,
    relative_upside_score: scores[scores.length - 1 - i],
  }));
}

function nulledScores(list: MarketCandidate[]): MarketCandidate[] {
  return list.map((c) => ({
    ...c,
    relative_upside_score: null,
    relative_upside_reasons: [],
  }));
}

function tickerOrder(container: HTMLElement, tickers: string[]): string[] {
  const text = container.textContent ?? "";
  return tickers
    .map((t) => ({ t, at: text.indexOf(t) }))
    .filter((x) => x.at >= 0)
    .sort((a, b) => a.at - b.at)
    .map((x) => x.t);
}

function expectNoScoreArtifacts(container: HTMLElement) {
  const text = container.textContent ?? "";
  for (const s of SCORE_TEXTS) expect(text).not.toContain(s);
  for (const r of REASON_TEXTS) expect(text).not.toContain(r);
  expect(text).not.toContain("참고점수");
  expect(text).not.toContain("점수 근거");
  expect(text).not.toContain("점수 미생성");
}

// --- C-1 / C-8 : 후보 표 · 후보 카드 ---------------------------------------

describe("C-1 후보 표 — 점수·사유 미표시", () => {
  it("점수가 들어와도 표에 점수·사유·고지 배너가 없다", () => {
    const { container } = render(
      <CandidateTable
        candidates={[cand()]}
        basis="one_month"
        order="desc"
        onSort={() => {}}
      />,
    );
    expectNoScoreArtifacts(container);
    // 남아야 하는 열은 그대로다.
    expect(within(container).getByText("고점 대비")).toBeInTheDocument();
    expect(within(container).getByText("069500")).toBeInTheDocument();
  });
});

describe("C-1 / C-8 후보 카드", () => {
  it("점수·사유가 없고 큰 숫자 자리는 1개월 수익률이다", () => {
    const { container } = render(
      <CandidateCards candidates={[cand()]} heldTickers={new Set()} />,
    );
    expectNoScoreArtifacts(container);
    const list = screen.getByTestId("candidate-card-list");
    expect(within(list).getAllByText("+6.01%").length).toBeGreaterThan(0);
    expect(within(list).getAllByText("1개월").length).toBeGreaterThan(0);
  });

  it("1개월 수익률이 없으면 0 이 아니라 결측 표기다", () => {
    const c = cand({ returns: { one_month: { return_pct: null } } } as never);
    const { container } = render(
      <CandidateCards candidates={[c]} heldTickers={new Set()} />,
    );
    const text = container.textContent ?? "";
    expect(text).not.toContain("+0.00%");
    expect(text).not.toContain("0.0");
  });

  it("펼쳐도 점수 근거가 나오지 않는다", () => {
    const { container } = render(
      <CandidateCards candidates={[cand()]} heldTickers={new Set()} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /상세 보기/ }));
    expectNoScoreArtifacts(container);
  });
});

// --- C-3 / C-4 : 주문 불변 (후보 표 · 후보 카드) ---------------------------

describe("C-3 / C-4 주문 불변 — 후보 표", () => {
  const TICKERS = ["AAA", "BBB", "CCC"];
  function orderOf(list: MarketCandidate[]) {
    const { container, unmount } = render(
      <CandidateTable
        candidates={list}
        basis="one_month"
        order="desc"
        onSort={() => {}}
      />,
    );
    const got = tickerOrder(container, TICKERS);
    unmount();
    return got;
  }

  it("점수를 뒤집거나 지워도 순서가 같고 API 순서와 일치한다", () => {
    const base = trio();
    const a = orderOf(base);
    const b = orderOf(reversedScores(base));
    const c = orderOf(nulledScores(base));
    expect(a).toEqual(TICKERS); // C-4 — API 순서 그대로
    expect(b).toEqual(a); // C-3
    expect(c).toEqual(a); // C-3
  });
});

describe("C-3 / C-4 주문 불변 — 후보 카드", () => {
  const TICKERS = ["AAA", "BBB", "CCC"];
  function orderOf(list: MarketCandidate[]) {
    const { container, unmount } = render(
      <CandidateCards candidates={list} heldTickers={new Set()} />,
    );
    const got = tickerOrder(container, TICKERS);
    unmount();
    return got;
  }

  it("점수를 뒤집거나 지워도 순서가 같고 API 순서와 일치한다", () => {
    const base = trio();
    const a = orderOf(base);
    expect(a).toEqual(TICKERS);
    expect(orderOf(reversedScores(base))).toEqual(a);
    expect(orderOf(nulledScores(base))).toEqual(a);
  });
});

// --- C-1 / C-2 / C-3 / C-4 / C-7 : 보유와 비교 -----------------------------

function compareData(candidates: MarketCandidate[]) {
  return {
    status: "ok",
    asof: "2026-08-27",
    candidates,
    daily_topn: [],
    one_month_topn: [],
    three_month_topn: [],
  } as never;
}

/**
 * 정렬 실동작 검증용 3종목.
 * 각 정렬 키가 **서로 다른 순서**를 만들도록 값을 설계했다.
 *   excess_20d(desc) : BBB(9) > AAA(5) > CCC(1)
 *   drawdown(desc)   : CCC(-0.01) > AAA(-0.05) > BBB(-0.09)
 *   exposure(desc)   : CCC(직접보유) > AAA · BBB  ← 기본 순서와 다름
 */
function sortTrio(): MarketCandidate[] {
  const mk = (
    ticker: string,
    name: string,
    rank: number,
    ex20: number,
    dd: number,
  ) =>
    cand({
      ticker,
      name,
      rank,
      relative_upside_score: 50,
      short_term_momentum: {
        status: "ok",
        excess_vs_kodex200_20d_pctp: ex20,
      },
      drawdown_20d: dd,
    });
  return [
    mk("AAA", "가나다 ETF", 1, 5, -0.05),
    mk("BBB", "라마바 ETF", 2, 9, -0.09),
    mk("CCC", "사아자 ETF", 3, 1, -0.01),
  ];
}

/** 보유 카드에도 같은 ticker·라벨이 나온다 — **후보 ETF 카드**로 범위를 좁힌다. */
function candidateCard(): HTMLElement {
  const card = screen.getByText("후보 ETF").closest(".card");
  if (!card) throw new Error("후보 ETF 카드를 찾지 못했다");
  return card as HTMLElement;
}

function candSortButton(label: RegExp): HTMLElement {
  return within(candidateCard()).getByRole("button", { name: label });
}

/** 후보 카드 안에서의 ticker 표시 순서. */
function candidateOrder(tickers: string[]): string[] {
  return tickerOrder(candidateCard(), tickers);
}

async function renderCompare(list: MarketCandidate[]) {
  const utils = render(<HoldingsCompareView data={compareData(list)} />);
  // 마운트 시 자동 조회가 끝날 때까지 기다린다 (act 경고 방지).
  await waitFor(() => {
    expect(fetchEnrichedHoldings).toHaveBeenCalled();
    expect(fetchHoldingsMarketEvidence).toHaveBeenCalled();
  });
  // 후보가 실제로 그려졌는지로 기다린다 (보유 종목 이름에 의존하지 않는다).
  const firstTicker = list[0]?.ticker ?? "";
  await waitFor(() => {
    expect(within(candidateCard()).getByText(firstTicker)).toBeInTheDocument();
  });
  return utils;
}

describe("보유와 비교 — 점수 미표시 · 정렬 선택지 부재 · 주문 불변", () => {
  beforeEach(() => {
    // **맨 뒤(CCC)** 만 직접 보유한다. 앞이 아니라 뒤를 보유해야
    // `보유 노출` 정렬 결과가 기본 순서와 달라져 실동작을 증명할 수 있다.
    fetchEnrichedHoldings.mockReset().mockResolvedValue({
      items: [
        {
          ticker: "CCC",
          name: "사아자 ETF",
          quantity: 10,
          avg_buy_price: 1000,
          invested_amount: 10000,
          current_price: 1100,
          price_asof: "2026-08-27",
          price_source: "n",
          eval_amount: 11000,
          pnl_amount: 1000,
          pnl_rate_pct: 10,
          buy_weight_pct: null,
          market_weight_pct: 100,
          price_missing: false,
          calc_missing: false,
        },
      ],
    });
    fetchHoldingsMarketEvidence.mockReset().mockResolvedValue({
      status: "ok",
      asof: "2026-08-27",
      holdings: [],
      warnings: [],
    });
  });

  it("C-1 점수·사유가 없다", async () => {
    const { container } = await renderCompare([cand()]);
    expectNoScoreArtifacts(container);
  });

  it("C-2 정렬 선택지에 `참고점수` 가 없다", async () => {
    await renderCompare([cand()]);
    expect(
      screen.queryByRole("button", { name: /참고점수/ }),
    ).not.toBeInTheDocument();
  });

  it("C-7 정상 정렬 3종이 **실제로 순서를 바꾼다**", async () => {
    const TICKERS = ["AAA", "BBB", "CCC"];
    await renderCompare(sortTrio());
    const order = () => candidateOrder(TICKERS);

    // 기본(default) — API 순서.
    expect(order()).toEqual(["AAA", "BBB", "CCC"]);

    // 첫 클릭은 desc (handleCandSort 계약).
    fireEvent.click(candSortButton(/20일 초과/));
    expect(order()).toEqual(["BBB", "AAA", "CCC"]);

    fireEvent.click(candSortButton(/고점 대비/));
    expect(order()).toEqual(["CCC", "AAA", "BBB"]);

    // `보유 노출` desc — 직접 보유한 CCC 가 **맨 뒤에서 맨 앞으로** 올라온다.
    // 기본 순서(AAA,BBB,CCC)와 결과가 달라야 정렬 분기의 실동작 증거가 된다.
    fireEvent.click(candSortButton(/보유 노출/));
    const byExposure = order();
    expect(byExposure).toEqual(["CCC", "AAA", "BBB"]);
    expect(byExposure).not.toEqual(TICKERS); // 기본 순서와 반드시 달라야 한다

    // 같은 키 재클릭 → asc 전환. 정렬이 살아 있음을 한 번 더 확인한다.
    fireEvent.click(candSortButton(/고점 대비/));
    fireEvent.click(candSortButton(/고점 대비/));
    expect(order()).toEqual(["BBB", "AAA", "CCC"]);
  });

  it("C-3 / C-4 점수를 뒤집거나 지워도 기본 순서가 API 순서와 같다", async () => {
    const TICKERS = ["AAA", "BBB", "CCC"];
    const base = trio();
    const orderOf = async (list: MarketCandidate[]) => {
      const { unmount } = await renderCompare(list);
      const got = candidateOrder(TICKERS);
      unmount();
      return got;
    };
    const a = await orderOf(base);
    expect(a).toEqual(TICKERS);
    expect(await orderOf(reversedScores(base))).toEqual(a);
    expect(await orderOf(nulledScores(base))).toEqual(a);
  });
});

describe("C-1 보유와 비교 선택 상세", () => {
  it("참고점수·사유가 없다", () => {
    const { container } = render(
      <SelectedDetail
        candidate={cand()}
        exposure={{ kind: "unchecked" } as never}
        expanded={false}
        onToggleExpanded={() => {}}
        directHoldingEvidence={undefined}
      />,
    );
    expectNoScoreArtifacts(container);
  });
});

// --- C-5 : ML 연구 화면 -----------------------------------------------------

describe("C-5 ML 연구 화면", () => {
  it("실행 카드가 유지되고 REJECT·연구용 표기가 보인다", () => {
    render(
      <RelativeUpsideRunCard
        result={null}
        errorMessage={null}
        onResult={() => {}}
        onError={() => {}}
      />,
    );
    expect(screen.getByText("relative_upside_v0")).toBeInTheDocument();
    expect(screen.getByText("REJECT")).toBeInTheDocument();
    expect(
      screen.getByText("연구용 baseline이며 투자 판단에 사용하지 않음"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /상대상승 점수 계산/ }),
    ).toBeInTheDocument();
  });

  it("후보 화면으로 이동하는 링크가 없다", () => {
    const { container } = render(<MLView />);
    expect(container.textContent ?? "").not.toContain("요즘 잘 오르는 ETF →");
  });
});
