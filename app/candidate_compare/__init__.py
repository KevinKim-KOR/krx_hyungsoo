"""POC7-03 주간 ETF 전체 비교와 우선 검토 후보 — PC 연구(맥북) · 운영 경로 무변경.

```text
설계   docs/ai_design/POC7/POC7_03_WEEKLY_ETF_CANDIDATE_COMPARISON_DESIGN_V1_2026-11-24.md
판정   docs/ai_design/POC7/POC7_03_WEEKLY_ETF_CANDIDATE_COMPARISON_PLAN_DECISION_2026-11-24.md
PLAN   docs/ai_plan/POC7/POC7_03_WEEKLY_ETF_CANDIDATE_COMPARISON_PLAN_V1.md
모듈   protocol(고정 설정) · rules(두 기준 · 오른 주 — 연구와 이번 주 화면이 같은 함수) · population(봉인 주 기록)
       · study(체결 · 평가 · 지표 · 판정) · flow(prepare · run) · verify(독립 재계산) · report(글)
       · current(이번 주 · PC 시세 DB 읽기 전용) · copy(AI 비교 묶음) · page(로컬 HTML) · crosscheck(AC1)
경계   POC7-01 해시 잠금 파일(app/entry_timing/* · krx_sealed_reader 등 17개)은 불러 쓰기만 한다
```
"""
