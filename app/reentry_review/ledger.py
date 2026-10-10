"""POC5-06 — 선택 ticker 의 PC 원장 사본 근거(읽기 전용 · 설계 개정 2 §3 · §10-4 · §10-5).

```text
읽기     `file:<사본>?mode=ro` 한 읽기 트랜잭션(BEGIN … ROLLBACK · 04 ledger_reports.source 와 같음).
         사본 없음 = NO_COPY(파일을 만들지 않는다) · DB 오류 = READ_FAILED(0행과 구분)
손상     04 `ledger_reports.source` · 03 동기화와 같은 판정 — 필수 6표(원장 4 + PC 전용 2) 중 하나라도
         없거나 · 결과 표를 만든 기록(meta schema_version.price_outcome)이 있는데 price_outcome 이
         없으면 READ_FAILED('원장 사본 손상 — …') · 근거 0행. 표가 없는 것을 '평가 없음' · '집계 중' ·
         '동기화 기록 없음'으로 바꾸지 않는다. 결과 표를 만든 기록이 없을 때의 price_outcome 없음만 정상(성숙 전).
         이 종목을 담은 후보 행의 values_json 을 해석할 수 없어도 손상(연결을 0건으로 숨기지 않음)
연결     FINALIZED 실행만 · 원장에 실제로 적힌 ticker 와 정확히 같을 때만
           SUBJECT               subject_kind='ticker' AND subject_id = ticker
           SECTOR_REPRESENTATIVE subject_kind='sector' AND values_json.ticker = ticker
           INDEX_GROUP_MEMBER    subject_kind='index_group' AND ticker ∈ values_json.tickers
         현재 설정 · 마스터 · 이름 · 날짜 근접으로 추정하지 않는다
가격 결과  같은 (event_id, item_seq) 에서 series_id 가 이 ticker 를 명시한 행만(benchmark 제외)
평가     알림(event) 단위 · 최신 1행 + 건수 · 종목별 평가 아님
개인값    values_json 을 돌려주지 않는다(손익률 · t0 로 평단을 역산할 수 있음) · ML 입력 0
```
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from app.ledger_copy import store as copy_store
from app.ledger_copy import views as copy_views
from app.ledger_reports.source import REQUIRED_TABLES
from app.reentry_review import models as M
from app.three_push_runtime.ledger_outcome import META_KEY as OUTCOME_META_KEY

HORIZONS = (1, 5, 20)
_OUTCOME_FIELDS = (
    "series_id",
    "horizon",
    "status",
    "eval_date",
    "return_raw",
    "max_up_raw",
    "max_down_raw",
    "price_basis",
    "computed_at",
)


def _view(disposition: str, delivery_status: Optional[str]) -> str:
    if disposition != "sent":
        return M.VIEW_OBSERVED
    if delivery_status == "sent":
        return M.VIEW_DELIVERED
    if delivery_status == "partial":
        return M.VIEW_PARTIAL
    return M.VIEW_NOT_DELIVERED


class _CopyDamaged(Exception):
    """연결을 판정할 수 없는 사본 행 — 0건으로 숨기지 않고 손상으로 알린다."""


def _link_kind(row: sqlite3.Row, ticker: str) -> Optional[str]:
    kind = row["subject_kind"]
    if kind == "ticker":
        return M.LINK_SUBJECT if row["subject_id"] == ticker else None
    where = f"{row['event_id']} · item {row['item_seq']}"
    try:
        values = json.loads(row["values_json"] or "{}")
    except ValueError as e:
        raise _CopyDamaged(f"values_json 해석 불가({where})") from e
    if not isinstance(values, dict):
        raise _CopyDamaged(f"values_json 형식 이상({where})")
    if kind == "sector" and values.get("ticker") == ticker:
        return M.LINK_SECTOR_REPRESENTATIVE
    members = values.get("tickers")
    if kind == "index_group" and isinstance(members, list) and ticker in members:
        return M.LINK_INDEX_GROUP_MEMBER
    return None


def _names_ticker(series_id: str, ticker: str) -> bool:
    prefix, _, code = series_id.partition(":")
    return prefix != "benchmark" and code == ticker


def _candidates(con: sqlite3.Connection, ticker: str) -> list[sqlite3.Row]:
    # 후보만 좁힌다(정확한 판정은 _link_kind) — 문자열 포함은 후보 선별에만 쓴다.
    return list(
        con.execute(
            "SELECT i.event_id, i.item_seq, i.subject_kind, i.subject_id, i.state,"
            " i.disposition, i.exposure, i.values_json, i.evaluable,"
            " r.push_kind, r.runtime_kst, r.runtime_date_kst, r.cohort, r.off_schedule,"
            " r.contract_version, r.status AS run_status, d.delivery_status"
            " FROM signal_item i JOIN evaluation_run r ON r.event_id = i.event_id"
            " LEFT JOIN delivery d ON d.event_id = i.event_id"
            " WHERE r.run_state = 'FINALIZED' AND ("
            " (i.subject_kind = 'ticker' AND i.subject_id = ?)"
            " OR (i.subject_kind IN ('sector', 'index_group') AND instr(i.values_json, ?) > 0))"
            " ORDER BY r.runtime_kst DESC, i.event_id, i.item_seq",
            (ticker, ticker),
        )
    )


def _tables(con: sqlite3.Connection) -> set[str]:
    return {
        r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def copy_problems(con: sqlite3.Connection, present: set[str]) -> list[str]:
    """사본 손상 사유(04 `load_snapshot` 의 problems 와 같은 규칙) · 없으면 []."""
    problems = [f"사본 필수 표 없음: {t}" for t in REQUIRED_TABLES if t not in present]
    if "price_outcome" not in present and "ledger_meta" in present:
        made = con.execute(
            "SELECT value FROM ledger_meta WHERE key = ?", (OUTCOME_META_KEY,)
        ).fetchone()
        if made is not None and made[0]:
            problems.append(
                "가격 결과 표를 만든 기록(schema_version.price_outcome)이 있는데"
                " price_outcome 표 없음"
            )
    return problems


def ticker_ledger_evidence(
    ticker: str, *, path: Optional[Path] = None
) -> dict[str, Any]:
    """선택 ticker 의 알림 근거 — {status, synced_at, items, counts}. 쓰기 0."""
    p = Path(path) if path is not None else Path(copy_store.DEFAULT_DB_PATH)
    base: dict[str, Any] = {
        "ticker": ticker,
        "synced_at": None,
        "items": [],
        "counts": {},
    }
    if not p.exists():
        return {**base, "status": M.NO_COPY, "status_text": M.STATUS_TEXT[M.NO_COPY]}
    try:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5.0)
    except sqlite3.Error as e:
        return {
            **base,
            "status": M.READ_FAILED,
            "status_text": f"원장 사본 읽기 실패: {type(e).__name__}",
        }
    try:
        con.row_factory = sqlite3.Row
        con.execute("BEGIN")
        present = _tables(con)
        problems = copy_problems(con, present)
        if problems:  # 손상 사본은 일부만 읽어 정상처럼 보이지 않는다
            con.execute("ROLLBACK")
            return {
                **base,
                "status": M.READ_FAILED,
                "status_text": "원장 사본 손상 — " + " · ".join(problems),
                "problems": problems,
            }
        try:
            items = _items(con, ticker, present)
        except _CopyDamaged as e:
            con.execute("ROLLBACK")
            return {
                **base,
                "status": M.READ_FAILED,
                "status_text": f"원장 사본 손상 — {e}",
                "problems": [str(e)],
            }
        row = con.execute(
            "SELECT attempted_at FROM ledger_sync_attempt WHERE ok = 1"
            " ORDER BY attempt_seq DESC LIMIT 1"
        ).fetchone()
        synced_at = None if row is None else row[0]
        con.execute("ROLLBACK")
    except sqlite3.Error as e:
        return {
            **base,
            "status": M.READ_FAILED,
            "status_text": f"원장 사본 읽기 실패: {type(e).__name__}",
        }
    finally:
        con.close()
    counts: dict[str, dict[str, int]] = {}
    for it in items:
        c = counts.setdefault(it["link_kind"], {})
        c[it["view"]] = c.get(it["view"], 0) + 1
    return {
        **base,
        "status": M.OK,
        "status_text": None,
        "synced_at": synced_at,
        "items": items,
        "counts": counts,
    }


def _items(
    con: sqlite3.Connection, ticker: str, present: set[str]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    feedback_cache: dict[str, dict[str, Any]] = {}
    for row in _candidates(con, ticker):
        link = _link_kind(row, ticker)
        if link is None:
            continue
        event_ok = copy_views.event_target(row["cohort"], row["off_schedule"])
        target = copy_views.item_target(
            event_ok, row["subject_kind"], row["subject_id"], row["evaluable"]
        )
        outcomes = _outcomes(con, row, ticker, present)
        done = {o["horizon"] for o in outcomes}
        out.append(
            {
                "link_kind": link,
                "link_text": M.LINK_TEXT[link],
                "event_id": row["event_id"],
                "item_seq": row["item_seq"],
                "push_kind": row["push_kind"],
                "runtime_kst": row["runtime_kst"],
                "runtime_date_kst": row["runtime_date_kst"],
                "subject_kind": row["subject_kind"],
                "subject_id": row["subject_id"],
                "state": row["state"],
                "state_label": copy_views.state_label(
                    row["push_kind"], row["subject_kind"], row["state"]
                ),
                "disposition": row["disposition"],
                "delivery_status": row["delivery_status"],
                "view": _view(row["disposition"], row["delivery_status"]),
                "view_text": M.VIEW_TEXT[
                    _view(row["disposition"], row["delivery_status"])
                ],
                "exposure": row["exposure"] or "NONE",
                "cohort": row["cohort"],
                "off_schedule": int(row["off_schedule"] or 0),
                "contract_version": row["contract_version"],
                "outcome_target": target,
                "outcomes": outcomes,
                "pending_horizons": [h for h in HORIZONS if target and h not in done],
                "feedback": _feedback(con, row["event_id"], feedback_cache),
            }
        )
    return out


def _outcomes(
    con: sqlite3.Connection, row: sqlite3.Row, ticker: str, present: set[str]
) -> list[dict[str, Any]]:
    if "price_outcome" not in present:
        return []
    cols = ", ".join(_OUTCOME_FIELDS)
    rows = con.execute(
        f"SELECT {cols} FROM price_outcome WHERE event_id = ? AND item_seq = ?"
        " ORDER BY series_id, horizon",
        (row["event_id"], row["item_seq"]),
    ).fetchall()
    return [dict(r) for r in rows if _names_ticker(r["series_id"], ticker)]


def _feedback(
    con: sqlite3.Connection, event_id: str, cache: dict[str, Any]
) -> dict[str, Any]:
    if event_id in cache:
        return cache[event_id]
    result: dict[str, Any] = {
        "scope": "EVENT",
        "scope_text": M.FEEDBACK_SCOPE_TEXT,
        "count": 0,
        "latest": None,
    }
    rows = con.execute(  # 필수 표(손상 판정에서 확인)
        "SELECT feedback_seq, helpfulness, action, memo, feedback_at FROM user_feedback"
        " WHERE event_id = ? ORDER BY feedback_seq",
        (event_id,),
    ).fetchall()
    if rows:
        result["count"] = len(rows)
        result["latest"] = dict(rows[-1])
    cache[event_id] = result
    return result


def snapshot_ids(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    """연구 snapshot 용 식별 근거만(메모 · 값 없음)."""
    out = []
    for it in evidence.get("items", []):
        fb = it["feedback"]["latest"]
        out.append(
            {
                "event_id": it["event_id"],
                "item_seq": it["item_seq"],
                "link_kind": it["link_kind"],
                "outcomes": [
                    {
                        "series_id": o["series_id"],
                        "horizon": o["horizon"],
                        "status": o["status"],
                    }
                    for o in it["outcomes"]
                ],
                "feedback": (
                    None
                    if fb is None
                    else {
                        "event_id": it["event_id"],
                        "feedback_seq": fb["feedback_seq"],
                        "helpfulness": fb["helpfulness"],
                    }
                ),
            }
        )
    return out
