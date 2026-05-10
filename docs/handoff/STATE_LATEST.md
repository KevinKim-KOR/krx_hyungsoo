# STATE_LATEST.md

최종 업데이트: 2026-05-10

---

## 1. 현재 상태

```text
현재 단계: POC2-Step5D-2 Final Round 완료 (검증자 VERIFIED, 2026-05-10) — 모든 KS-10 트리거 + 근접(50라인 이내) 0건
다음 단계: 사용자/설계자 결정 대기 — universe 모멘텀 산식 기능 STEP 진입
```

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
