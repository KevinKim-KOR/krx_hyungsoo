# POC3-OPS-02B-2 — 08:00 시장 흐름 브리핑 메시지·억제·운영 · 개발 결과서

작성일: 2026-09-13 · 작성자: 개발자(VSCode Claude) · 수신: 설계자 → 검증자

```text
IMPLEMENTATION            = DONE (로컬)
BACKEND_FULL_REGRESSION   = 1583 passed / 0 failed / 0 errors
MOCKUPS                   = 7종 생성 · 사용자 확정 (2026-09-13)
GUARD_REVERSE_VERIFICATION = 10/10 (무력화 시 실패 확인)
KS10                      = TRIGGER 0 · NEAR 6 · RUNNER 648 (FREEZE_AT_648)
EXTERNAL_SEND             = 0건
AUTOSEND                  = false (유지)
OCI_DEPLOY                = 0건
ACTIVATION                = 미수행 (별도 승인 대상)
DESIGN_DEVIATIONS         = 3건 (§9 — 전부 사용자 지시 또는 실측 결함 대응)
CALENDAR_POLICY           = USER_POLICY_OVERRIDE_ACCEPTED (snapshot 우선 · 없으면 평일 fallback)
KS10_CLEANUP              = VERIFIED (재검증·되돌림 없음)
```

**설계 편차 3건은 설계자가 승인했다(§9).** `DESIGNER_REVIEW = ACCEPT_FOR_VERIFICATION`
· `READY_FOR_VERIFIER = true`. 최종 `STEP_PASS` 는 검증자 판정 뒤다.

---

## 1. 처리한 요구사항

| 요구사항 | 결과 |
|---|---|
| 07:20 KRX 전종목 수집 · 무조정 가격 적재 · 정합성 판정 | **DONE** |
| 미국 지수 3종 benchmark 배치 연결 | **DONE** (선행 커밋) |
| 08:00 러너 §3-e 조립 · §6-c 판정 · §8 상태 저장 배선 | **DONE** |
| flow-through 테스트 | **DONE** — 9건 (§5) |
| 보호 로직 역검증 | **DONE** — 10건 전부 (§6) |
| 전체 회귀 | **DONE** — 1583 passed |
| 목업 7종 | **DONE** — 사용자 확정 (§4) |
| runner 650줄 이하 | **DONE** — 648줄 (수정 0건) |
| 활성화 차단 해소 | **DONE** — 캘린더 확보 (§3) |
| autosend 활성화 · OCI 배포 | **미수행** — 별도 승인 |

---

## 2. 변경된 파일

### 2.1 신규 — `app/market_briefing/` (8개 · 1,834줄)

| 줄 | 파일 | 책임 |
|---:|---|---|
| 348 | `flow.py` | 조립 흐름 · 거래일 Gate · **창 최신성 Gate** · fingerprint · 상태 저장 |
| 308 | `krx_sync.py` | 07:20 수집 · 기준일 역탐색 · **휴장일 응답 판정** |
| 254 | `evidence.py` | `SP500_SIGN_V1` 방향 · 기초지수 산출 · **추종 ETF 약명** |
| 232 | `krx_store.py` | 무조정 가격 저장소 · snapshot 검증 · 21거래일 창 |
| 229 | `meta_gate.py` | API↔CSV 정합성 (순수 함수) |
| 196 | `render.py` | 본문 · 부분 산출 분기 · **추종 ETF 표시** |
| 256 | `calendar.py` | 거래일 snapshot 로더 · Gate · **평일 fallback** · 실행일 파싱 가드 |
| 11 | `__init__.py` | 패키지 |

### 2.2 신규 — 배선·도구

| 줄 | 파일 |
|---:|---|
| 156 | `app/three_push_runtime/runner_market_briefing.py` — 러너 전용 helper |
| 204 | `scripts/build_krx_trading_days.py` — 거래일 CSV 생성·API 재대조 |
| 322 | `scripts/ops02b2/reverse_verify_guards.py` — 보호 로직 역검증 |
| 427 | `scripts/build_market_briefing_mockups.py` — 목업 7종 생성 |
| 244 | `state/market_meta/krx_trading_days_2026.csv` — 거래일 243일 |

### 2.3 신규 — 테스트 (1,713줄 · KS-10 임계 이하)

| 줄 | 파일 | 건수 |
|---:|---|---:|
| 893 | `tests/test_market_briefing_contracts.py` | 85 |
| 542 | `tests/test_market_briefing_batch.py` | 28 |
| 278 | `tests/test_market_briefing_flow_through.py` | 9 |

### 2.4 수정

| 파일 | 내용 |
|---|---|
| `scripts/run_three_push_runtime_oci.py` | §3-e·§6-c·§8 배선 (648줄 · 이후 수정 0건) |
| `app/three_push_runtime/runner_evidence.py` | `SKIP_EVIDENCE_KINDS` 에 `market_briefing` |
| `scripts/run_oci_market_data_batch.py` · `app/market_benchmark_batch.py` | 07:20 배치 연결 |
| `tests/conftest.py` | 라이브 state·KRX API 차단 가드 |

---

## 3. 활성화 차단 해소 — 거래일 캘린더

```text
이전: ACTIVATION_BLOCKED = true · KRX_TRADING_CALENDAR_NOT_PROVIDED
지금: state/market_meta/krx_trading_days_2026.csv — 거래일 243일
```

### 3.1 휴장일은 API 로 판정할 수 있었다 (실측)

설계 단계에서는 "08:00 에 당일 조회가 비어 판정 불가" 로만 확인했다. **완료된
날짜**에 대해서는 판정이 가능하다는 것을 이번에 실측했다.

```text
basDd=20260101 (신정)  rows=1058  TDD_CLSPRC=""      ← 휴장
basDd=20260911 (금)    rows=1168  TDD_CLSPRC=35130   ← 거래일
주말                    rows=0                        ← 레코드 없음
```

2026-01-01 ~ 09-11 **평일 182일 전수 조회**(실패 0건) → 거래일 171 · 평일 휴장 11.

### 3.2 날짜별 출처를 CSV 에 남긴다

| source | 일수 | 뜻 |
|---|---:|---|
| `MEASURED_KRX_API` | 171 | API 실측 |
| `USER_CONFIRMED` | 72 | 미공시 구간 · 사용자 확인 휴장일 7일 반영 |

`scripts/build_krx_trading_days.py 2026 --verify` 로 실측 구간을 재조회해
대조한다 — 실행 결과 **휴장 11일 = 기록 11일, 일치**.

### 3.3 "일반 공휴일" 규칙으로는 못 맞히는 날이 있다 (실측 근거)

- **2026-05-01 근로자의날** — 법정공휴일이 아니지만 KRX 는 휴장한다.
- 2026-07-17 제헌절 — 2026년부터 공휴일로 재지정됐다(사용자 확인).

규칙만으로 만들었으면 **올해 최소 1일은 장 닫힌 날에 발송**했다.

### 3.4 캘린더가 없는 연도는 **평일 fallback** (2026-09-13 사용자 운영정책)

이전의 "연도 미지원 → `KRX_CALENDAR_REFRESH_REQUIRED` fail-closed" 는 **폐기**됐다.

| 상황 | 판정 | `decided_by` |
|---|---|---|
| snapshot 있음 · 목록에 있음 | 거래일 | `snapshot` |
| snapshot 있음 · 목록에 없음 | **미발송** | `snapshot` |
| snapshot 없음·손상·연도 미지원 · **평일** | **거래일로 간주** | `weekday_fallback` |
| snapshot 없음·손상·연도 미지원 · 주말 | **미발송** | `weekday_fallback` |

실측 확인:

```text
2027-01-04 (월) ok=True  decided_by=weekday_fallback   ← 2027 CSV 없어도 막지 않는다
2027-01-09 (토) ok=False non_trading_day
2026-09-25 (금) ok=False non_trading_day  decided_by=snapshot  ← 추석. snapshot 이 이긴다
```

**2027년 CSV 는 활성화 선행조건이 아니다.** 있으면 쓰고 없으면 평일로 돈다.

창 최신성 Gate 도 **같은 축**을 쓴다 — 캘린더가 그 연도를 안 덮으면 평일 축으로
지연을 잰다. 여기서만 캘린더를 요구하면 캘린더 없는 연도에 기초지수가 늘 stale 이
되어 "평일이면 나머지 Gate 를 계속 평가한다" 는 정책이 깨진다. 평일 축은 공휴일을
모르므로 실제보다 지연이 크게 잡힐 수 있다 — **보수적인 쪽**이다.

---

## 4. 목업 7종 — 사용자 확정

`docs/ai_result/POC3/POC3-OPS-02B-2_MARKET_BRIEFING_MOCKUPS.md` (재생성:
`python scripts/build_market_briefing_mockups.py`). 손으로 쓴 본문이 아니라
운영과 **같은 `flow.assemble_market_briefing()`** 을 호출한 결과다.

| # | 시나리오 | 발송 | 사유 | 글자 | 분할 | 상태 저장 |
|---|---|---|---|---:|---:|---|
| ① | 상승 + 기초지수 2개 | 예 | - | 236 | 1 | 예 |
| ② | 하락 + 기초지수 1개 | 예 | - | 181 | 1 | 예 |
| ③ | 전망만 · 정상 0개 | 예 | - | 112 | 1 | 예 |
| ④ | 전망 불가 + 기초지수만 | 예 | - | 218 | 1 | 예 |
| ⑤ | `CSV_REFRESH_REQUIRED` | 예 | - | 127 | 1 | 예 |
| ⑥ | 전체 stale | **아니오** | `all_data_stale` | 0 | 0 | 아니오 |
| ⑦ | 동일 fingerprint | **아니오** | `no_change` | (236) | 0 | 아니오 |

**전부 Telegram 1건 이내. 분할 0건.** 사용 기준일은 미국 `2026-09-17` · 국내
`2026-09-17`(직전 거래일).

⑦은 fingerprint 를 손으로 적지 않고 **한 번 조립해 저장 → 다시 조립**하는 실제
운영 순서로 만들었다.

사용자 확정: **2026-09-13 "이걸로 확정하겠습니다"**.

---

## 5. flow-through 테스트 (9건)

계약 단위 테스트는 조립 함수를 직접 부른다. 여기서는 **러너 `run()` 을 실제로
태워** 배선을 본다.

| 테스트 | 고정하는 계약 |
|---|---|
| `sends_and_saves_state` | §3-e → §6-c → 발송 → §8 저장이 한 줄로 이어진다 |
| `repeat_is_suppressed_and_state_untouched` | 같은 상태면 두 번째는 안 보낸다 |
| `flag_guard_wins_over_non_trading_day` | **flag 가 꺼져 있으면 휴장일이어도 `push_kind_disabled`** |
| `non_trading_day_skips_without_send_or_state` | 휴장일 미발송 · 상태 미저장 |
| `stale_window_does_not_send_kr_basis` | 창이 오래되면 국내 기준일을 적지 않는다 |
| `telegram_failure_does_not_save_state` | 발송 실패 시 상태 미저장 |
| `partial_delivery_does_not_save_state` | 부분 전송은 성공이 아니다 |
| `dry_run_sends_nothing_and_saves_nothing` | dry-run 무발송·무저장 |
| `repo_state_file_is_not_touched` | 저장소 실경로 미접근 (파일 위치에서 직접 계산) |

---

## 6. 보호 로직 역검증 (10/10)

재현: `python scripts/ops02b2/reverse_verify_guards.py` (EXIT=0). 실경로 미사용 —
전부 임시 디렉터리·임시 DB·stub fetcher.

| 보호 로직 | 가드 있을 때 | **무력화하면** |
|---|---|---|
| ① 거래일 Gate | `skip_reason=non_trading_day` | 휴장일에 본문 180자 생성 |
| ② 창 최신성 Gate | `stale` · 국내 날짜 노출 `False` | 18일 지난 종가로 후보 생성 · `국내 2026-08-31 종가` |
| ③ 정합성 Gate | `CSV_REFRESH_REQUIRED` · 후보 0 | 정합성 깨진 채 후보 생성 |
| ④ 21거래일 창 요구 | `window=None` | `IndexError` 로 터짐 |
| ⑤ 휴장일 응답 판정 | 기준일 `20260816` (거래일) | 기준일 `20260817` (휴장일 · 종가 0행) |
| ⑥ `n≥2` 요구 | 후보 0 | 단일 ETF 지수가 후보로 승격 |
| ⑦ fingerprint 억제 | `skip_reason=no_change` | 같은 상태를 다시 발송 |
| ⑧ 실행일 파싱 가드 | `ok=False` `invalid_date_kst` | **읽을 수 없는 날짜가 거래일로 통과** |
| ⑨ 손상 행 적재 차단 | `ok=True` `decided_by=snapshot` | **`ValueError` 로 러너 중단** |
| ⑩ 실행일 형식 자르기 금지 | `ok=False` `invalid_date_kst` | **fallback 과 snapshot 판정이 갈림** |

---

## 7. 구현 중 발견해 고친 결함 2건

### 7.1 휴장일을 기준일로 집는다 (커밋 `3f48feb8`)

`resolve_basis_date` 가 `if rows:` 만 보고 휴장일 응답(가격 빈 문자열)을 기준일로
집었다. 재현:

```text
07:20 on 2026-08-18 (직전 8/17 광복절 대체공휴일)
  수정 전: 기준일 20260817 → invalid_snapshot · rows_written=0
  수정 후: 20260818(미공시) → 20260817(휴장) → … → 20260814 · rows_written=1163
```

**평일 휴장일 다음날마다** 가격 적재가 0건이었다(2026년 11회). 데이터 오염은
없었으나(fail-closed) 휴장 직후 브리핑이 조용히 열화된다. `has_traded_prices()`
를 공용 판정으로 두고 위반 가능 layer 2곳에 일괄 적용했다.

### 7.2 창 최신성 검사 부재 (사용자 지적)

`resolve_window` 는 21개가 모였는지만 보고 `days[-1]` 을 최신일로 썼다. 적재가
멈춰도 **18일 지난 종가로 "오늘 볼 기초지수" 를 만들어 보낸다.** 7.1 의 버그로
적재가 멈추면 바로 이 상태가 된다.

기존 benchmark 계약 `MAX_STALE_TRADING_DAYS = 1` 을 재사용했다 — 새 임계를 만들지
않았다. 지연을 **못 재는 경우**(적재 최신일이 거래일 축에 없음)도 `stale` 로
fail-closed 한다.

**부수 1건** — stale 로 막아도 본문 `기준` 줄에 쓰지 않은 국내 기준일이 남았다.
설계 §3.4("기준일이 다른 값을 하나의 기준일로 표시" 금지) 위반이라 `price_asof`
를 담지 않게 고쳤다.

---

### 7.3 손상 캘린더 처리 (검증자 r1·r2 · **2라운드 걸림**)

**r1** — `covered_years` 가 `int(d[:4])` 를 검증 없이 실행해 `not-a-date` 한 줄에
`ValueError` 로 러너가 멈췄다. 앞 4자리 숫자 검사를 넣어 막았다.

**r2** — 그 수정이 불충분했다. 앞 4자리만 보므로 `20260918` · `2026-13-45` 같은
행이 **2026년을 덮는 것으로 오인**됐고, 그 결과 **정상 평일이 전부
`non_trading_day`** 가 됐다. 예외가 안 나니 테스트도 통과했다.

```text
r1 수정 후: load_calendar → covered_years=(2026,) · 2026-09-18(금) → non_trading_day  ❌
r2 수정 후: load_calendar → None                  · 2026-09-18(금) → weekday_fallback ✅
```

**근본 수정은 로드 시점이다.** `load_calendar` 가 `parse_date()` 를 통과한 행만
싣는다. 유효한 행이 하나도 없으면 `None` → snapshot 이 없는 것과 같아 평일
fallback 으로 간다. 버린 행 수는 `dropped_rows` 로 진단에 남긴다.

정상 행이 섞여 있으면 그것만 쓴다 — `20260918 / not-a-date / 2026-09-21` 이면
`days={2026-09-21}` · `dropped_rows=2` · `covered_years=(2026,)` 다.

### 7.4 실행일 형식 (검증자 r1·r2 · **2라운드 걸림**)

**r1** — `is_weekend()` 가 파싱 실패를 `False` 로 돌려줬고 호출부가 "평일" 로
해석해 **읽을 수 없는 날짜가 거래일로 통과**했다. 주말 발송을 막는 계약이
무력화된다.

**r2** — `parse_date` 가 입력을 `[:10]` 으로 **잘라서** 검사해
`2026-09-18junk` · `2026-09-18T09:00:00` 이 통과했다. 더 나쁜 것은 snapshot
경로가 문자열 비교라 **같은 입력이 경로별로 다르게 판정**된 점이다.

```text
r1 수정 후: fallback ok=True  vs snapshot ok=False   ❌ 경로별 판정 갈림
r2 수정 후: fallback ok=False vs snapshot ok=False   ✅ 일치
```

지금은 **자르지 않는다.** 길이 10 · `YYYY-MM-DD` 형식만 인정한다.

```text
'2026-09-18'           ok=True   (양쪽 경로 일치)
'2026-09-18junk'       ok=False  invalid_date_kst
'2026-09-18T09:00:00'  ok=False  invalid_date_kst
'20260918'             ok=False  invalid_date_kst
```

**모르면 보내지 않는다 — 다만 예외는 올리지 않는다.**

### 7.5 왜 두 라운드가 걸렸나

r1 수정은 **증상**(예외)만 막고 원인(검증 없이 적재)을 두었다. 그래서 같은 자리에서
**비충돌 오판**이 남았다. 검증자 B-6 지적이 정확하다 — 테스트가 "예외 없음" 만
검사했고 판정값을 보지 않았다.

지금은 두 곳 모두 **판정값까지** 고정한다.

| 보강 | 내용 |
|---|---|
| 계약 테스트 | 손상 캘린더 6종이 `ok is True` 와 `decided_by` 까지 검사 |
| 〃 | 손상 행 4종이 연도 coverage 를 주장하지 않는지 |
| 〃 | 실행일 4종이 **두 경로에서 같은 판정**인지 |
| 역검증 ⑨ | `parse_date` 무력화 → 정상 평일이 막히는지 |
| 역검증 ⑩ | 옛 `[:10]` 구현 복원 → 경로별 판정이 갈리는지 |

---

## 8. 검증 실적

```text
backend 전체 회귀   1583 passed / 0 failed / 0 errors (140.75s)
  market_briefing 계약   85
  batch                  28
  flow-through            9
보호 로직 역검증      10/10 (EXIT=0)
black               338 files unchanged
flake8              0건
KS-10 (458개 전수)   TRIGGER 0 · NEAR 6 · runner 648 (FREEZE_AT_648)
라이브 state·SQLite·캘린더  회귀 전후 sha256 동일
Telegram 발송        0건 · autosend false
OCI write · 배포     0건
```

---

## 9. 설계 편차 3건 — **설계자 승인 완료**

```text
DESIGNER_REVIEW = ACCEPT_FOR_VERIFICATION
§9.1 캘린더 판정 정책 = USER_POLICY_OVERRIDE_ACCEPTED
§9.2 추종 ETF 이름 표시 = 승인 유지
§9.3 창 최신성 Gate     = 승인 유지
```

**셋 다 개발자 임의 판단이 아니다.** 근거를 남긴다.

### 9.1 거래일 판정 정책 — 사용자 운영정책으로 확정 (`USER_POLICY_OVERRIDE_ACCEPTED`)

**거래일 snapshot 이 있는 범위에서는 snapshot 을 사용한다. snapshot 이 없거나
연도가 미지원이면 평일을 거래일로 간주한다. 확인하지 못한 평일 휴장일의 불필요한
푸시는 1인 운영체계에서 사용자가 수용한 운영 오차이며 시스템 결함으로 분류하지
않는다.**

| 항목 | 내용 |
|---|---|
| 폐기된 설계 | §M-5 "캘린더 없으면 fail-closed" · "2027년 캘린더 미확보 시 중단" |
| 근거 | 사용자 운영정책 (2026-09-13) · 설계자 `USER_POLICY_OVERRIDE_ACCEPTED` |
| 2026 CSV | 유지. `source` 컬럼으로 출처를 구분한다 |
| 연간 갱신 BACKLOG | **생성하지 않는다.** 필수 운영조건이 아니다 |

**`USER_CONFIRMED` 값은 공식·API 실측값이 아니다.** 2026 CSV 의 171일은 API 실측
(`MEASURED_KRX_API`)이고, 72일은 사용자가 확인해 알려준 값(`USER_CONFIRMED`)이다.
후자를 실측값이라고 표현하지 않는다.

**여전히 결함으로 분류하는 것** — 주말 발송 · 정상 snapshot 과 반대 판정 · 캘린더
판단 중 예외로 러너 중단 · stale·정합성·21거래일 창 Gate 우회 · 중복 fingerprint
재발송. 전부 테스트로 고정했다(§5·§6).

### 9.2 추종 ETF 이름 표시 — 설계 §3 메시지 계약에 없음

| 항목 | 내용 |
|---|---|
| 이전 | `• 반도체: 5일 +4.8% · 20일 +10.0% · 추종 ETF 2개` |
| 지금 | `• 반도체: 5일 +4.8% · 20일 +10.0%` / `  추종 KODEX 반도체, TIGER 반도체` |
| 근거 | **사용자 요청** — "추종 ETF 2종이라고 했는데 그것이 어떤 것인지 알려주면 좋겠네요" (2026-09-13). 표시 방식(짧은 이름 · 상위 3개 + `외 N개`)도 사용자 확정 |
| 설계 §3.4 준수 | 이름은 공식 `한글종목약명` 그대로(축약·번역·테마명 변환 없음) · 순서는 **종목코드 오름차순 고정**(새 순위 산식 없음) · "추천·유망·매수" 어휘 미사용 · 수익률 계산에 **실제로 쓰인 ticker 만** · 약명 없으면 개수만 |
| 남는 위험 | ETF 이름이 나오면 **매수 지시로 읽힐 여지**가 생긴다. 위 완화로 줄였으나 판단은 설계자 몫이다 |

### 9.3 창 최신성 Gate 신설 — 설계에 없던 보호 로직

| 항목 | 내용 |
|---|---|
| 근거 | **실측 결함 대응**(§7.2). 사용자가 목업 기준일 이상을 지적해 드러났다 |
| 방식 | 기존 `MAX_STALE_TRADING_DAYS = 1` 재사용 · 기존 `stale` 상태 재사용 — 새 임계·새 상태값을 만들지 않았다 |
| 판정 | **승인 유지** (설계자 2026-09-13). 임계 `1거래일` 그대로 |

---

## 9.4 KS-10 Cleanup 상태 (설계자 §9)

```text
KS10_CLEANUP         = VERIFIED
KS10_REOPEN_REQUIRED = NO
```

선행 KS-10 Cleanup 2건(`RUNNER-EVIDENCE-EXTRACTION` · `TRIGGER-FILE-SPLIT`)은
**`VERIFIED` 로 수용**됐다. 설계자 중간 확인이 생략된 것을 이유로 재검증하거나
부모 Step 을 되돌리지 않는다. 실측 확인: 458개 전수 **TRIGGER 0** · 러너 **648줄**
(이번 수정에서도 변경 0건 · `FREEZE_AT_648`).

---

## 10. 알려진 한계 / BACKLOG 비승격 근거

1. **캘린더가 없는 연도의 평일 휴장일** — 브리핑이 생성된다. 사용자가 수용한
   운영 오차이며(§9.1) **결함이 아니다**. 2027년 CSV 는 선택적 유지보수 항목이고
   활성화 선행조건이 아니다.
2. **미공시 구간 임시공휴일** — 위와 같다. 구조적으로 사전 판정이 불가하다.
3. **기초지수 운영 가용성** — `OPS-02B-1` 결론대로 현재 196종 중 6종만 최신이라
   실제로는 후보가 거의 나오지 않을 수 있다. 목업 ③(전망만)이 흔한 모습일 수 있다.
4. **`DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY` 미해소** — 신규 무조정 계열은 기존
   `etf_daily_price` 와 **join 하지 않는다**. 이 Step 으로 해결됐다고 기록하지
   않는다. 분배락 민감도는 BACKLOG 유지.
5. **OCI 미배포** — OCI 는 `5d2614d6` 시점이다. 배포·활성화는 별도 승인.

---

## 11. 다음 검증자에게 알릴 점

1. **설계 편차 3건**(§9)이 설계자 승인 전이면 검증 기준이 흔들린다. 승인 여부를
   먼저 확인하라.
2. **§7 의 결함 2건은 이번 Step 구현 중 발견한 것**이다. 회귀가 아니라 원래
   있던 결함이고, 재현 절차를 결과서에 남겼다.
3. **역검증은 스크립트로 재현 가능**하다(`scripts/ops02b2/reverse_verify_guards.py`).
   가드가 "있을 때 통과" 만이 아니라 "없으면 실제로 깨진다" 를 보인다.
4. **캘린더 CSV 는 `source` 컬럼으로 출처가 구분된다.** 실측 구간은 `--verify`
   로 API 재대조가 가능하고, 사용자 확인 구간은 재현 불가하다(미공시).
5. 러너는 **648줄에서 수정 0건**이다. KS-10 Cleanup 2건은 이미 CLOSED 다.

---

## 12. 사용자 확인이 필요한 항목

1. **OCI 배포** — 로컬 구현만 끝났다. OCI 는 8커밋 이상 뒤처져 있다.
2. **autosend 활성화** — `PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED` 는 `false` 다.
   켜면 08:00 에 실제 발송이 시작된다.
3. **2027년 거래일 CSV** — **필수 아님**(§9.1). 넣으면 그 해 휴장일을 정확히
   막고, 없으면 평일 fallback 으로 돈다.
