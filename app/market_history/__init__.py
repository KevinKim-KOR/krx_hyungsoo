"""POC6-19 — 과거 시장 자료(코스피 수급 · 원/달러 · WTI) 연구 사본 확보(PC 연구 전용).

설계 `docs/ai_design/POC6/POC6-19_HISTORICAL_MARKET_CONTEXT_RESEARCH_INPUT_DESIGN_V1.md` ·
PLAN `docs/ai_plan/POC6/POC6-19_HISTORICAL_MARKET_CONTEXT_RESEARCH_INPUT_PLAN_V1.md`(판정 보완 2건 반영).

- `fetch` — 입력 사본 · A 표본 → 조건부 B 장기 조회 · 원시 응답 보관(실행 CLI `scripts/run_market_history.py`).
- `normalize` — 원시 → 정규화(수집 중 판정과 검산이 같은 함수).
- `report` — report.json / report.md.
- `verify` — 외부 재조회 없이 원시에서 다시 계산해 대조.

운영 DB · 05 보관 · 봉인 판 · OCI · 화면 쓰기 0. 산출물 = `state/ml/research/poc6_19/<run_id>/`(git 제외).
"""
