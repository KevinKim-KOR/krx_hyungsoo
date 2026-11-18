// POC6-31 STEP 4(PLAN C22 · C24 · 목업 M3) — 구성종목 비교 블록: 확인 범위 먼저 · 상태별 안내 · 계산 입력 펼침 · 금액 없음.
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import PairExposureBlock, { usePairExposure, type PairPhase } from "./PairExposureBlock";
import type { PairQuery } from "@/lib/api/pairExposure";

const fetchPairExposure = vi.fn();
vi.mock("@/lib/api/pairExposure", async (orig) => ({
  ...(await orig<typeof import("@/lib/api/pairExposure")>()),
  fetchPairExposure: (...a: unknown[]) => fetchPairExposure(...a),
}));
import { pairOk } from "@/lib/pairExposureTestFixtures";

const ok = (over = {}) => ({ phase: "success" as const, data: pairOk({ candidate: "C", holding: "H" }, over) });

describe("구성종목 비교 블록", () => {
  it("확인 범위가 표보다 먼저 · 표 = 후보 비중 · 고른 보유 비중 · 내 보유 전체 · Q19 문장", () => {
    render(<PairExposureBlock q={ok()} hasPick />);
    const scope = screen.getByTestId("pe-scope");
    const table = screen.getByTestId("pe-table");
    expect(scope.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // 기준일 줄 = 서버가 준 글 그대로(미리보기 원문과 같은 글 · 검증자 STEP 4~5 r1 B-6)
    expect(screen.getByTestId("pe-dates").textContent).toBe(pairOk({ candidate: "C", holding: "H" }).date_line);
    expect(table).toHaveTextContent("일라이 릴리29.98%3.12%2.65%");
    expect(screen.getByTestId("pe-formula")).toHaveTextContent("합계에서 반올림 2.65%");
    expect(screen.getByText(/추가 금액과 자금 출처가 있어야/)).toBeInTheDocument();
    expect(screen.getByTestId("pe-held")).toHaveTextContent("후보를 지금 보유하지 않음");
    expect(screen.getByTestId("pe-block").textContent).not.toMatch(/\d원/);
  });

  it("합계에서 빠진 ETF 는 노출 옆에 서버 사유 글(저장 범위 밖 · 편입 비중 확인 불가) · 다른 구성일은 참고(합계 밖)", () => {
    const base = pairOk({ candidate: "C", holding: "H" });
    const s0 = base.stocks[0];
    const stocks = [
      {
        ...s0,
        pair: { state: "out_of_range" as const, stored_rows: 30, stored_sum: "97.4" },
        exposure: {
          ...s0.exposure,
          unknown: [{ ticker: "A", name: "보유A", holding_weight: "12", range: "depth", stored_rows: 30 }],
          unknown_weight: "12",
        },
        reference: [
          { ticker: "R", name: "보유R", asof: "2026-11-12", holding_weight: "3.1", constituent_weight: "2.1", product: "0.0651" },
        ],
      },
    ];
    const note = "저장 범위 밖 미확인 ETF 1개 · 평가액 12.00% · 편입 비중 확인 불가 ETF 1개 · 평가액 40.00%";
    render(<PairExposureBlock q={ok({ stocks, stock_notes: { "LLY.N": note } })} hasPick />);
    expect(screen.getByTestId("pe-table")).toHaveTextContent("저장 범위에서 미확인(30행 · 저장 행 합 97.40%)");
    // 합계에서 빠진 사유 = 서버 글 그대로(사유별 · 검증자 STEP 4~5 r2 F14)
    expect(screen.getByTestId("pe-note").textContent).toBe(` · ${note}`);
    expect(screen.getByTestId("pe-reference")).toHaveTextContent("보유R 2026-11-12 — 일라이 릴리 2.10%");
  });

  it.each([
    ["no_holdings", "등록 보유 없음"],
    ["no_etf_list", "ETF 목록을 읽지 못해"],
  ] as const)("%s — 수치 없이 사유만", (status, text) => {
    render(<PairExposureBlock q={ok({ status, stocks: [] })} hasPick />);
    expect(screen.getByTestId("pe-status")).toHaveTextContent(text);
    expect(screen.queryByTestId("pe-table")).toBeNull();
  });

  it.each([
    ["holdings_unreadable", "보유 목록을 읽지 못했습니다", null],
    ["no_weight_basis", "비중 확인 불가", "x"],
  ] as const)("%s — 사유 + 짝 칸(편입 비중)은 그대로 · 노출만 '비중 확인 불가'(검토 지적 frontend#2)", (status, text, sc) => {
    const base = pairOk({ candidate: "C", holding: "H" });
    const stocks = base.stocks.map((s) => ({ ...s, exposure: null, reference: [] }));
    render(<PairExposureBlock q={ok({ status, stocks, scope: sc ? base.scope : null })} hasPick />);
    expect(screen.getByTestId("pe-status")).toHaveTextContent(text);
    expect(screen.getByTestId("pe-table")).toHaveTextContent("일라이 릴리29.98%3.12%비중 확인 불가");
    expect(screen.queryByTestId("pe-included")).toBeNull();
  });

  it("후보 구성 자료가 없으면 비교하지 않음(겹침 없음 아님) · 확인 범위는 보인다", () => {
    const base = pairOk({ candidate: "C", holding: "H" });
    render(
      <PairExposureBlock
        q={ok({ status: "no_candidate_data", stocks: [], candidate: { ...base.candidate, state: "unconfirmed", asof: "2026-06-22" } })}
        hasPick
      />,
    );
    expect(screen.getByTestId("pe-no-candidate")).toHaveTextContent(
      "원천 기준일 미확인(2026-06-22 보존 자료) — 비교하지 않음(겹침 없음이라는 뜻 아님)",
    );
    // POC6-32 V2(검토 F6) — 「ETF 구성종목」은 메뉴가 아니다: 상세 화면을 여는 버튼 경로로 안내
    expect(screen.getByTestId("pe-no-candidate")).toHaveTextContent(
      "[구성종목 보기]로 그 ETF 를 연 뒤 [구성종목 수집]을 누르고 다시 불러오세요.",
    );
    expect(screen.getByTestId("pe-no-candidate")).not.toHaveTextContent("「ETF 구성종목」에서");
    expect(screen.getByTestId("pe-scope")).toBeInTheDocument();
    expect(screen.queryByTestId("pe-table")).toBeNull();
  });

  it("읽는 중 · 실패 · 후보 없음", () => {
    const { rerender } = render(<PairExposureBlock q={{ phase: "loading" }} hasPick />);
    expect(screen.getByText("구성종목 비교 읽는 중...")).toBeInTheDocument();
    rerender(<PairExposureBlock q={{ phase: "error" }} hasPick />);
    expect(screen.getByTestId("pe-error")).toHaveTextContent("[다시 불러오기]");
    rerender(<PairExposureBlock q={{ phase: "idle" }} hasPick={false} />);
    expect(screen.getByText("후보를 고르면 구성종목 비교를 봅니다.")).toBeInTheDocument();
  });

  it("고른 보유가 개별 주식이면 그 평가 비중을 따로 적는다", () => {
    const base = pairOk({ candidate: "C", holding: "005930" });
    render(
      <PairExposureBlock
        q={ok({ holding: { ...base.holding!, kind: "stock", weight: "6.2", state: null, asof: null, stored_rows: null, range: null } })}
        hasPick
      />,
    );
    expect(screen.getByTestId("pe-holding-stock")).toHaveTextContent("전체 보유에서 차지하는 평가 비중 6.20%");
  });
});

describe("usePairExposure — 고른 종목이 바뀐 바로 그 그림에도 예전 비교를 보이지 않는다", () => {
  const q = (candidate: string): PairQuery => ({
    candidate,
    holding: "H",
    screen: "holding_candidate_compare",
    basis: "one_month",
    side: "top",
    rank: 1,
    start_date: "2026-10-14",
    end_date: "2026-11-13",
    filters: { exclude_inverse: true },
  });

  it("후보를 바꾼 첫 그림 = 읽는 중(예전 후보의 비교가 아님) · 늦게 온 예전 응답은 버림", async () => {
    const seen: { key: string; phase: PairPhase["phase"]; cand?: string }[] = [];
    let release: (v: unknown) => void = () => {};
    fetchPairExposure.mockImplementation((x: PairQuery) =>
      x.candidate === "A"
        ? Promise.resolve(pairOk(x))
        : new Promise((r) => {
            release = r;
          }),
    );
    function Harness({ c }: { c: string }) {
      const p = usePairExposure(q(c));
      seen.push({ key: p.key, phase: p.phase, cand: p.phase === "success" ? p.data.candidate.ticker : undefined });
      return null;
    }
    const { rerender } = render(<Harness c="A" />);
    await waitFor(() => expect(seen.some((x) => x.phase === "success")).toBe(true));
    seen.length = 0;
    rerender(<Harness c="B" />);
    // B 의 주소로 그린 어떤 그림도 A 의 비교(success · 후보 A)를 보이지 않는다
    expect(seen.filter((x) => x.key.includes("candidate=B")).every((x) => x.phase === "loading")).toBe(true);
    expect(seen.some((x) => x.cand === "A" && x.key.includes("candidate=B"))).toBe(false);
    release(pairOk({ candidate: "B", holding: "H" }));
    await waitFor(() => expect(seen.at(-1)?.cand).toBe("B"));
  });
});

describe("구성종목 비교 블록 — 검증자 STEP 4~5 r1 정정", () => {
  it("확인한 구성이 없는 주식은 0.00% 가 아니라 '확인 불가'(F10) · 고른 보유 구성일이 다르면 참고 표시(F12)", () => {
    const base = pairOk({ candidate: "C", holding: "H" });
    const s0 = base.stocks[0];
    const stocks = [{ ...s0, exposure: { ...s0.exposure!, terms: [], raw: null, value: null } }];
    render(<PairExposureBlock q={ok({ stocks, pair_dates_differ: true, date_line: "기준일: 서버 글" })} hasPick />);
    const table = screen.getByTestId("pe-table");
    expect(table).toHaveTextContent("확인 불가 · 확인한 구성 없음");
    expect(table).not.toHaveTextContent("0.00%");
    expect(table).toHaveTextContent("3.12%(구성일 다름 · 참고)");
    expect(screen.getByTestId("pe-dates").textContent).toBe("기준일: 서버 글");
  });
});
