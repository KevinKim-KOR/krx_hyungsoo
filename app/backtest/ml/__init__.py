"""P210-STEP10A Track B ML 패키지.

외부 진입점:
- `build_predictions_for_sweep`: sweep 모듈에서 호출하여 walk-forward
  학습 + per-rebalance-date prediction dict 을 반환.
- `format_training_report`: training report 산출물(md/json) 생성.

내부 구조 (단일 책임 분리):
- `predictive_risk_classifier.py`:
  - dataset build / label generation / feature generation
  - leakage check / walk-forward train-predict / report formatting
"""

from app.backtest.ml.predictive_risk_classifier import (
    build_predictions_for_sweep,
    format_training_report,
)

__all__ = [
    "build_predictions_for_sweep",
    "format_training_report",
]
