# POC2 — UI 안전실행 (ML evidence 갱신 background job) CONCLUSION

작성: 2026-06-11
성격: Step 완료 보고. canonical 상태 (`docs/STATE_LATEST.md`) 의 detail 링크.

---

## 0. 한 줄 요약

기존 CLI 3종 (`generate_ml_features` → `check_ml_feature_sanity` →
`run_ml_baseline_v0`) 을 Data Status 화면의 "ML evidence 갱신 실행" 버튼 1개로
안전하게 background 에서 순차 실행. CLI 경로는 그대로 살아있고 (이중화), HTTP
요청은 즉시 반환되며, 중복 실행은 차단된다. 단계 실패 시 이후 단계는 skipped 이고
기존 snapshot 은 삭제하지 않는다 (마지막 성공 결과 보존).

Celery / Redis / 신규 DB / 외부 source / ML 학습 / 매수·매도·추천·현금·조정장·
위험알림 0건.

---

## 1. AC 달성 현황

```text
AC-1  Data Status 실행 버튼 (ML evidence 갱신 실행)                          = DONE
AC-2  비동기 실행 (HTTP 즉시 반환, 화면 대기 X)                              = DONE
AC-3  단계별 실행 (feature → sanity → baseline 순서)                         = DONE
AC-4  중복 실행 방지 (in-process Lock + on-disk status 검사)                 = DONE
AC-5  상태 표시 (queued/running/success/failed + 단계별 + 시작·종료 시각)    = DONE
AC-6  실패 격리 (기존 snapshot 3종 삭제 안 함)                               = DONE
AC-7  status API read-only (job 실행 X)                                       = DONE
AC-8  실행 API background (HTTP 응답에서 동기 실행 X)                        = DONE
AC-9  CLI 경로 유지 (3 script 그대로 동작)                                   = DONE
AC-10 GenerateDraft 의 ML baseline evidence 연결 유지                         = DONE
AC-11 기존 흐름 유지 (Data Status / GenerateDraft / AI Sessions / Approval)  = DONE
AC-12 범위 위반 0건 (PUSH/OCI/Telegram/매수매도/threshold/Celery 모두 X)     = DONE
AC-13 문서 갱신 (STATE / NEXT_ACTIONS / FEATURE_INVENTORY + 본 파일)         = DONE
```

---

## 2. 변경 파일 (구조)

**Backend 신규 (2)**:
- `app/ml_job_runner.py` **447 라인** — job state schema + 3단계 runner +
  `threading.Lock` (in-process) + on-disk status + PID + heartbeat (10분 stale
  자동 해제). `_run_feature` / `_run_sanity` / `_run_baseline` 가 각각 CLI 와
  동일한 핵심 함수 (`build_features` / `build_sanity_report` /
  `build_baseline_report`) 를 직접 호출 → subprocess 0건.
- `app/api_ml_jobs.py` **101 라인** — `POST /ml/jobs/evidence-refresh`
  (FastAPI `BackgroundTasks` 사용, 즉시 반환) + `GET /ml/jobs/latest` (read-only).

**Backend 수정 (2)**:
- `app/api.py` — `ml_jobs_router` import + include.
- `.gitignore` — `state/ml/ml_job_status_latest.json` 운영 artifact.

**Frontend 신규 (2)**:
- `frontend/lib/api/mlJobs.ts` **79 라인** — 타입 5종 + `fetchMlJobsLatest()` +
  `startMlEvidenceRefresh()`.
- `frontend/app/components/MLEvidenceRefreshCard.tsx` **290 라인** — Data Status
  최상단 카드. 실행 중 5초 polling 자동 갱신 + 단계별 상태 표 + 마지막 성공 요약.

**Frontend 수정 (2)**:
- `frontend/lib/api/index.ts` — barrel re-export.
- `frontend/app/components/DataStatusView.tsx` — `<MLEvidenceRefreshCard />` 추가.

**Tests 신규 (1)**:
- `tests/test_ml_job_runner.py` **FIX r2 후 +6 = 16 테스트**
  (단계 순서 / 단계 실패 격리 / AC-6 snapshot 보존 / AC-4 중복 차단 / AC-2 즉시
  반환 / AC-7 status API read-only / stale lock 자동 해제 / API ok/already_running
  + FIX r2: Windows PID 비활성화 / Windows heartbeat-only stale 판정 / 손상 시
  GET·POST·get_latest_status 의 error 응답 3종).

**Docs 수정 (3)** + **신규 (1)**:
- `docs/STATE_LATEST.md` / `docs/handoff/POC2_B_NEXT_ACTIONS.md` /
  `docs/handoff/POC2_FEATURE_INVENTORY.md`.
- `docs/handoff/POC2_UI_SAFE_ML_EVIDENCE_EXECUTION_CONCLUSION.md` — 본 파일.

---

## 3. 핵심 설계 결정 (사용자 확정)

### 3.1 background 실행 — (a) in-process FastAPI BackgroundTasks + threading.Lock

CLI 의 main() 함수가 아니라 그 안의 핵심 함수 (`build_features` /
`build_sanity_report` / `build_baseline_report`) 를 runner 가 직접 호출.
subprocess / filelock 등 외부 의존성 0건. FastAPI 단일 워커 전제.

### 3.2 stale lock — (a) PID + heartbeat, 10분 초과면 해제

`state/ml/ml_job_status_latest.json` 에 `pid` 와 `last_heartbeat_at` 기록.
status=running 이지만 (1) PID 가 죽었거나 (2) heartbeat 가 10분 초과면 stale 로
간주하고 새 job 허용. 운영 안전 — 프로세스 추락 / kill / 시스템 재시작 후
사용자가 수동 해제 없이 다시 실행 가능.

**FIX r2 (A-1 / B-6)**: Windows 에서 `os.kill(pid, 0)` 이 PID 0 을 alive 로
반환하고 자기 PID 대상 시 KeyboardInterrupt 유발 가능 — stdlib 만으로 안전한
Windows PID 확인은 없으므로 `_PID_CHECK_SUPPORTED = sys.platform != "win32"`
플래그를 두고 Windows 에서는 PID 확인을 완전히 비활성화. heartbeat 10분만으로
stale 판정. POSIX 는 기존 로직 유지. psutil 등 신규 의존성 0건 (§8 정신 준수).

### 3.4 status 파일 손상 fail-loud (FIX r2 B-1)

기존 `_read_status` 가 JSON 손상 시 `None` 반환 → API 가 `status="empty"` 로
응답 → 미실행과 구분 불가. 해결:
- `_read_status_raw()` 가 `(state | None, error | None)` tuple 반환.
- `get_latest_status()` 동일 시그니처.
- API `GET /ml/jobs/latest` 가 손상 시 `status="error"` + 사용자에게 메시지
  ("파일을 삭제하거나 직접 확인 후 재시도하세요").
- API `POST /ml/jobs/evidence-refresh` 가 손상 시 새 job 자동 생성하지 않고
  `status="error"` 응답 — 자동 덮어쓰기 금지 (진단 기회 보존).
- frontend `MLEvidenceRefreshCard` 가 `status="error"` 분기에서 빨간색 메시지로
  명시 표시.

### 3.3 frontend Card — (a) MLEvidenceRefreshCard 신규 1개 + DataStatusView 상단

기존 `MLFeatureSanityCard` / `MLBaselineV0Card` 는 표시 전용으로 유지. 실행
접점은 신규 Card 하나. 책임 분리 명확, KS-10 안전. 실행 중일 때만 5초 polling
으로 자동 갱신 (완료 후 즉시 멈춤).

---

## 4. 운영 동작

```
사용자: Data Status 화면 진입
  ↓ MLEvidenceRefreshCard mount
  ↓ GET /ml/jobs/latest (read-only, 1회)
  ↓ 마지막 실행 상태 표시

사용자: "ML evidence 갱신 실행" 클릭
  ↓ POST /ml/jobs/evidence-refresh
  ↓ ml_job_runner.start_evidence_refresh_job(schedule=BackgroundTasks.add_task)
  ↓   ├─ on-disk status running 검사 (PID/heartbeat stale 자동 해제)
  ↓   ├─ in-process threading.Lock 획득 시도
  ↓   ├─ 초기 state 작성 + ml_job_status_latest.json 기록
  ↓   └─ BackgroundTasks 에 _runner 등록 (응답 송신 직후 실행)
  ↓ HTTP 응답 즉시 반환 (status=accepted) — 측정 2.6ms
  ↓
  ↓ [background] feature → sanity → baseline 순차 실행
  ↓   각 단계마다 snapshot 저장 + heartbeat 갱신
  ↓   실패 시 이후 단계 skipped, 기존 snapshot 보존
  ↓ 완료 시 in-process lock release

사용자: 화면 자동 갱신 (5초 polling — running 동안만)
  ↓ GET /ml/jobs/latest 반복
  ↓ 단계별 상태 / heartbeat / 마지막 성공 요약 표시
  ↓ status ∈ {success, failed} 도달 시 polling 자동 중단

중복 클릭 / 다른 사용자 동시 요청:
  ↓ POST /ml/jobs/evidence-refresh
  ↓ start_evidence_refresh_job 이 JobAlreadyRunningError raise
  ↓ HTTP 응답 status=already_running + 현재 running job snapshot 반환

CLI 경로 (이중화, 그대로 살아있음):
  $ python scripts/generate_ml_features.py     (수동)
  $ python scripts/check_ml_feature_sanity.py  (수동)
  $ python scripts/run_ml_baseline_v0.py       (수동)
  또는 본 runner 자체도 CLI 진입 가능:
  $ python -m app.ml_job_runner                (3단계 자동)
```

---

## 5. 이번 STEP 에서 의도적으로 하지 않은 것 (지시문 §8)

- ML feature 산식 / baseline scoring 변경.
- risk threshold 확정 / 조정장 라벨 / 매수·매도 / 현금비중 / 위험 알림.
- PUSH / OCI / Telegram 문구 변경.
- 신규 외부 source (CNN Fear&Greed / 원유 / 환율 / 미국 선물).
- Celery / Redis / 신규 DB / 학습형 ML 모델.
- 5년 backfill 기본 실행.

---

## 6. 검증 결과

- **backend pytest** — PASS (**470 passed**, +16 신규 / 회귀 0, FIX r2 후 3회 연속
  실행 비결정성 0건 확인).
- **black --check / flake8** — PASS (E203/black 충돌 1건은 기존 프로젝트 패턴
  대로 `# noqa: E203` 처리).
- **frontend ESLint / Next.js build** — PASS.
- **live 실측 (uvicorn 직접 호출, 운영 SQLite)**:
  - POST `/ml/jobs/evidence-refresh` 첫 호출 **2.6ms** 만에 `accepted` 반환
    (AC-2 / AC-8 충족 — 즉시 반환 확인).
  - 즉시 두 번째 POST **2.2ms** 만에 `already_running` 반환 (AC-4 충족 — 중복
    차단 확인).
  - GET `/ml/jobs/latest` polling: t+1~3s 동안 feature=running, t+4s 시점에
    sanity 와 baseline 까지 모두 success 전환. 단계별 상태 정확 (AC-5 충족).
  - 최종: status=success / evaluated_days=43 / baseline_report_status=ok.
- **외부 source 호출 0건** — runner 가 호출하는 함수들은 모두 SQLite read/write
  만 수행. `test_get_latest_does_not_start_job` 가 step 함수를 `_boom` 으로
  monkeypatch 해서 GET 이 job 을 실행하지 않음을 직접 보장.

---

## 7. KS-10 자체 점검

신규 / 수정 파일의 라인수 실측 (`wc -l`):

| 파일 | 라인 | 임계 | 분류 |
| --- | --- | --- | --- |
| `app/ml_job_runner.py` (FIX r2 후) | **502** | 600 / 650 | 안전 |
| `app/api_ml_jobs.py` (FIX r2 후) | **125** | 600 / 650 | 안전 |
| `frontend/app/components/MLEvidenceRefreshCard.tsx` (FIX r2 후) | **298** | 850 / 900 | 안전 |
| `frontend/lib/api/mlJobs.ts` (FIX r2 후) | **82** | 850 / 900 | 안전 |
| `tests/test_ml_job_runner.py` (FIX r2 후) | **513** | n/a (tests) | 안전 |

KS-10 trigger/near 0건. 신규 모듈 분리 (runner / api / frontend api / Card / test)
로 책임 명확 + 라인 폭증 회피.

---

## 8. 결과 해석 (참고용, 사용자 판단 영역)

- 본 STEP 은 **운영 편의 개선** 이지 ML 고도화가 아니다. baseline 산식 / 모델 /
  threshold 는 그대로다.
- 사용자가 터미널을 열 필요 없이 화면에서 ML evidence 를 갱신할 수 있고, 갱신
  결과는 그 자리에서 단계별로 확인할 수 있다.
- CLI 는 살아있으므로 자동화 (cron / scheduler) 가 필요한 경우 그대로 사용 가능.
  본 STEP 의 UI 는 CLI 대체가 아니라 보완.
- ML baseline evidence 의 stale 7일 정책 (ML Baseline Evidence Draft Integration
  STEP 에서 도입) 과 결합하면, 사용자가 GenerateDraft 직전에 evidence 가 stale
  임을 보고 본 버튼으로 즉시 갱신하는 흐름이 자연스러워진다.

---

## 9. 다음 분기 후보 (사용자 결정 영역)

1. **schedule 기반 자동 실행** — 사용자가 시간(예: 18:00) 을 지정해 매일 자동
   갱신. 본 STEP 의 runner 를 그대로 활용 가능.
2. **단계별 진행률** — 현재는 단계 단위 상태만 표시. feature 생성 progress bar
   등 세분화.
3. **실행 히스토리** — 현재는 latest 1건만 저장. 최근 10건 보존 + UI 표.
4. **stale 알림 통합** — ML baseline evidence 가 stale 일 때 GenerateDraft
   화면에서 "갱신이 필요합니다" 안내 + 본 STEP 의 갱신 버튼으로 deeplink.

본 문서는 다음 STEP 을 임의 확정하지 않는다.
