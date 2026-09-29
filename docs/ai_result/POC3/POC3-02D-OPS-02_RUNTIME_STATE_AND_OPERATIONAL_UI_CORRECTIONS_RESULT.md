# POC3-02D-OPS-02 개발 결과서 — RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS

작성일: 2026-09-28 · 갱신: 2026-09-29(검증자 r1 정정 · 배포 확인) · 작성자: 개발자(VSCode Claude) · 수신: 설계자 → 검증자

```text
STEP_ID                   = POC3-02D-OPS-02
STEP_NAME                 = 장중 전달 상태·운영 UI 정합성 보완
PREDECESSOR / SUCCESSOR   = POC3-02D-OPS-01 / POC5-01A
PLAN                      = CONFIRMED (설계자 판정 2026-09-28 · Q1~Q6)
USER_UI_CONTRACT_APPROVED = YES (2026-09-28 · 사용자가 3-4 화면 초안(목업) 승인 · 문구는 설계자 규칙)
IMPLEMENTED_UI_CHECK      = PASSED (2026-09-28 21:41 KST 무렵 · 사용자 회신 '화면에 둘다 잘 보입니다' — 「오늘의 투자 점검」 · 「요즘 잘 오르는 ETF」 시장 배경 · 브라우저 새로고침 뒤)
IMPLEMENTATION            = 3-1 커밋 · push 완료(b5b15509) · 3-2 · 3-3 · 3-4 DONE (커밋 eff609a0 · OCI 반영 2026-09-29)
RED_ON_BASE_CODE          = 3-2 새 테스트 49건 중 29건 실패(기준 1489896d) · 3-4 백엔드 새 테스트 수집 실패(함수 없음 — `kospi_display_state` · `with_kospi_display` import 실패) · §1-3
SABOTAGE                  = 3-2 리뷰 무력화 14종 + 추가 2종 · 3-4 백엔드 5종 · 프론트 5종(M1 포함) — 결함 모양 되돌림은 전부 테스트가 잡음(`out.intraday` 앞 대입만 되돌리는 1종은 동작이 같아 0건 · §6)
BACKEND_FULL_REGRESSION   = 2,430 passed / 0 failed / 0 errors (exit 0 · 362s · 백엔드 코드 수정을 모두 마친 뒤 실행 · 그 뒤 바뀐 것은 프론트 M1 · 문서뿐 — 백엔드 변경 0 이라 재실행하지 않음)
FRONTEND                  = vitest 22파일 · 261건 통과 · tsc 0 · eslint 0 (build 안 함 · M1 반영 뒤 재실행)
BLACK / FLAKE8 / COMPILE  = 변경 · 신규 Python 21파일 전부 통과
PC_LIVE_STATE             = PC `state/` · `logs/`(`state/ml/research` 제외) 224파일 sha256 전체 회귀 전후 동일(운영 DB `market_data.sqlite` · `runtime_state.sqlite` · `decision_evidence.sqlite` 포함 · 회귀 중 PC 백엔드 GET 1회 포함)
PC_PUSH_AUTOSEND_*        = 4줄 모두 false
OCI / TELEGRAM            = 이 단계 구현 · 검증 중 OCI 접속 0 · OCI 쓰기 0 · 실발송 0 (전송기 · 시세 · 상태 경로 전부 대역 · tmp). §1-5 의 OCI 07:20 값은 OPS-01 운영 확인(2026-09-28 아침) 때 읽은 기록. 2026-09-28 밤 이 단계 밖의 데이터 최신성 조사로 OCI 읽기 전용 접속 1회(쓰기 0)
KS10_TRIGGER              = 0 (러너 646줄 · 변경 0 · §8)
DESIGNER_RESULT_DECISION  = PASS (설계자 통합 판정 2026-09-29 · 원문은 `docs/ai_design/POC3/POC3-02D-OPS-03_OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY_DESIGN_V1.md`) — 앞선 PASS_WITH_MANDATORY_AMENDMENT(2026-09-28 · CORE PASS · RESULT 판정 Q1~Q3(구파일 다음 정상 저장 · 회복 → 미전달 Y → X · KOSPI 최신성) APPROVED · 필수 보완 M1 · M2 반영 · 원문은 설계서 끝)
VERIFIER                  = VERIFIED (r2 · 2026-09-29 · A-1~A-4 · B-1~B-6 통과 · 위험 NONE · 범위 폭주 NONE) — r1 REJECTED(A-2 결과서의 화면 확인 표기가 완료 · 대기로 동시에 적힘) 정정 뒤
COMMIT_PUSH_OCI           = 커밋 eff609a0 · push 2026-09-29 · OCI pull 2026-09-29 밤(사용자) · 재기동 불필요
DEPLOYMENT                = CONFIRMED (2026-09-29 20:4x · OCI 읽기 전용 5항목 — HEAD eff609a0 · 추적 파일 변경 0 · 배포본에 `last_delivered_state` 계약 · cron 12줄 · flag 불변 · KOSPI 상태 계약은 OCI 공용 lag 함수 + PC API 응답으로 확인)
RUNTIME_FIELD_OBSERVED    = PENDING_FIRST_NATURAL_SEND (pull 이 장 마감 뒤라 새 코드 첫 장중 실행은 2026-09-30 09:30 · 인계 `docs/handoff/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_HANDOFF_2026-09-29.md`)
```

입력 문서

- 설계서: `docs/ai_design/POC3/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_DESIGN_V1.md` (지시 원문 · Q1~Q6 판정 원문 · 3-4 문구 확정 원문)
- PLAN: `docs/ai_plan/POC3/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_PLAN_V1.md`
- 작업 기준 코드: `1489896d`(origin/main · OCI 와 같은 코드 — `1489896d` 는 문서만).

---

## 0. 한눈에

| 항목 | 결함(사실 성격) | 바뀐 것 | 기준 코드에서의 재현(RED) |
|---|---|---|---|
| 3-1 OCI 상세 링크 | 「개발·실험용」으로 감(실제 발생) | 「OCI 운영·적용」으로 · 문구 = 도착 화면 이름 · 라우팅 관통 테스트 | 커밋 `b5b15509`(사용자 지시 화면 합침과 함께 · 사용자 실화면 확인) |
| 3-2 전달 상태 | 결함 1: 전달 못 한 상태 변화가 관측 저장으로 '이미 보낸 상태' → 억제(잠재 · tmp 재현) · 결함 2: 조립 뒤 예외로 구 본문만 나가도 장중 신호가 발송 완료(잠재 · tmp 재현) | 마지막 성공 전달 상태 `last_delivered_state` 로 억제 비교 · `out.intraday` 는 본문 대체 분기에서만 · 구파일 전환 · 회복 기록 보존 | 29/49 실패 — 잘림 · 전송 실패 · 부분 전송 · 조립 뒤 예외 · Q3 · 회복 뒤 재진입 |
| 3-3 낡은 역검증 | ops02b2 ⑦ 이 폐지된 no_change 억제를 요구(`!!` · exit 1) · 목업 ⑦ 제목 모순(실제 발생) | ⑦-a · ⑦-b 현재 계약 역검증 · 목업 ⑦ 제목 · 현재형 옛 문구 · 과거 기록 적용 기간 | 기준 코드: ⑦ `!!` · exit 1 → 이제 11건 OK · exit 0 |
| 3-4 KOSPI 표시 | stale 을 '자료 없음' · 'N/A — 수집되지 않았습니다'(틀린 사유) + 영문 경고(실제 발생 · PC 화면) | 기존 응답 선택 필드 3개 · 두 화면 공용 생성기 · 확정 문구 | 새 테스트 수집 실패(함수 없음) · 무력화 10종(백엔드 5 · 프론트 5 · M1 포함) |

---

## 1. 처리한 요구사항

### 1-1. 설계자 지시 항목별

| 항목 | 판정 | 비고 |
|---|---|---|
| 3-1 OCI 상세 링크 | DONE | `b5b15509` 에 커밋 · push 됨(2026-09-27 · 사용자 지시 「OCI 운영·적용」 합침과 함께). 도착지 `approval` · 문구 'OCI 운영·적용에서 상세 보기 →' · `MainPanel.test.tsx` 관통 |
| 3-2 계약 1~10 · Q1~Q3 | DONE | §1-2 대조표 |
| 3-2 최소 재현 7항목 | DONE | 잘림 · `telegram_send_error` · `partial_delivery`(가짜 · 실제형 청크) · diagnostics 예외 · tally 분류 예외 · 다음 틱 재후보 · 성공 뒤 억제 — 전부 실제 `run()` 관통 |
| 3-3 역검증 · 목업 · 문구 | DONE | §1-6 |
| 3-4 5상태 구분 + KOSPI_AS_OF · TRADING_DAY_LAG · STATUS · REASON | DONE | §1-5. REASON 은 기술 토큰이 아니라 확정 사용자 문장(설계자 3-4 규칙) |
| STEP 5 검증 1~10 | DONE | §1-7 |
| 결과서 5분리 보고 | DONE | §1-4 요약 · 부록 A 전문 |
| 설계자 RESULT 필수 보완 M1 — `수집 결과 없음` 사유 분리 | DONE | 같은 배지 · 기준일 없음 → '저장된 KOSPI 자료가 없습니다.' · 기준일 있음(수익률 없음) → 'KOSPI 수익률을 계산할 자료가 충분하지 않습니다.' · 새 상태 · API 필드 0 · 프론트만(§1-5) |
| 설계자 RESULT 필수 보완 M2 — 화면 확인 표현 | DONE | 머리를 `USER_UI_CONTRACT_APPROVED`(초안 승인) · `IMPLEMENTED_UI_CHECK`(구현 화면 확인) 두 줄로 나눔 — 구현 화면은 사용자 확인(2026-09-28) 뒤 `PASSED` 로 기록했다. 설계서 · PLAN · STATE_LATEST 의 같은 표현도 '사용자 초안(목업) 승인' 으로 정정 |

### 1-2. 3-2 계약 대조 (코드 · 테스트)

코드 위치는 `app/runtime_evidence/sector_signal_state.py`(sss) · `holdings_risk_flow.py`(hrf). 테스트는 `tests/test_poc3_02d_ops02_delivery_state.py`.

| 계약 | 코드 | 테스트 |
|---|---|---|
| 1 관측/전달 분리 | entry = 관측 `state` · `continuous` + 전달 `last_delivered_state` · `last_sent_at` · 파일 `sent_today` | 모든 run() 시나리오가 둘을 따로 단언 |
| 2 전달 상태 기준 판정 | `compute_sector_changes` 가 `last_delivered_state(prev)` 와 비교 | `test_unit_suppression_table`(12행) |
| 3 관측이 전달을 전진시키지 않음 | 관측 경로(`_apply_observation` · `mark_absent_entries`)는 전달 필드를 전진시키지 않는다 | `test_unit_observation_paths_preserve_delivered_state` · `test_unit_mark_absent_entries_copies_delivered_fields` |
| 4 잘린 신호 → 다음 틱 후보 | 전달 필드는 `merge_sector_entries` 의 `sent`(본문에 실린 `sent_signals`)에서만 | `test_run_section_cap_cut_changes_are_sent_next_tick` |
| 5 전송 실패 | 전송 성공 경로에서만 저장(기존 경로 유지) | `test_run_undelivered_change_is_sent_next_tick[telegram_send_error]` |
| 6 부분 전송 | 같음 | 같은 테스트 `[partial_delivery]` · `test_run_realistic_chunk_partial_delivery_is_resent` |
| 7 조립 뒤 예외 | hrf: `out.intraday` 를 본문 대체 분기(`out.message_text = intraday.message_text` 바로 뒤)에서만 대입 · except 에서 `out.intraday = None` · `out.intraday_records = None` | `test_run_exception_after_assembly_marks_nothing_delivered[diagnostics · records · tally_classification]` |
| 8 성공 시 실린 것만 | `merge_sector_entries` sent 루프 | `test_unit_last_delivered_state_written_only_for_sent` · run() 마다 `delivered == included` |
| 9 회복 · 지속 유지 · 관측은 억제 근거 아님 | 회복 규칙(`continuous` · cooldown) 유지 · 비교 기준만 전달 상태 · 회복 기록 보존(아래 ②) | 억제표 회복 행 · `test_run_recovery_then_undelivered_y_then_x_*` 2건 |
| 10 상한 · 임계값 불변 | 변경 0 | `test_regression_daily_cap_still_blocks_pending_change` · `…section_cap_three_and_one_message_per_tick` · run() 마다 회차당 전송 ≤ 1 |
| Q1 필드 · 구파일 규칙 · 일괄 변환 금지 | `DELIVERED_STATE_KEY = "last_delivered_state"` · `last_delivered_state(entry)` · `SCHEMA_VERSION` 불변 · 다음 정상 저장 때 필드 추가(아래 ①) | `test_unit_legacy_rules`(6) · `test_unit_schema_version_unchanged_and_round_trip` · 읽기 뒤 파일 byte 불변(리뷰 실측) |
| Q2 조립 뒤 예외 · D\* | 계약 7 과 같음. D\* 는 구 본문 기준 `save_entries` 로 전송 성공 뒤에만 | `…marks_nothing_delivered` · `test_run_exception_after_assembly_with_failed_send_saves_no_d_star`(주입 3 × 실패 2) |
| Q3 X → 미전달 Y → X | 전달 X · 현재 X · 지속 → 억제 · 이후 Y → 후보 | `test_run_q3_x_undelivered_y_then_x_is_suppressed_then_y_sent` |

**리뷰가 찾아 고친 2건**(구현 → 적대 리뷰 2개 → 수정). 둘 다 계약을 지키려고 더한 것이다.

① **구파일 전환 구간** — 필드가 없고 `last_sent_at` 만 있는 entry 에서, 다음 전송 성공 전에 관측 저장(또는 전송 성공 저장의 관측 루프)이 `state` 를 미전달 Y 로 덮으면 Q1 추정 규칙이 Y 를 '전달 상태'로 읽는다. 결함 1 이 장중 배포 당일 한 번 재현됐다(리뷰 run() 실측 · 다음 날은 `date_reset` 으로 entry 가 버려진다). → `_pin_legacy_delivered`: 두 저장 경로가 `state` 를 덮기 **전에** 추정 전달 상태를 **그대로** 필드로 옮긴다. 설계자 Q1 '읽기만으로 일괄 변환하지 말고 **다음 정상 저장 때 필드를 추가**' 를 관측 저장까지 포함한 '정상 저장' 으로 읽었다(설계자 RESULT 판정 승인 2026-09-28). 값은 추정값 그대로라 전달 상태를 전진시키지 않는다(계약 3). 읽기 경로는 여전히 파일을 고치지 않는다.

② **회복 → 미전달 Y → X** — X 전달 → 임계 밖(회복 · `continuous=False`) → Y 관측(미전달)이 `continuous=True` 로 되돌림 → X 재진입이 cooldown 이 지나도 '지속 중' 으로 억제됐다(리뷰 실측). 관측이 억제 근거가 된 경우다(계약 9). → `_apply_observation`: 회복 뒤 **전달 상태와 다른** 상태로 관측되면 `continuous=False` 를 유지한다. 전달 상태와 같은 상태로 재진입하면 예전처럼 `True`(설계 §5 '회복 후 재진입' 규칙 그대로). 관측 상태 = 전달 상태인 모든 경우의 동작은 기준 코드와 같다.

### 1-3. RED · GREEN · 무력화

**RED — 기준 코드 `1489896d`(`git archive` 사본)에 새 테스트 파일만 넣어 실행**

| 대상 | 결과 | 실패 원인(요지) |
|---|---|---|
| 3-2 `test_poc3_02d_ops02_delivery_state.py` 49건 | **29 failed · 20 passed** | 잘림 · 전송 실패 · 부분 전송 · Q3 · diagnostics · tally 주입: 억제됐거나 발송 완료로 기록됨(동작 RED). 새 API(`last_delivered_state` · `DELIVERED_STATE_KEY`) import 실패. 일부(성공 뒤 억제 · records 주입 · 일일 · 구역 상한 회귀 · 회복 뒤 cooldown 경과)는 기준 코드도 동작은 같고 새 필드 단언에서만 실패 |
| 3-4 `test_poc3_02d_ops02_kospi_display.py` | 수집 실패 1 | `with_kospi_display` 없음 |

- `records` 주입은 기준 코드 자신의 저장도 같은 `set(5)` 에서 터져 발송 완료가 기록되지 않는다 — 동작 RED 가 아니다. 동작 RED 는 diagnostics · tally 주입이다.
- 기준 코드에서 통과한 20건: Gate(dry-run · flag-off · duplicate) 1 · 정책 비활성 1 · 억제표 9행 · 부재 표시 복사(`mark_absent_entries`) 1 · 예외+전송 실패 4 · 회복 필드 표 4행(기준 코드와 같은 동작 행).
- **기준 코드와 동작이 달라지는 경우 1건**: X 전달 → 회복 → 미전달 Y → **cooldown 이내** X 재진입. 기준 코드는 관측 Y ≠ X 라 즉시 발송했고, 지금은 전달 상태 X 기준 '회복 후 cooldown 이내 재진입' 이라 억제한다(`test_run_recovery_then_undelivered_y_then_x_within_cooldown_is_suppressed` · §6).

**GREEN** — 작업 트리에서 3-2 49 passed · 3-4 백엔드 29 passed · 프론트 `KospiStatusNote.test.tsx` 18 passed(M1 3건 포함).

**무력화**(수정 코드를 결함 모양으로 되돌려 테스트가 잡는지 · 매번 원복 후 `cmp` 동일 확인)

| 대상 | 무력화 | 실패 수 |
|---|---|---|
| 3-2 | 비교 기준을 관측 `state` 로 되돌림 | 8 (리뷰) |
| 3-2 | 관측 저장이 필드를 새로 씀 / 기존 필드만 덮음 | 8 / 7 (리뷰) |
| 3-2 | 잘린 신호에도 필드를 씀 / `sent_signals` 에 잘린 신호 포함 | 3 / 5 (리뷰) |
| 3-2 | `out.intraday` 앞 대입 재도입 + except 되돌림 제거 | 4 (리뷰 · 앞 대입만은 0 — §6) |
| 3-2 | 구파일 규칙을 '필드 없음 + `last_sent_at` → null' | 4 (리뷰) |
| 3-2 | `SCHEMA_VERSION` v2 | 1 (리뷰) |
| 3-2 | cooldown 무시 · `continuous` 판정 제거 · 관측이 `sent_today` 올림 · except `intraday_records` 되돌림 제거 · 읽을 때 파일 변환 | 2 · 9 · 16 · 3 · 1 (리뷰) |
| 3-2 | 구파일 추정값 옮기기 제거(①) | 2 |
| 3-2 | 회복 기록 보존 제거(②) | 2 |
| 3-4 백엔드 | 화면 lag 를 KODEX200 적재일 축(`freshness.lag_trading_days`)으로 | 3 |
| 3-4 백엔드 | 호출 실패 무시 / 휴장일 무시 / 캘린더 지연 무시(운영 판정만) / 엔드포인트 미연결 | 5 / 2 / 2 / 1 |
| 3-4 프론트 | 오늘 카드 배지 제거 / 영문 경고 필터 제거 / 모든 상태에 지연 표기 / 로딩을 미평가로 | 1 / 1 / 2 / 2 |
| 3-4 프론트 M1 | 기준일 유무로 나눈 사유를 한 문장으로 되돌림 | 2 |

### 1-4. 3-2 시나리오별 5분리 보고 (요약 · 전문은 부록 A)

테스트 rig(tmp 경로 · 대역 전송기)의 틱별 실제 저장 값이다. 가격은 싣지 않는다. X · Y = 같은 ticker 의 두 상태(사업군 `T00009` ENTRY_REVIEW → AVOID_CHASE · 보유 급등 `H00001` U5_7 → U7_10). '전달' = `last_delivered_state@last_sent_at`.

| 시나리오 · 핵심 틱 | OBSERVATION_STATE | DELIVERY_STATE | ACTUALLY_INCLUDED | SUCCESSFULLY_DELIVERED | PENDING_FOR_NEXT_TICK |
|---|---|---|---|---|---|
| 구역 상한 잘림 · t+60(Y 잘림 · 보유 급락 3종목이 「보유종목」 구역을 채움) | T00009=AC · H00001=U7_10 | T00009=ER@t+0 · H00001=U5_7@t+0 · sent_today 2 | D5_7×3 · 사업군 3 | 같음 | T00009=AC · H00001=U7_10 외 잘린 6 |
| 　└ t+120(다음 틱) | 같음 | T00009=AC@t+120 · H00001=U7_10@t+120 · 3 | T00009=AC · H00001=U7_10 | 같음 | 없음 |
| `telegram_send_error` · t+60 | AC · U7_10 | ER@t+0 · U5_7@t+0 · 1 | AC · U7_10 | 없음 | AC · U7_10 |
| 　└ t+120 | 같음 | AC@t+120 · U7_10@t+120 · 2 | AC · U7_10 | 같음 | 없음 |
| `partial_delivery`(가짜) | 위와 같은 모양 | 전진 없음 → 다음 틱 전진 | | | |
| 실제형 청크 부분 전송 · t+60 | AC · U7_10 | ER@t+0 · U5_7@t+0 · D\* 없음 | AC · U7_10 · D5_7×2 | 없음 | 넷 다 |
| 　└ t+120 | 같음 | AC@t+120 · U7_10@t+120 · D\* 2 | 넷 | 넷 | 없음 |
| 성공 뒤 같은 상태 지속 · t+60 · t+300 | AC · U7_10 | AC@t+0 · U7_10@t+0 · 1 | 없음(억제) | 없음 | 없음 |
| Q3 · t+120(X 다시) | ER(연속) | ER@t+0 · U5_7@t+0 · 1 | 없음(억제) | 없음 | 없음 |
| 　└ t+180(Y 다시) | AC | AC@t+180 · U7_10@t+180 · 2 | AC · U7_10 | 같음 | 없음 |
| 조립 뒤 diagnostics 예외 · t+0 | S entries 비어 있음(시드) | 전달 이력 없음 · sent_today 1(시드 그대로) · D\* H00001=D5_7 · 집계 0틱 | 구 본문 D5_7 | D5_7 | H00002=U7_10 · T00009=ER |
| 　└ t+60(주입 없음) | U7_10 · ER | U7_10@t+60 · ER@t+60 · 2 · 집계 1틱 | U7_10 · ER | 같음 | 없음 |
| 조립 뒤 tally 분류 예외 | diagnostics 와 같음 | | | | |
| 조립 뒤 예외 + 전송 실패 · 부분 전송(주입 3 × 2) | S 없음 | D\* 없음 · 집계 0 | 구 본문 D5_7 | 없음 | D5_7 · U7_10 · ER |
| 회복 → 미전달 Y → X · t+120(Y 실패) | AC(끊김 유지) | ER@t+0 · 1 | AC | 없음 | AC |
| 　└ t+300(X · cooldown 경과) | ER(연속) | ER@t+300 · 2 | ER | ER | 없음 |
| 회복 → Y → X(cooldown 이내) · t+90 · t+300 | ER(연속) | ER@t+0 · 1 | 없음(억제) | 없음 | 없음 |

### 1-5. 3-4 KOSPI 화면 상태

**응답** — 기존 `GET /market/topn/latest` 의 `market_context.kospi` 에 선택 필드 3개(설계자 Q4 조건: 신규 엔드포인트 0 · 기존 필드 의미 불변 · 외부 호출 0 · 기존 DB · 캘린더만 · Dashboard 자동 호출 부활 없음 — 「오늘의 투자 점검」 · 「요즘 잘 오르는 ETF」 는 이미 이 API 를 부른다).

| 필드 | 뜻 |
|---|---|
| `display_state` | `ok` · `stale` · `source_failed` · `no_result` · `not_evaluated` · `holiday` (백엔드 판정 · 아래 표) |
| `trading_day_lag` | KOSPI 기준일이 오늘 **직전 거래일**보다 몇 거래일 늦나 — C7 KOSPI 적재 감지와 **같은 함수**(`trading_day_lag.benchmark_lag_trading_days` · 캘린더 축 · 없으면 평일 fallback). KODEX200 적재일 축 lag 가 아니다(Q6) |
| `today_is_trading_day` | 오늘(KST) 거래일 여부 — 거래일 Gate 와 같은 `check_trading_day` |

**판정**(`api_market_topn_service.kospi_display_state` · 위에서부터 처음 맞는 줄 · 운영 판정 `compute_kospi_metrics` 와 `MAX_STALE_TRADING_DAYS=1` 은 그대로)

| 조건 | 상태 | 화면(설계자 확정 문구) |
|---|---|---|
| 화면 요청 중(프론트) | — | 로딩 `확인 중`(배지 아님) |
| 화면 요청 실패 · 응답에 KOSPI 없음(프론트) | `source_failed` | `자료원 확인 실패` · 'KOSPI 원자료를 불러오지 못했습니다.' |
| 저장 KOSPI 없음 · KS11 적재 기록 없음 | `not_evaluated` | `아직 평가되지 않음` · 'KOSPI 최신성 판정이 아직 실행되지 않았습니다.' |
| 저장 KOSPI 없음 · 마지막 적재가 호출 실패 | `source_failed` | `자료원 확인 실패` |
| 저장 KOSPI 없음 · 그 밖 | `no_result` | `수집 결과 없음` · '저장된 KOSPI 자료가 없습니다.' |
| 최신 아님 · 마지막 적재가 호출 실패(`source_stale:` 아님) | `source_failed` | `자료원 확인 실패` + `KOSPI 기준일 … · N거래일 지연` |
| 최신 아님(운영 판정 `stale` · 또는 캘린더 lag > 1 · 또는 lag 모름) | `stale` | `기준일 지연` + `KOSPI 기준일 … · N거래일 지연` · 'KOSPI 원자료가 최근 거래일까지 갱신되지 않았습니다.' |
| 최신이지만 수익률 미산출 | `no_result` | `수집 결과 없음` + `KOSPI 기준일 …` · 'KOSPI 수익률을 계산할 자료가 충분하지 않습니다.'(설계자 RESULT M1 — 프론트가 기준일 유무로 나눈다) |
| 최신 · 오늘 휴장 | `holiday` | 중립 `휴장일` + `KOSPI 기준일 …` · '오늘은 국내 증시 휴장일입니다.'(지연 표기 없음) |
| 최신 | `ok` | 배지 · 사유 없음 · 값 + `KOSPI 기준일 …` |

- 휴장일에 다른 상태가 겹치면 그 상태 배지 + 중립 `휴장일` 배지(사유 줄은 그 상태 것).
- N 은 백엔드 값만 쓴다. 모르면(`null`) 지연 부분을 붙이지 않는다. 화면은 KODEX200 축으로 계산하지 않으므로 'KODEX200 거래일 기준' 표기는 쓸 일이 없다.
- 두 화면은 같은 생성기(`frontend/app/components/KospiStatusNote.tsx :: kospiStatusView`)를 쓴다 — 「오늘의 투자 점검」 KOSPI 카드 '코스피 수익률·위치' · 「요즘 잘 오르는 ETF」 시장 배경 카드 '(KS11) KOSPI (보조)'. 테스트가 두 화면의 상태 줄 텍스트가 같음을 단언한다.
- 영문 KOSPI 경고 줄('KOSPI benchmark …')은 시장 배경 카드에서만 숨긴다(사용자 선택 · 응답 `warnings` 불변 · KODEX200 경고는 보임).
- 기술 토큰(`source_stale` · `stale` · `unavailable` · `failed` · `lag`) · KODEX200 축 표기가 어떤 상태 문구에도 없음을 테스트가 단언한다.

**PC 실측**(2026-09-28 저녁 · PC 백엔드가 `--reload` 로 새 코드를 읽음 · `curl` GET 1회 · 읽기만 · 전체 회귀 hash 비교 구간 안): `status=stale` · `as_of_date=2026-09-17` · `display_state=stale` · `trading_day_lag=4` · `today_is_trading_day=true`. 화면에는 `기준일 지연` · 'KOSPI 기준일 2026-09-17 · 4거래일 지연' · 사유 줄이 나온다 — 사용자가 2026-09-28 두 화면에서 확인했다(`IMPLEMENTED_UI_CHECK = PASSED` · §7). 같은 날 OCI 07:20 배치 기록의 `source_stale:as_of=2026-09-17,ref=2026-09-23,lag=4` 와 같은 값이다. PC 의 마지막 KS11 적재 기록(09-22 · C7 이전)은 성공 행이라 판정은 `stale`(호출 실패 아님)이다.

### 1-6. 3-3 낡은 fingerprint 역검증

| 대상 | 결과(2026-09-28 재실행) |
|---|---|
| `scripts/ops02b2/reverse_verify_guards.py` | 11건 OK · '전부 무력화 시 실패 확인: True' · exit 0. ⑦ → ⑦-a(다음 거래일 같은 fingerprint 시장 브리핑은 발송 · 무력화: 옛 no_change 억제 → skip) · ⑦-b(같은 날 재실행은 registry 일 단위 키로 차단 · tmp `runtime_state.sqlite` · 무력화: 분 단위 키 → 08:05 재실행 발송) |
| `scripts/build_market_briefing_mockups.py` | ①~⑥ 출력이 기준 스크립트와 byte 동일 · ⑦ 제목만 '동일 fingerprint · 다음 거래일 (발송)' · 상태 저장 = 예 |
| 보유 · 위험 알림 계약 | `tests/test_poc3_02d_ops02_regular_push_contract.py` 5건 — OPEN 발송 뒤 같은 입력 MIDDAY 발송(`content_unchanged`) · 같은 MIDDAY 재실행 `duplicate_runtime` · CLOSE 막히지 않음 · 위험 알림 둘째 틱 `no_new_or_worsened` |
| 현재형 옛 문구 | 주석 · docstring · 테스트 머리 문구만(동작 · 단언 불변) |
| 과거 기록 | 삭제 · 재생성 없이 적용 기간 주석('2026-09-18 운영분까지 적용 · 2026-09-18 밤 `02C-OPS-01` OCI 반영으로 폐지 · 새 계약 첫 운영일 2026-09-21') |

### 1-7. STEP 5 검증 실측

| # | 항목 | 결과 |
|---|---|---|
| 1 | 관련 계약 테스트 | 3-2 49 · 3-3 5 통과 · 3-4 새 29 를 포함한 C7 · topn · freshness 묶음 94 통과 |
| 2 | 실제 `run()` 관통 | 3-2 run() 시나리오 17개(부록 A) · 3-4 TestClient `GET /market/topn/latest` 2건 |
| 3 | 실패 · 잘림 시나리오 무력화 | §1-3 |
| 4 | 프론트 라우팅 · 상태 표시 | 3-1 `MainPanel.test.tsx`(커밋됨) · 3-4 `KospiStatusNote.test.tsx` 18건(M1 두 경우 · 두 화면 포함) |
| 5 | 백엔드 전체 회귀 | 2,430 passed / 0 failed / 0 errors (exit 0 · 362s · 백엔드 코드 수정을 모두 마친 뒤 실행 · 그 뒤 바뀐 것은 프론트 M1 · 문서뿐 — 백엔드 변경 0 이라 재실행하지 않음) |
| 6 | 프론트 전체 · 타입 · lint | vitest 22파일 261건 · `tsc --noEmit` 0 · `npm run lint` 0(M1 반영 뒤) |
| 7 | black · flake8 | 21파일 통과(+ py_compile) |
| 8 | KS-10 | §8 · 트리거 0 |
| 9 | PC 라이브 상태 · 운영 DB hash | PC `state/` · `logs/`(`state/ml/research` 제외) 224파일 sha256 전체 회귀 전후 동일(운영 DB `market_data.sqlite` · `runtime_state.sqlite` · `decision_evidence.sqlite` 포함 · 회귀 중 PC 백엔드 GET 1회 포함) |
| 10 | OCI 쓰기 · Telegram | OCI 쓰기 0 · 이 단계 구현 · 검증 중 OCI 접속 0(머리 OCI / TELEGRAM 줄 참고) · 실발송 0 · `PUSH_AUTOSEND_*` 4줄 false |

---

## 2. 변경된 파일 목록

**3-2 전달 상태**

- `app/runtime_evidence/sector_signal_state.py`: 수정 — `last_delivered_state` · 구파일 규칙 · `_pin_legacy_delivered` · `_apply_observation` · 억제 비교 · docstring(§15-2 개정 기록)
- `app/runtime_evidence/holdings_risk_flow.py`: 수정 — `out.intraday` 대입 위치 · except 되돌림 · docstring
- `app/runtime_evidence/intraday_alert_flow.py`: 수정 — 주석 · docstring만
- `app/three_push_runtime/runner_evidence.py`: 수정 — 주석 · docstring만
- `tests/test_poc3_02d_ops02_delivery_state.py`: 신규
- `tests/test_poc3_02d_ops01_holdings_risk_flow.py`: 수정 — docstring · 주석만(단언 변경 0)

**3-3 낡은 역검증**

- `scripts/ops02b2/reverse_verify_guards.py`: 수정 — ⑦ → ⑦-a · ⑦-b
- `scripts/build_market_briefing_mockups.py`: 수정 — 목업 ⑦
- `app/market_briefing/flow.py` · `app/market_briefing/__init__.py` · `app/runtime_evidence/holdings_selection_flow.py` · `app/runtime_evidence/holdings_selection_state.py`: 수정 — 주석 · docstring만
- `tests/test_holdings_selection_state.py` · `tests/test_market_briefing_contracts.py`: 수정 — 문구만
- `tests/test_poc3_02d_ops02_regular_push_contract.py`: 신규
- `docs/ai_result/POC3/POC3-OPS-02B-2_MARKET_BRIEFING_MOCKUPS.md` · `POC3-OPS-02B-2_MARKET_BRIEFING_MESSAGE_RESULT.md` · `POC3-OPS-01A_HOLDINGS_PUSH_SELECTION_AND_SUPPRESSION_RESULT.md`: 수정 — 적용 기간 주석

**3-4 KOSPI 화면 상태**

- `app/trading_day_lag.py`: 수정 — `benchmark_lag_trading_days`(C7 본문 이동)
- `app/market_benchmark_store.py`: 수정 — `_source_lag` 삭제 → 공용 함수 호출(동작 불변)
- `app/api_market_topn_service.py`: 수정 — `kospi_display_state` · `with_kospi_display`
- `app/api_market_topn.py`: 수정 — 응답 조립 때 `with_kospi_display`
- `app/api_market_topn_models.py`: 수정 — `MarketContextKospi` 선택 필드 3개
- `tests/test_poc3_02d_ops02_kospi_display.py`: 신규
- `frontend/app/components/KospiStatusNote.tsx` · `KospiStatusNote.test.tsx`: 신규
- `frontend/app/components/today/KospiHeadline.tsx` · `frontend/app/components/MarketContextCard.tsx`: 수정
- `frontend/lib/api/marketEvidence.ts`: 수정 — 타입
- `frontend/app/globals.css`: 수정 — `.kospi-badge` · `.kospi-status*`

**문서**

- `docs/ai_design/POC3/POC3-02D-OPS-02_…_DESIGN_V1.md` · `docs/ai_plan/POC3/POC3-02D-OPS-02_…_PLAN_V1.md`: 신규(staged)
- `docs/ai_result/POC3/POC3-02D-OPS-02_…_RESULT.md`(이 문서): 신규
- `docs/PROGRAM_TRUTH.md`: 수정 — 머리글 · §5.2 · §6.1 · §7.2 · §8 · §13-4 · 장중 급등락 절 · 부록 A
- `docs/STATE_LATEST.md`: 수정 — 머리 · '다음' · 단계 표 `02D-OPS-02` 행

(3-1 파일은 `b5b15509` 에 이미 커밋됐다.)

## 3. 신규 추가된 의존성

없음

## 4. 지시문 외 변경

- **C7 lag 계산 이동**: `market_benchmark_store._source_lag` 본문을 `trading_day_lag.benchmark_lag_trading_days` 로 그대로 옮기고 store 는 그 함수를 부른다. 이유: 설계자 Q6 '백엔드가 C7 공용 거래일 계산으로 산출한 lag' — 화면이 **같은 함수**를 쓰게 하려고(복제하면 둘이 갈릴 수 있다). C7 테스트 전부 통과 · 같은 날 · 같은 자료로 적재 기록 lag 와 화면 lag 가 같음을 테스트로 고정.
- **3-2 리뷰 수정 2건**(§1-2 ①②): PLAN 안 A 에 없던 구현. 계약 3 · 9 와 Q1 문장을 지키려고 더했다.
- **옛 주석 정정**: `holdings_risk_flow` 모듈 docstring · `intraday_alert_flow.py` 관측 목록 주석 · `runner_evidence` 주석의 '관측 상태는 조립 단계가 매 회차 저장' — 2026-09 D3 이후 틀린 문장(실제로는 Gate 통과 회차에 `apply_intraday_records()` 가 쓴다).
- **프론트 타입**: `MarketContextKospi.status` 에 백엔드가 이미 주던 `"stale"` 를 더했다.
- **모델 주석**: `MarketContextKospi.status` 주석 `ok / unavailable` → `ok / stale / unavailable`.

## 5. 알려진 한계 / 미완성

- **OCI 반영** — 2026-09-29 밤 사용자 pull 로 3-2 · 3-3 이 OCI 에 반영됐다(그날 장중 실행은 pull 전 옛 코드). 새 코드 첫 장중 실행은 2026-09-30 이고, `last_delivered_state` 실측은 첫 자연 발송 뒤다. 3-4 는 PC 화면이다 — PC 백엔드 응답은 새 필드를 실측으로 확인했고(§1-5), 화면(프론트 dev 서버)도 사용자가 확인했다(2026-09-28 · `IMPLEMENTED_UI_CHECK = PASSED`).
- **조립 뒤 예외 회차의 실행 기록**: 장중 진단값(`intraday_sector_sent_count` 등)이 run record 에 남는다. `intraday_error` 가 함께 남고 이 값을 읽는 코드는 없다(grep 0).
- **발송이 늘 수 있다**: 전달 못 한 상태 변화가 다음 틱에 다시 나가므로 일일 상한 4건에 더 일찍 닿을 수 있다(상한 · cooldown · 임계값 불변).
- **3-4 lag 축**: C7 과 같이 오늘 당일을 축에서 뺀다. 거래일 저녁에 당일 자료가 없어도 직전 거래일 자료는 지연 0 이다.
- **3-4 PC 사유 세분화 없음**: PC 에는 OCI 07:20 배치의 KOSPI 결과가 오지 않는다. PC 화면은 PC DB(PC 수동 갱신 KS11 기록)만 본다 — 설계 범위(외부 호출 · 신규 경로 0)대로다.
- **응답은 성공했는데 `market_context` 자체가 없는 경우**(시장 DB 에 ETF 가격이 없을 때 `compute_topn` 이 빈 결과를 줌): 「오늘의 투자 점검」은 `자료원 확인 실패` · 'KOSPI 원자료를 불러오지 못했습니다.' 를 보이고, 「요즘 잘 오르는 ETF」 시장 배경 카드는 기존대로 카드 전체 '시장 데이터가 없습니다…' 를 보인다(두 화면이 다름 · 리뷰 실측). 운영 PC DB 에는 가격이 있어 도달하지 않는다. 설계자 승인 문구는 '화면 요청 실패' 까지라 이 경우는 §6 에 따로 알린다.
- **이 변경 전 서버 응답**(선택 필드 없음)을 받으면 프론트는 기존 `status` 로만 상태를 고르고 지연 수를 붙이지 않는다.

## 6. 다음 검증자(Codex)에게 알릴 점

- **기준 코드와 동작이 달라지는 1건**(의도): X 전달 → 회복 → 미전달 Y → cooldown **이내** X 재진입. 기준 코드는 발송(관측 Y ≠ X), 지금은 억제(전달 상태 X 기준 회복 후 cooldown 이내 재진입 · 설계 §5). cooldown 이 지나면 발송된다. 설계자 RESULT 판정에서 승인됐다(2026-09-28 · 'cooldown 이내 X 재진입 = 억제').
- **Q1 '다음 정상 저장' 해석**: 관측 저장도 정상 저장으로 보고 구파일 추정값을 옮긴다(§1-2 ① · 설계자 RESULT 판정 승인). 전송 성공 저장만으로 읽으면 장중 배포 당일 결함 1 이 재현된다.
- **`out.intraday = None`(except)**: 대입이 대체 분기 끝이라 그 뒤 예외가 날 문장이 없어 방어 코드다. 앞 대입만 되돌리면 테스트 0건 실패(동작이 같아진다) · except 되돌림까지 없애면 4건 실패.
- **`RiskAssembly.intraday` 가 `None` 인 회차가 늘었다**(정책 비활성 · 일일 상한 · 신호 없음 · 예외). 유일한 소비처 `_save_intraday_state_after_send` 는 `None` · 빈 본문이면 바로 반환한다.
- **3-4 판정 선택**(설계자 RESULT 판정 승인): '최신' = 운영 판정 `stale` 아님 **그리고** 캘린더 lag ≤ 1. 최신이면 그 뒤 호출 실패는 보지 않는다. 화면 요청 실패도 `자료원 확인 실패`(사용자가 승인한 초안에 명시).
- **승인 범위 밖 1건(동작 변경 없음 · 공개)**: 응답은 성공했는데 `market_context` 가 없는 경우도 「오늘의 투자 점검」은 `자료원 확인 실패` 로 보인다(§1-5 표 '응답에 KOSPI 없음' · §5). 설계자는 '화면 요청 실패' 를 승인했다. 이 경우를 `아직 평가되지 않음` 등으로 바꿀지는 판단 대상이라 임의로 바꾸지 않았다.
- **M1 구분 기준**: `no_result` 에서 기준일(`as_of_date`)이 있으면 수익률 값은 늘 없다 — 백엔드는 운영 판정이 `ok` 일 때만 값을 주고, 기준일이 있는 `no_result` 는 그 판정이 `ok` 가 아닌 경우다. 그래서 기준일 유무만으로 두 사유를 나눈다(새 필드 0).
- **3-4 `with_kospi_display`** 는 읽기 실패 시 필드를 더하지 않는다(응답은 그대로 · 테스트). 입력 dict 를 바꾸지 않는다(테스트).
- **테스트 건수**: 3-2 파일 49건 = 1차 구현 41 + 리뷰 수정 8.

## 7. 사용자 확인이 필요한 항목

- **3-4 구현 화면 — 확인 완료**(`IMPLEMENTED_UI_CHECK = PASSED` · 2026-09-28 21:41 KST 무렵 · 설계자 판정 §4 항목): 브라우저 새로고침 뒤 ① 「오늘의 투자 점검」 '코스피 수익률·위치' 옆 `기준일 지연` 배지 · 'KOSPI 기준일 2026-09-17 · 4거래일 지연'(날짜가 지나면 늘어난다) · 'KOSPI 원자료가 최근 거래일까지 갱신되지 않았습니다.' ② 「요즘 잘 오르는 ETF」 → 시장 배경 '(KS11) KOSPI (보조)' 에 같은 상태 · 기준일 · 사유 · 영문 KOSPI 경고 줄 없음. 사용자 회신 '화면에 둘다 잘 보입니다'. 설계자 §4 의 'KODEX200 관련 다른 경고는 그대로' 는 지금 PC 응답에 KODEX200 경고가 없어(2026-09-28 실측 `warnings` = KOSPI 1건) 화면으로는 볼 수 없다 — `KospiStatusNote.test.tsx` 가 KODEX200 경고는 보이고 KOSPI 경고만 숨는 것을 단언한다. 남은 사용자 확인 항목은 아래 두 건이다.
- **장중 알림 동작 변화**(3-2 · OCI pull 뒤부터): 전달 못 한 변화가 다음 틱에 다시 나가 알림이 조금 늘 수 있다. 회복 → 미전달 → cooldown 이내 재진입은 보내지 않는다(§6 첫 항목).
- **OPS-01 C3 확인(설계자 요청 · 선택 · 검증자 전달을 막지 않음)**: 2026-09-28 「장중 급등락」 Telegram 한 건의 '기준' 다음 줄이 `현재가 2026-09-28 HH:MM` 인지(미회신). 그렇다면 C3 운영 확인 완료로 기록한다.

---

## 8. KS-10 (`wc -l` 실측 2026-09-28 · HEAD → 작업 트리)

| 파일 | 줄 | 비고 |
|---|---|---|
| `scripts/run_three_push_runtime_oci.py` | 646 → 646 | 변경 0(상한 648) |
| `app/runtime_evidence/sector_signal_state.py` | 325 → 427 | 백엔드 근접선 600 미만 |
| `app/runtime_evidence/holdings_risk_flow.py` | 491 → 508 | |
| `app/runtime_evidence/intraday_alert_flow.py` | 468 → 470 | |
| `app/three_push_runtime/runner_evidence.py` | 267 → 275 | |
| `app/api_market_topn_service.py` | 326 → 439 | |
| `app/api_market_topn.py` · `api_market_topn_models.py` | 184 → 188 · 294 → 300 | |
| `app/trading_day_lag.py` · `market_benchmark_store.py` | 94 → 125 · 298 → 273 | |
| `app/api.py` | 641 → 641 | 건드리지 않음 |
| `tests/test_poc3_02d_ops02_delivery_state.py` | 신규 987 | 테스트 근접선 1,450 미만 · 이 단계 전용 |
| `tests/test_poc3_02d_ops02_kospi_display.py` · `…regular_push_contract.py` | 신규 376 · 221 | |
| `tests/test_intraday_alert_flow_through.py` · `test_market_topn_api.py` | 1298 · 788 → 그대로 | 추가 0 |
| `tests/test_poc3_02d_ops01_holdings_risk_flow.py` | 944 → 947 | 문구만 |
| `frontend/app/components/KospiStatusNote.tsx` · `.test.tsx` | 신규 153 · 307 | M1 반영 뒤 |
| `today/KospiHeadline.tsx` · `MarketContextCard.tsx` | 139 → 144 · 131 → 142 | |
| `MarketDiscoveryView.tsx` · `TodayInvestmentCheckView.tsx` | 825 · 141 → 그대로 | 건드리지 않음 |

## 9. git 상태 (커밋 직전 실측 · 2026-09-29)

`git status --short --untracked-files=all` — 변경 · 신규 35파일 전부 staged(우측 컬럼 공백). 미추적 1건은 사용자 소유 `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`(건드리지 않음 · 올리지 않음). 이 목록이 검증자 `VERIFIED`(r2) 대상이고 그대로 커밋한다(커밋 SHA 는 `git log` 로 확인 — 이 문서에 적으면 자기참조라 적지 않는다).

```text
M  app/api_market_topn.py
M  app/api_market_topn_models.py
M  app/api_market_topn_service.py
M  app/market_benchmark_store.py
M  app/market_briefing/__init__.py
M  app/market_briefing/flow.py
M  app/runtime_evidence/holdings_risk_flow.py
M  app/runtime_evidence/holdings_selection_flow.py
M  app/runtime_evidence/holdings_selection_state.py
M  app/runtime_evidence/intraday_alert_flow.py
M  app/runtime_evidence/sector_signal_state.py
M  app/three_push_runtime/runner_evidence.py
M  app/trading_day_lag.py
M  docs/PROGRAM_TRUTH.md
M  docs/STATE_LATEST.md
A  docs/ai_design/POC3/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_DESIGN_V1.md
A  docs/ai_plan/POC3/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_PLAN_V1.md
A  docs/ai_result/POC3/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_RESULT.md
M  docs/ai_result/POC3/POC3-OPS-01A_HOLDINGS_PUSH_SELECTION_AND_SUPPRESSION_RESULT.md
M  docs/ai_result/POC3/POC3-OPS-02B-2_MARKET_BRIEFING_MESSAGE_RESULT.md
M  docs/ai_result/POC3/POC3-OPS-02B-2_MARKET_BRIEFING_MOCKUPS.md
A  frontend/app/components/KospiStatusNote.test.tsx
A  frontend/app/components/KospiStatusNote.tsx
M  frontend/app/components/MarketContextCard.tsx
M  frontend/app/components/today/KospiHeadline.tsx
M  frontend/app/globals.css
M  frontend/lib/api/marketEvidence.ts
M  scripts/build_market_briefing_mockups.py
M  scripts/ops02b2/reverse_verify_guards.py
M  tests/test_holdings_selection_state.py
M  tests/test_market_briefing_contracts.py
M  tests/test_poc3_02d_ops01_holdings_risk_flow.py
A  tests/test_poc3_02d_ops02_delivery_state.py
A  tests/test_poc3_02d_ops02_kospi_display.py
A  tests/test_poc3_02d_ops02_regular_push_contract.py
?? docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md
```

---

## 부록 A. 3-2 시나리오별 5분리 보고 전문

테스트 rig 그대로 돌려 틱 기록을 모은 출력이다(저장소 밖 pytest 플러그인 · `tests/conftest.py` · `_live_guard` 적용 · 17 passed). '(연속)' · '(끊김)' 은 `continuous`. 'D\* worst' 는 `holdings_risk_state` 의 `worst_state`. '집계 틱' 은 `intraday_checkup_tally` 틱 수.

```text
POC3-02D-OPS-02 §3-2 — 시나리오별 5분리 보고 (tmp 경로 · 대역 전송기 · 실발송 0)
pytest exitstatus=0 · 시나리오 17개

== test_run_section_cap_cut_changes_are_sent_next_tick · 구역 상한 잘림
  [t+0 X 전달] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U5_7(연속) · T00009=ENTRY_REVIEW(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=1
    ACTUALLY_INCLUDED_SIGNALS      H00001=U5_7 · T00009=ENTRY_REVIEW
    SUCCESSFULLY_DELIVERED_SIGNALS H00001=U5_7 · T00009=ENTRY_REVIEW
    PENDING_FOR_NEXT_TICK          (없음)
  [t+60 Y 잘림] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U7_10(연속) · T00000=AVOID_CHASE(연속) · T00001=AVOID_CHASE(연속) · T00002=AVOID_CHASE(연속) · T00003=AVOID_CHASE(연속) · T00004=AVOID_CHASE(연속) · T00005=AVOID_CHASE(연속) · T00006=AVOID_CHASE(연속) · T00007=AVOID_CHASE(연속) · T00008=AVOID_CHASE(연속) · T00009=AVOID_CHASE(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00000=AVOID_CHASE@t+60 · T00001=AVOID_CHASE@t+60 · T00002=AVOID_CHASE@t+60 · T00009=ENTRY_REVIEW@t+0 · sent_today=2 · D* worst: H00002=D5_7 · H00003=D5_7 · H00004=D5_7 · 집계 틱=2
    ACTUALLY_INCLUDED_SIGNALS      H00002=D5_7 · H00003=D5_7 · H00004=D5_7 · T00000=AVOID_CHASE · T00001=AVOID_CHASE · T00002=AVOID_CHASE
    SUCCESSFULLY_DELIVERED_SIGNALS H00002=D5_7 · H00003=D5_7 · H00004=D5_7 · T00000=AVOID_CHASE · T00001=AVOID_CHASE · T00002=AVOID_CHASE
    PENDING_FOR_NEXT_TICK          H00001=U7_10 · T00003=AVOID_CHASE · T00004=AVOID_CHASE · T00005=AVOID_CHASE · T00006=AVOID_CHASE · T00007=AVOID_CHASE · T00008=AVOID_CHASE · T00009=AVOID_CHASE
  [t+120 Y 지속] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U7_10(연속) · T00000=AVOID_CHASE(끊김) · T00001=AVOID_CHASE(끊김) · T00002=AVOID_CHASE(끊김) · T00003=AVOID_CHASE(끊김) · T00004=AVOID_CHASE(끊김) · T00005=AVOID_CHASE(끊김) · T00006=AVOID_CHASE(끊김) · T00007=AVOID_CHASE(끊김) · T00008=AVOID_CHASE(끊김) · T00009=AVOID_CHASE(연속)
    DELIVERY_STATE                 S: H00001=U7_10@t+120 · T00000=AVOID_CHASE@t+60 · T00001=AVOID_CHASE@t+60 · T00002=AVOID_CHASE@t+60 · T00009=AVOID_CHASE@t+120 · sent_today=3 · D* worst: H00002=D5_7 · H00003=D5_7 · H00004=D5_7 · 집계 틱=3
    ACTUALLY_INCLUDED_SIGNALS      H00001=U7_10 · T00009=AVOID_CHASE
    SUCCESSFULLY_DELIVERED_SIGNALS H00001=U7_10 · T00009=AVOID_CHASE
    PENDING_FOR_NEXT_TICK          (없음)
  [t+180 Y 지속(전달 뒤)] status=skipped reason=no_new_or_worsened partial=False 본문=(전송 없음)
    OBSERVATION_STATE              H00001=U7_10(연속) · T00000=AVOID_CHASE(끊김) · T00001=AVOID_CHASE(끊김) · T00002=AVOID_CHASE(끊김) · T00003=AVOID_CHASE(끊김) · T00004=AVOID_CHASE(끊김) · T00005=AVOID_CHASE(끊김) · T00006=AVOID_CHASE(끊김) · T00007=AVOID_CHASE(끊김) · T00008=AVOID_CHASE(끊김) · T00009=AVOID_CHASE(연속)
    DELIVERY_STATE                 S: H00001=U7_10@t+120 · T00000=AVOID_CHASE@t+60 · T00001=AVOID_CHASE@t+60 · T00002=AVOID_CHASE@t+60 · T00009=AVOID_CHASE@t+120 · sent_today=3 · D* worst: H00002=D5_7 · H00003=D5_7 · H00004=D5_7 · 집계 틱=4
    ACTUALLY_INCLUDED_SIGNALS      (없음)
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          (없음)

== test_run_undelivered_change_is_sent_next_tick[telegram_send_error] · telegram_send_error
  [t+0 X 전달] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U5_7(연속) · T00009=ENTRY_REVIEW(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=1
    ACTUALLY_INCLUDED_SIGNALS      H00001=U5_7 · T00009=ENTRY_REVIEW
    SUCCESSFULLY_DELIVERED_SIGNALS H00001=U5_7 · T00009=ENTRY_REVIEW
    PENDING_FOR_NEXT_TICK          (없음)
  [t+60 Y telegram_send_error] status=failed reason=telegram_send_error partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U7_10(연속) · T00009=AVOID_CHASE(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=2
    ACTUALLY_INCLUDED_SIGNALS      H00001=U7_10 · T00009=AVOID_CHASE
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          H00001=U7_10 · T00009=AVOID_CHASE
  [t+120 Y 지속 · 전송 정상] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U7_10(연속) · T00009=AVOID_CHASE(연속)
    DELIVERY_STATE                 S: H00001=U7_10@t+120 · T00009=AVOID_CHASE@t+120 · sent_today=2 · D* worst: (없음) · 집계 틱=3
    ACTUALLY_INCLUDED_SIGNALS      H00001=U7_10 · T00009=AVOID_CHASE
    SUCCESSFULLY_DELIVERED_SIGNALS H00001=U7_10 · T00009=AVOID_CHASE
    PENDING_FOR_NEXT_TICK          (없음)
  [t+180 Y 지속(전달 뒤)] status=skipped reason=no_new_or_worsened partial=False 본문=(전송 없음)
    OBSERVATION_STATE              H00001=U7_10(연속) · T00009=AVOID_CHASE(연속)
    DELIVERY_STATE                 S: H00001=U7_10@t+120 · T00009=AVOID_CHASE@t+120 · sent_today=2 · D* worst: (없음) · 집계 틱=4
    ACTUALLY_INCLUDED_SIGNALS      (없음)
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          (없음)

== test_run_undelivered_change_is_sent_next_tick[partial_delivery] · partial_delivery
  [t+0 X 전달] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U5_7(연속) · T00009=ENTRY_REVIEW(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=1
    ACTUALLY_INCLUDED_SIGNALS      H00001=U5_7 · T00009=ENTRY_REVIEW
    SUCCESSFULLY_DELIVERED_SIGNALS H00001=U5_7 · T00009=ENTRY_REVIEW
    PENDING_FOR_NEXT_TICK          (없음)
  [t+60 Y partial_delivery] status=sent reason=- partial=True 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U7_10(연속) · T00009=AVOID_CHASE(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=2
    ACTUALLY_INCLUDED_SIGNALS      H00001=U7_10 · T00009=AVOID_CHASE
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          H00001=U7_10 · T00009=AVOID_CHASE
  [t+120 Y 지속 · 전송 정상] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U7_10(연속) · T00009=AVOID_CHASE(연속)
    DELIVERY_STATE                 S: H00001=U7_10@t+120 · T00009=AVOID_CHASE@t+120 · sent_today=2 · D* worst: (없음) · 집계 틱=3
    ACTUALLY_INCLUDED_SIGNALS      H00001=U7_10 · T00009=AVOID_CHASE
    SUCCESSFULLY_DELIVERED_SIGNALS H00001=U7_10 · T00009=AVOID_CHASE
    PENDING_FOR_NEXT_TICK          (없음)
  [t+180 Y 지속(전달 뒤)] status=skipped reason=no_new_or_worsened partial=False 본문=(전송 없음)
    OBSERVATION_STATE              H00001=U7_10(연속) · T00009=AVOID_CHASE(연속)
    DELIVERY_STATE                 S: H00001=U7_10@t+120 · T00009=AVOID_CHASE@t+120 · sent_today=2 · D* worst: (없음) · 집계 틱=4
    ACTUALLY_INCLUDED_SIGNALS      (없음)
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          (없음)

== test_run_realistic_chunk_partial_delivery_is_resent · 실제형 부분 전송
  [t+0 X 전달(1청크)] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U5_7(연속) · T00009=ENTRY_REVIEW(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=1
    ACTUALLY_INCLUDED_SIGNALS      H00001=U5_7 · T00009=ENTRY_REVIEW
    SUCCESSFULLY_DELIVERED_SIGNALS H00001=U5_7 · T00009=ENTRY_REVIEW
    PENDING_FOR_NEXT_TICK          (없음)
  [t+60 Y 둘째 청크 실패] status=failed reason=telegram_send_error partial=True 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U7_10(연속) · T00009=AVOID_CHASE(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=2
    ACTUALLY_INCLUDED_SIGNALS      H00001=U7_10 · H00002=D5_7 · H00003=D5_7 · T00009=AVOID_CHASE
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          H00001=U7_10 · H00002=D5_7 · H00003=D5_7 · T00009=AVOID_CHASE
  [t+120 Y 지속 · 전송 정상] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U7_10(연속) · T00009=AVOID_CHASE(연속)
    DELIVERY_STATE                 S: H00001=U7_10@t+120 · T00009=AVOID_CHASE@t+120 · sent_today=2 · D* worst: H00002=D5_7 · H00003=D5_7 · 집계 틱=3
    ACTUALLY_INCLUDED_SIGNALS      H00001=U7_10 · H00002=D5_7 · H00003=D5_7 · T00009=AVOID_CHASE
    SUCCESSFULLY_DELIVERED_SIGNALS H00001=U7_10 · H00002=D5_7 · H00003=D5_7 · T00009=AVOID_CHASE
    PENDING_FOR_NEXT_TICK          (없음)

== test_run_same_state_is_suppressed_after_successful_delivery · 성공 뒤 억제
  [t+0 Y 전달] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U7_10(연속) · T00009=AVOID_CHASE(연속)
    DELIVERY_STATE                 S: H00001=U7_10@t+0 · T00009=AVOID_CHASE@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=1
    ACTUALLY_INCLUDED_SIGNALS      H00001=U7_10 · T00009=AVOID_CHASE
    SUCCESSFULLY_DELIVERED_SIGNALS H00001=U7_10 · T00009=AVOID_CHASE
    PENDING_FOR_NEXT_TICK          (없음)
  [t+60 Y 지속] status=skipped reason=no_new_or_worsened partial=False 본문=(전송 없음)
    OBSERVATION_STATE              H00001=U7_10(연속) · T00009=AVOID_CHASE(연속)
    DELIVERY_STATE                 S: H00001=U7_10@t+0 · T00009=AVOID_CHASE@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=2
    ACTUALLY_INCLUDED_SIGNALS      (없음)
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          (없음)
  [t+300 Y 지속(cooldown 경과)] status=skipped reason=no_new_or_worsened partial=False 본문=(전송 없음)
    OBSERVATION_STATE              H00001=U7_10(연속) · T00009=AVOID_CHASE(연속)
    DELIVERY_STATE                 S: H00001=U7_10@t+0 · T00009=AVOID_CHASE@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=3
    ACTUALLY_INCLUDED_SIGNALS      (없음)
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          (없음)

== test_run_q3_x_undelivered_y_then_x_is_suppressed_then_y_sent · Q3 X→Y→X→Y
  [t+0 X 전달] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U5_7(연속) · T00009=ENTRY_REVIEW(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=1
    ACTUALLY_INCLUDED_SIGNALS      H00001=U5_7 · T00009=ENTRY_REVIEW
    SUCCESSFULLY_DELIVERED_SIGNALS H00001=U5_7 · T00009=ENTRY_REVIEW
    PENDING_FOR_NEXT_TICK          (없음)
  [t+60 Y 전송 실패] status=failed reason=telegram_send_error partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U7_10(연속) · T00009=AVOID_CHASE(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=2
    ACTUALLY_INCLUDED_SIGNALS      H00001=U7_10 · T00009=AVOID_CHASE
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          H00001=U7_10 · T00009=AVOID_CHASE
  [t+120 다시 X] status=skipped reason=no_new_or_worsened partial=False 본문=(전송 없음)
    OBSERVATION_STATE              H00001=U5_7(연속) · T00009=ENTRY_REVIEW(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=3
    ACTUALLY_INCLUDED_SIGNALS      (없음)
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          (없음)
  [t+180 다시 Y] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U7_10(연속) · T00009=AVOID_CHASE(연속)
    DELIVERY_STATE                 S: H00001=U7_10@t+180 · T00009=AVOID_CHASE@t+180 · sent_today=2 · D* worst: (없음) · 집계 틱=4
    ACTUALLY_INCLUDED_SIGNALS      H00001=U7_10 · T00009=AVOID_CHASE
    SUCCESSFULLY_DELIVERED_SIGNALS H00001=U7_10 · T00009=AVOID_CHASE
    PENDING_FOR_NEXT_TICK          (없음)

== test_run_exception_after_assembly_marks_nothing_delivered[diagnostics] · _boom_diag
  [t+0 조립 뒤 예외] status=sent reason=- partial=False 본문=[보유 급락 알림] intraday_error=RuntimeError
    OBSERVATION_STATE              (S 파일 없음/비어 있음)
    DELIVERY_STATE                 S: (전달 이력 없음) · sent_today=1 · D* worst: H00001=D5_7 · 집계 틱=0
    ACTUALLY_INCLUDED_SIGNALS      H00001=D5_7
    SUCCESSFULLY_DELIVERED_SIGNALS H00001=D5_7
    PENDING_FOR_NEXT_TICK          H00002=U7_10 · T00009=ENTRY_REVIEW
  [t+60 주입 없음] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00002=U7_10(연속) · T00009=ENTRY_REVIEW(연속)
    DELIVERY_STATE                 S: H00002=U7_10@t+60 · T00009=ENTRY_REVIEW@t+60 · sent_today=2 · D* worst: H00001=D5_7 · 집계 틱=1
    ACTUALLY_INCLUDED_SIGNALS      H00002=U7_10 · T00009=ENTRY_REVIEW
    SUCCESSFULLY_DELIVERED_SIGNALS H00002=U7_10 · T00009=ENTRY_REVIEW
    PENDING_FOR_NEXT_TICK          (없음)

== test_run_exception_after_assembly_marks_nothing_delivered[records] · _boom_records
  [t+0 조립 뒤 예외] status=sent reason=- partial=False 본문=[보유 급락 알림] intraday_error=TypeError
    OBSERVATION_STATE              (S 파일 없음/비어 있음)
    DELIVERY_STATE                 S: (전달 이력 없음) · sent_today=1 · D* worst: H00001=D5_7 · 집계 틱=0
    ACTUALLY_INCLUDED_SIGNALS      H00001=D5_7
    SUCCESSFULLY_DELIVERED_SIGNALS H00001=D5_7
    PENDING_FOR_NEXT_TICK          H00002=U7_10 · T00009=ENTRY_REVIEW
  [t+60 주입 없음] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00002=U7_10(연속) · T00009=ENTRY_REVIEW(연속)
    DELIVERY_STATE                 S: H00002=U7_10@t+60 · T00009=ENTRY_REVIEW@t+60 · sent_today=2 · D* worst: H00001=D5_7 · 집계 틱=1
    ACTUALLY_INCLUDED_SIGNALS      H00002=U7_10 · T00009=ENTRY_REVIEW
    SUCCESSFULLY_DELIVERED_SIGNALS H00002=U7_10 · T00009=ENTRY_REVIEW
    PENDING_FOR_NEXT_TICK          (없음)

== test_run_exception_after_assembly_marks_nothing_delivered[tally_classification] · _boom_tally
  [t+0 조립 뒤 예외] status=sent reason=- partial=False 본문=[보유 급락 알림] intraday_error=RuntimeError
    OBSERVATION_STATE              (S 파일 없음/비어 있음)
    DELIVERY_STATE                 S: (전달 이력 없음) · sent_today=1 · D* worst: H00001=D5_7 · 집계 틱=0
    ACTUALLY_INCLUDED_SIGNALS      H00001=D5_7
    SUCCESSFULLY_DELIVERED_SIGNALS H00001=D5_7
    PENDING_FOR_NEXT_TICK          H00002=U7_10 · T00009=ENTRY_REVIEW
  [t+60 주입 없음] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00002=U7_10(연속) · T00009=ENTRY_REVIEW(연속)
    DELIVERY_STATE                 S: H00002=U7_10@t+60 · T00009=ENTRY_REVIEW@t+60 · sent_today=2 · D* worst: H00001=D5_7 · 집계 틱=1
    ACTUALLY_INCLUDED_SIGNALS      H00002=U7_10 · T00009=ENTRY_REVIEW
    SUCCESSFULLY_DELIVERED_SIGNALS H00002=U7_10 · T00009=ENTRY_REVIEW
    PENDING_FOR_NEXT_TICK          (없음)

== test_run_exception_after_assembly_with_failed_send_saves_no_d_star[telegram_failure-diagnostics] · 예외+실패
  [t+0 조립 뒤 예외 + 전송 실패] status=failed reason=telegram_send_error partial=False 본문=[보유 급락 알림] intraday_error=RuntimeError
    OBSERVATION_STATE              (S 파일 없음/비어 있음)
    DELIVERY_STATE                 S: (전달 이력 없음) · sent_today=None · D* worst: (없음) · 집계 틱=0
    ACTUALLY_INCLUDED_SIGNALS      H00001=D5_7
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          H00001=D5_7 · H00002=U7_10 · T00009=ENTRY_REVIEW

== test_run_exception_after_assembly_with_failed_send_saves_no_d_star[telegram_failure-records] · 예외+실패
  [t+0 조립 뒤 예외 + 전송 실패] status=failed reason=telegram_send_error partial=False 본문=[보유 급락 알림] intraday_error=TypeError
    OBSERVATION_STATE              (S 파일 없음/비어 있음)
    DELIVERY_STATE                 S: (전달 이력 없음) · sent_today=None · D* worst: (없음) · 집계 틱=0
    ACTUALLY_INCLUDED_SIGNALS      H00001=D5_7
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          H00001=D5_7 · H00002=U7_10 · T00009=ENTRY_REVIEW

== test_run_exception_after_assembly_with_failed_send_saves_no_d_star[telegram_failure-tally_classification] · 예외+실패
  [t+0 조립 뒤 예외 + 전송 실패] status=failed reason=telegram_send_error partial=False 본문=[보유 급락 알림] intraday_error=RuntimeError
    OBSERVATION_STATE              (S 파일 없음/비어 있음)
    DELIVERY_STATE                 S: (전달 이력 없음) · sent_today=None · D* worst: (없음) · 집계 틱=0
    ACTUALLY_INCLUDED_SIGNALS      H00001=D5_7
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          H00001=D5_7 · H00002=U7_10 · T00009=ENTRY_REVIEW

== test_run_exception_after_assembly_with_failed_send_saves_no_d_star[partial_delivery-diagnostics] · 예외+실패
  [t+0 조립 뒤 예외 + 전송 실패] status=sent reason=- partial=True 본문=[보유 급락 알림] intraday_error=RuntimeError
    OBSERVATION_STATE              (S 파일 없음/비어 있음)
    DELIVERY_STATE                 S: (전달 이력 없음) · sent_today=None · D* worst: (없음) · 집계 틱=0
    ACTUALLY_INCLUDED_SIGNALS      H00001=D5_7
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          H00001=D5_7 · H00002=U7_10 · T00009=ENTRY_REVIEW

== test_run_exception_after_assembly_with_failed_send_saves_no_d_star[partial_delivery-records] · 예외+실패
  [t+0 조립 뒤 예외 + 전송 실패] status=sent reason=- partial=True 본문=[보유 급락 알림] intraday_error=TypeError
    OBSERVATION_STATE              (S 파일 없음/비어 있음)
    DELIVERY_STATE                 S: (전달 이력 없음) · sent_today=None · D* worst: (없음) · 집계 틱=0
    ACTUALLY_INCLUDED_SIGNALS      H00001=D5_7
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          H00001=D5_7 · H00002=U7_10 · T00009=ENTRY_REVIEW

== test_run_exception_after_assembly_with_failed_send_saves_no_d_star[partial_delivery-tally_classification] · 예외+실패
  [t+0 조립 뒤 예외 + 전송 실패] status=sent reason=- partial=True 본문=[보유 급락 알림] intraday_error=RuntimeError
    OBSERVATION_STATE              (S 파일 없음/비어 있음)
    DELIVERY_STATE                 S: (전달 이력 없음) · sent_today=None · D* worst: (없음) · 집계 틱=0
    ACTUALLY_INCLUDED_SIGNALS      H00001=D5_7
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          H00001=D5_7 · H00002=U7_10 · T00009=ENTRY_REVIEW

== test_run_recovery_then_undelivered_y_then_x_follows_cooldown_rule · 회복 → 미전달 Y → X
  [t+0 X 전달] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U5_7(연속) · T00009=ENTRY_REVIEW(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=1
    ACTUALLY_INCLUDED_SIGNALS      H00001=U5_7 · T00009=ENTRY_REVIEW
    SUCCESSFULLY_DELIVERED_SIGNALS H00001=U5_7 · T00009=ENTRY_REVIEW
    PENDING_FOR_NEXT_TICK          (없음)
  [t+60 X 회복(임계 밖)] status=skipped reason=no_new_or_worsened partial=False 본문=(전송 없음)
    OBSERVATION_STATE              H00001=U5_7(연속) · T00009=ENTRY_REVIEW(끊김)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=2
    ACTUALLY_INCLUDED_SIGNALS      (없음)
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          (없음)
  [t+120 Y 전송 실패] status=failed reason=telegram_send_error partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U5_7(연속) · T00009=AVOID_CHASE(끊김)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=3
    ACTUALLY_INCLUDED_SIGNALS      T00009=AVOID_CHASE
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          T00009=AVOID_CHASE
  [t+300 X 재진입(cooldown 경과)] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U5_7(연속) · T00009=ENTRY_REVIEW(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+300 · sent_today=2 · D* worst: (없음) · 집계 틱=4
    ACTUALLY_INCLUDED_SIGNALS      T00009=ENTRY_REVIEW
    SUCCESSFULLY_DELIVERED_SIGNALS T00009=ENTRY_REVIEW
    PENDING_FOR_NEXT_TICK          (없음)
  [t+360 X 지속(전달 뒤)] status=skipped reason=no_new_or_worsened partial=False 본문=(전송 없음)
    OBSERVATION_STATE              H00001=U5_7(연속) · T00009=ENTRY_REVIEW(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+300 · sent_today=2 · D* worst: (없음) · 집계 틱=5
    ACTUALLY_INCLUDED_SIGNALS      (없음)
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          (없음)

== test_run_recovery_then_undelivered_y_then_x_within_cooldown_is_suppressed · 회복 → Y → X(이내)
  [t+0 X 전달] status=sent reason=- partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U5_7(연속) · T00009=ENTRY_REVIEW(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=1
    ACTUALLY_INCLUDED_SIGNALS      H00001=U5_7 · T00009=ENTRY_REVIEW
    SUCCESSFULLY_DELIVERED_SIGNALS H00001=U5_7 · T00009=ENTRY_REVIEW
    PENDING_FOR_NEXT_TICK          (없음)
  [t+30 X 회복] status=skipped reason=no_new_or_worsened partial=False 본문=(전송 없음)
    OBSERVATION_STATE              H00001=U5_7(연속) · T00009=ENTRY_REVIEW(끊김)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=2
    ACTUALLY_INCLUDED_SIGNALS      (없음)
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          (없음)
  [t+60 Y 전송 실패] status=failed reason=telegram_send_error partial=False 본문=[장중 급등락]
    OBSERVATION_STATE              H00001=U5_7(연속) · T00009=AVOID_CHASE(끊김)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=3
    ACTUALLY_INCLUDED_SIGNALS      T00009=AVOID_CHASE
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          T00009=AVOID_CHASE
  [t+90 X 재진입(cooldown 이내)] status=skipped reason=no_new_or_worsened partial=False 본문=(전송 없음)
    OBSERVATION_STATE              H00001=U5_7(연속) · T00009=ENTRY_REVIEW(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=4
    ACTUALLY_INCLUDED_SIGNALS      (없음)
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          (없음)
  [t+300 X 지속(cooldown 경과)] status=skipped reason=no_new_or_worsened partial=False 본문=(전송 없음)
    OBSERVATION_STATE              H00001=U5_7(연속) · T00009=ENTRY_REVIEW(연속)
    DELIVERY_STATE                 S: H00001=U5_7@t+0 · T00009=ENTRY_REVIEW@t+0 · sent_today=1 · D* worst: (없음) · 집계 틱=5
    ACTUALLY_INCLUDED_SIGNALS      (없음)
    SUCCESSFULLY_DELIVERED_SIGNALS (없음)
    PENDING_FOR_NEXT_TICK          (없음)
```
