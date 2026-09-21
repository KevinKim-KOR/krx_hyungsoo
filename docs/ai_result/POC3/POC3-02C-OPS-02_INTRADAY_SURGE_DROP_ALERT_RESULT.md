# POC3-02C-OPS-02 — 장중 급등락·진입 검토/회피 알림 · 개발 결과서

작성일: 2026-09-20 · 작성자: 개발자(VSCode Claude) · 수신: 설계자 → 검증자

```text
ROUND                       = 검증자 문서·계약 재검증 (§21 확정 반영 + 독립 감사 §22)
IMPLEMENTATION              = DONE — 모듈 + **운영 배선**

RUNTIME_WIRING              = DONE  cron → run() → assemble_holdings_risk_push
                                    → intraday_alert_flow → 본문 → 전송 → 저장
DISABLED_TARGET_LOOKUPS     = 대표 0건 · 대체 0건 · 합집합 = 보유 29종목만
ENABLED_TARGET_LOOKUPS      = 보유 29 ∪ 대표 27 = 53종목
SEND_SUCCESS_STATE_SAVE     = sent_today +1 · last_sent_at 기록 (전송 성공 뒤에만)
CAP_DROPPED_SIGNALS         = NOT_STAMPED — 구역 상한에 잘린 신호는 발송 아님 (수정 · §22-1)
DELIVERY_PROGRESS_ON_FAILURE_OR_PARTIAL = NOT_ADVANCED
SENT_TODAY_ON_FAILURE_OR_PARTIAL        = NOT_INCREMENTED
LAST_SENT_AT_ON_FAILURE_OR_PARTIAL      = NOT_CREATED_OR_ADVANCED
OBSERVATION_ENTRIES_EVERY_TICK          = SAVED
FINGERPRINT_PERSISTENCE                 = NONE
INTRADAY_SUMMARY_FLOW       = render_checkup_summary · 15:40 본문 말미 한 줄
SECTOR_COVERAGE_GATE        = sector_min_coverage_pct = 80 (PARAM)
PROVIDER_FAILURE_FALLBACK_CALLS = 0건 (조회 횟수로 실증)
FLOW_THROUGH_TESTS          = 53 passed — 함수 47 (run() 호출 36 · 비호출 11)
                              + 억제표 1함수가 7셀로 전개

BACKEND_FULL_REGRESSION     = 1,904 passed / 0 failed / 0 errors
BLACK / FLAKE8              = 361 files unchanged / 0건
KS10_TRIGGER / NEAR_LIST    = TRIGGER 0 · NEAR 7 (§9-2 목록)
RUNNER_LINES                = 646  (동결선 648 이하 · D3 훅 · §23-2)
COMMIT_PUSH_OCI_SEND        = 0 / 0 / 0
INTRADAY_POLICY_ENABLED     = false

DESIGNER_DECISION           = OPTION_A_FOR_BOTH  (§20 · §21)
D2_TRI_STATE_OBSERVATION    = DONE — 평가 불가는 회복으로 기록하지 않음 (§23-1 · 교차 §24-2·§24-3)
D3_RECORD_GATE              = DONE — dry-run·flag-off·duplicate 는 라이브 파일 미변경 (§23-2 · 교차 §24-1)
BLOCKING_ITEM               = NONE
```

입력: 설계서 `docs/ai_design/POC3/POC3-02C-OPS-02_INTRADAY_SURGE_DROP_ALERT_DESIGN_V1.md`
(§13 = PLAN V1 판정) · PLAN `docs/ai_plan/POC3/POC3-02C-OPS-02_INTRADAY_SURGE_DROP_ALERT_PLAN_V1.md`

---

## 1. 처리한 요구사항

| 설계 항목 | 결과 |
|---|---|
| §13-1 급등 3단계 대칭 (`U5_7`/`U7_10`/`U10_PLUS`) | **DONE** (§2) |
| §13-2 보유·사업군 모두 Naver `fluctuationsRatio` | **DONE** (§3) |
| §13-3 회차당 1건 · 일일 4건 · rolling 60분 미적용 | **DONE** (§5) |
| §13-4 호출량 — 대체는 ticker 단위 실패 시 1회 | **DONE** (§4) |
| §2 보유 ∪ 대표 합집합 · 같은 ticker 한 번만 | **DONE** (§4) |
| §4-2 사업군 판정 4상태 | **DONE** (§2) |
| §5 억제·cooldown 120분 | **DONE** (§5) |
| §6 구역별 3종목 · 우선순위 | **DONE** (§5) |
| §7 본문 · 빈 구역 생략 · 전부 비면 미발송 | **DONE** (§7 목업) |
| §8 15:40 점검 요약 한 줄 · `확인 불가` | **DONE** |
| §9 실패 격리 | **DONE** (§6 무력화 실증) |
| §10 검증 전 `enabled=false` | **DONE** — 정책 `None` 이면 본문 미생성 |
| 최근 데이터 재생 · 목업 | **DONE** (§3 · §7) |

---

## 2. 판정 규칙 구현

### 2-1. 급등 3단계 — 급락 경계를 **한 글자도 바꾸지 않았다**

```python
_SURGE_BANDS = ((U10_PLUS, 10.0, None), (U7_10, 7.0, 10.0), (U5_7, 5.0, 7.0))
```

부등호 방향이 뒤집힌다 — 급락은 `상한 배타·하한 포함`(정확히 −5% → `D5_7`),
급등은 `하한 포함·상한 배타`(정확히 +5% → `U5_7`). 0 에서 멀어질수록 심각해지는
성질을 양쪽에서 같게 유지하려면 이렇게 돼야 한다.

```text
  -12% D10_PLUS │  -10% D10_PLUS │  -7% D7_10 │  -5% D5_7 │ -4.99% -
 +4.99% -       │   +5% U5_7     │  +7% U7_10 │ +10% U10_PLUS │ +12% U10_PLUS
```

급등도 심각도 1·2·3 이며 급락과 **별도 축**이다.

### 2-2. 사업군 4상태 (§4-2)

`app/runtime_evidence/sector_signal.py`. **추격 주의가 진입 검토보다 앞선다** —
임계가 PARAM 으로 바뀌어도 겹치지 않도록 순서로 못박았다.

순위는 **평가 가능한 사업군 안에서** 매긴다. 조회 실패한 사업군을 분모에 넣으면
상위 20% 가 실제보다 좁아진다.

> **죽은 분기 1건을 구현 중 발견해 고쳤다.** `classify_sector` 가 창 수익률까지
> 봐서 이력이 모자라면 그냥 `None` 을 내므로, "진입 후보가 될 뻔했는데 이력이
> 없어 빠졌다" 를 구분할 수 없었다 — 감사 기록이 사라진다. `is_entry_band()` 를
> 분리해 그 경우를 `short_history` 로 남긴다.

### 2-3. 수치는 코드 상수가 아니다

`REQUIRED_POLICY_KEYS` 에 6개를 추가했다(`sector_entry_min_pct` ·
`sector_chase_pct` · `sector_avoid_drop_pct` · `sector_rank_top_pct` ·
`max_items_per_section` · §15-3 에서 더한 `sector_min_coverage_pct`) — 총 12개다.
기존 parametrize 테스트(`test_enabled_requires_every_policy_value`)가 키마다 한
셀씩 자동으로 덮는다(12셀). 백테스트·ML 로 교체할 수 있다.

---

## 3. 가격 기준 정정 — 설계자 §13-2 요구 전후 비교

### 3-1. 무엇을 바꿨나

```text
전  day_drop = current(무조정 Naver) / close_on(etf_daily_price, prev_day)(조정)
후  day_drop = Naver fluctuationsRatio          (무조정 D-1 대비)
```

필수 계약을 전부 코드로 막았다.

| 계약 | 구현 |
|---|---|
| `fluctuationsRatio` 직접 사용 | `market_naver.py` 가 그 필드만 읽는다 |
| 부호 복원 금지 | `compareToPreviousClosePrice` 는 **코드에 없다** |
| 역산 금지 | 등락률이 현재가와 모순돼도 등락률을 따른다(테스트) |
| 조정계열 fallback 금지 | `close_on` import 제거 · 테스트가 잔존 검사 |
| 누락은 그 ticker 만 제외 | `usable_day_return` → `None` → `unavailable` |
| 최신성 검사 유지 | `_is_same_day` 게이트 그대로 |

`0.0` 은 **유효한 보합**이라 별도 정규화 함수를 뒀다. `_coerce_price` 의
`n <= 0` 규칙을 등락률에 쓰면 보합뿐 아니라 **하락이 통째로** 사라진다.

### 3-2. 전후 비교 (OCI 실데이터 24거래일 · 보유 29종목 · 발송 0)

```text
판정 동일                        574건
수치 동일 · 급등 신규 검출          18건   ← 가격기준 무관 (기능 추가)
수치가 실제로 달라짐                6건   ← 가격기준 정정
  그중 급락 구간 판정이 바뀜         0건
```

**급락 판정이 바뀐 사례는 0건이다.** 수치가 달라진 6건은 전부 임계 밖이다.

| 날짜 | ticker | 옛 % | 새 % | 구간 |
|---|---|---:|---:|---|
| 2026-08-28 | 0097L0 | +0.60 | +0.16 | — → — |
| 2026-08-28 | 441800 | −0.33 | −0.83 | — → — |
| 2026-08-28 | 161510 | +1.11 | +0.71 | — → — |
| 2026-08-28 | 0107F0 | −0.48 | −0.74 | — → — |
| 2026-09-14 | 498860 | +0.18 | −0.06 | — → — |
| 2026-09-14 | 0052D0 | +0.51 | +0.10 | — → — |

최대 괴리 `0.50%p`. 두 날짜에 몰린 것은 **분배락**으로 설명된다 — 조정계열이
과거 종가를 소급 조정하므로 그 직후 분모가 달라진다. 무조정 D-1 이 맞다.

정확도 근거는 PLAN §1-3 — Naver 역산 전일종가가 KRX 무조정 D-1 과 **7/7 일치**.

---

## 4. 조회 대상과 호출량

```text
보유 29종목(고유) ∪ 대표 27종목 = 53종목   ← 설계자 §13-4 와 일치
```

> **설계 §2 위반을 하나 발견해 고쳤다.** 보유 원장은 다계좌라 같은 ticker 가
> 32행으로 온다(고유 29). 기존 경로는 그 32행을 그대로 조회한다 — 중복 3건.
> 설계 §2 가 "같은 ticker 는 한 번만" 을 명시하므로 **장중 경로에서만** 제거했다.
> `holdings_briefing` 은 기존 동작을 그대로 뒀다(행 수 32).

| 구분 | 현재 | 구현 후 |
|---|---:|---:|
| 보유 브리핑 3회 | 32행 × 3 = 96 | 96 |
| 조건형 7틱 | 32행 × 7 = 224 | **53 × 7 = 371** |
| 하루 합계 | 320 | **467** |

설계자 §13-4 의 458 과 9건 차이는 **보유 브리핑이 고유 29 가 아니라 행 32 로
조회하기 때문**이다(기존 동작, 이번 변경 아님). 조건형만 보면 371 로 정확히
일치한다.

**fallback 포함 이론상 상한**: 대표 27 이 전부 실패하고 대체가 전부 있으면
`53 + 22 = 75` 종목 × 7 = 525건. 대체 보유 대표는 22/27 이다. 재귀 대체는
금지이므로 그 이상은 없다.

---

## 5. 억제·상한

| 계약 | 구현 |
|---|---|
| fingerprint 에 숫자 제외 | `ticker#state` — 수치만 변하면 재발송 안 함 |
| cooldown 120분 | `compute_sector_changes` |
| 상태 변경은 cooldown 무관 | 즉시 발송 |
| 억제된 신호가 cooldown 을 밀지 않음 | `merge_sector_entries(sent=...)` 만 갱신 |
| 새 거래일 초기화 | `date_reset` |
| 회차당 1건 | 본문 1개만 생성 |
| 일일 4건 | `sent_today >= max_day` → 미생성 |
| 구역별 3종목 | `build_section_plan` · 잘린 것은 `dropped` 에 남김 |
| 발송 진척은 전송 성공 뒤에만 전진 | 조립 단계(`assemble_holdings_risk_push`)는 매 회차 `save_observation` 으로 관측만 저장 · `sent_today` 전진과 `last_sent_at` 기록은 러너의 전송 성공 경로에서만 |

rolling 60분 제한은 **넣지 않았다**(설계자 §13-3 — KS-5 "급변 상황 제외" 예외).

---

## 6. 실패 격리 — 무력화로 실증

설계 §9 "사업군 경로 실패가 보유 급락 경로를 막으면 안 됨" 을 **실제로 깨 보고**
확인했다.

```text
가드 있을 때                                        17 passed
① 사업군 try/except 제거                            2 failed
② 정책 비활성 시 기본값 대체                          1 failed
③ 일일 상한 제거                                    1 failed
```

> **② 는 처음에 안 잡혔다.** 내 테스트가 `flow.active_policy` 를 통째로 대역해
> **그 함수를 실행하지 않았다.** `store.get_active` 만 대역하고 함수를 진짜로
> 돌리는 계약 테스트 5건을 추가해 잡았다. 같은 실수(대역이 계약을 가림)를
> 또 했고, 실측으로 확인해 고쳤다.

가격 기준 쪽도 같은 방식으로 실증했다.

```text
① 조정계열 역산으로 되돌림        4 failed
② 0.0 을 누락으로 취급            4 failed
③ bool 거부 제거                 2 failed
④ 최신성 게이트 제거              2 failed
⑤ compareToPreviousClosePrice 사용 1 failed
```

---

## 7. 메시지 목업 (실데이터 재생 · 발송 0)

```text
[장중 급등락] 10:30

보유종목
• KODEX 200: 전일 대비 -5.4%
  보유 급락 5~7%
• KODEX 반도체: 전일 대비 +7.8%
  보유 급등 7~10%

신규 진입 검토
• 통신 · KoAct 광통신&위성네트워크액티브: +2.0%
  5일 +1.4% · 20일 +4.9%

진입 회피
• 건설 · KODEX 건설: -2.5%
  장중 급락
• 게임 · KODEX 게임산업: -2.3%
  장중 급락
• 로봇 · KODEX 로봇액티브: -2.0%
  장중 급락

기준
현재가 2026-09-16 10:30 · 직전 종가 2026-09-15

※ 자동 감지 결과이며, 최종 판단은 사용자가 합니다.
```

보유 2건은 형식 확인용 대역이고, 사업군 4건은 **실데이터 판정 결과**다.
상한으로 2건이 잘렸고 이력에는 남는다.

### 15:40 보유 브리핑 말미 (§8)

```text
장중 점검 7회 · 알림 2건 · 중복 억제 3건 · 신호 없음 2건
장중 점검 7회 · 알림 1건 · 중복 억제 2건 · 신호 없음 3건 · 조회 실패 1회
장중 점검 확인 불가
```

집계 불가를 `0` 으로 위장하지 않는다.

### 단일 시점 신호 재생 (§10-2)

**빈도 측정이 아니다** — 2026-09-16 **한 날짜**의 종가로 판정을 재생한 것이다
(설계자 §14-7 정정). 여러 날·여러 틱에 걸친 실제 발송 빈도는 활성화 후에야
측정된다.

```text
27개 사업군 전부 평가 · 신호 6건 (진입 검토 1 · 급락 5) · 제외 0건
```

**한 메시지 상한은 9종목**이다 — 구역 3개(보유/진입/회피) × 각 3종목. 위 목업이
6종목인 것은 그날 신호가 6건이었기 때문이고, 일반 상한과 다르다.

---

## 8. 변경된 파일

### 8-1. 신규 13건

| 줄 | 파일 | 내용 |
|---:|---|---|
| 468 | `app/runtime_evidence/intraday_alert_flow.py` | 조립 · 대체 조회 · 급등 억제 · 일일 상한 |
| 281 | `app/runtime_evidence/intraday_alert_render.py` | 본문 · 구역 상한 · 면책 문구 |
| 178 | `app/runtime_evidence/intraday_checkup_tally.py` | 회차 집계 (15:40 요약) |
| 408 | `app/runtime_evidence/sector_signal.py` | 사업군 판정 · 커버리지 Gate · provider 장애 구분 |
| 325 | `app/runtime_evidence/sector_signal_state.py` | 억제 · cooldown · 관측 저장 |
| 737 | `docs/ai_design/POC3/POC3-02C-OPS-02_INTRADAY_SURGE_DROP_ALERT_DESIGN_V1.md` | 설계서 보존본 (§15-2 는 설계자 확정 문구로 개정) |
| 309 | `docs/ai_plan/POC3/POC3-02C-OPS-02_INTRADAY_SURGE_DROP_ALERT_PLAN_V1.md` | 개발 PLAN |
| — | `docs/ai_result/POC3/POC3-02C-OPS-02_INTRADAY_SURGE_DROP_ALERT_RESULT.md` | 이 문서 (줄 수는 자기참조라 적지 않는다) |
| 175 | `tests/test_day_return_price_basis.py` | 37건 |
| 1212 | `tests/test_intraday_alert_flow_through.py` | 53건 |
| 481 | `tests/test_intraday_alert_integration.py` | 23건 |
| 467 | `tests/test_intraday_alert_render.py` | 34건 |
| 461 | `tests/test_sector_signal.py` | 41건 |

### 8-2. 수정 13건

| 줄 | 파일 | 내용 |
|---:|---|---|
| 286 | `app/intraday_config/schema.py` | 정책 키 6개 · 초기값 · 범위 검사 |
| 222 | `app/market_cache.py` | `day_return_pct` 필드 · `coerce_day_return` |
| 148 | `app/market_naver.py` | `fluctuationsRatio` 추출 |
| 426 | `app/runtime_evidence/holdings_risk.py` | 급등 3단계 · `usable_day_return` · 급등 선정 |
| 440 | `app/runtime_evidence/holdings_risk_flow.py` | **운영 배선** · 관측 저장 · 집계 기록 |
| 404 | `app/runtime_evidence/holdings_selection_flow.py` | **15:40 점검 요약 부착** |
| 267 | `app/three_push_runtime/runner_evidence.py` | **전송 성공 후 상태·집계 저장** |
| 142 | `app/three_push_runtime/target_tickers.py` | 보유 ∪ 대표 · 비활성 게이트 · 중복 제거 |
| 646 | `scripts/run_three_push_runtime_oci.py` | **3줄 교체** (설계자 §15-5 승인 예외) |
| 396 | `tests/conftest.py` | 장중 상태·집계 파일 격리 |
| 580 | `tests/test_holdings_risk_alert.py` | 38건 |
| 809 | `tests/test_holdings_risk_alert_runner.py` | 22건 |
| 340 | `tests/test_intraday_config_contracts.py` | 52건 |

> 줄 수는 **현재값**이다. 변경 목록은 `git diff --cached --name-status` 실측이다.

### 8-3. 기존 테스트 전환 (단언 무변경)

fixture 가 `(직전종가, 현재가)` 로 표현하던 **같은 사실**을 등락률로 옮겼다.
34건이 복구됐다. 교체한 것은 1건뿐이다 —
`test_denominator_is_previous_trading_day_close_not_today_open` 은 새 구조에서
**내 fixture 산술만 검사하는 공허한 테스트**가 되므로, 대신 "등락률과 현재가가
모순될 때 등락률을 따르는가"(역산 금지)를 검사한다.

### 8-4. 건드리지 않은 것

```text
scripts/run_three_push_runtime_oci.py   **줄 수 648 유지 · 내용 3줄 교체** (§15-1)
cron                                    무변경 (기존 7틱)
VALID_PUSH_KINDS                        무변경 (신규 종류 0)
spike_or_falling_alert                  부활 없음
정기 PUSH no_change 경로                무변경 (OPS-01 에서 종료)
```

---

## 9. 검증 실적

### 9-1. 실측값

```text
전체 회귀      1,904 passed / 0 failed / 0 errors
신규 계약      188 passed  (사업군 41 · 본문 34 · 통합 23 · 가격기준 37 · 관통 53)
무력화 실증    가격기준 5 · 격리 3 · 배선 3 · 재시도 3 · 상한 2 · D2 3 · D3 3 · 교차 3 — 전부 확인
black          361 files unchanged
flake8         0건
러너           646줄 (동결선 648 이하)
라이브 DB      회귀 전후 sha256 동일
Telegram / Naver 실호출  0건 (테스트 전부 대역)
OCI 쓰기       0건
```

### 9-2. KS-10 — 전수 484 · TRIGGER 0 · NEAR 7

측정 대상은 **git 추적 소스**(`git ls-files '*.py' '*.tsx' '*.ts'`, `node_modules`
제외)이고 임계는 분류별로 다르다 — 백엔드 650(NEAR 600) · 프론트 컴포넌트
900(NEAR 850) · 테스트 1500(NEAR 1450).

```text
855  frontend/app/components/JudgmentWorkbenchView.tsx
648  scripts/run_three_push_runtime_oci.py
641  app/api.py
638  scripts/ops02c/reverse_verify_guards.py
626  app/ml_score_validity_report.py
616  app/holdings_market_evidence.py
602  app/draft.py
```

**새로 NEAR 에 진입한 파일은 없다.** 이번 신규 5개는 전부 468줄 이하다
(`sector_signal` 408 · `intraday_alert_flow` 468 · `intraday_alert_render` 281 ·
`sector_signal_state` 325 · `intraday_checkup_tally` 178).

관통 테스트 파일은 1212줄이다 — 테스트 NEAR 임계 1450 에 못 미친다.

## 10. 신규 의존성

없음.

---

## 11. 지시문 외 변경

**1건.** `target_tickers` 장중 경로의 **다계좌 중복 제거**(§4). 설계 §2 "같은
ticker 는 한 번만" 을 지키기 위해서이며, `holdings_briefing` 기존 동작은
그대로 뒀다.

---

## 12. 알려진 한계 / 미완성

1. **무조정 이력이 24거래일뿐이다.** 20일 수익률에 21개가 필요해 여유가 3일이다.
   신규 상장 ETF 는 `short_history` 로 제외된다. OCI 07:20 배치가 매일 1일치를
   쌓으므로 시간이 지나면 해소된다.
2. **`enabled=true` PARAM 을 만들지 않았다.** 설계 §10-7 은 검증자 통과 뒤다.
   현재 비활성이라 사업군 조회가 0건이고, 통합 본문 경로는 **정책을 주입한
   테스트에서만** 실행된다.

## 13. 검증자에게 알릴 점

1. **운영 배선이 이번 라운드의 핵심**이다(§15-1). 실제 `run()` 경로 관통
   테스트로 고정했고(현재 건수는 머리말 `FLOW_THROUGH_TESTS`), 배선을 깨면
   잡히는 것을 실증했다.
2. **`enabled=false` 가 조회까지 막는다**(§15-2). 직전 제출에서는 비활성인데
   대표 27종목을 조회하고 있었다 — 설계자 지적으로 발견해 고쳤다.
3. **러너 648줄 동결 유지**. 3줄을 교체했고 추가는 0줄이다(§15-1 diff).
4. **가격 기준이 바뀌었다**(§3). 기존 급락 경로의 분모가 조정계열에서 무조정으로
   교체됐다. 전후 비교에서 **급락 판정 변경 0건**을 실측했다.
5. **기존 테스트 34건의 fixture 를 전환**했다(§8-3). 단언은 건드리지 않았다.
6. **면책 문구 충돌 1건은 설계자 확정으로 해소**됐다(§16-0 에 충돌 내용,
   §16-1 에 확정 반영). 자체 해석하지 않았고, 테스트가 확정 문구를 고정한다.
7. 구현 중 **죽은 분기 1건**(§2-2)과 **대역이 계약을 가린 테스트 1건**(§6)을
   스스로 발견해 고쳤다.
8. **설계서 §15-2 의 상태 저장 계약이 설계자 확정으로 정합화됐다**(§20·§21).
   계약은 "저장 여부" 가 아니라 **"전진 여부"** 로 표현한다 — 발송 진척
   상태(`last_sent_at`·`sent_today`)는 실패·부분 전송 시 전진하지 않고, 관측
   4종은 매 회차 저장이며, `fingerprint` 는 영속 상태가 아니다. 실행 코드
   변경은 없다(AST 동일).

## 14. 사용자 확인이 필요한 항목

1. **메시지 형식**(§7). 설계 §10-6 의 목업 확인 대상이다. 보유 급락·급등이
   한 구역에 들어가고, 진입 검토/회피가 별도 구역이다.
2. **발송량 전망** — 조건형 최대 4건이 고정 4건에 **더해진다**. 하루 최대 8건.
3. **커밋·푸시 미수행 · OCI 쓰기 0 · 발송 0.**
4. **설계자가 두 차례 모두 (a) 로 확정했다**(§20·§21). 설계서 §15-2 를 확정
   문구로 교체했고 실행 코드는 변경하지 않았다(AST 동일).

---

## 15. 설계자 §14 보완 결과 (2026-09-20)

### 15-1. 운영 배선 완료 (§14-2)

```text
cron(7틱) → run() → holdings_risk_alert → assemble_holdings_risk_push
  ├ 보유 급락 (기존 경로 · 먼저 끝난다)
  └ assemble_intraday_alert  ← 신규 배선
       ├ 보유 급등
       ├ 사업군 판정 (try/except 격리)
       └ 본문 조립 → 러너가 전송 → record_send_success 에서 상태 저장
```

**러너는 648줄 그대로**다. 배선은 전부 `holdings_risk_flow` 안에서 했고, 러너는
기존 3줄을 **교체**만 했다(추가 0줄).

```diff
- if risk_outcome is not None and risk_outcome.skip_reason:
-     # 신규·악화 없음 — 완화·해소·동일 구간은 발송하지 않는다.
+ if risk_outcome is not None and risk_outcome.skip_reason and not message_text:
+     # 신규·악화 없음. 단 장중 본문이 있으면 보낸다(OPS-02 사업군 단독 신호).
- holdings_selection_ctx = {"risk": risk_outcome}
+ holdings_selection_ctx = {"risk": risk_outcome, "intraday": _rasm.intraday}
```

> 세 번째 줄이 없으면 **보유 급락이 없는 날 사업군 신호가 통째로 묻힌다.**
> 기존 `skip_reason` 조기 반환이 먼저 걸리기 때문이다.

### 15-2. `enabled=false` 를 **조회까지** 차단 (§14-3)

지적이 정확했다. `_active_sectors()` 가 정책을 보지 않아 **비활성인데 대표
27종목을 조회**하고 있었다. 실측으로 확인하고 고쳤다.

| 상태 | 대표 조회 | 대체 조회 | 합집합 |
|---|---:|---:|---:|
| 비활성(현재) | **0건** | **0건** | 보유 29종목 |
| 활성 | 27건 | 실패 시만 1회 | 53종목 |

비활성 상태의 **기존 본문 형식도 그대로**다 — `[보유 급락 알림]` 이 나가고
`[장중 급등락]` 은 나오지 않는다(flow-through 실측).

### 15-3. 상대순위 최소 커버리지 Gate (§14-4)

```text
sector_min_coverage_pct = 80   (PARAM · 코드 상수 아님)
유효 대표 / 활성 사업군 >= 80% 일 때만 상대순위 판정
미달하면 사업군 구역 전체 생략 · 보유 경로는 계속
```

27개 중 3개만 조회돼도 그중 하나가 상위 20% 가 되던 왜곡을 막는다. 경계는
**하한 포함** — 정확히 80% 는 통과한다.

### 15-4. provider 장애 시 대체 연쇄 금지 (§14-5)

**조회 횟수를 직접 센다.** "대체를 안 쓴다" 를 결과로만 보면 안 쓰는지 못 찾는지
구분되지 않는다.

| 상황 | 대체 조회 |
|---|---:|
| ticker 1건 누락 | **1건** (그 사업군만) |
| primary 과반 실패 = provider 장애 | **0건** |
| 대체도 실패 | 재귀 없음 — 1건에서 멈춤 |

표본이 5개 미만이면 비율 판정을 하지 않는다. 사업군 1개짜리에서 그 하나가
실패하면 100% 실패가 되는데 그건 provider 장애가 아니다.

### 15-5. flow-through (§14-6)

**실제 `run()` 경로**다. 외부는 전부 대역이고 Telegram·Naver·OCI write 0건.

```text
비활성 → 대표 조회 0건 / 기존 본문 형식 / 상태 파일 미생성   3건
설정 누락·손상 → 기존 경로 유지                            2건
활성 + 신호 → 통합 본문 1건 / 합집합 조회                   2건
사업군 예외 → 보유 본문 유지                               1건
전송 성공 → sent_today=1 저장                             1건
전송 실패 → 발송 진척 미전진                               1건
일일 4건 도달 → 조건형 억제                                1건
외부 호출 0건                                             1건
```

무력화 실증 — 배선이 진짜인지 깨서 확인했다.

```text
비활성 게이트 제거      1 failed
러너 배선 제거          1 failed
전송 후 저장 제거       1 failed
```

### 15-6. 결과서 수치 정정 (§14-7)

| 지적 | 정정 |
|---|---|
| `black 359` vs `352` 불일치 | 최종 1회 실행값으로 통일 (현재 값은 머리말 `BLACK / FLAKE8` 한 곳에만 둔다) |
| NEAR 목록 미명시 | §9-2 에 7건 전수. **새로 진입한 파일은 없다** — 신규 최대 408줄 |
| 한 메시지 상한 | 구역 3개 × 3종목 = **이론상 최대 9종목**. 목업 6종목은 그날 신호 수다 |
| "알림 빈도 측정" | **"단일 시점 신호 재생"** 으로 정정 — 2026-09-16 한 날짜다 |

---

## 16-0. 설계자 판단이 필요했던 1건 — 면책 문구 충돌 (§16-1 에서 해소)

설계 §7 원문의 마지막 줄이 **기존 계약 2건과 충돌**했다. 자체 해석으로 문구를
바꾸거나 가드를 약화시키지 않고 분리해 보고했고, §16-1 에서 설계자가 확정했다.

```text
설계 §7 원문   "※ 자동 조건 감지이며 매수·매도 지시가 아닙니다."
```

| 충돌 | 내용 |
|---|---|
| ① `FORBIDDEN_PHRASES` | `"매도 지시"` 가 목록에 있다. **부정문인데도** 부분일치로 걸려 러너가 `forbidden_wording` 으로 **발송을 막았다**(flow-through 실측) |
| ② `holdings_risk_render` | **"면책문구·매매지시 문구 없음"** 을 명시한다(POC3-OPS-02A 확정) |

당시에는 기본값을 빈 문자열로 두어 기존 계약을 유지하고, 금지어를 피하는 문구로
확정받는 쪽(아래 (b))을 제안했다.

```text
(a) 면책 문구를 넣지 않는다 — 기존 OPS-02A 계약 유지
(b) 금지어를 피하는 문구로 확정
(c) FORBIDDEN_PHRASES 를 부정문 맥락에서 예외 처리 — 가드 약화 위험, 권하지 않음
```

설계자가 (b) 로 확정한 문구와 반영 결과는 §16-1 이다. 확정 문구가 가드를
통과함은 `test_disclaimer_passes_forbidden_phrase_guard` 가 고정한다.

---

## 16. 설계자 §15 보완 (2026-09-20 · 검증자 전달 전)

### 16-1. 면책 문구 확정 반영 (§15-1)

```text
※ 자동 감지 결과이며, 최종 판단은 사용자가 합니다.
```

`매수`·`매도`·`매매`·`지시` 를 **전부 피한다.** `FORBIDDEN_PHRASES` 는 **손대지
않았다** — 가드 완화 없이 문구만 바꿨다.

| 계약 | 테스트 |
|---|---|
| 확정 문구가 금지어를 통과 | `test_disclaimer_passes_forbidden_phrase_guard` |
| 4개 낱말을 피함 | `test_disclaimer_avoids_trade_words` |
| **가드가 약화되지 않음** | `test_forbidden_guard_is_not_weakened` |
| 신규 통합 메시지에만 | `test_unified_body_carries_disclaimer` |
| 기존 `[보유 급락 알림]` 에는 없음 | `test_legacy_body_has_no_disclaimer` |

무력화 실증 — 옛 문구로 되돌리면 **9건 실패**(관통 테스트 포함).

### 16-2. 관통 테스트 추가 (§15-2)

```text
test_partial_delivery_does_not_save_any_send_state   부분 전송 → 발송 진척 미전진
test_seven_ticks_feed_the_1540_summary               7틱 집계 → 요약 한 줄
test_tally_records_every_tick_even_without_send      미발송 회차도 집계
test_tally_failure_never_blocks_send                 집계 실패가 발송을 막지 않음
test_corrupt_tally_reports_unknown_not_zero          집계 불가 ≠ 0건
test_tally_from_another_day_is_unknown               날짜 경계
```

**회차 집계는 발송 상태와 별개 파일**이다. 발송 상태는 전송 성공 시에만 저장하는데
(§9), 집계는 **보내지 않은 회차도 세야** "신호 없음 N건" 이 나온다. 두 규칙이
정반대라 `intraday_checkup_tally_latest.json` 으로 분리했다. 집계가 깨져도 발송
판단은 영향받지 않는다 — 요약만 `확인 불가` 가 된다.

### 16-3. 커버리지 PARAM 계약 (§15-3)

`REQUIRED_POLICY_KEYS` 에 있었지만 **범위 검사가 없었다.** `POLICY_RANGES` 12쌍을
추가했다.

```text
키 누락        → ConfigSchemaError (기존)
비수치·bool    → ConfigSchemaError (신규)
범위 밖·NaN    → ConfigSchemaError (신규)
정확히 80%     → 통과 (하한·상한 포함)
```

범위 밖이 통과하면 `sector_min_coverage_pct = -1` 로 **Gate 가 무력화**된다.
검사를 빼면 **14건이 실패**한다(실증).

### 16-4. 테스트 격리 결함 1건 — 발견·수정

보완 중 전체 회귀가 **라이브 경로에 집계 파일을 만들었다.** 파일 내용을 확인했고
(7틱 · 당일 타임스탬프) 즉시 지운 뒤 `conftest` 격리에 두 경로를 추가했다.

```text
state/three_push/sector_signal_state_latest.json
state/three_push/intraday_checkup_tally_latest.json
```

이후 **전체 회귀 3회 연속 라이브 경로 무변경**이다.

> 다만 가드를 다시 빼도 **재현되지 않아** 어느 줄이 막는지는 단정하지 못한다.
> 그래서 감지(`names` — 변경 시 되돌리고 실패)와 격리(`setattr`)를 **둘 다** 뒀다.
> "가드가 막고 있다" 고 쓰지 않는다 — 실증하지 못한 주장이다.

### 16-5. 결과서 모순 정정 (§15-4)

| 지적 | 정정 |
|---|---|
| §8-4 runner "무변경" | **"줄 수 648 유지 · 내용 3줄 교체"** |
| "신규 파일 334줄 이하" | 실제 최대 **408줄** (`sector_signal`) |
| 목업 면책문구 | 확정 문구로 교체 |
| "면책문구가 목업에서 빠졌다" | 문장 삭제 |
| 배선 변경 파일 누락 | §8-2 를 **8건**으로 — `holdings_risk_flow` · `runner_evidence` · `run_three_push_runtime_oci` · `conftest` 추가 |
| `BLOCKING_ITEM` 참조 | §16 으로 정정 후 **NONE** |

### 16-6. 검증자가 독립 확인할 것 (§15-5)

```text
- 실제 diff 가 보고한 3줄과 일치      git diff scripts/run_three_push_runtime_oci.py
- 사업군 단독 신호가 skip_reason 에 묻히지 않음   3번째 줄이 그것을 막는다
- 비활성에서 대표 조회·신규 본문 0     관통 3건
- 발송 진척은 전송 성공 후에만 전진    관통 3건 (성공·실패·부분)
```

---

## 17. 검증자 REJECTED — 운영 계약 위반 7건 (2026-09-20)

**전부 인정한다.** 테스트 수치는 재현됐지만 **테스트가 잘못된 동작을 고정**하고
있었다. 아래는 건별 수정이다.

### 17-1. 지속 신호가 120분 뒤 재발송 (A-1 #1)

설계 §5 는 **"임계 밖으로 회복된 뒤 다시 진입하고 120분이 지남"** 인데 구현은
**경과 시간만** 봤다. 지속 중인 급락이 2시간마다 다시 나갔다.

```python
if prev.get("continuous"):
    out.suppressed.append(...)   # 시간이 아무리 지나도 재발송 안 함
    continue
last = _parse_kst(prev.get("last_sent_at"))   # 회복 후 재진입에서만 cooldown
```

`continuous` 는 `mark_absent_entries()` 가 내린다 — 이번 회차에 관측되지 않은
ticker 를 `False` 로 바꾼다. **기록 자체는 지우지 않는다**(지우면 재진입이
신규로 잡혀 cooldown 을 건너뛴다).

옛 테스트 `test_same_state_after_cooldown_is_sent` 가 **틀린 동작을 고정**하고
있었다. 계약대로 교체하고 5건을 추가했다.

### 17-2. 보유 급등이 억제 대상이 아니었음 (A-1 #2)

같은 급등이 유지돼도 **매 틱 재발송**됐다. 저장되는 상태가 사업군뿐이었다.

급등도 `compute_sector_changes` 를 탄다. `fingerprint` 가 `ticker#state` 라
`D*`(급락)·`U*`(급등)·사업군 상태가 서로 겹치지 않아 한 파일을 공유해도 섞이지
않는다. 저장은 `observed`(지속 갱신) + `sent_signals`(발송 시각) 두 축이다.

### 17-3. 대체 ETF 를 실제로 조회하지 않았음 (A-1 #3)

가장 뼈아픈 건이다. `collect_target_tickers` 는 보유+대표만 넣고 외부 조회는
**1회뿐**이라, `select_sector_signals` 가 `market_quotes` 에서 대체를 찾아도
**거기 있을 수가 없었다.** "대체를 쓸 수 있다" 고만 했지 실제로는 늘 실패했다.

`fetch_alternate_quotes()` 를 추가했다.

```text
대표 실패한 사업군의 대체만  → 한 번 조회
정상일 때                  → 0건 (정기 대상에 대체를 넣지 않는다)
provider 장애              → 0건 (fallback 연쇄 금지 · §14-5)
```

`fetch_many` 를 주입 가능하게 해 **조회 ticker 목록을 세는** 테스트 5건으로
고정했다.

### 17-4. 15:40 요약에 운영 소비자가 없었음 (A-1 #4)

`load_tally`/`render_summary_line` 을 **테스트가 직접 불러** 연결된 것처럼
검증했다. 운영 코드에는 호출자가 없었다.

`holdings_selection_flow` 의 본문 조립에 붙였다 — `slot_id == LAST_SLOT_ID`
(`CLOSE` = 15:40) 일 때만, 본문 말미에 한 줄. 별도 메시지를 만들지 않는다.
집계 실패는 삼키고 `확인 불가` 로 나간다.

### 17-5. `조회 실패 N회` 생산 경로가 없었음 (A-1 #5)

`OUTCOME_FAILED` 를 쓰는 곳이 테스트뿐이었다. 회차 집계가
`suppressed`/`no_signal` 만 적고 있었다.

```python
failed = bool(intraday.sector_error) or (
    intraday.sector.sector_count > 0 and not intraday.sector.coverage_ok
)
```

> 이 수정 중 **변수 섀도잉 1건**을 만들었다가 잡았다. tick 결과를 `outcome`
> 이라는 이름에 담아 바깥의 `HoldingsRiskOutcome` 을 덮었고,
> `'str' object has no attribute 'skip_reason'` 로 드러났다. `tick_outcome`
> 으로 바꿨다.

### 17-6. 구역 상한이 하위 유형마다 적용 (A-1 #6)

「보유종목」에 급락 3 + 급등 3 = **6개**, 「진입 회피」에 급락 3 + 추격 3 = 6개가
들어가 한 메시지 최대가 9가 아니라 **15**였다.

`fill()` 이 **구역 단위**로 `room = cap` 을 공유한다. §6 우선순위대로 채우고
넘치면 아래쪽부터 잘린다.

```text
보유종목 3 (급락 → 급등)  ·  진입 회피 3 (급락 → 추격)  ·  진입 검토 3  = 최대 9
```

### 17-7. 일일 상한이 보유 급락을 막지 않았음 (A-1 #7)

`holdings_risk_alert` **자체가 조건형 PUSH** 다. 통합 본문만 막고 기존 본문을
내보내면 하루 5건·6건이 나간다. 옛 테스트가 이 우회를 **정상으로 고정**했다.

상한 도달 시 `outcome.skip_reason = "intraday_daily_cap_reached"` 를 세워 러너의
**기존 skip 분기**를 타게 했다 — 러너는 여전히 648줄이다.

### 17-8. 무력화 실증

```text
① cooldown 의미 (continuous 무시)   1 failed
⑥ 구역 상한 (room 무한)             1 failed
⑦ 일일 상한 (분기 제거)             1 failed
③ 대체 조회 — 조회 ticker 목록으로 고정 (5건)
```

### 17-9. 결과서 A-2 정정

| 지적 | 정정 |
|---|---|
| 목업이 폐기된 면책 문구 사용 | 확정 문구로 교체 |
| "면책 문구 판단 대기" 가 한계로 남음 | 삭제 (§16-1 에서 확정됨) |
| `수정 8건` 인데 9행 | **9건** |
| KS-10 전수 484 vs 독립 485 | §9-2 를 **재측정 명령과 함께 484** 로 교체. 앞선 `485` 는 측정 대상을 명시하지 않은 채 독립 수치를 받아쓴 것이었다 — 수를 옮기지 말고 명령을 적는다 |
| 7틱 요약을 관통 완료로 보고 | §17-4 로 정정 — 운영 소비자를 이제 붙였다 |

---

## 18. 검증자 재REJECTED — ①·② 상태 저장 배선 (2026-09-20)

**인정한다.** ①·② 를 **단위 함수에서만** 고치고 실제 흐름에 연결하지 않았다.
직전 §17-1·17-2 의 서술은 코드보다 넓은 주장이었다.

### 18-1. 무엇이 빠져 있었나

```text
조립 단계   observed · sent_signals 를 만든다            ✅
저장 단계   여전히 intraday.changes.send 만 쓴다          ❌
미발송 회차 저장 함수가 아예 안 불린다 → continuous 영구 True  ❌
```

검증자 재현 그대로였다.

```text
saved_keys ['S1'] · surge_saved False
continuous_after_recovery_tick True
reentry_send [] · suppressed [('T1', 'AVOID_DROP')]
```

회복이 기록되지 않으니 재진입이 **오히려 계속 억제**됐다 — 고치려던 것과 반대
방향의 결함을 만든 셈이다.

### 18-2. 발송 상태와 관측 상태를 분리했다

설계 §9 의 "전송 성공 뒤에만 저장" 은 **발송 사실**을 뜻한다. 관측은 매 회차
갱신돼야 한다. 두 규칙이 정반대라 함수를 나눴다.

| 저장 대상 | 언제 | 함수 |
|---|---|---|
| `state` · `continuous` · `day_return_pct` | **매 회차** | `save_observation()` |
| `last_sent_at` · `sent_today` | **전송 성공 시에만** | `record_send_success()` |

`save_observation` 은 `last_sent_at` 을 건드리지 않는다 — 밀면 cooldown 이 영원히
끝나지 않는다.

### 18-3. 저장 경로가 급등을 포함한다

```python
sent = list(getattr(intraday, "sent_signals", None) or [])      # 사업군 + 급등
observed = list(getattr(intraday, "observed", None) or [])
merge_sector_entries(sent=sent, previous=previous, now_kst=now, observed=observed)
```

### 18-4. registry 중복키를 잘못 이해하고 있었다

재진입 테스트가 `duplicate_runtime` 으로 막혀 원인을 팠더니,
`holdings_risk_alert` 의 중복키는 **실행 시각 `HH:MM`** 이었다(7틱 · 악화 시
재발송 계약). 같은 분에 세 번 돌린 내 테스트가 잘못이었다 — 운영의
09:30/10:30/11:30 처럼 틱마다 시각을 옮겼다.

### 18-5. 검증자 재현 시나리오를 그대로 고정

```text
test_surge_is_saved_to_state_after_send          급등이 상태에 남는다
test_saved_entries_are_not_empty_after_send      entries 실제 검사 (B-6)
test_missed_tick_records_recovery                미발송 회차 → continuous False
test_observation_save_does_not_touch_last_sent_at  관측이 발송 시각을 밀지 않는다
test_suppressed_signal_is_not_marked_recovered   관측 중인 억제 신호 보존
test_recovery_then_reentry_sends_again           회복 → 재진입 → 발송
test_continuous_signal_is_not_resent_across_ticks  지속 중이면 180분 뒤에도 미발송
```

무력화 실증 — 배선을 빼면 잡힌다.

```text
매 틱 관측 저장 제거          2 failed
sent_signals → changes.send  1 failed
```

### 18-6. B-6 테스트 결함 3건 수정

| 지적 | 수정 |
|---|---|
| 전송 성공 테스트가 `entries` 미검사 | `test_saved_entries_are_not_empty_after_send` |
| 회복 테스트가 상태 함수 직접 호출 | `run()` 을 3회 통과시킨다 |
| `assert rec.get("partial_delivery") or True` — **항상 참** | 삭제. `sent_today == 0` · `last_sent_at` 부재로 검사 |

### 18-7. A-2 보고 정확성 정정

| 지적 | 정정 |
|---|---|
| "`observed + sent_signals` 저장" 주장에 소비자 없음 | §18-2·18-3 으로 **실제 연결** |
| 변경 목록 `수정 9건` vs Git 실측 | §8 을 `git diff --cached` 실측으로 재작성 |
| `23 passed (실제 run() 경로)` | `run()` 호출 건수와 소스검사 건수를 **구분 표기** |

---

## 19. 검증자 재REJECTED — 실패한 신호가 영영 안 나감 (2026-09-20)

### 19-1. 결함

`save_observation()` 은 **Telegram 결과가 나오기 전에** 돌아 `continuous=True` 를
남긴다 — 회복 판정에 필요해서다. 그런데 억제 판정이 `continuous` 를 **먼저**
봤다. 그래서 **한 번도 나간 적 없는 신호**(전송 실패·부분 전송)가 다음 틱에서
"지속 중" 으로 억제됐다. 회복 전까지 영영 안 나간다.

검증자 독립 재현:

```text
저장 상태   continuous=True · last_sent_at=None · sent_today=0
다음 틱     next_send=[] · next_suppressed=[('T1','AVOID_DROP')]
```

### 19-2. 수정 — 판정 순서를 뒤집었다

`app/runtime_evidence/sector_signal_state.py` `compute_sector_changes()`.
**`last_sent_at` 을 먼저 본다.** 보낸 적이 없으면 억제할 근거가 없다.

```text
last_sent_at 없음        → 발송        (관측만으로는 절대 억제하지 않는다)
있음 + continuous        → 억제
있음 + 회복 + cooldown↑  → 발송
있음 + 회복 + cooldown↓  → 억제
```

4가지 전이 모두 실측으로 확인했다.

### 19-3. 관통 테스트 3건 추가 (§18-6 지적 마감)

직전 테스트는 "발송 완료 표식이 없다" 만 봤다. 정작 중요한 **"실패한 신호가
다음 틱에 다시 나가는가"** 를 검사하지 않았다.

| 테스트 | 계약 |
|---|---|
| `test_failed_send_is_retried_on_next_tick` | 전송 실패 → 다음 틱 `status=sent` |
| `test_partial_delivery_is_retried_on_next_tick` | 부분 전송 → 다음 틱 `last_sent_at` 기록 |
| `test_observation_alone_never_suppresses` | `continuous=True` 단독으로는 억제 안 됨 |
| `test_suppression_table_is_complete` | 억제 계약 **7셀 전수** (아래 표) |

두 관통 테스트는 틱마다 시각을 옮긴다(`_tick_at`) — `holdings_risk_alert` 의
registry 중복키가 실행 시각 `HH:MM` 이라 같은 분에 두 번 돌리면 `duplicate_runtime`
으로 막혀 **재시도 여부를 검사할 수 없다**(§18-4).

무력화 실증 — 판정 순서를 되돌리면:

```text
test_failed_send_is_retried_on_next_tick          1 failed
test_partial_delivery_is_retried_on_next_tick     1 failed
test_observation_alone_never_suppresses           1 failed
```

### 19-4. A-2 보고 정확성 정정

| 지적 | 정정 |
|---|---|
| 머리말 `SEND_FAILURE_STATE_SAVE = 없음 (상태 파일 미생성)` | 당시 "발송 상태 미저장 · 관측 상태는 매 틱 저장" 으로 교체 → §21 에서 **"발송 진척 미전진"** 으로 최종 |
| `전송 실패 → 상태 미저장` | → 최종 `전송 실패 → 발송 진척 미전진` (§21) |
| `부분 전송 → 전부 미저장` | → 최종 `부분 전송 → 발송 진척 미전진` (§21) |
| flow-through 건수 | 재측정 값으로 교체 |

`비활성 → 상태 파일 미생성` 은 정정 대상이 아니다 — 비활성이면 관측 자체를
안 하므로 파일이 실제로 안 생긴다(`test_disabled_policy_writes_no_sector_state`).

### 19-5. 억제 계약을 표 전체로 고정했다

셀 하나씩 테스트를 쓰면 빠진 칸이 생긴다 — 이번을 포함해 반려가 난 자리가 늘
**"고친 것의 옆칸"** 이었다. 그래서 상태 × 전이를 **표로 전수** 고정했다
(`test_suppression_table_is_complete`, 7셀 파라미터).

| 이전 상태 | 판정 | 근거 |
|---|---|---|
| prev 없음 (신규 종목) | **발송** | 억제할 이력이 없다 |
| `last_sent_at` 없음 · `continuous=False` | **발송** | 신규 진입 |
| `last_sent_at` 없음 · `continuous=True` | **발송** | **전송 실패 — 이번 결함** |
| `last_sent_at` 있음 · `continuous=True` | 억제 | 지속 중 |
| `last_sent_at` 있음 · 회복 · cooldown 경과 | **발송** | 재진입 |
| `last_sent_at` 있음 · 회복 · cooldown 이내 | 억제 | 너무 잦다 |
| `last_sent_at` 손상값 · `continuous=True` | **발송** | 파싱 실패는 **열림** 으로 — 손상된 타임스탬프 때문에 알림이 영영 막히면 안 된다 |

판정 순서를 되돌리면 이 표에서 **2셀이 실패**한다(실패·손상값). 나머지 5셀은
옛 코드에서도 통과했다 — **그래서 셀 단위 테스트만으로는 못 잡았다.**

---

## 20. 설계서 §15-2 계약 정합화 (설계자 확정 · OPTION_A)

```text
DESIGNER_DECISION                   = OPTION_A_APPROVED (1차 · §21 에서 OPTION_A_FOR_BOTH 로 최종)
PARTIAL_DELIVERY_OBSERVATION_SAVE   = APPROVED
CODE_CHANGE_REQUIRED                = NO
DESIGN_DOCUMENT_UPDATE              = DONE (문구 2건은 §21 로 최종 확정)
VERIFIER_RECHECK_SCOPE              = DOCUMENT_AND_CONTRACT_ONLY
```

### 20-1. 무엇이 달랐나

설계서 §15-2 는 부분 전송 시 `sent_today·fingerprint·entries 미저장` 을
요구했으나, 구현은 `sent_today` 를 전진시키지 않고(키는 `0` 으로 존재) ·
`fingerprint` 는 저장 필드가 아니며 · **`entries` 는 저장**했다. 부분 전송 직후
상태 파일 실측:

```text
최상위 키      date_kst · entries · schema_version · sent_today
entries[T1]   continuous · day_return_pct · sector_key · state
sent_today    0
fingerprint   없음
```

즉 **발송 상태(`last_sent_at`·`sent_today`)는 전진하지 않고**, `entries` 안의
**관측 4종**만 저장된다. (`fingerprint` 는 이 파일의 저장 필드가 아니다 — §21-2)

`continuous`(관측 상태)는 설계서에 없던 개념이다 — 설계 원문에
`continuous`·`관측 저장` 은 0건이었다. 검증자 §18 라운드가 "회복 판정이
불가능하다", §19 라운드가 "미발송 신호가 영구 억제된다" 고 지적해 도입됐고,
저장 시점(매 틱)과 판정 순서(`last_sent_at` 우선)가 확정됐다.

### 20-2. 설계자 확정 — OPTION_A

> 관측 상태와 발송 상태는 목적이 다르다. 별도 파일로 분리하면 파일 간
> 원자성·정합성 문제만 하나 더 생긴다. 한 파일 안에서 필드와 저장 시점을
> 분리한 현재 구현이 더 단순하고 정확하다.

**부분 전송을 성공으로 치는 것이 아니다.** 발송 진척(`sent_today`·`last_sent_at`)은
전진하지 않고 관측한 사실만 남긴다(`sent_today=0` 은 카운터 초기값 — §21-1).
따라서 실패한 신호가 다음 틱에 재시도되는 현재 구현과 정확히 맞는다.

### 20-3. 반영 내역

| 대상 | 조치 |
|---|---|
| 설계서 §15-2 | 부분 전송 줄을 `발송 진척 상태 2종 미전진 · 관측 entries 는 저장` 으로 교체하고, **상태 저장 계약 5항**을 본문으로 추가(§21 확정 문구 반영) |
| 결과서 머리말 | §21 확정 토큰 5줄 (`DELIVERY_PROGRESS…=NOT_ADVANCED` · `SENT_TODAY…=NOT_INCREMENTED` · `LAST_SENT_AT…=NOT_CREATED_OR_ADVANCED` · `OBSERVATION_ENTRIES…=SAVED` · `FINGERPRINT_PERSISTENCE=NONE`) |
| 코드 · 테스트 | **변경 없음** |

§15-2 의 두 번째 요구(`실제 7틱 집계 → 15:40 점검 요약`)는 **그대로 남겼다.**
확정 문구가 상태 저장 계약만 다루므로, 절 전체를 갈아끼우면 이미 구현·검증된
관통 테스트 요구가 사라진다.

### 20-4. 계약과 코드의 대조

설계자 확정 5항을 현재 코드·테스트와 1:1로 확인했다.

| 확정 문구 | 코드·테스트 |
|---|---|
| 1. 관측 4종을 평가 회차마다 저장 | `holdings_risk_flow` 가 `intraday_policy_enabled` 일 때 매 회차 `save_observation()` 호출 |
| 2. 발송 진척 상태(`last_sent_at`·`sent_today`)는 전체 전송 성공 시에만 전진 — `fingerprint` 는 영속 필드가 아님 | `_save_intraday_state_after_send()` — `partial_delivery` 면 그 앞에서 `return`, 전송 성공 경로에서만 도달 |
| 3. 실패·부분 전송 → 관측 저장 · 발송 진척 미전진(`sent_today` 는 0 으로 존재 가능, `last_sent_at` 미생성) | `test_failed_send_is_retried_on_next_tick` · `test_partial_delivery_is_retried_on_next_tick` |
| 3. 이전 성공 기록을 실패 시각으로 밀지 않음 | `test_observation_save_does_not_touch_last_sent_at` |
| 3. 미성공 신호는 다음 틱 발송 대상 | 억제표 `last=None` 3셀 전부 **발송** |
| 4. 파일 존재 ≠ 발송 성공 | 억제 판정은 ticker·state·continuous·last_sent_at·sent_today 로 하되, `last_sent_at` 이 없으면 나머지와 무관하게 발송 |
| 5. 비활성 → 신규 상태 파일 미생성 | 위 1번 게이트가 관측 자체를 막는다 · `test_disabled_policy_writes_no_sector_state` |

---

## 21. 확정 문구 정정 2건 (설계자 확정 · OPTION_A_FOR_BOTH)

```text
DESIGNER_DECISION                    = OPTION_A_FOR_BOTH
DELIVERY_PROGRESS_ON_FAILURE_PARTIAL = NOT_ADVANCED
OBSERVATION_ENTRIES_EVERY_TICK       = SAVED
FINGERPRINT_PERSISTENCE              = NONE
CODE_CHANGE_REQUIRED                 = NO  (문구 정합화 자체는 코드 변경 0 · D1 수정은 §22-1)
BLOCKING_ITEM                        = NONE_AFTER_DOC_SYNC → 문서 반영 완료 · NONE
VERIFIER_RECHECK_SCOPE               = DOCUMENT_AND_CONTRACT_ONLY (+ §22-1 한 함수)
```

§20 의 OPTION_A 방향은 유지되고 **동작 결함은 없다.** 확정 문구의 두 표현이
실측 형상과 어긋나 설계자가 문구를 다시 확정했다. 핵심은 계약을 **"저장 여부"
가 아니라 "전진 여부"** 로 표현하는 것이다.

### 21-1. `NOT_CREATED` → `NOT_ADVANCED` — `sent_today: 0` 은 카운터 초기값

실측(관측 저장 직후):

```text
저장 전        파일 없음
관측 저장 후    파일 존재
최상위 키      date_kst · entries · schema_version · sent_today
sent_today    0
entries[T1]   continuous · day_return_pct · sector_key · state
```

`sent_today` 키는 **생성된다.** 값이 `0` 이라 발송 성공으로 전진하지 않을 뿐이다.
`last_sent_at` 은 생성되지 않는다.

**설계자 확정**: `sent_today=0` 은 "발송 성공 표식" 이 아니라 **카운터의
초기값**이다. 실패·부분 전송 시 `sent_today` 는 증가시키지 않고 직전 값을
유지하며, `last_sent_at` 은 생성·갱신하지 않는다. 상태 파일이나 `sent_today`
키의 존재는 발송 성공의 증거가 아니고, **발송 성공은 `sent_today` 증가와 해당
신호의 `last_sent_at` 갱신으로 판정**한다.

`DESIGNER_APPROVED_OPTION_A` — 종결.

### 21-2. `fingerprint` — 영속 발송 상태에서 제외

실측(전송 성공 후):

```text
최상위 키      date_kst · entries · schema_version · sent_today
entries[T1]   continuous · day_return_pct · last_sent_at · sector_key · state
fingerprint   문자열 자체가 파일에 없음
```

`fingerprint` 는 신호 객체의 **파생 속성**(`SectorSignal.fingerprint = ticker#state`)
이고, registry 중복키에 쓰는 분기는 `spike_or_falling_alert` 전용이다.
`holdings_risk_alert` 는 `runner_evidence` 의 `else` 분기로 가며 중복키는 실행
시각 `HH:MM` 이다(§18-4).

**설계자 확정**: 이 경로의 영속 발송 상태는 `last_sent_at` 과 `sent_today` 다.
`fingerprint` 는 저장 필드가 아니며, 실패·부분 전송 계약에서 완료 기준으로 쓰지
않고, 기존 상태 파일에 필드를 추가하지도 않는다. 억제 판정은 `ticker · state ·
continuous · last_sent_at · sent_today` 로 한다.

`DESIGNER_APPROVED_OPTION_A` — 종결.

### 21-3. 반영 내역

| 대상 | 조치 |
|---|---|
| 설계서 §15-2 | 2·3·4항을 확정 문구로 교체. 1항(관측 상태)·5항(비활성) 은 철회되지 않아 유지 |
| 결과서 머리말 | 확정 토큰 5줄 · `BLOCKING_ITEM = NONE` |
| 결과서 §20-3 | `발송 상태 3종 미저장` → `발송 진척 상태 2종 미전진` |
| 코드 주석 · docstring | 앞 라운드 6곳 + 독립 감사에서 찾은 11곳 정정 (§22-4 · 실행 코드 AST 동일) |
| 실행 코드 · 테스트 단언 | **변경 없음** |

### 21-4. 확정 계약 ↔ 코드 대조

| 확정 문구 | 코드·테스트 |
|---|---|
| 관측 회차에서 파일·`sent_today` 키 생성 가능, 초기값 0 | `save_observation()` 이 `sent_today` 를 기존값(없으면 0) 으로 씀 |
| 실패·부분 → `sent_today` 미증가 | `_save_intraday_state_after_send()` 는 `partial_delivery` 면 그 앞에서 `return` |
| 실패·부분 → `last_sent_at` 미생성·미갱신 | `save_observation()` 은 `last_sent_at` 을 쓰지 않음 · `test_observation_save_does_not_touch_last_sent_at` |
| 관측 entries 는 갱신 | `test_failed_send_is_retried_on_next_tick` · `test_partial_delivery_is_retried_on_next_tick` |
| 파일·키 존재 ≠ 발송 성공 | 억제 판정은 ticker·state·continuous·last_sent_at·sent_today 로 하되, `last_sent_at` 이 없으면 나머지와 무관하게 발송 — 억제표 `last=None` 3셀 전부 **발송** |
| `fingerprint` 비영속 · 중복키는 `HH:MM` | 상태 파일에 필드 없음(실측) · `resolve_duplicate_slot` 이 `holdings_risk_alert` 에 `HH:MM` 반환 |

---

## 22. 독립 감사 — 동작 결함 1건 수정 · 계약 공백 2건 회부 · stale 정정

검증자에게 넘기기 전에 **독립 검증자 6명이 서로 다른 렌즈**로 결과서·설계서·
코드 주석을 읽었다(설계서↔코드 · 결과서↔설계서 · 결과서 내부 stale · 수치 재측정
· 코드 주석 · 다른 문서). 발견 55건 중 **동작 결함 1건(D1)** 을 고쳤고, 계약에
정의가 없는 **2건(D2·D3)** 은 설계자에게 올리며, 나머지는 문구 정정이다.

### 22-1. D1 — 구역 상한에 잘린 신호에 `last_sent_at` 이 찍혔다 (수정)

`sent_signals` 를 **구역 상한을 적용하기 전에** 확정했다. 한 구역에 4개 이상이
오면 `build_section_plan` 이 3개만 싣고 나머지를 `dropped` 로 보내는데, 발송
목록에는 그대로 남아 러너가 `last_sent_at` 을 찍었다. 다음 틱에 그 신호는
"보낸 적 있음 + 지속 중" 으로 억제되고 — **지속되는 동안 한 번도 나가지 못한다.**
§19 에서 고친 "미발송 신호 영구 억제" 와 같은 부류이며, 설계 §15-2 4항(발송
성공은 **해당 신호의** `last_sent_at` 갱신으로 판정)에 정면으로 어긋난다.

수정 — `app/runtime_evidence/intraday_alert_flow.py` `assemble_intraday_alert()`.
발송 목록을 상한 적용 **뒤에**, 본문에 실제로 실리는 것(`plan.avoid_drop ·
avoid_chase · entry · held_surge`)으로만 확정한다. 잘린 신호는 §6 대로 `dropped`
이력에만 남고 관측 상태(`continuous`)는 그대로 저장된다. 일일 상한·신호 없음
경로에서는 발송 목록이 비어 있다(본문이 없으니 발송도 없다).

관통 테스트 2건(`run()` 경로). `AVOID_DROP` 은 하위 20% 순위 조건이 있어 10개 중
2개만 되므로, 순위 조건이 없는 `AVOID_CHASE`(≥ +4.0%) 로 한 구역에 10개를 넣었다.

| 테스트 | 계약 |
|---|---|
| `test_signals_dropped_by_section_cap_get_no_last_sent_at` | 10개 중 실린 3개만 `last_sent_at` · 관측은 10개 전부 · 잘린 것은 본문에 없음 |
| `test_signal_dropped_by_cap_is_sent_when_room_opens` | 틱 2 에서 앞선 3개가 회복되면 잘렸던 신호가 **cooldown 안에도 나간다** (보낸 적이 없으므로) |

무력화 실증 — 수정을 되돌리면 2건 실패, 복원하면 2건 통과.

**설계자 `CODE_CHANGE_REQUIRED = NO` 와의 관계**: 그 지시는 §21 문구 정합화에
대한 것이다. D1 은 감사에서 새로 찾은 계약 위반이라 알고도 두지 않았다. 실행
코드 변경은 이 한 함수뿐이며(다른 파일은 AST 동일), 전체 회귀를 다시 돌렸다
(머리말 `BACKEND_FULL_REGRESSION`).

### 22-2. D2 — 평가 불가 회차가 "회복" 으로 기록된다 (설계자 확정 필요)

`mark_absent_entries()` 는 이번 회차에 관측되지 않은 ticker 의 `continuous` 를
내린다 — 회복 판정의 근거다. 그런데 **사업군 평가 자체가 불가능한 회차**
(provider 장애 · 커버리지 미달 · 사업군 예외)에도 관측 목록의 사업군 부분이 빈
채로 저장돼, 지속 중인 신호가 전부 "회복" 으로 기록된다. 이후 같은 신호가 다시
관측되면 "회복 후 재진입" 분기로 가서 cooldown 경과 시 **지속 신호를 재발송**한다
(설계 §5 "같은 상태가 계속 유지 → 발송하지 않음" 과 어긋남). 독립 재현:

```text
09:30 T1 AVOID_CHASE 발송 (last_sent_at 09:30 · continuous=True)
10:30 provider 장애 → 관측 목록 사업군 0건 → T1.continuous=False
12:30 T1 같은 신호 → send=['T1']   (대조군: 10:30 정상 관측이면 suppressed)
```

§15-2 는 "활성 정책의 평가 회차마다 저장" 이라 하지만 **평가가 불가능한 회차**를
관측으로 칠지 정의가 없다. 코드로 정하지 않고 올린다.

```text
제안  평가 불가 회차(sector_error · provider_down · coverage_ok=False)에는
      사업군 entries 의 continuous 를 내리지 않는다 (보유 급등 관측은 그대로).
      §15-2 1항에 "평가 불가 회차는 관측으로 취급하지 않는다" 한 줄.
영향  intraday_alert_flow 또는 holdings_risk_flow 한 곳 · 관통 테스트 1~2건.
```

### 22-3. D3 — dry-run · flag-off · 중복 회차도 관측·집계를 기록한다 (설계자 확정 필요)

관측 저장(`save_observation`)과 회차 집계(`record_tick`)는 조립 단계에서 돌고,
러너의 dry-run 종료 · `PUSH_AUTOSEND_*` 게이트 · 중복 실행 게이트는 그 **뒤**에
있다. 따라서 `--mode dry-run`(검증/메시지 생성만) · flag-off skip · duplicate skip
회차에도 `sector_signal_state_latest.json` 과 `intraday_checkup_tally_latest.json`
이 쓰인다. OPS-01A 는 선정 상태 저장을 flag 게이트 뒤에 둔 것과 대조된다.
반대로 정책 키 누락 시 처리가 비대칭이다 — `cooldown_minutes` 누락은 예외로
아무것도 안 쓰고, `sector_min_coverage_pct` 누락은 격리돼 빈 관측을 쓴다.

```text
제안  "평가 회차" 를 send 모드 + 정책 활성 + 사업군 조립 무예외로 정의하고,
      dry-run·flag-off·duplicate 회차에는 관측·집계를 쓰지 않는다.
영향  러너(648줄 동결)에 mode/flag 를 조립으로 넘기는 인자 추가가 필요할 수
      있어 설계자 승인 없이는 손대지 않는다.
```

### 22-4. stale 정정

결과서 16곳 · 설계서 §15-2 우선순위 주석 1곳 · 코드 주석/docstring 11곳
(§21-3 표). 실행 코드 변경은 §22-1 한 함수뿐이다(나머지 파일 AST 동일).

주요 정정: 머리말 `SEND_SUCCESS_STATE_SAVE` 의 "entries 갱신 (전송 성공 뒤에만)"
(관측 entries 는 매 회차) · §20-1 "sent_today 는 저장하지 않으면서"(키는 0 으로
존재) · §20-2 "발송 성공 표식은 0"(카운터 초기값 — §21-1) · §20-4/§21-4 "억제
판정이 last_sent_at 으로만"(5개 정보로 하되 last_sent_at 없으면 발송) · §16-0 의
설계 §7 인용이 원문이 아닌 확정 문구였던 것 · §13-1 관통 건수 stale · §2-3 정책
키 5→6 · 모듈 docstring "상태 저장은 여기서 하지 않는다"(관측은 여기서) ·
`save_sector_state` docstring "성공 뒤에만 호출"(관측 경로도 호출) ·
`merge_sector_entries` "보낸 것만 갱신"(관측 전부 갱신 + 보낸 것만 `last_sent_at`).

### 22-5. 설계서 §15-2 밖의 옛 문구 (설계자 확인 필요 · 수정하지 않음)

§15-2 가 확정되기 전 문구가 같은 설계서에 남아 자기모순이다. 설계자 문서라 본문은
건드리지 않고, §15-2 첫머리에 **"상태 저장은 이 절이 정본"** 이라는 우선순위
주석만 넣었다.

| 위치 | 문구 |
|---|---|
| §9 실패 격리 | "Telegram 전송 성공 뒤에만 suppression state 저장" |
| §14-2 연결할 것 | "성공 발송 후에만 fingerprint·cooldown·일일 발송 수 저장" · "실패·부분 전송 시 발송 상태 미저장" |
| §14-6 5·6번 | "전송 성공 → 상태·일일 발송 수 1회 저장" · "전송 실패·부분 전송 → 발송 상태 미저장" |
| §15-5 검증자 확인 항목 | "전송 성공 후에만 상태 저장" — **검증자가 이 줄대로 확인하면 §15-2 와 충돌한다** |
| 머리말 | `CURRENT_ACTION = PLAN_V1` (검증 단계인데 PLAN 시점) |

### 22-6. 감사 방법과 한계

검증자 6명은 완주했으나, 발견 건마다 붙인 반박자 3명은 세션 한도로 171명 중
154명이 실패해 **4건만 반박 판정을 받았다**(black 값 · 관통 12건 · 통합 17건 ·
모듈 docstring). 나머지 51건은 개발자가 발견 원문의 인용을 파일에서 다시 열고
실행으로 재현해 직접 판정했다 — D1·D2·D3 는 코드 읽기와 실행으로 확인했고,
문구 건은 원문 위치를 grep 으로 확인했다. 반박에서 기각된 1건(§6 "가드 있을 때
17 passed" — 과거 실험 기록)은 그대로 두었다.

### 22-7. 챕터 종료 시 남는 일

`docs/PROGRAM_TRUTH.md` 와 `docs/STATE_LATEST.md` 에 OPS-02(장중 급등락 통합
본문 · 관측/집계 상태 파일 · 15:40 점검 요약 · 일일 상한 · 정책 `enabled`)가
**없다.** 정책이 `enabled=false` 라 "지금 실제 동작" 은 아직 바뀌지 않았지만,
`enabled=true` PARAM 을 만드는 시점에 함께 갱신해야 한다.

---

## 23. D2 · D3 구현 (설계자 확정 · 검증자 P1 2건)

검증자가 D2·D3 을 **실제 실행 결함**으로 재현했고(§22 에서 내가 "계약 공백" 으로
분류한 것이 틀렸다), 설계자가 `D2_UNEVALUABLE_OBSERVATION = APPROVED_WITH_TRI_STATE` ·
`D3_DRYRUN_FLAG_DUPLICATE_WRITE = PROHIBITED` · `CODE_CHANGE_REQUIRED = YES` 로
확정했다. 둘 다 구현했다.

```text
DESIGNER_DECISION      = OPTION_A_FOR_BOTH (§21) · D2 TRI_STATE · D3 PROHIBITED
RUNNER_LINES           = 646  (동결선 648 이하)
PLAN_RESUBMISSION      = NO   (설계자 지시)
COMMIT_PUSH_OCI_SEND   = 0 / 0 / 0
```

### 23-1. D2 — 관측을 3상태로

`mark_absent_entries()` 가 "관측 안 됨 = 회복" 으로 2분했다. 그래서 provider 장애·
커버리지 미달 회차에 지속 신호가 전부 회복으로 기록되고, cooldown 뒤 **재발송**됐다.

```text
SIGNAL_PRESENT    조건 충족          → continuous=True
SIGNAL_ABSENT     정상 평가 후 미충족 → continuous=False
UNEVALUABLE       평가 불가          → 기존 state·continuous·day_return_pct·
                                      last_sent_at 을 그대로 둔다
```

`unevaluable` 집합을 조립이 계산해 상태 계층으로 넘긴다
(`app/runtime_evidence/intraday_alert_flow.py` `_unevaluable_tickers()`).
**범위를 분리**한다 — 사업군이 통째로 무너져도 정상 평가된 보유는 갱신한다.

| 상황 | 보존 범위 |
|---|---|
| `sector_error` · `provider_down` · `coverage_ok=False` | 이전 기록 중 **사업군** entry 전체 (`sector_key != "보유"`) |
| 대표·대체 모두 등락률 없음 (`no_quote` · `no_day_return`) | 그 ticker 만 |
| 대표가 보유 종목이라 사업군 판정에서 제외 (`held`) | 그 ticker 만 |
| 보유 ticker 의 `usable_day_return` 이 `None` | 그 보유 entry 만 |

`short_history` 는 **보존하지 않는다.** 당일 등락률은 쓸 수 있었고 진입 분기만
미정이므로 급락·추격 조건은 정상 평가된 것이다 — 회복 기록이 맞다.

평가 불가 회차도 정상 스케줄의 운영 회차이므로 **집계에는 `조회 실패` 1회**로
남는다. `provider_down` 을 실패 판정에 더했다(전에는 커버리지가 살아 있으면
`신호 없음` 으로 셌다).

### 23-2. D3 — 실행 회차와 기록 회차 분리

관측·집계 쓰기가 조립 단계에 있어서 러너의 dry-run 종료(§5) · flag guard(§6) ·
duplicate guard(§7)보다 **앞**이었다. dry-run 만 돌려도 라이브 파일이 바뀌고,
중복 실행이 "장중 점검 N회" 를 두 번 셌다.

조립은 이제 **쓰지 않고 의도만 담는다**(`RiskAssembly.intraday_records`).
러너가 Gate 를 통과한 뒤 `apply_intraday_records()` 가 실제로 쓴다.

```text
mode = send  AND  정책 enabled  AND  PUSH_AUTOSEND_*  AND  duplicate 아님
```

러너 훅은 `_finish()` **한 곳**이다. 모든 종료 지점이 거기를 지나므로 분기마다
호출을 넣지 않아도 되고, `status`·`reason` 으로 Gate 를 판정할 수 있다.
pending 은 `record[PENDING_KEY]` 로 실어 보내고 `apply_intraday_records()` 가
**직렬화 전에 꺼내 지운다** — 경로·set 이 섞여 있어 history JSONL 로 나가면 안 된다.

**러너 646줄** (동결선 648 이하). 순증 4 · 순감 6. 줄을 벌기 위해
`holdings_risk_flow` import 를 모듈 별칭(`_hrf`)으로 바꿨고 — 파일이 이미
`_mb`(market briefing)에 쓰는 방식이다 — 완전히 중복된 주석 2줄을 지웠다.

### 23-3. 설계자 지정 필수 관통 검증 9건

전부 실제 `run()` 경로다.

| 테스트 | 계약 |
|---|---|
| `test_provider_down_tick_does_not_count_as_recovery` | 정상 → provider 장애 → 복귀: 재발송 없음 |
| `test_low_coverage_tick_does_not_count_as_recovery` | 정상 → 커버리지 미달 → 복귀: 재발송 없음 |
| `test_single_unevaluable_ticker_preserves_only_that_entry` | 그 ticker 만 보존 · 나머지는 회복 기록 |
| `test_held_surge_updates_even_when_sector_path_is_down` | 사업군 장애 중 보유 급등 관측은 갱신 |
| `test_provider_down_is_counted_as_lookup_failure` | 집계 `조회 실패` 1회 |
| `test_dry_run_does_not_touch_live_files` | 두 파일 sha256 동일 |
| `test_flag_off_does_not_touch_live_files` | 두 파일 sha256 동일 |
| `test_duplicate_tick_does_not_touch_live_files` | 두 파일 sha256 동일 |
| `test_signals_dropped_by_section_cap_get_no_last_sent_at` (§22-1) | D1 상한 제외 신호의 `last_sent_at` 부재 유지 |

무력화 실증 — 고친 줄을 되돌리면 잡힌다.

```text
D2  `unevaluable` 을 무시하게 되돌림        3 failed  (재발송 2 · 범위 분리 1)
D3  Gate 두 줄을 제거                      3 failed  (dry-run · flag-off · duplicate)
```

재발송 테스트는 **tick 0 에 실제로 발송된 ticker** 만 본다. 구역 상한에 잘린
신호는 D1 계약상 나가는 것이 맞아서, 본문에 사업군 이름이 있다는 것만으로는
재발송을 판정할 수 없다(처음에 그렇게 썼다가 실패로 잡았다).

### 23-4. 설계서 옛 문구 정리 (§22-5 마감)

우선순위 주석만 남기지 말라는 지시대로 본문을 교체했다.

| 위치 | 교체 후 |
|---|---|
| §9 | `운영 Gate 를 통과한 회차의 관측·집계는 매 회차 기록하고, 발송 진척은 전체 전송 성공 시에만 전진한다` |
| §14-2 | `전체 전송 성공 시 실제 본문 포함 신호의 last_sent_at 과 sent_today 만 전진한다. 실패·부분 전송·상한 제외 신호는 발송 진척을 전진시키지 않는다` |
| §14-6 5·6번 | 관측 / 집계 / 발송 진척 3축으로 교체 |
| §15-5 | `관측·집계 저장 Gate 와 발송 진척 저장 시점을 각각 확인` |
| 머리말 | `CURRENT_ACTION = RESULT_REMEDIATION_AND_VERIFICATION` |

§15-2 에 D2 3상태(6항)·D3 Gate 표(7항)를 본문으로 추가했다.

### 23-5. §22 분류 오류 정정

§22 에서 D2·D3 을 **"현재 구현의 결함이 아니라 계약 공백"** 이라고 적고 검증자
판정을 막지 않는다고 했다. **틀렸다.** 검증자가 실제 `run()` 경로에서 재현했다 —
지속 신호 재발송, dry-run·flag-off 파일 생성, duplicate 집계 증가. 계약에 정의가
없는 것과 동작이 틀린 것은 별개이고, 정의가 없어도 **동작은 이미 틀려 있었다.**
§22-2·§22-3 의 "계약 공백" 표현은 §23 이 대체한다.

---

## 24. 교차 경로 결함 3건 (검증자 P1)

§23 의 D2·D3 은 각 분기를 따로는 맞게 처리했지만 **조합에서 계약을 깼다.**
검증자가 셋 다 실행으로 재현했다. 반려 사유가 전부 "분기 A × 분기 B" 였다.

### 24-1. 정상 전송 회차가 `신호 없음` 으로 집계됐다

D3 으로 회차 기록이 `_finish()` 뒤로 밀렸는데, 전송 성공 경로는 여전히
집계 **파일**의 마지막 회차를 `sent` 로 고치고 있었다(`mark_last_tick_sent`).
그 시점에 **이번 회차 tick 은 아직 없다.** 그래서

```text
직전 회차가 발송으로 둔갑 · 이번 회차는 잠정값으로 남음
검증자 실측   checks=1 · sent=0 · no_signal=1
```

수정 — `app/three_push_runtime/runner_evidence.py`. 파일이 아니라 **아직 쓰이지
않은 pending 의 잠정값**을 고친다.

```python
pending = record.get(PENDING_KEY)
if pending is not None:
    pending["tick_outcome"] = OUTCOME_SENT
```

`mark_last_tick_sent()` 는 이제 운영 경로에서 호출되지 않는다. D3 이전 구조
(집계를 조립 단계에서 먼저 쓰던 때)의 정정 수단이었다.

### 24-2. 전송 성공 저장이 평가 불가를 회복으로 되돌렸다

`unevaluable` 을 관측 저장에만 넘기고 **전송 성공 저장에는 넘기지 않았다.**
사업군 장애 중 보유 급등만 나가는 회차에서 순서가 이렇게 된다.

```text
① 전송 성공 저장  merge_sector_entries(unevaluable 없음) → 사업군 continuous=False
② 관측 저장       이미 변질된 ①의 값을 "보존"
검증자 실측       기존 발송 사업군 3개가 전부 False
```

수정 — 같은 파일에서 `intraday.unevaluable` 을 `merge_sector_entries()` 에
전달한다. 이 함수는 이미 `unevaluable` 을 받도록 열려 있었는데(§23-1) 호출부
한 곳을 빠뜨렸다.

### 24-3. 대체 ETF 로 저장된 사업군이 보존되지 않았다

보존을 **ticker** 로 잡았다. 직전 회차가 대체 ETF 로 저장됐다면 이번 회차의
대표 ticker 와 달라 보존 집합에 안 든다.

```text
검증자 실측   ALT000 continuous=True → False
```

수정 — `app/runtime_evidence/intraday_alert_flow.py` `_unevaluable_tickers()`.
평가 불가 사유가 붙은 `sector_key` 를 모아, 이전 기록 중 **그 사업군에 속한
entry 전부**를 보존한다. 설계자 D2 의 "해당 사업군 entry 보존" 이 원래 뜻이다.

### 24-4. 교차 조건 테스트 3건

지정 9건은 각 분기를 따로 봤다. 조합을 보는 테스트를 더했다.

| 테스트 | 계약 |
|---|---|
| `test_successful_send_is_counted_as_alert` | 정상 전송 → `checks=1 · sent=1 · no_signal=0` |
| `test_send_success_save_keeps_unevaluable_sector_entries` | 사업군 평가 불가 + 보유 급등 전송 동시 → 사업군 보존 · 보유 갱신 |
| `test_alternate_etf_entry_is_preserved_by_sector_key` | 직전이 대체 ETF → `continuous`·`last_sent_at` 유지 |

무력화 실증 — 고친 줄을 각각 되돌리면 해당 1건이 실패한다.

```text
pending 대신 집계 파일을 고치게 되돌림     test_successful_send_is_counted_as_alert        1 failed
전송 성공 저장에서 unevaluable 제거        test_send_success_save_keeps_unevaluable_...    1 failed
sector_key 보존 제거 (ticker 만)           test_alternate_etf_entry_is_preserved_...       1 failed
```

### 24-5. 지정 테스트 1건의 기대가 틀렸었다

`test_provider_down_is_counted_as_lookup_failure` 를 보유 급락이 **발송되는**
회차로 짰다. 설계자 표에서 그 회차는 `정상 운영·평가 실패`(미전진) 행이 아니라
`전체 전송 성공`(`알림`) 행이다. 24-1 을 고치자 `sent=1` 이 나와 드러났다.
보유를 임계 밖(-1.0%)으로 바꿔 **발송 없는** 평가 실패 회차로 고쳤다.

두 행이 동시에 성립할 수 있다는 점을 계약이 명시하지 않는다 — 사업군은 평가
실패지만 보유 급등락은 정상 평가돼 발송되는 회차다. 현재 구현은 **발송이 있으면
`알림`** 으로 센다(점검 횟수는 어느 쪽이든 1회). 설계자 표의 `발송 진척` 열이
행을 가르는 기준이라 보고 그렇게 읽었다.
