# POC5-04 — R0 수집 점검 · R1 원시 결과 리포트 개발 PLAN V1

```text
STEP_ID        = POC5-04
DESIGN         = docs/ai_design/POC5/POC5-04_COLLECTION_AND_RAW_OUTCOME_REPORTS_DESIGN_V1.md (설계자 2026-10-08)
BASE_COMMIT    = 1d2fc929 (POC5-01B 종료 커밋 · 코드 기준 = 4e92d0c5)
STATUS         = PLAN 확정 — 설계자 PASS_TO_IMPLEMENT(2026-10-08 · Q-A 세 표 수용 · 재제출 불필요 · 설계서 개정 1 · §7)
조사            = 설계서 §9 6항목 — 개발자 직접 확인(코드 grep · PC 사본 읽기 전용 · OCI 읽기 전용 2026-10-08)
설계자 질문      = 1건(§6 · 코드와 설계가 실제로 맞지 않는 것만)
```

## 0. 요약

설계대로 만들 수 있다. PC 수동 CLI 1개(`scripts/run_ledger_report.py r0|r1`)와 새 패키지 `app/ledger_reports/`(읽기 전용)를 둔다. 01B · 02 · 03 코드 · 화면 · API · DB · cron · SSH · 외부 조회 · 의존성 변경은 0 이다. 02 의 대상 · 예상 슬롯 · 날짜 규칙과 03 의 사본을 그대로 읽는다.

코드와 설계가 실제로 맞지 않는 곳이 1곳 있다(§6 Q-A). 원장의 `exposure` 는 전이 처리(발송 · 반복 생략 · 상한 제외)에만 매겨지고, `not_selected` 와 시장 · 기초지수 item 은 비어 있다(10-08 10:15:49 동기화 PC 사본 88개 중 **79개 NULL** · PRIMARY 9). 그래서 '주 표 = exposure PRIMARY' 와 '관측 분포에 not_selected 포함' 을 함께 만족할 수 없다.

## 1. 사실조사 (설계서 §9)

### 1-1. 원장 필드 · 02/03 대상 helper (§9-1)

| 필드 | 실제 값 · 근거 |
|---|---|
| `exposure` | `PRIMARY` · `SECONDARY` · **NULL**. `ledger_items` 가 disposition ∈ {sent · suppressed · cut_by_section_cap · cut_by_daily_cap} 일 때만 매긴다(같은 날 같은 subject · state 첫 노출 = PRIMARY · 반복 = SECONDARY). PC 사본 실측(2026-10-08 10:15:49 동기화 · 같은 사본 · `GROUP BY exposure`): 보유 `not_selected` 26 · 장중 `not_selected` 50(sector 21 · ticker 29) · 시장 `market` 1 · `index_group` 2 = **NULL 79** / 장중 sector sent 4 · cut 2 · 보유 sent 3 = **PRIMARY 9** · 합계 88 → Q-A |
| `state` | 종류별 코드 — 보유 `D5_8` · `D8_10` · `D10_PLUS`(20거래일 하락) · 장중 `D5_7` · `D7_10` · `D10_PLUS` · `U5_7` …(전일 대비) · sector `ENTRY_REVIEW` · `AVOID_DROP` · `AVOID_CHASE` · 시장 `UP` · `DOWN` · `FLAT` · NULL(not_selected 등) |
| `contract_version` | run 마다 `market_briefing.v1` · `holdings_briefing.v1` · `holdings_risk_alert.v1` |
| `series_id` · `price_basis` | `krx_etf:<t>` · `krx_stock:<t>` · `benchmark:KOSPI` · `unsupported:<t>` / `KRX_ETF_UNADJUSTED|<분류>` 등(02 `price_outcome`) |
| 시작 meta | `ledger_meta.primary_start_date`(OCI 실측 2026-10-08) · `first_active_at` · `schema_version` · 계약 버전 3키 |
| 02 대상 · 예상 슬롯 | `ledger_outcome._load_targets(con)`(FINALIZED · PRIMARY_LIVE · off 0 · evaluable 1 · subject 4종 · market 은 SP500 만) · `_expected(t)`(index_group = 3 × ticker 수 · 그 밖 3) |
| 02 날짜 규칙 | `CLOSE_CUTOFF="15:30"` · 첫날 = 15:30 이전 사건은 사건일 · 이후는 `cal.next_after` · horizon h 평가일 = `cal.days_from(첫날, 20)[h-1]` · 채우기 창 `px.FILL_WINDOW`(ETF 21 · 개별주 31) |
| 03 대상 판정 | `views.event_target` · `item_target`(화면용 · 02 와 같은 규칙) |

- 재사용: 02 의 `_load_targets` · `_expected` · `CLOSE_CUTOFF` · `HORIZONS` · 상태 상수와 `ledger_outcome_prices.Calendar` 를 import 한다(02 코드 수정 0 · 비공개 이름 재사용은 POC5-03 선례 · 결과서에 명시). 첫날 계산 3줄은 02 `_mature_target` 과 같은 식을 쓴다.

### 1-2. OCI 대조 근거 (§9-2)

- 01B 대조 CLI 출력(실측 2026-10-08 10:13): `status=OK floor=<first_active_at>` 한 줄 + `ok=N missing_in_ledger=N started_gap=N ledger_only=N` 한 줄 + 0 이 아닌 분류의 `<분류>_ids=…` 줄. **실행 시각 · 기간 끝은 출력하지 않는다.**
- **결정**: R0 는 `--reconcile-evidence <파일>` 로 개발자가 저장한 텍스트를 읽는다. 파일 첫 줄은 개발자가 같은 SSH 명령에서 찍은 `captured_at=<KST ISO>`(OCI `date -Iseconds`), 나머지는 CLI 출력 그대로다. 기간 = `[floor, captured_at]`. 01B CLI 는 바꾸지 않는다.
  - (판정 정정 · 설계 개정 1 §3) 분류 건수 줄을 읽을 수 있고 누락 · 미종료 · 원장에만 중 하나라도 0 보다 크면 → **오류 검출**(건수 · ID 보존 · `CHECK_REQUIRED` 사유 · 실제 기간 `[floor, captured_at]` 을 함께 적고, 종료일 뒤 실행까지 포함한 누적 건수를 종료일 이전 오류 건수로 표현하지 않는다). `status≠OK` 라는 이유만으로 `NOT_CHECKED` 로 버리지 않는다.
  - 근거가 없거나 · 분류 건수를 읽을 수 없거나 · `captured_at` · `floor` 가 없거나 · `floor` 가 원장 `first_active_at` 과 다르거나 · 오류 0 인데 `captured_at` 이 종료일 15:45 KST 보다 이르면(기간이 종료일을 덮지 못함) → `RUNTIME_RECONCILIATION=NOT_CHECKED`. 종료일을 덮는 더 넓은 누적 구간의 정상 결과는 수용한다.

### 1-3. 종료일 · 10완료거래일 · horizon 날짜 (§9-3)

- 캘린더: PC 에도 `state/market_meta/krx_trading_days_2026.csv` 가 있다(OCI 와 같은 운영 캘린더 · 10-09 한글날 없음). `ledger_outcome_prices.Calendar(state/market_meta)` 를 실행당 1회 만든다. 캘린더 파일이 없는 해는 02 와 같은 평일 기본(한국 거래일 계약).
- **종료일(결정)**: `--end` 가 없으면 오늘(KST)보다 **이전**의 마지막 거래일(오늘 장중 제외).
- **10완료거래일(결정 · 판정 정정)**: `D10 = cal.days_from(primary_start_date, 10)[-1]`(시작일 포함). 공식 R0 조건 = 종료일 ≥ D10 ∧ **`--ops-evidence` 의 배치 완료 근거**(종료일 종가를 적재한 가격 배치의 `price_batch_price_date` ≥ 종료일 · `price_batch_status` = success/ok · `price_batch_completed_at`) ∧ **PC 마지막 성공 동기화 시각 > 그 배치 완료 시각**(03 `ledger_sync_attempt` ok=1 마지막 행) ∧ 대조 근거 유효. 시계가 09:30 을 지났다는 사실이나 동기화 시각만으로 배치 완료를 대신하지 않는다(설계 개정 1 §3). 근거는 개발자가 기존 status · 로그를 읽어 `key=value` 줄로 제공한다(새 cron · SSH · DB · 감시 0).
  - 시작일 2026-10-08 기준 D10 = **2026-10-22**(10-08 · 12 · 13 · 14 · 15 · 16 · 19 · 20 · 21 · 22) → 공식 R0 = **2026-10-23 09:30 이후** 새로고침 · 대조 근거 수집 뒤 1회.
- horizon 평가일은 §1-1 02 규칙 그대로 계산한다.

### 1-4. 예상 슬롯 · PENDING · 다중 ticker · 전달 분모 (§9-4)

- 예상 슬롯 = 대상 item 마다 `_expected(t)`. 실제 = 사본 `price_outcome` 행. 차이 = PENDING(행 없음).
- PENDING 분류(결정 · 판정 정정): 그 슬롯의 평가일 > 종료일 → `PENDING_NOT_DUE`(평가일 미도래 · 정상 대기) · 평가일 ≤ 종료일 → `PENDING_DUE` = **'평가일 도래 · 결과 미기록(원인 미확인)'** — 정상 뒤채우기 대기로 단정하지 않고 배치 · 오류 근거와 함께 보고한다. 둘 다 결측으로 바꾸지 않는다. 계열이 아직 정해지지 않은 item(개별주 적재 차례 전)은 item 단위 대기로 센다.
- 다중 ticker: index_group 은 ticker 마다 계열 · 관측 1개. `n_event · n_item · n_price_observation · n_signal_date` 를 따로 센다.
- 전달 분모: `disposition=sent ∧ delivery_status=sent` 만 '전달된 본문 항목' · `partial` 은 별도 건수(설계 §5).
- 예정 실행 대조(R0 2번): 거래일마다 시장 `08:30` · 보유 `09:15` · `12:30` · `15:40` · 장중 `09:30 ~ 14:30` 매시 + `15:20`(= `ledger_context.MARKET_TIMES` · `SLOT_TIME_LABEL` · `INTRADAY_TICKS`) = 11 슬롯. 원장 run(상태 무관 · skipped · no_selection 포함)과 `(날짜, kind, schedule_expected)` 로 대조한다. 비거래일 기록 · `off_schedule=1` 은 별도 건수(오류 아님). 10-08 실측은 아직 sent 만 있다 — 상한 skip 회차가 원장에 남는 모양은 첫 실측(10-08 오후 이후) 뒤 fixture 에 반영한다.

### 1-5. 블록 재표집 · 분위 · 재현성 (§9-5)

- 분위: `app/ml_score_validity_metrics.py :: percentile` 이 설계 규칙과 같다((n-1)×p 선형 보간 · 빈 값 None · 1건 = 그 값) → 재사용.
- bootstrap: 같은 파일의 `circular_block_bootstrap_ci` 는 **원형**(끝 날짜 뒤에 첫 날짜를 잇는다)이고 날짜 묶음이 없다 → 설계 §6('비연속 날짜를 이어 붙이지 않음' · 같은 날짜 묶음)과 맞지 않아 재사용하지 않는다. 새 함수 = **비원형 moving-block**: 날짜 축 = 시작일 ~ 종료일의 운영 거래일 전부(알림 없는 날 = 빈 묶음) · 블록 시작 = `[0, N-b]` 균등 · `ceil(N/b)` 블록을 이어 N 날짜로 자른 뒤 그 날짜들의 성숙 관측을 모두 모아 평균. 관측 0 인 재표본이 하나라도 있으면 '계산 불가'(`RESAMPLE_UNDEFINED`)로 구간 전체를 NULL 로 두고 건수를 출력한다(정상 구간으로 위장하지 않음 · 설계 §6).
- 난수: 표준 라이브러리 `random.Random(seed)`(기존 helper 와 같은 방식 · 새 의존성 0). numpy 는 쓰지 않는다.
- 재현성: 입력 digest = 사용한 표(run · item · delivery · outcome · meta · feedback 최신) 행을 PK 순으로 정렬한 정규 JSON 의 SHA-256 + 필터 · bootstrap 설정 · report 버전. 같은 입력 · 설정이면 출력 통계가 같다(테스트로 고정).

### 1-6. CLI · 산출물 · 변경 파일 · KS-10 (§9-6)

- CLI: `scripts/run_ledger_report.py r0 [--db] [--end] [--calendar-dir] [--reconcile-evidence] [--ops-evidence] [--out-dir]` · `r1 [--db] [--end] [--calendar-dir] [--iterations 1000] [--seed 0] [--out-dir]`. `--end` 는 YYYY-MM-DD · 오늘(KST)보다 이전 · 운영 거래일만 받는다. 입력 DB 기본 = PC 사본 `state/decision/decision_evidence.sqlite`(`mode=ro` · 읽기 트랜잭션 1개).
- **산출물 위치(결정)**: 기존 PC 연구 산출물 관례 `state/ml/research/`(gitignore · PC 전용)를 따라 `state/ml/research/poc5_04/<r0|r1>_<종료일>_<생성시각>/` 새 폴더에 `report.md` · `report.json`. 기존 폴더를 덮어쓰지 않는다. DB 에는 쓰지 않는다.

| 파일 | 변경 |
|---|---|
| `app/ledger_reports/__init__.py` · `source.py`(읽기 전용 스냅샷 · digest · meta · 동기화 시각) · `dates.py`(종료일 · D10 · 평가일) · `r0.py` · `r1.py` · `bootstrap.py` · `render.py`(Markdown · JSON) | 신규 · 각 400줄 아래 목표 |
| `scripts/run_ledger_report.py` | 신규 |
| `tests/test_poc5_04_ledger_reports.py` | 신규(tmp 원장 · 고정 fixture · 라이브 DB 열지 않음) |
| `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md` · 결과서 | 갱신 |

- 01B · 02 · 03 모듈 · 테스트 · `conftest` · 화면 변경 0(조사 기준).

## 2. 구현 계획 (판정 뒤)

### 2-1. R0

1. OCI 대조(§1-2) — 근거 파일 요약 · 기간 · 분류 건수 · ID.
2. 예정 실행(§1-4) — 거래일 × 11 슬롯 대조 · 누락 슬롯 키 · 비거래일 · 예정 외 건수.
3. 무결성 — orphan item · delivery · outcome · FINALIZED ⇒ delivery 1 · STARTED ⇒ item · delivery 0 · STARTED 잔류 · cohort × contract_version 건수.
4. 가격 결과 — 예상 슬롯 · 상태별 건수(MATURED · T0_MISSING · PRICE_MISSING · UNTRACKED_AFTER_EXIT · UNSUPPORTED_PRICE_SOURCE) · `PENDING_NOT_DUE` · `PENDING_DUE`.
5. 운영 대조 — `--ops-evidence` 텍스트(개발자 읽기 전용 확인 · 배치 status · 원장 오류 건수)를 요약해 함께 싣는다. 본문 · 비밀값은 싣지 않는다.
6. 판정: `NOT_READY`(10완료거래일 · 배치 · 동기화 조건 미충족 · 시작 meta 없음 · 대조 `NOT_CHECKED`) / `CHECK_REQUIRED`(공식 조건 충족 ∧ 대조 누락 · 미종료 · 원장에만 · 누락 슬롯 · orphan · 관계 오류 중 하나라도) / `COLLECTION_OK`. 자동 수정 · 재생성 0.

### 2-2. R1

- 표본: §5 그대로 + Q-A 판정 반영(PRIMARY 주 표 · SECONDARY 보조 표 · NONE 별도 표 · 표시 문구 '노출 분류 없음' · 원장 NULL 그대로). 제외 사유 건수(LEGACY · off_schedule · evaluable=0 · subject 대상 아님 · market 이 SP500 아님).
- 그룹 = `push_kind · subject_kind · state · contract_version · price_basis · horizon` × exposure 구분 × (관측 / 전달). partial 은 그룹 축이 아니라 모집단 건수(`partial_sent_items`) 하나로 낸다. 시장은 SP500 state 옆에 KOSPI 결과.
- 그룹 · horizon 마다: 성숙 건수 · 상태별 건수 · PENDING 건수 · 평균 · 중앙값 · 25/75 분위 · 최소 · 최대 · `max_up_raw` · `max_down_raw` 중앙값 · `n_event · n_item · n_price_observation · n_signal_date` · bootstrap 평균 95% 구간(또는 `INSUFFICIENT_SAMPLE` · 서로 다른 성숙 사건 날짜 < 2 × max(5, h)).
- 평가: 평가 있음 · 없음 event 건수와 최신 평가 분포만 부가 표. 표본 · 통계는 평가와 무관(테스트: 평가 추가 · 삭제 전후 통계 동일).
- 성공 임계 · 양수 비율 · 방향 채점 · 색 · 배지 0.

## 3. 검증 계획 (줄인 방식)

| 수용 기준 | 확인 |
|---|---|
| 1 | tmp 원장 fixture: 정상 · 슬롯 누락 · STARTED · orphan · 대조 근거 없음(NOT_READY) · **유효한 오류 대조(CHECK_REQUIRED)** · 기간 미달 · 10거래일 미달 · **배치 근거 없이 09:30 경과만(NOT_READY)** · 배치 완료 전 동기화 → 판정 |
| 2 | +20 미도래 · 채우기 창 안 대기 → PENDING_NOT_DUE / PENDING_DUE · 결측 0 |
| 3 | 다중 ticker · PRIMARY/SECONDARY/NULL · 관측/전달 · partial · LEGACY · off_schedule 분모 고정 fixture |
| 4 | 평가 0 · 1 · 2행 전후 R1 원시 가격 표본 · 통계 · bootstrap 값 같음 · **입력 digest 와 평가 부가 표는 달라질 수 있음**(digest 는 최신 평가를 포함 · 설계 개정 1 §2) · 실행 뒤 `user_feedback` 행 수 불변 |
| 5 | 알려진 값 평균 · 분위 · max_up/down · 같은 seed 결과 동일 |
| 6 | 날짜 묶음(같은 날 관측 함께 이동) · 비원형 블록 · 빈 날짜 보존 · 소표본 NULL |
| 7 | 실행 전후 입력 DB sha256 · 라이브 state/logs 해시 · SSH · Telegram · 외부 조회 0(AST import 검사) |
| 8 | black · flake8 · py_compile · KS-10 `wc -l` · 마지막 전체 회귀 1회 |

- 검토는 코드 + 문서 1회.

## 4. 문서 · 배포

- PROGRAM_TRUTH(§4 진입점 · §11 분류 · 부록 A) · STATE · 결과서 `docs/ai_result/POC5/POC5-04_COLLECTION_AND_RAW_OUTCOME_REPORTS_RESULT.md`.
- PC 도구라 OCI pull · cron · `.env` 변경 0. 개발 종료 = 구현 · 검증(설계 §10 · 표본 누적을 기다리지 않음). 공식 R0 는 2026-10-23 09:30 이후 개발자가 1회 실행해 별도로 보고한다.

## 5. 사용자 확인 항목

- 없음(화면 없음 · 리포트는 개발자가 실행).

## 6. 설계자 질문 (코드와 설계가 실제로 맞지 않는 것만)

**Q-A. R1 '주 표 = exposure PRIMARY' 와 '관측 분포 = sent · suppressed · cut · not_selected'**

- 사실: 원장 `exposure` 는 전이 처리 4종에만 매겨진다. `not_selected` · `data_unavailable` 과 시장(`market` · `index_group`) item 은 NULL 이다(10-08 10:15:49 동기화 사본 88개 중 79개 · 정정). 그래서 PRIMARY 만 주 표에 두면 관측 분포의 not_selected 와 시장 브리핑 결과가 모두 빠진다. 설계는 exposure 를 다시 계산하지 말라고 한다(맞다 — 다시 계산하지 않는다).
- 추천: exposure 를 세 구분으로 그대로 표시한다 — **`PRIMARY`(주 표) · `SECONDARY`(보조 표) · `NONE`(노출 분류 대상 아님 · 별도 표)**. 관측 분포 · 전달 분포는 세 표 각각에 둔다. not_selected 와 시장 item 은 `NONE` 표에서 보인다. 같은 날 같은 subject 가 여러 회차(09:15 · 12:30 · 15:40)에 반복 관측되는 것은 `n_item` · `n_signal_date` 로 드러나고, bootstrap 은 날짜 묶음이라 같은 날 반복이 독립 표본으로 부풀지 않는다.
- 대안: `NONE` 을 주 표에 합친다(PRIMARY ∪ NONE). 이 경우 노출 분류를 받은 행과 받지 않은 행이 한 표에 섞인다.

## 7. 설계자 판정 반영 (2026-10-08 · PASS_TO_IMPLEMENT · 원문 = 설계서 끝)

- Q-A 수용: PRIMARY · SECONDARY · NONE('노출 분류 없음') 세 표 · 재계산 · NULL 변경 없음 · not_selected · 시장 · 기초지수 NULL 대상도 NONE 표에 포함.
- 정정 반영(위 본문을 그 자리에서 고쳤다): §1-2 오류 대조 = `CHECK_REQUIRED`(status≠OK 만으로 버리지 않음) · §1-3 공식 R0 = 실제 종료일 배치 완료 근거 + 그 뒤 동기화 사본(09:30 경과 대체 불가) · §1-4 `PENDING_DUE` 원인 미확인 표시 · §3 평가 변경 시 digest 변화 허용 · 원시 통계 동일 · §0 · §1-1 NULL 79(78 은 덧셈 오류 · 같은 사본 10:15:49 재집계).
- 공식 R0 = 2026-10-23 09:30 이후 별도 1회. 04 개발 종료는 이 날짜를 기다리지 않는다.

## 8. 구현 중 확정 · 정정 (2026-10-08 · 개발자 독립 검토 1회 반영 · 결과서 §6-2)

- 날짜 축: `Calendar.days_from` 이 120 달력일까지만 걸어 긴 기간이 잘렸다 → 하루씩 직접 걸으며 `is_trading` 으로 거른다(긴 기간 테스트).
- 대조 근거 순서: 건수 줄 → `captured_at` · `floor` 존재 → `floor = first_active_at` → 오류 검출(`ERRORS`) → 기간이 종료일을 덮는지. 다른 원장 · 시작 불일치 근거는 오류 건수가 있어도 `NOT_CHECKED`(설계 §3 '시작 · 기간 정보를 확인할 수 없으면').
- 운영 근거: `price_batch_price_date` 는 엄격한 YYYY-MM-DD · **`ops_error_count`(개발자가 확인한 배치 · 원장 · PUSH 오류 건수) 필수** — 없으면 `NOT_READY` · > 0 이면 `CHECK_REQUIRED`(설계 §3 '확인된 배치 · 운영 오류 … 실제 오류를 COLLECTION_OK 로 처리하지 않는다'). 메모 줄은 비밀값 단어가 들면 통째로 가리고 32자 이상 토큰은 `[가림]`.
- R0 운영 실패(원장 기록): 기간 안 실행 `status=failed` · 전달 `failed` · `partial` → `CHECK_REQUIRED`(같은 설계 문장 · 설계자 확인 대상 — 결과서 §6).
- 무결성: 대상이 아닌 item(LEGACY · evaluable 0 등)에 붙은 outcome(`outcome_on_non_target`)도 점검 필요.
- 종료일 경계: 평가일이 종료일 뒤인 결과 행은 R0 · R1 모두 '그 종료일 기준 미도래' 로 센다(`dates.rows_known_by`).
- R1 제외: 기간 밖 item 을 `before_primary_start`(LEGACY 는 시작일 전 실행이라 여기) · `after_end` 로 센다.
- Markdown 표 칸의 `|` 이스케이프 · 알 수 없는 exposure 값은 별도 표(멈추지 않음) · 날짜 축 밖(비거래일) 성숙 관측 건수 `n_matured_outside_axis`.

## 9. 검증자 r1 정정으로 바뀐 계약 (2026-10-08 · 변경점만)

- 입력: PC 사본 필수 표(원장 4 + PC 전용 2)가 없거나, `schema_version.price_outcome` 기록이 있는데 `price_outcome` 이 없으면 '입력 사본 손상' — 빈 자료로 받지 않는다. R0 = 다른 조건과 무관하게 `CHECK_REQUIRED` · R1 = 통계를 만들지 않고 CLI exit 3.
- bootstrap 반복 횟수는 1 이상만(CLI · 함수 둘 다).
