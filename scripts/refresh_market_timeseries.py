"""CLI: refresh_market_timeseries (2026-06-30 Closeout).

Naver/FDR primary + Yahoo/FDR secondary 를 사용해 ETF·KODEX200 일별 종가를
기존 SQLite (`etf_daily_price` / `market_timeseries_ingestion_state` /
`market_timeseries_refresh_state`) 로 적재한다.

서브커맨드:
- benchmark   KODEX200(069500) 먼저 최신화. benchmark_asof_date 확정.
- initial     초기 적재 필요 종목만 처리. --max-tickers <N> | --all 필수.
- incremental 정상 종목의 last date+1 ~ benchmark_asof_date 구간만 요청.
- status      최신 상태 요약 출력.

출력은 ASCII 만 사용 (Windows cp949 안전).
UI/브라우저 요청과 무관 — PC CLI 로만 실행.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _reconfigure_stdio_to_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
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
    read_state,
)
from app.market_timeseries_naver_yahoo_adapter import (  # noqa: E402
    PRICE_BASIS,
    fetch_ticker_prices,
)
from app.market_timeseries_refresh_state_store import (  # noqa: E402
    STATUS_FAILED,
    STATUS_OK,
    STATUS_RUNNING,
    TimeseriesRefreshStateRow,
    normalize_running_to_failed,
    read_state as read_refresh_state,
    write_state as write_refresh_state,
)

REQUESTED_START_DATE = date(2014, 4, 7)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class _Args:
    command: str
    db_path: Path
    max_tickers: Optional[int]
    all_flag: bool
    retry_pending: bool
    start_date: date


def _parse_args(argv: Optional[list[str]] = None) -> _Args:
    p = argparse.ArgumentParser(
        prog="refresh_market_timeseries",
        description="Refresh KODEX200 / ETF daily prices via Naver/FDR + Yahoo fallback.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def _add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
        sp.add_argument(
            "--start-date",
            default=REQUESTED_START_DATE.isoformat(),
            help="Requested series start date (default 2014-04-07).",
        )

    sp_b = sub.add_parser("benchmark", help="Refresh KODEX200 first.")
    _add_common(sp_b)

    sp_i = sub.add_parser("initial", help="Initial ingestion for pending tickers.")
    _add_common(sp_i)
    g = sp_i.add_mutually_exclusive_group(required=True)
    g.add_argument("--max-tickers", type=int)
    g.add_argument("--all", dest="all_flag", action="store_true")

    sp_inc = sub.add_parser(
        "incremental", help="Incremental refresh for normal tickers."
    )
    _add_common(sp_inc)
    sp_inc.add_argument(
        "--retry-pending",
        action="store_true",
        help="Also re-process partial / missing_confirm / failed / source_missing.",
    )

    sp_s = sub.add_parser("status", help="Print refresh + ingestion status summary.")
    sp_s.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)

    # 2026-07-03 Market Risk Reference v1 — VIX 독립 CLI (지시문 §5 / §5.1).
    sp_v = sub.add_parser(
        "vix",
        help="Ingest VIX daily close via FDR. Independent from benchmark/etf.",
    )
    _add_common(sp_v)

    # 2026-07-05 Market Flow ML Baseline v1 Closeout — KOSPI 역사 보강 독립 CLI.
    # 일반 운영 최신화 아님. benchmark/initial/incremental/vix 책임 변경 없음.
    sp_k = sub.add_parser(
        "kospi",
        help="KOSPI history closeout (NAVER primary / YAHOO secondary). One-shot.",
    )
    sp_k.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)

    a = p.parse_args(argv)
    start_date = REQUESTED_START_DATE
    if hasattr(a, "start_date") and a.start_date:
        try:
            start_date = date.fromisoformat(a.start_date)
        except ValueError:
            print(
                f"[cli] invalid --start-date {a.start_date}",
                file=sys.stderr,
            )
            raise SystemExit(2)
    return _Args(
        command=a.command,
        db_path=a.db_path,
        max_tickers=getattr(a, "max_tickers", None),
        all_flag=getattr(a, "all_flag", False),
        retry_pending=getattr(a, "retry_pending", False),
        start_date=start_date,
    )


def _mark_running(db_path: Path, target_asof: date) -> None:
    prior = read_refresh_state(db_path=db_path)
    row = TimeseriesRefreshStateRow(
        target_asof_date=target_asof.isoformat(),
        benchmark_asof_date=prior.benchmark_asof_date if prior else None,
        last_attempt_started_at=_utcnow_iso(),
        last_attempt_finished_at=None,
        last_attempt_status=STATUS_RUNNING,
        last_success_at=prior.last_success_at if prior else None,
        eligible_ticker_count=prior.eligible_ticker_count if prior else 0,
        excluded_ticker_count=prior.excluded_ticker_count if prior else 0,
        error_summary=None,
    )
    write_refresh_state(row, db_path=db_path)


def _mark_finished(
    db_path: Path,
    *,
    status: str,
    benchmark_asof: Optional[str],
    eligible: int,
    excluded: int,
    error: Optional[str] = None,
) -> None:
    prior = read_refresh_state(db_path=db_path)
    now = _utcnow_iso()
    last_success_at = prior.last_success_at if prior else None
    if status == STATUS_OK:
        last_success_at = now
    row = TimeseriesRefreshStateRow(
        target_asof_date=prior.target_asof_date if prior else None,
        benchmark_asof_date=(
            benchmark_asof
            if benchmark_asof
            else (prior.benchmark_asof_date if prior else None)
        ),
        last_attempt_started_at=prior.last_attempt_started_at if prior else now,
        last_attempt_finished_at=now,
        last_attempt_status=status,
        last_success_at=last_success_at,
        eligible_ticker_count=eligible,
        excluded_ticker_count=excluded,
        error_summary=error,
    )
    write_refresh_state(row, db_path=db_path)


# ---------- benchmark ----------


def _cmd_benchmark(args: _Args) -> int:
    normalize_running_to_failed(db_path=args.db_path)
    target = date.today()
    _mark_running(args.db_path, target)

    result = fetch_ticker_prices(
        BENCHMARK_KODEX200_TICKER,
        start=args.start_date,
        end=target,
    )
    if not result.rows:
        _mark_finished(
            args.db_path,
            status=STATUS_FAILED,
            benchmark_asof=None,
            eligible=0,
            excluded=0,
            error=f"benchmark_fetch_failed: {result.error}",
        )
        print(
            f"[benchmark] failed to fetch KODEX200: {result.error}",
            file=sys.stderr,
        )
        return 2

    ing = ingest_benchmark_timeseries(
        benchmark_id=BENCHMARK_KODEX200_TICKER,
        benchmark_name="KODEX 200",
        rows=result.rows,
        source=result.source,
        price_basis=PRICE_BASIS,
        db_path=args.db_path,
    )
    benchmark_asof = ing.series_end_date
    if ing.status != STATUS_NORMAL:
        _mark_finished(
            args.db_path,
            status=STATUS_FAILED,
            benchmark_asof=benchmark_asof,
            eligible=0,
            excluded=0,
            error=f"benchmark_ingest_status={ing.status}: {ing.error_summary}",
        )
        print(
            f"[benchmark] ingest status={ing.status} error={ing.error_summary}",
            file=sys.stderr,
        )
        return 2

    _mark_finished(
        args.db_path,
        status=STATUS_OK,
        benchmark_asof=benchmark_asof,
        eligible=1,
        excluded=0,
    )
    print(
        f"[benchmark] source={result.source} rows={ing.rows_written} "
        f"start={ing.series_start_date} asof={benchmark_asof}"
    )
    return 0


# ---------- initial / incremental ----------


def _resolve_benchmark_calendar(db_path: Path) -> list[str]:
    return [
        dt for dt, _ in fetch_price_history(BENCHMARK_KODEX200_TICKER, db_path=db_path)
    ]


def _pending_tickers_for_initial(
    universe: list[str],
    db_path: Path,
) -> list[str]:
    """initial: 상태 행이 없거나 status != normal 인 ticker."""
    out: list[str] = []
    for tk in universe:
        state = read_state(tk, db_path=db_path)
        if state is None or state.ingestion_status != STATUS_NORMAL:
            out.append(tk)
    return out


def _incremental_start_for(ticker: str, db_path: Path, fallback: date) -> date:
    state = read_state(ticker, db_path=db_path)
    if state and state.confirmed_series_end_date:
        try:
            end_prev = date.fromisoformat(state.confirmed_series_end_date)
            # 다음 거래일부터 요청 — end_prev + 1 일.
            from datetime import timedelta

            return end_prev + timedelta(days=1)
        except ValueError:
            pass
    return fallback


def _run_universe_ingest(
    args: _Args,
    *,
    tickers: list[str],
    incremental_from_last: bool,
) -> tuple[int, int, dict[str, int]]:
    """returns (eligible, excluded, counts_by_status)."""
    benchmark_calendar = _resolve_benchmark_calendar(args.db_path)
    if not benchmark_calendar:
        raise RuntimeError("KODEX200 benchmark not ingested. Run `benchmark` first.")
    target = date.today()
    eligible = 0
    excluded = 0
    for tk in tickers:
        start = (
            _incremental_start_for(tk, args.db_path, args.start_date)
            if incremental_from_last
            else args.start_date
        )
        if start > target:
            # 이미 최신 — 요청 불필요.
            eligible += 1
            continue
        adapter_result = fetch_ticker_prices(tk, start=start, end=target)
        if not adapter_result.rows:
            ingest_etf_timeseries(
                IngestionInput(
                    ticker=tk,
                    rows=[],
                    source=adapter_result.source,
                    price_basis=PRICE_BASIS,
                    source_missing=True,
                ),
                benchmark_calendar=benchmark_calendar,
                db_path=args.db_path,
            )
            excluded += 1
            print(
                f"[etf] {tk} source_missing error={adapter_result.error}",
                file=sys.stderr,
            )
            continue
        ing = ingest_etf_timeseries(
            IngestionInput(
                ticker=tk,
                rows=adapter_result.rows,
                source=adapter_result.source,
                price_basis=PRICE_BASIS,
            ),
            benchmark_calendar=benchmark_calendar,
            db_path=args.db_path,
        )
        if ing.status == STATUS_NORMAL:
            eligible += 1
        else:
            excluded += 1
        print(
            f"[etf] {tk} source={adapter_result.source} status={ing.status} "
            f"rows={ing.rows_written} start={ing.series_start_date} "
            f"end={ing.series_end_date} missing={ing.post_listing_missing_count}"
        )
    counts = count_by_status(db_path=args.db_path)
    return eligible, excluded, counts


def _cmd_initial(args: _Args) -> int:
    normalize_running_to_failed(db_path=args.db_path)
    universe = list_etf_tickers(db_path=args.db_path)
    if not universe:
        print(
            "[initial] SQLite etf_master is empty. Run universe refresh first "
            "(POST /market/refresh).",
            file=sys.stderr,
        )
        return 2
    prior_bm = read_refresh_state(db_path=args.db_path)
    if prior_bm is None or not prior_bm.benchmark_asof_date:
        print(
            "[initial] benchmark_asof_date not set. Run `benchmark` first.",
            file=sys.stderr,
        )
        return 2

    pending = _pending_tickers_for_initial(universe, args.db_path)
    if args.all_flag:
        tickers = pending
    else:
        n = args.max_tickers or 0
        tickers = pending[:n]
    if not tickers:
        print("[initial] no pending tickers.")
        _mark_finished(
            args.db_path,
            status=STATUS_OK,
            benchmark_asof=prior_bm.benchmark_asof_date,
            eligible=len(universe),
            excluded=0,
        )
        return 0

    _mark_running(args.db_path, date.today())
    try:
        eligible, excluded, _counts = _run_universe_ingest(
            args, tickers=tickers, incremental_from_last=False
        )
    except RuntimeError as e:
        _mark_finished(
            args.db_path,
            status=STATUS_FAILED,
            benchmark_asof=prior_bm.benchmark_asof_date,
            eligible=0,
            excluded=0,
            error=str(e),
        )
        print(f"[initial] {e}", file=sys.stderr)
        return 2
    _mark_finished(
        args.db_path,
        status=STATUS_OK,
        benchmark_asof=prior_bm.benchmark_asof_date,
        eligible=eligible,
        excluded=excluded,
    )
    print(f"[initial] done -- eligible={eligible} excluded={excluded}")
    return 0


def _cmd_incremental(args: _Args) -> int:
    normalize_running_to_failed(db_path=args.db_path)
    universe = list_etf_tickers(db_path=args.db_path)
    if not universe:
        print(
            "[incremental] SQLite etf_master is empty.",
            file=sys.stderr,
        )
        return 2
    # 매번 benchmark 를 먼저 최신화.
    rc = _cmd_benchmark(args)
    if rc != 0:
        return rc

    prior = read_refresh_state(db_path=args.db_path)
    benchmark_asof = prior.benchmark_asof_date if prior else None

    if args.retry_pending:
        target_tickers = [
            tk
            for tk in universe
            if (read_state(tk, db_path=args.db_path) or None) is None
            or (read_state(tk, db_path=args.db_path).ingestion_status != STATUS_NORMAL)
        ]
    else:
        target_tickers = [
            tk
            for tk in universe
            if (read_state(tk, db_path=args.db_path) is not None)
            and (read_state(tk, db_path=args.db_path).ingestion_status == STATUS_NORMAL)
        ]

    _mark_running(args.db_path, date.today())
    try:
        eligible, excluded, _counts = _run_universe_ingest(
            args, tickers=target_tickers, incremental_from_last=True
        )
    except RuntimeError as e:
        _mark_finished(
            args.db_path,
            status=STATUS_FAILED,
            benchmark_asof=benchmark_asof,
            eligible=0,
            excluded=0,
            error=str(e),
        )
        print(f"[incremental] {e}", file=sys.stderr)
        return 2
    _mark_finished(
        args.db_path,
        status=STATUS_OK,
        benchmark_asof=benchmark_asof,
        eligible=eligible,
        excluded=excluded,
    )
    print(
        f"[incremental] done -- eligible={eligible} excluded={excluded} "
        f"benchmark_asof={benchmark_asof}"
    )
    return 0


# ---------- vix (2026-07-03 Market Risk Reference v1) ----------


def _cmd_vix(args: _Args) -> int:
    """VIX 서브커맨드 — 실 구현은 scripts/_market_refresh/vix_ingest.py 로 분리.

    Cleanup / FIX r7 Round 2: KS-10 trigger (686줄) 해소를 위한 최소 분리.
    CLI 계약 · 인자 · 출력 · 종료 코드 유지.
    """
    from scripts._market_refresh.vix_ingest import run_vix_ingest

    return run_vix_ingest(args.db_path)


def _cmd_status(args: _Args) -> int:
    normalize_running_to_failed(db_path=args.db_path)
    refresh = read_refresh_state(db_path=args.db_path)
    counts = count_by_status(db_path=args.db_path)
    print("[status] refresh:")
    if refresh is None:
        print("  (no refresh recorded)")
    else:
        print(f"  benchmark_asof_date: {refresh.benchmark_asof_date}")
        print(f"  last_attempt_status: {refresh.last_attempt_status}")
        print(f"  last_success_at:     {refresh.last_success_at}")
        print(f"  eligible_ticker_count: {refresh.eligible_ticker_count}")
        print(f"  excluded_ticker_count: {refresh.excluded_ticker_count}")
        if refresh.error_summary:
            print(f"  error_summary:       {refresh.error_summary}")
    print("[status] ingestion counts:")
    for status, n in counts.items():
        print(f"  {status}: {n}")
    return 0


def _cmd_kospi(args: _Args) -> int:
    """KOSPI 역사 보강 (지시문 §5.2 순서).

    NAVER 우선 → YAHOO 보조. 둘 다 split 충분성 불충족 시 SQLite 미변경.
    """
    from app.kospi_history_closeout import run_kospi_closeout

    result = run_kospi_closeout(db_path=args.db_path)
    print(
        f"[kospi] status={result.status} selected={result.selected_source} "
        f"inserted={result.inserted_row_count}"
    )
    if result.naver.queried:
        print(
            f"[kospi.naver] rows={result.naver.row_count} "
            f"split={result.naver.projected_split_rows}"
        )
    if result.yahoo.queried:
        print(
            f"[kospi.yahoo] rows={result.yahoo.row_count} "
            f"split={result.yahoo.projected_split_rows}"
        )
    if result.unavailable_reason:
        print(f"[kospi] reason={result.unavailable_reason}", file=sys.stderr)
    return 0 if result.status == "ok" else 2


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    if args.command == "benchmark":
        return _cmd_benchmark(args)
    if args.command == "initial":
        return _cmd_initial(args)
    if args.command == "incremental":
        return _cmd_incremental(args)
    if args.command == "status":
        return _cmd_status(args)
    if args.command == "vix":
        return _cmd_vix(args)
    if args.command == "kospi":
        return _cmd_kospi(args)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
