// POC3-05 보유 ETF 확인 근거 헬퍼 test — 순수 변환 로직.
import { describe, it, expect } from "vitest";
import {
  DEFAULT_EVIDENCE_SORT,
  EVIDENCE_SORT_OPTIONS,
  FILTERED_NOTES,
  FILTERED_NOTE_PREFIXES,
  NO_REASON_TEXT,
  OVERLAP_LIST_PREFIX,
  STOCK_RANK_TEXT,
  WEEKLY_RANK_FAILED,
  WEEKLY_RANK_LOADING,
  buildRiskEvidenceRows,
  dateRoleLines,
  diffText,
  directionText,
  evidenceGuidance,
  isFilteredNote,
  lowestFiveDayRows,
  mainHoldingsText,
  navCells,
  navRawLines,
  overlapFoundText,
  sortEvidenceRows,
  weeklyRankView,
  type RiskEvidenceRow,
} from "./helpers";
import { discountPctText } from "@/lib/navLabels";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type {
  ConstituentsSummaryResponse,
  EnrichedHolding,
  HoldingsMarketEvidenceItem,
  HoldingsMarketEvidenceNavDiscount,
} from "@/lib/api";
import type { CompareSummary } from "@/lib/api/etfCompare";
import type { QueryState } from "@/lib/api/queryCache";
import { link, summaryOk } from "@/lib/etfCompareTestFixtures";

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
      decline_band: null,
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
      "5저장일 변화",
      "20저장일 변화",
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
      "같은 종목의 계좌별 단기 흐름 값(상태 · 5저장일 · 20저장일 · KODEX 200 대비)이 서로 다릅니다.",
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

  it("일반 문구만 있는 자료 확인 필요(단기 흐름 partial)는 사유 미제공 문구 · 옛 후보 문구는 거름(POC6-33 E6)", () => {
    const { rows } = buildRiskEvidenceRows([enriched("EEE")], [
      {
        ...evItem("EEE", { status: "partial", return_20d_pct: null }),
        evidence_notes: ["현재 Market Discovery 후보에 포함되어 있지 않습니다."],
      },
    ]);
    const e = rows[0];
    expect([e.need_check, e.flow_unavailable]).toEqual([true, false]);
    expect(evidenceGuidance(e)).toEqual([NO_REASON_TEXT]);
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
    // 자료 부족 안내는 남기고 옛 후보 문구만 거른다(판정 Q23).
    expect(evidenceGuidance(f)).toEqual(["단기 흐름은 데이터 부족으로 확인할 수 없습니다."]);
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

  it("기준일 불일치 — 실제 날짜 사유를 맨 위에 · 사유 미제공 문구 없음 · 옛 후보 문구는 거름", () => {
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
      "이 종목 마지막 저장일: 2026-08-12 / 가격 기준일: 2026-10-08 — 두 날짜가 달라 현재 비교에 사용하지 않습니다.",
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
      "KODEX 200 대비 20저장일: 종목 비교 기간 2026-09-04 ~ 2026-10-08 / KODEX 200 비교 기간 2026-09-07 ~ 2026-10-08 — 기간이 달라 비교값을 비워 두었습니다.",
    ]);
    expect(evidenceGuidance(rowFor(stm, pd("2026-09-29", "2026-09-04")), basis)).toHaveLength(2);
    expect(evidenceGuidance(rowFor(stm, pd("2026-09-30", "2026-09-07")), basis)).toEqual([
      "KODEX 200 비교 기간이 종목과 달라 일부 비교값을 비워 두었습니다.",
    ]);
  });

  it("기준일이 같은 정상 행은 날짜 사유 없음 · 응답에 price_dates 가 없어도 옛 후보 문구는 거름", () => {
    const ok = rowFor(
      {},
      {
        end_date: "2026-10-08",
        start_date_5d: "2026-09-30",
        start_date_20d: "2026-09-07",
        comparison: "ok",
      },
    );
    expect(evidenceGuidance(ok, basis)).toEqual([]);
    const none = rowFor({}, undefined);
    expect(none.price_dates).toBeNull();
    expect(evidenceGuidance(none, null)).toEqual([]);
  });
});

// ── POC6-33 — 「확인 근거」 선택 상세 글(PLAN §3 · 판정 §3 · §4) ─────────────────────────────
// 검증자 r1 B-6 — 서버 시험(tests/test_holdings_market_evidence.py)과 같은 공용 고정 자료로 화면 거르기 상수를 대조한다
// (POC6-32 lib/marketCommonEvidenceCases.test.ts 와 같은 방식 · 저장소 파일만 읽음 · 합성 문장).
// holdings_risk_evidence → components → app → frontend → 저장소 루트
const REPO_ROOT = path.dirname(
  path.dirname(path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))))),
);
const FILTER_FIXTURE = JSON.parse(
  readFileSync(path.join(REPO_ROOT, "tests", "fixtures", "poc6_33_filtered_notes.json"), "utf8"),
) as { filtered_exact: string[]; filtered_prefixes: string[]; kept: string[] };

describe("필요한 자료 안내 거르기 (POC6-33 E6 · 판정 Q23 · I-3)", () => {
  it("화면 거르기 상수 = 서버 시험과 같은 공용 고정 자료(정확 일치 · 앞부분 · 남기는 문장)", () => {
    expect(FILTER_FIXTURE.filtered_exact.length).toBeGreaterThan(0);
    expect([...FILTERED_NOTES]).toEqual(FILTER_FIXTURE.filtered_exact);
    expect([...FILTERED_NOTE_PREFIXES]).toEqual(FILTER_FIXTURE.filtered_prefixes);
    for (const k of FILTER_FIXTURE.kept) expect(isFilteredNote(k)).toBe(false);
  });

  // builder 문장 예(app/holdings_market_evidence.py _build_evidence_notes · app/pc_price_basis.py · 서버 시험이 고정 자료로 확인).
  const BUILDER_FILTERED = [
    "현재 Market Discovery 후보와 일치합니다.",
    "현재 Market Discovery TOP 10 후보에 포함되어 있지 않습니다.",
    "현재 Market Discovery 후보에 포함되어 있지 않습니다.",
    "현재 Market Discovery 후보 목록을 확인할 수 없습니다.",
    "20거래일 KODEX200 대비 단기 흐름 차이 +1.25%p.",
    "20거래일 KODEX200 대비 단기 흐름 차이 -3.40%p.",
    "NAV / 괴리율 확인이 필요합니다.",
    "구성종목 기준 현재 후보군의 반복 핵심 종목과 일부 겹칩니다.",
    "구성종목 기준 현재 후보군의 반복 핵심 종목과 겹치는 항목이 없습니다.",
    "구성종목 데이터가 캐시에 없어 비교할 수 없습니다.",
    "현재 후보군의 구성종목 데이터를 확인할 수 없습니다.",
    "NAV / 괴리율은 source 미연동으로 확인할 수 없습니다.",
  ];
  const KEEP = "단기 흐름은 데이터 부족으로 확인할 수 없습니다.";

  it("판정 세 갈래 문장은 모두 거르고 · 자료 부족 안내와 모르는 문장은 남긴다(builder 순서 그대로)", () => {
    for (const n of BUILDER_FILTERED) expect(isFilteredNote(n)).toBe(true);
    for (const n of FILTERED_NOTES) expect(BUILDER_FILTERED).toContain(n);
    expect(isFilteredNote(KEEP)).toBe(false);
    expect(isFilteredNote("다른 안내")).toBe(false);
    const { rows } = buildRiskEvidenceRows([enriched("GGG")], [
      {
        ...evItem("GGG", { status: "unavailable", return_5d_pct: null, return_20d_pct: null, excess_vs_kodex200_20d_pctp: null }),
        evidence_notes: [BUILDER_FILTERED[1], KEEP, ...BUILDER_FILTERED.slice(6), "다른 안내"],
      },
    ]);
    expect(evidenceGuidance(rows[0])).toEqual([KEEP, "다른 안내"]);
  });
});

describe("방향 줄 글 (POC6-33 E4 · 판정 Q37 · I-14)", () => {
  it("보이는 값 0.00 = '변화 없음'(부호 없음) · 0.01 이상 올랐음 · −0.01 이하 내렸음 · 값 없음", () => {
    expect(directionText(2.5)).toBe("+2.50%(올랐음)");
    expect(directionText(0.01)).toBe("+0.01%(올랐음)");
    expect(directionText(-3)).toBe("-3.00%(내렸음)");
    expect(directionText(-0.01)).toBe("-0.01%(내렸음)");
    expect(directionText(0)).toBe("0.00%(변화 없음)");
    expect(directionText(0.004)).toBe("0.00%(변화 없음)");
    expect(directionText(-0.004)).toBe("0.00%(변화 없음)");
    expect(directionText(null)).toBe("자료 확인 필요");
    expect(diffText(-1.5)).toBe("-1.50%p");
    expect(diffText(0.3)).toBe("+0.30%p");
    expect(diffText(-0.004)).toBe("0.00%p");
    expect(diffText(null)).toBe("자료 확인 필요");
  });
});

describe("주간 순위 줄 (POC6-33 E5 · 판정 Q22 · Q24 · Q33 · Q49 · Q52 · I-7 · I-8 · I-12)", () => {
  const ok = (items: ReturnType<typeof link>[], over: Parameters<typeof summaryOk>[0] = {}): QueryState<CompareSummary> => ({
    phase: "success",
    data: summaryOk({ holdings: { status: "ok", items }, ...over }),
    stale: false,
  });
  // RESULT 판정 §1 — 순위 이름 = '1개월 수익률 상위 30'(목록 정렬 · 상위 10개 후보 목록과 구별).
  const BASIS = "「주간 ETF 점검」과 같은 조회 · 1개월 수익률 상위 30 · 10/12 → 11/9 · 인버스 · 레버리지 · 합성 · 선물 제외";
  const INTRADAY = { date: "2026-11-09", state: "intraday" as const, fetched_at_kst: "2026-11-09T10:00:00+09:00" };
  const UNKNOWN = { date: "2026-11-09", state: "unknown" as const, fetched_at_kst: null };

  it.each([
    ["상위 30 안", { top_rank: 3, side: "top" as const, side_rank: 3 }, "1개월 수익률 상위 30 중 3위 · 10/12 → 11/9 · 인버스 · 레버리지 · 합성 · 선물 제외"],
    ["상위 · 장중", { top_rank: 3, side: "top" as const, side_rank: 3, end_price: INTRADAY }, "1개월 수익률 상위 30 중 3위 · 10/12 → 11/9 · 인버스 · 레버리지 · 합성 · 선물 제외 · 장중 저장값 기준"],
    ["상위 · 마감 미확인", { top_rank: 3, side: "top" as const, side_rank: 3, end_price: UNKNOWN }, "1개월 수익률 상위 30 중 3위 · 10/12 → 11/9 · 인버스 · 레버리지 · 합성 · 선물 제외 · 마감값 확인 필요"],
    ["하위 30(Q24)", { side: "bottom" as const, side_rank: 2, top_rank: null }, "순위권 밖 · 1개월 수익률 상위 30 밖 · 10/12 → 11/9"],
    ["가운데", { side: null, side_rank: null, top_rank: null }, "순위권 밖 · 1개월 수익률 상위 30 밖 · 10/12 → 11/9"],
    ["순위권 밖 · 장중", { side: null, top_rank: null, end_price: INTRADAY }, "순위권 밖 · 1개월 수익률 상위 30 밖 · 10/12 → 11/9 · 장중 저장값 기준"],
    ["순위권 밖 · 마감 미확인", { side: null, top_rank: null, end_price: UNKNOWN }, "순위권 밖 · 1개월 수익률 상위 30 밖 · 10/12 → 11/9 · 마감값 확인 필요"],
    ["순위권 밖 · 끝 가격 없음", { side: null, top_rank: null, end_price: null }, "순위권 밖 · 1개월 수익률 상위 30 밖 · 10/12 → 11/9"],
    ["상·하위 공통(모집단 60 미만)", { side: "bottom" as const, side_rank: 4, top_rank: 7 }, "1개월 수익률 상위 30 중 7위 · 10/12 → 11/9 · 인버스 · 레버리지 · 합성 · 선물 제외"],
  ])("모집단 안 — %s", (_, over, main) => {
    const v = weeklyRankView(ok([link({ ticker: "A1", ...over })]), "A1");
    expect(v).toEqual({ main, basis: BASIS, stock: false });
  });

  it.each([
    ["규칙상 제외", "filter_excluded" as const, "규칙상 제외 — 인버스 · 레버리지 · 합성 · 선물 제외 조건 · 가격 · 손익 근거는 아래 그대로"],
    ["저장 가격 없음", "no_price" as const, "자료 확인 불가 — 저장 가격 없음"],
    ["같은 기간 아님", "period_differs" as const, "자료 확인 불가 — 같은 기간 수익률을 구하지 못함"],
  ])("모집단 밖 — %s · 끝 가격 상태를 붙이지 않는다", (_, reason, main) => {
    const v = weeklyRankView(
      ok([link({ ticker: "A1", in_population: false, out_reason: reason, basis_return: null, end_price: INTRADAY })]),
      "A1",
    );
    expect(v).toEqual({ main, basis: BASIS, stock: false });
  });

  it("개별 주식이 확인되면 'ETF 순위 대상 아님' · 조회 조건 줄 없음(is_stock · out_reason 어느 쪽이든)", () => {
    const a = link({ ticker: "S1", is_stock: true, in_population: false, out_reason: "stock", basis_return: null });
    expect(weeklyRankView(ok([a]), "S1")).toEqual({ main: STOCK_RANK_TEXT, basis: null, stock: true });
    const b = link({ ticker: "S2", is_stock: true, in_population: false, out_reason: null, basis_return: null });
    expect(weeklyRankView(ok([b]), "S2").stock).toBe(true);
  });

  it("조회 중 · 조회 실패 · 목록을 만들지 못함 · 응답에 종목 없음 — 개별 주식으로 보지 않는다", () => {
    expect(weeklyRankView({ phase: "loading" }, "A1")).toEqual({ main: WEEKLY_RANK_LOADING, basis: null, stock: false });
    expect(weeklyRankView({ phase: "idle" }, "A1").main).toBe(WEEKLY_RANK_LOADING);
    expect(weeklyRankView({ phase: "error" }, "A1")).toEqual({ main: WEEKLY_RANK_FAILED, basis: null, stock: false });
    // 검증자 r1 F1 — 다시 읽기 실패로 이전 성공값만 남은 상태(stale)는 이전 순위 대신 '조회 실패'.
    const prev = ok([link({ ticker: "A1", top_rank: 3, side: "top", side_rank: 3 })]);
    if (prev.phase !== "success") throw new Error("fixture");
    expect(weeklyRankView({ ...prev, stale: true }, "A1")).toEqual({ main: WEEKLY_RANK_FAILED, basis: null, stock: false });
    expect(weeklyRankView({ ...prev, stale: false }, "A1").main).toMatch(/ 중 3위 · /);
    const notOk: QueryState<CompareSummary> = {
      phase: "success",
      data: { status: "no_common_period", message: "x", basis: "one_month" },
      stale: false,
    };
    expect(weeklyRankView(notOk, "A1")).toEqual({
      main: "자료 확인 불가 — KODEX 200 저장 가격으로 같은 기간을 정하지 못함",
      basis: null,
      stock: false,
    });
    expect(weeklyRankView(ok([]), "A1")).toEqual({
      main: "자료 확인 불가 — 주간 순위 자료에 이 종목 없음",
      basis: BASIS,
      stock: false,
    });
    const errHold: QueryState<CompareSummary> = {
      phase: "success",
      data: summaryOk({ holdings: { status: "error", items: [] } }),
      stale: false,
    };
    expect(weeklyRankView(errHold, "A1").main).toBe("자료 확인 불가 — 주간 순위의 보유 목록을 읽지 못함");
  });

  // RESULT 판정 §1 — 기간 이름은 코드에 두지 않고 응답 basis 값에서 읽는다(같은 '수익률 상위 n' 이름 · 조건 줄도 같음).
  it("기간 이름 = 응답 basis · 순위 · 순위권 밖 · 조건 줄이 모두 '수익률 상위 n'", () => {
    const three = (over: Omit<Parameters<typeof link>[0], "ticker">) =>
      weeklyRankView(ok([link({ ...over, ticker: "A1" })], { basis: "three_month", n: 20 }), "A1");
    const inTop = three({ top_rank: 4, side: "top", side_rank: 4 });
    expect(inTop.main).toBe("3개월 수익률 상위 20 중 4위 · 10/12 → 11/9 · 인버스 · 레버리지 · 합성 · 선물 제외");
    expect(inTop.basis).toBe(
      "「주간 ETF 점검」과 같은 조회 · 3개월 수익률 상위 20 · 10/12 → 11/9 · 인버스 · 레버리지 · 합성 · 선물 제외",
    );
    expect(three({ side: null, side_rank: null, top_rank: null }).main).toBe(
      "순위권 밖 · 3개월 수익률 상위 20 밖 · 10/12 → 11/9",
    );
  });
});

// RESULT 판정 §2-1(E7 · I-4) — 구성종목 중복: 별도 후보 목록 이름 · 찾은 종목 = 이름 · 이 ETF 편입 비중(없으면 이름만).
describe("구성종목 중복 글 (POC6-33 RESULT 판정 §2-1)", () => {
  it("비교 후보 목록 머리 = 주간 순위 목록과 별도", () => {
    expect(OVERLAP_LIST_PREFIX).toBe("비교 후보 목록(주간 순위 목록과 별도): ");
  });
  it("찾은 겹침 = 이름 · 이 ETF 편입 비중(소수 둘째 자리) · 비중 없음 = 이름만 · 이름 없음 = 코드", () => {
    expect(overlapFoundText({ ticker: "X9", name: "구성 9", weight_pct: 1.234 })).toBe("구성 9 · 이 ETF 편입 비중 1.23%");
    expect(overlapFoundText({ ticker: "X9", name: "구성 9", weight_pct: 0 })).toBe("구성 9 · 이 ETF 편입 비중 0.00%");
    expect(overlapFoundText({ ticker: "X9", name: "구성 9", weight_pct: null })).toBe("구성 9");
    expect(overlapFoundText({ ticker: "X9", name: null, weight_pct: null })).toBe("X9");
    expect(overlapFoundText({ ticker: null, name: null, weight_pct: null })).toBe("-");
  });
});

describe("날짜 역할 · 주요 편입 · 순자산가치(NAV) 묶음 (POC6-33 E8 · E9 · E10)", () => {
  it("날짜 역할 = 응답 날짜만 · 기준일이 다른 종목은 수익률 역할 줄 없음", () => {
    const { rows } = buildRiskEvidenceRows([enriched("HHH")], [
      {
        ...evItem("HHH"),
        price_dates: { end_date: "2026-11-18", start_date_5d: "2026-11-11", start_date_20d: "2026-10-21", comparison: "ok" },
      },
    ]);
    const item = {
      ...evItem("HHH"),
      volume_trend: {
        asof_date: "2026-11-18",
        points: [
          { date: "2026-10-22", volume: 1 },
          { date: "2026-11-18", volume: 2 },
        ],
        missing_count: 0,
      },
      stored_volume: {
        ticker: "HHH", status: "ok" as const, asof_date: "2026-11-18", source: "x", volume: 1, window_size: 20,
        window_start_date: "2026-10-21", window_end_date: "2026-11-17", window_date_count: 20, valid_count: 20,
        avg_prev20: 1, avg_status: "ok" as const, ratio: 1, ratio_status: "ok" as const,
      },
    };
    expect(dateRoleLines(rows[0], item)).toEqual([
      "20저장일 수익률 = 시작 종가 10/21 → 끝 종가 11/18(종가 21개 · 변화 20구간)",
      "[세부 흐름 보기] 차트 = 표시 기간 10/22 ~ 11/18 · 최근 2개 저장일",
      "거래량 평균 = 비교 구간 10/21 ~ 11/17",
    ]);
    const stale = { ...rows[0], price_dates: { ...rows[0].price_dates!, comparison: "date_mismatch" as const } };
    expect(dateRoleLines(stale, null)).toEqual([]);
  });

  it("주요 편입 = 그 응답의 구성 기준일 · 기존 상태 글 · 저장 행 수 · 주식 상위 · 미수집 · 읽기 실패 · 파일 없음", () => {
    const base: ConstituentsSummaryResponse = {
      status: "ok", message: null, ticker: "TEST01", name: null, state: "top_rows", state_label: "상위 10행만 확인",
      asof: "2026-11-16", stored_rows: 10,
      top_stocks: [
        { name: "구성 1", weight_pct: 12.34 },
        { name: null, weight_pct: null },
      ],
    };
    expect(mainHoldingsText(base)).toEqual({
      head: "구성 기준일 11/16 · 상위 10행만 확인 · 저장 10행",
      stocks: "구성 1 12.3% · 이름 확인 불가 비중 확인 불가",
    });
    expect(mainHoldingsText({ ...base, top_stocks: [] }).stocks).toBeNull();
    expect(mainHoldingsText({ ...base, state: "not_collected", state_label: "미수집" }).head).toBe("미수집 — 저장된 구성 자료 없음");
    expect(mainHoldingsText({ ...base, status: "error", state: "error" }).head).toBe("구성 자료를 읽지 못함");
    expect(mainHoldingsText({ status: "missing", message: "x", ticker: "TEST01", name: null }).head).toBe(
      "구성 자료 확인 불가 — 시장 자료 파일 없음",
    );
  });

  const nav = (over: Partial<HoldingsMarketEvidenceNavDiscount> = {}): HoldingsMarketEvidenceNavDiscount => ({
    status: "ok", source: "naver_etf_item_list", asof: "2026-11-18", nav: 10010.4, market_price: 10000,
    discount_rate_pct: -0.1, flag: null, message: null, ...over,
  });
  const cellMap = (n: HoldingsMarketEvidenceNavDiscount) =>
    Object.fromEntries(navCells(n).map((c) => [c.label, c.value]));

  it("여섯 칸(시장가 · NAV · 괴리율 부호 · 기준일 · 출처 · 수집 상태) · 같은 사전(lib/navLabels)", () => {
    expect(cellMap(nav())).toEqual({
      시장가: "10,000", NAV: "10,010", 괴리율: "-0.10%", 기준일: "2026-11-18", 출처: "네이버", "수집 상태": "수집됨",
    });
    expect(navRawLines(nav())).toEqual([]);
    // 이전 목록 재사용 = 재저장일 · 사전 밖 = 기타 출처 · 상태 확인 필요 · 원문은 [자세히] 줄로만.
    const odd = nav({ status: "partial", source: "TEST_SRC", message: "원문 안내" });
    expect(cellMap(odd)).toMatchObject({ 기준일: "재저장일 2026-11-18", 출처: "기타 출처", "수집 상태": "이전 목록 재사용" });
    expect(navRawLines(odd)).toEqual(["받은 안내 원문: 원문 안내", "출처 원문: TEST_SRC"]);
    const weird = nav({ status: "warning" as HoldingsMarketEvidenceNavDiscount["status"], flag: "odd_flag" });
    expect(cellMap(weird)["수집 상태"]).toBe("상태 확인 필요");
    expect(navRawLines(weird)).toEqual(["수집 상태 원문: warning", "괴리율 표시 원문: odd_flag"]);
    expect(navCells(weird)[2].flag).toBeNull();
    // NAV 저장 행 없음(builder 표지 not_integrated) — 출처 '-' · 확인 불가 · 값 '-' · 영어 안내는 [자세히] 줄.
    const none = nav({
      status: "unavailable", source: "not_integrated", asof: null, nav: null, market_price: null, discount_rate_pct: null,
      message: "NAV / discount source not integrated",
    });
    expect(cellMap(none)).toEqual({
      시장가: "-", NAV: "-", 괴리율: "-", 기준일: "-", 출처: "-", "수집 상태": "확인 불가",
    });
    expect(navRawLines(none)).toEqual(["받은 안내 원문: NAV / discount source not integrated"]);
  });

  it("괴리율 부호 · 표시 글자 · 숫자 색(3 · 5 경계 · 음수 · 0.00)", () => {
    expect(discountPctText(3)).toBe("+3.00%");
    expect(discountPctText(-5)).toBe("-5.00%");
    expect(discountPctText(-0.004)).toBe("0.00%");
    expect(discountPctText(0.004)).toBe("0.00%");
    expect(discountPctText(null)).toBe("-");
    expect(navCells(nav({ discount_rate_pct: -0.004 }))[2].value).toBe("0.00%");
    const c3 = navCells(nav({ discount_rate_pct: 3, flag: "discount_check_needed" }))[2];
    expect([c3.flag, c3.flagClass, c3.color]).toEqual(["괴리 확인 필요(3% 이상)", "nav-flag", "var(--warn)"]);
    const c5 = navCells(nav({ discount_rate_pct: -5, flag: "discount_warning" }))[2];
    expect([c5.flag, c5.color]).toEqual(["괴리 주의(5% 이상)", "var(--danger)"]);
    const c2 = navCells(nav({ discount_rate_pct: 2.99 }))[2];
    expect([c2.flag, c2.color]).toEqual([null, "var(--fg)"]);
  });
});
