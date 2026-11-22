# POC6-35 개발 결과서 — 장중 재진입 알림 누락(K2) 정정

- 단계 ID: **POC6-35**(선행 POC6-34 PASS · CLOSED)
- 설계서: `docs/ai_design/POC6/POC6_35_INTRADAY_REENTRY_ALERT_DELIVERY_DESIGN_V1_2026-11-19.md`(AC1 ~ AC3)
- 설계자 PLAN 판정: `docs/ai_design/POC6/POC6_35_INTRADAY_REENTRY_ALERT_DELIVERY_PLAN_DECISION_2026-11-19.md`(보완 후 구현 승인 · A1 채택 · Q3 · Q5 · Q10 보완 수용 · 나머지 수용)
- 개발 PLAN(V1 확정): `docs/ai_plan/POC6/POC6_35_INTRADAY_REENTRY_ALERT_DELIVERY_PLAN_V1.md`(§0-1 [원장 새로고침] 결과 · §2 변경 표 · §3 시나리오 ① ~ ⑮ · §4 운영 확인 · §7 한계 · §9 보완 1 ~ 3)
- **코드 위치:** 격리 작업 사본 `/Users/hyungsookim/projects/krx_hyungsoo_wt_poc6_34` · 브랜치 `poc6-35-reentry`(기준 main `631b14a9` 에서 시작). 바뀐 코드 · 시험 · `docs/PROGRAM_TRUTH.md` 는 모두 이 사본의 커밋 전 변경이다(경로별 stage · §2). 이 결과서 · 설계서 · 판정 · PLAN · `docs/STATE_LATEST.md` 는 main 저장소에 있다(경로별 stage · 커밋 전).
- 격리 서버: 백엔드 8001(`uvicorn --reload` · 작업 사본 `app/` 를 봄) · 화면 3001(작업 사본 next dev). 이 작업에서 시작 · 중지하지 않았다. 운영 3000 · 8000 · OCI 는 손대지 않았다.
- **상태: 구현 · 통합 · 독립 검토 1회(두 관점) 처리 · 형수님 Q8 화면 문장 확인(2026-11-20) · 검증자 r1 `REJECTED`(F1 · §12) → F1 정정(§13 · 형수님 결정 2건 2026-11-20) → 검증자 r2 `VERIFIED`(§14 · 2026-11-20) → 설계자 RESULT `PASS`(2026-11-20) → 커밋 전 전체 회귀 통과 → 형수님 커밋 · push 승인 → 구현 커밋 `f0e0c945` main 반영 · push(§15).** 두 갈래(백엔드 BE · 화면 문장 FE) 구현 → 통합 → 독립 검토 지적 처리(§11) → 형수님 격리 화면 확인(§7) → 검증자 r1(§12) → F1 정정(§13) → 검증자 r2(§14) → 설계자 RESULT PASS · 전체 회귀 → 커밋 · main 반영 · push(§15). OCI pull(형수님 · push 뒤) · OCI revision 확인 = 완료(§15-2). 다음 = 운영 확인(반영 뒤 첫 정규 장중 회차 = 2026-11-23(월) 09:30 · 그 뒤 [원장 새로고침] · PLAN §4 · RESULT 판정 '반영과 종료 기준' 2 ~ 4) → AC3 근거를 담은 이 결과서를 설계자에게 회신 → 설계자 종료 판정(설계자 2026-11-21) → 그 뒤 POC7-01 PLAN.
- **공개 저장소 표기:** 보유 이름 · 코드 · 수량 · 금액은 적지 않는다. 시험에 나오는 종목은 시험 틀(rig)의 가짜 종목이다.

---

## 0. 요약

- **원인(PLAN §1-1):** 알린 뒤 조건 밖으로 나갔다가(회복) 마지막 전달 상태와 **같은 상태**로 다시 잡혀 재발송 대기를 채운 재진입은 그 회차의 발송 후보다. 이 후보가 구역 한도 · 전송 실패 등으로 본문에 실리지 못해도, 관측 저장이 그 행을 '이어짐'(`continuous=True`)으로 썼다. 그래서 다음 회차부터 조건이 이어지고 자리가 있어도 억제됐다(K2).
- **정정(원안 A1):** 이번 회차 발송 후보 `(종목, 상태)` 집합을 관측을 쓰는 두 저장(전송 성공 저장 `merge_sector_entries` · 매 회차 `save_observation`)에 **같은 집합**으로 넘긴다. '회복 ∧ 마지막 전달 상태와 같음 ∧ 후보'인 행은 회복 기록(`continuous=False`)을 유지한다. 다음 회차는 기존 '회복 뒤 재진입' 규칙(그 회차 정책의 재발송 대기 · 마지막 성공 전달 시각)으로 다시 판정한다.
  - 대기 때문에 억제된 재진입은 후보가 아니라 예전처럼 `True` 가 된다 → **K3 그대로**.
  - 전달에 성공한 행은 sent 루프가 `True` 와 새 `last_sent_at` 을 쓴다 → **AC2 반복 억제 그대로**.
- **보완 1(Q3 · 성공 전달 기록):** 통합 본문이 나간 회차의 최종 status 가 `sent` · 부분 전송 아님인데 러너 첫 상태 저장이 끝나지 않았으면, 뒤의 관측 저장이 첫 저장과 같은 병합(전달 필드 · `continuous=True` · `sent_today` +1)을 대신 한다. 실린 신호 행에 이번 회차 시각이 이미 있으면 `sent_today` 를 다시 올리지 않는다. 실행 기록에 `intraday_state_saved_by_observation=True` 가 남는다.
  - **대신 저장까지 실패하면(독립 검토 B-1):** `save_observation` 이 관측만 쓰는 저장을 한 번 더 해 이번 회차 관측 · 회복 기록을 남긴다(`sent_today` · 전달 필드는 그대로). 실행 기록에 `intraday_state_save_fallback_error`(예외 형)가 남는다. 그것까지 실패해야 예외를 내고 `intraday_observation_error` 가 남는다.
- **검증자 r1 F1 정정(§13 · 쓰기 직전 다시 읽기 실패 ≠ 발송 이력 없음):** 세 쓰기(러너 첫 저장 · 매 회차 관측 저장 · 대신 저장과 그 재시도)는 쓰기 직전에 상태 파일을 다시 읽는다. 그 읽기가 **읽기 실패**(`unreadable`)이면 이번 회차가 이미 아는 상태 위에 쓴다(`load_merge_base`). 아는 상태 = 조립 때 읽은 상태(`IntradayAssembly.previous` → pending `state_snapshot`) · 첫 저장이 썼으면 그 쓴 상태. 그래서 읽기 한 번 실패로 앞선 전달 기록 · `sent_today` 가 지워져 다음 회차에 재발송하거나 일일 상한을 넘기는 일이 없다.
  - **진단:** 실행 기록에 `intraday_state_save_base` · `intraday_observation_base`(`snapshot` · `unreadable`)가 남는다.
  - **예전 규칙 그대로인 경우:** 조립 때도 못 읽은 손상 파일은 예전처럼 비교 불가(전부 신규)로 보고 새로 써서 복구한다. 다시 읽기가 정상 · 없음 · 날짜 바뀜 · 형식 다름이어도 예전 규칙이다.
  - **형수님 결정(2026-11-20):** 같은 원인의 기존 두 경로(첫 저장 · 매 회차 관측 저장)도 함께 고쳤다. 조립 결과에 `previous` 칸을 더하느라 `intraday_alert_flow.py` 를 고쳤는데(PLAN §2 '변경 없음'과 다름 · §4 · §7), 이것도 형수님 결정이다.
- **보완 2(Q5 · 다음 회차 대기 판정):** 판정 코드는 바꾸지 않았다. 그 회차의 활성 정책 대기로 판정되는 것과, 미충족이면 K3 지속 억제로 바뀌는 것, 평가 불가 회차가 행을 그대로 두는 것을 시험 ⑨ · ⑭ · ⑮ 로 확인했다.
- **보완 3(Q10 · 운영 근거):** 반영 뒤 할 일이다(PLAN §4). 반영 전 기준선은 PLAN §0-1 에 있다(지난 31거래일 K2 의심 건 0건).
- **화면 문장(Q8):** 「OCI 운영·적용」 ② '장중 급등락 설정' 판정 기준 표 '구역별 최대' 행 '이 값의 뜻' 마지막 문장을 판정 문구로 바꿨다. 형수님이 격리 화면 캡처로 확인했다(2026-11-20 · §7).
- **바꾸지 않은 것:** 상태 파일 형식 · 필드 · `schema_version` · 임계값 · 재발송 대기 · 구역 · 일일 상한 · 정렬 · cron · 운영 flag · 원장 코드 · 원장 계약 버전(`holdings_risk_alert.v1`) · 판정 코드(`compute_sector_changes` · 조립의 판정 · 정렬 · 상한). `intraday_alert_flow.py` 는 r1 F1 정정으로 결과 칸 1개를 더하고 판정에 쓴 상태를 남기는 대입만 바꿨다(+3 / −1 · 592 → 594).
- **검사(검증자 r1 F1 정정 뒤 · 2026-11-20 · 최종 바이트):**
  - **정적 검사:** 백엔드 black · flake8 · py_compile 통과.
  - **관련 시험:** 38파일 **677 passed**(새 시험 70건 포함 · 지난 37파일 + 조립 모듈을 쓰는 `test_poc6_34_intraday_config_state`).
  - **RED(최종 시험 파일 바이트):**
    - POC6-35 전 main: 새 시험 **65 failed · 5 passed**.
    - r1 제출본(정정 전 stage 내용): **29 failed · 41 passed**. r1 새 시험 15건이 모두 실패하고, 나머지 14건은 반환값 칸 수 차이다.
  - **변이:** 백엔드 **32 / 32** 모두 잡혔다(지난 17 다시 · r1 15 새로).
  - **화면:** 화면 파일은 r1 정정에서 바뀌지 않아 통합 단계 결과(tsc · eslint 0 · vitest 190 passed · 화면 변이 3 / 3)를 그대로 둔다.

## 1. 처리한 요구사항

### 1-1. PLAN §2 변경 표

| 항목 | 상태 | 반영(격리 사본 코드 확인 · 줄 번호는 지금 파일) |
|---|---|---|
| 판정 · 저장 `app/runtime_evidence/sector_signal_state.py` | DONE | 후보 집합 helper `send_candidates(*change_sets)`(:109 · 형 별칭 `Candidates` :106 · `__all__` :579). `_apply_observation(row, sig, candidates=None)`(:166) — `is_candidate = (sig.ticker, sig.state) in candidates`(:191) · `continuous = not (recovered and delivered is not None and (sig.state != delivered or is_candidate))`(:192-193). `merge_sector_entries(candidates=)`(:371 · 관측 루프 :405) · `save_observation(candidates=)`(:422 · 관측 루프 :521). 새 인자 기본값 None = 예전 동작. sent 루프 · `compute_sector_changes` 판정 순서 · `mark_absent_entries` 무변경. 독스트링 갱신(모듈 머리 · `_apply_observation` · `compute_sector_changes` · `merge_sector_entries` · `save_observation` · `save_sector_state`) |
| 성공 저장 경로 `app/three_push_runtime/runner_evidence.py` | DONE | `_save_intraday_state_after_send` 가 `send_candidates(intraday.changes, intraday.surge_changes)`(:185)를 `merge_sector_entries(candidates=)`(:194)에 넘긴다. 독스트링 · `record_send_success` 주석 갱신 |
| 관측 저장 경로 `app/runtime_evidence/holdings_risk_flow.py` | DONE | pending(`intraday_records`)에 `candidates`(:412 · 조립 결과 `intraday` 에서 만든 같은 출처) → `apply_intraday_records` 가 `save_observation(candidates=)`(:558). pending 은 직렬화 전에 꺼내 지운다(기존 `PENDING_KEY` 계약 · JSON 에 안 나감) |
| 성공 사실 보존(보완 1) | DONE | 통합 본문 대체 분기(`out.intraday = intraday`)에서만 pending 에 `sent_signals`(:477 · 첫 저장과 같은 목록). `apply_intraday_records` 대신 저장 조건(:547-:552) = `sent_signals` 있음 ∧ status `sent` ∧ `partial_delivery` 아님 ∧ `intraday_state_saved` 없음 → `save_observation(sent=, now_kst=_now_kst(runtime_kst))`(:553). 반환 `(쓴 것, 대신 저장 예외 형, 기준 진단)` — 예외 형이 있으면 `intraday_state_save_fallback_error`(:565-:566) · 쓴 것이 `"sent"` 면 `intraday_state_saved_by_observation=True`(:567-:568). `save_observation`(반환형 :432): `sent` 만 있고 `now_kst` 가 없으면 ValueError(:486) · 실린 행 중 하나라도 `last_sent_at` 이 이번 회차 시각이면 +1 안 함(:495 · :512) · `merge_sector_entries`(:500) → 저장 → `("sent", None, 기준 진단)`(:514). 병합 · 쓰기가 예외면 예외 형을 기억하고(:516) 관측만 쓰는 저장(:517-:522)으로 내려가 `("observation", 예외 형, 기준 진단)`(:523). 관측만 쓰는 저장까지 실패하면 예외 → 호출자가 `intraday_observation_error`(:572). 기존 진단 키(`intraday_observation_saved` · `_preserved` · `_error`) 그대로 |
| 쓰기 기준 상태(검증자 r1 F1 · §13) | DONE | `sector_signal_state.load_merge_base(path, today_kst=, snapshot=)`(:224) — 다시 읽기의 `fallback_reason` 이 `unreadable` 이 아니면 읽은 그대로 · 진단 None(:244-:245). `unreadable` 이면 `snapshot` 이 있고 비교 가능하고 날짜가 같을 때(둘 다 있을 때만 비교 · `load_sector_state` 와 같은 규칙) 그 상태 · `'snapshot'`, 아니면 읽은 비교 불가 상태 · `'unreadable'`(:253). 세 쓰기가 모두 이 함수로 기준을 잡는다 — 러너 첫 저장 `load_merge_base(snapshot=intraday.previous)`(`runner_evidence.py:170` · 진단 `intraday_state_save_base` :176) · `save_observation`(:487 · 대신 저장 병합 · 그 재시도 · 관측만 쓰기가 같은 기준). 첫 저장은 쓴 뒤 pending `state_snapshot` 을 방금 쓴 상태(같은 entries · 오늘 날짜 · 쓴 `sent_today`)로 바꾼다(`runner_evidence.py:201-209`). pending 의 처음 값 = 조립 때 상태(`holdings_risk_flow.py:413`) → `save_observation(snapshot=)`(:561) · 진단 `intraday_observation_base`(:563-:564). 기존 첫 저장의 `sent_today` 계산 · `intraday_sent_today` 기록은 같은 값(`count` · :197 · :225) |
| 조립 `app/runtime_evidence/intraday_alert_flow.py` | DONE(r1 F1 · 판정 무변경) | 결과 칸 `IntradayAssembly.previous: Any = None`(:107 · 주석 :106) · 판정에 쓴 상태를 그대로 남김 `previous = out.previous = load_sector_state(...)`(:494). 592 → 594줄(+3 / −1). PLAN §1-7 KS-10 표 '고치지 않음' · §2 '변경 없음' · Q3 '`intraday_alert_flow.py` 무변경'과 다르다 — 형수님 결정(2026-11-20 · §4 · §7) |
| 원장 `ledger_items.py` · `ledger_context.py` · `ledger_store.py` | DONE(코드 변경 없음) | 세 파일 diff 0. 처분의 뜻만 바뀐다(K2 다음 회차 `suppressed` → `sent` · `cut_by_section_cap` · 일일 상한 뒤 회차 `suppressed` → `cut_by_daily_cap` · 시험 ⑧) |
| 문서 `docs/PROGRAM_TRUTH.md` | DONE(격리 사본) | 머리 줄 :5('`POC6-35` 반영 대기(격리 사본)' · '독립 검토 1회 반영 · 검증자 r1 REJECTED(F1) 정정 · 검증자 r2 VERIFIED · 설계자 RESULT 전') · 화면 문장 :314('형수님 실화면 확인 2026-11-20') · 상태 파일 표 :447 · §9 '장중 급등락' 의 '사업군 · 급등 전달 상태' 아래 세 항목 :888-943(대신 저장 실패 · 모두 실패 · `intraday_sent_today` 없음 문장 포함 · 세 번째 항목 :931-943 = r1 F1 쓰기 기준) · 부록 A 표 :1215(`sector_signal_state.py`) · :1216(`intraday_alert_flow.py` · r1 F1) · :1219(`apply_intraday_records`) · :1220(`runner_evidence :: _save_intraday_state_after_send`). 모든 자리에 '`POC6-35`(반영 대기 · 격리 사본)' 표시 |
| 화면 문장(Q8) | DONE · 형수님 실화면 확인(2026-11-20 · §7) | `frontend/app/components/approval/intradayCriteria.ts:377`(`sectionTexts` meaning 마지막 문장) · 시험 `intradayCriteria.test.ts:131`. 새 문장 = '보유 급락, 아직 알린 적 없는 신호, 마지막 알림과 상태가 다른 신호, 구역 한도에 밀린 재진입 신호는 다음 회차의 조건과 발송 한도에 따라 다시 검토합니다.' · 앞 두 문장 그대로. `frontend/app` 안 옛 문장 0건 |
| 바꾸지 않는 것 | DONE | 바뀐 경로는 §2 표 9개뿐이다. `app` diff 의 `schema_version` · 상수 · 임계값 · 대기 낱말은 독스트링 줄뿐이다(`git diff -U0 app` grep · 코드 줄 0). 설정 · cron · flag 파일 변경 0 · 수동 발송 0 |

### 1-2. PLAN §3 시나리오(새 시험 `tests/test_poc6_35_reentry_delivery.py` · run() 순서 · 다음 회차 본문 포함 여부를 전송기에 넘어간 본문으로 직접 단언)

| # | 시험 | 변경 전(RED) | 변경 후 | 상태 |
|---|---|---|---|---|
| ① K2 고정 사례(사업군 · 구역 한도) | `test_k2_reentry_cut_by_section_cap_is_sent_next_tick` | 실패 :118 '잘린 재진입이 다음 회차에 실리지 않았다' | 다음 회차 본문 포함 · 재전달 뒤 AC2 억제 · 해소 뒤 새 전달 기준 90분 재진입 억제 | DONE |
| ② 전송 실패 · 부분 전송 · 발송 전 차단 | `test_k2_reentry_undelivered_by_send_outcome_is_retried[telegram_send_error · partial_delivery · blocked_before_send]` | 3건 실패 :177 | 3건 모두 다음 회차 후보 → 발송 · 그다음 억제 | DONE |
| ③ 보유 급등 재진입이 급락 3건에 밀림 | `test_k2_held_surge_reentry_cut_by_held_drops_is_sent_next_tick` | 실패 :210 | 다음 회차 발송 | DONE |
| ④ 다음 회차 조건 이탈 | `test_reentry_cut_then_condition_exits_uses_last_successful_delivery` | 통과 | 통과(발송 안 함 · 그 뒤 재진입 대기 = 마지막 성공 전달 기준) | DONE |
| ⑤ AC2 재전달 뒤 반복 없음 | `test_ac2_redelivered_reentry_is_not_repeated` | 통과 | 통과 | DONE |
| ⑥ K3 119분 재진입 억제 → 지속 억제 | `test_k3_reentry_within_cooldown_then_continues_is_suppressed` | 통과 | 통과 · 기존 K3 잠금(`tests/test_poc3_02d_ops02_delivery_state.py`)도 그대로 통과 | DONE |
| ⑦ 두 번 잘림 | `test_reentry_cut_twice_stays_candidate` | 실패 :295 | 두 번째도 잘림(우선권 없음 · Q4) → 자리가 나면 실림 | DONE |
| ⑧ 일일 상한 회차 | `test_daily_cap_keeps_reentry_candidate_and_ledger_says_daily_cap` | 실패 :333(다음 회차 처분 `suppressed`) | 그날 발송 0 · 두 회차 모두 원장 처분 `cut_by_daily_cap`(Q6) · 회복 기록 유지 | DONE |
| ⑨ · ⑮ 평가 불가 회차(보완 2) | `test_unevaluable_tick_keeps_cut_reentry_pending[provider_down · single_ticker]` | 2건 실패 :355 | 평가 불가 회차는 행 그대로 → 다음 정상 평가에서 발송 | DONE |
| ⑩ 첫 저장만 실패(보완 1) | `test_first_save_fails_observation_save_keeps_success` | 실패 :389 '성공 전달 시각이 남지 않았다' | 다음 회차 반복 없음 · `sent_today` +1 한 번 · `last_sent_at` = 이번 회차 | DONE |
| ⑪ 첫 저장 성공(보완 1) | `test_first_save_succeeds_observation_save_does_not_recount` | 통과 | 통과(대신 저장 안 함 · 이중 증가 없음) | DONE |
| ⑪-b 첫 저장은 써졌는데 표식만 없음(추가) | `test_first_save_written_but_flag_lost_counts_once` | 실패 :425(진단 키 없음 · `sent_today` 는 원래 맞음) | 이번 회차 시각이 이미 있어 `sent_today` 를 다시 세지 않음 | DONE |
| ⑫ 이번 회차 상태 쓰기 모두 실패(보완 1 · I1) | `test_both_saves_fail_is_a_general_state_save_failure` | 통과 | 통과 — 쓰기 3번(첫 저장 · 대신 저장 · 관측만 다시 쓰기) 모두 실패 주입 · 두 진단 키 · 대신 저장 실패 키 없음 · 상태 파일 바이트 그대로 · `sent` 유지. 다음 회차에 한 번 더 나가고 `sent_today` 2(발송 회차 3) · 그다음 억제 | DONE |
| ⑫-b 대신 저장까지 실패(독립 검토 B-1) | `test_fallback_merge_fails_still_saves_observation[bad_sent_signal · write_fails_twice]` | 2건 실패 :499(변경 전에는 대신 저장 자체가 없어 진단 키 없음) | 관측만 다시 씀 — 빠진 종목 회복 기록(`False`) · 재진입 행 회복 유지 · `intraday_state_save_fallback_error` = `AttributeError` / `OSError` · `intraday_observation_saved` 있음 · `_error` · `_saved_by_observation` 없음 · `sent_today` 그대로. 다음 회차에 한 번 더 나감 | DONE |
| ⑬ 처음 잡힌 신호 · 상태 변화, 첫 저장만 실패(보완 1) | `test_first_save_fails_for_new_and_changed_signals_keeps_success[first_detected · state_change]` | 2건 실패 :533 '전달된 신호가 다음 회차에 다시 나갔다' | 다음 회차 억제 · 전달 필드 · `sent_today` 바름 | DONE |
| ⑬-b K2 잘림 회차 + 첫 저장만 실패(독립 검토 B-5) | `test_k2_cut_tick_first_save_fails_keeps_cut_reentry_pending` | 실패 :86(`_k2_prefix` 의 `sent_today == 2` — 변경 전에는 대신 저장이 없음) | `intraday_state_saved_by_observation=True` · 잘린 재진입 행 `(AC, False)` · 실린 3건 전달 필드 = 이번 회차 · `sent_today` 2(한 번) → 다음 회차 재진입 발송(`sent_today` 3) → 그다음 억제 | DONE |
| ⑭ 다음 회차 정책 대기가 늘어 미충족(보완 2) | `test_policy_cooldown_change_turns_cut_reentry_into_k3` | 실패 :573(잘린 회차 행이 `True` — K2 전제 단언) | 그 회차 억제 → `True` → 대기를 채운 뒤에도 지속 억제(K3 전환) | DONE |
| r1-①(검증자 F1 재현 표 그대로) 3회 발송 → 4번째 전송 성공 · 첫 쓰기만 실패 → 대신 저장의 다시 읽기만 실패 → 다음 회차 | `test_r1_f1_fallback_reload_unreadable_keeps_history_and_daily_cap` | 실패 :639 '일일 발송 수를 잃었다'(main 0 · r1 제출본 1 ≠ 4) | `sent_today` 4 · 앞선 3건 전달 기록 그대로 · 4번째 전달 = 이번 회차 · 다음 회차 일일 상한(본문 없음 · 보낸 수 그대로) · `intraday_state_saved_by_observation` · `intraday_observation_base=snapshot` | DONE |
| r1-② 같은 원인(기존 경로) · 첫 저장 성공 뒤 매 회차 관측 저장의 다시 읽기만 실패 | `test_r1_observation_reload_unreadable_after_first_save_keeps_history` | 실패 :639(0 ≠ 4) | 첫 저장이 방금 쓴 상태 위에 관측을 씀 → r1-① 과 같은 결과 · `intraday_observation_base=snapshot` | DONE |
| r1-③ 같은 원인 · 보내지 않은 회차(지속 억제)의 관측 저장 다시 읽기만 실패 | `test_r1_observation_reload_unreadable_on_quiet_tick_keeps_history` | 실패 :709 '같은 신호가 다시 나갔다' | 그 회차 · 다음 회차 억제 · 전달 기록 · `sent_today` 그대로 | DONE |
| r1-④ 같은 원인(기존 경로) · 러너 첫 저장의 다시 읽기만 실패 | `test_r1_first_save_reload_unreadable_uses_assembly_state` | 실패 :639(1 ≠ 4) | 조립 때 상태 위에 병합 · `intraday_sent_today` 4 · `intraday_state_save_base=snapshot` → r1-① 과 같은 결과 | DONE |
| r1-⑤ 조립 때도 못 읽은 손상 파일(복구 동작 그대로) | `test_r1_corrupt_state_file_is_rewritten_as_before` | 실패 :749(진단 키만 · 동작은 변경 전과 같음) | 비교 불가 → 전부 신규로 발송 → 첫 저장이 새로 써서 복구 · 다음 회차 억제 · `intraday_state_save_base=unreadable` | DONE |
| r1-⑥ B-1 재시도도 같은 기준 · 대신 저장 병합 실패 + 다시 읽기 실패 | `test_r1_fallback_merge_fails_and_reload_unreadable_keeps_history` | 실패 :780 '앞선 전달 기록을 잃었다' | 조립 때 상태 위에 관측만 씀 · 앞선 전달 기록 · `sent_today` 그대로 · 성공 사실은 못 남겨 재진입만 한 번 더 나감(§5-5 · 다른 신호는 안 나감) | DONE |
| 단위 | `_apply_observation` 10행 × 두 저장 경로(20) · 전달된 후보 행(1) · `send_candidates` 합집합(1) · 대신 저장 한 번만(1) · 빈 `sent`(1) · 대신 저장 병합 실패 → 관측만(1 · B-1) · 모두 실패해야 예외(1 · B-1) · `apply_intraday_records` 탐침 재현(1 · B-1) · 대신 저장 조건 6행(6) = 33건 | 33건 모두 실패(새 인자 · helper · 반환값 없음 TypeError · ImportError · 진단 키 없음 · 조건 단위) | 33건 통과 | DONE |
| 단위(r1 F1) | `load_merge_base` 8행(다시 읽기 정상 · 없음 · 날짜 바뀜 · 형식 다름 = 예전 규칙 · 읽기 실패 + 아는 상태 있음 = 그 상태 · 아는 상태 없음 · 비교 불가 · 다른 날 = `unreadable`) · `apply_intraday_records` 가 pending `state_snapshot` 을 기준으로 씀(1) = 9건 | 9건 모두 실패(main · r1 제출본 모두 `load_merge_base` 없음 · 진단 키 없음) | 9건 통과 | DONE |

- 새 시험 건수 = 시나리오 22(①~⑮ 19 + ⑫-b 2 + ⑬-b 1) + r1 시나리오 6 + 단위 33 + r1 단위 9 = **70**(`--junit-xml` 시험 수 실측).
- r1 시나리오의 읽기 실패 주입 = `pathlib.Path.read_text` 를 그 상태 파일에 한해 감싸 지정 함수(`save_observation` · `_save_intraday_state_after_send`) 호출 안의 **첫 읽기 한 번**만 OSError 로 만든다(파일은 그대로 · 주입 횟수 `failed == 1` 단언 · 그 함수 호출 1번에만).
- 기존 `tests/test_poc3_02d_ops02_delivery_state.py` 의 행 `(False, ER, ER, True)`(HEAD :662 · 지금 :664)는 값을 그대로 두었다. 끝에 붙어 있던 주석만 바로 위 주석 2줄(:662-663 · '이번 회차 후보 아님(예: 대기 억제) — 예전과 같다' · 후보였는데 미전달이면 False 유지)로 옮겨 좁혔다. 기존 시험 기대값 변경은 0건이다(PLAN §3 '바꿀 기존 기대값 0건').
- 기존 시험 틀의 '다음 틱 대기' 정의(같은 상태 재진입을 대기로 보지 않음 · PLAN §1-5 맹점)는 새 시험에서 쓰지 않았다.

### 1-3. 설계자 PLAN 판정 보완 · Q 대조

| 항목 | 상태 | 근거 |
|---|---|---|
| 보완 1 · Q3 성공 전달 우선 | DONE | §1-1 '성공 사실 보존' 행 · 시험 ⑩ ⑪ ⑪-b ⑫ ⑫-b ⑬ ⑬-b · 단위 대신 저장 6종. 상태 파일 형식 · 필드 그대로라 '상태 저장 계약 변경'이 필요하지 않았다(중단 조건 해당 없음) |
| 보완 2 · Q5 다음 회차 대기 판정 | DONE | 판정 코드 무변경(`compute_sector_changes`). 시험 ⑥ · ⑨ · ⑭ · ⑮ |
| 보완 3 · Q10 운영 근거 | PARTIAL | PLAN 반영 완료(§4 다시 씀). 반영 전 기준선(PLAN §0-1 · K2 의심 건 0건)은 기록됨. 반영 뒤 첫 정규 장중 회차 확인 · OCI revision 대조 · [원장 새로고침] 전후 대조는 커밋 · OCI pull 뒤에 한다(§5 · §7) |
| 검증자 r1 F1(보완 1 성공 시각 · 발송 수 보존 · Q6 일일 상한) | DONE | §13 · §1-1 '쓰기 기준 상태' 행 · 시험 r1-① ~ ⑥ · 단위 9 · 변이 R1 ~ R15. 형수님 결정 2건(2026-11-20 · §4 · §7) |
| Q1 미전달 원인 범위 | DONE | 구역 한도 · 전송 실패 · 부분 전송 · 발송 전 차단(①②) · 일일 상한(⑧) |
| Q2 대상 신호 | DONE | 사업군 + 보유 급등(③ · `send_candidates` 가 `surge_changes` 포함 · 변이 M5a ~ M5c). 보유 급락은 별도 상태 파일이라 무변경 |
| Q4 정렬 | DONE | 우선권 없음(⑦) · 정렬 코드 무변경 |
| Q6 일일 상한 | DONE | ⑧ · 원장 처분 `cut_by_daily_cap` |
| Q7 이관 · 반영 시각 | DONE(이관 없음) | 이관 코드 없음 · 반영 시각은 §7 |
| Q8 문장 갱신 | DONE · 형수님 실화면 확인(2026-11-20) | 화면 문장 · PROGRAM_TRUTH · 모듈 독스트링. 종료된 POC6-34 결과서는 손대지 않음 |
| Q9 원장 버전 | DONE | `holdings_risk_alert.v1` 유지 · 원장 코드 diff 0. 처분 · 노출 해석 메모는 §6(I4) |
| Q11 알림 증가 | DONE(수용 · 한도 무변경) | PROGRAM_TRUTH §9 문단 끝 문장 · §7 안내 |

## 2. 변경된 파일 목록

### 격리 작업 사본(기준 main `631b14a9` 대비 · 줄 수 = `git show HEAD:<경로> | wc -l` → `wc -l` 실측 · 2026-11-20)

`git status --short --untracked-files=all` 실측 = 'M ' 8 · 'A ' 1 · '??' 0(경로별 stage · `git diff --cached --stat` = 9 files changed, 1520 insertions(+), 63 deletions(-) · 줄 수 · numstat 은 stage 내용과 같음).

| 파일 | git | 줄 수(전 → 후) | `git diff --cached --numstat`(+/−) | 내용 |
|---|---|---|---|---|
| `app/runtime_evidence/sector_signal_state.py` | 'M ' 수정 | 427 → 580 | +185 / −32 | 후보 helper · 회복 유지 판정 · 두 저장 `candidates` · 대신 저장 · 대신 저장 실패 시 관측만 다시 쓰기 · 쓰기 기준 `load_merge_base`(r1 F1) · 반환값 3칸 |
| `app/three_push_runtime/runner_evidence.py` | 'M ' 수정 | 275 → 303 | +48 / −20 | 첫 저장에 후보 집합 전달 · 쓰기 기준(조립 때 상태) · 진단 `intraday_state_save_base` · 쓴 뒤 pending `state_snapshot` 교체(r1 F1) |
| `app/runtime_evidence/holdings_risk_flow.py` | 'M ' 수정 | 569 → 599 | +32 / −2 | pending `candidates` · `sent_signals` · `state_snapshot`(r1 F1) · 대신 저장 조건 · 진단 키 세 개 |
| `app/runtime_evidence/intraday_alert_flow.py` | 'M ' 수정 | 592 → 594 | +3 / −1 | 결과 칸 `previous` · 판정에 쓴 상태를 남기는 대입(r1 F1 · 판정 무변경 · PLAN §2 '변경 없음'과 다름 · 형수님 결정) |
| `tests/test_poc3_02d_ops02_delivery_state.py` | 'M ' 수정 | 987 → 989 | +3 / −1 | 행 :664(HEAD :662)의 주석만(값 그대로) |
| `tests/test_poc6_35_reentry_delivery.py` | 'A ' 신규 | — → 1182 | +1182 / −0 | 시나리오 22 + r1 시나리오 6 + 단위 33 + r1 단위 9 = 70건 |
| `frontend/app/components/approval/intradayCriteria.ts` | 'M ' 수정 | 469 → 470 | +2 / −1 | Q8 문장 · 출처 주석 1줄 |
| `frontend/app/components/approval/intradayCriteria.test.ts` | 'M ' 수정 | 550 → 551 | +2 / −1 | Q8 기대 문장 · 출처 주석 1줄 |
| `docs/PROGRAM_TRUTH.md` | 'M ' 수정 | 1305 → 1363 | +63 / −5 | §1-1 '문서' 행 자리 |

### main 저장소(문서 · 커밋 전)

| 파일 | git(실측) | 비고 |
|---|---|---|
| `docs/ai_result/POC6/POC6_35_INTRADAY_REENTRY_ALERT_DELIVERY_RESULT.md` | 'A ' 신규(이 문서) | 통합 단계에서 만들고 독립 검토 처리 · r1 F1 정정에서 고침(§12 는 검증자가 씀) |
| `docs/ai_plan/POC6/POC6_35_INTRADAY_REENTRY_ALERT_DELIVERY_PLAN_V1.md` | 'A ' 신규 | 독립 검토 처리에서 두 곳만 고침 — Q11 집계 문구('중복 억제 {n}건' · B-4) · §7-5(성공 사실이 남지 않는 세 경우 · B-1 · B-2). r1 F1 정정에서는 §7-5 안의 작업 사본 줄 번호 한 곳만 지금 줄(`runner_evidence.py:226-227`)로 고쳤다(r1 정정 검토 RA-3 · 개발자가 넣었던 주석). PLAN 과 다른 점은 이 결과서 §4 · §7 |
| `docs/ai_design/POC6/POC6_35_INTRADAY_REENTRY_ALERT_DELIVERY_DESIGN_V1_2026-11-19.md` | 'A ' 신규 | 설계자 문서 · 안 고침 |
| `docs/ai_design/POC6/POC6_35_INTRADAY_REENTRY_ALERT_DELIVERY_PLAN_DECISION_2026-11-19.md` | 'A ' 신규 | 설계자 문서 · 안 고침 |
| `docs/STATE_LATEST.md` | 'M ' 수정 | POC6-34 CLOSED · 메뉴 정리 · POC6-35 진행 칸 |

- 형수님 소유 `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 도 '??' 그대로다(손대지 않음).
- 격리 사본 PROGRAM_TRUTH 머리 줄은 위 설계서 · 판정 · PLAN · 이 결과서 경로를 적는다. 이 파일들은 main 저장소에만 있어, 합칠 때 함께 커밋돼야 경로가 맞는다.

## 3. 신규 추가된 의존성

- 없음

## 4. 지시문 외 변경

- **시험 ⑪-b 추가(BE 갈래):** PLAN §3 표에 없는 경우(첫 저장은 실제로 써졌고 표식만 없음)다. 보완 1 '같은 회차를 한 번만 반영'의 시각 확인 장치를 직접 잡으려고 더했다.
- **변이 M9 추가(BE 갈래):** PLAN §3 변이 목록에 없던 '후보 비교가 종목만 보고 상태를 무시'를 더했다(잡힘).
- **새 진단 키 `intraday_state_saved_by_observation`:** 보완 1 의 대신 저장이 일어난 회차를 실행 기록에서 구별하려고 더했다. 실행 기록 JSONL(`runner_record.py` 의 `json.dumps(record)`)에만 남는다. DB 실행 상태 표는 정해진 열만 쓰므로(`app/runtime_execution_status_store.py :: insert_status_from_record`) 표 · 스키마 영향이 없다. 원장도 실행 기록 전체를 저장하지 않는다(`ledger_context._json` 은 tags 만).
- **독립 검토 처리(§11)로 바뀐 것:** `save_observation` 반환값(None → `(쓴 것, 대신 저장 예외 형)`) · 새 진단 키 `intraday_state_save_fallback_error`(위 키와 같은 실행 기록 JSONL 에만) · 시험 6건 추가(⑫-b 2 · ⑬-b 1 · 단위 3) · ⑫ 시험 강화(쓰기 3번 실패 주입 · 다음 두 회차 단언) · `_k2_prefix` 에 잘림 회차 직전 훅 인자. 검토 처리 지시에 없던 것은 다음 셋이다.
  - 변이 M12(대신 저장 실패 진단 키 누락) · M13(`intraday_state_saved_by_observation` 을 쓴 결과 대신 조건으로 판정) 추가 — 실행 기록 진단이 실제와 맞는지(지시 '진단이 바른지')를 잠그려고 더했다(둘 다 잡힘).
  - 기존 단위 시험 3곳에 반환값 단언 추가(관측만 · 대신 저장 · 빈 `sent`).
  - PROGRAM_TRUTH 머리 줄 상태 문구 '독립 검토 · 검증자 · 설계자 RESULT 전' → '독립 검토 1회 반영 · 검증자 · 설계자 RESULT 전'(낡은 문구 교체).
- **출처 주석 1줄씩(FE 갈래):** `intradayCriteria.ts` · `.test.ts` 에 'POC6-35 PLAN 판정 Q8(2026-11-19)' 주석을 달았다. 같은 파일의 기존 '설계자 RESULT 판정' 주석 관례를 따랐고 동작 영향은 없다.
- **PROGRAM_TRUTH 부록 A 새 줄 1개(통합):** `runner_evidence :: _save_intraday_state_after_send` 줄을 더했다. 이 함수가 후보 집합을 넘기는 첫 저장 경로라서, 모듈 표 갱신과 같은 범위로 적었다.
- **통합 시험 범위 확대:** BE 갈래가 고른 17파일에 러너 전체 실행(`scripts/run_three_push_runtime_oci.run`)을 쓰는 시험(`tests/runtime_evidence/` 전체 · `tests/low_frequency_push/` 전체 · `test_runtime_runner_dry_run` · `_partial_delivery` · `_spike_no_signal` · `test_market_briefing_flow_through` · `test_oci_market_data_refresh`)을 더해 37파일로 돌렸다(§9). r1 F1 정정에서는 조립 모듈을 쓰는 `test_poc6_34_intraday_config_state` 를 더해 38파일이다.
- **검증자 r1 F1 정정에서 PLAN 과 다르게 한 것 · 넓힌 것(형수님 결정 2026-11-20 · §7):**
  - **`intraday_alert_flow.py` 변경(PLAN §1-7 KS-10 표 '592 → 고치지 않음' · §2 '조립 · 변경 없음' · Q3 '`intraday_alert_flow.py` 무변경'과 다름):** 결과 칸 `IntradayAssembly.previous` 와 판정에 쓴 상태를 남기는 대입(+3 / −1 · 592 → 594 · 판정 코드 무변경). 조립 때 읽은 상태를 저장 쪽에 넘길 다른 길이 없다. 저장 쪽에서 따로 다시 읽으면 그 읽기도 실패할 수 있고, 판정에 쓴 상태와 다를 수 있다. 형수님 결정 = '2줄 추가 · PLAN 차이 명시'.
  - **같은 원인의 기존 두 경로도 고침:** 러너 첫 저장(`runner_evidence`)과 매 회차 관측 저장(`save_observation` 의 관측만 쓰기)은 POC6-35 전부터 다시 읽기 실패를 빈 상태로 보고 덮어썼다(시험 r1-② ③ ④ 가 main 에서 실패 · §8-1). 검증자가 지적한 대신 저장과 같은 함수(`load_merge_base`)를 쓰게 했다. 형수님 결정 = '세 경로 함께 고침'.
  - **새 진단 키 2개:** `intraday_state_save_base` · `intraday_observation_base`. 다른 진단 키처럼 실행 기록 JSONL 에만 남고, DB 실행 상태 표 · 원장 영향은 없다.
  - **새 공개 함수 · pending 키 · 결과 칸:** 새 공개 함수 `load_merge_base`(`__all__` 에 추가), pending 새 키 `state_snapshot`, 결과 칸 `IntradayAssembly.previous` 를 더했다. pending 은 기존 계약대로 직렬화 전에 꺼내 지워 JSON 에 나가지 않는다.
  - **반환값 3칸:** `save_observation` 반환을 `(쓴 것, 대신 저장 예외 형, 기준 진단)` 로 바꿨다. 호출은 `holdings_risk_flow.py` 한 곳이다. 반환값을 비교하는 기존 단위 시험 5곳의 기대값도 3칸으로 고쳤다(새 시험 파일 안).
  - **변이 R1 ~ R15 추가:** 지난 변이 17건도 바뀐 코드에서 다시 돌렸다(§10).

## 5. 알려진 한계 / 미완성

1. **운영 확인 미착수(보완 3 · PLAN §4):** 커밋 · main 반영 · push · OCI pull 전이다. 반영 뒤 첫 정규 장중 회차의 처리 결과 · OCI revision · [원장 새로고침] 전후 대조 · K2 의심 건 질의는 그때 한다. 고정 사례 검증(§8 RED → GREEN)과 실제 운영의 K2 발생 유무는 따로 기록한다. 반영 전 31거래일 기준선은 K2 의심 건 0건이다(PLAN §0-1).
2. **실제 Telegram · OCI 관통 없음:** 시험은 기존 rig 로 러너 `run()` 전체(조립 · 금지 문구 검사 · 전송 대역 · 상태 · 집계 저장)를 지나지만, 실제 Telegram · OCI 는 거치지 않는다(PLAN §7-1 의 '`run()` 전체 관통 아직'은 rig 로 해소).
3. **반영 전에 굳은 행(PLAN §7-3 · Q7):** 반영 전에 이미 지속 억제로 저장된 행은 그날 복구되지 않는다(회복 · 재진입하거나 다음 날 초기화될 때까지).
4. **15:20 회차에 잘린 재진입(PLAN §7-4):** 그날 다음 회차가 없다. 다음 날은 날짜 초기화로 모두 신규다.
5. **성공 사실이 남지 않는 경우(PLAN §7-5):**
   - **대신 저장까지 실패(B-1):** 관측만 다시 써서 이번 회차 관측 · 회복 기록은 남지만 전달 필드 · `sent_today` 는 그대로다. 실측(⑫-b · 사업군 재진입): 다음 회차에 같은 재진입이 한 번 더 나가고 `sent_today` 는 발송 회차보다 1 적다.
   - **이번 회차 상태 쓰기가 모두 실패(I1):** 두 진단 키(`intraday_state_save_error` · `intraday_observation_error`) · 상태 파일 바이트 그대로. 실측(⑫): 다음 회차에 같은 재진입이 한 번 더 나가고 `sent_today` 가 2(발송 회차 t+0 · t+120 · t+180 = 3)로 1 적다. ⑫ 는 변경 전 코드에서도 통과한다(§8-1) — 변경 전과 같은 결과다.
   - **Telegram 전송 성공 뒤 `record_send_success` 의 `mark_sent` · `save_risk_state` 예외(B-2 · 변경 전부터 있던 경로 · 회귀 아님):** 러너가 `record_send_success`(`scripts/run_three_push_runtime_oci.py:450`)를 try 없이 부르므로 예외가 `run()` 밖으로 나가고 `return _finish("sent")` 에 닿지 않는다. 그래서 장중 첫 저장 · 관측 저장(대신 저장 포함) · 집계 · 실행 기록 JSONL · 원장 마무리(`led.finalize`)가 모두 없고, 다음 회차에 같은 신호가 다시 나갈 수 있다. 검토 탐침 실측: 두 함수 각각에 OSError 주입 시 `run()` 이 OSError 로 끝나고 상태 파일은 앞 회차 그대로(`sent_today` 1 · 재진입 행 `last_sent_at` = 첫 전달), main 트리도 같다. 이번 범위 밖이다.
   - 장중 신호 없이 보유 급락만 실린 통합 본문 회차(`sent_signals` 빈 목록)는 확인할 행이 없어 '한 번만' 보장이 첫 저장 표식(`intraday_state_saved`)에만 기댄다. 첫 저장의 `save_sector_state` 뒤에는 표식 대입만 있어, 써졌는데 표식만 빠질 가능성은 낮다.
   - 대신 저장 시각은 pending 의 `runtime_kst` 로 만든다. 러너는 늘 같은 `runtime_kst`(`kst_now_iso()`)를 조립과 첫 저장에 넘기지만, 비어 있으면 현재 시각이 되어 시각 확인 장치가 안 맞고 표식만으로 판정한다. 날짜는 pending `today_kst` 이고 첫 저장은 `runtime_date_kst` 를 쓴다. 장중 회차(09:30 ~ 15:20)에서는 같은 날이다.
6. **대신 저장 회차의 발송 수 진단(B-6):** 발송 회차의 실행 기록 `intraday_sent_today` 는 첫 저장(`runner_evidence.py:225`)이 쓴다(조립은 본문이 없는 일일 상한 회차에만 그 회차 전 값을 남긴다 · `intraday_alert_flow.py:535` → `runner_dispatch.py:103`). 대신 저장 회차 · 대신 저장 실패 회차에는 이 키가 없으므로, 운영 확인 때 그날 발송 수는 상태 파일(`sector_signal_state_latest.json`)의 `sent_today` 로 읽는다.
7. **수동 실행 끼어들기(PLAN §7-6):** 수동 실행이 조립과 저장 사이에 끼면 후보 집합이 어긋날 수 있다(기존 위험과 같은 성격).
8. **쓰기 기준 상태(r1 F1)가 다루는 범위:**
   - **읽기 실패일 때만 적용:** 이번 회차가 아는 상태로 바꿔 쓰는 것은 쓰기 직전 다시 읽기가 '읽기 실패'(`unreadable` · 파일은 있는데 읽지 못함 · JSON 손상)일 때뿐이다. 회차 중에 파일이 사라지거나(없음) 다른 날짜 · 형식으로 바뀌면 예전처럼 그 결과를 따른다.
   - **조립 때도 못 읽은 경우:** 손상 · 권한 문제로 조립 때도 못 읽었으면 기준으로 쓸 상태가 없다. 예전처럼 비교 불가(전부 신규 · 일일 상한을 0부터 셈)로 판정하고 빈 상태 위에 새로 쓴다(OPS-02 '비교 불가면 전부 신규' 그대로 · 시험 r1-⑤). 쓰기는 되는데 읽기가 계속 실패하는 파일이면 매 회차 이 상태가 이어진다(변경 전과 같음).
   - **조립 때 읽기만 한 번 실패한 경우:** 쓰기 직전 다시 읽기는 되더라도, 그 회차의 판정은 OPS-02 계약대로 비교 불가(전부 신규)다. 그래서 이미 보낸 신호도 다시 보내고, 일일 상한을 0부터 세어 4건을 넘길 수 있다. 첫 저장은 다시 읽은 실제 상태 위에 병합하므로, 앞선 기록은 남고 `sent_today` 는 실제 발송 수대로 늘어난다. 변경 전과 같은 동작이고, 판정 쪽 계약('조용한 억제로 대체하지 않는다')이라 이번 범위 밖이다(검토 탐침 실측: 5번째 회차 발송 · `sent_today` 5 · 그다음 회차 일일 상한).
   - **다른 실행이 끼어든 경우:** 조립과 저장 사이에 다른 실행(수동 실행)이 상태 파일을 고쳤고, 그 뒤 다시 읽기까지 실패하면 이번 회차가 아는 상태 위에 쓴다. 그 실행의 기록을 덮을 수 있다(7 과 같은 성격).
   - **대신 저장이 아는 상태로 쓴 경우:** 첫 저장이 실제로는 써졌는지 확인할 수 없다(다시 읽지 못함). 그래도 같은 기준(조립 때 상태)에 같은 인자(실린 신호 · 관측 · 평가 불가 · 후보 · 회차 시각)로 같은 병합을 하므로, 결과(`sent_today` = 이번 회차 전 값 + 1 · 같은 전달 필드)는 첫 저장이 쓴 것과 같다.
   - **확인하지 않은 범위:** 형식은 맞는데 값이 손상된 파일(예: `sent_today` 가 숫자가 아님)은 `load_sector_state` 의 `int()` 가 예외를 내는 기존 경로다. 읽기 실패 판정 · 쓰기 기준 규칙과 다른 경로라 이번에 시험하지 않았다.
9. **전체 백엔드 회귀:** PLAN §3 대로 커밋 전 1회만 돌렸다(설계자 RESULT PASS 뒤 · 통과 · §15). 정정 라운드마다 돌리지는 않았다.
10. **PROGRAM_TRUTH 표시:** main 반영 때 '`POC6-35`(반영 대기 · 격리 사본)' 표시 10곳과 머리 줄을 'main 반영 2026-11-20 · OCI 반영 대기'로 바꿨다(§15). OCI pull · 운영 확인 뒤 다시 반영 사실로 바꾼다.

## 6. 다음 검증자(Codex)에게 알릴 점

- **후보 집합의 뜻:** `send_candidates` = `compute_sector_changes` 결과(사업군 `changes` · 보유 급등 `surge_changes`)의 `send` 합집합이다. 구역 · 일일 상한과 전송 결과와 무관하다. 그래서 일일 상한 회차의 재진입도 후보로 남아 회복 기록이 유지된다(Q6 · ⑧). 비교는 `(종목, 상태)` 쌍이다(변이 M9 로 잠금).
- **두 저장 경로가 같은 집합:** 첫 저장(`runner_evidence.py:185`)과 관측 저장 pending(`holdings_risk_flow.py:412`)이 같은 조립 결과에서 집합을 만든다. 한쪽만 넘기면 잡힌다(r1 정정 뒤 다시 잰 값: M1a 19건 · M1b 6건 실패). 대신 저장 병합도 같은 집합을 받는다(`sector_signal_state.py:506` · M11 이 ⑬-b 와 단위 '한 번만' 2건으로 잡힘).
- **r1 F1 · 기준 선택 규칙(`load_merge_base` · `sector_signal_state.py:224`):** 다시 읽기 결과가 `unreadable` 일 때만 아는 상태를 본다. 없음 · 날짜 바뀜 · 형식 다름은 예전 규칙 그대로다(R2 로 잠금). 다시 읽기가 정상이면 아는 상태가 있어도 읽은 값을 쓴다(R5). 아는 상태는 비교 가능(R4)하고 날짜가 같아야(R3) 쓴다. 날짜 비교는 `load_sector_state` 처럼 둘 다 있을 때만 한다.
- **r1 F1 · 아는 상태의 출처와 순서:** 처음 값은 조립 때 읽은 상태다(`IntradayAssembly.previous` · `holdings_risk_flow.py:413` → pending `state_snapshot`). 러너 첫 저장이 쓰기에 **성공한 뒤에만** pending 값을 방금 쓴 상태로 바꾼다(`runner_evidence.py:201-209`). 그래서 첫 저장 뒤 관측 저장의 다시 읽기가 실패해도 조립 때(발송 전) 상태로 되돌아가지 않는다(R7 · R8 로 잠금). 첫 저장이 실패하면 pending 값은 조립 때 상태로 남고, 대신 저장이 그 위에 +1 한다.
- **r1 F1 · 기존 두 경로를 넓힌 이유:** 같은 원인이 POC6-35 전부터 첫 저장 · 매 회차 관측 저장에 있었다. main 에서 시험 r1-② ③ ④ 가 실패한다(§8-1). 매 회차 관측 저장은 발송이 없는 회차에도 돌아 F1 보다 더 자주 닿는다. 형수님 결정(2026-11-20)으로 세 경로를 함께 고쳤다(§4).
- **대신 저장 조건의 판정 순서:** `apply_intraday_records` 는 기존 출구(dry-run · `BLOCKED_RECORD_REASONS`) 뒤에서만 대신 저장 조건을 본다. 조건 4개(통합 본문 회차 · `sent` · 부분 전송 아님 · 첫 저장 표식 없음)는 단위 6행으로 잠갔다(M6 · M8a · M8b 잡힘). `failed`(전송 실패 · 발송 전 차단)는 기존처럼 관측만 쓴다.
- **대신 저장 실패 처리(B-1)의 위치:** 재시도는 `save_observation` 안에 있다(`holdings_risk_flow.py` 를 600줄 아래로 두려고 · KS-10). `save_observation` 은 아무것도 쓰지 못했을 때만 예외를 낸다. 관측만 다시 쓸 때 `sent_today` 는 올리지 않는다(+1 은 병합 쪽 저장 인자 안에서만 계산 · 단위 단언). r1 정정 뒤 다시 잰 값으로, 재시도를 빼면(M10) 6건 · 진단 키 누락(M12) 4건 · 표식을 쓴 결과 대신 조건으로 판정(M13) 3건이 잡힌다(§10-1).
- **B-1 시험의 RED 해석:** ⑫-b 는 변경 전 코드에서 대신 저장 자체가 없어 진단 키 단언(:499)에서 실패한다(변경 전에는 관측만 쓰는 저장이 늘 돌았으므로 관측은 남았다). '대신 저장 병합 실패가 관측을 지운다'는 B-1 이전 코드의 결함은 변이 M10(재시도 빠짐)으로 재현 · 확인했다.
- **I4 · Q9 처분 집계 해석:** 원장 `apply_transitions` 는 처분 `sent` · `suppressed` · `cut_by_section_cap` · `cut_by_daily_cap` 행에 전이를 매긴다. 직전 평가 상태가 같으면 `repeat_exposure` · 노출 `SECONDARY` 다(`ledger_items.py:439` · `:488-489`). 그래서 K2 정정 뒤 잘린 재진입이 다음 회차에 나가면, 첫 노출은 잘린 회차의 행에 남고 실제 발송 회차의 행은 `repeat_exposure` · `SECONDARY` 다. 반영 뒤 '재진입 발송' 을 원장으로 셀 때는 노출 · event_type 이 아니라 처분 `sent` 와 실행 기록 `delivery` 로 본다. 이 내용은 코드 읽기로 확인했고 시험 단언은 없다.
- **B-6:** 대신 저장 회차에는 실행 기록 `intraday_sent_today` 가 없다(§5-6). 운영 확인 질의는 상태 파일 `sent_today` 로 한다.
- **RED 중 동작 변경이 아닌 것:** ⑭ 의 RED 는 '잘린 회차 행이 `True`'라는 K2 전제 단언 때문이고, 그 뒤 K3 지속 억제 부분은 변경 전후 같다. ⑪-b 의 RED 는 진단 키 차이뿐이다(변경 전에도 `sent_today` 는 맞았다). ⑬-b 의 RED(:86)는 보완 1 이 없어 `sent_today` 가 1 인 것이다.
- **⑧ 원장 처분:** `ledger_items.risk_items(SimpleNamespace(outcome=None, intraday_eval=res), intraday_isolated=False)` 로 메모리에서 계산해 단언했다. 원장 DB · 러너 원장 경로는 거치지 않는다.
- **KS-10:**
  - `holdings_risk_flow.py` 599줄이다. 근접선 600 아래 1줄이고 트리거는 650이다. 이번에 넣은 설명 줄을 줄여 600 아래로 맞췄다.
  - `intraday_alert_flow.py` 594줄이다(+2).
  - `sector_signal_state.py` 는 427 → 580(+153)이다. 같은 파일에 후보 helper · 대신 저장 분기(재시도 포함) · 쓰기 기준 함수가 더해졌다. 같은 '상태 저장' 책임 안이라고 봤지만, 트리거 5 '같은 대형 파일에 신규 책임' 해당 여부는 검증자가 판단한다.
  - `runner_evidence.py` 303줄이다. 새 시험은 새 파일 1,182줄로 시험 파일 상한 1,500 아래다.
- **화면 시험 범위:** '구역별 최대' 문장 전체를 단언하는 곳은 `intradayCriteria.test.ts` 한 곳이다(`toEqual`). `IntradayConfigCard.test.tsx` 는 그 행 앞 문장만 `toContain` 으로 본다.
- **[live-db-copy] 한 줄:** 통합 실행 38파일(r1 정정 뒤 · 이전 37파일 때도 같음) 출력 끝에 기존 호환 목록 시험이 만든 세션 사본 검사 줄이 나왔다(복사 전후 · 사본 sha256 같음 · integrity ok). 새 시험 단독 실행에는 이 줄이 없다(라이브 DB 미사용).
- **RED 재측정 방법:** 두 기준 코드를 scratchpad 새 폴더에 풀었다(frontend · docs · archive 제외).
  - POC6-35 전 main = `git archive HEAD`.
  - r1 제출본 = 정정 전 index 를 `git checkout-index -a --prefix=`.
  - 각 폴더에 최종 시험 파일을 넣고(`cmp` 로 바이트 같음 확인) 잰 뒤, `--junit-xml` 로 시험별 결과 · 실패 줄을 셌다(§8-1).
- **변이 실행 위치:** 작업 사본이 아니라 작업 사본의 복사본(app · tests · scripts · legacy · setup.cfg)에서 돌렸다. 격리 서버 8001 이 작업 사본 `app/` 을 보고 있어서다.
  - 기준 실행의 실패 8건은 `test_intraday_alert_flow_through.py` 의 시장 DB 상대 경로 시험이다(I5 와 같은 환경 원인 · 작업 사본에서는 통과). 이 8건은 잡힘 판정에서 뺐다(기준보다 새로 실패한 시험만 셈).
  - 끝난 뒤 복사본의 네 소스가 작업 사본과 바이트가 같은지 단언했다(§10).

## 7. 사용자 확인이 필요한 항목

- **Q8 화면 문장 실화면 확인(형수님 · 2026-11-20 확인 완료):** 격리 화면 3001 「OCI 운영·적용」 ② '장중 급등락 설정' 판정 기준 표의 '구역별 최대' 행 '이 값의 뜻' 마지막 문장. 새 문장 = '보유 급락, 아직 알린 적 없는 신호, 마지막 알림과 상태가 다른 신호, 구역 한도에 밀린 재진입 신호는 다음 회차의 조건과 발송 한도에 따라 다시 검토합니다.' 개발자가 3001 화면을 1440 · 600 폭으로 캡처(그 행 넘침 없음)해 띄워 드렸고, 형수님이 '네 확인했습니다'로 확인했다. 화면 문장은 독립 검토 처리에서 바뀌지 않았다.
- **[원장 새로고침]:** 설계 '먼저' 항목용 새로고침은 형수님이 2026-11-20 00:02 에 실행했고, 결과는 PLAN §0-1 에 기록됐다(OCI 최신 기록과 PC 반영이 맞음 → 운영 점검으로 종료). 남은 것은 **반영 뒤** 운영 확인용 새로고침이다 — 반영 뒤 첫 정규 장중 회차가 끝난 다음 형수님이 [원장 새로고침]을 누르면, 개발자가 전후 시각과 같은 `event_id` 로 대조한다(PLAN §4-4).
- **OCI pull 시각:** 커밋 · main 반영 · push 는 각각 승인을 받는다. OCI pull 은 형수님이 15:20 회차가 끝난 뒤나 비거래일에 한다. 08:05 ~ 08:35 는 피한다. 재기동은 필요 없다(cron 이 회차마다 새 프로세스).
- **알림이 늘 수 있음(Q11 · 판정 수용):** 다시 나가는 재진입 때문에 일일 4건 상한에 더 일찍 닿을 수 있고, 닿은 뒤에는 보유 급락 알림도 막힐 수 있다. 15:40 요약의 '중복 억제 {n}건' 집계(`intraday_alert_render.py:295`)도 줄 수 있다. 한도 · 대기 · 임계값 · 회차 일정은 그대로다.
- **반영 당일 이미 굳은 행(Q7):** 옮기지 않는다. 그날은 기존 규칙대로 남는다.
- **상태 저장 장애 때 한 번 더 나갈 수 있음(§5-5):** 대신 저장까지 실패하거나 상태 쓰기가 모두 실패한 회차, 또는 전송 성공 뒤 발송 기록 함수가 예외를 낸 회차는 다음 회차에 같은 알림이 한 번 더 나갈 수 있다. 앞의 둘은 변경 전과 같은 결과이고, 마지막은 변경 전부터 있던 경로다. 쓰기 직전 다시 읽기를 한 번 못 읽은 회차(검증자 r1 F1)는 이제 이 목록에 들지 않는다(§13). 조립 때 읽기를 한 번 못 읽은 회차는 다르다. 예전처럼 비교 불가(전부 신규)로 보고, 이미 보낸 신호도 다시 보내며 일일 상한을 0부터 센다(§5-8 · OPS-02 계약 · 변경 전과 같음).
- **검증자 r1 F1 정정의 형수님 결정 2건(2026-11-20 · 질문 창 답변):**
  - '2줄 추가 · PLAN 차이 명시' — 확정 PLAN 이 '변경 없음'으로 적은 `intraday_alert_flow.py` 에 결과 칸 1개와 대입을 더함(592 → 594 · 판정 코드 그대로). 검증자 · 설계자가 이 차이를 판정한다.
  - '세 경로 함께 고침' — POC6-35 전부터 같은 원인이 있던 러너 첫 저장 · 매 회차 관측 저장도 같은 규칙으로 고침(§4).

## 8. RED → GREEN 근거

### 8-1. 백엔드 RED(최종 시험 파일 바이트 · 2026-11-20 검증자 r1 F1 정정 뒤 재측정 · 두 기준 코드)

- 방법(작업 사본 파일은 건드리지 않음):
  - **기준 코드 두 벌:** scratchpad 새 폴더 두 곳에 풀었다(`frontend` · `docs` · `archive` 제외).
    - POC6-35 전 main = 작업 사본 HEAD(`631b14a9`)를 `git archive HEAD` 로.
    - r1 제출본 = 정정 전 index(검증자 r1 이 본 stage 내용)를 `git checkout-index -a --prefix=` 로.
  - **넣은 시험:** 최종 `tests/test_poc6_35_reentry_delivery.py` 를 두 폴더에 복사했다(`cmp` 로 바이트 같음 확인).
  - **실행 · 집계:** 각 폴더에서 `PYTHONDONTWRITEBYTECODE=1 …/python -m pytest tests/test_poc6_35_reentry_delivery.py -q -p no:cacheprovider -p no:logging --junit-xml=…` 를 돌리고, XML 에서 시험별 결과와 마지막 시험 파일 줄을 셌다.
- **POC6-35 전 main: 65 failed, 5 passed.**
  - 변경 전 통과 5건은 변경 전후가 같아야 하는 것이다(K3 · AC2 · 조건 이탈 · 정상 저장 · 모두 실패).
    - ④ `test_reentry_cut_then_condition_exits_uses_last_successful_delivery`
    - ⑤ `test_ac2_redelivered_reentry_is_not_repeated`
    - ⑥ `test_k3_reentry_within_cooldown_then_continues_is_suppressed`
    - ⑪ `test_first_save_succeeds_observation_save_does_not_recount`
    - ⑫ `test_both_saves_fail_is_a_general_state_save_failure`(다음 회차 한 번 더 나감 · `sent_today` 1 적음 단언 포함)
  - 실패 위치(지금 파일 줄 · 시나리오):
    - :86 ⑬-b(1) · :118 ①(1) · :177 ②(3) · :210 ③(1) · :295 ⑦(1) · :333 ⑧(1) · :355 ⑨ · ⑮(2)
    - :389 ⑩(1) · :425 ⑪-b(1) · :499 ⑫-b(2) · :533 ⑬(2) · :573 ⑭(1)
  - 실패 위치(r1 시나리오 · `sent_today` 0 또는 1 ≠ 4 · 재발송 · 전달 기록 잃음):
    - :639 r1-① ② ④(3) · :709 r1-③(1) · :749 r1-⑤(1 · 진단 키만) · :780 r1-⑥(1)
  - 실패 위치(단위):
    - :849(10 · `merge_sector_entries` 에 `candidates` 없음) · :859(10 · `save_observation` 에 `candidates` 없음)
    - :879(1) · :892(1 · `send_candidates` ImportError) · :924(1 · `now_kst` 없음) · :948(1 · `sent` 없음) · :971(1) · :998(1)
    - :1041(1 · 대신 저장 실패 진단 키 없음) · :1094(1 · 대신 저장 진단 키 없음) · :1097(5 · 관측 경로 K2 영향으로 `continuous` 가 True)
    - :1144(8 · `load_merge_base` 없음) · :1177(1 · 기준 진단 키 없음)
  - 합계 = 65.
- **r1 제출본: 29 failed, 41 passed.**
  - r1 새 시험 15건이 모두 실패했다: :639(3) · :709 · :749 · :780 · :1144(8) · :1177.
    - :639 r1-① 의 값은 `assert 1 == 4` 다. 검증자 재현(발송 수 3 → 1)과 같다.
  - 나머지 14건은 반환값을 비교하는 기존 단위 시험이다. 반환 칸 수 차이만 있다(2칸 ≠ 3칸): :865(10) · :924 · :951 · :979 · :1008.
  - 그 밖의 41건(K2 · 보완 1 · B-1 · K3 · AC2)은 r1 제출본에서도 통과한다.
- PLAN 이 요구한 RED 를 모두 충족한다: K2 ① ② ③ 실패 · 보완 1 ⑩ ⑬ 실패 · K3 / AC2 ④ ⑤ ⑥ 통과. r1 F1(r1-①)은 r1 제출본에서 실패하고 정정본에서 통과한다.

### 8-2. 백엔드 GREEN(최종 코드 · 작업 사본)

- 새 시험 단독: **70 passed**(1 warning = Starlette 안내).
- 통합 관련 38파일: **677 passed, 1 warning**(§9).

### 8-3. 화면 RED → GREEN(FE 갈래 · 변이로 확인 · 이번 처리에서 화면 파일 무변경)

- 소스를 옛 문장으로 되돌리면(M1) vitest 'Tests 1 failed | 189 passed (190)' · 실패 = `intradayCriteria.test.ts` PLAN_2_3 `max_items_per_section` 행(`toEqual` 로 문장 전체 비교).
- 새 문장: 'Tests 190 passed (190)'(통합 단계 재실행도 같음).

## 9. 검사 결과(검증자 r1 F1 정정 뒤 · 2026-11-20 · 격리 사본 · 최종 바이트)

| 검사 | 결과 |
|---|---|
| `black --check`(r1 에서 바뀐 .py 5개: `sector_signal_state.py` · `runner_evidence.py` · `holdings_risk_flow.py` · `intraday_alert_flow.py` · `test_poc6_35_reentry_delivery.py`) | 5 files would be left unchanged · 종료 0 |
| `flake8` 같은 5개 | 종료 0 · 0건 |
| `py_compile` 같은 5개 | 5개 통과 |
| `pytest` 관련 38파일(`PYTHONDONTWRITEBYTECODE=1` · `-p no:cacheprovider` · `-p no:logging` · 작업 사본에서 실행) | **677 passed, 1 warning** · 19.17s |
| `pytest tests/test_poc6_35_reentry_delivery.py` 단독 | 70 passed, 1 warning |
| 화면 `npx tsc --noEmit` · `npx eslint` 3파일 · `npx vitest run` 2파일 | r1 정정에서 화면 파일 무변경(diff numstat 그대로 · +2/−1 두 파일)이라 다시 돌리지 않음. 통합 단계 결과 = tsc 종료 0 · eslint 0건 · Tests 190 passed(55 + 135) · 검증자 r1 실측도 화면 2파일 190건 통과(§12) |
| 전체 백엔드 회귀 · 전체 vitest | 정정 라운드에서는 안 돌림. 설계자 RESULT PASS 뒤 커밋 전 1회 = 백엔드 6532 passed · 2 skipped · 화면 vitest 100파일 2,261 passed(§15) |

- 38파일 = 아래 37파일 + `test_poc6_34_intraday_config_state`(r1 F1 로 바뀐 `intraday_alert_flow.py` 를 쓰는 시험 · `grep -rlE "intraday_alert_flow|IntradayAssembly|assemble_intraday_alert" tests` 결과 중 37파일 밖이던 1개).
- 37파일 = 새 시험 · `test_poc3_02d_ops02_delivery_state` · `test_intraday_alert_flow_through` · `_render` · `_integration` · `tests/runtime_evidence/`(7) · `test_holdings_risk_alert_runner` · `test_poc3_02d_ops01_holdings_risk_flow` · `test_poc3_02d_ops03_{consumer_isolation, holdings, intraday, price_basis}` · `test_poc5_01b_ledger_items` · `test_poc5_05_empty_holdings_oci` · `universe_bootstrap/test_runtime_universe` · `test_poc3_02d_ops02_regular_push_contract` · `test_poc5_01b_ledger_runner` · `tests/low_frequency_push/`(9) · `test_runtime_runner_dry_run` · `_partial_delivery` · `_spike_no_signal` · `test_market_briefing_flow_through` · `test_oci_market_data_refresh`. 고른 방법 = 바뀐 세 모듈 · 그 함수 · 러너 `run_three_push_runtime_oci` · 기존 rig 를 쓰는 시험 grep 합집합. r1 에서 `save_observation` 반환값을 3칸으로 바꿨으므로 그 호출 · 대체 위치를 다시 grep 했다 — 호출은 `holdings_risk_flow.py:553` 한 곳 · 시험 직접 호출 3파일(`ops03_consumer_isolation` · `ops02_delivery_state` · `ops03_intraday` · 모두 38파일 안 · 반환값 안 씀) · 새 시험 파일 안의 반환값 비교 5곳(3칸으로 고침) · monkeypatch 대체는 새 시험의 읽기 실패 주입 감싸기(`_fail_state_read_in` · 실제 함수를 그대로 부름)뿐.
- 새 시험은 라이브 상태 · DB 를 열지 않는다. 기존 rig(`ops02._Scenario`)가 `DEFAULT_SECTOR_STATE_PATH` · `DEFAULT_TALLY_PATH` 를 tmp 로 바꾼 경로만 쓴다. 38파일 통합 실행에는 기존 호환 목록(`tests/_live_db_legacy_readers.txt`)의 시험이 있다. 이 시험들은 라이브 DB 를 직접 열지 않고, 세션 시작 때 만든 사본을 읽는다(§6 '[live-db-copy] 한 줄' · 사본 sha256 · integrity 확인).

## 10. 변이 확인(최종 바이트 기준 · 백엔드 32 + 화면 3 = 35건 모두 잡힘)

- **방법(r1 F1 정정 뒤 · 2026-11-20):** 작업 사본을 건드리지 않았다. 격리 서버 8001 이 작업 사본 `app/` 을 보고 있어서다.
  - **복사본 준비:** 작업 사본의 app · tests · scripts · legacy · setup.cfg 를 scratchpad 로 복사했다.
  - **기준 실행:** 변이 없이 먼저 돌려 실패 집합을 잡았다. 결과 = 8 failed · 254 passed. 8건은 `test_intraday_alert_flow_through.py` 의 시장 DB 상대 경로 시험이다(I5 · 환경 원인).
  - **변이마다:** 교체 대상 문자열이 정확히 1곳인지 확인했다. 그다음 변이 바이트를 쓰고 → 시험 → 원래 바이트로 복원 → 바이트 일치를 단언했다.
  - **잡힘 판정:** 기준보다 새로 실패한 시험이 1건 이상이면 잡힘이다.
  - **끝난 뒤 확인:** 복사본의 네 소스(`sector_signal_state.py` · `runner_evidence.py` · `holdings_risk_flow.py` · `intraday_alert_flow.py`)가 작업 사본과 바이트가 같은지 단언했다(통과). git stash 는 쓰지 않았다.
- **시험 6파일:** 새 시험 · ops02 delivery_state · flow_through · ops01 holdings_risk_flow · ops03_intraday · intraday_alert_integration(회당 262건).
- **새 실패 건수:** 기준보다 새로 실패한 시험 수다. 지난 표(r1 전 · 4파일)와 건수가 조금 다를 수 있다 — 시험 파일 · 시험 수가 늘었기 때문이다.

### 10-1. 백엔드 — 지난 17건을 r1 정정 코드에서 다시(17 / 17)

| 변이 | 대상 | 결과(새 실패) |
|---|---|---|
| M1a 후보를 전송 성공 저장에만(관측 저장 `candidates` 없음) | `holdings_risk_flow.py` | 잡힘 · 19 |
| M1b 후보를 관측 저장에만(첫 저장 `candidates` 없음) | `runner_evidence.py` | 잡힘 · 6 |
| M2 후보 조건 빠짐(= A5) | `sector_signal_state.py` | 잡힘 · 12(새 시험 10 + ops02 2) |
| M3 회복 조건 빠짐 | `sector_signal_state.py` | 잡힘 · 15 |
| M4 전달 성공 행까지 False(sent 루프) | `sector_signal_state.py` | 잡힘 · 13 |
| M5a 급등 후보 누락(첫 저장 호출부) | `runner_evidence.py` | 잡힘 · 1(③) |
| M5b 급등 후보 누락(관측 저장 pending) | `holdings_risk_flow.py` | 잡힘 · 1(③) |
| M5c helper 가 `surge_changes` 를 빼먹음 | `sector_signal_state.py` | 잡힘 · 2 |
| M6 대신 저장이 첫 저장 표식을 무시 | `holdings_risk_flow.py` | 잡힘 · 5 |
| M7 이번 회차 시각이 이미 있어도 `sent_today` +1 | `sector_signal_state.py` | 잡힘 · 2(⑪-b · 단위) |
| M8a 전송 실패(`failed`) 회차에도 대신 저장 | `holdings_risk_flow.py` | 잡힘 · 10 |
| M8b 부분 전송 회차에도 대신 저장 | `holdings_risk_flow.py` | 잡힘 · 5 |
| M9 후보 비교가 종목만(상태 무시) | `sector_signal_state.py` | 잡힘 · 2 |
| M10(B-1) 재시도 빠짐 — 대신 저장 예외를 그대로 올림 | `sector_signal_state.py` | 잡힘 · 6 |
| M11(B-5) 대신 저장 병합 호출에서 `candidates=` 빠짐 | `sector_signal_state.py` | 잡힘 · 2(⑬-b · 단위 '한 번만') |
| M12(B-1) 대신 저장 실패 진단 키 누락 | `holdings_risk_flow.py` | 잡힘 · 4 |
| M13(B-1) `intraday_state_saved_by_observation` 을 쓴 결과 대신 조건으로 판정 | `holdings_risk_flow.py` | 잡힘 · 3 |

### 10-1-r1. 백엔드 — 검증자 r1 F1 정정 변이(15 / 15)

| 변이 | 대상 | 결과(새 실패) |
|---|---|---|
| R1 다시 읽기 실패에도 아는 상태를 안 씀(= 정정 전) | `sector_signal_state.py` | 잡힘 · 7 |
| R2 읽기 실패 말고도(없음 · 날짜 · 형식) 아는 상태를 씀 | `sector_signal_state.py` | 잡힘 · 3 |
| R3 아는 상태의 날짜 비교 빠짐 | `sector_signal_state.py` | 잡힘 · 1 |
| R4 아는 상태가 비교 불가여도 씀 | `sector_signal_state.py` | 잡힘 · 2 |
| R5 다시 읽기 정상이어도 아는 상태를 씀 | `sector_signal_state.py` | 잡힘 · 7 |
| R6 첫 저장이 조립 때 상태를 안 받음 | `runner_evidence.py` | 잡힘 · 1(r1-④) |
| R7 첫 저장이 쓴 상태를 pending 에 안 남김 | `runner_evidence.py` | 잡힘 · 1(r1-②) |
| R8 첫 저장이 남긴 상태의 발송 수가 1 적음 | `runner_evidence.py` | 잡힘 · 1(r1-②) |
| R9 pending 에 조립 때 상태를 안 넣음 | `holdings_risk_flow.py` | 잡힘 · 3 |
| R10 관측 저장에 아는 상태를 안 넘김 | `holdings_risk_flow.py` | 잡힘 · 5 |
| R11 조립이 판정에 쓴 상태를 결과에 안 남김 | `intraday_alert_flow.py` | 잡힘 · 4 |
| R12 관측 저장 기준 진단 키 누락 | `holdings_risk_flow.py` | 잡힘 · 5 |
| R13 첫 저장 기준 진단 키 누락 | `runner_evidence.py` | 잡힘 · 2 |
| R14 대신 저장 병합만 빈 상태 위에(관측만 다시 쓰기는 그대로) | `sector_signal_state.py` | 잡힘 · 2 |
| R15 관측만 다시 쓰기만 빈 상태 위에(대신 저장 병합은 그대로) | `sector_signal_state.py` | 잡힘 · 3 |

### 10-2. 화면(3 / 3 · vitest 2파일 · 통합 단계 결과 · 독립 검토 처리 · r1 정정에서 화면 파일 무변경)

| 변이 | 결과 |
|---|---|
| M1 마지막 문장을 옛 문장으로 되돌림 | 잡힘 · Tests 1 failed / 189 passed |
| M2 ', 구역 한도에 밀린 재진입 신호' 만 뺌 | 잡힘 · Tests 1 failed / 189 passed |
| M3 뒷부분만 '다음 회차에 다시 후보가 됩니다.'로 되돌림 | 잡힘 · Tests 1 failed / 189 passed |

## 11. 독립 검토(1회 · 두 관점) 처리

| 지적 | 관점 · 등급 | 내용 | 처리 |
|---|---|---|---|
| A 통과 항목(요약) | A · PASS | 검토 하네스(실제 `run()` · tmp 상태 · B-1 처리 전 코드)로 K2 구역 한도 · 미전달 5종(전송 실패 · 묶음 부분 전송 · 부분 전송 표식 · 금지 문구 · raw 식별자) · 보유 급등 재진입 · 조건 이탈 · AC2 · K3 119분(구역 가득 포함) · 두 번 잘림 · 일일 상한 3종 · 평가 불가 · 정책 대기 증감 · 보완 1(첫 저장 실패 2종 · 이중 증가 없음 · 모두 실패 · 관측만 실패 · 신규 · 상태 변화 · 보유 급락만 본문) · 잘림 + 첫 저장 실패 · 급등 잘림 뒤 시세 없음 · 정책 꺼짐 회차를 확인(검토 실행 출력 27 + 5 passed). 검토 원문(A 관점 PASS · 하네스 32건 = 변경 뒤 32/32 · 변경 전 20 실패 · 12 통과 · 개발자 시험 변경 전 44 실패 · 5 통과 재현)과 대조함만 적음 | 조치 없음(같은 범위를 새 시험 ① ~ ⑮ · ⑬-b 가 잠금) |
| B-1 | B · low · FIX | 대신 저장이 관측만 쓰던 저장을 **대체**해, 병합이 늘 실패하는 입력(탐침: `sector_key` 없는 실린 신호 → AttributeError)이면 이번 회차 관측(회복 기록 포함)이 통째로 사라짐 — 변경 전에는 관측만 쓰는 저장이 성공했음 | 고침 — `save_observation` 안에서 대신 저장 예외 시 관측만 쓰는 저장을 한 번 더(`sent_today` 그대로) · 아무것도 못 썼을 때만 예외 · 반환 `(쓴 것, 예외 형)` · 진단 `intraday_state_save_fallback_error` · `intraday_observation_saved` 는 실제로 쓴 경우만(§1-1). 시험 ⑫-b(2) · 단위 3 · 변이 M10 · M12 · M13 잡힘. `holdings_risk_flow.py` 595줄(그 처리 때 · r1 정정 뒤 599줄 · §6) |
| B-2 | B · low · RECORD | 전송 성공 뒤 `record_send_success` 의 `mark_sent` · `save_risk_state` 예외 → `run()` 전파 · `_finish` 미실행(첫 저장 · 대신 저장 · JSONL · 원장 마무리 없음) → 다음 회차 재발송 가능 · 변경 전부터 있던 경로 | 기록 — §5-5 · PLAN §7-5(문구 '두 저장이 모두 실패하는 경우만 남는다' 교체) |
| B-3 | B · info · FIX | `save_observation` 독스트링 표가 전달 필드 · `sent_today` 를 안 쓴다고만 적음 | 고침 — 표에 'POC6-35 예외: `sent` 를 받은 대신 저장은 이 셋도 쓴다' 줄 추가 |
| B-4 | B · info · RECORD | 15:40 문구는 '중복 억제 {n}건'(`intraday_alert_render.py:295`)이지 'N회' 가 아님 | 기록 — §7 · PLAN Q11 문구 교체 |
| B-5 | B · info · FIX | K2 잘림 회차 + 첫 저장 실패의 `run()` 시험 없음 | 고침 — ⑬-b 추가. 변이 M11(대신 저장 병합 `candidates=` 빠짐)이 2건(⑬-b · 단위 '한 번만')으로 잡힘 |
| B-6 | B · info · RECORD | 대신 저장 회차는 실행 기록 `intraday_sent_today` 를 쓰지 않음 | 기록 — §5-6 · §6 · PROGRAM_TRUTH §9 문단 |
| I1 | info · RECORD | 상태 쓰기가 모두 실패하면 다음 회차에 한 번 더 나가고 `sent_today` 가 1 적음(main 과 같음) | 기록 + 실측 — ⑫ 에 다음 두 회차 단언 추가(한 번 더 나감 · `sent_today` 2 / 발송 회차 3 · 그다음 억제) · 변경 전 코드에서도 통과(§8-1) · §5-5 |
| I2 | A · info · RECORD | 변경 전부터 있던 경로: Telegram 성공 뒤 `save_risk_state` · `mark_sent` 가 예외를 내면 `run()` 이 그대로 중단돼 첫 저장 · 관측 저장 · 대신 저장이 모두 돌지 않음(검토 탐침 v16 · main 과 같음) | 기록 — B-2 와 같은 경로라 §5-5 한 항목으로 적음 · 보완 1 의 '후속 저장이 가능하면' 범위 밖 |
| I3 | A · info · RECORD | `runtime_kst` 가 없고 첫 저장이 파일을 쓴 뒤 예외를 내면 `sent_today` 가 두 번 오를 수 있음(검토 함수 탐침 · 운영 러너는 늘 `kst_now_iso()` 를 넘겨 생기지 않음) | 기록 — §5-5 기존 한계와 같은 내용 |
| I5 | A · info · 환경 메모 | `tests/test_intraday_alert_flow_through.py` 일부 시험은 상대 경로 `state/market/market_data.sqlite` 가 있어야 함(검토자가 저장소 밖 사본에서 돌릴 때 두 사본 모두 같은 8건 실패 → 합성 DB 를 넣은 뒤 289/289) | 조치 없음 — 이번 변경과 무관 · 작업 사본에서는 기존대로 통과 |
| I4 | info · RECORD | K2 정정 뒤 다시 나간 재진입의 원장 행은 `repeat_exposure` · `SECONDARY`(첫 노출은 잘린 회차 행) | 기록 — §6 Q9 해석 메모(코드 읽기 `ledger_items.py:439` · `:488-489` · 시험 단언 없음) |

## 12. 검증자 r1 판정 (Codex · 2026-11-20)

검증 대상은 `poc6-35-reentry`의 기준 커밋 `631b14a9` 위에 stage된 8개 경로다. 설계서 AC1~AC3, PLAN 판정 Q3·Q6 및 보완 1, 확정 PLAN, 개발 결과서를 대조했다. 검증 시험은 staged 파일로 만든 임시 사본에서 합성 상태와 가짜 전송을 사용했다.

### 12-1. A. 기능·산출물 검증

- **A-1 지시 일치 — 위반(F1, P2).** 첫 성공 저장이 실패하고 후속 관측 저장에서 기존 상태를 한 번 읽지 못하면 일일 발송 수와 앞선 전달 기록을 잃는다. PLAN 판정 보완 1의 성공 시각·발송 수 보존과 Q6의 일일 상한을 어긴다.
- **A-2 보고 정확성 — 변경 목록과 절차 확인, 실패 경계 보증 불일치.** 격리 사본 8개(M 7 · A 1), 1,131줄 추가·42줄 삭제를 확인했다. main에는 문서와 STATE 5개가 stage되어 있다. 이 저장소의 미추적 handoff는 제외됐고 격리 사본에는 미추적 경로가 없다. §2의 변경 상태 표기를 실측에 맞췄다. §1·§5의 대신 저장 설명에는 읽기 실패 뒤에도 성공을 보고하는 F1 경계가 빠져 있다.
- **A-3 산출물 정합성 — 정상·기존 예외 경로 확인, F1에서 불일치.** 사업군과 보유 급등의 `(종목, 상태)` 후보 집합을 첫 저장과 관측 저장에 동일하게 전달한다. K2 대표 시험은 기준 코드에서 실패하고 제출 코드에서 통과했다. K3 대기 중 억제, 부분 전송 제외, 같은 회차 중복 집계 방지, 병합 실패 뒤 관측 저장은 제출 시험으로 확인했다. F1에서는 성공 진단과 남은 상태가 서로 어긋난다. Q8은 결과서의 사용자 확인 기록을 확인했다. 실운영 확인 AC3은 반영 뒤 단계다.
- **A-4 금지사항 — 위반 없음.** 신규 의존성·외부 API·삭제·DB 스키마 변경은 발견되지 않았다. 상태 파일 계약, 임계값, 120분 대기, 구역 한도 3, 일일 상한 4, cron, flag, 원장 코드와 `holdings_risk_alert.v1`은 교체되지 않았다.

#### F1. 기존 상태를 한 번 읽지 못하면 대신 저장이 기록을 지운 뒤 성공을 보고함 (P2)

`app/runtime_evidence/sector_signal_state.py:199`의 `load_sector_state()`는 읽기 오류를 `fallback=True`, `fallback_reason="unreadable"`인 빈 상태로 반환한다. `save_observation():446–473`은 대신 저장 경로에서 이 빈 상태의 발송 수 0으로 병합하고 기존 파일을 덮어쓴다. 반환값 `("sent", None)`을 받은 `app/runtime_evidence/holdings_risk_flow.py:552–568`은 `intraday_state_saved_by_observation=True`를 기록한다. 대신 저장 오류와 관측 오류 진단은 남지 않는다.

| 합성 재현 순서 | 확인 결과 |
|---|---|
| 실제 실행 진입점으로 가짜 발송 3회 완료 | 상태 파일에 `sent_today=3`과 앞선 전달 행이 남음 |
| 네 번째 회차 가짜 발송 성공 뒤 첫 쓰기만 실패 | 다음 읽기 직전 기존 상태 파일은 그대로 |
| 대신 저장의 기존 파일 읽기만 일시적으로 실패 | 새 쓰기는 성공. `sent_today=1`로 감소하고 앞선 전달 행이 사라짐. 성공 진단이 남음 |
| 다음 회차, 모든 파일 입출력이 정상 | 다섯 번째 가짜 발송이 나감. 일일 한도 4 초과 |

시험은 실제 상태 파일과 실행 흐름을 쓰되 저장과 읽기에 각각 한 번씩 합성 오류를 넣었다. 디스크에 남아 있던 세 건의 이력을 보존할 수 있는 상황에서 성공으로 표시하면서 상한 적용의 근거를 잃었다.

### 12-2. B. 구현 규칙·구조 품질 검증

- **B-1 암묵 fallback — 위반(F1).** 대신 저장이 기존 상태를 읽지 못한 경우를 발송 이력이 비어 있는 경우와 구별하지 않는다. 병합 또는 쓰기가 예외를 냈을 때 관측만 저장하는 경로는 별도 시험에서 동작했다.
- **B-2 단일 책임 — 위반 없음.** 후보 집합과 상태 병합은 기존 전달 상태의 책임 범위에 있다.
- **B-3 파일 크기 — 위반 없음.** `holdings_risk_flow.py` 595줄, `sector_signal_state.py` 538줄, `intraday_alert_flow.py` 592줄(변경 없음)이다. 제출 범위의 신규 시험은 892줄, 수정한 기존 시험은 최대 989줄이다.
- **B-4 실험·운영 경계 — 위반 없음.** 합성 재현은 격리 시험에 한정했다.
- **B-5 배포·실행 경로 — 위반 없음.** 제출 파일이 index에 있고 OCI 실행 진입점과 배포 스크립트는 그대로다.
- **B-6 기술부채 — 기존 B-2 경로 확인.** 전체 전송 성공 뒤 `record_send_success`의 `mark_sent` 또는 `save_risk_state`에서 오류가 나면 첫 상태 저장과 `_finish`에 도달하지 않는다. 두 경우를 기준 코드와 제출 코드에서 각각 재현했다. 확정 PLAN은 첫 상태 쓰기와 이후 관측 저장을 대상으로 하므로 개발 보고의 범위 구분은 타당하다. 이번 제출이 더 이른 예외의 재발송 가능성까지 해소한 것은 아니다.

### 12-3. 기반 문서 준수

신규 문서 4개는 이 과제의 설계·판정·PLAN·결과서다. 신규 저장소 기술·UI 프레임워크·의존성이나 KILL_SWITCHES 발동 근거는 확인되지 않았다.

### 12-4. 코드 안전성

**위험 수준 MEDIUM.** F1에서 일시적인 읽기 실패가 기존 발송 상태 손실과 일일 상한 초과로 이어진다. 외부 호출, 타임아웃, 자격 증명 처리 경로에는 신규 변경이 없다.

### 12-5. 범위 폭주

**NONE.** 구현은 상태 저장, 시험, 승인 화면 문장과 문서에 한정된다. 실제 전송·OCI 반영·운영 파일 조작을 수행하지 않았다.

### 12-6. 종합 판정

**REJECTED.** 합성 재현에서 최종 전송 뒤 대신 저장이 상한 적용에 필요한 기존 상태를 잃고도 성공으로 기록했다.

검증자 실측은 관련 백엔드 37파일 617건과 화면 2파일 190건 통과다. TypeScript, eslint, black, flake8, py_compile, stage 공백 검사도 통과했다. 별도 합성 검증 3건으로 F1 1건과 기존 B-2 2건을 재현했다. 전체 백엔드 회귀와 OCI 반영 뒤 검사는 이 검증에서 수행하지 않았다.

### 12-7. 사용자에게 한마디

일일 상한 전에 기존 발송 기록을 잃는 F1은 정정 후 재검증이 필요하다. 개발자에게 이 절의 재현 표를 전달하면 된다. 검증자는 결과서 §12 추가와 §2 stage 표기 정정만 수행했다.

## 13. 검증자 r1 지적 처리(개발자 · 2026-11-20)

§12 는 검증자 원문 그대로 두었다. 아래는 지적별 처리다. 본문(§0 ~ §10)은 정정 뒤 코드 기준으로 바꿔 썼다.

| 지적 | 처리 | 근거 |
|---|---|---|
| F1(P2) · A-1 · B-1 대신 저장이 기존 상태를 한 번 못 읽으면 빈 상태 위에 병합해 앞선 전달 기록 · `sent_today` 를 지우고 성공으로 보고 → 다음 회차 일일 상한 초과 | **고침.** 쓰기 직전 다시 읽기가 `unreadable` 이면 이번 회차가 아는 상태(조립 때 읽은 상태 · 첫 저장이 쓴 상태) 위에 쓴다(`load_merge_base`). 쓰기 기준을 실행 기록에 남긴다(`intraday_observation_base` · `intraday_state_save_base` = `snapshot` · `unreadable`). '읽기 실패'와 '발송 이력 없음'을 이제 구별한다 | §1-1 '쓰기 기준 상태' 행 · 시험 r1-①(재현 표 네 줄 그대로 · r1 제출본 `1 == 4` 실패 → 통과) · 변이 R1 · R5 · R9 · R10 · R11 · R14 |
| 같은 뿌리 — 다른 쓰기 경로(모든 layer 열거) | **같이 고침(형수님 결정 2026-11-20).** 상태 파일을 쓰는 곳은 `save_sector_state` 호출 세 곳(첫 저장 · 대신 저장 · 관측만 쓰기)이다(`grep -rn "save_sector_state(" app scripts` 실측). 셋 다 쓰기 직전 다시 읽기를 `load_merge_base` 하나로 잡게 했다. 조립의 읽기(`intraday_alert_flow`)는 쓰지 않는 판정용이라 기존 OPS-02 규칙('비교 불가면 전부 신규')을 그대로 둔다 | 시험 r1-② ③ ④ ⑥(main 에서 실패) · 변이 R6 ~ R8 · R12 · R13 · R15 |
| A-2 §1 · §5 의 대신 저장 설명에 읽기 실패 경계가 빠짐 | **고침.** §0 · §1-1 · §5-8(다루는 범위 · 예전 규칙 그대로인 경우 · 확인하지 않은 범위) · §6 에 경계를 적음. §2 git 표기는 검증자 정정 뒤 다시 실측해 바꿈(9파일) | 이 문서 |
| B-6 기존 B-2 경로(전송 성공 뒤 `record_send_success` 예외) | 변경 없음 — 검증자도 확정 PLAN 범위 밖으로 판정 · §5-5 기록 그대로 | §12-2 B-6 |
| 확정 PLAN 과 다른 점 | `intraday_alert_flow.py` 에 결과 칸 1개 · 대입 1줄(+3 / −1 · 판정 무변경). PLAN §1-7 KS-10 표 '고치지 않음' · §2 '조립 · 변경 없음' · Q3 '`intraday_alert_flow.py` 무변경'과 다르다 — 형수님 결정('2줄 추가 · PLAN 차이 명시'). 594줄로 근접선 600 아래다. 판정 요청 | §4 · §7 |

- **검증 다시 잴 것(r2):**
  - 대상 = 작업 사본 stage 9파일(정정 뒤 내용) · main stage 문서 5건.
  - RED 기준 두 벌 = POC6-35 전 main · r1 제출본(정정 전 index).
  - 변이 = 32건을 다시 돌림.
  - 화면 파일은 바뀌지 않았다.

## 14. 검증자 r2 판정 (Codex · 2026-11-20)

검증 대상은 `poc6-35-reentry`의 `631b14a9` 위에 stage된 9개 경로와 main의 문서 5개다. 설계서, 확정 PLAN, PLAN 판정, §12의 r1 판정과 §13의 정정 내역을 대조했다. 시험은 index에서 만든 임시 소스 사본과 합성 DB·상태 파일·가짜 전송으로 실행했다.

### 14-1. A. 기능·산출물 검증

- **A-1 지시 일치 — 통과.** r1 F1을 해소했다. 첫 성공 저장, 관측 저장, 대신 저장은 모두 `load_merge_base`로 기존 상태를 고른다. 다시 읽기가 `unreadable`이고 이번 회차에 비교 가능한 상태가 있으면 그 상태를 쓴다. 날짜가 양쪽에 있으면 같은 날이어야 한다. 첫 저장이 끝나면 방금 쓴 상태를 이후 관측 저장에 넘긴다. 사용자 승인 두 건은 §4·§7에 기록돼 있다. 조립 파일의 2줄 증가는 저장 기준을 전달하는 변경이며 발송 판정식은 같다.
- **A-2 보고 정확성 — 통과.** 격리 사본 M 8 · A 1, 1,520줄 추가·63줄 삭제, main 문서 M 1 · A 4를 확인했다. 대상 파일은 모두 index에 있다. 개발 보고서의 조립 읽기 실패 한계와 정정 범위가 실제 동작과 일치한다.
- **A-3 산출물 정합성 — 통과.** 기존 전달 시각과 일일 집계를 보존하는 결과, 성공·오류 진단, 다음 회차의 일일 상한을 확인했다. 사업군·보유 급등 후보 집합, 구역 상한, K3 대기와 부분 전송 계약은 관련 시험에서 통과했다. Q8 화면 두 파일은 r1 검증 기준과 바이트가 같고 사용자 확인은 §7에 있다. AC3 실운영 확인은 PLAN §4의 반영 뒤 단계다.
- **A-4 금지사항 — 위반 없음.** 신규 의존성·외부 API·파일 삭제·DB 스키마 변경이 없다. 상태 파일 형식·버전, 임계값, 120분 대기, 구역 한도 3, 일일 상한 4, cron, flag, 원장 코드·계약 버전에 변경이 없다.

| 검증자가 독립 재현한 장면 | 결과 |
|---|---|
| 3회 발송 뒤 네 번째 전체 전송 성공. 첫 저장이 쓰기 전에 실패하고, 대신 저장에서 기존 파일 읽기가 한 번 실패 | r1 사본은 발송 수 1로 실패. r2는 앞선 전달 이력과 네 번째 전달을 남겨 발송 수 4. 다음 회차 차단 |
| 같은 순서에서 첫 저장이 파일을 실제로 쓴 뒤 실패가 보고되고, 대신 저장에서 기존 파일 읽기가 한 번 실패 | r1 사본은 발송 수 1로 실패. r2는 결과를 4로 유지해 같은 회차를 한 번만 반영. 다음 회차 차단 |
| 이미 4회 발송한 상태에서 조립 읽기만 한 번 실패, 이후 파일 입출력 정상 | 기준 main·r1·r2 모두 다섯 번째 가짜 전송 뒤 발송 수 5를 기록. 다시 정상 평가한 다음 회차는 차단. §5-8에 공개된 기존 OPS-02 동작 |

제출 시험에서도 첫 저장의 다시 읽기 실패, 성공 저장 뒤 관측 읽기 실패, 미발송 회차의 관측 읽기 실패, 대신 저장 병합 실패 뒤 관측 저장을 확인했다. 정상 재조회 결과가 이번 회차의 기존 사본보다 우선하며, 날짜가 다른 사본은 사용하지 않는다.

### 14-2. B. 구현 규칙·구조 품질 검증

- **B-1 암묵 fallback — F1 해소.** 쓰기 직전 재조회 실패와 빈 상태를 구분한다. 현재 회차에 쓸 수 있는 상태가 없는 경우의 복구는 기존 비교 불가 계약을 따르며 진단이 남는다.
- **B-2 단일 책임 — 위반 없음.** 상태 선택·병합·쓰기는 기존 전달 상태 저장의 책임이다. 조립 결과는 이미 판정에 사용한 상태를 후속 저장 경로에 전달한다.
- **B-3 파일 크기 — 위반 없음.** 변경한 백엔드는 599·594·580·303줄이다. 신규 시험은 1,182줄이다. `sector_signal_state.py`의 추가 책임은 기존 전달 상태 처리 범위에 속해 KS-10 발동 사유가 아니다.
- **B-4 실험·운영 경계 — 위반 없음.** 재현 도우미는 검증용 임시 경로에만 있다.
- **B-5 배포·실행 경로 — 위반 없음.** 변경 경로가 Git index에 있고 OCI 실행 진입점과 배포 설정에 변경이 없다.
- **B-6 기술부채 — 추가 위반 없음.** 개발 보고서의 전송 성공 직후 발송 기록 예외(B-2)와 조립 읽기 실패는 기존 경로다. §5-8의 다른 실행과 겹치는 경우에도 이번 정정이 동시 쓰기까지 보장하지 않는다.

### 14-3. 기반 문서 준수

추가 문서 4개는 해당 과제의 설계·PLAN 판정·PLAN·결과서다. 운영 코드 변경에 시험이 있고 신규 저장소 기술·UI 프레임워크·KILL_SWITCHES 발동 근거는 확인되지 않았다.

### 14-4. 코드 안전성

**변경분 위험 수준 LOW.** r1에서 확인한 쓰기 전 재조회 실패의 기록 손실과 상한 초과를 재현 시험에서 해소했다. 조립 읽기 장애에 따른 기존 상한 초과 가능성은 §5-8에 남는다. 외부 전송·타임아웃·자격 증명 처리 경로는 이번 변경 대상이 아니다.

### 14-5. 범위 폭주

**NONE.** 첫 저장·관측 저장까지 같은 원인을 정정하고 조립 결과에 저장 기준을 싣는 변경은 §4·§7의 사용자 승인 범위다.

### 14-6. 종합 판정

**종합 판정: VERIFIED**

관련 백엔드 38파일 677건(POC6-35 시험 70건 포함), 검증자 별도 재현 3건, Python 5파일의 black·flake8·py_compile, 양쪽 Git 공백 검사를 통과했다. 화면 두 파일의 바이트가 r1과 같아 r1 화면 시험 190건의 근거를 유지했다. 개발자 변이 실행, 전체 회귀와 AC3 운영 확인은 이번 검증에서 반복하지 않았다.

### 14-7. 사용자에게 한마디

설계자 RESULT 판정에 §14를 전달할 수 있다. 사용자 승인에 따른 PLAN 차이 두 건과 조립 읽기 실패의 기존 한계는 §4·§5-8·§7에 있다. 검증자는 이 §14만 추가했다.

## 15. 설계자 RESULT 판정 · 커밋 전 전체 회귀(개발자 · 2026-11-20)

- **설계자 RESULT 판정 = PASS**(`docs/ai_design/POC6/POC6_35_INTRADAY_REENTRY_ALERT_DELIVERY_RESULT_DECISION_2026-11-20.md` · 원문 그대로 저장).
  - AC1 · AC2 · r1 F1 정정 · Q8 화면 문장을 수용했다. AC3 은 반영 뒤 첫 정규 장중 회차 대조가 남았다.
  - 형수님 승인 PLAN 차이 2건을 수용했다(`intraday_alert_flow.py` 결과 칸 · 세 경로 같은 쓰기 기준).
  - 후속 운영 검토 후보 2건:
    - 조립 때 최초 상태 읽기가 실패하면 일일 상한을 넘을 수 있다. OPS-02 비교 불가 정책에 따른 것이라 별도 검토로 둔다. 실제 운영에서 같은 진단과 중복 발송 · 상한 초과가 함께 관측되면 다시 본다.
    - 전달 성공을 기록하는 두 저장이 모두 실패하거나 앞단 발송 기록이 예외로 중단되는 경우다. 일반 상태 저장 장애로 추적한다.
- **판정 '반영과 종료 기준' 1 · 전체 백엔드 회귀 1회 = 통과.**
  - 위치 · 명령: 격리 사본에서 `caffeinate -i env PYTHONDONTWRITEBYTECODE=1 …/.venv/bin/python -m pytest tests -q -p no:cacheprovider`(POC6-34 와 같은 명령).
  - 결과: **6532 passed, 2 skipped, 1 warning**(Starlette 지원 중단 안내) · 1706.59s(28분 26초) · 종료 0 · 2026-11-20 14:04:31 → 14:33:00.
    - POC6-34 의 6462 passed 에 새 시험 70건이 더해진 수와 같다.
  - 같은 코드 확인: 실행 시작 · 끝의 stage 된 백엔드 변경분(`git diff --cached -- app tests`) sha256 이 `11b053467f9b…` 로 같다. stage 안 된 백엔드 변경은 시작 · 끝 모두 0줄이다.
  - 라이브 DB: 기존 호환 목록 시험은 세션 사본만 읽었다. `[live-db-copy]` 두 줄 모두(시장 DB · 원장 DB) 복사 전후 · 세션 끝 sha256 이 같고 integrity ok 다.
- **화면(같은 시각 · 격리 사본):** `npx tsc --noEmit` 종료 0 · `npm run lint` 0건 · 전체 `npx vitest run` **100파일 2,261 passed**. dev 서버를 켜 둔 상태라 화면 빌드는 돌리지 않았다.
- **다음(판정 '반영과 종료 기준' 2 ~ 4):**
  1. **커밋 · main 반영 · push = 완료**(형수님 승인 2026-11-20 '네'). 아래 15-1.
  2. OCI pull — 형수님 · 15:20 회차 뒤나 비거래일 · 08:05 ~ 08:35 제외.
  3. OCI revision · 반영 뒤 첫 정규 장중 회차의 처리 결과를 기록한다.
  4. 첫 정규 회차 뒤 [원장 새로고침] 전후를 같은 `event_id` 로 대조한다.
     - 자연 발송이 있으면 텔레그램 수신을 대조하고, 없으면 '수신 대조 대상 없음'으로 적는다.
     - K2 의심 질의 결과와 실제 원인 확인을 구분한다.
     - 대신 저장 회차의 일일 집계는 상태 파일 `sent_today` 로 본다.
  5. AC3 근거를 담은 이 결과서를 설계자에게 회신한다. POC6-35 종료는 설계자가 판정한다(설계자 2026-11-21). 커밋은 뒤에 한꺼번에 하고, push 는 따로 승인을 받는다.

### 15-1. 커밋 · main 반영 · push(2026-11-20 · 형수님 승인)

- **반영 전 상황:** 형수님이 16시대에 OCI pull · [원장 새로고침]을 먼저 하셨다. 그때는 커밋 · push 전이었다(로컬 · 원격 main 모두 `631b14a9` · 16:29 실측). 그래서 OCI 가 받은 새 코드는 없었고, 그 새로고침은 반영 전 기록이다.
- **구현 커밋 `f0e0c945`:** 격리 브랜치 `poc6-35-reentry` · 9파일 · 1520+ / 63−(`git show --stat f0e0c945`).
  - 커밋 전 그 사본의 stage 안 된 변경은 0이었다.
  - 커밋 뒤 `git status` 출력 0줄.
- **main 반영:** main 을 `git merge --ff-only poc6-35-reentry` 로 빨리 감기 했다(→ `f0e0c945`). main 에 stage 해 둔 문서 6건은 겹치지 않아 그대로였다.
- **PROGRAM_TRUTH 반영일:** '반영 대기(격리 사본)' 표시 10곳과 머리 줄을 'main 반영 2026-11-20 · OCI 반영 대기'로 바꿨다. 머리 줄에 RESULT 판정 · 회귀 · 구현 커밋을 더했다. 이 문서 커밋에 들어간다.
- **운영 화면 3000 확인(읽기만 · 쓰기 요청 0건 · 1440 폭):** 「OCI 운영·적용」 ② '장중 급등락 설정' '구역별 최대' 행 끝 문장이 새 문장이다('… 구역 한도에 밀린 재진입 신호는 다음 회차의 조건과 발송 한도에 따라 다시 검토합니다.'). 카드 넘침 없음(scrollWidth 1138 = clientWidth 1138). 표 값('3건')을 PC 백엔드 8000 응답으로 받아 그렸다.
- **문서 커밋 · push:**
  - 문서 커밋에 담은 것: 설계서 · PLAN 판정 · RESULT 판정 · PLAN · 이 결과서 · STATE · PROGRAM_TRUTH.
  - push: `origin/main` 으로 push 했다.
  - 커밋 번호는 `git log` 로 확인한다(이 문서 안에는 적지 않음).
- **다음:**
  1. 형수님이 OCI pull 을 다시 한다. 지금 원격에 이번 커밋들이 있다.
  2. 개발자가 OCI revision 을 읽기만으로 확인한다.
  3. 반영 뒤 첫 정규 장중 회차는 2026-11-23(월) 09:30 이다. 그 회차 뒤 형수님이 [원장 새로고침]을 누른다.
  4. 개발자가 원장 · PC 사본을 대조해 운영 확인을 기록하고, 결과서를 설계자에게 회신한다(종료는 설계자 판정).

### 15-2. OCI 반영 증거(2026-11-20 · 판정 '반영과 종료 기준' 2 의 앞부분)

- 형수님이 push 뒤 OCI pull 을 다시 했다.
- 개발자가 읽기 전용 명령 한 번으로 확인했다(`ssh oci-krx` · 2026-11-20 17:18:59 KST). 쓰기 · 발송 · 재시작은 하지 않았다.
  - 현재 커밋: `git log --oneline -2` = `42ce760f`(문서 커밋) · `f0e0c945`(구현 커밋).
  - 작업 트리: `git diff --quiet HEAD -- app scripts` 통과. OCI 의 `app` · `scripts` 가 그 커밋과 같다.
  - import: `PYTHONDONTWRITEBYTECODE=1 venv/bin/python -c "import …"` 로 바뀐 네 모듈(`sector_signal_state` · `intraday_alert_flow` · `runner_evidence` · `holdings_risk_flow`)을 불러왔다. 결과 = `import ok True True`(`load_merge_base` 있음 · `IntradayAssembly.previous` 칸 있음).
- **남은 것(판정 2 뒷부분 · 3):** 반영 뒤 첫 정규 장중 회차 2026-11-23(월) 09:30 의 처리 결과. 그 회차 뒤 [원장 새로고침] 전후 · 같은 `event_id` 대조 · 수신 대조(자연 발송이 있으면) · K2 의심 질의.
  - 2026-11-20 의 회차(09:30 ~ 15:20)는 모두 push 전 코드(`631b14a9`)로 돌았다. 그래서 반영 뒤 확인에 쓰지 않는다.
  - 형수님이 2026-11-20 에 지난 회차 기록을 지우고 지금 다시 돌리는 방법을 물었다. 개발자는 권하지 않았다. 이유는 네 가지다.
    1. 운영 원장 · 실행 기록 · 상태 파일을 지우면 증거 기록이 깨진다.
    2. 장 마감 뒤 수동 실행은 정규 회차가 아니다. 원장에는 예정 밖 실행으로 남는다.
    3. 상태를 지우면 모든 신호가 신규가 되어 실제 텔레그램이 다시 나갈 수 있다.
    4. 바뀐 코드는 이미 OCI 에 있어 월요일 첫 회차부터 그대로 동작한다.
