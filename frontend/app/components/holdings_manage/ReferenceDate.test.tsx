// POC5-07 — 가격 비교 기준일 화면 test(설계 §2 · §4 · §9-2-2). 보유 · 시장 흐름 자료 = 기존 History
// fixture(실제 백엔드 출력) + 기준일만 넣은 복사 · 시장 흐름 = referenceFixtures(실제 백엔드 출력).
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
import { referenceTargets } from "./ReferenceDateDialog";
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

describe("가격 비교 기준일 일괄 설정 창", () => {
  it("대상 = 보유 중 · 기준잔고 / 잔고 등록 · 기준일 없음 — 설정 한 번에 전부 보낸다", async () => {
    fetchTradeHistory.mockResolvedValue(HISTORY_V1);
    // 부모 보유 revision(7)이 아니라 대상 목록과 같은 조회의 revision(0)을 보낸다(§9-1)
    const onChanged = renderBook(vi.fn(), 7);
    fireEvent.click(screen.getByRole("button", { name: "가격 비교 기준일 설정" }));
    const dialog = await screen.findByRole("dialog", { name: "가격 비교 기준일 설정" });
    expect(within(dialog).getByLabelText("가격 비교 기준일")).toHaveValue("2026-01-02");
    expect(within(dialog).getByText("1건")).toBeInTheDocument();
    expect(within(dialog).getByText(V1_POS.name!)).toBeInTheDocument();
    expect(within(dialog).getByText("미상")).toBeInTheDocument(); // 실제 매수일은 미상 그대로
    fireEvent.click(within(dialog).getByRole("button", { name: "설정" }));
    await waitFor(() => expect(putReferenceDate).toHaveBeenCalledTimes(1));
    const cmd = putReferenceDate.mock.calls[0][0];
    expect(cmd).toMatchObject({
      action: "reference_date",
      base_revision: 0,
      reference_date: "2026-01-02",
      targets: [{ position_id: V1_POS.position_id, cycle_id: V1_CYCLE.cycle_id }],
    });
    expect(cmd.request_id).toMatch(/^[0-9a-f-]{36}$/);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(onChanged).toHaveBeenCalled();
  });

  it("이미 기준일이 있거나 실제 매수로 시작했거나 끝난 기간은 대상이 아니다", () => {
    const mixed = [
      ...HISTORY.positions, // KODEX = 매수로 시작 · 나머지 = 끝난 잔고 등록 기간
      ...withReference(HISTORY_V1, "2026-02-02").positions,
    ];
    expect(referenceTargets(mixed)).toEqual([]);
    expect(referenceTargets(HISTORY_V1.positions)).toHaveLength(1);
  });

  it("대상이 없으면 안내만 · 설정 버튼은 누를 수 없다", async () => {
    fetchTradeHistory.mockResolvedValue(withReference(HISTORY_V1, "2026-01-02"));
    renderBook();
    await waitFor(() => expect(fetchTradeHistory).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "가격 비교 기준일 설정" }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText(/설정할 보유가 없습니다/);
    expect(within(dialog).getByRole("button", { name: "설정" })).toBeDisabled();
  });

  it("충돌(409)은 문구로 보이고 창은 남는다 · 같은 내용 재시도는 같은 저장 ID", async () => {
    fetchTradeHistory.mockResolvedValue(HISTORY_V1);
    putReferenceDate.mockRejectedValueOnce(
      new ApiRequestError("HTTP 409", 409, { detail: "다른 화면에서 보유가 바뀌었습니다 — 새로고침한 뒤 다시 설정하세요." }),
    );
    renderBook();
    fireEvent.click(screen.getByRole("button", { name: "가격 비교 기준일 설정" }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText("1건");
    fireEvent.click(within(dialog).getByRole("button", { name: "설정" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("새로고침");
    fireEvent.click(within(dialog).getByRole("button", { name: "설정" }));
    await waitFor(() => expect(putReferenceDate).toHaveBeenCalledTimes(2));
    expect(putReferenceDate.mock.calls[1][0].request_id).toBe(putReferenceDate.mock.calls[0][0].request_id);
  });
});

describe("History 기간의 가격 비교 기준일", () => {
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
    expect(screen.getByText(/가격 비교 기준일:/)).toHaveTextContent("가격 비교 기준일: 없음");
    expect(screen.queryByRole("button", { name: "시장 흐름 보기" })).toBeNull(); // 매매 · 기준일 없음
    fireEvent.click(screen.getByRole("button", { name: "수정/해제" }));
    expect(screen.getAllByRole("dialog")).toHaveLength(1); // 창 위에 창 없음
    expect(screen.getByLabelText("가격 비교 기준일")).toHaveValue("2026-01-02");
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
    expect(await screen.findByText(/가격 비교 기준일:/)).toHaveTextContent("가격 비교 기준일: 2026-01-02");
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
    const input = screen.getByLabelText("가격 비교 기준일");
    fireEvent.change(input, { target: { value: "2999-01-01" } });
    expect(screen.getByRole("button", { name: "저장" })).toBeDisabled();
    fireEvent.change(input, { target: { value: "2026-01-05" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(putReferenceDate).toHaveBeenCalledTimes(2));
    expect(putReferenceDate.mock.calls[1][0].request_id).toBe(putReferenceDate.mock.calls[0][0].request_id);
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

describe("시장 흐름 — 가격 비교 기준일 이후 종가 변화", () => {
  it("기준일 → 마지막 저장일 항목을 맨 위에 · 휴장 기준일은 다음 거래일 · 매수 · 손익 문구 없음", async () => {
    fetchMarketFlow.mockResolvedValue(FLOW_REF_OPEN);
    render(<MarketFlowPanel positionId="p" cycleId="cyc-ref" />);
    const line = await screen.findByText("가격 비교 기준일 이후 종가 변화");
    const li = line.closest("li")!;
    expect(li).toHaveTextContent("설정한 기준일 2026-01-01");
    expect(li).toHaveTextContent(`마지막 저장일 ${FLOW_REF_OPEN.reference_flow!.latest_stored_date} 종가`);
    expect(li).toHaveTextContent("같은 날짜 KOSPI");
    expect(screen.getByText(/그날 보유 · 매수했다는 뜻이 아니며/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/매수 후 수익률|매수 후 손익/);
  });

  it("끝난 기간 = 가격 비교 기준일 → 마지막 매도일", async () => {
    fetchMarketFlow.mockResolvedValue(FLOW_REF_SOLD);
    render(<MarketFlowPanel positionId="p" cycleId="cyc-ref" />);
    const period = (await screen.findByText(/가격 비교 기준일 2026-01-02 → 마지막 매도일/)).closest("li")!;
    expect(period).toHaveTextContent("가격 비교 기준일 2026-01-02 → 마지막 매도일 2026-03-02 종가 변화");
    expect(period.textContent).not.toMatch(/보유 기간/); // 기준일 구간은 보유 기간이 아니다(§1)
    expect(screen.getByText(/실제 매수일: 미상/)).toBeInTheDocument(); // 매수일 미상 표시 유지(§9-1)
    expect(screen.getByText(/매도 뒤/)).toBeInTheDocument(); // 매도 뒤 변화는 기존 항목 그대로
  });
});
