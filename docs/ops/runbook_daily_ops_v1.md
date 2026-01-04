# Daily Ops Runbook V1

**Version**: 1.0
**Date**: 2026-01-04
**Status**: LOCKED

---

## 1. 정공법 순서 (Daily Ops Checklist)

일일 운영은 반드시 아래 순서로 진행합니다:

### Step 1: Emergency Stop 확인

```bash
GET /api/emergency_stop
```

| 상태 | 조치 |
|------|------|
| `enabled: false` | 정상, 다음 단계 진행 |
| `enabled: true` | **즉시 중단** - 비상 정지 해제 전까지 운영 금지 |

### Step 2: Gate 모드 확인

```bash
GET /api/execution_gate
```

| 모드 | 설명 |
|------|------|
| `MOCK_ONLY` | 안전 모드 (테스트만) |
| `DRY_RUN` | Dry-run 모드 |
| `REAL_ENABLED` | 실제 실행 모드 (**주의 필요**) |

### Step 3: Real Enable Window 상태 확인 (REAL 모드 시)

```bash
GET /api/real_enable_window/latest
```

- Window가 `ACTIVE`인지 확인
- TTL 남은 시간 확인
- 1회 소진 여부 확인

### Step 4: Approval 상태 확인 (REAL 모드 시)

```bash
GET /api/approvals/real_enable/latest
```

- 2-Key 승인이 `APPROVED`인지 확인

### Step 5: Ops Cycle 실행

```bash
# Windows
.\.venv\Scripts\python.exe -m app.run_ops_cycle

# Linux/NAS
./deploy/run_daily_ops.sh
```

### Step 6: 결과 확인

```bash
GET /api/ops/daily
```

또는 파일 확인:
- `reports/ops/daily/ops_report_latest.json`
- `reports/ops/daily/snapshots/ops_run_*.json`

---

## 2. 장애 대응

### STOPPED (긴급정지)

**원인**: `emergency_stop.enabled = true`

**조치**:
1. 긴급정지 사유 확인 (`GET /api/emergency_stop`)
2. 원인 해결
3. 긴급정지 해제 (`POST /api/emergency_stop` with `enabled: false`)
4. Ops Cycle 재실행

### PREFLIGHT_FAIL

**원인**: 의존성 미설치 또는 입력 파일 미준비

**조치**:
1. `reports/tickets/preflight/*.json`에서 실패 상세 확인
2. 의존성 설치: `pip install pandas pyarrow`
3. 입력 파일 확인: `input/`, `config/` 경로
4. Ops Cycle 재실행

### ALLOWLIST_VIOLATION

**원인**: 요청 타입이 Allowlist에 없음

**조치**:
1. `docs/contracts/execution_allowlist_v1.json` 확인
2. 필요 시 Allowlist 수정 (계약 변경 - 승인 필요)
3. 수정 후 커밋 및 재배포

### WINDOW_NOT_ACTIVE

**원인**: REAL Window가 비활성 상태

**조치**:
1. Window 생성: `POST /api/real_enable_window/request`
2. Approval 완료 확인
3. Window ACTIVE 확인 후 재실행

---

## 3. 절대 금지 리스트

> 🚫 **아래 행위는 시스템 무결성을 심각하게 훼손합니다**

| 금지 행위 | 사유 |
|-----------|------|
| `execution_gate.json`에서 REAL 강제 설정 | 안전장치 우회 |
| `state/tickets/*.jsonl` 수동 수정 | Append-only 원칙 위반 |
| `state/emergency_stop.json` 삭제 | 비상정지 무력화 |
| `logs/` 수동 삭제/수정 | 감사 추적 불가 |
| `docs/contracts/` 임의 수정 | 계약 무결성 훼손 |
| Allowlist/Window 없이 REAL 시도 | 미승인 실행 |

---

## 4. 스케줄러 등록 가이드

### Windows (작업 스케줄러)

1. `작업 스케줄러` 열기
2. `기본 작업 만들기`
3. 트리거: 매일 09:00 (또는 원하는 시간)
4. 동작: 프로그램 시작
   - 프로그램: `C:\path\to\project\.venv\Scripts\python.exe`
   - 인수: `-m app.run_ops_cycle`
   - 시작 위치: `C:\path\to\project`

### Linux (Cron)

```cron
# 매일 09:00 실행 (Asia/Seoul)
0 9 * * * cd /path/to/project && ./deploy/run_daily_ops.sh >> logs/cron.log 2>&1
```

### Synology NAS (작업 스케줄러)

1. 제어판 → 작업 스케줄러
2. 생성 → 예약된 작업 → 사용자 정의 스크립트
3. 스크립트: `/volume1/project/deploy/run_daily_ops.sh`

---

## 5. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-04 | 초기 버전 (Phase C-P.17) |
