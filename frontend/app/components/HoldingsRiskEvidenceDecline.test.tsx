// POC5-13 · POC5-15 — 「확인 근거」 현재 상태 + PC 최근 20저장일 하락 구간: 요약 블록 · ? 도움말 · 실패 · 빈 보유 문구 ·
// 보기 '하락 구간' · 구간 배지 ·
// 상세 줄. 받은 두 응답(보유 평가 · 근거)만 쓴다(추가 조회 0). 비중은 정상 보유 평가 응답의 종목 합산이다.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, fireEvent, within } from "@testing-library/react";
import { __resetQueryCache } from "@/lib/api/queryCache";
import type {
  HoldingsDeclineBand,
  HoldingsMarketEvidenceResponse,
  PriceVolatilityEvidence,
} from "@/lib/api";

const fetchEnrichedHoldings = vi.fn();
const fetchHoldingsMarketEvidence = vi.fn();
const fetchBenchmarkSeries = vi.fn();
const fetchPriceSeries = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    fetchEnrichedHoldings: (...a: unknown[]) => fetchEnrichedHoldings(...a),
    fetchHoldingsMarketEvidence: (...a: unknown[]) => fetchHoldingsMarketEvidence(...a),
    fetchBenchmarkSeries: (...a: unknown[]) => fetchBenchmarkSeries(...a),
    fetchPriceSeries: (...a: unknown[]) => fetchPriceSeries(...a),
  };
});

import HoldingsRiskEvidenceSection from "./HoldingsRiskEvidenceSection";
import {
  HELP_BAND_BASIS,
  HELP_PARTIAL_EVAL,
  HELP_PARTIAL_JUDGE,
} from "./holdings_risk_evidence/riskCombination";

function enrichedRow(ticker: string, name: string, evalAmt: number | null, invested: number) {
  return {
    ticker, name, quantity: 1, avg_buy_price: invested, invested_amount: invested,
    current_price: evalAmt, price_asof: "2026-10-14", price_source: "naver",
    eval_amount: evalAmt, pnl_amount: evalAmt === null ? null : evalAmt - invested,
    pnl_rate_pct: null, buy_weight_pct: null, market_weight_pct: null,
    price_missing: evalAmt === null, calc_missing: evalAmt === null,
  };
}
// 에이 두 계좌(3000 + 1000) · 비 2000 · 씨 3000 · 디 1000 → 합 10,000(에이 40% · 비 20% · 씨 30% · 디 10%).
function enriched(over: { bEval?: number | null } = {}) {
  return {
    items: [
      enrichedRow("A1", "에이", 3000, 3000),
      enrichedRow("A1", "에이", 1000, 1000),
      enrichedRow("B1", "비", over.bEval === undefined ? 2000 : over.bEval, 2000),
      enrichedRow("C1", "씨", 3000, 3000),
      enrichedRow("D1", "디", 1000, 1000),
    ],
  };
}

const LABEL = { D10_PLUS: "PC 20저장일 하락 10% 이상", D8_10: "PC 20저장일 하락 8~10%", D5_8: "PC 20저장일 하락 5~8%" };
function band(state: HoldingsDeclineBand["state"], v: number | null, reason: HoldingsDeclineBand["unjudged_reason"] = null): HoldingsDeclineBand {
  return { judgeable: reason === null, state, label: state ? LABEL[state] : null, return_20d_pct_1dp: v, unjudged_reason: reason };
}
function evItem(
  ticker: string, name: string, r5: number | null, r20: number | null, decline: HoldingsDeclineBand,
  comparison: "ok" | "date_mismatch" | "window_mismatch" = "ok",
) {
  const ok = comparison !== "date_mismatch";
  const wm = comparison === "window_mismatch"; // 20일 시작일만 KODEX200 과 다름 → 20일 대비만 비움
  return {
    ticker, name,
    // 근거 응답의 평가금액은 일부러 다르게(화면 비중이 이 값을 쓰면 시험이 깨진다).
    holding: { quantity: 1, avg_buy_price: 1, evaluation_amount: 777_777, pnl_rate_pct: 77 },
    topn_match: { status: "unavailable", rank: null, basis: null, candidate_name: null },
    returns: { status: "ok", one_month_return_pct: 1, three_month_return_pct: 2 },
    excess_return: { status: "ok", vs_kodex200_1m_pctp: 1, vs_kodex200_3m_pctp: 2 },
    short_term_momentum: {
      status: ok ? "ok" : "unavailable", return_5d_pct: r5, return_10d_pct: r5, return_20d_pct: r20,
      excess_vs_kodex200_5d_pctp: ok ? 0 : null, excess_vs_kodex200_10d_pctp: ok ? 0 : null,
      excess_vs_kodex200_20d_pctp: ok && !wm ? 0 : null,
    },
    constituents_overlap: { status: "ok", overlap_with_market_core: [] },
    nav_discount: { status: "ok", source: null, asof: null, nav: null, market_price: null, discount_rate_pct: null, flag: null, message: null },
    evidence_notes: [],
    price_dates: {
      end_date: ok ? "2026-10-14" : "2026-08-12",
      start_date_5d: ok ? "2026-10-07" : "2026-08-05",
      start_date_20d: wm ? "2026-09-12" : ok ? "2026-09-15" : "2026-07-15",
      comparison,
    },
    decline_band: decline,
  };
}
function evidence(bComparison: "ok" | "window_mismatch" = "ok"): HoldingsMarketEvidenceResponse {
  return {
    status: "ok", asof: "2026-10-14", holdings_asof: "2026-10-14", market_asof: "2026-10-14",
    market_context: null,
    summary: {
      total_holdings_count: 5, matched_topn_count: 0, not_in_current_topn_count: 5,
      evidence_unavailable_count: 0, constituents_available_count: 0,
      constituents_unavailable_count: 0, nav_discount_unavailable_count: 0,
    },
    holdings: [
      evItem("A1", "에이", -2, -12.34, band("D10_PLUS", -12.3)),
      evItem("A1", "에이", -2, -12.34, band("D10_PLUS", -12.3)),
      evItem("B1", "비", -1, -6.04, band("D5_8", -6.0), bComparison),
      evItem("C1", "씨", -3, -2.0, band(null, -2.0)),
      evItem("D1", "디", null, null, band(null, null, "date_mismatch"), "date_mismatch"),
    ],
    judgment_summary: {
      market_position: { available: true, regime_code: "bear", regime_label: "하락장", regime_streak_days: 4, regime_streak_at_least: false },
      holdings: { available: true, top_holdings: [], coverage: { total: 4, need_check: 1, ok: 3 } },
      data_status: {},
    },
    price_basis: {
      reference_date: "2026-10-14", reference_ticker: "069500",
      kodex200_start_date_5d: "2026-10-07", kodex200_start_date_20d: "2026-09-15",
      date_mismatch: [{ ticker: "D1", name: "디", end_date: "2026-08-12" }],
    },
    warnings: [],
  } as unknown as HoldingsMarketEvidenceResponse;
}

async function renderSection() {
  const utils = render(<HoldingsRiskEvidenceSection />);
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
  return utils;
}
function rowOrder(): string[] {
  const list = screen.getByTestId("hre-evidence-list");
  return Array.from(list.querySelectorAll('[role="button"]')).map(
    (el) => (el.getAttribute("aria-label") ?? "").replace(" 상세 보기", ""),
  );
}
const rowEl = (name: string) => screen.getByRole("button", { name: `${name} 상세 보기` });

describe("확인 근거 — PC 최근 20저장일 하락 구간 (POC5-13)", () => {
  beforeEach(() => {
    __resetQueryCache();
    fetchEnrichedHoldings.mockReset();
    fetchHoldingsMarketEvidence.mockReset();
    fetchEnrichedHoldings.mockResolvedValue(enriched());
    fetchHoldingsMarketEvidence.mockResolvedValue(evidence());
    fetchPriceSeries.mockResolvedValue({ availability: "NO_DATA", points: [] });
  });

  it("요약(POC5-15) — 현재 상태 + ? / 종목 수 · 비중 / 구간별 / 작은 보조 묶음 · 긴 안내 문단은 ? 로", async () => {
    await renderSection();
    const box = screen.getByTestId("hre-risk-summary");
    expect(screen.getByTestId("hre-risk-state").textContent).toBe("현재 상태시장·보유 동반 약세?");
    expect(screen.getByTestId("hre-risk-total").textContent).toBe("2종목 · 보유 평가 비중 60.0%");
    expect(screen.getByTestId("hre-risk-band-D10_PLUS").textContent).toBe("10% 이상 1종목 · 40.0%");
    expect(screen.getByTestId("hre-risk-band-D8_10").textContent).toBe("8~10% 0종목 · 0.0%");
    expect(screen.getByTestId("hre-risk-band-D5_8").textContent).toBe("5~8% 1종목 · 20.0%");
    const aux = Array.from(screen.getByTestId("hre-risk-scope").querySelectorAll("span")).map((n) => n.textContent);
    expect(aux).toEqual([
      "시장 국면 하락장 · 4거래일째", // 시장 국면 줄에 날짜를 붙이지 않는다(13 판정 §7 '날짜')
      "구간 판정 가능 3/4종목 · 일부 종목 판정 불가",
      "PC 가격 흐름 기준일 2026-10-14",
      "PC 저장 종가 기준",
    ]);
    // 긴 공통 안내 문단은 기본 화면에서 빠졌다(판정 Q3) — 그 내용은 ? 안에서 실제로 읽힌다.
    expect(box.textContent).not.toContain("OCI 알림과 값이 다를 수 있");
    expect(box.textContent).not.toContain("원인이라는 뜻은 아닙니다");
    expect(box.textContent).not.toMatch(/777/); // 근거 응답의 평가금액은 쓰지 않는다
    fireEvent.click(within(box).getByRole("button", { name: "현재 상태 도움말" }));
    const dlg = screen.getByRole("dialog", { name: "현재 상태 도움말" });
    expect(dlg.textContent).toContain("시장 국면이 각 종목 하락의 원인이라는 뜻은 아닙니다.");
    expect(dlg.textContent).toContain(HELP_BAND_BASIS);
    expect(dlg.textContent).toContain(HELP_PARTIAL_JUDGE);
    expect(dlg.textContent).not.toContain(HELP_PARTIAL_EVAL);
    for (const bad of ["위험", "고위험", "손절", "매도", "청산", "BUY", "SELL"]) {
      expect(document.body.textContent ?? "").not.toContain(bad);
    }
    fireEvent.mouseDown(screen.getByTestId("hre-risk-total"));
    expect(screen.queryByRole("dialog")).toBeNull();
    // 도움말을 열고 닫아도 다시 조회하지 않는다.
    expect(fetchEnrichedHoldings).toHaveBeenCalledTimes(1);
    expect(fetchHoldingsMarketEvidence).toHaveBeenCalledTimes(1);
  });

  it("일부 평가 미확인이면 비중 옆에 '확인된 평가금액 기준 · 일부 평가 자료 미확인' · 그 구간만 '확인 불가'", async () => {
    fetchEnrichedHoldings.mockResolvedValue(enriched({ bEval: null }));
    await renderSection();
    // 분모 8,000 · 에이 4,000 → 50.0%
    expect(screen.getByTestId("hre-risk-total").textContent).toBe(
      "2종목 · 보유 평가 비중 50.0% (확인된 평가금액 기준 · 일부 평가 자료 미확인)",
    );
    expect(screen.getByTestId("hre-risk-band-D5_8").textContent).toBe("5~8% 1종목 · 확인 불가");
  });

  it("보기 세 개 · '하락 구간'은 구간 종목만 · 사용자 정렬 유지 · 다시 조회하지 않는다", async () => {
    await renderSection();
    const qv = document.querySelector(".hre-quickview") as HTMLElement;
    expect(Array.from(qv.querySelectorAll("button")).map((b) => b.textContent)).toEqual([
      "전체",
      "하락 구간 (2)",
      "자료 확인 필요 (1)",
    ]);
    expect(rowOrder()).toEqual(["씨", "에이", "비", "디"]); // 기본 5일 변화
    fireEvent.click(screen.getByRole("button", { name: "하락 구간 (2)" }));
    expect(rowOrder()).toEqual(["에이", "비"]);
    fireEvent.click(screen.getByRole("button", { name: "평가 비중" }));
    expect(rowOrder()).toEqual(["에이", "비"]);
    fireEvent.click(screen.getByRole("button", { name: "자료 확인 필요 (1)" }));
    expect(rowOrder()).toEqual(["디"]);
    fireEvent.click(screen.getByRole("button", { name: "전체" }));
    expect(rowOrder()).toEqual(["에이", "씨", "비", "디"]); // 평가 비중 정렬 그대로
    expect(fetchEnrichedHoldings).toHaveBeenCalledTimes(1);
    expect(fetchHoldingsMarketEvidence).toHaveBeenCalledTimes(1);
  });

  it("구간 배지(파란 계열 class 'band')는 구간 종목에만 · 구간 밖 · 판정 안 함에는 없다", async () => {
    await renderSection();
    expect(within(rowEl("에이")).getByText("PC 20저장일 하락 10% 이상")).toHaveClass("wb-hb", "band");
    expect(within(rowEl("비")).getByText("PC 20저장일 하락 5~8%")).toHaveClass("wb-hb", "band");
    expect(rowEl("씨").querySelector(".wb-hb.band")).toBeNull();
    expect(rowEl("디").querySelector(".wb-hb.band")).toBeNull();
    expect(within(rowEl("디")).getByText("자료 확인 필요")).toHaveClass("wb-hb", "warn");
  });

  it("상세 'PC 20저장일 하락 구간' 줄 — 판정 값 · 기간 / 해당 없음 / 판정하지 않음", async () => {
    await renderSection();
    const detail = async (name: string) => {
      await act(async () => {
        fireEvent.click(rowEl(name));
        await Promise.resolve();
      });
      return screen.getByTestId("hre-decline-band").textContent ?? "";
    };
    expect(await detail("에이")).toBe(
      "PC 20저장일 하락 구간PC 20저장일 하락 10% 이상 · 20저장일 변화 -12.3%(판정에 쓴 소수 첫째 자리 값) · 기간 2026-09-15 ~ 2026-10-14 · PC 저장 종가",
    );
    expect(await detail("씨")).toContain("해당 없음 · 20저장일 변화 -2.0%");
    expect(await detail("디")).toContain(
      "판정하지 않음 — 이 종목의 최근 저장일(2026-08-12)이 PC 가격 흐름 기준일(2026-10-14)과 다릅니다(자료 확인 필요).",
    );
    expect(fetchEnrichedHoldings).toHaveBeenCalledTimes(1);
    expect(fetchHoldingsMarketEvidence).toHaveBeenCalledTimes(1);
  });

  it("20일 시작일이 다른 구간 종목은 '하락 구간'과 '자료 확인 필요' 두 보기에 함께 · 상세에 비교 기간 사유", async () => {
    fetchHoldingsMarketEvidence.mockResolvedValue(evidence("window_mismatch"));
    await renderSection();
    const qv = document.querySelector(".hre-quickview") as HTMLElement;
    expect(Array.from(qv.querySelectorAll("button")).map((b) => b.textContent)).toEqual([
      "전체",
      "하락 구간 (2)",
      "자료 확인 필요 (2)",
    ]);
    fireEvent.click(screen.getByRole("button", { name: "하락 구간 (2)" }));
    expect(rowOrder()).toEqual(["에이", "비"]);
    fireEvent.click(screen.getByRole("button", { name: "자료 확인 필요 (2)" }));
    expect(rowOrder()).toEqual(["비", "디"]);
    expect(within(rowEl("비")).getByText("PC 20저장일 하락 5~8%")).toHaveClass("wb-hb", "band");
    expect(rowEl("비").querySelector(".wb-hb.warn")?.textContent).toBe("자료 확인 필요");
    await act(async () => {
      fireEvent.click(rowEl("비"));
      await Promise.resolve();
    });
    expect(screen.getByTestId("hre-decline-band").textContent).toContain(
      "기간 2026-09-12 ~ 2026-10-14(KODEX200 비교 기간과 달라 상대 비교는 비워 둠)",
    );
    expect(fetchHoldingsMarketEvidence).toHaveBeenCalledTimes(1);
  });

  it("근거 응답에 구간 필드가 없으면(이전 응답) 0종목 · 판정 가능 0 — 구간 밖으로 꾸미지 않는다", async () => {
    const ev = evidence();
    for (const h of ev.holdings) delete (h as { decline_band?: unknown }).decline_band;
    fetchHoldingsMarketEvidence.mockResolvedValue(ev);
    await renderSection();
    expect(screen.getByTestId("hre-risk-scope").textContent).toContain("구간 판정 가능 0/4종목");
    expect(rowEl("에이").querySelector(".wb-hb.band")).toBeNull();
  });

  it("판정 Q4 — 시장 하락 아님 · 하락 없음 = '시장·보유 하락 구간 미해당'", async () => {
    const ev = evidence();
    (ev.judgment_summary as { market_position: Record<string, unknown> }).market_position = {
      available: true, regime_code: "neutral", regime_label: "보합장", regime_streak_days: 3, regime_streak_at_least: false,
    };
    for (const h of ev.holdings) {
      (h as { decline_band?: HoldingsDeclineBand }).decline_band = band(null, -1.0);
      (h as { price_dates?: { comparison: string } }).price_dates!.comparison = "ok";
    }
    fetchHoldingsMarketEvidence.mockResolvedValue(ev);
    await renderSection();
    expect(screen.getByTestId("hre-risk-state").textContent).toBe("현재 상태시장·보유 하락 구간 미해당?");
    fireEvent.click(screen.getByRole("button", { name: "현재 상태 도움말" }));
    expect(screen.getByRole("dialog").textContent).toContain("‘미해당’은 지금 기준에 해당하지 않았다는 뜻입니다.");
  });

  it.each([
    ["근거 실패", "evidence", "자료 확인 필요 — 확인 근거를 불러오지 못했습니다."],
    ["보유 실패(시장 하락)", "holdings", "시장 하락 · 보유 판정 불완전 — 보유 자료를 불러오지 못했습니다."],
    ["둘 다 실패", "both", "자료 확인 필요 — 보유 자료와 확인 근거를 불러오지 못했습니다."],
  ])("판정 Q1 — %s: 오늘 띠와 같은 상태 문구 + 실제 실패한 조회만", async (_, which, text) => {
    if (which !== "holdings") fetchHoldingsMarketEvidence.mockRejectedValue(new Error("evidence down"));
    if (which !== "evidence") fetchEnrichedHoldings.mockRejectedValue(new Error("holdings down"));
    await renderSection();
    expect(screen.getByTestId("hre-risk-state-failed").textContent).toBe(text);
    expect(screen.queryByTestId("hre-risk-summary")).toBeNull();
  });

  it("정상 응답의 빈 보유(근거도 성공) → '보유 판정 대상 없음' — 오늘 띠와 같은 문구", async () => {
    fetchEnrichedHoldings.mockResolvedValue({ items: [] });
    const ev = evidence();
    ev.holdings = [];
    fetchHoldingsMarketEvidence.mockResolvedValue(ev);
    await renderSection();
    expect(screen.getByTestId("hre-risk-state-empty").textContent).toBe(
      "보유 판정 대상 없음 — 표시할 보유 ETF 가 없습니다.",
    );
  });

  it("정상 응답의 빈 보유는 근거가 실패해도 '보유 판정 대상 없음' — 실패보다 먼저", async () => {
    fetchEnrichedHoldings.mockResolvedValue({ items: [] });
    fetchHoldingsMarketEvidence.mockRejectedValue(new Error("evidence down"));
    await renderSection();
    expect(screen.getByTestId("hre-risk-state-empty").textContent).toBe(
      "보유 판정 대상 없음 — 표시할 보유 ETF 가 없습니다.",
    );
    expect(screen.queryByTestId("hre-risk-state-failed")).toBeNull();
  });
});

// POC5-16 — 종목 상세의 '가격 흔들림(변동성)' 접힌 구역(거래량 칸 바로 아래 · 받은 근거 응답의 선택 필드만).
describe("확인 근거 — 종목 상세 가격 흔들림 (POC5-16)", () => {
  const PV: PriceVolatilityEvidence = {
    status: "ok",
    recent: { value_pct: 3.2, start_date: "2026-09-15", end_date: "2026-10-14" },
    previous: { value_pct: 2.97, start_date: "2026-08-14", end_date: "2026-09-15" },
    comparison: "higher",
    recent_reason: null,
    previous_reason: null,
    end_date: "2026-10-14",
  };
  beforeEach(() => {
    __resetQueryCache();
    fetchEnrichedHoldings.mockReset();
    fetchHoldingsMarketEvidence.mockReset();
    fetchEnrichedHoldings.mockResolvedValue(enriched());
    const ev = evidence();
    // 같은 종목 두 계좌(에이)는 같은 근거 · 비는 최근만 · 디(기준일 다른 종목)는 날짜 불일치 · 씨는 선택 필드 없음(이전 응답 모양).
    ev.holdings[0].price_volatility = PV;
    ev.holdings[1].price_volatility = PV;
    ev.holdings[2].price_volatility = {
      ...PV, status: "recent_only", previous: null, comparison: null, previous_reason: "insufficient_history",
    };
    ev.holdings[4].price_volatility = {
      ...PV, status: "date_mismatch", recent: null, previous: null, comparison: null, end_date: "2026-08-12",
    };
    fetchHoldingsMarketEvidence.mockResolvedValue(ev);
    fetchPriceSeries.mockResolvedValue({ availability: "NO_DATA", points: [] });
  });
  const open = async (name: string) => {
    await act(async () => {
      fireEvent.click(rowEl(name));
      await Promise.resolve();
    });
  };

  it("거래량 칸 바로 아래 · 기본 접힘 · 펼치면 두 값 · 비교 — 다시 조회하지 않는다", async () => {
    const rawFetch = vi.spyOn(globalThis, "fetch");
    await renderSection();
    expect(screen.queryByTestId("price-volatility")).toBeNull(); // 상세를 열기 전에는 없음
    await open("에이");
    const block = screen.getByTestId("price-volatility");
    const volume = screen.getByTestId("stored-volume");
    expect(volume.compareDocumentPosition(block) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(block.parentElement).toBe(volume.parentElement);
    expect(screen.queryByTestId("price-volatility-body")).toBeNull();
    fireEvent.click(within(block).getByRole("button", { name: "가격 흔들림(변동성) 보기" }));
    expect(screen.getByTestId("price-volatility-body").textContent).toContain("3.20%");
    expect(screen.getByTestId("price-volatility-cmp").textContent).toBe("직전보다 커짐");
    fireEvent.click(within(block).getByRole("button", { name: "가격 흔들림 도움말" }));
    expect(screen.getByRole("dialog", { name: "가격 흔들림 도움말" })).toBeInTheDocument();
    expect(fetchEnrichedHoldings).toHaveBeenCalledTimes(1);
    expect(fetchHoldingsMarketEvidence).toHaveBeenCalledTimes(1);
    expect(rawFetch).not.toHaveBeenCalled();
    rawFetch.mockRestore();
  });

  it("다른 종목을 고르면 다시 접힌 채로 시작한다", async () => {
    await renderSection();
    await open("에이");
    fireEvent.click(screen.getByRole("button", { name: "가격 흔들림(변동성) 보기" }));
    expect(screen.getByTestId("price-volatility-body")).toBeInTheDocument();
    await open("비");
    expect(screen.getByRole("button", { name: "가격 흔들림(변동성) 보기" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByTestId("price-volatility-body")).toBeNull();
    expect(screen.getByTestId("price-volatility-note").textContent).toBe(
      "직전 20구간은 계산하지 못해 비교하지 않습니다.",
    );
  });

  it("기준일 다른 종목은 접힌 채 사유(기존 날짜 안내와 함께) · 선택 필드가 없는 종목은 구역을 그리지 않는다", async () => {
    await renderSection();
    await open("디");
    expect(screen.getByTestId("price-volatility-note").textContent).toBe(
      "이 종목의 마지막 유효 가격일(2026-08-12)이 PC 가격 흐름 기준일(2026-10-14)과 달라 값을 보이지 않습니다.",
    );
    expect(screen.getByTestId("hre-decline-band").textContent).toContain("판정하지 않음");
    await open("씨");
    expect(screen.queryByTestId("price-volatility")).toBeNull();
    expect(fetchHoldingsMarketEvidence).toHaveBeenCalledTimes(1);
  });
});
