# POC2 Step 2D 종결 — Approval Draft Preview Separation

작성일: 2026-04-30
작성자: 개발자(VSCode Claude)
상태: 구현 + 자동 검증 게이트 통과 (black/flake8/pytest 82 passed/frontend lint+build). Codex 검증 1라운드 REJECTED (raw_json_not_exposed 위반) → 비-holdings 샘플 분기를 정적 안내 + 기본 접힘 details 로 수정 후 완료 처리. 운영 E2E (preview ↔ Telegram 발송문 시각 비교) 는 다음 사용자 실행 시점.
대상 독자: 다음 챕터 진입자

---

## 1. 단계 목적 (한 줄)

`초안 본문` 영역을 실제 전송될 메시지 미리보기 영역으로 정리한다. 백엔드가 generate 시점에 빌드한 message_text 를 단일 소스로 삼아 preview / OCI handoff / Telegram 발송 모두 동일 문자열을 사용하게 만든다.

---

## 2. 사용자(설계자) 결정 사항 반영

| Q | 결정 | 적용 위치 |
|---|---|---|
| message_text 저장 방식 | 해석 (A) — 초안 생성 시점에 백엔드가 빌드 → Run top-level optional 필드에 저장 → API 응답·OCI handoff·Telegram 모두 동일 소스 | `app/draft.py` / `app/models.py` / `app/api.py` / `app/delivery.py` |
| Run.message_text 추가 vs "스키마 변경 금지" | 허용 — top-level optional metadata 추가는 핵심 데이터 스키마(상태 모델·holdings·draft_payload·market_cache·OCI/Telegram 경로) 변경이 아니다 | `app/models.py::Run` |
| 과거 state/runs/*.json 의 message_text 누락 | Run.from_dict 가 None 으로 fallback. 강제 마이그레이션 안 함 | `app/models.py::Run.from_dict` |
| 프론트의 message_text 처리 | opaque string 으로 받아 그대로 렌더. 조립/파싱 금지 | `frontend/app/components/RunPanel.tsx::MessagePreview` |
| 과거 run UI fallback | 정적 안내 문구(LegacyFallback) + 근거 데이터 기본 펼침 | `RunPanel::ApprovalDraftBody` |
| 비-holdings(샘플) 분기의 raw JSON | 1차 보고에서 "유지" 로 보류했으나 Codex 지적 수용 — 정적 안내 + 기본 접힘 details 로 이동 | `RunPanel::ApprovalDraftBody` 비-holdings 분기 |
| Telegram message compaction | 변경 없음 — Step 2B 정책 그대로 유지 | `app/draft_message.py` 미수정 |

---

## 3. message_text 단일 소스 보장 흐름 (Step 2D 핵심)

```
[generate]
  draft.generate_draft / generate_draft_from_holdings
    → draft_message.build_message_text(run_id, payload)
    → Run.message_text 에 저장
    → store.save(run)              ← state/runs/{run_id}.json 에 top-level message_text 키 영속화

[조회]
  GET /runs/{run_id}
    → store.load(run_id)
    → RunResponse.from_run → message_text 를 응답에 그대로 포함
    → 프론트는 opaque string 으로 받아 <pre> 안에 그대로 렌더 (preview)

[승인]
  POST /runs/{run_id}/approve → DELIVERING 전환 → BackgroundTasks(_execute_delivery)
    → delivery.deliver(run)
    → message_text = run.message_text       ← 신규 run 은 이 단계에서 builder 재호출 없음
    → store.write_handoff_artifact(run, approved_at, message_text)
    → SCP → OCI inbox

[OCI 발송]
  poc1_consume_inbox.sh 가 inbox/{run_id}.json 의 top-level message_text 를 그대로 Telegram 으로 발송
```

핵심:
- preview / handoff / Telegram 의 message_text 는 **모두 generate 시점의 build_message_text 결과 1개 인스턴스를 공유**.
- 신규 run 에서는 절대 builder 가 재호출되지 않는다. 테스트 `test_step2d_delivery_uses_stored_message_text` 가 spy 로 검증.
- 과거 run (Run.message_text=None + holdings draft) 만 delivery.deliver 안에서 builder fallback 1회 호출 — legacy 호환.

---

## 4. UI 구조 (Step 2D 재편)

### 4.1 분기 4가지 (RunPanel::ApprovalDraftBody)

```
1. 빈 payload
   → "초안 본문이 없습니다" 안내만

2. 비-holdings(샘플 등)
   → LegacyFallback 정적 안내
   → note (있으면)
   → <details closed> 근거 데이터 펼쳐보기 (raw recommendations)
   - raw JSON 은 기본 접힘 안에서만 노출 (Step2D AC13)

3. holdings + message_text 있음 (신규 run)
   → MessagePreview (백엔드 원본 message_text 그대로 <pre>)
   → note (있으면)
   → OverallSummaryCard (전체 요약 기본 노출)
   → <details closed> 근거 데이터 펼쳐보기
       ├ AccountSummaryCards (계좌별 요약)
       └ CompactHoldingsTableStandalone (compact table + 행별 펼침)

4. holdings + message_text 없음 (legacy run)
   → LegacyFallback 정적 안내
   → note (있으면)
   → OverallSummaryCard (전체 요약 기본 노출)
   → <details open> 근거 데이터 펼쳐보기  (기본 펼침으로 사용자가 내용 확인 가능)
       ├ AccountSummaryCards
       └ CompactHoldingsTableStandalone
```

### 4.2 raw JSON 정책
- 어떤 분기에서도 기본 화면에 raw JSON 이 노출되지 않는다.
- 비-holdings 분기의 raw 표시는 기본 접힘 `<details>` 안으로만 노출.

### 4.3 message_text 렌더 정책
- 프론트엔드는 조립/파싱하지 않는다.
- `<pre className="preview-body">{messageText}</pre>` 로 줄바꿈/공백/이모지 그대로 출력.
- preview 와 Telegram 클라이언트의 줄바꿈/이모지 폭 미세 차이는 BACKLOG (Step 2D deferred 4번).

---

## 5. 변경 / 신규 파일

수정 (9건, git tracked, 모두 modified):
- `app/api.py` — `RunResponse.message_text: Optional[str]` 필드 + `from_run` 매핑
- `app/delivery.py` — handoff 흐름이 `Run.message_text` 우선 사용, 누락(legacy) 시 builder fallback
- `app/draft.py` — `draft_message` import + generate 시점에 `build_message_text` 호출 후 Run 저장
- `app/models.py` — `Run.message_text: Optional[str] = None` 필드 + `from_dict` 누락 시 None fallback
- `tests/test_poc1_loop.py` — Step2D 신규 6건 + `_ORIGINAL_DELIVER` 모듈 top-level 캡처 (autouse stub 우회)
- `frontend/lib/api.ts` — `Run.message_text?: string | null` 타입
- `frontend/app/components/RunPanel.tsx` — `Recommendations` / `HoldingsCompactView` 제거 → `ApprovalDraftBody` / `MessagePreview` / `LegacyFallback` / `EvidenceDetails` / `CompactHoldingsTableStandalone` 신규. 비-holdings 분기 raw JSON 도 기본 접힘 details 로 이동
- `frontend/app/globals.css` — preview-block / evidence-details 스타일
- `docs/backlog/BACKLOG.md` — POC2 Step 2D deferred 4건 추가

신규 (이 문서 제외 추가 신규 파일 없음).

---

## 6. 검증 게이트 통과 기록

```
.venv/Scripts/black.exe --check app/ tests/   → exit 0 (16 files unchanged)
.venv/Scripts/flake8.exe  app/ tests/         → exit 0
.venv/Scripts/python.exe -m pytest tests/ -q  → 82 passed (Step2C 76 + Step2D 신규 6)
cd frontend && npm run lint                   → PASS
NEXT_PUBLIC_API_BASE=... npm run build        → PASS (4 static pages)
```

테스트 추가 항목 (6건):
- `test_step2d_generate_from_holdings_persists_message_text` — 신규 run 의 generate 응답 + GET 에 message_text 포함, 동일 문자열
- `test_step2d_generate_sample_no_message_text_for_non_holdings` — 비-holdings 초안은 message_text=None
- `test_step2d_legacy_run_without_message_text_loadable` — 과거 파일 키 누락 → from_dict None fallback
- `test_step2d_get_run_returns_none_message_text_for_legacy` — legacy run 의 GET 응답에 message_text=None 노출
- `test_step2d_delivery_uses_stored_message_text` — 신규 run delivery 가 builder 재호출 없이 저장값 사용
- `test_step2d_delivery_legacy_run_falls_back_to_builder` — legacy run 만 builder fallback 트리거

---

## 7. Codex 검증 결과 처리

1라운드: REJECTED — A-1 / A-4 / B-6: 비-holdings 샘플 분기에 `<code>{JSON.stringify(r)}</code>` 가 기본 노출 경로로 남아 raw_json_not_exposed:true 보고와 코드 불일치.
조치: `RunPanel.tsx::ApprovalDraftBody` 의 비-holdings 분기를 정적 안내(LegacyFallback) + 기본 접힘 `<details className="evidence-details">` 안으로 이동. 모든 분기에서 raw JSON 기본 미노출 보장. 백엔드 변경 없음.

B-2 / B-3 (RunPanel.tsx 비대화, 경미): 코드 변경 없이 BACKLOG "프론트 compact UI 공용 모듈 추출" 항목 트리거 조건과 동일 정책으로 관리. Step2D 종료 시점 RunPanel.tsx 가 약 750라인 — 600라인 트리거를 초과하므로 다음 변경 시점에 추출 STEP 우선 검토 권장.

---

## 8. 알려진 한계 / 미완성

- 운영 E2E 자연 검증 미수행 — preview 와 실제 Telegram 발송문 시각 비교는 다음 사용자 실행 시점.
- 근거 데이터 접힘 상태 / 비-holdings raw 접힘 상태 모두 컴포넌트 메모리만 유지 — F5 / 새 run 시 초기화 (BACKLOG).
- preview 와 Telegram 클라이언트의 줄바꿈·이모지 렌더 미세 차이 자동 검증 미도입 (BACKLOG).
- RunPanel.tsx 가 750라인을 넘어 BACKLOG "프론트 compact UI 공용 모듈 추출" 트리거(~600라인) 충족 — 다음 STEP 우선 검토 후보.

---

## 9. 다음 챕터 진입자에게

### 건드리지 말아야 할 것 (Step 2D 까지 확정 계약)
- 5 state 모델 / 4필드 draft_payload / handoff 5필드 (run_id/asof/approved_at/draft_payload/message_text)
- holdings 식별 규약 (recommendations 첫 항목에 quantity 또는 avg_buy_price)
- 외부 fetch 는 `POST /market/refresh` 단 1곳에서만
- draft_payload 메타 flag(`price_missing/calc_missing`) 추가 금지
- `_is_priced` ≠ `_is_calc_available` 분리. 평가 집계는 calc_available 만
- action 은 'HOLD' 고정. score 도입 금지
- Telegram 메시지 compaction 정책 (Step 2B). 종목별 매입 상세 추가 금지
- 메시지 split / snapshot / history / 전일 대비 변화 감지 도입 금지
- "실시간" 단어 사용 금지
- account_group 은 표시/그룹용 라벨. 계좌번호/세금/증권사 API 로 확장 금지
- React key 정책: source_index + ticker + account_group + avg_buy_price 4 요소 모두 포함
- 동일 ticker 분할매수(같은 account_group 다른 avg_buy_price) 허용
- **Step 2D 단일 소스 정책**: preview / OCI handoff / Telegram 모두 Run.message_text 1개 인스턴스 공유. 프론트엔드는 message_text 조립/파싱 금지. 신규 run 의 delivery 단계에서 build_message_text 재호출 금지
- raw JSON 은 어떤 분기에서도 기본 화면에 노출 금지

### 즉시 진행 가능한 후보
- (A) 운영 E2E 자연 검증 — 사용자 디바이스에서 18+ 종목 preview / Telegram 수신 형식 비교 결과
- (B) POC2-Step2A — pykrx EOD fallback (BACKLOG 트리거 충족 시)
- (C) ML 연결 / factor 추천 (Phase 1 격리 모듈 활용)
- (D) 프론트 compact UI 공용 모듈 추출 (RunPanel.tsx 750+ 라인 — 트리거 충족)

---

## 10. 한 줄 당부

POC2 Step 2D 의 핵심 — **preview 는 문자열을 만들지 않는다, 그저 백엔드가 만든 한 줄을 보여줄 뿐이다** — 를 깨지 말고 위에 쌓아라. preview 와 발송문이 다른 경로에서 만들어지는 순간, 사용자 신뢰의 가장 큰 축이 흔들린다.
