// POC5-05 개정 2 — 과거 보유(접힌 목록) test(설계 §2 · PLAN §2-8).
// 자료 = 실제 백엔드 History 출력(historyFixtures). 이 목록은 API 를 부르지 않는다.
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";

import ClosedHoldings from "./ClosedHoldings";
import { HISTORY } from "./historyFixtures";

const KODEX = HISTORY.positions[0];
const TIGER = HISTORY.positions[1]; // 잔고 등록 → 입력 정정으로 종료
const HYNIX = HISTORY.positions[2]; // 잔고 등록 → 전량매도
// 실제 매수로 시작해 전량매도로 끝난 과거 보유(KODEX 의 지난 기간만 남긴 경우).
const KODEX_PAST = { ...KODEX, is_open: false, cycles: [KODEX.cycles[0]] };

function rowOf(label: string): HTMLElement {
  return screen.getByRole("button", { name: `${label} History` }).closest("tr") as HTMLElement;
}

describe("ClosedHoldings", () => {
  it("0건이면 아무것도 그리지 않는다", () => {
    const { container } = render(<ClosedHoldings positions={[]} onHistory={vi.fn()} onRebuy={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it("목록: 접힌 카드 · 종목(이름 + 코드) · 계좌 · 마지막 기간 · 실현손익 · 수익률 · 안내", () => {
    const { container } = render(
      <ClosedHoldings positions={[TIGER, HYNIX, KODEX_PAST]} onHistory={vi.fn()} onRebuy={vi.fn()} />,
    );
    const details = container.querySelector("details.card.hmx-closed");
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute("open");
    expect(screen.getByText("과거 보유 (3) — 보유가 끝난 종목")).toBeInTheDocument();

    const hynix = rowOf("SK하이닉스 · 연금");
    expect(within(hynix).getByText("000660")).toBeInTheDocument();
    expect(within(hynix).getByText("연금")).toBeInTheDocument();
    expect(within(hynix).getByText("매수일 미상 ~ 2026-09-30")).toBeInTheDocument();
    expect(within(hynix).getByText("+186,000")).toHaveClass("pnl-pos");
    expect(within(hynix).getByText("+12.4%")).toHaveClass("pnl-pos");

    const kodex = rowOf("KODEX 200 · ISA");
    expect(within(kodex).getByText("2026-03-02 ~ 2026-05-20")).toBeInTheDocument();
    expect(within(kodex).getByText("+8,000")).toBeInTheDocument();
    expect(within(kodex).getByText("+5%")).toBeInTheDocument();

    const tiger = rowOf("TIGER 2차전지테마 · 일반");
    expect(within(tiger).getByText("매수일 미상 ~ 2026-10-08")).toBeInTheDocument();
    expect(within(tiger).getByText("0")).toBeInTheDocument(); // 입력 정정 종료 = 실현손익 없음
    expect(within(tiger).getByText("—")).toBeInTheDocument(); // 수익률 대상 아님

    expect(
      screen.getByText(
        "과거 보유는 정기 시세 수집 · 알림 대상에 넣지 않습니다. 시장 흐름은 History 에서 직접 누를 때만 계산합니다.",
      ),
    ).toBeInTheDocument();
  });

  it("[History] → onHistory(position_id) · [재매수] → onRebuy(그 position)", () => {
    const onHistory = vi.fn();
    const onRebuy = vi.fn();
    render(<ClosedHoldings positions={[TIGER, HYNIX]} onHistory={onHistory} onRebuy={onRebuy} />);
    fireEvent.click(screen.getByRole("button", { name: "SK하이닉스 · 연금 History" }));
    expect(onHistory).toHaveBeenCalledTimes(1);
    expect(onHistory).toHaveBeenCalledWith(HYNIX.position_id);
    fireEvent.click(screen.getByRole("button", { name: "TIGER 2차전지테마 · 일반 재매수" }));
    expect(onRebuy).toHaveBeenCalledTimes(1);
    expect(onRebuy).toHaveBeenCalledWith(TIGER);
  });
});
