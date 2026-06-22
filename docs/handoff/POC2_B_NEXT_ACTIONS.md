# POC2 B 방향 — 다음 액션 (NEXT ACTIONS)

작성일: 2026-05-20 / 갱신: 2026-06-21 (보유 ETF와 시장 후보 비교 v1)
성격: **방향을 잊지 않기 위한 앵커.** 새로운 가드 문서가 아니다. 설계 결정이
흔들릴 때 PROJECT_ORIGIN_INTENT 원칙과 함께 본 문서로 복귀한다.

---

## 0. 직전 STEP 결과 (2026-06-21 — 보유 ETF와 시장 후보 비교 v1)

지시문 단일 목표: 기존 Market Discovery 안에서 보유 ETF 와 시장 후보 ETF 를
같은 화면에서 비교. 신규 endpoint / 신규 계산 0건.

### 결과 요약

- 신규 frontend: `HoldingsCompareView` — 보유 요약 표 + 후보 비교 표 (좌측 70%) + 후보 선택 상세 (우측 30%, split pane).
- 수정 frontend: `MarketDiscoveryView` — 상단 탭 토글 ("기본" / "보유와 비교") + 탭별 렌더 분기.
- 데이터 조합 (지시문 §5): 기존 `GET /market/topn/latest` + `GET /holdings/enriched` + `GET /holdings/market-evidence/latest` 응답을 client-side ticker 매칭으로 조합. exact match + constituents overlap 두 종류 표시.
- Evidence 명시 조회: 사용자 버튼 클릭으로만 조회, 후보 선택 자동 fetch 0건.
- 기준일 분리 표시: 후보 / 보유 / 중복 정보 각각 별도 노출.
- 신규 backend 0건. 기존 산식 변경 0건. OCI / PARAM / Telegram 변경 0건.

### 검증

- pytest **616 passed** (회귀 0 — backend 변경 0건). black / flake8 / frontend lint / build PASS.

### 다음 분기 후보

PC_OCI_ARCHITECTURE_DIRECTION 순서:

1. **ML 축2** — 위험 감지용 시계열 빈자리 하나 채우기 STEP.
2. **점수·위험·보유 비교가 모이는 PC 판단 화면** 좁은 STEP (본 STEP 의 후속).
3. **OCI read model foundation** — PC 판단 화면 + ML 축2 1차 결과 확보 뒤.
4. **BACKLOG CONSOLIDATED_BACKLOG_DEBT_CLEANUP**.

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.

---

## 0-prev. 이전 STEP 결과 (2026-06-21 — ML 축1 — 상대상승 점수 실행 UI 연결)

지시문 단일 목표: 기존 `relative_upside_score_v0` 실행을 Market Discovery UI 에 연결.
사용자가 CLI 없이 화면 버튼 1개로 점수 계산 + 정상 실행 여부 확인.

### 결과 요약

- 신규 backend: `app/api_ml_relative_upside.py` — `POST /market/relative-upside/run` 동기 처리. `scripts.run_ml_relative_upside_score_v0.main()` 직접 import 호출.
- 신규 frontend: `RelativeUpsideRunCard` (상태/기준일/마지막 계산/점수 반영 후보 수/GPU 실행 표시 + 단일 버튼 + 실패 시 기존 result 보존).
- 수정: `MarketDiscoveryView` 가 카드의 `onSuccess` 로 후보 표 자동 재조회.
- 신규 테스트 7건 (FIX r1 후 +2): 성공 6 필드 / GPU 미확인 메시지 / 예외 시 기존 meta 파일 변경 0건 / rc≠0 → failed / meta.status≠ok → unavailable / **meta 파일 손상 → unavailable** / **main() unavailable 분기에서 기존 score snapshot 덮어쓰기 0건** (A-1 핵심). 모든 테스트 tmp_path 격리. 응답에 raw 식별자 노출 0건 검증.

### 검증

- pytest **615 passed** (608 + 7 신규 FIX r1 후, 회귀 0). black / flake8 / frontend lint / build PASS.
- 검증자 1차 REJECTED → FIX r1 (A-1 실패 시 snapshot 보존 / A-3 응답 6 필드 정정 / B-1 meta 손상 분리 / B-6 테스트 격리) 적용.
- POST 실측 — status=ok, scored 1,111 후보, gpu_execution_used=true. 사용자 친화 message.
- 기존 ML 산식 / score snapshot 구조 / OCI runner / PARAM / Telegram 변경 0건.

### 다음 분기 후보

PC_OCI_ARCHITECTURE_DIRECTION 순서:

1. **ML 축2** — 위험 감지용 시계열 빈자리 하나 채우기 STEP.
2. **점수·위험·보유 비교가 모이는 PC 판단 화면** 좁은 STEP.
3. **OCI read model foundation** — PC 판단 화면 + ML 1차 결과 확보 뒤 진입.
4. **BACKLOG CONSOLIDATED_BACKLOG_DEBT_CLEANUP**.

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.

---

## 0-prev. 이전 STEP 결과 (2026-06-20 — ML 축1 — 후보 ETF 상대상승 참고점수 v0)

지시문 §3 단일 목표: 후보 ETF 별 0~100 상대상승 참고점수 생성 + UI 비교 가능.

### 결과 요약

- 신규 backend 모듈 3종 (`app/ml_relative_upside_features.py` + `ml_relative_upside_model.py` + `ml_relative_upside_score.py`).
- 신규 CLI: `scripts/run_ml_relative_upside_score_v0.py` — end-to-end runner.
- 수정: `app/api_market_topn.py` — `MarketCandidate` / `MarketTopNResponse` 필드 확장 + 머지 함수.
- 수정 frontend 3종: 컬럼 (상대상승 참고점수 / 고점 대비 / 점수 근거) + 로컬 정렬 + USER_NOTICE.
- 신규 의존성: `torch>=2.6.0` (CUDA 12.4) — 사용자 결정 예외.
- 신규 산출물 (gitignored): `state/ml/relative_upside_score_latest.json` + `_run_latest.json`.
- 신규 테스트 24건 — drawdown 정의 / future leakage / 점수 0~100 / 시간 순서 split / reasons user-language / API 분기.
- pytest **608 passed** (회귀 0). black / flake8 / frontend lint / build PASS.

### 실측 (2026-06-20)

- universe 1,140 ticker / training row pool 66,941
- train 35,991 vs test 8,998 (walk-forward 1회 split, train_date 2026-03-20~2026-05-08 / test_date 2026-05-08~2026-05-20)
- device `NVIDIA GeForce RTX 4070 SUPER`, GPU 사용, train 0.256초
- asof_date 2026-06-19, scored 1,111 후보 (0~100)
- 기존 ml_baseline_v0 / OCI runner / PARAM / Telegram 코드 변경 0건

### 다음 분기 후보

PC_OCI_ARCHITECTURE_DIRECTION 의 순서 유지:

1. **ML 축2 — 위험 감지용 시계열 빈자리 하나 채우기**. NAV/괴리율 시계열, 변동성 지표, 외국인/기관 수급, 시장 폭 지표 중 하나의 빈자리.
2. **점수·위험·보유 비교가 모이는 PC 판단 화면** 좁은 STEP.
3. **OCI read model foundation** — PC 판단 화면 + ML 1차 결과 확보 뒤 진입.
4. **BACKLOG CONSOLIDATED_BACKLOG_DEBT_CLEANUP** — 기존 회귀 1건 + Cleanup.

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.

---

## 0-prev. 이전 STEP 결과 (2026-06-20 — PUSH 사용자 표현 정리 + PARAM 적용 UI 연결)

지시문 §3 단일 목표: 사람 중심 Telegram PUSH + 현재 운영 기준 UI 표시 +
[현재 기준 OCI 적용] 단일 UI 동작. 2 commit 으로 분할 진행.

### 결과 요약

**Phase A — PUSH 사용자 표현 정리 (commit `2a65b277`)**
- 신규 모듈 2종: `app/push_user_labels.py` (source key → 사용자 표시 라벨 8종 매핑) /
  `app/push_user_copy.py` (전체 unavailable 축약 + 일부 available 별도 확인 블록 +
  KST 시각 포맷 + push_kind 별 unavailable source key 추출).
- 메시지 builder 수정: market_briefing / spike_alert / holdings_briefing 모두
  사용자 친화 섹션 헤더 + 전체 unavailable 시 사용자 중심 축약 메시지로 fallback.
- OCI runner 안전망: raw 기술 식별자 11종 본문 노출 차단.

**Phase B — PARAM 적용 UI 연결 (이번 commit)**
- 신규 API: `GET /three-push/param/state` + `POST /three-push/param/apply`.
- 신규 frontend 카드: `ThreePushParamCard` — 현재 적용 기준 / OCI 반영 상태 /
  마지막 적용 시각 표시 + [현재 기준 OCI 적용] 단일 버튼. 진행 단계 표시 +
  실패 시 기존 PARAM 보호.
- ApprovalTelegramView 에 카드 통합 (3-PUSH 화면 안).
- 신규 테스트 3건 — state 응답 형식 + display_label 사용자 친화성 + apply 실패
  시 raw 식별자 미노출 + 기존 PARAM 보호.

### 검증 결과

- pytest **584 passed** (회귀 0, FIX r1 신규 테스트 +3). 기존 환경 실패 1건 (`test_generate_spike_alert_via_unified_endpoint`) 은 본 STEP 이전부터 존재.
- 검증자 판정 **VERIFIED_WITH_NOTES** (commit `b2946643`, FIX r1 정식 PARAM runtime builder 사용자 메시지 + UI 단일 버튼 + sync state 3분리 / FIX r2 문서 정합성 정정).
- black / flake8 PASS. frontend lint / build PASS.

### 다음 분기 후보

PUSH 메시지 사람 중심 정리 + PARAM 적용 UI 완료. 이후 후보:

1. **BACKLOG CONSOLIDATED_BACKLOG_DEBT_CLEANUP** — 기존 회귀 1건 + Cleanup
   항목 정리.
2. **scheduled run 관찰 + 운영 진단 UI** — OCI runner 의 status/history 를
   UI 에서 read-only 표시 (실패 시 사용자가 직접 확인 가능).
3. **PARAM 후보 다중 관리 / 편집 UI** — 본 STEP 제외 항목. 정책 결정 후 별도
   STEP 으로 진행.
4. **PUSH-1 의 뉴스 source 도입** — `news_snapshot` 사용자 라벨은 만들었으나
   실제 source 0건. 별도 STEP 으로 결정 필요.

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.

---

## 0-prev. 이전 STEP 결과 (2026-06-18 — PARAM Handoff 기반 OCI Runtime 3-PUSH 전환)

정식 운영 경로를 **PC message package sync → OCI 단순 전달** 에서 **PC PARAM snapshot handoff → OCI runtime 메시지 생성** 으로 전환.

### 결과 요약

- 신규 PARAM contract `three_push_runtime_param.v1` 정의 (`app/three_push_runtime_param.py`).
- 신규 backend 모듈 3종: PARAM contract / runner 공통 헬퍼 / OCI runtime 단순 빌더.
- 신규 entrypoint `scripts/run_three_push_runtime_oci.py` (정식 crontab 실행 대상).
- 신규 PARAM 스크립트 3종: create / sync / verify.
- OCI 실측: dry-run 3종 PASS / PUSH-1 send → status=sent, telegram_sent=true / duplicate guard / disabled guard / missing_latest_param fail-closed 모두 통과.
- 기존 package runner / sync 산출물은 manual recovery 로 격하 (삭제 0건).
- BACKLOG 는 CONSOLIDATED_BACKLOG_DEBT_CLEANUP 1건으로 5건 통합 기록 (중복 분산 없음).

### 다음 분기 후보

1. **OCI crontab entry 를 PARAM runtime 명령으로 갱신** — 사용자가 OCI 에서 `crontab -e` 로 `run_three_push_oci.py` → `run_three_push_runtime_oci.py` 로 교체. 격하된 PC Task Scheduler 등록을 사용 중이라면 비활성화/제거.
2. **PARAM 변경 운영 사이클 검증** — manual_seed 외 baseline_static PARAM 으로 변경 후 sync → OCI dry-run 결과 비교.
3. **OCI runtime data source 점진 확장** — 지시문 §9 unavailable 목록 (CNN F&G / VIX / USD/KRW / 원유 / news / holdings valuation) 중 어떤 것부터 available 로 전환할지 사용자 결정.
4. **기존 회귀 1건 해소** — `test_generate_spike_alert_via_unified_endpoint`.

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.

---

## 0-prev1. 이전 STEP 결과 (2026-06-18 — OCI 3-PUSH 운영 등록, PARTIAL)

PC sync와 OCI runner를 KST 07:50/12:20/15:20 sync → 08:00/12:30/15:30 send 운영
스케줄로 연결하기 위한 PowerShell wrapper + Task Scheduler 등록 절차 + OCI crontab
template 최신화. 수동 등가 실행으로 Telegram 1회 발송 + duplicate guard 통과.

### 결과 요약

- **신규 산출물 3종**: `scripts/run_three_push_sync_task.ps1` (PS wrapper) /
  `docs/handoff/PC_THREE_PUSH_SYNC_TASKSCHEDULER.md` (schtasks CLI + GUI 절차) /
  `docs/handoff/POC2_OCI_THREE_PUSH_OPERATION_REGISTRATION_CONCLUSION.md` (conclusion).
- **수정 문서 1종**: `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` — venv 경로
  `venv/bin/python` 명시 + .env 자동 로드 + PC sync 선행 시간표 + 수동 등가 실행 절차.
- **수동 등가 실행 실측**: PC sync `status=success` / OCI dry-run 3종 `dry_run_success` /
  PUSH-1 send → `status=sent, telegram_sent=true` / 동일 package 재실행 →
  `status=skipped, reason=duplicate_package, telegram_attempted=false`. token/chat_id 미노출.
- **회귀**: backend / frontend / runner / sync / message_text / 산식 변경 0건. pytest
  533 passed + 1 기존 회귀 (`test_generate_spike_alert_via_unified_endpoint`, Clean tree에서도
  동일 실패, 본 STEP 무관). frontend lint / build PASS.

### PARTIAL 사유

- 사용자 OS 등록 단계 미수행 (PC Task Scheduler 3 task + OCI crontab 3 entry)
- 첫 scheduled run 자동 trigger 결과 미확인

### DONE 격상 조건

1. 사용자가 PC에서 schtasks 3 task 등록 (`PC_THREE_PUSH_SYNC_TASKSCHEDULER.md` §3 명령 그대로)
2. 사용자가 OCI에서 crontab 3 entry 등록 (`OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` §3 template 그대로)
3. 다음 scheduled 시각(KST 07:50/08:00/12:20/12:30/15:20/15:30 중 하나)에서 자동 trigger
   결과를 `logs/three_push_sync_task.log` / `logs/three_push_cron.log` / `oci_runner_status_latest.json`에서 확인

### 다음 분기 후보

1. **scheduled run 도달 확인 → DONE 격상**
2. **stale guard 마진 검토** — 기본 36h 유지 vs OCI .env에 `THREE_PUSH_MAX_PACKAGE_AGE_HOURS=48`
3. **기존 회귀 1건 분석/해소** — `test_generate_spike_alert_via_unified_endpoint`
   (Clean tree에서도 실패. live API 의존 가능성)
4. **runtime source 수동 refresh endpoint** (이전 STEP 후속)
5. **뉴스 source 도입** (PUSH-1 보강 / 이전 STEP 후속)
6. **ThreePushDraftCard 정식 화면 위치** (이전 STEP 후속)

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.

---

## 0-prev1. 이전 STEP 결과 (2026-06-16 — OCI 3-PUSH Crontab Runner & Telegram Autosend, FIX r4 최종)

OCI 에서 crontab 으로 PUSH-1 / PUSH-2 / PUSH-3 를 자동 실행하고 조건 충족 시
Telegram 발송하는 runner 구현. (요약: 신규 `scripts/run_three_push_oci.py` + guard 7종
+ `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md`. FIX r4에서 .env 자동 로드 + HTTPError
원인 분류 추가. OCI 실측 send → telegram_sent=true / 중복 재실행 → duplicate guard.)

---

## 0-prev2. 이전 STEP 결과 (2026-06-15 — PC-to-OCI 3-PUSH Evidence Package Sync)

PC 에서 생성한 `three_push_runtime_package.v1` package 3종과 manifest 를 OCI 가
읽을 수 있는 경로로 동기화하는 최소 경로 구현.

### 결과 요약

- **신규 backend 모듈 1종**: `app/three_push_package_exporter.py`, **신규 스크립트 2종**:
  `scripts/sync_three_push_packages.py` / `scripts/verify_three_push_packages_oci.py`.
- **신규 상태 경로**: `state/three_push/packages/` + `state/three_push/sync_status_latest.json`.
- **OCI 실측** (2026-06-15): status=success, package 3/3, manifest ok.
- pytest **534 passed** (회귀 0). black / flake8 PASS.

---

## 0-prev2. 이전 STEP 결과 (2026-06-14 — 3-PUSH Context Cleanup)

직전 기능 STEP (3-PUSH Message Text Runtime Evidence 반영) 의 PARTIALLY_VERIFIED
판정 사유였던 KS-10 trigger / near 4건을 helper 모듈 분리로 모두 해소.

### 결과 요약

- **처리한 trigger / near (before → after, PowerShell 측정 기준 — 검증자 r2
  NOTES A-2 반영)**:
  - `app/push_context.py` 798→**72** (trigger 해소, format/market/holdings/spike
    4 모듈로 분리 + orchestration wrapper).
  - `scripts/diagnose_nav_discount_source.py` 984→**524** (trigger 해소, judge_* /
    record / markdown helper 모듈로 분리).
  - `app/draft_message.py` 616→**299** (near 해소, focus / summary 렌더링 분리).
  - `app/market_topn.py` 613→**347** (near 해소, 상수 / dataclass / helper 분리).
- **신규 모듈 7종**: `app/push_context_format.py` (59) / `push_context_market.py`
  (266) / `push_context_holdings.py` (202) / `push_context_spike.py` (191) /
  `app/draft_message_focus.py` (216) / `app/market_topn_helpers.py` (234) /
  `scripts/diagnose_nav_discount_source_helpers.py` (391). 모두 KS-10 safe.
- **호환성**: 기존 import 경로 (`from app.push_context import ...` /
  `from app.draft_message import ...` / `from app.market_topn import ...`) 모두
  유지. 테스트 / 호출자 코드 변경 0건.
- **검증 후 trigger / near 잔여 (git-tracked 기준, backup/ref 제외 — 사용자
  결정)**: 0건 (backend `.py` 최대 524, frontend `.tsx` 최대 691, tests `.py`
  최대 924).
- pytest **534 passed** (회귀 0). black / flake8 (신규 파일 0 warning) /
  Next.js build PASS.
- 신규 기능 / 신규 API endpoint / 신규 dependency / 신규 source / message_text
  의미 변경 / 산식 변경 0건.

### 다음 분기 후보

본 Cleanup STEP 으로 구조 안정화 완료. 직전 STEP 의 PARTIALLY_VERIFIED 사유는
해소되어 다음 기능 STEP 진입 가능.

1. **OCI runtime source 도입** — PC 에서 검증한 source 가 OCI 네트워크에서도
   작동하는지 확인 + outbox / Telegram 발송 분기 마이그레이션.
2. **하루 3회 발송 시간 + 자동 발송 UX** — scheduler / 발송 시각 / 자동 vs 수동
   트리거 결정.
3. **runtime source 수동 refresh endpoint**.
4. **뉴스 source 도입** (PUSH-1 의 [전일 기준 시장 흐름] 보강).
5. **runtime_package preview 화면 정식화** (ThreePushDraftCard).

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.

---

## 0-prev1. 이전 STEP 결과 (2026-06-14 — 3-PUSH Message Text Runtime Evidence 반영)

직전 STEP (2026-06-13 3-PUSH Runtime Package PC 검증) 에서 만든
`runtime_package` + `push_context` 의 실제 evidence 를 PUSH-1 / PUSH-2 / PUSH-3
`message_text` 에 사람이 판단에 쓸 수 있는 수준으로 반영.

### 결과 요약

- **신규 source / dependency / endpoint / OCI runtime / scheduler 0건**. ML
  산식 / Market Discovery 산식 / NAV·괴리율 산식 / universe momentum 산식 변경
  0건. 매수·매도·교체·현금비중·조정장·위험 threshold 0건.
- **수정 모듈 (라인 수 실측)**:
  - `app/push_context.py` 247→**798 라인** — observation 별 사람이 읽는 text
    + 실제 값 채움 + 헬퍼 5종 추가 (overnight_us_lines 풍부화 + market_trend_lines
    / risk_pattern_lines / holdings_observation_lines / spike_view_lines 신규).
    spike_view 가 universe momentum + Market Discovery candidates 양쪽 합쳐
    풍부 표시. `_fmt_pct` 계약 변경 (% 가정).
  - `app/message_market_briefing.py` 197→**225 라인** — `[국내 시장 내부 신호
    (Market Discovery)]` + `[위험 패턴 참고 (ML baseline 룩백)]` 2 섹션 신규.
    `_market_internal_section` 이 compute_topn `candidates` / `items` 양쪽 호환.
  - `app/message_spike_alert.py` 239→**240 라인** — 직전 STEP 의 `_spike_view_
    section` (score 만 노출) 제거 + `spike_view_lines(push_context)` 호출로
    대체. score 단독 표시 폐기 (AC-5).
  - `app/draft_message.py` 586→**616 라인** — `_runtime_evidence_lines(payload)`
    신규 + PUSH-2 본문 조립 순서 갱신 (judgment → runtime → summary → focus).
  - `app/draft.py` 559→**586 라인** — `_build_holdings_payload` 가 PUSH-2
    evidence 에 compute_topn 결과를 채움 (AC-4 — market_view 연결). compute_topn
    은 함수당 1회만 호출 후 재사용 (검증자 r2 NOTES B-6 반영). candidates
    0건 시 빈 dict 로 유지하여 FIX r3 안전장치 보존.
- **신규 테스트**: `tests/test_three_push_message_text_runtime_evidence.py`
  **638 라인** / **15건** (AC-1 / AC-2 / AC-3 / AC-4 / AC-5 / AC-7 / AC-8 /
  AC-10 검증).
- **PC 라이브 본문 실측** (stub probe — Nasdaq +0.85% / SPX +0.41% / SOX +1.25%):
  - PUSH-1: `[밤사이 미국 시장 (runtime probe)] • NASDAQ +0.85% (close 18,000.12)
    • SPX +0.41% (close 5,400.33) • SOX +1.25% (close 5,200.45) • 반도체 지수
    강세는 국내 반도체/성장 ETF 해석에 참고 가능` + Market Discovery 흐름
    1줄 + ML baseline 룩백 1줄 모두 노출.
  - PUSH-3: `[universe momentum 관찰 (push_context 기반)] • {name}: 1d +X.XX%,
    20d +X.XX% · 방향 up · data_quality 이상 없음 · 보유 종목과 겹치지 않음`
    풍부 1줄/item (4축 노출).
  - PUSH-2: `[보유 종목 관찰 포인트] • {name} ({ticker}): runtime 시세
    {±X.XX%} (가격 {N,NNN}) · 국내 기준선 — 밤사이 미국 지수 흐름과 함께 확인
    필요 — 관찰 필요` + `[시장 흐름 연결 (market_view)]` + `[리뷰 포인트]`.
- pytest **534 passed** (직전 STEP 519 → +15 / 회귀 0). black / flake8 /
  Next.js build PASS.
- ⚠ **KS-10 trigger + near**: `app/push_context.py` 798 라인 (trigger ≥650) +
  `app/draft_message.py` 616 라인 (near ≥600, trigger 까지 34 라인 여유).
  본 STEP 범위 안에서 자연 증가. 단일 Cleanup STEP 으로 두 파일 책임 분리
  권고 (사용자 확인).

### 다음 분기 후보

1. **KS-10 Cleanup — `app/push_context.py` + `app/draft_message.py` 책임 분리**.
   push_context.py 의 helper 5종 (observation builder × 3 + message line
   helper × 5) 을 별도 모듈로 분리. draft_message.py 의 신규
   `_runtime_evidence_lines` 도 같은 Cleanup 범위에 포함. UI / 문구 / 데이터
   계약 변경 금지. **다음 기능 STEP 진입 전 우선 처리 권고 (KS-10 §발동 시
   조치)**.
2. **OCI runtime source 도입**.
3. **하루 3회 발송 시간 + 자동 발송 UX**.
4. **runtime source 수동 refresh endpoint**.
5. **뉴스 source 도입**.
6. **runtime_package preview 화면 정식화** (ThreePushDraftCard).

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.

---

## 0-prev. 이전 STEP 결과 (2026-06-13 — 3-PUSH Runtime Package PC 검증)

`three_push_runtime_package.v1` 구조를 PC 에서 실제 evidence + runtime probe
(네이버 국내 시세 / Yahoo Finance 미국 지수 3종) 로 생성해 Approval/Telegram
preview 에서 상태 확인 가능한 상태까지 검증. 3종 push_kind 모두
`draft_payload.runtime_package` 에 schema_version `three_push_runtime_package.v1`
저장 — OCI handoff JSON 으로도 자동 전달. OCI runtime 구현 / scheduler / Telegram
직접 발송 / 뉴스 source / 매수·매도·교체 / ML 산식 변경 0건.

### 결과 요약

- **신규 PUSH 전용 endpoint 0건 (Q3 사용자 결정)**: PUSH-1/3 은 기존 `/runs/generate +
  input_data.push_kind`, PUSH-2 는 기존 `/runs/generate-from-holdings` 유지.
  holdings 데이터 의존성으로 PUSH-2 endpoint 통합 강요는 과한 설계자 지시였음.
- **신규 dependency 0건 (Q1 사용자 결정)**: `urllib` + `json` + `http.cookiejar` 만
  사용. `requests` / `yfinance` 추가 없음. `requirements.txt` 변경 없음.
- 신규 backend 모듈 5종 (FIX r2/r3/r4 후 실측): `app/runtime_us_indices_probe.py`
  (171 라인 — Yahoo Finance chart endpoint + cookie jar 단일 opener 캐시),
  `app/runtime_kr_quote_probe.py` (182 라인 — Naver polling endpoint),
  `app/runtime_probe_cache.py` (133 라인 — 30분 TTL cache),
  `app/runtime_package.py` (292 라인 — three_push_runtime_package.v1 빌더),
  `app/push_context.py` (247 라인 — FIX r2 추가, FIX r3 보강). 모두 KS-10 안전.
- 신규 frontend Card: `RuntimePackageStatusCard` (204 라인) — `runtime_package`
  상태 요약 + 빈 slot placeholder 노출 0건 (§14 — `status="unavailable"` 일 때
  해당 행 자체 생략).
- 수정 모듈 (FIX r2/r3/r4 후 실측): `app/draft.py` 465→552 라인 (PUSH-2 holdings
  draft 에 `runtime_package` + push_context 키 추가 + FIX r4 동기화 가드 + FIX r5
  Run.message_text 가드), `app/draft_three_push.py` 207→332 라인 (PUSH-1/3 generate
  에 cache-aware runtime probe + build_push_context + `build_runtime_package` 호출
  + FIX r5 Run.message_text 가드). `app/delivery.py` 변경 0건 — `write_handoff_artifact`
  가 draft_payload 전체를 그대로 보존하므로 runtime_package 자동 포함.
- 실측 (live API + live probe, 2026-06-13 KST 오전): Nasdaq close=25,888.844
  +0.70%, SPX close=7,431.46 +0.65%, SOX close=13,371.47 +9.42%. KODEX 200
  price=129,270 +4.38%, KODEX 코스닥150 price=18,015 +2.15%. `POST /runs/generate`
  PUSH-1/3 generation_status=ok / PUSH-2 `/runs/generate-from-holdings` generation_status=ok
  + message_text 2,507자 + `runtime_package.message_contract.message_text` 와 동일 (AC-6).
- 30분 TTL cache: cache miss → probe 1회 + 저장, cache hit → probe 0건, TTL 만료 →
  새 probe, force_refresh → bypass, 손상 → fall-through 후 재조회.
- **FIX r2 (검증자 1차 REJECTED 후속)**: (A-1 (1)) message_text 생성 흐름을
  `runtime_package → push_context → message_text` 로 정렬 — 신규 모듈
  `app/push_context.py` 추가 (현재 라인 수는 위 신규 모듈 5종 표 참조 — FIX r3
  보강 후 247 라인) + message builder 들 `push_context` 옵션 추가.
  PUSH-1 message_text 안에 `push_context.market_view.observations` 기반
  `[밤사이 미국 시장 (runtime probe)]` 1줄 섹션 추가 (probe ok 시에만 노출).
  PUSH-3 도 push_context.spike_view 기반 1줄 섹션. PUSH-2 는 push_context.market_view
  가 §7.2 필수 evidence 조건 충족. (A-1 (2)) holdings_briefing generation_status
  검증에 market_view/market_discovery_snapshot 확인 추가. (B-1) broad exception 좁힘.
  (B-6) cache 저장 정책 정렬 — 두 snapshot 모두 failed 면 저장 안 함.
- **FIX r3 (검증자 2차 REJECTED 후속)**: (A-1) `unavailable` runtime 도
  partial 로 노출 (이전엔 ok 정상 통과). push_context view 가 빈 경우 키 자체
  생략 → holdings_briefing 검증의 market_view 조건이 빈 dict 면 False. failed
  package 의 message_contract.message_text 는 빈 문자열로 강제 (정상 본문 차단).
  (A-3) STATE_LATEST §1 라인 수 실측값으로 정정. 신규 테스트 4건.
- **FIX r4 (검증자 3차 REJECTED 후속)**: (A-1 / B-1) `generate_draft_from_holdings`
  의 message_contract 동기화 단계가 FIX r3 의 "failed package 본문 비움" 안전장치를
  무력화하던 문제 해소 — 동기화 시점에 generation_status.status 확인 후 failed 면
  본문 빈 문자열 유지. (A-3) §1 안 stale 라인 수 정정. 신규 테스트 1건.
- **FIX r5 (검증자 4차 REJECTED 후속)**: (A-1 / B-1 / B-6) `Run.message_text` 도
  `runtime_package.generation_status == "failed"` 이면 None 으로 비운다. PUSH-1/2/3
  모두 동일 가드 적용 (대칭성). Run.status 는 PENDING_APPROVAL 유지. RunPanel
  preview 가 정적 fallback 으로 자연스럽게 떨어져 정상 본문이 보이지 않고
  RuntimePackageStatusCard 의 failed 상태가 함께 표시되어 사용자가 reject 결정 가능.
  (A-3) 본 문서의 stale 라인 수 5건을 실측으로 정정. 신규 테스트 2건.
- **FIX r6 (검증자 5차 REJECTED 후속)**: (A-1 / B-1 / B-6) `app/delivery.py:deliver()`
  의 holdings legacy fallback 분기가 FIX r5 의 Run.message_text=None 가드를
  무력화하던 문제 해소 — fallback 진입 전에 runtime_package.generation_status=
  failed 사전 확인 가드 추가, failed 면 DeliveryError 명시 차단 (PUSH-1/3 의 기존
  가드 패턴과 정렬). PUSH-2 holdings 도 failed package 일 때 OCI 로 정상 본문이
  발송되지 않는다. (A-3) `delivery.py` 변경 0건 표기를 233→251 라인 으로 정정.
  신규 테스트 1건.
- pytest **519 passed** (+29 신규 / 회귀 0, 직전 STEP 490 → 519, FIX r6 후). black / flake8 / Next.js build PASS.
- 사용자 결정 (Q1~Q5): urllib 기반 미국 지수 probe / Naver realtime quote probe /
  PUSH-2 endpoint 분리 유지 / runtime_package 키 1건만 추가-기존 키 유지 / 30분 TTL
  cache (refresh endpoint 없음).

### 다음 분기 후보

1. **OCI runtime source 도입** — PC 에서 검증한 source 가 OCI 네트워크에서도
   작동하는지 확인 + outbox / Telegram 발송 분기 마이그레이션.
2. **하루 3회 발송 시간 + 자동 발송 UX** — scheduler / 발송 시각 / 자동 vs 수동
   트리거 결정.
3. **runtime source 수동 refresh endpoint** — 사용자가 cache 즉시 갱신 필요 시.
4. **뉴스 source 도입** — PUSH-1 의 [전일 기준 시장 흐름] 보강.
5. **runtime_package preview 화면 정식화** — 임시 진입점 `ThreePushDraftCard` 를
   정식 화면 위치로 이동 + UX 통일.

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.

---

## 0-1. 이전 STEP 결과 (2026-06-12 — 3-PUSH Message Contract 정렬)

기존 `Run → Approval → OCI handoff → Telegram` 단일 경로를 유지하면서 하루 3종
PUSH 메시지 (`market_briefing` / `holdings_briefing` / `spike_or_falling_alert`)
의 `message_text` 계약을 정리. 새 PUSH API / Telegram 직접 발송 / OCI 재구성 /
scheduler / 신규 외부 source / 매수·매도·교체·현금비중·조정장 확정 0건.

### 결과 요약

- 신규 builder 2종: `app/message_market_briefing.py` (184 라인, PUSH-1) +
  `app/message_spike_alert.py` (209 라인, PUSH-3). 입력은 모두 read-only —
  ML baseline evidence snapshot / compute_topn / universe_momentum_latest.json.
- **신규 API endpoint 0건 (FIX r2 — 설계자 수용)**: 1차 작업에서 신설했던
  `/runs/generate-{market-briefing,spike-alert}` 는 §3 / §11 금지선과 충돌해
  **모두 제거**. PUSH-1 / PUSH-3 는 기존 `POST /runs/generate` 의 `input_data.
  push_kind` 분기로 통합. `app/api_three_push.py` 삭제.
- draft entry 2종 (`generate_market_briefing_draft` / `generate_spike_alert_
  draft`) + Run.push_kind: Optional[str] 필드 추가 (legacy run 하위호환).
- `generate_draft(input_data)` 가 `input_data.get("push_kind")` 로 분기:
  `"market_briefing"` → PUSH-1, `"spike_or_falling_alert"` → PUSH-3, 그 외 →
  기존 sample_draft 흐름 (POC1 호환).
- PUSH-2 (holdings_briefing) 는 기존 `generate_draft_from_holdings()` 재정의
  — push_kind 만 명시, builder / payload 변경 0건.
- delivery fallback 보강: message_text 누락된 PUSH-1/3 run 이 holdings builder
  로 fallback 되어 raw recommendations 발송되는 것을 명시 차단 (DeliveryError).
- frontend: Run.push_kind 타입 + 2개 API 함수 + ThreePushDraftCard (Approval
  TelegramView 안 임시 진입점). 발송 시간 / UX 확정은 별도 STEP (지시문 §13).
- 실측 (live API): PUSH-1 496자 (운영 SQLite ML baseline 위험 패턴 + checklist
  7건), PUSH-3 209자 (현재 universe 임계 ±5% 이상 spike 없음 자연 노출).
- **FIX r2 추가 변경**: (1) `SPIKE_DISPLAY_THRESHOLD_PCT` → `SPIKE_DISPLAY_
  RETURN_PCT_MIN` rename ("threshold" 단어 제거). (2) `_load_universe_artifact`
  부재/손상 구분 로그 (B-1 해소). (3) `app/models.py` docstring 갱신.
- **FIX r3 (검증자 PARTIALLY_VERIFIED 후속 — B-2 / B-3 / B-6 수용)**:
  (1) draft.py 책임 집중 해소 — PUSH-1/3 본문을 신규 `app/draft_three_push.py`
  (207 라인) 으로 분리. draft.py 623 → 465 라인 (KS-10 안전 영역 복귀).
  (2) `app/api.py` + `frontend/lib/api/runApproval.ts` 의 삭제된 endpoint /
  파일을 가리키던 stale 주석 정리.
- pytest **490 passed** (+20 신규 / 회귀 0, FIX r2 후). black / flake8 /
  Next.js build PASS.
- 사용자 결정 (1차): Run.push_kind 추가 / generate-from-holdings 를 PUSH-2 로
  재정의 / 3층 테스트. **FIX r2 (설계자 수용)**: 신규 endpoint 제거, 기존
  `/runs/generate` 의 input_data.push_kind 분기로 통합.

### 다음 분기 후보

1. **하루 3회 발송 시간 + 승인 UX 확정** — 지시문 §13 에서 본 STEP 범위 밖.
   사용자가 시간을 정한 뒤 자동 스케줄 vs 수동 트리거 vs hybrid 결정 필요.
2. **PUSH-1 뉴스 source 도입** — 본 STEP 은 뉴스 section 생략. 외부 source
   (Naver / RSS) 추가 시 별도 STEP.
3. **PUSH-3 개별 주식 universe 확장** — 본 STEP 은 ETF universe 만. 개별 주식
   급등락 source 도입 여부는 별도 STEP.
4. **draft 화면 UI 정렬** — ThreePushDraftCard 가 ApprovalTelegramView 안 임시
   진입점. 정식 화면 위치는 별도 STEP.

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.

---

## 0-1. 이전 STEP 결과 (2026-06-11 — UI 안전실행, ML evidence 갱신 background job)

기존 CLI 3종 (`generate_ml_features` → `check_ml_feature_sanity` → `run_ml_baseline_v0`) 을
Data Status 화면의 "ML evidence 갱신 실행" 버튼 1개로 안전하게 background 에서
순차 실행. CLI 는 그대로 살아있음 (이중화). Celery / Redis / 신규 DB / 외부 source
0건. 매수/매도/추천/현금비중/조정장/위험알림 0건.

### 결과 요약

- 신규 모듈 1종: `app/ml_job_runner.py` **447 라인** (KS-10 안전 — 임계 600 미진입).
  job state schema + 3단계 runner + threading.Lock (in-process) + on-disk PID +
  heartbeat (10분 stale 자동 해제).
- 신규 API 2종: `POST /ml/jobs/evidence-refresh` (background 시작, FastAPI
  `BackgroundTasks` 사용, 즉시 반환) + `GET /ml/jobs/latest` (read-only).
  `app/api_ml_jobs.py` **101 라인**.
- 신규 frontend Card: `MLEvidenceRefreshCard` **290 라인** + `frontend/lib/api/mlJobs.ts`
  **79 라인**. DataStatusView 최상단 + 실행 중 5초 polling 자동 갱신 + 단계별 상태 표.
- 단계 실패 시: 이후 단계 skipped + 전체 failed. 기존 snapshot 3종은 **삭제 안 함**
  (마지막 성공 결과 사용자 계속 조회 가능, AC-6).
- 중복 실행 차단: in-process Lock + on-disk status 검사 + PID/heartbeat 10분 stale 자동 해제.
- runtime artifact `state/ml/ml_job_status_latest.json` (gitignored).
- 실측 (uvicorn 직접): POST **2.6ms** 만에 accepted / 중복 POST **2.2ms** 만에
  already_running / 단계별 polling 정확 / 운영 SQLite 로 최종 success
  (evaluated_days=43, baseline_report_status=ok).
- pytest **470 passed** (+16 신규 / 회귀 0, FIX r2 후). black / flake8 / Next.js build PASS.
- **FIX r2 (검증자 1차 REJECTED 후속)**: (A-1/B-6) Windows 에서 `os.kill(pid, 0)` 비결정적 동작 (KeyboardInterrupt 유발) 해소 — `_PID_CHECK_SUPPORTED` OS 분기 추가, Windows 는 heartbeat 만으로 stale 판정. (B-1) status 파일 손상을 미실행과 구분 — `get_latest_status()` (state, error) tuple 반환, API status="error" 응답, POST 도 손상 시 새 job 자동 생성 안 함.
- 사용자 결정 (a)+(a)+(a): in-process BackgroundTasks / PID+heartbeat 10분 stale /
  MLEvidenceRefreshCard 신규.

### 다음 분기 후보

1. **schedule 기반 자동 실행** — 사용자가 시간(예: 18:00) 을 지정해 매일 자동 갱신.
2. **단계별 진행률** — 현재는 단계 단위 상태만 표시. feature 생성 progress bar 등.
3. **실행 히스토리** — 현재는 latest 1건만 저장. 최근 10건 보존 + UI 표.
4. **stale 알림 통합** — ML baseline evidence 가 stale 일 때 GenerateDraft 화면
   에서 "갱신이 필요합니다" 안내 + 본 STEP 의 갱신 버튼으로 deeplink.

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.

---

## 0-1. 이전 STEP 결과 (2026-06-11 — ML Baseline Evidence Draft Integration)

저장된 ML baseline v0 룩백 report 를 GenerateDraft / AI Sessions draft 의 보조
evidence 로 연결. baseline 재계산 / feature 재생성 / 외부 source 호출 / ML 학습 /
HTTP self-call 0건. 매수/매도/추천/현금비중/조정장/위험 알림 0건.

### 결과 요약

- 신규 모듈 1종: `app/ml_baseline_evidence.py` **452 라인** — JSON 파일 직접 read
  (`state/ml/ml_baseline_v0_report_latest.json`), stale 기준 `feature_asof_range.end`
  7일 초과. snapshot builder + bullet builder + factor signal builder + renderer.
- 수정 모듈 2종: `app/draft.py` (Run payload 에 `ml_baseline_evidence_snapshot`
  키 + factor_signals 에 scope="ml_baseline_evidence" entry 1건 추가),
  `app/draft_message.py` ([판단 사유] 섹션 bullet 1줄).
- draft_payload 신규 키 `ml_baseline_evidence_snapshot`: status / report_status /
  report_generated_at / feature_asof_range / evaluated_asof_range /
  candidate_summary / risk_summary / leakage_summary / limitations /
  external_context_checklist (7건) / message — 총 11항목.
- status 5종 자동 판정: ok / warn / stale (7일 초과) / unavailable (report 부재)
  / error (손상 또는 errors 존재).
- AI 외부 context checklist 7건 (CNN Fear&Greed / VIX·VKOSPI / 원유 / USD-KRW /
  미국장·선물 / 지정학 / 한국장 영향 업종) — 외부 수집 구현 0건 (질문 목록만).
- 실측: 운영 SQLite 기준 status=ok / candidate evaluated_days=40 / risk
  evaluated_days=40 / leakage 0 / external checklist 7건. report 부재 / 손상 /
  stale 모두 draft 실패시키지 않음 (조용히 빠지지 않고 status 명시).
- pytest **454 passed** (+22 신규 / 회귀 0, FIX r3 후). black / flake8 / Next.js build PASS.
- 사용자 결정 (a)+(a)+(a): JSON 직접 read / stale 7일 / [판단 사유] bullet 위치.
- **FIX r2 (검증자 1차 REJECTED 후속)**: AC-2 의 AI Sessions / Decision Evidence
  저장 경로 통합 누락 보완. `ai_session_records.ml_baseline_evidence_snapshot_
  json` 컬럼 + 자동 마이그레이션 + insert/get/SELECT 경로 + API 모델 (Create/
  Detail) + frontend (aiSessionsDraft / decisionSessions 타입 + AISessionsCreateTab
  fallback). 신규 테스트 4건 (decision store 3 + ML evidence 통합 2).
- **FIX r3 (검증자 2차 REJECTED 후속, 데이터 계약 단일화)**: AISessionsCreateTab
  fallback 이 raw `{api_status, report_path, report, message}` 를 저장하던 문제 해결.
  backend `GET /ml/baseline-v0/evidence-snapshot` 신규 (GenerateDraft 와 동일 shape).
  frontend `fetchMlBaselineEvidenceSnapshot()` 신규 + AISessionsCreateTab fallback
  교체. fetch 실패 시에도 status="error" 정규화 snapshot 으로 채움 (silent fallback
  제거). 신규 테스트 2건 (evidence-snapshot API ok / unavailable).

### 다음 분기 후보

1. **report stale 시 CLI 재실행 안내 UI** — Data Status 카드 옆 안내 배지.
2. **5년 backfill 후 evidence 신호 강도 시계열 분해** — rolling window.
3. **§6.6 제외 source** (CNN Fear&Greed / VKOSPI / 외국인·기관 수급) — BACKLOG.

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.

---

## 0-1. 이전 STEP 결과 (2026-06-11 — ML Baseline v0 룩백 검증)

현재 feature dataset 이 과거 구간에서 (1) 상승 후보 발굴 / (2) 위험 구간 감지
baseline 으로 의미가 있었는지 룩백 검증. CLI 전용. 매수/매도 판단 X,
위험 알림 X, 조정장 확정 X, 위험 threshold X.

### 결과 요약

- 신규 모듈 4종 (FIX r2 후 실측): `app/ml_baseline_targets.py` (352) + `ml_baseline_candidate.py` (426) +
  `ml_baseline_risk.py` (390) + `ml_baseline_v0.py` (199 — orchestrator). KS-10 trigger/near 0건.
- 신규 API: `GET /ml/baseline-v0/latest` (snapshot read-only, 재계산 X / 외부 호출 X).
- CLI: `scripts/run_ml_baseline_v0.py` + Snapshot `state/ml/ml_baseline_v0_report_latest.json` (gitignored).
- Frontend 신규: `MLBaselineV0Card` (DataStatusView 하단). 매수/매도/위험 알림 문구 0건.
- 사용자 결정: (a) candidate top group = top quintile 20%, (a) risk group split = market composite tercile 1/3, (a) horizon tail = max horizon 20d 제외.
- 실측 (1137 ETF × 60거래일 / 평가 40거래일): **status=ok**. leakage 0. candidate top group 5d/10d/20d future return = 3.4%/5.5%/13.5% vs universe median 1.1%/2.1%/4.7%. risk high vs low future drawdown 10d = -8.1% vs -3.4% (위험 group 약 2.4x), drawdown_capture_rate 10d = 1.44.
- pytest **432 passed** (+15 신규, 회귀 0, FIX r2 후). black / flake8 / ESLint / Next.js build PASS.

### 다음 분기 후보

1. **NAV 일별 적재 / backfill** — Sanity 가 노출한 unavailable_ratio 0.98 해소.
2. **5년 backfill** — `--start-date 2021-06-08` 로 평가 가능 거래일 ≫ 40일 확장.
3. **Baseline v0 후속 — 시계열 rolling window 평가**: 본 STEP 의 단일-기간 평균을 rolling window 별로 분해.
4. **§6.6 제외 항목** (CNN Fear&Greed / VKOSPI / 외국인·기관 수급 등) — BACKLOG.

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.

---

## 0-2. 이전 STEP 결과 (2026-06-08 — ML Feature Sanity Check)

ML baseline v0 입력 직전 데이터 품질 검산. CLI 전용. 4 sub-check
(coverage / calculation / NAV join / risk proxy).

### 결과 요약

- 신규 모듈 2종: `app/ml_feature_sanity.py` (561 라인 — FIX r3 후) +
  `ml_feature_sanity_helpers.py` (141 라인). KS-10 trigger/near 0건.
- 신규 API: `GET /ml/feature-sanity/latest`. CLI: `scripts/check_ml_feature_sanity.py`.
- Snapshot: `state/ml/ml_feature_sanity_latest.json` (gitignored).
- Frontend: `MLFeatureSanityCard`.
- FIX r3 (검증자 1차 REJECTED 반영): coverage §4.3 누락 보강 (ticker별 row 누락 + asof drop) + snapshot 손상 fail-loud + untracked staging.
- 실측 (FIX r3 후): sanity_status=warn / ticker 1137 중 row 누락 69건 신규 감지 / calc 0 err / future_nav_join=0. pytest 417 passed.

### 다음 분기 후보 (당시)

→ 본 STEP (ML Baseline v0 룩백 검증) 으로 진입 (사용자 결정).

---

## 0-3. 이전 STEP 결과 (2026-06-08 — ML 최소 데이터 레인 1차)

ML baseline v0 입력 직전 데이터 품질 검산. CLI 전용 실행. ML 모델 / 위험 threshold /
매수·매도 판단 X.

### 결과 요약

- 신규 모듈: `app/ml_feature_sanity.py` (491 라인) + `app/ml_feature_sanity_helpers.py`
  (141 라인, FIX r2 분리). 4 검산 (coverage / calculation / NAV join / risk proxy).
- 신규 API: `GET /ml/feature-sanity/latest` (snapshot read-only, 재계산 X).
- CLI: `scripts/check_ml_feature_sanity.py` + Snapshot `state/ml/ml_feature_sanity_latest.json` (gitignored).
- Frontend: `MLFeatureSanityCard` (DataStatusView) — 7축 sub-check 상태 + 샘플 ETF 10건.
- 허용 오차 (사용자 결정 b): `abs_tol=1e-4 + rel_tol=1e-4`. risk proxy 이상치는 null 비율만 (사용자 결정 f).
- 실측: 1137 ETF × 60일 / sanity_status=warn / calc 0 error / future_nav_join=0 /
  risk all-null=0 / warning 2건 (NAV 분포 unavailable_ratio 0.983 — universe NAV refresh 1회만 적재된 운영 상태).
- pytest 414 passed (회귀 0). Next.js build PASS.

### 다음 분기 후보

1. **ML baseline v0** — 본 sanity check 통과한 dataset 입력. 상승 후보 점수화 +
   위험 구간 분류 binary 모델. threshold / label 확정 (별도 STEP).
2. **NAV 일별 적재 / backfill** — sanity 가 노출한 unavailable_ratio 0.983 해소.
   `etf_nav_daily` 가 universe refresh 1회만 적재 → 일별 누적 흐름 설계.
3. **5년 backfill** — `--start-date 2021-06-08` 로 장기 시계열 적재.
4. **§6.6 제외 항목 (CNN Fear&Greed / VKOSPI / 외국인·기관 수급 등)** — BACKLOG.

---

## 0-1. 이전 STEP 결과 (2026-06-08 — ML 최소 데이터 레인 1차)

ML baseline v0 가 바로 읽을 수 있는 daily feature dataset 을 SQLite 에 적재.
CLI 전용 실행 — 화면 / refresh 흐름 hook 0건. ML 모델 / 라벨 / 예측 / threshold X.

### 결과 요약

- 신규 테이블 2종 (`etf_ml_feature_daily` PK=(asof,ticker), `market_risk_feature_daily` PK=asof).
- 신규 모듈 3종: `app/ml_feature_store.py` / `app/ml_feature_builder.py` /
  `app/api_ml_readiness.py`.
- 신규 CLI: `scripts/generate_ml_features.py` (`--start-date` / `--end-date` /
  `--lookback-days` 기본 60거래일 / `--ticker` / `--no-snapshot`).
- 신규 read-only API: `GET /ml/readiness/latest`.
- `MLTimeseriesReadinessCard` 7축으로 갱신 (정적 9축 → API 응답 기반 7축).
- Snapshot: `state/ml/ml_feature_snapshot_latest.json` (gitignored).
- 실측: 1137 ETF × 60일 → 65,691 ETF row + 60 market risk row / 4.46초.
- pytest 405 passed (395 → 405 / 회귀 0). Next.js build PASS.

### 다음 분기 후보

ML baseline v0 가 본 dataset 을 입력으로 바로 시작 가능. 분기:

1. **ML baseline v0** — 본 feature dataset 을 입력으로 상승 후보 점수화 모델 +
   위험 구간 분류 (binary). 모델 / threshold / label 확정은 본 STEP 내용을 기반
   으로 새 STEP 에서 진행.
2. **CLI hook** — market refresh 직후 자동 ml_features generation hook 추가
   (현재는 의도적으로 분리).
3. **NAV / 괴리율 시계열 누적** — 이미 본 feature 에 join 되어 일부 노출. 별도
   feature 시계열로 분리 누적 검토.
4. **CNN Fear&Greed / VKOSPI / 외국인·기관 수급 / KOSPI 전체 시장 폭 / 구성종목
   가격 시계열** — 본 STEP §6.6 에서 제외 명시. BACKLOG 후보.

---

## 0-1. 이전 STEP 결과 (2026-06-08 — Market Discovery UI / Perf 후속 정리)

NAV / Discount Display FIX 직후 사용자가 즉시 보낸 UI 정리 요청 / perf 지적 5건을
연속 commit (`6c3728ec` → `8fad2bb4`) 으로 반영. 별도 STEP 보고서는 만들지 않고
검증자 전달용 note 만 생성 (`POC2_MARKET_DISCOVERY_UI_PERF_USER_FEEDBACK_NOTE.md`).

핵심:
- CandidateTable 컬럼 정리 (source/status/정렬기준/태그 제거, 6m/12m/1y/3y 추가).
- TopControlsRow 1 카드 안에 갱신+필터 + AI Sessions·ETF Exposure 전달 버튼 묶기.
- MarketContextCard 헤더에 `(069500) KODEX 200 (필수)` / `(KS11) KOSPI (보조)` 표기 +
  현재가/MA20/MA60 천단위 콤마.
- 백엔드 `MarketReturns` 모델 6m/12m/3y 필드 추가 (lookback 180/365/1095).
- `/market/topn/latest` 응답 2.4s → 0.85s (process-level init_db 캐시 + name bulk).

다음 분기 후보 영향: 없음 (분류는 §0-1 유지).

---

## 0-2. 직전 빈자리 채우기 STEP 결과 (2026-06-08 — NAV / Discount Display FIX)

직전 STEP(Naver ETF Universe NAV / 괴리율 연동)이 저장은 완료했지만 사용자가
주요 화면에서 NAV 값을 한눈에 확인하기 어려운 표시 누락이 있었다. 본 FIX 로
표시 매트릭스 6필드 × 4화면 모두 visible 상태로 정정.

### 결과 요약

- 신규 read-only API `GET /market/nav-discount/latest` — 저장된 `etf_nav_daily`
  전체 ETF (1136건 실측) 1회 응답. 외부 source 호출 X, refresh X.
- Data Status 화면 재설계 — placeholder → 전체 ETF NAV / 시장가 / 괴리율 표 +
  검색(ticker/이름) + status 필터 + 괴리율 정렬.
- Market Discovery CandidateTable — NAV / 시장가 / 괴리율 / asof / source /
  status 6 컬럼 직접 노출 (FIX 라운드 2 에서 tooltip → 직접 컬럼으로 정정).
- ETF Exposure NavDiscountPlaceholderCard — flag/source 통합 컬럼 → asof / source /
  status 분리 컬럼 + flag 인라인.
- Holdings Evidence NavDiscountLine — asof / status 추가 (이전 NAV·시장가·괴리율·source).
- 표시 매트릭스 (지시문 §5): MD/ETF Exposure/Holdings Evidence/전체 ETF 조회 × NAV·시장가·괴리율·asof·source·status = 모두 visible.
- 기존 `data_quality.nav_discount` 응답 계약 / `etf_nav_daily` schema 무변경.
- pytest 395 passed (391→395 / 회귀 0). Next.js build PASS.

---

## 0-1. 이전 STEP 결과 (2026-06-08 — Naver ETF Universe NAV / 괴리율 연동)

NAV / Discount Source Diagnosis 1차 (2026-06-07) 에서 발굴한 source 후보 +
친구 프로젝트(momentum-etf) 분석으로 확인한 `finance.naver.com/api/sise/etfItemList.nhn`
universe 단일 호출 패턴을 운영 fetcher 로 채택.

### 연동 결과

- 신규 모듈: `app/naver_etf_universe_fetcher.py` — TTL 30s + stale 재사용.
- `etf_nav_service.refresh_nav_universe()` 추가 — 1회 호출 → 전체 ETF universe
  `etf_nav_daily` upsert (per-ticker N회 호출 패턴 폐기).
- `market_refresh_service`: 기존 NAV hook(per-ticker 10건 cap)을 universe refresh
  로 교체. 실패 격리 정책 유지.
- `scripts/refresh_nav_universe.py`: 수동 실행 CLI (운영 API / 정기 job 연결 X).
- summary artifact: `state/market/nav_discount_refresh_latest.json`.
- Frontend: Market Discovery / ETF Exposure NavDiscountPlaceholderCard /
  Holdings Evidence Card 모두 unavailable 고정 → 실제 NAV / 시장가 / 괴리율 표시.
- 기존 `data_quality.nav_discount` 응답 계약 / `etf_nav_daily` schema /
  괴리율 threshold 무변경. 신규 API 0건. MongoDB 추가 0건.

### 다음 분기 후보 (사용자 결정 영역)

1. **NAV / 괴리율 시계열 누적** — universe 단면 스냅샷 → asof 일자별 누적.
   `etf_nav_daily` PK 가 이미 `(ticker, asof, source)` 라 자동 누적되지만,
   누적된 시계열을 ML readiness 카드에 반영하고 위험 감지 축 2 의 1차 후보로
   사용할지는 별도 결정.
2. **위험 감지 지표 시계열 적재 1차** — VKOSPI / Fear&Greed / 외국인·기관 수급 /
   시장 폭 후보 진단.
3. **구성종목 가격 시계열 source 진단** — ETF Exposure 등락률 unavailable 해소.
4. **MDD / Sharpe 계산 도입**.

---

## 0-1. 이전 빈자리 채우기 STEP 결과 (2026-06-07 — NAV / Discount Source Diagnosis 1차)

ETF Exposure Data Unfolding 1차 §0 "빈자리 후속 원칙" 에 따라 NAV / 괴리율
source 진단을 수행. 운영 fetcher 교체 X, source integration X.

### 진단 결과 요약

- pykrx (ohlcv / price_deviation): 모든 ticker × 날짜 empty → **unusable**
- FinanceDataReader: 시장가격 안정, NAV 직접 제공 X → **hold_unstable**
  (NAV source 와 결합 시 괴리율 계산 후보)
- Naver Mobile stock integration API: NAV + 시장가격 4/4 ticker OK
  (`$.etfKeyIndicator.nav`, `$.dealTrendInfos[0].closePrice`)
  → **hold_unstable** (비공식 endpoint — 운영 안정성 추가 진단 권고)
- Naver ETF dedicated endpoint 후보: 전부 HTTP 404 → **unusable**

**adopt_candidate 0건**. 단, naver_mobile_stock_integration 은 운영 안정성
추가 검증 STEP 거치면 adopt 승격 가능.

### 다음 분기 후보 (사용자 결정 영역)

빈자리 후속 원칙은 그대로 유효하다 — 다음 기능 STEP 은 여전히 빈자리 중
하나를 채우는 STEP 으로 제한한다.

1. **Naver Mobile NAV Source Stability 1차** — naver_mobile_stock_integration
   응답시간 / TTL / schema 변경 모니터링 / 다일 sample 확장. 결과에 따라
   adopt_candidate 승격 또는 unusable 하향.
2. **다른 빈자리로 전환** — 구성종목 가격 시계열 source 진단, 위험 감지 지표
   시계열 적재 후보 진단 등 (BACKLOG 참고).
3. **KRX OPEN API 인증키 확보 검토** — hold_auth_required 후보 발굴.

위 분기 중 어느 것을 선택할지는 사용자 결정. 본 문서에서 임의 확정하지 않는다.

---

## 0. 현재 최우선 작업 (2026-06-06 — ETF Exposure Data Unfolding 1차 완료)

### ETF Exposure Data Unfolding 1차 (DONE)

기존 ETF Exposure 화면의 구성종목 / 중복률 / 반복 핵심 종목 데이터를 펼쳐서
비교 가능하게 표시. Holdings Evidence 와는 State Bridge (명시 호출 버튼) 로
결합. ML / 위험 감지에 필요한 시계열 데이터 9축의 준비 상태를 화면 + 문서에
명시.

- 신규 API 0건. 신규 source 0건. 시계열 적재 job 0건.
- 신규 컴포넌트 3건: HoldingsOverlapBridgeCard / NavDiscountPlaceholderCard /
  MLTimeseriesReadinessCard.
- 위험 감지는 "하락 예측"이 아니라 "위험 구간 분류" 로 정의 — INTENT §9.5,
  ASSUMPTIONS Q6.
- pytest 379 passed (회귀 0). frontend Next.js build PASS.

### 빈자리 후속 원칙 (불변)

**ETF Exposure Data Unfolding 1차 이후 다음 기능 STEP 은 본 STEP 에서 드러난
빈자리 중 하나를 채우는 STEP 으로 제한한다.**

화면 + 문서에 명시된 빈자리:

1. **NAV / 괴리율 source** — `not_integrated`. source 진단 STEP 후보.
2. **구성종목 가격 시계열** — `not_integrated`. 구성종목 등락률 unavailable
   해소.
3. **위험 감지 지표 시계열** (변동성 / 거래량 급변 / 외국인·기관 수급 / 시장 폭) —
   `not_collected` / `not_calculated`. 축 2 선행 조건.
4. **MDD / Sharpe 계산** — 현재 미구현. 시계열 적재 후 1차 지표.

어떤 빈자리를 먼저 채울지는 **사용자 판단 영역**이다. 본 문서에서 임의로
순서를 확정하지 않는다.

위 제약은 ML / 백테스트 / 자동 매수·매도 판단 추가를 금지하는 의미가 아니라,
**시계열 데이터가 부족한 상태에서 ML 모델로 점프하지 않는다**는 의미다.

본 문서는 다음 챕터 진입자가 한 번 읽고 "지금 무엇을 해야 하는지" 를 즉시
파악할 수 있도록 작성되었다 — 단기 (현재 STEP) / 중기 (바로 다음 후보) /
보류 (지금 멈춘 것) 의 3 단으로만 구분한다.

---

## 1. 현재 최우선 작업 (2026-06-03 — Holdings × Market Discovery Evidence 1차 완료)

### Holdings × Market Discovery Evidence 1차 (DONE)

사용자의 실제 holdings 를 Market Discovery evidence (TOP N 후보 일치 여부 /
시장 국면 / KODEX200 대비 1m·3m 초과수익 / 5·10·20거래일 단기 흐름 / 구성종목
중복 / NAV) 와 raw evidence 수준에서 연결했다. PROJECT_ORIGIN_INTENT §3 PC
작업 4~5단계 (매매 결정 / 보류 + 결정 기록) 의 정량 재료 1차.

- 신규 read-only API `GET /holdings/market-evidence/latest` — 외부 fetch 0건.
- GenerateDraft 가 같은 evidence builder 를 재사용 — draft_payload.holdings_market_evidence_snapshot
  + factor_signals scope="holdings_market_evidence" + [판단 사유] 1줄.
- Strict Cache-only: 보유 ETF 구성종목 외부 source 신규 호출 0건.
- NAV source 신규 채택 0건 (기존 unavailable 흐름 유지).
- 매수/매도/교체 판단 어휘 0건 (회귀 테스트로 보장).
- pytest 379 passed (354 → 379, +25 신규 / 회귀 0).

### 다음 큰 방향 (사용자 결정 대기)

1. **AI Sessions 기록 복기 구조** — 누적 기록의 검색 / 비교 / 후속 판단
   회수율 측정.
2. **NAV / 괴리율 source 진단 STEP** — 직전 ETF Constituents Source Diagnosis
   패턴 따라 source 후보 smoke test 후 채택 검토.
3. **보유 ETF 구성종목 외부 source 채택** — Strict Cache-only 가 본 STEP
   범위였으므로 보유 ETF 의 구성종목 cache 가 없는 경우 후속 STEP 에서 채택
   여부 결정 (BACKLOG 후보).
4. **ML factor 후보 정리** — ASSUMPTIONS Q1 (여러 factor 를 붙일 수 있는
   구조의 엔진).
5. **ML / 백테스트 연결**.

### 별도 분기 후보 (Market Discovery 영역으로 회귀하는 경우만)

- **NAV / 괴리율 source 진단 STEP** — 직전 ETF Constituents Source
  Diagnosis 패턴 따라 Naver Stock detail endpoint 등 candidate source
  smoke test 후 채택 검토.

### (이전) KS-10 Cleanup: API Client / Type 책임 분리 (DONE 2026-06-03)

`frontend/lib/api.ts` 993 라인 단일 파일을 도메인 8개 모듈 + barrel 로 분리.
`@/lib/api` import 호환 유지 (21 컴포넌트 0건 수정). 활성 코드 trigger / near 0.
검증자 NOTE FIX 2건 반영 — A-2 카운트 정정, B-6 `request` barrel public 제외.

### (이전) Market Discovery Evidence Closeout 1차 (DONE 2026-06-01)

본 STEP 으로 Market Discovery 1차 증거 묶음을 마감했다. 단기 흐름 + 일간
플래그 + NAV / 괴리율 인프라 + AI Sessions 증거 snapshot 까지 통합 완료.
**Market Discovery 계열 신규 기능 확장은 일단 중단**한다.

### (이전) ETF Constituents Naver Source Integration (DONE 2026-05-31)

본 STEP 의 산출물은 [docs/handoff/STATE_LATEST_ARCHIVE.md](STATE_LATEST_ARCHIVE.md) §0.1 (2026-05-31 ETF Constituents Naver Source Integration) 참조.

- `naver_stock_etf_component` 를 1차 source 로 채택. service 의 cache key 도
  새 source 매칭.
- DB 스키마 4 컬럼 확장 + 자동 마이그레이션 (직전 STEP DB 호환).
- 해외형 ETF (`componentItemCode=null`) 도 `componentReutersCode` /
  `componentIsinCode` 보존 + 매칭 키 우선순위 확장 (constituent_key → ticker →
  reuters → ISIN → name).
- ETF Exposure / 구성종목 Refresh / 중복률 / AI 문구 [구성종목/중복 노출] 섹션
  모두 사용 가능 으로 전환 (POC2_FEATURE_INVENTORY 반영).

### 다음 후보 (참고만): C. KRX Open API / Official Provider Source Design (기존)

**실측 근거** (2026-05-31 Source Diagnosis 1차):
- pykrx `get_etf_portfolio_deposit_file` — 3 ETF × 5 날짜 = 15 호출 모두
  `no_data` (예외 0건, df 0 rows). **pykrx_operational_issue** 분류. **hold**.
- Naver Mobile ETF Component API — 3 ETF 모두 HTTP 404. **unusable**.
- 지시문 §21.C: "Naver Mobile API 사용 불가 + pykrx 사용 불가" → KRX Open API
  설계 후속 후보.

본 다음 STEP 의 범위 (지시문 §8 / §21.C):
- KRX Open API 인증키 필요 여부 확인.
- 호출 한도 / 응답 구조 / ETF 별 커버리지 / 구성종목 비중 제공 여부.
- K6 방어 가능 여부 (기존 service 의 10개 cap / 0.5s delay / 30s budget /
  partial / unavailable 정책에 fit 하는지).
- 인증키 활성화 대기 동안에는 ETF Exposure 메뉴를 사용 불가 상태로 인벤토리
  명시 (`docs/handoff/POC2_FEATURE_INVENTORY.md` §2.10~12).

### (이전) ETF Constituents & Overlap 1차

- 좌측 메뉴에 `ETF Exposure` 추가 (Market Discovery 와 화면 분리).
- Market Discovery → ETF Exposure draft 전달 (sessionStorage Context Bridge).
- pykrx PDF (`get_etf_portfolio_deposit_file`) 1차 fetcher + K6 방어 (10개
  cap / cache-first / 0.5s delay / 30s budget / partial / unavailable).
- POST /market/constituents/refresh + GET /market/constituents/analysis.
- 집중도 (top 1/3/5/10) + 쌍별 중복률 (common_count_top10 +
  weighted_overlap_pct = sum(min(left, right))) + 반복 등장 핵심 종목.
- AI 투자세션 복사용 문구에 [구성종목 / 중복 노출] 섹션 + 새 요청 문구
  (독립 테마 vs 반복 노출 판단).
- AI Sessions Context Bridge / POST /decision/sessions / 상세 화면 모두에
  `constituent_snapshot` / `overlap_snapshot` 영속화 (마이그레이션 포함).

본 STEP 의 범위는 "실제 노출 구조 확인" 까지다. 매수/매도 판단 / 리밸런싱 /
NAV / 유동성 점수화는 본 STEP 의 작업이 아니다.

### (이전) Market Regime & Benchmark Context 1차

- 시스템이 KODEX200 (필수) / KOSPI (보조) 기준으로 **1차 시장 국면 판정** 산출.
- 라벨: 상승장 / 보합장 / 하락장 / 판정불가 (regime_code: bull / neutral /
  bear / unavailable).
- 점수 방식: KODEX200 20거래일 / 60거래일 수익률 + MA20/MA60 위치 4 항목을
  +1/-1/0 으로 합산 → +2 이상 bull / -2 이하 bear / 그 외 neutral.
- Market Discovery 응답 (`GET /market/topn/latest`) 에 `market_context` +
  각 candidate 의 `excess_return` (vs KODEX200 / KOSPI 1m / 3m %p) 포함.
- Market Discovery 화면에 시장 배경 카드 + 후보 테이블에 KODEX200 대비 1m/3m
  컬럼 추가.
- AI 투자세션 복사용 문구에 [시스템 시장 판정] + [시장 대비 후보 강도] 섹션 추가.
- AI 요청 문구를 **AI 에게 장세 판정을 맡기지 않고** 시스템 판정 전제 + 해석/
  반론 요청으로 변경.
- Market Discovery → AI Sessions Context Bridge draft 에
  `market_context_snapshot` 포함. POST /decision/sessions 가 저장하고 GET
  상세에서 노출.

본 STEP 의 범위는 "정량 1차 판정 + benchmark context + 화면/문구/저장소
연계" 까지다. 완성형 시장 정권 모델 / KOSDAQ 비교 / ETF 구성 종목 / NAV /
ML 연결 / 매수·매도 판단은 본 STEP 의 작업이 아니다.

---

## 2. 바로 다음 후보 (사용자 결정 대기)

순서는 우선순위가 아니다 — 사용자가 명시 지시문으로 선택한다.

1. **시장 국면 판정 고도화** (2026-05-27 본 STEP 1차 후 후속)
   - 본 1차는 단순 점수 합산. 다음 단계 후보: 변동성 / 시장 폭 (advance-decline) /
     장기 추세 / 외인·기관 수급 등을 점수에 반영해 라벨 신뢰도 향상.
   - 운영 데이터로 1차 판정의 적중률을 검증한 뒤 진행.
2. **NAV / 괴리율 / 유동성**
   - 종목 선정 단계 진입 시 필요. ETF 가격이 NAV 와 얼마나 떨어져 있는지,
     거래량이 충분한지.
4. **AI 투자세션 결과 기반 개선**
   - 누적된 `ai_session_records` 를 1개월 운영 후 들여다보고, 어떤 판정 / 메모 /
     다음 확인 항목이 반복되는지 분석. 운영 데이터를 기반으로 다음 발굴 단위 /
     비교 기간 / 점수체계 후보를 도출.

---

## 3. 지금 멈춘 것 (보류 / 제외)

본 항목들은 영구 제외가 아니라 **현재 단계에서는 진행 중단**.

- **KOSDAQ 비교** — 기본 비교 대상에서 제외 (사용자가 코스피 중심으로 투자).
- **UI Grid 재정리** — 컬럼 추가 / 정렬 옵션 증설 / 차트 도입 등은 멈춘다.
  Grid 사용성은 직전 STEP (2026-05-19 GRID 우선 + 컬럼 클릭 정렬) 로 충분.
- **ML 연결** — 아직 아님. 점수 산식 / factor weight 자동 결정 모두 보류.
  ML 단계는 ASSUMPTIONS L-2 가 답 나올 때 다시.
- **매수 / 매도 자동 판단** — 시스템 책임 경계에 명시적으로 없다
  (PROJECT_ORIGIN_INTENT §3 "매수/매도 API 자동화 없음").
- **자동 AI 토론 / AI API 직접 호출** — 본 STEP 까지의 모든 AI 사용은
  외부 채널 + 사용자 손으로 paste. AI API 직접 호출은 다른 STEP 으로 분리.

---

## 4. 중요한 사용자 결정 (불변 앵커)

본 결정은 다음 STEP 진입 전 흔들리면 안 된다. 흔들리면 KS-11
(의사결정 24시간 룰) 발동 — 새 데이터 / 근거를 ASSUMPTIONS 또는
PROJECT_ORIGIN_INTENT 에 기록 후 변경.

1. **사용자는 코스피 중심으로 투자한다.**
2. **KODEX200 / KOSPI 비교는 유효하다.** — 발굴 ETF 의 alpha 측정 기준.
3. **KOSDAQ 비교는 기본 비교 대상이 아니다.**
4. **AI 질문 / 답변은 반드시 기록되어야 한다.** — 본 STEP 의 핵심 동기.
   기록 없는 AI 토론은 향후 검증 불가능 → 운영 학습 자산 손실.
5. **AI 답변은 GPT / Gemini / Claude 로 분리 기록한다.** — 2026-05-21 추가.
   3 채널 답변을 같은 셀에 합쳐 저장하지 않는다. 채널별 해석 차이를 사후
   복기할 수 있어야 한다.

---

## 5. 이 문서의 사용 규칙

- 본 문서는 **새 STEP 진입 시 가장 먼저 읽는 1개 문서** 다.
- 본 문서는 설계서가 아니다 — 결정 변경 시 PROJECT_ORIGIN_INTENT.md 또는
  ASSUMPTIONS.md 를 변경하고, 본 문서는 그 변경을 짧게 반영한다.
- 본 문서는 시간이 지나면 **현재 STEP** 만 갱신한다 — "바로 다음 후보" 와
  "지금 멈춘 것" 의 큰 흐름은 분기 1회 사용자 본인이 검토한다.

---

Active Reference:
3-PUSH Runtime Package Contract
- path: docs/handoff/THREE_PUSH_RUNTIME_PACKAGE_CONTRACT.md
- purpose: PC/OCI가 공유하는 three_push_runtime_package.v1 schema 계약
- usage: PUSH 후속 Step에서는 evidence package / runtime snapshot / message_text 설계 시 이 문서를 기준으로 한다.
