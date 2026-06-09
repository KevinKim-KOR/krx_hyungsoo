"""ML 최소 데이터 레인 — feature 생성 CLI (POC2 2026-06-08).

지시문 §4 — CLI / batch 전용. 화면 조회 / refresh 흐름에 hook 0건.

사용 예:
    # 기본 60거래일 backfill
    python scripts/generate_ml_features.py

    # 명시 구간
    python scripts/generate_ml_features.py --start-date 2026-03-01 --end-date 2026-06-08

    # 디버그용 ticker filter (소수)
    python scripts/generate_ml_features.py --ticker 069500 --ticker 360750

결과:
- SQLite etf_ml_feature_daily / market_risk_feature_daily upsert.
- state/ml/ml_feature_snapshot_latest.json snapshot 생성 (지시문 §6.5).

본 script 는 ML 모델 학습 / 라벨 / 예측 / 매수·매도 판단 X. feature row 만 적재.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.market_data_store import DEFAULT_DB_PATH  # noqa: E402
from app.ml_feature_builder import build_features  # noqa: E402
from app.ml_feature_store import (  # noqa: E402
    upsert_etf_features,
    upsert_market_risk_features,
)

SNAPSHOT_PATH = Path("state/ml/ml_feature_snapshot_latest.json")
DEFAULT_LOOKBACK_DAYS = 60


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-date",
        default=None,
        help="시작 asof (YYYY-MM-DD). 미지정 시 --end-date 기준 lookback 거래일 전.",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="종료 asof (YYYY-MM-DD). 미지정 시 SQLite 의 가장 최근 KODEX200 거래일.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help=f"--start-date 미지정 시 기본 lookback 거래일 (default {DEFAULT_LOOKBACK_DAYS}).",
    )
    parser.add_argument(
        "--ticker",
        action="append",
        default=None,
        help="대상 ticker (반복 가능, 디버그용). 미지정 시 universe 전체.",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"SQLite DB 경로 (default {DEFAULT_DB_PATH}).",
    )
    parser.add_argument(
        "--no-snapshot",
        action="store_true",
        help="JSON snapshot 생성 생략.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    started_at = _utcnow_iso()
    t0 = time.perf_counter()

    print(
        f"[START] generate_ml_features db={db_path} "
        f"start={args.start_date or '(auto)'} end={args.end_date or '(auto)'} "
        f"lookback={args.lookback_days}"
    )
    result = build_features(
        db_path=db_path,
        start_date=args.start_date,
        end_date=args.end_date,
        default_lookback_days=args.lookback_days,
        universe_filter=args.ticker,
    )

    etf_upserted = upsert_etf_features(result.etf_rows, db_path=db_path)
    mkt_upserted = upsert_market_risk_features(result.market_rows, db_path=db_path)
    elapsed = time.perf_counter() - t0
    finished_at = _utcnow_iso()

    asofs = result.asofs
    last_asof = asofs[-1] if asofs else None

    print(
        f"[END]   etf_rows={etf_upserted}  market_rows={mkt_upserted}  "
        f"asofs={len(asofs)}  elapsed={elapsed:.2f}s  last_asof={last_asof}"
    )
    print(f"        missing_data_summary={result.missing_data_summary}")

    if not args.no_snapshot:
        snap = {
            "asof": last_asof,
            "etf_feature_count": etf_upserted,
            "market_risk_feature_count": mkt_upserted,
            "asof_count": len(asofs),
            "etf_universe_count": result.missing_data_summary.get("etf_universe_count"),
            "etf_series_missing": result.missing_data_summary.get("etf_series_missing"),
            "asof_without_kospi": result.missing_data_summary.get("asof_without_kospi"),
            "nav_join_status": (
                "ok"
                if any(r.nav_status == "ok" for r in result.etf_rows)
                else "all_unavailable_or_missing"
            ),
            "market_risk_feature_status": ("ok" if result.market_rows else "empty"),
            "generated_at": finished_at,
            "started_at": started_at,
            "elapsed_seconds": round(elapsed, 3),
            "lookback_days_default": args.lookback_days,
            "start_date_arg": args.start_date,
            "end_date_arg": args.end_date,
            "ticker_filter_used": bool(args.ticker),
            "missing_data_summary": result.missing_data_summary,
            "sample_items": [asdict(r) for r in result.etf_rows[-5:]],
        }
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with SNAPSHOT_PATH.open("w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2, default=str)
        print(f"[WROTE] {SNAPSHOT_PATH}")

    return 0 if etf_upserted > 0 or mkt_upserted > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
