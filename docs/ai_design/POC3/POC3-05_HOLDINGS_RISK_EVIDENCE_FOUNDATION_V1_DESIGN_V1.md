# POC3-05 Holdings Risk Evidence Foundation V1 — 설계서

- 문서 번호: `POC3-05`
- 작성일: `2026-08-02`
- 상태: `설계 완료 · 레드팀 검토 대기`
- 선행 상태: `POC3-04 승인·알림 역할 분리 PASS / CLOSED`
- 다음 게이트: `레드팀 PASS → 개발 PLAN 작성 및 사실확인`

---

## 0. 결론

이번 Step은 새 위험 점수나 매매 신호를 만드는 작업이 아니다.

기존 보유 현황, 최근 가격 흐름, KODEX200 대비 흐름, 기존 급락 주의 신호,
데이터 상태를 종목 단위로 묶어 다음 질문에 답하게 한다.

> 하락장 아침에 이 화면을 보고 오늘 먼저 확인할 보유 종목과 그 이유를 1분 안에 고를 수 있는가?

내부 Step 명칭은 `Risk Evidence`지만 사용자 화면에서는 **`보유 ETF 확인 근거`**로 표현한다.
`위험`, `안전`, `정상 종목` 같은 확정 판정은 사용하지 않는다.

---

## 1. 왜 지금 해야 하는가

### 1.1 현재 문제

POC3-01~04를 통해 Dashboard, Judgment Workbench, 메뉴, OCI 적용·알림 화면은 정리됐다.
그러나 보유 종목을 볼 때는 사용자가 여전히 다음 자료를 직접 조합해야 한다.

- 평가 비중·평가손익
- 5일·20일 가격 흐름
- KODEX200 대비 흐름
- 기존 급락 주의 신호
- NAV·구성종목·데이터 상태

즉, 화면은 정리됐지만 **오늘 무엇부터 볼지 고르는 일**은 그대로 남아 있다.

### 1.2 사용자에게 생기는 도움

완료되면 사용자는 다음을 할 수 있다.

- 전체 보유 종목을 하나씩 열지 않고 최근 흐름이 낮은 종목부터 본다.
- 종목별 `5일·20일 흐름`, `KODEX200 대비`, `평가 비중`을 한 행에서 확인한다.
- 기존 급락 주의 신호와 정확히 일치한 보유 종목을 별도로 확인한다.
- 데이터 부족을 `문제없음`으로 오인하지 않는다.
- Dashboard에서 찾은 종목을 Holdings·Workbench의 같은 근거로 이어서 본다.

핵심 효과는 위험을 대신 맞혀주는 것이 아니라,
직장인 투자자인 사용자의 제한된 확인 시간을 어디에 먼저 쓸지 줄여주는 것이다.

### 1.3 하지 않으면 남는 문제

- Dashboard의 `내가 가진 ETF`가 실제 확인 대상과 이유를 제시하지 못한다.
- 보유 상태와 시장 흐름을 계속 머릿속에서 조합해야 한다.
- 데이터 미수집과 위험 없음이 혼동될 수 있다.
- 이후 판단 초안·AI Sessions·ML을 연결해도 근거 단위가 정리되지 않는다.
- 결국 PC 판단 화면보다 증권사 앱을 다시 보게 된다.

---

## 2. 현재 위치와 단일 목표

### 2.1 문서 순서 판정

초기 마스터의 `POC3-05 Data Integrity Gate`는 최신 통합지도에서 순서가 바뀐 과거 계획이다.
이번 Step은 최신 통합지도와 직전 Closeout을 따라 다음으로 확정한다.

- `POC3-05`: Holdings Risk Evidence Foundation
- VIX stale·시장 위치·freshness 완결성: 이후 `Market Position & Data Quality Completeness` Lane

이번 Step이 사용하는 데이터의 stale·unavailable은 숨기지 않지만,
VIX 자체는 보유 종목 확인 순서를 만드는 입력으로 사용하지 않는다.

### 2.2 단일 목표

```text
기존에 계산·저장·조회되는 보유 evidence만 재사용해,
보유 종목별 최근 흐름·시장 대비·보유 영향·기존 주의 신호·데이터 상태를
하나의 읽기 전용 확인 구조로 정리하고,
Dashboard → 내가 가진 ETF → Judgment Workbench에서 같은 의미로 연결한다.
```

이번 Step은 위험 구간 분류 모델을 확정하는 단계가 아니다.

---

## 3. 확정 설계 판단

### 3.1 사용자 화면 용어

| 내부 의미 | 사용자 표시 |
|---|---|
| 기존 explicit warning과 ticker 일치 | `기존 주의 신호와 일치` |
| 유효값의 단순 정렬 | `최근 5거래일 수익률 낮은 순` |
| KODEX200 대비 값 | `KODEX200 대비 20일` |
| stale·partial·unavailable·not_loaded | `자료 확인 필요` |
| 신호 source 미조회·실패 | `주의 신호 확인 불가` |

`저위험`, `중위험`, `고위험`, `위험도`, `안전`, `매도 필요`는 사용하지 않는다.

### 3.2 확인 대상을 만드는 방식

종합 위험 순위나 점수를 만들지 않고 다음 세 관점으로 분리한다.

1. **기존 주의 신호**
   - 기존 explicit signal과 보유 ticker가 정확히 일치한 종목
2. **최근 흐름 낮은 순**
   - 유효한 기존 5거래일 수익률을 오름차순 정렬
   - Dashboard에는 최대 3건
   - 동률은 ticker 오름차순
3. **자료 확인 필요**
   - 기존 상태가 stale·partial·unavailable·not_loaded인 종목
   - 투자 위험과 섞지 않고 별도 표시

`최근 흐름 낮은 순`은 화면 정렬일 뿐 위험 점수·저장 rank·signal이 아니다.
전체 Holdings 표에서는 평가 비중, 평가손익, 5일 흐름, KODEX200 대비를 로컬 정렬할 수 있다.

### 3.3 기존 급락 주의 신호의 경계

기존 `-10%` 급락 기준은 초기 운영값이며 검증된 투자 기준이 아니다.

- frontend에서 `-10%`를 다시 계산하거나 하드코딩하지 않는다.
- 기존 source가 반환한 `falling_candidate` 또는 동등한 explicit signal만 재사용한다.
- ticker와 기준일이 확인될 때만 일치 표시한다.
- source가 unavailable이면 `신호 없음` 또는 `0건`으로 표시하지 않는다.
- 일치하지 않는 종목을 `안전` 또는 `정상`으로 해석하지 않는다.
- threshold 적정성 검증은 이번 Step에 넣지 않는다.

### 3.4 MA20/MA60의 경계

MA20/MA60은 시장 전체의 후행 참고값이며 개별 ETF 위험 판정이 아니다.

- 현재 시장 위치와 기존 한계 설명은 공통 참고로 유지한다.
- 개별 종목 판단에는 동일 기간의 기존 KODEX200 초과수익만 사용한다.
- 시장 상태와 ETF 수익률을 결합한 `국면 불일치` 신호는 만들지 않는다.
- 시장 국면으로 종목 순서를 자동 변경하지 않는다.

---

## 4. Evidence 사용 계약

개발 PLAN에서 실제 필드명·단위·coverage를 확인하되 의미는 아래 경계를 따른다.

| Evidence | 기존 근거 | 이번 Step 사용 | 허용 범위 |
|---|---|---|---|
| 보유 현황 | 기존 Holdings 평가 응답 | 종목명·ticker·평가액·평가 비중·평가손익 | 표시·로컬 정렬 |
| 단기 흐름 | 기존 Holdings Market Evidence | 5일·20일 수익률 | 표시·5일 오름차순 정렬 |
| 시장 대비 | 기존 Holdings Market Evidence | KODEX200 대비 20일 | 표시·로컬 정렬 |
| 기존 급락 주의 신호 | 기존 Universe/Falling 결과 | ticker 정확 일치 시 표시 | 기존 신호 재표시만 |
| 데이터 상태 | 기존 availability/status/asof | stale·partial·unavailable·not_loaded 구분 | `자료 확인 필요` 분리 |
| 가격 차트 | Workbench 기존 선택 ticker 시계열 | 선택 상세 lazy 조회 | 목록 일괄 조회 금지 |
| NAV·구성종목·중복률 | 기존 상세 evidence | 선택 상세 참고 | 위험 사유로 승격 금지 |
| 시장 상태 | Dashboard 기존 시장 위치·MA20/MA60 | 공통 참고 | 개별 종목 판정 결합 금지 |

사용하지 않는 evidence:

- stale 상태인 VIX
- Holdings에 직접 제공되지 않는 `drawdown_20d`
- 신규 변동성·거래량·수급·시장 폭 지표
- 친구 프로젝트의 회귀 기울기·deadband·급변 threshold
- ML baseline·예측값
- 과거 PENDING run 또는 수동 미리보기 run

데이터 정직성 원칙:

- 서로 다른 기준일을 하나로 합치지 않는다.
- coverage는 `계산 가능 N/M · 확인 불가 K`로 표시한다.
- `not_loaded`와 `unavailable`을 구분한다.
- 값 일부만 있으면 `partial` 의미를 유지한다.
- 신호 source가 unavailable이면 일치 건수를 `0건`으로 만들지 않는다.
- ETF 외 보유 자산이 있어도 종목 유형을 신뢰할 계약이 없으면 임의 제외하지 않는다.

---

## 5. 화면 정보 구조

### 5.1 `오늘의 투자 점검` Dashboard

현재 `내가 가진 ETF` 영역을 다음 구조로 완성한다.

- 기존 보유 종목 수·총평가액·평가손익
- 기존 주의 신호 source 상태와 일치 종목
- 최근 5거래일 수익률 낮은 보유 종목 최대 3건
- 자료 확인 필요 건수와 대표 사유
- 각 항목의 기준일·coverage
- `보유 ETF 확인 근거 보기`

Dashboard는 상세 표를 복제하지 않는다.
`위험 종목 N건`, `현재 위험 없음`, `문제없음` 같은 문구를 사용하지 않는다.

### 5.2 `내가 가진 ETF` 화면

기존 보유 입력·저장 기능과 읽기 전용 확인 영역을 분리한다.

읽기 전용 영역:

- 제목 `보유 ETF 확인 근거`
- 기준일·coverage·자료 확인 필요 요약
- `전체 / 기존 주의 신호 / 자료 확인 필요` 빠른 보기
- 한 종목 한 행의 고밀도 표
- ETF명·ticker, 평가액·비중·손익, 5일·20일, KODEX200 대비, 신호 일치, 기준일, 데이터 상태
- 선택 종목 상세 펼침: 기존 가격 차트, NAV·괴리율, 구성종목·중복률, unavailable 사유

기존 입력·수정·저장 영역:

- 기능·버튼·저장 의미 유지
- 확인 근거 영역과 시각적·문맥적으로 분리
- evidence를 수정하거나 저장하는 기능처럼 보이지 않게 함

같은 ticker가 여러 계좌·행에 있을 때는 기존 Holdings 계약을 따른다.
기존 계약이 명확하지 않으면 임의 합산하거나 중복 제거하지 않는다.

### 5.3 Judgment Workbench

- `보유`와 `확인 필요` 보기에 같은 사용자 문구와 상태 의미를 적용한다.
- Dashboard·Holdings와 동일 ticker·동일 snapshot이면 같은 값과 상태를 표시한다.
- 선택 상세와 가격 차트의 현재 lazy 조회 계약을 유지한다.
- 별도 위험 계산이나 Holdings 저장 기능을 복제하지 않는다.

### 5.4 화면 연결

```text
오늘의 투자 점검
→ 보유 ETF 확인 근거
→ 선택 종목 상세
→ 필요 시 Judgment Workbench·ETF Exposure·데이터 상태
```

기존 menu key와 화면 전환 방식을 재사용한다.
신규 메뉴·route·독립 Risk Dashboard는 만들지 않는다.

---

## 6. 개발 전 사실확인

전체 저장소를 다시 조사하지 않고 다음 직접 경로부터 확인한다.

- `오늘의 투자 점검`의 `내가 가진 ETF` 렌더 경로
- `HoldingsClient`
- `JudgmentWorkbenchView`의 보유·확인 필요·선택 상세
- `GET /holdings/enriched` 소비 경로
- `GET /holdings/market-evidence/latest` 소비 경로
- `UniverseRefreshPanel`의 Falling 결과 소비 경로
- 선택 ticker 가격 시계열의 기존 lazy 조회 경로

PLAN에는 다음 사실확인 결과가 필요하다.

| 확인 항목 | 필수 결과 |
|---|---|
| 보유 행 식별 | ticker·계좌 중 현재 UI가 무엇을 한 행으로 보는지 |
| 수치 필드 | 평가 비중·평가손익·5일·20일·KODEX200 대비 필드명과 단위 |
| 상태·기준일 | 실제 status 값과 Holdings·Evidence·Falling 각각의 asof |
| coverage | 전체 보유 중 evidence 계산 가능 종목 수 |
| Falling 연결 | 보유 ticker와 exact match 가능한 읽기 경로 여부 |
| 호출 구조 | N+1 없이 목록을 채울 수 있는지 |
| 화면 연결 | Dashboard에서 Holdings 해당 영역으로 이동하는 기존 방식 |
| 공통 의미 | 세 화면이 파생 로직을 중복 구현하지 않을 방법 |

다음 조건이면 개발자가 추측하지 않고 설계자에게 복귀한다.

1. 수치 단위나 의미가 화면별로 다르다.
2. ticker를 안정적으로 연결할 수 없다.
3. 동일 ticker 복수 행 처리에 의미가 다른 선택지가 둘 이상이다.
4. 목록에 신규 endpoint 또는 ticker별 N+1 호출이 필요하다.
5. stale 판정에 신규 날짜 threshold가 필요하다.
6. 급락 신호를 읽을 때 run 생성·저장·Telegram·OCI 부수효과가 생긴다.
7. 목표 충족에 신규 factor·formula·threshold·label이 필요하다.

Falling 연결만 `UNAVAILABLE`이면 해당 영역을 만들지 않고 PLAN에 기록한다.
핵심 Holdings evidence까지 불가능하면 `BLOCKED`다.

---

## 7. 한 설계 안의 순차 개발 게이트

### A구간 — Evidence 계약 확정

- §6의 필드·단위·coverage·행 식별 확인
- `DIRECT / COMPOSE_SAME_SEMANTICS / UNAVAILABLE` 분류
- 신규 판정이 필요한 항목은 구현하지 않고 설계자에게 복귀

A는 확정 PLAN의 사실 근거다. 계약 확정 전 B 코딩에 착수하지 않는다.

### B구간 — `내가 가진 ETF` 확인 근거

- 읽기 전용 요약·표·선택 상세
- 기존 주의 신호·최근 흐름·자료 확인 필요 분리
- 입력·저장 영역과 역할 분리

개발 후 사용자 실화면 확인을 받고, 미통과하면 B만 수정한다.

사용자 확인 B:

1. 1분 안에 먼저 볼 종목과 실제 이유를 찾을 수 있는가
2. 매매 지시나 위험 확정처럼 보이지 않는가
3. 입력·저장 기능과 읽기 전용 근거가 혼동되지 않는가

### C구간 — Dashboard·Workbench 연결

- Dashboard 압축 요약과 상세 이동
- Workbench에 같은 evidence 의미 적용
- 세 화면의 값·상태·기준일 정합성 확인

개발 후 사용자 실화면 확인을 받고, 미통과하면 C만 수정한다.

사용자 확인 C:

4. Dashboard에서 발견한 종목을 상세에서 바로 이어서 볼 수 있는가
5. 세 화면이 같은 종목을 서로 다르게 설명하지 않는가
6. 기존 주요 기능을 빠뜨리지 않고 찾을 수 있는가

C 통과 후에만 전체 검증과 최종 PASS로 이동한다.

---

## 8. 유지할 것과 하지 않는 것

유지:

- Holdings 입력·수정·저장 계약
- Dashboard 시장 위치·정비 큐
- Workbench 읽기 전용 역할
- Market Discovery 갱신·후보 계산 역할
- 선택 종목 가격 시계열 lazy 조회
- NAV·구성종목·중복률의 기존 의미
- OCI·Telegram·PARAM·scheduler 계약
- 기존 menu key·화면 전환 경로

하지 않음:

- 신규 API·DB·table·source·proxy
- 신규 factor·formula·threshold·label
- 위험 점수·등급·종합 순위 저장
- ML·백테스트·튜닝
- VIX 적재 수정·freshness 기준 신설
- drawdown·변동성·거래량·수급 신규 계산
- 구성종목 source 확대
- BUY·SELL·손절·교체·자동 비중 조정·주문
- Telegram 문구·발송 조건·운영 빈도 변경
- 신규 메뉴·route·독립 화면·모바일 UI

---

## 9. 완료 기준 AC

1. `POC3-04 PASS / CLOSED`와 기존 메뉴·route가 유지된다.
2. 보유 입력·수정·저장 기능과 저장 의미가 바뀌지 않는다.
3. 보유 종목마다 가능한 범위의 평가 비중·손익·5일·20일·KODEX200 대비 값과 기준일을 한 행에서 확인할 수 있다.
4. 5일 낮은 순은 기존 유효값의 로컬 정렬이며 위험 점수·저장 rank·signal을 만들지 않는다.
5. 기존 급락 주의 신호는 source가 직접 제공하고 ticker·기준일이 확인될 때만 일치 표시된다.
6. source가 unavailable일 때 `신호 없음`·`0건`·`안전`으로 표시하지 않는다.
7. stale·partial·unavailable·not_loaded가 `자료 확인 필요`로 분리되고 값 `0`이나 `정상`으로 대체되지 않는다.
8. Dashboard에서 최근 흐름 낮은 종목 최대 3건, 신호 상태, 자료 확인 필요, 기준일·coverage를 확인할 수 있다.
9. Dashboard에서 기존 Holdings 화면의 확인 근거 영역으로 이동할 수 있다.
10. Holdings의 읽기 전용 확인 영역과 입력·저장 영역이 혼동되지 않는다.
11. Dashboard·Holdings·Workbench가 동일 ticker·snapshot을 서로 다르게 해석하지 않는다.
12. 선택 상세 외 목록에서 ticker별 N+1 가격 시계열 호출이 없다.
13. 신규 API·DB·source·factor·formula·threshold·label·scheduler·OCI·Telegram 변경이 0건이다.
14. 사용자 화면에 `저위험`, `고위험`, `안전`, `매도`, `손절`, `BUY`, `SELL` 문구가 없다.
15. Frontend 변경 범위 테스트·lint·build와 B·C 사용자 실화면 확인이 통과한다.
16. 실제 데이터 화면에서 사용자가 1분 안에 먼저 확인할 종목과 수치 근거를 찾을 수 있다.

AC 1~16 중 하나라도 충족하지 않으면 `PASS / CLOSED`로 판정하지 않는다.

---

## 10. BACKLOG 후보

### 10.1 종합 위험 구간 분류

이 항목은 factor·threshold·label 확정으로 범위가 커지므로 BACKLOG로 넘기는 것이 맞다.

- **보류 사유:** Q6가 OPEN이며 운영·Outcome 근거 없이 위험 구간을 정의할 수 없음
- **보류된 위험:** 확인 순서는 줄여주지만 위험 수준을 정량 비교하지 못함
- **재검토 트리거:** First Real Decision Cycle과 Decision Outcome Ledger에 실제 사례가 누적될 때

### 10.2 기존 급락 기준의 기간·threshold 검증

이 항목은 백테스트와 운영 기준 변경으로 커지므로 BACKLOG로 유지하는 것이 맞다.

- **보류 사유:** `-10%`는 1개월 기준 초기 운영값임
- **보류된 위험:** 너무 늦거나 민감해 실제 확인 시점을 놓칠 수 있음
- **재검토 트리거:** 신호가 2회 이상 발생하거나 사용자가 `이미 많이 하락한 뒤에 나온다`고 판정할 때

### 10.3 시장 국면과 개별 ETF의 불일치 판정

이 항목은 신규 결합 규칙이 되므로 BACKLOG로 넘기는 것이 맞다.

- **보류 사유:** MA20/MA60과 개별 ETF를 결합할 검증된 기준이 없음
- **보류된 위험:** 시장과 반대로 움직이는 보유 ETF를 별도 신호로 설명하지 못함
- **재검토 트리거:** KODEX200 대비 evidence만으로 판단이 반복해서 막히고 실제 사례가 Ledger에 기록될 때

---

## 11. Closeout과 다음 순서

최종 PASS 후 다음을 한 번에 갱신한다.

- `docs/STATE_LATEST.md`: 상태·revision·사용자 실화면 결과
- 통합 구현지도: P-06·B-003 판정과 다음 실제 Lane 하나
- `docs/backlog/BACKLOG.md`: 실제 트리거가 충족된 조건부 항목만
- RESULT: A 계약, B·C 사용자 확인, 검증 결과

진행 순서:

```text
본 설계서
→ 레드팀 검토
→ PASS 또는 수용 사항 반영 전체 통합본
→ 개발 PLAN·사실확인
→ A 계약 확정
→ B 구현·사용자 확인
→ C 연결·사용자 확인
→ 검증자 검증
→ RESULT·STATE·통합지도 Closeout
→ 설계자 PASS / CLOSED 판정
```

레드팀 PASS 전에는 개발자용 최종 지시문이나 구현 착수 지시를 작성하지 않는다.

문서 끝.
