// POC2 PUSH 사용자 표현 정리 + PARAM 적용 UI 연결 STEP (2026-06-20).
//
// 현재 운영 기준 카드 + [현재 기준 OCI 적용] 단일 동작.
//
// 응답은 raw 식별자(param_id / SSH target / remote path / 파일명) 노출 0건
// 으로 제한된 사용자 중심 dict (지시문 §6 데이터 계약).

import { request } from "./core";

export type ThreePushParamStatus =
  | "not_applied"
  | "applying"
  | "applied"
  | "failed"
  | "verification_required";

export interface ThreePushParamState {
  status: ThreePushParamStatus;
  display_label: string;
  applied_at: string | null;
  oci_verified: boolean;
  message: string;
}

export interface ThreePushParamApplyResult {
  status: ThreePushParamStatus;
  display_label: string;
  applied_at: string | null;
  oci_verified: boolean;
  message: string;
}

// apply 동작은 OCI scp + verify subprocess 를 포함하므로 GET timeout(10s) 보다
// 길어질 수 있다 — 120 초까지 허용.
const APPLY_TIMEOUT_MS = 120_000;

export async function fetchThreePushParamState(): Promise<ThreePushParamState> {
  return request<ThreePushParamState>("GET", "/three-push/param/state");
}

export async function applyThreePushParamToOci(): Promise<ThreePushParamApplyResult> {
  return request<ThreePushParamApplyResult>(
    "POST",
    "/three-push/param/apply",
    {},
    APPLY_TIMEOUT_MS
  );
}
