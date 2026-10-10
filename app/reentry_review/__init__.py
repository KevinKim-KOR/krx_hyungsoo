"""POC5-06 — 수동 재진입 검토 · ML 근거(PC 전용 · 사용자 버튼 · 선택 종목 1개).

설계 `docs/ai_design/POC5/POC5-06_MANUAL_REENTRY_REVIEW_AND_ML_EVIDENCE_DESIGN_V1.md` 개정 2 ·
PLAN `docs/ai_plan/POC5/POC5-06_MANUAL_REENTRY_REVIEW_AND_ML_EVIDENCE_PLAN_V1.md` §2 · §7.

```text
prices   선택 ETF 저장 종가 한 번 읽기(mode=ro) · 연구 축 · 감지된 가격 경계
model    D20(이후 20거래일 최저 종가 변화) · feature 5 · 3구간 검증 · 학습 중앙값 기준 · 최종 추정
ledger   PC 원장 사본에서 선택 ticker 의 알림 근거(SUBJECT · SECTOR_REPRESENTATIVE · INDEX_GROUP_MEMBER)
review   선택 검증 · 내 거래 · 저장된 근거 · ML 실행 · 연구 산출물
models   상태 · 문구 · 응답 모양
```

2026-10-09 POC5-06 한정 연구 예외(설계 개정 2 §10-1): 연구 추정이며 운영 · 추천 모델이 아니다
(`ML_OPERATION_PROMOTION = NOT_APPROVED` · `CURRENT_DEPLOYABLE_ML_MODEL = none`). 자동 실행 ·
PUSH · PARAM · OCI · 보유 쓰기 · 주문 0.
"""
