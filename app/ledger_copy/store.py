"""POC5-03 — PC 원장 사본 · 피드백 · 동기화 기록 저장소(PC 기존 decision DB · stdlib 만).

PLAN `docs/ai_plan/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_PLAN_V1.md` §2-2 · §8.

```text
경로        state/decision/decision_evidence.sqlite (PC 기존 파일 · 호출 때 해석 · 테스트가 바꿔 끼운다)
사본 표      evaluation_run · signal_item · delivery · ledger_meta · price_outcome
            — OCI 원장 DDL 상수를 그대로 실행(스키마 · 의미 불변)
PC 전용 표   user_feedback(append-only · event 마다 feedback_seq 1, 2, …)
            ledger_sync_attempt(append-only · 시도마다 1행 · 마지막 성공 · 실패 시각)
연결        권한 · 저널 방식은 바꾸지 않는다(기존 PC 파일 그대로 · `ledger_store.connect()` 미사용)
반영        검증을 마친 export 만 받는다 · BEGIN IMMEDIATE 한 번 · 충돌이나 예외면 전체 ROLLBACK
            · 성공 기록(ledger_sync_attempt ok=1)도 같은 트랜잭션에서 남긴다
            · PC 사본에만 있는 행이 있으면 충돌(원격은 지우지 않는다 → 원장 손실 · 교체) — 지우지도
              덮지도 않고 전체 취소 · user_feedback 은 반영 대상이 아니다
갱신        evaluation_run 사본이 STARTED 이고 원격이 FINALIZED · 시작 열이 같을 때만(finalize 1회와 같음)
숨김        동기화 기록 · 응답의 표별 반영 수에 price_outcome 을 넣지 않는다(피드백 전 결과 존재 여부 비노출)
```
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from app.three_push_runtime import ledger_outcome
from app.three_push_runtime import ledger_store

DEFAULT_DB_PATH = Path("state/decision/decision_evidence.sqlite")
TIMEOUT_SEC = 5.0

TABLES = ("evaluation_run", "signal_item", "delivery", "ledger_meta", "price_outcome")
KEYS = {
    "evaluation_run": ("event_id",),
    "signal_item": ("event_id", "item_seq"),
    "delivery": ("event_id",),
    "ledger_meta": ("key",),
    "price_outcome": ("event_id", "item_seq", "series_id", "horizon"),
}

HELPFULNESS = ("HELPFUL", "NEUTRAL", "UNHELPFUL_CONFUSING")
ACTIONS = ("WATCH_ONLY", "BUY_OR_ADD", "SELL_OR_REDUCE", "OTHER")
MEMO_MAX_LEN = 500
FEEDBACK_DELIVERY = ("sent", "partial")

PC_DDL = (
    """
    CREATE TABLE IF NOT EXISTS user_feedback (
        event_id TEXT NOT NULL,
        feedback_seq INTEGER NOT NULL,
        helpfulness TEXT NOT NULL,
        action TEXT,
        memo TEXT,
        feedback_at TEXT NOT NULL,
        PRIMARY KEY (event_id, feedback_seq)
    )""",
    """
    CREATE TABLE IF NOT EXISTS ledger_sync_attempt (
        attempt_seq INTEGER PRIMARY KEY AUTOINCREMENT,
        attempted_at TEXT NOT NULL,
        ok INTEGER NOT NULL,
        failure_kind TEXT,
        counts_json TEXT
    )""",
)

_KST = timezone(timedelta(hours=9))


class SyncConflict(Exception):
    """export 행이 PC 사본의 확정 행과 다르다 — 그 동기화 전체를 취소한다."""


class FeedbackError(Exception):
    """feedback 거부. code = invalid(입력) · not_found(로컬에 없음) · not_target(sent · partial 아님)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _db_path() -> Path:
    # 호출 때 모듈 전역을 읽는다 — conftest 가 이 상수 하나만 바꿔 끼운다.
    return DEFAULT_DB_PATH


def now_kst() -> str:
    return datetime.now(_KST).isoformat(timespec="seconds")


def connect(path: Optional[Path] = None) -> sqlite3.Connection:
    """PC 사본 연결. 처음이면 사본 표 · PC 전용 표를 만든다(IF NOT EXISTS · 기존 표 불변)."""
    p = Path(path) if path is not None else _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), timeout=TIMEOUT_SEC)
    try:
        con.row_factory = sqlite3.Row
        for stmt in (*ledger_store.DDL, *ledger_outcome.DDL, *PC_DDL):
            con.execute(stmt)
        con.commit()
    except Exception:
        con.close()
        raise
    return con


def table_columns(con: sqlite3.Connection) -> dict[str, dict[str, tuple[str, bool]]]:
    """사본 표마다 {열: (선언 타입, NOT NULL 또는 PK)}. export 검증의 기준이다."""
    out: dict[str, dict[str, tuple[str, bool]]] = {}
    for t in TABLES:
        out[t] = {
            r["name"]: (str(r["type"]).upper(), bool(r["notnull"]) or bool(r["pk"]))
            for r in con.execute(f"PRAGMA table_info({t})")
        }
    return out


def public_counts(counts: dict[str, Any]) -> dict[str, Any]:
    """화면 · 기록에 남기는 반영 수 — price_outcome 은 뺀다(피드백 전 결과 존재 여부 비노출)."""
    return {t: c for t, c in counts.items() if t != "price_outcome"}


# ── 사본 반영 ────────────────────────────────────────────────────────────────


def _where(keys: Iterable[str]) -> str:
    return " AND ".join(f"{k} = ?" for k in keys)


def _apply_row(
    con: sqlite3.Connection, table: str, row: dict[str, Any], counts: dict[str, int]
) -> None:
    keys = KEYS[table]
    cols = list(row)
    cur = con.execute(
        f"SELECT {', '.join(cols)} FROM {table} WHERE {_where(keys)}",
        tuple(row[k] for k in keys),
    ).fetchone()
    if cur is None:
        con.execute(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            tuple(row[c] for c in cols),
        )
        counts["inserted"] += 1
        return
    same = all(cur[c] == row[c] for c in cols)
    if same:
        counts["unchanged"] += 1
        return
    # 원격에서 바뀌는 행은 evaluation_run 의 STARTED → FINALIZED 1회뿐이다(ledger_store.finalize).
    # 시작 때 쓴 열(_FINAL_FIELDS 밖)은 그대로여야 한다 — 아니면 충돌.
    if table == "evaluation_run":
        start_cols = [
            c for c in cols if c != "run_state" and c not in ledger_store._FINAL_FIELDS
        ]
        if (
            cur["run_state"] == ledger_store.RUN_STARTED
            and row["run_state"] == ledger_store.RUN_FINALIZED
            and all(cur[c] == row[c] for c in start_cols)
        ):
            sets = ", ".join(f"{c} = ?" for c in cols if c != "event_id")
            con.execute(
                f"UPDATE evaluation_run SET {sets} WHERE event_id = ?",
                (*(row[c] for c in cols if c != "event_id"), row["event_id"]),
            )
            counts["updated"] += 1
            return
    raise SyncConflict(table)


def _check_nothing_lost(
    con: sqlite3.Connection, rows: dict[str, list[dict[str, Any]]]
) -> None:
    """PC 사본의 모든 키가 export 에도 있어야 한다. 원격 원장은 행을 지우지 않으므로 빠진 키는
    원장 손실 · 교체다 — 빈 원장을 받아 정상으로 넘기지 않는다."""
    for t in TABLES:
        exported = {tuple(r[k] for k in KEYS[t]) for r in rows.get(t, ())}
        for local in con.execute(f"SELECT {', '.join(KEYS[t])} FROM {t}"):
            if tuple(local) not in exported:
                raise SyncConflict(t)


def apply_export(
    rows: dict[str, list[dict[str, Any]]],
    *,
    attempted_at: str,
    path: Optional[Path] = None,
) -> dict[str, dict[str, int]]:
    """검증을 마친 export 와 성공 기록을 한 트랜잭션으로 반영한다. 충돌 · 예외면 전체 ROLLBACK.

    반환 = 표별 반영 수(price_outcome 제외 · `public_counts`)."""
    con = connect(path)
    try:
        con.execute("BEGIN IMMEDIATE")
        _check_nothing_lost(con, rows)
        out: dict[str, dict[str, int]] = {}
        for t in TABLES:
            counts = {"inserted": 0, "updated": 0, "unchanged": 0}
            for row in rows.get(t, ()):
                _apply_row(con, t, row, counts)
            out[t] = counts
        shown = public_counts(out)
        _insert_attempt(con, attempted_at, True, None, shown)
        con.execute("COMMIT")
        return shown
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


# ── 동기화 기록 ──────────────────────────────────────────────────────────────


def _insert_attempt(
    con: sqlite3.Connection,
    attempted_at: str,
    ok: bool,
    failure_kind: Optional[str],
    counts: Optional[dict[str, Any]],
) -> None:
    con.execute(
        "INSERT INTO ledger_sync_attempt (attempted_at, ok, failure_kind, counts_json)"
        " VALUES (?, ?, ?, ?)",
        (
            attempted_at,
            1 if ok else 0,
            failure_kind,
            None if counts is None else json.dumps(counts, sort_keys=True),
        ),
    )


def record_failure(
    *, failure_kind: str, attempted_at: str, path: Optional[Path] = None
) -> None:
    """실패 시도 1행(반영 트랜잭션이 롤백된 뒤 별도 짧은 트랜잭션)."""
    con = connect(path)
    try:
        with con:
            _insert_attempt(con, attempted_at, False, failure_kind, None)
    finally:
        con.close()


def sync_status(con: sqlite3.Connection) -> dict[str, Any]:
    """마지막 성공 · 실패 시각. 성공이 한 번도 없으면 사본이 없는 것으로 본다."""
    ok = con.execute(
        "SELECT attempted_at FROM ledger_sync_attempt WHERE ok = 1"
        " ORDER BY attempt_seq DESC LIMIT 1"
    ).fetchone()
    bad = con.execute(
        "SELECT attempted_at, failure_kind FROM ledger_sync_attempt WHERE ok = 0"
        " ORDER BY attempt_seq DESC LIMIT 1"
    ).fetchone()
    return {
        "has_copy": ok is not None,
        "last_success_at": None if ok is None else ok["attempted_at"],
        "last_failure_at": None if bad is None else bad["attempted_at"],
        "last_failure_kind": None if bad is None else bad["failure_kind"],
    }


# ── 피드백 ───────────────────────────────────────────────────────────────────


def _clean(
    helpfulness: Any, action: Any, memo: Any
) -> tuple[str, Optional[str], Optional[str]]:
    if helpfulness not in HELPFULNESS:
        raise FeedbackError("invalid", "helpfulness 값이 허용 목록 밖입니다.")
    if action is not None and action not in ACTIONS:
        raise FeedbackError("invalid", "action 값이 허용 목록 밖입니다.")
    text = None
    if memo is not None:
        if not isinstance(memo, str):
            raise FeedbackError("invalid", "memo 는 문자열이어야 합니다.")
        text = memo.strip() or None
        if text is not None and len(text) > MEMO_MAX_LEN:
            raise FeedbackError("invalid", f"memo 는 {MEMO_MAX_LEN}자 이하여야 합니다.")
    return helpfulness, action, text


def add_feedback(
    event_id: str,
    *,
    helpfulness: Any,
    action: Any = None,
    memo: Any = None,
    feedback_at: Optional[str] = None,
    path: Optional[Path] = None,
) -> dict[str, Any]:
    """feedback 1행 추가(append-only). sent · partial 전달이 로컬에 있는 event 만 받는다."""
    h, a, m = _clean(helpfulness, action, memo)
    con = connect(path)
    try:
        con.execute("BEGIN IMMEDIATE")
        run = con.execute(
            "SELECT 1 FROM evaluation_run WHERE event_id = ?", (event_id,)
        ).fetchone()
        if run is None:
            raise FeedbackError("not_found", "로컬 사본에 없는 알림입니다.")
        d = con.execute(
            "SELECT delivery_status FROM delivery WHERE event_id = ?", (event_id,)
        ).fetchone()
        if d is None or d["delivery_status"] not in FEEDBACK_DELIVERY:
            raise FeedbackError(
                "not_target", "발송 완료 · 일부 전달 알림만 평가할 수 있습니다."
            )
        seq = con.execute(
            "SELECT COALESCE(MAX(feedback_seq), 0) + 1 FROM user_feedback WHERE event_id = ?",
            (event_id,),
        ).fetchone()[0]
        at = feedback_at or now_kst()
        con.execute(
            "INSERT INTO user_feedback"
            " (event_id, feedback_seq, helpfulness, action, memo, feedback_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, seq, h, a, m, at),
        )
        con.execute("COMMIT")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    return {
        "event_id": event_id,
        "feedback_seq": seq,
        "helpfulness": h,
        "action": a,
        "memo": m,
        "feedback_at": at,
    }
