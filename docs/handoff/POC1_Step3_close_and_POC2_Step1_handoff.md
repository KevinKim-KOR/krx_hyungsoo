# POC1 Step 3 closeout + POC2 Step 1 handoff

작성일: 2026-04-25
작성자: 개발자(VSCode Claude)
상태: POC1 Step 3 정식 종료(end-to-end 실증 완료) + POC2 Step 1 구현 완료(Codex VERIFIED_WITH_NOTES 후속 정리 완료, commit/push 완료)
대상 독자: 다음 챕터(POC2 Step 2 또는 운영 안정화) 진입자

---

## 1. 전체 여정 요약

| 단계 | 핵심 결과 | 대표 commit |
|---|---|---|
| Phase 2 시작 | 1929개 파일 삭제 후 foundation 문서 정착 | `64e4b117` |
| POC1 Step 1 | 5 state × 4필드 최소 승인 루프 (FastAPI + Streamlit 임시 UI) | `014a61c1` |
| POC1 Step 2 | Streamlit 퇴출 + Next.js 15 + TS + App Router 도입 + CORS 분리 + DELIVERING polling | `409ae5d6` |
| POC1 Step 3 | 실제 OCI 전달 (SCP) + 기존 daily_ops.sh 안의 새 step 으로 consumer 통합 + Telegram 발송 + outbox reconciliation | `b0501701` + `ad723723` |
| POC2 Step 1 | sample 입력 폼 → holdings 기반 운영 진입점 전환. JSON SSOT 저장 + 매입금액/비중 자동 계산 + UI 재배치 | `f5a6d6ce` |

---

## 2. POC1 Step 3 — 실증 evidence (정식 종료)

검증 시각: 2026-04-25 22:44 ~ 22:53 KST

| evidence | 값 |
|---|---|
| `approved_run_id` | `run_20260425T134409_8075d54c` |
| `oci_receipt_reference` | `OCI:~/krx_hyungsoo/state/poc1_processed/run_20260425T134409_8075d54c.json` (289 bytes, 22:44 도달, 22:52 처리 후 processed/ 이동) |
| `oci_consume_reference` | `[poc1] processing run_id=run_20260425T134409_8075d54c → COMPLETED, consume done: completed=1 failed=0` (consumer 1회 수동 실행, 설계자 명시 허용 범위) |
| `notification_reference` | Telegram `message_id=2469`, 사용자 디바이스 수신 확인 (본문: `✅ POC1 승인 처리 / run_id: ... / title: 1 / note: 1 / recommendations: 1`) |
| `final_status` | `COMPLETED` (로컬 store reconciliation 후 갱신 확인) |

### 2.1 실 운영 흐름 검증 결과

```
[로컬 Approve]
  └→ state/poc1_handoff/{run_id}.json staging
  └→ scp → OCI:~/krx_hyungsoo/state/poc1_inbox/{run_id}.json
  └→ archive: state/poc1_handoff_processed/

[OCI consumer 1회 수동 실행 — 22:52 KST]
  └→ inbox 파일 발견 → Telegram sendMessage 성공
  └→ outbox/{run_id}.json 작성 (status=COMPLETED, telegram_message_id=2469)
  └→ inbox → processed/ 이동

[로컬 GET /runs/{run_id}]
  └→ DELIVERING 감지 → SSH cat outbox 성공
  └→ store 갱신: status=COMPLETED
```

### 2.2 Step 3 의 운영적 한계

- **자동 cron(09:05 KST) 경로**는 다음 자연 발생 시점에 자연 검증 예정 (수동 1회 검증 + cron schedule 등록은 완료)
- **Telegram 재시도 정책 없음** (1회 실패 = FAILED outbox)
- **OCI inbox orphan 정리 미구현**

---

## 3. POC2 Step 1 — holdings 기반 draft 생성 전환 (구현 완료)

### 3.1 운영 진입점 변경 (사용자/설계자 결정)

| 영역 | POC1 (이전) | POC2 Step 1 (현재) |
|---|---|---|
| 메인 화면 첫 섹션 | title/note/recommendations 직접 입력 폼 | **HoldingsClient** (행 단위 추가/삭제 + 매입금액/비중 즉시 계산) |
| 입력 검증 실패 처리 | 빈 dict 도 FAILED run 으로 저장 (POC1 규칙) | **422 차단** (run_id 생성 안 함) |
| 샘플 입력 | 메인 화면 큰 폼 | 가장 아래 `<details>` 접힘 + 고정 샘플 1버튼 ("개발/테스트용 — 운영 입력 아님") |
| draft_payload 생성 | sample_draft.build_sample_payload | `app.draft._build_holdings_payload` (운영) / `sample_draft.build_sample_payload` (샘플) |
| 추천 로직 | (없음) | `action="HOLD"` 고정, `score` 필드 없음. 보유 현황 그대로 |

### 3.2 holdings 입력 필드 (사용자 확정 결정)

| 필드 | 타입 | 필수 | 비고 |
|---|---|---|---|
| `ticker` | str | 필수 | 빈 문자열/공백 차단 |
| `quantity` | float | 필수 | > 0 |
| `avg_buy_price` | float | 필수 | > 0 (이번 단계까지 자동 계산되는 단가) |
| `name` | str | 선택 | 미입력 시 ticker 로 표시 (Naver 자동조회는 BACKLOG) |

저장 위치: `state/holdings/holdings_latest.json` (단일 SSOT, gitignored). DB 도입 / in-memory 단독 / frontend localStorage 단독 보관 모두 금지.

### 3.3 holdings → recommendations 매핑 (8 필드, score 없음)

```
ticker / name / quantity / avg_buy_price (입력에서 직접)
+ invested_amount  = quantity * avg_buy_price
+ buy_weight_pct   = invested_amount / total * 100 (소수 둘째자리 반올림)
+ action           = "HOLD" (고정)
+ reason           = "보유 종목 현황 (이번 단계는 추천 판단 없이 HOLD 고정)"
```

### 3.4 API 엔드포인트 (POC2 Step 1 신규)

| 엔드포인트 | 용도 |
|---|---|
| `GET  /holdings` | 저장된 holdings 조회 (없으면 빈 리스트) |
| `PUT  /holdings` | holdings 저장. validation 실패 시 422 |
| `POST /runs/generate-from-holdings` | 저장된 holdings 로 PENDING_APPROVAL run 생성. holdings 비어있으면 422 |

기존 엔드포인트(`POST /runs/generate`, `POST /runs/{id}/approve|reject`, `GET /runs[/{id}]`) 는 그대로 유지. `/runs/generate` 는 샘플 입력 전용으로 격하됨.

### 3.5 UI 구조 (frontend/app/components/)

```
MainPanel (컨테이너)
├─ HoldingsClient        ← 운영 진입점. 첫 섹션
├─ RunPanel              ← run 있을 때만 표시 (Approve/Reject + 12s polling)
└─ <details> 접힘
   └─ SampleDraftQuickButton  ← 개발/테스트용 고정 샘플 1버튼
```

`ApprovalLoopClient.tsx` 는 RunPanel + SampleDraftQuickButton 으로 분해되어 삭제됨.

---

## 4. 현재 코드 / 인프라 상태

### 4.1 백엔드 (`app/`)
- `api.py` — FastAPI + CORS + BackgroundTasks + holdings 엔드포인트
- `config.py` — `.env` 자동 로드 (python-dotenv) + `require_env`/`optional_env` 표준 진입점
- `delivery.py` — SCP/SSH 기반 OCI 연결 + `OCI_SSH_KEY_PATH` 옵션
- `draft.py` — `generate_draft` (샘플) / `generate_draft_from_holdings` (운영)
- `holdings.py` — JSON SSOT 저장소 + Holding dataclass + validation
- `models.py` / `state.py` / `store.py` / `sample_draft.py` — 그대로

### 4.2 프론트 (`frontend/`)
- Next.js 15 + TypeScript + App Router + ESLint flat config
- `lib/api.ts` — FastAPI 호출 유틸 + AbortController 10s timeout + holdings/runs API 함수
- `app/components/` — MainPanel / HoldingsClient / RunPanel / SampleDraftQuickButton

### 4.3 OCI 측 (`deploy/oci/`)
- `daily_ops.sh` — 09:05 KST cron + 새 step 으로 `poc1_consume_inbox.sh` 호출
- `poc1_consume_inbox.sh` — inbox 소비 + Telegram + outbox 작성. fail-loud 검증

### 4.4 운영 스크립트
- `start.bat` — uvicorn(8000) + npm run dev(3000) + 브라우저 자동 열기 (ASCII)
- `stop.bat` — 포트 3000/8000 정확 매칭 종료 (`findstr /C:` literal)

### 4.5 테스트
- `tests/test_poc1_loop.py` — 25 케이스 (POC1 17 + POC2 8). black/flake8/eslint/npm build 전부 통과

---

## 5. 환경 / 의존성

### 5.1 백엔드 (`requirements.txt`)
```
fastapi >= 0.110
uvicorn >= 0.27
pydantic >= 2.5
pytest >= 8.0
httpx >= 0.27
python-dotenv >= 1.0
```

### 5.2 프론트 (`frontend/package.json`)
```
next ^15.1.0, react ^19, typescript ^5.7
@types/* + eslint ^9 + eslint-config-next ^15.1 + @eslint/eslintrc ^3.2
```

### 5.3 환경변수 (`.env`, gitignored)
| 키 | 필수 | 설명 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | 필수 | OCI consumer 가 사용 |
| `OCI_BACKEND_URL` / `OCI_OPS_TOKEN` | 필수 | Phase 1 호환 |
| `OCI_SSH_TARGET` | 필수 | `~/.ssh/config` alias 권장 (`oci-krx`) |
| `OCI_REMOTE_INBOX` / `OCI_REMOTE_OUTBOX` | 필수 | OCI 측 절대경로 |
| `OCI_SSH_KEY_PATH` | 선택 | 미설정 시 `~/.ssh/config` IdentityFile 사용 |
| `NEXT_PUBLIC_API_BASE` (`frontend/.env.local`) | 필수 | `http://127.0.0.1:8000` |

`~/.ssh/config` 에 `oci-krx` alias 박아두면 IP 노출 없이 운영 가능.

---

## 6. BACKLOG 요약 (현재 23건 누적)

### POC1 누적
- 실패 상태 세분화 (DRAFT/PUSH/ALERT)
- 부분 재시도 정책 (Push/Alert)
- 운영 필드 확장 (approved_at/rejected_at/error_code)
- 추적 필드 (holdings_snapshot_ref / market_data_snapshot_ref)
- spike_watch / holding_watch 연계
- ML 기반 초안 생성 연결
- DELIVERING 타임아웃/orphan 처리
- Next.js UI 세분화, 전역 상태 관리, 에러 UX
- 수동 새로고침 시 run_id 유실 방지 (레드팀 MINOR)
- 운영 화면 분리, 인증, 스타일 시스템, 배포 구조 통합, polling 재검토
- OCI handoff 형식 고도화, 알림 재시도, OCI orphan, 결과 대시보드, 복수 알림 채널
- DELIVERING 느린 polling 고도화

### POC2 Step 1 신규
- holdings 스키마 확장 (계좌 / 매입일 / 메모 등)
- holdings 자동 import (KIS / OpenAPI / CSV)
- Naver Finance 종목명 자동 조회
- 현재가 / 평가금액 / 평가손익 / 수익률 / 현재가 기준 비중
- 추천 로직 / 정렬 / score 도입
- ML 기반 draft 생성기 연결 (POC2 Step 1 재확인)
- 샘플 입력 폼 완전 제거
- holdings 히스토리 / 스냅샷 관리
- 운영용 holdings 편집 UX 개선
- 복수 포트폴리오 / 계좌 지원
- 09:05 cron 자연 발생 검증 결과 반영
- ASSUMPTIONS Q2 closeout 이후 후속 질문 정리

전체 항목은 [docs/backlog/BACKLOG.md](../backlog/BACKLOG.md) 참조.

---

## 7. 다음 챕터 진입자에게

### 7.1 즉시 진행 가능한 후보 (사용자 결정 영역)

- **(A) ASSUMPTIONS Q2 ANSWERED 처리**: Step 3 evidence 가 채워졌으므로 Q2 ("OCI 푸쉬 파이프라인 동작 여부") 를 ANSWERED 섹션으로 이동. 아직 보류 중.
- **(B) 09:05 cron 자연 발생 검증**: 다음 09:05 KST 시점에 cron 이 inbox 잔존 파일을 자연스럽게 소비하는지 모니터링.
- **(C) 현재가 / 평가지표 도입 (POC2 Step 2 후보)**: pykrx / KIS / Naver / yfinance 중 시세 소스 결정 + draft_payload 확장. ML 단계는 아님.
- **(D) holdings 자동 import**: KIS API 또는 CSV 업로드.
- **(E) ML 연결**: backup/backtest/ml/predictive_risk_classifier 와 holdings 결합.

### 7.2 건드리지 말아야 할 것 (POC2 Step 1 까지 확정된 계약)

- **5 state 모델** (PENDING_APPROVAL / REJECTED / DELIVERING / FAILED / COMPLETED)
- **draft_payload 4 키** (title / asof / status 외 / draft_payload)
- **OCI handoff 4 키** (run_id / asof / approved_at / draft_payload)
- **상태 전이 규칙** (`app.state.ALLOWED_TRANSITIONS`)
- **terminal state 차단 정책**
- **GenerateDraft 실패 → FAILED 단일 규칙** (샘플 경로 한정)
- **holdings 검증 실패 → 422 차단** (POC2 규칙, run 생성 안 함)
- **표준 환경변수 진입점** (`app.config.require_env` / `optional_env`)
- **한글 ASCII 정책** (`start.bat` / `stop.bat` 는 ASCII 만)

### 7.3 운영 협조 필요 사항

- 09:05 cron 자연 발생 시 OCI 측 logs/poc1_consume.log 확인
- 다음 신규 환경변수 추가 시 `.env.example` + `app.config` 표준 진입점 사용

---

## 8. 검증 게이트 통과 기록

```
.venv/Scripts/black.exe --check app/ tests/   → exit 0
.venv/Scripts/flake8.exe  app/ tests/         → exit 0
.venv/Scripts/python.exe -m pytest tests/ -q  → 25 passed
cd frontend && npm run lint                   → exit 0
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000 npm run build   → Compiled successfully
```

main HEAD: `f5a6d6ce`. origin/main 동기화 완료.

---

## 9. 한 줄 당부

POC1 의 5 state × 4필드 + POC2 Step 1 의 holdings 진입점 / 422 차단 정책을 **건드리지 말고** 위에 쌓으라. 새 기능 추가 전 [docs/backlog/BACKLOG.md](../backlog/BACKLOG.md) 에 관련 항목이 있는지 먼저 확인하고, 설계자 지시문을 받은 뒤 착수할 것.
