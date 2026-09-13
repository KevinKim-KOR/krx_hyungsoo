# POC3-OPS-02B-2 — 08:00 시장 흐름 브리핑 · 개발 PLAN V1

- **작성**: 개발자 (VSCode Claude) · **수신**: 설계자 · **작성일**: 2026-09-11
- **대응 설계서**: `docs/ai_design/POC3/POC3-OPS-02B-2_MARKET_BRIEFING_MESSAGE_DESIGN_V1.md`
- **개정 이력**

  | 판 | 내용 |
  |---|---|
  | V1 (2026-09-11) | 최초 제출 → 설계자 **`REVISION_REQUIRED`** |
  | **V1.1** (2026-09-11) | 판정 반영. 운영 가격 공급 실측(§G) · Q1 거래일 Gate · Q2 미국 3종 · 상태 우선순위 · partial delivery · runner 배선 · 모듈 축소 |
  | **V1.2** (2026-09-11) | 설계자 **`APPROVED_WITH_REQUIRED_EDITS` · `IMPLEMENTATION = AUTHORIZED`**. **Q4 = C안**(KRX 일별 전종목 · **신규 테이블 별도 계열**) · Q1 **구현 진행/활성화만 차단** · 07:20 응답 1회 재사용 · coverage 분모 확정 · runner (a) 기각/(b) 만 · 추가 테스트 20종. 확정 사항은 **§M** |

- **상태**: **로컬 구현 승인** (`IMPLEMENTATION = AUTHORIZED`).
  `COMMIT_PUSH` · `OCI_DEPLOY` · `LIVE_SEND` **미승인** · `AUTOSEND = false` 유지 ·
  **`ACTIVATION_BLOCK = KRX_TRADING_CALENDAR_NOT_PROVIDED`**
- **수행 범위**: 저장소·로컬 DB 읽기 · OCI **읽기 전용** SSH · 소스 grep.
  **코드 수정 0건 · commit/push 0건 · OCI write 0건 · 발송 0건 ·
  `PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED=false` 유지 · 비밀값 미출력**

---

## 0. [V1.1] 요약 — **기초지수 블록이 현재 운영에서 산출 불가**

설계자 §4 지적이 맞았다. **`etf_daily_price` 전역 최신일 한 건으로 산출 가능성을
증명할 수 없었다.** OCI 읽기 전용 실측 결과는 다음과 같다.

| 실측 (OCI, 2026-09-11) | 값 |
|---|---:|
| `n≥2` 기초지수 그룹 distinct ticker | **196** |
| 그중 DB 에 **아예 없는** ticker | **5** |
| **최신 거래일(2026-09-10) 일치** | **6 / 196 = 3.1%** |
| **2026-07-03 에 멈춘** ticker | **185** |
| 5일·20일 수익률 계산 가능 | **6 / 196 = 3.1%** |
| **그룹별 fresh ticker ≥2 충족 그룹** | **1 / 43** (`코스피 200`) |
| 07:20 배치 실제 갱신 대상 | **41종** (`seed ∪ holdings`) |
| 배치 대상 ∩ `n≥2` 대상 | **6종** — 나머지 **190종이 배치 밖** |

→ **`INDEX_LEADERSHIP` 은 Gate 에서 `AVAILABLE` 이었지만 운영에서는 사실상
산출되지 않는다.** 유일하게 남는 `코스피 200` 은 시장 전체 지수라 "최근 강한
기초지수" 로서 의미가 없다. 상세와 보완안은 **§G**.

> `02B-1` Gate 가 `AVAILABLE` 을 낸 것은 **로컬 Mac DB**(당시 최신 2026-09-04)로
> 계산했기 때문이다. Gate 판정 자체는 데이터 구조상 옳지만, **운영 공급을 함께
> 보지 않았다.**

### [V1.2] 확정 — **모호점 없음**

| # | 항목 | 확정 |
|---|---|---|
| Q1 | 국내 거래일 Gate | **구현은 진행 · 활성화만 차단.** 로더·Gate·fail-closed 를 fixture 로 구현·검증 |
| Q2 | 미국 지수 | 3종(`US500`·`IXIC`·`^SOX`) · 07:20 배치 |
| Q3 | 기존 조립기 | 분기 제외 · 함수 존치 |
| **Q4** | 기초지수 가격 공급 | **C안 — KRX 일별 전종목 · 신규 테이블 별도 계열** |

```text
INDEX_LEADERSHIP_GATE      = AVAILABLE
INDEX_LEADERSHIP_OPERATION = CURRENTLY_UNAVAILABLE   (신규 계열 적재 후 재산출)
IMPLEMENTATION_BLOCKED     = false
ACTIVATION_BLOCKED         = true
BLOCK_REASON               = KRX_TRADING_CALENDAR_NOT_PROVIDED
```

`02B-1` Gate 판정을 뒤집지 않는다. 당시 판정은 **산출 구조와 데이터 확보
가능성**에 대한 것이고, 이번 실측은 **OCI 운영 공급 경로가 추가로 필요**하다는
사실을 확인한 것이다.

---

# A. 현재 구현 사실 (실측)

## A-1. `market_briefing` 의 현재 OCI 실행 경로

OCI cron (2026-09-11 실측) — **시각 변경 없음**:

```text
0 8 * * 1-5  run_three_push_runtime_oci.py --push-kind market_briefing --mode send
```

`scripts/run_three_push_runtime_oci.py` (**637줄**) 내부 순서:

| 절 | 줄 | 내용 | `market_briefing` 해당 |
|---|---:|---|---|
| §1 | 206 | active PARAM 로드 | O |
| §1-b | 224 | slot_id 계약 (holdings 만) | X |
| §2 | 243 | PARAM `enabled_push_kinds` 확인 | O |
| §3 | 252 | runtime 가격 조회 | **X — 조기 반환** |
| §3-a2 | 285 | Spike freshness guard | X |
| §3-b | 302 | Universe re-evaluator | X |
| §3-c | 320 | 보유 브리핑 조립 | X |
| §3-d | 350 | 보유 급락 알림 조립 | X |
| **§4** | **374** | **evidence 조립 + 본문 생성** | **O** |
| §4-c | 408 | 금지 문구 검사 | O |
| §4-b | 414 | raw 식별자 차단 | O |
| §5 | 423 | dry-run 종료 | O |
| **§6** | **436** | **enable flag guard** | **O** |
| §6-b | 446 | no-signal guard (spike 만) | X |
| §6-c | 472 | 보유 비거래일·skip 판정 | X |
| §7 | 513 | duplicate guard | O (일 단위) |
| §8 | 554 | Telegram 발송 + 성공 후 기록 | O |

## A-2. 실제 호출 파일·함수

```text
runner §4
 └─ app/three_push_runtime/runner_evidence.compose_evidence_and_message   (129줄)
     ├─ app/runtime_evidence/composer.compose_runtime_evidence            (298줄)
     │   └─ app/runtime_evidence/market_discovery.compose_market_discovery (105줄)
     │       └─ topn_fn = app.market_topn._compute_topn
     │           └─ app/market_regime.compute_market_context              (470줄)
     └─ app/three_push_runtime_message_builder.build_runtime_message      (203줄)
```

- `_MD_PUSH_KINDS = {"market_briefing"}` (`composer.py:53`) — 시장 브리핑만
  `compose_market_discovery` 를 탄다.
- `SKIP_EVIDENCE_KINDS = ("holdings_briefing", "holdings_risk_alert")`
  (`runner_evidence.py:15`) — **시장 브리핑은 이 경로를 탄다.**

## A-3. 외부 조회 위치

| 위치 | 외부 조회 |
|---|---|
| `price_refresh.refresh_runtime_quotes` | **`market_briefing` 은 조기 반환** — Naver 조회 **0건** |
| `compose_market_discovery` | **SQLite read only** (`market_data.sqlite`) |
| runner 전체 | 시장 브리핑 경로에 **외부 HTTP 조회 없음** |

> **`02B-2` 는 여기에 KRX Open API 일별 조회를 새로 추가해야 한다.** 현재 시장
> 브리핑 경로에는 외부 조회가 전혀 없다.

## A-4. freshness 판정 위치

| 대상 | 위치 | 상태 |
|---|---|---|
| benchmark(KOSPI·VIX) | `app/market_benchmark_freshness.py` (**122줄**, `02B-1` 신설) | **재사용** |
| KODEX200/KOSPI 수익률 | `market_regime.compute_kospi_metrics` — stale 이면 `status="stale"` | **재사용** |
| 배치 benchmark 갱신 | `app/market_benchmark_batch.py` (07:20) | 유지 |
| Spike artifact freshness | `spike_freshness.py` | 무관 |

`compose_market_discovery` 는 `kospi.get("status") == "ok"` 일 때만 문장을
만든다 → **`02B-1` 수정으로 stale KOSPI 문장은 이미 차단**된다.

## A-5. flag guard 위치

`run_three_push_runtime_oci.py:436` §6 — 전역 `PUSH_AUTOSEND_ENABLED` →
`PUSH_KIND_FLAG_ENVS[push_kind]`. OCI 실측 `PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED=false`.

## A-6. registry · history · state 저장 위치

| 대상 | 위치 |
|---|---|
| history JSONL | `_HISTORY_PATH = STATE_DIR/"oci_runtime_history.jsonl"` — `_finish()` 에서 **항상** 기록 |
| 상태 DB | `insert_status_from_record(record)` — `_finish()` 에서 **항상** |
| registry 중복키 | §7 `runner_duplicate.check_plain_duplicate` — 시장 브리핑은 **슬롯 접미 없음(일 단위)** |
| registry 기록 | §8 `record_send_success` → `mark_sent` — **발송 성공 뒤에만** |
| suppression state | 보유 `holdings_selection_state_latest.json` · 급락 `holdings_risk_state_latest.json` — **시장 브리핑용 파일은 없다** |

> **history/상태DB 는 항상 기록되고, registry/suppression 은 발송 성공 뒤에만**
> 기록된다. 설계 §6 의 "history 와 suppression state 를 같은 것으로 취급하지
> 않는다" 는 **이미 구조가 그렇다.**

## A-7. 기존 조립기 — 폐기 / 재사용

| 대상 | 판단 | 근거 |
|---|---|---|
| `build_runtime_message` (203줄) | **폐기** (시장 브리핑 한정) | `확인된 항목 / 별도 확인 필요` 목록 생성기다. 설계 §3.4 가 금지 |
| `compose_market_discovery` (105줄) | **폐기** (시장 브리핑 한정) | KODEX200/KOSPI 1m·3m + TOP 후보 나열. 새 계약과 내용이 다르다 |
| `compose_runtime_evidence` | **분기 축소** | `_MD_PUSH_KINDS` 에서 `market_briefing` 을 빼고 신규 조립기로 |
| `runner_evidence.SKIP_EVIDENCE_KINDS` | **확장** | `market_briefing` 추가 → 기존 §4 경로 미사용 |
| `app/market_benchmark_freshness.py` | **재사용** | `02B-1` 검증 완료 |
| `holdings_risk_state.py` 패턴 | **패턴 재사용** | fingerprint·발송 성공 후 저장 |
| `holdings_risk_flow.py` 패턴 | **패턴 재사용** | 조립은 helper, 판정은 runner §6-c |
| `runner_duplicate` 일 단위 키 | **재사용** | 슬롯 접미 없음 |
| `app/message_market_briefing.py` (283줄) | **무관** | PC 패키지 경로. OCI 미사용 |
| `scripts/ops02b1_gate/reproduce.py` | **로직 참조** | 필터·그룹·중앙값 계약 — **import 하지 않는다**(분석 스크립트) |

## A-8. 관련 파일 현재 줄 수 (실측 2026-09-11)

| 파일 | 줄 |
|---|---:|
| `scripts/run_three_push_runtime_oci.py` | **637** |
| `app/runtime_evidence/composer.py` | 298 |
| `app/runtime_evidence/market_discovery.py` | 105 |
| `app/three_push_runtime_message_builder.py` | 203 |
| `app/three_push_runtime/runner_evidence.py` | 129 |
| `app/three_push_runtime/runner_duplicate.py` | 68 |
| `app/market_benchmark_freshness.py` | 122 |
| `app/runtime_evidence/holdings_risk_state.py` | 190 |
| `app/runtime_evidence/holdings_risk_flow.py` | 236 |

**KS-10** — 러너 637줄. 임계 650 까지 **13줄** 여유뿐이다.

## A-9. 08:00 국내 휴장일 판정 — **기존 경로 없음**

| 확인 | 결과 |
|---|---|
| 기존 판정 함수 | `holdings_selection_flow.check_non_trading_day` → `non_trading_day.detect_non_trading_day` |
| 판정 근거 | **이미 가져온 quote 의 `price_asof`** ("신규 휴장일 캘린더·신규 외부 조회 없음" — 모듈 docstring) |
| 08:00 적용 가능? | **불가.** 시장 개장(09:00) 전이라 **어느 날이든 오늘 quote 가 0건**이다. 거래일에도 "비거래일" 로 읽힌다 |
| `market_briefing` 의 quote | `price_refresh` 가 **조기 반환** → `market_quotes` 가 **항상 비어 있다** |
| 가격 축으로 판정? | **불가.** `etf_daily_price` 에 **오늘 행이 없다**(장 마감 후 적재). 최신 `2026-09-04` |
| 휴장일 캘린더 | 저장소에 **없음** (grep 0건) |
| cron | `1-5` 이므로 **주말만** 걸러진다. **공휴일은 걸러지지 않는다** |

→ **Q1 (§F)**. 설계 §7 이 "기존 경로가 없으면 신규 캘린더·source 를 임의 추가하지
말고 모호점으로 보고" 라고 했으므로 그대로 보고한다.

---

# B. [V1.1] 변경 계획

> 상세 근거는 **§I**(runner 배선) · **§J**(모듈 축소).

| 파일 | 신규/수정 | 변경 책임 | 변경 이유 | 예상 줄 |
|---|---|---|---|---:|
| `app/market_briefing/meta_gate.py` | **신규** | KRX API 조회 · 기준일 bounded 역탐색 · CSV 대조 · `CSV_REFRESH_REQUIRED` · coverage | 외부 I/O 경계 일원화 (§5.2) | ~170 |
| `app/market_briefing/evidence.py` | **신규** | `SP500_SIGN_V1` 방향 + 기초지수 산출 | 순수 계산 (§3.2·§4) | ~190 |
| `app/market_briefing/render.py` | **신규** | 본문 · 부분 산출 6분기 · 안내 문구 4종 | 문구가 계산에 영향 주지 않게 | ~140 |
| `app/market_briefing/flow.py` | **신규** | 조립 흐름 · fingerprint · 억제 · 상태 저장 | runner 가 1회만 호출 (§7) | ~210 |
| `scripts/run_three_push_runtime_oci.py` | **수정** | §4 분기 교체 · §6-c 판정 · §8 배선 | **순증가 +15 내외** (§I-1) | +15 |
| **`app/market_benchmark_batch.py`** | **수정** | **미국 지수 3종 07:20 갱신** (`US500`·`IXIC`·`^SOX`) | Q2 확정 (§F-Q2) | ~+90 |
| **`app/market_benchmark_freshness.py`** | **수정** | 미국 benchmark 정적 catalog (timezone·종료시각) | `zoneinfo`·DST | ~+30 |
| `scripts/run_oci_market_data_batch.py` | 수정 | 미국 지수 결과를 **별도 상태로 기록** | 실패 은폐·rollback 금지 | ~+10 |
| `app/three_push_runtime/runner_evidence.py` | 수정 | `SKIP_EVIDENCE_KINDS` 에 `market_briefing` | 구 조립기 우회 | +2 |
| `app/runtime_evidence/composer.py` | 수정 | `_MD_PUSH_KINDS` 에서 제거 | 구 evidence 폐기 | −1 |
| `tests/test_market_briefing_*.py` | **신규** | 계약 37종 + 역검증 | §E·§K | ~850 |
| `docs/PROGRAM_TRUTH.md` | 수정 | C-1 본문 계약 · C-2 플래그 | 기능 변경 | — |

**Q1·Q4 확정 시 추가될 수 있는 것**

| 조건 | 추가 |
|---|---|
| Q1-(a) 채택 | `state/market_meta/krx_trading_days_*.csv` + 로더 (~60줄) |
| Q4-A/B 채택 | `collect_approved_tickers` 확장 (~20줄) |
| Q4-C 채택 | **별도 가격 계열 저장** — 설계자 확정 필요 |

| 항목 | 값 |
|---|---:|
| **신규 production 코드** | **~710줄** (V1 940 대비 −230) |
| 기존 파일 수정 합계 | **~+146줄** |
| 러너 순증가 | **+15 내외** · 최종 **650 이하 유지 필수** |

**schema 변경 없음** — `market_benchmark_daily_price` 는 **행 추가**이고
timezone·종료시각·freshness 규칙은 **코드 정적 catalog** 다.

---

# C. 데이터 흐름

```text
① 원천
   KRX Open API (일별, 신규 외부 조회)  →  ticker + IDX_IND_NM
   versioned 공식 CSV                   →  지수산출기관·추적배수·복제방법·기초자산분류
   market_data.sqlite (read only)       →  ETF 종가 · benchmark
   FDR? → **아니다.** 미국 지수는 benchmark 테이블에서 읽는다 (Q2)
       ↓
② freshness      benchmark 별 as_of_date + stale 판정  (market_benchmark_freshness)
       ↓
③ API·CSV 정합성  API-only ticker / 지수명 불일치 / coverage
       ↓
④ evidence       outlook_state(UP|DOWN|NONE) · index 후보 최대 2 · 근거 지수
       ↓
⑤ 메시지         render (부분 산출 6분기)
       ↓
⑥ fingerprint    "{outlook}#{index_state}"
       ↓
⑦ flag guard     전역 + 종류별  ← **여기가 최초 차단 지점**
       ↓
⑧ suppression    no_change 판정
       ↓
⑨ Telegram
       ↓
⑩ 성공 후        registry mark_sent + state 저장
```

| 단계 | 입력 | 출력 | 실패 상태 |
|---|---|---|---|
| ① | — | `api_rows` · `csv_rows` · DB | `api_fetch_failed` (빈 응답 포함) |
| ② | benchmark history + 거래일 축 | `as_of_date` · `is_fresh` | `stale` |
| ③ | ①의 두 목록 | `matched` · `api_only` · `mismatch` · `coverage` | `CSV_REFRESH_REQUIRED` · `coverage_below_threshold` |
| ④ | ②③ + 종가 | `outlook_state` · `index_candidates` | `outlook_unavailable` · `index_block_unavailable` |
| ⑤ | ④ | `message_text` | `no_publishable_sentence` |
| ⑥ | ④ | `state_fingerprint` | — |
| ⑦ | env | 통과/차단 | `autosend_disabled` · `push_kind_disabled` |
| ⑧ | ⑥ + 이전 상태 | 발송 여부 | `no_change` |
| ⑨ | ⑤ | `sent` · `partial` | `telegram_send_error` |
| ⑩ | ⑨ 성공 | registry + state | `state_write_failed` (**발송 사실과 분리 기록**) |

**①~⑥ 은 조립이고 판정하지 않는다.** 모든 skip·fail 결정은 **⑦ 뒤**다 (설계 §7).

---

# D. 상태 결정표 — **§H 로 대체됨 (V1.1)**

> V1 의 `D-3`("fingerprint 동일이면 **어떤 조합이든** `no_change`")과
> `sent + partial_delivery` 조합은 **설계자 §6 에서 기각**됐다. 현행 결정표와
> 우선순위는 **§H** 다. 이 절은 이력으로만 남긴다.

---

# E. 테스트·역검증 계획

## E-1. 계약 ↔ 테스트 ↔ 보호 분기 매핑

| # | 계약 | 테스트명 | 무력화할 실제 보호 분기 |
|---|---|---|---|
| 1 | 상승·하락 문구 | `test_outlook_up_down_sentence` | `outlook.direction_sentence` 분기 |
| 2 | `MIXED` 미사용 | `test_no_mixed_state_anywhere` | `outlook_state` 허용집합 |
| 3 | 예상 등락률 미출력 | `test_body_has_no_predicted_pct` | `render` 금지 패턴 |
| 4 | Nasdaq·반도체 미개입 | `test_other_indices_do_not_change_direction` | `outlook.decide` 입력 |
| 5 | `n=1` 제외·fallback 금지 | `test_single_ticker_index_excluded` | `MIN_TICKERS_PER_INDEX` 비교 |
| 6 | 5일/20일 ≤0 제외 | `test_nonpositive_return_excluded` | `m5>0 and m20>0` |
| 7 | 상위 2개·결정적 동률 | `test_tie_break_is_deterministic` | 정렬 키 3단 |
| 8 | 정상 0개 문단 생략 | `test_zero_candidate_omits_block` | `render` 분기 |
| 9 | API-only 감지 | `test_api_only_ticker_detected` | `krx_meta_sync` 집합 차 |
| 10 | 지수명 불일치 → `CSV_REFRESH_REQUIRED` | `test_name_mismatch_sets_refresh_required` | 불일치 판정 |
| 11 | 1건이라도 불일치면 **전체 차단** | `test_single_mismatch_blocks_whole_block` | fallback 금지 분기 |
| 12 | coverage 95% 경계 | `test_coverage_boundary_95` | `>=` 비교 |
| 13 | API 실패 fail-closed | `test_api_failure_is_not_disguised_as_mismatch` | 예외 분류 |
| 14 | stale 문장 미생성 | `test_stale_benchmark_not_rendered` | freshness 게이트 |
| 15 | 기준일 위장 금지 | `test_distinct_asof_dates_shown_separately` | `기준` 렌더 |
| 16 | fingerprint 에 숫자 없음 | `test_fingerprint_excludes_numbers` | fingerprint 조립 |
| 17 | 숫자만 달라지면 `no_change` | `test_same_state_different_numbers_suppressed` | 비교 |
| 18 | 상태 변경 시 발송 | `test_changed_state_sends` | 비교 |
| 19 | 미발송·실패 시 상태 불변 | `test_state_unchanged_on_failure` | §8 저장 조건 |
| 20 | 전체 성공 뒤에만 저장 | `test_partial_delivery_does_not_save` | `partial_delivery` 분기 |
| 21 | flag guard 앞 조기 skip 금지 | `test_flag_block_precedes_all_skips` | runner §6-c 위치 |
| 22 | flow-through | `test_runner_flow_market_briefing` | 전체 배선 |
| 23 | 식별자·secret 미노출 | `test_no_raw_identifier_or_secret` | §4-b·§4-c |
| 24 | 기존 PUSH 회귀 없음 | 전체 회귀 | — |

## E-2. 역검증 운영 규칙

- 무력화 **전 PASS / 후 FAIL / 복원 후 PASS** 를 각 분기별로 제출
- **대상 보호 코드가 없으면 SKIP 아니라 실패**
- fixture 는 **기본값과 결과가 우연히 같지 않게** 구성
  (예: 후보 0개를 "필터로 걸러서" 만들고 "데이터가 없어서" 로 만들지 않는다)
- `atexit` + SIGTERM/SIGINT/SIGHUP 복원 · `__pycache__` 삭제 ·
  `PYTHONDONTWRITEBYTECODE=1`

## E-3. 격리

| 대상 | 방식 |
|---|---|
| sender | mock 주입 → **발송 0건**. 호출 본문을 리스트로 수집 |
| KRX API | `httpx` mock. **실조회 0건** |
| live 시장 DB | `02B-1` conftest 가드 재사용 + `db_path` tmp 주입 |
| live state | `market_briefing_state_latest.json` 경로를 `tmp_path` 로 monkeypatch + **conftest 변경 감지** (OPS-01A/02A 패턴) |
| 공식 CSV | `state/market_meta/` 원본 미변경. fixture 는 합성 |

---

# F. [V1.1] 모호점과 범위 영향

## Q1. 국내 거래일 Gate — **공식 자료를 확보하지 못했다**

설계자 판정: 문제 수용, 개발자 권고안(문구 우회) **기각**. 이유에 동의한다 —
한국 휴장 중 미국시장이 추가로 열리면 확인한 S&P500 방향이 **실제 다음 한국
개장 직전의 방향이 아니다.** `SP500_SIGN_V1` 검증 조건과 달라진다.

### 확정 계약 (설계자 §1) — 그대로 반영

| # | 계약 |
|---|---|
| 1 | KST 실행일이 **실제 KRX 거래일**인 경우에만 발송 가능 |
| 2 | 휴장일이면 `skipped/non_trading_day` |
| 3 | 휴장일에 **suppression state·registry 불변** |
| 4 | 캘린더 없음·적용 연도 누락 → **fail-closed**, reason `KRX_CALENDAR_REFRESH_REQUIRED` |
| 5 | 런타임 브라우저 조회·매일 자동 다운로드 **금지** |
| 6 | 공식 KRX 기준 **저빈도 versioned 거래일 snapshot** |
| 7 | snapshot 에 원천·대상 연도·기준일·hash·행 수 기록 |
| 8 | 공휴일 패키지·미국시장 일정으로 **추정 금지** |

문구도 확정대로 쓴다 — `직전 미국 거래일 S&P500 {상승|하락}은 오늘 한국 개장에
{상승|하락} 압력으로 해석됩니다.` **거래일 Gate 통과일에만** 사용한다.

### 원천 조사 결과 (읽기 전용 probe)

| 후보 | 결과 |
|---|---|
| **KRX Open API 휴장일·거래일 서비스** | **없음.** `gen/hldy` · `gen/holiday` · `cal/hldy` 전부 **HTTP 404** |
| KRX 지수 일별시세(`idx/krx_dd_trd`) | **과거 거래일은 복원 가능.** `20260101`(신정) `rows=0` · `20260102` `rows=40` · `20260904` `rows=40` |
| 동 API 로 **오늘** 판정 | **불가.** `20260911`(오늘 08시대) `rows=0` — **거래일이어도 장중 데이터가 아직 없다.** 빈 응답 = 휴장일이 **아니다** |
| KRX 정보데이터시스템 웹 휴장일 화면 | **로그인 필요** (`02B-1` 실측: 세션 쿠키 확보 후에도 `HTTP 400 LOGOUT`) |
| 저장소 내 캘린더 | **없음** (grep 0건) |

### 판정: **`BLOCKED`**

설계자 §1 은 "적절한 공식 자료를 확보할 수 없다면 임의 대체하지 말고 `BLOCKED`
로 반환" 이라 했다. **API 로는 확보되지 않는다.**

**남은 유일한 경로는 공식 CSV 와 같은 방식** — KRX 가 연초 공표하는 **휴장일
안내를 사용자가 1회 내려받아** versioned snapshot 으로 두는 것이다. 이는
§5 의 "런타임 조회·매일 자동 다운로드 금지" 와 충돌하지 않는다(저빈도·수동).

**확정 요청** — 아래 중 어느 쪽인가.

- **(a)** 사용자에게 **KRX 공식 휴장일 자료 1회 제공**을 요청하고, 공식 CSV 와
  같은 versioned snapshot 계약(원천·연도·기준일·hash·행 수)으로 관리
- **(b)** `02B-2` 를 **거래일 Gate 없이는 진행하지 않고** 대기
- **(c)** 다른 공식 원천 지정

**개발자 의견: (a).** 설계자가 이미 CSV 에 같은 방식을 허용했고, 연 1회
갱신이면 운영 부담이 없다. 다만 **사용자에게 자료를 요청하는 것**이므로
개발자가 정할 수 없다.

## Q2. 미국 지수 — **확정됨** (설계자 §2)

| 표시 역할 | benchmark | symbol |
|---|---|---|
| 운영 방향 규칙 | S&P500 | `US500` |
| 선택적 근거 | Nasdaq | `IXIC` |
| 선택적 근거 | 반도체지수 | `^SOX` |

**Russell 2000·USD/KRW 는 추가하지 않는다.** VIX 는 기존 계약 유지.

**표현 정정** — V1 의 "`benchmark_id` 추가" 는 **schema 변경이 아니다.**
`market_benchmark_daily_price` 의 **행 추가**이고, timezone·종료시각·freshness
규칙은 **코드의 정적 catalog** 로 둔다(`02B-1` §12.2 확정 방식 그대로).

### 07:20 갱신 계약 (설계자 §2 그대로)

FDR 은 `02B-1` 에서 identity 가 확인된 **동일 원천만** · 미국 세션 날짜는
`America/New_York` · DST 는 `zoneinfo` · **최근 구간만** 조회해 최신·직전 미국
거래일 종가 확보 · **전체 과거 backfill 금지** · 1일 수익률에 필요한 **최소
구간만** 초기 적재 · benchmark 별 `source_latest_asof`·수집 시각·행 수·결측·상태
기록 · **당일 배치 성공 + 최신·직전 두 세션 모두 존재**해야 사용 · 미래 날짜·중복
날짜·종가 결측·조회 실패는 **fail-closed** · S&P500 unavailable 이면 전망
**`NONE`** · Nasdaq·반도체는 각각 fresh 일 때만 근거 줄 · **두 지수 실패가
S&P500 방향을 바꾸지 않음** · 미국 지수 실패를 **ETF·KOSPI·VIX 성공으로 숨기지
않음** · 미국 지수 실패로 **기존 배치 성공분 rollback 금지**.

`최근 S&P500` 표현을 **폐기**하고 전부 **`직전 미국 거래일의 1일 종가 수익률`**
로 통일한다.

**0 처리** — 임의 중립 구간을 만들지 않고 **`NONE/flat`** 으로 구분한다.

| 상황 | 문구 |
|---|---|
| 보합(정확히 0) | `직전 미국 거래일 S&P500이 보합이어서 최근 강한 기초지수만 확인합니다.` |
| stale·unavailable | `미국시장 방향 근거가 최신성 조건을 충족하지 않아 최근 강한 기초지수만 확인합니다.` |

## Q3. 기존 조립기 — **확정됨** (개발자 권고 수용)

`market_briefing` 만 기존 분기에서 제외 · `build_runtime_message` **존치** ·
`compose_market_discovery` **존치** · **파일 삭제 없음** · spike 잔존 경로
변경 없음 · 미사용 후보가 되어도 **이번 Step 에서 정리·삭제하지 않는다.**

> 이번 Step 은 기존 코드 청소 Step 이 아니다.

## Q4. **기초지수 가격 공급** — 신규 (§G)

§G 참조. **확정 필요.**

## 신규 source·DB·dependency

| 항목 | 판단 |
|---|---|
| 신규 dependency | **불필요** — `httpx`·`numpy`·`finance-datareader` 기존 선언 |
| 신규 테이블·schema 변경 | **없음** — `market_benchmark_daily_price` 에 **행 추가** |
| 신규 외부 source | KRX Open API 는 `02B-1` 승인·사용 중. **FDR 도 기존** |
| 신규 endpoint | 불필요 |
| **거래일 캘린더** | **Q1 — 공식 자료 미확보. `BLOCKED`** |

## 비차단 BACKLOG

| 항목 | 이번 Step 을 막는가 |
|---|---|
| `DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY` 본조사 | **막지 않는다** — 기초지수 수익률은 DB 단일 계열 상대 계산이라 균일 배수가 상쇄된다 |
| 분배락 민감도 | **막지 않는다** — `02B-2` 는 방향 부호만 쓴다 |
| **`DEF-FDR-TIMEOUT`** | **§G-4 에서 판정** |

---

# G. [V1.1] 운영 가격 공급 실측 — 설계자 §4

**OCI 읽기 전용.** `etf_daily_price` 전역 최신일 한 건이 아니라 **ticker 별·그룹
별** 로 측정했다.

## G-1. 실측 (2026-09-11, OCI)

| 항목 | 값 |
|---|---:|
| 전역 `MAX(date)` | `2026-09-10` |
| `n≥2` 그룹 distinct ticker | **196** |
| DB 에 존재 | 191 |
| **DB 에 아예 없음** | **5** |
| **최신 거래일 일치** | **6 (3.1%)** |
| `2026-07-03` 에 멈춤 | **185** |
| **5일·20일 계산 가능**(최신일 일치 + 21행 이상) | **6 (3.1%)** |
| **그룹별 fresh ≥2 충족** | **1 / 43** |
| 충족 그룹 | `코스피 200` (KRX) |

## G-2. 원인 — 배치 대상이 좁다

```text
07:20 배치 갱신 대상 = collect_approved_tickers() = seed ∪ holdings = 41종
```

| 교집합 | 값 |
|---|---:|
| 배치 대상 | **41** |
| 배치 ∩ `n≥2` 대상 | **6** |
| **`n≥2` 대상 중 배치 밖** | **190** |
| 배치 대상 6종의 최신일 일치 | **6 / 6** |
| `etf_master` 전체 | 1,146 |

**배치는 정상 동작한다. 대상이 좁을 뿐이다.** 배치에 포함된 6종은 모두 최신이다.
나머지 185종이 `2026-07-03` 에 멈춘 것은 **`POST /market/refresh`(Mac 수동)가
그 뒤로 돌지 않았기 때문**이다 — KOSPI·VIX 가 멈춘 날짜와 같다.

## G-3. 결론 — **현재 구조로는 기초지수 블록이 성립하지 않는다**

`n≥2` 43그룹 중 실제 산출 가능한 것은 **1그룹**이고, 그것도 `코스피 200`
(시장 전체 지수)이다. **"최근 강한 기초지수" 로서 정보 가치가 없다.**

**설계자 §4 금지 우회 — 전부 하지 않는다**

| 금지 | 준수 |
|---|---|
| KRX 무조정 종가를 기존 조정 계열 뒤에 붙이기 | **안 한다** |
| stale ETF 를 후보 계산에 포함 | **안 한다** |
| fresh ticker 하나로 `n=2` 유지 | **안 한다** |
| 측정 없이 전체 ETF 갱신을 배치에 추가 | **측정 후 §G-4 제시** |
| `DEF-FDR-TIMEOUT` 미측정 상태로 FDR 확대 | **§G-4 에서 판정** |

## G-4. 최소 보완안 (확정 필요 — **Q4**)

| 안 | 내용 | 추가 조회량 | 예상 배치 시간 | 위험 |
|---|---|---:|---|---|
| **A** | 배치 대상에 **`n≥2` 그룹 ticker 196종**만 추가 | +190종 | FDR 병렬 미사용 시 **수 분 추정**(미측정) | 대상이 메타데이터에 종속 — CSV 교체 시 대상이 바뀐다 |
| **B** | 배치 대상을 **`etf_master` 전체 1,146종**으로 확대 | +1,105종 | **미측정.** 현재 41종 대비 28배 | 07:20~08:00 창을 넘길 위험 · `DEF-FDR-TIMEOUT` 직격 |
| **C** | **KRX Open API 일별 전종목**(1일 1회 호출, 1,167행)으로 종가 확보 | **+1 호출** | **0.3초** (`02B-1` 실측) | **가격 계열이 KRX 무조정** — DB 조정 계열과 혼합 금지(설계자 §4) → **별도 계열로 분리 저장 필요** |
| **D** | 기초지수 블록을 **이번 Step 범위에서 제외**하고 전망만 발송 | 0 | 0 | `INDEX_LEADERSHIP=AVAILABLE` 판정과 어긋남 |

**개발자 의견** — **C 가 조회량·시간 면에서 압도적**이다(1 호출 0.3초 vs 190~1,105
종목 개별 조회). `02B-1` 에서 **KRX API 가 시가·종가를 무조정 단일 기준으로
준다**는 것을 이미 확인했다. 다만 설계자가 "**KRX 무조정 종가 한 행을 기존 조정
가격계열 뒤에 붙이기**" 를 금지했으므로, C 를 쓰려면 **별도 계열(테이블 또는
`source` 구분)로 저장하고 기초지수 수익률을 그 계열 안에서만 계산**해야 한다.
이는 **신규 테이블 논의**가 되므로 개발자가 정할 수 없다.

**`DEF-FDR-TIMEOUT` 판정** — **A·B 를 택하면 막을 가능성이 있다**(FDR 조회량이
4.8~28배). **C 를 택하면 FDR 조회가 늘지 않으므로 막지 않는다.** 현재 측정으로는
**C 기준 비차단**이다.

**확정 요청** — A / B / C / D 중 어느 쪽인가. C 라면 별도 계열 저장을 허용하는가.

## G-5. 공식 CSV·API 의 OCI 운영 경로

| 항목 | 실측 |
|---|---|
| 저장소 경로 | `state/market_meta/krx_etf_basic_20260909.csv` (1,168행 · `bf07e52b…`) |
| **OCI 경로** | **존재하지 않는다.** OCI HEAD `5d2614d6`(2026-09-08) — 저장소 HEAD 대비 **8커밋 뒤짐** |
| 배포 방식 | **수동.** cron·systemd timer 에 `git pull` **없음** (실측) |
| 정정 | 기존 PLAN §11.3 의 "OCI 자동 pull 확인됨" 은 **오기였다.** 같은 날 수동 배포를 자동으로 오인했다 |

→ `02B-2` 배포 시 **`state/market_meta/` 와 거래일 snapshot 이 OCI 에 반드시
올라가야 한다.** OCI 가 읽을 경로는 저장소와 동일한 상대경로다.

## G-6. KRX API 기준일(`basDd`) 결정 방식

**당일을 그대로 넣으면 안 된다.** 실측:

| `basDd` | 응답 | 의미 |
|---|---:|---|
| `20260911` (오늘 08시대) | **rows=0** | **거래일이어도 장중 데이터가 아직 없다** |
| `20260101` (신정) | rows=0 | 휴장일 |
| `20260902`·`20260904` | rows≈1,167 | 거래일 |

**빈 응답만으로 휴장일·조회 실패·universe 0건을 구분할 수 없다.**

**제안 — bounded 역탐색**

```text
d = 국내 가격 기준일(etf_daily_price MAX(date))       # 이미 완료된 거래일
for i in range(0, MAX_LOOKBACK=7):
    후보 = d - i영업일
    API(basDd=후보) rows > 0 이면 채택하고 종료
없으면 api_fetch_failed (fail-closed)
```

- **당일을 넣지 않는다.** 시작점은 **이미 완료된 국내 거래일**이다
- 최대 7회로 **bounded** — 무한 역탐색 금지
- **API 응답 날짜 ≠ 국내 가격 기준일**이면 → 두 날짜를 **모두 evidence 에 남기고**
  기초지수 블록은 **가격 기준일** 기준으로 계산한다. 메시지 `기준` 줄에도
  실제 날짜를 분리 표시한다
- 7회 내 성공 응답이 없으면 **`api_fetch_failed`** — `CSV_REFRESH_REQUIRED` 로
  위장하지 않는다

**coverage 분모·분자**

```text
분모 = API 응답 ticker 전체
분자 = API ↔ CSV 가 ticker 로 join 되고 기초지수명까지 완전일치한 수
coverage = 분자 / 분모        (95% 미만이면 블록 전체 미산출)
```

API-only ticker 수 = `분모 − (API∩CSV)` · 지수명 불일치 수 = `(API∩CSV) − 분자`.
**세 수치를 모두 evidence 에 기록**하고 손으로 옮겨 적지 않는다.

---

# H. [V1.1] 상태 결정 우선순위 — 수정

V1 의 `D-3`(fingerprint 동일이면 **어떤 조합이든** `no_change`)은 **잘못됐다.**
`NONE#NONE` 이 같다는 이유로 `no_publishable_content` 를 `no_change` 로 바꾸면
안 된다.

**fingerprint 비교는 발송 가능한 본문이 만들어진 경우에만 수행한다.**

```text
① evidence·freshness·본문 후보 조립        (판정하지 않는다)
② flag guard                              autosend_disabled / push_kind_disabled
③ non_trading_day / calendar unavailable  non_trading_day / KRX_CALENDAR_REFRESH_REQUIRED
④ all_data_stale / no_publishable_content / generation failure
⑤ fingerprint no_change
⑥ registry duplicate                      duplicate_runtime
⑦ Telegram
⑧ 전체 성공 후 registry·suppression state 저장
```

| 우선순위 | status | reason | 발송 | history | registry | state |
|---:|---|---|---|---|---|---|
| ② | `skipped` | `autosend_disabled` / `push_kind_disabled` | X | O | X | 불변 |
| ③ | `skipped` | `non_trading_day` / `KRX_CALENDAR_REFRESH_REQUIRED` | X | O | X | **불변** |
| ④ | `skipped` | `all_data_stale` / `no_publishable_content` / `message_build_error` | X | O | X | 불변 |
| ⑤ | `skipped` | `no_change` | X | O | X | 불변 |
| ⑥ | `skipped` | `duplicate_runtime` | X | O | X | 불변 |
| ⑦ | `sent` / `failed` | — / `telegram_send_error` | O / X | O | 성공 시만 | 성공 시만 |

## H-1. partial delivery — 수정

**`sent + partial_delivery` 조합을 제거한다.**

| 항목 | 값 |
|---|---|
| status | **`failed`** (비성공) |
| reason | **`partial_delivery`** |
| 일부 전달 사실 | **별도 필드**(`telegram_partial_delivery=true`)에 기록 |
| registry | **불변** |
| suppression state | **불변** |

## H-2. 안내 문구 (설계자 §8 확정)

| 내부 상태 | 사용자 문구 |
|---|---|
| `CSV_REFRESH_REQUIRED` | `기초지수 정보는 공식 기준정보 갱신이 필요해 제외했습니다.` |
| `coverage_below_threshold` | `기초지수 정보는 정합성 조건을 충족하지 않아 제외했습니다.` |
| `api_fetch_failed` | `기초지수 정보는 최신 기준을 확인하지 못해 제외했습니다.` |
| `stale` | `기초지수 정보는 최신성 조건을 충족하지 않아 제외했습니다.` |
| **정상 0개** | **안내 문구 없이 문단 자체 생략** |

---

# I. [V1.1] runner 배선 — 보유 PUSH 미변경

설계자 §7: 정상 운영 중인 **§3-c·§3-d 를 분리하는 안은 승인 불가.**

## I-1. 순증가 최소화 방식

기존 §4 분기가 시장 브리핑에 대해 **이미 `if push_kind not in SKIP_EVIDENCE_KINDS:`
블록을 차지하고 있다.** 새 조립기를 **그 자리에 교체**하면 순증가가 거의 없다.

```text
현재 §4 (17줄)                        변경 후 (18줄 예상)
  if push_kind not in SKIP_...:          if push_kind == "market_briefing":
      compose_evidence_and_message(...)      _masm = assemble_market_briefing(...)
      ...                                    record.update(_masm.diagnostics)
                                             market_fail = _masm.fail   # 판정은 §6-c
                                         elif push_kind not in SKIP_...:
                                             compose_evidence_and_message(...)
```

| 위치 | 변경 | 순증가 |
|---|---:|---:|
| §4 분기 교체 | 기존 블록 앞에 `elif` 추가 | **+6** |
| §6-c 판정 3분기 추가 | `market_fail` · 거래일 · `no_change` | **+9** |
| §8 상태 저장 배선 | `record_send_success` 에 위임 | **+0** (기존 `holdings_selection_ctx` 패턴 재사용) |
| **합계** | | **+15 내외** |

**637 + 15 = 652 → 임계 2줄 초과.** 따라서 다음 중 하나가 필요하다.

- **(a)** §8 의 `record_send_success` 호출 인자를 **dict 1개로 묶어** 러너에서
  12줄 → 3줄로 축약 (helper 내부만 바뀌고 **보유 PUSH 동작 불변**)
- **(b)** `market_briefing` 판정 3분기를 **helper 1함수**로 묶어 §6-c 에서 2줄로

**개발자 의견: (a)+(b) 병행.** 둘 다 **보유 PUSH 의 동작을 바꾸지 않고** 러너
줄 수만 줄인다. 그래도 650을 넘으면 **구현하지 않고 KS-10 선행 Cleanup 필요성을
보고**한다(설계자 §7).

## I-2. 기존 두 운영 PUSH 변경 범위

| 대상 | 변경 |
|---|---|
| §3-c 보유 브리핑 조립 | **없음** |
| §3-d 급락 알림 조립 | **없음** |
| §6-c 기존 3분기 | **없음** (뒤에 추가만) |
| `holdings_*` 모듈 | **없음** |
| `record_send_success` | (a) 채택 시 **인자 형태만** — 저장 조건·순서 불변 |

---

# J. [V1.1] 모듈 구성 — 축소

설계자 §7: "`SP500_SIGN_V1` 같은 단순 규칙까지 별도 120줄 모듈은 과도".
**6개 → 4개**로 줄인다.

| 모듈 | 책임 | 합칠 수 없는 이유 | 예상 줄 |
|---|---|---|---:|
| `app/market_briefing/meta_gate.py` | KRX API 조회 · CSV 대조 · `CSV_REFRESH_REQUIRED` · coverage · **기준일 역탐색** | **외부 I/O 경계.** 테스트에서 mock 대상이 여기 하나로 모여야 한다 | ~170 |
| `app/market_briefing/evidence.py` | **전망(`SP500_SIGN_V1`) + 기초지수 산출** | 둘 다 "숫자 → 상태" 순수 계산. 외부 I/O 없음 | ~190 |
| `app/market_briefing/render.py` | 본문 · 부분 산출 6분기 · 금지 표현 | 문구 변경이 계산에 영향 주지 않아야 한다 | ~140 |
| `app/market_briefing/flow.py` | 조립 흐름 + fingerprint·억제·상태 저장 | runner 가 **1회만** 호출하는 진입점 | ~210 |

| 항목 | 값 |
|---|---:|
| **신규 production 코드 총합** | **~710줄** (V1 940줄 대비 **−230**) |
| runner 순증가 | **+15 내외** (§I) |
| 기존 모듈 수정 | `runner_evidence.py` +2 · `composer.py` −1 |

**추상 계층 없이 직접적인 데이터 흐름인가** — 그렇다. 인터페이스·팩토리·플러그인
없이 **함수 호출 4단**(meta_gate → evidence → render → flow)이다. `02B-1` 의
`holdings_risk_*` 4모듈과 같은 형태다.

> `SP500_SIGN_V1` 은 **단일 함수**(~20줄)로 `evidence.py` 안에 둔다. 별도 모듈로
> 만들지 않는다.

---

# K. [V1.1] 테스트·역검증 추가분

§E 24종에 더해 이번 개정으로 다음이 추가된다.

| # | 계약 | 테스트 | 무력화할 보호 분기 |
|---|---|---|---|
| 25 | 휴장일 `skipped/non_trading_day` · **state·registry 불변** | `test_non_trading_day_blocks_and_keeps_state` | 거래일 Gate |
| 26 | 캘린더 없음 → `KRX_CALENDAR_REFRESH_REQUIRED` fail-closed | `test_missing_calendar_fails_closed` | 캘린더 로드 |
| 27 | **`no_publishable_content` 가 `no_change` 로 바뀌지 않음** | `test_empty_content_is_not_no_change` | 우선순위 ④→⑤ |
| 28 | fingerprint 비교는 **본문이 있을 때만** | `test_fingerprint_compared_only_when_publishable` | 〃 |
| 29 | partial delivery → **`failed`**, state·registry 불변 | `test_partial_delivery_is_failed_and_keeps_state` | 발송 결과 분기 |
| 30 | 미국 지수 **최신·직전 두 세션** 모두 있어야 사용 | `test_us_index_requires_two_sessions` | freshness 게이트 |
| 31 | S&P500 **0** → `NONE/flat` 전용 문구 | `test_flat_sp500_uses_flat_sentence` | 부호 분기 |
| 32 | Nasdaq·반도체 실패가 **방향을 바꾸지 않음** | `test_aux_index_failure_keeps_direction` | 방향 계산 입력 |
| 33 | 미국 지수 실패를 **ETF·KOSPI·VIX 성공으로 숨기지 않음** | `test_us_index_failure_recorded_separately` | 배치 상태 기록 |
| 34 | 미국 지수 실패로 **기존 배치 성공분 rollback 없음** | `test_us_index_failure_does_not_rollback` | 배치 예외 경계 |
| 35 | **당일을 `basDd` 로 넣지 않음** · bounded 역탐색 | `test_basdd_never_uses_today_and_is_bounded` | 기준일 선택 |
| 36 | 빈 응답을 **universe 0건으로 처리하지 않음** | `test_empty_api_response_is_fetch_failure` | 예외 분류 |
| 37 | 안내 문구 4종이 **내부 상태와 1:1** | `test_notice_sentence_matches_internal_state` | 렌더 분기 |

---

# L. [V1.1] 설계자 반환 항목 대조

| # | 요구 | 위치 |
|---|---|---|
| 1 | Q1 공식 KRX 거래일 자료 조사 결과 | **§F-Q1** — API 404 · 웹 로그인 필요 · **`BLOCKED`** |
| 2 | Q2 미국 지수 3종 배치·freshness 계약 | **§F-Q2** |
| 3 | **OCI 기초지수 ticker 별 가격 freshness 실측** | **§G-1 / §G-2** |
| 4 | 공식 CSV 의 OCI 운영 경로 | **§G-5** — **OCI 에 없음**, 배포 수동 |
| 5 | KRX API 기준일 선택 방식 | **§G-6** — bounded 역탐색 |
| 6 | 수정된 상태 결정 우선순위 | **§H** |
| 7 | partial delivery 상태 수정 | **§H-1** |
| 8 | 보유 PUSH 미변경 runner 배선안 | **§I** |
| 9 | 축소·정당화된 모듈 구성 | **§J** — 6→4개, ~710줄 |
| 10 | `market_benchmark_batch`·07:20 경로 반영 | **§B** |
| 11 | 테스트·역검증 추가분 | **§K** — 25~37 |
| 12 | 남은 모호점 | **Q1 · Q4** (아래) |

## 남은 모호점 **2건**

| # | 모호점 | 왜 개발자가 정할 수 없나 |
|---|---|---|
| **Q1** | 국내 거래일 Gate 공식 자료 | API 404·웹 로그인. 남은 경로는 **사용자에게 자료 요청** |
| **Q4** | 기초지수 가격 공급 (A/B/C/D) | C 는 **별도 가격 계열 저장** 논의 · A/B 는 `DEF-FDR-TIMEOUT` 위험 |

**두 건 모두 `02B-2` 진행을 막는다.**

- **Q1 미확정** → 거래일 Gate 를 만들 수 없다 → 설계자 §1 계약 미충족
- **Q4 미확정** → 기초지수 블록이 **운영에서 1그룹(`코스피 200`)만** 나온다

---

# M. [V1.2] 설계자 최종 확정 — 구현 계약

## M-1. 가격 공급 (Q4 = C안)

```text
PRICE_SUPPLY = KRX_DAILY_FULL_ETF_SNAPSHOT
PRICE_BASIS  = UNADJUSTED_TRADED_PRICE
STORAGE      = SEPARATE_SERIES
TABLE        = krx_etf_daily_price_unadjusted
```

| 필드 | 계약 |
|---|---|
| `date` | KRX 응답의 **실제 기준일** |
| `ticker` | ETF 종목코드 |
| `close` | 해당 거래일 **무조정 종가** |
| `source` | `KRX_OPEN_API` |
| `price_basis` | `UNADJUSTED_TRADED_PRICE` |
| `collected_at` | 실제 수집 시각 |
| 고유키 | `(date, ticker)` |

**격리 계약**

- `etf_daily_price` 와 **join 하여 하나의 시계열로 만들지 않는다**
- 기존 `etf_daily_price.open/close` 를 **수정·보완하지 않는다**
- 5일·20일 수익률의 **분자·분모 모두 신규 계열**에서
- 조정/무조정을 **구간 중간에서 연결하지 않는다**
- 이 테이블을 **다른 UI·ML·보유 PUSH 의 가격 source 로 확장하지 않는다**
- **`DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY` 가 해결됐다고 기록하지 않는다**
- 분배락 민감도는 **BACKLOG 유지**

**적재**

| 항목 | 값 |
|---|---|
| 20일 수익률 요건 | 최신일 포함 **21개 완료 거래일** |
| 최초 적재 | 21개 확보에 필요한 범위만 · **전체 backfill 금지** |
| 초기 역탐색 상한 | **40달력일** |
| 일별 역탐색 상한 | **7달력일** |
| 저장 범위 | 하루 응답의 **전체 ETF** (196종만 저장하지 않는다) |
| 재수집 | **idempotent** |
| fail-closed | 빈 응답 · ticker 중복 · 종가 결측 · 0 이하 · 응답 기준일 불일치 |
| OCI 초기 적재 | **별도 승인 대상 · 지금 수행하지 않는다** |

가격 저장과 후보 필터를 **분리**해, 메타데이터가 바뀌어도 가격 이력이 이어지게 한다.

## M-2. 07:20 응답 1회 재사용

07:20 배치가 받은 **최신 KRX 전종목 응답 하나**를 두 용도로 쓴다.

1. 신규 무조정 가격계열 **일별 적재**
2. API ticker·기초지수명과 공식 CSV **정합성 판정**

**08:00 runner 는 같은 API 를 다시 호출하지 않는다.** runner 가 읽는 것 —
07:20 snapshot 처리 상태 · API·CSV 정합성 결과 · 신규 무조정 계열 · 미국
benchmark 갱신 상태.

07:20 결과가 없거나 그날 배치가 실패했으면 **기초지수 블록 fail-closed**.
전망이 유효하면 **전망만 발송**할 수 있다.

## M-3. API 완전성 · coverage

기록할 값 — API ticker 수 · CSV ticker 수 · exact match 수 · **API-only** ·
**CSV-only** · 지수명 불일치 수 · join coverage.

```text
join_coverage = exact_match_count / max(api_ticker_count, csv_ticker_count)
```

| 조건 | 처리 |
|---|---|
| coverage **< 95%** | 기초지수 블록 **전체 미산출** |
| **API-only 또는 지수명 불일치 1건 이상** | **coverage 와 무관하게 `CSV_REFRESH_REQUIRED`** |
| CSV-only | 수량·목록 기록 + **coverage 에 반영** |
| API 부분 응답 의심(행 수 급감) | 위 coverage 에서 **fail-closed** |
| 정합성 실패 | 정상 수집된 가격 snapshot 을 **기존 계열과 섞지 않고**, 그 가격을 **PUSH 후보 계산에 쓰지 않는다** |

## M-4. 기초지수 산출 보완

- 최신일·5거래일 전·20거래일 전 가격을 **신규 KRX 계열에서만** 조회
- ticker 별 **세 기준 가격이 모두** 있어야 계산 가능
- 유효 distinct ticker **2개 이상**이어야 후보
- **stale·결측 ticker 를 `n` 에 포함하지 않는다**
- 그룹 수익률 = 유효 ETF 수익률 **중앙값**
- 5일·20일 중앙값이 **모두 양수**인 그룹만
- 20일 기준 **최대 2개**
- **`코스피 200` 이라는 이유만으로 임의 제외하지 않는다**
- **정보 가치가 낮다는 개발자 판단으로 필터를 추가하지 않는다** — 목업을 본 뒤
  사용자가 판정

**신규 무조정 계열로 최근 20거래일 후보 수와 실제 top 2 를 다시 산출해 제출**한다.
기존 조정계열 Gate 의 후보 수와 **같다고 가정하지 않는다.**

## M-5. Q1 — 구현 진행 · 활성화만 차단

| 구현 계약 | 내용 |
|---|---|
| 로더 | versioned KRX 거래일 snapshot |
| Gate | KST 실행일이 **거래일 목록에 있을 때만** 통과 |
| 휴장일 | `skipped/non_trading_day` |
| 파일 없음·손상·연도 누락 | `skipped/KRX_CALENDAR_REFRESH_REQUIRED` |
| 위 두 경우 | **registry·suppression state 불변** |
| fixture | 거래일과 휴장일이 **서로 다른 결과**를 내도록 |
| 금지 | 2026년 자료를 **추정값·빈 placeholder 로 만들지 않는다** · 공휴일 라이브러리·미국 일정·주말 규칙 대체 금지 · 런타임 다운로드·브라우저 자동화 없음 |

실제 공식 snapshot 은 **사용자 승인·제공 후 별도 반영**. 그전까지 autosend `false`.

## M-6. runner — (a) 기각, (b) 만

**`record_send_success` 인자 변경은 승인하지 않는다.** 공통 저장 helper 의 호출
계약을 바꾸면 운영 중인 두 PUSH 에 회귀 위험이 생긴다.

| 허용 | 금지 |
|---|---|
| market briefing **전용 판정 helper** | §3-c 보유 브리핑 변경 |
| 기존 market briefing 분기를 **helper 호출로 교체** | §3-d 급락 알림 변경 |
| | 공통 send-success 계약 변경 |
| | **다른 코드를 한 줄로 합쳐 줄 수만 맞추기** |

**runner 최종 650줄 이하.** 불가능하면 **구현을 멈추고 KS-10 선행 Cleanup
필요성을 보고**한다. 결과에 **모든 직접 변경 파일의 전·후 줄 수**를 제출한다.

## M-7. 모듈 책임 수정

`meta_gate` 는 **08:00 외부 조회 모듈이 아니라 07:20 정합성 결과를 소비하는
경계**다. 추가 책임 — 신규 무조정 가격 저장소 · 07:20 일별 전종목 수집 ·
정합성 상태 생성 · **초기 21거래일 bounded 적재** · 08:00 **read-only 소비**.

신규 코드가 예상보다 크게 늘거나 기존 핵심 모듈이 KS-10 근접·초과가 되면
**계속하지 말고 보고**한다.

## M-8. 추가 테스트 20종 (§K 37종에 더해)

38 신규 테이블과 `etf_daily_price` **완전 분리** · 39 신규 계산이 `etf_daily_price`
**미조회** · 40 21일 미만이면 20일 수익률 미산출 · 41 07:20 응답 **1회만** 사용 ·
42 **08:00 외부 KRX 조회 0건** · 43 ticker 중복·종가 결측·0 이하 fail-closed ·
44 부분 응답 coverage 차단 · 45 **API-only 1건 → `CSV_REFRESH_REQUIRED`** ·
46 CSV-only coverage 반영 · 47 **지수명 불일치 1건 → 블록 전체 차단** ·
48 정합성 실패 시 가격 미사용 · 49 세 기준 가격 모두 있어야 `n` 포함 ·
50 stale 제외 후 `n<2` 면 그룹 제외 · 51 **40/7달력일 bounded** ·
52 재실행 **idempotent** · 53 가격 적재 실패가 기존 성공분 **rollback 안 함** ·
54 **기존 `etf_daily_price` row count·값 불변** · 55 **캘린더 부재 + flag ON 이어도
발송 0건** · 56 휴장일·캘린더 누락 시 **registry·state 불변** ·
57 기존 두 PUSH **flow-through 회귀 없음**.

## M-9. OCI 상태 정정 (수용됨)

```text
OCI_AUTO_PULL  = false
OCI_DEPLOYMENT = MANUAL
OCI_HEAD       = 5d2614d6
REPO_GAP       = 8 commits (조사 시점)
```

**"OCI 자동 pull 확인됨" 표현을 현재 사실로 쓰지 않는다.** 배포 단계 확인
12항목은 설계자 §9 그대로.

**코드가 존재한다는 이유로 OCI 운영 상태라고 기록하지 않는다.**

## M-10. 권한 범위

| 승인 | 미승인 |
|---|---|
| PLAN 문서 반영 | commit · push |
| **로컬 코드 구현** | OCI 배포 · OCI DB migration·초기 적재 |
| 로컬 격리 테스트 | 실제 상태 파일 변경 |
| mock/no-send 산출 | Telegram 실발송 · autosend 활성화 |

구현 단계에서는 **합성 fixture 와 임시 DB 만** 쓴다. **구현·검증이 끝나도
`PUSH 3_OF_3` 으로 기록하지 않는다.**

---

# 착수 조건

```text
PLAN_STATUS      = APPROVED_WITH_REQUIRED_EDITS (V1.2 반영 완료)
IMPLEMENTATION   = AUTHORIZED   (로컬 한정)
COMMIT_PUSH      = NOT_AUTHORIZED
OCI_DEPLOY       = NOT_AUTHORIZED
AUTOSEND         = false 유지
ACTIVATION_BLOCK = KRX_TRADING_CALENDAR_NOT_PROVIDED
```

**모호점 없음.** Q1~Q4 전부 확정됐다(§M). 별도 PLAN 재심사 없이 구현에
착수한다. **구현 중 새로운 source identity·schema 충돌·KS-10 초과가 발견되는
경우에만 중단하고 보고**한다.

수행한 것: 저장소·로컬 DB 읽기 · **OCI 읽기 전용 SSH**(cron · flag · HEAD ·
ticker 별 freshness) · 소스 grep · **읽기 전용 외부 probe**(KRX Open API 기준일·
휴장일 서비스 탐색).

**코드 수정 0건**(본 PLAN 개정 + 기존 PLAN 오기 1건 정정 제외) · **운영 DB write
0건** · **state write 0건** · **발송 0건** · **commit/push/배포 0건** ·
`PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED=false` 유지 · 비밀값 미출력.

> **기존 문서 정정 1건** — `POC3-OPS-02B_..._PLAN_V1.md` §11.3 의 "OCI 자동 pull
> 확인됨" 을 실측(**수동 배포 · OCI 8커밋 뒤짐**)으로 고쳤다.
