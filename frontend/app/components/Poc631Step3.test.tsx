// POC6-31 STEP 3 — 여러 지수 계열이 함께 담은 주식 카드 · 중복률 탭(같은 날짜 상위 10쌍 · 참고) · 「섹터요약」 → 「후보리스트」.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

// 「ETF 구성종목」 화면 배치 시험용(이 파일의 다른 시험은 조회를 부르지 않음)
const fetchConstituentsAnalysis = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<Record<string, unknown>>()),
  fetchConstituentsAnalysis: (...a: unknown[]) => fetchConstituentsAnalysis(...a),
  fetchHoldingsMarketEvidence: (...a: unknown[]) => fetchHoldingsMarketEvidence(...a),
}));
const fetchConstituentsCrossFamily = vi.fn();
const fetchConstituentsCollectStatus = vi.fn();
vi.mock("@/lib/api/constituentsStatus", async (orig) => ({
  ...(await orig<Record<string, unknown>>()),
  fetchConstituentsCrossFamily: (...a: unknown[]) => fetchConstituentsCrossFamily(...a),
  fetchConstituentsCollectStatus: (...a: unknown[]) => fetchConstituentsCollectStatus(...a),
}));
import ETFExposureView from "./ETFExposureView";
import { saveETFExposureDraft } from "@/lib/etfExposureDraft";
import { loadAISessionsDraft } from "@/lib/aiSessionsDraft";
import CrossFamilyCard from "./CrossFamilyCard";
import OverlapTab from "./OverlapTab";
import SectorSummary from "./workbench/SectorSummary";
import type { CrossFamilyResponse, CrossFamilyStock } from "@/lib/api/constituentsStatus";
import type { ConstituentsAnalysisResponse, OverlapPair } from "@/lib/api";
import {
  __resetEtfCompareCondition,
  getScreenCondition,
  takeOneTimeCondition,
} from "@/lib/etfCompareCondition";
import { buildMarketDiscoveryCopyText } from "@/lib/marketDiscoveryCopyText";
import { summaryOk } from "@/lib/etfCompareTestFixtures";

const stock = (name: string, fam: number, etfs: number, maxW: number): CrossFamilyStock => ({
  key: name,
  name,
  families: Array.from({ length: fam }, (_, i) => `F${i}`),
  family_count: fam,
  etf_count: etfs,
  strategy_count: name === "코카콜라" ? 3 : 0,
  max_weight_pct: maxW,
  max_entry: { etf: "476070", etf_name: "KODEX 글로벌비만치료제TOP2 Plus", rank: 1 },
  entries: [
    { etf: "476070", etf_name: "KODEX 글로벌비만치료제TOP2 Plus", selection_rank: 4, family: "F0", index_name: "iSelect 글로벌 비만치료제TOP2 Plus 지수(PR)", strategy: false, rank: 1, weight_pct: 29.98, asof: "2026-11-13" },
    { etf: "458760", etf_name: "TIGER 미국배당다우존스타겟커버드콜2호", selection_rank: 22, family: "F1", index_name: "DowJones U.S. Dividend 100 7% Premium Covered Call 지수 (TR)", strategy: true, rank: 7, weight_pct: 3.96, asof: "2026-11-13" },
  ],
});

const cf = (p: Partial<CrossFamilyResponse> = {}): CrossFamilyResponse => ({
  status: "ok",
  scope: { requested: 30, with_data: 30, no_confirmed_data: 0, latest_date: "2026-11-13", same_date: 30, family_count: 22, unknown_rows: 2, evidence_count: 138, etf_with_stock_rows: 29, unconfirmed_family_etfs: 0 },
  stocks: [stock("암젠", 9, 12, 11.98), stock("일라이 릴리", 8, 8, 30.22), stock("코카콜라", 3, 6, 11.54)],
  reference: [],
  ...p,
});

describe("여러 지수 계열이 함께 담은 주식 카드", () => {
  it("확인 범위 · 판정 문장을 수치보다 먼저 · 펼치면 공식 지수명 · 전략형 · 후보로 고르기", () => {
    const onPick = vi.fn();
    render(<CrossFamilyCard cf={cf()} error={null} returnByTicker={{ "476070": 14.67 }} onPick={onPick} picked={null} />);
    expect(screen.getByTestId("cf-scope").textContent).toContain("구성 자료 30/30(원천 구성일 확인된 것) · 최신 구성일 11/13 30개 · 확인된 계열 22개 · 종류 미확인 행 2(가림)");
    expect(screen.getByTestId("cf-verdict").textContent).toBe("서로 다른 계열 2개 이상이 함께 담은 주식 3종목 · 편입 근거 138건");
    const card = screen.getByTestId("cf-card");
    expect(card.compareDocumentPosition(screen.getByTestId("cf-table")) & Node.DOCUMENT_POSITION_CONTAINED_BY).toBeTruthy();
    // POC6-31(형수님 화면 의견 · 목업 확인 2026-11-16) — 한 줄 요약 · 줄 전체를 눌러 펼침([ETF 보기] 버튼 없음)
    const row = within(screen.getByText("일라이 릴리").closest(".cf-stock") as HTMLElement).getByTestId("cf-stock-row");
    expect(row.textContent).toContain("계열 8");
    expect(row.textContent).toContain("ETF 8");
    expect(row.textContent).toContain("가장 큰 비중 30.22% · KODEX 글로벌비만치료제TOP2 Plus 1위");
    expect(screen.queryByRole("button", { name: "ETF 보기" })).toBeNull();
    expect(row).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(row);
    expect(row).toHaveAttribute("aria-expanded", "true");
    const entries = screen.getByTestId("cf-entries");
    expect(entries.textContent).toContain("DowJones U.S. Dividend 100 7% Premium Covered Call 지수 (TR) · 전략형");
    expect(entries.textContent).toContain("+14.67%");
    // ETF 줄 전체가 고르기
    fireEvent.click(within(entries).getAllByTestId("cf-etf")[0]);
    expect(onPick).toHaveBeenCalledWith("476070", "KODEX 글로벌비만치료제TOP2 Plus");
    fireEvent.click(row);
    expect(screen.queryByTestId("cf-entries")).toBeNull();
  });

  it.each([
    [{ status: "not_comparable" as const, stocks: [] }, "비교 못 함 — 같은 날짜에 주식 행이 있는 계열이 2개 미만입니다"],
    [{ status: "ok" as const, stocks: [] }, "0종목 — 비교는 성립했고 서로 다른 계열 2개 이상이 함께 담은 주식이 없습니다"],
    [{ status: "no_data" as const, stocks: [] }, "비교 못 함 — 원천 구성일이 확인된 구성 자료가 없습니다([구성종목 수집]으로 받습니다)"],
  ])("'비교 못 함'과 '0종목'을 구분한다 %#", (over, text) => {
    render(<CrossFamilyCard cf={cf(over)} error={null} returnByTicker={{}} onPick={vi.fn()} picked={null} />);
    expect(screen.getByTestId("cf-verdict").textContent).toBe(text);
  });

  it("이전 구성일은 참고 · 고른 ETF 는 파란 줄 · 채운 동그라미 · '✓ 고른 후보' · 어느 주식 아래든 같이 · 담은 주식 줄에 '고른 후보 포함'", () => {
    render(
      <CrossFamilyCard
        cf={cf({ reference: [{ date: "2026-11-12", status: "not_comparable", etf_count: 1, etf_with_stock_rows: 1, family_count: 1, unconfirmed_family_etfs: 0, unknown_rows: 0, evidence_count: 0, stocks: [] }] })}
        error={null}
        returnByTicker={{ "476070": 14.67 }}
        onPick={vi.fn()}
        picked={{ ticker: "476070", name: "KODEX 글로벌비만치료제TOP2 Plus" }}
      />,
    );
    expect(screen.getByTestId("cf-reference").textContent).toContain("11/12 구성 ETF 1개 — 비교 못 함");
    expect(screen.queryByTestId("cf-compare")).toBeNull();
    const rows = screen.getAllByTestId("cf-stock-row");
    for (const r of rows) expect(r.textContent).toContain("고른 후보 포함"); // 예시 세 주식 모두 476070 이 담음
    fireEvent.click(rows[0]);
    fireEvent.click(rows[1]);
    const lists = screen.getAllByTestId("cf-entries");
    expect(lists).toHaveLength(2);
    for (const l of lists) {
      const [on, off] = within(l).getAllByTestId("cf-etf");
      expect(on).toHaveAttribute("aria-pressed", "true");
      expect(on.className).toContain("cf-etf-on");
      expect(on.textContent).toContain("✓ 고른 후보");
      expect(off).toHaveAttribute("aria-pressed", "false");
      expect(off.textContent).not.toContain("고른 후보");
    }
  });
});

type Scope = NonNullable<OverlapPair["pair_scope"]>;
const pair = (i: number, overlap: number | null, scope: Scope | boolean = "same_date"): OverlapPair => {
  const sc: Scope = scope === true ? "same_date" : scope === false ? "different_date" : scope;
  return {
    left_ticker: `L${i}`,
    right_ticker: `R${i}`,
    common_count_top10: 1,
    weighted_overlap_pct: overlap,
    common_holdings: [],
    left_asof: "2026-11-13",
    right_asof: sc === "no_data" ? null : sc === "different_date" ? "2026-11-12" : "2026-11-13",
    same_date: sc === "no_data" ? null : sc === "same_date",
    pair_scope: sc,
  };
};

const analysisOf = (pairs: OverlapPair[]) =>
  ({
    status: "ok",
    asof: "2026-11-13",
    top_k: 30,
    overlap_top_k: 10,
    coverage: { requested_count: 30, available_count: 29, unavailable_count: 1 },
    constituents: [],
    overlap_matrix: pairs,
    repeated_core_holdings: [{ ticker: "X", name: "옛 반복", appears_in_etf_count: 3, items: [] }],
  }) as unknown as ConstituentsAnalysisResponse;

describe("중복률 탭(판정 Q7 · Q21)", () => {
  it("같은 날짜 쌍 중 상위 10쌍 + 나머지 펼치기 · 다른 날짜 쌍은 참고 · 예전 반복 핵심 종목 자리는 새 카드", () => {
    const a = {
      status: "ok",
      asof: "2026-11-13",
      top_k: 30,
      overlap_top_k: 10,
      coverage: { requested_count: 5, available_count: 5, unavailable_count: 0 },
      constituents: [],
      overlap_matrix: [...Array.from({ length: 12 }, (_, i) => pair(i, 50 - i)), pair(99, 99, false)],
      repeated_core_holdings: [{ ticker: "X", name: "옛 반복", appears_in_etf_count: 3, items: [] }],
    } as unknown as ConstituentsAnalysisResponse;
    render(<OverlapTab analysis={a} slot={<div data-testid="slot">새 카드</div>} />);
    expect(screen.getByTestId("overlap-pair-scope").textContent).toBe(
      "같은 구성일 쌍 12개 중 10쌍 · 나머지 2쌍은 아래에서 펼칩니다 · 같은 구성일이 아닌 쌍(구성일 다름 1)은 세지 않음",
    );
    const list = screen.getByTestId("overlap-pair-list");
    expect(list.querySelectorAll(":scope > *").length).toBe(10);
    expect(list.textContent).not.toContain("L99"); // 다른 날짜 쌍(99%)은 순위에 섞지 않음
    fireEvent.click(screen.getByTestId("overlap-rest"));
    expect(screen.getByTestId("overlap-pair-list").querySelectorAll(":scope > *").length).toBe(12);
    expect(screen.getByTestId("overlap-ref-pairs").textContent).toContain(
      "같은 구성일이 아닌 쌍 1개(참고 · 구성일 다름 1 · 원천 기준일 미확인 0)",
    );
    expect(screen.getByTestId("overlap-ref-note").textContent).toBe("구성일 다름 · 11/13 ↔ 11/12");
    expect(screen.getByTestId("slot")).toBeInTheDocument();
    expect(screen.queryByText("반복 등장 핵심 종목")).toBeNull();
  });
});

describe("중복률 쌍 범위 — 자료 없는 쌍 · 원천 기준일 미확인(지적 backend#0 · frontend#0 · backend#6)", () => {
  // 판정 §4 M2 — 30개 중 29개만 같은 날짜 자료 → 같은 구성일 쌍 406 · 한쪽 자료 없는 쌍 29 는 세지 않음
  const pairs = [
    ...Array.from({ length: 406 }, (_, i) => pair(i, i % 7 === 0 ? null : 10 + (i % 50))),
    ...Array.from({ length: 29 }, (_, i) => pair(1000 + i, null, "no_data")),
  ];

  it("화면 — 같은 구성일 쌍 406 · 중복률이 비어도(겹침 없음) 같은 구성일 쌍으로 센다 · 자료 없는 쌍은 개수만", () => {
    render(<OverlapTab analysis={analysisOf(pairs)} />);
    expect(screen.getByTestId("overlap-pair-scope").textContent).toBe(
      "같은 구성일 쌍 406개 중 10쌍 · 나머지 396쌍은 아래에서 펼칩니다 · 같은 구성일이 아닌 쌍(한쪽 구성 자료 없음 29)은 세지 않음",
    );
    expect(screen.queryByTestId("overlap-ref-pairs")).toBeNull(); // 자료 없는 쌍은 참고 목록에도 넣지 않음
  });

  it("원천 기준일 미확인 쌍은 같은 날짜여도 순위에 섞지 않고 참고(이유 표시)", () => {
    render(<OverlapTab analysis={analysisOf([pair(1, 20), pair(2, 90, "unconfirmed")])} />);
    expect(screen.getByTestId("overlap-pair-list").textContent).not.toContain("L2");
    expect(screen.getByTestId("overlap-ref-note").textContent).toBe("원천 기준일 미확인 · 11/13 ↔ 11/13");
  });

  it("AI 복사 글 — 같은 구성일 쌍 406 · 뺀 쌍 이유 · 공통 주식을 못 읽으면 '읽지 못함'(예전 반복 목록으로 채우지 않음)", () => {
    const lines = buildMarketDiscoveryCopyText({
      asof: "2026-11-13",
      filters: {} as never,
      candidates: [],
      marketContext: null,
      constituentsAnalysis: analysisOf(pairs),
      crossFamily: null,
      crossFamilyError: "요청 실패(HTTP 500)",
    }).split("\n");
    expect(lines.find((l) => l.startsWith("- 중복률 상위"))).toBe(
      "- 중복률 상위 (같은 구성일 쌍 406개 중 5쌍 · 같은 구성일이 아닌 쌍(한쪽 구성 자료 없음 29)은 뺌):",
    );
    expect(lines).toContain("- 여러 지수 계열이 함께 담은 주식: 읽지 못함 — 요청 실패(HTTP 500)");
    expect(lines.join("\n")).not.toContain("반복 등장 핵심 종목");
  });

  it("AI 복사 글 — 공통 주식 '비교 못 함' 문장은 화면과 같다(no_data · not_comparable 구분)", () => {
    const body = (status: "no_data" | "not_comparable") =>
      buildMarketDiscoveryCopyText({
        asof: "2026-11-13",
        filters: {} as never,
        candidates: [],
        marketContext: null,
        constituentsAnalysis: analysisOf([]),
        crossFamily: cf({ status, stocks: [] }),
      });
    expect(body("no_data")).toContain(": 비교 못 함 — 원천 구성일이 확인된 구성 자료가 없습니다([구성종목 수집]으로 받습니다)");
    expect(body("not_comparable")).toContain(": 비교 못 함 — 같은 날짜에 주식 행이 있는 계열이 2개 미만입니다");
  });
});

describe("「섹터요약」 → 「후보리스트」(판정 Q17 (b) 제한)", () => {
  beforeEach(() => __resetEtfCompareCondition());
  it("상위권 카드에서 이 조건으로 「후보리스트」를 연다 · 화면 조건 · 저장된 기본값은 바꾸지 않는다(이동 한 번)", () => {
    const s = summaryOk({ basis: "three_month" });
    const nav = vi.fn();
    const before = getScreenCondition("candidates");
    render(<SectorSummary s={s} onNavigate={nav} />);
    expect(within(screen.getByTestId("ec-card-bottom")).queryByTestId("ec-to-candidates")).toBeNull();
    fireEvent.click(screen.getByTestId("ec-to-candidates"));
    expect(nav).toHaveBeenCalledWith("workbench");
    expect(getScreenCondition("candidates")).toBe(before); // 화면 조건 메모리 그대로(지적 frontend#6)
    expect(window.localStorage.getItem("krx.screenBasis.candidates.v1")).toBeNull();
    const once = takeOneTimeCondition("candidates");
    expect(once?.cond).toEqual({ basis: "three_month", filters: { ...s.filters } });
    expect(takeOneTimeCondition("candidates")).toBeNull(); // 한 번 꺼내면 비움
  });
});


describe("「ETF 구성종목」 버튼 배치(2026-11-16 사용자 직접 지시 — 맨 아래 → 제목 줄 · 형제 화면과 같은 중간 버튼)", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    for (const f of [fetchConstituentsAnalysis, fetchHoldingsMarketEvidence, fetchConstituentsCrossFamily, fetchConstituentsCollectStatus]) f.mockReset();
    fetchConstituentsAnalysis.mockResolvedValue({
      ...analysisOf([]),
      coverage: { requested_count: 1, available_count: 1, unavailable_count: 0 },
      constituents: [
        {
          etf_ticker: "476070",
          etf_name: null,
          status: "ok",
          source: "naver_stock_etf_component",
          asof: "2026-11-16",
          asof_confirmed: true,
          top_holdings: [{ rank: 1, ticker: "LLY", name: "일라이 릴리", weight_pct: 29.98 }],
          concentration: { top1_weight_pct: 29.98, top3_weight_pct: null, top5_weight_pct: null, top10_weight_pct: null },
        },
      ],
    });
    fetchConstituentsCrossFamily.mockResolvedValue(cf());
    fetchConstituentsCollectStatus.mockResolvedValue({ state: "idle", job_id: null, items: [] });
    fetchHoldingsMarketEvidence.mockResolvedValue({
      summary: { total_holdings_count: 0, matched_topn_count: 0, constituents_available_count: 0, nav_discount_unavailable_count: 0 },
      holdings: [],
      market_asof: null,
      holdings_asof: null,
    });
    saveETFExposureDraft({
      asof: "2026-11-13",
      filters: {} as never,
      candidate_snapshot: [{ ticker: "476070", name: "KODEX 글로벌비만치료제TOP2 Plus", one_month_return_pct: 14.67, tags: [] } as never],
      market_candidates: [],
      draft_created_at: "2026-11-16T00:00:00Z",
      list_scope: "「후보리스트」 1개월 상위 1개",
      list_condition: { basis: "one_month", side: "top", start: "2026-10-14", end: "2026-11-13", filters: {} as never },
    });
  });

  it("동작 버튼 3개는 제목 줄(중간 버튼) · 수집 상태 · 고른 후보 줄은 탭 위 · 설명 띠는 그 아래 · 영어 'AI Sessions' 없음", async () => {
    const nav = vi.fn();
    const { container } = render(<ETFExposureView onNavigate={nav} />);
    await waitFor(() => expect(fetchConstituentsAnalysis).toHaveBeenCalled());
    const head = container.querySelector(".ec-head") as HTMLElement;
    expect(within(head).getByRole("heading", { name: "ETF 구성종목" })).toBeTruthy();
    const names = within(head).getAllByRole("button").map((b) => b.textContent);
    expect(names).toEqual(["구성종목 수집", "보유 ETF 겹침 불러오기", "AI 투자 세션으로 넘기기"]);
    for (const b of within(head).getAllByRole("button")) expect(b.className).toBe("wb-btn btn-md");
    const before = (a: Element, b: Element) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
    const tabs = container.querySelector(".decision-tab-row") as HTMLElement;
    const banner = container.querySelector(".role-banner") as HTMLElement;
    const top = screen.getByTestId("exposure-top");
    expect(before(head, top) && before(top, banner) && before(banner, tabs)).toBe(true);
    expect(container.textContent).not.toContain("AI Sessions");
    expect(screen.queryByText(/보유 ETF 겹침 정보/)).toBeNull(); // 누르기 전에는 카드 없음
  });

  it("[보유 ETF 겹침 불러오기]를 누르면 결과 카드가 위쪽(탭 위)에 열린다", async () => {
    const { container } = render(<ETFExposureView onNavigate={vi.fn()} />);
    fireEvent.click(screen.getByTestId("exposure-bridge-load"));
    await waitFor(() => expect(screen.getByText(/보유 ETF 겹침 정보/)).toBeTruthy());
    expect(fetchHoldingsMarketEvidence).toHaveBeenCalledTimes(1);
    const card = screen.getByText(/보유 ETF 겹침 정보/).closest(".card") as HTMLElement;
    const tabs = container.querySelector(".decision-tab-row") as HTMLElement;
    expect(card.compareDocumentPosition(tabs) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(card.textContent).not.toContain("State Bridge");
  });

  it("후보를 고르면 위쪽 줄에 이름 · 1개월 수익률 · [보유와 후보 비교에서 보기 →](탭과 상관없이)", async () => {
    const nav = vi.fn();
    render(<ETFExposureView onNavigate={nav} />);
    expect(screen.getByTestId("exposure-picked").textContent).toBe(
      "후보는 구성 표의 [후보로 고르기] 또는 공통 주식 카드의 ETF 줄을 눌러 고릅니다",
    );
    expect(screen.getByTestId("exposure-picked").className).toBe("exp-picked");
    const pick = await screen.findByRole("button", { name: "후보로 고르기" });
    expect(pick.className).toBe("wb-btn btn-md"); // 줄 안 보조 동작 = 중간 버튼
    fireEvent.click(pick);
    expect(screen.getByTestId("exposure-picked").textContent).toContain("고른 후보: KODEX 글로벌비만치료제TOP2 Plus +14.67%");
    // 고르면 파란 줄 · 화면을 내려도 위에 붙는 줄(수집 상태 묶음 밖 · 화면 구역 바로 아래 · 위치 고정은 실화면 확인)
    expect(screen.getByTestId("exposure-picked").className).toBe("exp-picked exp-picked-on");
    expect(screen.getByTestId("exposure-top").contains(screen.getByTestId("exposure-picked"))).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "중복률" }));
    expect(screen.getByTestId("exposure-compare")).toBeTruthy(); // 탭을 바꿔도 위에 남음
    fireEvent.click(screen.getByTestId("exposure-compare"));
    expect(nav).toHaveBeenCalledWith("holding_candidate_compare");
  });
});


describe("검증자 r1 F4 — 수집 전에 시작한 늦은 읽기가 새 결과를 덮지 않는다(화면 두 탭 · AI 초안)", () => {
  const anz = (stockName: string) => ({
    ...analysisOf([]),
    coverage: { requested_count: 1, available_count: 1, unavailable_count: 0 },
    constituents: [
      {
        etf_ticker: "476070",
        etf_name: null,
        status: "ok",
        source: "naver_stock_etf_component",
        asof: "2026-11-16",
        asof_confirmed: true,
        top_holdings: [{ rank: 1, ticker: "LLY", name: stockName, weight_pct: 29.98 }],
        concentration: { top1_weight_pct: 29.98, top3_weight_pct: null, top5_weight_pct: null, top10_weight_pct: null },
      },
    ],
  });
  const deferred = <T,>() => {
    let resolve!: (v: T) => void;
    const promise = new Promise<T>((r) => (resolve = r));
    return { promise, resolve };
  };

  beforeEach(() => {
    window.sessionStorage.clear();
    for (const f of [fetchConstituentsAnalysis, fetchHoldingsMarketEvidence, fetchConstituentsCrossFamily, fetchConstituentsCollectStatus]) f.mockReset();
    saveETFExposureDraft({
      asof: "2026-11-13",
      filters: {} as never,
      candidate_snapshot: [{ ticker: "476070", name: "KODEX 글로벌비만치료제TOP2 Plus", one_month_return_pct: 14.67, tags: [] } as never],
      market_candidates: [],
      draft_created_at: "2026-11-16T00:00:00Z",
      list_scope: "「후보리스트」 1개월 상위 1개",
      list_condition: { basis: "one_month", side: "top", start: "2026-10-14", end: "2026-11-13", filters: {} as never },
    });
  });

  it("진입 때 읽기 2개가 수집 뒤 다시 읽기보다 늦게 와도 새 구성 · 새 공통 주식 유지 · AI 초안도 새 응답", async () => {
    const oldA = deferred<unknown>();
    const oldCf = deferred<unknown>();
    fetchConstituentsAnalysis.mockReturnValueOnce(oldA.promise).mockResolvedValue(anz("새 주식"));
    fetchConstituentsCrossFamily
      .mockReturnValueOnce(oldCf.promise)
      .mockResolvedValue(cf({ stocks: [stock("새 공통", 2, 2, 12)] }));
    // 화면 진입 = 이 목록 작업이 도는 중 → 상태 확인에서 끝남 → 분석 · 공통 주식 다시 읽기
    const job = { job_id: "j", kind: "candidates", tickers: ["476070"], target_date: "2026-11-13", total: 1, items: [] };
    fetchConstituentsCollectStatus
      .mockResolvedValueOnce({ ...job, state: "running", done: 0 })
      .mockResolvedValue({ ...job, state: "done", done: 1, counts: { fetched: 1 }, calls: 1 });
    const nav = vi.fn();
    render(<ETFExposureView onNavigate={nav} />);
    await waitFor(() => expect(fetchConstituentsAnalysis).toHaveBeenCalledTimes(2), { timeout: 4000 });
    await screen.findByText("새 주식");
    // 이제 늦은 이전 응답이 도착
    oldA.resolve(anz("옛 주식"));
    oldCf.resolve(cf({ stocks: [stock("옛 공통", 2, 2, 12)] }));
    await new Promise((r) => setTimeout(r, 30));
    expect(screen.queryByText("옛 주식")).toBeNull();
    expect(screen.getByText("새 주식")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "중복률" }));
    expect(screen.getByText("새 공통")).toBeTruthy();
    expect(screen.queryByText("옛 공통")).toBeNull();
    fireEvent.click(screen.getByTestId("exposure-to-ai"));
    const d = loadAISessionsDraft();
    expect(JSON.stringify(d?.constituent_snapshot)).toContain("새 주식");
    expect(JSON.stringify(d?.constituent_snapshot)).not.toContain("옛 주식");
    expect(JSON.stringify(d?.overlap_snapshot)).toContain("새 공통");
    expect(d?.question_text).toContain("새 공통");
    expect(d?.question_text).not.toContain("옛 공통");
  });
});
