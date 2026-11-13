// 시험 전용 — 아침 요약 기준(GET /market/morning-basis) · 수급 5거래일(GET /market/short-flows) 응답(POC6-29 보완 2차).
// 값 모양 = 2026-11-12 격리 작업본 실측(기준일 11/11 · 코스피 · 수급 11/9 · KODEX 200 11/11 마감 뒤 저장 · 보유 자료 없음).
import type { MarketContext } from "./api/marketEvidence";
import type { MorningBasisResponse, MorningItem, MorningKey } from "./api/morningBasis";
import type { ShortFlowsResponse } from "./api/shortFlows";

function item(key: MorningKey, label: string, required: boolean, stored: string, over: Partial<MorningItem> = {}): MorningItem {
  return {
    key,
    label,
    required,
    stored_date: stored,
    expected_date: "2026-11-11",
    met: true,
    state: "fresh",
    behind: null,
    source: null,
    received_at: "2026-11-12T15:59:47+09:00",
    reason: null,
    last_attempt: null,
    ...over,
  };
}

export const MORNING_CTX = {
  status: "ok",
  asof: "2026-11-11",
  primary_benchmark: "KODEX200",
  regime_label: "하락장",
  regime_code: "bear",
  regime_score: -4,
  regime_reasons: ["KODEX200 20거래일 수익률 -10.70%"],
  kodex200: {
    status: "ok",
    close: 84540,
    return_20d_pct: -10.7,
    return_60d_pct: -20.1,
    ma20: 87500,
    ma60: 100500,
    ma20_position: "below",
    ma60_position: "below",
  },
  kospi: { status: "unavailable" },
  regime_streak: { regime_code: "bear", streak_days: 24, at_least: false },
  warnings: [],
} as unknown as MarketContext;

// 기본 = 필수 3 모두 충족(준비됨)
export function morningOk(over: Partial<MorningBasisResponse> = {}): MorningBasisResponse {
  return {
    status: "ok",
    message: null,
    today: "2026-11-12",
    expected_date: "2026-11-11",
    ready: true,
    missing: [],
    items: [
      item("kospi", "코스피 공식 종가", true, "2026-11-11"),
      item("kodex200", "KODEX 200 판정 근거", true, "2026-11-12", {
        basis_row: { date: "2026-11-11", close: 84540, state: "after_close" },
      }),
      item("flows", "투자자 수급", true, "2026-11-11"),
      item("vix", "VIX", false, "2026-11-11"),
      item("usdkrw", "원/달러", false, "2026-11-11"),
      item("wti", "WTI", false, "2026-11-11", { state: "observed", expected_date: null }),
    ],
    morning_regime: { status: "ok", basis_date: "2026-11-11", reason: null, context: MORNING_CTX },
    full_refresh: { cooldown_remaining_seconds: 0, next_available_at: null },
    // 설계자 V3 D1 — 기존 판정 상수(서버 SCORE_RULE 와 같은 값)
    score_rule: { return_20d_pct: 2, return_60d_pct: 5, bull_min: 2, bear_max: -2 },
    ...over,
  };
}

// 11/12 격리 작업본 사례 — 코스피 공식 종가 · 수급 11/9까지(설정 실패 사유)
export function morningMissing(): MorningBasisResponse {
  const ok = morningOk();
  return {
    ...ok,
    ready: false,
    missing: ["kospi", "flows"],
    items: ok.items.map((i) =>
      i.key === "kospi" || i.key === "flows"
        ? {
            ...i,
            stored_date: "2026-11-09",
            met: false,
            state: "late",
            behind: 2,
            reason: i.key === "kospi" ? "설정 확인 필요(KRX 키 없음) · 15:59 확인" : "가져오기 실패(가져오기 실행 실패) · 15:59 확인",
          }
        : i,
    ),
  };
}

export function shortOk(): ShortFlowsResponse {
  return {
    status: "ok",
    message: null,
    end_date: "2026-11-11",
    investors: [
      {
        key: "foreign",
        label: "외국인",
        last: { date: "2026-11-11", value: -525000000000 },
        recent5: { sum: -1058970000000, from: "2026-11-05", to: "2026-11-11" },
        previous5: { sum: 4400000000, from: "2026-10-29", to: "2026-11-04" },
        trend: "순매수 → 순매도 전환",
        note: null,
      },
      {
        key: "institution",
        label: "기관계",
        last: { date: "2026-11-11", value: 726500000000 },
        recent5: { sum: 400120000000, from: "2026-11-05", to: "2026-11-11" },
        previous5: null,
        trend: null,
        note: null,
      },
      { key: "individual", label: "개인", last: null, recent5: null, previous5: null, trend: null, note: "5거래일 자료 부족" },
    ],
  };
}
