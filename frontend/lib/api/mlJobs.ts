// POC2 UI 안전실행 (2026-06-11) — ML evidence refresh job API client.
//
// 본 클라이언트는 backend 의 read-only status 조회와 background job 시작
// endpoint 를 호출하기만 한다. baseline 재계산 / feature 생성 / 외부 source
// 호출 / ML 학습 / 매수·매도 판단 0건.

import { request } from "./core";

export type MlJobStepStatus =
  | "queued"
  | "running"
  | "success"
  | "failed"
  | "skipped"
  | string;

export type MlJobStatus =
  | "queued"
  | "running"
  | "success"
  | "failed"
  | string;

export interface MlJobStepState {
  status: MlJobStepStatus;
  started_at: string | null;
  finished_at: string | null;
  message: string;
  artifact_path: string;
}

export interface MlJobSteps {
  feature_generation: MlJobStepState;
  sanity_check: MlJobStepState;
  baseline_lookback: MlJobStepState;
}

export interface MlJobLastSuccessSummary {
  feature_asof_end?: string | null;
  evaluated_days?: number | null;
  baseline_report_status?: string | null;
  [key: string]: unknown;
}

export interface MlJobState {
  job_id: string;
  status: MlJobStatus;
  started_at: string | null;
  finished_at: string | null;
  requested_by: string;
  pid: number;
  last_heartbeat_at: string | null;
  steps: MlJobSteps;
  last_success_summary: MlJobLastSuccessSummary | null;
  message: string;
  error: string | null;
}

export interface MlJobLatestResponse {
  // FIX r2 — 손상 케이스 명시 (B-1). "error" 는 ml_job_status_latest.json 파일이
  // 손상되어 의미를 해석할 수 없음. 사용자에게 명시 안내 + 새 실행 차단.
  status: "ok" | "empty" | "error";
  job_status_path: string;
  job: MlJobState | null;
  message: string | null;
}

export interface MlJobStartResponse {
  // "error" 는 status 파일 손상으로 새 job 자동 생성 거부 (FIX r2).
  status: "accepted" | "already_running" | "error";
  job_status_path: string;
  job: MlJobState | null;
  message: string | null;
}

export function fetchMlJobsLatest(): Promise<MlJobLatestResponse> {
  return request<MlJobLatestResponse>("GET", "/ml/jobs/latest");
}

export function startMlEvidenceRefresh(): Promise<MlJobStartResponse> {
  return request<MlJobStartResponse>("POST", "/ml/jobs/evidence-refresh");
}
