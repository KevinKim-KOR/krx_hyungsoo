"""POC5-03 — 원장 새로고침: OCI 읽기 전용 export 1회 → PC 메모리 검증 → 사본 반영(단일 트랜잭션).

PLAN `docs/ai_plan/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_PLAN_V1.md` §2-3 · §8.

```text
호출        POST /decision-ledger/sync(사용자 버튼)만 — 기동 · 화면 진입 · 타이머에서 부르지 않는다
SSH         ssh -o BatchMode=yes -o ConnectTimeout=8 [키] <OCI_SSH_TARGET> "python3 - <원장 경로>"
            · 표준입력 = remote_export.py · 원격 명령은 상수(사용자 입력 결합 0) · 전체 60초
출력        bytes 를 b"\n" 로 나눠 줄마다 UTF-8 로 명시 디코딩 · stdout · stderr 는 로그 · 응답 · 파일
            어디에도 넣지 않는다
검증        header 처음 · end 마지막 · 표별 행 수 = end · 열 집합 = PC 표 열 · 선언 타입(TEXT · INTEGER ·
            REAL · bool · NaN · Infinity 거부) · PK · NOT NULL · 키 중복 0 ·
            run_state ∈ {STARTED, FINALIZED} · 원장 기본 4표 존재(빈 SQLite · 표 누락 = 손상) ·
            price_outcome 은 없어도 됨(성숙 전) — 단 ledger_meta 에 그 표를 만든 기록이 있으면 손상 ·
            item · delivery 는 FINALIZED run 에만 · outcome 은 export 안 item 을 가리킴
반영        전부 통과한 뒤 store.apply_export(한 트랜잭션 · 성공 기록 포함)
            · 실패하면 기존 사본 · feedback 그대로
기록        실패도 ledger_sync_attempt 1행(BUSY 제외) · 로그는 실패 종류 · exit code 만
응답        표별 반영 수에 price_outcome 을 넣지 않는다(피드백 전 결과 존재 여부 비노출)
```
"""

from __future__ import annotations

import json
import logging
import math
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable, Optional

from app.config import EnvConfigError, require_env
from app.ledger_copy import store
from app.ledger_copy.remote_export import FORMAT, TABLES
from app.oci_startup_status import _ssh_key_opts
from app.three_push_runtime.ledger_outcome import META_KEY as OUTCOME_META_KEY

logger = logging.getLogger(__name__)

REMOTE_LEDGER = "/home/ubuntu/krx_hyungsoo/state/decision/decision_evidence.sqlite"
REMOTE_CMD = f"python3 - {REMOTE_LEDGER}"
EXPORT_SCRIPT = Path(__file__).with_name("remote_export.py")
CONNECT_TIMEOUT_SEC = 8
RUN_TIMEOUT_SEC = 60

SSH_FAILED = "SSH_FAILED"
TIMEOUT = "TIMEOUT"
REMOTE_ERROR = "REMOTE_ERROR"
NO_REMOTE_LEDGER = "NO_REMOTE_LEDGER"
INVALID_EXPORT = "INVALID_EXPORT"
CONFLICT = "CONFLICT"
LOCAL_WRITE_FAILED = "LOCAL_WRITE_FAILED"
BUSY = "BUSY"

_LOCK = threading.Lock()
_INT_MIN, _INT_MAX = -(2**63), 2**63 - 1
_RUN_STATES = ("STARTED", "FINALIZED")
# 원장을 처음 열 때 함께 만들어지는 4표(ledger_store.DDL) — 하나라도 없으면 손상된 원장이다.
# price_outcome 은 POC5-02 성숙 첫 실행 때 생기므로 없을 수 있다(성숙 전).
CORE_TABLES = ("evaluation_run", "signal_item", "delivery", "ledger_meta")


class SyncFailure(Exception):
    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


def ssh_command() -> list[str]:
    """원장 export SSH 명령. 원격 명령은 상수다."""
    try:
        target = require_env("OCI_SSH_TARGET")
    except EnvConfigError as e:
        raise SyncFailure(SSH_FAILED) from e
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={CONNECT_TIMEOUT_SEC}",
        *_ssh_key_opts(),
        target,
        REMOTE_CMD,
    ]


def run_export() -> bytes:
    """OCI 읽기 전용 export 1회. 성공이면 stdout bytes, 아니면 SyncFailure."""
    script = (
        EXPORT_SCRIPT.read_bytes()
    )  # 로컬 파일 — 못 읽으면 SSH 실패로 분류하지 않는다
    cmd = ssh_command()
    try:
        result = subprocess.run(
            cmd,
            input=script,
            capture_output=True,
            timeout=RUN_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise SyncFailure(TIMEOUT) from e
    except OSError as e:
        raise SyncFailure(SSH_FAILED) from e
    if result.returncode == 255:  # ssh 자체 실패(인증 · 연결)
        logger.warning("원장 동기화 SSH 실패: exit=%s", result.returncode)
        raise SyncFailure(SSH_FAILED)
    if result.returncode != 0:
        logger.warning("원장 동기화 원격 export 실패: exit=%s", result.returncode)
        raise SyncFailure(REMOTE_ERROR)
    return result.stdout


def _no_constant(name: str) -> Any:
    raise ValueError(name)  # NaN · Infinity 거부


def _lines(raw: bytes) -> list[dict[str, Any]]:
    try:
        out = [
            json.loads(line.decode("utf-8"), parse_constant=_no_constant)
            for line in raw.split(b"\n")
            if line.strip()
        ]
    except (ValueError, RecursionError) as e:  # UnicodeDecodeError 는 ValueError
        raise SyncFailure(INVALID_EXPORT) from e
    if not all(isinstance(o, dict) for o in out):
        raise SyncFailure(INVALID_EXPORT)
    return out


def _typed(value: Any, decl: str) -> bool:
    """선언 타입에 맞는 JSON 값인가(None 은 NOT NULL 검사가 따로 본다)."""
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return decl in ("INTEGER", "REAL") and _INT_MIN <= value <= _INT_MAX
    if isinstance(value, float):
        return decl == "REAL" and math.isfinite(value)
    if isinstance(value, str):
        return decl == "TEXT"
    return False


def parse_export(
    raw: bytes, columns: dict[str, dict[str, tuple[str, bool]]]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, bool]]:
    """export 를 메모리에서 끝까지 검증한다. (표별 행, 표 유무)."""
    lines = _lines(raw)
    if any(o.get("kind") == "error" for o in lines):
        raise SyncFailure(REMOTE_ERROR)
    if len(lines) < 2:
        raise SyncFailure(INVALID_EXPORT)
    head, end = lines[0], lines[-1]
    if head.get("kind") != "header" or head.get("format") != FORMAT:
        raise SyncFailure(INVALID_EXPORT)
    if end.get("kind") != "end" or not isinstance(end.get("counts"), dict):
        raise SyncFailure(INVALID_EXPORT)
    if head.get("ledger") == "absent":
        raise SyncFailure(NO_REMOTE_LEDGER)
    tables = head.get("tables")
    if head.get("ledger") != "present" or not isinstance(tables, dict):
        raise SyncFailure(INVALID_EXPORT)
    if set(tables) != set(TABLES) or not all(
        isinstance(v, bool) for v in tables.values()
    ):
        raise SyncFailure(INVALID_EXPORT)
    if not all(tables[t] for t in CORE_TABLES):
        raise SyncFailure(INVALID_EXPORT)  # 빈 SQLite · 표 누락 = 정상 빈 원장이 아니다
    rows: dict[str, list[dict[str, Any]]] = {t: [] for t in TABLES}
    seen: dict[str, set[tuple[Any, ...]]] = {t: set() for t in TABLES}
    for o in lines[1:-1]:
        t, row = o.get("table"), o.get("row")
        if o.get("kind") != "row" or t not in rows or not tables.get(t):
            raise SyncFailure(INVALID_EXPORT)
        if not isinstance(row, dict) or set(row) != set(columns[t]):
            raise SyncFailure(
                INVALID_EXPORT
            )  # 열 집합이 다르면(스키마 불일치) 받지 않는다
        for c, (decl, required) in columns[t].items():
            if (required and row[c] is None) or not _typed(row[c], decl):
                raise SyncFailure(INVALID_EXPORT)
        if t == "evaluation_run" and row["run_state"] not in _RUN_STATES:
            raise SyncFailure(INVALID_EXPORT)
        key = tuple(row[k] for k in store.KEYS[t])
        if key in seen[t]:
            raise SyncFailure(INVALID_EXPORT)
        seen[t].add(key)
        rows[t].append(row)
    expected = {t: n for t, n in end["counts"].items()}
    actual = {t: len(rows[t]) for t in TABLES if tables[t]}
    if expected != actual:
        raise SyncFailure(INVALID_EXPORT)
    if not tables["price_outcome"] and any(
        r["key"] == OUTCOME_META_KEY for r in rows["ledger_meta"]
    ):
        raise SyncFailure(INVALID_EXPORT)  # 결과 표를 만든 기록이 있는데 표가 없다
    _check_relations(rows)
    return rows, tables


def _check_relations(rows: dict[str, list[dict[str, Any]]]) -> None:
    final = {
        r["event_id"]
        for r in rows["evaluation_run"]
        if r.get("run_state") == "FINALIZED"
    }
    for t in ("signal_item", "delivery"):
        if any(r["event_id"] not in final for r in rows[t]):
            raise SyncFailure(INVALID_EXPORT)
    items = {(r["event_id"], r["item_seq"]) for r in rows["signal_item"]}
    if any((r["event_id"], r["item_seq"]) not in items for r in rows["price_outcome"]):
        raise SyncFailure(INVALID_EXPORT)


def sync_once(
    *,
    runner: Optional[Callable[[], bytes]] = None,
    path: Optional[Path] = None,
) -> dict[str, Any]:
    """원장 새로고침 1회. 이미 진행 중이면 BUSY(기록 없음)."""
    if not _LOCK.acquire(blocking=False):
        return {"ok": False, "failure_kind": BUSY, "attempted_at": store.now_kst()}
    try:
        return _sync(runner or run_export, path)
    finally:
        _LOCK.release()


def _sync(runner: Callable[[], bytes], path: Optional[Path]) -> dict[str, Any]:
    attempted_at = store.now_kst()
    counts: Optional[dict[str, Any]] = None
    kind: Optional[str] = None
    try:
        con = store.connect(path)
        try:
            columns = store.table_columns(con)
        finally:
            con.close()
        raw = runner()
        rows, _tables = parse_export(raw, columns)
        try:
            counts = store.apply_export(rows, attempted_at=attempted_at, path=path)
        except store.SyncConflict as e:
            raise SyncFailure(CONFLICT) from e
        except Exception as e:  # noqa: BLE001 — 로컬 쓰기 실패는 종류만 남긴다
            raise SyncFailure(LOCAL_WRITE_FAILED) from e
    except SyncFailure as e:
        kind = e.kind
    except Exception as e:  # noqa: BLE001 — 예상 밖 실패도 사본을 건드리지 않고 종류만
        logger.warning("원장 동기화 실패: %s", type(e).__name__)
        kind = LOCAL_WRITE_FAILED
    if kind is not None:
        logger.warning("원장 동기화 실패: %s", kind)
        try:
            store.record_failure(
                failure_kind=kind, attempted_at=attempted_at, path=path
            )
        except Exception as e:  # noqa: BLE001 — 기록 실패가 동기화 결과를 바꾸지 않는다
            logger.warning("원장 동기화 기록 실패: %s", type(e).__name__)
    return {
        "ok": kind is None,
        "failure_kind": kind,
        "attempted_at": attempted_at,
        "counts": counts,
    }
