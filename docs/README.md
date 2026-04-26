# Phase 2 POC — 승인 루프

AI와 함께 투자 방향을 찾기 위한 최소 승인 루프 구현.
POC1(승인 루프) → POC1 Step 3(실 OCI 전달 + Telegram) → POC2 Step 1(holdings 진입점 전환) → POC2 Step 1A(raw JSON 표시 제거 + 사람이 읽는 렌더링) 까지 완료.

## 범위

- **운영 진입점**: 사용자가 보유 종목(holdings)을 입력 → 보유 현황 기반 초안 생성
- 초안 생성 → PENDING_APPROVAL
- 사용자 Approve → DELIVERING → 실제 OCI 전달 + Telegram 발송 → COMPLETED 또는 FAILED
- 사용자 Reject → REJECTED
- 실패/거절된 run 은 재사용 금지, 새 run_id 로만 재시도
- 입력 검증 실패는 422 로 차단되며 FAILED run 이 만들어지지 않음

이번 단계는 **ML 추천 단계가 아닙니다.** holdings 를 그대로 표시하는 보유 현황 기반 초안만 생성합니다.

## 실행

두 개의 터미널을 사용합니다. **UI 진입점은 `frontend/` (Next.js)** 입니다.
`legacy/ui_app.py` (Streamlit) 는 참조용 보존이며 실행 경로 아님.

운영 편의를 위해 루트에 `start.bat` / `stop.bat` 가 준비되어 있습니다.

### 빠른 실행 (권장)

```bash
start.bat   # 백엔드(8000) + 프론트(3000) + 브라우저 자동 열기
stop.bat    # 두 포트 정확 매칭 종료
```

### 수동 실행

#### 1) FastAPI 백엔드

```bash
# 최초 1회
.venv/Scripts/pip install -r requirements.txt

# 기동 (.env 의 OCI_SSH_TARGET 등은 자동 로드됨)
.venv/Scripts/python -m uvicorn app.api:app --host 127.0.0.1 --port 8000 --reload
```

#### 2) Next.js 프론트엔드

```bash
# 최초 1회
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_BASE 확인

# 기동 (dev)
npm run dev   # http://localhost:3000
```

## 사용 흐름 (운영)

1. 메인 화면 첫 섹션 **"1. 보유 종목 입력"** 에서 종목코드 / 수량 / 매입단가를 입력 (종목명은 선택)
2. **보유 종목 저장** → JSON 파일(`state/holdings/holdings_latest.json`) 에 저장
3. **저장된 보유 종목으로 초안 만들기** → PENDING_APPROVAL run 생성
4. **승인 (Approve)** → DELIVERING 진입 → 백엔드가 OCI 측 inbox 로 SCP 전송
5. OCI 측 `daily_ops.sh` (cron 09:05 KST 또는 수동 1회 실행) 가 inbox 를 소비 → Telegram 발송 → outbox 에 결과 기록
6. 로컬 UI 가 12초 간격 polling 또는 수동 새로고침으로 outbox 결과 확인 → COMPLETED/FAILED 표시

샘플 입력은 메인 화면 가장 아래 **"개발/테스트용 — 운영 입력 아님"** 접힘 섹션에서 사용. 운영 흐름과 분리.

## 구조

### 백엔드 (`app/`)
- `models.py` — 데이터 계약 (run_id / asof / status / draft_payload)
- `state.py` — 상태 전이 규칙
- `store.py` — JSON 파일 저장소 (`state/runs/*.json`, `state/poc1_handoff/*`). handoff artifact 5필드 (run_id / asof / approved_at / draft_payload / message_text)
- `holdings.py` — **POC2 Step 1**. 보유 종목 SSOT (`state/holdings/holdings_latest.json`)
- `draft.py` — `generate_draft_from_holdings` (운영) / `generate_draft` (샘플)
- `sample_draft.py` — 샘플용 stub payload 빌더
- `draft_message.py` — **POC2 Step 1A**. holdings draft → 사람이 읽는 message_text 빌더 (Telegram 본문)
- `delivery.py` — SCP/SSH 기반 OCI 전달 + outbox 조회 + holdings 식별 시 message_text 자동 첨부
- `config.py` — `.env` 자동 로드 + `require_env`/`optional_env` 표준 진입점
- `api.py` — FastAPI 엔드포인트 + CORS (localhost:3000) + holdings 엔드포인트

### 프론트 (`frontend/`)
- `app/page.tsx` — 서버 컴포넌트 (MainPanel 위임)
- `app/components/MainPanel.tsx` — 컨테이너 (운영 입력 우선 배치)
- `app/components/HoldingsClient.tsx` — **운영 진입점**. 행 단위 추가/삭제 + 매입금액/비중 즉시 계산
- `app/components/RunPanel.tsx` — run 표시 + Approve/Reject + 12s 느린 polling
- `app/components/SampleDraftQuickButton.tsx` — 개발/테스트용 고정 샘플 1버튼
- `lib/api.ts` — FastAPI 호출 유틸 + holdings/runs API

### OCI (`deploy/oci/`)
- `daily_ops.sh` — cron 09:05 KST 메인 엔트리. POC1 Step 3 분기로 inbox consumer 호출
- `poc1_consume_inbox.sh` — inbox 소비 + Telegram 발송 + outbox 작성

### 운영 스크립트 (루트)
- `start.bat` / `stop.bat` — ASCII 전용. 포트 3000/8000 정확 매칭 종료

### 테스트
- `tests/test_poc1_loop.py` — 25 케이스 (POC1 17 + POC2 8)

## API 엔드포인트

| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/holdings` | 저장된 holdings 조회 |
| PUT | `/holdings` | holdings 저장 (검증 실패 시 422) |
| POST | `/runs/generate-from-holdings` | **운영 흐름** — holdings 기반 PENDING_APPROVAL run 생성 |
| POST | `/runs/generate` | 샘플 입력 (개발/테스트용) |
| GET | `/runs` | 모든 run 목록 |
| GET | `/runs/{run_id}` | 단일 run 조회 + DELIVERING 인 경우 OCI outbox reconciliation |
| POST | `/runs/{run_id}/approve` | PENDING_APPROVAL → DELIVERING + SCP 백그라운드 |
| POST | `/runs/{run_id}/reject` | PENDING_APPROVAL → REJECTED |

## 상태 모델

```
PENDING_APPROVAL ── Reject  ──▶ REJECTED   (terminal)
       │
       ├─ Approve ─▶ DELIVERING ─ 전달 성공 ─▶ COMPLETED (terminal)
       │                         └ 전달 실패 ─▶ FAILED    (terminal)
       └─ Draft 생성 실패 ─────────────────────▶ FAILED    (terminal, 샘플 경로 한정)
```

APPROVED 상태는 존재하지 않는다. Approve 이벤트는 즉시 DELIVERING 으로 전이한다.
holdings 입력 검증 실패는 422 로 차단되며 run 자체가 만들어지지 않는다 (FAILED 와 구분).

## Telegram 메시지 (POC2 Step 1A)

- 메시지 문자열 생성 책임 = **로컬 백엔드** (`app/draft_message.py`)
- handoff artifact 의 top-level `message_text` 키로 OCI 에 전달
- OCI consumer (`deploy/oci/poc1_consume_inbox.sh`) 는 message_text 를 그대로 발송 (JSON 직접 파싱 안 함)
- holdings run 에서 message_text 누락 = `CONTRACT_ERROR` → FAILED outbox (raw JSON 대체 발송 금지)
- 평문 / 한국어 라벨 / 콤마·% 포맷 / payload 에 없는 필드는 줄 자체 생략

예시 메시지:
```
✅ POC2 holdings 승인 처리
run_id: run_20260426T134657_0d09feec
title: 보유 종목 기반 초안 (2026-04-26)

holdings 항목 2건 기준 자동 생성. ...

보유 종목:
1. RISE 미국은행TOP10 (0013P0)
   - 수량: 5
   - 평균 매입단가: 10,050원
   - 매입금액: 50,250원
   - 매입비중: 47.6%
   - 판단: HOLD
   - 사유: 보유 종목 현황 (이번 단계는 추천 판단 없이 HOLD 고정)
```

## 상태 갱신 정책 (POC1 Step 3 + POC2 Step 1)

- DELIVERING 상태에서만 제한적 polling (12초 간격, 최대 약 6분)
- terminal state(REJECTED / FAILED / COMPLETED) 도달 시 polling 즉시 중단
- 수동 새로고침 버튼도 제공
- WebSocket / SSE 는 도입하지 않음
- 별도 worker / scheduler 없음 — GET 호출이 reconciliation 트리거

## 환경변수 (`.env`, gitignored)

`.env.example` 참조. 표준 진입점 `app.config.require_env` 가 누락 시 fail-loud.

| 키 | 필수 | 설명 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | ✓ | OCI 측 consumer 가 사용 |
| `OCI_BACKEND_URL` / `OCI_OPS_TOKEN` | ✓ | Phase 1 호환 |
| `OCI_SSH_TARGET` | ✓ | `~/.ssh/config` alias 또는 `user@host` |
| `OCI_REMOTE_INBOX` / `OCI_REMOTE_OUTBOX` | ✓ | OCI 측 절대경로 |
| `OCI_SSH_KEY_PATH` | 선택 | 미설정 시 `~/.ssh/config` IdentityFile 사용 |
| `NEXT_PUBLIC_API_BASE` (`frontend/.env.local`) | ✓ | `http://127.0.0.1:8000` |

## 문서

- [PROJECT_ORIGIN_INTENT.md](./PROJECT_ORIGIN_INTENT.md) — 불변 앵커
- [ASSUMPTIONS.md](./ASSUMPTIONS.md) — open questions
- [KILL_SWITCHES.md](./KILL_SWITCHES.md) — 중단 조건
- [backlog/BACKLOG.md](./backlog/BACKLOG.md) — deferred 항목 (현재 30건 누적)
- [MASTER_PLAN.md](./MASTER_PLAN.md) — 전체 계획
- [handoff/POC1_Step3_close_and_POC2_Step1_handoff.md](./handoff/POC1_Step3_close_and_POC2_Step1_handoff.md) — POC1 Step 3 ~ POC2 Step 1 통합 handoff
- [handoff/POC2_Step1A_close.md](./handoff/POC2_Step1A_close.md) — POC2 Step 1A 종결 (가장 최근)
