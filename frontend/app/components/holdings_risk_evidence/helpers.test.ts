// POC3-05 보유 ETF 확인 근거 헬퍼 test — 순수 변환 로직.
import { describe, it, expect } from "vitest";
import {
  buildRiskEvidenceRows,
  lowestFiveDayRows,
} from "./helpers";
import type { EnrichedHolding, HoldingsMarketEvidenceItem } from "@/lib/api";

function enriched(
  ticker: string,
  over: Partial<EnrichedHolding> = {},
): EnrichedHolding {
  return {
    ticker,
    name: ticker + "명",
    quantity: 10,
    avg_buy_price: 1000,
    invested_amount: 10000,
    current_price: 1100,
    price_asof: "2026-07-24",
    price_source: "naver",
    eval_amount: 11000,
    pnl_amount: 1000,
    pnl_rate_pct: 10,
    buy_weight_pct: 50,
    market_weight_pct: 50,
    price_missing: false,
    calc_missing: false,
    ...over,
  };
}

function evItem(
  ticker: string,
  stm: Partial<HoldingsMarketEvidenceItem["short_term_momentum"]> = {},
  over: Partial<HoldingsMarketEvidenceItem> = {},
): HoldingsMarketEvidenceItem {
  return {
    ticker,
    name: ticker + "명",
    holding: {
      quantity: 10,
      avg_buy_price: 1000,
      evaluation_amount: 11000,
      pnl_rate_pct: 10,
    },
    topn_match: { status: "unavailable", rank: null, basis: null, candidate_name: null },
    returns: { status: "ok", one_month_return_pct: 1, three_month_return_pct: 2 },
    excess_return: { status: "ok", vs_kodex200_1m_pctp: 1, vs_kodex200_3m_pctp: 2 },
    short_term_momentum: {
      status: "ok",
      return_5d_pct: -1,
      return_10d_pct: -2,
      return_20d_pct: -3,
      excess_vs_kodex200_5d_pctp: -0.5,
      excess_vs_kodex200_10d_pctp: -1,
      excess_vs_kodex200_20d_pctp: -1.5,
      ...stm,
    },
    constituents_overlap: { status: "ok", overlap_with_market_core: [] },
    nav_discount: {
      status: "ok",
      source: null,
      asof: null,
      nav: null,
      market_price: null,
      discount_rate_pct: null,
      flag: null,
      message: null,
    },
    evidence_notes: [],
    ...over,
  };
}

describe("buildRiskEvidenceRows", () => {
  it("정상 종목은 확인됨(need_check=false), 값이 그대로 온다", () => {
    const res = buildRiskEvidenceRows(
      [enriched("069500")],
      [evItem("069500")],
    );
    expect(res.rows).toHaveLength(1);
    const r = res.rows[0];
    expect(r.need_check).toBe(false);
    expect(r.return_5d_pct).toBe(-1);
    expect(r.return_20d_pct).toBe(-3);
    expect(r.excess_vs_kodex200_20d_pctp).toBe(-1.5);
    expect(res.coverage).toEqual({ total: 1, ok: 1, need_check: 0 });
  });

  it("Q4: short_term_momentum.status=partial 이면 자료 확인 필요(값은 유지)", () => {
    const res = buildRiskEvidenceRows(
      [enriched("069500")],
      [evItem("069500", { status: "partial", return_5d_pct: -1 })],
    );
    expect(res.rows[0].need_check).toBe(true);
    expect(res.rows[0].return_5d_pct).toBe(-1); // partial 이어도 존재 수치 표시
  });

  it("Q4: 5일 값 null 이면 자료 확인 필요", () => {
    const res = buildRiskEvidenceRows(
      [enriched("069500")],
      [evItem("069500", { return_5d_pct: null })],
    );
    expect(res.rows[0].need_check).toBe(true);
  });

  it("Q4: enriched price_missing 이면 자료 확인 필요", () => {
    const res = buildRiskEvidenceRows(
      [enriched("069500", { price_missing: true, eval_amount: null })],
      [evItem("069500")],
    );
    expect(res.rows[0].need_check).toBe(true);
  });

  it("Q4: evidence item 미존재(not_loaded) 이면 자료 확인 필요", () => {
    const res = buildRiskEvidenceRows([enriched("069500")], []);
    expect(res.rows[0].need_check).toBe(true);
  });

  it("Q7: 같은 ticker 여러 계좌 — 평가는 aggregate 통합(1행)", () => {
    const res = buildRiskEvidenceRows(
      [
        enriched("069500", { account_group: "A", eval_amount: 11000, invested_amount: 10000 }),
        enriched("069500", { account_group: "B", eval_amount: 22000, invested_amount: 20000 }),
      ],
      [evItem("069500")],
    );
    expect(res.rows).toHaveLength(1); // ticker 통합
    expect(res.rows[0].eval_amount).toBe(33000);
  });

  it("Q7: 같은 ticker evidence 흐름 값이 계좌별로 다르면 자료 확인 필요(임의 선택 금지)", () => {
    const res = buildRiskEvidenceRows(
      [enriched("069500", { account_group: "A" }), enriched("069500", { account_group: "B" })],
      [
        evItem("069500", { return_5d_pct: -1 }),
        evItem("069500", { return_5d_pct: -9 }), // 다른 값
      ],
    );
    expect(res.rows).toHaveLength(1);
    expect(res.rows[0].need_check).toBe(true);
  });

  it("급락(falling) 관련 필드가 행에 없다 (이번 Step 제외)", () => {
    const res = buildRiskEvidenceRows([enriched("069500")], [evItem("069500")]);
    expect(res.rows[0]).not.toHaveProperty("falling");
    expect(JSON.stringify(res.rows[0])).not.toContain("falling");
  });
});

describe("lowestFiveDayRows (Q5)", () => {
  it("status ok & 5일 유효 종목만 오름차순, 동률 ticker 오름차순, 최대 N", () => {
    const res = buildRiskEvidenceRows(
      [enriched("A00001"), enriched("A00002"), enriched("A00003"), enriched("A00004")],
      [
        evItem("A00001", { return_5d_pct: -5 }),
        evItem("A00002", { return_5d_pct: -1 }),
        evItem("A00003", { return_5d_pct: -5 }), // 동률 → ticker 오름차순
        evItem("A00004", { status: "unavailable", return_5d_pct: null }), // 제외
      ],
    );
    const low = lowestFiveDayRows(res.rows, 3);
    expect(low.map((r) => r.ticker)).toEqual(["A00001", "A00003", "A00002"]);
    // unavailable 종목은 정렬·건수에서 제외
    expect(low.map((r) => r.ticker)).not.toContain("A00004");
  });

  it("유효 5일 종목이 없으면 빈 배열 (0건 위장 아님)", () => {
    const res = buildRiskEvidenceRows(
      [enriched("069500")],
      [evItem("069500", { status: "unavailable", return_5d_pct: null })],
    );
    expect(lowestFiveDayRows(res.rows, 3)).toEqual([]);
  });
});
