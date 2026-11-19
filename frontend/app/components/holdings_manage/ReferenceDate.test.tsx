// POC5-07 — 가격 비교 기준일 화면 test(설계 §2 · §4 · §9-2-2). 보유 · 시장 흐름 자료 = 기존 History
// fixture(실제 백엔드 출력) + 기준일만 넣은 복사 · 시장 흐름 = referenceFixtures(실제 백엔드 출력).
// POC6-33(판정 Q17 · Q18 · Q20 · Q46 · PLAN I-1 · I-2): 상단 일괄 버튼 · 일괄 창 시험 3개와 대상 고르기 단위
// 시험은 창이 _orphaned/ 로 보관돼 '상단에 일괄 버튼 없음' 하나로 바뀜(다건 저장 계약 = 백엔드
// tests/test_poc5_07_reference_date.py) · History 줄 낱말 = '비교 시작일' · 기준일 없는 새 잔고 등록 기간도
// History 에서 하나씩 설정(가상 자료 '보유 A' · 'TEST01').
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";

const putReferenceDate = vi.fn();
const fetchTradeHistory = vi.fn();
const fetchEnrichedHoldings = vi.fn();
const fetchMarketFlow = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    putReferenceDate: (...a: unknown[]) => putReferenceDate(...a),
    fetchTradeHistory: (...a: unknown[]) => fetchTradeHistory(...a),
    fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
    fetchMarketFlow: (...a: unknown[]) => fetchMarketFlow(...a),
  };
});

import { ApiRequestError, type HoldingItem, type TradeHistoryResponse } from "@/lib/api";
import HoldingsBookSection from "./HoldingsBookSection";
import HistoryDialog from "./HistoryDialog";
import MarketFlowPanel from "./MarketFlowPanel";
import { HISTORY, HISTORY_V1 } from "./historyFixtures";
import { FLOW_REF_OPEN, FLOW_REF_SOLD } from "./referenceFixtures";

const V1_POS = HISTORY_V1.positions[0];
const V1_CYCLE = V1_POS.cycles[0];

function withReference(h: TradeHistoryResponse, day: string | null): TradeHistoryResponse {
  return {
    ...h,
    positions: h.positions.map((p) => ({
      ...p,
      cycles: p.cycles.map((c) => (c.opened_by === "BUY" ? c : { ...c, reference_date: day })),
    })),
  };
}

const HOLDINGS: HoldingItem[] = [
  {
    ticker: V1_POS.ticker,
    name: V1_POS.name,
    account_group: V1_POS.account_group,
    quantity: 3,
    avg_buy_price: 100,
    position_id: V1_POS.position_id,
    cycle_id: V1_CYCLE.cycle_id,
  },
];

beforeEach(() => {
  for (const f of [putReferenceDate, fetchTradeHistory, fetchEnrichedHoldings, fetchMarketFlow]) {
    f.mockReset();
  }
  fetchEnrichedHoldings.mockResolvedValue({ items: [] });
  putReferenceDate.mockResolvedValue({ status: "V2", revision: 1, changed: [V1_CYCLE.cycle_id], unchanged: [] });
});

function renderBook(onChanged = vi.fn(), revision = 0) {
  render(
    <HoldingsBookSection
      holdings={HOLDINGS}
      revision={revision}
      status="OK"
      busy={false}
      reloadKey={0}
      onEdit={vi.fn()}
      onChanged={onChanged}
    />,
  );
  return onChanged;
}

// 기준일 없는 새 잔고 등록(보유 중) 기간 — 이름 · 코드 · 수량 · 금액은 가상 값(공개 저장소 · 실제 보유 아님).
// 모양 = 실제 백엔드 History 응답(historyFixtures 의 잔고 등록 기록)과 같은 칸.
const REG_POS = "pos-test-a";
const REG_CYCLE = "cyc-test-a";
function registerHistory(day: string | null, revision: number): TradeHistoryResponse {
  return {
    status: "V2",
    revision,
    positions: [
      {
        position_id: REG_POS,
        ticker: "TEST01",
        name: "보유 A",
        account_group: "일반",
        is_open: true,
        cycles: [
          {
            cycle_id: REG_CYCLE,
            status: "OPEN",
            opened_by: "REGISTER",
            closed_by: null,
            start_date: null,
            end_date: null,
            reference_date: day,
            has_adjustment: false,
            quantity: "10",
            cost: "100000",
            avg_buy_price: "10000",
            realized_pnl: "0",
            sold_cost: "0",
            realized_rate: null,
            events: [
              {
                record_id: "rec-test-a",
                kind: "REGISTER",
                recorded_at: "2026-11-17T10:00:00+09:00",
                supersedes_id: null,
                payload: { quantity: "10", avg_buy_price: "10000" },
                date: null,
                cost_of_sold: null,
                realized_pnl: null,
                realized_rate: null,
                q_after: "10",
                c_after: "100000",
                avg_after: "10000",
                previous: [],
              },
            ],
            voided: [],
          },
        ],
      },
    ],
  };
}

describe("종목 관리 상단 — 일괄 기준일 버튼 없음(POC6-33 Q46)", () => {
  it("상단 버튼 = [새 보유 추가] · [입력 정정] 둘뿐 · 기준일이 없는 보유가 있어도 일괄 버튼 · 저장 없음", async () => {
    // 일괄 대상이 1건 있는 자료(기준잔고 · 기준일 없음)로도 일괄 버튼이 나오지 않아야 한다.
    fetchTradeHistory.mockResolvedValue(HISTORY_V1);
    renderBook();
    await waitFor(() => expect(fetchTradeHistory).toHaveBeenCalled());
    const head = screen.getByRole("heading", { name: "1. 보유 종목" }).parentElement!;
    expect(within(head).getAllByRole("button").map((b) => b.textContent)).toEqual(["새 보유 추가", "입력 정정"]);
    expect(screen.queryByRole("button", { name: /기준일/ })).toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(putReferenceDate).not.toHaveBeenCalled();
  });
});

describe("종목 관리 표 아래 — 보유 행 수(POC6-33 H-1 · 설계자 RESULT 판정 §2-3)", () => {
  it("같은 종목이 두 계좌에 있으면 '보유 행 2개'(서로 다른 종목 수 '1종목' · '2종목'이 아님)", async () => {
    // 가상 자료(공개 저장소 · 실제 보유 아님) — 같은 코드 'TEST01' 을 일반 · ISA 두 계좌에 둔다.
    const twoAccounts: HoldingItem[] = [
      { ticker: "TEST01", name: "보유 A", account_group: "일반", quantity: 1, avg_buy_price: 100, position_id: "pos-a1", cycle_id: "cyc-a1" },
      { ticker: "TEST01", name: "보유 A", account_group: "ISA", quantity: 2, avg_buy_price: 100, position_id: "pos-a2", cycle_id: "cyc-a2" },
    ];
    fetchTradeHistory.mockResolvedValue({ status: "V2", revision: 0, positions: [] });
    render(
      <HoldingsBookSection
        holdings={twoAccounts}
        revision={0}
        status="OK"
        busy={false}
        reloadKey={0}
        onEdit={vi.fn()}
        onChanged={vi.fn()}
      />,
    );
    await waitFor(() => expect(fetchTradeHistory).toHaveBeenCalled());
    expect(screen.getAllByRole("row")).toHaveLength(3); // 머리 1 + 계좌별 보유 행 2
    const note = screen.getByText(/수익률은 「보유 현황」과 같은 현재가 기준 값/);
    expect(note).toHaveTextContent(/^보유 행 2개 · 수익률은 「보유 현황」과 같은 현재가 기준 값\(현재가 없으면 —\)$/);
    expect(note.textContent).not.toMatch(/\d+종목/);
  });
});

describe("History 기간의 비교 시작일(값 = 가격 비교 기준일)", () => {
  function renderHistory(onChanged = vi.fn()) {
    render(
      <HistoryDialog
        positionId={V1_POS.position_id}
        onClose={vi.fn()}
        onRebuy={vi.fn()}
        onCorrect={vi.fn()}
        onChanged={onChanged}
      />,
    );
    return onChanged;
  }

  it("실제 매수일 미상 · 기준일 없음을 함께 · 같은 줄 안에서 설정 → 다시 읽기", async () => {
    fetchTradeHistory.mockResolvedValue(HISTORY_V1);
    const onChanged = renderHistory();
    expect(await screen.findByText("실제 매수일: 미상")).toBeInTheDocument();
    expect(screen.getByText(/비교 시작일:/)).toHaveTextContent("비교 시작일: 없음");
    expect(screen.queryByText(/가격 비교 기준일:/)).toBeNull(); // 옛 낱말 없음(POC6-33 Q18)
    expect(screen.queryByRole("button", { name: "시장 흐름 보기" })).toBeNull(); // 매매 · 기준일 없음
    fireEvent.click(screen.getByRole("button", { name: "수정/해제" }));
    expect(screen.getAllByRole("dialog")).toHaveLength(1); // 창 위에 창 없음
    expect(screen.getByLabelText("비교 시작일")).toHaveValue("2026-01-02");
    expect(screen.queryByRole("button", { name: "해제" })).toBeNull(); // 없는 값은 해제 없음
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(putReferenceDate).toHaveBeenCalledTimes(1));
    expect(putReferenceDate.mock.calls[0][0]).toMatchObject({
      reference_date: "2026-01-02",
      base_revision: 0,
      targets: [{ position_id: V1_POS.position_id, cycle_id: V1_CYCLE.cycle_id }],
    });
    await waitFor(() => expect(fetchTradeHistory).toHaveBeenCalledTimes(2));
    expect(onChanged).toHaveBeenCalled();
  });

  it("기준일이 있으면 매매가 없어도 시장 흐름을 볼 수 있고 · 해제는 null 로 보낸다", async () => {
    fetchTradeHistory.mockResolvedValue(withReference(HISTORY_V1, "2026-01-02"));
    renderHistory();
    expect(await screen.findByText(/비교 시작일:/)).toHaveTextContent("비교 시작일: 2026-01-02");
    expect(screen.getByText("실제 매수일: 미상")).toBeInTheDocument(); // 기준일이 있어도 매수일은 미상
    expect(screen.getByRole("button", { name: "시장 흐름 보기" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "수정/해제" }));
    fireEvent.click(screen.getByRole("button", { name: "해제" }));
    await waitFor(() => expect(putReferenceDate).toHaveBeenCalledTimes(1));
    expect(putReferenceDate.mock.calls[0][0].reference_date).toBeNull();
  });

  it("오늘 이후 날짜는 저장할 수 없고 · 같은 내용 재시도는 같은 저장 ID", async () => {
    fetchTradeHistory.mockResolvedValue(HISTORY_V1);
    putReferenceDate.mockRejectedValueOnce(new ApiRequestError("HTTP 0", 0, null));
    renderHistory();
    fireEvent.click(await screen.findByRole("button", { name: "수정/해제" }));
    const input = screen.getByLabelText("비교 시작일");
    fireEvent.change(input, { target: { value: "2999-01-01" } });
    expect(screen.getByRole("button", { name: "저장" })).toBeDisabled();
    fireEvent.change(input, { target: { value: "2026-01-05" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(putReferenceDate).toHaveBeenCalledTimes(2));
    expect(putReferenceDate.mock.calls[1][0].request_id).toBe(putReferenceDate.mock.calls[0][0].request_id);
  });

  it("기준일 없는 새 잔고 등록 기간도 History 에서 하나씩 설정 · 저장한 값을 다시 읽어 보인다(POC6-33 Q20)", async () => {
    fetchTradeHistory
      .mockResolvedValueOnce(registerHistory(null, 3))
      .mockResolvedValueOnce(registerHistory("2026-01-05", 4));
    putReferenceDate.mockResolvedValueOnce({ status: "V2", revision: 4, changed: [REG_CYCLE], unchanged: [] });
    const onChanged = vi.fn();
    render(
      <HistoryDialog
        positionId={REG_POS}
        onClose={vi.fn()}
        onRebuy={vi.fn()}
        onCorrect={vi.fn()}
        onChanged={onChanged}
      />,
    );
    expect(await screen.findByText(/비교 시작일:/)).toHaveTextContent("비교 시작일: 없음");
    expect(screen.getByText("잔고 등록 · 매수일 미상")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "시장 흐름 보기" })).toBeNull(); // 매매 · 기준일 없음
    fireEvent.click(screen.getByRole("button", { name: "수정/해제" }));
    fireEvent.change(screen.getByLabelText("비교 시작일"), { target: { value: "2026-01-05" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(putReferenceDate).toHaveBeenCalledTimes(1));
    expect(putReferenceDate.mock.calls[0][0]).toMatchObject({
      action: "reference_date",
      base_revision: 3,
      reference_date: "2026-01-05",
      targets: [{ position_id: REG_POS, cycle_id: REG_CYCLE }], // 이 기간 1건만
    });
    // 저장 뒤 History 를 다시 읽어 저장된 값을 같은 줄에서 읽는다(편집 칸은 닫힘).
    await waitFor(() => expect(screen.getByText(/비교 시작일:/)).toHaveTextContent("비교 시작일: 2026-01-05"));
    expect(fetchTradeHistory).toHaveBeenCalledTimes(2);
    expect(onChanged).toHaveBeenCalled();
    expect(screen.queryByLabelText("비교 시작일")).toBeNull();
    expect(screen.getByRole("button", { name: "시장 흐름 보기" })).toBeInTheDocument(); // 기준일이 생겨 흐름 보기
  });

  it("실제 매수로 시작한 기간에는 기준일 줄이 없다", async () => {
    fetchTradeHistory.mockResolvedValue(HISTORY);
    render(
      <HistoryDialog
        positionId={HISTORY.positions[0].position_id}
        onClose={vi.fn()}
        onRebuy={vi.fn()}
        onCorrect={vi.fn()}
        onChanged={vi.fn()}
      />,
    );
    await screen.findAllByRole("button", { name: "시장 흐름 보기" });
    expect(screen.queryByText("실제 매수일: 미상")).toBeNull();
    expect(screen.queryByRole("button", { name: "수정/해제" })).toBeNull();
  });
});

// POC6-33 I-2 — 서버 원문('가격 비교 기준일 …')은 그대로 오고 화면은 History 와 같은 '비교 시작일'로 읽는다
// (사전 ↔ 서버 상수 대조 = MarketFlowPanel.test.tsx 공용 고정 자료 시험).
describe("시장 흐름 — 비교 시작일부터 종가 변화(서버 원문 = 가격 비교 기준일 이후 종가 변화)", () => {
  it("비교 시작일 → 마지막 저장일 항목을 맨 위에 · 휴장 시작일은 다음 거래일 · 매수 · 손익 문구 없음", async () => {
    fetchMarketFlow.mockResolvedValue(FLOW_REF_OPEN);
    render(<MarketFlowPanel positionId="p" cycleId="cyc-ref" />);
    const line = await screen.findByText("비교 시작일부터 종가 변화");
    const li = line.closest("li")!;
    expect(li).toHaveTextContent(
      `비교 시작일부터 종가 변화 · 2026-01-02(비거래일(연도 파일) → 다음 거래일(연도 파일) · 설정한 비교 시작일 2026-01-01) 종가 → 마지막 저장일 ${FLOW_REF_OPEN.reference_flow!.latest_stored_date} 종가: +20%`,
    );
    expect(li).toHaveTextContent("같은 날짜 KOSPI");
    expect(
      screen.getByText("비교 시작일은 종가 비교의 출발점이다 — 그날 보유 · 매수했다는 뜻이 아니며 개인 손익이 아니다."),
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/매수 후 수익률|매수 후 손익/);
    expect(document.body.textContent).not.toMatch(/가격 비교 기준일|설정한 기준일/); // 옛 낱말 없음
  });

  it("끝난 기간 = 비교 시작일 → 마지막 매도일", async () => {
    fetchMarketFlow.mockResolvedValue(FLOW_REF_SOLD);
    render(<MarketFlowPanel positionId="p" cycleId="cyc-ref" />);
    const period = (await screen.findByText(/비교 시작일 2026-01-02 → 마지막 매도일/)).closest("li")!;
    expect(period).toHaveTextContent(/^비교 시작일 2026-01-02 → 마지막 매도일 2026-03-02 종가 변화/);
    expect(document.body.textContent).not.toMatch(/가격 비교 기준일|설정한 기준일/); // 옛 낱말 없음
    expect(period.textContent).not.toMatch(/보유 기간/); // 기준일 구간은 보유 기간이 아니다(§1)
    expect(screen.getByText(/실제 매수일: 미상/)).toBeInTheDocument(); // 매수일 미상 표시 유지(§9-1)
    expect(screen.getByText(/매도 뒤/)).toBeInTheDocument(); // 매도 뒤 변화는 기존 항목 그대로
  });
});
