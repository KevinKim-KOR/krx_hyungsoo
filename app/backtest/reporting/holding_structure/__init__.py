"""P208-STEP8A holding structure 비교 sweep 패키지.

외부 진입점:
- `run_holding_structure_sweep`: G1~G8 실험군 실행 + md/csv/json 생성
  (run_backtest.py 에서 호출)

내부 구조 (단일 책임 분리 — R3 cleanup):
- `sweep.py`: run_holding_structure_sweep, _build_allocation_block
- `verdict.py`: _verdict (CAGR>15 & MDD<10 판정)
- `report_writer.py`: _write_outputs (md/csv/json 렌더러)
- `diagnostic.py`: _diagnostic_summary (Q1~Q4 진단)

R3 이전에는 모두 `holding_structure_compare.py` 라는 단일 파일에 있었음.
"""

from app.backtest.reporting.holding_structure.sweep import (
    run_holding_structure_sweep,
)

__all__ = [
    "run_holding_structure_sweep",
]
