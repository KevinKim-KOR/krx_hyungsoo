// POC5-05 개정 2 — 새 보유 추가 · 재매수 창(NewHoldingDialog) 동작 계약.
//   재매수 = 종목 · 계좌 고정 · 잔고 등록 없음 · position_id · 잔고 등록 = register · 거래일 칸 없음 ·
//   과거 보유 안내 · History 연결 · 여러 줄이면 고르게 함 · 종목명 조회의 늦은 응답 무시.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";

const putTradeCommand = vi.fn();
const fetchEtfName = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    putTradeCommand: (...a: unknown[]) => putTradeCommand(...a),
    fetchEtfName: (...a: unknown[]) => fetchEtfName(...a),
  };
});

import { ApiRequestError, type PositionHistory } from "@/lib/api";
import NewHoldingDialog from "./NewHoldingDialog";
import { todayKst } from "./format";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

function closedCycle(id: string, start: string | null, end: string, realized: string) {
  return {
    cycle_id: id,
    status: "CLOSED" as const,
    opened_by: start ? ("BUY" as const) : ("BASELINE" as const),
    closed_by: "SELL" as const,
    start_date: start,
    end_date: end,
    has_adjustment: false,
    quantity: "0",
    cost: "0",
    avg_buy_price: null,
    realized_pnl: realized,
    sold_cost: "1000000",
    realized_rate: "-4.25",
    events: [],
    voided: [],
  };
}

const PAST_BATTERY: PositionHistory = {
  position_id: "pos-old",
  ticker: "305540",
  name: "TIGER 2차전지테마",
  account_group: "일반",
  is_open: false,
  cycles: [closedCycle("cyc-a", "2026-08-04", "2026-09-22", "-42500")],
};

const ACCOUNTS = ["일반", "ISA", "연금"];

const OK_RESULT = {
  record: {
    record_id: "x",
    kind: "BUY",
    recorded_at: "2026-10-08T10:00:00+09:00",
    supersedes_id: null,
    payload: {},
    position_id: "pos-new",
    cycle_id: "cyc-new",
  },
  holdings: [],
  revision: 6,
};

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

beforeEach(() => {
  putTradeCommand.mockReset();
  fetchEtfName.mockReset();
  putTradeCommand.mockResolvedValue(OK_RESULT);
  fetchEtfName.mockImplementation((t: string) =>
    Promise.resolve(
      t === "069500"
        ? { ticker: t, found: true, name: "KODEX 200" }
        : t === "305540"
          ? { ticker: t, found: true, name: "TIGER 2차전지테마" }
          : { ticker: t, found: false, name: null },
    ),
  );
});

function renderNew(props: Partial<React.ComponentProps<typeof NewHoldingDialog>> = {}) {
  const onSaved = vi.fn();
  const onClose = vi.fn();
  const onOpenHistory = vi.fn();
  const utils = render(
    <NewHoldingDialog
      revision={5}
      pastPositions={[]}
      accountOptions={ACCOUNTS}
      onClose={onClose}
      onSaved={onSaved}
      onOpenHistory={onOpenHistory}
      {...props}
    />,
  );
  return { ...utils, onSaved, onClose, onOpenHistory };
}

function type(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

async function typeTicker(value: string) {
  await act(async () => {
    type("종목코드", value);
  });
}

async function clickSave() {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
  });
}

function fieldLabels(container: HTMLElement): (string | null | undefined)[] {
  const form = container.querySelector(".hmx-form")!;
  return Array.from(form.children)
    .filter((el) => el.classList.contains("hmx-field"))
    .map((f) => f.firstElementChild?.textContent);
}

describe("일반 모드 · 최초 매수", () => {
  it("칸 순서(종목코드 · 종목명 · 계좌 / 거래일 · 거래 시각 · 종류 / 체결단가 · 수량 · 계산 금액) · new_position 명령", async () => {
    const { container, onSaved } = renderNew();
    expect(screen.getByRole("dialog", { name: "새 보유 추가" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "최초 매수" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "잔고 등록" })).toHaveAttribute("aria-pressed", "false");
    expect(fieldLabels(container)).toEqual([
      "종목코드",
      "종목명",
      "계좌",
      "거래일",
      "거래 시각 (선택)",
      "종류",
      "체결단가 (원)",
      "수량",
      "계산 금액 (원)",
    ]);
    expect(screen.getByText("최초 매수", { selector: "output" })).toBeInTheDocument();
    expect((screen.getByLabelText("계좌") as HTMLSelectElement).value).toBe("일반");

    await typeTicker("069500");
    await waitFor(() => expect(screen.getByText("KODEX 200")).toBeInTheDocument());
    type("거래 시각 (선택)", "09:31");
    type("체결단가 (원)", "9,850");
    type("수량", "20");
    expect(screen.getByText("197,000")).toBeInTheDocument();
    await clickSave();
    const cmd = putTradeCommand.mock.calls[0][0];
    expect(cmd).toEqual({
      record_id: expect.stringMatching(UUID_RE),
      base_revision: 5,
      action: "new_position",
      position_id: null,
      ticker: "069500",
      account_group: "일반",
      name: "KODEX 200",
      trade: {
        trade_date: todayKst(),
        trade_time: "09:31",
        price: "9850",
        quantity: "20",
        memo: null,
      },
    });
    expect(onSaved).toHaveBeenCalledWith(OK_RESULT);
  });

  it("종목코드 형식이 아니면 조회하지 않고 저장도 비활성이다", async () => {
    renderNew();
    await typeTicker("0695");
    type("체결단가 (원)", "100");
    type("수량", "1");
    expect(fetchEtfName).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "저장" })).toBeDisabled();
  });

  it("ETF 목록에 없는 종목은 종목명을 직접 적어 보낸다(같은 칸 · 선택)", async () => {
    fetchEtfName.mockResolvedValue({ ticker: "005930", found: false, name: null });
    renderNew();
    await typeTicker("005930");
    await waitFor(() => expect(screen.getByLabelText("종목명 (선택 · ETF 목록에 없음)")).toBeInTheDocument());
    type("종목명 (선택 · ETF 목록에 없음)", " 삼성전자 ");
    type("체결단가 (원)", "71200");
    type("수량", "3");
    await clickSave();
    expect(putTradeCommand.mock.calls[0][0].name).toBe("삼성전자");
  });

  it("계좌는 목록에서만 고른다(기존 계좌 포함 · 직접 입력 없음 · POC3-08 (D))", async () => {
    renderNew({ accountOptions: ["일반", "ISA", "키움-일반"] });
    await typeTicker("069500");
    expect(screen.queryByRole("option", { name: "직접 입력…" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("계좌"), { target: { value: "키움-일반" } });
    type("체결단가 (원)", "100");
    type("수량", "1");
    await clickSave();
    expect(putTradeCommand.mock.calls[0][0].account_group).toBe("키움-일반");
  });

  it("이모지가 든 기존 30자 계좌도 저장할 수 있다(글자 수 = 코드 포인트 · 서버와 같음)", async () => {
    const acct = `${"A".repeat(29)}📈`; // 30자 · UTF-16 길이 31
    renderNew({ accountOptions: ["일반", acct, "B".repeat(31)] });
    await typeTicker("069500");
    type("체결단가 (원)", "100");
    type("수량", "1");
    fireEvent.change(screen.getByLabelText("계좌"), { target: { value: "B".repeat(31) } });
    expect(screen.getByRole("button", { name: "저장" })).toBeDisabled(); // 31자는 그대로 막는다
    fireEvent.change(screen.getByLabelText("계좌"), { target: { value: acct } });
    expect(screen.getByRole("button", { name: "저장" })).not.toBeDisabled();
    await clickSave();
    expect(putTradeCommand.mock.calls[0][0].account_group).toBe(acct);
  });
});

describe("잔고 등록", () => {
  it("거래일 · 시각 칸 없음 · 평단/매입금액 라벨 · register 명령(holding)", async () => {
    const { container } = renderNew();
    fireEvent.click(screen.getByRole("button", { name: "잔고 등록" }));
    expect(screen.queryByLabelText("거래일")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("거래 시각 (선택)")).not.toBeInTheDocument();
    expect(fieldLabels(container)).toEqual([
      "종목코드",
      "종목명",
      "계좌",
      "평단 (원)",
      "수량",
      "매입금액 (원)",
    ]);
    expect(
      screen.getByText(
        "잔고 등록은 거래를 모르는 기존 잔고입니다. 매수일은 미상으로 남고, 손익은 입력 평단 기준으로 계산합니다.",
      ),
    ).toBeInTheDocument();
    await typeTicker("069500");
    fireEvent.change(screen.getByLabelText("계좌"), { target: { value: "ISA" } });
    type("평단 (원)", "10,000.5");
    type("수량", "10");
    expect(screen.getByText("100,005")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("KODEX 200")).toBeInTheDocument());
    await clickSave();
    const cmd = putTradeCommand.mock.calls[0][0];
    expect(cmd).toEqual({
      record_id: expect.stringMatching(UUID_RE),
      base_revision: 5,
      action: "register",
      ticker: "069500",
      account_group: "ISA",
      name: "KODEX 200",
      holding: { quantity: "10", avg_buy_price: "10000.5" },
    });
    expect("trade" in cmd).toBe(false);
    expect("position_id" in cmd).toBe(false);
  });
});

describe("재매수 모드", () => {
  const REBUY = {
    position_id: "pos-old",
    ticker: "305540",
    name: "TIGER 2차전지테마",
    account_group: "일반",
  };

  it("종목 · 계좌 고정 · 잔고 등록 선택 없음 · 과거 기간 안내 · position_id 를 싣는다", async () => {
    const { onOpenHistory } = renderNew({ rebuy: REBUY, pastPositions: [PAST_BATTERY] });
    expect(screen.getByRole("dialog", { name: "재매수 — TIGER 2차전지테마 · 일반" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "잔고 등록" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "최초 매수" })).not.toBeInTheDocument();
    const ticker = screen.getByLabelText("종목코드") as HTMLInputElement;
    expect(ticker.value).toBe("305540");
    expect(ticker.readOnly).toBe(true);
    const acct = screen.getByLabelText("계좌") as HTMLInputElement;
    expect(acct.value).toBe("일반");
    expect(acct.readOnly).toBe(true);
    expect(screen.getByText("최초 매수", { selector: "output" })).toBeInTheDocument();
    expect(fetchEtfName).not.toHaveBeenCalled(); // 종목명이 이미 있으면 조회하지 않는다

    const info = screen.getByText(/같은 종목 · 계좌의 과거 보유 기간 1건이 있습니다/);
    expect(info).toHaveTextContent(
      "같은 종목 · 계좌의 과거 보유 기간 1건이 있습니다(2026-08-04 ~ 2026-09-22 · 실현 -42,500원). 저장하면 그 종목의 새 보유 기간으로 시작하고, 이전 기간의 원가 · 손익은 넘어오지 않습니다.",
    );
    fireEvent.click(screen.getByRole("button", { name: "History 보기" }));
    expect(onOpenHistory).toHaveBeenCalledWith("pos-old");

    type("체결단가 (원)", "9000");
    type("수량", "3");
    await clickSave();
    expect(putTradeCommand.mock.calls[0][0]).toEqual({
      record_id: expect.stringMatching(UUID_RE),
      base_revision: 5,
      action: "new_position",
      position_id: "pos-old",
      ticker: "305540",
      account_group: "일반",
      name: "TIGER 2차전지테마",
      trade: {
        trade_date: todayKst(),
        trade_time: null,
        price: "9000",
        quantity: "3",
        memo: null,
      },
    });
  });

  it("기존 비정형 종목코드 줄도 재매수 저장이 가능하다(형식 검사는 새 입력에만)", async () => {
    renderNew({ rebuy: { ...REBUY, ticker: "abc12" }, pastPositions: [] });
    type("체결단가 (원)", "100");
    type("수량", "1");
    expect(screen.getByRole("button", { name: "저장" })).not.toBeDisabled();
    await clickSave();
    expect(putTradeCommand.mock.calls[0][0]).toMatchObject({
      action: "new_position",
      position_id: "pos-old",
    });
  });

  it("이모지가 든 기존 30자 계좌 줄도 재매수 저장이 가능하다(글자 수 = 코드 포인트)", async () => {
    renderNew({ rebuy: { ...REBUY, account_group: `${"A".repeat(29)}📈` }, pastPositions: [] });
    type("체결단가 (원)", "100");
    type("수량", "1");
    expect(screen.getByRole("button", { name: "저장" })).not.toBeDisabled();
    await clickSave();
    expect(putTradeCommand.mock.calls[0][0]).toMatchObject({
      action: "new_position",
      position_id: "pos-old",
    });
  });

  it("재매수 대상 종목명이 비어 있으면 종목명을 조회해 보인다", async () => {
    renderNew({ rebuy: { ...REBUY, name: null }, pastPositions: [PAST_BATTERY] });
    await waitFor(() => expect(fetchEtfName).toHaveBeenCalledWith("305540"));
    expect(await screen.findByText("TIGER 2차전지테마", { selector: "span" })).toBeInTheDocument();
  });
});

describe("과거 보유 안내(일반 모드)", () => {
  it("같은 (종목코드, 계좌)가 과거 보유에 있으면 안내 · History 연결 · 매수일 미상 표시 · 계좌가 다르면 숨김", async () => {
    const hynix: PositionHistory = {
      position_id: "pos-hx",
      ticker: "000660",
      name: "SK하이닉스",
      account_group: "연금",
      is_open: false,
      cycles: [closedCycle("cyc-h", null, "2026-09-30", "186000")],
    };
    const { onOpenHistory } = renderNew({ pastPositions: [PAST_BATTERY, hynix] });
    await typeTicker("000660");
    expect(screen.queryByText(/과거 보유 기간/)).not.toBeInTheDocument(); // 계좌 '일반' ≠ '연금'
    fireEvent.change(screen.getByLabelText("계좌"), { target: { value: "연금" } });
    expect(screen.getByText(/과거 보유 기간 1건이 있습니다/)).toHaveTextContent(
      "(매수일 미상 ~ 2026-09-30 · 실현 +186,000원)",
    );
    expect(screen.getByLabelText("종목명 (선택 · ETF 목록에 없음)")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "History 보기" }));
    expect(onOpenHistory).toHaveBeenCalledWith("pos-hx");
  });

  it("같은 종목 · 계좌의 과거 보유가 여러 줄이면 고르라고 안내하고 저장을 막는다", async () => {
    const second: PositionHistory = {
      ...PAST_BATTERY,
      position_id: "pos-old-2",
      cycles: [closedCycle("cyc-b", "2026-03-02", "2026-05-20", "8000")],
    };
    renderNew({ pastPositions: [PAST_BATTERY, second] });
    await typeTicker("305540");
    expect(screen.getByText(/과거 보유 기간 2건이 있습니다/)).toHaveTextContent(
      "(2026-08-04 ~ 2026-09-22 · 실현 -42,500원)",
    );
    expect(screen.getByText(/과거 보유에서 재매수할 줄을 고르세요/)).toBeInTheDocument();
    type("체결단가 (원)", "9000");
    type("수량", "1");
    expect(screen.getByRole("button", { name: "저장" })).toBeDisabled();
  });
});

describe("종목명 자동 조회", () => {
  it("늦게 온 이전 응답은 무시한다", async () => {
    const slow = deferred<{ ticker: string; found: boolean; name: string | null }>();
    fetchEtfName.mockImplementation((t: string) =>
      t === "069500" ? slow.promise : Promise.resolve({ ticker: t, found: true, name: "TIGER 200 IT" }),
    );
    renderNew();
    await typeTicker("069500");
    expect(screen.getByText("조회 중…")).toBeInTheDocument();
    await typeTicker("139260");
    await waitFor(() => expect(screen.getByText("TIGER 200 IT")).toBeInTheDocument());
    await act(async () => {
      slow.resolve({ ticker: "069500", found: true, name: "KODEX 200" });
    });
    expect(screen.queryByText("KODEX 200")).not.toBeInTheDocument();
    expect(screen.getByText("TIGER 200 IT")).toBeInTheDocument();
    type("체결단가 (원)", "100");
    type("수량", "1");
    await clickSave();
    expect(putTradeCommand.mock.calls[0][0]).toMatchObject({ ticker: "139260", name: "TIGER 200 IT" });
  });

  it("ETF 목록에 없으면 종목명 칸(선택)이 나오고, 비워 두면 종목명 없이 보낸다", async () => {
    renderNew();
    await typeTicker("005930");
    await waitFor(() =>
      expect(screen.getByLabelText("종목명 (선택 · ETF 목록에 없음)")).toBeInTheDocument(),
    );
    type("체결단가 (원)", "71200");
    type("수량", "3");
    await clickSave();
    expect(putTradeCommand.mock.calls[0][0]).toMatchObject({ ticker: "005930", name: null });
  });
});

describe("저장 오류 · record_id", () => {
  it("409 는 서버 문구 + 새로고침 안내 · 같은 내용 재시도는 같은 record_id", async () => {
    putTradeCommand.mockRejectedValueOnce(
      new ApiRequestError("요청 실패", 409, {
        detail: "같은 종목 · 계좌를 이미 보유 중입니다 — 그 줄의 매매(추가매수)나 입력 정정을 쓰세요.",
      }),
    );
    const { onSaved } = renderNew();
    await typeTicker("069500");
    await waitFor(() => expect(screen.getByText("KODEX 200")).toBeInTheDocument());
    type("체결단가 (원)", "100");
    type("수량", "1");
    await clickSave();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "같은 종목 · 계좌를 이미 보유 중입니다 — 그 줄의 매매(추가매수)나 입력 정정을 쓰세요. 창을 닫으면 최신 보유로 새로고침됩니다.",
    );
    await clickSave();
    const ids = putTradeCommand.mock.calls.map((c) => c[0].record_id);
    expect(ids[1]).toBe(ids[0]);
    expect(onSaved).toHaveBeenCalledTimes(1);
  });
});
