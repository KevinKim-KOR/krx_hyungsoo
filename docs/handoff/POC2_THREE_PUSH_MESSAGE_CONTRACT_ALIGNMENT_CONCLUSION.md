# POC2 — 3-PUSH Message Contract 정렬 CONCLUSION

작성: 2026-06-12
성격: Step 완료 보고. canonical 상태 (`docs/STATE_LATEST.md`) 의 detail 링크.

---

## 0. 한 줄 요약

기존 `Run → Approval → OCI handoff → Telegram` 단일 경로를 유지하면서 하루 3종
PUSH 메시지 (`market_briefing` / `holdings_briefing` / `spike_or_falling_alert`)
의 `message_text` 계약을 정리. 새 PUSH API / Telegram 직접 발송 / OCI 재구성 /
scheduler / 신규 외부 source / 매수·매도·교체·현금비중·조정장 확정 0건.

PUSH-2 holdings briefing 은 기존 `generate-from-holdings` 가 재정의되어 동일
계약 (`push_kind="holdings_briefing"`) 으로 동작. PUSH-1 / PUSH-3 은 신규 builder
2종 추가 + 기존 `POST /runs/generate` 의 `input_data.push_kind` 분기로 통합 —
**신규 PUSH endpoint 0건** (지시문 §3 / §11 별도 PUSH API 신설 금지선 준수,
FIX r2 — 설계자 수용). 모두 외부 source 호출 0건 — 저장된 evidence / read-only
API 결과만 사용.

---

## 1. AC 달성 현황

```text
AC-1  3종 PUSH message type 정리 (push_kind 식별자)                         = DONE
AC-2  기존 message_text 단일 소스 유지 (frontend 조립 0건)                  = DONE
AC-3  기존 delivery 경로 유지 (Telegram 직접 호출 0건)                      = DONE
AC-4  PUSH-1 시장 흐름 브리핑 message_text 생성 (뉴스 섹션 미존재 시 생략)  = DONE
AC-5  PUSH-2 holdings 브리핑 (매수/매도/교체/비중 조절 0건, 기존 재정의)    = DONE
AC-6  PUSH-3 급등락 알림 (ETF universe 만, 개별 주식 source 도입 0건)       = DONE
AC-7  승인 게이트 유지 (생성 즉시 발송 X, scheduler X)                      = DONE
AC-8  PENDING_APPROVAL → DELIVERING → COMPLETED/FAILED 흐름 유지            = DONE
AC-9  AI Session payload 전체 전송 0건 (message_text 만 전송)               = DONE
AC-10 raw JSON / token / chat_id / 매매 지시 / 위험 threshold 확정 0건      = DONE (FIX r2 — 변수명 "threshold" 제거)
AC-11 테스트 중 실제 Telegram 발송 0건 (delivery 호출 격리)                 = DONE
AC-12 기존 흐름 (GenerateDraft / Run / Approval / OCI / outbox) 유지        = DONE
AC-13 문서 갱신 (STATE / NEXT_ACTIONS / FEATURE_INVENTORY + 본 파일)        = DONE
```

**FIX r2 — 설계자 수용 (2026-06-12, 1차 REJECTED 후속)**:
- A-1 / A-4: 별도 PUSH endpoint 신설 → `app/api_three_push.py` 삭제 + 기존
  `/runs/generate` 의 `input_data.push_kind` 분기로 통합.
- A-2 / A-3: 문서 "새 PUSH API 0건" / "3개 신규 endpoint" 모순 정정.
- A-3: `app/models.py` docstring 정정 (`message_text` / `push_kind` 필드 반영).
- B-1: `_load_universe_artifact` 손상 / 부재 구분 로그 추가.
- B-6: `SPIKE_DISPLAY_THRESHOLD_PCT` → `SPIKE_DISPLAY_RETURN_PCT_MIN` rename +
  message_text 본문 "표시 임계" → "표시 하한" 정리.

**FIX r3 — 검증자 PARTIALLY_VERIFIED 후속 (2026-06-12, B-2 / B-3 / B-6 수용)**:
- B-2 / B-3 draft.py 책임 집중 (623 라인, KS-10 near 진입): PUSH-1/3 entry +
  분기 진입점 + universe artifact loader 를 신규 `app/draft_three_push.py`
  (207 라인) 로 분리. draft.py 465 라인으로 복귀 (KS-10 안전 영역). draft.py
  는 re-export 만 유지하여 기존 호출자 (tests / 운영 호출 경로) 호환 보장.
- B-6 stale 주석: `app/api.py` 의 "app/api_three_push.py 로 분리" 표현, 그리고
  `frontend/lib/api/runApproval.ts` 상단 주석의 삭제된 endpoint 경로 표기 모두
  현재 구조 (POST /runs/generate + input_data.push_kind) 로 정정.

---

## 2. 변경 파일 (구조)

**Backend 신규 (2)**:
- `app/message_market_briefing.py` **184 라인** — PUSH-1 builder. ML baseline
  evidence snapshot + Market Discovery TopN 을 입력으로 받아 시장 내부 신호 /
  위험 패턴 참고 / 외부 변수 체크리스트 3섹션 message_text 생성. 외부 source
  호출 0건. 뉴스 source 추가 0건 (§4.2).
- `app/message_spike_alert.py` **212 라인** — PUSH-3 builder. compute_topn +
  universe_momentum_latest.json 을 입력으로 받아 ETF universe 변동성 확대 /
  기존 급락 ETF 신호 재사용 / data_quality 3섹션 생성. **개별 주식 전체 source
  도입 0건** (§4.4). `SPIKE_DISPLAY_RETURN_PCT_MIN` (변수명에 "threshold" 단어
  사용하지 않음 — §12 와 의미 분리).

**Backend 제거 (FIX r2)**:
- `app/api_three_push.py` (1차 작업에서 신설했던 PUSH-1 / PUSH-3 router) —
  §3 / §11 별도 PUSH API 신설 금지선과 충돌하여 **삭제**. PUSH-1 / PUSH-3 은
  기존 `POST /runs/generate` 의 `input_data.push_kind` 분기로 통합.

**Backend 수정 (4)**:
- `app/models.py` — `Run.push_kind: Optional[str]` 필드 추가. `PushKind` Literal
  타입 정의. `from_dict` 가 과거 run (필드 없음) 을 None 으로 허용 (하위호환).
  docstring 정정 (FIX r2): `message_text` / `push_kind` 반영, "필드 4개만 사용"
  표현 정정.
- `app/draft.py` — `generate_market_briefing_draft()` / `generate_spike_alert_
  draft()` 2종 entry 추가. 기존 `generate_draft_from_holdings()` 는 `push_kind
  ="holdings_briefing"` 자동 부여 (PUSH-2 재정의). **FIX r2 (설계자 수용)**:
  `generate_draft(input_data)` 가 `input_data.push_kind` 로 분기하도록 확장 —
  `"market_briefing"` / `"spike_or_falling_alert"` / 그 외 (기존 sample_draft).
  `_load_universe_artifact_for_spike()` 가 부재(정상)와 손상(이상) 을 logger
  로 구분.
- `app/api.py` — `RunResponse` 에 push_kind 필드 추가. **FIX r2 (설계자 수용)**:
  1차에서 추가했던 `three_push_router` include 제거 — 신규 endpoint 0건.
- `app/delivery.py` — message_text 누락된 PUSH-1/3 run 이 holdings builder 로
  rebuild 되어 raw recommendations 발송되는 분기 차단 (DeliveryError raise).

**Frontend 신규 (1)**:
- `frontend/app/components/ThreePushDraftCard.tsx` **107 라인** — PUSH-1 / PUSH-3
  진입점 카드. ApprovalTelegramView 안에 임시 위치 (정식 UX 는 별도 STEP).

**Frontend 수정 (2)**:
- `frontend/lib/api/runApproval.ts` — `PushKind` 타입 + `Run.push_kind` 필드
  추가 + `generateMarketBriefingDraft()` / `generateSpikeAlertDraft()` API 함수.
  **FIX r2**: 두 함수는 `POST /runs/generate` 를 호출하며 `input_data.push_kind`
  를 body 로 전송 (별도 endpoint 호출 아님).
- `frontend/app/components/ApprovalTelegramView.tsx` — `<ThreePushDraftCard />`
  추가 (UniverseRefreshPanel 직후).

**Tests 신규 (1)**:
- `tests/test_three_push_contract.py` **463 라인** — 18 테스트 3층 구조
  (사용자 결정 (a)):
  - Layer 1 builder 단위: PUSH-1/3 섹션 포함 / 뉴스 섹션 생략 / 금지 문구
    0건 / 길이 안전 / raw JSON 0건 / 기존 급락 신호 재사용 / empty universe
    safe default.
  - Layer 2 draft 통합: generate_market_briefing_draft / generate_spike_alert_
    draft 가 PENDING_APPROVAL + push_kind 박힌 Run 반환. holdings draft 가
    "holdings_briefing" 자동 부여.
  - Layer 3 API: POST 2종이 PENDING_APPROVAL + push_kind 전파 / delivery 호출
    안 함 (AC-7 인간 승인 전 발송 차단 검증) / Run 직렬화 하위호환 / delivery
    fallback 안전 (PUSH-1 + message_text=None → DeliveryError).

**Docs 수정 (3)** + **신규 (1)**:
- `docs/STATE_LATEST.md` / `docs/handoff/POC2_B_NEXT_ACTIONS.md` /
  `docs/handoff/POC2_FEATURE_INVENTORY.md`.
- `docs/handoff/POC2_THREE_PUSH_MESSAGE_CONTRACT_ALIGNMENT_CONCLUSION.md` —
  본 파일.

---

## 3. 핵심 설계 결정 (사용자 확정)

### 3.1 진입점 — FIX r2 (설계자 수용): 기존 `/runs/generate` + input 분기

1차 작업에서 사용자 결정으로 3개 신규 endpoint (a) 를 택했으나, 지시문 §3
("새 PUSH API를 만드는 작업이 아니다") / §11 ("별도 PUSH API 신설 금지") 와
충돌한다는 설계자 의견을 수용. **FIX r2**: 신규 endpoint 2개를 모두 제거하고
PUSH-1 / PUSH-3 은 기존 `POST /runs/generate` 의 `input_data.push_kind` 분기로
통합. PUSH-2 는 holdings 데이터 의존성으로 인해 기존 `/runs/generate-from-
holdings` 가 재정의된 형태로 유지. 신규 PUSH endpoint **0건**.

### 3.2 Run 데이터 계약 — (a) Run.push_kind Optional[str] 최소필드

draft_payload 내부 key 가 아니라 Run 의 top-level 필드로 push_kind 를 두어
- 식별 / 계약적 명확도 우선,
- from_dict 가 과거 run (필드 없음) 을 None 으로 허용 (하위호환),
- delivery / OCI consumer 가 본 필드를 읽지 않으므로 인터페이스 영향 0.

### 3.3 PUSH-2 범위 — (a) 기존 generate-from-holdings 를 재정의

현재 `generate_draft_from_holdings()` 가 이미 holdings 관찰 브리핑 성격이므로
push_kind 만 박아 PUSH-2 로 재정의. 새 builder / 새 entry 추가 0건. 중복 코드
회피 + 최소 변경 원칙.

### 3.4 테스트 전략 — (a) 3층 (builder / draft / API)

builder 단위에서 금지 문구 0건 + 허용 문구 포함 + 길이 안전 직접 검증. draft
layer 에서 push_kind 정확히 박히는지 + Run 직렬화 / 하위호환. API layer 에서
POST 가 PENDING_APPROVAL Run 반환 + delivery 호출 안 함 (승인 전 발송 차단).

---

## 4. 운영 동작

```
사용자: Approval / Telegram 화면 진입
  ↓ ThreePushDraftCard 표시
  ↓ "PUSH-1 시장 흐름 브리핑 초안" 클릭
  ↓ POST /runs/generate    body: { input_data: { push_kind: "market_briefing" } }
  ↓ draft.generate_draft(input_data) — input_data.push_kind 로 분기
  ↓   ├─ build_ml_baseline_evidence_snapshot() (read-only, 재계산 X)
  ↓   ├─ compute_topn(...) (SQLite read-only)
  ↓   └─ draft.generate_market_briefing_draft(...)
  ↓       └─ build_market_briefing_message(...) → message_text
  ↓ Run(status=PENDING_APPROVAL, push_kind="market_briefing",
  ↓     message_text=...) 저장 + 응답.

사용자: 위 RunPanel 에서 message_text preview 확인
  ↓ "승인" 클릭
  ↓ POST /runs/{run_id}/approve
  ↓ 기존 approval 흐름 — Run.status = DELIVERING
  ↓ delivery.deliver(run)
  ↓   ├─ Run.message_text 그대로 사용 (단일 소스)
  ↓   ├─ handoff JSON 생성 + SCP → OCI inbox
  ↓   └─ archive_handoff_artifact()
  ↓ OCI consumer (deploy/oci/poc1_consume_inbox.sh):
  ↓   ├─ message_text 그대로 Telegram sendMessage
  ↓   └─ outbox 결과 기록
  ↓ local polling — Run.status = COMPLETED / FAILED

[기존 흐름과 동일 — 본 STEP 은 message_text 빌더만 추가]

PUSH-2 (holdings_briefing):
  Holdings 화면 → "초안 생성" → POST /runs/generate-from-holdings
  → generate_draft_from_holdings() (push_kind="holdings_briefing" 자동 부여)
  → 이후 동일 승인 → OCI → Telegram 경로.

PUSH-3 (spike_or_falling_alert):
  ThreePushDraftCard → "PUSH-3 급등락 관찰 신호 초안"
  → POST /runs/generate  body: { input_data: { push_kind: "spike_or_falling_alert" } }
  → 동일 흐름 (input_data 분기).
```

---

## 5. 이번 STEP 에서 의도적으로 하지 않은 것 (지시문 §12 / §13)

- 새 PUSH API 신설 / Telegram 직접 호출 / OCI 재구성 / Scheduler 도입.
- 신규 뉴스 source / 외부 source 추가 / CNN Fear & Greed 수집 / 원유·환율·미국
  선물 source.
- 매수·매도 판단 / 현금비중 조절 / 조정장 확정 / 위험 threshold 확정.
- AI Session payload 전체 전송.
- frontend 의 message_text 조립.
- **하루 3회 발송 시간 / 승인 UX / 자동 스케줄 발송 여부** — 지시문 §13 에서
  본 STEP 범위 밖 명시.

---

## 6. 검증 결과

- **backend pytest** — PASS (**490 passed**, +20 신규 / 회귀 0, FIX r2 후).
- **black --check / flake8** — PASS.
- **frontend ESLint / Next.js build** — PASS.
- **live API 실측 (FIX r2 후)** — TestClient + 운영 SQLite:
  - POST `/runs/generate` body `{input_data: {push_kind: "market_briefing"}}`
    → HTTP 200 / `status=PENDING_APPROVAL` / `push_kind=market_briefing` /
    message_text 496자. ML baseline 위험 패턴 + 외부 변수 체크리스트 7건 정상.
  - POST `/runs/generate` body `{input_data: {push_kind: "spike_or_falling_
    alert"}}` → HTTP 200 / `push_kind=spike_or_falling_alert` / message_text
    213자. 표시 하한 이상 spike 없음 자연 노출.
  - POST `/runs/generate-market-briefing` / `/runs/generate-spike-alert` →
    HTTP 405 (제거 확인). 별도 PUSH endpoint 0건 직접 검증.
- **delivery 격리** (AC-11) — test_post_endpoints_do_not_trigger_telegram_send
  이 `app.delivery.deliver` 를 `_boom` 으로 patch 한 상태에서 POST 가 정상
  PENDING_APPROVAL 반환 — 승인 전 발송 0건 직접 보장.

---

## 7. KS-10 자체 점검

신규 / 수정 파일의 라인수 실측 (`wc -l`):

| 파일 | 라인 | 임계 | 분류 |
| --- | --- | --- | --- |
| `app/message_market_briefing.py` | **184** | 600 / 650 | 안전 |
| `app/message_spike_alert.py` | **212 (FIX r2 후)** | 600 / 650 | 안전 |
| `app/draft.py` | **465 (FIX r3 후, 623 → 465)** | 600 / 650 | 안전 (분리로 복귀) |
| `app/draft_three_push.py` | **207 (FIX r3 신규)** | 600 / 650 | 안전 |
| `app/api.py` | **548** | 600 / 650 | 안전 (수정) |
| `frontend/app/components/ThreePushDraftCard.tsx` | **107** | 850 / 900 | 안전 |
| `tests/test_three_push_contract.py` | **476 (FIX r2 후)** | n/a (tests) | 안전 |

`app/api_three_push.py` 는 FIX r2 에서 **삭제됨** (별도 PUSH endpoint 신설 금지선
준수). draft.py 의 PUSH 본문은 FIX r3 에서 `app/draft_three_push.py` 로 **분리**
(KS-10 책임 집중 해소).

KS-10 trigger/near 0건. api.py 가 본 STEP 추가 중 627 라인까지 도달했으나
3-PUSH 본문을 api_three_push.py 로 즉시 분리해 548 로 복귀 — 1 책임 1 파일
원칙 + KS-10 안전 영역 유지.

---

## 8. 결과 해석 (참고용, 사용자 판단 영역)

- 본 STEP 은 **계약과 빌더 정렬** 이지 운영 UX 정렬이 아니다. 사용자가 "하루
  3회 자동 발송" / "사용자가 트리거" / "특정 시간만" 어느 쪽을 원하는지는 별도
  STEP 에서 확정.
- 3종 builder 가 동일 패턴 (read-only 입력 → message_text + push_kind 표시 →
  PENDING_APPROVAL Run) 을 따르므로, 향후 PUSH 종류가 늘어나도 동일 패턴 확장
  가능.
- PUSH-1 의 뉴스 섹션을 비워두는 정책은 "보여주기식 unavailable 문구 금지"
  (§4.2) 와 정합. 뉴스 source 도입 시 빈 섹션이 자연스럽게 채워지도록 builder
  구조 유지.
- delivery 의 push_kind 가드는 운영 안전망 — 신규 run 은 generate 시점에
  message_text 가 항상 박혀있으므로 정상 흐름에서 트리거되지 않음. 결함 상태
  (e.g. 직접 DB 조작 후 deliver) 에서 raw recommendations 발송 차단.

---

## 9. 다음 분기 후보 (사용자 결정 영역)

1. **하루 3회 발송 시간 + 승인 UX 확정** — 지시문 §13 에서 본 STEP 범위 밖.
   자동 스케줄 vs 수동 트리거 vs hybrid.
2. **PUSH-1 뉴스 source 도입** — 본 STEP 은 뉴스 섹션 생략. 외부 source
   (Naver / RSS / 다른 source) 추가 시 별도 STEP.
3. **PUSH-3 개별 주식 universe 확장** — 본 STEP 은 ETF universe 만. 개별 주식
   급등락 source 도입 여부 별도 STEP.
4. **ThreePushDraftCard 정식 화면 위치** — 현재 ApprovalTelegramView 안 임시
   위치. UX 결정 후 정식 메뉴 위치 확정.

본 문서는 다음 STEP 을 임의 확정하지 않는다.
