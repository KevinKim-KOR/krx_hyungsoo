// POC5-25 — 「요즘 잘 오르는 ETF」 표 칸 · 목록 위 기간 상자 셋째 줄('20저장일 종가 고점 대비').
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import type { MarketCandidate } from "@/lib/api";
import CandidateTable from "./CandidateTable";

function cand(tk: string, rank: number, sd: Record<string, unknown> | null, old: number): MarketCandidate {
  return {
    rank,
    ticker: tk,
    name: `${tk} ETF`,
    returns: { one_month: { return_pct: 1, price_start_date: "2026-09-14", price_end_date: "2026-10-14" } },
    drawdown_20d: old,
    stored_drawdown_20: sd,
    data_quality: { status: "ok" },
  } as unknown as MarketCandidate;
}
const OK = {
  status: "ok",
  value_pct: -13.8354,
  start_date: "2026-09-16",
  end_date: "2026-10-14",
  peak_close: 28550,
  peak_date: "2026-10-06",
  close: 24600,
  rows: 20,
};

describe("표 칸 · 기간 줄 (POC5-25)", () => {
  it("칸 이름 · 새 값 · 값 아래 고점 날짜 · 값 없음은 사유 · 옛 값은 보이지 않는다", () => {
    const { container } = render(
      <CandidateTable
        candidates={[
          cand("475300", 1, OK, -0.9),
          cand("0239Z0", 2, { status: "unavailable", reason: "insufficient_history", rows: 18 }, -0.04),
        ]}
        basis="one_month"
        order="desc"
        onSort={() => {}}
      />,
    );
    const th = Array.from(container.querySelectorAll("th")).map((e) => e.textContent);
    expect(th).toContain("20저장일 종가 고점 대비");
    expect(th).not.toContain("고점 대비");
    const rows = container.querySelectorAll("tbody tr");
    const last = (r: Element) => r.querySelectorAll("td")[r.querySelectorAll("td").length - 1];
    expect(last(rows[0]).textContent).toBe("-13.84%고점 2026-10-06");
    expect(last(rows[1]).textContent).toBe("저장 종가 20개 미만");
    expect(container.textContent).not.toContain("-90.00%");
    expect(container.textContent).not.toContain("-4.00%");
  });

  it("기간 상자 셋째 줄 = 공통 기간 · 값 없음 수 · ? 에 뜻과 한계", () => {
    render(
      <CandidateTable
        candidates={[cand("475300", 1, OK, -0.9), cand("0239Z0", 2, { status: "unavailable", reason: "insufficient_history" }, 0)]}
        basis="one_month"
        order="desc"
        onSort={() => {}}
      />,
    );
    const box = screen.getByTestId("return-period-line");
    expect(box.textContent).toContain(
      "20저장일 종가 고점 대비2026-09-16 ~ 2026-10-14 저장 종가 20개 · 표시 후보 1개 모두 같음 · 값 없음 1개",
    );
    fireEvent.click(within(box).getByRole("button", { name: "20저장일 종가 고점 대비 도움말" }));
    expect(box.textContent).toContain("기간 중 최대 낙폭(MDD)");
    expect(box.textContent).toContain("2026-08-27 점수 스냅샷 값");
  });
});
