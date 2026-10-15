// POC5-13 — 「오늘의 투자 점검」 '내가 가진 ETF' 칸 요약 띠(사용자 목업 결정 B안).
// 자리 = 보유 칸 제목 바로 아래 · 안내 문장 위. 순서 = 시장 국면 / PC 최근 20저장일 하락 구간 · 보유 평가 비중 /
// 구간 판정 가능 a/b종목(판정 Q3). 「확인 근거」 요약과 같은 조립 함수 · 같은 수. 최대 3개는 그대로.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import type { QueryState } from "@/lib/api/queryCache";
import type {
  EnrichedHoldingsResult,
  HoldingsDeclineBand,
  HoldingsMarketEvidenceItem,
  HoldingsMarketEvidenceResponse,
  MarketTopNResponse,
} from "@/lib/api";
import JudgmentQueueSection from "./JudgmentQueueSection";
import { buildRiskEvidenceRows } from "../holdings_risk_evidence/helpers";
import { buildDeclineSummary, fmtShare } from "../holdings_risk_evidence/declineSummary";

const MARKET = { phase: "error" } as QueryState<MarketTopNResponse>;

function holdingsOf(rows: [string, string, number | null][]): QueryState<EnrichedHoldingsResult> {
  return {
    phase: "success",
    stale: false,
    data: {
      items: rows.map(([ticker, name, ev]) => ({
        ticker, name, eval_amount: ev, invested_amount: 1000, price_missing: ev === null, calc_missing: ev === null,
      })),
    } as unknown as EnrichedHoldingsResult,
  };
}
// 가 두 계좌(3000 + 1000) · 나 2000 · 다 3000 · 라 1000 → 가 40% · 나 20% · 다 30% · 라 10%.
const HOLDINGS = holdingsOf([
  ["A1", "가", 3000], ["A1", "가", 1000], ["B2", "나", 2000], ["C3", "다", 3000], ["D4", "라", 1000],
]);

const band = (state: HoldingsDeclineBand["state"], reason: HoldingsDeclineBand["unjudged_reason"] = null) =>
  ({ judgeable: reason === null, state, label: state ? `PC ${state}` : null, return_20d_pct_1dp: null, unjudged_reason: reason }) as HoldingsDeclineBand;
function item(ticker: string, decline: HoldingsDeclineBand): HoldingsMarketEvidenceItem {
  return {
    ticker,
    holding: { evaluation_amount: 555_555 }, // 근거 응답 평가금액 — 쓰지 않음
    short_term_momentum: { status: "ok", return_5d_pct: -1, return_20d_pct: -3, excess_vs_kodex200_20d_pctp: 0 },
    evidence_notes: [],
    decline_band: decline,
  } as unknown as HoldingsMarketEvidenceItem;
}
const top = (ticker: string, name: string, r5: number) => ({
  ticker, name, eval_amount: 0, market_weight_pct: 1, pnl_rate_pct: 1,
  return_5d_pct: r5, return_20d_pct: -1, excess_vs_kodex200_20d_pctp: 0,
});
function evidenceOf(items: HoldingsMarketEvidenceItem[]): QueryState<HoldingsMarketEvidenceResponse> {
  return {
    phase: "success",
    stale: false,
    data: {
      status: "ok",
      asof: "2026-10-14",
      summary: { total_holdings_count: 5 },
      holdings: items,
      judgment_summary: {
        market_position: { available: true, regime_label: "하락장", regime_streak_days: 4, regime_streak_at_least: false },
        holdings: {
          available: true,
          top_holdings: [top("C3", "다", -3), top("A1", "가", -2), top("B2", "나", -1)],
          coverage: { total: 4, need_check: 1, ok: 3 },
        },
        data_status: {},
      },
      price_basis: {
        reference_date: "2026-10-14", reference_ticker: "069500",
        kodex200_start_date_5d: "2026-10-07", kodex200_start_date_20d: "2026-09-15", date_mismatch: [],
      },
      warnings: [],
    } as unknown as HoldingsMarketEvidenceResponse,
  };
}
const ITEMS = [
  item("A1", band("D10_PLUS")), item("A1", band("D10_PLUS")), item("B2", band("D5_8")),
  item("C3", band(null)), item("D4", band(null, "date_mismatch")),
];

function renderQueue(h = HOLDINGS, ev = evidenceOf(ITEMS)) {
  return render(<JudgmentQueueSection market={MARKET} holdings={h} evidence={ev} onNavigate={() => undefined} />);
}
const parts = () =>
  Array.from(screen.getByTestId("tc-risk-strip").querySelectorAll(".tc-risk-part")).map((p) => p.textContent);

describe("오늘 — 보유 칸 하락 구간 띠 (POC5-13 · B안)", () => {
  it("보유 칸 제목 바로 아래 · 안내 문장 위 · 세 줄 순서", () => {
    renderQueue();
    const strip = screen.getByTestId("tc-risk-strip");
    expect(strip.previousElementSibling).toHaveClass("tc-queue-head");
    expect(strip.previousElementSibling?.textContent).toContain("내가 가진 ETF");
    expect(strip.nextElementSibling).toHaveClass("tc-hold-help");
    expect(strip.nextElementSibling?.textContent).toContain("보유 평가는");
    expect(parts()).toEqual([
      "시장 하락장 · 4거래일째",
      "PC 최근 20저장일 하락 구간 2종목 · 보유 평가 비중 60.0%",
      "구간 판정 가능 3/4종목",
    ]);
    expect(strip.querySelectorAll(".tc-risk-num")).toHaveLength(2);
    expect(screen.getByLabelText("오늘 내가 확인할 것").textContent).not.toMatch(/위험|하락 신호|경보|555/);
  });

  it("「확인 근거」 요약과 같은 조립 함수 · 같은 수", () => {
    renderQueue();
    const h = HOLDINGS as Extract<typeof HOLDINGS, { phase: "success" }>;
    const e = evidenceOf(ITEMS) as Extract<QueryState<HoldingsMarketEvidenceResponse>, { phase: "success" }>;
    const s = buildDeclineSummary(buildRiskEvidenceRows(h.data.items, e.data.holdings).rows, e.data);
    expect(parts()[1]).toBe(`PC 최근 20저장일 하락 구간 ${s.inBand}종목 · 보유 평가 비중 ${fmtShare(s.inBandShare)}`);
    expect(parts()[2]).toBe(`구간 판정 가능 ${s.judgeable}/${s.total}종목`);
  });

  it("일부 평가 미확인이면 비중 뒤 따로 '(확인된 평가금액 기준 · 일부 평가 자료 미확인)'", () => {
    renderQueue(
      holdingsOf([["A1", "가", 3000], ["A1", "가", 1000], ["B2", "나", null], ["C3", "다", 3000], ["D4", "라", 1000]]),
    );
    expect(parts()[1]).toBe(
      "PC 최근 20저장일 하락 구간 2종목 · 보유 평가 비중 50.0%(확인된 평가금액 기준 · 일부 평가 자료 미확인)",
    );
    expect(screen.getByTestId("tc-risk-strip").querySelector(".tc-risk-part .tc-risk-sub")?.textContent).toBe(
      "(확인된 평가금액 기준 · 일부 평가 자료 미확인)",
    );
  });

  it("평가금액이 모두 없으면 '확인 불가'", () => {
    renderQueue(holdingsOf([["A1", "가", null], ["B2", "나", null], ["C3", "다", null], ["D4", "라", null]]));
    expect(parts()[1]).toBe("PC 최근 20저장일 하락 구간 2종목 · 보유 평가 비중 확인 불가");
  });

  it("보유 · 근거 응답 전이나 실패면 띠가 없고, 최대 3개 선정 · 순서는 그대로", () => {
    const { unmount } = renderQueue({ phase: "loading" });
    expect(screen.queryByTestId("tc-risk-strip")).toBeNull();
    unmount();
    renderQueue(HOLDINGS, { phase: "error" });
    expect(screen.queryByTestId("tc-risk-strip")).toBeNull();
  });

  it("최대 3개는 backend 선정 · 순서 그대로(띠가 바꾸지 않음)", () => {
    renderQueue();
    const names = screen.getAllByTestId("tc-top-row").map((r) => r.textContent ?? "");
    expect(names).toHaveLength(3);
    expect(names[0]).toContain("다");
    expect(names[1]).toContain("가");
    expect(names[2]).toContain("나");
  });
});
