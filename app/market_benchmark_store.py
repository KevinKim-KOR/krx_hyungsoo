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

import hashlib
import json
import math
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from app.market_benchmark_freshness import kospi_freshness
from app.market_data_store import DEFAULT_DB_PATH
from app.trading_day_lag import (
    benchmark_lag_trading_days,
    expected_previous_trading_day,
    trading_days_ending,
)

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


# ─── KOSPI refresh — KRX 공식 지수 종가 (POC3-02D-OPS-03 확정 계약 9) ──────────
#
# FDR `KS11`(GitHub 캐시)이 2026-09-17 12:22 KST 에 멈췄고 그날 값도 공식 종가가
# 아니었다(PLAN STEP 1-6 · 공식 6,715.41 ≠ 저장 6,724.34). 자료원을 KRX Open API
# `idx/kospi_dd_trd` 공식 종가(`IDX_NM='코스피'` · `CLSPRC_IDX`)로 바꾼다(사용자 승인
# 2026-09-29 · 기존 키). 네트워크 경계는 `krx_sync._default_kospi_fetcher` 다.
#
# - 조회 날짜 = **저장 최신일(포함)부터 기대 T-1 까지** 거래일(캘린더) · 날짜당 1회 ·
#   오래된 날부터 · 회차 상한 `KOSPI_MAX_CALLS_PER_RUN`(넘으면 다음 회차가 잇는다).
# - 새 날짜를 하나라도 못 받으면 거기서 멈춘다 — 뒤 날짜만 저장하면 빈 날이 생기고,
#   다음 회차는 저장 최신일부터 보므로 그 빈 날을 다시 채우지 않는다. 저장 최신일
#   재확인(첫 날짜)만은 비어도 다음 날짜로 간다(이미 있는 행 · 빈 날 없음). 호출
#   예외는 곧바로 멈춘다(자료원 불통 · 헛호출 금지).
# - 같은 실행의 재시도(설계자 RESULT STEP 3)는 이번 실행이 저장 최신일을 이미 확인해
#   저장까지 마쳤으면 그 날짜를 빼고(`recheck_latest=False`) 그 뒤 빠진 날만 T-1 까지
#   부른다. 아니면(첫 시도가 그 날짜에서 멈춤 등) 다시 포함한다
#   (`market_benchmark_kospi_retry.latest_confirmed`).
# - 기존 행과 값 또는 source 가 다르면 **덮어쓰기 전에** 증거 JSON(기존 값 · source ·
#   행 hash · 새 값)을 남긴다. 증거를 못 남기면 아무것도 쓰지 않는다(확정 계약 9 ①).
#   같은 값 · 같은 source 인 행은 다시 쓰지 않는다.
# - 저장 뒤 날짜별 read-back(값 · source)으로 확인한다. 변경 전후 건수 · 값을 결과에
#   남긴다(확정 계약 9 ④).
# - 최신성 = `market_benchmark_freshness.kospi_freshness`(기대 T-1 정확 일치) — 계산 ·
#   API 경로와 같은 함수(확정 계약 9 ⑤).

KOSPI_ID = "KOSPI"
KOSPI_SOURCE = "KRX_OPEN_API/idx_kospi_dd_trd"
KOSPI_INDEX_NAME = "코스피"
# 평소 1~2회(저장 최신일 재확인 + T-1). 자료원 전환 첫 회는 09-17 부터 약 10회.
KOSPI_MAX_CALLS_PER_RUN = 40
# 정정 증거 JSON 폴더. **호출 시점에** 읽는다 — 테스트는 tmp 로 넘기거나 이 상수를 바꾼다.
KOSPI_EVIDENCE_DIR = Path("state/market/kospi_source_corrections")

KospiFetcher = Callable[[str, str], list]


def _valid_close(value: Any) -> bool:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(v) and v > 0


def _kospi_rows(db_path: Path) -> dict[str, dict]:
    """저장된 KOSPI 행 전부(date → 행). 증거 · 대조 · read-back 용."""
    with _connection(db_path) as con:
        cur = con.execute(
            "SELECT date, close, source, created_at FROM market_benchmark_daily_price "
            "WHERE benchmark_id = ?",
            (KOSPI_ID,),
        )
        return {
            str(r[0]): {
                "date": str(r[0]),
                "close": r[1],
                "source": r[2],
                "created_at": r[3],
            }
            for r in cur.fetchall()
        }


def _latest_valid(rows: dict[str, dict]) -> Optional[str]:
    valid = [d for d, r in rows.items() if _valid_close(r["close"])]
    return max(valid) if valid else None


def _row_hash(row: dict) -> str:
    """기존 행(benchmark_id · date · close · source · created_at)의 sha256."""
    payload = json.dumps(
        {"benchmark_id": KOSPI_ID, **row}, sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _fetch_dates(
    latest: Optional[str],
    expected: str,
    *,
    calendar_dir: Optional[Path],
    max_calls: int,
    include_latest: bool = True,
) -> list[str]:
    """조회할 거래일(오래된 날부터). 저장 최신일 포함 · 기대 T-1 까지 · 상한 `max_calls`.

    `include_latest=False`(재시도)면 저장 최신일은 빼고 그 뒤 날짜만 돌려준다.
    """
    try:
        start = date.fromisoformat(min(latest, expected)) if latest else None
    except ValueError:
        start = None
    if start is None:
        # 빈 표 — 기대 T-1 까지 최근 `max_calls` 거래일만 받는다.
        return trading_days_ending(expected, max_calls, calendar_dir=calendar_dir)
    span = (date.fromisoformat(expected) - start).days + 1
    days = trading_days_ending(expected, span, calendar_dir=calendar_dir)
    first = start.isoformat()
    keep = [d for d in days if (d >= first if include_latest else d > first)]
    return keep[:max_calls]


def _pick_kospi_close(rows: list, bas_dd: str) -> tuple[Optional[float], Optional[str]]:
    """응답에서 `코스피` 종가 하나. 못 고르면 `(None, 사유)`."""
    if not rows:
        return None, "no_rows"
    hits = [
        r
        for r in rows
        if isinstance(r, dict)
        and str(r.get("IDX_NM") or "").strip() == KOSPI_INDEX_NAME
    ]
    if not hits:
        return None, "kospi_row_missing"
    if len(hits) > 1:
        return None, "kospi_row_duplicate"
    row = hits[0]
    if str(row.get("BAS_DD") or "").strip() != bas_dd:
        return None, "basis_mismatch"
    try:
        close = float(str(row.get("CLSPRC_IDX") or "").replace(",", "").strip())
    except ValueError:
        return None, "invalid_close"
    if not _valid_close(close):
        return None, "invalid_close"
    return close, None


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _diff_existing(before: dict[str, dict], fetched: dict[str, float]) -> list[dict]:
    """받은 날짜 중 기존 행과 값 또는 source 가 다른 것(같은 날짜 전체 대조)."""
    changes: list[dict] = []
    for d, new in sorted(fetched.items()):
        old = before.get(d)
        if old is None:
            continue
        same_value = _valid_close(old["close"]) and round(float(old["close"]), 2) == (
            round(new, 2)
        )
        if same_value and old["source"] == KOSPI_SOURCE:
            continue
        changes.append(
            {
                "date": d,
                "old_close": old["close"],
                "old_source": old["source"],
                "old_created_at": old["created_at"],
                "old_row_hash": _row_hash(old),
                "new_close": new,
                "new_source": KOSPI_SOURCE,
                "value_changed": not same_value,
            }
        )
    return changes


def _fetch_official(
    dates: list[str], *, fetch: KospiFetcher, key: str, recheck: Optional[str]
) -> tuple[dict[str, float], list[dict], Optional[str], Optional[str]]:
    """날짜별 1회 조회. `(받은 종가, 시도 기록, 호출 예외, 멈춘 사유)`.

    시도 기록에는 날짜 · 행 수 · 결과 · 예외 종류만 남긴다(키 · 가격 값 없음).
    """
    fetched: dict[str, float] = {}
    attempts: list[dict] = []
    for d in dates:
        bas = d.replace("-", "")
        try:
            rows = list(fetch(bas, key) or [])
        except Exception as e:  # noqa: BLE001 - 자료원 불통은 결과로 돌려준다
            attempts.append(
                {"date": d, "result": "fetch_error", "error_type": type(e).__name__}
            )
            return fetched, attempts, f"fetch_failed:{type(e).__name__}", None
        close, why = _pick_kospi_close(rows, bas)
        attempts.append({"date": d, "rows": len(rows), "result": why or "ok"})
        if why is None:
            fetched[d] = close
        elif d != recheck:
            return fetched, attempts, None, f"{why}@{d}"
    return fetched, attempts, None, None


def refresh_kospi_benchmark(
    *,
    end_date,
    fetcher: Optional[KospiFetcher] = None,
    api_key: Optional[str] = None,
    env_path: Optional[Path] = None,
    db_path: Path = DEFAULT_DB_PATH,
    calendar_dir: Optional[Path] = None,
    evidence_dir: Optional[Path] = None,
    max_calls: int = KOSPI_MAX_CALLS_PER_RUN,
    recheck_latest: bool = True,
) -> dict:
    """KOSPI 공식 종가(KRX `idx/kospi_dd_trd`)를 받아 저장하고 최신성을 판정한다.

    실패는 dict 로 돌려준다(전체 refresh 흐름을 멈추지 않는다 — 지시문 §4.4 ·
    OPS-02B-1 계약 ③). `end_date` = 실행일(KST) — 기대 T-1 을 정한다.
    `recheck_latest=False` — 같은 실행의 재시도(설계자 RESULT STEP 3). 저장 최신일을
    다시 부르지 않는다.

    `status` 는 적재 뒤 `as_of`(유효 종가 마지막 날짜)가 기대 T-1 이면 `ok` 다.
    아니면 `failed` 이고 `error` 는:

    | 경우 | error | 화면 상태 |
    |---|---|---|
    | 공개 전 · 빈 응답 등 | `source_stale:as_of=…,expected=…,lag=…` | 기준일 지연 |
    | 키 없음 · 호출 예외 | `api_key_missing` · `fetch_failed:<예외>` | 자료원 확인 실패 |
    | 증거 · 저장 · read-back 실패 | `evidence_write_failed:…` 등 | 자료원 확인 실패 |

    `source_stale` 에는 멈춘 사유(`,reason=no_rows@2026-09-29` 등)가 붙을 수 있다.

    증거 · 저장 · read-back 실패는 기준일이 T-1 이어도 `failed` 다. 적재한 행은
    되돌리지 않는다. 기대 T-1 행이 이미 있으면 재확인 호출이 실패해도 `ok` 다
    (호출 기록은 `attempts` · `note` 에 남는다).
    """
    from app.market_briefing import krx_sync

    today = end_date.isoformat()[:10]
    expected = expected_previous_trading_day(today, calendar_dir=calendar_dir)
    before = _kospi_rows(db_path)
    out: dict[str, Any] = {
        "status": "failed",
        "error": None,
        "rows_written": 0,
        "source": KOSPI_SOURCE,
        "expected_as_of_date": expected,
        "calls": 0,
        "attempts": [],
        "corrections": [],
        "replaced": 0,
        "evidence_path": None,
        "before": {"rows": len(before), "as_of": _latest_valid(before)},
        "after": None,
    }
    fetch_error: Optional[str] = None
    integrity_error: Optional[str] = None
    stop: Optional[str] = None
    key = api_key or krx_sync.read_api_key(env_path)
    if expected is None:
        fetch_error = "expected_date_unknown"
    elif not key:
        fetch_error = "api_key_missing"
    else:
        latest = out["before"]["as_of"]
        dates = _fetch_dates(
            latest,
            expected,
            calendar_dir=calendar_dir,
            max_calls=max_calls,
            include_latest=recheck_latest,
        )
        fetched, attempts, fetch_error, stop = _fetch_official(
            dates,
            fetch=fetcher or krx_sync._default_kospi_fetcher,
            key=key,
            recheck=latest if recheck_latest else None,
        )
        out["calls"] = len(attempts)
        out["attempts"] = attempts
        integrity_error = _store_fetched(
            out, before, fetched, today, evidence_dir, db_path
        )
    return _finish(out, today, calendar_dir, fetch_error, integrity_error, stop)


def _store_fetched(
    out: dict,
    before: dict[str, dict],
    fetched: dict[str, float],
    today: str,
    evidence_dir: Optional[Path],
    db_path: Path,
) -> Optional[str]:
    """증거 → 저장 → read-back. 실패 사유(무결성) 또는 `None`. `out` 을 채운다."""
    changes = _diff_existing(before, fetched)
    changed = {c["date"] for c in changes}
    writes = {d: v for d, v in fetched.items() if d not in before or d in changed}
    out["replaced"] = len(changes)
    out["corrections"] = [
        {k: c[k] for k in ("date", "old_close", "new_close", "old_source")}
        for c in changes
        if c["value_changed"]
    ]
    evidence: Optional[dict] = None
    if changes:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = (evidence_dir or KOSPI_EVIDENCE_DIR) / f"kospi_correction_{stamp}.json"
        evidence = {
            "kind": "kospi_source_correction",
            "benchmark_id": KOSPI_ID,
            "created_at_utc": _utcnow_iso(),
            "today_kst": today,
            "expected_as_of_date": out["expected_as_of_date"],
            "new_source": KOSPI_SOURCE,
            "before": out["before"],
            "changes": changes,
            "new_dates": sorted(d for d in writes if d not in before),
            "stage": "before_write",
        }
        try:
            _write_json_atomic(path, evidence)
        except Exception as e:  # noqa: BLE001 - 증거 없이 덮어쓰지 않는다
            return f"evidence_write_failed:{type(e).__name__}"
        out["evidence_path"] = str(path)
    if writes:
        try:
            upsert_benchmark_prices(
                benchmark_id=KOSPI_ID,
                benchmark_name=KOSPI_ID,
                rows=sorted(writes.items()),
                source=KOSPI_SOURCE,
                db_path=db_path,
            )
        except Exception as e:  # noqa: BLE001
            return f"store:{type(e).__name__}"
    out["rows_written"] = len(writes)
    after = _kospi_rows(db_path)
    out["after"] = {"rows": len(after), "as_of": _latest_valid(after)}
    bad = [
        d
        for d, v in sorted(writes.items())
        if not (
            d in after
            and after[d]["source"] == KOSPI_SOURCE
            and _valid_close(after[d]["close"])
            and abs(float(after[d]["close"]) - v) < 1e-9
        )
    ]
    if evidence is not None:
        evidence.update(
            stage="after_write",
            after=out["after"],
            readback_ok=not bad,
            after_rows=[after.get(c["date"]) for c in changes],
        )
        try:
            _write_json_atomic(Path(out["evidence_path"]), evidence)
        except Exception:  # noqa: BLE001 - 보존은 쓰기 전에 끝났다 · 결과에도 남는다
            out["evidence_after_write_failed"] = True
    return f"readback_mismatch:{bad[0]}" if bad else None


def _finish(
    out: dict,
    today: str,
    calendar_dir: Optional[Path],
    fetch_error: Optional[str],
    integrity_error: Optional[str],
    stop: Optional[str],
) -> dict:
    as_of = (out["after"] or out["before"])["as_of"]
    out["as_of_date"] = as_of
    fresh = kospi_freshness(as_of, today_kst=today, calendar_dir=calendar_dir)
    if integrity_error:
        out.update(status="failed", error=integrity_error)
    elif fresh.is_fresh:
        out.update(status="ok", error=None)
        if fetch_error or stop:
            out["note"] = fetch_error or stop
    elif fetch_error:
        out.update(status="failed", error=fetch_error)
    else:
        # 자료원이 아직 T-1 을 주지 않음 — 화면은 '기준일 지연'(호출 실패와 구분).
        lag, _ref = benchmark_lag_trading_days(
            as_of, today_kst=today, calendar_dir=calendar_dir
        )
        out.update(
            status="failed",
            error=(
                f"source_stale:as_of={as_of or 'unknown'},"
                f"expected={fresh.expected_date or 'unknown'},"
                f"lag={'unknown' if lag is None else lag}"
                + (f",reason={stop}" if stop else "")
            ),
        )
    return out
