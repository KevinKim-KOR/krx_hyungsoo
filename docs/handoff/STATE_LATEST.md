# STATE_LATEST.md

최종 업데이트: 2026-05-11

---

## 1. 현재 상태

```text
현재 단계: POC2-Step7A 완료 (검증자 VERIFIED_WITH_NOTES, 2026-05-11) — 신규 ETF 관찰 후보 (PUSH 2) 최소 운영화
다음 단계: 사용자 협의 후 후속 구현 Step 1개 선택 (PUSH 1 / PUSH 3 / 운영 빈도 정합성 보정)
```

POC2-Step7A 검증 통과 commit chain:
- 3d9112d5 feat(poc2-step7a): align label + starter seed for new ETF watch candidate

검증자(Codex) 라운드 흐름:
- 1차 검증: VERIFIED_WITH_NOTES (B-6 KST 시간대 의존 NOTE 1건).
- B-6 처리: 본 STEP §5 알려진 한계로 이미 명시 + PROJECT_ORIGIN_INTENT §7 K6/EOD
  KST 전제 부합 → 수정 불필요 판정 (사유 1줄 보고).
- A-1 / A-2 / A-3 / A-4 + B-1 ~ B-5 모두 통과.
- 잔존 NOTE 는 운영 주의 수준이며 향후 timezone 도입 시 재검토.

POC2-Step7A 요약 (본 STEP):
- **명칭 정렬**: 사용자 노출 "외부 후보 점검" → 공식 PUSH 2 명칭 **"신규 ETF 관찰 후보"**
  로 정렬. 내부 함수명 / 파일명 / factor_id 는 변경 없음.
- **starter seed 도입**: seed 파일 부재 시 KODEX 200 + KODEX 미국S&P500 + KODEX
  미국나스닥100 3개 후보로 starter seed 자동 생성. **기존 사용자 seed 는 절대 덮어쓰지
  않음**. starter seed 는 투자전략 확정값이 아니며 기능 작동 확인용.
- **POST 응답 source 노출**: `summary.source` 필드로 UI 가 "기본 후보군 사용" 안내 표시.
- 새 endpoint 미도입. 새 draft_payload 키 미도입. 데이터 계약 변경 0건.

검증:
- pytest 119 → **147 passed** (Step6 16 + Step7A 11 추가).
- black / flake8 / TypeScript build / Next.js lint 모두 PASS.
- KS-10 임계: 백엔드 max 572 / 프론트 max 515 / 테스트 max 924 — 트리거 0 + 근접 0 유지.

신규 / 수정 파일:
신규:
- docs/handoff/POC2_STEP7A_NEW_ETF_WATCH_CANDIDATE_MINIMAL_PUSH.md (Step7A 종결 문서)
- tests/test_step7a_etf_watch_candidate.py (Step7A 회귀 11개)

수정:
- app/draft_message.py (EXTERNAL_UNIVERSE_BULLET_LABEL 정렬)
- app/draft.py (_build_universe_factor_signal 의 factor_name 정렬)
- app/universe_seed.py (STARTER_SEED_ITEMS + ensure_seed_file_exists 신규)
- app/api_universe.py (ensure_seed_file_exists 호출 + summary.source 노출)
- frontend/lib/api.ts (UniverseRefreshSummary 에 source 옵셔널 필드 추가)
- frontend/app/components/JudgmentReasonSection.tsx (default factor_name 정렬)
- frontend/app/components/UniverseRefreshPanel.tsx (헤더 / 버튼 / 안내 문구 정렬 + starter seed 안내)
- frontend/app/components/MainPanel.tsx (주석 정렬)
- tests/test_universe_momentum_step6.py / tests/test_universe_seed.py (라벨 정렬)

다음 단계:
- 사용자 협의 후 후속 구현 Step 1개 선택 (한 번에 하나의 PUSH 원칙 — Step7 §13).
- 후보: PUSH 1 보유 종목 상태 브리핑 / PUSH 3 급락 ETF 주의 신호 / 운영 빈도 문서 정합성 보정.

---

## 1.1 직전 상태 (POC2-Step7 설계서 저장)

```text
이전 단계: POC2-Step7 설계서 저장 완료 (CONDITIONAL_PASS, 2026-05-11) — 구조 재정렬 설계 단계
```

POC2-Step7 저장 요약 (본 작업):
- 신규 설계서: docs/handoff/POC2_STEP7_SYSTEM_OUTPUT_3_PUSH_REALIGNMENT_DESIGN.md
- 레드팀 결과: **CONDITIONAL_PASS** (MINOR 결함 1건 수용 — "보유 종목 상태 브리핑이
  향후 매수/매도 의견으로 드리프트될 수 있는 표현" 중립화).
- **Step7 은 구현 단계가 아니라 구조 재정렬 설계 단계**. 코드 / API / UI / Telegram /
  데이터 계약 변경 0건.

공식 PUSH 명칭 (중립형 — 매매 의견 드리프트 차단):
1. **보유 종목 상태 브리핑** (PUSH 1) — 매매 의견이 아니라 상태 브리핑 재료.
2. **신규 ETF 관찰 후보** (PUSH 2) — Step6 universe momentum 결과를 이어받은 관찰 후보.
3. **급락 ETF 주의 신호** (PUSH 3) — 자리만 잡음, 현재 구현 없음.

기존 산출물 3-PUSH 매핑:
- Step3 보유 비중 영향 → PUSH 1 재료
- Step5B holdings momentum → PUSH 1 재료
- Step6 universe momentum → PUSH 2 재료
- 급락 ETF 경고 → PUSH 3 자리만 잡음

Step6 의미 제한 (드리프트 방지):
- ETF 개별 후보 모멘텀 점검 배관 검증 완료. 섹터/테마 발굴 / 매수 추천 체계 / 매수·매도 판단
  체계 / 급락 경고 / ML 검증 — 어느 것도 완료되지 않음.

다음 상태:
- 사용자와 협의 후 후속 구현 Step 1개 선택.
- **후속 구현은 한 번에 하나의 PUSH 만 다룬다** (Step7 §13 분리 원칙).
- 후속 구현 Step 후보: PUSH 1 / PUSH 2 / PUSH 3 / 운영 빈도 문서 정합성 보정 중 택일.

---

## 1.1 직전 상태 (POC2-Step6 최종 PASS)

```text
이전 단계: POC2-Step6 최종 PASS (Telegram 수신 확인, 2026-05-11) — 문서 정합성 보정 완료
```

POC2-Step6 최종 PASS 요약:
- pykrx 1개월 수익률 기반 universe scoring 성공.
- top_candidate 1개가 message_text / Telegram 판단 사유 3번째 bullet 로 도달.
- Telegram 수신 확인됨 (사용자 운영 테스트 — 2026-05-11).

Step6 의 의미 제한:
- **ETF 개별 후보 모멘텀 점검 배관 검증 완료** — 잘 오르는 ETF 1건을 PUSH 까지 도달시키는 데이터 흐름이 정상 작동함을 확인.
- 섹터/테마 발굴 완료 아님 — 발굴 단위 / 시간 측정 기간은 Layer A (ASSUMPTIONS Q4) 로 관리, 운영 첫 달 데이터로 검증.

ASSUMPTIONS 정리 (2026-05-11):
- **Q1**: OPEN 유지 (여러 factor 부착 가능 구조).
- **Q4**: OPEN 유지 (잘 올라가는 섹터/ETF 발굴 단위 — Layer A 항목 2개 추가).
- **Q5**: BACKLOG 이관 (AI 토론 점수체계 검증 — docs/backlog/BACKLOG.md "AI 토론 점수체계 검증" 항목).
- **활성 질문**: Q1 / Q4 2개 (3개 채울 필요 없음).

BACKLOG 정리 (2026-05-11):
- AI 토론 점수체계 검증 (Q5 이관) + 와이프 UI 이해도 검증 항목 신규.
- OPEN 6개 항목을 Layer A / B / C 3단계로 분류.
- Layer A = ASSUMPTIONS Q4 활성 관리 (발굴 단위 세부 / 시간 측정 기간).
- Layer B = BACKLOG + 향후 코드 주석 대상 (무릎머리어깨 / 급락 임계값 / 보유-외부 가중치).
- Layer C = ML 단계 보류 (RS / 거래량 / 정배열 등 복합 지표).

Step6 검증 통과 commit chain:
- 6810e697 feat(poc2-step6): minimal universe momentum scoring (pykrx 1m return)
- 2a225473 fix(poc2-step6): remove new API + new draft_payload key per Codex REJECTED
- 8bd76072 chore(poc2-step6): address Codex VERIFIED_WITH_NOTES — type + docstring touch-ups
- aa1253e1 docs(poc2-step6): mark VERIFIED + add handoff document for next session
- 9518f749 docs: integrate strategy definition decisions into anchors
- 93025d18 chore(deps): pin setuptools<81 for pykrx pkg_resources compatibility

검증자(Codex) 라운드 흐름:
1차 REJECTED (신규 GET endpoint + 신규 draft_payload 키 + stale __init__ docstring)
→ Fix 라운드로 3건 모두 수용 수정
→ VERIFIED_WITH_NOTES (FactorSignal.scope 타입 + 테스트 docstring stale 표기 + 라인 수 수치 차이)
→ NOTES 대응 commit (8bd76072) 으로 타입/docstring 정정
→ 최종 VERIFIED_WITH_NOTES (남은 NOTES 2건: pykrx timeout MEDIUM + 배포 dependency 주의 — 사유 1줄 명시 후 수정 불필요 판정).

Step6 Fix 라운드 요약 (본 라운드, 검증자 1차 REJECTED 대응):
검증자(Codex) 1차 REJECTED 항목 3건 — A-3 (__init__.py stale docstring) / A-4 (신규 API
추가) / A-4 (신규 draft_payload 키 추가) — 모두 수용 + 수정.

핵심 변경:
- **app/momentum/__init__.py docstring 정정**: Step5C 시점 표기 ("universe 결과는 어디에도
  실리지 않는다", "draft_payload 6번째 키까지") 를 Step6 현재 구조로 갱신.
  universe 결과는 factor_signals 안의 scope="universe" signal 1건으로만 표현된다는
  점 명시. draft_payload 키 추가 없음 명시.
- **GET /universe/momentum/latest endpoint 제거**: 신규 API 추가 금지 가드 준수.
  POST /universe/momentum/refresh 응답에 summary_reason_text / top_candidate 필드를
  추가하여 UI 가 응답 1번으로 상태 패널 표시 가능.
- **draft_payload.external_universe_check 키 제거**: BACKLOG `factor_signals 외 메타 키
  추가 금지` 가드 준수. 사용자(설계자) 결정 — universe momentum 결과는 기존 factor_signals
  5번째 키 안의 scope="universe" signal 1건으로 표현.
  · factor_id="universe_one_month_return", scope="universe"
  · is_available + reason_text / fallback_text + value(%) + input_basis(asof, basis_date,
    scored, total, refresh_status) + computed_at
- **draft_message.py 의 _external_universe_bullet 재작성**: factor_signals 의 universe
  scope signal 에서 reason_text / fallback_text 를 그대로 bullet 본문으로 사용 (label
  은 signal.factor_name).
- **app/message_universe_bullet.py 단순화**: 외부 bullet 형식 문자열 만들기 책임만.
  draft.py 의 _build_universe_factor_signal 이 본 모듈의 build_universe_signal_texts 를
  호출해서 reason_text / fallback_text 두 문자열을 만든다.
- **UI**: UniverseRefreshPanel 의 mount 시 GET 호출 제거. POST refresh 응답 → frontend
  state 로 표시. 페이지 reload 시 state 비워짐 → 안내 문구만 표시. (사용성 trade-off
  명시 — 페이지 reload 시 갱신 1회 더 필요.)
- **JudgmentReasonSection**: pickExternalUniverseBullet 을 factor_signals scope==universe
  에서 추출하도록 재작성. draft_payload.external_universe_check 참조 제거.

draft_payload 키 신설 0건 (Step6 Fix 후):
- 1) title, 2) asof, 3) note, 4) recommendations, 5) factor_signals, 6) momentum_result
- universe 결과는 factor_signals 안의 scope="universe" signal 1건으로 표현 (키 추가 0).

검증:
- pytest 119 → **135 passed** (Step6 회귀 16개 추가 — GET endpoint 테스트 1건은 removed
  검증 1건으로 통합).
- black --check / flake8 / TypeScript build / Next.js lint 모두 PASS.
- KS-10 임계 (실측): 백엔드 max 569 / 프론트 max 515 / 테스트 max 924 — 트리거 0 + 근접 0.

직전 라운드 (Step6 1차) 요약:
"잘 달리는 말 찾기" 의 첫 실제 계산 단계. manual universe seed 후보군에 pykrx 기반
1개월 기간 수익률 1개를 적용해 상위 1개를 UI / Telegram [판단 사유] 1줄에 반영.

핵심 변경:
- 점검값: **pykrx 기반 1개월 수익률** (one_month_return_pct = (latest/base - 1)*100).
  복합 점수체계 / MA / RSI / 보너스 / Top N / BUY·SELL 일체 미도입.
- pykrx 호출은 **app/price_history_pykrx.py 1개 모듈에만**. fetch_one_month_basis 함수.
- bounded sync refresh: MAX_UNIVERSE_ITEMS_PER_REFRESH=20 / per_ticker_delay=0.5s /
  budget=30s. seed >20 hard fail. candidate 단위 실패 격리.
- POST /universe/momentum/refresh : status (ok / partial / failed) + scored/total 응답.
- GET /universe/momentum/latest : UI 상태 패널용 latest artifact 조회 (refresh 안 된
  상태는 status="absent").
- universe_momentum_latest.json 확장: refresh_status / data_source="pykrx" /
  score_basis="one_month_return_pct" / lookback_days=30 / fetch_window_days=45 /
  top_candidate (rank=1).
- candidate scored: score_value(%) / score_unit="%" / ranking_basis / price_history_basis
  (base_date/base_close/latest_date/latest_close).
- candidate unscored: exclusion_reason 만 기록. rank 키 미생성.
- GenerateDraft → universe_momentum_latest.json 의 top_candidate 를 draft_payload
  의 7번째 키 external_universe_check 로 병합. **pykrx 직접 호출 0건** (AC-20).
- message_text [판단 사유] 3번째 bullet 추가 — "외부 후보 점검: pykrx 1개월 수익률
  기준 {name} 이 가장 높습니다({value}%, 기준일 {date}, 계산 가능 {scored}/{total}개).
  이 값은 매수 추천이 아닙니다."
- 실패 시 bullet: "외부 후보 점검: pykrx 가격 데이터 부족으로 1개월 점검값을 계산하지
  못했습니다(기준일 {basis_date})."
- 기준일 우선순위: top_candidate.price_history_basis.latest_date → universe.asof →
  "기준일 확인 불가".
- [판단 사유] 헤더 1번 유지 (factor → 모멘텀 → 외부 후보 3 bullets).
- UI: HoldingsClient 아래 별도 UniverseRefreshPanel — 외부 후보 점검 갱신 버튼 +
  상태 패널 (마지막 asof / refresh_status / 기준일 / 계산 가능/전체 / top_candidate
  1건 / 실패 사유). 후보 전체 목록 미노출.
- 버튼 정책: 요청 중 disabled. Telegram / Approve / GenerateDraft 자동 실행 금지.

신규 / 수정 파일:
신규:
- app/price_history_pykrx.py (138라인) — pykrx 단일 호출 모듈
- app/universe_refresh.py (258라인) — bounded sync refresh service
- app/api_universe.py (151라인) — POST refresh + GET latest 라우터 분리
- app/message_universe_bullet.py (90라인) — 외부 후보 점검 bullet 빌더
- frontend/app/components/UniverseRefreshPanel.tsx (210라인) — UI refresh 버튼 + 상태 패널
- tests/test_universe_momentum_step6.py (391라인) — 17개 회귀 테스트

수정:
- app/momentum/universe_mode.py 147→314 (build_universe_momentum_result_scored 추가)
- app/momentum/__init__.py (re-export 추가)
- app/api.py 557→497 (universe endpoint → api_universe 로 분리, 라우터 include 만)
- app/draft.py 160→221 (external_universe_check 로딩 함수 추가)
- app/draft_message.py 525→536 (3번째 bullet 헤더 통합 — 본체는 message_universe_bullet)
- frontend/lib/api.ts 290→380 (universe refresh / latest 엔드포인트 클라이언트)
- frontend/app/components/MainPanel.tsx 65→69 (UniverseRefreshPanel embed)
- frontend/app/components/JudgmentReasonSection.tsx 108→173 (3번째 bullet picker)
- requirements.txt (pykrx>=1.0.51 추가)
- tests/conftest.py 86→118 (pykrx fetcher stub + universe path patch)
- tests/test_universe_seed.py (Step6 동작 반영 — external_universe_check 키 검증)

KS-10 임계 상태 (실측):
- 백엔드: max draft_message.py 536 / api.py 497 — 트리거 4 (650) 미달, 근접 (>=600) 0건 ✓
- 프론트: max EnrichedHoldingsSection.tsx 515 — 트리거 3 (900) 미달, 근접 (>=850) 0건 ✓
- 테스트: max test_holdings_message_text.py 924 — 트리거 1 (1500) 미달, 근접 (>=1450) 0건 ✓
- **모든 트리거 0건 + 모든 근접 0건 유지** ✓ (Step5D-2 Final 이후 회귀 없음)

검증:
- pytest 119 → 136 passed (1.17s) — Step6 회귀 17개 추가
- black --check / flake8 / TypeScript build / Next.js lint 모두 PASS
- pykrx 의존성 추가 (requirements.txt) — pykrx>=1.0.51

Q5 첫 실전 검증 기록 (ASSUMPTIONS.md Q5 보강):
- 채택: pykrx 1개월 기간 수익률 (단일 가격 기반 변수)
- 기각/보류: 수동 recent_return_pct (보수적) / 당일 등락률 (노이즈) / manual_score (근거 약함)
- Q5 상태: OPEN 유지 — 운영 사이클 1회 후 1차 검토

직전 상태 (Step5D-2 Final Round):

Step5D-2 Final Round 요약 (본 라운드):
직전 라운드의 §4.3 "관찰만" 대상이었던 HoldingsClient.tsx (906라인 = 트리거 3 충족) 와 draft_message.py (600라인 = 트리거 4 근접) 까지 모두 해소. 동시에 RunPanel ↔ EvidenceDetails 양방향 import 정돈.
- frontend/lib/holdings_view.ts (186라인) 신규 — RunPanel ↔ EvidenceDetails 가 공유하던 helpers/types 단일 출처. JSX 미포함 (.ts).
  · DEFAULT_GROUP, fmt 5종 (Money/SignedMoney/Pct/SignedPct/pnlClass), NormRec/Summary/AccountSummary 타입, normalizeRec/isPriced/isCalcAvailable/rowKey/computeSummaryFor.
- frontend/app/components/RunPanel.tsx 606 → 444라인. helpers/types 본문 제거 + lib import 로 전환. OverallSummaryCard 만 잔존 (JSX 컴포넌트라 lib 이동 부적합).
- frontend/app/components/EvidenceDetails.tsx 343라인. import 출처를 "./RunPanel" → "@/lib/holdings_view" 로만 변경 (양방향 import 해소). 본문 / 동작 / 렌더 동일.
- frontend/app/components/EnrichedHoldingsSection.tsx (515라인) 신규 — HoldingsClient.tsx 의 시세평가 compact UI 책임 분리.
  · EnrichedSection (default) + 8개 자식 컴포넌트 (OverallSummaryCard / AccountSummaryCards / AccountSummaryRow / CompactHoldingsTable / CompactRow / DetailRowFields / SummaryItem / KV).
  · 로컬 helpers (Summary/AccountSummary/isPriced/isCalcAvailable/computeSummaryFor/groupByAccount/rowKey) — EnrichedHolding 기반이라 holdings_view.ts 의 NormRec 기반 helpers 와 분리.
  · fmt helpers 는 holdings_view.ts 에서 import (중복 제거).
- frontend/app/components/HoldingsClient.tsx 906 → 394라인. EnrichedSection 추출 + fmt helpers 중복 제거. DEFAULT_GROUP 도 lib 사용.
- app/message_helpers.py (124라인) 신규 — draft_message.py 의 leaf-level format / 항목 식별 helpers 분리.
  · _to_finite_float, _format_money/_format_pct/_format_signed_money/_format_signed_pct, _is_priced/_is_calc_available/_is_default_hold/_item_label, DEFAULT_HOLD_REASON.
- app/draft_message.py 600 → 525라인. leaf helpers 본문 제거 + message_helpers 재공개. 공개 API (`is_holdings_draft` / `compute_summary` / `build_message_text` / `DEFAULT_HOLD_REASON` / `MAX_LENGTH_CHARS`) 동일 import 경로 유지.
- pytest 119 passed (1.16s). black --check / flake8 / TypeScript build / Next.js lint 모두 PASS.
- message_text / UI 렌더 / Telegram payload / [판단 사유] 헤더 / 2 bullets 모두 동일 (본문 이동만, 로직 변경 0).

KS-10 트리거 상태 (본 라운드 보고 직전 실측):
- 백엔드: app/api.py 557 / draft_message.py 525 / 그 외 모두 250 이하 — 트리거 4 (650) 미달, **근접(>=600) 0건** ✓
- 프론트: EnrichedHoldingsSection.tsx 515 / RunPanel.tsx 444 / HoldingsClient.tsx 394 / 그 외 모두 350 이하 — 트리거 3 (900) 미달, **근접(>=850) 0건** ✓
- 테스트: test_holdings_message_text.py 924 / 그 외 모두 510 이하 — 트리거 1 (1,500) 미달, **근접(>=1,450) 0건** ✓
- **모든 트리거 0건 + 모든 근접 0건 동시 달성** ✓

직전 라운드 (Step5D-2 1차) 요약:
Step5D-2 지시문 §1.2 가 명시한 트리거 2건만 해소.
- tests/test_holdings_draft_flow.py 1,982 → 244라인. 3개 파일로 도메인별 분리.
- frontend/app/components/RunPanel.tsx 905 → 606라인. EvidenceDetails.tsx (343라인) 추출.

Step5D Cleanup 요약:
검증자 NOTES B-3 누적 지적(단일 파일 책임 누적) 에 대응해 신규 기능 추가 없이 구조만 정돈.
- 백엔드 테스트 파일 분리: tests/test_poc1_loop.py 3,452라인 → 298라인.
  conftest.py / _helpers.py / 4개 신규 테스트 파일 (holdings_draft_flow / factor_signals / momentum_holdings / universe_seed) 로 분산.
  pytest 119 passed 그대로 유지 — 의미/개수/검증 강도 변경 0건.
- 프론트 컴포넌트 분리: RunPanel.tsx 1,055라인 → 905라인.
  JudgmentReasonSection.tsx + MomentumCandidatesSection.tsx 로 표시 책임 일부 추출.
  렌더링 / 문구 / 배치 / 동작 / message_text 모두 동일.
- KS-10 (단일 파일 라인 수 / 책임 누적 임계 초과) 가드 추가: KILL_SWITCHES.md 명문화.
- PROJECT_ORIGIN_INTENT 배움 자산 / ASSUMPTIONS Q3 보강 / Q5 확인 방법 보강.
- BACKLOG CLEANUP CANDIDATES 신규 섹션: holdings_draft_flow 추가 분리, EvidenceDetails 분리, HoldingsClient 분리, draft_message 패키지화, api.py 라우터 분리.

Step5C 요약 (직전 단계):
manual universe seed 파일을 읽어 score 없는 universe mode momentum_result 를 생성하고
state/universe/universe_momentum_latest.json 에 latest 1건 덮어쓰기 artifact 로 저장.
실행 트리거: POST /universe/momentum/refresh 수동 backend API 1곳.
universe 결과는 draft_payload / Run top-level / message_text / UI / Telegram 어디에도 노출 안 함.

Step5C 요약:
manual universe seed (state/universe/etf_universe_latest.json) 를 읽어 universe mode
momentum_result 를 생성하고 state/universe/universe_momentum_latest.json (latest 1건 덮어쓰기)
artifact 로 저장한다. 실행 트리거는 POST /universe/momentum/refresh 수동 backend API 1곳
이며, holdings draft 생성 / Approve / OCI handoff / Telegram / scheduler 어디에서도
자동 호출되지 않는다.
asof 는 YYYY-MM-DD 필수 + 미래 날짜 차단. UNIVERSE_SEED_MAX_AGE_DAYS=30 초과 = stale
(hard fail 아님, summary.source_freshness="stale" + summary_reason_text 에 명시).
universe mode 는 점수 미부여 (score_result.is_scored=false, rank 미생성) — 이번 Step 은
입력 통로 + latest artifact 저장만 검증.
universe 결과는 draft_payload / Run top-level / message_text / UI / Telegram 어디에도
실리지 않는다.
pytest 119 passed (Step5B 107 + Step5C 신규 12).

Step5B 요약 (직전 단계):
placeholder 산식(pnl_rate)으로 Momentum Engine holdings mode 를 1회 실행했다.
결과는 draft_payload.momentum_result (Step5B 한정 명시 승인된 6번째 키) 에 저장되며,
승인 초안 UI 의 [판단 사유] 섹션과 message_text/Telegram 에 1줄 bullet 으로 추가된다.
별도 [모멘텀 점검] 헤더는 만들지 않으며 [판단 사유] 헤더는 1번만 등장한다.
candidates 의 row 매핑은 source_index + ticker + account_group + avg_buy_price 4 요소로
보존되어 동일 ticker 분할매수 row 의 매핑 충돌을 방지한다.

Step5A 요약 (직전 단계):
Momentum Engine 의 최소 입력/출력 계약을 정의했다.
Momentum Engine 은 holdings mode 와 universe mode 가 공유한다.
universe mode 에서 엔진은 후보군을 직접 수집하지 않고, 외부에서 주입된 candidates 를 평가한다.
rank 는 optional 이며 score / ranking_basis 가 없으면 생략 가능하다.

이전 단계 누적:
- Step4: Momentum Engine 방향 정리 (holdings mode / universe mode 두 축, 친구 시스템은 결과물 아닌 과정만 참고)
- Step3: 보유 비중 영향 factor 1개를 draft_payload.factor_signals + 승인 초안 UI + message_text + Telegram/Push 까지 통합
- Step2 전체 종료: holdings 입력/저장, account_group, Naver 시세, 평가 계산, compact UI, message compaction, 승인 초안 preview 분리

ASSUMPTIONS:
- Q3 → A-5 ANSWERED 이동 (Step4 시점 — KS-3 비건설적 핑퐁 패턴 재발 없음)
- Q5 → OPEN 신규 등록 (검증 대상 = 사용자 본인)
- 활성 질문은 Q1 / Q4 / Q5 유지 (3개)

주의:
- Step5B 의 placeholder 산식(pnl_rate) 은 최종 투자 판단 산식이 아니다 — UI/메시지 모두 명시.
- Step5C 는 universe 후보군 입력 통로와 latest artifact 저장만 만든 단계. 잘 달리는 말 후보를 평가한 것이 아니다 — 점수 미부여, rank 미생성.
- 외부 ETF 자동 수집, MA/RSI/수익률 기간 산식, 유니버스 종목 수 / ETF 후보군 자동 결정, ML 모델, 화면 대개편, Telegram Top N, BUY/SELL/리밸런싱, 운영 결과 별도 DB, history 누적은 아직 구현하지 않았다.
- universe mode 결과 저장 위치는 state/universe/universe_momentum_latest.json (latest 1건 덮어쓰기). draft_payload / Run top-level / DB / history 미도입.
- holdings mode 결과 저장 위치는 draft_payload.momentum_result 6번째 키 (Step5B 결정 그대로).
- 운영 결과 기록 / AI 해석 로그 / ML dataset 구조는 Step5C 까지 미도입 — 별도 Step 에서 판단.
- "잘 달리는 말 찾기" 는 holdings factor 가 아니라 universe mode 에서 다룬다 — 단 엔진은 후보군을 직접 수집하지 않는다.
- 와이프는 UI 가독성 검증 대상이며 Q5 의 투자 판단/운영 방식 적합성 검증 대상이 아니다.
- Q1 은 ANSWERED 가 아니라 OPEN 유지. Step3 결과는 1차 긍정 증거에 불과.

직전 종결/설계 문서:
- `docs/handoff/POC2_STEP5A_MOMENTUM_ENGINE_BOUNDARY_AND_MINIMAL_CONTRACT.md` (Step5A 설계서)
- `docs/handoff/POC2_STEP4_MOMENTUM_ENGINE_DIRECTION_AND_Q4_BOUNDARY_DESIGN.md` (Step4 설계서)
- `docs/handoff/POC2_STEP3_CONCLUSION_AND_NEXT_HANDOFF.md` (Step3 종료 선언)
- `docs/handoff/POC2_STEP2_CONCLUSION_AND_STEP3_HANDOFF.md` (Step2 종료 선언)
- `docs/backlog/BACKLOG.md` (Step5 진입 전 정돈 완료 — ACTIVE REVIEW BEFORE STEP5 / CONSOLIDATED DEFERRED / CLOSED)

Step5B / 5C 구현 진입점 (코드):
- `app/momentum/holdings_mode.py` — placeholder 산식 빌더 (pnl_rate, Step5B)
- `app/momentum/universe_mode.py` — universe candidates 변환 + latest artifact 저장 (Step5C)
- `app/momentum/__init__.py` — 패키지 진입점 (holdings_mode + universe_mode export, 추상 클래스 / registry 미도입)
- `app/universe_seed.py` — manual seed loader + asof 검증 + UNIVERSE_SEED_MAX_AGE_DAYS=30 staleness (Step5C)
- `app/draft.py` — _build_holdings_payload 에서 holdings momentum_result 빌드 + draft_payload 6번째 키 부착 (Step5B). universe 와 무관.
- `app/draft_message.py::_render_judgment_lines` — factor + holdings momentum 두 bullet 을 1개의 [판단 사유] 헤더 아래에 합침 (Step5B). universe 는 메시지 미반영.
- `app/api.py` — POST /universe/momentum/refresh 수동 endpoint (Step5C, holdings draft 흐름과 분리)
- `frontend/lib/api.ts` — MomentumResult / MomentumCandidate / ... 타입 (Step5B holdings mode UI 한정. universe 는 UI 미노출)
- `frontend/app/components/RunPanel.tsx::JudgmentReasonSection` — 모멘텀 bullet 1줄 추가, EvidenceDetails 안 MomentumCandidatesSection (Step5B)
- `docs/examples/etf_universe_latest.example.json` — universe seed 예시 (Step5C)

---

## 2. Step2 완료 요약

```text
POC2-Step2는 holdings 입력/저장, account_group, Naver 시세 갱신, 평가 계산, compact table,
Telegram message compaction, 승인 초안 preview 분리까지 완료했다.
사용자 테스트 기준 Telegram 수신까지 확인했다.
```

세부 종결 문서:
- `docs/handoff/POC2_Step2_close.md` — Naver 시세 enrichment
- `docs/handoff/POC2_Step2B_close.md` — Telegram message compaction
- `docs/handoff/POC2_Step2C_close.md` — Holdings UI compaction + account grouping
- `docs/handoff/POC2_Step2D_close.md` — Approval draft preview separation
- `docs/handoff/POC2_STEP2_CONCLUSION_AND_STEP3_HANDOFF.md` — Step2 전체 종료 선언 + Step3 진입 가드

---

## 3. 완료된 Step (이력)

### POC1
- POC1-Step1: 최소 승인 루프 상태 모델 (PENDING_APPROVAL / REJECTED / DELIVERING / FAILED / COMPLETED)
- POC1-Step2: Next.js + TypeScript + App Router UI + FastAPI CORS
- POC1-Step3: 실 OCI handoff (SCP + outbox reconciliation) + Telegram 발송 end-to-end 검증

### POC2
- POC2-Step1: holdings 기반 draft 생성 + JSON SSOT 저장
- POC2-Step1A: raw JSON 표시 제거 + holdings 초안 사람이 읽는 렌더링 + handoff message_text top-level
- POC2-Step2: Naver 1차 시세 enrichment + 평가/손익/시장비중 계산
- POC2-Step2B: Telegram 메시지 요약형 + 길이 제한 방어 (MAX_LENGTH_CHARS=3500)
- POC2-Step2C: Compact UI + account_group + React key 안정성 + polling 펼침 상태 유지
- POC2-Step2D: 승인 초안 preview 분리 (Run.message_text top-level + 단일 소스 보장)
- POC2-Step3: 첫 factor signal 통합 (portfolio_concentration_v1 / "보유 비중 영향")
  · draft_payload.factor_signals 5번째 키 (Step3 한정 명시 승인)
  · portfolio scope 1개 + max_weight_row holding_row scope 0~1개 고정
  · message_text 에 [판단 사유] 1줄 (portfolio reason 또는 fallback)
  · 승인 초안 UI 에 판단 사유 섹션 기본 노출
  · BUY/SELL/리밸런싱/Top N/위험 등급 등 일체 미도입

---

## 4. 다음 단계 주의사항

```text
다음 세션은 Step3 설계에 진입한다.
Step3의 factor 종류, 라벨, 산식, threshold는 이 handoff에서 확정하지 않는다.
Step3 설계서에서 다시 검토한다.
추가 UI polish Step으로 우회하지 않는다.
ASSUMPTIONS Q1과 명시적으로 연결한다.
BUY/SELL/리밸런싱/ML 확장은 금지한다.
```

다음 Step 명칭 (잠정):

```text
POC2-Step3 — First Factor Signal Integration
```

Step3 종료 조건 (POC2_STEP2_CONCLUSION_AND_STEP3_HANDOFF.md §7 참조):
1. factor 1개가 계산된다.
2. factor 결과가 `draft_payload`에 반영된다.
3. factor 결과가 승인 초안 화면에 표시된다.
4. factor 결과가 `message_text`에 반영된다.
5. 승인 후 Telegram 에서 factor 기반 판단 사유를 확인한다.
6. 기존 승인/OCI/Telegram 경로가 유지된다.
7. BUY / SELL / 리밸런싱 / ML 확장은 발생하지 않는다.

---

## 5. 금지사항 (Step3 진입 가드)

```text
- Step3 factor 종류 선확정 금지
- WATCH/REVIEW 등 라벨 선확정 금지
- 다음다음 단계 로드맵 선설계 금지
- UI polish로 Step3 진입 지연 금지
- 친구 프로젝트 통째 복제 금지
```

추가 (Step2 까지 누적된 절대 금지 — Step3 도 동일 적용):
- pykrx / yfinance fallback (POC2-Step2A 별도 STEP 에서만 검토)
- BeautifulSoup / desktop scraping / polling stream / WebSocket / SSE
- DB / MongoDB / SQLite / PostgreSQL / Redis
- 새 UI 프레임워크 (shadcn/MUI/Tailwind) / 전역 상태 관리 라이브러리
- snapshot / history / 전일 대비 변화 감지
- 메시지 split 발송
- 계좌번호/증권사/세금/오픈뱅킹 API 연동
- "실시간" 단어 사용
- 신규 의존성 / 파일 삭제 / DB 스키마 변경 — 사용자 명시 승인 필수

---

## 6. 확정 기술 스택 (Step2 종료 시점 스냅샷)

Backend:
- FastAPI
- JSON 파일 기반 SSOT
- httpx + Naver 금융 JSON endpoint
- OCI handoff (SCP + outbox)
- existing daily_ops.sh 소비
- Telegram 기존 발송 경로
- Run.message_text top-level optional metadata

Frontend:
- Next.js 15 + TypeScript + App Router
- FastAPI 분리 + CORS
- HTML datalist (account_group 입력)
- preview block + evidence-details (Step 2D)

Storage:
- holdings: state/holdings/holdings_latest.json (account_group 키 포함)
- market cache: state/market_cache/market_latest.json
- runs: state/runs/{run_id}.json (message_text top-level 키 포함, 과거 run 은 누락 허용)

---

## 7. 현재 설계 원칙 (Step2 종료 시점 누적)

- 한 Step 은 하나의 목표만 가진다.
- 기능 확장보다 운영 장애 해결을 우선한다.
- Telegram 은 전체 보고서가 아니라 요약 알림이다. 전체 상세는 UI 에서 본다.
- 외부 조회는 명시적 갱신 액션(POST /market/refresh)에서만 수행한다.
- 화면 조회, polling, draft 조회에서 외부 fetch 금지.
- 누락 데이터는 0/null/undefined/NaN 으로 노출하지 않는다. 키 자체 생략 + 별도 플래그.
- "시세 확인" ≠ "평가 계산 가능". 평가 집계는 평가 계산 가능 종목만 사용.
- account_group 은 표시/그룹용 라벨이며 계좌번호/세금/증권사 판정값이 아니다.
- 백엔드 정규화가 최종 방어선. 프론트엔드 정규화는 보조.
- React key / 펼침 상태 식별자는 source_index + ticker + account_group + avg_buy_price 조합.
- 승인 초안 화면의 message_text 는 백엔드가 generate 시점에 빌드한 원본을 그대로 렌더 — 프론트엔드는 조립/파싱하지 않는다.
- preview / OCI handoff / Telegram 발송은 모두 동일한 Run.message_text 단일 소스를 사용한다.
- raw JSON 은 어떤 분기에서도 기본 화면에 노출되지 않는다 (필요 시 기본 접힘 details 안으로만).

---

## 8. 다음 세션 첫 액션

다음 세션은 아래 순서로 진행한다.

1. CLAUDE.md 읽기
2. docs/PROJECT_ORIGIN_INTENT.md 읽기
3. docs/agent/INSTRUCTION_RULES.md 읽기 (선택)
4. docs/KILL_SWITCHES.md 읽기
5. docs/ASSUMPTIONS.md 읽기 (Q1 OPEN 유지 / Q4 OPEN / Q5 OPEN 명시 연결, A-4 / A-5 ANSWERED 확인)
6. docs/MASTER_PLAN.md 읽기
7. docs/handoff/STATE_LATEST.md 읽기 (본 문서)
8. docs/handoff/POC2_STEP5A_MOMENTUM_ENGINE_BOUNDARY_AND_MINIMAL_CONTRACT.md 읽기 (Step5A 설계서 — 다음 STEP 의 입력/출력 계약)
9. docs/handoff/POC2_STEP4_MOMENTUM_ENGINE_DIRECTION_AND_Q4_BOUNDARY_DESIGN.md 읽기 (Step4 설계서 — Momentum Engine 방향 가드)
10. docs/handoff/POC2_STEP3_CONCLUSION_AND_NEXT_HANDOFF.md 읽기 (Step3 종료 선언, 필요 시)
11. docs/handoff/POC2_STEP2_CONCLUSION_AND_STEP3_HANDOFF.md 읽기 (Step2 종료 선언, 필요 시)
12. docs/backlog/BACKLOG.md 읽기 (ACTIVE REVIEW BEFORE STEP5 5건 + CONSOLIDATED DEFERRED + CLOSED)
13. "기반 문서 확인 완료" 응답 후 사용자/설계자 의 Step5B (Momentum result 저장 위치 결정) 설계 지시 대기

다음 세션이 절대 하지 않을 것:
- universe mode 에 실제 모멘텀 산식을 추가 (Step5C 다음 별도 STEP — 산식·데이터 소스·UI 노출은 별도 결정)
- universe 결과를 draft_payload / Run top-level / message_text / Telegram / UI 어디에도 자동 노출 (Step5C 가드)
- POST /universe/momentum/refresh 를 GenerateDraft / Approve / scheduler / cron 에서 자동 호출
- 외부 ETF 자동 수집 (Naver / pykrx / yfinance / KIS) — universe seed 는 사용자가 수기로 작성
- DB / history 저장소 / AI 해석 로그 / ML dataset 도입
- ML 바로 구현 / BUY·SELL·리밸런싱 구현
- 친구 UI 복제 / 친구 산식 통째 이식
- holdings mode 와 universe mode 동시 산식 도입 강제
- Q1 / Q5 를 ANSWERED 로 임의 이동
- "와이프 = 투자 판단/운영 방식 적합성 검증 대상" 으로 혼동 (와이프는 UI 가독성 전용)
- rank 를 Telegram Top N 또는 매수 우선순위로 해석
- draft_payload 7번째 키 신설 (Step5B 6번째 키까지가 한정 승인)
