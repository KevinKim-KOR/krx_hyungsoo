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
// POC6-31(판정 Q6 (b)) — 수집은 서버 작업(시작 · 상태 읽기)
const postConstituentsCollect = vi.fn();
const fetchConstituentsCollectStatus = vi.fn();
vi.mock("@/lib/api/constituentsStatus", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  postConstituentsCollect: (...a: unknown[]) => postConstituentsCollect(...a),
  fetchConstituentsCollectStatus: (...a: unknown[]) => fetchConstituentsCollectStatus(...a),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    refreshConstituents: (...a: unknown[]) => refreshConstituents(...a),
    fetchConstituentsAnalysis: (...a: unknown[]) => fetchConstituentsAnalysis(...a),
  };
});

import { useState } from "react";
import ConstituentsTab, { CollectButton, CollectHelp, CollectStatus, useCandidateCollect, type CandidateCollect } from "./ConstituentsTab";
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
  postConstituentsCollect.mockReset();
  fetchConstituentsCollectStatus.mockReset().mockResolvedValue({ state: "idle", job_id: null, items: [] });
});

const doneJob = (p: Record<string, unknown> = {}) => ({
  state: "done",
  job_id: "candidates_x",
  kind: "candidates",
  target_date: "2026-11-13",
  total: 2,
  done: 2,
  batch_index: 1,
  batch_total: 1,
  calls: 1,
  counts: { existing: 1, fetched: 1 },
  update_failed: 0,
  items: [
    { ticker: "069500", result: "existing", label: "기존 자료", reason: "r", source_asof: "2026-11-13", kept_asof: null, kept_confirmed: true },
    { ticker: "229200", result: "fetched", label: "새로 받음", reason: "r", source_asof: "2026-11-13", kept_asof: null, kept_confirmed: true },
  ],
  ...p,
});

// 화면(ETFExposureView)처럼 수집 훅을 탭 밖에서 든다 — 탭을 내려도 따라가기는 이어진다(지적 frontend#2).
function Harness({ onDone, analysis: a = null }: { onDone: () => void; analysis?: ConstituentsAnalysisResponse | null }) {
  const d = draft();
  const tickers = d.candidate_snapshot.map((c) => c.ticker as string);
  const collect = useCandidateCollect(tickers, onDone);
  const [tab, setTab] = useState(true);
  return (
    <>
      {/* 화면 머리 · 위쪽 상태(탭과 상관없이 늘 보임) */}
      <CollectButton collect={collect} count={tickers.length} />
      <CollectStatus collect={collect} />
      <button type="button" onClick={() => setTab(!tab)}>
        탭 바꾸기
      </button>
      {tab ? <ConstituentsTab draft={d} analysis={a} collect={collect} /> : null}
    </>
  );
}

const noCollect: CandidateCollect = { job: null, other: null, error: null, running: false, start: () => undefined };

describe("구성종목 수집 경로가 설계 확정 깊이를 그대로 보낸다", () => {
  it("수집 버튼 = 넘겨받은 목록으로 서버 수집 작업 시작 · 끝나면 부모가 다시 읽는다(POC6-31 Q6 (b))", async () => {
    postConstituentsCollect.mockResolvedValue(doneJob({ state: "running", done: 0, items: [] }));
    fetchConstituentsCollectStatus
      .mockResolvedValueOnce({ state: "idle", job_id: null, items: [] }) // 화면 열 때
      .mockResolvedValue(doneJob());
    const onDone = vi.fn();
    render(<Harness onDone={onDone} />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /구성종목 수집/ }));
    });
    expect(postConstituentsCollect).toHaveBeenCalledWith(["069500", "229200"]);
    expect(refreshConstituents).not.toHaveBeenCalled(); // 예전 한 번에 10개 요청 경로를 쓰지 않음
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1), { timeout: 4000 });
    expect(screen.getByTestId("cst-collect-line").textContent).toBe(
      "수집 끝 — 목표일 11/13 · 후보 2개 · 기존 자료 1 · 새로 받음 1 · 실제 호출 1회",
    );
    // 상태는 이 목록으로 읽는다(다른 목록의 작업을 이 목록 결과로 쓰지 않게)
    expect(fetchConstituentsCollectStatus).toHaveBeenCalledWith(["069500", "229200"]);
  });

  it("진행 중 작업이 있으면 화면을 열 때 이어서 따라간다(읽기만 · 새로 시작하지 않음)", async () => {
    fetchConstituentsCollectStatus.mockResolvedValueOnce(
      doneJob({ state: "running", done: 1, batch_index: 1, batch_total: 3, total: 30, items: [] }),
    );
    render(<Harness onDone={vi.fn()} />);
    await waitFor(() =>
      expect(screen.getByTestId("cst-collect-line").textContent).toBe(
        "1/3 묶음 받는 중 — 받을 ETF 30개 중 1개 끝 · 목표일 11/13",
      ),
    );
    expect(postConstituentsCollect).not.toHaveBeenCalled();
  });

  it("탭을 바꾼 사이 작업이 끝나도 분석을 다시 읽는다(지적 frontend#2) · 수집 상태 줄은 탭과 상관없이 남는다", async () => {
    fetchConstituentsCollectStatus
      .mockResolvedValueOnce(doneJob({ state: "running", done: 0, items: [] }))
      .mockResolvedValue(doneJob());
    const onDone = vi.fn();
    render(<Harness onDone={onDone} analysis={analysis()} />);
    await waitFor(() => expect(screen.getByTestId("cst-collect-line")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "탭 바꾸기" })); // 구성종목 탭이 내려감
    expect(screen.queryByText("상위 구성종목")).toBeNull();
    expect(screen.getByTestId("cst-collect-line")).toBeTruthy(); // 위쪽 상태 줄은 그대로
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1), { timeout: 4000 });
  });

  it("다른 목록의 작업이 돌면 그 작업을 이 목록 결과로 보이지 않는다(지적 frontend#1)", async () => {
    fetchConstituentsCollectStatus
      .mockResolvedValueOnce({
        state: "idle",
        job_id: null,
        stored: true,
        target_date: "2026-11-13",
        total: 2,
        needs_check: 2,
        counts: { not_checked: 2 },
        items: [],
        other_job: { total: 30, done: 4, started_at: "t" },
      })
      .mockResolvedValue({
        state: "idle",
        job_id: null,
        stored: true,
        target_date: "2026-11-13",
        total: 2,
        needs_check: 2,
        counts: { not_checked: 2 },
        items: [],
        other_job: { total: 30, done: 9, started_at: "t" },
      });
    render(<Harness onDone={vi.fn()} />);
    await waitFor(() =>
      expect(screen.getByTestId("cst-other-list").textContent).toBe(
        "다른 목록(30개)을 받는 중(4개 끝) — 끝난 뒤 이 목록의 [구성종목 수집]을 누르세요",
      ),
    );
    expect((screen.getByRole("button", { name: /구성종목 수집/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByTestId("cst-collect-line").textContent).toContain("저장 기록 기준 상태");
    expect(screen.getByTestId("cst-collect-line").textContent).not.toContain("30개");
  });

  it("POST 가 다른 목록의 작업을 돌려주면 그 개수를 이 목록 결과로 쓰지 않는다", async () => {
    fetchConstituentsCollectStatus.mockResolvedValue({ state: "idle", job_id: null, items: [] });
    postConstituentsCollect.mockResolvedValue(
      doneJob({ state: "running", other_list: true, total: 30, done: 2, tickers: ["X"], items: [] }),
    );
    render(<Harness onDone={vi.fn()} />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /구성종목 수집/ }));
    });
    expect(screen.getByTestId("cst-other-list").textContent).toContain("다른 목록(30개)을 받는 중");
    expect(screen.queryByTestId("cst-collect-line")).toBeNull();
  });

  it("작업이 없으면 저장 기록으로 만든 상태를 보인다(서버를 다시 켠 뒤 · 지적 backend#7)", async () => {
    fetchConstituentsCollectStatus.mockResolvedValueOnce({
      state: "idle",
      job_id: null,
      stored: true,
      stored_status: "ok",
      target_date: "2026-11-13",
      total: 2,
      needs_check: 1,
      counts: { existing: 1, target_wait: 1 },
      items: [],
      other_job: null,
    });
    render(<Harness onDone={vi.fn()} />);
    await waitFor(() =>
      expect(screen.getByTestId("cst-collect-line").textContent).toBe(
        "저장 기록 기준 상태(목표일 11/13) — 후보 2개 · 목표일 이상 구성 1 · 목표일 자료 대기 1 · 다시 확인 필요 1 — [구성종목 수집]으로 받습니다",
      ),
    );
  });

  it("검증자 r1 F4(같은 뿌리) — 진입 때 상태 읽기가 수집 시작 뒤 늦게 와도 진행 중 작업을 덮지 않는다", async () => {
    let resolveOld!: (v: unknown) => void;
    fetchConstituentsCollectStatus
      .mockReturnValueOnce(new Promise((r) => (resolveOld = r))) // 진입 때 읽기(늦음)
      .mockResolvedValue(doneJob()); // 상태 확인
    postConstituentsCollect.mockResolvedValue(doneJob({ state: "running", done: 0, items: [] }));
    const onDone = vi.fn();
    render(<Harness onDone={onDone} />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /구성종목 수집/ }));
    });
    expect(screen.getByTestId("cst-collect-line").textContent).toContain("받는 중");
    await act(async () => {
      resolveOld({ state: "idle", job_id: null, stored: true, target_date: "2026-11-13", total: 2, needs_check: 2, counts: { not_checked: 2 }, items: [], other_job: null });
    });
    // 늦은 진입 응답(저장 기록 상태)이 진행 중 작업을 덮지 않음 · 따라가기 계속 → 끝나면 다시 읽기 한 번
    expect(screen.getByTestId("cst-collect-line").textContent).toContain("받는 중");
    expect(onDone).not.toHaveBeenCalled();
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1), { timeout: 4000 });
    expect(screen.getByTestId("cst-collect-line").textContent).toContain("수집 끝");
  });

  it("안내문이 실제 수집 깊이와 같은 숫자를 말한다", () => {
    render(<CollectHelp />);
    expect(screen.getByTestId("cst-collect-help").textContent).toContain(
      `구성종목은 ETF마다 비중 상위 ${CONSTITUENTS_TOP_K}개까지 받습니다`,
    );
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
        collect={noCollect}
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
        collect={noCollect}
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
        collect={noCollect}
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
        collect={noCollect}
      />,
    );
    expect(screen.getByText(/상위\s*10건 기준입니다/)).toBeTruthy();
  });

  it("응답의 overlap_top_k 가 10 이 아니어도 그 값을 쓴다", () => {
    // 위 케이스는 입력이 옛 fallback 값(`?? 10`)과 같은 10 이라, 그것만으로는
    // fallback 제거를 구별하지 못한다(검증자 r2 B-6 참고). 10 이 아닌 값으로
    // "응답 값을 그대로 쓴다" 는 계약을 고정한다.
    const a = analysis();
    render(
      <ConstituentsTab
        draft={draft()}
        analysis={{ ...a, overlap_top_k: 7 }}
        collect={noCollect}
      />,
    );
    expect(screen.getByText(/상위\s*7건 기준입니다/)).toBeTruthy();
    expect(screen.queryByText(/상위\s*10건 기준입니다/)).toBeNull();
  });
});

describe("POC6-31 — ETF별 실제 구성일(판정 §1 첫째 · Q7)", () => {
  it("순위 끝날과 같으면 'M/D 기준 구성' · 끝날보다 새면 '현재 편입 참고' · 원천 기준일 미확인 표시", () => {
    const d = { ...draft(), list_condition: { basis: "one_month" as const, side: "top" as const, start: "2026-10-14", end: "2026-11-13", filters: {} as ETFExposureDraft["filters"] } };
    render(
      <ConstituentsTab
        draft={d}
        analysis={analysis([
          item({ etf_ticker: "069500", asof: "2026-11-13", asof_confirmed: true }),
          item({ etf_ticker: "229200", asof: "2026-11-14", asof_confirmed: false }),
        ])}
        collect={noCollect}
      />,
    );
    expect(screen.getByText("11/13 기준 구성")).toBeTruthy();
    expect(screen.getByText("11/14 구성 · 현재 편입 참고 · 원천 기준일 미확인")).toBeTruthy();
  });
});
