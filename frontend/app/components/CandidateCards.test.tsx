// 요즘 잘 오르는 ETF — 후보 카드 계약 test (2026-08-16 신규).
// 이 화면은 원래 테스트가 없었다. 카드 전환으로 새로 생긴 표시 계약만 고정한다.
// - 17열을 버리지 않는다: 카드에 없는 항목은 펼침 상세에 있다.
// - 보유 여부 3-state (미보유와 "확인 불가" 를 구분).
// - 데이터 상태는 정상이면 배지를 띄우지 않는다.
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import CandidateCards from "./CandidateCards";
import type { MarketCandidate } from "@/lib/api";

function cand(over: Partial<MarketCandidate> = {}): MarketCandidate {
  return {
    rank: 1,
    ticker: "069500",
    name: "KODEX 200",
    returns: {
      daily: { return_pct: 0.52 },
      one_month: { return_pct: 6.01 },
      three_month: { return_pct: -13.82 },
      six_month: { return_pct: 4.1 },
      twelve_month: { return_pct: 11.2 },
      three_year: { return_pct: 38.4 },
    },
    excess_return: { vs_kodex200_1m_pctp: 11.91, vs_kodex200_3m_pctp: -2.3 },
    relative_upside_score: 72.3,
    relative_upside_reasons: ["1M 상위", "거래대금 충분"],
    drawdown_20d: -0.042,
    data_quality: {
      status: "ok",
      nav_discount: { nav: 10919, market_price: 10935, discount_rate_pct: 0.15 },
    },
    ...over,
  } as MarketCandidate;
}

describe("후보 카드 (요즘 잘 오르는 ETF)", () => {
  it("카드에 티커·시장가·NAV·괴리율과 참고점수·기간 지표가 나온다", () => {
    render(<CandidateCards candidates={[cand()]} heldTickers={new Set()} />);
    const list = screen.getByTestId("candidate-card-list");
    expect(within(list).getByText("069500")).toBeInTheDocument();
    expect(within(list).getByText("10,935")).toBeInTheDocument(); // 시장가
    expect(within(list).getByText("10,919")).toBeInTheDocument(); // NAV
    expect(within(list).getByText("+0.15%")).toBeInTheDocument(); // 괴리율
    expect(within(list).getByText("72.3")).toBeInTheDocument(); // 참고점수
    expect(within(list).getByText("+11.91%")).toBeInTheDocument(); // KODEX200 대비 1M
  });

  it("카드에 없는 항목은 펼쳐야 보인다 (열을 버리지 않는다)", () => {
    render(<CandidateCards candidates={[cand()]} heldTickers={new Set()} />);
    // 접힘 상태 — 6개월·3년·KODEX200 대비 3M·고점 대비·점수 근거 없음.
    expect(screen.queryByText("6개월")).not.toBeInTheDocument();
    expect(screen.queryByText("KODEX200 대비 3M")).not.toBeInTheDocument();
    expect(screen.queryByText(/거래대금 충분/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /KODEX 200 상세 보기/ }));

    expect(screen.getByText("6개월")).toBeInTheDocument();
    expect(screen.getByText("12개월")).toBeInTheDocument();
    expect(screen.getByText("3년")).toBeInTheDocument();
    expect(screen.getByText("KODEX200 대비 3M")).toBeInTheDocument();
    expect(screen.getByText("고점 대비")).toBeInTheDocument();
    expect(screen.getByText(/거래대금 충분/)).toBeInTheDocument();
  });

  it("보유 여부는 3-state — 미보유와 '확인 불가' 를 구분한다", () => {
    // 보유 목록 로드됨 + 미보유.
    const { unmount } = render(
      <CandidateCards candidates={[cand()]} heldTickers={new Set()} />,
    );
    expect(screen.getByText("미보유")).toBeInTheDocument();
    unmount();

    // 보유 목록 로드됨 + 보유.
    const r2 = render(
      <CandidateCards candidates={[cand()]} heldTickers={new Set(["069500"])} />,
    );
    expect(screen.getByText("보유")).toBeInTheDocument();
    r2.unmount();

    // 보유 목록 미로드 → "미보유" 로 축약하지 않는다.
    render(<CandidateCards candidates={[cand()]} />);
    expect(screen.getByText("보유 확인 불가")).toBeInTheDocument();
    expect(screen.queryByText("미보유")).not.toBeInTheDocument();
  });

  it("데이터 상태는 정상이면 배지를 띄우지 않고 이상일 때만 띄운다", () => {
    const { unmount } = render(
      <CandidateCards candidates={[cand()]} heldTickers={new Set()} />,
    );
    expect(screen.queryByText(/데이터/)).not.toBeInTheDocument();
    unmount();

    render(
      <CandidateCards
        candidates={[
          cand({
            data_quality: { status: "warning" } as MarketCandidate["data_quality"],
          }),
        ]}
        heldTickers={new Set()}
      />,
    );
    expect(screen.getByText(/데이터 warning/)).toBeInTheDocument();
  });

  it("행을 선택하면 onSelect 로 ticker 를 알린다", () => {
    const onSelect = vi.fn();
    render(
      <CandidateCards
        candidates={[cand()]}
        heldTickers={new Set()}
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /KODEX 200 상세 보기/ }));
    expect(onSelect).toHaveBeenCalledWith("069500");
  });

  it("후보가 없으면 빈 상태 문구를 보여준다", () => {
    render(<CandidateCards candidates={[]} />);
    expect(screen.getByText("표시할 후보가 없습니다.")).toBeInTheDocument();
  });
});
