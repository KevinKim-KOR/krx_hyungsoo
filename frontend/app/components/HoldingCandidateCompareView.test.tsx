// 「ETF보유 및 후보 선정 › 보유와 후보 비교」 화면 계약(POC6-29 · PLAN 판정 2026-11-12 Q1 · Q4-1 · Q4-2 · Q10).
// 요약 · 상세 수치 · 보유 · 판단 근거 요청을 가짜로 바꿔 응답을 통제한다. 실제 네트워크 · 운영 자료 미의존.
// - 이 화면 조건으로 요약을 1회 읽고, 고른 보유 하나 · 후보 하나의 상세 수치를 한 번에 읽는다.
// - 보완 2차 S3(PLAN §10-6 · S 판정 Q-S6): 기본 비교 표(1 · 3개월 + 같은 기간 KODEX 200 · 최근 5 · 20구간 · 고점 대비 ·
//   항목마다 두 값 + 차이 줄) → 종목별 근거(후보 · 보유 탭 하나 · 판단 근거 미리보기 · [AI 세션에서 검토]).
// - 「보유」 행의 [보유와 후보 비교에서 보기 →]가 넘긴 보유를 먼저 고른다.
// - 후보 판단 근거는 이 화면의 공통 기간 목록(쪽 · 순위 · 날짜 · 가격 시점)으로 요청한다.
// - POC6-32 V2 [비교 상세](PLAN §3-2 D1 ~ D6): 두 칸 모두 빈 선택에서 시작(기본 짝 없음) · 넘겨받은 쪽만 채움 ·
//   같은 종목 = '같은 종목입니다' · 상품 확인 표(공식 기준정보 요청도 가짜) · 차이 줄은 '같은 공식 기초지수'일 때만.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import {
  __resetEtfCompareCondition,
  getScreenCondition,
  presetOneTimeCondition,
  setScreenCondition,
} from "@/lib/etfCompareCondition";
import type { EtfDetailItem } from "@/lib/api/etfDetail";
import type { EtfOfficialResponse, OfficialItem, OfficialPair, OfficialPairState } from "@/lib/api/etfOfficial";
import { detailItem, detailResponse, period, summaryOk } from "@/lib/etfCompareTestFixtures";
import { pairOk } from "@/lib/pairExposureTestFixtures";
import type { PairQuery } from "@/lib/api/pairExposure";

const fetchEtfCompareSummary = vi.fn();
const fetchEtfDetail = vi.fn();
const fetchEnrichedHoldings = vi.fn();
const postDecisionDraftPreview = vi.fn();
const fetchPairExposure = vi.fn();
const fetchEtfOfficial = vi.fn();

vi.mock("@/lib/api/etfCompare", async (orig) => ({
  ...(await orig<typeof import("@/lib/api/etfCompare")>()),
  fetchEtfCompareSummary: (...a: unknown[]) => fetchEtfCompareSummary(...a),
}));
vi.mock("@/lib/api/etfDetail", async (orig) => ({
  ...(await orig<typeof import("@/lib/api/etfDetail")>()),
  fetchEtfDetail: (...a: unknown[]) => fetchEtfDetail(...a),
}));
vi.mock("@/lib/api/etfOfficial", async (orig) => ({
  ...(await orig<typeof import("@/lib/api/etfOfficial")>()),
  fetchEtfOfficial: (...a: unknown[]) => fetchEtfOfficial(...a),
}));
vi.mock("@/lib/api/pairExposure", async (orig) => ({
  ...(await orig<typeof import("@/lib/api/pairExposure")>()),
  fetchPairExposure: (...a: unknown[]) => fetchPairExposure(...a),
}));
vi.mock("@/lib/api", () => ({
  fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
  postDecisionDraftPreview: (...a: unknown[]) => postDecisionDraftPreview(...a),
}));

import { useState } from "react";
import HoldingCandidateCompareView from "./HoldingCandidateCompareView";
import { presetCompareCandidate, presetCompareHolding } from "./workbench/compareSelection";
import { detailStateText, useEtfDetail } from "./workbench/DetailNumbers";

function item(ticker: string, name: string, weight: number | null) {
  return { ticker, name, quantity: 1, current_price: 100, eval_amount: 1000, market_weight_pct: weight, price_missing: false };
}

// POC6-32 V2 — GET /market/etf-official 시험 응답(서버 app/etf_official_info 와 같은 모양 · 합성 값).
function offItem(ticker: string, over: Partial<OfficialItem> = {}): OfficialItem {
  return {
    ticker,
    found: true,
    kind: "etf",
    name: `ETF ${ticker}`,
    index_name: "시험 지수 A",
    index_provider: "시험 산출기관",
    market: "국내",
    asset: "주식",
    multiple: "일반",
    replication: "실물(패시브)",
    fee_pct: "0.150000",
    tax: "배당소득세(보유기간과세)",
    listed: "2020/01/02",
    missing_reason: null,
    ...over,
  };
}
const PAIR: Record<OfficialPairState, OfficialPair> = {
  same: { state: "same", label: "같은 공식 기초지수", reason: "두 상품 모두 공식 기초지수 '시험 지수 A'", structure_diffs: [] },
  same_family: {
    state: "same_family",
    label: "다른 지수 · 같은 계열",
    reason: "공식 기초지수명이 다름('시험 지수 A' ↔ '시험 지수 A 커버드콜') · 같은 기초지수 계열로 확인됨(시험 계열)",
    structure_diffs: [],
  },
  different: { state: "different", label: "다른 지수", reason: "공식 기초지수가 다름('시험 지수 A' ↔ '시험 지수 B')", structure_diffs: [] },
  unconfirmed: { state: "unconfirmed", label: "기준 미확인", reason: "공식 기준정보에 없음", structure_diffs: [] },
};
function officialResp(ts: string[], state: OfficialPairState = "same", over: Partial<EtfOfficialResponse> = {}): EtfOfficialResponse {
  return {
    csv: { name: "krx_etf_basic_20260927.csv", asof: "2026-09-27", ok: true, error: null },
    items: Object.fromEntries(ts.map((t) => [t, offItem(t)])),
    pair: PAIR[state],
    ...over,
  };
}

const nav = vi.fn();
beforeEach(() => {
  __resetQueryCache();
  __resetEtfCompareCondition();
  window.sessionStorage.clear();
  for (const f of [fetchEtfCompareSummary, fetchEtfDetail, fetchEnrichedHoldings, postDecisionDraftPreview, fetchPairExposure, fetchEtfOfficial, nav])
    f.mockReset();
  fetchPairExposure.mockImplementation((q: PairQuery) => Promise.resolve(pairOk(q)));
  // 기본 = 같은 공식 기초지수(기존 차이 줄 규칙이 그대로 보이는 경우) · 지수 상태별 경우는 아래 조합 표.
  fetchEtfOfficial.mockImplementation((ts: string[]) => Promise.resolve(officialResp(ts)));
  fetchEtfCompareSummary.mockResolvedValue(summaryOk());
  fetchEtfDetail.mockImplementation((ts: string[]) => Promise.resolve(detailResponse(ts)));
  // 같은 종목 두 계좌(10 + 15 = 25) > 다른 종목 20 — 비중 큰 순 첫째 = B00001.
  fetchEnrichedHoldings.mockResolvedValue({
    items: [item("H00002", "분산 ETF", 20), item("B00001", "반도체 전공정", 10), item("B00001", "반도체 전공정", 15)],
  });
});

const tid = (id: string) => screen.getByTestId(id).textContent ?? "";

// 보완 R3 — 끝일 가격 상태(상세 응답 end_price). 장중 저장 = 같은 날 15:30 전 저장.
const INTRA = { date: "2026-11-09", state: "intraday" as const, fetched_at_kst: "2026-11-09T10:05:00+09:00" };
const AFTER = { date: "2026-11-09", state: "after_close" as const, fetched_at_kst: "2026-11-10T13:18:02+09:00" };
const UNKNOWN = { date: "2026-11-09", state: "unknown" as const, fetched_at_kst: null };

// 첫 종목 = 보유(B00001) · 둘째 = 후보(상위 1위)로 상세 응답을 바꾼다.
function detailWith(hold: Partial<EtfDetailItem>, cand: Partial<EtfDetailItem>) {
  fetchEtfDetail.mockImplementation((ts: string[]) =>
    Promise.resolve(detailResponse(ts, { items: [detailItem(ts[0], hold), detailItem(ts[1], cand)] })),
  );
}

const sel = (id: "hcc-holding" | "hcc-candidate") => screen.getByTestId(id) as HTMLSelectElement;

// V2 — 기본 짝이 없으므로 시험이 직접 고른다(보유 먼저 · 후보 다음 → 판단 근거 대상 = 후보 탭).
// 고른 뒤 waitFor 로 끝낸다 — 고르기가 시작한 조회의 응답이 act 밖에서 화면을 바꾸지 않게(waitFor 가 그 응답까지 흘려보냄).
async function pick(holding: string | null = "B00001", cand: string | null = `top:${summaryOk().top[0].ticker}`) {
  if (holding) {
    await waitFor(() => expect(sel("hcc-holding")).not.toBeDisabled());
    fireEvent.change(sel("hcc-holding"), { target: { value: holding } });
    await waitFor(() => expect(sel("hcc-holding").value).toBe(holding));
  }
  if (cand) {
    await waitFor(() => expect(sel("hcc-candidate")).not.toBeDisabled());
    fireEvent.change(sel("hcc-candidate"), { target: { value: cand } });
    await waitFor(() => expect(sel("hcc-candidate").value).toBe(cand));
  }
}

async function renderLoaded() {
  render(<HoldingCandidateCompareView onNavigate={nav} />);
  await pick();
  await waitFor(() => expect(screen.getByTestId("hcc-diff-m1")).toBeInTheDocument());
}

describe("「보유와 후보 비교」", () => {
  it("V2 — 두 칸 모두 빈 선택에서 시작(기본 짝 없음 · 상세 · 공식 기준정보 조회 없음) · 둘 다 고르면 두 종목 상세를 한 번에 읽어 기본 비교 표", async () => {
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    expect(screen.getByRole("heading", { level: 1, name: "보유와 후보 비교" })).toBeInTheDocument();
    await waitFor(() => expect(sel("hcc-holding")).not.toBeDisabled());
    await waitFor(() => expect(sel("hcc-candidate")).not.toBeDisabled());
    expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(1);
    expect(fetchEtfCompareSummary.mock.calls[0][0]).toEqual(getScreenCondition("compare"));
    // 보유 비중 1위(B00001) · 후보 1위를 고른 것처럼 보이지 않는다.
    expect(sel("hcc-holding").value).toBe("");
    expect(sel("hcc-candidate").value).toBe("");
    expect(screen.getByRole("option", { name: "보유를 고르세요" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "후보를 고르세요" })).toBeInTheDocument();
    expect(screen.queryByText(/다시 고르세요/)).toBeNull();
    expect(fetchEtfDetail).not.toHaveBeenCalled();
    expect(fetchEtfOfficial).not.toHaveBeenCalled();
    expect(fetchPairExposure).not.toHaveBeenCalled();
    expect(tid("hcc-name-holding")).toBe("—");
    expect(tid("hcc-price-holding")).toBe("보유를 고르세요");
    expect(tid("hcc-price-candidate")).toBe("후보를 고르세요");
    expect(tid("hcc-diff-pending")).toBe("보유와 후보를 고르면 비교합니다");
    for (const k of ["m1", "m3", "w5", "w20", "drawdown"]) expect(screen.queryByTestId(`hcc-diff-${k}`)).toBeNull();
    expect(screen.queryByTestId("hcc-product")).toBeNull();
    expect(tid("hcc-ev-who")).toBe("후보 · 후보를 고르세요");
    expect(screen.getByText("고른 후보가 없습니다 — 위에서 후보를 고르세요.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "보유 판단 근거" }));
    expect(tid("hcc-ev-who")).toBe("보유 · 보유를 고르세요");
    expect(screen.getByText("고른 보유가 없습니다 — 위에서 보유를 고르세요.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "후보 판단 근거" }));
    const top1 = summaryOk().top[0];
    await pick();
    expect(sel("hcc-holding").value).toBe("B00001");
    expect(sel("hcc-candidate").value).toBe(`top:${top1.ticker}`);
    await waitFor(() => expect(tid("hcc-holding-m1")).toContain("-10.25%"));
    expect(fetchEtfDetail).toHaveBeenLastCalledWith(["B00001", top1.ticker]);
    // 공식 기준정보 = [보유, 후보] 순서로 한 번(서버 pair 의 a = 보유 · b = 후보).
    expect(fetchEtfOfficial).toHaveBeenCalledTimes(1);
    expect(fetchEtfOfficial).toHaveBeenLastCalledWith(["B00001", top1.ticker]);
    expect(tid("hcc-name-holding")).toBe("반도체 전공정");
    expect(tid("hcc-name-candidate")).toBe(top1.name);
    expect(tid("hcc-badge-holding")).toBe("보유 · 비중 25.00%");
    expect(tid("hcc-badge-candidate")).toBe("후보 · 1개월 상위 1위");
    // 왼쪽 보유 · 오른쪽 후보(표 머리 · 값 칸 모두 문서 순서).
    const after = (a: string, b: string) =>
      expect(screen.getByTestId(a).compareDocumentPosition(screen.getByTestId(b)) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    after("hcc-head-holding", "hcc-head-candidate");
    for (const k of ["m1", "m3", "w5", "w20", "drawdown"]) after(`hcc-holding-${k}`, `hcc-candidate-${k}`);
    expect(tid("hcc-e-decline")).toBe("보유 종목만 판정합니다");
  });

  it("값 없음 · 기간 다름은 0 으로 채우지 않고 사유 · 실제 날짜를 적는다(행 상세 · 표와 같은 문장)", async () => {
    fetchEtfDetail.mockImplementation((ts: string[]) =>
      Promise.resolve(
        detailResponse(ts, {
          items: [
            detailItem(ts[0], { m12: period(null, null, null, "missing", "history_short") }),
            detailItem(ts[1], { m3: period(7.1, "2026-08-20", "2026-11-09", "period_differs") }),
          ],
        }),
      ),
    );
    await renderLoaded();
    await waitFor(() => expect(tid("hcc-candidate-m3")).toContain("기간 다름 · 실제 8/20 → 11/9"));
    fireEvent.click(screen.getByRole("button", { name: "보유 판단 근거" }));
    expect(tid("hcc-e-m12")).toContain("값 없음");
    expect(tid("hcc-e-m12")).not.toContain("0.00%");
    expect(tid("hcc-candidate-m3")).not.toContain("7.10");
    expect(tid("hcc-diff-m3")).toBe("3개월: 기간이 달라 비교하지 않음(보유 8/11 → 11/9 · 후보 8/20 → 11/9)");
  });

  it("「보유」에서 넘긴 보유만 채우고 후보는 빈칸(V2 기본 짝 없음) · 보유 판단 근거를 연다 · 다시 열면 둘 다 빈칸(한 번만)", async () => {
    presetCompareHolding("H00002");
    const { unmount } = render(<HoldingCandidateCompareView onNavigate={nav} />);
    await waitFor(() => expect(sel("hcc-holding").value).toBe("H00002"));
    await waitFor(() => expect(sel("hcc-candidate")).not.toBeDisabled());
    expect(sel("hcc-candidate").value).toBe("");
    expect(tid("hcc-preset-holding")).toBe("「보유」에서 고른 보유로 열렸습니다 · 비교할 후보를 고르세요");
    expect(screen.getByRole("button", { name: "보유 판단 근거" })).toHaveAttribute("aria-pressed", "true");
    await waitFor(() => expect(fetchEtfDetail).toHaveBeenLastCalledWith(["H00002"]));
    expect(tid("hcc-diff-pending")).toBe("후보를 고르면 비교합니다");
    expect(fetchEtfOfficial).not.toHaveBeenCalled();
    // 후보를 고르면 안내의 '후보를 고르세요'가 내려간다(넘겨받은 보유 안내는 그대로).
    await pick(null);
    await waitFor(() => expect(tid("hcc-preset-holding")).toBe("「보유」에서 고른 보유로 열렸습니다"));
    unmount();
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    await waitFor(() => expect(sel("hcc-holding")).not.toBeDisabled());
    expect(sel("hcc-holding").value).toBe("");
    expect(screen.queryByTestId("hcc-preset-holding")).toBeNull();
    expect(screen.getByRole("button", { name: "후보 판단 근거" })).toHaveAttribute("aria-pressed", "true");
  });

  it("후보 판단 근거 = 이 화면의 공통 기간 목록에서 고른 쪽 · 순위 · 날짜 · 가격 시점을 보낸다 · 시장 흐름 6개월", async () => {
    postDecisionDraftPreview.mockResolvedValue({ status: "error", message: "목록이 바뀌었습니다 — 목록을 다시 읽고 다시 고르세요." });
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    const b1 = summaryOk().bottom[1];
    await pick("B00001", `bottom:${b1.ticker}`);
    // POC6-31 C25 — 그 후보 · 고른 보유 · 이 화면 조건의 구성종목 비교를 읽은 뒤에 만들 수 있다.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "판단 근거 미리보기 생성" })).not.toBeDisabled(),
    );
    expect(fetchPairExposure).toHaveBeenLastCalledWith({
      candidate: b1.ticker,
      holding: "B00001",
      screen: "holding_candidate_compare",
      basis: "one_month",
      side: "bottom",
      rank: b1.rank,
      start_date: b1.basis_return.start,
      end_date: b1.basis_return.end,
      filters: summaryOk().filters,
    });
    fireEvent.click(screen.getByRole("button", { name: "판단 근거 미리보기 생성" }));
    await waitFor(() => expect(postDecisionDraftPreview).toHaveBeenCalledTimes(1));
    const [kind, ticker, q, flowPeriod, pair] = postDecisionDraftPreview.mock.calls[0];
    expect(pair).toEqual({ holding: "B00001", fingerprint: `fp-${b1.ticker}-B00001` });
    expect(kind).toBe("candidate");
    expect(ticker).toBe(b1.ticker);
    expect(q).toMatchObject({
      list_source: "common_period",
      screen: "holding_candidate_compare",
      basis: "one_month",
      side: "bottom",
      rank: b1.rank,
      start_date: b1.basis_return.start,
      end_date: b1.basis_return.end,
      end_price_state: b1.end_price.state,
    });
    expect(flowPeriod).toBe("6M");
    expect(await screen.findByText("목록이 바뀌었습니다 — 목록을 다시 읽고 다시 고르세요.")).toBeInTheDocument();
  });

  it("이 화면 조건은 다른 화면과 따로 — 「후보리스트」 기간을 바꿔도 이 화면 조회는 그대로", async () => {
    setScreenCondition("candidates", { ...getScreenCondition("candidates"), basis: "three_month" });
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    await waitFor(() => expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(1));
    expect(fetchEtfCompareSummary.mock.calls[0][0].basis).toBe("one_month");
    expect(within(screen.getByTestId("ec-save-compare")).getByRole("button")).toBeInTheDocument();
  });

  it("[다시 불러오기] = 요약 · 보유와 함께 두 종목 상세 · 공식 기준정보도 다시 읽는다 · '확인 중'에 멈추지 않음(검토 지적)", async () => {
    await renderLoaded();
    await waitFor(() => expect(tid("hcc-holding-m1")).toContain("-10.25%"));
    const calls = fetchEtfDetail.mock.calls.length;
    const offCalls = fetchEtfOfficial.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "다시 불러오기" }));
    await waitFor(() => expect(fetchEtfDetail.mock.calls.length).toBeGreaterThan(calls));
    await waitFor(() => expect(fetchEtfOfficial.mock.calls.length).toBeGreaterThan(offCalls));
    await waitFor(() => expect(screen.getByTestId("hcc-index-chip")).toHaveTextContent("같은 공식 기초지수"));
    await waitFor(() => expect(tid("hcc-candidate-m1")).toContain("-10.25%"));
    expect(screen.queryByText("상세 수치 확인 중...")).toBeNull();
    expect(screen.getByTestId("hcc-diff-m1")).toBeInTheDocument();
  });

  // 검토 NAV-1 — MainPanel 은 보낸 화면을 내리지 않고 숨겨 둔다. 그 화면의 열린 행 상세(같은 상세 조회 hook · 다른 키)가
  // [다시 불러오기] 뒤에도 자기 값을 그대로 가져야 한다(앞부분으로 지우면 그 칸은 스스로 다시 읽지 않아 '확인 중'에 멈춤).
  it.each<[string, string[], [string | null, string | null]]>([
    ["다른 종목 행 상세", ["S00001"], ["B00001", `top:${summaryOk().top[0].ticker}`]],
    // 이 화면 키(보유 하나만 고름)가 앞부분으로 겹치는 보낸 화면 키(여러 종목 [표])도 지우지 않는다(정확히 같은 키만)
    ["앞부분이 겹치는 여러 종목 키", ["B00001", "S00001"], ["B00001", null]],
  ])("[다시 불러오기]는 이 화면 키만 지운다 — 숨긴 보낸 화면(%s)은 돌아가도 값 그대로", async (_t, senderTickers, picks) => {
    function SenderRow() {
      const d = useEtfDetail(senderTickers);
      return <p data-testid="sender-detail">{detailStateText(d, senderTickers[0]) ?? "보낸 화면 상세 있음"}</p>;
    }
    function Stack() {
      const [onDetail, setOnDetail] = useState(false);
      return (
        <>
          <div hidden={onDetail}>
            <SenderRow />
            <button type="button" onClick={() => setOnDetail(true)}>
              비교 상세 열기
            </button>
          </div>
          {onDetail ? (
            <>
              <button type="button" onClick={() => setOnDetail(false)}>
                ← 보낸 화면으로
              </button>
              <HoldingCandidateCompareView onNavigate={nav} />
            </>
          ) : null}
        </>
      );
    }
    render(<Stack />);
    await waitFor(() => expect(tid("sender-detail")).toBe("보낸 화면 상세 있음"));
    fireEvent.click(screen.getByRole("button", { name: "비교 상세 열기" }));
    await pick(...picks);
    await waitFor(() => expect(tid("hcc-holding-m1")).toContain("-10.25%"));
    const calls = fetchEtfDetail.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "다시 불러오기" }));
    await waitFor(() => expect(fetchEtfDetail.mock.calls.length).toBeGreaterThan(calls));
    await waitFor(() => expect(tid("hcc-holding-m1")).toContain("-10.25%"));
    fireEvent.click(screen.getByRole("button", { name: "← 보낸 화면으로" }));
    expect(tid("sender-detail")).toBe("보낸 화면 상세 있음");
    // 보낸 화면 키는 다시 읽지 않았다(지워지지 않음 · 그 화면 자기 조회 1번 그대로)
    expect(fetchEtfDetail.mock.calls.filter((c) => (c[0] as string[]).join(",") === senderTickers.join(","))).toHaveLength(1);
  });

  it("고점 대비(기본 비교) = 기간 다름 · 값 없음은 행 상세와 같은 문장 · 차이 줄은 값 없음 사유(0 으로 채우지 않음)", async () => {
    fetchEtfDetail.mockImplementation((ts: string[]) =>
      Promise.resolve(
        detailResponse(ts, {
          items: [
            detailItem(ts[0], {
              drawdown: { status: "period_differs", value: -3.2, start: "2026-10-10", end: "2026-11-09", peak_date: "2026-10-20", peak_close: 10300, close: 9970, reason: null },
            }),
            detailItem(ts[1], { drawdown: { status: "missing", value: null, start: null, end: null, peak_date: null, peak_close: null, close: null, reason: "insufficient_history" } }),
          ],
        }),
      ),
    );
    await renderLoaded();
    expect(tid("hcc-holding-drawdown")).toBe("20저장일 10/10 ~ 11/9 · 고점 10/20 10,300원 → -3.20% · 기간 다름");
    expect(tid("hcc-candidate-drawdown")).toBe("값 없음 · 저장 이력 부족");
    expect(tid("hcc-diff-drawdown")).toBe("고점 대비: 비교하지 않음 — 후보 값 없음 · 저장 이력 부족");
    expect(tid("hcc-diff-drawdown")).not.toMatch(/0\.00|작음|큼|같음/);
  });

  it("보유 판단 근거 = 이 화면 조건(기간 · 제외)을 함께 보낸다 — 서버가 그 조건 목록으로 후보 관계를 확인(판정 Q4-2)", async () => {
    postDecisionDraftPreview.mockResolvedValue({ status: "error", message: "x" });
    // 요약 응답은 요청한 조건의 목록이다(화면은 보이는 목록의 조건을 보낸다).
    fetchEtfCompareSummary.mockImplementation((c: { basis: "daily" | "one_month" | "three_month" }) => Promise.resolve(summaryOk({ basis: c.basis })));
    setScreenCondition("compare", { ...getScreenCondition("compare"), basis: "three_month" });
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    await pick("B00001", null);
    await waitFor(() => expect(fetchEtfDetail).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "보유 판단 근거" }));
    fireEvent.click(screen.getByRole("button", { name: "판단 근거 미리보기 생성" }));
    await waitFor(() => expect(postDecisionDraftPreview).toHaveBeenCalledTimes(1));
    const [kind, ticker, q] = postDecisionDraftPreview.mock.calls[0];
    expect(kind).toBe("holding");
    expect(ticker).toBe("B00001");
    expect(q).toMatchObject({ list_source: "common_period", screen: "holding_candidate_compare", basis: "three_month", exclude_inverse: true });
  });

  it("보유를 못 읽으면 그 사실을 적고 고른 후보 값 칸은 그대로 · 차이 줄은 만들지 않음(0 으로 채우지 않음)", async () => {
    fetchEnrichedHoldings.mockRejectedValue(new Error("down"));
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    expect(await screen.findByText("보유를 불러오지 못했습니다")).toBeInTheDocument();
    await pick(null);
    await waitFor(() => expect(fetchEtfDetail).toHaveBeenCalledWith([summaryOk().top[0].ticker]));
    await waitFor(() => expect(tid("hcc-candidate-m1")).toContain("-10.25%"));
    expect(tid("hcc-name-holding")).toBe("—");
    expect(tid("hcc-price-holding")).toBe("보유 목록을 읽지 못해 고를 보유가 없습니다");
    for (const k of ["m1", "m3", "w5", "w20", "drawdown"]) expect(tid(`hcc-holding-${k}`)).toBe("—");
    expect(tid("hcc-diff-pending")).toBe("보유 목록을 읽지 못해 비교하지 않습니다");
    for (const k of ["m1", "m3", "w5", "w20", "drawdown"]) expect(screen.queryByTestId(`hcc-diff-${k}`)).toBeNull();
    expect(screen.queryByTestId("hcc-product")).toBeNull();
    expect(fetchEtfOfficial).not.toHaveBeenCalled();
  });

  it("기본 비교 값 칸 = 1 · 3개월 큰 숫자(색 · 부호 · 실제 날짜) · 같은 기간 KODEX 200 대비 · 최근 5 · 20구간 · 고점 대비 · 가격 기준", async () => {
    detailWith(
      {},
      {
        m1: period(14.55),
        same_kodex: {
          one_month: { status: "ok", value: 37.19, etf_return_pct: 14.55, kodex200_return_pct: -22.64, start: "2026-10-12", end: "2026-11-09", reason: null },
          three_month: { status: "period_differs", value: null, etf_return_pct: null, kodex200_return_pct: null, start: "2026-08-20", end: "2026-11-09", reason: "start_differs" },
        },
        m3: period(null, "2026-08-20", "2026-11-09", "period_differs", "start_differs"),
      },
    );
    await renderLoaded();
    expect(tid("hcc-holding-m1")).toBe("10/12 → 11/9-10.25%KODEX 200 대비 +12.39%p (KODEX 200 -22.64% · 같은 기간)");
    expect(tid("hcc-holding-m3")).toBe("8/11 → 11/9-5.50%KODEX 200 대비 +10.20%p (KODEX 200 -15.70% · 같은 기간)");
    expect(tid("hcc-candidate-m1")).toBe("10/12 → 11/9+14.55%KODEX 200 대비 +37.19%p (KODEX 200 -22.64% · 같은 기간)");
    // 기간 다름 = 큰 숫자 대신 실제 날짜 · KODEX 200 대비도 기간 다름(0 으로 채우지 않음).
    expect(tid("hcc-candidate-m3")).toBe("기간 다름 · 실제 8/20 → 11/9 · 시작일 다름KODEX 200 대비 기간 다름");
    // 최근 5 · 20구간 = 실제 기간 · 값(KODEX 200 줄 없음) · 고점 대비 = 20저장일 창 · 값 · 고점일(고점 가격).
    expect(tid("hcc-holding-w5")).toBe("11/2 → 11/9-1.20%");
    expect(tid("hcc-holding-w20")).toBe("10/13 → 11/9-8.40%");
    expect(tid("hcc-holding-drawdown")).toBe("20저장일 10/13 → 11/9-3.00%고점 10/20(10,300원)");
    expect(within(screen.getByTestId("hcc-holding-drawdown")).getByText("-3.00%")).toHaveStyle({ color: "var(--pnl-down)" });
    // 색 = 국내 관례(상승 빨강 · 하락 파랑 토큰).
    expect(within(screen.getByTestId("hcc-holding-m1")).getByText("-10.25%")).toHaveStyle({ color: "var(--pnl-down)" });
    expect(within(screen.getByTestId("hcc-candidate-m1")).getByText("+14.55%")).toHaveStyle({ color: "var(--pnl-up)" });
    expect(within(screen.getByTestId("hcc-candidate-m1")).getByText("+37.19%p")).toHaveStyle({ color: "var(--pnl-up)" });
    // 가격 기준(마감 뒤 저장 · 잠정 배지 없음).
    expect(tid("hcc-price-holding")).toBe("가격 11/9 마감 뒤 저장(11/10 13:18 저장)");
    expect(tid("hcc-price-candidate")).toBe("가격 11/9 마감 뒤 저장(11/10 13:18 저장)");
    expect(within(screen.getByTestId("hcc-basic")).queryByText("잠정")).toBeNull();
    // 거래량 · 흔들림은 기본 비교에 넣지 않는다(Q-R4 (a)).
    expect(tid("hcc-basic")).not.toMatch(/거래량|흔들림/);
    // 한 항목 = 값 줄 + 바로 아래 차이 줄(같은 묶음 안).
    for (const k of ["m1", "m3", "w5", "w20", "drawdown"]) {
      const row = screen.getByTestId(`hcc-row-${k}`);
      expect(within(row).getByTestId(`hcc-holding-${k}`)).toBeInTheDocument();
      expect(within(row).getByTestId(`hcc-diff-${k}`)).toBeInTheDocument();
    }
  });

  it("같은 기간 KODEX 200 대비 값 없음 = 사유(쉬운 한국어) · 장중 저장값 = 시각 + 잠정 배지 · 확인 필요", async () => {
    detailWith(
      {
        end_price: INTRA,
        same_kodex: {
          ...detailItem("x").same_kodex,
          three_month: { status: "missing", value: null, etf_return_pct: null, kodex200_return_pct: null, start: "2026-08-11", end: "2026-11-09", reason: "kodex200_start_price_missing" },
        },
      },
      { end_price: UNKNOWN },
    );
    await renderLoaded();
    expect(tid("hcc-holding-m3")).toContain("-5.50%");
    expect(tid("hcc-holding-m3")).toContain("KODEX 200 대비 값 없음 · KODEX 200 시작일 가격 없음");
    expect(tid("hcc-price-holding")).toBe("가격 11/9 10:05 장중 저장 잠정");
    expect(within(screen.getByTestId("hcc-price-holding")).getByText("잠정")).toHaveClass("tc-sum-badge");
    expect(tid("hcc-price-candidate")).toBe("가격 11/9 · 가격 시점 확인 필요");
  });

  const DIFF_CASES: [string, Partial<EtfDetailItem>, Partial<EtfDetailItem>, string, string, string][] = [
    [
      "둘 다 마감 뒤 · 같은 기간 = 보통 비교",
      {},
      { m1: period(14.55) },
      "compared",
      "1개월(10/12 → 11/9 · 같은 기간): 후보가 24.80%p 높음",
      "3개월(8/11 → 11/9 · 같은 기간): 같음",
    ],
    [
      "둘 다 장중 = 잠정 비교",
      { end_price: INTRA },
      { end_price: INTRA, m1: period(-12.5) },
      "provisional",
      "잠정 비교 · 1개월(10/12 → 11/9 · 같은 기간): 보유가 2.25%p 높음(두 쪽 모두 장중 저장값)",
      "잠정 비교 · 3개월(8/11 → 11/9 · 같은 기간): 같음(두 쪽 모두 장중 저장값)",
    ],
    [
      "가격 상태 다름(보유 장중 · 후보 마감 뒤)",
      { end_price: INTRA },
      { end_price: AFTER },
      "not_compared",
      "1개월(10/12 → 11/9): 가격 상태가 달라 비교하지 않음(보유 장중 · 후보 마감 뒤)",
      "3개월(8/11 → 11/9): 가격 상태가 달라 비교하지 않음(보유 장중 · 후보 마감 뒤)",
    ],
    [
      "기간 다름(시작일이 다름)",
      {},
      { m1: period(3, "2026-10-13"), m3: period(null, "2026-08-20", "2026-11-09", "period_differs", "start_differs") },
      "not_compared",
      "1개월: 기간이 달라 비교하지 않음(보유 10/12 → 11/9 · 후보 10/13 → 11/9)",
      "3개월: 기간이 달라 비교하지 않음(보유 8/11 → 11/9 · 후보 8/20 → 11/9)",
    ],
    [
      "값 없음(보유) = 자료 상태 · 사유",
      { m1: period(null, null, "2026-11-09", "missing", "insufficient_history") },
      {},
      "not_compared",
      "1개월: 비교하지 않음 — 보유 값 없음 · 저장 이력 부족",
      "3개월(8/11 → 11/9 · 같은 기간): 같음",
    ],
    [
      "가격 시점 확인 필요(후보)",
      {},
      { end_price: UNKNOWN },
      "not_compared",
      "1개월(10/12 → 11/9): 비교하지 않음 — 가격 시점 확인 필요(후보)",
      "3개월(8/11 → 11/9): 비교하지 않음 — 가격 시점 확인 필요(후보)",
    ],
  ];

  it.each(DIFF_CASES)("차이 줄 — %s", async (_name, hold, cand, kind, m1, m3) => {
    detailWith(hold, cand);
    await renderLoaded();
    expect(tid("hcc-diff-m1")).toBe(m1);
    expect(screen.getByTestId("hcc-diff-m1")).toHaveAttribute("data-kind", kind);
    expect(tid("hcc-diff-m3")).toBe(m3);
    if (kind === "not_compared") expect(tid("hcc-diff-m1")).not.toMatch(/0\.00%p|같음/);
  });

  // 보완 2차 S3 — 새 줄(최근 5 · 20구간 · 고점 대비)의 차이 줄. 고정 자료 기본 = 최근 5구간 11/2 → 11/9 -1.20% ·
  // 최근 20구간 10/13 → 11/9 -8.40% · 고점 대비 20저장일 10/13 → 11/9 -3.00% · 마감 뒤 저장.
  const DD0 = detailItem("x").drawdown;
  type NewKey = "w5" | "w20" | "drawdown";
  const NEW_ROW_CASES: [string, Partial<EtfDetailItem>, Partial<EtfDetailItem>, Record<NewKey, [string, string]>][] = [
    [
      "같은 기간 · 둘 다 마감 뒤 = 차이 · 후보 하락폭이 작음",
      {},
      { w5: period(-0.92, "2026-11-02"), w20: period(6.6, "2026-10-13"), drawdown: { ...DD0, value: -0.5 } },
      {
        w5: ["compared", "최근 5구간(11/2 → 11/9 · 같은 기간): 후보가 0.28%p 높음"],
        w20: ["compared", "최근 20구간(10/13 → 11/9 · 같은 기간): 후보가 15.00%p 높음"],
        drawdown: ["compared", "고점 대비(20저장일 10/13 → 11/9 · 같은 기간): 후보 하락폭이 2.50%p 작음"],
      },
    ],
    [
      "보유가 높음 · 같음 · 후보 하락폭이 큼",
      {},
      { w5: period(-3.2, "2026-11-02"), drawdown: { ...DD0, value: -7.25 } },
      {
        w5: ["compared", "최근 5구간(11/2 → 11/9 · 같은 기간): 보유가 2.00%p 높음"],
        w20: ["compared", "최근 20구간(10/13 → 11/9 · 같은 기간): 같음"],
        drawdown: ["compared", "고점 대비(20저장일 10/13 → 11/9 · 같은 기간): 후보 하락폭이 4.25%p 큼"],
      },
    ],
    [
      "둘 다 장중 = 잠정 비교(하락폭 같음 포함)",
      { end_price: INTRA },
      { end_price: INTRA, w20: period(-7.4, "2026-10-13") },
      {
        w5: ["provisional", "잠정 비교 · 최근 5구간(11/2 → 11/9 · 같은 기간): 같음(두 쪽 모두 장중 저장값)"],
        w20: ["provisional", "잠정 비교 · 최근 20구간(10/13 → 11/9 · 같은 기간): 후보가 1.00%p 높음(두 쪽 모두 장중 저장값)"],
        drawdown: ["provisional", "잠정 비교 · 고점 대비(20저장일 10/13 → 11/9 · 같은 기간): 하락폭 같음(두 쪽 모두 장중 저장값)"],
      },
    ],
    [
      "가격 상태 다름(보유 장중 · 후보 마감 뒤)",
      { end_price: INTRA },
      { end_price: AFTER },
      {
        w5: ["not_compared", "최근 5구간(11/2 → 11/9): 가격 상태가 달라 비교하지 않음(보유 장중 · 후보 마감 뒤)"],
        w20: ["not_compared", "최근 20구간(10/13 → 11/9): 가격 상태가 달라 비교하지 않음(보유 장중 · 후보 마감 뒤)"],
        drawdown: ["not_compared", "고점 대비(20저장일 10/13 → 11/9): 가격 상태가 달라 비교하지 않음(보유 장중 · 후보 마감 뒤)"],
      },
    ],
    [
      "기간 · 20저장일 창이 다름",
      {},
      {
        w5: period(null, "2026-11-01", "2026-11-07", "period_differs", "end_differs"),
        w20: period(2, "2026-10-10"),
        drawdown: { ...DD0, status: "period_differs", value: -1, start: "2026-10-10", end: "2026-11-07", reason: "end_differs" },
      },
      {
        w5: ["not_compared", "최근 5구간: 기간이 달라 비교하지 않음(보유 11/2 → 11/9 · 후보 11/1 → 11/7)"],
        w20: ["not_compared", "최근 20구간: 기간이 달라 비교하지 않음(보유 10/13 → 11/9 · 후보 10/10 → 11/9)"],
        drawdown: ["not_compared", "고점 대비: 기간이 달라 비교하지 않음(보유 20저장일 10/13 → 11/9 · 후보 20저장일 10/10 → 11/7)"],
      },
    ],
    [
      "값 없음(보유) = 자료 상태 · 사유",
      {
        w5: period(null, null, "2026-11-09", "missing", "insufficient_history"),
        w20: period(null, null, "2026-11-09", "missing", "insufficient_history"),
        drawdown: { ...DD0, status: "missing", value: null, start: null, end: null, peak_date: null, peak_close: null, close: null, reason: "insufficient_history" },
      },
      {},
      {
        w5: ["not_compared", "최근 5구간: 비교하지 않음 — 보유 값 없음 · 저장 이력 부족"],
        w20: ["not_compared", "최근 20구간: 비교하지 않음 — 보유 값 없음 · 저장 이력 부족"],
        drawdown: ["not_compared", "고점 대비: 비교하지 않음 — 보유 값 없음 · 저장 이력 부족"],
      },
    ],
  ];

  it.each(NEW_ROW_CASES)("새 줄 차이 — %s", async (_name, hold, cand, expected) => {
    detailWith(hold, cand);
    await renderLoaded();
    for (const k of ["w5", "w20", "drawdown"] as NewKey[]) {
      const [kind, text] = expected[k];
      expect(tid(`hcc-diff-${k}`)).toBe(text);
      expect(screen.getByTestId(`hcc-diff-${k}`)).toHaveAttribute("data-kind", kind);
      if (kind === "not_compared") expect(tid(`hcc-diff-${k}`)).not.toMatch(/0\.00%p|같음|높음|작음|큼/);
    }
  });

  it("새 줄 값 칸 — 기간 다름 · 값 없음은 0 으로 채우지 않고 실제 날짜 · 사유", async () => {
    detailWith(
      { w20: period(null, null, "2026-11-09", "missing", "insufficient_history") },
      { w5: period(null, "2026-11-01", "2026-11-07", "period_differs", "end_differs") },
    );
    await renderLoaded();
    expect(tid("hcc-candidate-w5")).toBe("기간 다름 · 실제 11/1 → 11/7 · 끝일 다름");
    expect(tid("hcc-holding-w20")).toBe("값 없음 · 저장 이력 부족");
    for (const id of ["hcc-candidate-w5", "hcc-holding-w20"]) expect(tid(id)).not.toMatch(/0\.00/);
  });

  it("상세를 읽는 중 · 실패면 차이 줄을 만들지 않고 그 사실만 적는다", async () => {
    fetchEtfDetail.mockRejectedValue(new Error("down"));
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    await pick();
    expect(await screen.findByText("상세 수치를 읽지 못해 차이를 적지 않습니다")).toBeInTheDocument();
    for (const k of ["m1", "m3", "w5", "w20", "drawdown"]) expect(screen.queryByTestId(`hcc-diff-${k}`)).toBeNull();
    expect(tid("hcc-price-holding")).toBe("상세 수치 조회 실패 — [다시 불러오기]로 다시 시도하세요.");
  });

  it("종목별 근거 = 후보 · 보유 탭 하나 · 접기 없음 · 시장가 · NAV · 괴리율 · 6 · 12개월 · 20구간 KODEX 200 차이 · 하락 판정 · 구성종목 겹침", async () => {
    await renderLoaded();
    const ev = screen.getByTestId("hcc-evidence");
    // 값 칸은 접지 않는다(POC6-29). 펼치기는 구성종목 비교의 계산 입력 · ETF별 저장 행뿐(POC6-31 C22 '같은 자리에서 펼쳐 읽음').
    await waitFor(() => expect(screen.getByTestId("pe-block")).toBeInTheDocument());
    for (const d of Array.from(ev.querySelectorAll("details"))) {
      expect(screen.getByTestId("pe-block").contains(d)).toBe(true);
    }
    expect(screen.queryByTestId("hcc-fold-long")).toBeNull();
    // 처음 = 후보 탭.
    expect(tid("hcc-ev-who")).toBe(`후보 · ${summaryOk().top[0].name}`);
    expect(tid("hcc-e-nav")).toBe("10,000원 · 10,010원 · -0.10% · 11/9 자료");
    expect(tid("hcc-e-m6")).toBe("+12.30% (5/12 → 11/9)");
    expect(tid("hcc-e-m12")).toBe("+30.10% (2025-11-10 → 11/9)");
    expect(tid("hcc-e-excess")).toBe("+6.10%p (이 종목 -8.40% · KODEX 200 -14.50% · 같은 10/13 → 11/9)");
    expect(tid("hcc-e-decline")).toBe("보유 종목만 판정합니다");
    // POC6-31 C22 — 예전 '구성종목 겹침' 자리 = 구성종목 비교(확인 범위 먼저 · 후보 · 고른 보유 · 내 보유 전체).
    await waitFor(() => expect(tid("hcc-e-cons")).toContain("확인 범위(먼저 읽기)"));
    const cons = tid("hcc-e-cons");
    expect(cons).toContain("구성종목 비교 — 후보 주요 주식과 내 보유");
    expect(cons).not.toContain("구성종목 겹침");
    expect(within(ev).getByRole("button", { name: "판단 근거 미리보기 생성" })).toBeInTheDocument();
    // 보유 탭 = 보유 종목의 근거(하락 판정) · 구성종목 비교는 고른 두 종목의 비교라 두 탭이 같다.
    fireEvent.click(within(ev).getByRole("button", { name: "보유 판단 근거" }));
    expect(within(ev).getByRole("button", { name: "보유 판단 근거" })).toHaveAttribute("aria-pressed", "true");
    expect(tid("hcc-ev-who")).toBe("보유 · 반도체 전공정");
    expect(tid("hcc-e-decline")).toBe("하락 구간 아님");
    expect(tid("hcc-e-cons")).toBe(cons);
    expect(tid("hcc-e-nav")).toBe("10,000원 · 10,010원 · -0.10% · 11/9 자료");
    expect(within(ev).getByRole("button", { name: "판단 근거 미리보기 생성" })).toBeInTheDocument();
  });

  it("종목별 근거 — 상세를 못 읽으면 안내만 · 값 칸은 비움(0 으로 채우지 않음)", async () => {
    fetchEtfDetail.mockRejectedValue(new Error("down"));
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    await pick();
    await waitFor(() => expect(tid("hcc-ev-who")).toContain("상세 수치 조회 실패"));
    for (const id of ["hcc-e-nav", "hcc-e-m6", "hcc-e-m12", "hcc-e-excess"]) expect(tid(id)).toBe("—");
  });

  it("화면 순서 = 고르기 → 상품 확인(지수 상태) → 기본 비교(1 · 3개월 · 최근 5 · 20구간 · 고점 대비) → 종목별 근거 → 미리보기 → [AI 세션에서 검토]까지 닿는다", async () => {
    postDecisionDraftPreview.mockResolvedValue({
      status: "ok",
      target_kind: "candidate",
      ticker: summaryOk().top[0].ticker,
      preview_text: "[대상]\n- 시험 후보",
      generated_at: "2026-11-10T13:20:00+09:00",
      evidence_as_of: { target_as_of_date: "2026-11-09", kodex200_as_of_date: "2026-11-09", vix_as_of_date: "2026-11-08" },
    });
    await renderLoaded();
    const ev = screen.getByTestId("hcc-evidence");
    await waitFor(() => expect(screen.getByTestId("hcc-index-state")).toBeInTheDocument());
    const order = [
      screen.getByTestId("hcc-candidate"),
      screen.getByTestId("hcc-product"),
      screen.getByTestId("hcc-product-table"),
      screen.getByTestId("hcc-index-state"),
      screen.getByTestId("hcc-basic"),
      screen.getByTestId("hcc-row-m1"),
      screen.getByTestId("hcc-row-m3"),
      screen.getByTestId("hcc-row-w5"),
      screen.getByTestId("hcc-row-w20"),
      screen.getByTestId("hcc-row-drawdown"),
      ev,
      within(ev).getByRole("button", { name: "후보 판단 근거" }),
      screen.getByTestId("hcc-e-nav"),
      within(ev).getByRole("button", { name: "판단 근거 미리보기 생성" }),
    ];
    for (let i = 1; i < order.length; i++) {
      expect(order[i - 1].compareDocumentPosition(order[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
    // 미리보기 카드는 종목별 근거 안 한 곳(따로 떨어진 카드 없음).
    expect(screen.getAllByRole("button", { name: "판단 근거 미리보기 생성" })).toHaveLength(1);
    // 구성종목 비교는 종목별 근거 값 칸 뒤 · 미리보기 앞.
    await waitFor(() => expect(screen.getByTestId("pe-scope")).toBeInTheDocument());
    expect(
      screen.getByTestId("hcc-e-nav").compareDocumentPosition(screen.getByTestId("hcc-e-cons")) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      screen.getByTestId("hcc-e-cons").compareDocumentPosition(screen.getByTestId("hcc-preview")) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "판단 근거 미리보기 생성" }));
    fireEvent.click(await within(ev).findByRole("button", { name: "AI 세션에서 검토" }));
    expect(screen.getAllByRole("button", { name: "AI 세션에서 검토" })).toHaveLength(1);
    expect(nav).toHaveBeenCalledWith("ai_sessions");
  });
});

// POC6-31(판정 Q10 · PLAN C18 · C23) — 「ETF 구성종목」에서 고른 후보 한 건과 그 목록 조건으로 열기.
describe("「ETF 구성종목」에서 넘어온 후보", () => {
  const cond = { basis: "three_month" as const, filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: false } };
  // 보내는 쪽(ETFExposureView.goCompare)과 같게 — 후보 + 이동 한 번 조건
  const send = (p: Partial<Parameters<typeof presetCompareCandidate>[0]> = {}) => {
    const c = { ticker: "T00003", name: "헬스케어", side: "top" as const, condition: cond, start: "2026-10-12", end: "2026-11-09", ...p };
    presetCompareCandidate(c);
    if (c.condition) presetOneTimeCondition("compare", c.condition);
  };

  it("후보 · 조건을 이번 이동에 쓴다(화면 조건 · 저장된 기본값과 별개) · 그 후보를 첫 선택으로 · 목록 날짜 같음", async () => {
    const before = getScreenCondition("compare");
    send();
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    await waitFor(() => expect(fetchEtfCompareSummary).toHaveBeenCalled());
    expect(fetchEtfCompareSummary.mock.calls[0][0]).toEqual(cond);
    expect(window.localStorage.getItem("krx.screenBasis.compare.v1")).toBeNull(); // 저장된 기본값은 그대로
    expect(getScreenCondition("compare")).toBe(before); // 화면 조건 메모리도 그대로(지적 frontend#6)
    await waitFor(() => expect((screen.getByTestId("hcc-candidate") as HTMLSelectElement).value).toBe("top:T00003"));
    expect(tid("hcc-preset-candidate")).toBe(
      "「ETF 구성종목」에서 고른 후보로 열렸습니다 · 이번 이동 조건 = 3개월 상위(넘긴 목록 조건 · 이 화면을 다시 열면 원래 조건) · 목록 날짜 10/12 → 11/9 같음",
    );
    // V2(D1) — 넘겨받은 후보 쪽만 채운다(보유는 빈칸 · 기본 짝 없음).
    await waitFor(() => expect(sel("hcc-holding")).not.toBeDisabled());
    expect(sel("hcc-holding").value).toBe("");
    expect(tid("hcc-diff-pending")).toBe("보유를 고르면 비교합니다");
  });

  it("POC6-32(검토 F5 · V2 D6) — 보낸 화면 이름이 있으면 그 이름으로(「주간 ETF 점검」에서 고른 후보로 열렸습니다)", async () => {
    send({ origin: "「주간 ETF 점검」" });
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    await waitFor(() => expect(tid("hcc-preset-candidate")).toContain("「주간 ETF 점검」에서 고른 후보로 열렸습니다"));
    expect(tid("hcc-preset-candidate")).not.toContain("「ETF 구성종목」");
  });

  it("넘긴 목록의 시작일 · 끝일이 이 화면 목록과 다르면 이유로 보인다(지적 frontend#5)", async () => {
    send({ start: "2026-10-14", end: "2026-11-13" });
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    await waitFor(() =>
      expect(tid("hcc-preset-candidate")).toContain(
        "넘긴 목록(10/14 → 11/13)과 이 화면 목록(10/12 → 11/9)의 날짜가 다릅니다 — 순위 · 수익률은 이 화면 목록 기준입니다",
      ),
    );
    expect(screen.getByTestId("hcc-preset-candidate").className).toContain("wb-warn");
  });

  it("넘긴 조건이 없으면(예전 초안) '넘겨받은 조건 없음 — 이 화면 조건'", async () => {
    send({ condition: null, start: null, end: null });
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    await waitFor(() => expect(tid("hcc-preset-candidate")).toContain("넘겨받은 조건 없음 — 이 화면 조건(1개월 상위)으로 찾았습니다"));
    expect(fetchEtfCompareSummary.mock.calls[0][0]).toEqual(getScreenCondition("compare"));
  });

  it("화면을 떠났다 다시 열면 원래 화면 조건(이동 한 번 · 지적 frontend#6)", async () => {
    send();
    const { unmount } = render(<HoldingCandidateCompareView onNavigate={nav} />);
    await waitFor(() => expect(fetchEtfCompareSummary).toHaveBeenCalled());
    unmount();
    fetchEtfCompareSummary.mockClear();
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    await waitFor(() => expect(fetchEtfCompareSummary).toHaveBeenCalled());
    expect(fetchEtfCompareSummary.mock.calls[0][0]).toEqual(getScreenCondition("compare"));
    expect(screen.queryByTestId("hcc-preset-candidate")).toBeNull();
  });

  it("이 화면에서 조건을 정하면 사용자 값이 이긴다(넘긴 조건을 내림)", async () => {
    send();
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    await waitFor(() => expect(fetchEtfCompareSummary).toHaveBeenCalled());
    const base = getScreenCondition("compare");
    await act(async () => setScreenCondition("compare", base)); // 같은 값이어도 '정함'
    await waitFor(() => expect(fetchEtfCompareSummary.mock.calls.at(-1)?.[0]).toEqual(base));
  });

  it("그 조건 목록에 없으면 이유를 보이고 다른 종목으로 바꾸지 않는다 · 다른 후보를 고르면 안내를 내린다", async () => {
    presetCompareCandidate({ ticker: "ZZZ999", name: "목록 밖", side: "top", condition: null });
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    await waitFor(() => expect(tid("hcc-preset-candidate")).toContain("이 조건 목록에 없습니다"));
    expect((screen.getByTestId("hcc-candidate") as HTMLSelectElement).value).toBe("");
    // 고르면 그 후보로 바뀐다(넘겨받은 후보가 아니므로 안내 사라짐)
    fireEvent.change(screen.getByTestId("hcc-candidate"), { target: { value: "top:T00002" } });
    await waitFor(() => expect(screen.queryByTestId("hcc-preset-candidate")).toBeNull());
  });
});

// POC6-31 STEP 4 ~ 5(PLAN C21 ~ C25 · 판정 Q12 · Q13) — 구성종목 비교 · 같은 근거로만 미리보기 · 고른 종목 유지.
describe("「보유와 후보 비교」 구성종목 비교 · 같은 근거", () => {
  const okPreview = (ticker: string) => ({
    status: "ok",
    target_kind: "candidate",
    ticker,
    preview_text: "[대상]\n- 시험 후보",
    generated_at: "2026-11-16T13:20:00+09:00",
    evidence_as_of: {
      target_as_of_date: "2026-11-13",
      kodex200_as_of_date: "2026-11-13",
      vix_as_of_date: "2026-11-12",
      candidate_constituents_asof: "2026-11-13",
      holding_constituents_asof: "2026-11-13",
      exposure_asof: "2026-11-13",
    },
  });

  it("고른 보유를 바꾸면 그 보유로 다시 읽는다 · 확인 범위가 표보다 먼저", async () => {
    await renderLoaded();
    await waitFor(() => expect(screen.getByTestId("pe-table")).toBeInTheDocument());
    expect(
      screen.getByTestId("pe-scope").compareDocumentPosition(screen.getByTestId("pe-table")) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    fireEvent.change(screen.getByTestId("hcc-holding"), { target: { value: "H00002" } });
    await waitFor(() => expect(fetchPairExposure).toHaveBeenLastCalledWith(expect.objectContaining({ holding: "H00002" })));
  });

  it("비교를 못 읽으면 미리보기를 만들지 않는다(같은 근거로만) · [다시 불러오기]가 비교도 다시 읽는다", async () => {
    fetchPairExposure.mockRejectedValue(new Error("down"));
    await renderLoaded();
    await waitFor(() => expect(screen.getByTestId("pe-error")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "판단 근거 미리보기 생성" })).toBeDisabled();
    expect(screen.getByTestId("ddp-pair-pending")).toBeInTheDocument();
    const calls = fetchPairExposure.mock.calls.length;
    fetchPairExposure.mockImplementation((q: PairQuery) => Promise.resolve(pairOk(q)));
    fireEvent.click(screen.getByRole("button", { name: "다시 불러오기" }));
    await waitFor(() => expect(fetchPairExposure.mock.calls.length).toBeGreaterThan(calls));
    await waitFor(() => expect(screen.getByRole("button", { name: "판단 근거 미리보기 생성" })).not.toBeDisabled());
  });

  it("서버가 '자료가 바뀌었습니다'면 그 안내 · 고른 보유 · 후보는 그대로", async () => {
    const msg = "자료가 바뀌었습니다 — [다시 불러오기]를 누르세요. 고른 보유 · 후보는 그대로 둡니다.";
    postDecisionDraftPreview.mockResolvedValue({ status: "error", message: msg });
    await renderLoaded();
    const b1 = summaryOk().bottom[1];
    fireEvent.change(screen.getByTestId("hcc-candidate"), { target: { value: `bottom:${b1.ticker}` } });
    fireEvent.change(screen.getByTestId("hcc-holding"), { target: { value: "H00002" } });
    await waitFor(() => expect(screen.getByRole("button", { name: "판단 근거 미리보기 생성" })).not.toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: "판단 근거 미리보기 생성" }));
    expect(await screen.findByText(msg)).toBeInTheDocument();
    expect((screen.getByTestId("hcc-candidate") as HTMLSelectElement).value).toBe(`bottom:${b1.ticker}`);
    expect((screen.getByTestId("hcc-holding") as HTMLSelectElement).value).toBe("H00002");
  });

  it("만든 뒤 근거가 바뀌면([다시 불러오기]) [AI 세션에서 검토] 때 다시 만들지 먼저 묻는다(이동 안 함) · [다시 만들기] = 새 근거로", async () => {
    const t0 = summaryOk().top[0].ticker;
    postDecisionDraftPreview.mockResolvedValue(okPreview(t0));
    await renderLoaded();
    await waitFor(() => expect(screen.getByRole("button", { name: "판단 근거 미리보기 생성" })).not.toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: "판단 근거 미리보기 생성" }));
    await screen.findByRole("button", { name: "AI 세션에서 검토" });
    // 역할별 기준일이 미리보기 날짜 줄에 보인다(C26).
    expect(screen.getByText(/구성: 후보 2026-11-13 · 고른 보유 2026-11-13 · 노출 합계 2026-11-13/)).toBeInTheDocument();
    // 그사이 구성종목 수집 · 시세가 바뀌어 [다시 불러오기]가 새 근거 지문을 받음(같은 후보 · 같은 보유 · 미리보기는 그대로 남음)
    fetchPairExposure.mockImplementation((q: PairQuery) => Promise.resolve(pairOk(q, { fingerprint: "fp-new" })));
    fireEvent.click(screen.getByRole("button", { name: "다시 불러오기" }));
    await waitFor(() => expect(fetchPairExposure.mock.calls.length).toBeGreaterThan(1));
    await waitFor(() => expect(screen.getByRole("button", { name: "다시 생성" })).not.toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: "AI 세션에서 검토" }));
    expect(await screen.findByTestId("ddp-pair-differs")).toHaveTextContent("지금 화면과 미리보기가 다릅니다");
    expect(nav).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "다시 만들기" }));
    await waitFor(() => expect(postDecisionDraftPreview).toHaveBeenCalledTimes(2));
    expect(postDecisionDraftPreview.mock.calls[1][4]).toEqual({ holding: "B00001", fingerprint: "fp-new" });
    fireEvent.click(await screen.findByRole("button", { name: "AI 세션에서 검토" }));
    expect(nav).toHaveBeenCalledWith("ai_sessions");
  });

  it("[다시 불러오기] 뒤 고른 후보 · 보유가 목록에 없으면 첫 종목으로 바꾸지 않고 다시 고르라고 보인다", async () => {
    await renderLoaded();
    const b1 = summaryOk().bottom[1];
    fireEvent.change(screen.getByTestId("hcc-candidate"), { target: { value: `bottom:${b1.ticker}` } });
    fireEvent.change(screen.getByTestId("hcc-holding"), { target: { value: "H00002" } });
    const s2 = summaryOk();
    fetchEtfCompareSummary.mockResolvedValue({ ...s2, bottom: s2.bottom.filter((r) => r.ticker !== b1.ticker) });
    fetchEnrichedHoldings.mockResolvedValue({ items: [item("B00001", "반도체 전공정", 10)] });
    fireEvent.click(screen.getByRole("button", { name: "다시 불러오기" }));
    await waitFor(() => expect(screen.getByTestId("hcc-pick-missing")).toBeInTheDocument());
    expect(screen.getByTestId("hcc-holding-missing")).toBeInTheDocument();
    expect((screen.getByTestId("hcc-candidate") as HTMLSelectElement).value).toBe("");
    expect((screen.getByTestId("hcc-holding") as HTMLSelectElement).value).toBe("");
    // 다시 고르면 안내가 내려간다
    fireEvent.change(screen.getByTestId("hcc-candidate"), { target: { value: `top:${s2.top[0].ticker}` } });
    fireEvent.change(screen.getByTestId("hcc-holding"), { target: { value: "B00001" } });
    await waitFor(() => expect(screen.queryByTestId("hcc-pick-missing")).toBeNull());
    expect(screen.queryByTestId("hcc-holding-missing")).toBeNull();
  });

  it("V2 — 고르지 않았으면 [다시 불러오기] 뒤에도 빈 선택 그대로(첫 종목을 고른 것으로 굳히지 않음 · 기본 짝 없음)", async () => {
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    await waitFor(() => expect(sel("hcc-holding")).not.toBeDisabled());
    await waitFor(() => expect(sel("hcc-candidate")).not.toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: "다시 불러오기" }));
    await waitFor(() => expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(fetchEnrichedHoldings).toHaveBeenCalledTimes(2));
    expect(sel("hcc-holding").value).toBe("");
    expect(sel("hcc-candidate").value).toBe("");
    expect(screen.queryByTestId("hcc-pick-missing")).toBeNull();
    expect(screen.queryByTestId("hcc-holding-missing")).toBeNull();
    expect(screen.getByRole("option", { name: "보유를 고르세요" })).toBeInTheDocument();
    expect(fetchEtfDetail).not.toHaveBeenCalled();
    expect(fetchEtfOfficial).not.toHaveBeenCalled();
  });
});

// POC6-32 V2 [비교 상세](PLAN §3-2 D1 ~ D4 · §9 I-6 · I-19 · I-20 · I-21) — 같은 종목 · 상품 확인 표 · 지수 상태 · 차이 줄 조건.
describe("V2 [비교 상세] 상품 확인 · 지수 상태", () => {
  const T0 = () => summaryOk().top[0].ticker;
  const ROWS5 = ["m1", "m3", "w5", "w20", "drawdown"];

  it("같은 종목을 두 칸에 고르면 '같은 종목입니다' · 상품 확인 · 차이 줄 · 공식 기준정보 조회 없음", async () => {
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    // B00001 = 보유이면서 하위 1위 후보(고정 자료 held)
    await pick("B00001", "bottom:B00001");
    expect(await screen.findByTestId("hcc-same")).toHaveTextContent("같은 종목입니다");
    expect(tid("hcc-diff-pending")).toBe("같은 종목입니다 — 비교하지 않습니다");
    for (const k of ROWS5) expect(screen.queryByTestId(`hcc-diff-${k}`)).toBeNull();
    expect(screen.queryByTestId("hcc-product")).toBeNull();
    expect(fetchEtfOfficial).not.toHaveBeenCalled();
    // 다른 후보로 바꾸면 비교로 돌아온다.
    fireEvent.change(sel("hcc-candidate"), { target: { value: `top:${T0()}` } });
    await waitFor(() => expect(screen.getByTestId("hcc-diff-m1")).toBeInTheDocument());
    expect(screen.queryByTestId("hcc-same")).toBeNull();
    expect(fetchEtfOfficial).toHaveBeenLastCalledWith(["B00001", T0()]);
  });

  it("상품 확인 표 = 칸마다 공식 기초지수 · 지수산출기관 · 투자 대상 · 상품 구조(총보수 %) · 과세유형 · 공식 기준정보 파일 + 지수 상태 한 줄", async () => {
    fetchEtfOfficial.mockImplementation((ts: string[]) =>
      Promise.resolve(
        officialResp(ts, "same", {
          items: { [ts[0]]: offItem(ts[0]), [ts[1]]: offItem(ts[1], { market: "해외", fee_pct: "0.450000", replication: "실물(액티브)" }) },
        }),
      ),
    );
    await renderLoaded();
    await waitFor(() => expect(screen.getByTestId("hcc-product-table")).toBeInTheDocument());
    expect(tid("hcc-p-head-holding")).toBe("보유 · 반도체 전공정");
    expect(tid("hcc-p-head-candidate")).toBe(`후보 · ${summaryOk().top[0].name}`);
    expect(tid("hcc-p-index-holding")).toBe("시험 지수 A");
    expect(tid("hcc-p-provider-holding")).toBe("시험 산출기관");
    expect(tid("hcc-p-target-holding")).toBe("국내 · 주식");
    expect(tid("hcc-p-target-candidate")).toBe("해외 · 주식");
    expect(tid("hcc-p-structure-holding")).toBe("일반 · 실물(패시브) · 총보수 0.15%");
    expect(tid("hcc-p-structure-candidate")).toBe("일반 · 실물(액티브) · 총보수 0.45%");
    expect(tid("hcc-p-tax-candidate")).toBe("배당소득세(보유기간과세)");
    expect(tid("hcc-p-file-holding")).toBe("KRX 2026-09-27 파일");
    expect(tid("hcc-index-chip")).toBe("같은 공식 기초지수");
    expect(tid("hcc-index-reason")).toBe(
      "두 상품 모두 공식 기초지수 '시험 지수 A' — 기간 · 가격 상태가 맞는 줄만 아래 기본 비교에 차이(해당 기간 가격 성과)를 적습니다",
    );
    expect(screen.getByRole("heading", { level: 2, name: "기본 비교 — 해당 기간 가격 성과" })).toBeInTheDocument();
    // 구조가 다르다는 서버 칸이 없으면 '구조 다름' 줄도 없다.
    expect(screen.queryByTestId("hcc-structure")).toBeNull();
  });

  it("보유 칸의 개별 주식(I-19) = '개별 주식 · 기초지수 해당 없음' · 기준 미확인 · 다섯 줄 모두 차이 요약 안 함 · 값 칸은 그대로", async () => {
    fetchEtfOfficial.mockImplementation((ts: string[]) =>
      Promise.resolve(
        officialResp(ts, "unconfirmed", {
          items: {
            [ts[0]]: offItem(ts[0], {
              found: false,
              kind: "stock",
              name: null,
              index_name: null,
              index_provider: null,
              market: null,
              asset: null,
              multiple: null,
              replication: null,
              fee_pct: null,
              tax: null,
              listed: null,
              missing_reason: "개별 주식 · 기초지수 해당 없음",
            }),
            [ts[1]]: offItem(ts[1]),
          },
          pair: { ...PAIR.unconfirmed, reason: "개별 주식 · 기초지수 해당 없음" },
        }),
      ),
    );
    detailWith({}, { m1: period(14.55) });
    await renderLoaded();
    await waitFor(() => expect(tid("hcc-index-chip")).toBe("기준 미확인"));
    expect(tid("hcc-p-index-holding")).toBe("개별 주식 · 기초지수 해당 없음");
    for (const k of ["provider", "target", "structure", "tax"]) expect(tid(`hcc-p-${k}-holding`)).toBe("—");
    expect(tid("hcc-p-file-holding")).toBe("해당 없음");
    expect(tid("hcc-index-reason")).toBe("개별 주식 · 기초지수 해당 없음 — 수익률 차이 요약을 쓰지 않고 각 ETF 값만 보입니다");
    expect(tid("hcc-diff-m1")).toBe("1개월: 차이 요약 안 함 — 기준 미확인");
    for (const k of ROWS5) {
      expect(screen.getByTestId(`hcc-diff-${k}`)).toHaveAttribute("data-kind", "not_compared");
      expect(tid(`hcc-diff-${k}`)).not.toMatch(/높음|작음|큼|같음|%p/);
    }
    expect(tid("hcc-holding-m1")).toContain("-10.25%");
    expect(tid("hcc-candidate-m1")).toContain("+14.55%");
  });

  it("공식 기준정보에 없는 후보(I-21) = '공식 기준정보에 없음 — 확인 불가' · 파일 날짜에 없음", async () => {
    fetchEtfOfficial.mockImplementation((ts: string[]) =>
      Promise.resolve(
        officialResp(ts, "unconfirmed", {
          items: {
            [ts[0]]: offItem(ts[0]),
            [ts[1]]: offItem(ts[1], {
              found: false,
              index_name: null,
              index_provider: null,
              market: null,
              asset: null,
              multiple: null,
              replication: null,
              fee_pct: null,
              tax: null,
              missing_reason: "공식 기준정보에 없음",
            }),
          },
        }),
      ),
    );
    await renderLoaded();
    await waitFor(() => expect(tid("hcc-p-index-candidate")).toBe("공식 기준정보에 없음 — 확인 불가"));
    expect(tid("hcc-p-file-candidate")).toBe("KRX 2026-09-27 파일에 없음");
    expect(tid("hcc-index-chip")).toBe("기준 미확인");
  });

  it("공식 기준정보 조회 실패 = 기준 미확인(차이 요약 안 함) · [다시 불러오기]로 다시 읽으면 같은 지수 차이", async () => {
    fetchEtfOfficial.mockRejectedValue(new Error("down"));
    detailWith({}, { m1: period(14.55) });
    await renderLoaded();
    expect(await screen.findByTestId("hcc-product-error")).toHaveTextContent("공식 기준정보를 읽지 못했습니다");
    expect(tid("hcc-index-chip")).toBe("기준 미확인");
    expect(tid("hcc-index-reason")).toContain("공식 기준정보를 읽지 못함");
    expect(tid("hcc-diff-m1")).toBe("1개월: 차이 요약 안 함 — 기준 미확인");
    fetchEtfOfficial.mockImplementation((ts: string[]) => Promise.resolve(officialResp(ts)));
    fireEvent.click(screen.getByRole("button", { name: "다시 불러오기" }));
    await waitFor(() => expect(tid("hcc-index-chip")).toBe("같은 공식 기초지수"));
    await waitFor(() => expect(tid("hcc-diff-m1")).toBe("1개월(10/12 → 11/9 · 같은 기간): 후보가 24.80%p 높음"));
    expect(screen.queryByTestId("hcc-product-error")).toBeNull();
  });

  it("공식 기준정보를 읽는 중이면 차이 줄을 만들지 않고 그 사실만(같은 지수인지 모르는 채로 차이를 적지 않음)", async () => {
    fetchEtfOfficial.mockImplementation(() => new Promise(() => {}));
    render(<HoldingCandidateCompareView onNavigate={nav} />);
    await pick();
    await waitFor(() => expect(tid("hcc-holding-m1")).toContain("-10.25%"));
    expect(fetchEtfOfficial).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("hcc-product")).toHaveTextContent("공식 기준정보 확인 중...");
    expect(tid("hcc-diff-pending")).toBe("공식 기준정보를 읽는 중이라 차이는 아직 적지 않습니다");
    for (const k of ROWS5) expect(screen.queryByTestId(`hcc-diff-${k}`)).toBeNull();
    expect(screen.queryByTestId("hcc-index-state")).toBeNull();
  });

  it("같은 공식 기초지수 · 구조 다름 = 차이를 적고 '구조 다름: …'(확인된 값 · 보유 ↔ 후보)", async () => {
    fetchEtfOfficial.mockImplementation((ts: string[]) =>
      Promise.resolve(
        officialResp(ts, "same", {
          pair: {
            ...PAIR.same,
            reason: "두 상품 모두 공식 기초지수 '시험 지수 A' · 상품 구조 다름",
            structure_diffs: [
              { field: "추적배수", a: "일반", b: "2X 레버리지" },
              { field: "총보수", a: "0.150000", b: "0.450000" },
            ],
          },
        }),
      ),
    );
    detailWith({}, { m1: period(14.55) });
    await renderLoaded();
    await waitFor(() => expect(screen.getByTestId("hcc-structure")).toBeInTheDocument());
    expect(tid("hcc-structure")).toBe("구조 다름: 추적배수 일반 ↔ 2X 레버리지 · 총보수 0.15% ↔ 0.45%(보유 ↔ 후보)");
    expect(tid("hcc-diff-m1")).toBe("1개월(10/12 → 11/9 · 같은 기간): 후보가 24.80%p 높음");
    expect(screen.getByTestId("hcc-diff-m1")).toHaveAttribute("data-kind", "compared");
    // 구조 다름 줄은 기본 비교 안 · 차이 줄보다 앞.
    expect(
      screen.getByTestId("hcc-structure").compareDocumentPosition(screen.getByTestId("hcc-row-m1")) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("같은 공식 기초지수 · 한쪽 총보수만 빔 = 차이를 적고 '확인 안 된 구조 항목'(구조 다름 아님 · r1 F2)", async () => {
    fetchEtfOfficial.mockImplementation((ts: string[]) =>
      Promise.resolve(
        officialResp(ts, "same", {
          pair: {
            ...PAIR.same,
            reason: "두 상품 모두 공식 기초지수 '시험 지수 A' · 상품 구조 일부 확인 안 됨",
            structure_diffs: [],
            structure_unconfirmed: [{ field: "총보수", side: "a" }],
          },
        }),
      ),
    );
    detailWith({}, { m1: period(14.55) });
    await renderLoaded();
    await waitFor(() => expect(screen.getByTestId("hcc-structure")).toBeInTheDocument());
    expect(tid("hcc-structure")).toBe("확인 안 된 구조 항목: 총보수(보유 쪽)");
    expect(tid("hcc-structure")).not.toContain("구조 다름");
    expect(tid("hcc-diff-m1")).toBe("1개월(10/12 → 11/9 · 같은 기간): 후보가 24.80%p 높음");
    expect(screen.getByTestId("hcc-diff-m1")).toHaveAttribute("data-kind", "compared");
  });

  // 조합 표 — 서버 지수 상태 넷 × 상세 수치 경우 넷(기간 · 가격 상태가 맞음 · 기간 다름 · 가격 상태 다름 · 값 없음).
  // 같은 공식 기초지수일 때만 기존 규칙 글 · 그 밖은 지수 사유를 먼저(기존 사유는 뒤) · 차이(%p) 없음.
  const GATE_WORD: Record<Exclude<OfficialPairState, "same">, string> = {
    different: "지수 다름",
    same_family: "지수 다름(같은 계열)",
    unconfirmed: "기준 미확인",
  };
  const DETAIL: [string, Partial<EtfDetailItem>, Partial<EtfDetailItem>, string, string, string][] = [
    ["기간 · 가격 상태 맞음", {}, { m1: period(14.55) }, "compared", "1개월(10/12 → 11/9 · 같은 기간): 후보가 24.80%p 높음", ""],
    [
      "기간 다름",
      {},
      { m1: period(3, "2026-10-13") },
      "not_compared",
      "1개월: 기간이 달라 비교하지 않음(보유 10/12 → 11/9 · 후보 10/13 → 11/9)",
      " · 기간 다름(보유 10/12 → 11/9 · 후보 10/13 → 11/9)",
    ],
    [
      "가격 상태 다름",
      { end_price: INTRA },
      { end_price: AFTER },
      "not_compared",
      "1개월(10/12 → 11/9): 가격 상태가 달라 비교하지 않음(보유 장중 · 후보 마감 뒤)",
      " · 가격 상태 다름(보유 장중 · 후보 마감 뒤)",
    ],
    [
      "값 없음(보유)",
      { m1: period(null, null, "2026-11-09", "missing", "insufficient_history") },
      {},
      "not_compared",
      "1개월: 비교하지 않음 — 보유 값 없음 · 저장 이력 부족",
      " · 보유 값 없음 · 저장 이력 부족",
    ],
  ];
  const STATES: OfficialPairState[] = ["same", "same_family", "different", "unconfirmed"];
  const COMBOS = STATES.flatMap((st) => DETAIL.map((d) => [st, ...d] as const));

  it.each(COMBOS)("지수 상태 %s × %s", async (st, _name, hold, cand, sameKind, sameText, extra) => {
    fetchEtfOfficial.mockImplementation((ts: string[]) => Promise.resolve(officialResp(ts, st)));
    detailWith(hold, cand);
    await renderLoaded();
    await waitFor(() => expect(tid("hcc-index-chip")).toBe(PAIR[st].label));
    if (st === "same") {
      expect(tid("hcc-diff-m1")).toBe(sameText);
      expect(screen.getByTestId("hcc-diff-m1")).toHaveAttribute("data-kind", sameKind);
    } else {
      expect(tid("hcc-diff-m1")).toBe(`1개월: 차이 요약 안 함 — ${GATE_WORD[st]}${extra}`);
      expect(screen.getByTestId("hcc-diff-m1")).toHaveAttribute("data-kind", "not_compared");
      expect(tid("hcc-index-reason")).toContain("수익률 차이 요약을 쓰지 않고 각 ETF 값만 보입니다");
      for (const k of ROWS5) expect(tid(`hcc-diff-${k}`)).not.toMatch(/높음|작음|큼|같음|%p/);
    }
    // 값 칸(각 ETF 값 · 실제 기간)은 지수 상태와 상관없이 그대로(비어 있지 않음).
    for (const r of ["holding", "candidate"]) expect(tid(`hcc-${r}-m1`)).not.toBe("—");
  });

  it("지수 다름이어도 값 칸은 각 ETF 값 · 실제 기간 · 같은 기간 KODEX 200 대비 그대로", async () => {
    fetchEtfOfficial.mockImplementation((ts: string[]) => Promise.resolve(officialResp(ts, "different")));
    detailWith({}, { m1: period(14.55) });
    await renderLoaded();
    await waitFor(() => expect(tid("hcc-index-chip")).toBe("다른 지수"));
    expect(tid("hcc-holding-m1")).toBe("10/12 → 11/9-10.25%KODEX 200 대비 +12.39%p (KODEX 200 -22.64% · 같은 기간)");
    expect(tid("hcc-candidate-m1")).toContain("+14.55%");
    expect(tid("hcc-diff-m1")).toBe("1개월: 차이 요약 안 함 — 지수 다름");
  });

  it("응답에 지수 상태가 없거나 알 수 없는 상태 글이면 기준 미확인(영어 상태 글을 보이지 않음)", async () => {
    fetchEtfOfficial.mockImplementation((ts: string[]) =>
      Promise.resolve({ ...officialResp(ts), pair: { ...PAIR.same, state: "mystery" as unknown as OfficialPairState, label: "mystery" } }),
    );
    await renderLoaded();
    await waitFor(() => expect(tid("hcc-index-chip")).toBe("기준 미확인"));
    expect(tid("hcc-index-reason")).toContain("공식 기준정보 응답에 두 상품의 지수 상태가 없음");
    expect(tid("hcc-product")).not.toContain("mystery");
    expect(tid("hcc-diff-m1")).toBe("1개월: 차이 요약 안 함 — 기준 미확인");
  });
});
