> **기록 정보** — 작성: 설계자(웹 GPT) · 전달: 사용자(2026-10-07) · 기록: 개발자(VSCode Claude). 아래는 설계자 설계서 원문이다.
> 상위 설계: `docs/ai_design/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_DESIGN_V1.md` · PLAN `docs/ai_plan/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_PLAN_V1.md`(Q1 ~ Q30 확정 · 다시 묻지 않는다).
> 선행: `docs/ai_design/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md`(설계자 RESULT `PASS_TO_DEPLOY` 2026-10-07).
> 이 단계 PLAN: `docs/ai_plan/POC5/POC5-02_PRICE_OUTCOME_MATURITY_PLAN_V1.md`.

# POC5-02 — 가격 결과 성숙 DESIGN V1

```text
STEP_ID          = POC5-02
PREDECESSOR      = POC5-01B
SUCCESSOR        = POC5-03
PURPOSE          = 01B 사건에 +1/+5/+20 거래일의 원시 가격 결과를 붙인다
OUTCOME_POLICY   = RAW_ONLY
LOCAL_WORK       = DESIGN·PLAN·구현·검증 진행 가능
OCI_DEPLOY_GATE  = POC5-01B 첫 거래일 운영 확인
```

## 1. 완료 모습

01B 원장의 평가 가능한 항목마다 가격 자료가 실제로 쌓인 뒤 +1·+5·+20 결과가 `price_outcome`에 한 번씩 기록된다.

- 수익률·평가일 가격·종가 경로의 최대 상승/하락을 원시값으로 남긴다.
- 성공·실패, 유리·불리, 추천 적중률은 만들지 않는다.
- +20일까지 기다리지 않고 단계 개발과 종료를 진행한다. 이후 누적 확인은 POC5-04 R0/R1이 맡는다.

## 2. 포함·제외

### 포함

- 기존 OCI `state/decision/decision_evidence.sqlite`에 `price_outcome` 테이블 1개 추가
- `PRIMARY_LIVE`의 평가 가능한 item에 대한 +1/+5/+20 결과
- 기존 08:10 가격 배치와 09:20 KRX 보강 뒤의 격리된 성숙 실행
- ETF·보유 개별주·사업군 대표 ETF·시장(KOSPI)·기초지수 선택 ticker
- 결측·매도 뒤 미추적·t0 누락 상태
- 과거 실행 건수·연결 상태를 보는 legacy 진단

### 제외

- 과거 종목 신호·가격 결과 backfill
- 성공 기준·방향 적중률·상태별 유리한 방향
- PC 화면·동기화·사용자 피드백
- 신규 cron·외부 API·시세 조회·의존성
- 기존 PUSH·가격 배치 status·exit code 변경
- 거래량 추가와 거래정지 판별

## 3. 가격 자료원

한 outcome은 처음 정한 한 가격 계열만 사용하며 다른 자료원으로 대체하지 않는다.

| 대상 | 가격 계열 | 계약 |
|---|---|---|
| ETF·사업군 대표·기초지수 ticker | `krx_etf_daily_price_unadjusted` | KRX 무조정 종가 |
| KRX 상장 보유 개별주 | `krx_stock_daily_price_unadjusted` | OPS-04 KRX 공식 무조정 종가 |
| 시장 브리핑의 한국 시장 | `market_benchmark_daily_price`의 KOSPI | KRX 공식 KOSPI 종가 |
| 지원 계열이 없는 대상 | 없음 | `UNSUPPORTED_PRICE_SOURCE`; FDR 대체 금지 |

POC5-00 Q15의 `비ETF 보유 = FDR`은 당시 KRX 개별주 표가 없던 계약이다. OPS-04에서 공식 표와 PUSH 소비가 확정됐으므로 **KRX 상장 보유주는 공식 표로 대체**한다. 기존 FDR 표는 POC5-02 outcome에 섞지 않는다.

`KRX_UNADJUSTED`는 분배락 효과가 가격에 포함되는 계열이라는 뜻이다. 실제 분배 발생 여부를 별도 데이터 없이 추정하지 않는다.

## 4. 대상과 표본

- `cohort=PRIMARY_LIVE`, `off_schedule=0`인 run의 item을 대상으로 한다.
- `evaluable=1`이면 sent·suppressed·cut·not_selected 모두 원시 결과 대상이다.
- 전달 효과 표본은 나중에 `disposition=sent AND delivery_status=sent`로 필터링한다.
- `evaluable=0`은 가격 outcome을 만들지 않는다. 자료 장애 사실은 01B item이 정본이다.
- legacy는 실행 연결·건수 진단만 허용하며 `price_outcome`을 만들지 않는다.

기초지수 그룹에 ticker가 여러 개면 평균값을 만들지 않고 ticker별 원시 결과를 둔다. 따라서 outcome 키는 최소 `(event_id, item_seq, series_id, horizon)`을 구분해야 한다.

## 5. t0와 거래일 축

### t0

- 보유 브리핑·장중 항목: 01B가 메시지 조립에 실제 사용한 `t0_price`와 시각
- 시장 KOSPI·기초지수 ticker: 메시지 시점에 이미 확정된 직전 가격 계열 종가
- 현재가가 없으면 종가로 대신하지 않는다.

### +1/+5/+20

- 가격 DB에 실제 적재된 공통 날짜 축에서 사건 뒤의 1·5·20번째 종가를 고른다.
- 15:30 이전 사건은 같은 날 종가를 첫 번째로 센다.
- 15:30 이후 사건(현재 15:40 보유 CLOSE)은 다음 적재 거래일 종가부터 센다.
- 시장 08:30 사건은 당일 KOSPI 종가가 +1이다.
- 캘린더 예상일만으로 성숙시키지 않는다. 평가일 가격 행이 실제로 저장돼야 `MATURED`다.

## 6. 결과 기록

각 horizon은 다음을 한 번만 INSERT한다.

```text
event_id · item_seq · series_id · horizon · t0_price · t0_price_asof
signal_date_close · previous_close · eval_date · eval_price
return_raw · max_up_raw · max_down_raw · price_basis
status · computed_at · source_collected_at
```

- `return_raw = eval_price / t0_price - 1`
- `max_up_raw`, `max_down_raw`는 t0 대비 해당 horizon까지의 종가 경로 최대·최소다.
- 원시 소수값을 저장하고 표시용 반올림은 하지 않는다.
- 원천에 실제 수집 시각이 없으면 `source_collected_at`을 꾸며 넣지 않고 NULL로 둔다.
- 성숙 전은 행이 없는 상태이며 조회 단계에서만 `PENDING`으로 해석한다.

상태는 최소 다음을 구분한다.

```text
MATURED / T0_MISSING / PRICE_MISSING /
UNTRACKED_AFTER_EXIT / UNSUPPORTED_PRICE_SOURCE
```

`PRICE_MISSING`은 평가일 축이 다음 날짜까지 전진했는데 대상 행이 없을 때만 확정한다. 최신 날짜의 일시적 적재 지연은 계속 PENDING으로 두어 09:20 또는 다음 배치의 복구 기회를 보존한다.

## 7. 실행 위치와 장애 격리

- 08:10 전체 가격 배치가 기존 기록을 끝낸 뒤 성숙 단계를 실행한다.
- 09:20 KRX 보강이 가격을 추가할 수 있으므로 같은 성숙 단계를 다시 실행한다.
- 실행은 idempotent하며 이미 있는 `(event_id, item_seq, series_id, horizon)`은 건드리지 않는다.
- 성숙 실패는 별도 로그와 처리 건수만 남기고 가격 배치 status·exit code·08:30 PUSH에 영향을 주지 않는다.
- 재시도 큐·daemon·별도 scheduler·새 상태 JSON은 만들지 않는다.

## 8. 수용 기준

1. +1/+5/+20 날짜 선택이 pre-open·장중·15:40 사건에서 계약대로 다르다.
2. ETF·개별주·KOSPI가 지정 계열만 사용하고 FDR fallback이 0건이다.
3. 같은 입력을 반복 실행해도 outcome 행과 값이 늘지 않는다.
4. 최신 평가일 행 누락은 PENDING이며, 날짜 축이 전진한 뒤에만 PRICE_MISSING이 된다.
5. 매도 뒤 개별주 추적 중단과 일반 결측을 구분한다.
6. t0 누락 시 다른 가격으로 대체하지 않는다.
7. sent·suppressed·cut·not_selected는 계산되고 evaluable=0·legacy는 제외된다.
8. 시장 결과는 KOSPI 원시값만 기록하며 방향 적중 판정을 만들지 않는다.
9. 08:10·09:20 성숙 실패를 주입해도 기존 배치 기록·exit code·PUSH가 같다.
10. 임시 DB fixture·전체 회귀·라이브 파일 불변·KS-10을 통과한다.

## 9. 개발 PLAN에서 확인할 것

1. 01B `signal_item.values_json`과 subject별 `series_id`의 정확한 매핑
2. 세 가격 테이블의 컬럼·날짜 축·수집 시각·현재 보유 판별 경로
3. 08:10과 09:20에서 기존 batch 결과 확정 뒤 붙일 정확한 한 지점
4. pre-open·장중·15:40의 평가 날짜 fixture
5. `price_outcome` DDL·인덱스·INSERT-once 경계
6. PRICE_MISSING과 UNTRACKED_AFTER_EXIT를 확정할 증거
7. 변경 파일·테스트·전 파일 KS-10 실측

POC5-00 Q1~Q30을 다시 질문하지 않는다. 실제 01B item으로 가격 계열을 유일하게 정할 수 없는 경우만 추천안과 함께 중단 보고한다.

## 10. 진행 기준

- POC5-01B 운영 확인을 기다리지 않고 DESIGN·PLAN·로컬 구현·검증을 진행할 수 있다.
- POC5-02 OCI 배포만 POC5-01B 첫 거래일 운영 확인 뒤 진행한다.
- +5·+20 결과 누적은 POC5-02 종료 조건이 아니다.
- 외부 조회·과거 outcome backfill·가격 fallback·기존 배치 결과 변경이 필요하면 구현 전에 중단한다.

---

## 설계자 전달문 — 2026-10-07 (사용자 전달 원문)

```text
POC5-02 PLAN 작성 요청

설계서:
docs/ai_design/POC5/POC5-02_PRICE_OUTCOME_MATURITY_DESIGN_V1.md

요청 사항:
- 설계서 §9의 7개 항목을 실제 코드 기준으로 조사
- 구현 전에 PLAN 제출
- POC5-00 Q1~Q30 재질문 금지
- 신규 외부 조회·cron·FDR fallback·과거 outcome backfill 금지
- POC5-01B 운영 확인을 기다리지 않고 PLAN·로컬 구현·검증 진행 가능
- POC5-02 OCI 배포만 POC5-01B 첫 거래일 운영 확인 뒤 진행
- 설계와 실제 코드가 충돌하는 항목만 추천안과 함께 보고
```

> 핵심 결정은 하나입니다. 과거 POC5-00의 '비ETF 보유종목은 FDR 사용' 계약을 OPS-04 이후 현실에 맞게 수정했습니다. 이제 KRX 상장 보유주는 OPS-04가 만든 KRX 공식 개별주 가격표만 사용하며 FDR로 대체하지 않습니다.


## 설계자 PLAN 판정 — 2026-10-07 (사용자 전달 원문)

```text
PLAN_DECISION = PASS_TO_IMPLEMENT
RESUBMISSION = NOT_REQUIRED
Q-A = ACCEPTED
Q-B = ACCEPTED
Q-C = ACCEPTED_WITH_CORRECTION
Q-D = ACCEPTED
```

> 다만 Q-C는 구현할 때 두 가지를 반드시 반영해야 합니다.
>
> 1. +1/+5/+20 날짜는 기존 운영 거래일 캘린더만으로 확정합니다.
>    - 가격표에 행이 있느냐를 휴장일 판정에 사용하지 않습니다.
>    - 가격 적재 상태가 바뀌어도 평가일은 바뀌면 안 됩니다.
>    - 연도 캘린더가 없을 때는 기존 운영 정책인 평일 fallback을 사용합니다.
> 2. `MATURED`는 평가일 종가만 있다고 기록하면 안 됩니다.
>    - +5라면 +1부터 +5까지 예상된 5개 종가가 모두 있어야 합니다.
>    - 중간 가격이 빠졌으면 backfill 가능 기간에는 `PENDING`으로 둡니다.
>    - backfill 기간이 끝나도 빠져 있으면 `PRICE_MISSING`으로 확정합니다.
>    - `path_points`는 진단용으로 유지하되, 불완전한 경로로 최대 상승·하락을 확정하는 근거로 사용하면 안 됩니다.
>
> 그 밖의 판정은 다음과 같습니다.
>
> - Q-A: 기존 `classify_assets` 재사용 승인. `UNKNOWN`은 재시도하고, KRX 개별주 표가 지원하지 않는 코스닥 종목은 `UNSUPPORTED_PRICE_SOURCE`로 처리합니다.
> - Q-B: `market/SP500` item을 KOSPI 결과의 연결 주체로 사용하는 안을 승인합니다. subject를 KOSPI로 바꾸지는 않습니다.
> - Q-D: 기존 대조 CLI의 선택적 `--legacy` 출력으로 제한하는 안을 승인합니다. 기본 출력은 그대로 유지합니다.
> - 추가 컬럼 `path_points` 승인
> - 배치 프로세스에서 `.env`의 원장 플래그 한 키만 직접 읽는 방식 승인
> - §0의 "새 모듈 하나"는 실제 계획대로 "새 모듈 2개"로 문구만 바로잡으면 됩니다.

```text
(개발자 전달문 중 사용자 OCI 작업 기록)
- git pull 완료
- DECISION_LEDGER_ENABLED=true 적용
- grep 결과 1
POC5-01B OCI 즉시 확인은 읽기 전용으로 진행하고, 첫 거래일 운영 확인은 2026-10-08 09:35 이후 수행한다.
이는 POC5-02 로컬 구현을 막지 않는다.
```


## 설계자 RESULT 판정 — 2026-10-07 (사용자 전달 원문 · 검증자 r1 VERIFIED 뒤)

```text
RESULT_DECISION = PASS_TO_DEPLOY_AFTER_GATE
VERIFIER = VERIFIED r1
CODE_REMEDIATION = NONE
REVERIFICATION = NONE
EXTRA_CHANGES = ACCEPTED 4/4
DEPLOY_GATE = POC5-01B 첫 거래일 운영 확인
```

> 판정 내용:
>
> - 성숙 모듈 자체 DDL: 수용
> - 기존 `holdings_tickers` 재사용: 수용
> - 캘린더 실행당 1회 생성: 수용
> - 01B 상태 문서가 같은 커밋에 포함된 것: 수용
> - 성능 개선 15.3초 → 0.14초: 정상
> - 거래정지 미지원: 사용자 결정으로 종료
> - 코드 재작업과 재검증은 필요 없습니다.
>
> 내일 10월 8일 09:35 이후 01B 운영 확인을 통과하면 POC5-02 배포가 가능합니다. 그 전에도 커밋·push 준비와 다음 단계 개발은 진행할 수 있지만, 실제 OCI pull만 기다립니다.
>
> 보유 이력 요청도 판단했습니다.
>
> - 필요성 인정
> - BACKLOG 재검토 트리거 충족
> - POC5-02 결함이나 배포 차단 사유는 아님
> - POC5-03에는 포함하지 않음
> - 별도 소형 설계로 매수·매도 시점과 금액을 다룸
> - 금액·수량은 holdings에만 두고 의사결정 원장에는 넣지 않음
> - 기존 POC5-02 결과를 다시 계산하지 않음

```text
(개발자 전달문)
배포 게이트:
- 2026-10-08 09:35 이후 POC5-01B 첫 거래일 운영 확인
- 통과 뒤 POC5-02 OCI pull
- cron · .env 변경 없음
```
