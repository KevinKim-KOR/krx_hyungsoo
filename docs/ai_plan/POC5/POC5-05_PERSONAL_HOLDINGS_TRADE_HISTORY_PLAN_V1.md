# POC5-05 — 보유·매매 이력 통합 개발 PLAN V1 (설계 개정 2 반영)

```text
STEP_ID        = POC5-05
DESIGN         = docs/ai_design/POC5/POC5-05_PERSONAL_HOLDINGS_TRADE_HISTORY_DESIGN_V1.md (개정 2 · 설계자 2026-10-08)
BASE_COMMIT    = eb5d1ead (POC5-04 종료 커밋)
STATUS         = PLAN 확정 — 설계자 PASS_TO_IMPLEMENT(2026-10-08 · 설계 개정 2 §11 · 재제출 불필요 · 판정 반영 = 본문 정정 + §9)
조사            = 설계서 §10 6항목 — 코드 읽기 5갈래(읽기 전용) + 개발자 직접 재확인 · PC DB 읽기 전용 실측(2026-10-08)
설계자 질문      = 5건 → 판정 완료(§7 · 추천안 기준 확정 · 보완 §9)
사용자 확인      = 통합 보유 화면 목업 확인 완료(2026-10-08 · §8)
```

## 0. 요약

설계대로 만들 수 있다. PC `state/holdings/holdings_latest.json` 을 한 문서(현재 보유 + 개인 이력)로 확장하고, 모든 PC 보유 쓰기를 한 저장 경계로 모은다. 매매 한 번 저장으로 이력 기록 → 보유 기간 재계산(이동평균) → 현재 보유 갱신이 한 파일 교체로 끝난다. OCI 적용은 허용 5필드 payload 를 만들어 보내고 hash 도 그 payload 로 계산한다.

실제 코드와 맞지 않아 설계자 판단을 받은 곳은 5곳이고, 모두 추천안 기준으로 확정됐다(§7 · 보완은 §9).
- **Q-A**: 빈 보유를 OCI 보유 PUSH 가 오류로 처리한다. 4개 층에 걸쳐 있어 OCI 코드 변경 · OCI pull 이 필요하다.
- **Q-B**: 시장 흐름 가격 계열이 설계 전제와 다르다. PC 개별주 자료가 없거나 멈춰 있고, KRX 무조정 표는 UI 사용이 금지돼 있다.
- **Q-C**: '현재 수익률' 을 어느 화면에 보일지 모호하다. 「종목 관리」 에는 평가 표를 노출하지 않는다는 기존 계약이 있다.
- **Q-D**: `app/api.py` 가 646줄로 KS-10 백엔드 임계 650 에 걸린다. `GET/PUT /holdings` 를 바꾸려면 두 경로를 다른 모듈로 옮겨야 한다.
- **Q-E**: 입력 정정(ADJUSTMENT)의 계산 순서 · 의미를 정해 달라. 설계가 위치를 정하지 않았다.

신규 의존성 0. 미커밋 개정 1 backend 는 검증 · ID · 재시도 비교만 재사용하고, SQLite 개인 표 저장은 걷어낸다. 라이브 PC DB 에는 개인 표가 생성된 적이 없다(실측 · 보존할 행 0).

## 1. 사실조사 (설계서 §10)

### 1-1. PC 보유 읽기 · 쓰기 경로 (§10-1)

- **writer 는 하나**: `PUT /holdings`(`app/api.py:260-288`) → `holdings.save()`(`app/holdings.py:226-233`). 다른 PC writer 는 `app/` · `scripts/` 에 없다.
- **`save()` 가 새 정보를 버린다**: `{"holdings": [asdict(Holding)]}` 만 `write_text` 로 직접 덮어쓴다. 임시 파일 · `os.replace` · 잠금이 없다. 최상위 메타와 행 추가 필드(`position_id` 등)는 모두 사라진다. 설계 §5 '구판 writer' 위험이 실제로 있다.
- **`load()`(`:236-254`)의 판정**:
  - 최상위 dict 만 읽는다.
  - 파일 없음 → `[]` · 손상 → `JSONDecodeError` · 키 누락 → `HoldingsValidationError`
  - **빈 배열 → `HoldingsValidationError`**(`validate_holdings :207-210`). 정상 빈 보유를 지금은 어떤 경로로도 읽을 수 없다.
  - 행 추가 키 · 최상위 다른 키는 무시한다.
- **GET/PUT /holdings 모델**(`app/api.py:225-236`): `HoldingItem` 5필드 · `HoldingsPayload{holdings}`. pydantic 기본 동작으로 `revision` · `position_id` 를 조용히 버린다. 프론트 `RowDraft`(`HoldingsManageView.tsx:40-49`)도 5필드만 왕복한다.
- **중복 차단 키**: (종목, 계좌, 평단) 삼중조합(`holdings.py:215-220`). 실측 현재 보유는 32줄 · 종목 29종 · (종목, 계좌) 중복 0.
- **추가 필드에서 깨지는 PC 소비자 1곳**: `three_push_package_exporter.py:81 Holding(**h)` → `position_id` 에서 `TypeError`(PC 예비 경로 `scripts/sync_three_push_packages.py`).
- **추가 필드를 견디는 소비자**: `ledger_copy/views.py:76-82` 와 `scripts/build_holdings_selection_preview.py`.
- **PC 실행 방식**: `start.sh:29` · `start.bat:18` = `uvicorn --reload` · workers 미지정 → 단일 프로세스. 쓰기 엔드포인트는 sync def 라 같은 프로세스 threadpool 에서 동시에 돈다 → **프로세스 내 `threading.Lock` + revision 으로 직렬화가 성립**한다.
  - 같은 방식 선례: `market_cache._atomic_write` = 같은 디렉터리 mkstemp → `os.replace`.
  - 프로세스 간 파일 잠금 선례는 없다.
- **파일 mtime 을 '보유 기준 시각' 으로 표시하는 곳**: `holdings_market_evidence.get_holdings_file_mtime_iso` — "표기용 · 매매 결정에는 사용하지 않는다". 이력만 바뀌어도 시각이 바뀐다 → 표시 의미('파일 갱신 시각')가 맞으므로 유지한다.

### 1-2. 저장 직렬화 · revision · 재시도 (§10-2)

- 선례는 위 `threading.Lock` + 원자 교체다. 저장 경계는 §2-3 에 정한다.

### 1-3. OCI 적용 · OCI 소비 경로 (§10-3)

**적용(전부 PC 코드 · OCI 배포 불필요)**
- 현재 흐름: `holdings_oci_apply.py:223-224` = PC 파일 바이트를 그대로 `read_bytes` → sha256 → 같은 파일을 `scp`(`:266`) → 원격 sha 대조 → 원격 검사 `len(holdings)>0`(`:289-294`) → `mv` → 다시 읽어 sha 확인.
- **지금 저장 형식만 바뀌면 '적용' 한 번에 개인 이력 전체가 OCI 로 간다**: 로컬 검증이 확장 문서를 통과시키고, OCI loader 는 다른 키를 조용히 무시한다(메모리 내 실측). → 저장 형식 변경과 payload 생성은 **같은 커밋**이어야 한다.
- `asdict(Holding)` = 정확히 허용 5필드다. 기존 `save()` 와 같은 직렬화(indent 2 · `ensure_ascii=False`)면 같은 내용의 기존 파일과 바이트가 같다. 이력만 바뀌면 payload hash 가 같다(실측).
- 상태 파일은 매 시도마다 덮어쓴다(`:199-202`). 마지막 성공 hash 가 남지 않는다.
  - `GET /holdings/apply/status` 응답에 hash 가 없다.
  - **'미적용' 판정은 backend · 프론트 어디에도 없다**.
- PC 경로가 `_LOCAL_HOLDINGS` 로 따로 하드코딩돼 있다(`:54` · conftest 격리 밖).
- 수동 publication CLI(`scripts/run_holdings_publication.py` · prepare 는 PC · verify/activate 는 OCI)도 파일 바이트 전체를 hash 한다. 사용자가 SCP 하면 이력 포함 파일이 OCI 로 갈 수 있다.

**OCI 소비(cron 2개 · 모두 `holdings.load()` 경유)**
- 08:10 · 09:20 배치, 보유 브리핑 3슬롯, 위험 알림 7틱. 원문을 직접 읽는 OCI 경로는 없다.
- **빈 보유를 오류로 만드는 층이 4개다**.
  1. 공용 `load()` 가 빈 배열을 거절한다.
  2. `target_tickers.py:107-109` 가 빈 보유에 `RuntimeError('holdings source is empty')` 를 낸다.
  3. 보유 브리핑 · 위험 알림 완전성 가드(`holdings_selection_flow.py:431-440` · `holdings_risk_flow.py:201,299`)가 대상 0 을 `quote_incomplete` → failed 로 처리한다.
  4. PC 적용의 로컬 · 원격 빈 목록 거절.
- 지금 빈 목록이 적용되면 이렇게 된다.
  - 배치: 승인 대상 수집 실패 → FDR 증분 · universe 산출물이 빠진다.
  - 보유 브리핑 · 위험 알림: 매 실행 failed. 사업군 대표 장중 알림도 같이 멈춘다.
- `load()` 만 고치면 개별주 KRX 보강은 `no_holdings` 가 되고, `price_outcome` 은 보유 0 으로 정상 판정한다. 배치는 seed 로 계속 돈다.
- 개인값 금지 규칙(`privacy_detector` · 원장 item)과 충돌 없음: payload 가 같은 5필드이고, 원장에는 보유 여부 0/1 만 있다.

### 1-4. 미커밋 개정 1 backend 재사용 · 개인 표 실데이터 (§10-4)

- **재사용**:
  - `_decimal`(유한 · 양수 · 자릿수 초과 거절 · 반올림 금지)
  - `build_trade` 의 날짜 · 시각 · 계좌 · 종목 검증
  - `valid_record_id`(UUID)
  - 같은 ID 재시도 비교(종류 · 대상 · 정규화 내용)
  - 하위 router `GET/PUT /holdings/trade-history` 진입점
- **걷어냄**:
  - SQLite DDL · 연결 · `BEGIN IMMEDIATE`
  - 수량만 담은 BASELINE
  - 선택 금액(→ 필수 체결단가 + 계산 금액)
  - `conftest` 의 `DEFAULT_DB_PATH` 격리 줄
- **라이브 PC DB `state/decision/decision_evidence.sqlite`**(`mode=ro` 실측): 표 9개 중 `personal_holdings_history` 없음 → 보존 · 이관할 행 0. 원장 동기화와도 무관하다.
- 개정 1 테스트 37개 중 보유 불변 · 분리 DB 를 고정한 것(빈 배열 → UNREADABLE · 보유 sha 불변 · apply import 금지)은 새 계약으로 바꾼다. 입력 검증 테스트는 재사용한다. 37개 통과를 개정 2 검증으로 쓰지 않는다.

### 1-5. PC 가격 자료 — 시장 흐름 보기 (§10-5 · `state/market/market_data.sqlite` `mode=ro` 실측)

| 표 | 실측 |
|---|---|
| `etf_daily_price` | 2014-04-09 ~ 2026-10-02 · 1,190종목. 출처가 날짜 구간으로 섞인다(`NAVER_FDR` 2014-04-09 ~ 2026-03-05 · `FinanceDataReader` 2026-02-19 ~ 2026-10-02). 코드 주석상 조정 계열 |
| 보유 29종 | ETF 26종 = 10-02 까지 있음 · **개별주 3종(000660 · 005930 · 006400) = FDR 행이 2026-03-30 ~ 08-12 에서 멈춤**(PC `/market/refresh` 는 ETF 목록만 수집). 코드 주석: FDR 개별주 일봉은 KRX 정규장 종가가 아니다(+0.9 ~ 1.4%) |
| `market_benchmark_daily_price` KOSPI | `NAVER_FDR` 2014-04-10 ~ 2025-12-18 · `FinanceDataReader/KS11` 2025-12-19 ~ 2026-09-16 · `KRX_OPEN_API` 2026-09-17 ~ 10-02 — 출처 3개가 이어진다 |
| `krx_etf_daily_price_unadjusted` | 2026-09-11 하루 1,168종목뿐(OCI 배치만 채움). 모듈 머리말이 'UI 표시 · ML 로 확장하지 않는다' 고 정함 |
| `krx_stock_daily_price_unadjusted` | PC 에 표 없음 |

- 거래일: PC 에는 `krx_trading_days_2026.csv` 하나뿐이다. 다른 해는 평일 기본(5/1 · 12/31 만 휴장). '그날 또는 다음 거래일' 은 기존 `ledger_outcome_prices.Calendar.days_from(day, 1)` 을 쓴다.
- 기존 읽기 함수 일부(`fetch_price_history` · `market_benchmark_store._connection` · `krx_store.closes_on`)는 연결할 때 `CREATE TABLE IF NOT EXISTS` 를 실행한다 → 시장 흐름은 `mode=ro` 로만 읽는 새 조회로 한다(기존 `ledger_outcome_prices.open_ro` 와 같은 방식).

### 1-6. 화면 · KS-10 (§10-6)

- 「종목 관리」(`HoldingsManageView.tsx` **797줄** · 프론트 임계 900 · 근접 850)는 지금 모든 칸을 바로 고치는 표 하나다(행 = 입력칸 5 + × 삭제). '보유 종목 저장' 이 전체를 PUT 한다.
  - 마지막 1행은 지울 수 없다(`:403-404`). 0건이면 빈 입력 행이 생긴다.
  - OCI 카드에는 마지막 적용 기록만 있다.
  - 수익률은 없다(「보유 현황」 이 `/holdings/enriched` 로 표시). 파일 머리 주석이 '평가 표 노출 금지(POC3-05 §4.3)' 를 정한다.
- 모달 · Dialog 기존 패턴 0건(펼침형 · 행 선택만). 오류 표시 `handleApiError` 는 객체 detail 을 `[object Object]` 로 보인다 → 새 API 의 detail 은 문자열로 고정한다.
- 이 화면 vitest 3파일(behavior 3건 · commas · sort). behavior 3건은 × 삭제 · 빈 행 · 전체 저장 계약에 묶여 있어 다시 쓴다. commas · sort 는 순수 함수 import 경로만 유지한다.

## 2. 구현 계획 (판정 뒤)

### 2-1. 문서 형식 v2 (`holdings_latest.json`)

```text
{
  "schema_version": 2,
  "revision": <정수 · 쓰기마다 +1>,
  "holdings": [ {ticker, quantity, avg_buy_price, name, account_group, position_id, cycle_id} ],
  "personal_trade_history": {
    "positions": [ {position_id, ticker, account_group, name} ],
    "records":   [ {record_id, request_id?, recorded_at, kind, position_id, cycle_id, supersedes_id?, payload} ]
  }
}
```

- **정본 = `records`**. `holdings` 는 records 를 재계산한 호환용 결과다. 저장 때마다 재계산값과 일치를 검증한다. 수량 · 평단 숫자는 Decimal 결과의 호환 표현(float)이다. 기존 float 정밀도 손실을 복원했다고 하지 않는다.
- 계산값(원가 · 실현손익 · 수익률)은 저장하지 않는다. 정정 뒤 낡은 값이 남지 않게 조회 · 저장 때 records 로 계산한다.

| kind | payload(입력 사실만 · 십진 문자열) | 비고 |
|---|---|---|
| `BASELINE` | `quantity` · `avg_buy_price`(읽은 값 · 자릿수 제한 없음) | **첫 v2 쓰기 때 기존 줄마다 1건**(같은 문서 교체 안에서). 원가 = 수량 × 입력 평단 · 매수일 = 미상 |
| `REGISTER` | `quantity` · `avg_buy_price` | '잔고 등록'(실제 거래를 모르는 기존 잔고) · 매수일 미상 |
| `BUY` · `SELL` | `trade_date` · `trade_time`\|null · `seq` · `price`(소수 2) · `quantity`(소수 6) · `amount`(= 단가 × 수량 · 정확값 · 자르지 않음) · `memo`\|null(≤200자) | 새 보유의 첫 `BUY` = 최초 매수 |
| `ADJUSTMENT` | `effective_date` · `seq` · 정정 뒤 `quantity` · `avg_buy_price` · 정정 전 값(입력 당시 참고값 · 나중에 덮어쓰지 않음) · 또는 `name` 만(표시값 정정) | 입력 정정 · 매매가 아님. 수량 · 평단 정정 = 그 위치에서 Q 와 C = Q × 입력 평단을 확정. **종목명만 정정 = 표시값만 바꿈(Q · C · 평단 불변 · '원가 기준 변경' 표시 없음 · 호환 float 평단을 다시 곱하지 않음)**. **수량 0 = '입력 정정으로 종료'** — SELL · 손익 0원 거래로 기록하지 않음 · 그 정정의 매매대금 · 손익 · 수익률 = 대상 아님(null) · SELL 집계 제외 · 이미 발생한 매도 계산은 그대로 |
| `VOID` | 없음(대상 = `supersedes_id`) | `BUY` · `SELL` 만 대상 |
| 거래 오기 정정 | 대상과 같은 kind + `supersedes_id` | `BUY` · `SELL` 만 대상 · 이미 대체 · 취소된 행 재정정 = 409 |

- **ID**:
  - `position_id` 는 보유 줄, `cycle_id` 는 보유 기간 하나를 가리킨다. 둘 다 서버가 UUID 로 만들고 평단이 바뀌어도 그대로다.
  - 같은 (종목, 계좌)를 전량매도 뒤 다시 사면 **같은 `position_id` · 새 `cycle_id`** 다. 이렇게 History 가 이전 기간을 함께 보여 준다.
  - 계좌가 다르면 다른 position 이다. 계좌별로 자동 합산하지 않는다.
- **v1 파일(현행) 읽기**: revision 0 으로 본다. 줄 ID 는 '파일 내용 sha + 줄 순번' 에서 결정적으로 만든 임시 UUID(uuid5)다.
  - 첫 v2 쓰기 때 이 ID 를 BASELINE 의 정식 ID 로 쓴다 → 조회가 아무것도 저장하지 않아도 화면이 줄 ID 로 매매를 보낼 수 있다.
  - 그 사이 v1 파일이 바뀌면 ID 가 달라져 409(새로고침)다.
- **중복 판정**: v2 는 `position_id` 유일성으로 판정한다. (종목, 계좌, 평단) 삼중조합 검사는 ID 없는 구형 입력에만 남긴다. 그래야 줄별 계산 결과의 평단이 우연히 같아져도 거절되지 않는다.

### 2-2. 계산 — 이동평균 · 보유 기간

- 기간(cycle)별 상태는 Q(수량)와 C(남은 원가)다. 공식은 설계 §3 그대로다.
  - 추가매수: C += b × p
  - 매도분 원가 = C × s / Q · 실현손익 = s × p − 매도분 원가 · 남은 평단 유지
  - 전량매도: 남은 C 전부 배분 · Q = C = 0 · 기간 종료
- `decimal.localcontext(prec=40)`. 화면 반올림 값은 다음 계산에 쓰지 않는다.
- 매도별 실현수익률 = 실현손익 / 매도분 원가 × 100. 기간 누적 = 합 / 합 × 100 이다(개별 수익률을 평균하지 않음).
- **계산 순서**:
  - **BASELINE · REGISTER** 로 시작한 기간(매수일 미상)은 그 기준잔고를 먼저 적용한다.
  - **실제 최초 매수로 시작한 기간**은 Q = C = 0 에서 모든 유효 BUY · SELL 을 거래일 · seq 순으로 계산한다. 처음 입력한 BUY 를 날짜와 무관하게 맨 앞에 두지 않는다(설계 §11-2).
  - 거래 오기 정정은 대체한 내용의 날짜 · 순서로 다시 계산한다. VOID 된 BUY 는 계산에 남지 않는다. 최초 BUY 를 취소해 유효 매수가 없으면 현재 보유에서 빠지고 취소 이력은 남는다.
  - 이후는 (날짜, seq) 순이다. 날짜는 BUY · SELL 의 `trade_date`, ADJUSTMENT 의 `effective_date` 다.
  - 새 기록은 같은 날 맨 뒤(seq = 최대 + 1)에 들어간다. 화면에서 '같은 날 기존 기록 앞' 을 고르면 최소 − 1 이다.
  - 다른 기록의 seq 는 바꾸지 않는다. seq 를 체결 시각의 증거로 쓰지 않는다.
  - 입력 정정(Q-E)은 이 순서 안의 자기 위치(저장한 KST 날짜 맨 뒤)에서 잔고를 확정한다.
  - 기간 경계: 한 기간의 거래일은 같은 position 의 직전 기간 종료일 이후(같은 날 허용) · 다음 기간 시작일 이전(같은 날 허용)이어야 한다. 벗어나면 409(그 기간의 기록으로 입력 · 자동 이동 · 병합 없음).
- **거절(409 · 관련 기록 목록과 함께 · 저장 0)**:
  - 매도 수량 > 그 시점 잔량
  - 기간 중간에 Q 가 0 이 됐는데 뒤에 기록이 있음
  - 정정 · 취소로 닫힌 기간이 다시 열리는데 같은 position 에 더 뒤의 기간이 있음(자동 합치지 않음)
  - 전량매도 요청 수량 ≠ 서버 재계산 잔량
  - 이미 보유 중인 (종목, 계좌)에 '새 보유 최초 매수' → 그 줄의 추가매수로 안내
- 종료 기간 안의 정정은 그 기간만 다시 계산한다 → 새 기간 평단은 바뀌지 않는다.
- 설계 §3 계산 예는 그대로 테스트 고정값이다.
  - 15주 · 원가 160,000 · 평단 10,666.666…
  - 6주 매도 → 원가 64,000 · +14,000 · 21.875%
  - 9주 · 96,000 → 9주 × 10,000 매도 → −6,000
  - 기간 합계 +8,000 · 5%
- 설계 §11-2 순서 예도 고정값이다: 10-08 최초 BUY 10주 × 10,000 뒤 누락된 10-07 BUY 5주 × 20,000 · SELL 2주 × 30,000 을 넣으면 SELL 원가 40,000 · 이익 20,000 · 이후 잔량 13주 · 원가 160,000. 최초 BUY 날짜 정정 · 취소 경우도 같은 테스트에 넣는다.

### 2-3. 저장 경계 (모든 PC 보유 쓰기)

```text
lock(threading.Lock · 모듈 전역)
 → 최신 문서 읽기(없음 / 손상 / v1 / v2 구분 · 손상이면 쓰기 거절 · 덮어쓰지 않음)
 → 같은 record_id · request_id 확인(있으면: 같은 내용 → 저장된 결과 · 최신 보유 반환 · 다른 내용 → 409)   ← revision 확인보다 먼저
 → base_revision 확인(다르면 409 · 새로고침)
 → (첫 v2 쓰기면 BASELINE 생성) → 기록 추가 → 영향받은 기간 재계산 · 전체 문서 검증
 → 같은 디렉터리 mkstemp → write · flush · fsync → os.replace → revision+1
```

- 파일 교체 전 실패 → 보유 · 이력 모두 그대로. 응답 유실 뒤 같은 ID 재시도 → 기존 결과(수량이 두 번 바뀌지 않음).
- 기존 `holdings.save()` 는 이 경계로 위임한다. 그래서 구판 writer 경로가 남지 않는다. 새 모듈은 `app/holdings_store.py`(문서 읽기 · 상태 구분 · 잠금 · 원자 교체 · BASELINE)와 `app/holdings_book.py`(기록 검증 · 이동평균 재계산 · 기간)다. `app/holdings.py` 는 모델 · 검증 · 호환 `load()` 로 남는다.
- **빈 보유**:
  - `load()` 는 정상 빈 배열을 `[]` 로 돌려준다.
  - 화면용 상태는 `NO_FILE` · `EMPTY` · `OK` 로 구분한다. 손상은 예외로 둔다.
  - `validate_holdings` 의 빈 목록 거절은 기본값으로 유지하고, 문서 저장 · 로더에서만 허용 인자를 쓴다.
  - 전량매도 · 정정 종료로 0줄이 되는 저장을 허용한다.

### 2-4. API

| 경로 | 변경 |
|---|---|
| `GET /holdings` | 응답에 `revision` · `status`(`NO_FILE`/`EMPTY`/`OK`) · 행 `position_id` · `cycle_id` 추가(기존 5필드 유지) |
| `PUT /holdings`(입력 정정 모드 · 전체 목록) | body 에 `revision` · `request_id`(저장 동작별 UUID) · 행 `position_id` 를 선택 필드로 추가한다. 같은 저장 경계를 쓴다. ID 있는 행의 수량 · 평단 변경 → ADJUSTMENT · ID 없는 새 행 → REGISTER · 빠진 ID → 정정 종료 · 변화 없음 → 기록 0. **v2 문서에 revision 없는 요청 → 409**. ID 를 안전하게 맞출 수 없으면 409(새로고침) · 파일 없음 + ID 없는 첫 등록 = 허용. 빈 목록 = 허용(모두 정정 종료) |
| `GET /holdings/trade-history` | position 별 기간 · 기록 · 계산값(매도별 실현손익 · 수익률 · 기간 누적 · 정정 전 입력 · 취소 · 입력 정정 구간 표시) · `revision`. `?position_id=` 로 좁힌다. 쓰기 0 · 파일 없음 = 기록 없음 · 손상 = 500 |
| `PUT /holdings/trade-history` | 통합 매매 명령 `{record_id, base_revision, action: buy\|sell\|sell_all\|new_position\|register\|correct\|void, position_id?, ticker?, account_group?, name?, trade?, same_day?: before\|after, supersedes_id?}` → `{record, holdings, revision}` · 422 검증 · 409 충돌(문자열 detail) |
| `GET /holdings/trade-history/market-flow?position_id&cycle_id` | 사용자가 누를 때만 · PC 시세 DB `mode=ro` 읽기(§2-7) · History 조회는 부르지 않음 |
| `GET /holdings/apply/status` | `pending_apply`(true/false/null) 추가 = 현재 허용 5필드 payload sha ≠ 마지막 **성공** 적용 sha. 성공 기록이 없거나 PC 문서를 읽을 수 없으면 `null` = '적용 여부 확인 안 됨'(적용 완료로 표시하지 않음) |

- GET/PUT `/holdings` 와 관련 모델만 새 router `app/api_holdings.py` 로 옮긴다(Q-D 판정). URL · 기존 5필드 의미는 유지하고, 이번 revision · ID · 상태 · 저장 경계 변경을 반영한다. 다른 경로 이전은 하지 않는다.

### 2-5. OCI 적용 (PC 코드)

- `build_apply_payload()` 는 문서를 한 번 읽는다 → `validate_holdings(allow_empty)` → `{"holdings": [asdict(h)]}` 를 기존 `save()` 와 같은 직렬화로 bytes 로 만든다. 개인 이력 · ID · 실현손익 · 메모 · 과거 보유는 구조상 들어갈 자리가 없다.
- 그 bytes 를 PC 임시 파일(바이너리 쓰기)로 scp 한다. 로컬 sha · 원격 sha 대조 · 다시 읽기 확인을 모두 **payload bytes 기준**으로 한다. 원격 검사는 `len>0` 을 빼고 '리스트인지' 만 본다.
- 상태 기록에 `last_applied_sha256` 을 따로 둔다. 이 값은 성공(`OCI_APPLIED`) 때만 갱신하고, 실패가 덮어써도 남는다. `_LOCAL_HOLDINGS` 하드코딩은 `holdings.HOLDINGS_FILE` 로 합친다(테스트 격리 일원화).
- 수동 publication CLI 는 prepare · verify · activate 모두에서 **최상위에 `holdings` 외 키가 있거나, 행에 허용 5필드 외 키가 있는** 문서를 거절한다. 메시지는 '종목 관리의 적용 버튼 사용' 이다(이력 · ID 포함 파일의 원문 바이트 게시 차단). 정상 5필드 파일은 기존 검증 경로 그대로다.
- PC `three_push_package_exporter` 의 `Holding(**h)` 는 `holdings.load()` 로 바꾼다(빈 보유 RuntimeError 는 유지).

### 2-6. OCI 소비 경로 — 정상 빈 보유 (OCI 배포 대상)

- `app/holdings.py` `load()` 가 빈 배열을 허용한다. 하위 호환이라 비어 있지 않은 보유의 동작은 그대로다.
- `target_tickers` 는 보유 브리핑에서 `[]` 를 돌려주고, 위험 알림은 사업군 대표만 쓴다. 파일 없음 RuntimeError 는 유지한다.
- 보유 브리핑 · 위험 알림 조립은 빈 보유를 완전성 가드 앞에서 별도 사유로 처리한다(Q-A 판정대로). 배치 · KRX 개별주 보강 · `price_outcome` 은 loader 수정만으로 정상 동작한다(회귀 테스트로 고정).
- 알려진 기존 동작: 장중 매도 뒤 적용하면 그 종목이 다음 보유 브리핑에 '정상 해소' 로 한 번 나올 수 있다. 줄 삭제 뒤 적용할 때도 같다. 바꾸지 않는다.

### 2-7. 시장 흐름 보기 (`app/holdings_market_flow.py` · 읽기 전용)

- 입력은 position · cycle 이다. 기간의 기록에서 알려진 매수일 · 매도일을 얻는다. BASELINE · REGISTER 의 매수 전후 변화는 계산하지 않는다.
- 기준일은 거래일 그날이고, 휴장이면 `Calendar.days_from(day, 1)` 의 첫 거래일이다. 실제 기준일과 판정 근거(연도 파일 / 평일 기본)를 표시한다.
- 값:
  - 기준일 종가와 최신 저장 종가 사이의 변화
  - 알려진 매수일 ~ 매도일 종가 변화
  - 같은 기준일 KOSPI 변화(양 끝이 모두 있을 때만)
- '매도 뒤 지금까지' 는 **'매도 기준일 → 마지막 저장일(날짜)'** 로 표시한다. 마지막 저장 종가가 오늘 시세라는 뜻이 아니다. 마지막 저장일이 기준일보다 이르거나 기준일 가격이 없으면 변화율을 만들지 않는다.
- 계열 = ETF `etf_daily_price` · 시장 `market_benchmark_daily_price` KOSPI(Q-B 판정). 개별주 = '자료 없음' · KRX 무조정 표는 쓰지 않는다. 양 끝 출처가 다르면 '출처 다름(…→…)' 을 붙여 저장 종가 비교값으로 준다. 단 가격 기준이 확인되지 않거나 다른 출처(조정 ↔ 무조정 등)는 비교 불가다 — ETF 는 `FinanceDataReader` · `NAVER_FDR` 끼리만 비교한다(PC 실측 출처는 이 둘뿐). 그 밖의 출처가 한쪽 끝에 있으면 '비교 불가(가격 기준 확인 안 됨)' 이다. KOSPI 는 지수 종가 3출처(`NAVER_FDR` · `FinanceDataReader/KS11` · `KRX_OPEN_API/idx_kospi_dd_trd`)를 비교한다.
- 각 값에 날짜 · 출처(행의 `source`) · 계열 이름을 붙인다. 정해진 기준일 행이 없으면 인접일로 메우지 않고 '자료 없음' 이다. DB · 표가 없어도 '자료 없음' 이다. **DB 읽기 오류는 '자료 없음' 과 구분해 '조회 실패' 로 알린다.** 시장 흐름이 없거나 실패해도 개인 거래 · History 손익 조회는 그대로 된다.
- 과거 보유의 '매도일 종가 → 최신 저장 종가' 변화가 재진입 때 보는 값이다. PC `/market/refresh` 는 보유와 무관하게 ETF 목록 전체를 모으므로 매도한 ETF 도 계속 저장된다(개별주는 Q-B). ML '재진입 검토' 는 후속 POC5-06 이며, 05 화면에 버튼을 두지 않는다(설계 §8).
- 체결단가로 계산한 개인 손익과 종가 변화는 따로 보인다. 정형 문장만 쓰고 자유 생성 코멘트 · 모델은 없다. 외부 조회 · 쓰기 · 수집 확대도 0 이다.
- 사용할 계열은 Q-B 판정대로 한다.

### 2-8. 화면 (목업 확인 뒤 · §8)

- 「종목 관리」 보유 표는 **읽기 표시 줄**로 바꾼다.
  - 줄(또는 '매매' 버튼)을 누르면 그 종목 · 계좌가 고정된 **매매 입력 창**이 열린다.
  - 줄마다 'History' 버튼을 둔다.
  - 직접 수량 · 평단을 고치는 것은 **'입력 정정' 모드**로 한다. 기존 편집 표를 재사용하고, 저장하면 ADJUSTMENT 로 기록한다는 안내를 붙인다.
- '새 보유 추가' 는 '최초 매수' 와 '잔고 등록' 중 고른다. 같은 (종목, 계좌)의 과거 보유가 있으면 '이전 보유 기간 n건 · History' 를 보이고, 그 position 의 새 기간으로 잇는다.
- [재매수](과거 보유 · History) 는 **선택한 `position_id`** 로 새 기간을 연다. '새 보유 추가' 에서 같은 (종목, 계좌)의 과거 position 이 여러 개라 연결이 모호하면 임의로 합치지 않고 사용자가 고르게 한다.
- 수익률 열(Q-C 판정): 기존 `/holdings/enriched` 를 재사용하고 줄별(position)로 연결한다. 같은 종목이라고 합치지 않는다. 가격 없음 · 불완전은 기존처럼 표시하고, 새 시세 소스 · 폴링은 없다. History 현재 기간 미실현손익도 같은 평가 근거를 쓴다.
- 매매 입력 창은 동일 폭 열의 두 줄이다(목업 확인 항목).
  - 1줄: 거래일 · 시각(선택) · 종류(추가매수/분할매도/전량매도)
  - 2줄: 체결단가 · 수량 · 계산 금액(자동)
  - 메모(선택)는 그 아래 전체 폭이다.
  - 저장 전 '저장 후 수량 · 평단 · 이번 실현손익' 미리보기가 나온다. 전량매도는 잔량을 자동으로 채운다.
- 같은 화면 아래에 접힌 **'과거 보유'**(전량매도한 position · 기간별 실현손익 요약 · History · 재매수)를 둔다.
- History 창(창 하나 · position 별 내용 — 보유 중이면 현재 기간 + 지난 기간, 과거 보유면 지난 기간 + '재매수'):
  - 기간별 매수 · 매도 · 수량 · 단가 · 매매대금 · 매도별 실현손익 · 수익률 · 기간 누적을 보인다.
  - 현재 기간은 미실현손익을 따로 보인다(Q-C).
  - '수수료 · 세금 · 배당 미반영' 표시 · BASELINE '매수일 미상 · 입력 평단 기준' · 입력 정정 구간 표시 · 정정 전 입력 / 취소 기록 펼침이 있다.
  - 기간마다 '시장 흐름 보기' 버튼이 있다.
- OCI 적용 카드는 별도 파일로 옮기고 '미적용 변경 있음' 을 표시한다. 저장 · 매매 뒤 적용 상태를 다시 읽는다.
- 창은 신규 라이브러리 없이 자체 구현한다(`role="dialog"` · `aria-modal` · Esc · 첫 칸 포커스). 오류 detail 은 문자열이다.
- **KS-10**:
  - 새 책임은 `frontend/app/components/holdings_manage/` 새 파일로 둔다. 대상은 매매 창 · History 창 · 과거 보유 · OCI 카드 · 창 틀 · 종목명 조회 훅(기존 `lookupTicker` 추출)이다.
  - `HoldingsManageView.tsx` 는 OCI 카드를 내보내 줄이고, 변경 뒤 **850 미만을 실측**한다.

### 2-9. 변경 파일 (예정 · 줄 수는 구현 뒤 실측)

| 영역 | 파일 |
|---|---|
| backend 신규 | `app/holdings_store.py` · `app/holdings_book.py` · `app/holdings_market_flow.py` |
| backend 재작성 | `app/holdings_history.py`(명령 처리 · 개정 1 의 검증 · ID · 재시도 비교 재사용) · `app/api_holdings_history.py`(GET/PUT trade-history · market-flow) |
| backend 수정 | `app/holdings.py`(빈 배열 허용 · `save` 위임) · `app/api.py` + (Q-D) · `app/holdings_oci_apply.py` · `app/api_holdings_oci_apply.py` · `app/three_push_package_exporter.py` · `scripts/run_holdings_publication.py` |
| OCI 소비(배포) | `app/three_push_runtime/target_tickers.py` · `app/runtime_evidence/holdings_selection_flow.py` · `app/runtime_evidence/holdings_risk_flow.py` (+ `runner_dispatch.py` 는 skip 배선이 필요할 때만) |
| frontend | `HoldingsManageView.tsx` · `holdings_manage/*` 신규 · `lib/api/holdings.ts` · `lib/api/holdingsHistory.ts` 신규 · `lib/api/holdingsApply.ts` · `lib/api/index.ts` · `globals.css` |
| 테스트 | 개정 1 테스트 재작성(계산 · 저장 · API 로 나눔) · `tests/conftest.py`(SQLite 격리 줄 → 문서 경로 격리) · `test_holdings_oci_apply.py` · `test_holdings_apply_status.py` · `test_holdings_draft_flow.py` · `test_run_holdings_publication.py` · OCI 빈 보유 회귀(배치 · PUSH · KRX 개별주 · price_outcome) · vitest(behavior 재작성 · 새 컴포넌트) |
| 문서 | `docs/PROGRAM_TRUTH.md`(보유 저장 · 적용 · OCI 소비 · 새 API · 화면) · `docs/STATE_LATEST.md` · 결과서 |

## 3. 검증 계획

| 수용 기준 | 확인 |
|---|---|
| 1 | 최초 매수 · 추가매수 · 분할매도 · 전량매도 각각 PUT 한 번 → 문서 한 번 교체 · 보유와 이력이 같이 바뀜(tmp 파일) |
| 2 | §3 계산 예 고정 · §11-2 날짜 순서 예(SELL 원가 40,000 · 이익 20,000) · 최초 BUY 날짜 정정 · 취소 · 손실 매도 · 잔량 초과 409 · 소수 수량 · 분할매도 평단 유지 · 전량매도 원가 0 · 재매수 원가 분리 · 누적 수익률 = 합/합 · 기간 경계 밖 거래일 409 |
| 3 | v1 32줄 형태 fixture → 첫 쓰기 BASELINE 줄마다 1건 · 수량 · 평단 그대로 · 매수일 미상 · 다른 계좌 · 복수 줄 원가 분리 · 조회만으로 BASELINE 0 |
| 4 | 교체 전 실패 주입 → 파일 바이트 불변 · 같은 ID 재시도 → 기존 결과 · 수량 1회 · 다른 내용 409 · 오래된 revision 409(재시도 확인이 먼저) · 정정 · 취소 재계산 · 동시 요청 2개(스레드) 직렬화 |
| 5 | 전량매도 → 현재 목록에서 빠지고 History · 과거 보유에 남음 · 전 종목 매도 → 정상 빈 보유(`EMPTY`) · PC 소비자 · OCI 소비 경로 회귀(배치 seed · PUSH 처리 · `no_holdings` · price_outcome) |
| 6 | 입력 정정 · 정정 종료가 BUY/SELL · 실현손익을 만들지 않음(수량 0 정정 = SELL 집계 제외 · 손익 null · 기존 매도 계산 유지 · 기간 합계 '입력 정정 포함 · 참고 계산') · 종목명만 정정 = Q · C · 평단 불변 · 종료 기간 정정이 새 기간 평단 불변 · 구형 PUT(revision 없음 · v2) 409 · 같은 내용 재저장 기록 0 · 정상 빈 보유 ≠ 파일 없음 · 손상 · 조회 실패 |
| 7 | payload 키 = 허용 5필드 · 최상위 = `holdings` 만 · 이력 포함 문서의 전송 바이트에 이력 0 · 이력만 바뀐 문서 → 같은 hash · `pending_apply` false · 보유 변경 → true · 실패 뒤에도 마지막 성공 hash 유지 · 성공 기록 없음 = `pending_apply` null('확인 안 됨') · publication CLI 가 최상위 추가 키 · 행 추가 필드 문서 모두 거절(정상 5필드 파일은 통과) · 원장 · 피드백 · price_outcome 불변 |
| 8 | 목업 확인(정렬 · 행 매매 · History · 과거 보유 · 재매수) · History 조회 = 시장 흐름 호출 0 · 외부 호출 0 · 시장 흐름은 tmp DB `mode=ro`(파일 · 표 없음 = 자료 없음 · 인접일 대체 0 · 출처 표시) |
| 9 | 새 테스트 · 고친 기존 테스트 · vitest · black · flake8 · tsc · eslint · KS-10 실측 · 전체 회귀 마지막 1회. 라이브 보유 · DB 사용 0(tmp · 기존 `_live_guard`) |

- 검토는 코드 + 문서 1회.

## 4. 배포 순서

1. 한 커밋에 넣는다: 저장 형식 v2 + 허용 필드 payload + payload hash. 따로 들어가면 그사이 '적용' 한 번에 이력이 OCI 로 간다.
2. 커밋 · push 뒤 **OCI pull**(사용자 · **거래일 08:05 ~ 15:45 회피** — 공용 PUSH 소비 경로가 바뀌므로 기존 운영 기준 · 당일 15:45 이후 가능 · 새 거래일 대기 없음)로 빈 보유 처리 · publication CLI 거절을 반영한다. OCI 변경은 하위 호환이다.
3. PC 재기동 뒤 사용자 실화면 확인. 그 뒤 첫 '적용' 을 개발자가 OCI 읽기 전용으로 확인한다. 적용 파일의 최상위 키 = `holdings` 만인지 확인하고, 전량매도 테스트는 실제로 하지 않는다.
4. 빈 보유 OCI 동작은 테스트로 확인한다. 실제 빈 보유 적용 · 새 영업일 관찰은 형식상 추가하지 않는다(설계 §9).

## 5. 사용자 확인 항목

- 통합 보유 화면 목업(§8): 정렬 · 행 매매 · History · 과거 보유 · 재매수 · 입력 정정 모드 — 확인 완료(2026-10-08).
- frontend 구현 뒤 실화면: 매수 → 분할매도 → 정정 → 취소 → 전량매도 → 재매수 · 미적용 표시 → 적용.

## 6. 설계 계약 확인 (설계 §1 ~ §9 대조 · 변경 없음)

- 증권사 연동 · 주문 · 현금 · 세금 · 과거 거래 일괄 복원 0
- History 열기 · 종목 선택만으로 시장 조회 · ML 0
- 과거 보유를 정기 flow · 수집 · PUSH 대상에 넣지 않음
- 05 에 ML 판정 버튼 · 임시 성공 판정 0
- 01B / 02 / 03 원장 · 피드백 · price_outcome 불변
- 개인 이력은 원장 export · 동기화 · Telegram · 일반 로그에 0(로그 = record_id · 종류 · 실패 종류만)

## 7. 설계자 질문 (코드와 설계가 실제로 맞지 않는 것만) — 판정: 5건 모두 추천안 기준 확정(2026-10-08 · 설계 §11-1 · 보완 §9)

**Q-A. 빈 보유 날 OCI 보유 PUSH**
- 사실:
  - `load()` 만 고쳐도 보유 브리핑 · 위험 알림은 실패한다. `target_tickers` 가 `RuntimeError('holdings source is empty')` 를 내고, 그것까지 고치면 완전성 가드가 대상 0 을 `quote_incomplete` 로 막는다(메모리 내 실측).
  - 위험 알림 실행이 실패하면 사업군 대표 장중 알림도 같이 멈춘다.
- 추천:
  - 보유 브리핑 = 빈 보유면 발송하지 않고 `skipped/no_holdings` 로 기록한다(기존 '선정 0 = 미발송' 과 같은 결).
  - 위험 알림 = 사업군 대표만으로 계속한다. 대표도 0 이면 `skipped/no_holdings` 다.
  - OCI 에서 도는 변경 파일은 `app/holdings.py` · `target_tickers.py` · `holdings_selection_flow.py` · `holdings_risk_flow.py` · `scripts/run_holdings_publication.py`(verify · activate) 다. 배선이 필요하면 `runner_dispatch.py` 가 더해지고, OCI pull 이 필요하다.
- 대안: 빈 보유 날 '보유 없음' 한 줄 발송.

**Q-B. 시장 흐름 가격 계열**
- 사실(§1-5 실측):
  - 보유 개별주 3종의 PC 일별 종가는 FDR 행이 08-12 에서 멈췄다(PC 수집은 ETF 만). KRX 정규장 종가와도 다르다.
  - KRX 무조정 표는 PC 에 ETF 하루치뿐이다. 모듈 계약도 'UI · ML 로 확장하지 않는다' 이다.
  - ETF 종가 표 · KOSPI 표는 같은 표 안에서 날짜 구간마다 출처가 바뀐다.
- 추천:
  - 계열 = `etf_daily_price`(ETF) · `market_benchmark_daily_price` KOSPI. 표 단위로 하나의 계열로 본다.
  - 기준일 행마다 출처를 표시한다. 양 끝 출처가 다르면 수치는 보이되 '출처 다름(…→…)' 을 붙인다.
  - 개별주는 '자료 없음(PC 개별주 일별 종가 미수집)' 이다. 08-12 까지 있는 FDR 행도 쓰지 않는다.
  - KRX 무조정 표는 쓰지 않는다.
- 대안: 출처가 다르면 '계열 불일치 · 자료 없음'.

**Q-C. '현재 수익률' 표시 위치**
- 사실: 설계 §2 는 저장 뒤 현재 수익률이 바뀐 수량 · 평단으로 계산된다고 한다. 「종목 관리」 는 평가 API 를 쓰지 않고, 머리 주석(POC3-05 §4.3)이 평가 표 노출을 금지한다. 수익률은 「보유 현황」(`/holdings/enriched`)에 있다.
- 추천:
  - 「종목 관리」 보유 줄에 **수익률 한 열만** 더한다. 값은 「보유 현황」 과 같은 `/holdings/enriched` 의 현재가 기준 값이고, 현재가가 없으면 '—' 다.
  - History 현재 기간의 미실현손익도 같은 값을 쓴다. 평가 표 전체는 옮기지 않는다.
  - 사용자 요청('평단이랑 수익률이 변경되는 형태')에 맞춘다.
- 대안: 「종목 관리」 는 무효화만 하고 수익률은 「보유 현황」 에서만 본다.

**Q-D. `GET/PUT /holdings` 위치(KS-10)**
- 사실: 두 경로는 `app/api.py:225-288` 에 있다. `api.py` 는 646줄이고 백엔드 임계는 650 이다. revision · ID · 상태 · 저장 경계 연결을 더하면 650 을 넘는다(트리거 4).
- 추천: 두 경로와 모델을 경로 · 동작 그대로 새 router `app/api_holdings.py` 로 옮긴다. `api.py` 에는 등록만 남긴다(줄 수 감소). 기존 테스트가 경로 · 응답을 그대로 고정한다.
- 대안: `api.py` 안에서 최소 수정 + 다른 경로 이전(범위가 더 넓다).

**Q-E. 입력 정정(ADJUSTMENT)의 의미와 순서**
- 사실: 설계 §6 은 입력 정정을 매매가 아닌 기록으로 두지만, 계산 순서상 위치는 정하지 않았다. 나중에 그 이전 날짜의 매매를 끼워 넣을 수 있다(§4).
- 추천:
  - 입력 정정 = **정정 뒤 값(수량 · 평단)을 그 시점에 확정**하는 기록이다. 순서는 (`effective_date` = 저장한 KST 날짜, 그날 맨 뒤)다.
  - 그 앞 날짜로 나중에 넣은 매매는 정정 시점까지의 경로 · 실현손익에는 반영되지만, 정정 뒤 수량은 정정값이다. 이중 계산을 하지 않는다. History 는 이 구간을 '입력 정정 — 원가 기준 변경' 으로 표시한다.
  - 수량 0 정정 = 잘못 등록한 보유를 정정으로 종료한다(실현손익 0).
  - 입력 정정 · BASELINE · REGISTER 는 취소 · 정정 대상이 아니다. 다시 고치려면 새 입력 정정을 한다.
- 대안: 입력 정정을 차이값(Δ수량 · Δ원가)으로 저장 — 끼워 넣은 매매가 현재 수량에 더해진다.

## 8. 목업 (사용자 확인 · 통합 보유 화면)

- 링크: https://claude.ai/artifact/AQdUdj2GX2CTrhB9rU7aTz (2026-10-08 · 개정 2 판 · 실제 「종목 관리」 폭 · 예시 자료).
- 확인할 점: 행 매매 · History · 과거 보유 · 재매수 연결 · 입력 정정 모드 · 두 줄 정렬 · 미적용 표시.
- **사용자 확인 완료(2026-10-08)**. 확인 중 반영:
  - 재매수 창 = 종목 · 계좌 고정 '최초 매수' 전용(잔고 등록 없음) · 이전 기간 안내 · History 링크
  - History = 창 하나 · position 별 내용(보유 중 = 현재 기간 + 지난 기간 · 과거 보유 = 지난 기간 + 재매수)
  - '재진입 검토'(ML)는 POC5-06 · 05 화면에 버튼 없음

## 9. 설계자 판정 반영 (2026-10-08 · PASS_TO_IMPLEMENT · 원문 = 설계서 §11)

- Q-A ~ Q-E: 추천안 기준 확정. 위 본문(§2-1 · §2-2 · §2-4 · §2-5 · §2-7 · §2-8 · §3 · §4)을 그 자리에서 고쳤다.
- 정상 빈 보유만 `skipped/no_holdings`. 파일 없음 · 손상 · 조회 실패를 정상 빈 보유로 숨기지 않는다.
- 계산 순서: 실제 최초 매수 기간은 Q = C = 0 에서 날짜 · seq 순. BASELINE · REGISTER 만 기간 앞 기준이다.
- 입력 정정:
  - 수량 0 = '입력 정정으로 종료'(SELL · 손익 0원 거래가 아님)
  - 종목명만 정정 = 표시값만 바꾼다
  - 정정 전 값 = 입력 당시 참고값
- 시장 흐름:
  - '매도 기준일 → 마지막 저장일'
  - 기준일 가격 없음 · 마지막 저장일이 더 이르면 변화율 없음
  - 자료 없음 ≠ 조회 실패
  - 출처 다름 표시 · 가격 기준이 다르면 비교 불가
- `pending_apply` null = '적용 여부 확인 안 됨'. publication CLI 는 행 추가 필드도 거절한다.
- 재매수 = 선택한 `position_id` · 모호하면 사용자가 고른다.
- 목업 재확인 없음. 시험은 격리 파일 · 테스트 자료로만 하고, 라이브 보유에 가짜 거래를 넣지 않는다.
- 배포: 거래일 08:05 ~ 15:45 회피 · 당일 15:45 이후 가능.
- 진행: 재제출 없이 backend → frontend → 검증 → 결과서. 결과서에는 신규 market-flow 로컬 조회 경로 · 기존 API 변경 · OCI 변경 파일을 실제대로 적는다.
