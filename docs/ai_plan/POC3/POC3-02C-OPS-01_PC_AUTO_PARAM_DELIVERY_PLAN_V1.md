# POC3-02C-OPS-01 — PC 자동 산출 · 승인 · OCI 전달 개발 PLAN V1

작성일: 2026-09-16 · 작성자: 개발자(VSCode Claude) · 수신: 설계자

```text
CURRENT_ACTION = PLAN_V1
IMPLEMENTATION = PLAN 승인 후
CODE_CHANGE_SO_FAR = 0
```

조사 내용은 반복하지 않는다. 앞선 두 조사서를 전제로 한다.

- `docs/ai_result/POC3/POC3-OPS-02C_SECTOR_ETF_SURVEY.md`
- `docs/ai_result/POC3/POC3-OPS-02C_PARAM_DELIVERY_SURVEY.md`

---

## 0. ⚠ 착수 전 확정이 필요한 실측 사실 3건

PLAN 을 쓰면서 새로 드러났다. **이 셋이 정해지지 않으면 §5 사슬을 설계할 수 없다.**

### 0-1. PC 에 `runtime_state.sqlite` 가 없다

```text
PC   state/runtime/runtime_state.sqlite   →  존재하지 않음
OCI  state/runtime/runtime_state.sqlite   →  307,200 bytes · version 2건 · active pointer 1건
```

설계자 §3 은 **"DB version/approval/active 가 SSOT"** 이고 §5 는 **"PC 승인 DB →
전송 JSON export"** 다. 그런데 **PC 에는 그 DB 가 없다.**

현재 OCI DB 의 active pointer 는 이렇게 들어갔다.

```text
param-20260907T152806-255383  approved_by='user'  activated_by='create_script_approve'
```

즉 **OCI 에서 직접 CLI 를 실행해 만든 것**이지, PC 에서 전달된 것이 아니다.

### 0-2. sync 는 JSON 만 옮기고 DB 를 건드리지 않는다

`scripts/sync_three_push_runtime_param.py` 에 `sqlite` · `create_param_version` ·
`activate_param_version` 호출이 **0건**이다. scp + atomic rename + verify 뿐이다.

`verify_three_push_param_oci.py` 도 JSON 금지어 검사(`_collect_forbidden`)만 한다.

### 0-3. 그런데 OCI 러너는 DB 만 읽는다

```text
read_active_param_dict()  — "JSON fallback 코드 경로 없음" (fail-closed)
```

**전달된 JSON 과 러너가 읽는 DB 사이에 연결이 없다.**

> **설계자 §5 지시대로 "OCI DB 적재·활성화 단계가 없다" 를 명시한다. 신규 구현
> 범위다.** 다만 이것은 이번 Step 만의 문제가 아니라 **기존 `runtime_param` 전달
> 경로에 이미 있는 공백**이다. 지금 OCI 가 도는 것은 사람이 OCI 에서 직접 CLI 를
> 돌려 놓았기 때문이다.

**판단 요청 A** — 이 공백을 (a) 이번 Step 에서 함께 메울지, (b) `runtime_param`
기존 경로는 그대로 두고 신규 번들만 완결된 사슬로 만들지.
개발자 의견은 **(b)** 다. (a) 는 이미 운영 중인 PUSH 3종의 PARAM 경로를 건드려
회귀 위험이 크다.

---

## 1. PC 자동 산출 트리거

| 항목 | 내용 |
|---|---|
| 트리거 | 기존 PC universe·ML 분석 작업 **완료 시점에 이어서** 자동 계산 |
| 별도 cron | **없음** (설계자 지시) |
| 재생성 억제 | 입력 hash 동일 → **새 버전 생성 안 함** |

### 1-1. 입력 hash 정의

```text
input_hash = sha256(
    공식 CSV sha256          # 기초지수·종목 메타 (현재 계약에 이미 있음)
  + 가격 기준일              # krx_etf_daily_price_unadjusted 최신 date
  + 선정 규칙 version        # 아래 1-2
  + 보유 ticker 정렬 목록     # 보유 변동 시 재계산 필요
)
```

같은 `input_hash` 면 **후보 생성 자체를 건너뛴다.** 산출물이 같은데 버전만 늘어
승인 요청이 반복되는 것을 막는다.

### 1-2. 선정 규칙 version

산식을 바꾸면 `input_hash` 가 같아도 결과가 달라진다. 규칙에 version 을 붙여
hash 에 포함한다. **이번 Step 의 초기 규칙은 §1-3 이다.**

### 1-3. ⚠ 판단 요청 B — 사업군 병합 기준이 아직 없다

`SECTOR_ETF_SURVEY §3` 실측: 기초지수 단위로 뽑으면 **반도체만 19그룹**,
상위 40 중 9개가 반도체 계열이다. 설계자 목표는 "사업군 20~40개 · 사업군당 1개" 다.

**개발자가 임의 라벨을 만들지 않는다.** 다음 중 하나를 설계자가 정해야 한다.

| 안 | 내용 | 결과 |
|---|---|---|
| B-1 | 기초지수 단위 그대로 (병합 없음) | 281그룹 → 상위 N개 컷. 반도체 편중 |
| B-2 | 공식 지수명 토큰 사전 정의 (반도체·2차전지·조선…) | 사전을 **사람이 확정**해야 함 |
| B-3 | 구성종목 중복도 기반 자동 병합 | `etf_constituents` 400행뿐 — **데이터 부족** |

개발자 의견은 **B-2** 다. B-3 은 데이터가 없고, B-1 은 "사업군" 이 아니다.
B-2 의 사전은 `INTRADAY_ALERT_CONFIG` 안에 **데이터로** 담아 버전 관리한다
(코드 하드코딩 아님).

---

## 2. 신규 단일 승인 번들 `INTRADAY_ALERT_CONFIG`

두 부분을 **하나의 version/checksum 으로 원자 적용**한다.

```text
INTRADAY_ALERT_CONFIG  v1
├─ sector_representative_universe
│    sector_key            공식 지수명 토큰 (B-2 사전)
│    sector_label          사용자 표시명 = sector_key 그대로 (임의 번역 없음)
│    representative        { ticker, short_name, index_agency, index_name }
│    alternates            [ 동일 구조 ]
│    selection_basis       { rule_version, metric, data_asof }
├─ intraday_alert_policy
│    surge / drop 판정 임계
│    검토 / 회피 분류 규칙
│    cooldown · 중복 억제
│    회차별 · 일별 발송 상한
└─ meta
     config_version_id · created_at · input_hash · source_hash_sha256
     approved_at · approved_by · rule_version
```

**임계값·분류 규칙의 구체 수치는 이 PLAN 에서 정하지 않는다.** 설계자가
"먼저 구조를 정하고 산식은 나중" 이라고 했고, 목업 없이 숫자를 정하면
`OPS-01C` 때와 같은 "이름만 spike" 가 반복된다.

---

## 3. 저장 경계

| 항목 | 결정 |
|---|---|
| 기존 `runtime_param` | **논리적으로 분리** — 테이블을 공유하지 않는다 |
| DB 파일 | 기존 `state/runtime/runtime_state.sqlite` **재사용** |
| 신규 DB 파일 | **금지** (설계자 지시) |
| SSOT | DB 의 version / approval / active |
| JSON | **전송·archive 전용**. 러너가 읽지 않는다 |

### 3-1. 신규 테이블 3개 (기존 `runtime_param_*` 패턴 복제)

```sql
intraday_alert_config_version   -- config_version_id PK · created_at · input_hash
                                -- source_hash_sha256 · rule_version · payload_json
                                -- approved_at · approved_by      (NULL 허용)
intraday_alert_config_active    -- scope PK · config_version_id · activated_at · activated_by
intraday_alert_config_sync      -- config_version_id · target · synced_at · verify_status
```

`payload_json` 에 번들 전체를 넣는다. `runtime_param` 처럼 값을 flatten 하지
않는다 — universe 는 가변 길이 목록이라 flatten 이 맞지 않는다.

### 3-2. migration

`app/runtime_state_db.py` 의 기존 스키마 생성 경로에 3개 테이블을 **추가**한다.
기존 테이블은 건드리지 않는다. `CREATE TABLE IF NOT EXISTS` 로 재실행 안전.

---

## 4. 승인 강제 — **코드 게이트를 만든다**

조사 결과 현재 `activate_param_version` 은 `approved_*` 를 **검사하지 않는다**
(감사 필드일 뿐). 설계자가 확정한 `AUTO_PROMOTION_WITHOUT_APPROVAL = false` 를
코드로 강제한다.

```python
def activate_intraday_config(config_version_id, *, activated_by):
    row = get_version(config_version_id)
    if not row["approved_at"] or not row["approved_by"]:
        raise ApprovalRequired(config_version_id)   # ← 활성화 거부
    set_active_pointer(...)
```

| 규칙 | 구현 |
|---|---|
| 자동 산출은 **미승인 후보만** 생성 | 생성 시 `approved_at=NULL` |
| 사용자가 **버전 전체**를 승인/기각 | API 2개 (§7) |
| `approved_*` 없으면 activate 거부 | 위 게이트 |
| ETF 직접 선택 UI | **만들지 않는다** |

기존 `activate_param_version` 은 **건드리지 않는다**(운영 중 경로 · 회귀 위험).

---

## 5. PC→OCI 호출 사슬

설계자 §5 순서 그대로 구현한다. **굵게** 표시한 3단계가 신규다(§0-3).

```text
1. PC 승인 DB                     intraday_alert_config_version (approved)
2. 전송 JSON export               state/three_push/params/latest_intraday_alert_config.json
3. SCP → atomic rename            기존 sync 4단계 재사용
4. OCI verify                     금지어 + schema + source_hash 대조
5. **OCI DB version 적재**        원격에서 version row insert          ← 신규
6. **승인 확인**                   approved_at/by 존재 검사             ← 신규
7. **active pointer 갱신**        activate_intraday_config()          ← 신규
8. version/hash 재독출 대조        PC 값과 일치 확인
```

### 5-1. 5~7 단계 실행 방식

기존 sync 가 `verify_three_push_param_oci.py` 를 **일시 업로드해 원격 실행**하는
패턴을 그대로 쓴다. 신규 `apply_intraday_config_oci.py` 를 같은 방식으로 올려
원격에서 5~7 을 수행한다. **상시 배포 스크립트를 늘리지 않는다.**

### 5-2. PC DB 부재 문제 (§0-1)

PC 에 `runtime_state.sqlite` 가 없으므로 **첫 실행 시 생성**된다
(`CREATE TABLE IF NOT EXISTS`). 기존 `runtime_param_*` 테이블도 같이 생기지만
**PC 는 그 테이블을 쓰지 않는다** — 신규 3개 테이블만 사용한다.

---

## 6. 실패 계약

| 실패 지점 | 동작 |
|---|---|
| PC 산출 실패 | 새 후보 없음. 기존 승인 버전 유지 |
| 승인 없음 | activate 거부(§4). OCI 직전 active 유지 |
| 전달 실패 | atomic rename 미실행 → OCI 기존 JSON 유지 |
| verify 실패 | 5~7 미실행 → **OCI active pointer 불변** |
| OCI 적재 실패 | pointer 갱신 안 함 → 직전 active 유지 |

### 6-1. 기존 PUSH 3종 보호

```text
market_briefing · holdings_briefing · holdings_risk_alert  →  전부 유지
```

이번 Step 은 **번들 생성·승인·전달까지만**이다. 러너 발송 경로를 바꾸지 않는다
(그것은 `OPS-02`). 따라서 이번 Step 실패가 기존 발송을 막을 수 없다.

`OPS-02` 에서 소비할 때 적용할 계약을 미리 못박아 둔다.

- **holdings 경로 우선** — 보유 급락 판정을 먼저 계산한다.
- **후보 경로 실패가 holdings 발송을 막지 않는다** — 대표 ETF 조회·판정 실패는
  진단에만 남기고 보유 부분만으로 발송한다.

---

## 7. PC 화면

기존 `ThreePushParamCard` 의 3요소(현재 버전 · 반영 상태 · 적용 시각)를 재사용한
**신규 카드 1개**를 만든다. 기존 카드는 건드리지 않는다.

| 표시 | 출처 |
|---|---|
| 자동 산출된 변경 요약 | 직전 승인 버전 대비 diff |
| 추가 · 제외 · 교체 종목과 사유 | `selection_basis` |
| 데이터 기준일 | `data_asof` |
| 버전 / checksum | `config_version_id` · `source_hash_sha256` |
| 승인 / 기각 | 신규 API 2개 |
| OCI 적용 상태 | `intraday_alert_config_sync` |

**직접 종목을 고르는 편집 화면은 만들지 않는다.**

### 7-1. 신규 API

```text
GET  /intraday-config/state     현재 active · 미승인 후보 · 변경 요약 · 적용 상태
POST /intraday-config/approve   { config_version_id }  → approved_at/by 기록
POST /intraday-config/reject    { config_version_id, reason }
POST /intraday-config/apply     승인본을 OCI 로 전달 (§5 사슬)
```

승인과 전달을 **분리**한다. 기존 `/three-push/param/apply` 는 생성+활성화+전달이
한 버튼이라 승인 개념이 없었다.

---

## 8. 변경 파일 · 검증 계획

### 8-1. 예상 변경 파일

| 구분 | 파일 | 예상 |
|---|---|---:|
| 신규 | `app/intraday_config/__init__.py` | ~10 |
| 신규 | `app/intraday_config/schema.py` — 번들 스키마·검증 | ~180 |
| 신규 | `app/intraday_config/selector.py` — 사업군·대표 산출 | ~220 |
| 신규 | `app/intraday_config/store.py` — DB version/approval/active | ~240 |
| 신규 | `app/api_intraday_config.py` — API 4종 | ~180 |
| 신규 | `scripts/sync_intraday_config.py` — §5 사슬 | ~200 |
| 신규 | `scripts/apply_intraday_config_oci.py` — 원격 5~7 | ~120 |
| 신규 | `frontend/app/components/IntradayConfigCard.tsx` | ~200 |
| 신규 | `frontend/lib/api/intradayConfig.ts` | ~60 |
| 수정 | `app/runtime_state_db.py` — 테이블 3개 추가 | +40 |
| 수정 | `app/api.py` — router 등록 | +3 |
| 신규 | `tests/test_intraday_config_*.py` (3파일) | ~700 |

**KS-10**: 모든 신규 파일이 backend 600 / frontend 850 / test 1450 미만이다.
`app/api.py` 는 현재 632줄(NEAR)이라 **+3 줄만** 쓴다. 러너는 **건드리지 않는다**
(`FREEZE_AT_648`).

### 8-2. DB migration

`CREATE TABLE IF NOT EXISTS` 3개. 기존 테이블 변경 0건. 롤백은 테이블 drop 없이
active pointer 미설정으로 충분하다(러너가 아직 읽지 않으므로).

### 8-3. 테스트

| 종류 | 내용 |
|---|---|
| focused | 스키마 검증 · input_hash 동일 시 미생성 · **승인 없으면 activate 거부** · 원자 적용 · 실패 시 직전 active 유지 |
| 역검증 | 승인 게이트 무력화 시 미승인 버전이 활성화되는지 |
| 회귀 | 전체 `pytest tests/` — 현재 기준선 **1,583 passed** 유지 |
| 프론트 | `npx tsc --noEmit` · `npm run lint` · `npx vitest run` (현재 191 tests) |
| KS-10 | tracked + untracked 전수 · TRIGGER 0 · 러너 648 유지 |

라이브 격리는 기존 `conftest` 가드를 그대로 상속한다(신규 `conftest` 를 만들지
않는다).

---

## 9. 이번 Step 에 포함하지 않는 것

| 항목 | 이유 |
|---|---|
| 장중 조회·판정·발송 | `OPS-02` 범위 |
| 임계값·분류 규칙 수치 | 구조 확정 후 (§2) |
| 기존 `runtime_param` 경로 보수 | §0-3 판단 요청 A |
| 대표 ETF 교체 주기 | 설계자가 "아직 고정하지 않는다" |
| Naver 조회 가능 여부 확인 | 최종 목록 확정 후 · 외부 호출 승인 필요 |

---

## 10. 설계자 판단 요청 요약

| # | 항목 | 개발자 의견 |
|---|---|---|
| **A** | 기존 `runtime_param` 의 OCI DB 적재 공백(§0-3)을 함께 메울지 | **(b) 신규 번들만** |
| **B** | 사업군 병합 기준(§1-3) | **B-2 토큰 사전을 데이터로** |
| C | `sector_label` 을 공식 지수명 토큰 그대로 쓸지 | 그대로 (임의 라벨 금지) |
| D | 승인 UI 를 신규 카드로 둘지 기존 카드 확장할지 | **신규 카드** (기존 무변경) |

**A 와 B 는 답이 없으면 구현에 착수할 수 없다.** C·D 는 기본안으로 진행 가능하다.
