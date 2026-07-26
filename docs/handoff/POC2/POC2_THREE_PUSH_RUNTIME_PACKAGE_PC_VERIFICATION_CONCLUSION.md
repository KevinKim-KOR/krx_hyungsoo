# POC2 — 3-PUSH Runtime Package PC 검증 (Conclusion)

작성일: 2026-06-13
관련 commit: (이번 STEP)
기준 문서: [docs/handoff/THREE_PUSH_RUNTIME_PACKAGE_CONTRACT.md](THREE_PUSH_RUNTIME_PACKAGE_CONTRACT.md)
지시문: 개발자 최종 지시문 — 3-PUSH Runtime Package PC 검증 (2026-06-13)
사용자 결정 (Q1~Q5): docs 본문 참조 (질의 답변 — Clarification).

---

## 0. 한 줄 요약

PC 에서 `three_push_runtime_package.v1` 구조를 실제 evidence + runtime probe
(네이버 국내 시세 / Yahoo Finance 미국 지수 3종) 로 생성하고, Approval / Telegram
preview 에서 상태 확인 가능한 상태까지 검증 완료. PUSH-1 / PUSH-2 / PUSH-3 3종
모두 `draft_payload.runtime_package` 에 schema_version `three_push_runtime_package.v1`
구조가 저장되며 OCI handoff JSON 으로도 전달된다.

---

## 1. 범위 / 비범위 (지시문 §5)

### 1.1 범위 (구현 대상)

- `/runs/generate` + `input_data.push_kind` → runtime_package 생성 (PUSH-1/3).
- `/runs/generate-from-holdings` → runtime_package 생성 (PUSH-2, 기존 endpoint 유지 — Q3 사용자 결정).
- `draft_payload.runtime_package` 신규 키 1건 추가 (Q4 — 기존 키 유지).
- PC runtime source probe 2종:
  - **국내 시세**: Naver polling realtime quote endpoint.
  - **미국 지수 3종**: Nasdaq (^IXIC) / S&P 500 (^GSPC) / Philadelphia Semiconductor (^SOX) via Yahoo Finance chart endpoint.
- 30분 TTL cache (`state/runtime/three_push_runtime_probe_latest.json`).
- frontend `RuntimePackageStatusCard` — runtime_package 상태 요약 표시 + 빈 slot placeholder 금지.

### 1.2 비범위 (이번 STEP 외)

- OCI runtime 구현 / scheduler / 자동 발송 / 뉴스 source / 개별 주식 universe 확장 / 매수·매도·교체·비중 조절 / ML 산식 변경.

---

## 2. 사용자 결정 요약 (Q1~Q5)

| ID | 결정 | 적용 결과 |
| --- | --- | --- |
| Q1 | requests 기반 미국 지수 실제 probe (신규 dependency 금지), 실패 시 PARTIAL | `urllib` + cookie jar 기반 Yahoo Finance chart endpoint — 3종 모두 실제 조회 성공 |
| Q2 | Naver realtime quote probe 추가 (기존 dependency 범위) | `urllib` 기반 Naver polling endpoint — KODEX 200 / KODEX 코스닥150 실제 조회 성공 |
| Q3 | PUSH-2 는 기존 `/runs/generate-from-holdings` 유지 | PUSH-1/3 은 `/runs/generate + input_data.push_kind`, PUSH-2 는 기존 endpoint 그대로 — 신규 PUSH 전용 endpoint 0건 |
| Q4 | `draft_payload.runtime_package` 만 추가, 기존 키 유지 | `factor_signals` / `momentum_result` / `holdings_market_evidence_snapshot` / `ml_baseline_evidence_snapshot` / `recommendations` 모두 유지. `runtime_package` 1건 추가. |
| Q5 | cache read → miss/TTL 만료 시 probe (TTL 30분), refresh endpoint 0건 | `app/runtime_probe_cache.py` — 30분 TTL, 손상 시 fall-through 후 재조회. scheduler / 별도 endpoint 0건 |

---

## 3. 신규 파일

### 3.1 backend

| 파일 | 라인 수 | 책임 |
| --- | --- | --- |
| `app/runtime_us_indices_probe.py` | **171** | Yahoo Finance chart endpoint 로 Nasdaq / S&P 500 / SOX 3종 probe. cookie jar 단일 opener 캐시 (rate-limit 회피). |
| `app/runtime_kr_quote_probe.py` | **182** | Naver polling realtime quote endpoint 로 단일 종목/ETF 시세 probe. |
| `app/runtime_probe_cache.py` | **133** | `state/runtime/three_push_runtime_probe_latest.json` cache. TTL 30분. 손상 시 silent fall-through. 두 snapshot 모두 failed 시 cache 저장 건너뜀 (FIX r2 — B-6). |
| `app/runtime_package.py` | **292** | `three_push_runtime_package.v1` 빌더. push_kind 별 generation_status 산정. message_text 는 만들지 않음. holdings_briefing 검증에 market_view/market_discovery 확인 추가 (FIX r2 — A-1 (2)). unavailable runtime 도 warning 처리 + failed package 의 message_contract.message_text 빈 문자열 강제 (FIX r3 — A-1). |
| `app/push_context.py` | **247** | **FIX r2 신규** / FIX r3 보강. push_kind 별 `market_view` / `holdings_view` / `spike_view` 빌더. evidence + runtime → push_context → message_text 흐름의 중간 단계 (A-1 (1)). FIX r3 에서 observations/items 0건이면 빈 dict 반환 — 빈 view 가 "있는 것" 으로 오인되지 않게 함. |
| `tests/test_runtime_package.py` | **670** (FIX r6 후) | 22 신규 테스트 (AC-1 ~ AC-12 + push_context 흐름 + holdings_briefing 필수 evidence + unavailable 노출 + failed 시 message_contract 비움 + 빈 market_view + holdings 동기화 후에도 failed 본문 빈 문자열 유지 + Run.message_text 도 failed 시 None — PUSH-1 / PUSH-2 + delivery 가 failed package 의 holdings fallback 재생성을 DeliveryError 로 차단). |
| `tests/test_runtime_probe_cache.py` | **212** | 7 신규 테스트 (cache hit / miss / TTL / force_refresh / 손상 + both_failed_not_cached / partial_cached). |

### 3.2 frontend

| 파일 | 라인 수 | 책임 |
| --- | --- | --- |
| `frontend/app/components/RuntimePackageStatusCard.tsx` | **204** | `draft_payload.runtime_package` 상태 요약. status badge / generation_status / kr·us probe 요약 / raw JSON details. 빈 slot placeholder 노출 0건 (§14 — `kr.status==="unavailable"` 또는 `us.status==="unavailable"` 일 때 해당 row 자체 생략). |

---

## 4. 수정 파일

### 4.1 backend

| 파일 | 라인 수 변화 | 변경 내용 |
| --- | --- | --- |
| `app/draft.py` | 465 → **559** | `_build_holdings_payload` 가 holdings + benchmark ticker 로 runtime probe 호출 후 `push_context` 빌드 + `runtime_package` 신규 키 추가. `generate_draft_from_holdings` 가 Run 저장 직전에 message_contract.message_text 동기화. (FIX r2) `_runtime_snapshot_for_holdings` 의 broad exception 을 (OSError, TimeoutError) 로 좁힘. (FIX r4) 동기화 시점에 `runtime_package.generation_status.status == "failed"` 확인 후 failed 면 message_contract 본문 빈 문자열 유지. (FIX r5) failed 면 Run.message_text 도 None 으로 비움 — 실제 승인/preview/발송 단일 소스에서도 정상 본문 차단. |
| `app/draft_three_push.py` | 207 → **344** | PUSH-1/3 generate 함수가 cache-aware runtime probe → `build_push_context` → message builder (push_context 인자 전달) → `build_runtime_package` 흐름으로 정렬 (FIX r2 — A-1 (1)). `_runtime_snapshot_with_cache` helper 도 (OSError, TimeoutError) 만 흡수. (FIX r5) generate_market_briefing_draft / generate_spike_alert_draft 가 runtime_package 가 failed 이면 Run.message_text=None 으로 비움 (PUSH-2 와 대칭). |
| `app/delivery.py` | 233 → **251** | **FIX r6** — `deliver()` 의 holdings legacy fallback 분기에 `runtime_package.generation_status.status == "failed"` 사전 확인 가드 추가. failed package 면 fallback 진입 자체를 차단하고 `DeliveryError` 명시 raise (PUSH-1/3 의 기존 가드 패턴과 정렬). 이전 r1 ~ r5 에서는 0 변경이었음 — r6 에서 처음 수정. |
| `app/message_market_briefing.py` | 185 → **196** | (FIX r2) `build_market_briefing_message` 에 `push_context` 옵션 추가. push_context 가 주입되면 `overnight_us_lines` 헬퍼로 `[밤사이 미국 시장 (runtime probe)]` 1줄 섹션 추가 (probe ok 시에만). |
| `app/message_spike_alert.py` | 213 → **238** | (FIX r2) `build_spike_alert_message` 에 `push_context` 옵션 추가 + `_spike_view_section` 신규 — push_context.spike_view.items 의 1줄 요약. |
| `tests/conftest.py` | 119 → 162 | `_stub_runtime_probes` autouse fixture 추가 (모든 outbound HTTP 차단). |
| `tests/test_universe_seed.py` | 변경 | `expected_keys` 에 `"runtime_package"` 추가 (회귀 1건 해소). |

### 4.2 frontend

| 파일 | 변경 내용 |
| --- | --- |
| `frontend/app/components/RunPanel.tsx` | `RuntimePackageStatusCard` import + run 카드 아래 표시. |

---

## 5. PC runtime source probe 실측

### 5.1 미국 지수 3종 (Yahoo Finance chart endpoint)

- Endpoint: `https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d`
- 인증: 없음. `finance.yahoo.com` 홈 1회 priming 으로 cookie 받음 (rate-limit 회피).
- 실측 (2026-06-13 KST 오전):
  - **NASDAQ (^IXIC)**: close = 25,888.844, change_pct = +0.6979%, status = ok.
  - **SPX (^GSPC)**: close = 7,431.46, change_pct = +0.6463%, status = ok.
  - **SOX (^SOX)**: close = 13,371.47, change_pct = +9.416%, status = ok.
- Probe 시간: 개별 timeout 3초, 3종 합산 약 1초 (cookie 재사용).

> 검증 도중 cookie priming 없이 3초 timeout 만으로 호출 시 HTTP 429 (Too Many Requests) 가 발생함을 확인 — 모듈에 cookie jar 단일 opener 캐시 추가 후 안정 동작.

### 5.2 국내 시세 (Naver polling endpoint)

- Endpoint: `https://polling.finance.naver.com/api/realtime/domestic/stock/{ticker}`
- 인증: 없음. 기존 `app/naver_etf_universe_fetcher.py` 와 동일 dependency 범위.
- 실측 (2026-06-13 KST 오전):
  - **069500 KODEX 200**: price = 129,270 KRW, change_pct = +4.38%, status = ok.
  - **229200 KODEX 코스닥150**: price = 18,015 KRW, change_pct = +2.15%, status = ok.

### 5.3 신규 dependency

**0건**. `requirements.txt` 변경 없음. 모두 `urllib` + `json` + `http.cookiejar` (stdlib).

---

## 6. /runs/generate 통합 실측

### 6.1 PUSH-1 (market_briefing)

```text
POST /runs/generate {"input_data": {"push_kind": "market_briefing"}}
→ 200
   run_id = run_<stamp>_<hex>
   push_kind = "market_briefing"
   draft_payload.runtime_package.schema_version = "three_push_runtime_package.v1"
   generation_status.status = "ok"
   runtime_snapshot.kr_realtime_price_snapshot.status = "ok"
   runtime_snapshot.overnight_us_market_snapshot.status = "ok"
   message_text 길이 = 496 자
```

### 6.2 PUSH-3 (spike_or_falling_alert)

```text
POST /runs/generate {"input_data": {"push_kind": "spike_or_falling_alert"}}
→ 200
   push_kind = "spike_or_falling_alert"
   draft_payload.runtime_package.schema_version = "three_push_runtime_package.v1"
   generation_status.status = "ok"
   message_text 길이 = 213 자
```

### 6.3 PUSH-2 (holdings_briefing)

```text
POST /runs/generate-from-holdings
→ 200
   push_kind = "holdings_briefing"
   draft_payload.runtime_package.schema_version = "three_push_runtime_package.v1"
   generation_status.status = "ok"
   message_text 길이 = 2,507 자
   runtime_package.message_contract.message_text == Run.message_text (AC-6)
```

### 6.4 금지 substring 점검

3종 모두 다음 substring 0건:
`미국지수 unavailable`, `뉴스 unavailable`, `실시간 시세: unavailable`,
`raw_json`, `chat_id`, `token=`, `매수 후보`, `매도 후보`, `지금 매수`, `지금 매도`, `unavailable`.

---

## 7. AC 매핑 (지시문 §17)

| AC | 결과 | 근거 |
| --- | --- | --- |
| AC-1 runtime_package 생성 | PASS | 3종 push_kind 모두 `draft_payload.runtime_package.schema_version = "three_push_runtime_package.v1"` 확인. |
| AC-2 push_kind 별 package 생성 | PASS | PUSH-1/2/3 라이브 API 실측. |
| AC-3 PC evidence snapshot 포함 | PASS | `pc_evidence_snapshot` 6 키 모두 존재 (push_kind 별로 일부 빈 dict 허용). |
| AC-4 국내 runtime probe | PASS | KODEX 200 / KODEX 코스닥150 실제 조회 성공. |
| AC-5 미국 지수 runtime probe | PASS | Nasdaq / S&P 500 / SOX 실제 조회 성공. |
| AC-6 message_text = package 기반 | PASS (FIX r2) | message_text 생성 흐름을 `pc_evidence + runtime_snapshot → push_context → message builder` 로 정렬. PUSH-1 의 `[밤사이 미국 시장 (runtime probe)]` 1줄 섹션이 `push_context.market_view.observations.overnight_us` 가 채워질 때만 노출됨을 라이브 검증 (probe ok → 섹션 +60자 / probe failed → 섹션 0자) + 신규 단위 테스트 2건 (`test_message_text_contains_overnight_us_section_when_probe_ok` / `test_message_text_omits_overnight_us_section_when_probe_fails`). `runtime_package.message_contract.message_text == Run.message_text` 동일성도 유지. |
| AC-7 UI placeholder 방지 | PASS | `RuntimePackageStatusCard` 가 `status==="unavailable"` 일 때 해당 행 생략. message_text 에 `unavailable` substring 0건. |
| AC-8 handoff 포함 | PASS | `store.write_handoff_artifact` 가 `draft_payload` 전체를 그대로 저장 — `runtime_package` 자동 포함. 단위 테스트 검증. |
| AC-9 기존 delivery 흐름 유지 | PASS | PENDING_APPROVAL → DELIVERING → COMPLETED / FAILED 흐름 변경 0건. 4-state 흐름 유지. (FIX r6) `delivery.py` 의 holdings legacy fallback 분기에 failed package 가드 추가 — 기존 분기 로직은 유지하고 사전 차단 조건 1건 + DeliveryError 1건만 추가. PUSH-1/3 의 기존 가드와 정렬. |
| AC-10 기존 계산 기능 불변 | PASS | holdings / Market Discovery / ML baseline / NAV·괴리율 / universe momentum / data quality 산식 변경 0건. 기존 builder 결과 dict 를 그대로 evidence snapshot 에 넣음. |
| AC-11 실제 Telegram 발송 0 | PASS | 테스트는 `delivery.deliver` autouse stub. live 검증에서도 PENDING_APPROVAL 만 도달. |
| AC-12 금지 문구 0건 | PASS | 3종 message_text 라이브 검증 + 단위 테스트 prohibited substring 검사. |
| AC-13 문서 갱신 | PASS | STATE_LATEST / handoff STATE_LATEST / POC2_B_NEXT_ACTIONS / POC2_FEATURE_INVENTORY / 본 conclusion 모두 갱신. |
| AC-14 신규 PUSH 전용 endpoint 0건 | PASS | PUSH-1/3 은 `/runs/generate + input_data.push_kind`, PUSH-2 는 기존 `/runs/generate-from-holdings`. 신규 endpoint 0건. |

---

## 8. 안전 가드 결과 (safety_guards 고정 값)

```json
{
  "requires_pc_approval_for_test_send": true,
  "allow_unapproved_delivery": false,
  "frontend_may_build_message_text": false,
  "telegram_direct_call_from_pc": false,
  "oci_consumer_contract_required": true,
  "actual_send_allowed_in_tests": false
}
```

---

## 9. 검증 결과 (지시문 §18)

- backend tests: **519 passed** (이전 490 → 신규 +29, 회귀 0). 직전 STEP 종료 시점 490 passed → 본 STEP 1차 +16 → FIX r2 +5 → FIX r3 +4 → FIX r4 +1 → FIX r5 +2 → FIX r6 +1 = 519.
  - 신규 테스트 (FIX r6 후 실측): `tests/test_runtime_package.py` **22건** + `tests/test_runtime_probe_cache.py` **7건** = **29건**.
  - 기존 회귀 1건 (`test_step5c_endpoint_does_not_affect_holdings_draft_flow` 의 `expected_keys`) 은 `"runtime_package"` 키 추가에 따라 일치하도록 갱신.
- backend format / lint: **PASS** (`black --check` / `flake8` 0 warning).
- frontend lint: **PASS** (eslint 0 warning).
- frontend build: **PASS** (Next.js 15 production build).
- live API probe 실측: 본 문서 §5 / §6 참조.

---

## 10. 다음 STEP 후보 (사용자 결정 대기)

1. **OCI runtime source 도입** — PC 에서 검증한 source 가 OCI 네트워크에서도 작동하는지 확인 + outbox/Telegram 발송 분기 마이그레이션.
2. **하루 3회 발송 시간 + 자동 발송 UX** — scheduler / 발송 시각 / 자동 vs 수동 트리거 결정.
3. **runtime source 수동 refresh endpoint** — 사용자가 cache 를 즉시 갱신하고 싶을 때 사용 (cache TTL 만료 대기 불편 해소).
4. **뉴스 source 도입** — PUSH-1 의 [전일 기준 시장 흐름] 보강.
5. **runtime_package preview 화면 정식화** — 임시 진입점 `ThreePushDraftCard` 를 정식 화면 위치로 이동 + UX 통일.

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.
