"""POC5-24 — 선택 근거(「보유와 비교」 판단 근거 미리보기)의 AI 세션 저장 · 재조회.

모든 시험은 임시 DB(tmp_path) — 라이브 `state/decision/decision_evidence.sqlite` 를 열지 않는다.
실제 API(POST → GET 목록 · 상세) 왕복으로 `selected_preview` 유실 · 변형이 없는지 본다.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_decision_sessions, decision_evidence_store
from app.decision_selected_preview import (
    SELECTED_PREVIEW_SOURCE_SCREEN,
    is_selected_preview_record,
    kst_date_of,
    selected_target_label,
)

FILTERS = {
    "exclude_inverse": True,
    "exclude_leveraged": False,
    "exclude_synthetic": True,
    "exclude_futures": True,
}
# 미리보기 원문 — 줄바꿈 · 앞뒤 공백 · 부호 · %p · 천 단위 쉼표 · 화살표를 그대로 보존해야 한다.
PREVIEW_TEXT = (
    "[대상]\n- KODEX AI반도체TOP2플러스 (395160) · 보유 종목(ETF)\n"
    "- 평가비중 +4.47% · 손익률 -34.83%  \n\n"
    "[가격 흐름 · PC 저장 종가]\n- 변화율 5저장일 -18.91% · 20저장일 -15.24% (2026-09-10 → 2026-10-14)\n"
    "- 단기 KODEX200 차이(저장일 수 기준) 5저장일 -4.70%p\n"
    "[거래량]\n- 2026-10-14 거래량 4,655,670주 · 직전 20개 저장일 평균 3,463,997.80주\n"
)


def _sp(**override) -> dict:
    sp = {
        "target_kind": "holding",
        "generated_at": "2026-10-18T22:44:05+09:00",
        "evidence_as_of": {
            "target_as_of_date": "2026-10-14",
            "kodex200_as_of_date": "2026-10-14",
            "vix_as_of_date": "2026-10-13",
        },
        "preview_text": PREVIEW_TEXT,
    }
    sp.update(override)
    return sp


def _payload(*, candidate: dict | None = None, **override) -> dict:
    base = dict(
        asof="2026-10-14",
        source_screen=SELECTED_PREVIEW_SOURCE_SCREEN,
        filters=FILTERS,
        candidate_snapshot=[
            candidate
            or {
                "rank": None,
                "ticker": "395160",
                "name": "KODEX AI반도체TOP2플러스",
                "tags": [],
                "selected_preview": _sp(),
            }
        ],
        question_text=PREVIEW_TEXT,
        gpt_answer_text="① 함께 확인되는 사실 …",
        user_memo="업종 조정인지 다음 주 확인",
        user_verdict="needs_market_compare",
        next_checks=["반도체 ETF 3종 같은 기간 비교"],
        linked_market_refresh_id=None,
        market_context_snapshot=None,
        constituent_snapshot=None,
        overlap_snapshot=None,
        short_term_momentum_snapshot=None,
        data_quality_snapshot=None,
        ml_baseline_evidence_snapshot=None,
    )
    base.update(override)
    return base


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    fake_db = tmp_path / "decision_evidence.sqlite"
    monkeypatch.setattr(decision_evidence_store, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(api_decision_sessions, "DEFAULT_DB_PATH", fake_db)
    return TestClient(api_module.app)


def _save(client: TestClient, payload: dict) -> str:
    res = client.post("/decision/sessions", json=payload)
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _detail(client: TestClient, rid: str) -> dict:
    body = client.get(f"/decision/sessions/{rid}").json()
    assert body["status"] == "ok"
    return body["record"]


def _rows(client: TestClient) -> dict:
    body = client.get("/decision/sessions?limit=50").json()
    return {r["id"]: r for r in body["records"]}


# ── 저장 → 상세 · 목록 왕복 ────────────────────────────────────────────


def test_holding_round_trip_keeps_preview_exactly(client: TestClient) -> None:
    rid = _save(client, _payload())
    rec = _detail(client, rid)
    assert rec["source_screen"] == SELECTED_PREVIEW_SOURCE_SCREEN
    assert rec["asof"] == "2026-10-14"
    assert rec["filters"] == FILTERS
    assert len(rec["candidate_snapshot"]) == 1
    c = rec["candidate_snapshot"][0]
    assert c["rank"] is None and c["ticker"] == "395160"
    assert (
        c["selected_preview"] == _sp()
    )  # 원문 · 대상 종류 · 생성 시각 · 근거 날짜 3개 그대로
    assert rec["question_text"] == PREVIEW_TEXT
    assert rec["gpt_answer_text"] == "① 함께 확인되는 사실 …"
    assert rec["user_verdict"] == "needs_market_compare"
    assert rec["user_memo"] == "업종 조정인지 다음 주 확인"
    assert rec["ml_baseline_evidence_snapshot"] == {}  # 자동 보충 없음
    row = _rows(client)[rid]
    assert row["target_label"] == "KODEX AI반도체TOP2플러스(395160)"
    assert row["candidate_count"] == 1
    assert row["summary"] == "업종 조정인지 다음 주 확인"


def test_candidate_edited_question_keeps_original_preview(client: TestClient) -> None:
    sp = _sp(
        target_kind="candidate",
        preview_text="[대상]\n- SOL 반도체전공정 (475300) · 후보 ETF\n",
    )
    edited = "(내 질문) 겹치는 정도를 같이 봐 주세요.\n\n" + sp["preview_text"]
    rid = _save(
        client,
        _payload(
            candidate={
                "rank": 9,
                "ticker": "475300",
                "name": "SOL 반도체전공정",
                "tags": [],
                "selected_preview": sp,
            },
            question_text=edited,
        ),
    )
    rec = _detail(client, rid)
    assert rec["question_text"] == edited
    assert (
        rec["candidate_snapshot"][0]["selected_preview"]["preview_text"]
        == sp["preview_text"]
    )
    assert rec["candidate_snapshot"][0]["rank"] == 9
    assert _rows(client)[rid]["target_label"] == "SOL 반도체전공정(475300)"


def test_raw_stored_json_holds_preview_inside_candidate_snapshot(
    client: TestClient,
) -> None:
    rid = _save(client, _payload())
    con = sqlite3.connect(str(decision_evidence_store.DEFAULT_DB_PATH))
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(ai_session_records)")}
        raw = con.execute(
            "SELECT candidate_snapshot_json FROM ai_session_records WHERE id = ?",
            (rid,),
        ).fetchone()[0]
    finally:
        con.close()
    assert not any("selected" in c or "preview" in c for c in cols)  # 새 열 없음
    assert json.loads(raw)[0]["selected_preview"]["preview_text"] == PREVIEW_TEXT


# ── 가격 기준일 없음 · 기록 기준일 ──────────────────────────────────────


def test_price_date_unknown_uses_generated_kst_date_and_keeps_null(
    client: TestClient,
) -> None:
    sp = _sp(
        generated_at="2026-10-18T16:30:00+00:00",  # KST 2026-10-19 01:30
        evidence_as_of={
            "target_as_of_date": None,
            "kodex200_as_of_date": "2026-10-14",
            "vix_as_of_date": None,
        },
    )
    cand = {
        "rank": None,
        "ticker": "005930",
        "name": "삼성전자",
        "tags": [],
        "selected_preview": sp,
    }
    bad = client.post(
        "/decision/sessions", json=_payload(candidate=cand, asof="2026-10-18")
    )
    assert bad.status_code == 422 and "2026-10-19" in bad.text
    rid = _save(client, _payload(candidate=cand, asof="2026-10-19"))
    rec = _detail(client, rid)
    assert rec["asof"] == "2026-10-19"
    assert (
        rec["candidate_snapshot"][0]["selected_preview"]["evidence_as_of"][
            "target_as_of_date"
        ]
        is None
    )


def test_price_date_present_must_be_record_asof(client: TestClient) -> None:
    res = client.post("/decision/sessions", json=_payload(asof="2026-10-18"))
    assert res.status_code == 422 and "2026-10-14" in res.text


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-18T22:44:05+09:00", "2026-10-18"),
        ("2026-10-18T15:00:00+00:00", "2026-10-19"),
        ("2026-10-18T14:59:59Z", "2026-10-18"),
        ("2026-10-18T23:10:00", "2026-10-18"),  # 시간대 없음 = KST
        ("2026-10-18 20:00:00", "2026-10-18"),  # 화면 kstDateOf 와 같은 사례
        ("2026-10-18", "2026-10-18"),
        (" 2026-10-18T22:44:05+09:00 ", "2026-10-18"),
        ("not-a-time", None),
        ("", None),
    ],
)
def test_kst_date_of(value: str, expected: str | None) -> None:
    assert kst_date_of(value) == expected


# ── 선택 근거 모드 판정 · 일반 기록과 구분 ──────────────────────────────


def test_plain_one_candidate_record_is_not_selected_mode(client: TestClient) -> None:
    rid = _save(
        client,
        _payload(
            source_screen="market_discovery",
            candidate={
                "rank": 1,
                "ticker": "139260",
                "name": "TIGER 200 IT",
                "tags": [],
            },
            asof="2026-05-15",
        ),
    )
    row = _rows(client)[rid]
    assert row["target_label"] is None and row["candidate_count"] == 1
    assert _detail(client, rid)["candidate_snapshot"][0]["selected_preview"] is None


def test_legacy_rows_without_key_read_as_before(client: TestClient) -> None:
    _save(client, _payload())  # 표 생성
    con = sqlite3.connect(str(decision_evidence_store.DEFAULT_DB_PATH))
    try:
        for rid, screen in (
            ("legacy_md", "market_discovery"),
            ("legacy_odd", SELECTED_PREVIEW_SOURCE_SCREEN),
        ):
            con.execute(
                "INSERT INTO ai_session_records (id, created_at, updated_at, asof, "
                "source_screen, filters_json, candidate_snapshot_json, question_text, "
                "gpt_answer_text, user_verdict) "
                "VALUES (?, '2026-01-01T00:00:00.000000+0900', '2026-01-01T00:00:00.000000+0900', "
                "'2025-12-31', ?, ?, ?, 'q', 'a', 'hold')",
                (
                    rid,
                    screen,
                    json.dumps(FILTERS),
                    json.dumps([{"rank": 1, "ticker": "X", "name": "옛 후보"}]),
                ),
            )
        con.commit()
    finally:
        con.close()
    rows = _rows(client)
    assert rows["legacy_md"]["target_label"] is None
    assert (
        rows["legacy_odd"]["target_label"] is None
    )  # 화면 값만 같고 선택 근거가 없으면 선택 모드 아님
    assert (
        _detail(client, "legacy_md")["candidate_snapshot"][0]["selected_preview"]
        is None
    )


def test_selected_mode_predicate_needs_all_three() -> None:
    one = [{"ticker": "A", "name": "가", "selected_preview": {"preview_text": "x"}}]
    assert is_selected_preview_record(SELECTED_PREVIEW_SOURCE_SCREEN, one)
    assert not is_selected_preview_record("market_discovery", one)
    assert not is_selected_preview_record(SELECTED_PREVIEW_SOURCE_SCREEN, one * 2)
    assert not is_selected_preview_record(
        SELECTED_PREVIEW_SOURCE_SCREEN, [{"ticker": "A"}]
    )
    assert not is_selected_preview_record(
        SELECTED_PREVIEW_SOURCE_SCREEN, [{"selected_preview": "x"}]
    )
    assert (
        selected_target_label(
            SELECTED_PREVIEW_SOURCE_SCREEN, [{"ticker": "A", "selected_preview": {}}]
        )
        == "A"
    )
    assert (
        selected_target_label(
            SELECTED_PREVIEW_SOURCE_SCREEN, [{"name": " 가 ", "selected_preview": {}}]
        )
        == "가"
    )
    assert (
        selected_target_label(
            SELECTED_PREVIEW_SOURCE_SCREEN, [{"selected_preview": {}}]
        )
        is None
    )


# ── 쓰기 규칙 위반 = 422 · 저장 0 ──────────────────────────────────────


def _bad_cases() -> list[tuple[str, dict]]:
    sp_cand = {
        "rank": 1,
        "ticker": "A",
        "name": "가",
        "tags": [],
        "selected_preview": _sp(),
    }
    plain = {"rank": 2, "ticker": "B", "name": "나", "tags": []}
    return [
        ("preview_on_market_screen", _payload(source_screen="market_discovery")),
        ("two_candidates", _payload(candidate_snapshot=[sp_cand, plain])),
        ("missing_preview", _payload(candidate=plain)),
        (
            "blank_preview_text",
            _payload(
                candidate={**sp_cand, "selected_preview": _sp(preview_text="  \n ")}
            ),
        ),
        (
            "empty_preview_text",
            _payload(candidate={**sp_cand, "selected_preview": _sp(preview_text="")}),
        ),
        (
            "bad_kind",
            _payload(candidate={**sp_cand, "selected_preview": _sp(target_kind="etf")}),
        ),
        (
            "bad_generated_at",
            _payload(
                candidate={**sp_cand, "selected_preview": _sp(generated_at="어제")}
            ),
        ),
        ("ml_snapshot", _payload(ml_baseline_evidence_snapshot={"status": "ok"})),
        ("market_snapshot", _payload(market_context_snapshot={"regime": "x"})),
        ("quality_snapshot", _payload(data_quality_snapshot={"status": "ok"})),
        ("no_answer", _payload(gpt_answer_text="")),
    ]


@pytest.mark.parametrize("name", [n for n, _ in _bad_cases()])
def test_selected_mode_rule_violations_are_rejected(
    client: TestClient, name: str
) -> None:
    payload = dict(_bad_cases())[name]
    res = client.post("/decision/sessions", json=payload)
    assert res.status_code == 422, (name, res.text)
    assert client.get("/decision/sessions").json()["records"] == []


# ── 기존 전체 후보 전달은 그대로 ────────────────────────────────────────


def test_market_discovery_full_transfer_unchanged(client: TestClient) -> None:
    cands = [
        {"rank": i, "ticker": f"T{i}", "name": f"후보{i}", "tags": []}
        for i in range(1, 11)
    ]
    rid = _save(
        client,
        _payload(
            source_screen="market_discovery",
            candidate_snapshot=cands,
            asof="2026-10-15",
            question_text="상위 10 후보 질문",
            market_context_snapshot={"regime": "하락장"},
            ml_baseline_evidence_snapshot={"status": "ok"},
        ),
    )
    rec = _detail(client, rid)
    assert [c["ticker"] for c in rec["candidate_snapshot"]] == [
        f"T{i}" for i in range(1, 11)
    ]
    assert all(c["selected_preview"] is None for c in rec["candidate_snapshot"])
    assert rec["market_context_snapshot"] == {"regime": "하락장"}
    assert rec["ml_baseline_evidence_snapshot"] == {"status": "ok"}
    row = _rows(client)[rid]
    assert row["target_label"] is None and row["candidate_count"] == 10


# ── 저장소 층 직접 검사(API 모델을 거치지 않는 호출도 같은 규칙) ─────────────────


@pytest.mark.parametrize(
    ("label", "sp_over"),
    [
        ("bad_kind", {"target_kind": "etf"}),
        ("blank_generated_at", {"generated_at": "  "}),
        ("blank_preview_text", {"preview_text": " \n "}),
        ("missing_preview_text", {"preview_text": None}),
    ],
)
def test_store_layer_rejects_selected_preview_rule_violations(
    tmp_path: Path, label: str, sp_over: dict
) -> None:
    db = tmp_path / "decision_evidence.sqlite"
    p = _payload(gemini_answer_text="", claude_answer_text="")
    ok = decision_evidence_store.insert_record(
        db_path=db, **p
    )  # 같은 자료의 정상 저장(대조)
    p["candidate_snapshot"] = [
        {**p["candidate_snapshot"][0], "selected_preview": _sp(**sp_over)}
    ]
    with pytest.raises(decision_evidence_store.DecisionValidationError):
        decision_evidence_store.insert_record(db_path=db, **p)
    rows = decision_evidence_store.list_recent_records(db_path=db)
    assert [r["id"] for r in rows] == [ok["id"]], label
