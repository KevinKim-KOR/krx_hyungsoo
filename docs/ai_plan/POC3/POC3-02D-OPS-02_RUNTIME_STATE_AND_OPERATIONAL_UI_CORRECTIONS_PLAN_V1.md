# POC3-02D-OPS-02 — RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS PLAN V1

작성일: 2026-09-27 · 작성자: 개발자(VSCode Claude) · 수신: 설계자

```text
STEP_ID          = POC3-02D-OPS-02
STEP_NAME        = 장중 전달 상태·운영 UI 정합성 보완
PREDECESSOR      = POC3-02D-OPS-01
SUCCESSOR        = POC5-01A
DESIGN           = docs/ai_design/POC3/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_DESIGN_V1.md (설계자 지시 원문)
PLAN_STATUS      = CONFIRMED — 설계자 판정 2026-09-28(Q1~Q6 · §6 · 원문은 설계서 끝)
IMPLEMENTATION   = 3-1 커밋 · push 완료(b5b15509 · 사용자 지시로 「OCI 운영·적용」 화면 합침과 함께 · 사용자 실화면 확인) · 3-2 · 3-3 · 3-4 구현 · 테스트 완료 · 검증자 VERIFIED(2026-09-29) · 커밋(결과서 `docs/ai_result/POC3/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_RESULT.md`)
LIMITS           = NEW_API 0 · 외부 source 0 · 의존성 0 · DB 테이블 0 · push_kind 0 · cron 0 · flag 0 · 실발송 0 · OCI 쓰기 0
RUNNER           = scripts/run_three_push_runtime_oci.py 646줄 — 변경 0 목표(상한 648)
```

**근거** — 사실조사(2026-09-27 · 읽기 전용 · 코드 file:line 인용 · 수정 0건). 원인을 추정한 곳은 `(추정)` 으로 표시한다.

---

## 0. 한눈에

| 항목 | 지금 동작(사실) | 바꾸는 것 | 중단 조건 | 진행 |
|---|---|---|---|---|
| 3-1 OCI 링크 | 「오늘의 투자 점검」 OCI 한 줄의 '진단·상태에서 상세 보기 →' 가 `diagnostics`(「개발·실험용」 · OCI 상세 없음)로 간다. 2026-08-16 메뉴 분리(`6d818d4d`)가 이 링크를 고치지 않았다 | 대상 = OCI 상태 화면(2026-09-27 사용자 지시로 「OCI 운영·적용」 `approval` 에 합쳐짐) · 문구를 도착 화면 이름으로 · 라우팅 관통 테스트 | 없음 | 완료(`b5b15509` · 사용자 실화면 확인) |
| 3-2 전달 상태 | 억제 판정이 **관측 `state`** 와 비교한다. 관측은 매 회차 덮이므로, 전달되지 못한 새 상태가 '이미 보낸 상태'가 된다(결함 1). `out.intraday` 대입 뒤 예외로 구 본문만 나가도 장중 신호가 발송 완료로 기록된다(결함 2) | 마지막 **성공 전달 상태**를 따로 저장하고 억제 비교를 그것으로(안 A) · `out.intraday` 대입을 본문 대체 시점으로 | **해석 필요**(§6 Q1): JSON 상태 파일 필드 1개 추가 · 02C-OPS-02 §15-2 개정 | 구현 완료(Q1~Q3 확정) |
| 3-3 낡은 역검증 | `scripts/ops02b2/reverse_verify_guards.py` ⑦ 이 옛 계약(no_change 억제)을 요구해 `!!` · exit 1 · 목업 ⑦ 제목 '동일 fingerprint (미발송)' 과 결과 '발송 = 예' 모순 | ⑦ 을 현재 계약 역검증으로 교체 · 목업 ⑦ 정정 · 현재형 옛 문구 정정 · 과거 기록에 적용 기간 | 없음 | 구현 완료 |
| 3-4 KOSPI 표시 | 「오늘의 투자 점검」은 `ok` 외 전부 '수익률·위치 자료 없음' · 「요즘 잘 오르는 ETF」는 stale 을 'N/A — KOSPI 시계열이 수집되지 않았습니다.'(틀린 사유) + 영문 경고 | 상태별 표시 | **해석 필요**(§6 Q4): 5상태 중 fetch 실패 · 휴장 구분은 기존 응답에 필드 추가가 필요 | 구현 완료(안 B · Q4~Q6 · 문구 확정 §7) |

---

## 1. 진행 순서

1. 이 PLAN 기록(완료) → 설계자에게 §6 질문 전달.
2. 3-1 · 3-3 구현 · 테스트(중단 조건 없음 · 설계자 지시 STEP 3 '재판정 없이 구현').
3. §6 Q1 확인 → 3-2 구현. Q4 확인 + 사용자 문구 확인 → 3-4 구현.
4. STEP 5 전체 검증 → 결과서 → 설계자 RESULT 판정 → 검증자 → VERIFIED 뒤 커밋 · push 승인 요청 → OCI pull · 운영 확인 → POC5-01A.
5. OPS-01 운영 확인(2026-09-28 07:20 · 08:00)은 이 단계와 병행한다(설계자 STEP 6).

---

## 2. 3-1 OCI 상세 링크

**사실**

- 링크: `frontend/app/components/today/OciStatusOneLine.tsx:58` `onNavigate("diagnostics")` · 문구 `:60` '진단·상태에서 상세 보기 →'.
- `diagnostics` 의 메뉴 이름은 「개발·실험용」(`LeftSidebar.tsx:104`)이고 OCI 내용이 없다(`DiagnosticsView.tsx:30-63`). '진단·상태' 는 메뉴 **그룹** 이름이다(`LeftSidebar.tsx:93-105`).
- 도착해야 할 화면: `oci_status` → `OciStatusView`(`MainPanel.tsx:90-92`) · 메뉴 이름과 h1 이 모두 「OCI 운영 상태」(`LeftSidebar.tsx:102` · `OciStatusView.tsx:45`).
- 이 링크를 보는 테스트가 없고, `MainPanel` 수준 테스트도 없다.

**바꾸는 것**

> **2026-09-27 사용자 직접 지시로 도착지 변경** — 같은 날 「승인·적용」과 「OCI 운영 상태」가 한 화면 「OCI 운영·적용」(`approval` · OCI 상태는 ① 섹션)으로 합쳐졌다(UI 전용 · MenuKey 13→12 · `oci_status` 없음). 그래서 3-1 링크의 도착지와 문구도 그 화면을 따른다. 설계자 3-1 원칙(실제 OCI 상태 화면 · 문구 = 도착 화면 이름 · 신규 메뉴 없음 · 관통 테스트)은 그대로다.

- `:58` → `onNavigate("approval")`(처음 구현은 `oci_status` · 합침 뒤 변경).
- `:60` → **'OCI 운영·적용에서 상세 보기 →'**(메뉴 정본 이름을 그대로 쓴다 · 사용자 실화면 확인 대상).
- 주석 정정: `OciStatusOneLine.tsx:3-6 · :15` · `TodayInvestmentCheckView.tsx:112-113` · `MainPanel.tsx:76-77`(주석만 · 08-16 부터 틀린 서술).
- 범위 밖(보고만): NAV · 데이터 원인을 「개발·실험용」으로 보내는 다른 링크(`HoldingsRiskEvidenceSection.tsx:342` · `JudgmentWorkbenchView.tsx:619/638/680/699/706` · LEGACY `DashboardView.tsx`). OCI 와 무관하다.

**테스트**

- 단위(`TodayInvestmentCheckView.test.tsx`): API mock 에 `fetchOciStartupStatus` 추가 · 링크 클릭 → `onNavigate('approval')`(`'diagnostics'` · `'oci_status'` 아님) · 링크 이름이 `MENU_ITEMS` 의 `approval` label(「OCI 운영·적용」)을 포함.
- **라우팅 관통**(신규 `frontend/app/components/MainPanel.test.tsx`): 실제 `<MainPanel/>` 렌더 → 링크 클릭 → h1 「OCI 운영·적용」 · h2 「① 지금 OCI 상태 (읽기만)」 표시 · 「개발·실험용」 h1 없음 · 사이드바 「OCI 운영·적용」 이 현재 화면.
- 회귀: vitest 전체 · `npx tsc --noEmit` · `npm run lint`(build 는 하지 않는다).

---

## 3. 3-2 전달 상태 저장 계약

**사실**

- 저장 파일: `state/three_push/sector_signal_state_latest.json`(사업군 · 보유 급등 U\*) · `holdings_risk_state_latest.json`(보유 급락 D\*) · `intraday_checkup_tally_latest.json`. PC 에는 장중 state 파일이 없다(OCI 에만 생성).
- entry 필드: `state` · `continuous` · `last_sent_at`(+ 파일 수준 `sent_today`) — `state` 는 하나뿐이다(`sector_signal_state.py:126` · `:258-267`).
- 억제 판정(`compute_sector_changes`): 저장된 `state` == 현재 state 이고 `last_sent_at` 이 있고 `continuous` 면 억제. 저장된 `state` 는 관측 저장(`save_observation` · 모든 Gate 통과 회차)이 매번 덮는다.
- 발송 진척: 전체 성공(부분 아님) 뒤 `runner_evidence._save_intraday_state_after_send` 가 본문에 실린 `sent_signals` 에 `last_sent_at` · `sent_today +1`(D1 · 본문에 실린 것만).
- D\*(보유 급락)는 `worst_state` 를 성공 뒤에만 저장하고 C4 로 잘린 것을 뺀다 → 이미 '성공 전달 기준'이다.

| 시나리오 | 지금 저장되는 것 | 결함 |
|---|---|---|
| 구역 상한에 잘림 | 잘린 신호의 `state` 가 새 상태로(관측) · `last_sent_at` 은 이전 전달 그대로 | 이전에 전달된 ticker 는 다음 틱 억제 |
| `telegram_send_error` | 관측만 저장(`state` 전진) · 발송 진척 없음 | 같음 |
| `partial_delivery` | 같은 경로 | 같음 |
| 조립 뒤 diagnostics 예외(`holdings_risk_flow.py:331`) | 구 본문 발송 · 장중 `sent_signals` 에 `last_sent_at` · `sent_today +1` | 한 번도 안 나간 신호가 발송 완료 |
| 조립 뒤 tally 분류 예외(`:351-384`) | 같음 + 관측 저장 | 같음 |
| 전달된 뒤 같은 상태 지속 | 억제(정상) | — |

**바꾸는 것(안 A · 개발자 제안 · §6 Q1)**

- `sector_signal_state.py`(325 → 약 340): entry 에 **마지막 성공 전달 상태** 필드 1개(확정 이름 `last_delivered_state` · Q1)를 두고, **전체 성공 경로의 `sent` 루프에서만** 전진시킨다. 관측 저장은 전달 상태를 전진시키지 않는다.
  - 구현 중 추가(2026-09-28 · 리뷰 실측 2건 · 결과서 §1-2): ① 구파일 entry(필드 없음 · `last_sent_at` 있음)는 **다음 정상 저장**(관측 저장 · 전송 성공 저장) 때 `state` 를 덮기 전에 추정 전달 상태를 그대로 필드로 옮긴다(Q1 '다음 정상 저장 때 필드를 추가' — 옮기지 않으면 장중 배포 당일 미전달 상태가 추정 규칙으로 '전달 상태' 가 된다). ② 회복(`continuous=False`) 뒤 전달 상태와 **다른** 상태로 관측돼도 회복 기록을 지우지 않는다 — 그래야 전달 X → 회복 → 미전달 Y → X 가 설계 §5 '회복 후 재진입 + cooldown' 으로 판정된다(전에는 cooldown 뒤에도 '지속 중' 억제). 관측 상태 = 전달 상태인 경우의 동작은 전과 같다.
- `compute_sector_changes`: 비교 기준을 `delivered_state` 로. 필드가 없는 옛 entry 는 `last_sent_at` 이 있을 때만 `state` 를 전달 상태로 본다(오늘 억제 동작 유지 · 기존 테스트 불변).
- `schema_version` 은 `sector_signal_state.v1` 유지 — 올리면 `schema_mismatch` 로 `sent_today` 가 0 으로 읽혀 일일 상한이 풀린다(항목 10 위반).
- `holdings_risk_flow.py`(491 → 약 496): `out.intraday = intraday` 를 **통합 본문이 구 본문을 대체하는 분기**로 옮기고, except 에서 `out.intraday` · `out.intraday_records` 를 비운다. → 조립 뒤 예외도 조립 전 예외와 같은 경로(구 본문 · D\* 전체 저장 · 장중 발송 진척 · 관측 · 집계 쓰기 0 · 이미 테스트로 고정된 경로)가 된다.
- 러너 변경 0 · `runner_evidence.py` 는 주석만(필요 시). cooldown · 일일 상한 · 회차당 · 구역 상한 · 임계값 변경 0.
- 효과(사용자에게 보이는 변화): 전달되지 못한 상태 변화가 다음 틱에 다시 나간다. 그만큼 일일 상한(4)에 더 일찍 닿을 수 있다(상한 자체는 그대로).

**정한 기본값**(§6 에서 다르게 판정하면 따른다)

- 전달된 X → 미전달 Y → 다시 X(연속): 억제 — 마지막 전달 상태가 X 다(§6 Q3).
- 예외 경로 회차: 관측 · 집계 · `sent_today` 쓰기 없음 — 조립 전 예외와 같게(§6 Q2).
- '장중 조립 후 tally/summary 예외' = `holdings_risk_flow.py:351-384` 의 회차 결과 분류. 발송 뒤의 `record_tick` · 15:40 요약은 이미 격리돼 있어 범위 밖.
- `runner_evidence.py:151` `getattr(intraday, 'state_path')` 가 항상 None 인 잠재 불일치(운영은 기본 경로로 일관): 보고만.
- 결과서 5분리(OBSERVATION_STATE · DELIVERY_STATE · ACTUALLY_INCLUDED_SIGNALS · SUCCESSFULLY_DELIVERED_SIGNALS · PENDING_FOR_NEXT_TICK)는 **테스트가 tmp 파일에서 뽑은 산출물**로 보고한다. JSONL 에 새 키를 넣지 않는다(POC5-01 과 겹침).

**테스트**(신규 `tests/test_poc3_02d_ops02_delivery_state.py` · OPS-01 rig · tmp 경로 · 대역 전송기)

- run() 관통 7건: 구역 상한 잘림(사업군 ENTRY_REVIEW→AVOID_CHASE · 보유 급등 U5_7→U7_10) · `telegram_send_error` · `partial_delivery`(가짜 · 실제형 chunk 실패) · diagnostics 예외 · tally 분류 예외 · 다음 틱 재후보 · 성공 전달 뒤 정상 억제.
- 단위: `delivered_state` 는 `sent` 에서만 · 관측 · 부재 표시 · 평가 불가 경로가 그대로 보존 · 억제표(관측 ≠ 전달 → 발송 · 관측 == 전달 + 연속 → 억제 · 회복 뒤 cooldown · 옛 entry 호환 · 손상 값).
- 회귀: 일일 상한 · 회차당 1 · 구역 3 · dry-run · flag-off · duplicate 쓰기 0 · 정책 비활성 · C4 전 테스트 · flow_through 상태 테스트.
- 무력화: 기준 커밋 `git archive` 사본에서 새 테스트가 실패(RED) · 수정 뒤 통과(GREEN).

---

## 4. 3-3 낡은 fingerprint 역검증

**사실**

- 2026-09-18(`02C-OPS-01` · `685de1c4`)부터 정기 PUSH 는 fingerprint 로 발송을 막지 않는다. 시장 브리핑은 `content_unchanged` 기록만(`flow.py:381-397` · `runner_market_briefing.decide`), 보유 브리핑은 변화가 없으면 현재 상태 전체를 보낸다(`holdings_selection_flow.py:166-188` · 선정 0건만 `no_selection`).
- 같은 실행 · 같은 슬롯 중복은 registry 가 막는다 — 키: 시장 = 날짜 · 보유 = 날짜#슬롯 · 위험 알림 = 날짜#HH:MM(모두 `param_id` 포함). 사건형 `holdings_risk_alert` 는 `worst_state` 로 같은 위험을 억제한다.
- `scripts/ops02b2/reverse_verify_guards.py` ⑦(`:226-246`)은 옛 억제를 요구한다 → `!!` · exit 1. 무력화 수단도 현재 계약에서는 똑같이 발송돼 시험할 보호가 없다. `scripts/ops02c` ⑥ 은 이미 새 계약을 검증한다.
- 목업 ⑦(`build_market_briefing_mockups.py:347-386` · docstring `:4`): 제목 '미발송' · 결과 '발송 = 예' · '상태 저장 = 아니오 (미발송 …)' — 모순 3개.
- 현재형 옛 문구: `flow.py:1,3-4,23` · `app/market_briefing/__init__.py:10` · `holdings_selection_flow.py:1,8` · `holdings_selection_state.py:1-4` · 테스트 `test_market_briefing_contracts.py:663` · `test_holdings_selection_state.py:1,132,228-238`.

**바꾸는 것**

- ops02b2 ⑦ 을 현재 계약 역검증 두 개로 교체(각각 '가드 있음 통과' + '무력화 시 해악'):
  - ⑦-a 다음 거래일 같은 fingerprint 시장 브리핑은 발송(무력화: 옛 no_change 억제를 씌우면 skip).
  - ⑦-b 같은 날 재실행은 registry 일 단위 키로 차단(tmp `runtime_state.sqlite` · 무력화: 분 단위 키로 바꾸면 08:05 재실행이 발송).
  - 스크립트는 러너 모듈을 import 하지 않는다(`.env` 로드 방지).
- 보유 · 위험 알림 계약은 pytest run() 관통 테스트로(신규 `tests/test_poc3_02d_ops02_regular_push_contract.py`): OPEN 발송 뒤 같은 입력의 MIDDAY 도 발송(`content_unchanged`) · 같은 MIDDAY 재실행은 `duplicate_runtime` · CLOSE 는 막히지 않음 · 위험 알림 두 번째 틱은 `no_new_or_worsened`. 무력화: 슬롯 키를 일 단위 / 분 단위로 바꾸면 실패.
- 목업 ⑦: 제목 '동일 fingerprint · 다음 거래일 (발송)' · 상태 저장 = 예 · 비고에 `content_unchanged` 와 같은 날 재실행은 registry 가 막는다는 설명. 나머지 ①~⑥ 출력 불변(diff).
- 현재형 옛 문구: 주석 · docstring · 테스트 머리 문구만 고친다(동작 · 단언 불변). `_simulate_slot` 은 '2026-09-18 운영분까지의 러너 순서 재현' 이라고 표기만 한다(단언 약화 없음).
- 과거 기록: 삭제 · 재생성 없이 적용 기간 주석('2026-09-18 운영분까지 적용 · 2026-09-18 밤 `02C-OPS-01` OCI 반영으로 폐지 · 새 계약 첫 운영일 2026-09-21')을 단다 — `POC3-OPS-02B-2_MARKET_BRIEFING_MOCKUPS.md` ⑦ · `POC3-OPS-02B-2_MARKET_BRIEFING_MESSAGE_RESULT.md` · `POC3-OPS-01A_…_RESULT.md` 해당 행. handoff · 설계서는 건드리지 않는다.
- 범위 밖(보고만): `scripts/ops02c` ④ 의 기존 `!!`(POLICY_RANGES 가 REQUIRED_POLICY_KEYS 와 같은 12키라 무력화가 드러나지 않는 구조) · `REASON_NO_CHANGE` 상수는 유지(ops02c ⑥ · 테스트 3곳 사용).

---

## 5. 3-4 KOSPI stale 화면 표현

**사실**

- 백엔드 `compute_kospi_metrics` 상태는 `ok` · `stale` · `unavailable` 과 `freshness{as_of_date, reference_date, lag_trading_days, is_fresh, reason}` 이다(`market_regime.py:138-169` · `market_benchmark_freshness.py:64-80`). lag 축은 **KODEX200 DB 날짜**다(달력 아님).
- `GET /market/topn/latest` 의 모델 `MarketContextKospi` 에는 `freshness` · `reason` 이 없어 응답에서 빠진다(`api_market_topn_models.py:156-168` · Pydantic 기본 extra=ignore). lag 는 영문 warning 문자열에만 남는다.
- `GET /holdings/market-evidence/latest` 의 `judgment_summary.market_position.kospi.freshness` 에는 lag · reason 이 있다(오늘 화면이 이미 조회 중).
- 'source_stale:' 표지는 PC 수동 갱신의 KS11 `market_refresh_log` 행에만 있다. KS11 행만 골라 주는 기존 응답은 없다(`topn.latest_refresh` 는 필터 없는 최신 행 · 우연히 KS11 일 때만). OCI 07:20 배치의 KOSPI 결과는 PC 로 오는 경로가 없다.
- 거래일 판정 함수는 있지만 어떤 API 도 노출하지 않는다. 휴장일에는 KODEX200 · KOSPI 모두 직전 거래일에 머물러 `ok` 로 보인다.

**5상태별 가능 여부**

| 상태 | 안 A — 프론트만(응답 변경 0) | 안 B — 기존 응답에 선택 필드 추가(엔드포인트 신설 없음) |
|---|---|---|
| 정상 최신 | 가능 | 가능 |
| source stale | 가능(`status=stale` · as_of · lag/reason 은 evidence 응답에서) · 원인이 source 인지는 KS11 행이 최신일 때만 | 가능(KS11 전용 최근 적재 요약) |
| provider · fetch 실패 | KS11 행이 최신일 때만(우연) · 아니면 '원인 확인 불가' | 가능 |
| 아직 평가되지 않음 | 조회 중 · 한 번도 수집되지 않음(`unavailable` · as_of 없음)은 가능 | 같음 |
| 휴장 · 거래일 아님 | 주말만 · 평일 휴장은 **불가** | 가능(기존 캘린더 · 함수) |

- 판단 로직(`market_topn.py:320-349` · composer `:193-194`)과 임계값(`MAX_STALE_TRADING_DAYS=1`)은 어느 안이든 건드리지 않는다.
- 범위(제안): 「오늘의 투자 점검」 KOSPI 머리(`KospiHeadline.tsx` 139줄) + 「요즘 잘 오르는 ETF」 시장 배경 카드(`MarketContextCard.tsx` 131줄). 차트 · AI 복사 텍스트 · LEGACY Dashboard 는 범위 밖(보고만). `MarketDiscoveryView.tsx`(825줄 · 근접선 850)는 건드리지 않는다.
- 상태별 한국어 문구는 **구조와 초안을 사용자에게 먼저 보여 확정**한다(§7).
- **구현(안 B · Q4~Q6 확정)**: 기존 `GET /market/topn/latest` 의 `market_context.kospi` 에 선택 필드 3개(`display_state` · `trading_day_lag` · `today_is_trading_day`). 상태는 백엔드(`api_market_topn_service.kospi_display_state`)가 저장 KOSPI · KS11 적재 기록 · C7 거래일 지연 · 운영 판정 · 오늘 거래일 여부로 정한다. lag 는 C7 계산을 `trading_day_lag.benchmark_lag_trading_days` 로 옮겨 적재 감지와 같은 함수를 쓴다(본문 불변). 화면은 공용 생성기 `KospiStatusNote.tsx` 가 상태 → 확정 문구로 옮긴다.

---

## 6. 설계자 확인 (중단 조건 해석 · 선택)

**확정(설계자 판정 2026-09-28 · 원문은 설계서 끝) — 아래 질문표보다 우선한다.**

| Q | 확정 |
|---|---|
| Q1 | 승인 · 중단 조건 아님. 필드명 **`last_delivered_state`** 고정 · `schema_version` 유지 · fingerprint 저장 아님 · 02C-OPS-02 §15-2 를 이 계약으로 개정. 구파일: 필드 있음 → 그대로 · 없음 + `last_sent_at` 있음 → 기존 `state` 를 마지막 전달 상태로 추정 · 없음 + `last_sent_at` 없음 → null. 읽기만으로 일괄 변환하지 않고 다음 정상 저장 때 필드를 더한다 |
| Q2 | 승인 — 조립 뒤 예외로 구 본문만 나간 회차: 장중 관측 전진 · 집계 · `sent_today` 증가 · 발송 완료 저장 모두 안 함 · 오류는 실행 이력에 · 구 본문에 실제 실린 D\* 만 전송 성공 계약대로 저장 · 전송 실패 · 부분 전송이면 D\* 도 저장 안 함 |
| Q3 | 억제 — 마지막 전달 X · 현재 X 면 억제 · 이후 Y 가 다시 나오면 X 와 달라 다시 후보 |
| Q4 | 승인 · `NEW_API=0` 위반 아님. 조건: 신규 엔드포인트 금지 · 기존 필드 의미 불변 · 추가 필드는 선택 필드 · 외부 호출 추가 금지 · 이미 보유한 DB · 상태만 사용 · Dashboard 의 `/market/topn/latest` 자동 호출 부활 금지(KS-1) · 이미 그 API 를 부르는 화면에서만 표시 |
| Q5 | 합치지 않는다 — 화면 요청 진행 중 `확인 중` · 실행 · 수집 이력 전혀 없음 `아직 평가되지 않음` · 수집했지만 값 없음 `수집 결과 없음` · 데이터 오래됨 `기준일 지연` · 호출 실패 `자료원 확인 실패` |
| Q6 | 화면이 계산하지 않고 **백엔드가 C7 공용 거래일 계산으로 산출한 lag** 를 우선 쓴다. KODEX200 적재일을 대체 축으로 쓸 때만 'KODEX200 거래일 기준 N일 지연' 처럼 명시하고 `KOSPI_TRADING_DAY_LAG` 와 같은 값처럼 다루지 않는다 |

질문표(제출판 · 기록용):

| Q | 항목 | 질문 | 개발자 제안 |
|---|---|---|---|
| **Q1** | 3-2 · 중단 조건 | `sector_signal_state_latest.json` entry 에 '마지막 성공 전달 상태' 필드 1개를 더한다(DB 아님 · `schema_version` v1 유지 · 옛 파일 호환 · C5 tally 선례). 이것이 '신규 DB 또는 스키마 변경' 중단 조건인가? 또 02C-OPS-02 설계 §15-2 '영속 발송 상태 = last_sent_at · sent_today' · '기존 상태 파일에 fingerprint 필드를 추가하지 않는다'를 이번 3-2 ① · ② 가 개정한 것으로 보는가? | 해당 없음 · 개정으로 본다(안 A). 대안 B(필드 없이 전달 이력이 있는 entry 의 `state` 를 관측이 덮지 않게)는 §15-2 1항('state 는 매 회차 갱신되는 관측 필드')을 뒤집고 관측 상태를 잃어 STEP 5 의 OBSERVATION_STATE 를 보고할 수 없다 |
| Q2 | 3-2 | 조립 뒤 예외로 구 본문만 나간 회차에 관측 · 집계 · `sent_today` 를 쓰는가? | 쓰지 않는다 — 조립 전 예외 경로(테스트로 고정)와 같게. D\* 는 구 본문 기준 저장 유지 |
| Q3 | 3-2 | 전달된 X → 전달 못 한 Y → 다시 X(연속 관측)는? | 억제 — 마지막 전달 상태가 X 다 |
| **Q4** | 3-4 · 중단 조건 | 기존 `GET /market/topn/latest` 의 `market_context.kospi` 에 선택 필드(`freshness` · `reason` · KS11 최근 적재 요약 · 오늘 거래일 판정)를 더하는 것이 `NEW_API = 0` 위반인가? | 엔드포인트 신설이 아니므로 위반 아님으로 보고 안 B. 위반이면 안 A 로 하고 fetch 실패 · 평일 휴장은 결과서에 '표시 불가' 로 적는다 |
| Q5 | 3-4 | '아직 평가되지 않음' 의 뜻 | 한 번도 수집되지 않음(`unavailable` · as_of 없음) + 화면 조회 중. '오늘 갱신 전' · 'OCI 07:20 전' 은 PC 에 자료가 없어 제외 |
| Q6 | 3-4 | 표시할 lag 의 축 | 화면 계산값(KODEX200 DB 축)을 'KODEX200 기준' 으로 표기. 적재 로그의 달력 축 lag 는 사유 문자열에만 |

---

## 7. 사용자 확인

- **3-1 문구**: 'OCI 운영·적용에서 상세 보기 →'(2026-09-27 합침 뒤). 구현 뒤 실화면으로 확인 — 완료(`b5b15509`).
- **3-4 상태별 문구 — 확정(2026-09-28 · 사용자 초안(목업) 승인 + 설계자 문구 규칙 · 원문은 설계서 끝)**. 구현 화면 확인은 따로다(결과서 `IMPLEMENTED_UI_CHECK`). 영문 KOSPI 경고 줄은 화면에서만 숨긴다(사용자 선택). 설계자 RESULT 필수 보완 M1(2026-09-28): 같은 `수집 결과 없음` 배지에서 기준일이 없으면 '저장된 KOSPI 자료가 없습니다.', 기준일은 있으나 수익률이 없으면 'KOSPI 수익률을 계산할 자료가 충분하지 않습니다.'. 아래 표는 제출 때 초안(기록용)이다:

  | 상태 | 「오늘의 투자 점검」 KOSPI 머리 초안 |
  |---|---|
  | 정상 최신 | (기존 값 그대로) + 'KOSPI 기준일 YYYY-MM-DD' |
  | source stale | '자료가 오래됨 — KOSPI 기준일 YYYY-MM-DD · N거래일 지연(KODEX200 기준)' |
  | provider · fetch 실패 | '최근 갱신 실패 — 마지막 KOSPI 기준일 YYYY-MM-DD' |
  | 아직 평가되지 않음 | 'KOSPI 자료가 아직 수집되지 않았습니다' |
  | 휴장 · 거래일 아님 | '오늘은 휴장일 — 직전 거래일 YYYY-MM-DD 기준' |

---

## 8. 금지 범위 대조 (설계자 STEP 4)

| 항목 | 이 PLAN |
|---|---|
| 신규 API · 외부 source · 의존성 · DB 테이블 · push_kind | 0. 3-4 안 B 의 기존 응답 선택 필드는 Q4 판정 대상 |
| cron · flag · 임계값 · cooldown · 일일 상한 · 스케줄 | 변경 0 |
| 실발송 · OCI 쓰기 | 0 — 테스트는 tmp 경로 · tmp DB · 대역 전송기 · `_live_guard` |
| 러너 | 646 · 변경 0 목표 |
| 사용자 소유 handoff | 건드리지 않음 |
| 신규 파일 | 설계자가 이름을 정한 문서 3개 + 테스트 파일 3개(`tests/test_poc3_02d_ops02_delivery_state.py` · `tests/test_poc3_02d_ops02_regular_push_contract.py` · `frontend/app/components/MainPanel.test.tsx`) — STEP 5 테스트 요구 · 기존 큰 파일(1298 · 1406줄)에 섞지 않기 위해서. 3-4 구현에서 추가: `frontend/app/components/KospiStatusNote.tsx`(설계자 '두 화면 같은 생성기 공유') · `KospiStatusNote.test.tsx` · `tests/test_poc3_02d_ops02_kospi_display.py` |
| 전후 hash | PC `state/`(STEP 1 방식) · 운영 DB(`market_data.sqlite` · `runtime_state.sqlite` · `decision_evidence.sqlite`) · 운영 파일(러너 등) |

---

## 9. KS-10 (2026-09-27 `wc -l` 실측)

| 파일 | 줄 | 비고 |
|---|---|---|
| `scripts/run_three_push_runtime_oci.py` | 646 | 변경 0(상한 648) |
| `app/api.py` | 641 | 건드리지 않음 |
| `scripts/ops02c/reverse_verify_guards.py` | 638 | 건드리지 않음(보고만) |
| `app/holdings_market_evidence.py` | 616 | 건드리지 않음 |
| `app/runtime_evidence/holdings_risk_flow.py` | 491 | 3-2 · 약 +5 |
| `app/runtime_evidence/intraday_alert_flow.py` | 468 | 주석만 |
| `app/runtime_evidence/sector_signal_state.py` | 325 | 3-2 · 약 +15 |
| `scripts/ops02b2/reverse_verify_guards.py` | 328 | 3-3 · ⑦ 교체 |
| `scripts/build_market_briefing_mockups.py` | 459 | 3-3 |
| `frontend/app/components/MarketDiscoveryView.tsx` | 825 | 건드리지 않음 |
| `tests/test_market_briefing_contracts.py` | 1406 | 문구 1줄만(새 테스트 추가 금지) |
| `tests/test_intraday_alert_flow_through.py` | 1298 | 추가 0 |
| `tests/test_poc3_02d_ops01_holdings_risk_flow.py` | 944 | 추가 0(OPS-01 전용) |

---

## 10. 검증 (설계자 STEP 5 대응)

1. 계약 테스트 · 2. run() 관통 · 3. 5개 실패 · 잘림 시나리오 무력화(기준 커밋 사본 RED → GREEN) · 4. 프론트 라우팅 · 상태 표시 테스트 · 5. 백엔드 전체 회귀(background) · 6. 프론트 vitest · tsc · lint · 7. black · flake8 · 8. KS-10 전수 · 9. PC 라이브 state · 운영 DB 전후 hash 동일 · 10. OCI 쓰기 · Telegram 발송 0.

결과서에 OBSERVATION_STATE · DELIVERY_STATE · ACTUALLY_INCLUDED_SIGNALS · SUCCESSFULLY_DELIVERED_SIGNALS · PENDING_FOR_NEXT_TICK 을 시나리오별로 나눠 싣는다.

## 11. 문서 갱신

- `docs/PROGRAM_TRUTH.md`: 장중 급등락 절(알려진 결함 → 새 계약) · §5.2 OCI 링크 ⚠ 문장 · KOSPI 화면 서술(§8 · §13-4) · 부록 A.
- 02C-OPS-02 설계서 §15-2 는 설계자 문서라 개발자가 고치지 않는다 — Q1 판정을 이 PLAN · 결과서에 '계약 개정'으로 기록한다.
- `docs/STATE_LATEST.md`: 종료 기록.
