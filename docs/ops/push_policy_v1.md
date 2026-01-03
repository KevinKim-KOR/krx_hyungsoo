# PUSH Policy V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 트리거 조건

| 조건 | 시점 |
|------|------|
| **Primary** | Latest 산출물 갱신 직후 (Post-hook) |
| **Trigger Point** | `reports/phase_c/latest/*.json` 파일 갱신 완료 시 |

---

## 2. Push 생성 규칙

### 2.1 PUSH_DIAGNOSIS_ALERT (Critical/Warning)

**조건:**
```
recon_summary.integrity.critical_total > 0  → CRITICAL
recon_summary.integrity.warning_total > 0   → WARNING
```

**생성 시:**
- Severity에 따라 `CRITICAL` 또는 `WARNING` 설정
- `body_ko`에 상위 5개 issue 포함

---

### 2.2 PUSH_MARKET_STATE_BRIEF (Daily)

**조건:**
```
recon_summary.status == "ready"
```

**생성 시:**
- 하루 1회만 생성 (중복 방지)
- `report_human.json`의 KPI 5개 요약 포함

---

### 2.3 PUSH_ACTION_REQUEST (Gatekeeper)

**조건:**
```
gatekeeper_decision_latest.json 존재
AND (decision == "HOLD" OR decision == "REJECT")
```

**생성 시:**
- 운영자 승인/조치 요청 액션 포함
- `body_ko`에 결정 사유 포함

---

## 3. 예외 처리 정책

| 상황 | 처리 |
|------|------|
| 필수 파일 누락 | **SKIP** (중단하지 않음, 로그만) |
| Gatekeeper 파일 없음 | `PUSH_ACTION_REQUEST` SKIP, INFO 로그 |
| 읽기 오류 | SKIP + WARNING 로그 |

> ⚠️ **원칙**: 파일 누락으로 시스템을 중단시키지 않습니다.

---

## 4. 중복 방지 규칙

| Push Type | 중복 방지 |
|-----------|-----------|
| `DIAGNOSIS_ALERT` | 같은 `critical_total` 값이면 재발송 안함 |
| `MARKET_STATE_BRIEF` | 하루 1회 (asof 날짜 기준) |
| `ACTION_REQUEST` | 같은 `decision_id`면 재발송 안함 |

---

## 5. 로깅 정책

| Level | 상황 |
|-------|------|
| INFO | Push 생성 성공, SKIP 처리 |
| WARNING | 파일 읽기 오류, 예외 발생 |
| ERROR | 시스템 오류 (발생 시 운영자 알림) |

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.0) |
