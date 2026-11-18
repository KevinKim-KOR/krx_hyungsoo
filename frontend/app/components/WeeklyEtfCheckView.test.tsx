// POC6-32 V2(PLAN 판정 V2 Q1 (a) · PLAN §2 S1 · S3 · S4 · §3-1 R5 · §9 I-5) — 「오늘 확인 › 주간 ETF 점검」 화면.
// - 제목 · [다시 읽기] · 열 때 주간 자료를 새로 읽음(GET /weekly/etf-check · 고정 응답 = lib/weeklyReviewTestFixtures).
// - 관통(실제 MainPanel · 사이드바 · 주간 화면): ③ [비교 상세 →] · [구성종목 보기 →]로 상세를 열었다가 [← 보낸 화면으로]로
//   돌아오면 고른 후보 · 같은 응답 그대로(다시 읽지 않음) · 메뉴로 다시 열면 새로 읽음(고른 것 없음).
// 오늘 화면 · 두 상세 화면은 이동만 보려고 가짜 화면으로 바꾼다(실제 네트워크 · 운영 자료 미의존) — 넘긴 값은 그 화면이 읽는
// 한 번 넘김 함수로 가짜 화면 안에서 꺼내 보인다.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import { weeklyFor } from "@/lib/weeklyReviewTestFixtures";

const fetchWeeklyReview = vi.fn();
vi.mock("@/lib/api/weeklyReview", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  fetchWeeklyReview: (...a: unknown[]) => fetchWeeklyReview(...a),
}));
vi.mock("./TodayInvestmentCheckView", () => ({ default: () => <h1>오늘의 투자 점검</h1> }));
vi.mock("./HoldingCandidateCompareView", async () => {
  const R = await import("react");
  const { takePresetCandidate } = await import("./workbench/compareSelection");
  function Fake() {
    const [p] = R.useState(() => takePresetCandidate());
    return (
      <>
        <h1>보유와 후보 비교</h1>
        <p data-testid="fake-compare">{p ? `${p.origin} · ${p.ticker}` : "넘긴 후보 없음"}</p>
      </>
    );
  }
  return { default: Fake };
});
vi.mock("./ETFExposureView", async () => {
  const R = await import("react");
  const { takeExposureSingle } = await import("@/lib/detailNav");
  function Fake() {
    const [p] = R.useState(() => takeExposureSingle());
    return (
      <>
        <h1>ETF 구성종목</h1>
        <p data-testid="fake-exposure">{p ? `${p.from} · ${p.ticker}` : "넘긴 ETF 없음"}</p>
      </>
    );
  }
  return { default: Fake };
});

import WeeklyEtfCheckView from "./WeeklyEtfCheckView";
import MainPanel from "./MainPanel";

beforeEach(() => {
  __resetQueryCache();
  vi.clearAllMocks();
  fetchWeeklyReview.mockImplementation(async (sel: string | null) => weeklyFor(sel));
});

const head = () => screen.getByTestId("wr-review");
const PICKED = "KODEX 글로벌비만치료제TOP2 Plus(476070) · 1개월 상위 2위";
const pickSecondRow = async () => {
  const rows = screen.getByTestId("wr-flows").querySelectorAll(":scope > .wr-table-wrap tbody tr[data-flow]");
  fireEvent.click(within(rows[1] as HTMLElement).getByRole("button", { name: /고르기/ }));
  await waitFor(() => expect(head()).toHaveTextContent(PICKED));
};

describe("「주간 ETF 점검」 화면 틀", () => {
  it("제목 한 개 · [다시 읽기](중간 버튼) · 열 때 주간 자료를 읽음 · [다시 읽기] = 한 번 더 읽음", async () => {
    render(<WeeklyEtfCheckView onNavigate={vi.fn()} />);
    expect(screen.getByRole("heading", { level: 1, name: "주간 ETF 점검" })).toBeInTheDocument();
    await screen.findByTestId("wr-flows");
    // 안쪽 본문에 예전 제목(ETF 주간 검토)이 겹쳐 있지 않다
    expect(screen.getAllByRole("heading")).toHaveLength(1);
    expect(screen.queryByText("ETF 주간 검토")).toBeNull();
    expect(fetchWeeklyReview).toHaveBeenCalledTimes(1);
    expect(fetchWeeklyReview).toHaveBeenCalledWith(null);
    const again = screen.getByRole("button", { name: "다시 읽기" });
    expect(again.className).toContain("btn-md");
    fireEvent.click(again);
    await waitFor(() => expect(fetchWeeklyReview).toHaveBeenCalledTimes(2));
  });

  it("다시 열면(새로 그림) 받아 둔 응답을 쓰지 않고 새로 읽는다", async () => {
    const first = render(<WeeklyEtfCheckView onNavigate={vi.fn()} />);
    await screen.findByTestId("wr-flows");
    first.unmount();
    render(<WeeklyEtfCheckView onNavigate={vi.fn()} />);
    await screen.findByTestId("wr-flows");
    expect(fetchWeeklyReview).toHaveBeenCalledTimes(2);
  });
});

describe("MainPanel 「주간 ETF 점검」 관통", () => {
  const sidebar = () => screen.getByRole("complementary", { name: "좌측 메뉴" });
  const menu = (label: string) => within(sidebar()).getByText(label).closest("button")!;

  it("[비교 상세 →] → 「보유와 후보 비교」(고른 후보 · 보낸 화면) → [← 보낸 화면으로] = 고른 후보 · 같은 응답 그대로 · 메뉴로 다시 열면 새로 읽음", async () => {
    render(<MainPanel />);
    fireEvent.click(menu("주간 ETF 점검"));
    expect(await screen.findByRole("heading", { level: 1, name: "주간 ETF 점검" })).toBeInTheDocument();
    await screen.findByTestId("wr-flows");
    await pickSecondRow();
    const calls = fetchWeeklyReview.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: "비교 상세 →" }));
    expect(screen.getByRole("heading", { level: 1, name: "보유와 후보 비교" })).toBeInTheDocument();
    expect(screen.getByTestId("fake-compare")).toHaveTextContent("「주간 ETF 점검」 · 476070");
    expect(screen.queryByRole("heading", { level: 1, name: "주간 ETF 점검" })).toBeNull();
    expect(screen.getByTestId("dn-back")).toHaveTextContent("보낸 화면 「주간 ETF 점검」");

    fireEvent.click(screen.getByRole("button", { name: "← 보낸 화면으로" }));
    expect(screen.getByRole("heading", { level: 1, name: "주간 ETF 점검" })).toBeInTheDocument();
    expect(head()).toHaveTextContent(PICKED);
    expect(fetchWeeklyReview.mock.calls.length).toBe(calls);

    fireEvent.click(menu("오늘의 투자 점검"));
    fireEvent.click(menu("주간 ETF 점검"));
    await screen.findByTestId("wr-flows");
    expect(fetchWeeklyReview.mock.calls.length).toBe(calls + 1);
    expect(fetchWeeklyReview).toHaveBeenLastCalledWith(null);
    expect(head()).not.toHaveTextContent(PICKED);
  });

  it("[구성종목 보기 →] → 「ETF 구성종목」 이 ETF 하나(보낸 화면) → [← 보낸 화면으로] = 고른 후보 그대로", async () => {
    render(<MainPanel />);
    fireEvent.click(menu("주간 ETF 점검"));
    await screen.findByTestId("wr-flows");
    await pickSecondRow();
    const calls = fetchWeeklyReview.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "구성종목 보기 →" }));
    expect(screen.getByRole("heading", { level: 1, name: "ETF 구성종목" })).toBeInTheDocument();
    expect(screen.getByTestId("fake-exposure")).toHaveTextContent("「주간 ETF 점검」 · 476070");
    fireEvent.click(screen.getByRole("button", { name: "← 보낸 화면으로" }));
    expect(head()).toHaveTextContent(PICKED);
    expect(fetchWeeklyReview.mock.calls.length).toBe(calls);
  });
});
