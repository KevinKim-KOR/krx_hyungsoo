# Telegram Holdings Briefing Controlled Send v1 — Conclusion (DONE)

작성일: 2026-07-18
성격: OCI 운영 실측. 기존 Runtime send · sent registry 계약 그대로. 실측 중 발견된 결함 1건 (Telegram 4096자 한도 초과) 은 sender 계층 최소 수정 (FIX (a)) 으로 이 STEP 내 해결.

## 1. revision

- Send 성공 실측 시점 OCI revision: `3d65aa9a` (FIX (a) 반영 commit)
- 이번 STEP closeout commit: (아래 commit 후 확정)

## 2. 최초 Preview (2026-07-18 16:22 KST · FIX 반영본)

| 필드 | 값 |
|---|---|
| runtime_kst | 2026-07-18T16:22:29+09:00 |
| runtime_date_kst | 2026-07-18 |
| param_id (masked) | ****757435 |
| param_source | manual_seed |
| Holdings 기준일 | 2026-07-03 (수익률) · 2026-07-04 (NAV) |
| holdings_loaded_count | 35 |
| holdings_contentful_fact_count | 35 |
| nav_contentful_fact_count | 32 |
| contentful_fact_count (합) | 67 |
| selection_result_count | 35 |
| message_text_length | 5506 |
| private_fields_exposed | false |
| raw_identifier_exposed | false |
| telegram_target_masked | ****5904 |
| autosend flags | PUSH_AUTOSEND_ENABLED=true · PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED=true |
| 자동 실행 위험 | 없음 (오늘=토, cron 평일 1-5 필터, holdings 12:30 이미 지남) |
| current_duplicate_key_exists | false |
| sent_registry_total (before) | 63 |

메시지 확인 (§4 Phase A):
- 수량 · 평균매입가 · 투자원금 (합산 포함) · account_group 미노출: ✅
- 내부 source key · raw param_id · reason code 미노출: ✅
- BUY/SELL/매수/매도/교체/비중 조정 문구 없음 (하단 안내문 "매도·교체·비중 조절을 지시하지 않습니다" 는 안내 성격): ✅
- 빈 문장 · placeholder 없음: ✅

특이사항 (기존 계약 산출 · 이번 STEP 변경 대상 아님):
- 종목명 중복 표기: KODEX 200 3회, KoAct 미국나스닥성장기업액티브 2회, RISE 네트워크인프라 2회 (계정별 loading 결과)
- "구성종목 반복 핵심: 원화현금" (SOL AI반도체TOP2플러스 evidence composer 산출)

## 3. 사용자 승인

- Preview 전문 전달 후 사용자 승인 확보 (재승인 · FIX 이후 신규 승인)
- 승인 내용: chat `****5904` 로 논리적 1 briefing = 물리 2 chunks 발송

## 4. 발송 직전 재확인 dry-run (2026-07-18 16:31 KST · Phase C)

CLI: `python3 scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode dry-run`

7 필드 최초 Preview (16:22) 와 비교:
- runtime_date_kst · Holdings 기준일 · holdings_loaded_count · contentful_fact_count · selection_result_count · message_text_length · 본문 종목/수치 → **전부 완전 일치** (runtime_kst 시각 문자열만 16:22 → 16:31)
- 재확인 결과: **핵심 내용 동일 확인 → Phase D send 명령 안내**

지시문 §4.C 계약 (승인 → dry-run 회신 → 비교 → send) 완전 준수. 이 절차는 직전 Market STEP §4.1 accepted_deviation 재발 방지 규칙 (send 직전 재확인 dry-run 을 선행 단독 단계로 분리) 을 이번 STEP 부터 무조건 적용한 결과.

## 5. 첫 발송 시도 (2026-07-18 16:32 KST · FIX 이전) — 결함 발견

**최초 send 시도 시점 (16:32 실측 이전, FIX 이전 상태 revision `df4b4a26`)**:

CLI: `python3 scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode send`

| 필드 | 값 |
|---|---|
| status | **failed** |
| reason | telegram_send_error |
| telegram_attempted | true |
| telegram_sent | **false** |
| error | `other_non_secret_error: HTTP 400` |
| duplicate_key | holdings_briefing::****757435::2026-07-18 (record 에 기록) |

**원인**: 메시지 5506 자 · HTML `parse_mode` · Telegram sendMessage 한도 4096 자 초과.

**registry 무결성**: `current_duplicate_key_exists=False`, `sent_registry_total_after_fail=63` (delta 0). 지시문 §9 FAIL 목록 "send 실패인데 registry 기록" 미해당. 재발송 시나리오 정상 진행 가능.

## 6. FIX (a) — telegram_send 분할 전송 지원

사용자 (a) 승인 하에 sender 계층 최소 수정으로 이 STEP 내 해결.

### 6.1 코드 변경

**`app/three_push_runner_common.py`** (FIX r1 + r2):
- 신규 상수 `_TELEGRAM_MESSAGE_MAX_CHARS = 4000` (한도 4096 · 안전 96)
- 신규 함수 `_split_message_for_telegram(text) -> list[str]`
  - 한도 이하 → 단일 chunk 반환 (기존 계약 유지, header 없음)
  - 초과 → 줄바꿈(`\n`) 경계 우선 분할
  - 한 line 자체가 한도 초과 → hard split (안전망)
  - 순수 분할 · 누락/요약/재작성 없음
  - `(i/N)\n` 순서 표식 header 부착 (지시문 "chunk 순서 표식 허용")
- `telegram_send(text) -> tuple[bool, Optional[str], bool]` **FIX r2 반환 확장**:
  - `(sent, error, partial_delivery)` 3-tuple
  - `partial_delivery=True` 조건: 다중 chunk 중 하나 이상 성공 후 후속 실패
  - 첫 chunk 부터 실패 · 단일 chunk 실패 · 검증 단계 실패 → `partial_delivery=False`
  - error 접두어 `partial_delivery_at_chunk_N_of_M` 유지 (기존 파싱 호환)
  - 자동 재시도 없음
  - "모든 chunk 성공 후에만 sent=true → registry +1" 은 runner 기존 `if sent: mark_sent()` 로직으로 자동 준수
- 신규 헬퍼 `_telegram_send_one(token, chat_id, text)`: 기존 send 본체 순수 이관

**`scripts/run_three_push_runtime_oci.py`** (FIX r2):
- Record 초기값에 `partial_delivery: False` 신규 필드 추가
- `sent, err, partial_delivery = telegram_send(message_text)` 3-tuple 언팩
- `record["partial_delivery"] = partial_delivery` 설정
- 기존 `if sent: mark_sent()` 로직 변경 없음

### 6.2 focused test + integration test

**`tests/test_telegram_send_chunking.py`** (15 케이스, FIX r2 반영):
- `_split_message_for_telegram`: 한도 이하 · 정확히 한도 · 초과 분할 무손실 · 순서 header · 각 chunk 한도 이하 · 초긴 line hard split · 5506자 현실 본문
- `telegram_send`: 단일 성공/multi 성공 (partial=False) · 1번째 chunk 실패 (partial=False) · 2번째 chunk 실패 (partial=True · 3번째 미호출) · 단일 chunk 실패 partial 접두 없음 · placeholder token 거부 (partial=False) · token in message 거부 (partial=False)

**`tests/test_runtime_runner_partial_delivery.py`** (3 integration 케이스, FIX r2 신규):
- 2번째 chunk 실패 → record `partial_delivery=True`, `telegram_sent=False`, `status=failed`, `reason=telegram_send_error`, registry 불변, history JSONL 에 `partial_delivery` 필드 포함 append
- 1번째 chunk 실패 → record `partial_delivery=False`, registry 불변
- 전 chunk 성공 → record `partial_delivery=False`, `telegram_sent=True`, registry +1

### 6.3 정적 검사

- black --check: 통과 (전체 249 files)
- flake8 --max-line-length=100: 통과
- pytest focused (chunking + partial_delivery): **18 passed**
- pytest closeout 회귀 (`tests/` · `--ignore=tests/backtest`):
  - Deselect 없는 실행: **2 failed, 987 passed, 4 skipped** — 실측 그대로 (은닉 없음)
  - Deselect 2 (사전 결함 · 이번 FIX 무관) 반영 실행: **987 passed, 4 skipped, 2 deselected** (222s)
  - 실패 2건은 §13.1 사전 test 결함 (Universe artifact fixture 미격리 · 문구 substring 매치). 이번 FIX (sender 3-tuple · runner record) 와 인과관계 없음. BACKLOG 이관 후 설계자 보고 대상. 지시문 §7 "closeout 에서 전체 회귀 1회" 는 실행 완료, 사전 결함 2건은 이번 STEP 의 코드 변경 결과가 아님

### 6.4 미변경 (계약 준수)

- Holdings evidence composer / builder / 산식 / 선정 기준
- Duplicate key 계약 / registry schema
- Runner 실행 흐름 (§ 1 active PARAM 로드 ~ §7 duplicate guard ~ §8 telegram_send 호출 순서 · dry-run 조기 종료 조건 · mark_sent 조건)
- PARAM / scheduler / DB schema
- 다른 push_kind (market_briefing · spike_or_falling_alert) 계약

Runner 파일 (`scripts/run_three_push_runtime_oci.py`) 자체는 FIX r2 에서 record 초기값에 `partial_delivery: False` 필드 1개 추가 + `telegram_send` 3-tuple 언팩 + `record["partial_delivery"] = partial_delivery` 대입만 반영 (§6.1). Runner 의 실행 순서 · guard · registry 계약은 전부 유지.

FIX r1 commit push: revision `3d65aa9a` (2026-07-18 16:22 실측 이전 시점). OCI 반영 후 Preview 재시작.
FIX r2 commit push: (closeout commit · 아래).

## 7. 재시작 Preview 및 재확인 dry-run

FIX 이후 지시문 "수정 후에는 다시 최초 Preview부터 진행" 준수.

- 재시작 최초 Preview (2026-07-18 16:22 KST): §2 표 동일 값. FIX 는 sender 계층만 수정, builder/composer 미변경이므로 preview 본문 완전 동일.
- 로컬 chunk 분할 시뮬레이션 (`_split_message_for_telegram(msg=5506)`): **2 chunks**
  - Chunk 1/2: 헤더 `(1/2)` + 본문 4001 자
  - Chunk 2/2: 헤더 `(2/2)` + 본문 1516 자
- 사용자에게 예상 chunk 수 · 각 chunk 대략 크기 사전 안내 후 Phase B 재승인 확보.
- Phase C 재확인 dry-run (16:31 KST): §4 완전 통과.

## 8. 실제 첫 발송 (2026-07-18 16:32 KST · FIX 반영본)

CLI: `python3 scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode send`

| 필드 | 값 |
|---|---|
| status | sent |
| runtime_kst | 2026-07-18T16:32:04+09:00 |
| runtime_date_kst | 2026-07-18 |
| param_id (masked) | ****757435 |
| message_text_length | 5506 |
| contentful_fact_count | 67 |
| selection_result_count | 35 |
| holdings_snapshot_status | available |
| holdings_loaded_count | 35 |
| holdings_evidence_item_count | 35 |
| holdings_contentful_fact_count | 35 |
| nav_contentful_fact_count | 32 |
| holdings_selection_result_count | 35 |
| rendered_holdings_fact_count | 35 |
| private_fields_exposed | false |
| raw_identifier_exposed | false |
| duplicate_key | holdings_briefing::****757435::2026-07-18 |
| telegram_attempted | true |
| telegram_sent | true |
| error | null |

승인 시점 대비 재확인 (Phase C) 5필드 · 본문 완전 동일. `runtime_kst` 시각 문자열만 16:31 → 16:32.

**참고**: 이 실측 record 는 FIX r2 이전 revision `3d65aa9a` 시점 실행이라 `partial_delivery` 필드가 없습니다. FIX r2 (§6.1) 이후 revision 부터는 record 에 `partial_delivery: false` (성공 케이스) 필드가 명시적으로 포함됩니다. 이 사실은 record 검증 시 참고. 실측 결과 자체 (전 chunk 성공) 는 새 계약에서 `partial_delivery=false` 로 일치.

## 9. 사용자 수신 확인

- 대상: chat `****5904` (올바른 대상)
- 도착 chunk: `(1/2)` + `(2/2)` 정확히 2건 (논리적 1 briefing = 물리 2 chunks · AC-6 정정 반영)
- 두 chunk 이어 붙이면 Preview 5506자 본문과 완전 일치 (기준 시각 표기만 16:31 → 16:32)
- 각 chunk 본문 잘림 · 문자 깨짐 없음
- 종목명 · 수치 · NAV · 괴리율 정상 표시
- `(1/2)` · `(2/2)` header 각 chunk 앞에 정확히 1회씩 표시 (사용자 붙여넣기 시 수동 `(2/2)` 라벨 겹침은 붙여넣기 아티팩트, 실제 Telegram 화면에는 header 1회만)

## 10. sent registry 전후

| 시점 | count |
|---|---|
| 발송 전 | 63 |
| FIX 이전 첫 시도 실패 후 | 63 (delta 0 · §9 FAIL 미해당) |
| FIX 반영 실제 send 성공 후 | 64 (delta +1) |
| 재실행 (중복 차단) 후 | 64 (delta 0) |

## 11. 중복 차단 실측 (2026-07-18 16:34 KST)

CLI: `python3 scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode send` (동일 키 재실행)

| 필드 | 값 |
|---|---|
| status | skipped |
| reason | duplicate_runtime |
| telegram_attempted | false |
| telegram_sent | false |
| duplicate_key | holdings_briefing::****757435::2026-07-18 (첫 발송과 완전 동일) |

Runner 로그: `중복 발송 차단: holdings_briefing::****757435::2026-07-18`

Telegram 두 번째 발송 도착 없음 (사용자 실측 확인).

## 12. Market · Spike 미발송

- 이번 STEP 중 Telegram 실제 발송 총 건수: **holdings_briefing 1건 (2 chunks)**
- market_briefing 발송: 0건
- spike_or_falling_alert 발송: 0건

## 13. 코드 변경 및 테스트

- 코드 변경 (FIX r1 + r2):
  - `app/three_push_runner_common.py` (sender 분할 지원 + 3-tuple 반환)
  - `scripts/run_three_push_runtime_oci.py` (record 에 `partial_delivery` 필드)
- 신규 test:
  - `tests/test_telegram_send_chunking.py` (15 케이스, sender 계약)
  - `tests/test_runtime_runner_partial_delivery.py` (3 케이스, runner record + registry integration)
- Closeout backend regression (지시문 §7, 1회):
  - Deselect 없는 실제 실행: **2 failed, 987 passed, 4 skipped**
  - 사전 결함 2건 deselect 후: **987 passed, 4 skipped, 2 deselected** (222s)
  - 실패 2건 상세: §13.1 (Universe artifact fixture 미격리 · 문구 substring 매치). 이번 FIX (sender · runner record) 무관 · BACKLOG 이관 · 설계자 별도 보고 대상 (§13.2)
- 지시문 §7: FIX 라운드 (r1 → r2) 마다 전체 회귀 반복 없이 r2 확정 후 closeout 에서 1회만 수행

### 13.1 Deselected 2건 (사전 test 결함, 이번 FIX 와 무관, BACKLOG 이관)

1. `tests/test_runtime_runner_dry_run.py::test_runner_dry_run_spike_all_unavailable_no_topn_calls`
   - 원인: Universe STEP 산출물 (`state/universe/universe_momentum_latest.json`) 이 실제 존재하여 spike composer 가 5 candidate evidence 생성. Test 는 all_unavailable 시나리오 (contentful=0) 를 기대. Test 가 universe artifact 도 `tmp_path` 로 격리해야 하지만 monkeypatch 안 되어 있음.
   - 이번 STEP scope 밖 (sender 결함 아님).

2. `tests/test_three_push_message_text_runtime_evidence.py::test_push2_message_text_has_observation_points`
   - 원인: 메시지 안내 문구 "이 값은 매수/매도 지시가 아닙니다" 가 test 의 substring 검사 `"매도 지시" not in msg` 에 걸림. Message contract 정렬 commit (`65c04362`, 2026-06-20) 시 문구 변경되었으나 test 는 그 이후 갱신되지 않음.
   - 이번 STEP scope 밖 (sender 결함 아님).

두 결함 모두 이번 FIX (telegram_send 분할 · partial_delivery 계약) 와 인과관계 없음. BACKLOG 이관 후 별도 STEP 에서 처리.

### 13.2 설계자 보고 대상 (사용자 확정)

사용자 방침 (2026-07-18): "BACKLOG 로 보낸 것에 대한 부분 제외하면 VERIFIED. BACKLOG 로 보낸 것에 대해서 설계자에게 보고하는 것으로 이번 단계를 확정하겠습니다."

**설계자 보고 요약**:

- 위 §13.1 사전 test 결함 2건은 이번 Telegram Holdings Controlled Send v1 STEP 의 코드 변경 (sender 3-tuple · runner record `partial_delivery`) 과 인과관계 없음. 이 STEP 이전 시점에도 동일하게 실패 상태였을 가능성 (실측 미확인) 이 있음.
- 원인:
  1. **Universe artifact fixture 미격리**: Universe Momentum Evidence Publication v1 STEP 산출물 (`state/universe/universe_momentum_latest.json`) 이 실제 파일로 생성된 이후, 이 test 가 `tmp_path` 로 격리되지 않아 spike composer 가 실제 파일을 참조하여 5 candidate evidence 를 생성. Test 는 all_unavailable 시나리오 (contentful=0) 를 기대.
  2. **메시지 안내 문구 substring 매치**: Message contract 정렬 commit (`65c04362`, 2026-06-20) 시 안내 문구 "이 값은 매수/매도 지시가 아닙니다" 로 변경되어 test 의 substring 검사 `"매도 지시" not in msg` 에 걸림. Test 는 whole word 매칭 또는 문구 제외로 개선 필요.
- 이번 STEP 지시문 §5 (허용) · §6 (금지) 를 종합할 때 이 사전 결함들의 test-side 수정은 이번 STEP scope 밖 (sender/registry 결함 아님). 별도 STEP 지시문 확정 후 처리.
- 이번 STEP 은 사용자 방침에 따라 위 2건을 BACKLOG 이관 + 설계자 보고 조건 하에 **DONE · PASS** 로 확정.

## 14. AC 충족 (지시문 §8)

| AC | 상태 |
|---|---|
| AC-1 직전 Market STEP 문서 DONE/PASS/accepted_deviation 정정 | ✅ |
| AC-2 Holdings Preview contentful + 개인정보 · 내부 식별자 미노출 | ✅ |
| AC-3 사용자 승인 (Preview 확인 후) | ✅ (재승인, FIX 이후) |
| AC-4 승인 후 독립 dry-run 회신 · 비교 완료 후에만 send 명령 제공 | ✅ (Phase C 재확인 통과 후 D 안내) |
| AC-5 기존 Runtime send 경로로 holdings 만 1회 발송 | ✅ |
| AC-6 올바른 Telegram 대상 · 메시지 수신 · 잘림/깨짐 없음 (정정: 논리적 1건 · 물리 chunk 여러 건 허용) | ✅ (chat ****5904 · 2 chunks) |
| AC-7 sent registry +1 | ✅ (63 → 64) |
| AC-8 동일 키 재실행 sender 미호출 · registry +0 | ✅ (skipped · 64 유지) |
| AC-9 Market · Spike 미발송 · PARAM/scheduler/DB 계약 불변 | ✅ |
| (참고 · FIX r2) `partial_delivery` boolean 필드 명시 · 오류 문자열 파싱 의존 제거 | ✅ (§6.1 sender 3-tuple + runner record 필드) |
| (참고 · FIX r2) 첫 chunk 성공 + 두 번째 chunk 실패 통합 test | ✅ (§6.2 `tests/test_runtime_runner_partial_delivery.py`) |

## 15. 지시문 §6 금지사항 준수

- 발송 직전 dry-run 결과 회신 전 send 명령 제공: X (Phase C 재확인 통과 후에만 D 안내)
- Market briefing 재발송: X
- Spike alert 실제 발송: X
- Telegram API 직접 호출: X (기존 telegram_send · FIX 이후 sender 계층만 사용)
- 별도 발송 스크립트 작성: X
- 메시지 본문 수동 변경: X
- 중복 키 변경: X
- sent registry 삭제·수정: X
- PARAM · scheduler · DB schema 변경: X
- Holdings 산식 또는 메시지 문구 개선: X (sender 계층만 수정)
- 자동 재시도: X
- 신규 API · UI · source 추가: X

## 16. 최종 상태

```
status = DONE
completion_judgment = PASS
next_step_gate = TELEGRAM_SPIKE_ALERT_CONDITIONAL_SEND_V1
```

다음 STEP 후보 (설계자 지시 대기): `Telegram Spike Alert Conditional Send v1`.

## 17. 사후 정책 갱신 (2026-07-19, Spike STEP §7)

이후 Telegram Spike Alert Conditional Send v1 (2026-07-19) 지시문 §7 에서 **사용자 승인 게이트 제거** 확정. Market · Holdings · Spike PUSH 는 매 발송 전 사용자 승인을 요구하지 않으며, 사용자 개입은 매수 · 매도 · 비중 변경 · 종목 교체 · 주문 실행 판단에만 남음. 본 STEP 의 사용자 승인·수신 확인 실측 (2026-07-18 16:32 KST) 및 Phase C 재확인 dry-run 절차 는 최초 발송 경로 검증 당시의 **일회성 실측 절차** 로 기록. 향후 운영 계약에서 `USER_SEND_APPROVAL_REQUIRED` · `USER_RECEIPT_CONFIRMATION_REQUIRED` · `PRE_SEND_DRY_RUN_CONFIRMATION_REQUIRED` 게이트 없음. 단, sender 분할 · partial_delivery 계약 (§6.1) · no-signal 미발송 계약 (Spike §6-b) 은 유지.
