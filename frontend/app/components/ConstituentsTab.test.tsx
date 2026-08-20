// 구성종목 탭 — 수집 경로 계약 test (2026-08-19 검증자 REJECTED 대응).
//
// 왜 이 파일이 생겼나: 백엔드 깊이를 30 으로 올리고 **조회 한 곳만** 30 으로 고쳤다.
// 수집 버튼(POST)과 수집 직후 재조회(GET)는 리터럴 10 이 남아 있었고, 백엔드는
// "10건 요청 + 10건 캐시" 를 완료로 판단하므로 **사용자 경로에서는 재수집도 30건
// 표시도 일어나지 않았다.** 백엔드 테스트 10건은 전부 통과했지만 이 연결 누락을
// 잡지 못했다 — 실제 사용자 경로를 검사하는 테스트가 없었기 때문이다.
//
// 그래서 여기서는 **화면이 서버에 무엇을 보내는지**를 고정한다.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, fireEvent, waitFor } from "@testing-library/react";

const refreshConstituents = vi.fn();
const fetchConstituentsAnalysis = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    refreshConstituents: (...a: unknown[]) => refreshConstituents(...a),
    fetchConstituentsAnalysis: (...a: unknown[]) => fetchConstituentsAnalysis(...a),
  };
});

import ConstituentsTab from "./ConstituentsTab";
import { CONSTITUENTS_TOP_K } from "@/lib/api";
import type {
  ConstituentsAnalysisResponse,
  ConstituentItem,
} from "@/lib/api";
import type { ETFExposureDraft } from "@/lib/etfExposureDraft";

function draft(): ETFExposureDraft {
  return {
    asof: "2026-08-19",
    filters: {} as ETFExposureDraft["filters"],
    candidate_snapshot: [
      { ticker: "069500", name: "KODEX 200", tags: [] },
      { ticker: "229200", name: "KODEX 코스닥150", tags: [] },
    ],
    market_candidates: [],
    draft_created_at: "2026-08-19T00:00:00Z",
  };
}

function item(overrides: Partial<ConstituentItem> = {}): ConstituentItem {
  return {
    etf_ticker: "069500",
    etf_name: null,
    status: "ok",
    source: "naver_stock_etf_component",
    asof: "2026-08-19",
    top_holdings: [
      { rank: 1, ticker: "005930", name: "삼성전자", weight_pct: 34.19 },
      { rank: 2, ticker: "000660", name: "SK하이닉스", weight_pct: 10.81 },
    ],
    concentration: {
      top1_weight_pct: 34.19,
      top3_weight_pct: 45.0,
      top5_weight_pct: 50.0,
      top10_weight_pct: 60.0,
    },
    ...overrides,
  } as ConstituentItem;
}

function analysis(items: ConstituentItem[] = [item()]): ConstituentsAnalysisResponse {
  return {
    status: "ok",
    asof: "2026-08-19",
    top_k: CONSTITUENTS_TOP_K,
    overlap_top_k: 10,
    coverage: {
      requested_count: items.length,
      available_count: items.length,
      unavailable_count: 0,
    },
    constituents: items,
    overlap_matrix: [],
    repeated_core_holdings: [],
  } as ConstituentsAnalysisResponse;
}

beforeEach(() => {
  refreshConstituents.mockReset();
  fetchConstituentsAnalysis.mockReset();
});

describe("구성종목 수집 경로가 설계 확정 깊이를 그대로 보낸다", () => {
  it("수집 버튼이 top_k=30 으로 POST 하고, 직후 조회도 30 으로 한다", async () => {
    refreshConstituents.mockResolvedValue({
      status: "ok",
      success_count: 2,
      fail_count: 0,
      cached_count: 0,
      skipped_count: 0,
      items: [],
    });
    fetchConstituentsAnalysis.mockResolvedValue(analysis());

    render(
      <ConstituentsTab draft={draft()} analysis={null} setAnalysis={vi.fn()} />,
    );
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /수집/ }));
    });

    await waitFor(() => expect(refreshConstituents).toHaveBeenCalledTimes(1));

    // POST — 백엔드가 "10건 요청 + 10건 캐시" 를 완료로 보므로, 여기서 10 을
    // 보내면 기존 캐시가 그대로 유지되고 재수집이 일어나지 않는다.
    expect(refreshConstituents.mock.calls[0][0]).toMatchObject({
      top_k: CONSTITUENTS_TOP_K,
    });
    expect(CONSTITUENTS_TOP_K).toBe(30);

    // 수집 직후 재조회 — 표시 깊이도 같은 값이어야 30건이 화면에 나온다.
    await waitFor(() => expect(fetchConstituentsAnalysis).toHaveBeenCalled());
    expect(fetchConstituentsAnalysis.mock.calls[0][2]).toBe(CONSTITUENTS_TOP_K);
  });

  it("안내문이 실제 수집 깊이와 같은 숫자를 말한다", () => {
    render(
      <ConstituentsTab draft={draft()} analysis={null} setAnalysis={vi.fn()} />,
    );
    expect(
      screen.getByText(new RegExp(`상위\\s*${CONSTITUENTS_TOP_K}개 구성종목`)),
    ).toBeTruthy();
  });
});

describe("표시 계약", () => {
  it("비중이 없는 종목을 0 으로 합산하지 않고 제외 개수를 밝힌다", () => {
    const withMissing = item({
      top_holdings: [
        { rank: 1, ticker: "005930", name: "삼성전자", weight_pct: 34.19 },
        { rank: 2, ticker: "000660", name: "SK하이닉스", weight_pct: null },
      ],
    } as Partial<ConstituentItem>);
    render(
      <ConstituentsTab
        draft={draft()}
        analysis={analysis([withMissing])}
        setAnalysis={vi.fn()}
      />,
    );
    // 합계 문장은 여러 텍스트 노드로 쪼개져 그려지므로 문단 전체로 본다.
    const summary = screen
      .getAllByText(/표시 비중 합계/)
      .map((el) => el.textContent ?? "")
      .join(" ");
    // 값이 있는 것만 더한다.
    expect(summary).toMatch(/34\.19%/);
    // **이 줄이 판별점이다.** `?? 0` 으로 합산하면 합계 숫자는 똑같이 34.19% 라
    // 수치만으로는 옛 동작과 구분되지 않는다. 빠진 개수를 밝히는지가 차이다.
    expect(summary).toMatch(/비중 미확인 1개 제외/);
  });

  it("비중이 전부 없으면 0.00% 가 아니라 확인 불가 로 적는다", () => {
    // `?? 0` 합산이면 여기서 "0.00%" 가 나온다 — 값이 없는데 완성된 수치처럼
    // 보이는 정확히 그 상황이다.
    const allMissing = item({
      top_holdings: [
        { rank: 1, ticker: "005930", name: "삼성전자", weight_pct: null },
        { rank: 2, ticker: "000660", name: "SK하이닉스", weight_pct: null },
      ],
    } as Partial<ConstituentItem>);
    render(
      <ConstituentsTab
        draft={draft()}
        analysis={analysis([allMissing])}
        setAnalysis={vi.fn()}
      />,
    );
    const summary = screen
      .getAllByText(/표시 비중 합계/)
      .map((el) => el.textContent ?? "")
      .join(" ");
    expect(summary).toMatch(/확인 불가/);
    expect(summary).not.toMatch(/0\.00%/);
  });

  it("등락률 열과 unavailable 안내문이 없다", () => {
    render(
      <ConstituentsTab
        draft={draft()}
        analysis={analysis()}
        setAnalysis={vi.fn()}
      />,
    );
    expect(screen.queryByText("등락률")).toBeNull();
    expect(screen.queryByText(/등락률 unavailable/)).toBeNull();
  });

  it("중복률 기준 깊이를 응답 값 그대로 말한다 (임의값으로 메우지 않는다)", () => {
    render(
      <ConstituentsTab
        draft={draft()}
        analysis={analysis()}
        setAnalysis={vi.fn()}
      />,
    );
    expect(screen.getByText(/상위\s*10건 기준으로 계산합니다/)).toBeTruthy();
  });
});
