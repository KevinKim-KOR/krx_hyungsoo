// POC6-31 STEP 4(PLAN C21 · C22 · C24 · 판정 §2 둘째 · 셋째 · Q11 · Q12 · Q19) — 보유와 후보의 구성종목 비교.
// GET /market/constituents/pair-exposure(읽기 전용 · 외부 호출 0 · 금액 없음 · %만). 계산 수치는 서버가 만든
// 글(계산에 쓴 자릿수 그대로)이다 — 화면은 다시 계산하지 않고, 표시할 때만 소수 둘째 자리로 반올림한다.

import { request } from "./core";

export type PairState =
  | "found"
  | "weight_unknown"
  | "zero"
  | "out_of_range"
  | "self"
  | "not_applicable"
  | "unconfirmed"
  | "no_data";

export interface PairCell {
  state: PairState;
  weight?: string;
  asof?: string;
  stored_rows?: number;
  stored_sum?: string;
}

export interface ExposureTerm {
  ticker: string;
  name: string | null;
  holding_weight: string;
  constituent_weight: string;
  product: string;
}

// 다른 구성일 참고 — 비중을 읽을 수 없으면 null(0 으로 채우지 않음 · 검증자 STEP 4~5 r1 F10)
export interface ReferenceTerm {
  ticker: string;
  name: string | null;
  asof: string;
  holding_weight: string;
  constituent_weight: string | null;
  product: string | null;
}

export interface PairStock {
  key: string;
  name: string;
  rank: number;
  candidate_weight: string | null;
  pair: PairCell | null;
  // 보유를 못 읽거나 분모가 없으면 null(짝 칸만 보임 · '내 보유 전체 비중 확인 불가')
  exposure: {
    terms: ExposureTerm[];
    direct: { ticker: string; name: string | null; weight: string }[];
    zero_confirmed: string[];
    unknown: { ticker: string; name: string | null; holding_weight: string; range: string; stored_rows: number }[];
    unknown_weight: string;
    // 확인한 부분(편입 비중을 읽은 ETF · 없음이 확인된 ETF · 직접 보유)이 없으면 null = '확인 불가'(F10)
    raw: string | null;
    value: string | null;
  } | null;
  reference: ReferenceTerm[];
}

export interface PairScopePart {
  count: number;
  weight: string;
}

export interface PairScopeEtf {
  ticker: string;
  name: string | null;
  weight: string | null;
  use: "sum" | "other_date" | "unconfirmed" | "no_data" | "no_weight";
  state: "confirmed" | "unconfirmed" | "no_data";
  asof: string | null;
  stored_rows: number;
  range: "full" | "depth" | "legacy" | "unverified" | null;
}

export interface PairExposure {
  status: "ok" | "holdings_unreadable" | "no_holdings" | "no_weight_basis" | "no_candidate_data" | "no_etf_list";
  condition: Record<string, unknown>;
  candidate: {
    ticker: string;
    name: string | null;
    state: "confirmed" | "unconfirmed" | "no_data";
    asof: string | null;
    stored_rows: number;
    held: boolean;
    held_weight: string | null;
    held_use: string | null;
  };
  holding: {
    ticker: string;
    name: string | null;
    kind: "etf" | "stock";
    held: boolean;
    weight: string | null;
    state: "confirmed" | "unconfirmed" | "no_data" | null;
    asof: string | null;
    stored_rows: number | null;
    range: string | null;
  } | null;
  dates: { candidate: string | null; holding: string | null; exposure: string | null };
  basis: {
    rows: number;
    priced_rows: number;
    partial: boolean;
    price_date: { state: string; min: string | null; max: string | null } | null;
  } | null;
  scope: {
    holdings: number;
    included: PairScopePart;
    direct: PairScopePart;
    other_date: PairScopePart & { dates: string[] };
    unconfirmed: PairScopePart;
    no_data: PairScopePart;
    no_weight: { count: number };
    ranges: {
      depth: number;
      legacy: number;
      unverified: number;
      full: number;
      full_min: number | null;
      full_max: number | null;
    };
    etfs: PairScopeEtf[];
  } | null;
  stocks: PairStock[];
  candidate_top_rows: number;
  candidate_non_stock_rows: number;
  fingerprint: string;
  // 서버가 만든 기준일 줄(미리보기 원문과 같은 글) · 후보와 고른 보유 구성일이 다름(짝 비중 = 참고) — 지문 밖(r1 B-6 · F12)
  date_line: string;
  pair_dates_differ: boolean;
  // 주식(key)별 합계에서 빠진 ETF 사유 글 — 서버 글(미리보기 원문과 같음 · 없으면 null · 검증자 STEP 4~5 r2 F14)
  stock_notes: Record<string, string | null>;
}

export interface PairQuery {
  candidate: string;
  holding: string | null;
  screen: string;
  basis: string;
  side: "top" | "bottom";
  rank: number;
  start_date: string | null;
  end_date: string | null;
  filters: Record<string, boolean>;
}

export function pairExposureUrl(q: PairQuery): string {
  const p = new URLSearchParams();
  p.set("candidate", q.candidate);
  if (q.holding) p.set("holding", q.holding);
  p.set("screen", q.screen);
  p.set("basis", q.basis);
  p.set("side", q.side);
  p.set("rank", String(q.rank));
  if (q.start_date) p.set("start_date", q.start_date);
  if (q.end_date) p.set("end_date", q.end_date);
  for (const [k, v] of Object.entries(q.filters)) p.set(k, String(v));
  return `/market/constituents/pair-exposure?${p.toString()}`;
}

export function fetchPairExposure(q: PairQuery): Promise<PairExposure> {
  return request<PairExposure>("GET", pairExposureUrl(q));
}
