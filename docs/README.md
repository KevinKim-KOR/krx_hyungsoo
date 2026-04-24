# Phase 2 POC — 승인 루프 1단계

AI와 함께 투자 방향을 찾기 위한 최소 승인 루프 구현.

## 범위

- 초안 생성 → PENDING_APPROVAL
- 사용자 Approve → DELIVERING → COMPLETED 또는 FAILED
- 사용자 Reject → REJECTED
- 실패/거절된 run 은 재사용 금지, 새 run_id 로만 재시도

## 실행

```bash
# 백엔드
uvicorn app.api:app --host 127.0.0.1 --port 8000

# UI (다른 터미널)
streamlit run ui_app.py
```

## 구조

- `app/models.py` — 데이터 계약 (run_id / asof / status / draft_payload)
- `app/state.py` — 상태 전이 규칙
- `app/store.py` — JSON 파일 저장소 (state/runs/*.json)
- `app/draft.py` — 초안 생성
- `app/delivery.py` — 외부 전달 stub (BACKLOG: 실 연동)
- `app/api.py` — FastAPI 엔드포인트
- `ui_app.py` — Streamlit UI (백엔드 status 값 그대로 표시)
- `tests/test_poc1_loop.py` — Acceptance Criteria 검증

## 상태 모델

```
PENDING_APPROVAL ── Reject  ──▶ REJECTED   (terminal)
       │
       ├─ Approve ─▶ DELIVERING ─ 전달 성공 ─▶ COMPLETED (terminal)
       │                         └ 전달 실패 ─▶ FAILED    (terminal)
       └─ Draft 생성 실패 ─────────────────────▶ FAILED    (terminal)
```

APPROVED 상태는 존재하지 않는다. Approve 이벤트는 즉시 DELIVERING 으로 전이한다.

## 문서

- [PROJECT_ORIGIN_INTENT.md](./PROJECT_ORIGIN_INTENT.md) — 불변 앵커
- [ASSUMPTIONS.md](./ASSUMPTIONS.md) — open questions
- [KILL_SWITCHES.md](./KILL_SWITCHES.md) — 중단 조건
- [backlog/BACKLOG.md](./backlog/BACKLOG.md) — deferred 항목
