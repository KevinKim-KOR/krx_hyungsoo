"""POC6-03 — 한 묶음 조회 · 연구 사본 저장(PLAN §7-2 · 판정 §3).

```text
대상    POC6-02 공식 snapshot 의 ETF(26종) — 목록 고정 · 시장 전체로 넓히지 않음
조회    기존 `market_data_fdr` 의 읽기 부분만(`_default_price_fetcher` · `_dataframe_to_price_rows`)
        저장부(`upsert_daily_prices` · `log_refresh`) 호출 0 · 요청 시간 제한 = 기존 `fdr_request_timeout()`
구간    종목별 snapshot 첫 저장일 ~ 기준일 T · 종목마다 한 번 · 자동 재시도 · 실패 종목 반복 조회 없음
저장    state/ml/research/poc6_03/<시각>_<id>/copy.sqlite · fetch.json(임시 폴더에 다 쓴 뒤 이름 바꾸기)
```

라이브 시세 DB · 보유 · 원장 · OCI 쓰기 0. 같은 날 받았다고 동시점 snapshot 이 보장되지는 않는다(판정 §3).
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Callable, Optional

from app import market_data_fdr as fdr_mod
from app.d20_pooled.snapshot import digest as snapshot_digest
from app.three_push_runtime.market_data_batch import fdr_request_timeout

SCHEMA = "poc6_03_copy_v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 저장소 기준 절대 경로(실행 위치와 무관 · gitignored) · 호출 때 읽는다(시험이 tmp 로 바꾼다)
RESEARCH_ROOT = PROJECT_ROOT / "state" / "ml" / "research" / "poc6_03"
MAX_TARGETS = 26  # 설계자 판정 Q1 · §3 — POC6-02 공식 snapshot 의 보유 ETF 26종 한 묶음
SOURCE = fdr_mod.FDR_SOURCE
OK, FAILED, NO_DATA, NO_STORED = "OK", "FAILED", "NO_DATA", "NO_STORED_HISTORY"
_KST = timezone(timedelta(hours=9))

Fetcher = Callable[[str, date, date], Any]


class CopySaveError(Exception):
    """연구 사본 저장 실패 — 정상 완료로 보이지 않는다."""


class FetchRefused(Exception):
    """승인 범위 밖 조회 거절(다른 snapshot · 대상 수 초과 · 같은 snapshot 사본이 이미 있음) — 조회 0."""


def existing_copies(snapshot_digest_value: str) -> list[str]:
    root = Path(RESEARCH_ROOT)
    out = []
    for db in sorted(root.glob("*/copy.sqlite")) if root.is_dir() else []:
        try:
            con = sqlite3.connect(f"file:{db.resolve()}?mode=ro", uri=True)
            try:
                row = con.execute(
                    "SELECT value FROM meta WHERE key = 'snapshot_digest'"
                ).fetchone()
            finally:
                con.close()
        except sqlite3.Error:
            continue
        if row and json.loads(row[0]) == snapshot_digest_value:
            out.append(db.parent.name)
    return out


def preflight(snap: dict[str, Any], expect_digest: str) -> None:
    """승인된 한 묶음만 — 공식 snapshot digest 일치 · 대상 ≤ 26 · 같은 snapshot 사본 없음(반복 조회 금지)."""
    got = snapshot_digest(snap)
    if got != expect_digest:
        raise FetchRefused(f"snapshot digest {got} ≠ 승인된 {expect_digest}")
    n = len(targets(snap))
    if n > MAX_TARGETS:
        raise FetchRefused(f"대상 {n}종 > 승인 범위 {MAX_TARGETS}종")
    done = existing_copies(got)
    if done:
        raise FetchRefused(
            f"같은 snapshot 의 사본이 이미 있음 {done}"
            " — 다시 조회하지 않고 `compare --copy-dir` 로 대조만"
        )


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def library_versions() -> dict[str, Optional[str]]:
    out: dict[str, Optional[str]] = {}
    for dist in ("finance-datareader", "pandas", "requests"):
        try:
            out[dist] = metadata.version(dist)
        except metadata.PackageNotFoundError:
            out[dist] = None
    return out


def targets(snap: dict[str, Any]) -> list[tuple[str, Optional[str]]]:
    """(ticker, 요청 시작일) — snapshot 의 ETF 목록 그대로 · 시작일 = 그 종목 첫 저장일(없으면 None)."""
    return [
        (t, (e["rows"][0][0] if e["rows"] else None))
        for t, e in sorted(snap["etfs"].items())
    ]


def fetch_batch(
    snap: dict[str, Any], *, fetcher: Optional[Fetcher] = None
) -> dict[str, Any]:
    """한 묶음 조회 — 종목마다 한 번. 실패는 그 종목 기록으로 남기고 다음 종목으로(재시도 0)."""
    fetch = fetcher or fdr_mod._default_price_fetcher
    T = snap["T"]
    end = date.fromisoformat(T)
    log: list[dict[str, Any]] = []
    rows: dict[str, list] = {}
    started = _utc()
    for t, start in targets(snap):
        entry: dict[str, Any] = {
            "ticker": t,
            "requested_start": start,
            "requested_end": T,
            "started_at": None,
            "finished_at": None,
            "status": None,
            "error": None,
            "timeout": False,
            "rows": 0,
            "returned_first": None,
            "returned_last": None,
            "rows_after_T": 0,
            "source": SOURCE,
        }
        if start is None:
            entry["status"] = NO_STORED
            log.append(entry)
            continue
        entry["started_at"] = _utc()
        try:
            with fdr_request_timeout():
                df = fetch(t, date.fromisoformat(start), end)
        except Exception as e:  # noqa: BLE001 — 종목 단위 실패 기록(재시도 없음)
            entry.update(
                status=FAILED,
                error=f"{type(e).__name__}: {e}"[:200],
                timeout=fdr_mod._is_request_timeout(e),
                finished_at=_utc(),
            )
            log.append(entry)
            continue
        try:  # 변환 오류도 그 종목 실패로(묶음 전체를 멈추지 않음 · 검토 LOW-1)
            got = fdr_mod._dataframe_to_price_rows(t, df)
        except Exception as e:  # noqa: BLE001
            entry.update(
                status=FAILED,
                error=f"convert: {type(e).__name__}: {e}"[:200],
                finished_at=_utc(),
            )
            log.append(entry)
            continue
        entry["finished_at"] = _utc()
        if not got:
            entry["status"] = NO_DATA
            log.append(entry)
            continue
        entry.update(
            status=OK,
            rows=len(got),
            returned_first=got[0].date,
            returned_last=got[-1].date,
            rows_after_T=sum(1 for r in got if r.date > T),
        )
        rows[t] = [(r, entry["finished_at"]) for r in got]
        log.append(entry)
    return {
        "started_at": started,
        "finished_at": _utc(),
        "T": T,
        "libraries": library_versions(),
        "log": log,
        "rows": rows,
    }


_DDL = (
    "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE fetch_log (ticker TEXT PRIMARY KEY, body TEXT NOT NULL)",
    "CREATE TABLE prices (ticker TEXT NOT NULL, date TEXT NOT NULL, open REAL, high REAL,"
    " low REAL, close REAL, volume INTEGER, change REAL, source TEXT NOT NULL,"
    " fetched_at TEXT NOT NULL, PRIMARY KEY (ticker, date))",
)


def _write_db(path: Path, meta: dict[str, Any], batch: dict[str, Any]) -> None:
    con = sqlite3.connect(path)
    try:
        for ddl in _DDL:
            con.execute(ddl)
        con.executemany(
            "INSERT INTO meta VALUES (?, ?)",
            [(k, json.dumps(v, ensure_ascii=False)) for k, v in meta.items()],
        )
        con.executemany(
            "INSERT INTO fetch_log VALUES (?, ?)",
            [(e["ticker"], json.dumps(e, ensure_ascii=False)) for e in batch["log"]],
        )
        con.executemany(
            "INSERT INTO prices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (t, r.date, r.open, r.high, r.low, r.close, r.volume, r.change)
                + (SOURCE, at)
                for t, got in batch["rows"].items()
                for r, at in got
            ],
        )
        con.commit()
    finally:
        con.close()


def write_copy(
    snap: dict[str, Any], snapshot_path: Path, batch: dict[str, Any]
) -> Path:
    created = datetime.now(_KST)
    name = f"{created.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    root = Path(RESEARCH_ROOT)
    folder, staging = root / name, root / f".{name}.partial"
    meta = {
        "schema": SCHEMA,
        "copy_id": name,
        "created_at": created.isoformat(timespec="seconds"),
        "snapshot_path": str(snapshot_path),
        "snapshot_digest": snapshot_digest(snap),
        "T": batch["T"],
        "batch_started_at": batch["started_at"],
        "batch_finished_at": batch["finished_at"],
        "libraries": batch["libraries"],
        "source": SOURCE,
        "targets": len(batch["log"]),
    }
    made = False
    try:
        root.mkdir(parents=True, exist_ok=True)
        staging.mkdir(exist_ok=False)
        made = True
        _write_db(staging / "copy.sqlite", meta, batch)
        summary = {**meta, "log": batch["log"]}
        (staging / "fetch.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        os.rename(staging, folder)
    except (OSError, sqlite3.Error) as e:
        if made:
            shutil.rmtree(staging, ignore_errors=True)
        raise CopySaveError(f"연구 사본 저장 실패: {type(e).__name__}") from e
    return folder
