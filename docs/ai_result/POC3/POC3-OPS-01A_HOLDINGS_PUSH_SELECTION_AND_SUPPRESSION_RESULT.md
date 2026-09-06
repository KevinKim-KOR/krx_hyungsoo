# POC3-OPS-01A — 보유 PUSH 선별·그룹화·반복 억제 · 개발 결과서

- **작성**: 개발자 (VSCode Claude)
- **수신**: 검증자 (Codex)
- **작성일**: 2026-09-04
- **상태**: **`VERIFIED`** (검증자 r12, 2026-09-06 · ②항목 제한 재검증). **OCI 미배포**.
  r10 `VERIFIED` → 사용자 요청으로 코드 변경 → r11 `REJECTED`(고점 대비 분자 결함) → r12 `VERIFIED`. r10 `VERIFIED` 이후 **사용자 요청으로
  코드가 바뀌었다**(매입 대비 손익 추가) — 기존 `VERIFIED` 를 그대로 이어 쓰지 않는다.
  설계자가 지정한 **제한 재검증 4항목**은 §9.15. 이전 상태: `CLOSED` (2026-09-05).
  사용자 확인 원문: *"일단 지금보다는 나을 것 같습니다. 받아보면서 결정하겠습니다."*
  → **조건부 승인**이다. 실제 발송을 받아본 뒤 형식 조정이 올 수 있다(§10-1).
  **단, 받아보려면 OCI 배포가 선행돼야 한다 — 현재 미배포**(§10-2).
- **검증 라운드**: r1~r4 `REJECTED` → 개발자 영역 전건 처리. **2026-09-05 설계자 확정 회신**으로 계약 2건 해소(§9.7) → r5~r9 `REJECTED` 정정 → **r10 `VERIFIED`**. r9·r10 에서 기능·구조·안전 계약 위반 0건. §9.3·§9.5·§9.6·§9.7·§9.9~§9.17 참조
- **설계서**: `docs/ai_design/POC3/POC3-OPS-01A_HOLDINGS_PUSH_SELECTION_AND_SUPPRESSION_DESIGN_V1.md`
- **PLAN**: `docs/ai_plan/POC3/POC3-OPS-01A_HOLDINGS_PUSH_SELECTION_AND_SUPPRESSION_PLAN_V1.md`
  (V1 `REJECTED` → V1.1 `REJECTED` → V1.2 **`PASS`** → V1.3 §9 확정 후 착수)
- **커밋·푸시**: 사용자 지시로 **수행** (2026-09-05). 커밋 해시는 `git log` 로 실측한다.

---

## 1. 처리한 요구사항

> 계약 2건은 **2026-09-05 설계자 확정**으로 해소됐다. 확정 내용과 정정 구현은 §9.7.

| 확정 계약 | 상태 |
|---|---|
| 선정 이유 있는 종목만 표시 | **DONE** — `RECENT_DECLINE` · `DATA_UNAVAILABLE_OR_STALE` |
| 개수 상한 없음 | **DONE** — 29종목 전부 선정 fixture 로 29행 확인 (T-2) |
| 같은 이유끼리 그룹화 | **DONE** — `reason + state` 그룹 |
| 고유 ticker 1회 · 다계좌 합침 | **DONE** — `(3개 계좌)` 표기 (T-3) |
| OPEN 전체 상태 / 이후 변화분만 | **DONE** |
| 동일 종목·이유·구간 반복 안 함 | **DONE** — `ticker \| sorted(reason:state)` |
| 변화 없으면 미발송 | **DONE** — `skipped/no_change` |
| 선정 0건이면 미발송 + 빈 상태 저장 | **DONE** — `skipped/no_selection` |
| **면책문구 제거** | **DONE** — 금지 문구 6종 미출현 검사 (T-13) |
| **장중에 변하는 값 사용** | **DONE** — 분자 runtime 현재가 / 분모 20거래일 전 종가 |
| **구간 사실형 명칭** | **DONE** — `관찰/주의/경고` 미사용 |
| **발송 성공 후에만 상태 확정** | **DONE** — 부분 실패 시 미저장 (러너 테스트로 고정) |
| **비거래일 최소 안전계약** | **DONE (설계자 확정 반영)** — 완전성을 **고유 ticker 집합 일치**로 판정한다. 건수(`attempted`=행 수)는 분모로 쓰지 않는다. 신규 캘린더·외부 조회·cron 변경 0건 |
| **종가 stale 임계** | **DONE (폐기 확정)** — `MAX_PRICE_STALE_DAYS` 제거. 달력일 임계 없이 **거래일 축 기준일의 정확한 종가** 유무로 판정한다 |
| 미발송 preview | **PARTIAL** — 새 계약으로 재생성(11종목·621자·`telegram_sent=false`). **사용자 형식 승인 기록은 r5 VERIFIED 후**(§10-1) |
| cron 미변경 | **DONE** |

---

## 2. 변경된 파일 목록

| 파일 | 구분 | 줄수 |
|---|---|---:|
| `app/runtime_evidence/holdings_selection.py` | **신규** — reason 판정 · 구간 · 그룹 · fingerprint | 354 |
| `app/runtime_evidence/holdings_selection_state.py` | **신규** — 상태 저장 · 변화 판정 | 190 |
| `app/runtime_evidence/holdings_selection_render.py` | **신규** — 본문 렌더 | 147 |
| `app/runtime_evidence/holdings_selection_source.py` | **신규** — 입력 조립 | 118 |
| `app/runtime_evidence/holdings_selection_flow.py` | **신규** — 흐름 · 비거래일 · privacy · 헤더 포맷 | 367 |
| `app/three_push_runtime/non_trading_day.py` | **신규** — 비거래일 판정 | 120 |
| `app/three_push_runtime/runner_diagnostics.py` | **신규 (r1)** — 러너 진단 전달 분리 | 43 |
| `app/three_push_runtime/price_refresh.py` | 수정 **(r5)** — 완전성 판정용 target/success 집합 진단 추가 | 71 |
| `app/three_push_runtime/runner_spike.py` | **신규 (r1)** — spike 재평가·중복가드 분리 | 142 |
| `scripts/build_holdings_selection_preview.py` | **신규** — 미발송 preview | 188 |
| `scripts/run_three_push_runtime_oci.py` | 수정 — 가드·선정 경로 연결 | 644 |
| `tests/test_holdings_selection.py` | **신규** | 35건 |
| `tests/test_holdings_selection_state.py` | **신규** | 38건 |
| `tests/test_holdings_selection_preview.py` | **신규 (r1)** — T-17 preview | 6건 |
| `tests/test_runner_spike_extraction.py` | **신규 (r2)** — spike 분리 등가성 | 8건 |
| `tests/test_low_frequency_push_operation.py` | 수정 — 러너 계약 추가 (T-21 포함) | 52건 |
| `tests/runtime_evidence/test_runtime_runner_forwarding.py` | 수정 — 새 계약 반영 | 159 |
| `tests/conftest.py` | 수정 **(r1·r3)** — 보유 선정 상태 경로 autouse 격리 (§9.4) | — |
| `tests/test_runtime_runner_spike_no_signal.py` | 수정 **(r3)** — 자정 경계 재현성 (§9.6) | 4건 |
| `docs/STATE_LATEST.md` | 수정 **(종료)** — 상태 앵커 | — |
| `docs/PROGRAM_TRUTH.md` | 수정 **(종료)** — 프로세스 C-1 본문 계약 (미배포 명시) | — |
| `docs/handoff/POC3/POC3-OPS-01A_HANDOFF_CLOSEOUT.md` | **신규 (종료)** — 인계 | — |

**변경 없음**: cron · API 응답 계약 · DB 스키마 · 시장 브리핑 · 급등락 · PC/Mac UI · ML.

#### 2.1 커밋 `ffca640c` 에 포함된 전체 경로 (27건)

r2 까지는 `.py` 만 세어 **17개**로 적었는데, 검증자가 실제 git 상태는 **22경로**
라고 지적했다(설계서·PLAN·RESULT·preview JSON 누락). 아래는 `git status --short
--untracked-files=all` 출력 그대로다.

| 경로 | 상태 |
|---|---|
| `app/runtime_evidence/holdings_selection.py` | 신규 |
| `app/runtime_evidence/holdings_selection_flow.py` | 신규 |
| `app/runtime_evidence/holdings_selection_render.py` | 신규 |
| `app/runtime_evidence/holdings_selection_source.py` | 신규 |
| `app/runtime_evidence/holdings_selection_state.py` | 신규 |
| `app/three_push_runtime/non_trading_day.py` | 신규 |
| `app/three_push_runtime/price_refresh.py` | 수정 |
| `app/three_push_runtime/runner_diagnostics.py` | 신규 |
| `app/three_push_runtime/runner_spike.py` | 신규 |
| `docs/PROGRAM_TRUTH.md` | 수정 |
| `docs/STATE_LATEST.md` | 수정 |
| `docs/ai_design/POC3/POC3-OPS-01A_HOLDINGS_PUSH_SELECTION_AND_SUPPRESSION_DESIGN_V1.md` | 신규 |
| `docs/ai_plan/POC3/POC3-OPS-01A_HOLDINGS_PUSH_SELECTION_AND_SUPPRESSION_PLAN_V1.md` | 신규 |
| `docs/ai_result/POC3/POC3-OPS-01A_HOLDINGS_PUSH_SELECTION_AND_SUPPRESSION_RESULT.md` | 신규 |
| `docs/backlog/BACKLOG.md` | 수정 |
| `docs/handoff/POC3/POC3-OPS-01A_HANDOFF_CLOSEOUT.md` | 신규 |
| `scripts/build_holdings_selection_preview.py` | 신규 |
| `scripts/run_three_push_runtime_oci.py` | 수정 |
| `state/three_push/previews/holdings_selection_preview_latest.json` | 신규 |
| `tests/conftest.py` | 수정 |
| `tests/runtime_evidence/test_runtime_runner_forwarding.py` | 수정 |
| `tests/test_holdings_selection.py` | 신규 |
| `tests/test_holdings_selection_preview.py` | 신규 |
| `tests/test_holdings_selection_state.py` | 신규 |
| `tests/test_low_frequency_push_operation.py` | 수정 |
| `tests/test_runner_spike_extraction.py` | 신규 |
| `tests/test_runtime_runner_spike_no_signal.py` | 수정 |

> ⚠️ **r3 에서 이 표에 경로 오타가 있었다** — 첫 행이 `cripts/...` 로 `s` 가 빠졌다.
> 표를 만든 스크립트가 `git status` **출력 전체에 `.strip()`** 를 걸어 첫 줄의 선행
> 공백(` M `)이 지워졌고, 그 뒤 3글자를 잘라내다 경로 첫 글자까지 먹었다. 수정 파일이
> 첫 줄일 때만 나타나는 오류라 눈으로는 안 보였다. 지금은 출력을 통째로 strip 하지
> 않고 `ln[:2]` / `ln[3:]` 로 나눈다.
>
> 그리고 **"불일치 0건" 을 주장으로 적지 않고 검사로 바꿨다.** 아래 4가지를 스크립트로
> 돌려 통과한 것만 적는다 — ① 이 표 = `git status` 출력과 경로·상태 **집합 완전 일치**
> ② 문서에 등장하는 **모든 파일 경로가 실존**(오타 탐지) ③ git 의 `.py` 변경 전건이
> §2 정본 표에 등재 ④ 줄 수·테스트 건수 실측 대조. r3 마지막 실행에서 **4항목 모두 0건**.
>
> ③ 이 없어서 r3 에서 `tests/test_runtime_runner_spike_no_signal.py` 가 §2.1 에만 있고
> §2 정본 표에는 빠졌다. ② 가 없어서 헤더의 `POC3-OPS-01A_..._DESIGN_V1.md` 같은 축약
> 표기도 방치됐다 — 전체 경로로 폈다.

**커밋·푸시 완료** (`ffca640c`, 2026-09-05 · 사용자 지시). 검증자 r6 B-5 지적
(신규 모듈이 untracked 라 Git 기반 OCI 배포에 포함되지 않음)은 이로써 해소됐다.

> **KS-10 해소 (r1 에서 정정)**: 최초 제출본은 `run_three_push_runtime_oci.py` 가
> **717줄**로 임계 650 을 넘었고, 결과서에 "범위 밖" 이라 적고 넘겼다. 검증자 B-3
> 지적을 받아 **판정 로직을 바꾸지 않는 기계적 분리**로 처리했다: 진단 전달 →
> `runner_diagnostics.py`, spike 재평가·중복 가드 → `runner_spike.py`. 임계 아래로
> 내려왔다 — **현재 줄 수는 §2 표가 정본이다**(라운드마다 바뀌므로 본문에 숫자를
> 박지 않는다). 남은 최대 모듈은 `app/api.py` 632줄로 이번 변경과 무관하다.
>
> ⚠️ **분리 중 사고 1건**: spike 블록을 잘라내면서 뒤따르던 **금지 문구 검사
> (`check_forbidden_wording`)·raw 식별자 검사(`check_raw_identifiers`)가 함께
> 삭제**됐다. `flake8` 의 F401(import 되었으나 미사용) 로 즉시 발견해 §4-a/§4-b 로
> 복원했고, `tests/test_three_push_contract.py` 포함 108건으로 차단 동작을 재확인했다.

---

## 3. 구현 계약 요약

### 3.1 `RECENT_DECLINE` — 장중에 변하는 값

```
20일 수익률 = OCI 실행 시점 현재가 / 20거래일 전 종가 − 1
```

**현행 계약 (설계자 확정 2026-09-05)**

```
기준일 = KRX 거래일 축에서 실행일보다 앞선 20번째 거래일
분모   = 그 ticker 의 **기준일 종가** (정확히 그 날짜)
분자   = 실행 시점의 유효한 runtime 현재가 (price_asof 가 **실행일**)
```

분자는 러너가 이미 수행하는 runtime quote(Naver), 분모는 `etf_daily_price`.
거래일 축은 walk-forward 가 쓰는 KODEX200 시퀀스를 재사용한다
(`TRADING_DAY_AXIS_TICKER`). **신규 외부 조회 0건** — 같은 `fetch_history` 를 쓴다.

- 기준일 종가가 없으면 `DATA_UNAVAILABLE_OR_STALE`. **더 오래된 종가로 대체하지
  않는다** — 대체하면 20거래일이 아닌 구간의 수익률을 20거래일이라고 보고한다.
- 분자의 `price_asof` 가 실행일이 아니면(과거·미래·파싱 불가) 그 종목만 뺀다.
- 고점 대비 보조값은 구간이 불완전하면 **보조값만** 생략한다. 그 때문에 계산
  가능한 `RECENT_DECLINE` 을 버리지 않는다.

> ⚠️ **달력일 임계 `MAX_PRICE_STALE_DAYS = 7` 은 폐기됐다.** r1~r4 에서 개발자가
> 다른 PUSH 계약의 7일을 가져다 썼는데, 설계자가 **승인하지 않고 폐기**했다
> ("20거래일 수익률에도 맞지 않는다"). "며칠 전인가" 가 아니라 **"정확한 기준일
> 데이터가 있는가"** 로 판정한다. 상세 §9.7.

### 3.2 구간 — 판정과 표시가 같은 값

| state | 범위 | 화면 |
|---|---:|---|
| `D5_8` | `−8% < r ≤ −5%` | `20거래일 하락 5~8%` |
| `D8_10` | `−10% < r ≤ −8%` | `20거래일 하락 8~10%` |
| `D10_PLUS` | `r ≤ −10%` | `20거래일 하락 10% 이상` |
| `ACTIVE` | — | `데이터 확인 필요` (별도 그룹) |

**구현 중 실제로 발생한 결함 1건**: `92/100−1` 은 float 로 `−7.999999999999996`
이라 정규화 없이 판정하면 `D5_8` 인데 화면에는 `−8.0%` 로 찍혔다. 설계자가 금지한
경계 불일치다. `normalize_pct()` 로 **판정·저장·표시가 같은 값**을 쓰게 고쳤고
T-16 두 건으로 고정했다.

### 3.3 fingerprint · 상태

```
fingerprint(ticker) = ticker | sorted(reason:state)
```

근거 값은 identity 에서 제외한다(`−10.41 → −10.43` 에 매번 발송 방지).
저장 형식은 `{"reasons": {reason: {"state","value"}}}` — **reason별** 이라
primary 가 그대로여도 secondary 구간 이동이 잡힌다(T-10).

**저장 시점**: `변화 계산 → Telegram 발송 → 전체 chunk 성공 → 원자 교체`.
부분·전체 실패 시 저장하지 않아 다음 슬롯에서 같은 변화를 다시 시도한다.

### 3.4 비거래일 · 시세 완전성 (설계자 확정 2026-09-05)

**완전성 = 고유 ticker 집합 일치.** 건수 비교가 아니다.

```
target_set  = 보유 원장의 **고유 ticker** 집합
success_set = 유효한 runtime quote 를 받은 ticker 집합

complete = target_set 비어 있지 않음
           and success_set == target_set
           and failed_tickers 비어 있음
```

`attempted`(보유 **행** 수, 32)는 분모로 쓰지 않는다 — 고유 ticker 수(29)와 달라
건수 비교가 성립하지 않는다. 건수만 같고 **다른 ticker 가 섞인 경우도 통과시키지
않는다**.

**상태별 처리**

| 상태 | 처리 | 구현 |
|---|---|---|
| 완전 수집 + 전 종목 `price_asof < 오늘` | `skipped/non_trading_day` · 미발송 · state 불변 | `detect_non_trading_day` |
| 한 종목이라도 오늘 quote | 거래일로 판정 | `reason="traded_today"` |
| 오늘 quote 존재 + 일부 실패·과거 quote | **해당 종목만** `데이터 확인 필요` | 러너가 보유만 부분 실패 통과 |
| 성공 0건 | Fail-Closed · 미발송 · state 불변 | `runtime_price_all_failed` |
| 일부 성공 + 오늘 quote 0건 | Fail-Closed · 미발송 · state 불변 | `holdings_quotes_incomplete_no_today` |

"오늘 quote 존재" 는 **대상 종목 중**에서 센다. 대상 밖 ticker 의 체결은 세지
않는다(§9.9 — r5 에서 실제로 뚫렸던 지점).

`any` 가 아니라 `all` 이다 — 한 종목이라도 오늘 체결값이면 거래일로 본다
(오탐보다 과탐 선택).

**부분 실패는 보유만 통과한다.** 시장·급등락은 기존대로 `runtime_price_partial_failed`
로 차단된다(테스트로 고정). 보유까지 차단하면 `DATA_UNAVAILABLE_OR_STALE` 표시가
실제 OCI 경로에서 영영 나오지 않는다.

**가드 위치** — 판정·조립은 §3-c, **모든 skip·fail 결정은 enable flag guard 뒤(§6-c)**.
앞에 두면 push_kind 비활성인데도 데이터 실패가 `push_kind_disabled` 를 가로챈다.

---

## 4. 지시문 외 변경

**4건. 전부 확정 계약의 직접 귀결 · 안전 신호 보존 · 검증자 지적 대응이다.**

1. **`holdings_selection_flow.py` 신설** — PLAN 예상 파일 외. 러너가 KS-10 임계를
   더 크게 넘지 않도록 조립·가드·로깅을 옮겼다.
2. **`private_fields_exposed` · `raw_identifier_exposed` 복원** — 보유 브리핑이
   evidence 경로를 타지 않게 되면서 이 **안전 신호 2개가 사라졌다**. 새 본문에
   같은 탐지기를 그대로 돌려 되살렸다. 없애면 개인 값 노출을 아무도 안 본다.
3. **`runner_diagnostics.py` · `runner_spike.py` 신설 (r1)** — 검증자 KS-10 지적
   대응. **판정 로직 변경 0건의 기계적 분리**다. 러너 closure `_finish` 를 쓰던
   자리는 실패 사유를 튜플로 돌려주고 러너가 `_finish(*fail)` 로 그대로 넘긴다.
4. **`test_runtime_runner_forwarding.py` 갱신** — evidence composer 진단
   (`holdings_snapshot_status` · `nav_contentful_fact_count` ·
   `rendered_holdings_fact_count`)은 새 경로에서 **생성되지 않는다**. 선정 진단으로
   교체하고 안전 신호 2건은 그대로 단언한다.

---

## 5. 미발송 preview

`scripts/build_holdings_selection_preview.py --basis-date 2026-06-30`
→ `state/three_push/previews/holdings_selection_preview_latest.json`

```
[보유 종목 관찰 브리핑 — 형식 미리보기]
과거 종가 기준: 2026-06-30

■ 20거래일 하락 10% 이상 (7)
  삼성SDI  20거래일 -25.3%   [고점 대비 -19.8%]
  KODEX 미국우주항공  20거래일 -21.1%   [고점 대비 -16.5%]
  1Q 미국우주항공테크  20거래일 -18.4%   [고점 대비 -15.3%]
  PLUS 글로벌휴머노이드로봇액티브  20거래일 -13.6%   [고점 대비 -11.2%]
  IBK K-AI반도체코어테크  20거래일 -12.1%
  PLUS 고배당주  20거래일 -10.7%   [고점 대비 -12.7%]
  TIGER 코리아배당다우존스  20거래일 -10.5%   [고점 대비 -12.7%]

■ 20거래일 하락 8~10% (1)
  TIGER 미국테크 TOP10 INDXX  20거래일 -8.0%   [고점 대비 -8.1%]

■ 20거래일 하락 5~8% (3)
  RISE 네트워크인프라 (2개 계좌)  20거래일 -7.9%
  TIME Korea플러스배당액티브  20거래일 -7.1%
  RISE 코리아금융고배당  20거래일 -6.5%   [고점 대비 -12.6%]
```

| 항목 | 값 |
|---|---|
| `basis` | **`EOD_CLOSE_PROXY`** — 과거 장중 시세가 없어 종가를 분자로 썼다. **실제 OPEN 재현이 아니다** |
| 선정 | **11 / 29** |
| 길이 | **587자** (현재 운영 8,690자 대비 **−93%**) |
| `telegram_sent` | **false** |
| 헤더 | 실행시각(`09:14`) **없음** · 기준일만 |
| 면책문구 | **없음** |

`TIGER 미국테크 TOP10 INDXX −8.0%` 가 `8~10%` 그룹에 들어간 것이 경계 정규화가
작동한 증거다.

---

## 6. 현재 시점 실측 — **`no_selection` 이 아니다**

설계자 지시는 "현재 `no_selection` 실측" 이었으나, **현재는 0건이 아니다.**

| 기준일 | 데이터 | 종가 기준 선정 |
|---|---|---:|
| 2026-08-28 (PLAN 작성 시점) | OCI | **0종목** |
| **2026-09-03 (현재)** | OCI | **14종목** |

2026-09-03 선정 (OCI 읽기 전용 · 발송 없음):
`0015B0 −12.7` · `0193T0 −13.9` · `0181B0 −11.1` · `0035T0 −10.6` · `390390 −9.7` ·
`0131V0 −8.4` · `0137V0 −8.4` · `0107F0 −7.5` · `0167Z0 −7.5` · `0174B0 −7.2` ·
`379810 −6.7` · `381170 −6.1` · `379800 −5.8` · `0137W0 −5.0`

**`no_selection` 경로 자체는 테스트로 실증**했다 —
`test_open_zero_selection_saves_empty_state`(빈 상태 저장) ·
`test_holdings_selection_state_never_written_to_live_path`(러너에서 `skipped/no_selection`).

> **Mac 로컬 preview 의 `데이터 확인 필요` 는 OCI 문제가 아니다.**
> 로컬 preview 를 `2026-08-27` 로 돌리면 개별주 3종(`005930`·`000660`·`006400`)이
> `데이터 확인 필요` 로 잡힌다. **Mac DB 가 2026-08-12 에 멈춰 있기 때문**이고
> (기존 BACKLOG 항목), **OCI 는 2026-09-03 까지 정상**임을 실측 확인했다.

---

## 7. 알려진 한계

- **비거래일 판정의 이론적 오탐**: 완전 수집(집합 일치)이고 보유 29종목 전부의
  `price_asof` 가 오늘 이전이면 거래일인데 `non_trading_day` 로 본다. `KODEX 200`
  (3계좌) 등 대표 유동 종목이 있어 현실적으로 어렵지만 **가능성은 남는다**(PLAN §9.4).
- **로컬 개발 DB 는 보유 개별주를 갱신하지 않는다**: 로컬 `POST /market/refresh` 는
  ETF 유니버스만 갱신하므로 Holdings 전용 ticker(개별주)가 정체된다. **운영(OCI)은
  정상**이다 — 배치가 `collect_approved_tickers()` = 승인 seed ∪ Holdings 를 대상으로
  한다. 로컬 수치로 운영을 판단하지 말 것 (§9.17 — 실제로 오등재했다).
- **구간 쏠림**: 60거래일 종가 기준 `D10_PLUS` 가 67%(501/743)다. 확정 임계값을
  그대로 구현했고 명칭을 사실형으로 바꾼 근거이기도 하다.
- **운영 발생 빈도 ≠ §2 분포**: PLAN §2 분포는 **종가 기준**이다. 운영은 분자가
  장중 현재가라 실제 빈도가 다를 수 있다. 추가 조사는 지시대로 하지 않았다.
- **`run_three_push_runtime_oci.py`** — KS-10 임계 650 아래로 내렸으나 여전히 경고
  구간(600 이상)이고 **임계까지 여유가 5줄 남짓**이다(검증자 r3 B-3 주의). 현재
  줄 수는 §2 표. 추가 축소는 01A 범위 밖이라 손대지 않았다.
- **`LOSS_WORSENING`·`INTRADAY_DROP` 미구현** — 설계자 확정 제외.

---

## 8. 다음 검증자에게 알릴 점

1. **가드 순서가 이 Step 의 핵심 위험이었다.** 선정 블록을 flag guard 앞에 뒀더니
   `no_selection` 이 `push_kind_disabled` 를 가로챘고(회귀에서 실제 발생),
   **비활성 상태인데 라이브 상태 파일까지 썼다**. 지금은 **조립은 §3-c(dry-run 확인
   가능), skip 판정·상태 저장은 §6-c(flag guard 뒤)** 로 분리했다.
2. **테스트가 라이브 상태 경로에 실제로 썼던 흔적이 있었다.** 순서 정정 전 실행이
   `state/three_push/holdings_selection_state_latest.json` 을 만들었다. 삭제했고,
   경로 주입이 먹는지·라이브가 안 생기는지를
   `test_holdings_selection_state_never_written_to_live_path` 로 고정했다.
3. **경계 정규화**(§3.2)는 설계자가 명시적으로 금지한 불일치였고 **실제로 발생**했다.
   T-16 두 건이 이를 잡는다.
4. **안전 신호 2개를 잃을 뻔했다**(§4-2). evidence 경로를 벗어나며 사라진 것을
   복원했다.
5. **역검증을 전부 실제로 돌렸다.** 현행은 **26종**(§9.8). §9.2 의 20종은 r1~r3 시점 이력이니 현행으로 읽지 말 것. 실패 테스트명·건수를 그대로 적었다.

---

## 9. 검수 실측

### 9.1 검사

| 항목 | 결과 |
|---|---|
| 신규 계약 test | **87 passed** (`selection` 35 · `selection_state` 38 · `selection_preview` 6 · `runner_spike_extraction` 8) |
| 러너 계약 test | **52 passed** (`low_frequency_push`) |
| **백엔드 전체** | **1,365 passed** (143.16초) |
| `black --check` | 신규·수정 **19파일** unchanged (r1 11 · r2 17 은 오보) |
| `flake8` | **0건** |
| **라이브 상태 유출** | 전체 회귀 후 `holdings_selection_state_latest.json` **미생성**. 추가로 **flag guard 를 무력화한 상태에서도 미생성**(아래 §9.4) |
| 운영 산출물 변경 | `state/three_push/` 기존 파일 변경 **0건** |
| OCI | **읽기 전용만** — 쓰기·발송·배포 **0건** |

### 9.2 역검증 20종 — 전부 탐지 (r1 전면 재실행 · r2 6종 · r3 4종 추가)

> 📌 **이 표는 r1~r3 시점 이력이다.** 설계자 확정(2026-09-05) 이후의 현행
> 역검증은 **§9.8**(26종, 기준선 183) 을 본다.

기준선 **158 passed**(당시 · 사보타주 없음). 각 사보타주는 계약 1곳만 깨고 즉시 원복한다.
대상 테스트: `test_holdings_selection` · `test_holdings_selection_state` ·
`test_holdings_selection_preview` · `tests/runtime_evidence/` ·
`test_low_frequency_push_operation` · `test_runtime_runner_partial_delivery` ·
`test_runner_spike_extraction`.

| # | 무력화 | 실패 |
|---|---|---:|
| N-1 | 첫 슬롯 `full_send` 분기 제거 | **6** |
| N-2 | `normalize_pct` 무력화 (경계 반올림 제거) | **2** |
| N-3 | `_is_stale` 항상 False (stale 종가 허용) | **2** |
| N-4 | stale 일자 파싱 실패를 fail-open 으로 | **1** |
| N-5 | 비거래일 판정에서 실패 건수 무시 | **2** |
| N-6 | 슬롯 라벨 변환 제거 (`OPEN` 원문 노출) | **5** |
| N-7 | 부분 발송에도 상태 저장 | **1** |
| N-8 | 종류별 enable flag 가드 우회 | **2** |
| N-9 | `resolved`(해소) 수집 제거 | **1** |
| N-10 | fingerprint 에서 구간(state) 제외 | **2** |
| **N-11** | 휴장일 판정을 선정 뒤로 되돌림 | **1** |
| **N-12** | spike 중복 skip 의 `error` 를 빈 문자열로 | **1** |
| **N-13** | 신규 fingerprint 만 남기는 body 재조립 제거 | **1** |
| **N-14** | 미래 일자 stale 판정 제거 | **1** |
| **N-15** | privacy 검사 실패를 통과 처리 | **1** |
| **N-16** | 가격 이력 예외를 그대로 전파 | **1** |
| **N-17** | (fixture) 사전 존재하는 라이브 상태 파일 덮어쓰기 | probe 실패 + 원본 복구 |
| **N-18a** | helper 가 주입된 러너 logger 를 무시 | **1** |
| **N-18b** | helper 에 모듈 전역 logger 재도입 | **1** |
| **N-19** | artifact 를 모듈 최상위에 다시 고정 | **1** |

N-11~N-16 은 r2, N-17~N-19 는 r3 지적으로 새로 만든 계약이다. **N-12·N-13 은 r2 전에는 대응 테스트가
없어 미탐지였다** — `duplicate_runtime` 경로를 덮는 테스트가 저장소에 한 건도 없었다.

전부 원복 후 **158 passed** 재확인. 사보타주 잔여 문자열 grep **0건**.

> ⚠️ **재실행 1차는 무효였다.** pytest 인자에 파일과 그 상위 디렉터리를 함께 넘겨
> **0건 수집(exit 5)** 이 났는데, 스크립트가 "exit != 0" 만 보고 10건 전부
> `DETECTED` 로 찍었다. 판정을 `failed` 건수 파싱 + exit 2/3/5 무효 처리로 바꾸고
> 다시 돌렸다. 그 뒤 N-8(가드 앞에 `if False: pass` 삽입)·N-10(`sorted`→`list`)이
> **실질적 무력화가 아니어서** 미탐지로 나왔고, 각각 가드 조건 자체와 fingerprint
> 구성 요소를 깨도록 고쳐 탐지를 확인했다.

### 9.3 검증자 r1 REJECTED — 지적 9건 처리

| # | 지적 | 처리 |
|---|---|---|
| 1 | 비거래일 가드가 `success == attempted` 라 32행/29유니크에서 죽어 있음 | `attempted>0 and success>0 and failed==0` 으로 정정 (N-5 로 고정) |
| 2 | stale 계약이 결과서에만 있고 코드에 없음 | `MAX_PRICE_STALE_DAYS=7` · `_is_stale()` 신설, 파싱 실패는 fail-closed (N-3·N-4) |
| 3 | 헤더에 `OPEN`·ISO 원문 노출 | `slot_label_for()` · `format_quote_asof()` 신설 (N-6) |
| 4 | 비거래일 판정이 flag guard 앞 | §6-c 로 이동 — flag guard 뒤 (N-8) |
| 5 | `load_price_history` 예외가 러너로 전파 | 조립 전체를 감싸 **`holdings_selection_error`** 로 수렴 (r1 보고의 `runtime_evidence_error` 는 오보) |
| 6 | privacy 검사 예외 시 fail-open | 예외를 `out.error` 로 전환해 발송 차단 |
| 7 | T-17 preview 테스트 없음 | `tests/test_holdings_selection_preview.py` **6건** 신설 |
| 8 | 32행/29유니크 · stale 형상 테스트 없음 | 형상 3건 · stale 4건 · 헤더 1건 추가 |
| 9 | 러너 717줄 KS-10 초과 | 기계적 분리로 임계 아래로 (현재 줄 수는 §2 표) |

---

### 9.4 라이브 상태 경로 격리 — 역검증 중 발견한 결함

역검증 N-8(종류별 enable flag 가드 우회) 실행 후 `state/three_push/
holdings_selection_state_latest.json` 이 **실제로 생성됐다**(`entries:{}` ·
`last_slot:OPEN` — `no_selection` 의 빈 상태 저장 경로).

원인은 테스트 격리 부족이다. 러너 테스트 중 일부만
`HOLDINGS_SELECTION_STATE_PATH` 를 개별 monkeypatch 하고 있었고, 나머지는
**flag guard 가 먼저 막아준 덕분에** 라이브 경로에 쓰지 않았을 뿐이다. 가드 하나가
사라지면 곧바로 운영 파일을 건드린다.

조치 — `tests/conftest.py` 에 autouse fixture
`_isolated_holdings_selection_state` 신설. **세 라운드에 걸쳐 형태가 바뀌었다.**

| 라운드 | 방식 | 왜 부족했나 |
|---|---|---|
| r1 | 러너를 `importlib` 로 **직접 import** 후 경로 패치 | 러너 import 가 `load_dotenv_file()` 을 실행해 **모든 테스트에 운영 `.env` 를 올렸다** (r2 B-6) |
| r2 | eager import 제거 + "파일이 **새로 생기면**" 실패 | 이미 있던 파일의 **덮어쓰기를 놓쳤고**, 상대경로라 실행 위치가 저장소 루트가 아니면 엉뚱한 곳을 봤다 (r3 B-6) |
| r3 (현재) | ① 러너와 **같은 절대경로**(`STATE_DIR`) ② 이미 import 됐으면 경로 패치 ③ **생성·내용 변경 모두** 감지 후 원본 복구 + 실패 | — |

`app.three_push_runner_common` 은 import 해도 `.env` 를 읽지 않아 `STATE_DIR`
(절대경로) 를 안전하게 가져올 수 있다.

재검증 — 두 갈래를 따로 확인했다.
- **경로 격리(②)**: N-8 사보타주를 그대로 둔 채 재실행 → 라이브 파일 무변경,
  N-8 탐지는 2건 실패로 유지.
- **감지기(③)**: ② 가 먼저 막아 감지기가 안 돌므로, 라이브 경로에 일부러 쓰는
  일회용 probe 테스트를 넣고 돌렸다 → **"덮어썼다" 로 실패 + 원본 바이트 복구**
  확인 후 probe 삭제.

> 이 결함은 검증자 r1 지적 목록에 없었다. 사용자 규칙(라이브 state 대상 쓰기 금지 ·
> 경로 격리 필수)에 직접 걸리는 사안이라 별도로 처리하고 여기 남긴다.

---

### 9.5 검증자 r2 REJECTED — 처리 내역

**개발자가 닫은 항목 (6건)**

| # | 지적 | 처리 | 역검증 |
|---|---|---|---|
| A-1 | 휴장일에도 선정·stale 판정이 먼저 실행 | 비거래일 **판정**을 §3-c 선정 앞으로 이동. skip **결정**은 §6-c(flag guard 뒤) 유지 | N-11 |
| A-1 | T-21 이 불완전 quote 판정만 확인 | 러너 계약 테스트 `test_t21_non_trading_day_produces_no_stale_judgment` 신설 — 휴장일에 `fetch_price_history` 호출 0건 · `DATA_UNAVAILABLE_OR_STALE` 미생성 | N-11 |
| A-3 | spike 중복 skip 이 `error=None` → `""` 로 바뀜 | `None` 복원. **`duplicate_runtime` 경로 테스트가 저장소에 한 건도 없어** 전체 회귀를 통과했다 — `tests/test_runner_spike_extraction.py` 6건 신설(실제 registry 헬퍼 사용) | N-12·N-13 |
| B-6 | autouse fixture 가 운영 러너를 import 해 `.env` 를 전역 로드 | eager import 제거. ① 이미 import 된 경우만 경로 덮어쓰기 ② **라이브 파일이 생기면 테스트 실패** 로 이중화 | §9.4 |
| B-6 | privacy 차단·가격 이력 예외 수렴 회귀 테스트 없음 | 각각 테스트 신설. `detect_privacy_on_body` docstring 이 실제 동작(fail-closed)과 **반대**였던 것도 정정 | N-15·N-16 |
| B-6 | 미래 날짜가 stale 로 판정되지 않음 | `d > t` 면 stale. `(t-d)` 가 음수라 임계 비교만으로는 통과했다 | N-14 |

**A-2 보고 정확성 정정**

| 항목 | r1 보고 | 실측 |
|---|---:|---:|
| `holdings_selection.py` | 235줄 | **270줄** |
| `test_holdings_selection_state.py` | 21건 | **29건** |
| `test_low_frequency_push_operation.py` | 47건/48건 불일치 | **49건** |
| `test_holdings_selection_preview.py` | 변경 파일 목록 누락 | **등재** |
| 가격 이력 예외 수렴 사유 | `runtime_evidence_error` | **`holdings_selection_error`** |

> r1 결과서의 줄 수·건수는 **작성 시점 실측 후 코드가 더 바뀌었는데 갱신하지 않은**
> 값이었다. 이번에는 §9.1 수치를 전부 이 라운드에서 다시 재고, 파일 표의 줄 수도
> `wc -l` 출력으로 다시 채웠다.

---

## 11. 설계자 확정 계약 2건 — **확정 완료 (2026-09-05)**

> ✅ **2026-09-05 설계자 확정 완료.** `design_decision = CONFIRMED`.
> 확정 원문·근거 실측은 **PLAN §11.5** 가 정본이다
> (`docs/ai_plan/POC3/POC3-OPS-01A_HOLDINGS_PUSH_SELECTION_AND_SUPPRESSION_PLAN_V1.md`).
> 반영 내역은 **§9.7**, 현행 계약은 **§3.1·§3.4**.
>
> 아래 §11.1·§11.2 는 **확정 전에 무엇을 왜 물었는지**의 기록이다 — 현행 계약이
> 아니다. 두 절의 "현재 구현" 서술은 확정 전 상태를 가리킨다.

검증자 r2 가 **개발자가 임의 판단할 사안이 아니라고 판정**한 항목이다. 확정 전까지
구현을 더 진행하지 않는다.

### 11.1 비거래일 완전성 조건

| | 내용 |
|---|---|
| PLAN 확정 | `success == attempted > 0` |
| 현재 구현 | `attempted > 0 and success > 0 and failed == 0` |
| 왜 바꿨나 | 보유는 `collect_target_tickers` 가 **32행**(다계좌 중복 포함), `fetch_many` 가 **29유니크** quote 를 돌려준다. `success == attempted` 는 정상 상황에서 참이 될 수 없어 **가드가 죽어 있었다**(r1 검증자 지적). |
| 쟁점 | 32/29 문제 해소는 맞지만 **PLAN 계약 변경**이다. 개발자가 확정할 수 없다. |
| 선택지 | (a) `failed == 0` 으로 PLAN 을 개정 (b) `success == 유니크 ticker 수` 로 완전성을 다시 정의 (c) 다른 안 |

### 11.2 보유 시세·종가 stale 임계

| | 내용 |
|---|---|
| 현재 구현 | `MAX_PRICE_STALE_DAYS = 7` |
| 출처 | 다른 Spike 계약의 7일을 가져왔다. **이번 설계에는 없는 신규 비즈니스 임계값**이며 보유 runtime 시세·종가에 적용한다는 승인이 없다. |
| 쟁점 | 값의 근거가 없다. 휴장 연휴를 넘기는 선에서 정했을 뿐 실측으로 도출하지 않았다. |
| 선택지 | (a) 7일 승인 (b) 다른 값 지정 (c) 거래일 기준으로 정의 (d) stale 판정 자체를 이번 범위에서 제외 |

> 파싱 실패·미래 일자를 stale 로 보는 **fail-closed 방향**은 임계값과 무관한
> 안전 처리라 그대로 두었다. 임계값만 확정받으면 된다.

---

### 9.6 검증자 r3 REJECTED — 처리 내역

| # | 지적 | 처리 | 역검증 |
|---|---|---|---|
| A-3 | 분리한 spike helper 가 러너 logger 를 쓰지 않아 INFO·오류 로그가 **운영 로그 파일에 안 남음** → "기계적 등가 분리" 가 아님 | 러너 logger 를 helper 로 **주입**. 모듈 전역 logger 제거 | N-18a·N-18b |
| A-3 | 금지 문구 검사 로그 수준이 `warning` → `error` 로 바뀜 | **git 원본 블록을 그대로 복원**(섹션 번호 `4-c` 포함). r1 복원 때 원본을 안 보고 기억으로 다시 썼던 게 원인이다 | `git diff` 로 해당 구간 차이 0 |
| B-6 | 상태 격리 fixture 가 **사전 존재 파일의 덮어쓰기를 감지 못 하고**, 상대경로라 실행 위치에 따라 엉뚱한 곳을 봄 | 러너와 같은 **절대경로**(`STATE_DIR`) + **내용 변경까지** 감지 + 원본 복구 후 실패 | probe 테스트 (§9.4) |
| B-6 | 전체 테스트가 자정을 넘으면 freshness 2건 실패 (모듈 import 시 "오늘" 고정) | artifact 를 **매 호출 생성**으로 변경. 함수 지연성 + **모듈이 결과를 상수로 굳히지 않는지** 둘 다 테스트로 고정 | N-19 |

**A-2 보고 정확성 — r4 정정 (경로 오타 · 정본 표 누락)**

| 지적 | 원인 | 조치 |
|---|---|---|
| git 표 첫 행이 `cripts/...` | 표 생성 스크립트가 `git status` 출력 **전체에 `.strip()`** → 첫 줄 선행 공백이 사라진 채 3글자를 잘라 경로 첫 글자까지 먹음 | 출력을 통째로 strip 하지 않고 `ln[:2]`/`ln[3:]` 로 분리 |
| §2 정본 표에 `tests/test_runtime_runner_spike_no_signal.py` 누락 | 추가 조건을 "문서 전체에 이름이 없으면" 으로 걸었는데 §2.1 에 이미 있어 건너뜀 | §2.1 과 §2 를 **각각** 검사하도록 분리 |

**A-2 보고 정확성 — 재발 방지 조치**

줄 수·건수가 r1·r2·r3 세 라운드 연속으로 틀렸다. 원인은 **문서에 숫자를 손으로
적고, 이후 코드가 바뀌어도 갱신하지 않은 것**이다. 이번에는 방식을 바꿨다.

- §2 파일 표의 줄 수는 `wc -l` 출력으로 **자동 대조·정정**했다 (불일치 0건 확인).
- **본문(표 밖)에서는 줄 수를 아예 빼고** "현재 줄 수는 §2 표" 로 넘겼다. 값이
  한 곳에만 있으면 갱신 누락이 생기지 않는다.
- §2.1 에 `git status --short --untracked-files=all` **출력 전체**를 표로 넣었다.
  r2 까지 `.py` 만 세어 17개로 적었던 것이 누락의 원인이다(설계서·PLAN·RESULT·
  preview JSON).
- §1 에서 승인 대기 2건을 `DONE` → **`BLOCKED`** 로 고쳐 §11 과의 모순을 없앴다.

---

### 9.7 설계자 확정 반영 (2026-09-05) — 정정 6건

`design_decision = CONFIRMED` · `step_status = BLOCKED_PENDING_R5` ·
`commit_push = NOT_ALLOWED_YET`. 확정 원문과 근거 실측은 **PLAN §11.5** 가 정본이다.

| # | 확정 지시 | 구현 | 역검증 |
|---|---|---|---|
| 1 | 비거래일 완전성을 **고유 ticker 집합 일치**로 | `detect_non_trading_day(target_tickers, success_tickers, failed_tickers)`. `attempted`(행 수)는 분모에서 제거 | N-20·N-27 |
| 2 | 부분 실패 처리 계약 정정 | 보유는 부분 실패에도 진행해 **실패 종목만** `데이터 확인 필요`. 시장·급등락은 기존대로 차단. "일부 성공 + 오늘 quote 0건" 은 신규 Fail-Closed | N-24·N-26 |
| 3 | `MAX_PRICE_STALE_DAYS = 7` 제거 | 상수·`_is_stale` 삭제. 달력일 임계 없음 | N-21·N-22 |
| 4 | 정확한 20거래일 기준일 종가 계약 | 기준일 = 거래일 축에서 실행일보다 앞선 20번째. 분모 = **그 날짜** 종가, 없으면 `DATA_UNAVAILABLE_OR_STALE`. 더 오래된 종가로 대체 안 함. 보조값 구간 불완전 시 **보조값만** 생략 | N-21·N-23 |
| 5 | 개별주 가격 이력 단절 열린 결함 등재 | `DEF-PRICE-EQUITY-REFRESH` (열린 결함 2 → **3건**). 재검토 트리거 = 01A 종료 직후·OPS-01B 착수 전 | — |
| 6 | 관련 테스트·역검증 | 아래 §9.8 | 22종 |

**거래일 축은 신규로 만들지 않았다.** walk-forward 가 이미 쓰는 KODEX200 거래일
시퀀스를 그대로 재사용한다(`TRADING_DAY_AXIS_TICKER`). 같은 `fetch_history` 를
쓰므로 **신규 외부 조회 0건**이다.

**가드 순서 재확인** — 정정 과정에서 새 Fail-Closed(`holdings_quotes_incomplete_no_today`)
를 §3-c 에 뒀더니 **`push_kind_disabled` 를 다시 가로챘다**(이전 라운드와 같은 결함).
조립 단계는 실패를 `holdings_fail` 로 보관만 하고, 판정은 **flag guard 뒤(§6-c)**
에서 한다. dry-run 은 발송 경로가 아니므로 그대로 보고한다. N-25 로 고정했다.

### 9.8 역검증 26종 — 전부 탐지 (r5·r6·r7 · stale bytecode 제거 후 전량 재실행)

기준선 **183 passed**. r5 에서 8종(N-20~N-27), r6·r7 에서 4종(N-28~N-31)을 추가했다.

| # | 무력화 | 실패 |
|---|---|---:|
| N-1 | 첫 슬롯 `full_send` 분기 제거 | 1 |
| N-2 | `normalize_pct` 무력화 | 2 |
| N-6 | 슬롯 라벨 원문 노출 | 1 |
| N-7 | 부분발송에도 state 저장 | 1 |
| N-8 | enable flag 가드 우회 | 1 |
| N-9 | `resolved` 수집 제거 | 1 |
| N-10 | fingerprint 에서 구간 제외 | 2 |
| N-11 | 휴장일 판정을 선정 뒤로 | 1 |
| N-12 | spike 중복 skip `error` 를 빈 문자열로 | 1 |
| N-13 | 신규 fp 만 남기는 body 재조립 제거 | 1 |
| N-15 | privacy 실패를 통과 처리 | 1 |
| N-16 | 가격 이력 예외를 그대로 전파 | 1 |
| N-18 | helper 가 모듈 logger 사용 | 1 |
| N-19 | artifact 를 모듈 최상위에 고정 | 1 |
| **N-20** | 완전성을 집합이 아니라 **건수**로 | 1 |
| **N-21** | 기준일 종가 없을 때 **더 오래된 종가로 대체** | 3 |
| **N-22** | 분자의 **당일** 검사 제거 | 4 |
| **N-23** | 보조값 불완전 구간에서도 계산 | 1 |
| **N-24** | 보유 부분 실패를 다시 전면 차단 | 1 |
| **N-25** | 보유 실패 판정을 flag guard 앞으로 | 1 |
| **N-26** | 오늘 quote 0건인데 진행 | 1 |
| **N-27** | target/success 집합 진단 제거 | 1 |
| **N-28** | 오늘 시세 검사를 대상 집합으로 제한하지 않음 | 2 |
| **N-29** | 조립 단계에서 불완전 집합을 통과 | 1 |
| **N-30** | 필수 `target_tickers` 에 기본값 `None` 부활 | 1 |
| **N-31** | `None` 검증을 조기 반환 **뒤로** 이동 | 1 |

> ⚠️ **첫 r5 역검증 실행은 무효였다.** 2분 타임아웃으로 스크립트가 N-25 사보타주를
> 적용한 **직후 SIGTERM 을 받아 복원되지 않았고**, 이어진 실행 전체가 **오염된
> 소스 위에서** 돌았다(N-25 는 "대상 문자열 없음" 으로 SKIP 되어 21/22 로 보였다).
> 소스를 복원해 52 passed 를 확인한 뒤, 스크립트에 `atexit` + SIGTERM/SIGINT/SIGHUP
> 핸들러로 **어떤 경로로 죽어도 원본을 되돌리도록** 고치고 전량 재실행했다.
> 위 표는 재실행 결과다. 사보타주 잔여 grep **0건**.

---

### 9.9 검증자 r5 REJECTED — 처리 내역

| # | 지적 | 처리 |
|---|---|---|
| A-1 | **대상 밖 ticker 가 Fail-Closed 우회** | `today_quote_exists` 가 `market_quotes` 전체를 훑어, `target={A,B,C}`·`success={A,B,X}` 에서 X 만 오늘 시세여도 통과했다. **대상 집합으로 제한**하도록 고쳤다 |
| A-1 | 테스트가 1차 판정만 검사 | `assemble_holdings_push` 진입점까지 연결한 테스트 추가 — 차단 시 **종가 이력 조회 0건**까지 단언 |
| A-2 | §3.1 에 폐기된 7일 임계가 현행으로 남음 | 현행 계약(거래일 축 기준일)으로 교체. 폐기 사실을 명시 |
| A-2 | §3.4 에 과거 건수 판정·전면 차단이 현행으로 남음 | 집합 일치 + 상태별 처리표로 교체 |
| A-2 | §11 이 "설계자 확정 대기" | "확정 완료" 로 갱신. §11.1·§11.2 는 **확정 전 질의 기록**임을 명시 |
| A-2 | §9.1 수치 stale | 전체 **1,351** · 계약 **73건** · 러너 **52건** 으로 재측정 |
| A-2 | PLAN 머리말이 확정 완료와 "2건 미확정" 을 동시 주장 | 머리말·§11 머리말 모두 정정 |
| A-3 | BACKLOG 가 개별주를 "현재부터 계속 불가" 로 기록 | **정정**. 아래 재실측 참조 |

**재현 (지적 A-1)** — 고치기 전 실제 출력:

```
non_trading_day reason = quote_incomplete | skip = False
blocked = None            ← 집합 불일치인데 Fail-Closed 우회
```

고친 뒤 `blocked = reason=quote_incomplete`. 보유하지도 않은 종목의 체결이 발송
여부를 정하던 문제다. N-28·N-29 로 고정했다.

**BACKLOG 정정 (지적 A-3)** — 검증자 실측이 맞다. 2026-09-05 재측정:

| 항목 | 값 |
|---|---|
| 거래일 축(KODEX200) | 3,044일 · 최신 2026-09-04 |
| 현재 기준일 | **2026-08-07** |
| 개별주 3종의 기준일 종가 | **모두 존재** (231,000 / 1,422,000 / 459,000) |
| → 현재 운영 영향 | **없다. 지금은 정상 계산된다** |
| 2026-08-12 이후 누적 거래일 | 16개 |
| 기준일이 단절 시점을 넘기까지 | **약 4 거래일** |

"현재부터 계속 `데이터 확인 필요`" 라고 쓴 것은 과장이었다. 확정 계약대로
**기준일이 단절 시점을 지난 뒤에만** 불가능해진다.

> ⛔ **이 절 전체가 2026-09-06 에 철회됐다.** 로컬 개발 DB만 보고 운영 결함으로
> 단정한 것이었고 **OCI 는 정상 갱신 중**이다. 상세와 실측은 **§9.17**.

---

### 9.10 검증자 r6 REJECTED — 처리 내역

| # | 지적 | 처리 |
|---|---|---|
| B-1 | `target_tickers=None` 이면 **전체 시세 검색으로 조용히 회귀** (fallback 금지 위배) | 기본값 제거 → **필수 인자**. `None` 이면 `ValueError`. 인자 생략은 `TypeError` |
| B-6 | 누락 시 fail-loud 계약 테스트 없음 | `inspect.signature` 로 **기본값이 없음까지** 단언 + 두 예외 경로 테스트 |
| A-2 | 〈옛〉 §7 에 폐기된 7일 임계가 현행 한계로 | 삭제. 대신 개별주 유예를 한계로 기록 (**그 기록도 §9.17 에서 철회**) |
| A-2 | §9.1 전체 회귀가 `1,340` | 실측값으로 갱신 |
| A-2 | 머리말이 `r5 재검증 대기` | 갱신 |
| B-5 | untracked 17 · staged 0 | 의도한 24경로 **`git add` 까지만** 수행 (커밋·푸시 금지 유지) |

**왜 두 번 놓쳤나 — 검사기의 구멍**

r4 에서 만든 결과서 자동 검사는 **표(파일 경로·줄 수·건수)만** 봤다. §7·§9.1 처럼
**본문에 박힌 수치와 폐기된 계약 표현**은 검사 대상이 아니었고, 그래서 "검사 5종
전부 통과" 라고 보고하면서도 실제로는 stale 이 남아 있었다. 게다가 그 수치를 고칠 때
`.replace()` 를 **assert 없이** 써서 대상 문자열이 없으면 조용히 no-op 했다.

조치 — 검사기에 3종을 추가했다.

| # | 검사 |
|---|---|
| ⑥ | 본문 `백엔드 전체` 수치 == **전체 회귀 로그 실측** |
| ⑦ | 폐기된 계약 표현(`stale 임계 7일`·`설계자 확정 대기`·라운드 표기)이 **이력 문맥 밖**에 있으면 실패 |
| ⑧ | PLAN 이 "확정 완료" 와 "미확정" 을 동시에 주장하지 않는가 |

그리고 문서 수정은 **전부 `assert` 후 치환**으로 바꿨다. 확장한 검사기는 즉시
이 라운드 편집에서 생긴 표 수치 2건(`holdings_selection_flow.py` 343→352,
`test_holdings_selection_state.py` 35→36)을 잡아냈다.

**역검증 N-30** — 기본값 `= None` 을 되살리면 **1건 실패**로 잡힌다.

---

### 9.11 검증자 r7 REJECTED — 처리 내역

| # | 지적 | 처리 |
|---|---|---|
| B-1 | `None` 검증이 **조기 반환 뒤**에 있어 `skip_non_trading_day=True`·`traded_today` 두 분기가 통과 | 검증을 **함수 진입부**로 이동 |
| B-6 | `None` 테스트가 `quote_incomplete` **한 분기만** 검사 | **4개 분기 전부** 검사하도록 확장 |
| A-2 | §9.8 기준선 `171` (실측 172) | 갱신 |
| A-2 | 〈옛〉 §8 이 "역검증 10종" | §9.2 는 r1~r3 이력임을 명시하고 현행 종수로 정정 |
| A-2 | 〈옛〉 §10 에 해소된 "설계자 확정 없이는 진행 불가" 가 활성 | 확정 완료로 교체 |

**재현 (지적 B-1)** — 고치기 전:

```
skip_non_trading_day=True : 예외 없이 통과 → None   ← 계약 위반
reason=traded_today       : 예외 없이 통과 → None   ← 계약 위반
reason=quote_incomplete   : ValueError OK
```

"명시적 `None` → `ValueError`" 는 **한 분기에서만** 참이었다. 진입부로 올린 뒤
세 분기 모두 `ValueError`. N-31 로 고정했다.

**⚠️ 역검증 방법론 결함 — stale bytecode (r7 에서 발견)**

N-31 사보타주를 복원한 뒤 전체 회귀가 **1건 거짓 실패**했다. 소스는 정상인데
동작만 사보타주 상태였다. 원인은 Python 의 `.pyc` 무효화 방식이다.

- N-31 사보타주는 **블록 순서만 바꾼 것**이라 파일 **크기가 동일**했다.
- 사보타주 → 복원이 **같은 초 안에** 일어났다.
- Python 기본 timestamp 방식은 `(mtime, size)` 로 캐시 유효성을 본다. 둘 다
  같아 보이면 **사보타주 시점에 컴파일된 `.pyc` 를 계속 쓴다.**

즉 **"복원했으니 원상태" 라는 전제가 성립하지 않는 조건**이 있었다. 같은 크기의
사보타주는 이번이 처음이라 이전 라운드에서는 드러나지 않았다.

조치 — 사보타주 적용·복원 **양쪽에서** `app`/`scripts`/`tests` 의 `__pycache__`
를 지우고, 하위 pytest 를 `PYTHONDONTWRITEBYTECODE=1` 로 돌린다. 그 뒤 **전
역검증을 재실행**했다(26/26 탐지). 재실행 결과가 §9.8 표다.

**검사기 3종 추가** — r6 에서 본문 수치를 잡도록 넓혔는데도 §8·§9.8·§10 이
빠져나갔다. 원인은 검사가 **"내가 stale 이라고 예상한 문자열"** 만 봤기 때문이다.
이번엔 문서 내 주장을 **실측과 대조**하는 쪽으로 바꿨다.

| # | 검사 |
|---|---|
| ⑦-b | 해소된 차단 조건(`설계자 확정 없이는` 등)이 이력 문맥 밖에 있으면 실패 |
| ⑨ | §9.8 기준선 == **집중 회귀 실측** |
| ⑩ | §9.8 "역검증 N종" 표기 == **표 행 수** |

---

### 9.12 검증자 r8 — 대조 결과

접수한 r8 판정문은 **r7 판정문과 문면·인용 줄번호·실측값이 동일**했다. 추측하지
않고 4건을 현재 코드·문서와 하나씩 대조했다.

> 📌 **표기 규약**: `〈옛〉` 로 시작하는 항목은 **고치기 전 문장을 인용**한 것이다.
> 현행 계약이 아니며, 문서 검사기도 이 표시를 보고 건너뛴다.

| r8 지적 | 현재 상태 | 근거 |
|---|---|---|
| `None` 검증이 조기 반환 뒤 | **이미 수정됨** | staged blob 기준 `if target_tickers is None` 23행 / `if skip_non_trading_day` 28행. 세 분기 모두 `ValueError` 재현 |
| §9.8 기준선 `171` | **이미 172** | 590행 |
| 〈옛〉 §10 에 "설계자 확정 없이는 진행 불가" 활성 | **이미 교체됨** | §10-4 는 "설계자 확정 완료 · 미확정 계약 0건" |
| §8 이 "역검증 10종" | **실재했다 → 정정** | 아래 |

**실재한 1건** — §8 이 현행을 25종, §9.2 를 10종으로 적었다. 실제는 §9.8 26종 ·
§9.2 20종이다. 둘 다 실측(표 행 수)으로 다시 채웠다.

**r8 이 인용한 707~712행은 §10 이 아니라 §9.11 의 "r7 처리 내역 표"** 다. 그 표는
고친 대상을 인용하므로 옛 문장(`설계자 확정 없이는 진행 불가` 등)이 **처리 기록으로**
들어 있다. 문자열 검색으로는 현행과 구분되지 않는다.

**검사기 ⑪ 추가** — 각 역검증 섹션의 "N종" 표기를 **자기 표 행 수**와 대조하고,
§8 의 참조 수치가 각 섹션과 맞는지 본다. r7 의 ⑩ 은 §9.8 하나만 봐서 §8·§9.2 를
놓쳤다.

> 나머지 3건이 이미 반영된 상태이므로, r8 이 **현재 트리를 다시 읽은 결과인지**
> 확인이 필요하다. staged == working tree (`git diff` 0건) 이고 HEAD 는 `fd87c440`
> 으로 이번 작업은 아직 커밋되지 않았다 — 커밋된 상태를 읽으면 이번 변경이 전혀
> 보이지 않는다.

---

### 9.13 검증자 r9 — 문서 정합성 4건 정정

r9 는 `HEAD` 가 아니라 **staged blob·작업 트리**를 읽었고, **기능은 통과**
(A-1 통과 · B 전 항목 위반 없음)로 확인됐다. 남은 지적은 결과서 자체 모순 4건이다.

| # | 지적 | 정정 | 근거 |
|---|---|---|---|
| 1 | §9.2 안내문이 현행 §9.8 을 〈옛〉`24종·기준선 171` 로 참조 | `26종·172` | 표 행 수·집중 회귀 실측 |
| 2 | §9.8 이 N-28~N-31 **4건**을 〈옛〉`3종` 으로 기록 | `4종(N-28~N-31)` | 표 항목 수 |
| 3 | 머리말 상태가 〈옛〉`r6 지적 정정 완료` | `r10 지적 정정 완료` (현재값) | 문서 내 최신 라운드. **라운드 기록을 추가할 때마다 최신이 바뀌므로 머리말과 함께 고쳐야 한다** — 검사기 ⑭·⑮ 가 강제한다 |
| 4 | §8 의 현행 종수 〈옛〉`25종` · §9.2 참조 〈옛〉`10종` | `26종` · `20종` | 각 표 행 수 |

**왜 또 놓쳤나 — 검사기가 "예상한 자리" 만 봤다**

r7·r8 에서 검사기를 넓혔지만 여전히 **§9.8 본문 한 곳**만 대조했다. 같은 수치를
가리키는 **상호 참조**(§9.2 안내문·§8·머리말)는 검사 대상이 아니었다. 이번에는
같은 값을 여러 곳에서 주장하면 **전부 데이터에서 다시 계산해 대조**하도록 바꿨다.

| # | 신규 검사 |
|---|---|
| ⑫ | `§9.8(N종, 기준선 M)` **모든 상호 참조**가 표 행 수·집중 회귀 실측과 일치 |
| ⑬ | §9.8 의 "r5 에서 N종(범위), r6·r7 에서 M종(범위)" 이 **표 항목 수**와 일치 |
| ⑭ | 머리말 라운드 표기가 **문서 내 최신 라운드**와 일치 |

**검사기 자체 역검증 (D-1~D-5)** — "검사 통과" 만 보고했다가 검사기가 눈멀어
있던 적이 있어, 이번에는 정정한 4곳을 **일부러 되돌려** 검사기가 잡는지 확인했다.

| # | 문서 사보타주 | 결과 |
|---|---|---|
| D-1 | §9.2 안내문을 `24종·171` 로 | **DETECTED** (실패 2) |
| D-2 | §9.8 라운드 건수를 `3종` 으로 | **DETECTED** (실패 1) |
| D-3 | 머리말을 `r6` 으로 | **DETECTED** (실패 1) |
| D-4 | §8 현행 종수를 `25종` 으로 | **DETECTED** (실패 1) |
| D-5 | §9.8 헤더를 `24종` 으로 | **DETECTED** (실패 2) |

전부 원복 후 사보타주 잔여 grep **0건**, 검사 **14종 전부 통과**.

---

### 9.14 검증자 r10 — 자기참조 모순 1건 정정

r10 은 r9 의 4건이 모두 정상 정정됐음을 확인했고(A-1 통과), **§9.13 이 만들어낸
새 모순 1건**만 지적했다.

| 지적 | 정정 |
|---|---|
| §9.13 의 정정 결과 칸이 〈옛〉`r8 지적 정정 완료` 인데 머리말은 `r9` | 머리말 값에서 다시 채움 |

**원인 — 라운드 기록이 자기 자신을 바꾼다.** §9.13 을 쓰는 순간 문서의 최신
라운드가 r9 가 되므로 머리말도 r9 가 돼야 한다. 검사기 ⑭ 가 그 자리에서 잡아
머리말은 고쳤지만, **§9.13 표 안에 적어 둔 "정정 후 값"** 은 r8 인 채로 남았다.
같은 사실을 두 곳에 손으로 적었기 때문이다.

**검사기 ⑮ 추가** — 문서 안의 모든 `` `rN 지적 정정 완료` `` 가 머리말 값과
같은지 본다. `〈옛〉` 로 인용한 것만 예외다.

**검사기 역검증**

| # | 문서 사보타주 | 기대 | 결과 |
|---|---|---|---|
| D-6 | §9.13 정정 결과를 `r8` 로 되돌림 | 탐지 | **DETECTED** (실패 1) |
| D-7 | 〈옛〉 인용을 현행 값으로 바꿈 | **오탐 없어야** | 통과 (실패 0) |

D-7 은 "인용까지 잡아서 못 고치게 되는" 반대 실패를 확인한 것이다.

---

### 9.15 매입 대비 손익 추가 (2026-09-06) — 제한 재검증 요청

r10 `VERIFIED` 이후 **사용자 요청으로 코드가 바뀌었다.** 설계자가
`verification = PENDING` 으로 두고 **재검증 범위를 4항목으로 한정**했다.
계약 원문·근거는 **PLAN §13** 이 정본이다.

**왜 바꿨나** — 판단용 PUSH 인데 "내가 산 금액 대비" 가 없어 팔지 홀딩할지 정할
수 없었다. 같은 `20거래일 하락 10% 이상` 그룹에서 매입대비가
**+64.1% / +21.9% / −10.7%** 로 갈린다.

**세 지표는 같은 runtime 현재가를 분자로 쓴다** (설계자 지적 반영 — 개발자가
채팅에서 "분모" 라 잘못 설명했다. 코드·문서는 처음부터 분자로 맞게 돼 있었다).

```
매입 대비 손익률 = 현재가 / 수량가중평균 매입가 - 1
20거래일 수익률  = 현재가 / 20거래일 전 종가     - 1
고점 대비 수익률 = 현재가 / 기간 고점            - 1
```

**재검증 4항목 — 개발자 자체 결과**

| # | 설계자 지정 항목 | 고정 테스트 | 역검증 |
|---|---|---|---|
| 1 | 수량가중평균 계산 | `test_average_buy_price_is_quantity_weighted` · `test_average_buy_price_skips_unusable_rows` | **P-2b** |
| 2 | 세 지표가 동일 현재가를 분자로 | `test_profit_loss_uses_same_current_price_as_return` | **P-7** |
| 3 | 선정기 → flow → 본문 전달 | `test_flow_carries_buy_price_into_message` · `test_flow_multi_account_uses_weighted_buy_price` | **P-6** |
| 4 | 손익 변화만으로 반복 PUSH 없음 | `test_profit_loss_is_not_in_fingerprint` | **P-1** |

> ⚠️ **3번은 처음에 역검증 미탐지였다.** 선정기 단위 테스트만 있어 flow 배선이
> 끊겨도 아무도 못 잡았다. 흐름 통과 테스트 2건을 추가해 막았다 — 이전 라운드에
> 지적받은 "builder 필드 유실" 과 같은 유형이다.

**그 밖의 설계자 지적 2건**

| 지적 | 처리 |
|---|---|
| 라벨 `매입` → `매입대비` | 렌더러·테스트 일괄 변경 |
| 목업이 없는 장중 시세(`09:14`)를 표기 | 목업 ① 을 **미리보기 헤더**로 교체. ② 의 `12:30` 도 슬롯 표기임을 명시 |

**실측**

| 항목 | 값 |
|---|---|
| 전체 백엔드 | **1,363 passed** |
| 신규 역검증 | **7/7 탐지** |
| 본문 길이 | OPEN 807자 · MIDDAY 725자 — **chunk 1개** |
| 목업 | `docs/handoff/POC3/OPS-01A_TELEGRAM_MOCK.html` · 사용자 **`APPROVED`** |

---

### 9.16 검증자 r11 REJECTED — 고점 대비 분자 결함 정정

**실제 계산 결함이었다.** 결과서에는 세 지표가 같은 현재가를 분자로 쓴다고 적었지만
**고점 대비만 구간 마지막 종가를 분자로** 쓰고 있었다.

**재현 (고치기 전)** — 현재가 80 · 구간 종가·고점 전부 100:

| 지표 | 실제 | 계약 |
|---|---:|---:|
| 매입대비 | +60% | +60% |
| 20거래일 | −20% | −20% |
| **고점 대비** | **0%** | **−20%** |

장중에 빠진 만큼이 고점 대비에 반영되지 않아 **실제보다 얕은 하락으로 보고**됐다.
투자 판단용 수치라 위험 MEDIUM 이 맞다.

**원인** — `_drawdown_pct_over_window()` 가 분자로 `closes[-1]`(구간 마지막 종가)를
썼고, 호출부도 `current` 를 넘기지 않았다.

**정정** — 함수에 `current` 인자를 추가하고 `current / peak - 1` 로 바꿨다.
분모(기간 고점)는 그대로다. 현재가가 없으면 `None` 이며 **종가로 대체하지 않는다**.

**왜 놓쳤나 — 테스트가 두 지표만 봤다**

`test_profit_loss_uses_same_current_price_as_return` 은 이름과 보고상 "세 지표"
테스트였지만 실제로는 매입대비·20거래일 **둘만** 검사했다. 고점 대비를 확인하지
않아 결함이 71 passed 를 통과했다.

| 조치 | 내용 |
|---|---|
| 테스트 교체 | `test_three_metrics_share_the_same_current_price_numerator` — **셋 다** 단언. 분모를 셋 다 다르게 두어 같은 분자를 쓰는지 실제로 드러나게 했다 |
| 분자 전용 | `test_drawdown_numerator_is_current_price_not_last_close` — 마지막 종가와 현재가를 다르게 두어 구분 |
| 분모 전용 | `test_drawdown_peak_is_window_high_not_current` |
| 역검증 | **P-8**(분자를 마지막 종가로 되돌림) 3건 실패 · **P-9**(호출부가 기준일 종가를 넘김) 2건 실패 |

**수치 영향** — 2026-09-04 실측 선정 8종목에서 고점 대비가 바뀌었다
(예: `KODEX 미국반도체` −10.5% → **−9.7%**, `PLUS 글로벌휴머노이드로봇액티브`
−13.1% → **−10.5%**). 목업·preview 산출물을 모두 재생성했다.

> 참고: 2026-06-30 preview 에서는 고점 대비와 20거래일이 여러 종목에서 **같은 값**이
> 된다. 그 구간이 기준일부터 단조 하락이라 구간 고점 = 20거래일 전 종가이기
> 때문이며, 계산 오류가 아니다. 2026-09-04 실측에서는 서로 다르다.

**실측**: 백엔드 **1,365 passed** · 본문 OPEN 792자 · MIDDAY 739자 (chunk 1개 유지).

---

### 9.17 `DEF-PRICE-EQUITY-REFRESH` 철회 — 개발자 오등재 (2026-09-06)

r10 결과서·PLAN §12.3·STATE·BACKLOG 에 **"보유 개별주 가격이 갱신되지 않는다 ·
유예 4 거래일"** 을 열린 결함으로 올렸다. **틀렸다. 운영에는 결함이 없다.**

**실측 (OCI 읽기 전용)**

| 확인 | 값 |
|---|---|
| OCI 배치 최근 실행 | `attempted=41 success=41 fail=0` · `status=success` |
| OCI DB 개별주 3종 마지막 종가 | **2026-09-03 — 정상** |
| 로컬 DB 개별주 3종 마지막 종가 | 2026-08-12 (정체) |

**원인 — 두 갱신 경로의 대상이 다르다**

| 경로 | 대상 | 개별주 |
|---|---|---|
| OCI 배치 | `collect_approved_tickers()` = 승인 seed ∪ **Holdings** (41개) | **포함** |
| 로컬 `POST /market/refresh` | `fdr.StockListing("ETF/KR")` → `etf_master`(~1,178) | 미포함 |

`collect_approved_tickers()` 는 처음부터 Holdings 를 합친다
(`app/three_push_runtime/market_data_batch.py:85`). 개별주가 대상에서 빠진 적이 없다.

**왜 틀렸나** — 로컬 개발 DB 한 곳만 보고 운영 상태로 단정했다. 이전에도 같은
유형의 실수를 한 적이 있다(`project_kospi_data_quality_suspect` — 시세 이상을
의심했다가 실제 시세와 일치해 철회). **운영 판단은 OCI 를 직접 확인해야 한다.**

**여파** — 설계자에게 "유예 4 거래일, 판단 필요" 로 전달해 불필요한 판단을
요청했다. BACKLOG 열린 결함이 3건으로 잘못 늘었다(→ 2건 복구). 관련 문서
5곳(BACKLOG·PLAN §12.3·STATE·결과서 §10·handoff)을 정정했다.

---

## 10. 사용자 확인이 필요한 항목

1. **preview 확인 — 완료 (2026-09-05)**. OPEN·MIDDAY 실제 운영 헤더 형식과 미발송 4케이스를
   함께 제시했고 사용자가 *"일단 지금보다는 나을 것 같습니다. 받아보면서 결정하겠습니다"* 로
   확인했다. **조건부 승인** — 운영 수신 후 형식 조정 가능.
   `state/three_push/previews/holdings_selection_preview_latest.json`
2. **⚠️ OCI 배포 필요 — 미수행.** 저장소에만 반영됐다. **배포 전까지 실제 발송 본문은 이전
   형식(전 종목 나열)** 이므로 사용자가 "받아보면서 결정" 할 수 없다.
   OCI 는 `a0a0b192` 로 **69 커밋 뒤처져** 있다(2026-09-05 읽기 전용 실측). 그중 cron 진입점을
   바꾸는 것은 `scripts/run_three_push_runtime_oci.py` 하나지만, `app/`·`scripts/` 전체로는
   **38파일**이 함께 딸려간다(ML 체인 복구·구성종목 수집 깊이·PARAM 적용 등).
   **배포는 쓰기 작업이라 개발자가 하지 않는다** — 사용자·설계자 판단 사항.
3. **KS-10 해소됨**(착수 전 626 → r1 최초 717 → 현재는 §2 표). 다만 분리 과정에서 금지 문구·raw 식별자 검사가
   일시 삭제됐다가 복원된 사고가 있었다(§2). 검증자가 §4-a/§4-b 존치를 직접
   확인해 주기 바란다.
4. **설계자 확정 완료 (2026-09-05)** — 비거래일 완전성 조건·stale 임계 2건이 확정돼
   반영을 마쳤다(§9.7·§11.5). **미확정 계약 0건.**
5. ~~개별주 20일 관찰 유예 4거래일~~ → **철회 (2026-09-06).** 개발자 오등재였다.
   **OCI 는 정상 갱신 중**(개별주 3종 종가 2026-09-03, 배치 `41/41 success`).
   로컬 개발 DB만 보고 운영 결함으로 단정했다. 상세 §9.17.
