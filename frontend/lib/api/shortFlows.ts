// POC6-29 보완 2차(S 판정 §1) — 투자자 수급 5거래일 합(`GET /market/short-flows` · 저장 일별 원자료만).
import { request } from "./core";

export interface ShortFlowSum {
  sum: number; // 원
  from: string;
  to: string;
}

export interface ShortFlowInvestor {
  key: "foreign" | "institution" | "individual";
  label: string;
  last: { date: string; value: number } | null; // 끝일 그 주체 순매수(원)
  recent5: ShortFlowSum | null; // 하루라도 빠지면 null
  previous5: ShortFlowSum | null;
  trend: string | null; // 직전 5거래일 대비 문장(둘 다 있을 때만)
  note: string | null; // '5거래일 자료 부족'
}

export interface ShortFlowsResponse {
  status: "ok" | "empty" | "invalid";
  message: string | null;
  end_date: string | null;
  investors: ShortFlowInvestor[];
}

export const SHORT_FLOWS_KEY = "market:short-flows";

export function fetchShortFlows(): Promise<ShortFlowsResponse> {
  return request<ShortFlowsResponse>("GET", "/market/short-flows");
}
