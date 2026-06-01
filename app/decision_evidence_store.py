"""Decision Evidence SQLite 저장소 (POC2 — AI Sessions / Context Bridge).

본 모듈은 다음 1개 테이블만 관리한다:
- ai_session_records: AI 질문 / GPT·Gemini·Claude 3개 답변 / 사용자 메모 / 1차
  판정 / 후보 스냅샷 / 필터 스냅샷.

DB 파일은 시장 데이터(`state/market/market_data.sqlite`) 와 분리된
`state/decision/decision_evidence.sqlite` 다. 두 도메인을 같은 DB 파일에
섞지 않는다 (PROJECT_ORIGIN_INTENT §10 — 데이터 종류별 SSOT 분리).

2026-05-21 변경 (AI Sessions / Decision Evidence + Context Bridge):
- 기존 단일 `answer_text` 컬럼 → `gpt_answer_text` / `gemini_answer_text` /
  `claude_answer_text` 3 컬럼으로 분리. AI 답변은 채널별로 영속 보존된다.
- 신규 스키마는 `CREATE TABLE IF NOT EXISTS` 가 처리. 기존 DB (직전 STEP
  bd387281 시점 단일 answer_text 스키마) 는 `_migrate_legacy_answer_text` 가
  SQLite 권장 패턴 (new table + copy + drop + rename) 으로 무손실 마이그레이션.
  기존 answer_text 값은 `gpt_answer_text` 로 이관 (분리 표기 정보가 없어
  GPT 채널로 가정).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path("state/decision/decision_evidence.sqlite")

# 사용자 1차 판정 enum (지시문 §9).
ALLOWED_USER_VERDICTS = ("useful", "needs_constituents", "needs_market_compare", "hold")
DEFAULT_USER_VERDICT = "hold"

AI_SESSION_RECORDS_DDL = """
CREATE TABLE IF NOT EXISTS ai_session_records (
    id                            TEXT PRIMARY KEY,
    created_at                    TEXT NOT NULL,
    updated_at                    TEXT NOT NULL,
    asof                          TEXT NOT NULL,
    source_screen                 TEXT NOT NULL,
    filters_json                  TEXT NOT NULL,
    candidate_snapshot_json       TEXT NOT NULL,
    question_text                 TEXT NOT NULL,
    gpt_answer_text               TEXT NOT NULL DEFAULT '',
    gemini_answer_text            TEXT NOT NULL DEFAULT '',
    claude_answer_text            TEXT NOT NULL DEFAULT '',
    user_memo                     TEXT NOT NULL DEFAULT '',
    user_verdict                  TEXT NOT NULL,
    next_checks_json              TEXT NOT NULL DEFAULT '[]',
    linked_market_refresh_id      TEXT,
    market_context_snapshot_json  TEXT NOT NULL DEFAULT '{}',
    constituent_snapshot_json     TEXT NOT NULL DEFAULT '{}',
    overlap_snapshot_json         TEXT NOT NULL DEFAULT '{}'
);
""".strip()


# KST 고정 — 사용자가 한국 사용자이고 지시문 응답 예시(+09:00)와 정합.
_KST = timezone(timedelta(hours=9))


def _kst_now_iso() -> str:
    """KST(+09:00) ISO-8601 timestamp, 마이크로초 포함 (정렬 안정성)."""
    return datetime.now(_KST).strftime("%Y-%m-%dT%H:%M:%S.%f%z")


def _generate_id(now: Optional[datetime] = None) -> str:
    """`decision_YYYYMMDDHHMMSS_<hex8>` — 가독성 + 충돌 방지."""
    base = now if now is not None else datetime.now(_KST)
    return f"decision_{base.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _migrate_legacy_answer_text(con: sqlite3.Connection) -> None:
    """단일 answer_text 컬럼 → 3 분리 컬럼 (SQLite 권장 무손실 마이그레이션).

    조건:
    - 기존 테이블이 있고 `gpt_answer_text` 컬럼이 없으며 `answer_text` 컬럼이
      있을 때만 동작.
    - 그 외 (신규 DB / 이미 마이그레이션 완료 / 알 수 없는 스키마) 는 no-op.

    기존 answer_text 값은 gpt_answer_text 로 이관한다 — 직전 STEP 까지는
    어떤 AI 채널의 답변인지 분리되어 있지 않았으므로 GPT 채널로 가정.

    Robust 가드 (사용자 PC 운영 사고 1건 후 추가, 2026-05-21 FIX):
    - 진입 시 잔재 ai_session_records_new (이전 부분 실패의 흔적) 가 있으면
      먼저 drop. sqlite3 의 기본 isolation_level 에서 DDL 은 autocommit 이라
      CREATE 만 영속화되고 INSERT 가 rollback 된 상태가 가능하다.
    - PRAGMA 결과로 가드를 통과해도 실제 SELECT 가능성을 한 번 더 확인한다
      (PRAGMA 와 실제 schema view 의 race condition 방어).
    - 마이그레이션 도중 OperationalError 가 발생하면 _new 잔재를 cleanup
      한 뒤 raise — 다음 호출이 stale 잔재 위에서 동작하지 않도록.
    """
    # 잔재 cleanup — 정상 path 에서는 영향 없음 (테이블 없으면 IF EXISTS 가 무시).
    con.execute("DROP TABLE IF EXISTS ai_session_records_new")

    cur = con.execute("PRAGMA table_info(ai_session_records)")
    cols = {row[1] for row in cur.fetchall()}
    if not cols:
        return
    if "gpt_answer_text" in cols:
        return
    if "answer_text" not in cols:
        return

    # PRAGMA 와 실제 SELECT 가 동의하는지 명시 확인 — 둘이 어긋나면 안전 skip.
    try:
        con.execute("SELECT answer_text FROM ai_session_records LIMIT 0")
    except sqlite3.OperationalError:
        return

    con.execute(
        "CREATE TABLE ai_session_records_new ("
        "id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
        "asof TEXT NOT NULL, source_screen TEXT NOT NULL, "
        "filters_json TEXT NOT NULL, candidate_snapshot_json TEXT NOT NULL, "
        "question_text TEXT NOT NULL, "
        "gpt_answer_text TEXT NOT NULL DEFAULT '', "
        "gemini_answer_text TEXT NOT NULL DEFAULT '', "
        "claude_answer_text TEXT NOT NULL DEFAULT '', "
        "user_memo TEXT NOT NULL DEFAULT '', "
        "user_verdict TEXT NOT NULL, "
        "next_checks_json TEXT NOT NULL DEFAULT '[]', "
        "linked_market_refresh_id TEXT)"
    )
    try:
        con.execute(
            "INSERT INTO ai_session_records_new ("
            "id, created_at, updated_at, asof, source_screen, "
            "filters_json, candidate_snapshot_json, question_text, "
            "gpt_answer_text, gemini_answer_text, claude_answer_text, "
            "user_memo, user_verdict, next_checks_json, linked_market_refresh_id) "
            "SELECT id, created_at, updated_at, asof, source_screen, "
            "filters_json, candidate_snapshot_json, question_text, "
            "answer_text, '', '', "
            "user_memo, user_verdict, next_checks_json, linked_market_refresh_id "
            "FROM ai_session_records"
        )
    except sqlite3.OperationalError:
        # INSERT 실패 시 _new 잔재를 즉시 cleanup 후 raise — 다음 호출이
        # stale 잔재를 보지 않도록.
        con.execute("DROP TABLE IF EXISTS ai_session_records_new")
        raise
    con.execute("DROP TABLE ai_session_records")
    con.execute("ALTER TABLE ai_session_records_new RENAME TO ai_session_records")


def _safe_add_column(con: sqlite3.Connection, sql: str) -> None:
    """ALTER TABLE ADD COLUMN 실행 — 동시 init race 보호 (2026-06-01 FIX).

    PRAGMA 확인 시점과 ALTER 실행 시점 사이에 다른 스레드가 같은 컬럼을
    추가하면 "duplicate column name" OperationalError 가 발생한다. 이는 정상
    race (이미 완료) 이므로 무시. 그 외 OperationalError 는 그대로 re-raise.
    """
    try:
        con.execute(sql)
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            raise


def _migrate_add_market_context_snapshot(con: sqlite3.Connection) -> None:
    """market_context_snapshot_json 컬럼이 없으면 ADD COLUMN 으로 추가.

    SQLite 의 ALTER TABLE ADD COLUMN 은 단순 컬럼 추가만 지원하므로 본 변경은
    DROP/RENAME 패턴 없이 가능. DEFAULT '{}' 로 기존 row 의 결측값을 채운다.
    """
    cur = con.execute("PRAGMA table_info(ai_session_records)")
    cols = {row[1] for row in cur.fetchall()}
    if not cols:
        return
    if "market_context_snapshot_json" in cols:
        return
    _safe_add_column(
        con,
        "ALTER TABLE ai_session_records "
        "ADD COLUMN market_context_snapshot_json TEXT NOT NULL DEFAULT '{}'",
    )


def _migrate_add_constituent_overlap_snapshots(con: sqlite3.Connection) -> None:
    """constituent_snapshot_json / overlap_snapshot_json 컬럼 자동 추가
    (POC2 2026-05-27). 각각 누락 시에만 ADD COLUMN — 누락 1 / 2 모두 안전."""
    cur = con.execute("PRAGMA table_info(ai_session_records)")
    cols = {row[1] for row in cur.fetchall()}
    if not cols:
        return
    if "constituent_snapshot_json" not in cols:
        _safe_add_column(
            con,
            "ALTER TABLE ai_session_records "
            "ADD COLUMN constituent_snapshot_json TEXT NOT NULL DEFAULT '{}'",
        )
    if "overlap_snapshot_json" not in cols:
        _safe_add_column(
            con,
            "ALTER TABLE ai_session_records "
            "ADD COLUMN overlap_snapshot_json TEXT NOT NULL DEFAULT '{}'",
        )


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """DB 파일 + 테이블 보장. 기존 스키마는 자동 마이그레이션.

    마이그레이션 순서:
    1. 신규 스키마로 CREATE TABLE IF NOT EXISTS — 신규 DB 일 때만 효력.
    2. _migrate_legacy_answer_text — 단일 answer_text → 3 분리 (POC2 2026-05-21).
    3. _migrate_add_market_context_snapshot — market_context 컬럼 (2026-05-22).
    4. _migrate_add_constituent_overlap_snapshots — constituent/overlap 2 컬럼
       (POC2 2026-05-27).
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as con:
        con.execute(AI_SESSION_RECORDS_DDL)
        _migrate_legacy_answer_text(con)
        _migrate_add_market_context_snapshot(con)
        _migrate_add_constituent_overlap_snapshots(con)
        con.commit()


@contextmanager
def _connection(db_path: Path):
    init_db(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        yield con
        con.commit()
    finally:
        con.close()


class DecisionValidationError(ValueError):
    """입력 검증 실패 — 422 로 응답될 호출자 에러."""


def _validate_user_verdict(value: str) -> str:
    if value not in ALLOWED_USER_VERDICTS:
        raise DecisionValidationError(
            f"user_verdict must be one of {ALLOWED_USER_VERDICTS}, got {value!r}"
        )
    return value


def insert_record(
    *,
    asof: str,
    source_screen: str,
    filters: dict,
    candidate_snapshot: list[dict],
    question_text: str,
    gpt_answer_text: str,
    gemini_answer_text: str,
    claude_answer_text: str,
    user_memo: str,
    user_verdict: str,
    next_checks: list[str],
    linked_market_refresh_id: Optional[str],
    market_context_snapshot: Optional[dict] = None,
    constituent_snapshot: Optional[dict] = None,
    overlap_snapshot: Optional[dict] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict:
    """신규 ai_session_records 1건 저장 → 저장된 row(요약) 반환.

    검증 규칙 (지시문 §10.1):
    - asof / source_screen / question_text 필수.
    - candidate_snapshot 빈 배열 불가.
    - gpt / gemini / claude 답변 중 **최소 1개 이상** 비어 있지 않아야 한다.
    - user_verdict 는 enum.
    - next_checks 는 배열.
    """
    if not asof:
        raise DecisionValidationError("asof is required.")
    if not source_screen:
        raise DecisionValidationError("source_screen is required.")
    if not candidate_snapshot:
        raise DecisionValidationError("candidate_snapshot must not be empty.")
    if not question_text:
        raise DecisionValidationError("question_text is required.")
    if not (
        (gpt_answer_text and gpt_answer_text.strip())
        or (gemini_answer_text and gemini_answer_text.strip())
        or (claude_answer_text and claude_answer_text.strip())
    ):
        raise DecisionValidationError(
            "At least one of gpt_answer_text / gemini_answer_text / "
            "claude_answer_text must be non-empty."
        )
    _validate_user_verdict(user_verdict)
    if not isinstance(next_checks, list):
        raise DecisionValidationError("next_checks must be a list.")

    now_iso = _kst_now_iso()
    new_id = _generate_id()

    filters_json = json.dumps(filters, ensure_ascii=False, sort_keys=True)
    snapshot_json = json.dumps(candidate_snapshot, ensure_ascii=False)
    next_checks_json = json.dumps(next_checks, ensure_ascii=False)
    market_context_json = json.dumps(market_context_snapshot or {}, ensure_ascii=False)
    constituent_json = json.dumps(constituent_snapshot or {}, ensure_ascii=False)
    overlap_json = json.dumps(overlap_snapshot or {}, ensure_ascii=False)

    with _connection(db_path) as con:
        con.execute(
            "INSERT INTO ai_session_records ("
            "id, created_at, updated_at, asof, source_screen, "
            "filters_json, candidate_snapshot_json, question_text, "
            "gpt_answer_text, gemini_answer_text, claude_answer_text, "
            "user_memo, user_verdict, next_checks_json, "
            "linked_market_refresh_id, market_context_snapshot_json, "
            "constituent_snapshot_json, overlap_snapshot_json"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                new_id,
                now_iso,
                now_iso,
                asof,
                source_screen,
                filters_json,
                snapshot_json,
                question_text,
                gpt_answer_text or "",
                gemini_answer_text or "",
                claude_answer_text or "",
                user_memo or "",
                user_verdict,
                next_checks_json,
                linked_market_refresh_id,
                market_context_json,
                constituent_json,
                overlap_json,
            ),
        )

    return {"id": new_id, "created_at": now_iso}


_SELECT_COLS = (
    "id, created_at, updated_at, asof, source_screen, "
    "filters_json, candidate_snapshot_json, question_text, "
    "gpt_answer_text, gemini_answer_text, claude_answer_text, "
    "user_memo, user_verdict, next_checks_json, linked_market_refresh_id, "
    "market_context_snapshot_json, constituent_snapshot_json, overlap_snapshot_json"
)


def _safe_json(text, default):
    try:
        return json.loads(text or "")
    except (TypeError, ValueError):
        return default


def _row_to_full_dict(row: tuple) -> dict:
    """ai_session_records 전체 컬럼 → dict (JSON 필드 디코딩)."""
    (
        id_,
        created_at,
        updated_at,
        asof,
        source_screen,
        filters_json,
        snapshot_json,
        question_text,
        gpt_answer_text,
        gemini_answer_text,
        claude_answer_text,
        user_memo,
        user_verdict,
        next_checks_json,
        linked_market_refresh_id,
        market_context_snapshot_json,
        constituent_snapshot_json,
        overlap_snapshot_json,
    ) = row
    return {
        "id": id_,
        "created_at": created_at,
        "updated_at": updated_at,
        "asof": asof,
        "source_screen": source_screen,
        "filters": json.loads(filters_json),
        "candidate_snapshot": json.loads(snapshot_json),
        "question_text": question_text,
        "gpt_answer_text": gpt_answer_text or "",
        "gemini_answer_text": gemini_answer_text or "",
        "claude_answer_text": claude_answer_text or "",
        "user_memo": user_memo,
        "user_verdict": user_verdict,
        "next_checks": json.loads(next_checks_json),
        "linked_market_refresh_id": linked_market_refresh_id,
        "market_context_snapshot": _safe_json(market_context_snapshot_json, {}),
        "constituent_snapshot": _safe_json(constituent_snapshot_json, {}),
        "overlap_snapshot": _safe_json(overlap_snapshot_json, {}),
    }


def _summary_text(record: dict) -> str:
    """목록 표시용 요약 (앞 50자).

    우선순위: user_memo → gpt_answer_text → gemini_answer_text →
    claude_answer_text → question_text. 첫 번째 비어있지 않은 텍스트를 사용.
    """
    for key in (
        "user_memo",
        "gpt_answer_text",
        "gemini_answer_text",
        "claude_answer_text",
        "question_text",
    ):
        text = (record.get(key) or "").strip()
        if text:
            return text[:50]
    return ""


def list_recent_records(
    *,
    limit: int = 10,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """최근 created_at DESC 순 N건 — 목록용 축약 dict 리스트.

    each item 에 `has_gpt_answer / has_gemini_answer / has_claude_answer` boolean
    포함 (지시문 §10.2).
    """
    if limit <= 0:
        return []
    with _connection(db_path) as con:
        cur = con.execute(
            f"SELECT {_SELECT_COLS} FROM ai_session_records "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (int(limit),),
        )
        rows = cur.fetchall()

    out: list[dict] = []
    for row in rows:
        full = _row_to_full_dict(row)
        out.append(
            {
                "id": full["id"],
                "created_at": full["created_at"],
                "asof": full["asof"],
                "source_screen": full["source_screen"],
                "user_verdict": full["user_verdict"],
                "summary": _summary_text(full),
                "candidate_count": len(full["candidate_snapshot"]),
                "has_gpt_answer": bool(full["gpt_answer_text"].strip()),
                "has_gemini_answer": bool(full["gemini_answer_text"].strip()),
                "has_claude_answer": bool(full["claude_answer_text"].strip()),
            }
        )
    return out


def get_record(record_id: str, *, db_path: Path = DEFAULT_DB_PATH) -> Optional[dict]:
    """단일 record 전체 — 없으면 None."""
    with _connection(db_path) as con:
        cur = con.execute(
            f"SELECT {_SELECT_COLS} FROM ai_session_records WHERE id = ?",
            (record_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return _row_to_full_dict(row)
