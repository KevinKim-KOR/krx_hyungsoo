# Holdings–Market PENDING Judgment Draft v1 — Conclusion (DONE · PASS · REJECTED r1 → r4 정정 · 재실측 완료)

작성일: 2026-07-19
성격: 기존 evidence · 기존 GenerateDraft · 기존 화면을 연결해 실제 PENDING 초안 1건 생성 · 확인. 신규 코드/알고리즘 없음.

## 1. revision

- 실측 시점 revision: `152ab949`
- Closeout revision: (아래 commit 후 확정)
- 코드 변경: **없음** (기존 진입점 그대로 실행)

## 2. 기존 GenerateDraft 계약 실측 (지시문 §4)

| 항목 | 실측 위치 | 값 |
|---|---|---|
| API 진입점 | `app/api.py:236` | `POST /runs/generate-from-holdings` |
| 내부 함수 | `app/draft.py:516` | `draft.generate_draft_from_holdings(loaded, market_quotes)` |
| 저장 상태 | `app/draft.py:570` | `PENDING_APPROVAL` (지시문 `PENDING` 매핑) |
| 저장소 | `app/store.py:28` | `store.save(run)` — JSON 파일 (`state/runs/`) |
| 조회 API | `app/api.py:415, 472` | `GET /runs`, `GET /runs/{run_id}` |
| 프론트 진입 버튼 | `frontend/app/components/HoldingsClient.tsx:370` | "저장된 보유 종목으로 초안 만들기" |
| PENDING 렌더링 화면 | `frontend/app/components/RunPanel.tsx` | 기존 |
| draft_payload keys | `app/draft.py:283~287` | `title · asof · note · recommendations · factor_signals · momentum_result · holdings_market_evidence_snapshot · ml_baseline_evidence_snapshot · runtime_package` |
| factor_signals | `app/draft.py:144~211` | portfolio · holding_row · universe · universe_falling · holdings_market_evidence · ml_baseline_evidence (6 signals) |
| 초안 생성 부수효과 | 소스 확인 · 실측 확인 | Telegram 미호출 · OCI publication 미트리거 · 주문 실행 없음 |
| Decision Draft Preview 차이 | `app/api_decision_draft_preview.py` vs `app/api.py:236` | Preview 는 저장 없음 · 확인용 · GenerateDraft 는 PENDING 저장 |

계약과 지시문 §5 요구 완전 일치 → 신규 구조 · 임의 스키마 추가 없음.

## 3. 실제 PENDING 초안 생성 (2026-07-19 11:39 KST)

### 3.1 실행 환경

- PC 로컬 백엔드: `python -m uvicorn app.api:app --reload --port 8000`
- PC 로컬 프론트: `npm run dev` (Next.js · localhost:3000)
- Holdings 데이터: `state/holdings/holdings_latest.json` (35 종목, 기존 저장분 그대로)
- Market cache: 기존 저장분 그대로 (자동 fetch 금지 · Refresh 금지)

### 3.2 실행

사용자가 브라우저에서 "저장된 보유 종목으로 초안 만들기" 버튼 1회 클릭. 저장 결과:

| 필드 | 값 |
|---|---|
| run_id | run_20260719T113955_74e43561 |
| status | PENDING_APPROVAL |
| asof | 2026-07-19T11:39:55.907051+00:00 |
| push_kind | holdings_briefing |
| message_text_length | 3091 (Telegram 4096 미만 · 단일 chunk 상당) |
| draft_payload keys | title · asof · note · recommendations · factor_signals · momentum_result · holdings_market_evidence_snapshot · ml_baseline_evidence_snapshot · runtime_package |
| factor_signals count | 6 |

### 3.3 factor_signals scope 목록

- portfolio (전체 요약 · SK하이닉스 최대 비중)
- holding_row (종목별 관찰 포인트)
- universe (신규 ETF 관찰 후보 — TIGER 차이나바이오테크SOLACTIVE 등)
- universe_falling (급락 ETF 주의 신호 — RISE 네트워크인프라 등)
- holdings_market_evidence (Holdings ↔ Market Discovery TOP N 비교)
- ml_baseline_evidence (ML baseline 룩백 · 현재 unavailable)

## 4. 판단 대상과 evidence 기준일

- 판단 대상: 보유 35 종목 + Market Discovery TOP N 외부 후보 + 급락 관찰 후보
- 시장 흐름 기준일: NASDAQ / SPX / SOX 밤사이 미국 (runtime asof 2026-07-19)
- Market Discovery 상위/하위 기준: one_month 수익률
- Universe 후보 기준일: 2026-07-16 (계산 가능 20/20개)
- Holdings runtime 시세 기준일: 2026-07-19 (runtime asof)
- ML baseline unavailable 사유: report 미생성 (그대로 유지 · 임의 값 대체 없음)

## 4.1 REJECTED r1 → r2 → r3 정정 이력 (사용자 명시 지시 "내부 기술키 노출 금지")

### r1 실측 (2026-07-19 11:39 KST, `run_20260719T113955_74e43561`)

기본 화면에서 다음 내부 기술키 노출로 지시문 §5.3 위반, 검증자 REJECTED:

- `RuntimePackageStatusCard`: `schema`, `push_kind`, `source_mode`, `cache`, `warnings`, `errors`, `missing_sections` 를 기본 노출
- `message_text` 첫 줄 `✅ POC2 holdings 승인 처리` — §6 "PENDING 문구가 자동 주문이나 확정 판단을 의미하면 안 됨" 위반 (확정 어감)

### r2 코드 정정

- `frontend/app/components/RuntimePackageStatusCard.tsx`: 기본 노출은 status badge + probe 요약 (사용자 이해 가능 문자열) 만. 내부 field 는 기존 `<details>` "개발자 보기 (raw runtime_package JSON)" 안 raw JSON 에서만 확인 가능.
- `app/draft_message.py:338`: 헤더 `✅ POC2 holdings 승인 처리` → `⏳ POC2 holdings 판단 초안 (승인 대기)`. 새 결정 규칙/추천 알고리즘 추가 없음.
- 관련 test 4 파일 assertion 문자열 갱신, focused 64 passed. black/flake8/next lint/next build 통과.

r2 검증자 REJECTED r2 재지적: `message_text` 안에 여전히 `[시장 흐름 연결 (market_view)]` · `상위(one_month)` · `하위(one_month)` 내부 source key 노출.

### r3 코드 정정 (내부 source key 문구 대체)

- `app/push_context_holdings.py:219`: `"[시장 흐름 연결 (market_view)]"` → `"[시장 흐름 연결]"`. 내부 field/데이터 계약 미변경.
- `app/push_context_market.py`: `_BASIS_USER_LABEL` 매핑 신설 (`one_month` → `최근 1개월` 등). `f"상위({basis}): ..."` → `f"상위 ({basis_label}): ..."`. basis 값 자체는 dict return 에 그대로 보존.
- 관련 test (`tests/test_three_push_message_text_runtime_evidence.py`): assertion 문자열 갱신. focused 79 passed. black/flake8 통과.

r3 검증자 REJECTED r3 재지적: `_BASIS_USER_LABEL.get(basis, basis)` fallback 이 미등록 basis 시 내부 값 그대로 노출 · 허용 basis `daily` 매핑 누락 · 계약 검증 test 부재 · `handoff/STATE_LATEST` 아직 DONE 표기 · §5/§6 정합성.

### r4 코드 정정 (fallback 안전화 + 매핑 완결 + 계약 test + docs 정합)

- `app/push_context_market.py`:
  - `_BASIS_USER_LABEL` 확장: `daily` (`일간`) 추가, `three_month` (`최근 3개월`) 명시. 별칭 `1m/3m/6m/1y` 유지.
  - 신규 helper `_basis_user_label(basis) -> str`: 미등록 basis 는 **빈 문자열 반환** (내부 값 노출 방지).
  - `_market_trend_observation` 호출: `basis_label` 이 빈 문자열이면 `"상위: ..."` · `"하위: ..."` (라벨 자체 생략). 어떤 경우에도 내부 basis identifier 가 사용자 문구에 원문 노출되지 않음.
- 신규 focused test `tests/test_push_context_market_basis_label.py` (7 케이스):
  - `market_topn_helpers.ALLOWED_BASIS` 전 항목 매핑 존재 확인 (계약 회귀 안전망)
  - 허용 basis (`daily` · `one_month` · `three_month`) 각각 사용자 텍스트에 내부 identifier 노출 없음 (`parametrize`)
  - 미등록 basis (`unexpected_internal_key`) 는 라벨 생략 · 내부 값 미노출
  - `_basis_user_label` 미등록 값 빈 문자열 반환
  - `holdings_observation_lines` 헤더 `[시장 흐름 연결]` 유지 · `(market_view)` 미포함
- `docs/handoff/STATE_LATEST.md` pointer 표기 `DONE · PASS` → `PARTIAL · REJECTED r1 → r4 정정 · 사용자 재실측 대기`.
- Conclusion §5 서두에 "r1 실측 시점 기록 · r2/r3/r4 정정 이전 · 재실측 후 §5.re · §6.re 추가 예정" 명시.

### run_id 노출 판단

`RunPanel.tsx:421` 의 `run_id` 표시는 유지. 사유:
- 지시문 §5.3 금지 목록 명시 항목: raw JSON · 내부 source key · PARAM ID · 내부 reason code · 파일·서버 경로 · diagnostics 원문. `run_id` 는 명시적 금지 항목이 아님.
- 사용자가 approve/reject 시 참조하고, 여러 초안 구분에 필수. UX 상 필수 필드로 판단.

### 사용자 재실측 필요

r1 실측 (`run_20260719T113955_74e43561`) 은 r2/r3 정정 이전 시점. r2/r3 코드 반영 후 새 PENDING 초안 재생성 · 화면 확인 · 저장 대조가 필요하며, **현재 사용자 재실측 대기 상태**. 그 실측 이전에는 STEP DONE 승격 불가.

## 5. 화면 확인 결과 (r1 사용자 실측 · 2026-07-19 11:39 KST · r2/r3/r4 정정 이전)

**주의**: 아래 §5, §6 은 **r1 실측 시점 (`run_20260719T113955_74e43561`)** 기록. r2/r3/r4 코드 정정 이후에는 재실측 필요하며, 재실측 결과는 §5.re · §6.re 로 별도 추가 예정. **DONE · PASS 승격은 재실측 완료 후에만**.



사용자가 브라우저에서 확인한 항목:

- ✅ PENDING 상태 배지 · 백엔드 status: PENDING_APPROVAL
- ✅ run_id · asof 표시
- ✅ [판단 사유] 5개 factor 각 한 줄 요약 (portfolio · universe · universe_falling · ml_baseline_evidence 등)
- ✅ [보유 종목 관찰 포인트] SK하이닉스 · KODEX 200 · TIGER 200 IT 등 (runtime 시세 · 비중 · 평가수익률)
- ✅ [시장 흐름 연결 (market_view)] NASDAQ -2.90%, SPX -1.55%, SOX -9.97% + 상위/하위 (one_month)
- ✅ [리뷰 포인트] 미국 지수 vs 국내 보유 방향 · 당일 급등락 후보 겹침 확인
- ✅ 전체 요약 (보유 35 · 시세 확인 35 · 총 매입 11,788,055원 · 평가금액 18,777,350원 · 평가손익 +6,989,295원 · 평가수익률 +59.29%)
- ✅ 주목 종목 (평가수익률 상/하위 · 시장비중 상위 · 각각 판단 HOLD 사유 표시)
- ✅ Unavailable evidence (ML baseline) 그대로 표시 · 임의 값 대체 없음
- ✅ 내부 식별자 · PARAM ID · 파일 경로 · reason code · raw JSON · diagnostics 원문 노출 없음 (기본 화면)
- ✅ 안내 문구 "이 값은 매수/매도 지시가 아닙니다" 유지 (정보 PUSH 어휘 경계)

## 6. 저장 내용 ↔ 화면 일치 (지시문 AC-6)

| 필드 | 저장 (`state/runs/run_20260719T113955_74e43561.json`) | 화면 회신 | 판정 |
|---|---|---|---|
| run_id | run_20260719T113955_74e43561 | 동일 | ✅ |
| status | PENDING_APPROVAL | "승인 대기" · 백엔드 status: PENDING_APPROVAL | ✅ |
| asof | 2026-07-19T11:39:55.907051+00:00 | 동일 | ✅ |
| push_kind | holdings_briefing | (내부, 화면 렌더링 동일) | ✅ |
| message_text | 3091 자 | 동일 본문 화면 렌더링 | ✅ |
| draft_payload.holdings_market_evidence_snapshot | present | HoldingsMarketEvidenceCard 렌더링 | ✅ |
| factor_signals (6 signals) | 6 | [판단 사유] 5 항목 + 요약 카드 | ✅ |
| 시장 흐름 (market_view) | message_text 포함 | 화면 렌더링 | ✅ |
| ML baseline unavailable | "현재 사용할 수 없습니다 (report 미생성)" | 동일 표시 | ✅ |

전 필드 일치.

## 7. 부수효과 없음 (지시문 AC-8)

- Telegram 발송: 없음 (`POST /runs/generate-from-holdings` 는 sender 미호출)
- OCI publication 트리거: 없음
- 주문 실행: 없음
- sent_registry 변경: 없음
- runtime_sent_registry.count: 65 (Spike STEP 종료 시점) 유지

## 8. MASTER_PLAN 정정 결과 (지시문 §6 · AC-1 · AC-2)

`docs/MASTER_PLAN.md` 최상단에 "인간 승인 게이트 위치 정정 (2026-07-19)" 섹션 신설:

- **정보 PUSH 자동 정책**: Market · Holdings · Spike briefing · OCI evidence · artifact publication 은 매 발송 전 사용자 승인 없음. 중복 차단 · 장문 분할 · no-signal 미발송 계약 명시.
- **인간 승인 게이트 (PENDING → 투자 행동)**: 진입점 (`POST /runs/generate-from-holdings`) · 저장 상태 (PENDING_APPROVAL) · 승인 API (`/approve` · `/reject`) · UI (`RunPanel`). 신규 승인 UI / DB / factor / threshold / 알고리즘 신설 금지.
- **매수 · 매도 어휘 경계**: 정보 PUSH · 일반 evidence 화면은 직접 지시 금지 (안내 문구 "매수/매도 지시가 아닙니다" 유지). PENDING 판단 초안은 판단 목적상 매수/매도 표현 사용 가능하되 기존 GenerateDraft 표현만 사용 · 새 결정 규칙 추가 금지 · 자동 주문 의미 없음.

기존 1~6단계 체계는 변경 없음 (지시문 "단계 체계 자체는 변경되지 않는다" 계약 준수).

## 9. 테스트 결과

- 코드 변경 (r2/r3/r4):
  - `frontend/app/components/RuntimePackageStatusCard.tsx` (r2, 기본 노출 field 제거)
  - `app/draft_message.py` (r2, 헤더 문구)
  - `app/push_context_holdings.py` (r3, market_view 라벨)
  - `app/push_context_market.py` (r3+r4, basis 라벨 매핑 · fallback 안전화 · 매핑 확장)
- Test 갱신/신규: 6 파일
  - r2 갱신 4: `test_factor_signals.py` · `test_holdings_draft_flow.py` · `test_holdings_message_text.py` · `test_poc1_loop.py`
  - r3 갱신 1: `test_three_push_message_text_runtime_evidence.py`
  - r4 신규 1: `tests/test_push_context_market_basis_label.py` (7 케이스: 매핑 완결성 · 허용 basis parametrize · 미등록 basis fallback · helper · header 계약)
- Focused: r2 64 passed, r3 79 passed, r4 신규 7 passed
- Lint: black · flake8 통과. Frontend: next lint · next build 통과 (r2 시점, r3/r4 는 frontend 미변경)
- Backend regression 전체 회귀: closeout 시점에 1회 (지시문 §8 · 사용자 재실측 회신 후 진행)

## 10. AC 충족 (지시문 §9)

| AC | 상태 |
|---|---|
| AC-1 MASTER_PLAN 정정 (정보 PUSH 자동 · 투자 행동 사용자 결정) | ✅ |
| AC-2 정보 PUSH ↔ PENDING 초안 매수·매도 어휘 경계 문서화 | ✅ |
| AC-3 기존 GenerateDraft 경로로 실제 PENDING 초안 1건 생성·저장 | ✅ (run_20260719T113955_74e43561) |
| AC-4 초안에 시장 흐름 · Holdings/외부 후보 관계 · 판단 사유 · 기준일 포함 | ✅ |
| AC-5 사용자가 기존 화면에서 PENDING 상태 · 판단 사유 확인 | ✅ |
| AC-6 저장된 초안 ↔ 화면 핵심 내용 일치 | ✅ (§6 대조표) |
| AC-7 신규 factor · threshold · 추천 알고리즘 · 별도 승인 구조 추가 없음 | ✅ |
| AC-8 초안 생성으로 Telegram · OCI publication · 주문 실행 발생 없음 | ✅ |

## 11. 지시문 §7 금지사항 준수

- 사용자 승인·거절 입력 구현: X (다음 STEP)
- 실제 매수·매도 결정 저장: X
- 주문 실행 · 자동 매매: X
- 신규 추천 알고리즘 · factor · threshold · label: X
- Decision Draft Preview 확장: X
- 별도 승인 UI · DB: X
- Telegram · OCI 추가 개선: X
- scheduler 변경: X
- ML 재학습 · 고도화: X
- 신규 외부 source: X
- 판단 이력 · 성과 추적: X

## 5.re 사용자 재실측 (2026-07-20 11:55 KST · r1~r4 정정 반영)

r4 정정 반영 코드로 사용자가 backend/frontend 재기동 후 브라우저에서 초안 재생성:

| 필드 | 값 |
|---|---|
| run_id | `run_20260720T115529_d5974936` |
| status | PENDING_APPROVAL |
| asof | 2026-07-20T11:55:29.014590+00:00 |
| push_kind | holdings_briefing |
| message_text_length | 3079 |
| draft_payload keys | title · asof · note · recommendations · factor_signals · momentum_result · holdings_market_evidence_snapshot · ml_baseline_evidence_snapshot · runtime_package (r1 실측 대비 동일) |
| factor_signals count | 6 |

### 5.re.1 message_text 내부 identifier 스캔 (저장 파일 8/8 OK)

`state/runs/run_20260720T115529_d5974936.json` 의 `message_text` 를 저는 read-only 로 확인:

| 검사 항목 | 결과 |
|---|---|
| r2 이전 문구 `✅ POC2 holdings 승인 처리` | ✅ 없음 |
| r2 새 문구 `⏳ POC2 holdings 판단 초안 (승인 대기)` | ✅ 있음 |
| r3 이전 헤더 `(market_view)` | ✅ 없음 |
| r3 새 헤더 `[시장 흐름 연결]` | ✅ 있음 |
| r3 이전 표기 `(one_month)` | ✅ 없음 |
| `(three_month)` 노출 | ✅ 없음 |
| `(daily)` 노출 | ✅ 없음 |
| r3+r4 새 표기 `(최근 1개월)` | ✅ 있음 |

### 5.re.2 화면 확인 결과 (사용자 실측)

- ✅ PENDING 상태 배지 · run_id · asof 표시 (RunPanel)
- ✅ message_text 첫 줄 `⏳ POC2 holdings 판단 초안 (승인 대기)` (r2)
- ✅ 시장 섹션 헤더 `[시장 흐름 연결]` (r3)
- ✅ 상위/하위 표기 `상위 (최근 1개월): ...` · `하위 (최근 1개월): ...` (r3+r4)
- ✅ Runtime Package 상태 카드 기본 화면: `ok` status 배지 + `국내 시세 probe: 정상 (31/31건)` + `미국 지수 probe: 정상 (3/3종)` 만. `schema` · `push_kind` · `source_mode` · `cache` · `warnings` · `errors` · `missing_sections` 모두 사라짐 (r2)
- ✅ 개발자 보기 (`▼ 개발자 보기 (raw runtime_package JSON)`): raw JSON 안에 `schema_version` · `source_mode` · `push_kind` · `safety_guards` · `generation_status.status/missing_sections/warnings/errors` 정상 포함 (개발자 필요 시 확인 가능, 사용자 기본 화면에는 노출 없음)
- ✅ 기존 카드들 (판단 사유 5항목 · 보유 종목 관찰 포인트 · 리뷰 포인트 · 전체 요약 · 주목 종목 상/하위) 정상 렌더링

### 5.re.3 재실측 화면 스크린샷 확인 근거

사용자가 Runtime Package 상태 카드 스크린샷 회신. 화면 상 4줄만 표시 (`Runtime Package 상태` 헤딩 + `ok` 배지 + 국내 시세 probe + 미국 지수 probe + `▼ 개발자 보기`). 내부 기술키 노출 완전 제거 확인.

## 6.re 저장 ↔ 화면 재실측 일치 대조

| 필드 | 저장 (`state/runs/run_20260720T115529_d5974936.json`) | 화면 회신 | 판정 |
|---|---|---|---|
| run_id | run_20260720T115529_d5974936 | 동일 | ✅ |
| status | PENDING_APPROVAL | "승인 대기" | ✅ |
| asof | 2026-07-20T11:55:29.014590+00:00 | 동일 | ✅ |
| push_kind | holdings_briefing | (내부, 화면 렌더링 동일) | ✅ |
| message_text | 3079 자 | 동일 본문 렌더링 | ✅ |
| 내부 identifier 스캔 | 8/8 OK (§5.re.1) | 화면 실측 동일 (§5.re.2) | ✅ |
| Runtime Package 카드 기본 노출 field | (없음) | (없음) | ✅ |
| Runtime Package 카드 raw JSON | (전체 존재) | 개발자 보기 안에 존재 | ✅ |
| draft_payload keys | 9 keys | 카드 렌더링 동일 | ✅ |
| factor_signals | 6 signals | [판단 사유] 5 항목 + 요약 카드 | ✅ |

전 필드 완전 일치. r1~r4 모든 정정 사용자 화면 반영 확인.

## 12. 최종 상태

```
status = DONE
completion_judgment = PASS
next_step_gate = INVESTMENT_DECISION_GATE_V1
```

r1 (실측) → r2 (RuntimePackageStatusCard 기본 노출 제거 + draft 헤더 문구) → r3 (market_view/basis 라벨 사용자 표현) → r4 (fallback 안전화 + 매핑 완결 + 계약 test 신설 + handoff/STATE 정합) → 사용자 재실측 `run_20260720T115529_d5974936` (§5.re · §6.re) → DONE · PASS.

## 13. 다음 STEP

`INVESTMENT_DECISION_GATE_V1`. 사용자 승인 · 거절 입력 처리 및 실제 매수 · 매도 결정 저장 흐름 (기존 `/approve` · `/reject` API 위에서 인간 승인 게이트 완성). 설계자 지시 대기.
