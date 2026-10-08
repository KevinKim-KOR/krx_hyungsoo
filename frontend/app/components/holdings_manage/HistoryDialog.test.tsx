// POC5-05 개정 2 — History 창 동작 test(설계 §2 · §3 · §6 · §8 · PLAN §2-8).
// 자료 = 실제 백엔드 출력(historyFixtures). API 는 vi.mock("@/lib/api") 로 바꿔 끼운다.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";

const fetchTradeHistory = vi.fn();
const fetchMarketFlow = vi.fn();
const putTradeCommand = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchTradeHistory: (...a: unknown[]) => fetchTradeHistory(...a),
    fetchMarketFlow: (...a: unknown[]) => fetchMarketFlow(...a),
    putTradeCommand: (...a: unknown[]) => putTradeCommand(...a),
  };
});

import { ApiRequestError, type PositionHistory } from "@/lib/api";
import HistoryDialog from "./HistoryDialog";
import { FLOW_ETF, HISTORY, HISTORY_V1 } from "./historyFixtures";

const KODEX = HISTORY.positions[0]; // 보유 중 · 지난 기간 1 + 현재 기간(취소 1건)
const TIGER = HISTORY.positions[1]; // 과거 보유 · 잔고 등록 → 입력 정정 → 입력 정정 종료
const HYNIX = HISTORY.positions[2]; // 과거 보유 · 잔고 등록 → 전량매도
const [KODEX_CLOSED, KODEX_OPEN] = KODEX.cycles;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

function only(pos: PositionHistory) {
  return { ...HISTORY, positions: [pos] };
}

beforeEach(() => {
  fetchTradeHistory.mockReset();
  fetchMarketFlow.mockReset();
  putTradeCommand.mockReset();
});

function renderDialog(positionId: string, priceInfo: Parameters<typeof HistoryDialog>[0]["priceInfo"] = null) {
  const props = {
    positionId,
    priceInfo,
    onClose: vi.fn(),
    onRebuy: vi.fn(),
    onCorrect: vi.fn(),
    onChanged: vi.fn(),
  };
  render(<HistoryDialog {...props} />);
  return props;
}

function rowOf(buttonName: string): HTMLElement {
  return screen.getByRole("button", { name: buttonName }).closest("tr") as HTMLElement;
}

function sumValue(scope: HTMLElement, key: string): HTMLElement {
  return within(scope).getByText(key, { selector: ".hmx-k" }).nextElementSibling as HTMLElement;
}

describe("열기 · 조회", () => {
  it("열 때 fetchTradeHistory(positionId) 1회만 · 시장 흐름 · 저장 호출 0", async () => {
    fetchTradeHistory.mockResolvedValue(only(KODEX));
    renderDialog(KODEX.position_id);
    expect(await screen.findByRole("heading", { name: "History — KODEX 200 · ISA" })).toBeInTheDocument();
    expect(screen.getByText("체결단가 기준 · 수수료 · 세금 · 배당 미반영 · 이동평균 평단")).toBeInTheDocument();
    expect(fetchTradeHistory).toHaveBeenCalledTimes(1);
    expect(fetchTradeHistory).toHaveBeenCalledWith(KODEX.position_id);
    expect(fetchMarketFlow).not.toHaveBeenCalled();
    expect(putTradeCommand).not.toHaveBeenCalled();
  });

  it("[시장 흐름 보기]를 누를 때만 그 기간으로 1회 · 접었다 다시 펼쳐도 다시 부르지 않는다", async () => {
    fetchTradeHistory.mockResolvedValue(only(KODEX));
    fetchMarketFlow.mockResolvedValue(FLOW_ETF);
    renderDialog(KODEX.position_id);
    const closed = await screen.findByRole("region", { name: "지난 보유 기간 · 2026-03-02 ~ 2026-05-20" });
    fireEvent.click(within(closed).getByRole("button", { name: "시장 흐름 보기" }));
    expect(fetchMarketFlow).toHaveBeenCalledTimes(1);
    expect(fetchMarketFlow).toHaveBeenCalledWith(KODEX.position_id, KODEX_CLOSED.cycle_id);
    expect(await within(closed).findByText(/보유 기간: 최초 매수일/)).toBeInTheDocument();
    fireEvent.click(within(closed).getByRole("button", { name: "시장 흐름 접기" }));
    fireEvent.click(within(closed).getByRole("button", { name: "시장 흐름 보기" }));
    expect(fetchMarketFlow).toHaveBeenCalledTimes(1);
    expect(fetchTradeHistory).toHaveBeenCalledTimes(1);
  });

  it("조회 실패 = 백엔드 문구 그대로", async () => {
    fetchTradeHistory.mockRejectedValue(
      new ApiRequestError("HTTP 500", 500, { detail: "보유 · 이력 파일을 읽을 수 없습니다: 손상" }),
    );
    renderDialog(KODEX.position_id);
    expect(await screen.findByRole("alert")).toHaveTextContent("보유 · 이력 파일을 읽을 수 없습니다: 손상");
    expect(screen.getByRole("heading", { name: "History" })).toBeInTheDocument();
  });

  it("응답에 그 보유가 없으면 새로고침 안내", async () => {
    fetchTradeHistory.mockResolvedValue({ ...HISTORY, positions: [] });
    renderDialog("없는-줄");
    expect(await screen.findByRole("alert")).toHaveTextContent("이 보유의 기록을 찾을 수 없습니다");
  });
});

describe("보유 중 · 과거 보유 내용", () => {
  it("보유 중: 현재 기간이 위 · 미실현(부모 값) · 누적 실현 · 재매수 없음", async () => {
    fetchTradeHistory.mockResolvedValue(only(KODEX));
    renderDialog(KODEX.position_id, { current_price: 10450, pnl_amount: 3150, pnl_rate_pct: 4.5 });
    const open = await screen.findByRole("region", { name: "보유 중 · 2026-09-24" });
    const regions = screen.getAllByRole("region");
    expect(regions[0]).toBe(open); // 최근 기간이 위
    expect(sumValue(open, "잔량 · 평단")).toHaveTextContent("7주 · 10,000원");
    expect(sumValue(open, "남은 원가")).toHaveTextContent("70,000원");
    const unreal = sumValue(open, "미실현 (현재가 10,450)");
    expect(unreal).toHaveTextContent("+3,150원 · +4.5%");
    expect(unreal).toHaveClass("pnl-pos");
    expect(sumValue(open, "누적 실현")).toHaveTextContent("+6,000원 · +20%");
    expect(screen.queryByRole("button", { name: "재매수" })).toBeNull();
    expect(screen.queryByText(/현재 보유 없음/)).toBeNull();
    // 구분: 기간의 첫 매수 = 최초 매수 · 잔량 0 이 된 매도 = 전량매도
    expect(within(rowOf("2026-03-02 09:31 최초 매수 정정")).getByText("첫 매수")).toBeInTheDocument();
    expect(rowOf("2026-04-15 추가매수 정정")).toBeInTheDocument();
    expect(rowOf("2026-05-20 전량매도 정정")).toBeInTheDocument();
    expect(rowOf("2026-09-24 10:42 최초 매수 정정")).toBeInTheDocument();
    expect(rowOf("2026-09-30 분할매도 정정")).toBeInTheDocument();
  });

  it("보유 중인데 가격 정보가 없으면 미실현 '—'", async () => {
    fetchTradeHistory.mockResolvedValue(only(KODEX));
    renderDialog(KODEX.position_id, null);
    const open = await screen.findByRole("region", { name: "보유 중 · 2026-09-24" });
    expect(sumValue(open, "미실현")).toHaveTextContent("—");
  });

  it("과거 보유: 제목 · '현재 보유 없음' · [재매수] → onRebuy(그 position) · 매수일 미상 기간 요약", async () => {
    fetchTradeHistory.mockResolvedValue(only(HYNIX));
    const props = renderDialog(HYNIX.position_id);
    expect(
      await screen.findByRole("heading", { name: "History — SK하이닉스 · 연금 (과거 보유)" }),
    ).toBeInTheDocument();
    expect(screen.getByText("현재 보유 없음 · 지난 보유 기간 1건")).toBeInTheDocument();
    const cycle = screen.getByRole("region", { name: "지난 보유 기간 · 매수일 미상 ~ 2026-09-30" });
    expect(within(cycle).getByText("잔고 등록 · 매수일 미상")).toBeInTheDocument();
    expect(within(cycle).getByText("150,000 (평단)")).toBeInTheDocument();
    expect(sumValue(cycle, "매도분 원가 합계")).toHaveTextContent("1,500,000원");
    expect(sumValue(cycle, "기간 실현손익")).toHaveTextContent("+186,000원");
    expect(sumValue(cycle, "기간 수익률")).toHaveTextContent("+12.4%");
    fireEvent.click(screen.getByRole("button", { name: "재매수" }));
    expect(props.onRebuy).toHaveBeenCalledTimes(1);
    expect(props.onRebuy).toHaveBeenCalledWith(HYNIX);
  });

  it("기록 시작 전 기준잔고: 기준잔고 표시 · 매매 없음 안내 · 시장 흐름 버튼 없음", async () => {
    fetchTradeHistory.mockResolvedValue(HISTORY_V1);
    const pos = HISTORY_V1.positions[0];
    renderDialog(pos.position_id);
    const cycle = await screen.findByRole("region", { name: "보유 중 · 매수일 미상" });
    expect(within(cycle).getByText("기준잔고 · 매수일 미상 · 입력 평단 기준")).toBeInTheDocument();
    expect(within(cycle).getByText("기록 시작 전")).toBeInTheDocument();
    expect(within(cycle).getByText("기준잔고")).toBeInTheDocument();
    expect(within(cycle).getByText("21,385 (평단)")).toBeInTheDocument();
    expect(within(cycle).getByText(/기록 시작 뒤 매매 없음/)).toBeInTheDocument();
    expect(within(cycle).queryByRole("button")).toBeNull(); // 정정 · 취소 · 시장 흐름 없음
    expect(screen.getByText("지난 보유 기간 없음.")).toBeInTheDocument();
  });
});

describe("매도 손익 · 정정 · 취소", () => {
  it("매도 줄: 매도분 원가 · 실현손익 · 수익률(서버 계산값 · 손익 색)", async () => {
    fetchTradeHistory.mockResolvedValue(only(KODEX));
    renderDialog(KODEX.position_id);
    await screen.findByRole("heading", { name: "History — KODEX 200 · ISA" });
    const part = rowOf("2026-05-06 분할매도 정정");
    expect(within(part).getByText("78,000")).toBeInTheDocument(); // 매매대금
    expect(within(part).getByText("64,000")).toBeInTheDocument(); // 매도분 원가
    expect(within(part).getByText("+14,000")).toHaveClass("pnl-pos");
    expect(within(part).getByText("+21.88%")).toHaveClass("pnl-pos");
    expect(within(part).getByText("9 · 10,666.67")).toBeInTheDocument();
    const all = rowOf("2026-05-20 전량매도 정정");
    expect(within(all).getByText("96,000")).toBeInTheDocument();
    expect(within(all).getByText("-6,000")).toHaveClass("pnl-neg");
    expect(within(all).getByText("-6.25%")).toHaveClass("pnl-neg");
    const closed = screen.getByRole("region", { name: "지난 보유 기간 · 2026-03-02 ~ 2026-05-20" });
    expect(sumValue(closed, "매도분 원가 합계")).toHaveTextContent("160,000원");
    expect(sumValue(closed, "기간 실현손익")).toHaveTextContent("+8,000원");
    expect(sumValue(closed, "기간 수익률")).toHaveTextContent("+5%");
  });

  it("[정정] → onCorrect(position, 그 기간, 그 기록) · 저장 호출 없음", async () => {
    fetchTradeHistory.mockResolvedValue(only(KODEX));
    const props = renderDialog(KODEX.position_id);
    await screen.findByRole("heading", { name: "History — KODEX 200 · ISA" });
    fireEvent.click(screen.getByRole("button", { name: "2026-05-06 분할매도 정정" }));
    expect(props.onCorrect).toHaveBeenCalledTimes(1);
    const [pos, cycle, ev] = props.onCorrect.mock.calls[0];
    expect(pos).toBe(KODEX);
    expect(cycle).toBe(KODEX_CLOSED);
    expect(ev).toBe(KODEX_CLOSED.events[2]);
    expect(putTradeCommand).not.toHaveBeenCalled();
  });

  it("[취소] → 화면 안 확인 → 취소 확정 = void 명령 → 다시 조회 + onChanged", async () => {
    fetchTradeHistory.mockResolvedValue(only(KODEX));
    putTradeCommand.mockResolvedValue({ record: {}, holdings: [], revision: 15 });
    const props = renderDialog(KODEX.position_id);
    await screen.findByRole("heading", { name: "History — KODEX 200 · ISA" });
    fireEvent.click(screen.getByRole("button", { name: "2026-09-30 분할매도 취소" }));
    expect(screen.getByText("이 기록을 취소할까요?")).toBeInTheDocument();
    expect(putTradeCommand).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "취소 확정" }));
    await waitFor(() => expect(fetchTradeHistory).toHaveBeenCalledTimes(2));
    expect(putTradeCommand).toHaveBeenCalledTimes(1);
    const cmd = putTradeCommand.mock.calls[0][0];
    expect(Object.keys(cmd).sort()).toEqual(["action", "base_revision", "record_id", "supersedes_id"]);
    expect(cmd).toMatchObject({
      action: "void",
      base_revision: HISTORY.revision,
      supersedes_id: KODEX_OPEN.events[1].record_id,
    });
    expect(cmd.record_id).toMatch(UUID);
    expect(props.onChanged).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.queryByText("이 기록을 취소할까요?")).toBeNull());
  });

  it("[그대로 두기] = 저장 없이 확인 닫기", async () => {
    fetchTradeHistory.mockResolvedValue(only(KODEX));
    const props = renderDialog(KODEX.position_id);
    await screen.findByRole("heading", { name: "History — KODEX 200 · ISA" });
    fireEvent.click(screen.getByRole("button", { name: "2026-04-15 추가매수 취소" }));
    fireEvent.click(screen.getByRole("button", { name: "그대로 두기" }));
    expect(screen.queryByText("이 기록을 취소할까요?")).toBeNull();
    expect(putTradeCommand).not.toHaveBeenCalled();
    expect(props.onChanged).not.toHaveBeenCalled();
  });

  it("취소 저장 실패 = 백엔드 문구 · 재시도는 같은 저장 ID", async () => {
    fetchTradeHistory.mockResolvedValue(only(KODEX));
    putTradeCommand.mockRejectedValue(
      new ApiRequestError("HTTP 409", 409, {
        detail: "다른 화면에서 보유가 바뀌었습니다 — 새로고침한 뒤 다시 입력하세요.",
      }),
    );
    const props = renderDialog(KODEX.position_id);
    await screen.findByRole("heading", { name: "History — KODEX 200 · ISA" });
    fireEvent.click(screen.getByRole("button", { name: "2026-09-30 분할매도 취소" }));
    fireEvent.click(screen.getByRole("button", { name: "취소 확정" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "다른 화면에서 보유가 바뀌었습니다 — 새로고침한 뒤 다시 입력하세요.",
    );
    expect(props.onChanged).not.toHaveBeenCalled();
    expect(fetchTradeHistory).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "취소 확정" }));
    await waitFor(() => expect(putTradeCommand).toHaveBeenCalledTimes(2));
    expect(putTradeCommand.mock.calls[1][0].record_id).toBe(putTradeCommand.mock.calls[0][0].record_id);
  });
});

describe("정정 전 입력 · 취소한 기록 · 입력 정정", () => {
  it("정정 전 입력 n건 · 취소한 기록 n건", async () => {
    fetchTradeHistory.mockResolvedValue(only(KODEX));
    renderDialog(KODEX.position_id);
    await screen.findByRole("heading", { name: "History — KODEX 200 · ISA" });
    expect(screen.getByText("정정 전 입력 1건")).toBeInTheDocument();
    expect(
      screen.getByText("이전 입력: 2026-05-06 매도 · 수량 7 · 체결단가 13,000 · 2026-10-08 16:10 저장"),
    ).toBeInTheDocument();
    expect(screen.getByText("취소한 기록 1건")).toBeInTheDocument();
    expect(
      screen.getByText("2026-09-25 매수 · 수량 2 · 체결단가 11,000 · 2026-10-08 16:10 취소"),
    ).toBeInTheDocument();
    // 취소된 매수는 표의 기록 줄이 아니다
    expect(screen.queryByRole("button", { name: /2026-09-25/ })).toBeNull();
  });

  it("입력 정정 포함 기간: 참고 계산 표시 · 정정 전 → 정정 후 · 입력 정정(종료) · 매매 동작 없음", async () => {
    fetchTradeHistory.mockResolvedValue(only(TIGER));
    renderDialog(TIGER.position_id);
    expect(
      await screen.findByRole("heading", { name: "History — TIGER 2차전지테마 · 일반 (과거 보유)" }),
    ).toBeInTheDocument();
    const cycle = screen.getByRole("region", { name: "지난 보유 기간 · 매수일 미상 ~ 2026-10-08" });
    expect(within(cycle).getByText("입력 정정 포함 · 참고 계산")).toHaveClass("hmx-tag-warn");
    expect(
      within(cycle).getByText(
        "정정 전 수량 · 평단 100 · 10,000 → 정정 후 80 · 10,000 · 종목명 정정: TIGER 2차전지 → TIGER 2차전지테마",
      ),
    ).toBeInTheDocument();
    expect(within(cycle).getByText("입력 정정(종료)")).toBeInTheDocument();
    expect(
      within(cycle).getByText("정정 전 수량 · 평단 80 · 10,000 → 정정 후 0 (입력 정정으로 종료)"),
    ).toBeInTheDocument();
    expect(sumValue(cycle, "종료")).toHaveTextContent("입력 정정으로 종료");
    expect(sumValue(cycle, "기간 수익률")).toHaveTextContent("—");
    expect(within(cycle).queryByRole("button")).toBeNull(); // 입력 정정 · 잔고 등록 줄에는 정정 · 취소 없음
  });

  it("종목명만 고친 입력 정정 = '종목명 정정: A → B' 만", async () => {
    const cy = TIGER.cycles[0];
    const nameOnly = {
      ...cy.events[1],
      payload: { effective_date: "2026-10-08", seq: 0, name: "새 이름", before: { name: "옛 이름" } },
    };
    const pos = { ...TIGER, cycles: [{ ...cy, events: [cy.events[0], nameOnly] }] };
    fetchTradeHistory.mockResolvedValue(only(pos));
    renderDialog(TIGER.position_id);
    expect(await screen.findByText("종목명 정정: 옛 이름 → 새 이름")).toBeInTheDocument();
    expect(screen.queryByText(/정정 전 수량/)).toBeNull();
  });
});
