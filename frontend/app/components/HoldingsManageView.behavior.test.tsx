// POC3-08 재작업(검증자 지적) — 종목 관리 화면 실제 비동기·정합 계약 test.
//   #1 비동기 종목명 조회와 정렬·삭제의 index 경합(uid 기반으로 해소).
//   #2 기존 사용자 정의 계좌의 표시값 = 저장값 정합(위장 금지).
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, fireEvent, waitFor } from "@testing-library/react";

const fetchHoldings = vi.fn();
const saveHoldings = vi.fn();
const fetchEtfName = vi.fn();
const fetchHoldingsApplyStatus = vi.fn();
const applyHoldingsToOci = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchHoldings: (...a: unknown[]) => fetchHoldings(...a),
    saveHoldings: (...a: unknown[]) => saveHoldings(...a),
    fetchEtfName: (...a: unknown[]) => fetchEtfName(...a),
    fetchHoldingsApplyStatus: (...a: unknown[]) => fetchHoldingsApplyStatus(...a),
    applyHoldingsToOci: (...a: unknown[]) => applyHoldingsToOci(...a),
  };
});

import HoldingsManageView from "./HoldingsManageView";

// 조회 응답을 수동 제어하기 위한 deferred.
function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

beforeEach(() => {
  fetchHoldings.mockReset();
  saveHoldings.mockReset();
  fetchEtfName.mockReset();
  fetchHoldingsApplyStatus.mockReset();
  applyHoldingsToOci.mockReset();
  fetchHoldingsApplyStatus.mockResolvedValue({ has_record: false });
});

function renderView() {
  return render(<HoldingsManageView onNavigate={() => {}} />);
}

// ─── #1 비동기 조회 ↔ 정렬/삭제 경합 ──────────────────────────────

describe("#1 비동기 종목명 조회가 정렬·삭제 후 엉뚱한 행을 안 건드린다", () => {
  it("조회 진행 중 행이 삭제되면 늦게 온 응답은 어떤 행에도 적용되지 않는다", async () => {
    // 두 행 로드: A(069500), B(139260). A 는 조회를 지연(deferred)시킨다.
    fetchHoldings.mockResolvedValue({
      holdings: [
        { ticker: "069500", name: "", quantity: 1, avg_buy_price: 100, account_group: "일반" },
        { ticker: "139260", name: "", quantity: 1, avg_buy_price: 100, account_group: "일반" },
      ],
    });
    const dA = deferred<{ ticker: string; found: boolean; name: string | null }>();
    fetchEtfName.mockImplementation((t: string) => {
      if (t === "069500") return dA.promise; // A 지연
      return Promise.resolve({ ticker: t, found: true, name: "TIGER 200 IT" });
    });

    await act(async () => {
      renderView();
    });

    // B 는 즉시 이름 자동채움 확인.
    await waitFor(() =>
      expect(screen.getByDisplayValue("TIGER 200 IT")).toBeInTheDocument()
    );

    // A(첫 행) 삭제.
    const delButtons = screen.getAllByRole("button", { name: "이 행 삭제" });
    await act(async () => {
      fireEvent.click(delButtons[0]);
    });

    // 이제 A 의 늦은 응답 도착(삭제된 행 대상).
    await act(async () => {
      dA.resolve({ ticker: "069500", found: true, name: "KODEX 200" });
      await Promise.resolve();
    });

    // 삭제된 A 의 이름("KODEX 200")이 남은 행(B)에 잘못 적용되면 안 된다.
    expect(screen.queryByDisplayValue("KODEX 200")).not.toBeInTheDocument();
    // B 의 이름은 그대로 유지.
    expect(screen.getByDisplayValue("TIGER 200 IT")).toBeInTheDocument();
  });

  it("조회 도중 같은 행의 종목코드를 바꾸면 이전 코드의 응답은 폐기된다", async () => {
    fetchHoldings.mockResolvedValue({ holdings: [] }); // 빈 시작(행 1개)
    const d1 = deferred<{ ticker: string; found: boolean; name: string | null }>();
    fetchEtfName.mockImplementation((t: string) => {
      if (t === "069500") return d1.promise;
      return Promise.resolve({ ticker: t, found: true, name: "TIGER 200 IT" });
    });

    await act(async () => {
      renderView();
    });

    const codeInput = screen.getByLabelText("종목코드");
    // 069500 입력 → debounce(350ms) 후 조회 시작.
    await act(async () => {
      fireEvent.change(codeInput, { target: { value: "069500" } });
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 400));
    });
    // 조회 도중 코드를 139260 으로 변경 → 새 조회.
    await act(async () => {
      fireEvent.change(codeInput, { target: { value: "139260" } });
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 400));
    });
    // 이제 069500 의 늦은 응답 도착.
    await act(async () => {
      d1.resolve({ ticker: "069500", found: true, name: "KODEX 200" });
      await Promise.resolve();
    });

    // 현재 코드는 139260 이므로 069500 의 이름이 적용되면 안 된다.
    expect(screen.queryByDisplayValue("KODEX 200")).not.toBeInTheDocument();
    expect(screen.getByDisplayValue("TIGER 200 IT")).toBeInTheDocument();
  });
});

// ─── #2 기존 사용자 정의 계좌 표시값 = 저장값 ─────────────────────

describe("#2 추천 목록 밖 기존 계좌를 '일반'으로 위장하지 않는다", () => {
  it("기존 커스텀 계좌가 select 에 실제 값으로 표시되고, 미변경 저장 시 그대로 전송된다", async () => {
    fetchHoldings.mockResolvedValue({
      holdings: [
        {
          ticker: "069500",
          name: "KODEX 200",
          quantity: 3,
          avg_buy_price: 100,
          account_group: "키움-일반", // 추천 목록 밖 기존 값
        },
      ],
    });
    fetchEtfName.mockResolvedValue({ ticker: "069500", found: true, name: "KODEX 200" });
    saveHoldings.mockImplementation((payload: { holdings: unknown[] }) =>
      Promise.resolve(payload)
    );

    await act(async () => {
      renderView();
    });

    // select 표시값이 "일반"이 아니라 실제 저장값이어야 한다.
    const acctSelect = screen.getByLabelText("계좌") as HTMLSelectElement;
    await waitFor(() => expect(acctSelect.value).toBe("키움-일반"));

    // 계좌를 건드리지 않고 저장 → payload 의 account_group 이 화면 표시값과 일치.
    const saveBtn = screen.getByRole("button", { name: "보유 종목 저장" });
    await act(async () => {
      fireEvent.click(saveBtn);
    });
    await waitFor(() => expect(saveHoldings).toHaveBeenCalled());
    const sent = saveHoldings.mock.calls[0][0] as {
      holdings: Array<{ account_group?: string }>;
    };
    expect(sent.holdings[0].account_group).toBe("키움-일반");
  });
});
