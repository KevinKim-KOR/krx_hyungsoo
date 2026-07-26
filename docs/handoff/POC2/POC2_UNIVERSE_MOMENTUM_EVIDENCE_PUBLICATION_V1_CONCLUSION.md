# Universe Momentum Evidence Publication v1 — Conclusion (DONE · PC+OCI 완료)

작성일: 2026-07-16 (PC) · 2026-07-18 (OCI closeout)
성격: Universe Seed Bootstrap + Runtime `spike_or_falling_alert` evidence 연결 + OCI controlled publication.

## 1. Step 목표

기존 Holdings + Market Discovery 결과를 이용해 Universe seed 후보를 제안 →
사용자 승인 → manual seed 생성 → 기존 producer PC 1회 실행 → OCI controlled publication →
`spike_or_falling_alert` 가 real read-only artifact 로 evidence 생성.

## 2. Source Contract 실측

| 항목 | 값 |
|---|---|
| Canonical seed | `state/universe/etf_universe_latest.json` |
| Canonical artifact | `state/universe/universe_momentum_latest.json` |
| Producer | `app.universe_refresh.run_universe_refresh(seed)` |
| Artifact writer | `app.momentum.universe_mode.save_latest_artifact()` |
| Runtime reader | `app.draft_three_push._load_universe_artifact_for_spike()` (재사용) |
| External API | pykrx `_default_fetcher` (기존, 1개월 이력) |
| Artifact schema | `engine_id / engine_version / mode / asof / summary(refresh_status, top_candidate, falling_candidate, ...) / candidates[]` |
| refresh_status allowlist | `{ok, partial}`; `failed` → 활성화 차단 |

Schema · threshold · 후보 선정 기준 · candidate 정렬 변경 없음.

## 3. Bootstrap

### 3.1 Propose 결과 (실측 v5)

| 지표 | 값 |
|---|---|
| status | ok |
| publishable_proposal | true |
| holdings_asof | 2026-06-17T16:10:22+09:00 |
| market_discovery_asof | 2026-07-03 |
| proposal_count | 20 (unique ticker 20) |

**Holdings (평가금액 합산 후 내림차순, 최대 10)**:
1. 069500 KODEX 200
2. 139260 TIGER 200 IT
3. 379800 KODEX 미국S&P500
4. 442580 PLUS 글로벌HBM반도체
5. 0167A0 SOL AI반도체TOP2플러스
6. 379810 KODEX 미국나스닥100
7. 441800 TIME Korea플러스배당액티브
8. 390390 KODEX 미국반도체
9. 396500 TIGER 반도체TOP10
10. 367760 RISE 네트워크인프라

**Market Discovery (canonical 순위 유지, 최대 10)**:
11~20. 0113G0, 203780, 396520, 490330, 0083S0, 476070, 0133E0, 485810, 476310, 371470.

**개인정보 비노출 확인 (§7.4 · §10.1)**: quantity · avg_buy_price · eval_amount(합산 값 포함) · account_group · Holdings JSON 원문 미노출.

### 3.2 사용자 승인

- 승인 방식: (a) v5 20개 전부.
- pykrx 실행 승인: yes.

### 3.3 Materialize

| 지표 | 값 |
|---|---|
| seed_path | `state/universe/etf_universe_latest.json` |
| source | manual |
| asof | 2026-07-16 |
| item_count | 20 |
| canonical validation | 통과 (`parse_universe_seed`) |
| seed_hash | `bc08b0c2a3088cde5db3fbe5b2999d485721673768409497add9e3c8d3170987` |

## 4. Producer 실행

`run_universe_refresh(seed) + save_latest_artifact(result)` PC 1회.

| 지표 | 값 |
|---|---|
| pykrx 외부 호출 | yes (기존 `_default_fetcher`) |
| refresh_status | ok |
| scored candidates | 20/20 |
| result mode | universe |
| result asof | 2026-07-16 |
| artifact_hash | `9722ef2dc49bc9f22d3d8c399b640f9e0b88e11c269031c3f7fd53e25034df9c` |
| artifact_size | 18406 bytes |

신규 threshold · 신규 fetcher · 후보 강제 생성 · artifact 수동 조작 없음.

## 5. PC prepare 실측

```json
{
  "command": "prepare",
  "status": "ok",
  "source_exists": true,
  "source_valid": true,
  "source_artifact_status": "ok",
  "source_asof": "2026-07-16",
  "source_candidate_count": 20,
  "source_hash": "9722ef2dc49bc9f22d3d8c399b640f9e0b88e11c269031c3f7fd53e25034df9c",
  "source_size": 18406,
  "publishable": true
}
```

## 6. PC Runtime dry-run

### spike_or_falling_alert
```
universe_snapshot_status = available
universe_snapshot_reason = ""
universe_artifact_present = true
universe_artifact_valid = true
universe_candidate_count = 20
universe_selected_count = 5
universe_contentful_fact_count = 5
no_signal = false
private_fields_exposed = false
raw_identifier_exposed = false
contentful_fact_count = 5
selection_result_count = 5
```

첫 evidence 문장 예시: `KODEX 200 (2026-07-16 기준): 1개월 -21.89%.`

### market_briefing 회귀 (§31)
`contentful=3, selection=10` (baseline 유지).

### holdings_briefing 회귀 (§31)
`available, loaded=35, contentful=67, selection=35, private_fields_exposed=false, raw_identifier_exposed=false` (baseline 유지).

## 7. 실제 state SHA-256 (before ↔ after)

| 파일 | before | after | 결과 |
|---|---|---|---|
| `state/holdings/holdings_latest.json` | 767815e0... | 767815e0... | ✅ 불변 |
| `state/market/market_data.sqlite` | f7df867d... | f7df867d... | ✅ 불변 |
| `state/runtime/runtime_state.sqlite` | f72dd796... | f72dd796... | ✅ 불변 |
| `state/three_push/params/latest_runtime_param.json` | 84151b56... | 84151b56... | ✅ 불변 |
| `state/universe/etf_universe_latest.json` | not_present | bc08b0c2... | 명시적 materialize (사용자 승인) |
| `state/universe/universe_momentum_latest.json` | not_present | 9722ef2d... | 명시적 producer 실행 (사용자 승인) |

기존 4종 완전 불변. 신규 2종 (seed, artifact) 은 사용자 승인 하에 명시적 실행으로만 생성.

## 8. 회귀 · 검증

| 항목 | 값 |
|---|---|
| Runtime evidence + universe bootstrap focused | 124 passed, 4 skipped |
| Backend full regression | 971 passed, 4 skipped, 0 failed. 199s |
| black --check | 통과 (247 files) |
| flake8 --max-line-length=100 | 통과 |

## 9. Publication ↔ Runtime 계약 일치

Shared validator `app.universe_bootstrap.artifact_validator.validate_artifact` 사용.

- refresh_status allowlist `{ok, partial}`
- candidate shape: ticker(str) + score_result(dict) + `is_scored`(bool)
- is_scored=True ⟹ score_value 유한 실수 (NaN/Inf 차단)
- asof YYYY-MM-DD + `date.fromisoformat` 통과
- producer status 완전 교차 검증:
  - ok ⟺ scored == total
  - partial ⟺ 0 < scored < total
  - failed ⟹ 이미 차단

Publication 통과 artifact 는 Runtime 에서 반드시 available (candidate_count ≥ 1 + fact ≥ 1).

## 10. 금지사항 준수 (§38)

- Universe Momentum 신규 알고리즘 · 신규 factor · 신규 threshold · 후보 재정렬 · 후보 임의 생성: 없음
- Market Discovery Refresh · 실시간 국내 시세 · 미국 시장 · ML · 뉴스 source: 없음
- 신규 API · 신규 UI · 자동 사용자 승인 · seed 자동 갱신: 없음
- 범용 publication framework · DB schema · DB migration: 없음
- Telegram 실제 발송 · scheduler · PARAM 정책 · package fallback: 없음
- BUY / SELL / 교체 / 비중 조정 / 자동 리밸런싱: 없음

## 11. dry-run 안전 계약 (§16 · §36)

- telegram_attempted = false (전 records)
- telegram_sent = false (전 records)
- sent_registry_before = sent_registry_after (자동 test 는 tmp fixture)

## 12. 검증자 지적 정정 이력

- R1: ETF 필터 · source 실패 전파 · publishable_proposal · Runtime 순서/reader 예외 · refresh_status allowlist · 내부 reason 미노출 · materialize validation · owner=ubuntu · lint/format
- R2: shared validator (B-6 중복 제거) · privacy detector 재사용 · sanitized error_reason · owner 고정 · materialize atomic · candidate shape 검증 · seed 보존 (B-1)
- R3: owner CLI override 제거 · is_scored boolean 검증 · Publication↔Runtime 계약 강화
- R4: owner env 우회 완전 제거 · NaN/Inf score_value 차단
- R5: producer status 교차 검증 (scored=0 차단) · stale 주석 제거
- R6: verify mode/owner activation_ready 판정 반영 · asof 실제 날짜 형식 · producer status 완전 교차 (ok/partial 3 규칙)
- R7: CLI materialize malformed 항목 skip 제거 · Market Discovery candidate 예외 안전 처리
- R8: Holdings/Market Discovery 내부 ticker 중복 제거
- R9: Holdings 중복 ticker 평가금액 합산 후 순위

최종 판정 r10: **VERIFIED_WITH_NOTES** (PC 범위). OCI 재검증 대기.

## 13. OCI 재검증 실측 (2026-07-18)

### 13.1 revision

- OCI `git log --oneline -1`: `b8eaeeac feat(universe-momentum-evidence-publication-v1): ...`
- PC ↔ OCI revision 동일 (AC-45).

### 13.2 verify JSON 실측

```
command=verify, status=ok
destination_temp_received=true, destination_valid=true
destination_artifact_status=ok
destination_asof=2026-07-16
destination_candidate_count=20
destination_hash=9722ef2dc49bc9f22d3d8c399b640f9e0b88e11c269031c3f7fd53e25034df9c
destination_size=18406
hash_match=true, size_match=true, asof_match=true, candidate_count_match=true
mode_match=true, owner_match=true
activation_ready=true
temp_mode=600, temp_owner=ubuntu, temp_group=ubuntu
```

### 13.3 activate JSON 실측

```
command=activate, status=ok
final_validation_passed=true, atomic_activation_completed=true
active_file_exists=true
active_artifact_status=ok, active_asof=2026-07-16
active_candidate_count=20
active_hash=9722ef2dc49bc9f22d3d8c399b640f9e0b88e11c269031c3f7fd53e25034df9c
active_size=18406
active_file_mode=600, active_file_owner=ubuntu
active_file_permission_checked=true
```

### 13.4 OCI Runtime dry-run 3종

**spike_or_falling_alert** (universe evidence 첫 실운영 실측):
```
status=dry_run_success
universe_snapshot_status=available, universe_snapshot_reason=""
universe_artifact_present=true, universe_artifact_valid=true
universe_artifact_status=ok, universe_artifact_asof=2026-07-16
universe_candidate_count=20, universe_selected_count=5, universe_contentful_fact_count=5
contentful_fact_count=5, selection_result_count=5
no_signal=false
private_fields_exposed=false, raw_identifier_exposed=false
telegram_attempted=false, telegram_sent=false
message_text_length=344
```

**market_briefing** (baseline 유지 확인):
```
status=dry_run_success
contentful_fact_count=3, selection_result_count=10
telegram_attempted=false, telegram_sent=false
message_text_length=393
```

**holdings_briefing** (baseline 유지 확인):
```
status=dry_run_success
holdings_snapshot_status=available, holdings_loaded_count=35
holdings_contentful_fact_count=67 (record 표기: contentful_fact_count=67)
holdings_selection_result_count=35
private_fields_exposed=false, raw_identifier_exposed=false
telegram_attempted=false, telegram_sent=false
```

### 13.5 PC ↔ OCI 대조

| 항목 | PC | OCI | 판정 |
|---|---|---|---|
| revision | b8eaeeac | b8eaeeac | ✅ |
| artifact hash | 9722ef2d... | 9722ef2d... | ✅ |
| artifact size | 18406 | 18406 | ✅ |
| artifact asof | 2026-07-16 | 2026-07-16 | ✅ |
| candidate_count | 20 | 20 | ✅ |
| spike universe_selected/contentful | 5/5 | 5/5 | ✅ |
| spike no_signal | false | false | ✅ |
| spike privacy | false/false | false/false | ✅ |
| market contentful/selection | 3/10 | 3/10 | ✅ baseline |
| holdings loaded/contentful/selection | 35/67/35 | 35/67/35 | ✅ baseline |
| holdings privacy | false/false | false/false | ✅ baseline |

전 항목 완전 일치.

## 14. AC 충족 상황 (최종)

| AC | 상태 |
|---|---|
| AC-1~12 (Bootstrap) | ✅ |
| AC-13~16 (Producer) | ✅ |
| AC-17~19 (PC prepare · Publication) | ✅ |
| AC-20~27 (OCI verify · activate · 권한) | ✅ |
| AC-28~37 (Runtime source · 회귀 · 개인정보) | ✅ |
| AC-38~44 (회귀 · 안전) | ✅ |
| AC-45~46 (PC↔OCI same revision · docs) | ✅ |

## 15. Phase 상태 (최종)

```
status = DONE
next_step_gate = READY_FOR_NEXT_STEP
```

## 16. BACKLOG 이관 (§40)

- 보유/외부 후보 비율 가변화
- 거래대금·유동성 필터
- 변동성·하락 위험 반영
- 테마 중복 제거
- constituents overlap 반영
- seed 유지 기간 · 교체 조건 · 갱신 주기
- 사용자 재승인 조건
- ML·백테스트 기반 seed 품질 개선

재검토 트리거: Telegram 운영 1회전 완료 후 Universe 후보 품질 평가 시점.

## 17. 다음 Step

Universe Momentum Evidence Publication v1 완료. 다음 Step 후보 (§29 · §43): `Telegram Contentful Controlled Send v1`.
