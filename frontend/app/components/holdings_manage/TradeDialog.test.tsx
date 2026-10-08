// POC5-05 개정 2 — 매매 입력 창(TradeDialog) 동작 계약.
//   칸 순서 · 미리보기(설계 §3 계산 예) · 잔량 초과 차단 · 전량매도 잔량 고정 · 명령 모양 ·
//   record_id 재시도 규칙 · 409 문구 · 거래 오기 정정 모드 · 같은 날 앞/뒤 선택.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";

const putTradeCommand = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    putTradeCommand: (...a: unknown[]) => putTradeCommand(...a),
  };
});

import { ApiRequestError, type HoldingItem } from "@/lib/api";
import TradeDialog from "./TradeDialog";
import { todayKst } from "./format";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

const H10: HoldingItem = {
  ticker: "069500",
  name: "KODEX 200",
  account_group: "ISA",
  quantity: 10,
  avg_buy_price: 10000,
  position_id: "pos-1",
  cycle_id: "cyc-1",
};

// 설계 §3 예: 10주×10,000 + 5주×12,000 = 15주 · 원가 160,000 · 평단 10,666.666…
const H15: HoldingItem = { ...H10, quantity: 15, avg_buy_price: 160000 / 15 };

const OK_RESULT = {
  record: {
    record_id: "x",
    kind: "BUY",
    recorded_at: "2026-10-08T10:00:00+09:00",
    supersedes_id: null,
    payload: {},
    position_id: "pos-1",
    cycle_id: "cyc-1",
  },
  holdings: [],
  revision: 4,
};

beforeEach(() => {
  putTradeCommand.mockReset();
  putTradeCommand.mockResolvedValue(OK_RESULT);
});

function renderTrade(props: Partial<React.ComponentProps<typeof TradeDialog>> = {}) {
  const onSaved = vi.fn();
  const onClose = vi.fn();
  const utils = render(
    <TradeDialog holding={H10} revision={3} onClose={onClose} onSaved={onSaved} {...props} />,
  );
  return { ...utils, onSaved, onClose };
}

function type(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

async function clickSave(name = "매매 저장") {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name }));
  });
}

function sentCommands(): Record<string, unknown>[] {
  return putTradeCommand.mock.calls.map((c) => c[0] as Record<string, unknown>);
}

describe("화면 · 칸 배치", () => {
  it("제목 · 부제와 두 줄 같은 그리드(거래일 · 거래 시각 · 종류 / 체결단가 · 수량 · 계산 금액) + 전체 폭 메모", () => {
    const { container } = renderTrade();
    expect(screen.getByRole("dialog", { name: "KODEX 200 · ISA 매매 입력" })).toBeInTheDocument();
    expect(screen.getByText("지금 10주 · 평단 10,000원 · 원가 100,000원")).toBeInTheDocument();
    const forms = container.querySelectorAll(".hmx-form");
    expect(forms).toHaveLength(1);
    const fields = Array.from(forms[0].children).filter((el) => el.classList.contains("hmx-field"));
    expect(fields.map((f) => f.firstElementChild?.textContent)).toEqual([
      "거래일",
      "거래 시각 (선택)",
      "종류",
      "체결단가 (원)",
      "수량",
      "계산 금액 (원)",
      "메모 (선택)",
    ]);
    expect(fields[6].classList.contains("hmx-field-wide")).toBe(true);
    // 종류 = 버튼 3개(추가매수 기본)
    expect(screen.getByRole("button", { name: "추가매수" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "분할매도" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "전량매도" })).toHaveAttribute("aria-pressed", "false");
    expect((screen.getByLabelText("거래일") as HTMLInputElement).value).toBe(todayKst());
    expect(screen.getByLabelText("거래일")).toHaveAttribute("max", todayKst());
    expect(
      screen.getByText(/시각을 모르면 비워 두세요\(날짜 단위로 기록\)\. 휴장일 날짜도 기록할 수 있습니다\./),
    ).toBeInTheDocument();
  });
});

describe("미리보기", () => {
  it("추가매수: 10주 평단 10,000 + 5주×12,000 → 15주 · 평단 10,666.67원 · 실현손익 — (매수)", () => {
    renderTrade();
    type("체결단가 (원)", "12,000");
    type("수량", "5");
    expect(screen.getByText("60,000")).toBeInTheDocument();
    expect(screen.getByText("15주")).toBeInTheDocument();
    expect(screen.getByText("10,666.67원")).toBeInTheDocument();
    expect(screen.getByText("— (매수)")).toBeInTheDocument();
  });

  it("분할매도: 15주(원가 160,000)에서 6주×13,000 → 실현 +14,000원 · +21.88% · 9주 · 평단 유지", () => {
    renderTrade({ holding: H15 });
    fireEvent.click(screen.getByRole("button", { name: "분할매도" }));
    type("체결단가 (원)", "13000");
    type("수량", "6");
    expect(screen.getByText("+14,000원 · +21.88%")).toBeInTheDocument();
    expect(screen.getByText("9주")).toBeInTheDocument();
    expect(screen.getByText("10,666.67원 (유지)")).toBeInTheDocument();
  });

  it("잔량 초과면 '잔량 초과 — 저장할 수 없음' 이고 저장 버튼이 비활성이다", () => {
    renderTrade();
    fireEvent.click(screen.getByRole("button", { name: "분할매도" }));
    type("체결단가 (원)", "13000");
    type("수량", "11");
    expect(screen.getByText("잔량 초과 — 저장할 수 없음")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "매매 저장" })).toBeDisabled();
    type("수량", "10");
    expect(screen.queryByText("잔량 초과 — 저장할 수 없음")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "매매 저장" })).toBeEnabled();
  });
});

describe("전량매도", () => {
  it("수량 = 현재 잔량으로 고정(readOnly) · 보유 종료 미리보기 · sell_all 명령", async () => {
    renderTrade({ initialKind: "sell_all" });
    const qty = screen.getByLabelText("수량") as HTMLInputElement;
    expect(screen.getByRole("button", { name: "전량매도" })).toHaveAttribute("aria-pressed", "true");
    expect(qty.value).toBe("10");
    expect(qty.readOnly).toBe(true);
    type("체결단가 (원)", "9500");
    expect(screen.getByText("0주 (보유 종료)")).toBeInTheDocument();
    expect(screen.getByText("-5,000원 · -5%")).toBeInTheDocument();
    await clickSave();
    const [cmd] = sentCommands();
    expect(cmd.action).toBe("sell_all");
    expect((cmd.trade as Record<string, unknown>).quantity).toBe("10");
  });

  it("서버의 정확한 잔량(십진 문자열)이 있으면 float 대신 그 값을 보낸다", async () => {
    renderTrade({
      initialKind: "sell_all",
      holding: { ...H10, quantity: 10.123456789012345 },
      exactQuantity: "10.12345678901234567",
    });
    type("체결단가 (원)", "9500");
    await clickSave();
    const [cmd] = sentCommands();
    expect((cmd.trade as Record<string, unknown>).quantity).toBe("10.12345678901234567");
  });

  it("다른 종류로 바꾸면 수량 칸을 다시 고칠 수 있다", () => {
    renderTrade();
    fireEvent.click(screen.getByRole("button", { name: "전량매도" }));
    expect((screen.getByLabelText("수량") as HTMLInputElement).readOnly).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "분할매도" }));
    expect((screen.getByLabelText("수량") as HTMLInputElement).readOnly).toBe(false);
  });
});

describe("명령 모양", () => {
  it("추가매수 저장 → action buy · position_id · base_revision · trade(쉼표 제거 십진 문자열) · same_day 없음", async () => {
    const { onSaved } = renderTrade();
    type("거래일", "2026-09-24");
    type("거래 시각 (선택)", "10:42");
    type("체결단가 (원)", "12,000.5");
    type("수량", "5");
    type("메모 (선택)", "  실적 발표 뒤  ");
    await clickSave();
    expect(putTradeCommand).toHaveBeenCalledTimes(1);
    const [cmd] = sentCommands();
    expect(cmd).toEqual({
      record_id: expect.stringMatching(UUID_RE),
      base_revision: 3,
      action: "buy",
      position_id: "pos-1",
      trade: {
        trade_date: "2026-09-24",
        trade_time: "10:42",
        price: "12000.5",
        quantity: "5",
        memo: "실적 발표 뒤",
      },
    });
    expect("same_day" in cmd).toBe(false);
    expect(onSaved).toHaveBeenCalledWith(OK_RESULT);
  });

  it("시각 · 메모를 비우면 null 로 보낸다(미상 시각을 채우지 않는다)", async () => {
    renderTrade();
    fireEvent.click(screen.getByRole("button", { name: "분할매도" }));
    type("체결단가 (원)", "13000");
    type("수량", "2");
    await clickSave();
    const [cmd] = sentCommands();
    expect(cmd.action).toBe("sell");
    expect(cmd.trade).toEqual({
      trade_date: todayKst(),
      trade_time: null,
      price: "13000",
      quantity: "2",
      memo: null,
    });
  });
});

describe("record_id — 저장 동작마다 새 ID · 실패 뒤 같은 내용 재시도는 같은 ID", () => {
  it("네트워크 실패 → 같은 내용 재시도 = 같은 ID · 내용 변경 = 새 ID · 성공 뒤 새 저장 = 새 ID", async () => {
    const netErr = new ApiRequestError("네트워크 호출 실패: PUT /holdings/trade-history — x", 0, null);
    putTradeCommand
      .mockRejectedValueOnce(netErr)
      .mockRejectedValueOnce(netErr)
      .mockRejectedValueOnce(netErr);
    const { onSaved } = renderTrade();
    type("체결단가 (원)", "12000");
    type("수량", "5");

    await clickSave();
    expect(screen.getByRole("alert")).toHaveTextContent("네트워크 호출 실패");
    await clickSave(); // 같은 내용 재시도(실패)
    type("수량", "6"); // 내용 변경
    await clickSave(); // 실패
    expect(onSaved).not.toHaveBeenCalled();
    await clickSave(); // 같은 내용 재시도(성공)
    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
    await clickSave(); // 성공 뒤 새 저장

    const ids = sentCommands().map((c) => c.record_id as string);
    expect(ids).toHaveLength(5);
    ids.forEach((id) => expect(id).toMatch(UUID_RE));
    expect(ids[1]).toBe(ids[0]); // 같은 내용 재시도
    expect(ids[2]).not.toBe(ids[1]); // 내용이 바뀌면 새 ID
    expect(ids[3]).toBe(ids[2]); // 바뀐 내용의 재시도 = 그 ID
    expect(ids[4]).not.toBe(ids[3]); // 성공 뒤 새 저장 = 새 ID
    expect(ids[4]).not.toBe(ids[0]);
  });

  it("저장 중에는 버튼이 비활성이고 두 번 눌러도 한 번만 보낸다", async () => {
    let resolve!: (v: unknown) => void;
    putTradeCommand.mockImplementationOnce(() => new Promise((r) => (resolve = r)));
    const { onSaved } = renderTrade();
    type("체결단가 (원)", "12000");
    type("수량", "5");
    await clickSave();
    const busy = screen.getByRole("button", { name: "저장 중…" });
    expect(busy).toBeDisabled();
    expect(screen.getByRole("button", { name: "취소" })).toBeDisabled();
    fireEvent.click(busy);
    expect(putTradeCommand).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolve(OK_RESULT);
    });
    expect(onSaved).toHaveBeenCalledWith(OK_RESULT);
  });

  it("409 는 서버 문구 뒤에 '창을 닫으면 최신 보유로 새로고침됩니다.' 를 붙인다", async () => {
    putTradeCommand.mockRejectedValueOnce(
      new ApiRequestError("요청 실패: PUT /holdings/trade-history (HTTP 409)", 409, {
        detail: "다른 화면에서 보유가 바뀌었습니다 — 새로고침한 뒤 다시 입력하세요.",
      }),
    );
    const { onSaved } = renderTrade();
    type("체결단가 (원)", "12000");
    type("수량", "5");
    await clickSave();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "다른 화면에서 보유가 바뀌었습니다 — 새로고침한 뒤 다시 입력하세요. 창을 닫으면 최신 보유로 새로고침됩니다.",
    );
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("422 는 서버 문구를 그대로 보인다", async () => {
    putTradeCommand.mockRejectedValueOnce(
      new ApiRequestError("요청 실패", 422, { detail: "체결단가 는 소수 2자리까지만 입력할 수 있습니다." }),
    );
    renderTrade();
    type("체결단가 (원)", "12000.123");
    type("수량", "5");
    await clickSave();
    expect(screen.getByRole("alert")).toHaveTextContent(
      /^체결단가 는 소수 2자리까지만 입력할 수 있습니다\.$/,
    );
  });
});

describe("거래 오기 정정 모드", () => {
  const CORRECT = {
    recordId: "rec-9",
    kind: "SELL" as const,
    tradeDate: "2026-09-30",
    tradeTime: null,
    price: "13000",
    quantity: "7",
    memo: "분할매도",
  };

  it("제목 · 종류 고정 · 값 미리 채움 · 미리보기 대신 재계산 안내 · action correct + supersedes_id", async () => {
    renderTrade({ correct: CORRECT, eventDates: ["2026-09-30"] });
    expect(screen.getByRole("dialog", { name: "매매 기록 정정" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "추가매수" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "분할매도" })).not.toBeInTheDocument();
    expect(screen.getByText("매도")).toBeInTheDocument();
    expect((screen.getByLabelText("거래일") as HTMLInputElement).value).toBe("2026-09-30");
    expect((screen.getByLabelText("체결단가 (원)") as HTMLInputElement).value).toBe("13000");
    expect((screen.getByLabelText("수량") as HTMLInputElement).value).toBe("7");
    expect((screen.getByLabelText("메모 (선택)") as HTMLInputElement).value).toBe("분할매도");
    expect(screen.queryByText("저장 후 수량")).not.toBeInTheDocument();
    expect(screen.getByText("저장하면 이 기간을 다시 계산합니다.")).toBeInTheDocument();
    // 같은 날짜 그대로면 서버가 원래 순서를 유지 → 앞/뒤 선택 없음
    expect(screen.queryByRole("group", { name: "같은 날 기존 기록의 뒤 / 앞" })).not.toBeInTheDocument();

    type("수량", "6");
    await clickSave("정정 저장");
    const [cmd] = sentCommands();
    expect(cmd).toEqual({
      record_id: expect.stringMatching(UUID_RE),
      base_revision: 3,
      action: "correct",
      position_id: "pos-1",
      supersedes_id: "rec-9",
      trade: {
        trade_date: "2026-09-30",
        trade_time: null,
        price: "13000",
        quantity: "6",
        memo: "분할매도",
      },
    });
    expect("same_day" in cmd).toBe(false);
  });

  it("기존 정밀도 수량의 기록을 단가만 정정하면 수량을 그대로 보낸다(화면이 자릿수를 막지 않음)", async () => {
    renderTrade({ correct: { ...CORRECT, quantity: "0.1234567" } });
    type("체결단가 (원)", "12000");
    await clickSave("정정 저장");
    const [cmd] = sentCommands();
    expect(cmd.action).toBe("correct");
    expect((cmd.trade as Record<string, unknown>).quantity).toBe("0.1234567");
  });

  it("정정 모드는 잔량 미리보기 검사를 하지 않는다(재계산 검사는 서버)", () => {
    renderTrade({ correct: { ...CORRECT, quantity: "50" } });
    expect(screen.getByRole("button", { name: "정정 저장" })).toBeEnabled();
  });
});

describe("같은 날 기존 기록 앞/뒤", () => {
  it("거래일이 eventDates 에 있으면 선택 칸이 보이고 same_day 가 실린다(기본 after · '앞' = before)", async () => {
    renderTrade({ eventDates: ["2020-01-02"] });
    expect(screen.queryByRole("group", { name: "같은 날 기존 기록의 뒤 / 앞" })).not.toBeInTheDocument();
    type("거래일", "2020-01-02");
    expect(screen.getByRole("group", { name: "같은 날 기존 기록의 뒤 / 앞" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "뒤 (기본)" })).toHaveAttribute("aria-pressed", "true");
    type("체결단가 (원)", "12000");
    type("수량", "1");
    await clickSave();
    expect(sentCommands()[0].same_day).toBe("after");

    fireEvent.click(screen.getByRole("button", { name: "앞" }));
    await clickSave();
    expect(sentCommands()[1].same_day).toBe("before");
  });

  it("다른 날짜면 선택 칸이 없고 same_day 를 보내지 않는다", async () => {
    renderTrade({ eventDates: ["2020-01-02"] });
    type("거래일", "2020-01-03");
    type("체결단가 (원)", "12000");
    type("수량", "1");
    await clickSave();
    expect("same_day" in sentCommands()[0]).toBe(false);
  });

  it("정정 모드에서 날짜를 다른 기록이 있는 날로 옮기면 선택 칸이 보인다", async () => {
    renderTrade({
      correct: {
        recordId: "rec-1",
        kind: "BUY",
        tradeDate: "2020-01-03",
        tradeTime: "09:10",
        price: "100",
        quantity: "1",
        memo: null,
      },
      eventDates: ["2020-01-02", "2020-01-03"],
    });
    expect(screen.getByText("매수")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "같은 날 기존 기록의 뒤 / 앞" })).not.toBeInTheDocument();
    type("거래일", "2020-01-02");
    fireEvent.click(screen.getByRole("button", { name: "앞" }));
    await clickSave("정정 저장");
    const [cmd] = sentCommands();
    expect(cmd.action).toBe("correct");
    expect(cmd.same_day).toBe("before");
    expect((cmd.trade as Record<string, unknown>).trade_time).toBe("09:10");
  });
});
