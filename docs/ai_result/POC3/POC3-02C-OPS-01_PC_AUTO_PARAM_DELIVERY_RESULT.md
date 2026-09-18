# POC3-02C-OPS-01 — PC 자동 산출 · 승인 · OCI 전달 · 개발 결과서

작성일: 2026-09-16 · 작성자: 개발자(VSCode Claude) · 수신: 검증자

```text
ROUND                   = FIX r9  (§12~§14 · 설계자 §15 · §16 · §17 · §18 · r8 §19)
IMPLEMENTATION          = DONE (로컬)
BACKEND_FULL_REGRESSION = 1,676 passed / 0 failed / 0 errors
FRONTEND                = tsc·eslint exit 0 · vitest 18 files / 207 tests
REVERSE_VERIFY          = 26가드 · EXIT=0
UI_WIRED                = ApprovalTelegramView (설계자 배치 판단 (a))
KS10                    = 474개 전수 · TRIGGER 0 · NEAR 7 · API 641 · RUNNER 648
OCI_DEPLOY_EXECUTED     = 시도 1회 · 적용 0회 (§17)
                          사용자가 2026-09-18T12:56:10Z 승인 버튼을 눌렀다.
                          precheck_failed 로 멈췄으나 **그 전에 원격 파일 2개가
                          이미 쓰였다** — OCI active·DB 는 무변경.
OCI_LEFTOVER_FILES      = 2 (정리 미승인 · §17-3)
TELEGRAM / NAVER        = 0건
COMMIT_PUSH             = 0
```

입력 문서: 설계서 `docs/ai_design/POC3/POC3-02C_INTRADAY_DECISION_BRIEFING_DESIGN_V1.md`
· PLAN `docs/ai_plan/POC3/POC3-02C-OPS-01_PC_AUTO_PARAM_DELIVERY_PLAN_V1.md`

---

## 1. 처리한 요구사항

| 요구사항 | 결과 |
|---|---|
| 판단 A — 기존 `runtime_param` 미변경, 신규 번들만 완결 | **DONE** (§4) |
| 판단 B — 토큰 사전 자동 분류 | **DONE** — 27개 사업군 |
| 판단 C — `sector_label` = 공식 토큰 그대로 | **DONE** |
| 판단 D — 신규 카드 | **DONE** |
| 배치 판단 (a) — 승인·적용 화면 연결 | **DONE** (§8-A) |
| 보완 ① 해시 분리 | **DONE** |
| 보완 ② PC 자동 산출 시점 (cron 없음) | **DONE** — r1 에서 함수만 있고 배선이 없었다(§12-1) |
| 보완 ③ 승인+적용 한 번의 동작 | **DONE** |
| 보완 ④ PC/OCI DB 역할 구분 | **DONE** |
| 보완 ⑤ checksum 범위 | **DONE** |
| 보완 ⑥ 최초 번들 비활성 | **DONE** |
| OCI DB 적재·활성화 사슬 5~7 (신규) | **DONE** (§5) |
| 실제 OCI 전달 실행 | **시도 1회 · 적용 0회** — 원격 파일 2개 잔존(§17) |
| `OPS-03` 판정 (b) — 정기 PUSH 콘텐츠 동일 억제 해제 | **DONE** (§11) |
| `OPS-03` — 사건형(급락 알림) 억제 유지 | **DONE** — 무변경 실측 |
| `OPS-03` — 12:30 건 (ㄱ)/(ㄴ) 판정 | **DONE** (§11-6) — (ㄱ) 슬롯 간 비교 |

---

## 2. 변경된 파일

### 2.1 신규 — 백엔드 (1,428줄)

| 줄 | 파일 | 책임 |
|---:|---|---|
| 439 | `app/intraday_config/store.py` | DB version/approval/active · **승인 게이트** |
| 334 | `app/intraday_config/selector.py` | 토큰 사전 분류 · 대표/대체 선정 |
| 234 | `app/intraday_config/schema.py` | 번들 계약 · 두 해시 · checksum 범위 |
| 250 | `app/api_intraday_config.py` | state · approve-and-apply · reject |
| 162 | `app/intraday_config/generator.py` | 자동 산출 트리거 |
| 9 | `app/intraday_config/__init__.py` | 패키지 |

### 2.2 신규 — 스크립트 (484줄)

| 줄 | 파일 |
|---:|---|
| 335 | `scripts/sync_intraday_config.py` — 8단계 전달 사슬 |
| 149 | `scripts/apply_intraday_config_oci.py` — 원격 4~7단계 (일시 업로드) |

### 2.3 신규 — 프론트 (310줄) · 테스트 (515줄)

| 줄 | 파일 | 건수 |
|---:|---|---:|
| 244 | `frontend/app/components/IntradayConfigCard.tsx` | — |
| 248 | `frontend/app/components/IntradayConfigCard.test.tsx` | **16** |
| 66 | `frontend/lib/api/intradayConfig.ts` | — |
| 267 | `tests/test_intraday_config_contracts.py` | **26** |

### 2.4 수정 (4건)

| 파일 | 전 → 후 | 내용 |
|---|---|---|
| `app/runtime_state_db.py` | 221 → 292 | 신규 테이블 3개 + 인덱스 2개. **삭제 1줄**(docstring 한 줄 교체) |
| `app/api.py` | 632 → 641 | import 1 + router 등록 1 + 기동 catch-up 1 + 주석 |
| `app/market_refresh_service.py` | 464 → 490 | 갱신 **성공 후** 재산출 호출 + helper (§12-1) |
| `frontend/app/components/ApprovalTelegramView.tsx` | 28 → 41 | 카드 1줄 연결 + import 1 + 주석. **기존 `ThreePushParamCard` 는 그대로** |

### 2.5 건드리지 않은 것 — `git diff HEAD` 0줄 실측

```text
app/runtime_param_store.py                      무변경
app/three_push_runtime_param.py                 무변경
scripts/sync_three_push_runtime_param.py        무변경
scripts/create_three_push_runtime_param.py      무변경
app/api_three_push_param.py                     무변경
scripts/run_three_push_runtime_oci.py           무변경  (648줄 · FREEZE_AT_648)
frontend/app/components/ThreePushParamCard.tsx  무변경
```

### 2.6 `POC3-02B-OPS-03` 억제 해제 — 수정 2건 · 테스트 3건 · 신규 1건

| 파일 | 전 → 후 | 내용 |
|---|---|---|
| `app/market_briefing/flow.py` | 348 → 359 | `no_change` skip 제거 · `content_unchanged` 진단 기록 |
| `app/runtime_evidence/holdings_selection_flow.py` | 367 → 382 | 동일 내용도 전체 상태 발송 · `load_state(today_kst=...)` 정합성 수정 |
| `tests/test_market_briefing_contracts.py` | 893 → 928 | 교체 1 + 신규 2 |
| `tests/test_market_briefing_flow_through.py` | 278 → 300 | 교체 1 + 신규 1 |
| `tests/test_holdings_selection.py` | 608 → 675 | 신규 4 |
| `scripts/ops02c/reverse_verify_guards.py` | 신규 638 | 역검증 6가드 (EXIT=0) |

교체 2건은 **약화가 아니라 계약 교체**다 — 근거는 §11-5.

### 2.7 FIX r2 — P1 6건이 어느 파일에 떨어졌나

줄 수는 §2.1~2.6 이 이미 **현재값**이다. 여기서는 대응만 적는다.

| P1 | 파일 |
|---|---|
| ① 자동 산출 진입점 | `app/intraday_config/startup.py`(신규) · `app/api.py` · `app/market_refresh_service.py` |
| ② 배포 실패 재시도 소실 | `app/intraday_config/store.py` · `app/api_intraday_config.py` · `IntradayConfigCard.tsx` · `intradayConfig.ts` |
| ③ 실패 전 OCI active 변경 | `scripts/apply_intraday_config_oci.py` · `scripts/sync_intraday_config.py` |
| ④ 기각본 활성화 | `app/intraday_config/store.py` |
| ⑤ 시총 결측 fallback | `app/intraday_config/selector.py` |
| ⑥ 토큰 사전 하드코딩 | `app/intraday_config/selector.py` · `state/intraday_config/token_dictionary_v1.json`(신규) |
| B-6 테스트 공백 | `tests/test_intraday_config_integration.py`(신규) · `scripts/ops02c/reverse_verify_guards.py` · `IntradayConfigCard.test.tsx` |

### 2.8 FIX r2 신규 3건

| 줄 | 파일 |
|---:|---|
| 995 | `tests/test_intraday_config_integration.py` — 통합 60건 |
| 104 | `state/intraday_config/token_dictionary_v1.json` — 28사업군 · 41토큰 |
| 42 | `app/intraday_config/startup.py` — 기동 catch-up |

---

## 3. 보완 6건 구현 결과 (실측)

### 3.1 해시 분리 — 매일 승인 요청이 생기지 않는다

```text
1차 생성        status=created    사업군 27 · 미분류 149 · 기준일 2026-09-11
2차 생성(force) status=unchanged  같은 config_version_id
기준일만 변경    새 버전 생성 안 함
대표 ticker 교체 새 버전 생성
```

`evaluation_input_hash` 는 데이터·기준일·규칙 변경을 감지해 **계산 이력에만**
쓰고, 새 버전 생성은 `effective_config_hash` 로만 판정한다.

`effective_config_hash` 에 넣는 것 — 사업군 키 · 대표/대체 ticker · 토큰 사전 ·
정책 · `rule_version`. **`data_asof` 와 시총은 넣지 않는다.**

**보유 목록은 선정 입력이 아니다** — `evaluation_input_hash` 에도 넣지 않았다.

### 3.2 자동 산출 시점 — cron 없음

**호출자 2곳이 실제로 배선돼 있다**(r1 REJECTED 사유. §12-1):

```text
app/api.py  _lifespan   → intraday_startup.catch_up()        기동 시 catch-up
app/market_refresh_service.py → _regenerate_intraday_config() 갱신 성공 후
```

`generator.should_regenerate()` 판정:

| 상황 | 결과 |
|---|---|
| 활성 버전 없음 | `no_active_version` → 즉시 |
| 대표가 적격성 상실(상장폐지·레버리지화 등) | `representative_ineligible:<ticker>` → 주기 무관 즉시 |
| `data_asof` 가 거래일 축에 없음 | `asof_not_on_axis` → 재계산 |
| 20거래일 경과 | `interval_elapsed:<n>` |
| 그 외 | `within_interval:<n>` → 하지 않음 |

`generate()` 는 **예외를 올리지 않는다** — 실패해도 dict 를 돌려준다. 백엔드
기동을 막으면 안 되기 때문이다(테스트로 고정).

### 3.3 승인과 적용은 한 번의 동작

```text
POST /intraday-config/approve-and-apply
  → store.approve()            (1 PC 승인 기록)
  → sync_intraday_config.deploy()  (2~8)
```

전달 실패 시 응답 `deploy_status = APPROVED_NOT_DEPLOYED` 이고 메시지는
**"승인은 기록됐고 전달이 실패했다. 재시도하면 된다"** 다. 승인 행은 그대로
남으므로 **재승인을 요구하지 않는다.**

### 3.4 PC / OCI DB 역할 구분

| DB | 역할 |
|---|---|
| PC `state/runtime/runtime_state.sqlite` | 후보 버전 · 승인 · 전달 이력 |
| OCI 같은 경로 | 실제 운영 active |
| JSON `state/three_push/params/latest_intraday_alert_config.json` | 전송·archive |

**DB 파일을 복사하거나 덮어쓰지 않는다.** `sync` 는 JSON 만 scp 하고, OCI 에서
`apply_intraday_config_oci.py` 가 원격 DB 에 적재한다.

### 3.5 checksum 범위

```text
승인 전 source_hash  efde834da9efd10a
승인 후 source_hash  efde834da9efd10a   (동일)
```

`VOLATILE_KEYS` 로 `created_at` · `approved_at` · `approved_by` · `rejected_*` ·
`sync` · hash 필드 자체 · `config_version_id` 를 **재귀 제거**한 뒤 정규화 JSON
(`sort_keys` · 공백 고정)의 sha256 을 쓴다.

### 3.6 최초 번들 비활성

```text
enabled = false · policy_status = NOT_CONFIGURED
```

`enabled=true` 인데 `surge_threshold_pct` · `drop_threshold_pct` ·
`cooldown_minutes` · `dedup_window_minutes` · `max_sends_per_run` ·
`max_sends_per_day` 중 **하나라도 없으면 `ConfigSchemaError`** 다
(6개 키 parametrize 테스트).

`enabled=false` 인데 `policy_status=CONFIGURED` 인 모순도 거부한다.

---

## 4. 승인 게이트 — 이번 Step 의 핵심

조사에서 확인된 사실: 기존 `activate_param_version` 은 `approved_*` 를
**검사하지 않는다**(감사 필드일 뿐). 승인은 "cron 이 부르지 않으니 사람이 눌러야
한다" 는 **절차적 통제**로만 지켜지고 있었다.

신규 경로는 **코드로 강제**한다.

```python
def activate(config_version_id, *, activated_by, db_path=None):
    row = get_version(config_version_id, db_path=db_path)
    if not row.get("approved_at") or not row.get("approved_by"):
        raise ApprovalRequired(f"미승인 버전은 활성화할 수 없다: {config_version_id}")
```

원격 `apply_intraday_config_oci.py` 도 5단계 적재 전에 `approved_*` 를 확인하고,
7단계에서 `store.activate()` 를 호출해 **게이트를 한 번 더 통과**한다.

**기존 `activate_param_version` 은 건드리지 않았다** — 운영 중 경로다(판단 A).

---

## 5. PC→OCI 8단계 사슬

```text
1 PC 승인 DB              approved 확인 · 미승인이면 전달 자체를 하지 않는다
2 전송 JSON export        tmp → os.replace (원자)
3 SCP → atomic rename     원격 tmp 업로드 후 mv
4 OCI verify              schema 검증 + source_hash 재계산 대조    ← 신규
5 OCI DB version 적재     upsert_version (승인 필드 원본 그대로)   ← 신규
6 승인 확인                approved_* 없으면 거부                  ← 신규
7 active pointer 갱신     store.activate() — 게이트 재통과         ← 신규
8 재독출 대조 + rollback   불일치면 직전 active 로 되돌리고 실패      ← 원격 내부
```

4~7 은 `apply_intraday_config_oci.py` 를 **일시 업로드해 원격 실행**하고 즉시
삭제한다. 기존 `verify_three_push_param_oci.py` 와 같은 방식이며 **상시 배포
스크립트를 늘리지 않았다.**

`deploy()` 는 **예외를 올리지 않는다.** 모든 실패가
`intraday_alert_config_sync` 에 사유와 함께 기록되고 `(False, reason)` 을
돌려준다.

**8단계는 원격 프로세스 안에서 한다.** r1 에서는 PC 가 별도 `ssh` 로 다시
읽었고, 그 왕복만 실패해도 `deploy` 는 실패를 반환하면서 OCI active 는 이미
새 버전인 상태로 남았다 — 결과서가 "어느 단계에서 실패하든 active 를 건드리지
않는다" 고 적은 것이 거짓이었다(§12-3).

지금은 7단계 직전에 직전 active 를 붙들고, 8단계 재독출이 어긋나면
`_restore()` 로 되돌린 뒤 실패를 반환한다. 되돌릴 자리가 없던 최초 전달이면
pointer 를 지운다(`clear_active`).

전달에 성공하면 **PC active 도 같이 갱신한다.** 안 하면 성공한 버전이 계속
`approved_not_deployed` 로 잡혀 재시도 버튼이 사라지지 않는다.

---

## 6. 사업군 자동 분류 결과

```text
1,168 전체 ETF → 적격 필터 → 토큰 사전 분류
= 사업군 27개 · 미분류 지수 149건 (excluded 로 기록)
```

설계자 목표 "20~40개" 범위 안이다. 조사서에서 지적한 **반도체 22개 후보가 하나로
병합**됐다.

| 사업군 | 대표 | ticker | 대체 | 후보 |
|---|---|---|---|---:|
| 반도체 | TIGER 반도체TOP10 | `396500` | `091160` | 22 |
| 바이오 | KoAct 바이오헬스케어액티브 | `462900` | `364970` | 17 |
| 2차전지 | KODEX 2차전지산업 | `305720` | `305540` | 10 |
| 게임 | KODEX 게임산업 | `300950` | `300640` | 5 |
| 로봇 | KODEX 로봇액티브 | `445290` | `0148J0` | 4 |
| 네트워크 | RISE 네트워크인프라 | `367760` | 없음 | 1 |

분류 규칙 — **긴 토큰 우선**, 같은 길이 토큰이 서로 다른 사업군을 가리키면
**충돌로 보고 분류하지 않는다**(임의로 하나를 고르지 않는다). 미분류는 조용히
버리지 않고 `excluded` 에 지수명·ETF 수·사유를 남긴다.

**토큰 사전의 원천은 데이터 파일**이다 — `state/intraday_config/token_dictionary_v1.json`
(git 추적). 거기서 읽어 `payload...token_dictionary` 에 담겨 버전과 함께 승인된다.
파일이 없거나 깨지면 **올린다** — 코드 상수로 되돌아가는 fallback 이 없다.

> r1 에서는 사전이 Python 리터럴이었고 결과서는 "코드 상수가 아니다" 라고 적었다.
> payload 에 복사되는 것과 원천이 데이터인 것은 다르다(§12-6).

---

## 7. 검증 실적 (FIX r9 재실측)

```text
신규 계약 테스트   26 passed   tests/test_intraday_config_contracts.py
신규 통합 테스트   60 passed   tests/test_intraday_config_integration.py
역검증            26가드 · EXIT=0   (6 → 13 → 17 → 20 → 24 → 26)
전체 회귀         1,676 passed / 0 failed / 0 errors   (r8 과 동일 — 프론트만 수정)
black             350 files unchanged
flake8            0건
frontend tsc      exit 0
frontend eslint   exit 0
frontend vitest   18 files / 207 tests
                  무부하 10회 + CPU부하 8프로세스 5회 = **15회 모두 207** (§18-4)
KS-10             474개 전수 · TRIGGER 0 · NEAR 7 · api.py 641 · 러너 648
                  NEAR 6 → 7 — 역검증 스크립트가 605줄로 근접 진입(§15-7)
라이브 state·DB   회귀 전후 sha256 동일
Telegram / Naver  0건 — 신규 코드 grep 0
OCI 접속           읽기 전용 확인 다수 + 사용자 승인 시도 1회
OCI 쓰기           **원격 파일 2개** (사용자 승인 시도 시 · §17)
OCI active/DB      무변경 — intraday 테이블 자체가 없다
```

### 7.1 백엔드 계약 테스트 26건이 고정한 것 (영역 8묶음)

| 영역 | 고정 내용 |
|---|---|
| 분류 | 긴 토큰 우선 · 충돌 시 미분류 · 미분류 기록 · 대표 ticker 중복 없음 |
| 적격성 | 레버리지·인버스·합성·해외 제외 · 대표≠대체 |
| 해시 | 기준일만 변경 → 새 버전 없음 · 대표 교체 → 새 버전 · 보유는 입력 아님 |
| checksum | 승인·시각이 바뀌어도 불변 |
| 정책 | 최초 비활성 · `enabled=true` 시 6개 키 전부 필수(parametrize) · 상태 모순 거부 |
| 승인 게이트 | 미승인 activate 거부 · 기각본 거부 · 승인 후 성공 |
| 실패 계약 | 전달 실패가 직전 active 를 바꾸지 않음 |
| 트리거 | idempotent · 예외 미발생 · 활성 없으면 즉시 · 신규 DB 파일 없음 |

---

## 8. 알려진 한계 / 미완성

1. **OCI 전달은 실패했고, 원격에 파일 2개가 남았다**(§17). OCI active·DB 는
   무변경이다. 잔존 파일 정리는 쓰기라 사용자 승인 대상이다.
2. **정책 수치가 비어 있다.** 설계자 확정대로 `enabled=false` 이며 임계·cooldown·
   상한은 `POC3-02C-OPS-02` 에서 정한다.
3. **`sync_intraday_config.deploy()` 의 3~8단계가 실행 검증되지 않았다.** 단위
   경로는 테스트로 고정했으나 실제 scp/ssh 왕복은 OCI 전달을 해야 확인된다.
4. **기존 `runtime_param` 의 OCI DB 적재 공백은 그대로다**(판단 A). 별도 Cleanup
   대상이며 `PROGRAM_TRUTH` 기록은 이번 결과서 제출 후 갱신 예정이다.

---

## 8-A. UI 연결 (설계자 배치 판단 (a) · 2026-09-16)

`ApprovalTelegramView` 의 기존 `ThreePushParamCard` **바로 아래**에 연결했다.
신규 메뉴·라우트를 만들지 않았고 `MainPanel` 구조는 그대로다.

| 설계자 요구 | 구현 |
|---|---|
| 화면 표시명 「장중 급등락 설정」 | `<h2>장중 급등락 설정</h2>` · 내부 이름 비노출 |
| 자동 분류 사업군 수 | `27개` |
| 적용 예정 대표 ETF 수 | `27종목 (사업군당 1종목)` |
| 데이터 기준일 | `2026-09-11` |
| 설정 버전 · checksum | `config_version_id` · sha 앞 12자 |
| 직전 승인본 대비 변경 요약 | 추가/제외/교체 · 이전→이후 ticker |
| `enabled=false` · 정책 미설정 | **"구조 준비 완료 · 장중 알림 정책 설정 전"** |
| OCI 미적용 | **"아직 적용하지 않음"** (실패로 표시하지 않음) |
| ETF 직접 편집 금지 | `input`·`select` 0개 · 버튼은 승인·기각 둘뿐 |

### 8-A-1. 기존 계약 위반을 발견해 **제 문구를 바꿨다**

`ApprovalTelegramView.test.tsx` 에 이 화면의 **`"승인 대기"` 문구 금지** 계약이
있다("빈 자리표시자를 만들지 않는다"). 처음 만든 카드가 `승인 대기 중인 변경` 을
써서 이를 위반했다.

그 테스트는 **우연히 통과하고 있었다** — 테스트 환경에서 API 호출이 실패해 카드가
`불러오는 중...` 으로만 렌더됐기 때문이다.

**기존 테스트를 약화시키지 않고 카드 문구를 `확인할 변경` 으로 바꿨다.**

### 8-A-2. 우연한 통과를 막는 신규 테스트 8건

`IntradayConfigCard.test.tsx` 는 **state 를 실제로 채워 렌더**한다.

표시명·내부 이름 비노출 · `"승인 대기"` 미사용 · `enabled=false` 를 오류
어휘(`오류`·`실패`·`에러`·`비정상`)로 표시하지 않음 · 미적용을 실패로 표시하지
않음 · 설계자 요구 항목 전부 표시 · 변경 요약 · 편집 UI 없음 · 승인과 적용이
버튼 하나.

### 8-A-3. 화면 주석 정정

`ApprovalTelegramView` 머리말의 2026-08-05 기록(*"정보 PUSH 는 승인 대상이
아니다 → 카드 만들지 않음"*)과 새 카드가 모순돼 보이므로, 그 기록을 지우지 않고
**새 카드가 정보 PUSH 가 아니라 운영 기준의 승인·적용임**을 덧붙였다.

---

## 9. 검증자에게 알릴 점

1. **r1 REJECTED 의 P1 6건을 한 라운드에서 닫았다.** 건별 대응은 §12.
   역검증을 6 → **13가드**로 늘려 6건 각각이 "무력화하면 실제로 깨지는지"를
   출력으로 남긴다(`scripts/ops02c/reverse_verify_guards.py`, EXIT=0).
2. **통합 테스트 공백을 메웠다**(B-6 지적). 신규
   `tests/test_intraday_config_integration.py` 가 배선·API 왕복·실패 후
   재시도·rollback 을 본다. 함수 단위 테스트로는 6건 전부 안 잡혔다.
3. **`app/api.py` 가 KS-10 임계를 넘었다가 되돌렸다.** catch-up 을 인라인했더니
   653줄(>650)이 돼서 `app/intraday_config/startup.py` 로 분리했다. 현재 641줄
   (NEAR, 기존과 동일 구간).
4. **`app/market_refresh_service.py` 를 건드렸다** — 지시문에 없던 파일이다.
   갱신 성공 후 재산출이 설계 §10-3(2) 계약이라 그 성공 지점이 여기뿐이었다.
   기존 로직은 `success_overall` 분기 뒤 호출 1줄만 추가했고 lock 밖이다.
5. **`store.clear_active()` 는 rollback 전용**이다. 운영 경로에서 부르지 않는다
   — 최초 전달이 8단계에서 실패했을 때 되돌릴 자리가 없어 필요하다.
6. **`OPS-03` 억제 해제**(§11)는 r1 에서 정상 구현으로 확인받았고 이번 라운드에
   변경 없다.

---

## 10. 사용자 확인이 필요한 항목

현재 상태 실측 (2026-09-18, 이 문서 작성 시점):

```text
action_state   approved_not_deployed
version        intraday-20260916T144047-642949  (27개 사업군 · 기준일 2026-09-11)
PC active      없음
deploy_status  precheck_failed
화면 버튼       「OCI 적용 재시도」
```

1. **실화면 확인** — 「승인·적용」 메뉴에서 27개 사업군과 **「OCI 적용 재시도」**
   버튼이 보이는지. 사용자가 이미 승인했으므로(2026-09-18T12:56:10Z) 재승인은
   필요 없다. 지금 눌러도 OCI 에 이 기능 코드가 없어 `precheck_failed` 로
   멈춘다 — **커밋·푸시·OCI 배포 뒤에** 눌러야 성공한다.
2. **OCI 잔존 파일 2개 정리**(§17-3). 지우는 것은 OCI 쓰기라 승인이 필요하다.
   다음 정상 전달이 덮어쓰므로 **보류해도 안전하다**(검증자 r7 확인).
3. **발송량이 늘어난다**(§11-8) — 08:00 시장 브리핑이 거래일마다, 보유 브리핑이
   슬롯마다 온다. 하루 고정 4건. 이전에는 실측 약 44% 만 발송됐다.
4. **커밋 미수행**

> `deploy_unconfirmed` 는 **설계자 승인 완료**다(설계서 §12 · 결과서 §15).
> 더 이상 대기 항목이 아니다.

---

## 11. 함께 포함된 수정 — `POC3-02B-OPS-03` 정기 PUSH 억제 해제

설계자 판정(2026-09-16)과 사용자 지시로 **이번 제출에 함께 담았다.** 별도 PLAN 은
요구되지 않았고 확정 계약을 그대로 구현했다.

### 11-1. 무엇이 문제였나 (실측)

```text
2026-09-16 08:00  market_briefing   skipped  no_change
                  fp=DOWN#KRX|KRX 은행|KRX|코스피 200 금융  (전일과 동일)
2026-09-16 12:30  holdings_briefing skipped  no_change     (오전 슬롯과 동일)
```

07:20 배치는 정상이었다 — 적재 21→22일, 최신 `2026-09-14`, 08:00 기준 지연
1거래일로 임계(1) 안이었다. **코드는 계약대로 움직였고, 그 계약이 정기 브리핑의
목적과 맞지 않았다.**

지난 9거래일 실측: 전망 상태 변경 3회 → **발송 4일 · 억제 5일**.
`2026-09-07~09-11` 은 5거래일 연속 `DOWN` 이라 그 주 브리핑이 1회였을 것이다.

### 11-2. 확정 계약

| PUSH | 성격 | 억제 |
|---|---|---|
| 08:00 시장 브리핑 | 정기 | 거래일마다 발송. **전일과 같아도 발송** |
| 보유 브리핑 3슬롯 | 정기 | 슬롯마다 발송. **내용이 같아도 발송** |
| 보유 급락 알림 7틱 | 사건 | 동일 위험·중복 신호 억제 **유지** |

**fingerprint 를 없애지 않았다.** 용도만 바꿨다 — 메시지 비교·운영 기록에 쓰고,
발송은 막지 않는다. 중복 차단 기준은 이미 있던 `registry_key` 다.

```text
market_briefing   registry_key(push_kind, param_id, runtime_date_kst)
holdings_briefing registry_key(..., slot_id=...)  →  runtime_date_kst#slot_id
```

### 11-3. 변경 지점 2곳

| 파일 | 변경 |
|---|---|
| `app/market_briefing/flow.py` | `previous_fingerprint == fingerprint` 시 `skip_reason` 설정을 제거. 대신 `diagnostics["content_unchanged"]` 기록 |
| `app/runtime_evidence/holdings_selection_flow.py` | `not changes.has_change` 시 skip 대신 **현재 상태 전체 발송**(`send_full`). `content_unchanged` 기록 |

`REASON_NO_CHANGE` 상수는 **남겼다** — 진단·이력 호환용이며 발송을 막는 경로에서
빠졌다.

### 11-4. 작업 중 발견한 정합성 오류 1건

`holdings_selection_flow` 가 `load_state(state_path)` 를 **`today_kst` 없이**
불러 실제 오늘 날짜로 비교하고 있었다. 함수가 받은 `today_kst` 와 어긋나면 조용히
`date_mismatch` fallback 이 된다.

운영에서는 두 값이 같아 동작이 바뀌지 않지만, 계약을 코드로 맞췄다
(`load_state(state_path, today_kst=today_kst)`).

### 11-5. 교체한 기존 테스트 2건 — **약화 아님**

옛 계약을 고정하던 테스트다. 새 계약으로 **교체**하고 커버리지를 늘렸다.

| 기존 | 교체 후 |
|---|---|
| `test_same_state_different_numbers_is_no_change` | `test_same_state_still_sends_and_records_unchanged` — 같은 상태여도 `skip_reason is None` · `content_unchanged is True` · 본문 존재 |
| `test_flow_through_repeat_is_suppressed_and_state_untouched` | `test_same_day_rerun_is_blocked_by_registry` — 같은 날 재실행은 여전히 막히되 사유가 **`duplicate_runtime`** 이고 `no_change` 가 아님 |

추가한 테스트:

```text
test_consecutive_same_state_days_all_send          5거래일 연속 같은 전망도 매일 발송
test_no_change_reason_is_no_longer_produced        no_change 경로 부재
test_next_trading_day_sends_even_if_content_identical  다음 거래일 발송 + 본문 동일
test_unchanged_midday_still_sends                  오전과 같아도 낮 브리핑 발송
test_unchanged_close_still_sends                   마감 슬롯도 동일
test_unchanged_slot_sends_full_state_not_changes   변화분 대신 전체 상태
test_no_change_skip_reason_is_gone                 두 슬롯 모두 no_change 없음
```

### 11-6. 12:30 실측 판정 (설계자 요구)

```text
원인 = 같은 날 OPEN 슬롯과 선정이 동일 → 콘텐츠 동일 억제
판정 = 수정 대상 (같은 날짜·동일 MIDDAY 재실행 차단이 아니었다)
```

`holdings_briefing` 의 `no_change` 는 **같은 날 슬롯 간 비교**였다. OPEN 은 전체
상태를, MIDDAY/CLOSE 는 변화분을 보내는 구조라 변화가 없으면 통째로 빠졌다.

### 11-7. 역검증 (6/6)

재현: `python scripts/ops02c/reverse_verify_guards.py` (EXIT=0). 임시 경로만
사용하며 외부 호출·발송 0건.

| 보호 로직 | 가드 있을 때 | **무력화하면** |
|---|---|---|
| ① 승인 게이트 | `ApprovalRequired` 거부 | 미승인 버전이 활성화됨 |
| ② 동일 설정 재생성 차단 | `created=False` · 같은 id | 같은 설정으로 새 버전 생성 |
| ③ checksum 가변필드 제외 | 승인 시각 추가해도 동일 | 승인 시각이 checksum 을 바꿈 |
| ④ `enabled=true` 필수값 | `ConfigSchemaError` 거부 | 임계 없이 통과 |
| ⑤ 생성 트리거 예외 격리 | `status=failed` (예외 미발생) | selector 가 그대로 raise |
| ⑥ **정기 PUSH 억제 해제** | 다음 거래일 `skip_reason=None` | 옛 계약이면 `no_change` 로 막힘 |

### 11-8. 이번 수정으로 바뀌는 사용자 체감

```text
08:00 시장 브리핑    거래일마다 1건        (이전: 상태 바뀔 때만 · 실측 약 44%)
보유 브리핑          슬롯마다 1건 · 하루 3건 (이전: 변화 있을 때만)
보유 급락 알림        변화 없음            (사건형 억제 유지)
```

하루 고정 메시지가 **최대 4건**으로 안정된다. 급락 알림은 그대로 조건 발생 시에만
온다.

---

## 12. r1 REJECTED — P1 6건 대응 (검증자 2026-09-16)

전부 **인정**했다. 설계 재해석이 필요한 건은 없었다 — 설계서에 이미 적힌 계약을
코드가 안 지킨 경우다. 한 라운드에서 닫았다.

### 12-1. 자동 산출 진입점이 없음 → 배선 2곳

`generate()` 는 완성돼 있었으나 **호출자가 테스트와 역검증 스크립트뿐**이었다.
그래서 후보가 한 건도 안 생겼고 화면이 `0개 / —` 였다.

| 위치 | 시점 |
|---|---|
| `app/api.py` `_lifespan` → `intraday_startup.catch_up()` | 기동 catch-up |
| `app/market_refresh_service.py` → `_regenerate_intraday_config()` | 갱신 **성공 후** |

둘 다 예외를 삼킨다 — 산출 실패가 백엔드 기동이나 시세 갱신을 깨면 안 된다.
`catch_up()` 을 `api.py` 에 인라인하지 않은 이유는 KS-10 이다(§9-3).

### 12-2. 배포 실패 상태·재시도 대상 소실 → `actionable_version()`

승인된 행은 `latest_candidate()` 에서 빠지고(승인됐으니) active 도 아니라
(전달 실패했으니) **새로고침 한 번에 통째로 사라졌다.**

```text
pending_approval        미승인·미기각            → 「승인하고 OCI 적용」
approved_not_deployed   승인됐으나 active 아님    → 「OCI 적용 재시도」
```

API 가 `action_state` 로 내려주고 카드가 문구·버튼을 바꾼다. 재승인을 요구하지
않는다. 반대편도 막았다 — 전달 성공 시 **PC active 를 갱신**해 재시도 버튼이
영구히 남지 않게 했다(역검증 ⑨).

### 12-3. 실패 반환 전에 OCI active 변경 → 원격 내부 재독출 + rollback

§5 참조. 8단계를 원격 프로세스 안으로 옮기고 불일치 시 `_restore()` 한다.

### 12-4. 승인 후 기각본 활성화 가능 → 이중 차단

검증자가 **직접 재현에 성공**한 결함이다.

```text
reject()   승인 필드(approved_at/by)를 함께 지운다
activate() rejected_at 을 직접 본다
```

한쪽만으로는 부족하다 — 승인 필드를 남기는 경로가 하나라도 생기면 게이트가
뚫린다. 역검증 ⑦ 이 승인 필드를 되살려 넣고도 막히는지 확인한다.

### 12-5. 결측 시가총액을 0으로 대체 → fallback 제거

```python
# 전: items.sort(key=lambda x: (-(x["market_cap"] or 0.0), x["ticker"]))
#     → 전원 결측이면 종목코드 오름차순으로 뽑고도 metric="market_cap" 이라 기록
# 후: 시총이 있는 후보만 대표가 된다. 없는 후보는 no_market_cap 으로 기록,
#     사업군 전체가 미상이면 sector_no_market_cap 으로 제외한다.
```

`selection_basis` 에 **실제 값**을 남긴다(`representative_market_cap` ·
`alternate_market_cap` · `unpriced_candidate_count`). 값이 없으면 근거가 없다는
뜻이고, 그 상태는 위에서 이미 걸러진다.

실데이터 실측 — 결측 **0/1,168건**, 사업군 27개 유지, 제외 0건. 즉 현재
오선정은 없었고 **결측이 생겼을 때 조용히 무너지는 잠복 결함**이었다.

### 12-6. 토큰 사전 코드 하드코딩 → 번들 데이터 파일

`state/intraday_config/token_dictionary_v1.json` (git 추적, 28개 사업군 · 41
토큰). `load_token_dictionary()` 가 `schema_version` 과 각 항목 형식을 검사하고,
**읽기 실패 시 올린다** — 코드 상수로 되돌아가는 fallback 을 두지 않았다.
조용히 옛 사전으로 분류하면 승인된 내용과 실제 분류가 갈린다.

소스에 매핑 리터럴(`"반도체": [...]`)이 남아 있으면 테스트와 역검증 ⑫ 가 잡는다.

### 12-7. 결과서 오보고 정정 (A-2)

| r1 서술 | 실제 |
|---|---|
| 보완 ② 자동 산출 시점 DONE | 함수만 있고 배선 없음 → §12-1 로 해소 |
| 어느 단계에서 실패해도 OCI active 불변 | 8단계 재독출 실패 시 변경된 채 남음 → §12-3 |
| 토큰 사전은 코드 상수가 아님 | 원천이 Python 리터럴이었음 → §12-6 |
| black 347 files | **348 files** (검증자 실측이 맞다) |
| PC `runtime_state.sqlite` 생성되지 않음 | 파일은 이전부터 존재. 테스트는 `tmp_path` 만 쓴다 — 두 사실을 뭉뚱그린 서술이었다 |

### 12-8. 테스트 보강 (B-6)

| 지적 | 대응 |
|---|---|
| `test_failed_deploy_keeps_previous_active` 가 `deploy()` 미실행 | rollback 을 `_restore()` 단위로 실증 + 역검증 ⑩ |
| 기각 테스트가 미승인→기각만 검사 | `test_approved_then_rejected_cannot_activate` 외 2건 |
| 자동 생성 테스트가 함수 단위뿐 | 배선 테스트 5건 (`catch_up` 호출·lifespan 소스·refresh 성공 경로) |
| API 승인·실패·새로고침·재시도 통합 테스트 없음 | `api_client` fixture + 6건 |
| 역검증 6/6 이 결함을 못 잡음 | **13가드**로 확장 — ⑦~⑬ 이 P1 6건 각각에 대응 |

---

## 13. r2 REJECTED — P1 4건 · P2 1건 대응 (검증자 2026-09-16)

전부 **인정**했다. 근본 원인은 하나다 — r1 수정을 **승인본이 하나뿐인 상황**만
놓고 짰다. 정상적인 다중 버전 이력에서 무너졌다.

### 13-1. 옛 승인본이 재시도 대상으로 되살아남 (P1)

```text
v1 배포(active=v1) → v2 배포(active=v2)
  actionable_version() 이 v1 을 approved_not_deployed 로 반환
  → 화면이 옛 설정을 「OCI 적용 재시도」 대상으로 권한다 (롤백성 재배포)
```

**"active 가 아닌 승인본"을 물은 것이 잘못**이었다. active 만 제외하면 과거
승인본 전부가 조건에 남는다. 조치 대상은 **최신 미기각 버전 하나뿐**이다.

```sql
SELECT * FROM intraday_alert_config_version
 WHERE rejected_at IS NULL ORDER BY created_at DESC LIMIT 1
```

그 최신본이 active 면 `(None, None)` — 할 일 없음. 승인됐는데 active 가 아니면
재시도. 미승인이면 승인. 과거 버전은 **이력이지 할 일이 아니다.**

### 13-2. 재시도가 승인 기록을 다시 씀 (P1)

재시도도 `approve-and-apply` 를 쓰는데 이 함수가 상태와 무관하게
`store.approve()` 를 다시 불러 `approved_at` 을 새로 찍었다. 결과서의 "승인은
그대로 남는다" 와 실제가 달랐다.

```python
already = bool(row.get("approved_at") and row.get("approved_by"))
if not already:
    store.approve(...)          # **승인은 멱등이다**
```

기각된 버전으로 이 엔드포인트를 부르면 **409** 로 막는다.

### 13-3. 원격 적용 성공 후 SSH 실패 (P1)

원인이 두 겹이었다.

```text
① `... --json {file}; rm -f {apply}` → rc 가 **정리 명령**에서 나온다.
   적용이 성공해도 rm 이 실패하면 remote_apply_failed 로 뒤집힌다.
② ssh 가 진짜로 끊기면 원격이 적용됐는지 PC 가 알 수 없다.
```

① 은 `rm` 을 **별도 명령으로 분리**하고 rc 를 무시해 해결했다.

② 는 모르는 채로 보고하지 않는다. 적용 **직전** 원격 active 를 붙들어 두고,
모호한 실패에서 원격 상태를 다시 읽는다.

| 원격 상태 | 처리 |
|---|---|
| 읽을 수 없음 | `deploy_unconfirmed` — **"직전 active 유지" 라고 적지 않는다** |
| 새 버전으로 바뀌어 있음 | 직전 값으로 **원격 rollback** 후 `remote_apply_failed_rolled_back` |
| 직전 값 그대로 | `remote_apply_failed` (계약대로 유지됨) |

### 13-4. 운영 중 버전을 기각할 수 있었음 (P1)

`reject()` 가 대상이 active 인지 안 봤다. 허용하면 active pointer 는 그대로인데
그 행이 `approved_at=NULL · rejected_at!=NULL` 이 된다 — **지금 돌아가는 설정이
동시에 기각 상태**인 모순이다.

`store.CannotRejectActive` 로 거부하고 API 는 **409** 를 낸다.

### 13-5. rollback 테스트가 helper 만 검사 (P2)

`_restore()` 만 직접 불러서 `activate → readback 실패 → rollback` 배선이 끊겨도
통과했다. **실제 `apply_file()` 을 태우도록** 바꿨다.

```text
test_apply_file_rolls_back_active_on_readback_mismatch
  진짜 activate 가 일어난 뒤 _readback_matches 만 False → active 가 v1 로 복원
test_apply_file_succeeds_and_activates_when_readback_matches
  반대편 — 정상 경로에서 active 가 실제로 바뀐다
```

### 13-6. 테스트·역검증 보강

| r2 지적 | 대응 |
|---|---|
| 다중 버전 경로 미검증 | `test_past_deployed_version_is_not_offered_for_retry` 외 3건 |
| 재시도 후 승인 시각 불변 미검사 | `test_retry_does_not_rewrite_approved_at` (API 재호출 실측) |
| 원격 성공 후 SSH 실패 미검증 | `test_ambiguous_remote_failure_reconciles` · `test_unreadable_remote_is_reported_as_unconfirmed` |
| rollback 이 helper 만 | §13-5 |
| 역검증이 결함을 못 잡음 | **13 → 17가드** (⑭~⑰ 이 r2 4건에 대응) |

### 13-7. 결과서 오보고 정정 (A-2)

| r2 서술 | 실제 |
|---|---|
| P1 6건 전부 대응 | 2·3 이 다중 버전·모호 실패에서 미완 → §13-1·13-3 |
| 재승인 불필요 | 재시도가 `approved_at` 을 덮어썼다 → §13-2 |
| 실패 시 OCI active 보존 | 모호 실패 경로에 구멍 → §13-3 |
| §2.4 수정 3건 | **4건** — `app/market_refresh_service.py` 누락이었다 |

---

## 14. r3 REJECTED — P1 2건 · B-1 · B-6 · A-2 대응 (검증자 2026-09-18)

> 검증자는 "직전 r2 보고와 코드가 동일" 이라고 적었으나, 지적 중
> `rollback_impossible` 은 **r2 대응 때 새로 쓴 코드**다(§13-3). 제출은 동일하지
> 않았다. 다만 **지적 5건은 전부 실재했고 전부 인정**한다 — 아래는 그 대응이다.

### 14-1. stale 화면에서 옛 후보를 승인·배포할 수 있었음 (P1)

조회는 최신본만 보여주는데 `approve-and-apply` 는 **아무 버전이나** 받았다.
화면을 오래 열어둔 사이 새 후보가 산출되면, 화면과 실제로 나가는 설정이 갈린다.

```python
current, _state = store.actionable_version()
if current is None or current["config_version_id"] != req.config_version_id:
    raise HTTPException(409, "화면이 오래됐다. 새로고침 후 다시 시도 …")
```

재시도(`approved_not_deployed`)도 최신본이므로 게이트를 통과한다 — 정상 경로를
막지 않는지 테스트로 고정했다.

### 14-2. active 사전 조회 실패 후에도 적용 진행 (P1)

`prior_read_ok` 가 `False` 여도 원격 적용을 계속한 뒤 `rollback_impossible` 을
냈다. **그 시점엔 이미 늦다** — 되돌릴 기준 없이 원격이 바뀐 뒤다.

```text
전: 사전 조회 실패 → 적용 진행 → 모호 실패 → rollback_impossible (active 불명)
후: 사전 조회 실패 → precheck_failed 로 **적용을 시작하지 않는다**
```

`rollback_impossible` 분기는 도달 불가가 되어 삭제했다. 테스트가 "적용 명령이
아예 호출되지 않는지" 를 확인한다.

이 수정으로 `deploy_unconfirmed` 경로도 **좁아졌다** — 사전 조회는 됐고, 적용이
모호하게 실패했고, **사후** 조회까지 안 되는 경우만 남는다.

### 14-3. 손상 payload 를 빈 객체로 숨김 (B-1 fallback)

```python
# 전: except (KeyError, TypeError, ValueError): return {}
#     → 내용이 깨진 버전이 화면에 "0개 사업군" 으로 보인다.
#       정상적으로 비어 있는 것과 구분되지 않는 거짓 표시다.
# 후: PayloadCorrupt 로 올리고, /state 는 payload_error 로 그대로 내려준다.
```

카드는 값을 지어내지 않고 **"저장된 설정을 읽지 못했습니다"** 와 원인을 보여주며
승인·기각 버튼을 내린다.

### 14-4. rollback 역검증이 helper 만 호출 (B-6)

역검증 ⑩ 이 `_restore()` 를 직접 불러서 `activate → readback → rollback` 배선이
끊겨도 통과했다. **실제 `apply_file()` 을 태우도록** 바꿨고, 무력화 쪽도
`_restore` 를 no-op 로 만들어 같은 체인을 돌린다.

```text
가드 있을 때   apply_file rc=2 · active = 직전본으로 복원
무력화하면     실패를 반환하면서 active 는 새 버전으로 남는다
```

### 14-5. 결과서 테스트 건수 오보고 (A-2)

| r3 서술 | 실제 |
|---|---|
| 프론트 `IntradayConfigCard.test.tsx` **8**건 | r3 시점 11건 (현재 12건) |
| 통합 테스트 32건 | r3 시점 44건 (현재 51건) |

**원인은 검증 스크립트의 구멍**이다. 줄 수·합계·헤더는 대조했지만
`| **8** |` 같은 **테스트 건수 컬럼과 본문 건수 표기를 안 봤다.** 그래서
"문서 수치 불일치 0건" 이 성립하지 않았다.

`docverify3` 로 확장해 ⑤ 표 컬럼 · ⑥ 본문 `— 통합 N건` / `N passed <path>` 를
추가했고, 즉시 오보고 3건을 잡아 자동 정정했다. 이 종류의 오보고가 반복되지
않는다.

### 14-6. 테스트 보강

```text
test_stale_screen_cannot_apply_an_older_candidate      옛 버전 POST → 409
test_current_actionable_version_still_applies          정상 경로 미차단
test_retry_of_the_current_version_passes_the_gate      재시도 미차단
test_deploy_stops_when_prior_active_is_unreadable      적용 명령 미호출
test_rollback_impossible_path_is_gone                  분기 소멸
test_unreadable_remote_after_apply_is_unconfirmed      좁아진 경로
test_corrupt_payload_is_surfaced_not_hidden            손상 노출
test_healthy_payload_has_no_error                      정상 시 무영향
IntradayConfigCard "깨진 설정을 0개로 그리지 않는다"     화면 계약
```

역검증 **17 → 20가드** (⑱ stale 차단 · ⑲ 사전조회 실패 중단 · ⑳ 손상 노출).

### 14-7. 설계자 확인이 필요한 항목 — `deploy_unconfirmed` (A-3)

검증자 지적대로 **설계자가 승인한 실패 계약이 아니다.** 다만 이것을 없애려면
"원격 상태를 모르는 경우" 를 기존 `remote_apply_failed`(= 직전 active 유지) 로
적어야 하는데, 그건 **모르는 것을 안다고 쓰는 것**이다.

§14-2 로 발생 범위가 크게 좁아졌다. 계약 채택 여부는 설계자 판단이며,
§10 에 사용자 확인 항목으로 올렸다.

---

## 15. 설계자 `deploy_unconfirmed` 승인 반영 (2026-09-18)

r3 의 유일한 잔여 반려 사유가 설계자 판정으로 해소됐다. 설계 기록은
`docs/ai_design/POC3/POC3-02C_INTRADAY_DECISION_BRIEFING_DESIGN_V1.md` §12.

```text
DESIGNER_DECISION   = APPROVED      DEPLOY_UNCONFIRMED = VALID_STATE
BOUNDED_READ_RETRY  = IMPLEMENT_NOW AUTOMATIC_REAPPLY  = FORBIDDEN
```

### 15-1. 계약 변경 1건 — 모호 실패 시 rollback 을 **하지 않는다**

§13-3 에서 나는 "적용된 것이 확인되면 되돌린다" 로 만들었다. 설계자 확정은
**다르다** — 목표 version/hash 가 확인되면 `deployed`(성공)다.

```text
전: 모호 실패 → 조회 → 목표 확인 → 원격 rollback → remote_apply_failed_rolled_back
후: 모호 실패 → 조회 → 목표 확인 → **deployed** (되돌리지 않는다)
```

되돌리면 멀쩡히 적용된 설정을 **우리 쪽 통신 사고로 날리는 셈**이다. 이 판정이
더 맞다. PC 측 `_remote_rollback()` 은 도달 불가가 되어 **삭제**했다
(원격 `apply_file` 내부의 재독출 rollback 은 성격이 달라 그대로 둔다).

### 15-2. read-back 재시도 — 조회만 3회

```python
READBACK_DELAYS = (0.0, 2.0, 5.0)

def reconcile_after_apply(target, *, want_id, want_hash, prior_id, prior_hash, sleep=None):
    ...  # 목표 확인 → deployed · 직전 확인 → remote_apply_failed
         # 3회 모두 실패/예상 밖 → deploy_unconfirmed
```

`sleep` 을 **호출 시점에 해석**한다. 기본 인자로 `time.sleep` 을 박았더니
import 때 고정돼 테스트가 실제로 7초를 잤다(실측 36.79s → 0.87s).

`_remote_active()` 가 **version 과 hash 를 함께** 돌려주도록 바꿨다. version 만
보면 내용이 다른 설정을 적용 완료로 단정할 수 있다(역검증 ㉓).

### 15-3. `deploy_unconfirmed` 일 때 동작

| 층 | 동작 |
|---|---|
| `deploy()` | `(False, "deploy_unconfirmed")` · PC active 갱신 **안 함** |
| API | `deploy_status = "UNCONFIRMED"` · 완료·실패로 단정 안 함 |
| 화면 | 「OCI 적용 여부 확인 필요」 + "자동으로 다시 보내지 않습니다" |

추정하지 않는다 — OCI active 가 무엇인지 쓰지 않는다.

### 15-4. focused test (설계자 지정 5건 + 1)

```text
test_reconcile_confirms_deployed_after_two_failed_reads  1·2회 실패 후 확인 성공
test_reconcile_confirms_prior_active_kept                직전 active 유지 확인
test_three_failed_reads_are_unconfirmed                  3회 전부 조회 실패
test_unexpected_version_is_unconfirmed                   예상 밖 version/hash
test_no_automatic_reapply_in_any_reconcile_path          3경로 모두 apply 1회
test_reconcile_is_read_only                              재시도 경로에 쓰기 0
```

`slept == [2.0, 5.0]` 로 **간격까지** 고정했다. 프론트 2건이 화면 문구를 고정한다.

### 15-5. 역검증 20 → 24가드

```text
㉑ read-back 3회 재시도      1회만 조회하면 같은 상황이 unconfirmed 로 끝난다
㉒ 직전 active 유지 확정      구분 안 하면 적용 안 된 경우도 '모름' 으로 뭉뚱그려진다
㉓ 예상 밖 상태 추정 금지      version 만 보면 다른 설정을 완료로 단정한다
㉔ 재시도는 조회 전용         apply 재실행은 OCI 를 한 번 더 건드린다
```

### 15-6. OCI 실측 — **이 시점 값이며 이후 바뀌었다**

```text
2026-09-18 승인 시도 **이전** 측정값:
git                      b077641f  (거래일 평일 fallback …)
설정 JSON                 없음
intraday 테이블            없음
→ 당시 상태 = not_deployed.

승인 시도 이후 값은 §17. 나는 이 표를 재측정 없이 §16 에 옮겨 적었고,
그것이 r6 A-2 오보고가 됐다.
```

### 15-7. KS-10 — NEAR 6 → 7 (신규 1건)

역검증 가드를 20 → 24 로 늘리면서 `scripts/ops02c/reverse_verify_guards.py` 가
**605줄**이 됐다. 백엔드 근접 임계(≥600)에 새로 들어왔다.

```text
TRIGGER 0건 (임계 650 미만)
NEAR    7건 — 신규 1건이 이 파일이다
```

트리거는 아니지만 **다음 라운드에 가드를 더 붙이면 넘는다.** 지금 쪼개면 이번
검증 대상이 늘어나므로 그대로 두고 보고한다. 분리가 필요해지면 검증 종료 후
Cleanup 으로 잡는 것이 맞다고 본다 — 판단은 검증자·설계자 몫이다.

---

## 16. r5 REJECTED — 미확정 상태를 실패로도 단정 (검증자 2026-09-18)

인정한다. 설계 §12-4(완료·실패 추정 금지) 위반이었다.

### 16-1. 두 분기가 동시에 참이었다

```text
deploy_status = deploy_unconfirmed    → "완료도 실패도 아닙니다"
action_state  = approved_not_deployed → "OCI 전달만 실패했습니다"
```

승인은 됐고 active 는 아니므로 `approved_not_deployed` 는 **맞다.** 문제는 그
공통 분기를 배타 처리하지 않은 것이다. 결과적으로 한 화면에 제목
「적용하지 못한 설정」과 "전달만 실패했습니다" 가 같이 떴다.

```tsx
const isUnconfirmed = state.deploy_status === "deploy_unconfirmed";
const isRetry = state.action_state === RETRY && !isUnconfirmed;
```

제목도 3분기로 바꿨다 — 미확정이면 「OCI 적용 여부 확인 필요」. 재시도 버튼은
양쪽 모두에서 살아 있다(조치는 같으므로).

### 16-2. 테스트가 못 잡은 이유 (B-6)

`"적용 실패"` · `"적용 완료"` 라는 **정확한 문자열 2개만** 금지해서
`"OCI 전달만 실패했습니다"` 를 그대로 통과시켰다. 단정 표현 전체를 막는다.

```text
금지: 적용 실패 · 적용 완료 · 적용하지 못한 · 전달만 실패 ·
      실패했습니다 · 다시 승인할 필요
추가: h3 제목이 ["OCI 적용 여부 확인 필요"] 하나뿐인지
추가: 미확정에서도 재시도 버튼이 있는지
```

`"완료도 실패도 아닙니다"` 때문에 **낱말 "실패" 자체는 금지할 수 없다** — 단정
구문만 막는다.

### 16-3. 사용자 실화면에서 나온 `precheck_failed` (지시문 외 1건)

사용자가 승인 버튼을 눌렀고 `precheck_failed` 로 멈췄다. **가드는 정상 동작**했다.

```text
버전    intraday-20260916T144047   승인 2026-09-18T12:56:10Z
active  없음
전달    precheck_failed
OCI     설정 JSON 없음 · intraday 테이블 없음 (읽기 전용 실측)
```

원인은 **OCI 에 이 기능 코드가 아직 없다는 것**이다.

```text
OCI $ ls app/intraday_config/          → No such file or directory
OCI $ from app.intraday_config import store → ModuleNotFoundError
```

`_remote_active()` 는 OCI 에서 이 패키지를 import 해 active 를 읽는다. 커밋·푸시·
배포 전이므로 읽을 수 없는 것이 맞다. **결함이 아니라 순서 문제**다.

```text
검증자 통과 → 커밋 → 푸시 → OCI 배포 → 그때 승인 버튼
```

다만 메시지가 원인을 알려주지 않아 사용자가 혼란스러워했다. 문구만 고쳤다
(동작 무변경).

```text
전: 적용 전 OCI active 를 읽지 못했다. 되돌릴 기준이 없어 중단한다
후: OCI 상태를 읽지 못해 중단했다. 원격에 아무것도 쓰지 않았다.
    OCI 에 이 기능 코드가 아직 배포되지 않았거나 접속이 안 되는 경우다
    (문구가 사실이 되도록 **순서까지** 고쳤다 — §17-1)
```

---

## 17. r6 REJECTED — precheck 전에 원격을 이미 바꿨다 (검증자 2026-09-18)

인정한다. **실행 순서를 직접 재현한 지적이 맞고 내 보고가 틀렸다.**

### 17-1. 순서가 거꾸로였다

```text
전: 승인확인 → ssh → export → scp JSON → mv 정본 → scp 적용스크립트
                                                      → precheck ← 너무 늦다
후: 승인확인 → ssh → **precheck** → export → scp → mv → scp → apply
```

`precheck_failed` 를 반환하면서 "원격을 건드리지 않았다" 고 적었지만, 그 시점에
**원격 정본 JSON 은 이미 교체돼 있었고** 임시 적용 스크립트도 남아 있었다.

정리도 보장하지 않았다. 업로드 뒤 실패하면 `rm` 에 도달하지 못했다.

```python
def cleanup() -> None:                      # 임시파일 일괄 제거
    _run(["ssh", target, f"rm -f {remote_tmp} {remote_apply}"], timeout=30)

def fail_after_upload(reason, err=None):    # 업로드 뒤 실패는 전부 여기로
    cleanup()
    return fail(reason, err)
```

업로드 이후 실패 경로 **5곳**이 전부 정리를 거친다(역검증 ㉖).

### 17-2. OCI 실측 — 파일 2개가 실제로 남았다

```text
/home/ubuntu/krx_hyungsoo/state/three_push/params/
  -rw-r--r--  33884  Sep 18 21:56  latest_intraday_alert_config.json
  -rw-r--r--   5284  Sep 18 21:56  .apply_intraday_config_oci.py
```

`21:56 KST = 12:56 UTC` — 사용자 승인 시각과 일치한다.

**OCI active·DB 는 무변경이다.** `intraday_alert_config_*` 테이블이 OCI 에 아예
없고 `app/intraday_config/` 패키지도 없다. 두 파일은 **아무 코드도 읽지 않는다** —
cron 도 러너도 참조하지 않는다. 운영 영향 0, 다만 있어서는 안 될 파일이다.

### 17-3. 정리는 사용자 승인 대상

삭제는 OCI **쓰기**다. 읽기 전용 원칙에 따라 임의로 하지 않는다.

```text
rm -f /home/ubuntu/krx_hyungsoo/state/three_push/params/.apply_intraday_config_oci.py
rm -f /home/ubuntu/krx_hyungsoo/state/three_push/params/latest_intraday_alert_config.json
```

§10 에 사용자 확인 항목으로 올렸다. 다음 정상 전달이 두 파일을 덮어쓰므로
급하지는 않다.

### 17-4. 테스트가 못 잡은 이유 (B-6)

`fake_run` 이 `--json` 이 들어간 적용 명령만 셌다. 그 **앞**의 scp·mv 는 아예
기록하지 않아 "원격을 건드리지 않는다" 를 증명하지 못했다.

```python
if cmd[0] == "scp" or (cmd[0] == "ssh" and any(w in joined for w in ("mv ", "rm ", "> "))):
    writes.append(cmd)        # 원격을 바꾸는 **모든** 명령
```

| 테스트 | 고정 내용 |
|---|---|
| `test_deploy_writes_nothing_remote_when_precheck_fails` | precheck 실패 시 `writes == []` |
| `test_precheck_runs_before_any_remote_write` | 소스 순서 — precheck 이 `scp` 보다 앞 |
| `test_temp_apply_script_is_cleaned_on_failure` | 실패해도 `rm -f` 가 임시 스크립트 포함 |

역검증 24 → **26가드** (㉕ precheck 선행 · ㉖ 실패 시 정리).

### 17-5. 결과서 오보고 정정 (A-2)

| r6 서술 | 실제 |
|---|---|
| `OCI_DEPLOY_EXECUTED = 0` | 시도 1회 (사용자 승인) · 적용 0회 · **원격 파일 2개** |
| 실제 OCI 전달 미수행 | 전달 시도했고 실패. 원격 파일은 남았다 |
| OCI 접속·쓰기 0건 | 쓰기 **3회**(scp·mv·scp) 발생 |
| OCI 설정 JSON 없음 | **승인 이전** 측정값이다. 이후 생겼다 |
| OCI 를 건드리지 않았다 | 거짓이었다. 이제 순서를 고쳐 **사실이 됐다** |

`§15-6` 표에 "이 시점 값" 임을 명시했다. **재측정 없이 옛 측정값을 현재로 옮겨
적은 것**이 이 오보고의 원인이다 — 같은 실수를 반복했다.

### 17-6. 프론트 회귀 1건 불안정 (검증자 B-6)

검증자 첫 실행 `206/207`, 재실행 `207/207`. 내 실행에서는 재현되지 않았다
(`207/207`). 이번 라운드 변경 파일(`IntradayConfigCard`) 16건은 양쪽 모두 안정
통과다. 원인 미상이며 **해결했다고 적지 않는다.**

---

## 18. r7 REJECTED — P2 3건 (검증자 2026-09-18)

기능 코드 결함은 없었다. 결과서 현재 상태 모순 2건과 검증 공백 1건이다.

### 18-1. §10 항목이 현재 화면과 달랐다 (A-2 · A-3)

「승인하고 OCI 적용」이라고 적었는데 현재는 이미 승인돼 있어 버튼이
「OCI 적용 재시도」다. §10 을 **실측값 블록으로 교체**했다.

```text
action_state   approved_not_deployed
version        intraday-20260916T144047-642949
PC active      없음
deploy_status  precheck_failed
화면 버튼       「OCI 적용 재시도」
```

### 18-2. 확정된 설계 판단을 다시 대기로 적었다 (A-3)

`deploy_unconfirmed` 는 설계서 §12 · 결과서 §15 에서 **승인 완료**인데 §10
사용자 확인 목록에 "설계자 판단을 받아야 한다" 가 남아 문서가 자기모순이었다.
삭제하고 승인 완료임을 명시했다.

### 18-3. 정리 가드가 약했다 (B-6)

㉖ 이 `fail_after_upload(` **개수**를 셌는데 거기엔 함수 정의도 포함된다. 호출
한 곳이 빠져도 4로 남아 통과했다 — 내가 만든 가드가 자기 계약을 못 지켰다.

실제 계약을 본다: **첫 원격 쓰기부터 `cleanup()` 까지 구간에 맨 `fail(` 이
하나도 없어야 한다.**

```text
가드 있을 때   쓰기~정리 구간: 맨 fail 0건 · fail_after_upload 4건
무력화하면     호출 1곳을 맨 fail 로 되돌리면 맨 fail 1건 → EXIT=1 (실측)
```

테스트도 **분기별로 실제 태운다** — 이전에는 apply 실행 실패 경로만 봤다.

```text
test_every_post_upload_failure_cleans_up[scp_json]   scp_failed
test_every_post_upload_failure_cleans_up[mv]         rename_failed
test_every_post_upload_failure_cleans_up[scp_apply]  apply_upload_failed
→ 세 분기 모두 rm -f 가 .apply_intraday_config_oci.py 를 포함하는지 확인
```

### 18-4. 프론트 간헐 실패 — **원인 오진 1회 후 실제 수정** (r8 에서 정정)

r7 때 나는 실패 소요가 `1,003~1,008ms` 인 것만 보고 **RTL `waitFor` 기본 한도
1,000ms 가 빠듯한 것**이라 추정해 `vitest.setup.ts` 에 `asyncUtilTimeout: 5000`
을 넣었다. **틀린 진단이었다.** 검증자가 5초 설정 후에도 `206/207` 을 재현했고,
실패 단언이 **동기 `getByText`** 라는 것까지 짚어 줬다 — 동기 단언은 timeout 을
쓰지 않으므로 그 설정은 애초에 그 경로에 닿지 않는다.

`vitest.setup.ts` 는 **되돌렸다**(`git status` 0건). 근거가 사라진 변경이다.

#### 진짜 원인

```tsx
// renderView() 가 기다리던 것
await screen.findByText("코스피 가격 흐름");
```

`KospiHeadline.tsx:36` 의 이 문자열은 **데이터와 무관한 정적 라벨**이다.

```tsx
<div className="tc-label">코스피 가격 흐름</div>   // 마운트 즉시 존재
```

즉 이 대기는 **마운트만 기다리고 조회 resolve 는 기다리지 않았다.** 뒤따르는
동기 `getByText` 들이 조회와 경쟁했고, 부하가 걸리면 졌다.

`KospiHeadline` 은 로딩 표시가 없다는 점이 겹쳤다 — 성공 전에는 그냥
"자료 없음" 을 그리므로 "불러오는 중" 이 사라지는 것만으로도 부족하다.

#### 수정 — 데이터가 있어야만 나오는 값을 기다린다

```tsx
await waitFor(() => expect(screen.queryByText(/불러오는 중/)).toBeNull());
await screen.findByText(/마지막 자료 기준일 \d{4}-\d{2}-\d{2}/);
```

기준일은 `fmtKstDate(null) === "자료 없음"` 이고 조회 성공 시에만 `YYYY-MM-DD`
가 된다. **어느 fixture 에서도 통하는 앵커**다 — `kospi: {}` 로 두는 B-1
테스트까지 포함해서.

> 첫 시도로 `/1개월/` 을 앵커로 썼다가 B-1 에서 깨졌다(그 fixture 는 `kospi` 가
> 비어 수익률 블록을 안 그린다). 그래서 기준일로 바꿨다.

#### 실측

```text
무부하 연속 10회        207/207 × 10
CPU 부하 8프로세스 5회   207/207 × 5     ← 검증자 환경 재현 시도
해당 파일 단독          35/35
```

부하를 건 상태에서도 재현되지 않는다. 다만 검증자 환경에서 재발 여부는
확인이 필요하다 — **이번에는 원인을 특정하고 그 지점을 고쳤다.**

---

## 19. r8 REJECTED — P2 2건 (검증자 2026-09-18)

기능 코드는 통과였다. 문서 수치 1건과 **내가 오진한 프론트 불안정성** 1건이다.

### 19-1. 반복 횟수 자기모순 (A-2)

§7 은 "연속 9회", §18 은 "6회" 라고 적었다. 서로 다른 시점의 실행을 각각 적고
합치지 않아 문서 안에서 모순이 됐다.

§18-4 를 **이번 라운드 실측으로 통째 교체**하고 §7 도 같은 값으로 맞췄다.

```text
무부하 연속 10회        207/207 × 10
CPU 부하 8프로세스 5회   207/207 × 5
→ 합계 15회
```

### 19-2. 프론트 불안정 — 내 진단이 틀렸다 (A-3 · B-6)

r7 에서 나는 **관측값 하나(1,003~1,008ms)** 만 보고 `waitFor` 한도 문제로
단정했다. 검증자가 5초 설정 후에도 `206/207` 을 재현했고, **실패 단언이 동기
`getByText`** 라는 것을 짚었다 — 동기 단언은 async timeout 을 쓰지 않으므로
그 설정은 그 경로에 닿지도 않는다.

`vitest.setup.ts` 변경은 **되돌렸다.** 근거가 사라진 변경이고, 검증자가
`범위 폭주 MINOR` 로 지적한 항목이다. 지금 `git status` 에 이 파일은 없다.

실제 원인과 수정은 §18-4 에 적었다. 요지는 `renderView()` 가 기다리던
「코스피 가격 흐름」이 **정적 라벨**이라 데이터 로드를 보장하지 못했다는 것이다.

### 19-3. 이 라운드에서 내가 반복한 실수

r6 은 "재측정 없이 옛 값을 현재로 옮겨 적기", r8 은 "관측 하나로 원인 단정하기"
였다. 둘 다 **실측 없이 단정**한 것이 공통이다.

이번에는 고친 뒤 **부하를 걸어 15회 돌려** 확인했고, 그래도 검증자 환경에서
재발할 수 있으므로 "해결" 이 아니라 **"원인을 특정하고 그 지점을 고쳤다"** 로
적는다.

---

## 20. VERIFIED 이후 운영 실행에서 터진 2건 (2026-09-18 · OCI 배포 후)

사용자가 OCI `git pull` 후 승인·적용 화면의 **두 버튼을 모두 눌렀고 둘 다
실패**했다. 서로 다른 버그이며 **둘 다 원격에서 실행해야만 드러난다.**

### 20-1. 「장중 급등락 설정」 — 내 버그 · 업로드 위치에서 루트를 못 찾음

```text
ModuleNotFoundError: No module named 'app'
  at /home/ubuntu/krx_hyungsoo/state/three_push/params/.apply_intraday_config_oci.py
```

```python
_PROJECT_ROOT = Path(__file__).resolve().parents[1]   # ← 원인
```

| 위치 | `parents[1]` |
|---|---|
| PC `scripts/` | `krx_hyungsoo` ✅ |
| 원격 `state/three_push/params/` | `state/three_push` ❌ |

호출부의 `cd` 는 소용없다 — `python <경로>` 는 **스크립트 디렉터리**를
`sys.path[0]` 에 넣지 cwd 를 넣지 않는다.

**수정** — 루트를 자기 위치에서 추측하지 않는다. `--project-root` 를 **필수
인자**로 받고 호출부가 넘긴다. `app` import 는 bootstrap 이후로 미룬다.

### 20-2. 「현재 운영 기준」 — 기존 버그 · 복제된 허용 목록이 낡음

```text
upload_status  ok          ← 전송은 성공했다
verify_status  failed
error          enabled_push_kinds 허용값 위반: 'holdings_risk_alert'
```

| 파일 | 목록 |
|---|---|
| `app/three_push_runner_common.py` (정본) | … + **holdings_risk_alert** |
| `scripts/verify_three_push_param_oci.py` (복제) | 없음 |

`holdings_risk_alert` 가 `POC3-OPS-02A`(commit `5d2614d6`)에서 정본에만 추가됐다.
**그때부터 이 버튼은 계속 실패하고 있었다** — 이번 작업과 무관한 기존 결함이다.

복제 자체는 불가피하다(OCI `/tmp` 에서 `python3` standalone 실행이라 `app` 을
import 할 수 없다). 복제를 유지하되 **어긋남을 테스트가 막는다.**

### 20-3. 왜 못 잡았나

**검증자**: 두 건 다 원격 실행에서만 드러나므로 로컬 검증이 구조적으로 닿지
않는다.

**나**: §8 에 "3~8단계 실행 미검증" 을 한계로 **신고는 했다.** 그러나 실행해야만
알 수 있는 게 아니었다 — `parents[1]` 과 "`params/` 로 업로드" 는 내가 쓴 두
파일에 나란히 있었다.

결정적으로 내 테스트가 이랬다.

```python
rc = apply_mod.apply_file(...)      # PC 안에서 직접 호출 — app 이 이미 import 됨
```

계약은 "이 스크립트가 **원격 위치에서** 동작한다" 인데, 검사한 것은 "app 이 이미
있는 곳에서 함수가 동작한다" 였다. `sys.path` 로직을 한 번도 태우지 않았다.

**어제 메모리에 적은 "테스트는 diff 가 아니라 계약 문장에서 쓴다" 를 바로 다음
날 다시 어겼다.**

### 20-4. 이번엔 실행으로 검사한다

`tests/test_remote_script_execution_contracts.py` (8건).

```text
test_apply_script_runs_from_a_deep_upload_path      원격과 같은 3단계 깊이로
                                                    복사해 subprocess 실행
test_apply_script_requires_project_root             루트를 추측하지 않는다
test_sync_passes_project_root_to_remote             호출부가 실제로 넘긴다
test_apply_script_does_not_derive_root_...          parents[N] 코드 라인 부재
test_verify_script_allowed_kinds_match_canonical    복제본 == 정본
test_verify_script_accepts_holdings_risk_alert      실행으로 통과 확인
test_verify_script_still_rejects_unknown_kinds      느슨해지지 않았는지 (×2)
```

무력화 실증 — `parents[1]` 로 되돌리면 **2건이 실제로 실패**한다.

### 20-5. 검증

```text
전체 회귀   1,684 passed / 0 failed   (직전 1,676 -> +8)
역검증      26가드 · EXIT=0
프론트      18 files / 207 tests
black 351 · flake8 0 · tsc 0
라이브 DB   회귀 전후 sha256 동일
```

### 20-6. 아직 안 한 것

**OCI 재배포 전에는 두 버튼 모두 여전히 실패한다.** 수정은 로컬에만 있다.
커밋·푸시·OCI `git pull` 이 필요하며 사용자 승인 대상이다.
