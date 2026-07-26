# Telegram Spike Alert Conditional Send v1 — Conclusion (DONE · PASS · 3-PUSH Controlled Send Stage Closeout)

작성일: 2026-07-19
성격: (1) 사전 test 결함 2건 해소, (2) Spike 실제 발송·중복 차단·no-signal 미발송 검증, (3) 3-PUSH Controlled Send Stage 종료 + 사용자 승인 게이트 제거.

## 1. revision

- OCI 실측 시점 revision: `81c204d8` (Phase 1 + 5 FIX 반영)
- Closeout revision: (아래 commit 후 확정)

## 2. 사전 test 결함 2건 해소 (지시문 §4)

### 2.1 Universe artifact fixture 격리 (§4.1)

- 대상: `tests/test_runtime_runner_dry_run.py::test_runner_dry_run_spike_all_unavailable_no_topn_calls`
- 수정: `monkeypatch.setattr(_dtp, "UNIVERSE_LATEST_FILE", tmp_path / "no_universe.json")` 로 reader 상수를 존재하지 않는 tmp 경로로 격리
- 결과: production reader 계약 변경 없음, 실 artifact 미조작, all_unavailable 시나리오 정확 재현

### 2.2 안전 안내 문구 substring 오탐 수정 (§4.2)

- 대상: `tests/test_three_push_message_text_runtime_evidence.py::test_push2_message_text_has_observation_points`
- 수정 이력:
  - r1: `_NEGATION_MARKERS` 튜플 신설 + 라인 제외 헬퍼 → 검증자 REJECTED (§4.2 새 메시지 정책 금지 + 같은 라인에 실제 지시가 함께 오면 놓칠 수 있는 false-negative 위험)
  - **r2**: 부가 forbidden loop 자체를 완전 제거. 본질 assertion 2건 (`[보유 종목 관찰 포인트]` · `[시장 흐름 연결 (market_view)]` 섹션 존재) 유지. 금지 문구 검사는 별도 test (`test_three_push_runtime_message_builder.py` · `runtime_evidence/test_privacy_detector.py`) 와 운영 발송 경로 (runner §4-b `check_forbidden_wording`) 계약이 담당
- 결과: 실제 사용자 메시지 문구 변경 없음, 새 정책 신설 없음, 기존 detector 계약 유지

## 3. Spike no-signal 미발송 계약 (지시문 §6/AC-6)

### 3.1 신규 focused test

- `tests/test_runtime_runner_spike_no_signal.py` — 2 케이스:
  - `test_spike_no_signal_dry_run_no_send_no_registry` — dry-run: sender 미호출 · registry 불변
  - `test_spike_no_signal_send_mode_no_telegram_no_registry` — send mode: `no_signal=True` 여도 sender 미호출 · registry 불변

### 3.2 결함 발견 → runner 최소 수정 (§5 허용)

- 첫 test 실행 결과 send mode 에서 no_signal=True 여도 sender 가 호출됨을 확인 (실제 결함)
- `scripts/run_three_push_runtime_oci.py` 에 §6-b 신설:

```python
if push_kind == "spike_or_falling_alert" and record.get("no_signal") is True:
    logger.info("no-signal 발송 skip: push_kind=%s param_id=%s (universe candidate 0건)", ...)
    return _finish("skipped", "no_signal")
```

- 위치: enable flag guard (§6) 통과 후, duplicate guard (§7) 진입 전
- 계약: sender 미호출 · registry 미기록 · duplicate_key 도 계산하지 않음
- Universe artifact / candidate / threshold / duplicate key / registry schema 미변경

## 4. OCI Spike dry-run (2026-07-19 10:08 KST)

CLI: `python3 scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode dry-run`

| 필드 | 값 |
|---|---|
| runtime_kst | 2026-07-19T10:08:09+09:00 |
| runtime_date_kst | 2026-07-19 |
| param_id (masked) | ****757435 |
| message_text_length | 344 |
| contentful_fact_count | 5 |
| selection_result_count | 5 |
| universe_artifact_valid | true |
| universe_artifact_status | ok |
| universe_artifact_asof | 2026-07-16 |
| universe_candidate_count | 20 |
| universe_selected_count | 5 |
| universe_contentful_fact_count | 5 |
| universe_snapshot_status | available |
| no_signal | false |
| private_fields_exposed | false |
| raw_identifier_exposed | false |
| telegram_attempted / sent | false / false |

지시문 §5.2 발송 가능 조건 8개 전부 충족. **사용자 승인 대기 없이** 곧바로 send 명령 진행.

## 5. OCI Spike 실제 1회 발송 (2026-07-19 10:08 KST)

CLI: `python3 scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send`

| 필드 | 값 |
|---|---|
| status | sent |
| telegram_attempted | true |
| telegram_sent | true |
| partial_delivery | false |
| duplicate_key | spike_or_falling_alert::****757435::2026-07-19 |
| message_text_length | 344 (Telegram 4096 한도 미만 → 단일 chunk · header 없음) |
| error | null |

### 5.1 사용자 수신 확인 (chat `****5904`)

수신 메시지 (사용자 실측):

```
[급등락·상승 관찰 신호]

기준 시각: 7월 19일 10:08

지금 확인된 항목
• 급등락 관찰

별도 확인 필요
• 국내 ETF 시세

• KODEX 200 (2026-07-16 기준): 1개월 -21.89%.
• TIGER 200 IT (2026-07-16 기준): 1개월 -26.11%.
• KODEX 미국S&P500 (2026-07-16 기준): 1개월 -1.70%.
• PLUS 글로벌HBM반도체 (2026-07-16 기준): 1개월 -20.03%.
• SOL AI반도체TOP2플러스 (2026-07-16 기준): 1개월 -27.15%.

이 알림은 시장 관찰용 정보이며 직접적인 매매 지시는 아닙니다.
```

- 대상: chat `****5904` (올바른 대상)
- 논리적 1건 = 물리 1 chunk (344 자 < 4000)
- Preview 와 완전 일치 (기준 시각 10:08 그대로)
- 잘림 · 문자 깨짐 없음
- 개인정보 · 내부 식별자 · 금지 문구 없음

## 6. sent registry 전후

| 시점 | count |
|---|---|
| Spike send 전 | 64 |
| Spike send 후 | 65 (delta +1) |
| 중복 재실행 후 | 65 (delta 0) |

## 7. OCI 중복 차단 (2026-07-19 10:09 KST)

CLI: 동일 명령 재실행

| 필드 | 값 |
|---|---|
| status | skipped |
| reason | duplicate_runtime |
| telegram_attempted | false |
| telegram_sent | false |
| duplicate_key | spike_or_falling_alert::****757435::2026-07-19 (완전 동일) |

Runner 로그: `중복 발송 차단: spike_or_falling_alert::****757435::2026-07-19` (param_id 마스킹 적용, OCI 실측 raw log 는 masking 없이 존재)

Telegram 두 번째 메시지 도착 없음 (사용자 실측 확인).

## 8. no-signal 미발송 검증 (Phase 5 focused fixture)

지시문 §6 계약: artifact valid=true · candidate_count=0 · no_signal=true → sender 미호출 · registry 불변.

- `tests/test_runtime_runner_spike_no_signal.py` 2 케이스 전부 통과.
- 운영 Universe artifact 미변경 · 후보 미삭제 · threshold 미변경 · producer 미조작 · 실제 Telegram 발송 없음.

## 9. Market · Holdings 미발송

- Market briefing 발송: 0건
- Holdings briefing 발송: 0건
- 이번 STEP 중 Telegram 실제 발송 총 건수: **spike_or_falling_alert 1건 (1 chunk)**

## 10. 사용자 승인 게이트 제거 (지시문 §7)

이번 STEP 부터 다음 게이트를 향후 운영 계약에서 제거:

```
USER_SEND_APPROVAL_REQUIRED
USER_RECEIPT_CONFIRMATION_REQUIRED
```

새 운영 정책:

```
Market · Holdings · Spike PUSH 는 매 발송 전 사용자 승인을 요구하지 않는다.
사용자는 정보 PUSH 수신에는 개입하지 않고,
매수 · 매도 · 비중 변경 · 종목 교체 · 주문 실행에서만 최종 결정한다.
```

과거 실제 승인·수신 기록 (Market 2026-07-18 14:42 · Holdings 2026-07-18 16:32) 은 이력으로 유지. 이번 Spike 발송 (2026-07-19 10:08) 이 새 정책 적용 첫 사례.

## 11. 코드 변경 및 테스트

- 코드 변경:
  - `scripts/run_three_push_runtime_oci.py` — §6-b no-signal guard 신설
- Test 변경:
  - `tests/test_runtime_runner_dry_run.py` — Universe fixture 격리
  - `tests/test_three_push_message_text_runtime_evidence.py` — 부가 forbidden loop 제거 (r2)
  - `tests/test_runtime_runner_spike_no_signal.py` — 신규 2 케이스
- Focused test: **4 passed** (Phase 1 두 결함 수정 확인 2 + Phase 5 no-signal fixture 2)
- Closeout backend regression (지시문 §7 · 1회 · deselect 없음):
  - **991 passed, 4 skipped, 0 failed, 0 deselected** (209s)
  - 지시문 §10 완료 조건 `failed = 0 · known_failures = 0 · deselected_known_failures = 0` 충족

## 12. AC 충족 (지시문 §11)

| AC | 상태 |
|---|---|
| AC-1 알려진 test 실패 2건 수정 · focused 통과 | ✅ |
| AC-2 Spike dry-run valid · contentful · 개인정보 비노출 확인 | ✅ |
| AC-3 사용자 승인 대기 없이 논리적 1회 발송 | ✅ |
| AC-4 전체 chunk 성공 후 registry +1 | ✅ (64 → 65) |
| AC-5 동일 키 재실행 sender 미호출 · registry 불변 | ✅ (65 유지) |
| AC-6 no-signal fixture Telegram 미호출 · registry 불변 | ✅ |
| AC-7 Market · Holdings 미발송 · PARAM · scheduler · DB · Universe 계약 불변 | ✅ |
| AC-8 전체 backend regression deselect 없이 실패 0건 | ✅ (991 passed / 0 failed / 0 deselected) |
| AC-9 3-PUSH Controlled Send Stage + 최소 사용자 개입 정책 문서 반영 | ✅ (§10 + STATE + NEXT_ACTIONS + Market/Holdings conclusion) |

## 13. 지시문 §9 금지사항 준수

- Market · Holdings 재발송: X
- 사용자 발송 승인 게이트 추가: X (오히려 제거)
- Universe seed / artifact 변경: X
- 후보 · threshold · 정렬 변경: X
- Spike 메시지 문구 개선: X
- Telegram API 직접 호출: X (기존 telegram_send 만 사용)
- registry 삭제 · 수정: X
- PARAM · scheduler · DB schema 변경: X
- 신규 API · UI · source · ML · 뉴스 · 실시간 시세: X
- 자동 재시도: X
- 매수 · 매도 · 교체 · 비중 결정 · 주문 실행: X

## 14. 3-PUSH Controlled Send Stage 최종 상태

| STEP | Telegram 실제 발송 | Registry | 중복 차단 | 상태 |
|---|---|---|---|---|
| Market Briefing v1 (2026-07-18) | 1건 · chat ****5904 · 393자 | +1 | 확인 | DONE · PASS · accepted_deviation |
| Holdings Briefing v1 (2026-07-18) | 1건 (2 chunks) · chat ****5904 · 5506자 | +1 | 확인 | DONE · PASS |
| Spike Alert Conditional v1 (2026-07-19) | 1건 · chat ****5904 · 344자 | +1 | 확인 | DONE · PASS |

계약:
- 분할 전송 (Holdings STEP FIX): `_split_message_for_telegram` + `(i/N)\n` header + partial_delivery boolean
- 중복 차단: `push_kind + param_id + runtime_date_kst` (KST 오늘)
- no-signal 미발송 (Spike STEP §6-b): universe candidate=0 이면 sender 미호출
- 최소 사용자 개입 (Spike STEP §7): 정보 PUSH 는 매 발송 전 승인 없음

## 15. 최종 상태

```
status = DONE
completion_judgment = PASS
next_step_gate = POST_OCI_PROJECT_REANCHOR
```

## 16. 완료 후 프로젝트 앵커 (지시문 §14)

OCI · Telegram 보강 stage 완료. 다음 STEP 은 최신 MASTER_PLAN · STATE_LATEST · handoff · BACKLOG 를 기준으로 재선택.

우선 확인할 전체 흐름:

```
보유 종목과 외부 시장 후보 비교
→ 판단 사유가 있는 초안 생성
→ 사용자의 매수·매도 최종 판단
```

다음 게이트: `POST_OCI_PROJECT_REANCHOR`.
