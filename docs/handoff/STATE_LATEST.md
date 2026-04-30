# STATE_LATEST.md

최종 업데이트: 2026-04-29

## 1. 프로젝트 현재 상태

현재 프로젝트는 POC2 단계다.

POC1에서는 승인 루프와 실제 OCI 전달을 검증했다.
POC2에서는 holdings 기반 입력, Naver 시세 enrichment, Telegram 메시지 가독성, UI 압축 + 계좌 구분을 진행 중이다.

현재 위치:
- POC2-Step2C 완료 (Codex CONDITIONAL_PASS 후 보고 정확성 수정으로 완료 처리)
- 다음 작업: 사용자 결정 대기

## 2. 완료된 Step

### POC1-Step1
최소 승인 루프 상태 모델 구현.

상태:
- PENDING_APPROVAL
- REJECTED
- DELIVERING
- FAILED
- COMPLETED

### POC1-Step2
Next.js + TypeScript + App Router 기반 UI 구현.
FastAPI와 CORS 연동 완료.
Streamlit은 legacy로 이동.

### POC1-Step3
Approve된 run이 실제 OCI로 handoff되고, 기존 daily_ops.sh 경로에서 소비되며 Telegram 발송까지 end-to-end 검증 완료.

### POC2-Step1
샘플 초안 입력에서 holdings 기반 draft 생성으로 전환.
holdings는 JSON SSOT로 저장.

### POC2-Step1A
raw JSON 표시 제거.
holdings 초안을 UI와 Telegram에서 사람이 읽는 목록으로 렌더링.
message_text를 handoff top-level 필드로 추가.

### POC2-Step2
Naver 금융 기반 시장데이터 enrichment 구현.
명시적 [시세 갱신] 액션에서만 Naver 조회.
market_cache는 메모리 + JSON 파일.
현재가, 평가금액, 평가손익, 수익률, 시장비중 계산.

### POC2-Step2B
Telegram message 요약형 전환 + 길이 제한 방어.
보유 종목 18+ 에서도 message_text 가 안전 한도(MAX_LENGTH_CHARS=3500) 이하로 생성.
"시세 확인" ≠ "평가 계산 가능" 분리. 평가 집계는 calc_available 기준만.

### POC2-Step2C
Holdings UI 압축 + 계좌 구분 도입.
- holdings 스키마에 account_group(표시/그룹용 라벨) 필드 추가.
- 백엔드 단일 helper(normalize_account_group) 로 trim / 30자 제한 / 기본 추천값 대소문자 정규화 / "일반" 기본값 처리.
- 중복 정책 완화: (ticker, account_group, avg_buy_price) 삼중조합 중복만 차단 (분할매수 허용).
- 시세평가 섹션을 전체 요약 + 계좌별 요약 + compact table + 상세 펼침 구조로 재편.
- React key 안정성: source_index + ticker + account_group + avg_buy_price 조합.
- polling 시 동일 run 의 동일 항목 펼침 상태 유지.
- 과거 holdings / draft_payload 의 account_group 누락은 백엔드 로드 단계 또는 프론트 normalizeRec 단계에서 "일반" / 행 인덱스 fallback 으로 안전 처리.
- pytest 76 passed (기존 63 + Step2C 신규 13).

## 3. 현재 발견된 운영 이슈

특이사항 없음. POC2-Step2B 의 메시지 길이 초과 이슈는 해결됨.
운영 E2E 자연 검증(사용자 디바이스에서 18+ 종목 [시세 갱신] → 초안 → 승인 → Telegram 수신) 은 다음 사용자 실행 시점 자연 발생 검증 대기.

## 4. 다음 Step 후보

### 후보 A — 운영 E2E 자연 검증 follow-up
사용자 디바이스에서 [시세 갱신] → 초안 → 승인 → 18+ 종목 새 형식 Telegram 수신 결과 사용자 보고 받기.
검증 OK 시 STATE_LATEST.md 업데이트. 검증 NG 시 즉시 fix 라운드.

### 후보 B — POC2-Step2A — pykrx EOD fallback 추가
Naver 가 실제로 차단/실패할 때만 검토.
BACKLOG 트리거 충족 여부 사용자 확인 필요.
사전 결정 필요: pykrx 의존성 추가에 대한 사용자 승인, 캐시/저장 위치, TTL, 1차→2차 fallback 우선순위.

### 후보 C — ML 연결 / factor 추천
Phase 1 격리 모듈(`backup/backtest/ml/predictive_risk_classifier.py`) 활용.
ASSUMPTIONS Q1 (factor 추가 10줄 이내) 검증 시점.

### 후보 D — 프론트 compact UI 공용 모듈 추출 (BACKLOG)
HoldingsClient.tsx 와 RunPanel.tsx 의 요약 계산/테이블 렌더링 공용 모듈화.
트리거 발생(동시 변경 2회 이상 / 한 파일 ~600라인 초과 / 두 곳 동일 버그) 시 진입.

## 5. 확정 기술 스택

Backend:
- FastAPI
- JSON 파일 기반 SSOT
- httpx
- Naver 금융 JSON endpoint
- OCI handoff
- existing daily_ops.sh 소비
- Telegram 기존 발송 경로

Frontend:
- Next.js
- TypeScript
- App Router
- FastAPI 분리 + CORS
- HTML datalist (account_group 입력 — Step 2C 추가)

Storage:
- holdings: state/holdings/holdings_latest.json (Step 2C 부터 account_group 키 포함)
- market cache: state/market_cache/market_latest.json
- runs: 기존 run store

금지:
- MongoDB
- SQLite/PostgreSQL
- yfinance
- pykrx, 단 Step2A에서 별도 승인 시 가능
- Streamlit 현행 UI 복귀
- ML/factor 조기 도입
- 새 UI 프레임워크 / 전역 상태 관리 라이브러리
- WebSocket / SSE / message split

## 6. 현재 설계 원칙

- 한 Step은 하나의 목표만 가진다.
- 기능 확장보다 운영 장애 해결을 우선한다.
- Telegram은 전체 보고서가 아니라 요약 알림이다. 전체 상세는 UI 에서 본다.
- 외부 조회는 명시적 갱신 액션(POST /market/refresh)에서만 수행한다.
- 화면 조회, polling, draft 조회에서 외부 fetch 금지.
- 누락 데이터는 0/null/undefined/NaN 으로 노출하지 않는다. 키 자체 생략 + 별도 플래그.
- "시세 확인" ≠ "평가 계산 가능". 평가 집계는 평가 계산 가능 종목만 사용.
- account_group 은 표시/그룹용 라벨이며 계좌번호/세금/증권사 판정값이 아니다.
- 백엔드 정규화가 최종 방어선. 프론트엔드 정규화는 보조.
- React key / 펼침 상태 식별자는 source_index + ticker + account_group + avg_buy_price 조합.

## 7. 다음 세션 첫 액션

다음 세션은 아래 순서로 진행한다.

1. CLAUDE.md 읽기
2. docs/PROJECT_ORIGIN_INTENT.md 읽기
3. docs/agent/INSTRUCTION_RULES.md 읽기 (선택)
4. docs/KILL_SWITCHES.md 읽기
5. docs/ASSUMPTIONS.md 읽기
6. docs/MASTER_PLAN.md 읽기
7. docs/handoff/STATE_LATEST.md 읽기 (본 문서)
8. docs/handoff/POC2_Step2C_close.md 읽기 (직전 종결 문서)
9. docs/backlog/BACKLOG.md 읽기
10. "기반 문서 확인 완료" 응답 후 사용자 결정 대기
