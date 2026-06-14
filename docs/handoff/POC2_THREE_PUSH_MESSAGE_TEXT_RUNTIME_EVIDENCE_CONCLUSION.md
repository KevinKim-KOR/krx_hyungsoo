# POC2 — 3-PUSH Message Text Runtime Evidence 반영 (Conclusion)

작성일: 2026-06-14
관련 commit: (이번 STEP)
기준 문서: [docs/handoff/THREE_PUSH_RUNTIME_PACKAGE_CONTRACT.md](THREE_PUSH_RUNTIME_PACKAGE_CONTRACT.md)
지시문: 개발자 최종 지시문 — 3-PUSH Message Text Runtime Evidence 반영 (2026-06-14)

---

## 0. 한 줄 요약

직전 STEP (3-PUSH Runtime Package PC 검증, 2026-06-13) 에서 만들어진
`runtime_package` + `push_context` 의 실제 evidence (미국 지수 실제 등락률 /
Market Discovery 상위·하위 흐름 / ML baseline 룩백 / holdings × runtime quote /
universe momentum 후보) 를 PUSH-1 / PUSH-2 / PUSH-3 `message_text` 에 사람이
판단에 쓸 수 있는 수준으로 반영. 신규 source / 신규 dependency / 신규 endpoint /
OCI runtime / scheduler / 매수·매도·교체·현금비중·조정장·위험 threshold 0건.

---

## 1. 범위 / 비범위 (지시문 §5)

### 1.1 범위 (구현 대상)

- PUSH-1 message_text 에 NASDAQ / S&P 500 / SOX 실제 close + change_pct + 섹터
  해석 hint 노출.
- PUSH-1 에 Market Discovery 상위·하위 ETF 흐름 + ML baseline 룩백 evidence
  1줄씩 노출 (push_context 기반).
- PUSH-2 message_text 에 holdings 별 관찰 포인트 (runtime quote 변동률 / 비중 /
  Market Discovery overlap / 국내 기준선 안내) + market_view 연결 1줄 + 리뷰
  포인트.
- PUSH-3 message_text 에 universe momentum + Market Discovery candidates 의
  수익률 근거 / 방향 / data_quality / holdings overlap 4축 풍부 표시 (AC-5 —
  score 단독 표시 금지).
- runtime probe 가 일부 실패하면 성공한 항목만, 전부 실패하면 섹션 자체 생략
  (AC-7 — 빈 placeholder 금지).

### 1.2 비범위 (이번 STEP 외)

- 신규 runtime source / 뉴스 source / 개별 주식 universe.
- OCI runtime 구현 / scheduler / 자동 발송 / Telegram 직접 호출.
- 매수·매도·교체·비중조절·현금비중 판단 / 위험 threshold / 조정장 확정.
- ML 산식 / Market Discovery 산식 / NAV·괴리율 산식 / universe momentum 산식 변경.

---

## 2. 핵심 변경

### 2.1 push_context.py (변경 — 풍부화 + 헬퍼 4종 추가)

직전 STEP 의 push_context 는 observations 안에 `type` / `evidence_refs` 같은
키만 채우고 실제 값 / 사람이 읽는 텍스트는 비어있었다. 본 STEP 에서:

- `_market_trend_observation()` — Market Discovery candidates 의 상위·하위 3건
  씩 정렬 + 실제 등락률 문자열을 `text` 로 저장.
- `_overnight_us_observation()` — runtime probe 의 성공 indices 만 모아 실제
  close / change_pct + 섹터 해석 hint (`_US_SECTOR_HINTS`) 부여.
- `_risk_pattern_observation()` — ML baseline 의 high/low risk 10d drawdown
  값을 사람이 읽는 1줄로 변환.
- `_holdings_position_text()` — holdings position 1건 → runtime quote / 비중 /
  Market Discovery overlap / 국내 기준선 안내 우선순위 문장 (단순 ticker 노출은
  하지 않음 — AC-3 단순 목록 금지).
- `_universe_momentum_items()` — universe artifact 의 top / falling candidate
  추출.
- `build_spike_view()` — universe momentum item 에 더해 Market Discovery 의
  절대 수익률 상위 candidates (data_quality_flag / holdings_overlap 포함) 도
  spike_view.items 로 추가 — 단일 후보 3건만 노출하던 직전 STEP 대비 풍부화.

신규 message builder 용 헬퍼 5종:

- `overnight_us_lines()` — 직전 단순 "조회 가능 지수" 1줄에서 실제 등락률 다중
  행 + 섹터 해석 hint 로 확장 (AC-1).
- `market_trend_lines()` — Market Discovery 흐름 1줄 섹션 (AC-2).
- `risk_pattern_lines()` — ML baseline 룩백 1줄 섹션 (AC-2).
- `holdings_observation_lines()` — PUSH-2 [보유 종목 관찰 포인트] + [시장 흐름
  연결 (market_view)] + [리뷰 포인트] 다중 섹션 (AC-3 / AC-4).
- `spike_view_lines()` — PUSH-3 풍부 관찰 1줄/item (수익률 근거 / 방향 /
  data_quality / overlap 4축 — AC-5).

`_fmt_pct(value)` 계약 변경: 입력을 이미 % 단위로 본다 (`0.85 → "+0.85%"`).
ratio→% 자동 변환은 `_candidate_return_pct()` / `_risk_pattern_observation()`
내부에서 명시적으로 수행.

### 2.2 message_market_briefing.py (변경 — push_context 우선 + 섹션 3종 추가)

`build_market_briefing_message` body 가 다음 순서로 조립된다 (지시문 §7.2 — 단순
"조회 가능 지수" 금지):

1. `[밤사이 미국 시장 (runtime probe)]` — `overnight_us_lines(push_context)` —
   실제 close + change_pct + 섹터 해석 hint.
2. `[국내 시장 내부 신호 (Market Discovery)]` — `market_trend_lines(push_context)` —
   상위 / 하위 흐름 1줄 (AC-2).
3. `[시장 내부 신호]` — 기존 `_market_internal_section(topn_payload)` — 상세
   목록 (push_context 가 비어있어도 그대로 동작 — fallback).
4. `[위험 패턴 참고 (ML baseline 룩백)]` — `risk_pattern_lines(push_context)` —
   1줄 evidence (AC-2).
5. `[위험 패턴 참고]` — 기존 `_evidence_section(ml_baseline_snapshot)` — 상세.
6. `[추가 확인 필요 외부 변수]` — 기존 외부 checklist.
7. 중립 안내.

`_market_internal_section` 은 `compute_topn` 의 candidates / items 양쪽 호환
(`selected_return_pct` 우선, `return_pct` 폴백).

### 2.3 message_spike_alert.py (변경 — push_context.spike_view 우선)

`build_spike_alert_message` body 가 다음 순서로 조립된다:

1. `[universe momentum 관찰 (push_context 기반)]` — 신규 `spike_view_lines(push_context)`
   — 풍부 관찰 1줄/item (AC-5):
   - 수익률 근거: `1d` / `5d` / `20d` 중 사용 가능한 것 / 또는 momentum score.
   - 방향: `up` / `down`.
   - data_quality: flag 있으면 표시, 없으면 "이상 없음".
   - holdings overlap: 보유 종목과 겹침 / 겹치지 않음 명시.
2. `[ETF universe 변동성 확대 관찰]` — 기존 `_topn_spike_section` — 표시 하한
   이상 변동 목록.
3. `[기존 급락 ETF 주의 신호 (PUSH 3 재사용)]` — 기존 falling candidate 1줄.
4. `[data_quality 확인 필요]` — 기존 data_quality flag 모음.
5. 중립 안내.

직전 STEP 의 `_spike_view_section()` (score 만 노출) 은 `spike_view_lines` 가
대체. `_topn_candidates()` 도 candidates / items 양쪽 호환.

### 2.4 draft_message.py (변경 — PUSH-2 본문에 runtime 섹션 삽입)

`_runtime_evidence_lines(payload)` 신규 — payload.runtime_package.push_context 가
있을 때 `holdings_observation_lines()` 를 호출해 다음 3 섹션을 만든다:

- `[보유 종목 관찰 포인트]` — holdings_view.observations 의 사람이 읽는 1줄들.
- `[시장 흐름 연결 (market_view)]` — market_view 의 미국 지수 요약 + Market
  Discovery 흐름 1줄 (AC-4 — market_view 연결 보장).
- `[리뷰 포인트]` — review_points 3건.

`_build_with_focus_limit()` 안의 본문 조립 순서: `header → judgment → runtime →
summary → focus → footer` — judgment 직후, summary 직전. 본 위치는 사용자가
"왜 이 종목을 봐야 하는지" 를 먼저 읽고 그 다음 전체 평가 요약을 보도록 의도.

`push_context` 가 비어있거나 의미 있는 observation 0건이면 `_runtime_evidence_lines`
가 빈 리스트를 반환 → 기존 흐름 그대로 유지.

### 2.5 draft.py (변경 — PUSH-2 evidence 에 Market Discovery topn 추가)

`_build_holdings_payload` 가 holdings 흐름의 `runtime_package` evidence 에
`market_discovery_snapshot` 을 채운다 (AC-4 — market_view 연결 강화).

**compute_topn 호출 정책 (검증자 r2 NOTES B-6 반영)**: 본 함수는 `compute_topn`
을 **함수당 정확히 1회만** 호출하고, 그 결과 (`topn_payload_for_holdings`) 를
다음 두 곳에서 재사용한다:

1. `build_holdings_market_evidence(topn_payload=...)` — 기존 holdings × Market
   Discovery evidence builder 입력.
2. PUSH-2 `runtime_package` 의 `pc_evidence_snapshot.market_discovery_snapshot`
   — push_context 의 market_view 연결을 위한 evidence (AC-4).

candidates 가 비어있는 경우 (테스트 stub / 시장 데이터 미적재) 는
`market_discovery_snapshot` 자체를 빈 dict 로 두어 holdings_briefing 의 필수
evidence 검증 (market_view 또는 market_discovery) 이 그대로 동작하도록 한다 —
FIX r3 의 "failed package 시 본문 비움" 안전장치 보존.

`_runtime_snapshot_for_holdings` 의 try/except 는 직전 STEP 그대로 (변경 없음).

---

## 3. 신규 파일

| 파일 | 라인 수 | 책임 |
| --- | --- | --- |
| `tests/test_three_push_message_text_runtime_evidence.py` | **638** | 15 신규 테스트 (AC-1 / AC-2 / AC-3 / AC-4 / AC-5 / AC-7 / AC-8 / AC-10 검증 + push_context 헬퍼 + end-to-end Run). |

---

## 4. 수정 파일

| 파일 | 라인 수 (실측) | 변경 내용 |
| --- | --- | --- |
| `app/push_context.py` | 247 → **798** | observation 별 사람이 읽는 text + 실제 값 채움. 신규 헬퍼 5종 (`overnight_us_lines` 풍부화 + `market_trend_lines` / `risk_pattern_lines` / `holdings_observation_lines` / `spike_view_lines` 신규). spike_view 가 universe momentum + Market Discovery candidates 양쪽 합쳐 풍부 표시. `_fmt_pct` 계약 변경 (% 가정). |
| `app/message_market_briefing.py` | 197 → **225** | body 조립에 `market_trend_lines` / `risk_pattern_lines` 섹션 추가 + `_market_internal_section` 이 compute_topn `candidates` / `items` 양쪽 호환. |
| `app/message_spike_alert.py` | 239 → **240** | `_spike_view_section` 제거 + `spike_view_lines(push_context)` 호출로 대체. `_topn_spike_section` / `_data_quality_section` 이 candidates / items 양쪽 호환. |
| `app/draft_message.py` | 586 → **616** ⚠ near | `_runtime_evidence_lines(payload)` 신규 + `_build_with_focus_limit` 본문 조립에 runtime 섹션 삽입. |
| `app/draft.py` | 559 → **586** | `_build_holdings_payload` 가 PUSH-2 evidence 에 compute_topn 결과를 채움 (1회 호출 후 재사용, candidates 0건 시 빈 dict 유지). |

⚠ **KS-10 영향 (백엔드 핵심 모듈 임계)**:
- `app/push_context.py` **798 라인** — KS-10 **trigger** (≥650 라인) 진입.
- `app/draft_message.py` **616 라인** — KS-10 **근접 (near)** (≥600 라인).

두 파일 모두 본 STEP 의 책임 범위 안에서 자연 증가. 후속 Cleanup STEP 으로
분리 필요 — 보고서 §7 사용자 확인 항목.

---

## 5. 메시지 본문 실측 (PC 라이브 — stub probe)

### 5.1 PUSH-1 (`POST /runs/generate + push_kind="market_briefing"`)

```text
📊 시장 흐름 브리핑
기준일/생성: 2026-06-14T...

[밤사이 미국 시장 (runtime probe)]
  • NASDAQ +0.85% (close 18,000.12)
  • SPX +0.41% (close 5,400.33)
  • SOX +1.25% (close 5,200.45)
  • 반도체 지수 강세는 국내 반도체/성장 ETF 해석에 참고 가능

[국내 시장 내부 신호 (Market Discovery)]
  • 상위(one_month): ACE 코리아AI테크핵심산업 +32.77%, ... / 하위(one_month): ...

[시장 내부 신호]
  • 기준일: 2026-06-11 / 비교 기준: one_month
  • 상위 ETF 흐름: ...
  • 하위 ETF 흐름: ...

[위험 패턴 참고 (ML baseline 룩백)]
  • 과거 43거래일 룩백 — high-risk bucket 의 이후 10d drawdown -8.37% vs low-risk -4.43% (참고용 baseline).

[위험 패턴 참고]
  • 과거 43거래일 룩백 — high-risk bucket 의 이후 10d drawdown -8.37% vs low-risk -4.43%.
  • 본 항목은 baseline 참고이며 현재 시장의 확정 판정이 아닙니다.

[추가 확인 필요 외부 변수]
  • CNN Fear & Greed 현재 수준
  • VIX 또는 VKOSPI 유사 변동성 지표
  ...

이 브리핑은 시장 내부 신호의 요약이며 ...
```

AC-1 / AC-2 / AC-7 / AC-8 통과.

### 5.2 PUSH-3 (`POST /runs/generate + push_kind="spike_or_falling_alert"`)

```text
⚡ 급등락 관찰 신호
기준일/생성: 2026-06-14T...

[universe momentum 관찰 (push_context 기반)]
  • KODEX 200: momentum score +38.60 · 방향 up · data_quality 이상 없음 · 보유 종목과 겹치지 않음
  • ACE 코리아AI테크핵심산업: 1d +0.92%, 20d +32.77% · 방향 up · data_quality 이상 없음 · 보유 종목과 겹치지 않음
  • RISE 네트워크인프라: 1d +0.94%, 20d +31.57% · 방향 up · ...
  ...

[ETF universe 변동성 확대 관찰]
  ...

이 신호는 universe 내부 관찰이며 ...
```

AC-5 / AC-7 / AC-8 통과 — score 만 표시되지 않고 수익률 근거 / 방향 /
data_quality / holdings overlap 4축이 함께 노출.

### 5.3 PUSH-2 (`POST /runs/generate-from-holdings`)

```text
✅ POC2 holdings 승인 처리
run_id: run_...
title: 보유 종목 기반 초안 (2026-06-14)

holdings 항목 N건 기준 ...

[판단 사유]
- 보유 종목 상태 브리핑: ...
- 보유 vs 시장: ...
- ML baseline 룩백 evidence: ...

[보유 종목 관찰 포인트]
  • KODEX 200 (069500): runtime 시세 +0.42% (가격 36,000) · 국내 기준선 — 밤사이 미국 지수 흐름과 함께 확인 필요 — 관찰 필요
  • KODEX 코스닥150 (229200): runtime 시세 -1.10% (가격 18,000) — 관찰 필요

[시장 흐름 연결 (market_view)]
  • 밤사이 미국: NASDAQ +0.85%, SPX +0.41%, SOX +1.25% / 상위(one_month): ... / 하위(one_month): ...

[리뷰 포인트]
  • 미국 지수와 국내 보유 ETF의 방향이 엇갈리는지 확인
  • 보유 종목이 당일 급등락 후보와 겹치는지 확인

전체 요약: ...
주목 종목: ...
```

AC-3 / AC-4 / AC-7 / AC-8 통과 — 단순 holdings 목록이 아닌 관찰 포인트 +
market_view 연결.

---

## 6. AC 매핑 (지시문 §15)

| AC | 결과 | 근거 |
| --- | --- | --- |
| AC-1 PUSH-1 미국 지수 값 반영 | PASS | NASDAQ +0.85% / SPX +0.41% / SOX +1.25% 실측 노출. 신규 단위 테스트 `test_overnight_us_lines_shows_actual_change_pct` + end-to-end `test_push1_message_text_includes_us_indices_through_run`. |
| AC-2 PUSH-1 market evidence 연결 | PASS | `[국내 시장 내부 신호 (Market Discovery)]` + `[위험 패턴 참고 (ML baseline 룩백)]` 2 섹션 본문 포함. 단위 테스트 `test_market_briefing_message_text_contains_us_values_and_evidence`. |
| AC-3 PUSH-2 holdings 관찰 포인트 | PASS | `[보유 종목 관찰 포인트]` 섹션 + 단순 목록 회피. 단위 테스트 `test_holdings_view_observations_have_text_lines` + `test_holdings_view_skips_position_without_signal_data` + end-to-end `test_push2_message_text_has_observation_points`. |
| AC-4 PUSH-2 market_view 연결 | PASS | `[시장 흐름 연결 (market_view)]` 1줄 (미국 지수 + Market Discovery 흐름). 단위 테스트 `test_holdings_observation_lines_contain_market_view_connection`. |
| AC-5 PUSH-3 score 단독 금지 | PASS | `spike_view_lines` 가 수익률 근거 / 방향 / data_quality / overlap 4축을 함께 노출. 단위 테스트 `test_spike_view_lines_render_not_score_only` + `test_spike_alert_message_text_includes_runtime_evidence` + end-to-end `test_push3_message_text_not_score_only_through_run`. |
| AC-6 runtime_package 기반 생성 | PASS | 모든 builder 가 `push_context` 인자를 받아 동작. `runtime_package.message_contract.message_text == Run.message_text` 일치 (직전 STEP 검증 유지). |
| AC-7 빈 placeholder 방지 | PASS | 실패한 indices 는 행 생략 / 전부 실패면 섹션 생략 (`test_overnight_us_lines_empty_when_all_failed` + `test_overnight_us_lines_skips_failed_index`). message_text 에 "unavailable" / "조회 실패" substring 0건 (라이브 검증). |
| AC-8 금지 문구 없음 | PASS | 신규 테스트 forbidden substring 검사 (지금 매수 / 지금 매도 / 교체 매수 / 조정장 확정 / 위험 threshold 확정 / 현금 비중 확대 / raw_json / token / chat_id). |
| AC-9 기존 delivery 흐름 유지 | PASS | PENDING_APPROVAL → DELIVERING → COMPLETED / FAILED 흐름 변경 0건. delivery.py 변경 0건 (직전 STEP r6 이후 유지). |
| AC-10 기존 계산 산식 불변 | PASS | holdings / Market Discovery / ML baseline / NAV·괴리율 / universe momentum / data quality 산식 변경 0건. push_context 는 기존 builder 결과 dict 를 그대로 읽기만 함. |
| AC-11 실제 Telegram 발송 0 | PASS | 테스트는 `delivery.deliver` autouse stub (기존). 라이브 검증은 PENDING_APPROVAL 까지만 도달. |
| AC-12 문서 갱신 | PASS (partial) | STATE_LATEST / POC2_B_NEXT_ACTIONS / POC2_FEATURE_INVENTORY / 본 conclusion 갱신. **handoff/STATE_LATEST.md 는 6줄 redirect stub 이라 미갱신 — 캐노니컬 state 는 docs/STATE_LATEST.md 단독 유지 (§7 참조)**. |

---

## 7. 사용자 확인 필요 항목 (KS-10)

- **`app/push_context.py` 798 라인 (KS-10 trigger — 백엔드 핵심 모듈 ≥650 라인)**:
  본 STEP 범위 (push_context 풍부화 — observation 별 실제 값 + 헬퍼 5종) 안에서
  자연 증가. 책임 분리는 본 STEP 범위 밖이므로 후속 Cleanup STEP 으로 분리
  필요. KS-10 의 트리거 발동 시 조치 — `다음 기능 Step 진입 중단 / Cleanup
  Step 별도 명명 / UI·문구·데이터 계약 변경 금지` — 를 따라 다음 STEP 진입 전
  사용자 확인 필요.
- **`app/draft_message.py` 616 라인 (KS-10 근접 near — 백엔드 핵심 모듈 ≥600 라인)**:
  본 STEP 의 `_runtime_evidence_lines(payload)` 신규 추가로 30 라인 증가.
  trigger 까지 34 라인 여유. 다음 변경 시 trigger 진입 가능성 — Cleanup STEP
  범위에 함께 포함 권고 (단일 Cleanup STEP 으로 push_context + draft_message
  책임 분리).
- **`docs/handoff/STATE_LATEST.md` 미갱신**: 본 파일은 6줄 redirect stub
  ("본 파일과 ARCHIVE 로 안내" 만 포함). 본 STEP 에서는 변경하지 않았다 (stub
  자체가 변경 대상 아님). 캐노니컬 state 는 `docs/STATE_LATEST.md` 가 단독
  유지 — 본 conclusion §8 / 보고서 JSON 의 `handoff_state_latest_updated` 는
  `false` 로 정정.

---

## 8. 검증 결과 (지시문 §16)

- backend tests: **534 passed** (직전 STEP 519 → +15 신규 / 회귀 0).
  - 신규 테스트: `tests/test_three_push_message_text_runtime_evidence.py` **15건**.
- backend format / lint: **PASS** (`black --check` / `flake8` 0 warning).
- frontend lint: **PASS** (eslint 0 warning).
- frontend build: **PASS** (Next.js 15 production build).
- PC 라이브 preview 실측 (§5): PUSH-1 / PUSH-3 / PUSH-2 본문 모두 풍부화 확인.

---

## 9. 범위 외 영향 (지시문 §13 — 0건 검증)

- 신규 API endpoint: **0건**.
- 신규 외부 source: **0건**.
- 신규 dependency: **0건** (`requirements.txt` 변경 없음).
- OCI runtime 구현: **없음**.
- scheduler: **없음**.
- 뉴스 source: **없음**.
- 개별 주식 universe: **없음**.
- ML 산식 / Market Discovery 산식 / NAV·괴리율 산식 / universe momentum 산식 변경:
  **0건**.
- 매수·매도·교체·비중조절·위험 threshold·조정장 확정: **0건**.
- frontend message_text 조립: **0건**.

---

## 10. 다음 STEP 후보 (사용자 결정 대기)

1. **KS-10 Cleanup — push_context 책임 분리**: 본 STEP 의 KS-10 trigger 해소.
   helper 5종을 별도 모듈로 분리 (관찰 빌더 / 메시지 line 빌더 분리). UI / 문구 /
   데이터 계약 변경 금지.
2. **OCI runtime source 도입**: PC 에서 검증한 source 가 OCI 네트워크에서도
   작동하는지 확인 + outbox/Telegram 발송 분기 마이그레이션.
3. **하루 3회 발송 시간 + 자동 발송 UX**: scheduler / 발송 시각 / 자동 vs 수동
   트리거 결정.
4. **runtime source 수동 refresh endpoint**.
5. **뉴스 source 도입** (PUSH-1 의 [전일 기준 시장 흐름] 보강).
6. **ThreePushDraftCard 정식 화면 위치 결정**.

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.
