// POC6-32 V2(PLAN S5 · 판정 Q9 (a) 보완 · Q11 (d)) — 「후보리스트」 · 「섹터요약」 행 상세의 상세 이동 버튼 두 개.
// [비교 상세 →] = 「보유와 후보 비교」 후보 칸에 이 ETF 한쪽(이 화면 조건 · 공통 기간은 이번 이동에만) ·
// [구성종목 보기 →] = 「ETF 구성종목」 한 ETF 모드(이 ETF 하나 · 보낸 화면 · 목록 조건).
// 차트 · 상세 수치 · 판단 근거 미리보기는 이 시험과 무관해 빈 자리로 바꾼다(조회 없음 · 고정 자료 가상 종목).
import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

vi.mock("./PriceChart", () => ({ default: () => null }));
vi.mock("./DetailNumbers", () => ({
  DetailLines: () => null,
  detailOf: () => null,
  detailStateText: () => "읽는 중",
  useEtfDetail: () => ({ phase: "loading" }),
}));
vi.mock("../holdings_compare/DecisionDraftPreviewCard", () => ({ default: () => <div>미리보기 자리</div> }));

import EtfRowDetail, { ROW_DETAIL_ORIGIN } from "./EtfRowDetail";
import { takePresetCandidate } from "./compareSelection";
import { takeExposureSingle } from "@/lib/detailNav";
import { __resetEtfCompareCondition, getScreenCondition, takeOneTimeCondition } from "@/lib/etfCompareCondition";
import { summaryOk } from "@/lib/etfCompareTestFixtures";

beforeEach(() => {
  __resetEtfCompareCondition();
  takePresetCandidate();
  takeExposureSingle();
});

const s = summaryOk({ basis: "three_month" });
const row = s.top[0];

describe("행 상세 → 상세 화면(PLAN S5)", () => {
  it("[비교 상세 →] = 후보 칸에 이 ETF · 이 화면 조건 · 공통 기간 시작 · 끝 · 보낸 화면 이름 · 이동 한 번 조건", () => {
    const nav = vi.fn();
    const before = getScreenCondition("compare");
    render(<EtfRowDetail row={row} s={s} side="top" screen="candidate_list" onNavigate={nav} />);
    const go = screen.getByTestId("ec-detail-go");
    const btn = within(go).getByRole("button", { name: "비교 상세 →" });
    expect(btn.className).toBe("wb-btn btn-md");
    fireEvent.click(btn);
    expect(nav).toHaveBeenCalledTimes(1);
    expect(nav).toHaveBeenCalledWith("holding_candidate_compare");
    expect(takePresetCandidate()).toEqual({
      ticker: row.ticker,
      name: row.name,
      side: "top",
      condition: { basis: "three_month", filters: { ...s.filters } },
      start: s.period.start,
      end: s.end_date,
      origin: "「후보리스트」",
    });
    expect(takeOneTimeCondition("compare")?.cond).toEqual({ basis: "three_month", filters: { ...s.filters } });
    expect(getScreenCondition("compare")).toBe(before); // 받는 화면 조건 메모리는 그대로(이번 이동에만)
    expect(takeExposureSingle()).toBeNull(); // 다른 넘김은 건드리지 않음
  });

  it("[구성종목 보기 →] = 「ETF 구성종목」 한 ETF 모드(이 ETF 하나 · 「섹터요약」 · 목록 조건)", () => {
    const nav = vi.fn();
    const r = s.bottom[0];
    render(<EtfRowDetail row={r} s={s} side="bottom" screen="sector_summary" onNavigate={nav} />);
    const btn = within(screen.getByTestId("ec-detail-go")).getByRole("button", { name: "구성종목 보기 →" });
    expect(btn.className).toBe("wb-btn btn-md");
    fireEvent.click(btn);
    expect(nav).toHaveBeenCalledWith("etf_exposure");
    expect(takeExposureSingle()).toEqual({
      ticker: r.ticker,
      name: r.name,
      from: "「섹터요약」",
      condition: { basis: "three_month", side: "bottom", start: s.period.start, end: s.end_date, filters: { ...s.filters } },
    });
    expect(takePresetCandidate()).toBeNull();
    expect(takeOneTimeCondition("compare")).toBeNull();
  });

  it("이동할 수 없으면(onNavigate 없음) 버튼 줄을 그리지 않는다 · 보낸 화면 이름 표", () => {
    render(<EtfRowDetail row={row} s={s} side="top" screen="candidate_list" />);
    expect(screen.queryByTestId("ec-detail-go")).toBeNull();
    expect(ROW_DETAIL_ORIGIN.candidate_list).toBe("「후보리스트」");
    expect(ROW_DETAIL_ORIGIN.sector_summary).toBe("「섹터요약」");
  });
});
