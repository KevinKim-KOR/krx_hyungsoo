"""POC6-32 r1 F3 — 판단 기록 DB 를 읽기만 하는 조회(「주간 ETF 점검」 GET 두 곳).

기존 `decision_evidence_store` 의 읽기 함수는 연결마다 `init_db`(폴더 · 파일 · 표 만들기 · 옛 스키마 마이그레이션 ·
commit)를 부른다. 주간 GET(`/weekly/etf-check` 의 마지막 기록 · `/weekly/etf-check/records/{id}/review`)이 그 일을
하지 않게 이 모듈은:
- 파일이 없으면 '기록 없음'(None) — 폴더 · 파일 · 표를 만들지 않고 연결도 열지 않는다.
- `file:...?mode=ro` URI 로 연다(쓰기 불가 연결 · 한 읽기 트랜잭션).
- 표에 실제로 있는 칸만 고른다(`PRAGMA table_info`) — 옛 스키마도 마이그레이션 없이 읽고, 없는 칸은 빈 기본값
  (빈 글 · 빈 JSON · 후보 · 다음 확인은 빈 목록). 옛 단일 `answer_text` 만 있으면 기존 마이그레이션과 같이 GPT 답으로 읽는다.
- 행 → 기록 사전은 기존 `_row_to_full_dict`(저장소 `get_record` 와 같은 모양 · 같은 JSON 해석).
저장(POST)은 그대로 `decision_evidence_store` 가 한다(표 · 스키마 변경 없음).
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Optional, Sequence

from app.decision_evidence_store import _SELECT_COLS, _row_to_full_dict

TABLE = "ai_session_records"
COLS = tuple(c.strip() for c in _SELECT_COLS.split(","))
# 2026-05-21 이전 단일 답 칸(기존 마이그레이션 = GPT 답으로 옮김)
LEGACY_ANSWER = "answer_text"
_LIST_DEFAULT = ("candidate_snapshot_json", "next_checks_json")


def _empty(col: str) -> Any:
    if col == "linked_market_refresh_id":
        return None
    if col in _LIST_DEFAULT:
        return "[]"
    return "{}" if col.endswith("_json") else ""


def _read_one(
    db_path: Path, need: Sequence[str], tail: str, params: Sequence[Any]
) -> Optional[dict[str, Any]]:
    """`SELECT 있는 칸 FROM ai_session_records {tail} LIMIT 1` — 파일 · 표 · 조건 칸이 없으면 None."""
    p = Path(db_path)
    if not p.exists():
        return None
    with closing(sqlite3.connect(f"file:{p}?mode=ro", uri=True)) as con:
        con.execute("BEGIN")
        have = {r[1] for r in con.execute(f"PRAGMA table_info({TABLE})")}
        if not have or not set(need) <= have:
            return None
        pick = [c for c in COLS if c in have]
        legacy = "gpt_answer_text" not in have and LEGACY_ANSWER in have
        if legacy:
            pick.append(LEGACY_ANSWER)
        row = con.execute(
            f"SELECT {', '.join(pick)} FROM {TABLE} {tail} LIMIT 1", tuple(params)
        ).fetchone()
    if row is None:
        return None
    got = dict(zip(pick, row))
    if legacy:
        got["gpt_answer_text"] = got.pop(LEGACY_ANSWER)
    return _row_to_full_dict(tuple(got[c] if c in got else _empty(c) for c in COLS))


def get_record(record_id: str, *, db_path: Path) -> Optional[dict[str, Any]]:
    """기록 하나 전체(저장소 `get_record` 와 같은 모양) — 없으면 None(파일 · 표가 없어도 None · 만들지 않음)."""
    return _read_one(db_path, ("id",), "WHERE id = ?", (record_id,))


def latest_record(*, db_path: Path, source_screen: str) -> Optional[dict[str, Any]]:
    """출처가 `source_screen` 인 기록 중 저장 시각이 가장 늦은 1건(저장소 목록과 같은 순서 · created_at · id 내림차순)."""
    return _read_one(
        db_path,
        ("id", "created_at", "source_screen"),
        "WHERE source_screen = ? ORDER BY created_at DESC, id DESC",
        (source_screen,),
    )
