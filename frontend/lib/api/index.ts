// `@/lib/api` barrel re-export — KS-10 Cleanup (API Client / Type Split) 의
// 호환 게이트.
//
// 본 파일은 도메인 책임을 갖지 않는다. 새 책임을 추가할 때는 도메인 모듈
// (core / runApproval / holdings / universeMomentum / market / marketEvidence /
//  etfExposure / decisionSessions) 중 해당 파일에 직접 추가한다.
//
// core.ts 의 `request` 는 도메인 모듈 간 내부 fetch wrapper 이므로 외부에
// 노출하지 않는다 (원본 frontend/lib/api.ts 에서 비-export 였음 — public surface
// 정합 유지). core 에서는 `ApiConfigError` 와 `ApiRequestError` 만 명시 재export.

export { ApiConfigError, ApiRequestError } from "./core";
export * from "./runApproval";
export * from "./holdings";
export * from "./universeMomentum";
export * from "./marketEvidence";
export * from "./market";
export * from "./etfExposure";
export * from "./decisionSessions";
