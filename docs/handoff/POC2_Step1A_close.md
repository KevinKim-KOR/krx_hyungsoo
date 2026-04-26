# POC2 Step 1A 종결 — raw JSON 표시 제거 + holdings 초안 사람이 읽는 렌더링

작성일: 2026-04-26
작성자: 개발자(VSCode Claude)
상태: 구현 완료 + commit/push 완료. 사용자 디바이스 Telegram 새 형식 수신 확인은 다음 cron(09:05 KST 자연 발생) 또는 1회 수동 실행 시점에 이뤄짐.
대상 독자: 다음 챕터(POC2 Step 2 또는 운영 안정화) 진입자

---

## 1. 단계 목적 (한 줄)

POC2 Step 1 까지 만든 holdings 기반 draft 가 화면/Telegram 에서 raw JSON 으로 노출되던 것을 사람이 읽는 형태로 표현 계층만 보정. 데이터 신규 생성 / ML 연결 / 추천 로직 / 시세 도입은 모두 금지하고, **이미 존재하는 필드만** 사람이 읽는 형식으로 렌더링.

---

## 2. 사용자 결정 사항 반영

| Q | 결정 | 적용 위치 |
|---|---|---|
| handoff artifact 어디에 message_text 를 넣을지 | **(a) top-level 5번째 키** | `app/store.py::write_handoff_artifact` + `deploy/oci/poc1_consume_inbox.sh` |
| 숫자 포맷 | 콤마(`50,250원`) + `%` | `app/draft_message.py` + frontend `Number.toLocaleString("ko-KR")` |
| 기존 RunPanel 안에서 holdings 감지 후 카드 리스트 | OK | `frontend/app/components/RunPanel.tsx::Recommendations` |
| 메시지 헤더 | "POC2 holdings 승인 처리" | `app/draft_message.py::build_message_text` |
| 샘플 초안 | 그대로 유지 (raw 표시 / 접힘 섹션 / "개발/테스트용" 라벨) | 변경 없음 |

---

## 3. 책임 분리 (Step 1A 핵심)

```
[로컬 FastAPI]
  └─ delivery.deliver() 가 holdings 식별 시
     · draft_message.build_message_text(run_id, payload) 호출
     · staging artifact 의 top-level 5번째 키 message_text 로 포함
     · scp 로 OCI inbox 에 전달

[OCI]
  └─ daily_ops.sh → poc1_consume_inbox.sh
     · Python 블록이 message_text 우선 사용
     · holdings + message_text 누락 = CONTRACT_ERROR → FAILED outbox
     · 비-holdings + message_text 없으면 POC1 형식 fallback (호환)
     · OCI bash 가 recommendations JSON 을 직접 파싱해 메시지 조립하지 않음
```

**핵심 규칙**: 메시지 문자열 생성은 **로컬 백엔드 단독 책임**. OCI 는 발송만 담당.

---

## 4. handoff artifact 5필드 구조 (POC2 Step 1A 확정)

```json
{
  "run_id": "run_YYYYMMDDThhmmss_xxxxxxxx",
  "asof": "ISO-8601",
  "approved_at": "ISO-8601",
  "draft_payload": {
    "title": "...",
    "asof": "...",
    "note": "...",
    "recommendations": [ ... ]
  },
  "message_text": "✅ POC2 holdings 승인 처리\n..."
}
```

- `message_text` 는 holdings run 일 때 필수, 비-holdings 에서는 키 자체 생략 가능
- `draft_payload` 4 키 구조는 **변경 없음** (책임 분리 — payload 는 승인 본문, message_text 는 발송 본문)

---

## 5. 메시지 형식 예시

```
✅ POC2 holdings 승인 처리
run_id: run_20260426T134657_0d09feec
title: 보유 종목 기반 초안 (2026-04-26)

holdings 항목 2건 기준 자동 생성. 이번 단계는 보유 현황 기반 초안이며 추천 판단(매수/매도 등)은 포함하지 않습니다.

보유 종목:
1. RISE 미국은행TOP10 (0013P0)
   - 수량: 5
   - 평균 매입단가: 10,050원
   - 매입금액: 50,250원
   - 매입비중: 47.6%
   - 판단: HOLD
   - 사유: 보유 종목 현황 (이번 단계는 추천 판단 없이 HOLD 고정)
2. 0015B0
   - 수량: 5
   - 평균 매입단가: 11,063원
   - 매입금액: 55,315원
   - 매입비중: 52.4%
   - 판단: HOLD
   - 사유: 보유 종목 현황 (이번 단계는 추천 판단 없이 HOLD 고정)
```

- 종목명 미입력은 ticker 단독 표시 (외부 자동조회 안 함)
- payload 에 없는 필드는 줄 자체 생략 (undefined/None 노출 없음)

---

## 6. 변경 파일 (commit f4c58f2c + 5a3282a6)

**신규**:
- `app/draft_message.py` — holdings 식별 + message_text 빌더

**수정**:
- `app/store.py` — `write_handoff_artifact(run, approved_at, message_text=None)`
- `app/delivery.py` — `deliver()` 가 holdings 식별 시 message_text 자동 생성
- `deploy/oci/poc1_consume_inbox.sh` — message_text 우선 사용, holdings 누락 시 CONTRACT_ERROR
- `frontend/app/components/RunPanel.tsx` — `Recommendations` 가 holdings 식별 시 `HoldingsCard` 카드 리스트 렌더
- `frontend/app/globals.css` — `.holdings-list` / `.holdings-item` 스타일
- `tests/test_poc1_loop.py` — Step 1A 단위 6건 추가 (총 31)
- `docs/backlog/BACKLOG.md` — Step 1A deferred 7건 추가
- `.gitignore` — `backup/` 추가 (사용자 결정으로 19개 파일 추적 해제 + 향후도 ignore)

---

## 7. 검증 게이트 통과 기록

```
.venv/Scripts/black.exe --check app/ tests/   → exit 0
.venv/Scripts/flake8.exe  app/ tests/         → exit 0
.venv/Scripts/python.exe -m pytest tests/ -q  → 31 passed
bash -n deploy/oci/poc1_consume_inbox.sh      → exit 0
cd frontend && npm run lint                   → exit 0
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000 npm run build   → Compiled successfully
```

---

## 8. 알려진 한계 / 미완성

- **Telegram 평문 한정** — 마크다운 / 이모지 강조 / parse_mode 미사용 (BACKLOG)
- **현재가 / 평가지표 / 수익률 미포함** — 시세 소스 미연결 (BACKLOG)
- **추천 판단 정적** — action=HOLD, reason 정적 stub. ML 미연결 (BACKLOG)
- **Telegram 단일 채널** — Slack/Discord/Email 등 미도입 (BACKLOG)
- **OCI consumer fallback 은 POC1 형식 그대로** — 운영 흐름은 모두 holdings 라 영향 없음
- **사용자 협조 영역** — 다음 cron(09:05 KST) 자연 발생 또는 1회 수동 실행 후 새 메시지 형식 디바이스 수신 확인

---

## 9. 다음 챕터 진입자에게

### 건드리지 말아야 할 것 (Step 1A 까지 확정 계약)

- 5 state 모델 / 4필드 draft_payload / handoff 5필드 (run_id / asof / approved_at / draft_payload / message_text)
- 상태 전이 규칙 / terminal state 차단 / 422 입력 차단
- holdings 식별 규약 (recommendations 첫 항목에 quantity 또는 avg_buy_price)
- message_text 생성 책임 = 로컬 백엔드. OCI bash 는 발송만
- 표준 환경변수 진입점 (`app.config.require_env` / `optional_env`)
- ASCII 정책 (`start.bat` / `stop.bat`)
- `.gitignore` `backup/` 룰

### 즉시 진행 가능한 후보

- **(A) ASSUMPTIONS Q2 ANSWERED 처리** (사용자 결정 보류 중)
- **(B) 09:05 cron 자연 발생 검증** (다음 자연 발생 시점)
- **(C) 현재가 / 평가지표 도입 (POC2 Step 2 후보)** — pykrx/KIS/Naver/yfinance 중 시세 소스 결정 필요
- **(D) holdings 자동 import** (KIS API / CSV)
- **(E) ML 연결** (backup/ 의 predictive_risk_classifier 와 holdings 결합)

---

## 10. 한 줄 당부

POC2 Step 1A 의 책임 분리 원칙 — **사람이 읽는 메시지는 로컬 백엔드, OCI 는 발송만** — 을 깨지 말고 위에 쌓아라. 새 채널을 추가하면 message_text 외에 채널별 키를 분리할지, 함수만 분리할지를 BACKLOG 에서 먼저 검토할 것.
