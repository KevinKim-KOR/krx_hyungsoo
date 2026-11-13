// POC6-29 보완(RESULT 판정 §2-3 · 보완 PLAN 판정 Q-R1) — 빠른 시세: 코스피 · 코스닥 지수 · KODEX 200(네이버).
// [최신 자료 갱신] 묶음 작업의 ⓪ 단계가 받아 PC 서버에 저장한다. 이 조회(GET /market/quick-quotes)는 저장값만 읽는다
// (화면을 열 때 · [요약 다시 읽기] = 외부 조회 없음). 시장 국면 · 순위 · 판단 근거는 이 값을 쓰지 않는다.

import { request } from "./core";

export type QuickCode = "KOSPI" | "KOSDAQ" | "069500";
export type QuickAttemptStatus = "updated" | "unchanged" | "failed";

export interface QuickQuote {
  value: number;
  change: number | null;
  change_pct: number | null;
  // 네이버 원천 표기 시각(마감 뒤 지수는 값이 같아도 시각만 바뀔 수 있음)
  source_time: string;
  trade_date: string;
  // OPEN · CLOSE · 그 밖(원문 그대로) · 응답에 없으면 null
  market_status: string | null;
  // 우리가 조회한 시각
  fetched_at: string;
}

export interface QuickQuoteItem {
  code: QuickCode;
  name: string;
  kind: "index" | "stock";
  // 성공 기록이 없으면 null(시세 미확인) · 실패해도 마지막 성공 값은 남는다 · '변동 없음'이면 이전 성공 값 그대로
  // (원천 시각 · 받은 시각 포함 — 새로 확인한 시각은 last_attempt.at)
  quote: QuickQuote | null;
  last_attempt: { at: string; status: QuickAttemptStatus; reason: string | null } | null;
}

export interface QuickQuotesResponse {
  status: "ok" | "empty" | "invalid";
  message: string | null;
  items: QuickQuoteItem[];
}

export const QUICK_QUOTES_KEY = "market:quick-quotes";

export function fetchQuickQuotes(): Promise<QuickQuotesResponse> {
  return request<QuickQuotesResponse>("GET", "/market/quick-quotes");
}
