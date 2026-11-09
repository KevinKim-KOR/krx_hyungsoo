// POC6-16 — 「오늘의 투자 점검」 「지금 확인할 내용」 관통 시험(실제 화면 · 가짜 응답 · PLAN 판정 V1.1 §2 · §3 · §3-1 · §4 · §6).
// POC6-27 — 개편 배치(설계 · PLAN 판정 PASS_WITH_REQUIRED_CORRECTIONS)에 맞춰 같은 계약을 새 자리에서 본다.
//
// - 첫 진입 = 기존 조회 8개 + PC 원장 사본 1개 · 명령 0 · 왕복 = 캐시 재사용.
// - [요약 다시 읽기] = 저장 자료 6개만(시장 판정 · 목록 · OCI · 명령 0) · 중복 클릭 막음 · 다 끝난 뒤 완료 / 일부 실패.
// - 판정 Q3 — 늦거나 확인이 필요한 자료가 있으면 고르기 전 반영하지 않음 · [취소] = 화면 · 공유 캐시 · 읽은 시각 그대로 ·
//   [이 자료로 계속] = 창에 보인 같은 결과 반영.
// - 판정 Q2 — 「지금 할 일」은 맨 위 「자료 최신화 필요」(같은 판정 · 버튼은 이 화면의 같은 작업) · 연구 대기는 할 일 아님.
// - 같은 화면 이동은 목적 카드로 스크롤 + 포커스.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within, act } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import { DATA as FWD } from "../ml_forward/testFixtures";

const fetchMarketTopnLatest = vi.fn();
const fetchEnrichedHoldings = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
const fetchNavDiscountLatest = vi.fn();
const fetchBenchmarkSeries = vi.fn();
const refreshMarket = vi.fn();
const fetchOciStartupStatus = vi.fn();
const postMarketRefresh = vi.fn();
const fetchMarketRefreshStatus = vi.fn();
const fetchMarketFlowContext = vi.fn();
const fetchForwardComparison = vi.fn();
const fetchLedgerLatestByKind = vi.fn();

vi.mock("@/lib/api", () => ({
  fetchMarketTopnLatest: (...a: unknown[]) => fetchMarketTopnLatest(...a),
  fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
  fetchHoldingsMarketEvidence: (...a: unknown[]) => fetchHoldingsMarketEvidence(...a),
  fetchNavDiscountLatest: (...a: unknown[]) => fetchNavDiscountLatest(...a),
  fetchBenchmarkSeries: (...a: unknown[]) => fetchBenchmarkSeries(...a),
  refreshMarket: (...a: unknown[]) => refreshMarket(...a),
  fetchOciStartupStatus: (...a: unknown[]) => fetchOciStartupStatus(...a),
  postMarketRefresh: (...a: unknown[]) => postMarketRefresh(...a),
  fetchMarketRefreshStatus: (...a: unknown[]) => fetchMarketRefreshStatus(...a),
}));
vi.mock("@/lib/api/marketFlow", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return { ...actual, fetchMarketFlowContext: (...a: unknown[]) => fetchMarketFlowContext(...a) };
});
vi.mock("@/lib/api/mlForwardComparison", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return { ...actual, fetchForwardComparison: (...a: unknown[]) => fetchForwardComparison(...a) };
});
vi.mock("@/lib/api/decisionLedger", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return { ...actual, fetchLedgerLatestByKind: (...a: unknown[]) => fetchLedgerLatestByKind(...a) };
});

import TodayInvestmentCheckView from "../TodayInvestmentCheckView";

function marketOk(kospiState: "ok" | "stale" = "stale") {
  return {
    status: "ok",
    asof: "2026-10-23",
    basis: "one_month",
    order: "desc",
    n: 10,
    filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
    candidates: [
      { ticker: "A1", name: "가", selected_return_pct: 11.4873, selected_basis_start_date: "2026-09-23", selected_basis_end_date: "2026-10-23" },
      { ticker: "B2", name: "나", selected_return_pct: 9.702, selected_basis_start_date: "2026-09-23", selected_basis_end_date: "2026-10-23" },
    ],
    daily_topn: [],
    one_month_topn: [],
    three_month_topn: [],
    market_context: {
      status: "ok",
      asof: "2026-10-23",
      regime_label: "하락장",
      regime_code: "bear",
      warnings: [],
      kodex200: { status: "ok", ma20_distance_pct: -1, ma60_distance_pct: -2, ma20_position: "below", ma60_position: "below" },
      kospi:
        kospiState === "ok"
          ? { status: "ok", display_state: "ok", as_of_date: "2026-10-23", daily_return_pct: -1, return_20d_pct: -3.5, return_60d_pct: -7.25 }
          : { status: "stale", display_state: "stale", as_of_date: "2026-10-22", trading_day_lag: 6 },
      regime_streak: { regime_code: "bear", streak_days: 11, at_least: false },
      primary_benchmark: "KODEX200",
      regime_reasons: [],
    },
    market_risk_reference: {
      kodex200: { availability: "available", as_of_date: "2026-10-23", recent_20d_series: [] },
      vix:
        kospiState === "ok"
          ? { availability: "available", as_of_date: "2026-10-22", recent_20d_series: [], freshness: { state: "fresh" } }
          : { availability: "available", as_of_date: "2026-10-22", recent_20d_series: [] },
    },
  };
}
const EVIDENCE = {
  status: "ok",
  asof: "2026-10-23",
  summary: {
    total_holdings_count: 1,
    evidence_unavailable_count: 0,
    constituents_unavailable_count: 0,
    nav_discount_unavailable_count: 0,
  },
  holdings: [],
  price_basis: { reference_date: "2026-10-23", reference_ticker: "069500", kodex200_start_date_5d: null, kodex200_start_date_20d: null, date_mismatch: [] },
  warnings: [],
};
const HOLDINGS = {
  items: [
    {
      ticker: "069500", name: "KODEX200", price_missing: false, eval_amount: 1000, invested_amount: 900,
      current_price: 10, price_source: "naver", price_asof: "2026-10-23T15:30:00+09:00",
    },
  ],
};
const NAV = { status: "ok", asof: "2026-10-23", summary: { unavailable_count: 0, failed_count: 0 } };
const SERIES = {
  ticker: "KOSPI",
  availability: "AVAILABLE",
  available_from: "2026-10-01",
  available_to: "2026-10-22",
  series: [
    { date: "2026-10-21", price: 5550 },
    { date: "2026-10-22", price: 5533 },
  ],
};
// 시장 흐름 — 수급 · 원/달러가 국내 기대 기준일(10/23)과 같음(서버 freshness).
const FLOW = {
  generated_at: "2026-10-24T09:00:00+09:00",
  D: "2026-10-23",
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
  today_lines: ["시장 흐름 6개월(10/23까지): 코스피 -13.78%"],
  ai_text: {},
  freshness: {
    today_kst: "2026-10-24",
    expected_kr: "2026-10-23",
    expected_kr_basis: "calendar",
    items: [
      { key: "flows", label: "외국인 수급", last_date: "2026-10-23", expected: "2026-10-23", basis: "kr_t1", state: "fresh", behind: 0, reason: null },
      { key: "usdkrw", label: "원/달러", last_date: "2026-10-23", expected: "2026-10-23", basis: "kr_t1", state: "fresh", behind: 0, reason: null },
      { key: "wti", label: "WTI", last_date: "2026-10-22", expected: null, basis: "observed_only", state: "observed", behind: null, reason: null },
    ],
  },
};
const LEDGER = {
  today_kst: "2026-10-24",
  sync: { has_copy: true, last_success_at: "2026-10-23T14:27:25+09:00", last_failure_at: null, last_failure_kind: null },
  kinds: [
    { kind: "market_briefing", label: "시장 브리핑", time_kst: "2026-10-23T08:30:02+09:00", run_date_kst: "2026-10-23", delivery_status: "sent", run_status: "sent" },
    { kind: "holdings_briefing", label: "보유 브리핑", time_kst: "2026-10-23T12:30:02+09:00", run_date_kst: "2026-10-23", delivery_status: "sent", run_status: "sent" },
    { kind: "holdings_risk_alert", label: "장중 급등락", time_kst: "2026-10-23T13:30:01+09:00", run_date_kst: "2026-10-23", delivery_status: "skipped", run_status: "skipped" },
  ],
};

const READ_FNS = [
  fetchBenchmarkSeries,
  fetchMarketFlowContext,
  fetchEnrichedHoldings,
  fetchHoldingsMarketEvidence,
  fetchNavDiscountLatest,
  fetchForwardComparison,
];

function prime(kospiState: "ok" | "stale" = "stale") {
  fetchMarketTopnLatest.mockResolvedValue(marketOk(kospiState));
  fetchEnrichedHoldings.mockResolvedValue(HOLDINGS);
  fetchHoldingsMarketEvidence.mockResolvedValue(EVIDENCE);
  fetchNavDiscountLatest.mockResolvedValue(NAV);
  fetchBenchmarkSeries.mockResolvedValue(SERIES);
  fetchOciStartupStatus.mockResolvedValue({ reachable: true, overall: "OPERATING", summary_line: "OCI 정상", jobs: [], note: "" });
  fetchMarketFlowContext.mockResolvedValue(FLOW);
  fetchForwardComparison.mockResolvedValue(FWD);
  fetchLedgerLatestByKind.mockResolvedValue(LEDGER);
  refreshMarket.mockResolvedValue({});
  postMarketRefresh.mockResolvedValue({ status: "accepted", refresh_id: "r1", message: "", cooldown_remaining_seconds: 0 });
  fetchMarketRefreshStatus.mockResolvedValue({ status: "idle", refresh_id: null, cooldown_remaining_seconds: 0 });
}

beforeEach(() => {
  __resetQueryCache();
  vi.clearAllMocks();
  prime();
});

const summary = () => screen.getByLabelText("지금 확인할 내용");
const row = (id: string) => summary().querySelector(`[data-row="${id}"]`) as HTMLElement;
const flowCard = () => screen.getByLabelText("시장 흐름");
const freshCard = () => screen.queryByLabelText("자료 최신화 필요");
function openFresh() {
  const b = screen.queryByRole("button", { name: "자료 최신화 필요 펼치기" });
  if (b) fireEvent.click(b);
  return screen.getByTestId("tc-fresh-body");
}
const dialog = () => screen.queryByTestId("tc-stale-dialog");

async function renderView(onNavigate = vi.fn()) {
  const r = render(<TodayInvestmentCheckView onNavigate={onNavigate} />);
  await waitFor(() => expect(within(row("research")).queryByText("불러오는 중")).toBeNull());
  await waitFor(() => expect(screen.getByTestId("tc-flow-regime").textContent).not.toContain("불러오는 중"));
  await waitFor(() => expect(within(screen.getByLabelText("보유 점검")).queryByText(/불러오는 중/)).toBeNull());
  return { ...r, onNavigate };
}

describe("POC6-16 · POC6-27 지금 확인할 내용", () => {
  it("첫 진입 = 기존 조회 8개 + 원장 사본 1개 + 시장 갱신 상태 1회 · 명령 0 · 왕복 = 캐시 재사용(자료 새 호출 0)", async () => {
    const { unmount } = await renderView();
    expect(fetchMarketTopnLatest).toHaveBeenCalledTimes(1);
    expect(fetchOciStartupStatus).toHaveBeenCalledTimes(1);
    expect(fetchLedgerLatestByKind).toHaveBeenCalledTimes(1);
    for (const f of READ_FNS) expect(f).toHaveBeenCalledTimes(1);
    expect(fetchForwardComparison).toHaveBeenCalledWith();
    expect(refreshMarket).not.toHaveBeenCalled();
    expect(postMarketRefresh).not.toHaveBeenCalled();
    expect(fetchMarketRefreshStatus).toHaveBeenCalledTimes(1); // 들어올 때 상태 1회(진행 중이면 이어 봄 · 시작 0 · PLAN 쟁점 5)
    unmount();
    vi.clearAllMocks();
    prime();
    render(<TodayInvestmentCheckView onNavigate={vi.fn()} />);
    await screen.findByText("KOSPI 가격 흐름");
    expect(fetchMarketTopnLatest).not.toHaveBeenCalled();
    for (const f of READ_FNS) expect(f).not.toHaveBeenCalled();
  });

  it("배치: 머리말 → 자료 최신화 · OCI → 지금 확인할 내용(시장 흐름 → 보유 점검 | 잘 오르는 ETF → 자세히 좌우 → 자료 · 연구 · 사용자 결정 ④)", async () => {
    await renderView();
    const seq = [
      screen.getByRole("heading", { level: 1, name: "오늘의 투자 점검" }),
      freshCard() as HTMLElement,
      screen.getByLabelText("OCI 운영 스케줄 확인"),
      flowCard(),
      screen.getByLabelText("보유 점검"),
      screen.getByLabelText("잘 오르는 ETF"),
      screen.getByLabelText("보유 자세히"),
      screen.getByLabelText("잘 오르는 ETF 자세히"),
      screen.getByRole("group", { name: "자료 · 연구 상태" }),
    ];
    for (let i = 1; i < seq.length; i++) {
      expect(seq[i - 1].compareDocumentPosition(seq[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
    const data = screen.getByRole("group", { name: "자료 · 연구 상태" });
    expect(Array.from(data.querySelectorAll("[data-row]")).map((e) => e.getAttribute("data-row"))).toEqual(["data", "research"]);
  });

  it("사용자 결정 ⑤ — 맨 위 두 카드는 어느 쪽 버튼으로든 함께 펼치고 함께 접는다 · 다시 들어오면 둘 다 접힘", async () => {
    const { unmount } = await renderView();
    const btn = (name: string) => screen.getByRole("button", { name });
    expect(btn("자료 최신화 필요 펼치기")).toHaveAttribute("aria-expanded", "false");
    expect(btn("OCI 운영 스케줄 확인 펼치기")).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(btn("OCI 운영 스케줄 확인 펼치기"));
    expect(screen.getByTestId("tc-fresh-body")).toBeInTheDocument();
    expect(screen.getByTestId("tc-oci-body")).toBeInTheDocument();
    expect(btn("자료 최신화 필요 접기")).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(btn("자료 최신화 필요 접기"));
    expect(screen.queryByTestId("tc-fresh-body")).toBeNull();
    expect(screen.queryByTestId("tc-oci-body")).toBeNull();
    fireEvent.click(btn("자료 최신화 필요 펼치기"));
    expect(screen.getByTestId("tc-oci-body")).toBeInTheDocument();
    fireEvent.click(btn("OCI 운영 스케줄 확인 접기"));
    expect(screen.queryByTestId("tc-fresh-body")).toBeNull();
    expect(screen.queryByTestId("tc-oci-body")).toBeNull();
    fireEvent.click(btn("OCI 운영 스케줄 확인 펼치기"));
    unmount();
    await renderView();
    expect(screen.queryByTestId("tc-fresh-body")).toBeNull();
    expect(screen.queryByTestId("tc-oci-body")).toBeNull();
  });

  it("요약 = 원래 구역 값(시장 판정 · KOSPI 상태 · 잘 오르는 ETF 수 · 연구 결론)", async () => {
    await renderView();
    expect(screen.getByTestId("tc-flow-regime").textContent).toBe("하락장 · 11거래일째");
    // KOSPI 가 화면 판정상 지연이면 20 · 60거래일 값을 보이지 않고 기존 사유를 보인다(복사문과 같은 규칙).
    expect(screen.getByTestId("tc-tile-20").textContent).toContain("확인 불가");
    const flowText = flowCard().textContent ?? "";
    expect(flowText).toContain("KOSPI 기준일 2026-10-22 · 6거래일 지연");
    expect(within(screen.getByLabelText("잘 오르는 ETF")).getByText("1개월 수익률 높은 순 2개")).toBeInTheDocument();
    expect(within(screen.getByLabelText("잘 오르는 ETF 자세히")).getByText("1개월 수익률 높은 순 2개")).toBeInTheDocument();
    expect(within(row("research")).getByText("아직 비교할 결과가 없습니다")).toBeInTheDocument();
  });

  it("KOSPI 정상이면 20 · 60거래일 값 · 기준일을 칸에 보인다(시장 판정 응답 그대로)", async () => {
    prime("ok");
    await renderView();
    expect(screen.getByTestId("tc-tile-20").textContent).toContain("-3.50%");
    expect(screen.getByTestId("tc-tile-20").textContent).toContain("10/23 기준");
    expect(screen.getByTestId("tc-tile-60").textContent).toContain("-7.25%");
  });

  it("[요약 다시 읽기] = 저장 자료 6개만 원천별 1번 · 시장 판정 · 목록 · OCI · 명령 0 · 중복 클릭 막음 · 완료 표시", async () => {
    prime("ok");
    await renderView();
    vi.clearAllMocks();
    prime("ok");
    let release!: () => void;
    fetchHoldingsMarketEvidence.mockImplementation(() => new Promise((r) => (release = () => r(EVIDENCE))));
    fireEvent.click(screen.getByRole("button", { name: "요약 다시 읽기" }));
    const running = await screen.findByRole("button", { name: "다시 읽는 중..." });
    expect(running).toBeDisabled();
    fireEvent.click(running);
    // 다 끝나기 전에는 완료를 보이지 않는다 · 도는 동안 [보유 현재가 업데이트](POST 뒤 다시 읽기)도 막힌다(검토 지적 4 · 11)
    expect(screen.queryByTestId("tc-reload-state")).toBeNull();
    expect(screen.getAllByRole("button", { name: "보유 현재가 업데이트" }).every((b) => (b as HTMLButtonElement).disabled)).toBe(true);
    await act(async () => release());
    await screen.findByText(/^다시 읽기 완료 · /);
    expect(dialog()).toBeNull(); // 모두 최신 → 창 없이 바로 반영
    for (const f of READ_FNS) expect(f).toHaveBeenCalledTimes(1);
    expect(fetchMarketTopnLatest).not.toHaveBeenCalled();
    expect(fetchOciStartupStatus).not.toHaveBeenCalled();
    expect(refreshMarket).not.toHaveBeenCalled();
    expect(postMarketRefresh).not.toHaveBeenCalled();
    // 안내 문장(설계 §2)은 [?] 안에.
    fireEvent.click(screen.getByRole("button", { name: "요약 다시 읽기 도움말" }));
    expect(screen.getByRole("dialog", { name: "요약 다시 읽기 도움말" }).textContent).toContain(
      "저장된 값만 다시 읽습니다. 시장 판정과 요즘 잘 오르는 ETF 목록은 이 버튼으로 다시 계산하지 않습니다.",
    );
  });

  it("판정 Q3 — 늦은 자료가 있으면 고르기 전에는 반영 안 함 · [취소] = 화면 · 공유 캐시 · 읽은 시각 그대로", async () => {
    await renderView(); // KOSPI 지연(늦음)
    const readBefore = screen.getByTestId("tc-read-range").textContent;
    fetchForwardComparison.mockResolvedValueOnce({ ...FWD, status: "NO_RECORDS" });
    fireEvent.click(screen.getByRole("button", { name: "요약 다시 읽기" }));
    const dlg = await screen.findByTestId("tc-stale-dialog");
    expect(dlg.textContent).toContain("최신 상태를 확인해야 할 자료가 있습니다. 현재 저장된 자료로 계속할까요?");
    expect(dlg.querySelector('[data-fresh="kospi"]')?.textContent).toContain("마지막 2026-10-22");
    // 설계자 2026-11-10 — 같은 버튼을 다시 누를지 고민하지 않게
    expect(screen.getByTestId("tc-stale-continue-note")).toHaveTextContent("[이 자료로 계속]을 선택하면 위에 표시된 기준일로 볼 수 있습니다.");
    // 창이 열려 있는 동안 연구 줄은 이전 값 그대로(새 값 '예측 기록 없음'을 아직 반영하지 않음).
    expect(within(row("research")).getByText("아직 비교할 결과가 없습니다")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "요약 다시 읽기" })).toBeDisabled();
    fireEvent.click(within(dlg).getByRole("button", { name: "취소" }));
    expect(dialog()).toBeNull();
    expect(within(row("research")).getByText("아직 비교할 결과가 없습니다")).toBeInTheDocument();
    expect(screen.getByTestId("tc-read-range").textContent).toBe(readBefore);
    expect(screen.getByTestId("tc-reload-state").textContent).toContain("다시 읽기 취소 · 화면 값은 그대로입니다");
    // 상단 두 최신화 버튼은 그대로 누를 수 있다.
    expect(screen.getAllByRole("button", { name: "보유 현재가 업데이트" })[0]).not.toBeDisabled();
    expect(screen.getAllByRole("button", { name: "최신 시장 데이터 갱신" })[0]).not.toBeDisabled();
  });

  it("판정 Q3 — [이 자료로 계속] = 창에 보인 같은 결과 반영(다시 조회 없음) · 완료 표시", async () => {
    await renderView();
    fetchForwardComparison.mockResolvedValueOnce({ ...FWD, status: "NO_RECORDS" });
    fireEvent.click(screen.getByRole("button", { name: "요약 다시 읽기" }));
    const dlg = await screen.findByTestId("tc-stale-dialog");
    const calls = READ_FNS.map((f) => f.mock.calls.length);
    fireEvent.click(within(dlg).getByRole("button", { name: "이 자료로 계속" }));
    expect(within(row("research")).getByText("예측 기록 없음")).toBeInTheDocument();
    expect(READ_FNS.map((f) => f.mock.calls.length)).toEqual(calls);
    expect(screen.getByTestId("tc-reload-state").textContent).toMatch(/^다시 읽기 완료 · /);
  });

  it("다시 읽기 일부 실패 — 창에 '불러오지 못함 · 이전 값 유지' · 계속하면 실패 원천만 이전 값 + 그 시각 · 완료로 위장 안 함", async () => {
    prime("ok");
    await renderView();
    fetchHoldingsMarketEvidence.mockRejectedValueOnce(new Error("x"));
    fetchForwardComparison.mockResolvedValueOnce({ ...FWD, status: "NO_RECORDS" });
    fireEvent.click(screen.getByRole("button", { name: "요약 다시 읽기" }));
    const dlg = await screen.findByTestId("tc-stale-dialog");
    expect(dlg.querySelector('[data-failed="보유 근거"]')?.textContent).toMatch(/불러오지 못함 · 이전 값\(.+에 읽음\) 유지 · x/);
    fireEvent.click(within(dlg).getByRole("button", { name: "이 자료로 계속" }));
    expect(await screen.findByText(/^다시 읽기 일부 실패\(보유 근거\)/)).toBeInTheDocument();
    expect(screen.getByLabelText("보유 점검").textContent).toMatch(/보유 근거: 다시 읽기 실패 · \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}에 읽은 값을 표시 중/);
    expect(within(row("research")).getByText("예측 기록 없음")).toBeInTheDocument();
    expect(row("research").textContent).not.toContain("다시 읽기 실패");
    // 보유 근거로 만든 정비 항목을 보이는 자료 확인 줄에도 그 값의 시각(검토 지적 3)
    expect(row("data").textContent).toMatch(/보유 근거: 다시 읽기 실패 · \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}에 읽은 값을 표시 중/);
  });

  it("[보유 현재가 업데이트](POST 뒤 다시 읽기)가 도는 동안 [요약 다시 읽기]는 막힘 — 같은 조회가 겹쳐 POST 전 값으로 완료되지 않게(검토 지적 4)", async () => {
    await renderView();
    let done!: () => void;
    refreshMarket.mockImplementation(() => new Promise((r) => (done = () => r({}))));
    fireEvent.click(screen.getAllByRole("button", { name: "보유 현재가 업데이트" })[0]);
    await waitFor(() => expect(screen.getByRole("button", { name: "요약 다시 읽기" })).toBeDisabled());
    await act(async () => done());
    await waitFor(() => expect(screen.getByRole("button", { name: "요약 다시 읽기" })).not.toBeDisabled());
  });

  it("판정 Q2 — 시장 자료 지연 할 일은 맨 위 「자료 최신화 필요」 안 · 버튼은 이 화면 [최신 시장 데이터 갱신](누를 때만 시작)", async () => {
    const { onNavigate } = await renderView();
    expect(screen.getByTestId("tc-fresh-summary").textContent).toContain("6거래일 늦음");
    const body = openFresh();
    const task = body.querySelector('[data-task="market_refresh"]') as HTMLElement;
    expect(task.textContent).toContain("시장 자료 갱신이 필요합니다.");
    expect(task.textContent).toContain("지금 PC에 저장된 시장 자료: KOSPI 2026-10-22 · ETF 가격 2026-10-23");
    expect(task.textContent).toContain("[최신 시장 데이터 갱신]을 눌러 주세요(맨 위 버튼과 같은 작업).");
    expect(postMarketRefresh).not.toHaveBeenCalled();
    fireEvent.click(within(body).getByRole("button", { name: "최신 시장 데이터 갱신" }));
    await waitFor(() => expect(postMarketRefresh).toHaveBeenCalledTimes(1));
    expect(onNavigate).not.toHaveBeenCalled();
    expect(refreshMarket).not.toHaveBeenCalled();
    expect(await screen.findByTestId("tc-market-result")).toHaveTextContent("시장 데이터 갱신 중입니다");
    // 같은 작업은 진행 중 다시 시작하지 않는다(중복 실행 막음).
    for (const b of screen.getAllByRole("button", { name: /시장 데이터 갱신/ })) expect(b).toBeDisabled();
  });

  it("늦은 자료 · 할 일이 없으면 「자료 최신화 필요」 카드 없음 · 연구 대기는 할 일이 아님", async () => {
    prime("ok");
    await renderView();
    await waitFor(() => expect(freshCard()).toBeNull());
    expect(within(row("data")).getByText("갱신 필요 없음")).toBeInTheDocument();
    expect(within(row("research")).getByText("아직 비교할 결과가 없습니다")).toBeInTheDocument();
  });

  it("첫 조회 실패(보유) — 상태 모름 할 일 + [요약 다시 읽기] · 미갱신으로 단정 안 함 · 다른 칸은 정상", async () => {
    prime("ok");
    fetchEnrichedHoldings.mockRejectedValue(new Error("x"));
    await renderView();
    const body = openFresh();
    expect(body.textContent).toContain("자료 상태를 확인하지 못했습니다. 다시 읽어 주세요.");
    expect(body.querySelector('[data-task="market_refresh"]')).toBeNull();
    expect(within(body).getByRole("button", { name: "요약 다시 읽기" })).toBeInTheDocument();
    expect(screen.getByTestId("tc-risk-failed").textContent).toBe("보유 자료를 불러오지 못했습니다.");
    expect(screen.getByTestId("tc-flow-regime").textContent).toBe("하락장 · 11거래일째");
  });

  it("버튼 — 카드 · 줄마다 이동 목적지(자료 확인 줄은 버튼 없음 · 바로 아래 펼침)", async () => {
    const { onNavigate } = await renderView();
    expect(row("data").querySelectorAll(".tc-sum-go button")).toHaveLength(0);
    const primaries = Array.from(row("research").querySelectorAll(".tc-sum-go button")).filter((b) => !b.classList.contains("tc-fold-btn"));
    expect(primaries.map((b) => b.textContent)).toEqual(["예측과 결과 비교"]);
    for (const [area, name, key] of [
      ["보유 점검", "확인 근거 보기 →", "holdings_evidence"],
      ["보유 점검", "보유 현황 보기 →", "holdings"],
      ["잘 오르는 ETF", "요즘 잘 오르는 ETF →", "market_discovery"],
      ["잘 오르는 ETF 자세히", "ETF 비교하기", "workbench"],
    ] as const) {
      fireEvent.click(within(screen.getByLabelText(area)).getByRole("button", { name }));
      expect(onNavigate).toHaveBeenLastCalledWith(key);
    }
    fireEvent.click(within(row("research")).getByRole("button", { name: "예측과 결과 비교" }));
    expect(onNavigate).toHaveBeenLastCalledWith("ml");
    fireEvent.click(within(flowCard()).getByRole("button", { name: "시장 흐름 자세히(요즘 잘 오르는 ETF)" }));
    expect(onNavigate).toHaveBeenLastCalledWith("market_discovery");
  });

  it("같은 화면 이동 — [보유 자세히 ↓] · [ETF 자세히 ↓]는 목적 카드로 스크롤하고 포커스 · 화면 전환 없음", async () => {
    const spy = vi.fn();
    Element.prototype.scrollIntoView = spy;
    const { onNavigate } = await renderView();
    fireEvent.click(screen.getByRole("button", { name: "보유 자세히 ↓" }));
    expect(document.activeElement).toBe(screen.getByLabelText("보유 자세히"));
    fireEvent.click(screen.getByRole("button", { name: "ETF 자세히 ↓" }));
    expect(document.activeElement).toBe(screen.getByLabelText("잘 오르는 ETF 자세히"));
    expect(spy).toHaveBeenCalledTimes(2);
    expect(onNavigate).not.toHaveBeenCalled();
  });

  // 검증자 r1 F1 — 원천 7개 × 첫 조회 실패(이전 값 없음): 화면에서 빠지지 않고 · 정비 점검 원천이면 '갱신 필요 없음'이 아니다.
  it.each([
    ["시장 목록", fetchMarketTopnLatest, true, "market_unknown"],
    ["KOSPI 가격 흐름", fetchBenchmarkSeries, false, "read_failed"],
    ["수급 · 환율 · 유가", fetchMarketFlowContext, false, "read_failed"],
    ["보유", fetchEnrichedHoldings, true, "read_failed"],
    ["보유 근거", fetchHoldingsMarketEvidence, true, "read_failed"],
    ["ETF 기준가", fetchNavDiscountLatest, true, "read_failed"],
    ["연구", fetchForwardComparison, false, "read_failed"],
  ] as const)("첫 조회 실패 — %s", async (_name, fn, checksData, taskId) => {
    prime("ok");
    fn.mockRejectedValue(new Error("x"));
    render(<TodayInvestmentCheckView onNavigate={vi.fn()} />);
    await waitFor(() => expect(within(row("data")).queryByText("확인 중")).toBeNull());
    await waitFor(() => expect(freshCard()).not.toBeNull());
    const body = openFresh();
    await waitFor(() => expect(body.querySelector(`[data-task="${taskId}"]`)).not.toBeNull());
    expect(body.querySelector('[data-task="market_refresh"]')).toBeNull();
    if (checksData) expect(within(row("data")).queryByText("갱신 필요 없음")).toBeNull();
  });

  it("연구 줄 — 실제 예측 기준일 범위(보고 만든 시각과 따로)", async () => {
    await renderView();
    expect(row("research").textContent).toContain(
      "예측이 기록된 기준일 2개(2026-10-27 ~ 2026-10-29) · 비교 보고에 들어간 기준일 3개(2026-10-22 ~ 2026-10-29)",
    );
  });

  // 검증자 r2 F3 재현 조합 — 두 원천이 함께 첫 조회 실패해도 '오래됐거나 없는 자료와 함께'라고 하지 않는다 · 실제 결측과 섞일 때만 '함께'.
  it.each([
    ["보유 + NAV", [fetchEnrichedHoldings, fetchNavDiscountLatest], false],
    ["보유 + 보유 근거", [fetchEnrichedHoldings, fetchHoldingsMarketEvidence], false],
    ["시장 목록 + NAV", [fetchMarketTopnLatest, fetchNavDiscountLatest], false],
    ["보유 실패 + 실제 구성종목 결측(대조)", [fetchEnrichedHoldings], true],
  ] as const)("조회 실패 조합 — %s", async (_n, fns, realMissing) => {
    prime("ok");
    if (realMissing) {
      fetchHoldingsMarketEvidence.mockResolvedValue({ ...EVIDENCE, summary: { ...EVIDENCE.summary, constituents_unavailable_count: 25 } });
    }
    for (const f of fns) f.mockRejectedValue(new Error("x"));
    render(<TodayInvestmentCheckView onNavigate={vi.fn()} />);
    await waitFor(() => expect(within(row("data")).queryByText("확인 중")).toBeNull());
    await waitFor(() => expect(row("data").textContent).toMatch(/불러오지 못/));
    const basis = row("data").querySelector(".tc-sum-basis")?.textContent ?? "";
    if (realMissing) expect(basis).toContain("오래됐거나 없는 자료와 불러오지 못한 자료가 함께 있습니다");
    else {
      expect(basis).not.toContain("오래됐거나 없는");
      expect(basis).toMatch(/오래됐다는 뜻은 아님/);
    }
  });
});
