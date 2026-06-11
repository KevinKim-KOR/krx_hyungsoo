# POC2 — ML Baseline Evidence Draft Integration CONCLUSION

작성: 2026-06-11
성격: Step 완료 보고. canonical 상태 (`docs/STATE_LATEST.md`) 의 detail 링크.

---

## 0. 한 줄 요약

이미 생성된 ML baseline v0 룩백 검증 결과를 `GenerateDraft` / `AI Sessions`
draft 의 **보조 evidence** 로 연결. baseline 재계산 / feature 재생성 / 외부
source 호출 / ML 학습 / HTTP self-call 0건. 매수/매도/추천/현금비중/조정장/
위험 알림 문구 0건. report 부재 / 손상 / stale 도 draft 생성을 실패시키지
않음 (조용히 빠지지 않고 status 명시).

사용자 결정 (a)+(a)+(a): JSON 파일 직접 read / stale 기준 7일 / draft_message
[판단 사유] bullet 위치.

실측: 운영 SQLite 기준 status=ok / candidate evaluated_days=40 / risk
evaluated_days=40 / leakage 0 / external context checklist 7건 노출.

---

## 1. AC 달성 현황

```text
AC-1  ML baseline report 읽기 (재계산 / feature 생성 / 외부 호출 X)        = DONE
AC-2  AI Sessions draft payload 에 ml_baseline_evidence_snapshot 저장      = DONE (FIX r2 + r3 데이터 계약 단일화)
AC-3  candidate evidence 반영 (매수/추천/교체 문구 0건)                    = DONE
AC-4  risk evidence 반영 (조정장 확정 / 현금비중 / 위험 알림 0건)          = DONE
AC-5  leakage / 한계 표시 (evaluated_days / report_status / leakage / 한계) = DONE
AC-6  AI 외부 context checklist 7건 포함 (외부 source 수집 0건)             = DONE
AC-7  report 부재 / stale 처리 (draft 실패 X, status 명시)                  = DONE
AC-8  기존 evidence (Market Discovery / Holdings / NAV) 유지                = DONE
AC-9  기존 흐름 (GenerateDraft / AI Sessions / Approval / Telegram) 유지   = DONE
AC-10 범위 위반 0건 (ML 재실행 / UI 버튼 / PUSH / OCI / Telegram 변경 X)   = DONE
AC-11 문서 갱신 (STATE / NEXT_ACTIONS / FEATURE_INVENTORY + 본 파일)        = DONE
```

---

## 2. 변경 파일 (구조)

**Backend 신규 (1)**:
- `app/ml_baseline_evidence.py` **452 라인** — report loader (`state/ml/
  ml_baseline_v0_report_latest.json` 직접 read) + snapshot builder + bullet
  builder + factor_signal builder + renderer. stale 기준 `feature_asof_range.
  end` 7일 초과. KS-10 안전 (임계 600/650).

**Backend 수정 (4)**:
- `app/draft.py` — `generate_draft_from_holdings` 흐름의 `_build_holdings_
  payload` 에서 evidence snapshot + factor_signal 추가. draft_payload 신규 키
  `ml_baseline_evidence_snapshot` 1건 + factor_signals 신규 scope
  `ml_baseline_evidence` entry 1건.
- `app/draft_message.py` — `_render_judgment_lines` 가 holdings briefing /
  holdings market evidence 직후 `render_ml_baseline_evidence_bullet` 호출.
  [판단 사유] 섹션에 "ML baseline 룩백 evidence" 1줄 추가.
- `app/decision_evidence_store.py` (FIX r2) — `ai_session_records` 테이블에
  `ml_baseline_evidence_snapshot_json` 컬럼 추가 + `_migrate_add_ml_baseline_
  evidence_snapshot` 자동 ADD COLUMN. `insert_record` / `_SELECT_COLS` /
  `_row_to_full_dict` 갱신.
- `app/api_decision_sessions.py` (FIX r2) — `CreateDecisionSessionRequest` /
  `DecisionSessionDetail` Pydantic 모델에 `ml_baseline_evidence_snapshot` 필드
  추가 + POST/GET 핸들러 전달.
- `app/api_ml_baseline.py` (FIX r3) — `GET /ml/baseline-v0/evidence-snapshot`
  신규 endpoint + `MlBaselineEvidenceSnapshotResponse` Pydantic 모델. read-only
  (재계산 / 외부 호출 X). `build_ml_baseline_evidence_snapshot()` 결과를 그대로
  반환 — GenerateDraft 와 동일한 정규화 shape 보장.

**Frontend 수정 (3, FIX r2)**:
- `frontend/lib/aiSessionsDraft.ts` — `AISessionsDraft` 인터페이스에
  `ml_baseline_evidence_snapshot?` 필드 추가.
- `frontend/lib/api/decisionSessions.ts` — `CreateDecisionSessionRequest` /
  `DecisionSessionDetail` 타입에 동일 필드 추가.
- `frontend/lib/api/mlBaselineV0.ts` (FIX r3) — `MlBaselineEvidenceSnapshot`
  타입 + `fetchMlBaselineEvidenceSnapshot()` 추가 (GenerateDraft 동일 shape).
- `frontend/app/components/AISessionsCreateTab.tsx` (FIX r3) —
  `fetchMlBaselineEvidenceSnapshot` 사용으로 교체. 저장 시점에 draft 에
  snapshot 없으면 본 API 결과를 그대로 payload 에 담음. fetch 실패 시에도
  status="error" 정규화 snapshot 으로 채워 silent fallback 제거 (§4.7).

**Tests 신규 (1)**:
- `tests/test_ml_baseline_evidence.py` **499 라인 (FIX r3 후)** — 19 테스트 (snapshot 5종
  status / bullet 금지 문구 검증 / factor_signal / draft 통합 / 기본 경로 +
  FIX r2: AI Sessions / Decision Evidence 통합 2건).

**Tests 수정 (1, FIX r2)**:
- `tests/test_decision_evidence_store.py` — 신규 컬럼 마이그레이션 + insert/
  get 통합 3건 추가 (`test_insert_record_with_ml_baseline_evidence_snapshot`
  / `test_ml_baseline_evidence_column_present_after_migration` / `test_legacy_
  db_migrates_ml_baseline_evidence_column`) + 기존 closeout snapshot 테스트의
  defaults 검사에 ml 필드 1줄 추가.

**Tests 수정 (1)**:
- `tests/test_universe_seed.py` — `test_step5c_endpoint_does_not_affect_
  holdings_draft_flow` 의 (a) "universe" substring 검사 → "신규 ETF 관찰 후보"
  라벨 부재 검사로 좁힘 (ML evidence bullet 본문에 "universe median" 비교 문구가
  들어가서 단순 substring 검사 부적합). (b) `expected_keys` 에 `ml_baseline_
  evidence_snapshot` 추가.

**Docs 수정 (3)** + **신규 (1)**:
- `docs/STATE_LATEST.md` / `docs/handoff/POC2_B_NEXT_ACTIONS.md` /
  `docs/handoff/POC2_FEATURE_INVENTORY.md`.
- `docs/handoff/POC2_ML_BASELINE_EVIDENCE_DRAFT_INTEGRATION_CONCLUSION.md` —
  본 파일.

---

## 3. 핵심 설계 결정 (사용자 확정)

### 3.1 report 읽기 — (a) JSON 파일 직접

`state/ml/ml_baseline_v0_report_latest.json` 을 `Path.read_text` + `json.loads`
로 직접 파싱. HTTP self-call 사용 안 함 → 외부 호출 0건 / import 결합 최소.

### 3.2 stale 기준 — (a) feature_asof_range.end 7일 초과

오늘(KST) 대비 `feature_asof_range.end` 가 `STALE_DAYS_THRESHOLD=7` 일 초과면
status=stale. CLI 미실행 시점에 자동 표면화 (조용히 빠지지 않음).

### 3.3 draft 문구 위치 — (a) draft_message [판단 사유] bullet

`_render_judgment_lines` 에 1줄 추가. 기존 holdings briefing → holdings market
evidence → ML baseline evidence → 신규 ETF 관찰 후보 → 급락 ETF 주의 신호 순서.
[판단 사유] 헤더 중복 금지 (기존 정책 유지).

---

## 4. 운영 동작

```
사용자: 좌측 메뉴 Holdings → "초안 생성" 클릭
  ↓ POST /runs/generate-from-holdings
  ↓ generate_draft_from_holdings(holdings, market_quotes)
  ↓ _build_holdings_payload(...)
  ↓   ├─ recommendations / momentum_result / holdings_market_evidence_snapshot
  ↓   ├─ factor_signals (portfolio / universe / falling / holdings_market_evidence)
  ↓   └─ ★ build_ml_baseline_evidence_snapshot()  ← 본 STEP
  ↓        ├─ load state/ml/ml_baseline_v0_report_latest.json (read-only)
  ↓        ├─ status 결정 (ok / warn / stale / unavailable / error)
  ↓        ├─ candidate_summary / risk_summary / leakage_summary / limitations
  ↓        └─ external_context_checklist (7건)
  ↓   + factor_signals 에 scope="ml_baseline_evidence" entry 1건 추가
  ↓ draft_message.build_message_text(payload)
  ↓   └─ [판단 사유] 섹션에 "ML baseline 룩백 evidence: ..." 1줄 추가
  ↓ store.save(Run)
  → 사용자: GenerateDraft 결과 → AI Sessions / Approval → Telegram

CLI:
  $ python scripts/run_ml_baseline_v0.py  (기존 — 이번 STEP 추가 없음)
  → state/ml/ml_baseline_v0_report_latest.json 갱신
  → 다음 draft 생성 시점에 자동 반영
```

---

## 5. 이번 STEP 에서 의도적으로 하지 않은 것 (지시문 §7)

- ML baseline 재계산 / feature 재생성 / sanity 재실행.
- UI 실행 버튼 추가 / 화면 진입점 추가.
- PUSH 구현 / OCI 연결 / Telegram 문구 변경.
- 외부 source 추가 (CNN Fear & Greed / VKOSPI / 원유 / 환율 / 미국 선물 모두 0건).
- 매수 / 매도 판단 / 현금비중 조절 / 조정장 확정 라벨 / 위험 threshold 확정.
- 학습형 ML 모델 추가.

---

## 6. 검증 결과

- **backend pytest** — PASS (**454 passed**, +22 신규 / 회귀 1건 → 테스트 가정
  갱신으로 해결). FIX r3 후 신규 테스트: ml_baseline_evidence 19건 (FIX r3 의
  evidence-snapshot API ok/unavailable 포함) + decision store 3건. 기존
  `test_step5c_endpoint_does_not_affect_holdings_draft_flow` 의 universe
  substring 검사 / expected_keys 두 가정이 본 STEP 의 정당한 변경 (ML evidence
  bullet 본문 + draft_payload 신규 키) 으로 인해 갱신됨.
- **black --check** — 본 STEP 변경 파일 PASS (사전 존재 `scripts/diagnose_
  constituents_source.py` 1건은 본 STEP 무관).
- **flake8** — PASS.
- **frontend Next.js build** — PASS (frontend 변경 0건).
- **CLI live 실측** (운영 SQLite):
  - status=ok / report_status=ok.
  - candidate.evaluated_days=40 / risk.evaluated_days=40.
  - leakage: future_data_leakage_detected=False / tail_excluded=True /
    time_order_preserved=True.
  - external_context_checklist=7건 (CNN Fear&Greed / VIX·VKOSPI / 원유 /
    USD-KRW / 미국장·선물 / 지정학 / 한국장 영향 업종).
- **외부 source 호출 0건** — `build_ml_baseline_evidence_snapshot` 은 파일
  read 만 수행. `test_draft_does_not_fail_when_report_missing` 가 monkeypatch
  로 report 부재 → status=unavailable 분기 확인.

---

## 7. KS-10 자체 점검

신규 / 수정 파일의 라인수 실측 (`wc -l`):

| 파일 | 라인 | 임계 | 분류 |
| --- | --- | --- | --- |
| `app/ml_baseline_evidence.py` | **452** | 600 / 650 | 안전 |
| `app/draft.py` | **431** | 600 / 650 | 안전 (수정) |
| `app/draft_message.py` | **585** | 600 / 650 | near 미진입 (수정) |
| `app/decision_evidence_store.py` (FIX r2) | **543** | 600 / 650 | 안전 (수정) |
| `app/api_decision_sessions.py` (FIX r2) | **235** | 600 / 650 | 안전 (수정) |
| `app/api_ml_baseline.py` (FIX r3) | **113** | 600 / 650 | 안전 (수정) |
| `tests/test_ml_baseline_evidence.py` | **499 (FIX r3 후)** | n/a (tests) | 안전 |

KS-10 trigger/near 0건. 신규 모듈 분리로 draft.py / draft_message.py 라인 폭증
회피.

---

## 8. 결과 해석 (참고용, 사용자 판단 영역)

- ML baseline evidence 는 **판단 결론이 아니라 evidence**. AI 와 사용자가 판단할
  때 참고하는 보조 근거다.
- candidate baseline 의 top group future return 은 universe median 대비 의미
  있는 차이가 있었지만 evaluated_days=40 으로 짧다. 본 STEP 은 이 한계를
  `limitations` 필드와 [판단 사유] bullet 본문에 명시 노출한다.
- AI 가 별도로 확인해야 할 외부 context (Fear&Greed / VKOSPI / 원유 / 환율 /
  미국장 / 지정학 / 업종) 는 `external_context_checklist` 7건으로 질문 목록만
  전달. 외부 source 수집 구현은 0건 — 본 STEP 범위 밖.
- report 가 7일 초과 stale 이면 status=stale 로 자동 표면화. 사용자가 CLI 재실행
  결정.

---

## 9. 다음 분기 후보 (사용자 결정 영역)

1. **report stale 시 CLI 재실행 안내 UI** — Data Status 카드 옆 안내 배지.
2. **5년 backfill 후 evidence 신호 강도 시계열 분해** — rolling window 평가.
3. **§6.6 제외 source** (CNN Fear&Greed / VKOSPI / 외국인·기관 수급 등) — BACKLOG.
4. **AI Sessions UI 에 evidence snapshot 시각화** — 현재는 payload 안에만 저장.

본 문서는 다음 STEP 을 임의 확정하지 않는다.
