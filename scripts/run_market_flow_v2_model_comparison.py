"""Market Flow ML v2 — Data Validity + Model Comparison 수동 실행 (2026-07-05).

SQLite read only. 외부 호출 없음. 기존 baseline / walk-forward artifact 미변경.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.market_data_store import DEFAULT_DB_PATH
from app.market_flow_v2_model_comparison import (
    DATA_VALIDITY_ARTIFACT_PATH,
    PREDICTIONS_CSV_PATH,
    SUMMARY_JSON_PATH,
    run_v2_model_comparison,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Market Flow ML v2 Data Validity + Model Comparison "
        "(SQLite read only)."
    )
    p.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument(
        "--data-validity-path",
        type=Path,
        default=DATA_VALIDITY_ARTIFACT_PATH,
    )
    p.add_argument("--predictions-path", type=Path, default=PREDICTIONS_CSV_PATH)
    p.add_argument("--summary-path", type=Path, default=SUMMARY_JSON_PATH)
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    payload = run_v2_model_comparison(
        db_path=args.db_path,
        data_validity_path=args.data_validity_path,
        predictions_path=args.predictions_path,
        summary_path=args.summary_path,
    )
    ev = payload["evaluation"]
    m = payload["metrics"]
    print(
        f"[market-flow-v2] status={payload['status']} "
        f"predictions={ev['prediction_count']} "
        f"excluded={ev['excluded_prediction_count']}"
    )
    if ev["prediction_count"]:
        print(f"[period] {ev['start_date']} ~ {ev['end_date']}")
        print(f"[simple_baseline] {m['simple_baseline']}")
        print(f"[full_ridge] {m['full_ridge']}")
        print(f"[core_ridge] {m['core_ridge']}")
        print(f"[full - simple] {m['full_ridge_minus_simple']}")
        print(f"[core - simple] {m['core_ridge_minus_simple']}")
        print(f"[full - core] {m['full_ridge_minus_core']}")
        import json

        dv = json.loads(
            Path(payload["artifacts"]["data_validity_json"]).read_text(encoding="utf-8")
        )
        q_boundaries = dv["walk_forward_coverage"]["quartile_boundaries"]
        print(f"[coverage_quartile_boundaries] {q_boundaries}")
        print(
            "[quartile_counts] "
            + ", ".join(
                f"{q['quartile']}={q['prediction_count']}"
                for q in payload["coverage_quartile_metrics"]
            )
        )
    if ev["excluded_reason_counts"]:
        print(f"[excluded_reasons] {ev['excluded_reason_counts']}")
    print(f"[artifact] data_validity={args.data_validity_path}")
    print(f"[artifact] predictions={args.predictions_path}")
    print(f"[artifact] summary={args.summary_path}")
    return 0 if payload["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
