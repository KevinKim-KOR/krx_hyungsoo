// POC3-08 재작업(검증자 지적) — 종목 관리 화면 실제 비동기·정합 계약 test.
//   #1 비동기 종목명 조회와 정렬·삭제의 index 경합(uid 기반으로 해소).
//   #2 기존 사용자 정의 계좌의 표시값 = 저장값 정합(위장 금지).
// POC5-05 개정 2: 편집 표는 '입력 정정' 모드 — 위 계약은 그 모드에서 그대로 유지된다.
//   #3 기본 보유 표 · 빈 보유 상태 · 입력 정정 저장(revision · 줄 ID · 저장 동작 ID) · OCI 미적용 표시.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, fireEvent, waitFor } from "@testing-library/react";

const fetchHoldings = vi.fn();
const saveHoldings = vi.fn();
const fetchEtfName = vi.fn();
const fetchHoldingsApplyStatus = vi.fn();
const applyHoldingsToOci = vi.fn();
const fetchTradeHistory = vi.fn();
const fetchEnrichedHoldings = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchHoldings: (...a: unknown[]) => fetchHoldings(...a),
    saveHoldings: (...a: unknown[]) => saveHoldings(...a),
    fetchEtfName: (...a: unknown[]) => fetchEtfName(...a),
    fetchHoldingsApplyStatus: (...a: unknown[]) => fetchHoldingsApplyStatus(...a),
    applyHoldingsToOci: (...a: unknown[]) => applyHoldingsToOci(...a),
    fetchTradeHistory: (...a: unknown[]) => fetchTradeHistory(...a),
    fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
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
  fetchHoldingsApplyStatus.mockResolvedValue({ has_record: false, pending_apply: null });
  fetchTradeHistory.mockReset();
  fetchTradeHistory.mockResolvedValue({ status: "V2", revision: 1, positions: [] });
  fetchEnrichedHoldings.mockReset();
  fetchEnrichedHoldings.mockResolvedValue({ items: [] });
  // 기본: 종목명 조회는 '목록에 없음'(각 테스트가 필요하면 덮어쓴다 · 처리 안 된 오류 방지).
  fetchEtfName.mockResolvedValue({ ticker: "", found: false, name: null });
});

function renderView() {
  return render(<HoldingsManageView onNavigate={() => {}} />);
}

// POC5-05: 응답에 revision · status · 줄 ID 가 더해졌다.
function state(holdings: Array<Record<string, unknown>>, status = "OK", revision = 1) {
  return {
    holdings: holdings.map((h, i) => ({ position_id: `p${i}`, cycle_id: `c${i}`, ...h })),
    revision,
    status: holdings.length ? status : status === "OK" ? "EMPTY" : status,
  };
}

async function enterEditMode() {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "입력 정정" }));
  });
}

// ─── #1 비동기 조회 ↔ 정렬/삭제 경합 ──────────────────────────────

describe("#1 비동기 종목명 조회가 정렬·삭제 후 엉뚱한 행을 안 건드린다", () => {
  it("조회 진행 중 행이 삭제되면 늦게 온 응답은 어떤 행에도 적용되지 않는다", async () => {
    // 두 행 로드: A(069500), B(139260). A 는 조회를 지연(deferred)시킨다.
    fetchHoldings.mockResolvedValue(
      state([
        { ticker: "069500", name: "", quantity: 1, avg_buy_price: 100, account_group: "일반" },
        { ticker: "139260", name: "", quantity: 1, avg_buy_price: 100, account_group: "일반" },
      ]),
    );
    const dA = deferred<{ ticker: string; found: boolean; name: string | null }>();
    fetchEtfName.mockImplementation((t: string) => {
      if (t === "069500") return dA.promise; // A 지연
      return Promise.resolve({ ticker: t, found: true, name: "TIGER 200 IT" });
    });

    await act(async () => {
      renderView();
    });
    await enterEditMode();

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
    fetchHoldings.mockResolvedValue(state([], "NO_FILE", 0)); // 빈 시작 → 행 추가
    const d1 = deferred<{ ticker: string; found: boolean; name: string | null }>();
    fetchEtfName.mockImplementation((t: string) => {
      if (t === "069500") return d1.promise;
      return Promise.resolve({ ticker: t, found: true, name: "TIGER 200 IT" });
    });

    await act(async () => {
      renderView();
    });
    await enterEditMode();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "행 추가" }));
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
    fetchHoldings.mockResolvedValue(
      state([
        {
          ticker: "069500",
          name: "KODEX 200",
          quantity: 3,
          avg_buy_price: 100,
          account_group: "키움-일반", // 추천 목록 밖 기존 값
        },
      ]),
    );
    fetchEtfName.mockResolvedValue({ ticker: "069500", found: true, name: "KODEX 200" });
    saveHoldings.mockImplementation((payload: { holdings: unknown[] }) =>
      Promise.resolve({ ...payload, revision: 2, status: "OK" })
    );

    await act(async () => {
      renderView();
    });
    await enterEditMode();

    // select 표시값이 "일반"이 아니라 실제 저장값이어야 한다.
    const acctSelect = screen.getByLabelText("계좌") as HTMLSelectElement;
    await waitFor(() => expect(acctSelect.value).toBe("키움-일반"));

    // 계좌를 건드리지 않고 저장 → payload 의 account_group 이 화면 표시값과 일치.
    const saveBtn = screen.getByRole("button", { name: "입력 정정 저장" });
    await act(async () => {
      fireEvent.click(saveBtn);
    });
    await waitFor(() => expect(saveHoldings).toHaveBeenCalled());
    const sent = saveHoldings.mock.calls[0][0] as {
      holdings: Array<{ account_group?: string; position_id?: string }>;
      revision: number;
      request_id: string;
    };
    expect(sent.holdings[0].account_group).toBe("키움-일반");
    // POC5-05: 읽은 revision · 줄 ID · 저장 동작 ID 를 함께 보낸다.
    expect(sent.revision).toBe(1);
    expect(sent.holdings[0].position_id).toBe("p0");
    expect(sent.request_id).toMatch(/^[0-9a-f-]{36}$/);
  });
});

// ─── #3 POC5-05 개정 2: 보유 표 · 빈 보유 · 입력 정정 저장 · OCI 미적용 ──────────

describe("#3 보유 표와 입력 정정 모드", () => {
  it("기본은 읽기 표시 보유 표이고 입력칸이 없다 · 수익률은 보유 현황 값", async () => {
    fetchHoldings.mockResolvedValue(
      state([{ ticker: "069500", name: "KODEX 200", quantity: 9, avg_buy_price: 10666.67, account_group: "ISA" }]),
    );
    fetchEnrichedHoldings.mockResolvedValue({ items: [{ source_index: 0, pnl_rate_pct: -2.03 }] });
    await act(async () => {
      renderView();
    });
    expect(screen.queryByLabelText("종목코드")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "매매" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "History" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("-2.03%")).toBeInTheDocument());
  });

  it("정상 빈 보유 · 파일 없음은 빈 입력 행 대신 상태 문구를 보인다", async () => {
    fetchHoldings.mockResolvedValue(state([], "OK", 3));
    await act(async () => {
      renderView();
    });
    expect(screen.getByText(/현재 보유 없음\(전량매도\)/)).toBeInTheDocument();
    expect(screen.queryByLabelText("종목코드")).not.toBeInTheDocument();
  });

  it("입력 정정에서 마지막 줄도 지울 수 있고, 실패 뒤 같은 내용 재시도는 같은 저장 ID", async () => {
    fetchHoldings.mockResolvedValue(
      state([{ ticker: "069500", name: "KODEX 200", quantity: 1, avg_buy_price: 100, account_group: "일반" }]),
    );
    fetchEtfName.mockResolvedValue({ ticker: "069500", found: true, name: "KODEX 200" });
    saveHoldings.mockRejectedValueOnce(new Error("network"));
    saveHoldings.mockResolvedValue({ holdings: [], revision: 2, status: "EMPTY" });
    await act(async () => {
      renderView();
    });
    await enterEditMode();
    const del = screen.getByRole("button", { name: "이 행 삭제" });
    expect(del).not.toBeDisabled();
    await act(async () => {
      fireEvent.click(del);
    });
    const save = screen.getByRole("button", { name: "입력 정정 저장" });
    await act(async () => {
      fireEvent.click(save);
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "입력 정정 저장" }));
    });
    await waitFor(() => expect(saveHoldings).toHaveBeenCalledTimes(2));
    const [first, second] = saveHoldings.mock.calls.map((c) => c[0] as { holdings: unknown[]; request_id: string });
    expect(first.holdings).toEqual([]);
    expect(second.request_id).toBe(first.request_id);
    // 성공하면 정정 모드를 닫고 다시 읽는다.
    await waitFor(() => expect(fetchHoldings).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("button", { name: "입력 정정 저장" })).not.toBeInTheDocument();
  });

  it("입력 정정: 지수 표기로 읽히는 기존 값(1e-7 · 1e21)을 건드리지 않고 저장하면 같은 값을 보낸다", async () => {
    fetchHoldings.mockResolvedValue(
      state([
        { ticker: "069500", name: "KODEX 200", quantity: 1e-7, avg_buy_price: 1e21, account_group: "일반" },
        { ticker: "005930", name: "삼성전자", quantity: 1.5e-7, avg_buy_price: 2.5e22, account_group: "일반" },
      ]),
    );
    fetchEtfName.mockResolvedValue({ ticker: "069500", found: true, name: "KODEX 200" });
    saveHoldings.mockImplementation((payload: { holdings: unknown[] }) =>
      Promise.resolve({ ...payload, revision: 2, status: "OK" }),
    );
    await act(async () => {
      renderView();
    });
    await enterEditMode();
    // 칸에는 지수 표기 대신 같은 값의 십진 표기('e' 가 지워져 1e-7 → "17" 이 되지 않는다).
    const qty = screen.getAllByLabelText("수량") as HTMLInputElement[];
    expect(qty.map((q) => q.value).sort()).toEqual(["0.0000001", "0.00000015"]);
    const avg = screen.getAllByLabelText("매입단가") as HTMLInputElement[];
    expect(avg.map((a) => a.value)).toContain("1,000,000,000,000,000,000,000");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "입력 정정 저장" }));
    });
    await waitFor(() => expect(saveHoldings).toHaveBeenCalled());
    const sent = saveHoldings.mock.calls[0][0] as {
      holdings: Array<{ ticker: string; quantity: number; avg_buy_price: number }>;
    };
    expect(Object.fromEntries(sent.holdings.map((h) => [h.ticker, [h.quantity, h.avg_buy_price]]))).toEqual({
      "069500": [1e-7, 1e21],
      "005930": [1.5e-7, 2.5e22],
    });
  });

  it("OCI 적용 카드: 미적용 · 확인 안 됨 표시", async () => {
    fetchHoldings.mockResolvedValue(state([], "NO_FILE", 0));
    fetchHoldingsApplyStatus.mockResolvedValue({ has_record: true, status: "OCI_APPLIED", applied_at: "2026-10-08T09:12:00+09:00", pending_apply: true });
    await act(async () => {
      renderView();
    });
    await waitFor(() => expect(screen.getByText("PC 보유 변경 있음 · 아직 OCI 미적용")).toBeInTheDocument());
  });

  it("OCI 적용 카드: 적용된 보유와 같으면 초록 표시(경고색 아님)", async () => {
    fetchHoldings.mockResolvedValue(state([], "NO_FILE", 0));
    fetchHoldingsApplyStatus.mockResolvedValue({ has_record: true, status: "OCI_APPLIED", applied_at: "2026-10-09T07:34:43+09:00", pending_apply: false });
    await act(async () => {
      renderView();
    });
    const same = await screen.findByText("OCI 에 적용된 보유와 같음");
    expect(same).toHaveClass("hmx-tag", "hmx-tag-ok");
    expect(same).not.toHaveClass("hmx-tag-warn");
  });
});
