# Phase 2 POC — 승인 루프 1단계

AI와 함께 투자 방향을 찾기 위한 최소 승인 루프 구현.

## 범위

- 초안 생성 → PENDING_APPROVAL
- 사용자 Approve → DELIVERING → COMPLETED 또는 FAILED
- 사용자 Reject → REJECTED
- 실패/거절된 run 은 재사용 금지, 새 run_id 로만 재시도

## 실행

두 개의 터미널을 사용합니다. **UI 진입점은 `frontend/` (Next.js)** 입니다.
`legacy/ui_app.py` (Streamlit) 는 참조용 보존이며 실행 경로 아님.

### 1) FastAPI 백엔드

```bash
# 최초 1회
.venv/Scripts/pip install -r requirements.txt

# 기동
.venv/Scripts/python -m uvicorn app.api:app --host 127.0.0.1 --port 8000 --reload
```

### 2) Next.js 프론트엔드

```bash
# 최초 1회
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_BASE 확인

# 기동 (dev)
npm run dev   # http://localhost:3000
```

## 구조

- `app/models.py` — 데이터 계약 (run_id / asof / status / draft_payload)
- `app/state.py` — 상태 전이 규칙
- `app/store.py` — JSON 파일 저장소 (`state/runs/*.json`)
- `app/draft.py` — 초안 생성
- `app/sample_draft.py` — POC 전용 stub payload 빌더
- `app/delivery.py` — 외부 전달 stub (BACKLOG: 실 연동)
- `app/api.py` — FastAPI 엔드포인트 + CORS (localhost:3000 허용)
- `frontend/` — Next.js + TypeScript + App Router UI
  - `frontend/app/page.tsx` — 서버 컴포넌트 (클라이언트 뷰 위임)
  - `frontend/app/components/ApprovalLoopClient.tsx` — 승인 루프 클라이언트 컴포넌트
  - `frontend/lib/api.ts` — FastAPI 호출 유틸
- `tests/test_poc1_loop.py` — Acceptance Criteria 검증 (pytest)
- `legacy/ui_app.py` — 이전 Streamlit UI (참조용 보존, 실행 경로 아님)

## 상태 모델

```
PENDING_APPROVAL ── Reject  ──▶ REJECTED   (terminal)
       │
       ├─ Approve ─▶ DELIVERING ─ 전달 성공 ─▶ COMPLETED (terminal)
       │                         └ 전달 실패 ─▶ FAILED    (terminal)
       └─ Draft 생성 실패 ─────────────────────▶ FAILED    (terminal)
```

APPROVED 상태는 존재하지 않는다. Approve 이벤트는 즉시 DELIVERING 으로 전이한다.

## 상태 갱신 정책

- DELIVERING 상태에서만 제한적 polling (기본 1.5초 간격, 최대 약 45초)
- terminal state(REJECTED / FAILED / COMPLETED) 도달 시 polling 즉시 중단
- 수동 새로고침 버튼도 제공 (사용자가 언제든 최종 상태 확인)
- WebSocket / SSE 는 도입하지 않음

## 문서

- [PROJECT_ORIGIN_INTENT.md](./PROJECT_ORIGIN_INTENT.md) — 불변 앵커
- [ASSUMPTIONS.md](./ASSUMPTIONS.md) — open questions
- [KILL_SWITCHES.md](./KILL_SWITCHES.md) — 중단 조건
- [backlog/BACKLOG.md](./backlog/BACKLOG.md) — deferred 항목
- [MASTER_PLAN.md](./MASTER_PLAN.md) — 전체 계획
