"""POC4-01 — ML baseline 불변 입력 스냅샷 (설계자 결정 1 — 2026-09-23).

기존 145일 baseline 은 평가기가 라이브 DB 를 직접 읽어서 재현되지 않았다
(`ROOT_CAUSE = MUTABLE_INPUT_DATA`). 본 모듈은 평가 입력을 한 번 동결해 sha256 으로
봉인하고, 평가기가 그 봉인된 사본만 읽도록 강제한다.

- `build_snapshot`  라이브 DB 를 **읽기 전용**으로 열어 평가 입력 3개 테이블
  (가격은 cutoff 이하)과 E1 비교용 점수 JSON 을 새 bundle 에 복사하고 manifest 를
  쓴다. 이미 있는 bundle 은 덮어쓰지 않는다.
- `verify_snapshot` manifest 가 없거나, 파일이 없거나, sha256 이 다르면 즉시 실패.
- `snapshot_session` 검증 → 작업 사본 생성 → 허용 경로 외 sqlite 접속 차단.

작업 사본을 쓰는 이유: 운영 조회 함수(`market_data_store._connection`)는 처음 여는
DB 에 `CREATE TABLE IF NOT EXISTS` 를 쓴다. 봉인 파일을 직접 열면 그 쓰기가 봉인을
깬다. 그래서 봉인 파일은 hash 확인용으로만 읽고, 평가는 hash 가 같은 사본에서 한다.

하지 않는 것 — 라이브 DB 쓰기 / OCI / 외부 API / 기존 bundle 덮어쓰기.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

SNAPSHOT_TABLES = ("etf_master", "etf_daily_price", "market_refresh_log")
DATE_FILTERED_TABLE = "etf_daily_price"
DATASET_FILENAME = "dataset.sqlite"
E1_FILENAME = "e1_score_snapshot.json"
MANIFEST_FILENAME = "dataset_manifest.json"
WORKING_COPY_NAME = "_work_dataset.sqlite"
WORKING_E1_NAME = "_work_e1_score_snapshot.json"
# 테이블별 최소일·최대일을 잴 날짜 컬럼 (설계자 결정 1 — 테이블별 최소일·최대일).
DATE_COLUMNS = {
    "etf_daily_price": "date",
    "market_refresh_log": "asof",
    "etf_master": "last_seen_at",
}
MANIFEST_SCHEMA = "ml_baseline_dataset_manifest.v1"
_READ_ONLY = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH


class SnapshotIntegrityError(RuntimeError):
    """스냅샷 누락·hash 불일치·cutoff 불일치 — 평가를 시작하지 않는다."""


class SnapshotGuardError(RuntimeError):
    """스냅샷 모드에서 허용되지 않은 DB(예: 라이브 DB) 접속 시도."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_manifest_sha256(manifest: dict) -> str:
    """manifest 내용의 hash — 줄바꿈·들여쓰기 같은 파일 바이트 차이와 무관하다."""
    text = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SnapshotSession:
    manifest: dict
    manifest_path: Path
    manifest_sha256: str
    manifest_canonical_sha256: str
    work_db: Path
    e1_path: Path
    cutoff: str

    def reverify(self) -> None:
        """결과를 쓰기 **직전**에 부른다 — 봉인 원본이 세션 시작 때와 같은지."""
        if (
            not self.manifest_path.is_file()
            or file_sha256(self.manifest_path) != self.manifest_sha256
        ):
            raise SnapshotIntegrityError("실행 중 snapshot manifest 가 바뀌었다")
        verify_snapshot(self.manifest_path)


# --- 통계 · hash --------------------------------------------------------------


def _order_by(con: sqlite3.Connection, table: str) -> str:
    """PK 순서로 정렬 — 없으면 전체 컬럼 순서. content hash 가 저장 순서와 무관해진다."""
    info = list(con.execute(f"PRAGMA table_info({table})"))
    pk = [r[1] for r in sorted(info, key=lambda r: r[5]) if r[5] > 0]
    return ", ".join(pk or [r[1] for r in info])


def table_stats(con: sqlite3.Connection, table: str, schema: str = "main") -> dict:
    cols = [r[1] for r in con.execute(f"PRAGMA {schema}.table_info({table})")]
    stats: dict = {
        "rows": con.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchone()[0]
    }
    if "ticker" in cols:
        stats["tickers"] = con.execute(
            f"SELECT COUNT(DISTINCT ticker) FROM {schema}.{table}"
        ).fetchone()[0]
    date_col = DATE_COLUMNS.get(table)
    if date_col in cols:
        lo, hi = con.execute(
            f"SELECT MIN({date_col}), MAX({date_col}) FROM {schema}.{table}"
        ).fetchone()
        stats["date_column"] = date_col
        stats["min_date"], stats["max_date"] = lo, hi
    return stats


def content_sha256(con: sqlite3.Connection, table: str) -> str:
    """행 내용의 canonical sha256 (PK 정렬 · JSON 직렬화). 파일 배치와 무관."""
    digest = hashlib.sha256()
    for row in con.execute(f"SELECT * FROM {table} ORDER BY {_order_by(con, table)}"):
        digest.update(
            json.dumps(list(row), ensure_ascii=False, separators=(",", ":")).encode()
        )
        digest.update(b"\n")
    return digest.hexdigest()


def schema_sha256(con: sqlite3.Connection) -> str:
    rows = con.execute(
        "SELECT type, name, tbl_name, COALESCE(sql, '') FROM sqlite_master "
        "ORDER BY type, name"
    ).fetchall()
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()


# --- 생성 --------------------------------------------------------------------


def _copy_tables(dataset: Path, live_db_path: Path, cutoff: str) -> dict:
    """한 읽기 트랜잭션 안에서 복사한다 — 복사 중 라이브 DB 가 바뀌어도 섞이지 않는다."""
    con = sqlite3.connect(f"file:{dataset}", uri=True, isolation_level=None)
    try:
        con.execute(
            "ATTACH DATABASE ? AS src", (f"file:{live_db_path.resolve()}?mode=ro",)
        )
        con.execute("BEGIN")
        live = {t: table_stats(con, t, schema="src") for t in SNAPSHOT_TABLES}
        for table in SNAPSHOT_TABLES:
            ddl = con.execute(
                "SELECT sql FROM src.sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if not ddl:
                raise SnapshotIntegrityError(f"라이브 DB 에 {table} 테이블이 없다")
            con.execute(ddl[0])
            where = " WHERE date <= ?" if table == DATE_FILTERED_TABLE else ""
            params = (cutoff,) if where else ()
            order = _order_by(con, table)
            con.execute(
                f"INSERT INTO main.{table} SELECT * FROM src.{table}{where} "
                f"ORDER BY {order}",
                params,
            )
        con.execute("COMMIT")
        con.execute("DETACH DATABASE src")
    finally:
        con.close()
    return live


def _evaluation_calendar(dataset: Path, scratch: Path) -> dict:
    """스냅샷에서 E2 평가일 목록을 미리 계산해 manifest 에 고정한다.

    운영 조회 함수를 그대로 쓰기 위해 scratch 사본에서 계산한다(봉인 파일 보호).
    """
    from app.market_data_store import fetch_price_history
    from app.ml_relative_upside_features import KODEX200_TICKER
    from app.ml_score_validity_eval import (
        PHASE_EVALUATION,
        build_calendar,
        classify_phase,
    )

    shutil.copyfile(dataset, scratch)
    try:
        days = [d for d, _ in fetch_price_history(KODEX200_TICKER, db_path=scratch)]
    finally:
        scratch.unlink(missing_ok=True)
    points = build_calendar(days, months_ahead=1)
    e2 = [
        p.signal_date
        for p in points
        if classify_phase(p.signal_date) == PHASE_EVALUATION
    ]
    warmup = [p.signal_date for p in points if p.signal_date not in e2]
    return {
        "basis": "KODEX200 유효 종가일 · build_calendar(months_ahead=1)",
        "e2_dates": e2,
        "e2_count": len(e2),
        "warmup_dates": warmup,
        "trading_days": len(days),
        "first_trading_day": days[0] if days else None,
        "last_trading_day": days[-1] if days else None,
    }


def build_snapshot(
    *,
    live_db_path: Path,
    e1_source_path: Path,
    bundle_dir: Path,
    cutoff: str,
    baseline_id: str,
) -> dict:
    """새 bundle 을 만든다. 같은 경로가 이미 있으면 실패 — 덮어쓰지 않는다."""
    datetime.strptime(cutoff, "%Y-%m-%d")
    if bundle_dir.exists():
        raise SnapshotIntegrityError(
            f"bundle 이 이미 있다 — 덮어쓰지 않는다: {bundle_dir}"
        )
    for src in (live_db_path, e1_source_path):
        if not src.exists():
            raise SnapshotIntegrityError(f"입력 파일이 없다: {src}")
    building = bundle_dir.with_name(bundle_dir.name + ".building")
    building.mkdir(parents=True, exist_ok=False)
    dataset = building / DATASET_FILENAME
    e1_copy = building / E1_FILENAME
    written = [dataset, e1_copy, building / MANIFEST_FILENAME]
    try:
        live = _copy_tables(dataset, live_db_path, cutoff)
        shutil.copyfile(e1_source_path, e1_copy)
        con = sqlite3.connect(f"file:{dataset}?mode=ro", uri=True)
        try:
            tables = {
                t: {**table_stats(con, t), "content_sha256": content_sha256(con, t)}
                for t in SNAPSHOT_TABLES
            }
            schema = schema_sha256(con)
        finally:
            con.close()
        max_date = tables[DATE_FILTERED_TABLE].get("max_date")
        if not max_date or max_date > cutoff:
            raise SnapshotIntegrityError(f"cutoff 위반: max_date={max_date}")
        e1 = json.loads(e1_copy.read_text(encoding="utf-8"))
        manifest = {
            "schema_version": MANIFEST_SCHEMA,
            "baseline_id": baseline_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "data_cutoff": cutoff,
            "source": {
                "live_db_path": str(live_db_path),
                "live_db_stats_at_snapshot": live,
                "e1_source_path": str(e1_source_path),
            },
            "files": {
                "dataset": {"path": DATASET_FILENAME, "sha256": file_sha256(dataset)},
                "e1_score_snapshot": {
                    "path": E1_FILENAME,
                    "sha256": file_sha256(e1_copy),
                    "asof_date": e1.get("asof_date"),
                    "generated_at": e1.get("generated_at"),
                    "candidates": len(e1.get("candidates") or []),
                },
            },
            "tables": tables,
            "schema_sha256": schema,
            "evaluation_calendar": _evaluation_calendar(
                dataset, building / WORKING_COPY_NAME
            ),
        }
        (building / MANIFEST_FILENAME).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
            newline="\n",
        )
        for path in written:
            os.chmod(path, _READ_ONLY)
        building.rename(bundle_dir)
    except BaseException:
        # 이번 호출이 방금 만든 임시 폴더의 파일만 정리한다.
        for path in building.iterdir():
            os.chmod(path, stat.S_IWUSR | stat.S_IRUSR)
            path.unlink()
        building.rmdir()
        raise
    return manifest


# --- 검증 · 세션 -------------------------------------------------------------


def verify_snapshot(manifest_path: Path) -> dict:
    """manifest·파일 누락 또는 sha256 불일치면 `SnapshotIntegrityError`."""
    if not manifest_path.is_file():
        raise SnapshotIntegrityError(f"snapshot manifest 가 없다: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise SnapshotIntegrityError(
            f"manifest schema 불일치: {manifest.get('schema_version')}"
        )
    for key in ("dataset", "e1_score_snapshot"):
        entry = (manifest.get("files") or {}).get(key) or {}
        path = manifest_path.parent / str(entry.get("path") or "")
        if not entry.get("path") or not path.is_file():
            raise SnapshotIntegrityError(f"snapshot 파일이 없다: {key} ({path})")
        actual = file_sha256(path)
        if actual != entry.get("sha256"):
            raise SnapshotIntegrityError(
                f"snapshot hash 불일치: {key} 기대 {entry.get('sha256')} 실제 {actual}"
            )
    return manifest


def _under_alias(path: Path, root: Path) -> bool:
    """대소문자·firmlink 같은 별칭 경로로 root 아래를 가리키는지 (있는 조상을 samefile 로 비교)."""
    if not root.exists():
        return False
    for ancestor in (path, *path.parents):
        if ancestor.exists() and os.path.samefile(ancestor, root):
            return True
    return False


def new_run_dir(out_dir: Path, *, forbidden_root: Path) -> Path:
    """실행마다 **새 폴더** (검증자 P1 — 산출물 보호).

    이미 있는 폴더를 받으면 고정 파일명으로 이전 결과를 덮어쓰거나, 실패한 실행에서
    이전 결과가 남아 새 결과처럼 보일 수 있다. legacy 결과 폴더와 그 하위는 금지한다.
    """
    out, root = out_dir.resolve(), forbidden_root.resolve()
    if out == root or out.is_relative_to(root) or _under_alias(out, root):
        raise SnapshotIntegrityError("기존(legacy) 결과 폴더와 그 하위에는 쓰지 않는다")
    if out.exists():
        raise SnapshotIntegrityError(
            f"--out-dir 가 이미 있다 — 실행마다 새 폴더: {out}"
        )
    return out


def _path_key(database: object) -> str:
    text = os.fspath(database) if isinstance(database, os.PathLike) else str(database)
    if text.startswith("file:"):
        text = text[len("file:") :].split("?", 1)[0]  # noqa: E203
    return os.path.realpath(text)


@contextmanager
def guard_sqlite_paths(allowed: Iterable[Path]) -> Iterator[None]:
    """블록 안에서 `sqlite3.connect` 를 허용 경로로만 제한한다 (라이브 DB 차단)."""
    allowed_keys = {_path_key(p) for p in allowed}
    real_connect = sqlite3.connect

    def _guarded(database, *args, **kwargs):
        if _path_key(database) not in allowed_keys:
            raise SnapshotGuardError(
                f"스냅샷 모드에서 허용되지 않은 DB 접속: {database}"
            )
        return real_connect(database, *args, **kwargs)

    sqlite3.connect = _guarded
    try:
        yield
    finally:
        sqlite3.connect = real_connect


@contextmanager
def snapshot_session(
    manifest_path: Path,
    *,
    cutoff: str,
    work_dir: Path,
    extra_allowed: Iterable[Path] = (),
) -> Iterator[SnapshotSession]:
    """검증된 스냅샷의 작업 사본으로만 평가하게 한다."""
    manifest = verify_snapshot(manifest_path)
    if cutoff != manifest.get("data_cutoff"):
        raise SnapshotIntegrityError(
            f"cutoff 불일치: 인자 {cutoff} · manifest {manifest.get('data_cutoff')}"
        )
    manifest_sha256 = file_sha256(manifest_path)
    bundle = manifest_path.parent
    copies = {
        "dataset": work_dir / WORKING_COPY_NAME,
        "e1_score_snapshot": work_dir / WORKING_E1_NAME,
    }
    try:
        # 평가 중에는 봉인 원본을 읽지 않는다 — hash 를 확인한 사본만 읽는다.
        for key, copy in copies.items():
            shutil.copyfile(bundle / manifest["files"][key]["path"], copy)
            os.chmod(copy, stat.S_IWUSR | stat.S_IRUSR)
            if file_sha256(copy) != manifest["files"][key]["sha256"]:
                raise SnapshotIntegrityError(
                    f"작업 사본 hash 가 snapshot 과 다르다: {key}"
                )
        session = SnapshotSession(
            manifest=manifest,
            manifest_path=manifest_path,
            manifest_sha256=manifest_sha256,
            manifest_canonical_sha256=canonical_manifest_sha256(manifest),
            work_db=copies["dataset"],
            e1_path=copies["e1_score_snapshot"],
            cutoff=cutoff,
        )
        with guard_sqlite_paths([session.work_db, *extra_allowed]):
            yield session
    finally:
        for copy in copies.values():
            copy.unlink(missing_ok=True)
        Path(f"{copies['dataset']}-journal").unlink(missing_ok=True)
