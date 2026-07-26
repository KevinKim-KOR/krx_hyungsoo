# POC2 — 3-PUSH Context Cleanup (Conclusion)

작성일: 2026-06-14
관련 commit: (이번 STEP)
지시문: 개발자 최종 지시문 — Cleanup Step: 3-PUSH Message Context 구조 분리 (2026-06-14)

---

## 0. 한 줄 요약

직전 STEP (3-PUSH Message Text Runtime Evidence 반영, 2026-06-14) 의 PARTIALLY_VERIFIED
판정 원인이었던 KS-10 trigger / near 4건을 모두 해소 — `app/push_context.py`
798 라인 trigger + `app/draft_message.py` 616 라인 near + `app/market_topn.py`
613 라인 near + `scripts/diagnose_nav_discount_source.py` 984 라인 trigger 를
helper 모듈 분리로 모두 600 라인 미만으로 낮춤. 산식 / 문구 / 데이터 계약 / API
endpoint / message_text 의미 변경 0건.

---

## 1. 범위 (지시문 §3 / §6)

### 1.1 처리한 trigger / near

작업 시작 시 KS-10 기준 (백엔드 `.py` 트리거 ≥650 / near ≥600) 으로 전체 `.py`
실측 후 분류한 결과:

| 파일 | before | KS-10 분류 | 처리 |
| --- | --- | --- | --- |
| `app/push_context.py` | 798 | trigger | format/market/holdings/spike 4 모듈 + wrapper 로 분리 |
| `scripts/diagnose_nav_discount_source.py` | 984 | trigger | judge/record/markdown helper 모듈 1개로 분리 |
| `app/draft_message.py` | 616 | near | focus/summary 렌더링을 별도 모듈로 분리 |
| `app/market_topn.py` | 613 | near | 상수 / dataclass / helper 를 별도 모듈로 분리 |

작업 종료 시점 라인 수 (실측, black 적용 후, PowerShell
`Get-Content | Measure-Object -Line` 기준 — 검증자 r2 NOTES A-2/A-3 반영):

| 파일 | after | KS-10 |
| --- | --- | --- |
| `app/push_context.py` | **72** | safe |
| `scripts/diagnose_nav_discount_source.py` | **524** | safe |
| `app/draft_message.py` | **299** | safe |
| `app/market_topn.py` | **347** | safe |

> 1차 보고 당시 `wc -l` (Unix style, trailing newline 포함) 으로 측정한 수치
> (83 / 594 / 374 / 383) 와 차이. KS-10 임계 비교는 보수적으로 **작은 값** 인
> PowerShell 측정값을 단일 기준으로 통일 (직전 STEP 까지 검증자가 사용한 측정
> 기준과 일치).

### 1.2 frontend / tests 측정 결과 (git-tracked 기준, backup/ref 제외 — 사용자 결정)

- frontend `.ts` / `.tsx`: 최대 691 라인 (`MarketDiscoveryView.tsx`) — KS-10 기준
  (frontend 컴포넌트 trigger ≥900 / near ≥850) 미진입. **trigger/near 0건**.
- tests `.py`: 최대 924 라인 (`test_holdings_message_text.py`) — KS-10 테스트 기준
  (trigger ≥2,500 또는 1,500+여러 Step 섞임 / near ≥1,450) 미진입. **trigger/near 0건**.

---

## 2. 신규 모듈

| 파일 | 라인 수 | 책임 |
| --- | --- | --- |
라인 수는 PowerShell `Get-Content | Measure-Object -Line` 기준 (검증자 r2
NOTES A-2 반영).

| 파일 | 라인 수 | 책임 |
| --- | --- | --- |
| `app/push_context_format.py` | 59 | `_fmt_pct` / `_has_data` / `_topn_candidates` / `_candidate_*` / `_US_SECTOR_HINTS`. |
| `app/push_context_market.py` | 266 | `build_market_view` + `overnight_us_lines` / `market_trend_lines` / `risk_pattern_lines` + 내부 observation builder 3종. |
| `app/push_context_holdings.py` | 202 | `build_holdings_view` + `holdings_observation_lines` + `_holdings_overlap_tickers` + `_holdings_position_text`. |
| `app/push_context_spike.py` | 191 | `build_spike_view` + `spike_view_lines` + `_universe_momentum_items`. |
| `app/draft_message_focus.py` | 216 | `compute_summary` / `select_focus_items` / `_render_summary_lines` / `_render_focus_item` / `_render_focus_section` + `TOP_N_*` 상수. |
| `app/market_topn_helpers.py` | 234 | `REQUIRED_TABLES` / `EXCLUSION_REASONS` / lookback days 상수 / `TopNEntry` / `_PeriodResult` / `_missing_required_tables` / `classify_etf_tags` / `_compute_period` / `_empty_*_buckets` / `_latest_*` / `_build_filters_dict` / `_build_empty_payload`. |
| `scripts/diagnose_nav_discount_source_helpers.py` | 391 | `judge_pykrx_ohlcv` / `judge_pykrx_deviation` / `judge_fdr` / `judge_naver_integration` / `judge_naver_etf_detail` / `_record_from` / `_build_flat_records` / `render_markdown`. |

---

## 3. 수정 파일

| 파일 | 변경 |
| --- | --- |
| `app/push_context.py` | 본문 helper / view builder 모두 분리 모듈로 이관. orchestration `build_push_context` + 분리 모듈 re-export 만 유지. |
| `app/draft_message.py` | `compute_summary` / `_render_summary_lines` / `select_focus_items` / `_render_focus_item` / `_render_focus_section` / `_CATEGORY_HEADERS` / `TOP_N_*` 본문 정의 제거 + `draft_message_focus` re-export. |
| `app/market_topn.py` | 상수 / dataclass / helper 본문 정의 제거 + `market_topn_helpers` re-export. `compute_topn` 본문은 그대로 유지. |
| `scripts/diagnose_nav_discount_source.py` | `judge_*` × 5 + `_record_from` + `_build_flat_records` + `render_markdown` 본문 정의 제거 + helpers 모듈 re-export. `run_diagnosis` + probe 함수들은 그대로 유지. |
| `scripts/diagnose_constituents_source.py` | black 자동 포맷팅만 적용 (본 STEP 변경 의도 아님). |

---

## 4. 호환성 보장 (지시문 §6.3)

기존 import 경로는 모두 유지된다:

```python
# 기존 (계속 동작):
from app.push_context import (
    build_push_context,
    build_market_view,
    build_holdings_view,
    build_spike_view,
    overnight_us_lines,
    market_trend_lines,
    risk_pattern_lines,
    holdings_observation_lines,
    spike_view_lines,
)
from app.draft_message import (
    compute_summary,
    select_focus_items,
    _render_summary_lines,
    _render_focus_item,
    _render_focus_section,
    TOP_N_PRICE_MISSING,
)
from app.market_topn import (
    compute_topn,
    DEFAULT_N, DEFAULT_BASIS, DEFAULT_ORDER,
    classify_etf_tags,
    TopNEntry,
)
```

기존 테스트와 호출자는 코드 변경 없이 동작 — pytest 534 passed (회귀 0).

---

## 5. AC 매핑 (지시문 §9)

| AC | 결과 | 근거 |
| --- | --- | --- |
| AC-1 라인 수 측정 (전후) | PASS | §1.1 / §1.2 표 + verification 보고서 JSON `line_count` 필드. |
| AC-2 trigger_files_before 목록화 | PASS | `app/push_context.py` (798) + `scripts/diagnose_nav_discount_source.py` (984). |
| AC-3 near_threshold_files_before 목록화 | PASS | `app/draft_message.py` (616) + `app/market_topn.py` (613). |
| AC-4 trigger_files_after = [] | PASS | 본 STEP 종료 시점 backend `.py` 중 ≥650 라인 0건. |
| AC-5 near_threshold_files_after = [] | PASS | backend `.py` 중 ≥600 라인 0건. |
| AC-6 push_context.py 구조 분리 | PASS | 798→72 라인. market / holdings / spike / format 4 모듈로 분리. wrapper 만 유지. |
| AC-7 draft_message.py near 해소 | PASS | 616→299 라인. focus / summary 렌더링 분리. |
| AC-8 message_text 회귀 없음 | PASS | pytest 534 passed (회귀 0). `tests/test_three_push_message_text_runtime_evidence.py` 15건 / `tests/test_runtime_package.py` 22건 / `tests/test_holdings_message_text.py` 24건 모두 통과. |
| AC-9 기존 테스트 통과 | PASS | pytest 534 passed. |
| AC-10 frontend lint/build 통과 | PASS | eslint 0 warning / Next.js 15 production build PASS. |
| AC-11 신규 기능 0건 | PASS | 함수 시그니처 / 본문 그대로 이동만 수행. |
| AC-12 신규 API / 데이터 계약 0건 | PASS | endpoint / runtime_package schema 변경 0건. |
| AC-13 문서 갱신 | PASS | STATE_LATEST / POC2_B_NEXT_ACTIONS / POC2_FEATURE_INVENTORY + 본 conclusion. |

---

## 6. 검증 결과

- backend tests: **534 passed** (직전 STEP 534 유지 / 회귀 0).
- backend format: `black` PASS (자동 reformat 후 통과).
- backend lint: `flake8` — 본 STEP 신규 파일 0 warning. `scripts/diagnose_constituents_source.py` 의 4 warning (`F541 f-string is missing placeholders`) 는 stale (본 STEP 작업 전부터 존재, KS-10 트리거 아님 — 본 STEP 범위 밖).
- frontend lint: eslint **0 warning**.
- frontend build: Next.js 15 production build **PASS**.
- 라인 수 재측정 (PowerShell `Get-Content | Measure-Object -Line` 기준, git-tracked 영역): backend `.py` 최대 524 (`scripts/diagnose_nav_discount_source.py`) — KS-10 trigger 0건 + near 0건.

---

## 7. 다음 STEP 후보 (사용자 결정 대기)

본 Cleanup STEP 으로 구조 안정화 완료. 직전 STEP 의 PARTIALLY_VERIFIED 사유는
해소되어 다음 기능 STEP 진입 가능.

1. **OCI runtime source 도입** — PC 에서 검증한 source 가 OCI 네트워크에서도
   작동하는지 확인 + outbox / Telegram 발송 분기 마이그레이션.
2. **하루 3회 발송 시간 + 자동 발송 UX** — scheduler / 발송 시각 / 자동 vs 수동
   트리거 결정.
3. **runtime source 수동 refresh endpoint** — 사용자가 cache 즉시 갱신 필요 시.
4. **뉴스 source 도입** — PUSH-1 의 [전일 기준 시장 흐름] 보강.
5. **ThreePushDraftCard 정식 화면 위치 결정**.

본 문서는 다음 STEP 을 임의 확정하지 않는다.
