"""POC6-13 — 전향 비교(POC6-06) 정기 실행 · 보관 연결 · 연구 자산 외장 백업.

기존 06 명령(`scripts/run_forward_compare.py run --pull` · `archive --upload`)을 자식 프로세스로 부르고
그 산출물을 읽기만 한다. 06 · 05 산출물을 바깥에서 고치지 않는다. 자동화 상태는
`state/ml/operations/poc6_13/` 에만 쓴다(설계 V1 · PLAN 판정 2026-10-28).
"""
