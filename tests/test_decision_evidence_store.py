"""Decision Evidence SQLite store 단위 테스트.

2026-05-21 갱신 (AI Sessions / Context Bridge):
- 단일 answer_text → gpt/gemini/claude 3 분리 필드 검증.
- 최소 1개 답변 필수 검증.
- 단일 answer_text 스키마 → 3 분리 자동 마이그레이션 검증.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.decision_evidence_store import (
    ALLOWED_USER_VERDICTS,
    DEFAULT_USER_VERDICT,
    DecisionValidationError,
    get_record,
    init_db,
    insert_record,
    list_recent_records,
)


def _minimal_kwargs(**override):
    base = dict(
        asof="2026-05-15",
        source_screen="market_discovery",
        filters={
            "exclude_inverse": True,
            "exclude_leveraged": True,
            "exclude_synthetic": True,
            "exclude_futures": True,
        },
        candidate_snapshot=[
            {
                "rank": 1,
                "ticker": "139260",
                "name": "TIGER 200 IT",
                "daily_return_pct": -3.73,
                "one_month_return_pct": 49.87,
                "three_month_return_pct": 82.05,
                "tags": [],
            }
        ],
        question_text="AI 에게 보낸 질문 전문",
        gpt_answer_text="GPT 답변 전문",
        gemini_answer_text="",
        claude_answer_text="",
        user_memo="사용자 메모",
        user_verdict="needs_constituents",
        next_checks=["KODEX200 대비 초과수익 확인"],
        linked_market_refresh_id=None,
    )
    base.update(override)
    return base


def test_init_db_creates_table_with_three_answer_columns(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    init_db(db)
    with sqlite3.connect(str(db)) as con:
        cur = con.execute("PRAGMA table_info(ai_session_records)")
        cols = {row[1] for row in cur.fetchall()}
    assert {"gpt_answer_text", "gemini_answer_text", "claude_answer_text"} <= cols
    # 단일 answer_text 가 신규 DB 에 자동 생성되어서는 안 된다 (스키마 분리 의도).
    assert "answer_text" not in cols


def test_insert_record_persists_all_three_answers(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    saved = insert_record(
        db_path=db,
        **_minimal_kwargs(
            gpt_answer_text="GPT 답변 전문",
            gemini_answer_text="Gemini 답변 전문",
            claude_answer_text="Claude 답변 전문",
        ),
    )

    fetched = get_record(saved["id"], db_path=db)
    assert fetched is not None
    assert fetched["gpt_answer_text"] == "GPT 답변 전문"
    assert fetched["gemini_answer_text"] == "Gemini 답변 전문"
    assert fetched["claude_answer_text"] == "Claude 답변 전문"
    assert fetched["question_text"] == "AI 에게 보낸 질문 전문"
    assert fetched["user_verdict"] == "needs_constituents"
    # created_at == updated_at (이번 STEP 수정 기능 없음).
    assert fetched["created_at"] == fetched["updated_at"]


def test_insert_record_accepts_only_one_answer(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    # GPT 만.
    saved_gpt = insert_record(
        db_path=db,
        **_minimal_kwargs(
            gpt_answer_text="GPT only", gemini_answer_text="", claude_answer_text=""
        ),
    )
    # Gemini 만.
    saved_gemini = insert_record(
        db_path=db,
        **_minimal_kwargs(
            gpt_answer_text="", gemini_answer_text="Gemini only", claude_answer_text=""
        ),
    )
    # Claude 만.
    saved_claude = insert_record(
        db_path=db,
        **_minimal_kwargs(
            gpt_answer_text="", gemini_answer_text="", claude_answer_text="Claude only"
        ),
    )
    assert all(
        s["id"].startswith("decision_") for s in (saved_gpt, saved_gemini, saved_claude)
    )


def test_insert_record_rejects_all_empty_answers(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    with pytest.raises(DecisionValidationError):
        insert_record(
            db_path=db,
            **_minimal_kwargs(
                gpt_answer_text="",
                gemini_answer_text="",
                claude_answer_text="",
            ),
        )
    # whitespace-only 도 비어 있는 것으로 간주.
    with pytest.raises(DecisionValidationError):
        insert_record(
            db_path=db,
            **_minimal_kwargs(
                gpt_answer_text="   ",
                gemini_answer_text="\n\t",
                claude_answer_text=" ",
            ),
        )


def test_insert_record_rejects_empty_candidate_snapshot(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    with pytest.raises(DecisionValidationError):
        insert_record(db_path=db, **_minimal_kwargs(candidate_snapshot=[]))


def test_insert_record_rejects_invalid_user_verdict(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    with pytest.raises(DecisionValidationError):
        insert_record(db_path=db, **_minimal_kwargs(user_verdict="buy_now"))


def test_user_verdict_enum_constants():
    assert ALLOWED_USER_VERDICTS == (
        "useful",
        "needs_constituents",
        "needs_market_compare",
        "hold",
    )
    assert DEFAULT_USER_VERDICT == "hold"


def test_list_recent_records_orders_by_created_at_desc(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    id1 = insert_record(db_path=db, **_minimal_kwargs(asof="2026-05-13"))["id"]
    id2 = insert_record(db_path=db, **_minimal_kwargs(asof="2026-05-14"))["id"]
    id3 = insert_record(db_path=db, **_minimal_kwargs(asof="2026-05-15"))["id"]

    records = list_recent_records(limit=10, db_path=db)
    assert [r["id"] for r in records] == [id3, id2, id1]


def test_list_recent_records_includes_has_answer_flags(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    insert_record(
        db_path=db,
        **_minimal_kwargs(
            gpt_answer_text="GPT", gemini_answer_text="", claude_answer_text=""
        ),
    )
    insert_record(
        db_path=db,
        **_minimal_kwargs(
            gpt_answer_text="",
            gemini_answer_text="Gemini",
            claude_answer_text="Claude",
        ),
    )

    records = list_recent_records(limit=10, db_path=db)
    # 가장 최근 (두 번째 insert) — Gemini + Claude.
    latest = records[0]
    assert latest["has_gpt_answer"] is False
    assert latest["has_gemini_answer"] is True
    assert latest["has_claude_answer"] is True
    # 두 번째 (첫 insert) — GPT only.
    earlier = records[1]
    assert earlier["has_gpt_answer"] is True
    assert earlier["has_gemini_answer"] is False
    assert earlier["has_claude_answer"] is False


def test_list_recent_records_summary_priority(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    # memo 가 있으면 memo 우선.
    saved_a = insert_record(
        db_path=db,
        **_minimal_kwargs(
            user_memo="메모 우선 표시",
            gpt_answer_text="답변",
            question_text="질문",
        ),
    )
    # memo 없으면 gpt_answer_text.
    saved_b = insert_record(
        db_path=db,
        **_minimal_kwargs(
            user_memo="",
            gpt_answer_text="GPT 답변 우선",
            gemini_answer_text="",
            claude_answer_text="",
        ),
    )
    # memo 없고 gpt 없으면 gemini.
    saved_c = insert_record(
        db_path=db,
        **_minimal_kwargs(
            user_memo="",
            gpt_answer_text="",
            gemini_answer_text="Gemini 답변 우선",
            claude_answer_text="",
        ),
    )
    rows = list_recent_records(limit=10, db_path=db)
    by_id = {r["id"]: r for r in rows}
    assert by_id[saved_a["id"]]["summary"] == "메모 우선 표시"
    assert by_id[saved_b["id"]]["summary"] == "GPT 답변 우선"
    assert by_id[saved_c["id"]]["summary"] == "Gemini 답변 우선"


def test_get_record_returns_none_when_missing(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    init_db(db)
    assert get_record("decision_unknown_id", db_path=db) is None


def test_list_recent_records_respects_limit(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    for i in range(5):
        insert_record(db_path=db, **_minimal_kwargs(asof=f"2026-05-1{i}"))
    assert len(list_recent_records(limit=3, db_path=db)) == 3


def test_legacy_single_answer_text_schema_auto_migrates(tmp_path: Path):
    """직전 STEP 의 단일 answer_text DB 가 init_db 호출 시 무손실 마이그레이션.

    재현: 직전 STEP 의 DDL 로 테이블 생성 + 1건 insert → init_db() 호출 →
    스키마 자동 변환 + 기존 answer_text 값이 gpt_answer_text 로 이관 확인.
    """
    db = tmp_path / "decision_evidence.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)

    legacy_ddl = (
        "CREATE TABLE ai_session_records ("
        "id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
        "asof TEXT NOT NULL, source_screen TEXT NOT NULL, "
        "filters_json TEXT NOT NULL, candidate_snapshot_json TEXT NOT NULL, "
        "question_text TEXT NOT NULL, answer_text TEXT NOT NULL, "
        "user_memo TEXT NOT NULL DEFAULT '', user_verdict TEXT NOT NULL, "
        "next_checks_json TEXT NOT NULL DEFAULT '[]', "
        "linked_market_refresh_id TEXT)"
    )
    with sqlite3.connect(str(db)) as con:
        con.execute(legacy_ddl)
        con.execute(
            "INSERT INTO ai_session_records ("
            "id, created_at, updated_at, asof, source_screen, "
            "filters_json, candidate_snapshot_json, question_text, "
            "answer_text, user_memo, user_verdict, next_checks_json, "
            "linked_market_refresh_id) VALUES ("
            "'decision_legacy_001', '2026-05-20T12:00:00.000000+0900', "
            "'2026-05-20T12:00:00.000000+0900', '2026-05-15', 'market_discovery', "
            "'{}', '[{\"ticker\":\"139260\"}]', '직전 STEP 질문', "
            "'직전 STEP 단일 답변', '', 'hold', '[]', NULL)"
        )
        con.commit()

    # init_db 가 마이그레이션 trigger.
    init_db(db)

    with sqlite3.connect(str(db)) as con:
        cur = con.execute("PRAGMA table_info(ai_session_records)")
        cols = {row[1] for row in cur.fetchall()}
    assert {"gpt_answer_text", "gemini_answer_text", "claude_answer_text"} <= cols
    assert "answer_text" not in cols  # legacy 컬럼은 drop 됨.

    # 기존 데이터는 그대로 + answer_text → gpt_answer_text 이관 확인.
    fetched = get_record("decision_legacy_001", db_path=db)
    assert fetched is not None
    assert fetched["gpt_answer_text"] == "직전 STEP 단일 답변"
    assert fetched["gemini_answer_text"] == ""
    assert fetched["claude_answer_text"] == ""
    assert fetched["question_text"] == "직전 STEP 질문"
