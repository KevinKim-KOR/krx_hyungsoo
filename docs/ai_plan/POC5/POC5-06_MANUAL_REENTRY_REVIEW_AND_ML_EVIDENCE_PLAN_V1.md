# POC5-06 — 수동 재진입 검토 · ML 근거 개발 PLAN V1

```text
STEP_ID        = POC5-06
DESIGN         = docs/ai_design/POC5/POC5-06_MANUAL_REENTRY_REVIEW_AND_ML_EVIDENCE_DESIGN_V1.md (설계자 2026-10-09 · 끝에 전달문 원문)
BASE_COMMIT    = ae5fa38c (POC5-05 종료)
STATUS         = PLAN 확정 — 설계자 PASS_TO_IMPLEMENT_WITH_CORRECTIONS(2026-10-09 · Q-A ~ Q-D 확정 · 재제출 불필요 · 설계서 개정 2 §10 · 반영 = 본문 정정 + §7)
조사            = 설계서 §8 6항목 — 개발자 + 독립 조사 5갈래(읽기 전용 · PC DB mode=ro · 2026-10-09) · 수치 · 코드 근거는 개발자가 다시 실행 · 확인(분배락 조정 대조 수치만 독립 조사 실측 · §1-2 표시)
설계자 질문      = 4건(§6 · 기반 문서 · 실제 코드 · 실제 자료와 맞지 않는 것만)
```

## 0. 요약

설계 구조대로 만들 수 있다. History 의 [재진입 검토] → 선택 position · cycle 을 고정한 검토 창(내 거래 · 저장된 근거 · ML 검토) → ETF 1개 수동 실행 → StandardScaler → Ridge(svd) · 학습 중앙값 기준 → PC 연구 산출물. 새 의존성 0(scikit-learn 1.9.0 · numpy 2.4.6 설치 = requirements 고정값) · OCI · PUSH · cron · 보유 쓰기 · 원장 · 02/03 코드 변경 0. 069500 시제품 실행은 프로세스 전체 약 2초이고, 같은 입력이면 같은 결과다.

다만 설계 문장을 지금 자료에 그대로 적용하면 ML 이 거의 실행되지 않거나 기반 문서와 부딪친다(§6).

- **Q-A 기반 문서**: ASSUMPTIONS Q6 · INTENT §9.5 '미래 하락을 미리 맞히는 모델을 만들지 않는다'(불변), POC4-02 §7, POC5-00 §12 'POC5 안에서 ML 모델을 다시 열어야 함 = 즉시 중단'.
- **Q-B 거래일 축**: 캘린더 파일은 2026 하나다. 과거 휴장일이 '종가 없는 거래일'이 되어 2014~2025 표본이 0 이고 늘 DATA_SHORT 다.
- **Q-C 가격 경계**: 출처 라벨 전환을 경계로 두면 ETF 787종목 중 785 가 DATA_SHORT, 실제 기준 변화만 경계로 두면 711 이 세 구간을 채운다.
- **Q-D 원장 연결**: 사업군 대표 ETF · 기초지수 그룹 구성 ETF 로 기록된 알림을 포함할지.

## 1. 사실조사 (설계서 §8)

### 1-1. 05 History 재사용 (§8-1)

| 항목 | 실제 · 근거 |
|---|---|
| 라우터 | `app/api_holdings_history.py`(71줄 · prefix `/holdings` · `app/api.py:126` 등록 완료) — 같은 라우터에 경로를 더하면 `api.py` 변경 0 |
| 선택 검증 | `holdings_history_view.market_flow_input(position_id, cycle_id)`(view:115-141)가 문서를 다시 읽어 position · cycle 을 함께 찾고 ticker 는 서버 문서에서 가져온다(없으면 404). 06 도 서버가 검증한 ticker 만 쓴다 |
| 기간 · 거래 | `history()` cycle = status · opened_by(BASELINE/REGISTER/BUY) · closed_by(SELL/ADJUSTMENT) · start_date(BUY 시작일 때만) · end_date · has_adjustment · realized_pnl · sold_cost · realized_rate · events(+ cost_of_sold · realized_pnl · q_after) · voided. 05 계산 결과를 그대로 쓴다 |
| 마지막 실제 매도 | events 중 SELL 의 가장 늦은 trade_date. closed_by=ADJUSTMENT(입력 정정 종료)의 end_date 는 정정일이라 매도일로 쓰지 않는다 |
| 매도 후 변화 | 05 `_event`(flow:408-450)가 SELL 마다 '매도 기준일 → 마지막 저장일'을 이미 만든다 → 수정 없이 호출. 05 `_holding_period` 는 closed_by 와 무관하게 마지막 SELL 을 쓴다(flow:466-482) — 06 은 입력 정정 종료 기간을 '매도로 종료'로 표시하지 않는다 |
| 화면 | `HistoryDialog` → 기간마다 `HistoryCycle`. [시장 흐름 보기]는 매매가 있는 기간에만(HistoryCycle:94 · 119). 창 상태는 하나(`HoldingsBookSection` Open = trade/new/history)이고 공용 `Dialog` 의 Esc 는 document 단위라 창 위에 창을 열면 Esc 한 번에 둘 다 닫힌다 |
| 실제 PC 보유 | 아직 기존 형식(v1 · 32줄 = 종목 29(ETF 26 · 개별주 3) · 이력 0 · 과거 보유 0) → 모든 기간이 '매수일 미상 · 매매 없음'. v1 줄 ID 는 파일 내용 sha256 으로 만들어져(store:60-100) 저장 한 번에 모두 바뀐다 |
| ETF 판정 | `etf_master` 기준(05 `asset_kind`). 개별주 줄도 `etf_daily_price` 행이 있으므로 가격 행 유무로 ETF 를 판정하지 않는다 |

### 1-2. 가격 계열 (§8-2 · §4)

- **표**: `state/market/market_data.sqlite :: etf_daily_price` — 1,413,813행 · 1,190종목 · 2014-04-09 ~ 2026-10-02 · 이상 종가(NULL · 0 이하) 0 · KOSPI 저장일 대비 종목 내부 날짜 누락 0(전 종목).
- **출처 라벨 2개**: `NAVER_FDR`(~ 2026-03-05 · 2026-07-02 백필 한 번) · `FinanceDataReader`(2026-02-19 ~ · 갱신 때마다). 둘 다 설치된 FinanceDataReader 0.9.202 의 같은 네이버 reader 다(6자리 코드 · `NAVER:` 접두 모두 `NaverDailyReader`). 주 전환(2026-03-05 → 03-06) 1,063종목은 저장된 `change` 가 직전 NAVER 종가와 연속이다(1,063/1,063 · 재현). 131종목은 02-19 에 비연속으로 먼저 바뀌었다가 NAVER 로 돌아갔다.
- **가격 의미**: 분배락 조정 흔적이 있다(독립 조사 실측 · 봉인 KRX 대조 — 069500 저장 / KRX 무조정 비율이 2014 0.7931 → 2026 1.0 으로 분배락일마다 계단 · 분배락일 수익률이 조정 수익률과 일치 8,352건 vs 무조정과 일치 137건). 총수익 여부는 문서가 없어 미확정이다. 기존 코드 라벨끼리도 다르다(`SOURCE_CLOSE` · '분배금 미반영' · '배당조정 계열').
- **수집 경계 계단**: `POST /market/refresh` 가 매번 전 ETF 의 최근 120일을 덮어써, 수집일 경계마다 조정 기준이 다른 값이 이어 붙는다. 같은 `FinanceDataReader` 라벨 안에서 `change` 불일치 750행(04-20 431 · 06-08 136 · 05-07 127 · 05-26 56 · 재현). 예: 069500 2026-04-20 저장 change +0.479% · 저장 종가 기준 −0.167%(−0.64%p 계단). 기존 결함 `DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY` 의 '미해명 계단'과 같은 현상이다. NAVER_FDR 행은 change 가 비어 있어 그 안의 작은 계단은 감지할 수 없다.
- **쓰지 않는 표**: `krx_etf_daily_price_unadjusted`(OCI 무조정 하루치 · krx_store 계약 'UI · ML 금지') · 봉인 KRX DB · 원장 price_outcome(KRX 무조정 계열 — '저장된 근거' 칸에 값 그대로만 표시).
- **05 reader**: `holdings_market_flow._Reader` 는 두 날짜 지점만 읽고 change · fetched_at 을 읽지 않는다 → ML 은 한 번의 SELECT(mode=ro)로 전체 계열을 읽는 새 reader 를 쓰고, 05 의 `open_ro` · `ETF_SOURCES` · `asset_kind` · 읽기 오류 구분만 재사용한다. `market_data_store.fetch_price_history` 는 DDL 을 실행하므로 쓰지 않는다.
- **갱신 경로**: 「요즘 잘 오르는 ETF」 [최신 시장 데이터 갱신] = `POST /market/refresh` — 전 ETF(etf_master 1,187종목) 최근 120일 + KOSPI · NAV · 장중 설정 · 80 ~ 149초(최근 7회) · 6시간 간격 · 한 번에 하나. 「받은 알림 기록」 원장 새로고침은 시세를 건드리지 않는다. 단일 종목 수집기는 만들지 않는다.
- **최신성**: PC 저장 최신일 2026-10-02 · 오늘(10-09) 기대 완료일 2026-10-08(`trading_day_lag.expected_previous_trading_day`) → 3거래일 늦음.

### 1-3. 거래일 축 · 검증 날짜 (§8-3)

- 캘린더 파일은 `state/market_meta/krx_trading_days_2026.csv` 하나(244일)다. 다른 해는 평일 기본(주말 · 5/1 · 12/31 만 휴장)이다.
- 069500 을 평일 기본 축에 놓으면 2014 ~ 2025 에 종가 없는 '거래일'이 166일(연 11 ~ 17일 · 설 · 추석 등 휴장일로 보이나 공식 자료와 대조하지 않음)이다. 설계 규칙(창 [t−60, t+20] 의 모든 축 날짜에 종가)을 적용하면 2014 ~ 2025 표본 0 · 2026 107 → 세 구간 모두 DATA_SHORT(학습 0 / 0 / 24)다. 2027 이후도 같은 구조다.
- 기존 helper `trading_day_lag.trading_days_ending(t, N, calendar_dir, stored=<KOSPI 저장일>)` 는 '파일 있는 해 = 파일 · 없는 해 = 평일 기본 ∩ 저장일'이고 KOSPI 저장일 3,061일과 같다(0.36초 · 재현). `stored` 인자는 운영에서도 같은 뜻으로 쓴다(krx_store · holdings_selection_source · sector_signal). 02 price_outcome 은 '가격표 행으로 휴장을 추론하지 않는다'(설계자 Q-C)라 stored 를 쓰지 않는다 — 02 는 바꾸지 않는다.
- 과거 공식 거래일 자료는 저장소에 없다. `scripts/build_krx_trading_days.py` 는 KRX Open API(키 필요 · 평일마다 1회 · 약 3,100회)이고 2026 만 고정돼 있다.
- 검증 날짜: t = 선택 ETF 의 마지막 저장 종가일. 검증 끝 = 축에서 t 의 20거래일 전 · 그 앞 189 축 날짜를 63씩 3구간. +20 · −60 은 축 위치로 센다(가격 행 수로 세지 않음).

### 1-4. ML 실행 가능성 · 표본 · 시간 (§8-4)

- scikit-learn 1.9.0 · numpy 2.4.6 설치 = requirements.txt 고정값 → 설치 · 버전 변경 0. `Ridge(alpha=1.0, solver='svd', fit_intercept=True)` · `StandardScaler` 정상.
- 기존 Ridge 코드(POC2 `market_flow_*`)는 solver 기본값 · 평균 기준 · 다른 목표 · 분할이라 쓰지 않는다. POC4-03 RF 자산 사용 0. 새 작은 모듈에서 sklearn 을 직접 부른다.
- 시제품(scratchpad · 설계 §5 그대로 · 069500 · t = 2026-10-02 · 검증 2025-11-25 ~ 2026-09-02):

| 축 · 가격 경계 | 유효 표본 | 구간 검증 수 | 구간 MAE 모델 / 기준(%p) | 전체(%p) | t 추정 |
|---|---|---|---|---|---|
| KOSPI 저장일 축 · 가격 경계 없음 | 2,981 | 63 · 63 · 63 | 3.35/3.16 · 4.29/4.28 · 10.71/12.52 | 6.11 / 6.65 (n=189) | −1.75% |
| 〃 · 출처 라벨 전환을 경계로 | 2,901 | 46 · **0** · 63 | — | DATA_SHORT | — |
| 평일 기본 축 | 107 | 0 · 44 · 63(학습 0 · 0 · 24) | — | DATA_SHORT | — |

- 경계 규칙별 구간 표본 수(학습 없이 셈 · 541행 이상 787종목 · t = 각 종목 마지막 저장일 · 재현):

| 경계 규칙 | 069500 구간 검증 수 | 787종목 |
|---|---|---|
| 출처 라벨 전환 + 실제 기준 변화 + 공백 | 46 · 0 · 32 | DATA_SHORT 785 · 세 구간 통과 2 |
| 실제 기준 변화(FDR `change` 불일치 · FDR→NAVER 재전환) + 공백 | 63 · 14 · 32 | 세 구간 통과 711 · DATA_SHORT 76 |

- 시간: 프로세스 전체 2.0초(sklearn import 0.8 ~ 1.2초 · DB 읽기 약 0.01초 · 축 약 0.36초 · 표본 + 학습 4회 약 0.06초). 서버에서는 첫 실행만 import 비용이 든다 → 동기 POST 로 충분하고 작업 큐는 없다.
- 결정성: 같은 입력 반복 실행 결과 sha256 동일(`f05a3b58…` · 재현).

### 1-5. 원장 연결 · 개인값 경계 (§8-5)

- **PC 원장 사본**(`state/decision/decision_evidence.sqlite` · mode=ro): 2026-10-08 하루치 실행 3 · item 88 · delivery 3(모두 sent) · price_outcome 0행(PENDING = 행 없음) · user_feedback 1행 · 마지막 동기화 2026-10-08 10:15.
- **ticker 가 원장에 명시되는 곳 3가지**: ① `subject_kind='ticker'` 의 subject_id(보유 종목 · 인덱스 있음) ② sector 행 `values_json.ticker`(사업군 대표 ETF · 02 결과도 이 ETF 계열) ③ index_group 행 `values_json.tickers`(기초지수 그룹 구성 ETF). 사본 기준 보유 종목 중 ②로도 기록된 것 3종목 · ③ 0.
- **구분 보존**: disposition(sent · suppressed · cut_by_* · not_selected · data_unavailable) + delivery_status(sent/partial/failed/skipped) → 전달 · partial · 관측만. exposure PRIMARY/SECONDARY/NULL('노출 분류 없음') · cohort · off_schedule · contract_version. price_outcome 상태 MATURED · T0_MISSING · PRICE_MISSING · UNTRACKED_AFTER_EXIT · UNSUPPORTED_PRICE_SOURCE(행 없음 = 집계 중) · price_basis.
- **사용자 평가**: user_feedback 는 알림(event) 단위 · append-only · sent/partial 만 → 화면에 '이 알림 전체에 대한 평가'로 표시한다(종목 평가로 보이지 않음).
- **읽기 방식**: 기존 03 조회(`views.list_alerts` · `alert_detail`)는 하루 단위 · ticker 필터 없음이고, `store.connect()` 가 폴더 생성 · DDL · COMMIT 을 한다 → 06 은 04 `ledger_reports/source.py` 처럼 `mode=ro` · BEGIN … ROLLBACK 한 트랜잭션으로 읽는 새 함수를 둔다(사본 없음 = NO_COPY · DB 오류 = READ_FAILED · 0행과 구분). 03 코드는 바꾸지 않는다.
- **개인값**: ticker 행은 `values_json` 의 `profit_loss_pct`(58/58)와 열 `t0_price`(58/58)를 함께 가져 평단을 근사 역산할 수 있다 → values_json 을 통째로 돌려주거나 산출물에 복사하지 않고, 손익률은 ML · 산출물에 넣지 않는다(화면에 필요한 키만). ML 입력에 원장 값 0 · 개인 수량 · 평단 · 금액 · 메모 0. PC 밖으로 나가는 통로는 원장 동기화 SSH(상수 명령) · OCI 적용(5필드) · Decision Draft Preview(사용자 복사)뿐이고 06 은 셋 다 부르지 않는다. app/ 의 외부 LLM 호출 코드 0.

### 1-6. 변경 파일 · API · 산출물 · KS-10 (§8-6)

- **KS-10(실측)**: 트리거 0. `app/holdings_market_flow.py` 591(백엔드 근접선 600까지 9줄) → 06 계산은 새 모듈에 둔다. `api_holdings_history.py` 71 · `holdings_history_view.py` 141 · `HistoryCycle.tsx` 143 · `HistoryDialog.tsx` 185 · `HoldingsBookSection.tsx` 327 · `HoldingsManageView.tsx` 761 · `frontend/lib/api/holdingsHistory.ts` 193.
- **산출물**: `state/ml/research/`(git 추적 밖) 관례 = 새 폴더만(exist_ok=False) · JSON sort_keys. 06 = `state/ml/research/poc5_06/<YYYYmmddTHHMMSS>_<짧은 id>/{review.json, input_snapshot.json}`(설계 §6). API 프로세스가 이 경로에 쓰는 첫 기능이다. 테스트 가드가 state/ 쓰기를 막으므로 시험은 tmp 경로로 한다.

## 2. 구현 계획 (판정 뒤)

### 2-1. 백엔드 — 새 패키지 `app/reentry_review/` (05 · 02 · 03 코드 변경 0)

| 파일 | 책임 |
|---|---|
| `prices.py` | 선택 ETF 전체 종가 한 번 읽기(mode=ro) · 경계(Q-C) · 연구 축(Q-B) · 최신성 · 사용한 가격의 canonical hash |
| `model.py` | D20 · feature 5 · 3구간 검증 · 학습 중앙값 기준 · 최종 fit · [-1, 0] 제한 · MAE(%p). sklearn 은 이 파일 함수 안에서만 import |
| `ledger.py` | `ticker_ledger_evidence(ticker)` — mode=ro 한 트랜잭션 · link_kind(Q-D) · 필요한 키만 |
| `review.py` | 선택 검증(05 방식) · 내 거래 사실(05 history 재사용) · 저장된 근거(05 `_event` 호출 · 최근 가격 상태 = feature 다섯 값) · ML 실행 · 산출물 쓰기 |
| `models.py` | API 응답 모델 |

API — `app/api_holdings_history.py` 에 경로 2개(공개 API 아님 · 파일 · 모델 경로 입력 없음 · 보유 저장 API 와 분리):

- `GET /holdings/trade-history/reentry-review?position_id&cycle_id` — 내 거래 · 저장된 근거 · 원장 근거. 학습 · 외부 조회 · 쓰기 0.
- `POST /holdings/trade-history/reentry-review/ml` (body: position_id · cycle_id) — ML 1회 · 산출물 저장 · 결과 반환.

상태(제안): `OK` · `DATA_SHORT` · `PRICE_BASIS_UNCONFIRMED` · `NOT_ETF`(개별주) · `NO_PRICE` · `AXIS_UNCERTAIN`(t 가 축에 없음 · 연도 파일 없는 해에 KOSPI 최신일이 t 보다 이른 경우) · `READ_FAILED`(DB 오류) · `SAVE_FAILED`(산출물 저장 실패 → 정상 완료로 보이지 않음) · 선택 무효 404('보유가 바뀌었습니다 — 다시 여세요').

### 2-2. 화면

- History 의 기간마다 [재진입 검토] — 현재 · 과거 보유 모두. 실제 보유가 아직 매매 0 이므로 매매 유무와 무관하게 둔다.
- 검토 창은 History 창을 대신해 열고, 닫으면 History 로 돌아간다(창 상태 하나 · 창 위 창 Esc 문제 회피). backend 구현 중 작은 목업으로 확인한다(설계 §2).
- 세 부분: **내 거래**(선택 기간 · 이전 기간 · 마지막 실제 매도 · 매수일 미상 · 입력 정정 안내) / **저장된 근거**(매도 기준일 → 마지막 저장일 · 최근 가격 상태 · 같은 종목 알림 · 가격 결과 · 선택 평가) / **ML 검토**([ML 검토 실행] · 기준일 · 추정값 · 단순 기준과 검증 오차 · 표본 · 제외 수 · 한계).
- 문구: '저장 종가 YYYY-MM-DD 기준' · 지연이면 '이 날짜 기준 검토' · '연구 추정 · 투자 유효성 미확정' · 열위면 '단순 기준보다 검증 오차 큼' · '이 값은 매수/매도 지시가 아닙니다'(MASTER_PLAN). 신뢰구간 · 성공률 · 확률 배지 없음.
- 이동 링크: 「요즘 잘 오르는 ETF」(가격 갱신 · 전 ETF · 약 1.5 ~ 2.5분 안내) · 「받은 알림 기록」(원장 새로고침). 자동 실행 없음. [재매수]는 05 매매 창이고 ML 결과와 연결하지 않는다.

### 2-3. 정해 둔 세부 (질문 아님 · 판정에서 바꿀 수 있음)

- 입력 정정으로 끝난 기간: 매도일 · 매도 손익을 만들지 않는다. 그 기간 안에 실제 부분 매도가 있으면 그 SELL 의 '매도 기준일 → 마지막 저장일'만 보인다.
- 원장 조회 범위는 원장 전체(시작 2026-10-08). 관측만 된 행은 건수 + 펼치기.
- 평가: 알림마다 최신 1행 + 건수. 메모는 화면에만 보이고 산출물에는 event_id · feedback_seq · helpfulness 만 남긴다.
- 개별주: 개인 History · 원장 근거는 보이고 ML 은 '대상 아님(ETF 만)'.
- 산출물 hash: 실제 사용한 (date, close, source, fetched_at, change) + 축 날짜 + recipe 로 canonical sha256. live DB 파일 hash 로 대신하지 않는다.
- 읽은 기준: 보유 문서 revision(v1 이면 0 + 파일 sha256) · 원장 사본 마지막 동기화 시각 · 가격 최신일.

## 3. 검증 계획 (줄인 방식)

| 수용 기준(설계 §7) | 시험 |
|---|---|
| 선택 실행 | 창 GET 은 sklearn import · 산출물 · SSH · 외부 호출 0 · POST 는 서버가 검증한 ticker 하나만 |
| 거래 경계 | 계좌 · cycle 분리 · 매수일 미상 · 입력 정정 종료를 실제 거래로 만들지 않음 |
| 목표 계산 | 알려진 경로의 D20 · 전부 상승 = 0 · +20 경계 · 휴장(축) · 누락 · 경계 제외 |
| 누수 차단 | 학습 정답 종료일 < 검증 시작일 · 뒤 가격을 바꿔도 이전 feature · 해당 구간 학습 불변 |
| 학습 · 비교 | scaler 학습 구간만 · 고정 Ridge · 같은 제한 · 학습 중앙값 기준 · MAE %p · 구간/전체 분모 |
| 부족 · 장애 | 짧은 자료 · 개별주 · 가격 의미 미확인 · 늦은 기준일 · DB 오류 · 저장 실패 구분 |
| 평가 선택 | 피드백 0행 ↔ 추가 후 ML 출력 동일 · user_feedback · price_outcome 불변 |
| 부수효과 | tmp 자료 · 보유 · 적용 hash · 원장 · 운영 파일 불변 · Telegram · OCI 쓰기 0 |

검토 1회 · 변이 시험(저장소 사본) · 정적 검사 · vitest · tsc · eslint · 전체 회귀 1회 + 라이브 해시(state/logs 전체 · 범위 고정) · KS-10. POC4 연구 재실행 · 기존 모듈 정비는 하지 않는다.

## 4. 문서 · 배포

- OCI 에서 도는 파일 변경 0 → OCI pull · 첫 영업일 확인 없음.
- 결과서 → 검증자 → 설계자 RESULT → 커밋 · push(사용자 승인) → PC 재기동 → 실화면(실제 저장 자료가 있는 ETF 하나) → 종료 기록 · 인계.
- PROGRAM_TRUTH(화면 · API 표 · state 경로 표) 갱신. Q-A 결정에 따른 기반 문서 동기화는 이 단계 범위에 넣는다.

## 5. 사용자 확인 항목

1. 실화면 전에 「요즘 잘 오르는 ETF」 [최신 시장 데이터 갱신]을 한 번 눌러 두면 최신 기준으로 볼 수 있다(지금 3거래일 늦음 · 누르지 않아도 '2026-10-02 기준'으로 동작).
2. PC 보유에 아직 매매 기록이 없어(과거 보유 0) 실화면은 현재 보유 ETF 의 검토로 한다. '매도 후 변화'는 시험 자료로만 확인한다.
3. Q-A 에서 PROJECT_ORIGIN_INTENT §9.5(사용자 작성 불변 앵커)를 고치는 안이 선택되면 사용자 승인이 필요하다.
4. 이번 ML 은 알림 평가 모델이 아니라 가격 기반 D20 추정이다(알림 도움 여부 평가는 후속).

## 6. 설계자 질문 (기반 문서 · 실제 코드 · 실제 자료와 맞지 않는 것만)

### Q-A. 기반 문서의 '하락 예측 모델 금지' · 'POC5 ML 재개 금지'

- 사실: ASSUMPTIONS.md:52-53 · INTENT:309-311 '"하락 예측"이 아니라 "위험 구간 분류" … 미래 하락을 미리 맞히는 모델을 만들지 않는다'(불변). INTENT:316-317 'threshold / factor / label / 학습창 / 모델 … 사용자 결정 영역'. POC4-02 V2:194-197 '금지 = 미래 하락률을 확정값처럼 예측 · 미래 구간의 하락은 모델 출력이 아니라 과거 검증용 label 로만' · :849-851 02B REJECT · Track B 재시도는 새 PLAN · 새 사전 등록. POC5-00 설계:311 즉시 중단 조건 'POC5 안에서 ML 모델을 다시 열어야 함' · :400-402 'ML 재개 아님'. POC4-03:404 '실전 out-of-sample 기록에서 새 label 이나 feature 가설이 생길 때만 새 ML 연구 개방'. STATE_LATEST:2736 'ML / … label 확정 (Q6 답 나오기 전)'. KILL_SWITCHES:169 '사용자 요청만으로 KS-11 예외를 허용하지 않는다'.
- POC5-06 §1 은 POC5-00 금지를 '01~04 수집 단계 계약'으로 좁혀 읽고, D20 추정을 'ML 하락 위험 추정'으로 부른다. 설계서에 Q6 · 02B 언급은 없다.
- 추천: ① 06 은 축 2(시장 위험 구간 분류) · Q6 운영 계약 · 02B Track B 재시도가 아니라 **'선택 ETF 하나의 가격 경로 연구 추정'** 이라고 설계서 §1 에 적고, 화면 · 문서의 '하락 위험' 표현을 '이후 20거래일 최저 종가 변화(연구 추정)'로 통일한다. ② 개방 근거(사용자 재진입 요청 · POC5-05 §8 · 다른 질문 · 단일 고정 모델 · 사후 선택 없음)와 `ML_OPERATION_PROMOTION = NOT_APPROVED` · `CURRENT_DEPLOYABLE_ML_MODEL = none` 유지를 설계서에 적는다. ③ 날짜 붙은 '06 PC 수동 연구 한정' 기록을 ASSUMPTIONS Q6 · POC5-00 설계 · PLAN · STATE 에 남긴다(INTENT §9.5 는 사용자 승인 시). 문서 동기화는 이 단계에서 한다.

### Q-B. 과거 연도의 거래일 축

- 사실: §1-3. 설계 §4 '기존 한국 거래일 Calendar' 를 그대로 쓰면 2014 ~ 2025 표본 0 → 늘 DATA_SHORT.
- 추천: 06 연구 축만 `trading_days_ending(..., stored=KOSPI 저장일)`(파일 있는 해 = 파일 · 없는 해 = 평일 기본 ∩ KOSPI 저장일). 02 의 '가격표 행으로 휴장 추론 안 함'과 원칙이 다르므로 결과에 '공식 휴장 목록이 아닌 KOSPI 저장일 보정 축' · 기준 계열 최신일 · 연도별 건너뛴 평일 수를 남기고 축 날짜를 hash 에 넣는다. 운영 계약 · 02 · 캘린더 파일 변경 0. 대안은 과거 공식 거래일 파일을 만드는 것이다(KRX API 약 3,100회 · 키 · 사용자 승인 · `state/market_meta` 에 두면 운영 범위가 바뀌므로 연구 폴더 필요).

### Q-C. 가격 경계와 가격 의미

- 사실: §1-2 · §1-4 — 두 라벨은 같은 네이버 reader · 주 전환 연속 1,063/1,063 · 같은 라벨 안 수집 경계 계단 750행 · 분배락 조정 흔적 · 총수익 미확정. 라벨 전환을 경계로 두면 787종목 중 785 DATA_SHORT, 실제 기준 변화만 경계로 두면 711 통과(t = 각 종목 마지막 저장일 기준).
- 추천: `NAVER_FDR` · `FinanceDataReader` 를 같은 원천 · 같은 가격 의미로 보고 라벨 전환 자체는 경계로 두지 않는다. 대신 실제로 감지되는 기준 변화(FinanceDataReader 행 `change` 와 저장 종가 변화의 차이 > 1e-6 · FDR→NAVER 재전환 · 축 공백)를 경계로 두고 그 창만 뺀다(사유별 제외 수 기록). 두 라벨 밖 출처가 창에 있거나, 첫 행이 아닌 FDR 행의 change 가 비어 연속성을 볼 수 없으면 `PRICE_BASIS_UNCONFIRMED`. 가격 표시는 '저장 종가(네이버 계열 · 분배락 조정 흔적 · 총수익 여부 미확정)'. 한계: NAVER_FDR 구간 안의 작은 계단은 감지할 수 없어 남는다. 기존 `market_timeseries_ingestion_state` 의 missing_confirm 표시(2026-07-02 뒤 갱신 안 됨)는 쓰지 않고 위 경계 규칙만 쓴다.

### Q-D. 원장 알림 연결 범위

- 사실: §1-5 — 원장에 ticker 가 적히는 곳은 주체(ticker) · 사업군 대표 ETF(`values_json.ticker`) · 기초지수 그룹 구성 ETF(`values_json.tickers`) 세 가지다. 설계 §3 은 '원장에 명시된 ticker 로 연결 · 사업군 키만 있는 항목은 추정 금지'다.
- 추천: link_kind 3종 — `SUBJECT`(기본 표시) / `SECTOR_REPRESENTATIVE`('사업군 신호의 대표 ETF 로 기록됨') / `INDEX_GROUP_MEMBER`('기초지수 그룹 구성 ETF 로 기록됨'). 원장에 실제로 적힌 ticker 와 정확히 같을 때만 연결하고, 따로 표시하며 합치지 않는다. 가격 결과는 series_id 가 이 ticker 인 행만 붙인다. etf_master · 설정 · 이름 · 날짜 근접으로 추정하지 않는다. 엄격 해석이면 `SUBJECT` 만 쓴다.

## 7. 설계자 판정 반영 (2026-10-09 · PASS_TO_IMPLEMENT_WITH_CORRECTIONS · 원문 = 설계서 §10 · 끝에 전달문 원문)

- **Q-A**: 표현 변경만으로 금지 밖이라고 해석하지 않고, 날짜 붙은 **POC5-06 PC 수동 연구 한정 예외**를 기반 문서에 덧붙였다(원래 문장 보존 · 설계자 확정문 그대로) — `docs/PROJECT_ORIGIN_INTENT.md` §9.5 축 2 · `docs/ASSUMPTIONS.md` Q6(별도 연구 계약 · Q6 해결 아님) · POC5-00 설계(§9 · §12 · POC5_PURPOSE) · POC5-00 PLAN(목적 · §9/§12 대조 표) · `docs/STATE_LATEST.md`(POC5 · POC4 상태 · 옛 불변 원칙). ML 코드는 이 동기화 뒤에 구현한다. 화면 · 문서 이름은 '이후 20거래일 최저 종가 변화(연구 추정)'.
- **Q-B**: 연구 축 = 연도 파일 있는 해는 파일, 없는 해는 평일 기본 ∩ KOSPI 저장일(`trading_days_ending(..., stored=KOSPI 저장일)`). snapshot · hash 에 축 날짜 · 연도별 적용 방식(파일/보정) · KOSPI 최신일 · 건너뛴 평일 수와 날짜를 남긴다. 건너뛴 평일을 '확인된 휴장일'이라 하지 않는다. 모델 · 기준 · feature · target · 분할은 같은 축을 쓴다.
- **Q-C**: 라벨만 바뀐 연속 창은 쓴다. 경계 = FinanceDataReader 행 `|change − (close / 직전 저장 종가 − 1)| > 1e-6`(절대 비율 · 0.0001%p) · FDR→NAVER_FDR 재전환 · 축 공백. 허용 밖 출처 · 첫 행이 아닌 FDR 행의 change 누락은 그 창을 뺀다. 최신 t 의 60일 feature 창이 조건을 못 채우면 현재 추정 = `PRICE_BASIS_UNCONFIRMED`(History · 원장 근거는 그대로 조회). NAVER_FDR 구간은 경계 검사가 부분적이라는 안내를 화면 · review 에 둔다. '가격 일관성 확인' · '711종목 ML 유효'라고 쓰지 않는다. 시제품 수치(−1.75% · 6.11/6.65)는 경계 없는 시제품 값이며 RESULT 는 확정 규칙으로 실제 계산한 값을 적는다.
- **Q-D**: `SUBJECT`(기본) · `SECTOR_REPRESENTATIVE` · `INDEX_GROUP_MEMBER`('연관 근거'로 따로 · 제목을 직접 종목 신호처럼 바꾸지 않음). 가격 결과는 같은 `(event_id, item_seq)` 에서 series_id 가 선택 ticker 를 명시한 행만. 현재 설정 · 마스터 · 이름 · 시장 태그로 과거 대표 · 구성을 복원하지 않는다. 그 item 의 t0 · 원시 결과를 ML target 으로 쓰지 않는다.
- **기본값(§2-3) 보완**: 표시할 거래 사실과 모델 입력 선택은 **한 번 읽은 보유 문서**에서 조립한다 — 05 함수가 파일을 다시 읽으면 읽은 문서를 받는 작은 adapter 로 재사용하고(05 계산 계약 불변), revision 이 다른 거래 · ID 를 섞지 않는다. 평가는 '알림 전체 평가'(item 마다 보여도 종목별 여러 건으로 세지 않음). 가격 hash 는 같은 수치라도 fetched_at 이 바뀌면 달라질 수 있다 — '같은 snapshot 결정성'과 '같은 가격 수치의 추정값 불변'을 따로 시험한다. 조회로 v2 저장을 일으키지 않는다.
- **시험 추가(§10-6)**: 파일 있는 해의 KOSPI 누락일은 파일 축 유지 · 파일 없는 해의 보정 · KOSPI 최신일 부족 → `AXIS_UNCERTAIN` · 같은 라벨 내부 계단 · 연속 라벨 전환 · change 누락 · 1e-6 비율 ↔ %p 변환 · 세 연결 종류와 다른 ticker 결과 제외 · 모델과 기준을 서로 다른 검증 날짜로 비교하면 잡히는 변이.
- **진행 순서**: 기반 문서 동기화(완료) → PC backend → 작은 검토 창 목업 사용자 확인 → frontend → 검증자 → 설계자 RESULT → PC 재기동 · 실화면(현재 보유 ETF 하나) → 종료. OCI pull · 새 영업일 · 10-12/10-23 대기 없음. PC 가격 갱신은 선택(필수 게이트 아님).
