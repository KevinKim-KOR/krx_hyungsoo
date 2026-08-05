// POC3-07 (2026-08-05) — OCI 기동 시 상태 스냅샷 조회.
//
// 이 응답은 PC 백엔드가 **기동 시 1회** 읽은 프로세스 로컬 스냅샷이다.
// 화면이 이 GET 을 불러도 OCI 를 다시 조회하지 않는다(백엔드 캐시 반환).
// 자동 polling·수동 새로고침 버튼을 두지 않는다(설계자 Q2·Q12).
//
// 민감정보(토큰·chat id·원격 경로·raw payload)는 응답에 없다.

import { request } from "./core";

export interface OciJobStatus {
  job: string;
  status: string; // SUCCESS / STALE / UNKNOWN
  detail: string;
}

export interface OciStartupStatus {
  checked_at: string | null;
  reachable: boolean;
  overall: string; // OPERATING / UNKNOWN
  summary_line: string;
  crontab_active: boolean | null;
  jobs: OciJobStatus[];
  note: string;
}

export async function fetchOciStartupStatus(): Promise<OciStartupStatus> {
  return request<OciStartupStatus>("GET", "/oci/startup-status");
}
