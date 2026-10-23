// POC6-01 — 시장 흐름(수급 · 환율 · 유가) 화면 · 복사문 · 미리보기 기간 연결(설계 POC5-28 개정 3 §4 ·
// PLAN 판정 2026-10-20 · POC6-01 판정 §5 · 사용자 목업 확인 2026-10-20).
// - 기간 버튼은 받은 자료를 다시 자를 뿐 다시 조회하지 않고, 고른 기간은 복사문 · 미리보기와 공유한다.
// - 문장 · 꼬리표 · 사건 · 해석은 서버 응답 그대로. 늦음 · 수급 없음 · D 없음 · 모양 다른 응답을 따로 본다.
// - 차트 가로축은 달력 날짜(저장 순서 아님). 실제 request · 응답 모양 검사를 쓰고 fetch 만 가짜다.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";

import FlowTimeChart from "@/app/components/charts/FlowTimeChart";
import type { MarketCandidate, MarketContext } from "@/lib/api";
import { MARKET_FLOW_KEY, MARKET_INVALIDATION_KEYS } from "@/lib/api/dashboardKeys";
import { isMarketFlowContext, type FlowPoint, type MarketFlowContext } from "@/lib/api/marketFlow";
import { __resetQueryCache } from "@/lib/api/queryCache";
import { loadAISessionsDraft } from "@/lib/aiSessionsDraft";
import { buildMarketDiscoveryCopyText } from "@/lib/marketDiscoveryCopyText";
import { __resetMarketFlowPeriod, getMarketFlowPeriod, setMarketFlowPeriod } from "@/lib/marketFlowPeriod";
import { MARKET_FLOW_TEXT_UNAVAILABLE, marketFlowCopySection } from "@/lib/marketFlowText";
import TransferToAISessionsCard from "../TransferToAISessionsCard";

import MarketFlowCard from "./MarketFlowCard";
import TodayFlowLines from "./TodayFlowLines";

const D = "2026-10-16";

function weekdays(start: string, end: string): string[] {
  const out: string[] = [];
  for (let t = Date.parse(`${start}T00:00:00Z`); t <= Date.parse(`${end}T00:00:00Z`); t += 86_400_000) {
    const d = new Date(t);
    if (d.getUTCDay() % 6 !== 0) out.push(d.toISOString().slice(0, 10));
  }
  return out;
}

const DAYS = weekdays("2026-04-01", D);
const pts = (f: (i: number) => number, until = D): FlowPoint[] =>
  DAYS.filter((d) => d <= until).map((d, i) => [d, f(i)] as FlowPoint);

function per(code: string, label: string, boundary: string) {
  return {
    label,
    boundary,
    start: DAYS.find((d) => d > boundary) ?? null,
    end: D,
    lines: [`${label} 요약 줄(${code})`],
  };
}

function ctx(over: Partial<MarketFlowContext> = {}): MarketFlowContext {
  return {
    generated_at: "2026-10-16T18:00:00+09:00",
    D,
    has_flows: true,
    series: {
      kospi: { label: "코스피", unit: "pt", E: D, points: pts((i) => 2500 + i), collected_at: null },
      usdkrw: { label: "원/달러", unit: "원", E: D, points: pts((i) => 1400 + i / 2), collected_at: "2026-10-16T09:00:00Z" },
      wti: { label: "WTI", unit: "달러", E: "2026-10-15", points: pts(() => 70, "2026-10-15"), collected_at: "2026-10-16T09:00:00Z" },
      flows: {
        label: "투자자별 순매수",
        unit: "원",
        E: D,
        investors: {
          foreign: pts(() => -1e11),
          individual: pts(() => 8e10),
          institution: pts(() => 1e10),
          other_corp: pts(() => 1e10),
        },
        collected_at: "2026-10-16T09:00:00Z",
      },
    },
    periods: {
      "1M": per("1M", "1개월", "2026-09-16"),
      "3M": per("3M", "3개월", "2026-07-16"),
      "6M": per("6M", "6개월", "2026-04-16"),
      YTD: per("YTD", "연초 이후", "2025-12-31"),
    },
    windows: { lines: ["외국인 최근 20거래일 -2.0조원(일평균 -1,000억원)"] },
    short_lines: [
      { text: "코스피 10/16 · 직전 대비 +1.00pt(+0.04%)", flags: ["최근 변화 확대 · 이전 20회 평균 변화의 3.4배"] },
      { text: "원/달러 10/16 · 직전 대비 +0.50원(+0.03%)", flags: ["비교 자료 부족"] },
      { text: "WTI 10/15 · 직전 대비 0.00달러(0.00%)", flags: ["늦음 — 최신 10/15(D 10/16 보다 이전)"] },
    ],
    events: [
      { date: "2026-10-16", series: "코스피", kind: "expansion", text: "10/16 코스피 변화 확대" },
      { date: "2026-08-03", series: "외국인", kind: "flow", text: "8/3 외국인 순매도 규모 확대" },
    ],
    event_check: { checked: ["코스피", "원/달러", "WTI", "외국인", "기관계"], unchecked: [], unchecked_text: null, empty_text: null },
    interpretation: {
      "1M": { rows: [["관측 문장 1M", "가능성 문장 1M", "다른 설명 1M"]], notes: [] },
      "3M": { rows: [], notes: ["지금 조합에 해당하는 해석 규칙 없음(설명을 만들어 내지 않음)"] },
      "6M": { rows: [["관측 문장 A", "가능성 문장 A", "다른 설명 A"]], notes: [] },
      YTD: {
        rows: [],
        notes: [
          "확인 못 한 조합: 코스피 하락 · 외국인 순매도 · 원/달러 — 외국인 수급 부분 집계(58/59일)",
          "확인한 조합에는 해당하는 해석 규칙 없음(설명을 만들어 내지 않음)",
        ],
      },
    },
    limits: ["한계 문장"],
    status: [
      { key: "kospi", label: "코스피", E: D, collected_at: null },
      { key: "flows", label: "투자자별 순매수", E: D, collected_at: "2026-10-16T09:00:00Z" },
      { key: "usdkrw", label: "원/달러", E: D, collected_at: "2026-10-16T09:00:00Z" },
      { key: "wti", label: "WTI", E: "2026-10-15", collected_at: "2026-10-16T09:00:00Z" },
    ],
    today_lines: ["시장 흐름 6개월: 오늘 첫 줄", "최근 큰 변화: 오늘 둘째 줄"],
    ai_text: { "1M": "[시장 흐름 글 1M]", "3M": "[시장 흐름 글 3M]", "6M": "[시장 흐름 글 6M]", YTD: "[시장 흐름 글 YTD]" },
    ...over,
  };
}

function serve(body: unknown, status = 200) {
  vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://api.test");
  const stub = vi.fn(async (url: string) => {
    expect(String(url)).toBe("http://api.test/market/flow-context");
    return { ok: status < 400, status, text: async () => JSON.stringify(body) };
  });
  vi.stubGlobal("fetch", stub);
  return stub;
}

beforeEach(() => {
  __resetQueryCache();
  __resetMarketFlowPeriod();
  window.sessionStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("응답 모양 검사", () => {
  it("화면이 쓰는 칸이 다 있으면 통과 · 하나라도 어긋나면 거절", () => {
    expect(isMarketFlowContext(ctx())).toBe(true);
    expect(isMarketFlowContext(ctx({ D: null }))).toBe(true);
    expect(isMarketFlowContext({})).toBe(false);
    expect(isMarketFlowContext(null)).toBe(false);
    const { today_lines: _drop, ...noToday } = ctx();
    void _drop;
    expect(isMarketFlowContext(noToday)).toBe(false);
    expect(isMarketFlowContext({ ...ctx(), windows: {} })).toBe(false);
    expect(isMarketFlowContext({ ...ctx(), today_lines: [1] })).toBe(false);
    expect(isMarketFlowContext({ ...ctx(), interpretation: { "6M": "x" } })).toBe(false);
    expect(isMarketFlowContext({ ...ctx(), interpretation: { "6M": [["a", "b", "c"]] } })).toBe(false);
    const { event_check: _ec, ...noCheck } = ctx();
    void _ec;
    expect(isMarketFlowContext(noCheck)).toBe(false);
  });
});

describe("「요즘 잘 오르는 ETF」 시장 흐름 카드", () => {
  it("기본 6개월 · 기간 버튼은 다시 조회하지 않고 공유 기간을 바꾼다", async () => {
    const stub = serve(ctx());
    render(<MarketFlowCard />);
    expect(await screen.findByText("6개월 요약 줄(6M)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "6개월" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("가능한 해석 — 6개월 기준 · 확정이 아님")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "1개월" }));
    expect(screen.getByText("1개월 요약 줄(1M)")).toBeInTheDocument();
    expect(screen.queryByText("6개월 요약 줄(6M)")).toBeNull();
    // 해석도 같은 기간(기간 선택은 묶음 전체에 하나)
    expect(screen.getByText("가능한 해석 — 1개월 기준 · 확정이 아님")).toBeInTheDocument();
    expect(screen.getByText("관측 문장 1M")).toBeInTheDocument();
    expect(screen.queryByText("관측 문장 A")).toBeNull();
    expect(screen.getByRole("button", { name: "1개월" })).toHaveAttribute("aria-pressed", "true");
    expect(getMarketFlowPeriod()).toBe("1M");
    fireEvent.click(screen.getByRole("button", { name: "3개월" }));
    expect(screen.getByText("지금 조합에 해당하는 해석 규칙 없음(설명을 만들어 내지 않음)")).toHaveClass("tc-muted");
    // 확인 못 한 조합은 '해당 없음'과 구분해 경고 색으로(서버 문장 그대로)
    fireEvent.click(screen.getByRole("button", { name: "연초 이후" }));
    expect(
      screen.getByText("확인 못 한 조합: 코스피 하락 · 외국인 순매도 · 원/달러 — 외국인 수급 부분 집계(58/59일)"),
    ).toHaveClass("tc-warn");
    expect(screen.getByText("확인한 조합에는 해당하는 해석 규칙 없음(설명을 만들어 내지 않음)")).toHaveClass("tc-muted");
    fireEvent.click(screen.getByRole("button", { name: "연초 이후" }));
    expect(screen.getByText("연초 이후 요약 줄(YTD)")).toBeInTheDocument();
    expect(stub).toHaveBeenCalledTimes(1);
  });

  it("꼬리표 종류별 표시 · 최근 사건 · 해석 · 늦은 자료 경고", async () => {
    serve(ctx());
    const { container } = render(<MarketFlowCard />);
    await screen.findByText("6개월 요약 줄(6M)");
    expect(screen.getByText("비교 자료 부족")).toHaveClass("mf-flag", "mf-flag-na");
    expect(screen.getByText("늦음 — 최신 10/15(D 10/16 보다 이전)")).toHaveClass("mf-flag", "mf-flag-late");
    expect(screen.getByText("최근 변화 확대 · 이전 20회 평균 변화의 3.4배")).toHaveClass("mf-flag");
    expect(screen.getByText("10/16 코스피 변화 확대")).toBeInTheDocument();
    expect(screen.getByText("관측 문장 A")).toBeInTheDocument();
    const status = container.querySelector(".mf-status") as HTMLElement;
    expect(status.textContent).toContain("늦음: WTI 10/15(D 10/16 보다 이전)");
    expect(status.textContent).toContain("코스피 10/16(수집 —)");
    expect(status.textContent).toContain("원/달러 10/16(수집 10/16 18:00)"); // UTC 09:00 → 한국 18:00
  });

  it("사건 표시 점은 기간 경계 뒤만 · 1개월로 줄이면 8/3 수급 · 경계일(9/16) 코스피 사건 점은 사라진다", async () => {
    const edge = { date: "2026-09-16", series: "코스피", kind: "range", text: "9/16 코스피 범위 아래" };
    serve(ctx({ events: [...ctx().events, edge] }));
    render(<MarketFlowCard />);
    await screen.findByText("6개월 요약 줄(6M)");
    expect(screen.getByTestId("mf-chart-kospi-mark-kospi-2026-10-16")).toBeInTheDocument();
    expect(screen.getByTestId("mf-chart-kospi-mark-kospi-2026-09-16")).toBeInTheDocument();
    expect(screen.getByTestId("mf-chart-flows-mark-foreign-2026-08-03")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "1개월" }));
    expect(screen.queryByTestId("mf-chart-flows-mark-foreign-2026-08-03")).toBeNull();
    // 경계일 값은 선의 시작점(기간 직전 종가)으로만 그리고, 그날 사건은 기간 밖이다.
    expect(screen.queryByTestId("mf-chart-kospi-mark-kospi-2026-09-16")).toBeNull();
    expect(screen.getByTestId("mf-chart-kospi-mark-kospi-2026-10-16")).toBeInTheDocument();
  });

  it("같은 자료 · 같은 날 사건 두 개(변화 확대 + 범위 아래)는 점 하나 · 사건 줄은 둘 다 · key 중복 경고 없음", async () => {
    // POC6-07 실화면 중 발견(2026-10-23) — 10/13 · 10/15 코스피에 두 종류 사건이 함께 있으면 같은 key 점이 두 번 생겼다.
    const twin = { date: "2026-10-16", series: "코스피", kind: "range", text: "10/16 코스피 직전 20개 관측 범위 아래" };
    serve(ctx({ events: [...ctx().events, twin] }));
    const err = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      render(<MarketFlowCard />);
      await screen.findByText("6개월 요약 줄(6M)");
      expect(screen.getAllByTestId("mf-chart-kospi-mark-kospi-2026-10-16")).toHaveLength(1);
      expect(screen.getByText("10/16 코스피 변화 확대")).toBeInTheDocument();
      expect(screen.getByText("10/16 코스피 직전 20개 관측 범위 아래")).toBeInTheDocument();
      expect(err.mock.calls.some((c) => String(c[0]).includes("same key"))).toBe(false);
    } finally {
      err.mockRestore();
    }
  });

  it("1조원 아래 누적은 억원 정수(-0조원으로 보이지 않음)", async () => {
    const small = ctx();
    small.series.flows!.investors.foreign = pts((i) => (i === DAYS.length - 1 ? -4.8e10 : 0));
    serve(small);
    render(<MarketFlowCard />);
    const readout = await screen.findByTestId("market-flow-readout");
    expect(readout.textContent).toContain("외국인 -480억원");
    expect(readout.textContent).not.toContain("0조원");
  });

  it("사건이 없으면 서버 문장 — 모두 비교했을 때만 '큰 변화 없음' · 아니면 확인 못 한 자료(경고 색)", async () => {
    const none = "최근 5개 관측: 표시 기준(이전 20회 평균 변화의 3배 · 직전 20개 범위)에 해당하는 큰 변화 없음 — 안정이라는 뜻은 아님";
    serve(
      ctx({
        events: [],
        event_check: { checked: ["코스피"], unchecked: [], unchecked_text: null, empty_text: none },
      }),
    );
    const { unmount } = render(<MarketFlowCard />);
    expect(await screen.findByTestId("market-flow-events-empty")).toHaveTextContent(none);
    expect(screen.getByTestId("market-flow-events-empty")).toHaveClass("tc-muted");
    unmount();
    __resetQueryCache();
    const partial = "최근 5개 관측: 큰 변화를 확인하지 못함 — 원/달러 자료 없음 · WTI 자료 없음";
    serve(
      ctx({
        events: [],
        event_check: {
          checked: [],
          unchecked: [{ label: "원/달러", reason: "자료 없음" }],
          unchecked_text: "확인 못 한 자료 — 원/달러 자료 없음 · WTI 자료 없음",
          empty_text: partial,
        },
      }),
    );
    render(<MarketFlowCard />);
    expect(await screen.findByTestId("market-flow-events-empty")).toHaveTextContent(partial);
    expect(screen.getByTestId("market-flow-events-empty")).toHaveClass("tc-warn");
    expect(screen.queryByText(/큰 변화 없음/)).toBeNull();
    expect(screen.queryByTestId("market-flow-events-unchecked")).toBeNull(); // 같은 사유를 두 번 쓰지 않음
  });

  it("사건이 있어도 확인 못 한 자료는 함께 적는다", async () => {
    serve(
      ctx({
        event_check: {
          checked: ["코스피"],
          unchecked: [{ label: "WTI", reason: "비교 자료 부족" }],
          unchecked_text: "확인 못 한 자료 — WTI 비교 자료 부족",
          empty_text: null,
        },
      }),
    );
    render(<MarketFlowCard />);
    expect(await screen.findByTestId("market-flow-events-unchecked")).toHaveTextContent(
      "확인 못 한 자료 — WTI 비교 자료 부족",
    );
    expect(screen.getByText("10/16 코스피 변화 확대")).toBeInTheDocument();
  });

  it("고른 날 읽기 줄 = 기본 D · 좌우 화살표로 코스피 거래일을 옮기고 늦은 자료는 그 이전 값 날짜를 붙인다", async () => {
    serve(ctx());
    render(<MarketFlowCard />);
    const readout = await screen.findByTestId("market-flow-readout");
    expect(readout.textContent).toContain(D);
    expect(readout.textContent).toContain("코스피 2,");
    // 누적 = 기간 시작 직전 0 · 첫 거래일 포함(6개월 경계 4/16 뒤 ~ D 의 모든 날).
    const n6 = DAYS.filter((d) => d > "2026-04-16" && d <= D).length;
    const jo6 = ((-1e11 * n6) / 1e12).toLocaleString("ko-KR", { maximumFractionDigits: 1 });
    expect(readout.textContent).toContain(`외국인 ${jo6}조원`);
    expect(readout.textContent).toMatch(/WTI 70\.00달러\(10\/15\)/);
    const plot = within(screen.getByTestId("mf-chart-kospi")).getByRole("group");
    fireEvent.keyDown(plot, { key: "ArrowLeft" });
    expect(screen.getByTestId("market-flow-readout").textContent).toContain("2026-10-15");
    expect(screen.getByTestId("market-flow-readout").textContent).not.toMatch(/WTI 70\.00달러\(/);
    fireEvent.keyDown(plot, { key: "ArrowRight" });
    fireEvent.keyDown(plot, { key: "ArrowRight" });
    expect(screen.getByTestId("market-flow-readout").textContent).toContain(D);
  });

  it("수급이 없으면 수급 차트 대신 '자료 없음' · 읽기 줄에 투자자 없음(0 으로 채우지 않음)", async () => {
    serve(ctx({ has_flows: false }));
    render(<MarketFlowCard />);
    await screen.findByText("6개월 요약 줄(6M)");
    expect(screen.queryByTestId("mf-chart-flows")).toBeNull();
    expect(screen.getByText(/투자자별 누적 순매수 — 자료 없음/)).toBeInTheDocument();
    expect(screen.getByTestId("market-flow-readout").textContent).not.toContain("외국인");
  });

  it("D 가 없으면 서버 첫 줄만 · 차트 없음", async () => {
    serve(ctx({ D: null, today_lines: ["시장 흐름: 코스피 · 수급이 함께 저장된 날이 없습니다"] }));
    render(<MarketFlowCard />);
    expect(await screen.findByText("시장 흐름: 코스피 · 수급이 함께 저장된 날이 없습니다")).toBeInTheDocument();
    expect(screen.queryByTestId("mf-chart-kospi")).toBeNull();
    expect(screen.queryByTestId("market-flow-readout")).toBeNull();
  });

  it("모양이 다른 응답 · 서버 오류는 카드 안 실패 문구(화면 전체를 깨지 않음)", async () => {
    serve({ status: "ok", items: [] });
    const { unmount } = render(<MarketFlowCard />);
    expect(await screen.findByText("시장 흐름 자료를 불러오지 못했습니다.")).toBeInTheDocument();
    unmount();
    __resetQueryCache();
    serve({ detail: "x" }, 500);
    render(<MarketFlowCard />);
    expect(await screen.findByText("시장 흐름 자료를 불러오지 못했습니다.")).toBeInTheDocument();
  });
});

describe("「오늘의 투자 점검」 코스피 카드 두 줄", () => {
  it("서버 today_lines 그대로 두 줄", async () => {
    serve(ctx());
    render(<TodayFlowLines />);
    expect(await screen.findByText("시장 흐름 6개월: 오늘 첫 줄")).toHaveClass("mf-today-main");
    expect(screen.getByText("최근 큰 변화: 오늘 둘째 줄")).toHaveClass("mf-today-sub");
  });

  it("조회 실패면 한 줄 실패 문구", async () => {
    serve({}, 500);
    render(<TodayFlowLines />);
    expect(await screen.findByText(/시장 흐름\(수급 · 환율 · 유가\) 자료를 불러오지 못했습니다/)).toBeInTheDocument();
  });
});

describe("날짜 가로축 차트", () => {
  it("저장 순서가 아니라 달력 날짜 위치에 그린다(빈 날 보간 없음)", () => {
    render(
      <FlowTimeChart
        title="t"
        domain={["2026-01-01", "2026-01-11"]}
        lines={[{ key: "a", label: "A", color: "#000", points: [["2026-01-01", 1], ["2026-01-02", 2], ["2026-01-11", 3]] }]}
        fmt={String}
        selected="2026-01-11"
        testId="c"
      />,
    );
    const d = screen.getByTestId("c-line-a").getAttribute("d") ?? "";
    expect(d.split(" ").map((s) => s.slice(1).split(",")[0])).toEqual(["0.00", "100.00", "1000.00"]);
  });

  it("값이 없으면 '이 기간에 저장된 값이 없습니다'", () => {
    render(<FlowTimeChart title="t" domain={["2026-01-01", "2026-01-11"]} lines={[]} fmt={String} selected="2026-01-11" />);
    expect(screen.getByText("이 기간에 저장된 값이 없습니다.")).toBeInTheDocument();
  });
});

describe("복사문 · 무효화", () => {
  it("고른 기간의 서버 글 그대로 · 없으면 '넣지 못함' 문구", () => {
    expect(marketFlowCopySection(ctx(), "3M")).toBe("[시장 흐름 글 3M]");
    expect(marketFlowCopySection(ctx({ ai_text: {} }), "3M")).toBe(MARKET_FLOW_TEXT_UNAVAILABLE);
    expect(marketFlowCopySection(null, "6M")).toBe(MARKET_FLOW_TEXT_UNAVAILABLE);
  });

  it("복사문에서는 [시스템 시장 판정] 다음 · 넘기지 않으면 구간 없음", () => {
    const base = {
      asof: D,
      filters: { exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true },
      candidates: [] as MarketCandidate[],
      marketContext: null,
    };
    const withFlow = buildMarketDiscoveryCopyText({ ...base, marketFlowText: "[시장 흐름 글 6M]" });
    const judge = withFlow.indexOf("[시스템 시장 판정]");
    const flow = withFlow.indexOf("[시장 흐름 글 6M]");
    expect(judge).toBeGreaterThan(-1);
    expect(flow).toBeGreaterThan(judge);
    expect(buildMarketDiscoveryCopyText(base)).not.toContain("[시장 흐름");
  });

  it("시장 갱신 완료 무효화 대상에 시장 흐름 키 포함", () => {
    expect(MARKET_INVALIDATION_KEYS).toContain(MARKET_FLOW_KEY);
  });

  it("AI 세션 전달 초안 질문 = 카드에서 고른 기간의 서버 글", async () => {
    serve(ctx());
    const CTX = { status: "ok", regime_label: "하락장", kodex200: { status: "ok" }, kospi: { status: "unavailable" }, warnings: [] } as unknown as MarketContext;
    const cand = [{ rank: 1, ticker: "0005D0", name: "후보", tags: [], returns: {} }] as unknown as MarketCandidate[];
    render(
      <>
        <MarketFlowCard />
        <TransferToAISessionsCard asof={D} filters={{ exclude_inverse: true, exclude_leveraged: true, exclude_synthetic: true, exclude_futures: true }} candidates={cand} linkedMarketRefreshId={null} marketContext={CTX} compact />
      </>,
    );
    await screen.findByText("6개월 요약 줄(6M)");
    fireEvent.click(screen.getByRole("button", { name: "3개월" }));
    fireEvent.click(screen.getByRole("button", { name: "AI Sessions로 넘기기" }));
    await waitFor(() => expect(loadAISessionsDraft()?.question_text).toContain("[시장 흐름 글 3M]"));
    expect(loadAISessionsDraft()?.question_text).not.toContain("[시장 흐름 글 6M]");
    setMarketFlowPeriod("6M");
  });
});
