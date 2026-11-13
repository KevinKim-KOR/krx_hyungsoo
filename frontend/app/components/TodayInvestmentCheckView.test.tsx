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
import { detailResponse, summaryOk } from "@/lib/etfCompareTestFixtures";
import { quickOk } from "@/lib/quickQuotesTestFixtures";
import { morningOk, shortOk } from "@/lib/morningTestFixtures";

const fetchMarketTopnLatest = vi.fn();
const fetchEnrichedHoldings = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
const fetchNavDiscountLatest = vi.fn();
const fetchBenchmarkSeries = vi.fn();
const refreshMarket = vi.fn();
const fetchOciStartupStatus = vi.fn();
const fetchMarketRefreshStatus = vi.fn();
// POC6-29 — [최신 자료 갱신] 묶음 작업 · 잘 오르는 ETF · 보유 점검 요약(같은 요약 응답).
const postRefreshAll = vi.fn();
const fetchRefreshAllStatus = vi.fn();
const fetchEtfCompareSummary = vi.fn();

vi.mock("@/lib/api/etfCompare", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchEtfCompareSummary: (...a: unknown[]) => fetchEtfCompareSummary(...a),
}));

vi.mock("@/lib/api/refreshAll", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  postRefreshAll: (...a: unknown[]) => postRefreshAll(...a),
  fetchRefreshAllStatus: (...a: unknown[]) => fetchRefreshAllStatus(...a),
}));

vi.mock("@/lib/api", () => ({
  fetchMarketTopnLatest: (...a: unknown[]) => fetchMarketTopnLatest(...a),
  fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
  fetchHoldingsMarketEvidence: (...a: unknown[]) => fetchHoldingsMarketEvidence(...a),
  fetchNavDiscountLatest: (...a: unknown[]) => fetchNavDiscountLatest(...a),
  fetchBenchmarkSeries: (...a: unknown[]) => fetchBenchmarkSeries(...a),
  refreshMarket: (...a: unknown[]) => refreshMarket(...a),
  fetchOciStartupStatus: (...a: unknown[]) => fetchOciStartupStatus(...a),
  fetchMarketRefreshStatus: (...a: unknown[]) => fetchMarketRefreshStatus(...a),
}));

const fetchMarketFlowContext = vi.fn();
const fetchForwardComparison = vi.fn();
const fetchLedgerLatestByKind = vi.fn();
vi.mock("@/lib/api/marketFlow", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchMarketFlowContext: (...a: unknown[]) => fetchMarketFlowContext(...a),
}));
vi.mock("@/lib/api/mlForwardComparison", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchForwardComparison: (...a: unknown[]) => fetchForwardComparison(...a),
}));
vi.mock("@/lib/api/decisionLedger", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchLedgerLatestByKind: (...a: unknown[]) => fetchLedgerLatestByKind(...a),
}));

// POC6-29 보완 — 빠른 시세 저장값 · KODEX 200 상세(시장 판정 문장 기준 · 갱신 전후 대조)도 가짜로 둔다.
const fetchQuickQuotes = vi.fn();
const fetchEtfDetail = vi.fn();
vi.mock("@/lib/api/quickQuotes", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchQuickQuotes: (...a: unknown[]) => fetchQuickQuotes(...a),
}));
const fetchMorningBasis = vi.fn();
const fetchShortFlows = vi.fn();
vi.mock("@/lib/api/morningBasis", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/morningBasis")>()),
  fetchMorningBasis: (...a: unknown[]) => fetchMorningBasis(...a),
}));
vi.mock("@/lib/api/shortFlows", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/shortFlows")>()),
  fetchShortFlows: (...a: unknown[]) => fetchShortFlows(...a),
}));
vi.mock("@/lib/api/etfDetail", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchEtfDetail: (...a: unknown[]) => fetchEtfDetail(...a),
}));

import TodayInvestmentCheckView from "./TodayInvestmentCheckView";

// ── fixture ──────────────────────────────────────────────────────────────────
function marketOk(overrides: Record<string, unknown> = {}) {
  return {
    status: "ok",
    asof: "2026-07-24",
    basis: "one_month",
    order: "desc",
    n: 10,
    filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
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
  fetchQuickQuotes.mockReset().mockResolvedValue(quickOk());
  fetchMorningBasis.mockReset().mockResolvedValue(morningOk());
  fetchShortFlows.mockReset().mockResolvedValue(shortOk());
  fetchEtfDetail.mockReset().mockImplementation((ts: string[]) => Promise.resolve(detailResponse(ts)));
  fetchMarketTopnLatest.mockResolvedValue(marketOk());
  fetchEnrichedHoldings.mockResolvedValue(holdingsOk());
  fetchHoldingsMarketEvidence.mockResolvedValue(evidenceOk());
  fetchNavDiscountLatest.mockResolvedValue(navOk());
  fetchBenchmarkSeries.mockResolvedValue(kospiSeriesOk());
  refreshMarket.mockResolvedValue({ status: "ok" });
  fetchOciStartupStatus.mockResolvedValue(ociOk());
  fetchMarketFlowContext.mockRejectedValue(new Error("flow down"));
  fetchForwardComparison.mockRejectedValue(new Error("forward down"));
  fetchLedgerLatestByKind.mockRejectedValue(new Error("ledger down"));
  fetchMarketRefreshStatus.mockResolvedValue({ status: "idle", refresh_id: null, cooldown_remaining_seconds: 0 });
  fetchRefreshAllStatus.mockResolvedValue(refreshIdle());
  postRefreshAll.mockResolvedValue(refreshIdle());
  fetchEtfCompareSummary.mockResolvedValue(summaryOk());
}

function refreshIdle() {
  return { state: "idle", job_id: null, started_at: null, finished_at: null, steps: { holdings: null, market: null } };
}

// POC3-02D-OPS-02 3-1 — OCI 한 줄이 쓰는 기동 시 상태(백엔드 캐시 응답 모양).
function ociOk() {
  return {
    checked_at: "2026-09-27T08:18:31+00:00",
    reachable: true,
    overall: "OPERATING",
    summary_line: "OCI 자동 운영 스케줄 활성 (필수 3종 등록 · 기동 시 확인)",
    crontab_active: true,
    jobs: [],
    note: "",
    schedule: [
      { kind: "market_briefing", label: "시장 브리핑", state: "registered" },
      { kind: "holdings_briefing", label: "보유 브리핑", state: "registered" },
      { kind: "holdings_risk_alert", label: "장중 급등락", state: "registered" },
    ],
  };
}

beforeEach(() => {
  __resetQueryCache();
  vi.clearAllMocks();
  primeAll();
});

// POC5-UI-03 — 접기(시장 수치와 거래량 · 수치 더보기 · 현재 제공 범위와 남은 기능 · 모두 보기)를
// 모두 편다. 이 파일의 시험은 펼친 상태(예전처럼 모든 값이 그려진 상태)에서 확인한다. 값이 '없다'를
// 보는 시험(AC-7 · §3.1 등)이 접힌 칸 때문에 아무것도 보지 않고 통과하지 않게 한다(판정 §3).
// 접힌 기본 상태는 `today/TodayFolds.test.tsx` 가 따로 본다.
// 하나씩 누르고 다시 찾는다 — 맨 위 두 카드는 함께 펼쳐지므로(사용자 결정 ⑤) 한꺼번에 모아 누르면 다시 접힌다.
function expandAll() {
  for (let i = 0; i < 30; i++) {
    const closed = document.querySelector<HTMLButtonElement>('button.tc-fold-btn[aria-expanded="false"]');
    if (!closed) return;
    fireEvent.click(closed);
  }
}

async function renderView() {
  const onNavigate = vi.fn();
  render(<TodayInvestmentCheckView onNavigate={onNavigate} />);
  // `useSharedQuery` 는 effect 로 조회한다. **로딩 표시가 모두 사라질 때까지**
  // 기다린다.
  //
  // 예전에는 「코스피 가격 흐름」을 기다렸는데 그건 KospiHeadline 의 **정적
  // 라벨**이라 마운트 즉시 잡힌다 — 데이터 로드를 전혀 보장하지 않았다.
  // 그래서 뒤따르는 동기 `getByText` 가 조회 resolve 와 경쟁해 전체 회귀를
  // 연속 실행하면 간헐적으로 깨졌다(검증자 관측, 206/207).
  await waitFor(() => {
    expect(screen.queryByText(/불러오는 중/)).toBeNull();
  });
  // 시장 조회가 실제로 **반영**됐는지 확인한다. 예전 앵커(펼친 '기존 시장 판정 참고'의 'KODEX200 기준일')는 설계자
  // RESULT 재판정 V3 D4(2026-11-13)로 빠졌다 — 판정 표 '당일' 줄이 시장 판정 응답(아침 기준 응답에 당일 판정이 없는
  // 이 fixture 의 대체 출처)을 반영해 '불러오는 중'을 벗어날 때를 기다린다(성공 · 실패 · 판정 칸 없음 모두 벗어남).
  expandAll();
  await waitFor(() => expect(screen.getByTestId("tc-regime-today").textContent).not.toContain("불러오는 중"));
  expandAll(); // 앵커 뒤에 그려진 최대 3개 행의 '수치 더보기'까지.
  return { onNavigate };
}

describe("TodayInvestmentCheckView", () => {
  it("세 영역이 모두 보인다 (10초 과업 구조) — POC6-27 개편 배치", async () => {
    await renderView();
    // 시장 흐름 · 보유 · 잘 오르는 ETF(판단) · 자료 최신화 · OCI(정비 · 운영) 영역이 각각 존재.
    expect(screen.getByLabelText("시장 흐름")).toBeInTheDocument();
    // POC6-29 — 보유 점검 · 잘 오르는 ETF 각 한 카드 · 시장 근거 접힘 구역(자세히 구역 없음).
    expect(screen.getByLabelText("보유 점검")).toBeInTheDocument();
    expect(screen.getByLabelText("잘 오르는 ETF")).toBeInTheDocument();
    expect(screen.getByTestId("tc-evidence-fold")).toBeInTheDocument();
    expect(screen.queryByLabelText("보유 자세히")).toBeNull();
    expect(screen.queryByLabelText("잘 오르는 ETF 자세히")).toBeNull();
    expect(screen.getByLabelText("자료 최신화 필요")).toBeInTheDocument();
    expect(screen.getByLabelText("OCI 운영 스케줄 확인")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "시장 흐름" })).toBeInTheDocument();
  });

  it("형수님 결정(2026-11-13) — 아침 요약 → 오늘 시장 변화(당일 판정 → 판정 표 → 코스피 공식 종가 · 칸 · 차트(숫자 바로 아래) · 코스피 지표) · 근거 표는 접기 안 · 시장 흐름은 전체 폭", async () => {
    await renderView();
    const flow = screen.getByLabelText("시장 흐름");
    const now = within(flow).getByTestId("tc-market-now");
    const order = [
      within(flow).getByTestId("tc-morning"),
      ...["tc-now-regime", "tc-kodex-basis", "tc-kospi-close", "tc-tile-1m", "tc-tile-3m", "tc-tile-6m", "tc-flow-chart"].map((id) =>
        within(now).getByTestId(id),
      ),
      within(now).getByLabelText("KOSPI 현재 위치"),
    ];
    for (let i = 1; i < order.length; i++) {
      expect(order[i - 1].compareDocumentPosition(order[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
    // 판정 표 바로 다음이 코스피 공식 종가 덩어리(한 덩어리 · 칸 · 차트 · 지표가 그 안)
    const close = within(now).getByTestId("tc-kospi-close");
    expect(within(now).getByTestId("tc-kodex-basis").nextElementSibling).toBe(close);
    for (const id of ["tc-tile-1m", "tc-tile-3m", "tc-tile-6m", "tc-flow-chart"]) expect(close.contains(within(now).getByTestId(id))).toBe(true);
    expect(close.contains(within(now).getByLabelText("KOSPI 현재 위치"))).toBe(true);
    // 접기 안에는 코스피 덩어리가 없고 근거 표가 있다
    const fold = screen.getByTestId("tc-evidence-fold");
    expect(within(fold).queryByTestId("tc-kospi-close")).toBeNull();
    expect(within(fold).queryByTestId("tc-flow-chart")).toBeNull();
    expect(within(fold).getByTestId("tc-ev-table")).toBeInTheDocument();
    // 차트는 기존 KospiChart(최근 최대 120개 저장일 · 이 fixture 는 2개 · 그래프 아래 줄은 2026-11-14 형수님 결정으로 뺌).
    expect(await within(within(now).getByTestId("tc-flow-chart")).findByTestId("kospi-chart-readout")).toBeInTheDocument();
    expect(within(now).getByTestId("tc-flow-chart").textContent).not.toMatch(/개 저장일/);
    // 시장 흐름은 좌우 두 칸 격자 안에 있지 않다(전체 폭).
    expect(flow.closest(".tc-check-grid")).toBeNull();
    expect(flow.closest(".tc-detail-grid")).toBeNull();
  });

  it("코스피 기간 수익률(20 · 60거래일 · 예전 이름 1M/3M)을 표시한다 (저장 KOSPI 시계열)", async () => {
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
            return_20d_pct: -25.08, // 서버는 1m = 20거래일 · 3m = 60거래일(같은 계산)
            return_60d_pct: 3.32,
          },
          primary_benchmark: "KODEX200",
          regime_reasons: [],
        },
      }),
    );
    // 2026-11-14(설계자 지시 · POC6-29-1 결과서 §5) — 상세 값은 아침 기준 응답의 저장값 상세(kospi_detail · 실제 시작일 · 위 시장 판정
    // 응답의 20 · 60거래일 칸은 이 칸에 쓰지 않음)
    fetchMorningBasis.mockResolvedValue(
      morningOk({
        kospi_detail: {
          status: "ok",
          as_of_date: "2026-07-24",
          r20: { start_date: "2026-06-25", end_date: "2026-07-24", pct: -25.08 },
          r60: { start_date: "2026-04-28", end_date: "2026-07-24", pct: 3.32 },
          return_1y_pct: null,
          high_52w_gap_pct: null,
          reason: null,
        },
      }),
    );
    await renderView();
    const headline = screen.getByLabelText("KOSPI 현재 위치");
    // 형수님 결정(2026-11-14) — 이름을 실제 계산대로(위 1 · 3개월 칸 = 달력 기간과 겹치지 않게)
    expect(within(headline).getByText("20거래일 -25.08% (6/25부터)")).toBeInTheDocument();
    expect(within(headline).getByText("60거래일 +3.32% (4/28부터)")).toBeInTheDocument();
    expect(within(headline).getByText(/코스피 수익률·위치/).textContent).toBe("코스피 수익률·위치 · 7/24 종가 기준");
    expect(within(headline).queryByText(/1개월|3개월/)).toBeNull();
  });

  it("§3.1 강제 분리: KODEX200 판정을 코스피와 별도 라벨로 표기한다", async () => {
    await renderView();
    // 판정은 'KODEX 200' 이름을 단 판정 표에서만(설계자 V3 D4 — 코스피 구역의 '기존 시장 판정 참고'는 뺐다).
    const basis = screen.getByLabelText("시장 판정 근거");
    expect(within(basis).getByText(/시장 판정 근거 · KODEX 200/)).toBeInTheDocument();
    expect(within(screen.getByTestId("tc-regime-today")).getByText(/하락장/)).toBeInTheDocument();
    expect(within(screen.getByLabelText("KOSPI 현재 위치")).queryByText(/하락장|기존 시장 판정 참고/)).toBeNull();
    // "코스피 상승장/코스피 시장 상태" 처럼 두 기준을 합친 표현이 없어야 (FAIL 조건).
    expect(screen.queryByText(/코스피 시장 상태/)).toBeNull();
    expect(screen.queryByText(/코스피 하락장/)).toBeNull();
  });

  it("KODEX200 MA20·MA60 대비 거리를 각각 명시한다 (단일 '전환까지 거리' 아님) — 설계자 V3 D3 판정 표에 가격 + 거리", async () => {
    await renderView();
    const today = screen.getByTestId("tc-regime-today").textContent ?? "";
    expect(today).toMatch(/20일선 [\d,]+원 · \d+\.\d{2}% (위|아래)/);
    expect(today).toMatch(/60일선 [\d,]+원 · \d+\.\d{2}% (위|아래)/);
    // 코스피 구역의 중복 'KODEX200 기준선 대비 위치'는 뺐다(D3 · 화면 맨 아래 「현재 제공 범위」 설명 글은 별개).
    expect(within(screen.getByLabelText("KOSPI 현재 위치")).queryByText(/KODEX200 기준선 대비 위치|KODEX200 MA20 대비/)).toBeNull();
  });

  it("POC3-06 §3.2: KOSPI 일간·1년·고점 대비·지속일이 실제값으로 표시된다", async () => {
    await renderView();
    const headline = screen.getByLabelText("KOSPI 현재 위치");
    const text = headline.textContent ?? "";
    // 일간·1년·최근 1년 고점 대비 실제값 (개발 중 자리표시자 아님).
    // 일간 변화 칸은 2026-11-14 뺐다(형수님 결정 · 코스피 공식 종가 머리 줄이 같은 일간 변화 · 비교 날짜를 보임).
    expect(screen.queryByTestId("tc-kospi-daily")).toBeNull();
    expect(text).toContain("최근 1년 고점 대비");
    // 흐름 지속 거래일 수 실제값 — 설계자 V3 D4(2026-11-13)로 코스피 구역의 '기존 시장 판정 참고'를 빼서 판정 표에서 읽는다.
    expect(screen.getByTestId("tc-regime-today").textContent).toContain("12거래일째");
    expect(text).not.toContain("거래일째");
    // 개발 중 자리표시자는 headline 에 없다.
    expect(text).not.toContain("개발 중");
  });

  it("AC-13: KOSPI 지수 거래량은 미제공 · 공격방어 · SuperTrend 는 이번 단계 미도입으로 남는다", async () => {
    await renderView();
    const detail = screen.getByLabelText("코스피 상세 (개발 중)");
    // POC5-09 판정 §9-3 — 거래량 항목 = 'KOSPI 지수 거래량' · '미제공'.
    expect(within(detail).getByText("KOSPI 지수 거래량")).toBeInTheDocument();
    expect(within(detail).getByText("미제공")).toBeInTheDocument();
    expect(within(detail).queryByText("거래량 흐름")).toBeNull();
    expect(within(detail).getByText("공격·방어 비중")).toBeInTheDocument();
    expect(within(detail).getByText(/SuperTrend/)).toBeInTheDocument();
    expect(within(detail).queryByText("일간 등락률")).toBeNull();
    expect(within(detail).queryByText("1년 수익률")).toBeNull();
    // 사유는 hover 툴팁(title) — KOSPI 지수 거래량 미저장 · KODEX200 거래량은 ETF 한 종목 값.
    const volInfo = within(detail).getByRole("note", {
      name: /KOSPI 지수 거래량은 미저장입니다/,
    });
    expect(volInfo).toHaveAttribute(
      "title",
      "KOSPI 지수 거래량은 미저장입니다. 표시되는 KODEX200 거래량은 ETF 한 종목의 값입니다.",
    );
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
    for (const label of ["보유 점검", "잘 오르는 ETF"]) {
      const judgment = screen.getByLabelText(label);
      // 판단 영역 안에는 자료 상태 문구가 없어야 한다.
      expect(within(judgment).queryByText(/자료가 없습니다/)).toBeNull();
      expect(within(judgment).queryByText(/오래되었습니다/)).toBeNull();
      expect(within(judgment).queryByText(/지금 다시 불러오기/)).toBeNull();
    }
    // POC6-27 판정 Q2 — 구성종목 등 정비 항목은 「자료 확인」 펼침의 정비 목록에 있다(구성종목 미수집 2건 fixture).
    const maint = screen.getByLabelText("자료 업데이트 목록");
    expect(
      within(maint).getByText(/ETF가 담고 있는 종목 자료가 없습니다/),
    ).toBeInTheDocument();
  });

  it("판정 Q2: 바로 조치할 일(보유 현재가)은 맨 위 카드 · 버튼, 기존 정비 항목은 「자료 확인」 목록의 이동 버튼", async () => {
    // fixture: constituents_unavailable(heavy) + 기본 holdings price_missing(light).
    fetchHoldingsMarketEvidence.mockResolvedValue(
      evidenceOk({ evidence_unavailable_count: 2, constituents_unavailable_count: 1 }),
    );
    await renderView();
    const top = screen.getByLabelText("자료 최신화 필요");
    expect(within(top).getByText(/보유 종목 현재가를 불러오지 못했습니다/)).toBeInTheDocument();
    expect(within(top).getByRole("button", { name: "최신 자료 갱신" })).toBeInTheDocument();
    const list = screen.getByLabelText("자료 업데이트 목록");
    expect(within(list).getByRole("button", { name: "구성종목 업데이트로" })).toBeInTheDocument();
    // 경량(현재가) 항목은 목록에 다시 나오지 않는다(같은 항목 두 곳 없음).
    expect(within(list).queryByText(/보유 종목 현재가를 불러오지 못했습니다/)).toBeNull();
  });

  it("ⓘ 근거: 각 정비 항목에 최신이 아닌 근거(비교 대상)가 툴팁으로 붙는다", async () => {
    await renderView();
    const maint = screen.getByLabelText("자료 업데이트 목록");
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

  it("POC3-02D-OPS-03 RESULT STEP 4: KOSPI 지연은 맨 위 「자료 최신화 필요」(코스피 줄 · 갱신 할 일) · 카드 기준일은 KOSPI 기준일", async () => {
    const base = marketOk();
    fetchMarketTopnLatest.mockResolvedValue({
      ...base,
      market_context: {
        ...base.market_context,
        kospi: {
          status: "stale",
          as_of_date: "2026-07-23",
          display_state: "stale",
          trading_day_lag: 1,
          today_is_trading_day: true,
        },
      },
    });
    await renderView();
    const top = screen.getByLabelText("자료 최신화 필요");
    expect(top.querySelector('[data-fresh="kospi"]')?.textContent).toContain("마지막 2026-07-23");
    const reason = within(top).getByText(/KOSPI 원자료가 최근 거래일까지 갱신되지 않았습니다/);
    expect(reason.textContent).toContain("(KOSPI 기준일 2026-07-23 · 1거래일 지연)");
    expect(within(top).getByRole("button", { name: "최신 자료 갱신" })).toBeInTheDocument();
    // 「자료 확인」 목록에는 같은 코스피 항목을 다시 두지 않는다 · 판단 영역에는 들어가지 않는다(AC-4/AC-5).
    expect(within(screen.getByLabelText("자료 업데이트 목록")).queryByText(/KOSPI 원자료/)).toBeNull();
    expect(within(screen.getByLabelText("보유 점검")).queryByText(/KOSPI 원자료/)).toBeNull();
    // 2026-11-14(설계자 지시 · POC6-29-1 결과서 §5) — 수집 · 지연 사유는 위 「자료 최신화 필요」(자료 상태) 한 곳 · KOSPI 지표 칸에는
    // '마지막 자료 기준일' · 사유 줄 없이 출처 한 줄(기준일은 코스피 공식 종가 머리 줄).
    const headline = screen.getByLabelText("KOSPI 현재 위치");
    expect(within(headline).getByTestId("tc-kospi-source").textContent).toBe("출처: 한국거래소(KRX)");
    expect(headline.textContent).not.toMatch(/마지막 자료 기준일|원자료가 최근 거래일까지|거래일 지연/);
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
    // POC6-29 판정 Q17 — 사용자가 정한 메뉴 이름(「후보리스트」 · 「보유와 후보 비교」 · 「ETF보유 및 후보 선정」)을 가리키는
    // 곳만 '후보'를 허용한다. 그 이름을 지운 뒤에는 '후보'가 남지 않아야 한다.
    const all = parts
      .join(" ")
      .replaceAll("ETF보유 및 후보 선정", "")
      .replaceAll("보유와 후보 비교", "")
      .replaceAll("후보리스트", "");
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

  it("POC6-29 잘 오르는 ETF: 이 화면 조건(1개월 · 4종 제외 고정)의 공통 기간 목록 선정 1 ~ 3위 · [후보리스트 보기 →]", async () => {
    const { onNavigate } = await renderView();
    const card = screen.getByLabelText("잘 오르는 ETF");
    const s = summaryOk();
    expect(fetchEtfCompareSummary.mock.calls[0][0]).toEqual({
      basis: "one_month",
      filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
    });
    const top = within(card).getByTestId("tc-cand-top");
    for (const r of s.top.slice(0, 3)) expect(top).toHaveTextContent(`${r.rank}위${r.name}`);
    expect(within(card).getByTestId("tc-cand-line")).toHaveTextContent("1개월 수익률 상위 · 10/12 → 11/9");
    fireEvent.click(within(card).getByRole("button", { name: "3개월" }));
    await waitFor(() => expect(fetchEtfCompareSummary.mock.calls.some((c) => c[0].basis === "three_month")).toBe(true));
    fireEvent.click(within(card).getByRole("button", { name: "후보리스트 보기 →" }));
    expect(onNavigate).toHaveBeenCalledWith("workbench");
    expect(within(card).queryByRole("button", { name: /요즘 잘 오르는 ETF/ })).toBeNull();
  });

  // 2026-09-27 사용자 직접 지시: 「OCI 운영 상태」(oci_status)가 「승인·적용」과 합쳐져
  // 「OCI 운영·적용」(approval)이 됐다. 도착 key · 문구가 함께 바뀐다.
  it("POC3-02D-OPS-02 3-1 · POC6-27: OCI 카드(기본 접힘) 링크 → 「OCI 운영·적용」(approval)", async () => {
    const { onNavigate } = await renderView();
    const ociLabel = MENU_ITEMS.find((m) => m.key === "approval")?.label;
    expect(ociLabel).toBe("OCI 운영·적용");
    const card = screen.getByLabelText("OCI 운영 스케줄 확인");
    expect(within(card).getByTestId("tc-oci-summary").textContent).toBe("예약 3/3 확인");
    // 문구가 도착 화면 이름을 그대로 쓴다 — '진단·상태'(그룹명) · 「개발·실험용」 아님.
    const link = within(card).getByRole("button", { name: `${ociLabel} →` });
    expect(link.textContent).not.toMatch(/진단·상태|개발·실험용/);
    fireEvent.click(link);
    expect(onNavigate).toHaveBeenCalledWith("approval");
    expect(onNavigate).not.toHaveBeenCalledWith("diagnostics");
    expect(onNavigate).not.toHaveBeenCalledWith("oci_status");
  });

  it("POC3-02D-OPS-02 3-1: OCI 조회가 실패해도 링크는 approval 로 간다(예약 '확인 불가'는 누락이 아님)", async () => {
    fetchOciStartupStatus.mockRejectedValue(new Error("down"));
    const { onNavigate } = await renderView();
    const card = screen.getByLabelText("OCI 운영 스케줄 확인");
    await waitFor(() => expect(within(card).getByTestId("tc-oci-summary").textContent).toBe("예약 상태 불러오지 못함"));
    expect(card.textContent).not.toContain("누락");
    const ociLabel = MENU_ITEMS.find((m) => m.key === "approval")?.label;
    fireEvent.click(within(card).getByRole("button", { name: `${ociLabel} →` }));
    expect(onNavigate).toHaveBeenCalledWith("approval");
    expect(onNavigate).not.toHaveBeenCalledWith("diagnostics");
    expect(onNavigate).not.toHaveBeenCalledWith("oci_status");
  });

  it("AC-14 정비 이동: 항목별 직접 라우팅 (구성종목 → etf_exposure)", async () => {
    const { onNavigate } = await renderView();
    fireEvent.click(within(screen.getByLabelText("자료 업데이트 목록")).getByRole("button", { name: "구성종목 업데이트로" }));
    expect(onNavigate).toHaveBeenCalledWith("etf_exposure");
  });

  // ── POC6-29 판정 Q7 — [최신 자료 갱신] 한 번(PC 서버 묶음 작업 · 보유 현재가 → 시장 자료) ──
  // 묶음 작업 응답(가짜) — 단계 결과를 바로 담은 '끝남' 응답(빠른 작업)으로 시험한다(진행 중 → 끝남은 아래 따로).
  const holdDone = (p: Record<string, unknown> = {}) => ({ status: "done", ok_count: 2, fail_count: 0, ...p });
  const allDone = (holdings: Record<string, unknown>, market: Record<string, unknown> = { status: "skipped_cooldown", cooldown_remaining_seconds: 1800, message: "" }) => ({
    state: "done",
    job_id: "j1",
    started_at: "2026-07-25T00:00:00Z",
    finished_at: "2026-07-25T00:00:05Z",
    steps: { holdings, market },
  });
  const clickRefresh = () => fireEvent.click(screen.getAllByRole("button", { name: "최신 자료 갱신" })[0]);

  it("[최신 자료 갱신] = 묶음 작업 한 번(POST /refresh/all) · 옛 두 버튼은 없다 · 시장 대기는 다음 가능 시각과 함께", async () => {
    postRefreshAll.mockResolvedValue(allDone(holdDone()));
    await renderView();
    expect(screen.queryByRole("button", { name: "보유 현재가 업데이트" })).toBeNull();
    expect(screen.queryByRole("button", { name: "최신 시장 데이터 갱신" })).toBeNull();
    clickRefresh();
    expect(postRefreshAll).toHaveBeenCalledTimes(1);
    expect(refreshMarket).not.toHaveBeenCalled(); // 화면이 보유 갱신을 따로 부르지 않는다(서버 묶음 작업)
    expect((await screen.findByTestId("tc-hold-result")).textContent).toContain("보유 현재가 업데이트 완료 2건");
    // 판정 Q7 · 보완 PLAN 판정 Q-R2 — 시장이 대기 중이면 다음 가능 시각(서버 값이 없으면 남은 초로 계산)과 지금 표시 중인
    // 값의 기준(ETF 가격은 저장 시각 · 가격 시점까지).
    expect(screen.getByTestId("tc-market-result").textContent).toMatch(
      /^② 시장 자료는 대기 중입니다\(6시간 간격\) — 다음 갱신 가능 \d{1,2}\/\d{1,2} \d{2}:\d{2}\(약 30분 뒤\) · 지금 표시 = ETF 가격 /,
    );
  });

  it("시장 대기 — 서버가 준 다음 가능 시각을 그대로(KST) · 자료별 지금 기준일", async () => {
    postRefreshAll.mockResolvedValue(
      allDone(holdDone(), { status: "skipped_cooldown", cooldown_remaining_seconds: 1800, message: "", next_available_at: "2026-07-25T06:30:00+00:00" }),
    );
    await renderView();
    clickRefresh();
    const line = (await screen.findByTestId("tc-market-result")).textContent ?? "";
    expect(line).toContain("다음 갱신 가능 7/25 15:30(약 30분 뒤)");
    // ETF 가격 = KODEX 200 상세의 끝일 · 저장 시각 · 가격 시점(시험 자료 = 11/9 가격을 11/10 13:18 마감 뒤 저장 → 저장 날짜까지)
    expect(line).toContain("지금 표시 = ETF 가격 11/9(11/10 13:18 마감 뒤 저장) · 코스피 공식 종가 ");
    expect(line).toMatch(/· 외국인 수급 .+ · 원\/달러 .+ · WTI .+ · VIX .+\(빠른 시세 · 보유 현재가는 이 대기와 별개로 받습니다\)$/);
  });

  it("연타해도 묶음 작업은 한 번만 시작한다(진행 중 · 버튼 막힘)", async () => {
    let resolve: (v: unknown) => void = () => {};
    postRefreshAll.mockReturnValue(new Promise((r) => (resolve = r)));
    await renderView();
    clickRefresh();
    clickRefresh();
    expect(postRefreshAll).toHaveBeenCalledTimes(1);
    expect(screen.getAllByRole("button", { name: "자료 갱신 중..." })[0]).toBeDisabled();
    await act(async () => resolve(allDone(holdDone())));
    expect((await screen.findByTestId("tc-hold-result")).textContent).toContain("완료");
  });

  it("다른 탭에서 시작한 묶음 작업이 돌고 있으면 열 때 이어서 따라간다", async () => {
    fetchRefreshAllStatus
      .mockResolvedValueOnce({ ...allDone({ status: "running" }, { status: "pending" }), state: "running", finished_at: null })
      .mockResolvedValue(allDone(holdDone()));
    await renderView();
    expect(screen.getByTestId("tc-all-result").textContent).toContain("① 보유 현재가 받는 중");
    expect(await screen.findByTestId("tc-hold-result", {}, { timeout: 4000 })).toHaveTextContent("보유 현재가 업데이트 완료");
    expect(postRefreshAll).not.toHaveBeenCalled();
  });

  it("핵심 정정: 갱신으로 현재가 결측이 해소되면 보유 현재가 할 일이 사라진다", async () => {
    postRefreshAll.mockResolvedValue(allDone(holdDone()));
    await renderView();
    expect(
      within(screen.getByLabelText("자료 최신화 필요")).getByText(/보유 종목 현재가를 불러오지 못했습니다/),
    ).toBeInTheDocument();
    fetchEnrichedHoldings.mockResolvedValue({
      items: [{ ticker: "069500", name: "KODEX200", price_missing: false }],
    });
    clickRefresh();
    await screen.findByTestId("tc-hold-result");
    await waitFor(() => {
      expect(screen.queryByText(/보유 종목 현재가를 불러오지 못했습니다/)).toBeNull();
    });
  });

  it("재분류: evidence stale·NAV 는 「자료 확인」 목록 항목 · 그 버튼은 같은 화면 [최신 자료 갱신]", async () => {
    fetchEnrichedHoldings.mockResolvedValue({
      items: [{ ticker: "069500", name: "KODEX200", price_missing: false }],
    });
    fetchHoldingsMarketEvidence.mockResolvedValue(
      evidenceOk({ evidence_unavailable_count: 2, constituents_unavailable_count: 0 }),
    );
    postRefreshAll.mockResolvedValue(allDone(holdDone()));
    const { onNavigate } = await renderView();
    const list = screen.getByLabelText("자료 업데이트 목록");
    const btn = within(list).getAllByRole("button", { name: "최신 자료 갱신" })[0];
    expect(within(list).queryByRole("button", { name: "시장 자료 업데이트로" })).toBeNull();
    fireEvent.click(btn);
    expect(postRefreshAll).toHaveBeenCalledTimes(1);
    expect(onNavigate).not.toHaveBeenCalled(); // 다른 화면으로 가지 않는다(옛 시장 화면 없음)
    expect(screen.queryByText(/보유 종목 현재가를 불러오지 못했습니다/)).toBeNull();
  });

  it("UI 정정: [최신 자료 갱신]은 맨 위 1개 + 할 일이 있을 때 카드 안 할 일마다(같은 작업)", async () => {
    await renderView();
    const top = screen.getByLabelText("자료 최신화 필요");
    expect(within(top).getAllByRole("button", { name: "최신 자료 갱신" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("banner").querySelectorAll("button").length).toBeGreaterThan(0);
  });

  it("Q7 정정: 보유 현재가 단계가 끝나면 Holdings · Evidence · NAV · 요약을 모두 다시 읽는다", async () => {
    postRefreshAll.mockResolvedValue(allDone(holdDone()));
    await renderView();
    const h0 = fetchEnrichedHoldings.mock.calls.length;
    const e0 = fetchHoldingsMarketEvidence.mock.calls.length;
    const n0 = fetchNavDiscountLatest.mock.calls.length;
    const s0 = fetchEtfCompareSummary.mock.calls.length;
    clickRefresh();
    await screen.findByTestId("tc-hold-result");
    await waitFor(() => {
      expect(fetchEnrichedHoldings.mock.calls.length).toBeGreaterThan(h0);
      expect(fetchHoldingsMarketEvidence.mock.calls.length).toBeGreaterThan(e0);
      expect(fetchNavDiscountLatest.mock.calls.length).toBeGreaterThan(n0);
      expect(fetchEtfCompareSummary.mock.calls.length).toBeGreaterThan(s0);
    });
  });

  it("r5 A-1: NAV 재조회 실패 시 '완료' 로 위장하지 않는다 (거짓 완료 금지)", async () => {
    postRefreshAll.mockResolvedValue(allDone(holdDone()));
    await renderView();
    fetchNavDiscountLatest.mockRejectedValueOnce(new Error("nav-network"));
    clickRefresh();
    const r = await screen.findByTestId("tc-hold-result");
    expect(r.textContent).toContain("실패");
    expect(r.textContent).toContain("ETF 기준가");
    expect(r.textContent).not.toContain("완료");
  });

  it("A-1(4): 보유 재조회 실패 시 '완료' 를 표시하지 않는다 (거짓 완료 금지)", async () => {
    postRefreshAll.mockResolvedValue(allDone(holdDone()));
    await renderView();
    fetchEnrichedHoldings.mockRejectedValueOnce(new Error("network"));
    clickRefresh();
    const r = await screen.findByTestId("tc-hold-result");
    expect(r.textContent).toContain("실패");
    expect(r.textContent).not.toContain("완료");
  });

  it("POC6-27 판정 §4: 보유 갱신은 전건 실패 · 일부 실패를 나눠 표시한다(전건 = 경고색)", async () => {
    postRefreshAll.mockResolvedValue(allDone({ status: "failed", reason: "all_failed", ok_count: 0, fail_count: 2 }));
    await renderView();
    clickRefresh();
    const r = await screen.findByTestId("tc-hold-result");
    expect(r.textContent).toBe("① 보유 현재가를 받지 못했습니다(실패 2건)");
    expect(r.className).toContain("tc-warn");
  });

  it("POC6-27 판정 §4: 일부 실패는 받은 건수와 함께", async () => {
    postRefreshAll.mockResolvedValue(allDone(holdDone({ ok_count: 1, fail_count: 1 })));
    await renderView();
    clickRefresh();
    const r = await screen.findByTestId("tc-hold-result");
    expect(r.textContent).toContain("보유 현재가 일부 실패 1건 · 받은 1건");
    expect(r.className).toContain("tc-warn");
  });

  it("보유가 없으면(서버가 건너뜀) 그 사유 · 시장 자료 단계는 그대로 진행", async () => {
    postRefreshAll.mockResolvedValue(
      allDone({ status: "skipped", reason: "holdings_empty", message: "holdings 가 비어 있습니다" }, { status: "accepted", refresh_id: "r1", message: "", cooldown_remaining_seconds: 0 }),
    );
    await renderView();
    // 화면을 연 뒤에 시작된 시장 갱신(묶음 작업이 시작) — 그 진행을 이어서 따라간다.
    fetchMarketRefreshStatus.mockResolvedValue({ status: "running", refresh_id: "r1", cooldown_remaining_seconds: 0 });
    clickRefresh();
    expect((await screen.findByTestId("tc-hold-result")).textContent).toContain("보유 현재가: 저장된 보유 종목이 없어 받지 않았습니다(「종목 관리」에서 입력 · 저장)");
    expect(screen.getByTestId("tc-hold-result").textContent).not.toContain("holdings"); // 서버 원문(영어 낱말)을 쓰지 않음
    expect(screen.getByTestId("tc-market-result").textContent).toContain("② 시장 자료 갱신 중입니다");
  });

  it("POC6-27: 정비 목록의 모든 행에 ⓘ 근거가 붙는다(다른 항목과 통일)", async () => {
    await renderView();
    const rows = within(screen.getByLabelText("자료 업데이트 목록")).getAllByRole("listitem");
    expect(rows.length).toBeGreaterThan(0);
    for (const row of rows) expect(within(row).getByRole("note")).toHaveAttribute("title");
  });

  it("정정: 보유 갱신 결과 줄은 3초 뒤 자동으로 사라진다", async () => {
    postRefreshAll.mockResolvedValue(allDone(holdDone()));
    vi.useFakeTimers();
    try {
      const onNavigate = vi.fn();
      render(<TodayInvestmentCheckView onNavigate={onNavigate} />);
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
      });
      fireEvent.click(screen.getAllByRole("button", { name: "최신 자료 갱신" })[0]);
      await act(async () => {
        for (let i = 0; i < 10; i++) await Promise.resolve();
      });
      expect(screen.getByTestId("tc-hold-result").textContent).toContain("완료");
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3100);
      });
      expect(screen.queryByTestId("tc-hold-result")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("AC-11: MA 한계 설명은 항상 노출 문단이 아니다 — 설계자 V3 D1 · D3 로 판정 표 제목 옆 [?](점수 산식과 함께 · 처음엔 닫힘)", async () => {
    await renderView();
    const hint = screen.getByTestId("tc-score-rule") as HTMLDetailsElement;
    expect(hint.open).toBe(false);
    expect(within(hint).getByLabelText("점수 산식 보기")).toBeInTheDocument();
    expect(hint.querySelector(".tc-src-pop")?.textContent).toContain(
      "이동평균 거리는 급격한 하락이나 반등에 늦게 반응할 수 있으며, 미래의 추세 전환을 예측하는 값은 아닙니다.",
    );
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
    // 설계자 V3 D3 — 판정 표의 이동평균 칸: 값이 없으면 '자료 없음'('-' 아님)
    const today = screen.getByTestId("tc-regime-today").textContent ?? "";
    expect(today).toContain("20일선 자료 없음");
    expect(today).toContain("60일선 자료 없음");
  });

  // 금지 용어: 라틴 내부 용어 + 한국어 금지 용어. label·hint 모두 적용.
  // 2026-08-02 POC3-05 DESIGN_V2: "확인 근거" 가 설계서 §4.1·§4.4 가 명시한 사용자 화면
  //   메뉴 라벨이 되어 "근거" 는 금지어에서 제외한다(V2 AC-2·AC-7). V2 AC-19 사용자 금지어
  //   (저위험/고위험/안전/매도/손절/BUY/SELL)에는 "근거" 가 없다. "후보" 는 계속 금지.
  // 2026-11-11 POC6-28(설계자 PLAN 판정 Q1 · 사용자 결정): 「ETF 비교하기」 폴더 아래 하위 메뉴 이름 「후보」(workbench)
  //   한 곳만 허용한다. 다른 메뉴 이름 · 모든 설명(hint)에는 여전히 "후보" 를 쓰지 않는다.
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

  // 2026-11-12 POC6-29(설계자 PLAN 판정 Q17): '후보' 예외를 사용자가 정한 세 이름 — 그룹 「ETF보유 및 후보 선정」 ·
  //   「후보리스트」 · 「보유와 후보 비교」 — 에 정확히 한정한다(설명 hint 에는 쓰지 않음). 「요즘 잘 오르는 ETF」 메뉴는 없앴다.
  const CANDIDATE_NAMES = ["ETF보유 및 후보 선정", "후보리스트", "보유와 후보 비교"];

  it("AC-7: 좌측 메뉴 전체 텍스트(라벨+힌트)에 금지 용어가 없다 (Sidebar 실제 렌더)", () => {
    render(<LeftSidebar active="today_check" onSelect={() => {}} />);
    const text = document.body.textContent ?? "";
    for (const term of FORBIDDEN_TERMS) {
      if (term === "후보") continue;
      expect(text).not.toContain(term);
    }
    expect(text.split("후보").length - 1).toBe(3); // 세 이름에 한 번씩
    let rest = text;
    for (const n of CANDIDATE_NAMES) {
      expect(rest).toContain(n);
      rest = rest.replace(n, "");
    }
    expect(rest).not.toContain("후보");
    // 사용자 언어 라벨이 실제로 있는지도 확인.
    expect(text).not.toContain("요즘 잘 오르는 ETF");
    expect(text).toContain("보유 현황");
    expect(text).toContain("섹터요약");
  });

  it("AC-7 보강: MENU_ITEMS 의 label·hint 모두 금지 용어가 없다", () => {
    for (const item of MENU_ITEMS) {
      for (const term of FORBIDDEN_TERMS) {
        if (!(term === "후보" && CANDIDATE_NAMES.includes(item.label))) {
          expect(item.label).not.toContain(term);
        }
        expect(item.hint ?? "").not.toContain(term);
      }
    }
  });

  it("AC-1: 접힌 「자료 최신화 필요」 줄 · 「자료 확인」 배지에 건수를 표시한다 (몇 건인지 한눈에)", async () => {
    await renderView();
    expect(screen.getByTestId("tc-fresh-summary").textContent).toMatch(/\d+건/);
    const data = document.querySelector('[data-row="data"]') as HTMLElement;
    expect(data.textContent).toMatch(/확인할 자료 \d+건/);
  });

  it("POC6-29 보유 점검: 한 카드 · 종목 단위 판정(「보유」와 같은 요약 응답) · [보유 보기 →] = 「보유」", async () => {
    fetchEnrichedHoldings.mockResolvedValue({
      items: [
        { ticker: "B00001", name: "하락 ETF", price_missing: false },
        { ticker: "B00001", name: "하락 ETF", price_missing: false },
        { ticker: "S00001", name: "다른 보유", price_missing: false },
      ],
    });
    const { onNavigate } = await renderView();
    const card = screen.getByLabelText("보유 점검");
    // 같은 종목 두 계좌 = 한 종목 · 요약에 없는 보유는 판정 못 함(하락 아님으로 세지 않음).
    expect(within(card).getByTestId("tc-hold-count").textContent).toMatch(/^보유 2종목 중 \d종목 하락 · 판정 1종목$/);
    expect(within(card).getByTestId("tc-hold-basis").textContent).toContain("판정 못 한 보유 1종목은 세지 않음");
    expect(within(card).queryByText("내가 가진 ETF")).toBeNull();
    fireEvent.click(within(card).getByRole("button", { name: "보유 보기 →" }));
    expect(onNavigate).toHaveBeenCalledWith("workbench_holdings");
  });

  // POC6-29 — 「보유 자세히」(내가 가진 ETF · 자료 확인 필요 건수 · 5일 하위 3개)는 카드 합침으로 없앴다(설계 §2 ·
  //   종목별 수치는 「보유」). 그 표시만 보던 POC3-06 §6.1 시험 2건은 함께 지웠다.
  it("POC6-29 보유 점검: 보유 근거 조회가 실패해도 요약 판정으로 셈 · 요약 조회 실패는 실패로(0종목 위장 없음)", async () => {
    fetchHoldingsMarketEvidence.mockRejectedValue(new Error("evidence down"));
    fetchEnrichedHoldings.mockResolvedValue({ items: [{ ticker: "B00001", name: "하락 ETF", price_missing: false }] });
    await renderView();
    const strip = screen.getByTestId("tc-risk-strip");
    expect(within(strip).getByTestId("tc-hold-count").textContent).toMatch(/^보유 1종목 중 \d종목 하락 · 판정 1종목$/);
  });

  it("POC6-29 보유 점검: 요약 조회 실패 = '불러오지 못했습니다' · 숫자를 만들지 않는다", async () => {
    fetchEtfCompareSummary.mockRejectedValue(new Error("summary down"));
    render(<TodayInvestmentCheckView onNavigate={vi.fn()} />);
    const strip = await screen.findByTestId("tc-risk-strip");
    expect(await within(strip).findByTestId("tc-risk-failed")).toHaveTextContent("보유 하락 판정 자료를 불러오지 못했습니다.");
    expect(within(strip).queryByTestId("tc-hold-count")).toBeNull();
  });
});

// POC6-27 — 모든 자료가 기대 기준일(2026-07-24) 이상인 시장 흐름 응답(필요한 칸만).
const FRESH_FLOW = {
  generated_at: "2026-07-25T09:00:00+09:00",
  D: "2026-07-24",
  has_flows: false,
  series: {},
  periods: {},
  windows: { lines: ["투자자별 수급 자료 없음"] },
  short_lines: [],
  events: [],
  event_check: { checked: [], unchecked: [], unchecked_text: null, empty_text: "최근 큰 변화 없음" },
  interpretation: {},
  limits: [],
  status: [],
  today_lines: [],
  ai_text: {},
  freshness: {
    today_kst: "2026-07-25",
    expected_kr: "2026-07-24",
    expected_kr_basis: "calendar",
    items: [
      { key: "flows", label: "외국인 수급", last_date: "2026-07-24", expected: "2026-07-24", basis: "kr_t1", state: "fresh", behind: 0, reason: null },
      { key: "usdkrw", label: "원/달러", last_date: "2026-07-24", expected: "2026-07-24", basis: "kr_t1", state: "fresh", behind: 0, reason: null },
      { key: "wti", label: "WTI", last_date: "2026-07-24", expected: null, basis: "observed_only", state: "observed", behind: null, reason: null },
    ],
  },
};

// ── POC5-UI-03 — 기본 접힘 화면(전체) ────────────────────────────────────────
describe("POC5-UI-03 「오늘의 투자 점검」 기본 화면 · 아래 묶음 · 0건 카드", () => {
  async function renderFolded() {
    render(<TodayInvestmentCheckView onNavigate={vi.fn()} />);
    await waitFor(() => {
      expect(screen.queryByText(/불러오는 중/)).toBeNull();
    });
    // 시장 응답 반영 앵커 = 펼친 '코스피 수익률·위치'의 1년 값(fixture 12.3% · 일간 변화 칸은 2026-11-14 뺌).
    await screen.findByText("1년 +12.30%");
  }

  it("배치(POC6-27 → POC6-29) — 머리 → 자료 최신화 · OCI(기본 접힘) → 지금 확인할 내용(보유 점검 · 잘 오르는 ETF) → 시장 근거(접힘) → 자료 · 연구 상태 → 맨 아래 「현재 제공 범위와 남은 기능」", async () => {
    await renderFolded();
    const seq = [
      screen.getByRole("heading", { level: 1, name: "오늘의 투자 점검" }),
      screen.getByLabelText("자료 최신화 필요"),
      screen.getByLabelText("OCI 운영 스케줄 확인"),
      screen.getByLabelText("지금 확인할 내용"),
      screen.getByLabelText("보유 점검"),
      screen.getByLabelText("잘 오르는 ETF"),
      screen.getByTestId("tc-evidence-fold"),
      screen.getAllByLabelText("자료 · 연구 상태")[0],
      screen.getByLabelText("현재 제공 범위와 남은 기능"),
    ];
    for (let i = 1; i < seq.length; i++) {
      expect(seq[i - 1].compareDocumentPosition(seq[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
    const scope = screen.getByLabelText("현재 제공 범위와 남은 기능");
    expect(scope.parentElement?.lastElementChild).toBe(scope);
    // 보완 2차 — '시장 수치와 거래량'은 처음부터 펼친다(판정서 V2 §2) · 형수님 결정(2026-11-13)으로 접기 밖 코스피 덩어리 안.
    expect(within(screen.getByTestId("tc-kospi-close")).getByRole("button", { name: "시장 수치와 거래량 접기" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    for (const name of [
      "자료 최신화 필요 펼치기",
      "OCI 운영 스케줄 확인 펼치기",
      "현재 제공 범위와 남은 기능 펼치기",
    ]) {
      const b = screen.getByRole("button", { name });
      expect(b).toHaveAttribute("aria-expanded", "false");
      expect(b).toHaveClass("btn-md");
    }
    // 시장 근거는 처음엔 접힘(설계 §2).
    expect(screen.getByTestId("tc-evidence-fold")).not.toHaveAttribute("open");
    // 접힌 칸은 그리지 않는다.
    expect(screen.queryByTestId("tc-fresh-body")).toBeNull();
    expect(screen.queryByTestId("tc-oci-body")).toBeNull();
    expect(screen.queryByLabelText("코스피 상세 (개발 중)")).toBeNull();
    expect(screen.queryByLabelText("개발 중인 판단 기능")).toBeNull();
    expect(screen.queryByText("KOSPI 지수 거래량")).toBeNull();
  });

  it("아래 묶음을 펼치면 두 안내 구역의 항목 · 배지 · 설명이 모두 그대로", async () => {
    await renderFolded();
    fireEvent.click(screen.getByRole("button", { name: "현재 제공 범위와 남은 기능 펼치기" }));
    const detail = screen.getByLabelText("코스피 상세 (개발 중)");
    expect(within(detail).getByRole("heading", { name: "코스피 상세 지표" })).toBeInTheDocument();
    for (const [name, badge] of [
      ["KOSPI 지수 거래량", "미제공"],
      ["공격·방어 비중", "이번 단계 미도입"],
      ["추세 전환선 (SuperTrend)", "이번 단계 미도입"],
    ]) {
      const row = within(detail).getByText(name).closest("span") as HTMLElement;
      expect(row.textContent).toContain(badge);
      expect(within(row).getByRole("note")).toHaveAttribute("title");
    }
    const board = screen.getByLabelText("개발 중인 판단 기능");
    expect(within(board).getByRole("heading", { name: "개발 중인 판단 기능" })).toBeInTheDocument();
    for (const [name, badge, desc] of [
      // POC5-13 RESULT 판정 §4 — 이미 제공하는 범위를 '부분 제공'으로 표시(종합 위험 구간 분류는 미제공).
      [
        "내가 가진 ETF의 위험 신호",
        "부분 제공",
        "시장 국면과 PC 하락 구간·평가 비중을 제공합니다. 종합 위험 구간 분류는 아직 제공하지 않습니다.",
      ],
      ["시장 흐름 전환까지의 거리", "개발 중", "현재는 KODEX200 기준선 대비 위치만 참고로 제공합니다."],
      ["저장 거래량 확인 근거", "일부 제공", "종합 위험 분류에는 아직 반영하지 않습니다."],
      ["공격·방어 비중", "이번 단계 미도입", "매매 비중 판단 표시는 이번 단계 범위 밖."],
      ["추세 전환선 (SuperTrend)", "이번 단계 미도입", "신규 추세 전환 지표 — 후속 위험 신호 단계에서 검토."],
    ]) {
      const li = within(board).getByText(name).closest("li") as HTMLElement;
      expect(li.textContent).toContain(badge);
      expect(li.textContent).toContain(desc);
    }
    const risk = within(board).getByText("내가 가진 ETF의 위험 신호").closest("li") as HTMLElement;
    expect(risk.textContent).not.toContain("개발 중");
    expect(risk.textContent).not.toContain("먼저 점검할 종목과 그 이유를 찾는 기능");
    fireEvent.click(screen.getByRole("button", { name: "현재 제공 범위와 남은 기능 접기" }));
    expect(screen.queryByLabelText("개발 중인 판단 기능")).toBeNull();
  });

  it("POC6-27 설계 §1-2 — 늦은 자료 · 할 일이 0건이면 「자료 최신화 필요」 카드는 없고 맨 위 [최신 자료 갱신]은 그대로", async () => {
    fetchEnrichedHoldings.mockResolvedValue({
      items: [
        { ticker: "069500", name: "KODEX200", price_missing: false, current_price: 1, price_source: "naver", price_asof: "2026-07-24T15:30:00+09:00" },
      ],
    });
    fetchHoldingsMarketEvidence.mockResolvedValue({
      ...evidenceOk({ evidence_unavailable_count: 0, constituents_unavailable_count: 0 }),
      price_basis: { reference_date: "2026-07-24", reference_ticker: "069500", kodex200_start_date_5d: null, kodex200_start_date_20d: null, date_mismatch: [] },
    });
    fetchForwardComparison.mockResolvedValue({ status: "NO_RECORDS", label: "연구용 · 운영 미채택" });
    fetchMarketFlowContext.mockResolvedValue(FRESH_FLOW);
    fetchMarketTopnLatest.mockResolvedValue(
      marketOk({
        market_risk_reference: {
          kodex200: { availability: "available", as_of_date: "2026-07-24", recent_20d_series: [] },
          vix: {
            availability: "available",
            as_of_date: "2026-07-24",
            recent_20d_series: [],
            freshness: { state: "fresh", compare_date: "2026-07-24", weekdays_behind: 0 },
          },
        },
      }),
    );
    await renderFolded();
    await waitFor(() => expect(screen.queryByLabelText("자료 최신화 필요")).toBeNull());
    expect(screen.getByRole("button", { name: "최신 자료 갱신" })).toBeInTheDocument();
  });
});
