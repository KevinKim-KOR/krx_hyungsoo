// POC6-15 — 「진단·상태 › ML 연구」 두 화면 관통 시험(실제 MainPanel · 사이드바 · MLView · 카드 · 가짜 응답).
//
// 설계자 PLAN 판정(2026-11-01) §5 시험 묶음:
// - 두 화면 분배: 예측과 결과 비교(`ml` · 카드 1) · 이전 자료·실험(`ml_legacy` · 카드 5) · 고른 화면의 카드만 조회.
// - 기존 `ml` key 진입 = 예측과 결과 비교.
// - 폴더 접기 · 펼치기는 본문을 다시 그리지 않음(조회 추가 0 · 고른 기준일 그대로).
// - 메뉴 이동만으로 명령(이전 자료 다시 만들기 · 참고점수 계산) 호출 0.
//
// @/lib/api 는 부분 mock — 오늘 화면이 부르는 조회는 실패시키고(이동만 본다), ML 조회는 호출 수를 센다.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, within, act } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import { DATA } from "./ml_forward/testFixtures";

const noData = () => Promise.reject(new Error("test: 자료 없음"));
const fetchForwardComparison = vi.fn();
const fetchMlReadinessLatest = vi.fn();
const fetchMlFeatureSanityLatest = vi.fn();
const fetchMlJobsLatest = vi.fn();
const fetchMlBaselineV0Latest = vi.fn();
const startMlEvidenceRefresh = vi.fn();
const runRelativeUpsideScore = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchMarketTopnLatest: () => noData(),
    fetchEnrichedHoldings: () => noData(),
    fetchHoldingsMarketEvidence: () => noData(),
    fetchNavDiscountLatest: () => noData(),
    fetchBenchmarkSeries: () => noData(),
    fetchOciStartupStatus: () => noData(),
    fetchForwardComparison: (...a: unknown[]) => fetchForwardComparison(...a),
    fetchMlReadinessLatest: (...a: unknown[]) => fetchMlReadinessLatest(...a),
    fetchMlFeatureSanityLatest: (...a: unknown[]) => fetchMlFeatureSanityLatest(...a),
    fetchMlJobsLatest: (...a: unknown[]) => fetchMlJobsLatest(...a),
    fetchMlBaselineV0Latest: (...a: unknown[]) => fetchMlBaselineV0Latest(...a),
    startMlEvidenceRefresh: (...a: unknown[]) => startMlEvidenceRefresh(...a),
  };
});

vi.mock("@/lib/api/mlRelativeUpside", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return { ...actual, runRelativeUpsideScore: (...a: unknown[]) => runRelativeUpsideScore(...a) };
});

import MainPanel from "./MainPanel";
import MLView from "./MLView";

const LEGACY_FETCHES = [
  fetchMlReadinessLatest,
  fetchMlFeatureSanityLatest,
  fetchMlJobsLatest,
  fetchMlBaselineV0Latest,
];

beforeEach(() => {
  __resetQueryCache();
  vi.clearAllMocks();
  fetchForwardComparison.mockImplementation((d?: string) =>
    Promise.resolve(d ? { ...DATA, selected_D: d } : DATA),
  );
  for (const f of LEGACY_FETCHES) f.mockImplementation(() => noData());
});

const menu = (label: string) => screen.getByText(label).closest("button")!;

// 첫 화면(오늘의 투자 점검)의 조회 실패 처리까지 act 안에서 끝낸다(act 경고 없이 이동만 본다).
async function renderPanel() {
  const r = render(<MainPanel />);
  await act(async () => {
    await new Promise((res) => setTimeout(res, 0));
  });
  return r;
}
const folder = () => screen.getByText("ML 연구").closest("button")!;

describe("POC6-15 ML 연구 두 화면", () => {
  it("예측과 결과 비교(`ml`) = 전향 카드 1개만 · 이전 자료 카드 조회 0", async () => {
    await renderPanel();
    fireEvent.click(menu("예측과 결과 비교"));
    const page = await screen.findByRole("heading", { level: 1, name: "예측과 결과 비교" });
    expect(screen.getByText("미리 기록한 예측과 이후 실제 결과를 비교합니다.")).toBeInTheDocument();
    await screen.findByText("-3.06%");
    const section = page.closest("section")!;
    expect(section.querySelectorAll(":scope > .card").length).toBe(1);
    expect(fetchForwardComparison).toHaveBeenCalledTimes(1);
    for (const f of LEGACY_FETCHES) expect(f).not.toHaveBeenCalled();
  });

  it("이전 자료·실험(`ml_legacy`) = 카드 5개 · 안내 한 줄 · 전향 조회 0 · 카드마다 조회 1회", async () => {
    await renderPanel();
    fireEvent.click(menu("이전 자료·실험"));
    const page = await screen.findByRole("heading", { level: 1, name: "이전 자료·실험" });
    expect(
      screen.getByText("현재 예측 비교와 별개인 이전 자료와 실험 결과를 확인합니다."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/이 자료를 다시 만들어도 현재 예측 비교의 입력이나 모델이 갱신되는 것은\s*아닙니다/),
    ).toBeInTheDocument();
    const section = page.closest("section")!;
    // 카드 5개 = .card 4개 + 상대 상승 카드(.card 또는 section) — 직속 카드 수로 센다
    const cards = section.querySelectorAll(":scope > .card, :scope > section");
    expect(cards.length).toBe(5);
    expect(fetchForwardComparison).not.toHaveBeenCalled();
    for (const f of LEGACY_FETCHES) expect(f).toHaveBeenCalledTimes(1);
  });

  it("두 화면을 오가도 명령 함수 호출 0 · 화면마다 새로 그림", async () => {
    await renderPanel();
    fireEvent.click(menu("이전 자료·실험"));
    await screen.findByRole("heading", { level: 1, name: "이전 자료·실험" });
    fireEvent.click(menu("예측과 결과 비교"));
    await screen.findByText("-3.06%");
    fireEvent.click(menu("이전 자료·실험"));
    await screen.findByRole("heading", { level: 1, name: "이전 자료·실험" });
    expect(startMlEvidenceRefresh).not.toHaveBeenCalled();
    expect(runRelativeUpsideScore).not.toHaveBeenCalled();
    expect(fetchForwardComparison).toHaveBeenCalledTimes(1);
    for (const f of LEGACY_FETCHES) expect(f).toHaveBeenCalledTimes(2);
  });

  it("폴더 접기 · 펼치기 = 본문 그대로(조회 추가 0 · 고른 기준일 유지)", async () => {
    await renderPanel();
    fireEvent.click(menu("예측과 결과 비교"));
    const select = await screen.findByRole("combobox");
    fireEvent.change(select, { target: { value: "2026-10-27" } });
    expect(await screen.findByRole("combobox")).toHaveValue("2026-10-27");
    const calls = fetchForwardComparison.mock.calls.length;
    fireEvent.click(folder());
    expect(folder()).toHaveAttribute("aria-expanded", "false");
    expect(folder()).toHaveTextContent("· 예측과 결과 비교");
    fireEvent.click(folder());
    expect(screen.getByRole("combobox")).toHaveValue("2026-10-27");
    expect(fetchForwardComparison.mock.calls.length).toBe(calls);
    expect(screen.getByRole("heading", { level: 1, name: "예측과 결과 비교" })).toBeInTheDocument();
  });

  it("사이드바에 「ML 실험」은 없고 진단·상태 안 ML 연구 폴더 아래 두 화면", async () => {
    await renderPanel();
    expect(screen.queryByText("ML 실험")).toBeNull();
    const sub = document.getElementById(folder().getAttribute("aria-controls")!)!;
    expect(within(sub).getAllByRole("button").map((b) => b.querySelector(".sidebar-menu-label")?.textContent)).toEqual([
      "예측과 결과 비교",
      "이전 자료·실험",
    ]);
  });

  it("MLView 단독 — page 마다 제목 · 카드만(고르지 않은 화면 카드의 조회 0)", async () => {
    const a = render(<MLView page="forward" />);
    await screen.findByText("-3.06%");
    for (const f of LEGACY_FETCHES) expect(f).not.toHaveBeenCalled();
    a.unmount();
    vi.clearAllMocks();
    for (const f of LEGACY_FETCHES) f.mockImplementation(() => noData());
    render(<MLView page="legacy" />);
    await act(async () => {
      await new Promise((res) => setTimeout(res, 0));
    });
    expect(screen.getByRole("heading", { level: 1, name: "이전 자료·실험" })).toBeInTheDocument();
    expect(fetchForwardComparison).not.toHaveBeenCalled();
  });
});
