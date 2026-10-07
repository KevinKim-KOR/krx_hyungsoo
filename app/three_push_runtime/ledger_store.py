"""POC5-01B — 운영 의사결정 이벤트 원장 저장소(OCI 전용 SQLite · stdlib 만).

설계서 `docs/ai_design/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md` §4 ·
PLAN `docs/ai_plan/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_PLAN_V1.md` §1-6 · §1-7.

```text
경로        state/decision/decision_evidence.sqlite (POC5-00 승인 경로 · 호출 때 해석 · 테스트가 바꿔 끼운다)
테이블      evaluation_run · signal_item · delivery · ledger_meta (미래 단계 테이블 0)
권한        폴더 0700 · DB 0600 — 만들거나 확인하지 못하면 `LedgerUnavailable`(그 실행은 원장 쓰기 중단)
트랜잭션    시작 = STARTED INSERT 1문 · 종료 = BEGIN IMMEDIATE → 직전 평가 읽기 → item · delivery INSERT
            → run FINALIZED 1회 갱신(rowcount 1) → COMMIT. item · delivery 를 고치는 경로는 없다
연결        timeout 5초 · busy_timeout 5000 · WAL · 재시도 · 큐 · daemon 없음
```

PC 결정 세션 저장소(`app.decision_evidence_store`)는 import 하지 않는다 — 원장 경로가 PC 테이블
DDL 을 돌리지 않게 하기 위해서다.
"""

from __future__ import annotations

import os
import sqlite3
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

DEFAULT_DB_PATH = Path("state/decision/decision_evidence.sqlite")
SCHEMA_VERSION = "decision_ledger.v1"
DIR_MODE = 0o700
FILE_MODE = 0o600
BUSY_TIMEOUT_MS = 5000

RUN_STARTED = "STARTED"
RUN_FINALIZED = "FINALIZED"

_RUN_COLUMNS = (
    "event_id",
    "run_state",
    "push_kind",
    "contract_version",
    "slot_id",
    "tick",
    "runtime_kst",
    "runtime_date_kst",
    "input_basis_date",
    "mode",
    "status",
    "reason",
    "error",
    "started_at",
    "finished_at",
    "run_id",
    "param_id",
    "config_version_id",
    "off_schedule",
    "schedule_expected",
    "cohort",
    "tags_json",
)
_ITEM_COLUMNS = (
    "event_id",
    "item_seq",
    "subject_kind",
    "subject_id",
    "held",
    "state",
    "prev_state",
    "disposition",
    "event_type",
    "exposure",
    "values_json",
    "t0_price",
    "t0_price_asof",
    "evaluable",
)
_DELIVERY_COLUMNS = (
    "event_id",
    "delivery_status",
    "telegram_sent",
    "planned_chunk_count",
    "body_text",
    "body_sha256",
    "body_withheld",
)

DDL = (
    """
    CREATE TABLE IF NOT EXISTS evaluation_run (
        event_id TEXT PRIMARY KEY,
        run_state TEXT NOT NULL,
        push_kind TEXT NOT NULL,
        contract_version TEXT,
        slot_id TEXT,
        tick TEXT,
        runtime_kst TEXT,
        runtime_date_kst TEXT,
        input_basis_date TEXT,
        mode TEXT,
        status TEXT,
        reason TEXT,
        error TEXT,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        run_id INTEGER,
        param_id TEXT,
        config_version_id TEXT,
        off_schedule INTEGER NOT NULL DEFAULT 0,
        schedule_expected TEXT,
        cohort TEXT,
        tags_json TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_evaluation_run_kind_started"
    " ON evaluation_run (push_kind, started_at)",
    "CREATE INDEX IF NOT EXISTS idx_evaluation_run_state ON evaluation_run (run_state)",
    """
    CREATE TABLE IF NOT EXISTS signal_item (
        event_id TEXT NOT NULL,
        item_seq INTEGER NOT NULL,
        subject_kind TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        held INTEGER,
        state TEXT,
        prev_state TEXT,
        disposition TEXT NOT NULL,
        event_type TEXT,
        exposure TEXT,
        values_json TEXT,
        t0_price REAL,
        t0_price_asof TEXT,
        evaluable INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY (event_id, item_seq)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_signal_item_subject"
    " ON signal_item (subject_kind, subject_id)",
    """
    CREATE TABLE IF NOT EXISTS delivery (
        event_id TEXT PRIMARY KEY,
        delivery_status TEXT NOT NULL,
        telegram_sent INTEGER,
        planned_chunk_count INTEGER,
        body_text TEXT,
        body_sha256 TEXT,
        body_withheld INTEGER NOT NULL DEFAULT 0
    )""",
    """
    CREATE TABLE IF NOT EXISTS ledger_meta (
        key TEXT PRIMARY KEY,
        value TEXT,
        recorded_at TEXT NOT NULL
    )""",
)

_INITIALIZED: set[str] = set()


class LedgerUnavailable(Exception):
    """원장을 안전하게 쓸 수 없다(권한 · 초기화 실패). 그 실행은 원장 쓰기를 멈춘다."""


def _db_path() -> Path:
    # 호출 때 모듈 전역을 읽는다 — conftest 가 이 상수 하나만 바꿔 끼운다.
    return DEFAULT_DB_PATH


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


def _secure(path: Path, mode: int) -> None:
    """권한을 맞추고 다시 확인한다. 안 되면 `LedgerUnavailable`(설계자 보정 1)."""
    try:
        if _mode(path) != mode:
            os.chmod(path, mode)
        actual = _mode(path)
    except OSError as e:
        raise LedgerUnavailable(f"chmod:{type(e).__name__}") from e
    if actual != mode:
        raise LedgerUnavailable(f"mode:{oct(actual)}")


def connect(path: Optional[Path] = None) -> sqlite3.Connection:
    """권한을 확인한 연결. 처음이면 폴더 · DB 를 만들고 스키마 · WAL 을 건다."""
    p = Path(path) if path is not None else _db_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise LedgerUnavailable(f"mkdir:{type(e).__name__}") from e
    _secure(p.parent, DIR_MODE)
    try:
        con = sqlite3.connect(str(p), timeout=BUSY_TIMEOUT_MS / 1000)
    except sqlite3.Error as e:
        raise LedgerUnavailable(f"connect:{type(e).__name__}") from e
    try:
        _secure(p, FILE_MODE)
        con.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        key = str(p.resolve())
        if key not in _INITIALIZED:
            con.execute("PRAGMA journal_mode = WAL")
            for stmt in DDL:
                con.execute(stmt)
            con.commit()
            _INITIALIZED.add(key)
    except Exception:
        con.close()
        raise
    return con


def reset_init_cache_for_testing() -> None:
    _INITIALIZED.clear()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── meta ─────────────────────────────────────────────────────────────────────


def meta_get(con: sqlite3.Connection, key: str) -> Optional[str]:
    row = con.execute("SELECT value FROM ledger_meta WHERE key = ?", (key,)).fetchone()
    return None if row is None else row[0]


def meta_put_once(con: sqlite3.Connection, key: str, value: str) -> bool:
    """처음 한 번만 쓴다(INSERT OR IGNORE · 행 수정 0). 새로 썼으면 True."""
    with con:
        cur = con.execute(
            "INSERT OR IGNORE INTO ledger_meta (key, value, recorded_at) VALUES (?, ?, ?)",
            (key, value, now_utc()),
        )
    return cur.rowcount > 0


# ── run ──────────────────────────────────────────────────────────────────────


def insert_started(con: sqlite3.Connection, run: dict[str, Any]) -> None:
    row = {c: run.get(c) for c in _RUN_COLUMNS}
    row["run_state"] = RUN_STARTED
    cols = ", ".join(_RUN_COLUMNS)
    marks = ", ".join("?" for _ in _RUN_COLUMNS)
    with con:
        con.execute(
            f"INSERT INTO evaluation_run ({cols}) VALUES ({marks})",
            tuple(row[c] for c in _RUN_COLUMNS),
        )


_FINAL_FIELDS = (
    "contract_version",
    "slot_id",
    "tick",
    "input_basis_date",
    "status",
    "reason",
    "error",
    "finished_at",
    "run_id",
    "param_id",
    "config_version_id",
    "off_schedule",
    "schedule_expected",
    "cohort",
    "tags_json",
)


def finalize(
    con: sqlite3.Connection,
    event_id: str,
    run: dict[str, Any],
    items_fn: Any,
    delivery: Optional[dict[str, Any]],
) -> None:
    """종료 확정 1회 — 한 트랜잭션. `items_fn(con)` 은 같은 트랜잭션 안에서 직전 평가를 읽고
    item 행 목록을 돌려준다. 이미 확정된 run 이면 롤백하고 `LedgerUnavailable`."""
    con.execute("BEGIN IMMEDIATE")
    try:
        state = con.execute(
            "SELECT run_state FROM evaluation_run WHERE event_id = ?", (event_id,)
        ).fetchone()
        if state is None or state[0] != RUN_STARTED:
            raise LedgerUnavailable("finalize:not_started")  # 종료 확정은 1회만
        items = list(items_fn(con) or [])
        if items:
            cols = ", ".join(_ITEM_COLUMNS)
            marks = ", ".join("?" for _ in _ITEM_COLUMNS)
            for it in items:
                it["evaluable"] = int(it.get("evaluable", 1))
            con.executemany(
                f"INSERT INTO signal_item ({cols}) VALUES ({marks})",
                [
                    tuple(
                        (
                            event_id
                            if c == "event_id"
                            else (seq if c == "item_seq" else it.get(c))
                        )
                        for c in _ITEM_COLUMNS
                    )
                    for seq, it in enumerate(items, start=1)
                ],
            )
        if delivery is not None:
            row = {"body_withheld": 0, **delivery, "event_id": event_id}
            row["body_withheld"] = int(row.get("body_withheld") or 0)
            cols = ", ".join(_DELIVERY_COLUMNS)
            marks = ", ".join("?" for _ in _DELIVERY_COLUMNS)
            con.execute(
                f"INSERT INTO delivery ({cols}) VALUES ({marks})",
                tuple(row.get(c) for c in _DELIVERY_COLUMNS),
            )
        fields = [c for c in _FINAL_FIELDS if c in run]  # 넘겨받은 값만(시작 값 보존)
        sets = "".join(f", {c} = ?" for c in fields)
        cur = con.execute(
            f"UPDATE evaluation_run SET run_state = ?{sets}"
            " WHERE event_id = ? AND run_state = ?",
            (RUN_FINALIZED, *(run[c] for c in fields), event_id, RUN_STARTED),
        )
        if cur.rowcount != 1:
            raise LedgerUnavailable("finalize:not_started")
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise


# ── 직전 평가(원장 자기 행 · 설계자 Q-C · Q-D 승인) ───────────────────────────


def previous_item(
    con: sqlite3.Connection,
    *,
    push_kind: str,
    subject_kind: str,
    subject_id: str,
) -> Optional[tuple[Optional[str], str]]:
    """같은 kind · subject 의 가장 최근 확정 · 예정 회차 · **평가된** item `(state, runtime_date_kst)`.

    평가 불가 행(`evaluable = 0` — 자료없음 · 보유 제외 사업군 · 급등 미평가)은 건너뛴다 —
    코드의 UNEVALUABLE 규칙(직전 관측 유지)과 같다.
    """
    row = con.execute(
        "SELECT i.state, r.runtime_date_kst FROM signal_item i"
        " JOIN evaluation_run r ON r.event_id = i.event_id"
        " WHERE r.push_kind = ? AND r.run_state = ? AND r.off_schedule = 0"
        " AND i.subject_kind = ? AND i.subject_id = ? AND i.evaluable = 1"
        " ORDER BY r.started_at DESC, i.item_seq DESC LIMIT 1",
        (push_kind, RUN_FINALIZED, subject_kind, subject_id),
    ).fetchone()
    return None if row is None else (row[0], row[1])


def ever_active(
    con: sqlite3.Connection, *, push_kind: str, subject_kind: str, subject_id: str
) -> bool:
    """예정 회차에서 그 subject 가 활성 state 로 관측된 적이 있는가(회복 뒤 재진입 판정)."""
    row = con.execute(
        "SELECT 1 FROM signal_item i JOIN evaluation_run r ON r.event_id = i.event_id"
        " WHERE r.push_kind = ? AND r.run_state = ? AND r.off_schedule = 0"
        " AND i.subject_kind = ? AND i.subject_id = ? AND i.event_type IS NOT NULL"
        " LIMIT 1",
        (push_kind, RUN_FINALIZED, subject_kind, subject_id),
    ).fetchone()
    return row is not None


def primary_today(
    con: sqlite3.Connection,
    *,
    push_kind: str,
    subject_kind: str,
    subject_id: str,
    state: str,
    runtime_date_kst: str,
) -> bool:
    """같은 KST 날짜 · subject · state 가 예정 회차에서 이미 PRIMARY 였는가(Q29 · Q-D)."""
    row = con.execute(
        "SELECT 1 FROM signal_item i JOIN evaluation_run r ON r.event_id = i.event_id"
        " WHERE r.push_kind = ? AND r.run_state = ? AND r.off_schedule = 0"
        " AND r.runtime_date_kst = ? AND i.subject_kind = ? AND i.subject_id = ?"
        " AND i.state = ? AND i.exposure = 'PRIMARY' LIMIT 1",
        (push_kind, RUN_FINALIZED, runtime_date_kst, subject_kind, subject_id, state),
    ).fetchone()
    return row is not None


def previous_run_value(
    con: sqlite3.Connection,
    *,
    push_kind: str,
    subject_kind: str,
    subject_id: str,
) -> Optional[str]:
    """같은 kind · subject 의 직전 확정 · 예정 회차 item `values_json`(시장 태그용)."""
    row = con.execute(
        "SELECT i.values_json FROM signal_item i"
        " JOIN evaluation_run r ON r.event_id = i.event_id"
        " WHERE r.push_kind = ? AND r.run_state = ? AND r.off_schedule = 0"
        " AND i.subject_kind = ? AND i.subject_id = ?"
        " ORDER BY r.started_at DESC LIMIT 1",
        (push_kind, RUN_FINALIZED, subject_kind, subject_id),
    ).fetchone()
    return None if row is None else row[0]


# ── 읽기 전용 대조(설계서 §7 · PLAN §2-6) ──────────────────────────────────────


def _ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True, timeout=5.0)


def reconcile(
    ledger_path: Path,
    runtime_path: Path,
    *,
    kinds: Iterable[str],
) -> dict[str, Any]:
    """원장 run · 기존 `runtime_execution_status` · STARTED 잔류를 비교한다(읽기 전용).

    대상 runtime 행 = mode='send' · 운영 kind · started_at ≥ 원장 첫 활성 시각. 키는
    `(push_kind, started_at)` 이다. 결과는 분류별 건수와 ID 뿐이다(자동 수정 0).
    """
    kinds = tuple(kinds)
    marks = ", ".join("?" for _ in kinds)
    led = _ro(ledger_path)
    try:
        floor_row = led.execute(
            "SELECT value FROM ledger_meta WHERE key = 'first_active_at'"
        ).fetchone()
        floor = floor_row[0] if floor_row else None
        if floor is None:
            m = led.execute("SELECT MIN(started_at) FROM evaluation_run").fetchone()
            floor = m[0] if m else None
        runs = led.execute(
            "SELECT event_id, push_kind, started_at, run_state, run_id FROM evaluation_run"
            f" WHERE push_kind IN ({marks})",
            kinds,
        ).fetchall()
    finally:
        led.close()
    rt_rows: list[tuple] = []
    if floor is not None:
        rt = _ro(runtime_path)
        try:
            rt_rows = rt.execute(
                "SELECT run_id, push_kind, started_at FROM runtime_execution_status"
                f" WHERE mode = 'send' AND push_kind IN ({marks}) AND started_at >= ?",
                (*kinds, floor),
            ).fetchall()
        finally:
            rt.close()
    by_key = {(r[1], r[2]): r for r in runs}
    rt_keys = {(r[1], r[2]): r for r in rt_rows}
    ok, gap, orphan = [], [], []
    for key, r in by_key.items():
        if r[3] != RUN_FINALIZED:
            gap.append(r[0])
        elif key in rt_keys:
            ok.append(r[0])
        else:
            orphan.append(r[0])
    missing = [r[0] for key, r in rt_keys.items() if key not in by_key]
    return {
        "floor": floor,
        "ok": {"count": len(ok), "ids": sorted(ok)},
        "missing_in_ledger": {"count": len(missing), "ids": sorted(missing)},
        "started_gap": {"count": len(gap), "ids": sorted(gap)},
        "ledger_only": {"count": len(orphan), "ids": sorted(orphan)},
    }


__all__ = [
    "DEFAULT_DB_PATH",
    "DIR_MODE",
    "FILE_MODE",
    "RUN_FINALIZED",
    "RUN_STARTED",
    "SCHEMA_VERSION",
    "LedgerUnavailable",
    "connect",
    "ever_active",
    "finalize",
    "insert_started",
    "meta_get",
    "meta_put_once",
    "previous_item",
    "previous_run_value",
    "primary_today",
    "reconcile",
    "reset_init_cache_for_testing",
]
