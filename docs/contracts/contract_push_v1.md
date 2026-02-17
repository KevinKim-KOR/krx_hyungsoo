# Contract: PUSH Message V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: DRAFT → REVIEW

---

## 1. 개요

Push 시스템은 **알림, 브리핑, 운영 요청**을 생성하는 시스템입니다.

> ⚠️ **범위 제한**: 매수 추천, 실거래 실행은 이 Contract의 범위 외입니다.

> 🚫 **금지 규정 (CP-1)**: 
> - Push 생성기가 subprocess를 호출하거나 엔진을 직접 실행하는 것을 **금지**합니다.
> - **Holdings/종목추천/실매매 Push는 Phase C-P.2 이후에만 허용**됩니다. 이 Contract에서는 **브리핑/알림/운영요청**만 다룹니다.

---

## 2. 입력 소스 (Single Source of Truth)

Push 생성기는 **오직 아래 파일들만** 읽을 수 있습니다:

| 파일 | 용도 | 필수 |
|------|------|------|
| `reports/phase_c/latest/recon_summary.json` | Integrity 상태 | ✅ |
| `reports/phase_c/latest/recon_daily.jsonl` | 일별 상세 | ✅ |
| `reports/phase_c/latest/report_human.json` | Human Report | ✅ |
| `reports/phase_c/latest/report_ai.json` | AI Report | ✅ |
| `reports/tuning/latest/gatekeeper_decision_latest.json` | Gatekeeper 결정 | ⚠️ Optional |

---

## 3. PUSH 타입 정의 (3종)

| Type | 설명 | Source |
|------|------|--------|
| `PUSH_DIAGNOSIS_ALERT` | 시스템 무결성/데이터 이상 알림 | Recon |
| `PUSH_MARKET_STATE_BRIEF` | 오늘 시장/엔진 상태 요약 | Report |
| `PUSH_ACTION_REQUEST` | 운영자 승인/조치 요청 | Gatekeeper |

---

## 4. PUSH_MESSAGE_V1 스키마

```json
{
  "schema": "PUSH_MESSAGE_V1",
  "message_id": "push_20260103_143000_001",
  "type": "PUSH_DIAGNOSIS_ALERT | PUSH_MARKET_STATE_BRIEF | PUSH_ACTION_REQUEST",
  "severity": "INFO | WARNING | CRITICAL",
  "title_ko": "시스템 알림 제목",
  "body_ko": "알림 본문 (최대 500자)",
  "asof": "2026-01-03T14:30:00+09:00",
  "sources": [
    {
      "file": "reports/phase_c/latest/recon_summary.json",
      "hash": "abc123...",
      "read_at": "2026-01-03T14:29:55+09:00"
    }
  ],
  "actions": [
    {
      "id": "OPEN_DASHBOARD",
      "label_ko": "대시보드 열기",
      "target": "/"
    }
  ]
}
```

### 필드 정의

| Key | Type | 필수 | 설명 |
|-----|------|------|------|
| `message_id` | string | ✅ | 고유 식별자 (push_YYYYMMDD_HHMMSS_NNN) |
| `type` | enum | ✅ | 3종 중 하나 |
| `severity` | enum | ✅ | INFO / WARNING / CRITICAL |
| `title_ko` | string | ✅ | 한국어 제목 (최대 50자) |
| `body_ko` | string | ✅ | 한국어 본문 (최대 500자) |
| `asof` | ISO8601 | ✅ | 생성 시각 |
| `sources` | array | ✅ | 읽은 파일 목록 + 해시 |
| `actions` | array | ✅ | 가능한 액션 목록 |

---

## 5. Actions Enum

| Action | 설명 | 실행 주체 |
|--------|------|-----------|
| `OPEN_DASHBOARD` | 대시보드 탭 열기 | UI |
| `REQUEST_RECONCILE` | Reconcile 재실행 요청 (티켓) | 운영자 |
| `REQUEST_REPORTS` | Report 재생성 요청 (티켓) | 운영자 |
| `OPEN_ISSUE` | GitHub Issue 생성 | 운영자 |
| `ACKNOWLEDGE` | 알림 확인 처리 | 운영자 |

> 🚫 **RUN 금지**: `RUN_*` 형태의 직접 실행 액션은 허용하지 않습니다.

---

## 6. Severity 정의

| Severity | 조건 | 알림 방식 |
|----------|------|-----------|
| `CRITICAL` | `integrity.critical_total > 0` | 즉시 알림 + 상단 고정 |
| `WARNING` | `warning_total > 0` | 일반 알림 |
| `INFO` | 정상 상태 | 로그만 |

> 🔴 **CP-2 규정**: CRITICAL은 **오직 `recon_summary.integrity.critical_total > 0`일 때만** 발생합니다.
> - Trade mismatch, Gatekeeper missing 등은 CRITICAL이 **아닙니다** (WARNING 또는 INFO).
> - CRITICAL 남용을 방지하기 위해 이 조건은 변경 금지입니다.

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.0) |
