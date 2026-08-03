// POC3-01 오늘의 투자 점검 — 핵심 UI 계약 test.
// @/lib/api 를 mock 해 응답을 통제한다. 실제 네트워크·운영 데이터 미의존.
//
// 검증 대상 (설계서 AC):
// - §3.1 강제 분리: 코스피 차트와 KODEX200 판정을 하나로 묶지 않는다 (별도 라벨).
// - AC-4/AC-5 큐 분리: 정비 항목(자료 상태)이 "오늘 내가 확인할 것" 에 없다.
// - AC-9 정직 표시: 미구현/미저장은 "개발 중"; 임시 숫자 없음.
// - AC-7 사용자 언어: 내부 용어(Evidence/Workbench/Unavailable/Pending/후보) 비노출.
// - AC-14 이동 버튼: ETF 비교하기 → workbench 라우팅.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within, act } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import LeftSidebar, { MENU_ITEMS } from "./LeftSidebar";

const fetchMarketTopnLatest = vi.fn();
const fetchEnrichedHoldings = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
const fetchNavDiscountLatest = vi.fn();
const fetchBenchmarkSeries = vi.fn();
const refreshMarket = vi.fn();

vi.mock("@/lib/api", () => ({
  fetchMarketTopnLatest: (...a: unknown[]) => fetchMarketTopnLatest(...a),
  fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
  fetchHoldingsMarketEvidence: (...a: unknown[]) => fetchHoldingsMarketEvidence(...a),
  fetchNavDiscountLatest: (...a: unknown[]) => fetchNavDiscountLatest(...a),
  fetchBenchmarkSeries: (...a: unknown[]) => fetchBenchmarkSeries(...a),
  refreshMarket: (...a: unknown[]) => refreshMarket(...a),
}));

import TodayInvestmentCheckView from "./TodayInvestmentCheckView";

// ── fixture ──────────────────────────────────────────────────────────────────
function marketOk(overrides: Record<string, unknown> = {}) {
  return {
    status: "ok",
    asof: "2026-07-24",
    candidates: [{ ticker: "069500" }, { ticker: "139260" }, { ticker: "305720" }],
    daily_topn: [],
    one_month_topn: [],
    three_month_topn: [],
    market_context: {
      status: "ok",
      asof: "2026-07-24",
      regime_label: "하락장",
      regime_code: "bear",
      warnings: [],
      kodex200: {
        status: "ok",
        close: 34000,
        ma20: 36000,
        ma60: 38000,
        ma20_position: "below",
        ma60_position: "below",
        ma20_distance_pct: -5.56,
        ma60_distance_pct: -10.53,
      },
      kospi: {
        status: "ok",
        return_1m_pct: -3.0,
        return_3m_pct: -8.0,
        // POC3-06 §6.2 실제값.
        daily_return_pct: -1.5,
        return_1y_pct: 12.3,
        high_52w_gap_pct: -7.4,
        as_of_date: "2026-07-24",
      },
      regime_streak: { regime_code: "bear", streak_days: 12, at_least: false },
      primary_benchmark: "KODEX200",
      regime_reasons: [],
    },
    market_risk_reference: {
      kodex200: { availability: "available", as_of_date: "2026-07-24", recent_20d_series: [] },
      vix: { availability: "available", as_of_date: "2026-07-03", recent_20d_series: [] },
    },
    ...overrides,
  };
}
function evidenceOk(overrides: Record<string, number> = {}) {
  return {
    status: "ok",
    asof: "2026-07-24",
    summary: {
      total_holdings_count: 2,
      matched_topn_count: 0,
      not_in_current_topn_count: 2,
      // 기본 fixture 에 light 항목(evidence_unavailable=1) + heavy 항목
      // (constituents_unavailable=2) 을 함께 둬 두 그룹 + 갱신 버튼이 렌더된다.
      evidence_unavailable_count: 1,
      constituents_available_count: 0,
      constituents_unavailable_count: 2,
      nav_discount_unavailable_count: 0,
      ...overrides,
    },
    holdings: [],
    warnings: [],
  };
}
function navOk() {
  return { status: "ok", asof: "2026-07-24", summary: { unavailable_count: 0, failed_count: 0 } };
}
function kospiSeriesOk() {
  return {
    ticker: "KOSPI",
    availability: "AVAILABLE",
    available_from: "2026-02-01",
    available_to: "2026-07-24",
    series: [
      { date: "2026-07-23", price: 2650 },
      { date: "2026-07-24", price: 2600 },
    ],
  };
}

// 기본 holdings: 현재가 결측 1건(light 항목 → 경량 갱신 버튼 렌더) + 정상 1건.
function holdingsOk() {
  return {
    items: [
      { ticker: "069500", name: "KODEX200", price_missing: false },
      { ticker: "133690", name: "TIGER", price_missing: true },
    ],
  };
}

function primeAll() {
  fetchMarketTopnLatest.mockResolvedValue(marketOk());
  fetchEnrichedHoldings.mockResolvedValue(holdingsOk());
  fetchHoldingsMarketEvidence.mockResolvedValue(evidenceOk());
  fetchNavDiscountLatest.mockResolvedValue(navOk());
  fetchBenchmarkSeries.mockResolvedValue(kospiSeriesOk());
  refreshMarket.mockResolvedValue({ status: "ok" });
}

beforeEach(() => {
  __resetQueryCache();
  vi.clearAllMocks();
  primeAll();
});

async function renderView() {
  const onNavigate = vi.fn();
  render(<TodayInvestmentCheckView onNavigate={onNavigate} />);
  // useSharedQuery 는 effect 로 조회 → resolve 후 상태 반영 대기.
  await screen.findByText("코스피 가격 흐름");
  return { onNavigate };
}

describe("TodayInvestmentCheckView", () => {
  it("세 영역이 모두 보인다 (10초 과업 구조)", async () => {
    await renderView();
    // 코스피 대표(라벨) · 판단 큐 · 정비 큐 세 영역이 각각 존재.
    expect(screen.getByLabelText("KOSPI 현재 위치")).toBeInTheDocument();
    expect(screen.getByLabelText("오늘 내가 확인할 것")).toBeInTheDocument();
    expect(screen.getByLabelText("자료 최신화 필요")).toBeInTheDocument();
    // 대표 제목은 "KOSPI".
    expect(screen.getByRole("heading", { name: "KOSPI" })).toBeInTheDocument();
  });

  it("§4.1: 코스피 대표 영역이 전체 폭(최상단)이다 — 판단/정비 큐와 같은 열에 있지 않다", async () => {
    await renderView();
    const headline = screen.getByLabelText("KOSPI 현재 위치");
    const judgment = screen.getByLabelText("오늘 내가 확인할 것");
    // 코스피 헤드라인은 큐 grid(.tc-queue-grid) 안에 들어있지 않아야 한다
    // (2열 큐와 나란히 배치되면 반쪽 폭 → §4.1 위반).
    expect(headline.closest(".tc-queue-grid")).toBeNull();
    // 판단 큐는 큐 grid 안에 있다 (코스피 아래 2열).
    expect(judgment.closest(".tc-queue-grid")).not.toBeNull();
    // 헤드라인은 tc-root 의 직접 자식(전체 폭 카드).
    expect(headline.parentElement).toHaveClass("tc-root");
  });

  it("코스피 기간 수익률(1M/3M)을 표시한다 (저장 KOSPI 시계열)", async () => {
    fetchMarketTopnLatest.mockResolvedValue(
      marketOk({
        market_context: {
          status: "ok",
          asof: "2026-07-24",
          regime_label: "하락장",
          regime_code: "bear",
          warnings: [],
          kodex200: {
            status: "ok",
            close: 34000,
            ma20: 36000,
            ma60: 38000,
            ma20_position: "below",
            ma60_position: "below",
            ma20_distance_pct: -5.56,
            ma60_distance_pct: -10.53,
          },
          kospi: {
            status: "ok",
            return_1m_pct: -25.08,
            return_3m_pct: 3.32,
          },
          primary_benchmark: "KODEX200",
          regime_reasons: [],
        },
      }),
    );
    await renderView();
    const headline = screen.getByLabelText("KOSPI 현재 위치");
    expect(within(headline).getByText(/1개월/)).toBeInTheDocument();
    expect(within(headline).getByText(/3개월/)).toBeInTheDocument();
  });

  it("§3.1 강제 분리: KODEX200 판정을 코스피와 별도 라벨로 표기한다", async () => {
    await renderView();
    // "기존 시장 판정 참고 · KODEX200 기준" 라벨이 코스피 차트와 분리되어 있어야.
    expect(screen.getByText(/기존 시장 판정 참고/)).toBeInTheDocument();
    expect(screen.getByText("하락장")).toBeInTheDocument();
    // "코스피 상승장/코스피 시장 상태" 처럼 두 기준을 합친 표현이 없어야 (FAIL 조건).
    expect(screen.queryByText(/코스피 시장 상태/)).toBeNull();
    expect(screen.queryByText(/코스피 하락장/)).toBeNull();
  });

  it("KODEX200 MA20·MA60 대비 거리를 각각 명시한다 (단일 '전환까지 거리' 아님)", async () => {
    await renderView();
    expect(screen.getByText(/KODEX200 MA20 대비/)).toBeInTheDocument();
    expect(screen.getByText(/KODEX200 MA60 대비/)).toBeInTheDocument();
  });

  it("POC3-06 §3.2: KOSPI 일간·1년·고점 대비·지속일이 실제값으로 표시된다", async () => {
    await renderView();
    const headline = screen.getByLabelText("KOSPI 현재 위치");
    const text = headline.textContent ?? "";
    // 일간·1년·최근 1년 고점 대비 실제값 (개발 중 자리표시자 아님).
    expect(text).toContain("일간");
    expect(text).toContain("최근 1년 고점 대비");
    // 흐름 지속 거래일 수 실제값.
    expect(text).toContain("12거래일째");
    // 개발 중 자리표시자는 headline 에 없다.
    expect(text).not.toContain("개발 중");
  });

  it("AC-13: 거래량·공격방어·SuperTrend 는 이번 단계 미도입으로 남는다", async () => {
    await renderView();
    const detail = screen.getByLabelText("코스피 상세 (개발 중)");
    // 이번 단계 미도입 부류만 남는다 (개발 중 4항목 제거됨).
    expect(within(detail).getByText("거래량 흐름")).toBeInTheDocument();
    expect(within(detail).getByText("공격·방어 비중")).toBeInTheDocument();
    expect(within(detail).getByText(/SuperTrend/)).toBeInTheDocument();
    expect(within(detail).queryByText("일간 등락률")).toBeNull();
    expect(within(detail).queryByText("1년 수익률")).toBeNull();
    // 거래량 미저장 사유는 hover 툴팁(title)로 제공.
    const volInfo = within(detail).getByRole("note", {
      name: /거래량 자료를 저장하지 않아/,
    });
    expect(volInfo).toHaveAttribute("title", expect.stringContaining("저장하지 않아"));
  });

  it("§4.4 board: 개발 중 + 이번 단계 미도입 기능을 모두 기록한다", async () => {
    await renderView();
    const board = screen.getByLabelText("개발 중인 판단 기능");
    expect(within(board).getByText("내가 가진 ETF의 위험 신호")).toBeInTheDocument();
    expect(within(board).getByText(/공격·방어 비중/)).toBeInTheDocument();
    expect(within(board).getByText(/SuperTrend/)).toBeInTheDocument();
    // 두 부류 구분 라벨 (미도입 배지가 여러 개라 getAllByText).
    expect(within(board).getByText(/준비 중/)).toBeInTheDocument();
    expect(within(board).getAllByText(/이번 단계 미도입/).length).toBeGreaterThan(0);
  });

  it("AC-4/AC-5 큐 분리: 정비 항목이 '오늘 내가 확인할 것' 안에 없다", async () => {
    await renderView();
    const judgment = screen.getByLabelText("오늘 내가 확인할 것");
    // 판단 큐 안에는 자료 상태 문구가 없어야 한다.
    expect(within(judgment).queryByText(/자료가 없습니다/)).toBeNull();
    expect(within(judgment).queryByText(/오래되었습니다/)).toBeNull();
    expect(within(judgment).queryByText(/지금 다시 불러오기/)).toBeNull();
    // 정비 항목은 정비 큐 안에 있어야 한다 (구성종목 미수집 2건 fixture).
    const maint = screen.getByLabelText("자료 최신화 필요");
    expect(
      within(maint).getByText(/ETF가 담고 있는 종목 자료가 없습니다/),
    ).toBeInTheDocument();
  });

  it("§4.3: 정비 큐 — light 는 '업데이트' 버튼, heavy 는 상세 이동 버튼 (그룹 라벨 없음)", async () => {
    // fixture: constituents_unavailable(heavy) + 기본 holdings price_missing(light).
    fetchHoldingsMarketEvidence.mockResolvedValue(
      evidenceOk({ evidence_unavailable_count: 2, constituents_unavailable_count: 1 }),
    );
    await renderView();
    const maint = screen.getByLabelText("자료 최신화 필요");
    // 그룹 라벨("보유 현재가"·"상세 화면에서 업데이트")·상태줄 삭제됨.
    expect(within(maint).queryByText("보유 현재가")).toBeNull();
    expect(within(maint).queryByText("상세 화면에서 업데이트")).toBeNull();
    // light 는 정확히 "업데이트" 버튼, heavy 는 "…업데이트로" 이동 버튼.
    expect(
      within(maint).getByRole("button", { name: "업데이트" }),
    ).toBeInTheDocument();
    expect(
      within(maint).getByRole("button", { name: "구성종목 업데이트로" }),
    ).toBeInTheDocument();
  });

  it("ⓘ 근거: 각 정비 항목에 최신이 아닌 근거(비교 대상)가 툴팁으로 붙는다", async () => {
    await renderView();
    const maint = screen.getByLabelText("자료 최신화 필요");
    // VIX 항목 ⓘ 에 기준일 비교 근거.
    const notes = within(maint).getAllByRole("note");
    expect(notes.length).toBeGreaterThan(0);
    // 근거 문구에 실제 비교 대상(기준일/NAV/구성종목 등)이 들어간다.
    const anyReason = notes.some((n) =>
      /기준일|순자산가치|NAV|구성종목|시장 위치|현재가/.test(n.getAttribute("title") ?? ""),
    );
    expect(anyReason).toBe(true);
  });

  it("B-1: NAV 집계 필드 손상 시 0건 위장이 아니라 '확인할 수 없습니다' 로 표시", async () => {
    // 필수 집계값이 숫자가 아닌(손상) 응답 → 정상 0건처럼 숨기지 않는다.
    fetchNavDiscountLatest.mockResolvedValue({
      status: "ok",
      asof: "2026-07-24",
      summary: { unavailable_count: null, failed_count: undefined },
    });
    await renderView();
    const maint = screen.getByLabelText("자료 최신화 필요");
    expect(
      within(maint).getByText(/ETF 기준가 자료 상태를 확인할 수 없습니다/),
    ).toBeInTheDocument();
  });

  it("AC-7 사용자 언어: 본문 + 툴팁(title/aria-label)에 내부 용어가 없다", async () => {
    await renderView();
    // 본문 텍스트 + hover 툴팁(title)·접근성 라벨(aria-label)까지 모두 검사한다.
    // (title/aria-label 도 사용자에게 실제 노출 → 이전 테스트가 title 을 놓쳐 후보 누락.)
    const parts: string[] = [document.body.textContent ?? ""];
    document.body.querySelectorAll("[title]").forEach((el) => {
      parts.push(el.getAttribute("title") ?? "");
    });
    document.body.querySelectorAll("[aria-label]").forEach((el) => {
      parts.push(el.getAttribute("aria-label") ?? "");
    });
    const all = parts.join(" ");
    for (const term of [
      "Evidence",
      "Workbench",
      "Unavailable",
      "Pending",
      "Operations Panel",
      "후보",
    ]) {
      expect(all).not.toContain(term);
    }
  });

  it("판단 큐: 요즘 잘 오르는 ETF 건수 + ETF 비교하기 이동", async () => {
    const onNavigate = vi.fn();
    render(<TodayInvestmentCheckView onNavigate={onNavigate} />);
    await screen.findByText("코스피 가격 흐름");
    expect(await screen.findByText("3개")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "ETF 비교하기" }));
    expect(onNavigate).toHaveBeenCalledWith("workbench");
  });

  it("AC-14 정비 이동: 항목별 직접 라우팅 (구성종목 → etf_exposure)", async () => {
    const onNavigate = vi.fn();
    render(<TodayInvestmentCheckView onNavigate={onNavigate} />);
    await screen.findByText("코스피 가격 흐름");
    fireEvent.click(await screen.findByRole("button", { name: "구성종목 업데이트로" }));
    expect(onNavigate).toHaveBeenCalledWith("etf_exposure");
  });

  it("Q7 경량 갱신: 지금 다시 불러오기 → holdings/market/refresh 호출", async () => {
    await renderView();
    fireEvent.click(screen.getByRole("button", { name: "업데이트" }));
    expect(refreshMarket).toHaveBeenCalledTimes(1);
    // 무거운 갱신(POST /market/refresh)은 호출하지 않는다 — mock 자체가 없다.
    await screen.findByText(/완료/);
  });

  it("핵심 정정: 갱신으로 현재가 결측이 해소되면 light 항목이 목록에서 사라진다", async () => {
    // 최초: 현재가 결측 1건 → light 항목 노출. 갱신 후 결측 0건으로 응답 → 사라짐.
    await renderView();
    expect(
      screen.getByText(/보유 종목 현재가를 불러오지 못했습니다/),
    ).toBeInTheDocument();
    // 갱신 후 재조회 시에는 결측 없는 holdings 를 반환하도록 설정.
    fetchEnrichedHoldings.mockResolvedValue({
      items: [{ ticker: "069500", name: "KODEX200", price_missing: false }],
    });
    fireEvent.click(screen.getByRole("button", { name: "업데이트" }));
    await screen.findByText(/완료/);
    // light 항목(현재가 결측)이 사라져야 한다 (계약과 동작 일치 · 사용자 지적 6번).
    await waitFor(() => {
      expect(
        screen.queryByText(/보유 종목 현재가를 불러오지 못했습니다/),
      ).toBeNull();
    });
  });

  it("재분류: evidence stale·NAV 는 heavy(상세 이동), 경량 갱신 대상 아님", async () => {
    // 현재가는 정상(결측 0) + evidence stale 1건 → light 없음, heavy 만.
    fetchEnrichedHoldings.mockResolvedValue({
      items: [{ ticker: "069500", name: "KODEX200", price_missing: false }],
    });
    fetchHoldingsMarketEvidence.mockResolvedValue(
      evidenceOk({ evidence_unavailable_count: 2, constituents_unavailable_count: 0 }),
    );
    await renderView();
    const maint = screen.getByLabelText("자료 최신화 필요");
    // evidence stale 은 상세 이동 버튼("시장 자료 업데이트로")으로 노출 (VIX stale 도
    // 같은 라벨이라 1개 이상).
    expect(
      within(maint).getAllByRole("button", { name: "시장 자료 업데이트로" }).length,
    ).toBeGreaterThan(0);
    // 현재가 결측이 없어도 갱신 버튼은 항상 표시(사용자 확정) — 다만 최신 상태 힌트.
    expect(
      within(maint).getByRole("button", { name: "업데이트" }),
    ).toBeInTheDocument();
    expect(within(maint).getByText(/현재가는 최신 상태입니다/)).toBeInTheDocument();
    // light 항목(현재가 결측 문구)은 목록에 없다.
    expect(
      within(maint).queryByText(/보유 종목 현재가를 불러오지 못했습니다/),
    ).toBeNull();
  });

  it("UI 정정: 경량 갱신 버튼('업데이트')은 정확히 1개다 (중복 제거)", async () => {
    await renderView();
    // 경량 갱신 버튼은 이름이 정확히 "업데이트" 인 것 1개 (heavy 의 "…업데이트로" 와 구분).
    const buttons = screen.getAllByRole("button", { name: "업데이트" });
    expect(buttons.length).toBe(1);
  });

  it("UI 정정: 갱신 완료 후 상태 문구가 '완료' 로 바뀐다", async () => {
    await renderView();
    fireEvent.click(screen.getByRole("button", { name: "업데이트" }));
    // 완료 문구가 실제로 나타나야 한다 (불러오는 중에 갇히지 않음).
    expect(await screen.findByText(/완료/)).toBeInTheDocument();
    // 버튼도 다시 활성(불러오는 중 아님)으로 돌아온다.
    expect(
      screen.getByRole("button", { name: "업데이트" }),
    ).not.toBeDisabled();
  });

  it("Q7 정정: 갱신 성공 후 Holdings·Evidence·NAV 를 모두 재조회한다 (최신 반영)", async () => {
    await renderView();
    // 초기 마운트 조회 1회씩.
    const holdCalls0 = fetchEnrichedHoldings.mock.calls.length;
    const evidCalls0 = fetchHoldingsMarketEvidence.mock.calls.length;
    const navCalls0 = fetchNavDiscountLatest.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "업데이트" }));
    await screen.findByText(/완료/);
    // 갱신 후 Holdings·Evidence·NAV GET 이 모두 다시 호출돼야 한다 (r5 A-1 정정:
    // NAV 를 light 로 분류했으면 NAV 도 실제로 재조회해야 계약과 동작 일치).
    await waitFor(() => {
      expect(fetchEnrichedHoldings.mock.calls.length).toBeGreaterThan(holdCalls0);
      expect(fetchHoldingsMarketEvidence.mock.calls.length).toBeGreaterThan(evidCalls0);
      expect(fetchNavDiscountLatest.mock.calls.length).toBeGreaterThan(navCalls0);
    });
  });

  it("r5 A-1: NAV 재조회 실패 시 '완료' 로 위장하지 않는다 (거짓 완료 금지)", async () => {
    await renderView();
    // POST·Holdings·Evidence 는 성공하지만 NAV 재조회만 실패.
    fetchNavDiscountLatest.mockRejectedValueOnce(new Error("nav-network"));
    fireEvent.click(screen.getByRole("button", { name: "업데이트" }));
    await screen.findByText(/· 실패/);
    expect(screen.queryByText(/· 완료/)).toBeNull();
  });

  it("A-1(4): 재조회 실패 시 '완료' 를 표시하지 않는다 (거짓 완료 금지)", async () => {
    await renderView();
    // 갱신 POST 는 성공하지만 이어지는 보유 재조회가 실패하도록 설정.
    fetchEnrichedHoldings.mockRejectedValueOnce(new Error("network"));
    fireEvent.click(screen.getByRole("button", { name: "업데이트" }));
    // "· 실패" 가 뜨고 "· 완료" 는 뜨지 않는다.
    await screen.findByText(/· 실패/);
    expect(screen.queryByText(/· 완료/)).toBeNull();
  });

  it("§4.3: 갱신 성공 후 light 행에 '· 완료' 피드백이 붙는다", async () => {
    await renderView();
    fireEvent.click(screen.getByRole("button", { name: "업데이트" }));
    // 완료 후 light 행 문구에 "· 완료" 가 나타난다 (별도 상태줄 없음).
    expect(await screen.findByText(/· 완료/)).toBeInTheDocument();
  });

  it("정정: 최신 상태 행에도 ⓘ 근거가 붙는다 (다른 항목과 통일)", async () => {
    // 현재가 결측 0 → "최신" 행. 그 행에도 ⓘ note 가 있어야 한다.
    fetchEnrichedHoldings.mockResolvedValue({
      items: [{ ticker: "069500", name: "KODEX200", price_missing: false }],
    });
    await renderView();
    const freshText = screen.getByText(/보유 종목 현재가는 최신 상태입니다/);
    const row = freshText.closest("li");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByRole("note")).toHaveAttribute("title");
  });

  it("정정: '· 완료' 피드백은 3초 뒤 자동으로 사라진다", async () => {
    vi.useFakeTimers();
    try {
      const onNavigate = vi.fn();
      render(<TodayInvestmentCheckView onNavigate={onNavigate} />);
      // 초기 조회(promise) flush — microtask 만 소모, 3초 타이머는 아직 안 건드림.
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
      });
      fireEvent.click(screen.getByRole("button", { name: "업데이트" }));
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
      });
      expect(screen.getByText(/· 완료/)).toBeInTheDocument();
      // 3초 경과 후 idle 복귀 → "· 완료" 사라짐.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3100);
      });
      expect(screen.queryByText(/· 완료/)).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("AC-11: MA 한계 설명은 hover 툴팁(title)이며 항상 노출 문단이 아니다", async () => {
    await renderView();
    const info = screen.getByRole("note", { name: /이동평균 기준선까지의 거리/ });
    expect(info).toHaveAttribute("title");
    // 짧은 마커만 노출, 전체 설명은 title/aria 에.
    expect(info.textContent).toContain("이 값의 한계");
  });

  it("B-1: MA 거리 결측은 '자료 없음' 으로 정직 표시 ('-' 아님)", async () => {
    fetchMarketTopnLatest.mockResolvedValue(
      marketOk({
        market_context: {
          status: "ok",
          asof: "2026-07-24",
          regime_label: "보합장",
          regime_code: "neutral",
          warnings: [],
          kodex200: {
            status: "ok",
            close: 34000,
            ma20: null,
            ma60: null,
            ma20_position: null,
            ma60_position: null,
            ma20_distance_pct: null,
            ma60_distance_pct: null,
          },
          kospi: {},
          primary_benchmark: "KODEX200",
          regime_reasons: [],
        },
      }),
    );
    await renderView();
    expect(screen.getByText(/KODEX200 MA20 대비 자료 없음/)).toBeInTheDocument();
  });

  // 금지 용어: 라틴 내부 용어 + 한국어 금지 용어. label·hint 모두 적용.
  // 2026-08-02 POC3-05 DESIGN_V2: "확인 근거" 가 설계서 §4.1·§4.4 가 명시한 사용자 화면
  //   메뉴 라벨이 되어 "근거" 는 금지어에서 제외한다(V2 AC-2·AC-7). V2 AC-19 사용자 금지어
  //   (저위험/고위험/안전/매도/손절/BUY/SELL)에는 "근거" 가 없다. "후보" 는 계속 금지.
  const FORBIDDEN_TERMS = [
    "Workbench",
    "Market Discovery",
    "ETF Exposure",
    "Holdings",
    "Dashboard",
    "Approval",
    "Data Status",
    "Evidence",
    "Unavailable",
    "Pending",
    "Operations Panel",
    "후보",
  ];

  it("AC-7: 좌측 메뉴 전체 텍스트(라벨+힌트)에 금지 용어가 없다 (Sidebar 실제 렌더)", () => {
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    const text = document.body.textContent ?? "";
    for (const term of FORBIDDEN_TERMS) {
      expect(text).not.toContain(term);
    }
    // 사용자 언어 라벨이 실제로 있는지도 확인.
    expect(text).toContain("요즘 잘 오르는 ETF");
    expect(text).toContain("보유 현황");
    expect(text).toContain("ETF 비교하기");
  });

  it("AC-7 보강: MENU_ITEMS 의 label·hint 모두 금지 용어가 없다", () => {
    for (const item of MENU_ITEMS) {
      for (const term of FORBIDDEN_TERMS) {
        expect(item.label).not.toContain(term);
        expect(item.hint ?? "").not.toContain(term);
      }
    }
  });

  it("AC-1: 정비 큐 제목에 총 건수를 표시한다 (몇 건인지 한눈에)", async () => {
    await renderView();
    const maint = screen.getByLabelText("자료 최신화 필요");
    // 제목(h2) 안에 총 건수 배지가 있어야 한다 (항목별 "(N건)" 과 구분).
    const heading = within(maint).getByRole("heading", { level: 2 });
    expect(heading.textContent).toMatch(/\d+건/);
  });

  it("POC3-05 §7·AC-13: 판단 큐에서 보유 현황·확인 근거로 직접 이동한다", async () => {
    const { onNavigate } = await renderView();
    const judgment = screen.getByLabelText("오늘 내가 확인할 것");
    // 개발 중 자리표시자 대신 실제 동선. "개발 중" 뱃지는 이 영역에 없다.
    expect(within(judgment).getByText("내가 가진 ETF")).toBeInTheDocument();

    fireEvent.click(within(judgment).getByRole("button", { name: "보유 현황" }));
    expect(onNavigate).toHaveBeenCalledWith("holdings");

    fireEvent.click(within(judgment).getByRole("button", { name: "확인 근거" }));
    expect(onNavigate).toHaveBeenCalledWith("holdings_evidence");
  });

  it("AC-14: 자료 확인 필요 건수가 '확인 근거' 화면과 동일 판정(buildRiskEvidenceRows)을 쓴다", async () => {
    // short_term_momentum.status=partial → computeNeedCheck=true 이지만 backend
    // evidence_unavailable_count 는 0. 오늘 화면이 backend count 를 쓰면 0건,
    // 확인 근거와 같은 판정(computeNeedCheck)을 쓰면 1건. 후자여야 한다(화면 간 정합).
    fetchEnrichedHoldings.mockResolvedValue({
      items: [
        {
          ticker: "069500", name: "KODEX200", quantity: 10, avg_buy_price: 1000,
          invested_amount: 10000, current_price: 1100, price_asof: "2026-07-24",
          price_source: "naver", eval_amount: 11000, pnl_amount: 1000,
          pnl_rate_pct: 10, buy_weight_pct: 50, market_weight_pct: 50,
          price_missing: false, calc_missing: false,
        },
      ],
    });
    fetchHoldingsMarketEvidence.mockResolvedValue({
      status: "ok", asof: "2026-07-24", holdings_asof: "2026-07-24", market_asof: "2026-07-24",
      market_context: null,
      summary: {
        total_holdings_count: 1, matched_topn_count: 0, not_in_current_topn_count: 1,
        evidence_unavailable_count: 0, constituents_available_count: 1,
        constituents_unavailable_count: 0, nav_discount_unavailable_count: 0,
      },
      holdings: [
        {
          ticker: "069500", name: "KODEX200",
          holding: { quantity: 10, avg_buy_price: 1000, evaluation_amount: 11000, pnl_rate_pct: 10 },
          topn_match: { status: "unavailable", rank: null, basis: null, candidate_name: null },
          returns: { status: "ok", one_month_return_pct: 1, three_month_return_pct: 2 },
          excess_return: { status: "ok", vs_kodex200_1m_pctp: 1, vs_kodex200_3m_pctp: 2 },
          short_term_momentum: {
            status: "partial", return_5d_pct: -1, return_10d_pct: null, return_20d_pct: null,
            excess_vs_kodex200_5d_pctp: null, excess_vs_kodex200_10d_pctp: null, excess_vs_kodex200_20d_pctp: null,
          },
          constituents_overlap: { status: "ok", overlap_with_market_core: [] },
          nav_discount: { status: "ok", source: null, asof: null, nav: null, market_price: null, discount_rate_pct: null, flag: null, message: null },
          evidence_notes: [],
        },
      ],
      warnings: [],
    });
    await renderView();
    const judgment = screen.getByLabelText("오늘 내가 확인할 것");
    // computeNeedCheck 기준 1건(partial). backend count(0)를 썼다면 이 문구가 없어야 한다.
    expect(within(judgment).getByText(/자료 확인 필요 1건/)).toBeInTheDocument();
  });

  it("§6.4: Evidence 조회 실패여도 성공한 보유 종목 수는 확인 불가로 덮이지 않는다", async () => {
    fetchEnrichedHoldings.mockResolvedValue({
      items: [
        { ticker: "069500", name: "KODEX200", price_missing: false },
        { ticker: "133690", name: "TIGER", price_missing: false },
      ],
    });
    // Evidence 만 실패 — holdings 는 성공.
    fetchHoldingsMarketEvidence.mockRejectedValue(new Error("evidence down"));
    await renderView();
    const judgment = screen.getByLabelText("오늘 내가 확인할 것");
    // "내가 가진 ETF" head 에 보유 수(2)가 확정 표시되고 "확인 불가" 는 없다.
    const holdHead = within(judgment)
      .getByText("내가 가진 ETF")
      .closest(".tc-queue-head") as HTMLElement;
    expect(holdHead.textContent).toContain("2");
    expect(holdHead.textContent).toContain("개");
    expect(holdHead.textContent).not.toContain("확인 불가");
    // 자료 확인 필요 건수는 evidence 없으니 표시하지 않는다(오해 방지).
    expect(within(judgment).queryByText(/자료 확인 필요/)).toBeNull();
  });

  it("POC3-06 §6.1·AC-2·6·7: Dashboard 판단 큐가 오늘 먼저 볼 보유 ETF 최대 3건을 표시한다", async () => {
    // 5일 값이 다른 두 종목 → lowestFiveDayRows(= backend select_top_holdings 동일 규칙)
    // 로 5일 낮은 순 표시. Dashboard 가 실제로 이 목록을 렌더링해야 한다(REJECTED #1).
    const enriched = (ticker: string, name: string) => ({
      ticker, name, quantity: 10, avg_buy_price: 1000,
      invested_amount: 10000, current_price: 1100, price_asof: "2026-07-24",
      price_source: "naver", eval_amount: 11000, pnl_amount: 1000,
      pnl_rate_pct: 10, buy_weight_pct: 50, market_weight_pct: 50,
      price_missing: false, calc_missing: false,
    });
    const evItem = (ticker: string, name: string, r5: number) => ({
      ticker, name,
      holding: { quantity: 10, avg_buy_price: 1000, evaluation_amount: 11000, pnl_rate_pct: 10 },
      topn_match: { status: "unavailable", rank: null, basis: null, candidate_name: null },
      returns: { status: "ok", one_month_return_pct: 1, three_month_return_pct: 2 },
      excess_return: { status: "ok", vs_kodex200_1m_pctp: 1, vs_kodex200_3m_pctp: 2 },
      short_term_momentum: {
        status: "ok", return_5d_pct: r5, return_10d_pct: -2, return_20d_pct: -3,
        excess_vs_kodex200_5d_pctp: -0.5, excess_vs_kodex200_10d_pctp: -1,
        excess_vs_kodex200_20d_pctp: -1.5,
      },
      constituents_overlap: { status: "ok", overlap_with_market_core: [] },
      nav_discount: { status: "ok", source: null, asof: null, nav: null, market_price: null, discount_rate_pct: null, flag: null, message: null },
      evidence_notes: [],
    });
    fetchEnrichedHoldings.mockResolvedValue({
      items: [enriched("069500", "코덱스200"), enriched("133690", "타이거나스닥")],
    });
    fetchHoldingsMarketEvidence.mockResolvedValue({
      status: "ok", asof: "2026-07-24", holdings_asof: "2026-07-24", market_asof: "2026-07-24",
      market_context: null,
      summary: {
        total_holdings_count: 2, matched_topn_count: 0, not_in_current_topn_count: 2,
        evidence_unavailable_count: 0, constituents_available_count: 2,
        constituents_unavailable_count: 0, nav_discount_unavailable_count: 0,
      },
      holdings: [evItem("069500", "코덱스200", -1), evItem("133690", "타이거나스닥", -8)],
      warnings: [],
    });
    await renderView();
    const judgment = screen.getByLabelText("오늘 내가 확인할 것");
    // 최대 3건 목록에 두 ETF 모두 표시.
    expect(within(judgment).getByText("타이거나스닥")).toBeInTheDocument();
    expect(within(judgment).getByText("코덱스200")).toBeInTheDocument();
    // 5일 낮은 순: 타이거나스닥(-8) 이 코덱스200(-1) 보다 먼저.
    const text = judgment.textContent ?? "";
    expect(text.indexOf("타이거나스닥")).toBeLessThan(text.indexOf("코덱스200"));
  });
});
