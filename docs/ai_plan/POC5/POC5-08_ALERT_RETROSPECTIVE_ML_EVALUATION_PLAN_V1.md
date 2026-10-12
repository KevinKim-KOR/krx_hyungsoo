# POC5-08 — 알림의 ML 사후평가 개발 PLAN V1

작성 2026-10-11 · 작성자: 개발자(VSCode Claude) · 수신: 설계자(웹 GPT)

```text
STATUS        = PLAN 확정 — 설계자 PASS(2026-10-11 · 재제출 없음 · 보충 A ~ C 반영 = §7)
DESIGN        = docs/ai_design/POC5/POC5-08_ALERT_RETROSPECTIVE_ML_EVALUATION_DESIGN_V1.md (V1 · §12 PLAN 판정 원문 · 끝에 전달문 원문 2건)
BASE_COMMIT   = 8ac6f41f
QUESTIONS     = 없음 — 설계와 충돌하는 코드 · 자료 사실 없음(§6). 정해 둔 세부는 §2-6(판정에서 바꿀 수 있음)
API           = 로컬 2경로(설계 §8 그대로 · 기존 decision-ledger router)
OCI           = 변경 0(OCI 에서 도는 파일 · cron · .env 변경 없음) → OCI pull 불필요
FULL_3BLOCK   = 전체 3구간 비교의 가장 이른 보고 종료일(조건부) = 2026-12-09(§1-4) — 고정 실행 금지 조건 아님 · 실행마다 실제 유효 표본으로 판단 · 그 전에도 가격 평가 · 유효 구간 진단 제공
```

## 0. 요약

「받은 알림 기록」 머리에 큰 버튼 **[사후평가 실행]** 을 둔다. 누르면 PC 원장 사본을 04 리포트와 같은 방식(`mode=ro` · 읽기 트랜잭션 1개 · 손상 판정)으로 한 번 읽어 메모리 snapshot 을 확정한다. 그 snapshot 으로 다음 세 가지를 만든다.

1. **자동 가격 사후평가**: 저장된 +1 / +5 / +20 결과를 그대로 쓴다.
2. **+5 고정 Ridge 시간 분리 검증**: 날짜 균형 가중치로 학습하고, 가중 중앙값 기준과 같은 행에서 비교한다. 세 구간 × 5거래일이다.
3. **사용자 평가 표시**: 별도 근거로, event 최신 1건만 쓴다.

결과는 `state/ml/research/poc5_08/<생성시각>_<id>/report.json · input_snapshot.json` 에 쓴다. 조회(GET)는 완성된 최신 산출물을 읽기만 하고, 사본이 바뀌었으면 '입력이 변경됨 · 재실행 필요'를 함께 보인다. 평가가 없는 알림도 그대로 쓰고, 평가는 어떤 필터에도 들어가지 않는다.

## 1. 사실조사 (설계 §9 의 6항목)

### 1-1. 원장 · 결과 · 평가 스키마와 helper (PC 사본 실측 · 2026-10-11 · 읽기 전용)

- 사본 `state/decision/decision_evidence.sqlite`: `evaluation_run` 3 · `signal_item` 88 · `delivery` 3 · `ledger_meta` 8 · `price_outcome` 0 · `user_feedback` 1 · `ledger_sync_attempt` 3. 마지막 동기화 2026-10-08(10-08 하루치 · 그 뒤 동기화 안 함 — 사용자가 [원장 새로고침]을 누르면 갱신).
- `signal_item`: event_id · item_seq · subject_kind · subject_id · held · state · prev_state · disposition · event_type · exposure · values_json · t0_price · t0_price_asof · evaluable. `evaluation_run`: push_kind · contract_version · runtime_kst · runtime_date_kst · schedule_expected · off_schedule · cohort · run_state 등. `delivery`: delivery_status(sent / partial / …).
- `price_outcome`(02): event_id · item_seq · series_id · horizon · t0_price · eval_date · eval_price · return_raw(소수 비율) · max_up_raw · max_down_raw · path_points · price_basis · status(MATURED · T0_MISSING · PRICE_MISSING · UNTRACKED_AFTER_EXIT · UNSUPPORTED_PRICE_SOURCE) · computed_at(UTC `now_utc()`). PENDING 은 행이 없다.
- `user_feedback`: event_id · feedback_seq · helpfulness · action · memo · feedback_at.
- **재사용할 helper**(코드 변경 0):
  - `app/ledger_reports/source.py :: load_snapshot` — mode=ro · 읽기 트랜잭션 1 · `REQUIRED_TABLES` 손상 판정(`problems`) · 02 `_load_targets` 같은 트랜잭션 실행 · event 최신 평가.
  - `app/ledger_reports/dates.py` — `calendar` · `default_end`(KST 오늘 이전 마지막 거래일) · `validate_end` · `eval_dates`(15:30 규칙) · `parse_kst` · `at_kst`.
  - `app/ledger_reports/r1.py` — 미도래 / 도래 후 미기록 구분 방식.
- **series 연결**: ticker 종목 = `krx_etf:` · `krx_stock:` / sector = 기록된 대표 `krx_etf:` / market = `benchmark:KOSPI` / index_group = 구성 ETF 마다.
- **price_basis**: `KRX_ETF_UNADJUSTED|<종목 구분 출처>` · `KRX_STOCK_UNADJUSTED|<종목 구분 출처>`(예: `etf_master_csv` · `etf_master_csv+krx_table` — `app/runtime_evidence/holdings_price_basis.py` · 2026-10-12 실데이터로 표현 정정) · `KRX_ETF_UNADJUSTED`(sector) · `KRX_KOSPI_INDEX`.

### 1-2. feature 두 숫자(키 · 부호 · 단위 · 적용 kind · 결측 · 계약 버전)

| push_kind / subject_kind | 판정 입력(state 를 정한 값) | 20거래일 변화 | 당일 변화 | 사본 실측 |
|---|---|---|---|---|
| holdings_briefing / ticker | 최근 20거래일 하락 단계(D5_8 등) = `return_20d_pct`(`ledger_items.holdings_briefing_items` ← `return_pct`) | `return_20d_pct` | 없음(구조적 결측) | 29 / 29 값 있음 |
| holdings_risk_alert / ticker | 급락 / 급등 단계 = `day_return_pct`(← `day_return`) | 없음(구조적 결측) | `day_return_pct` | 29 / 29 |
| holdings_risk_alert / sector | 사업군 신호 | `return_20d_pct` | `day_return_pct` | 27 / 27 |
| market_briefing / market · index_group | — | ML 범위 밖(설계 §3) | — | 원시 결과만 |

- 단위는 퍼센트(8.8 = +8.8%) → **÷ 100 해서 비율로 맞춘다**(라벨 return_raw 와 같은 단위). 부호는 + = 상승.
- `profit_loss_pct`(보유 손익률 · 개인 매입가 대비)·`drawdown_*`·`return_5d_pct`·`rank`·`base_close` 등 **다른 키는 쓰지 않는다**(설계 허용 목록 밖 · 개인값 포함).
- 계약 버전(사본 meta): `holdings_briefing.v1` · `holdings_risk_alert.v1` · `market_briefing.v1` 각 1개 — 지원 = 이 버전들. 다른 버전이 나오면 '지원 안 되는 계약 버전' 사유로 ML 에서 빼고 건수를 남긴다(가격 평가는 유지).
- 범주 값(사본 실측): push_kind 2(ML 대상) · subject_kind ticker / sector · state NULL · D5_8 · AVOID_DROP · ENTRY_REVIEW 등 · event_type NULL / new_entry · exposure NULL / PRIMARY · held 1 / NULL. NULL = 명시적 'NONE'.

### 1-3. 시각 경계 · 날짜 fixture

- **신호일** = `runtime_date_kst`. **+h 평가일** = 04 `eval_dates`(사건 `schedule_expected` < 15:30 이면 사건일 종가가 +1 · 이후(15:40 등) = 다음 거래일부터) — 02 와 같은 식.
- **학습 가능 조건**(설계 §6-1): `at_kst(eval_date, "15:30") < 시험 구간 시작 시각` 그리고 `parse(computed_at) < 시험 구간 시작 시각`(UTC → 시간대 비교).
- **시험 구간 시작 시각** = 그 구간 ML 시험 행 가운데 가장 이른 사건의 `runtime_kst`(§2-6-1).
- 02 는 OCI 08:10 · 09:20 배치에서 결과를 쓴다. 그래서 아침 사건의 +5(평가일 = 사건일 + 4거래일)는 평가일 다음 거래일 08:10 쯤 계산된다 → 학습에 들어가는 신호일은 대략 '시험 시작일 − 5거래일' 이전.
- **시험 fixture**:
  - 15:30 앞 · 뒤 사건(09:15 · 15:40)
  - 같은 날 여러 행(브리핑 · 장중 · 대표 ETF 중복)
  - computed_at 이 늦게(평가일 몇 주 뒤) 기록된 과거 라벨
  - UTC / KST 표기 섞임
  - 휴장일(2026 캘린더 파일)

### 1-4. 지금 건수 · 모델 가능 날짜

- 지금 사본: 신호일 1일(2026-10-08) · ML 대상 item 85(보유 브리핑 종목 29 · 장중 종목 29 · 사업군 27) · price_outcome 0 → 실행하면 가격 사후평가 = 전부 미기록(미도래 / 도래 후 미기록 구분) · ML = 자료 부족.
- **전체 3구간 비교의 가장 이른 보고 종료일(조건부 · 운영 캘린더 계산)** = **2026-12-09**:
  - 학습 신호일 20일 = 10-08 ~ 11-05
  - 첫 시험 구간 시작 11-12
  - anchor 12-02
  - 그 +5 결과가 12-10 08:10 에 계산되고, 그 뒤 PC 사본을 동기화해야 한다.
- 이 날짜는 매 거래일 ML 대상 행이 있고, +5 가 정상 성숙하며, 사본이 그때까지 동기화된다는 가정의 하한이다(실제 실행은 12-10 배치 · PC 동기화 뒤). 날짜로 실행을 막지 않는다 — 그 전에도 학습 신호일 20 · 시험 행이 갖춰진 구간은 구간별 진단을 내고, 세 구간이 모두 유효하지 않으면 전체 비교 없이 DATA_SHORT + 구간 진단(판정 §3-A).

### 1-5. 실행 시간 · 설치 버전

- scikit-learn 1.9.0 · numpy 2.4.6(기존 고정 버전 · 추가 설치 0).
- 임시 1만 관측 × 24열(one-hot + 숫자 + 결측 표시) · 세 구간 `Ridge(alpha=1.0, solver="svd").fit(sample_weight=…)` + 예측 = 0.02 ~ 0.03초. 사본 읽기 · 산출물 쓰기를 더해도 몇 초 안(동기 POST 로 충분).

### 1-6. 파일 · API · 목업 · 시험 · KS-10

- **새 패키지 `app/alert_retro/`** — 01B ~ 06 의 원장 · 성숙 · 동기화 · 평가 저장 · 기존 모델의 계약 / 처리 변경 0. 03 화면(View · Card)과 router(`app/api_decision_ledger.py`) · API client 는 08 용으로 확장(설계 §8 승인 범위 · 판정 §3-C):
  - `population.py` — snapshot → 관측 모집단 · 분모 · 전달 · 노출 · 가격 상태
  - `features.py` — 허용 feature · 단위 · 계약 버전
  - `model.py` — 가중치 · 가중 중앙값 · 학습 구간 전처리 · Ridge · 세 구간 · 날짜 MAE
  - `report.py` — 실행 · digest · 산출물 · 최신 조회 · 입력 변경 판정
  - 각 400줄 이하 목표
- **API**: `app/api_decision_ledger.py`(181줄)에 2경로 추가.
- **화면**:
  - `AlertRecordsView.tsx`(177): 머리 버튼 + 결과 영역 → 새 `alert_records/RetroSummary.tsx`
  - `AlertCard.tsx`(152): 상세에 항목별 결과 → 새 `alert_records/RetroItemRows.tsx`
  - `frontend/lib/api/decisionLedger.ts`(165): 타입 · 함수
- **목업**: backend 구현 중 결과 영역(요약 + 알림 상세 항목 한 줄) 작은 목업 1회.
- **시험**: 새 백엔드 2파일(모델 · 모집단) · vitest 1파일. KS-10 트리거 없음 예상(최대 화면 파일 ≈ 230 · 백엔드 ≈ 400). 기존 647줄 시장 흐름 모듈은 건드리지 않는다.

## 2. 구현 계획

### 2-1. 실행(POST) 순서

```text
1 입력   end_date(선택 · YYYY-MM-DD · 04 validate_end — 오늘 이전 거래일만) · 없으면 04 default_end = 신호 기간 · ML 구간의 상한
         (결과를 그날 상태로 되돌리지 않음) · snapshot 획득 시각(KST) 1회 고정 → price_asof_date = 그 시각 기준 마지막 종가가 끝난
         거래일(획득 시각 ≥ 그날 15:30 이면 그날 · 아니면 직전 거래일 · 운영 캘린더) — 연구 입력 기준일(DB 에 쓰지 않음)
2 읽기   04 load_snapshot(사본) — 파일 없음 = NO_COPY(정상 · 산출물 없음) · problems = CHECK_REQUIRED(원인 · 산출물 없음)
         · 같은 (event_id, item_seq, series_id, horizon) 중복 · 없는 item 을 가리키는 결과 = CHECK_REQUIRED
3 모집단 02 대상(FINALIZED · PRIMARY_LIVE · off_schedule 0 · evaluable 1) — 신호일 ≤ 보고 종료일 · 평가 · 전달 · 노출과 무관
         · 분모: 사건 · 항목 · 가격 관측 · 신호일 · series 수 따로 · 제외(LEGACY · 예정 외 · evaluable 0 · 대상 아님) 사유 건수
4 가격   (event, item, series, horizon) 결과 그대로 · MATURED 표시값 · 저장된 결측 상태 그대로 · 결과 없는 슬롯 = 평가일(04 eval_dates)
         이 price_asof_date 보다 뒤 = 미도래 · 같거나 앞 = 도래 후 미기록(공개 · 보강 대기 포함 — 그 사실만으로 오류 · PRICE_MISSING
         으로 바꾸지 않음 · 판정 §3-B) ·
         +5 성숙이면 '+5 종가 상승 / 하락 / 변화 없음'(저장 원시값 부호) · 경로 일부 = path_points < horizon
5 ML     대상 = 보유 브리핑 / 장중의 ticker · sector 중 price_basis 의 `|` 앞이 KRX_ETF_UNADJUSTED · KRX_STOCK_UNADJUSTED 와 같은
         +5 MATURED 행 · 지원 계약 버전 · 세 구간 시간 분리 검증(§2-2)
6 저장   임시 폴더에 report.json · input_snapshot.json 을 다 쓴 뒤 이름 바꾸기(06 과 같음) · 실패 = 실행 실패(500) · 이전 산출물 보존
```

### 2-2. 모델(설계 §5 · §6 그대로)

- 라벨 y = +5 MATURED `return_raw` · 관측 키 = event_id + item_seq + series_id.
- **가중치**: 같은 신호일의 서로 다른 series 수 S · 그 날 같은 series 유효 행 수 N → w = 1 / (S × N)(날짜 합 1). 학습 · 시험 집합마다 그 집합 안에서 다시 확정.
- **가중 중앙값**: y 오름차순 · 누적 가중치 ≥ 총합 / 2 인 첫 값.
- **전처리(학습 구간에서만 fit)**:
  - 숫자 2개 → 결측 표시 2개 + 대입(학습 유효값의 가중 중앙값 · 유효값 0 이면 0) → 가중 평균 · 가중 모집단 표준편차로 표준화(상수 열 = 0).
  - 범주 6개 → 학습 사전 dense float64 one-hot(표준화 안 함 · 시험의 처음 보는 값 = 그 묶음 0 벡터 + 건수).
- **모델**: `Ridge(alpha=1.0, solver="svd", fit_intercept=True).fit(X, y, sample_weight=w)` · 예측 하한 −1(상한 없음 · 라벨 자르지 않음).
- **구간**:
  - anchor = 보고 종료일의 5거래일 전(운영 캘린더)
  - anchor 로 끝나는 15거래일을 5일씩 3구간(사건 없는 날도 날짜로 남김)
  - 시험 = 그 구간 신호일 · +5 평가일 ≤ 보고 종료일
  - 학습 = 구간 시작 전 신호일 · §1-3 시각 조건
  - 학습 유효 신호일 20 이상 + 시험 행 1 이상이 아니면 그 구간 DATA_SHORT
- **MAE**: 날짜별 가중 절대오차 합 → 날짜 평균 · %p. 세 구간 모두 유효할 때만 전체(시험 날짜를 합친 날짜 균형 MAE)와 '개선 / 차이 없음 / 악화'(소수 2자리 %p 비교 · 원시값 보존). 불완전이면 구간별 진단만.
- **item 별 ML 칸**: 자신이 시험 행인 구간 모델의 추정만. 그 밖 = 값 없음 + 사유(시험 구간 밖 · 미성숙 · 자료 부족 · ML 범위 밖 · 지원 안 되는 버전).

### 2-3. 산출물 · 조회

- **`report.json`**:
  - 신호 종료일 · 가격 관측 기준일(price_asof_date) · snapshot 획득 시각 · 생성 시각 · 사본 동기화 시각
  - 분모 · 가격 상태 건수 · ML 상태 · 구간표
  - item / series 별 가격 평가 · ML 값 · 사유 · 사용자 평가(event 최신 1건: feedback_seq · helpfulness · feedback_at)
  - recipe · 라이브러리 버전 · 입력 digest
- **`input_snapshot.json`**: 실제 쓴 허용 feature(정규화 값) · 결과 행 · 연결 키 · 시각 · 계약 버전 · 평가 식별값 · recipe · 신호 종료일 · price_asof_date. 행 · 키 정렬 → canonical sha256 = 입력 digest. values_json 전체 · 본문 · 메모 · action · 손익률 · 개인값은 넣지 않는다.
- **GET latest**:
  - 정상 폴더(두 파일 다 있음) 중 최신을 읽는다.
  - `event_id` 를 주면 그 알림의 item / series 결과만 돌려준다.
  - 지금 사본의 입력 digest 를 **원래 보고의 신호 종료일 · price_asof_date 로** 같은 방식으로 다시 계산해 다르면 `input_changed: true`('입력이 변경됨 · 재실행 필요')를 함께 보인다(조회 시계만으로 변경이 생기지 않음 · 판정 §3-B). 사본 읽기만 하며 학습 · SSH · 쓰기는 없다. 새 기준일 보고는 새 POST 로.
  - 산출물이 없으면 `NO_RESULT`.

### 2-4. 화면

- **「받은 알림 기록」 머리**: [원장 새로고침] 옆에 큰 버튼 **[사후평가 실행]**(별도 동작 · 실행 중 표시 · 실패 문구).
- **결과 영역(요약)**: 신호 종료일 · 가격 관측 기준일 · snapshot 획득 시각 · 생성 시각 · 사본 동기화 시각 · 대상 / 성숙 / 미성숙 건수 · ML 상태 · 세 구간 표 · 입력 변경 안내.
- **알림 상세(기존 '자세히 보기')**:
  - 항목 · series 별 '+5 실제 / 과거 검증 추정 / 단순 기준 / 절대오차' 또는 사유.
  - 자동 가격 평가 문구와 사용자 평가는 각각 따로 둔다.
  - 여러 항목인 알림에 '알림 전체 점수'를 만들지 않는다.
- 처음 들어올 때는 GET latest 만 부른다(실행 0). 평가 입력 방식 · 메뉴는 그대로다.

### 2-5. 기반 문서(설계 §2 한정 예외)

- **확정문 '2026-10-11 POC5-08 연구 예외'를 날짜와 함께 덧붙이는 곳**:
  - PROJECT_ORIGIN_INTENT §9.5
  - ASSUMPTIONS Q6
  - POC5-00 설계 · PLAN(현재 계약 줄)
  - STATE · PROGRAM_TRUTH
- 원래 문장 · 01 ~ 04 ML 미포함 · 06 별도 연구 · 실패 실험 기록은 보존한다. 구현 시작 때 함께 반영한다.

### 2-6. 정해 둔 세부 (질문 아님 · 판정에서 바꿀 수 있음)

1. 시험 구간 시작 시각 = 그 구간 ML 시험 행 중 가장 이른 `runtime_kst`(KST 시각). 시험 행이 없으면 그 구간은 DATA_SHORT.
2. ML 대상 price_basis = `|` 앞 기본 이름이 `KRX_ETF_UNADJUSTED` · `KRX_STOCK_UNADJUSTED` 와 정확히 같음(02 가 `|종목 구분 출처`를 붙여 기록) · 접미는 snapshot 에 그대로 남기고 feature 로 쓰지 않는다.
3. 구조적 결측(보유 브리핑의 당일 변화 · 장중 종목의 20거래일 변화)도 설계 규칙대로 결측 표시 + 대입 — 행을 빼지 않는다.
4. 입력 digest 에는 event 최신 평가(feedback_seq · helpfulness · feedback_at)가 들어간다 → 평가만 바뀌어도 '입력 변경'이 뜬다(설계 §7 '평가만 바뀌면 digest 변경'). 모델 수치는 같다.
5. 조회 때의 '입력 변경' 판정을 위해 사본을 읽기 전용으로 한 번 읽는다(학습 · 산출물 쓰기 없음).
6. 사본 없음(NO_COPY)은 산출물을 만들지 않고 안내만(빈 모집단 성공 아님).

## 3. 검증 계획 (설계 §9 1:1 · 줄인 방식)

| 설계 §9 | 시험(tmp 사본 · 고정 fixture) |
|---|---|
| 무평가 사용 | 평가 0 → 추가 → 변경에서 관측 · 라벨 · 가중치 · 모델 · 가격 문구 같음 · 사용자 평가 표시와 digest 만 다름 |
| 분모 · 연결 | PRIMARY / SECONDARY / NONE · not_selected · suppressed · cut_by_section_cap · partial · 전달 실패 · 다중 ticker · 대표 / 대체 ETF · 시장 · 기초지수(ML 범위 밖 · 원시 유지) · 같은 event 평가 1번만 |
| 가격 상태 | +1 성숙 / +5 대기 / +20 대기 · T0_MISSING · PRICE_MISSING · UNTRACKED_AFTER_EXIT · UNSUPPORTED · 경로 일부 · 끝점 부호 · 결측을 0% · 나쁜 라벨로 바꾸지 않음 · 미도래 / 도래 후 미기록 = price_asof_date 기준 · **과거 보고 종료일을 지정하고 평가일이 지난 뒤 실행해도 그 결측 슬롯은 price_asof_date 기준(종료일이 아님)** · snapshot 획득 시각 15:30 앞 · 뒤 |
| 시간 누출 | 시험 미래값 · 평가 변경에 학습 변환 불변 · 늦게 계산된 과거 라벨 제외 · 15:40 사건 · 같은 날 여러 행 · 겹치는 창 제외 |
| 모델 비교 | 충분 표본 fixture(합성 · 임시 사본)로 알려진 가중 중앙값 · 날짜 MAE · 세 구간 · 하한 −1 · 처음 보는 범주 · 숫자 결측 · 구간 부족 · 같은 snapshot 결정성 |
| 보존 · 실패 | 사본 · 보유 · 시세 · 기존 연구 파일 불변 · 실행 / 조회에 SSH · 시세 · 외부 조회 0 · 필수 표 누락 · 손상 · 중복 키 = CHECK_REQUIRED · 저장 실패 = 500 · 이전 산출물 보존 · 반쪽 폴더 없음 |

- 화면 vitest(실행 버튼 · 요약 · 상세 항목 · 실패 · 입력 변경 · 첫 진입 실행 0).
- 독립 검토 1회 · 변이 시험(저장소 사본) · 정적 검사 · 관련 회귀 · 마지막 전체 회귀 1회 + 라이브 해시(같은 범위) · KS-10.
- 실제 원장에 알림 · 거래 · 평가를 만들지 않는다.

## 4. 문서 · 배포

- OCI 변경 0 → OCI pull · 새 cron · .env 변경 없음.
- 흐름: PLAN 판정 → 기반 문서 예외 반영 → backend → 결과 영역 목업 확인 → frontend → 검증자 → 설계자 RESULT → 커밋 · push(사용자 승인) → PC 재기동 · 실화면 → 종료.
- 실화면은 그때 자료로 가격 사후평가 · ML 상태(자료 부족 · 구간 진단) 정상 표시와 실행 · 보존 계약을 확인한다(좋은 모델 수치 · 실데이터 누적은 종료 조건 아님 · 설계 §10).
- PROGRAM_TRUTH(화면 · API · 산출물 경로) · STATE 갱신.

## 5. 사용자 확인 항목

1. PC 원장 사본이 2026-10-08 이후 동기화되지 않았다. 실화면 전에 [원장 새로고침]을 한 번 누르면 최신 사본으로 볼 수 있다(선택 · 10-12 08:10 이후면 02 첫 결과 행도 들어온다).
2. 세 구간 전체 비교는 조건부로 가장 이르면 2026-12-09 보고 종료일부터다(§1-4). 그 전 실행은 가격 사후평가 + 자료가 갖춰진 구간의 진단 · 나머지는 '자료 부족'이 정상이다.
3. backend 구현 중 결과 영역 목업 1회 확인(설계 §8).

## 6. 설계자 질문

없음. 설계 §3 ~ §8 의 입력 · helper · 시각 경계 · 모델 · 산출물 · API 를 현재 코드와 자료로 모두 지킬 수 있다(§1). 숫자 feature 두 개의 실제 키(`return_20d_pct` · `day_return_pct` · % 단위)와 개인값 `profit_loss_pct` 제외는 §1-2 에 고정했다.

## 7. 설계자 판정 반영 (2026-10-11 · PASS · 원문 = 설계서 §12 · 끝에 전달문 원문)

- 수용: % → 비율 · 개인 손익률 제외 · 구조적 결측 유지 · 학습 / 시험 분리 · 시험 시작 시각(§2-6-1) · price_basis 는 `|` 앞 기본 이름을 `KRX_ETF_UNADJUSTED` / `KRX_STOCK_UNADJUSTED` 와 **정확히** 비교(§2-6-2 정정 · 접미 보존 · feature 아님) · 04 / 02 helper 재사용 · 로컬 2경로 · 연구 파일 2개 · NO_COPY / CHECK_REQUIRED 구분.
- **보충 A**: 12-09 = 전체 3구간 비교의 조건부 가장 이른 보고 종료일(§0 · §1-4 · §5 정정) — 날짜로 실행을 막지 않고 실행마다 실제 유효 표본으로 판단 · 그 전에도 유효 구간 진단.
- **보충 B**: 신호 종료일(end_date)과 가격 관측 기준일(price_asof_date)을 나눈다(§2-1 · §2-3 · §3 정정) — snapshot 획득 시각 1회 고정 → 그 시각까지 종가가 끝난 마지막 거래일 · 결과 없는 슬롯 = 평가일이 그 뒤면 미도래 · 같거나 앞이면 도래 후 미기록(공개 · 보강 대기 포함 — 오류 · PRICE_MISSING 으로 바꾸지 않음) · 보고에 신호 종료일 · 가격 관측 기준일 · snapshot 획득 시각 · digest / recipe 에 price_asof_date · GET 의 입력 변경 비교는 원래 보고의 두 날짜로 · 04 코드 · 뜻 불변 · 과거 종료일 + 늦은 실행 fixture.
- **보충 C**: '01B ~ 06 코드 변경 0' → '01B ~ 06 원장 · 성숙 · 동기화 · 평가 저장 · 기존 모델의 계약 / 처리 변경 0 · 03 화면과 router 는 08 용으로 확장'(§1-6 정정).
- 다음: 기반 문서 예외 반영 → backend → 결과 영역 목업 1회 → 사용자 확인 → frontend → 검증자 → RESULT.
