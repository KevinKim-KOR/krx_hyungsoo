"""POC7-02 — 로컬 AI 주간 ETF 검토 한 장 요약(PC 연구 · 맥북 개발 · Windows PC 실행).

설계 `docs/ai_design/POC7/POC7_02_WEEKLY_REVIEW_LOCAL_AI_SUMMARY_DESIGN_V1_2026-11-22.md` · PLAN
`docs/ai_plan/POC7/POC7_02_WEEKLY_REVIEW_LOCAL_AI_SUMMARY_PLAN_V1.md` · 판정
`docs/ai_design/POC7/POC7_02_WEEKLY_REVIEW_LOCAL_AI_SUMMARY_PLAN_DECISION_2026-11-23.md`
(판정이 PLAN 보다 우선).

```text
맥북        archive(맥북 서버 「주간 ETF 점검」 읽기 조회 응답 보관) → lock-key(채점용 메모 잠금 · 출력 전)
            → pack(실행 묶음 zip) → (USB) → Windows PC run_summary.bat → (USB)
            → merge(대조 · 보관) → report(비교표 · AC4)
Windows PC  runner_win(= 묶음의 run_summary.py · 표준 라이브러리만) · 환경 확인 → 합성 점검 → 실제 요약
공유 코드   render(한 장 HTML) · judge(결과 구분) — 표준 라이브러리만 · 묶음에 사본으로 들어가 두 기기가 같은 코드를 쓴다
```

운영 화면 · API · 기록 DB · OCI · PUSH 를 바꾸지 않는다. 쓰기는 `state/ml/research/poc7_02/`(git 제외)에만
POC7-01 위치 도구(`app.entry_timing.protocol` · 링크 · 폴더 밖 거부 · 한 번 쓰기)로 한다.
"""
