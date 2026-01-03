# Phase C-P.0: PUSH Workflow Design

**Date**: 2026-01-03
**Status**: ✅ 완료

---

## 📋 목표

Push 시스템의 정의, 범위, 데이터 소스, 생성 규칙을 Contract(계약)와 Policy(정책) 문서로 확정.

---

## 📁 생성된 문서

| 문서 | 경로 | 설명 |
|------|------|------|
| Contract | `docs/contracts/contract_push_v1.md` | PUSH_MESSAGE_V1 스키마 정의 |
| Policy | `docs/ops/push_policy_v1.md` | 생성 규칙, 예외 처리 |
| UI Requirements | `docs/ops/push_ui_requirements_v1.md` | UI 요구사항 |

---

## 🔗 입력 소스 (SoT Allowlist)

1. `reports/phase_c/latest/recon_summary.json`
2. `reports/phase_c/latest/recon_daily.jsonl`
3. `reports/phase_c/latest/report_human.json`
4. `reports/phase_c/latest/report_ai.json`
5. `reports/tuning/gatekeeper_decision_latest.json` (Optional)

---

## 📊 PUSH 타입 (3종)

| Type | 설명 |
|------|------|
| `PUSH_DIAGNOSIS_ALERT` | 시스템 무결성/데이터 이상 알림 |
| `PUSH_MARKET_STATE_BRIEF` | 시장/엔진 상태 요약 |
| `PUSH_ACTION_REQUEST` | 운영자 승인/조치 요청 |

---

## 🎯 Actions Enum

| Action | 설명 |
|--------|------|
| `OPEN_DASHBOARD` | 대시보드 열기 |
| `REQUEST_RECONCILE` | 재조정 요청 (티켓) |
| `REQUEST_REPORTS` | 리포트 재생성 요청 (티켓) |
| `OPEN_ISSUE` | GitHub Issue 생성 |
| `ACKNOWLEDGE` | 알림 확인 |

> 🚫 RUN 금지: 직접 실행 액션 없음

---

## 🚀 다음 단계

**C-P.1**: PUSH Ticket Schema & Generator Design
