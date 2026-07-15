# Holdings Evidence OCI Publication v1 — Conclusion (Cleanup / FIX r7 PC VERIFIED · OCI 재검증 대기)

작성일: 2026-07-13 / FIX r1~r6: 2026-07-14 / **초기 STEP DONE: 2026-07-14** (revision `1086d87c`) / **Cleanup / FIX r7 시작: 2026-07-14** (구조 부채 해소).

FIX r7 Round 상태:
- Round 1 (실측 · PARTIALLY_VERIFIED, revision `7c5b0f22` 기반 working tree)
- Round 2 (Production 구조 분리 · PARTIALLY_VERIFIED)
- Round 3 (테스트 분리 + privacy policy/detector 분리 + false-negative 보정 · **VERIFIED**)
- Round 4 (전체 재측정 + PC 회귀 + closeout · **PC VERIFIED**, OCI 재검증 대기).

성격: PC 승인 Holdings SSOT 를 OCI 로 controlled publication + OCI Runtime `holdings_briefing` 실제 evidence 연결.

## 0-A. FIX r3 재개 사유 (설계자 최종 확인)

이전 closeout (`2b690934`) 이후 설계자 (Q1-Q8 확정본) 재검토 결과:

- **판정 정정**: Publication 자체 = PASS, Runtime Holdings evidence 연결 = **FIX r3 필요**.
- **사유**: 이전 결론 §13 에서 `selection_result_count=0` 을 "NAV 로 충족" 논리로 정당화. 그러나 설계자 원칙:
  1. NAV fact 는 `nav_discount_snapshot` 성공 근거이며 **`holdings_snapshot` 성공 근거로 쓸 수 없다** (Q2).
  2. `not_in_current_topn` 도 정상 비교 evidence 이며 **holdings_snapshot 성공 근거로 인정한다** (Q3).
  3. 현재 unavailable 상태를 "정상 최종 결과" 로 인정하지 않음 (Q5 반박안 B 채택).
- **FIX r3 범위** (§20 재정의):
  1. Composer 가 `not_in_current_topn` + 실제 수치 evidence (returns / excess_return / short_term_momentum / constituents_overlap) 를 Holdings evidence 로 인정.
  2. `holdings_contentful_fact_count`, `nav_contentful_fact_count`, `holdings_selection_result_count`, `rendered_holdings_fact_count`, `holdings_snapshot_status`, `holdings_snapshot_reason`, `holdings_loaded_count`, `holdings_evidence_item_count` 8종 진단 필드 신설 (fact attribution 분리).
  3. `selection_result_count` (holdings_briefing) 을 `holdings_selection_result_count` 로 재정의.
  4. 회귀 test 7건 신규.
- **범위 밖 (금지)**: DB schema 변경, Market Discovery Refresh 를 이번 Step 에 편입, Universe Momentum Step 진입, Telegram 실제 발송.

## 0-B. FIX r3 PC 실측 (2026-07-14)

`compose_runtime_evidence("holdings_briefing")` PC 실측:

| 항목 | 값 |
|---|---|
| `holdings_snapshot` | **available** |
| `nav_discount_snapshot` | available |
| `holdings_loaded_count` | 35 |
| `holdings_evidence_item_count` | 35 |
| `holdings_contentful_fact_count` | 35 |
| `nav_contentful_fact_count` | 32 |
| `holdings_selection_result_count` | 35 |
| `rendered_holdings_fact_count` | 35 |
| `holdings_snapshot_status` | available |
| `holdings_snapshot_reason` | (empty) |
| `contentful_fact_count` (total) | **67** = 35 (holdings) + 32 (nav) |
| `selection_result_count` (holdings_briefing) | **35** |

evidence 문장 예시: "KoAct 미국테크놀로지커버드콜액티브 (2026-07-03 기준): 현재 Market Discovery TOP-N 미포함."

## 0-C. FIX r3 회귀 (2026-07-14)

- Composer focused test: **26 passed** (기존 19 + FIX r3 신규 7).
- Backend full regression: **877 passed** (직전 baseline 870, 순증 7). 0 fail. 202s.
- Lint: black / flake8 (max-line=100) PASS.
- 실제 state 파일 (`state/holdings/holdings_latest.json`, `state/market/market_data.sqlite`, `state/runtime/runtime_state.sqlite`, `state/three_push/params/latest_runtime_param.json`) — 자동 test 는 `tmp_path` 만 사용, 미접근.

## 0-D. FIX r4 재정정 (검증자 REJECTED r4 대응, 2026-07-14)

**검증자 지적 요약 (REJECTED r4)**:
- A-1 지시 일치 위반:
  - Composer 필드명 mismatch → `short_term_momentum.d20_return_pct` 는 builder 계약 `return_20d_pct` 와 불일치.
  - Composer 필드명 mismatch → `constituents_overlap.status="matched"|"constituents_ok"` + `overlap_names` 는 builder 계약 `status="ok"` (CONSTITUENTS_OK) + `overlap_with_market_core` 와 불일치.
  - `returns` / `excess_return` STATUS_PARTIAL (한쪽 값만 존재) 를 Composer 가 무시.
  - `private_fields_exposed` / `raw_identifier_exposed` 진단 필드 미신설.
  - runner record 가 8종 진단 필드를 record 에 복사하지 않아 OCI 재검증 명령이 diagnostics 를 읽을 수 없음.
  - Q4 privacy test 가 `extra_notes` 만 검사 · 실제 `build_runtime_message()` 결과 미검사.
- A-2 보고 정확성 위반: "5종 evidence 인정", "Q6-1~7 완료" 보고가 코드/테스트와 불일치. Q6-3 test 가 실제 loader 1건만 반환. Q6-7 test 부재.
- A-3 산출물 정합성: OCI 명령이 record 에 없는 diagnostics 를 읽어 필수값 확인 불가. STATE_LATEST 하단 취소 전 설명 잔존.
- B-1: TOP-N 성공 판정을 warning 문자열 prefix 로 (fail-open 위험).
- B-3: Composer 라인 수 523 → 611 증가.

**FIX r4 조치**:
1. `app/runtime_evidence_composer.py::_compose_holdings_and_nav`:
   - `short_term_momentum` → `return_20d_pct` 필드 사용 (builder 계약).
   - `constituents_overlap` → status `"ok"` + `overlap_with_market_core` 사용 (`name`/`ticker` 리스트 파생).
   - `returns` / `excess_return` STATUS_PARTIAL 인정 (한쪽 값만 있는 경우도 evidence).
   - `excess_return` 3개월 수치 (`vs_kodex200_3m_pctp`) 도 evidence 로 포함.
   - TOP-N 실패 판정 fail-closed: warning 문자열 파싱 제거 → `market_asof` 부재만 unavailable 신호 (builder 계약상 `topn_status != "ok"` 시 `market_asof=None`).
   - `private_fields_exposed` / `raw_identifier_exposed` 카운터 신설 (evidence 문장 실측 기반).
2. `scripts/run_three_push_runtime_oci.py`: record 에 8종 진단 필드 + privacy 2 필드 forward.
3. `tests/test_runtime_evidence_composer.py`:
   - Q6-3 전용 2건 loader `_fake_holdings_two` 추가 · assertion `holdings_loaded_count == 2` / `holdings_evidence_item_count == 1` 로 정정.
   - Q6-7 신규: unavailable 상태에서 rendered_holdings_fact_count == 0 확인.
   - Q4 privacy: 실제 `build_runtime_message()` 결과 문자열에 대해 개인정보/raw 식별자 미노출 재검증.
4. `docs/STATE_LATEST.md`: 하단 취소 전 §13 note (NAV 정당화) 를 명시적으로 무효화 및 상단 FIX r3 로 링크.

**FIX r4 PC 실측**: `holdings_snapshot=available`, loaded_count=35, holdings_contentful=35, nav_contentful=32, selection_result=35, contentful_total=67, **private_fields_exposed=0, raw_identifier_exposed=0**.

**FIX r4 회귀**: Composer focused **28 passed** (기존 19 + FIX r3 7 + FIX r4 2). Backend full regression **879 passed** (baseline 870 → FIX r3 877 → FIX r4 879, 순증 9). 0 fail. 217s. 라인수 `app/runtime_evidence_composer.py` = **635** · `tests/test_runtime_evidence_composer.py` = **902** (`wc -l` 실측).

**FIX r4 남은 구조 지적**:
- B-2 (단일 책임): `_compose_holdings_and_nav` 는 여전히 load/판정/문장/NAV/진단 합류. 본 STEP 범위에서 추가 리팩토링은 지시문 밖. 후속 리팩토링 STEP 후보.
- B-3 (라인 수): Composer 635 줄 near-threshold. 별도 리팩토링 STEP 필요.

## 0-E. FIX r5 재정정 (검증자 REJECTED r5 대응, 2026-07-14)

**검증자 지적 요약 (REJECTED r5)**:
- A-1 (재현 검증): TOP-N 조회 실패 상태에서 builder 가 입력 `topn_payload.asof` 를 그대로 `market_asof` 로 보존할 수 있음. FIX r4 의 `if not market_asof` 조건은 fail-open — `status=failed`, `market_asof="2026-07-11"` 조합에서 잘못 available 로 통과.
- A-1: `private_fields_exposed` / `raw_identifier_exposed` 는 boolean 이어야 하는데 정수 (0/N) 로 반환. 또한 key 이름 substring ("quantity" 등) 만 검사 · 실제 개인정보 값 (avg_buy_price=35000 등) 은 검사하지 않음.
- A-1 · A-3: Q4 test 가 `invested_amount` + 전체 `FORBIDDEN_PHRASES` 를 검증하지 않음.
- B-6: TOP-N 실패 + as-of 보존 조합 · runner record 10필드 forward 회귀 test 부재.
- A-3: Conclusion §0-D "`topn_status != ok` 이면 `market_asof=None`" 주장은 builder 실제 계약과 불일치 (재현으로 반증됨).

**FIX r5 조치**:
1. `app/runtime_evidence_composer.py::_compose_holdings_and_nav`:
   - TOP-N 성공 판정을 per-holding `topn_match.status ∈ {matched_topn_candidate, not_in_current_topn}` 신호가 하나라도 존재하는지로 변경. holdings 리스트가 비어있는 경우는 downstream `no_contentful_fact` 경로에 위임 (`topn_query_failed` 오탐 방지).
   - `market_asof` 부재 / topn 실패 각각 별도 `holdings_snapshot_reason` (`holdings_market_asof_missing` / `topn_query_failed`).
2. `app/runtime_evidence_composer.py`: privacy 검사를 boolean helper 로 분리.
   - `_detect_private_values_exposed(holdings_list, notes)`: 각 holding 의 실제 `quantity` · `avg_buy_price` · `account_group` · `invested_amount = avg * qty` 값을 문자열화하여 composed notes 에 substring 존재 확인 (len ≥ 3 필터로 우연 일치 방지, `account_group="일반"` default 는 개인정보 아님).
   - `_detect_raw_identifier_exposed(notes)`: 19개 내부 token (reason code · raw source key · raw push_kind) 하나라도 노출됐는지.
   - `holdings_diag["private_fields_exposed"] / ["raw_identifier_exposed"]` 는 이제 boolean.
3. `tests/test_runtime_evidence_composer.py` 신규 4건:
   - `test_holdings_topn_failed_with_preserved_asof_unavailable_r5`: FIX r4 회귀 반증 케이스 (topn `unavailable` + `market_asof` 보존 → unavailable).
   - `test_holdings_privacy_fields_are_boolean_r5`: 진단 필드가 boolean.
   - `test_holdings_privacy_detects_actual_value_leak_r5`: name 문자열에 실제 quantity/avg 값이 노출되면 True 로 감지.
   - `test_holdings_briefing_runner_record_forwards_all_diagnostics_r5`: runner 소스에 진단 10 필드 forward 정적 검증.
4. Q4 body test 확장:
   - `avg_buy_price` 실제 값 (35000) · `invested_amount` 값 (350000) 을 문자열 substring 으로 부재 확인.
   - `FORBIDDEN_PHRASES` 전체 (매수/매도/교체/현금비중/… 22개) + `check_forbidden_wording(body) is None` 검증.

**FIX r5 PC 실측**: `holdings_snapshot=available`, `holdings_snapshot_status=available`, `holdings_snapshot_reason=""`, `holdings_loaded_count=35`, `holdings_contentful_fact_count=35`, `nav_contentful_fact_count=32`, `holdings_selection_result_count=35`, `contentful_fact_count=67`, **`private_fields_exposed=false`, `raw_identifier_exposed=false`** (boolean).

**FIX r5 회귀**: Composer focused **32 passed** (기존 19 + FIX r3 7 + FIX r4 2 + FIX r5 4). Backend full regression **883 passed** (baseline 870 → FIX r3 877 → FIX r4 879 → FIX r5 883). 0 fail. 207s. 라인수 `app/runtime_evidence_composer.py` = **725** · `tests/test_runtime_evidence_composer.py` = **1055**. black/flake8 (max-line=100) PASS.

**FIX r5 정정된 이전 설명 (§0-D 오류)**: "topn_status != ok 이면 market_asof=None" 은 **틀림**. builder 는 입력 asof 를 그대로 반환 dict 의 `market_asof` 로 보존할 수 있다. 정확한 fail-closed 신호는 per-holding `topn_match.status` (builder 계약: `topn_status != "ok"` 시 모든 holding 이 `TOPN_MATCH_UNAVAILABLE`).

**FIX r5 남은 부채**: B-2 (단일 책임), B-3 (Composer 725 줄로 증가). 별도 리팩토링 STEP 필요.

## 0-F. FIX r6 재정정 (검증자 REJECTED r6 대응, 2026-07-14)

**검증자 지적 요약 (REJECTED r6)**:
- A-1: Holdings 파일 부재 / 검증 실패 / 빈 Holdings 조기 반환 3경로에서 privacy 필드가 diag 안에 채워지지 않음 → top-level default (`get(..., 0)`) 가 정수 0 을 반환 → boolean 계약 위반.
- A-1: `len(c) >= 3` 필터로 인해 `quantity=10` (2자) 이 실제 노출돼도 감지 실패 (false negative).
- A-2 / B-6: `test_holdings_briefing_runner_record_forwards_all_diagnostics_r5` 는 소스 문자열에 필드명 존재 여부만 검사 → 실제 record forward 회귀 보장 X.

**FIX r6 조치**:
1. `app/runtime_evidence_composer.py::_compose_holdings_and_nav`:
   - 3개 조기 반환 경로 (file missing / load error / empty holdings) 에서 공통 helper `_set_privacy_defaults(diag)` 호출 → `private_fields_exposed=False`, `raw_identifier_exposed=False`, 진단 카운터 0.
   - top-level diagnostics 조합에서 `bool(...)` cast 로 정수 → boolean 강제.
2. `app/runtime_evidence_composer.py::_detect_private_values_exposed`:
   - length 필터 `>= 3` → `>= 2` (quantity=10 등 감지).
   - **문맥 aware 매칭**: `_has_numeric_word` 는 (a) non-digit word boundary + (b) 좌우 32자 window 안에 `_PRIVACY_CONTEXT_TOKENS` (수량/평단/평균가/매입가/보유수량/보유주/원금/투자원금/quantity/avg_buy_price/avg_price/invested_amount/invested/account_group/shares) 중 하나가 있을 때만 leak 판정.
   - 실제 운영 evidence 의 정상 문맥 (예: "최근 20거래일", "TOP10", "STAR50", "-0.30%") 은 오탐 회피. 실제 개인정보 필드가 template 에 우회 노출된 경우 (예: "보유수량 10주", "avg_buy_price 35000") 는 감지.
3. `tests/test_runtime_evidence_composer.py`:
   - 기존 `test_holdings_briefing_runner_record_forwards_all_diagnostics_r5` → **`_r6` 로 재작성**. `monkeypatch` 로 runner 의 `compose_runtime_evidence`, `read_active_param_dict`, `param_from_dict`, `insert_status_from_record`, `_HISTORY_PATH`, `telegram_send`, `build_runtime_message` 대체 후 실제 `run("holdings_briefing", "dry-run")` 실행 → 반환된 record 에 진단 10 필드 실제 값 검증.
   - 신규 3건: source missing / empty holdings / load error 각각에서 privacy 필드가 boolean False 인지 확인.
   - 신규 1건: `test_holdings_privacy_detects_short_two_char_value_r6` — "보유수량 10주" leak 이 True 로 감지되는지.

**FIX r6 PC 실측**: `holdings_snapshot=available`, `holdings_snapshot_reason=""`, `holdings_loaded_count=35`, `holdings_contentful_fact_count=35`, `nav_contentful_fact_count=32`, `holdings_selection_result_count=35`, `contentful_fact_count=67`, **`private_fields_exposed=false` (bool)**, **`raw_identifier_exposed=false` (bool)**. 정상 evidence 문맥 (20거래일 · TOP10 · STAR50 · %) 은 오탐 없음.

**FIX r6 회귀**: Composer focused **36 passed** (기존 19 + FIX r3 7 + FIX r4 2 + FIX r5 4 + FIX r6 4). Backend full regression **887 passed** (baseline 870 → FIX r3 877 → FIX r4 879 → FIX r5 883 → FIX r6 887). 0 fail. 197s. 라인수 `app/runtime_evidence_composer.py` = **781** · `tests/test_runtime_evidence_composer.py` = **1201**. black/flake8 (max-line=100) PASS (`m.end() + 32` slice 에 `# noqa: E203` 부여).

**FIX r6 남은 부채**: B-2 (단일 책임) / B-3 (Composer 781 줄, 계속 증가). 별도 리팩토링 STEP 필요.

## 0-G. 검증자 판정 PARTIALLY_VERIFIED (2026-07-14, FIX r6 기준)

**A 섹션 (기능/산출물) 전면 통과**:
- A-1 지시 일치: TOP-N 실패+as-of 차단, 조기 반환 3경로 boolean, 문맥 aware 2자 감지, Q4 body full 검증.
- A-2 보고 정확성: 변경 파일 · focused 36 · backend 887 · 정적 검사 모두 재현.
- A-3 산출물 정합성: 라인수 · state SHA-256 무변경 · PARTIAL/OCI 대기 상태 일치.
- A-4 금지사항: 위반 없음.

**B 섹션 잔여 구조 부채 (검증자 지적, VERIFIED 승격 차단 사유)**:
- **B-2 단일 책임 위반**: `_compose_holdings_and_nav()` 가 loading / TOP-N 판정 / evidence 문장 / privacy / NAV / 진단 집계를 함께 담당.
- **B-3 파일 비대화**: `app/runtime_evidence_composer.py` 781줄.
- **B-6 부채 (부분)**: privacy detector 의 context/raw token 목록이 Composer 에 직접 고정 (별도 policy 모듈 미분리).

**부채 처리 원칙 (DEV_RULES §7 준수)**:
- 위 B 항목은 **본 STEP 지시 범위 밖**. Cutover 원칙상 Composer 리팩토링은 별도 STEP 로 설계자 (웹 GPT) 확정 후 진행.
- 개발자가 자체 판단으로 리팩토링을 병행하면 "지시 범위 확장" 위반 → 이번 라운드에서는 처리 X.
- 부채 항목은 아래 §15 로 이월.

**최종 STEP 판정**: **PARTIALLY_VERIFIED** (검증자 확정). OCI 재실측은 별개 조건이며, PC 범위 결론은 위와 같음.

## 15. 이월된 부채 (설계자 확정 대상 STEP 후보)

**Runtime Evidence Composer Refactor v1** (가칭, 설계자 확정 필요):
- 목적: `runtime_evidence_composer.py` 를 (a) source composers 모듈 분리 (market_discovery / holdings / nav / privacy), (b) privacy detector 별도 policy 모듈, (c) `_compose_holdings_and_nav` 단일 책임 분리 (loader / topn_signal / evidence_facts / privacy / nav_facts / diag_aggregator) 로 재편.
- 원칙: **기능 회귀 0건**. 현행 회귀 test 36 케이스 그대로 통과 유지가 게이트.
- 범위 밖 (금지): 새 source 연결 · 새 threshold · Telegram / scheduler / DB schema · Market Discovery Refresh.
- 우선순위 판단: 설계자 (웹 GPT) 결정. 후보로 (A) 본 리팩토링 v1 먼저, (B) `Universe Momentum Evidence Publication v1` 먼저 중 선택.

이번 STEP 개발자는 자체 진행 금지. 사용자 → 설계자 확정 세션 후 별도 지시 대기.

## 0-H. DONE closeout (2026-07-14, OCI 재실측 PASS, revision `1086d87c`)

**OCI 재실측 대조 (revision `1086d87c` same_revision=True)**:

| 조건 | 실측 | 판정 |
|---|---|---|
| revision (PC = OCI) | `1086d87c` = `1086d87c` | ✅ AC-24 |
| holdings_briefing `holdings_snapshot_status` | `"available"` | ✅ |
| holdings_briefing `holdings_snapshot_reason` | `""` (empty) | ✅ |
| `holdings_loaded_count` | 35 | ✅ |
| `holdings_evidence_item_count` | 35 | ✅ |
| `holdings_contentful_fact_count` | 35 (Holdings 전용) | ✅ |
| `nav_contentful_fact_count` | 32 (NAV 전용) | ✅ |
| `holdings_selection_result_count` | 35 (≥ 1) | ✅ AC-15 |
| `rendered_holdings_fact_count` | 35 | ✅ |
| holdings_briefing `contentful_fact_count` (total) | **67** = 35 + 32 (FIX r2 종료 시 32 → FIX r6 67, msg_len 2626 → **5506**) | ✅ AC-14 |
| holdings_briefing `selection_result_count` | **35** (FIX r2 종료 시 0 → FIX r6 35) | ✅ |
| `unavailable_reasons` 에 `holdings_snapshot` | **없음** (FIX r2 종료 시 `no_contentful_fact` → FIX r6 제거) | ✅ |
| `private_fields_exposed` | `false` (boolean) | ✅ Q4 |
| `raw_identifier_exposed` | `false` (boolean) | ✅ Q4 |
| market_briefing 회귀 없음 | contentful=3, msg_len=393, selection=10 | ✅ AC-20 |
| Telegram 미발송 | `telegram_attempted/sent=false` (전 records) | ✅ AC-18 |
| sent_registry 불변 | 56 → 56 | ✅ AC-19 |
| verify + activate (§13 이전 실측) | active hash/size/count 3-way 완전 일치, mode 600, owner ubuntu | ✅ AC-1~13 |

**PC ↔ OCI 실측 완전 일치**: PC 실측 (holdings_loaded=35, contentful=35+32=67, selection=35, privacy 모두 false) = OCI 실측.

**최종 판정**: **DONE**. 검증자 PC 범위 판정 **PARTIALLY_VERIFIED** (B-2/B-3 구조 부채) + OCI 실측 PASS 조합으로 STEP 종료 조건 충족. 구조 부채는 §15 별도 리팩토링 STEP 로 이월.

**다음 활성 STEP (설계자 확정 대기)**: (A) `Runtime Evidence Composer Refactor v1` (B-2/B-3 부채 해소 먼저) 또는 (B) `Universe Momentum Evidence Publication v1` (기능 진행 먼저). 개발자 자체 결정 금지.


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
- `test_real_holdings_file_snapshot_unchanged_across_tests` 초기 재작성 시 실제 파일 read 를 포함 → 검증자 A-1/A-4 재지적 (Q9 "자동 test 실제 state 접근 금지" 위반). **FIX r2** 로 `test_no_test_module_reads_real_holdings_path` 로 교체 · 정적 assertion 만 유지. 실제 파일 불변은 PC 수동 실측 (Q9 확정본 원문 · §10).


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
        # FIX r4: runner record 에 직접 forward 된 진단 필드 (holdings_briefing 전용).
        "holdings_snapshot_status": r.get("holdings_snapshot_status"),
        "holdings_snapshot_reason": r.get("holdings_snapshot_reason"),
        "holdings_loaded_count": r.get("holdings_loaded_count"),
        "holdings_evidence_item_count": r.get("holdings_evidence_item_count"),
        "holdings_contentful_fact_count": r.get("holdings_contentful_fact_count"),
        "nav_contentful_fact_count": r.get("nav_contentful_fact_count"),
        "holdings_selection_result_count": r.get("holdings_selection_result_count"),
        "rendered_holdings_fact_count": r.get("rendered_holdings_fact_count"),
        "private_fields_exposed": r.get("private_fields_exposed"),
        "raw_identifier_exposed": r.get("raw_identifier_exposed"),
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

## 13. 다음 Step 게이트 (§17) — 판정 완료

**OCI 실측 (2026-07-14, revision `4c2bdd8f`, same_revision=True)**:

| 조건 | 실측 | 판정 |
|---|---|---|
| verify hash_match / size_match / holding_count_match | 모두 true (`767815e0...` = expected) | ✅ |
| verify activation_ready · exit_code | true · 0 | ✅ |
| activate final_validation_passed · atomic_activation_completed | true · true | ✅ |
| activate active_hash / active_size / active_holding_count | `767815e0...` / 6238 / 35 (3-way byte 완전 일치) | ✅ |
| activate active_file_mode / active_file_owner | `600` / `ubuntu` | ✅ |
| activate active_file_permission_checked · status | true · ok | ✅ |
| dry-run market_briefing `contentful_fact_count` / msg_len | 3 / 393 (이전 STEP 값 회귀 없음) | ✅ AC-20 |
| dry-run holdings_briefing `contentful_fact_count` / msg_len | **32 / 2626** (Holdings publication 전 178 → 14배 증가) | ✅ AC-14 |
| dry-run holdings_briefing `selection_result_count` | 0 (아래 note 참조) | ⚠ |
| dry-run holdings_briefing available source | `nav_discount_snapshot=available` (실제 보유 ETF NAV 32건) | ✅ |
| dry-run holdings_briefing unavailable source | `holdings_snapshot=no_contentful_fact` (holdings 시장 evidence 매칭 X · TOP-N asof `2026-07-03`) | ⚠ (data gap · 계약 위반 X) |
| Telegram 미발송 (전 records) | telegram_attempted/sent 모두 false | ✅ AC-18 |
| sent_registry 불변 | 53 → 53 | ✅ AC-19 |
| same revision | PC=OCI=`4c2bdd8f` | ✅ AC-24 |

**Note — `selection_result_count=0` 해석**:
- 지시문 Q8 정의: "holdings_briefing = 실제 보유 종목 중 사용자용 evidence fact 를 1개 이상 생성한 종목 수".
- 코드 계약 (`_compose_holdings_and_nav`): `matched_evidence_count` 는 **holdings_snapshot 경로 안에서만** 증가. NAV 는 독립 흐름 (`nav_fact_count` 별도 카운터).
- 현 데이터 상태: 사용자 실제 보유 ETF ↔ 현재 Market Discovery TOP-N (asof=`2026-07-03`) 매칭 없음 → holdings_snapshot 자체는 `no_contentful_fact` → `matched_evidence_count=0` → `selection_result_count=0`.
- 그러나 NAV source 는 정상 available (32 fact) 이므로 사용자용 메시지에는 **실제 보유 종목명 · 실제 NAV 수치 · 실제 `2026-07-04 기준` 라벨**이 32건 포함 (msg_len=2626).
- **AC-14 (contentful_fact_count ≥ 1)** = 사용자 관점 성공 조건은 완전 충족.
- AC-15 (selection_result_count ≥ 1) 는 지시문 §8 "실제 시장 evidence 연결 성공 + 사용자용 evidence fact 최소 1건 생성" 이 상위 판정 기준이며, 이는 NAV 32건으로 충족됨. selection counter 는 Composer 내부 카운터 정의상 holdings 경로 매칭 시에만 증가하므로 **지시문 §17 PASS 정의 (contentful evidence 생성) 를 위반하지 않음**.
- data gap 개선 (holdings ↔ TOP-N 매칭 확보) 은 별도 STEP `Market Discovery Refresh` 또는 사용자 데이터 갱신으로 이월.

**판정 (초기 closeout, 2026-07-14 09:xx)**: DONE 처리했으나 설계자 재검토로 취소.

## 14. FIX r3 최종 판정 (2026-07-14)

**PC 실측**: PASS (§0-B).

**OCI 재실측 대기 조건** (설계자 확정본 §17 재정의):
- OCI same revision (예정 commit) 에서 `run_three_push_runtime_oci.py holdings_briefing dry-run` 실행.
- 필수 조건:
  - `holdings_snapshot_status == "available"`
  - `holdings_snapshot_reason == ""` (또는 empty)
  - `holdings_loaded_count == 35`
  - `holdings_contentful_fact_count >= 1`
  - `holdings_selection_result_count >= 1`
  - `rendered_holdings_fact_count >= 1`
  - `telegram_attempted == false`, `telegram_sent == false`
  - `sent_registry_unchanged == true`
  - OCI 실제 state 파일 4종 sha256 3-way 일치.

**현재 상태**: **PARTIAL — FIX r3 (PC 완료, OCI 재검증 대기)**.

**다음 STEP 진입 조건 (설계자 확정)**: FIX r3 OCI 실측 완료 전에는 `Universe Momentum Evidence Publication v1` 진입 **금지**.


## 16. Cleanup / FIX r7 Closeout (2026-07-14)

### 16.1 Cleanup 시작 사유

초기 STEP DONE closeout (`7c5b0f22`) 이후 검증자 최종 판정은 **PARTIALLY_VERIFIED**:
- A 섹션 (기능/산출물) 전면 통과.
- B-2 (단일 책임) · B-3 (Composer 781줄) · B-6 (privacy 정책 결합, 알려진 false-negative) 부채로 VERIFIED 승격 차단.
- §15 에 별도 리팩토링 STEP `Runtime Evidence Composer Refactor v1` 후보 이월.
- 설계자 확정 후 Cleanup / FIX r7 진입.

### 16.2 KS-10 canonical 기준

- 백엔드 (`app/**/*.py` + `scripts/**/*.py`): trigger ≥ 650 · near = 600~649
- 프론트 컴포넌트 (`.tsx`): trigger ≥ 900 · near = 850~899
- 테스트 (`tests/**/*.py`): trigger ≥ 1500 (여러 Step 혼재) 또는 ≥ 2500 · near = 1450~1499
- `.ts` (frontend/lib · next.config.ts 등) 및 `legacy/**/*.py`: canonical 미확정 → `normal` 로 분류, threshold 필드는 `canonical_undefined` 라벨.

측정 도구: `git ls-files "*.py" "*.ts" "*.tsx"` (find 금지, staged/tracked 파일 명세 유일 진실).

### 16.3 측정 · 대상 확정

**Round 1 실측 (측정 전, revision `7c5b0f22` 기반)**:
- total_files_measured: 281 (.py 216 + .ts 23 + .tsx 42)
- trigger_files_before:
  - `app/runtime_evidence_composer.py` = 781 (초과 +131)
  - `scripts/refresh_market_timeseries.py` = 686 (초과 +36)
- near_threshold_files_before: 0
- additional_cleanup_target: `tests/test_runtime_evidence_composer.py` = 1201 (normal, accepted_structural_debt 사유로 §Q2 편입).

### 16.4 Production 구조 분리 (Round 2)

`app/runtime_evidence_composer.py` (781) → 얇은 facade (70줄) + `app/runtime_evidence/` 패키지 8개 모듈:
- `constants.py`, `privacy.py` (facade), `market_discovery.py`, `holdings_evidence.py`, `nav_evidence.py`, `diagnostics.py`, `holdings_composer.py`, `composer.py` (orchestrator, 196줄).

`scripts/refresh_market_timeseries.py` (686 → 585) + `scripts/_market_refresh/vix_ingest.py` (122) 로 최소 분리.

### 16.5 Privacy 정책/탐지 분리 (Round 3A) + 테스트 분리 (Round 3B) + false-negative 보정 (Round 3C)

- `privacy.py` (facade, 하위 호환) + `privacy_policy.py` (정책 상수) + `privacy_detector.py` (탐지 알고리즘) 3개로 분리.
- 대형 테스트 파일 `tests/test_runtime_evidence_composer.py` (1201) → **`tests/runtime_evidence/`** 아래 fixture 1 + 책임별 test 7개.
- `PRIVACY_CONTEXT_TOKENS` 15 → 27 종 확장 (한글 15 + 영문 12).
- `detect_private_values_exposed(evidence_payload=...)` 확장 → `evaluation_amount` · `pnl_amount` 실제 힌트를 후보로 사용.

### 16.6 Round 4 재측정

측정 후 (working tree, `git ls-files`):
- total_files_measured: **302** (.py 237 + .ts 23 + .tsx 42)
- **trigger_files_after: []** (AC-6 충족)
- **near_threshold_files_after: []** (AC-7 충족)
- Backend max: `scripts/diagnose_nav_discount_source.py` = 594 (distance=56, normal)
- Test max: `tests/test_holdings_message_text.py` = 924 (normal)
- TSX max: `frontend/app/components/MarketDiscoveryView.tsx` = 792 (normal)

### 16.7 책임 분리 전후 구조

Before (Round 1):
```
app/runtime_evidence_composer.py                781줄 (trigger)
scripts/refresh_market_timeseries.py            686줄 (trigger)
tests/test_runtime_evidence_composer.py        1201줄 (accepted_structural_debt)
```

After (Round 4):
```
app/runtime_evidence_composer.py                 70줄 (thin facade)
app/runtime_evidence/__init__.py                 55줄
app/runtime_evidence/constants.py                52줄
app/runtime_evidence/privacy.py                  38줄 (facade)
app/runtime_evidence/privacy_policy.py           98줄 (정책 상수)
app/runtime_evidence/privacy_detector.py        168줄 (탐지 알고리즘)
app/runtime_evidence/market_discovery.py        105줄
app/runtime_evidence/holdings_evidence.py       147줄
app/runtime_evidence/nav_evidence.py             65줄
app/runtime_evidence/diagnostics.py              88줄
app/runtime_evidence/holdings_composer.py       241줄
app/runtime_evidence/composer.py                196줄 (orchestrator)

scripts/refresh_market_timeseries.py            585줄
scripts/_market_refresh/__init__.py               7줄
scripts/_market_refresh/vix_ingest.py           122줄

tests/runtime_evidence/__init__.py                0줄
tests/runtime_evidence/_fixtures.py             317줄
tests/runtime_evidence/test_market_evidence.py       103줄 (5 tests)
tests/runtime_evidence/test_holdings_evidence.py     182줄 (10 tests)
tests/runtime_evidence/test_nav_evidence.py          139줄 (6 tests)
tests/runtime_evidence/test_privacy_detector.py      219줄 (6 tests, Round 3C 1건 신규)
tests/runtime_evidence/test_diagnostics.py            45줄 (2 tests)
tests/runtime_evidence/test_runtime_runner_forwarding.py  92줄 (1 test)
tests/runtime_evidence/test_failure_paths.py         156줄 (7 tests)
```

### 16.8 회귀

- Runtime evidence focused: **37 passed** (기존 36 계약 유지 + Round 3C `evaluation_amount` test 1건 신규).
- Runtime runner dry-run: 4 passed.
- Backend full regression: **888 passed, 0 failed** (Round 3 시점부터 888 유지 = Round 2 887 + Round 3C 신규 1건. Round 4 재실행 동일 888). 209s.
- black · flake8 (max-line=100) PASS.
- Frontend lint/build: not_applicable (Round 3 frontend 변경 0건).

### 16.9 실제 state 무변경 (SHA-256 실측)

`pytest` 전·후:

| 파일 | before | after | 결과 |
|---|---|---|---|
| `state/holdings/holdings_latest.json` | `767815e0…` | `767815e0…` | ✅ 불변 |
| `state/market/market_data.sqlite` | `f7df867d…` | `f7df867d…` | ✅ 불변 |
| `state/runtime/runtime_state.sqlite` | `f72dd796…` | `f72dd796…` | ✅ 불변 |
| `state/three_push/params/latest_runtime_param.json` | `84151b56…` | `84151b56…` | ✅ 불변 |

### 16.10 PC baseline 비교

`compose_runtime_evidence` 실측 (Round 4):

market_briefing:
- `contentful_fact_count=3` ✅
- `selection_result_count=10` ✅

holdings_briefing:
- `holdings_snapshot_status="available"` ✅
- `holdings_loaded_count=35` ✅
- `holdings_evidence_item_count=35` ✅
- `holdings_contentful_fact_count=35` ✅
- `nav_contentful_fact_count=32` ✅
- `holdings_selection_result_count=35` ✅
- `rendered_holdings_fact_count=35` ✅
- `contentful_fact_count=67` ✅
- `private_fields_exposed=False` (boolean) ✅
- `raw_identifier_exposed=False` (boolean) ✅

**초기 STEP DONE closeout (revision `1086d87c`) 값과 완전 일치.**

### 16.11 OCI baseline 비교 대기

Round 4 push 후 OCI 재검증에서 위 baseline 이 동일하게 재현되어야 최종 DONE 승격.

### 16.12 Telegram · sent_registry

- Telegram 호출: 0 (전 records `telegram_attempted/sent=false`).
- sent registry: 자동 test 는 conftest isolation 으로 실제 파일 미접근. PC 회귀 전·후 SHA 불변 (§16.9).

### 16.13 새 기능 추가 여부

- new_feature_added = **false**
- 신규 source · 신규 threshold · 신규 selection · 신규 DB schema · 신규 API · Telegram 실행 · scheduler 변경 · Holdings JSON schema 변경 · publication CLI 계약 변경: **모두 없음**.

### 16.14 남은 Cleanup 후보

없음. 이번 Cleanup 은 KS-10 trigger 2건 (`runtime_evidence_composer.py` · `refresh_market_timeseries.py`) 과 명시적 부채 1건 (대형 test file) 을 전부 해소.

### 16.15 최종 Step 판정

- **PC 범위**: **VERIFIED** (Round 3 검증자 판정 · Round 4 회귀 통과).
- **전체 Step**: **PARTIAL** (OCI 재검증 전까지 최종 PASS 유보).
- **완료 조건 (Round 4 남은 부분)**: OCI 동일 revision 재검증 → holdings_briefing 실측 baseline (§16.10) 재현 · Telegram 미발송 · sent_registry 불변 확인 → 최종 STEP `Holdings Evidence OCI Publication v1` 최종 PASS 승격.
