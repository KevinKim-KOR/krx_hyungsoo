// POC3-07 (2026-08-05) — Holdings OCI 명시적 적용.
//
// 저장(PUT /holdings)과 별개 동작. 사용자가 명시적으로 [OCI 적용] 을 눌렀을 때만
// 호출한다. 응답은 이번 적용 동작의 결과만 담는다(일반 OCI 상태 재조회 아님).
//
// 응답에 SSH target·remote path·raw·secret 은 없다(백엔드 §6·§13).

import { request } from "./core";

export type HoldingsApplyStatus =
  | "PC_SAVED"
  | "OCI_APPLIED"
  | "OUT_OF_SYNC"
  | "APPLY_FAILED"
  | "UNKNOWN";

export interface HoldingsApplyResult {
  status: HoldingsApplyStatus;
  applied_at: string | null;
  content_sha256: string | null;
  oci_verified: boolean;
  message: string;
}

// scp + ssh verify 를 포함하므로 기본 timeout(10s)보다 길게 허용.
const APPLY_TIMEOUT_MS = 120_000;

export async function applyHoldingsToOci(): Promise<HoldingsApplyResult> {
  return request<HoldingsApplyResult>(
    "POST",
    "/holdings/apply",
    {},
    APPLY_TIMEOUT_MS
  );
}

// POC3-08: 마지막 OCI 적용 상태(지속 기록). 화면 재진입해도 남는다.
//   GET 은 PC 로컬 status 파일만 읽고 재적용하지 않는다.
export interface HoldingsApplyStatusRecord {
  has_record: boolean;
  status: HoldingsApplyStatus | null;
  applied_at: string | null;
  oci_verified: boolean | null;
  message: string | null;
}

export async function fetchHoldingsApplyStatus(): Promise<HoldingsApplyStatusRecord> {
  return request<HoldingsApplyStatusRecord>("GET", "/holdings/apply/status");
}
