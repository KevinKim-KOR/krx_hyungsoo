# STATE_LATEST.md

최종 업데이트: 2026-04-30

---

## 1. 현재 상태

```text
현재 단계: POC2-Step5A 설계 완료 (계약 문서화 단계, 구현 단계 아님)
다음 단계: Step5B — Momentum result 저장 위치 결정 설계 지시문 작성
```

Step5A 요약:
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
- Step5A 는 구현 단계가 아니다 — 계약 문서화 단계.
- 구체 점수 산식, MA 기간, RSI 기준, 수익률 기간, 유니버스 종목 수, ETF 후보군, 데이터 소스, ML 모델, 화면 디자인, Telegram Top N, BUY/SELL/리밸런싱, 운영 결과 저장소는 확정하지 않았다.
- Momentum result 저장 위치(draft_payload / factor_signals / 별도 artifact / Run top-level / 외부 저장소) 는 Step5B 에서 판단.
- 운영 결과 기록 / AI·ML 분석 넘김은 Step5C 또는 별도 Step 에서 판단.
- "잘 달리는 말 찾기" 는 holdings factor 가 아니라 universe mode 에서 다룬다 — 단 엔진은 후보군을 직접 수집하지 않는다.
- 와이프는 UI 가독성 검증 대상이며 Q5 의 투자 판단/운영 방식 적합성 검증 대상이 아니다.
- Q1 은 ANSWERED 가 아니라 OPEN 유지. Step3 결과는 1차 긍정 증거에 불과.

직전 종결/설계 문서:
- `docs/handoff/POC2_STEP5A_MOMENTUM_ENGINE_BOUNDARY_AND_MINIMAL_CONTRACT.md` (Step5A 설계서, 본 문서 직전)
- `docs/handoff/POC2_STEP4_MOMENTUM_ENGINE_DIRECTION_AND_Q4_BOUNDARY_DESIGN.md` (Step4 설계서)
- `docs/handoff/POC2_STEP3_CONCLUSION_AND_NEXT_HANDOFF.md` (Step3 종료 선언)
- `docs/handoff/POC2_STEP2_CONCLUSION_AND_STEP3_HANDOFF.md` (Step2 종료 선언)
- `docs/backlog/BACKLOG.md` (Step5 진입 전 정돈 완료 — ACTIVE REVIEW BEFORE STEP5 / CONSOLIDATED DEFERRED / CLOSED)

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
- Step5B 에서 Momentum Engine 코드 구현 (저장 위치 결정만)
- Step5B/C 에서 점수 산식 / 유니버스 / 데이터 소스 / ML 모델 / UI 디자인 결정
- Step5B 에서 draft_payload 6번째 키 신설 (factor_signals 안 또는 별도 artifact 또는 Run top-level 중 1개 선택)
- Step5C 가 결정되기 전에 새 저장소 / 새 DB / 새 로그 체계 / 새 분석 파이프라인 도입
- Momentum Engine 이 universe 후보군을 직접 수집하도록 구현 (외부 주입만)
- ML 바로 구현 / sector discovery 바로 구현 / BUY·SELL·리밸런싱 구현
- 친구 UI 복제 / 친구 산식 통째 이식
- holdings mode 와 universe mode 동시 구현 강제
- Q1 / Q5 를 ANSWERED 로 임의 이동
- "와이프 = 투자 판단/운영 방식 적합성 검증 대상" 으로 혼동 (와이프는 UI 가독성 전용)
- rank 를 Telegram Top N 또는 매수 우선순위로 해석
