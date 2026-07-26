# POC2 — OCI 3-PUSH Crontab Runner & Telegram Autosend Conclusion

작성일: 2026-06-15 / FIX r1: 2026-06-15 (guard 4건 보강) / FIX r2: 2026-06-15 (guard 4건 실측 확인) / FIX r3: 2026-06-15 (manifest.generated_at stale + data_cutoff dict + dry-run stale 구분) / FIX r4: 2026-06-16 (_load_dotenv_file 추가 + OCI package re-sync + OCI 전 항목 실측 PASS)
STEP: OCI_THREE_PUSH_CRONTAB_RUNNER_AUTOSEND
상태: DONE

---

## 1. 목표 요약

직전 Step 에서 PC-to-OCI package sync 를 완료한 상태에서,
OCI 에서 crontab 으로 PUSH-1 / PUSH-2 / PUSH-3 를 자동 실행하고
조건 충족 시 Telegram 으로 발송되는 runner 를 구현한다.

---

## 2. 구현 결과

### 신규 파일

| 파일 | 역할 |
|---|---|
| `scripts/run_three_push_oci.py` | OCI runner entrypoint — `--push-kind / --mode` 인자, guard 7종, Telegram 발송, status 기록. stdlib 전용 |
| `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` | push_kind 3종 crontab entry + 환경변수 설명 + dry-run 확인 절차 |

### 수정 파일

| 파일 | 수정 내용 |
|---|---|
| `app/three_push_package_exporter.py` | `build_holdings_briefing_package` — message_text 동기화 누락 bug fix. `build_message_text(run_id, payload)` 호출 후 `message_contract.message_text` 에 동기화 |
| `.gitignore` | OCI runner runtime artifact 3종 추가 (`oci_runner_status_latest.json` / `oci_runner_history.jsonl` / `oci_sent_registry.json`) |

### 신규 상태 경로 (gitignored)

| 경로 | 내용 |
|---|---|
| `state/three_push/oci_runner_status_latest.json` | 최신 runner 실행 결과 |
| `state/three_push/oci_runner_history.jsonl` | runner 실행 이력 (1행 1실행) |
| `state/three_push/oci_sent_registry.json` | 중복 발송 방지 registry (push_kind + package_id 키) |

---

## 3. AC 달성 현황

| AC | 내용 | 결과 |
|---|---|---|
| AC-1 | OCI runner entrypoint | DONE — `scripts/run_three_push_oci.py` |
| AC-2 | push_kind 3종 지원 | DONE — market_briefing / holdings_briefing / spike_or_falling_alert |
| AC-3 | dry-run 모드 | DONE — Telegram 0건, 검증 + status 기록 |
| AC-4 | send 모드 | DONE — 조건 충족 시 Telegram 발송 |
| AC-5 | 전체 enable flag guard | DONE — `PUSH_AUTOSEND_ENABLED` 미충족 시 `status=skipped` |
| AC-6 | push_kind별 enable guard | DONE — `PUSH_AUTOSEND_{KIND}_ENABLED` |
| AC-7 | package load | DONE — manifest + push_kind package 읽기 + schema 검증 |
| AC-8 | package 검증 | DONE — schema_version / push_kind / generation_status / package_id / message_text |
| AC-9 | 최신성 guard | DONE — 36h 기본, `THREE_PUSH_MAX_PACKAGE_AGE_HOURS` override |
| AC-10 | 중복 발송 방지 | DONE — `oci_sent_registry.json` push_kind+package_id 키 |
| AC-11 | Telegram secret 비노출 | DONE — token/chat_id 로그/status/error 에 출력 안 함, message_text 노출 시 발송 차단 |
| AC-12 | crontab template | DONE — `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` |
| AC-13 | status/log 기록 | DONE — `oci_runner_status_latest.json` + `oci_runner_history.jsonl` + `logs/three_push_cron.log` |
| AC-14 | 기존 package sync 구조 유지 | DONE — `sync_three_push_packages.py` 변경 0건 |
| AC-15 | 기존 PC Approval 구조 유지 | DONE — draft.py / delivery.py 변경 0건 |
| AC-16 | 신규 DB / scheduler framework 없음 | DONE — 0건 |
| AC-17 | 기존 계산 산식 불변 | DONE — 산식 변경 0건 |
| AC-18 | 금지 판단 문구 없음 | DONE — `_FORBIDDEN_PHRASES` 22종 검사, 감지 시 차단 |
| AC-19 | send 실측 | DONE — enable=false → `skipped`, enable=true → Telegram `status=sent` 실측 PASS |
| AC-20 | 문서 갱신 | DONE — STATE_LATEST / POC2_B_NEXT_ACTIONS / POC2_FEATURE_INVENTORY / CONCLUSION / CRONTAB_TEMPLATE |

---

## 4. 제외 범위 준수 확인

| 항목 | 결과 |
|---|---|
| PC Daily Run Control UI | 0건 |
| SQLite OCI 이전 | 0건 |
| 신규 DB | 0건 |
| Celery / Redis / Airflow / Prefect / Dagster | 0건 |
| 신규 scheduler framework | 0건 |
| 신규 뉴스 source | 0건 |
| message_text 문구 개선 | 0건 |
| 매수 / 매도 / 교체 / 비중 조절 판단 | 0건 |
| 조정장 확정 | 0건 |
| 위험 threshold 확정 | 0건 |

---

## 5. 실행 방법

```bash
# dry-run (검증만, Telegram 발송 없음)
python scripts/run_three_push_oci.py --push-kind market_briefing --mode dry-run
python scripts/run_three_push_oci.py --push-kind holdings_briefing --mode dry-run
python scripts/run_three_push_oci.py --push-kind spike_or_falling_alert --mode dry-run

# send (조건 충족 시 Telegram 발송)
PUSH_AUTOSEND_ENABLED=true PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED=true \
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... \
python scripts/run_three_push_oci.py --push-kind market_briefing --mode send
```

### 필요 환경변수

```bash
THREE_PUSH_PACKAGE_DIR=/home/ubuntu/krx_hyungsoo/state/three_push/packages  # 기본값
PUSH_AUTOSEND_ENABLED=true
PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED=true
PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED=true
PUSH_AUTOSEND_SPIKE_OR_FALLING_ALERT_ENABLED=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
THREE_PUSH_MAX_PACKAGE_AGE_HOURS=36  # 기본값
```

---

## 6. 검증 결과

- black / flake8: **PASS**
- pytest: **494 passed** (OCI 실측, 기존 환경 실패 40건은 이번 변경 전부터 존재 — 회귀 0)
- 신규 의존성: 없음 (stdlib 전용)
- **기능 검증 (2026-06-16 OCI 실측, FIX r4 최종)**:
  - dry-run market_briefing: `status=dry_run_success`, msg_len=1252
  - dry-run holdings_briefing: `status=dry_run_success`, msg_len=1793 (FIX r4: OCI re-sync 후)
  - dry-run spike_or_falling_alert: `status=dry_run_success`, msg_len=938
  - dry-run + stale manifest → `status=dry_run_stale`, `reason=stale_package` (FIX r3)
  - send + PUSH_AUTOSEND_ENABLED=false → `status=skipped`, `reason=autosend_disabled`
  - send + push_kind flag=false → `status=skipped`, `reason=push_kind_disabled`
  - send + stale (MAX_AGE=0) → `status=skipped`, `reason=stale_package`
  - send + `manifest.generated_at=2020-01-01` → `status=skipped`, `reason=stale_package` (FIX r3)
  - send + duplicate → `status=skipped`, `reason=duplicate_package`
  - send + registry 손상 → `status=failed`, `reason=registry_corrupted` (FIX r2)
  - send + `generation_status="weird"` → `status=failed`, `reason=package_load_error` (FIX r2)
  - send + `package_id` 없음 → `status=failed`, `reason=package_load_error` (FIX r2)
  - send + manifest path 존재하지 않음 → `status=failed`, `reason=package_load_error` (FIX r2)
  - send + enable=true + `.env` 자격증명 (OCI) → `status=sent`, `telegram_sent=true` (**OCI 실측 PASS**, FIX r4)
  - mock HTTP 404 → `malformed_telegram_api_url` 분류 (FIX r4)
  - mock HTTP 401 → `invalid_or_placeholder_bot_token` 분류 (FIX r4)
  - status 파일 token/chat_id 노출 확인: **0건**

---

## 7. exporter bug fix 내역

직전 Step (`PC-to-OCI 3-PUSH Evidence Package Sync`) 에서 `build_holdings_briefing_package` 가
`_build_holdings_payload` 호출 후 message_text 동기화를 누락해 holdings package 에
`message_text=""` 로 저장됨.

이번 Step 에서 `generate_draft_from_holdings` 와 동일하게 `build_message_text(run_id, payload)` 를
호출 후 `message_contract.message_text` 에 동기화하는 로직을 추가.

수정 후 holdings_briefing package message_text 길이: **2086** 자 (당시 PC 로컬 측정값).
FIX r4 OCI 실측값: **1793** 자 (2026-06-16 시황 반영 재생성).

---

## 8. 다음 단계 (사용자 결정 대기)

1. **OCI crontab 등록** — `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` 참고,
   발송 시간 확정 후 OCI `crontab -e` 로 3 entry 등록.
2. **PC sync 주기 확립** — runner 의 36h stale guard 만료 전 PC 에서
   `python scripts/sync_three_push_packages.py` 를 하루 1회 이상 실행.
3. **runtime source 수동 refresh endpoint** / **뉴스 source 도입** 은 BACKLOG.
