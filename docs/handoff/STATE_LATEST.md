# STATE_LATEST.md

최종 업데이트: 2026-04-28

## 1. 프로젝트 현재 상태

현재 프로젝트는 POC2 단계다.

POC1에서는 승인 루프와 실제 OCI 전달을 검증했다.
POC2에서는 holdings 기반 입력, Naver 시세 enrichment, Telegram 메시지 가독성 개선을 진행 중이다.

현재 위치:
- POC2-Step2 완료
- 다음 작업: POC2-Step2B Telegram Message Compaction

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
pykrx는 이번 Step에서 제외하고 POC2-Step2A 후보로 BACKLOG.

## 3. 현재 발견된 운영 이슈

보유종목이 많을 경우 Telegram 메시지가 너무 길어져 전송 실패 발생.

실제 오류:
Bad Request: message is too long

설계 판단:
- POC2-Step2 자체는 PASS
- 다음은 기능 확장보다 Telegram 메시지 요약화가 우선
- snapshot 비교는 하지 않음
- 기본 HOLD 종목 전체를 Telegram에 모두 보내지 않음

## 4. 다음 Step

다음 Step:
POC2-Step2B — Telegram Message Compaction

목표:
보유종목이 많아도 Telegram 메시지가 길이 제한을 넘지 않도록 요약형 메시지로 전환한다.

범위:
- Telegram message_text 요약화
- 기본 HOLD 종목 상세 전체 나열 금지
- 주목 종목 Top N만 표시
- 메시지 길이 안전 한도 적용
- raw JSON 금지
- 기존 OCI/Telegram 경로 유지

비범위:
- UI 압축
- 계좌 구분
- snapshot/history
- 전일 대비 변화 감지
- ML/factor
- pykrx fallback
- 매수/매도 추천

## 5. 다음 Step 이후 후보

### POC2-Step2C
Holdings UI 압축 + 계좌 구분 추가.

내용:
- 계좌 구분: ISA, 일반, 연금, 오픈뱅킹, 기타
- 계좌별 요약
- 종목 카드 → compact table 중심
- 상세는 접힘/확장

### POC2-Step2A
pykrx EOD fallback 추가.

진입 조건:
- Naver 불안정
- 특정 ETF 코드 조회 실패 반복
- EOD fallback 필요
- 사용자 pykrx 설치 승인

## 6. 확정 기술 스택

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

Storage:
- holdings: state/holdings/holdings_latest.json
- market cache: state/market_cache/market_latest.json
- runs: 기존 run store

금지:
- MongoDB
- SQLite/PostgreSQL
- yfinance
- pykrx, 단 Step2A에서 별도 승인 시 가능
- Streamlit 현행 UI 복귀
- ML/factor 조기 도입

## 7. 현재 설계 원칙

- 한 Step은 하나의 목표만 가진다.
- 기능 확장보다 운영 장애 해결을 우선한다.
- Telegram은 전체 보고서가 아니라 요약 알림이다.
- 전체 상세는 UI에서 본다.
- 기본 HOLD 종목 전체를 메시지에 나열하지 않는다.
- "변화 없음"은 snapshot 비교가 아니라 action=HOLD 기본 종목을 상세 메시지에서 제외한다는 의미다.
- 외부 조회는 명시적 갱신 액션에서만 수행한다.
- 화면 조회, polling, draft 조회에서 외부 fetch 금지.

## 8. 다음 세션 첫 액션

다음 세션은 아래 순서로 진행한다.

1. docs/PROJECT_ORIGIN_INTENT.md 읽기
2. docs/KILL_SWITCHES.md 읽기
3. docs/ASSUMPTIONS.md 읽기
4. docs/MASTER_PLAN.md 읽기
5. docs/STATE_LATEST.md 읽기
6. docs/agent/INSTRUCTION_RULES.md 읽기
7. POC2-Step2B 레드팀 검토용 지시문 작성
8. 레드팀 통과 후 개발자용 최종 지시문 작성