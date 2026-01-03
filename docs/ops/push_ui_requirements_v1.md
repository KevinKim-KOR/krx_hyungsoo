# PUSH UI Requirements V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: DRAFT

---

## 1. Push 탭 정보 구조

```
Dashboard
├── Status
├── Diagnosis
├── Push ← 신규 탭
│   ├── Active Alerts (상단)
│   ├── Today's Brief (중단)
│   └── History (하단)
└── ...
```

---

## 2. Active Alerts 섹션

### 표시 항목
| 필드 | 표시 |
|------|------|
| `severity` | 배지 (🔴 CRITICAL / 🟠 WARNING / 🟢 INFO) |
| `title_ko` | 제목 |
| `asof` | 시간 (상대 시간: "5분 전") |
| `actions` | 버튼 목록 |

### CRITICAL 배지 규칙
- 🔴 **CRITICAL**: 빨간색 배지 + **상단 고정**
- 🟠 WARNING: 주황색 배지
- 🟢 INFO: 회색 배지

---

## 3. Drill-down 규칙

### Integrity Code 클릭 시
| 클릭 대상 | 동작 |
|-----------|------|
| `IC_*` 코드 | Diagnosis 탭으로 이동 + 해당 코드 필터링 |
| `A1_*` 코드 | Diagnosis 탭으로 이동 + 해당 코드 필터링 |

### 구현
```
클릭: "IC_MISSING_SIGNAL"
→ 이동: /diagnosis?filter=IC_MISSING_SIGNAL
```

---

## 4. 버튼 규칙

> ⚠️ **핵심 원칙**: 버튼은 "실행"이 아니라 **"요청 티켓 생성"**입니다.

| 버튼 | 라벨 | 동작 |
|------|------|------|
| `OPEN_DASHBOARD` | "대시보드 열기" | `/` 로 이동 |
| `REQUEST_RECONCILE` | "재조정 요청" | 티켓 생성 모달 |
| `REQUEST_REPORTS` | "리포트 재생성 요청" | 티켓 생성 모달 |
| `OPEN_ISSUE` | "이슈 생성" | GitHub Issue 링크 |
| `ACKNOWLEDGE` | "확인" | 알림 읽음 처리 |

### 티켓 생성 모달
```
┌─────────────────────────────┐
│ 재조정 요청                  │
├─────────────────────────────┤
│ 사유: [________________]    │
│ 우선순위: ○ 낮음 ● 보통 ○ 높음 │
├─────────────────────────────┤
│ [취소]          [요청 생성]  │
└─────────────────────────────┘
```

---

## 5. Today's Brief 섹션

| 항목 | 내용 |
|------|------|
| 시장 상태 | Bull / Bear / Chop |
| KPI 요약 | 5개 지표 요약 |
| 엔진 상태 | Ready / Not Ready |

---

## 6. History 섹션

| 필드 | 표시 |
|------|------|
| `asof` | 날짜/시간 |
| `type` | 타입 배지 |
| `title_ko` | 제목 |
| `severity` | 심각도 |

### 필터
- 날짜 범위
- 타입별 (DIAGNOSIS / BRIEF / ACTION)
- 심각도별

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.0) |
