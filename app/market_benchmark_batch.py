"""POC3-OPS-02B-1 — 운영 배치용 benchmark 갱신 (계약 ①).

`DEF-KOSPI-BENCHMARK-VALUE-ASOF-INTEGRITY` 의 **운영 층위**다.

OCI 07:20 배치(`run_oci_market_data_batch.py`)는 ETF 가격만 갱신하고 KOSPI·VIX
갱신을 호출하지 않았다. `refresh_kospi_benchmark` 는 `POST /market/refresh`
(Mac 수동) 경로에만, VIX 는 cron 미등록 스크립트에만 있었다. 그래서 ETF 가격이
2026-09-07 로 최신인데 KOSPI·VIX 만 2026-07-03 에 멈춰 있었다.

**설계자 확정 계약**

| # | 계약 |
|---|---|
| 1 | ETF 가격 성공과 benchmark 성공을 **별도 상태로 기록** |
| 2 | benchmark 실패를 **전체 배치 성공으로 숨기지 않는다** |
| 3 | benchmark 실패 때문에 **정상 ETF 가격 적재까지 롤백하지 않는다** |

그래서 이 모듈은 **예외를 던지지 않는다.** 각 benchmark 의 성공/실패를 dict 로
돌려주고, 판단은 배치가 한다.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

BENCHMARK_KOSPI = "KOSPI"
BENCHMARK_VIX = "VIX"

# POC3-OPS-02B-2 §M-2 — 08:00 시장 브리핑이 쓰는 미국 지수 **3종만**.
# Russell 2000·USD/KRW 는 이번 Step 에 추가하지 않는다(설계자 확정).
# identity 는 OPS-02B-1 probe 에서 확인된 것만 쓴다. `SOX` 는 실패하고
# `^SOX` 로만 조회된다.
US_BENCHMARKS: tuple[tuple[str, str, str], ...] = (
    ("US500", "S&P500", "FDR_US500"),
    ("IXIC", "Nasdaq", "FDR_IXIC"),
    ("^SOX", "반도체지수", "FDR_SOX"),
)

# 1일 수익률에는 **최신·직전 두 세션**이 필요하다. 전체 과거 backfill 을 하지
# 않고 최근 구간만 조회한다.
US_LOOKBACK_DAYS = 14
US_REQUIRED_SESSIONS = 2


def _result(
    status: str, *, as_of: Optional[str] = None, error: Optional[str] = None, **extra
) -> dict[str, Any]:
    out: dict[str, Any] = {"status": status, "as_of_date": as_of, "error": error}
    out.update(extra)
    return out


def refresh_kospi(*, end_date: date, db_path=None) -> dict[str, Any]:
    """KOSPI benchmark 갱신. 실패해도 예외를 올리지 않는다."""
    try:
        from app.market_benchmark_store import (
            latest_benchmark_date,
            refresh_kospi_benchmark,
        )
    except Exception as e:  # noqa: BLE001
        return _result("failed", error=f"import:{type(e).__name__}")
    try:
        kwargs = {"end_date": end_date}
        if db_path is not None:
            kwargs["db_path"] = db_path
        res = refresh_kospi_benchmark(**kwargs)
    except Exception as e:  # noqa: BLE001
        return _result("failed", error=f"{type(e).__name__}: {str(e)[:200]}")
    # `refresh_kospi_benchmark` 는 실패를 dict 로 돌려준다(예외를 올리지 않는다).
    status = (res or {}).get("status") or "failed"
    try:
        as_of = latest_benchmark_date(
            BENCHMARK_KOSPI, **({"db_path": db_path} if db_path is not None else {})
        )
    except Exception:  # noqa: BLE001
        as_of = None
    return _result(
        "ok" if status == "ok" else "failed",
        as_of=as_of,
        error=(res or {}).get("error"),
        written=(res or {}).get("rows_written"),
    )


def refresh_vix(*, db_path=None) -> dict[str, Any]:
    """VIX 갱신. 기존 `scripts/_market_refresh/vix_ingest.run_vix_ingest` 재사용."""
    try:
        from scripts._market_refresh.vix_ingest import run_vix_ingest
    except Exception as e:  # noqa: BLE001
        return _result("failed", error=f"import:{type(e).__name__}")
    try:
        if db_path is None:
            from app.market_benchmark_store import DEFAULT_DB_PATH

            db_path = DEFAULT_DB_PATH
        rc = run_vix_ingest(db_path)
    except Exception as e:  # noqa: BLE001
        return _result("failed", error=f"{type(e).__name__}: {str(e)[:200]}")
    try:
        from app.market_benchmark_store import latest_benchmark_date

        as_of = latest_benchmark_date(
            BENCHMARK_VIX, **({"db_path": db_path} if db_path is not None else {})
        )
    except Exception:  # noqa: BLE001
        as_of = None
    return _result("ok" if rc in (0, None) else "failed", as_of=as_of, exit_code=rc)


def refresh_us_index(
    symbol: str,
    name: str,
    source: str,
    *,
    end_date: date,
    db_path=None,
    price_fetcher=None,
) -> dict[str, Any]:
    """미국 지수 1종 갱신. **최근 구간만** 조회한다.

    설계자 §M-2 — 미래 날짜·중복 날짜·종가 결측·조회 실패는 **fail-closed**.
    최신·직전 **두 세션이 모두 있어야** 사용 가능(`ok`)으로 본다.
    """
    from datetime import timedelta

    try:
        from app.market_benchmark_store import (
            latest_benchmark_date,
            upsert_benchmark_prices,
        )
    except Exception as e:  # noqa: BLE001
        return _result("failed", error=f"import:{type(e).__name__}")

    if price_fetcher is None:
        try:
            from app.market_data_fdr import _default_price_fetcher

            price_fetcher = _default_price_fetcher
        except Exception as e:  # noqa: BLE001
            return _result("failed", error=f"fdr_import:{type(e).__name__}")

    start = end_date - timedelta(days=US_LOOKBACK_DAYS)
    try:
        df = price_fetcher(symbol, start, end_date)
    except Exception as e:  # noqa: BLE001
        return _result("failed", error=f"{type(e).__name__}: {str(e)[:160]}")

    rows: list[tuple[str, Optional[float]]] = []
    seen: set[str] = set()
    try:
        for idx, row in df.iterrows():
            d = idx.strftime("%Y-%m-%d")
            if d > end_date.isoformat():
                return _result("failed", as_of=None, error=f"future_date:{d}")
            if d in seen:
                return _result("failed", as_of=None, error=f"duplicate_date:{d}")
            seen.add(d)
            close = row.get("Close") if hasattr(row, "get") else row["Close"]
            if close is None or close != close or float(close) <= 0:
                continue  # 결측일은 담지 않는다. 아래 세션 수 검사에서 걸린다.
            rows.append((d, float(close)))
    except Exception as e:  # noqa: BLE001
        return _result("failed", error=f"parse:{type(e).__name__}")

    if len(rows) < US_REQUIRED_SESSIONS:
        return _result(
            "failed",
            error=f"insufficient_sessions:{len(rows)}<{US_REQUIRED_SESSIONS}",
            sessions=len(rows),
        )

    kwargs = {"db_path": db_path} if db_path is not None else {}
    try:
        written = upsert_benchmark_prices(
            benchmark_id=symbol,
            benchmark_name=name,
            rows=rows,
            source=source,
            **kwargs,
        )
        as_of = latest_benchmark_date(symbol, **kwargs)
    except Exception as e:  # noqa: BLE001
        return _result("failed", error=f"store:{type(e).__name__}")

    return _result("ok", as_of=as_of, written=written, sessions=len(rows))


def refresh_benchmarks(*, end_date: date, db_path=None, logger=None) -> dict[str, Any]:
    """KOSPI·VIX 를 각각 갱신하고 **개별 상태**를 돌려준다.

    반환:
        {
          "kospi": {...}, "vix": {...},
          "status": "ok" | "partial" | "failed",
          "failed": ["vix", ...],
        }

    - **예외를 올리지 않는다** — 배치가 ETF 가격 적재를 롤백하지 않게 하기 위해서다.
    - 하나만 실패하면 `partial` 이다. 배치는 이 값을 record 에 그대로 남겨
      **benchmark 실패를 전체 성공으로 숨기지 않는다.**
    """

    # 개별 함수도 내부에서 catch 하지만, **여기서 한 번 더 감싼다.** 이 경계를
    # 넘어가는 예외 하나가 배치 전체를 실패시켜 정상 ETF 가격 적재까지 되돌린다.
    def _guard(_label, _fn, *args, **kw):
        # `_label`·`_fn` 에 밑줄을 붙인다 — `refresh_us_index(symbol, name, source)`
        # 의 `name` 과 이름이 겹치면 TypeError 가 난다(테스트가 잡았다).
        try:
            return _fn(*args, **kw)
        except Exception as e:  # noqa: BLE001
            return _result(
                "failed", error=f"{_label}:{type(e).__name__}: {str(e)[:160]}"
            )
        # `BaseException`(KeyboardInterrupt·SystemExit·SIGTERM 변환 등)은 **삼키지
        # 않는다.** 프로세스 종료 신호를 "benchmark 실패" 로 바꾸면 배치가 죽는
        # 중에도 정상 종료한 것처럼 보인다 (검증자 r1 B-6).

    kospi = _guard("kospi", refresh_kospi, end_date=end_date, db_path=db_path)
    vix = _guard("vix", refresh_vix, db_path=db_path)

    # POC3-OPS-02B-2 — 미국 지수 3종. **각각 독립**이고, 실패가 KOSPI·VIX 나
    # ETF 가격 성공분을 되돌리지 않는다(설계자 §M-2).
    us: dict[str, Any] = {}
    for symbol, name, source in US_BENCHMARKS:
        us[symbol] = _guard(
            f"us:{symbol}",
            refresh_us_index,
            symbol,
            name,
            source,
            end_date=end_date,
            db_path=db_path,
        )

    pairs = [("kospi", kospi), ("vix", vix)] + [(f"us:{k}", v) for k, v in us.items()]
    failed = [n for n, r in pairs if r["status"] != "ok"]
    if not failed:
        status = "ok"
    elif len(failed) == len(pairs):
        status = "failed"
    else:
        status = "partial"
    if logger is not None:
        logger.info(
            "benchmark 갱신: kospi=%s(as_of=%s) vix=%s(as_of=%s) -> %s",
            kospi["status"],
            kospi["as_of_date"],
            vix["status"],
            vix["as_of_date"],
            status,
        )
    return {
        "kospi": kospi,
        "vix": vix,
        "us_indices": us,
        "status": status,
        "failed": failed,
    }


__all__ = [
    "BENCHMARK_KOSPI",
    "BENCHMARK_VIX",
    "US_BENCHMARKS",
    "US_LOOKBACK_DAYS",
    "US_REQUIRED_SESSIONS",
    "refresh_us_index",
    "refresh_benchmarks",
    "refresh_kospi",
    "refresh_vix",
]
