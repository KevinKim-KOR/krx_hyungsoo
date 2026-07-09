# OCI Database Environment Remediation v1 — Conclusion (DONE, 3-way SHA-256 일치 · Preflight READY)

작성일: 2026-07-09
closeout: 2026-07-09
성격: 이전 STEP `OCI Database Preflight v1` 에서 확인된 OCI `state/market/market_data.sqlite` 부재를 1회성 시드 반영으로 복구하는 환경 복구 Step. **기능 개발이 아님**.

**협업 방식 (Q1 (b) 확정)**: 개발자는 OCI 접속하지 않는다. 개발자는 PC source DB 확인 + SHA-256 산출 + 사용자에게 전달할 OCI 명령 세트 작성까지 수행하고, OCI 실제 실행은 사용자가 수행한 뒤 sanitised 결과를 받아 closeout 한다.

---

## 1. 현재 상태

**DONE** — 사용자 OCI 실행 완료 (2026-07-09, revision `c6967d1a`, same_revision=True). 3-way SHA-256 일치 · integrity_check=ok 3회 · table_count=12 3회 · Preflight `[market_data] readiness=READY` · single_environment_readiness=READY.

---

## 2. PC source DB 확인 (완료, 2026-07-09)

**Q2 (a) 확정 — SHA-256 통일** + PRAGMA integrity_check (둘 다 필요).

| 항목 | 값 |
|---|---|
| source 파일 경로 (프로젝트 상대) | `state/market/market_data.sqlite` |
| 파일 존재 | True |
| regular file 여부 | True |
| 파일 크기 (bytes) | **131,538,944** |
| SHA-256 | **`f7df867d0f69fc07929b0a25a87ccdc0f235a01097299a9a522bf991614cf286`** |
| read-only open (`file:...?mode=ro`) | 성공 |
| PRAGMA integrity_check | **ok** |
| PRAGMA schema_version | 12 |
| PRAGMA application_id | 0 |
| table_count | 12 |
| Preflight PC 결과 (`OCI Database Preflight v1`, `fd7ff116`) | **READY** |

**table list** (검증 기준으로 OCI 에서도 동일해야 함):

1. `etf_constituent_refresh_log`
2. `etf_constituents`
3. `etf_daily_price`
4. `etf_master`
5. `etf_ml_feature_daily`
6. `etf_nav_daily`
7. `market_benchmark_daily_price`
8. `market_refresh_log`
9. `market_refresh_state`
10. `market_risk_feature_daily`
11. `market_timeseries_ingestion_state`
12. `market_timeseries_refresh_state`

**§6 준수**: source DB 는 전송 전 아래 조건 모두 충족.
- 파일 존재 ✅
- read-only open 성공 ✅
- PRAGMA integrity_check = ok ✅
- table list 조회 가능 ✅ (12개)
- Preflight PC 결과 READY ✅
- SHA-256 산출 가능 ✅

---

## 3. 사용자가 OCI 에서 실행할 명령 세트

**전제**:
- 사용자는 이미 OCI repository root (`~/krx_hyungsoo`) 로 접속·이동한 상태.
- 개발자는 OCI host · user · 절대 경로 · SSH credential 을 다루지 않음.
- 아래 명령은 **모두 프로젝트 상대 경로 기준**. secret · token · 절대 경로 미포함.

### 3.1 §8.1 PC → OCI 임시 파일 전송 (기존 운영 방식)

지시문 §7 원칙 준수:
- ❌ target 파일 (`state/market/market_data.sqlite`) 을 직접 덮어쓰지 않음.
- ✅ 반드시 **임시 파일 `state/market/market_data.sqlite.tmp`** 로 먼저 전송.
- ✅ 임시 파일명은 active runtime 이 읽지 않는 이름 (`.tmp` 확장자).

**사용자 액션 (기존 SCP/rsync 절차 그대로)**: PC 의 `state/market/market_data.sqlite` 를 OCI 의 `state/market/market_data.sqlite.tmp` 로 전송. 개발자는 이 절차를 새로 설계하지 않는다.

### 3.2 §8.2 OCI target directory 준비

OCI `state/market/` 이 이미 있으면 skip. 없으면 아래만 생성 (다른 state 경로는 만들지 않음):

```bash
mkdir -p state/market
```

### 3.3 §8.4 OCI 임시 파일 검증

전송 완료 후 OCI 에서:

```bash
# 존재 + 크기.
ls -l state/market/market_data.sqlite.tmp

# 파일 크기 (bytes).
stat -c '%s' state/market/market_data.sqlite.tmp

# SHA-256 산출.
sha256sum state/market/market_data.sqlite.tmp

# read-only open + integrity_check + table list.
python3 -c "
import sqlite3
p = 'state/market/market_data.sqlite.tmp'
con = sqlite3.connect(f'file:{p}?mode=ro', uri=True)
try:
    integ = con.execute('PRAGMA integrity_check').fetchone()[0]
    tables = con.execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\").fetchall()
    print(f'integrity_check={integ}')
    print(f'table_count={len(tables)}')
    for (n,) in tables:
        print(f'  {n}')
finally:
    con.close()
"
```

**검증 기준** (모두 만족해야 §8.6 원자적 교체 진행):
- 파일 크기 = **131538944**
- SHA-256 = **`f7df867d0f69fc07929b0a25a87ccdc0f235a01097299a9a522bf991614cf286`**
- integrity_check = **ok**
- table_count = **12** + table list 이 §2 와 동일

임시 파일 검증이 실패하면 target 으로 교체하지 않음.

### 3.4 §8.5 기존 target 처리 (Preflight 결과상 부재로 확인됨)

Preflight `fd7ff116` 결과: OCI `state/market/market_data.sqlite` **부재**. 그래도 실행 시점 안전 확인:

```bash
# 실행 시점에 실제 부재인지 재확인.
ls -l state/market/market_data.sqlite 2>&1 || echo "absent (expected)"
```

**시나리오**:
- **부재 (예상)** → 그대로 §3.5 진행.
- **혹시 존재하면** → 크기 + SHA-256 확인 후 source 와 동일하면 교체 skip / 다르거나 비정상이면 `state/market/market_data.sqlite.remediation-backup-YYYYMMDD-HHMMSS` 로 백업 후 교체. 백업 이름은 active state 로 읽히지 않도록 `.remediation-backup-*` 접미.

### 3.5 §8.6 target 경로로 원자적 교체

임시 파일 검증 완료 후:

```bash
# 원자적 교체 (POSIX rename → atomic).
mv state/market/market_data.sqlite.tmp state/market/market_data.sqlite
```

**주의**: `mv` (POSIX rename) 는 동일 파일시스템 내에서 원자적. `cp` + `rm` 은 사용하지 않음.

### 3.6 §8.6 target DB 재검증

교체 직후 OCI 에서:

```bash
# 존재 + 크기.
ls -l state/market/market_data.sqlite

# SHA-256 재산출.
sha256sum state/market/market_data.sqlite

# read-only open + integrity_check + table list.
python3 -c "
import sqlite3
p = 'state/market/market_data.sqlite'
con = sqlite3.connect(f'file:{p}?mode=ro', uri=True)
try:
    integ = con.execute('PRAGMA integrity_check').fetchone()[0]
    tables = con.execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\").fetchall()
    print(f'integrity_check={integ}')
    print(f'table_count={len(tables)}')
    for (n,) in tables:
        print(f'  {n}')
finally:
    con.close()
"
```

**검증 기준**:
- 파일 크기 = 131538944
- SHA-256 = `f7df867d0f69fc07929b0a25a87ccdc0f235a01097299a9a522bf991614cf286` (source · temp · target 세 값 모두 일치 — Q2 확정본)
- integrity_check = ok
- table_count = 12

### 3.7 §8.7 OCI Preflight CLI 재실행

```bash
python -m scripts.run_oci_database_preflight --environment oci
git rev-parse --short HEAD
```

**성공 판정 기준** (지시문 §3 · §11):
```
[market_data] readiness=READY
```

---

## 4. 사용자가 개발자에게 전달할 sanitised 요약

다음 항목만 새 세션에 전달 (secret / 절대 경로 / SSH host 절대 미포함):

| 항목 | 형식 |
|---|---|
| OCI temp 파일 크기 | 정수 (bytes) |
| OCI temp SHA-256 | 64-hex |
| OCI temp integrity_check | `ok` 또는 실패 사유 |
| OCI temp table_count | 정수 |
| OCI temp table list | 12개 이름 |
| 기존 target 상태 (§8.5) | `absent` / `kept_same` / `backed_up_then_replaced` |
| OCI target 파일 크기 | 정수 |
| OCI target SHA-256 | 64-hex |
| OCI target integrity_check | `ok` 또는 실패 사유 |
| OCI target table_count | 정수 |
| Preflight 재실행 stdout | 그대로 (§3.7 형식) |
| OCI revision (`git rev-parse --short HEAD`) | short hash |

**절대 전달 X**: Telegram token / chat id / 환경변수 값 원문 / 절대 경로 / SSH credential / raw traceback.

---

## 5. 검증 결과 (사용자 OCI 실행 실측, 2026-07-09)

### 5.1 SHA-256 3-way 일치 (§6 · §7 · Q2 확정본)

| 위치 | SHA-256 | 상태 |
|---|---|---|
| PC source | `f7df867d0f69fc07929b0a25a87ccdc0f235a01097299a9a522bf991614cf286` | ✅ (§2 PC 실측) |
| OCI temp | `f7df867d0f69fc07929b0a25a87ccdc0f235a01097299a9a522bf991614cf286` | ✅ (OCI §3.3 실측) |
| OCI target | `f7df867d0f69fc07929b0a25a87ccdc0f235a01097299a9a522bf991614cf286` | ✅ (OCI §3.6 실측) |

세 값 모두 일치 → §7 완료.

### 5.2 OCI temp / target 세부 실측 (§3.3 · §3.6)

| 항목 | OCI temp | OCI target |
|---|---|---|
| 파일 크기 (bytes) | 131538944 | 131538944 |
| SHA-256 | 상기 일치 | 상기 일치 |
| integrity_check | ok | ok |
| table_count | 12 | 12 |
| table list | §2 와 동일 (12개) | §2 와 동일 (12개) |
| 기존 target 상태 (§3.4) | — | `absent` (Preflight 상 부재 그대로 재확인) |
| 원자적 교체 (§3.5) | — | `mv` 완료 |

### 5.3 OCI Preflight 재실행 결과 (§3.7)

| 항목 | 값 |
|---|---|
| revision | `c6967d1a` (PC = `c6967d1a`, same_revision=True) |
| market_data readiness | **READY** |
| market_data path_status | `resolved` (`single_canonical_path`) |
| market_data exists · regular_file · read_access · read_open_success | True · True · True · True |
| market_data schema_version · application_id · file_size_bytes | 12 · 0 · 131538944 |
| decision_evidence readiness | `OPTIONAL_MISSING` (이번 STEP 범위 밖 — 기대대로 변화 없음) |
| runtime_paths 상태 | `confirmed_from_local_and_prior_audit` (기존 4 JSON 존재, probe latest 부재 — 이번 STEP 범위 밖) |
| staging 상태 | `unconfirmed_from_audit` (이번 STEP 범위 밖) |
| single_environment_readiness | **READY** |

---

## 6. 이번 STEP 에서 하지 않은 것 (지시문 §4 금지 · §5 · §9 · §10)

- SQLite schema 생성·변경, row insert/update/delete: **0건**.
- PARAM DB table 생성, active PARAM 전환: **0건**.
- JSON → DB migration, JSON 삭제·rename: **0건**.
- Runtime evidence DB 조회 연결, `available_sources=None` 수정: **0건**.
- Publish bundle · 정기 동기화 · OCI→PC replica 설계: **0건**.
- Telegram dry-run · 실제 발송 · 외부 API 호출: **0건**.
- 신규 API · UI · scheduler · daemon · watcher · worker: **0건**.
- `state/decision/decision_evidence.sqlite` 생성·복사·역할 확정: **0건** (§9 그대로).
- `state/runtime/three_push_runtime_probe_latest.json` 생성·수정: **0건** (§10 그대로).
- 기존 PARAM JSON / runtime status / sent registry / history 파일 수정: **0건**.

---

## 7. 완료 판정 (지시문 §12) — **DONE**

실행 결과가 §12 표의 첫 번째 행에 해당:
- `market_data readiness = READY` ✅
- `single_environment_readiness = READY` ✅
- 3-way SHA-256 일치 ✅
- integrity_check = ok (source · temp · target 3회) ✅
- table_count = 12 (source · temp · target 3회, table list 동일) ✅
- OCI revision (`c6967d1a`) = PC revision (`c6967d1a`), same_revision=True ✅

→ **STEP DONE**. 다음 STEP: **`PARAM / Runtime State DB Mapping v1`** (설계자 확정 세션).

---

## 8. 다음 STEP 으로 넘길 항목 (지시문 §13)

이번 STEP 에서 결정하지 않음:
- PARAM table 구조
- Runtime status DB 매핑
- Sent registry DB 매핑
- Holdings DB 매핑
- Source publication id
- PC → OCI PARAM publication 방식
- OCI → PC analysis replica 방식
- Runtime evidence SQL 계약
- `available_sources=None` 제거
- Telegram contentful dry-run
- Mobile read model

---

## 9. 남은 미확인 항목 (이번 STEP 범위 밖 · 다음 STEP 후속)

이번 STEP 에서 해결한 항목 (§5 · §7 참조): OCI temp / target SHA-256 실측, 기존 target 존재 여부 (`absent`), Preflight 재실행 결과 (`READY`), same_revision (`c6967d1a=c6967d1a`).

다음 STEP 으로 이월 (지시문 §13):
- `decision_evidence.sqlite` 역할 (OPTIONAL_MISSING 유지) — `PARAM / Runtime State DB Mapping v1` 에서 확정.
- `three_push_runtime_probe_latest.json` 생성 정책 — 별도 STEP.
- staging (`THREE_PUSH_REMOTE_PACKAGE_DIR`) 실제 상태 — 별도 STEP.
- `available_sources=None` 수정 — 별도 STEP.

---

## 10. 변경 파일 목록 (전체 STEP, 문서만)

**PARTIAL 라운드 (commit `c6967d1a`)**:
- 신규: `docs/handoff/POC2_OCI_DATABASE_ENVIRONMENT_REMEDIATION_V1_CONCLUSION.md`
- 수정: `docs/STATE_LATEST.md`, `docs/handoff/POC2_B_NEXT_ACTIONS.md`

**DONE closeout 라운드 (본 commit 예정)**:
- 수정: `docs/handoff/POC2_OCI_DATABASE_ENVIRONMENT_REMEDIATION_V1_CONCLUSION.md` (본 문서 — PARTIAL → DONE, §5 · §7 · §9 실측값 반영)
- 수정: `docs/STATE_LATEST.md` (DONE 승격)
- 수정: `docs/handoff/POC2_B_NEXT_ACTIONS.md` (§0 DONE + 다음 STEP gate 확정)

**변경 없음 확인** (전체 STEP):
- `app/` / `frontend/` / `scripts/` / `tests/` — 0 파일.
- `state/` — 0 파일 (PC 는 read-only, OCI 는 사용자 실행 · 개발자 미개입).
- 소스 코드 · SQLite schema · SQLite rows · JSON runtime · API · UI · scheduler — 0 변경.
- 지시문 §4 금지 · §5 허용 범위 정확 준수.
