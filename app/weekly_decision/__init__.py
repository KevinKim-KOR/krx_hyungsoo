"""POC7-04 관심 ETF 한 건의 주간 판단 근거와 AI 검토 — 맥북 로컬 연구(운영 경로 무변경).

```text
설계   docs/ai_design/POC7/POC7_04_WEEKLY_ETF_REVIEW_DECISION_SUPPORT_DESIGN_V1_2026-11-24.md
판정   docs/ai_design/POC7/POC7_04_WEEKLY_ETF_REVIEW_DECISION_SUPPORT_PLAN_DECISION_2026-11-24.md
PLAN   docs/ai_plan/POC7/POC7_04_WEEKLY_ETF_REVIEW_DECISION_SUPPORT_PLAN_V1.md
모듈   history(지난 네 주 · 복원 · 그 주 저장 기록 · 그 뒤 관측) · peers(같은 공식 기초지수 · 같은 구조)
       · lines(첫 화면 줄 · AI에 확인할 것 · 복사문) · store(판단 한 건 = 한 파일) · page(한 장) · server(127.0.0.1)
경계   POC7-03(app/candidate_compare) 은 불러 쓰기만 · 시세 DB · 판단 근거 DB 읽기 전용 · 외부 조회 0
```
"""
