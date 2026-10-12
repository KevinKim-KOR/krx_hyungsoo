# POC5-08 개발 결과서 — ALERT_RETROSPECTIVE_ML_EVALUATION (알림의 ML 사후평가)

작성 2026-10-11 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex)

```text
STATUS                 = IMPLEMENTED_VERIFIED_DEPLOYED_CLOSED — 검증자 r2 VERIFIED(2026-10-12 · 위험 NONE · 범위 폭주 NONE) · 설계자 RESULT PASS_TO_DEPLOY(2026-10-12) · 커밋 `f1951812` push(사용자 승인) · PC 재기동 · 실화면 사용자 확인 · 종료(§10 · 설계자 재판정 없음 · 설계서 §13-6)
DESIGNER_RESULT        = PASS_TO_DEPLOY(2026-10-12 · CODE_REWORK NONE · REVERIFY 불필요 · 결측 표시 열 0/1 비표준화 = 고정 recipe 확정 · 지시문 외 변경 5건 수용 · §5 한계 수용 · POC5-02 · 03 종료 수용 · OCI_PULL 불필요) — 원문 = 설계서 §13 · 끝에 전달문 원문
VERIFIER               = r1 REJECTED(시각 형식 검사 · 실행 시각 자정 대체 · §6-3 수정) → r2 VERIFIED(A-1 ~ A-4 통과 · B-1 ~ B-6 없음 · 독립 확인 관련 회귀 235 · 추가 재현 5 · 정적 검사 통과 · 결과서 시험 건수 문구는 검증자가 직접 정정)
STEP_ID                = POC5-08 알림의 ML 사후평가
DESIGN                 = docs/ai_design/POC5/POC5-08_ALERT_RETROSPECTIVE_ML_EVALUATION_DESIGN_V1.md (V1 · §12 설계자 PLAN 판정 PASS 원문 · 끝에 전달문 원문 2건)
PLAN                   = docs/ai_plan/POC5/POC5-08_ALERT_RETROSPECTIVE_ML_EVALUATION_PLAN_V1.md (PLAN 확정 · 판정 반영 = 본문 정정 + §7)
PREDECESSOR            = POC5-07 · POC5-UI-01
BASE_COMMIT(코드 기준)  = 8ac6f41f
MOCKUP                 = 결과 영역 목업 1회 → 사용자 확인 2026-10-11("확인") · 검토 반영으로 항목 추가(§4 · §7)
API                    = 로컬 2경로 추가(기존 decision-ledger router) — POST /decision-ledger/retrospective-evaluation · GET /decision-ledger/retrospective-evaluation/latest
OCI_CODE               = OCI 실행 파일 · cron · .env 변경 0 → OCI pull 없음
DEPENDENCY             = 신규 0(기존 scikit-learn 1.9.0 · numpy 2.4.6)
TESTS                  = 백엔드 새 2파일 75건(모델 24 · 실행 / 조회 51) · vitest 새 1파일 12건 + 기존 1파일 mock 추가 · 단언 1줄 — §8-1
REVIEW                 = 독립 검토 1회(읽기 전용) — 핵심 ML 로직 결함 0 · 지적 12건 → 11건 수정 · 1건 설계자 확인 요청(§6-2 · §7) · 검증자 r1 지적 1건 수정(§6-3)
MUTATION               = 저장소 사본 38변이 전부 검출(처음 28변이 중 4 생존 → 시험 보강 · 검토 반영 뒤 5변이 · r1 수정 뒤 5변이 추가) — §8-3
KS-10                  = 트리거 0 — 새 백엔드 최대 report.py 390 · 화면 최대 RetroItemRows.tsx 244 · AlertRecordsView.tsx 177 → 238 · 기존 647줄 시장 흐름 모듈 미접촉
BACKEND_FULL_REGRESSION= 3387 passed / 0 failed · exit 0 · 403.47s(2026-10-12 07:05:47 ~ 07:12:35 · r1 수정 뒤 최종 코드) · PC state/logs 1,157파일 해시 동일(§8-5)
```

## 0. 요약

「받은 알림 기록」에서 사용자가 **[사후평가 실행]** 을 누르면 PC 원장 사본을 04 리포트와 같은 방식(`mode=ro` · 읽기 트랜잭션 1개 · 손상 판정)으로 한 번 읽는다. 그 snapshot 으로 다음 세 가지를 만든다.

1. **자동 가격 사후평가**: 저장된 +1 / +5 / +20 결과를 그대로 쓴다. 결과가 없는 칸은 실행 때 고정한 **가격 관측 기준일(price_asof_date)** 로 미도래 / 도래 후 미기록을 나눈다.
2. **+5 고정 Ridge 시간 분리 검증**: 날짜 균형 가중치 · 학습 구간만의 전처리 · 가중 중앙값 기준 · 5거래일 × 3구간 · 날짜 평균 MAE 를 쓴다.
3. **사용자 평가**: event 최신 1건을 별도 근거로 보인다. 표본 · 라벨 · 입력에는 쓰지 않는다.

결과는 `state/ml/research/poc5_08/<생성시각>_<id>/report.json · input_snapshot.json` 에 쓴다. 화면 진입 · 상세 열기는 완성된 최신 산출물 GET 만 한다(학습 · SSH · 쓰기 0). 입력이 바뀌었으면 '입력이 변경됨 · 재실행 필요'를 보인다.

지금 PC 사본(2026-10-08 하루)으로 읽기 전용 시험 실행을 했다(산출물은 scratchpad). 결과는 OK · 알림 3 · 항목 88 · 가격 관측 93 · +1 도래 후 미기록 93 · +5 / +20 미도래 93 · ML 자료 부족(대상 0행 · +5 미성숙 85 · ML 범위 밖 8)이다. 사본 파일 sha256 은 실행 전후 같았다.

## 1. 처리한 요구사항

| 항목 | 상태 | 근거 |
|---|---|---|
| 설계 §2 기반 문서 한정 예외(INTENT §9.5 · ASSUMPTIONS Q6 · POC5-00 설계 · PLAN · STATE · PROGRAM_TRUTH) | DONE | 확정문 원문 그대로 덧붙임 · 기존 문장 · 01 ~ 04 ML 미포함 · 06 별도 연구 보존 |
| 설계 §3 입력 · 대상 · 분모(02 대상 재사용 · 관측 disposition 5종 · 평가 무관 · 전달 / partial 구분 · exposure NONE 보존 · 사건 / 항목 / 가격 관측 / 신호일 / 계열 수 · 제외 사유 건수 · 시장 · 기초지수 = ML 범위 밖 + 원시 유지) | DONE | `app/alert_retro/population.py :: build, summarize, _exclusions` · `test_population_denominators_delivery_and_exclusions` |
| 설계 §4 자동 가격 사후평가(저장 결과 그대로 · MATURED 표시값 · +5 부호 문구 · 경로 일부 · 결측 상태 각각 · 0% 대체 없음 · 평가와 무관) | DONE | `population._slot · _pending` · 화면 `RetroItemRows.tsx :: priceCell, PriceFacts` · `test_price_statuses_sign_partial_path_and_no_zero_fill` |
| 판정 §3-B 가격 관측 기준일(실행 때 1회 고정 · 캘린더 + 15:30 · 미도래 / 도래 후 미기록 · snapshot · digest · GET 은 원래 보고의 두 날짜) | DONE | `report.price_asof_date` · `test_price_asof_date_follows_calendar_and_close` · `test_pending_uses_fixed_price_asof_not_signal_end_date` · `test_latest_input_check_uses_report_dates_not_clock` |
| 설계 §5 ML 입력(허용 feature · % → 비율 · 개인 손익률 제외 · 구조적 결측 유지 · 범주 NONE · 계약 버전 · price_basis 정확 비교) | DONE | `features.py` · `test_price_basis_base_must_match_exactly` · `test_unsupported_contract_version_is_not_ml_target` |
| 설계 §5 가중치 · 가중 중앙값 · 학습 구간 전처리 · Ridge · 하한 −1 | DONE | `model.py :: weights, weighted_median, Prep, _block` · 모델 시험 24건 |
| 설계 §6 시간 분리(anchor · 15거래일 × 3 · 학습 경계 · 시험 시작 · 20신호일 · 날짜 MAE · 전체 판정은 세 구간 유효 때만 · 2자리 비교) | DONE | `model.evaluate · window · verdict_of` · §8-3 변이 |
| 판정 §3-A 12-09 = 조건부 · 날짜로 실행을 막지 않음 · 유효 구간 진단 | DONE | 날짜 고정 조건 없음 · 구간별 진단 · 화면 안내에 날짜 없음 |
| 설계 §7 산출물 · 결정성 · 평가 변경 = digest 만 · 손상 = CHECK_REQUIRED · 저장 실패 = 500 + 이전 보존 · 완성된 것만 latest | DONE | `report.py :: run, _write, latest, _load_report` · 관련 시험 |
| 설계 §8 화면 · 로컬 API 2경로 · 진입 / 상세 = 조회만 · 목업 1회 → 사용자 확인 | DONE | `AlertRecordsView.tsx` · `RetroSummary.tsx` · `RetroItemRows.tsx` · `RetroResults.test.tsx` |
| 설계 §9 검증(무평가 · 분모 · 가격 상태 · 시간 누출 · 모델 비교 · 보존 · 실패) | DONE | §8 |

## 2. 변경된 파일 목록

- 신규 — 백엔드
  - `app/alert_retro/__init__.py`
  - `app/alert_retro/features.py`
  - `app/alert_retro/population.py`
  - `app/alert_retro/model.py`
  - `app/alert_retro/report.py`
- 수정 — 백엔드: `app/api_decision_ledger.py`(머리 설명 · `RetroRequest` · 2경로)
- 신규 — 화면
  - `frontend/app/components/alert_records/RetroSummary.tsx`
  - `frontend/app/components/alert_records/RetroItemRows.tsx`
- 수정 — 화면
  - `frontend/app/components/AlertRecordsView.tsx`(버튼 · 최신 조회 · 실행)
  - `frontend/app/components/alert_records/AlertCard.tsx`(상세에 사후평가 표 · `retroKey`)
  - `frontend/lib/api/decisionLedger.ts`(타입 · `runRetrospective` · `fetchRetrospectiveLatest`)
  - `frontend/app/globals.css`(ar- 블록 안 POC5-08 클래스 · 23줄 추가)
- 신규 — 시험
  - `tests/test_poc5_08_alert_retro_model.py`
  - `tests/test_poc5_08_alert_retro_report.py`
  - `frontend/app/components/alert_records/RetroResults.test.tsx`
- 수정 — 시험: `frontend/app/components/AlertRecordsView.test.tsx`(새 API 2개 mock · 진입 시 실행 0 단언 1줄)
- 문서
  - 신규: 설계서(사용자 전달 원문 + §12 판정 · 전달문) · PLAN · 이 결과서
  - 수정: `docs/PROJECT_ORIGIN_INTENT.md` · `docs/ASSUMPTIONS.md` · `docs/ai_design/POC5/POC5-00_..._DESIGN_V1.md` · `docs/ai_plan/POC5/POC5-00_..._PLAN_V1.md`(연구 예외 덧붙임) · `docs/STATE_LATEST.md` · `docs/PROGRAM_TRUTH.md`

## 3. 신규 추가된 의존성

없음(기존 scikit-learn 1.9.0 · numpy 2.4.6 · `Ridge` 는 POST 경로에서만 import).

## 4. 지시문 외 변경

1. **결측 상태 문구를 03 화면과 같게**: PRICE_MISSING = '가격 자료 없음' · UNTRACKED_AFTER_EXIT = '매도 뒤 추적 중단' · UNSUPPORTED = '지원 계열 없음'(목업 예시의 '가격 결측'과 다름). 같은 상태가 한 화면에서 두 이름으로 보이지 않게 했다.
2. **목업 안내 줄의 '12-09' 를 뺐다**: 고정 날짜는 시간이 지나면 틀린 문장이 된다(DEV_RULES 2.2). 대신 "구간마다 학습 신호일 20일 이상과 시험 행이 갖춰지면 나옵니다"로 썼다.
3. **검토 반영으로 화면 항목 추가**(설계 §3 · §4 · §6 · §8 의 '표시' 문장 대조 · 사용자 확인 목업에 없던 것):
   - 기준 날짜에 '생성 시각' 칸
   - '대상에서 뺀 항목' 줄(있을 때만)
   - 입력 변경을 확인할 수 없을 때의 노란 줄
   - 상세 접기 '가격 결과 세부' — 평가일 · 기준가 · 종가 · 경로 최고 / 최저 · 경로 종가 수 · 가격 기준 · 계산 시각(KST)
4. **분모 이름 `series` → `series_recorded`**: 결과 행이 기록된 실제 계열만 센다(`unsupported:` 제외). 미성숙 슬롯은 계열을 알 수 없어서다. 화면에는 표시하지 않는다.
5. **block 정보에 `numeric_fit` · `vocab_sizes`**: 학습 구간에서만 fit 한 변환값의 감사 기록이다. 숫자 전처리 누출 시험에 쓴다.

## 5. 알려진 한계 / 미완성

1. **산출물 크기**: report.json 은 item 마다 슬롯 3개를 담는다. 자료가 1년 쌓이면 수십 MB 가 될 수 있다. GET 은 그 파일 전체와 사본 전체(입력 변경 확인)를 한 번 읽는다. 지금 사본(88 item) 실행은 `runtime_seconds` 0.01 이다.
2. **조회 기준의 계산 범위**: GET 의 입력 변경 확인은 사본을 다시 읽어 digest 를 잰다(학습 없음). 운영 캘린더 파일이나 recipe 가 바뀌어도 '입력 변경'으로 보인다(둘 다 입력으로 취급).
3. **실데이터 ML**: 지금 사본은 신호일 1일이라 ML 은 자료 부족이 정상이다. 세 구간 전체 비교는 조건부로 가장 이르면 12-09 종료일 보고부터다(PLAN §1-4 · 판정 §3-A). 좋은 모델 수치는 종료 조건이 아니다(설계 §10).
4. **화면 실화면 확인 전**: 실제 데이터로 [사후평가 실행]을 누른 실화면은 아직이다. 실행 중인 PC 백엔드(자동 재기동)에서 `GET …/latest` = `NO_RESULT` 응답과 연구 폴더 미생성만 확인했다.

## 6. 다음 검증자(Codex)에게 알릴 점

### 6-1. 확인을 부탁할 곳

1. **판정 §3-B**: `report.run` 에서 `acquired = _now()` 는 `load_snapshot` 직전 1회다. `price_asof_date` 는 snapshot / digest / report 에 들어간다. `latest → _input_check` 는 보고 파일의 `end_date` · `price_asof_date` 로 다시 잰다.
2. **시간 경계**: `model._block` 의 학습 조건 3개(신호일 < 구간 첫날 · `at_kst(eval_date, 15:30) < test_start` · `computed < test_start`). `runtime_kst` · `computed_at` 은 시간대가 붙은 ISO 시각만 읽는다(`features.aware_time`). 읽을 수 없거나 시간대가 없으면 대체 시각을 만들지 않고 사본 손상(CHECK_REQUIRED)이다(§6-3).
3. **손상 판정 범위**(`population.check_copy`): 04 problems 를 그대로 쓰고 다음을 더했다.
   - 참조: 실행 없는 항목 · 없는 항목을 가리키는 결과
   - 중복 키 3종: 실행 · 항목 · 결과
   - 대상 항목 values_json 해석 불가
   - 실행 날짜 `runtime_date_kst` = `YYYY-MM-DD`(모든 실행)
   - 가격 결과 대상 실행: 예정 시각 `schedule_expected` = `HH:MM`(00:00 ~ 23:59 · 비어 있으면 손상) · 실행 시각 `runtime_kst` = 시간대 있는 ISO 이고 그 KST 날짜 = 실행 날짜
   - 결과 행 형식: horizon 1 / 5 / 20 · 알려진 status · 숫자 칸 · 평가일 `YYYY-MM-DD` · 문자 칸 · 계산 시각 `computed_at` = 시간대 있는 ISO
   - 모두 CHECK_REQUIRED · 산출물 없음이다. 사본이 나중에 손상되면 GET 은 기존 결과를 보이고 `input_changed=null` 이다.
4. **실행 / 조회 응답**: POST 응답과 GET 요약에는 `items` · `feedback` 이 없다. `event_id` 를 주면 그 알림 항목과 그 event 최신 평가 3칸만 준다. 메모 · action · values_json · 손익률은 어느 파일 · 응답에도 없다(시험 문자열 검사).

### 6-2. 독립 검토(2026-10-11 · 읽기 전용 · 1회) 반영

검토 판정: 시간 분리 · 가중치 · 중앙값 · MAE · 하한 · price_asof_date 결함 0. 지적 12건을 아래처럼 처리했다.

| # | 지적 | 처리 |
|---|---|---|
| 1 | 중복 키 검사가 결과 표에만 있음(실행 · 항목 중복 사본 → OK · 항목 2배) | 수정 — 실행 · 항목 중복도 CHECK_REQUIRED · 시험 2건 |
| 2 | 날짜 NULL 실행 · 문자 숫자 칸 → 500(POST · GET) | 수정 — 형식 검사 → CHECK_REQUIRED · GET 은 기존 결과 + `input_changed=null` · 시험 6건 |
| 3 | `[]` · `null` · 키 빠진 보고 파일 → 500 | 수정 — `_load_report` 형식 검사 → `ARTIFACT_UNREADABLE` · 시험 |
| 4 | 설계 '표시' 항목 일부가 화면에 없음 | 수정 — §4-3 항목 추가 · vitest |
| 5 | 신호 기간 끝 뒤 새 알림만으로 '입력 변경' | 수정 — digest 의 제외 건수에서 `after_end` 뺌 · 시험 |
| 6 | '+5 실제'와 오차의 반올림 방식 다름 | 수정 — 시험 행은 백엔드 `actual_pct` 표시 |
| 7 | 모르는 horizon · status 결과 행이 조용히 빠짐 | 수정 — 형식 손상으로 CHECK_REQUIRED(2와 함께) |
| 8 | `series` 분모가 미지원 표시 계열까지 셈 | 수정 — `series_recorded`(§4-4) |
| 9 | 숫자 전처리 누출 시험 없음(변이 생존) | 수정 — `numeric_fit` 비교 시험 · 변이 M29 검출 |
| 10 | 단언 누락(GET sklearn · 상세 실행 0 · 평가 '변경') | 수정 — 새 프로세스 sklearn 미적재 시험 · vitest 단언 · 두 번째 평가 시험 |
| 11 | 결측 표시 열을 표준화하지 않는 선택이 PLAN 문장으로 모호 | 설계자 확정(RESULT 판정 §13-2) — 현재 구현(0/1 그대로) 유지 · 코드 변경 0 |
| 12 | 입력 변경 확인 불가 때 경고 줄 없음 | 수정 — 노란 줄 |

### 6-3. 검증자 r1 REJECTED 수정(2026-10-12)

- **지적**: `schedule_expected` · `runtime_kst` · `computed_at` 을 각각 `invalid-time` 으로 바꾼 사본이 OK 산출물을 만들고 GET 이 `input_changed=false` 를 냈다. 실행 시각은 읽지 못하면 자정으로 대체됐다(B-1 fallback).
- **원인**: `check_copy` 가 시각 칸을 문자열인지만 봤다. `features.observations` 는 읽지 못한 실행 시각을 사건일 00:00 으로 대체했다. 오프셋 없는 `computed_at` 은 UTC 로 가정했다.
- **먼저 열거한 시각 소비 지점**(판단에 쓰는 곳)
  - 신호일 `runtime_date_kst`: 모집단 · 구간 · 제외 건수
  - 예정 시각 `schedule_expected`: 04 `eval_dates` 의 15:30 앞 · 뒤
  - 실행 시각 `runtime_kst`: 시험 시작 시각
  - 계산 시각 `computed_at`: 학습 경계
  - 평가일 `eval_date`: 이미 날짜 형식 검사
  - 화면 · 보고 표시용 시각(`feedback_at` · 동기화 시각)은 판단에 쓰지 않는다.
- **수정**
  - `population.check_copy` 에 `_run_ok`(§6-1-3 규칙) · 결과 행 `computed_at` 검사를 넣었다.
  - `features.aware_time` 은 시간대 있는 ISO 만 읽는다. 대체값(자정 · UTC 가정)을 모두 없앴다. 검사를 거치지 않은 입력이 오면 값을 만들지 않고 오류를 낸다.
  - 사본이 나중에 이렇게 손상되면 GET 은 기존 결과를 보이고 `input_changed=null` 이다(입력 변경을 확인할 수 없음 · 노란 줄).
- **시험**: 손상 매개변수 9건과 정상 UTC 시각 시험 1건을 더했다(신규 시험 합계 10건). 기존 정상 사본 시험에는 손상 시험의 바탕인 결과 행을 추가해 정상 처리를 확인했다.
  - 예정 시각 `invalid-time` · `25:00` · 비어 있음
  - 실행 시각 `invalid-time` · 시간대 없음 · KST 날짜 다름
  - 대상 아닌 실행의 날짜
  - 계산 시각 `invalid-time` · 시간대 없음
  - 정상 쪽: UTC 표기의 같은 시각은 OK(신규 1건) · 손상 시험 바탕 행은 OK(기존 정상 사본 시험에 추가)
- **실제 PC 사본**(읽기 전용 · 산출물 scratchpad): 강화한 검사에서도 OK · 손상 0 · 직후 GET `input_changed=False`. 지금 원장 자료는 이 형식을 모두 지킨다.
- **결과서 줄 수**: 검증자가 화면 최대 줄 수를 `RetroItemRows.tsx 244` 로 정정 · stage 한 것을 그대로 둔다.

## 7. 사용자 확인이 필요한 항목

1. **화면 추가 항목**(§4-3): 확인해 주신 목업에 다음이 더해졌다. 실화면에서 함께 봐 주시면 된다.
   - '생성 시각' 칸 · '대상에서 뺀 항목' 줄 · 상세의 '가격 결과 세부' 접기 · 입력 확인 불가 노란 줄
2. **결측 표시 열 — 설계자 확정(2026-10-12 · 설계서 §13-2)**: 숫자 2개의 결측 표시 열은 0/1 그대로(표준화 안 함) · 숫자 값 2열만 학습 구간 가중 평균 · 가중 모집단 표준편차로 표준화 · 범주 one-hot 표준화 안 함 — 현재 구현 = 고정 recipe(`model.RECIPE.numeric_transform`) · 코드 · 수치 변경 0.
3. **PC 사본 동기화**: 실화면 전에 [원장 새로고침]을 한 번 누르면 10-08 이후 자료로 볼 수 있다(선택).

## 8. 검증 실측 (2026-10-11 ~ 2026-10-12)

### 8-1. 테스트

- 백엔드 새 2파일 75 passed
  - `tests/test_poc5_08_alert_retro_model.py` 24
  - `tests/test_poc5_08_alert_retro_report.py` 51
- 관련 회귀(03 · 04 · 06 + 08 첫 판) 221 passed(검토 반영 전 · 08 지금 판은 위 75 · §8-5 전체 회귀)
- vitest 33파일 406 passed — 새 `RetroResults.test.tsx` 12 · 기존 `AlertRecordsView.test.tsx` 10(mock 2개 · 단언 1줄 추가)

### 8-2. 정적 검사

- black --check · flake8 · py_compile — 백엔드 8파일 exit 0
- tsc --noEmit exit 0 · eslint exit 0

### 8-3. 변이 시험(저장소 사본 · scratchpad/mut08)

38변이 전부 검출. 처음 28변이 중 4개가 생존했다(판정 2자리 비교 · price_basis 정확 비교 · 계약 버전 · 시험 행 평가일 ≤ 종료일). 시험을 보강해 잡았다. 검토 반영 뒤 5변이를 추가했다(M29 숫자 변환만 시험 포함 fit · M30 실행 중복 검사 삭제 · M31 결과 행 형식 검사 삭제 · M32 기간 뒤 건수 digest 포함 · M33 보고 파일 형식 검사 삭제). r1 수정 뒤 5변이를 더했다(M34 예정 시각 형식 · M35 실행 시각 시간대 없음 허용 · M36 실행 시각 날짜 일치 · M37 계산 시각 형식 · M38 대상 아닌 실행 날짜 검사 삭제).

### 8-4. 라이브 사본 읽기 전용 실행

- 실제 PC 사본(`mode=ro`) · 산출물 = scratchpad
- 결과: OK · 종료일 10-08 · 가격 관측 기준일 10-08 · 위 §0 숫자
- 직후 GET `input_changed=False` · 사본 sha256 실행 전후 같음
- 검토자도 사본 백업으로 같은 결과를 확인했다.

### 8-5. 백엔드 전체 회귀 · 라이브 보호

- `pytest tests/ -q`(caffeinate · r1 수정 뒤 최종 코드) — **3387 passed** · 1 warning(starlette httpx 안내) · 403.47s · exit 0 · 2026-10-12 07:05:47 ~ 07:12:35(r1 전 코드 = 3377 passed · 2026-10-11 23:26 ~ 23:37)
- 같은 구간 전후 PC `state/` · `logs/` 1,157파일 sha256 비교 — changed 0 · removed 0 · added 0
- 실행 중인 PC 백엔드(자동 재기동)에 `GET /decision-ledger/retrospective-evaluation/latest` 1회 — `NO_RESULT` · `state/ml/research/poc5_08/` 미생성(쓰기 0)

## 9. git 상태

커밋 전 · 변경 파일은 경로를 하나씩 지정해 stage(사용자 소유 untracked `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 만 제외). 보고 직전 `git status --short --untracked-files=all` 실측은 보고 메시지에 인용한다.

## 10. 배포 · 실화면 · 종료 기록 (2026-10-12)

- **커밋 · push**: `f1951812`(27파일 · POC5-02 · 03 종료 기록 포함 · 사용자 승인) → origin/main. OCI pull 없음(OCI 실행 파일 변경 0).
- **PC 재기동**: 사용자 · 백엔드 `uvicorn app.api:app --host 127.0.0.1 --port 8000` 시작 13:27:04.
- **실화면**(사용자 확인 2026-10-12): 「받은 알림 기록」 [사후평가 실행] 1회(13:27:20) → 「사후평가 결과」 카드 · 10-08 알림 [자세히 보기] 의 사후평가 표 · 「가격 결과 세부」 · 추가 표시 항목(생성 시각 · 대상에서 뺀 항목 줄) 확인 · 평상시 노란 경고 줄 없음.
- **산출물**(개발자 읽기 확인): `state/ml/research/poc5_08/20261012T132720892170_6b622a76/` = `report.json` · `input_snapshot.json` 2개.
  - 신호 기간 끝 2026-10-08 · 가격 관측 기준일 2026-10-08 · 사본 읽은 시각 · 생성 시각 13:27:20 · 사본 동기화 10-12 13:09:21
  - 알림 11 · 항목 482 · 가격 관측 487 · 신호일 1 · 결과 기록 계열 61
  - +1 성숙 458 · 미도래 29(15:40 보유 브리핑) · +5 / +20 미도래 487
  - 대상에서 뺀 항목 = 신호 기간 끝 뒤 285(10-12 알림) · 평가 있는 알림 1 / 없음 10
  - ML 자료 부족 · 대상 0행(+5 미성숙 479 · 이번 ML 범위 밖 8) · 세 구간 모두 '시험 행 없음'
  - report 의 입력 digest = snapshot digest · 실행 0.054초 · scikit-learn 1.9.0 · numpy 2.4.6
  - 직후 `GET …/latest` = 같은 run · `input_changed=False` · '입력 변경 없음'
  - 개인값 · 메모 · action 문자열 0(정확 문자열 검사) · `values_json` 은 recipe 설명문 1줄뿐
- **사본 불변**: 실행 뒤 PC 사본 실행 29 · 항목 767 · 가격 결과 458 · 평가 1 · 마지막 동기화 13:09:21 — 실행 전과 같다(읽기 전용 경로 `mode=ro`).
- 위 숫자는 재기동 전 같은 사본으로 한 읽기 전용 시험 실행(scratchpad)과 같다.
- 같은 코드의 실화면 통과로 **`IMPLEMENTED_VERIFIED_DEPLOYED_CLOSED` 로 종료**한다(설계자 재판정 · 검증자 재검증 없음 · 설계서 §13-6). 인계 = `docs/handoff/POC5-08_ALERT_RETROSPECTIVE_ML_EVALUATION_HANDOFF_2026-10-12.md`.
