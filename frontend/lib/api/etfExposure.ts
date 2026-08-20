// POC2 ETF Constituents & Overlap 1차 (2026-05-27 / 2026-05-31 갱신).
//
// state/market/market_data.sqlite 의 etf_constituents / refresh_log 테이블 +
// Naver Stock ETFComponent fetcher (2026-05-31 채택, 실패 시 unavailable).
// K6 방어 — 1회 최대 10개 ticker.
//
// 대표 ETF 선정 / 자동 클러스터링 / 중복 후보 접기 / 독립 테마 자동 라벨링 은
// 본 모듈의 책임이 아니다 — 별도 STEP 으로 분리한다.

import { request } from "./core";

// ─── Constituents refresh ────────────────────────────────────────────

export interface RefreshConstituentsRequest {
  asof: string;
  tickers: string[];
  top_k?: number;
  force?: boolean;
}

export interface RefreshConstituentsItem {
  ticker: string;
  status: "ok" | "unavailable" | "skipped_timeout";
  source?: string | null;
  constituent_count: number;
  from_cache: boolean;
  message?: string | null;
}

export interface RefreshConstituentsResponse {
  status: "ok" | "partial" | "rejected";
  reason?: string | null;
  message?: string | null;
  asof?: string | null;
  requested_count: number;
  success_count: number;
  fail_count: number;
  cached_count: number;
  fetched_count: number;
  skipped_count: number;
  source?: string | null;
  items: RefreshConstituentsItem[];
}

export function refreshConstituents(
  req: RefreshConstituentsRequest,
): Promise<RefreshConstituentsResponse> {
  // pykrx 호출은 분당 가량이 걸릴 수 있어 timeout 여유.
  return request<RefreshConstituentsResponse>(
    "POST",
    "/market/constituents/refresh",
    req,
    60000,
  );
}

// ─── Constituents analysis (top holdings + overlap + repeated core) ──

export interface TopHolding {
  rank: number;
  ticker?: string | null;
  name?: string | null;
  weight_pct?: number | null;
  // 2026-05-31 — Naver Stock ETFComponent 통합. 해외형 종목은 ticker=null + 아래
  // 필드 중 1개 이상으로 식별.
  constituent_isin?: string | null;
  constituent_reuters_code?: string | null;
  market_type?: string | null;
}

export interface Concentration {
  top1_weight_pct?: number | null;
  top3_weight_pct?: number | null;
  top5_weight_pct?: number | null;
  top10_weight_pct?: number | null;
}

export interface ConstituentItem {
  etf_ticker: string;
  etf_name?: string | null;
  status: "ok" | "unavailable";
  source?: string | null;
  asof: string;
  top_holdings: TopHolding[];
  concentration: Concentration;
}

export interface OverlapCommonHolding {
  ticker?: string | null;
  name?: string | null;
  left_weight_pct?: number | null;
  right_weight_pct?: number | null;
}

export interface OverlapPair {
  left_ticker: string;
  right_ticker: string;
  common_count_top10: number;
  weighted_overlap_pct?: number | null;
  common_holdings: OverlapCommonHolding[];
}

export interface RepeatedCoreItem {
  etf_ticker: string;
  weight_pct?: number | null;
}

export interface RepeatedCoreHolding {
  ticker?: string | null;
  name?: string | null;
  appears_in_etf_count: number;
  items: RepeatedCoreItem[];
}

// 2026-08-19 설계 확정 — 구성종목 표시 깊이. **수집·조회 모든 경로가 이 값 하나를
// 쓴다.** 이전에는 리터럴 10 이 화면 3곳에 흩어져 있어, 조회 한 곳만 30 으로 고쳤을 때
// 수집 버튼은 계속 10 을 보내 재수집이 일어나지 않았다(검증자 P1).
export const CONSTITUENTS_TOP_K = 30;

export interface ConstituentsAnalysisResponse {
  status: "ok";
  asof: string;
  // 표시 깊이 (구성종목 탭). 2026-08-19 설계 확정으로 최대 30.
  top_k: number;
  // 중복률·반복 등장 계산 기준. **표시 깊이와 무관하게 항상 10.**
  // optional 이 아니다 — 없으면 화면이 임의값으로 메우게 되어 누락을 숨긴다.
  overlap_top_k: number;
  coverage: {
    requested_count: number;
    available_count: number;
    unavailable_count: number;
  };
  constituents: ConstituentItem[];
  overlap_matrix: OverlapPair[];
  repeated_core_holdings: RepeatedCoreHolding[];
}

export function fetchConstituentsAnalysis(
  tickers: string[],
  asof?: string | null,
  top_k: number = CONSTITUENTS_TOP_K,
): Promise<ConstituentsAnalysisResponse> {
  // 2026-06-01 FIX (검증자 A-1 NOTE 반영) — asof 는 optional. 누락 시 백엔드가
  // latest_constituent_asof MAX 를 effective asof 로 사용 (지시문 §8.2 응답
  // 예시 + 직전 FIX 라운드 구현). Naver source 의 referenceDate 가 입력 asof
  // 와 다른 케이스를 자동 정렬 — refresh 직후 analysis 가 0건으로 나오던
  // end-to-end 버그를 해소한다.
  const params = new URLSearchParams({
    tickers: tickers.join(","),
    top_k: String(top_k),
  });
  if (asof) {
    params.set("asof", asof);
  }
  return request<ConstituentsAnalysisResponse>(
    "GET",
    `/market/constituents/analysis?${params.toString()}`,
  );
}
