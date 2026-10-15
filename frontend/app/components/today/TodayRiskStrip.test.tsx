// POC5-13 · POC5-15 — 「오늘의 투자 점검」 '내가 가진 ETF' 칸 요약 띠.
// 자리 = 보유 칸 제목 바로 아래 · 안내 문장 위(13 B안). POC5-15 세 묶음(PLAN 판정 §4):
// 상태 문구 + ? / PC 하락 구간 종목 수 · 보유 평가 비중 / 작은 보조 묶음(시장 국면 · 구간 판정 가능 a/b).
// 실패면 상태와 실제 실패 사유 한 문장 · 빈 보유면 상태만. 「확인 근거」와 같은 공통 판정 함수. 최대 3개 그대로.
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { QueryState } from "@/lib/api/queryCache";
import type {
  EnrichedHoldingsResult,
  HoldingsDeclineBand,
  HoldingsMarketEvidenceItem,
  HoldingsMarketEvidenceResponse,
  MarketTopNResponse,
} from "@/lib/api";
import JudgmentQueueSection from "./JudgmentQueueSection";
import { fmtShare } from "../holdings_risk_evidence/declineSummary";
import {
  HELP_BAND_BASIS,
  HELP_PARTIAL_EVAL,
  HELP_PARTIAL_JUDGE,
  HELP_SHARE_UNAVAILABLE,
  riskStateFromQueries,
} from "../holdings_risk_evidence/riskCombination";

const MARKET = { phase: "error" } as QueryState<MarketTopNResponse>;

function holdingsOf(rows: [string, string, number | null][], stale = false): QueryState<EnrichedHoldingsResult> {
  return {
    phase: "success",
    stale,
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
const BEAR = { available: true, regime_code: "bear", regime_label: "하락장", regime_streak_days: 4, regime_streak_at_least: false };
function evidenceOf(
  items: HoldingsMarketEvidenceItem[],
  mp: Record<string, unknown> = BEAR,
  stale = false,
): QueryState<HoldingsMarketEvidenceResponse> {
  return {
    phase: "success",
    stale,
    data: {
      status: "ok",
      asof: "2026-10-14",
      summary: { total_holdings_count: 5 },
      holdings: items,
      judgment_summary: {
        market_position: mp,
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
// 가 10% 이상 · 나 5~8% · 다 구간 밖 · 라 판정 안 함(기준일 다름) → 하락 있음 2종목 · 판정 가능 3/4.
const ITEMS = [
  item("A1", band("D10_PLUS")), item("A1", band("D10_PLUS")), item("B2", band("D5_8")),
  item("C3", band(null)), item("D4", band(null, "date_mismatch")),
];
const ALL_JUDGED = [
  item("A1", band("D10_PLUS")), item("A1", band("D10_PLUS")), item("B2", band("D5_8")),
  item("C3", band(null)), item("D4", band(null)),
];
const NONE = ALL_JUDGED.map((it) => ({ ...it, decline_band: band(null) }));
const ERR = { phase: "error" } as const;

function renderQueue(
  h: QueryState<EnrichedHoldingsResult> = HOLDINGS,
  ev: QueryState<HoldingsMarketEvidenceResponse> = evidenceOf(ALL_JUDGED),
) {
  return render(<JudgmentQueueSection market={MARKET} holdings={h} evidence={ev} onNavigate={() => undefined} />);
}
const strip = () => screen.getByTestId("tc-risk-strip");
const head = () => strip().querySelector(".tc-risk-head") as HTMLElement;
const auxItems = () => Array.from(strip().querySelectorAll(".tc-risk-aux > span")).map((s) => s.textContent);
const card = () => screen.getByLabelText("오늘 내가 확인할 것");

describe("오늘 — 보유 칸 현재 상태 띠 (POC5-15 · 세 묶음)", () => {
  it("보유 칸 제목 바로 아래 · 안내 문장 위 · 상태 + ? / 종목 수 · 비중 / 시장 · 판정 범위", () => {
    renderQueue();
    expect(strip().previousElementSibling).toHaveClass("tc-queue-head");
    expect(strip().previousElementSibling?.textContent).toContain("내가 가진 ETF");
    expect(strip().nextElementSibling).toHaveClass("tc-hold-help");
    expect(head().textContent).toBe("시장·보유 동반 약세?");
    expect(screen.getByRole("button", { name: "현재 상태 도움말" })).toHaveAttribute("aria-expanded", "false");
    expect(strip().querySelector(".tc-risk-part")?.textContent).toBe(
      "PC 최근 20저장일 하락 구간 2종목 · 보유 평가 비중 60.0%",
    );
    expect(auxItems()).toEqual(["시장 하락장 · 4거래일째", "구간 판정 가능 4/4종목"]);
    expect(strip().querySelectorAll(".tc-risk-num")).toHaveLength(2);
    // 시장 국면을 상태 문구 줄에 이어 붙이지 않는다(판정 §4).
    expect(head().textContent).not.toContain("하락장");
    expect(card().textContent).not.toMatch(/위험|하락 신호|경보|555/);
  });

  it("「확인 근거」와 같은 공통 판정 함수 · 같은 수", () => {
    renderQueue(HOLDINGS, evidenceOf(ITEMS));
    const v = riskStateFromQueries(HOLDINGS, evidenceOf(ITEMS))!;
    expect(head().textContent).toBe(`${v.combo.text}?`);
    expect(strip().querySelector(".tc-risk-part")?.textContent).toBe(
      `PC 최근 20저장일 하락 구간 ${v.summary!.inBand}종목 · 보유 평가 비중 ${fmtShare(v.summary!.inBandShare)}`,
    );
  });

  it("일부 종목 판정 불가는 기본 화면에 보이고 · ? 안에 그 제한 문단이 있다", () => {
    renderQueue(HOLDINGS, evidenceOf(ITEMS));
    expect(head().textContent).toBe("시장·보유 동반 약세?");
    expect(auxItems()[1]).toBe("구간 판정 가능 3/4종목 · 일부 종목 판정 불가");
    fireEvent.click(screen.getByRole("button", { name: "현재 상태 도움말" }));
    const dlg = screen.getByRole("dialog", { name: "현재 상태 도움말" });
    expect(dlg.textContent).toContain(HELP_PARTIAL_JUDGE);
    expect(dlg.textContent).toContain(HELP_BAND_BASIS);
    expect(dlg.textContent).not.toContain(HELP_PARTIAL_EVAL);
    expect(card().textContent).not.toMatch(/위험|하락 신호|경보/);
  });

  it("일부 평가 미확인은 비중 뒤 괄호로 기본 화면에 · ? 안에 평가 부족 문단", () => {
    renderQueue(
      holdingsOf([["A1", "가", 3000], ["A1", "가", 1000], ["B2", "나", null], ["C3", "다", 3000], ["D4", "라", 1000]]),
      evidenceOf(ALL_JUDGED),
    );
    expect(strip().querySelector(".tc-risk-part")?.textContent).toBe(
      "PC 최근 20저장일 하락 구간 2종목 · 보유 평가 비중 50.0%(확인된 평가금액 기준 · 일부 평가 자료 미확인)",
    );
    fireEvent.click(screen.getByRole("button", { name: "현재 상태 도움말" }));
    expect(screen.getByRole("dialog").textContent).toContain(HELP_PARTIAL_EVAL);
  });

  it("평가금액이 모두 없으면 비중 '확인 불가' · 상태 분류는 그대로", () => {
    renderQueue(holdingsOf([["A1", "가", null], ["B2", "나", null], ["C3", "다", null], ["D4", "라", null]]), evidenceOf(ALL_JUDGED));
    expect(head().textContent).toBe("시장·보유 동반 약세?");
    expect(strip().querySelector(".tc-risk-part")?.textContent).toBe(
      "PC 최근 20저장일 하락 구간 2종목 · 보유 평가 비중 확인 불가",
    );
  });

  it("판정 Q4 — 시장 하락 아님 · 하락 없음 = '시장·보유 하락 구간 미해당'('하락 신호' 금지 검사 그대로)", () => {
    renderQueue(HOLDINGS, evidenceOf(NONE, { ...BEAR, regime_code: "neutral", regime_label: "보합장", regime_streak_days: 3 }));
    expect(head().textContent).toBe("시장·보유 하락 구간 미해당?");
    expect(auxItems()[0]).toBe("시장 보합장 · 3거래일째");
    expect(card().textContent).not.toMatch(/위험|하락 신호|경보|안전|정상/);
  });

  it("모르는 시장 코드면 '시장 판정 불가' · 보조 묶음은 '시장 확인 불가'(백엔드 라벨을 붙이지 않음)", () => {
    renderQueue(HOLDINGS, evidenceOf(ALL_JUDGED, { ...BEAR, regime_code: "strong_bear" }));
    expect(head().textContent).toBe("보유 하락 구간 확인 · 시장 판정 불가?");
    expect(auxItems()[0]).toBe("시장 확인 불가");
  });

  it.each([
    ["근거 실패", HOLDINGS, ERR, "자료 확인 필요?", "확인 근거를 불러오지 못했습니다."],
    ["보유 실패(시장 하락)", ERR, evidenceOf(ALL_JUDGED), "시장 하락 · 보유 판정 불완전?", "보유 자료를 불러오지 못했습니다."],
    ["둘 다 실패", ERR, ERR, "자료 확인 필요?", "보유 자료와 확인 근거를 불러오지 못했습니다."],
  ] as const)("판정 Q1 — %s: 상태와 실제 실패 사유 한 문장만(없는 수치 자리 없음)", (_, h, e, headText, reason) => {
    renderQueue(h as QueryState<EnrichedHoldingsResult>, e as QueryState<HoldingsMarketEvidenceResponse>);
    expect(head().textContent).toBe(headText);
    expect(screen.getByTestId("tc-risk-failed").textContent).toBe(reason);
    expect(strip().querySelector(".tc-risk-part")).toBeNull();
    expect(strip().querySelector(".tc-risk-aux")).toBeNull();
    expect(strip().textContent).not.toMatch(/0종목|0\/0/);
  });

  it("정상 응답의 빈 보유는 근거가 실패해도 '보유 판정 대상 없음'만", () => {
    renderQueue(holdingsOf([]), ERR as QueryState<HoldingsMarketEvidenceResponse>);
    expect(head().textContent).toBe("보유 판정 대상 없음?");
    expect(screen.queryByTestId("tc-risk-failed")).toBeNull();
    expect(strip().querySelector(".tc-risk-part")).toBeNull();
  });

  it("정상 응답의 빈 보유(근거도 성공) → '보유 판정 대상 없음'만 · 「확인 근거」와 같은 문구", () => {
    renderQueue(holdingsOf([]), evidenceOf([]));
    expect(head().textContent).toBe("보유 판정 대상 없음?");
    expect(strip().querySelector(".tc-risk-part")).toBeNull();
    expect(riskStateFromQueries(holdingsOf([]), evidenceOf([]))!.combo.text).toBe("보유 판정 대상 없음");
  });

  it("평가금액이 모두 없을 때 ? 는 '비중 확인 불가'를 말하고 '계산했다'고 하지 않는다", () => {
    renderQueue(holdingsOf([["A1", "가", null], ["B2", "나", null], ["C3", "다", null], ["D4", "라", null]]), evidenceOf(ALL_JUDGED));
    fireEvent.click(screen.getByRole("button", { name: "현재 상태 도움말" }));
    const t = screen.getByRole("dialog").textContent ?? "";
    expect(t).toContain(HELP_SHARE_UNAVAILABLE);
    expect(t).not.toContain(HELP_PARTIAL_EVAL);
  });

  it("받는 중이면 띠가 없다", () => {
    const { unmount } = renderQueue({ phase: "loading" }, evidenceOf(ALL_JUDGED));
    expect(screen.queryByTestId("tc-risk-strip")).toBeNull();
    unmount();
    renderQueue(HOLDINGS, { phase: "loading" });
    expect(screen.queryByTestId("tc-risk-strip")).toBeNull();
  });

  it("다시 읽기 실패(stale)여도 받은 자료로 그대로 분류", () => {
    renderQueue(
      holdingsOf([["A1", "가", 3000], ["A1", "가", 1000], ["B2", "나", 2000], ["C3", "다", 3000], ["D4", "라", 1000]], true),
      evidenceOf(ALL_JUDGED, BEAR, true),
    );
    expect(head().textContent).toBe("시장·보유 동반 약세?");
    expect(screen.queryByTestId("tc-risk-failed")).toBeNull();
  });

  it("? 를 열고 닫아도 띠 · 최대 3개는 그대로(받은 자료만)", () => {
    renderQueue();
    const btn = screen.getByRole("button", { name: "현재 상태 도움말" });
    fireEvent.click(btn);
    expect(screen.getByRole("dialog").textContent).toContain("시장 국면이 각 종목 하락의 원인이라는 뜻은 아닙니다");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    const names = screen.getAllByTestId("tc-top-row").map((r) => r.textContent ?? "");
    expect(names).toHaveLength(3);
    expect(names[0]).toContain("다");
    expect(names[1]).toContain("가");
    expect(names[2]).toContain("나");
  });
});
