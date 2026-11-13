// POC6-29(PLAN §3-6 · 판정 Q7 기본안) — [최신 자료 갱신] 한 번: PC 서버 묶음 작업(보유 현재가 → 시장 자료 시작).
// POST /refresh/all = 시작(이미 도는 중이면 그 작업 상태) · GET /refresh/all/status = 단계별 상태.
// 시장 자료는 기존 시장 갱신(백그라운드 · 한 번에 하나 · 6시간 간격)을 시작만 하고, 진행은 기존 상태 확인으로 따라간다.
// POC6-29 보완(보완 PLAN 판정 Q-R1 · Q-R2) — 맨 앞에 ⓪ 빠른 시세(코스피 · 코스닥 · KODEX 200)를 받는다(6시간 대기와 무관).

import { request } from "./core";
import type { MarketRefreshStartStatus } from "./market";
import type { QuickAttemptStatus, QuickCode } from "./quickQuotes";

export interface RefreshAllQuickStep {
  status: "pending" | "running" | "done" | "partial" | "failed";
  fetched_at?: string | null;
  items?: Partial<Record<QuickCode, { status: QuickAttemptStatus; reason?: string | null }>>;
  message?: string | null;
}

export interface RefreshAllHoldingsStep {
  status: "pending" | "running" | "done" | "failed" | "skipped";
  ok_count?: number | null;
  fail_count?: number | null;
  price_asof_max?: string | null;
  // null | holdings_empty | holdings_invalid | all_failed | error
  reason?: string | null;
  message?: string | null;
}

export interface RefreshAllMarketStep {
  status: "pending" | MarketRefreshStartStatus;
  refresh_id?: string | null;
  message?: string | null;
  cooldown_remaining_seconds?: number | null;
  next_available_at?: string | null;
}

// POC6-29 보완 2차(PLAN §10-4 · S 판정 Q-S2) — ③ 전일 자료 보충(② 가 6시간 대기일 때만 · 모자란 것만 · 기존 경로).
export type PrevdayItemStatus = "already" | "fetched" | "applied" | "unchanged" | "failed" | "skipped" | "pending";

export interface PrevdayItem {
  label: string;
  status: PrevdayItemStatus;
  before: string | null;
  after: string | null;
  reason: string | null;
  via?: "local" | "pull" | null; // 수급만 — PC 보관본 · 가져오기
}

export interface RefreshAllPrevdayStep {
  status: "pending" | "running" | "done" | "skipped" | "failed";
  reason?: string | null;
  id?: string | null;
  expected_date?: string | null;
  items?: Partial<Record<"kospi" | "flows" | "vix" | "usdkrw" | "wti", PrevdayItem>>;
}

export interface RefreshAllStatus {
  state: "idle" | "running" | "done";
  job_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  // quick 이 없는 응답(보완 전 서버)도 읽는다.
  // prevday 가 없는 응답(보완 2차 전 서버)도 읽는다.
  steps: {
    quick?: RefreshAllQuickStep | null;
    holdings: RefreshAllHoldingsStep | null;
    market: RefreshAllMarketStep | null;
    prevday?: RefreshAllPrevdayStep | null;
  };
}

export function postRefreshAll(): Promise<RefreshAllStatus> {
  return request<RefreshAllStatus>("POST", "/refresh/all", undefined, 90000);
}

export function fetchRefreshAllStatus(): Promise<RefreshAllStatus> {
  return request<RefreshAllStatus>("GET", "/refresh/all/status");
}
