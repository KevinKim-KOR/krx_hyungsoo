# POC5-07 — 기존 보유의 가격 비교 기준일 개발 PLAN V1

작성 2026-10-11 · 작성자: 개발자(VSCode Claude) · 수신: 설계자(웹 GPT)

```text
STATUS        = PLAN 확정 — 설계자 PASS_TO_IMPLEMENT(2026-10-11 · 재제출 없음 · 명확화 2건 반영 = §7)
DESIGN        = docs/ai_design/POC5/POC5-07_HOLDINGS_REFERENCE_DATE_DESIGN_V1.md (V1 · §9 PLAN 판정 · 끝에 전달문 원문 2건)
BASE_COMMIT   = ba7d55db
QUESTIONS     = 없음 — 설계와 충돌하는 코드 사실 없음(§6). 정해 둔 세부는 §2-6(판정에서 바꿀 수 있음)
API           = 경로 추가 0 — 기존 PUT /holdings/trade-history 에 action "reference_date" 1개 · GET 응답 필드 추가
OCI           = OCI 에서 도는 파일 변경 0 → OCI pull 불필요(§1-6)
NEW_FILES     = app/holdings_reference_date.py · tests/test_poc5_07_reference_date.py · 화면 1 + 시험 1(§2-5)
```

## 0. 요약

기준잔고(BASELINE) · 잔고 등록(REGISTER)으로 시작한 보유 기간에 **REFERENCE_DATE** 기록을 더해 '가격 비교 기준일'을 둔다. 이 기록은 계산(수량 · 원가 · 손익 · 순서 · 기간 시작/종료)에 들어가지 않고, 같은 기간의 마지막 기록 값이 현재 기준일이다(`null` = 해제). 일괄 설정 · 기간별 수정/해제는 같은 명령 하나(대상 목록 1 ~ N)이며 기존 입력 정정 일괄 저장과 같은 `request_id` 재시도 방식 · revision 확인 · `holdings_store.commit` 원자 교체를 쓴다. 시장 흐름은 기준일이 있는 기간에 '가격 비교 기준일 이후 종가 변화'를 더한다(05 기준일 · 출처 · 인접일 대체 금지 규칙 그대로). 실제 매수일은 계속 '미상'이다.

## 1. 사실조사 (현재 코드 · 실제 자료)

### 1-1. 실제 보유 (2026-10-11 · 읽기 전용)

- `state/holdings/holdings_latest.json` = 기존 형식(V1) · revision 0 · 32줄 · 종목 29 · 기록 = 가상 BASELINE 32(저장 전) · 보유 기간 32개 모두 BASELINE · 보유 중. 매매 기록 0.
- 첫 명시적 저장 때 V1 → V2 전환은 `holdings_store.materialize`(가상 ID 그대로 확정 · `app/holdings_store.py:141`)를 쓰는 기존 경로가 있다(POC5-05 · 06 시험으로 'ID 그대로 확정' 확인됨).

### 1-2. 기록 형식 · 무결성 (`app/holdings_book.py`)

- 기록 종류 `KINDS = BASELINE · REGISTER · BUY · SELL · ADJUSTMENT · VOID`(:106). 알 수 없는 종류 = 손상(:290).
- 종류별 허용 칸 `PAYLOAD_KEYS`(:123) — BASELINE · REGISTER = 수량 · 평단뿐. 다른 칸 = 손상(:196).
- 기록 공통 칸 `RECORD_KEYS`(:110) = record_id · request_id · request_hash · recorded_at · kind · position_id · cycle_id · supersedes_id · payload(+ 메모리 전용 virtual). 정정 · 취소 대상은 매매(BUY · SELL)만(:305 ~ 316 · `holdings_history._target` :305).
- **계산 경로**: `compute`(:426)가 기간의 유효 기록을 모두 `replay_cycle`(:335)에 넣는다 — 정렬 키가 `payload.seq` 를 읽고(:93) 보유 0 뒤 같은 기간 기록이 있으면 오류(:355). **REFERENCE_DATE 를 그대로 두면 정렬에서 실패하거나, 종료된 기간에 설정할 때 '보유가 0 이 된 뒤 기록'으로 거절된다 → 계산 경로에서 반드시 뺀다.**
- `next_seq`(:502) · `effective_records`(:76)는 날짜 없는 기록을 이미 건너뛴다(영향 없음).

### 1-3. 저장 · 재시도 (`holdings_store.commit` · 기존 두 방식)

- 매매 명령 1건: `record_id` = 재시도 키(`holdings_history.apply_command` :419) · 재시도 확인 → revision 확인 순서.
- 입력 정정 일괄 저장: `request_id` + 기록마다 `request_hash`(`holdings_edit.save_full_list` :32) — 같은 request_id 기록이 있으면 같은 hash = 저장 없이 그대로 응답 · 다른 hash = 409 · 그다음 revision(V2 = 같아야 · V1 = None 또는 0). 바뀐 것이 없으면 쓰지 않는다. **이번 일괄 · 단건 설정은 이 방식을 그대로 쓴다**(설계 §3 '기존 다중 기록 저장 방식').
- `commit`(:167): 잠금 → 최신 문서 → change → 쓰기 직전 `holdings.holdings_from_document` 판정(= `holdings_book.compute`) → 같은 폴더 임시 파일 · fsync · `os.replace`.

### 1-4. History · 시장 흐름

- History 기간 보기 `holdings_history_view._cycle_view`(:43): `opened_by` · `start_date`(BUY 시작만) · 사건 목록. 시장 흐름 입력 `market_flow_input_of`(:127)는 매매 사건만 넘긴다.
- 시장 흐름 `holdings_market_flow.build_market_flow`: 매매 사건마다 '기준일 → 마지막 저장일'(`_event` :408) · 실제 매수로 시작해 종료된 기간만 '첫 매수 기준일 → 마지막 매도 기준일'(`_holding_period` :451). BASELINE · REGISTER 기간 = `PURCHASE_DATE_UNKNOWN`('매수일 미상 — 매수 전후 변화 계산 안 함' :105). 비거래일 → 다음 거래일(`_BasisDays`) · 인접일 대체 금지 · 출처 비교 · KOSPI 같은 두 날짜 · 사유 문구(`REASONS` :88)는 그대로 재사용할 수 있다.
- POC5-06 검토 창은 같은 `history_of` · `market_flow_input_of` · `build_market_flow` 를 쓴다(06 코드 변경 없이 기준일 정보가 함께 흐른다 · ML 은 개인 기록을 쓰지 않음).

### 1-5. 화면

- 보유 표 버튼 줄 `HoldingsBookSection.tsx:188`([새 보유 추가] · [입력 정정]). History 기간 머리 `HistoryCycle.tsx:45 ~ 48`('기준잔고 · 매수일 미상 · 입력 평단 기준' · '잔고 등록 · 매수일 미상'). 시장 흐름 표시 `MarketFlowPanel.tsx`(`MarketFlowView` — 06 창도 같은 표시). 창 위에 창을 겹치지 않는 규칙(05 · 06).

### 1-6. OCI · 원장 · ML 영향

- OCI 에서 도는 파일(`app/holdings.py` · `target_tickers.py` · `holdings_selection_flow.py` · `holdings_risk_flow.py` · `scripts/run_holdings_publication.py`)은 `holdings_book` 을 import 하지 않는다. `app/holdings.py` 는 **이력 문서일 때만** 함수 안에서 `holdings_book` 을 불러오고(:288), OCI 파일은 늘 허용 5필드 기존 형식이다 → OCI 실행 경로 변경 0 · `app/holdings.py` 수정 불필요 · OCI pull 불필요.
- OCI 적용 payload = 현재 보유 5필드(`holdings_oci_apply._build_payload`) — REFERENCE_DATE 는 `holdings` 행을 바꾸지 않으므로 payload · hash · `pending_apply` 같음. V1 첫 전환 때 `holdings` 행에 position_id · cycle_id 가 붙어도 payload 5필드는 같다(POC5-05 와 같은 동작).
- 원장(01B · 02 · 03) · 04 리포트 · 06 ML 코드는 보유 이력을 읽지 않는다(06 은 History 표시 · 시장 흐름만).

### 1-7. KS-10 (현재 줄 수)

`holdings_book.py` 513 · `holdings_history.py` 476 · `holdings_history_view.py` 154 · **`holdings_market_flow.py` 593(백엔드 근접선 600 바로 아래)** · `api_holdings_history.py` 120 · `HoldingsBookSection.tsx` 347 · `HistoryCycle.tsx` 150 · `MarketFlowPanel.tsx` 170 · 시험 `test_poc5_05_holdings_history.py` 940 · `test_poc5_05_history_integrity.py` 787 · `test_poc5_05_market_flow.py` 539.

## 2. 구현 계획

### 2-1. 기록 · 무결성 · 계산 (`app/holdings_book.py`)

- `KINDS` 에 `REFERENCE_DATE` · `PAYLOAD_KEYS["REFERENCE_DATE"] = {"reference_date"}` — 칸이 정확히 이것 하나(빠져도 손상) · 값 = `null` 또는 YYYY-MM-DD 이며 저장일(recorded_at 의 **KST 날짜** · 판정 §9-2-1) 이하.
- 연결 검사 추가: REFERENCE_DATE 의 (position_id, cycle_id) 기간에 BASELINE · REGISTER 기록이 있어야 한다(없으면 손상 — BUY 로 시작한 기간 · 없는 기간 · 다른 줄의 기간 거절). `supersedes_id` 는 늘 null(기존 규칙상 매매만 대상 · 그대로 손상).
- 계산: `compute` 가 기간 계산(`replay_cycle`)에 넘기기 전에 REFERENCE_DATE 를 뺀다 · 기간 결과에 `reference_date`(그 기간 REFERENCE_DATE 의 저장 순서 마지막 값 · 없으면 null)를 붙인다. 수량 · 원가 · 손익 · 순서 · 종료 판정 · 기간 순서 · `holdings` 는 기준일 유무와 무관하게 같다.
- 알 수 없는 종류 손상 규칙은 그대로(새 종류 하나만 허용).

### 2-2. 명령 (새 `app/holdings_reference_date.py` · API 분기 1줄)

`PUT /holdings/trade-history` 본문 `action == "reference_date"` 이면 이 모듈로 보낸다(그 밖은 기존 `apply_command` 그대로).

```text
요청   { action: "reference_date", request_id: <UUID>, base_revision: <int ≥ 0>,
         reference_date: "YYYY-MM-DD" | null, targets: [ {position_id, cycle_id}, ... ] }   (1 ~ 200 · 겹침 없음)
검증   날짜 = 유효 · KST 오늘 이하(휴장일 · 가격 없는 날 허용) · 대상 형식 → 422
처리   commit 안에서: request_id 재시도 확인(같은 hash = 쓰기 없이 응답 · 다른 hash = 409)
       → revision(V2 같아야 · V1 = 0) 다르면 409 → 대상마다 현재 계산에서 찾기(없음 = 409 '새로고침' ·
       BUY 로 시작한 기간 = 422) → 현재 값과 같으면 '변경 없음' → 바뀌는 대상만 REFERENCE_DATE 기록
       (기록마다 새 record_id · request_id · request_hash · recorded_at) → 하나도 없으면 쓰지 않음(revision 그대로)
       → 있으면 V1 materialize · holdings 다시 계산(값 같음) · revision + 1 → 한 번 교체
응답   { revision, status, changed: [cycle_id...], unchanged: [cycle_id...] }
```

- 일괄 · 단건 모두 이 명령(단건 = 대상 1개). 일부만 저장되는 경로 없음(전부 판정 뒤 한 번 쓰기).

### 2-3. History 조회 (`app/holdings_history_view.py`)

- 기간 보기에 `reference_date` 추가(BASELINE · REGISTER 기간만 값 · BUY 기간 = null). REFERENCE_DATE 는 사건 목록 · 취소 목록에 넣지 않는다(매매가 아님).
- `market_flow_input_of` 의 기간 입력에 `reference_date` 추가.

### 2-4. 시장 흐름 (`app/holdings_market_flow.py`)

- 입력 기간에 `reference_date`(BASELINE · REGISTER 기간만 허용 · 그 밖은 형식 오류).
- 기준일이 있으면 `reference_flow` 1항목 = '가격 비교 기준일 이후 종가 변화' — 기준일의 기준 거래일(`_BasisDays.of` · 실제 사용일 표시) → 그 종목 마지막 저장일 · 같은 두 날짜 KOSPI. 기존 `_event` 와 같은 규칙(가격 없음 · 마지막 저장일이 기준일보다 이름 · 개별주 · 출처 비교 불가 = 기존 사유 문구).
- 종료된 기간에 실제 매도가 있으면 기존 '보유 기간' 항목을 '가격 비교 기준일 → 마지막 매도 기준일'로 계산(기준일이 매도 기준일보다 늦으면 기존 '구간 끝이 시작보다 이름' 사유). 매도 뒤 변화는 기존 매도 사건 항목 그대로. 매도 없는 입력 정정 종료 = 기존 그대로(가상 매도일 없음).
- 기준일이 없으면 지금과 같은 출력(`purchase_date_unknown` · 사유 그대로). `purchase_date_unknown` 은 기준일이 있어도 true(실제 매수일 미상 유지).
- 줄 수: 기존 `_event` 본문을 날짜 하나를 받는 도우미로 나눠 재사용 — 593 → 640 이하 목표(650 넘으면 표시 문구 · 상수를 분리).

### 2-5. 화면

- `HoldingsBookSection.tsx`: 버튼 줄에 [가격 비교 기준일 설정] → 새 `ReferenceDateDialog.tsx`(날짜 한 칸 · 초기값 2026-01-02 · 대상 = 보유 중 · BASELINE/REGISTER 로 시작 · 기준일 없음 — 종목명 · 종목코드 · 계좌 목록과 건수 · [설정]). 대상 0 이면 안내만. 기존 폼 폭 · 정렬 재사용.
- `HistoryCycle.tsx`: BASELINE · REGISTER 기간 머리에 '실제 매수일: 미상' · '가격 비교 기준일: YYYY-MM-DD'(없으면 '없음') · [수정/해제] → 같은 줄 안에서 날짜 칸 · [저장] · [해제] · [취소](창 위 창 없음). 종료된 기간도 같음. BUY 기간은 기존 표시.
- `MarketFlowPanel.tsx`(`MarketFlowView`): `reference_flow` 를 '가격 비교 기준일 이후 종가 변화'로 표시(06 창에도 그대로 보임). '매수 후 수익률' · 손익 문구 없음.
- `frontend/lib/api/holdingsHistory.ts`: 기간 `reference_date` · 명령 함수 · 시장 흐름 타입.
- 저장 뒤 보유 표 · History 를 다시 읽는다(기존 저장 뒤 동작과 같음).

### 2-6. 정해 둔 세부 (질문 아님 · 판정에서 바꿀 수 있음)

1. 일괄 설정의 '이미 설정된 기간 덮어쓰지 않음'은 화면이 기준일 없는 기간만 대상으로 보내고 서버가 base_revision 일치를 확인해 보장한다(그 사이 다른 화면이 설정했으면 revision 이 달라 409). 서버에 '덮어쓰기 금지' 별도 표지를 두지 않는다.
2. 같은 기간의 유효 값 = REFERENCE_DATE 의 저장 순서 마지막 기록. 기록은 지우지 않는다(해제 = `null` 기록).
3. 기준일 상한은 KST 오늘(입력) · 저장일의 KST 날짜(무결성 · 같은 날짜 축) 둘 다. 하한은 두지 않는다(가격 없으면 시장 흐름이 '자료 없음').
4. 시장 흐름에서 종료된 기간도 '기준일 이후 종가 변화'(기준일 → 마지막 저장일)를 함께 보인다(설계 §4 첫 문장 '실제 매수일을 모르는 기간은 … 마지막 저장일까지').
5. 06 검토 창 '내 거래'에는 손대지 않는다(시장 흐름 표시로 기준일 변화가 보임 · ML 입력 · 결과 불변).
6. 기준일을 매수일 · 매수 거래로 이름 붙이지 않는다(표기 = '가격 비교 기준일'). History 기간 머리에는 '실제 매수일: 미상'과 '가격 비교 기준일: 날짜/없음'을 **함께** 표시한다(판정 §9-2-2).

## 3. 검증 계획 (설계 §6 1:1 · 줄인 방식)

| 설계 §6 | 시험 |
|---|---|
| 1 계산 불변 | V1 첫 전환 · 실제 매매가 있는 V2(매수 · 분할매도 · 입력 정정 포함) 각각 설정 · 수정 · 해제 전후 수량 · 평단 · 원가 · 실현손익 · 기간 연결 · `holdings` · OCI payload / hash · `pending_apply` 같음 · V1 가상 ID 그대로 |
| 2 일괄 원자성 | 여러 대상 한 번 저장 · 같은 request_id 재시도(쓰기 0 · 기록 중복 0) · 같은 ID 다른 내용 409 · 오래된 revision 409 · 없는 기간 409 · 교체 직전 실패(쓰기 실패 주입) = 파일 그대로 |
| 3 구분 | 현재 · 종료 기간 · 다른 계좌 같은 종목 · 재매수 새 기간(이전 기준일 복사 없음) · BUY 기간 거절 · 같은 값 재설정 · 미설정 해제 = 변경 없음(revision 그대로) · History 에 BUY · 매수일로 안 보임 |
| 4 날짜 · 표시 | 유효 · 미래(422) · 휴장일(다음 거래일 · 실제 사용일) · 기준일 종가 없음 · 마지막 저장일 < 기준일 · 기준일 > 매도 기준일 · 개별주 · History 열기 · 저장에 외부 조회 · ML 0 |
| 5 06 불변 | 같은 tmp 가격 자료로 기준일 설정 전후 06 ML 표본 · MAE · 추정값 같음 · 문서 hash 만 다름 |
| 무결성 | REFERENCE_DATE 칸 누락 · 추가 칸 · 잘못된 날짜 · 저장일 이후 날짜 · BUY 기간 · 다른 줄 기간 · supersedes 있음 = 손상 · 기준일 없는 기존 V2 그대로 읽힘 |

- 화면 vitest: 일괄 창(대상 · 건수 · 대상 0 안내 · 저장 요청 형태) · History 수정/해제 · 시장 흐름 표시 · 기존 05 · 06 화면 시험 회귀.
- 독립 검토 1회 · 변이 시험(저장소 사본) · 정적 검사 · 관련 회귀 · 마지막 전체 회귀 1회 + 라이브 해시(state/logs 같은 범위) · KS-10. 라이브 보유에 시험 기록을 넣지 않는다(tmp + `tests/_live_guard.py`).

## 4. 문서 · 배포

- OCI 에서 도는 파일 변경 0 → OCI pull · 첫 영업일 확인 없음(§1-6).
- 결과서 → 검증자 → 설계자 RESULT → 커밋 · push(사용자 승인) → PC 재기동 → 실화면(사용자가 실제 기준일을 설정 · History · 시장 흐름 확인) → 종료 기록 · 인계.
- PROGRAM_TRUTH(화면 · API 표 · 기록 종류) · STATE 갱신.

## 5. 사용자 확인 항목

1. 실화면에서 사용자가 실제로 `2026-01-02`(또는 원하는 날)를 일괄 설정하면 PC 보유 파일이 V1 → V2 로 처음 바뀐다(첫 저장 · 수량 · 평단 · OCI 보유 그대로 · 되돌리려면 History 에서 해제 — 파일은 V2 로 남음). 배포 전 V1 백업 `state/holdings/backup/holdings_latest_pre_POC5-05_20261009.json` 이 이미 있다.
2. 별도 목업 확인은 없다(설계 §7) — 실화면에서 버튼 위치 · 창 · History 표시를 함께 본다.

## 6. 설계자 질문

없음. 설계 §3 의 '경로 추가 없이' · '기존 다중 기록 저장 방식' · '알 수 없는 종류 일괄 무시 금지' · §5 의 'OCI 실행 경로 확인'을 현재 코드로 모두 지킬 수 있다(§1 · §2). 계산 경로에서 REFERENCE_DATE 를 빼야 한다는 점(§1-2)은 설계 §3 'REFERENCE_DATE 는 … 계산에 참여하지 않는다'와 같은 방향이다.

## 7. 설계자 판정 반영 (2026-10-11 · PASS_TO_IMPLEMENT · 원문 = 설계서 §9 · 끝에 전달문 원문)

- 계산 제외 · 단건 / 일괄 저장 · 재시도 · 무결성 · 시장 흐름 · OCI · ML · 화면 · 세부 6건 모두 수용 — 본문 그대로 구현한다.
- **명확화 1 — 저장일 상한 = recorded_at 의 KST 날짜**(§2-1 · §2-6-3 정정): 무결성은 recorded_at 을 시각으로 읽어 KST 날짜로 바꾼 뒤 기준일과 비교한다(입력의 'KST 오늘 이하'와 같은 축). KST 자정 부근 저장(예: UTC 표기 전날 15시대 = KST 다음날)을 시험에 넣는다.
- **명확화 2 — History 문구**(§2-6-6 정정): 기간 머리에 '실제 매수일: 미상'과 '가격 비교 기준일: 날짜/없음'을 함께 표시한다. 시장 흐름의 `purchase_date_unknown = true` 는 기준일 종가 비교 항목을 숨기는 조건으로 쓰지 않는다.
- 기준일 해제는 비교 설정을 지우는 동작이며 V1 파일 복구가 아니다(§5-1 과 같음). 실제 데이터 · 보유 수량을 바꾸는 시험 거래는 만들지 않는다.
- 다음: backend → frontend → 격리 시험 · 관련 회귀 · 전체 회귀 · 정적 검사 → 결과서(실제 변경 파일 · OCI 경로 · 계산 불변 결과) → 검증자.
