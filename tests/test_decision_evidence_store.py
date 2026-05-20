"""Decision Evidence SQLite store 단위 테스트 (POC2 — AI 투자세션 기록 1차)."""

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
        answer_text="AI 답변 전문",
        user_memo="사용자 메모",
        user_verdict="needs_constituents",
        next_checks=["KODEX200 대비 초과수익 확인"],
        linked_market_refresh_id=None,
    )
    base.update(override)
    return base


def test_init_db_creates_table(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    init_db(db)
    with sqlite3.connect(str(db)) as con:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='ai_session_records'"
        )
        assert cur.fetchone() is not None


def test_insert_record_persists_all_fields(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    saved = insert_record(db_path=db, **_minimal_kwargs())

    assert saved["id"].startswith("decision_")
    assert saved["created_at"]

    fetched = get_record(saved["id"], db_path=db)
    assert fetched is not None
    assert fetched["asof"] == "2026-05-15"
    assert fetched["source_screen"] == "market_discovery"
    assert fetched["question_text"] == "AI 에게 보낸 질문 전문"
    assert fetched["answer_text"] == "AI 답변 전문"
    assert fetched["user_memo"] == "사용자 메모"
    assert fetched["user_verdict"] == "needs_constituents"
    assert fetched["next_checks"] == ["KODEX200 대비 초과수익 확인"]
    assert fetched["linked_market_refresh_id"] is None
    # snapshot + filters 가 JSON 으로 round-trip.
    assert len(fetched["candidate_snapshot"]) == 1
    assert fetched["candidate_snapshot"][0]["ticker"] == "139260"
    assert fetched["filters"]["exclude_inverse"] is True
    # 이번 STEP 은 수정 기능 없음 — created_at == updated_at.
    assert fetched["created_at"] == fetched["updated_at"]


def test_insert_record_rejects_empty_candidate_snapshot(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    with pytest.raises(DecisionValidationError):
        insert_record(db_path=db, **_minimal_kwargs(candidate_snapshot=[]))


def test_insert_record_rejects_invalid_user_verdict(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    with pytest.raises(DecisionValidationError):
        insert_record(db_path=db, **_minimal_kwargs(user_verdict="buy_now"))


def test_user_verdict_enum_constants():
    # 지시문 §5 — 4개 enum 값만 허용 + default hold.
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
    assert all("summary" in r for r in records)
    assert records[0]["candidate_count"] == 1


def test_list_recent_records_summary_priority(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    # user_memo 있으면 memo 우선.
    saved_a = insert_record(
        db_path=db,
        **_minimal_kwargs(
            user_memo="메모 우선 표시", answer_text="답변", question_text="질문"
        ),
    )
    # user_memo 없으면 answer.
    saved_b = insert_record(
        db_path=db,
        **_minimal_kwargs(user_memo="", answer_text="답변 우선", question_text="질문"),
    )
    rows = list_recent_records(limit=10, db_path=db)
    by_id = {r["id"]: r for r in rows}
    assert by_id[saved_a["id"]]["summary"] == "메모 우선 표시"
    assert by_id[saved_b["id"]]["summary"] == "답변 우선"


def test_get_record_returns_none_when_missing(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    init_db(db)
    assert get_record("decision_unknown_id", db_path=db) is None


def test_list_recent_records_respects_limit(tmp_path: Path):
    db = tmp_path / "decision_evidence.sqlite"
    for i in range(5):
        insert_record(db_path=db, **_minimal_kwargs(asof=f"2026-05-1{i}"))
    assert len(list_recent_records(limit=3, db_path=db)) == 3
