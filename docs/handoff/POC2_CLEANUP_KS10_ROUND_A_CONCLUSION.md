# Cleanup KS-10 Round A — Conclusion

작성일: 2026-06-29
측정 방식: `wc -l` (Bash) 통일. 모든 라인 수는 본 Round 작업 후 실측값.

---

## 1. 목표

- 전체 `.py` (app/ + scripts/ + tests/ + legacy/) / `.ts` / `.tsx` (frontend/) 파일 라인 수 기준선 확정 및 문서화
- KS-10 trigger / near-threshold / ambiguity 파일 목록화
- `test_generate_spike_alert_via_unified_endpoint` 회귀 해소

---

## 2. KS-10 판정 기준 (KILL_SWITCHES.md)

| 구분 | trigger | near (사전 경고) |
|---|---|---|
| 백엔드 핵심 모듈 (`app/`) | ≥ 650 | ≥ 600 |
| 테스트 파일 (`tests/`) — 여러 Step 섞임 | ≥ 1,500 | ≥ 1,450 |
| 테스트 파일 (`tests/`) — 무조건 | ≥ 2,500 | ≥ 2,450 |
| 프론트엔드 컴포넌트 (`frontend/`) | ≥ 900 | ≥ 850 |

---

## 3. KS-10 분류 결과 (Round A 기준선)

### trigger 파일

**app/ — 없음** (최대 636: `app/api_market_topn.py`, trigger 미달)

**tests/ — 없음** (최대 924: `tests/test_holdings_message_text.py`, Step5D-2 분리 단일 주제 파일 — "여러 Step 섞임" 조건 미해당, 1,500 미달)

**frontend/ — 없음** (최대 789: `frontend/app/components/MarketDiscoveryView.tsx`, 900 미달)

### near-threshold 파일

| 파일 | 라인 수 | 구분 |
|---|---|---|
| `app/api_market_topn.py` | 636 | 백엔드 near (600~649) |

### classification_ambiguities

| 파일 | 라인 수 | 판단 불명확 이유 |
|---|---|---|
| `scripts/run_three_push_oci.py` | 672 | KS-10 트리거 4번("백엔드 핵심 모듈") 이 `scripts/` 배포 스크립트에도 적용되는지 불명확. Round B 진입 전 사용자 결정 필요. |

---

## 4. 전체 파일 라인 수 기준선 (wc -l, Round A 완료 후)

### app/ (.py)

| 파일 | 라인 수 |
|---|---|
| `app/__init__.py` | 0 |
| `app/api.py` | 560 |
| `app/api_decision_sessions.py` | 235 |
| `app/api_etf_constituents.py` | 237 |
| `app/api_holdings_market_evidence.py` | 213 |
| `app/api_market_topn.py` | **636** ← near |
| `app/api_ml_baseline.py` | 113 |
| `app/api_ml_jobs.py` | 125 |
| `app/api_ml_readiness.py` | 157 |
| `app/api_ml_relative_upside.py` | 182 |
| `app/api_ml_sanity.py` | 65 |
| `app/api_nav_discount.py` | 160 |
| `app/api_three_push_param.py` | 327 |
| `app/api_universe.py` | 138 |
| `app/config.py` | 61 |
| `app/decision_evidence_store.py` | 543 |
| `app/delivery.py` | 251 |
| `app/draft.py` | 586 |
| `app/draft_message.py` | 427 |
| `app/draft_message_focus.py` | 273 |
| `app/draft_three_push.py` | 360 |
| `app/etf_constituents_analysis.py` | 283 |
| `app/etf_constituents_fetcher.py` | 388 |
| `app/etf_constituents_service.py` | 326 |
| `app/etf_constituents_store.py` | 291 |
| `app/etf_nav_fetcher.py` | 87 |
| `app/etf_nav_service.py` | 433 |
| `app/etf_nav_store.py` | 224 |
| `app/factors/__init__.py` | 24 |
| `app/factors/portfolio_concentration.py` | 185 |
| `app/holdings.py` | 232 |
| `app/holdings_enrich.py` | 233 |
| `app/holdings_market_evidence.py` | 538 |
| `app/market_benchmark_store.py` | 198 |
| `app/market_cache.py` | 183 |
| `app/market_data_fdr.py` | 300 |
| `app/market_data_store.py` | 382 |
| `app/market_naver.py` | 135 |
| `app/market_refresh_service.py` | 332 |
| `app/market_regime.py` | 253 |
| `app/market_topn.py` | 383 |
| `app/market_topn_helpers.py` | 275 |
| `app/message_falling_etf_bullet.py` | 77 |
| `app/message_helpers.py` | 124 |
| `app/message_holdings_briefing.py` | 110 |
| `app/message_holdings_market_evidence_bullet.py` | 139 |
| `app/message_market_briefing.py` | 235 |
| `app/message_spike_alert.py` | 251 |
| `app/message_universe_bullet.py` | 68 |
| `app/ml_baseline_candidate.py` | 426 |
| `app/ml_baseline_evidence.py` | 452 |
| `app/ml_baseline_risk.py` | 390 |
| `app/ml_baseline_targets.py` | 352 |
| `app/ml_baseline_v0.py` | 199 |
| `app/ml_feature_builder.py` | 455 |
| `app/ml_feature_nav_lookup.py` | 78 |
| `app/ml_feature_primitives.py` | 124 |
| `app/ml_feature_sanity.py` | 561 |
| `app/ml_feature_sanity_helpers.py` | 141 |
| `app/ml_feature_store.py` | 376 |
| `app/ml_job_runner.py` | 502 |
| `app/ml_relative_upside_features.py` | 241 |
| `app/ml_relative_upside_model.py` | 279 |
| `app/ml_relative_upside_score.py` | 242 |
| `app/models.py` | 86 |
| `app/momentum/__init__.py` | 59 |
| `app/momentum/holdings_mode.py` | 239 |
| `app/momentum/universe_mode.py` | 382 |
| `app/naver_etf_universe_fetcher.py` | 321 |
| `app/price_history_pykrx.py` | 138 |
| `app/push_context.py` | 83 |
| `app/push_context_format.py` | 79 |
| `app/push_context_holdings.py` | 228 |
| `app/push_context_market.py` | 294 |
| `app/push_context_spike.py` | 213 |
| `app/push_user_copy.py` | 217 |
| `app/push_user_labels.py` | 45 |
| `app/runtime_kr_quote_probe.py` | 182 |
| `app/runtime_package.py` | 292 |
| `app/runtime_probe_cache.py` | 133 |
| `app/runtime_us_indices_probe.py` | 171 |
| `app/sample_draft.py` | 51 |
| `app/short_term_momentum.py` | 244 |
| `app/state.py` | 36 |
| `app/store.py` | 99 |
| `app/three_push_package_exporter.py` | 326 |
| `app/three_push_runner_common.py` | 307 |
| `app/three_push_runtime_message_builder.py` | 203 |
| `app/three_push_runtime_param.py` | 317 |
| `app/universe_refresh.py` | 263 |
| `app/universe_seed.py` | 242 |
| **app/ 합계** | **22,406** |

### legacy/ (.py)

| 파일 | 라인 수 |
|---|---|
| `legacy/ui_app.py` | 171 |
| **legacy/ 합계** | **171** |

### scripts/ (.py)

| 파일 | 라인 수 |
|---|---|
| `scripts/check_ml_feature_sanity.py` | 102 |
| `scripts/create_three_push_runtime_param.py` | 134 |
| `scripts/diagnose_constituents_source.py` | 456 |
| `scripts/diagnose_nav_discount_source.py` | 594 |
| `scripts/diagnose_nav_discount_source_helpers.py` | 422 |
| `scripts/generate_ml_features.py` | 152 |
| `scripts/refresh_nav_universe.py` | 113 |
| `scripts/run_ml_baseline_v0.py` | 92 |
| `scripts/run_ml_relative_upside_score_v0.py` | 272 |
| `scripts/run_three_push_oci.py` | **672** ← ambiguity |
| `scripts/run_three_push_runtime_oci.py` | 294 |
| `scripts/sync_three_push_packages.py` | 479 |
| `scripts/sync_three_push_runtime_param.py` | 218 |
| `scripts/verify_three_push_packages_oci.py` | 270 |
| `scripts/verify_three_push_param_oci.py` | 140 |
| **scripts/ 합계** | **4,410** |

### tests/ (.py)

| 파일 | 라인 수 |
|---|---|
| `tests/__init__.py` | 0 |
| `tests/_helpers.py` | 251 |
| `tests/conftest.py` | 157 |
| `tests/test_api_holdings_market_evidence.py` | 153 |
| `tests/test_api_ml_relative_upside.py` | 350 |
| `tests/test_api_nav_discount.py` | 173 |
| `tests/test_decision_evidence_store.py` | 667 |
| `tests/test_decision_sessions_api.py` | 335 |
| `tests/test_etf_constituents_analysis.py` | 138 |
| `tests/test_etf_constituents_api.py` | 243 |
| `tests/test_etf_constituents_naver_fetcher.py` | 191 |
| `tests/test_etf_constituents_naver_integration.py` | 315 |
| `tests/test_etf_constituents_service.py` | 225 |
| `tests/test_etf_constituents_store.py` | 136 |
| `tests/test_etf_nav.py` | 252 |
| `tests/test_factor_signals.py` | 431 |
| `tests/test_holdings_account_group.py` | 334 |
| `tests/test_holdings_draft_flow.py` | 244 |
| `tests/test_holdings_market_enrichment.py` | 504 |
| `tests/test_holdings_market_evidence.py` | 332 |
| `tests/test_holdings_message_text.py` | 924 |
| `tests/test_market_benchmark_store.py` | 149 |
| `tests/test_market_data_fdr.py` | 214 |
| `tests/test_market_data_store.py` | 224 |
| `tests/test_market_regime.py` | 127 |
| `tests/test_market_topn.py` | 742 |
| `tests/test_market_topn_api.py` | 617 |
| `tests/test_message_holdings_market_evidence_bullet.py` | 214 |
| `tests/test_ml_baseline_evidence.py` | 499 |
| `tests/test_ml_baseline_v0.py` | 288 |
| `tests/test_ml_feature_lane.py` | 320 |
| `tests/test_ml_feature_sanity.py` | 302 |
| `tests/test_ml_job_runner.py` | 513 |
| `tests/test_ml_relative_upside_features.py` | 119 |
| `tests/test_ml_relative_upside_model.py` | 91 |
| `tests/test_ml_relative_upside_score.py` | 178 |
| `tests/test_momentum_holdings.py` | 317 |
| `tests/test_naver_etf_universe.py` | 305 |
| `tests/test_poc1_loop.py` | 298 |
| `tests/test_runtime_package.py` | 670 |
| `tests/test_runtime_probe_cache.py` | 212 |
| `tests/test_short_term_momentum.py` | 148 |
| `tests/test_step7a_etf_watch_candidate.py` | 196 |
| `tests/test_step7b_holdings_status_briefing.py` | 202 |
| `tests/test_step7c_falling_etf_caution.py` | 410 |
| `tests/test_three_push_contract.py` | **531** ← Round A 수정 (+26) |
| `tests/test_three_push_message_text_runtime_evidence.py` | 638 |
| `tests/test_three_push_param_api.py` | 105 |
| `tests/test_three_push_runtime_message_builder.py` | 147 |
| `tests/test_three_push_runtime_param.py` | 248 |
| `tests/test_universe_momentum_step6.py` | 396 |
| `tests/test_universe_seed.py` | 307 |
| **tests/ 합계** | **16,082** |

### frontend/ (.tsx / .ts)

| 파일 | 라인 수 |
|---|---|
| `frontend/app/components/AISessionsCreateTab.tsx` | 353 |
| `frontend/app/components/AISessionsListTab.tsx` | 323 |
| `frontend/app/components/AISessionsView.tsx` | 103 |
| `frontend/app/components/ApprovalTelegramView.tsx` | 96 |
| `frontend/app/components/CandidateTable.tsx` | 356 |
| `frontend/app/components/ConstituentsTab.tsx` | 231 |
| `frontend/app/components/DashboardView.tsx` | 152 |
| `frontend/app/components/DataStatusView.tsx` | 363 |
| `frontend/app/components/ETFExposureView.tsx` | 344 |
| `frontend/app/components/EnrichedHoldingsSection.tsx` | 515 |
| `frontend/app/components/EvidenceDetails.tsx` | 343 |
| `frontend/app/components/HoldingsClient.tsx` | 406 |
| `frontend/app/components/HoldingsCompareView.tsx` | 533 |
| `frontend/app/components/HoldingsMarketEvidenceCard.tsx` | 290 |
| `frontend/app/components/HoldingsOverlapBridgeCard.tsx` | 206 |
| `frontend/app/components/HoldingsView.tsx` | 37 |
| `frontend/app/components/JudgmentReasonSection.tsx` | 197 |
| `frontend/app/components/LeftSidebar.tsx` | 70 |
| `frontend/app/components/MLBaselineV0Card.tsx` | 357 |
| `frontend/app/components/MLEvidenceRefreshCard.tsx` | 298 |
| `frontend/app/components/MLFeatureSanityCard.tsx` | 312 |
| `frontend/app/components/MLTimeseriesReadinessCard.tsx` | 151 |
| `frontend/app/components/MainPanel.tsx` | 78 |
| `frontend/app/components/MarketContextCard.tsx` | 131 |
| `frontend/app/components/MarketDiscoveryView.tsx` | 789 |
| `frontend/app/components/MomentumCandidatesSection.tsx` | 82 |
| `frontend/app/components/NavDiscountPlaceholderCard.tsx` | 144 |
| `frontend/app/components/OverlapTab.tsx` | 106 |
| `frontend/app/components/RelativeUpsideRunCard.tsx` | 207 |
| `frontend/app/components/RunPanel.tsx` | 489 |
| `frontend/app/components/RuntimePackageStatusCard.tsx` | 204 |
| `frontend/app/components/SampleDraftQuickButton.tsx` | 62 |
| `frontend/app/components/ThreePushDraftCard.tsx` | 107 |
| `frontend/app/components/ThreePushParamCard.tsx` | 204 |
| `frontend/app/components/TransferToAISessionsCard.tsx` | 206 |
| `frontend/app/components/TransferToETFExposureCard.tsx` | 85 |
| `frontend/app/components/UniverseRefreshPanel.tsx` | 237 |
| `frontend/app/components/holdings_compare/SelectedDetail.tsx` | 198 |
| `frontend/app/components/holdings_compare/helpers.ts` | 330 |
| `frontend/app/layout.tsx` | 19 |
| `frontend/app/page.tsx` | 7 |
| `frontend/lib/aiSessionsDraft.ts` | 86 |
| `frontend/lib/api/core.ts` | 80 |
| `frontend/lib/api/decisionSessions.ts` | 174 |
| `frontend/lib/api/etfExposure.ts` | 150 |
| `frontend/lib/api/holdings.ts` | 227 |
| `frontend/lib/api/index.ts` | 24 |
| `frontend/lib/api/market.ts` | 249 |
| `frontend/lib/api/marketEvidence.ts` | 116 |
| `frontend/lib/api/mlBaselineV0.ts` | 121 |
| `frontend/lib/api/mlJobs.ts` | 82 |
| `frontend/lib/api/mlReadiness.ts` | 28 |
| `frontend/lib/api/mlRelativeUpside.ts` | 30 |
| `frontend/lib/api/mlSanity.ts` | 68 |
| `frontend/lib/api/navDiscount.ts` | 40 |
| `frontend/lib/api/runApproval.ts` | 171 |
| `frontend/lib/api/threePushParam.ts` | 48 |
| `frontend/lib/api/universeMomentum.ts` | 73 |
| `frontend/lib/etfExposureDraft.ts` | 150 |
| `frontend/lib/holdings_view.ts` | 186 |
| `frontend/lib/marketDiscoveryCopyText.ts` | 392 |
| `frontend/next.config.ts` | 9 |
| **frontend/ 합계** | **12,225** |

---

## 5. D-1 회귀 해소

| 항목 | 내용 |
|---|---|
| 테스트 | `tests/test_three_push_contract.py::test_generate_spike_alert_via_unified_endpoint` |
| 원인 | commit `21e400b0` 에서 `generate_spike_alert_draft` 에 `build_runtime_package` + `is_failed_package` 가드 추가 시 테스트 isolation(runtime probe mock) 미추가. 테스트 환경에서 `kr_realtime_price_snapshot.status=unavailable` + `universe_momentum_snapshot={}` → `_check_spike_alert_requirements` 실패 → `generation_status=failed` → `message_text=None` |
| 수정 | `tests/test_three_push_contract.py` 에 `_runtime_snapshot_with_cache` / `_load_universe_artifact_for_spike` stub 2개 추가. assertion 변경 0건 |
| 라인 수 | 505 → 531 (wc -l, +26) |

---

## 6. 검증 결과

| 항목 | 결과 |
|---|---|
| backend 전체 테스트 | **617 passed**, 0 failed, 0 deselected |
| black | PASS |
| flake8 | PASS |
| frontend lint | 미실행 (Round A 범위 — frontend 변경 0건) |
| frontend build | 미실행 (Round A 범위 — frontend 변경 0건) |
| 새 기능 추가 | false |

---

## 7. 변경 파일 목록 (git status 실측)

```
 M docs/STATE_LATEST.md
 M docs/handoff/POC2_B_NEXT_ACTIONS.md
 M tests/test_three_push_contract.py
A  docs/handoff/POC2_CLEANUP_KS10_ROUND_A_CONCLUSION.md
```

- `tests/test_three_push_contract.py`: 수정 (505→531 라인)
- `docs/STATE_LATEST.md`: 수정
- `docs/handoff/POC2_B_NEXT_ACTIONS.md`: 수정
- `docs/handoff/POC2_CLEANUP_KS10_ROUND_A_CONCLUSION.md`: 신규 (staged)

---

## 8. Round B 대상 (다음 Round 진입 전 확인 필요)

1. `scripts/run_three_push_oci.py` 672 라인 — KS-10 trigger 적용 여부 사용자 결정 대기.
2. `app/api_market_topn.py` 636 라인 — near-threshold 파일 분리 (Round B 주요 대상).
3. 신규 near 발생 여부 전체 재측정 후 Round B 시작.
