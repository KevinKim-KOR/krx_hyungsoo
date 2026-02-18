# Contracts Index

**Version**: 2.1 (P146: Operator API & Draft)
**Date**: 2026-02-18
**Status**: ACTIVE

---

## 🌟 Top 5 Operational Contracts (Start Here)

운영자가 가장 먼저 확인해야 할 핵심 문서입니다.

| 순위 | 문서 | 설명 |
|:---:|---|---|
| **1** | **[STATE_LATEST.md](../SSOT/STATE_LATEST.md)** | 시스템 현재 상태 및 운영 구조 (Handoff) |
| **2** | **[contract_sync_v1.md](contract_sync_v1.md)** | PC↔OCI 동기화 (SSOT, Status, Artifact) |
| **3** | **[contract_operator_api_v1.md](contract_operator_api_v1.md)** | OCI Operator Dashboard API (Draft/Submit) |
| **4** | **[contract_ops_summary_v1.md](contract_ops_summary_v1.md)** | 운영 상태 요약 (Single Pane of Glass) |
| **5** | **[contract_manual_execution_ticket_v1.md](contract_manual_execution_ticket_v1.md)** | 매매 티켓 (Source=Export) |

---

## 1. Interface & Sync (P146)

| 스키마명 | 문서 경로 | 설명 |
|----------|-----------|------|
| `OPERATOR_API_V1` | [contract_operator_api_v1.md](contract_operator_api_v1.md) | Draft/Submit/Regen API |
| `SSOT_SYNC_V1` | [contract_sync_v1.md](contract_sync_v1.md) | PC Push / OCI Pull 프로토콜 |
| `EVIDENCE_REF_V1` | [contract_evidence_ref_v1.md](contract_evidence_ref_v1.md) | Artifact/Log 파일 경로 해석 규칙 |

---

## 2. Manual Execution (Human-in-the-Loop)

| 스키마명 | 문서 경로 | 설명 |
|----------|-----------|------|
| `ORDER_PLAN_EXPORT_V1` | [contract_order_plan_export_v1.md](contract_order_plan_export_v1.md) | **Execution Source** (Token Master) |
| `MANUAL_EXECUTION_TICKET_V1` | [contract_manual_execution_ticket_v1.md](contract_manual_execution_ticket_v1.md) | Human View (Markdown) |
| `MANUAL_EXECUTION_DRAFT_V1` | [contract_manual_execution_record_draft_v1.md](contract_manual_execution_record_draft_v1.md) | Preview Object |
| `MANUAL_EXECUTION_RECORD_V1` | [contract_manual_execution_record_v1.md](contract_manual_execution_record_v1.md) | Final Receipt |

---

## 3. Execution Control

| 스키마명 | 문서 경로 | 설명 |
|----------|-----------|------|
| `EXECUTION_GATE_V1` | [contract_execution_gate_v1.md](contract_execution_gate_v1.md) | Mode Control (Live/Replay, Mock/Real) |
| `EXECUTION_PLAN_V1` | [contract_execution_plan_v1.md](contract_execution_plan_v1.md) | 자동 매매 계획 (JSON SoT) |
| `SETTINGS_V1` | [contract_settings_v1.md](contract_settings_v1.md) | 통합 설정 (System/Spike/Holding) |

---

## 4. Reports & Artifacts

| 스키마명 | 문서 경로 | 설명 |
|----------|-----------|------|
| `CONTRACT5_REPORT_V1` | [contract_5_reports.md](contract_5_reports.md) | Human/AI Report |
| `RECON_SUMMARY_V1` | [contract_reconcile_dependency_v1.md](contract_reconcile_dependency_v1.md) | 정합성 검증 요약 |
| `STRATEGY_BUNDLE_V1` | [contract_strategy_bundle_v1.md](contract_strategy_bundle_v1.md) | 전략 번들 (Settings+Code) |

---

## 5. Push & Notification

| 스키마명 | 문서 경로 | 설명 |
|----------|-----------|------|
| `PUSH_MESSAGE_V1` | [contract_push_v1.md](contract_push_v1.md) | Push 기본 포맷 |
| `PUSH_SEND_RECEIPT_V1` | [contract_push_send_receipt_v1.md](contract_push_send_receipt_v1.md) | 발송 결과 |

---
