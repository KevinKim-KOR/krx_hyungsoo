"""POC6-23 — 비용을 반영한 주간 의사결정 학습(PC 회고 연구 · 70계수 공유 선형 · MAE ↔ SPO+ · SciPy HiGHS · 수동 CLI).

원 설계 `docs/ai_design/POC6/POC6_23_COST_AWARE_WEEKLY_DECISION_LEARNING_DESIGN_V1.md` ·
PLAN 판정 · 통합 설계 V1 개정 2 `..._PLAN_DECISION_2026-11-05.md`(우선) ·
PLAN `docs/ai_plan/POC6/POC6_23_COST_AWARE_WEEKLY_DECISION_LEARNING_PLAN_V1.md`.

가격의 의미: 봉인 KRX 합성 가격지수와 POC6-19 연구 사본으로 만든 이미 본 기간의 탐색적 회고 모의 비교다.
총수익 검증 · 실제 권고 채택 · 운영 ML 이 아니다(TOTAL_RETURN_VALIDATED=NO · OPERATION_ADOPTION=NO).

```text
actions   허용 행동(KEEP · SELL · BUY · SWITCH ≤ 36) · 예정 슬롯 · 예산 경계 · b · s · k · 70칸 z
labels    R0 20bp 참조 경로(판단 직전 상태 복제 · POC6-21 simulate 대조) · 행동별 20거래일 분기 g
learn     분기 표준화(정상 결측 평균 대치) · s_g · MAE · SPO+ 선형계획(HiGHS threads=1) · 수치 조건
policy    일별 루프(매수 직전 슬롯 · 현금 재확인) · P/S 주간 선택 장부 · R = POC6-21 R0 원본
audit     P/S 행동 · 점수 · 선택 독립 손검산(정책 함수 미사용) + POC6-21 체결 · 보호 검산
protocol  고정 입력 · 기대값(PLAN §1) · 분기 창 · recipe · 환경(SciPy · HiGHS · numpy · 스레드 변수)
report    AC3 ~ AC6 · bootstrap(주간 S − P) · 거래 · Q4 노출 · report.md
flow      prepare/lock · run(참조 · 정답 → 분모 → 70 fit → 선행 → 주 평가) · 실패 기록 · finish 예산 판정
verify    저장 산출물 재계산(재학습 없음) · 필수 근거 계약
```

H1(`app/weekly_selection`) · POC6-19 · POC6-20 · POC6-21(`app/trend_switch`) · POC6-22 · 운영 코드 ·
UI · API · OCI · PUSH 변경 없음. 산출물은 `state/ml/research/poc6_23/` 에 추가만 한다(PC_ONLY).
"""

# POC6-21 패키지(→ POC6-20 → H1)를 먼저 불러온다 — 그 패키지들의 import 순서(OpenMP)를 그대로 따른다.
import app.trend_switch  # noqa: F401,E402
