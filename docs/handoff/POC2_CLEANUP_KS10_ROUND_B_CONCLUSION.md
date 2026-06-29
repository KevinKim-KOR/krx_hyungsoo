# Cleanup KS-10 Round B — Conclusion

작성일: 2026-06-29
측정 방식: `wc -l` (Bash) 통일. 모든 라인 수는 본 Round 작업 후 실측값.

---

## 1. 목표

- Round A 에서 확인된 near/ambiguity 파일을 책임 단위로 분리
- 전체 재측정에서 KS-10 trigger=0, near=0 달성

---

## 2. 분리 결과 (wc -l 실측)

### scripts/run_three_push_oci.py (672 → 255줄)

| 구분 | 파일 | 라인 수 (wc -l) |
|---|---|---|
| entrypoint + flow control | `scripts/run_three_push_oci.py` | **255** |
| 상수·설정·guard·I/O 헬퍼 | `scripts/three_push_oci_helpers.py` (신규) | **450** |

분리 전 672줄 → 분리 후 최대 450줄. `scripts/` 는 KS-10 기준 (`app/` ≥650) 미적용.

보존 항목:
- OCI 실행 동작 / CLI usage / dry-run·send 분기 / duplicate send 방지 / PARAM 적용 / Telegram 발송 결과 — 모두 보존.
- `run_three_push_oci.run()` + `main()` signature 변경 0건.

### app/api_market_topn.py (636 → 178줄)

| 구분 | 파일 | 라인 수 (wc -l) |
|---|---|---|
| HTTP request/response 조립 (endpoint 3개) | `app/api_market_topn.py` | **178** |
| Pydantic 모델 (Response/Request 모두) | `app/api_market_topn_models.py` (신규) | **234** |
| 변환 헬퍼 + evidence 보강 + score 머지 + context 변환 | `app/api_market_topn_service.py` (신규) | **274** |

분리 전 636줄 → 분리 후 최대 274줄. 세 파일 모두 KS-10 near(≥600) / trigger(≥650) 미달.

보존 항목:
- 모든 endpoint (`/market/topn/latest` / `/market/refresh` / `/market/refresh/status`) 유지.
- 모든 응답 필드 유지.
- Market Discovery 계산 / relative_upside_score 응답 / market_context 응답 변경 0건.

---

## 3. 설계 결정 — db_path 파라미터화

`api_market_topn_service.enrich_candidates_with_evidence` 및 `build_nav_discount_payload` 가
`DEFAULT_DB_PATH` 를 내부에서 직접 읽는 구조에서 `db_path` 파라미터를 받는 구조로 변경.

**이유**: 기존 테스트 (`test_market_topn_api.py` `api_client` fixture) 가
`monkeypatch.setattr(api_market_topn, "DEFAULT_DB_PATH", fake_db)` 로 DB 경로를 교체하는데,
service 모듈 분리 후 service 의 `DEFAULT_DB_PATH` 는 별도 모듈에 묶이므로 patch 가 누락됨.
테스트 코드를 건드리지 않고 호출자 (`api_market_topn.py`) 가 `DEFAULT_DB_PATH` 를 service 에 전달하는 방식으로 해결.

---

## 4. Round B 후 KS-10 재분류

| 구분 | 기준 | 파일 (최대) | 라인 수 | 판정 |
|---|---|---|---|---|
| app/ trigger | ≥ 650 | `app/draft.py` | 586 | 없음 |
| app/ near | ≥ 600 | `app/draft.py` | 586 | 없음 |
| tests/ trigger (단일 주제) | ≥ 2,500 | `tests/test_holdings_message_text.py` | 924 | 없음 |
| tests/ trigger (혼합) | ≥ 1,500 | `tests/test_holdings_message_text.py` | 924 | 없음 |
| frontend/ trigger | ≥ 900 | `frontend/app/components/MarketDiscoveryView.tsx` | 789 | 없음 |
| frontend/ near | ≥ 850 | `frontend/app/components/MarketDiscoveryView.tsx` | 789 | 없음 |

**결론: trigger 0건 / near 0건.**

---

## 5. 검증 결과

| 항목 | 결과 |
|---|---|
| backend 전체 테스트 | **617 passed**, 0 failed, 0 deselected |
| black | PASS |
| flake8 | PASS (FIX 라운드: `scripts/diagnose_constituents_source.py` F541 4건 수정 포함) |
| frontend lint | PASS (eslint — 출력 없음) |
| frontend build | PASS (Next.js static prerender 완료) |
| 새 기능 추가 | false |

---

## 6. 변경 파일 목록

- `app/api_market_topn.py`: 수정 (636 → 178줄)
- `scripts/run_three_push_oci.py`: 수정 (672 → 255줄)
- `scripts/diagnose_constituents_source.py`: 수정 (F541 f-string 4건 수정)
- `app/api_market_topn_models.py`: 신규 (234줄)
- `app/api_market_topn_service.py`: 신규 (274줄)
- `scripts/three_push_oci_helpers.py`: 신규 (450줄)
- `docs/STATE_LATEST.md`: 수정
- `docs/handoff/POC2_B_NEXT_ACTIONS.md`: 수정
- `docs/handoff/POC2_FEATURE_INVENTORY.md`: 수정 (§2.32 + §2.33 추가)
- `docs/handoff/POC2_CLEANUP_KS10_ROUND_B_CONCLUSION.md`: 신규 (본 파일)
- `docs/handoff/POC2_CLEANUP_KS10_CONCLUSION.md`: 신규 (Round A+B 통합 요약)

---

## 7. 다음 분기 후보

본 Round B 로 KS-10 파일 크기 구조 정리 완료. 다음 작업 방향:

1. **D-2 결함 해소** — `app/market_refresh_service.py` in-memory state 재시작 시 소실.
2. **ML 축2** — 위험 감지용 시계열 빈자리 채우기.
3. **OCI read model foundation** — PC 판단 화면 + ML 1차 결과 확보 뒤 진입.

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.
