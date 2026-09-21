// POC3-02C-OPS-01 — 장중 알림 설정 번들 API 클라이언트.
//
// 사용자는 **종목을 직접 고르지 않는다.** PC 가 자동 산출한 버전 전체를 보고
// 승인하거나 기각할 뿐이다(설계자 §4-3).
//
// 승인과 적용은 **한 번의 동작**이다(§10-3(3)) — 버튼을 두 번 누르게 하지 않는다.

import { request } from "./core";

export type SectorChange = {
  sector_key: string;
  change: "added" | "removed" | "replaced";
  before?: string | null;
  after?: string | null;
};

export type IntradayConfigState = {
  active_version_id: string | null;
  active_source_hash: string | null;
  active_data_asof: string | null;
  active_sector_count: number;
  candidate_version_id: string | null;
  candidate_source_hash: string | null;
  candidate_data_asof: string | null;
  candidate_sector_count: number;
  changes: SectorChange[];
  // **현재 운영 중인 active 정책** 상태. 후보 값이 아니다.
  policy_enabled: boolean;
  policy_status: string | null;
  // **적용하면 어떻게 되는지.** 후보가 없으면 null.
  candidate_policy_enabled: boolean | null;
  candidate_policy_status: string | null;
  // OPS-03 §2 — 읽기 전용 표시용. 값을 고치는 UI 는 만들지 않는다.
  policy_values: { key: string; value: unknown }[];
  policy_rule_version: string | null;
  deploy_status: string | null;
  deploy_error: string | null;
  // 지금 사용자가 할 일. pending_approval = 승인 · approved_not_deployed = 재시도.
  action_state: string | null;
  // 저장된 설정이 깨졌을 때. 비정상을 "0개" 로 보이게 하지 않는다.
  payload_error: string | null;
};

export type IntradayConfigAction = {
  ok: boolean;
  config_version_id: string;
  deploy_status: string;
  message: string;
};

export function fetchIntradayConfigState(): Promise<IntradayConfigState> {
  return request<IntradayConfigState>("GET", "/intraday-config/state");
}

export function approveAndApplyIntradayConfig(
  configVersionId: string,
): Promise<IntradayConfigAction> {
  return request<IntradayConfigAction>(
    "POST",
    "/intraday-config/approve-and-apply",
    { config_version_id: configVersionId },
  );
}

export function rejectIntradayConfig(
  configVersionId: string,
  reason: string,
): Promise<IntradayConfigAction> {
  return request<IntradayConfigAction>("POST", "/intraday-config/reject", {
    config_version_id: configVersionId,
    reason,
  });
}
