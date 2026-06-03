// POC2 Step 6 + Fix 라운드: universe momentum refresh.
//
// 정책 (Fix 라운드 2026-05-11): 신규 endpoint 추가 금지 — GET /universe/momentum/latest
// 미도입. UI 의 마지막 갱신 표시는 POST refresh 응답을 frontend state 로 보관해서 처리
// (페이지 reload 시 안내 문구로 비워짐). POST 응답에 top_candidate / summary_reason_text
// 가 함께 포함되어 status panel 을 그릴 수 있다.
//
// SQLite 기반 Market Discovery (market.ts) 와 별도 흐름이다 — universe_mode 가
// 산출하는 모멘텀 결과 + 급락 ETF 신호 (PUSH 3) 를 그대로 표현한다.

import { request } from "./core";

export interface UniversePriceHistoryBasis {
  base_date: string;
  base_close: number;
  latest_date: string;
  latest_close: number;
}

export interface UniverseTopCandidate {
  candidate_id?: string;
  ticker: string;
  name: string;
  rank?: number;
  score_result?: {
    is_scored: boolean;
    score_value?: number;
    score_unit?: string;
    score_basis_text?: string;
    ranking_basis?: string;
    exclusion_reason?: string;
  };
  reason_text?: string;
  price_history_basis?: UniversePriceHistoryBasis;
}

export interface UniverseRefreshSummary {
  total_candidates: number;
  scored_candidates: number;
  excluded_candidates: number;
  source_freshness: string;
  refresh_status: "ok" | "partial" | "failed";
  // Step6 Fix: UI 가 GET /latest 없이 POST 응답만으로 status panel 을 그리도록 확장.
  summary_reason_text?: string | null;
  top_candidate?: UniverseTopCandidate | null;
  // Step7A: seed source — "starter_seed" 면 UI 가 "기본 후보군 사용" 안내 표시.
  source?: string | null;
  // Step7C: 급락 ETF 주의 신호 (PUSH 3) — universe_mode 가 계산한 결과.
  // falling_candidate 가 null 이면 신호 없음.
  falling_candidate?: UniverseTopCandidate | null;
  falling_threshold_pct?: number | null;
}

export interface UniverseRefreshResponse {
  status: "ok" | "partial" | "failed";
  artifact_path: string;
  momentum_result: {
    mode: string;
    asof: string;
    summary: UniverseRefreshSummary;
  };
}

// 명시적 사용자 액션에서만 호출 — Telegram / Approve / GenerateDraft 자동 발동 금지.
export function refreshUniverseMomentum(): Promise<UniverseRefreshResponse> {
  // pykrx ticker 별 0.5s delay × 최대 20개 + 30s budget — 60s timeout 으로 여유.
  return request<UniverseRefreshResponse>(
    "POST",
    "/universe/momentum/refresh",
    undefined,
    60000,
  );
}
