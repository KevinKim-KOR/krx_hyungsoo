// POC5-13 — 시장 국면 + PC 최근 20저장일 하락 구간 요약 조립(순수 함수).
// 비중은 정상 enriched 종목 합산(aggregateHoldingsByTicker)만 쓴다 — 근거 응답의 평가금액은 일부러 다르게 둔다.
import { describe, it, expect } from "vitest";
import type {
  EnrichedHolding,
  HoldingsDeclineBand,
  HoldingsMarketEvidenceItem,
  HoldingsMarketEvidencePriceDates,
  HoldingsMarketEvidenceResponse,
  PriceBasis,
} from "@/lib/api";
import { buildRiskEvidenceRows, type RiskEvidenceRow } from "./helpers";
import {
  PARTIAL_EVAL_TEXT,
  buildDeclineSummary,
  declineDetailText,
  fmtShare,
} from "./declineSummary";

function enriched(ticker: string, evalAmt: number | null, invested = 1000): EnrichedHolding {
  return {
    ticker,
    name: ticker + "명",
    quantity: 1,
    avg_buy_price: invested,
    invested_amount: invested,
    current_price: evalAmt,
    price_asof: "2026-10-14",
    price_source: "naver",
    eval_amount: evalAmt,
    pnl_amount: evalAmt === null ? null : evalAmt - invested,
    pnl_rate_pct: null,
    buy_weight_pct: null,
    market_weight_pct: 1, // 화면은 이 값을 쓰지 않는다(종목 합산 함수가 평가금액으로 다시 계산)
    price_missing: evalAmt === null,
    calc_missing: evalAmt === null,
  };
}

const band = (
  state: HoldingsDeclineBand["state"],
  v: number | null,
  reason: HoldingsDeclineBand["unjudged_reason"] = null,
): HoldingsDeclineBand => ({
  judgeable: reason === null,
  state,
  label: state ? `PC 20저장일 하락 ${{ D10_PLUS: "10% 이상", D8_10: "8~10%", D5_8: "5~8%" }[state]}` : null,
  return_20d_pct_1dp: reason === null ? v : null,
  unjudged_reason: reason,
});

function evItem(
  ticker: string,
  decline: HoldingsDeclineBand | null,
  r20: number | null = -3,
): HoldingsMarketEvidenceItem {
  return {
    ticker,
    name: ticker + "명",
    // 근거 응답의 평가금액 — 일부러 엉뚱한 값(쓰이면 시험이 깨짐 · POC5-14 이전 복사 값 흉내).
    holding: { quantity: 1, avg_buy_price: 1, evaluation_amount: 999_999, pnl_rate_pct: 99 },
    topn_match: { status: "unavailable", rank: null, basis: null, candidate_name: null },
    returns: { status: "ok", one_month_return_pct: 1, three_month_return_pct: 2 },
    excess_return: { status: "ok", vs_kodex200_1m_pctp: 1, vs_kodex200_3m_pctp: 2 },
    short_term_momentum: {
      status: "ok",
      return_5d_pct: -1,
      return_10d_pct: -2,
      return_20d_pct: r20,
      excess_vs_kodex200_5d_pctp: 0,
      excess_vs_kodex200_10d_pctp: 0,
      excess_vs_kodex200_20d_pctp: 0,
    },
    constituents_overlap: { status: "ok", overlap_with_market_core: [] },
    nav_discount: {
      status: "ok", source: null, asof: null, nav: null, market_price: null,
      discount_rate_pct: null, flag: null, message: null,
    },
    evidence_notes: [],
    decline_band: decline,
  } as HoldingsMarketEvidenceItem;
}

function response(
  items: HoldingsMarketEvidenceItem[],
  marketPosition: Record<string, unknown> = {
    available: true,
    regime_code: "bear",
    regime_label: "하락장",
    regime_streak_days: 4,
    regime_streak_at_least: false,
  },
): HoldingsMarketEvidenceResponse {
  return {
    status: "ok",
    asof: "2026-10-14",
    holdings_asof: null,
    market_asof: "2026-10-14",
    market_context: null,
    summary: {
      total_holdings_count: items.length, matched_topn_count: 0, not_in_current_topn_count: 0,
      evidence_unavailable_count: 0, constituents_available_count: 0,
      constituents_unavailable_count: 0, nav_discount_unavailable_count: 0,
    },
    holdings: items,
    judgment_summary: {
      market_position: marketPosition,
      holdings: { available: true, top_holdings: [], coverage: { total: 0, need_check: 0, ok: 0 } },
      data_status: {},
    },
    price_basis: {
      reference_date: "2026-10-14",
      reference_ticker: "069500",
      kodex200_start_date_5d: "2026-10-07",
      kodex200_start_date_20d: "2026-09-15",
      date_mismatch: [],
    },
    warnings: [],
  } as unknown as HoldingsMarketEvidenceResponse;
}

// 069500 두 계좌(3000 + 1000) · 111111 2000 · 222222 1500 · 333333 1500 · 444444 1000 → 합 10,000.
const ENRICHED = [
  enriched("069500", 3000, 2000),
  enriched("069500", 1000, 1000),
  enriched("111111", 2000),
  enriched("222222", 1500),
  enriched("333333", 1500),
  enriched("444444", 1000),
];
const ITEMS = [
  evItem("069500", band("D10_PLUS", -12.3)),
  evItem("069500", band("D10_PLUS", -12.3)),
  evItem("111111", band("D5_8", -6.1)),
  evItem("222222", band("D8_10", -8.0)),
  evItem("333333", band(null, -2.0)),
  evItem("444444", band(null, null, "date_mismatch"), null),
];

function summarize(enrichedRows = ENRICHED, items = ITEMS, mp?: Record<string, unknown>) {
  const ev = mp ? response(items, mp) : response(items);
  return buildDeclineSummary(buildRiskEvidenceRows(enrichedRows, items).rows, ev);
}

describe("buildDeclineSummary (POC5-13)", () => {
  it("종목 수 = ticker · 비중 = enriched 종목 합산 원값 합(근거 응답 평가금액 무시)", () => {
    const s = summarize();
    expect(s.total).toBe(5); // 6줄 · 5종목
    expect(s.judgeable).toBe(4);
    expect(s.inBand).toBe(3);
    expect(s.inBandShare).toBeCloseTo(75, 10); // 40 + 20 + 15
    expect(s.bands.map((b) => [b.state, b.count])).toEqual([
      ["D10_PLUS", 1],
      ["D8_10", 1],
      ["D5_8", 1],
    ]);
    expect(s.bands.map((b) => b.share)).toEqual([40, 15, 20]);
    expect(s.evalPartial).toBe(false);
    expect(s.regime).toBe("하락장 · 4거래일째");
    expect(s.flowDate).toBe("2026-10-14");
    expect(fmtShare(s.inBandShare)).toBe("75.0%");
  });

  it("일부 평가 미확인 — 확인된 평가금액 기준 · 그 종목만 든 구간은 '확인 불가'(0% 로 채우지 않음)", () => {
    const rows = ENRICHED.map((e) => (e.ticker === "111111" ? enriched("111111", null) : e));
    const s = summarize(rows);
    expect(s.evalPartial).toBe(true);
    expect(s.inBand).toBe(3); // 구간 판정은 평가 여부와 따로
    // 분모 8,000(평가 있는 계좌 행 합) · 069500 50% + 222222 18.75%
    expect(s.inBandShare).toBeCloseTo(68.75, 10);
    expect(fmtShare(s.inBandShare)).toBe("68.8%");
    const d58 = s.bands.find((b) => b.state === "D5_8");
    expect(d58).toEqual({ state: "D5_8", count: 1, share: null });
    expect(fmtShare(null)).toBe("확인 불가");
    expect(PARTIAL_EVAL_TEXT).toBe("확인된 평가금액 기준 · 일부 평가 자료 미확인");
  });

  it("같은 종목 한 계좌만 평가 미확인이어도 그 종목 합산값은 비어 있다(부분 합 아님)", () => {
    const rows = [enriched("069500", 3000, 2000), enriched("069500", null), ...ENRICHED.slice(2)];
    const s = summarize(rows);
    expect(s.evalPartial).toBe(true);
    const d10 = s.bands.find((b) => b.state === "D10_PLUS");
    expect(d10?.share).toBeNull();
  });

  it("평가금액이 하나도 없으면 비중은 모두 '확인 불가'", () => {
    const rows = ENRICHED.map((e) => enriched(e.ticker, null));
    const s = summarize(rows);
    expect(s.inBand).toBe(3);
    expect(s.inBandShare).toBeNull();
    expect(s.bands.every((b) => b.share === null)).toBe(true);
    // 빈 구간 · 0종목도 '확인 불가'(분모 0 — 0% 로 채우지 않음).
    const none = ITEMS.map((it) => ({ ...it, decline_band: band(null, -1.0) }));
    const z = summarize(rows, none);
    expect(z.inBand).toBe(0);
    expect(z.inBandShare).toBeNull();
    expect(z.bands.map((b) => [b.count, b.share])).toEqual([[0, null], [0, null], [0, null]]);
  });

  it("하락 구간 0종목이면 0종목 · 0.0% 이고 판정 범위는 그대로 보인다(위험 없음으로 바꾸지 않음)", () => {
    const items = ITEMS.map((it) =>
      it.ticker === "444444" ? it : { ...it, decline_band: band(null, -1.0) },
    );
    const s = summarize(ENRICHED, items);
    expect(s.inBand).toBe(0);
    expect(fmtShare(s.inBandShare)).toBe("0.0%");
    expect(`${s.judgeable}/${s.total}`).toBe("4/5");
  });

  it("계좌 간 흐름 값이 다르면 그 종목은 판정하지 않음(구간 · 판정 가능에서 빠짐)", () => {
    const items = [evItem("069500", band("D10_PLUS", -12.3), -12.3), evItem("069500", band("D10_PLUS", -12.3), -11.0), ...ITEMS.slice(2)];
    const s = summarize(ENRICHED, items);
    expect(s.inBand).toBe(2);
    expect(s.judgeable).toBe(3);
  });

  it("시장 국면 문구 — 지속일 · '이상' · 지속일 없음 · 국면 없음", () => {
    expect(summarize(ENRICHED, ITEMS, { available: true, regime_label: "하락장", regime_streak_days: 120, regime_streak_at_least: true }).regime).toBe("하락장 · 120거래일째 이상");
    expect(summarize(ENRICHED, ITEMS, { available: true, regime_label: "보합장", regime_streak_days: null }).regime).toBe("보합장");
    expect(summarize(ENRICHED, ITEMS, { available: true, regime_code: "bull", regime_label: null, regime_streak_days: 2 }).regime).toBe("상승장 · 2거래일째");
    expect(summarize(ENRICHED, ITEMS, { available: false, regime_label: "판정불가" }).regime).toBeNull();
  });
});

describe("declineDetailText (POC5-13 상세 줄)", () => {
  const dates = (comparison: HoldingsMarketEvidencePriceDates["comparison"], end = "2026-10-14") => ({
    end_date: end,
    start_date_5d: "2026-10-07",
    start_date_20d: "2026-09-15",
    comparison,
  });
  const row = (over: Partial<RiskEvidenceRow>): RiskEvidenceRow =>
    ({ ticker: "T", name: "T", evidence_conflict: false, price_dates: dates("ok"), decline_band: null, ...over }) as RiskEvidenceRow;
  // KODEX200 20일 기간 시작 = 2026-09-15(종목 기본 fixture 와 같음).
  const BASIS: PriceBasis = {
    reference_date: "2026-10-14",
    reference_ticker: "069500",
    kodex200_start_date_5d: "2026-10-07",
    kodex200_start_date_20d: "2026-09-15",
    date_mismatch: [],
  };

  it("판정한 종목 — 이름 · 판정에 쓴 값 · 실제 기간", () => {
    expect(declineDetailText(row({ decline_band: band("D8_10", -8.0) }), BASIS)).toBe(
      "PC 20저장일 하락 8~10% · 20저장일 변화 -8.0%(판정에 쓴 소수 첫째 자리 값) · 기간 2026-09-15 ~ 2026-10-14 · PC 저장 종가",
    );
    expect(declineDetailText(row({ decline_band: band(null, -4.9) }), BASIS)).toBe(
      "해당 없음 · 20저장일 변화 -4.9%(판정에 쓴 소수 첫째 자리 값) · 기간 2026-09-15 ~ 2026-10-14",
    );
  });

  it("20일 시작일이 KODEX200 과 다르면 판정하고 상대 비교를 비운 사유를 붙인다", () => {
    const t = declineDetailText(
      row({
        decline_band: band("D5_8", -5.0),
        price_dates: { ...dates("window_mismatch"), start_date_20d: "2026-09-12" },
      }),
      BASIS,
    );
    expect(t).toBe(
      "PC 20저장일 하락 5~8% · 20저장일 변화 -5.0%(판정에 쓴 소수 첫째 자리 값) · 기간 2026-09-12 ~ 2026-10-14(KODEX200 비교 기간과 달라 상대 비교는 비워 둠) · PC 저장 종가",
    );
  });

  it("5일 기간만 다르고 20일 기간이 같으면 비교 기간 사유를 붙이지 않는다(20일 대비 값은 남아 있음)", () => {
    const t = declineDetailText(
      row({
        decline_band: band("D8_10", -9.0),
        price_dates: { ...dates("window_mismatch"), start_date_5d: "2026-10-06" },
      }),
      BASIS,
    );
    expect(t).toBe(
      "PC 20저장일 하락 8~10% · 20저장일 변화 -9.0%(판정에 쓴 소수 첫째 자리 값) · 기간 2026-09-15 ~ 2026-10-14 · PC 저장 종가",
    );
  });

  it("판정 안 함 — 이유별 문구(구간 밖과 다름)", () => {
    expect(
      declineDetailText(
        row({ decline_band: band(null, null, "date_mismatch"), price_dates: dates("date_mismatch", "2026-08-12") }),
        BASIS,
      ),
    ).toBe("판정하지 않음 — 이 종목의 최근 저장일(2026-08-12)이 PC 가격 흐름 기준일(2026-10-14)과 다릅니다(자료 확인 필요).");
    expect(declineDetailText(row({ decline_band: band(null, null, "insufficient_history") }), null)).toContain(
      "저장 종가가 21개보다 적어",
    );
    expect(declineDetailText(row({ decline_band: band(null, null, "invalid_value") }), null)).toBe(
      "판정하지 않음 — 20저장일 변화 값을 확인할 수 없습니다(자료 확인 필요).",
    );
    expect(declineDetailText(row({ evidence_conflict: true }), null)).toBe(
      "판정하지 않음 — 계좌 간 가격 흐름 값이 달라 확인이 필요합니다.",
    );
    for (const t of [
      declineDetailText(row({ decline_band: band(null, null, "insufficient_history") }), null),
      declineDetailText(row({ decline_band: null }), null),
    ]) {
      expect(t).not.toContain("해당 없음");
    }
  });
});
