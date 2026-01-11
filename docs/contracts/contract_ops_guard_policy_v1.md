# Contract: Ops Guard Policy V1

**Version**: 1.0
**Date**: 2026-01-11
**Status**: LOCKED

---

## 1. 개요

Ops Cycle 실행 전 Guard 규칙을 정의합니다.

> 🔒 **Fail-Closed 원칙**: 예외 발생 시 무조건 FAIL로 간주
> 
> 🔒 **No External Send**: 외부 발송 금지 정책 유지

---

## 2. Guard 실행 순서 (강제)

```
1. Emergency Stop 확인 (최우선)
   └─ enabled=true → overall_status=STOPPED, 전 단계 SKIP

2. Execution Gate Mode 관측 (기록용)

3. Evidence Health 생성/갱신
   └─ run_evidence_health_check.regenerate_health_report() 호출

4. Health 결과 로드 + Guard 판정
   └─ PASS/WARN → 기존 ops 흐름 진행
   └─ FAIL → downstream 단계 전부 SKIP

5. Fail-Closed 처리
   └─ Health 생성/로드 중 예외 발생 시:
      - evidence_health.decision = FAIL
      - fail_closed_triggered = true
      - 이후 단계 전부 SKIP
```

---

## 3. Guard 판정 결과

| Evidence Health Decision | Overall Status | Downstream |
|--------------------------|----------------|------------|
| `PASS` | DONE | 정상 진행 |
| `WARN` | DONE | 정상 진행 |
| `FAIL` | BLOCKED | 전부 SKIP |
| 예외 발생 | BLOCKED | 전부 SKIP (fail_closed) |

---

## 4. Downstream 단계 SKIP 규칙

| 단계 | SKIP 시 decision | reason |
|------|------------------|--------|
| `ticket_step` | SKIPPED | EVIDENCE_HEALTH_FAIL |
| `push_delivery_step` | SKIPPED | EVIDENCE_HEALTH_FAIL |
| `live_fire_step` | SKIPPED | EVIDENCE_HEALTH_FAIL |

---

## 5. Emergency Stop 우선순위

| 조건 | 결과 |
|------|------|
| `emergency_stop.enabled == true` | `overall_status: STOPPED` |
| 모든 단계 | `reason: EMERGENCY_STOP` |

> Emergency Stop은 Evidence Health보다 우선

---

## 6. 시크릿 기록 규칙

- ✅ 허용: 환경변수 **키 이름** (예: `TELEGRAM_BOT_TOKEN`)
- ❌ 금지: 환경변수 **값** (토큰, API 키 등)
- ❌ 금지: 스택트레이스 전체
- ✅ 허용: 에러 요약 (1줄)

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-11 | 초기 버전 (Phase C-P.34) |
