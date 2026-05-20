"""Decision Evidence SQLite 저장소 (POC2 — AI 투자세션 기록 1차).

본 모듈은 다음 1개 테이블만 관리한다:
- ai_session_records: AI 질문 / 답변 / 사용자 메모 / 1차 판정 / 후보 스냅샷 / 필터 스냅샷.

DB 파일은 시장 데이터(`state/market/market_data.sqlite`) 와 분리된
`state/decision/decision_evidence.sqlite` 다. 두 도메인을 같은 DB 파일에
섞지 않는다 (PROJECT_ORIGIN_INTENT §10 — 데이터 종류별 SSOT 분리).

본 모듈은 매수/매도 판단 / 매매 결과 추적 / ML 점수 저장을 하지 않는다.
이 STEP 의 범위는 "질문 + 답변 + 메모 + 1차 판정" 까지다.
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

# 사용자 1차 판정 enum (지시문 §5).
ALLOWED_USER_VERDICTS = ("useful", "needs_constituents", "needs_market_compare", "hold")
DEFAULT_USER_VERDICT = "hold"

AI_SESSION_RECORDS_DDL = """
CREATE TABLE IF NOT EXISTS ai_session_records (
    id                        TEXT PRIMARY KEY,
    created_at                TEXT NOT NULL,
    updated_at                TEXT NOT NULL,
    asof                      TEXT NOT NULL,
    source_screen             TEXT NOT NULL,
    filters_json              TEXT NOT NULL,
    candidate_snapshot_json   TEXT NOT NULL,
    question_text             TEXT NOT NULL,
    answer_text               TEXT NOT NULL,
    user_memo                 TEXT NOT NULL DEFAULT '',
    user_verdict              TEXT NOT NULL,
    next_checks_json          TEXT NOT NULL DEFAULT '[]',
    linked_market_refresh_id  TEXT
);
""".strip()


# KST 고정 — 사용자가 한국 사용자이고 지시문 응답 예시(+09:00)와 정합.
# market_data_store 의 UTC Z 와는 다른 DB 파일이라 시간대 통일 강제 없음.
_KST = timezone(timedelta(hours=9))


def _kst_now_iso() -> str:
    """KST(+09:00) ISO-8601 timestamp.

    마이크로초까지 포함한다 — created_at 을 정렬 키로 사용할 때 같은 초 안에
    연속 insert 가 발생해도 안정적으로 순서가 유지되도록.
    응답 노출 시점에는 그대로 ISO-8601 valid 문자열.
    """
    return datetime.now(_KST).strftime("%Y-%m-%dT%H:%M:%S.%f%z")


def _generate_id(now: Optional[datetime] = None) -> str:
    """`decision_YYYYMMDDHHMMSS_<hex8>` — 가독성 + 충돌 방지."""
    base = now if now is not None else datetime.now(_KST)
    return f"decision_{base.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """DB 파일 + 테이블 보장. 시장 데이터 DB 와는 별도 파일."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as con:
        con.execute(AI_SESSION_RECORDS_DDL)
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
    answer_text: str,
    user_memo: str,
    user_verdict: str,
    next_checks: list[str],
    linked_market_refresh_id: Optional[str],
    db_path: Path = DEFAULT_DB_PATH,
) -> dict:
    """신규 ai_session_records 1건 저장 → 저장된 row(요약) 반환.

    - id 는 `decision_YYYYMMDDHHMMSS_<hex8>` 로 자동 생성 (호출자 지정 금지).
    - created_at = updated_at = 저장 시각 (KST iso). 이번 STEP 은 수정 기능 없음.
    - candidate_snapshot 은 비어있으면 안 된다 (지시문 §6.1 검증 규칙).
    - 모든 JSON 필드는 ensure_ascii=False 로 한국어 그대로 저장.
    """
    if not asof:
        raise DecisionValidationError("asof is required.")
    if not source_screen:
        raise DecisionValidationError("source_screen is required.")
    if not candidate_snapshot:
        raise DecisionValidationError("candidate_snapshot must not be empty.")
    if not question_text:
        raise DecisionValidationError("question_text is required.")
    if not answer_text:
        raise DecisionValidationError("answer_text is required.")
    _validate_user_verdict(user_verdict)
    if not isinstance(next_checks, list):
        raise DecisionValidationError("next_checks must be a list.")

    now_iso = _kst_now_iso()
    new_id = _generate_id()

    filters_json = json.dumps(filters, ensure_ascii=False, sort_keys=True)
    snapshot_json = json.dumps(candidate_snapshot, ensure_ascii=False)
    next_checks_json = json.dumps(next_checks, ensure_ascii=False)

    with _connection(db_path) as con:
        con.execute(
            "INSERT INTO ai_session_records ("
            "id, created_at, updated_at, asof, source_screen, "
            "filters_json, candidate_snapshot_json, question_text, "
            "answer_text, user_memo, user_verdict, next_checks_json, "
            "linked_market_refresh_id"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                new_id,
                now_iso,
                now_iso,
                asof,
                source_screen,
                filters_json,
                snapshot_json,
                question_text,
                answer_text,
                user_memo or "",
                user_verdict,
                next_checks_json,
                linked_market_refresh_id,
            ),
        )

    return {"id": new_id, "created_at": now_iso}


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
        answer_text,
        user_memo,
        user_verdict,
        next_checks_json,
        linked_market_refresh_id,
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
        "answer_text": answer_text,
        "user_memo": user_memo,
        "user_verdict": user_verdict,
        "next_checks": json.loads(next_checks_json),
        "linked_market_refresh_id": linked_market_refresh_id,
    }


def _summary_text(record: dict) -> str:
    """목록 표시용 요약 (지시문 §7.3 우선순위: memo → answer → question, 앞 50자)."""
    for key in ("user_memo", "answer_text", "question_text"):
        text = (record.get(key) or "").strip()
        if text:
            return text[:50]
    return ""


def list_recent_records(
    *,
    limit: int = 10,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """최근 created_at DESC 순 N건 — 목록용 축약 dict 리스트."""
    if limit <= 0:
        return []
    with _connection(db_path) as con:
        cur = con.execute(
            "SELECT id, created_at, updated_at, asof, source_screen, "
            "filters_json, candidate_snapshot_json, question_text, "
            "answer_text, user_memo, user_verdict, next_checks_json, "
            "linked_market_refresh_id FROM ai_session_records "
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
            }
        )
    return out


def get_record(record_id: str, *, db_path: Path = DEFAULT_DB_PATH) -> Optional[dict]:
    """단일 record 전체 — 없으면 None."""
    with _connection(db_path) as con:
        cur = con.execute(
            "SELECT id, created_at, updated_at, asof, source_screen, "
            "filters_json, candidate_snapshot_json, question_text, "
            "answer_text, user_memo, user_verdict, next_checks_json, "
            "linked_market_refresh_id FROM ai_session_records WHERE id = ?",
            (record_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return _row_to_full_dict(row)
