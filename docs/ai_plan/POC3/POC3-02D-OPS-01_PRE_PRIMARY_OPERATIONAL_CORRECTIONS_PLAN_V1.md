# POC3-02D-OPS-01 — PRE_PRIMARY_OPERATIONAL_CORRECTIONS PLAN V1

작성일: 2026-09-26 · 작성자: 개발자(VSCode Claude) · 수신: 설계자

```text
STEP_ID                 = POC3-02D-OPS-01
STEP_NAME               = PRE_PRIMARY_OPERATIONAL_CORRECTIONS
PREDECESSOR             = POC5-00
SUCCESSOR               = POC3-02D-OPS-02 (설계자 RESULT 판정 2026-09-27 · 그 뒤 POC5-01A)
PLAN_DECISION           = PASS_WITH_MANDATORY_AMENDMENT_R2 (설계자 최종 2026-09-27)
PLAN_STATUS             = CONFIRMED (R2 반영 · Q23~Q27 확정)
RESULT_DECISION         = PASS_TO_VERIFIER (설계자 2026-09-27 · 원문은 전용 설계서 끝) → 검증자 VERIFIED (2026-09-27)
IMPLEMENTATION          = DONE (C1~C7 · 검증자 VERIFIED 2026-09-27)
FOLLOW_UP               = POC3-02D-OPS-02 — OCI 상세 링크 · Q8 인접 상태 저장 결함 · 낡은 역검증 ⑦ · 목업 ⑦ 제목 정리(설계자 결정 · PRIMARY 전) · 후보: KOSPI stale 화면 문구(Q19 · 2026-09-26 PLAN 판정 · 포함 여부는 OPS-02 PLAN 때 판정)
C3_CODE_CHANGE          = 사용자 원문 확인(2026-09-27 · `현재가 —`) → 수정
C7_CAUSE_FINAL          = UPSTREAM_2026_CSV_STALLED_AT_2026-09-17
C1_LOGIC                = UNBLOCKED
C1_LIVE_DATA            = 사용자가 KRX 에서 직접 다운로드한 원본 수신 · 반영 완료(2026-09-27)
COMMIT_PUSH_OCI         = 커밋(검증자 VERIFIED · STATE_LATEST 1차 갱신 뒤 · 이 문서 포함) · push 별도 승인 대기 · OCI pull 대기
SOURCE_SWITCH           = PROHIBITED
OCI_ACCESS              = 읽기 전용
POC5_IMPLEMENTATION     = NOT_STARTED
PRIMARY_COHORT          = NOT_STARTED (이 단계가 끝나도 시작하지 않음 · §1 끝)
LEGACY_OUTCOME_BACKFILL = PROHIBITED
```

**근거**

- 정정 목록 C1~C7: POC5-00 PLAN §3-1 · §5.
- 분류 기준: 설계자 보완 판정(2026-09-26). 원문은 `docs/ai_design/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_DESIGN_V1.md` 끝 `# 설계자 보완 판정` 에 있다.
- 단계 번호: 설계자 지정(2026-09-26 · 사용자 전달).
- 전용 설계서: `docs/ai_design/POC3/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_DESIGN_V1.md`. 설계자 판정 원문 · C1~C7 범위 · 사용자 입력 대기가 있다.

**문서 규칙**

- 이 문서는 설계자 판정(`PASS_WITH_MANDATORY_AMENDMENT` · 2026-09-26)을 반영한 **확정 PLAN** 이다. C1~C7 마다 사실 · 확정 · 바뀌는 것 · 테스트를 적는다.
- '확정'은 판정 원문(전용 설계서 §3)과 최종 판정 R2(전용 설계서 끝)를 따른다. 둘이 다르면 R2 를 따른다. §6-2 Q23~Q27 은 R2 로 확정됐다.
- 정정 번호 C1~C7 은 POC5-00 PLAN §3-1 의 1~7 과 같다.
- OCI 값은 모두 2026-09-26 읽기 전용 실측이다. 가격 값 · 본문 전문 · 과거 수익률 · 적중률은 출력하거나 열지 않았다. 날짜 · 상태 · 건수 · ticker 식별자만 봤다.
- 원인을 추정한 곳은 `(추정)` 으로 표시했다.

---

## 0. 한눈에

**사실 성격**

- **실제 발생**: 운영 기록으로 실측된 결함.
- **발생 추정**: 코드와 기록으로는 확실하지만, 사용자에게 보인 원문이나 화면은 아직 보지 못한 결함.
- **잠재**: 결함 경로는 코드로 확인됐지만 운영 발생은 0건인 결함.

| 정정 | 내용 | 설계자 분류 | 사실 성격 | 지금 운영 (OCI 실측) | 확정 | 사용자에게 보이는 변화 | OCI pull |
|---|---|---|---|---|---|---|---|
| C1 | 08:00 기초지수 구역 복구 | PRIMARY 전 필수 | **실제 발생** | 09-17 부터 매 거래일 차단 · 발송 5건 모두 후보 0 · 본문 127자 · 09-25 판정의 API 전용 종목 8 | 공용 resolver(최신 유효 CSV 자동 선택 · Q25) + pending gate + `refresh_due`(Q23) · 08:00 안내 1줄(Q24) · 판정 창 검사(Q27) · 새 CSV `20260927` 반영 | 08:00 본문에 '오늘 볼 기초지수' · '국내 날짜 종가' 복귀 | 필요 |
| C2 | 폐지 spike 필수 판정 | 화면 정정 | **발생 추정**(cron 실측 + 코드 · 화면 미확인) | 주석 줄 push-kind 0건 → 코드상 DEGRADED 거짓 경보 | 필수 목록을 운영 3종으로 교체 | 「OCI 운영 상태」 OPERATING | 불필요(PC 백엔드 재기동) |
| C3 | 장중 본문 `현재가 —` | 실제 문구 확인 후 수정 | **발생 추정**(원문 확인 대기) | 통합 본문 발송 8건 · 시각을 채우는 키가 기록에 0회 | 사용자 원문이 `현재가 —` 일 때만 인자 1줄 교체(실행 시각) | '기준' 줄에 실행 시각 표시 | 필요 |
| C4 | 잘린 보유 급락의 잘못된 억제 | PRIMARY 전 필수 | **잠재**(발생 0건) | 정책 활성 뒤 발송 8건 모두 보유 급락 0 · 상한 제외 0 | 저장 대상을 본문에 실린 것 기준으로 재계산 | 잘린 급락이 다음 틱에 발송될 수 있음 | 필요 |
| C5 | Telegram 실패 집계 | 운영 집계 · 증거 정정 | **잠재**(실패 0건) | `holdings_risk_alert` 전송 실패 전 기간 0건 | `send_failed` · '발송 실패 N회' · 출구 4곳 · 성공도 최종 status | 실패가 있던 날만 15:40 줄에 토큰 1개 | 필요 |
| C6 | `message_text_length=0` | 운영 집계 · 증거 정정 | **실제 발생**(기록 결함) | `holdings_risk_alert` 98행 전부 0. 0이 결함인 행은 발송 14행(정책 전 6 · 뒤 8)이다. 나머지(신규 · 악화 없음 58 · 일일 상한 5 · 비거래일 14)는 정정 뒤에도 0이 맞다. push_kind_disabled 7행은 본문 유무를 확인하지 않았다 | flow 에서 조립된 본문 길이 기록 | 없음(기록만) | 필요 |
| C7 | KOSPI 09-17 정지 | 원인 조사 후 판정 | **실제 발생** | 09-18 자료부터 미적재인데 배치는 매일 `kospi=ok(as_of=2026-09-17)` · status success | 감지 정정 A(`failed + source_stale:` · 공용 lag helper 추출 · 유효 종가 `as_of` Q26) · source 교체 금지 · 원인 확정: upstream KS11 `2026.csv` 09-17 정지 | 없음(배치 기록만) | 필요 |

**분류별 묶음**(설계자 보완 판정)

- PRIMARY 시작 전 필수: C1 · C4
- 실제 문구 확인 후 수정: C3
- 운영 집계 · 증거 정정: C5 · C6
- 화면 정정: C2
- 원인 조사 후 판정: C7

---

## 1. 작업 단계 (STEP 1 → STEP 7)

| STEP | 이름 | 내용 | 끝나는 조건 |
|---|---|---|---|
| STEP 1 | 사실 기준선 고정 | 사용자 입력을 받는다. C7 `2026.csv` 마지막 행은 설계자가 확인해 해소됐고(R2 · 09-17), C1 CSV 원본은 2026-09-27 에 받았다. C3 원문도 2026-09-27 에 받았다(`현재가 ㅡ. 직전 종가 2026-09-22` · 사용자 입력 그대로). 기다리는 동안 막히지 않은 구현(STEP 2)은 진행한다. 착수 시점 OCI 읽기로 기준값을 다시 잰다(정합성 JSON API 전용 목록 · 활성 정책 · history 집계 · KOSPI 로그). PC 라이브 state · DB sha256 과 `git status` 를 기록한다. | 입력 · 기준값이 결과서 초안에 인용됨 |
| STEP 2 | C1~C7 구현 | 순서: C2 → C4 → C5 → C6 → C7(A) → C1(resolver · pending gate · `refresh_due` · Q27 판정 창 검사 · Q24 안내 · 검증 스크립트) → C7 Q26 → C1 실제 CSV(`20260927` 반영) → C3(원문 확인 뒤). 항목마다 RED 테스트로 결함을 재현한 뒤 GREEN 으로 만든다. Q8 인접 결함 2개는 tmp 재현만 한다. | 항목별 RED → GREEN |
| STEP 3 | 집중 · 전체 회귀 | `black --check` · `flake8` · `py_compile` · 항목별 집중 테스트 · 전체 pytest(background) · 본문 byte 동일 · C1 검증 스크립트 · 02B-1 MANIFEST(`reproduce.py manifest` 만) | 전부 통과 |
| STEP 4 | 운영 상태 불변 확인 | PC 라이브 state · DB sha256 이 STEP 1 과 같은지, 실발송 0 · 외부 호출 0 인지, PC `.env` `PUSH_AUTOSEND_*` 가 false 인지 확인한다. OCI 쓰기 0 · OCI HEAD 불변도 읽기로 확인한다. | 불변 확인 |
| STEP 5 | 검증자 판정 | 결과서 `docs/ai_result/POC3/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_RESULT.md` 작성 → 설계자 → 검증자 | 판정 PASS |
| STEP 6 | commit · push | 설계자 RESULT 판정 순서: 검증자 `VERIFIED` → `STATE_LATEST` 갱신 → 커밋 · push. push 는 별도 승인이다. | `origin/main` 반영 |
| STEP 7 | OCI 적용 및 사후 실측 | pull 직전에 OCI 정합성 JSON 의 `api_only` 를 다시 읽어 새 CSV 와 대조한다. 새 CSV 에 없는 ticker 가 있으면(pending gate 로 d20 종가가 없는 것은 제외) pull 하지 않고 멈춰 보고한다. CSV 를 다시 받을지는 설계자 · 사용자가 판정한다. 대조가 맞으면 사용자가 OCI `git pull` 을 한다(거래일 15:40 뒤 ~ 다음 거래일 07:15 전). C2 는 PC 백엔드 재기동. 사후 OCI 읽기와 사용자 실화면 확인(§3 항목별) 뒤 `STATE_LATEST` 를 갱신한다. | 사후 실측 인용 |

**PRIMARY**: 이 단계의 pull 로는 시작하지 않는다. 확정 Q28 · POC5-00 PLAN §2-7 과 설계자 RESULT 판정(2026-09-27)대로 아래 세 가지가 모두 끝난 뒤 첫 KRX 거래일부터 시작한다.

1. 이 단계의 운영 정정 반영. Q21 로 C1 을 뒤 라운드로 분리하면 그 반영까지 포함한다.
2. POC5-01 코드 pull(OCI reflog 로 확인).
3. 후속 `POC3-02D-OPS-02` 완료(설계자 RESULT 판정 — OCI 상세 링크 · Q8 인접 상태 저장 결함 · 낡은 역검증 ⑦ 정리 · PRIMARY 전).

시작일과 근거는 POC5-01 원장 메타에 기록한다.

- Q20 확정: C1~C7 모두 PRIMARY 전에 반영한다. C7 은 감지 정정까지이고, source 복구는 선행조건이 아니다.
- Q21 확정: C1 을 분리해도 PRIMARY 는 C1 까지 기다린다.

**되돌리기**: 모든 정정은 코드 · 데이터 파일 변경뿐이다. 스키마 · 상태 파일 이관이 없으므로 revert + pull 로 원복된다.

---

## 2. 공통 사실

- **OCI 코드 = 저장소 코드.** OCI HEAD 는 `8bf843e6` 이고 추적 파일 변경은 0이다. `8bf843e6..3b6e3257` 은 문서 3개뿐이다(`git diff --stat`). 그래서 이 PLAN 의 코드 줄 번호가 OCI 에서 실제로 도는 코드와 같다.
- **다음 거래일은 2026-09-29(화)다.** `krx_trading_days_2026.csv` 에 09-24 · 09-25 · 09-28 이 없다.
- **러너는 건드리지 않는다.** `scripts/run_three_push_runtime_oci.py` 는 646줄이다(KS-10 트리거 650). 확정안 모두 러너 변경 0이다.
- **활성 장중 정책**(`intraday-20260921T144447-168782`): enabled True · `max_items_per_section` 3 · `max_sends_per_day` 4 · `cooldown_minutes` 120.
- **정책 활성 뒤 `holdings_risk_alert`**: 09-22 · 09-23 에 14틱이 돌았다. 발송 8 · skip 6(일일 상한 5 · 신규 · 악화 없음 1)이다. 09-24 · 25 는 비거래일 skip 이다.

---

## 3. 정정 항목 (C1 → C7)

### C1 — 08:00 기초지수 구역 복구 · PRIMARY 전 필수 · 실제 발생

**사실**

- 차단 규칙: API 에만 있는 ticker(`api_only`)나 기초지수명 불일치가 1건이라도 있으면 블록 전체가 `CSV_REFRESH_REQUIRED` 다(`app/market_briefing/meta_gate.py:157-161` · 02B-2 설계 §5.2). 본문은 안내 1줄 '기초지수 정보는 공식 기준정보 갱신이 필요해 제외했습니다.'(`render.py:52`)로 바뀐다.
- 직접 원인(OCI 실측):
  - 공식 CSV `krx_etf_basic_20260909.csv`(09-09 수동 다운로드 · cp949 · 17컬럼 · 1,168행)에 없는 신규 상장 ETF 가 기준일에 들어왔다.
  - 첫 4종 `0227L0` · `0238F0` · `0239Y0` · `0239Z0` 의 KRX 적재 첫 날짜는 09-15(화)다.
  - 07:20 KRX 기준일은 실행일보다 2거래일 앞선다. 그래서 09-17 07:20 에 처음 들어왔고, 그날부터 차단됐다.
  - CSV 에만 있는 `465780`(마지막 적재 09-14 · 만기매칭 채권 ETF 로 추정)은 차단 원인이 아니다.
- **09-25 07:20 판정**(OCI `market_briefing_meta_consistency_latest.json`):
  - `api_basis_date` 20260922 · `api_only` **8종**: 위 4종 + `0238C0` · `0240J0` · `0241R0` · `0242S0`.
  - `csv_only` 1(`465780`) · 기초지수명 불일치 0 · `exact_match_count` 1,167 · `join_coverage` 0.993191.
  - 추가 4종의 KRX 적재 첫 날짜는 모두 09-22(화)다(적재 건수 09-21 1,171 → 09-22 1,175). **화요일 상장분이 이후 07:20 기준일에 들어와 차단 대상이 늘어나는 현상이 두 번 관측됐다**(09-15 상장분 → 09-17 07:20, 09-22 상장분 → 09-25 07:20). 다만 CSV 를 갱신한 적이 없으므로 '갱신 뒤 재차단'은 아직 관측된 적이 없다.
- 08:00 기록: 09-17 · 18 · 21 · 22 · 23 발송 5건 모두 `index_status=CSV_REFRESH_REQUIRED` · 후보 0 · 본문 127자다.
- 파일명이 상수로 고정돼 있다. 08:00 은 `app/three_push_runtime/runner_market_briefing.py:28`, 07:20 은 `scripts/run_oci_market_data_batch.py:47` 에 따로 정의돼 있다. 장중 설정 생성기 `app/intraday_config/generator.py:56` 에 세 번째 사본이 있다. 최신 파일을 고르는 규칙은 없다.
- 상장 빈도(현 CSV 상장일 기준 최근 12개월): 191종이 상장했고, 52주 중 44주에 1건 이상이며, 요일은 화요일이 171건이다.
- 신규 ticker 는 d20 종가가 없으면 후보 계산에서 원래 빠진다. `compute_index_leadership` 은 latest · d5 · d20 종가가 모두 있는 ticker 만 n 에 넣는다. d20 은 저장 거래일 `days[-21]` 이다(`app/market_briefing/krx_store.py:202-213`). 즉 적재가 약 20거래일이 안 된 ETF 는 CSV 에 행이 있어도 후보 수치에 영향이 0이다.
- 가려진 관문: 최신성 관문(lag>1 → stale · `MAX_STALE_TRADING_DAYS=1`). KRX 기준일이 2거래일 늦으므로 평상시 lag=1 로 임계와 같다. 게재가 하루 더 늦으면 '최신성' 안내로 바뀔 수 있다(추정 · 09-17 이후에는 CSV 관문이 먼저 끊어서 기록에 보이지 않는다).

**확정 설계**(설계자 판정 Q1~Q5 · C1 필수 보완)

- **공용 resolver**(Q1 · Q2): 07:20 배치와 08:00 러너가 같은 함수를 부른다. 새 모듈은 `app/market_briefing/official_csv.py` 다. 파일명 상수 `OFFICIAL_ETF_CSV` 로 파일을 고르지 않는다.
  - 후보: `state/market_meta/krx_etf_basic_*.csv`.
  - 선택: 파일명 날짜(`YYYYMMDD`)가 가장 늦고 검증을 통과한 파일을 결정적으로 고른다.
  - fail-loud 검사:
    - 파일명 날짜 파싱(엄격 패턴 `krx_etf_basic_YYYYMMDD.csv`).
    - 동일 날짜 파일 중복.
    - CP949 디코딩.
    - 17개 컬럼(`20260909` 헤더와 같음).
    - 단축코드 중복 · 빈 기초지수명.
  - 기록: 선택 파일명 · SHA-256 · `csv_asof` 를 정합성 JSON(07:20)과 08:00 진단에 남긴다. 검사에 걸린 파일과 사유도 함께 남기고 로그에 경고한다.
  - Q25 확정(R2): 가장 늦은 파일이 검사에 걸리면 그 이전의 최신 유효 파일을 고르고, 거부 파일명 · 원본 SHA-256 · 사유를 JSON · 로그에 남긴다. 동일 날짜 파일이 둘 이상이면 그 날짜 묶음 전체를 무효로 보고 이전 유효 날짜로 내려간다.
  - 유효 파일이 하나도 없으면 지금처럼 fail-closed 다(`CSV_REFRESH_REQUIRED` + error).
- **pending gate**(Q1 (c)):
  - `api_only` 중 d20 종가가 없는 ticker 는 차단하지 않는다. `api_only_pending`(ticker · 첫 적재일)으로 기록한다.
  - d20 종가가 있는 `api_only` 와 기초지수명 불일치는 지금처럼 `CSV_REFRESH_REQUIRED` 다. coverage 규칙도 그대로다.
  - 판정은 07:20 에서 한다(적재 직후 · 같은 응답). 08:00 은 결과만 읽는다.
  - 02B-2 §5.2 '1건이라도 차단' 계약은 이 판정(Q1)으로 개정된다.
- **`refresh_due`**(Q1 · Q23 확정 R2): 07:20 이 적재 직후 정한다.
  - pending ETF 마다 `remaining_trading_days = max(0, 21 - stored_trading_day_count)` 를 기록한다. `stored_trading_day_count` 는 그 ETF 의 저장된 KRX 거래일 수다.
  - `refresh_due = (가장 오래된 pending 의 remaining_trading_days <= 5) OR (status == CSV_REFRESH_REQUIRED)`.
  - 정합성 JSON 과 07:20 배치 로그에 매회 상태를 남긴다.
- **08:00 안내**(Q24 확정 R2): 확정 문구 `※ 운영 안내: KRX ETF 전종목 기본정보 CSV를 갱신해 주세요.` 를 08:00 본문 끝에 1줄 붙인다.
  - `refresh_due` 가 false → true 가 된 주기마다 한 번만 알린다(07:20 이 주기 id 를 기록하고, 전체 발송 성공 뒤 알린 주기를 시장 브리핑 상태에 저장).
  - 그날 08:00 발송이 없으면 다음 실제 발송까지 보류한다. 안내 때문에 발송을 만들거나 브리핑을 막지 않는다. fingerprint 도 바꾸지 않는다.
- **판정 창 검사**(Q27 확정 R2 · 개발자 제안 (a) 불승인): 07:20 이 `evaluated_api_basis_date` · `evaluated_window_d20_date` · `evaluated_at_kst` 를 JSON 에 남긴다.
  - 08:00 은 현재 창(`krx_store.resolve_window`)과 비교한다. 일치하면 저장된 판정을 쓴다.
  - 누락 · 불일치면 기초지수 구역만 fail-closed 한다. 진단 상태는 `META_GATE_STALE` 이고 `CSV_REFRESH_REQUIRED` 로 표시하지 않는다. 그 JSON 의 `refresh_due` 도 안내에 쓰지 않는다.
  - 미국 전망 한 줄 등 나머지 브리핑은 정상 진행한다. 재계산이 아니라 저장된 판정이 오늘 창의 것인지 확인하는 안전 검사다.
  - 본문의 제외 안내 문구는 R2 가 정하지 않았다. 새 문구를 만들지 않고 기존 승인 문구(`STATUS_API_FETCH_FAILED` 의 '기초지수 정보는 최신 기준을 확인하지 못해 제외했습니다.')를 재사용한다 — 결과서 §7 확인 항목.
- **`20260909` 고정**(Q3): 다음은 `20260909` 경로를 그대로 쓰고, 운영 resolver 와 섞지 않는다.
  - 장중 설정 생성기(`app/intraday_config/generator.py:56`).
  - 02B-1 재현(`scripts/ops02b1_gate/reproduce.py:42`).
  - 장중 역검증 스크립트(`scripts/ops02c/reverse_verify_guards.py:32`).
  - 기존 테스트 fixture.
- **운영 규칙**(Q4): OCI pull 은 07:15~08:05 에 하지 않는다. 코드 시간 가드는 넣지 않는다.
- **최신성 관문**(Q5): `MAX_STALE_TRADING_DAYS=1` 을 그대로 두고, 복구 뒤 드러나는 결과를 관찰한다.
- **앞으로의 CSV 갱신 = 데이터 파일 추가만**:
  - 사용자가 원본을 전달하면 개발자가 `state/market_meta/krx_etf_basic_YYYYMMDD.csv` 로 byte 그대로 추가한다. 코드는 바꾸지 않는다.
  - 검증 스크립트와 C1 집중 테스트가 통과하면 전체 검증자 재판정 없이 진행한다. 검증 스크립트는 새 파일 `scripts/check_krx_etf_basic_csv.py` 이고, PC 전용 · 외부 호출 0이다.
  - commit · push · OCI pull 승인은 그대로 받는다.
- **거부한 방법**:
  - 같은 파일명 덮어쓰기: `csv_asof` 를 파일명에서 읽고, MANIFEST sha 가 깨진다.
  - 자동 다운로드: 범위 밖이고 KRX 로그인이 필요하다.
  - 누락 행 수기 추가: 수동 편집본 금지 규칙 위반이다.

**바뀌는 것**

- 07:20 · 08:00 의 CSV 선택이 '고정 상수'에서 'resolver 가 고른 최신 유효 파일'로 바뀐다. 지금 저장소에는 `20260909` 하나뿐이라 선택 결과는 같다.
- d20 종가가 없는 신규 ETF 는 더 이상 차단 사유가 아니다.
  - 지금 `api_only` 8종은 첫 적재가 09-15 · 09-22 라 모두 적재 21거래일 미만이다.
  - 09-25 판정 기준으로 기초지수명 불일치 0 · coverage 1,167/1,175 = 0.9932 이다.
  - 그래서 **새 CSV 가 오기 전에도** pull 뒤 첫 07:20 판정이 ok 가 될 수 있다(추정 · 최신성 관문은 별도).
  - 새 CSV 가 들어오면 pending 이 비고, 다음 갱신까지 여유가 다시 생긴다.
- 정합성이 ok 이면 08:00 본문에서 안내 줄이 빠진다. 후보가 있으면 '오늘 볼 기초지수'(최대 2그룹 × 2줄)와 기준 줄 '국내 {날짜} 종가' 가 붙는다. 후보가 0이면 기준 줄에 국내 날짜만 붙는다.
- 미국 전망이 NONE 인 날은 skip 에서 기초지수 중심 발송으로 바뀔 수 있다. 02B-2 목업 ③④ 에 이미 있는 동작이다.
- 정합성 JSON 과 08:00 진단에 필드가 더해진다: 선택 파일명 · `api_only_pending`(첫 적재일 포함) · resolver 검사 결과.
- 문구 · 시각 · 임계는 바뀌지 않는다. 관문 규칙은 pending gate 만 바뀐다.

**테스트**

- resolver:
  - 여러 날짜 파일 중 가장 늦은 유효 파일을 고르고, 같은 입력이면 같은 결과를 낸다.
  - 패턴 밖 이름 · 날짜 파싱 실패 · 동일 날짜 중복 · CP949 실패 · 컬럼 수 불일치 · 단축코드 중복 · 빈 기초지수명 → 각각 기록되고 경고된다. 가장 늦은 파일이 떨어지면 이전 최신 유효 파일을 고른다(Q25).
- `refresh_due`(Q23): remaining 6 · 5 · 0 경계 · `CSV_REFRESH_REQUIRED` 만으로 true · 주기 id 유지 · 새 주기 · 해제.
- 판정 창 검사(Q27): 일치 · 불일치 · 누락 → `META_GATE_STALE` · 나머지 본문 유지 · 오래된 `refresh_due` 무시.
- 08:00 안내(Q24): 주기당 한 번 · `META_GATE_STALE` 이면 붙지 않음 · skip 날은 다음 발송으로 보류 · 전체 발송 성공 뒤에만 상태 저장 · fingerprint · 발송 판정 불변 · 안내가 없을 때 본문 byte 동일.
  - 유효 파일 0개 → fail-closed.
  - 선택 파일명 · sha · `csv_asof` 가 기록된다.
- 07:20 · 08:00 이 같은 resolver 를 부르는지 고정한다(한 층만 바꾸는 회귀 방지).
- `20260909` 고정 경로(장중 생성기 · 02B-1 재현 · 역검증 스크립트)가 resolver 결과와 무관한지 고정한다.
- pending gate:
  - `api_only` + d20 없음 → ok + pending 기록(첫 적재일 포함).
  - `api_only` + d20 있음 → `CSV_REFRESH_REQUIRED`.
  - 기초지수명 불일치 → 불변.
  - coverage 0.95 경계 → 불변.
  - 신규 ticker 가 있든 없든 후보가 같음(수치 영향 0 결속 테스트).
- 검증 스크립트: 올바른 파일은 통과(exit 0), 잘못된 파일은 사유와 함께 실패(exit 1).
- 기존 회귀: `test_market_briefing_contracts` · `test_market_briefing_batch` · `test_market_briefing_flow_through` · `test_intraday_config_*`(`20260909` 계속 사용).
- 02B-1 MANIFEST sha 불변은 `python scripts/ops02b1_gate/reproduce.py manifest` 만 실행해 확인한다. 통계 섹션(operating · outlook · index)은 과거 적중률 · 수익률을 출력하므로 실행하지 않는다.
- 반영 전 PC 대조(테스트가 아니라 결과서 증거 · CSV 도착 뒤):
  - 새 CSV 대 `20260909` 의 추가 ticker 에 위 8종이 모두 들어 있는지 확인한다. 그 뒤 상장분이 더 있을 수 있다.
  - 삭제 ticker 에 `465780` 이 있는지 확인한다.
  - 공통 ticker 의 기초지수명 변경 수를 센다.
  - 착수 시점 OCI 정합성 JSON 의 `api_only` 목록을 읽어, 새 CSV 에 모두 있는지 대조한다(`api_only` 0 예측 · STEP 7 pull 직전에 한 번 더).
  - git 저장본 sha 가 원본 sha 와 같은지 확인한다.
- 반영 뒤 OCI 읽기: 정합성 JSON(status · 선택 파일명 · `api_only` · pending · 불일치 · `csv_asof` · sha)과 08:00 기록(`index_status` · 후보 수 · 본문 길이).

**사용자 조치** — **완료(2026-09-27 원본 수신)**. 반영 전 PC 대조 결과는 다음과 같다.

- 파일 `KRX_증권상품_ETF_전종목기본정보_20260927.csv` · 373,228 byte · SHA-256 `0f0c074240e66c6d7a3406861c287dc63b8137c7aa497e5db509fae9f8722314`. 저장소에는 byte 그대로 `state/market_meta/krx_etf_basic_20260927.csv` 로 넣는다.
- cp949 디코드 OK · 17컬럼(`20260909` 헤더와 동일) · 1,175행 · 단축코드 중복 0 · 기초지수명 · 지수산출기관 빈 값 0.
- `20260909` 대비 추가 8종 = OCI 09-25 판정의 API 전용 8종과 정확히 같다(상장일 09-15 · 09-22). 삭제는 `465780` 1종. 공통 ticker 기초지수명 변경 0.
- 다운로드 날짜(2026-09-27)와 메뉴 경로(증권상품 > ETF > 전종목 기본정보)는 파일명에서 읽은 값이었다. 사용자가 KRX 에서 직접 다운로드한 파일임을 대화에서 확인했다(2026-09-27). 설계자 RESULT 판정 표의 출처(KRX Data Marketplace) · 다운로드일도 같고, 설계자는 원본 내용을 대조했다. 추석 연휴 중 받은 파일이라 `2026-09-27` 은 다운로드 · 스냅샷 날짜이고 거래 기준일이 아니다.

원래 요청했던 절차(기록용):

- KRX 정보데이터시스템에 로그인해 ETF 전종목 기본정보 CSV 를 받는다.
- 파일을 Excel 로 열어 다시 저장하지 않는다(인코딩 · byte 가 바뀐다).
- 원본 파일, 다운로드 날짜, 실제 메뉴 경로를 전달한다. 저장소에 출처 메뉴 기록이 없다.
- 파일명 날짜는 화면에 기준일 표시가 없으면 다운로드 날짜로 한다(기존 `20260909` 와 같은 규칙).

### C2 — 폐지 spike 필수 판정 · 화면 정정 · 발생 추정

**사실**

- 필수 목록은 `_REQUIRED_PUSH_KINDS = ("market_briefing", "holdings_briefing", "spike_or_falling_alert")` 다(`app/oci_startup_status.py:108-112`).
  - POC3-07(2026-08-05~06) 때 정한 뒤 바뀌지 않았다.
  - OPS-02A(09-07~08)에서 cron 의 spike 7줄이 `holdings_risk_alert` 7줄로 바뀔 때 같이 고쳐지지 않았다.
- 판정 규칙(`:115-128`): 필수가 모두 있으면 OPERATING, 하나라도 없으면 DEGRADED, 0개면 UNKNOWN 이다. 필수 목록 밖의 kind 는 무시한다.
- PC 백엔드가 기동할 때 SSH 로 한 번 `crontab -l` 에서 `--push-kind` 를 뽑는다. 주석 줄은 거르지 않는다(`:165-173`).
- **OCI 실측**:
  - 모듈과 같은 방식으로 뽑으면 `holdings_briefing` · `holdings_risk_alert` · `market_briefing` 이다.
  - 주석 줄 안의 `--push-kind` 는 0건이다.
  - 따라서 코드 판정은 DEGRADED '일부 스케줄 누락: spike_or_falling_alert' 다(거짓 경보).
  - 반대로 `holdings_risk_alert` 가 빠져도 감지하지 못한다.
  - 화면 값은 직접 보지 못했다. PC 백엔드 로컬 API 가 응답하지 않았고, 이 판정은 코드에 실측값을 대입한 결과다.
- 표시 위치는 「진단 · 상태 > OCI 운영 상태」(overall · jobs)와 「오늘 확인 > 오늘의 투자 점검」 상단 한 줄이다. 프론트는 문자열을 그대로 보여 주므로 프론트 변경은 0이다.
- 기존 테스트 4곳이 옛 목록을 고정하고 있다(`tests/test_oci_startup_status.py:18-23` · `:26-30` · `:44-51` · `:66-76`).
- 이름이 같은 상수가 둘 있다. `app/three_push_runner_common.py:44-50` 의 `VALID_PUSH_KINDS` 는 `holdings_risk_alert` 를 포함한다. `scripts/three_push_oci_helpers.py:60` 의 같은 이름 상수는 포함하지 않는다.

**검토한 선택지**

- **A.** 튜플 1줄을 운영 3종으로 바꾼다. 문구 · 원격 명령 · API · 프론트는 그대로 둔다.
- **B.** A 에 더해 주석 줄 제외 필터를 넣는다.
- **C.** A 에 더해 폐지 kind 경고를 표시한다(새 문구).
- **D.** 운영 kind 정본 상수를 새로 만든다. 러너 공통 모듈을 건드리고, POC5-01 허용 목록과 겹친다.

**확정**(Q14): A — 운영 3종 목록 교체만.

- B 는 주석 줄이 0건으로 실측됐으므로 이번 범위 밖으로 두고 알려진 한계로 기록한다.
- C · D · 틱 수 검사도 범위 밖이다.
- 문구 '필수 스케줄(시장·보유·급등락)' · '필수 3종' 은 유지한다. 개수가 3으로 같고, '급등락' 은 이제 [장중 급등락](`holdings_risk_alert`)을 가리킨다.

**바뀌는 것**

- 「OCI 운영 상태」가 DEGRADED/STALE 에서 OPERATING/SUCCESS '필수 스케줄(시장·보유·급등락) 모두 등록됨' 으로 바뀐다.
- 한 줄은 'OCI 자동 운영 스케줄 활성 (필수 3종 등록 · 기동 시 확인)' 이 된다.
- `holdings_risk_alert` 가 빠지면 DEGRADED 로 그 이름을 표시한다. spike 줄이 다시 생겨도 무시한다.
- OCI 동작 변화는 0이고 pull 은 필요 없다. PC 백엔드를 재기동해야 반영된다.

**테스트**

- 기존 4곳을 새 목록으로 바꾼다.
- 지금 cron 모양 → OPERATING(재발 방지).
- 옛 cron 모양 → DEGRADED · `missing=['holdings_risk_alert']`.
- 4종 모두 → OPERATING.
- 계약: `set(_REQUIRED_PUSH_KINDS)` 가 운영 3종이고, spike 가 없고, `app.three_push_runner_common.VALID_PUSH_KINDS` 에 포함된다. 패키지용 `scripts/three_push_oci_helpers.py:60` 상수는 쓰지 않는다.

**문서**(Q15 확정)

- `PROGRAM_TRUTH` 에 '필수 판정 = 운영 3종' 을 적는다.
- §5.2 · §9-D 에 'diagnostics' 로 남은 위치 stale 을 고친다.
- `PROGRAM_TRUTH` §4(130행)가 가리키는 옛 crontab 문서(07-25 DRAFT · spike 7틱 · UTC) 머리에 SUPERSEDED 안내 1줄을 넣는다.

백엔드 파일을 바꾸므로 검증자 대상이고, 재기동 뒤 사용자 실화면 확인도 받는다.

### C3 — 장중 본문 `현재가 —` · 실제 문구 확인 후 수정 · 발생 추정

**사실**

- 렌더는 `quote_asof` 가 없으면 '기준' 다음 줄을 `현재가 — · 직전 종가 <날짜>` 로 낸다(`app/runtime_evidence/intraday_alert_render.py:236`). 이 줄은 구역이 하나라도 있는 통합 본문에 항상 붙는다.
- 운영 경로는 `quote_asof=outcome.diagnostics.get("risk_quote_asof")` 로 읽는다(`app/runtime_evidence/holdings_risk_flow.py:297`). 그런데 저장소 전체에 이 키를 채우는 곳이 0이다(grep). 추가 커밋 `b79d1468` 은 읽는 쪽만 넣었다.
- **OCI 실측**:
  - `oci_runtime_history.jsonl` 에 `risk_quote_asof` 가 0회 나온다.
  - 정책 활성 뒤 통합 본문 발송은 8건이다: 09-22 09:30 · 10:30 · 12:30 · 13:30, 09-23 09:30 · 10:30 · 11:30 · 12:30.
  - 본문은 어디에도 저장되지 않는다. 원문은 사용자 Telegram 에만 있다.
- 설계 §7 목업은 `현재가 2026-09-21 10:30 · 직전 종가 2026-09-18` 이다. 헤더 `[장중 급등락] 10:30` 과 시각이 같다.
- 같은 러너의 구 [보유 급락 알림] '시세'(`holdings_risk_flow.py:145`)와 보유 브리핑(`holdings_selection_flow.py:196`)은 `format_quote_asof(runtime_kst)` 를 쓴다.
- 놓친 이유: 이 줄을 보는 테스트는 렌더에 값을 직접 넘기는 단위 테스트 1건뿐이다(`tests/test_intraday_alert_render.py:335-348`). 결과서 목업도 렌더를 직접 불러 만들었다(추정).

**사용자 원문 확인(2026-09-27)**: 사용자 입력 그대로 `현재가 ㅡ. 직전 종가 2026-09-22`. 손으로 옮긴 것이라 `—` · `·` 이 `ㅡ` · `.` 으로 적혔다. 시각이 없고 줄표만 있으므로 결함이 실수신 메시지에서 확인됐다. 수정 전 코드로 run() 관통 테스트를 돌리면 `현재가 — · 직전 종가 2026-08-25` 로 실패해 같은 결함이 재현된다(RED).

**확인 절차**(설계자 분류대로 수정 전에 한다)

1. 사용자가 Telegram 에서 위 8건 중 1건 이상을 열어 '기준' 다음 줄 원문을 전달한다. 예상 원문은 `현재가 — · 직전 종가 YYYY-MM-DD` 다.
2. OCI 코드 동일성은 확인을 마쳤다(§2).
3. 구현할 때 run() 경로 테스트를 먼저 RED 로 만들어 `현재가 —` 를 재현하고, 그 결과를 결과서에 인용한다.

원문이 예상과 다르면(시각이 찍혀 있으면) 수정하지 않고 멈춰 보고한다.

**검토한 선택지**

- **A.** `:297` 인자를 `format_quote_asof(runtime_kst)` 로 바꾼다. 1줄이고 import 는 이미 있다.
- **A'.** `diagnostics["risk_quote_asof"]` 를 채운다. 본문 결과는 같지만 JSONL 에 새 키가 생긴다.
- **B.** 종목별 체결 시각(`price_asof`)을 쓴다. 어느 종목 값을 보일지 새로 정해야 하고 범위가 커진다.
- **C.** 줄을 없애거나 그대로 둔다. 설계 §7 목업과 어긋난다.

**확정**(Q9 (a)): A. 단, 사용자 원문이 정말 `현재가 —` 일 때만 수정한다(`C3_CODE_CHANGE = BLOCKED_BY_USER_MESSAGE_TEXT`). Q10 확정: '직전 종가' 날짜 축 문제는 범위 밖으로 기록한다.

**바뀌는 것**

- 「장중 급등락」 '기준' 다음 줄이 `현재가 YYYY-MM-DD HH:MM · 직전 종가 <날짜>` 가 된다.
- 시각은 러너 시작 시각이고 헤더 HH:MM 과 같다. 본문은 15자 늘어난다.
- 그 밖의 본문 줄 · 구 본문 · 상태 · 집계 · record 키 · 러너는 바뀌지 않는다.

**테스트**

- run() 관통 RED → GREEN. 다음 줄이 정규식 `^현재가 \d{4}-\d{2}-\d{2} \d{2}:\d{2} · 직전 종가 ` 와 맞고, `현재가 —` 가 없어야 한다.
- 조립 단위: `runtime_kst=2026-09-22T10:30:12+09:00` → `현재가 2026-09-22 10:30`. 헤더와 시각이 같아야 한다.
- 구 본문 '시세' 와 같은 값인지 확인한다.
- '기준' 다음 줄 말고는 본문 줄이 같은지 확인한다.
- 렌더 기본값(None → `—`) 계약은 그대로인지 확인한다.
- 금지 문구 · raw 식별자 가드를 통과하는지 확인한다.

### C4 — 잘린 보유 급락의 잘못된 억제 · PRIMARY 전 필수 · 잠재

**사실**

- 저장 대상은 조립 시점에 선정 전체로 정해진다. `out.save_entries = merge_worst(selected=selected, previous=previous)`(`holdings_risk_flow.py:134` · 주석 '발송 여부와 무관하게 계산해 둔다'). 여기서 `out` 은 `build_holdings_risk_alert` 의 `HoldingsRiskOutcome`(`:62`)이다.
- 정책이 활성이면 통합 본문이 구 본문을 대체한다(`:365-368`).
  - 「보유종목」 구역은 급락 → 급등 순으로 채운다.
  - 구역 상한 3을 넘친 것은 `plan.dropped`(`reason: section_cap`)에만 남는다(`intraday_alert_render.py:128-150`).
  - 이때 `save_entries` 는 다시 계산되지 않는다.
- 발송이 성공하면 러너가 `save_entries` 를 그대로 저장한다(`app/three_push_runtime/runner_evidence.py:239-250`). 그 결과:
  - 잘린 신규 종목은 더 나쁜 구간으로 가지 않는 한 그날 억제된다.
  - 잘린 악화 종목은 발송 없이 worst 로 기록돼, 그 악화 알림이 사라진다.
- 이 동작은 기존 계약 두 가지와 어긋난다. OPS-02A 는 '미발송 신호를 발송 완료로 기록하지 않는다', OPS-02 설계 §14-2 는 '실패 · 부분 전송 · 상한 제외 신호는 발송 진척을 전진시키지 않는다'이다. 사업군 · 급등은 D1(본문에 실린 것만 발송으로 기록 · `intraday_alert_flow.py:425-436`)로 이미 지키고 있다.
- 구 본문 경로(정책 비활성 · 장중 조립 예외)는 전 종목을 싣기 때문에 잘림이 없다. 일일 상한 회차는 저장 자체가 없다.
- **OCI 실측**:
  - 정책 활성 뒤 발송 8건은 모두 `risk_new_count` + `risk_worsened_count` = 0 · 본문 보유 급락 0 · `intraday_dropped_by_cap` 0 이다. 결함 경로는 **아직 한 번도 발생하지 않았다**.
  - 정책 활성 전 발송 6건(09-10~09-14)은 구 본문이었다.
  - 잠재 결함이며, 광범위 하락일(보유 급락 3종목 초과)에 처음 드러난다.
- 이 동작을 고정하는 기존 테스트는 없다. flow-through rig 는 보유 1종목이고, 러너 테스트는 정책 비활성이다.

**검토한 선택지**

- **A.** `holdings_risk_flow.py` 한 파일만 바꾼다. 저장 대상을 본문에 실린 것 기준으로 다시 계산한다.
  - kept = 본문에 실린 보유 급락 + 이번 회차에 보낼 대상이 아니던 선정분(억제분).
  - `merge_worst(kept, previous)` 로 계산한다. 잘린 악화 종목은 이전 worst 가 그대로 유지된다.
- **B.** 러너 저장 단계(`runner_evidence`)에서 `plan.dropped` 로 걸러낸다. 저장 계층이 어느 본문이 나갔는지 추론해야 하고 렌더 구조에 묶이므로 권장하지 않는다.
- **C.** A 에 더해 `intraday_alert_flow` 에 `sent_held_drop` 필드를 둔다. 운영 파일이 2개가 되고 동작 이득은 없다.
- **D(기각).** 보유 급락을 상한에서 빼거나 심각도 순으로 재정렬한다. 본문 byte 와 설계 §6 이 바뀐다.

**확정**: A. Q6: 상세 ticker 는 JSONL 에 추가하지 않는다(POC5-01 이 맡음). Q7: 정렬 순서는 유지한다. 구현 조건은 네 가지다.

1. 재계산 위치: `assemble_intraday_alert` 가 반환된 직후, `out.intraday = intraday`(`:301`) 대입보다 먼저 지역 변수로 계산한다. `will_send()` 이고 일일 상한이 아닐 때만 한다. 본문 대체(`:368`) 때 그 값을 `outcome.save_entries` 에 넣는다.
   - 여기서 `outcome` 은 지역 변수이고 `out.outcome` 과 같은 `HoldingsRiskOutcome` 이다(`:261` · `:270`).
   - 이 함수의 `out` 은 `RiskAssembly`(`:209-222` · `:244`)라 `save_entries` 필드가 없다. 여기에 대입하면 오류 없이 새 속성만 붙고 저장에는 반영되지 않는다.
   - 러너는 `_rasm.outcome` 을 `risk` 로 받아 `risk.save_entries` 를 저장한다(`run_three_push_runtime_oci.py:366` · `:498` · `runner_evidence.py:244-246`).
   - 재계산이 예외를 내면 기존 '장중 조립 예외' 경로와 같아진다. `out.intraday` · `intraday_records` 는 비어 있고, 구 본문 + 위험 상태 전체 저장이 되며, 사업군 · 급등 발송 상태와 집계 쓰기는 0이다.
   - 본문 대체 직전에 재계산하면 안 된다. `:301` 뒤에 예외가 나면 구 본문이 나가는데도 사업군 · 급등 신호가 발송 완료로 기록되기 때문이다(`runner_evidence.py:137-173`).
2. `merge_worst` 는 바꾸지 않는다.
3. 구 본문 · 일일 상한 · 실패 · 부분 전송 분기는 코드 변화 0이다.
4. 본문 byte 동일을 테스트로 고정한다.

**알려진 한계**(기존 틈 · 이번 범위 밖): `:301` 대입 뒤 재계산 말고 다른 예외(예: `intraday_records` 구성)로 구 본문이 나가면, 사업군 · 급등 `last_sent_at` 이 전진한다. 가능성은 낮다. Q8 확정: tmp 로 재현해 결과서에 보고하고, 이번 단계에서 고치지 않는다.

**바뀌는 것** — 정책 활성 · 통합 본문 발송 · 보유 급락 3종목 초과 회차에서만 달라진다.

- 잘린 급락은 worst 에 기록되지 않는다. 다음 틱에 신규 · 악화로 다시 잡히고, 일일 상한이 남아 있으면 발송된다.
- 광범위 하락일에 조건형 발송 회차가 늘 수 있다. 예를 들어 급락 6종목이면 09:30 에 3, 10:30 에 3이 나간다.
- 상한(회차당 1건 · 하루 4건 · 구역 3)은 그대로다. 그만큼 그날 뒤쪽 신호가 쓸 일일 상한이 먼저 소진된다. KS-5 는 설계 §13-3 에서 조건형 급변 예외로 확정돼 있다.
- 본문 문구 · 순서 · 구간 임계 · 7틱 · 구 본문 경로 · 사업군 · 급등 상태 저장은 바뀌지 않는다.

**테스트**(tmp 경로 · 대역 전송기)

- run() 관통 · 정책 활성 · 보유 5종목 신규 급락 · 상한 3 → 본문 3종목 · 저장 entries 3 ticker 만. 정정을 되돌리면 실패해야 한다(무력화 실증). 저장 entries 는 러너가 `risk.save_entries` 를 읽어 쓴 상태 파일로 확인하므로, `RiskAssembly` 에 대입하는 잘못된 구현도 이 테스트에서 실패한다.
- 같은 날 다음 틱 · 같은 시세 → 앞 3종목은 억제, 잘린 2종목이 발송된다. 저장 5종목.
- 잘린 악화: 오늘 X 를 D5_7 로 저장해 둔다. 신규 3 + X 가 D10_PLUS 인 틱 → X 잘림 · 저장 worst 는 D5_7 유지. 다음 틱에 X 발송.
- 날짜가 바뀐 첫 틱(`date_reset`) → 잘린 신규는 저장되지 않는다.
- 재계산 예외 주입 → 구 본문 발송 · 위험 상태 전체 저장 · `sector_signal_state` 의 `last_sent_at` · `sent_today` 불변 · 집계 파일 불변.
- 회귀:
  - 정책 비활성 5종목 → 구 본문 5 · 저장 5.
  - 장중 조립 예외 → 구 본문 5 · 저장 5.
  - 일일 상한 회차 → 위험 상태 파일 불변.
  - Telegram 실패 · 부분 전송 → 저장 없음.
  - 사업군 D1 기존 테스트 · `merge_worst` 단위 테스트 그대로 통과.
- 본문 byte 동일: 정정 전에 먼저 작성해 통과시킨 단언이 정정 뒤에도 통과해야 한다.

**운영 조치**

- pull 은 거래일 15:40 뒤부터 다음 거래일 07:15 전까지 한다. 장중에 pull 하면 그날 구 코드가 저장한 억제분이 섞이고, 다음 거래일에는 `date_reset` 으로 깨끗이 시작하기 때문이다.
- 상태 파일은 수동으로 편집하지 않는다.

### C5 — Telegram 실패 집계 · 운영 집계 · 증거 정정 · 잠재

**사실**

- 장중 회차 결과(`tick_outcome`)는 Telegram 전송 전, 조립 시점에 잠정으로 정해진다(`holdings_risk_flow.py:347-353`).
  - 사업군 조회 실패 → failed.
  - 억제됐고 보낼 본문이 없음 → suppressed.
  - 나머지 → no_signal. 보낼 본문이 있는 회차도 여기서 시작한다.
- sent 로 고치는 곳은 전송 성공 경로 한 곳뿐이다(`runner_evidence.py:181-189`, 사업군 상태 저장 뒤).
- 러너의 처리된 종료(`_finish`)가 모두 지나는 `apply_intraday_records`(`holdings_risk_flow.py:396-440`)는 최종 status 를 인자로 받지만, 회차 결과를 정하는 데 쓰지 않는다. 그래서 다음 두 경우는 잠정값으로 집계된다. 대개 '신호 없음'이고, 같은 틱에 사업군 조회 실패가 겹치면 '조회 실패'다.
  - `telegram_send_error`. 실제 `telegram_send` 는 부분 전송도 `sent=False` 로 돌려준다.
  - 조립 뒤 발송 전에 끝나는 다른 failed 출구 3곳: `forbidden_wording` · `raw_identifier_exposed` · `registry_corrupted`.
- `_finish` 를 거치지 않는 예외 종료(발송 뒤 `mark_sent` · 상태 저장 예외 등)는 집계 틱 자체가 남지 않는다. 이번 범위 밖이고, POC5-01 최외곽 종료 확정이 맡는다.
- 15:40 요약 줄은 '장중 점검 N회 · 알림 N건 · 중복 억제 N건 · 신호 없음 N건' 이다. failed 가 있을 때만 '· 조회 실패 N회' 가 붙는다(`intraday_alert_render.py:243-267`). 설계 §8 에서 '조회 실패'는 조회 · 평가 실패를 뜻한다.
- 집계 파일은 `intraday_checkup_tally.v1` 이다. 일 단위로 리셋되고 `OUTCOME_FAILED` 가 이미 있다. DB 에는 집계 칸이 없고, JSONL `intraday_tally_outcome` 에만 남는다.
- **OCI 실측**: `telegram_send_error` 는 전 기간 4건이고 모두 `holdings_briefing`(07-15~07-18)이다. `holdings_risk_alert` 의 전송 실패는 0건이다. 과거 집계가 틀린 적은 없다.

**검토한 선택지**

- **A.** `OUTCOME_FAILED` 를 재사용한다. '조회 실패 N회'에 합쳐지므로 뜻이 넓어진다.
- **B.** 새 값 `send_failed` 와 '발송 실패 N회' 토큰을 둔다.
  - 실패가 있던 날만 토큰이 붙는다.
  - 조회 실패와 같은 틱에 겹치면 발송 실패를 우선한다.
  - 스키마는 v1 을 유지한다.
- **C.** 러너 실패 분기를 고친다. 러너가 646줄이고, 출구 한 곳만 막게 되므로 권장하지 않는다.
- **부가.** 성공 확정도 `apply` 에서 한다(status=sent 이고 부분 전송이 아니면 sent). 사업군 상태 저장 예외 때문에 실제 발송 회차가 no_signal 로 남던 edge 만 바뀐다.

**확정**(Q11~Q13): B + 조립 뒤 failed 출구 4곳 전부 + 성공 경로도 최종 status 기준.

- 파일: `holdings_risk_flow.py`(apply) · `intraday_checkup_tally.py` · `intraday_alert_render.py`(`send_failed=0` 기본 → 기존 줄 byte 동일).
- 사용자 문구 '발송 실패 N회' 는 설계자가 확정했다(Q11).

**바뀌는 것**

- 실패가 있던 날만 15:40 보유 브리핑 말미 줄에 '· 발송 실패 N회' 가 붙는다.
- 그 회차는 잠정값(신호 없음 또는 조회 실패)에서 빠진다. 조회 실패와 겹친 틱이면 '조회 실패 N회' 가 줄고, 0이 되면 그 토큰이 사라진다.
- JSONL `intraday_tally_outcome` 에 `send_failed` 값이 생긴다.
- 실패가 없는 날의 줄은 byte 동일하다.

**테스트**

- `sent=False` 전송기 → failed/`telegram_send_error` · 집계 `send_failed` 1 · no_signal 0.
- 실제형 부분 전송 → `send_failed`.
- 사업군 조회 실패 + 전송 실패가 같은 틱 → 틱 1개 · `send_failed`. 조회 실패가 그 틱뿐이면 '조회 실패' 토큰이 없고 '발송 실패 1회' 만 붙는다.
- 금지 문구 · raw 식별자 · `registry_corrupted` 대역 → 각각 `send_failed`.
- 회귀: 성공은 sent · 상한 · 신호 없음 skip 은 기존 잠정값 · 사업군 조회 실패만 있으면 failed · dry-run · flag-off · duplicate 에서 집계 · 관측 파일 hash 불변.
- 렌더: `send_failed=0` 이면 기존 문자열 byte 동일, 1이면 '· 발송 실패 1회'.
- 구 v1 집계 파일을 읽은 결과가 같아야 한다.
- 15:40 관통.

### C6 — `message_text_length=0` · 운영 집계 · 증거 정정 · 실제 발생

**사실**

- `holdings_risk_alert` 는 legacy evidence 단계를 건너뛴다(`SKIP_EVIDENCE_KINDS`). 그래서 길이를 채우는 공용 지점(`runner_evidence.py:112`)을 타지 않는다.
- 새 흐름도 길이를 채우지 않아, 러너 초기값 0(`run_three_push_runtime_oci.py:160`)이 그대로 남는다.
- 다른 kind 는 조립 단계에서 채운다. 예: `holdings_selection_flow.py:238` `out.diagnostics["message_text_length"] = len(out.message_text)`.
- **OCI 실측**: `holdings_risk_alert` JSONL 98행의 값은 {0} 뿐이다. 0이 결함인 행은 발송 14행(정책 전 6 · 뒤 8)이다. 신규 · 악화 없음 58 · 일일 상한 5 · 비거래일 14 행은 아래 정의로도 0이 맞다. push_kind_disabled 7행은 본문 유무를 확인하지 않았다. PC DB 의심 12행도 0이며 보존 대상이다.

**검토한 선택지**

- **A.** `assemble_holdings_risk_push` 끝에서 같은 패턴으로 기록한다.
- **B.** 러너에 1줄을 넣는다(647줄 · 권장하지 않음).
- **C.** 모든 kind 공통으로 기록한다. 다른 kind 기록의 의미가 바뀌므로 권장하지 않는다.

**확정**: A. 값의 뜻은 다음과 같다.

- **조립된 최종 본문**(통합 본문 또는 구 본문)의 분할 전 길이다. 다른 kind(`holdings_selection_flow.py:238`)와 뜻이 같다.
- 실제 발송 여부는 status · `telegram_sent` 로 판정한다. 길이 > 0 이 발송을 뜻하지는 않는다.
  - 러너가 조립 직후 이 값을 record 에 병합하므로(`run_three_push_runtime_oci.py:363`), 조립 뒤 발송 없이 끝나는 행에도 조립 길이가 남는다. 해당 행: dry-run · autosend_disabled · push_kind_disabled · duplicate_runtime · forbidden_wording · raw_identifier_exposed · registry_corrupted · telegram_send_error.
  - 0이 되는 것은 두 경우다. 본문이 빈 회차(신규 · 악화 없음이면서 장중 본문 없음 · 일일 상한)와 조립 전에 끝나는 회차(비거래일 · 시세 불완전 · 조립 오류)다.
- 과거 0은 고치지 않는다(본문 미저장 · backfill 금지).
- POC5 원장 문서에 '배포일 이전 `holdings_risk_alert` 의 0 = 미기록 · 길이 > 0 ≠ 발송' 을 적는다.

**테스트**

- 구 본문 · 통합 본문 발송 → 보낸 본문 길이와 같다.
- 4,000자 초과(분할 발송) → 분할 전 전체 길이.
- 본문이 빈 회차(신규 · 악화 없음 · 일일 상한) · 비거래일 · 조립 오류 → 0.
- duplicate_runtime · autosend_disabled · `telegram_send_error` → 조립 길이(0 아님).
- tmp DB 행과 JSONL 값이 같다.

### C7 — KOSPI 09-17 정지 · 원인 조사 후 판정 · 실제 발생

**조사 결과**

코드 변경 · 외부 호출 · source 교체 · 날짜 밀어 넣기는 모두 0이다.

- **경로.** 07:20 배치 → `refresh_kospi_benchmark` → FDR `KS11` 순서로 간다. FDR `KS11` 은 거래소가 아니라 제3자 GitHub 캐시 CSV 를 연도별로 읽는다. 위치는 `FinanceData/fdr_krx_data_cache` 의 **master 브랜치 고정**(`refs/heads/master` · FDR `krx/data.py:269`) `data/index/year_ks11/{연도}.csv` 다. 연도별 조회 예외는 삼켜서 빈 결과로 바꾼다(`krx/data.py:260-284`).
- **OCI 배치 로그 'benchmark 갱신'**:
  - 09-17: `kospi=ok(as_of=2026-09-16)`.
  - 09-18: `ok(as_of=2026-09-17)`.
  - 09-21 · 22 · 23 · 24 · 25: 모두 `kospi=ok(as_of=2026-09-17)`.
  - 같은 줄의 vix 는 09-18 에서 09-24 까지 전진했다. 즉 **09-18 자료부터** 들어오지 않았다.
- **H2(OCI 조회 실패)는 배제한다.**
  - 조회 실패라면 빈 결과가 `failed/no_data` 로 기록되는데, 로그는 ok 다.
  - KOSPI 09-15~09-17 행의 `created_at` 은 `2026-09-24T22:20:10Z`(09-25 07:20 KST 배치)다. upsert 는 충돌 시 `created_at` 도 갱신한다(`app/market_benchmark_store.py:75-84`).
  - 따라서 09-25 조회는 09-17 로 끝나는, 비어 있지 않은 결과를 돌려준 것이다.
- **H3(OCI FDR 버전 · 매핑 차이)도 배제한다.**
  - OCI `finance-datareader` 는 0.9.202 로 PC 와 같다.
  - PC 09-22 수동 갱신도 같은 09-17 에서 멈췄다(`market_refresh_log` success=1). 같은 실행에서 KODEX200(`069500`, 네이버 경로)은 09-21 까지 받았다.
- **결론**: 우리 쪽에서 확인되는 원인은 upstream 캐시(master)가 09-18 이후 행을 내주지 않는 것(H1)이다. **아직 모르는 것은 upstream 이 일시 지연인지 영구 중단인지** 다. 외부 사이트를 봐야 알 수 있다.
- **원인 확정(R2 · 2026-09-27)**: 설계자가 GitHub 현재 파일을 직접 확인했다. `2026.csv` 마지막 행은 **2026-09-17**, 이 파일의 최신 커밋은 **2026-09-17 12:22 KST** 다. 저장소 전체의 9월 26일 커밋과 별개로 KS11 의 `2026.csv` 만 멈춰 있다.
  - `REPOSITORY_DEAD = false` · `KS11_FILE_CURRENT = false` · `KS11_LAST_ROW = 2026-09-17` · `C7_CAUSE_FINAL = upstream KS11 2026.csv stopped` · `SOURCE_SWITCH = PROHIBITED`.
- **사용자 확인(Q16 · 2026-09-26)**: `UPSTREAM_MASTER_LAST_COMMIT = 2026-09-26 04:46`(브라우저).
  - 저장소 전체가 살아 있다는 증거일 뿐, `2026.csv` 가 갱신됐다는 증거는 아니다.
  - 현재 판정: `REPOSITORY_DEAD = false` · `KS11_FILE_CURRENT = UNCONFIRMED` · `SOURCE_SWITCH = PROHIBITED` · `STALE_DETECTION_FIX = APPROVED`.
  - 위 R2 원인 확정으로 해소됐다.
- **구조 결함**(원인과 별개로 코드로 확인됨 · 실제 발생):
  - `refresh_kospi_benchmark` 는 비어 있지 않은 반환이면 마지막 날짜와 상관없이 `status: ok` 다(`:219`).
  - 신선도 계약(`MAX_STALE_TRADING_DAYS=1`)은 계산 · 표시 계층(`compute_kospi_metrics`)에만 있다.
  - 배치 상태의 `kospi_as_of` 를 읽는 화면 · 알림이 없다. 배치 상태 파일을 읽는 코드는 폐지 spike 가드 하나이고, 그 가드는 `status` · `refresh_date_kst` · `price_data_as_of` 만 본다(`app/three_push_runtime/spike_freshness.py:57-80`).
  - 그래서 09-25 배치는 status success · `benchmark_status` ok · `kospi_as_of` 09-17 로 남았다. OPS-02B-1 계약 '벤치마크 실패를 전체 성공으로 숨기지 않는다'와 어긋난다.
- **영향**:
  - 현행 운영 PUSH 3종 본문에는 KOSPI 가 없다. 08:00 은 S&P500 과 KRX 기초지수만 쓰고, 세 kind 모두 `SKIP_EVIDENCE_KINDS` 다. 따라서 메시지 계약에는 영향이 없다(정적 코드 기준).
  - PC 화면(코드 기준 · 실화면 미확인):
    - 「오늘의 투자 점검」 KOSPI 머리: '수익률·위치 자료 없음'. stale 을 구분하지 않는다.
    - 「요즘 잘 오르는 ETF」 시장 배경 카드: 'N/A — KOSPI 시계열이 수집되지 않았습니다.'. 사실과 다른 사유다.
- **자동 복구**: upstream 이 재개되면 다음 07:20 배치의 180일 lookback upsert 가 09-18 이후를 채운다. 날짜를 밀어 넣을 필요가 없다.
- 참고: OCI `etf_daily_price` 의 `069500` 최신일은 09-23 이다.

**감지 정정 A**(Q17 확정 · 원인과 무관하게 구현)

- **위치**: store 함수 `refresh_kospi_benchmark`. OCI 배치와 PC 수동 갱신(`/market/refresh`) 두 적재 경로에 한꺼번에 적용된다.
- **축**: `end_date` 미만 거래일로 만든다. KRX 거래일 스냅샷을 쓰고, 없으면 평일 fallback 이다. 08:00 기초지수 최신성 관문과 같은 축이다. KODEX200 DB 축은 DB 가 같이 멈추면 lag 가 0이 되는 순환 결함이 있어 쓰지 않는다.
  - 축 계산은 **공용 거래일-lag helper 로 추출**한다(Q17). store 가 flow 의 private helper 를 import 하는 방식은 금지다.
    - `flow.py` 의 `_weekday_axis_before` · `_window_lag_trading_days`(`:118-164`) 본체를 새 공용 모듈(예정 `app/trading_day_lag.py`)로 옮긴다. store 와 `flow.py` 가 함께 쓴다.
    - `flow.py` 는 같은 이름을 모듈 안에 남긴다. `scripts/ops02b2/reverse_verify_guards.py:110-113` 의 monkeypatch 와 기존 테스트가 그대로 동작하게 하기 위해서다.
    - 시장 브리핑 동작이 옮기기 전과 같은지 테스트로 고정한다.
    - 순환 import 가 없는 위치인지 구현 때 확인한다. 리팩토링이므로 Dockerfile · 배포 스크립트 영향도 확인한다(개발 규칙 §2.3).
  - 이 helper 는 기준일 당일을 축에서 뺀다(`flow.py:155` · `:130`). 그래서 **반환 마지막 날짜가 축의 마지막 날 이상이면(PC 수동 갱신에서 `end_date=date.today()` 당일 행이 온 경우 포함) lag 0 으로 먼저 처리한다.** 그러지 않으면 정상 자료가 stale 로 오판된다(`market_refresh_service.py:466`).
  - 'lag 계산 불가 → stale' 은 최신일이 축보다 오래됐거나, 축 안에 없는 과거 날짜이거나, 파싱이 안 되는 경우로 한정한다.
- **임계**: 기존 `MAX_STALE_TRADING_DAYS=1` 을 그대로 쓴다. 새 임계는 만들지 않는다.
- **넘으면**(Q17 확정):
  - status `failed` + error `source_stale:as_of=…,ref=…,lag=N`. 배치 계층 `refresh_kospi` 가 ok 가 아닌 값을 이미 `failed` 로 바꾸므로(`app/market_benchmark_batch.py:78-79`) 배치 계층 변경은 0이다.
  - 적재한 행은 되돌리지 않는다.
- **바뀌는 것**:
  - OCI 07:20 배치: 로그가 `kospi=failed(as_of=…)` 로 남는다. `source_stale:` error 는 배치 실행 결과의 `benchmark_refresh.kospi.error` 에 남는다. 배치 status 는 success 에서 `success_with_benchmark_failure`(reason `benchmark_partial:kospi`)로, exit code 는 0에서 1로 바뀐다.
  - crontab 07:20 줄은 `cd … && venv/bin/python scripts/run_oci_market_data_batch.py >> logs/oci_market_data_batch.log 2>&1` 이다(실측). 뒤에 이어지는 명령이 없으므로 exit 1 이 다른 작업을 막지 않는다.
  - 수동 `spike_or_falling_alert` 실행은 KOSPI 지연일에 spike 가드(`status != "success"`)에서 `batch_not_success:success_with_benchmark_failure` 로 fail-closed 된다. OCI cron 에 spike 줄이 없어 운영 PUSH 영향은 없다. 기존 benchmark 실패 때와 같은 동작이다.
  - PC 수동 갱신에서는 `market_refresh_log` KS11 행 success 가 1에서 0이 되고 `error_summary` 가 남는다. 전체 갱신은 실패로 처리되지 않는다.
  - ETF 가격 적재 · artifact · 08:00 · 보유 · 장중 PUSH 는 바뀌지 않는다.
- **알려진 한계**: 캘린더가 실행 연도를 덮지 않으면 평일 fallback 축을 쓰는데, 이 축은 공휴일을 모른다(`flow.py:118-131`).
  - 그래서 평일 휴장일 다음 배치에서는 정상 자료도 lag 2 로 stale 이 된다(kospi failed · 배치 `success_with_benchmark_failure` · exit 1 · PC 수동 갱신 KS11 success 0).
  - 저장소 캘린더는 2026 파일 하나이고 마지막 행은 2026-12-30 이다. 2027 파일이 없으면 2027-01-04 07:20 부터 이렇게 된다(축 끝 12-31 · 01-01 · KOSPI 최신 12-30).
  - 08:00 기초지수 최신성 관문도 같은 성질이다. 2027 캘린더를 넣으면 해소된다. POC5-00 확정 Q17 대로 2027 파일은 선행조건이 아니므로 알려진 한계로 기록한다.
- **테스트**(tmp DB · stub fetcher · 외부 호출 0):
  - lag 2 이상 → `failed` + `source_stale:`. 행은 유지되고, `as_of` 는 유효 종가(> 0)가 있는 마지막 날짜다(Q26).
  - 마지막 행 종가가 NaN · 0 · 음수 → 그 날짜는 신선한 자료로 치지 않는다. 유효 종가 행이 없으면 `failed` · `source_stale:as_of=unknown`(Q26).
  - lag 0 · 1 → ok(회귀).
  - 반환 마지막 날짜 == `end_date`(거래일) → ok · lag 0.
  - 빈 반환 → 지금처럼 `failed/no_data`.
  - 배치 run 관통 → `success_with_benchmark_failure` · `benchmark_failed=['kospi']` · artifact 저장됨.
  - PC 수동 갱신 → `market_refresh_log` 에 실패 기록 · 전체 refresh 는 실패가 아님.
  - 08:00 · 보유 · 장중 러너 본문 byte 테스트를 다시 돌린다.
  - 공용 helper 추출 전후로 시장 브리핑 판정이 같아야 한다. 기존 flow · 최신성 테스트, 같은 입력의 lag 비교, `reverse_verify_guards` 스크립트로 확인한다.

**복구 · 화면**

- **복구**:
  - Q18 확정: upstream 이 재개되면 그대로 쓴다(코드 0 · 180일 lookback 으로 자동 채움).
  - 계속 멈추면 source 교체를 별도 설계로 판단한다. 그 전까지 `SOURCE_SWITCH = PROHIBITED` 다.
- **화면 B**(Q19 확정): KOSPI stale 화면 문구(위 두 문구)는 이번 단계에서 뺀다. 후속 `POC3-02D-OPS-02` 후보로 기록한다.
- **POC5-02**: '한국 시장 원시 결과'에 쓸 계열은 POC5-02 PLAN 에서 이 정지 사실을 반영해 정한다.

---

## 4. 테스트 배치

- C3 · C4 · C5 · C6 은 새 테스트 파일 1개 `tests/test_poc3_02d_ops01_holdings_risk_flow.py` 에 둔다. 기존 rig 를 재사용한다.
  - 기존 `tests/test_intraday_alert_flow_through.py` 는 1,298줄이라 KS-10 테스트 근접선(1,450)에 가깝다.
  - 새 파일은 설계자가 승인했다(Q22).
- C1 · C2 · C7 은 기존 테스트 파일에 추가한다.
- 모든 테스트는 tmp 경로 · tmp DB · stub 을 쓴다. `_live_guard` 를 지키고, 외부 호출 · 실발송은 0이다.

---

## 5. 사용자 확인이 필요한 것

1. **C3 — 원문 수신**(2026-09-27): 사용자 입력 그대로 `현재가 ㅡ. 직전 종가 2026-09-22`. 현재가 자리에 시각 없이 줄표만 있어 R2 조건('실제로 `현재가 —` 이면 수정')이 충족됐다.
2. **C7 — 해소**(R2 · 설계자 확인: 마지막 행 2026-09-17).
3. **C1 — 원본 수신 · 확인 완료**(2026-09-27). 사용자가 KRX 에서 직접 다운로드한 파일이다(사용자 확인). 설계자는 원본 내용을 대조했다(RESULT 판정).
4. **(선택) C2**: PC 백엔드를 켠 뒤 「진단 · 상태 > OCI 운영 상태」의 '상태:' 값. 거짓 경보가 실제로 뜨는지 확정하는 수정 전 증거다.
5. **§6-2 Q23~Q27 — 확정**(R2).
6. **커밋 · push · OCI**: 검증자 `VERIFIED` 뒤 커밋(완료 · 2026-09-27). push 는 별도 승인(STEP 6).

---

## 6. 설계자 확정과 추가 확인

### 6-1. 확정 (설계자 PLAN 판정 2026-09-26 · 원문은 전용 설계서 §3)

| Q | 정정 | 확정 |
|---|---|---|
| Q1 | C1 | (c) 채택 + 최신 유효 CSV 자동 선택. d20 없는 `api_only` 는 pending 기록 · 차단 안 함. 고정 주기가 아니라 `refresh_due` 발생 시 갱신 요청 |
| Q2 | C1 | 07:20 · 08:00 이 하나의 CSV resolver 공유 |
| Q3 | C1 | 장중 설정 · 02B-1 재현은 `20260909` 고정 · 운영 resolver 와 섞지 않음 |
| Q4 | C1 | `07:15~08:05 pull 금지` 운영 규칙만 · 코드 시간 가드 없음 |
| Q5 | C1 | 기존 최신성 임계 유지 · 결과 관찰 |
| Q6 | C4 | 상세 ticker JSONL 추가 없음(POC5-01) |
| Q7 | C4 | 보유 급락 정렬 유지 |
| Q8 | C4 | 인접 결함 2개 tmp 재현 · 결과서 보고 · 이번에 고치지 않음 |
| Q9 | C3 | (a) 실행 시각 · 사용자 원문이 정말 `현재가 —` 일 때만 수정 |
| Q10 | C3 | 범위 밖 기록 |
| Q11 | C5 | (b) `send_failed` + 사용자 문구 `발송 실패 N회` |
| Q12 | C5 | 조립 뒤 failed 출구 4개 모두 |
| Q13 | C5 | 성공 경로도 최종 status 기준 |
| Q14 | C2 | 운영 3종 목록 교체만 · 주석 필터 · 틱 수 검사 제외 |
| Q15 | C2 | `PROGRAM_TRUTH` 갱신 + 옛 crontab 문서 SUPERSEDED |
| Q16 | C7 | 사용자 브라우저 증거 · master 커밋 시각과 CSV 마지막 행을 따로 기록 |
| Q17 | C7 | C7-A 채택 · `failed + source_stale:` · 공용 거래일-lag helper 추출(flow private helper import 금지) · 시장 브리핑 동작 동일 테스트 |
| Q18 | C7 | upstream 재개 시 그대로 사용 · 계속 멈추면 source 교체를 별도 설계로 판단 |
| Q19 | C7 | KOSPI stale 화면 문구 제외 · 후속 `POC3-02D-OPS-02` 후보 |
| Q20 | 공통 | C1~C7 모두 PRIMARY 전 반영 · C7 은 감지 정정까지 · source 복구는 선행조건 아님 |
| Q21 | 공통 | 한 단계 · 한 결과서 · 한 pull · C1 분리 가능하나 PRIMARY 는 C1 까지 기다림 |
| Q22 | 공통 | 새 테스트 파일 생성 승인 |

### 6-2. 추가 확인 → 설계자 확정 (최종 판정 R2 2026-09-27 · 원문은 전용 설계서 끝)

| Q | 정정 | 확정(R2) |
|---|---|---|
| Q23 | C1 | (a) N=5 — 가장 오래된 pending 의 `max(0, 21 - stored_trading_day_count) <= 5` 이거나 이미 `CSV_REFRESH_REQUIRED` 면 `refresh_due=true` |
| Q24 | C1 | (b) 08:00 본문 끝 조건부 1줄 `※ 운영 안내: KRX ETF 전종목 기본정보 CSV를 갱신해 주세요.` · false→true 주기마다 한 번 · 발송 없는 날은 다음 실제 발송까지 보류 · JSON · 배치 로그에 매회 기록 · 브리핑을 막지 않음 |
| Q25 | C1 | (a) 최신 파일 실패 시 직전 최신 유효 파일 사용 · 거부 파일 · SHA · 사유 기록 · 동일 날짜 묶음 무효 · 유효 파일 0개일 때만 `CSV_REFRESH_REQUIRED` + resolver error |
| Q26 | C7 | (b) `as_of` = `Close > 0` 인 행 중 마지막 날짜 · 유효 행 없으면 `failed` · `source_stale:as_of=unknown` |
| Q27 | C1 | (b) — 개발자 제안 (a) 불승인. `evaluated_api_basis_date` · `evaluated_window_d20_date` · `evaluated_at_kst` 기록 · 08:00 현재 창과 비교 · 누락 · 불일치면 기초지수 구역만 fail-closed · `META_GATE_STALE` · `CSV_REFRESH_REQUIRED` 로 표시하지 않음 · 나머지 브리핑 정상 |

질문 원문(제출판 · 기록용):

| Q | 정정 | 질문 | 개발자 제안 |
|---|---|---|---|
| Q23 | C1 | `refresh_due` 발생 조건: (a) pending 중 첫 적재가 가장 이른 ticker 가 d20 종가를 얻기까지 남은 KRX 거래일이 N 이하이거나, 이미 `CSV_REFRESH_REQUIRED` 일 때(N 은 새 상수) (b) pending 이 1건이라도 생기면 즉시 | (a) N=5. 약 1주 여유를 두고, 거의 매주 오는 요청을 피한다 |
| Q24 | C1 | `refresh_due` 를 사용자에게 알리는 경로: (a) 정합성 JSON · 배치 로그 기록만(사용자는 개발자 OCI 읽기로 앎) (b) 08:00 시장 브리핑 본문 끝에 발생일만 조건부 1줄(문구 설계자 지정) (c) PC 화면 | (b). 판정 문구 '사용자에게 갱신 요청'을 운영 경로로 채울 수 있는 방법이다. 문구 지정을 요청한다. 08:00 이 skip 인 날은 다음 발송일에 전달된다 |
| Q25 | C1 | resolver 가 가장 늦은 파일을 검사에서 떨어뜨렸을 때: (a) 검사를 통과한 가장 늦은 이전 파일을 고르고, 떨어진 파일 · 사유를 정합성 JSON · 로그에 남긴다 (b) 고르지 않고 fail-closed(`CSV_REFRESH_REQUIRED` + resolver error). 동일 날짜 중복도 같은 규칙 | (a). 판정 문구 '가장 늦고 검증을 통과한 파일'을 그대로 따르고, 기초지수 구역을 불필요하게 끄지 않는다 |
| Q26 | C7 | 감지 정정 A 의 `as_of` 정의. 확정 PLAN 은 '반환의 마지막 날짜'다. 그런데 upstream 이 새 날짜에 종가 없는 행(NaN · 0 이하)을 주면, `as_of` 가 그 날짜가 되어 lag 0 · `ok` 로 통과한다. 한편 화면 계층(`fetch_benchmark_history`)은 유효 종가 행만 보므로 여전히 멈춘 날짜를 본다. 구현 뒤 독립 검토에서 tmp 재현으로 확인했다(NaN · 0.0 · -1.0 모두 `ok`). (a) 확정 PLAN 그대로('반환의 마지막 날짜') (b) '유효 종가(>0)가 있는 마지막 날짜'로 바꾸고, 유효 행이 없으면 `source_stale:as_of=unknown` | (b). 판정 취지('stale 을 `ok` 로 보고한 구조 결함')를 우회 없이 지킨다. 확정 문구를 바꾸는 것이라 판정을 받은 뒤 구현한다 |
| Q27 | C1 | 08:00 은 07:20 판정 JSON 을 읽기만 하고, 그 판정이 **오늘 창**으로 만든 것인지 확인하지 않는다. pending gate 뒤로는 판정이 창(d20)에 따라 달라진다. 그래서 07:20 이 적재 뒤 · 저장 전에 실패하면(예: CSV 디코드 오류 · 파일 쓰기 오류) 전날의 `ok` 판정이 남는다. 그 사이 d20 을 얻어 차단돼야 할 날에도 기초지수 구역이 나갈 수 있다(구현 뒤 검토 · 장애 조건에서만 · tmp 재현). (a) 이번 범위 밖 · 알려진 한계로 기록 (b) 판정 JSON 에 판정에 쓴 d20 을 기록하고, 08:00 에서 `resolve_window` 와 다르면 fail-closed('08:00 은 결과만 읽는다' 설계와 부딪힘) | (a). 07:20 실패 자체가 드물고 배치 로그에 남는다. (b) 는 08:00 설계를 바꾸는 것이라 별도 판정이 필요하다 |

---

## 7. 금지 범위 대조

| 항목 | 이 PLAN |
|---|---|
| PLAN 판정 전 코드 · CSV · OCI 상태 변경 | 0. 판정 뒤 문서 동기화만 했다: 전용 설계서 신규 · 이 PLAN 확정 갱신 · POC5-00 설계서 · PLAN 보완 판정 기록(모두 미커밋) |
| KOSPI source 교체 · 날짜 밀어 넣기 · 외부 GET | 0 — `SOURCE_SWITCH = PROHIBITED`(Q18) |
| PC 의심 기록 12행 | 보존 |
| 과거 JSONL · DB 값 수정 · backfill | 0 |
| 운영 결과 · 과거 수익률 · 적중률 열람 | 0. OCI 읽기는 날짜 · 상태 · 건수 · ticker 식별자만. 02B-1 재현은 `manifest` 섹션만 |
| 러너 646줄 · `runtime_state.sqlite` 스키마 | 변경 0 |
| 신규 의존성 · 외부 API 추가 · 파일 삭제 | 0(`20260909` CSV 유지) |
| 새 파일 | 판정 근거가 있는 것만: 전용 설계서 · 테스트 파일 1개(Q22) · resolver 모듈 · 검증 스크립트(C1 필수 보완) · 공용 lag helper 모듈(Q17) |
| 테스트의 라이브 state · DB 쓰기 · 실발송 | 0 — tmp 경로 · tmp DB · stub · `_live_guard` |
| 현행 PUSH 문구 · 시간 · 임계 · 상한 변경 | 설계자가 확정한 정정만 — C1 복구(pending gate 포함) · C3 '기준' 줄 · C4 억제 · C5 실패일 토큰(`발송 실패 N회`) · C1 `refresh_due` 안내 1줄(Q24 확정 문구) |

---

## 8. KS-10 (2026-09-26 `wc -l` 실측)

| 파일 | 줄 | 정정 | 비고 |
|---|---|---|---|
| `app/runtime_evidence/holdings_risk_flow.py` | 440 | C3 · C4 · C5 · C6 | 약 +30줄 예상 · 백엔드 근접 600 · 트리거 650 과 거리 있음 |
| `app/runtime_evidence/intraday_checkup_tally.py` | 178 | C5(B) | |
| `app/runtime_evidence/intraday_alert_render.py` | 281 | C5(B) | |
| `app/three_push_runtime/runner_market_briefing.py` | 156 | C1 | 파일명 상수 대신 resolver 호출 |
| `scripts/run_oci_market_data_batch.py` | 328 | C1 | 파일명 상수 대신 resolver 호출 |
| `app/market_briefing/meta_gate.py` | 229 | C1 | pending gate · 기록 필드 |
| `app/market_briefing/krx_sync.py` | 308 | C1 | d20 종가 · 첫 적재일 전달 |
| `app/market_briefing/krx_store.py` | 232 | C1 | 필요 시 첫 적재일 조회 |
| `app/market_briefing/official_csv.py` | 신규 | C1 | resolver |
| `scripts/check_krx_etf_basic_csv.py` | 신규 | C1 | 검증 스크립트(PC 전용) |
| `app/oci_startup_status.py` | 276 | C2 | |
| `app/market_benchmark_store.py` | 219 | C7(A) | |
| `app/market_benchmark_batch.py` | 272 | — | 변경 0(Q17 상태값 `failed`) |
| `app/trading_day_lag.py` | 신규(예정 이름) | C7(A) | 공용 거래일-lag helper |
| `app/market_briefing/flow.py` | 359 | C7(A) | helper 본체를 공용 모듈로 옮기고 같은 이름 유지 · 줄 수 감소 예상 |
| `scripts/run_three_push_runtime_oci.py` | 646 | — | **변경 0** |
| `tests/test_intraday_alert_flow_through.py` | 1,298 | — | 추가하지 않음(새 파일 Q22) |
| `tests/test_poc3_02d_ops01_holdings_risk_flow.py` | 신규 | C3 · C4 · C5 · C6 | Q22 승인 |
| `tests/test_oci_startup_status.py` | 103 | C2 | |
| `tests/test_market_briefing_contracts.py` | 928 | C1 | |
| `tests/test_market_benchmark_freshness.py` | 460 | C7 | |

---

## 9. 문서 갱신 범위(STEP 5 · STEP 7)

- `docs/PROGRAM_TRUTH.md`:
  - 08:00 공식 CSV: resolver 선택 규칙 · pending gate · `refresh_due` · 데이터 파일만 추가하는 갱신 절차.
  - 「장중 급등락」 절: 잘린 보유 급락은 다음 틱에 재판정 · '기준' 줄 계약.
  - 15:40 요약 줄 토큰.
  - 「OCI 운영 상태」 필수 판정 · 위치 stale.
  - KOSPI 적재 stale 기록.
  - 작업 전 §5.1 · §6.1 · §9 · §11 · §13 · §15 · 부록 전 섹션을 grep 한 뒤 일괄 반영한다.
- `docs/handoff/OCI_LOW_FREQUENCY_TELEGRAM_PUSH_OPERATION_V1_CRONTAB.md`: 머리에 SUPERSEDED 1줄(Q15).
- POC5 원장 문서(POC5-01 PLAN 때):
  - outcome 값 집합에 `send_failed` 추가.
  - '배포일 이전 `holdings_risk_alert` 의 `message_text_length=0` = 미기록 · 길이 > 0 ≠ 발송'.
- `docs/STATE_LATEST.md`: 검증자 `VERIFIED` 뒤 · 커밋 전에 갱신한다(설계자 RESULT 판정 순서 3). STEP 7 사후 실측 뒤 다시 갱신한다. 후속 `POC3-02D-OPS-02` 범위(설계자 결정: OCI 상세 링크 · Q8 인접 상태 저장 결함 · 낡은 역검증 ⑦ · 목업 ⑦ 제목 · 후보: KOSPI stale 화면 문구)를 기록한다.
