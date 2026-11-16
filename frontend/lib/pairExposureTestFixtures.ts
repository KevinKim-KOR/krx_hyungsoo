// POC6-31 STEP 4 시험용 — 구성종목 비교 응답(서버 `constituents_pair_exposure.build` 와 같은 모양 · 가짜 값 · 금액 없음).
import type { PairExposure, PairQuery } from "./api/pairExposure";

export function pairOk(q: Pick<PairQuery, "candidate" | "holding">, over: Partial<PairExposure> = {}): PairExposure {
  return {
    status: "ok",
    condition: {},
    candidate: {
      ticker: q.candidate,
      name: "후보",
      state: "confirmed",
      asof: "2026-11-13",
      stored_rows: 30,
      held: false,
      held_weight: null,
      held_use: null,
    },
    holding: q.holding
      ? {
          ticker: q.holding,
          name: "고른 보유",
          kind: "etf",
          held: true,
          weight: "25",
          state: "confirmed",
          asof: "2026-11-13",
          stored_rows: 30,
          range: "depth",
        }
      : null,
    dates: { candidate: "2026-11-13", holding: q.holding ? "2026-11-13" : null, exposure: "2026-11-13" },
    basis: { rows: 3, priced_rows: 3, partial: false, price_date: { state: "KNOWN", min: "2026-11-13", max: "2026-11-13" } },
    scope: {
      holdings: 2,
      included: { count: 1, weight: "85" },
      direct: { count: 0, weight: "0" },
      other_date: { count: 0, weight: "0", dates: [] },
      unconfirmed: { count: 0, weight: "0" },
      no_data: { count: 1, weight: "15" },
      no_weight: { count: 0 },
      ranges: { depth: 1, legacy: 0, unverified: 0, full: 0, full_min: null, full_max: null },
      etfs: [
        {
          ticker: q.holding ?? "H",
          name: "고른 보유",
          weight: "85",
          use: "sum",
          state: "confirmed",
          asof: "2026-11-13",
          stored_rows: 30,
          range: "depth",
        },
      ],
    },
    stocks: [
      {
        key: "LLY.N",
        name: "일라이 릴리",
        rank: 1,
        candidate_weight: "29.98",
        pair: q.holding ? { state: "found", weight: "3.12" } : null,
        exposure: {
          terms: [
            { ticker: "H", name: "고른 보유", holding_weight: "85", constituent_weight: "3.12", product: "2.652" },
          ],
          direct: [],
          zero_confirmed: [],
          unknown: [],
          unknown_weight: "0",
          raw: "2.652",
          value: "2.65",
        },
        reference: [],
      },
    ],
    candidate_top_rows: 10,
    candidate_non_stock_rows: 0,
    fingerprint: `fp-${q.candidate}-${q.holding ?? "none"}`,
    date_line:
      "기준일: 후보 구성 2026-11-13 · " +
      (q.holding ? "고른 보유(고른 보유) 구성 2026-11-13" : "고른 보유 없음") +
      " · 노출 합계 2026-11-13 · 보유 평가 2026-11-13 · 현금 제외 보유 평가액 기준",
    pair_dates_differ: false,
    stock_notes: { "LLY.N": null },
    ...over,
  };
}
