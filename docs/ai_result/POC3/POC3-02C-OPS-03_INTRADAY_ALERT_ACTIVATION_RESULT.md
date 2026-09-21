# POC3-02C-OPS-03 개발 결과서 — 장중 급등락 알림 활성화

```text
STEP                        = POC3-02C-OPS-03
SUMMARY_WHEN_DISABLED       = OMITTED
POLICY_CONTROL_FIELDS       = 2/2        (enabled · policy_status)
REQUIRED_POLICY_VALUE_KEYS  = 12/12 VALID
TOTAL_POLICY_FIELDS         = 14
DERIVED_POLICY_KEYS         = 2  (dedup_window_minutes · max_sends_per_run)
USER_EDITABLE_THRESHOLDS    = 0
CANDIDATE_DRY_RUN           = PASS
FLOW_THROUGH_TESTS          = PASS  (관통 57 · 설정 73)
BACKEND_FULL_REGRESSION     = 1,921 passed / 0 failed / 0 errors
FRONTEND                    = 18 files / 211 passed · tsc·eslint 0건
BLACK / FLAKE8              = 361 files unchanged / 0건
KS10_TRIGGER / NEAR         = 0 / 7
RUNNER_LINES                = 646  (동결선 648 이하 · 이번 Step 변경 0줄)
OCI_ACTIVE_ENABLED          = false
TELEGRAM_SENDS              = 0
USER_MESSAGE_APPROVAL       = APPROVED (2026-09-21 · 형식 + 하루 최대 8건)
COMMIT_PUSH_OCI_APPLY       = 미수행 (검증자 통과 전 금지)
BLOCKING_ITEM               = NONE
```

입력: 설계자 지시 보존본
`docs/ai_design/POC3/POC3-02C-OPS-03_INTRADAY_ALERT_ACTIVATION_DESIGN_V1.md`
(`PLAN_RESUBMISSION_REQUIRED = NO` 이므로 PLAN 을 따로 쓰지 않았다)

---

## 1. 처리한 요구사항

| 지시 | 상태 |
|---|---|
| §1 15:40 비활성 요약 결함 수정 | **DONE** |
| §1 네 경로 관통 테스트 | **DONE** — 무력화 실증 |
| §2 정책을 번들에 담아 승인·전달 완결 | **DONE** |
| §2 카드에 읽기 전용 표시 + 경고 | **DONE** — 상태 구분 결함 1건은 §12 에서 수정 |
| §2 임계값 편집 UI 금지 | **DONE** — 쓰기 엔드포인트 2개 유지(테스트로 고정) |
| §3 정책 값 12키 확정 (+ 제어 2필드) | **DONE** — 근거 표는 §4 |
| 보완 — 파생·고정 키 2개 검증 규칙 | **DONE** — 무력화 실증 (§4-2) |
| §4 안전선 1~5단계 | **DONE** — 6단계(검증자)부터는 대기 |
| §5 발송 계약 | **DONE** — 신규 push kind·cron 0 |
| §6 완료 기준 | 머리말 참조 |

---

## 2. 15:40 요약 결함 수정 (§1)

부착 조건이 `슬롯 == CLOSE and 본문 있음` 뿐이라 정책 상태를 보지 않았다.
비활성이면 집계 파일이 없으므로 **`장중 점검 확인 불가` 가 매 15:40 브리핑에
붙었다.** "기능이 꺼짐" 과 "켜져 있는데 집계를 못 읽음" 을 같은 문구로 말한 것이다.

`app/runtime_evidence/holdings_selection_flow.py` — 부착 전에 `active_policy()`
를 본다. 비활성이면 줄을 만들지 않고 진단만 남긴다
(`intraday_checkup_summary_omitted = "policy_disabled"`).

| 경로 | 결과 |
|---|---|
| 비활성 · `NOT_CONFIGURED` | **줄 없음** |
| 활성 + 정상 집계 | `장중 점검 3회 · 알림 1건 · 중복 억제 0건 · 신호 없음 2건` |
| 활성 + 집계 파일 없음 | `장중 점검 확인 불가` |
| 활성 + 집계 손상 | `장중 점검 확인 불가` |

기존 15:40 본문과 발송 슬롯은 건드리지 않았다.

### 2-1. 관통 테스트 4건

소스 검사가 아니라 **운영 조립 함수** `build_holdings_selection()` 를 부른다.
기존 2건(`test_1540_slot_appends_summary_through_selection_flow` ·
`test_summary_only_on_close_slot`)은 소스 문자열만 봐서 이 결함을 못 잡았다.

```text
test_1540_summary_omitted_when_policy_disabled
test_1540_summary_shown_when_policy_enabled_and_tally_ok
test_1540_summary_unknown_when_enabled_but_tally_missing
test_1540_summary_unknown_when_enabled_but_tally_corrupt
```

무력화 실증 — 정책 확인을 빼면 `..._omitted_when_policy_disabled` **1 failed**.

---

## 3. 정책 생성·승인·전달 (§2)

### 3-1. 왜 켤 수 없었나

`generator.generate()` 가 `schema.build_payload()` 를 호출할 때 `policy=` 를
넘기지 않아 항상 기본값 `{"enabled": False, "policy_status": "NOT_CONFIGURED"}`
가 들어갔다. `policy=` 를 넘기는 호출처는 저장소 전체에 0건이었다.

### 3-2. 고친 것

`app/intraday_config/generator.py` 에 `CONFIRMED_POLICY` 를 두고
`build_payload(policy=dict(CONFIRMED_POLICY))` 로 넘긴다. **스키마 기본값에서
조용히 오는 구조가 아니다**(설계자 지시) — 테스트가 이를 고정한다
(`test_policy_is_not_silently_taken_from_schema_defaults`).

전달 경로는 **이미 완결돼 있었다.** `approve-and-apply` → `deploy()` →
`export_json()` 이 `payload_json` **전체**를 원격 `latest_intraday_alert_config.json`
으로 보낸다. 사업군만 보내는 구조가 아니었으므로, 번들에 정책을 담으면 그대로
따라간다. 이 경로는 손대지 않았다.

### 3-3. 카드 읽기 전용 표시

> 이 절의 최초 구현에는 **현재 상태와 적용 예정 상태를 구분하지 못하는 P1
> 결함**이 있었다. 검증자가 잡았고 §12 에서 고쳤다. 아래는 고친 뒤 기준이다.

`GET /intraday-config/state` 에 `policy_values`(12키, 스키마 순서)와
`policy_rule_version` 을 더했다. 값이 없으면 `None` 으로 내려 **"빠졌다" 는
사실이 화면에도 보이게** 한다 — 0 으로 위장하지 않는다.

카드에는 키 이름 대신 사용자 말로 적는다(`보유 급락 기준` · `재발송 대기` …).
후보가 있고 아직 비활성이면 경고를 덧붙인다.

```text
이 설정을 적용하면 장중 알림이 실제로 발송됩니다. 기존 고정 4건에 더해
조건이 맞는 날 최대 4건이 추가됩니다(하루 최대 8건). 조건이 없으면 추가
발송은 없습니다.
```

**임계값 편집 UI 는 만들지 않았다.** 쓰기 엔드포인트가 2개(`approve-and-apply` ·
`reject`)뿐임을 테스트가 고정한다 — 정책 편집 엔드포인트가 생기면 실패한다.

### 3-4. 정보 블록으로 렌더한 이유 (판단 1건)

정책 표에 `<h3>` 를 쓰면 기존 테스트가 깨진다 — 이 카드에는 **지금 할 동작
제목이 하나만 나오게** 막는 계약이 있다(`IntradayConfigCard.test.tsx`
"재시도 문단과 동시에 렌더되지 않는다", `querySelectorAll("h3")` 전수 비교).

검증된 가드를 느슨하게 만들지 않고, 정책 블록을 **동작이 아닌 정보**로 표시했다
(굵은 라벨 + `dl`). 사용자에게 보이는 결과는 같다.

---

## 4. 정책 필드 14개와 확정 근거 (§3)

필드를 셋으로 나눈다. "정책 12키" 는 **값 키**를 뜻하고, 여기에 제어 필드
2개(`enabled`·`policy_status`)를 더해 번들에는 **14필드**가 실린다.

```text
POLICY_CONTROL_FIELDS       = 2   enabled · policy_status
REQUIRED_POLICY_VALUE_KEYS  = 12  REQUIRED_POLICY_KEYS
TOTAL_POLICY_FIELDS         = 14
```

설계자 §3 이 값까지 명시한 것은 9개(제어 1 + 값 8)다. 나머지는 설계서·스키마
확정값을 썼고, **근거 없는 값은 만들지 않았다.**

| 키 | 값 | 근거 |
|---|---:|---|
| `enabled` | `true` | 설계자 §3 |
| `policy_status` | `CONFIGURED` | `schema.validate` — `enabled=true` 면 필수 |
| `cooldown_minutes` | 120 | 설계자 §3 · 설계 §5 |
| `max_sends_per_day` | 4 | 설계자 §3 (`max_alerts_per_day`) · 설계 §6 |
| `max_items_per_section` | 3 | 설계자 §3 · 설계 §6 |
| `sector_entry_min_pct` | +1.5 | 설계자 §3 · 설계 §4-2 |
| `sector_chase_pct` | +4.0 | 설계자 §3 · 설계 §4-2 |
| `sector_avoid_drop_pct` | −1.5 | 설계자 §3 · 설계 §4-2 |
| `sector_rank_top_pct` | 20.0 | 설계자 §3 · 설계 §4-2 |
| `sector_min_coverage_pct` | 80.0 | 설계자 §3 · 설계 §14 |
| `surge_threshold_pct` | 5.0 | **§3 목록 밖** — 설계 §13-1 `U5_7 = +5% 이상` |
| `drop_threshold_pct` | −5.0 | **§3 목록 밖** — 설계 §13-1 `D5_7 = -5% 이하` |
| `max_sends_per_run` | 1 | **§3 목록 밖** — 설계 §6 "회차당 최대 1건" |
| `dedup_window_minutes` | 120 | **§3 목록 밖** — 설계 §5 중복 억제 창 120분 |

### 4-1. 키 이름 차이 1건

설계자 §3 은 `max_alerts_per_day` 로 적었으나 스키마 키는 `max_sends_per_day`
다. 값(4)·의미(조건형 일일 상한)가 같고 설계 §6 이 뒷받침하므로 스키마 키를
썼다. 새 키를 만들지 않았다.

### 4-2. 파생·고정 키 2개 — 장식용으로 남기지 않았다 (설계자 필수 보완)

`dedup_window_minutes` 와 `max_sends_per_run` 은 `schema.py` 밖에서 읽는 코드가
**0건**이다. 범위 검사만 두면 화면에 "조절 가능" 처럼 보이면서 실제 효과가 없다.
설계자 확정대로 **검증 규칙으로 못박았다.**

| 키 | 확정 | 거부 규칙 |
|---|---|---|
| `dedup_window_minutes` | `cooldown_minutes` 의 **호환 별칭** | 두 값이 다르면 `ConfigSchemaError` |
| `max_sends_per_run` | **고정값 `1`** (조립이 회차당 본문 1개) | `1` 이 아니면 `ConfigSchemaError` |

별칭은 **상수가 아니다** — 둘을 함께 옮기는 것은 허용된다(`cooldown=90 ·
dedup=90` 통과). 실측:

```text
기본값                                통과
dedup 90 · cooldown 120               거부 — "호환 별칭이다 — 같아야 한다: 90 != 120"
max_sends_per_run 2 · 5 · 10          거부 — "고정값(1)이다"
max_sends_per_run 0                   거부 — 기존 범위 검사(1~10)가 먼저 잡는다
cooldown 90 · dedup 90                통과
```

**화면에서도 독립 정책처럼 보이지 않는다.** 「적용될 판정 기준」 목록에서 두 키를
빼고 아래 한 줄로 대신한다.

```text
중복 억제 창은 재발송 대기와 같은 값이고, 회차당 최대는 1건으로 고정입니다.
따로 조절하지 않습니다.
```

파생 키 목록은 **두 곳에 따로 있다** — 백엔드 `schema.DERIVED_POLICY_KEYS` 와
프론트 `IntradayConfigCard.tsx` 의 `DERIVED_KEYS`. API 가 이 목록을 내려주지
않으므로 화면이 자기 집합을 갖는다. 지금 두 목록은 같고 계약도 정확히
동작하지만, **키가 늘어나면 한쪽만 고칠 수 있다**(검증자 B-6 주석 · 비차단).

계약 테스트 4건(`test_dedup_window_must_equal_cooldown` ·
`test_max_sends_per_run_is_fixed_at_one` ·
`test_derived_keys_are_named_so_ui_can_separate_them` ·
`test_generated_bundle_satisfies_derived_key_rules`).
무력화 실증 — 두 규칙을 지우면 앞 2건이 실패한다.

---

## 5. 안전선 1~5단계 실측 (§4)

### 5-1. 후보 생성 · 12키 검증 (2·3단계)

**격리 DB** 에서 생성했다 — 라이브 `state/runtime/runtime_state.sqlite` 는
전후 sha256 동일.

```text
상태          created
rule_version  sector_rep.v1
data_asof     2026-09-11
사업군        27개 · 제외 149
승인 여부     False (후보 상태 · active 아님)
정책          enabled=True · policy_status=CONFIGURED
12키          전부 존재 · 전부 범위 안 (범위 밖·누락 0)
```

### 5-2. 후보 기준 dry-run · 목업 대조 (4단계)

로컬 무조정 테이블에는 날짜가 1개뿐이라 D-1 비교가 불가능했다. **OCI 에서
읽기 전용으로** 최근 2거래일 종가만 가져와 로컬 코드로 재생했다
(OCI 쓰기 0 · 외부 API 호출 0 · 발송 0).

```text
재생 2026-09-17 (직전 2026-09-16)
평가 27/27 · 커버리지 100.0% · coverage_ok=True · provider_down=False
신호 6건 · 제외 1건 (short_history)

  미디어      TIGER 미디어컨텐츠    -1.9%  장중 급락
  정보기술    TIGER 200 IT         -1.7%  장중 급락
  조선        SOL 조선TOP3플러스    +4.5%  단기 급등 · 추격 주의
  방위산업    PLUS K방산           +4.6%  단기 급등 · 추격 주의
  조선기자재  SOL 조선기자재        +5.3%  단기 급등 · 추격 주의
  우주항공    PLUS 우주항공        +7.9%  단기 급등 · 추격 주의
```

본문(사업군 구역만 · 보유는 이 재생에 포함하지 않음):

```text
[장중 급등락] 10:30

진입 회피
• 미디어 · TIGER 미디어컨텐츠: -1.9%
  장중 급락
• 정보기술 · TIGER 200 IT: -1.7%
  장중 급락
• 방위산업 · PLUS K방산: +4.6%
  단기 급등 · 추격 주의

기준
현재가 2026-09-17 10:30 · 직전 종가 2026-09-16

※ 자동 감지 결과이며, 최종 판단은 사용자가 합니다.
```

**목업(OPS-02 결과서 §7) 형식과 일치한다.** 신호 6건 중 구역 상한으로 3건만
실리고 3건은 `dropped` 이력에 남았다 — 잘린 것은 발송으로 치지 않는다.

> **빈도 측정이 아니다.** 2026-09-17 **한 시점**의 종가로 판정을 재생한 것이다.
> 실제 발송 빈도는 활성화 후에야 측정된다.

### 5-3. 전체 회귀·KS-10 (5단계)

머리말 참조. 러너는 이번 Step 에서 **0줄** 바뀌었다(646 유지).

---

## 6. 변경된 파일

| 줄 | 파일 | 내용 |
|---:|---|---|
| 419 | `app/runtime_evidence/holdings_selection_flow.py` | §1 — 15:40 요약에 정책 Gate |
| 193 | `app/intraday_config/generator.py` | §2·§3 — `CONFIRMED_POLICY` 를 번들에 |
| 283 | `app/api_intraday_config.py` | §2 — `policy_values` · `policy_rule_version` |
| 73 | `frontend/lib/api/intradayConfig.ts` | 같음 (타입) |
| 340 | `frontend/app/components/IntradayConfigCard.tsx` | §2 — 읽기 전용 표시 · 활성화 경고 |
| 307 | `frontend/app/components/IntradayConfigCard.test.tsx` | fixture 에 신규 필드 |
| 1298 | `tests/test_intraday_alert_flow_through.py` | §1 관통 4건 |
| 1267 | `tests/test_intraday_config_integration.py` | §2·§3 계약 5건 |
| 134 | `docs/ai_design/POC3/POC3-02C-OPS-03_INTRADAY_ALERT_ACTIVATION_DESIGN_V1.md` | 설계자 지시 보존본 (신규) |
| — | `docs/ai_result/POC3/POC3-02C-OPS-03_INTRADAY_ALERT_ACTIVATION_RESULT.md` | 이 문서 (줄 수는 자기참조라 적지 않는다) |

> 줄 수는 현재값이다. 변경 목록은 `git status --short` 실측이다.

---

## 7. 신규 의존성

없음.

---

## 8. 지시문 외 변경

없음.

---

## 9. 알려진 한계 / 미완성

- **파생 키 목록이 백엔드·프론트에 중복 정의돼 있다**(§4-2). 검증자
  `VERIFIED_WITH_NOTES` 의 비차단 주석이다. 없애려면 `/state` 응답에 파생 키
  목록을 실어 화면이 그것을 읽게 해야 하는데, 검증자가 "추가 개발은 필요하지
  않다" 고 했으므로 이번 Step 에서 하지 않았다. **BACKLOG.**

- **활성화는 하지 않았다.** `OCI_ACTIVE_ENABLED = false` · 발송 0.
  설계자 §4 의 6~10단계(검증자 → 사용자 확인 → 승인 → read-back → 운영 확인)가
  남았다.
- `dedup_window_minutes` · `max_sends_per_run` 은 여전히 실행 코드가 읽지
  않는다. 다만 **장식용으로 남기지 않았다** — 설계자 확정대로 별칭·고정값
  검증 규칙으로 못박고 화면에서도 분리했다(§4-2).
- `PROGRAM_TRUTH.md` · `STATE_LATEST.md` 는 **활성화 시점에** 갱신한다. 지금은
  정책이 여전히 비활성이라 "지금 실제 동작" 이 바뀌지 않았다. 다만 §1 수정으로
  **`장중 점검 확인 불가` 줄이 사라지는 것**은 배포 시점에 바뀌므로, 그때
  `PROGRAM_TRUTH` 프로세스 C 의 해당 문단을 함께 고쳐야 한다.

---

## 10. 검증자에게 알릴 점

1. **정책 표를 `h3` 로 쓰지 않았다**(§3-4). 기존 검증 가드가 `h3` 전수를
   비교하기 때문이다. 가드를 고치지 않고 마크업을 바꿨다.
2. **키 이름 차이 1건**(§4-1) — 설계자 `max_alerts_per_day` vs 스키마
   `max_sends_per_day`. 새 키를 만들지 않고 스키마 키를 썼다.
3. **dry-run 재생에 OCI 데이터를 썼다**(§5-2). 로컬 무조정 테이블에 날짜가
   하나뿐이라 D-1 비교가 불가능했다. **읽기 전용 SELECT 2건**이고 OCI 쓰기·
   발송·재시작은 0건이다.
4. **보완 과정에서 내 테스트 결함 2건을 잡았다.** 별칭 규칙이 생기자
   `cooldown` 만 옮기던 테스트가 거부됐고(둘을 함께 옮기도록 수정),
   `max_sends_per_run=0` 은 고정값 규칙이 아니라 기존 범위 검사(1~10)에
   먼저 걸렸다(범위 안 값 2·5·10 으로 교체하고 0 은 별도 단언).
   **코드가 아니라 테스트가 틀렸다.**
4. 전달 경로(`deploy`)는 **이미 payload 전체를 보내고 있었다.** 고치지 않았다 —
   §2 "완결한다" 는 생성부에 정책을 담는 것으로 충족된다.

---

## 11. 사용자 확인이 필요한 항목

1. **메시지 형식과 하루 최대 8건 계약 — 사용자 승인 완료**(2026-09-21).
   설계자 §4 의 7단계다. 목업이 바뀌지 않는 한 다시 묻지 않는다.

   ```text
   메시지 형식                                승인
   고정 4건 + 조건형 최대 4건 = 하루 최대 8건   승인
   ```

2. **커밋·푸시·OCI 적용 미수행.** 검증자 통과 전 금지 계약을 지켰다.
   검증자 통과 후 코드 배포는 가능하되, 기존 active 정책은 `enabled=false`
   로 유지한다. `enabled=true` 후보의 `approve-and-apply` 는 **그 적용이 곧
   실제 활성화**이므로 별도 시점에 수행한다.

---

## 12. 검증자 P1 — 승인 전 화면이 현재 상태를 잘못 표시

### 12-1. 무엇이 틀렸나

`get_state()` 가 `policy = (cp or ap)` 로 정책을 하나만 읽었다. **후보가 있으면
후보가 이긴다.** 그래서 active 가 비활성인데 `enabled=true` 후보가 승인 대기
중이면:

```text
API      policy_enabled = true      ← 후보 값
화면     「장중 알림 발송 중」        ← 승인 전인데 이미 켜진 것처럼
경고     숨김                        ← `!state.policy_enabled` 조건에 가림
```

정작 **켜지는 순간에 활성화 경고가 사라진다.** 사용자가 지금 상태를 활성으로
오인한 채, 발송량 경고 없이 승인할 수 있었다.

### 12-2. 고친 것 — 두 상태를 분리했다

`app/api_intraday_config.py`

| 필드 | 뜻 |
|---|---|
| `policy_enabled` · `policy_status` | **지금 운영 중인 active** 정책 |
| `candidate_policy_enabled` · `candidate_policy_status` | **적용하면 어떻게 되는지** (후보 없으면 `None`) |
| `policy_values` · `policy_rule_version` | 「적용될 판정 기준」 — **승인 대상**(후보 있으면 후보) |

후보가 없으면 `None` 으로 내린다 — `False` 로 위장하지 않는다.

`IntradayConfigCard.tsx`

- `지금 알림 상태` — active 기준
- `적용 후 상태` — 후보가 있을 때만 별도 행 (`장중 알림 발송 시작` / `장중 알림 없음`)
- 활성화 경고 조건을 `!policy_enabled` → **`candidate_policy_enabled`** 로.
  경고는 **적용 결과**로 판단해야 한다.

실측(active 비활성 · 후보 `enabled=true`):

```text
active 정책    enabled = False · NOT_CONFIGURED
후보 정책      enabled = True  · CONFIGURED
판정 기준      12개 · cooldown = 120 (후보 기준)
화면 알림 상태  구조 준비 완료 · 장중 알림 정책 설정 전
활성화 경고    표시
```

### 12-3. 테스트 — 응답 내용을 본다 (검증자 B-6)

앞선 API 테스트는 **엔드포인트 목록만** 봤고, 프론트 fixture 는
`candidate_version_id` 가 있으면서 `policy_enabled=false` 인 형태만 썼다.
그래서 이 결함을 못 잡았다. 실제 승인 대기 상태를 만들어 응답을 검사한다.

| 테스트 | 계약 |
|---|---|
| `test_state_reports_active_policy_not_candidate` | `policy_enabled` 는 active 기준 |
| `test_state_reports_candidate_policy_separately` | 적용 예정 상태를 별도 필드로 |
| `test_state_policy_values_come_from_the_version_being_approved` | 판정 기준은 후보 기준 |
| `test_state_without_candidate_has_no_candidate_policy` | 후보 없으면 `None` |
| (프론트) `승인 전에는 '발송 중' 으로 표시하지 않는다` | 화면 라벨 |
| (프론트) `적용 후 켜진다는 것을 따로 보여준다` | 별도 행 |
| (프론트) `활성화 경고를 숨기지 않는다` | 경고 + `하루 최대 8건` |
| (프론트) `후보가 비활성이면 활성화 경고를 띄우지 않는다` | 반대 경우 |

무력화 실증:

```text
API 를 (cp or ap) 로 되돌림              policy_enabled=True 재현 · 백엔드 1 failed
경고 조건을 !candidate_policy_enabled 로  프론트 2 failed
```
