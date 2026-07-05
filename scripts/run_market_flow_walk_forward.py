"""Market Flow ML Walk-forward Lookback v1 수동 실행 진입점 (2026-07-05).

SQLite read only. 외부 호출 없음. 기존 baseline artifact 미변경.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.market_data_store import DEFAULT_DB_PATH
from app.market_flow_walk_forward import (
    WALK_FORWARD_PREDICTIONS_CSV_PATH,
    WALK_FORWARD_SUMMARY_JSON_PATH,
    run_walk_forward,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Market Flow ML Walk-forward Lookback v1 (SQLite read only)."
    )
    p.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument(
        "--predictions-path",
        type=Path,
        default=WALK_FORWARD_PREDICTIONS_CSV_PATH,
    )
    p.add_argument("--summary-path", type=Path, default=WALK_FORWARD_SUMMARY_JSON_PATH)
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    payload = run_walk_forward(
        db_path=args.db_path,
        predictions_path=args.predictions_path,
        summary_path=args.summary_path,
    )
    ev = payload["evaluation"]
    m = payload["metrics"]
    print(
        f"[market-flow-walk-forward] status={payload['status']} "
        f"predictions={ev['prediction_count']} "
        f"excluded={ev['excluded_prediction_count']}"
    )
    if ev["prediction_count"]:
        print(
            f"[period] {ev['start_date']} ~ {ev['end_date']} "
            f"(target_end year buckets: {len(payload['yearly_metrics'])})"
        )
        print(f"[ridge] {m['ridge']}")
        print(f"[simple_baseline] {m['simple_baseline']}")
        print(f"[ridge_minus_simple] {m['ridge_minus_simple']}")
    print(f"[artifact] predictions={args.predictions_path}")
    print(f"[artifact] summary={args.summary_path}")
    return 0 if payload["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
