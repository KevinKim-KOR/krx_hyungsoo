// POC5-21 — AI 해석용 복사문의 실제 계산 기간(설계 V1 §3 · PLAN 판정 Q1 · Q2).
// - 수익률 줄마다 (사용 종가 시작 → 끝) · 날짜 없으면 '계산 기간 확인 불가' · 값 없으면 '-' 그대로.
// - 머리말은 시장 저장 최신일을 따로 적는다('○○ 기준 결과'라고 쓰지 않음).
// - KODEX200 대비 = 수익률 차이(%p) + 두 기간 · 제목 · 요청 문구도 그 뜻.
import { describe, it, expect } from "vitest";
import type {
  ConstituentsAnalysisResponse,
  MarketCandidate,
  MarketContext,
  MarketContextKodex200,
  MarketPeriodReturn,
} from "./api";
import { buildMarketDiscoveryCopyText } from "./marketDiscoveryCopyText";

const ASOF = "2026-10-14";
const FILTERS = {
  exclude_inverse: true,
  exclude_leveraged: true,
  exclude_synthetic: true,
  exclude_futures: true,
};
const KODEX: MarketContextKodex200 = {
  status: "ok",
  return_20d_pct: -15.06,
  return_60d_pct: -13.23,
  return_1m_start_date: "2026-09-10",
  return_3m_start_date: "2026-07-14",
  return_end_date: ASOF,
};

function r(pct: number | null, start?: string, end?: string): MarketPeriodReturn {
  return {
    return_pct: pct,
    basis_start_date: start ?? null,
    basis_end_date: ASOF,
    ...(start ? { price_start_date: start } : {}),
    ...(end ? { price_end_date: end } : {}),
  };
}

function ctx(k: MarketContextKodex200 = KODEX): MarketContext {
  return {
    status: "ok",
    regime_label: "하락장",
    regime_code: "bear",
    regime_reasons: [],
    kodex200: k,
    kospi: { status: "unavailable" },
    warnings: [],
  } as unknown as MarketContext;
}

const STM_OK = {
  status: "ok" as const,
  return_5d_pct: 1.04,
  return_10d_pct: 17.22,
  return_20d_pct: 12.97,
  excess_vs_kodex200_5d_pctp: 15.25,
  excess_vs_kodex200_10d_pctp: 30.45,
  excess_vs_kodex200_20d_pctp: 28.04,
  start_dates: { five_d: "2026-10-06", ten_d: "2026-09-28", twenty_d: "2026-09-10" },
  end_date: ASOF,
  kodex200_start_dates: { five_d: "2026-10-06", ten_d: "2026-09-27", twenty_d: "2026-09-10" },
  kodex200_end_date: ASOF,
};

function cand(over: Partial<MarketCandidate> = {}): MarketCandidate {
  return {
    rank: 1,
    ticker: "0005D0",
    name: "SOL 전고체배터리&실리콘음극재",
    tags: [],
    returns: {
      daily: r(5.4, "2026-10-13", ASOF),
      one_month: r(22.27, "2026-09-14", ASOF),
      three_month: r(33.79, "2026-07-16", ASOF),
    },
    excess_return: { vs_kodex200_1m_pctp: 37.33, vs_kodex200_3m_pctp: 47.02 },
    short_term_momentum: STM_OK,
    data_quality: {
      status: "ok",
      daily_return_check: {
        status: "ok",
        daily_return_pct: 5.4,
        price_start_date: "2026-10-13",
        price_end_date: ASOF,
      },
      nav_discount: { status: "unavailable" },
      warnings: [],
    },
    ...over,
  } as MarketCandidate;
}

function text(cands: MarketCandidate[], k?: MarketContextKodex200, analysis?: ConstituentsAnalysisResponse) {
  return buildMarketDiscoveryCopyText({
    asof: ASOF,
    filters: FILTERS,
    candidates: cands,
    marketContext: ctx(k),
    constituentsAnalysis: analysis ?? null,
  }).split("\n");
}

describe("머리말 — 시장 저장 최신일을 따로", () => {
  it("'○○ 기준 결과'로 후보 끝일을 보증하지 않는다", () => {
    const t = text([cand()]);
    expect(t[0]).toBe("아래는 한국 상장 ETF Market Discovery 결과입니다.");
    expect(t).toContain(
      "- 시장 저장 최신일: 2026-10-14 (저장된 전체 종목 가격 중 가장 늦은 저장일 — 후보별 수익률 계산 기간은 각 값 뒤 괄호)",
    );
    expect(t.join("\n")).not.toContain("기준 한국 상장 ETF");
    expect(t.join("\n")).not.toContain("데이터 기준일");
  });
});

describe("수익률 줄마다 실제 기간", () => {
  it("[후보 ETF] 일간 · 1개월 · 3개월 + [KODEX200 대비 수익률 차이] 1개월", () => {
    const t = text([cand()]);
    expect(t).toContain("   - 일간 수익률: +5.40% (직전 저장일 대비 · 사용 종가 2026-10-13 → 2026-10-14)");
    expect(t).toContain("   - 1개월 수익률: +22.27% (사용 종가 2026-09-14 → 2026-10-14)");
    expect(t).toContain("   - 3개월 수익률: +33.79% (사용 종가 2026-07-16 → 2026-10-14)");
    expect(t.filter((l) => l === "   - 1개월 수익률: +22.27% (사용 종가 2026-09-14 → 2026-10-14)")).toHaveLength(2);
  });

  it("끝일이 다른 후보는 그 끝일 · 날짜 없음은 확인 불가 · 값 없음은 '-' 그대로", () => {
    const stale = cand({
      returns: {
        daily: r(0.08, "2026-10-12", "2026-10-13"),
        one_month: r(17.89, "2026-09-14", "2026-10-13"),
        three_month: r(null),
      },
    });
    const t = text([stale]);
    expect(t).toContain("   - 1개월 수익률: +17.89% (사용 종가 2026-09-14 → 2026-10-13)");
    expect(t).toContain("   - 3개월 수익률: -");
    const unk = text([cand({ returns: { daily: r(5.09), one_month: r(20.3), three_month: r(30.97) } })]);
    expect(unk).toContain("   - 일간 수익률: +5.09% (계산 기간 확인 불가)");
    expect(unk).toContain("   - 3개월 수익률: +30.97% (계산 기간 확인 불가)");
  });
});

describe("KODEX200 대비 — 수익률 차이(%p)와 두 기간", () => {
  it("제목 · 기간 다름 · 같은 기간 · 확인 불가", () => {
    const t = text([cand()]);
    expect(t).toContain("[KODEX200 대비 수익률 차이]");
    expect(t[t.indexOf("[KODEX200 대비 수익률 차이]") + 1]).toBe(
      "- 수익률 차이 = 후보 수익률 − KODEX200 수익률(%p). 괄호의 두 기간이 다르면 같은 기간 초과수익이나 시장 대비 우위를 확인한 값이 아닙니다.",
    );
    expect(t.join("\n")).not.toContain("[시장 대비 후보 강도]");
    expect(t).toContain(
      "   - KODEX200 대비 1개월 수익률 차이: +37.33%p (기간 다름 — 후보 2026-09-14 → 2026-10-14 · KODEX200 2026-09-10 → 2026-10-14)",
    );
    expect(t).toContain(
      "   - KODEX200 대비 3개월 수익률 차이: +47.02%p (기간 다름 — 후보 2026-07-16 → 2026-10-14 · KODEX200 2026-07-14 → 2026-10-14)",
    );
    const same = text([cand()], { ...KODEX, return_1m_start_date: "2026-09-14" });
    expect(same).toContain("   - KODEX200 대비 1개월 수익률 차이: +37.33%p (같은 기간 2026-09-14 → 2026-10-14)");
    const endOnly = text([
      cand({ returns: { ...cand().returns, one_month: r(22.27, "2026-09-10", "2026-10-13") } }),
    ]);
    expect(endOnly).toContain(
      "   - KODEX200 대비 1개월 수익률 차이: +37.33%p (기간 다름 — 후보 2026-09-10 → 2026-10-13 · KODEX200 2026-09-10 → 2026-10-14)",
    );
    const unk = text([cand()], { status: "ok" });
    expect(unk).toContain(
      "   - KODEX200 대비 1개월 수익률 차이: +37.33%p (기간 확인 불가 — 후보 2026-09-14 → 2026-10-14 · KODEX200 확인 불가)",
    );
    const none = text([cand({ excess_return: { vs_kodex200_1m_pctp: null, vs_kodex200_3m_pctp: null } })]);
    expect(none).toContain("   - KODEX200 대비 1개월 수익률 차이: -");
    expect(t.join("\n")).not.toMatch(/초과수익[:,]/);
  });

  it("단기 흐름 5 · 10 · 20거래일 — 후보 기간 + KODEX200 비교 기간", () => {
    const t = text([cand()]);
    expect(t).toContain("   - 5거래일 수익률: +1.04% (사용 종가 2026-10-06 → 2026-10-14)");
    expect(t).toContain("   - 20거래일 수익률: +12.97% (사용 종가 2026-09-10 → 2026-10-14)");
    expect(t).toContain("   - KODEX200 대비 5거래일 수익률 차이: +15.25%p (같은 기간 2026-10-06 → 2026-10-14)");
    expect(t).toContain(
      "   - KODEX200 대비 10거래일 수익률 차이: +30.45%p (기간 다름 — 후보 2026-09-28 → 2026-10-14 · KODEX200 2026-09-27 → 2026-10-14)",
    );
    const old = text([
      cand({ short_term_momentum: { ...STM_OK, kodex200_start_dates: null, kodex200_end_date: null } }),
    ]);
    expect(old).toContain(
      "   - KODEX200 대비 20거래일 수익률 차이: +28.04%p (기간 확인 불가 — 후보 2026-09-10 → 2026-10-14 · KODEX200 확인 불가)",
    );
  });

  it("[요청] 문구도 수익률 차이 — 두 갈래 모두", () => {
    const plain = text([cand()]).join("\n");
    expect(plain).toContain("시스템의 시장 국면 판정, KODEX200 대비 수익률 차이(기간이 다르면 괄호에 두 기간),");
    const analysis = {
      coverage: { requested_count: 0, available_count: 0, unavailable_count: 0 },
      constituents: [],
      overlap_matrix: [],
      repeated_core_holdings: [],
    } as unknown as ConstituentsAnalysisResponse;
    const withC = text([cand()], KODEX, analysis).join("\n");
    expect(withC).toContain("시스템의 시장 국면 판정, KODEX200 대비 수익률 차이(기간이 다르면 괄호에 두 기간),");
    expect(withC).not.toMatch(/초과수익[:,]/);
  });
});

describe("[데이터 품질] 일간 — 같은 계산의 두 행 날짜", () => {
  it("정상 · 경고 · 날짜 없음", () => {
    expect(text([cand()])).toContain("   - 일간 수익률: +5.40% (정상 · 사용 종가 2026-10-13 → 2026-10-14)");
    const warn = cand({
      data_quality: {
        status: "warning",
        daily_return_check: {
          status: "warning",
          daily_return_pct: 12.5,
          flag: "daily_surge_check_needed",
          price_start_date: "2026-10-13",
          price_end_date: ASOF,
        },
        nav_discount: { status: "unavailable" },
        warnings: [],
      },
    } as Partial<MarketCandidate>);
    expect(text([warn])).toContain(
      "   - 일간 수익률: +12.50% — daily_surge_check_needed (사용 종가 2026-10-13 → 2026-10-14)",
    );
    const old = cand({
      data_quality: {
        status: "ok",
        daily_return_check: { status: "ok", daily_return_pct: 5.4 },
        nav_discount: { status: "unavailable" },
        warnings: [],
      },
    } as Partial<MarketCandidate>);
    expect(text([old])).toContain("   - 일간 수익률: +5.40% (정상 · 계산 기간 확인 불가)");
  });
});
