// POC6-31 — ETF 구성종목 수집 상태(보유 · 후보) · 후보 수집 작업.
// - GET  /market/constituents/holdings-status : 보유 ETF 별 구성 상태(저장 자료만 · 읽기만으로 수집이 시작되지 않음).
// - POST /market/constituents/collect         : 후보 목록 수집 작업 시작(서버 작업 · 이미 돌면 그 작업).
// - GET  /market/constituents/collect/status  : 후보 수집 작업 상태(읽기만). 목록(tickers)을 주면 같은 목록의 작업이
//   없을 때 저장 기록으로 ETF별 상태를 돌려준다(stored · 서버를 다시 켜도 같은 상태) · 다른 목록 작업은 other_job.
// 결과 코드와 화면 이름은 서버(app/etf_constituents_status.py)가 정한다 — 화면은 받은 label · reason 을 그대로 쓴다.

import { request } from "./core";

export type ConstituentResult =
  | "existing"
  | "fetched"
  | "target_wait"
  | "failed"
  | "timeout"
  | "locked"
  | "no_source_date"
  | "not_checked";

// '갱신 실패'로 묶는 결과(판정 §4 M1)
export const UPDATE_FAILED_RESULTS: ConstituentResult[] = ["failed", "timeout", "locked", "no_source_date"];

export interface ConstituentItem {
  ticker: string;
  name?: string | null;
  result: ConstituentResult;
  label: string;
  reason: string;
  source_asof: string | null; // 원천일이 확인된 실제 구성일
  rows?: number | null;
  kept_asof: string | null; // 실패 · 미확인 때 마지막 보존 자료 날짜
  kept_confirmed: boolean;
  checked_at?: string | null; // 이번 작업의 확인 시각(UTC)
  last_checked_at?: string | null; // 저장 기록의 마지막 확인 시각(UTC)
  needs_check?: boolean;
  shared?: boolean; // 다른 작업이 부른 결과를 함께 받음(이 작업의 실제 호출에는 없음)
  detail?: string | null; // 개발 식별 문구(화면 '자세히' 안)
}

export type ConstituentCounts = Partial<Record<ConstituentResult, number>>;

export interface HoldingsConstituentsStatus {
  // read_failed = 저장소 잠김으로 상태를 읽지 못함('할 일 없음'과 다름)
  status: "ok" | "skipped" | "read_failed";
  reason: string | null;
  target_date: string | null;
  running: boolean;
  total: number;
  needs_check: number;
  counts: ConstituentCounts;
  items: ConstituentItem[];
}

export const HOLDINGS_CONSTITUENTS_KEY = "holdings-constituents-status";

export function fetchHoldingsConstituentsStatus(): Promise<HoldingsConstituentsStatus> {
  return request<HoldingsConstituentsStatus>("GET", "/market/constituents/holdings-status");
}

export interface ConstituentsCollectJob {
  state: "idle" | "running" | "done";
  job_id: string | null;
  kind?: "candidates" | "holdings";
  reason?: string | null;
  reason_detail?: string | null; // 예외 이름 등(화면 '자세히' 안)
  target_date?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  tickers?: string[]; // 작업 대상(시작 때 확정)
  other_list?: boolean; // 돌려받은 작업의 대상이 요청 목록과 다름(POST)
  stored?: boolean; // 저장 기록으로 만든 상태(메모리 작업 아님)
  stored_status?: "ok" | "read_failed";
  needs_check?: number;
  other_job?: { total: number; done: number; started_at: string | null } | null;
  total?: number;
  done?: number;
  batch_index?: number;
  batch_total?: number;
  calls?: number;
  counts?: ConstituentCounts;
  update_failed?: number;
  shared?: number; // 다른 작업과 함께 받은 수
  unlogged_logs?: number; // 저장소 잠김으로 끝내 못 쓴 확인 기록 수
  items: ConstituentItem[];
}

export function postConstituentsCollect(tickers: string[]): Promise<ConstituentsCollectJob> {
  return request<ConstituentsCollectJob>("POST", "/market/constituents/collect", { tickers });
}

export function fetchConstituentsCollectStatus(tickers?: string[]): Promise<ConstituentsCollectJob> {
  const q = tickers && tickers.length ? `?tickers=${encodeURIComponent(tickers.join(","))}` : "";
  return request<ConstituentsCollectJob>("GET", `/market/constituents/collect/status${q}`);
}

// POC6-31 STEP 3(판정 §2 첫째 · Q9 · Q21) — 여러 지수 계열이 함께 담은 주식(읽기 전용 · 외부 호출 0).
export interface CrossFamilyEntry {
  etf: string;
  etf_name: string | null;
  selection_rank: number | null;
  family: string | null;
  index_name: string | null;
  strategy: boolean;
  rank: number;
  weight_pct: number | null;
  asof: string;
}

export interface CrossFamilyStock {
  key: string;
  name: string;
  families: string[];
  family_count: number;
  etf_count: number;
  strategy_count: number;
  max_weight_pct: number;
  max_entry: { etf: string; etf_name: string | null; rank: number };
  entries: CrossFamilyEntry[];
}

export type CrossFamilyStatus = "ok" | "not_comparable" | "no_data";

export interface CrossFamilyGroup {
  status: CrossFamilyStatus;
  etf_count: number;
  etf_with_stock_rows: number;
  family_count: number;
  unconfirmed_family_etfs: number;
  unknown_rows: number;
  evidence_count: number;
  stocks: CrossFamilyStock[];
}

export interface CrossFamilyResponse {
  status: CrossFamilyStatus;
  scope: {
    requested: number;
    with_data: number;
    no_confirmed_data: number;
    latest_date: string | null;
    same_date: number;
    etf_with_stock_rows?: number;
    family_count?: number;
    unconfirmed_family_etfs?: number;
    unknown_rows?: number;
    evidence_count?: number;
  };
  stocks: CrossFamilyStock[];
  reference: (CrossFamilyGroup & { date: string })[];
  official_csv?: string | null;
}

export function fetchConstituentsCrossFamily(tickers: string[]): Promise<CrossFamilyResponse> {
  return request<CrossFamilyResponse>(
    "GET",
    `/market/constituents/cross-family?tickers=${encodeURIComponent(tickers.join(","))}`,
  );
}
