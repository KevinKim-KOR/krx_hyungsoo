"""POC5-02 — 원장 사건의 +1/+5/+20 거래일 원시 가격 결과(`price_outcome`) 성숙.

PLAN `docs/ai_plan/POC5/POC5-02_PRICE_OUTCOME_MATURITY_PLAN_V1.md` §2 · §8(설계자 판정).

```text
실행        08:10 · 09:20 배치 `main()` 이 기록 · 출력을 끝낸 뒤 1회(격리 · status · exit code 불변)
게이트      ① 원장 플래그(환경변수 · 없으면 .env 의 DECISION_LEDGER_ENABLED 한 키만 직접 읽음)
            ② 원장 파일이 이미 있음 — 원장 파일 · 폴더는 러너만 만든다
대상        FINALIZED · PRIMARY_LIVE · off_schedule=0 run 의 evaluable=1 item
            (ticker · sector · market/SP500 → KOSPI · index_group → ticker 마다)
날짜        15:30 이전 사건 = 사건일 종가가 +1 · 15:30 이후(15:40 CLOSE) = 다음 거래일부터 ·
            운영 거래일 캘린더만(가격표 행으로 휴장 추론 금지)
MATURED     +1 ~ horizon 예상 종가가 모두 저장됨 — 하나라도 빠지면 채우기 창 안 = PENDING(행 없음) ·
            창을 지나면 PRICE_MISSING(KOSPI 는 채우기가 없어 그 뒤 날짜가 저장되면 확정)
기록        (event_id, item_seq, series_id, horizon) 마다 INSERT OR IGNORE 1회 — UPDATE · DELETE 0
원시값만     수익률 · 경로 최대/최소 원시 소수 · 성공 · 방향 적중 판정 0
```
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from app.three_push_runner_common import PROJECT_ROOT
from app.three_push_runtime import ledger_outcome_prices as px
from app.three_push_runtime import ledger_store as store

FLAG_ENV = "DECISION_LEDGER_ENABLED"
ENV_PATH = PROJECT_ROOT / ".env"  # 호출 때 읽는다(테스트는 tmp 로 바꾼다)
HORIZONS = (1, 5, 20)
CLOSE_CUTOFF = "15:30"  # 이 시각 이후 사건은 다음 거래일 종가부터 센다
META_KEY = "schema_version.price_outcome"
SCHEMA_VERSION = "price_outcome.v1"

MATURED = "MATURED"
T0_MISSING = "T0_MISSING"
PRICE_MISSING = "PRICE_MISSING"
UNTRACKED_AFTER_EXIT = "UNTRACKED_AFTER_EXIT"
UNSUPPORTED = "UNSUPPORTED_PRICE_SOURCE"

_TARGET_KINDS = ("ticker", "sector", "market", "index_group")
_KST = timezone(timedelta(hours=9))

DDL = (
    """
    CREATE TABLE IF NOT EXISTS price_outcome (
        event_id TEXT NOT NULL,
        item_seq INTEGER NOT NULL,
        series_id TEXT NOT NULL,
        horizon INTEGER NOT NULL,
        t0_price REAL,
        t0_price_asof TEXT,
        signal_date_close REAL,
        previous_close REAL,
        eval_date TEXT,
        eval_price REAL,
        return_raw REAL,
        max_up_raw REAL,
        max_down_raw REAL,
        path_points INTEGER,
        price_basis TEXT,
        status TEXT NOT NULL,
        computed_at TEXT NOT NULL,
        source_collected_at TEXT,
        PRIMARY KEY (event_id, item_seq, series_id, horizon)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_price_outcome_status ON price_outcome (status)",
)
_COLUMNS = (
    "event_id",
    "item_seq",
    "series_id",
    "horizon",
    "t0_price",
    "t0_price_asof",
    "signal_date_close",
    "previous_close",
    "eval_date",
    "eval_price",
    "return_raw",
    "max_up_raw",
    "max_down_raw",
    "path_points",
    "price_basis",
    "status",
    "computed_at",
    "source_collected_at",
)


@dataclass
class _Target:
    event_id: str
    item_seq: int
    subject_kind: str
    subject_id: str
    held: Optional[int]
    values: dict[str, Any]
    t0_price: Optional[float]
    t0_asof: Optional[str]
    signal_date: str
    schedule: Optional[str]


@dataclass
class _Series:
    series: str  # px.SERIES_*
    ident: str  # ticker · KOSPI
    basis: Optional[str]
    t0_price: Optional[float]
    t0_asof: Optional[str]

    @property
    def series_id(self) -> str:
        return f"{self.series}:{self.ident}"


# ── 게이트 ─────────────────────────────────────────────────────────────────────


def flag_enabled(env_path: Optional[Path] = None) -> bool:
    """원장 플래그 — 환경변수가 있으면 그것, 없으면 `.env` 에서 이 한 키만 읽는다.

    배치 프로세스는 `.env` 를 환경변수로 올리지 않는다(설계자 승인 2026-10-07).
    """
    if FLAG_ENV in os.environ:
        return os.environ[FLAG_ENV].strip().lower() == "true"
    p = env_path or ENV_PATH
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines:
        key, sep, val = line.strip().partition("=")
        if sep and key.strip() == FLAG_ENV:
            return val.strip().strip('"').strip("'").lower() == "true"
    return False


# ── 진입 ─────────────────────────────────────────────────────────────────────


def run_maturity(
    *,
    today_kst: Optional[str] = None,
    calendar_dir: Optional[Path] = None,
    market_db: Optional[Path] = None,
    holdings_loader: Optional[Callable[[], Iterable[Any]]] = None,
    classify: Optional[Callable[..., dict[str, tuple[str, Optional[str]]]]] = None,
    env_path: Optional[Path] = None,
) -> dict[str, Any]:
    """한 번 돌린다. 결과는 건수 요약(dict)뿐이다 — 예외는 호출부가 격리한다."""
    if not flag_enabled(env_path):
        return {"status": "disabled"}
    if not store._db_path().exists():
        return {"status": "no_ledger"}  # 원장 파일은 러너만 만든다
    from app.three_push_runtime import ledger_context

    cal = px.Calendar(
        calendar_dir if calendar_dir is not None else ledger_context.CALENDAR_DIR
    )
    today = today_kst or datetime.now(_KST).date().isoformat()

    con = store.connect()
    try:
        for stmt in DDL:
            con.execute(stmt)
        store.meta_put_once(con, META_KEY, SCHEMA_VERSION)
        targets = _load_targets(con)
        done = {
            (r[0], r[1], r[2], r[3])
            for r in con.execute(
                "SELECT event_id, item_seq, series_id, horizon FROM price_outcome"
            )
        }
    finally:
        con.close()
    # 이미 끝난 item 은 날짜 계산 전에 뺀다(실행 시간이 누적 item 수로 늘지 않게).
    counts: dict[tuple[str, int], int] = {}
    for key in done:
        counts[(key[0], key[1])] = counts.get((key[0], key[1]), 0) + 1
    targets = [
        t for t in targets if counts.get((t.event_id, t.item_seq), 0) < _expected(t)
    ]

    rows: list[dict[str, Any]] = []
    pending = 0
    if targets:
        mcon = px.open_ro(market_db)
        try:
            reader = px.PriceReader(mcon)
            tickers = sorted(
                {t.subject_id for t in targets if t.subject_kind == "ticker"}
            )
            kinds = (
                (classify or px.classify)(tickers, db_path=market_db) if tickers else {}
            )
            holdings = px.current_holdings(holdings_loader)
            for t in targets:
                got, waiting = _mature_target(
                    t, reader, kinds, holdings, done, today=today, cal=cal
                )
                rows.extend(got)
                pending += waiting
        finally:
            mcon.close()

    if rows:
        con = store.connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            try:
                marks = ", ".join("?" for _ in _COLUMNS)
                con.executemany(
                    f"INSERT OR IGNORE INTO price_outcome ({', '.join(_COLUMNS)})"
                    f" VALUES ({marks})",
                    [tuple(r.get(c) for c in _COLUMNS) for r in rows],
                )
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
        finally:
            con.close()
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    return {
        "status": "ok",
        "targets": len(targets),
        "inserted": len(rows),
        "pending": pending,
        "by_status": by_status,
    }


def _expected(t: _Target) -> int:
    """그 item 에서 나올 행 수(계열 수 × horizon 수)."""
    if t.subject_kind == "index_group":
        return len(HORIZONS) * max(1, len(t.values.get("tickers") or []))
    return len(HORIZONS)


def _load_targets(con: Any) -> list[_Target]:
    marks = ", ".join("?" for _ in _TARGET_KINDS)
    rows = con.execute(
        "SELECT i.event_id, i.item_seq, i.subject_kind, i.subject_id, i.held,"
        " i.values_json, i.t0_price, i.t0_price_asof, r.runtime_date_kst,"
        " r.schedule_expected"
        " FROM signal_item i JOIN evaluation_run r ON r.event_id = i.event_id"
        " WHERE r.run_state = ? AND r.cohort = 'PRIMARY_LIVE' AND r.off_schedule = 0"
        f" AND i.evaluable = 1 AND i.subject_kind IN ({marks})"
        " ORDER BY r.started_at, i.item_seq",
        (store.RUN_FINALIZED, *_TARGET_KINDS),
    ).fetchall()
    out = []
    for r in rows:
        if r[2] == "market" and r[3] != "SP500":
            continue
        try:
            values = json.loads(r[5] or "{}")
        except ValueError:
            values = {}
        out.append(
            _Target(r[0], r[1], r[2], r[3], r[4], values, r[6], r[7], r[8], r[9])
        )
    return out


# ── 한 item ──────────────────────────────────────────────────────────────────


def _series_of(
    t: _Target,
    reader: px.PriceReader,
    kinds: dict[str, tuple[str, Optional[str]]],
    first_day: Optional[str],
    fill_start: Optional[str],
) -> tuple[list[_Series], bool, Optional[str]]:
    """`(계열 목록, 다음 실행에서 다시 볼지, 지원 안 함 사유 ticker)`."""
    if t.subject_kind == "ticker":
        kind, cls = kinds.get(t.subject_id, ("UNKNOWN", None))
        if kind == "ETF":
            basis = f"{px.PRICE_BASIS[px.SERIES_ETF]}|{cls}"
            return (
                [_Series(px.SERIES_ETF, t.subject_id, basis, t.t0_price, t.t0_asof)],
                False,
                None,
            )
        if kind == "STOCK":
            basis = f"{px.PRICE_BASIS[px.SERIES_STOCK]}|{cls}"
            if reader.latest_date(px.SERIES_STOCK, t.subject_id) is not None:
                return (
                    [
                        _Series(
                            px.SERIES_STOCK, t.subject_id, basis, t.t0_price, t.t0_asof
                        )
                    ],
                    False,
                    None,
                )
            table_latest = reader.latest_date(px.SERIES_STOCK)
            passed = bool(first_day and table_latest and table_latest >= first_day)
            closed = bool(first_day and fill_start and fill_start > first_day)
            if passed or closed:
                return (
                    [],
                    False,
                    t.subject_id,
                )  # 개별주 표가 지원하지 않는 종목(코스닥 등)
            return [], True, None  # 아직 적재 차례가 아님
        return [], True, None  # UNKNOWN — 원천 하나를 못 읽음 · 다음 실행에서 다시 본다
    if t.subject_kind == "sector":
        ticker = t.values.get("ticker")
        if not ticker:
            return [], False, None
        basis = px.PRICE_BASIS[px.SERIES_ETF]
        return (
            [_Series(px.SERIES_ETF, str(ticker), basis, t.t0_price, t.t0_asof)],
            False,
            None,
        )
    if t.subject_kind == "market":
        prev = reader.last_before(px.SERIES_KOSPI, "KOSPI", t.signal_date)
        basis = px.PRICE_BASIS[px.SERIES_KOSPI]
        p0, a0 = (prev[1], prev[0]) if prev else (None, None)
        return [_Series(px.SERIES_KOSPI, "KOSPI", basis, p0, a0)], False, None
    out = []
    asof = t.values.get("price_asof")
    for ticker in t.values.get("tickers") or []:
        got = reader.closes(px.SERIES_ETF, str(ticker), [asof]) if asof else {}
        p0 = got[asof][0] if asof in got else None
        basis = px.PRICE_BASIS[px.SERIES_ETF]
        out.append(_Series(px.SERIES_ETF, str(ticker), basis, p0, asof if p0 else None))
    return out, False, None


def _mature_target(
    t: _Target,
    reader: px.PriceReader,
    kinds: dict[str, tuple[str, Optional[str]]],
    holdings: Optional[set[str]],
    done: set[tuple[str, int, str, int]],
    *,
    today: str,
    cal: px.Calendar,
) -> tuple[list[dict[str, Any]], int]:
    after_close = (t.schedule or "") >= CLOSE_CUTOFF
    if after_close:
        first = cal.next_after(t.signal_date)
    else:
        got = cal.days_from(t.signal_date, 1)
        first = got[0] if got else None
    series, retry, unsupported = _series_of(
        t, reader, kinds, first, cal.fill_start(px.SERIES_STOCK, today)
    )
    now = store.now_utc()
    rows: list[dict[str, Any]] = []
    if unsupported is not None:
        sid = f"unsupported:{unsupported}"
        for h in HORIZONS:
            if (t.event_id, t.item_seq, sid, h) not in done:
                rows.append(_row(t, sid, h, None, UNSUPPORTED, now))
        return rows, 0
    if retry or first is None:
        return [], len(HORIZONS)
    days = cal.days_from(first, max(HORIZONS))
    prev_day = cal.previous(t.signal_date)
    waiting = 0
    for s in series:
        todo = [
            h for h in HORIZONS if (t.event_id, t.item_seq, s.series_id, h) not in done
        ]
        if not todo:
            continue
        if s.t0_price is None or s.t0_price <= 0:
            rows.extend(_row(t, s.series_id, h, s, T0_MISSING, now) for h in todo)
            continue
        side = reader.closes(
            s.series, s.ident, [d for d in (t.signal_date, prev_day) if d]
        )
        for h in todo:
            if len(days) < h:
                waiting += 1
                continue
            row = _horizon(t, s, h, days[:h], reader, holdings, today, cal, now)
            if row is None:
                waiting += 1
                continue
            row["signal_date_close"] = side.get(t.signal_date, (None, None))[0]
            row["previous_close"] = (
                side.get(prev_day, (None, None))[0] if prev_day else None
            )
            rows.append(row)
    return rows, waiting


def _horizon(
    t: _Target,
    s: _Series,
    h: int,
    path: list[str],
    reader: px.PriceReader,
    holdings: Optional[set[str]],
    today: str,
    cal: px.Calendar,
    now: str,
) -> Optional[dict[str, Any]]:
    """그 horizon 의 행 — 아직 정할 수 없으면 None(PENDING)."""
    closes = reader.closes(s.series, s.ident, path)
    missing = [d for d in path if d not in closes]
    if not missing:
        vals = [closes[d][0] for d in path]
        t0 = float(s.t0_price)
        row = _row(t, s.series_id, h, s, MATURED, now)
        row.update(
            eval_date=path[-1],
            eval_price=vals[-1],
            return_raw=vals[-1] / t0 - 1.0,
            max_up_raw=max(vals) / t0 - 1.0,
            max_down_raw=min(vals) / t0 - 1.0,
            path_points=len(vals),
            source_collected_at=closes[path[-1]][1],
        )
        return row
    status: Optional[str] = None
    if s.series == px.SERIES_KOSPI:
        latest = reader.latest_date(px.SERIES_KOSPI)
        if latest and all(d < latest for d in missing):
            status = PRICE_MISSING  # KOSPI 는 빠진 날을 채우지 않는다
    else:
        if _untracked(t, s, missing[0], path[-1], reader, holdings):
            status = UNTRACKED_AFTER_EXIT
        else:
            start = cal.fill_start(s.series, today)
            if start and all(d < start for d in missing):
                status = PRICE_MISSING  # 채우기 창을 지나 다시 채워지지 않는다
    if status is None:
        return None
    row = _row(t, s.series_id, h, s, status, now)
    row.update(eval_date=path[-1], path_points=len(path) - len(missing))
    return row


def _untracked(
    t: _Target,
    s: _Series,
    first_missing: str,
    eval_date: str,
    reader: px.PriceReader,
    holdings: Optional[set[str]],
) -> bool:
    """매도 뒤 개별주 추적 중단 — 사건 때 보유 · 지금 미보유(보유 목록을 읽었을 때만) ·
    그 종목 행이 첫 빠진 날 전에 끊김 · 공통 축(ETF 표)은 **평가일**까지 지남."""
    if s.series != px.SERIES_STOCK or t.held != 1 or holdings is None:
        return False
    if s.ident in holdings:
        return False
    last = reader.latest_date(px.SERIES_STOCK, s.ident)
    axis = reader.latest_date(px.SERIES_ETF)
    return (last is None or last < first_missing) and bool(axis and axis >= eval_date)


def _row(
    t: _Target,
    series_id: str,
    h: int,
    s: Optional[_Series],
    status: str,
    now: str,
) -> dict[str, Any]:
    return {
        "event_id": t.event_id,
        "item_seq": t.item_seq,
        "series_id": series_id,
        "horizon": h,
        "t0_price": s.t0_price if s else None,
        "t0_price_asof": s.t0_asof if s else None,
        "price_basis": s.basis if s else None,
        "status": status,
        "computed_at": now,
    }


__all__ = [
    "DDL",
    "FLAG_ENV",
    "HORIZONS",
    "MATURED",
    "PRICE_MISSING",
    "T0_MISSING",
    "UNSUPPORTED",
    "UNTRACKED_AFTER_EXIT",
    "flag_enabled",
    "run_maturity",
]
