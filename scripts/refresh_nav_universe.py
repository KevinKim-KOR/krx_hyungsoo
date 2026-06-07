"""Naver ETF Universe NAV / 괴리율 수동 refresh CLI (2026-06-08).

지시문 §5.4 — 수동 실행 script 패턴. 운영 API / 정기 job 에 연결되지 않는다.

용도:
- 진단 / 디버그: market refresh hook 없이 단독으로 NAV universe 호출 결과 확인.
- 1회성 asof 강제 백필 (검증자 / 운영자가 명시 호출).

사용 예:
    python scripts/refresh_nav_universe.py
    python scripts/refresh_nav_universe.py --asof 2026-06-05
    python scripts/refresh_nav_universe.py --asof 2026-06-05 --force

기본 asof:
    SQLite market_refresh_log 최신 성공 row 의 asof — (a) 결정에 따른 1순위.
    log 가 비어있으면 KST 오늘 날짜.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.etf_nav_service import refresh_nav_universe  # noqa: E402
from app.market_refresh_service import (  # noqa: E402
    NAV_REFRESH_SUMMARY_PATH,
    _write_nav_refresh_summary,
)
from app.market_data_store import DEFAULT_DB_PATH  # noqa: E402

KST = ZoneInfo("Asia/Seoul")


def _resolve_asof_from_log(db_path: Path) -> str | None:
    """market_refresh_log 최신 성공 row 의 asof 를 반환. 없으면 None."""
    if not db_path.exists():
        return None
    try:
        with sqlite3.connect(str(db_path)) as con:
            cur = con.execute(
                "SELECT asof FROM market_refresh_log "
                "WHERE success > 0 ORDER BY created_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            return row[0] if row else None
    except Exception:  # noqa: BLE001
        return None


def _kst_today_iso() -> str:
    return datetime.now(KST).date().isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--asof",
        help="기준일 (YYYY-MM-DD). 미지정 시 market_refresh_log 최신 → KST 오늘.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="TTL 캐시 무시하고 외부 호출 강제.",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"SQLite DB 경로 (기본 {DEFAULT_DB_PATH}).",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="JSON summary artifact 작성 생략 (stdout 출력만).",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    asof = args.asof or _resolve_asof_from_log(db_path) or _kst_today_iso()

    print(f"[START] refresh_nav_universe asof={asof} force={args.force}")
    print(f"        db_path={db_path}")
    summary = refresh_nav_universe(asof=asof, force=args.force, db_path=db_path)

    print(f"[END]   status={summary.status} total={summary.total_count}")
    print(
        f"        success={summary.success_count} "
        f"unavailable={summary.unavailable_count} "
        f"cache_hit={summary.cache_hit} stale={summary.stale_cache_used}"
    )
    print(
        f"        elapsed={summary.elapsed_seconds}s upserted={summary.upserted_count}"
    )
    if summary.sample_tickers:
        print(f"        sample={summary.sample_tickers}")

    if not args.no_summary:
        _write_nav_refresh_summary(summary)
        print(f"[WROTE] {NAV_REFRESH_SUMMARY_PATH}")

    # 종료 코드: status 가 unavailable 이면 1, 그 외 0.
    return 0 if summary.status != "unavailable" else 1


if __name__ == "__main__":
    sys.exit(main())
