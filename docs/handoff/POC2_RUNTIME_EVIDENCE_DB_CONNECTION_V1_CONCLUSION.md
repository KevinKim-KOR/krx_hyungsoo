# Runtime Evidence DB Connection v1 — Conclusion (PARTIAL — PC DONE · OCI 실행 대기)

작성일: 2026-07-12
성격: OCI PARAM Runtime 에 기존 read-only evidence (market_data.sqlite · Holdings · runtime_state.sqlite) 를 연결해 실제 시장 수치가 포함된 사용자 메시지를 생성하는 STEP. **새 데이터 수집 · 신규 selection 로직 · Telegram 발송 없음.**

## 1. Runtime 연결 흐름

**Before**:
```
PARAM load → push enabled 확인 → build_runtime_message(available_sources=None)
```
- 모든 source unavailable 처리 → 축약 메시지만.

**After (본 STEP)**:
```
PARAM load → push enabled 확인 →
compose_runtime_evidence(push_kind) →
build_runtime_message(
    available_sources=result.available_sources,
    extra_notes=result.extra_notes,
)
→ record 에 diagnostics summary 추가
```

- `scripts/run_three_push_runtime_oci.py:171~193` 정정 (`available_sources=None` 제거 · `extra_notes` 전달).
- record 신규 필드: `contentful_fact_count`, `selection_result_count`, `unavailable_reasons` (본문 비노출 대상은 저장 X — 지시문 §9 준수).

## 2. Composer 책임과 반환 계약

**모듈**: `app/runtime_evidence_composer.py` (지시문 §4.1 신규).

**반환 dataclass** (지시문 §4.2):
```python
@dataclass
class RuntimeEvidenceResult:
    available_sources: dict[str, str]   # build_runtime_message 계약 유지
    extra_notes: list[str]              # 사용자 문장 (실제 수치+as-of)
    diagnostics: dict[str, Any]         # 내부 진단 (본문 비노출)
```

**diagnostics 필드**:
- `push_kind`
- `source_statuses` (dict[source_key, status])
- `source_asof` (dict[source_key, iso date])
- `contentful_fact_count`
- `selection_result_count`
- `unavailable_reasons`
- `holdings_source_present`

**책임 밖 (지시문 §4.1)**: 외부 API 호출 · DB/artifact write · 신규 selection 로직 · 신규 threshold.

**DI (지시문 Q10)**: `market_db_path` / `holdings_file` / `holdings_loader` / `topn_fn` / `nav_fn` / `evidence_fn` 파라미터로 override 가능 → test 는 tmp path/fixture 사용.

## 3. source 별 reader · status · as-of

| source_key | reader (재사용) | 이번 STEP 처리 | reason (unavailable 시) |
|---|---|---|---|
| `market_discovery_snapshot` | `compute_topn()` @ `app.market_topn` | ✅ 필수 연결 (§5.1) | `market_db_missing_or_empty` / `no_contentful_fact` |
| `holdings_snapshot` | `holdings.load()` + `build_holdings_market_evidence()` | ✅ 조건부 연결 (§5.2) | `holdings_source_missing` / `holdings_load_error` / `holdings_empty` / `no_contentful_fact` |
| `nav_discount_snapshot` | `fetch_latest_nav()` @ `app.etf_nav_store` | ✅ 조건부 연결 (§5.3) | `holdings_source_missing` / `nav_row_unavailable` |
| `kr_realtime_price_snapshot` | — | unavailable 유지 (§5.4) | `unavailable_external_fetch_required` |
| `overnight_us_market_snapshot` | — | unavailable 유지 (§5.5) | `unavailable_external_fetch_required` |
| `ml_baseline_v0` | — | unavailable 유지 (§5.6) | `unavailable_not_implemented` |
| `news_snapshot` | — | unavailable 유지 (§5.7) | `unavailable_not_implemented` |
| `universe_momentum_snapshot` | — | unavailable 유지 (§5.8) | `unavailable_not_implemented` |

**중요**:
- DB/table 존재만으로 available 처리하지 않음 (지시문 §5.1 · AC-8). `compute_topn().status == "ok"` + 실제 asof + 실제 수치 + evidence 문장 1개 이상 생성 가능해야 available.
- daily close 를 realtime source 로 승격 X (§5.4 · AC-9).
- NAV 는 Holdings + DB row 있을 때만 available (§5.3 · AC-12), 실제 DB as-of 사용 (AC-13).

## 4. 3-PUSH 별 결과 (PC 실측 · FIX r1)

**실행 방식**: 실제 PC 로컬 `state/market/market_data.sqlite` (baseline `f7df867d...`) + `state/holdings/holdings_latest.json` 존재 상태에서 `compose_runtime_evidence()` 를 직접 호출한 결과.

**market_briefing (실측)**:
- `market_discovery_snapshot=available` (asof=`2026-07-03`), 나머지 4 source unavailable.
- `extra_notes count=3` (KODEX200 · KOSPI · TOP preview 각 1건, 모두 `(2026-07-03 기준)` 표시).
- `contentful_fact_count=3` (`market_discovery_snapshot` 만 집계 — A-1 정정 결과).
- `selection_result_count=10` (compute_topn 실제 후보 수).
- `source_statuses`: `market_discovery_snapshot=available`, 나머지 4 = `unavailable` (A-1 정정 · `not_applicable` 제거).

**holdings_briefing (FIX r2 실측)**:
- `holdings_snapshot=unavailable` (reason=`no_contentful_fact` — TOP-N 이 Holdings 실제 보유 종목과 매칭 안 되는 상태, market_asof=`2026-07-03` 존재하여 이 자체는 정상 판정 경로), `nav_discount_snapshot=available` (asof=`2026-07-04`), 나머지 2 unavailable.
- `extra_notes count=32` (NAV 문장 32건, 각각 실제 as-of 포함).
- `contentful_fact_count=32` (holdings=0 + nav=32 = 32 — A-1 정정 결과, Market Discovery fact 미가산).
- `selection_result_count=0` (holdings evidence 매칭 없음).
- `source_asof={"holdings_snapshot": "2026-07-03", "nav_discount_snapshot": "2026-07-04"}` — FIX r2 정정 결과 Holdings 도 asof 반영 (이전에는 nav 만).

**spike_or_falling_alert (실측)**:
- `universe_momentum_snapshot=unavailable_not_implemented`, `kr_realtime_price_snapshot=unavailable_external_fetch_required`.
- `extra_notes=[]`.
- `contentful_fact_count=0` ✅ (이전 잘못 합산 3 → 정정 후 0, B-6 재현 · A-1 정정).
- `selection_result_count=0`.
- `source_asof={}` — Spike 는 `compute_topn` 미호출 (B-6 정정).
- `source_statuses` 모두 `unavailable` 라벨.

## 5. Diagnosis 정합화 (§11)

**대상**: `app/push_content_gap_diagnosis_reproducers.py::reproduce_param_runtime`.

**변경**:
- Legacy JSON reader (`read_param_file(PARAM_PATH)`) 제거.
- `app.runtime_param_store.read_active_param_dict()` 로 전환 (runtime_state.sqlite active pointer 기반).
- `available_sources=None` 하드코딩 제거 → 동일 `compose_runtime_evidence()` 호출.
- Telegram · runtime status DB · sent registry · market/holdings write 0건 (§11 계약 준수).
- reproducer 결과에 `contentful_fact_count`, `unavailable_reasons` 추가 (진단 상세성 강화).

**공통 경로 확인** (AC-15):
- 운영 runner (`scripts/run_three_push_runtime_oci.py`) 와 diagnosis reproducer 가 모두 `compose_runtime_evidence()` + `build_runtime_message(available_sources=..., extra_notes=...)` 를 호출.
- `test_diagnosis_reproducer_uses_runtime_state_db` 로 확인.

## 6. Privacy · 사용자 본문 기준 (§7)

**노출 필드**:
- 종목명 / ticker / 기간 수익률 / 초과수익 / Market Discovery 일치 / NAV · 괴리율 / 실제 기준일.

**비노출** (Composer 가 생성하지 않음 / diagnostics 만 기록):
- 보유 수량 / 평균 매입가 / 계좌 그룹 / 투자 원금 / 평가금액 / 포트폴리오 비중 / Holdings JSON 원문.
- PARAM ID · source · raw push_kind · snake_case source key · 내부 reason code.

**BUY / SELL / 교체 / 비중 조절 문구**: Composer 문장 생성 시 사용 안 함 (기존 forbidden wording 검사도 통과).

**diagnostics 저장 범위** (지시문 §9 · A-3 정정): `contentful_fact_count`, `selection_result_count`, `unavailable_reasons` 는 record dict 에 추가되어 **history JSONL 에는 그대로 append** 됨 (runner 가 `_HISTORY_PATH` 로 직접 append). **DB `runtime_execution_status` 에는 이번 STEP 에서 저장되지 않음** — DB schema 변경은 §13 금지 항목이므로 신규 컬럼 추가 없이 기존 컬럼만 사용. `insert_status_from_record` 는 기존 record 필드만 매핑. 신규 diagnostics 세 필드의 DB 저장은 별도 STEP (schema 변경 승인 필요). message body 에는 노출되지 않음. Holdings 개인정보는 record 에도 저장하지 않음.

## 7. dry-run side effect 결과 (§10)

**계약 유지** (지시문 §10):
- runtime execution status DB write: **YES** (기존 계약).
- history JSONL append: **YES** (기존 계약).
- Telegram 호출: **NO**.
- sent registry write: **NO** (dry-run 이므로 `mark_sent` 미도달).

**변경 없음**: runner `_finish()` 는 그대로. `insert_status_from_record` + JSONL append 조합 유지.

**§10 §19 note**: `dry_run.runtime_status_written = true`, `dry_run.history_appended = true`, `dry_run.telegram_attempted = false`, `dry_run.sent_registry_before == sent_registry_after`.

## 8. PC 검증 결과 (FIX r2)

**Composer focused test**: **17 passed** (14 → 17: `test_holdings_value_error_propagates`, `test_holdings_unavailable_when_market_asof_missing`, `test_holdings_source_asof_populated_when_available` 신규).
**Runner dry-run focused test**: **4 passed** (holdings/spike test 에 Telegram spy 미호출 + `sent_registry` 불변 직접 assert 추가).
**Diagnosis test**: `test_1_diagnosis_calls_existing_push_helpers` + `test_8_exact_reason_code_recorded` 통과.
**backend regression (FIX r2 최종)**: **848 passed** (827 → 838 → 845 → 848, 이번 STEP 순증 21). 0 fail. 196s.
**실제 state 3종 (`runtime_state.sqlite` / `latest_runtime_param.json` / `market_data.sqlite`) pytest 전·후 완전 불변** (sha256 3중 일치 확인).
**Lint**: black / flake8 (max-line=100) / py_compile PASS.

**실제 state 무변경 (pytest 838 실행 전·후 실측 대조)**:
- `state/runtime/runtime_state.sqlite`: size=53248, sha256=`f72dd796b20441c8d89ab59815c546cbdf74cac318f27eabede011750d1b386e`, mtime=1783846900.8138113. 3중 완전 동일.
- `state/three_push/params/latest_runtime_param.json`: size=884, sha256=`84151b5659abba0a8622af3e418856e5512e3f290c6fd50a0697b0609af422aa`, mtime=1783846900.6387017. 3중 완전 동일.
- `state/market/market_data.sqlite`: size=131538944, sha256=`f7df867d0f69fc07929b0a25a87ccdc0f235a01097299a9a522bf991614cf286`, mtime=1783231217.8648515. 3중 완전 동일 (Cutover v1 §2 · Remediation v1 baseline).

## 9. OCI 실행 명령 (사용자 실행 대기)

### 9.1 최신 코드 반영

```bash
cd ~/krx_hyungsoo
git pull origin main
git rev-parse --short HEAD
```

### 9.2 각 push_kind 별 dry-run 실행

```bash
# runtime status/history 는 정상적으로 append 되지만 Telegram 발송 · sent registry write 는 발생하지 않음.
python3 -m scripts.run_three_push_runtime_oci --push-kind market_briefing --mode dry-run
python3 -m scripts.run_three_push_runtime_oci --push-kind holdings_briefing --mode dry-run
python3 -m scripts.run_three_push_runtime_oci --push-kind spike_or_falling_alert --mode dry-run
```

### 9.3 실행 후 verify

```bash
python3 -m scripts.run_runtime_state_db_cutover verify
```

### 9.4 사용자 sanitised 회신 항목

**각 push_kind 별**:
- `record.push_kind`, `record.mode`, `record.status`, `record.reason`.
- `record.param_id`, `record.param_source`.
- `record.message_text_length`.
- `record.availability` (dict, `{"available": int, "unavailable_or_other": int}`).
- `record.contentful_fact_count`, `record.selection_result_count`.
- `record.unavailable_reasons` (dict, raw reason code — sanitised 대상: message body 노출 없음).
- `record.telegram_attempted` (expect: `false`), `record.telegram_sent` (`false`).
- `record.duplicate_key`.

**시장 데이터 as-of** (compute_topn 실측):
- 사용자가 `python3 -c "from app.market_topn import compute_topn; print(compute_topn().get('asof'))"` 실행.

**sent_registry 변화**:
- dry-run 전 후 `runtime_sent_registry` COUNT(*) 비교. 반드시 동일해야 함.

**verify overall**:
- 이전 STEP FIX r1 baseline 대비 무변화 (verify `overall=READY`, `readiness_errors=[]`, `activated_by=cutover_seed`).

**절대 회신 금지**: message body 원문, PARAM 원문, 보유 수량 · 평단 · 계좌 그룹, Holdings JSON 원문, 절대 경로, token, chat_id, raw traceback.

## 10. 남은 source gap (다음 STEP 후보)

이번 STEP 에서 unavailable 유지된 source:
- `kr_realtime_price_snapshot` — 외부 API (예: naver / KRX intraday) 연결 필요.
- `overnight_us_market_snapshot` — 외부 API (예: Yahoo Finance overnight) 연결 필요.
- `ml_baseline_v0` — ML artifact 생성 · OCI 전달 STEP.
- `news_snapshot` — producer/reader 신설.
- `universe_momentum_snapshot` — artifact 생성 · 전송 STEP.

## 11. PC vs OCI 비교 (사용자 실행 후 갱신)

| 항목 | PC | OCI |
|---|---|---|
| revision (git HEAD) | (이 commit) | ⏳ |
| active_param_version_id | `param-20260708T141218-914114` | ⏳ (same_hash 예상 여부) |
| market_asof (compute_topn) | ⏳ (사용자 실행) | ⏳ |
| market_briefing available/reasons | ⏳ | ⏳ |
| holdings_briefing available/reasons | ⏳ | ⏳ |
| spike_or_falling_alert available | unavailable | unavailable (기대) |
| telegram_attempted/sent | false/false | false/false (기대) |
| sent_registry_before → after | 무변화 | 무변화 (기대) |

## 12. 다음 STEP 게이트

**PASS 조건** (지시문 §18):
- OCI market briefing contentful evidence 최소 1개 생성.
- 실제 as-of + 실제 수치.
- available_sources · extra_notes 전달 확인.
- Telegram 미발송 · sent registry 불변.
- Diagnosis 공통 Composer 사용 확인 (test 로 이미 확인).

**분기**:
- 시장 · Holdings · Spike 모두 contentful → `Telegram Contentful Controlled Send v1`.
- 시장만 contentful, Holdings/Spike source 부재 → `OCI Evidence Publication / Missing Source Connection`.

**Holdings JSON OCI 부재 시**: `holdings_source_missing` 으로 unavailable. **이번 STEP FAIL 아님** (지시문 §18 명시).

## 13. 금지 항목 변경 0건 확인 (§13)

- DB schema 변경 · row migration · Holdings DB Cutover · ML/universe artifact 생성 · runtime probe 실행 · 외부 API · 뉴스 source 구현 · 신규 threshold · 신규 selection · Telegram 발송 · scheduler · PARAM 정책 · sent registry 기준 · package fallback · BUY/SELL/교체/리밸런싱 — 모두 0건.
- `build_runtime_message()` 시그니처 무변경. `PUSH_KIND_DATA_SOURCES` 무변경.
