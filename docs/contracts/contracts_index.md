# Contracts Index

**Version**: 2.0  
**Date**: 2026-01-03

---

## Contract 5: Reports

| 스키마명 | 파일 경로 | 소비 주체 |
|----------|-----------|-----------|
| `REPORT_HUMAN_V1` | `reports/phase_c/latest/report_human.json` | UI (Dashboard) |
| `REPORT_AI_V1` | `reports/phase_c/latest/report_ai.json` | AI Agent |

→ 상세: [contract_5_reports.md](contract_5_reports.md)

---

## Reconciliation Contracts

| 스키마명 | 파일 경로 | 소비 주체 |
|----------|-----------|-----------|
| `RECON_SUMMARY_V1` | `reports/phase_c/latest/recon_summary.json` | Backend, UI, Report Generator |
| `RECON_DAILY_V1` | `reports/phase_c/latest/recon_daily.jsonl` | Backend, UI |

---

## Ticket Contracts

| 스키마명 | 문서 경로 | 설명 |
|----------|-----------|------|
| `TICKET_SUBMIT_V1` | [contract_ticket_v1.md](contract_ticket_v1.md) | 클라이언트 입력용 |
| `TICKET_REQUEST_V1` | [contract_ticket_v1.md](contract_ticket_v1.md) | 서버 저장용 |
| `TICKET_RESULT_V1` | [contract_ticket_result_v1.md](contract_ticket_result_v1.md) | 처리 결과 |
| `TICKETS_BOARD_V1` | [contract_ticket_result_v1.md](contract_ticket_result_v1.md) | 상태 보드 View |

---

## Execution & Gate Contracts

| 스키마명 | 문서 경로 | 설명 |
|----------|-----------|------|
| `EXECUTION_GATE_V1` | [contract_execution_gate_v1.md](contract_execution_gate_v1.md) | 실행 모드 제어 |
| `EXECUTION_PLAN_V1` | [contract_execution_plan_v1.md](contract_execution_plan_v1.md) | 실행 계획 (JSON SoT: [execution_plan_v1.json](execution_plan_v1.json)) |
| `DRYRUN_ARTIFACT_V1` | [contract_dryrun_artifact_v1.md](contract_dryrun_artifact_v1.md) | Dry-Run 결과물 |

---

## Push & Worker Contracts

| 스키마명 | 문서 경로 | 설명 |
|----------|-----------|------|
| `PUSH_MESSAGE_V1` | [contract_push_v1.md](contract_push_v1.md) | Push 메시지 |
| `TICKET_WORKER_V1` | [contract_ticket_worker_v1.md](contract_ticket_worker_v1.md) | 워커 정책 |
| `TICKET_IDEMPOTENCY_V1` | [contract_ticket_idempotency_v1.md](contract_ticket_idempotency_v1.md) | 중복 방지 규칙 |

---

## Safety & Receipt Contracts

| 스키마명 | 문서 경로 | 설명 |
|----------|-----------|------|
| `EXECUTION_RECEIPT_V3` | [contract_execution_receipt_v3.md](contract_execution_receipt_v3.md) | sha256 기반 증거 |
| `RECONCILE_DEPENDENCY_V2` | [contract_reconcile_dependency_v2.md](contract_reconcile_dependency_v2.md) | 의존성 정공법 |
| `RECONCILE_PREFLIGHT_V1` | [contract_reconcile_preflight_v1.md](contract_reconcile_preflight_v1.md) | Preflight 체크 |
| `REAL_ENABLE_WINDOW_V1` | [contract_real_enable_window_v1.md](contract_real_enable_window_v1.md) | REAL 윈도우 |
| `EMERGENCY_STOP_V1` | [contract_emergency_stop_v1.md](contract_emergency_stop_v1.md) | 비상 정지 |
| `REAL_WINDOW_OPS_V1` | [contract_real_window_ops_v1.md](contract_real_window_ops_v1.md) | 윈도우 운영 정책 |
| `DAILY_OPS_REPORT_V1` | [contract_daily_ops_report_v1.md](contract_daily_ops_report_v1.md) | 일일 운영 리포트 |
| `REAL_EXECUTION_OPS_FLOW_V1` | [contract_real_execution_ops_flow_v1.md](contract_real_execution_ops_flow_v1.md) | REAL 실행 플로우 |
| `OPS_RUNNER_V1` | [contract_ops_runner_v1.md](contract_ops_runner_v1.md) | 운영 관측 루프 |
| `OPS_CYCLE_V2` | [contract_ops_cycle_v2.md](contract_ops_cycle_v2.md) | Ops Cycle + 티켓 처리 |
| `SCHEDULER_V1` | [contract_scheduler_v1.md](contract_scheduler_v1.md) | 일일 스케줄러 |
| ~~`PUSH_DELIVERY_V1`~~ | [contract_push_delivery_v1.md](contract_push_delivery_v1.md) | ~~푸시 발송 결정~~ *(DEPRECATED)* |
| `PUSH_DELIVERY_RECEIPT_V2` | [contract_push_delivery_receipt_v2.md](contract_push_delivery_receipt_v2.md) | 푸시 발송 결정 V2 |
| `PUSH_CHANNELS_V1` | [contract_push_channels_v1.md](contract_push_channels_v1.md) | 푸시 채널 정의 |
| `SECRETS_STATUS_V1` | [contract_secrets_status_v1.md](contract_secrets_status_v1.md) | 시크릿 상태 |
| `SECRETS_PROVISIONING_V1` | [contract_secrets_provisioning_v1.md](contract_secrets_provisioning_v1.md) | 시크릿 프로비저닝 |
| `SECRETS_SELF_TEST_V1` | [contract_secrets_self_test_v1.md](contract_secrets_self_test_v1.md) | 시크릿 Self-Test |
| `PUSH_OUTBOX_V1` | [contract_push_outbox_v1.md](contract_push_outbox_v1.md) | 푸시 Outbox |
| `PUSH_RENDER_PREVIEW_V1` | [contract_push_render_preview_v1.md](contract_push_render_preview_v1.md) | 푸시 렌더 프리뷰 |
| `REAL_SENDER_ENABLE_V1` | [contract_real_sender_enable_v1.md](contract_real_sender_enable_v1.md) | Real Sender 활성화 |
| `PUSH_SEND_RECEIPT_V1` | [contract_push_send_receipt_v1.md](contract_push_send_receipt_v1.md) | 푸시 발송 영수증 |

---

## 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-S.0) |
| 2.0 | 2026-01-03 | Ticket, Execution, Push, Worker 관련 계약 추가 (Phase C-P.6.0) |
| 3.0 | 2026-01-03 | Safety & Receipt 계약 추가 (Phase C-P.11) |
