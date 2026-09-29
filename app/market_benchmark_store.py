"""Market benchmark SQLite 저장소 (POC2 — Market Regime & Benchmark Context 1차).

본 모듈은 1개 신규 테이블만 관리한다:
- market_benchmark_daily_price: 시장 대표지수 가격 시계열 (KOSPI 등).

저장 위치는 시장 데이터 DB (`state/market/market_data.sqlite`) 와 동일 파일이다 —
Decision Evidence DB 와는 분리 (지시문 §4.1).

KODEX200 은 ETF 라 기존 etf_daily_price 테이블을 그대로 사용하고, 본 테이블은
KOSPI 같이 ETF 가 아닌 지수만 별도 보관한다. API 응답에서는 둘 다 benchmark
형태로 정규화되어 노출된다 (지시문 §4.3).
"""

from __future__ import annotations

import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from app.market_benchmark_freshness import MAX_STALE_TRADING_DAYS
from app.market_data_store import DEFAULT_DB_PATH
from app.trading_day_lag import benchmark_lag_trading_days

MARKET_BENCHMARK_DAILY_PRICE_DDL = """
CREATE TABLE IF NOT EXISTS market_benchmark_daily_price (
    benchmark_id    TEXT NOT NULL,
    benchmark_name  TEXT NOT NULL,
    date            TEXT NOT NULL,
    close           REAL,
    source          TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    PRIMARY KEY (benchmark_id, date)
);
""".strip()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def init_benchmark_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """benchmark 테이블 보장. market_data_store.init_db 와 동일 DB 파일."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as con:
        con.execute(MARKET_BENCHMARK_DAILY_PRICE_DDL)
        con.commit()


@contextmanager
def _connection(db_path: Path):
    init_benchmark_db(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        yield con
        con.commit()
    finally:
        con.close()


def upsert_benchmark_prices(
    *,
    benchmark_id: str,
    benchmark_name: str,
    rows: Iterable[tuple[str, Optional[float]]],
    source: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """(date, close) 시계열을 (benchmark_id, date) PK 기준 upsert."""
    now = _utcnow_iso()
    payload = [
        (benchmark_id, benchmark_name, dt, close, source, now) for dt, close in rows
    ]
    if not payload:
        return 0
    sql = """
    INSERT INTO market_benchmark_daily_price
        (benchmark_id, benchmark_name, date, close, source, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(benchmark_id, date) DO UPDATE SET
        benchmark_name = excluded.benchmark_name,
        close = excluded.close,
        source = excluded.source,
        created_at = excluded.created_at
    """
    with _connection(db_path) as con:
        con.executemany(sql, payload)
    return len(payload)


def fetch_benchmark_history(
    benchmark_id: str,
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[tuple[str, float]]:
    """(date, close) 시계열 (date ASC). close 가 null/0 이하인 행 제외."""
    with _connection(db_path) as con:
        cur = con.execute(
            "SELECT date, close FROM market_benchmark_daily_price "
            "WHERE benchmark_id = ? AND close IS NOT NULL AND close > 0 "
            "ORDER BY date ASC",
            (benchmark_id,),
        )
        return [(r[0], float(r[1])) for r in cur.fetchall()]


def fetch_existing_benchmark_close_map(
    benchmark_id: str,
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, Optional[float]]:
    """기존 market_benchmark_daily_price 의 (date → close) 매핑.

    2026-06-30 — 시장 시계열 보강 STEP: 신규 적재 전 기존 가격과 충돌 검출용.
    """
    with _connection(db_path) as con:
        cur = con.execute(
            "SELECT date, close FROM market_benchmark_daily_price "
            "WHERE benchmark_id = ?",
            (benchmark_id,),
        )
        return {
            str(row[0]): (float(row[1]) if row[1] is not None else None)
            for row in cur.fetchall()
        }


def latest_benchmark_date(
    benchmark_id: str,
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> Optional[str]:
    with _connection(db_path) as con:
        cur = con.execute(
            "SELECT MAX(date) FROM market_benchmark_daily_price WHERE benchmark_id = ?",
            (benchmark_id,),
        )
        row = cur.fetchone()
        return row[0] if row and row[0] else None


# ─── KOSPI refresh (지수 — ETF 가 아니므로 별도 fetch + upsert) ────────


def _df_to_close_rows(df) -> list[tuple[str, Optional[float]]]:
    """fdr.DataReader DataFrame → (date_iso, close) 리스트."""
    rows: list[tuple[str, Optional[float]]] = []
    if df is None or len(df) == 0:
        return rows
    if "Close" not in df.columns:
        return rows
    for idx, raw in df.iterrows():
        try:
            dt = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        except Exception:  # noqa: BLE001
            continue
        close_raw = raw.get("Close") if hasattr(raw, "get") else raw["Close"]
        try:
            if close_raw is None:
                close = None
            else:
                close = float(close_raw)
                if close != close:  # NaN
                    close = None
        except (TypeError, ValueError):
            close = None
        rows.append((dt, close))
    return rows


def _latest_valid_close_date(rows: list[tuple[str, Optional[float]]]) -> Optional[str]:
    """유효 종가가 있는 행 중 마지막 날짜. 없으면 `None`.

    POC3-02D-OPS-01 C7 · 설계자 Q26(b) — 유효 종가 = 유한한 수 · 0 초과. 반환의
    마지막 날짜를 그대로 쓰면 upstream 이 새 날짜에 종가 없는 행(NaN · None ·
    0 · 음수)을 줄 때 lag 0 · `ok` 로 통과한다. 화면 계층
    (`fetch_benchmark_history`)은 유효 종가 행만 보므로 여전히 멈춘 날짜를 본다.
    """
    valid = [
        dt
        for dt, close in rows
        if close is not None and math.isfinite(close) and close > 0
    ]
    return max(valid) if valid else None


def refresh_kospi_benchmark(
    *,
    end_date,
    lookback_days: int = 180,
    price_fetcher=None,
    db_path: Path = DEFAULT_DB_PATH,
    calendar_dir: Optional[Path] = None,
) -> dict:
    """KOSPI (FDR symbol 'KS11') 시계열 fetch + upsert.

    실패는 모듈 안에서 catch 후 dict 로 결과를 반환한다 (전체 refresh 흐름을
    중단시키지 않기 위해 — 지시문 §4.4 "KOSPI 실패 때문에 전체 Market
    Discovery refresh 를 실패 처리하지 않는다").

    price_fetcher 가 None 이면 lazy import 로 FDR 직접 호출. 테스트는 stub 주입.

    POC3-02D-OPS-01 C7(감지 정정 A · 설계자 Q17) — 반환이 비어 있지 않아도
    `as_of`(아래)가 `MAX_STALE_TRADING_DAYS` 보다 뒤처졌으면(lag 를 못 재는 경우
    포함) `failed` + `source_stale:` 이다. 09-18 부터 upstream 이 멈췄는데 배치는
    매일 `kospi=ok(as_of=2026-09-17)` 였다. **적재한 행은 되돌리지 않는다** —
    upstream 이 재개되면 다음 적재의 lookback 이 빈 날을 채운다.

    `as_of` 는 **유효 종가(유한 · 0 초과)가 있는 마지막 날짜**다(설계자 Q26(b)).
    더 최신 날짜에 NaN · None · 0 · 음수 행이 있어도 신선한 자료로 치지 않는다.
    유효 종가 행이 하나도 없으면 `source_stale:as_of=unknown` 이다. 이때도 행은
    지금처럼 적재하고 되돌리지 않는다.

    calendar_dir 가 None 이면 거래일 snapshot 기본 경로를 쓴다. 테스트는 tmp 주입.
    """
    from datetime import timedelta

    if price_fetcher is None:
        # lazy import — FDR 가 설치되지 않은 환경에서도 모듈 import 자체는 안전.
        from app.market_data_fdr import _default_price_fetcher

        price_fetcher = _default_price_fetcher

    start_date = end_date - timedelta(days=lookback_days)
    try:
        df = price_fetcher("KS11", start_date, end_date)
    except Exception as e:  # noqa: BLE001
        return {
            "status": "failed",
            "error": f"{type(e).__name__}: {e}"[:200],
            "rows_written": 0,
        }
    rows = _df_to_close_rows(df)
    if not rows:
        return {"status": "failed", "error": "no_data", "rows_written": 0}
    try:
        written = upsert_benchmark_prices(
            benchmark_id="KOSPI",
            benchmark_name="KOSPI",
            rows=rows,
            source="FinanceDataReader/KS11",
            db_path=db_path,
        )
    except Exception as e:  # noqa: BLE001
        return {
            "status": "failed",
            "error": f"store: {type(e).__name__}: {e}"[:200],
            "rows_written": 0,
        }
    # 같은 날짜가 두 번 오면 적재(upsert)처럼 **마지막 행**이 남는다 — 판정도
    # 그 행으로 한다. 앞 행의 유효 종가로 신선하다고 보면 저장값과 갈린다.
    as_of = _latest_valid_close_date(list(dict(rows).items()))
    # lag 계산은 공용 함수(`app.trading_day_lag.benchmark_lag_trading_days`) — 화면
    # KOSPI 상태(POC3-02D-OPS-02 3-4)가 같은 값을 쓴다.
    lag, ref = benchmark_lag_trading_days(
        as_of, today_kst=end_date.isoformat()[:10], calendar_dir=calendar_dir
    )
    if lag is None or lag > MAX_STALE_TRADING_DAYS:
        # 배치 계층(`market_benchmark_batch.refresh_kospi`)이 ok 가 아닌 값을
        # 이미 failed 로 바꾸므로 배치 status 는 `success_with_benchmark_failure`
        # 가 된다 — 벤치마크 실패를 전체 성공으로 숨기지 않는다(OPS-02B-1 계약 ②).
        return {
            "status": "failed",
            "error": (
                f"source_stale:as_of={'unknown' if as_of is None else as_of},"
                f"ref={ref or 'unknown'},"
                f"lag={'unknown' if lag is None else lag}"
            ),
            "rows_written": written,
        }
    return {"status": "ok", "error": None, "rows_written": written}
