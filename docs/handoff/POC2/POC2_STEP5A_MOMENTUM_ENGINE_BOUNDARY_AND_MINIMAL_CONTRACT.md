# POC2-Step5A 설계서
## Momentum Engine Boundary & Minimal Contract

작성일: 2026-04-30
작성자: 사용자 본인 (지시문 원본) + 개발자 저장
대상: 다음 세션 진입자 (Step5B 설계자 — Momentum Engine 결과 저장 위치 결정)
성격: 계약 문서화 단계. 구현 단계 아님. 산식·유니버스·데이터 소스·저장 위치·ML·UI 디자인 모두 확정하지 않는다.

---

## 1. Step5A 의 단일 목표

```text
holdings mode 와 universe mode 가 공유할 수 있는
Momentum Engine 의 최소 입력/출력 계약을 정의한다.
```

이번 Step5A 는 구현 단계가 아니다.

아래는 확정하지 않는다:

- 구체 점수 산식
- MA 기간
- RSI 기준
- 수익률 기간
- 보너스 점수
- 유니버스 종목 수
- ETF 후보군 목록
- 데이터 소스
- pykrx / yfinance / KIS 여부
- ML 모델
- 화면 디자인
- Telegram Top N
- BUY / SELL / 리밸런싱
- 운영 결과 저장소

---

## 2. 현재 위치 요약

### Step2 까지의 흐름
```text
holdings 입력
→ 시세 갱신
→ 평가 계산
→ 승인 초안
→ 승인
→ OCI / Telegram 전달
```

### Step3
```text
보유 비중 영향 factor 1개 추가
→ draft_payload.factor_signals
→ 승인 초안 UI
→ message_text
→ Telegram/Push 확인
```

### Step4
```text
잘 달리는 말 찾기를 holdings factor 가 아니라
Momentum Engine 의 universe mode 로 다루는 방향 정리
```

### Step5A 의 문제의식
```text
Momentum Engine 이 정확히 무엇을 입력받고,
무엇을 내보내야 하는지 아직 없다.
```

---

## 3. 핵심 결정

### 3.1 Momentum Engine 은 공통 엔진

```text
Momentum Engine 은 holdings mode 와 universe mode 가 공유한다.
```

두 모드의 차이:

```text
holdings mode:
내가 이미 보유한 종목을 점검한다.

universe mode:
보유 여부와 무관하게 외부 ETF/섹터 후보군을 평가해 관찰 후보를 드러낸다.
```

### 3.2 universe mode 책임 범위 명확화 (검토 MINOR 1 반영)

**반드시 박아두는 문장:**

```text
Momentum Engine 은 universe 후보군을 직접 수집하지 않는다.
Momentum Engine 은 외부에서 주입된 candidates 목록을 평가하고,
점수 결과와 판단 사유를 반환한다.
```

"발굴" 이라는 표현은 다음 의미로 제한한다:

```text
"발굴" 은 엔진이 시장 데이터를 직접 가져와 universe 를 만드는 뜻이 아니다.
Step5A 기준의 발굴은 주입된 universe candidates 안에서
모멘텀 관찰 후보를 평가 결과로 드러내는 것을 의미한다.
```

후보군 생성 책임은 Step5A 범위 밖이다:

```text
universe 후보군을 어디서 가져올지,
어떤 ETF 를 포함할지,
데이터 소스를 무엇으로 할지는 Step5A 에서 확정하지 않는다.
```

### 3.3 추천 엔진이 아니라 후보/관찰 엔진

**허용 표현:**
- 모멘텀 후보
- 관찰 후보
- 점수 결과
- 판단 사유
- 상승 흐름 후보

**금지 표현:**
- 매수 후보
- 매도 후보
- 교체 후보
- 리밸런싱 후보
- 목표 비중
- 주문 계획

---

## 4. 최소 입력 계약

Momentum Engine 입력은 아래 3개로 정의한다:

```text
1. run_context
2. mode
3. candidates
```

### 4.1 run_context

**역할**: 이번 계산이 언제, 어떤 목적, 어떤 초안 흐름에서 만들어졌는지 나타낸다.

**최소 필드**:
```text
asof
run_id           (optional)
engine_id
engine_version
```

**주의**:
```text
run_context 는 계산 맥락이다.
투자 판단값이 아니다.
```

### 4.2 mode

**허용 값**:
```text
holdings
universe
```

**의미**:
```text
holdings:
현재 보유 종목 기반 점검

universe:
외부에서 주입된 ETF/섹터 후보군 기반 평가
```

**금지 값**:
```text
mixed
live
backtest
ml
auto_trade
```

### 4.3 candidates

Momentum Engine 은 후보 목록을 입력받는다.

**공통 후보 필드**:
```text
candidate_id
ticker
name
source_type
input_available
input_basis
```

**holdings mode 에서 추가로 가질 수 있는 필드**:
```text
source_index
account_group
quantity
avg_buy_price
market_value
market_weight_pct
pnl_rate
```

**universe mode 에서 나중에 가질 수 있는 필드**:
```text
universe_group
sector_or_theme
current_price
recent_return
trend_inputs
```

**주의**:
```text
Step5A 에서는 universe 후보군의 실제 구성, 종목 수, 데이터 소스,
trend_inputs 의 산식을 확정하지 않는다.
```

---

## 5. 최소 출력 계약

Momentum Engine 출력은 아래 개념으로 정의한다:

```text
momentum_result
```

**momentum_result 최소 필드**:
```text
engine_id
engine_version
mode
asof
summary
candidates
```

### 5.1 summary

**역할**: 이번 결과의 전체 요약을 담는다.

**최소 필드**:
```text
total_candidates
scored_candidates
excluded_candidates
summary_reason_text
```

### 5.2 candidate result

각 후보 결과는 아래 구조를 가진다:

```text
candidate_id
ticker
name
mode
is_available
score_result
reason_text
input_basis
rank             (optional)
exclusion_reason
```

**중요**:
```text
rank 는 optional 이다.
score_result 가 없거나 ranking_basis 가 없으면 rank 를 반환하지 않는다.
```

### 5.3 score_result

`score_result` 는 점수 산식 결과를 담는 자리다.
**단, Step5A 에서는 산식을 정하지 않는다.**

**최소 구조**:
```text
is_scored
score_value      (optional)
score_unit       (optional)
score_basis_text
ranking_basis    (optional)
```

**주의**:
```text
score_value 가 있다고 해서 BUY/SELL 판단이 아니다.
score_value 가 없을 수도 있다.
score_value 가 없으면 rank 도 없을 수 있다.
```

### 5.4 reason_text

**역할**: 사람이 읽을 수 있는 판단 사유.

**원칙**:
- 짧아야 한다.
- 투자 행동을 지시하지 않는다.
- 계산 불가 시 fallback 문구를 가진다.

**허용 예시 수준**:
```text
이 후보는 최근 흐름 점검 대상입니다.
현재 입력값 기준으로 상승 흐름 후보로 분류될 수 있습니다.
```

**금지**:
```text
매수하세요
비중을 늘리세요
갈아타세요
손절하세요
```

### 5.5 rank (검토 MINOR 2 반영)

`rank` 는 허용하지만 **optional** 이다.

**의미**:
```text
rank 는 출력 정렬을 위한 순서다.
Telegram Top N 정책이 아니다.
매수 우선순위도 아니다.
```

**rank 반환 조건**:
- `score_result.is_scored = true`
- `score_value` 또는 `ranking_basis` 가 존재
- 동일 결과 내에서 비교 가능한 후보가 2개 이상 존재

**rank 생략 조건**:
- `score_result.is_scored = false`
- `score_value` 없음
- `ranking_basis` 없음
- 후보 간 비교 불가

**Step5A 에서 확정하지 않는 것**:
- rank 산식
- Top N 개수
- Telegram 노출 개수
- UI 표시 방식

---

## 6. holdings mode 와 universe mode

### 6.1 공통점
- 같은 Momentum Engine 계약 사용
- 후보 목록 입력
- 후보별 score_result 출력 가능
- 후보별 reason_text 출력
- 계산 제외 후보는 실패가 아니라 `exclusion_reason` 처리
- BUY/SELL 없음

### 6.2 차이

```text
holdings mode:
보유 중인 종목의 상태를 점검한다.
기존 holdings / market_cache / draft_payload 기반이다.
현재 포트폴리오 내부 설명에 가깝다.

universe mode:
보유 여부와 무관하게 외부에서 주입된 ETF/섹터 후보군을 평가한다.
엔진이 후보군을 직접 수집하지 않는다.
아직 유니버스, 데이터 소스, 산식은 미정이다.
```

---

## 7. 데이터 저장 위치

Step5A 에서는 `momentum_result` 라는 **개념 계약만** 정의한다.

**아래는 확정하지 않는다**:
- `draft_payload` 안에 넣을지
- `factor_signals` 안에 넣을지
- 별도 `momentum_results` 파일로 둘지
- Run top-level 필드로 둘지
- DB 나 history 저장소를 만들지

**이유**:
```text
Step3 에서 draft_payload.factor_signals 는 예외적으로 허용된 키다.
Step5 에서 momentum_result 까지 무작정 draft_payload 에 넣으면
데이터 계약이 다시 불어난다.
```

**저장 위치는 Step5B 에서 판단한다.**

---

## 8. 운영 결과 기록 / AI·ML 분석 넘김

Step5A 에서는 아래만 남긴다:

```text
Momentum Engine 출력은 나중에 기록 가능한 구조여야 한다.
하지만 이번 하위 단계에서 새 저장 구조를 만들지 않는다.
```

**Step5C 에서 판단할 내용**:
- 운영 결과 기록이 기존 run 파일로 충분한가
- 별도 result artifact 가 필요한가
- AI 해석 로그가 필요한가
- ML 분석용 dataset 형태가 필요한가

**새 시스템이 필요하면 Step5 에서 구현하지 않는다**:
```text
새 저장소 / 새 DB / 새 로그 체계 / 새 분석 파이프라인이 필요하면
Step6 또는 별도 Step 으로 넘긴다.
```

---

## 9. Step5A 완료 기준 AC

```text
AC-1. Momentum Engine 이 holdings mode 와 universe mode 를 공유하는 공통 엔진으로 정의된다.
AC-2. mode 허용 값은 holdings / universe 로 제한된다.
AC-3. universe mode 에서 Momentum Engine 은 후보군을 직접 수집하지 않고, 외부에서 주입된 candidates 를 평가한다고 명시된다.
AC-4. "발굴" 은 후보군 수집이 아니라, 주입된 universe 안에서 관찰 후보를 드러내는 의미로 제한된다.
AC-5. Momentum Engine 최소 입력 계약이 정의된다 (run_context / mode / candidates).
AC-6. Momentum Engine 최소 출력 계약이 정의된다 (momentum_result / summary / candidates / score_result / reason_text / rank optional / exclusion_reason).
AC-7. rank 는 optional 로 명시된다.
AC-8. score_result 가 없거나 ranking_basis 가 없으면 rank 를 생략할 수 있다고 명시된다.
AC-9. rank 는 Telegram Top N 또는 매수 우선순위로 해석하지 않는다고 명시된다.
AC-10. score_result 는 자리만 정의하고 산식은 확정하지 않는다.
AC-11. universe mode 의 유니버스, 데이터 소스, 산식은 확정하지 않는다.
AC-12. Momentum Engine 결과 저장 위치는 Step5A 에서 확정하지 않는다.
AC-13. 운영 결과 기록 / AI·ML 분석 넘김은 Step5A 에서 구현하지 않고 Step5C 또는 다음 Step 판단 대상으로 둔다.
AC-14. BUY / SELL / 리밸런싱 / ML 학습은 포함하지 않는다.
AC-15. 코드 변경은 발생하지 않는다.
```

---

## 10. 금지사항 (Step5A 한정)

```text
- 코드 수정
- Momentum Engine 구현
- 점수 산식 작성
- 유니버스 후보군 작성
- 데이터 소스 확정
- 저장 위치 확정
- ML 연결
- UI 변경
- Telegram 문구 변경
- BUY / SELL / 리밸런싱 도입
```

---

## 11. 다음 하위 단계 진입 가드

다음 하위 단계는 **바로 구현이 아니다**.

```text
Step5B: Momentum result 저장 위치 결정
  · draft_payload 안 / factor_signals 확장 / 별도 artifact / Run top-level / 외부 저장소 중 선택
  · 과거 run 호환 정책 결정
  · OCI handoff 영향 분석

Step5C: 운영 결과 기록 / AI·ML 분석 넘김 판단
  · 기존 run 파일로 충분한지 평가
  · 별도 result artifact 또는 AI 해석 로그 필요성 판단
  · ML dataset 형태 필요성 판단
  · 새 저장소가 필요하면 Step6 또는 별도 Step 으로 분리

이후 첫 구현 STEP:
  · holdings mode 또는 universe mode 중 한쪽을 먼저 구현 (어느 쪽인지는 Step5B/C 결과에 따라 결정)
  · 첫 점수 산식 / 입력 변수 / 데이터 소스 / 유니버스(해당되면) 결정
```

위 분기는 Step5A 가 미리 박지 않는다 — Step5B/C 의 자체 설계 지시문에서 새로 결정한다.

---

## 12. 최종 선언

POC2-Step5A 는 **계약 문서화 단계** 다.

```text
이 단계는 구현 단계가 아니다.
이 단계는 점수 산식을 박는 단계가 아니다.
이 단계는 유니버스 / 데이터 소스 / 저장 위치를 박는 단계가 아니다.
이 단계는 ML 진입 단계가 아니다.

이 단계는 Momentum Engine 이
무엇을 입력받고
무엇을 내보내야 하는지를
공통 계약으로 박아두는 단계다.

다음은 위 §11 의 Step5B 에서 결과 저장 위치를 결정하는 설계 지시문 작성이다.
```
