// POC2 PUSH 사용자 표현 정리 + PARAM 적용 UI 연결 STEP (2026-06-20).
//
// 현재 운영 기준 카드 + 단일 동작. POC5-27 부터 [현재 기준 OCI 적용] = OCI DB 활성값을 먼저 읽고
// 같으면 바꾸지 않고, 다르면 OCI 로컬 도구가 PC 값을 그대로 발행 · 활성화한 뒤 다시 읽어 확인한다.
//
// 응답은 raw 식별자(param_id / SSH target / remote path / 파일명) 노출 0건
// 으로 제한된 사용자 중심 dict (지시문 §6 데이터 계약).

import { request } from "./core";

export type ThreePushParamStatus =
  | "not_applied"
  | "applying" // 화면 전용(요청 중)
  | "delivered_only" // 예전 '전달' 기록만 있음 — 활성화 확인 없음(POC5-27 판정 §5)
  | "active_same" // OCI 활성값이 이미 같음 · 바꾼 것 없음
  | "activated" // 바꾸고 다시 읽어 확인
  | "failed" // 적용 못 함 · 기존 OCI 활성값 그대로
  | "unconfirmed" // 결과 확인 불가 — 단정하지 않음
  | "busy" // 다른 적용이 진행 중
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
  // POC3-07 (Q4): 표시용 전송 payload SHA-256(성공 판정 아님 · 성공은 OCI 다시 읽기).
  content_sha256?: string | null;
  // POC5-27 — 이 요청에서 OCI 활성값을 실제로 읽었을 때만(비교 수 · 다른 수 · 읽은 시각 KST).
  compared?: number | null;
  differing?: number | null;
  checked_at?: string | null;
}

// apply 는 OCI 읽기 · 전달 · 적용 · 다시 읽기를 포함하므로 GET timeout(10s) 보다 길다 —
// 120 초까지 허용(서버 전체 예산 105초 · POC5-27).
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
