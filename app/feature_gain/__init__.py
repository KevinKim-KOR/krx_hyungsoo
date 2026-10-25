"""POC6-08 — 거래량 · 동일 기간 상대강도의 ML 추가 효용 검증(PC 회고 연구 · CPU · 수동 CLI).

설계 `docs/ai_design/POC6/POC6-08_VOLUME_AND_RELATIVE_STRENGTH_FEATURE_VALUE_DESIGN_V1.md` ·
PLAN `docs/ai_plan/POC6/POC6-08_VOLUME_AND_RELATIVE_STRENGTH_FEATURE_VALUE_PLAN_V1.md`(§7 판정 반영) ·
판정 `..._PLAN_DECISION_2026-10-24.md`.

```text
protocol  고정 입력(경로 · 완전한 해시) · 기준 · 구성 · 범위 · 실행 잠금 · 1회 쓰기
inputs    입력 검증 · 연구 축 · 종목별 행(P · V · R · D20 · 사유) · 구간 · 적격 · 가용
study     여섯 구성 학습 · 예측(원시 + [-1, 0] 제한) · 모델 bytes · 복원 대조
report    날짜 균형 MAE · 구간 · 종목별 · 큰 하락 MAE · U · A/B 판정 · report.md/json
```

06 코드 · protocol · 저장 형식은 바꾸지 않는다(함수 단위 재사용만). 산출물은 `state/ml/research/poc6_08/` 에
추가만 한다. 외부 조회 · OCI · 라이브 DB 쓰기 없음.
"""
