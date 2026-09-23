"""POC4-01 — KRX 과거 ETF universe 연구 DB (설계자 결정 2 — 2026-09-23).

생존편향을 없애려면 "그날 상장돼 있던 ETF 전체" 가 필요하다. 운영 DB 의
`etf_master` 는 현재 상장 종목만 있어 상장폐지 종목이 빠진다. KRX Open API
`etf_bydd_trd` 는 기준일 당시 상장 종목을 폐지 종목까지 돌려준다(공식 FAQ).

```text
LOCATION      = PC 전용 별도 ML research DB (state/ml/research/)
OCI_WRITE     = 0
OPERATING_DB  = 변경 금지 (state/market/market_data.sqlite 를 열지 않는다)
PRICE_MIXING  = 금지 (운영 etf_daily_price 와 섞지 않는다 — 조정/무조정 계열이 다르다)
```

저장 계약
- 원응답 본문을 그대로 append-only 로 보관한다 (`krx_raw_response`) — 덮어쓰지 않는다.
- 호출마다 batch·조회 시각·source·HTTP 상태·payload sha256 을 남긴다 (`krx_fetch_attempt`).
- 날짜·종목 행은 원문 dict 그대로 (`krx_etf_daily_raw`) — 현재 etf_master 로 거르지 않는다.
- dataset version 은 기준일 → 응답 1개의 묶음이다. 같은 날짜를 다시 받아 내용이
  다르면 기존 version 을 바꾸지 않고 충돌로 기록한다 → 새 version 은 명시적으로 만든다.
- checkpoint(`krx_download_plan`)로 중단 후 이어받는다. 끝난 날짜는 다시 부르지 않는다.

호출 한도 — KRX OPEN API 이용약관 제8조④(2025-12-26 시행)·공식 FAQ: 인증키당 하루
10,000회, 초과 시 HTTP 429. 운영 배치와 키를 같이 쓰므로 한 번 실행은 그 절반 이하로 막는다.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

from app.market_data_store import DEFAULT_DB_PATH

KRX_ETF_DAILY_URL = "https://data-dbg.krx.co.kr/svc/apis/etp/etf_bydd_trd"
SOURCE = "KRX_OPEN_API"
DEFAULT_RESEARCH_DB = (
    Path(__file__).resolve().parent.parent
    / "state"
    / "ml"
    / "research"
    / "krx_etf_universe.sqlite"
)
OFFICIAL_DAILY_CALL_LIMIT = 10_000
MAX_CALLS_PER_KST_DAY = OFFICIAL_DAILY_CALL_LIMIT // 2
CANARY_MAX_DATES = 20
REQUEST_TIMEOUT = 40.0
KST = timezone(timedelta(hours=9))

# plan 상태 — PENDING 과 FAILED 만 다시 부른다.
PENDING, FAILED = "PENDING", "FAILED"
TRADED, NON_TRADING, NO_ROWS = "TRADED", "NON_TRADING", "NO_ROWS"
TERMINAL = (TRADED, NON_TRADING, NO_ROWS)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS krx_download_batch (
    batch_id TEXT PRIMARY KEY, purpose TEXT NOT NULL, dataset_version TEXT NOT NULL,
    source TEXT NOT NULL, endpoint TEXT NOT NULL, created_at TEXT NOT NULL,
    planned_count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS krx_download_plan (
    batch_id TEXT NOT NULL, bas_dd TEXT NOT NULL, state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, response_id INTEGER,
    updated_at TEXT NOT NULL, PRIMARY KEY (batch_id, bas_dd)
);
CREATE TABLE IF NOT EXISTS krx_fetch_attempt (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id TEXT NOT NULL,
    bas_dd TEXT NOT NULL, requested_at TEXT NOT NULL, requested_kst_date TEXT NOT NULL,
    http_status INTEGER, error TEXT, response_id INTEGER
);
CREATE TABLE IF NOT EXISTS krx_raw_response (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id TEXT NOT NULL,
    bas_dd TEXT NOT NULL, requested_at TEXT NOT NULL, source TEXT NOT NULL,
    endpoint TEXT NOT NULL, http_status INTEGER NOT NULL,
    payload_sha256 TEXT NOT NULL, payload TEXT NOT NULL,
    row_count INTEGER NOT NULL, traded INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS krx_etf_daily_raw (
    response_id INTEGER NOT NULL, row_no INTEGER NOT NULL, bas_dd TEXT NOT NULL,
    isu_cd TEXT, row_json TEXT NOT NULL, PRIMARY KEY (response_id, row_no)
);
CREATE INDEX IF NOT EXISTS idx_krx_raw_date_isu ON krx_etf_daily_raw (bas_dd, isu_cd);
CREATE TABLE IF NOT EXISTS krx_dataset_version (
    version_id TEXT PRIMARY KEY, parent_version TEXT, status TEXT NOT NULL,
    created_at TEXT NOT NULL, sealed_at TEXT, content_sha256 TEXT, note TEXT
);
CREATE TABLE IF NOT EXISTS krx_dataset_member (
    version_id TEXT NOT NULL, bas_dd TEXT NOT NULL, response_id INTEGER NOT NULL,
    PRIMARY KEY (version_id, bas_dd)
);
CREATE TABLE IF NOT EXISTS krx_refetch_conflict (
    version_id TEXT NOT NULL, bas_dd TEXT NOT NULL, kept_response_id INTEGER NOT NULL,
    new_response_id INTEGER NOT NULL, detected_at TEXT NOT NULL,
    PRIMARY KEY (version_id, bas_dd, new_response_id)
);
"""


class ResearchDbError(RuntimeError):
    """연구 DB 계약 위반 (운영 DB 경로 · 봉인 version 수정 · 한도 초과 계획 등)."""


@dataclass(frozen=True)
class FetchResult:
    http_status: int
    text: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def connect(db_path: Path = DEFAULT_RESEARCH_DB) -> sqlite3.Connection:
    """연구 DB 연결. 운영 시장 DB 경로면 거부한다 (OPERATING_DB 변경 금지)."""
    if Path(db_path).resolve() == Path(DEFAULT_DB_PATH).resolve():
        raise ResearchDbError("운영 시장 DB 에는 연구 데이터를 쓰지 않는다")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.executescript(_SCHEMA)
    return con


def http_fetch(bas_dd: str, key: str) -> FetchResult:
    """원응답 본문을 그대로 돌려준다. **키는 헤더로만 보내고 기록하지 않는다.**"""
    import httpx

    r = httpx.get(
        KRX_ETF_DAILY_URL,
        params={"basDd": bas_dd},
        headers={"AUTH_KEY": key},
        timeout=REQUEST_TIMEOUT,
    )
    return FetchResult(r.status_code, r.text)


def weekdays(start: str, end: str) -> list[str]:
    """KRX 는 거래일 달력 API 가 없다(공식 FAQ) — 평일 전부를 계획하고 휴장은 응답으로 판정."""
    d0, d1 = (datetime.strptime(x, "%Y%m%d").date() for x in (start, end))
    out: list[str] = []
    d = d0
    while d <= d1:
        if d.weekday() < 5:
            out.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return out


def calls_today(con: sqlite3.Connection, today: Optional[date] = None) -> int:
    day = (today or _now().astimezone(KST).date()).isoformat()
    return con.execute(
        "SELECT COUNT(*) FROM krx_fetch_attempt WHERE requested_kst_date = ?", (day,)
    ).fetchone()[0]


def create_batch(
    con: sqlite3.Connection,
    *,
    batch_id: str,
    purpose: str,
    dates: Iterable[str],
    dataset_version: str,
) -> int:
    """batch + checkpoint 계획을 만든다. 이미 있으면 계획을 바꾸지 않는다(이어받기)."""
    dates = sorted(set(dates))
    if purpose == "CANARY" and len(dates) > CANARY_MAX_DATES:
        raise ResearchDbError(f"canary 는 최대 {CANARY_MAX_DATES}개 기준일")
    if len(dates) > MAX_CALLS_PER_KST_DAY:
        raise ResearchDbError("한 batch 계획이 하루 호출 상한을 넘는다 — 나눠서 계획")
    row = con.execute(
        "SELECT dataset_version FROM krx_download_batch WHERE batch_id=?", (batch_id,)
    ).fetchone()
    if row:
        if row[0] != dataset_version:
            raise ResearchDbError("기존 batch 의 dataset version 과 다르다")
        return con.execute(
            "SELECT COUNT(*) FROM krx_download_plan WHERE batch_id=?", (batch_id,)
        ).fetchone()[0]
    _ensure_open_version(con, dataset_version)
    now = _now().isoformat()
    con.execute(
        "INSERT INTO krx_download_batch VALUES (?,?,?,?,?,?,?)",
        (
            batch_id,
            purpose,
            dataset_version,
            SOURCE,
            KRX_ETF_DAILY_URL,
            now,
            len(dates),
        ),
    )
    con.executemany(
        "INSERT INTO krx_download_plan (batch_id, bas_dd, state, updated_at) "
        "VALUES (?,?,?,?)",
        [(batch_id, d, PENDING, now) for d in dates],
    )
    con.commit()
    return len(dates)


def _ensure_open_version(con: sqlite3.Connection, version_id: str) -> None:
    row = con.execute(
        "SELECT status FROM krx_dataset_version WHERE version_id=?", (version_id,)
    ).fetchone()
    if row is None:
        con.execute(
            "INSERT INTO krx_dataset_version (version_id, status, created_at) "
            "VALUES (?, 'OPEN', ?)",
            (version_id, _now().isoformat()),
        )
    elif row[0] != "OPEN":
        raise ResearchDbError(
            f"봉인된 dataset version 에는 추가하지 않는다: {version_id}"
        )


def _classify(rows: list[dict]) -> str:
    if not rows:
        return NO_ROWS
    traded = any((r.get("TDD_CLSPRC") or "").strip() for r in rows)
    return TRADED if traded else NON_TRADING


def _store_response(
    con: sqlite3.Connection, batch_id: str, bas_dd: str, res: FetchResult, rows: list
) -> int:
    state = _classify(rows)
    cur = con.execute(
        "INSERT INTO krx_raw_response (batch_id, bas_dd, requested_at, source, "
        "endpoint, http_status, payload_sha256, payload, row_count, traded) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            batch_id,
            bas_dd,
            _now().isoformat(),
            SOURCE,
            KRX_ETF_DAILY_URL,
            res.http_status,
            hashlib.sha256(res.text.encode("utf-8")).hexdigest(),
            res.text,
            len(rows),
            int(state == TRADED),
        ),
    )
    response_id = int(cur.lastrowid)
    con.executemany(
        "INSERT INTO krx_etf_daily_raw VALUES (?,?,?,?,?)",
        [
            (
                response_id,
                i,
                bas_dd,
                r.get("ISU_CD"),
                json.dumps(r, ensure_ascii=False, sort_keys=True),
            )
            for i, r in enumerate(rows)
        ],
    )
    return response_id


def _attach_member(
    con: sqlite3.Connection, version_id: str, bas_dd: str, response_id: int
) -> None:
    """version 에 기준일을 붙인다. 이미 다른 내용이 있으면 바꾸지 않고 충돌로 남긴다."""
    row = con.execute(
        "SELECT m.response_id, r.payload_sha256 FROM krx_dataset_member m "
        "JOIN krx_raw_response r ON r.response_id = m.response_id "
        "WHERE m.version_id=? AND m.bas_dd=?",
        (version_id, bas_dd),
    ).fetchone()
    if row is None:
        con.execute(
            "INSERT INTO krx_dataset_member VALUES (?,?,?)",
            (version_id, bas_dd, response_id),
        )
        return
    new_hash = con.execute(
        "SELECT payload_sha256 FROM krx_raw_response WHERE response_id=?",
        (response_id,),
    ).fetchone()[0]
    if new_hash != row[1]:
        con.execute(
            "INSERT OR IGNORE INTO krx_refetch_conflict VALUES (?,?,?,?,?)",
            (version_id, bas_dd, row[0], response_id, _now().isoformat()),
        )


def _record_attempt(con, batch_id, bas_dd, status, error, response_id=None) -> None:
    now = _now()
    con.execute(
        "INSERT INTO krx_fetch_attempt (batch_id, bas_dd, requested_at, "
        "requested_kst_date, http_status, error, response_id) VALUES (?,?,?,?,?,?,?)",
        (
            batch_id,
            bas_dd,
            now.isoformat(),
            now.astimezone(KST).date().isoformat(),
            status,
            error,
            response_id,
        ),
    )


def run_batch(
    con: sqlite3.Connection,
    batch_id: str,
    *,
    key: str,
    fetch: Callable[[str, str], FetchResult] = http_fetch,
    max_calls: int,
    pause_seconds: float = 0.5,
    max_attempts: int = 3,
    backoff_seconds: float = 2.0,
    max_consecutive_failures: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """PENDING·FAILED 기준일을 순서대로 받는다. 날짜마다 commit(checkpoint).

    - HTTP 429 → 즉시 중단 (한도 소진 — 재시도하지 않는다)
    - 그 밖의 4xx → 즉시 중단 (키·신청 문제 — 계속 부르면 호출만 낭비)
    - 5xx·네트워크·JSON 오류 → 지수 backoff 재시도, 소진 시 FAILED 후 다음 날짜
    - 연속 FAILED 가 `max_consecutive_failures` 이면 중단
    """
    version = con.execute(
        "SELECT dataset_version FROM krx_download_batch WHERE batch_id=?", (batch_id,)
    ).fetchone()
    if version is None:
        raise ResearchDbError(f"batch 가 없다: {batch_id}")
    _ensure_open_version(con, version[0])
    budget = MAX_CALLS_PER_KST_DAY - calls_today(con)
    limit = min(max_calls, budget)
    todo = [
        r[0]
        for r in con.execute(
            "SELECT bas_dd FROM krx_download_plan WHERE batch_id=? AND state IN (?,?) "
            "ORDER BY bas_dd",
            (batch_id, PENDING, FAILED),
        )
    ]
    calls, done, stopped, consecutive = 0, 0, None, 0
    for bas_dd in todo:
        if calls >= limit:
            stopped = "CALL_LIMIT"  # 이 날짜는 PENDING 그대로 — 다음 실행이 이어받는다
            break
        state, error, response_id = FAILED, None, None
        for attempt in range(max_attempts):
            if attempt and calls >= limit:
                stopped = "CALL_LIMIT"  # 재시도 중 상한 — FAILED 로 남겨 다음에 재시도
                break
            if calls:
                sleep(pause_seconds)
            calls += 1
            try:
                res = fetch(bas_dd, key)
            except Exception as exc:  # noqa: BLE001 — 네트워크 오류는 재시도
                error, status = type(exc).__name__, None
            else:
                status = res.http_status
                if status == 429:
                    error, stopped = "HTTP 429", "QUOTA_429"
                elif 400 <= status < 500:
                    error, stopped = f"HTTP {status}", f"HTTP_{status}"
                elif status >= 500:
                    error = f"HTTP {status}"
                else:
                    try:
                        rows = json.loads(res.text).get("OutBlock_1") or []
                    except (ValueError, AttributeError) as exc:
                        error = f"JSON {type(exc).__name__}"
                    else:
                        response_id = _store_response(con, batch_id, bas_dd, res, rows)
                        state, error = _classify(rows), None
                        if state == TRADED:
                            _attach_member(con, version[0], bas_dd, response_id)
            _record_attempt(con, batch_id, bas_dd, status, error, response_id)
            con.execute(
                "UPDATE krx_download_plan SET attempts = attempts + 1 "
                "WHERE batch_id=? AND bas_dd=?",
                (batch_id, bas_dd),
            )
            if state != FAILED or stopped:
                break
            if attempt + 1 < max_attempts:
                sleep(backoff_seconds * (2**attempt))
        con.execute(
            "UPDATE krx_download_plan SET state=?, last_error=?, response_id=?, "
            "updated_at=? WHERE batch_id=? AND bas_dd=?",
            (state, error, response_id, _now().isoformat(), batch_id, bas_dd),
        )
        con.commit()
        done += state in TERMINAL
        consecutive = consecutive + 1 if state == FAILED else 0
        if stopped:
            break
        if consecutive >= max_consecutive_failures:
            stopped = "CONSECUTIVE_FAILURES"
            break
    con.commit()
    return {
        "batch_id": batch_id,
        "calls": calls,
        "completed_dates": done,
        "stopped": stopped,
        "status": batch_status(con, batch_id),
    }


def batch_status(con: sqlite3.Connection, batch_id: str) -> dict:
    counts = dict(
        con.execute(
            "SELECT state, COUNT(*) FROM krx_download_plan WHERE batch_id=? "
            "GROUP BY state",
            (batch_id,),
        ).fetchall()
    )
    return {
        "states": counts,
        "remaining": counts.get(PENDING, 0) + counts.get(FAILED, 0),
    }


def verify_batch(con: sqlite3.Connection, batch_id: str) -> dict:
    """중복·누락·hash·version 정합성 점검 (canary 게이트 4)."""
    version = con.execute(
        "SELECT dataset_version FROM krx_download_batch WHERE batch_id=?", (batch_id,)
    ).fetchone()[0]
    not_terminal = [
        r[0]
        for r in con.execute(
            "SELECT bas_dd FROM krx_download_plan WHERE batch_id=? AND state NOT IN "
            "(?,?,?)",
            (batch_id, *TERMINAL),
        )
    ]
    hash_mismatch = [
        r[0]
        for r in con.execute(
            "SELECT response_id, payload, payload_sha256 FROM krx_raw_response "
            "WHERE batch_id=?",
            (batch_id,),
        )
        if hashlib.sha256(r[1].encode("utf-8")).hexdigest() != r[2]
    ]
    dup_rows = con.execute(
        "SELECT COUNT(*) FROM (SELECT response_id, isu_cd FROM krx_etf_daily_raw "
        "WHERE response_id IN (SELECT response_id FROM krx_raw_response "
        "WHERE batch_id=?) GROUP BY response_id, isu_cd HAVING COUNT(*) > 1)",
        (batch_id,),
    ).fetchone()[0]
    missing_isu = con.execute(
        "SELECT COUNT(*) FROM krx_etf_daily_raw WHERE isu_cd IS NULL AND response_id "
        "IN (SELECT response_id FROM krx_raw_response WHERE batch_id=?)",
        (batch_id,),
    ).fetchone()[0]
    traded_not_member = [
        r[0]
        for r in con.execute(
            "SELECT p.bas_dd FROM krx_download_plan p WHERE p.batch_id=? AND "
            "p.state=? AND NOT EXISTS (SELECT 1 FROM krx_dataset_member m WHERE "
            "m.version_id=? AND m.bas_dd=p.bas_dd)",
            (batch_id, TRADED, version),
        )
    ]
    conflicts = con.execute(
        "SELECT COUNT(*) FROM krx_refetch_conflict WHERE version_id=?", (version,)
    ).fetchone()[0]
    ok = not (not_terminal or hash_mismatch or dup_rows or missing_isu)
    return {
        "ok": ok and not traded_not_member,
        "not_terminal_dates": not_terminal,
        "payload_hash_mismatch": hash_mismatch,
        "duplicate_isu_within_response": dup_rows,
        "rows_without_isu_cd": missing_isu,
        "traded_dates_missing_from_version": traded_not_member,
        "refetch_conflicts_in_version": conflicts,
    }


def seal_version(con: sqlite3.Connection, version_id: str, note: str = "") -> dict:
    """version 을 봉인한다. 이후 이 version 은 바뀌지 않는다 (baseline 은 봉인본 하나만 쓴다)."""
    _ensure_open_version(con, version_id)
    members = con.execute(
        "SELECT m.bas_dd, r.payload_sha256 FROM krx_dataset_member m JOIN "
        "krx_raw_response r ON r.response_id=m.response_id WHERE m.version_id=? "
        "ORDER BY m.bas_dd",
        (version_id,),
    ).fetchall()
    digest = hashlib.sha256(
        "".join(f"{d}|{h}\n" for d, h in members).encode("utf-8")
    ).hexdigest()
    con.execute(
        "UPDATE krx_dataset_version SET status='SEALED', sealed_at=?, "
        "content_sha256=?, note=? WHERE version_id=?",
        (_now().isoformat(), digest, note, version_id),
    )
    con.commit()
    return {"version_id": version_id, "dates": len(members), "content_sha256": digest}


def derive_version(
    con: sqlite3.Connection,
    new_version: str,
    parent: str,
    replacements: dict[str, int],
) -> None:
    """재수집 결과가 달라졌을 때 쓰는 **별도** version. 부모는 그대로 둔다."""
    if con.execute(
        "SELECT 1 FROM krx_dataset_version WHERE version_id=?", (new_version,)
    ).fetchone():
        raise ResearchDbError(f"이미 있는 version: {new_version}")
    con.execute(
        "INSERT INTO krx_dataset_version (version_id, parent_version, status, "
        "created_at) VALUES (?,?, 'OPEN', ?)",
        (new_version, parent, _now().isoformat()),
    )
    con.execute(
        "INSERT INTO krx_dataset_member SELECT ?, bas_dd, response_id FROM "
        "krx_dataset_member WHERE version_id=?",
        (new_version, parent),
    )
    for bas_dd, response_id in replacements.items():
        con.execute(
            "INSERT OR REPLACE INTO krx_dataset_member VALUES (?,?,?)",
            (new_version, bas_dd, response_id),
        )
    con.commit()
