# POC1 Step 3 closeout + POC2 handoff

작성일: 2026-04-25
작성자: 개발자(VSCode Claude)
상태: Step 3 구현 완료, Codex 검증 통과, 실사용 확인 완료
대상 독자: 다음 챕터(POC2) 진입자

---

## 1. 전체 여정 요약

Phase 2 POC1 은 "AI 초안 → 사람 승인/거절 → 외부 전달" 루프를 **1개 기능** 으로 완성하는 것이 목표였다. 세 단계로 진행됨.

### Step 1 — 최소 승인 루프 (commit `014a61c1`)
- 5 state 모델: `PENDING_APPROVAL / REJECTED / DELIVERING / FAILED / COMPLETED`
- 4필드 최소 계약: `run_id / asof / status / draft_payload`
- FastAPI 엔드포인트 4개 + JSON 파일 저장소 + Streamlit 임시 UI
- Codex 3차 검증 통과 (VERIFIED_WITH_NOTES)

### Step 2 — Streamlit 퇴출
- `ui_app.py` → `legacy/ui_app.py` 이동 (참조용 보존)
- `requirements.txt` 에서 `streamlit`, `requests` 제거
- docs/README.md 를 Next.js 기준으로 갱신

### Step 3 — Next.js 프론트 + CORS + 비동기 전달
- `frontend/` 하위에 Next.js 15 + TypeScript + App Router 스캐폴딩
- FastAPI `CORSMiddleware` (`localhost:3000` 허용)
- `post_approve` 를 `BackgroundTasks` 기반 비동기 전달로 전환
  - 응답은 `DELIVERING` 스냅샷으로 고정
  - 실제 `delivery.deliver()` 는 백그라운드에서 실행, 결과를 store 에 반영
  - 프론트 polling 이 정상 경로에서 작동 (AC 7/8 충족)
- `frontend/lib/api.ts` 에 `AbortController + 10초 timeout` 적용
- ESLint 9 flat config + `eslint-config-next`
- `start.bat` / `stop.bat` ASCII 재작성 (cp949 / UTF-8 충돌 근본 해소)

---

## 2. 현재 상태

### 실행 방법

**최초 1회 선행 조건**:
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
cd frontend && npm install && cd ..
copy frontend\.env.local.example frontend\.env.local
```

**정상 기동**:
```
start.bat     # FastAPI(8000) + Next.js(3000) 동시 기동 + 브라우저 자동 열기
stop.bat      # 포트 3000/8000 기반 프로세스 종료
```

**주요 URL**:
- Frontend : http://localhost:3000
- Backend  : http://127.0.0.1:8000/docs
- OpenAPI  : http://127.0.0.1:8000/openapi.json

### 동작 확인 시나리오

| 시나리오 | 입력 | 결과 |
|---|---|---|
| A. 정상 승인 | title/note/recommendations 모두 입력 → Approve | PENDING_APPROVAL → DELIVERING → COMPLETED (polling 관찰 가능) |
| B. 거절 | 정상 입력 → Reject | REJECTED (terminal) |
| C. 입력 실패 | 일부/전체 비움 → Generate | FAILED (draft_payload=null) |
| D. 깨진 JSON | recommendations 에 잘못된 JSON | 클라이언트 단 에러 배너, 서버 요청 차단 |
| E. terminal 재시도 | COMPLETED/REJECTED/FAILED 에서 액션 | UI 버튼 비노출 + 서버 409 이중 방어 |

---

## 3. 상태 모델 / 데이터 계약

```
PENDING_APPROVAL ── Reject ──▶ REJECTED    (terminal)
       │
       ├── Approve ─▶ DELIVERING ─ 전달 성공 ─▶ COMPLETED (terminal)
       │                         └ 전달 실패 ─▶ FAILED    (terminal)
       └── Draft 생성 실패 ─────────────────────▶ FAILED    (terminal)
```

- **APPROVED 상태 없음**: Approve 이벤트는 즉시 DELIVERING 으로 전이
- **terminal state**: REJECTED / FAILED / COMPLETED — 재실행 금지
- **새 시도**: 반드시 새 run_id 로 생성

### 데이터 계약 (4필드 고정)

| 필드 | 타입 | 비고 |
|---|---|---|
| `run_id` | `str` | `run_YYYYMMDDThhmmss_<uuid8>` |
| `asof` | `str (ISO-8601)` | 생성 시각(UTC) |
| `status` | `enum str` | 5 state 중 하나 |
| `draft_payload` | `dict | null` | FAILED 일 때 null 허용 |

UI / 백엔드 모두 동일 값 사용. 프론트 가공 상태 금지(KS-1).

---

## 4. 파일/디렉토리 구조

### 백엔드 (Python / FastAPI)
```
app/
├─ __init__.py
├─ api.py           # FastAPI 엔드포인트 + CORS + BackgroundTasks
├─ models.py        # Run dataclass, Status enum, TERMINAL_STATES
├─ state.py         # 상태 전이 규칙, InvalidTransition
├─ store.py         # state/runs/*.json 파일 저장소
├─ draft.py         # 초안 생성 엔트리
├─ sample_draft.py  # POC 전용 stub payload 빌더 (교체 대상)
└─ delivery.py      # 외부 전달 stub (교체 대상)

tests/
└─ test_poc1_loop.py  # 13 AC 테스트 (pytest)

state/
└─ runs/              # 런타임 산출물 (gitignore)
```

### 프론트엔드 (Next.js 15 / TypeScript / App Router)
```
frontend/
├─ package.json           # next/react/typescript + eslint + eslint-config-next
├─ tsconfig.json
├─ next.config.ts
├─ eslint.config.mjs      # ESLint 9 flat config
├─ .env.local.example     # NEXT_PUBLIC_API_BASE 견본 (실사용은 .env.local)
├─ .gitignore
├─ lib/
│  └─ api.ts              # FastAPI 호출 유틸 + AbortController timeout
└─ app/
   ├─ layout.tsx          # 서버 컴포넌트
   ├─ page.tsx            # 서버 컴포넌트 → 클라이언트 컴포넌트 위임
   ├─ globals.css         # 최소 CSS
   └─ components/
      └─ ApprovalLoopClient.tsx  # 'use client' + 승인 루프 단일 화면 + polling
```

### 운영 스크립트
```
start.bat   # FastAPI + Next.js 동시 기동, ASCII 전용
stop.bat    # 포트 3000/8000 기반 종료, findstr /C: literal 매칭
```

### 문서
```
docs/
├─ README.md               # 실행 가이드
├─ PROJECT_ORIGIN_INTENT.md  # 불변 앵커 (MDD보다 친구 놀람/4070s/와이프 UI)
├─ ASSUMPTIONS.md          # Open Questions (현재 Q1~Q3)
├─ KILL_SWITCHES.md        # 즉시/재검토 중단 기준 (Next.js 허용됨)
├─ MASTER_PLAN.md          # 전체 계획
├─ COLLAB_RULES.md         # 협업 규칙
├─ agent/
│  ├─ DEV_RULES.md         # 개발자(Claude) 상세 규칙
│  └─ VERIFY_RULES.md      # 검증자(Codex) 상세 규칙
├─ backlog/
│  └─ BACKLOG.md           # 16개 DEFERRED 항목
└─ handoff/                # 이 파일 포함
```

### 레거시 / 백업
```
legacy/ui_app.py           # Streamlit 퇴출, 참조용 보존 (실행 경로 아님)
docs/backup/               # Phase 1 인벤토리 + ML 화이트리스트 스냅샷
backup/                    # ML 코어 원본 (predictive_risk_classifier 등)
```

---

## 5. 검증 기록 (Step 3 최종 시점)

| 게이트 | 결과 |
|---|---|
| `black --check app/ tests/` | exit 0 |
| `flake8 app/ tests/` | exit 0 |
| `pytest tests/ -q` | 13 passed |
| `cd frontend && npm run lint` | 0 errors / 0 warnings |
| `cd frontend && NEXT_PUBLIC_API_BASE=... npm run build` | Compiled successfully |
| Codex 검증 (최종) | VERIFIED (REJECTED 3회 반영 후 통과) |

### Codex REJECTED 대응 이력 (참고)
1. flake8 E501 + _simulate_* 플래그 payload 오염 + 암묵 fallback
2. 400 경로 + delivery title fallback + README 링크 + UI 하드코딩 샘플
3. DELIVERING polling 정상 경로 미확보 → BackgroundTasks 비동기화
4. start.bat/stop.bat 보고 누락 + stop.bat findstr 부분 매칭 → `/C:` literal
5. findstr trailing space 오해 → `/C:` 옵션으로 literal 강제 실증

---

## 6. 알려진 한계 / BACKLOG 요약

### 이번 단계에서 해결하지 않은 대표 항목 (docs/backlog/BACKLOG.md 전체 16개)

#### POC1 전체 관통
- 실패 상태 세분화(DRAFT_FAILED / PUSH_FAILED 등) — FAILED 단일 유지
- 부분 재시도 정책(Retry Push / Retry Alert) — 새 run_id 로만 재시도
- 운영 필드 확장(approved_at / rejected_at / error_code 등) — 최소 4필드 고정
- 추적 필드(holdings_snapshot_ref 등) — 재현성 요구 발생 시 재검토
- spike_watch / holding_watch 연계 — 다른 알림 파이프라인 통합 보류
- ML 기반 초안 생성 연결 — `sample_draft.py` stub 유지, `backup/` ML 미배선
- DELIVERING 타임아웃 / orphan 처리 — BackgroundTasks 는 uvicorn 프로세스 수명 내만

#### Step 3 에서 추가됨
- Next.js UI 세분화 / 컴포넌트 구조 정리
- 전역 상태 관리 라이브러리(Redux/Zustand) 선도입 금지
- 상세 에러 UX 개선 (단일 배너 → 카테고리 분리)
- 수동 새로고침 시 run_id 유실 방지 (레드팀 MINOR, 최우선 재검토)
- 운영용 화면 분리 (POC2 이후)
- 인증/사용자 구분 — 단일 사용자 전제
- 스타일 시스템 / 컴포넌트 라이브러리 도입 여부
- 실제 운영 배포 구조 통합 (리버스 프록시 / 정적 서빙)
- polling 제거 또는 대체 실시간 갱신 방식 재검토

---

## 7. 다음 챕터(POC2) 진입자를 위한 컨텍스트

### POC1 에서 확정된 것
- **상태 모델/데이터 계약 동결**: 5 state × 4필드. 확장 금지의 근거는 [PROJECT_ORIGIN_INTENT](../PROJECT_ORIGIN_INTENT.md) 와 DEV_RULES "지시 범위 확장 금지"
- **기술 스택 확정**: FastAPI(Py3.14) + Next.js 15(TS + App Router) + JSON SSOT. MongoDB 금지, Next.js 전면 허용
- **실행 진입점**: `frontend/` (UI), `app/api.py` (백엔드). Streamlit 은 `legacy/` 로 보존만
- **검증 체계**: black + flake8 + pytest + npm lint + npm build 5단 품질 게이트 + Codex 7섹션 보고

### POC1 에서 드러난 UX 이슈 (POC2 개선 대상)
- **"본문" 용어 혼동**: UI 메시지 "초안 본문이 없습니다" vs 입력 필드 "메모(note)" 가 같은 "본문" 단어를 다른 의미로 사용. 실사용자가 혼동 보고함
- **선제 입력 검증**: 현재는 빈 입력 → 서버 FAILED run → UI 표시 순서. 클라이언트 단 선제 차단 여부 미정 (BACKLOG)
- **recommendations 타입 검증 없음**: `sample_draft` 는 키 존재만 검증. 숫자 `1` 을 recommendations 로 보내도 통과. stub 한계
- **ESLint 최소 프리셋**: `next/core-web-vitals` + `next/typescript` 만. 커스텀 규칙 0개

### POC2 착수 전 확인 필요 사항
1. **Q1 (factor 추가 10줄 이내)**: sample_draft 를 실제 factor 기반 로직으로 교체 시 난이도 측정 — ASSUMPTIONS.md 판정 기준
2. **Q2 (OCI 푸쉬 실동작)**: `app/delivery.py` stub 을 실제 Telegram/OCI 로 교체하는 범위 정의 필요
3. **Q3 (핑퐁 재발 여부)**: POC1 전 과정 경과 관찰 완료. Step 3 에서 Codex REJECTED 가 3회 발생했으나 각 라운드마다 구체 산출물 생성됨(3턴 KS-3 발동 기준 미달) → 현재는 통과 상태

### POC2 에서 우선 고려 후보 (설계자 확정 필요)
- **ML 기반 초안 생성기 실연결** (`backup/backtest/ml/predictive_risk_classifier.py`)
- **수동 새로고침 시 run_id 유지** (URL Query or localStorage)
- **외부 전달 실 연결** (Telegram / OCI — Q2 해소)
- **"본문" 용어 혼동 해결** (UI 메시지 or 선제 입력 차단)

구체 지시문은 **설계자(웹 GPT) 영역**. 개발자(Claude) 는 지시문 없이 구현 착수 금지.

---

## 8. 미완료 / 승인 대기 항목

다음 항목은 이번 챕터에서 **판단만 보고하고 구현은 보류** 상태:

| 항목 | 상태 |
|---|---|
| `start.bat` 선행 조건 자동 검사(.venv / npm install / .env.local) | 승인 대기 — 추가 시 ASCII 로 간단 확장 가능 |
| "본문 없음" 메시지 용어 수정 | 승인 대기 — `(a)` 메시지 수정 / `(b)` 선제 차단 / `(c)` BACKLOG 만 |
| `legacy/ui_app.py` 완전 삭제 시점 | 승인 대기 — 현재 참조 보존 |
| ESLint 커스텀 규칙 추가 여부 | BACKLOG 후보 |

---

## 9. 리소스 링크

- [docs/README.md](../README.md) — 실행 가이드
- [docs/PROJECT_ORIGIN_INTENT.md](../PROJECT_ORIGIN_INTENT.md) — 불변 앵커
- [docs/KILL_SWITCHES.md](../KILL_SWITCHES.md) — 중단 기준 (Next.js 허용 포함)
- [docs/backlog/BACKLOG.md](../backlog/BACKLOG.md) — 16 DEFERRED 전체
- [docs/agent/DEV_RULES.md](../agent/DEV_RULES.md) — 개발자 규칙
- [docs/agent/VERIFY_RULES.md](../agent/VERIFY_RULES.md) — 검증자 규칙

Git 상의 대응 커밋(최신순):
- Step 3 구현 커밋 (이 handoff 와 동일 push)
- `4e0dc3c1` docs(phase2): 운영 기반 문서 정착 + KILL_SWITCHES Next.js 허용
- `014a61c1` feat(poc1): Step 1 — 최소 승인 루프 구현 + Codex 3차 검증 통과
- `64e4b117` Phase 2 start: foundation documents

---

## 10. 다음 진입자에게 한 줄

POC1 의 5 state × 4필드 계약과 `frontend/` / `app/` 분리를 **건들지 말고** 위에 쌓으라. 새 기능 추가 시 먼저 [BACKLOG](../backlog/BACKLOG.md) 에서 관련 항목이 있는지 확인하고, 설계자 지시문을 받은 뒤 착수할 것.
