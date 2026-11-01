// POC6-14 — 「전향 ML 비교 · 연구」 카드 시험(가짜 응답 · 서버 · 연구 폴더 없음).
//
// - 기본 노출: 네 예측 · 결과 상태가 펼치지 않아도 보임 · 연구용 꼬리표.
// - 행을 누르면 그 행 바로 아래에 상세 · [복사] = 화면에 그린 응답에서 만든 문장(클릭 때 조회 없음).
// - 기준일 바꾸기 중 늦게 온 이전 응답은 버림. 상태별(없음 · 실패 · 보고 대기 · 보고 손상) 문구.
import { StrictMode } from "react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within, act } from "@testing-library/react";
import type { ForwardComparisonResponse } from "@/lib/api";
import { DATA, ROW } from "./testFixtures";
import { cardNotices, copyText, reportNotices } from "./forwardText";

const fetchForwardComparison = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return { ...actual, fetchForwardComparison: (...a: unknown[]) => fetchForwardComparison(...a) };
});

import ForwardComparisonCard from "./ForwardComparisonCard";
import { ApiRequestError } from "@/lib/api";

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

beforeEach(() => {
  fetchForwardComparison.mockReset();
});

describe("ForwardComparisonCard", () => {
  it("기본 화면 — 네 예측 · 상태 · 연구용 · 보고 있음(펼치지 않아도)", async () => {
    fetchForwardComparison.mockResolvedValue(DATA);
    render(<ForwardComparisonCard />);
    expect(await screen.findByText("-3.06%")).toBeInTheDocument();
    expect(fetchForwardComparison).toHaveBeenCalledWith(undefined);
    expect(screen.getByText("0.00%")).toBeInTheDocument(); // -0.0001 → 0.00%(부호 없음)
    expect(screen.getByText("환경 불일치")).toBeInTheDocument();
    expect(screen.getByText("재시도로 채움")).toBeInTheDocument();
    expect(screen.getByText("성숙 확인 전")).toBeInTheDocument();
    expect(screen.getAllByText("연구용 · 운영 미채택").length).toBeGreaterThan(0);
    expect(screen.getByText(/이 기준일 주 기록 없음 — 입력 상태 NO_EVIDENCE/)).toBeInTheDocument();
    expect(screen.getByText("보고 있음")).toBeInTheDocument();
    expect(screen.getAllByText("아직 비교할 결과 없음").length).toBeGreaterThan(0);
    expect(screen.queryByText("복사")).toBeNull(); // 상세는 닫혀 있음
  });

  it("행을 누르면 그 행 바로 아래 상세 · 복사 = 화면 응답 문장(조회 없음)", async () => {
    fetchForwardComparison.mockResolvedValue(DATA);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<ForwardComparisonCard />);
    const btn = await screen.findByRole("button", { name: "0015K0 상세" });
    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-expanded", "true");
    const rowTr = btn.closest("tr")!;
    const detailTr = rowTr.nextElementSibling as HTMLElement;
    expect(within(detailTr).getByText(/0015K0 TIGER 미국소비트렌드액티브 · 기준일 2026-10-29/)).toBeInTheDocument();
    expect(within(detailTr).getByText(/scikit-learn 1.9.0 → 1.9.1/)).toBeInTheDocument();
    const calls = fetchForwardComparison.mock.calls.length;
    fireEvent.click(within(detailTr).getByRole("button", { name: "복사" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(copyText(DATA, ROW)));
    expect(await within(detailTr).findByText("복사했습니다")).toBeInTheDocument();
    expect(fetchForwardComparison.mock.calls.length).toBe(calls);
  });

  it("복사 실패는 성공처럼 보이지 않음", async () => {
    fetchForwardComparison.mockResolvedValue(DATA);
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockRejectedValue(new Error("no")) } });
    render(<ForwardComparisonCard />);
    fireEvent.click(await screen.findByRole("button", { name: "0015K0 상세" }));
    fireEvent.click(screen.getByRole("button", { name: "복사" }));
    expect(await screen.findByText("복사하지 못했습니다")).toBeInTheDocument();
  });

  it("기준일을 바꾸면 그 D 로 다시 조회", async () => {
    fetchForwardComparison.mockResolvedValueOnce(DATA);
    render(<ForwardComparisonCard />);
    const select = await screen.findByRole("combobox");
    fetchForwardComparison.mockResolvedValueOnce({ ...DATA, selected_D: "2026-10-27" });
    fireEvent.change(select, { target: { value: "2026-10-27" } });
    expect(fetchForwardComparison).toHaveBeenLastCalledWith("2026-10-27");
    expect(await screen.findByRole("combobox")).toHaveValue("2026-10-27");
  });

  it("겹친 요청(개발 모드 첫 조회 두 번) — 늦게 온 이전 응답은 화면에 붙지 않음", async () => {
    const slow = deferred<ForwardComparisonResponse>();
    const fast = deferred<ForwardComparisonResponse>();
    fetchForwardComparison.mockReturnValueOnce(slow.promise).mockReturnValueOnce(fast.promise);
    render(
      <StrictMode>
        <ForwardComparisonCard />
      </StrictMode>,
    );
    expect(fetchForwardComparison).toHaveBeenCalledTimes(2);
    await act(async () => fast.resolve(DATA));
    await act(async () => slow.resolve({ ...DATA, selected_D: "2026-10-27" }));
    expect(await screen.findByRole("combobox")).toHaveValue("2026-10-29");
  });

  it("기록 없음 · 불러오기 실패 · 요청 오류를 구분", async () => {
    fetchForwardComparison.mockResolvedValueOnce({
      status: "NO_RECORDS",
      label: "연구용 · 운영 미채택",
      message: "공개 확인된 연구 기록이 없습니다",
      other: { unconfirmed_forward_records: 2, diagnostic_entries: 0, supplementary_entries: 0 },
    });
    const { unmount } = render(<ForwardComparisonCard />);
    expect(await screen.findByText(/공개 확인된 연구 기록 없음/)).toHaveTextContent("마감 뒤 확인 2개");
    unmount();
    fetchForwardComparison.mockResolvedValueOnce({ status: "CHECK_REQUIRED", label: "연구용 · 운영 미채택", message: "cohort 다름" });
    const r2 = render(<ForwardComparisonCard />);
    expect(await screen.findByText(/불러오기 실패 · 확인 필요 — cohort 다름/)).toBeInTheDocument();
    expect(screen.queryByText("-3.06%")).toBeNull();
    r2.unmount();
    fetchForwardComparison.mockRejectedValueOnce(new ApiRequestError("x", 404, null));
    render(<ForwardComparisonCard />);
    expect(await screen.findByText(/선택한 기준일 기록 없음/)).toBeInTheDocument();
  });

  it("보고 대기 · 회차 보고 손상 · 더 늦은 보고 손상", async () => {
    const wait = { ...DATA, report: { ...DATA.report!, selected_D: "RUN_REPORT_MISSING" as const } };
    fetchForwardComparison.mockResolvedValueOnce(wait);
    const a = render(<ForwardComparisonCard />);
    expect(await screen.findByText(/보고서 확인 대기 — 이 기준일을 기록한 회차/)).toBeInTheDocument();
    a.unmount();
    const bad = { ...DATA, report: { ...DATA.report!, selected_D: "RUN_REPORT_UNREADABLE" as const } };
    fetchForwardComparison.mockResolvedValueOnce(bad);
    const b = render(<ForwardComparisonCard />);
    expect(await screen.findByText(/최신 보고 확인 필요 — 이 기준일을 기록한 회차/)).toBeInTheDocument();
    b.unmount();
    const newer = { ...DATA, report: { ...DATA.report!, newer_unreadable: ["20261031T000000Z_x"] } };
    fetchForwardComparison.mockResolvedValueOnce(newer);
    render(<ForwardComparisonCard />);
    expect(await screen.findByText(/더 늦은 이름의 보고 파일 1개를 읽지 못했습니다/)).toBeInTheDocument();
  });

  it("MAE 는 부호 없는 %p · 큰 하락 표는 해당 행이 있을 때만", async () => {
    const withRows = {
      ...DATA,
      report: {
        ...DATA.report!,
        comparisons: {
          ALL_FOUR: {
            rows: 133,
            dates: 6,
            tickers: 24,
            excluded_rows: 6,
            mae_pp: { MEDIAN: 3.39, RIDGE: 3.1, HGB: 3.04, MLP_CPU: 3.21 },
            deep: { rows: 10, under_estimate_pp: { MEDIAN: 6.1, RIDGE: 5.7, HGB: 5, MLP_CPU: 5.8 } },
          },
        },
      },
    };
    fetchForwardComparison.mockResolvedValueOnce(withRows);
    render(<ForwardComparisonCard />);
    expect(await screen.findByText("3.39%p")).toBeInTheDocument();
    expect(screen.queryByText("+3.39%p")).toBeNull();
    expect(screen.getByText("큰 하락 행에서 작게 추정한 정도(%p · 보조)")).toBeInTheDocument();
    expect(screen.getByText("D20 ≤ −8% 행 10")).toBeInTheDocument();
  });

  // 검증자 r1 F2 — 화면에 보인 보고 · 카드 경고는 같은 응답의 복사문에도 그대로 남는다.
  const R = DATA.report!;
  const VARIANTS: [string, ForwardComparisonResponse][] = [
    ["보고 있음", DATA],
    ["회차 보고 대기", { ...DATA, report: { ...R, selected_D: "RUN_REPORT_MISSING" } }],
    ["회차 보고 손상", { ...DATA, report: { ...R, selected_D: "RUN_REPORT_UNREADABLE", newer_unreadable: ["z"] } }],
    [
      "보고 전부 손상",
      { ...DATA, report: { state: "CHECK_REQUIRED", selected_D: "RUN_REPORT_UNREADABLE", unreadable: ["a", "b"] } },
    ],
    ["더 늦은 보고 손상", { ...DATA, report: { ...R, newer_unreadable: ["20261031T000000Z_x"] } }],
    ["보고 값 확인 필요", { ...DATA, report: { ...R, state: "CHECK_REQUIRED" } }],
    ["보고 없음", { ...DATA, report: { state: "NONE", selected_D: "RUN_REPORT_MISSING" } }],
    ["회차 기록 손상", { ...DATA, basis: { ...DATA.basis!, unreadable_runs: ["r1"] } }],
  ];
  it.each(VARIANTS)("화면 경고 = 복사문 경고 — %s", async (_name, data) => {
    fetchForwardComparison.mockResolvedValue(data);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<ForwardComparisonCard />);
    fireEvent.click(await screen.findByRole("button", { name: "0015K0 상세" }));
    const notices = [...cardNotices(data), ...reportNotices(data)];
    expect(notices.length).toBeGreaterThan(0);
    for (const n of notices) expect(screen.getByText(n.text)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "복사" }));
    await waitFor(() => expect(writeText).toHaveBeenCalled());
    const copied = writeText.mock.calls[0][0] as string;
    expect(copied).toBe(copyText(data, ROW));
    for (const n of notices) expect(copied).toContain(n.text);
  });

  it("비교 항목이 없거나 행 수가 없으면 '아직 비교할 결과 없음'으로 바꾸지 않음", async () => {
    const broken = { ...DATA, report: { ...R, comparisons: {} } };
    fetchForwardComparison.mockResolvedValueOnce(broken);
    render(<ForwardComparisonCard />);
    expect((await screen.findAllByText("비교 항목 확인 필요")).length).toBe(3);
    expect(screen.queryByText("아직 비교할 결과 없음")).toBeNull();
  });

  it("행이 있는 비교에서 값이 null 이면 '-' 가 아니라 '값 확인 필요'(r2 F3 · 화면 방어)", async () => {
    const partial = {
      ...DATA,
      report: {
        ...R,
        comparisons: {
          ALL_FOUR: {
            rows: 1,
            dates: 1,
            tickers: 1,
            excluded_rows: 0,
            mae_pp: { MEDIAN: 7, RIDGE: 7, HGB: null, MLP_CPU: 7 },
            deep: { rows: 1, under_estimate_pp: { MEDIAN: 7, RIDGE: 7, HGB: null, MLP_CPU: 7 } },
          },
        },
      },
    };
    fetchForwardComparison.mockResolvedValueOnce(partial);
    render(<ForwardComparisonCard />);
    expect((await screen.findAllByText("값 확인 필요")).length).toBe(2);
    expect(screen.getAllByText("7.00%p").length).toBe(6);
  });
});
