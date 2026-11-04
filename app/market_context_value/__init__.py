"""POC6-20 — 시장 정보 추가 효용 비교(PC 회고 연구 · CPU LightGBM ML_B · 수동 CLI).

설계 `docs/ai_design/POC6/POC6-20_MARKET_CONTEXT_INCREMENTAL_VALUE_DESIGN_V1.md` ·
PLAN `docs/ai_plan/POC6/POC6-20_MARKET_CONTEXT_INCREMENTAL_VALUE_PLAN_V1.md`(§5 판정 반영) ·
판정 `..._PLAN_DECISION_2026-11-04.md`.

가격의 의미: 봉인 KRX 합성 가격지수와 POC6-19 연구 사본으로 만든 회고 모의 비교다. 총수익 검증 · 실제 권고
채택 · 운영 ML 이 아니다(TOTAL_RETURN_VALIDATED=NO · OPERATION_ADOPTION=NO).

```text
market_inputs  POC6-19 사본(해시 확인) → 신호일별 시장 4열 · 가용 시각 근거 · 미정의 사유
learner        H1 ML_B 설정 그대로 · 열 폭만 인자(P = 30열 · M = 34열)
protocol       고정 입력 · 기대 분모(PLAN 표) · recipe · 잠금 검사
report         판정 축(추가 효용 · 목적 · 위험 · 비용) · report.md
flow           prepare/lock · run(선행 재생 → 주 평가) · 실패 기록 · 예산 감시
verify         저장 산출물 재계산 · 정책 재적용 · 독립 손검산 연결
```

H1(`app/weekly_selection`) · POC6-19 · 공용 reader · 운영 코드 · UI · API · OCI · PUSH 변경 없음.
산출물은 `state/ml/research/poc6_20/` 에 추가만 한다(PC_ONLY).
"""

# H1 패키지를 먼저 불러온다 — 그 안에서 LightGBM(Homebrew libomp)을 torch 보다 먼저 올린다(OpenMP 순서 · H1 판정).
import app.weekly_selection  # noqa: F401,E402
