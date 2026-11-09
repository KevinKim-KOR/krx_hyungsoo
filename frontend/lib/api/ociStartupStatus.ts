// POC3-07 (2026-08-05) — OCI 기동 시 상태 스냅샷 조회.
//
// 이 응답은 PC 백엔드가 **기동 시 1회** 읽은 프로세스 로컬 스냅샷이다.
// 화면이 이 GET 을 불러도 OCI 를 다시 조회하지 않는다(백엔드 캐시 반환).
// 자동 polling·수동 새로고침 버튼을 두지 않는다(설계자 Q2·Q12).
// POC3-02D-OPS-04: '운영 기준 활성'(param_active) 행만 요청 때 PC 운영 기준과 다시 비교한다
// (OCI 값은 기동 때 읽은 것 그대로). ② 전달 뒤 ① 이 이 GET 을 한 번 더 부른다.
//
// 민감정보(토큰·chat id·원격 경로·raw payload)는 응답에 없다.

import { request } from "./core";

export interface OciJobStatus {
  job: string;
  status: string; // SUCCESS / STALE / UNKNOWN
  detail: string;
}

// POC6-27 — 필수 알림 3종의 예약 상태(기동 때 읽은 예약 목록 · 확인 실패 = unknown · 누락으로 세지 않음)
export interface OciScheduleRow {
  kind: string;
  label: string;
  state: "registered" | "missing" | "unknown";
}

export interface OciStartupStatus {
  checked_at: string | null;
  reachable: boolean;
  overall: string; // OPERATING / UNKNOWN
  summary_line: string;
  crontab_active: boolean | null;
  jobs: OciJobStatus[];
  note: string;
  schedule?: OciScheduleRow[];
}

export async function fetchOciStartupStatus(): Promise<OciStartupStatus> {
  return request<OciStartupStatus>("GET", "/oci/startup-status");
}
