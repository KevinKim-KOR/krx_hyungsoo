"""ML Baseline v0 룩백 검증 CLI (POC2 2026-06-11).

지시문 §4 — CLI 또는 batch 만. 화면 진입 / Data Status / Market Discovery /
GenerateDraft / Telegram / market refresh 와 분리.

사용법:
    python scripts/run_ml_baseline_v0.py
    python scripts/run_ml_baseline_v0.py --db state/market/market_data.sqlite
    python scripts/run_ml_baseline_v0.py --no-snapshot
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api_ml_baseline import BASELINE_REPORT_PATH  # noqa: E402
from app.market_data_store import DEFAULT_DB_PATH  # noqa: E402
from app.market_regime import KODEX200_TICKER  # noqa: E402
from app.ml_baseline_v0 import build_baseline_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="ML Baseline v0 룩백 검증 (CLI 전용).",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"SQLite path (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--kodex-ticker",
        default=KODEX200_TICKER,
        help="benchmark ticker (default: KODEX200).",
    )
    parser.add_argument(
        "--no-snapshot",
        action="store_true",
        help="state/ml/ml_baseline_v0_report_latest.json 저장 생략.",
    )
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    print(f"[START] run_ml_baseline_v0 db={db_path} kodex={args.kodex_ticker}")

    report = build_baseline_report(db_path=db_path, kodex_ticker=args.kodex_ticker)

    cand = report.candidate_baseline
    risk = report.risk_baseline
    leak = report.leakage_checks
    print(
        f"[END]   status={report.status} "
        f"feature_asof={report.feature_asof_range.get('start')}→"
        f"{report.feature_asof_range.get('end')} "
        f"trading_days={report.feature_asof_range.get('trading_days')} "
        f"evaluated_days={report.evaluated_asof_range.get('evaluated_days')}"
    )
    print(
        f"        candidate.status={cand.get('status')} "
        f"days={cand.get('evaluated_days')} "
        f"tickers={cand.get('evaluated_ticker_count')} "
        f"top_quantile={cand.get('top_group_quantile')}"
    )
    print(f"        risk.status={risk.get('status')} days={risk.get('evaluated_days')}")
    print(
        f"        leakage.future_data_detected="
        f"{leak.get('feature_future_data_leakage_detected')} "
        f"tail_excluded={leak.get('target_horizon_short_tail_excluded')} "
        f"time_order={leak.get('time_order_preserved')}"
    )
    print(f"        warnings={len(report.warnings)} errors={len(report.errors)}")

    if not args.no_snapshot:
        BASELINE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with BASELINE_REPORT_PATH.open("w", encoding="utf-8") as f:
            json.dump(asdict(report), f, ensure_ascii=False, indent=2, default=str)
        print(f"[WROTE] {BASELINE_REPORT_PATH}")

    # exit code: error → 1, 그 외 0.
    return 1 if report.status == "error" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
