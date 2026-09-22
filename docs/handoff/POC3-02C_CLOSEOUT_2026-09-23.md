# POC3-02C 통합 종료 — 장중 급등락 알림 (OPS-01 · 02 · 03)

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 세션 개발자
- **작성일**: 2026-09-23 · 설계자 지시 `POC3-02C_CLOSEOUT = WRITE_NOW`

```text
STATUS                  = IMPLEMENTED_VERIFIED_ACTIVATED
FIRST_OPERATION_DATE    = 2026-09-22
SCHEDULED_TICKS         = 7/7
TELEGRAM_MESSAGES       = 4
DAILY_CAP               = ENFORCED
SECTOR_COVERAGE         = 27/27
PARTIAL_DELIVERY        = 0
RUNTIME_ERRORS          = 0
NEXT_PHASE_BLOCKED      = NO
```

배포 확인은 SHA 를 적지 않고 명령으로 한다. **OCI 는 자동 배포가 아니다 —
수동 `git pull` 이다.** 푸시했다고 배포된 것이 아니다.

```bash
git log --oneline -1
ssh oci-krx "cd /home/ubuntu/krx_hyungsoo && git log --oneline -1"
```

---

## 1. 이 챕터가 만든 것

기존 `holdings_risk_alert` 7틱(09:30·10:30·11:30·12:30·13:30·14:30·15:20)에
**사업군 대표 ETF 판정**과 **보유 급등**을 얹어 「장중 급등락」 통합 본문을
만든다. **신규 push_kind 0 · 신규 cron 0** — 기존 종류에 올라탄다.

| Step | 내용 | 종료 |
|---|---|---|
| **OPS-01** | PC 가 사업군·대표 ETF 를 자동 산출 → 사용자가 버전 전체 승인 → OCI 전달 | 검증자 `VERIFIED` (9라운드) |
| **OPS-02** | 판정·본문·억제·상태 저장 엔진 | 검증자 `VERIFIED` |
| **OPS-03** | 정책을 번들에 실어 **켤 수 있게** + 15:40 요약 결함 수정 | 검증자 `VERIFIED_WITH_NOTES` |

메시지 구역은 셋이고 **구역마다 최대 3종목**, 한 메시지 최대 9종목이다.

```text
보유종목      보유 급락 + 보유 급등
진입 회피     사업군 급락 + 추격 주의
신규 진입 검토 사업군 진입 후보
```

15:40 보유 브리핑 말미에 그날 회차 집계가 한 줄 붙는다.

### 코드

```text
408  app/runtime_evidence/sector_signal.py          사업군 판정(§4-2) · 커버리지 Gate · provider 장애 구분
325  app/runtime_evidence/sector_signal_state.py    억제·cooldown · 관측 3상태 저장
468  app/runtime_evidence/intraday_alert_flow.py    회차 조립 · 대체 조회 · 구역/일일 상한 · 기록 의도
281  app/runtime_evidence/intraday_alert_render.py  본문 · 15:40 요약 한 줄
178  app/runtime_evidence/intraday_checkup_tally.py 회차 집계 (발송 상태와 별개 파일)

204  app/intraday_config/generator.py   PC 자동 산출 트리거 · CONFIRMED_POLICY
313  app/intraday_config/schema.py      번들 스키마 · 정책 검증 · effective_config_hash
334  app/intraday_config/selector.py    사업군 분류 · 대표/대체 선정
439  app/intraday_config/store.py       버전·승인·활성·sync 이력
 42  app/intraday_config/startup.py     백엔드 기동 시 catch-up
```

러너 `scripts/run_three_push_runtime_oci.py` 는 **646줄**(KS-10 동결선 648 이하).
OPS-02 에서 3줄 교체, OPS-03 에서 0줄.

### 테스트

```text
41  test_sector_signal              34  test_intraday_alert_render
23  test_intraday_alert_integration 37  test_day_return_price_basis
57  test_intraday_alert_flow_through
52  test_intraday_config_contracts  79  test_intraday_config_integration
```

---

## 2. 첫 운영일 실측 — 2026-09-22

**정책 활성화**: 2026-09-21 23:48 KST, 사용자가 카드의 승인 버튼을 눌렀다
(`approved_by=user` → `activated_by=pc_deploy` → `deployed / verify ok`).

### 2-1. 7틱 전부 실행

| 시각 | 결과 | 사업군 평가 | 신호 | 발송 | 억제 |
|---|---|---:|---:|---:|---:|
| 09:30 | **sent** | 27/27 | 2 | 2 | 0 |
| 10:30 | **sent** | 27/27 | 2 | 1 | 1 |
| 11:30 | skipped `no_new_or_worsened` | — | — | — | (기록 없음) |
| 12:30 | **sent** | 27/27 | 3 | 1 | 2 |
| 13:30 | **sent** | 27/27 | 3 | 1 | 2 |
| 14:30 | skipped `intraday_daily_cap_reached` | — | — | — | — |
| 15:20 | skipped `intraday_daily_cap_reached` | — | — | — | — |

`telegram_sent=True` · `telegram_partial_delivery=False` — **4건 모두 전송됐다.**

### 2-2. 억제 — 회차와 신호 건수를 구분한다

설계자 지시대로 둘을 섞지 않는다. **숫자가 우연히 같아 더 위험하다.**

```text
SUPPRESSED_RUNS          = 3   신호가 억제된 회차 (10:30 · 12:30 · 13:30)
SUPPRESSED_SIGNAL_ITEMS  = 5   억제된 신호 건수 (1 + 2 + 2) — **기록된 것**
```

집계 파일의 `suppressed` 3건은 **다른 뜻**이다 — 발송이 없었던 회차
(11:30 · 14:30 · 15:20)를 센다. 15:40 요약의 `중복 억제 3건` 이 이 값이다.

```text
회차 집계(7틱)   sent 4 · suppressed 3 · no_signal 0 · failed 0
15:40 요약       장중 점검 7회 · 알림 4건 · 중복 억제 3건 · 신호 없음 0건
```

> **`SUPPRESSED_SIGNAL_ITEMS = 5` 는 "기록된" 값이다.** 11:30 회차도 신호가
> 전부 억제돼 본문이 비었는데(그래서 집계가 `suppressed`), 그 회차의 억제
> 건수는 진단에 남지 않았다 — §5-1. 실제 총합은 **5건 이상**이다.

### 2-3. 상태 파일 — D1·D2 계약이 운영에서 그대로 나왔다

```text
date_kst 2026-09-22 · sent_today 4 · entries 6종목

396500  ENTRY_REVIEW   cont=False  +2.6%  last_sent 09:30
487240  ENTRY_REVIEW   cont=False  +2.2%  last_sent 10:30
0193T0  U5_7           cont=False  +5.1%  last_sent 09:30   ← 보유 급등
228810  AVOID_DROP     cont=True   -2.9%  last_sent 12:30
140700  AVOID_DROP     cont=False  -1.5%  last_sent 13:30
462900  AVOID_DROP     cont=True   -2.2%  last_sent None    ← 관측만, 발송 아님
```

- `sent_today=4` 가 실제 발송 수와 일치한다.
- **`462900` 은 `last_sent=None`** — 관측은 됐지만 나가지 않아 발송 표식이
  안 찍혔다. 검증에서 고친 **D1 계약**(상한에 잘린 신호를 발송으로 치지 않는다)
  이 실제 운영에서 그대로 나왔다.
- **`intraday_observation_preserved = 1`** 이 매 틱 나왔다 — **D2 3상태**가
  돌고 있다. 대표 ETF 27개 중 3개(`139260`·`161510`·`367760`)가 보유 종목과
  겹쳐 사업군 판정에서 빠지는데(`REASON_HELD`), 그 기록을 "회복" 으로 적지
  않고 보존한 것이다. **정상 동작이다.**

### 2-4. 오류 0건

`intraday_error` · `intraday_sector_error` · `intraday_observation_error` ·
`intraday_tally_error` 전부 없음. `provider_down` 없음. 커버리지 100%.

---

## 3. 반드시 알아야 할 계약 3개

이 셋을 모르면 다음 수정에서 같은 함정에 빠진다. **검증 반려가 전부 이 셋의
조합에서 났다.**

### 3-1. 관측 상태 ≠ 발송 진척 (설계서 §15-2 가 정본)

한 파일(`sector_signal_state_latest.json`) 안에서 **필드와 저장 시점이 다르다.**

| 구분 | 필드 | 언제 |
|---|---|---|
| 관측 상태 | `state` · `continuous` · `sector_key` · `day_return_pct` | 운영 Gate 통과 **매 회차** |
| 발송 진척 | `last_sent_at` · `sent_today` | **전체 전송 성공 시에만** 전진 |

- `fingerprint` 는 **저장 필드가 아니다.** `ticker#state` 파생값이고,
  `holdings_risk_alert` 의 registry 중복키는 실행 시각 `HH:MM` 이다.
- 파일이나 `sent_today` 키의 **존재는 발송 성공의 증거가 아니다.**
  `sent_today` 는 0 으로 존재할 수 있다(카운터 초기값).
- 계약은 "저장 여부" 가 아니라 **"전진 여부"** 로 말한다.
- `dedup_window_minutes` 는 `cooldown_minutes` 의 **호환 별칭**(다르면 거부),
  `max_sends_per_run` 은 **고정값 1**(그 외 거부). 둘 다 독립 조절 대상이 아니다.

### 3-2. 관측은 3상태다 — 모르는 것을 회복으로 적지 않는다

```text
SIGNAL_PRESENT   조건 충족          → continuous=true
SIGNAL_ABSENT    정상 평가 후 미충족 → continuous=false
UNEVALUABLE      평가 불가          → 기존 값 전부 유지
```

평가 불가는 provider 장애 · 커버리지 미달 · 사업군 예외(`held`) · 시세 없음이다.
이걸 회복으로 적으면 지속 신호가 cooldown 뒤 **재발송**된다.

보존은 **`sector_key` 단위**다 — 직전 회차가 대체 ETF 로 저장됐다면 이번 회차의
대표 ticker 와 달라, ticker 로만 잡으면 빠진다.

범위를 분리한다 — 사업군이 통째로 무너져도 **정상 평가된 보유 급등은 갱신**한다.

### 3-3. 라이브 파일은 운영 Gate 통과 회차만 쓴다

```text
mode = send  AND  정책 enabled  AND  PUSH_AUTOSEND_HOLDINGS_RISK_ALERT_ENABLED  AND  duplicate 아님
```

조립은 **쓰지 않고 의도만 담는다**(`RiskAssembly.intraday_records`).
러너 `_finish()` 한 곳에서 `apply_intraday_records()` 가 실제로 쓴다. 모든 종료
지점이 `_finish` 를 지나므로 분기마다 호출을 넣지 않아도 된다. pending 은
`record[PENDING_KEY]` 로 실어 보내고 **직렬화 전에 꺼내 지운다**.

> `dry-run` 만 돌려도 라이브 파일이 바뀌면 안 된다. duplicate 회차를 세면
> 15:40 의 "장중 점검 N회" 가 같은 틱을 두 번 센다.

---

## 4. 운영 방법

### 4-1. 정책을 바꾸려면

사용자가 임계값을 직접 입력하는 화면은 **없다.** PC 가 산출한 버전 전체를
승인하는 구조다.

```text
1  app/intraday_config/generator.py 의 CONFIRMED_POLICY 를 고친다
2  백엔드가 기동(또는 --reload)하면 catch_up 이 새 후보를 만든다
   — 정책이 다르면 주기와 무관하게 재산출된다(should_regenerate)
3  화면 「승인·적용 > 장중 급등락 설정」 에서 값 확인 후 승인
4  승인 = OCI 전달이고, **그 순간부터 다음 틱에 적용된다**
```

결과가 같으면 `effective_config_hash` 가 같아 새 버전이 생기지 않는다.

### 4-2. 현재 운영값

```text
enabled                 true      max_sends_per_day        4
cooldown_minutes        120       max_items_per_section    3
dedup_window_minutes    120       max_sends_per_run        1
drop_threshold_pct      -5.0      surge_threshold_pct      5.0
sector_avoid_drop_pct   -1.5      sector_chase_pct         4.0
sector_entry_min_pct    1.5       sector_rank_top_pct      20.0
sector_min_coverage_pct 80.0
```

### 4-3. 발송 계약

```text
고정 4건   시장 브리핑 08:00 + 보유 브리핑 09:15·12:30·15:40
조건형     7틱에서 조건 충족 시 하루 최대 4건 (신호 없으면 0건)
하루 최대  8건
15:40 요약 보유 브리핑 안의 한 줄 — 별도 발송 건수가 아니다
```

사용자가 메시지 형식과 하루 최대 8건을 **2026-09-21 승인**했다.

### 4-4. 운영 점검 명령 (읽기 전용)

```bash
# 코드가 최신인가
ssh oci-krx "cd /home/ubuntu/krx_hyungsoo && git log --oneline -1"

# 틱별 결과
ssh oci-krx "grep holdings_risk_alert /home/ubuntu/krx_hyungsoo/logs/low_freq_push_cron.log | grep <날짜> | grep 완료"

# 회차 집계 · 사업군 상태
ssh oci-krx "cat /home/ubuntu/krx_hyungsoo/state/three_push/intraday_checkup_tally_latest.json"
ssh oci-krx "cat /home/ubuntu/krx_hyungsoo/state/three_push/sector_signal_state_latest.json"

# 틱별 진단 (발송 회차만 사업군 수치가 남는다 — §5-1)
ssh oci-krx "cd /home/ubuntu/krx_hyungsoo && grep <날짜> state/three_push/oci_runtime_history.jsonl"
```

---

## 5. 열린 항목 — **전부 비차단**

### 5-1. 억제 회차의 진단이 남지 않는다 (신규 · 이번 점검에서 발견)

`intraday_alert_flow.assemble_intraday_alert()` 의 진단 기록 블록이
**두 조기 반환보다 뒤**에 있다.

```text
408행  REASON_DAILY_CAP  → return
422행  REASON_NO_SIGNAL  → return
444행  out.diagnostics.update({... 사업군 수치 ...})
```

그래서 **모든 신호가 억제돼 본문이 빈 회차**(11:30 이 그랬다)와 **일일 상한
회차**는 `intraday_sector_signal_count` · `..._suppressed_count` 등이
기록되지 않는다. 집계는 `suppressed` 로 남으므로 **발송 여부 판정에는 영향이
없다.** 사후 분석에서 "몇 건이 억제됐나" 를 셀 수 없을 뿐이다.

`SUPPRESSED_SIGNAL_ITEMS = 5` 가 "기록된 값" 인 이유가 이것이다.

```text
제안  진단 update 를 조기 반환 **앞**으로 옮기거나, 두 반환 경로에서도
      사업군 수치를 남긴다. 발송 동작은 바뀌지 않는다.
```

### 5-2. 파생 키 목록이 두 곳에 중복 정의돼 있다

백엔드 `schema.DERIVED_POLICY_KEYS` 와 프론트 `IntradayConfigCard.tsx` 의
`DERIVED_KEYS`. API 가 목록을 내려주지 않아 화면이 자기 집합을 갖는다. 지금
두 목록은 같고 계약도 정확히 동작하지만, **키가 늘면 한쪽만 고칠 수 있다.**
검증자가 두 라운드 연속 비차단 주석으로 남겼다.

### 5-3. 무조정 시세 창이 D-1 에 못 미칠 수 있다

`krx_etf_daily_price_unadjusted` 는 25일 롤링 창이고 07:20 배치가 채운다.
2026-09-22 기준 최신일이 **09-17** 이었다 — 배치가 `09-21→09-17` 로 거슬러
올라가 그날을 기준일로 잡았다(09-18·09-21 에 KRX 종가 없음).

영향은 **「신규 진입 검토」 구역뿐**이다(5일·20일 창이 필요). 급락·급등·추격
주의는 Naver 실시간 등락률만 쓰므로 무관하다. 첫 운영일에 `ENTRY_REVIEW` 2건이
정상 산출됐으므로 **실동작에는 문제가 없었다.**

### 5-4. 이월 (02B-2 에서)

`CSV_REFRESH_REQUIRED` — API 에만 있는 신규 ticker 감지 · API·CSV 불일치 감지.
정적 CSV 자동 다운로드는 범위 밖. 배치 로그에 계속 나타난다.

---

## 6. 이 챕터에서 배운 것 (반복하지 말 것)

검증 반려가 OPS-01 에서 9라운드, OPS-02·03 에서 여러 라운드 났다. 사유가
매번 **"방금 고친 것의 옆칸"** 이었다.

1. **층(layer)만 열거하면 놓친다.** 결함은 다른 차원에 있었다 — **상태**(버전이
   여럿일 때), **순서**(N행 위에서 이미 무슨 일이 일어났나), **조합**(분기 A ×
   분기 B).
2. **상태 계약을 고치면 상태 × 전이 표를 먼저 그린다.** 억제 계약을 7셀로
   전수 고정했더니 판정 순서를 되돌렸을 때 **2셀만 실패**했다 — 나머지 5셀은
   옛 코드에서도 통과했다. 셀 단위 테스트만 썼으면 못 잡았다.
3. **한 함수에 인자를 추가하면 호출부를 전부 센다.** `merge_sector_entries()` 에
   `unevaluable` 을 열어 두고 호출부 한 곳을 빠뜨려 P1 이 났다.
4. **호출 가능성과 도달 가능성은 다르다.** 마지막 세 라운드가 전부 이것이었다.

   ```text
   엔드포인트 목록만 보고 **응답 내용**을 안 봤다
   generate() 를 직접 불러 **주기 게이트가 막는 상황**을 지나쳤다
   후보 있는 상태만 보고 **후보가 사라진 뒤**를 안 봤다
   ```

5. **실화면이 아니면 못 잡는 것이 있다.** 「적용될 판정 기준」 이 전부 `없음`
   으로 나와 후보가 아예 생기지 않는다는 것을 알았다. 자동 테스트 1,900여 건이
   전부 통과하고 있었다.
6. **무력화 실증을 반드시 한다.** 고친 줄을 되돌려 실제로 실패하는지 본다.
   그 과정에서 **내 테스트 기대가 틀린 것을 여러 번** 잡았다.
7. **"계약 공백" 과 "동작 결함" 을 혼동하지 말 것.** 정의가 없어도 동작은 이미
   틀려 있을 수 있다.
8. **문서에 자기참조 값을 적지 않는다.** "현재 HEAD = `<SHA>`" · 커밋 수 · 그
   문서 자신의 줄 수는 커밋하는 순간 낡는다. 경로와 확인 명령을 적는다.
9. **추론을 실측으로 적지 않는다.** "OCI 자동 배포" 라고 썼는데 사용자가 곧바로
   pull 한 것이었다. 장치 유무는 crontab·timer 를 봐야 안다.

---

## 7. 다음 사람이 바로 할 일

```text
1. 발송 빈도 관찰 — 며칠 쌓이면 max_sends_per_day 4 가 적절한지 본다.
   **비차단 운영 튜닝 항목**이다. 첫날 상한 도달은 "평소 4건" 을 뜻하지 않는다.
2. §5-1 진단 공백 — 억제 회차 분석이 필요해지면 그때 고친다.
3. §5-2 파생 키 중복 — 정책 키가 늘어날 때 함께 정리한다.
4. 정책값을 바꾸려면 §4-1 순서.
```

착수 전 `docs/PROGRAM_TRUTH.md` 프로세스 C 를 읽는다 — 지금 실제 동작이 거기 있다.

---

## 8. 문서

| 문서 | 경로 |
|---|---|
| **상태 저장 계약 정본** | `docs/ai_design/POC3/POC3-02C-OPS-02_INTRADAY_SURGE_DROP_ALERT_DESIGN_V1.md` **§15-2** |
| OPS-01 결과서 | `docs/ai_result/POC3/POC3-02C-OPS-01_PC_AUTO_PARAM_DELIVERY_RESULT.md` |
| OPS-02 결과서 (목업 §7 · D2/D3 §23 · 교차 §24) | `docs/ai_result/POC3/POC3-02C-OPS-02_INTRADAY_SURGE_DROP_ALERT_RESULT.md` |
| OPS-03 결과서 (P1 §12 · 도달성 §13 · 활성화 §14) | `docs/ai_result/POC3/POC3-02C-OPS-03_INTRADAY_ALERT_ACTIVATION_RESULT.md` |
| OPS-01 종료 | `docs/handoff/POC3-02C-OPS-01_CLOSEOUT_2026-09-18.md` |
| OPS-02 종료 | `docs/handoff/POC3-02C-OPS-02_CLOSEOUT_2026-09-21.md` |
| 지금 실제 동작 | `docs/PROGRAM_TRUTH.md` 프로세스 C · §13-7 · 부록 A |
| 상태 앵커 | `docs/STATE_LATEST.md` |

---

## 9. 사용자 확인

**남은 것 하나** — 2026-09-22 에 Telegram 「장중 급등락」 **4건**을 실제로
받으셨는지. 받으셨다면 사용자 운영 확인까지 **완전 종료**다.

시스템 기록은 `telegram_sent=True` · `partial_delivery=False` 로 4건 전송
성공이다. 수신 여부만 사용자가 확인하면 된다.
