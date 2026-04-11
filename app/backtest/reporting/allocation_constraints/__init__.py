"""P207-STEP7C allocation constraints sweep 패키지.

외부 진입점:
- `run_allocation_constraint_sweep`: allocation_experiments sweep 실행
  + compare md/csv 생성 (run_backtest.py 에서 호출)
- `build_allocation_meta`: format_result 용 P207 meta 필드 빌더
  (run_backtest.py 의 format_result 에서 호출)

내부 구조 (단일 책임 분리 — R4 cleanup, P207 inline 블록 추출):
- `sweep.py`: run_allocation_constraint_sweep
- `diagnostic.py`: allocation_experiment_verdict
- `report_writer.py`: write_allocation_constraint_compare (md/csv)
- `meta_builder.py`: build_allocation_meta (format_result 메타 필드)

R4 이전에는 모두 `app/run_backtest.py` 의 `run_cli_backtest` / `format_result`
내부에 inline 으로 존재했음. drawdown/, holding_structure/ 패키지와 대칭성
확보를 위해 별도 패키지로 추출.
"""

from app.backtest.reporting.allocation_constraints.meta_builder import (
    build_allocation_meta,
)
from app.backtest.reporting.allocation_constraints.sweep import (
    run_allocation_constraint_sweep,
)

__all__ = [
    "run_allocation_constraint_sweep",
    "build_allocation_meta",
]
