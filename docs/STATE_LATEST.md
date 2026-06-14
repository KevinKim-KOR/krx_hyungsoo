# STATE_LATEST

최종 업데이트: 2026-06-13 (3-PUSH Runtime Package PC 검증)

## 0. Canonical

- **Canonical state file**: `docs/STATE_LATEST.md` (본 파일)
- **Step detail files**: `docs/handoff/<step_file>.md` (Step 종료 후에만 생성)
- **Past accumulation archive**: [docs/handoff/STATE_LATEST_ARCHIVE.md](handoff/STATE_LATEST_ARCHIVE.md)
  — 2026-05-14 ~ 2026-06-07 사이 시간순 누적 본문. 본 정리 이후로는 더 이상 append 하지 않는다.
- 본 파일에는 현재 상태 / history 요약 / Open decisions / Index 만 둔다. **Step 상세는 append 하지 않는다.**

### Step 상세 파일 생성 규칙

```text
Step 상세 파일은 Step 종료 후 다음 Step 으로 넘어갈 때 생성한다.
진행 중 Step 의 상세 파일은 미리 만들지 않는다.
docs/STATE_LATEST.md 에는 요약만 남기고, 상세는 docs/handoff/<step_file>.md 에 둔다.
```

## 1. Current position

- **프로젝트 큰 흐름**:
  보유 현황 입력 → 시세/평가 계산 → 시장 후보 발굴(Market Discovery) → 구성종목 / 중복 분석(ETF Exposure)
  → 보유 vs 시장 Evidence → 판단 사유 있는 초안 생성(GenerateDraft) → 인간 승인 → OCI 전달 → Telegram 수신.
- **현재 완료 상태**: **3-PUSH Runtime Package PC 검증** (2026-06-13).
  - `three_push_runtime_package.v1` 구조를 PC 에서 실제 evidence + runtime probe (네이버 국내 시세 + Yahoo Finance 미국 지수 3종 Nasdaq/SPX/SOX) 로 생성해 Approval/Telegram preview 에서 상태 확인 가능한 상태까지 검증. 3종 push_kind 모두 `draft_payload.runtime_package` 에 schema_version `three_push_runtime_package.v1` 저장 — OCI handoff JSON 으로도 자동 전달 (store.write_handoff_artifact 변경 0건).
  - **신규 PUSH 전용 endpoint 0건 (Q3 사용자 결정)**: PUSH-1/3 은 기존 `POST /runs/generate + input_data.push_kind` 분기, PUSH-2 는 기존 `POST /runs/generate-from-holdings` 유지. holdings 데이터 의존성으로 PUSH-2 endpoint 통합 강요는 과한 설계자 지시였음 — 사용자 결정으로 분리 유지.
  - **신규 dependency 0건 (Q1 사용자 결정)**: `urllib` + `json` + `http.cookiejar` 만 사용. `requests` / `yfinance` 추가 없음.
  - 신규 backend 모듈 5종 (FIX r2/r3 후 실측): `app/runtime_us_indices_probe.py` (**171 라인**, Yahoo Finance chart endpoint + cookie jar 단일 opener 캐시 — rate-limit 회피), `app/runtime_kr_quote_probe.py` (**182 라인**, Naver polling endpoint), `app/runtime_probe_cache.py` (**133 라인**, 30분 TTL cache `state/runtime/three_push_runtime_probe_latest.json`), `app/runtime_package.py` (**292 라인**, three_push_runtime_package.v1 빌더 + push_kind 별 generation_status 산정, FIX r3 에서 failed 시 message_contract.message_text 빈 문자열 강제 + unavailable runtime 도 warning 처리), `app/push_context.py` (**247 라인**, FIX r2 추가 — push_kind 별 view 빌더, FIX r3 에서 빈 view 는 키 자체 생략). 모두 KS-10 안전.
  - 신규 frontend Card: `RuntimePackageStatusCard` (**204 라인**) — `draft_payload.runtime_package` 의 status / generation_status / kr·us probe 요약 + raw JSON details. 빈 slot placeholder 노출 0건 (`status==="unavailable"` 일 때 해당 행 자체 생략).
  - 수정 모듈 (KS-10 라인, FIX r2/r3/r4/r5/r6 후 실측): `app/draft.py` 465→**559 라인** (PUSH-2 `_build_holdings_payload` 에 runtime_package + push_context 키 추가 + FIX r4 동기화 가드 + FIX r5 Run.message_text 가드), `app/draft_three_push.py` 207→**344 라인** (PUSH-1/3 generate 함수에 cache-aware runtime probe + build_push_context + build_runtime_package 호출 + FIX r5 Run.message_text 가드), `app/delivery.py` 233→**251 라인** (FIX r6 — holdings fallback 분기에 runtime_package.generation_status=failed 체크 + DeliveryError 명시 차단). `write_handoff_artifact` 변경 0건 — draft_payload 전체 보존으로 runtime_package 자동 포함.
  - 실측 (live API + live probe, 2026-06-13 KST 오전): Nasdaq close=25,888.844 +0.70% / SPX close=7,431.46 +0.65% / SOX close=13,371.47 +9.42% / KODEX 200 price=129,270 +4.38% / KODEX 코스닥150 price=18,015 +2.15%. `POST /runs/generate` PUSH-1 generation_status=ok / PUSH-3 generation_status=ok / `POST /runs/generate-from-holdings` PUSH-2 generation_status=ok + message_text 2,507자 + runtime_package.message_contract.message_text 와 동일 (AC-6).
  - 30분 TTL cache 동작: cache miss → probe 1회 + 저장 (단, 두 snapshot 모두 failed 면 cache 저장 건너뜀 — 다음 호출이 즉시 재시도, B-6 정책), cache hit → probe 0건, TTL 만료 → 새 probe, force_refresh → bypass, 손상 → fall-through 후 재조회. 단위 테스트 7건 통과 (cache_miss / cache_hit / cache_expired / force_refresh / corrupted_cache / both_failed_not_cached / partial_cached).
  - 회귀 1건 해소: `tests/test_universe_seed.py::test_step5c_endpoint_does_not_affect_holdings_draft_flow` 의 `expected_keys` 에 `"runtime_package"` 추가 (Q4 — 신규 키 1건 허용, 기존 키 유지).
  - **FIX r2 (검증자 1차 REJECTED 후속, A-1/A-3/B-1/B-6 수용)**:
    (A-1 (1)) message_text 생성 흐름을 `runtime_package → push_context → message_text` 로 정렬. 신규 모듈 `app/push_context.py` 추가 (현재 라인 수는 §1 상단 신규 모듈 5종 표 참조 — FIX r3 보강 후 247 라인). push_kind 별 `market_view` / `holdings_view` / `spike_view` 빌더. `message_market_briefing.build_market_briefing_message` 와 `message_spike_alert.build_spike_alert_message` 에 `push_context` 옵션 인자 추가. PUSH-1 message_text 안에 `push_context.market_view.observations` 기반 `[밤사이 미국 시장 (runtime probe)]` 1줄 섹션 추가 — runtime probe ok 시에만 노출, failed/unavailable 시 섹션 자체 생략 (AC-7 placeholder 금지 유지). PUSH-3 도 `push_context.spike_view.items` 기반 `[universe momentum 관찰 (push_context 기반)]` 섹션 추가. PUSH-2 는 `push_context.market_view` 가 holdings_briefing 의 §7.2 필수 evidence 조건 (`holdings_snapshot + (market_view 또는 market_discovery_snapshot)`) 을 충족.
    (A-1 (2)) `runtime_package._check_holdings_briefing_requirements` 에 push_context.market_view 또는 pc_evidence.market_discovery_snapshot 존재 확인 추가 — 둘 다 없으면 generation_status=failed + missing_sections.
    (B-1) `_runtime_snapshot_with_cache` / `_runtime_snapshot_for_holdings` 의 broad `except Exception` 을 `except (OSError, TimeoutError)` 로 좁힘 — 코드 결함은 호출자에게 전파, I/O 실패만 흡수 + 예외 타입 logger.warning 명시.
    (B-6) `runtime_probe_cache._write_cache` — 두 snapshot 모두 failed/unavailable 인 경우 cache 저장 건너뛰는 `_both_failed` 가드 추가. 한쪽이라도 ok/partial 이면 저장 (다음 호출이 그대로 사용). 신규 테스트 2건.
  - **FIX r3 (검증자 2차 REJECTED 후속, A-1/A-3/B-1/B-6 수용)**:
    (A-1 (1)) `unavailable` 도 정상 통과 차단 — `push_context.build_market_view` / `build_holdings_view` / `build_spike_view` 가 observations/items 1건도 없으면 빈 dict 반환. `build_push_context` 도 빈 view 는 키 자체 생략. holdings_briefing 검증의 `bool(push_context.get("market_view"))` 가 빈 dict 면 False 가 되어 정상 차단.
    (A-1 (2)) `runtime_package._evaluate_generation_status` 가 runtime snapshot `status="unavailable"` 도 warning 으로 처리 — partial 노출 (이전엔 unavailable 이 ok 정상 통과). kr/us 양쪽 동일.
    (A-1 (3)) `build_runtime_package` 가 `generation_status.status=="failed"` 인 경우 `message_contract.message_text` 를 빈 문자열로 강제 — "failed 인데 정상 본문" 차단 (계약 §12 정렬). Run.message_text 는 그대로 유지 (preview UI 가 generation_status 함께 보고 판단).
    (A-3) STATE_LATEST.md §1 의 라인 수 stale 값을 실측값으로 정정 (push_context 247 / runtime_package 292 / runtime_probe_cache 133 / draft 544 (FIX r3 시점) / draft_three_push 332 / us_indices 171). FIX r4 후 draft.py 는 추가로 552 라인.
    신규 테스트 4건 (`test_unavailable_runtime_us_marks_partial_status` / `test_unavailable_runtime_kr_marks_partial_status` / `test_failed_package_clears_message_contract_text` / `test_empty_market_view_not_treated_as_present`).
  - **FIX r4 (검증자 3차 REJECTED 후속, A-1 / B-1 / A-3 수용)**:
    (A-1 / B-1) `app/draft.py:generate_draft_from_holdings()` 의 message_contract 동기화 단계가 FIX r3 의 "failed package 본문 비움" 안전장치를 무력화하던 문제 해소 — 동기화 시점에 `runtime_package.generation_status.status == "failed"` 확인 후 failed 면 `mc["message_text"] = ""` 유지 (정상 본문 차단). holdings 경로에서도 FIX r3 정책이 일관되게 적용된다.
    (A-3) 본 §1 안의 FIX r2 항목에 남아있던 `push_context.py 216 라인` 표기를 §1 상단 신규 모듈 5종 표 (FIX r3 후 247 라인) 참조로 정정 — 같은 §1 안에서 라인 수가 일관되게 표기됨.
    신규 테스트 1건 (`test_holdings_draft_failed_package_keeps_message_contract_empty`) — 모든 evidence stub 으로 unavailable 만들어 generation_status=failed 재현, 동기화 후에도 message_contract.message_text 가 빈 문자열인지 검증.
  - **FIX r5 (검증자 4차 REJECTED 후속, A-1 / B-1 / B-6 / A-3 수용)**:
    (A-1 / B-1 / B-6) 실제 승인/preview/Telegram 발송의 단일 소스인 `Run.message_text` 도 `runtime_package.generation_status.status == "failed"` 이면 None 으로 비운다. PUSH-1 (`generate_market_briefing_draft`) / PUSH-2 (`generate_draft_from_holdings`) / PUSH-3 (`generate_spike_alert_draft`) 모두 동일 가드 적용 — 대칭성 유지. Run.status 는 PENDING_APPROVAL 유지 (기존 4-state 흐름 손상 X). `RunPanel` 은 message_text=None 일 때 정적 fallback ("승인 대기 메시지 초안 미리보기 미지원" 안내) 으로 자연스럽게 떨어져 정상 본문 preview 가 보이지 않고, `RuntimePackageStatusCard` 의 generation_status=failed 가 함께 표시되어 사용자가 reject 결정을 내릴 수 있다.
    (A-3) `POC2_B_NEXT_ACTIONS.md` 의 stale 라인 수 5건 (`runtime_probe_cache.py 120` / `runtime_package.py 278` / `draft.py 532` / `draft_three_push.py 311` / `push_context.py 216`) 을 실측 (133 / 292 / 552 / 332 / 247) 으로 정정. FIX r5 후 draft.py 559 / draft_three_push.py 344.
    신규 테스트 2건 (`test_holdings_draft_failed_package_clears_run_message_text` / `test_market_briefing_failed_package_clears_run_message_text`) — Run.message_text 가 failed 시 None 인지 검증 + Run.status 는 PENDING_APPROVAL 유지.
  - **FIX r6 (검증자 5차 REJECTED 후속, A-1 / B-1 / B-6 / A-3 수용)**:
    (A-1 / B-1 / B-6) `app/delivery.py:deliver()` 의 holdings legacy fallback 분기가 FIX r5 의 "failed package 시 Run.message_text=None" 가드를 무력화하던 문제 해소. fallback 으로 `draft_message.build_message_text(...)` 를 호출해 정상 본문을 재생성하던 경로에 `runtime_package.generation_status.status == "failed"` 사전 확인 가드 추가 — failed 면 fallback 진입 자체를 차단하고 `DeliveryError` 명시 raise (PUSH-1/3 의 기존 가드 패턴과 정렬). PUSH-2 holdings 도 failed package 일 때 OCI 로 정상 본문이 발송되지 않는다 (계약 §12 일관 적용).
    (A-3) `app/delivery.py` 변경 0건 표기를 233→**251 라인** 으로 정정 (본 STEP 에서 delivery.py 가 처음 수정됨). STATE_LATEST §1 의 "수정 모듈" 행에도 반영.
    신규 테스트 1건 (`test_holdings_delivery_rejects_failed_package_message_rebuild`) — failed package 의 holdings draft 가 delivery 진입 시 DeliveryError 로 차단되는지 검증.
  - pytest **519 passed** (+29 신규 / 회귀 0, 직전 STEP 490 → 519, FIX r6 후). black / flake8 / Next.js build PASS.
  - 사용자 결정 (Q1~Q5): Q1=urllib 기반 미국 지수 probe (신규 dep 금지), Q2=Naver realtime quote probe, Q3=PUSH-2 endpoint 분리 유지, Q4=runtime_package 키 1건만 추가/기존 키 유지, Q5=30분 TTL cache (refresh endpoint 없음).
- **이전 STEP**: **3-PUSH Message Contract 정렬** (2026-06-12).
  - 기존 `Run → Approval → OCI handoff → Telegram` 단일 경로를 유지하면서 하루 3종 PUSH 메시지의 `message_text` 계약 정리. 새 PUSH API / Telegram 직접 발송 / OCI 재구성 / scheduler / 신규 외부 source / 매수·매도·교체·현금비중·조정장 확정 0건.
  - 신규 builder 2종: `app/message_market_briefing.py` **184 라인** (PUSH-1 시장 흐름 브리핑), `app/message_spike_alert.py` **209 라인** (PUSH-3 급등락 관찰 신호). 모두 외부 source 호출 0건 — ML baseline evidence snapshot / compute_topn / universe_momentum_latest.json read-only 만 사용.
  - **신규 API endpoint 0건 (FIX r2 — 설계자 수용)**: 1차 작업에서 신설했던 `/runs/generate-{market-briefing,spike-alert}` 와 `app/api_three_push.py` 는 §3 / §11 "별도 PUSH API 신설 금지" 와 충돌하여 **모두 제거**. PUSH-1 / PUSH-3 는 기존 `POST /runs/generate` 의 `input_data.push_kind` 분기로 통합.
  - draft entry 2종 신규: `generate_market_briefing_draft()`, `generate_spike_alert_draft()`. `generate_draft(input_data)` 가 `push_kind` 값으로 분기. Run 모델에 `push_kind: Optional[str]` 추가 (legacy run 하위호환 — None 허용).
  - PUSH-2 (holdings_briefing) 는 기존 `generate_draft_from_holdings()` 가 재정의 — push_kind 만 명시. builder / payload 변경 0건. 별도 holdings 데이터 의존성으로 인해 기존 `/runs/generate-from-holdings` endpoint 유지.
  - delivery fallback 보강: message_text 누락 시 holdings builder 로 rebuild 되던 분기에 `push_kind in {"market_briefing", "spike_or_falling_alert"}` 가드 추가 — raw recommendations 발송 차단.
  - frontend: `Run.push_kind` 타입 추가, `generateMarketBriefingDraft()` / `generateSpikeAlertDraft()` API 함수 + `ThreePushDraftCard` 신규 (ApprovalTelegramView 안 임시 진입점, 발송 시간 / UX 확정은 별도 STEP — 지시문 §13).
  - **FIX r2 추가 변경**: (1) `SPIKE_DISPLAY_THRESHOLD_PCT` → `SPIKE_DISPLAY_RETURN_PCT_MIN` 으로 rename (변수명에 "threshold" 단어 제거 — §12 "위험 threshold 확정 금지" 와 의미 분리). message_text 본문의 "표시 임계" → "표시 하한" 으로 정리. (2) `_load_universe_artifact` 가 부재(정상)와 손상(이상) 을 logger.debug / logger.warning 으로 구분 (B-1 의심 해소). (3) `app/models.py` docstring 갱신 (`message_text` / `push_kind` 필드 반영, "필드 4개만 사용" 표현 정정).
  - **FIX r3 추가 변경 (검증자 PARTIALLY_VERIFIED 후속, B-2 / B-3 / B-6 수용)**: (1) draft.py 책임 집중 해소 — PUSH-1/3 entry (`generate_market_briefing_draft` / `generate_spike_alert_draft`) + 분기 진입점 (`generate_*_via_generic`) + `_load_universe_artifact_for_spike` 를 신규 `app/draft_three_push.py` (**207 라인**) 로 분리. draft.py 623 → **465 라인** (KS-10 안전 영역 복귀). draft.py 는 re-export 만 유지 (기존 호출자 호환). (2) stale 주석 정리 — `app/api.py` 의 "app/api_three_push.py 로 분리" 와 `frontend/lib/api/runApproval.ts` 상단 주석의 삭제된 endpoint 표현 모두 정정.
  - 실측 (live API, FIX r2 후): `POST /runs/generate` (`input_data.push_kind="market_briefing"`) → 496자 / push_kind=market_briefing 전파. (`spike_or_falling_alert`) → 213자. 신규 PUSH endpoint 2개는 405 (제거 확인).
  - pytest **490 passed** (+20 신규, 회귀 0, FIX r3 후). black / flake8 / Next.js build PASS.
- **이전 STEP**: **UI 안전실행 — ML evidence 갱신 background job** (2026-06-11, commit `b855a982`).
  - 기존 CLI 3종 (`generate_ml_features` → `check_ml_feature_sanity` → `run_ml_baseline_v0`) 을 Data Status 화면의 "ML evidence 갱신 실행" 버튼 1개로 안전하게 background 에서 순차 실행. CLI 경로는 그대로 살아있음 (이중화).
  - 신규 모듈: `app/ml_job_runner.py` **447 라인** — job state schema + 3단계 runner + `threading.Lock` (in-process) + on-disk `state/ml/ml_job_status_latest.json` lock + PID/heartbeat 기반 stale 자동 해제 (10분, 사용자 결정).
  - 신규 API: `POST /ml/jobs/evidence-refresh` (background 시작, 즉시 반환) + `GET /ml/jobs/latest` (read-only). FastAPI `BackgroundTasks` 사용 — Celery/Redis/신규 DB 0건 (§8).
  - 신규 Card: `MLEvidenceRefreshCard` (DataStatusView 최상단). 실행 중 5초 polling 자동 갱신. 단계별 상태 / 시작·종료 시각 / 실패 메시지 / 마지막 성공 요약 표시. 매수/매도/추천/현금/조정장/위험알림 문구 0건.
  - 단계 실패 시: 이후 단계 skipped, 기존 snapshot 3종 (feature/sanity/baseline) **삭제하지 않음** (마지막 성공 결과 보존, AC-6).
  - 중복 실행 차단: in-process Lock + on-disk status running 검사. 중복 POST 는 새 job 안 만들고 현재 running 응답 (already_running).
  - 실측 (uvicorn 직접 호출): POST `/ml/jobs/evidence-refresh` **2.6ms** 만에 accepted 반환 / 즉시 중복 POST 2.2ms 만에 already_running / 단계별 polling (feature→sanity→baseline) 정확 / 최종 status=success, evaluated_days=43, baseline_report_status=ok.
  - **FIX r2 (검증자 1차 REJECTED 후속, 2건)**:
    (A-1 / B-6) Windows 에서 `os.kill(pid, 0)` 이 PID 0 을 alive 로 반환하고 자기 PID 대상 시 KeyboardInterrupt 유발 가능 — `_PID_CHECK_SUPPORTED = sys.platform != "win32"` 분기 추가. Windows 에서는 PID 확인 비활성화 + heartbeat 10분 만으로 stale 판정 (POSIX 는 기존 로직 유지). psutil 등 신규 의존성 0건 (§8 정신 준수).
    (B-1) `_read_status` 가 JSON 손상 시 None 반환해 미실행과 구분 안 되던 문제 — `_read_status_raw()` 가 `(state, error)` tuple 반환하도록 변경. `get_latest_status()` 도 동일 시그니처. API 가 손상 시 `status="error"` 응답 + frontend Card 에 error 분기 표시. POST 도 손상 감지 시 새 job 자동 생성 안 함 (fail-loud).
  - pytest **470 passed** (+16 신규, 회귀 0, FIX r2 후 3회 연속 비결정성 0건 확인). black / flake8 / Next.js build PASS.
- **이전 STEP**: **ML Baseline Evidence Draft Integration** (2026-06-11, commit `f7ec493e`).
  - 저장된 ML baseline v0 룩백 report 를 GenerateDraft 의 보조 evidence 로 연결. CLI 재실행 / feature 재생성 / 외부 source 호출 / ML 학습 0건. 매수/매도/추천/현금비중/조정장/위험 알림 문구 0건.
  - 신규 모듈: `app/ml_baseline_evidence.py` **452 라인** (KS-10 안전) — JSON 파일 직접 read (HTTP self-call X), stale 기준 `feature_asof_range.end` 7일 초과.
  - draft_payload 신규 키: `ml_baseline_evidence_snapshot` (status / candidate_summary / risk_summary / leakage_summary / limitations / external_context_checklist 7항목). factor_signals 신규 scope: `ml_baseline_evidence` (보조 evidence 1건).
  - **FIX r2 (검증자 1차 REJECTED 후속, AC-2 완전 구현)**: AI Sessions / Decision Evidence 저장 경로에도 `ml_baseline_evidence_snapshot` 정식 연결. `ai_session_records` 테이블에 `ml_baseline_evidence_snapshot_json` 컬럼 + 자동 ADD COLUMN 마이그레이션 (`_migrate_add_ml_baseline_evidence_snapshot`). `insert_record` / `get_record` / `_row_to_full_dict` / `_SELECT_COLS` 갱신. `app/api_decision_sessions.py` 의 `CreateDecisionSessionRequest` / `DecisionSessionDetail` 에 필드 추가. frontend `aiSessionsDraft.ts` / `decisionSessions.ts` 타입 + `AISessionsCreateTab` 저장 시점 fallback 으로 자동 채움 (draft 에 이미 있으면 그대로 사용).
  - **FIX r3 (검증자 2차 REJECTED 후속, 데이터 계약 단일화)**: `AISessionsCreateTab` fallback 이 raw `{api_status, report_path, report, message}` 를 저장하던 문제를 해결. backend 에 `GET /ml/baseline-v0/evidence-snapshot` 신규 (GenerateDraft 와 동일한 정규화 shape 반환, read-only) + frontend `fetchMlBaselineEvidenceSnapshot()` 신규 + AISessionsCreateTab 가 이 API 결과를 그대로 payload 에 담음. fetch 실패 시에도 status="error" 정규화 snapshot 으로 채움 (지시문 §4.7 — 조용히 빠지지 않음).
  - draft_message [판단 사유] 섹션에 "ML baseline 룩백 evidence" 1줄 추가 — 평가 거래일 / 후보 발굴 baseline / 위험 baseline / leakage / 한계 4종 본문.
  - report 부재 → status=unavailable / 손상 → error / stale → stale / warn → warn 으로 draft 에 그대로 노출 (조용히 빠지지 않음).
  - 실측 (운영 SQLite): status=ok / candidate evaluated_days=40 / risk evaluated_days=40 / leakage 0 / external checklist 7건.
  - pytest **454 passed** (+22 신규, 회귀 0, FIX r3 후). black / flake8 / Next.js build PASS.
- **이전 STEP**: **ML Baseline v0 룩백 검증** (2026-06-11, commit `4c1cb3b5`).
  - 현재 feature dataset 이 과거 구간에서 (1) 상승 후보 발굴 baseline 과 (2) 위험 구간 감지 baseline 으로 의미가 있었는지 룩백 검증. 실시간 매수/매도 판단 X, 위험 알림 X, 조정장 확정 X, 위험 threshold X.
  - CLI: `scripts/run_ml_baseline_v0.py` (외부 source 호출 0건). read-only API: `GET /ml/baseline-v0/latest`. Data Status 카드 신규: `MLBaselineV0Card`.
  - Candidate baseline (사용자 결정 — Top quintile 20%): composite rank v0 = return_20d / excess_20d / return_10d / volume_ratio_20d DESC rank 평균. future_return / future_excess_return horizons = 5/10/20d.
  - Risk baseline (사용자 결정 — market composite tercile 1/3): 13축 risk axes (변동성/시장폭/distance_from_20d_high/조정장 전조 proxy 등) rank 평균. future_kodex200_return 3/5/10d + future_market_drawdown 5/10d + future_universe_down_ratio_5d.
  - Horizon tail (사용자 결정 — max horizon 20d 만큼 tail 제외): 마지막 20거래일은 평가에서 제외 (모든 horizon 의 future target 측정 가능 구간만).
  - Leakage check: feature asof 이후 가격만 target 계산에 사용 — 구조적 누수 불가. time order ASC 보장.
  - 실측 (1137 ETF × 60거래일 / 평가 40거래일 / FIX r2 후): **status=ok**, leakage 0. evaluated_asof_range=2026-03-11→2026-05-07. candidate top group 5d/10d/20d return = 3.4%/5.5%/13.5% vs universe median 1.1%/2.1%/4.7%. risk high vs low future drawdown 10d = -8.1% vs -3.4%, drawdown_capture_rate 10d = 1.44.
  - **FIX r2 (검증자 1차 REJECTED 후속)**: (A-1) 지시문 §7.4/§8.4 단순 baseline 누락 보강 — candidate `simple_baselines` 2종 (return_20d / excess_20d top quintile) + risk `simple_baselines` 3종 (5일 시장 수익률 / 20일 drawdown / 시장폭) 노출. (A-2) `MLBaselineV0Card` helper 문구의 §12 금지 단어 (매수/매도/현금/위험알림/조정장) 제거 — "0건" 표현이라도 위반. (A-3) `evaluated_asof_range.end` null → "2026-05-07" 채움.
  - 신규 파일 라인 수 (실측, FIX r2 후): `ml_baseline_targets.py` 352 / `ml_baseline_candidate.py` **426** / `ml_baseline_risk.py` **390** / `ml_baseline_v0.py` 199 / `api_ml_baseline.py` 66. KS-10 trigger/near 0건.
  - Snapshot: `state/ml/ml_baseline_v0_report_latest.json` (gitignored, 운영 artifact).
  - pytest **432 passed** (+15 신규 / 회귀 0). black / flake8 / ESLint / Next.js build PASS.
- **이전 STEP**: **ML Feature Sanity Check** (2026-06-08, commit `7a259454`).
  - ML baseline v0 입력 직전 데이터 품질 검산 4종 (coverage / calculation / NAV join / risk proxy).
  - CLI: `scripts/check_ml_feature_sanity.py` (외부 source 호출 0건, sample_count 인자).
  - 신규 read-only API `GET /ml/feature-sanity/latest` — snapshot JSON 만 read (재계산 X).
  - Data Status 화면에 sanity 요약 + 7축 sub-check + 샘플 ETF 10건 (return/excess/vol/dd/NAV 괴리율) 표시.
  - 허용 오차 (사용자 결정 (b)): `abs_tol=1e-4 + rel_tol=1e-4` (numpy isclose 패턴). risk proxy 이상치는 null 비율만 (사용자 결정 (f)).
  - 실측 (FIX r3 후): 1137 ETF × 60일 / sanity_status=warn / calc 0 error / future_nav_join=0 / risk all-null=0 / warning 3건 (NAV unavailable 2 + **ticker별 row 누락 69건 신규 감지** — FIX r3 효과).
  - **FIX r2 (KS-10 자체 점검)**: 첫 작성된 `ml_feature_sanity.py` 607 라인 → near 진입. helpers 모듈로 분리 → `ml_feature_sanity.py` 491 라인 + `ml_feature_sanity_helpers.py` 141 라인. ML 신규 파일 KS-10 trigger/near 0건.
  - **FIX r3 (검증자 REJECTED 후속)**: (1) coverage §4.3 누락 보강 — ticker별 row 누락 + asof drop 검산 추가. (2) snapshot 손상 시 status=error 분리 (fail-loud, empty 와 구분). (3) untracked 8건 즉시 staging. 실측: `ml_feature_sanity.py` **561 라인** (near 600 미진입), `api_ml_sanity.py` 65 라인. pytest **417 passed** (+3, 회귀 0).
  - Snapshot: `state/ml/ml_feature_sanity_latest.json` (gitignored).
- **이전 STEP**: ML 최소 데이터 레인 1차 (2026-06-08, commit `e918bb47`).
  - FIX r2 (검증자 REJECTED 대응): 신규 `ml_feature_builder.py` 615 라인 (backend near ≥600) → 책임 분리. primitives / nav_lookup 2 모듈 신규. **builder 455 라인 (near 이탈)** + primitives 124 + nav_lookup 78. ML 핵심 파일 KS-10 trigger/near 0건.
  - SQLite 2 테이블 신규: `etf_ml_feature_daily` (ETF별 daily feature) + `market_risk_feature_daily` (시장 위험 daily feature).
  - CLI 전용 실행 (`scripts/generate_ml_features.py`) — 화면 / refresh 흐름 hook 0건. `--start-date` / `--end-date` / `--lookback-days` (기본 60거래일) / `--ticker` filter / `--no-snapshot`.
  - ETF feature: return 5/10/20d + KODEX200 대비 초과수익 + volatility_20d + drawdown_20d + volume_ratio_20d + NAV/괴리율 join (latest available ≤ asof, 미래 데이터 금지).
  - Market risk feature: KODEX200/KOSPI return 1/5/20d + ETF universe up/down/flat count·ratio + median return 1d/5d + NAV 분포 (avg/abs_avg/extreme≥3%) + 변동성/drawdown proxy + 조정장 전조 5종 (distance_from_20d_high / volatility_expansion_20d / down_day_volume_ratio / large_negative_day_proxy / short_term_weakness_proxy / breadth_deterioration_proxy).
  - 신규 read-only API `GET /ml/readiness/latest` — row 수 / latest asof 동적 표시.
  - `MLTimeseriesReadinessCard` 갱신 (9축 정적 표 → 7축 + API 조회). CNN Fear&Greed / VKOSPI / 외국인·기관 수급 / KOSPI 전체 시장 폭 / 구성종목 가격 시계열은 표시 제외 (BACKLOG).
  - Snapshot: `state/ml/ml_feature_snapshot_latest.json` (gitignored, 운영 artifact).
  - 실측 (1137 ETF × 60일): 4.46초 / 65,691 ETF feature row + 60 market risk row.
  - ML 모델 학습 / 라벨 / 예측 / 매수·매도 판단 / 위험 threshold 0건. 외부 크롤링 0건.
- **이전 STEP (직전 commit 7건)**: 사용자 즉시 피드백 (`6c3728ec` → `8fad2bb4`) 의 Market Discovery UI / Perf 정리.
  - 직전 STEP(NAV / Discount Display FIX) 이후 사용자가 보낸 UI 정리 요청 + perf 지적 일괄 반영.
  - **UI**: CandidateTable 의 source/status/정렬기준/태그 컬럼 제거, 6m/12m/1y/3y 표시 컬럼 추가 (표시 전용, 정렬 X). asof 컬럼 제거. TopControlsRow 1 카드 안에 (1행) 갱신+필터 / (2행) AI Sessions·ETF Exposure 전달 버튼 묶음. AI 투자세션 복사용 문구 / 별도 Transfer 섹션 / 정렬 기준 안내 / role banner / subtitle 문구 모두 제거.
  - **MarketContextCard**: `(069500) KODEX 200 (필수)` / `(KS11) KOSPI (보조)` 헤더 — 현재가/MA20/MA60 행이 어느 종목인지 명확. 금액 천단위 콤마 (`119,560`).
  - **Backend**: `MarketReturns` 모델에 six_month / twelve_month / three_year 추가 (lookback 180/365/1095). 정렬 가능 basis 는 daily/1m/3m 그대로 (신규 기간은 표시 전용).
  - **Perf**: `/market/topn/latest` 응답 **2.4s → 0.85s (65% 단축)**. 원인 = `_connection()` 매 호출마다 `init_db()` 반복 + `get_etf_name()` universe 1137 회 단건 SQL. 처리 = process-level `_INITIALIZED_DBS` 캐시 + `get_etf_name_map()` bulk loader 추가.
- **현재 진행 예정**: 사용자 결정 대기 (§6 Next action 참조).

## 2. Latest completed step

| Step | Status | Date | Detail |
| --- | --- | --- | --- |
| 3-PUSH Runtime Package PC 검증 | DONE | 2026-06-13 | [POC2_THREE_PUSH_RUNTIME_PACKAGE_PC_VERIFICATION_CONCLUSION.md](handoff/POC2_THREE_PUSH_RUNTIME_PACKAGE_PC_VERIFICATION_CONCLUSION.md) |
| 3-PUSH Message Contract 정렬 | DONE | 2026-06-12 | [POC2_THREE_PUSH_MESSAGE_CONTRACT_ALIGNMENT_CONCLUSION.md](handoff/POC2_THREE_PUSH_MESSAGE_CONTRACT_ALIGNMENT_CONCLUSION.md) |
| UI 안전실행 — ML evidence 갱신 background job | DONE | 2026-06-11 | [POC2_UI_SAFE_ML_EVIDENCE_EXECUTION_CONCLUSION.md](handoff/POC2_UI_SAFE_ML_EVIDENCE_EXECUTION_CONCLUSION.md) |
| ML Baseline Evidence Draft Integration | DONE | 2026-06-11 | [POC2_ML_BASELINE_EVIDENCE_DRAFT_INTEGRATION_CONCLUSION.md](handoff/POC2_ML_BASELINE_EVIDENCE_DRAFT_INTEGRATION_CONCLUSION.md) |
| ML Baseline v0 룩백 검증 | DONE | 2026-06-11 | [POC2_ML_BASELINE_V0_LOOKBACK_CONCLUSION.md](handoff/POC2_ML_BASELINE_V0_LOOKBACK_CONCLUSION.md) |
| ML Feature Sanity Check | DONE | 2026-06-08 | [POC2_ML_FEATURE_SANITY_CHECK_CONCLUSION.md](handoff/POC2_ML_FEATURE_SANITY_CHECK_CONCLUSION.md) |
| ML 최소 데이터 레인 1차 | DONE | 2026-06-08 | [POC2_ML_MINIMAL_DATA_LANE_CONCLUSION.md](handoff/POC2_ML_MINIMAL_DATA_LANE_CONCLUSION.md) |
| Market Discovery UI / Perf 후속 정리 (사용자 즉시 피드백 5 commit) | DONE | 2026-06-08 | commits `6c3728ec` → `8fad2bb4` (별도 Conclusion 미생성 — handoff 검증자 보고서 [POC2_MARKET_DISCOVERY_UI_PERF_USER_FEEDBACK_NOTE.md](handoff/POC2_MARKET_DISCOVERY_UI_PERF_USER_FEEDBACK_NOTE.md)) |
| NAV / Discount Display FIX (전체 ETF 조회 영역 + 표시 매트릭스) | DONE | 2026-06-08 | [POC2_NAV_DISCOUNT_DISPLAY_FIX_CONCLUSION.md](handoff/POC2_NAV_DISCOUNT_DISPLAY_FIX_CONCLUSION.md) |

## 3. Recent history summary

| Step | Result | Summary | Detail |
| --- | --- | --- | --- |
| 2026-06-08 ML Feature Sanity Check | DONE | coverage / calculation / NAV join / risk proxy 검산 4종 + read-only API + Data Status 표시. sanity_status=warn / calc 0 err / future_nav_join=0. | [conclusion](handoff/POC2_ML_FEATURE_SANITY_CHECK_CONCLUSION.md) |
| 2026-06-08 ML 최소 데이터 레인 1차 | DONE | etf_ml_feature_daily + market_risk_feature_daily 2 테이블 + CLI + 7축 readiness API. 1137 ETF×60일 → 65,691 row / 4.46초. ML 모델 / threshold / label 0건. | [conclusion](handoff/POC2_ML_MINIMAL_DATA_LANE_CONCLUSION.md) |
| 2026-06-08 Market Discovery UI / Perf 후속 정리 | DONE | CandidateTable 컬럼 정리 + 6m/12m/1y/3y 추가 + TopControlsRow 통합 + MarketContextCard 표기 정정 + 응답 2.4s→0.85s. | commits `6c3728ec`…`8fad2bb4` / [feedback note](handoff/POC2_MARKET_DISCOVERY_UI_PERF_USER_FEEDBACK_NOTE.md) |
| 2026-06-08 NAV / Discount Display FIX | DONE | GET /market/nav-discount/latest 신규 + Data Status 전체 ETF NAV 표 + MD/ETF Exposure/Holdings 표시 보강. 표시 매트릭스 충족. | [conclusion](handoff/POC2_NAV_DISCOUNT_DISPLAY_FIX_CONCLUSION.md) |
| 2026-06-08 Naver ETF Universe NAV / 괴리율 연동 | DONE | universe 1회 호출(`etfItemList.nhn`) → `etf_nav_daily` upsert + 3개 화면 NAV 표시. TTL 30s + stale 재사용. 신규 API 0건. | [conclusion](handoff/POC2_NAVER_ETF_UNIVERSE_NAV_INTEGRATION_CONCLUSION.md) |
| 2026-06-07 ETF NAV / Discount Source Diagnosis 1차 (FIX) | DONE | NAV/괴리율 source 5건 실측. adopt 0 / hold_unstable 2 / unusable 3. flat_records + timeout 명시 + asof 키 확장 FIX. | commit `b5a80a3f` / [archive](handoff/STATE_LATEST_ARCHIVE.md) |
| 2026-06-06 ETF Exposure Data Unfolding 1차 | DONE | 구성종목 펼쳐보기 + 반복 핵심 종목 + 중복률 + Holdings Evidence State Bridge + ML readiness 9축. ML 방향성 2축 문서화. | commit `bce8f7fd` / [archive#0.1](handoff/STATE_LATEST_ARCHIVE.md) |

> 직전 5개를 제외한 이전 STEP (2026-06-01 이전 — Market Discovery Closeout / Constituents Naver Integration /
> Constituents Diagnosis / Constituents & Overlap / Market Regime / AI Sessions / Decision Evidence /
> AI 투자세션 복사용 문구 / Grid 사용성 FIX / 통합 후보 테이블 / 후보 정제 / SQLite Direct Refresh /
> TOP N 최소 표시 / PC UI Shell / FDR+SQLite Foundation / B 방향 전환 등) 은
> [docs/handoff/STATE_LATEST_ARCHIVE.md](handoff/STATE_LATEST_ARCHIVE.md) 에 전문 보존되어 있다.

## 4. Current evidence flow

- **Market Discovery**: SQLite 직접 계산 TOP N. 수동 refresh (6h cooldown). 응답 0.85s (2026-06-08 perf). TopControlsRow 1 카드 (1행 갱신+필터 / 2행 AI Sessions·ETF Exposure 전달). 시장 국면(`(069500) KODEX 200 (필수)` / `(KS11) KOSPI (보조)`, 금액 천단위 콤마). 그리드 컬럼: 순위/티커/ETF명/일간·1m·3m(정렬)/6m·12m·1y·3y(표시)/KODEX200 대비 1m·3m/NAV/시장가/괴리율. asof/source/status/태그 컬럼은 그리드에서 제거 (Data Status 화면에서 조회).
- **ETF Exposure**: 구성종목 펼쳐보기(자동 open + 등락률 unavailable 컬럼) + 중복률 + 반복 핵심 종목 + Holdings Evidence State Bridge (명시 호출 버튼) + NAV/괴리율 카드(상위 5건 + asof/source/status) + ML readiness 9축.
- **Holdings Evidence**: `GET /holdings/market-evidence/latest` (read-only, 외부 fetch 0건). 보유 ETF × Market Discovery 후보 / 시장 국면 / 단기 흐름 / 구성종목 중복 / NAV·시장가·괴리율·asof·status·source(`etf_nav_daily` store 에서 read).
- **Data Status**: 전체 ETF NAV / 시장가 / 괴리율 조회 화면 (`GET /market/nav-discount/latest`). 검색 + status 필터 + 괴리율 정렬. 외부 source 호출 0건. 1136 ETF 1회 응답.
- **GenerateDraft**: 같은 evidence builder 재사용 — `draft_payload.holdings_market_evidence_snapshot` + `factor_signals` scope="holdings_market_evidence" + [판단 사유] bullet. 매수·매도·교체 어휘 0건.
- **Approval / Telegram**: 인간 승인 게이트 유지. 3-PUSH (보유 종목 상태 / 신규 ETF 관찰 후보 / 급락 ETF 주의). 자동 매매 X.
- **AI Sessions**: 외부 AI 답변 + 사용자 판단 기록. Market Discovery 후보 스냅샷 + 시장 국면 + 구성종목/중복률 / 단기 흐름 / 데이터 품질 / Decision Candidate 전부 포함.

## 5. Open decisions

| ID | 상태 | 내용 | 참조 |
| --- | --- | --- | --- |
| Q1 | OPEN | 여러 factor 를 붙일 수 있는 구조의 엔진이 될 것인가? | ASSUMPTIONS §2 |
| Q4 | OPEN | "잘 올라가는 섹터/ETF 발굴" 작동 단위 (운영 1개월 검증 필요) | ASSUMPTIONS §2 |
| Q6 | OPEN | 위험 감지 = "위험 구간 분류" — factor / threshold / label 어떻게 확정할 것인가? (시계열 적재 선행) | ASSUMPTIONS §2 / INTENT §9.5 |

## 6. Next action

- **다음 Step 후보 (사용자 결정 대기)**:
  1. ~~NAV / Discount Source Adoption~~ — **DONE (2026-06-08 Naver Universe NAV Integration)**.
  2. **NAV / 괴리율 시계열 누적** — 현재는 universe 1회 호출 = 단면 스냅샷. asof 일자별 누적이 위험 감지 축 2 의 시계열 후보로 직접 사용 가능 (ML readiness 카드의 NAV/괴리율 시계열 partial → available 승격 경로).
  3. **위험 감지 지표 시계열 적재 1차** — VKOSPI / Fear&Greed / 외국인·기관 수급 / 시장 폭 후보 진단. ML 2축 중 축 2 선행 조건.
  4. **구성종목 가격 시계열 source 진단** — ETF Exposure 화면에서 등락률 unavailable 해소.
  5. **MDD / Sharpe 계산 도입** — Phase 1 BACKLOG 항목.
- **하지 않을 것 (불변 원칙)**:
  - 자동 매매 / Telegram 문구 변경 / OCI push 자동화 (사용자 명시 승인 필요)
  - MongoDB 전환 (PROJECT_ORIGIN_INTENT §10 #2 — SQLite(시장) + JSON(holdings/Run) SSOT 분리)
  - ML / 백테스트 / threshold / label 확정 (Q6 답 나오기 전)
  - 매수·매도·교체 어휘 / 자동 클러스터링 / 대표 ETF 선정
- **사용자 결정 필요**: ✅ 위 4개 후보 중 다음 Step 선택.

## 7. Index

### 불변 앵커 (먼저 읽어야 하는 5개 문서)

- [docs/PROJECT_ORIGIN_INTENT.md](PROJECT_ORIGIN_INTENT.md) — 한 줄 정의 / 1년 뒤 목표 / 절대 하지 않을 것 / ML 2축 (§9.5)
- [docs/KILL_SWITCHES.md](KILL_SWITCHES.md) — KS-1 ~ KS-11 (단일 파일 책임 누적 / 의사결정 24시간 룰 등)
- [docs/ASSUMPTIONS.md](ASSUMPTIONS.md) — Open Question Q1 / Q4 / Q6 (활성 3개 한도)
- [docs/COLLAB_RULES.md](COLLAB_RULES.md) — 협업 규칙
- [docs/MASTER_PLAN.md](MASTER_PLAN.md) — 마스터 플랜

### Active reference (현 진행에 영향, 자주 갱신)

- [docs/handoff/POC2_B_NEXT_ACTIONS.md](handoff/POC2_B_NEXT_ACTIONS.md) — 빈자리 후속 원칙 + 다음 분기 후보
- [docs/handoff/POC2_FEATURE_INVENTORY.md](handoff/POC2_FEATURE_INVENTORY.md) — 기능 인벤토리

Active Reference:
3-PUSH Runtime Package Contract
- path: docs/handoff/THREE_PUSH_RUNTIME_PACKAGE_CONTRACT.md
- purpose: PC/OCI가 공유하는 three_push_runtime_package.v1 schema 계약
- usage: PUSH 후속 Step에서는 evidence package / runtime snapshot / message_text 설계 시 이 문서를 기준으로 한다.
- [docs/handoff/ETF_NAV_DISCOUNT_SOURCE_DIAGNOSIS.md](handoff/ETF_NAV_DISCOUNT_SOURCE_DIAGNOSIS.md) — NAV 진단 1차 결과
- [docs/handoff/ETF_CONSTITUENTS_SOURCE_DIAGNOSIS.md](handoff/ETF_CONSTITUENTS_SOURCE_DIAGNOSIS.md) — 구성종목 source 진단
- [docs/backlog/BACKLOG.md](backlog/BACKLOG.md) — Backlog (시계열 / NAV source / MDD / Sharpe / 구성종목 가격 / 위험감지 지표)
- [docs/ref/FRIEND_PROJECT_DATA_SOURCES_ANALYSIS.md](ref/FRIEND_PROJECT_DATA_SOURCES_ANALYSIS.md) — 친구 프로젝트 source / 주기 분석

### Step detail (Step 종료 후 생성된 상세 기록)

POC1 → POC2 초기:
- [POC1_step3_close_and_POC2_handoff.md](handoff/POC1_step3_close_and_POC2_handoff.md) — POC1 Step3 종결 + POC2 진입 1차
- [POC1_Step3_close_and_POC2_Step1_handoff.md](handoff/POC1_Step3_close_and_POC2_Step1_handoff.md) — POC1 Step3 종결 + POC2 Step1 완료 종합

POC2 Step 1A ~ 6:
- [POC2_Step1A_close.md](handoff/POC2_Step1A_close.md) / [POC2_Step2_close.md](handoff/POC2_Step2_close.md) / [Step2B](handoff/POC2_Step2B_close.md) / [Step2C](handoff/POC2_Step2C_close.md) / [Step2D](handoff/POC2_Step2D_close.md)
- [POC2_STEP2_CONCLUSION_AND_STEP3_HANDOFF.md](handoff/POC2_STEP2_CONCLUSION_AND_STEP3_HANDOFF.md)
- [POC2_STEP3_CONCLUSION_AND_NEXT_HANDOFF.md](handoff/POC2_STEP3_CONCLUSION_AND_NEXT_HANDOFF.md)
- [POC2_STEP4_MOMENTUM_ENGINE_DIRECTION_AND_Q4_BOUNDARY_DESIGN.md](handoff/POC2_STEP4_MOMENTUM_ENGINE_DIRECTION_AND_Q4_BOUNDARY_DESIGN.md)
- [POC2_STEP5A_MOMENTUM_ENGINE_BOUNDARY_AND_MINIMAL_CONTRACT.md](handoff/POC2_STEP5A_MOMENTUM_ENGINE_BOUNDARY_AND_MINIMAL_CONTRACT.md)
- [POC2_STEP6_CONCLUSION_AND_NEXT_HANDOFF.md](handoff/POC2_STEP6_CONCLUSION_AND_NEXT_HANDOFF.md)

POC2 Step 7 (3-PUSH realignment):
- [POC2_STEP7_SYSTEM_OUTPUT_3_PUSH_REALIGNMENT_DESIGN.md](handoff/POC2_STEP7_SYSTEM_OUTPUT_3_PUSH_REALIGNMENT_DESIGN.md)
- [POC2_STEP7A_NEW_ETF_WATCH_CANDIDATE_MINIMAL_PUSH.md](handoff/POC2_STEP7A_NEW_ETF_WATCH_CANDIDATE_MINIMAL_PUSH.md)
- [POC2_STEP7B_HOLDINGS_STATUS_BRIEFING_MINIMAL_PUSH.md](handoff/POC2_STEP7B_HOLDINGS_STATUS_BRIEFING_MINIMAL_PUSH.md)
- [POC2_STEP7C_FALLING_ETF_CAUTION_SIGNAL_MINIMAL_PUSH.md](handoff/POC2_STEP7C_FALLING_ETF_CAUTION_SIGNAL_MINIMAL_PUSH.md)
- [POC2_STEP7_CONCLUSION_AND_NEXT_HANDOFF.md](handoff/POC2_STEP7_CONCLUSION_AND_NEXT_HANDOFF.md)

POC2 Step 8 (3-PUSH 운영 1주기 검증) + 별도 Foundation:
- [POC2_STEP8_3PUSH_FIRST_OPERATIONAL_CYCLE_VALIDATION.md](handoff/POC2_STEP8_3PUSH_FIRST_OPERATIONAL_CYCLE_VALIDATION.md)
- [POC2_FDR_SQLITE_MARKET_DATA_FOUNDATION.md](handoff/POC2_FDR_SQLITE_MARKET_DATA_FOUNDATION.md) — FDR + SQLite 시장 데이터 기반 구축

2026-06-01 이후 (가장 최근 5개 STEP — §3 참조 + ARCHIVE 전문):
- 2026-06-07 NAV / Discount Source Diagnosis 1차 (FIX) → [STATE_LATEST_ARCHIVE §0](handoff/STATE_LATEST_ARCHIVE.md)
- 2026-06-06 ETF Exposure Data Unfolding 1차 → [ARCHIVE §0.1](handoff/STATE_LATEST_ARCHIVE.md)
- 2026-06-06 Operational UI Cleanup 1차 → [ARCHIVE §0.1](handoff/STATE_LATEST_ARCHIVE.md)
- 2026-06-03 Holdings × Market Discovery Evidence 1차 → [ARCHIVE §0.1](handoff/STATE_LATEST_ARCHIVE.md)
- 2026-06-03 KS-10 Cleanup (API Client / Type 책임 분리) → [ARCHIVE §0.1](handoff/STATE_LATEST_ARCHIVE.md)
- 2026-06-01 이전 16개 STEP 시간순 누적 → [STATE_LATEST_ARCHIVE.md](handoff/STATE_LATEST_ARCHIVE.md) 전문

### Deprecated / redirect

- [docs/handoff/STATE_LATEST.md](handoff/STATE_LATEST.md) — 6줄 redirect stub. 본 파일과 ARCHIVE 로 안내. 더 이상 append 하지 않는다.
