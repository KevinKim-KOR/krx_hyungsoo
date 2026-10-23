"""POC6-06 — 보유 독립 ETF 대상의 전향 ML 비교 · 기록(PC 수동 · 연구 · 운영 아님).

| 모듈 | 책임 |
|---|---|
| `protocol` | 고정 상수 · 경로 · 보조 묶음 · 산출물 머리 · 한 번 쓰면 끝 파일 쓰기 |
| `cohort` | 05 목록 판 + PC 저장일 수로 고정 24종(cohort_v1) 선정 · 재현 확인 |
| `bootstrap` | 초기 장기 가격 1회 조회(승인 뒤) · 초기 회고 예제 |
| `inputs` | 05 PC 보관본에서 연구 축 · 종목별 가장 이른 유효 입력 판 · 성숙 목표 창 고르기 |
| `models` | MEDIAN · RIDGE · HGB · MLP_CPU 학습 · 저장 · 복원 · 예측 |
| `training` | 초기 · 월별 · 실패 방법 복구 학습 결정 · 예제 묶음 · 모델 판 저장 |
| `forward` | run = 성숙 → 학습 결정 → 예측 기록 → 보고 |
| `mature` | 성숙 목표(한 수신 판 · D ~ D+20) 첫 평가 고정 |
| `records` | 예측 · 목표 기록 읽기(주 기록 · 재시도 연결 · 진단 분리) |
| `report` | 같은 행 날짜 균형 MAE · 분모 · 보조 표 |
| `archive` | 05 보관소 등록 · OCI 업로드(명시 실행만) |

ML_OPERATION_PROMOTION=NOT_APPROVED · CURRENT_DEPLOYABLE_ML_MODEL=none · Q6 OPEN 그대로.
"""
