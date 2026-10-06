# POC3-02D-OPS-04 — 남은 운영 정정 PLAN V1 (확정 · 설계자 CONDITIONAL_PASS + 사용자 승인 → PASS 2026-10-04)

```text
STEP            = POC3-02D-OPS-04 REMAINING OPERATIONAL CORRECTIONS
DESIGN          = docs/ai_design/POC3/POC3-02D-OPS-04_REMAINING_OPERATIONAL_CORRECTIONS_DESIGN_V1.md (설계자 2026-10-04 원문)
보조 원문        = docs/ai_design/POC3/POC3-02D-OPS-03_OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY_DESIGN_V1.md 끝
                  '설계자 OPS-03 종료 판정 · 잔여 판단 5건' (2026-10-02 · 항목 1~5 의 처음 결정)
PREDECESSOR     = POC5-01A (검증자 VERIFIED 2026-10-04 · push · OCI pull 2026-10-04 · 첫 거래일 10-06 확인 대기)
SUCCESSOR       = POC5-01B 운영 원장
PLAN_DECISION   = PASS — 설계자 CONDITIONAL_PASS(2026-10-04 · 재제출 불요 · Q1~Q8 확정 · 원문 = 설계서 끝)
                  + 사용자 명시 승인 2건(2026-10-04: 시장 DB 표 1개 추가 · KRX `sto/stk_bydd_trd` 사용)
IMPLEMENTATION  = 로컬 구현 승인(사용자 2026-10-04 — '로컬 구현 먼저') · 커밋 · push · OCI pull 은 POC5-01A 종료(10-06 첫 거래일 확인) 뒤 · 별도 승인
이번 조사의 변경   = 코드 · 테스트 · DB · cron · OCI 변경 0 · 문서 = 설계서 원문 저장 1 + 이 PLAN 1(둘 다 신규)
                  · OCI 읽기 명령 2회(상태 파일 모양 · 읽기 도구 유무)

중단 보고 → 해소:
  항목 1 은 기존 저장 구조로 안 돼 중단 보고했다(§1-1) → 설계자 Q1 (a) 기존 `market_data.sqlite` 에 표 1개 추가 · 사용자 승인.
  항목 2 ~ 6 — 신규 DB · 신규 API · 새 메뉴 없이 된다(기존 API 응답 · 기존 상태 파일 · 기존 기동 시 SSH 읽기 재사용).

항목별 요약:
  1 개별주 가격     새 표 `krx_stock_daily_price_unadjusted`(Q1 a) · 조회 `sto/stk_bydd_trd` 경계 1개 · 보유 코스피 개별주만
  2 FDR 고지        한 곳 — `batch_failure_reasons` 의 FDR 단계 판정을 뺀다
  3 대표 ETF 행     기동 시 SSH 읽기에 블록 1개 + `jobs` 행 1개 + 프론트 라벨 · 상태 표시
  4 단절 가드       PUSH 파생값 경로 5곳 모두 이미 충족 → 코드 변경 없이 닫기 제안(Q5)
  5 09:20 재시도    미충족 → ledger 에 일시 오류(timeout · 연결 · 5xx · 429) 날짜를 남기고 09:20 만 1회 더 부른다
  6 PARAM 의미      기동 시 SSH 읽기에 블록 1개(`python3` 읽기 전용) + `jobs` 행 1개(유효값 14개 비교) + 카드 문구 '적용' → '전달'
```

- **작성**: 개발자(VSCode Claude) · **독자**: 설계자 · **작성** 2026-10-04
- **기반 문서 확인**: `PROJECT_ORIGIN_INTENT` §4(와이프가 이해할 수 있는 UI) · §10(신규 대형 DB 금지 · 시장 시세 SSOT = `state/market/market_data.sqlite`) · `KILL_SWITCHES` KS-10(백엔드 650 트리거 · 600 근접 · 프론트 900 · 850) · 한국 거래일 계약(평일 기본 · 2026-09-11 사용자 확정 · 이 PLAN 에서 다시 묻지 않음).
- **조사 방법**: 소스 읽기 · grep · 보유 파일 읽기(읽기 전용) · OCI 읽기 명령 2회. 재현 명령은 부록 A.

---

## 1. 사실조사 (항목별 현재 경로)

### 1-1. 항목 1 — 보유 개별주 일별 가격

| 사실 | 근거 |
|---|---|
| 지금 개별주 파생값(20거래일 수익률 · 고점 대비)은 **늘 닫힌다**. 이력은 FDR(`etf_daily_price`)에서 읽지만 T-1 비교 기록에만 쓴다 | `app/runtime_evidence/holdings_price_basis.py:269-274`(`REASON_MISMATCH`) · `:253` · 계약 이름 `:53` `ETF_KRX_UNADJUSTED__STOCK_FDR` |
| 현재 보유 개별주 = **3종** `005930` 삼성전자 · `000660` SK하이닉스 · `006400` 삼성SDI — 모두 **코스피** | PC `state/holdings/holdings_latest.json` 32행 읽기(2026-10-04) |
| KRX 공식 주식 일별 = `sto/stk_bydd_trd`(코스피). 요청 인자는 기준일(`basDd`) 하나라 응답은 **그날 전 종목**이다 — 종목만 골라 받을 수 없다. 코스닥은 별도(`sto/ksq_bydd_trd`) | 2026-09-29 같은 키로 1회 읽기 전용 확인(`holdings_price_basis.py:18-22` · 설계자 RESULT STEP 1-7) |
| 조회 경계: `app/market_briefing/krx_sync.py` 에 ETF(`:53`) · KOSPI(`:91`) URL 과 fetcher 가 있다. 테스트 가드 `tests/conftest.py` `_block_live_krx_api` 가 이 모듈의 경계를 막는다 | 소스 |
| **저장 구조 — 기존 것으로 안 된다**: | |
| · `krx_etf_daily_price_unadjusted` 에 넣으면 ETF 분류가 깨진다 — 이 표에 행이 있으면 ETF 로 분류한다(`holdings_price_basis.py` `classify_assets` · `CLASS_KRX_TABLE`). 적재 검사 행 수(`krx_store.row_count_on` · `baseline_row_count`) · 대표 선정(`intraday_config/selector.py:179-184`)도 이 표 전체를 ETF 로 본다. OPS-03 종료 판정 1-1 도 'ETF 무조정 테이블과 섞지 않고 별도 공식 주식 가격 저장소' | `app/market_briefing/krx_store.py:45-63` |
| · `etf_daily_price` 에 넣으면 PK `(ticker, date)` 가 FDR 행과 겹친다 — 한 종목에 두 계열이 섞이고 다음 FDR 갱신이 덮는다 | `app/market_data_store.py:38-51` |
| · 저장 없이 실행마다 조회하면 PUSH 1회에 21거래일 이상 호출 — 불가 | `krx_store.REQUIRED_TRADING_DAYS = 21` |
| 따라서 **새 저장 위치(표 또는 파일)가 필요** → 설계서 §5 · 사용자 지시에 따라 **중단 보고**(Q1) | |

### 1-2. 항목 2 — FDR 실패 고지

| 사실 | 근거 |
|---|---|
| 08:30 시장 브리핑의 배치 실패 고지 사유 = 배치 상태 없음 · 오늘 기록 아님 · **`stage_status.fdr_price != "ok"`** | `app/three_push_runtime/runner_market_briefing.py:104-120` |
| 고지 문구 '※ 운영 안내: 오늘 아침 보유 종목 시세 갱신이 끝나지 않아 고점 대비 값이 빠질 수 있습니다.' · 본문 끝 1줄 · 낼 내용 없으면 고지만 · 하루 1회는 브리핑 registry | `app/market_briefing/render.py:72-82` · `flow.py:375-431` |
| PUSH 가 FDR(`etf_daily_price`)을 쓰는 곳은 **개별주 이력 하나**뿐이고, 그것도 지금은 파생값을 늘 닫는다(1-1). 같은 판단이 코드 주석에 이미 있다('FDR 단계만 실패한 날의 보유 영향은 사실상 없다 … 발동 입력에서 FDR 을 뺄지는 설계자 결정 대상') | `runner_dispatch.py:67 · 91` → `load_basis_history` · `render.py:75-78` |
| 내부 기록은 그대로 남는다 — 배치 상태 JSON `stage_status.fdr_price` · 배치 로그 | OCI `state/market/oci_market_data_batch_state.json`(2026-10-02 `fdr_price: ok`) |

### 1-3. 항목 3 — 장중 대표 ETF 화면 행

| 사실 | 근거 |
|---|---|
| 「OCI 운영·적용」 ① 표 = PC 백엔드 **기동 시 SSH 읽기 1회**(`refresh_snapshot`) 결과. 기존 API `GET /oci/startup-status` 가 캐시를 돌려준다 · 재조회 없음(POC3-07 설계자 Q2) | `app/oci_startup_status.py:144-271` · `app/api_oci_startup_status.py:39-40` |
| 원격 명령은 `###` 로 나눈 블록 4개(crontab · stat · 달력 폴더). 행은 `jobs` 목록(`OciJobStatus{job, status, detail}`) — 행을 더해도 응답 모델은 그대로다 | `oci_startup_status.py:169-180 · 246-249` |
| 프론트는 `JOB_LABEL` 로 이름을 붙이고, 모르는 job 은 원문을 그대로 보인다 | `frontend/app/components/OciStatusView.tsx:31-40 · 196-200` |
| 대표 커버리지 기록은 **이미 OCI 상태 파일 두 곳**에 있다 — 08:10 `oci_market_data_batch_state.json` · 09:20 `oci_krx_reinforcement_state.json` 의 `krx_representatives = {source, status, expected_previous_trading_day, count, missing[], representatives_refresh_due}` | OCI 읽기(2026-10-04): 두 파일 모두 `status=ok · 기준일 2026-10-01 · count 27 · missing []` |
| `status` 값: `ok` · `intraday_config_unavailable`(활성 설정 못 읽음) · `representative_missing` · `not_evaluated`(표 읽기 오류) | `app/intraday_config/representatives.py:23-26` · `krx_target_checks.py:240-275` |

### 1-4. 항목 4 — ETF 가격 단절(누락 거래일) 가드

PUSH 가 ETF 가격으로 만드는 파생값 경로를 전부 찾았다. **다섯 곳 모두 이미 설계서 §3 규칙을 지킨다.**

| 경로 | 수익률(시작 · 끝 날짜 정확 일치) | 구간 값(구간 완전할 때만) |
|---|---|---|
| 보유 브리핑 20거래일 · 고점 대비 | `close_on` — 그 날짜 종가만 · 더 오래된 값으로 대체 안 함(`holdings_selection.py:183-196`) | `_drawdown_pct_over_window` — 하루라도 없으면 `None`(`:225-253`) |
| 장중 보유 위험 고점 대비 | (등락률은 Naver · 파생 아님) | `_drawdown_pct` 같은 규칙(`holdings_risk.py:196-213`) |
| 장중 사업군 5 · 20일 추세 | `trend_returns` — 날짜로 고름 · 없으면 `None`(`sector_signal.py:288-308`) | `TrendBasis.missing_days` 있으면 `usable=False`(`:157-180`) |
| 08:30 기초지수 5 · 20일 | `CalendarWindow.missing_required` 있으면 `usable=False`(`krx_store.py:431-458` · `flow.py:221`) | — |
| ETF 가격 계열 | KRX 무조정 한 계열 · 조정계열 fallback 없음(`holdings_price_basis.py` docstring · `:262-268`) — AC 2 | |

- 행 순서로 날짜를 고르는 옛 `resolve_window`(`krx_store.py:318-331`)가 하나 남아 있다. 쓰는 곳은 08:10 정합성 판정 기록(`krx_sync.py:324` · d20 종가 없는 ticker 기록)뿐이고 사용자에게 보이는 파생값이 아니다.
- 연도 파일이 없는 해의 평일 기본 운영(저장 자료 없는 평일 = 휴장)은 사용자 확정 계약이라 이 Step 에서 바꾸지 않는다. 2026 은 연도 파일이 있다.
- 관련 테스트 파일이 경로마다 있다(부록 A-3). 구현 단계에서 경로별 '누락일' 시나리오 고정 여부를 확인하고, 빠진 경로만 focused test 를 더한다.
- OPS-03 종료 판정 1-4 는 '분할 · 병합 · 비정상 단절 탐지'(KRX 기업행위 확인 · 공식 등락률 대조 조사)였다. OPS-04 설계서 §3 은 '누락 거래일 완전성'으로 정했다 → Q5.

### 1-5. 항목 5 — 09:20 누락일 재시도

| 사실 | 근거 |
|---|---|
| 창(21거래일) 안 빠진 날 채우기는 ledger `krx_backfill_ledger.json`(`{date_kst, calls:{날짜: n}}`)으로 **같은 날짜를 KST 하루 1회만** 부른다 — 08:10 첫 채우기 · 같은 실행 `backfill_retry` · 09:20 `--krx-only` · 수동 재실행을 **모두 합쳐서** | `app/market_briefing/krx_backfill.py:1-20 · 144-152` |
| 부르기 **전에** 기록한다. 그래서 08:10 에 일시 오류(timeout · 5xx)로 실패한 날짜도 '오늘 부름'으로 남아 **09:20 이 다시 부르지 않는다** → 설계서의 '09:20 1회 재시도' **미충족** | `krx_backfill.py:144-165` |
| 결과 코드: `ok` · `not_published` · `fetch_error`(예외 — timeout · 연결 · HTTP 오류, HTTP 코드 함께 기록) · `basis_date_mismatch` · `invalid_snapshot` · `row_drop` · `readback_mismatch` · `store_error` | `krx_target_checks.py:35-42 · 155-172` |
| 09:20 은 `run_krx_only()`(`max_attempts=1`) · 자기 상태 파일로 **하루 1회 실행** 가드가 이미 있다(오늘 이미 돌았으면 건너뜀) | `scripts/run_oci_market_data_batch.py:433-470` |
| 목표일(T-1) 시각표 시도(08:10 · 08:15 · 08:20 · 08:24 · 09:20)는 ledger 밖이다 — 이번 항목은 **창 안 누락일**만 | `krx_backfill.py:12-13` |

### 1-6. 항목 6 — PARAM '적용' 의미

| 사실 | 근거 |
|---|---|
| 화면 '현재 운영 기준 적용' = `POST /three-push/param/apply` → PC DB 활성 + PC JSON → OCI 에 JSON scp · mv → **JSON 만** 검사. OCI DB 를 건드리지 않는다 | `app/api_three_push_param.py:226-261 · 306-` · `scripts/sync_three_push_runtime_param.py:153-178` |
| OCI 러너는 DB 활성 포인터만 읽는다 · JSON fallback 없음 | `app/runtime_param_store.py:369-389` |
| 카드 표시: 배지 '적용 완료'(`status=applied` = sync + JSON 검증 성공) · 행 'OCI 반영' | `frontend/app/components/ThreePushParamCard.tsx:30-43 · 156` · `api_three_push_param.py:153-160` |
| 카드 표시 계약: **`param_id` 를 화면에 보이지 않는다**(지시문 §5.2) | `ThreePushParamCard.tsx:12-14` |
| OCI 에는 `sqlite3` 명령이 없고 `python3`(3.12.3)만 있다 → DB 활성 포인터를 읽으려면 표준 라이브러리 `sqlite3`(읽기 전용 URI) `python3 -c` 가 필요하다. 지금 기동 시 읽기는 셸 명령(crontab · stat · ls)뿐이다 | OCI 읽기(2026-10-04) |
| 2026-10-04 실측: OCI DB 활성 `param-20260907T152806-255383` · OCI JSON `param-20261004T020942-999570` · 값 14키 차이 0 | `docs/backlog/BACKLOG.md` §11(2026-10-04 등재) |

### 1-7. KS-10 — 손댈 후보 파일 줄 수(2026-10-04 실측)

`oci_startup_status.py` 343 · `api_oci_startup_status.py` 54 · `krx_backfill.py` 184 · `krx_target_sync.py` 494 · `krx_target_checks.py` 293 · `krx_sync.py` 501 · `krx_store.py` 538 · `holdings_price_basis.py` 311 · `runner_market_briefing.py` 247 · `render.py` 246 · `market_data_batch.py` 507 · `api_three_push_param.py` 359 · `OciStatusView.tsx` 221 · `ThreePushParamCard.tsx` 206 · `threePushParam.ts` 50. 모두 근접(600 · 850) 아래다. `krx_store.py`(538)에는 새 책임을 넣지 않는다.

---

## 2. 최소 변경안

### 2-1. 항목 1 — 공식 주식 일별 가격 표 (Q1 a 확정 · 사용자 승인 2026-10-04)

0. 저장: 기존 `state/market/market_data.sqlite` 에 표 1개 `krx_stock_daily_price_unadjusted`(ETF 무조정 표와 같은 6열 `date · ticker · close · source · price_basis · collected_at` · PK `(date, ticker)`). 새 모듈 1개가 맡는다(`krx_store.py` 538줄에 넣지 않는다). ETF 표와 join · 혼합 0. 새 DB 파일 0.
1. 조회: `krx_sync.py` 에 `sto/stk_bydd_trd` URL · fetcher 1개(ETF · KOSPI 와 같은 모양 · 같은 키 · 같은 테스트 가드). 응답에서 **보유 개별주 행만** 저장한다(전 종목 적재 0).
2. 시점: 기존 08:10 KRX 단계의 곁 작업(KOSPI 재시도와 같은 자리 · 마감 08:27 공유) + 09:20 보강(항목 5 규칙). 새 cron 0.
3. 범위: 보유 개별주 × 목표일로 끝나는 창(21거래일 + 앞 여유 10 · `FETCH_EXTRA_TRADING_DAYS`). 처음 한 번은 창을 채우고(날짜당 1호출 · 최대 약 31호출 · 하루 1회 ledger 규칙) 그 뒤는 날마다 T-1 1호출.
4. 사용: `holdings_price_basis` 의 개별주 분기를 KRX 공식 종가로 바꾼다. 없는 날은 그 파생값만 닫는다(항목 4 규칙 그대로). 계약 이름 · evidence(`price_source` · `price_basis` · 기준일)를 바꾼다. 현재가는 Naver 그대로.
5. 범위 = 현재 보유 코스피 개별주(오늘 3종). 코스닥 지원 · 전체 종목 적재 · 전체 과거 백필은 하지 않는다 — 보유에 코스닥 종목이 생기면 그 종목 파생값만 `확인 불가`.

### 2-2. 항목 2 — FDR 단계 판정 제거

- `batch_failure_reasons`(`runner_market_briefing.py:104-120`)에서 `stage_status.fdr_price` 판정을 뺀다. 상태 파일 없음 · 오늘 기록 아님(배치가 안 돈 날 — KRX 도 없음) 고지는 남긴다(Q2).
- 옛 상태 파일 분기(`status == "failed"`)는 `stage_status` 가 없는 옛 기록용이다 — 그대로 둔다.
- `render.py:75-78` 주석의 '설계자 결정 대상' 문장을 결정 결과로 바꾼다.
- 배치 상태 JSON · 로그의 FDR 기록은 그대로(내부 기록 유지).

### 2-3. 항목 3 — 「OCI 운영·적용」 ① 표 '장중 대표 ETF' 행

- `refresh_snapshot` 원격 명령에 블록 1개: 두 상태 파일의 `krx_representatives` · 기록 날짜(`refresh_date_kst` · `date_kst`)만 꺼낸다(원문 payload 를 들고 오지 않는다). 읽기 전용.
- 같은 KST 날짜면 09:20 기록, 없으면 08:10 기록을 쓴다(Q3 a). 오늘 기록이 아니어도 그대로 보이고 기준일을 함께 보인다(Q3 a).
- `jobs` 행 1개(`intraday_representatives`): 상태 · 기준일 · `확인 수/필요 수`(= `count − len(missing)` / `count`).

```text
정상        기준일 2026-10-01 · 27/27
확인 필요   기준일 2026-10-01 · 26/27 · 누락 1종
확인 불가   활성 설정을 읽지 못함            (intraday_config_unavailable · not_evaluated · 파일 없음 · 파싱 실패)
```

- **미확인은 0 이나 정상으로 보이지 않는다** — 읽지 못하면 `0/27` 이 아니라 `확인 불가`.
- 프론트: `JOB_LABEL` 에 '장중 대표 ETF' · 상태 라벨 매핑. 새 메뉴 · 새 API 0(기존 `GET /oci/startup-status` 의 `jobs` 행).

### 2-4. 항목 4 — 코드 변경 없이 닫기 (Q5)

- 1-4 표의 다섯 경로가 이미 '정확한 날짜 · 완전 구간 · 당겨 쓰지 않음'을 지킨다.
- 구현 단계: 경로별 누락일 시나리오 테스트가 있는지 확인한다. **기존 테스트가 있으면 새 테스트를 기계적으로 더하지 않는다** — 없는 경로만 더한다(운영 코드 변경 0 · Q5 a).
- 분할 · 병합 탐지 조사는 하지 않는다(Q5 a).

### 2-5. 항목 5 — ledger 에 결과 종류를 남기고 09:20 에 1회 허용

- ledger 에 날짜별 첫 결과 종류를 더한다(`{date_kst, calls, retryable: [날짜…]}` · 상태 JSON 필드 추가 · DB 아님).
- **일시 오류**(Q6 b 확정: `fetch_error` 중 timeout · 연결 오류 · HTTP 5xx · HTTP 429)로 끝난 날짜만 `retryable` 에 넣는다.
- 09:20 `--krx-only` 경로만 `retryable` 날짜를 **한 번 더** 부른다(`calls` 1 → 2). 08:10 같은 실행의 `backfill_retry` · 수동 재실행은 지금처럼 건너뛴다.
- 영구 실패(`invalid_snapshot` · `basis_date_mismatch` · `row_drop` · `readback_mismatch` · 429 밖의 HTTP 4xx 등)는 같은 날 다시 부르지 않는다.
- 날짜별 하루 최대 = 최초 1회 + 보강 1회. 정상 행 재처리 0 · 다른 자료원 0 · 새 cron 0.
- 항목 1 의 개별주 누락일도 같은 규칙을 쓴다.

### 2-6. 항목 6 — '전달'과 '활성'을 나눠 보이기

- `refresh_snapshot` 원격 명령에 블록 1개: `python3 -c`(표준 라이브러리 · `sqlite3` 읽기 전용 URI `mode=ro` · Q8 a)로 OCI DB `runtime_param_active` 가 가리키는 버전의 **유효값 행**(`runtime_param_value` · 오늘 14개)을 읽는다. 쓰기 · job 실행 0.
- 비교 기준 = **러너가 실제로 쓰는 유효값 14개**(Q7 b). 버전 ID 가 달라도 값이 같으면 일치다. PC 쪽은 PC JSON 을 PARAM 버전을 만들 때 쓰는 같은 펼침 규칙(`app/runtime_param_store.py:50` `flatten_param_dict`)으로 펼쳐 같은 키 · 같은 값 표현으로 맞춘다.
- 비교는 **GET 때** 한다 — 캐시한 OCI 유효값과 **지금** PC JSON 을 비교한다. 같은 세션에서 값을 바꿔 적용하면 바로 '다름'이 된다(적용은 OCI 활성을 바꾸지 않는다).
- ① 표 행 1개(`param_active` · '운영 기준 활성'):

```text
일치        활성값과 일치 (14/14)
다름        활성값과 다름 — OCI 는 이전 값으로 동작합니다 (전달만 됨)
확인 불가   OCI 활성값을 읽지 못함
```

- ② 카드 문구: 배지 '적용 완료' → '전달 완료', 행 'OCI 반영' → 'OCI 전달'. 활성 여부는 ① 행을 보게 한 줄 안내. `param_id` 는 계속 보이지 않는다.
- 문구는 구현 전 목업 1회로 확정한다(위 표는 초안). 자동 활성화 · 원격 쓰기 경로 0.

---

## 3. 변경 파일 목록 (예상)

| 항목 | 운영 코드 | 테스트 |
|---|---|---|
| 1 | 새 모듈 1개(공식 주식 일별 표 · 예: `app/market_briefing/krx_stock_store.py`) · `app/market_briefing/krx_sync.py`(fetcher) · 08:10 KRX 단계 · 09:20 보강 연결(`krx_target_sync.py` 또는 `scripts/run_oci_market_data_batch.py`) · `app/runtime_evidence/holdings_price_basis.py`(개별주 분기) | `tests/conftest.py` 라이브 KRX 가드에 새 경계 · 새 focused test · `tests/test_poc3_02d_ops03_price_basis.py` 개별주 사례 정정 |
| 2 | `app/three_push_runtime/runner_market_briefing.py` · `app/market_briefing/render.py`(주석) | `tests/test_poc3_02d_ops03_briefing.py` 고지 사례 정정 |
| 3 · 6 | `app/oci_startup_status.py`(약 +80 → 약 425줄) · `app/api_oci_startup_status.py`(GET 때 비교 · 필요 시) · `frontend/app/components/OciStatusView.tsx` · `frontend/app/components/ThreePushParamCard.tsx` | `tests/test_oci_startup_status.py` · `OciStatusView.test.tsx` · `ThreePushParamCard.test.tsx` |
| 4 | 0 | 빠진 경로만 focused test |
| 5 | `app/market_briefing/krx_backfill.py` · `app/market_briefing/krx_target_sync.py`(09:20 표시 전달) | `tests/test_poc3_02d_ops03_krx_batch.py` · 새 focused test |
| 문서 | `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md` · `docs/backlog/BACKLOG.md`(§11 PARAM 항목 처리) · 결과서 | |

신규 DB 파일 0 · 신규 API 0 · 새 메뉴 0 · cron 0 · 의존성 0. DB 스키마 = 기존 `market_data.sqlite` 에 표 1개 추가뿐(사용자 승인 2026-10-04) · `runtime_state.sqlite` 스키마 0.

---

## 4. 검증 계획 (줄인 방식)

1. 항목별 focused test → 마지막에 백엔드 전체 회귀 1회(라이브 가드 · 라이브 파일 hash 전후 비교).
2. 프론트: `npx tsc --noEmit` · `npm run lint` · `npx vitest run`. 최종 build 는 **저장소 밖 사본에서 1회**만 확인한다(저장소 `frontend/.next` 불변).
3. 화면(항목 3 · 6): 구현 전 목업 **1회**로 문구를 확정한다(별도 설계 라운드 아님). 구현 뒤 사용자 실화면 확인(AC 10).
4. 파괴 시험 검토 1회(예: FDR 단계 판정 되살리기 · 09:20 이 영구 실패 날짜를 다시 부르기 · 미확인을 0/27 로 표시).
5. 배포 뒤 OCI 읽기 전용 확인 + 첫 거래일 08:10 · 08:30 · 09:20 기록 확인.

---

## 5. 배포 · 롤백

- 커밋 · push 는 사용자 승인. OCI pull 은 사용자(거래일 08:05 ~ 15:45 제외). cron · `.env` 변경 0(항목 1 도 기존 KRX 키).
- PC 백엔드 재기동이 있어야 ① 표의 새 행이 보인다(기동 시 1회 읽기).
- 롤백 = 커밋 revert + OCI pull. 항목 5 ledger 새 필드는 옛 코드가 무시한다(`calls` 만 읽음).

---

## 6. 설계자 확정 (2026-10-04 · 원문 = 설계서 끝 `# 설계자 PLAN 판정`)

| 질문 | 확정 |
|---|---|
| Q1 개별주 저장 | **(a)** 기존 `market_data.sqlite` 에 공식 주식 일별 가격 표 1개(`krx_stock_daily_price_unadjusted` 성격 · 별도 표). JSON 파일은 쓰지 않는다(시계열 SSOT 가 갈라짐) |
| Q2 FDR 고지 | **(a)** FDR 실패 조건만 제거 · 배치 자체가 안 돈 날의 고지는 유지 |
| Q3 대표 ETF 기록 | **(a)/(a)** 같은 날이면 09:20 우선 · 없으면 08:10 · 지난 기록도 기준일과 함께 표시 |
| Q4 SSH 읽기 | **(a)** 기존 기동 시 읽기에 블록 2개 추가 허용 |
| Q5 단절 가드 | **(a)/(a)** 운영 코드는 이미 충족 · 빠진 테스트만 보완 · 분할 · 병합 조사 안 함 |
| Q6 일시 오류 | **(b)** timeout · 연결 오류 · HTTP 5xx · 429 만 09:20 재시도 |
| Q7 PARAM 비교 | **(b)** 실제 유효값 14개 비교 · ID 가 달라도 값이 같으면 `활성값과 일치` |
| Q8 DB 읽기 | **(a)** 읽기 전용 `python3 -c` 허용 |

필수 반영 7건 → 위치: Q1 별도 표(§2-1 0) · 보유 코스피 개별주만(§2-1 5) · 코스닥 · 전 종목 · 전체 백필 없음(§2-1 5) · Q7 유효값 비교(§2-6) · 항목 4 기계적 테스트 추가 금지(§2-4) · build 는 저장소 밖 사본 1회(§4-2) · 목업 1회(§4-3).

---

## 7. 사용자 확인 항목

1. **외부 API 추가** KRX `sto/stk_bydd_trd`(기존 KRX 키) — **사용자 승인 2026-10-04**.
2. **DB 표 추가** 기존 `market_data.sqlite` 에 공식 주식 일별 가격 표 1개 — **사용자 승인 2026-10-04**.
3. **화면 문구**(항목 3 · 6 · 카드 '적용 완료' → '전달 완료'): 구현 전 목업 1회 확인(남음).
4. **발송 내용 변화**(항목 1 이 들어가면): 개별주 3종의 20거래일 하락 판정 · 고점 대비가 다시 계산된다. 보유 브리핑 선정 · 장중 위험 알림의 고점 대비 줄이 늘 수 있다.

---

## 7-1. 작업 순서 (PLAN PASS 뒤)

1. 로컬 구현은 지금 시작(사용자 결정 2026-10-04). 커밋 · 배포는 POC5-01A 종료(10-06 첫 거래일) 뒤.
2. 항목 2 · 5 · 4(백엔드만) → 항목 1(표 · 조회 · 가격 기준) → 항목 3 · 6(목업 1회 → 구현 → 실화면).
3. 전체 회귀 1회 → 결과서 → 설계자 RESULT 판정 → 검증자.

---

## 부록 A. 재현 명령 (저장소 루트 · 읽기 전용)

```text
A-1 항목별 경로
  grep -n "def batch_failure_reasons" -A17 app/three_push_runtime/runner_market_briefing.py
  sed -n 101,165p app/market_briefing/krx_backfill.py
  sed -n 144,271p app/oci_startup_status.py
  sed -n 240,290p app/runtime_evidence/holdings_price_basis.py
  sed -n 35,42p app/market_briefing/krx_target_checks.py
A-2 OCI(읽기 전용)
  ssh oci-krx 'cd /home/ubuntu/krx_hyungsoo && python3 -c "import json;print(json.load(open(\"state/market/oci_market_data_batch_state.json\"))[\"krx_representatives\"])"'
  ssh oci-krx 'which sqlite3 python3'
A-3 항목 4 관련 테스트 파일
  grep -rl "_drawdown_pct_over_window\|drawdown_20d_pct" tests   → test_holdings_selection.py · test_poc3_02d_ops03_price_basis.py
  grep -rl "drawdown_pct" tests                                   → 4파일
  grep -rl "trend_returns\|missing_days" tests                    → 4파일
  grep -rl "missing_required\|resolve_calendar_window" tests      → 4파일
A-4 줄 수
  wc -l app/oci_startup_status.py app/market_briefing/krx_store.py app/market_briefing/krx_backfill.py …
```
