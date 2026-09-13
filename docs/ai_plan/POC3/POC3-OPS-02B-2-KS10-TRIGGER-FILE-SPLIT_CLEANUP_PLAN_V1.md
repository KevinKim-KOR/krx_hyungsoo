# POC3-OPS-02B-2-KS10-TRIGGER-FILE-SPLIT — Cleanup PLAN V1

작성일: 2026-09-13 · 작성자: 개발자(VSCode Claude) · 수신: 설계자

```text
CLEANUP_UNIT    = POC3-OPS-02B-2-KS10-TRIGGER-FILE-SPLIT
CURRENT_ACTION  = PLAN_ONLY
CODE_CHANGED    = 0건
PARENT_STEP     = POC3-OPS-02B-2 (PAUSED)
TRIGGER_COUNT   = 2 (추가 trigger 0건)
NEAR_COUNT      = 6 (이번 범위 밖 — 보고만)
COMMIT_PUSH_DEPLOY_SEND = 0
```

이 문서는 **계획서**다. 승인 전까지 코드를 바꾸지 않는다. 아래 측정은 모두
2026-09-13 실측이며 추정값이 없다.

---

## §1. 현재 `git status --short` 원문

```text
 M app/market_benchmark_batch.py
 M app/runtime_evidence/composer.py
 M app/three_push_runtime/market_data_batch.py
 M app/three_push_runtime/runner_evidence.py
 M docs/ai_plan/POC3/POC3-OPS-02B_MARKET_BRIEFING_REDEVELOPMENT_PLAN_V1.md
 M scripts/run_oci_market_data_batch.py
 M scripts/run_three_push_runtime_oci.py
 M tests/_helpers.py
 M tests/conftest.py
 M tests/runtime_evidence/test_runtime_runner_forwarding.py
 M tests/test_low_frequency_push_operation.py
 M tests/test_market_benchmark_freshness.py
 M tests/test_runtime_runner_partial_delivery.py
 M tests/universe_bootstrap/test_runtime_universe.py
?? app/market_briefing/
?? app/three_push_runtime/runner_market_briefing.py
?? docs/ai_design/POC3/POC3-OPS-02B-2_MARKET_BRIEFING_MESSAGE_DESIGN_V1.md
?? docs/ai_plan/POC3/POC3-OPS-02B-2_MARKET_BRIEFING_MESSAGE_PLAN_V1.md
?? docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md
?? docs/handoff/POC3/OPS-02B-2_IMPLEMENTATION_CHECKPOINT.md
?? state/three_push/market_briefing_meta_consistency_latest.json
?? state/three_push/market_briefing_state_latest.json
?? tests/test_market_briefing_batch.py
?? tests/test_market_briefing_contracts.py
```

`--untracked-files=all` 기준 31건. worktree 는 깨끗하지 않다. 부모 Step 구현과
완료된 Cleanup(runner evidence 추출)이 모두 uncommitted 다. 임의로 정리하지
않았다 — `git stash·reset·checkout` **0건**.

`docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 는 사용자 소유
파일이다. 읽지도 옮기지도 지우지도 않았다.

---

## §2. 전체 tracked `.py` / `.ts` / `.tsx` 측정

측정 명령 (재현 가능):

```bash
git ls-files -z '*.py' '*.ts' '*.tsx' | xargs -0 wc -l
```

| 구분 | 파일 수 |
|---|---:|
| backend `.py` (app·scripts 등) | 204 |
| test `.py` (`tests/`, `test_*.py`) | 110 |
| frontend `.tsx` | 74 |
| frontend `.ts` | 37 |
| **tracked 합계** | **425** |

적용 임계 (`docs/KILL_SWITCHES.md` KS-10):

| 역할 | NEAR | TRIGGER |
|---|---:|---:|
| backend 핵심 모듈 | ≥600 | >650 |
| 테스트 | ≥1450 | >1500 |
| frontend 컴포넌트 | ≥850 | >900 |

### §2.1 TRIGGER — 2건

| 줄 | 역할 | 파일 |
|---:|---|---|
| **1548** | test | `tests/test_low_frequency_push_operation.py` |
| **907** | frontend | `frontend/app/components/TodayInvestmentCheckView.tsx` |

### §2.2 NEAR — 6건 (이번 Cleanup 범위 **밖**)

| 줄 | 역할 | 파일 | 임계까지 |
|---:|---|---|---:|
| 855 | frontend | `frontend/app/components/JudgmentWorkbenchView.tsx` | 45 |
| 648 | backend | `scripts/run_three_push_runtime_oci.py` | 2 |
| 632 | backend | `app/api.py` | 18 |
| 626 | backend | `app/ml_score_validity_report.py` | 24 |
| 616 | backend | `app/holdings_market_evidence.py` | 34 |
| 602 | backend | `app/draft.py` | 48 |

### §2.3 SAFE — 417건

### §2.4 추가 trigger 존재 여부

**추가 trigger 0건.** 이미 확인된 2건 외에 임계를 넘는 tracked 파일은 없다.
경계 확인용 상위 목록:

| 역할 | 1위 | 2위 | 3위 |
|---|---|---|---|
| test | 1548 `test_low_frequency_push_operation.py` | 924 `test_holdings_message_text.py` | 809 `test_ml_job_runner.py` |
| `.tsx` | 907 `TodayInvestmentCheckView.tsx` | 855 `JudgmentWorkbenchView.tsx` | 825 `MarketDiscoveryView.tsx` |
| `.ts` | 392 `lib/marketDiscoveryCopyText.ts` | 331 `holdings_compare/helpers.ts` | 282 `lib/api/market.ts` |

test 2위가 924 — TRIGGER 와 624줄 차이다. `.ts` 는 최대 392 로 임계와 무관하다.

### §2.5 아직 untracked 인 이번 Step 산출물 (참고)

commit 되면 tracked 가 되므로 같이 측정했다. **trigger·near 0건.**

| 줄 | 파일 |
|---:|---|
| 567 | `tests/test_market_briefing_contracts.py` |
| 385 | `tests/test_market_briefing_batch.py` |
| 286 | `app/market_briefing/krx_sync.py` |
| 262 | `app/market_briefing/flow.py` |
| 232 | `app/market_briefing/krx_store.py` |
| 229 | `app/market_briefing/meta_gate.py` |
| 226 | `app/market_briefing/evidence.py` |
| 172 | `app/market_briefing/render.py` |
| 161 | `app/market_briefing/calendar.py` |
| 156 | `app/three_push_runtime/runner_market_briefing.py` |
| 11 | `app/market_briefing/__init__.py` |

---

## §3. TRIGGER 1 — `tests/test_low_frequency_push_operation.py` (1548줄)

### §3.1 현재 구조 — 파일이 이미 책임별로 나뉘어 있다

파일 안에 `# ── … ──` 섹션 주석이 11개 있고, 각 섹션이 서로 다른 책임을 검사한다.
섹션별 실측:

| 줄 | test | helper | 섹션 |
|---:|---:|---:|---|
| 73 | 0 | 3 | (머리말 + 공용 helper) |
| 114 | 4 | 0 | Holdings overlay / runtime line / selection_count |
| 21 | 2 | 0 | Registry key |
| 125 | 8 | 2 | Reevaluator: Published Evidence 강제 · fingerprint 축약 |
| 29 | 1 | 0 | Producer publish |
| 15 | 2 | 0 | Spike body 재조립 (혼합 신호) |
| 378 | 8 | 4 | Runner-level Fail-Closed |
| 258 | 9 | 0 | as-of · loader · spike_body raise · reeval 예외 강제 |
| 182 | 11 | 3 | target_tickers unit test 확장 |
| 89 | 2 | 1 | PUSH 종류별 flag = false → 차단 분기 |
| 264 | 5 | 1 | POC3-OPS-01A — 선정 상태 라이브 경로 누출 |
| **1548** | **52** | **14** | 합계 |

설계자 지적대로 이 파일은 여러 PUSH·Step 책임이 섞여 있다. 단일 역사 파일이
아니라 **11개 책임의 누적**이다.

### §3.2 분리 방법 — 기존 선례를 그대로 따른다

저장소에 이미 같은 분리 선례가 있다: `tests/runtime_evidence/` 패키지가
`_fixtures.py` + 책임별 `test_*.py` 로 나뉘어 있고, 다른 테스트가
`from tests.runtime_evidence._fixtures import _ok_topn_payload` 로 쓴다.
새 규칙을 만들지 않고 이 구조를 복제한다.

신규 패키지 `tests/low_frequency_push/`:

| 파일 | 담을 것 | 예상 줄 |
|---|---|---:|
| `__init__.py` | (빈 패키지) | 1 |
| `_fixtures.py` | helper 14개 전부 | ~250 |
| `test_holdings_runtime_line.py` | Holdings overlay 섹션 + asof 중 holdings 1건 | ~170 |
| `test_registry_key.py` | Registry key 섹션 | ~45 |
| `test_reevaluator.py` | Reevaluator 섹션 + asof 중 reeval 2건 + composer 예외 1건 | ~200 |
| `test_spike_body.py` | Producer publish + Spike body 재조립 + raise 2건 | ~110 |
| `test_market_quote.py` | naver quote as-of 실패 1건 | ~45 |
| `test_runner_fail_closed.py` | Runner-level Fail-Closed 섹션 + asof 중 runner 3건 | ~430 |
| `test_target_tickers.py` | target_tickers 섹션 | ~160 |
| `test_kind_flag_guard.py` | PUSH 종류별 flag 차단 섹션 | ~75 |
| `test_selection_state_isolation.py` | POC3-OPS-01A 섹션 | ~250 |
| **합계** | **test 52건 전부 · helper 14개 전부** | **~1736** |

원본 `tests/test_low_frequency_push_operation.py` 는 **삭제하지 않고 0바이트로
비우지도 않는다.** 내용을 전부 옮긴 뒤 파일 자체를 제거할지는 **설계자 판단을
받는다**(파일 삭제는 사용자 승인 대상이기도 하다). 승인 전 기본안은
`git mv` 없이 신규 패키지에 옮기고 원본을 삭제 후보로만 보고하는 것이다.

합계가 1548 → ~1736 으로 느는 것은 파일당 머리말·import·섹션 주석이 11번
반복되기 때문이다. **최대 단일 파일은 ~430줄**로 test NEAR(1450) 의 30% 이하다.

### §3.3 as-of 섹션(258줄·9건) 재배치 — 1:1 매핑

이 섹션만 책임이 섞여 있어 개별로 옮긴다. 9건 전부 행선지를 명시한다.

| 현재 test | 행선지 |
|---|---|
| `test_reeval_missing_asof_reports_partial` | `test_reevaluator.py` |
| `test_holdings_runtime_line_absent_when_price_asof_missing` | `test_holdings_runtime_line.py` |
| `test_format_spike_signal_note_raises_on_missing_asof` | `test_spike_body.py` |
| `test_filter_extra_notes_length_mismatch_raises` | `test_spike_body.py` |
| `test_market_naver_missing_asof_fails_quote` | `test_market_quote.py` |
| `test_runner_holdings_file_missing_returns_failed` | `test_runner_fail_closed.py` |
| `test_runner_reeval_exception_forces_failed_no_send` | `test_runner_fail_closed.py` |
| `test_composer_reeval_fn_exception_produces_failed_result` | `test_reevaluator.py` |
| `test_runner_universe_semantic_invalid_returns_failed` | `test_runner_fail_closed.py` |

### §3.4 의미 보존 근거

- **테스트 개수 보존**: 52건 → 52건. 분리 전후 `pytest --collect-only -q | wc -l`
  로 총 수집 건수가 같음을 대조한다.
- **assertion 원문 보존**: 각 test 함수 본문을 **한 줄도 고치지 않고** 그대로
  옮긴다. 삭제·skip·`assert` 약화·줄 합치기·압축 금지.
- **helper 동일성**: helper 14개를 `_fixtures.py` 로 옮기되 **본문 무수정**.
  호출부는 import 경로만 바뀐다.
- **docstring 보존**: 각 test 의 docstring(검증자 라운드 근거가 적혀 있다)을
  그대로 가져간다. 섹션 주석도 행선지 파일 머리말로 옮겨 이력이 사라지지 않게
  한다.
- **외부 의존 확인 필요**: 다른 테스트가 이 파일의 helper 를 import 하는지
  착수 시 `grep -rn "test_low_frequency_push_operation" tests/` 로 먼저 확인한다.
  있으면 그 import 도 같은 커밋에서 고친다(현재 미확인 — PLAN 단계에서 코드를
  만지지 않기 위해 착수 시 확인 항목으로 남긴다).

---

## §4. TRIGGER 2 — `frontend/app/components/TodayInvestmentCheckView.tsx` (907줄)

### §4.1 이번 Step 이 만든 trigger 가 아니다 (실측)

이 파일은 **2026-08-05 커밋 `fdced239`** 에 900줄을 넘었다. `POC3-OPS-02B-2`
에서 프론트 변경은 **0건**이다. 설계자 판정대로 trigger 자체는 유효하므로
이번 Cleanup 범위에 넣는다.

### §4.2 현재 구조 — 이미 하위 컴포넌트 함수로 나뉘어 있다

| 줄 | 구간 | 내용 |
|---:|---|---|
| 56 | L1–56 | import · `Props` |
| 155 | L57–211 | `MaintenanceItem` 타입 + `collectMaintenance()` (순수 자료 가공) |
| 122 | L212–333 | `KospiHeadline` (§4.1 코스피 대표) |
| 75 | L334–408 | `BlockedMetric`·상수 2종·`BlockedRow`·`KospiDetailSection` |
| 129 | L409–537 | `JudgmentQueueSection` (§4.2 판단 큐) |
| 119 | L538–656 | `MaintInfo` + `MaintenanceQueueSection` (§4.3 정비 큐) |
| 78 | L657–734 | `DevItem`·상수 2종·`DevList`·`InDevelopmentSection` (§4.4) |
| 56 | L735–790 | `OciStatusOneLine` |
| 85 | L791–875 | 컨테이너 `TodayInvestmentCheckView` (default export) |
| 32 | L876–907 | `RefreshPhase`·`REFRESH_FEEDBACK_MS`·`useLightRefreshState` |
| **907** | | 합계 |

`export` 는 **default 1개뿐**이다(L791). 나머지는 모두 모듈 내부 함수다.

### §4.3 분리 방법 — 기존 선례를 그대로 따른다

선례: `frontend/app/components/holdings_compare/`(컴포넌트 4 + `helpers.ts`),
`frontend/app/components/holdings_risk_evidence/`(`helpers.ts` + 테스트).
같은 형태로 `frontend/app/components/today_investment_check/` 를 만든다.

| 파일 | 담을 것 | 예상 줄 |
|---|---|---:|
| `today_investment_check/maintenanceQueue.ts` | `MaintenanceItem` + `collectMaintenance` | ~165 |
| `today_investment_check/KospiHeadline.tsx` | `KospiHeadline` | ~135 |
| `today_investment_check/KospiDetailSection.tsx` | `BlockedMetric`·상수·`BlockedRow`·`KospiDetailSection` | ~90 |
| `today_investment_check/JudgmentQueueSection.tsx` | `JudgmentQueueSection` | ~140 |
| `today_investment_check/MaintenanceQueueSection.tsx` | `MaintInfo` + `MaintenanceQueueSection` | ~130 |
| `today_investment_check/InDevelopmentSection.tsx` | `DevItem`·상수·`DevList`·`InDevelopmentSection` | ~90 |
| `today_investment_check/OciStatusOneLine.tsx` | `OciStatusOneLine` | ~70 |
| `today_investment_check/useLightRefreshState.ts` | `RefreshPhase`·`REFRESH_FEEDBACK_MS`·hook | ~45 |
| `TodayInvestmentCheckView.tsx` (잔존) | import · `Props` · 컨테이너 | **~120** |
| **합계** | | **~985** |

**최대 단일 파일 ~165줄** — frontend NEAR(850) 의 20% 이하. 잔존 파일 ~120줄.

### §4.4 의미 보존 근거 — 외부 계약이 바뀌지 않는다 (실측)

이 파일의 무엇을 외부가 쓰는지 grep 으로 확인했다:

```text
frontend/app/components/MainPanel.tsx:21:import TodayInvestmentCheckView from "./TodayInvestmentCheckView";
frontend/app/components/TodayInvestmentCheckView.test.tsx:31:import TodayInvestmentCheckView from "./TodayInvestmentCheckView";
```

- 외부는 **default export 하나만** 쓴다. 파일 경로와 default export 를 그대로
  두므로 `MainPanel` 과 테스트의 import 는 **한 글자도 바뀌지 않는다**.
- 옮기는 함수들은 현재 모듈 내부 함수다. 새 파일에서 named export 가 되고
  잔존 파일이 import 한다. **렌더 트리·props·순서 불변.**
- **JSX 문구·className·핸들러·`fetch` 호출을 편집하지 않는다.** 블록을 그대로
  옮기고 import/export 줄만 더한다. 한국어 라벨·배지·안내 문구 전부 원문 유지.
- `useState` 4 · `useEffect` 3 · API 호출 10개의 **위치와 호출 시점이 바뀌지
  않도록**, hook 은 지금 있는 컴포넌트와 함께 이동한다(컴포넌트 경계를 가로질러
  hook 을 옮기지 않는다).
- **회귀 안전망**: `TodayInvestmentCheckView.test.tsx` 는 724줄·`it` 35건이며
  컴포넌트 전체를 `render` 한다. 분리가 문구·상호작용·API 호출을 깨면 이
  테스트가 잡는다. 테스트 파일은 **수정하지 않는다** — 수정이 필요해지면
  분리가 잘못된 것이므로 멈추고 보고한다.

---

## §5. 실행할 검증 범위

### §5.1 백엔드

| 단계 | 명령 | 통과 기준 |
|---|---|---|
| 포맷 | `black --check app tests scripts` | unchanged |
| lint | `flake8 app tests scripts` | exit 0 |
| 컴파일 | `py_compile` (신규 파일 전체) | OK |
| 수집 건수 대조 | `pytest --collect-only -q` 분리 전/후 | **총 건수 동일** |
| focused | `pytest tests/low_frequency_push/ -q` | 52 passed |
| 전체 회귀 | `pytest tests/ -q` | 현재 기준선 **1533 passed / 0 failed / 0 errors** 유지 |

전체 회귀는 ~140초로 2분 타임아웃을 넘길 수 있어 `run_in_background` 로 돌린다.

### §5.2 프론트엔드

| 단계 | 명령 | 비고 |
|---|---|---|
| 타입 | `npx tsc --noEmit` | |
| lint | `npm run lint` (eslint) | |
| 테스트 | `npx vitest run` | `TodayInvestmentCheckView.test.tsx` 35건 포함 |

**`npm run build` 는 이 Cleanup 의 자체 검수에서 제외한다.** 사용자 확정 규칙이다
— dev 서버가 켜진 상태에서 build 를 돌리면 `.next` 캐시가 겹쳐 dev 가 500
오류를 낸다. 현재 포트 3000 이 **LISTEN(dev 가동 중)** 임을 실측했다. build
검증이 필요하다면 dev 를 내리고 **별도 승인** 후 수행한다.

### §5.3 사용자 실화면 확인

이 Cleanup 은 UI 를 바꾸지 않는 것이 목표이므로, 분리 후 사용자에게
**「오늘의 투자 점검」 화면이 이전과 같은지** 한 번 확인받는다. 자동 테스트로는
레이아웃·폭이 잡히지 않는다(누적 교훈).

---

## §6. 변경 예상 파일과 예상 줄 수 (요약)

### §6.1 신규

| 파일 | 예상 줄 |
|---|---:|
| `tests/low_frequency_push/__init__.py` | 1 |
| `tests/low_frequency_push/_fixtures.py` | ~250 |
| `tests/low_frequency_push/test_*.py` (9개) | ~1485 |
| `frontend/app/components/today_investment_check/*.ts(x)` (8개) | ~865 |

### §6.2 수정

| 파일 | 현재 | 예상 후 |
|---|---:|---:|
| `frontend/app/components/TodayInvestmentCheckView.tsx` | 907 | **~120** |
| `tests/test_low_frequency_push_operation.py` | 1548 | **내용 이관 · 처리 방식은 설계자 판단** |

### §6.3 건드리지 않는 것

- `frontend/app/components/TodayInvestmentCheckView.test.tsx` (724) — 무수정
- `frontend/app/components/MainPanel.tsx` — import 변경 없음
- NEAR 6건 전부 — 임의 동시 수정 금지
- `scripts/run_three_push_runtime_oci.py` (648) — 이번 범위 밖
- 백엔드 운영 모듈 일체 · `app/market_briefing/` 6개 모듈

---

## §7. 라이브 DB·상태 파일·외부 네트워크 차단과 역검증

이 Cleanup 은 테스트 파일 이동과 프론트 분리뿐이라 새 쓰기 경로를 만들지
않는다. 기존 가드가 계속 유효한지 확인한다.

### §7.1 이미 걸려 있는 가드 (`tests/conftest.py`)

| 가드 | 대상 |
|---|---|
| `_isolated_store` | runs · handoff · holdings · market_cache 경로 |
| `_isolated_holdings_selection_state` | 보유 선정 · 급락 · **시장 브리핑 상태 2종** + `_mb.STATE_DIR` + `STATE_DIR` 원본 |
| `_stub_oci_calls` | deliver · fetch_outbox_result |
| `_block_live_benchmark_refresh` | `upsert_benchmark_prices` 저장 계층 |
| `_block_live_krx_api` | `krx_sync._default_fetcher` 네트워크 경계 |

신규 `tests/low_frequency_push/` 는 `tests/` 하위이므로 `tests/conftest.py` 의
autouse fixture 를 **그대로 상속**한다. 패키지 안에 별도 `conftest.py` 를 만들어
가드를 덮어쓰지 않는다.

### §7.2 역검증 방법 (분리 후 재실행)

1. **가드 활성 증거** — 아래를 실행해 출력을 RESULT 에 원문 인용한다.

   ```bash
   .venv/bin/python -c "
   from _pytest.monkeypatch import MonkeyPatch
   import tests.conftest as C
   from app.market_briefing import krx_sync
   mp = MonkeyPatch(); C._block_live_krx_api.__wrapped__(mp)
   krx_sync._default_fetcher('20260911','DUMMY')"
   ```

   `AssertionError: 테스트가 라이브 KRX Open API 를 호출했다.` 가 나와야 한다.

2. **라이브 파일 불변 증거** — 전체 회귀 **전후** 로 아래 sha256 을 비교해
   동일함을 RESULT 에 적는다.

   ```bash
   shasum -a 256 state/three_push/*.json state/market/market_data.sqlite
   ```

3. **무력화 시 실제로 실패하는가** — 상태 격리를 일시 해제하고 러너 테스트를
   돌려 검사에 걸리는지 확인한 뒤 **즉시 원복**하고, 원복 후 `conftest.py` 가
   바이트 동일함을 확인한다.

4. **외부 호출 0건** — 분리 작업 중 KRX·Naver·Telegram 실호출 0건을 유지한다.
   `_block_live_krx_api` 는 착수 전에 이미 들어가 있다.

---

## §8. 설계자 판단이 필요한 항목

착수 전에 답을 받아야 하는 것만 적는다. 추측해서 진행하지 않는다.

1. **원본 테스트 파일 처리** — 내용을 전부 `tests/low_frequency_push/` 로 옮긴 뒤
   `tests/test_low_frequency_push_operation.py` 를 **삭제**할지, 남길지.
   파일 삭제는 사용자 승인 대상이기도 하다. 기본안은 **삭제하지 않고 삭제 후보로
   보고**다.

2. **신규 패키지 이름** — `tests/low_frequency_push/` 로 제안한다
   (`tests/runtime_evidence/` 선례와 같은 꼴). 다른 이름을 원하면 지정해 달라.

3. **프론트 디렉터리 이름** — `frontend/app/components/today_investment_check/`
   로 제안한다 (`holdings_compare/`·`holdings_risk_evidence/` 선례와 같은 꼴).

4. **`npm run build` 제외 승인** — §5.2 사유로 자체 검수에서 뺀다. 필요하면
   dev 중지 + 별도 승인 후 수행한다. 이대로 괜찮은지 확인이 필요하다.

5. **NEAR 6건 처리 순서** — 이번 범위에서 제외했다. 특히
   `scripts/run_three_push_runtime_oci.py` 는 임계까지 **2줄**이고,
   `JudgmentWorkbenchView.tsx` 는 855 로 frontend 임계까지 45줄이다. 부모 Step
   복귀 시 러너에 한 줄이라도 더 들어가면 즉시 TRIGGER 가 된다. 별도 Cleanup
   단위로 언제 다룰지 순서를 정해 달라. 임의로 함께 수정하지 않는다.

---

## §9. 이 PLAN 단계에서 한 일 / 하지 않은 일

| 항목 | 실적 |
|---|---|
| 코드 수정 | **0건** |
| 파일 생성 | 이 PLAN 문서 1건 + 체크포인트 부록 정정 |
| commit · push | 0건 |
| OCI write · 배포 | 0건 |
| Telegram 발송 | 0건 |
| autosend | `false` 유지 |
| 로컬 DB·상태 파일 삭제·되돌림 | 0건 |
| 외부 네트워크 호출 | 0건 (KRX 차단 가드 역검증은 stub 호출로만 수행) |

부모 Step `POC3-OPS-02B-2` 는 `PAUSED` 상태 그대로다. 이 PLAN 승인 전에는 본
구현·목업·commit·push·OCI write·배포·autosend·실발송을 진행하지 않는다.
