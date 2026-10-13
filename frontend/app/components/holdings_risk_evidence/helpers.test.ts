// POC3-05 보유 ETF 확인 근거 헬퍼 test — 순수 변환 로직.
import { describe, it, expect } from "vitest";
import {
  DEFAULT_EVIDENCE_SORT,
  EVIDENCE_SORT_OPTIONS,
  NO_REASON_TEXT,
  buildRiskEvidenceRows,
  evidenceGuidance,
  lowestFiveDayRows,
  sortEvidenceRows,
  type RiskEvidenceRow,
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

// ── POC5-UI-02 sortEvidenceRows ───────────────────────────────────────────────
describe("sortEvidenceRows (POC5-UI-02)", () => {
  function row(ticker: string, over: Partial<RiskEvidenceRow> = {}): RiskEvidenceRow {
    return {
      ticker,
      name: ticker,
      eval_amount: 1000,
      market_weight_pct: 10,
      pnl_rate_pct: 0,
      return_5d_pct: 0,
      return_20d_pct: 0,
      excess_vs_kodex200_20d_pctp: 0,
      need_check: false,
      five_d_sortable: true,
      notes: [],
      price_missing: false,
      calc_missing: false,
      evidence_conflict: false,
      flow_unavailable: false,
      price_dates: null,
      ...over,
    };
  }
  const t = (rows: RiskEvidenceRow[]) => rows.map((r) => r.ticker);

  it("키마다 방향 — 평가 비중만 큰 값부터, 나머지는 작은 값부터 · 정렬은 네 가지(KODEX200 대비 없음)", () => {
    const rows = [
      row("a", { market_weight_pct: 10, pnl_rate_pct: 5, return_5d_pct: 2, return_20d_pct: -1, excess_vs_kodex200_20d_pctp: 0.3 }),
      row("b", { market_weight_pct: 30, pnl_rate_pct: -5, return_5d_pct: -2, return_20d_pct: 1, excess_vs_kodex200_20d_pctp: -0.3 }),
      row("c", { market_weight_pct: 20, pnl_rate_pct: 0, return_5d_pct: 0, return_20d_pct: 0, excess_vs_kodex200_20d_pctp: 0.1 }),
    ];
    expect(t(sortEvidenceRows(rows, "weight"))).toEqual(["b", "c", "a"]);
    expect(t(sortEvidenceRows(rows, "pnl_rate"))).toEqual(["b", "c", "a"]);
    expect(t(sortEvidenceRows(rows, "ret5"))).toEqual(["b", "c", "a"]);
    expect(t(sortEvidenceRows(rows, "ret20"))).toEqual(["a", "c", "b"]);
    expect(DEFAULT_EVIDENCE_SORT).toBe("ret5");
    expect(EVIDENCE_SORT_OPTIONS.map(([, label]) => label)).toEqual([
      "평가 비중",
      "손익률",
      "5일 변화",
      "20일 변화",
    ]);
  });

  it("값 없는 행은 어느 키에서나 맨 뒤 · 값 없는 행끼리와 같은 값끼리는 들어온 순서", () => {
    // 들어온 순서를 종목코드 역순으로 둔다 — 종목코드 순으로 동률을 깨는 변이(옛 lowestFiveDayRows 규칙)를 잡는다.
    const rows = [
      row("n2", { return_5d_pct: null, market_weight_pct: null }),
      row("y", { return_5d_pct: 1, market_weight_pct: 5 }),
      row("n1", { return_5d_pct: null, market_weight_pct: null }),
      row("x", { return_5d_pct: 1, market_weight_pct: 5 }),
      row("z", { return_5d_pct: -1, market_weight_pct: 9 }),
    ];
    expect(t(sortEvidenceRows(rows, "ret5"))).toEqual(["z", "y", "x", "n2", "n1"]);
    expect(t(sortEvidenceRows(rows, "weight"))).toEqual(["z", "y", "x", "n2", "n1"]);
  });

  it("반올림하면 같아지는 값도 원래 숫자로 · 행 수 · 입력 배열 불변 · 자료 확인 필요 행도 값으로 정렬", () => {
    // 화면 표시(소수 둘째 자리)로는 둘 다 1.23 — 표시값으로 정렬하면 들어온 순서(p, q)가 남는다.
    const rows = [
      row("p", { return_5d_pct: 1.2349 }),
      row("q", { return_5d_pct: 1.2341, need_check: true, five_d_sortable: false }),
    ];
    const before = t(rows);
    const out = sortEvidenceRows(rows, "ret5");
    expect(t(out)).toEqual(["q", "p"]);
    expect(out).toHaveLength(2);
    expect(t(rows)).toEqual(before);
  });

  it("유한수가 아닌 값(NaN)도 값 없는 행처럼 맨 뒤 — 다른 행 순서를 깨지 않는다", () => {
    const rows = [
      row("a", { pnl_rate_pct: 0 }),
      row("b", { pnl_rate_pct: Number.NaN }),
      row("c", { pnl_rate_pct: -50 }),
    ];
    expect(t(sortEvidenceRows(rows, "pnl_rate"))).toEqual(["c", "a", "b"]);
  });
});

// ── POC5-UI-02 §11-3 자료 확인 안내 ──────────────────────────────────────────
describe("buildRiskEvidenceRows 안내 칸 · evidenceGuidance (POC5-UI-02 §11)", () => {
  it("계좌 행의 시세 · 계산 미확인 · 계좌 간 흐름 불일치 · evidence_notes(같은 문구 한 번)를 모은다", () => {
    const { rows } = buildRiskEvidenceRows(
      [
        enriched("AAA", { price_missing: true }),
        enriched("AAA", { calc_missing: true }),
        enriched("BBB"),
      ],
      [
        { ...evItem("AAA", { return_5d_pct: -1 }), evidence_notes: ["메모 1", "공통 메모"] },
        { ...evItem("AAA", { return_5d_pct: -2 }), evidence_notes: ["공통 메모", "메모 2"] },
        { ...evItem("BBB"), evidence_notes: ["정상 메모"] },
      ],
    );
    const a = rows.find((r) => r.ticker === "AAA")!;
    const b = rows.find((r) => r.ticker === "BBB")!;
    expect([a.price_missing, a.calc_missing, a.evidence_conflict]).toEqual([true, true, true]);
    expect(a.notes).toEqual(["메모 1", "공통 메모", "메모 2"]);
    expect(evidenceGuidance(a)).toEqual([
      "보유 시세를 확인할 수 없습니다.",
      "보유 평가 계산값을 확인할 수 없습니다.",
      "같은 종목의 계좌별 단기 흐름 값(상태 · 5일 · 20일 · KODEX200 대비)이 서로 다릅니다.",
      "메모 1",
      "공통 메모",
      "메모 2",
    ]);
    // 다른 종목의 사유가 섞이지 않는다.
    expect([b.price_missing, b.calc_missing, b.evidence_conflict]).toEqual([false, false, false]);
    expect(evidenceGuidance(b)).toEqual(["정상 메모"]);
  });

  it("자료 확인 필요인데 사유가 없으면 '상세 사유 정보가 제공되지 않습니다' · 정상이고 안내가 없으면 빈 목록", () => {
    const { rows } = buildRiskEvidenceRows([enriched("CCC"), enriched("DDD")], [
      { ...evItem("DDD"), evidence_notes: [] },
    ]);
    const c = rows.find((r) => r.ticker === "CCC")!; // 시장 evidence 없음 → 자료 확인 필요 · 사유 없음
    const d = rows.find((r) => r.ticker === "DDD")!;
    expect(c.need_check).toBe(true);
    expect(evidenceGuidance(c)).toEqual([NO_REASON_TEXT]);
    expect(d.need_check).toBe(false);
    expect(evidenceGuidance(d)).toEqual([]);
  });

  it("일반 문구만 있는 자료 확인 필요(단기 흐름 partial)는 사유 미제공 문구를 먼저 · 일반 문구는 그대로", () => {
    const { rows } = buildRiskEvidenceRows([enriched("EEE")], [
      {
        ...evItem("EEE", { status: "partial", return_20d_pct: null }),
        evidence_notes: ["현재 Market Discovery 후보에 포함되어 있지 않습니다."],
      },
    ]);
    const e = rows[0];
    expect([e.need_check, e.flow_unavailable]).toEqual([true, false]);
    expect(evidenceGuidance(e)).toEqual([
      NO_REASON_TEXT,
      "현재 Market Discovery 후보에 포함되어 있지 않습니다.",
    ]);
  });

  it("단기 흐름 unavailable 은 백엔드 문구가 사유라 사유 미제공 문구를 붙이지 않는다", () => {
    const { rows } = buildRiskEvidenceRows([enriched("FFF")], [
      {
        ...evItem("FFF", {
          status: "unavailable",
          return_5d_pct: null,
          return_20d_pct: null,
          excess_vs_kodex200_20d_pctp: null,
        }),
        evidence_notes: [
          "현재 Market Discovery 후보에 포함되어 있지 않습니다.",
          "단기 흐름은 데이터 부족으로 확인할 수 없습니다.",
        ],
      },
    ]);
    const f = rows[0];
    expect([f.need_check, f.flow_unavailable]).toEqual([true, true]);
    expect(evidenceGuidance(f)).toEqual([
      "현재 Market Discovery 후보에 포함되어 있지 않습니다.",
      "단기 흐름은 데이터 부족으로 확인할 수 없습니다.",
    ]);
  });
});

// ── POC5-09 판정 §9-4 — 가격 흐름 기준일 · 비교 기간 사유 ──────────────────────
describe("evidenceGuidance 가격 기준일 사유 (POC5-09)", () => {
  const basis = {
    reference_date: "2026-10-08",
    reference_ticker: "069500",
    kodex200_start_date_5d: "2026-09-30",
    kodex200_start_date_20d: "2026-09-07",
    date_mismatch: [{ ticker: "000660", name: "SK하이닉스", end_date: "2026-08-12" }],
  };
  const MD = "현재 Market Discovery TOP 10 후보에 포함되어 있지 않습니다.";

  function rowFor(
    stm: Parameters<typeof evItem>[1],
    priceDates: HoldingsMarketEvidenceItem["price_dates"],
  ) {
    const { rows } = buildRiskEvidenceRows(
      [enriched("000660")],
      [{ ...evItem("000660", stm), evidence_notes: [MD], price_dates: priceDates }],
    );
    return rows[0];
  }

  it("기준일 불일치 — 실제 날짜 사유를 맨 위에 · 사유 미제공 문구 없음 · 일반 문구 유지", () => {
    const r = rowFor(
      {
        status: "unavailable",
        return_5d_pct: null,
        return_20d_pct: null,
        excess_vs_kodex200_20d_pctp: null,
      },
      {
        end_date: "2026-08-12",
        start_date_5d: "2026-08-05",
        start_date_20d: "2026-07-14",
        comparison: "date_mismatch",
      },
    );
    expect(r.need_check).toBe(true);
    expect(r.price_dates?.end_date).toBe("2026-08-12");
    expect(evidenceGuidance(r, basis)).toEqual([
      "저장 가격 기준일: 2026-08-12 / PC 비교 기준일: 2026-10-08 — 기준일이 달라 현재 비교에 사용하지 않습니다.",
      MD,
    ]);
  });

  it("비교 기간 불일치 — 다른 기간만 실제 날짜로 · 둘 다 같으면 일반 기간 문구", () => {
    const pd = (s5: string, s20: string) => ({
      end_date: "2026-10-08",
      start_date_5d: s5,
      start_date_20d: s20,
      comparison: "window_mismatch" as const,
    });
    const stm = { status: "partial" as const, excess_vs_kodex200_20d_pctp: null };
    expect(evidenceGuidance(rowFor(stm, pd("2026-09-30", "2026-09-04")), basis)).toEqual([
      "KODEX200 대비 20일: 종목 비교 기간 2026-09-04 ~ 2026-10-08 / KODEX200 비교 기간 2026-09-07 ~ 2026-10-08 — 기간이 달라 비교값을 비워 두었습니다.",
      MD,
    ]);
    expect(evidenceGuidance(rowFor(stm, pd("2026-09-29", "2026-09-04")), basis)).toHaveLength(3);
    expect(evidenceGuidance(rowFor(stm, pd("2026-09-30", "2026-09-07")), basis)).toEqual([
      "KODEX200 비교 기간이 종목과 달라 일부 비교값을 비워 두었습니다.",
      MD,
    ]);
  });

  it("기준일이 같은 정상 행은 날짜 사유 없음 · 응답에 price_dates 가 없으면 기존 안내 그대로", () => {
    const ok = rowFor(
      {},
      {
        end_date: "2026-10-08",
        start_date_5d: "2026-09-30",
        start_date_20d: "2026-09-07",
        comparison: "ok",
      },
    );
    expect(evidenceGuidance(ok, basis)).toEqual([MD]);
    const none = rowFor({}, undefined);
    expect(none.price_dates).toBeNull();
    expect(evidenceGuidance(none, null)).toEqual([MD]);
  });
});

