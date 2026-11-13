// 「ETF보유 및 후보 선정 › 섹터요약」 화면 계약(POC6-28 「후보」 [섹터 요약] → POC6-29 독립 메뉴 · PLAN 판정 2026-11-12 Q1 · Q11).
// 요약 API · 상세 수치 API · 가격 시계열을 가짜로 바꿔 응답을 통제한다. 실제 네트워크 · 운영 자료 미의존.
// POC6-28 섹터 요약 시험(카드 순서 · 묶음 · 공통 구성종목 · 상·하위 공통)을 옮겼고, 이 화면만의 조건 · 기본 저장을 더했다.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import { __resetEtfCompareCondition, getScreenCondition, setScreenCondition, storageKeyOf } from "@/lib/etfCompareCondition";
import { detailResponse, group, link, row, summaryOk } from "@/lib/etfCompareTestFixtures";

const fetchEtfCompareSummary = vi.fn();
const fetchPriceSeries = vi.fn();
const fetchEtfDetail = vi.fn();

vi.mock("@/lib/api/etfCompare", async (orig) => ({
  ...(await orig<typeof import("@/lib/api/etfCompare")>()),
  fetchEtfCompareSummary: (...a: unknown[]) => fetchEtfCompareSummary(...a),
}));
vi.mock("@/lib/api/etfDetail", async (orig) => ({
  ...(await orig<typeof import("@/lib/api/etfDetail")>()),
  fetchEtfDetail: (...a: unknown[]) => fetchEtfDetail(...a),
}));
vi.mock("@/lib/api", () => ({
  fetchPriceSeries: (...a: unknown[]) => fetchPriceSeries(...a),
}));

import SectorSummaryView from "./SectorSummaryView";

const nav = vi.fn();
function renderView() {
  return render(<SectorSummaryView onNavigate={nav} />);
}

beforeEach(() => {
  vi.restoreAllMocks();
  __resetQueryCache();
  __resetEtfCompareCondition();
  window.localStorage.clear();
  fetchEtfCompareSummary.mockReset();
  fetchPriceSeries.mockReset();
  fetchEtfDetail.mockReset();
  nav.mockReset();
  fetchEtfCompareSummary.mockResolvedValue(summaryOk());
  fetchPriceSeries.mockImplementation((t: string) =>
    Promise.resolve({ ticker: t, availability: "AVAILABLE", series: [{ date: "2026-11-09", price: 100 }] }),
  );
  fetchEtfDetail.mockImplementation((ts: string[]) => Promise.resolve(detailResponse(ts)));
});

describe("「섹터요약」 첫 화면", () => {
  it("이 화면 조건으로 1회 조회 · 기준 줄 · 시장 판정 줄 · 가격 · 상세는 조회하지 않는다", async () => {
    renderView();
    expect(await screen.findByTestId("ec-sector-summary")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "섹터요약" })).toBeInTheDocument();
    expect(screen.getByTestId("ec-basis")).toHaveTextContent("1개월 · 10/12 → 11/9");
    expect(screen.getByTestId("ec-regime")).toHaveTextContent("시장 판정(국내시장 · KODEX 200 · 11/9): 하락장");
    expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(1);
    expect(fetchEtfCompareSummary.mock.calls[0][0]).toEqual(getScreenCondition("sector"));
    expect(fetchPriceSeries).not.toHaveBeenCalled();
    expect(fetchEtfDetail).not.toHaveBeenCalled();
  });

  it("하락장 = 보유 겹침 → 하위 → 상위 카드 순서 · 상위권 공식 구성 · 하위권 반복 업종 먼저", async () => {
    renderView();
    const box = await screen.findByTestId("ec-sector-summary");
    expect(box.getAttribute("data-order")).toBe("holdings,bottom,top");
    expect(screen.getByTestId("ec-mix-top")).toHaveTextContent("공식 분류: 해외 주식 2 · 국내 주식 1");
    const card = screen.getByTestId("ec-card-bottom");
    const semi = within(card).getAllByTestId("ec-group")[0];
    expect(semi).toHaveTextContent("반도체");
    expect(semi).toHaveTextContent("공통 구성종목 주성엔지니어링 2 · 마이크론 2");
  });

  it("ETF 를 누르면 그 행 아래 상세 — 그 종목 하나의 상세 수치 · 1 · 3 · 6 · 12개월 · 시장가 · NAV · 괴리율 · 판단 근거 카드", async () => {
    renderView();
    const card = await screen.findByTestId("ec-card-bottom");
    fireEvent.click(within(card).getByRole("button", { name: /반도체 전공정/ }));
    const detail = await within(card).findByTestId("ec-etf-detail");
    await waitFor(() => expect(fetchEtfDetail).toHaveBeenCalledWith(["B00001"]));
    expect(await within(detail).findByTestId("dn-months")).toHaveTextContent(
      "1개월 -10.25% (10/12 → 11/9) · 3개월 -5.50% (8/11 → 11/9) · 6개월 +12.30% (5/12 → 11/9) · 12개월 +30.10% (2025-11-10 → 11/9)",
    );
    expect(within(detail).getByTestId("dn-excess")).toHaveTextContent("+6.10%p (이 종목 -8.40% · KODEX 200 -14.50% · 같은 10/13 → 11/9)");
    expect(within(detail).getByTestId("dn-nav")).toHaveTextContent("10,000원 · 10,010원 · -0.10% · 11/9 자료");
    expect(within(detail).getByRole("button", { name: "판단 근거 미리보기 생성" })).toBeInTheDocument();
    expect(detail).toHaveTextContent("보유 중");
  });

  it("목록 전체 AI 복사 — 클립보드에만 · 머리 = 같은 기간 ETF 목록", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    Object.assign(navigator, { clipboard: { writeText } });
    renderView();
    const copy = await screen.findByTestId("ec-copy-bottom");
    fireEvent.click(within(copy).getByRole("button", { name: "이 목록 전체를 AI 질문용으로 복사" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(String((writeText.mock.calls[0] as unknown[])[0])).toContain("[같은 기간 ETF 목록 · 1개월 하위 3개 · 10/12 → 11/9]");
  });

  it("상·하위에 함께 든 같은 ETF 는 ETF 줄 · 내 보유와 겹친 항목에 공통 표시(검증자 r1 F3)", async () => {
    const x = row({ rank: 1, ticker: "X00001", name: "단일 ETF", value: -3 });
    const g = group([x], { kind: "index", name: "단일 지수" });
    const s = summaryOk();
    fetchEtfCompareSummary.mockResolvedValue({
      ...s,
      top: [x],
      bottom: [x],
      in_both: ["X00001"],
      groups: { top: [g], bottom: [g] },
      counts: { ...s.counts, population: 1, shown_top: 1, shown_bottom: 1 },
      holdings: { status: "ok" as const, items: [link({ ticker: "X00001", side: "bottom", side_rank: 1, top_rank: 1 })] },
    });
    renderView();
    const hold = await screen.findByTestId("ec-card-holdings");
    expect(hold).toHaveTextContent("하위 1위 · 상위 1위(상·하위 공통)");
    const card = screen.getByTestId("ec-card-bottom");
    fireEvent.click(within(card).getByRole("button", { name: /기초지수별 묶음 1개/ }));
    fireEvent.click(within(card).getAllByTestId("ec-group")[0].querySelector("summary")!);
    expect(within(card).getByRole("button", { name: /단일 ETF/ })).toHaveTextContent("상·하위 공통");
  });
});

describe("이 화면의 조회 기준 · 기본 저장(판정 Q1 · Q11)", () => {
  it("[조회 기준]에서 3개월 적용 = 이 화면만 · 후보리스트 · 보유 조건은 그대로", async () => {
    renderView();
    await screen.findByTestId("ec-sector-summary");
    fireEvent.click(screen.getByRole("button", { name: "조회 기준" }));
    const panel = screen.getByTestId("ec-condition-panel");
    expect(panel).toHaveTextContent("「섹터요약」 조회 기준");
    fireEvent.click(within(panel).getByRole("button", { name: "3개월" }));
    fireEvent.click(within(panel).getByRole("button", { name: "적용" }));
    await waitFor(() => expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(2));
    expect(getScreenCondition("sector").basis).toBe("three_month");
    expect(getScreenCondition("candidates").basis).toBe("one_month");
    expect(getScreenCondition("holdings").basis).toBe("one_month");
  });

  it("[이 기준을 기본으로] = 이 화면 저장 칸에만 · 새로 고침(저장소 초기화)하면 그 기간으로 시작", async () => {
    renderView();
    await screen.findByTestId("ec-sector-summary");
    fireEvent.click(screen.getByRole("button", { name: "조회 기준" }));
    const panel = screen.getByTestId("ec-condition-panel");
    fireEvent.click(within(panel).getByRole("button", { name: "3개월" }));
    fireEvent.click(within(panel).getByRole("button", { name: "적용" }));
    const save = await screen.findByTestId("ec-save-sector");
    fireEvent.click(within(save).getByRole("button", { name: "이 기준을 기본으로(3개월)" }));
    expect(window.localStorage.getItem(storageKeyOf("sector"))).toBe("three_month");
    expect(window.localStorage.getItem(storageKeyOf("candidates"))).toBeNull();
    expect(save).toHaveTextContent("기본 기간: 3개월 (이 화면에 저장됨)");
    __resetEtfCompareCondition();
    expect(getScreenCondition("sector").basis).toBe("three_month");
    expect(getScreenCondition("candidates").basis).toBe("one_month");
  });

  it("[기본값으로] = 이 화면에 저장한 기본 기간 · 4종 제외(늘 1개월이 아님 · 검토 지적)", async () => {
    window.localStorage.setItem(storageKeyOf("sector"), "three_month");
    __resetEtfCompareCondition();
    renderView();
    await screen.findByTestId("ec-sector-summary");
    fireEvent.click(screen.getByRole("button", { name: "조회 기준" }));
    let panel = screen.getByTestId("ec-condition-panel");
    fireEvent.click(within(panel).getByRole("button", { name: "1일" }));
    fireEvent.click(within(panel).getByRole("button", { name: "적용" }));
    await waitFor(() => expect(getScreenCondition("sector").basis).toBe("daily"));
    fireEvent.click(screen.getByRole("button", { name: "조회 기준" }));
    panel = screen.getByTestId("ec-condition-panel");
    fireEvent.click(within(panel).getByRole("button", { name: "기본값으로" }));
    fireEvent.click(within(panel).getByRole("button", { name: "적용" }));
    await waitFor(() => expect(getScreenCondition("sector").basis).toBe("three_month"));
    expect(getScreenCondition("sector").filters.exclude_inverse).toBe(true);
  });
});

describe("저장 기간을 확인하지 못함 · 다른 탭 저장(검증자 r1 F2 · PLAN §3-1)", () => {
  it("저장소 읽기 예외 = 실패 안내('저장 없음' 아님) · 1개월 조회 그대로 · 저장에 성공하면 저장됨", async () => {
    const get = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    renderView();
    await screen.findByTestId("ec-sector-summary");
    const save = screen.getByTestId("ec-save-sector");
    expect(within(save).getByTestId("ec-save-notice-sector")).toHaveTextContent(
      "저장된 기본을 읽지 못해 1개월로 시작했습니다",
    );
    expect(save).not.toHaveTextContent("저장 없음");
    expect(fetchEtfCompareSummary).toHaveBeenCalledWith(expect.objectContaining({ basis: "one_month" }));
    get.mockRestore();
    fireEvent.click(within(save).getByRole("button", { name: "이 기준을 기본으로(1개월)" }));
    expect(save).toHaveTextContent("기본 기간: 1개월 (이 화면에 저장됨)");
    expect(within(save).queryByTestId("ec-save-notice-sector")).toBeNull();
  });

  it("허용 밖 저장값 = '쓸 수 없어' 안내 · 1개월을 보고 있어도 [이 기준을 기본으로]로 바로잡음", async () => {
    window.localStorage.setItem(storageKeyOf("sector"), "weekly");
    renderView();
    await screen.findByTestId("ec-sector-summary");
    const save = screen.getByTestId("ec-save-sector");
    expect(save).toHaveTextContent("저장된 기본 값을 쓸 수 없어 1개월로 시작했습니다");
    fireEvent.click(within(save).getByRole("button", { name: "이 기준을 기본으로(1개월)" }));
    expect(window.localStorage.getItem(storageKeyOf("sector"))).toBe("one_month");
    expect(save).toHaveTextContent("기본 기간: 1개월 (이 화면에 저장됨)");
  });

  it("다른 탭에서 저장 = 저장 표시만 다시 읽음 · 지금 조회 · 요청은 그대로", async () => {
    renderView();
    await screen.findByTestId("ec-sector-summary");
    const save = screen.getByTestId("ec-save-sector");
    expect(save).toHaveTextContent("저장 없음");
    window.localStorage.setItem(storageKeyOf("sector"), "three_month");
    act(() => {
      window.dispatchEvent(new StorageEvent("storage", { key: "other.key" }));
    });
    expect(save).toHaveTextContent("저장 없음");
    act(() => {
      window.dispatchEvent(new StorageEvent("storage", { key: storageKeyOf("sector") }));
    });
    expect(save).toHaveTextContent("기본 기간: 3개월 (이 화면에 저장됨)");
    expect(getScreenCondition("sector").basis).toBe("one_month");
    expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(1);
  });
});

describe("저장값 안내 = 지금 조회 기간과 맞춤(검증자 r2 F3 · 시작 상태 × 기간 변경 × 다른 탭 저장 뒤 다시 읽기)", () => {
  type St = "saved" | "none" | "read_failed" | "invalid";
  type B = "daily" | "one_month" | "three_month";
  const KEY = storageKeyOf("sector");
  const LABEL: Record<B, string> = { daily: "1일", one_month: "1개월", three_month: "3개월" };
  const START_FORM = {
    read_failed: "저장된 기본을 읽지 못해 1개월로 시작했습니다",
    invalid: "저장된 기본 값을 쓸 수 없어 1개월로 시작했습니다",
  };
  const NOW_FORM = { read_failed: "저장된 기본을 읽지 못했습니다", invalid: "저장된 기본 값을 쓸 수 없습니다" };

  // 저장소를 그 상태로 둔다 — read_failed 는 읽기 예외 spy 를 돌려준다(호출자가 풀어 줌).
  function prepare(st: St, value: B) {
    window.localStorage.removeItem(KEY);
    if (st === "saved") window.localStorage.setItem(KEY, value);
    if (st === "invalid") window.localStorage.setItem(KEY, "weekly");
    return st === "read_failed"
      ? vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
          throw new DOMException("blocked", "SecurityError");
        })
      : null;
  }

  // 계약: 읽기 실패 · 쓸 수 없는 값에서 '…해 1개월로 시작했습니다'는 바로 그 이유로 1개월로 시작했고 지금도
  // 1개월일 때만. 그 밖은 '— 지금 조회(기간)는 그대로입니다'. 저장됨 · 없음은 저장 상태 그대로.
  function expected(start: St, now: St, basis: B, savedValue: B): string {
    if (now === "saved") return `기본 기간: ${LABEL[savedValue]} (이 화면에 저장됨)`;
    if (now === "none") return "기본 기간: 1개월 (저장 없음 · 새로 고치면 1개월로 시작)";
    return start === now && basis === "one_month"
      ? START_FORM[now]
      : `${NOW_FORM[now]} — 지금 조회(${LABEL[basis]})는 그대로입니다`;
  }

  const STATES: St[] = ["saved", "none", "read_failed", "invalid"];
  const cases = STATES.flatMap((start) =>
    [false, true].flatMap((changed) => STATES.map((now) => ({ start, changed, now }))),
  );

  it.each(cases)("시작 $start · 기간 바꿈 $changed · 다시 읽기 $now", async ({ start, changed, now }) => {
    const spy1 = prepare(start, "three_month");
    renderView();
    await screen.findByTestId("ec-sector-summary");
    spy1?.mockRestore();
    const first: B = start === "saved" ? "three_month" : "one_month";
    expect(getScreenCondition("sector").basis).toBe(first);
    const save = screen.getByTestId("ec-save-sector");
    expect(save).toHaveTextContent(expected(start, start, first, "three_month"));
    let basis: B = first;
    if (changed) {
      basis = first === "three_month" ? "one_month" : "three_month";
      act(() => setScreenCondition("sector", { ...getScreenCondition("sector"), basis }));
      await waitFor(() =>
        expect(fetchEtfCompareSummary).toHaveBeenLastCalledWith(expect.objectContaining({ basis })),
      );
      expect(save).toHaveTextContent(expected(start, start, basis, "three_month"));
    }
    const calls = fetchEtfCompareSummary.mock.calls.length;
    const spy2 = prepare(now, "daily");
    act(() => {
      window.dispatchEvent(new StorageEvent("storage", { key: KEY }));
    });
    const text = expected(start, now, basis, "daily");
    expect(save).toHaveTextContent(text);
    if (!text.includes("1개월로 시작했습니다")) expect(save).not.toHaveTextContent("1개월로 시작했습니다");
    spy2?.mockRestore();
    // 지금 조회는 그대로(조건 · 요청 모두)
    expect(getScreenCondition("sector").basis).toBe(basis);
    expect(fetchEtfCompareSummary).toHaveBeenCalledTimes(calls);
  });

  it("검증자 재현 — 저장된 3개월로 시작 · 다른 탭 저장 뒤 읽기 실패 / 쓸 수 없는 값 = '1개월로 시작' 아님 · 지금 조회 3개월", async () => {
    window.localStorage.setItem(KEY, "three_month");
    renderView();
    await screen.findByTestId("ec-sector-summary");
    const save = screen.getByTestId("ec-save-sector");
    window.localStorage.setItem(KEY, "weekly");
    act(() => {
      window.dispatchEvent(new StorageEvent("storage", { key: KEY }));
    });
    expect(within(save).getByTestId("ec-save-notice-sector")).toHaveTextContent(
      "저장된 기본 값을 쓸 수 없습니다 — 지금 조회(3개월)는 그대로입니다",
    );
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    act(() => {
      window.dispatchEvent(new StorageEvent("storage", { key: KEY }));
    });
    expect(within(save).getByTestId("ec-save-notice-sector")).toHaveTextContent(
      "저장된 기본을 읽지 못했습니다 — 지금 조회(3개월)는 그대로입니다",
    );
    expect(save).not.toHaveTextContent("1개월로 시작했습니다");
    expect(getScreenCondition("sector").basis).toBe("three_month");
  });

  it("저장 실패 안내 = 같은 기간이 저장된 것으로 다시 읽히면 내림 · 다른 기간이 저장되면 남김", async () => {
    renderView();
    await screen.findByTestId("ec-sector-summary");
    const save = screen.getByTestId("ec-save-sector");
    const FAIL = "기본값(1개월) 저장을 확인하지 못했습니다 — 지금 조회는 그대로입니다";
    const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => undefined);
    fireEvent.click(within(save).getByRole("button", { name: "이 기준을 기본으로(1개월)" }));
    expect(save).toHaveTextContent(FAIL);
    set.mockRestore();
    // 실패 뒤 기간을 바꿔도 실패한 기간(1개월)을 그대로 적는다
    act(() => setScreenCondition("sector", { ...getScreenCondition("sector"), basis: "three_month" }));
    expect(save).toHaveTextContent(FAIL);
    act(() => setScreenCondition("sector", { ...getScreenCondition("sector"), basis: "one_month" }));
    window.localStorage.setItem(KEY, "three_month");
    act(() => {
      window.dispatchEvent(new StorageEvent("storage", { key: KEY }));
    });
    expect(save).toHaveTextContent("기본 기간: 3개월 (이 화면에 저장됨)");
    expect(save).toHaveTextContent(FAIL); // 1개월 저장은 여전히 확인 못 함
    window.localStorage.setItem(KEY, "one_month");
    act(() => {
      window.dispatchEvent(new StorageEvent("storage", { key: KEY }));
    });
    expect(save).toHaveTextContent("기본 기간: 1개월 (이 화면에 저장됨)");
    expect(save).not.toHaveTextContent(FAIL);
  });
});
