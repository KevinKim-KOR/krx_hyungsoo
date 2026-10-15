// POC5-15 — 현재 시장 · 보유 상태 조합(설계 V1 §3 · §4 · PLAN 판정 §2 · §5) 순수 함수.
import { describe, it, expect } from "vitest";
import type {
  EnrichedHoldingsResult,
  HoldingsDeclineBand,
  HoldingsMarketEvidenceItem,
  HoldingsMarketEvidenceResponse,
} from "@/lib/api";
import type { QueryState } from "@/lib/api/queryCache";
import type { DeclineSummary } from "./declineSummary";
import {
  FAILURE_TEXT,
  HELP_BAND_BASIS,
  HELP_MARKET_BASIS,
  HELP_PARTIAL_EVAL,
  HELP_PARTIAL_JUDGE,
  HELP_SHARE_BASIS,
  HELP_SHARE_UNAVAILABLE,
  NO_HOLDINGS_TEXT,
  combineRiskState,
  holdingsStateOf,
  marketStateOf,
  riskHelpParagraphs,
  riskStateFromQueries,
  type HoldingsState,
  type MarketState,
} from "./riskCombination";

function summary(over: Partial<DeclineSummary> = {}): DeclineSummary {
  return {
    total: 4, judgeable: 4, inBand: 2, inBandShare: 60, bands: [], evalPartial: false,
    regime: "하락장 · 4거래일째", flowDate: "2026-10-14", ...over,
  };
}
function ev(mp: Record<string, unknown>, items: HoldingsMarketEvidenceItem[] = []): HoldingsMarketEvidenceResponse {
  return {
    status: "ok", asof: "2026-10-14", holdings: items,
    judgment_summary: { market_position: mp, holdings: { available: true, top_holdings: [], coverage: {} }, data_status: {} },
    price_basis: { reference_date: "2026-10-14", reference_ticker: "069500", kodex200_start_date_5d: null, kodex200_start_date_20d: null, date_mismatch: [] },
    warnings: [],
  } as unknown as HoldingsMarketEvidenceResponse;
}
const BEAR = { available: true, regime_code: "bear", regime_label: "하락장", regime_streak_days: 4, regime_streak_at_least: false };

describe("marketStateOf — 기존 판정 코드만(화면 문구를 거꾸로 읽지 않음)", () => {
  it.each([
    [{ available: true, regime_code: "bear", regime_label: "하락장" }, "down"],
    [{ available: true, regime_code: "bull", regime_label: "상승장" }, "not_down"],
    [{ available: true, regime_code: "neutral", regime_label: "보합장" }, "not_down"],
    [{ available: true, regime_code: "unavailable", regime_label: "판정불가" }, "unknown"],
    [{ available: true, regime_code: "strong_bear", regime_label: "하락장" }, "unknown"], // 모르는 코드 ≠ 하락 아님
    [{ available: true, regime_code: null, regime_label: "하락장" }, "unknown"],
    [{ available: false, regime_code: "bear", regime_label: "하락장" }, "unknown"],
    [{}, "unknown"],
  ])("%j → %s", (mp, expected) => {
    expect(marketStateOf(ev(mp))).toBe(expected);
  });
  it("근거 응답 없음 → 미확인", () => {
    expect(marketStateOf(null)).toBe("unknown");
  });
});

describe("holdingsStateOf", () => {
  it("빈 보유 → 대상 없음 · 요약 없음 → 미확인", () => {
    expect(holdingsStateOf(summary(), true)).toBe("no_holdings");
    expect(holdingsStateOf(null, false)).toBe("unknown");
  });
  it("N > 0 이면 일부 판정 불가여도 하락 있음", () => {
    expect(holdingsStateOf(summary({ inBand: 1, judgeable: 2, total: 4 }), false)).toBe("down_found");
  });
  it("N = 0 · A = B → 하락 없음 / N = 0 · A < B → 미확인 / B = 0 → 미확인", () => {
    expect(holdingsStateOf(summary({ inBand: 0 }), false)).toBe("none_found");
    expect(holdingsStateOf(summary({ inBand: 0, judgeable: 3 }), false)).toBe("unknown");
    expect(holdingsStateOf(summary({ inBand: 0, judgeable: 0, total: 0 }), false)).toBe("unknown");
  });
});

describe("combineRiskState — 설계 §4 표 전체(판정 Q4 문구)", () => {
  const table: [MarketState, Exclude<HoldingsState, "no_holdings">, string][] = [
    ["down", "down_found", "시장·보유 동반 약세"],
    ["not_down", "down_found", "보유 하락 구간 확인"],
    ["down", "none_found", "시장 하락 · 보유 하락 구간 미해당"],
    ["not_down", "none_found", "시장·보유 하락 구간 미해당"],
    ["unknown", "down_found", "보유 하락 구간 확인 · 시장 판정 불가"],
    ["down", "unknown", "시장 하락 · 보유 판정 불완전"],
    ["not_down", "unknown", "자료 확인 필요"],
    ["unknown", "unknown", "자료 확인 필요"],
    ["unknown", "none_found", "보유 하락 구간 미해당 · 시장 판정 불가"],
  ];
  it.each(table)("시장 %s · 보유 %s → %s", (m, h, text) => {
    expect(combineRiskState(m, h, null).text).toBe(text);
  });
  it.each(["down", "not_down", "unknown"] as MarketState[])("시장 %s · 대상 없음 → 보유 판정 대상 없음", (m) => {
    expect(combineRiskState(m, "no_holdings", null).text).toBe(NO_HOLDINGS_TEXT);
  });
  it("모든 문구에 '안전' · '정상' · '위험' · '하락 신호'가 없다", () => {
    for (const [m, h] of table) {
      expect(combineRiskState(m, h, null).text).not.toMatch(/안전|정상|위험|하락 신호|경보/);
    }
  });
  it("부분 판정 표시: A < B 일 때만", () => {
    expect(combineRiskState("down", "down_found", summary({ judgeable: 3 })).partial).toBe(true);
    expect(combineRiskState("down", "down_found", summary()).partial).toBe(false);
    expect(combineRiskState("down", "unknown", summary({ inBand: 0, judgeable: 3 })).partial).toBe(true);
    expect(combineRiskState("down", "unknown", null).partial).toBe(false);
  });
});

// ── 두 조회 → 판정(두 화면 공통) ─────────────────────────────────────────────
const band = (state: HoldingsDeclineBand["state"], reason: HoldingsDeclineBand["unjudged_reason"] = null) =>
  ({ judgeable: reason === null, state, label: state ? `PC ${state}` : null, return_20d_pct_1dp: null, unjudged_reason: reason }) as HoldingsDeclineBand;
const item = (ticker: string, b: HoldingsDeclineBand) =>
  ({ ticker, holding: {}, short_term_momentum: { status: "ok", return_5d_pct: -1, return_20d_pct: -3, excess_vs_kodex200_20d_pctp: 0 }, evidence_notes: [], decline_band: b }) as unknown as HoldingsMarketEvidenceItem;
const ok = <T,>(data: T, stale = false): QueryState<T> => ({ phase: "success", data, stale });
const H = (rows: [string, number | null][]) =>
  ok({ items: rows.map(([ticker, e]) => ({ ticker, name: ticker, eval_amount: e, invested_amount: 1000 })) } as unknown as EnrichedHoldingsResult);

describe("riskStateFromQueries — 판정 순서 · 실제 실패 사유(판정 Q1)", () => {
  const holdings = H([["A1", 3000], ["B2", 1000]]);
  const evidence = ok(ev(BEAR, [item("A1", band("D10_PLUS")), item("B2", band(null))]));

  it("받는 중이면 판정하지 않는다", () => {
    expect(riskStateFromQueries({ phase: "loading" }, evidence)).toBeNull();
    expect(riskStateFromQueries(holdings, { phase: "loading" })).toBeNull();
    expect(riskStateFromQueries(holdings, { phase: "idle" })).toBeNull();
  });
  it("두 응답 성공 → 13 요약으로 판정 · 시장 국면 문구", () => {
    const v = riskStateFromQueries(holdings, evidence)!;
    expect(v.combo.text).toBe("시장·보유 동반 약세");
    expect(v.summary?.inBand).toBe(1);
    expect(v.regime).toBe("하락장 · 4거래일째");
    expect(v.failed).toBeNull();
  });
  it("다시 읽기 실패(stale)여도 받은 자료로 판정", () => {
    const v = riskStateFromQueries(H([["A1", 3000], ["B2", 1000]]), ok(ev(BEAR, [item("A1", band("D10_PLUS")), item("B2", band(null))]), true))!;
    expect(v.combo.text).toBe("시장·보유 동반 약세");
    expect(v.failed).toBeNull();
  });
  it.each([
    ["holdings" as const, { phase: "error" } as QueryState<EnrichedHoldingsResult>, evidence, "시장 하락 · 보유 판정 불완전"],
    ["evidence" as const, holdings, { phase: "error" } as QueryState<HoldingsMarketEvidenceResponse>, "자료 확인 필요"],
    ["both" as const, { phase: "error" } as QueryState<EnrichedHoldingsResult>, { phase: "error" } as QueryState<HoldingsMarketEvidenceResponse>, "자료 확인 필요"],
  ])("실패 %s → 상태 · 그 조회만 사유", (failed, h, e, text) => {
    const v = riskStateFromQueries(h, e)!;
    expect(v.failed).toBe(failed);
    expect(v.combo.text).toBe(text);
    expect(v.summary).toBeNull(); // 확인되지 않은 건수를 0 으로 만들지 않는다
  });
  it("정상 응답의 빈 보유는 근거 실패보다 먼저 → 대상 없음 · 실패 사유 없음", () => {
    const v = riskStateFromQueries(H([]), { phase: "error" })!;
    expect(v.combo.text).toBe(NO_HOLDINGS_TEXT);
    expect(v.failed).toBeNull();
    expect(riskStateFromQueries(H([]), ok(ev(BEAR)))!.combo.text).toBe(NO_HOLDINGS_TEXT);
  });
  it("모르는 시장 코드면 백엔드 라벨이 있어도 국면 이름을 붙이지 않는다", () => {
    const v = riskStateFromQueries(holdings, ok(ev({ ...BEAR, regime_code: "strong_bear" }, [item("A1", band("D10_PLUS")), item("B2", band(null))])))!;
    expect(v.combo.text).toBe("보유 하락 구간 확인 · 시장 판정 불가");
    expect(v.regime).toBeNull();
  });
  it("평가금액 부족은 비중만 — 가격 하락 분류는 그대로", () => {
    const v = riskStateFromQueries(H([["A1", null], ["B2", null]]), evidence)!;
    expect(v.combo.text).toBe("시장·보유 동반 약세");
    expect(v.summary?.inBandShare).toBeNull();
  });
  it("넘겨받은 행을 쓰면 다시 만들지 않는다(같은 결과)", () => {
    const a = riskStateFromQueries(holdings, evidence)!;
    const b = riskStateFromQueries(holdings, evidence, [])!; // 빈 행을 넘기면 그 행으로 계산
    expect(a.summary?.total).toBe(2);
    expect(b.summary?.total).toBe(0);
  });
  it("실패 사유 문장", () => {
    expect(FAILURE_TEXT).toEqual({
      holdings: "보유 자료를 불러오지 못했습니다.",
      evidence: "확인 근거를 불러오지 못했습니다.",
      both: "보유 자료와 확인 근거를 불러오지 못했습니다.",
    });
  });
});

describe("riskHelpParagraphs — 뜻 → 기준 → 지금 해당하는 제한만(판정 §5)", () => {
  const base = { failed: null, regime: "하락장 · 4거래일째" } as const;
  it("동반 약세 · 전부 판정 · 평가 정상 → 뜻 · 구간 기준 · 비중 기준 · 시장 기준(제한 없음)", () => {
    const s = summary();
    const p = riskHelpParagraphs({ ...base, summary: s, combo: combineRiskState("down", "down_found", s) });
    expect(p[0]).toContain("시장 국면이 각 종목 하락의 원인이라는 뜻은 아닙니다");
    expect(p).toEqual([p[0], HELP_BAND_BASIS, HELP_SHARE_BASIS, HELP_MARKET_BASIS]);
    expect(p.join(" ")).not.toContain("‘미해당’");
  });
  it("미해당 상태일 때만 '미해당' 뜻 · 일부 판정 · 평가 부족일 때만 그 문단", () => {
    const s = summary({ inBand: 0, judgeable: 3, evalPartial: true });
    const p = riskHelpParagraphs({ ...base, summary: s, combo: combineRiskState("down", "unknown", s) });
    expect(p).toContain(HELP_PARTIAL_JUDGE);
    expect(p).toContain(HELP_PARTIAL_EVAL);
    const none = summary({ inBand: 0 });
    const q = riskHelpParagraphs({ ...base, summary: none, combo: combineRiskState("not_down", "none_found", none) });
    expect(q[0]).toContain("‘미해당’은 지금 기준에 해당하지 않았다는 뜻입니다");
    expect(q).not.toContain(HELP_PARTIAL_JUDGE);
    expect(q).not.toContain(HELP_PARTIAL_EVAL);
  });
  it("자료가 없으면 구간 · 비중 기준을 넣지 않고 · 시장 미확인이면 시장 기준도 없음", () => {
    const p = riskHelpParagraphs({ summary: null, failed: "evidence", regime: null, combo: combineRiskState("unknown", "unknown", null) });
    expect(p).toEqual(["시장 국면이나 보유 하락 구간을 판정할 자료가 부족합니다."]);
  });
  it("PC 와 OCI 차이 · 반올림 · 평가금액 합산 기준이 도움말에 있다(기본 화면에서 옮긴 내용)", () => {
    expect(HELP_BAND_BASIS).toContain("소수 첫째 자리로 반올림한 뒤");
    expect(HELP_BAND_BASIS).toContain("OCI 알림과 값이 다를 수 있습니다");
    expect(HELP_SHARE_BASIS).toContain("평가금액을 종목별로 합산");
  });
  it("비중이 '확인 불가'면 '확인 불가' 문단 · '확인된 평가금액으로 계산' 문단은 넣지 않는다(기본 화면과 같은 조건)", () => {
    const s = summary({ inBandShare: null, evalPartial: true });
    const p = riskHelpParagraphs({ ...base, summary: s, combo: combineRiskState("down", "down_found", s) });
    expect(p).toContain(HELP_SHARE_UNAVAILABLE);
    expect(p).not.toContain(HELP_PARTIAL_EVAL);
  });
  it("일부 판정 불가 문단은 원인을 한 가지로 단정하지 않고 종목 상세로 보낸다", () => {
    expect(HELP_PARTIAL_JUDGE).toContain("경우 등");
    expect(HELP_PARTIAL_JUDGE).toContain("종목별 이유는 「확인 근거」 종목 상세");
  });
});
