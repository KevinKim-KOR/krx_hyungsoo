# POC2 PARAM Handoff 기반 OCI Runtime 3-PUSH 전환 — Conclusion

작성일: 2026-06-18
Step: `PARAM_HANDOFF_OCI_RUNTIME_3PUSH`
직전 Step: `OCI_THREE_PUSH_OPERATION_REGISTRATION` (2026-06-18 PARTIAL)

---

## 0. 한 줄 요약

정식 운영 경로를 **PC가 매 발송마다 message package 를 만들어 OCI 로 동기화** 하는 구조에서 **PC 가 사용자 승인한 PARAM snapshot 을 한 번만 OCI 로 전달하고, OCI 가 latest PARAM 을 고정 사용해 runtime 시점 데이터를 보고 메시지를 생성** 하는 구조로 전환했다. 신규 PARAM contract + 신규 runtime entrypoint + PARAM 생성/전달/검증 CLI 3종 + OCI 실측 (dry-run 3종 / send 1회 / duplicate / disabled / missing_latest_param / secret 가드 모두 PASS) 완료.

기존 package sync 산출물은 삭제 없이 manual recovery 로 격하했다.

---

## 1. 처리한 요구사항 (지시문 §17 AC 기준)

| AC | 항목 | 결과 |
|---|---|---|
| AC-1 | `three_push_runtime_param.v1` 계약 문서화 | DONE — `app/three_push_runtime_param.py` + STATE_LATEST §1 + FEATURE_INVENTORY §2.27 + 본 conclusion §2.1 |
| AC-2 | OCI latest PARAM 위치 정의 | DONE — `state/three_push/params/latest_runtime_param.json` |
| AC-3 | PC approved PARAM 생성 | DONE — `scripts/create_three_push_runtime_param.py --source manual_seed --approve` |
| AC-4 | PARAM OCI handoff | DONE — `scripts/sync_three_push_runtime_param.py` (scp + atomic rename + remote verify) |
| AC-5 | OCI PARAM 로드 | DONE — `scripts/run_three_push_runtime_oci.py` 가 `app/three_push_runtime_param.read_param_file` 호출, schema/필수필드/금지키 검증 |
| AC-6 | package message_text 정식 의존 제거 | DONE — 정식 entrypoint 는 `run_three_push_runtime_oci.py`. 기존 `run_three_push_oci.py` 는 manual recovery 로 격하 |
| AC-7 | runtime message 생성 | DONE — `app/three_push_runtime_message_builder.py` (runtime timestamp + param_id + push_kind + data availability + unavailable + 면책) |
| AC-8 | unavailable fail-closed | DONE — runtime 빌더가 외부 API 호출 없이 모든 source 를 기본 unavailable 로 표시. latest PARAM 부재 시 `status=failed, reason=missing_latest_param` |
| AC-9 | PARAM runtime Telegram 발송 | DONE — PUSH-1 market_briefing send → status=sent, telegram_sent=true |
| AC-10 | 기존 guard 유지 | DONE — disabled / duplicate / forbidden wording / secret 비노출 모두 PASS (실측 확인) |
| AC-11 | duplicate key 전환 | DONE — `push_kind::param_id::KST_date` (예: `market_briefing::param-20260618T142511-622384::2026-06-18`) |
| AC-12 | package sync 격하 | DONE — `PC_THREE_PUSH_SYNC_TASKSCHEDULER.md` §0 격하 명시 + 기존 등록 schtasks 비활성화/제거 안내 |
| AC-13 | OCI crontab template 갱신 | DONE — `OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` 정식 §3 (runtime) + §3-fallback (package manual recovery) 분리 |
| AC-14 | 기존 산식 불변 | DONE — runtime/draft/message builder/exporter 코드 변경 0건 |
| AC-15 | ML 구현 없음 | DONE — ML 학습/튜닝/백테스트 0건. `future_ml_placeholder` 는 PARAM source 허용값으로 슬롯만 예약 |
| AC-16 | 신규 DB 없음 | DONE — file-based JSON 만 사용 (latest_runtime_param.json / history/<param_id>.json / runtime registry/status/history) |
| AC-17 | 신규 scheduler framework 없음 | DONE — OCI crontab 만 사용. Celery/Redis/Airflow/Prefect/Dagster 0건 |
| AC-18 | 금지 판단 없음 | DONE — 매수/매도/비중조절/조정장 확정/위험 threshold 확정 추가 0건. runtime 빌더는 명시적 면책 라인 포함 |
| AC-19 | 문서 갱신 | DONE — STATE_LATEST / B_NEXT_ACTIONS / FEATURE_INVENTORY §2.27 신규 + §2.26 격하 / BACKLOG (CONSOLIDATED 1건) / OCI_THREE_PUSH_CRONTAB_TEMPLATE / PC_THREE_PUSH_SYNC_TASKSCHEDULER / 본 conclusion |

---

## 2. 산출물

### 2.1 신규 backend 모듈 (3종)

| 파일 | 역할 | 핵심 |
|---|---|---|
| `app/three_push_runtime_param.py` | `three_push_runtime_param.v1` 계약 | `RuntimeParam` dataclass / `build_manual_seed_param` / `validate_param_dict` / `from_dict` / `write_param_file` / `read_param_file`. 금지 키 11종 검사 (`message_text` / `buy_candidates` / `sell_candidates` / `cash_allocation` / `regime_confirmation` / `risk_threshold_confirmation` / `etf_ranking` / `token` / `chat_id` / `bot_token` / `telegram_token` / `telegram_chat_id`). `param_source` 허용값: manual_seed / baseline_static / future_ml_placeholder / ml_export |
| `app/three_push_runner_common.py` | 공통 헬퍼 | `.env` stdlib 로더 / Telegram send (token 마스킹, HTTPError 분류) / `forbidden_wording` 검사 / `secret_exposure` 검사 / registry helper (`load/save/is_already_sent/mark_sent`) / status/history writer. package runner 와 runtime runner 가 공유. 지시문 §1 Q1 답변 "공통 헬퍼는 최소 범위만 추출" 준수 |
| `app/three_push_runtime_message_builder.py` | OCI runtime 전용 단순 빌더 | `build_runtime_message(push_kind, param, runtime_kst_iso, available_sources, extra_notes)`. 외부 API 호출 0건. 모든 source 기본 unavailable. 출력 구조: 헤더 (title/runtime_kst/param_id/param_source/push_kind) → 데이터 가용성 → unavailable 또는 별도 확인 필요 → 본문 안내 → 면책 |

### 2.2 신규 entrypoint + PARAM 스크립트 (4종)

| 파일 | 역할 |
|---|---|
| `scripts/run_three_push_runtime_oci.py` | OCI **정식** crontab runner. latest PARAM 로드 → secret 가드 → enabled_push_kinds 확인 → runtime 메시지 생성 → forbidden wording → dry-run/send 분기 → enable flag → duplicate guard (key = `push_kind::param_id::KST_date`) → Telegram 발송. status/history 별도 경로 |
| `scripts/create_three_push_runtime_param.py` | PC PARAM 생성 + `--approve` 옵션 시 `latest_runtime_param.json` 으로 승격. `history/<param_id>.json` 별도 보존 |
| `scripts/sync_three_push_runtime_param.py` | PC → OCI scp + atomic rename + verify. env `OCI_SSH_TARGET`, `THREE_PUSH_REMOTE_PARAM_DIR` 사용 |
| `scripts/verify_three_push_param_oci.py` | OCI 측 stand-alone 검증 (stdlib only, app/* import 없음 — OCI 일시 환경에서도 동작) |

### 2.3 수정 문서 (4종)

| 파일 | 변경 |
|---|---|
| `docs/STATE_LATEST.md` | §1 현재 완료 상태를 본 Step 결과로 교체 + 직전 Step 격하 표기 |
| `docs/handoff/POC2_B_NEXT_ACTIONS.md` | §0 본 Step 결과 + 다음 분기 후보 4건 |
| `docs/handoff/POC2_FEATURE_INVENTORY.md` | §2.27 신규 (PARAM runtime 정식 항목) + §2.26 격하 표기 |
| `docs/backlog/BACKLOG.md` | `CONSOLIDATED_BACKLOG_DEBT_CLEANUP` 1건 (5건 sub-bullet 통합 — 지시문 §16 중복 확장 금지 준수) |
| `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` | §0 정식 운영 경로 변경 안내 + §3 정식 (runtime) / §3-fallback (package manual recovery) 분리 + §4 PARAM handoff 시간표 + §5/§6/§9 모두 runtime 명령으로 갱신 |
| `docs/handoff/PC_THREE_PUSH_SYNC_TASKSCHEDULER.md` | §0 격하 안내 + 기존 등록 schtasks 비활성화/제거 명령 + §1 이하 manual recovery 참고 절차 |
| `docs/handoff/POC2_PARAM_HANDOFF_OCI_RUNTIME_CONCLUSION.md` | 신규 (본 문서) |

### 2.4 격하된 산출물 (보존)

| 파일 | 상태 |
|---|---|
| `scripts/run_three_push_oci.py` | 보존 — manual recovery template (`OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` §3-fallback). 정식 crontab 등록 대상 아님 |
| `scripts/sync_three_push_packages.py` | 보존 — manual recovery / smoke test |
| `scripts/run_three_push_sync_task.ps1` | 보존 — manual recovery wrapper |
| `app/three_push_package_exporter.py` 등 PC builder | 보존 — manual recovery 시 package 생성 경로로 사용 가능. 정식 자동 발송에서는 호출되지 않음 |

---

## 3. 실측 결과 (2026-06-18, KST 23:25 ~ 23:26)

### 3.1 PC PARAM 생성 + handoff

```text
create_three_push_runtime_param.py --source manual_seed --approve --description "..." --note "..."
→ status: approved
→ param_id: param-20260618T142511-622384
→ latest_path: state/three_push/params/latest_runtime_param.json
→ history_path: state/three_push/params/history/param-20260618T142511-622384.json

sync_three_push_runtime_param.py
→ OCI 대상: oci-krx → /home/ubuntu/krx_hyungsoo/state/three_push/params
→ [scp] PARAM upload OK (atomic via .tmp → rename)
→ [verify] OK (OCI 측 verify_three_push_param_oci.py 실행 결과 status=ok)
→ status: success
```

### 3.2 OCI runtime dry-run 3종

| push_kind | status | message_text_length | param_id | runtime_kst |
|---|---|---|---|---|
| market_briefing | dry_run_success | 581 | param-20260618T142511-622384 | 2026-06-18T23:26:10+09:00 |
| holdings_briefing | dry_run_success | 542 | param-20260618T142511-622384 | 2026-06-18T23:26:10+09:00 |
| spike_or_falling_alert | dry_run_success | 489 | param-20260618T142511-622384 | 2026-06-18T23:26:11+09:00 |

availability = `{available: 0, unavailable_or_other: 0}` (외부 source 호출 0건 — 빌더는 모든 source 를 list에 기록하지 않고 unavailable 라인만 출력. 향후 OCI 측 가용 source 가 추가되면 `available_sources` 인자로 전달).

### 3.3 OCI runtime send + duplicate guard

```text
1차 send (market_briefing)
→ status: sent
→ telegram_attempted: true / telegram_sent: true
→ duplicate_key: market_briefing::param-20260618T142511-622384::2026-06-18

2차 send 즉시 재실행 (동일 push_kind / param_id / KST_date)
→ status: skipped
→ reason: duplicate_runtime
→ telegram_attempted: false / telegram_sent: false
```

### 3.4 fail-closed / disabled guard

```text
latest PARAM 일시 제거 → dry-run holdings_briefing
→ status: failed
→ reason: missing_latest_param
→ telegram_attempted: false

PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED=false → send holdings_briefing
→ status: skipped
→ reason: push_kind_disabled
→ telegram_attempted: false
```

### 3.5 secret 노출 검사

PARAM dict 내 `assert_no_sensitive_keys` 통과 (token/chat_id/bot_token 키 부재). status 파일 및 history.jsonl 에 token/chat_id 미기록 확인.

---

## 4. 회귀 검증

### 4.1 신규 코드만 추가. 기존 코드 변경 0건

| 영역 | 변경 |
|---|---|
| `scripts/run_three_push_oci.py` | 0 라인 변경 (보존) |
| `scripts/sync_three_push_packages.py` | 0 라인 변경 (보존) |
| `app/runtime_package.py` / `draft.py` / `draft_three_push.py` / `message_*` / `push_context*` | 0 라인 변경 |
| `app/three_push_package_exporter.py` | 0 라인 변경 |
| 산식 / Market Discovery / ETF Exposure / NAV / momentum 계산 | 0 라인 변경 |
| frontend / Approval UI | 0 라인 변경 |

### 4.2 pytest

본 conclusion 작성 시점 백그라운드 실행 중. 결과는 보고서 §17 verification 섹션에 기재.

직전 Step 동일 환경 기준 533 passed + 1 failed (`tests/test_three_push_contract.py::test_generate_spike_alert_via_unified_endpoint`, Clean tree 에서도 동일 실패하는 기존 회귀, 본 Step 무관). BACKLOG `CONSOLIDATED_BACKLOG_DEBT_CLEANUP` 에 기록.

### 4.3 black / flake8

본 Step 신규 모듈 + 신규 스크립트 모두 black --check 통과 / flake8 신규 위반 0건 (기존 파일의 기존 위반은 무관).

### 4.4 frontend lint / build

frontend 변경 0건. 직전 Step 시점 lint OK / build OK 그대로 유지될 것으로 예상.

---

## 5. 지시문 외 변경

- 검증 단계에서 OCI 에 신규 backend/scripts 를 commit 전에 scp 로 임시 전송하여 실측 진행 (정식 push 후 OCI git pull 절차 전에 실측을 먼저 통과시키기 위한 운영 패턴). commit/push 후 OCI 가 git pull 하면 동일 코드가 정식 경로로 들어옴.
- 본 Step 작업 도중 PARAM 의 `extra` 직렬화에서 금지 키와 충돌하지 않도록 `RuntimeParam.to_dict` 에 `FORBIDDEN_PARAM_TOP_LEVEL_KEYS` 필터 추가. 지시문 §6 "허용 예: param_description / source_note 등" 을 안전하게 보장.

---

## 6. 알려진 한계 / 미완성

- **사용자 OCI crontab 갱신 필요**: 기존 crontab entry 는 여전히 `run_three_push_oci.py` (package fallback) 를 호출. 사용자가 `crontab -e` 로 `run_three_push_runtime_oci.py` 로 교체해야 정식 자동 발송이 동작. 본 Step 의 산출물 + 실측만으로는 자동 trigger 도달이 확인되지 않음.
- **기존 등록 PC Task Scheduler**: 직전 Step 에서 사용자가 등록했다면 비활성화/제거 필요. 등록된 채로 두면 무의미한 package sync 가 계속 실행됨.
- **OCI runtime data availability**: 본 Step 의 runtime 빌더는 모든 source 를 기본 unavailable 로 표시. 실제 가용 source 점진 확장은 BACKLOG `CONSOLIDATED_BACKLOG_DEBT_CLEANUP` 대상.
- **기존 회귀 1건 (test_generate_spike_alert_via_unified_endpoint)**: 본 Step 무관, 직전 Step부터 동일 실패. BACKLOG 통합 기록.
- **PARAM history rotation 미적용**: `state/three_push/params/history/` 는 무한 누적. 운영 기간이 길어지면 logrotate 도구 또는 별도 cleanup 필요 (본 Step scope 외).

---

## 7. 다음 검증자(Codex)에게 알릴 점

- 본 Step 은 책임 분리 전환이 핵심. PC 가 매 발송마다 message package 를 만드는 부담을 제거하고, OCI 가 latest PARAM 을 고정 사용해 runtime 시점 데이터를 보고 메시지를 만든다.
- 기존 package 경로 산출물은 **삭제 없이 격하**되었다. 지시문 §4.1 명시 사항. 이는 KS-9 (복잡도 폭증) 위반이 아니라 **fallback 채널 보존** 의도.
- duplicate guard key 가 package 경로의 `push_kind + package_id` 에서 runtime 경로의 `push_kind + param_id + KST_date` 로 전환됨. 둘은 별도 registry (`oci_sent_registry.json` vs `oci_runtime_sent_registry.json`) 를 사용하므로 상호 간섭 없음.
- PARAM 의 `param_source = future_ml_placeholder` 는 슬롯만 예약. 실제 ML 학습/튜닝/백테스트는 본 Step 범위 외 (지시문 §15).
- pytest 1 failed 는 직전 Step 부터 존재하는 기존 회귀. Clean tree (이전 main 기준) 에서도 동일 실패 확인됨. 본 Step 의 PARAM runtime 경로와는 무관 — 본 Step 책임 아님.

---

## 8. 사용자 확인이 필요한 항목

1. **OCI 실제 Telegram 수신 확인** — OCI runner 가 status=sent 반환했으나 사용자 단말기에서 수신했는지 확증 필요.
2. **OCI crontab 갱신 시점 결정** — `OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` §3 정식 template 으로 사용자가 직접 `crontab -e` 갱신 필요.
3. **기존 등록 PC Task Scheduler 처리** — 격하된 sync 가 등록되어 있다면 `PC_THREE_PUSH_SYNC_TASKSCHEDULER.md` §0.3 명령으로 비활성화/제거.
4. **PARAM 변경 운영 사이클 검증** — manual_seed 외 baseline_static 등으로 PARAM 변경 → sync → OCI dry-run 비교 검증 진행 여부.
5. **commit + push 승인** — 본 Step 산출물 commit 후 push 진행 여부. push 는 항상 사용자 명시 승인 사안.
