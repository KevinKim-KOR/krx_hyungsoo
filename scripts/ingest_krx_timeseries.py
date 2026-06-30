"""KRX 데이터마켓 자료 → SQLite 적재 CLI (2026-06-30 시장 시계열 보강 STEP).

본 스크립트는 PC 에서 사용자가 명시적으로 실행한다.
외부 네트워크 호출 / 자격증명 / KRX 자동 다운로드 기능을 포함하지 않는다.

사용 흐름:
1. 사용자가 KRX 데이터마켓 (https://data.krx.co.kr) 에서 ETF·KOSPI 일별
   시세 CSV / ZIP 을 PC 에 다운로드.
2. 본 CLI 가 CSV 를 읽어 컬럼을 정규화 후 SQLite 에 점진 적재.
3. 종목별 적재 상태는 `market_timeseries_ingestion_state` 에 기록.

지원하는 CSV 컬럼 매핑 (대소문자 / 한글 / 영문 모두 허용. 실측 데이터로 확장):
- ticker  : `종목코드 / Symbol / ticker / ISU_SRT_CD`
- date    : `일자 / 기준일 / TRD_DD / date`  (YYYY-MM-DD 또는 YYYYMMDD)
- close   : `종가 / TDD_CLSPRC / Close / close`
- (선택)  price_basis 컬럼 — 사용자가 자료에 명시된 가격 기준 (조정/원시) 을
           --price-basis 인자로 전달. 자동 추정 금지.

재개·중복 방지:
- 이미 status=normal 로 적재된 종목은 기본적으로 skip (--force 로 재적재).
- 동일 (ticker, date) 는 ON CONFLICT 로 흡수.

사용 예:
    python -m scripts.ingest_krx_timeseries benchmark \\
        --csv data/krx/kodex200_2010_2026.csv \\
        --benchmark-id 069500 --benchmark-name "KODEX 200" \\
        --price-basis raw_close

    python -m scripts.ingest_krx_timeseries etf \\
        --csv data/krx/etf_universe_daily.csv \\
        --price-basis raw_close

    python -m scripts.ingest_krx_timeseries status
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

# sys.path 보정 - `python scripts/...` 직접 실행 호환.
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# FIX r2 (Windows 콘솔 안전):
# Windows 기본 콘솔 코드페이지 (cp949 등) 에서 em dash / 화살표 같은 비ASCII
# 문자를 출력하면 UnicodeEncodeError 로 종료된다. CLI 출력 메시지는 ASCII
# 만 사용하고, 추가로 stdout/stderr 를 가능하면 UTF-8 로 reconfigure 한다.
# Python 3.7+ TextIOWrapper.reconfigure 사용. 실패 (예: redirect 된 file) 시
# 무시 — 본 CLI 의 메시지는 이미 ASCII 라 안전.
def _reconfigure_stdio_to_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - best-effort, never crash CLI
            pass


_reconfigure_stdio_to_utf8()

from app.market_data_store import (  # noqa: E402
    DEFAULT_DB_PATH,
    fetch_price_history,
    list_etf_tickers,
)
from app.market_timeseries_ingestion_service import (  # noqa: E402
    BENCHMARK_KODEX200_TICKER,
    IngestionInput,
    ingest_benchmark_timeseries,
    ingest_etf_timeseries,
)
from app.market_timeseries_ingestion_store import (  # noqa: E402
    STATUS_NORMAL,
    count_by_status,
    list_pending_tickers,
    list_states,
    read_state,
)

_TICKER_KEYS = ("종목코드", "Symbol", "ticker", "ISU_SRT_CD", "SHRT_CD", "Ticker")
_DATE_KEYS = ("일자", "기준일", "TRD_DD", "date", "Date", "DATE")
_CLOSE_KEYS = ("종가", "TDD_CLSPRC", "Close", "close", "CLOSE")


@dataclass
class _Args:
    command: str
    csv_path: Optional[Path]
    benchmark_id: Optional[str]
    benchmark_name: Optional[str]
    price_basis: Optional[str]
    source: str
    db_path: Path
    force: bool
    ticker: Optional[str]


def _parse_args(argv: Optional[list[str]] = None) -> _Args:
    p = argparse.ArgumentParser(
        prog="ingest_krx_timeseries",
        description="Ingest KRX data-market CSV into SQLite (incremental).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_bench = sub.add_parser("benchmark", help="Ingest benchmark timeseries.")
    p_bench.add_argument("--csv", type=Path, required=True)
    p_bench.add_argument("--benchmark-id", required=True)
    p_bench.add_argument("--benchmark-name", required=True)
    p_bench.add_argument("--price-basis", required=True)
    p_bench.add_argument("--source", default="KRX_DATA_MARKET")
    p_bench.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)

    p_etf = sub.add_parser(
        "etf",
        help="Ingest ETF universe timeseries (resumable, no duplicates).",
    )
    p_etf.add_argument("--csv", type=Path, required=True)
    p_etf.add_argument("--price-basis", required=True)
    p_etf.add_argument("--source", default="KRX_DATA_MARKET")
    p_etf.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    p_etf.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest even tickers already marked normal (default: skip).",
    )
    p_etf.add_argument(
        "--ticker",
        help="Ingest a single ticker only (source verification).",
    )

    p_stat = sub.add_parser("status", help="Print ingestion status summary.")
    p_stat.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)

    a = p.parse_args(argv)
    return _Args(
        command=a.command,
        csv_path=getattr(a, "csv", None),
        benchmark_id=getattr(a, "benchmark_id", None),
        benchmark_name=getattr(a, "benchmark_name", None),
        price_basis=getattr(a, "price_basis", None),
        source=getattr(a, "source", "KRX_DATA_MARKET"),
        db_path=a.db_path,
        force=getattr(a, "force", False),
        ticker=getattr(a, "ticker", None),
    )


def _pick(row: dict[str, str], keys: Iterable[str]) -> Optional[str]:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


def _normalize_date(s: str) -> Optional[str]:
    s = s.strip()
    if not s:
        return None
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return s
    # Allow YYYY/MM/DD
    if len(s) == 10 and s[4] == "/" and s[7] == "/":
        return s.replace("/", "-")
    return None


def _parse_close(s: str) -> Optional[float]:
    s = s.replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _read_csv_rows(
    csv_path: Path,
) -> dict[str, list[tuple[str, Optional[float]]]]:
    """CSV → ticker → [(date_iso, close), ...]."""
    out: dict[str, list[tuple[str, Optional[float]]]] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            tk_raw = _pick(raw, _TICKER_KEYS)
            dt_raw = _pick(raw, _DATE_KEYS)
            cl_raw = _pick(raw, _CLOSE_KEYS)
            if not tk_raw or not dt_raw or cl_raw is None:
                continue
            tk = (
                str(tk_raw).strip().zfill(6)
                if str(tk_raw).strip().isdigit()
                else str(tk_raw).strip()
            )
            dt = _normalize_date(str(dt_raw))
            if dt is None:
                continue
            close = _parse_close(str(cl_raw))
            out.setdefault(tk, []).append((dt, close))
    return out


def _kodex200_calendar(db_path: Path) -> list[str]:
    series = fetch_price_history(BENCHMARK_KODEX200_TICKER, db_path=db_path)
    return [dt for dt, _ in series]


def _cmd_benchmark(args: _Args) -> int:
    parsed = _read_csv_rows(args.csv_path)
    if args.benchmark_id not in parsed:
        print(
            f"[benchmark] CSV does not contain benchmark_id={args.benchmark_id}.",
            file=sys.stderr,
        )
        return 2
    rows = parsed[args.benchmark_id]
    result = ingest_benchmark_timeseries(
        benchmark_id=args.benchmark_id,
        benchmark_name=args.benchmark_name or args.benchmark_id,
        rows=rows,
        source=args.source,
        price_basis=args.price_basis,
        db_path=args.db_path,
    )
    print(
        f"[benchmark] ticker={result.ticker} status={result.status} "
        f"rows={result.rows_written} start={result.series_start_date} "
        f"end={result.series_end_date} observed={result.observed_trading_day_count}"
    )
    return 0


def _cmd_etf(args: _Args) -> int:
    parsed = _read_csv_rows(args.csv_path)
    if not parsed:
        print("[etf] CSV has no ingestable rows.", file=sys.stderr)
        return 2
    benchmark_calendar = _kodex200_calendar(args.db_path)

    # 적재 대상 universe 는 **기존 SQLite etf_master** 가 기준 (지시문 §7).
    # CSV 는 가격 입력 자료일 뿐이며 universe 변경 권한이 없다.
    # FIX r2 — universe 가드는 --ticker 경로에서도 동일하게 적용:
    #   etf_master 가 비어 있으면 --ticker 여부 무관하게 거부.
    sqlite_universe = list_etf_tickers(db_path=args.db_path)
    if not sqlite_universe:
        print(
            "[etf] SQLite etf_master is empty. Run universe refresh first "
            "(POST /market/refresh).",
            file=sys.stderr,
        )
        return 2
    if args.ticker:
        if args.ticker not in sqlite_universe:
            print(
                f"[etf] {args.ticker}: not in SQLite etf_master -- skip.",
                file=sys.stderr,
            )
            return 2
        tickers = [args.ticker]
    else:
        if args.force:
            tickers = sqlite_universe
        else:
            tickers = list_pending_tickers(
                universe_tickers=sqlite_universe, db_path=args.db_path
            )
        csv_only = sorted(set(parsed.keys()) - set(sqlite_universe))
        if csv_only:
            print(
                f"[etf] CSV contains {len(csv_only)} tickers not in SQLite universe -- skip "
                f"(e.g. {','.join(csv_only[:5])})"
            )

    ok = 0
    skipped = 0
    for tk in tickers:
        rows = parsed.get(tk)
        if rows is None:
            print(f"[etf] {tk}: source_missing (not in CSV)")
            ingest_etf_timeseries(
                IngestionInput(
                    ticker=tk,
                    rows=[],
                    source=args.source,
                    price_basis=args.price_basis,
                    source_missing=True,
                ),
                benchmark_calendar=benchmark_calendar,
                db_path=args.db_path,
            )
            continue
        prior = read_state(tk, db_path=args.db_path)
        if (
            prior is not None
            and prior.ingestion_status == STATUS_NORMAL
            and not args.force
        ):
            skipped += 1
            continue
        result = ingest_etf_timeseries(
            IngestionInput(
                ticker=tk,
                rows=rows,
                source=args.source,
                price_basis=args.price_basis,
            ),
            benchmark_calendar=benchmark_calendar,
            db_path=args.db_path,
        )
        ok += 1
        print(
            f"[etf] {result.ticker} status={result.status} rows={result.rows_written} "
            f"start={result.series_start_date} end={result.series_end_date} "
            f"observed={result.observed_trading_day_count} "
            f"missing={result.post_listing_missing_count}"
        )
    print(f"[etf] done -- written={ok} skipped(normal)={skipped}")
    return 0


def _cmd_status(args: _Args) -> int:
    counts = count_by_status(db_path=args.db_path)
    print("[status] ingestion_status counts:")
    for status, n in counts.items():
        print(f"  {status}: {n}")
    states = list_states(db_path=args.db_path)
    print(f"[status] total tracked tickers: {len(states)}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    if args.command == "benchmark":
        return _cmd_benchmark(args)
    if args.command == "etf":
        return _cmd_etf(args)
    if args.command == "status":
        return _cmd_status(args)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
