# POC3-OPS-01A — 보유 PUSH 선별·그룹화·반복 억제 PLAN 작성 지시

- **작성**: 설계자
- **수신**: 개발자
- **수신일**: 2026-08-31
- **성격**: **설계자 지시문**(개발자 입력). §1 이하는 설계자 원문 그대로.
- **개발자 회신**: `docs/ai_plan/POC3/POC3-OPS-01A_HOLDINGS_PUSH_SELECTION_AND_SUPPRESSION_PLAN_V1.md`
- **선행**: `POC3-OPS-01` 사전 실측 (읽기 전용 · 채팅 반환 · 판정 `PARTIALLY_CAPTURED`)
- **선행**: `docs/ai_result/POC3/POC3-ML-02-CLOSEOUT_..._RESULT.md` (Closeout `CLOSED` · 커밋 `fd87c440`)

---

## 0. 선행 실측 요약 (POC3-OPS-01 · 채팅 반환)

01A 의 기준선이 되는 사실만 옮긴다. 재측정하지 않는다.

- 활성 PUSH **3종** — 시장 흐름 브리핑 / 보유 종목 관찰 브리핑 / 급등락·상승 관찰 신호
- 실행 주기는 **cron 이 결정** — 시장 1회·보유 3회·급등락 7회 (하루 11회)
- 14일(2026-08-18~08-31) 실행 110 · 발송 49 · 스킵 61 · 실패 0
- 보유 브리핑 평균 **8,690자 · chunk 3개 · 종목 32 전량 · 종목당 2줄**
- **선정·정렬·"봐야 할 이유" 로직 없음** — 전량 나열
- 발송 본문 **미저장** (`HISTORICAL_BODY_UNAVAILABLE`)
- 위험 evidence (`market_risk_feature_daily` 등) **`NOT_CONSUMED`** · OCI 0행
- 판정 `PARTIALLY_CAPTURED`

---

## 1. 목표

현재 하루 3회 발송되는 보유 브리핑을 다음 구조로 바꾼다.

* 선정 이유가 있는 보유종목만 표시
* 해당 종목은 개수 제한 없이 모두 표시
* 같은 이유끼리 그룹화
* OPEN에는 당일 최초 상태를 전달
* MIDDAY·CLOSE에는 새 문제·이유 추가·심각도 변화만 전달
* 동일 종목·동일 이유·동일 심각도는 반복하지 않음
* 볼 종목이 없거나 변화가 없으면 발송하지 않음

이번 반환에서는 구현하지 않는다. 현재 데이터로 가능한 선정 이유와 발생 건수를 실측하고 개발 PLAN만 제출한다.

## 2. 현재 기준선

다시 측정하지 말고 기존 14일 실측을 기준선으로 사용한다.

```text
holdings_logical_push_per_business_day = 3
holdings_telegram_chunks_per_business_day = 9
holdings_characters_per_business_day ≈ 26,070
holdings_rows_rendered_per_business_day = 96
holdings_records = 32
unique_tickers = 29
```

`32 attempted / 29 success / 0 failed`는 32개 계좌별 보유 행과 29개 고유 ticker의 차이로 이미 확인됐다. 신규 결함으로 열지 않는다.

## 3. 확정된 메시지 계약

### OPEN

* 고유 ticker 기준으로 한 번만 표시
* 현재 선정 이유가 있는 종목을 모두 포함
* 같은 이유의 종목을 하나의 그룹으로 표시
* 종목 수 상한 없음
* 평가금액은 기본 제외
* 선정과 관련 없는 숫자는 제외
* 한 종목이 여러 이유에 해당하면 중복 행으로 나열하지 않음
* 주된 이유 아래에 추가 이유를 표시하는 방식을 PLAN에서 제시

### MIDDAY·CLOSE

다음 변화가 있을 때만 발송한다.

* 새 종목이 선정됨
* 기존 종목에 새로운 이유가 추가됨
* 기존 이유의 심각도가 변경됨
* 기존 문제가 정상 상태로 해소됨

동일한 상태는 반복 발송하지 않는다. 변화가 없으면 runner는 실행하더라도 Telegram을 보내지 않는다.

OPEN·MIDDAY·CLOSE cron 자체는 이번 Step에서 변경하지 않는다.

## 4. 선정 이유 후보 — 데이터 실측

아래 후보별로 현재 OCI에서 계산 가능한지 확인한다.

| 후보 reason | 확인할 내용 |
| --- | --- |
| `MARKET_RELATIVE_WEAKNESS` | KODEX200 대비 1개월 초과수익 |
| `RECENT_DECLINE` | 최근 20거래일 수익률 |
| `INTRADAY_DROP` | 직전 종가 대비 runtime 현재가 하락률 |
| `RECENT_LOW_OR_DRAWDOWN` | 최근 고점 대비 하락 또는 20거래일 저점 접근 |
| `LOSS_WORSENING` | OPEN 이후 평가수익률 악화 |
| `DATA_UNAVAILABLE_OR_STALE` | 현재가·가격 기준일·필수 evidence 누락 또는 지연 |

각 후보에 대해 제출한다.

* 원천 필드와 파일·DB 경로
* OCI에서의 현재 가용 여부
* 기준일과 갱신 시점
* 고유 ticker 29개 중 계산 가능 수
* 과거 재현 가능 기간
* 신규 데이터 수집 없이 가능한지
* 현재 Step에서 사용할 수 없다면 그 이유

Mac에만 있고 OCI에 없는 데이터는 사용 가능으로 판정하지 않는다. 신규 외부 데이터와 ML feature 이전은 이번 범위 밖이다.

## 5. 임계값 프로파일

최종 임계값은 개발자가 정하지 않는다. 아래 후보값별 발생 건수만 계산한다.

### 시장 대비 약세

* KODEX200 대비 1개월 `−3%p`
* `−5%p`
* `−8%p`

### 최근 하락

* 최근 20거래일 `−5%`
* `−8%`
* `−10%`

### 당일 하락

* 전일 종가 대비 `−2%`
* `−3%`
* `−5%`

가능한 데이터에 대해 최근 60거래일을 우선 사용하고, 불가능하면 확보 가능한 기간을 명시한다.

각 임계값별로 제출한다.

| reason | 임계값 | 일평균 선정 ticker | 중앙값 | 최대 | 선정 0일 비율 |
| --- | --: | --: | --: | -: | --: |

추가로 현재 보유 29종목 기준 실제 선정 ticker와 값을 제출한다.

평가손실·저점·데이터 지연은 분포를 확인한 뒤 별도 임계값 후보를 제시할 수 있으나, 개발자가 채택 판정을 내리지는 않는다.

## 6. 심각도와 그룹 구조

PLAN에는 다음을 제안하되 확정하지 않는다.

* 심각도 단계와 명칭
* 각 단계의 임계값
* 여러 reason이 겹칠 때 primary reason 결정 규칙
* 같은 reason 그룹 안의 정렬 기준
* 심각도 완화·정상 해소 시 메시지 표현
* 하나의 ticker가 여러 계좌에 있을 때 표시 방식

선정 종목 누락을 막기 위해 `최대 N개`나 상위 일부만 표시하는 규칙은 제안하지 않는다.

## 7. 반복 억제 상태 계약

PLAN에서 다음을 명확히 정의한다.

* 하루 시작·종료 기준: KST
* OPEN 최초 상태 저장 방식
* 비교 identity: ticker · reason 집합 · severity
* MIDDAY·CLOSE 변화 판정
* 정상 해소 처리
* 다음 영업일 OPEN 재발송 여부
* 상태 파일이 없거나 손상됐을 때의 처리

상태 비교 실패를 `변화 없음`으로 대체해 조용히 억제하면 안 된다. 비교할 수 없으면 전체 현재 상태를 보내는 방향을 우선안으로 제시하고 운영 기록에는 원인을 남긴다.

## 8. 연관 BACKLOG 영향 확인

BACKLOG 전체를 재분류하지 않는다.

현재 55개 항목에서 다음 키워드와 책임이 직접 겹치는 항목만 찾는다.

* holdings / briefing / PUSH / autosend / duplicate / registry / Telegram / runtime price / evidence freshness

아래 형식으로 제출한다.

| BACKLOG ID | 01A와 관계 | 제안 처리 | 이유 |
| --- | --- | --- | --- |
| | `BLOCKER` | `RESOLVE_IN_STEP` | |
| | `DIRECT_OVERLAP` | `INCLUDE_IN_STEP` | |
| | `SUPERSEDED` | `DROP_AS_SUPERSEDED` | |
| | `RELATED_LATER` | `KEEP_BACKLOG` | |

파일이 겹친다는 이유만으로 포함하지 않는다. 01A 목표와 수용기준에 직접 필요한 항목만 포함 후보로 올린다.

이번 PLAN 단계에서는 BACKLOG를 수정하거나 폐기하지 않는다. 설계자 판정 후 확정한다.

## 9. 테스트와 역검증 계약

PLAN에는 다음 테스트를 포함한다.

### 정상 계약

* reason 없는 종목은 표시되지 않음
* reason 있는 종목은 개수 제한 없이 전부 표시
* 동일 ticker의 계좌 중복 표시 없음
* 같은 reason끼리 그룹화
* OPEN 최초 상태 발송
* MIDDAY·CLOSE 동일 상태 미발송
* 새 종목·새 reason·severity 변화 발송
* 정상 해소 상태 처리
* 상태 비교 실패를 정상·변화 없음으로 오판하지 않음

### 필수 역검증

결과서 제출 전에 아래 보호를 실제로 무력화하고 테스트 실패를 확인해야 한다.

1. 반복 억제 제거 → 동일 상태 재발송 테스트 실패
2. fingerprint를 상수로 변경 → 새 종목·새 reason이 억제되어 테스트 실패
3. severity 변화 분기 제거 → 악화·완화 재발송 테스트 실패
4. selection filter 제거 → reason 없는 전체 종목이 출력되어 테스트 실패
5. 선정 종목 하나를 강제로 누락 → 전체 선정 종목 포함 계약 테스트 실패

역검증은 "코드상 잡을 것"이라는 설명이 아니라 실제 실패 건수와 실패 단언을 결과서에 기록한다.

## 10. 범위 제외

* 미국시장 데이터 / 상승 섹터 탐지 / 시장 브리핑 변경 / 시장 위험 알림
* 신규 ML·모델·feature / OCI ML 테이블 이전 / 급등락 후보 알림 변경
* cron 횟수 변경 / 신규 외부 데이터 / API·PC/Mac UI 변경 / 전체 BACKLOG 재분류

## 11. 이번 반환물

1. 개발 PLAN
2. 선정 reason 가용성 표
3. 임계값별 발생 건수 표
4. 상태·fingerprint 설계
5. 연관 BACKLOG 영향표
6. 테스트·역검증 계획
7. 남은 설계자 판정 사항

구현·테스트 추가·운영 발송·배포·커밋·푸시는 하지 않는다.
