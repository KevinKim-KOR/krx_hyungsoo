// POC6-32 V2(PLAN §3-2 D2 · D3 · §9 I-6 · I-19 · I-21) — GET /market/etf-official?tickers=A,B — 공식 기준정보
// (KRX ETF 기본정보 CSV · 서버 `app/etf_official_info`)와 두 상품의 지수 상태(읽기 전용 · 외부 호출 0).
// 값은 CSV 글자 그대로 온다(예: 총보수 '0.450000'). 지수 상태 판정(같은 공식 기초지수 · 같은 계열 · 다른 지수 · 기준
// 미확인)과 구조 차이는 서버가 정한다 — 화면은 다시 판정하지 않는다. 서버는 코드가 중복을 뺀 뒤 정확히 2개일 때만
// `pair` 를 붙인다(앞 코드 = a · 뒤 코드 = b). 「보유와 후보 비교」는 [보유, 후보] 순서로 묻는다.

import { request } from "./core";

export type OfficialKind = "etf" | "stock" | "unknown";

export interface OfficialItem {
  ticker: string;
  found: boolean;
  kind: OfficialKind;
  name: string | null;
  index_name: string | null;
  index_provider: string | null;
  market: string | null;
  asset: string | null;
  multiple: string | null;
  replication: string | null;
  fee_pct: string | null;
  tax: string | null;
  listed: string | null;
  // 공식 기준정보에 없을 때의 사유(서버 글) · 있으면 null.
  missing_reason: string | null;
}

export interface OfficialCsv {
  name: string | null;
  asof: string | null;
  ok: boolean;
  error: string | null;
}

export type OfficialPairState = "same" | "same_family" | "different" | "unconfirmed";

export interface OfficialStructureDiff {
  field: string; // 화면 이름 = CSV 열 이름(추적배수 · 복제방법 · 총보수 · 과세유형)
  a: string | null;
  b: string | null;
}

// 값이 비어 있는 구조 칸(r1 F2) — 차이가 아니라 확인 안 된 칸. side = 빈 쪽(a = 앞 코드 · b = 뒤 코드 · both = 두 쪽).
export interface OfficialStructureUnconfirmed {
  field: string;
  side: "a" | "b" | "both";
}

export interface OfficialPair {
  state: OfficialPairState;
  label: string;
  reason: string;
  // 두 값이 모두 확인됐고(빈 값 아님) 서로 다른 칸만(r1 F2).
  structure_diffs: OfficialStructureDiff[];
  // 이 칸이 없는 응답(옛 서버) = 빈 목록으로 본다.
  structure_unconfirmed?: OfficialStructureUnconfirmed[];
}

export interface EtfOfficialResponse {
  csv: OfficialCsv;
  items: Record<string, OfficialItem>;
  pair?: OfficialPair;
}

export const ETF_OFFICIAL_KEY_PREFIX = "etf-official?";
export const ETF_OFFICIAL_MAX = 10; // 서버 상한(api_market_evidence.MAX_TICKERS)과 같음

// 순서를 지키고 중복을 뺀다(앞 코드 = 서버 pair 의 a).
function uniq(tickers: readonly string[]): string[] {
  return [...new Set(tickers.filter((t) => !!t))].slice(0, ETF_OFFICIAL_MAX);
}

export function etfOfficialKey(tickers: readonly string[]): string {
  return `${ETF_OFFICIAL_KEY_PREFIX}tickers=${uniq(tickers).join(",")}`;
}

export function fetchEtfOfficial(tickers: readonly string[]): Promise<EtfOfficialResponse> {
  const params = new URLSearchParams({ tickers: uniq(tickers).join(",") });
  return request<EtfOfficialResponse>("GET", `/market/etf-official?${params.toString()}`);
}
