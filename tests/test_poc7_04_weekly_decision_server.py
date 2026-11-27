"""POC7-04 판단 저장 · 다시 열기 · 연구 서버 · 브라우저 동작(tmp DB · tmp 저장 폴더만 · 라이브 DB 안 엶)."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pytest

from app.weekly_decision import page as PG
from app.weekly_decision import page_base as PB
from app.weekly_decision import page_live as PL
from app.weekly_decision import page_saved as PS
from app.weekly_decision import server as SV
from app.weekly_decision import store as ST
from tests._poc7_04_support import (
    _bump,
    FILTERS,
    OFFICIAL,
    FakeReader,
    _decision,
    trading,
    KST,
    END,
    _put,
    make_market,
    _snap,
    _app,
    _bid,
    _free_port,
    _req,
)


@pytest.fixture
def market(tmp_path: Path) -> Path:
    return make_market(tmp_path)


def test_clean_decision_rejects_bad_input() -> None:
    ok = ST.clean_decision({})
    assert ok["verdict"] == "unrecorded" and ok["used"] == [] and ok["ais"] == []
    assert ok["excerpt"] == "" and "ai" not in ok

    def one(**kw):
        return {"ais": [{"name": "GPT", "answer": "답", **kw}]}

    bad = [
        {"verdict": "useful"},
        {"used": "peer"},
        {"used": ["peer", "nope"]},
        {"reason": 3},
        {"reason": "x" * 501},
        {"ais": "GPT"},
        {"ais": [1]},
        {"ais": [{"name": "Bard", "answer": "x"}]},
        {"ais": [{"name": "기타", "answer": "x"}]},
        one(answer="x" * 60001),
        one(pasted_at="어제"),
        one(pasted_at=5),
        one(helpful="yes"),
        one(answer=3),
        {"ais": [{"name": "GPT", "answer": "a"}, {"name": "GPT", "answer": "b"}]},
        {
            "ais": [
                {"name": n, "answer": "a"} for n in ("GPT", "Gemini", "Claude", "GPT")
            ]
        },
        # 판정 2026-11-26 §3 — 답을 넣지 않은 칸은 '판단에 도움이 된 답'으로 고를 수 없음
        {"ais": [{"name": "Gemini", "answer": "  ", "helpful": True}]},
    ]
    for b in bad:
        with pytest.raises(ST.InputError):
            ST.clean_decision(b)
    got = ST.clean_decision(
        {
            "verdict": "hold",
            "used": ["ai_answer", "peer"],
            "ais": [
                {"name": "Claude", "answer": "답C", "helpful": True},
                {"name": "Gemini", "answer": ""},
                {
                    "name": "GPT",
                    "answer": " 답G ",
                    "pasted_at": "2026-11-24T01:00:00.000Z",
                },
            ],
            "ai_excerpt": "대목",
        }
    )
    assert got["used"] == ["peer", "ai_answer"]
    # 답을 넣은 칸만 · 고정 순서(GPT · Gemini · Claude) · 도움 선택 · 시각 그대로
    # 답 원문은 앞뒤 공백 · 줄바꿈까지 그대로(검증 F16) · 공백만인 칸은 답 없음
    assert [(a["name"], a["answer"], a["helpful"]) for a in got["ais"]] == [
        ("GPT", " 답G ", False),
        ("Claude", "답C", True),
    ]
    assert got["ais"][0]["pasted_at"] == "2026-11-24T01:00:00.000Z"
    assert got["excerpt"] == "대목"


def test_store_save_load_list_and_write_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 11, 24, 9, 0, tzinfo=KST)
    a = ST.save(
        tmp_path, now, _snap(), ST.clean_decision({"verdict": "hold", "reason": "r"})
    )
    doc = ST.load(tmp_path, a["review_id"])
    assert doc["decision"]["reason"] == "r" and doc["snapshot"]["ticker"] == "AAA001"
    b = ST.save(
        tmp_path, now + timedelta(minutes=1), _snap("DOM001"), ST.clean_decision({})
    )
    (tmp_path / "reviews" / "20261124T000000Z_cccccccc.json").write_text(
        "{", encoding="utf-8"
    )
    (tmp_path / "reviews" / "bad-name.json").write_text("{}", encoding="utf-8")
    listing = ST.list_reviews(tmp_path)
    assert [x["review_id"] for x in listing["items"]] == [
        b["review_id"],
        a["review_id"],
    ]
    assert sorted(listing["broken"]) == [
        "20261124T000000Z_cccccccc.json",
        "bad-name.json",
    ]
    for rid in ("../reviews/x", "20261124T000000Z_cccccccc", "nope"):
        with pytest.raises((KeyError, ValueError)):
            ST.load(tmp_path, rid)
    monkeypatch.setattr(ST, "new_id", lambda now: a["review_id"])
    with pytest.raises(FileExistsError):
        ST.save(tmp_path, now, _snap(), ST.clean_decision({}))
    assert (
        ST.load(tmp_path, a["review_id"])["decision"]["reason"] == "r"
    )  # 덮어쓰지 않음


def test_app_save_uses_server_snapshot_only(market: Path, tmp_path: Path) -> None:
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    bid = _bid(html)
    body = {
        "build_id": bid,
        "ticker": "AAA001",
        "verdict": "continue",
        "reason": "현지도 오름",
        "copy": "가짜",
    }
    code, out = app.save(body)
    assert code == 200
    doc = ST.load(app.root, out["review_id"])
    assert doc["snapshot"]["copy"] == app.builds[bid]["copy"] != "가짜"
    assert (
        doc["snapshot"]["screen"]["one"]
        == PG.screen_parts(app.builds[bid]["review"])["one"]
    )
    assert doc["decision"]["verdict"] == "continue"
    assert set(doc["snapshot"]["fingerprints"]) >= {"current"}
    assert app.save({"build_id": "nope", "ticker": "AAA001"})[0] == 409
    assert app.save({"build_id": bid, "ticker": "DOM001"})[0] == 400
    assert (
        app.save({"build_id": bid, "ticker": "AAA001", "verdict": "useful"})[0] == 422
    )
    assert app.save([1])[0] == 400
    assert len(ST.list_reviews(app.root)["items"]) == 1  # 거절은 아무것도 쓰지 않음


def test_app_context_reused_until_market_changes(market: Path, tmp_path: Path) -> None:
    app = _app(market, tmp_path)
    c1 = app.context()
    assert app.context() is c1
    with sqlite3.connect(market) as con:
        con.execute(
            "UPDATE etf_daily_price SET close = close + 1 WHERE ticker='AAA001' AND date=?",
            (END,),
        )
    c2 = app.context()
    assert c2 is not c1 and c2.fingerprint != c1.fingerprint


def test_saved_page_keeps_screen_after_market_changes(
    market: Path, tmp_path: Path
) -> None:
    app = _app(market, tmp_path)
    bid = _bid(app.page("AAA001"))
    _, out = app.save(
        {"build_id": bid, "ticker": "AAA001", "verdict": "hold", "reason": "이유1"}
    )
    one = app.builds[bid]["screen"]["one"]
    _put(market, "AAA001", [999.0], ["2026-11-24"])
    _put(market, "069500", [96.0], ["2026-11-24"])
    assert "11/24" in app.page("AAA001")  # 새 끝일로 다시 계산
    saved = PS.render_saved(ST.load(app.root, out["review_id"]))
    assert one in saved and "이유1" in saved and "11/24(화)" not in saved


@pytest.fixture
def served(market: Path, tmp_path: Path):
    app = _app(market, tmp_path)
    port = _free_port()
    httpd = SV.serve(app, port)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield app, port
    httpd.shutdown()
    httpd.server_close()


def test_http_flow_and_guards(served) -> None:
    app, port = served
    code, html = _req(port, "GET", "/?ticker=AAA001")
    assert code == 200
    bid = _bid(html)
    payload = json.dumps(
        {"build_id": bid, "ticker": "AAA001", "verdict": "hold", "reason": "근거부족"}
    ).encode()
    js = {"Content-Type": "application/json"}
    code, out = _req(
        port,
        "POST",
        "/api/reviews",
        payload,
        {**js, "Origin": f"http://127.0.0.1:{port}"},
    )
    assert code == 200
    rid = json.loads(out)["review_id"]
    assert _req(port, "GET", f"/reviews/{rid}")[1].count("근거부족") >= 1
    assert rid in _req(port, "GET", "/reviews")[1]
    assert _req(port, "GET", "/reviews/..%2Fx")[0] == 404
    assert _req(port, "GET", "/?ticker=NOPE99")[0] == 404
    assert _req(port, "GET", "/", headers={"Host": "evil.example"})[0] == 403
    assert (
        _req(
            port,
            "POST",
            "/api/reviews",
            payload,
            {**js, "Origin": "http://evil.example"},
        )[0]
        == 403
    )
    assert (
        _req(port, "POST", "/api/reviews", payload, {"Content-Type": "text/plain"})[0]
        == 415
    )
    assert (
        _req(
            port,
            "POST",
            "/api/reviews",
            b"",
            {**js, "Content-Length": str(SV.MAX_BODY + 1)},
        )[0]
        == 413
    )
    assert _req(port, "POST", "/api/reviews", b"{", js)[0] == 400
    assert _req(port, "POST", "/nope", payload, js)[0] == 404
    assert len(ST.list_reviews(app.root)["items"]) == 1


def test_saved_file_field_types_are_checked(tmp_path: Path) -> None:
    """검토 8 — 형이 틀린 저장 파일은 그 파일만 '읽지 못한 기록'(목록 · 화면은 계속)."""
    now = datetime(2026, 11, 24, 9, 0, tzinfo=KST)
    good = ST.save(tmp_path, now, _snap(), ST.clean_decision({}))
    doc = ST.load(tmp_path, good["review_id"])
    bads = {
        "20261124T000001Z_00000001": {"snapshot": {**doc["snapshot"], "end": None}},
        "20261124T000002Z_00000002": {
            "snapshot": {
                **doc["snapshot"],
                "review": {"rank": 1, "one_month": {"value": 1.0, "end": END}},
            }
        },
        "20261124T000003Z_00000003": {"decision": {**doc["decision"], "used": "peer"}},
        "20261124T000004Z_00000004": {"saved_at": "어제"},
        "20261124T000005Z_00000005": {
            "snapshot": {**doc["snapshot"], "screen": {"sub": 1}}
        },
    }
    for rid, patch in bads.items():
        bad = {**doc, **patch, "review_id": rid}
        (tmp_path / "reviews" / f"{rid}.json").write_text(
            json.dumps(bad), encoding="utf-8"
        )
    listing = ST.list_reviews(tmp_path)
    assert [x["review_id"] for x in listing["items"]] == [good["review_id"]]
    assert len(listing["broken"]) == 5
    assert "읽지 못한 기록 5건" in PS.render_list(listing)


def test_not_candidate_page_shows_reason(served) -> None:
    """검토 9 — 후보 목록 밖 ETF 는 사유와 함께."""
    app, port = served
    code, html = _req(port, "GET", "/?ticker=AAA003")
    assert (
        code == 404
        and "다 인도합성(합성)(AAA003)" in html
        and "조회 조건에서 제외" in html
    )
    code, html = _req(port, "GET", "/?ticker=NOPE99")
    assert code == 404 and "현재 ETF 목록에 없음" in html


ASKED_TEXT = {
    "this_screen": "질문: 이 화면의 복사문",
    "same_copy": "이 화면과 같은 복사문(같은 질문 원문을 앞서 연 화면에서 복사)",
    "other_screen": "다른 화면(기준일",
    "unknown_screen": "어느 화면의 복사문인지 모름</b>(서버를 다시 켰거나 오래돼",
    "mixed": "어느 질문의 답인지 하나로 정할 수 없음",
    "no_copy_record": "답을 붙일 때 복사한 기록 없음",
}


def test_ai_answer_question_provenance(market: Path, tmp_path: Path) -> None:
    """검토 4 · 검증자 r1 F2 — AI 답의 질문 출처는 '답을 붙일 때의 복사' 화면 번호를 서버 자료로 판정."""
    app = _app(market, tmp_path)
    b0 = _bid(app.page("AAA001"))
    _bump(market)
    b1 = _bid(app.page("AAA001"))
    b2 = _bid(app.page("AAA001"))
    assert app.builds[b0]["copy"] != app.builds[b2]["copy"]
    assert app.builds[b1]["copy"] == app.builds[b2]["copy"]
    base = {"ticker": "AAA001", "verdict": "hold"}
    cases = [
        ({"build_id": b2, "answer_from": b2}, "this_screen"),
        ({"build_id": b2, "answer_from": b1}, "same_copy"),
        ({"build_id": b2, "answer_from": b0}, "other_screen"),
        (
            {"build_id": b2, "answer_from": "20261124T000000Z_99999999"},
            "unknown_screen",
        ),
        # 서버가 모르는 화면 번호 + 이 화면 질문 원문과 같은 지문 = 같은 복사문(다른 지문이면 모름)
        (
            {
                "build_id": b2,
                "answer_from": "20261124T000000Z_99999999",
                "answer_sig": SV.copy_sig(app.builds[b2]["copy"]),
            },
            "same_copy",
        ),
        (
            {
                "build_id": b2,
                "answer_from": "20261124T000000Z_99999999",
                "answer_sig": SV.copy_sig(app.builds[b0]["copy"]),
            },
            "unknown_screen",
        ),
        ({"build_id": b2, "answer_from": "mixed"}, "mixed"),
        ({"build_id": b2}, "no_copy_record"),
        # 예전 칸 이름(마지막 복사)은 답의 출처로 쓰지 않는다
        ({"build_id": b2, "copied_build": b2}, "no_copy_record"),
        ({"build_id": b2, "answer_from": b2, "ai_answer": "  "}, "no_answer"),
    ]

    def body(extra):
        """칸 세 개 계약 — 출처 칸은 GPT 칸 안 · 화면 번호 · 예전 칸 이름(copied_build)은 본문 맨 위."""
        top = {k: extra[k] for k in ("build_id", "copied_build") if k in extra}
        entry = {"name": "GPT", "answer": "답"}
        entry.update({k: v for k, v in extra.items() if k not in top})
        return {**base, **top, "ais": [entry]}

    for extra, want in cases:
        extra = {("answer" if k == "ai_answer" else k): v for k, v in extra.items()}
        code, out = app.save(body(extra))
        assert code == 200
        doc = ST.load(app.root, out["review_id"])
        assert doc["schema"] == ST.SCHEMA
        ais = doc["decision"]["ais"]
        saved = PS.render_saved(doc)
        if want == "no_answer":
            assert ais == [] and "질문:" not in saved and saved.count("답 미입력") == 3
            continue
        ai = ais[0]
        assert ai["asked"]["state"] == want, extra
        assert not {"answer_from", "answer_sig", "copied_build"} & set(ai)
        if want == "other_screen":
            assert ai["asked"]["copy"] == app.builds[b0]["copy"]
        assert ASKED_TEXT[want] in saved
    for bad in ("../x", "MIXED", 3):
        assert app.save(body({"build_id": b2, "answer_from": bad}))[0] == 422
    for bad in ("XYZ", "0123456789", 7):
        assert app.save(body({"build_id": b2, "answer_sig": bad}))[0] == 422
    # 지문 계산 = FNV-1a 32비트(UTF-16 단위) — 화면 스크립트와 같은 값(브라우저 시험에서 대조)
    assert SV.copy_sig("") == "811c9dc5" and SV.copy_sig("a") == "e40c292c"


def test_question_copy_time_is_kept_and_shown(market: Path, tmp_path: Path) -> None:
    """반박 LOW8 — 답을 붙일 때 쓴 질문 복사의 시각을 저장하고 다시 열기에 보인다(형식이 틀리면 쓰기 전 거절)."""
    app = _app(market, tmp_path)
    b = _bid(app.page("AAA001"))
    base = {"build_id": b, "ticker": "AAA001", "verdict": "hold"}

    def gpt(**kw):
        return {**base, "ais": [{"name": "GPT", "answer": "답", **kw}]}

    code, out = app.save(
        gpt(answer_from=b, answer_copied_at="2026-11-24T01:00:00.000Z")
    )
    assert code == 200
    doc = ST.load(app.root, out["review_id"])
    assert doc["decision"]["ais"][0]["copied_at"] == "2026-11-24T01:00:00.000Z"
    assert "질문 복사 11/24 10:00" in PS.render_saved(doc)
    for bad in ("어제", 5):
        assert app.save(gpt(answer_copied_at=bad))[0] == 422


def test_pasted_time_shown_in_kst() -> None:
    assert PB.when_kst("2026-11-24T14:00:00.000Z") == "11/24 23:00"
    assert PB.when_kst("2026-11-17T00:14:11.101273+0900") == "11/17 00:14"
    assert PB.when_kst("2026-11-17T00:14:00") == "11/17 00:14"


# --- 검증자 r1 정정(2026-11-25) — 지난 판단 목록 시점 · AI 답 출처 · 저장 중 수정 보존 ---


def test_past_list_uses_same_review_time_filter(market: Path, tmp_path: Path) -> None:
    """F1 — 과거 기준일 화면의 '이 ETF 의 지난 판단'도 근거와 같은 검토 시점 필터(나중 판단 0건)."""
    root = tmp_path / "root"
    root.mkdir()

    def put(end: str, at: datetime, reason: str, ticker: str = "AAA001") -> None:
        dec = ST.clean_decision({"verdict": "continue", "reason": reason})
        ST.save(root, at, {**_snap(ticker), "end": end}, dec)

    put("2026-11-13", datetime(2026, 11, 13, 22, 0, tzinfo=KST), "그날밤판단")
    put("2026-11-13", datetime(2026, 11, 14, 0, 0, tzinfo=KST), "자정판단")
    put("2026-11-13", datetime(2026, 11, 25, 9, 0, tzinfo=KST), "나중판단")
    put("2026-11-20", datetime(2026, 11, 25, 9, 0, tzinfo=KST), "다음주판단")
    put(
        "2026-11-13",
        datetime(2026, 11, 13, 21, 0, tzinfo=KST),
        "다른종목판단",
        "DOM001",
    )
    app = SV.App(
        db=market,
        decision_db=_decision(tmp_path, []),
        root=root,
        end="2026-11-13",
        filters=FILTERS,
        sources=lambda: (OFFICIAL, None),
        reader=FakeReader(),
        is_trading=trading,
        now=lambda: datetime(2026, 11, 25, 10, 0, tzinfo=KST),
    )
    html = app.page("AAA001")
    assert "이 ETF 의 지난 판단" in html and "그날밤판단" in html
    for late in ("자정판단", "나중판단", "다음주판단", "다른종목판단"):
        assert late not in html, late
    rv = app.builds[_bid(html)]["review"]
    assert [r["reason"] for r in rv["past"]] == ["그날밤판단"]
    assert (
        rv["sessions"]["late"] == 2
    )  # 끝일 이하 · 검토 시점 뒤(자정 · 나중) — 다음 주 것은 끝일로 빠짐
    live = SV.App(
        db=market,
        decision_db=_decision(tmp_path, []),
        root=root,
        end=None,
        filters=FILTERS,
        sources=lambda: (OFFICIAL, None),
        reader=FakeReader(),
        is_trading=trading,
        now=lambda: datetime(2026, 11, 25, 10, 0, tzinfo=KST),
    )
    html = live.page("AAA001")
    assert all(r in html for r in ("그날밤판단", "자정판단", "나중판단", "다음주판단"))


def test_archive_list_marks_later_judgments_on_past_date_server(
    market: Path, tmp_path: Path
) -> None:
    """반박 L8 — 끝일을 지정한 서버의 전체 보관 목록은 검토 시점 이후 저장한 판단에 표시를 단다."""
    root = tmp_path / "root"
    root.mkdir()

    def put(end: str, at: datetime, reason: str) -> None:
        dec = ST.clean_decision({"verdict": "hold", "reason": reason})
        ST.save(root, at, {**_snap(), "end": end}, dec)

    put("2026-11-13", datetime(2026, 11, 13, 22, 0, tzinfo=KST), "그날")
    put("2026-11-13", datetime(2026, 11, 14, 0, 0, tzinfo=KST), "자정")
    put("2026-11-20", datetime(2026, 11, 20, 22, 0, tzinfo=KST), "다음주")
    # 기준일이 더 뒤면 저장 시각과 상관없이 표시(합성 — 기준일 11/20 판단을 11/13 밤에 저장)
    put("2026-11-20", datetime(2026, 11, 13, 21, 0, tzinfo=KST), "기준일뒤")

    def app_for(end: Optional[str]) -> SV.App:
        return SV.App(
            db=market,
            decision_db=_decision(tmp_path, []),
            root=root,
            end=end,
            filters=FILTERS,
            sources=lambda: (OFFICIAL, None),
            reader=FakeReader(),
            is_trading=trading,
            now=lambda: datetime(2026, 11, 25, 10, 0, tzinfo=KST),
        )

    html = app_for("2026-11-13").list_page()
    assert "11/13 기준 검토입니다" in html
    assert html.count("검토 시점 이후 저장</span>") == 3
    assert all(r in html for r in ("그날", "자정", "다음주", "기준일뒤"))
    live = app_for(None).list_page()
    assert "검토 시점 이후 저장" not in live and "기준 검토입니다" not in live


def test_static_page_does_not_claim_recording(market: Path, tmp_path: Path) -> None:
    """반박 L5 — 저장 안 되는 한 장(page 명령)은 '함께 남습니다'라고 쓰지 않는다."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    rv = app.builds[_bid(html)]["review"]
    static = PL.render_live(rv, build_id=None, candidates=[], reviews=[])
    assert "<span><b>AI 답 붙여 넣기</b></span>" in static
    assert "함께 남습니다" not in static
    assert "그때 복사해 둔 질문이 함께 남습니다" in html
