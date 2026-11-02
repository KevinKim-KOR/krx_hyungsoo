# POC6-17 개발 PLAN V1 — OCI 수급 보관본의 PC 반영과 비교 기준일 설명

작성 2026-11-02 · 작성자: 개발자(VSCode Claude) · 수신: 설계자

```text
STATUS   = PLAN 제출(2026-11-02 · 설계 V1 §7 다섯 묶음 · 질문 2)
           → 설계자 PLAN 판정 PASS_WITH_REQUIRED_CORRECTIONS(2026-11-02 · Q1 (a) · Q2 (a) · §4 보완 · PLAN 재제출 없음 · §8 반영)
           → 구현 · 시험(2026-11-02 · 결과서 docs/ai_result/POC6/POC6-17_OCI_INVESTOR_FLOW_PC_IMPORT_AND_DATE_EXPLANATION_RESULT.md)
           → 검증자 r1 REJECTED(F1 OCI 수집 실패 우선 · 반영 실패 조합) → 정정(결과서 §4-3) → 검증자 r2 VERIFIED(격리 구현 범위 · 결과서 §12) → 설계자 RESULT PASS(2026-11-02 · 결과서 §13)
           → 사용자 승인 · 실제 PC 반영(2026-11-02 21:48 KST · (나) 단독 실행 · 수급 · D 10-30 · 결과서 §14) → 구현 커밋 d2da9490 push → IMPLEMENTED_VERIFIED_CLOSED(2026-11-02 · 결과서 §15)
DESIGN   = docs/ai_design/POC6/POC6-17_OCI_INVESTOR_FLOW_PC_IMPORT_AND_DATE_EXPLANATION_DESIGN_V1.md
판정     = docs/ai_design/POC6/POC6-17_OCI_INVESTOR_FLOW_PC_IMPORT_AND_DATE_EXPLANATION_PLAN_DECISION_2026-11-02.md
조사 요청 = docs/ai_design/POC6/POC6-17_MARKET_FLOW_FRESHNESS_DIAGNOSIS_REQUEST_V1.md(회신은 §0)
확인     = 2026-11-02 18:13 ~ 18:19 KST(약 6분 · 상한 30분) · 코드 읽기 · PC 운영 DB 읽기 전용(mode=ro) · PC 보관 사본 읽기
           · 새 외부 호출 · pull · 수집 · DB 쓰기 · OCI 접속 0
```

## 0. 조사 회신 핵심(2026-11-02 17:47 ~ 17:52 KST · 설계 §1 수용)

- PC 수급 마지막 날짜 10-22(저장 10-23 19:31 KST) · OCI 운영 표 10-30(저장 11-02 09:40 KST). 코스피 · 원/달러 · WTI 는 PC 도 10-30.
- 11-02 10:09 KST PC 갱신의 수급 단계만 실패: 키움 토큰 '코드 3 · 8050 IP 미등록'(백엔드 로그). 갱신 전체는 `completed`.
- 끝일 D = 코스피 날짜 ∩ 외국인 수급 날짜의 마지막(`app/supply_fx_oil_context.py:132-133`) → 1M · 3M · 6M · YTD 끝 모두 10-22.
- 05 `pull` 은 보관 사본만 PC `state/ml/evidence/` 로 복사하며 PC 운영 표에 쓰는 코드는 없음.

## 1. 입력 연결(§7-1)

| 항목 | 실측 |
|---|---|
| PC 보관 사본 | 완료 묶음 18(일일 수집 `DAILY_COLLECTION` 14 · 연구 4) · 목록 문제 0. 일일 수집 수급 구역: OK 12 · FAILED 2(10-22 초기 2건 '키움 인증 정보 없음' · object 0) |
| 수급 object 한 개 | `{"date","index_close","nets":{13분류: 정수 원},"observed_at"}` · 441바이트 JSON · 단위 = 원(키움 억원 × 1억 이미 적용) · `observed_at` = OCI 확보 시각(UTC) |
| 성공 구분 | manifest `sources.investor_flow` = `status`(OK/PARTIAL/FAILED) · `received`(날짜) · `objects`(같은 순서 hash) · `failed` · `not_attempted` · `db_upsert` · `mismatch`. object 는 OCI 가 그날 OCI 코스피 종가와 지수값을 대조한 뒤에만 저장(`supply_fx_oil_refresh.py:177 · 182`) |
| 보관 범위 | 수급 object 475개 · 262일(2025-09-30 ~ 2026-10-30) · 전부 hash 일치 · 읽기 가능 |
| 재사용할 검증 | `store.list_runs`(schema · run_id · kind · status · published_at) · `store.read_object`(hash) · manifest `objects` 크기 대조(`verify_run`) |
| 가져오기 | `scripts/run_ml_evidence.py pull` → `transfer.pull`(SSH · 시간 상한 목록 60초 · scp 300초 단위 · 이미 받은 묶음도 매번 재검사) |

## 2. 쓰기 · 정정(§7-2)

- **대상 표**: `market_investor_flow_daily` · 키 `(market, trade_date, investor)` · 칸 `net_value`(정수 원) · `source` · `collected_at`. PC 행 3,328개 전부 `source = KIWOOM_KA10051_KRX` · `collected_at` = PC 저장 시각.
- **최초 전환 충돌**: 없음. 겹치는 3,328행이 보관본 최신 판과 값이 모두 같다. OCI 판 사이 정정(같은 날짜 · 분류 다른 값)도 0이다. 보관본에만 있는 날짜는 10-23 · 10-26 ~ 10-30(6일)이고 PC 에만 있는 날짜는 0이다. 보관 object 475개의 지수값은 PC 코스피 종가와 모두 같다.
- **반영 규칙**(새 함수 · 행마다):
  - 표에 없으면 넣는다.
  - 표에 있고 값이 같으면 그대로 둔다(원래 PC 출처 · 시각 보존).
  - 값이 다르면 시각을 비교한다(`store.parse_iso` 로 해석해 비교 · 문자열 비교 안 함). 보관본 `observed_at` 이 더 늦으면 정정하고, 더 이르면 기존 값을 유지한다(건수만 기록). 같은 시각이면 충돌로 보고 그 묶음을 멈춘다.
  - 넣거나 고친 행은 `source = KIWOOM_KA10051_KRX_VIA_OCI`(원천 키움 · 생산 장소 OCI · 05 §6-8 '생산 장소 구별'), `collected_at = observed_at`(OCI 확보 시각 · PC 반영 시각으로 바꾸지 않음).
  - 매수 · 매도 총액은 기존대로 NULL이다. 범위 밖 행 삭제 · 보간 · 0 채우기는 없다.
- **object 검사**(하나라도 틀리면 그 묶음 전체를 반영하지 않음): 날짜 형식 · manifest `received` 에 있는 날짜 · 13분류 정확히(`INVESTORS`) · 정수(bool 아님) · `observed_at` 해석 가능 · 지수값 숫자. PC 코스피에 그 날짜가 있으면 지수값이 같아야 한다(±0.005 · 기존 규칙). 그 날짜가 PC 코스피에 아직 없으면 반영한다(D 는 공통 날짜만 쓰므로 미래로 밀리지 않음).
- **묶음 단위 원자 반영**: 묶음(run) 하나의 수급 전체를 검사한 뒤 `BEGIN IMMEDIATE` 한 트랜잭션으로 행 반영과 아래 반영 기록 1행을 함께 쓴다. 예외가 나면 rollback해 이전 표와 보관 원본을 그대로 둔다. 순서는 run_id(=OCI 수집 시작 시각) 순이며, 실패한 묶음에서 멈추고 앞서 끝난 범위만 성공으로 적는다.
- **최소 저장안(사용자 승인 필요 · DB 스키마 변경)**: 같은 DB 에 표 1개 `market_investor_flow_import`를 둔다.
  - 칸: `evidence_run_id` PK · `manifest_sha256` · `flow_status` · `first_date` · `last_date` · `dates` · `new_rows` · `corrected_rows` · `same_rows` · `kept_newer_rows` · `max_observed_at` · `applied_at`(PC 반영 시각) · `refresh_id`.
  - 쓰임:
    - 이미 반영한 묶음은 건너뛴다. 그래서 오래된 묶음 하나가 손상돼도 새 반영을 영원히 막지 않는다.
    - 같은 run_id 인데 manifest hash 가 다르면 충돌로 처리한다.
    - 추적 기록이 된다. 행 → `collected_at`(=observed_at) → 묶음 → manifest 의 날짜별 object hash.
  - 기존 `market_refresh_log` 만으로는 `error_summary` 칸에 성공 추적 문구를 넣어야 해서(칸 뜻과 어긋남) 쓰지 않는다.
  - 범용 동기화 표 · 새 보관 서버는 만들지 않는다.
- **단계 결과 기록**: 기존 패턴대로 `market_refresh_log` 에 단계 1행을 쓴다(새 출처 `OCI_EVIDENCE_KOSPI_FLOW_IMPORT` · `run_id = market-flow-flowoci-<refresh_id>` · 실패면 짧은 한국어 사유). 새 출처는 `MARKET_FLOW_LOG_SOURCES` 에 넣어 '마지막 전체 갱신' 조회에서 뺀다(`market_topn_helpers.py:217`).
- **잠금**: 갱신 작업은 이미 한 번에 하나다(`market_refresh_service` 의 작업 잠금). DB 반영은 짧은 트랜잭션이고, 보관소 읽기는 공개된 묶음만 다룬다(`.partial` 제외).

## 3. PC 호출 경계(§7-3)

- **바꿀 한 지점**: `app/supply_fx_oil_refresh.py:247-268` `refresh_market_flow` 의 하위 단계 두 개 중 두 번째(`FLOW_LOG_SOURCE` · `refresh_investor_flows`)를 새 단계(`OCI_EVIDENCE_KOSPI_FLOW_IMPORT` · 새 모듈 함수)로 바꾼다.
  - 원/달러 · WTI 단계(Yahoo)는 그대로 둔다.
  - `refresh_market_flow` 를 부르는 곳은 PC 갱신(`market_refresh_service.py:448`) 하나뿐이다.
  - OCI 09:40 수집(`app/ml_evidence/daily_flow.py:170 · 180`)은 `refresh_fx_wti` · `refresh_investor_flows` 를 직접 부르므로 바뀌지 않는다. 키움 공통 수집 함수도 그대로다.
  - `deploy/oci` 에서 `POST /market/refresh` 를 부르는 곳은 0이다.
- **PC 수급 단계의 키움 호출 = 0**: 새 단계는 `KiwoomClient` 를 만들지 않는다. 실패해도 직접 조회로 대체하지 않는다.
- **pull 호출과 시간 상한**: 기존 CLI 를 그대로 subprocess 로 부른다(`venv python scripts/run_ml_evidence.py pull` · JSON 결과 읽기). 상한은 **150초**다.
  - 근거: 기존 수급 단계 상한은 180초였다. 화면 대기 상한은 8분이고(`MarketDiscoveryView.tsx:70`), 11-02 갱신 전체는 약 3분 40초였다.
  - 같은 프로세스 안에서 부르면 시간을 끊을 수 없다. 시간 초과로 끊겨도 pull 은 '빠진 것만 다시 받는' 구조라 다음 실행에서 이어진다.
- **결과 분리**: 새 단계의 결과는 단계 기록 1행과 완료 사유 끝 문구(`시장 흐름 자료 일부를 갱신하지 못했습니다(투자자 수급(…))` 기존 형식)로만 낸다. 다른 단계의 성공 · 실패 판정은 바꾸지 않는다(기존 격리 그대로).
- **06 자동 실행과의 차이**: 06 `run --pull` 이 보관본을 받아도 운영 표는 바뀌지 않는다. 반영은 이 버튼 단계에서만 일어난다(안내 문구에 적음).

## 4. 출력 경계(§7-4)

- **공통 설명 생성부(서버 한 곳)**: 새 모듈 `app/supply_fx_oil_basis.py` 를 두고 `build_market_flow_context` 에서 부른다. `supply_fx_oil_context.py` 가 560줄이라 650줄 한도(KS-10) 안에 두려는 분리다. 응답에 칸 2개를 추가한다.
  - `end_basis` = `{D, kospi_E, flows_E, limited_by: "flows" | "kospi" | "gap" | null, text}`. `limited_by` 는 공통 끝일을 실제로 막은 자료다. 코스피 · 수급 최신일이 같은데 D 가 더 이르면 `gap`(중간 결측)이고, 수급만 탓하지 않는다.
  - `flow_link` = `{state, at, text, oci_flow_status}`. 근거는 `market_refresh_log` 의 수급 출처(옛 키움 직접 · 새 OCI 반영) 중 가장 최근 1행과 반영 표다. 읽기 전용 연결이다.
    - `state`: `applied` · `apply_failed` · `oci_collect_failed`(보관본의 최근 수집 자체 실패) · `no_record` · `legacy_direct_failed` · `unknown`(기록 읽기 실패).
    - 새 반영이 성공한 뒤의 옛 키움 실패는 표시하지 않는다.
    - 서버 메모리가 아니라 DB 기록이므로 재기동 뒤에도 남는다.
- **네 출력에 같은 뜻으로 전달**:
  - ① 「시장 흐름 자세히」: `MarketFlowCard.tsx:116` '기간 … 끝일 D' 줄 아래에 `end_basis.text` · `flow_link.text`.
  - ② 대시보드: `summaryLines.ts` 시장 흐름 줄 보조 문장, KOSPI 카드 `TodayFlowLines`(제한 · 실패일 때만 한 줄).
  - ③ AI 복사문 · ④ 판단 근거 미리보기: `ai_text` 머리 다음에 `[기간 비교 기준일] …` 한 줄. 미리보기는 `decision_draft_preview_service.py:223` 이 같은 `ai_text` 를 쓴다.
  - 캐시: 갱신 완료 때 기존 `MARKET_INVALIDATION_KEYS` 에 `market:flow-context` 가 이미 있고, 대시보드도 같은 키를 쓴다(`useMarketFlowContext.ts:7`). 새 키는 없다.
- **「지금 할 일」(POC6-16)**: `limited_by = flows` 또는 `state = apply_failed` · `legacy_direct_failed` 이면 기존 `market_refresh` 할 일에 이유 한 줄을 더한다. 그 할 일이 없으면 같은 버튼으로 하나 만든다. 버튼은 하나로 유지한다. `oci_collect_failed` 이면 할 일을 만들지 않고 자료 확인 줄에만 적는다(다시 눌러도 해결되지 않음). GET 실패 · 미확인만으로는 할 일을 만들지 않는다.
- **부분 문구 예시**(날짜는 예시 · 실제 자료일로 생성):

| 상태 | 「시장 흐름 자세히」 · 대시보드 · 복사문 공통 문장 |
|---|---|
| 정상 | 기간 비교 기준일 10/30 · 코스피 · 수급 모두 10/30까지 · 수급은 OCI 수집본을 PC에 반영(11/02 18:30) |
| 기간 제한 | 코스피는 10/30, 수급은 10/22까지 있어 기간 비교는 10/22까지입니다 · 원/달러 · WTI 최근 값(10/30)은 '최근 큰 변화'에 따로 보입니다 |
| 반영 실패 · 이전 값 있음 | 수급 자료 반영 실패(11/02 18:30 · OCI 연결 실패) · 이전 수급 10/22까지 사용 중 · [시장 자료 갱신 화면]에서 [최신 시장 데이터 갱신] |
| 기록 없음 · 옛 실패 | 아직 OCI 수급을 반영한 기록 없음 · 마지막 PC 직접 조회 실패(11/02 10:09 · 키움 인증 실패) |
| OCI 수집 실패 확인 | OCI 의 최근 수급 수집이 실패했습니다(11/02 09:40) · 다시 갱신해도 바뀌지 않을 수 있습니다 · 이전 수급 10/29까지 사용 중 |
| 확인 불가 | 수급 연결 상태 확인 필요(반영 기록을 읽지 못함) |

- 사유는 고정된 짧은 한국어로만 쓴다(OCI 연결 실패 · 시간 제한 · 보관본 확인 필요(손상 · 충돌) · PC 표 반영 실패 · OCI 최근 수집 실패). 키 · 토큰 · IP · 원시 응답은 내지 않는다.

## 5. 격리 검사와 실제 확인(§7-5 · 설계 §8)

- **새 시험 `tests/test_poc6_17_flow_import.py`**(임시 DB · 임시 보관소 · `store` 함수로 fixture 생성 · 가짜 pull 실행기 · 라이브 DB 미접근):
  - 회신과 같은 입력: 10-22 → 10-30, D = 10-30, 원/달러 · WTI 날짜 불변
  - 같은 묶음 재반영 0행
  - 최신 판 뒤 과거 판(유지 건수)
  - 겹친 날짜 후속 정정
  - 최초 전환: 같은 값 · 다른 값 · 시각 늦음/이름 · 같은 시각 충돌
  - 수급 OK · 다른 원천 실패(PARTIAL) 묶음 반영 / 수급 FAILED · object 손상 · 분류 누락 · bool · 비정수 거절
  - 주입한 DB 오류 시 rollback(표 · 반영 기록 둘 다 0)
  - 중간 묶음 실패 시 멈춤과 앞 범위 기록
  - pull 실패 · 시간 초과
  - 비대상 표(가격 · 코스피 · 원/달러 · WTI · 보유 · 원장 · PARAM · 다른 market) 전후 동일
  - `KiwoomClient` 생성 0
- **시장 흐름 응답 시험**(기존 `tests/test_poc6_01_supply_fx_oil_context.py` 에 추가): `end_basis` 4종 · `flow_link` 6종 · `ai_text` 줄 · GET 쓰기 0(읽기 전용 연결).
- **기존 시험 수정**: `tests/test_poc6_01_supply_fx_oil_sources.py` 의 PC `refresh_market_flow` 수급 경로(FakeKiwoom) 기대를 새 단계로 바꾼다. `refresh_investor_flows` 자체 시험은 OCI 가 계속 쓰므로 그대로 둔다.
- **프런트 시험**: `MarketFlow.test.tsx` · `summaryLines.test.ts` · `TodaySummary.test.tsx` 에 상태별 문장, 「지금 할 일」 합치기 · 만들지 않음(OCI 수집 실패 · GET 실패)을 추가한다.
- **회귀**: 관련 시험 뒤 백엔드 전체 pytest 1회(백그라운드) · 프런트 tsc · lint · vitest 전체 1회.
- **예상 변경 범위**:
  - 신규: `app/oci_flow_import.py` · `app/supply_fx_oil_basis.py` · 시험 1
  - 수정: `app/supply_fx_oil_refresh.py` · `app/supply_fx_oil_store.py`(출처 상수 · 반영 표 DDL) · `app/supply_fx_oil_context.py` · `app/api_supply_fx_oil.py`(응답 칸) · 프런트 `lib/api/marketFlow.ts` · `marketflow/MarketFlowCard.tsx` · `marketflow/TodayFlowLines.tsx` · `today/summaryLines.ts` · 기존 시험 · 문서(결과서 · STATE · PROGRAM_TRUTH)
  - 무변경: 05 `pull`(Q1 제외)/export · 06 · 13 · OCI 수집 · 의존성 · cron · 키
- **실제 연결 확인(사용자 승인 항목)**: PC 반영 1회. 둘 중 하나를 승인받는다.
  - (가) [최신 시장 데이터 갱신] 버튼 — 실제 사용 경로이며 갱신 화면 문구까지 확인할 수 있다. 다른 단계의 기존 외부 조회(FinanceDataReader · KRX · Yahoo · NAV)와 PC DB 쓰기가 함께 일어난다.
  - (나) 같은 핵심 함수의 단독 실행(pull + 반영만).
  - 전후로 수급 자료일 · 행 수 · 출처 분포, 비대상 표 행 수 · 최대 날짜, D · 화면 · 복사문을 대조한다.
- **사용자 승인 항목**: ① 새 표 1개(DB 스키마 변경) ② 실제 반영 1회 방법((가) 또는 (나)) ③ Q1 이 (a)이면 05 pull 의 동시 실행 처리 변경.

## 6. 기반 문서 대조

| 문서 · 원문 | 이번 PLAN |
|---|---|
| POC6-05 DESIGN §9-6 'PC 가져오기/export는 승인된 OCI 보관 경로 읽기만 하며 시장/원장/보유 DB에 쓰지 않는다.' | pull/export 는 그대로이고, 반영은 별도 새 함수가 한다(설계 §2 POC6-17 한정 예외). 원문은 고치지 않는다. 결과서 · PROGRAM_TRUTH 수급 줄에 예외 한 줄을 적는다. |
| POC6-05 DESIGN §6-8 '동일 자료를 두 곳에서 받았으면 원천/확보 시각과 생산 장소를 구별한다.' | `source = …_VIA_OCI` · `collected_at = observed_at` 로 충족한다. |
| POC6-01 `supply_fx_oil_store.py` 머리 '쓰기는 PC 시장 갱신과 POC6-05 OCI 일일 수집만' | 새 반영도 PC 시장 갱신 단계 안이라 문장은 유지하고, 주석에 'OCI 보관본 반영' 을 더한다. |
| PROJECT_ORIGIN_INTENT §10 'PC 는 OCI DB 의 일관된 분석 복제본을 사용한다' | 수급 한 표만 연결한다. PC DB 전체가 같은 판이라고 쓰지 않는다. |
| 설계 §3 '기존 05 pull … 동작은 바꾸지 않는다' | 아래 Q1 이 실제 충돌이다. |

## 7. 질문(실제 불일치 2건)

**Q1. pull 동시 실행.** 06 자동 실행(`run --pull` · 평일 10:00 이후)과 버튼의 pull 이 겹칠 수 있다. 11-02 에도 06 공개(10:06:21)가 갱신(10:06:05 ~ 10:09:45) 안에 있었다.
- `transfer.pull` 은 시작할 때 다른 pull 의 임시 칸(`.incoming/pull_*`)을 지운다(`transfer.py:196-197`). 그래서 겹치면 한쪽이 '확인 필요'로 끝날 수 있다. 자료 손상은 아니다(hash 검사 · 공개 잠금).
- 지금 pull 에는 동시 실행 잠금이 없다.
- 선택지:
  - (a) pull 안에 기다리지 않는 잠금 1개를 둔다. 겹치면 즉시 '다른 가져오기 진행 중'으로 끝낸다. 05 pull 동작이 겹칠 때만 바뀌고, 06 쪽 같은 경합도 함께 막는다.
  - (b) pull 은 그대로 두고, 겹침은 이 단계에서 '가져오기 확인 필요'로 표시한다(Q2 에 따라 이미 받은 보관본은 반영).
- 개발자 판단: (a). 설계 §3 문장과 충돌하므로 판정을 요청한다.

**Q2. pull 이 실패했을 때(망 없음 · SSH 실패 · 150초 초과) PC 에 이미 받아 둔 미반영 보관본을 반영할지.**
- 06 자동 실행이 평일마다 보관본을 받아 두므로, pull 이 실패해도 PC 에 더 새 보관본이 있을 수 있다.
- 선택지:
  - (a) 검증을 통과한 기존 사본은 반영하고, '가져오기 실패 · PC 에 있던 보관본(10/30까지)으로 반영'으로 실패를 함께 표시한다. 성공으로 감추지 않는다.
  - (b) 반영하지 않고 기존 수급을 유지한다(설계 §3 '실패하면 기존 PC 수급을 유지' 문자 그대로).
- 개발자 판단: (a). 맥북 망과 관계없이 최신에 가까워진다. 설계 §3 의 '실패'가 pull 실패까지 뜻하는지 확인이 필요하다.

질문이 없는 항목은 위 판단대로 진행한다. 실제 PC 반영 · 새 표 생성은 PLAN 판정과 사용자 승인 뒤에 한다.

## 8. PLAN 판정 반영(2026-11-02 · PASS_WITH_REQUIRED_CORRECTIONS · 재제출 없음)

판정이 PLAN 과 다르게 정한 곳은 판정을 따른다. 위 §1 ~ §7 본문은 제출본 그대로 두고 바뀐 계약만 여기 적는다.

| 판정 | PLAN 에서 바뀐 것 |
|---|---|
| §2 Q1 (a) | `transfer.pull` 안에 보관소 기준 비대기 잠금(`.pull.lock`). 잠금을 잡은 뒤에만 임시 칸 정리 · 전송 · 공개. 겹치면 즉시 `BUSY`(이유 `PULL_BUSY` · '다른 가져오기 진행 중') · 원격 호출 0 · 남의 임시 칸 그대로. 06 함수 호출도 같은 잠금. 버튼 쪽 150초 초과 = 자식 프로세스 그룹 정리(`forward_auto.runner.run_child` 재사용) → 잠금도 함께 풀림 |
| §3 Q2 (a) | 가져오기 실패(망 · SSH · 시간 초과 · 경합 · 전송 확인 필요)여도 검증된 공개 완료 사본은 반영(이 버튼 단계만 · 06 실패 처리는 그대로 · pull 실행 자체의 알 수 없는 실패는 반영 안 함 — 독립 검토 반영). 가져오기 결과와 반영 결과를 기록 2행으로 따로 남기고 `flow_link` 를 `applied_local`(사본 반영) · `kept_local`(새 자료 없음)로 구분 — 일반 `applied` 로 바꾸지 않음 |
| §4-1 | §2 의 '값이 같으면 그대로'를 바꿈: **같은 값이라도 더 늦은 관측이면 출처 · 관측 시각을 올린다**(`refreshed` 건수 · 값 정정 `corrected` 와 구분). 더 이른 관측은 값과 관계없이 내리지 않음. 같은 시각 다른 값 · 시각 불명 기존 행의 다른 값 = 충돌 |
| §4-2 | 수급 FAILED · object 없는 묶음 = 반영 대상 아님 · 반영 표에 `EXCLUDED_NO_FLOW` 로 기록(상태 근거 · 뒤 묶음을 막지 않음). 수급 OK · PARTIAL 의 반환 object 는 전부 검사 통과해야 묶음 단위 반영 · 빠진 날 채우지 않음 |
| §4-3 | 지수값 = bool 아닌 유한 양수 · `observed_at` 은 UTC `Z` 만(시간대 미상 = 확인 필요) · ±0.005 대조 그대로 · 순매수 재환산 없음 |
| §4-4 | `limited_by = gap` 은 `D < min(kospi_E, flows_E)` 전부 · 공통 날짜 없음 = `unknown`. 확인된 OCI 수집 실패면 기간 제한이 있어도 '다시 누르기' 할 일 없음(서버 `retry_helps = false`) |
| §5 | 첫 실제 확인 = (나) 단독 실행(`python -m app.oci_flow_import` · 버튼과 같은 수급 단계 함수만). 실제 PC DB 쓰기는 사용자 승인 묶음 뒤 |

질문 Q1 · Q2 는 닫혔다. 새 질문 없음. 구현 뒤 독립 검토 7건 반영 내역은 결과서 §4-2.
