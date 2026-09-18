# POC3-OPS-02C 사전 사실조사 (2) — PC→OCI PARAM 전달 계약

작성일: 2026-09-16 · 작성자: 개발자(VSCode Claude) · 수신: 설계자

```text
CODE_CHANGE = 0 · CRON_CHANGE = 0 · FLAG_CHANGE = 0 · DB_CHANGE = 0 · NETWORK_CHANGE = 0
```

추정으로 채운 항목은 없다. 확인되지 않은 것은 **"없음"** 또는 **"미확인"** 으로 적었다.

---

## 1. PC→OCI 전달을 정한 최초 문서

| 항목 | 값 |
|---|---|
| 경로 | `docs/PROJECT_ORIGIN_INTENT.md` |
| 절 | **PC 분석 평면 / OCI 운영·조회 평면 분리** (2026-06-20 추가) |
| 참조 | 같은 절이 `docs/handoff/PC_OCI_ARCHITECTURE_DIRECTION.md` 를 가리킨다 |

원문 요지:

> **PC = 분석·판단 평면**: 시장 데이터 SQLite 관리, ETF universe 갱신, 후보 ETF
> 검토, ML 학습·백테스트·feature 실험, AI 투자세션, **사용자 승인**, **approved
> PARAM** 과 published data snapshot 생성. PC 는 24시간 상시 실행을 전제로 하지
> 않는다.
>
> **OCI = 상시 운영·조회 평면**: **latest approved PARAM 보관**, PUSH 별 목적에
> 맞는 독립 운영, Telegram 발송. **OCI 는 ML 학습을 수행하지 않는다.**

### 후속 정정 2건 — 둘 다 이번 Step 에 직접 걸린다

| 시점 | 정정 | 내용 |
|---|---|---|
| 2026-07-24 | OCI 제한적 런타임 가격 조회 허용 | 승인된 시세 출처 조회 · Holdings 재계산 · 조건 재평가 · **현재 active PARAM 적용** · as-of 기록. "PC 의 분석 기능을 OCI 로 이전하는 것이 아니다" |
| 2026-07-26 | OCI 자율 시세 갱신·운영 artifact 생성 허용 | 갱신 대상을 **"승인된 seed ticker ∪ 현재 Holdings ticker"** 로 한정. **전체 시장 수집 · seed 외 종목 자동 선정 금지** |

**2026-07-26 정정이 설계자의 "대표 ETF 방식" 판단을 문서로 뒷받침한다.**
개발자가 직전 조사에서 "전체 1,168종 장중 스캔" 을 검토 대상으로 올린 것은 이
경계를 놓친 것이다.

---

## 2. 현재 실제 PARAM 전달 계약

### 2.1 생성

| 항목 | 값 |
|---|---|
| CLI | `scripts/create_three_push_runtime_param.py` |
| API | `POST /three-push/param/apply` → `_create_approved_manual_seed_param()` |
| 산출 | `build_manual_seed_param()` — **manual seed 고정값**. ML·퀀트 산출이 아니다 |
| 실행 주기 | **스케줄 없음.** cron 에 등록돼 있지 않다. 사용자가 화면에서 누를 때만 |

### 2.2 저장

| 위치 | 경로 |
|---|---|
| DB | `runtime_param_version` (version row) + `runtime_param_active` (pointer) |
| JSON latest | `state/three_push/params/latest_runtime_param.json` |
| JSON history | `state/three_push/params/history/<param_id>.json` |
| sync 상태 | `state/three_push/params/param_sync_status_latest.json` |

**PC 와 OCI 가 같은 상대경로**를 쓴다(`app/three_push_runtime_param.py` 주석 명시).

### 2.3 검증 정보

| 필드 | 존재 |
|---|---|
| `param_version_id` · `schema_version` · `created_at` | **있음** |
| `approved_at` · `approved_by` | **있음** (테이블 컬럼) |
| `source_hash_sha256` | **있음** |
| `param_source` · `param_description` · `source_note` | 있음 |

### 2.4 OCI 전달

`scripts/sync_three_push_runtime_param.py` — 4단계다.

```text
1. ssh OCI_SSH_TARGET "echo OK"  로 접속 확인
2. scp 로 OCI tmp 위치에 업로드
3. ssh 로 atomic rename (tmp → latest)
4. verify_three_push_param_oci.py 를 일시 업로드·실행해 OCI 측 검증
```

원격 경로 기본값 `/home/ubuntu/krx_hyungsoo/state/three_push/params`
(env `THREE_PUSH_REMOTE_PARAM_DIR` 로 override).

### 2.5 OCI load

```text
scripts/run_three_push_runtime_oci.py:204
  param_dict = read_active_param_dict()      ← DB active pointer 기준
파일 경로도 동일: state/three_push/params/latest_runtime_param.json
```

### 2.6 자동 승격 조건

**없다.** `activate_param_version` 호출자는 4곳뿐이다.

| 호출자 | activated_by |
|---|---|
| `app/api_three_push_param.py` | `"api_param_apply"` — 사용자가 화면 버튼을 눌렀을 때 |
| `scripts/create_three_push_runtime_param.py` | CLI 실행 시 |
| `scripts/run_runtime_state_db_cutover.py` | 1회성 cutover |

**cron·스케줄러에서 부르는 곳이 없다.** 즉 지금은 "자동 승격" 자체가 존재하지
않고, 사람이 트리거해야만 바뀐다.

### 2.7 실패 시 직전 정상 버전 유지

**명시적 fallback 코드는 없다.** 다만 구조상 그렇게 동작한다.

- sync 는 **atomic rename** 이라 실패하면 OCI 의 기존 `latest` 가 그대로 남는다.
- OCI 러너는 `read_active_param_dict()` 로 **DB active pointer** 를 읽으므로,
  pointer 를 갱신하지 않는 한 직전 버전이 계속 쓰인다.
- 프론트 카드도 실패 시 기존 state 를 유지한다
  (`// 실패해도 카드의 기존 state 유지 — 사용자는 직전 적용 상태를 볼 수 있다`).

**"검증 실패 시 자동 롤백" 같은 명시 로직은 확인되지 않았다.**

### 2.8 수동 사용자 승인이 실제 필수인가

```text
approved_at / approved_by  = 스키마에 존재
activate_param_version(..., activated_by: str)  = 필수 인자
```

그러나 **승인 상태를 검사하는 게이트는 없다.** `activate_param_version` 은
pointer 를 갱신할 뿐이고, "approved 가 아니면 활성화 거부" 하는 분기가 없다.

```text
ACTIVATED_BY = 감사(audit) 필드
APPROVAL_GATE = 없음
```

**설계자 질의 답**: `activated_by` 는 **감사 필드이지 승인 게이트가 아니다.**
실질 승인은 "사람이 화면 버튼을 눌러야만 pointer 가 바뀐다" 는 **절차적 통제**로
성립하고 있다.

---

## 3. 두 신규 artifact 를 같은 경로로 전달할 수 있는가

| artifact | 판정 |
|---|---|
| A. `SECTOR_REPRESENTATIVE_UNIVERSE` | **가능** — 단 신규 계약 필요 |
| B. `INTRADAY_ALERT_POLICY` | **가능** — 단 신규 계약 필요 |

재사용 가능한 것:

- scp + atomic rename + 원격 verify 4단계 sync
- `param_version_id` / `created_at` / `source_hash_sha256` / `approved_*` 스키마
- DB version row + active pointer 패턴
- 프론트 `ThreePushParamCard` 의 적용 상태 표시 구조

새로 정해야 하는 것:

- 두 artifact 의 **스키마**(사업군 식별자 · 대표/대체 ETF · 적용 기간 · 선정 근거 ·
  데이터 기준일 / 임계값 · cooldown · 발송 상한)
- 기존 `runtime_param` 에 **합칠지 별도 artifact 로 둘지**
- OCI 측 verify 스크립트 확장
- **PC 자동 산출 스케줄** (현재 PARAM 생성에는 스케줄이 없다)

---

## 4. PC 자동 선정과 OCI 장중 작업의 경계

| 경계 | 문서 근거 | 현재 구현 |
|---|---|---|
| PC = 전체 ETF 대상 무거운 계산 | `PROJECT_ORIGIN_INTENT` PC 평면 | ML·백테스트 코드 존재 |
| OCI = 배포된 소수 + 보유만 조회 | 2026-07-26 정정 | `collect_target_tickers` 가 보유 원장만 반환 |
| OCI 전체 ETF 자동 탐색 금지 | 2026-07-26 정정 원문 | **현재 위반 없음** |
| Market Discovery 를 필수 선행조건으로 삼지 않음 | — | 현재 universe artifact 는 spike 전용. 급락 알림은 쓰지 않는다 |

⚠ **한 가지 확인 필요** — 07:20 배치가 **전체 ETF 1,168종의 KRX 일별 시세**를
적재한다(`OPS-02B-2`). 이는 2026-07-26 정정의 "승인된 seed ∪ Holdings 로 한정"
과 문언상 어긋나 보인다. 다만 그 정정은 **장중 조회·자동 선정**을 막는 취지이고,
07:20 배치는 일별 종가 적재라 성격이 다르다. **설계자 판단이 필요하다.**

---

## 5. 기존 PC 화면 재사용 가능성

| 항목 | 현재 `ThreePushParamCard` | 설계자 요구 |
|---|---|---|
| 현재 적용 버전 | **있음** (`display_label`) | 필요 |
| OCI 반영 상태 | **있음** (적용 완료 / 적용 중 / 적용 실패 / 미적용) | 필요 |
| 마지막 적용 시각 | **있음** | 필요 |
| 진행 단계 표시 | 있음 (생성 중 → 적용 중 → 확인 중 → 완료) | — |
| 승인 / 기각 버튼 | **없음** — `[현재 기준 OCI 적용]` **단일 버튼**뿐 | **필요** |
| 변경 요약(추가·제외·교체) | **없음** | **필요** |
| 변경 사유·산출 근거 | **없음** | **필요** |
| 다음 산출 예정 시각 | **없음** (스케줄 자체가 없음) | 필요 |
| 직전 정상 버전 fallback 상태 | **없음** | 필요 |

**판정**: 카드의 "현재 버전 · 반영 상태 · 적용 시각" 3요소는 그대로 재사용
가능하다. **승인/기각과 변경 요약은 신규 개발이다.**

**기존 승인 경로는 API 다** — `POST /three-push/param/apply`
(`frontend/lib/api/threePushParam.ts`). CLI(`create_three_push_runtime_param.py`)
도 같은 일을 하지만 화면 경로는 API 다.

---

## 6. 설계자 반환 항목 요약

```text
ORIGIN_DOC            = docs/PROJECT_ORIGIN_INTENT.md §PC 분석 평면 / OCI 운영·조회 평면 분리
ORIGIN_DATE           = 2026-06-20 (정정 2026-07-24 · 2026-07-26)
PC_GENERATOR          = scripts/create_three_push_runtime_param.py
                        + POST /three-push/param/apply
PC_SCHEDULE           = 없음 (cron 미등록 · 사용자 트리거)
ARTIFACT_FORMAT       = JSON + SQLite version row/pointer
ARTIFACT_PATH         = state/three_push/params/latest_runtime_param.json
VERSION_FIELDS        = param_version_id · schema_version · created_at
                        approved_at · approved_by · source_hash_sha256
DELIVERY              = ssh 확인 → scp → atomic rename → 원격 verify (4단계)
OCI_LOAD              = read_active_param_dict()  (DB active pointer)
AUTO_PROMOTION        = 없음 (자동 승격 경로 자체가 없다)
FAILURE_FALLBACK      = 명시 로직 없음. atomic rename + pointer 미갱신으로 사실상 유지
APPROVAL_GATE         = 없음.  activated_by 는 감사 필드
                        실질 통제 = "사람이 눌러야 pointer 가 바뀐다"
NEW_ARTIFACT_FEASIBLE = YES (경로·스키마 패턴 재사용 가능)
UI_REUSABLE           = 부분. 버전·반영상태·적용시각 재사용 / 승인·변경요약 신규
APPROVAL_PATH_TODAY   = API  POST /three-push/param/apply
```

---

## 7. 설계자 판단이 필요한 항목

1. **승인 게이트를 코드로 만들 것인가** — 지금은 절차적 통제뿐이고
   `approved_*` 컬럼을 검사하는 분기가 없다. 설계자가 확정한
   `AUTO_PROMOTION_WITHOUT_APPROVAL = false` 를 **코드로 강제**하려면 게이트
   신설이 필요하다.

2. **PC 자동 산출 스케줄** — 현재 PARAM 생성에 스케줄이 없다. 사업군·대표 ETF 를
   "자동 산출" 하려면 PC 측 주기 실행이 필요한데, PC 는 상시 가동이 아니다
   (`PROJECT_ORIGIN_INTENT`: "PC 는 24시간 상시 실행을 전제로 하지 않는다").
   **PC 가 꺼져 있으면 누가 언제 산출하는가** 가 미해결이다.

3. **07:20 전체 ETF 적재와 2026-07-26 정정의 관계** (§4 ⚠)

4. **신규 artifact 를 기존 `runtime_param` 에 합칠지 분리할지**
