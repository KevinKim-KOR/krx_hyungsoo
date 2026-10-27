"""POC6-11 — H1 주간 ETF 상대성과 선별 검증(PC 회고 연구 · CPU LightGBM · 수동 CLI).

설계 `docs/ai_design/POC6/POC6-11_WEEKLY_ETF_RELATIVE_RETURN_SELECTION_DESIGN_V1.md` ·
PLAN `docs/ai_plan/POC6/POC6-11_WEEKLY_ETF_RELATIVE_RETURN_SELECTION_PLAN_V1.md`(§6 판정 반영) ·
판정 `..._PLAN_DECISION_2026-10-26.md`.

가격의 의미: 봉인 KRX `KRX_BASEPRICE_CHAIN` 합성 가격지수의 모의 성과다. 분배금 포함 총수익 · 실제 계좌 ·
추천 채택 · 프로젝트 완료가 아니다(TOTAL_RETURN_VALIDATED=NO · OPERATION_ADOPTION=NO).

```text
data      봉인 확인 · 원시 OHLCV 어댑터(새로 씀) · 합성 O/H/L · 체결 가능 · 주간 신호 · 시점별 자격
features  30열 · 정답 z · y · 가용성 · 분기 학습 표본 · 가중치 · 모델 배정
model     LightGBM 학습 · 저장 · 복원 · 예측 · 해석된 매개변수 · 환경(libomp 실제 로드 경로)
policy    공통 운용(주간 선정 · 보호 이탈 · 재진입 대기 · 체결 · 장부) · K
report    지표 · 회전율 · 보유기간 · bootstrap · 상태 축 · 판정 · report.md
protocol  고정 입력 · 기준 · 잠금 사실(PLAN 표 대조) · 모델 적용 일정 · 산출물 해시
flow      prepare/lock · run(검증 → 선택 → 시험) · 실패 기록 · 예산 감시
audit     정책 함수를 쓰지 않는 독립 손검산(장부 · 체결 · 계획 · K)
evidence  필수 근거 계약(기록이 주장하는 범위 = 있어야 할 단계 · 파일 · 칸)
verify    저장 산출물 재계산 · 정책 재적용 · 손검산 연결
```

공용 reader · 운영 코드 · UI · API · OCI · PUSH 변경 없음. POC6-10 로컬 브랜치 코드 · Backtrader 미사용.
산출물은 `state/ml/research/poc6_11/` 에 추가만 한다(PC_ONLY).
LightGBM(https://github.com/lightgbm-org/LightGBM)은 MIT License 이며 연구 venv 에만 해시 고정 설치한다.
"""

try:
    # LightGBM(Homebrew libomp)을 torch 보다 먼저 올린다. POC4 이름 필터(ml_pit_universe)를 불러오면 torch 와 그
    # libomp 가 함께 올라오는데, torch 의 libomp 가 먼저면 LightGBM 학습 자료 생성에서 세그폴트가 난다
    # (설치 확인 2026-10-27 실측). 순서는 prepare · run · verify 가 `model.openmp_problem()` 으로 다시 확인한다.
    import lightgbm as _lightgbm  # noqa: F401
except ImportError:  # 설치 전 — 자료 · 장부 모듈과 가짜 자료 시험만 쓰는 경우
    _lightgbm = None
