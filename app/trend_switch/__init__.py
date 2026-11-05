"""POC6-21 — 추세 참여와 단기 재진입 · 재이탈의 ML 효용 검증(PC 회고 연구 · CPU LightGBM ML_B · 수동 CLI).

설계 `docs/ai_design/POC6/POC6-21_TREND_PARTICIPATION_AND_RECENT_SWITCH_ML_DESIGN_V1.md` ·
설계 검토 판정(통합 설계 V1 개정 2) `..._DESIGN_REVIEW_DECISION_2026-11-04.md` ·
PLAN `docs/ai_plan/POC6/POC6-21_TREND_PARTICIPATION_AND_RECENT_SWITCH_ML_PLAN_V1.md` ·
판정 `..._PLAN_DECISION_2026-11-04.md`.

가격의 의미: 봉인 KRX 합성 가격지수와 POC6-19 연구 사본으로 만든 탐색적 회고 모의 비교다. 총수익 검증 · 실제
권고 채택 · 운영 ML 이 아니다(TOTAL_RETURN_VALIDATED=NO · OPERATION_ADOPTION=NO).

```text
labels     ETF 자체 절대 정답 log(I[E+59]/O*[E]) · 날짜 사용 규칙(자격 20 · 정답 20 · 95%) · 069500 미래 행 요구 없음
policy     주간 보유/현금 전환(후보 = RET_120 상위 5 · 문턱 h · 최근 10거래일 2h) · H1 체결 · 이연 · 보호 재사용
audit      새 규칙 독립 손검산(정책 함수 미사용) · K 는 H1 audit_k
trades     완료 거래 손익(비용 포함) · 직전 손익 분류 · 10거래일 묶음 · 최장 고점 미회복 · 검토 기회 · 보류 분모
protocol   고정 입력 · 기대 분모(PLAN §2) · recipe · 잠금 검사
report     판정 축(ML 추가 효용 · 강화 효용 · 목적/위험/부담 · 높은 비용) · report.md
study      학습 · 계획 · 장부 · 쌍 bootstrap 도우미(flow · verify 공용)
flow       prepare/lock · run(선행 재생 → 주 평가) · 실패 기록 · 모든 계산 뒤 finish 예산 판정
evidence   실행 폴더 파일 · 정지 주장 · 식별자 · 보고 칸 계약
verify     저장 산출물 재계산 · 정책 재적용 · 독립 손검산 연결
```

H1(`app/weekly_selection`) · POC6-19 · POC6-20(`app/market_context_value`) · 공용 reader · 운영 코드 ·
UI · API · OCI · PUSH 변경 없음. 산출물은 `state/ml/research/poc6_21/` 에 추가만 한다(PC_ONLY).
"""

# POC6-20 패키지(→ H1)를 먼저 불러온다 — LightGBM(Homebrew libomp)을 torch 보다 먼저 올린다(OpenMP 순서).
import app.market_context_value  # noqa: F401,E402
