# POC2 — PC-to-OCI 3-PUSH Evidence Package Sync Conclusion

작성일: 2026-06-15 / FIX r1: 2026-06-15 (OCI 실행 완료 + holdings bug fix + dry_run status 분리)
STEP: THREE_PUSH_EVIDENCE_PACKAGE_OCI_SYNC
상태: DONE

---

## 1. 목표 요약

PC 에서 생성한 `three_push_runtime_package.v1` package 3종과 manifest 를 OCI 가
읽을 수 있는 경로로 동기화하는 최소 경로 구현.

OCI crontab runner 이전에 package 공급 경로를 확보한다.

---

## 2. 구현 결과

### 신규 파일

| 파일 | 역할 |
|---|---|
| `app/three_push_package_exporter.py` | push_kind 별 package artifact export + manifest 생성 + token 비노출 가드 + atomic 저장 |
| `scripts/sync_three_push_packages.py` | PC local 생성 → OCI SCP atomic 업로드 → OCI verification → status 기록. `--dry-run` / `--export-only` 지원 |
| `scripts/verify_three_push_packages_oci.py` | OCI 에서 standalone 실행되는 검증 스크립트. manifest + package 3종 schema / push_kind / token 비노출 검증. stdlib 만 사용 |

### 신규 state 경로

| 경로 | 내용 |
|---|---|
| `state/three_push/packages/latest_market_briefing.json` | PUSH-1 latest package artifact |
| `state/three_push/packages/latest_holdings_briefing.json` | PUSH-2 latest package artifact |
| `state/three_push/packages/latest_spike_or_falling_alert.json` | PUSH-3 latest package artifact |
| `state/three_push/packages/manifest.json` | push_kind 3종 포인터 manifest |
| `state/three_push/sync_status_latest.json` | sync 실행 결과 기록 |

---

## 3. AC 달성 현황

| AC | 내용 | 결과 |
|---|---|---|
| AC-1 | push_kind 별 package 생성 | DONE — `build_market/holdings/spike_*_package()` |
| AC-2 | manifest 생성 | DONE — `build_manifest()` + `save_manifest()` |
| AC-3 | schema 검증 (`three_push_runtime_package.v1`) | DONE — `_validate_package()` + verify script |
| AC-4 | OCI 업로드 | DONE — SCP atomic (tmp → mv) |
| AC-5 | OCI 읽기 검증 | DONE — `verify_three_push_packages_oci.py` 원격 실행 |
| AC-6 | atomic upload | DONE — *.tmp 업로드 후 rename. manifest 마지막 |
| AC-7 | token 비노출 | DONE — `_assert_no_sensitive_keys` 재귀 검증 |
| AC-8 | SQLite 이전 없음 | DONE — 파일 기반 sync 만 |
| AC-9 | 신규 scheduler 없음 | DONE — 수동 스크립트 실행만 |
| AC-10 | Telegram 발송 없음 | DONE — Telegram 코드 0건 |
| AC-11 | 기존 message_text 변경 없음 | DONE — 기존 builder 재사용만 |
| AC-12 | 기존 계산 산식 불변 | DONE — 산식 변경 0건 |
| AC-13 | 상태 기록 | DONE — `sync_status_latest.json` |
| AC-14 | 문서 갱신 | DONE — STATE_LATEST / POC2_B_NEXT_ACTIONS / POC2_FEATURE_INVENTORY / CONCLUSION |

---

## 4. 제외 범위 준수 확인

| 항목 | 결과 |
|---|---|
| OCI crontab runner 구현 | 0건 |
| crontab 등록 | 0건 |
| Telegram send | 0건 |
| send enable flag | 0건 |
| scheduler | 0건 |
| SQLite OCI 이전 | 0건 |
| 신규 DB | 0건 |
| DB replication | 0건 |
| 신규 external source | 0건 |
| 신규 PUSH 전용 endpoint | 0건 |
| message_text 문구 개선 | 0건 |
| 매수/매도/교체/비중 조절 판단 | 0건 |
| 위험 threshold 확정 | 0건 |

---

## 5. 실행 방법

```bash
# 1) export-only (OCI SSH 없어도 local 저장만)
python scripts/sync_three_push_packages.py --export-only

# 2) dry-run (OCI 환경변수 있어도 실제 SCP/SSH 없음)
python scripts/sync_three_push_packages.py --dry-run

# 3) 실제 sync (OCI_SSH_TARGET + THREE_PUSH_REMOTE_PACKAGE_DIR 필요)
python scripts/sync_three_push_packages.py
```

### 필요 환경변수

```bash
OCI_SSH_TARGET=ubuntu@<oci-host>                     # 필수
THREE_PUSH_REMOTE_PACKAGE_DIR=~/krx-alertor/state/three_push/packages  # 권장
# 또는 OCI_REMOTE_INBOX=... (자동으로 sibling 경로 추론)
OCI_SSH_KEY_PATH=/path/to/key                        # 선택
```

---

## 6. 검증 결과

- black / flake8 / py_compile: **PASS**
- pytest: **534 passed** (회귀 0)
- 신규 의존성: 없음
- **OCI 실행 결과 (2026-06-15 실측)**:
  - `python scripts/sync_three_push_packages.py` (OCI_SSH_TARGET=oci-krx, OCI_REMOTE_INBOX 기반 경로 자동 추론)
  - export: package 3/3 success (`market_briefing` / `holdings_briefing` / `spike_or_falling_alert`)
  - OCI upload: package 3/3 ok, manifest ok (atomic tmp→rename 확인)
  - OCI remote dir: `/home/ubuntu/krx_hyungsoo/state/three_push/packages`
  - OCI read verification: **status=success** (manifest schema ✓ / push_kind 3종 ✓ / package schema ✓ / generation_status ✓ / token 비노출 ✓)
  - sync_status_latest.json: 생성 확인 (`state/three_push/sync_status_latest.json`)

### FIX r1 — 검증자 REJECTED 반영 (2026-06-15)

| 항목 | 수정 내용 |
|---|---|
| holdings_briefing package 생성 실패 | `three_push_package_exporter.py` — holdings 파일이 `{"holdings": [...]}` dict 형태인 경우 `raw.get("holdings", [])` 로 처리하도록 수정 (기존: list 아니면 `[]` fallback → 0건 오류) |
| subprocess 인코딩 오류 | `sync_three_push_packages.py` — `_scp_upload` / `_ssh_run` 의 `subprocess.run` 에 `encoding="utf-8", errors="replace"` 추가 (Windows cp949 환경 UnicodeDecodeError 방지) |
| dry_run status 오인 가능성 | `sync_three_push_packages.py` — dry_run 모드는 최종 status 를 `"dry_run"` 으로 고정 (기존: `"success"` 로 기록돼 실제 업로드와 구분 불가) |
| runtime artifact gitignore 누락 | `.gitignore` — `state/three_push/packages/` + `state/three_push/sync_status_latest.json` 추가 |

---

## 7. 다음 단계 (사용자 결정 대기)

1. **OCI crontab runner 구현** — 본 STEP 에서 공급한 manifest 소비 + Telegram 발송
2. **하루 3회 발송 시간 + 자동 발송 UX** 결정
3. runtime source 수동 refresh endpoint / 뉴스 source 도입은 BACKLOG
