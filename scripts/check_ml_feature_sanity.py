"""ML Feature Sanity Check CLI (POC2 2026-06-08).

지시문 §4.1 / §4.2 — etf_ml_feature_daily / market_risk_feature_daily 의 계산
정합성 / 데이터 품질을 검산하고 JSON snapshot 으로 저장. ML 모델 학습 X,
threshold 확정 X, 매수·매도 판단 X, 외부 source 호출 X.

사용 예:
    # 기본 (운영 SQLite + 10 sample ticker)
    python scripts/check_ml_feature_sanity.py

    # sample 수 / DB 경로 명시
    python scripts/check_ml_feature_sanity.py --sample-count 20 --db state/market/market_data.sqlite

결과:
- state/ml/ml_feature_sanity_latest.json 저장 (gitignored 운영 artifact).
- stdout 으로 sanity_status / warning / error 수 요약 출력.

종료 코드:
- 0: sanity_status = ok 또는 warn
- 1: sanity_status = error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api_ml_sanity import SANITY_SNAPSHOT_PATH  # noqa: E402
from app.market_data_store import DEFAULT_DB_PATH  # noqa: E402
from app.ml_feature_sanity import (  # noqa: E402
    DEFAULT_SAMPLE_TICKER_COUNT,
    build_sanity_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"SQLite DB 경로 (default {DEFAULT_DB_PATH}).",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=DEFAULT_SAMPLE_TICKER_COUNT,
        help=f"검산용 sample ticker 수 (default {DEFAULT_SAMPLE_TICKER_COUNT}).",
    )
    parser.add_argument(
        "--no-snapshot",
        action="store_true",
        help="JSON snapshot 저장 생략 (stdout 출력만).",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    print(
        f"[START] check_ml_feature_sanity db={db_path} sample_count={args.sample_count}"
    )

    report = build_sanity_report(db_path=db_path, sample_count=args.sample_count)
    cov = report.coverage_checks
    calc = report.calculation_checks
    nav = report.nav_join_checks
    risk = report.risk_proxy_checks

    print(
        f"[END]   sanity_status={report.sanity_status} "
        f"etf_rows={report.etf_feature_row_count} "
        f"market_rows={report.market_risk_row_count} "
        f"asof_range={cov['feature_asof_start']}→{cov['feature_asof_end']} "
        f"trading_days={cov['trading_days']}"
    )
    print(
        f"        checked_tickers={calc['checked_ticker_count']} "
        f"calc warn={len(calc['warnings'])} err={len(calc['errors'])} "
        f"nav future_join={nav['future_nav_join_count']} "
        f"nav unavailable_ratio={nav['unavailable_ratio']}"
    )
    print(
        f"        risk all_null_asof={risk['all_null_asof_count']} "
        f"risk warn={len(risk['warnings'])}"
    )
    print(f"        total warnings={len(report.warnings)} errors={len(report.errors)}")

    if not args.no_snapshot:
        SANITY_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with SANITY_SNAPSHOT_PATH.open("w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2, default=str)
        print(f"[WROTE] {SANITY_SNAPSHOT_PATH}")

    return 0 if report.sanity_status != "error" else 1


if __name__ == "__main__":
    sys.exit(main())
