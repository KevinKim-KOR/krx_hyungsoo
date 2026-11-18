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
  // POC6-31 — 이 ETF 구성일이 원천이 준 날짜로 확인됐나(없는 응답 = 예전 서버)
  asof_confirmed?: boolean | null;
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
  // POC6-31(판정 Q7) — 양쪽 구성일 · 같은 날짜 쌍인가(없는 응답 = 예전 서버 · 같은 날짜로 본다)
  left_asof?: string | null;
  right_asof?: string | null;
  same_date?: boolean | null;
  // POC6-31 — 쌍 범위(서버가 정함): 같은 구성일(양쪽 원천일 확인) · 원천 기준일 미확인 · 구성일 다름 · 한쪽 자료 없음.
  // 칸 없는 응답 = 예전 서버(한 날짜로 읽음).
  pair_scope?: "same_date" | "unconfirmed" | "different_date" | "no_data" | null;
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

// ─── 한 ETF 구성 요약(POC6-32 V2 · PLAN S6 · 읽기 전용 · 수집하지 않음) ──
// 서버(app/api_weekly_review.py `GET /market/constituents/summary`)가 원천일이 확인된 최신 구성을, 없으면 저장 최신 구성을
// 돌려준다. 상태 = 미수집 · 원천 기준일 미확인 · 상위 N행만 확인 · 전체 확인 + 읽기 실패(error · '미수집'과 다름).
export type ConstituentSummaryState = "not_collected" | "source_unconfirmed" | "top_rows" | "full" | "error";

export interface ConstituentSummaryRow {
  rank: number;
  name: string | null;
  weight_pct: number | null;
  // null = ETF 목록을 읽지 못해 주식 여부를 가를 수 없음
  is_stock: boolean | null;
  kind_label: string | null;
}

// status = missing(시장 자료 파일 없음)이면 아래 구성 칸이 없다.
export interface ConstituentsSummaryResponse {
  status: "ok" | "missing" | "error";
  message: string | null;
  ticker: string;
  name: string | null;
  state?: ConstituentSummaryState;
  state_label?: string;
  asof?: string | null;
  stored_rows?: number;
  stocks_known?: boolean;
  stock_rows?: number | null;
  other_rows?: { label: string; count: number }[];
  top_n?: number | null;
  top_stocks?: { name: string | null; weight_pct: number | null }[];
  top3_sum_pct?: number | null;
  rows?: ConstituentSummaryRow[];
  // 기존 집중 정의(저장 행 비중 상위 1 · 3 · 5 · 10 합 · 주식 아닌 행 포함)
  concentration?: Concentration;
  line?: string;
}

export function fetchConstituentsSummary(ticker: string): Promise<ConstituentsSummaryResponse> {
  const params = new URLSearchParams({ ticker });
  return request<ConstituentsSummaryResponse>("GET", `/market/constituents/summary?${params.toString()}`);
}
