"""POC5-20 — 가격 · 거래량 · 변동성 근거 조합의 과거 사례 대조(PC 수동 · 읽기 전용 연구 산출).

설계 `docs/ai_design/POC5/POC5-20_OBSERVED_EVIDENCE_COMBINATION_REVIEW_DESIGN_V1.md` ·
PLAN `docs/ai_plan/POC5/POC5-20_OBSERVED_EVIDENCE_COMBINATION_REVIEW_PLAN_V1.md`(§5 판정 반영).

- `observations` — 기준일 t 이하 자료만으로 세 관측(하락 구간 · 거래량 배수 · 흔들림 비교) · t 다음
  2026 캘린더 20거래일의 두 결과 · 공통 표본에서 빠진 첫 사유.
- `tables` — 같은 공통 표본의 가격 구간 표 · 네 조합 표 · 분위 · 날짜별 중앙값의 중앙값 · 앞 / 뒤 기간.
- `report` — 한 번의 읽기 트랜잭션 · 입력 사본 · 입력 식별 · report.md · report.json · input_snapshot.json.

학습 · 예측 · 기준 탐색 · 점수 · 위험 등급 · 운영 채택이 아니다(Q6 운영 계약 OPEN 유지).
"""
