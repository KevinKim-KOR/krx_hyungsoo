"""P209-STEP9A drawdown 분석 패키지.

외부 진입점:
- `run_analysis_pipeline`: A/B 2-variant 분석 파이프라인 (run_backtest.py 에서 호출)
- `analyze_variant`: 단일 variant 분석 orchestrator (필요 시 직접 호출 가능)

내부 구조 (단일 책임 분리 — R2 cleanup):
- `window.py`: find_mdd_window (MDD 구간 식별)
- `positions.py`: _build_close_series, reconstruct_daily_positions
- `attribution.py`: compute_ticker_contributions (return attribution)
- `selection_quality.py`: compute_selection_quality, summary, verdict
- `bucket_risk.py`: compute_bucket_risk
- `pipeline.py`: analyze_variant, run_analysis_pipeline, meta injection
- `report_writer.py`: write_drawdown_contribution_report (md/json/csv)

R2 이전에는 모두 `drawdown_contribution.py` 라는 단일 god module 에 있었음.
"""

from app.backtest.reporting.drawdown.pipeline import (
    analyze_variant,
    run_analysis_pipeline,
)

__all__ = [
    "analyze_variant",
    "run_analysis_pipeline",
]
