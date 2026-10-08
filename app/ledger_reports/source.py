"""POC5-04 — 리포트 입력: PC 원장 사본의 읽기 전용 스냅샷(`mode=ro` · 읽기 트랜잭션 1개).

설계 `docs/ai_design/POC5/POC5-04_COLLECTION_AND_RAW_OUTCOME_REPORTS_DESIGN_V1.md` §2 ·
PLAN §1-1 · §1-5.

```text
입력        PC 원장 사본(03) — evaluation_run · signal_item · delivery · ledger_meta · price_outcome
            + PC 전용 user_feedback(event 마다 최신 1행만) · ledger_sync_attempt(마지막 성공 · 실패)
대상        02 `ledger_outcome._load_targets` 를 같은 트랜잭션에서 그대로 실행(02 코드 수정 0)
digest      표마다 PK 순 정렬한 행 + 최신 평가를 정규 JSON 으로 만든 SHA-256(평가가 바뀌면 달라진다)
손상        필수 표(원장 4 + PC 전용 2)가 없거나 · 결과 표를 만든 기록(meta schema_version.price_outcome)이
            있는데 price_outcome 이 없으면 `problems` 에 남긴다 — 빈 자료로 받지 않는다(R0 = CHECK_REQUIRED ·
            R1 = 통계를 만들지 않음)
쓰기        0 — 연결은 mode=ro · 트랜잭션은 ROLLBACK 으로 닫는다
```
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.three_push_runtime import ledger_outcome

REPORT_VERSION = "ledger_report.v1"
# PC 사본(03)에 늘 있는 표 — 원장 4표(ledger_store.DDL) + PC 전용 2표(ledger_copy.store.PC_DDL).
REQUIRED_TABLES = (
    "evaluation_run",
    "signal_item",
    "delivery",
    "ledger_meta",
    "user_feedback",
    "ledger_sync_attempt",
)

_ORDER = {
    "evaluation_run": "event_id",
    "signal_item": "event_id, item_seq",
    "delivery": "event_id",
    "ledger_meta": "key",
    "price_outcome": "event_id, item_seq, series_id, horizon",
}


@dataclass
class Snapshot:
    path: str
    runs: list[dict[str, Any]]
    items: list[dict[str, Any]]
    deliveries: list[dict[str, Any]]
    outcomes: list[dict[str, Any]]
    meta: dict[str, Optional[str]]
    feedback: dict[str, dict[str, Any]]  # event_id → 최신 평가
    targets: list[Any]  # ledger_outcome._Target
    sync: dict[str, Optional[str]]
    tables: dict[str, bool]
    digest: str = ""
    counts: dict[str, int] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)  # 입력 사본 손상


def _rows(
    con: sqlite3.Connection, table: str, present: set[str]
) -> list[dict[str, Any]]:
    if table not in present:
        return []
    return [
        dict(r) for r in con.execute(f"SELECT * FROM {table} ORDER BY {_ORDER[table]}")
    ]


def _digest(snap: Snapshot) -> str:
    payload = {
        "evaluation_run": snap.runs,
        "signal_item": snap.items,
        "delivery": snap.deliveries,
        "ledger_meta": sorted(snap.meta.items()),
        "price_outcome": snap.outcomes,
        "latest_feedback": [snap.feedback[k] for k in sorted(snap.feedback)],
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def load_snapshot(path: Path) -> Snapshot:
    """원장 사본을 한 읽기 트랜잭션으로 읽는다. 파일이 없으면 FileNotFoundError."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5.0)
    try:
        con.row_factory = sqlite3.Row
        con.execute("BEGIN")
        present = {
            r[0]
            for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        runs = _rows(con, "evaluation_run", present)
        items = _rows(con, "signal_item", present)
        deliveries = _rows(con, "delivery", present)
        outcomes = _rows(con, "price_outcome", present)
        meta = {r["key"]: r["value"] for r in _rows(con, "ledger_meta", present)}
        feedback: dict[str, dict[str, Any]] = {}
        if "user_feedback" in present:
            for r in con.execute(
                "SELECT f.* FROM user_feedback f JOIN ("
                " SELECT event_id, MAX(feedback_seq) AS seq FROM user_feedback"
                " GROUP BY event_id) m"
                " ON m.event_id = f.event_id AND m.seq = f.feedback_seq"
            ):
                feedback[r["event_id"]] = dict(r)
        sync: dict[str, Optional[str]] = {
            "last_success_at": None,
            "last_failure_at": None,
        }
        if "ledger_sync_attempt" in present:
            for key, ok in (("last_success_at", 1), ("last_failure_at", 0)):
                row = con.execute(
                    "SELECT attempted_at FROM ledger_sync_attempt WHERE ok = ?"
                    " ORDER BY attempt_seq DESC LIMIT 1",
                    (ok,),
                ).fetchone()
                sync[key] = None if row is None else row[0]
        problems = [
            f"사본 필수 표 없음: {t}" for t in REQUIRED_TABLES if t not in present
        ]
        if "price_outcome" not in present and meta.get(ledger_outcome.META_KEY):
            problems.append(
                "가격 결과 표를 만든 기록(schema_version.price_outcome)이 있는데"
                " price_outcome 표 없음"
            )
        core = {"evaluation_run", "signal_item"} <= present
        targets = ledger_outcome._load_targets(con) if core else []
        con.execute("ROLLBACK")
    finally:
        con.close()
    snap = Snapshot(
        path=str(p),
        runs=runs,
        items=items,
        deliveries=deliveries,
        outcomes=outcomes,
        meta=meta,
        feedback=feedback,
        targets=targets,
        sync=sync,
        tables={
            t: t in present for t in (*_ORDER, "user_feedback", "ledger_sync_attempt")
        },
    )
    snap.problems = problems
    snap.digest = _digest(snap)
    snap.counts = {
        "evaluation_run": len(runs),
        "signal_item": len(items),
        "delivery": len(deliveries),
        "ledger_meta": len(meta),
        "price_outcome": len(outcomes),
        "events_with_feedback": len(feedback),
    }
    return snap


def input_summary(snap: Snapshot) -> dict[str, Any]:
    """리포트 머리 — 원장 시점 · 동기화 시각 · 시작 meta · 계약 버전 · 행 수 · digest."""
    keep = ("primary_start_date", "first_active_at", "schema_version", "deploy_commit")
    return {
        "path": snap.path,
        "digest": snap.digest,
        "counts": snap.counts,
        "tables": snap.tables,
        "sync": snap.sync,
        "problems": snap.problems,
        "meta": {k: snap.meta.get(k) for k in keep},
        "contract_versions": sorted(
            k for k in snap.meta if k.startswith("contract_version.")
        ),
    }
