# POC6-05 개발 결과서 — CONTINUOUS_MARKET_DATA_AND_ML_EVIDENCE_RETENTION (지속 시장 자료 수집 · ML 연구 증거 보관 연결)

작성 2026-10-22 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex) · 설계자

```text
STATUS        = IMPLEMENTED_ISOLATED — 격리 구현 · 시험(2026-10-22) → 독립 검토 1회 반영(§4-2 · HIGH 1 · MEDIUM 8 · LOW 다수)
                → 변이 47종 모두 잡힘 → 전체 회귀 4300 passed
                → 검증자 r1 REJECTED(2026-10-22 · §11 · P2 3건 = 이미 받은 사본 재검사 없음 · 공개 시각 문자열 검사 · 목록 조회 요청 상한 누락)
                → 개발자 정정(§4-3 · 같은 종류 포함) → 변이 56종(기존 47 + 정정 9) → 전체 회귀 4309 passed → 검증자 r2 VERIFIED(2026-10-22 · §12 · 격리 구현 범위) → 설계자 RESULT PASS_TO_DEPLOY(2026-10-22 · §13) → 실제 OCI 연결 대기
                → (사용자 승인 묶음 §7) 커밋 · push · OCI pull · 실제 수집 1회 · PC 가져오기 · 연구 업로드 · 복구 확인 · cron → 종료
STEP_ID       = POC6-05 지속 시장 자료 수집 · ML 연구 증거 보관 연결
DESIGN        = docs/ai_design/POC6/POC6-05_CONTINUOUS_MARKET_DATA_AND_ML_EVIDENCE_RETENTION_DESIGN_V1.md
DECISION      = docs/ai_design/POC6/POC6-05_CONTINUOUS_MARKET_DATA_AND_ML_EVIDENCE_RETENTION_PLAN_DECISION_2026-10-22.md(PASS_WITH_REQUIRED_CORRECTIONS · Q1 ~ Q4 (a))
PLAN          = docs/ai_plan/POC6/POC6-05_CONTINUOUS_MARKET_DATA_AND_ML_EVIDENCE_RETENTION_PLAN_V1.md(§11 판정 반영)
SCOPE         = 증거 보관소 · OCI 일일 수집 CLI · PC 가져오기 · 연구 등록 · 업로드 받기 · export · 복구 확인 · 상태 읽기
                + POC6-01 수집 함수의 선택 인자 capture(기본 None = PC 동작 그대로) · 기반 문서 3곳 05 한정 예외 문장
REAL_RUNS     = 아직 없음 — OCI 외부 조회 · OCI 쓰기 · 업로드 · cron 은 0 (판정 §8 · 사용자 승인 뒤)
CHECKS        = §9
VERIFIER      = r2 VERIFIED(2026-10-22 · §12 · r1 F1·F2·F3 해소 · 격리 구현 범위 · 운영 코드·시험 직접 수정 0)
```

## 0. 요약

- **무엇**: 새 학습 · 추론 · 성과 계산 없이 세 가지를 연결했다.
  1. 기존 연구 증거(POC6-02 · 03 · 04 공식 22파일)를 바이트 그대로 보관하는 경로.
  2. OCI 일일 자료 묶음을 만드는 CLI `collect-daily`.
  3. PC 가 그 묶음을 받아(`pull`) 검사 · 복구 확인 · 기준 시각 export 를 하는 경로.
- **보관소**(OCI · PC 같은 구조 · git 제외): `state/ml/evidence/`
  - 내용 해시 object(한 번 쓰면 끝) · 완료 manifest(`.partial` 뒤 이름 바꿈) · 다시 채우는 색인 · 쓰기 잠금.
  - 미완료 묶음은 읽지 않는다. 자동 삭제 · 덮어쓰기는 없다.
  - 이름과 내용이 다른(손상) object 는 지우지 않고 `.corrupt/` 에 격리하고, 같은 내용이 다시 오면 되살린다.
- **일일 수집**(OCI 09:40 매일 예정 · 독립 프로세스 · 단일 실행 잠금):
  - ETF 목록 · 네이버/FDR 120일 수신 창 — 보유 · seed 와 무관한 ETF 전체, DB 쓰기 0.
    - 새 완료 거래일이 있거나 같은 기준일 미확보분이 있을 때만 받는다.
    - 요청이 끝날 때마다 0.25초 쉰다 · 시간 초과 5회 · 실패 20회 · HTTP 403/429 즉시 멈춤 · 30분 새 요청 예산.
    - 오늘 KST 날짜 이상 행은 진행 중 봉으로 뺀다.
  - 기존 OCI 표(KRX ETF · 보유 개별주 · 지수)는 재조회 0, 최근 21거래일 delta 로 보관.
  - 08:10 · 09:20 상태 파일 · KOSPI 정정 증거 · 달력 CSV · KOSPI 저장일 목록을 실제 내용 그대로 보관.
  - 원/달러 · WTI · 코스피 수급은 POC6-01 함수 그대로 쓴다.
    - 받은 값마다 그 자리에서 object 로 확정 저장한 **뒤에** 표에 반영한다.
    - OCI DB 새 쓰기 = 두 시장 흐름 표뿐.
- **PC**:
  - `pull`: 완료 manifest 전체 대조(시각 커서 없음) · 없는 object 만.
  - `register-research` → `upload-research` → OCI `accept-upload`: 허용 실험 · 경로 · 해시만.
  - `export --as-of`: `published_at ≤ as-of` 만 · 판 이어 붙이기 없음.
  - `restore-check`: 빈 별도 경로에 복원해 같은 해시 · 목록 · 읽기 결과 확인.
  - `status [--remote]`: 목록 · 최신일 · 실패 · 연구 연결 · 두 번째 사본.
- **실제 파일 확인**(쓰기 = scratch 만): 실제 02 · 03 · 04 공식 22파일 등록 = OK, object 21, 원본 해시 · 수정 시각 불변, 복원 확인 OK(§9-5).
- **아직 안 한 것**: OCI 배포 · 실제 수집 · 연구 업로드 · cron. 판정 §8 에 따라 RESULT 판정 뒤 사용자 승인 묶음(§7)으로 한다.
- **운영 경계**: `ML_OPERATION_PROMOTION=NOT_APPROVED` · `CURRENT_DEPLOYABLE_ML_MODEL=none` · Q6 OPEN 그대로. PUSH · PARAM · 원장 · 화면 · API 변경 0.

## 1. 처리한 요구사항

| # | 요구(설계 · 판정 · PLAN §11) | 상태 | 근거 |
|---:|---|---|---|
| 1 | 기존 연구 증거 별도 보관(02 · 03 · 04 공식 22파일 · 바이트 그대로 · 내용 중복 1 = object 하나) · 실험 · 원래 대상 · 예측 · 정답 위치 · recipe 연결 · 가중치 not_saved · RETROSPECTIVE_TEST | DONE(PC 격리) | `research.register_research` · 실제 파일 확인 §9-5 · OCI 업로드는 §7 승인 뒤 |
| 2 | 봉인 KRX 판 = 참조만(경로 · 해시 · 바이트) · POC5-06 · 08 OCI 등록 제외 · 원본 보존 | DONE | `research._links` · `EXCLUDED` |
| 3 | 과거 연구 실행 commit = 미상 · 근거 종류별 기록(최초 포함 commit · 결과서 재현 · GPU code_sha256) · HEAD 대입 금지 | DONE | `STATIC.code_evidence` · `COMMON.run_commit=None` · 시험 · 변이 M32 |
| 4 | 일일 목록 = 보유와 독립 · 목록 해시 · 기준일(KST) · 분류 출처 · 추가 · 사라짐 · KRX T-1 차이 수 · 95% 미만 = 직전 목록 stale(임시 보류) | DONE | `daily._fetch_list` · `daily_naver.judge_list` · 시험 |
| 5 | 네이버/FDR 수신 창 = 증거 파일에만(운영 표 쓰기 0) · 요청 · 반환 범위 · 받은 시각 · 진행 중 봉 제외 · 61행 미만 '부족' 표시 · 가격 의미 문구 | DONE | `daily_naver.fetch_windows` · 시험 · 변이 M1 · M7 · N11 |
| 6 | 네이버 멈춤 규칙(판정 §5): 간격 0.25초 · 20초 · 연속 시간 초과 5회 · 종류 무관 20회(성공 = 초기화) · 403/429 즉시(예외 · 빈 응답 + 마지막 HTTP 상태) · 30분 = 새 요청 시작 금지 예산 · **ETF 목록 조회도 같은 20초 상한**(r1 F3) | DONE | `Limits` · `last_http_status` · 실제 FDR 경로 403 시험 · 실제 FDR 목록 경로 상한 시험 · 변이 M2 ~ M6 · N8 · R10 |
| 7 | 같은 기준일 부분 실패 → 다음 실행이 미확보분만 · 이전 판 명시 재사용 · 새 거래일 없음 = SKIPPED(이전 실패를 감추지 않음) | DONE | `daily._domestic` · 시험 · 변이 M8 ~ M11 |
| 8 | 공급자 미제공(NO_NEW_ROW) ≠ 실패 · 토요일 받은 금요일 봉 = 토요일 확보 시각 | DONE | 시험(토 · 일 · 월 09:40 · 화) |
| 9 | 기존 KRX · 지수 표 재조회 0 · 21거래일 delta(첫 실행 = 그 시점 표에 있는 최근 21개 날짜 키 전체를 한 object 로 보관 — 2014년 이후 전체 역사가 아님 · 이후 = 바뀐 날짜만) · 바뀐 날만 새 object · 이전 object 참조 · 시각 칸 = DB 마지막 쓰기 표시 · 기준일 행 없음 기록 | DONE | `daily_tables.delta` · `note_behind` · 변이 M14 · M15 · M34 |
| 10 | 날짜 축 · 이전 판을 실제로 복구 가능하게(달력 CSV · KOSPI 저장일 목록 = object · 없으면 없음 기록) | DONE | `Collector._axis` · 시험 · 복원 시험(실제 수집 묶음) |
| 11 | 원/달러 · WTI · 수급 = POC6-01 함수 + capture(표 반영 전 확정 저장 · 실패 = upsert 0) · 실패 · 미시도 사유 · 엇갈림 기록 · `capture=None` PC 동작 그대로 | DONE | `supply_fx_oil_refresh` capture · `daily_flow` · POC6-01 기존 시험 통과 · 변이 M18 · M19 · N9 · N10 |
| 12 | 상태 OK / PARTIAL / FAILED / SKIPPED_NO_NEW · 자료원별 분모 · 전부 실패 = FAILED · 무결성 실패 = FAILED | DONE | `daily.combine` · `bundle_status` · 시험 · 변이 M12 · N4 · N5 |
| 13 | 보관 구조(catalog + 내용 해시 object + manifest · 쓰기 전용 · 같은 내용 한 번 · 관측 기록 구분 · 공개 전 검사 · 덮어쓰기 없음 · 쓰기 잠금 공용) | DONE | `store.py` · 시험 · 변이 M20 ~ M24 |
| 14 | 시각 칸: observed_at = 실제 수신 · published_at(= available_at) = 잠금 · 검사 뒤 공개 순간 · imported_at · copied_at_pc = PC 공개 순간 · 원래 공개 시각 불변 | DONE | `store._publish(stamp)` · receipt 함수 · 시험 |
| 15 | PC 가져오기: 완료 manifest 전체 대조(늦게 공개된 낮은 run_id 포함) · 없는 · 손상 object 만 · **이미 받은 묶음도 매번 다시 검사**(없는 · 손상 PC object = OCI 정상본으로 되살림 · `REPAIRED` · OCI 쪽 손상 = 확인 필요 · r1 F1) · 이어받기 · 같은 id 다른 내용 = 충돌 · SSH 실패 = 기존 사본 보존 | DONE | `transfer.pull` · 시험 · 변이 M25 ~ M27 · R1 · R3 · R4 |
| 16 | 연구 업로드 = 허용 목록 전용 명령(임의 원격 쓰기 아님) · 이름 = 해시 · manifest 해시 · 허용 실험 · 허용 (실험 · 경로 · 해시) · object = 등록 파일 · OCI 에 이미 있으면 OCI 쪽 손상만 PC 정상본으로 되살림 · PC 손상 사본은 올리지 않음 · 받기 = 이미 있는 object 도 해시 확인(r1 F1 같은 종류) | DONE | `transfer.accept_upload` · `_research_problems` · 시험 8경우 · 변이 M28 · M29 · N6 · N7 · R5 · R12 |
| 17 | export: published_at ≤ as-of(**실제 해석한 UTC 시각으로 비교** · 형식 · 달력이 틀린 published_at · run_id 의 manifest 는 공개 · 목록 · export 에서 제외 · r1 F2) · FAILED · 미완료 · 손상 제외 · PARTIAL 은 실패 범위와 함께 · 판 이어 붙이기 없음 · 출력 = 새 폴더 · DB 쓰기 · 외부 조회 0 | DONE | `store.parse_iso` · `run_id_ok` · `export.py` · 시험 · 변이 M30 · M31 · R6 · R8 |
| 18 | 복구 확인 = 빈 별도 경로에 복원 · 같은 해시 · 목록 · 읽기 결과 · 실행 중 SQLite 복사 · 원본 위 복구 없음 | DONE(격리) | `store.restore_check` · 실제 수집 묶음 · 실제 연구 묶음(§9-5) · OCI 쪽은 §7 뒤 |
| 19 | 상태 읽기: 목록 · 자료원별 최신일 · 받은 시각 · 실패 · 미확보 · 연구 입력 · 예측 · 정답 연결 · 두 번째 사본 · 묶음별 없는 · 손상 object | DONE | `status.summarize` · `status --remote` · 시험 · 변이 R11 |
| 20 | 비밀 · 개인 값이 산출물 · 오류에 없음 · 학습 모듈을 불러오지 않음 | DONE | 시험(가짜 키 · 하위 프로세스 import 확인) |
| 21 | 기반 문서 3곳 05 한정 예외 문장(판정 §2 원문) · `.gitignore` · POC6-01 'PC 에서만' 주석 | DONE | §2 |
| 22 | 실제 OCI 수동 1회(소수 종목 RSS 확인 → 전체) · PC 가져오기 · 연구 업로드 · 양쪽 복구 확인 · cron · 첫 정기 실행 확인 | PENDING | 판정 §8 — 설계자 RESULT 판정 · 사용자 승인 묶음(§7) 뒤 |

## 2. 변경된 파일 목록

| 파일 | 구분 | 내용 |
|---|---|---|
| `app/ml_evidence/__init__.py` | 신규 | 패키지 설명 |
| `app/ml_evidence/store.py` | 신규 | object · manifest · 색인 · 잠금 · 검사 · 복구 확인 · 손상본 격리 |
| `app/ml_evidence/daily.py` | 신규 | 일일 수집 흐름 · 국내 단계 · 상태 |
| `app/ml_evidence/daily_naver.py` | 신규 | ETF 목록 · 네이버/FDR 수신 창 · 멈춤 규칙 |
| `app/ml_evidence/daily_tables.py` | 신규 | 기존 표 delta · 수집 기록 · 기준일 뒤처짐 |
| `app/ml_evidence/daily_flow.py` | 신규 | 원/달러 · WTI · 수급 capture |
| `app/ml_evidence/research.py` | 신규 | 연구 등록 · 허용 목록 · 미래 예측 기록 형식(생산 없음) |
| `app/ml_evidence/transfer.py` | 신규 | pull · upload-research · accept-upload · list-runs |
| `app/ml_evidence/export.py` | 신규 | 기준 시각 export |
| `app/ml_evidence/status.py` | 신규 | 상태 읽기 |
| `scripts/run_ml_evidence.py` | 신규 | CLI(하위 명령 10개) |
| `tests/test_poc6_05_evidence_daily.py` | 신규 | 일일 수집 경계 시험 |
| `tests/test_poc6_05_evidence_store.py` | 신규 | 보관소 · 연구 · 전송 · export · 복구 시험 |
| `app/supply_fx_oil_refresh.py` | 수정 | `refresh_fx_wti` · `refresh_investor_flows` 선택 인자 `capture`(기본 None) |
| `app/supply_fx_oil_store.py` · `app/kiwoom_investor_flow.py` | 수정 | 주석만('PC 에서만' → PC + 05 OCI 수집) |
| `.gitignore` | 수정 | `state/ml/evidence/` |
| `docs/PROJECT_ORIGIN_INTENT.md` · `docs/KILL_SWITCHES.md` · `docs/ASSUMPTIONS.md` | 수정 | 판정 §2 '05 한정 예외' 문장 원문 · 날짜 · 출처(기존 원문 보존) |
| `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md` | 수정 | POC6-05 항목 |
| `docs/ai_design/POC6/…_DESIGN_V1.md` · `…_PLAN_DECISION_2026-10-22.md` | 신규 | 설계 · 판정 원문(받은 파일과 바이트 같음) |
| `docs/ai_plan/POC6/…_PLAN_V1.md` | 신규 | 개발 PLAN(§11 판정 반영) |
| `docs/ai_result/POC6/…_RESULT.md` | 신규 | 이 결과서 |

- 바꾸지 않은 것: `scripts/run_oci_market_data_batch.py` · `app/market_refresh_service.py` · `app/market_data_store.py` · `app/market_data_fdr.py`(읽기 재사용) · OCI 운영 표 · PUSH · 원장.

## 3. 신규 추가된 의존성

없음(표준 라이브러리 gzip · json · hashlib · fcntl · sqlite3 · subprocess · 기존 FinanceDataReader · requests).

## 4. 지시문 외 변경 · 구현 판단

### 4-1. 구현 판단

1. **KRX 무조정 표 · 지수 표의 '시각'**: 기존 표의 `collected_at` · `created_at` 은 덮어쓸 때 바뀌는 '마지막 쓰기 시각'이다. 그대로 옮기되 "최초 확보 시각 아님"으로 표시했다. 08:10 경로(`attempt_once`)에 원응답 보관 고리를 넣지 않았다(설계 §6-3 · 08:10 경로 무변경).
2. **수급 '계획 밖 미시도'**: 기준 거래일의 KOSPI 행이 아직 없어 수급을 시도할 수 없으면(주말 · 08:10 미저장) `not_attempted_extra` 로 날짜 · 사유를 남기고 상태는 낮추지 않는다. 기존 표의 '기준일 행 아직 없음'(`behind_target`)과 같은 취급이다. 계획 안 날짜의 실패 · 미시도는 PARTIAL 이다.
3. **국내 단계 이어 쓰기**: 직전 묶음 = FAILED 가 아닌 마지막 일일 묶음. FAILED 묶음의 판은 잇지 않고 `skipped_failed_runs` 로 남긴다.
4. **손상 object**: 이름(해시)과 내용이 다르면 지우지 않고 `objects/.corrupt/` 로 옮기고, 같은 내용이 다시 오면 되살린다(`repaired_objects`). 내용 해시가 같은 값이므로 증거를 바꾸는 덮어쓰기가 아니다. 이전 판 참조는 해시 확인 뒤에만 잇고, 손상이면 그 날짜는 지금 표 값으로 다시 보관한다(`repaired_keys`).
5. **수급 · 환율 보관 단위**: 받은 값(FX 계열 하나 · 수급 날짜 하나)마다 JSON object 하나로 확정 저장한다(gzip 버퍼에 두면 디스크 오류가 표 반영 뒤에야 드러나기 때문 · 검토 §4-2 #2).
6. **목록 95% 규칙**: 응답 급감의 임시 보류로만 쓴다. 새 응답 object · 차이 수 · 사유를 남기고 상장폐지 확정으로 해석하지 않는다(판정 §6-4).
7. **첫 실연결 소수 종목**: `collect-daily --limit-tickers N` — 나머지는 '미시도(시험 제한)'로 남고 다음 실행이 같은 기준일 미확보분으로 이어 받는다.

### 4-2. 독립 검토 1회 반영(2026-10-22 · 모두 고침 · 한계로 미룬 것 없음)

| # | 수준 | 지적 | 고침 |
|---:|---|---|---|
| 1 | HIGH | 실제 POC6-03 `fetch.json` 의 `targets` = 정수(26) → 연구 등록이 TypeError 로 멈춤(시험 fixture 가 목록이라 못 잡음) | `_count`(정수 · 목록) · 연결 정보 읽기 실패는 `links.error` + PARTIAL(등록 전체를 멈추지 않음) · fixture = 실제 형식 · 실제 22파일로 확인(§9-5) |
| 2 | MEDIUM | capture 가 gzip 버퍼에만 써서 디스크 오류가 표 반영 뒤에 드러남(보관 실패인데 upsert) | 값마다 object 확정 저장(fsync · link) 뒤 반영 · 시험(확정 저장 실패 = 표 0) |
| 3 | MEDIUM | 이전 판 object 하나가 손상되면 매일 공개가 몇 주 멈춤 | 이전 판 해시 확인 · 손상 = 지금 값으로 다시 보관 · 손상본 격리 · 되살림 · 시험 |
| 4 | MEDIUM | FAILED 묶음의 판을 이어 쓰지만 export 는 FAILED 를 안 읽음 → 그날 자료가 사라짐 | FAILED 묶음을 직전으로 쓰지 않음 · 시험(같은 날 전체 다시 받음 · export 에 모두 나옴) |
| 5 | MEDIUM | 모든 확보 실패여도 날짜 축 · 수집 기록이 OK 라 묶음이 PARTIAL | 확보 자료원으로만 판정 · 날짜 축 · 수집 기록 실패는 OK 를 PARTIAL 로만 낮춤 · 시험 |
| 6 | MEDIUM | accept-upload 가 빈 experiments · 허용 밖 object 를 받음 | 허용 (실험 · 경로 · 해시) 집합 · object = 등록 파일 · 형식 검사 · 시험 2경우 추가 |
| 7 | MEDIUM | 실제 FDR 네이버 경로는 403 을 빈 표로 돌려줘 즉시 멈춤이 안 걸림 | 블록 안 마지막 HTTP 상태 기록(`last_http_status`) · 빈 응답 + 403/429 = 즉시 멈춤 · 실제 FDR 경로 시험(전송만 가짜) |
| 8 | MEDIUM | FX 받기 실패가 '미시도'로 보이고 사유가 없음 | `capture.fx_fail` · 상태 `FETCH_OR_KEEP_FAILED` · `UPSERT_FAILED`(엇갈림) · 사유 · 시험 |
| 9 | MEDIUM | status 가 설계 §7 항목(목록 · 받은 시각 · 실패 내역 · 연구 연결 · 두 번째 사본)을 안 보여 줌 | `app/ml_evidence/status.py` · `status --remote` · 시험 |
| 10 | LOW | published_at 이 잠금 · 검사 전 · observed_at 이 요청 전 · 간격 = 시작 기준 · copied_at_pc = pull 시작 · list_date = UTC · stale 의 from_run 덮음 · stale 차이 수 · KRX 차이 수 없음 | 잠금 · 검사 뒤 stamp · 응답 뒤 시각 · 요청이 끝날 때마다 0.25초 · 공개 순간 receipt · KST · 원래 from_run 유지 · 차이 수 · KRX T-1 비교 · 시험 |
| 11 | 시험 | 보유 독립 · 실제 수집 묶음 복구 · 손상 · FAILED 이어 쓰기 · 전부 실패 · 업로드 경우가 시험에 없음 | 모두 추가(보유 · 개인 값 읽기 통로를 막고 실행) |

### 4-3. 검증자 r1 정정(2026-10-22 · P2 3건 + 같은 종류 · 모두 고침)

| ID | 결함 | 같은 종류로 함께 본 곳 | 고침 | 시험 · 변이 |
|---|---|---|---|---|
| F1 | `pull` 이 PC 에 manifest 가 있는 묶음의 object 를 다시 보지 않아, 이미 받은 사본의 손상 · 삭제를 `OK` 로 끝냄 | 업로드(OCI 에 이미 있으면 OCI 손상을 안 봄) · 업로드 받기(이미 있는 object 는 존재만 확인) · `list-runs`(그 장소 손상 미표시) · `status`(손상 미표시) | `store.object_ok` · `damaged_objects` 로 통일. pull = 이미 받은 묶음도 매번 검사 → OCI 정상본으로 되살림(`REPAIRED` · rc 2) · OCI 쪽 손상은 받지 않고 확인 필요 · PC `list_runs` 문제도 보고. 업로드 = PC 손상 사본은 올리지 않음 · OCI 손상만 되살림. 받기 = 이미 있는 object 도 해시 확인. 목록 · 상태 = 손상 object 표시 | 이미 받은 사본 손상 · 삭제 → REPAIRED · 다음 pull OK · 양쪽 손상 → 확인 필요 · OCI 손상 업로드 되살림 · 받기 기존 손상 거절 · PC 손상 업로드 거절 · R1 · R3 · R4 · R5 · R11 · R12 |
| F2 | `published_at` 을 문자열인지만 보고 문자열로 as-of 와 비교(다른 시간대 · 없는 날짜가 섞이면 미래 판이 과거 export 에 들어감) | run_id 날짜 부분(정규식만) · export 정렬 · 목록 해석 | `store.parse_iso`(UTC `…Z` 마이크로초 · 실제 달력 해석) · `run_id_ok`(날짜 해석) → manifest 형식 검사 · 공개 · 목록에서 제외. export 는 해석한 시각으로 비교 · 정렬 | 4경우 parametrize(-01:00 · 0000-00-00 · 마이크로초 없음 · 없는 run_id 날짜) · 미래 판 999 미포함 · R6 · R8 |
| F3 | ETF 목록 조회가 요청 상한(20초) 밖에서 실행(FDR 목록 경로는 자체 상한 없음) | 수집기의 모든 외부 요청을 다시 봤다: 가격 = 상한 안 · Yahoo 20초 · 키움 15초 · ssh/scp 상한 있음 → 목록 하나뿐 | 목록 조회를 `request_timeout()`(기존 `fdr_request_timeout`) 안에서 실행 | 실제 FDR 목록 경로 + 가짜 전송으로 timeout=20.0 확인 · R10 |

- 이번 정정은 형식 검사를 '문자열인가'로 끝내고 비교를 문자열로 한 재발(POC6-02 r1 과 같은 종류)과, '새로 받는 것'만 검사하고 '이미 받은 것'을 다시 보지 않은 확인 범위 누락이다. 같은 종류 칸을 표의 셋째 열처럼 함께 고쳤다.

## 5. 알려진 한계 / 미완성

1. **실제 OCI 실행 전**: 외부 조회 · OCI 쓰기 · 연구 업로드 · cron 은 아직 0이다. 실제 시간 · 최대 RSS · 증가 바이트 · 네이버 응답(오늘 진행 중 봉 포함 여부) · 키움 OCI 인증은 첫 실행에서 잰다.
2. **네트워크 수신 바이트**: `network_received_bytes=null`(기존 HTTP 경계에서 셀 수 없음 · 공급자가 전체 이력을 준 뒤 자름). 보관 바이트 · 시간 · RSS 만 기록한다.
3. **KRX 원응답**: 08:10 경로가 종가 외 18칸과 원응답을 버린다. 05 는 표에 남은 종가 · 마지막 쓰기 시각만 보관한다. 원응답 보관은 08:10 경로 변경이라 하지 않았다.
4. **최근 21거래일 밖 정정**: 보존을 주장하지 않는다.
5. **확보 시각 의미**: 05 실제 수집 뒤의 `observed_at` 은 이 수집기가 받은 시각이며, 공급자의 최초 공표 시각이 아니다. 과거 연구 등록은 `imported_at`(회고 자료)이다.
6. **09:40 확보분의 쓰임**: 같은 날 08:30 판단에는 쓸 수 없다(확보 시각 규칙). 후속 비교 설계에서 판단 시각을 정할 때 참고한다.
7. **과거 연구 복원 한계**: 03 · 04 원본 안 절대경로(맥북) 때문에 다른 경로 복원본으로 기존 연구 CLI 를 무수정 재실행할 수는 없다. 04 행 단위 예측 · 02 · 04 학습 가중치는 원래 없다(not_saved).
8. **주말 묶음**: 토 · 일 실행은 국내 새 자료가 없거나(일) 수급 기준일 KOSPI 가 없어 '계획 밖 미시도'를 기록한다.

## 6. 다음 검증자(Codex)에게 알릴 점

- **잠금**: 단일 실행 · 공개 잠금은 `fcntl.flock`(PARAM 도구의 `_writer_lock` 과 같은 방식)이다. OCI cron 은 매일 한 번이고, 수동 실행과 겹치면 `BUSY`(rc 3 · 쓰기 0)다.
- **손상 object 되살림**(§4-1-4): "덮어쓰기 없음" 원칙과의 관계를 판단 근거로 적었다. 이름 = 내용 해시이므로 같은 값을 다시 쓰는 것이다.
- **수급 계획 밖 미시도**(§4-1-2): 상태를 낮추지 않는다. 계획 안 실패 · 미시도는 PARTIAL 이다.
- **POC6-01 capture 인자**: 모든 호출이 `if capture is not None` 로 막혀 있다. POC6-01 기존 시험이 그대로 통과한다(§9).
- **실제 파일 확인**(§9-5): 실제 research 파일은 읽기만 했고, 결과는 scratch 에만 썼다.

## 7. 사용자 확인이 필요한 항목 (판정 §8 · 한 번에 확인 · 이 결과서 판정 뒤)

1. 외부 조회 추가: OCI 에서 네이버 ETF 목록 · 수신 창(약 1,176종 · 새 완료 거래일마다) · Yahoo 원/달러 · WTI · 키움 ka10051.
2. DB 스키마 변경: OCI `market_data.sqlite` 에 `market_macro_daily` · `market_investor_flow_daily` 생성(POC6-01 과 같은 스키마 · 첫 수집 때 자동 생성).
3. OCI 쓰기:
   - 커밋 · push 뒤 OCI pull(거래일 08:05 ~ 15:45 피함)
   - `state/ml/evidence/` 생성 · 쓰기
   - 연구 묶음 업로드
   - crontab 한 줄: `40 9 * * * cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_ml_evidence.py collect-daily >> logs/ml_evidence_daily.log 2>&1`
4. 사용자 직접:
   - OCI `.env` 에 `KIWOOM_APP_KEY` · `KIWOOM_APP_SECRET`
   - 키움에 OCI 공인 IP 등록(키는 채팅 · 문서 · 로그로 받지 않음)
   - 등록 전 실행은 수급만 '키움 인증 정보 없음'으로 기록되고 나머지는 진행한다.

## 8. 실제 실행 순서 (승인 뒤 · PLAN §6-2 · 판정 §5 · §8)

1. 커밋 · push → OCI pull(평일이면 15:45 뒤).
2. OCI 수동 `collect-daily --limit-tickers 20` → 최대 RSS · 경과 · 증가 바이트 확인.
   - 가용 메모리 여유가 없으면 전체를 강행하지 않고 보고한다.
3. OCI 수동 `collect-daily`(같은 기준일 미확보분 = 나머지 종목) → 전체 확보 확인.
4. PC `pull` → `status --remote`(두 번째 사본) → PC `restore-check`(OCI 일일 묶음 · 빈 임시 폴더).
5. PC `register-research` → `upload-research` → OCI `restore-check`(연구 묶음 · 빈 임시 폴더).
6. 운영 불변 확인(읽기만):
   - OCI `etf_daily_price` · `etf_master` · KRX · 지수 표 행 수 · 최대 시각이 실행 전후 같다.
   - 새로 생긴 것은 두 시장 흐름 표뿐이다.
7. 사용자 crontab 한 줄 → `crontab -l` 읽기 확인 → 종료 기록.
8. 다음 날 09:40 정기 실행 = 별도 '정기 운영 확인'(다음 거래일 08:10 · 08:30 원래 배치 · 발송 확인과 함께 · 읽기 전용).

## 9. 검증 실측 (2026-10-22)

1. **정적 검사**: black --check · flake8(`app/ml_evidence` · CLI · 수정 3파일 · 시험 2파일) · py_compile 통과.
2. **KS-10**(줄 수 `wc -l` · r1 정정 뒤): store 553 · daily 511 · research 441 · transfer 438 · daily_naver 244 · daily_flow 193 · daily_tables 192 · export 184 · status 171 · CLI 216 · supply_fx_oil_refresh 293 · 시험 919 · 707(모두 기준 안 · 백엔드 근접 600 미만).
3. **시험**: `tests/test_poc6_05_evidence_daily.py` 46 · `tests/test_poc6_05_evidence_store.py` 32(`--collect-only` · r1 정정 뒤) + POC6-01 수집 시험 `tests/test_poc6_01_supply_fx_oil_sources.py` 43 = 121 모두 통과(가짜 수집기 · tmp DB · tmp 보관소 · 가짜 원격).
4. **변이 56종 모두 잡힘**(scratch 사본 · 내용 쓰기 + utime 복원 · 위 3 시험 파일 · r1 정정 뒤 코드로 47종 다시 실행 + 정정 9종):
   - 1차 34종: 진행 중 봉 · 연속 시간 초과 · 성공 초기화 · 403/429 · 시간 예산 · 간격 · 공급자 미제공 · 같은 기준일 재시도 · 판정 · 이전 판 참조 · 미확보 상태 · 전부 실패 · stale 목록 · delta · 이전 object 참조 · KOSPI 없는 기준일 · 수급 실패 · FX · 수급 capture · 손상 object · 같은 run_id · .partial · 색인 다시 채움 · 복원 참조 · pull 시각 커서 · 손상 로컬본 · manifest 해시 · 허용 실험 · manifest 밖 파일 · as-of · FAILED export · 과거 commit · 95% · KRX 뒤처짐.
   - 검토 반영 13종: targets 정수 · 이전 판 해시 확인 · FAILED 이어 쓰기 · 수집 기록 실패 반영 · 확보 자료원 판정 · 허용 파일 · 빈 experiments · 빈 응답 403 · FX 실패 사유 · 수급 확정 저장 · 응답 뒤 수신 시각 · KST 목록 날짜 · 손상 이전 판 delta.
   - 처음 살아남은 3종(M17 · N2 · N7)은 시험을 보강하거나(한 날짜만 실패 · 크기 같은 손상) 문구를 맞춘 뒤 잡혔다.
   - r1 정정 9종(R1 이미 받은 사본 재검사 · R3 REPAIRED · R4 목록 손상 표시 · R5 받기 기존 object 해시 · R6 published_at 해석 · R8 run_id 날짜 해석 · R10 목록 요청 상한 · R11 상태 손상 표시 · R12 PC 손상 업로드 거절): R12 는 처음 살아남아 시험(PC 손상 사본 업로드 거절)을 더한 뒤 잡혔다. M26 · M30 은 정정으로 바뀐 문구에 맞춰 다시 적용해 잡혔다.
5. **실제 연구 파일 확인**(scratch 출력 · 원본 읽기만):
   - 실제 02 · 03 · 04 공식 22파일 `register_research` = OK(파일 22 · object 21 · 확인 필요 0 · 원본 해시 · 수정 시각 전후 같음).
   - 연결 정보: 02 적격 4 · 제외 22 · HGB RESEARCH_PROMISING · MLP REJECT / 03 대상 26 · 봉인 판 참조 / 04 B 4종 · C 12종 · '탐색적 기준 미충족'.
   - 복원 확인 OK(object 21 · 같은 읽기 결과).
6. **전체 백엔드 회귀 1회**: `PYTHONDONTWRITEBYTECODE=1 caffeinate -i .venv/bin/python -m pytest -q -p no:cacheprovider tests/` → **4309 passed, 1 warning in 709.79s**(r1 정정 뒤 · 실패 0 · 4231 + POC6-05 78).
7. **라이브 불변**: 시험 · 확인 모두 tmp · scratch 에만 썼다(라이브 `state/` · OCI 쓰기 0).

## 10. git 상태 (검증자 r1 정정 뒤 다시 stage · 실측 2026-10-22)

`git status --short --untracked-files=all`:

```text
M  .gitignore
M  app/kiwoom_investor_flow.py
A  app/ml_evidence/__init__.py
A  app/ml_evidence/daily.py
A  app/ml_evidence/daily_flow.py
A  app/ml_evidence/daily_naver.py
A  app/ml_evidence/daily_tables.py
A  app/ml_evidence/export.py
A  app/ml_evidence/research.py
A  app/ml_evidence/status.py
A  app/ml_evidence/store.py
A  app/ml_evidence/transfer.py
M  app/supply_fx_oil_refresh.py
M  app/supply_fx_oil_store.py
M  docs/ASSUMPTIONS.md
M  docs/KILL_SWITCHES.md
M  docs/PROGRAM_TRUTH.md
M  docs/PROJECT_ORIGIN_INTENT.md
M  docs/STATE_LATEST.md
A  docs/ai_design/POC6/POC6-05_CONTINUOUS_MARKET_DATA_AND_ML_EVIDENCE_RETENTION_DESIGN_V1.md
A  docs/ai_design/POC6/POC6-05_CONTINUOUS_MARKET_DATA_AND_ML_EVIDENCE_RETENTION_PLAN_DECISION_2026-10-22.md
A  docs/ai_plan/POC6/POC6-05_CONTINUOUS_MARKET_DATA_AND_ML_EVIDENCE_RETENTION_PLAN_V1.md
A  docs/ai_result/POC6/POC6-05_CONTINUOUS_MARKET_DATA_AND_ML_EVIDENCE_RETENTION_RESULT.md
A  scripts/run_ml_evidence.py
A  tests/test_poc6_05_evidence_daily.py
A  tests/test_poc6_05_evidence_store.py
?? docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md
```

- staged 26파일(A 17 · M 9) · 오른쪽 칸 공백(unstaged 0) · r1 정정으로 바뀐 파일도 같은 26파일 안이다.
- untracked 1 = 사용자 보존 handoff(의도적 제외 · stage 하지 않음).
- `git diff --cached --check` 0건.
- 커밋 · push 없음(종료 때 사용자 승인으로 · 판정 §8 — 결과서 판정 뒤 OCI 배포 전에 커밋 · push 가 필요하다).

## 11. 검증자 r1 판정 — 2026-10-22

검증자: Codex · 적용: `.agents/skills/krx-verify/SKILL.md` · 기준 HEAD `fea10c38049e821cfc07b1c3e4c4a52235de0f0d`.
검증 범위 = staged 26파일(A 17·M 9)·unstaged 0. 사용자 handoff는 읽기·수정·stage에서 제외했다.
OCI 실행·외부 조회·업로드·cron·라이브 DB 접근은 하지 않았다. 아래 재현은 저장소 밖 index 사본·임시 보관소·가짜 원격/HTTP에서만 수행했다.

### 1) A. 기능/산출물 검증

**A-1 지시 일치: 위반 — 코드 결함 P2 3건.**

| ID | 위치(검증 시작 소스) | 발견·재현 | 계약 영향 |
|---|---|---|---|
| F1 · P2 | `app/ml_evidence/transfer.py:166`·`:173-175` | `need`는 PC에 manifest가 없는 묶음만이다. object 검사·다운로드도 그 목록에만 적용된다. 정상 pull을 한 번 마친 뒤 PC object의 첫 바이트만 바꾸거나 파일을 삭제하고 다시 pull하면, 두 경우 모두 `status=OK`, `already_local=1`, `objects_downloaded=0`, `problems=[]`이다. 같은 PC 사본의 `verify_run`은 각각 EvidenceError/FileNotFoundError를 검출한다. 원격 object는 정상이다. | 설계 §7·§9-5/6, PLAN §4-4의 손상/누락 검사와 증분 가져오기 계약 미충족. 이미 공개된 PC 사본의 손실을 정상 동기화로 보고한다. 기존 `test_pull_redownloads_corrupt_local_object`는 첫 pull 전에 object만 손상시킨 경우여서 이미 받은 manifest가 있는 경로를 검증하지 않는다. |
| F2 · P2 | `app/ml_evidence/store.py:263-264`·`app/ml_evidence/export.py:64` | 공개 시각은 문자열인지 확인할 뿐 실제 해석·UTC 형식을 확인하지 않고 문자열로 as-of와 비교한다. `published_at=2026-10-21T23:40:00-01:00`인 manifest가 정상으로 공개·읽힌다. 실제 공개 시각은 10-22 00:40Z인데, `--as-of 2026-10-21T23:50:00Z` export가 그 판의 가격 999를 포함하고 `OK`, `problems=[]`로 끝난다. `0000-00-00T00:00:00.000000Z`도 같은 검사를 통과해 정상 export에 포함된다. | 설계 §3-2·§9-3, 판정 §6-2, PLAN §11-2-4/5의 기준 시각 이후 자료 배제·손상 입력 구분 계약 미충족. `parse_as_of`가 조회 인자를 정상화해도 저장된 공개 시각의 문제가 남는다. |
| F3 · P2 | `app/ml_evidence/daily.py:395-398` | ETF 목록 조회는 `deps.request_timeout` 경계 밖에서 `list_fetcher()`를 호출한다. 기본 실제 FDR 목록 경로까지 실행하고 HTTP 전송만 가짜로 바꿔 기록한 결과 `requests.Session.request`에 timeout 인자가 없었다. 같은 조회기를 기존 timeout 컨텍스트 안에서 실행한 대조군은 `timeout=20.0`이다. 실제 설치된 FDR의 ETF 목록 경로도 `requests.get(url)`이며 자체 timeout이 없다. | 설계 §6-4·판정 §5의 기존 요청 timeout 재사용과 코드 안전성 조건 미충족. 첫 목록 응답이 멈추면 가격 단계의 시간 예산 검사에 도달하지 못하며, 단일 실행 잠금·후속 자료 보관·완료 manifest 공개가 대기할 수 있다. DNS까지 강제 종료하지 않는다는 허용과는 별개의 요청 timeout 누락이다. |

- **A-2 보고 정확성:** 파일 수·줄 수·변경 목록과 실제 연구 등록 수치는 일치한다. 다만 §1의 완료 주장 중 F1~F3 경로는 코드가 충족하지 못한다. 문서 수치 오기만으로 반려한 것이 아니다.
- **A-3 산출물 정합성: 위반.** 정상 fixture의 시험 통과와 별개로, 위 두 손상 상태가 정상 pull/export로 처리되고 목록 조회의 20초 경계가 빠져 있다. 실제 연구 등록 22파일·object 21개·복원 확인은 검증자도 정상 재현했다.
- **A-4 금지사항 위반: 없음.** 격리 구현은 판정 §8에서 허용됐다. 아직 승인 전인 실제 OCI 외부 조회·표 생성·원격 쓰기·cron을 완료한 것으로 판정하지 않는다. 신규 의존성·공개 API·화면·PUSH 변경·파일 삭제는 없다.

### 2) B. 구현 규칙/구조 품질 검증

- **B-1 fallback 위반: 있음.** F1의 누락/손상 사본과 F2의 부적합 시각을 정상 입력·완료 상태로 수용하는 경로가 있다.
- **B-2 단일 책임 위반: 없음.** 보관소·자료원 수집·등록·전송·export·상태의 책임은 분리돼 있다.
- **B-3 파일 책임 과다: 없음.** 줄 수는 §9-2와 일치한다. 신규 모듈 최대 store.py 515줄, daily.py 510줄이며 KS-10 위반이 없다.
- **B-4 실험/운영 경계 위반: 없음.** 수집·등록이 모델 학습 모듈을 불러오지 않고, `capture=None`인 기존 PC 수집 시험이 통과한다. 과거 연구를 재실행하지 않았다.
- **B-5 배포/실행 경로 영향: 없음.** CLI·모듈·시험은 모두 index 추적 경로와 일치한다. 기존 OCI 배치·러너·cron 소스는 수정되지 않았다. 실제 OCI 적용은 별도 승인·운영 확인 전이다.
- **B-6 기술부채/구조적 퇴행:** 위 결함 외 추가 위반 없음. 보관은 내용 해시와 완료 manifest를 기준으로 하며 catalog는 다시 생성할 수 있다. 기존 연구의 미상 실행 commit·미저장 가중치·봉인 DB 미전송 경계도 보존된다.

### 3) 기반 문서 준수

- 판정 §2의 05 한정 예외가 세 기반 문서에 원문과 출처를 유지해 추가됐다. 기존 금지 원문을 삭제하지 않았다.
- 신규 문서는 승인된 설계·PLAN 판정·PLAN·결과서다. MongoDB·새 UI 프레임워크·운영 ML 승격은 없다. 별도 handoff도 만들지 않았다.

### 4) 코드 안전성

- **위험 수준: MEDIUM.** F1의 사본 무결성 오판, F2의 시각 경계 위반, F3의 외부 요청 timeout 누락이 확인됐다.
- 저장소 밖 index 사본에서 관련 시험 **112 passed, 1 warning**(05 69개+01 수집 43개)을 직접 확인했다. black --check·flake8·py_compile(16파일)이 통과했다. 경고는 기존 Starlette/httpx 폐기 안내다.
- 전체 회귀 **4,300 passed**와 변이 **47/47**은 개발자의 최종 코드 근거를 재사용했다. 전체 회귀·변이 전체·과거 모델 실행은 반복하지 않았다.
- 실제 02·03·04의 지정된 연구 파일 22개로 scratch 등록을 재현했다: OK·object 21개·별도 빈 경로 복원 OK. 원본 22파일의 해시·크기·수정 시각은 전후 같다. 라이브 시장 DB·보유 파일·키·OCI는 열지 않았다.
- 검증 근거: `/private/tmp/poc605-r1-verify-wzirjk6n/`의 `related.log`, `repro605.py`·`.json`·`.log`, `repro_listing_timeout.py`, `listing-timeout-control.json`, `real-research-check.json`, 정적 검사·줄 수 기록.

### 5) 범위 폭주

- **폭주 수준: NONE.** 선택 인자 capture와 기반 문서 예외는 승인된 구현 범위다. 새 수집·배포 권한을 이번 검증이 대신 승인하지 않는다.

### 6) 종합 판정

**REJECTED — 코드 결함 P2 3건(F1·F2·F3).** 문서 수치·줄 수 불일치 때문이 아니다. 검증자는 운영 코드·시험을 수정하지 않았으며, 이 검증 기록만 결과서에 추가했다.

### 7) 사용자에게 한마디

다음은 개발자의 정정과 검증자 재검증이다. 이미 보관된 사본의 손상도 정상 pull로 끝나는 경로와 미래 공개 판이 과거 export에 섞이는 경로가 핵심이다. 실제 OCI 수집·업로드·표 생성·cron·커밋·push는 실행하지 않았다.


## 12. 검증자 r2 판정 — 2026-10-22

검증자: Codex · 적용: `.agents/skills/krx-verify/SKILL.md` · 기준 HEAD `fea10c38049e821cfc07b1c3e4c4a52235de0f0d`.
검증 대상은 staged 26파일(A 17·M 9)이며 작업 트리와 일치한다. 사용자 소유 handoff는 읽기·수정·stage에서 제외했다.
설계·PLAN·판정·결과서 및 r1 대비 변경을 대조했다. 변경 없는 부분은 §11의 검증 근거를 재사용하고, 정정 경로는 저장소 밖 index 사본에서 다시 재현했다.

### 1) A. 기능/산출물 검증

- **A-1 지시 일치: 통과.** r1 P2 3건(F1·F2·F3)이 모두 해소됐다. 같은 원인의 업로드·받기·목록·상태 및 run_id 날짜 검사도 승인된 손상 검사·시각 경계 범위 안이다.

| 지적 | 수정본 직접 확인 | 판정 |
|---|---|---|
| F1 이미 받은 사본의 손상/누락 | 정상 pull 완료 후 PC object의 동일 크기 첫 바이트 손상과 파일 삭제를 각각 재현했다. 두 경우 모두 다음 pull은 `REPAIRED`, 내려받기 1개, `verify_run=[]`이며 그 다음 pull은 `OK`·추가 내려받기 0개다. PC·가짜 OCI 양쪽을 손상시키면 `CHECK_REQUIRED`·복구 0개이고 원격/PC 손상 사유가 남는다. CLI의 `REPAIRED` 종료 코드 2도 확인했다. | CLOSED |
| F2 공개 시각의 문자열 검사·비교 | r1의 불가능한 날짜와 `-01:00` 시각은 공개 단계에서 EvidenceError로 거절된다. 이미 저장된 manifest를 같은 값으로 손상시켜도 목록에서 제외되고, export는 손상 사유를 포함한 `PARTIAL`이며 가격 999를 내보내지 않는다. 정상 UTC 과거판·미래판 대조에서는 as-of 이전 가격 100만 선택한다. 실제 날짜를 가진 run_id 검사와 시각 파싱 뒤 정렬도 확인했다. | CLOSED |
| F3 ETF 목록 요청 상한 누락 | 실제 기본 FDR ETF 목록 조회 경로를 실행하되 HTTP 전송만 가짜로 바꿨다. `requests.Session.request`에 `timeout=20.0`이 전달되고 목록은 정상 처리됐다. 실제 외부 요청은 0이다. | CLOSED |

- **A-2 보고 정확성: 통과.** staged 26개·A 17/M 9·unstaged 0 및 보고된 코드/시험 줄 수가 실측과 일치한다. 신규 운영 모듈 최대는 `store.py` 553줄이다. §4-3의 정정 설명과 실제 diff가 일치한다.
- **A-3 산출물 정합성: 통과.** 저장소 밖 사본의 관련 시험은 **121 passed, 1 warning in 30.38s**다. 05 시험 78개와 기존 01 수집 시험 43개가 포함된다. 손상 복구·시각 배제·요청 timeout의 직접 재현 결과도 코드 및 보고와 일치한다.
- **A-4 금지사항 위반: 없음.** 실제 OCI 외부 조회·쓰기·DB 표 생성·업로드·cron·커밋·push는 실행하지 않았다. 라이브 DB·보유 파일·비밀 설정도 열지 않았다. 신규 의존성·공개 API·화면·PUSH 변경은 없다.

### 2) B. 구현 규칙/구조 품질 검증

- **B-1 fallback 위반: 없음.** 이번 정정 경로에서 손상 사본을 정상 완료로 숨기거나 부적합 시각을 정상 입력으로 사용하는 문제가 해소됐다. 양쪽 손상은 확인 필요로 구분한다.
- **B-2 단일 책임 위반: 없음.** 공용 무결성·시각 검사는 store, 전송은 transfer, 내보내기는 export, 상태는 status에 둔다.
- **B-3 파일 책임 과다: 없음.** 신규 운영 모듈 최대 553줄로 KS-10 근접선 600 미만이다. 시험 파일도 919·707줄로 기준 안이다.
- **B-4 실험/운영 경계 위반: 없음.** 모델 학습·추론을 추가하지 않았다. 변경 없는 기존 PC 수집 경계와 연구 등록 근거는 r1 검증을 유지하며 관련 기존 수집 시험도 다시 통과했다.
- **B-5 배포/실행 경로 영향: 없음.** CLI·모듈·시험은 모두 index 추적 경로와 일치한다. 기존 배치·PUSH 러너·Dockerfile·cron 경로는 바꾸지 않았다. 실제 OCI 연결·운영 확인은 미완료로 유지한다.
- **B-6 기술부채/구조적 퇴행: 없음.** 이미 받은 사본을 내용 해시로 다시 검사하고, 손상본 격리와 정상본 복구를 구분한다. 공개 시각은 실제 해석한 UTC 시각으로 비교한다. 과거 연구 산출물을 새 성과로 재사용하지 않았다.

### 3) 기반 문서 준수

- 판정 §2의 05 한정 예외 및 기존 금지 원문은 r1 검증 때와 같다. 운영 ML 승격·새 프레임워크·MongoDB 도입이 없다.
- 신규 문서는 승인된 설계·PLAN 판정·PLAN·결과서뿐이다. 새 검증 문서나 종료 handoff는 만들지 않았다.

### 4) 코드 안전성

- **위험 수준: NONE(이번 격리 구현 검증 범위에서 미해결 결함 없음).** 실제 OCI 수집·네트워크 연결·배포 안전성까지 완료했다고 판정한 것은 아니다.
- 검증자가 직접 실행한 것: 관련 시험 **121 passed**; r1 손상/누락·시각 경계·실제 FDR 목록 경로 재현; **black --check·flake8·py_compile 16파일 통과**; 줄 수·Git 추적·최종 소스 일치 검사.
- 개발자의 최종 전체 회귀 **4,309 passed**와 변이 **56/56**은 근거를 재사용했다. 전체 회귀·변이 전체를 반복하지 않았다. 유일한 경고는 기존 Starlette/httpx 폐기 안내다.
- 실제 연구 등록 코드는 r1과 같아 §11의 지정 22파일·object 21개·scratch 복원 OK·원본 불변 근거를 재사용했다. 원본 연구를 재계산하지 않았다.
- 근거 폴더: `/private/tmp/poc605-r2-verify-wsivh659/` — `related.log`, `repro605_r2.py`·`.json`·`.log`, `repro_listing_timeout_r2.py`·`.log`, `listing-timeout.json`, `static-checks.json`, `lines.json`, `r1-r2.diff`, `check.json`.

### 5) 범위 폭주

- **폭주 수준: NONE.** 동일 원인의 사본 검사·시각 해석·요청 상한 보완이며 새 운영 권한이나 연구 기능을 추가하지 않았다.

### 6) 종합 판정

**VERIFIED — POC6-05 격리 구현 범위.** r1 F1·F2·F3 CLOSED. 코드·시험 직접 수정 0이며 검증자는 결과서의 상태 메타와 이 판정 기록만 갱신했다. 문서 수치 불일치로 반려하지 않았다.

### 7) 사용자에게 한마디

다음은 설계자 RESULT 판정이다. 그 뒤 §7의 사용자 승인 묶음과 실제 OCI/PC 연결 확인을 거쳐 종료한다. 이번 VERIFIED는 커밋·push·OCI 작업의 사용자 승인을 대신하지 않는다.

## 13. 설계자 RESULT 판정 원문 (2026-10-22 · `docs/ai_design/POC6/POC6-05_CONTINUOUS_MARKET_DATA_AND_ML_EVIDENCE_RETENTION_RESULT_DECISION_2026-10-22.md`)

> # POC6-05 RESULT 판정 — 지속 시장 자료 수집 · ML 연구 증거 보관 연결
>
> 작성: 설계자 · 2026-10-22 · 독자: 개발자 / 사용자
>
> **판정: PASS_TO_DEPLOY — 격리 구현·검증 범위 PASS. 사용자 승인 범위에서 실제 OCI/PC 연결 확인으로 진행한다.**
>
> 현재 POC6-05 전체가 종료된 것은 아니다. 실제 수집·메모리·인증·전송·복구·cron은 미확인으로 유지하고, 아래 조건을 완료하면 추가 설계자 재판정 없이 종료 기록을 남길 수 있다.
>
> ## 1. 근거와 열람 범위
>
> 제출 결과서 전체(359줄), 기존 DESIGN V1 및 PLAN 판정의 조건을 대조했다. 검증자 r2 VERIFIED는 **staged 26파일의 격리 구현 범위**로 수용한다. 설계자가 저장소 코드·OCI·실제 연구 원본을 직접 실행/검증한 판정은 아니다.
>
> - r1 F1 사본 재검사 누락, F2 시각 해석/비교, F3 목록 조회 timeout 누락이 r2의 직접 재현에서 모두 CLOSED다. 같은 원인의 업로드·받기·목록·상태·run_id 날짜 검사 보완도 수용한다.
> - 검증자가 직접 실행한 관련 121건·정적 검사와 개발자의 최종 전체 회귀 4,309건·변이 56/56 근거를 사용한다. 전체 시험·변이를 다시 실행하지 않는다.
> - 지정된 02·03·04 연구 파일 22개·object 21개 등록/별도 경로 읽기 복구와 원본 불변은 검증자의 r1 직접 확인 및 r2 근거 재사용을 수용한다. 실제 OCI 보관·복구까지 완료한 것으로 확대하지 않는다.
> - 기반 문서의 05 한정 예외, 새 의존성/공개 API/화면/모델 실행/PUSH 변경 없음은 보고와 검증 기록이 일치한다. 코드 안전성 NONE은 이 격리 범위의 미해결 결함 없음이라는 뜻이다.
>
> ## 2. 구현 판단·검토·정정 수용
>
> 결과서 §4-1~§4-3의 판단과 정정을 수용한다. 특히 다음 의미를 유지한다.
>
> 1. **기존 DB 시각:** 마지막 쓰기 시각을 그대로 보존하고 최초 확보/원천 공표 시각으로 바꾸지 않는다. 08:10 원응답 보관 고리를 새로 넣지 않은 선택도 승인된 배치 무변경 범위에 맞는다.
> 2. **수급 계획 밖 미시도:** 저장된 KOSPI 행이 없어서 원천 조회 계획에 들어가지 않은 날짜를 `not_attempted_extra`/`behind_target`로 남기고 실행 상태를 낮추지 않는 해석을 수용한다. 이때 OK는 계획된 실행 범위의 상태이며 **기대 기준일까지 수급이 모두 확보됐다는 뜻이 아니다.** 실제 확인 보고·후속 export의 한계에는 기대일·저장 끝일·계획 밖 날짜/사유를 함께 제시한다. 해당 날의 값을 0으로 채우거나 정상 전체 확보라고 보고하지 않는다. 이미 계획한 날짜의 실패·미시도는 PARTIAL 규칙을 유지한다.
> 3. **FAILED 판 제외:** FAILED 묶음을 국내 이어 쓰기의 직전 판으로 삼지 않고 기록으로 남기는 선택을 수용한다. 해당 object를 삭제하라는 뜻은 아니다.
> 4. **손상본 격리/복구:** 손상본을 `.corrupt/`에 남기고 hash가 일치하는 정상본으로 되살리는 것은 원래 정상 내용을 바꾸는 정정 덮어쓰기가 아니다. 양쪽이 손상된 경우 확인 필요를 유지한다. `REPAIRED`/rc 2는 복구 내역과 무결성 재검사 결과로 확인하며, 이 종료 코드만으로 외부 자료를 다시 수집하지 않는다.
> 5. **capture 저장 순서:** 값 단위로 object를 확정 저장한 뒤 최신 표에 반영하는 선택을 수용한다. 표 반영 실패와 보관 실패를 구별하고 다른 계열·기존 완료본을 보존한다.
> 6. **목록 보류/소수 실행:** 95% 규칙을 임시 보류로 쓰고 새 응답·차이를 보존한 것, `--limit-tickers` 미시도분을 다음 실행에서 잇는 방식, 요청 종료 후 0.25초 간격을 수용한다.
> 7. **공개 시각·전송:** 공개 순간 시각과 PC 수신 시각을 구분하고 실제 UTC로 해석해 as-of를 비교한 정정, 완료 목록 전체 대조, 이미 받은 사본의 무결성 재검사를 수용한다.
>
> 위 판단을 이유로 코드 재작업·과거 연구 재실행·추가 검증 단계를 요구하지 않는다.
>
> ## 3. 알려진 한계의 수용
>
> - OCI 실제 실행 전이며 시간·RSS·키움 인증·네이버 실제 응답·실제 전송은 아직 확인하지 않았다. 추정한 저장량/시간으로 실제 실행 성공을 대신하지 않는다.
> - 네트워크 수신량은 미측정(null)이다. 보관 바이트·경과 시간·RSS를 사용하며 별도 계측 기능을 추가하지 않는다.
> - KRX 보관은 기존 표에 남은 종가와 마지막 쓰기 시각 중심이다. 버려진 원응답/추가 18칸, 최근 21거래일 밖의 정정까지 보존한다고 주장하지 않는다.
> - 결과서의 ‘처음=전체’는 최근 21거래일 delta의 초기 보관 범위가 무엇인지 실제 구현에 맞게 한 문장으로 명확히 적는다. 이것을 2014년 이후 전체 역사 복구 완료로 해석하지 않는다. 문구 명확화만 하며 새 대규모 수집·코드 변경을 붙이지 않는다.
> - 09:40 확보분은 같은 날 08:30 판단의 입력이 아니다. 확보/공개 시각을 지키며, 과거 연구 등록은 회고 자료로 보존한다.
> - 학습 가중치·04의 행 예측 미저장, 원본 절대경로에 따른 재실행 한계는 그대로다. 이번 복구는 같은 파일/내용/읽기 연결 확인이며 학습 체크포인트 복원이나 모든 과거 실험의 재실행 보증이 아니다.
> - 30분은 새 요청 예산이다. 기존 DNS·느린 연속 응답의 전체 종료 미보장 한계를 유지한다. 이번 배포를 이유로 범용 timeout/감시 기능을 추가하지 않는다.
>
> ## 4. 문서 상태와 사용자 승인
>
> 1. 결과서에 본 판정 원문을 추가하고 PLAN·STATE·PROGRAM_TRUTH에는 **격리 구현·r2 검증 완료 / RESULT PASS_TO_DEPLOY / 실제 OCI 연결 대기**로 맞춘다. 아직 CLOSED나 실배포 완료로 바꾸지 않는다.
> 2. 실제 작업은 결과서 §7의 묶음으로 필요한 사용자 승인을 한 번 받는다. 기존 동일 승인 범위가 확인되면 재사용한다. 이 판정 자체는 새 커밋·push·원격 쓰기의 사용자 승인을 대신하지 않는다.
> 3. 승인 묶음에는 구현 커밋·push, OCI pull, 외부 조회/표 2개/보관 경로/연구 업로드/cron, 완료 뒤 종료 기록의 후속 문서 커밋·push까지 포함해 제시할 수 있다. 같은 작업의 승인을 쪼개 반복하지 않는다.
> 4. OCI의 기존 코드가 `e525dc37`이므로 pull에는 중간 연구 코드도 따라온다. 수집 실행이 모델 학습 모듈을 불러오지 않는 격리 검증 근거를 유지하고 torch·sklearn을 OCI에 설치하지 않는다. 실제 배포 commit을 기록한다.
> 5. 키움 키 입력·OCI 실제 외부 접속 IP 등록은 사용자가 한다. 기존 `.env` 전체를 복사하거나 키를 전달문/로그로 받지 않는다. 키를 미리 설정했더라도 별도 승인 전 수집을 시작한 것으로 간주하지 않는다.
>
> ## 5. 승인 뒤 실제 연결 확인
>
> 결과서 §8의 순서를 수용한다. 평일 OCI 배포는 기존 08:05~15:45 회피 규칙을 따른다. 예정된 POC5-04 R0와는 작업을 겹치지 않게 하되, 05의 격리 완료 기록을 그 점검의 대기로 바꾸지 않는다.
>
> 1. 승인 범위로 커밋·push·OCI pull을 진행한다. cron과 동일한 작업 경로·venv·설정에서 수동 확인한다.
> 2. `collect-daily --limit-tickers 20`으로 경과·최대 RSS·남은 메모리·증가 바이트·실패 범위를 확인한다. 시험 제한으로 인한 PARTIAL/미시도는 기대된 상태이며 전체 성공으로 쓰지 않는다. 메모리 여유가 없으면 확대를 멈추고 보고한다.
> 3. 전체 실행으로 같은 기준일의 나머지를 처리한다. 대상 목록, 실제 시도/성공/실패/미시도, 국내/해외 최신일과 확보/공개 시각, 시장 흐름 표 반영 여부를 기록한다. 정상적인 상장 이력 부족과 HTTP/인증/저장 실패를 구분한다.
> 4. PC pull·상태 읽기·일일 묶음 별도 경로 복구를 확인하고, 연구 등록·업로드·OCI 별도 경로 복구를 확인한다. 연구 22파일/21object와 원본 hash를 연결하고 최초 보관/두 번째 사본의 시점을 남긴다.
> 5. 기존 `etf_daily_price`·`etf_master`·KRX·지수 표와 기존 발송 설정이 바뀌지 않았음을 관련 범위에서 읽기 전용으로 확인한다. 새 DB 쓰기는 두 시장 흐름 표에 한정한다. 실제 OCI 연구 등록을 하지 않고 PC scratch 성공만으로 대신하지 않는다.
> 6. 매일 09:40 cron 한 줄을 추가하고 실제 등록 내용·호스트 시간대·실행 경로를 확인한다. 키움 미설정/인증 실패로 수급이 미연결된 상태는 분리 실패 처리가 작동한 증거일 뿐, 시장 흐름 전체 연결 완료는 아니다.
>
> 전체 시도가 가능하고 각 계열의 정상 자료 보관·PC 가져오기·연구 OCI 보관·복구가 확인돼야 종료 조건을 충족한다. 일부 종목의 정상적인 자료 부족이나 설명 가능한 일시 응답 실패는 분모·상태·재수집 방식을 기록한다. 이를 모든 종목/모든 날짜의 완전 확보로 확대하지 않는다.
>
> 메모리 부족·원천의 광범위한 차단/형식 불일치·키움 미연결·업로드/복구 무결성 오류·원래 운영 경로 변경/장애가 있으면 미완료 범위를 보고한다. 범위를 바꾸거나 무리하게 반복 수집해 완료로 맞추지 않는다.
>
> ## 6. 종료 기록과 첫 정기 운영 확인
>
> §5를 완료하고 새 코드 변경·미해결 결함이 없으면 **IMPLEMENTED_VERIFIED_DEPLOYED_CLOSED**로 종료 기록을 남길 수 있다. 설계자 재판정·검증자 재검증·전체 회귀·과거 모델 학습을 추가하지 않는다. 실행 중 실제 코드 결함을 수정했다면 바뀐 경계에 맞는 검사/검증으로 처리하고, 변경 없는 부분은 기존 근거를 재사용한다.
>
> 종료 기록에는 구현/배포 commit, 수동 소수/전체 실행 시각·상태/분모, RSS·바이트, PC/OCI 보관/복구 결과, 운영 불변 범위, cron과 키움 설정의 확인 여부를 적는다. 비밀값은 기록하지 않는다. 사용자의 보존 handoff는 포함하지 않는다.
>
> 첫 09:40 정기 실행은 **정기 운영 확인 대기**로 따로 표시하고, 실제 실행 로그/manifest로 갱신한다. 다음 거래일의 원래 08:10 배치·08:30 발송 확인도 그때 함께 수행할 수 있다. 일일 수집과 주말 자료 의미가 다르므로 첫 실행이 주말이면 그 날짜와 실제 확보 범위를 그대로 기록한다. 정기 실행을 아직 안 보고 운영 확인 완료라고 쓰지 않는다. 20거래일 결과 성숙을 기다리는 조건은 없다.
>
> 실제 확인을 마치면 종료 기록만 기존 문서에 반영한다. 같은 POC6 안이므로 별도 handoff 문서는 만들지 않는다.
>
> ## 7. 이후 방향
>
> 이번 완료는 **자료를 쌓고 보존본을 연구로 가져오는 연결의 완료**다. 새 모델의 일일 예측·실사용·정확도 개선·종목 선별·PC 화면 자동 최신화를 완료한 것이 아니다. 기존 02/04 판정과 운영 ML 미승격, Q6 OPEN, #3/#55/#57/#62 미완료를 유지한다.
>
> 다음 비교 설계는 보유와 독립된 평가 대상·사용자 판단 목적·기준 모델·시간 분리·재학습/예측 기록을 먼저 정한다. 그 설계 준비를 자료가 오래 쌓일 때까지 무조건 미루지는 않되, 본 판정으로 새 실험·학습·예측 작업을 자동 시작하지 않는다.
>
> **개발자 전달: 격리 구현은 PASS_TO_DEPLOY입니다. 결과서 §7의 사용자 승인 묶음을 한 번 확인한 뒤 §5의 실제 연결 확인으로 진행해 주세요. §6 조건을 충족하면 추가 재판정 없이 종료 기록을 남깁니다.**
