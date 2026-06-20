// POC2 ML 축1 — 상대상승 참고점수 실행 UI 연결 (2026-06-21).
//
// POST /market/relative-upside/run — 동기 처리 (backend 는 같은 프로세스 내
// scripts.run_ml_relative_upside_score_v0.main() 직접 import 호출 — subprocess
// 가 아님). torch GPU 학습 + 추론을 포함하므로 timeout 을 길게 (120s). 응답에
// raw 식별자 / device name / loss / epoch / artifact path 노출 0건.

import { request } from "./core";

export type RelativeUpsideRunStatus = "ok" | "failed" | "unavailable";

export interface RelativeUpsideRunResult {
  status: RelativeUpsideRunStatus;
  asof_date: string | null;
  generated_at: string | null;
  scored_candidate_count: number | null;
  gpu_execution_used: boolean | null;
  message: string;
}

const RUN_TIMEOUT_MS = 120_000;

export async function runRelativeUpsideScore(): Promise<RelativeUpsideRunResult> {
  return request<RelativeUpsideRunResult>(
    "POST",
    "/market/relative-upside/run",
    {},
    RUN_TIMEOUT_MS,
  );
}
