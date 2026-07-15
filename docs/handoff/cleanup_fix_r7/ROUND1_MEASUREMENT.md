# Cleanup / FIX r7 — Round 1 실측 보고

측정 일자: 2026-07-14
측정 대상: git-tracked `.py` / `.ts` / `.tsx` 전량
측정 도구: `wc -l`
측정 기준 (KS-10 canonical, 설계자 확정):
- 백엔드 (`app/**/*.py` + `scripts/**/*.py`): trigger ≥ 650 · near = 600~649
- 프론트 컴포넌트 (`.tsx`): trigger ≥ 900 · near = 850~899
- 테스트 (`tests/**/*.py`): trigger ≥ 1500 (여러 Step 혼재) 또는 ≥ 2500 · near = 1450~1499
- `.ts` 파일 (frontend/lib · `next.config.ts` 등) 및 `legacy/**/*.py`: **canonical 미확정** (지시문 §15 신규 threshold 부여 금지 준수). 24개 파일 실측 최대 392줄 (`frontend/lib/marketDiscoveryCopyText.ts`) 로 어떤 canonical 임계치도 근접 아님 → 지시문 §5.1 허용값 `trigger / near_threshold / normal` 중 `normal` 로 분류. CSV `ks10_threshold` · `distance_to_threshold` 컬럼에는 숫자 대신 `canonical_undefined` 라벨 사용 (임의 숫자 부여 회피).

## 집계

| 지표 | 값 |
|---|---|
| total_files_measured | **281** (git ls-files 기준) |
| .py 파일 총계 | 216 (`app/` 117 · `scripts/` 25 · `tests/` 73 · `legacy/` 1) |
| .ts 파일 | 23 |
| .tsx 파일 | 42 |
| trigger_files_count | **2** |
| near_threshold_files_count | **0** |
| normal_files_count | **279** (canonical 임계치 대상 255 + canonical 미확정 24) |

## trigger_files_before

| path | extension | line_count | ks10_threshold | 초과 | classification |
|---|---|---|---|---|---|
| `app/runtime_evidence_composer.py` | py (backend) | 781 | 650 | +131 | trigger |
| `scripts/refresh_market_timeseries.py` | py (backend) | 686 | 650 | +36 | trigger |

## near_threshold_files_before

없음 (0건).

## additional_cleanup_targets (설계자 §Q2 확정)

| path | extension | line_count | classification | cleanup_target | reason |
|---|---|---|---|---|---|
| `tests/test_runtime_evidence_composer.py` | py (test) | 1201 | normal | true | accepted_structural_debt (검증자 B-2/B-3 지적 + AC-14 + focused 36 test 계약 유지) |

## 상위 20 참고 (near 아님 · 이번 Cleanup 대상 아님)

`round1_full_measurement.csv` 원본에서 `sort -t'|' -k3 -rn | head -20` 재실행 가능.

| rank | path | line_count | class |
|---|---|---|---|
| 1 | tests/test_runtime_evidence_composer.py | 1201 | normal (구조 부채) |
| 2 | tests/test_holdings_message_text.py | 924 | normal |
| 3 | frontend/app/components/MarketDiscoveryView.tsx | 792 | normal |
| 4 | app/runtime_evidence_composer.py | 781 | **trigger** |
| 5 | tests/test_decision_draft_preview.py | 766 | normal |
| 6 | tests/test_market_topn.py | 742 | normal |
| 7 | scripts/refresh_market_timeseries.py | 686 | **trigger** |
| 8 | tests/test_runtime_package.py | 670 | normal |
| 9 | tests/test_decision_evidence_store.py | 667 | normal |
| 10 | tests/test_three_push_message_text_runtime_evidence.py | 638 | normal |
| 11 | frontend/app/components/HoldingsCompareView.tsx | 622 | normal |
| 12 | tests/test_market_topn_api.py | 618 | normal |
| 13 | scripts/diagnose_nav_discount_source.py | 594 | normal (distance=56) |
| 14 | tests/test_market_flow_v2_model_comparison.py | 590 | normal |
| 15 | app/draft.py | 586 | normal |
| 16 | tests/test_run_holdings_publication.py | 582 | normal |
| 17 | app/api.py | 565 | normal |
| 18 | app/ml_feature_sanity.py | 561 | normal |
| 19 | app/decision_evidence_store.py | 543 | normal |
| 20 | app/holdings_market_evidence.py | 538 | normal |

## 산출물

- 전체 파일별 실측: `docs/handoff/cleanup_fix_r7/round1_full_measurement.csv` (281 rows + 1 header).
- 컬럼: `path | extension | line_count | ks10_threshold | distance_to_threshold | classification`
- `extension` = 실제 파일 확장자 (`py` / `ts` / `tsx`).
- `classification` = 지시문 §5.1 허용값 (`trigger` / `near_threshold` / `normal`) 만 사용.
- canonical 대상 파일: `distance_to_threshold` = `ks10_threshold - line_count` (음수면 trigger).
- canonical 미확정 파일 24건 (`.ts` 23 + `legacy/ui_app.py` 1): `ks10_threshold=canonical_undefined`, `distance_to_threshold=canonical_undefined`, `classification=normal` (실측 라인수 최대 392 로 canonical 임계치 미근접).
