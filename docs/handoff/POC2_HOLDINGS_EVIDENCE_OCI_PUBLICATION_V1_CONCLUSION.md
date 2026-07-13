# Holdings Evidence OCI Publication v1 — Conclusion (PARTIAL FIX r1 — PC DONE · OCI 실행 대기)

작성일: 2026-07-13 / FIX r1: 2026-07-13
성격: PC 승인 Holdings SSOT 를 OCI 로 controlled publication + OCI Runtime `holdings_briefing` 실제 evidence 연결.

## 0. FIX r1 요약 (검증자 REJECTED 대응)

**원인**: 최초 커밋 (`4937423c`) 후 검증자 지적:
- A-1: `HoldingsValidationError` 원문 stdout 노출 (종목명 · ticker · 평단 등).
- A-1/B-1: chmod 실패를 무시하고 `os.replace()` 진행 → 기존 active 파일 보존 계약 위반.
- A-1/B-1: owner 조회 결과 None 이어도 `active_file_permission_checked=true`, `status=ok` 로 성공.
- B-6: chmod 실패 / owner 조회 불가 / validation 실패 개인정보 출력 회귀 test 부재.
- B-6: `test_real_holdings_file_not_touched_by_tests` 는 `assert True` 만 → 의미 없는 test.

**FIX r1 조치**:
- `_parse_and_validate`: `HoldingsValidationError` catch 후 예외 str() 을 그대로 반환하지 않고 sanitised reason code `"holdings_validation_error"` 만 반환.
- `cmd_activate`: (1) chmod 실패 → return 4 (기존 active 보존). (2) `tmp_mode != "600"` → return 4. (3) `tmp_owner is None or exec_user is None` → return 4. (4) `a_owner != exec_user` → return 4/7.
- `_current_user`: 실패 시 빈 문자열이 아니라 `None` 반환 (owner 대조 우회 방지).
- 신규 test 5 추가:
  - `test_validation_error_does_not_leak_sensitive_info` (A-1 · prepare 원문 미노출).
  - `test_activate_blocks_when_chmod_fails` (chmod 실패 → 기존 active 보존).
  - `test_activate_blocks_when_owner_check_unavailable` (owner=None → 차단).
  - `test_activate_blocks_when_exec_user_none` (exec_user=None → 차단).
  - `test_verify_fail_does_not_leak_holdings_content` (verify 실패 시에도 원문 미노출).
- `test_real_holdings_file_snapshot_unchanged_across_tests` 재작성: 자기 실행 전·후 실제 파일 sha256/size 실측 대조 (실제 파일 존재 시). 실제 파일 부재 시 test 가 새로 만들지 않음 assert.


## 1. Step 목표와 범위

**목표**: PC `state/holdings/holdings_latest.json` 을 OCI 로 안전 전달 → OCI Runtime `holdings_briefing` contentful evidence 생성.

**범위**: prepare/verify/activate CLI 신규 + validate_holdings 재사용 + 원자적 activation + mode 600. **Holdings schema · DB Cutover · scheduler · Telegram 발송 없음.**

**협업 방식 (Q1 b, Cutover v1 원칙 재적용)**: 개발자 = PC 구현 + PC prepare 실측 + OCI 명령 세트. 사용자 = OCI SCP (기존 방식) + verify/activate 실행 + sanitised 결과 회신.

## 2. PC source 경로 · OCI active 경로

- PC source (SSOT): `state/holdings/holdings_latest.json`.
- OCI active: `state/holdings/holdings_latest.json` (동일 상대 경로).
- OCI 임시: `state/holdings/holdings_latest.json.tmp` (동일 디렉터리 필수).

## 3. Publication 방식

Controlled publication (Q1 b · §4.2):
- CLI 3 subcommand: `prepare` (PC) → 사용자 SCP → `verify` (OCI) → `activate` (OCI).
- CLI 는 SSH/SCP 미수행.
- expected hash/size/count 를 `verify` + `activate` 양쪽 인자로 전달 (TOCTOU 방지).

## 4. Source validation 결과 (PC 실측)

`python -m scripts.run_holdings_publication prepare` 실측 (2026-07-13):

| 항목 | 값 |
|---|---|
| `source_exists` | true |
| `source_valid` | true (validate_holdings 통과) |
| `source_hash` | `767815e059ad3613727afd2a21f85de39d3e0b0758aa7a103e8fc0cacc0d028b` |
| `source_size` | 6238 bytes |
| `source_holding_count` | 35 |
| `status` | ok |
| `error_reason` | (empty) |

**보유 종목 수 35** 확인. hash/size/count 는 OCI verify + activate 에 expected 인자로 전달.

## 5. Atomic activation 계약 (§4.4, Q7-보정)

`activate` 실행 순서:
1. 임시 파일 존재 확인.
2. 임시 파일이 active 파일과 동일 디렉터리인지 확인 (POSIX rename atomic 조건).
3. **expected hash/size/count 재검증** (TOCTOU 방지).
4. mode 600 적용 + owner 확인.
5. `os.replace()` 원자적 교체.
6. active 파일 hash/size/count 재검증.
7. active 파일 mode/owner 재검증.
8. sanitized JSON 결과 출력.

각 단계 실패 시 stdout `error_reason` 기록 + non-zero exit code.

## 6. OCI 파일 권한 정책 (§5.5 · Q4)

`active_file_permission_checked=true` 조건 (§Q11):
- mode = `600`
- owner = activation 실행 계정 (getpass.getuser()).
- group/other 접근 없음 (mode 600 이 이를 보장).
- 파일 read 가능 (validate_holdings 성공).

Runtime cron 계정과 activation 계정이 다르면 → `owner_mismatch` PARTIAL 중단 (사용자 확인 필요).

**신규 운영 계정 · 자동 chown 금지** (§Q4).

## 7. OCI Runtime 연결

기존 흐름 유지 (신규 reader 없음, §7 · AC-11/12):
```
holdings.load() → compute_topn() → build_holdings_market_evidence()
→ Runtime Evidence Composer → build_runtime_message()
```

Composer 는 이미 이전 STEP `Runtime Evidence DB Connection v1` 에서 다음 조건 준수:
- Holdings JSON 존재 필수.
- validate_holdings 성공 필수.
- 실제 market as-of 필수.
- 실제 evidence fact 생성 필수 (§8).
- 파일 존재만으로 available 처리 X.

## 8. 개인정보 비노출 확인 (§9 · AC-17)

**CLI stdout 미노출** (`test_stdout_contains_no_sensitive_fields` 로 확인):
- 종목명 · ticker · 수량 · 평단 · account_group · JSON 원문 stdout 미출력.
- 실측 원문 (계좌 그룹명, 종목명 등) 자동 test 로 미노출 assert.

**출력 허용**: SHA-256, size, holding_count, mode, owner, group.

## 9. dry-run 계약 유지 (§Q10 · AC-18/19)

Publication CLI 자체는 Telegram 미호출 · sent_registry 미변경. 다음 단계 (OCI dry-run) 는 이전 STEP 인 `Runtime Evidence DB Connection v1` 계약 그대로.

## 10. PC 검증 결과

**backend regression (FIX r1 최종)**: **870 passed** (직전 850 → 865 → 870, 이번 STEP 순증 20 = 초기 15 + FIX r1 5). 0 fail. 203s.
**focused test**: **20 passed** (`tests/test_run_holdings_publication.py`, FIX r1 순증 5).
**Lint**: black / flake8 (max-line=100) / py_compile PASS.

**실제 state 무변경 (자동 test)**:
- 모든 test 는 `tmp_path` fixture 사용. 실제 `state/holdings/holdings_latest.json`, `state/market/market_data.sqlite`, `state/runtime/runtime_state.sqlite` 미참조 · 미변경 (Q9 확정본 준수).

**실제 파일 불변 실측 (Q9 수동)** — pytest 865 실행 전·후 4종 sha256 3중 일치:

| 파일 | before sha256 | after sha256 | 결과 |
|---|---|---|---|
| `state/holdings/holdings_latest.json` | `767815e059ad3613...` | `767815e059ad3613...` | ✅ 불변 (size 6238) |
| `state/runtime/runtime_state.sqlite` | `f72dd796b20441c8...` | `f72dd796b20441c8...` | ✅ 불변 |
| `state/three_push/params/latest_runtime_param.json` | `84151b5659abba0a...` | `84151b5659abba0a...` | ✅ 불변 |
| `state/market/market_data.sqlite` | `f7df867d0f69fc07...` | `f7df867d0f69fc07...` | ✅ 불변 |

## 11. OCI 실행 명령 (사용자 실행 대기)

### 11.1 SCP 전송 (기존 운영 방식)

PC 에서:
```powershell
scp -i "D:\AI\oci_ssh_key\id_rsa" "E:\AI Study\krx_alertor_modular\state\holdings\holdings_latest.json" ubuntu@152.67.211.223:/home/ubuntu/krx_hyungsoo/state/holdings/holdings_latest.json.tmp
```

**중요**: 목적지 파일명에 `.tmp` 붙임 (active 파일 직접 덮어쓰기 금지 · §4.4).

### 11.2 OCI 최신 코드 반영 + verify + activate

```bash
cd ~/krx_hyungsoo && git pull origin main && python3 <<'PY'
import json, subprocess
from scripts.run_holdings_publication import main as run

EXPECTED_HASH = "767815e059ad3613727afd2a21f85de39d3e0b0758aa7a103e8fc0cacc0d028b"
EXPECTED_SIZE = 6238
EXPECTED_COUNT = 35

head = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
print(f"=== revision: {head} ===")

# 1) verify
print("=== VERIFY ===")
rc1 = run([
    "verify",
    "--temp", "state/holdings/holdings_latest.json.tmp",
    "--expected-hash", EXPECTED_HASH,
    "--expected-size", str(EXPECTED_SIZE),
    "--expected-count", str(EXPECTED_COUNT),
])
print(f"verify exit: {rc1}")

if rc1 == 0:
    # 2) activate
    print("=== ACTIVATE ===")
    rc2 = run([
        "activate",
        "--temp", "state/holdings/holdings_latest.json.tmp",
        "--expected-hash", EXPECTED_HASH,
        "--expected-size", str(EXPECTED_SIZE),
        "--expected-count", str(EXPECTED_COUNT),
    ])
    print(f"activate exit: {rc2}")
PY
```

### 11.3 OCI holdings_briefing dry-run (activate 성공 후)

```bash
cd ~/krx_hyungsoo && python3 <<'PY'
import json, subprocess
from app import runtime_state_db as _db
from app.market_topn import compute_topn
from app.runtime_sent_registry_store import count as _sent_count
from app.runtime_param_store import get_active_pointer

head = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
sent_before = _sent_count()
ptr = get_active_pointer(_db.DEFAULT_DB_PATH) or {}
market_asof = compute_topn().get("asof")

import app.three_push_runner_common as _rc
_rc.telegram_send = lambda *a, **kw: (False, "blocked_by_wrapper")

from scripts.run_three_push_runtime_oci import run
records = [run(pk, "dry-run") for pk in ["market_briefing", "holdings_briefing"]]
sent_after = _sent_count()

def _pick(r):
    return {
        "push_kind": r.get("push_kind"),
        "status": r.get("status"),
        "message_text_length": r.get("message_text_length"),
        "availability": r.get("availability"),
        "contentful_fact_count": r.get("contentful_fact_count"),
        "selection_result_count": r.get("selection_result_count"),
        "unavailable_reasons": r.get("unavailable_reasons"),
        "telegram_attempted": r.get("telegram_attempted"),
        "telegram_sent": r.get("telegram_sent"),
    }

print(json.dumps({
    "revision": head,
    "market_asof": market_asof,
    "active_pointer": {
        "active_param_version_id": ptr.get("active_param_version_id"),
        "activated_by": ptr.get("activated_by"),
    },
    "sent_registry_before": sent_before,
    "sent_registry_after": sent_after,
    "sent_registry_unchanged": sent_before == sent_after,
    "records": [_pick(r) for r in records],
}, ensure_ascii=False, indent=2))
PY
```

### 11.4 사용자 회신 항목 (sanitised)

- verify stdout: `destination_hash`, `destination_size`, `destination_holding_count`, `hash_match`, `size_match`, `holding_count_match`, `activation_ready`.
- activate stdout: `final_validation_passed`, `atomic_activation_completed`, `active_file_exists`, `active_hash`, `active_size`, `active_holding_count`, `active_file_mode`, `active_file_owner`, `active_file_permission_checked`.
- dry-run stdout: 위 JSON 그대로.

**절대 미포함**: 종목명, ticker, 수량, 평단, account_group, Holdings JSON 원문, 절대 경로, token, chat_id, raw traceback.

## 12. 남은 source gap

- `kr_realtime_price_snapshot` (외부 API 필요, 후속 STEP).
- `overnight_us_market_snapshot` (외부 API 필요).
- `ml_baseline_v0` (ML artifact publication STEP).
- `news_snapshot` (producer/reader 신설).
- `universe_momentum_snapshot` (artifact publication STEP — 다음 후보).

## 13. 다음 Step 게이트 (§17)

**PASS 조건**:
- verify · activate 모두 성공.
- `active_file_permission_checked=true`.
- OCI `holdings_briefing.contentful_fact_count >= 1`.
- OCI `holdings_briefing.selection_result_count >= 1`.
- Telegram 미발송.
- sent_registry 불변.
- market_briefing 회귀 없음.

**분기**:
- PASS → 다음 STEP: **`Universe Momentum Evidence Publication v1`**.
- PARTIAL / FAIL → 같은 Step 에서 미완료 원인 해소.
