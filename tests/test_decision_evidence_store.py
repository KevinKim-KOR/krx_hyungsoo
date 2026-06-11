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


def test_init_db_auto_adds_constituent_and_overlap_snapshot_columns(tmp_path: Path):
    """직전 STEP (market_context_snapshot 컬럼까지 있는 스키마) DB 에 대해
    init_db() 가 constituent/overlap snapshot 컬럼 2개를 자동 ADD COLUMN."""
    db = tmp_path / "decision_evidence.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    # 직전 STEP 시점 DDL — constituent/overlap 컬럼 없음.
    prev_ddl = (
        "CREATE TABLE ai_session_records ("
        "id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
        "asof TEXT NOT NULL, source_screen TEXT NOT NULL, "
        "filters_json TEXT NOT NULL, candidate_snapshot_json TEXT NOT NULL, "
        "question_text TEXT NOT NULL, "
        "gpt_answer_text TEXT NOT NULL DEFAULT '', "
        "gemini_answer_text TEXT NOT NULL DEFAULT '', "
        "claude_answer_text TEXT NOT NULL DEFAULT '', "
        "user_memo TEXT NOT NULL DEFAULT '', user_verdict TEXT NOT NULL, "
        "next_checks_json TEXT NOT NULL DEFAULT '[]', "
        "linked_market_refresh_id TEXT, "
        "market_context_snapshot_json TEXT NOT NULL DEFAULT '{}')"
    )
    with sqlite3.connect(str(db)) as con:
        con.execute(prev_ddl)
        con.commit()

    init_db(db)

    with sqlite3.connect(str(db)) as con:
        cur = con.execute("PRAGMA table_info(ai_session_records)")
        cols = {row[1] for row in cur.fetchall()}
    assert "constituent_snapshot_json" in cols
    assert "overlap_snapshot_json" in cols

    saved = insert_record(
        db_path=db,
        **_minimal_kwargs(),
        constituent_snapshot={"items": [{"etf_ticker": "139260"}]},
        overlap_snapshot={"matrix": [{"left_ticker": "139260"}]},
    )
    fetched = get_record(saved["id"], db_path=db)
    assert fetched["constituent_snapshot"]["items"][0]["etf_ticker"] == "139260"
    assert fetched["overlap_snapshot"]["matrix"][0]["left_ticker"] == "139260"


def test_init_db_auto_adds_market_context_snapshot_column(tmp_path: Path):
    """직전 STEP (3 분리 스키마, market_context_snapshot 컬럼 없음) DB 에 대해
    init_db() 가 ALTER TABLE ADD COLUMN 으로 자동 마이그레이션."""
    db = tmp_path / "decision_evidence.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    # 직전 STEP 시점 DDL — market_context_snapshot_json 컬럼 없음.
    prev_ddl = (
        "CREATE TABLE ai_session_records ("
        "id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
        "asof TEXT NOT NULL, source_screen TEXT NOT NULL, "
        "filters_json TEXT NOT NULL, candidate_snapshot_json TEXT NOT NULL, "
        "question_text TEXT NOT NULL, "
        "gpt_answer_text TEXT NOT NULL DEFAULT '', "
        "gemini_answer_text TEXT NOT NULL DEFAULT '', "
        "claude_answer_text TEXT NOT NULL DEFAULT '', "
        "user_memo TEXT NOT NULL DEFAULT '', user_verdict TEXT NOT NULL, "
        "next_checks_json TEXT NOT NULL DEFAULT '[]', "
        "linked_market_refresh_id TEXT)"
    )
    with sqlite3.connect(str(db)) as con:
        con.execute(prev_ddl)
        con.commit()

    init_db(db)

    with sqlite3.connect(str(db)) as con:
        cur = con.execute("PRAGMA table_info(ai_session_records)")
        cols = {row[1] for row in cur.fetchall()}
    assert "market_context_snapshot_json" in cols

    # 신규 insert 가 정상 동작 + market_context_snapshot 저장 round-trip.
    saved = insert_record(
        db_path=db,
        **_minimal_kwargs(),
        market_context_snapshot={"regime_label": "상승장", "regime_code": "bull"},
    )
    fetched = get_record(saved["id"], db_path=db)
    assert fetched["market_context_snapshot"]["regime_label"] == "상승장"


def test_init_db_cleans_up_stale_ai_session_records_new(tmp_path: Path):
    """이전 부분 마이그레이션 잔재 (ai_session_records_new 테이블) 가 있을 때
    init_db() 가 호출되면 잔재를 자동 cleanup 한다.

    재현: 운영 사고 1건 (2026-05-21) — 사용자 PC 에서 마이그레이션이 부분
    진행되어 ai_session_records 는 이미 신규 스키마인데 ai_session_records_new
    잔재가 남아 다음 init_db 가 같은 INSERT 를 재시도 → no-op 가드 통과 후에도
    엉뚱한 컬럼 에러를 만들 수 있는 상태.
    """
    db = tmp_path / "decision_evidence.sqlite"
    # 1) 정상 신규 DB 만들기 (3 분리 스키마).
    init_db(db)
    # 2) 의도적으로 잔재 _new 테이블 주입.
    with sqlite3.connect(str(db)) as con:
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
        con.commit()

    # 3) init_db 재호출 → 잔재 cleanup.
    init_db(db)
    with sqlite3.connect(str(db)) as con:
        tables = {
            row[0]
            for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "ai_session_records" in tables
    assert "ai_session_records_new" not in tables

    # 4) 정상 insert/조회 동작 확인.
    saved = insert_record(db_path=db, **_minimal_kwargs())
    assert get_record(saved["id"], db_path=db) is not None


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


def test_migration_concurrent_init_does_not_raise(tmp_path: Path):
    """2026-06-01 FIX (운영 사고 1건 후속) — FastAPI threadpool 에서 AI Sessions
    조회 등 API 가 동시 호출될 때, _connection() → init_db() →
    _migrate_add_market_context_snapshot / _migrate_add_constituent_overlap_snapshots
    가 매번 실행된다. PRAGMA 확인 시점과 ALTER 실행 시점 사이 race 로
    duplicate column 오류 발생. 본 회귀 — 8 스레드 동시 init 예외 0.
    """
    import threading

    db = tmp_path / "m.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    # 직전 스키마 — market_context / constituent / overlap 3 컬럼 없음 (마이그레이션 trigger).
    prev_ddl = (
        "CREATE TABLE ai_session_records ("
        "id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
        "asof TEXT NOT NULL, source_screen TEXT NOT NULL, filters_json TEXT NOT NULL, "
        "candidate_snapshot_json TEXT NOT NULL, question_text TEXT NOT NULL, "
        "gpt_answer_text TEXT NOT NULL DEFAULT '', "
        "gemini_answer_text TEXT NOT NULL DEFAULT '', "
        "claude_answer_text TEXT NOT NULL DEFAULT '', "
        "user_memo TEXT NOT NULL DEFAULT '', user_verdict TEXT NOT NULL DEFAULT 'pending', "
        "next_checks_json TEXT NOT NULL DEFAULT '[]', "
        "linked_market_refresh_id TEXT)"
    )
    with sqlite3.connect(str(db)) as con:
        con.execute(prev_ddl)
        con.commit()

    errors: list[BaseException] = []

    def _worker():
        try:
            init_db(db)
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    # 결과적으로 3 컬럼 모두 정상 추가.
    with sqlite3.connect(str(db)) as con:
        cur = con.execute("PRAGMA table_info(ai_session_records)")
        cols = {row[1] for row in cur.fetchall()}
    assert {
        "market_context_snapshot_json",
        "constituent_snapshot_json",
        "overlap_snapshot_json",
        "short_term_momentum_snapshot_json",
        "data_quality_snapshot_json",
    } <= cols


def test_insert_record_with_closeout_snapshots(tmp_path: Path):
    """2026-06-01 Market Discovery Evidence Closeout 1차 — short_term_momentum
    + data_quality snapshot 이 정상 저장 + 조회된다 (AC-17 / AC-18 / AC-19)."""
    from app.decision_evidence_store import get_record, insert_record

    db = tmp_path / "decision.sqlite"
    saved = insert_record(
        **_minimal_kwargs(
            short_term_momentum_snapshot={
                "asof": "2026-05-31",
                "benchmark": "KODEX200",
                "items": [
                    {
                        "ticker": "266390",
                        "name": "KODEX 경기소비재",
                        "return_5d_pct": 18.42,
                        "excess_vs_kodex200_5d_pctp": 5.12,
                    }
                ],
            },
            data_quality_snapshot={
                "asof": "2026-05-31",
                "items": [
                    {
                        "ticker": "266390",
                        "daily_return_check": {
                            "status": "warning",
                            "daily_return_pct": 23.86,
                            "flag": "daily_surge_check_needed",
                        },
                        "nav_discount": {
                            "status": "unavailable",
                            "source": None,
                        },
                        "warnings": ["daily_surge_check_needed"],
                    }
                ],
            },
        ),
        db_path=db,
    )
    fetched = get_record(saved["id"], db_path=db)
    assert fetched is not None
    s = fetched["short_term_momentum_snapshot"]
    assert s["benchmark"] == "KODEX200"
    assert s["items"][0]["return_5d_pct"] == 18.42
    d = fetched["data_quality_snapshot"]
    assert d["items"][0]["daily_return_check"]["flag"] == "daily_surge_check_needed"


def test_insert_record_without_closeout_snapshots_defaults_to_empty(
    tmp_path: Path,
):
    """본 STEP 이전 호출자는 신규 snapshot 을 보내지 않는다. 기존 흐름 무변경."""
    from app.decision_evidence_store import get_record, insert_record

    db = tmp_path / "decision.sqlite"
    saved = insert_record(**_minimal_kwargs(), db_path=db)
    fetched = get_record(saved["id"], db_path=db)
    assert fetched is not None
    assert fetched["short_term_momentum_snapshot"] == {}
    assert fetched["data_quality_snapshot"] == {}
    # 2026-06-11 — ML Baseline Evidence Draft Integration. 신규 컬럼도
    # 기본값이 빈 dict 로 안전하게 반환된다.
    assert fetched["ml_baseline_evidence_snapshot"] == {}


# ─── 2026-06-11 ML Baseline Evidence Draft Integration ─────────────


def test_insert_record_with_ml_baseline_evidence_snapshot(tmp_path: Path):
    """ml_baseline_evidence_snapshot 이 저장 + 조회된다."""
    from app.decision_evidence_store import get_record, insert_record

    db = tmp_path / "decision.sqlite"
    snap = {
        "status": "ok",
        "report_status": "ok",
        "report_path": "state/ml/ml_baseline_v0_report_latest.json",
        "feature_asof_range": {"start": "2026-03-11", "end": "2026-06-08"},
        "evaluated_asof_range": {
            "start": "2026-03-11",
            "end": "2026-05-10",
            "evaluated_days": 40,
        },
        "candidate_summary": {
            "status": "ok",
            "evaluated_days": 40,
            "top_group_avg_future_return": {"20d": 0.1351},
        },
        "risk_summary": {
            "status": "ok",
            "high_risk_group_future_drawdown": {"10d": -0.0809},
        },
        "leakage_summary": {
            "future_data_leakage_detected": False,
            "tail_excluded": True,
            "time_order_preserved": True,
        },
        "limitations": ["평가 기간이 짧아 장기 안정성 검증은 아닙니다."],
        "external_context_checklist": [
            "CNN Fear & Greed 현재 수준",
            "원유 가격 급등 여부",
        ],
    }
    saved = insert_record(
        **_minimal_kwargs(ml_baseline_evidence_snapshot=snap), db_path=db
    )
    fetched = get_record(saved["id"], db_path=db)
    assert fetched is not None
    got = fetched["ml_baseline_evidence_snapshot"]
    assert got["status"] == "ok"
    assert got["candidate_summary"]["evaluated_days"] == 40
    assert got["risk_summary"]["high_risk_group_future_drawdown"]["10d"] == -0.0809
    assert got["leakage_summary"]["future_data_leakage_detected"] is False
    assert "CNN Fear & Greed 현재 수준" in got["external_context_checklist"]


def test_ml_baseline_evidence_column_present_after_migration(tmp_path: Path):
    """init_db 후 ml_baseline_evidence_snapshot_json 컬럼이 항상 존재."""
    import sqlite3

    from app.decision_evidence_store import init_db

    db = tmp_path / "decision.sqlite"
    init_db(db_path=db)
    with sqlite3.connect(str(db)) as con:
        cur = con.execute("PRAGMA table_info(ai_session_records)")
        cols = {row[1] for row in cur.fetchall()}
    assert "ml_baseline_evidence_snapshot_json" in cols


def test_legacy_db_migrates_ml_baseline_evidence_column(tmp_path: Path):
    """ml 컬럼이 없는 legacy DB 가 자동 마이그레이션된다."""
    import sqlite3

    from app.decision_evidence_store import init_db

    db = tmp_path / "decision.sqlite"
    # legacy: 신규 컬럼 누락한 옛 DDL.
    legacy_ddl = """
    CREATE TABLE ai_session_records (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        asof TEXT NOT NULL,
        source_screen TEXT NOT NULL,
        filters_json TEXT NOT NULL,
        candidate_snapshot_json TEXT NOT NULL,
        question_text TEXT NOT NULL,
        gpt_answer_text TEXT NOT NULL DEFAULT '',
        gemini_answer_text TEXT NOT NULL DEFAULT '',
        claude_answer_text TEXT NOT NULL DEFAULT '',
        user_memo TEXT NOT NULL DEFAULT '',
        user_verdict TEXT NOT NULL,
        next_checks_json TEXT NOT NULL DEFAULT '[]',
        linked_market_refresh_id TEXT,
        market_context_snapshot_json TEXT NOT NULL DEFAULT '{}',
        constituent_snapshot_json TEXT NOT NULL DEFAULT '{}',
        overlap_snapshot_json TEXT NOT NULL DEFAULT '{}',
        short_term_momentum_snapshot_json TEXT NOT NULL DEFAULT '{}',
        data_quality_snapshot_json TEXT NOT NULL DEFAULT '{}'
    );
    """.strip()
    with sqlite3.connect(str(db)) as con:
        con.execute(legacy_ddl)
        con.commit()

    init_db(db_path=db)

    with sqlite3.connect(str(db)) as con:
        cur = con.execute("PRAGMA table_info(ai_session_records)")
        cols = {row[1] for row in cur.fetchall()}
    assert "ml_baseline_evidence_snapshot_json" in cols
